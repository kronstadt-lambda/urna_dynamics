import matplotlib.pyplot as plt
import seaborn as sns
import textwrap

class GraficadorValidacion:
    """
    Encapsula la lógica de visualización para la validación forense.
    Genera gráficas que superponen la densidad de probabilidad de la simulación
    física contra la frecuencia de observación real, con soporte para validación cruzada.
    """
    def __init__(self):
        sns.set_style("whitegrid")

    def _dibujar_panel(self, ax, res: dict, color: str, ancho_intervalo: int, is_main: bool):
        df = res['plot_data']

        # Normalización al vuelo
        if 'Votos_Reales_Norm' not in df.columns:
            suma_reales = df['Votos_Reales'].sum()
            df['Votos_Reales_Norm'] = df['Votos_Reales'] / suma_reales if suma_reales > 0 else 0

        grupo_nombre = "INCLUIDOS" if is_main else "EXCLUIDOS"
        label_sim = f"Modelo Físico {res['party']} ({grupo_nombre})"

        # Curva A: Probabilidad del Modelo Físico
        ax.plot(df['Estrato'], df['Probabilidad_Modelo'], color=color, linewidth=2.5, label=label_sim)
        ax.fill_between(df['Estrato'], df['Probabilidad_Modelo'], color=color, alpha=0.2)

        # Curva B: Votos Reales Observados
        width = 0.4
        ax.bar(df['Estrato'], df['Votos_Reales_Norm'], width=width, color='black', alpha=0.7,
               edgecolor='black', label=f"Realidad ({res['option']})")

        # Preparación de textos para la caja forense
        validado = "VÁLIDO" if res['p_value'] >= 0.05 else "NO VÁLIDO"

        if res['nombres_analizados']:
            analizados_str = self._formatear_nombres_cortos(res['nombres_analizados'])
        else:
            analizados_str = "Ninguno"
        str_analizados_wrap = textwrap.fill(analizados_str, width=65)

        textstr = (
            f"GRUPO: {grupo_nombre}\n"
            f"• Opción Contrastada: {res['option']}\n"
            f"• Votantes en esta curva ({res['n_analizados']} de {res['n_total']}):\n  {str_analizados_wrap}\n"
            f"--------------------------------------------------\n"
            f"ESTADÍSTICA (Test-G):\n"
            f"• G-Stat Ponderado = {res['g_stat']:.3f}\n"
            f"• Grados de Libertad = {res['df']:.1f}\n"
            f"• P-Value = {res['p_value']:.4f}\n"
            f"• STATUS: {validado}"
        )

        props = dict(boxstyle='round,pad=0.6', facecolor='#F8F9F9', alpha=0.95, edgecolor='gray')
        ax.text(0.02, 0.96, textstr, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=props, fontfamily='monospace')

        titulo = f"Validación de {grupo_nombre} vs {res['option']}"
        ax.set_title(titulo, fontsize=14, pad=15, fontweight='bold')
        ax.set_ylabel("Densidad Probabilística / Frecuencia Observada", fontsize=11)
        ax.set_xlabel(f"Estrato de Extracción (Ancho del Bin: {ancho_intervalo} votos)", fontsize=11)

        ax.legend(loc='upper right', frameon=True, shadow=True, fontsize=10)
        ax.tick_params(axis='x', rotation=45)

    def _formatear_nombres_cortos(self, lista_nombres: list) -> str:
        """Convierte 'Nivardo Tello' a 'N. Tello' para ahorrar espacio visual."""
        acortados = []
        for nombre in lista_nombres:
            partes = str(nombre).strip().split()
            if len(partes) > 1:
                acortados.append(f"{partes[0][0]}. {partes[-1]}")
            else:
                acortados.append(str(nombre))
        return ", ".join(acortados)

    def generar_grafica_doble(self, res_principal: dict, res_excluidos: dict, output_path: str, ancho_intervalo: int) -> None:
        """
        Genera un panel doble si existen excluidos, permitiendo comparar visualmente
        la decisión del grupo principal vs la facción disidente.
        """
        if res_principal is None:
            return

        # Determinar si dibujamos 1 o 2 paneles
        if res_excluidos and res_excluidos['n_analizados'] > 0:
            fig, axes = plt.subplots(2, 1, figsize=(14, 16))
            ax1, ax2 = axes
        else:
            fig, ax1 = plt.subplots(figsize=(14, 8))
            ax2 = None

        color_principal = '#0000FF' if res_principal['party'] == 'AvP' else '#FF0000'
        color_secundario = '#28B463' # Un color verde/neutro para contrastar la disidencia

        # Dibujar Panel Superior (Principal)
        self._dibujar_panel(ax1, res_principal, color_principal, ancho_intervalo, is_main=True)

        # Dibujar Panel Inferior (Excluidos vs Opcion Contraria)
        if ax2 is not None:
            self._dibujar_panel(ax2, res_excluidos, color_secundario, ancho_intervalo, is_main=False)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()