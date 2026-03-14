import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

class VisualizadorDistribucion:
    """
    Clase dedicada a la generación de gráficos estadísticos avanzados
    para la auditoría estratigráfica.
    """
    def __init__(self):
        # Configuraciones globales de estilo de Seaborn
        sns.set_theme(style="whitegrid")
        # El orden físico de inserción (de abajo hacia arriba)
        self.orden_colores = ['rosado', 'rojo', 'morado', 'verde', 'celeste', 'amarillo']
        # Paleta consistente para comparar
        self.paleta = {"Real (Campo)": "#2ca02c", "Simulado (Blender)": "#ff7f0e"}

    def graficar_dispersion_violin(self, df_plot: pd.DataFrame, friction: float, bounciness: float, ruta_salida: Path) -> None:
        """
        Genera un Violin Plot dividido (Split).
        Permite comparar visualmente la campana de distribución real frente a la simulada lado a lado.
        """
        plt.figure(figsize=(12, 6))

        # split=True une la mitad "Real" y la "Simulada" en un solo violín por color
        sns.violinplot(
            data=df_plot,
            x="party",
            y="extraction_rank",
            hue="Origen",
            split=True,
            inner="quartile", # Muestra las líneas de los cuartiles dentro del violín
            order=self.orden_colores,
            palette=self.paleta,
            linewidth=1.2
        )

        self._aplicar_estilos_y_guardar(
            titulo=f"Distribución Estratigráfica por Color (Violin Plot)\nComparativa Real vs Simulado (Friction: {friction} | Bounciness: {bounciness})",
            ruta_salida=ruta_salida
        )

    def graficar_dispersion_cajas(self, df_plot: pd.DataFrame, friction: float, bounciness: float, ruta_salida: Path) -> None:
        """
        Genera un Box Plot agrupado clásico.
        Ideal para ver los valores atípicos (outliers) y la desviación intercuartil.
        """
        plt.figure(figsize=(12, 6))

        sns.boxplot(
            data=df_plot,
            x="party",
            y="extraction_rank",
            hue="Origen",
            order=self.orden_colores,
            palette=self.paleta
        )

        self._aplicar_estilos_y_guardar(
            titulo=f"Dispersión Estratigráfica por Color (Box Plot)\nComparativa Real vs Simulado (Friction: {friction} | Bounciness: {bounciness})",
            ruta_salida=ruta_salida
        )

    def _aplicar_estilos_y_guardar(self, titulo: str, ruta_salida: Path) -> None:
        """Helper interno para no repetir el código de renderizado y guardado."""
        plt.title(titulo, fontsize=14, pad=15)
        plt.xlabel("Color del Grupo (Partido)", fontsize=12)
        plt.ylabel("Turno de Extracción (1 = Primero en salir, 60 = Último)", fontsize=12)
        plt.ylim(0, 65) # Límite fijo de la urna
        plt.legend(title="Fuente de Datos", loc="lower right")

        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        plt.tight_layout()
        plt.savefig(ruta_salida, dpi=300)
        plt.close()
        print(f"[PLOT] Gráfico exportado en: {ruta_salida}")