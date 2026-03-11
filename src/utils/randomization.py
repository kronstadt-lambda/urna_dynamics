import random
import math
from typing import List, Dict, Optional

class GeneradorAleatorioVotos:
    """
    Generador estocástico para los parámetros de posicionamiento de caída de los votos.

    Esta clase centraliza la lógica aleatoria para asegurar que la deposición
    de las papeletas en la urna sea reproducible. Utiliza una semilla (seed)
    para que cada "escenario" forense pueda ser replicado exactamente.

    Attributes:
        semilla_usada (int): Semilla aplicada para la generación actual.
        random_gen (random.Random): Instancia independiente del generador.
    """
    # # Parámetros físicos de lanzamiento
    # RADIO_MAX_LANZAMIENTO = 0.04 # Metros: radio del círculo de caída
    # ROTACION_Y_RANGO = (-10, 10) # Grados: balanceo lateral al soltar
    # ALTURA_Z_BASE = 0.15         # Metros: altura mínima de inicio
    # INCREMENTO_Z_POR_VOTO = 0.05 # Metros: separación para evitar colisiones iniciales

    def __init__(self, semilla: Optional[int] = None, config_tecnica: Dict = None):
        """
        Inicializar el generador con una semilla específica.

        Args:
            semilla (int, optional): Valor para garantizar la reproducibilidad.
                Si es None, se genera un entero aleatorio entre 1 y 10000.
        """
        self.semilla_usada = semilla if semilla is not None else random.randint(1, 10000)
        self.random_gen = random.Random(self.semilla_usada)

        # Asignar parámetros dinámicos (con valores por defecto por seguridad)
        config = config_tecnica or {}
        self.radio_max = config.get("radio_max_lanzamiento", 0.04)
        self.rot_y_rango = config.get("rotacion_y_rango", [-10, 10])
        self.z_base = config.get("altura_z_base", 0.15)
        self.z_inc = config.get("incremento_z_por_voto", 0.05)

    def obtener_parametros_caida_libre(self, orden: int) -> Dict[str, float]:
        """
        Calcula las coordenadas y rotaciones iniciales para un voto.

        Utiliza una distribución uniforme circular para las coordenadas X e Y,
        y un incremento dinámico determinista en Z para evitar que el motor de física de
        Blender detecte colisiones internas al instanciar los objetos.

        Args:
            orden (int): El número secuencial del votante en la lista.

        Returns:
            Dict[str, float]: Diccionario con las claves 'x', 'y', 'z',
                'rot_y' y 'rot_z'.
        """

        # 1) Posición X/Y: Distribución uniforme en un disco
        # Para lograr una distribución uniforme en un círculo, no basta con elegir r y theta de forma independiente.
        # La fórmula correcta es: r = R * sqrt(random()), donde R es el radio
        r = self.radio_max * math.sqrt(self.random_gen.random())
        theta = self.random_gen.uniform(0, 2 * math.pi)

        loc_x = round(r * math.cos(theta), 3)
        loc_y = round(r * math.sin(theta), 3)

        # 2) Rotaciones: Orientación estocástica de la papeleta
        rot_y = round(self.random_gen.uniform(*self.rot_y_rango), 2)
        rot_z = round(self.random_gen.uniform(0, 360), 2)

        # 3) Altura Z Dinámica: Asegura que cada papel nazca sobre el anterior
        loc_z = round(self.z_base + (orden - 1) * self.z_inc, 3)

        return {
            "x": loc_x,
            "y": loc_y,
            "z": loc_z,
            "rot_y": rot_y,
            "rot_z": rot_z
        }

    def elegir_patron(self, lista_patrones: list) -> str:
        """
        Selecciona de forma aleatoria un patrón de doblado de la papeleta.

        En un análisis forense, un mismo votante podría haber doblado el voto
        de distintas maneras. Esta función elige una de las opciones registradas.

        Args:
            lista_patrones (List[str]): Nombres de los modelos .blend de doblado.

        Returns:
            str: El nombre del patrón seleccionado para la simulación.
        """
        return self.random_gen.choice(lista_patrones)