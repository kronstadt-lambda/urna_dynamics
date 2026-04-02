import pandas as pd
import numpy as np
import math
import itertools
import random
from scipy import stats
from typing import List, Dict, Tuple

class MotorMontecarloForense:
    """
    Motor estadístico para análisis de sensibilidad en simulaciones forenses.
    Calcula combinatorias de votantes y ejecuta el Test-G de verosimilitud ponderada.
    """
    def __init__(self, total_votos: int, ancho_estrato: int, max_iteraciones: int = 500):
        self.total_votos = total_votos
        self.ancho_estrato = ancho_estrato
        self.max_iteraciones = max_iteraciones

        # Pre-calcular los bins (estratos) para optimizar el rendimiento del bucle
        self.bins = range(1, self.total_votos + self.ancho_estrato + 1, self.ancho_estrato)
        self.estratos_labels = [f"{self.bins[i]}-{self.bins[i+1]-1}" for i in range(len(self.bins)-1)]

    def generar_combinaciones(self, lista_votantes: List[str], porcentaje: float) -> List[Tuple[str, ...]]:
        """
        Genera subconjuntos de votantes. Usa combinatoria exacta si es computacionalmente
        viable, de lo contrario aplica un muestreo de Montecarlo.
        """
        k = max(1, round(len(lista_votantes) * porcentaje))
        total_posibles = math.comb(len(lista_votantes), k)

        if total_posibles <= self.max_iteraciones:
            # Búsqueda Exhaustiva
            return list(itertools.combinations(lista_votantes, k))
        else:
            # Muestreo Montecarlo
            subconjuntos_unicos = set()
            intentos = 0
            # Límite de seguridad para evitar bucles infinitos en colisiones
            while len(subconjuntos_unicos) < self.max_iteraciones and intentos < self.max_iteraciones * 3:
                muestra = tuple(sorted(random.sample(lista_votantes, k)))
                subconjuntos_unicos.add(muestra)
                intentos += 1
            return list(subconjuntos_unicos)

    def _asignar_estratos(self, serie_posiciones: pd.Series) -> pd.Series:
        return pd.cut(serie_posiciones, bins=self.bins, labels=self.estratos_labels, right=False, include_lowest=True)

    def calcular_test_g_ponderado(self, df_sim_subset: pd.DataFrame, df_real_opcion: pd.DataFrame) -> Tuple[float, float, float]:
        """
        Ejecuta el Test-G continuo (sin umbrales) sobre un subconjunto específico de datos.
        Retorna: (G-Stat, P-Value, Grados de Libertad Efectivos)
        """
        # Curva A: Densidad del Modelo (Subconjunto)
        estratos_sim = self._asignar_estratos(df_sim_subset['conteo_orden'])
        conteo_sim = estratos_sim.value_counts().reindex(self.estratos_labels, fill_value=0)

        suma_sim = conteo_sim.sum()
        if suma_sim == 0:
            return float('inf'), 0.0, 1.0

        prob_modelo = conteo_sim / suma_sim

        # Curva B: Observaciones Reales (Ya filtradas por opción)
        estratos_real = self._asignar_estratos(df_real_opcion['orden_conteo'])
        conteo_real = estratos_real.value_counts().reindex(self.estratos_labels, fill_value=0).values
        total_reales = conteo_real.sum()

        if total_reales == 0:
            return float('inf'), 0.0, 1.0

        # Frecuencias Esperadas
        frecuencias_esperadas = prob_modelo.values * total_reales
        frecuencias_esperadas = np.where(frecuencias_esperadas == 0, 1e-12, frecuencias_esperadas)
        frecuencias_esperadas = (frecuencias_esperadas / frecuencias_esperadas.sum()) * total_reales

        obs = conteo_real.astype(float)
        exp = frecuencias_esperadas

        # Desviación de Poisson
        g_terms = np.zeros_like(obs)
        mask = obs > 0
        g_terms[mask] = 2 * (obs[mask] * np.log(obs[mask] / exp[mask]) + exp[mask] - obs[mask])
        g_terms[~mask] = 2 * exp[~mask]

        # Ponderación proporcional pura
        max_prob = prob_modelo.values.max()
        pesos = prob_modelo.values / max_prob if max_prob > 0 else np.zeros_like(prob_modelo.values)

        g_stat_ponderado = np.sum(pesos * g_terms)
        df_efectivo = max(1.0, np.sum(pesos) - 1.0)
        p_value = stats.chi2.sf(g_stat_ponderado, df_efectivo)

        return float(g_stat_ponderado), float(p_value), float(df_efectivo)