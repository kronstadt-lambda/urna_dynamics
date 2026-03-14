from pathlib import Path
from typing import List, Dict, Any, Tuple
from utils.simuladores import SimuladorFisico
from utils.randomization import GeneradorAleatorioVotos

class EscenarioBase:
    """
    Clase base para la gestión de escenarios forenses en Blender.

    Provee la infraestructura común para cualquier tipo de simulación (Llenado,
    Vaciado, Conteo), gestionando el simulador, el generador estocástico y
    la persistencia de la memoria de los objetos.
    """

    def __init__(self, simulador: SimuladorFisico, generador: GeneradorAleatorioVotos, datos_votantes: List[Dict]):
        """
        Inicializa los componentes del escenario.

        Args:
            simulador: Instancia del motor físico universal.
            generador: Generador de parámetros aleatorios reproducibles.
            datos_votantes: Lista de diccionarios con la información de los votantes.
        """
        self.simulador = simulador
        self.generador = generador
        self.datos_votantes = datos_votantes
        self.objetos_en_escena: List[Tuple[Any, Dict]] = []

class EscenarioVotacion(EscenarioBase):
    """Orquestador del escenario de llenado de urna (Deposición).

    Simula el proceso secuencial de votación, manejando la importación de
    papeletas, su posicionamiento estocástico y el cálculo de la
    estratigrafía final resultante.
    """

    # # Parámetros de control de tiempo (en frames de Blender)
    # INTERVALO_CAIDA = 100  # Tiempo de espera entre la caída de cada papeleta

    def __init__(self, simulador: SimuladorFisico, generador: GeneradorAleatorioVotos, datos_votantes: List[Dict], intervalo_caida: int = 100, friccion: float = 0.5, rebote: float = 0.0):
        super().__init__(simulador, generador, datos_votantes) # Llama al init de EscenarioBase
        self.intervalo_caida = intervalo_caida
        self.friccion = friccion
        self.rebote = rebote

    def ejecutar_llenado(self, ruta_urna: Path, ruta_voto: Path) -> List[Dict]:
        """
        Ejecuta la coreografía completa de votación.

        Args:
            ruta_urna: Ruta al archivo .blend que contiene el modelo de la urna.
            ruta_voto: Ruta al archivo .blend con los patrones de doblado.

        Returns:
            List[Dict]: Dataset completo con la posición y rotación final de cada voto.
        """
        # Preparación del entorno
        self.simulador.importar_activo(ruta_urna, "urna_cylinder", "urna_activa")
        print(f"[SCENE] Urna inicializada desde: {ruta_urna.name}")

        frame_actual = self.simulador.frame_start

        # Bucle de deposición secuencial (voto por voto)
        for idx, voto_original in enumerate(self.datos_votantes):
            # Clonamos el diccionario para no contaminar la memoria global
            voto_info = voto_original.copy()

            # Inyectamos los parámetros físicos al dataset para trazabilidad en el CSV
            voto_info['friction'] = self.friccion
            voto_info['bounciness'] = self.rebote

            # a) Preparación de metadatos para trazabilidad forense
            orden = voto_info['order']
            nombre_instancia = f"voto_{orden}"

            # b) Selección estocástica del patrón de doblado
            patron = self.generador.elegir_patron(voto_info['fold_pattern'])
            voto_info['fold_pattern_used'] = patron
            voto_info['sim_seed'] = self.generador.semilla_usada

            print(f"[*] Procesando votante {orden}: {voto_info['name']} (Frame {frame_actual})")

            # c) Importación y posicionamiento estocástico
            voto_obj = self.simulador.importar_activo(ruta_voto, patron, nombre_instancia)
            # Aplicar las propiedades físicas al objeto recién importado
            self.simulador.configurar_propiedades_superficie(voto_obj, self.friccion, self.rebote)
            p = self.generador.obtener_parametros_caida_libre(orden)

            self.simulador.transformar_objeto(
                objeto=voto_obj,
                loc=(p['x'], p['y'], p['z']),
                rot_grados=(0, p['rot_y'], p['rot_z'])
            )

            # d) Ejecución de la física
            self.simulador.configurar_animacion_fisica(voto_obj, frame_activacion=frame_actual)
            self.simulador.ejecutar_pasos_fisica(frames=self.intervalo_caida)

            # e) Almacenar referencia para el análisis final
            self.objetos_en_escena.append((voto_obj, voto_info))
            frame_actual += self.intervalo_caida

        # Extracción de resultados estratigráficos
        print("\n[SCENE] Finalizado. Capturando telemetría final de la pila...")
        return [
            self.simulador.capturar_estado_datos(obj, info)
            for obj, info in self.objetos_en_escena
        ]

class EscenarioVaciado(EscenarioBase):
    """
    Orquestador del escenario de vaciado de urna (Extracción).
    Simula la acción humana de retirar el voto más próximo a la superficie
    uno por uno, permitiendo que la pila colapse y se asiente en el proceso.
    """

    def __init__(self, simulador: SimuladorFisico, generador: GeneradorAleatorioVotos, datos_votantes: List[Dict],
                 intervalo_vaciado: int = 50, punto_busqueda: tuple = (0.0, 0.0, 0.5),
                 coord_apilamiento: list = [1.0, 1.0, 0.5], inc_z_apilamiento: float = 0.1):
        super().__init__(simulador, generador, datos_votantes)
        self.intervalo_vaciado = intervalo_vaciado
        self.punto_busqueda = punto_busqueda
        self.coord_apilamiento = coord_apilamiento
        self.inc_z_apilamiento = inc_z_apilamiento

    def ejecutar_vaciado(self, objetos_en_escena: List[Tuple[Any, Dict]]) -> List[Dict]:
        """
        Ejecuta la coreografía de extracción voto a voto.

        Args:
            objetos_en_escena: Lista de tuplas (objeto_blender, metadata) proveniente del llenado.

        Returns:
            List[Dict]: Dataset con el orden exacto en que salieron los votos.
        """
        print("\n[SCENE] Iniciando proceso de vaciado estratigráfico...")
        frame_actual = self.simulador.obtener_frame_actual()

        # Parámetros de la regla de extracción
        punto_radial_busqueda = self.punto_busqueda
        coord_apilamiento_base = list(self.coord_apilamiento) # Usamos lista para poder mutar Z

        # Clonamos la lista para ir eliminando los votos que ya sacamos
        pool_extraccion = list(objetos_en_escena)
        resultados_extraccion = []
        rango_salida = 1 # El voto que salga primero tendrá rango 1

        while pool_extraccion:
            # 1. Aplicar Regla: Encontrar el voto más cercano a (0, 0, 0.5)
            lista_objetos_blender = [item[0] for item in pool_extraccion]
            obj_elegido = self.simulador.obtener_objeto_mas_cercano(punto_radial_busqueda, lista_objetos_blender)

            # 2. Recuperar su metadata asociada y sacarlo del pool
            tupla_elegida = next(item for item in pool_extraccion if item[0] == obj_elegido)
            metadata_voto = tupla_elegida[1].copy()
            pool_extraccion.remove(tupla_elegida)

            print(f"[*] Extrayendo {obj_elegido.name} (Rango de salida {rango_salida}) en Frame {frame_actual}...")

            # 3. Extraer y suspender en el aire
            coord_destino = tuple(coord_apilamiento_base)
            self.simulador.extraer_objeto_a_coordenada(obj_elegido, frame_actual, coord_destino)

            # 4. Registrar datos de salida
            metadata_voto["extraction_rank"] = rango_salida
            metadata_voto["extract_frame"] = frame_actual
            resultados_extraccion.append(metadata_voto)

            # 5. Aumentar Z para que el próximo voto flote 0.1m más arriba
            coord_apilamiento_base[2] += self.inc_z_apilamiento

            # 6. Aplicar dinámica: Avanzar 50 frames para que el agujero dejado colapse por gravedad
            self.simulador.ejecutar_pasos_fisica(frames=self.intervalo_vaciado)
            frame_actual += self.intervalo_vaciado
            rango_salida += 1

        print("\n[SCENE] Vaciado completado.")
        return resultados_extraccion