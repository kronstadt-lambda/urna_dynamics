import json
import pandas as pd
from pathlib import Path
from utils.paths import (
    VAL_SETTINGS_FILE,
    RESULTS_VOTE_DIR,
    REAL_CSV_NAME,
    EXT_SIMULATION_CSV_NAME,
    TRUE_METRICS_JSON_NAME,
    SIM_METRICS_JSON_NAME,
    COMP_RESULT_CSV_NAME
)
from utils.validador import ValidadorEstratigrafico

def cargar_configuracion(ruta: Path) -> dict:
    """Lee los hiperparámetros del experimento actual."""
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)

def imprimir_mejores_modelos(ruta_csv_comp: Path, top_n: int = 3) -> None:
    """Lee el CSV resultante y muestra en terminal los modelos con menor error."""
    if not ruta_csv_comp.exists():
        return

    df = pd.read_csv(ruta_csv_comp)

    print("\n" + "=" * 80)
    print(f" 🏆 TOP {top_n} MEJORES COMBINACIONES FÍSICAS (Menor Error Total)")
    print("=" * 80)
    # Seleccionamos las columnas más importantes para no saturar la terminal
    columnas_vista = ['friction', 'bounciness', 'error_total_ponderado', 'mse_centro_masa']
    print(df[columnas_vista].head(top_n).to_string(index=False))
    print("=" * 80 + "\n")

def main():
    print("=" * 60)
    print(" 🚀 INICIANDO PIPELINE DE VALIDACIÓN ESTRATIGRÁFICA")
    print("=" * 60)

    # 1. Preparación del contexto (Rutas)
    settings = cargar_configuracion(VAL_SETTINGS_FILE)
    nombre_exp = settings.get("nombre_experimento", "experimento_default")

    directorio_exp = RESULTS_VOTE_DIR / nombre_exp
    directorio_fisico = RESULTS_VOTE_DIR / "validacion_estratigrafia"

    # Entradas CSV
    ruta_csv_real = directorio_fisico / REAL_CSV_NAME
    ruta_csv_sim = directorio_exp / EXT_SIMULATION_CSV_NAME

    # Salidas JSON y CSV
    ruta_json_real = directorio_exp / TRUE_METRICS_JSON_NAME
    ruta_json_sim = directorio_exp / SIM_METRICS_JSON_NAME
    ruta_csv_comp = directorio_exp / COMP_RESULT_CSV_NAME

    # 2. Inicialización del motor
    validador = ValidadorEstratigrafico()

    # 3. Procesar Verdad de Campo (Datos Reales)
    if ruta_csv_real.exists():
        validador.procesar_extraccion_csv(ruta_csv_real, ruta_json_real)
    else:
        print(f"[ADVERTENCIA] No se encontró el CSV físico real en: {ruta_csv_real}")

    # 4. Procesar Simulaciones Computarizadas (Grid Search)
    if ruta_csv_sim.exists():
        validador.procesar_extraccion_csv(ruta_csv_sim, ruta_json_sim)
    else:
        print(f"[ADVERTENCIA] No se encontró el CSV de simulación en: {ruta_csv_sim}")

    # 5. Generar Comparativa Final (MSE)
    if ruta_json_real.exists() and ruta_json_sim.exists():
        validador.generar_comparativa_csv(ruta_json_real, ruta_json_sim, ruta_csv_comp)

        # Mostrar resumen en consola
        imprimir_mejores_modelos(ruta_csv_comp)
    else:
        print("[ADVERTENCIA] Faltan los archivos JSON base para generar la matriz comparativa.")

    print("[SISTEMA] Pipeline finalizado con éxito.\n")

if __name__ == "__main__":
    main()