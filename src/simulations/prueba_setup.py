import os
import sys
import json
import random

# Inyección dinámica para reconocer el paquete 'utils'
ruta_src = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ruta_src not in sys.path:
    sys.path.append(ruta_src)

from utils.paths import ASSETS_DIR, RESULTS_VOTE_DIR, CONFIG_DIR, SIM_SETTINGS_FILE
from utils.simuladores import SimuladorFisico
from utils.randomization import GeneradorAleatorioVotos
from utils.escenarios import EscenarioVotacion

if __name__ == "__main__":
    # ==========================================
    # 0. CARGA DE HIPERPARÁMETROS (SETTINGS)
    # ==========================================
    with open(SIM_SETTINGS_FILE, "r", encoding="utf-8") as f:
        settings = json.load(f)
    CANTIDAD_SIMULACIONES_A_CORRER = settings["cantidad_simulaciones"]
    GUARDAR_BLEND = settings.get("guardar_blend_inspeccion", True)

    # ==========================================
    # 1. CARGA DE LA VERDAD DE CAMPO (JSON)
    # ==========================================
    archivo_json = settings["archivo_datos_json"]
    ruta_json = os.path.join(CONFIG_DIR, archivo_json)

    with open(ruta_json, "r", encoding="utf-8") as f:
        datos_votantes = json.load(f)

    # Extraemos el nombre de la urna desde el primer registro (ej. "urn2")
    nombre_urna_actual = datos_votantes[0].get("urn", "urna_default")

    # ==========================================
    # 2. HIPERPARÁMETROS Y LÓGICA DE REANUDACIÓN
    # ==========================================

    archivo_urna = os.path.join(ASSETS_DIR, settings["archivo_urna_blend"])
    archivo_voto = os.path.join(ASSETS_DIR, settings["archivo_voto_blend"])

    nombre_archivo_csv = f"auditoria_{nombre_urna_actual}_completa.csv"
    ruta_csv_completa = os.path.join(RESULTS_VOTE_DIR, nombre_archivo_csv)

    # Lógica para detectar el último sim_id guardado y reanudar desde ahí
    sim_id_inicial = 1
    if os.path.exists(ruta_csv_completa):
        import csv
        try:
            with open(ruta_csv_completa, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                # Extraemos todos los sim_id existentes y buscamos el máximo
                sim_ids_existentes = [int(row['sim_id']) for row in reader if row.get('sim_id', '').isdigit()]
                if sim_ids_existentes:
                    sim_id_inicial = max(sim_ids_existentes) + 1
                    print(f"[*] Historial detectado. Reanudando desde Sim ID: {sim_id_inicial}")
        except Exception as e:
            print(f"[!] Error leyendo CSV para reanudar. Empezando en {sim_id_inicial}. Detalles: {e}")

    # Calculamos el límite del bucle
    sim_id_final = sim_id_inicial + CANTIDAD_SIMULACIONES_A_CORRER

    # ==========================================
    # 3. BUCLE PRINCIPAL DE SIMULACIÓN
    # ==========================================
    print(f"Iniciando lote de simulaciones para {nombre_urna_actual}...")
    print(f"Rango a ejecutar: ID {sim_id_inicial} hasta ID {sim_id_final - 1}")

    # Modificamos el bucle para que respete el nuevo rango
    for sim_actual in range(sim_id_inicial, sim_id_final):
        print(f"\n{'='*40}\nARRANCANDO SIMULACIÓN {sim_actual} (de {sim_id_final - 1})\n{'='*40}")

        # A. Generar semilla única para esta corrida
        semilla_simulacion = sim_actual #random.randint(1, 100000)

        # B. Inicializar Componentes (el resto del script se mantiene idéntico)
        simulador = SimuladorFisico(sim_id=sim_actual)
        generador = GeneradorAleatorioVotos(semilla=semilla_simulacion)

        escenario = EscenarioVotacion(
            simulador=simulador,
            generador=generador,
            datos_votantes=datos_votantes  # Pasamos la lista completa
        )

        # C. Ejecutar el llenado
        lista_estados_finales = escenario.ejecutar_llenado(
            ruta_urna=archivo_urna,
            ruta_voto=archivo_voto
        )

        # D. Guardar Datos Masivos en CSV
        simulador.registrar_multiples_datos_csv(
            lista_datos=lista_estados_finales,
            directorio=RESULTS_VOTE_DIR,
            nombre_archivo=f"auditoria_{nombre_urna_actual}_completa.csv"
        )

        # # E.0 Guardar Inspección Visual (.blend)
        # # Nomenclatura: urn2_sim_1_inspeccion.blend
        # simulador.guardar_escena(
        #     directorio_destino=RESULTS_VOTE_DIR,
        #     nombre_archivo=f"{nombre_urna_actual}_sim_{sim_actual}_inspeccion.blend"
        # )

        # E. Guardar estado final como nuevo inicio para inspección visual (READY_TO_UNLOAD)
        if GUARDAR_BLEND:
            simulador.guardar_estado_final_como_inicio(
                directorio_destino=RESULTS_VOTE_DIR,
                nombre_archivo=f"{nombre_urna_actual}_sim_{sim_actual}_READY_TO_UNLOAD.blend"
            )


    print(f"\n[LOTE COMPLETADO] Todas las simulaciones han finalizado correctamente.")