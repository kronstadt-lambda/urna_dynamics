import json
import csv
from pathlib import Path

# Configuración de rutas (Basado en tu estructura paths.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
RUTA_URNA = BASE_DIR / "config" / "urna_colors.json"
RUTA_RECOPILACION = BASE_DIR / "config" / "recopilacion_fisica.json"
RUTA_SALIDA = BASE_DIR / "results" / "vote" / "calibracion_estratigrafia" / "extraccion_real_estandarizada.csv"

def estandarizar_datos_reales():
    # 1. Cargar Metadatos de Urna
    with open(RUTA_URNA, 'r', encoding='utf-8') as f:
        votos_metadata = {v["order"]: v for v in json.load(f)}

    # 2. Cargar Pruebas Físicas
    with open(RUTA_RECOPILACION, 'r', encoding='utf-8') as f:
        pruebas_reales = json.load(f)

    dataset_csv = []

    # 3. Mapeo Trial -> sim_seed y Orden -> extraction_rank
    for trial in pruebas_reales["trials"]:
        seed = trial["trial_id"]

        for rank, vote_id in enumerate(trial["extraction_order"], start=1):
            meta = votos_metadata[vote_id]

            fila = {
                "order": meta["order"],
                "urn": meta["urn"],
                "name": meta["name"],
                "party": meta["party"],
                "vote": meta["vote"],
                "fold_pattern": meta["fold_pattern"],
                "friction": "REAL_WORLD",
                "bounciness": "REAL_WORLD",
                "fold_pattern_used": meta["fold_pattern"][0], # patron unico en real
                "sim_seed": seed,
                "extraction_rank": rank,
                "extract_frame": "" # Irrelevante para real
            }
            dataset_csv.append(fila)

    # 4. Persistir CSV
    RUTA_SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(RUTA_SALIDA, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=dataset_csv[0].keys())
        writer.writeheader()
        writer.writerows(dataset_csv)

    print(f"[SISTEMA] Archivo estandarizado creado: {RUTA_SALIDA}")

if __name__ == "__main__":
    estandarizar_datos_reales()