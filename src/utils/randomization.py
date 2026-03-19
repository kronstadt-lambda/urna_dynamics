"""
Módulo Estocástico (Capa Analítica)
-----------------------------------
Garantiza distribuciones aleatorias deterministas (a través de semillas)
para asegurar la reproducibilidad forense de cada simulacro de votación.
"""

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
        self.rot_x_rango = config.get("rotacion_y_rango", [-30, 30])
        self.rot_y_rango = config.get("rotacion_y_rango", [-30, 30])
        self.z_base = config.get("altura_z_base", 0.15)
        self.z_inc = config.get("incremento_z_por_voto", 0.05)

    def obtener_parametros_caida_libre(self, indice_local: int, centro_x: float = 0.0, centro_y: float = 0.0) -> Dict[str, float]:
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

        # Mapeo uniforme polar-cartesiano (r = R * sqrt(random))
        r = self.radio_max * math.sqrt(self.random_gen.random())
        theta = self.random_gen.uniform(0, 2 * math.pi)

        loc_x = round(centro_x + r * math.cos(theta), 3)
        loc_y = round(centro_y + r * math.sin(theta), 3)

        # Rotaciones estocásticas para añadir caos natural
        rot_x = round(self.random_gen.uniform(*self.rot_x_rango), 2)
        rot_y = round(self.random_gen.uniform(*self.rot_y_rango), 2)
        rot_z = round(self.random_gen.uniform(0, 360), 2)

        # Altura Z Dinámica para asegura que cada papel nazca sobre el anterior
        loc_z = round(self.z_base + (indice_local - 1) * self.z_inc, 3)

        return {
            "x": loc_x,
            "y": loc_y,
            "z": loc_z,
            "rot_x": rot_x,
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