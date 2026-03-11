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

    def __init__(self, simulador: SimuladorFisico, generador: GeneradorAleatorioVotos, datos_votantes: List[Dict], intervalo_caida: int = 100):
        super().__init__(simulador, generador, datos_votantes) # Llama al init de EscenarioBase
        self.intervalo_caida = intervalo_caida

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

            # a) Preparación de metadatos para trazabilidad forense
            orden = voto_info['order']
            nombre_instancia = f"voto_{orden}"

            # b) Selección estocástica del patrón de doblado
            patron = self.generador.elegir_patron(voto_info['fold_pattern'])
            voto_info['fold_pattern_used'] = patron
            voto_info['sim_seed'] = self.generador.semilla_usada

            print(f"[*] Procesando votante {orden}: {voto_info['name_acronym']} (Frame {frame_actual})")

            # c) Importación y posicionamiento estocástico
            voto_obj = self.simulador.importar_activo(ruta_voto, patron, nombre_instancia)
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