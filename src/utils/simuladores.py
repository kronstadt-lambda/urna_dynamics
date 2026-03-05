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
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()

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

    def obtener_estado_completo(self, objeto):
        """Extrae la posición y rotación final estática del objeto."""
        pos = objeto.matrix_world.translation
        rot = [math.degrees(a) for a in objeto.matrix_world.to_euler()]

        return {
            "sim_id": self.sim_id,
            "objeto": objeto.name,
            "pos_x": round(pos.x, 6),
            "pos_y": round(pos.y, 6),
            "pos_z": round(pos.z, 6),
            "rot_x": round(rot[0], 2),
            "rot_y": round(rot[1], 2),
            "rot_z": round(rot[2], 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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