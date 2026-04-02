import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

def inyectar_directorio_src() -> None:
    ruta_src = Path(__file__).resolve().parent.parent
    if str(ruta_src) not in sys.path:
        sys.path.append(str(ruta_src))

inyectar_directorio_src()

from utils.paths import VAL_SETTINGS_FILE, RESULTS_VOTE_DIR, COUNT_REAL_FILE
from graphs.visualizacion_validacion import GraficadorValidacion

def asignar_estratos_numericos(serie_posiciones: pd.Series, ancho: int, total_votos: int = 113) -> pd.Series:
    bins = range(1, total_votos + ancho + 1, ancho)
    labels = [f"{bins[i]}-{bins[i+1]-1}" for i in range(len(bins)-1)]
    return pd.cut(serie_posiciones, bins=bins, labels=labels, right=False, include_lowest=True)

def calcular_test_g(df_sim_completo: pd.DataFrame, df_real: pd.DataFrame, partido_objetivo: str,
                    opcion_esperada: str, ancho_intervalo: int, total_votos: int = 113) -> dict:
    """Calcula el G-Test Ponderado basado estrictamente en la distribución histórica."""
    print(f"[*] Procesando validación numérica para {partido_objetivo} vs {opcion_esperada}...")

    df_partido = df_sim_completo[df_sim_completo['party_acronym'] == partido_objetivo].copy()
    if df_partido.empty:
        print(f"[!] No se encontraron votos para el partido {partido_objetivo} en la simulación.")
        return None

    posiciones_simuladas = df_partido['conteo_orden']

    estratos_labels = [f"{i}-{min(i+ancho_intervalo-1, total_votos)}" for i in range(1, total_votos + 1, ancho_intervalo)]
    df_partido['estrato'] = asignar_estratos_numericos(posiciones_simuladas, ancho_intervalo, total_votos)
    conteo_estratos_sim = df_partido['estrato'].value_counts().reindex(estratos_labels, fill_value=0)
    prob_modelo = conteo_estratos_sim / conteo_estratos_sim.sum()

    df_opcion_real = df_real[df_real['voto_observado'] == opcion_esperada].copy()
    df_opcion_real['estrato'] = asignar_estratos_numericos(df_opcion_real['orden_conteo'], ancho_intervalo, total_votos)
    conteo_estratos_real = df_opcion_real['estrato'].value_counts().reindex(estratos_labels, fill_value=0).values
    total_reales = conteo_estratos_real.sum()

    frecuencias_esperadas = prob_modelo.values * total_reales
    frecuencias_esperadas = np.where(frecuencias_esperadas == 0, 1e-12, frecuencias_esperadas)
    frecuencias_esperadas = (frecuencias_esperadas / frecuencias_esperadas.sum()) * total_reales

    obs = conteo_estratos_real.astype(float)
    exp = frecuencias_esperadas

    g_terms = np.zeros_like(obs)
    mask = obs > 0
    g_terms[mask] = 2 * (obs[mask] * np.log(obs[mask] / exp[mask]) + exp[mask] - obs[mask])
    g_terms[~mask] = 2 * exp[~mask]

    # Pesos: Proporcionalidad pura basada en la máxima densidad del modelo
    pesos = prob_modelo.values / prob_modelo.values.max()

    g_stat_ponderado = np.sum(pesos * g_terms)
    df_efectivo = max(1.0, np.sum(pesos) - 1.0)
    p_value = stats.chi2.sf(g_stat_ponderado, df_efectivo)

    plot_data = pd.DataFrame({
        'Estrato': estratos_labels,
        'Probabilidad_Modelo': prob_modelo.values,
        'Votos_Reales': conteo_estratos_real
    })

    return {
        'party': partido_objetivo,
        'option': opcion_esperada,
        'g_stat': g_stat_ponderado,
        'p_value': p_value,
        'df': df_efectivo,
        'total_real_votes': total_reales,
        'plot_data': plot_data
    }

def filtrar_simulaciones_integras(df_sims: pd.DataFrame, total_esperado: int = 113) -> pd.DataFrame:
    conteo_por_sim = df_sims.groupby('sim_id').size()
    sims_validas = conteo_por_sim[conteo_por_sim == total_esperado].index
    df_filtrado = df_sims[df_sims['sim_id'].isin(sims_validas)].copy()

    n_original = len(conteo_por_sim)
    n_filtrado = len(sims_validas)

    if n_filtrado < n_original:
        print(f"[!] AUDITORÍA: Se descartaron {n_original - n_filtrado} simulaciones incompletas.")
        print(f"[*] Simulaciones íntegras restantes: {n_filtrado}")

    return df_filtrado

def principal():
    ANCHO_INTERVALO = 4
    TOTAL_VOTOS = 113

    with open(VAL_SETTINGS_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
        nombre_exp = config.get("nombre_experimento", "exp_def")

    directorio_resultados = RESULTS_VOTE_DIR / nombre_exp
    ruta_simulaciones_csv = directorio_resultados / "resultado_forense_final.csv"
    archivo_grafico_salida = directorio_resultados / f"validacion_ROI_testG_ancho_{ANCHO_INTERVALO}.png"

    if not ruta_simulaciones_csv.exists():
        print(f"[!] Error: No se encontró el dataset en {ruta_simulaciones_csv}")
        return

    print("[*] Cargando resultados masivos de simulación...")
    df_sim_raw = pd.read_csv(ruta_simulaciones_csv)
    df_sim_completo = filtrar_simulaciones_integras(df_sim_raw, TOTAL_VOTOS)

    if df_sim_completo.empty:
        print("[!] ERROR: Ninguna simulación tiene los 113 votos completos.")
        return

    print("[*] Cargando conteo real (Ground Truth)...")
    with open(COUNT_REAL_FILE, "r", encoding="utf-8") as f:
        df_real = pd.DataFrame(json.load(f))

    resultados_avp = calcular_test_g(df_sim_completo, df_real, "AvP", "OPCION 2", ANCHO_INTERVALO, TOTAL_VOTOS)
    resultados_pp = calcular_test_g(df_sim_completo, df_real, "PP", "OPCION 4", ANCHO_INTERVALO, TOTAL_VOTOS)

    if resultados_avp and resultados_pp:
        graficador = GraficadorValidacion()
        graficador.generar_grafica_integrada(
            results_avp=resultados_avp,
            results_pp=resultados_pp,
            output_path=archivo_grafico_salida,
            ancho_intervalo=ANCHO_INTERVALO
        )
        print("\n[VALIDACIÓN COMPLETADA] Revisa la gráfica generada.")

if __name__ == "__main__":
    principal()