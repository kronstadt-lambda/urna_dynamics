from pathlib import Path

# Calcula la raíz del proyecto (match_mind/)
# utils/ -> src/ -> match_mind/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Rutas internas del proyecto (Single Source of Truth)
LOGS_DIR = PROJECT_ROOT / "logs"
CONFIG_DIR = PROJECT_ROOT / "config"
IMAGES_DIR = PROJECT_ROOT / "images"
ASSETS_DIR = PROJECT_ROOT / "assets"
RESULTS_VOTE_DIR = PROJECT_ROOT / "results" / "vote"

# Archivos específicos
SIM_SETTINGS_FILE = CONFIG_DIR / "sim_settings.json"
