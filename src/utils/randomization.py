import random
import math

class GeneradorAleatorioVotos:
    """
    Clase para generar parámetros estocásticos de caída de votos.
    Garantiza reproducibilidad mediante el uso de semillas (seeds).
    """

    def __init__(self, semilla: int = None):
        """
        Inicializa el generador. Si se provee una semilla,
        los resultados serán idénticos en cada ejecución.
        """
        self.semilla_usada = semilla if semilla is not None else random.randint(1, 10000)
        self.random_gen = random.Random(self.semilla_usada)

    def obtener_parametros_caida(self):
        """
        Genera los 4 parámetros aleatorios basados en las restricciones físicas:
        - loc_x, loc_y: Dentro de un círculo de radio 0.04m (distribución uniforme).
        - rot_y: 90 +/- 15 grados.
        - rot_z: 0 a 360 grados.
        """

        # 1. Coordenadas X e Y dentro de un radio de 0.04m
        # Para que sea uniforme en el área de un círculo, usamos sqrt(r)
        radio_max = 0.04
        r = radio_max * math.sqrt(self.random_gen.random())
        theta = self.random_gen.uniform(0, 2 * math.pi)

        loc_x = round(r * math.cos(theta), 3)
        loc_y = round(r * math.sin(theta), 3)

        # 2. Rotación en Y: 90 +/- 15 grados (75 a 105)
        rot_y = round(self.random_gen.uniform(-10, 10), 2)

        # 3. Rotación en Z: 0 a 360 grados
        rot_z = round(self.random_gen.uniform(0, 360), 2)

        return {
            "x": loc_x,
            "y": loc_y,
            "rot_y": rot_y,
            "rot_z": rot_z
        }

    def elegir_patron(self, lista_patrones: list) -> str:
        """Elige uniformemente un patrón de doblez de la lista provista."""
        return self.random_gen.choice(lista_patrones)