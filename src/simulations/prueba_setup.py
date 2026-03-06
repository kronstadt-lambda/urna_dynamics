import os
import sys
import json
import random

# Inyección dinámica para reconocer el paquete 'utils'
ruta_src = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ruta_src not in sys.path:
    sys.path.append(ruta_src)

from utils.paths import ASSETS_DIR, RESULTS_VOTE_DIR, CONFIG_DIR
from utils.simuladores import SimuladorFisico
from utils.randomization import GeneradorAleatorioVotos
from utils.escenarios import EscenarioVotacion

if __name__ == "__main__":
    # ==========================================
    # 1. CARGA DE LA VERDAD DE CAMPO (JSON)
    # ==========================================
    archivo_json = "urna2.json"
    ruta_json = os.path.join(CONFIG_DIR, archivo_json)

    with open(ruta_json, "r", encoding="utf-8") as f:
        datos_votantes = json.load(f)

    # Extraemos el nombre de la urna desde el primer registro (ej. "urn2")
    nombre_urna_actual = datos_votantes[0].get("urn", "urna_default")

    # ==========================================
    # 2. HIPERPARÁMETROS DEL LOTE
    # ==========================================
    CANTIDAD_SIMULACIONES = 1  # Ajusta este valor (ej. 10000 para producción)

    archivo_urna = os.path.join(ASSETS_DIR, "urna.blend")
    archivo_voto = os.path.join(ASSETS_DIR, "voto.blend")

    # ==========================================
    # 3. BUCLE PRINCIPAL DE SIMULACIÓN
    # ==========================================
    print(f"Iniciando lote de {CANTIDAD_SIMULACIONES} simulaciones para {nombre_urna_actual}...")

    for sim_actual in range(1, CANTIDAD_SIMULACIONES + 1):
        print(f"\n{'='*40}\nARRANCANDO SIMULACIÓN {sim_actual}/{CANTIDAD_SIMULACIONES}\n{'='*40}")

        # A. Generar semilla única para esta corrida
        semilla_simulacion = random.randint(1, 10000)

        # B. Inicializar Componentes
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

        # E. Guardar Inspección Visual (.blend)
        # Nomenclatura: urn2_sim_1_inspeccion.blend
        simulador.guardar_escena(
            directorio_destino=RESULTS_VOTE_DIR,
            nombre_archivo=f"{nombre_urna_actual}_sim_{sim_actual}_inspeccion.blend"
        )

        # # E. Guardar estado final como nuevo inicio para inspección visual (READY_TO_UNLOAD)
        # simulador.guardar_estado_final_como_inicio(
        #     directorio_destino=RESULTS_VOTE_DIR,
        #     nombre_archivo=f"{nombre_urna_actual}_sim_{sim_actual}_READY_TO_UNLOAD.blend"
        # )


    print(f"\n[LOTE COMPLETADO] Todas las simulaciones han finalizado correctamente.")