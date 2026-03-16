import sys
import json
import csv
from pathlib import Path
from typing import Optional, Tuple

# Inyección dinámica del directorio 'src' para asegurar la importación de 'utils'
def inyectar_directorio_src() -> None:
    """Resuelve la ruta del directorio 'src' y la añade al sys.path.
    Permite importar el paquete 'utils' sin importar desde dónde se ejecute el script.
    """
    ruta_src = Path(__file__).resolve().parent.parent
    if str(ruta_src) not in sys.path:
        sys.path.append(str(ruta_src))

# Ejecutamos la función de inyección al inicio del script
inyectar_directorio_src()

from utils.paths import ASSETS_DIR, RESULTS_VOTE_DIR, CONFIG_DIR, SIM_SETTINGS_FILE
from utils.simuladores import SimuladorFisico
from utils.randomization import GeneradorAleatorioVotos
from utils.escenarios import EscenarioVotacion, EscenarioVaciado

class GestorExperimentos:
    """
    Orquestador a nivel macro para ejecutar y aislar corridas de simulación.

    Lee los hiperparámetros, crea entornos de guardado aislados por experimento
    y gestiona la reanudación automática de simulaciones interrumpidas.
    """

    def __init__(self, ruta_config: Path = SIM_SETTINGS_FILE):
        """
        Inicializa el gestor de experimentos con la configuración especificada.
        """
        self.ruta_config = ruta_config
        self.settings = self._cargar_configuracion()

        # Parámetros del experimento actual
        self.nombre_exp = self.settings.get("nombre_experimento", "experimento_default")
        self.cantidad_sims = self.settings["cantidad_simulaciones"]
        self.guardar_blend = self.settings.get("guardar_blend_inspeccion", True)

        # Rutas de activos
        self.ruta_urna = ASSETS_DIR / self.settings["archivo_urna_blend"]
        self.ruta_voto = ASSETS_DIR / self.settings["archivo_voto_blend"]

        # Carga de la "Verdad de Campo" (Ground Truth)
        self.datos_votantes = self._cargar_datos_json(self.settings["archivo_datos_json"])
        self.nombre_urna_actual = self.datos_votantes[0].get("urn", "urna_desconocida")

        # Configuración de subcarpetas dinámicas por experimento
        self.directorio_salida_vote = RESULTS_VOTE_DIR / self.nombre_exp
        self.directorio_salida_vote.mkdir(parents=True, exist_ok=True)

        self.archivo_csv = f"auditoria_{self.nombre_urna_actual}_completa.csv"
        self.ruta_csv_completa = self.directorio_salida_vote / self.archivo_csv

        self.archivo_csv_extraccion = f"extraccion_auditoria_{self.nombre_urna_actual}_completa.csv"

    def _cargar_configuracion(self) -> dict:
        """
        Carga el archivo JSON de hiperparámetros.
        """
        with open(self.ruta_config, "r", encoding="utf-8") as f:
            return json.load(f)

    def _cargar_datos_json(self, nombre_archivo: str) -> list:
        """
        Carga la lista de votantes desde la carpeta de configuración.
        """
        ruta_json = CONFIG_DIR / nombre_archivo
        with open(ruta_json, "r", encoding="utf-8") as f:
            return json.load(f)

    def _obtener_ultimo_sim_id(self) -> int:
        """
        Analiza el CSV actual del experimento para reanudar donde se quedó.
        """
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
        """
        Bucle principal que orquesta la ejecución masiva de escenarios hasta alcanzar la meta.
        """
        rango_pendientes = self._calcular_rango_ejecucion()

        # Si el helper devuelve None, la cuota está llena y salimos limpiamente
        if not rango_pendientes:
            return

        sim_id_inicial, sim_id_final = rango_pendientes

        # Extraer parámetros técnicos del JSON (puedes poner esto en el __init__ si prefieres)
        pt = self.settings.get("parametros_tecnicos", {})
        conf_rand = pt.get("randomization", {})
        conf_sim = pt.get("simulador", {})
        conf_esc = pt.get("escenario", {})
        conf_phy = pt.get("physics", {})

        friccion = conf_phy.get("friccion", 0.8)
        rebote = conf_phy.get("rebote", 0.6)

        print(f"\n{'='*50}")
        print(f" EXPERIMENTO: {self.nombre_exp.upper()}")
        print(f" URNA: {self.nombre_urna_actual}")
        print(f" RANGO: ID {sim_id_inicial} al {sim_id_final - 1}")
        print(f" SALIDA: {self.directorio_salida_vote}")
        print(f"{'='*50}\n")

        for sim_actual in range(sim_id_inicial, sim_id_final):
            print(f"[*] Iniciando Simulación {sim_actual}...")

            # Inicialización de componentes principales
            simulador = SimuladorFisico(
                sim_id=sim_actual,
                substeps=conf_sim.get("substeps_per_frame", 120),
                solver_iters=conf_sim.get("solver_iterations", 60),
                frame_start=conf_sim.get("frame_start", 1)
            )

            generador = GeneradorAleatorioVotos(
                semilla=sim_actual,
                config_tecnica=conf_rand
            )

            escenario = EscenarioVotacion(
                simulador, generador, self.datos_votantes,
                intervalo_caida=conf_esc.get("intervalo_caida_frames", 100),
                friccion = friccion,
                rebote = rebote
            )

            # Ejecución de la coreografía
            lista_estados_finales = escenario.ejecutar_llenado(self.ruta_urna, self.ruta_voto)

            # Persistencia de Datos
            simulador.guardar_resultado_csv(
                datos=lista_estados_finales,
                ruta_dir=self.directorio_salida_vote,
                archivo=self.archivo_csv
            )

            escenario_vaciado = EscenarioVaciado(
                simulador=simulador,
                generador=generador,
                datos_votantes=self.datos_votantes,
                intervalo_vaciado=conf_esc.get("intervalo_vaciado_frames", 50),
                punto_busqueda=tuple(conf_esc.get("punto_radial_busqueda", [0.0, 0.0, 0.5])),
                coord_apilamiento=conf_esc.get("coord_apilamiento_base", [1.0, 1.0, 0.5]),
                inc_z_apilamiento=conf_esc.get("incremento_z_apilamiento", 0.1)
            )

            # Ejecutamos pasando los objetos físicos que quedaron del llenado
            lista_votos_extraidos = escenario_vaciado.ejecutar_vaciado(escenario.objetos_en_escena)

            # Persistencia de Datos (Extracción)
            simulador.guardar_resultado_csv(
                datos=lista_votos_extraidos,
                ruta_dir=self.directorio_salida_vote,
                archivo=self.archivo_csv_extraccion
            )

            # Guardado para la siguiente fase (Vaciado e Inspección)
            if self.guardar_blend:
                # 1) guardar la escena con toda su dinámica y física intacta
                nombre_escena_final = f"{self.nombre_urna_actual}_sim_{sim_actual}_ESCENA_FINAL.blend"
                simulador.guardar_escena(self.directorio_salida_vote, nombre_escena_final)

                # 2) congelar la memoria y guardar el estado base para la fase de descarga
                nombre_blend = f"{self.nombre_urna_actual}_sim_{sim_actual}_READY_TO_UNLOAD.blend"
                simulador.guardar_estado_final_como_inicio(self.directorio_salida_vote, nombre_blend)

        print("\n[LOTE COMPLETADO] Todas las simulaciones han finalizado correctamente.")

    def _calcular_rango_ejecucion(self) -> Optional[Tuple[int, int]]:
        """
        Calcula el rango de simulaciones pendientes y verifica si la meta se cumplió.

        Returns:
            Una tupla (sim_id_inicial, sim_id_final) si hay trabajo por hacer.
            None si el experimento ya alcanzó su cuota total.
        """
        sim_id_inicial = self._obtener_ultimo_sim_id()
        sim_id_final = self.cantidad_sims + 1  # +1 porque la función range() es exclusiva

        if sim_id_inicial >= sim_id_final:
            print(f"\n[INFO] El experimento '{self.nombre_exp}' ya alcanzó la meta de {self.cantidad_sims} simulaciones.")
            print(f"Archivo de resultados: {self.ruta_csv_completa}")
            return None

        return sim_id_inicial, sim_id_final

# ==========================================
# 3. PUNTO DE ENTRADA (ENTRY POINT)
# ==========================================
if __name__ == "__main__":
    gestor = GestorExperimentos()
    gestor.ejecutar_lote()