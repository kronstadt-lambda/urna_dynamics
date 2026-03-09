from utils.simuladores import SimuladorFisico
from utils.randomization import GeneradorAleatorioVotos

class EscenarioVotacion:
    """
    Manager que orquesta la simulación del 'Primer Escenario' (Llenado de urna).
    Controla el flujo físico secuencial de n votos.
    """

    def __init__(self, simulador: SimuladorFisico, generador: GeneradorAleatorioVotos, datos_votantes: list):
        self.simulador = simulador
        self.generador = generador
        self.datos_votantes = datos_votantes
        self.votos_en_urna = []

    def ejecutar_llenado(self, ruta_urna: str, ruta_voto: str) -> list:
        self.simulador.importar_objeto(ruta_urna, "urna_cylinder", "urna_1")
        print("[ESCENARIO] Urna inicializada.")

        frame_actual = 1
        intervalo_espera = 100

        for voto_info in self.datos_votantes:
            orden = voto_info['order']
            nombre_voto = f"voto_{orden}"
            print(f"\n[ESCENARIO] Votante {orden} ({voto_info['name_acronym']}) en Frame {frame_actual}...")

            # Selección estocástica del patrón
            patron_elegido = self.generador.elegir_patron(voto_info['fold_pattern'])

            # Guardamos la selección en el diccionario para pasarlo al CSV después
            voto_info['fold_pattern_used'] = patron_elegido
            voto_info['sim_seed'] = self.generador.semilla_usada

            # Importar y posicionar
            voto = self.simulador.importar_objeto(ruta_voto, patron_elegido, nombre_voto)
            p = self.generador.obtener_parametros_caida(orden)

            self.simulador.posicionar_objeto(
                objeto=voto,
                loc_x=p['x'],
                loc_y=p['y'],
                loc_z=p['z'],
                rot_y_grados=p['rot_y'],
                rot_z_grados=p['rot_z']
            )

            self.simulador.programar_caida_secuencial(voto, frame_caida=frame_actual)
            self.simulador.avanzar_simulacion(frames_a_avanzar=intervalo_espera)

            # Guardamos la tupla (objeto_blender, metadata_json)
            self.votos_en_urna.append((voto, voto_info))
            frame_actual += intervalo_espera

        print("\n[ESCENARIO] Extrayendo datos de la estratigrafía final...")

        # Extraemos el estado pasando la metadata asociada a cada objeto
        datos_finales_todos = [
            self.simulador.obtener_estado_completo(obj, info)
            for obj, info in self.votos_en_urna
        ]

        return datos_finales_todos