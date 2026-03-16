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

    def ejecutar_llenado(self, ruta_urna: Path, ruta_voto: Path, posiciones_urnas: dict) -> List[Dict]:
        """
        Ejecuta la coreografía completa de votación.

        Args:
            ruta_urna: Ruta al archivo .blend que contiene el modelo de la urna.
            ruta_voto: Ruta al archivo .blend con los patrones de doblado.

        Returns:
            List[Dict]: Dataset completo con la posición y rotación final de cada voto.
        """
        # Preparación del entorno
        for nombre_urna, coords in posiciones_urnas.items():
            urna_obj = self.simulador.importar_activo(ruta_urna, "urna_cylinder", f"urna_activa_{nombre_urna}")
            self.simulador.transformar_objeto(urna_obj, loc=tuple(coords), rot_grados=(0,0,0))
            print(f"[SCENE] {nombre_urna} inicializada en {coords}")

        frame_actual = self.simulador.frame_start
        contadores_locales = {"urn1": 1, "urn2": 1}

        # Bucle de deposición secuencial (voto por voto)
        for idx, voto_original in enumerate(self.datos_votantes):
            # Clonamos el diccionario para no contaminar la memoria global
            voto_info = voto_original.copy()

            # Inyectamos los parámetros físicos al dataset para trazabilidad en el CSV
            voto_info['friction'] = self.friccion
            voto_info['bounciness'] = self.rebote

            urna_destino = voto_info['urn']
            idx_local = contadores_locales[urna_destino]
            contadores_locales[urna_destino] += 1
            pos_urna = posiciones_urnas[urna_destino]

            # a) Preparación de metadatos para trazabilidad forense
            orden = voto_info['order']
            nombre_instancia = f"voto_{urna_destino}_{orden}"

            # b) Selección estocástica del patrón de doblado
            patron = self.generador.elegir_patron(voto_info['fold_pattern'])
            voto_info['fold_pattern_used'] = patron
            voto_info['sim_seed'] = self.generador.semilla_usada

            print(f"[*] Procesando votante {orden} -> urna {urna_destino}: {voto_info['name']} (Frame {frame_actual})")

            # c) Importación y posicionamiento estocástico
            voto_obj = self.simulador.importar_activo(ruta_voto, patron, nombre_instancia)
            # Aplicar las propiedades físicas al objeto recién importado
            self.simulador.configurar_propiedades_superficie(voto_obj, self.friccion, self.rebote)
            p = self.generador.obtener_parametros_caida_libre(idx_local, centro_x=pos_urna[0], centro_y=pos_urna[1])

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

    def ejecutar_vaciado(self, objetos_en_escena: List[Tuple[Any, Dict]], puntos_busqueda: dict) -> List[Dict]:
        print("\n[SCENE] Iniciando proceso de vaciado secuencial (Urna 1 -> Urna 2)...")
        frame_actual = self.simulador.obtener_frame_actual()

        # El apilamiento se mantiene vivo a través del cambio de urnas
        coord_apilamiento_base = list(self.coord_apilamiento)
        rango_salida = 1
        resultados_extraccion = []

        # Forzamos el orden de vaciado
        orden_urnas = ["urn1", "urn2"]

        for urna_actual in orden_urnas:
            print(f"\n[SCENE] >>> Vaciando {urna_actual.upper()} <<<")
            punto_radial_busqueda = puntos_busqueda.get(urna_actual, [0,0,0.5])

            # Filtramos solo los votos de la urna que toca
            pool_extraccion = [item for item in objetos_en_escena if item[1]['urn'] == urna_actual]

            while pool_extraccion:
                lista_objetos_blender = [item[0] for item in pool_extraccion]
                obj_elegido = self.simulador.obtener_objeto_mas_cercano(tuple(punto_radial_busqueda), lista_objetos_blender)

                tupla_elegida = next(item for item in pool_extraccion if item[0] == obj_elegido)
                metadata_voto = tupla_elegida[1].copy()
                pool_extraccion.remove(tupla_elegida)

                print(f"[*] Extrayendo de {urna_actual}: {obj_elegido.name} (Global {rango_salida}) en Frame {frame_actual}...")

                coord_destino = tuple(coord_apilamiento_base)
                self.simulador.extraer_objeto_a_coordenada(obj_elegido, frame_actual, coord_destino)

                metadata_voto["extraction_rank"] = rango_salida
                metadata_voto["extract_frame"] = frame_actual
                resultados_extraccion.append(metadata_voto)

                # El Z sigue creciendo, unificando la hilera
                coord_apilamiento_base[2] += self.inc_z_apilamiento

                self.simulador.ejecutar_pasos_fisica(frames=self.intervalo_vaciado)
                frame_actual += self.intervalo_vaciado
                rango_salida += 1

        print("\n[SCENE] Vaciado completado.")
        return resultados_extraccion