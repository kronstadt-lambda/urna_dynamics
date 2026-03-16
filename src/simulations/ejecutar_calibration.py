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

from utils.paths import ASSETS_DIR, RESULTS_VOTE_DIR, CONFIG_DIR, CAL_SETTINGS_FILE
from utils.simuladores import SimuladorFisico
from utils.randomization import GeneradorAleatorioVotos
from utils.escenarios import EscenarioVotacion, EscenarioVaciado

class GestorExperimentos:
    """
    Orquestador a nivel macro para ejecutar y aislar corridas de simulación.

    Lee los hiperparámetros, crea entornos de guardado aislados por experimento
    y gestiona la reanudación automática de simulaciones interrumpidas.
    """

    def __init__(self, ruta_config: Path = CAL_SETTINGS_FILE):
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

    def _generar_tareas_grid_search(self) -> tuple[list, list, list]:
        """
        Genera la matriz de tareas para el Grid Search basada en los límites
        y pasos definidos en el archivo de configuración.
        """
        pt = self.settings.get("parametros_tecnicos", {})
        gs = pt.get("grid_search", {})

        f_min = gs.get("friccion_min", 0.0)
        f_max = gs.get("friccion_max", 1.2)
        f_step = gs.get("friccion_step", 0.1)

        r_min = gs.get("rebote_min", 0.0)
        r_max = gs.get("rebote_max", 0.6)
        r_step = gs.get("rebote_step", 0.1)

        # Cálculo seguro de intervalos para evitar errores de coma flotante en Python
        f_pasos = int(round((f_max - f_min) / f_step)) + 1 if f_step > 0 else 1
        r_pasos = int(round((r_max - r_min) / r_step)) + 1 if r_step > 0 else 1

        fricciones = [round(f_min + (i * f_step), 2) for i in range(f_pasos)]
        rebotes = [round(r_min + (i * r_step), 2) for i in range(r_pasos)]

        tareas = []
        sim_id_global = 1
        for f in fricciones:
            for r in rebotes:
                for sim_local in range(1, self.cantidad_sims + 1):
                    tareas.append({
                        "sim_id_global": sim_id_global,
                        "friccion": f,
                        "rebote": r,
                        "sim_local": sim_local
                    })
                    sim_id_global += 1

        return tareas, fricciones, rebotes

    def ejecutar_lote(self) -> None:
        """Bucle principal que orquesta la ejecución del Grid Search."""
        # 1. Generar el espacio de búsqueda y las tareas dinámicamente
        tareas, fricciones, rebotes = self._generar_tareas_grid_search()

        # 3. Lógica de Reanudación Automática
        ultimo_id_guardado = self._obtener_ultimo_sim_id()
        tareas_pendientes = [t for t in tareas if t["sim_id_global"] >= ultimo_id_guardado]

        if not tareas_pendientes:
            print(f"\n[INFO] El Grid Search '{self.nombre_exp}' ha finalizado exitosamente todas las combinaciones.")
            return

        pt = self.settings.get("parametros_tecnicos", {})
        conf_rand = pt.get("randomization", {})
        conf_sim = pt.get("simulador", {})
        conf_esc = pt.get("escenario", {})

        print(f"\n{'='*50}")
        print(f" INICIANDO GRID SEARCH DE VALIDACIÓN")
        print(f" EXPERIMENTO: {self.nombre_exp.upper()}")
        print(f" COMBINACIONES: {len(fricciones)} (Fricción) x {len(rebotes)} (Rebote) = {len(fricciones)*len(rebotes)}")
        print(f" TOTAL SIMULACIONES: {len(tareas)} | PENDIENTES: {len(tareas_pendientes)}")
        print(f"{'='*50}\n")

        # 4. Ejecución del Lote
        for tarea in tareas_pendientes:
            sim_actual = tarea["sim_id_global"]
            friccion_actual = tarea["friccion"]
            rebote_actual = tarea["rebote"]
            iteracion_local = tarea["sim_local"]

            print(f"\n[*] Ejecutando Sim ID {sim_actual} -> Fricción: {friccion_actual} | Rebote: {rebote_actual} (Corrida {iteracion_local}/{self.cantidad_sims})")

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
                friccion=friccion_actual,  # Pasamos la fricción
                rebote=rebote_actual       # Pasamos el rebote
            )

            lista_estados_finales = escenario.ejecutar_llenado(self.ruta_urna, self.ruta_voto)

            # Ejecución del Vaciado
            escenario_vaciado = EscenarioVaciado(
                simulador=simulador,
                generador=generador,
                datos_votantes=self.datos_votantes,
                intervalo_vaciado=conf_esc.get("intervalo_vaciado_frames", 50),
                punto_busqueda=tuple(conf_esc.get("punto_radial_busqueda", [0.0, 0.0, 0.5])),
                coord_apilamiento=conf_esc.get("coord_apilamiento_base", [1.0, 1.0, 0.5]),
                inc_z_apilamiento=conf_esc.get("incremento_z_apilamiento", 0.1)
            )
            # Le pasamos los objetos que el escenario 1 acaba de crear
            lista_votos_extraidos = escenario_vaciado.ejecutar_vaciado(escenario.objetos_en_escena)

            # Persistencia de Datos (Llenado)
            simulador.guardar_resultado_csv(
                datos=lista_estados_finales,
                ruta_dir=self.directorio_salida_vote,
                archivo=self.archivo_csv
            )

            # Guardaremos un CSV exclusivo que indique en qué orden salieron los votos
            simulador.guardar_resultado_csv(
                datos=lista_votos_extraidos,
                ruta_dir=self.directorio_salida_vote,
                archivo=self.archivo_csv_extraccion
            )

            # 5. Guardado Visual al final de toda la coreografía
            if self.guardar_blend:
                nombre_blend = f"{self.nombre_urna_actual}_F{friccion_actual}_R{rebote_actual}_iter{iteracion_local}_READY.blend"
                simulador.guardar_estado_final_como_inicio(self.directorio_salida_vote, nombre_blend)

# ==========================================
# 3. PUNTO DE ENTRADA (ENTRY POINT)
# ==========================================
if __name__ == "__main__":
    gestor = GestorExperimentos()
    gestor.ejecutar_lote()