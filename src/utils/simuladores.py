import bpy
import os
import math
import csv
from datetime import datetime

class SimuladorFisico:
    """
    Gestiona el motor físico de Blender.
    Actúa como una capa de abstracción (Wrapper) sobre la API bpy.
    """

    def __init__(self, sim_id: int = 0):
        self.sim_id = sim_id
        self._limpiar_escena()

    def _limpiar_escena(self):
        """
        Limpia la escena, resetea la línea de tiempo y purga memoria.
        Preparado para soportar miles de iteraciones sin fugas (Memory Leaks).
        """
        scene = bpy.context.scene

        # 1. CRÍTICO: Resetear la línea de tiempo al inicio
        scene.frame_set(1)

        # 2. Eliminar todos los objetos físicos del Viewport
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()

        # 3. Limpiar caché y AUMENTAR PRECISIÓN del Rigid Body World
        if scene.rigidbody_world:
            scene.rigidbody_world.point_cache.frame_start = 1
            scene.rigidbody_world.point_cache.frame_end = 250

            # # SOLUCIÓN EFECTO BALA: Aumentamos los pasos de cálculo para evitar explosiones
            # scene.rigidbody_world.substeps_per_frame = 120  # Predeterminado es 10. 120 asegura colisiones de papel
            # scene.rigidbody_world.solver_iterations = 60    # Aumenta la rigidez de las colisiones

            # Liberar el caché de la memoria
            bpy.ops.ptcache.free_bake_all()

        # 4. GARBAGE COLLECTION: Eliminar mallas y materiales huérfanos
        # Cuando borras un objeto en Blender, su malla (geometría) se queda en la RAM.
        # Esto las elimina definitivamente para no saturar tu servidor Linux.
        for block in bpy.data.meshes:
            if block.users == 0:
                bpy.data.meshes.remove(block)

        for block in bpy.data.materials:
            if block.users == 0:
                bpy.data.materials.remove(block)

        # purgar keyframes.
        for block in bpy.data.actions:
            if block.users == 0:
                bpy.data.actions.remove(block)

        # Purgar objetos que hayan quedado residuales en la base de datos
        for block in bpy.data.objects:
            if block.users == 0:
                bpy.data.objects.remove(block)

    def importar_objeto(self, ruta_archivo: str, nombre_original: str, nombre_nuevo: str):
        directorio_interno = os.path.join(ruta_archivo, "Object")
        bpy.ops.wm.append(
            filepath=os.path.join(directorio_interno, nombre_original),
            directory=directorio_interno + "/",
            filename=nombre_original
        )
        objeto_importado = bpy.context.selected_objects[0]
        objeto_importado.name = nombre_nuevo
        return objeto_importado

    def posicionar_objeto(self, objeto, loc_x: float, loc_y: float, loc_z: float, rot_y_grados: float, rot_z_grados: float):
        objeto.location = (loc_x, loc_y, loc_z)
        objeto.rotation_euler[1] = math.radians(rot_y_grados)
        objeto.rotation_euler[2] = math.radians(rot_z_grados)

    def avanzar_simulacion(self, frames_a_avanzar: int = 100):
        """
        Avanza el tiempo del motor físico.
        Los objetos ya existentes interactuarán con los nuevos objetos añadidos.
        """
        scene = bpy.context.scene
        frame_inicial = scene.frame_current
        frame_final = frame_inicial + frames_a_avanzar

        # Extiende el límite de la escena para permitir el cálculo
        scene.frame_end = max(scene.frame_end, frame_final)

        print(f"Calculando física acumulativa (Frames: {frame_inicial} -> {frame_final})...")
        for frame in range(frame_inicial, frame_final + 1):
            scene.frame_set(frame)
            # Obliga al motor a actualizar la matriz 3D en modo Headless
            bpy.context.view_layer.update()

    def programar_caida_secuencial(self, objeto, frame_caida: int):
        """
        Bloquea el objeto en el aire y lo oculta hasta su frame específico de caída.
        Esto crea el efecto realista de que los votantes depositan la papeleta uno a uno.
        """
        # 1. Expandir el caché de físicas del mundo para asegurar que se calcule todo
        scene = bpy.context.scene
        if scene.rigidbody_world.point_cache.frame_end < frame_caida + 100:
            scene.rigidbody_world.point_cache.frame_end = frame_caida + 100
            scene.frame_end = frame_caida + 100

        # 2. Keyframes de Física (Propiedad Kinematic / Animated)
        # Kinematic = True significa que la gravedad NO le afecta (está sostenido)
        objeto.rigid_body.kinematic = True
        objeto.rigid_body.keyframe_insert(data_path="kinematic", frame=1)

        if frame_caida > 1:
            objeto.rigid_body.keyframe_insert(data_path="kinematic", frame=frame_caida - 1)

        # Kinematic = False significa que se suelta a merced del motor físico
        objeto.rigid_body.kinematic = False
        objeto.rigid_body.keyframe_insert(data_path="kinematic", frame=frame_caida)

        # 3. Keyframes de Visibilidad (Para que no floten fantasmalmente antes de votar)
        objeto.hide_viewport = True
        objeto.hide_render = True
        objeto.keyframe_insert(data_path="hide_viewport", frame=1)
        objeto.keyframe_insert(data_path="hide_render", frame=1)

        if frame_caida > 1:
            objeto.keyframe_insert(data_path="hide_viewport", frame=frame_caida - 1)
            objeto.keyframe_insert(data_path="hide_render", frame=frame_caida - 1)

        objeto.hide_viewport = False
        objeto.hide_render = False
        objeto.keyframe_insert(data_path="hide_viewport", frame=frame_caida)
        objeto.keyframe_insert(data_path="hide_render", frame=frame_caida)

    def guardar_escena(self, directorio_destino: str, nombre_archivo: str):
        if not nombre_archivo.endswith(".blend"):
            nombre_archivo += ".blend"
        ruta_completa = os.path.join(directorio_destino, nombre_archivo)
        os.makedirs(directorio_destino, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=ruta_completa)
        print(f"Escena estratigráfica guardada en: {ruta_completa}")

    def guardar_estado_final_como_inicio(self, directorio_destino: str, nombre_archivo: str):
        """
        Convierte la posición final de la simulación en la posición base (Frame 1).
        Limpia keyframes y prepara la escena para la fase de descarga.
        """
        # 1. Identificar y congelar la transformación visual de cada voto
        for obj in bpy.data.objects:
            if obj.name.startswith("voto_"):
                # Deseleccionamos todo para evitar aplicar cambios a objetos erróneos
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                # Aplicamos la transformación visual (convierte física en posición real)
                bpy.ops.object.visual_transform_apply()

                # Limpiamos animaciones previas para que no regresen al origen al dar 'Play'
                if obj.animation_data:
                    obj.animation_data_clear()

                # Configuramos para que sean dinámicos en la siguiente etapa
                if obj.rigid_body:
                    obj.rigid_body.kinematic = False

        # 2. Resetear el tiempo y limpiar el caché físico
        bpy.context.scene.frame_set(1)
        if bpy.context.scene.rigidbody_world:
            bpy.ops.ptcache.free_bake_all()
            bpy.context.scene.rigidbody_world.point_cache.frame_start = 1

        # 3. Guardado definitivo del archivo READY_TO_UNLOAD
        if not nombre_archivo.endswith(".blend"):
            nombre_archivo += ".blend"
        ruta_completa = os.path.join(directorio_destino, nombre_archivo)
        os.makedirs(directorio_destino, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=ruta_completa)

        print(f"[CONGELADO] Escena base guardada exitosamente en: {ruta_completa}")

    def obtener_estado_completo(self, objeto, metadatos_voto: dict):
        """Extrae la posición final e integra la información del JSON."""

        # Forzar una última actualización para garantizar que leemos la realidad física
        bpy.context.view_layer.update()

        pos = objeto.matrix_world.translation
        rot = [math.degrees(a) for a in objeto.matrix_world.to_euler()]

        # Ensamblamos el diccionario final cruzando datos físicos e información real
        return {
            "sim_id": self.sim_id,
            "seed": metadatos_voto.get("sim_seed"),
            "urn": metadatos_voto.get("urn"),
            "order": metadatos_voto.get("order"),
            "name_acronym": metadatos_voto.get("name_acronym"),
            "party_acronym": metadatos_voto.get("party_acronym"),
            "vote": metadatos_voto.get("vote"),
            "fold_pattern_used": metadatos_voto.get("fold_pattern_used"),
            "pos_x": round(pos.x, 6),
            "pos_y": round(pos.y, 6),
            "pos_z": round(pos.z, 6),
            "rot_x": round(rot[0], 2),
            "rot_y": round(rot[1], 2),
            "rot_z": round(rot[2], 2)
        }

    def registrar_multiples_datos_csv(self, lista_datos: list, directorio: str, nombre_archivo: str = "registro_votacion.csv"):
        """Recibe una lista de diccionarios y los guarda todos en el CSV."""
        if not lista_datos:
            return

        ruta_csv = os.path.join(directorio, nombre_archivo)
        os.makedirs(directorio, exist_ok=True)
        archivo_existe = os.path.isfile(ruta_csv)

        with open(ruta_csv, mode='a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=lista_datos[0].keys())
            if not archivo_existe:
                writer.writeheader()
            writer.writerows(lista_datos) # Escribe toda la lista de un golpe

        print(f"{len(lista_datos)} registros guardados en {nombre_archivo} para Sim ID: {self.sim_id}")