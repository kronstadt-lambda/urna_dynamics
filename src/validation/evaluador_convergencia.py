import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm

def inyectar_directorio_src() -> None:
    ruta_src = Path(__file__).resolve().parent.parent
    if str(ruta_src) not in sys.path:
        sys.path.append(str(ruta_src))

inyectar_directorio_src()

from utils.paths import FORENSIC_VAL_SETTINGS_FILE, RESULTS_VOTE_DIR, COUNT_REAL_FILE, CONFIG_DIR
from analytics.motor_estadistico import MotorMontecarloForense

class EvaluadorConvergencia:
    """
    Analiza la estabilidad asintótica del modelo físico evaluando
    cómo evolucionan los índices macro a medida que se acumulan las simulaciones.
    """
    def __init__(self, num_pasos=5):
        self.num_pasos = num_pasos

        with open(FORENSIC_VAL_SETTINGS_FILE, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.nombre_exp = self.config.get("nombre_experimento")
        self.dir_resultados = RESULTS_VOTE_DIR / self.nombre_exp
        self.ruta_simulaciones = self.dir_resultados / "resultado_forense_final.csv"

        params = self.config.get("parametros_analisis", {})
        self.total_votos = params.get("total_votos_urna", 113)
        self.ancho_estrato = params.get("ancho_estrato", 6)

        # Usamos el motor genérico
        self.motor = MotorMontecarloForense(
            total_votos=self.total_votos,
            ancho_estrato=self.ancho_estrato,
            max_iteraciones=params.get("max_iteraciones_montecarlo", 1000)
        )

    def _cargar_datos_base(self):
        # 1. Cargar votos reales
        with open(COUNT_REAL_FILE, "r", encoding="utf-8") as f:
            self.df_real = pd.DataFrame(json.load(f))

        # 2. Cargar padrón de votantes
        archivos_datos = self.config.get("archivos_datos_json", [])
        self.votantes_por_partido = {}
        for archivo in archivos_datos:
            ruta = CONFIG_DIR / archivo
            if ruta.exists():
                with open(ruta, "r", encoding="utf-8") as f:
                    for v in json.load(f):
                        partido = v['party_acronym']
                        if partido not in self.votantes_por_partido:
                            self.votantes_por_partido[partido] = []
                        self.votantes_por_partido[partido].append(v['name'])

        # 3. Cargar simulaciones y filtrar íntegras
        df_sim_raw = pd.read_csv(self.ruta_simulaciones)
        conteo_por_sim = df_sim_raw.groupby('sim_id').size()
        sims_validas = conteo_por_sim[conteo_por_sim == self.total_votos].index
        self.df_sim_integra = df_sim_raw[df_sim_raw['sim_id'].isin(sims_validas)].copy()

    def _calcular_indices_macro_memoria(self, df_sim_subset: pd.DataFrame) -> dict:
        """Versión ultrarrápida del cálculo macro para un lote de simulaciones."""
        objetivos = self.config.get("objetivos_validacion", [])

        indices_certeza = []
        indices_cohesion = []

        for obj in objetivos:
            partido = obj['partido_acronimo']
            opcion_ppal = obj['opcion_esperada']
            opcion_contraria = "OPCION 4" if opcion_ppal == "OPCION 2" else "OPCION 2"

            lista_nombres = self.votantes_por_partido.get(partido, [])
            total_miembros = len(lista_nombres)
            if total_miembros == 0: continue

            df_partido_sim = df_sim_subset[df_sim_subset['party_acronym'] == partido]
            df_real_ppal = self.df_real[self.df_real['voto_observado'] == opcion_ppal]
            df_real_espejo = self.df_real[self.df_real['voto_observado'] == opcion_contraria]

            limite_inferior = max(2, int(total_miembros * 0.33))

            puntos_certeza_partido = 0
            total_combinaciones_partido = 0
            mejores_estratos = [] # Para calcular cohesión

            for k in range(total_miembros, limite_inferior - 1, -1):
                num_excluidos = total_miembros - k
                combinaciones = self.motor.generar_combinaciones(lista_nombres, k)

                for combo in combinaciones:
                    total_combinaciones_partido += 1

                    # Test Principal
                    df_sim_ppal = df_partido_sim[df_partido_sim['name'].isin(combo)]
                    g_stat_ppal, p_val_ppal, _ = self.motor.calcular_test_g_ponderado(df_sim_ppal, df_real_ppal)

                    if p_val_ppal >= 0.05:
                        excluidos = list(set(lista_nombres) - set(combo))
                        # Test Espejo
                        espejo_doble = False
                        if len(excluidos) >= 2:
                            df_sim_exc = df_partido_sim[df_partido_sim['name'].isin(excluidos)]
                            _, p_val_exc, _ = self.motor.calcular_test_g_ponderado(df_sim_exc, df_real_espejo)
                            if p_val_exc >= 0.05:
                                espejo_doble = True

                        if espejo_doble or len(excluidos) < 2:
                            puntos_certeza_partido += 1.0
                            # CAMBIO: Guardamos la tupla con el g_stat_ppal
                            mejores_estratos.append((num_excluidos, 1, g_stat_ppal))
                        else:
                            puntos_certeza_partido += 0.5
                            # CAMBIO: Guardamos la tupla con el g_stat_ppal
                            mejores_estratos.append((num_excluidos, 0, g_stat_ppal))

            # Certeza del Partido
            certeza_idx = (puntos_certeza_partido / total_combinaciones_partido) * 100 if total_combinaciones_partido > 0 else 0
            indices_certeza.append(certeza_idx)

            # Cohesión del Partido (Ponderación por densidad + Desempate por G-Stat)
            if mejores_estratos:
                # CAMBIO: Añadimos la columna G_Stat
                df_estr = pd.DataFrame(mejores_estratos, columns=['Exc', 'Espejo', 'G_Stat'])

                # CAMBIO: Agregamos el promedio del G_Stat en la agrupación
                resumen = df_estr.groupby('Exc').agg(
                    Count=('Exc', 'count'),
                    Dobles=('Espejo', 'sum'),
                    G_Stat_Mean=('G_Stat', 'mean')
                ).reset_index()

                # CAMBIO: Ordenamos priorizando Dobles, luego Simples (Count), y desempatamos con el menor G_Stat
                resumen = resumen.sort_values(
                    by=['Dobles', 'Count', 'G_Stat_Mean'],
                    ascending=[False, False, True]
                )

                mejor_estrato = resumen.iloc[0]['Exc']
                cohesion_idx = ((total_miembros - mejor_estrato) / total_miembros) * 100
            else:
                cohesion_idx = 0.0
            indices_cohesion.append(cohesion_idx)

        return {
            "certeza_media": np.mean(indices_certeza) if indices_certeza else 0.0,
            "cohesion_media": np.mean(indices_cohesion) if indices_cohesion else 0.0
        }

    def ejecutar_analisis_convergencia(self):
        print(f"\n{'='*60}")
        print(f" INICIANDO ANÁLISIS DE CONVERGENCIA (ESTABILIDAD)")
        print(f" Experimento: {self.nombre_exp}")
        print(f"{'='*60}")

        self._cargar_datos_base()

        sim_ids_unicos = self.df_sim_integra['sim_id'].unique()
        total_sims = len(sim_ids_unicos)

        if total_sims == 0:
            print("[!] No hay simulaciones íntegras para evaluar.")
            return

        # Calcular los cortes (ej. 20%, 40%, 60%, 80%, 100%)
        fracciones = np.linspace(1.0 / self.num_pasos, 1.0, self.num_pasos)
        tamanos_lotes = [max(1, int(total_sims * frac)) for frac in fracciones]

        historial_pasos = []
        certeza_anterior = 0.0
        cohesion_anterior = 0.0

        for i, tamano in enumerate(tamanos_lotes):
            lote_sim_ids = sim_ids_unicos[:tamano]
            df_sim_lote = self.df_sim_integra[self.df_sim_integra['sim_id'].isin(lote_sim_ids)]

            print(f"[*] Procesando Paso {i+1}/{self.num_pasos} -> Usando {tamano} simulaciones...", end="\r")
            metricas = self._calcular_indices_macro_memoria(df_sim_lote)

            # Calcular Deltas Absolutos
            delta_certeza = abs(metricas['certeza_media'] - certeza_anterior) if i > 0 else 0.0
            delta_cohesion = abs(metricas['cohesion_media'] - cohesion_anterior) if i > 0 else 0.0

            historial_pasos.append({
                "Paso": i + 1,
                "Numero_Simulaciones": int(tamano),
                "Porcentaje_Dataset": f"{int(fracciones[i]*100)}%",
                "Indice_Certeza_Global": round(metricas['certeza_media'], 2),
                "Delta_Certeza": round(delta_certeza, 2),
                "Indice_Cohesion_Global": round(metricas['cohesion_media'], 2),
                "Delta_Cohesion": round(delta_cohesion, 2)
            })

            certeza_anterior = metricas['certeza_media']
            cohesion_anterior = metricas['cohesion_media']

        print(f"[*] Procesando Paso {self.num_pasos}/{self.num_pasos} -> Completado.                     ")

        # Evaluar Estabilidad Final basada en los últimos dos pasos
        ultimos_deltas = [historial_pasos[-1]['Delta_Certeza'], historial_pasos[-1]['Delta_Cohesion']]
        max_delta_final = max(ultimos_deltas)

        # Umbral estricto: Si la variación en el último tramo es menor a 1.5%, hay convergencia.
        umbral_convergencia = 1.5

        if max_delta_final <= umbral_convergencia:
            veredicto = "ESTABLE. El modelo ha convergido. No se requieren más simulaciones."
        else:
            veredicto = f"INESTABLE. Variación final de {max_delta_final}% supera el umbral de {umbral_convergencia}%. Se recomiendan más simulaciones."

        reporte_convergencia = {
            "Experimento": self.nombre_exp,
            "Resumen_Convergencia": {
                "Total_Simulaciones_Disponibles": int(total_sims),
                "Variacion_Final_Maxima_Pct": max_delta_final,
                "Veredicto": veredicto
            },
            "Historial_Evolucion": historial_pasos
        }

        ruta_salida = self.dir_resultados / f"convergencia_modelo_estrato_{self.ancho_estrato}.json"
        with open(ruta_salida, "w", encoding="utf-8") as f:
            json.dump(reporte_convergencia, f, indent=4, ensure_ascii=False)

        print(f"\n{'-'*60}")
        print(f" RESULTADO DE ESTABILIDAD")
        print(f"{'-'*60}")
        print(f" -> {veredicto}")
        print(f" -> Variación de Certeza en el último tramo : {historial_pasos[-1]['Delta_Certeza']}%")
        print(f" -> Variación de Cohesión en el último tramo: {historial_pasos[-1]['Delta_Cohesion']}%")
        print(f"[+] Reporte exportado a:\n    {ruta_salida}\n")

if __name__ == "__main__":
    # Puedes cambiar el num_pasos si quieres más granularidad (ej. 10 pasos)
    evaluador = EvaluadorConvergencia(num_pasos=5)
    evaluador.ejecutar_analisis_convergencia()