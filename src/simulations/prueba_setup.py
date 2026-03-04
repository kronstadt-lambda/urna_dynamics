import os
import sys
ruta_src = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ruta_src not in sys.path:
    sys.path.append(ruta_src)

from utils.paths import ASSETS_DIR, RESULTS_VOTE_DIR
from utils.simuladores import SimuladorFisico
from utils.randomization import GeneradorAleatorioVotos

# randomization
generador = GeneradorAleatorioVotos(semilla=2026)
ID_ACTUAL = 45

if __name__ == "__main__":
    # 1. Definir las rutas
    archivo_urna = os.path.join(ASSETS_DIR, "simple_urna.blend")
    archivo_voto = os.path.join(ASSETS_DIR, "voto.blend")

    # 2. Instanciar nuestra clase
    simulador = SimuladorFisico(sim_id=ID_ACTUAL)

    # 3. Importar la Urna (tal como esta)
    urna = simulador.importar_objeto(
        ruta_archivo=archivo_urna,
        nombre_original="urna_cylinder",
        nombre_nuevo="urna_1"
    )
    print(f"Urna importada: {urna.name}")

    # 4. Importar el Voto
    voto = simulador.importar_objeto(
        ruta_archivo=archivo_voto,
        nombre_original="voto_1D_patron1",
        nombre_nuevo="voto_1"
    )
    print(f"Voto importado: {voto.name}")

    # 5. Prueba de Generación Estocástica de parametros de posicionamiento y rotación
    p = generador.obtener_parametros_caida()

    # 6. Posicionar el Voto según los requerimientos
    simulador.posicionar_objeto(voto, p['x'], p['y'], 0.51, p['rot_y'], rot_z_grados=p['rot_z'])

    # # 7. Aplicar transformaciones al voto en su posición final (estandarizacion)
    # simulador.aplicar_transformaciones_y_resetear_origen(voto)

    # 8. Ejecutar la física hasta el frame 30 y obtener la lectura
    datos_finales = simulador.ejecutar_simulacion_y_obtener_datos(frame_final=100, objeto_objetivo=voto)

    # 3. Guardar en el archivo central de la votación
    simulador.registrar_datos_csv(
        datos=datos_finales,
        directorio=RESULTS_VOTE_DIR,
        nombre_archivo="auditoria_completa_votos.csv"
    )

    # 10. Guardar el resultado en un archivo .blend
    simulador.guardar_escena(
        directorio_destino=RESULTS_VOTE_DIR,
        nombre_archivo=f"sim_{ID_ACTUAL}_inspeccion.blend"
    )
