import os
import sys

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
    # 1. HIPERPARÁMETROS DE LA SIMULACIÓN
    # ==========================================
    ID_ACTUAL = 45
    SEMILLA_ESTOCASTICA = 1
    CANTIDAD_VOTOS = 5
    PATRON_A_USAR = "voto_1D_patron1"

    # ==========================================
    # 2. RUTAS DE ASSETS
    # ==========================================
    archivo_urna = os.path.join(ASSETS_DIR, "simple_urna.blend")
    archivo_voto = os.path.join(ASSETS_DIR, "voto.blend")

    # ==========================================
    # 3. INICIALIZACIÓN DE COMPONENTES
    # ==========================================
    simulador = SimuladorFisico(sim_id=ID_ACTUAL)
    generador = GeneradorAleatorioVotos(semilla=SEMILLA_ESTOCASTICA)

    escenario = EscenarioVotacion(
        simulador=simulador,
        generador=generador,
        num_votos=CANTIDAD_VOTOS
    )

    # ==========================================
    # 4. EJECUCIÓN DEL ESCENARIO
    # ==========================================
    lista_estados_finales = escenario.ejecutar_llenado(
        ruta_urna=archivo_urna,
        ruta_voto=archivo_voto,
        patron_voto=PATRON_A_USAR
    )

    # ==========================================
    # 5. GUARDADO DE RESULTADOS (DATOS Y 3D)
    # ==========================================
    simulador.registrar_multiples_datos_csv(
        lista_datos=lista_estados_finales,
        directorio=RESULTS_VOTE_DIR,
        nombre_archivo="auditoria_completa_votos.csv"
    )

    simulador.guardar_escena(
        directorio_destino=RESULTS_VOTE_DIR,
        nombre_archivo=f"sim_{ID_ACTUAL}_inspeccion_estratigrafica.blend"
    )

    print(f"\n[ORQUESTADOR] Simulación {ID_ACTUAL} finalizada con éxito.")