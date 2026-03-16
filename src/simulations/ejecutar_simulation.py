import sys
import json
import csv
from pathlib import Path
from typing import Optional, Tuple

def inyectar_directorio_src() -> None:
    ruta_src = Path(__file__).resolve().parent.parent
    if str(ruta_src) not in sys.path:
        sys.path.append(str(ruta_src))

inyectar_directorio_src()

from utils.paths import ASSETS_DIR, RESULTS_VOTE_DIR, CONFIG_DIR, SIM_SETTINGS_FILE
from utils.simuladores import SimuladorFisico
from utils.randomization import GeneradorAleatorioVotos
from utils.escenarios import EscenarioVotacion, EscenarioVaciado

class GestorExperimentos:
    def __init__(self, ruta_config: Path = SIM_SETTINGS_FILE):
        self.ruta_config = ruta_config
        self.settings = self._cargar_configuracion()

        self.nombre_exp = self.settings.get("nombre_experimento", "experimento_default")
        self.cantidad_sims = self.settings["cantidad_simulaciones"]
        self.guardar_blend = self.settings.get("guardar_blend_inspeccion", True)

        self.ruta_urna = ASSETS_DIR / self.settings["archivo_urna_blend"]
        self.ruta_voto = ASSETS_DIR / self.settings["archivo_voto_blend"]

        # Cargar todos los JSON en una sola lista unificada
        lista_archivos = self.settings.get("archivos_datos_json", ["urna1.json"])
        self.datos_votantes = self._cargar_multiples_json(lista_archivos)

        self.directorio_salida_vote = RESULTS_VOTE_DIR / self.nombre_exp
        self.directorio_salida_vote.mkdir(parents=True, exist_ok=True)

        # Nombre genérico ya que manejamos múltiples urnas
        self.archivo_csv = "auditoria_multi_urna_completa.csv"
        self.ruta_csv_completa = self.directorio_salida_vote / self.archivo_csv
        self.archivo_csv_extraccion = "extraccion_auditoria_multi_urna_completa.csv"

    def _cargar_configuracion(self) -> dict:
        with open(self.ruta_config, "r", encoding="utf-8") as f:
            return json.load(f)

    def _cargar_multiples_json(self, nombres_archivos: list) -> list:
        datos_completos = []
        for nombre in nombres_archivos:
            ruta_json = CONFIG_DIR / nombre
            with open(ruta_json, "r", encoding="utf-8") as f:
                datos_completos.extend(json.load(f))
        return datos_completos

    def _obtener_ultimo_sim_id(self) -> int:
        if not self.ruta_csv_completa.exists():
            return 1
        try:
            with open(self.ruta_csv_completa, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                sim_ids = [int(row['sim_id']) for row in reader if row.get('sim_id', '').isdigit()]
                if sim_ids:
                    return max(sim_ids) + 1
        except Exception as e:
            print(f"[!] Error leyendo CSV para reanudar. Detalles: {e}")
        return 1

    def ejecutar_lote(self) -> None:
        rango_pendientes = self._calcular_rango_ejecucion()
        if not rango_pendientes:
            return

        sim_id_inicial, sim_id_final = rango_pendientes

        pt = self.settings.get("parametros_tecnicos", {})
        conf_rand = pt.get("randomization", {})
        conf_sim = pt.get("simulador", {})
        conf_esc = pt.get("escenario", {})
        conf_phy = pt.get("physics", {})

        friccion = conf_phy.get("friccion", 0.8)
        rebote = conf_phy.get("rebote", 0.6)

        posiciones_urnas = conf_esc.get("posiciones_urnas", {"urn1": [0.0, 0.0, 0.0]})
        puntos_busqueda = conf_esc.get("puntos_busqueda_vaciado", {"urn1": [0.0, 0.0, 0.5]})

        print(f"\n{'='*50}")
        print(f" EXPERIMENTO: {self.nombre_exp.upper()}")
        print(f" URNAS DETECTADAS: {list(posiciones_urnas.keys())}")
        print(f" RANGO: ID {sim_id_inicial} al {sim_id_final - 1}")
        print(f"{'='*50}\n")

        for sim_actual in range(sim_id_inicial, sim_id_final):
            print(f"[*] Iniciando Simulación {sim_actual}...")

            simulador = SimuladorFisico(
                sim_id=sim_actual,
                substeps=conf_sim.get("substeps_per_frame", 120),
                solver_iters=conf_sim.get("solver_iterations", 60),
                frame_start=conf_sim.get("frame_start", 1)
            )

            generador = GeneradorAleatorioVotos(semilla=sim_actual, config_tecnica=conf_rand)

            escenario = EscenarioVotacion(
                simulador, generador, self.datos_votantes,
                intervalo_caida=conf_esc.get("intervalo_caida_frames", 100),
                friccion=friccion, rebote=rebote
            )

            # Inyectamos el diccionario de posiciones
            lista_estados_finales = escenario.ejecutar_llenado(self.ruta_urna, self.ruta_voto, posiciones_urnas)

            simulador.guardar_resultado_csv(lista_estados_finales, self.directorio_salida_vote, self.archivo_csv)

            escenario_vaciado = EscenarioVaciado(
                simulador=simulador,
                generador=generador,
                datos_votantes=self.datos_votantes,
                intervalo_vaciado=conf_esc.get("intervalo_vaciado_frames", 50),
                coord_apilamiento=conf_esc.get("coord_apilamiento_base", [1.0, 1.0, 0.5]),
                inc_z_apilamiento=conf_esc.get("incremento_z_apilamiento", 0.1)
            )

            # Inyectamos el diccionario de puntos de búsqueda para el vaciado
            lista_votos_extraidos = escenario_vaciado.ejecutar_vaciado(escenario.objetos_en_escena, puntos_busqueda)

            simulador.guardar_resultado_csv(lista_votos_extraidos, self.directorio_salida_vote, self.archivo_csv_extraccion)

            if self.guardar_blend:
                nombre_escena_final = f"multi_urna_sim_{sim_actual}_ESCENA_FINAL.blend"
                simulador.guardar_escena(self.directorio_salida_vote, nombre_escena_final)
                nombre_blend = f"multi_urna_sim_{sim_actual}_READY_TO_UNLOAD.blend"
                simulador.guardar_estado_final_como_inicio(self.directorio_salida_vote, nombre_blend)

        print("\n[LOTE COMPLETADO] Todas las simulaciones han finalizado correctamente.")

    def _calcular_rango_ejecucion(self) -> Optional[Tuple[int, int]]:
        sim_id_inicial = self._obtener_ultimo_sim_id()
        sim_id_final = self.cantidad_sims + 1
        if sim_id_inicial >= sim_id_final:
            return None
        return sim_id_inicial, sim_id_final

if __name__ == "__main__":
    gestor = GestorExperimentos()
    gestor.ejecutar_lote()