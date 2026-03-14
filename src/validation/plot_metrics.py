import json
import pandas as pd
from pathlib import Path

from utils.paths import (
    VAL_SETTINGS_FILE,
    RESULTS_VOTE_DIR,
    REAL_CSV_NAME,
    EXT_SIMULATION_CSV_NAME,
    COMP_RESULT_CSV_NAME
)
from graphs.visualizador_estadistico import VisualizadorDistribucion

def cargar_configuracion(ruta: Path) -> dict:
    """Lee los hiperparámetros del experimento actual."""
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)

def preparar_datos_plot(ruta_real: Path, ruta_sim: Path, friction: float, bounciness: float) -> pd.DataFrame:
    """
    Carga ambos CSVs, filtra la simulación por los parámetros seleccionados
    y unifica ambos en formato largo (Long Format) preparado para Seaborn.
    """
    df_real = pd.read_csv(ruta_real)
    df_sim = pd.read_csv(ruta_sim)

    # Convertimos los parámetros simulados a float y redondeamos para evitar problemas de exactitud de coma flotante
    df_sim['friction'] = df_sim['friction'].astype(float).round(2)
    df_sim['bounciness'] = df_sim['bounciness'].astype(float).round(2)

    filtro_f = round(friction, 2)
    filtro_b = round(bounciness, 2)

    # 1. Filtramos las 20 simulaciones que corresponden EXCLUSIVAMENTE a este parámetro
    df_sim_filtrado = df_sim[(df_sim['friction'] == filtro_f) & (df_sim['bounciness'] == filtro_b)].copy()

    if df_sim_filtrado.empty:
        print(f"[ADVERTENCIA] No hay datos simulados para Fricción={filtro_f} y Rebote={filtro_b}.")
        return pd.DataFrame()

    # 2. Extraer columnas clave de la realidad y añadir la etiqueta 'Origen'
    df_plot_real = df_real[['party', 'extraction_rank']].copy()
    df_plot_real['Origen'] = 'Real (Campo)'
    df_plot_real['extraction_rank'] = pd.to_numeric(df_plot_real['extraction_rank'], errors='coerce')

    # 3. Extraer columnas clave de la simulación y añadir la etiqueta 'Origen'
    df_plot_sim = df_sim_filtrado[['party', 'extraction_rank']].copy()
    df_plot_sim['Origen'] = 'Simulado (Blender)'
    df_plot_sim['extraction_rank'] = pd.to_numeric(df_plot_sim['extraction_rank'], errors='coerce')

    # 4. Unir (Concatenar) los dos DataFrames uno debajo del otro
    df_unido = pd.concat([df_plot_real, df_plot_sim], ignore_index=True)
    return df_unido

def main():
    print("=" * 60)
    print(" 📊 INICIANDO ORQUESTADOR DE GRÁFICOS DE DISPERSIÓN")
    print("=" * 60)

    # 1. Rutas del contexto
    settings = cargar_configuracion(VAL_SETTINGS_FILE)
    nombre_exp = settings.get("nombre_experimento", "experimento_default")

    directorio_exp = RESULTS_VOTE_DIR / nombre_exp
    directorio_fisico = RESULTS_VOTE_DIR / "validacion_estratigrafia"
    plots_dir = directorio_exp / "plots"

    ruta_csv_real = directorio_fisico / REAL_CSV_NAME
    ruta_csv_sim = directorio_exp / EXT_SIMULATION_CSV_NAME
    ruta_csv_comp = directorio_exp / COMP_RESULT_CSV_NAME

    if not ruta_csv_comp.exists():
        print("[ERROR] No se encontró el archivo de comparativa (comparison_results.csv).")
        return

    # 2. Selección Inteligente: Buscar el mejor resultado
    # Cargamos el CSV comparativo y agarramos la primera fila (la de menor error global)
    df_comp = pd.read_csv(ruta_csv_comp)
    mejor_friccion = float(df_comp.iloc[0]['friction'])
    mejor_rebote = float(df_comp.iloc[0]['bounciness'])

    print(f"[*] Parámetro seleccionado automáticamente por menor MSE:")
    print(f"    -> Friction: {mejor_friccion} | Bounciness: {mejor_rebote}")

    # 3. Limpieza y preparación de datos
    df_plot = preparar_datos_plot(ruta_csv_real, ruta_csv_sim, mejor_friccion, mejor_rebote)

    if df_plot.empty:
        return

    # 4. Invocación del Visualizador
    visualizador = VisualizadorDistribucion()

    ruta_violin = plots_dir / f"violin_F{mejor_friccion}_R{mejor_rebote}.png"
    ruta_caja = plots_dir / f"boxplot_F{mejor_friccion}_R{mejor_rebote}.png"

    visualizador.graficar_dispersion_violin(df_plot, mejor_friccion, mejor_rebote, ruta_violin)
    visualizador.graficar_dispersion_cajas(df_plot, mejor_friccion, mejor_rebote, ruta_caja)

    print("\n[SISTEMA] Visualización completada con éxito.")

if __name__ == "__main__":
    main()