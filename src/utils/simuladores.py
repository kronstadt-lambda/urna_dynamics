"""
Módulo de Simulación Física (Capa de Infraestructura)
-----------------------------------------------------
Encapsula toda la interacción con el motor de físicas de Blender (Bullet Physics).
Garantiza que la capa de lógica de negocio (escenarios) no dependa directamente de 'bpy'.
Maneja la prevención de Memory Leaks y la estabilización del caché de colisiones.
"""

import bpy
import math
import csv
from pathlib import Path
from typing import List, Dict, Any

class SimuladorFisico:
    """
    Orquestador universal del motor de física de Blender (bpy).

    Esta clase actúa como el motor central para diversos escenarios forenses
    (Votación, Vaciado, Volcado, Conteo). Provee una interfaz limpia para manipular
    objetos 3D, ejecutar cálculos de colisiones y extraer datos de posición
    sin que la lógica del escenario dependa directamente de la API de Blender.
    """

    def __init__(self, sim_id: int = 0, substeps: int = 120, solver_iters: int = 60, frame_start: int = 1):
        """
        Inicializa el entorno de simulación purgado y optimizado.

        Args:
            sim_id (int): Identificador para la trazabilidad de la simulación actual.
            substeps (int): Pasos de cálculo por frame (120 evita que papeles se atraviesen).
            solver_iters (int): Iteraciones del solver para estabilizar colisiones complejas.
            frame_start (int): Fotograma inicial de la línea de tiempo.
        """
        self.sim_id = sim_id
        self.substeps = substeps
        self.solver_iters = solver_iters
        self.frame_start = frame_start
        self._preparar_escena_limpia()

    def _preparar_escena_limpia(self) -> None:
        """Limpia la memoria RAM y configura el mundo físico desde cero."""
        scene = bpy.context.scene
        scene.frame_set(self.frame_start)

        # Borrado profundo de objetos para evitar dependencias fantasma
        for obj in list(bpy.context.scene.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

        # Asegurar que el mundo de física exista y esté configurado para alta fidelidad forense
        if not scene.rigidbody_world:
            bpy.ops.rigidbody.world_add()

        # Configuración del motor de física para evitar que los objetos atraviesen otros (tunneling)
        rbw = scene.rigidbody_world
        rbw.substeps_per_frame = self.substeps
        rbw.solver_iterations = self.solver_iters
        rbw.point_cache.frame_start = self.frame_start
        rbw.point_cache.frame_end = 250

        # Purga de Memoria
        self._ejecutar_garbage_collector_blender()
        bpy.ops.ptcache.free_bake_all()

    def _ejecutar_garbage_collector_blender(self) -> None:
        """Elimina bloques de datos (mallas, materiales) sin usuarios en memoria."""
        for collection in [bpy.data.meshes, bpy.data.materials,
                           bpy.data.actions, bpy.data.objects, bpy.data.collections]:
            for block in list(collection):
                if block.users == 0:
                    collection.remove(block)

    def importar_activo(self, ruta_blend: Path, nombre_obj: str, nombre_instancia: str) -> bpy.types.Object:
        """Importa un objeto 3D desde un archivo .blend externo."""
        dir_interno = str(ruta_blend / "Object")
        bpy.ops.wm.append(
            filepath=str(ruta_blend / "Object" / nombre_obj),
            directory=dir_interno + "/",
            filename=nombre_obj
        )
        obj = bpy.context.selected_objects[0]
        obj.name = nombre_instancia
        return obj

    def transformar_objeto(self, objeto: bpy.types.Object, loc: tuple, rot_grados: tuple) -> None:
        """Aplica coordenadas y rotaciones absolutas a un objeto."""
        objeto.location = loc
        objeto.rotation_euler = [math.radians(d) for d in rot_grados]

    def ejecutar_pasos_fisica(self, frames: int = 100) -> None:
        """
        Avanza la línea de tiempo forzando el cálculo físico dinámicamente.
        Expande el caché de manera automática para evitar que los objetos floten.
        """
        scene = bpy.context.scene
        f_final = scene.frame_current + frames
        scene.frame_end = max(scene.frame_end, f_final)

        # Expansión dinámica de la memoria de cálculo (+50 frames de margen)
        if scene.rigidbody_world and scene.rigidbody_world.point_cache.frame_end < f_final + 50:
            scene.rigidbody_world.point_cache.frame_end = f_final + 50

        # Recalculamos la física frame por frame
        for frame in range(scene.frame_current, f_final + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()

    def configurar_animacion_fisica(self, objeto: bpy.types.Object, frame_activacion: int, visible_inicial: bool = False) -> None:
        """
        Orquesta la transición de un objeto inmóvil a dinámico (caída libre).
        Gestiona keyframes de cinemática (Kinematic) y visibilidad.
        """
        scene = bpy.context.scene
        if scene.rigidbody_world.point_cache.frame_end < frame_activacion + 100:
            scene.rigidbody_world.point_cache.frame_end = frame_activacion + 100
            scene.frame_end = frame_activacion + 100

        # Mantenemos el objeto flotando (Kinematic = True) hasta el frame de activación
        objeto.rigid_body.kinematic = True
        objeto.rigid_body.keyframe_insert(data_path="kinematic", frame=1)

        if frame_activacion > 1:
            objeto.rigid_body.keyframe_insert(data_path="kinematic", frame=frame_activacion - 1)

        # Liberamos a la gravedad (Kinematic = False)
        objeto.rigid_body.kinematic = False
        objeto.rigid_body.keyframe_insert(data_path="kinematic", frame=frame_activacion)

        # Animación de visibilidad
        self._set_visibilidad(objeto, 1, visible_inicial)
        if frame_activacion > 1:
            self._set_visibilidad(objeto, frame_activacion - 1, visible_inicial)
        self._set_visibilidad(objeto, frame_activacion, not visible_inicial)

    def _set_visibilidad(self, objeto: bpy.types.Object, frame: int, visible: bool) -> None:
        """Controlador interno para animar el render y viewport."""
        ocultar = not visible
        objeto.hide_viewport = ocultar
        objeto.hide_render = ocultar
        objeto.keyframe_insert(data_path="hide_viewport", frame=frame)
        objeto.keyframe_insert(data_path="hide_render", frame=frame)

    def capturar_estado_datos(self, objeto: bpy.types.Object, metadatos: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae la matriz de transformación absoluta y la une con la metadata del voto."""
        bpy.context.view_layer.update()
        pos = objeto.matrix_world.translation
        rot = [math.degrees(a) for a in objeto.matrix_world.to_euler()]

        datos_fisicos = {
            "sim_id": self.sim_id,
            "pos_x": round(pos.x, 6), "pos_y": round(pos.y, 6), "pos_z": round(pos.z, 6),
            "rot_x": round(rot[0], 2), "rot_y": round(rot[1], 2), "rot_z": round(rot[2], 2)
        }
        return {**metadatos, **datos_fisicos}

    def guardar_resultado_csv(self, datos: List[Dict], ruta_dir: Path, archivo: str) -> None:
        """Persiste diccionarios de datos a un archivo CSV."""
        if not datos: return

        path_csv = ruta_dir / archivo
        ruta_dir.mkdir(parents=True, exist_ok=True)
        existe = path_csv.exists()

        with open(path_csv, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=datos[0].keys())
            if not existe: writer.writeheader()
            writer.writerows(datos)

    def guardar_escena(self, ruta_dir: Path, nombre_archivo: str) -> None:
        """Guarda la escena .blend conservando la animación en el caché."""
        bpy.context.scene.frame_set(self.frame_start)
        self._persistir_escena_blend(ruta_dir, nombre_archivo)

    def guardar_estado_final_como_inicio(self, ruta_dir: Path, nombre_archivo: str) -> None:
        """Congela las papeletas en su posición final, lista para iniciar el vaciado."""
        self._congelar_estratigrafia_votos()
        self._resetear_cronologia_y_cache()
        self._persistir_escena_blend(ruta_dir, nombre_archivo)

    def _congelar_estratigrafia_votos(self) -> None:
        for obj in bpy.data.objects:
            if obj.name.startswith("voto_"):
                self._aplicar_estado_estatico_a_objeto(obj)

    def _aplicar_estado_estatico_a_objeto(self, objeto: bpy.types.Object) -> None:
        """Destruye el historial de animación y clava el objeto en su matriz final."""
        bpy.context.view_layer.update()
        matriz_final = objeto.matrix_world.copy()

        if objeto.animation_data:
            objeto.animation_data_clear()

        objeto.matrix_world = matriz_final

        objeto.keyframe_insert(data_path="location", frame=self.frame_start)
        objeto.keyframe_insert(data_path="rotation_euler", frame=self.frame_start)

        if objeto.rigid_body:
            objeto.rigid_body.kinematic = True
            objeto.rigid_body.keyframe_insert(data_path="kinematic", frame=self.frame_start)

    def _resetear_cronologia_y_cache(self) -> None:
        bpy.context.scene.frame_set(self.frame_start)
        if bpy.context.scene.rigidbody_world:
            bpy.ops.ptcache.free_bake_all()
            bpy.context.scene.rigidbody_world.point_cache.frame_start = self.frame_start

    def _persistir_escena_blend(self, ruta_dir: Path, nombre_archivo: str) -> None:
        archivo = nombre_archivo if nombre_archivo.endswith(".blend") else f"{nombre_archivo}.blend"
        path_final = ruta_dir / archivo

        ruta_dir.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(path_final))
        print(f"[AUDITORÍA] Escena base lista para descarga en: {path_final}")

    def configurar_propiedades_superficie(self, objeto: bpy.types.Object, friccion: float, rebote: float) -> None:
        if objeto.rigid_body:
            objeto.rigid_body.friction = friccion
            objeto.rigid_body.restitution = rebote

    def obtener_frame_actual(self) -> int:
        return bpy.context.scene.frame_current

    def obtener_objeto_mas_cercano(self, coord_ref: tuple, lista_objetos: List[bpy.types.Object]) -> bpy.types.Object:
        """Encuentra el objeto más cercano a una coordenada usando distancia euclidiana."""
        bpy.context.view_layer.update()
        min_dist = float('inf')
        obj_cercano = None

        for obj in lista_objetos:
            dist = math.dist(obj.matrix_world.translation, coord_ref)
            if dist < min_dist:
                min_dist = dist
                obj_cercano = obj

        return obj_cercano

    def extraer_objeto_a_coordenada(self, objeto: bpy.types.Object, frame_actual: int, coord_destino: tuple) -> None:
        """Teletransporta un objeto a la hilera vertical de vaciado."""
        scene = bpy.context.scene
        if scene.rigidbody_world.point_cache.frame_end < frame_actual + 50:
            scene.rigidbody_world.point_cache.frame_end = frame_actual + 50
            scene.frame_end = frame_actual + 50

        # Anclamos el objeto a su posición actual un frame antes
        objeto.keyframe_insert(data_path="location", frame=frame_actual - 1)
        objeto.keyframe_insert(data_path="rotation_euler", frame=frame_actual - 1)

        if objeto.rigid_body:
            objeto.rigid_body.kinematic = True
            objeto.rigid_body.keyframe_insert(data_path="kinematic", frame=frame_actual)

        # Traslación instantánea (sin interpolación visual)
        objeto.location = coord_destino
        objeto.rotation_euler = (0, 0, 0)

        objeto.keyframe_insert(data_path="location", frame=frame_actual)
        objeto.keyframe_insert(data_path="rotation_euler", frame=frame_actual)

    def obtener_objeto_por_nombre(self, nombre: str) -> bpy.types.Object:
        return bpy.data.objects.get(nombre)

    def soltar_objeto_suspendido(self, objeto: bpy.types.Object, frame_actual: int, margen_frames: int = 100) -> None:
        """
        Reactiva la física de un objeto suspendido.
        Implementa protecciones contra la desactivación automática del motor.
        """
        scene = bpy.context.scene
        frame_limite = frame_actual + margen_frames

        if scene.rigidbody_world.point_cache.frame_end < frame_limite:
            scene.rigidbody_world.point_cache.frame_end = frame_limite
            scene.frame_end = frame_limite

        if objeto.rigid_body:
            # Obliga al motor a evaluar el objeto aunque lleve inactivo miles de frames
            objeto.rigid_body.use_deactivation = False

            # Anclaje explícito para evitar velocidades fantasma al iniciar gravedad
            objeto.keyframe_insert(data_path="location", frame=frame_actual - 1)
            objeto.keyframe_insert(data_path="rotation_euler", frame=frame_actual - 1)

            objeto.rigid_body.kinematic = True
            objeto.rigid_body.keyframe_insert(data_path="kinematic", frame=frame_actual - 1)

            # Liberación del voto
            objeto.rigid_body.kinematic = False
            objeto.rigid_body.keyframe_insert(data_path="kinematic", frame=frame_actual)

    def anular_rebote(self, objeto: bpy.types.Object) -> None:
        """Elimina el comportamiento elástico para simular manipulación humana."""
        if objeto.rigid_body:
            objeto.rigid_body.restitution = 0.0

    def actualizar_escena_a_frame(self, frame: int) -> None:
        """Mueve la línea de tiempo forzando el recálculo absoluto del Dependency Graph."""
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()