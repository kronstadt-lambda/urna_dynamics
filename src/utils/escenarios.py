from utils.simuladores import SimuladorFisico
from utils.randomization import GeneradorAleatorioVotos

class EscenarioVotacion:
    """
    Manager que orquesta la simulación del 'Primer Escenario' (Llenado de urna).
    Controla el flujo físico secuencial de n votos.
    """

    def __init__(self, simulador: SimuladorFisico, generador: GeneradorAleatorioVotos, num_votos: int):
        self.simulador = simulador
        self.generador = generador
        self.num_votos = num_votos
        self.votos_en_urna = []

    def ejecutar_llenado(self, ruta_urna: str, ruta_voto: str, patron_voto: str) -> list:
        """
        Ejecuta la caída secuencial de votos programando sus keyframes en la línea de tiempo.
        """
        self.simulador.importar_objeto(ruta_urna, "urna_cylinder", "urna_1")
        print("[ESCENARIO] Urna inicializada.")

        # Variable para controlar la línea de tiempo (iniciamos en el frame 1)
        frame_actual = 1
        intervalo_espera = 100  # Frames que tarda un voto en asentarse

        for i in range(1, self.num_votos + 1):
            nombre_voto = f"voto_{i}"
            print(f"\n[ESCENARIO] Votante {i} ingresando papeleta en el Frame {frame_actual}...")

            voto = self.simulador.importar_objeto(ruta_voto, patron_voto, nombre_voto)
            p = self.generador.obtener_parametros_caida()

            self.simulador.posicionar_objeto(
                objeto=voto,
                loc_x=p['x'],
                loc_y=p['y'],
                loc_z=0.51,
                rot_y_grados=p['rot_y'],
                rot_z_grados=p['rot_z']
            )

            # NUEVO: Instruimos al simulador a bloquear el voto hasta este frame exacto
            self.simulador.programar_caida_secuencial(voto, frame_caida=frame_actual)

            # Avanzamos el motor físico los 100 frames para procesar esta caída
            self.simulador.avanzar_simulacion(frames_a_avanzar=intervalo_espera)

            self.votos_en_urna.append(voto)

            # Preparamos el reloj para el siguiente votante
            frame_actual += intervalo_espera

        print("\n[ESCENARIO] Extrayendo datos de la estratigrafía final...")

        # Una vez que todos han caído, extraemos la posición
        datos_finales_todos = [self.simulador.obtener_estado_completo(v) for v in self.votos_en_urna]

        return datos_finales_todos