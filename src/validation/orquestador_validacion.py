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

class OrquestadorForense:
    def __init__(self):
        with open(FORENSIC_VAL_SETTINGS_FILE, "r", encoding="utf-8") as f:
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
            max_iteraciones=params.get("max_iteraciones_montecarlo", 1000)
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
                        nombre = v['name']
                        if partido not in mapa_partidos:
                            mapa_partidos[partido] = []
                        mapa_partidos[partido].append(nombre)
        return mapa_partidos

    def _generar_metricas_macro(self, df: pd.DataFrame, votantes_por_partido: dict):
        if df.empty: return

        partidos = df['Partido'].unique()
        reporte_partidos = {}
        indices_cohesion_global = []
        indices_certeza_global = []

        for partido in partidos:
            df_p = df[df['Partido'] == partido]
            lista_nombres_partido = votantes_por_partido.get(partido, [])

            total_miembros = len(lista_nombres_partido)
            total_combinaciones = len(df_p)

            # --- 1. CERTEZA FÍSICA DEL MODELO ---
            aciertos_perfectos = len(df_p[df_p['Validado_Espejo'].isin(['SI (Doble)', 'SI (Sin Espejo)'])])
            aciertos_parciales = len(df_p[df_p['Validado_Espejo'] == 'SI (Parcial)'])
            fallos_absolutos = len(df_p[df_p['Validado_Principal'] == 'NO'])

            puntos_certeza = (aciertos_perfectos * 1.0) + (aciertos_parciales * 0.5)
            certeza_idx = (puntos_certeza / total_combinaciones) * 100 if total_combinaciones > 0 else 0.0
            indices_certeza_global.append(certeza_idx)

            # --- 2. COHESIÓN Y FIDELIDAD INDIVIDUAL PONDERADA ---
            validas_df = df_p[df_p['Validado_Principal'] == 'SI'].copy()
            fidelidad_votantes = {}

            if validas_df.empty:
                cohesion_idx = 0.0
                mejor_estrato_exc = total_miembros
                soporte_doble = 0
                g_stat_promedio = 0.0
                for nombre in lista_nombres_partido:
                    fidelidad_votantes[nombre] = {"Fidelidad_Pct": 50.0, "Rol_Inferido": "Indeterminado / Sin Datos"}
            else:
                # --- A. Cálculo de Cohesión (Agrupación por Densidad) ---
                resumen_estratos = validas_df.groupby('Cantidad_Excluidos').agg(
                    Num_Validas_Simples=('Validado_Principal', 'count'),
                    Num_Validas_Dobles=('Validado_Espejo', lambda x: (x == 'SI (Doble)').sum()),
                    G_Stat_Mean=('G_Stat_Principal', 'mean')
                ).reset_index()

                resumen_estratos = resumen_estratos.sort_values(
                    by=['Num_Validas_Dobles', 'Num_Validas_Simples', 'G_Stat_Mean'],
                    ascending=[False, False, True]
                )

                mejor_estrato_exc = int(resumen_estratos.iloc[0]['Cantidad_Excluidos'])
                soporte_doble = int(resumen_estratos.iloc[0]['Num_Validas_Dobles'])
                soporte_simple = int(resumen_estratos.iloc[0]['Num_Validas_Simples'])
                g_stat_promedio = float(resumen_estratos.iloc[0]['G_Stat_Mean'])
                cohesion_idx = ((total_miembros - mejor_estrato_exc) / total_miembros) * 100

                # --- B. Cálculo de Fidelidad Individual Ponderada ---
                # Ponderación 1: Validación Espejo
                w_base = np.where(validas_df['Validado_Espejo'].isin(['SI (Doble)', 'SI (Sin Espejo)']), 1.0, 0.5)

                # Ponderación 2: Normalización Inversa del G-Stat (Más cerca a 0 = mejor = peso 1.0)
                g_min = validas_df['G_Stat_Principal'].min()
                g_max = validas_df['G_Stat_Principal'].max()
                w_g = 1.0 - ((validas_df['G_Stat_Principal'] - g_min) / (g_max - g_min)) if g_max > g_min else 1.0

                # Peso Combinado final (+0.01 para evitar divisiones matemáticas por 0 puro)
                validas_df['Peso_Combo'] = (w_base * w_g) + 0.01

                for nombre in lista_nombres_partido:
                    # Máscara para saber en qué filas el votante fue EXCLUIDO
                    mask_exc = validas_df['Excluidos'].apply(lambda x: nombre in [n.strip() for n in str(x).split(',')])

                    df_out = validas_df[mask_exc]
                    df_in = validas_df[~mask_exc]

                    # Calculamos la calidad promedio de los escenarios cuando está Adentro vs Afuera
                    avg_w_out = df_out['Peso_Combo'].mean() if not df_out.empty else 0.0
                    avg_w_in = df_in['Peso_Combo'].mean() if not df_in.empty else 0.0

                    if avg_w_in == 0.0 and avg_w_out == 0.0:
                        fidelidad = 50.0
                    else:
                        fidelidad = (avg_w_in / (avg_w_in + avg_w_out)) * 100

                    # Asignar Etiqueta de Rol
                    if fidelidad >= 65: rol = "Leal (Alineado con Bloque)"
                    elif fidelidad <= 35: rol = "Disidente (Alta Probabilidad)"
                    else: rol = "Neutral / Equifinalidad Física"

                    fidelidad_votantes[nombre] = {
                        "Fidelidad_Pct": round(fidelidad, 2),
                        "Rol_Inferido": rol
                    }

                # Ordenar de más fiel a menos fiel para una lectura limpia
                fidelidad_votantes = dict(sorted(fidelidad_votantes.items(), key=lambda x: x[1]['Fidelidad_Pct'], reverse=True))

            indices_cohesion_global.append(cohesion_idx)

            # --- 3. CONSOLIDACIÓN DEL REPORTE DEL PARTIDO ---
            reporte_partidos[partido] = {
                "Padron_Total": total_miembros,
                "Evaluacion_Modelo_Fisico": {
                    "Indice_Certeza_Fisica_Pct": round(certeza_idx, 2),
                    "Total_Combinaciones_Probadas": total_combinaciones,
                    "Aciertos_Perfectos_(Dobles_o_Sin_Espejo)": aciertos_perfectos,
                    "Aciertos_Parciales_(Solo_Principal)": aciertos_parciales,
                    "Fallos_Absolutos_(Ruido_Fisico)": fallos_absolutos
                },
                "Analisis_Cohesion": {
                    "Indice_Cohesion_Partido_Pct": round(cohesion_idx, 2),
                    "Punto_Quiebre_Fisico_(Excluidos)": mejor_estrato_exc,
                    "Tamano_Bloque_Leal": total_miembros - mejor_estrato_exc,
                    "Soporte_Densidad_(Comb_Dobles)": soporte_doble,
                    "Soporte_Densidad_(Comb_Simples)": soporte_simple,
                    "G_Stat_Promedio_Bloque": round(g_stat_promedio, 4)
                },
                "Fidelidad_Individual": fidelidad_votantes
            }

        # --- 4. MÉTRICAS MACRO GLOBALES ---
        cohesion_macro = float(np.mean(indices_cohesion_global)) if indices_cohesion_global else 0.0
        certeza_macro = float(np.mean(indices_certeza_global)) if indices_certeza_global else 0.0

        reporte_global = {
            "Experimento": self.nombre_exp,
            "Resumen_Macro": {
                "Indice_Certeza_Media_Global_Pct": round(certeza_macro, 2),
                "Cohesion_Media_Global_Pct": round(cohesion_macro, 2),
                "Nota": "La Fidelidad Individual está ponderada por el G-Stat y la Validación de Espejo."
            },
            "Detalle_Partidos": reporte_partidos
        }

        ruta_salida = self.dir_resultados / f"metricas_macro_modelo_estrato_{self.ancho_estrato}.json"
        with open(ruta_salida, "w", encoding="utf-8") as f:
            json.dump(reporte_global, f, indent=4, ensure_ascii=False)

        # Output en Consola Resumido
        print(f"\n{'='*65}")
        print(f" REPORTE DE VALIDACIÓN Y COHESIÓN FORENSE - {self.nombre_exp}")
        print(f"{'='*65}")

        for p, d in reporte_partidos.items():
            print(f" Partido: {p} (Certeza Física: {d['Evaluacion_Modelo_Fisico']['Indice_Certeza_Fisica_Pct']}%)")
            print(f"   • Cohesión del Bloque: {d['Analisis_Cohesion']['Indice_Cohesion_Partido_Pct']}%")

            # Imprimir rápidamente los disidentes detectados
            disidentes = [nom for nom, info in d['Fidelidad_Individual'].items() if info['Fidelidad_Pct'] <= 35]
            if disidentes:
                print(f"   • Disidentes Detectados: {', '.join(disidentes)}")
            else:
                print(f"   • Disidentes Detectados: Ninguno concluyente")
            print(f"")
        print(f"{'='*65}\n[+] Revisa 'metricas_macro_modelo.json' para el desglose individual completo.")


    def ejecutar_analisis(self):
        print(f"\n{'='*50}")
        print(f" INICIANDO VALIDACIÓN CRUZADA Y PONDERACIÓN")
        print(f" Experimento: {self.nombre_exp}")
        print(f"{'='*50}")

        if not self.ruta_simulaciones.exists():
            print(f"[!] Error: Dataset de simulación no encontrado.")
            return

        df_sim_raw = pd.read_csv(self.ruta_simulaciones)
        df_sim = self._filtrar_simulaciones_integras(df_sim_raw)

        with open(COUNT_REAL_FILE, "r", encoding="utf-8") as f:
            df_real = pd.DataFrame(json.load(f))

        votantes_por_partido = self._cargar_listas_votantes()
        resultados_totales = []

        objetivos = self.config.get("objetivos_validacion", [])

        for obj in objetivos:
            partido = obj['partido_acronimo']
            opcion_ppal = obj['opcion_esperada']

            opcion_contraria = "OPCION 4" if opcion_ppal == "OPCION 2" else "OPCION 2"

            lista_nombres_partido = votantes_por_partido.get(partido, [])
            total_miembros = len(lista_nombres_partido)

            if total_miembros == 0:
                continue

            df_partido_sim = df_sim[df_sim['party_acronym'] == partido]
            df_real_ppal = df_real[df_real['voto_observado'] == opcion_ppal]
            df_real_espejo = df_real[df_real['voto_observado'] == opcion_contraria]

            limite_inferior = max(2, int(total_miembros * 0.33))

            print(f"\n[*] Evaluando: {partido} -> {opcion_ppal} (Espejo: {opcion_contraria})")

            for k_seleccionados in range(total_miembros, limite_inferior - 1, -1):
                num_excluidos = total_miembros - k_seleccionados
                combinaciones = self.motor.generar_combinaciones(lista_nombres_partido, k_seleccionados)

                for combo in tqdm(combinaciones, desc=f"      Excluyendo {num_excluidos} ({k_seleccionados} activos)", leave=False):

                    df_sim_subset_ppal = df_partido_sim[df_partido_sim['name'].isin(combo)]
                    g_stat_ppal, p_val_ppal, df_eff_ppal = self.motor.calcular_test_g_ponderado(df_sim_subset_ppal, df_real_ppal)
                    validado_ppal = "SI" if p_val_ppal >= 0.05 else "NO"

                    excluidos = list(set(lista_nombres_partido) - set(combo))
                    str_excluidos = ", ".join(sorted(excluidos)) if excluidos else "NINGUNO"

                    g_stat_exc, p_val_exc, df_eff_exc = None, None, None
                    validado_exc = "N/A"

                    if len(excluidos) >= 2:
                        df_sim_subset_exc = df_partido_sim[df_partido_sim['name'].isin(excluidos)]
                        g_stat_exc, p_val_exc, df_eff_exc = self.motor.calcular_test_g_ponderado(df_sim_subset_exc, df_real_espejo)
                        validado_exc = "SI" if p_val_exc >= 0.05 else "NO"

                    espejo_valido = "NO"
                    if validado_ppal == "SI":
                        if len(excluidos) < 2:
                            espejo_valido = "SI (Sin Espejo)"
                        elif validado_exc == "SI":
                            espejo_valido = "SI (Doble)"
                        else:
                            espejo_valido = "SI (Parcial)"

                    resultados_totales.append({
                        "Partido": partido,
                        "Opcion_Principal": opcion_ppal,
                        "Opcion_Contraria": opcion_contraria,
                        "Cantidad_Excluidos": num_excluidos,
                        "N_Votantes_Incluidos": k_seleccionados,
                        "G_Stat_Principal": round(g_stat_ppal, 4),
                        "df_Principal": round(df_eff_ppal, 2),
                        "Validado_Principal": validado_ppal,
                        "G_Stat_Excluidos": round(g_stat_exc, 4) if g_stat_exc is not None else "N/A",
                        "df_Excluidos": round(df_eff_exc, 2) if df_eff_exc is not None else "N/A",
                        "Validado_Excluidos": validado_exc,
                        "Validado_Espejo": espejo_valido,
                        "Excluidos": str_excluidos
                    })

        if resultados_totales:
            df_resultados = pd.DataFrame(resultados_totales)

            df_resultados = df_resultados.sort_values(
                by=['Partido', 'Validado_Espejo', 'Validado_Principal', 'G_Stat_Principal'],
                ascending=[True, False, False, True]
            )

            df_resultados.insert(0, 'ID_Analisis', range(1, len(df_resultados) + 1))

            archivo_salida = self.dir_resultados / f"analisis_sensibilidad_forense_estrato_{self.ancho_estrato}.csv"
            df_resultados.to_csv(archivo_salida, index=False, encoding='utf-8')
            print(f"\n[+] Análisis completado. Resultados exportados a:\n    {archivo_salida}")

            # Le pasamos el diccionario de votantes para el cálculo individual
            self._generar_metricas_macro(df_resultados, votantes_por_partido)

if __name__ == "__main__":
    orquestador = OrquestadorForense()
    orquestador.ejecutar_analisis()