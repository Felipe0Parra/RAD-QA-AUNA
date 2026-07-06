from data.ManejoDatos.catphan_TAC.leer_dicom import GeometriaCatphan, DicomVolume
from scipy.signal import find_peaks

# ---------------------------------------------- Espesor de corte ----------------------------------------------
def calcular_fwhm_interpolado(perfil):
    """Calcula el FWHM con interpolación lineal entre los puntos que cruzan el medio máximo.
    
    Args:
        perfil: Array con los valores del perfil (sin normalizar)
    
    Returns:
        tuple: (fwhm, left_cross, right_cross)
    """
    import numpy as np
    
    # Calcular el valor de medio máximo basado en los valores reales del perfil
    max_val = np.max(perfil)
    min_val = np.min(perfil)
    half_max = (max_val + min_val) / 2  # Valor medio entre el máximo y el mínimo
    
    indices = np.where(perfil > half_max)[0]
    if len(indices) == 0:
        return 0, 0, 0  # No hay cruce

    # Buscar el primer cruce por debajo del medio máximo antes del primer índice
    left_idx = indices[0]
    if left_idx == 0:
        left_cross = left_idx
    else:
        x0, x1 = left_idx - 1, left_idx
        y0, y1 = perfil[x0], perfil[x1]
        left_cross = x0 + (half_max - y0) / (y1 - y0)

    # Buscar el último cruce por debajo del medio máximo después del último índice
    right_idx = indices[-1]
    if right_idx == len(perfil) - 1:
        right_cross = right_idx
    else:
        x0, x1 = right_idx, right_idx + 1
        y0, y1 = perfil[x0], perfil[x1]
        right_cross = x0 + (half_max - y0) / (y1 - y0)
    
    fwhm = right_cross - left_cross
    return fwhm, left_cross, right_cross

def espesor_corte(corte_255, corte_hu, tam_px: float, visualizar: bool = True, 
                            combinar_slices: bool = False, slices_adyacentes: list = None, canvas = None) -> dict:
    """
    Calcula el espesor de corte utilizando las rampas de alambre del módulo CTP404.
    
    Args:
        corte_255: Imagen normalizada (0-255) del corte que contiene el módulo CTP404.
        tam_px: Tamaño de píxel en mm.
        visualizar: Si se muestran visualizaciones.
        combinar_slices: Si se combinan cortes adyacentes para mejorar SNR.
        slices_adyacentes: Lista de arrays de cortes adyacentes para combinar si combinar_slices=True.
    
    Returns:
        dict: Resultados con el espesor medido y valores individuales de cada rampa.
    """
    import cv2
    import numpy as np
    
    # Factor de corrección para el ángulo de 23° de las rampas de alambre
    RAMP_ANGLE_RATIO = 0.42
    print(f"Tamño de px que entra a la función {tam_px}")
    # Imagen a procesar (original o combinada)
    imagen_analisis = corte_hu
    
    # Si se solicita combinar cortes para mejorar SNR
    if combinar_slices and slices_adyacentes:
        # Apilar y promediar los cortes
        slices_stack = np.dstack([corte_hu] + slices_adyacentes)
        imagen_analisis = np.mean(slices_stack, axis=2).astype(np.uint8)
    
    # Obtener geometría del phantom
    catphan = GeometriaCatphan(corte_255, tam_px)
    
    # Configuración de ROIs para las rampas
    # width: dimensión perpendicular al alambre (dirección del ángulo)
    # height: dimensión paralela al alambre (perpendicular al ángulo)
    thickness_roi_width = 10   # Ancho perpendicular al alambre
    thickness_roi_height = 43  # Longitud paralela al alambre
    thickness_roi_distance_mm = 38  # Distancia del centro en mm
    
    # Definir las 4 rampas (izquierda, abajo, derecha, arriba)
    # Para cada ROI: width es la dimensión en la dirección del ángulo,
    # height es la dimensión perpendicular al ángulo
    thickness_rois = {
    "Izquierda": {"angulo": 180, "width": thickness_roi_width, "height": thickness_roi_height, "distancia": thickness_roi_distance_mm},
    "Abajo":     {"angulo": 90,  "width": thickness_roi_height, "height": thickness_roi_width, "distancia": thickness_roi_distance_mm},
    "Derecha":   {"angulo": 0,   "width": thickness_roi_width, "height": thickness_roi_height, "distancia": thickness_roi_distance_mm},
    "Arriba":    {"angulo": -90, "width": thickness_roi_height, "height": thickness_roi_width, "distancia": thickness_roi_distance_mm}
    }

    # Resultados para cada rampa
    resultados_rampas = {}
    espesores = []
    
    # Preparar visualización
    if visualizar:
        output = cv2.cvtColor(corte_255, cv2.COLOR_GRAY2BGR)
        cv2.circle(output, catphan.centro_int, catphan.radio_int, (141, 60, 60), 1)
    
    # Analizar cada rampa
    for nombre, roi_info in thickness_rois.items():
        # Obtener posición de la ROI
        distancia_px = roi_info["distancia"] / tam_px
        centro_x = int(catphan.centro[0] + distancia_px * np.cos(np.deg2rad(roi_info["angulo"])))
        centro_y = int(catphan.centro[1] + distancia_px * np.sin(np.deg2rad(roi_info["angulo"])))
        
        # Crear ROI rectangular rotada
        # width: dimensión en la dirección del ángulo (perpendicular al alambre)
        # height: dimensión perpendicular al ángulo (paralela al alambre)
        width_px = roi_info["width"]
        height_px = roi_info["height"]
        angulo_rad = np.deg2rad(roi_info["angulo"])

        # Para ángulos verticales (90° y -90°), intercambiar width y height
        # porque el cálculo de vértices asume que width va en dirección del ángulo
        angulo_norm = roi_info["angulo"] % 360
        if 45 < angulo_norm < 135 or 225 < angulo_norm < 315:
            # Ángulos verticales: intercambiar dimensiones para que el ROI quede horizontal
            width_px, height_px = height_px, width_px
        
        # Vectores unitarios para el sistema rotado
        # Vector en dirección del ángulo (width)
        cos_a = np.cos(angulo_rad)
        sin_a = np.sin(angulo_rad)
        # Vector perpendicular (height)
        cos_perp = -sin_a
        sin_perp = cos_a
        
        # Calcular los 4 vértices del rectángulo rotado
        # Desde el centro, nos movemos ±width/2 en dirección del ángulo
        # y ±height/2 en dirección perpendicular
        x1 = int(centro_x - width_px/2 * cos_a - height_px/2 * cos_perp)
        y1 = int(centro_y - width_px/2 * sin_a - height_px/2 * sin_perp)
        x2 = int(centro_x + width_px/2 * cos_a - height_px/2 * cos_perp)
        y2 = int(centro_y + width_px/2 * sin_a - height_px/2 * sin_perp)
        x3 = int(centro_x + width_px/2 * cos_a + height_px/2 * cos_perp)
        y3 = int(centro_y + width_px/2 * sin_a + height_px/2 * sin_perp)
        x4 = int(centro_x - width_px/2 * cos_a + height_px/2 * cos_perp)
        y4 = int(centro_y - width_px/2 * sin_a + height_px/2 * sin_perp)

        # Imprimir los vértices para depuración
        #print(f"ROI {nombre}: Vértices = ({x1}, {y1}), ({x2}, {y2}), ({x3}, {y3}), ({x4}, {y4})")

        # Crear máscara y extraer región
        h, w = imagen_analisis.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        pts = np.array([[x1, y1], [x2, y2], [x3, y3], [x4, y4]], np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv2.fillPoly(mask, [pts], 255)
        roi_array = imagen_analisis.copy()
        roi_array[mask == 0] = 0
        
        # Extraer el perfil colapsando en la dimensión más corta (width)
        # El perfil debe ser a lo largo del alambre (height)
        # Determinamos qué eje colapsar basándonos en el ángulo
        angulo_norm = roi_info["angulo"] % 360
        
        # Para ángulos cercanos a 0° o 180° (horizontales): el alambre es vertical, colapsar en X (axis=1)
        # Para ángulos cercanos a 90° o 270° (verticales): el alambre es horizontal, colapsar en Y (axis=0)
        if (angulo_norm < 45) or (angulo_norm > 315) or (135 < angulo_norm < 225):
            perfil = np.max(roi_array, axis=1)  # Colapsar columnas, perfil vertical
        else:
            perfil = np.max(roi_array, axis=0)  # Colapsar filas, perfil horizontal
        
        # Filtrar el perfil para reducir ruido (sigma=1 como en pylinac)
        from scipy.ndimage import gaussian_filter1d
        perfil_filtrado = gaussian_filter1d(perfil.astype(float), sigma=0.8)
        
        # Calcular FWHM directamente sobre valores filtrados (sin normalizar)
        fwhm_px, left_cross, right_cross = calcular_fwhm_interpolado(perfil_filtrado)
                
        # Calcular espesor de corte aplicando el factor de corrección del ángulo
        espesor_mm = fwhm_px * tam_px * RAMP_ANGLE_RATIO
        espesores.append(espesor_mm)
        
        resultados_rampas[nombre] = {
            "fwhm_px": fwhm_px,
            "espesor_mm": espesor_mm,
            "perfil": perfil_filtrado,
            "indices_fwhm": (left_cross, right_cross)
        }
    
        #print(f"Espesor en px en {nombre}: {fwhm_px}")
        
        # Visualización
        if visualizar:
            # Dibujar el ROI
            cv2.polylines(output, [pts], True, (0, 255, 0), 2)
            cv2.putText(output, nombre, (centro_x - 30, centro_y - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Si se calculó FWHM, mostrar el valor
            if nombre in resultados_rampas:
                cv2.putText(output, f"{resultados_rampas[nombre]['espesor_mm']:.2f} mm", 
                            (centro_x - 30, centro_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    
    # Calcular el espesor de corte promedio
    espesor_promedio = None
    if espesores:
        espesor_promedio = np.mean(espesores)
    
    # Mostrar resultado visual
    if visualizar and (output is not None):
        num_rampas = len(resultados_rampas)
        filas, columnas = 2, 3  # 2 filas, 3 columnas
        
        if canvas is not None:
            # Usar la figura del canvas existente
            canvas.figure.clear()
            axs = canvas.figure.subplots(filas, columnas)
            axs = axs.flatten()
        else:
            # Crear nueva figura solo si no hay canvas
            import matplotlib.pyplot as plt
            fig, axs = plt.subplots(filas, columnas, figsize=(9, 6))
            axs = axs.flatten()
        
        # Primer subplot: imagen con ROIs
        axs[0].imshow(output)
        axs[0].set_title("ROIs de Espesor de Corte")
        axs[0].axis('off')
        # Siguientes subplots: perfiles de rampas
        for i, (nombre, res) in enumerate(resultados_rampas.items(), start=1):
            axs[i].plot(res['perfil'], 'b-')
            if 'indices_fwhm' in res:
                first, last = res['indices_fwhm']
                axs[i].axvline(x=first, color='r', linestyle='--')
                axs[i].axvline(x=last, color='r', linestyle='--')
                axs[i].axhline(y=np.max(res['perfil']) / 2, color='g', linestyle='--')
            axs[i].set_title(f"{nombre}: {res['espesor_mm']:.2f} mm")
            axs[i].grid(True)
        # Ocultar los subplots vacíos
        for j in range(1 + num_rampas, filas * columnas):
            axs[j].axis('off')
        
        if canvas is not None:
            canvas.figure.tight_layout()
            canvas.draw()
        else:
            import matplotlib.pyplot as plt
            plt.tight_layout()
            plt.show()

        # Convertir output a formato BLOB para devolver
        if output is not None:
            _, buffer = cv2.imencode('.png', output)
            output_blob = buffer.tobytes() # Imagen en formato BLOB 
        else:
            output_blob = None

    # Devolver resultados
    return {
        "espesor_promedio_mm": round(espesor_promedio, 2) if espesor_promedio else None,
        "espesores_individuales": {nombre: round(res["espesor_mm"], 2) for nombre, res in resultados_rampas.items()},
        "factor_correccion": RAMP_ANGLE_RATIO,
        "num_rampas_detectadas": len(espesores),
        "combinacion_slices": combinar_slices,
        "imagen_analisis": output_blob if visualizar else None # Imagen con ROIs dibujadas en formato BLOB
    }

# ---------------------------------------------- Tamaño de pixel  ----------------------------------------------

def tamano_pixel(corte_255,  tam_px: float, visualizar: bool, canvas = None)  -> dict:
    """
    Calcula el tamaño de pixel estimado usando los centros de los círculos.
    Args:
        corte: Imagen 2D (0-255).
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

    # Obtener geometría del phantom
    catphan = GeometriaCatphan(corte_255, tam_px)
    
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
                         cnr_lim: float = 1.0,
                         visibilidad_lim: float = 0.1,
                         visibilidad_manual: dict | None = None) -> dict:
    import cv2
    import numpy as np

    if catphan is None:
        catphan = GeometriaCatphan(corte_255, tam_px)

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
        angulo      = roi_info["angulo"]
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
        "pasa_test_cnr":             rois_visibles_cnr         >= 4,
        "pasa_test_visibilidad":     rois_visibles_visibilidad >= 4,
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

def resolucion_espacial(corte, tam_px: float, visualizar=True, canvas=None) -> dict:
    """
    Analiza la resolución espacial mediante el cálculo del MTF.
    Usa boundaries en orden descendente (segmentos: start > end).
    """
    import cv2
    import numpy as np
    
    catphan = GeometriaCatphan(corte, tam_px)

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
    angles = np.arctan2(ys - catphan.centro[1], xs - catphan.centro[0])
    angles = np.mod(angles, 2*np.pi)
    idx = np.argsort(angles)
    angles_sorted = angles[idx]
    values_sorted = corte[ys[idx], xs[idx]]
    norm_angles = angles_sorted / (2*np.pi)

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

def mostrar_regiones_anillo(corte, tam_px: float, boundaries=None, roi_settings=None,
        radio_mm=47, ancho_rel=0.08, angle_offset_deg=0, visualizar=True, return_data=True,
        invertir_config_en_mismo_lugar=False, invertir_posicion=False):
    """
    Visualiza las regiones del anillo. Usa los mismos flags de inversión que construir_roi_settings.
    """
    import cv2
    import numpy as np
    
    geo = GeometriaCatphan(corte, tam_px)
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
        catphan = GeometriaCatphanCT(corte_255, tam_px)
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

def uniformidad(corte_255, corte_hu, tam_px, visualizar:bool=True, canvas=None,
                        hu_tolerancia: float = 40.0, ui_threshold_pct: float = 2.0, inu_threshold_pct: float = 2.0,
                        roi_shrink: float = 0.8) -> dict:
    """
    Analiza la uniformidad (CTP486).
    Pasa si |UI|max <= ui_threshold_pct y INU*100 <= inu_threshold_pct.
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

    catphan = GeometriaCatphan(corte_255, tam_px)
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
            res["pasa_tolerancia_rel_centro"] = (diff_centro <= hu_tolerancia)
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
        cnr_lim=1.0,
        visibilidad_lim=0.1,
      
    )
    
    imprimir_resultados_contraste_bajo(resultados_contraste)