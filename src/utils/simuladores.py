import bpy
import math
import csv
from pathlib import Path
from typing import List, Dict, Any

class SimuladorFisico:
    """
    Orquestador universal del motor de física de Blender (bpy).

    Esta clase actúa como el motor central para diversos escenarios forenses
    (Votación, Vaciado, Conteo). Provee una interfaz limpia para manipular
    objetos 3D, ejecutar cálculos de colisiones y extraer datos de posición
    sin que la lógica del escenario dependa directamente de la API de Blender.
    """
    # Configuraciones de precisión física (Nivel Forense)
    # # 120 substeps aseguran que objetos delgados (papeletas) no se atraviesen.
    # SUBSTEPS_PER_FRAME = 120 # Por defecto es 10
    # SOLVER_ITERATIONS = 60 # Por defecto es 10
    # frame_start = 1 # Frame 1 siempre es el punto de partida en la línea de tiempo de Blender

    def __init__(self, sim_id: int = 0, substeps: int = 120, solver_iters: int = 60, frame_start: int = 1):
        """
        Inicializa el entorno de simulación purgado y optimizado.

        Args:
            sim_id (int): Identificador para trazabilidad de la corrida actual.
        """
        self.sim_id = sim_id
        self.substeps = substeps
        self.solver_iters = solver_iters
        self.frame_start = frame_start
        self._preparar_escena_limpia()

    def _preparar_escena_limpia(self) -> None:
        """
        Limpia la RAM de Blender y configura el mundo físico desde cero.

        Importante para evitar Memory Leaks en ejecuciones masivas (entorno Linux),
        asegurando que cada simulación inicie con recursos frescos.
        """
        scene = bpy.context.scene # Obtenemos la escena activa para manipular su línea de tiempo y mundo físico
        scene.frame_set(self.frame_start) # Reseteamos al Frame 1 para evitar problemas de caché residual

        # 1) Limpieza de Objetos y Mallas
        if bpy.context.object:
            bpy.ops.object.select_all(action='SELECT') # Seleccionamos todo para eliminarlo
            bpy.ops.object.delete() # Eliminamos los objetos seleccionados (esto no libera la malla de la RAM!)

        # 2) Reinicio del Rigid Body World (El contenedor de la física)
        if not scene.rigidbody_world:
            bpy.ops.rigidbody.world_add() # Si no existe un mundo de física, lo creamos.

        rbw = scene.rigidbody_world
        rbw.substeps_per_frame = self.substeps
        rbw.solver_iterations = self.solver_iters
        rbw.point_cache.frame_start = self.frame_start
        rbw.point_cache.frame_end = 250 # Límite inicial, expandible dinámicamente.

        # 3. Purga de Memoria (Elimina datos huérfanos de la RAM)
        self._ejecutar_garbage_collector_blender()
        bpy.ops.ptcache.free_bake_all()

    def _ejecutar_garbage_collector_blender(self) -> None:
        """
        Elimina bloques de datos (mallas, materiales) que ya no tienen usuarios.
        """
        for collection in [bpy.data.meshes, bpy.data.materials,
                           bpy.data.actions, bpy.data.objects]:
            for block in collection:
                if block.users == 0:
                    collection.remove(block)

    def importar_activo(self, ruta_blend: Path, nombre_obj: str, nombre_instancia: str) -> bpy.types.Object:
        """
        Importa un activo (urna, papeleta, mesa) desde un archivo de assets.

        Args:
            ruta_blend (Path): Ruta al archivo .blend (usa pathlib).
            nombre_obj (str): Nombre del objeto dentro del archivo .blend.
            nombre_instancia (str): Nombre único para esta simulación.
        """
        dir_interno = str(ruta_blend / "Object")
        bpy.ops.wm.append(
            filepath=str(ruta_blend / "Object" / nombre_obj),
            directory=dir_interno + "/",
            filename=nombre_obj
        ) # El operador 'append' de Blender importa el objeto y lo selecciona automáticamente
        obj = bpy.context.selected_objects[0] # El objeto importado es el que queda seleccionado
        obj.name = nombre_instancia # Renombramos la instancia para evitar conflictos en la escena
        return obj

    def transformar_objeto(self, objeto: bpy.types.Object, loc: tuple, rot_grados: tuple) -> None:
        """
        Aplica posición y rotación a un objeto en el espacio 3D.

        Args:
            loc (tuple): Coordenadas (x, y, z).
            rot_grados (tuple): Rotaciones en grados (x, y, z).
        """
        objeto.location = loc
        objeto.rotation_euler = [math.radians(d) for d in rot_grados]

    def ejecutar_pasos_fisica(self, frames: int = 100) -> None:
        """
        Avanza la línea de tiempo para calcular interacciones físicas.

        Indispensable en modo Headless para forzar la actualización de matrices.
        """
        scene = bpy.context.scene # Obtenemos la escena activa para manipular su línea de tiempo
        f_final = scene.frame_current + frames # Calculamos el frame final al que queremos avanzar
        scene.frame_end = max(scene.frame_end, f_final) # Aseguramos que el frame final esté dentro del rango de la línea de tiempo

        # Avanzamos frame por frame para que el motor de física calcule las colisiones y actualice las posiciones
        for frame in range(scene.frame_current, f_final + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()

    def configurar_animacion_fisica(self, objeto: bpy.types.Object, frame_activacion: int, visible_inicial: bool = False) -> None:
        """
                Controla cuándo un objeto empieza a ser afectado por la gravedad.

                Utiliza keyframes en la propiedad 'kinematic' para 'soltar' el objeto
                en el momento preciso del escenario (Votación o Vaciado).
                """
        # ====================================================================
        # [CORRECCIÓN CRÍTICA]: Expansión dinámica del caché de físicas
        # Obliga a Blender a extender la memoria de cálculo para los nuevos frames
        # ====================================================================
        scene = bpy.context.scene
        if scene.rigidbody_world.point_cache.frame_end < frame_activacion + 100:
            scene.rigidbody_world.point_cache.frame_end = frame_activacion + 100
            scene.frame_end = frame_activacion + 100

        # Control Kinematic (True = Inmóvil, False = Dinámico)
        objeto.rigid_body.kinematic = True
        objeto.rigid_body.keyframe_insert(data_path="kinematic", frame=1)

        if frame_activacion > 1:
            objeto.rigid_body.keyframe_insert(data_path="kinematic", frame=frame_activacion - 1)

        objeto.rigid_body.kinematic = False
        objeto.rigid_body.keyframe_insert(data_path="kinematic", frame=frame_activacion)

        # Gestión de visibilidad
        self._set_visibilidad(objeto, 1, visible_inicial)
        if frame_activacion > 1:
            self._set_visibilidad(objeto, frame_activacion - 1, visible_inicial)
        self._set_visibilidad(objeto, frame_activacion, not visible_inicial)

    def _set_visibilidad(self, objeto: bpy.types.Object, frame: int, visible: bool) -> None:
        """
        Helper interno para ocultar/mostrar objetos en frames específicos.
        """
        ocultar = not visible # Si visible es True, ocultar será False, y viceversa
        objeto.hide_viewport = ocultar # Controla la visibilidad en el viewport (interfaz de Blender)
        objeto.hide_render = ocultar # Controla la visibilidad en el render final (importante para inspecciones visuales)
        objeto.keyframe_insert(data_path="hide_viewport", frame=frame) # Insertamos keyframe para la visibilidad en el viewport
        objeto.keyframe_insert(data_path="hide_render", frame=frame) # Insertamos keyframe para la visibilidad en el render

    def capturar_estado_datos(self, objeto: bpy.types.Object, metadatos: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrae la telemetría física final y la combina con datos de origen.

        Args:
            objeto: El objeto de Blender procesado.
            metadatos: Diccionario con info del votante/papeleta (proveniente de JSON).
        Returns:
            Un diccionario combinado listo para guardar en CSV.
        """
        bpy.context.view_layer.update() # Forzamos una actualización para asegurarnos de que leemos la posición física real después de la simulación
        pos = objeto.matrix_world.translation # Extraemos la posición global del objeto en el espacio 3D
        rot = [math.degrees(a) for a in objeto.matrix_world.to_euler()] # Extraemos la rotación global y la convertimos a grados para mayor legibilidad

        datos_fisicos = {
            "sim_id": self.sim_id,
            "pos_x": round(pos.x, 6), "pos_y": round(pos.y, 6), "pos_z": round(pos.z, 6),
            "rot_x": round(rot[0], 2), "rot_y": round(rot[1], 2), "rot_z": round(rot[2], 2)
        }
        return {**metadatos, **datos_fisicos}

    def guardar_resultado_csv(self, datos: List[Dict], ruta_dir: Path, archivo: str) -> None:
        """
        Persiste los resultados en un archivo CSV para auditoría estadística.
        """
        if not datos: return

        path_csv = ruta_dir / archivo
        ruta_dir.mkdir(parents=True, exist_ok=True)
        existe = path_csv.exists()

        # Escribimos los datos en el CSV, añadiendo la cabecera solo si el archivo no existía previamente
        with open(path_csv, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=datos[0].keys())
            if not existe: writer.writeheader()
            writer.writerows(datos)

    def guardar_escena(self, ruta_dir: Path, nombre_archivo: str) -> None:
        """
        Guarda la escena actual conservando toda la física y animaciones.

        Este método es fundamental para la auditoría visual, ya que permite
        inspeccionar la trayectoria completa y las colisiones de las papeletas
        durante la simulación.

        Args:
            ruta_dir: Objeto Path al directorio de destino (ej. RESULTS_VOTE_DIR).
            nombre_archivo: Nombre del archivo (se le añadirá .blend si no lo tiene).
        """
        # Rebobinamos al inicio para que al abrir el archivo esté listo para darle 'Play'
        bpy.context.scene.frame_set(self.frame_start)

        # Reutilizamos el helper interno para mantener el principio DRY
        self._persistir_escena_blend(ruta_dir, nombre_archivo)

    def guardar_estado_final_como_inicio(self, ruta_dir: Path, nombre_archivo: str) -> None:
        """Fija la posición final de la simulación y crea un punto base para el vaciado.

        Orquestador que coordina la congelación de mallas, el reinicio de la
        línea de tiempo y la persistencia del archivo de inspección.
        """
        self._congelar_estratigrafia_votos()
        self._resetear_cronologia_y_cache()
        self._persistir_escena_blend(ruta_dir, nombre_archivo)

    def _congelar_estratigrafia_votos(self) -> None:
        """Busca y transforma la física de cada papeleta en coordenadas fijas."""
        for obj in bpy.data.objects:
            if obj.name.startswith("voto_"):
                self._aplicar_estado_estatico_a_objeto(obj)

    def _aplicar_estado_estatico_a_objeto(self, objeto: bpy.types.Object) -> None:
        """Convierte la transformación visual en real y limpia datos de animación."""
        # 1. Selección y activación para operaciones de la API de Blender
        bpy.ops.object.select_all(action='DESELECT')
        objeto.select_set(True)
        bpy.context.view_layer.objects.active = objeto

        # 2. Congelar posición final y eliminar keyframes previos
        bpy.ops.object.visual_transform_apply()
        if objeto.animation_data:
            objeto.animation_data_clear()

        # 3. Preparar para que sea dinámico en la siguiente etapa (vaciado)
        if objeto.rigid_body:
            objeto.rigid_body.kinematic = False

    def _resetear_cronologia_y_cache(self) -> None:
        """Vuelve al inicio de la simulación y purga el caché del motor físico."""
        bpy.context.scene.frame_set(self.frame_start)
        if bpy.context.scene.rigidbody_world:
            bpy.ops.ptcache.free_bake_all()
            bpy.context.scene.rigidbody_world.point_cache.frame_start = self.frame_start

    def _persistir_escena_blend(self, ruta_dir: Path, nombre_archivo: str) -> None:
        """Gestiona la creación del directorio y el guardado físico del archivo .blend."""
        # Normalización del nombre y ruta con pathlib
        archivo = nombre_archivo if nombre_archivo.endswith(".blend") else f"{nombre_archivo}.blend"
        path_final = ruta_dir / archivo

        ruta_dir.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(path_final))
        print(f"[AUDITORÍA] Escena base lista para descarga en: {path_final}")