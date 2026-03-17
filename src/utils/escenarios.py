"""
Módulo de Escenarios (Capa de Reglas de Negocio)
------------------------------------------------
Define las coreografías de Votación, Vaciado, Volcado y Conteo.
Interactúa exclusivamente mediante interfaces provistas por SimuladorFisico.
"""

from tqdm import tqdm
from pathlib import Path
from typing import List, Dict, Any, Tuple
from utils.simuladores import SimuladorFisico
from utils.randomization import GeneradorAleatorioVotos

class EscenarioBase:
    """
    Clase base para la gestión de escenarios forenses en Blender.

    Provee la infraestructura común para cualquier tipo de simulación (Llenado,
    Vaciado, Volcado y Conteo), gestionando el simulador, el generador estocástico y
    la persistencia de la memoria de los objetos.
    """

    def __init__(self, simulador: SimuladorFisico, generador: GeneradorAleatorioVotos, datos_votantes: List[Dict]):
        """
        Inicializa los componentes del escenario.

        Args:
            simulador: Instancia del motor físico universal.
            generador: Instancia del generador estocástico para parámetros de caída.
            datos_votantes: Lista de diccionarios con la información de los votantes.
        """
        self.simulador = simulador
        self.generador = generador
        self.datos_votantes = datos_votantes
        self.objetos_en_escena: List[Tuple[Any, Dict]] = []

class EscenarioVotacion(EscenarioBase):
    """Orquestador del escenario de llenado de urna (Deposición).

    Simula el proceso secuencial de votación, manejando la importación de
    papeletas, su posicionamiento estocástico y el cálculo de la
    estratigrafía final resultante.
    """

    def __init__(self, simulador: SimuladorFisico, generador: GeneradorAleatorioVotos, datos_votantes: List[Dict], intervalo_caida: int = 100, friccion: float = 0.5, rebote: float = 0.0):
        super().__init__(simulador, generador, datos_votantes)
        self.intervalo_caida = intervalo_caida
        self.friccion = friccion
        self.rebote = rebote

    def ejecutar_llenado(self, ruta_urna: Path, ruta_voto: Path, posiciones_urnas: dict) -> List[Dict]:
        """
        Ejecuta la coreografía completa de votación.

        Args:
            ruta_urna: Ruta al archivo .blend que contiene el modelo de la urna.
            ruta_voto: Ruta al archivo .blend con los patrones de doblado.

        Returns:
            List[Dict]: Dataset completo con la posición y rotación final de cada voto.
        """
        # Preparación del entorno
        for nombre_urna, coords in posiciones_urnas.items():
            urna_obj = self.simulador.importar_activo(ruta_urna, "urna_cylinder", f"urna_activa_{nombre_urna}")
            self.simulador.transformar_objeto(urna_obj, loc=tuple(coords), rot_grados=(0,0,0))
            tqdm.write(f"[SCENE] {nombre_urna} inicializada en {coords}")

        frame_actual = self.simulador.frame_start
        contadores_locales = {urna: 1 for urna in posiciones_urnas.keys()}

        # Bucle de deposición secuencial (voto por voto)
        with tqdm(total=len(self.datos_votantes), desc="1/4 Votación", unit="voto", leave=True, bar_format='{l_bar}{bar:30}{r_bar}') as pbar:
            for idx, voto_original in enumerate(self.datos_votantes):
                # Clonamos el diccionario para no contaminar la memoria global
                voto_info = voto_original.copy()

                # Inyectamos los parámetros físicos al dataset para trazabilidad en el CSV
                voto_info['friction'] = self.friccion
                voto_info['bounciness'] = self.rebote

                urna_destino = voto_info['urn']
                idx_local = contadores_locales[urna_destino]
                contadores_locales[urna_destino] += 1
                pos_urna = posiciones_urnas[urna_destino]

                # a) Preparación de metadatos para trazabilidad forense
                orden = voto_info['order']
                nombre_instancia = f"voto_{urna_destino}_{orden}"

                # b) Selección estocástica del patrón de doblado
                patron = self.generador.elegir_patron(voto_info['fold_pattern'])
                voto_info['fold_pattern_used'] = patron
                voto_info['sim_seed'] = self.generador.semilla_usada

                pbar.set_postfix({"Voto": f"#{orden}", "Urna": urna_destino, "Frame": frame_actual})

                # c) Importación y posicionamiento estocástico
                voto_obj = self.simulador.importar_activo(ruta_voto, patron, nombre_instancia)
                # Aplicar las propiedades físicas al objeto recién importado
                self.simulador.configurar_propiedades_superficie(voto_obj, self.friccion, self.rebote)
                p = self.generador.obtener_parametros_caida_libre(idx_local, centro_x=pos_urna[0], centro_y=pos_urna[1])

                self.simulador.transformar_objeto(
                    objeto=voto_obj,
                    loc=(p['x'], p['y'], p['z']),
                    rot_grados=(0, p['rot_y'], p['rot_z'])
                )

                # d) Ejecución de la física
                self.simulador.configurar_animacion_fisica(voto_obj, frame_activacion=frame_actual)
                self.simulador.ejecutar_pasos_fisica(frames=self.intervalo_caida)

                # e) Almacenar referencia para el análisis final
                self.objetos_en_escena.append((voto_obj, voto_info))
                frame_actual += self.intervalo_caida

                pbar.update(1)

        # Extracción de resultados estratigráficos
        tqdm.write("[SCENE] Finalizado. Capturando telemetría final de la pila...")
        return [
            self.simulador.capturar_estado_datos(obj, info)
            for obj, info in self.objetos_en_escena
        ]

class EscenarioVaciado(EscenarioBase):
    """
    Orquestador del escenario de vaciado de urna (Extracción).
    Simula la acción humana de retirar el voto más próximo a la superficie
    uno por uno, permitiendo que la pila colapse y se asiente en el proceso.
    """

    def __init__(self, simulador: SimuladorFisico, generador: GeneradorAleatorioVotos, datos_votantes: List[Dict],
                 intervalo_vaciado: int = 50, punto_busqueda: tuple = (0.0, 0.0, 0.5),
                 posiciones_bandejas: dict = None, inc_z_apilamiento: float = 0.1):
        super().__init__(simulador, generador, datos_votantes)
        self.intervalo_vaciado = intervalo_vaciado
        self.punto_busqueda = punto_busqueda
        self.posiciones_bandejas = posiciones_bandejas or {}
        self.inc_z_apilamiento = inc_z_apilamiento

    def ejecutar_vaciado(self, objetos_en_escena: List[Tuple[Any, Dict]], puntos_busqueda: dict) -> List[Dict]:
        tqdm.write("\n[SCENE] Iniciando proceso de vaciado secuencial...")
        frame_actual = self.simulador.obtener_frame_actual()
        rango_salida = 1
        resultados_extraccion = []

        # Base Z individual inicializada 50cm sobre cada bandeja
        z_bases = {
            nombre: coords[2] + 0.5
            for nombre, coords in self.posiciones_bandejas.items()
        }

        orden_urnas = ["urn1", "urn2"]

        with tqdm(total=len(objetos_en_escena), desc="2/4 Vaciado ", unit="voto", leave=True, bar_format='{l_bar}{bar:30}{r_bar}') as pbar:
            for urna_actual in orden_urnas:
                tqdm.write(f"[SCENE] >>> Cambiando a {urna_actual.upper()} <<<")
                punto_radial_busqueda = puntos_busqueda.get(urna_actual, [0,0,0.5])
                pool_extraccion = [item for item in objetos_en_escena if item[1]['urn'] == urna_actual]

                while pool_extraccion:
                    lista_objetos_blender = [item[0] for item in pool_extraccion]
                    obj_elegido = self.simulador.obtener_objeto_mas_cercano(tuple(punto_radial_busqueda), lista_objetos_blender)

                    tupla_elegida = next(item for item in pool_extraccion if item[0] == obj_elegido)
                    metadata_voto = tupla_elegida[1].copy()
                    pool_extraccion.remove(tupla_elegida)

                    # Regla de la realidad: 1 al 51 a bandeja 1, resto a bandeja 2
                    nombre_bandeja = "bandeja1" if rango_salida <= 51 else "bandeja2"
                    pos_xy = self.posiciones_bandejas[nombre_bandeja]

                    pbar.set_postfix({"Extr": rango_salida, "Urna": urna_actual, "Dest": nombre_bandeja, "Frame": frame_actual})

                    # Destino directo sobre su bandeja correspondiente
                    coord_destino = (pos_xy[0], pos_xy[1], z_bases[nombre_bandeja])
                    self.simulador.extraer_objeto_a_coordenada(obj_elegido, frame_actual, coord_destino)

                    metadata_voto["extraction_rank"] = rango_salida
                    metadata_voto["extract_frame"] = frame_actual
                    resultados_extraccion.append(metadata_voto)

                    # Incrementamos la altura Z de esa bandeja específica
                    z_bases[nombre_bandeja] += self.inc_z_apilamiento

                    self.simulador.ejecutar_pasos_fisica(frames=self.intervalo_vaciado)
                    frame_actual += self.intervalo_vaciado
                    rango_salida += 1

                    pbar.update(1)

        tqdm.write("[SCENE] Vaciado completado.")
        return resultados_extraccion

class EscenarioVolcado(EscenarioBase):
    """
    Orquestador del escenario de volcado a bandejas.
    Simplemente deja caer los votos que ya fueron posicionados verticalmente
    sobre las bandejas en la fase de vaciado.
    """
    def __init__(self, simulador: SimuladorFisico, generador: GeneradorAleatorioVotos, datos_votantes: List[Dict],
                 intervalo_volcado: int = 100):
        super().__init__(simulador, generador, datos_votantes)
        self.intervalo_volcado = intervalo_volcado

    def ejecutar_volcado(self, lista_votos_extraidos: List[Dict], ruta_bandeja: Path, posiciones_bandejas: dict) -> List[Dict]:
        tqdm.write("\n[SCENE] Iniciando proceso de volcado a bandejas (Conteo)...")

        frame_actual = self.simulador.obtener_frame_actual()

        # Importar bandejas
        for nombre_bandeja, coords in posiciones_bandejas.items():
            bandeja_obj = self.simulador.importar_activo(ruta_bandeja, "bandeja_amplia", f"instancia_{nombre_bandeja}")
            self.simulador.transformar_objeto(bandeja_obj, loc=tuple(coords), rot_grados=(0,0,0))
            tqdm.write(f"[SCENE] {nombre_bandeja} importada y posicionada en {coords}")

        # Margen de seguridad para estabilizar la memoria de Blender tras la extracción masiva
        tqdm.write(f"[*] Aplicando buffer de 200 frames de estabilización...")
        self.simulador.ejecutar_pasos_fisica(frames=200)
        frame_actual += 200

        votos_ordenados = sorted(lista_votos_extraidos, key=lambda x: x["extraction_rank"])
        objetos_procesados = []

        # Únicamente aplicamos gravedad y recolectamos la metadata limpia
        with tqdm(total=len(votos_ordenados), desc="3/4 Volcado ", unit="voto", leave=True, bar_format='{l_bar}{bar:30}{r_bar}') as pbar:
            for metadata_voto in votos_ordenados:
                rank = metadata_voto["extraction_rank"]
                nombre_bandeja = "bandeja1" if rank <= 51 else "bandeja2"

                urn = metadata_voto['urn']
                orden = metadata_voto['order']
                nombre_instancia = f"voto_{urn}_{orden}"
                voto_obj = self.simulador.obtener_objeto_por_nombre(nombre_instancia)

                if not voto_obj:
                    continue

                # Delegamos la eliminación del rebote al simulador
                self.simulador.anular_rebote(voto_obj)

                pbar.set_postfix({"Voto": nombre_instancia, "Extr": rank, "Dest": nombre_bandeja, "Frame": frame_actual})

                # Soltamos el voto exactamente desde donde ya estaba apilado
                self.simulador.soltar_objeto_suspendido(voto_obj, frame_actual=frame_actual, margen_frames=self.intervalo_volcado)

                # Avanzamos la física para que caiga
                self.simulador.ejecutar_pasos_fisica(frames=self.intervalo_volcado)
                frame_actual += self.intervalo_volcado

                # Limpiamos la metadata
                meta_limpia = metadata_voto.copy()
                for clave in ["fold_pattern", "fold_pattern_used", "friction", "bounciness", "extract_frame"]:
                    meta_limpia.pop(clave, None)
                meta_limpia["bandeja_destino"] = nombre_bandeja

                objetos_procesados.append((voto_obj, meta_limpia))

                pbar.update(1)

        # --- FASE B: LECTURA AISLADA DEL CSV ---
        tqdm.write("\n[SCENE] Dejando asentar la pila y registrando coordenadas finales...")

        # 100 frames extra de estabilización tras el último voto
        self.simulador.ejecutar_pasos_fisica(frames=100)
        frame_actual += 100

        # Delegamos la actualización del caché en el frame final al simulador
        self.simulador.actualizar_escena_a_frame(frame_actual)

        resultados_volcado = []
        for obj, meta in objetos_procesados:
            estado_final = self.simulador.capturar_estado_datos(obj, meta)
            resultados_volcado.append(estado_final)

        tqdm.write("[SCENE] Volcado a bandejas completado.")
        return resultados_volcado

class EscenarioConteo(EscenarioBase):
    def __init__(self, simulador: SimuladorFisico, generador: GeneradorAleatorioVotos, datos_votantes: List[Dict],
                 datos_conteo_real: List[Dict], intervalo_extraccion: int = 50,
                 posicion_final_conteo: tuple = (0.0, 0.0, 0.5), inc_z_apilamiento: float = 0.05,
                 tolerancia_busqueda: int = 3):
        super().__init__(simulador, generador, datos_votantes)
        self.datos_conteo_real = datos_conteo_real
        self.intervalo_extraccion = intervalo_extraccion
        self.pos_final = posicion_final_conteo
        self.inc_z_apilamiento = inc_z_apilamiento
        self.tolerancia_busqueda = tolerancia_busqueda

    def _evaluar_prioridad(self, voto_fisico_tipo: str, voto_real_tipo: str) -> int:
        """
        1: Coincidencia exacta (Prioridad Máxima - ¡Usar primero!)
        2: Comodín compatible (Prioridad Secundaria - ¡Ahorrar!)
        0: Incompatible
        """
        if voto_real_tipo == "VICIADO":
            # Para los viciados, la única opción exacta es usar un indeterminado
            return 1 if voto_fisico_tipo == "INDETERMINADO" else 0
        elif voto_real_tipo == "OPCION 4":
            if voto_fisico_tipo == "OPCION 4": return 1
            if voto_fisico_tipo == "INDETERMINADO": return 2
            return 0
        elif voto_real_tipo == "OPCION 2":
            if voto_fisico_tipo == "OPCION 2": return 1
            if voto_fisico_tipo == "INDETERMINADO": return 2
            return 0
        return 0

    def ejecutar_conteo(self, lista_votos_volcados: List[Dict], criterio_busqueda: str = 'z_max', puntos_busqueda: dict = None) -> List[Dict]:
        tqdm.write(f"\n[SCENE] Iniciando vinculación forense (Tolerancia de capa: {self.tolerancia_busqueda} votos)...")
        frame_actual = self.simulador.obtener_frame_actual()
        pool_disponible = lista_votos_volcados.copy()
        resultados_conteo = []
        z_actual = self.pos_final[2]

        with tqdm(total=len(self.datos_conteo_real), desc="4/4 Conteo  ", unit="voto", leave=True, bar_format='{l_bar}{bar:30}{r_bar}') as pbar:
            for evento_real in self.datos_conteo_real:
                orden = evento_real["orden_conteo"]
                bandeja_esperada = "bandeja1" if orden <= 51 else "bandeja2"
                voto_esperado = evento_real["voto_observado"]

                pbar.set_postfix({
                    "Progreso": f"{orden}/{len(self.datos_conteo_real)}",
                    "Tipo": voto_esperado,
                    "Bandeja": bandeja_esperada
                })

                candidatos_fisicos = [v for v in pool_disponible if v.get("bandeja_destino") == bandeja_esperada]
                objetos_map = {self.simulador.obtener_objeto_por_nombre(f"voto_{v['urn']}_{v['order']}"): v for v in candidatos_fisicos}
                lista_objs = [obj for obj in objetos_map.keys() if obj is not None]

                coord_ref = puntos_busqueda.get(bandeja_esperada) if puntos_busqueda else None
                objetos_ordenados = self.simulador.obtener_candidatos_ordenados(lista_objs, criterio_busqueda, coord_ref)

                # Dividimos los candidatos en la "Ventana Superficial" y el "Resto Profundo"
                ventana_superficial = objetos_ordenados[:self.tolerancia_busqueda]
                resto_profundo = objetos_ordenados[self.tolerancia_busqueda:]

                obj_elegido = None
                meta_elegida = None

                # ESTRATEGIA DE EXTRACCIÓN (4 INTENTOS)

                # Intento 1: Buscar coincidencia EXACTA en la superficie
                for obj in ventana_superficial:
                    if self._evaluar_prioridad(objetos_map[obj]["vote"], voto_esperado) == 1:
                        obj_elegido, meta_elegida = obj, objetos_map[obj]
                        break

                # Intento 2: Si no hay exacto arriba, gastar un COMODÍN superficial
                if not obj_elegido:
                    for obj in ventana_superficial:
                        if self._evaluar_prioridad(objetos_map[obj]["vote"], voto_esperado) == 2:
                            obj_elegido, meta_elegida = obj, objetos_map[obj]
                            break

                # Intento 3: Si la superficie no sirve, escarbar buscando un EXACTO profundo
                if not obj_elegido:
                    for obj in resto_profundo:
                        if self._evaluar_prioridad(objetos_map[obj]["vote"], voto_esperado) == 1:
                            obj_elegido, meta_elegida = obj, objetos_map[obj]
                            tqdm.write(f"  [i] Escarbando profundo por voto exacto ({voto_esperado}) en orden {orden}")
                            break

                # Intento 4: Último recurso, buscar un COMODÍN profundo
                if not obj_elegido:
                    for obj in resto_profundo:
                        if self._evaluar_prioridad(objetos_map[obj]["vote"], voto_esperado) == 2:
                            obj_elegido, meta_elegida = obj, objetos_map[obj]
                            tqdm.write(f"  [i] Escarbando profundo por comodín ({voto_esperado}) en orden {orden}")
                            break

                if not obj_elegido:
                    tqdm.write(f"[!] ERROR CRÍTICO: Se agotaron los votos físicos compatibles para el evento #{orden} ({voto_esperado}) en {bandeja_esperada}.")
                    continue

                # Extracción y registro
                pool_disponible.remove(meta_elegida)
                coord_destino = (self.pos_final[0], self.pos_final[1], z_actual)
                self.simulador.extraer_objeto_a_coordenada(obj_elegido, frame_actual, coord_destino)

                meta_final = meta_elegida.copy()
                meta_final.update({"conteo_orden": orden, "conteo_rol": voto_esperado, "conteo_z": round(z_actual, 3)})
                resultados_conteo.append(meta_final)

                z_actual += self.inc_z_apilamiento
                self.simulador.ejecutar_pasos_fisica(frames=self.intervalo_extraccion)
                frame_actual += self.intervalo_extraccion

                pbar.update(1)

        tqdm.write("[SCENE] Vinculación forense completada.")
        return resultados_conteo