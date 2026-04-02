import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import gaussian_kde
import pandas as pd
from pathlib import Path

class GraficadorEstratos:
    """
    Genera distribuciones de densidad intercaladas de clusters,
    aislamiento de partidos objetivo y superposición del conteo real.
    """

    COLORES_BASE = [
        (1.0, 0.2, 0.2, 1.0), (0.2, 0.8, 0.2, 1.0), (0.2, 0.5, 1.0, 1.0),
        (1.0, 0.8, 0.0, 1.0), (0.8, 0.2, 1.0, 1.0), (0.0, 1.0, 1.0, 1.0),
        (1.0, 0.5, 0.0, 1.0), (1.0, 0.4, 0.7, 1.0), (0.6, 1.0, 0.2, 1.0),
        (0.5, 0.5, 0.5, 1.0), (0.4, 0.2, 0.0, 1.0), (0.0, 0.5, 0.5, 1.0),
        (0.0, 0.0, 0.5, 1.0), (0.5, 0.0, 0.0, 1.0), (0.5, 0.5, 0.0, 1.0),
        (0.3, 0.0, 0.5, 1.0), (0.8, 0.7, 0.0, 1.0), (0.5, 0.8, 1.0, 1.0),
        (0.1, 0.4, 0.1, 1.0), (1.0, 0.6, 0.5, 1.0)
    ]

    @classmethod
    def generar_grafica_intercalada(cls, df: pd.DataFrame, df_real: pd.DataFrame, ruta_salida: Path, ancho: int):
        """
        Dibuja clusters (izq), partidos (der) y marcas del conteo real (eje central del panel der).
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 16), gridspec_kw={'width_ratios': [3, 1]}, sharey=True)

        # --- PANEL 1: CLUSTERS ---
        ax1.axvline(0, color='black', linewidth=1.5, linestyle='--')
        df_copy = df.dropna(subset=['conteo_orden']).copy()
        df_copy['nivel_num'] = df_copy['estrato'].str.extract('(\d+)').astype(int)
        niveles = sorted(df_copy['nivel_num'].unique())

        max_orden = df_copy['conteo_orden'].max()
        y_eval = np.linspace(1, max_orden + 5, 500)

        for i, nivel in enumerate(niveles):
            datos = df_copy[df_copy['nivel_num'] == nivel]['conteo_orden']
            if len(datos) < 2 or datos.std() < 1e-5: continue

            kde = gaussian_kde(datos)
            kde.set_bandwidth(bw_method='scott')
            densidad = kde(y_eval) * (ancho * 3)

            if i % 2 != 0: densidad = -densidad
            color_rgba = cls.COLORES_BASE[i % len(cls.COLORES_BASE)]
            ax1.fill_betweenx(y_eval, 0, densidad, color=(color_rgba[0], color_rgba[1], color_rgba[2], 0.6), label=f'Level {nivel}')

        ax1.set_ylabel('Orden de Conteo (1=Sup, 113=Fondo)', fontsize=12)
        ax1.invert_yaxis()

        # --- PANEL 2: PARTIDOS + CONTEO REAL ---
        ax2.axvline(0, color='black', linewidth=1.5)

        # Superposición de CONTEO REAL (Puntos en el eje central)
        # Opc 2: Verde Esmeralda | Opc 4: Naranja
        for _, row in df_real.iterrows():
            y_pos = row['orden_conteo']
            voto = row['voto_observado']
            color_real = '#2ecc71' if voto == 'OPCION 2' else '#e67e22'
            # Dibujamos una pequeña línea horizontal que cruza el eje 0
            ax2.hlines(y_pos, -0.1, 0.1, color=color_real, alpha=0.8, linewidth=2, zorder=5)

        # Distribución Partidos
        for party, color, side in [('AvP', 'blue', -1), ('PP', 'red', 1)]:
            df_p = df_copy[df_copy['party_acronym'] == party]['conteo_orden']
            if len(df_p) > 1 and df_p.std() > 1e-5:
                dens = gaussian_kde(df_p)(y_eval) * (ancho * 3)
                ax2.fill_betweenx(y_eval, 0, side * dens, color=color, alpha=1.0, label=party)

        # Añadir leyenda manual para el conteo real
        from matplotlib.lines import Line2D
        custom_lines = [Line2D([0], [0], color='#2ecc71', lw=4),
                        Line2D([0], [0], color='#e67e22', lw=4),
                        Line2D([0], [0], color='blue', lw=4),
                        Line2D([0], [0], color='red', lw=4)]
        ax2.legend(custom_lines, ['Real: OPC 2', 'Real: OPC 4', 'Sim: AvP', 'Sim: PP'], loc='upper right')

        ax2.set_title('Inferencia Forense\n(Realidad vs Simulaciones)')
        ax2.set_xticks([])

        plt.tight_layout()
        plt.savefig(ruta_salida, dpi=300, bbox_inches='tight')
        plt.close()