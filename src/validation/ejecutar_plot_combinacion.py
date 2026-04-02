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

from utils.paths import FORENSIC_SETTINGS_FILE, RESULTS_VOTE_DIR, FILES_DIR, COUNT_REAL_FILE, VOTOS_REAL_FILE
from graphs.visualizacion_validacion import GraficadorValidacion

def filtrar_simulaciones_integras(df_sims: pd.DataFrame, total_votos: int) -> pd.DataFrame:
    """Filtra y mantiene únicamente las simulaciones que tienen el conteo de votos exacto."""
    conteo_por_sim = df_sims.groupby('sim_id').size()
    sims_validas = conteo_por_sim[conteo_por_sim == total_votos].index
    return df_sims[df_sims['sim_id'].isin(sims_validas)].copy()

def corregir_etiquetas_partidos(df_sims: pd.DataFrame) -> pd.DataFrame:
    """
    Homogeneiza cruzando con votos_base.csv.
    Descarta ÚNICAMENTE el partido de la simulación y lo restaura usando el nombre completo.
    """
    if not VOTOS_REAL_FILE.exists():
        return df_sims.copy()

    df_base = pd.read_csv(VOTOS_REAL_FILE)

    # CORRECCIÓN: Solo descartamos 'party_acronym'. Dejamos 'name_acronym' intacto.
    df_sims_limpio = df_sims.drop(columns=['party_acronym'], errors='ignore')

    # Restauramos la columna oficial cruzando únicamente por 'name'
    df_corregido = pd.merge(
        df_sims_limpio,
        df_base[['name', 'party_acronym']],
        on='name',
        how='left'
    )
    return df_corregido.dropna(subset=['party_acronym']).copy()

def asignar_estratos_numericos(serie_posiciones: pd.Series, ancho: int, total_votos: int = 113) -> pd.Series:
    """Crea los bins para el cálculo de densidad."""
    bins = range(1, total_votos + ancho + 1, ancho)
    labels = [f"{bins[i]}-{bins[i+1]-1}" for i in range(len(bins)-1)]
    return pd.cut(serie_posiciones, bins=bins, labels=labels, right=False, include_lowest=True)

def calcular_test_g_individual(df_sim_completo: pd.DataFrame, df_real: pd.DataFrame, partido_objetivo: str,
                               opcion_esperada: str, ancho_intervalo: int, excluidos: list,
                               total_miembros_oficial: int, total_votos: int = 113) -> dict:

    # 1. Aislar al partido (Base Total) usando los datos ya corregidos
    df_partido_base = df_sim_completo[df_sim_completo['party_acronym'] == partido_objetivo]
    if df_partido_base.empty:
        return None

    # 2. Aplicar exclusiones (Filtrar por el name_acronym corregido)
    df_partido = df_partido_base[~df_partido_base['name_acronym'].isin(excluidos)]
    miembros_incluidos = len(df_partido['name_acronym'].unique())

    # Generar labels de bins fijos para asegurar alineación
    bins = range(1, total_votos + ancho_intervalo + 1, ancho_intervalo)
    labels = [f"{bins[i]}-{bins[i+1]-1}" for i in range(len(bins)-1)]

    # Curva A: Modelo Físico
    estratos_sim = asignar_estratos_numericos(df_partido['conteo_orden'], ancho_intervalo, total_votos)

    # Reindexar con labels fijos
    conteo_sim = estratos_sim.value_counts().reindex(labels, fill_value=0)

    suma_sim = conteo_sim.sum()
    if suma_sim == 0: return None
    prob_modelo = conteo_sim / suma_sim

    # Curva B: Realidad
    df_real_opcion = df_real[df_real['voto_observado'] == opcion_esperada]
    estratos_real = asignar_estratos_numericos(df_real_opcion['orden_conteo'], ancho_intervalo, total_votos)
    conteo_real = estratos_real.value_counts().reindex(prob_modelo.index, fill_value=0).values
    total_reales = conteo_real.sum()
    if total_reales == 0: return None

    # Test-G Matemáticas
    frec_esperadas = prob_modelo.values * total_reales
    frec_esperadas = np.where(frec_esperadas == 0, 1e-12, frec_esperadas)
    frec_esperadas = (frec_esperadas / frec_esperadas.sum()) * total_reales

    obs = conteo_real.astype(float)
    exp = frec_esperadas
    g_terms = np.zeros_like(obs)
    mask = obs > 0
    g_terms[mask] = 2 * (obs[mask] * np.log(obs[mask] / exp[mask]) + exp[mask] - obs[mask])
    g_terms[~mask] = 2 * exp[~mask]

    max_prob = prob_modelo.values.max()
    pesos = np.where(prob_modelo.values > 0, prob_modelo.values / max_prob, 0)
    g_stat_ponderado = np.sum(g_terms * pesos)

    # Cálculo de Grados de Libertad Efectivos
    df_efectivo = max(1.0, np.sum(pesos) - 1.0)
    p_value = stats.chi2.sf(g_stat_ponderado, df_efectivo)

    df_plot = pd.DataFrame({
        'Estrato': prob_modelo.index,
        'Probabilidad_Modelo': prob_modelo.values,
        'Votos_Reales': conteo_real
    })

    return {
        'party': partido_objetivo, 'option': opcion_esperada,
        'g_stat': g_stat_ponderado, 'df': df_efectivo, 'p_value': p_value,
        'plot_data': df_plot,
        'n_total': total_miembros_oficial,  # <-- Ahora pasamos el padrón real
        'n_incluidos': miembros_incluidos,
        'excluidos': excluidos
    }

def plotear_combinacion(id_analisis: int, ancho_intervalo: int = 6):
    with open(FORENSIC_SETTINGS_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
        nombre_exp = config.get("nombre_experimento")
        total_votos = config.get("parametros_analisis", {}).get("total_votos_urna", 113)

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

    # 1. Extraer parámetros
    partido_objetivo = fila.iloc[0]['Partido']
    excluidos_raw = str(fila.iloc[0]['Excluidos'])

    # Limpiamos corchetes y comillas
    excluidos_limpio = excluidos_raw.replace('[', '').replace(']', '').replace("'", "").replace('"', "")

    if excluidos_limpio and excluidos_limpio.lower() not in ['nan', 'none', '', 'ninguno']:
        excluidos = [x.strip() for x in excluidos_limpio.split(",") if x.strip()]
    else:
        excluidos = []

    opcion_esperada = "OPCION 2" if partido_objetivo == "AvP" else "OPCION 4"

    # --- UNIFICACIÓN DE CRITERIO: Calcular padrón directamente de la fuente oficial ---
    df_votos_base = pd.read_csv(VOTOS_REAL_FILE)
    padron_partido = df_votos_base[df_votos_base['party_acronym'] == partido_objetivo]
    total_miembros_oficial = len(padron_partido)
    # ----------------------------------------------------------------------------------

    print(f"\n{'='*55}")
    print(f" PLOTEO DE COMBINACIÓN FORENSE - ID: {id_analisis}")
    print(f" Partido : {partido_objetivo} (Padrón oficial: {total_miembros_oficial} miembros)")
    print(f" Votantes Excluidos: {len(excluidos)}")
    if excluidos: print(f" -> {', '.join(excluidos)}")
    print(f"{'='*55}")

    # 2. Cargar y Limpiar datos
    df_sims_raw = pd.read_csv(ruta_simulaciones)

    # Filtrar integridad física
    df_sims_integras = filtrar_simulaciones_integras(df_sims_raw, total_votos)

    # Corregir etiquetas cruzando por nombre exacto con la base de datos
    df_sims = corregir_etiquetas_partidos(df_sims_integras)

    with open(COUNT_REAL_FILE, "r", encoding="utf-8") as f:
        df_real = pd.DataFrame(json.load(f))

    # 3. Calcular el partido objetivo pasando el padrón oficial
    resultados = calcular_test_g_individual(
        df_sims, df_real, partido_objetivo, opcion_esperada,
        ancho_intervalo, excluidos, total_miembros_oficial, total_votos
    )

    if resultados is None:
        print(f"[!] No hay datos suficientes para {partido_objetivo}.")
        return

    # 4. Graficar
    archivo_salida = dir_plots / f"plot_ID_{id_analisis}.png"

    print("[*] Renderizando la gráfica de validación...")
    graficador = GraficadorValidacion()
    graficador.generar_grafica_individual(resultados, str(archivo_salida), ancho_intervalo)

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