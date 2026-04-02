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

from utils.paths import FORENSIC_SETTINGS_FILE, RESULTS_VOTE_DIR, COUNT_REAL_FILE, CONFIG_DIR
from validation.motor_forense import MotorMontecarloForense

class OrquestadorForense:
    def __init__(self):
        with open(FORENSIC_SETTINGS_FILE, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.nombre_exp = self.config.get("nombre_experimento")
        self.dir_resultados = RESULTS_VOTE_DIR / self.nombre_exp
        self.ruta_simulaciones = self.dir_resultados / "resultado_forense_final.csv"

        params = self.config.get("parametros_analisis", {})
        self.total_votos = params.get("total_votos_urna", 113)
        self.ancho_estrato = params.get("ancho_estrato", 6)

        self.motor = MotorMontecarloForense(
            total_votos=self.total_votos,
            ancho_estrato=self.ancho_estrato,
            max_iteraciones=params.get("max_iteraciones_montecarlo", 500)
        )

    def _filtrar_simulaciones_integras(self, df_sims: pd.DataFrame) -> pd.DataFrame:
        conteo_por_sim = df_sims.groupby('sim_id').size()
        sims_validas = conteo_por_sim[conteo_por_sim == self.total_votos].index
        return df_sims[df_sims['sim_id'].isin(sims_validas)].copy()

    def _cargar_listas_votantes(self) -> dict:
        archivos_datos = self.config.get("archivos_datos_json", [])
        mapa_partidos = {}
        for archivo in archivos_datos:
            ruta = CONFIG_DIR / archivo
            if ruta.exists():
                with open(ruta, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                    for v in datos:
                        partido = v['party_acronym']
                        acronimo = v['name_acronym']
                        if partido not in mapa_partidos:
                            mapa_partidos[partido] = []
                        mapa_partidos[partido].append(acronimo)
        return mapa_partidos

    def _corregir_etiquetas_partidos(self, df_sims: pd.DataFrame) -> pd.DataFrame:
        """
        Homogeneiza y corrige las siglas de los partidos (party_acronym) cruzando
        los nombres de los votantes con la fuente de verdad absoluta (votos_base.csv).
        """
        from utils.paths import VOTOS_REAL_FILE

        if not VOTOS_REAL_FILE.exists():
            print(f"[!] ADVERTENCIA: No se encontró {VOTOS_REAL_FILE}. Se usarán las etiquetas originales.")
            return df_sims.copy()

        df_base = pd.read_csv(VOTOS_REAL_FILE)

        # 1. Descartar la columna contaminada de las simulaciones
        df_sims_limpio = df_sims.drop(columns=['party_acronym'], errors='ignore')

        # 2. Inyectar la etiqueta correcta haciendo match exacto por 'name'
        df_corregido = pd.merge(
            df_sims_limpio,
            df_base[['name', 'party_acronym']],
            on='name',
            how='left'
        )

        # 3. Eliminar posibles filas huérfanas o con errores de merge y retornar
        df_final = df_corregido.dropna(subset=['party_acronym']).copy()

        print(f"[*] Limpieza de partidos completada: {len(df_sims) - len(df_final)} registros anómalos removidos.")
        return df_final

    def _generar_metricas_macro(self, df: pd.DataFrame, top_k: int = 10):
        """
        Calcula el Model Quality Index (MQI) y otras métricas macro a partir del DataFrame de resultados.
        """
        if df.empty:
            return

        partidos = df['Partido'].unique()
        reporte_partidos = {}
        g_stats_globales_top = []
        hit_rates_partidos = []

        for partido in partidos:
            df_p = df[df['Partido'] == partido]
            total_combinaciones = len(df_p)

            # 1. Tasa de Plausibilidad (Hit Rate)
            validas = len(df_p[df_p['Validado'] == 'SI'])
            hit_rate = (validas / total_combinaciones) * 100 if total_combinaciones > 0 else 0
            hit_rates_partidos.append(hit_rate)

            # 2. G-Stat Estabilizado (Promedio de los Top K mejores)
            mejores_g = df_p.sort_values(by='G_Stat', ascending=True).head(top_k)['G_Stat'].values
            g_stat_promedio_top = float(np.mean(mejores_g)) if len(mejores_g) > 0 else float('inf')
            g_stats_globales_top.extend(mejores_g)

            reporte_partidos[partido] = {
                "Total_Combinaciones": int(total_combinaciones),
                "Combinaciones_Validas": int(validas),
                "Hit_Rate_Pct": round(hit_rate, 2),
                f"G_Stat_Promedio_Top_{top_k}": round(g_stat_promedio_top, 4)
            }

        # 3. Métricas Globales y Penalización por Asimetría
        hit_rate_global = float(np.mean(hit_rates_partidos)) if hit_rates_partidos else 0.0
        varianza_hit_rate = float(np.var(hit_rates_partidos)) if hit_rates_partidos else 0.0
        g_stat_macro_estabilizado = float(np.mean(g_stats_globales_top)) if g_stats_globales_top else float('inf')

        penalizacion_asimetria = float(np.sqrt(varianza_hit_rate) / 100)

        if g_stat_macro_estabilizado > 0 and g_stat_macro_estabilizado != float('inf'):
            mqi = hit_rate_global / (g_stat_macro_estabilizado * (1 + penalizacion_asimetria))
        else:
            mqi = 0.0

        reporte_global = {
            "Experimento": self.nombre_exp,
            "Hit_Rate_Global_Pct": round(hit_rate_global, 2),
            "Desbalance_Partidario": round(penalizacion_asimetria, 4),
            "G_Stat_Macro_Estabilizado": round(g_stat_macro_estabilizado, 4),
            "Model_Quality_Index_(MQI)": round(mqi, 4),
            "Detalle_Partidos": reporte_partidos
        }

        # Guardar JSON
        ruta_salida = self.dir_resultados / "metricas_macro_modelo.json"
        with open(ruta_salida, "w", encoding="utf-8") as f:
            json.dump(reporte_global, f, indent=4)

        # Imprimir Reporte en Consola
        print(f"\n{'='*60}")
        print(f" REPORTE MACRO DE CALIDAD FÍSICA - {self.nombre_exp}")
        print(f"{'='*60}")
        print(f" [GLOBAL] Tasa de Plausibilidad Media : {reporte_global['Hit_Rate_Global_Pct']}%")
        print(f" [GLOBAL] G-Stat Estabilizado (Top {top_k})  : {reporte_global['G_Stat_Macro_Estabilizado']}")
        print(f" [GLOBAL] Factor de Desbalance        : {reporte_global['Desbalance_Partidario']}")
        print(f" -> ÍNDICE DE CALIDAD (MQI)         : {reporte_global['Model_Quality_Index_(MQI)']}")
        print(f"{'-'*60}")
        print(f"[+] Reporte macro exportado a:\n    {ruta_salida}")


    def ejecutar_analisis(self):
        print(f"\n{'='*50}")
        print(f" INICIANDO ANÁLISIS FORENSE DE SENSIBILIDAD")
        print(f" Experimento: {self.nombre_exp}")
        print(f"{'='*50}")

        if not self.ruta_simulaciones.exists():
            print(f"[!] Error: Dataset de simulación no encontrado en {self.ruta_simulaciones}")
            return

        df_sim_raw = pd.read_csv(self.ruta_simulaciones)
        # Filtro de integridad fisica
        df_sim_integras = self._filtrar_simulaciones_integras(df_sim_raw)

        # Corrección forense de etiquetas de partido
        df_sim = self._corregir_etiquetas_partidos(df_sim_integras)

        with open(COUNT_REAL_FILE, "r", encoding="utf-8") as f:
            df_real = pd.DataFrame(json.load(f))

        votantes_por_partido = self._cargar_listas_votantes()
        resultados_totales = []

        objetivos = self.config.get("objetivos_validacion", [])
        porcentajes = self.config.get("porcentajes_sensibilidad", [1.0])

        for obj in objetivos:
            partido = obj['partido_acronimo']
            opcion = obj['opcion_esperada']

            lista_nombres_partido = votantes_por_partido.get(partido, [])
            if not lista_nombres_partido:
                continue

            df_partido_sim = df_sim[df_sim['party_acronym'] == partido]
            df_real_opcion = df_real[df_real['voto_observado'] == opcion]

            print(f"\n[*] Evaluando: {partido} -> {opcion}")

            for pct in porcentajes:
                combinaciones = self.motor.generar_combinaciones(lista_nombres_partido, pct)
                k_seleccionados = max(1, round(len(lista_nombres_partido) * pct))

                for combo in tqdm(combinaciones, desc=f"      {int(pct*100)}% ({k_seleccionados} votantes)", leave=False):
                    df_sim_subset = df_partido_sim[df_partido_sim['name_acronym'].isin(combo)]

                    g_stat, p_val, df_efectivo = self.motor.calcular_test_g_ponderado(df_sim_subset, df_real_opcion)

                    excluidos = set(lista_nombres_partido) - set(combo)
                    str_excluidos = ", ".join(sorted(list(excluidos))) if excluidos else "NINGUNO"

                    resultados_totales.append({
                        "Partido": partido,
                        "Opcion_Observada": opcion,
                        "Porcentaje_Analisis": f"{int(pct*100)}%",
                        "N_Votantes_Incluidos": k_seleccionados,
                        "G_Stat": round(g_stat, 4),
                        "Grados_Libertad_Eff": round(df_efectivo, 2),
                        "Validado": "SI" if p_val >= 0.05 else "NO",
                        "Excluidos": str_excluidos
                    })

        if resultados_totales:
            df_resultados = pd.DataFrame(resultados_totales)

            # NUEVA LÓGICA DE ORDENAMIENTO:
            # 1. Por Partido (asc)
            # 2. Por Validado (desc: 'SI' aparece antes que 'NO')
            # 3. Por G_Stat (asc: menor error primero)
            df_resultados = df_resultados.sort_values(
                by=['Partido', 'Validado', 'G_Stat'],
                ascending=[True, False, True]
            )

            # INSERTAR IDENTIFICADOR ÚNICO DE FILA AL INICIO
            df_resultados.insert(0, 'ID_Analisis', range(1, len(df_resultados) + 1))

            archivo_salida = self.dir_resultados / "analisis_sensibilidad_forense.csv"
            df_resultados.to_csv(archivo_salida, index=False, encoding='utf-8')
            print(f"\n[+] Análisis completado. Resultados exportados a:\n    {archivo_salida}")

            # --- NUEVO: Ejecutar el cálculo de métricas macro automáticamente ---
            self._generar_metricas_macro(df_resultados)

if __name__ == "__main__":
    orquestador = OrquestadorForense()
    orquestador.ejecutar_analisis()