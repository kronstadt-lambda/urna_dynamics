"""
Motor Principal de Simulaciones Forenses (Entry Point)
------------------------------------------------------
Coordina el ciclo de vida completo: Llenado, Vaciado y Volcado.
Implementa reanudación automática (resume) basada en CSVs existentes.
"""

import sys
import json
import csv
import time
import random
from tqdm import tqdm
from pathlib import Path
from typing import Optional, Tuple

def inyectar_directorio_src() -> None:
    ruta_src = Path(__file__).resolve().parent.parent
    if str(ruta_src) not in sys.path:
        sys.path.append(str(ruta_src))

inyectar_directorio_src()

from utils.paths import ASSETS_DIR, RESULTS_VOTE_DIR, CONFIG_DIR, VAL_SETTINGS_FILE, COUNT_REAL_FILE
from utils.simuladores import SimuladorFisico
from utils.randomization import GeneradorAleatorioVotos
from utils.escenarios import EscenarioVotacion, EscenarioVaciado, EscenarioVolcado, EscenarioConteo

class GestorExperimentos:
    """
    Controlador de ejecuciones por lote y persistencia de datos.
    Lee archivos de configuración (JSON) y gestiona los directorios de salida.
    """
    def __init__(self, ruta_config: Path = VAL_SETTINGS_FILE, ruta_conteo_real: Path = COUNT_REAL_FILE):
        self.ruta_config = ruta_config
        self.settings = self._cargar_configuracion()

        self.ruta_conteo_real = ruta_conteo_real
        self.datos_conteo_real = self._cargar_conteo_real()

        self.nombre_exp = self.settings.get("nombre_experimento", "experimento_default")
        self.cantidad_sims = self.settings["cantidad_simulaciones"]
        self.guardar_blend = self.settings.get("guardar_blend_inspeccion", True)

        # Assets (.blend)
        self.ruta_urna = ASSETS_DIR / self.settings["archivo_urna_blend"]
        self.ruta_voto = ASSETS_DIR / self.settings["archivo_voto_blend"]
        self.ruta_bandeja = ASSETS_DIR / self.settings["archivo_bandeja_blend"]

        # Cargar todos los JSON en una sola lista unificada
        lista_archivos = self.settings.get("archivos_datos_json", ["urna1.json"])
        self.datos_votantes = self._cargar_multiples_json(lista_archivos)

        # Rutas de guardado
        self.directorio_salida_vote = RESULTS_VOTE_DIR / self.nombre_exp
        self.directorio_salida_vote.mkdir(parents=True, exist_ok=True)

        # Nombre genérico ya que manejamos múltiples urnas
        self.archivo_csv_extraccion = "extraccion_auditoria_multi_urna_completa.csv"
        self.archivo_csv_volcado = "volcado_auditoria_bandejas.csv"
        self.archivo_csv_conteo = "resultado_forense_final.csv"
        self.ruta_csv_final = self.directorio_salida_vote / self.archivo_csv_conteo

    def _cargar_conteo_real(self) -> dict:
        with open(self.ruta_conteo_real, "r", encoding="utf-8") as f:
            return json.load(f)

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
        """Verifica la última iteración procesada en el CSV FINAL para auto-reanudación."""
        ruta_csv_conteo = self.directorio_salida_vote / self.archivo_csv_conteo
        if not ruta_csv_conteo.exists():
            return 1
        try:
            with open(ruta_csv_conteo, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                sim_ids = [int(row['sim_id']) for row in reader if row.get('sim_id', '').isdigit()]
                if sim_ids:
                    return max(sim_ids) + 1
        except Exception as e:
            print(f"[!] Error leyendo CSV para reanudar. Detalles: {e}")
        return 1

    def ejecutar_lote(self) -> None:
        """Ejecuta el ciclo de vida secuencial del experimento solicitado."""
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

        posiciones_urnas = conf_esc.get("posiciones_urnas", {})
        puntos_busqueda = conf_esc.get("puntos_busqueda_vaciado", {})
        posiciones_bandejas = conf_esc.get("posiciones_bandejas", {})
        puntos_busqueda_conteo = conf_esc.get("puntos_busqueda_conteo", {})
        pos_conteo_final = tuple(conf_esc.get("posicion_final_conteo", [0, 0, 0.5]))
        inc_z = conf_esc.get("incremento_z_apilamiento", 0.1)
        criterio_busqueda = conf_esc.get("criterio_busqueda", "euclidiana")

        print(f"\n{'='*50}")
        print(f" EXPERIMENTO: {self.nombre_exp.upper()}")
        print(f" URNAS DETECTADAS: {list(posiciones_urnas.keys())}")
        print(f" RANGO: ID {sim_id_inicial} al {sim_id_final - 1}")
        print(f"{'='*50}\n")

        semillas_historicas = self._obtener_semillas_usadas()

        for sim_actual in range(sim_id_inicial, sim_id_final):
            tqdm.write(f"\n{'='*50}")
            tqdm.write(f"[*] INICIANDO SIMULACIÓN {sim_actual} DE {sim_id_final - 1}")

            # Lógica de protección y generación de semilla única
            while True:
                nueva_semilla = random.randint(1, 10000)
                if nueva_semilla not in semillas_historicas:
                    semillas_historicas.add(nueva_semilla)
                    break

            tqdm.write(f"[*] Semilla asignada: {nueva_semilla}")
            tqdm.write(f"{'='*50}")

            # Iniciamos el cronómetro de la simulación
            tiempo_inicio_sim = time.perf_counter()

            simulador = SimuladorFisico(
                sim_id=sim_actual,
                substeps=conf_sim.get("substeps_per_frame", 120),
                solver_iters=conf_sim.get("solver_iterations", 60),
                frame_start=conf_sim.get("frame_start", 1)
            )

            generador = GeneradorAleatorioVotos(semilla=nueva_semilla, config_tecnica=conf_rand)

            # --- FASE 1: Votacion ---
            escenario = EscenarioVotacion(
                simulador, generador, self.datos_votantes,
                intervalo_caida=conf_esc.get("intervalo_caida_frames", 100),
                friccion=friccion, rebote=rebote
            )

            # Inyectamos el diccionario de posiciones
            lista_estados_finales = escenario.ejecutar_llenado(self.ruta_urna, self.ruta_voto, posiciones_urnas)

            # --- FASE 2: Vaciado Secuencial ---
            escenario_vaciado = EscenarioVaciado(
                simulador=simulador,
                generador=generador,
                datos_votantes=self.datos_votantes,
                intervalo_vaciado=conf_esc.get("intervalo_vaciado_frames", 50),
                posiciones_bandejas=posiciones_bandejas,
                inc_z_apilamiento=conf_esc.get("incremento_z_apilamiento", 0.1)
            )

            # Inyectamos el diccionario de puntos de búsqueda para el vaciado
            lista_votos_extraidos = escenario_vaciado.ejecutar_vaciado(escenario.objetos_en_escena, puntos_busqueda)

            # --- FASE 3: Volcado a Bandejas (Conteo) ---
            escenario_volcado = EscenarioVolcado(
                simulador=simulador, generador=generador, datos_votantes=self.datos_votantes,
                intervalo_volcado=conf_esc.get("intervalo_volcado_frames", 100)
            )

            # Inyectamos el diccionario de posiciones para las bandejas
            lista_estado_bandejas = escenario_volcado.ejecutar_volcado(
                lista_votos_extraidos,
                self.ruta_bandeja,
                posiciones_bandejas
            )

            # --- FASE 4: Conteo Forense con Validación ---
            escenario_conteo = EscenarioConteo(
                simulador=simulador,
                generador=generador,
                datos_votantes=self.datos_votantes,
                datos_conteo_real=self.datos_conteo_real,
                intervalo_extraccion=conf_esc.get("intervalo_volcado_frames", 50),
                posicion_final_conteo=pos_conteo_final,
                inc_z_apilamiento=inc_z,
                tolerancia_busqueda=conf_esc.get("tolerancia_busqueda_comodines", 3)
            )

            # Ejecutar con criterio de superficie (z_max)
            lista_final_conteo = escenario_conteo.ejecutar_conteo(
                lista_votos_volcados=lista_estado_bandejas,
                criterio_busqueda=criterio_busqueda,
                puntos_busqueda=puntos_busqueda_conteo
            )

            simulador.guardar_resultado_csv(lista_final_conteo, self.directorio_salida_vote, self.archivo_csv_conteo)

            if self.guardar_blend:
                simulador.guardar_escena(self.directorio_salida_vote, f"sim_{sim_actual}_ESCENA_COMPLETA.blend")
                simulador.guardar_estado_final_como_inicio(self.directorio_salida_vote, f"sim_{sim_actual}_READY_TO_COUNT.blend")

            tiempo_fin_sim = time.perf_counter()
            tiempo_total = tiempo_fin_sim - tiempo_inicio_sim
            minutos, segundos = divmod(tiempo_total, 60)

            tqdm.write(f"\n[+] Simulación {sim_actual} finalizada exitosamente en {int(minutos)}m {segundos:.1f}s.")

        print("\n[LOTE COMPLETADO] Todas las simulaciones han finalizado correctamente.")

    def _calcular_rango_ejecucion(self) -> Optional[Tuple[int, int]]:
        sim_id_inicial = self._obtener_ultimo_sim_id()
        sim_id_final = self.cantidad_sims + 1
        if sim_id_inicial >= sim_id_final:
            return None
        return sim_id_inicial, sim_id_final

    def _obtener_semillas_usadas(self) -> set:
        """Lee el CSV principal para recuperar las semillas ya usadas y evitar duplicados forenses."""
        semillas_usadas = set()
        if self.ruta_csv_final.exists():
            try:
                with open(self.ruta_csv_final, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if 'sim_seed' in row and row['sim_seed'].isdigit():
                            semillas_usadas.add(int(row['sim_seed']))
            except Exception as e:
                print(f"[!] No se pudieron leer las semillas previas: {e}")
        return semillas_usadas

if __name__ == "__main__":
    gestor = GestorExperimentos()
    gestor.ejecutar_lote()