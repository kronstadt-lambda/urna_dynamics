import matplotlib.pyplot as plt
import seaborn as sns
import textwrap

class GraficadorValidacion:
    """
    Encapsula la lógica de visualización para la validación forense.
    Genera gráficas que superponen la densidad de probabilidad de la simulación
    física contra la frecuencia de observación real.
    """
    def __init__(self):
        sns.set_style("whitegrid")

    def generar_grafica_individual(self, res: dict, output_path: str, ancho_intervalo: int) -> None:
        """
        Genera un panel único enfocado en una combinación específica, mostrando
        detalladamente la metadata de exclusiones.
        """
        if res is None:
            return

        fig, ax = plt.subplots(figsize=(14, 8))
        color = '#0000FF' if res['party'] == 'AvP' else '#FF0000'
        df = res['plot_data']

        # Normalización al vuelo
        if 'Votos_Reales_Norm' not in df.columns:
            suma_reales = df['Votos_Reales'].sum()
            df['Votos_Reales_Norm'] = df['Votos_Reales'] / suma_reales if suma_reales > 0 else 0

        # Curva A: Probabilidad del Modelo Físico
        ax.plot(df['Estrato'], df['Probabilidad_Modelo'], color=color, linewidth=2.5, label=f"Modelo Físico {res['party']} (P)")
        ax.fill_between(df['Estrato'], df['Probabilidad_Modelo'], color=color, alpha=0.2)

        # Curva B: Votos Reales Observados
        width = 0.4
        ax.bar(df['Estrato'], df['Votos_Reales_Norm'], width=width, color='black', alpha=0.7,
               edgecolor='black', label=f"Realidad ({res['option']})")

        # --- CAJA DE INFORMACIÓN FORENSE DETALLADA ---
        validado = "VÁLIDO" if res['p_value'] >= 0.05 else "NO VÁLIDO"
        str_excluidos = ", ".join(res['excluidos']) if res['excluidos'] else "Ninguno"
        str_excluidos_wrap = textwrap.fill(str_excluidos, width=65) # Evita que el texto se salga de la caja

        textstr = (
            f"DATOS DE LA COMBINACIÓN:\n"
            f"• Partido: {res['party']}\n"
            f"• Opción Objetivo: {res['option']}\n"
            f"• Votantes Analizados: {res['n_incluidos']} de {res['n_total']} congresistas.\n"
            f"• Excluidos ({len(res['excluidos'])}):\n  {str_excluidos_wrap}\n"
            f"--------------------------------------------------\n"
            f"ESTADÍSTICA (Test-G):\n"
            f"• G-Stat Ponderado = {res['g_stat']:.3f}\n"
            f"• Grados de Libertad = {res['df']:.1f}\n"
            f"• P-Value = {res['p_value']:.4f}\n"
            f"• STATUS: {validado}"
        )

        props = dict(boxstyle='round,pad=0.6', facecolor='#F8F9F9', alpha=0.95, edgecolor='gray')

        # Colocamos la caja arriba a la izquierda
        ax.text(0.02, 0.96, textstr, transform=ax.transAxes, fontsize=11,
                verticalalignment='top', bbox=props, fontfamily='monospace')

        # Formato y Títulos
        ax.set_title(f"Análisis de Sensibilidad: Distribución Física vs Realidad", fontsize=16, pad=20, fontweight='bold')
        ax.set_ylabel("Densidad Probabilística / Frecuencia Observada", fontsize=12)
        ax.set_xlabel(f"Estrato de Extracción (Ancho del Bin: {ancho_intervalo} votos)", fontsize=12)

        ax.legend(loc='upper right', frameon=True, shadow=True, fontsize=11)
        ax.tick_params(axis='x', rotation=45)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()