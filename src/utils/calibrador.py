import json
import pandas as pd
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional

class CalibradorEstratigrafico:
    """Motor universal de calibracion estratigráfica.

    Procesa archivos CSV estandarizados (reales o simulados) para extraer
    métricas físicas de sedimentación y genera comparativas de error (MSE).
    """

    def __init__(self):
        """Inicializa el calibrador (sin estado). La inyección de datos se hace por método."""
        pass

    def procesar_extraccion_csv(self, ruta_csv_entrada: Path, ruta_json_salida: Path) -> None:
        """
        Lee un CSV estandarizado, agrupa por Fricción/Rebote y calcula las 3 métricas.
        Guarda el resultado consolidado en un archivo JSON.
        """
        print(f"\n[CALIBRADOR] Procesando archivo: {ruta_csv_entrada.name}...")

        if not ruta_csv_entrada.exists():
            raise FileNotFoundError(f"No se encontró el archivo CSV: {ruta_csv_entrada}")

        df = pd.read_csv(ruta_csv_entrada)

        # Aseguramos que el rango de extracción sea numérico
        df['extraction_rank'] = pd.to_numeric(df['extraction_rank'], errors='coerce')

        resultados = []
        grupos_parametros = df.groupby(['friction', 'bounciness'])

        for (friccion, rebote), df_grupo in grupos_parametros:
            # 1. Centro de Masa (Promedio matemático del rango de salida)
            cm_dict = df_grupo.groupby('party')['extraction_rank'].mean().round(2).to_dict()
            cm_dict = dict(sorted(cm_dict.items(), key=lambda item: item[1]))

            # 2. Dispersión (Desviación Estándar de la capa)
            # fillna(0) previene errores si hay un solo voto de un color
            disp_dict = df_grupo.groupby('party')['extraction_rank'].std().fillna(0).round(2).to_dict()

            # 3. Inversión Fina (A sale antes que B)
            inv_dict = self._calcular_inversion_fina(df_grupo)

            resultados.append({
                "friction": friccion,
                "bounciness": rebote,
                "total_sim_seeds": df_grupo['sim_seed'].nunique(),
                "metricas": {
                    "centro_masa": cm_dict,
                    "dispersion": disp_dict,
                    "inversion_fina": inv_dict
                }
            })

        datos_exportar = {
            "metadata": {"fuente_origen": ruta_csv_entrada.name},
            "resultados": resultados
        }

        self._guardar_json(datos_exportar, ruta_json_salida)

    def _calcular_inversion_fina(self, df_grupo: pd.DataFrame) -> Dict[str, float]:
        """Helper puro que calcula la tasa de inversión local (Mezcla A/B)."""
        df = df_grupo.copy()
        # Extraer 'A' o 'B' de la columna 'vote' (Ej: 'ROSADO A' -> 'A')
        df['subgroup'] = df['vote'].apply(lambda x: str(x).split()[-1])

        tasas_inversion_por_color = defaultdict(list)

        # Iteramos semilla por semilla (trial)
        for _, df_seed in df.groupby('sim_seed'):
            for color, df_color in df_seed.groupby('party'):
                rangos_A = df_color[df_color['subgroup'] == 'A']['extraction_rank'].tolist()
                rangos_B = df_color[df_color['subgroup'] == 'B']['extraction_rank'].tolist()

                if rangos_A and rangos_B:
                    # Inversión: Voto A (entró primero) sale ANTES (rango menor) que Voto B
                    inversiones = sum(1 for a in rangos_A for b in rangos_B if a < b)
                    total_pares = len(rangos_A) * len(rangos_B)

                    tasa = (inversiones / total_pares) * 100
                    tasas_inversion_por_color[color].append(tasa)

        # Retornamos el promedio de la tasa entre todas las semillas/trials
        return {color: round(sum(tasas) / len(tasas), 2) for color, tasas in tasas_inversion_por_color.items()}

    def generar_comparativa_csv(self, ruta_true_json: Path, ruta_sim_json: Path, ruta_csv_salida: Path) -> None:
        """
        Lee los JSONs de métricas procesadas, calcula el Error Cuadrático Medio (MSE)
        y exporta un CSV ordenado de menor a mayor error.
        """
        print(f"\n[CALIBRADOR] Generando comparativa: {ruta_csv_salida.name}...")

        if not ruta_true_json.exists() or not ruta_sim_json.exists():
            print("[ERROR] Faltan los archivos JSON base para realizar la comparación.")
            return

        with open(ruta_true_json, 'r', encoding='utf-8') as f:
            datos_true = json.load(f)["resultados"][0]["metricas"] # El índice 0 es 'REAL_WORLD'

        with open(ruta_sim_json, 'r', encoding='utf-8') as f:
            datos_sim = json.load(f)["resultados"]

        filas_csv = []

        for combo in datos_sim:
            m_sim = combo["metricas"]

            # Cálculos de MSE para cada componente
            mse_cm = self._calcular_mse(datos_true["centro_masa"], m_sim["centro_masa"])
            mse_disp = self._calcular_mse(datos_true["dispersion"], m_sim["dispersion"])
            mse_inv = self._calcular_mse(datos_true["inversion_fina"], m_sim["inversion_fina"])

            # Error Global (Pesos: 50% Centro Masa, 30% Dispersión, 20% Inversión)
            error_total = (mse_cm * 0.4) + (mse_disp * 0.4) + (mse_inv * 0.2)

            filas_csv.append({
                "friction": combo["friction"],
                "bounciness": combo["bounciness"],
                "mse_centro_masa": round(mse_cm, 4),
                "mse_dispersion": round(mse_disp, 4),
                "mse_inversion_fina": round(mse_inv, 4),
                "error_total_ponderado": round(error_total, 4)
            })

        # Convertir a DataFrame, ordenar del mejor (menor error) al peor, y guardar
        df_resultados = pd.DataFrame(filas_csv)
        df_resultados = df_resultados.sort_values(by="error_total_ponderado", ascending=True)

        ruta_csv_salida.parent.mkdir(parents=True, exist_ok=True)
        df_resultados.to_csv(ruta_csv_salida, index=False)
        print(f"[SISTEMA] Matriz de comparación exportada en: {ruta_csv_salida}")

    def _calcular_mse(self, dict_real: Dict[str, float], dict_sim: Dict[str, float]) -> float:
        """Helper para calcular el Error Cuadrático Medio entre dos diccionarios."""
        suma_cuadrados, n_colores = 0, 0
        for color, valor_real in dict_real.items():
            valor_sim = dict_sim.get(color, 0.0) # Si falta en simulado, asumimos 0 y penaliza
            suma_cuadrados += (valor_real - valor_sim) ** 2
            n_colores += 1

        return suma_cuadrados / n_colores if n_colores > 0 else 0.0

    def _guardar_json(self, datos: Dict[str, Any], ruta_salida: Path) -> None:
        """Exportador universal a JSON."""
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
        print(f"[SISTEMA] Archivo JSON exportado exitosamente en: {ruta_salida}")