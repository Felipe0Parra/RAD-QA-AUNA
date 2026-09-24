from data.ManejoDatos.catphan_TAC.leer_dicom import GeometriaCatphan, DicomVolume
from scipy.signal import find_peaks


def _angulo_efectivo(angulo_nominal, orientacion, roll_deg):
    """D.1 (23-09, PLAN_HANDOFF_IMAGENES_22-09.md): traduce un ángulo NOMINAL
    (definido para el fantoma sin girar, orientación normal) a su posición
    real, dados el giro medido por el motor pylinac (`roll_deg`, en su
    propio marco -- volteado si `orientacion == "invertido"`) y si el
    fantoma está invertido. Fórmula validada empíricamente (giro sintético
    grande + HU real de materiales conocidos de CTP404, la única forma de
    fijar el signo de una composición espejo+giro sin ambigüedad): un
    fantoma invertido se refleja (180 - ángulo) antes de sumar el giro; uno
    normal solo suma el giro. Con orientacion="normal"/roll_deg=0.0 (los
    valores por defecto de D.0) esto es angulo_nominal, sin cambio."""
    if orientacion == "invertido":
        return 180.0 - angulo_nominal + roll_deg
    return angulo_nominal + roll_deg


# ---------------------------------------------- Espesor de corte ----------------------------------------------
# E.1 (PLAN_ESPESOR_CORTE_24-09.md): mismo algoritmo que pylinac 3.45 (CTP404CP504 / ThicknessROI), calculado
# sobre el corte que eligio el fisico y sus dos vecinos. Causa medida del sesgo de +40-60 % y del 11.66 / 17.48:
# la media altura se tomaba contra el 0 que la mascara ponia fuera de la ROI (DIAGNOSTICO_ESPESOR.md).
# --- constantes del metodo (fuente: pylinac 3.45 CTP404CP504 / ThicknessROI) ---
RAMP_ANGLE_RATIO = 0.42           # tan(23 grados) = 0.4245; 0.42 es el del manual Catphan y el de pylinac
ESPESOR_ROI_ANCHO_MM = 10.0       # perpendicular al alambre
ESPESOR_ROI_LARGO_MM = 40.0       # a lo largo del alambre
ESPESOR_ROI_DISTANCIA_MM = 38.0   # del centro del fantoma al centro de la ROI
ESPESOR_SIGMA_FILTRO_PX = 1.0     # gaussiano 2D, pylinac `img.filter(size=1, kind="gaussian")`
ESPESOR_MAX_COMBINAR_MM = 3.5     # pylinac thickness_slice_straddle="auto": combina +-1 corte si nominal < 3.5 mm
# --- guarda de validez (medida en el corpus; NO es un criterio de aceptacion clinico) ---
ESPESOR_MIN_SIGMAS_PICO = 8.0     # prominencia del pico / sigma del ruido, en el corte elegido
                                  # (medido: rampas validas >= 15.4, cortes sin alambre <= 6.0)
ESPESOR_MARGEN_MIN_MM = 3.0       # fondo minimo a cada lado del FWHM dentro de la ROI
ESPESOR_MIN_ENSANCHE = 1.6        # FWHM combinado / FWHM del corte elegido, si se combinan cortes
                                  # (medido: validas 1.78-3.02; solape T/2 1.46-1.54)
ESPESOR_MIN_RAMPAS = 3            # rampas validas necesarias para dar un espesor

_RAMPAS = {"Izquierda": 180.0, "Abajo": 90.0, "Derecha": 0.0, "Arriba": -90.0}


def calcular_fwhm_interpolado(perfil):
    """FWHM del pico principal de `perfil`, a media PROMINENCIA.

    La media altura se mide sobre el fondo LOCAL del pico (el mas alto de los
    dos minimos que lo encierran, definicion de `scipy.signal.peak_widths`, la
    misma que usa pylinac `FWXMProfile`), con cruces interpolados. Antes era
    `(max + min) / 2` del perfil entero, y el minimo era el 0 que la mascara
    ponia fuera de la ROI: el umbral quedaba ~100 HU (TAC/Halcyon) o ~540 HU
    (iX) por debajo del correcto.

    Returns: (fwhm_px, cruce_izq, cruce_der, umbral, prominencia); umbral y
    prominencia en unidades del perfil. Sin pico: (0.0, 0.0, 0.0, None, 0.0).
    """
    import numpy as np
    from scipy.signal import find_peaks
    perfil = np.asarray(perfil, dtype=float)
    picos, props = find_peaks(perfil, rel_height=0.5, width=0, prominence=0)
    if len(picos) == 0:
        return 0.0, 0.0, 0.0, None, 0.0
    k = int(np.argmax(props["prominences"]))
    izq, der = float(props["left_ips"][k]), float(props["right_ips"][k])
    return der - izq, izq, der, float(props["width_heights"][k]), float(props["prominences"][k])


def _sigma_ruido(sub):
    """Desviacion robusta (1.4826*MAD) del recorte tras quitarle un plano
    (el cupping del iX es un gradiente suave). El alambre ocupa pocos
    pixeles del recorte, asi que no pesa en la mediana."""
    import numpy as np
    yy, xx = np.mgrid[0:sub.shape[0], 0:sub.shape[1]]
    a = np.c_[xx.ravel(), yy.ravel(), np.ones(xx.size)]
    coef, *_ = np.linalg.lstsq(a, sub.ravel(), rcond=None)
    res = sub.ravel() - a @ coef
    return float(1.4826 * np.median(np.abs(res - np.median(res))))


def cortes_vecinos_espesor(volumen_hu, indice, espesor_nominal_mm):
    """Los cortes HU a combinar con `volumen_hu[indice]` para medir el espesor:
    uno a cada lado si el espesor nominal es < 3.5 mm (regla de pylinac,
    `thickness_slice_straddle="auto"`); ninguno si es mayor, si no se conoce,
    o si el corte esta en un extremo del volumen. Devuelve una lista (vacia o
    de dos cortes); la pantalla la pasa tal cual a `espesor_corte`."""
    if volumen_hu is None or indice is None or espesor_nominal_mm is None:
        return []
    try:
        nominal = float(espesor_nominal_mm)
    except (TypeError, ValueError):
        return []
    if not (0.0 < nominal < ESPESOR_MAX_COMBINAR_MM):
        return []
    if indice - 1 < 0 or indice + 1 >= len(volumen_hu):
        return []
    return [volumen_hu[indice - 1], volumen_hu[indice + 1]]


def espesor_corte(corte_255, corte_hu, tam_px: float, visualizar: bool = True,
                  combinar_slices: bool = False, slices_adyacentes: list = None, canvas=None) -> dict:
    """Espesor de corte con las 4 rampas de alambre de 23 grados del CTP404.

    Mide SIEMPRE sobre `corte_hu` (HU, float). `corte_255` (8 bits,
    ventaneado) solo se usa para DIBUJAR: el resultado no depende de la
    ventana de visualizacion.

    Args:
        corte_255: imagen 0-255 del corte, solo para dibujar.
        corte_hu: corte en HU (float) -- de aqui sale todo el calculo.
        tam_px: tamano de pixel en mm.
        visualizar: dibuja ROIs y perfiles (en `canvas` si se da).
        combinar_slices / slices_adyacentes: si True y hay vecinos, se promedian
            con el corte (en HU) y el FWHM se divide por el numero de cortes
            (pylinac `thickness_slice_straddle`). Usar `cortes_vecinos_espesor`.

    Returns: dict con espesor_promedio_mm (None si hay menos de
        ESPESOR_MIN_RAMPAS rampas validas), espesores_individuales (solo las
        validas), factor_correccion, num_rampas_detectadas (validas),
        combinacion_slices, imagen_analisis.
    """
    import cv2
    import numpy as np
    from scipy import ndimage

    corte_hu = np.asarray(corte_hu, dtype=np.float32)
    imagen_analisis = corte_hu
    n_cortes = 1
    if combinar_slices and slices_adyacentes:
        pila = [corte_hu] + [np.asarray(s, dtype=np.float32) for s in slices_adyacentes]
        imagen_analisis = np.mean(np.stack(pila), axis=0)   # en HU; nunca a uint8
        n_cortes = len(pila)

    catphan = GeometriaCatphan(corte_hu, tam_px)             # D.0: geometria desde HU
    cx0, cy0 = float(catphan.centro[0]), float(catphan.centro[1])
    dist_px = ESPESOR_ROI_DISTANCIA_MM / tam_px
    corto_px = ESPESOR_ROI_ANCHO_MM / tam_px
    largo_px = ESPESOR_ROI_LARGO_MM / tam_px
    alto_img, ancho_img = imagen_analisis.shape[:2]

    resultados_rampas = {}      # todas las rampas medidas (validas o no), para dibujar
    rectangulos = {}
    for nombre, angulo_nominal in _RAMPAS.items():
        ang = np.deg2rad(angulo_nominal)
        cx = cx0 + dist_px * np.cos(ang)
        cy = cy0 + dist_px * np.sin(ang)
        # recorte alineado a los ejes (como pylinac): las rampas izquierda/derecha
        # corren en vertical, las de arriba/abajo en horizontal
        if nombre in ("Izquierda", "Derecha"):
            w, h = corto_px, largo_px
        else:
            w, h = largo_px, corto_px
        y0, y1 = int(round(cy - h / 2)), int(round(cy + h / 2))
        x0, x1 = int(round(cx - w / 2)), int(round(cx + w / 2))
        rectangulos[nombre] = (x0, y0, x1, y1)
        if x0 < 0 or y0 < 0 or x1 > ancho_img or y1 > alto_img or (x1 - x0) < 2 or (y1 - y0) < 2:
            continue                                         # ROI fuera de la imagen: rampa no medible
        sub = ndimage.gaussian_filter(imagen_analisis[y0:y1, x0:x1].astype(float),
                                      sigma=ESPESOR_SIGMA_FILTRO_PX)
        perfil = sub.max(axis=int(np.argmin(sub.shape)))    # perfil a lo largo del alambre
        fwhm_px, izq, der, umbral, prominencia = calcular_fwhm_interpolado(perfil)
        if umbral is None or fwhm_px <= 0:
            continue
        # (a) hay alambre en el corte ELEGIDO: se juzga sin promediar vecinos
        # (promediar baja el contraste del alambre 3 veces y el criterio pierde margen)
        ensanche = None
        if n_cortes > 1:
            sub_c = ndimage.gaussian_filter(corte_hu[y0:y1, x0:x1].astype(float), sigma=ESPESOR_SIGMA_FILTRO_PX)
            fwhm_c, _, _, _, prominencia_c = calcular_fwhm_interpolado(sub_c.max(axis=int(np.argmin(sub_c.shape))))
            ensanche = fwhm_px / fwhm_c if fwhm_c > 0 else 0.0
        else:
            sub_c, prominencia_c = sub, prominencia
        sigma = _sigma_ruido(sub_c)
        sigmas_pico = prominencia_c / sigma if sigma > 0 else float("inf")
        margen_mm = min(izq, len(perfil) - 1 - der) * tam_px
        valida = (sigmas_pico >= ESPESOR_MIN_SIGMAS_PICO and margen_mm >= ESPESOR_MARGEN_MIN_MM
                  and (ensanche is None or ensanche >= ESPESOR_MIN_ENSANCHE))
        resultados_rampas[nombre] = {
            "fwhm_px": fwhm_px,
            "espesor_mm": fwhm_px * tam_px * RAMP_ANGLE_RATIO / n_cortes,
            "perfil": perfil,
            "indices_fwhm": (izq, der),
            "umbral": umbral,
            "valida": valida,
            "sigmas_pico": sigmas_pico,
            "margen_mm": margen_mm,
            "ensanche": ensanche,
        }

    validas = {n: r for n, r in resultados_rampas.items() if r["valida"]}
    espesores = [r["espesor_mm"] for r in validas.values()]
    espesor_promedio = float(np.mean(espesores)) if len(espesores) >= ESPESOR_MIN_RAMPAS else None

    output_blob = None
    if visualizar:
        output = cv2.cvtColor(corte_255, cv2.COLOR_GRAY2BGR)
        cv2.circle(output, catphan.centro_int, catphan.radio_int, (141, 60, 60), 1)
        for nombre, (x0, y0, x1, y1) in rectangulos.items():
            res = resultados_rampas.get(nombre)
            color = (0, 255, 0) if (res and res["valida"]) else (0, 0, 255)
            cv2.rectangle(output, (x0, y0), (x1, y1), color, 1)
            cv2.putText(output, nombre, (x0, y0 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            texto = f"{res['espesor_mm']:.2f} mm" if (res and res["valida"]) else "no detectada"
            cv2.putText(output, texto, (x0, y1 + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        filas, columnas = 2, 3
        if canvas is not None:
            canvas.figure.clear()
            axs = canvas.figure.subplots(filas, columnas).flatten()
        else:
            import matplotlib.pyplot as plt
            fig, axs = plt.subplots(filas, columnas, figsize=(9, 6))
            axs = axs.flatten()
        axs[0].imshow(output)
        titulo = "ROIs de Espesor de Corte"
        if n_cortes > 1:
            titulo += f" ({n_cortes} cortes)"
        axs[0].set_title(titulo)
        axs[0].axis('off')
        for i, (nombre, res) in enumerate(resultados_rampas.items(), start=1):
            axs[i].plot(res['perfil'], 'b-')
            izq, der = res['indices_fwhm']
            axs[i].axvline(x=izq, color='r', linestyle='--')
            axs[i].axvline(x=der, color='r', linestyle='--')
            axs[i].axhline(y=res['umbral'], color='g', linestyle='--')   # la media altura REAL usada
            axs[i].set_title(f"{nombre}: {res['espesor_mm']:.2f} mm" if res["valida"]
                             else f"{nombre}: rampa no detectada")
            axs[i].grid(True)
        for j in range(1 + len(resultados_rampas), filas * columnas):
            axs[j].axis('off')
        if canvas is not None:
            canvas.figure.tight_layout()
            canvas.draw()
        else:
            import matplotlib.pyplot as plt
            plt.tight_layout()
            plt.show()
        _, buffer = cv2.imencode('.png', output)
        output_blob = buffer.tobytes()

    return {
        "espesor_promedio_mm": round(espesor_promedio, 2) if espesor_promedio else None,
        "espesores_individuales": {n: round(r["espesor_mm"], 2) for n, r in validas.items()},
        "factor_correccion": RAMP_ANGLE_RATIO,
        "num_rampas_detectadas": len(espesores),
        "combinacion_slices": n_cortes > 1,
        "imagen_analisis": output_blob,
    }

# ---------------------------------------------- Tamaño de pixel  ----------------------------------------------

def tamano_pixel(corte_255, corte_hu, tam_px: float, visualizar: bool, canvas = None)  -> dict:
    """
    Calcula el tamaño de pixel estimado usando los centros de los círculos.
    Args:
        corte_255: Imagen 2D (0-255), solo para dibujar.
        corte_hu: Imagen 2D en HU -- de aquí sale la geometría (D.0, 23-09).
        tam_px: Tamaño de píxel en mm.
        visualizar: Si se muestran visualizaciones.
        tolerancia: Diferencia máxima para considerar alineados (en píxeles).
    Returns:
        Dict con tamaños en x/y (mm/pixel).
    """
    import cv2
    import numpy as np

    # Definir ROIs de uniformidad
    tamano_px_rois = {
        "ArrIzq": {"angulo": 135, "distancia": 35, "radio": 3},
        "ArrDer": {"angulo": 45, "distancia": 35, "radio": 3},
        "AbajoIzq": {"angulo": 225, "distancia": 35, "radio": 3},
        "AbajoDer": {"angulo": 315, "distancia": 35, "radio": 3}
    }

    # Obtener geometría del phantom (D.0: desde HU, no desde la ventana)
    catphan = GeometriaCatphan(corte_hu, tam_px)

    # Preparar visualización
    output = cv2.cvtColor(corte_255, cv2.COLOR_GRAY2BGR) if visualizar else None
    
    # Analizar cada ROI

    distancias_x = {'arriba': [], 'abajo': []}
    distancias_y = {'izquierda': [], 'derecha': []}

    centros = []

    for nombre, roi_info in tamano_px_rois.items():
        centro, radio = catphan.posicion_roi(
            roi_info["angulo"], 
            roi_info["distancia"], 
            roi_info["radio"]
        )
        centros.append(centro)

        if visualizar and output is not None:
            cv2.circle(output, centro, radio, (0, 255, 0), 2)
            cv2.putText(output, nombre, (centro[0] - 20, centro[1] - radio - 5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.circle(output, catphan.centro_int, catphan.radio_int, (141, 60, 60), 1)
            cv2.circle(output, catphan.centro_int, catphan.radio_int, (141, 60, 60), 1)
        
        #print(f"Centro {nombre}: {centro}, Radio: {radio}")
    TOL = 5  # píxeles de tolerancia

    for i in range(len(centros)):
        for j in range(i+1, len(centros)):
            if abs(centros[i][0] - centros[j][0]) <= TOL and centros[i][1] != centros[j][1]:
                dist_y = abs(int(centros[i][1]) - int(centros[j][1]))
                if centros[i][1] < centros[j][1]:
                    distancias_x['arriba'].append(dist_y)
                    distancias_x['abajo'].append(dist_y)
                else:
                    distancias_x['abajo'].append(dist_y)
                    distancias_x['arriba'].append(dist_y)

            if abs(centros[i][1] - centros[j][1]) <= TOL and centros[i][0] != centros[j][0]:
                #print("Centros alineados en Y:", centros[i], centros[j])
                dist_x = abs(int(centros[i][0]) - int(centros[j][0]))
                if centros[i][0] < centros[j][0]:
                    distancias_y['izquierda'].append(dist_x)
                    distancias_y['derecha'].append(dist_x)
                else:
                    distancias_y['derecha'].append(dist_x)
                    distancias_y['izquierda'].append(dist_x)
    
    if visualizar and output is not None or canvas is not None:
        if canvas is not None:
            # Usar la figura del canvas existente
            canvas.figure.clear()
            ax = canvas.figure.add_subplot(111)
            ax.imshow(output)
            ax.set_title("Detección de círculos para tamaño de píxel")
            ax.axis('off')
            canvas.draw()
        else:
            # Crear nueva figura solo si no hay canvas
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(6, 6))
            ax.imshow(output)
            ax.set_title("Detección de círculos para tamaño de píxel")
            ax.axis('off')
            plt.show()

        # Convertir output a formato BLOB para devolver
        if output is not None:
            _, buffer = cv2.imencode('.png', output)
            output_blob = buffer.tobytes() # Imagen en formato BLOB
        else:
            output_blob = None

    resultado = {}
    for key in distancias_x:
        if distancias_x[key]:
            resultado['X'] = round(50.1 / np.mean(distancias_x[key]), 3)
    for key in distancias_y:
        if distancias_y[key]:
            resultado['Y'] = round(50.1 / np.mean(distancias_y[key]), 3)
    resultado['imagen_analisis'] = output_blob if visualizar else None # Imagen con ROIs dibujadas en formato BLOB
    return resultado

# ---------------------------------------------- Resolución de contraste ---------------------------------------
# En analisisImagenes/Analisis_Catphan_TAC.py, al inicio del archivo
def resolucion_contraste(corte_255, corte_hu, tam_px: float,
                         catphan=None,
                         visualizar: bool = True,
                         canvas=None,
                         *,
                         cnr_lim: float,
                         visibilidad_lim: float,
                         min_rois_visibles: int,
                         visibilidad_manual: dict | None = None,
                         orientacion: str = "normal",
                         roll_deg: float = 0.0) -> dict:
    """`cnr_lim`, `visibilidad_lim` y `min_rois_visibles` (G.3, 24-09): OBLIGATORIOS y sin valor por defecto. Definen
    qué cuenta como ROI visible en esta métrica y cuántos hacen falta para el `pasa_test_*` heredado; no tienen fuente
    normativa (D-18) y no son el veredicto de la prueba. Viven en un solo sitio,
    `criterios.PARAMETROS_HEREDADOS["resolucion_contraste"]`; ningún literal de umbral se escribe en la pantalla ni aquí.

    `orientacion`/`roll_deg` (D.1, 23-09): del motor pylinac (B.2, plan
    del 18-09) para esta serie. Si `catphan` no se pasa, la instancia que
    esta función construye ya los usa (vía `GeometriaCatphan`, para el ROI
    principal de cada inserto); las 6 ROI de fondo, que se ubican con
    `catphan.posicion_roi(angulo, ...)` y no con `_calcular_roi_float`, se
    corrigen aquí con el mismo ángulo efectivo. Si `catphan` SÍ se pasa
    (desde el posicionador manual), debe haberse construido ya con estos
    mismos `orientacion`/`roll_deg` -- ver `tac_mensual.py`."""
    import cv2
    import numpy as np

    if catphan is None:
        catphan = GeometriaCatphan(corte_hu, tam_px, orientacion=orientacion, roll_deg=roll_deg)  # D.0/D.1

    contraste_rois = catphan.ROI_CONFIG
    roi_dist_mm    = catphan.ROI_DIST_MM
    radio_fondo_mm = 4.0
    factor_fondo   = 0.75

    output = cv2.cvtColor(corte_255, cv2.COLOR_GRAY2BGR) if visualizar else None

    resultados               = {}
    rois_visibles_cnr        = 0
    rois_visibles_visibilidad = 0

    def extraer(centro, radio):
        m = np.zeros(corte_255.shape, np.uint8)
        cv2.circle(m, centro, radio, 1, -1)
        v = corte_hu[m == 1]
        return v if len(v) > 0 else None
    def _roi_es_valido(centro_roi, centro_phantom, radio_phantom, radio_roi):
        dist = np.hypot(
            centro_roi[0] - centro_phantom[0],
            centro_roi[1] - centro_phantom[1]
        )
        # El ROI debe estar completamente dentro del phantom
        return (dist + radio_roi) < radio_phantom * 0.95
    def _roi_es_homogeneo(v_roi, fondo_std, factor=1.8):
        """El interior del ROI no debe ser más ruidoso que el fondo * factor."""
        if v_roi is None or len(v_roi) < 4:
            return False
        return float(np.std(v_roi)) < fondo_std * factor

    for nombre, roi_info in contraste_rois.items():
        # D.1: las ROI de fondo se ubican con posicion_roi(angulo,...), que
        # no pasa por _calcular_roi_float -- necesitan el mismo ángulo
        # efectivo que ya usa catphan.obtener_roi(nombre) para el inserto.
        angulo      = _angulo_efectivo(roi_info["angulo"], orientacion, roll_deg)
        radio_mm    = roi_info["radio_mm"]
        diametro_mm = roi_info["diametro_mm"]

        # ── ROIs de fondo ────────────────────────────────────────────────────
        dist_int_mm = roi_dist_mm * factor_fondo           # 37.5 mm
        dist_ext_mm = roi_dist_mm * (2.0 - factor_fondo)  # 62.5 mm

        centro_int, radio_fondo_px = catphan.posicion_roi(angulo, dist_int_mm, radio_fondo_mm)
        centro_ext, _              = catphan.posicion_roi(angulo, dist_ext_mm, radio_fondo_mm)

        v_int = extraer(centro_int, radio_fondo_px)
        v_ext = extraer(centro_ext, radio_fondo_px)

        if v_int is not None and v_ext is not None:
            fondo_val = float(np.mean([np.mean(v_int), np.mean(v_ext)]))
            fondo_std = float(max(np.std(v_int), np.std(v_ext)))
        elif v_ext is not None:
            fondo_val = float(np.mean(v_ext))
            fondo_std = float(np.std(v_ext))
        elif v_int is not None:
            fondo_val = float(np.mean(v_int))
            fondo_std = float(np.std(v_int))
        else:
            fondo_val, fondo_std = 0.0, 1.0

        # ── ROI principal ────────────────────────────────────────────────────
        centro_roi,  radio_roi_px = catphan.obtener_roi(nombre)
        (_, __),     radio_roi_f  = catphan.obtener_roi_float(nombre)
        
        radio_medicion = max(2, int(radio_roi_px * 0.7))

        v_roi = extraer(centro_roi, radio_medicion)

        
        if v_roi is None or not _roi_es_valido(centro_roi, catphan.centro_int, catphan.radio_int, radio_roi_px):
            roi_prom = roi_std = contraste_michelson = None
            diferencia_hu = cnr = snr = visibilidad = area_px = None
            pasa_cnr = pasa_vis = False

        else:
            roi_prom = float(np.mean(v_roi))
            roi_std  = float(np.std(v_roi))

            suma                = roi_prom + fondo_val
            contraste_michelson = abs(roi_prom - fondo_val) / suma \
                                if suma != 0 else 0.0
            diferencia_hu       = abs(roi_prom - fondo_val)
            cnr                 = diferencia_hu / fondo_std \
                                if fondo_std > 0 else 0.0
            snr                 = roi_prom / roi_std \
                                if roi_std > 0 else 0.0
            area_px             = np.pi * radio_roi_f ** 2
            visibilidad         = contraste_michelson * np.sqrt(area_px) / fondo_std \
                                if fondo_std > 0 else 0.0

            pasa_cnr = cnr >= cnr_lim
            pasa_vis = visibilidad >= visibilidad_lim

            # Juicio manual (OR con cálculo)
            if visibilidad_manual is not None:
                manual_para_este_roi = visibilidad_manual.get(nombre, None)
                if manual_para_este_roi is not None:
                    # El usuario se pronunció explícitamente: su juicio manda
                    pasa_vis_final = manual_para_este_roi
                    criterio = "manual"
                else:
                    # El usuario no tocó este ROI: cálculo manda
                    pasa_vis_final = pasa_vis
                    criterio = "calculo" if pasa_vis else "ninguno"
            else:
                manual_para_este_roi = None
                pasa_vis_final = pasa_vis
                criterio = "calculo" if pasa_vis else "ninguno"

            pasa_cnr_final = pasa_cnr  # CNR nunca lo toca el usuario

            if pasa_cnr_final: rois_visibles_cnr        += 1
            if pasa_vis_final: rois_visibles_visibilidad += 1

        resultados[nombre] = {
            "centro_roi":          centro_roi,
            "diametro_mm":         diametro_mm,
            "radio_mm":            radio_mm,
            "radio_px":            radio_roi_px,
            "roi_prom":            round(roi_prom,            2) if roi_prom            is not None else None,
            "roi_std":             round(roi_std,             2) if roi_std             is not None else None,
            "background_prom":     round(fondo_val,           2),
            "background_std":      round(fondo_std,           2),
            "diferencia_hu":       round(diferencia_hu,       2) if diferencia_hu       is not None else None,
            "contraste_michelson": round(contraste_michelson, 4) if contraste_michelson is not None else None,
            "cnr":                 round(cnr,                 2) if cnr                 is not None else None,
            "snr":                 round(snr,                 2) if snr                 is not None else None,
            "visibilidad":         round(visibilidad,         4) if visibilidad         is not None else None,
            "visibilidad_lim":     round(visibilidad,         4) if visibilidad         is not None else None,  # alias para compatibilidad
            "area_px":             round(area_px,             1) if area_px             is not None else None,
            "pasa_visibilidad":     pasa_vis_final,
            "pasa_visibilidad_lim": pasa_vis_final,
            "pasa_cnr":             pasa_cnr_final,
            "visible_manual":       manual_para_este_roi,
            "criterio_visibilidad": criterio,
            "centro_fondo_int":    centro_int,
            "centro_fondo_ext":    centro_ext,
        }

        if visualizar and output is not None:
            color = (0, 255, 0) if pasa_vis_final else (0, 0, 255)
            cv2.circle(output, centro_roi,         radio_roi_px,   color,          1)
            cv2.circle(output, centro_int,         radio_fondo_px, (255, 255, 0),  1)
            cv2.circle(output, centro_ext,         radio_fondo_px, (255, 255, 0),  1)
            cv2.circle(output, catphan.centro_int, catphan.radio_int, (141, 60, 60), 1)

    # ── Resumen ───────────────────────────────────────────────────────────────
    resumen = {
        "rois_visibles_cnr":         rois_visibles_cnr,
        "rois_visibles_visibilidad": rois_visibles_visibilidad,
        "total_rois":                len(contraste_rois),
        "cnr_lim":                   cnr_lim,
        "visibilidad_lim":           visibilidad_lim,   # ← parámetro, no variable de loop
        "min_rois_visibles":         min_rois_visibles,
        "pasa_test_cnr":             rois_visibles_cnr         >= min_rois_visibles,
        "pasa_test_visibilidad":     rois_visibles_visibilidad >= min_rois_visibles,
    }

    # ── Visualización ─────────────────────────────────────────────────────────
    if visualizar and output is not None:
        titulo_base = (                             # ← definido ANTES del if/else
            f"Análisis Contraste Bajo CTP515\n"
            f"CNR≥{cnr_lim}: {rois_visibles_cnr}/{len(contraste_rois)}  |  "
            f"Visibilidad≥{visibilidad_lim}: {rois_visibles_visibilidad}/{len(contraste_rois)}"
        )

        if canvas is not None:
            from PyQt5.QtCore import Qt
            canvas.figure.clear()
            ax = canvas.figure.add_subplot(111)

            estado       = {"original": False}
            original_rgb = corte_255
            anotado_rgb  = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)

            img_obj = ax.imshow(anotado_rgb)
            ax.set_title(titulo_base, fontsize=9)
            ax.axis("off")
            canvas.draw()

            def on_key(event):
                if event.key != " ":
                    return
                estado["original"] = not estado["original"]
                if estado["original"]:
                    img_obj.set_data(original_rgb)
                    img_obj.set_cmap("gray")
                    ax.set_title("Original  [ESPACIO = volver]")
                else:
                    img_obj.set_data(anotado_rgb)
                    img_obj.set_cmap(None)
                    ax.set_title(titulo_base)
                canvas.draw_idle()

            canvas.mpl_connect("key_press_event", on_key)
            canvas.setFocusPolicy(Qt.StrongFocus)
            canvas.setFocus()

        else:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(10, 8))
            ax.imshow(cv2.cvtColor(output, cv2.COLOR_BGR2RGB))
            ax.set_title(titulo_base)
            ax.axis("off")
            plt.show()

        _, buf = cv2.imencode(".png", output)
        resumen["imagen_analisis"] = buf.tobytes()

    return {"resultados_roi": resultados, "resumen": resumen}
def imprimir_resultados_contraste_bajo(resultados):
    """Imprime los resultados del análisis de contraste bajo en formato tabla"""
    print("\n" + "="*130)
    print("                                    ANÁLISIS DE CONTRASTE BAJO (CTP515)")
    print("="*130)
    print("NOTA: CNR = |HU_roi - HU_fondo|/std(ROI)  |  Visibilidad = Contraste*sqrt(área)/std(ROI)")
    print("="*130)
    print("| ROI  | Diám. | Centro (x,y)  |  ROI HU  | ROI std | Fondo HU | Fnd std | Δ HU | Contr. | CNR  |  SNR  | Visib. | CNR✓ | Vis✓ |")
    print("|------|-------|---------------|----------|---------|----------|---------|------|--------|------|-------|--------|------|------|")
    
    for nombre, res in resultados["resultados_roi"].items():
        centro_str = f"({res['centro_roi'][0]},{res['centro_roi'][1]})"
        roi_hu = f"{res['roi_prom']:.1f}" if res['roi_prom'] is not None else "N/A"
        roi_std = f"{res['roi_std']:.1f}" if res['roi_std'] is not None else "N/A"
        fondo_hu = f"{res['background_prom']:.1f}"
        fondo_std = f"{res['background_std']:.1f}"
        delta_hu = f"{res['diferencia_hu']:.1f}" if res['diferencia_hu'] is not None else "N/A"
        contraste = f"{res['contraste_michelson']:.4f}" if res['contraste_michelson'] is not None else "N/A"
        cnr = f"{res['cnr']:.2f}" if res['cnr'] is not None else "N/A"
        snr = f"{res['snr']:.1f}" if res['snr'] is not None else "N/A"
        visib = f"{res['visibilidad']:.3f}" if res['visibilidad'] is not None else "N/A"
        cnr_pass = "✓" if res['pasa_cnr'] else "✗"
        vis_pass = "✓" if res['pasa_visibilidad'] else "✗"
        
        print(  f"| {nombre:^4} | {res['diametro_mm']:^5} | {centro_str:^13} | {roi_hu:^8} | {roi_std:^7} | "
                f"{fondo_hu:^8} | {fondo_std:^7} | {delta_hu:^4} | {contraste:^6} | {cnr:^4} | {snr:^5} | {visib:^6} | {cnr_pass:^4} | {vis_pass:^4} |")
    
    print("="*130)
    resumen = resultados["resumen"]
    print(  f"ROIs visibles (CNR ≥ {resumen['cnr_lim']}): {resumen['rois_visibles_cnr']}/{resumen['total_rois']} | "
            f"Pasa test: {'✓' if resumen['pasa_test_cnr'] else '✗'}")
    print(  f"ROIs visibles (visibilidad ≥ {resumen['visibilidad_lim']}): {resumen['rois_visibles_visibilidad']}/{resumen['total_rois']} | "
            f"Pasa test: {'✓' if resumen['pasa_test_visibilidad'] else '✗'} ← Método recomendado por pylinac")
    print("="*130)

# ---------------------------------------------- Resolución espacial -------------------------------------------

def resolucion_espacial(corte, corte_hu, tam_px: float, visualizar=True, canvas=None,
                        orientacion: str = "normal", roll_deg: float = 0.0) -> dict:
    """
    Analiza la resolución espacial mediante el cálculo del MTF.
    Usa boundaries en orden descendente (segmentos: start > end).

    `corte_hu` (D.0, 23-09): la geometría (dónde caen las 8 regiones del
    anillo) y, desde B.1 (23-09), también los VALORES del perfil
    (`values_sorted` más abajo) salen de aquí -- antes se leían de
    `corte` (la imagen ventaneada de 8 bits), así que el MTF salía de
    datos saturados por la ventana de visualización (§0.5 del plan: esta
    función era la única de las seis que medía así). `corte` sigue
    yendo solo al dibujo del anillo.

    B.1 (23-09): las regiones por encima del límite de Nyquist del
    píxel (`1/(2·tam_px_cm)`) no se intentan analizar -- cualquier "pico"
    ahí sería aliasing, no resolución real -- y su estado pasa a decir
    "Fuera del límite de muestreo", no "Picos insuficientes" (que sugiere
    un fallo del análisis en vez de un límite físico de la adquisición).

    `orientacion`/`roll_deg` (D.1, 23-09): del motor pylinac para esta
    serie. `boundaries` son fracciones fijas del círculo completo,
    definidas para el fantoma SIN girar en orientación normal -- el
    ángulo de cada punto de muestra se traduce a ese mismo marco NOMINAL
    antes de compararlo contra `boundaries` (es la transformación
    INVERSA de la que usa `_angulo_efectivo`: aquí se parte de dónde
    ESTÁ la muestra y se pregunta qué región nominal le corresponde).
    """
    import cv2
    import numpy as np

    catphan = GeometriaCatphan(corte_hu, tam_px)  # D.0: geometría desde HU

    # Boundaries descendentes (norm_angle 0..1)
    boundaries = (0.470, 0.382, 0.320, 0.260, 0.220, 0.160, 0.120, 0.060, 0.020)
    roi_settings = {
        "region 1": {"start": boundaries[0], "end": boundaries[1], "num_peaks": 2, "num_valleys": 1, "peak_spacing": 0.021,    "lp/cm": 1},
        "region 2": {"start": boundaries[1], "end": boundaries[2], "num_peaks": 3, "num_valleys": 2, "peak_spacing": 0.010,    "lp/cm": 2},
        "region 3": {"start": boundaries[2], "end": boundaries[3], "num_peaks": 4, "num_valleys": 3, "peak_spacing": 0.006,    "lp/cm": 3},
        "region 4": {"start": boundaries[3], "end": boundaries[4], "num_peaks": 4, "num_valleys": 3, "peak_spacing": 0.00557,  "lp/cm": 4},
        "region 5": {"start": boundaries[4], "end": boundaries[5], "num_peaks": 4, "num_valleys": 3, "peak_spacing": 0.004777, "lp/cm": 5},
        "region 6": {"start": boundaries[5], "end": boundaries[6], "num_peaks": 5, "num_valleys": 4, "peak_spacing": 0.00398,  "lp/cm": 6},
        "region 7": {"start": boundaries[6], "end": boundaries[7], "num_peaks": 5, "num_valleys": 4, "peak_spacing": 0.00358,  "lp/cm": 7},
        "region 8": {"start": boundaries[7], "end": boundaries[8], "num_peaks": 5, "num_valleys": 4, "peak_spacing": 0.0027866,"lp/cm": 8},
    }

    radio_anillo_mm = 48
    radio_px = int(radio_anillo_mm / tam_px)

    h, w = corte.shape
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt((X - catphan.centro[0])**2 + (Y - catphan.centro[1])**2)

    ancho = 0.04 * radio_px
    mask = (dist >= radio_px - ancho/2) & (dist <= radio_px + ancho/2)

    ys, xs = np.where(mask)
    angles_deg = np.degrees(np.arctan2(ys - catphan.centro[1], xs - catphan.centro[0]))
    # D.1: angulo MEDIDO -> angulo NOMINAL equivalente (inversa de
    # _angulo_efectivo), para que `boundaries` (definido sin giro, sin
    # invertir) siga delimitando las regiones correctas.
    if orientacion == "invertido":
        angles_deg = 180.0 - angles_deg + roll_deg
    else:
        angles_deg = angles_deg - roll_deg
    angles = np.radians(np.mod(angles_deg, 360.0))
    idx = np.argsort(angles)
    angles_sorted = angles[idx]
    values_sorted = corte_hu[ys[idx], xs[idx]]  # B.1: valores desde HU, no desde la ventana
    norm_angles = angles_sorted / (2*np.pi)

    # B.1 (23-09): límite de Nyquist del propio píxel -- un hecho físico de
    # la adquisición, no un umbral de la app. tam_px está en mm; 1 lp/cm
    # necesita el tamaño de píxel en cm.
    nyquist_lp_cm = 1.0 / (2.0 * (tam_px / 10.0))

    from scipy.ndimage import gaussian_filter1d
    values_filtered = gaussian_filter1d(values_sorted, sigma=1)
    values_ground = values_filtered - np.min(values_filtered)

    maxs = []
    mins = []
    region_results = {}
    region_order = []
    all_peak_values_concat = []
    import numpy as np
    

    for key, region in roi_settings.items():
        # start > end (intervalo descendente), pero la array está ascendente;
        # usamos searchsorted(end) -> searchsorted(start) y tomamos slice [lo:hi]
        start_norm = region["start"]
        end_norm = region["end"]
        if start_norm <= end_norm:
            region_results[key] = {"status": "Intervalo inválido (start<=end)"}
            continue

        # B.1 (23-09): por encima de Nyquist, cualquier "pico" sería
        # aliasing -- se declara el límite físico, no se intenta medir.
        if region["lp/cm"] > nyquist_lp_cm:
            region_results[key] = {
                "lp/cm": region["lp/cm"],
                "status": f"Fuera del límite de muestreo ({nyquist_lp_cm:.2f} lp/cm con este píxel)",
            }
            continue

        start_idx = np.searchsorted(norm_angles, end_norm, side="left")
        end_idx = np.searchsorted(norm_angles, start_norm, side="left")

        if end_idx - start_idx < 8:
            region_results[key] = {"status": "Región muy pequeña", "lp/cm": region["lp/cm"]}
            continue

        region_values = values_ground[start_idx:end_idx]

        # Distancia mínima entre picos
        global_profile_len = len(values_ground)
        min_distance = max(1, int(global_profile_len * region["peak_spacing"]))
        local_range = np.ptp(region_values)
        prom_min = max(0.05 * local_range, 1e-6)

        peak_indices, props = find_peaks(region_values, distance=min_distance, prominence=prom_min)

        # Mantener sólo los más prominentes si sobran
        if len(peak_indices) > region["num_peaks"]:
            order = np.argsort(props["prominences"])[-region["num_peaks"]:]
            peak_indices = np.sort(peak_indices[order])

        if len(peak_indices) < region["num_peaks"]:
            region_results[key] = {
                "lp/cm": region["lp/cm"],
                "found_peaks": int(len(peak_indices)),
                "expected_peaks": region["num_peaks"],
                "status": "Picos insuficientes"
            }
            continue

        global_peak_indices = start_idx + peak_indices
        peak_values = values_ground[global_peak_indices]

        # Valles entre picos
        valley_indices = []
        for i in range(len(global_peak_indices) - 1):
            a = global_peak_indices[i]
            b = global_peak_indices[i+1]
            if b - a < 2:
                continue
            valley_idx = a + np.argmin(values_ground[a:b])
            valley_indices.append(valley_idx)

        if len(valley_indices) < region["num_valleys"]:
            region_results[key] = {
                "lp/cm": region["lp/cm"],
                "found_valleys": int(len(valley_indices)),
                "expected_valleys": region["num_valleys"],
                "status": "Valles insuficientes"
            }
            continue

        valley_values = values_ground[valley_indices]

        maxs.append(float(np.mean(peak_values)))
        mins.append(float(np.mean(valley_values)))
        region_order.append(key)
        all_peak_values_concat.extend(peak_values.tolist())

        # Calcular gap_size en cm
        gap_size_cm = 1 / (region["lp/cm"]) / 2

        region_results[key] = {
            "lp/cm": region["lp/cm"],
            "peak_mean": round(float(np.mean(peak_values)), 3) if len(peak_values) > 0 else None,
            "valley_mean": round(float(np.mean(valley_values)), 3) if len(valley_values) > 0 else None,
            "n_peaks_used": int(len(peak_indices)),
            "n_valleys_used": int(len(valley_indices)),
            "gap_size_cm": round(gap_size_cm, 3),
            "status": "OK"
        }
        # import matplotlib.pyplot as plt
        # plt.figure(figsize=(10,3))
        # plt.plot(region_values)

        # plt.plot(
        #     peak_indices,
        #     region_values[peak_indices],
        #     'ro'
        # )

        # plt.title(f"{key}")
        # plt.grid(True)
        # plt.show()

    # Calcular MTF normalizada
    for key, res in region_results.items():
        print(f"{key}: {res.get('status')} | peaks: {res.get('found_peaks', res.get('n_peaks_used', '?'))}")
    mtf_values = {}
    if maxs and mins:
        ref = None
        for i, (mx, mn) in enumerate(zip(maxs, mins)):
            if mx <= mn:
                continue
            mod = (mx - mn) / (mx + mn)
            if ref is None:
                ref = mod
            else:
                lp_val = roi_settings[region_order[i]]["lp/cm"]
                mtf_values[f"{lp_val:.1f}"] = mod / ref if ref > 0 else 0.0

    # Interpolación MTF %
    mtf_lp_mm = {}
    if len(mtf_values) >= 2:
        spacings = sorted([(round(float(k), 3), v) for k, v in mtf_values.items()])
        x = [s[0] for s in spacings]
        y = [s[1] for s in spacings]
        from scipy.interpolate import interp1d
        f = interp1d(y, x, bounds_error=False, fill_value="extrapolate")
        for pct in (10, 20, 30, 40, 50):
            target = pct / 100
            if min(y) <= target <= max(y):
                mtf_lp_mm[str(pct)] = float(f(target))

    # Visualización
    if visualizar and corte is not None or canvas is not None:
        if canvas is not None:
            # Usar la figura del canvas existente
            canvas.figure.clear()
            # Imagen + anillo
            ax1 = canvas.figure.add_subplot(1, 2, 1)
            ax1.imshow(corte, cmap="gray")
            ax1.contour(mask, colors='r', linewidths=0.4)
            ax1.set_title("Anillo resolución")
            ax1.axis("off")
            
            # MTF
            if mtf_values:
                ax4 = canvas.figure.add_subplot(1, 2, 2)
                xs = [float(k) for k in mtf_values.keys()]
                ys = list(mtf_values.values())
                ax4.plot(xs, ys, 'o-')
                for pct, val in mtf_lp_mm.items():
                    ax4.plot(val, int(pct)/100, 'rx')
                    ax4.text(val, int(pct)/100, f"{pct}% {val:.2f}", fontsize=8)
                ax4.set_ylim(0, 1.05); ax4.grid(True)
                ax4.set_xlabel("lp/cm"); ax4.set_ylabel("MTF")
                ax4.set_title("MTF normalizada")
            
            
            canvas.figure.tight_layout()
            canvas.draw()
            
            # Convertir figura a formato BLOB para devolver
            import io
            buf = io.BytesIO()
            canvas.figure.savefig(buf, format='png')
            buf.seek(0)
            output_blob = buf.getvalue()  # Imagen en formato BLOB
            buf.close()
        else:
            # Crear nueva figura solo si no hay canvas
            import matplotlib.pyplot as plt
            fig = plt.figure(figsize=(8, 5))
            # Imagen + anillo
            ax1 = fig.add_subplot(1, 2, 1) 
            ax1.imshow(corte, cmap="gray")
            ax1.contour(mask, colors='r', linewidths=0.4)
            ax1.set_title("Anillo resolución")
            ax1.axis("off")
            
            # MTF
            if mtf_values:
                ax4 = fig.add_subplot(1, 2, 2)
                xs = [float(k) for k in mtf_values.keys()]
                ys = list(mtf_values.values())
                ax4.plot(xs, ys, 'o-')
                for pct, val in mtf_lp_mm.items():
                    ax4.plot(val, int(pct)/100, 'rx')
                    ax4.text(val, int(pct)/100, f"{pct}% {val:.2f}", fontsize=8)
                ax4.set_ylim(0, 1.05); ax4.grid(True)
                ax4.set_xlabel("lp/cm"); ax4.set_ylabel("MTF")
                ax4.set_title("MTF normalizada")
            
            fig.tight_layout()
            plt.show()

            # Convertir figura a formato BLOB para devolver
            import io
            buf = io.BytesIO()
            fig.savefig(buf, format='png')
            buf.seek(0)
            output_blob = buf.getvalue()  # Imagen en formato BLOB
            buf.close()

    # Encontrar la última región que pasó el análisis (con mayor lp/mm)
    ultima_region_ok = None
    max_lp_mm = -1

    for region_name, result in region_results.items():
        if result.get("status") == "OK":
            lp_mm = result.get("lp/cm", 0)
            if lp_mm > max_lp_mm:
                max_lp_mm = lp_mm
                ultima_region_ok = region_name

    # Información sobre resolución límite
    resolucion_limite = {
        "ultima_region": ultima_region_ok,
        "lp_mm_maximo": max_lp_mm
    }

    if ultima_region_ok:
        resolucion_limite["gap_size_cm"] = region_results[ultima_region_ok]["gap_size_cm"]

    total_peaks = sum(
        r.get("n_peaks_used", 0) for r in region_results.values() if r.get("status") == "OK"
    )
    
    

    return {
        "region_results": region_results,
        "mtf_values": mtf_values,
        "mtf_lp_mm": mtf_lp_mm,
        "num_picos": total_peaks,
        "valores_picos": [round(v, 2) for v in all_peak_values_concat],
        "resolucion_limite": resolucion_limite,
        "imagen_analisis": output_blob if visualizar else None
    }

def mostrar_regiones_anillo(corte, corte_hu, tam_px: float, boundaries=None, roi_settings=None,
        radio_mm=47, ancho_rel=0.08, angle_offset_deg=0, visualizar=True, return_data=True,
        invertir_config_en_mismo_lugar=False, invertir_posicion=False):
    """
    Visualiza las regiones del anillo. Usa los mismos flags de inversión que construir_roi_settings.

    `corte_hu` (D.0, 23-09): geometría desde HU, no desde la ventana.
    """
    import cv2
    import numpy as np

    geo = GeometriaCatphan(corte_hu, tam_px)  # D.0: geometría desde HU
    cx, cy = int(geo.centro[0]), int(geo.centro[1])
    radio_px = int(radio_mm / tam_px)
    h, w = corte.shape

    # 2. Definición de regiones de pares de líneas (basado en CTP528CP504)
    #boundaries = (0, 0.107, 0.173, 0.236, 0.286, 0.335, 0.387, 0.434, 0.479)

    #boundaries = (0.479, 0.372, 0.306, 0.233, 0.183, 0.134, 0.082, 0.035, 0)
    boundaries = (0.470, 0.382, 0.320, 0.260, 0.220, 0.160, 0.120, 0.060, 0.020)
    roi_settings = {
        "region 1": {"start": boundaries[0], "end": boundaries[1], "num_peaks": 2, "num_valleys": 1, "peak_spacing": 0.021, "lp/mm": 0.1},
        "region 2": {"start": boundaries[1], "end": boundaries[2], "num_peaks": 3, "num_valleys": 2, "peak_spacing": 0.01, "lp/mm": 0.2},
        "region 3": {"start": boundaries[2], "end": boundaries[3], "num_peaks": 4, "num_valleys": 3, "peak_spacing": 0.006, "lp/mm": 0.3},
        "region 4": {"start": boundaries[3], "end": boundaries[4], "num_peaks": 4, "num_valleys": 3, "peak_spacing": 0.00557, "lp/mm": 0.4},
        "region 5": {"start": boundaries[4], "end": boundaries[5], "num_peaks": 4, "num_valleys": 3, "peak_spacing": 0.004777, "lp/mm": 0.5},
        "region 6": {"start": boundaries[5], "end": boundaries[6], "num_peaks": 5, "num_valleys": 4, "peak_spacing": 0.00398, "lp/mm": 0.6},
        "region 7": {"start": boundaries[6], "end": boundaries[7], "num_peaks": 5, "num_valleys": 4, "peak_spacing": 0.00358, "lp/mm": 0.7},
        "region 8": {"start": boundaries[7], "end": boundaries[8], "num_peaks": 5, "num_valleys": 4, "peak_spacing": 0.0027866, "lp/mm": 0.8},
    }

    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt((X - cx)**2 + (Y - cy)**2)
    ancho = ancho_rel * radio_px
    mask = (dist >= radio_px - ancho/2) & (dist <= radio_px + ancho/2)

    ys, xs = np.where(mask)
    ang = np.arctan2(ys - cy, xs - cx)
    ang = np.mod(ang, 2*np.pi)

    angle_offset = np.deg2rad(angle_offset_deg)
    ang_offset = np.mod(ang - angle_offset, 2*np.pi)
    idx = np.argsort(ang_offset)
    norm_angles = ang_offset[idx] / (2*np.pi)

    overlay = cv2.cvtColor(corte, cv2.COLOR_GRAY2BGR)
    cv2.circle(overlay, (cx, cy), radio_px, (255, 255, 0), 1)

    for b in boundaries:
        theta = (b * 2*np.pi + angle_offset)
        x2 = int(cx + radio_px * np.cos(theta))
        y2 = int(cy + radio_px * np.sin(theta))
        cv2.line(overlay, (cx, cy), (x2, y2), (0, 255, 255), 1)

    bounding_boxes = {}
    font = cv2.FONT_HERSHEY_SIMPLEX
    for key, reg in roi_settings.items():
        s = reg["end"]; e = reg["start"]
        sel = (norm_angles >= s) & (norm_angles < e)
        if not np.any(sel):
            continue
        xs_r = xs[idx][sel]; ys_r = ys[idx][sel]
        x_min, x_max = int(xs_r.min()), int(xs_r.max())
        y_min, y_max = int(ys_r.min()), int(ys_r.max())
        bounding_boxes[key] = {
            "bbox": (x_min, y_min, x_max, y_max),
            "lp/mm": reg["lp/mm"],
            "start_norm": s,
            "end_norm": e
        }
        cv2.rectangle(overlay, (x_min, y_min), (x_max, y_max), (0,0,255),1)
        cv2.putText(overlay, f"{key} ({reg['lp/mm']})", (x_min, max(10, y_min-5)),
                    font, 0.45, (0,0,255), 1, cv2.LINE_AA)

    if visualizar:
        cv2.imshow(f"Regiones Resolución (offset={angle_offset_deg}°)", overlay)
        cv2.waitKey(0); cv2.destroyAllWindows()

    if return_data:
        return {
            "centro": (cx, cy),
            "radio_px": radio_px,
            "bounding_boxes": bounding_boxes,
            "angle_offset_deg": angle_offset_deg,
            "invertir_config_en_mismo_lugar": invertir_config_en_mismo_lugar,
            "invertir_posicion": invertir_posicion
        }

# ---------------------------------------------- Prueba Valor del Número CT ------------------------------------

def valor_numero_ct(corte_255, corte_hu,tam_px, catphan=None,visualizar=True, canvas=None) -> list:
    """
    Calcula el promedio HU y errores para cada ROI.
    Args:
        corte: Imagen 2D (HU).
        rois: Lista [(centro, radio), ...].
        materiales_dic: Lista de dicts con info de materiales.
    Returns:
        Lista de dicts con resultados por ROI.
    """
    import cv2
    import numpy as np
    
    # Posicion relativa real en mm de los ROIs en Catphan
    

    catphan_rois = {
        "Teflon":       {"angulo": 300, "distancia": 59, "radio": 5, "valor_hu": (941, 1060)},
        "Delrin":       {"angulo": 0,   "distancia": 58, "radio": 5, "valor_hu": (344, 387)},
        "Acrilico":     {"angulo": 60,  "distancia": 58, "radio": 5, "valor_hu": (92, 137)},
        "Poliestireno": {"angulo": 120, "distancia": 59, "radio": 5, "valor_hu": (-65, -29)},
        "LDPE":         {"angulo": 180, "distancia": 59, "radio": 5, "valor_hu": (-121, -87)},
        "PMP":          {"angulo": 240, "distancia": 58, "radio": 5, "valor_hu": (-220, -172)},
        "Aire":         {"angulo": 270, "distancia": 58, "radio": 6, "valor_hu": (-1046, -986)}
    }

    # 1. Preparar detectar geometría (rois)
    from data.ManejoDatos.catphan_TAC.posicionador_manual import GeometriaCatphanCT
    if catphan is None:
        catphan = GeometriaCatphanCT(corte_hu, tam_px)  # D.0: geometría desde HU
    resultados = []    
    output = cv2.cvtColor(corte_255, cv2.COLOR_GRAY2BGR) if visualizar else None
    # 2. Analizar cada ROI definido
    for material, roi_info in catphan_rois.items():
        centro, radio = catphan.posicion_roi(
            roi_info["angulo"], 
            roi_info["distancia"], 
            roi_info["radio"]
        )
        mask = np.zeros(corte_hu.shape, dtype=np.uint8)
        area_int =int(radio * 0.8) # 70% del radio para evitar bordes
        cv2.circle(mask, centro, area_int, 1, -1)
        valores = corte_hu[mask == 1]

        # Calcular estadísticas
        if len(valores) > 0:
            promedio = float(np.mean(valores))
            std = float(np.std(valores))
            
            # Calcular errores
            error_abs, error_rel = error_valores_ct(promedio, roi_info)
        else:
            promedio = None
            std = None
            error_abs = None
            error_rel = None

        # 3. Guardar resultado
        resultados.append({
            "centro": centro, 
            "material": material,
            "promedio_hu": round(promedio, 3) if promedio is not None else None,
            "std_hu": round(std, 3) if std is not None else None,
            "rango_hu": roi_info["valor_hu"],
            "error_abs": error_abs,
            "error_rel": error_rel,
        })
        # Visualización
        if visualizar and output is not None:
            color = (0, 255, 0) if error_abs and error_abs <= 20 else (0, 0, 255)
            cv2.circle(output, centro, radio, color, 2)
            cv2.circle(output, centro, area_int, (255, 255, 0), 1)
            cv2.putText(output, material, (centro[0] - 30, centro[1] - radio - 5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            if promedio:
                cv2.putText(output, f"{promedio:.1f}", (centro[0] - 30, centro[1] + 35), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
            cv2.circle(output, catphan.centro_int, catphan.radio_int, (141, 60, 60), 1)
            #cv2.circle(output, catphan.centro_int, catphan.radio_int, (141, 60, 60), 1)

    # Mostrar resultado visual
    if visualizar and output is not None or canvas is not None:
        # Asegúrate que output es un array válido
        if output is not None:
            output = np.array(output, dtype=np.uint8)
            
            if canvas is not None:
                # Usar la figura del canvas existente
                canvas.figure.clear()
                ax = canvas.figure.add_subplot(111)
                ax.imshow(output)
                ax.set_title("Valores del Número CT")
                ax.axis('off')
                canvas.draw()
            else:
                # Crear nueva figura solo si no hay canvas
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(6, 6))
                ax.imshow(output)
                ax.set_title("Valores del Número CT")
                ax.axis('off')
                plt.show()
            
            # Convertir output a formato BLOB para devolver
            _, buffer = cv2.imencode('.png', output)
            output_blob = buffer.tobytes() # Imagen en formato BLOB
        else:
            output_blob = None
        
    # Agregar la imagen de análisis como metadatos en el último elemento
    resultado_final = resultados.copy()  # Copia la lista de resultados
    
    # Agregar metadatos como un elemento especial al final
    if visualizar and output_blob:
        resultado_final.append({
            "imagen_analisis": output_blob if visualizar else None
        }) 
    
    return resultado_final

def error_valores_ct(valor_hu: float, material_info: dict) -> tuple:
    """
    Calcula el error absoluto y relativo entre el valor medido y el rango de referencia.
    Args:
        valor_hu: Valor HU medido.
        material_info: Dict con 'valor_hu' (tuple con rango min-max).
    Returns:
        (error_abs, error_rel): Valores individuales.
    """
    rango = material_info["valor_hu"]
    
    if not isinstance(rango, tuple) or len(rango) != 2 or valor_hu is None:
        return None, None
        
    rango_min, rango_max = rango
    
    # Determinar si está dentro del rango
    if rango_min <= valor_hu <= rango_max:
        error_abs = 0.0
        error_rel = "Dentro del Rango"
    else:
        # Calcular distancia al punto más cercano del rango
        if valor_hu < rango_min:
            error_abs = abs(valor_hu - rango_min)
            valor_ref = rango_min
            error_rel = "Fuera de Rango"
        else:  # valor_hu > rango_max
            error_abs = abs(valor_hu - rango_max)
            valor_ref = rango_max
            error_rel = "Fuera de Rango"
        
        # Error relativo respecto al valor de referencia más cercano
        #error_rel = (error_abs / abs(valor_ref)) * 100 if valor_ref != 0 else float('inf')
    
    return round(error_abs, 3), error_rel

def imprimir_tabla_resultados(resultado_completo):
    # Extraer la lista de resultados del diccionario
    if isinstance(resultado_completo, dict) and "resultados" in resultado_completo:
        resultados = resultado_completo["resultados"]
    else:
        # Compatibilidad hacia atrás si se pasa directamente la lista
        resultados = resultado_completo
    
    print("\n --------------------------------------------------------------------------------------------------------------------------")
    print(" |   Punto   |   Centro (x,y)   |   Material   |   Promedio HU   |   Rango HU Ref.   |   Error Abs.  |   En el rango   |")
    print(" |-----------|------------------|--------------|-----------------|-------------------|---------------|--------------------|")
    for i, res in enumerate(resultados):
        # Verificar que el elemento tenga las claves necesarias
        if not isinstance(res, dict) or "centro" not in res:
            continue
            
        centro = res["centro"]
        material = res["material"]
        promedio = res["promedio_hu"]
        rango = res["rango_hu"]
        err_abs = res["error_abs"]
        err_rel = res["error_rel"]
        rango_str = f"{rango[0]} a {rango[1]}" if rango[0] is not None and rango[1] is not None else "N/A"
        err_abs_str = f"{err_abs}" if err_abs != 'N/A' else "N/A"
        err_rel_str = f"{err_rel}" if err_rel != 'N/A' else "N/A"
        print(f" |   {i+1:^7} | {str(centro):^16} | {material:^12} | {round(promedio,1) if promedio is not None else 'N/A':^15} | {rango_str:^17} | {err_abs_str:^13} | {err_rel_str:^18} |")
        print(" |-----------|------------------|--------------|-----------------|-------------------|---------------|--------------------|")

# ---------------------------------------------- Linealidad CT y escala de contraste ---------------------------
def linealidad_ct(datos, hu_promedio, visualizar=True, canvas=None):
    import matplotlib.pyplot as plt
    import numpy as np
    """
    Analiza la linealidad de la respuesta CT.
    """
    # Datos de referencia (μ en 1/cm)


    if visualizar:
        if canvas is not None:
            # Usar la figura del canvas existente
            canvas.figure.clear()
            ax = canvas.figure.add_subplot(111)
            ax.scatter(datos, hu_promedio, color='blue', label='Datos Medidos')
            ax.plot(np.unique(datos), np.poly1d(np.polyfit(datos, hu_promedio, 1))(np.unique(datos)), color='red', label='Ajuste Lineal')
            ax.set_title('Linealidad de la Respuesta CT')
            ax.set_xlabel('Coeficiente de Atenuación (μ (1/cm))')
            ax.set_ylabel('Valor HU Medido')
            ax.legend()
            ax.grid()
            canvas.draw()
            
            # Convertir figura a formato BLOB para devolver
            import io
            buf = io.BytesIO()
            canvas.figure.savefig(buf, format='png')
            buf.seek(0)
            output_blob = buf.getvalue()  # Imagen en formato BLOB
            buf.close()
        else:
            # Crear nueva figura solo si no hay canvas
            import matplotlib.pyplot as plt
            plt.figure(figsize=(4, 4))
            plt.scatter(datos, hu_promedio, color='blue', label='Datos Medidos')
            plt.plot(np.unique(datos), np.poly1d(np.polyfit(datos, hu_promedio, 1))(np.unique(datos)), color='red', label='Ajuste Lineal')
            plt.title('Linealidad de la Respuesta CT')
            plt.xlabel('Coeficiente de Atenuación (μ (1/cm))')
            plt.ylabel('Valor HU Medido')
            plt.legend()
            plt.grid()
            plt.show()
            
            # Convertir figura a formato BLOB para devolver
            import io
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            output_blob = buf.getvalue()  # Imagen en formato BLOB
            buf.close()

    # Pendiente de la recta:
    pendiente, intercepto = np.polyfit(datos, hu_promedio, 1)
    r_squared = np.corrcoef(datos, hu_promedio)[0, 1]

    # El coeficiente de atenuación del aire y el valor HU del aire
    referencia  = (datos[0] - (0.161))/(hu_promedio[0] - 0) if hu_promedio[0] != 0 else float('inf')
    escala_contraste = 1 / pendiente if pendiente != 0 else float('inf')
    

    return {
        "pendiente": round(pendiente, 3),
        "intercepto": round(intercepto, 3),
        "r_squared": round(r_squared, 3),
        "referencia": round(referencia, 8),
        "escala_contraste": round(escala_contraste, 8),
        "imagen_analisis": output_blob if visualizar else None
    }

# ---------------------------------------------- Uniformidad ----------------------------------------------

def uniformidad(corte_255, corte_hu, tam_px, visualizar:bool=True, canvas=None, *,
                        hu_tolerancia, ui_threshold_pct: float, inu_threshold_pct: float,
                        roi_shrink: float = 0.8) -> dict:
    """
    Analiza la uniformidad (CTP486).

    G.3 (24-09): `hu_tolerancia`, `ui_threshold_pct` e `inu_threshold_pct` son OBLIGATORIOS y sin valor por defecto.
    `hu_tolerancia` es la tolerancia de la regla de uniformidad del equipo (`perfiles.py`; `None` si el equipo no tiene
    regla: entonces la marca por ROI queda `None`). Los umbrales de UI e INU no tienen fuente normativa (D-18): con ellos
    se calculan `pasa_ui`/`pasa_inu`/`pasa_global`, columnas heredadas que la BD sigue guardando; NO son el veredicto
    (ese sale de `criterios.py`). Ver `criterios.parametros_de_analisis`.

    `pasa_global` (heredado): |UI|max <= ui_threshold_pct y INU*100 <= inu_threshold_pct.
    Además marca por-ROI si |ROI-Centro| <= hu_tolerancia.
    """
    import cv2
    import numpy as np
    
    uniformidad_rois = {
        "Centro":   {"angulo": 0,   "distancia": 0,  "radio": 10},
        "Abajo":    {"angulo": 90,  "distancia": 53, "radio": 10},
        "Derecha":  {"angulo": 0,   "distancia": 53, "radio": 10},
        "Arriba":   {"angulo": 270, "distancia": 53, "radio": 10},
        "Izquierda":{"angulo": 180, "distancia": 53, "radio": 10}
    }

    catphan = GeometriaCatphan(corte_hu, tam_px)  # D.0: geometría desde HU
    output = cv2.cvtColor(corte_255, cv2.COLOR_GRAY2BGR) if visualizar else None

    resultados = {}
    valores_promedio = []

    for nombre, roi_info in uniformidad_rois.items():
        centro, radio = catphan.posicion_roi(roi_info["angulo"], roi_info["distancia"], roi_info["radio"])
        mask = np.zeros(corte_hu.shape, dtype=np.uint8)
        radio_eff = max(1, int(radio * roi_shrink))  # encoge para evitar borde
        cv2.circle(mask, centro, radio_eff, 1, -1)
        valores = corte_hu[mask == 1]

        if len(valores) > 0:
            promedio_hu = float(np.mean(valores))
            desviacion = float(np.std(valores))
            valores_promedio.append(promedio_hu)
        else:
            promedio_hu, desviacion = None, None

        resultados[nombre] = {
            "centro": centro,
            "promedio_hu": round(promedio_hu, 1) if promedio_hu is not None else None,
            "desviacion": round(desviacion, 1) if desviacion is not None else None
        }

        if visualizar and output is not None:
            cv2.circle(output, centro, radio, (0, 255, 0), 1)
            cv2.circle(output, centro, radio_eff, (255, 255, 0), 1)
            cv2.putText(output, nombre, (centro[0] - 20, centro[1] - radio - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            if promedio_hu is not None:
                cv2.putText(output, f"{promedio_hu:.1f}", (centro[0] - 20, centro[1] + 45),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.circle(output, catphan.centro_int, catphan.radio_int, (141, 60, 60), 1)
            cv2.circle(output, catphan.centro_int, catphan.radio_int, (141, 60, 60), 1)

    # UI e INU
    ui_max_val = None
    ui_max_roi = None
    center_hu = resultados.get("Centro", {}).get("promedio_hu", None)

    if center_hu is not None:
        denom = center_hu + 1000.0
        for nombre, res in resultados.items():
            if nombre == "Centro" or res["promedio_hu"] is None:
                continue
            ui = 100.0 * (res["promedio_hu"] - center_hu) / denom if denom != 0 else None  # % ya
            res["ui"] = round(ui, 3) if ui is not None else None
            diff_centro = abs(res["promedio_hu"] - center_hu)
            res["pasa_tolerancia_rel_centro"] = (None if hu_tolerancia is None else diff_centro <= hu_tolerancia)
            if ui is not None and (ui_max_val is None or abs(ui) > abs(ui_max_val)):
                ui_max_val, ui_max_roi = ui, nombre

    proms_validos = [res["promedio_hu"] for res in resultados.values() if res.get("promedio_hu") is not None]
    inu = None
    inu_warning = None
    if proms_validos:
        hu_max = max(proms_validos)
        hu_min = min(proms_validos)
        denom_inu = hu_max + hu_min + 2000.0
        if np.isfinite(denom_inu) and denom_inu > 0:
            inu = (hu_max - hu_min) / denom_inu  # fracción
        else:
            inu = None
            inu_warning = f"Denominador INU inválido (hu_max+hu_min+2000 = {denom_inu:.2f}). Revise ROIs/centro/HU."

    if valores_promedio:
        max_diferencia = max(valores_promedio) - min(valores_promedio)
        uniformity_pass_ui = (ui_max_val is not None and abs(ui_max_val) <= ui_threshold_pct)
        uniformity_pass_inu = (inu is not None and (inu * 100.0) <= inu_threshold_pct)
        resultados["Uniformidad"] = {
            "max_diferencia": round(float(max_diferencia), 3),
            "desviacion_global": round(float(np.std(valores_promedio)), 3),
            "uniformity_index_max": round(float(abs(ui_max_val)), 3) if ui_max_val is not None else None,  # usar |UI|max
            "uniformity_index_roi": ui_max_roi,
            "integral_non_uniformity": round(float(inu), 5) if inu is not None else None,
            "integral_non_uniformity_pct": round(float(inu*100), 3) if inu is not None else None,
            "pasa_ui": uniformity_pass_ui,
            "pasa_inu": uniformity_pass_inu,
            "pasa_global": bool(uniformity_pass_ui and uniformity_pass_inu),
            "inu_warning": inu_warning,
        }

    if visualizar and output is not None:
        if canvas is not None:
            # Usar la figura del canvas existente
            canvas.figure.clear()
            ax = canvas.figure.add_subplot(111)
            ax.imshow(output)
            ax.set_title("Análisis de Uniformidad")
            ax.axis('off')
            canvas.draw()
            
            # Convertir output a formato BLOB para devolver
            import io
            buf = io.BytesIO()
            canvas.figure.savefig(buf, format='png')
            buf.seek(0)
            output_blob = buf.getvalue()  # Imagen en formato BLOB
            buf.close()
        else:
            # Crear nueva figura solo si no hay canvas
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.imshow(output)
            ax.set_title("Análisis de Uniformidad")
            ax.axis('off')
            plt.show()

            # Convertir output a formato BLOB para devolver
            import io
            buf = io.BytesIO()
            fig.savefig(buf, format='png')
            buf.seek(0)
            output_blob = buf.getvalue()  # Imagen en formato BLOB
            buf.close()
        
        resultados["imagen_analisis"] = output_blob if visualizar else None

    return resultados

if __name__ == "__main__":
    from analisisImagenes.catphan.criterios import PARAMETROS_HEREDADOS
    # Cargar volumen DICOM
    ruta = "C:/Users/penak/OneDrive/Documents/SEMESTRE 8/PRUEBA_IMAGEN_KAROL/CATPHANKV"
    vol = DicomVolume(ruta)
    vol_normalizado = vol.get_volumen_normalizado(wl=-122, ww=1007)
    tam_px = vol.get_pixel_spacing()
    corte_idx = 19

    # 5. Análisis de contraste bajo
    print("\n--- Análisis de Contraste Bajo (CTP515) ---")
    corte_idx_contraste = 19  # Ajusta según tu dataset para el corte CTP515
    imagen_contraste = vol_normalizado[corte_idx_contraste]
    imagen_contraste_hu = vol_normalizado[corte_idx_contraste]
    
    resultados_contraste = resolucion_contraste(
        imagen_contraste, 
        imagen_contraste_hu, 
        tam_px=tam_px[0], 
        visualizar=True,
        **PARAMETROS_HEREDADOS["resolucion_contraste"],
    )
    
    imprimir_resultados_contraste_bajo(resultados_contraste)