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

from utils.paths import FORENSIC_VAL_SETTINGS_FILE, RESULTS_VOTE_DIR, COUNT_REAL_FILE
from graphs.graficador_comparativo import GraficadorValidacion

def filtrar_simulaciones_integras(df_sims: pd.DataFrame, total_votos: int) -> pd.DataFrame:
    conteo_por_sim = df_sims.groupby('sim_id').size()
    sims_validas = conteo_por_sim[conteo_por_sim == total_votos].index
    return df_sims[df_sims['sim_id'].isin(sims_validas)].copy()

def asignar_estratos_numericos(serie_posiciones: pd.Series, ancho: int, total_votos: int = 113) -> pd.Series:
    bins = range(1, total_votos + ancho + 1, ancho)
    labels = [f"{bins[i]}-{bins[i+1]-1}" for i in range(len(bins)-1)]
    return pd.cut(serie_posiciones, bins=bins, labels=labels, right=False, include_lowest=True)

def calcular_test_g_individual(df_sim_completo: pd.DataFrame, df_real: pd.DataFrame, partido_objetivo: str,
                               opcion_esperada: str, ancho_intervalo: int, excluidos_para_filtro: list,
                               total_miembros_oficial: int, total_votos: int = 113) -> dict:

    df_partido_base = df_sim_completo[df_sim_completo['party_acronym'] == partido_objetivo]
    if df_partido_base.empty:
        return None

    # Omitimos de la curva a quienes estén en la lista recibida
    df_partido = df_partido_base[~df_partido_base['name'].isin(excluidos_para_filtro)]
    nombres_en_curva = df_partido['name'].unique().tolist()
    miembros_incluidos = len(nombres_en_curva)

    if miembros_incluidos == 0:
        return None

    bins = range(1, total_votos + ancho_intervalo + 1, ancho_intervalo)
    labels = [f"{bins[i]}-{bins[i+1]-1}" for i in range(len(bins)-1)]

    estratos_sim = asignar_estratos_numericos(df_partido['conteo_orden'], ancho_intervalo, total_votos)
    conteo_sim = estratos_sim.value_counts().reindex(labels, fill_value=0)

    suma_sim = conteo_sim.sum()
    if suma_sim == 0: return None
    prob_modelo = conteo_sim / suma_sim

    df_real_opcion = df_real[df_real['voto_observado'] == opcion_esperada]
    estratos_real = asignar_estratos_numericos(df_real_opcion['orden_conteo'], ancho_intervalo, total_votos)
    conteo_real = estratos_real.value_counts().reindex(prob_modelo.index, fill_value=0).values
    total_reales = conteo_real.sum()
    if total_reales == 0: return None

    frecuencias_esperadas = prob_modelo.values * total_reales
    frecuencias_esperadas = np.where(frecuencias_esperadas == 0, 1e-12, frecuencias_esperadas)
    frecuencias_esperadas = (frecuencias_esperadas / frecuencias_esperadas.sum()) * total_reales

    obs = conteo_real.astype(float)
    exp = frecuencias_esperadas
    g_terms = np.zeros_like(obs)
    mask = obs > 0
    g_terms[mask] = 2 * (obs[mask] * np.log(obs[mask] / exp[mask]) + exp[mask] - obs[mask])
    g_terms[~mask] = 2 * exp[~mask]

    max_prob = prob_modelo.values.max()
    pesos = np.where(prob_modelo.values > 0, prob_modelo.values / max_prob, 0)
    g_stat_ponderado = np.sum(g_terms * pesos)

    df_efectivo = max(1.0, np.sum(pesos) - 1.0)
    p_value = stats.chi2.sf(g_stat_ponderado, df_efectivo)

    df_plot = pd.DataFrame({
        'Estrato': prob_modelo.index,
        'Probabilidad_Modelo': prob_modelo.values,
        'Votos_Reales': conteo_real
    })

    return {
        'party': partido_objetivo,
        'option': opcion_esperada,
        'g_stat': g_stat_ponderado, 'df': df_efectivo, 'p_value': p_value,
        'plot_data': df_plot,
        'n_total': total_miembros_oficial,
        'n_analizados': miembros_incluidos,
        'nombres_analizados': sorted(nombres_en_curva),
        'nombres_omitidos': sorted(excluidos_para_filtro)
    }

def plotear_combinacion(id_analisis: int):
    with open(FORENSIC_VAL_SETTINGS_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
        nombre_exp = config.get("nombre_experimento")
        total_votos = config.get("parametros_analisis", {}).get("total_votos_urna", 113)
        ancho_intervalo = config.get("parametros_analisis", {}).get("ancho_estrato", 6)

    dir_resultados = RESULTS_VOTE_DIR / nombre_exp
    ruta_analisis = dir_resultados / "analisis_sensibilidad_forense.csv"
    ruta_simulaciones = dir_resultados / "resultado_forense_final.csv"

    dir_plots = dir_resultados / "plots"
    dir_plots.mkdir(parents=True, exist_ok=True)

    if not ruta_analisis.exists():
        print(f"[!] No se encontró el análisis en: {ruta_analisis}")
        return

    df_analisis = pd.read_csv(ruta_analisis)
    fila = df_analisis[df_analisis['ID_Analisis'] == id_analisis]

    if fila.empty:
        print(f"[!] ID_Analisis {id_analisis} no encontrado.")
        return

    partido_objetivo = fila.iloc[0]['Partido']
    opcion_esperada = fila.iloc[0]['Opcion_Observada']
    excluidos_raw = str(fila.iloc[0]['Excluidos'])

    # Lógica Inversa: Detectar la opción del bloque opositor/disidente
    opcion_contraria = "OPCION 4" if opcion_esperada == "OPCION 2" else "OPCION 2"

    n_excluidos = int(fila.iloc[0]['Cantidad_Excluidos'])
    n_incluidos = int(fila.iloc[0]['N_Votantes_Incluidos'])
    total_miembros_oficial = n_excluidos + n_incluidos

    excluidos_limpio = excluidos_raw.replace('[', '').replace(']', '').replace("'", "").replace('"', "")
    if excluidos_limpio and excluidos_limpio.lower() not in ['nan', 'none', '', 'ninguno']:
        excluidos_principales = [x.strip() for x in excluidos_limpio.split(",") if x.strip()]
    else:
        excluidos_principales = []

    print(f"\n{'='*55}")
    print(f" PLOTEO CRUZADO FORENSE - ID: {id_analisis}")
    print(f" Partido : {partido_objetivo} (Padrón total: {total_miembros_oficial} miembros)")
    print(f"{'='*55}")

    df_sims_raw = pd.read_csv(ruta_simulaciones)
    df_sims = filtrar_simulaciones_integras(df_sims_raw, total_votos)

    with open(COUNT_REAL_FILE, "r", encoding="utf-8") as f:
        df_real = pd.DataFrame(json.load(f))

    # 1. Calcular Grupo Principal (La combinación registrada en el CSV)
    print(f"[*] Evaluando INCLUIDOS vs {opcion_esperada}...")
    res_principal = calcular_test_g_individual(
        df_sims, df_real, partido_objetivo, opcion_esperada,
        ancho_intervalo, excluidos_para_filtro=excluidos_principales,
        total_miembros_oficial=total_miembros_oficial, total_votos=total_votos
    )

    # 2. Calcular Grupo Secundario (Los excluidos contrastados con la opción contraria)
    res_excluidos = None
    if len(excluidos_principales) > 0:
        print(f"[*] Evaluando EXCLUIDOS vs {opcion_contraria}...")

        # Para evaluar a los disidentes, debemos omitir de la curva matemática a la bancada principal
        todos_los_miembros = df_sims[df_sims['party_acronym'] == partido_objetivo]['name'].unique().tolist()
        incluidos_principales = [m for m in todos_los_miembros if m not in excluidos_principales]

        res_excluidos = calcular_test_g_individual(
            df_sims, df_real, partido_objetivo, opcion_contraria,
            ancho_intervalo, excluidos_para_filtro=incluidos_principales,
            total_miembros_oficial=total_miembros_oficial, total_votos=total_votos
        )

    archivo_salida = dir_plots / f"plot_ID_{id_analisis}_cruzado.png"

    print("[*] Renderizando la gráfica de validación doble...")
    graficador = GraficadorValidacion()
    graficador.generar_grafica_doble(res_principal, res_excluidos, str(archivo_salida), ancho_intervalo)

    print(f"[+] Gráfica generada exitosamente en:\n -> {archivo_salida}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            plotear_combinacion(int(sys.argv[1]))
        except ValueError:
            print("[!] El ID_Analisis debe ser numérico.")
    else:
        try:
            plotear_combinacion(int(input("Ingresa el ID_Analisis que deseas plotear: ")))
        except ValueError:
            print("[!] Entrada inválida.")