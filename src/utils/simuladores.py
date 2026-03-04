import bpy
import os
import math
import csv
from datetime import datetime

class SimuladorFisico:
    """
    Clase encargada de gestionar el entorno, importar objetos y ejecutar la física.
    Diseñada para ser escalable en la investigación de auditoría geométrica.
    """

    def __init__(self, sim_id: int = 0):
        # Almacenamos el ID de esta simulación específica
        self.sim_id = sim_id
        self._limpiar_escena()

    def _limpiar_escena(self):
        """Elimina todos los objetos (cubo, luz, cámara) de la escena actual."""
        # Selecciona todos los objetos en la escena
        bpy.ops.object.select_all(action='SELECT')
        # Elimina los objetos seleccionados
        bpy.ops.object.delete()

    def importar_objeto(self, ruta_archivo: str, nombre_original: str, nombre_nuevo: str):
        """
        Importa un objeto desde un archivo .blend externo y lo renombra.
        Retorna la referencia al objeto en la escena actual.
        """
        # Blender requiere la ruta interna a la carpeta 'Object' dentro del .blend
        directorio_interno = os.path.join(ruta_archivo, "Object")

        # Ejecuta el comando Append (Añadir sin vincular)
        bpy.ops.wm.append(
            filepath=os.path.join(directorio_interno, nombre_original),
            directory=directorio_interno + "/",
            filename=nombre_original
        )

        # El objeto importado queda seleccionado por defecto. Lo capturamos.
        objeto_importado = bpy.context.selected_objects[0]
        # Cambiamos su nombre al solicitado (ej. 'urna_1' o 'voto_1')
        objeto_importado.name = nombre_nuevo

        return objeto_importado

    def posicionar_objeto(self, objeto, loc_x: float, loc_y: float, loc_z: float, rot_y_grados: float, rot_z_grados: float):
        """
        Ubica y rota un objeto en el espacio 3D.
        - rot_y_grados: Controla la inclinación del voto (ej. 90° +/- 15°).
        - rot_z_grados: Controla la dirección hacia la que apunta el objeto (0° a 360°).
        """
        # 1. Asignar la posición en el espacio global
        objeto.location = (loc_x, loc_y, loc_z)

        # 2. Aplicar rotacion convirtiendo grados a radianes
        # Eje Y : Inclinación lateral
        objeto.rotation_euler[1] = math.radians(rot_y_grados)
        # Eje Z : Rotación sobre su propio eje vertical
        objeto.rotation_euler[2] = math.radians(rot_z_grados)

    def ejecutar_simulacion_y_obtener_datos(self, frame_final: int, objeto_objetivo):
        """
        Calcula la física paso a paso hasta un frame específico
        y retorna la coordenada global final del objeto.
        """
        scene = bpy.context.scene
        scene.frame_start = 1
        scene.frame_end = frame_final

        # Bucle para forzar a Blender a calcular la física de Rigid Body cuadro por cuadro
        print(f"Iniciando cálculo físico hasta el frame {frame_final}...")
        for frame in range(1, frame_final + 1):
            scene.frame_set(frame)

        # Una vez que la simulación ha avanzado hasta el frame final, obtenemos la posición y rotación del objeto objetivo
        return self.obtener_estado_completo(objeto_objetivo)

    def guardar_escena(self, directorio_destino: str, nombre_archivo: str):
        """Guarda el estado actual de la simulación en un archivo .blend."""
        # Aseguramos que el nombre tenga la extensión correcta
        if not nombre_archivo.endswith(".blend"):
            nombre_archivo += ".blend"

        # Creamos la ruta completa
        ruta_completa = os.path.join(directorio_destino, nombre_archivo)

        # Verificamos si el directorio existe, si no, lo creamos
        if not os.path.exists(directorio_destino):
            os.makedirs(directorio_destino, exist_ok=True)
            print(f"Directorio creado: {directorio_destino}")

        # Guardamos el archivo principal de Blender
        bpy.ops.wm.save_as_mainfile(filepath=ruta_completa)
        print(f"Escena guardada exitosamente en: {ruta_completa}")

    def aplicar_transformaciones_y_resetear_origen(self, objeto):
        """
        Aplica transformaciones para estandarizar la malla y
        devuelve el origen al centro de masa para mantener la física realista.
        """
        # 1. Aseguramos selección y objeto activo
        bpy.ops.object.select_all(action='DESELECT')
        objeto.select_set(True)
        bpy.context.view_layer.objects.active = objeto

        # 2. Aplicamos todas las transformaciones (todas las escalas en 1.0, rotaciones en 0)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        # 3. Devolvemos el origen al centro de masa (recorreccion)
        bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='MEDIAN')

    def obtener_estado_completo(self, objeto):
        """
        Extrae la posición y rotación (Euler) final del objeto.
        Se recomienda guardar la rotación en grados para legibilidad en auditoría.
        """
        pos = objeto.matrix_world.translation
        # Convertimos la rotación de radianes a grados
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
        }

    def registrar_datos_csv(self, datos: dict, directorio: str, nombre_archivo: str = "registro_votacion.csv"):
        """
        Guarda los datos en un único archivo CSV.
        Si el archivo no existe, crea la cabecera; si existe, añade la fila (append).
        """
        ruta_csv = os.path.join(directorio, nombre_archivo)
        os.makedirs(directorio, exist_ok=True)

        archivo_existe = os.path.isfile(ruta_csv)

        with open(ruta_csv, mode='a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=datos.keys())
            if not archivo_existe:
                writer.writeheader()
            writer.writerow(datos)

        print(f"Datos de simulación {self.sim_id} registrados en: {nombre_archivo}")