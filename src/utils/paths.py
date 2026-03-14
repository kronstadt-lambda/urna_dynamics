from pathlib import Path

# Calcula la raíz del proyecto (match_mind/)
# utils/ -> src/ -> match_mind/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Rutas internas del proyecto (Single Source of Truth)
LOGS_DIR = PROJECT_ROOT / "logs"
CONFIG_DIR = PROJECT_ROOT / "config"
IMAGES_DIR = PROJECT_ROOT / "images"
ASSETS_DIR = PROJECT_ROOT / "assets"
SRC_DIR = PROJECT_ROOT / "src"
GRAPHS_DIR = SRC_DIR / "graphs"
RESULTS_VOTE_DIR = PROJECT_ROOT / "results" / "vote"

# Ruta archivos específicos
SIM_SETTINGS_FILE = CONFIG_DIR / "sim_settings.json"
VAL_SETTINGS_FILE = CONFIG_DIR / "val_settings.json"
PHYS_COMPILATION_FILE = CONFIG_DIR / "recopilacion_fisica.json" # Dataset de resultados reales para validación
URNA_COLORS_FILE = CONFIG_DIR / "urna_colors.json" # Mapeo de colores a votantes para validación

# Nombre de archivos especificos para calibracion
EXT_SIMULATION_CSV_NAME = "extraccion_auditoria_urn1_completa.csv"
REAL_CSV_NAME = "extraccion_real_estandarizada.csv"
TRUE_METRICS_JSON_NAME = "true_metrics.json"
SIM_METRICS_JSON_NAME = "sim_metrics.json"
COMP_RESULT_CSV_NAME = "comparison_results.csv"
