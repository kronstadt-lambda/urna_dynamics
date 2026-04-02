import sys
import json
import pandas as pd
from pathlib import Path

def inyectar_directorio_src() -> None:
    ruta_src = Path(__file__).resolve().parent.parent
    if str(ruta_src) not in sys.path:
        sys.path.append(str(ruta_src))

inyectar_directorio_src()

# Importamos el archivo de conteo real desde paths
from utils.paths import VAL_SETTINGS_FILE, RESULTS_VOTE_DIR, FILES_DIR, COUNT_REAL_FILE
from graphs.visualizacion_estratos import GraficadorEstratos

def asignar_estratos_dinamicos(df_base: pd.DataFrame, ancho: int) -> pd.DataFrame:
    df_base = df_base.sort_values(by=['urn', 'order']).reset_index(drop=True)
    df_base['orden_absoluto'] = range(1, len(df_base) + 1)

    total_votos = len(df_base)
    num_grupos_completos = total_votos // ancho
    resto = total_votos % ancho

    estratos = []
    for i in range(total_votos):
        grupo_idx = (i // ancho) + 1
        if grupo_idx > num_grupos_completos:
            if resto < 5:
                grupo_idx = num_grupos_completos
            else:
                grupo_idx = num_grupos_completos + 1
        estratos.append(f'Level {grupo_idx}')

    df_base['estrato'] = estratos
    return df_base

def principal():
    ANCHO_INTERVALO = 10

    # Cargar Configuración
    with open(VAL_SETTINGS_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
        nombre_exp = config.get("nombre_experimento", "exp_def")

    # Cargar CONTEO REAL (La verdad de campo)
    with open(COUNT_REAL_FILE, "r", encoding="utf-8") as f:
        datos_reales_json = json.load(f)
    df_real = pd.DataFrame(datos_reales_json)

    # Rutas
    directorio_resultados = RESULTS_VOTE_DIR / nombre_exp
    ruta_simulaciones_csv = directorio_resultados / "resultado_forense_final.csv"
    ruta_votos_base = FILES_DIR / "votos_base.csv"
    archivo_grafico_salida = directorio_resultados / f"validacion_forense_ancho_{ANCHO_INTERVALO}.png"

    # Procesamiento
    df_base = pd.read_csv(ruta_votos_base)
    df_base_est = asignar_estratos_dinamicos(df_base, ANCHO_INTERVALO)

    # Aquí procesamos TODAS las simulaciones del CSV
    df_sims = pd.read_csv(ruta_simulaciones_csv)
    df_completo = pd.merge(df_sims, df_base_est[['urn', 'order', 'estrato']], on=['urn', 'order'], how='left')

    print(f"[*] Generando gráfica con {len(df_sims)} registros de simulación...")

    # Llamada al graficador con la data real
    GraficadorEstratos.generar_grafica_intercalada(df_completo, df_real, archivo_grafico_salida, ANCHO_INTERVALO)

    print(f"[+] Archivo validado generado en: {archivo_grafico_salida}")

if __name__ == "__main__":
    principal()