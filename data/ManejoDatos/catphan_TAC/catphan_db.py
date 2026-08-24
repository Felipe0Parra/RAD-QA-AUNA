"""
Funciones de mapeo y guardado para análisis CatPhan TAC.
Conecta los resultados de las funciones de análisis con las tablas de base de datos.
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
import traceback, os, io
import numpy as np
from PIL import Image
from datetime import datetime
from data.ManejoDatos.conection import Conexion
from .leer_dicom import DicomVolume
from services.audit_minimo import registrar as _registrar_auditoria
from services.audit_minimo import ACCION_GUARDAR
from services.anulacion import filtro_activo, reemplazar_bloque, sql_anular_bloque

# ------------------------------------ FUNCIONES PARA MOSTRAR IMÁGENES ------------------------------------

def mostrar_imagen_blob_en_canvas(blob_data, canvas=None):
    """
    Convierte datos BLOB a imagen y la muestra en un canvas de matplotlib.
    
    Args:
        blob_data (bytes): Datos de imagen en formato BLOB
        canvas (FigureCanvas, optional): Canvas donde mostrar la imagen
    
    Returns:
        bool: True si se mostró correctamente, False si hubo error
    """
    if not blob_data:
        #print("❌ No hay datos de imagen BLOB")
        return False
        
    try:
        # Convertir BLOB a imagen PIL
        imagen_buffer = io.BytesIO(blob_data)
        imagen_pil = Image.open(imagen_buffer)
        imagen_array = np.array(imagen_pil)
        
        if canvas:
            # Limpiar el canvas actual
            canvas.figure.clear()
            
            # Crear subplot
            ax = canvas.figure.add_subplot(111)
            ax.imshow(imagen_array, cmap='gray')
            ax.set_title('Imagen de Análisis Guardada', fontsize=12, pad=15)
            ax.axis('off')
            
            # Actualizar el canvas
            canvas.draw()
            #print("✅ Imagen BLOB mostrada en canvas")
            return True
        else:
            #print("⚠️ No se proporcionó canvas para mostrar la imagen")
            return False
            
    except Exception as e:
        #print(f"❌ Error al mostrar imagen BLOB: {e}")
        return False

def crear_widget_con_imagen_y_resultados(texto_resultados, imagen_blob, kv, ma, espesor_corte, label, canvas):
    """
    Actualiza el label con texto e información de parámetros, y muestra la imagen en el canvas.
    """

    from PyQt5.QtWidgets import  QLabel
    # 1. Crear texto con parámetros de adquisición
    contenido_completo = f"""📊 Parámetros: {kv} kV | {ma} mA | {espesor_corte} mm
                        {texto_resultados}"""
    
    # 2. Actualizar el label con el texto completo
    label.setText(contenido_completo)
    label.setStyleSheet("""
        QLabel {
            font-family: 'Segoe UI';
            font-size: 13px;
            color: #2c3e50;
            background-color: #f8f9fa;
            padding: 15px;
            border: 1px solid #dee2e6;
            border-radius: 5px;
        }
    """)
    
    # 3. Mostrar la imagen en el canvas si está disponible
    if imagen_blob and canvas:
        mostrar_imagen_blob_en_canvas(imagen_blob, canvas)

    return True  # Indicar que se completó la operación

def crear_widget_con_parametros_imagen_y_contenido(widget_contenido, label_objetivo, kv, ma, espesor_corte, imagen_blob, canvas):
    """
    Actualiza el label con parámetros y tabla de resultados, y muestra la imagen en el canvas proporcionado.
    Similar a crear_widget_con_imagen_y_resultados pero usando el canvas existente.
    """
    from PyQt5.QtWidgets import QLabel
    
    # 1. Crear texto con parámetros de adquisición
    contenido_completo = f"""📊 Parámetros: {kv} kV | {ma} mA | {espesor_corte} mm
                        """
    
    # 2. Actualizar el label con parámetros y reemplazar con la tabla
    label_objetivo.setText(contenido_completo)
    label_objetivo.setStyleSheet("""
        QLabel {
            font-family: 'Segoe UI';
            font-size: 13px;
            color: #2c3e50;
            background-color: #f8f9fa;
            padding: 15px;
            border: 1px solid #dee2e6;
            border-radius: 5px;
        }
    """)
    
    # 3. Reemplazar el contenido del label con la tabla/widget
    reemplazar_resultados_texto_con_tabla(widget_contenido, label_objetivo)
    
    # 4. Mostrar la imagen en el canvas proporcionado si está disponible
    if imagen_blob and canvas:
        mostrar_imagen_blob_en_canvas(imagen_blob, canvas)
    return True  # Indicar que se completó la operación

# ------------------------------------ FUNCIONES DE MAPEO ------------------------------------

def mapear_espesor_corte(resultados_espesor, espesor_teorico_dicom):
    """
    Mapea los resultados de espesor_corte() a la estructura de BD.
    
    Args:
        resultados_espesor (dict): Resultados de la función espesor_corte()
        espesor_teorico_dicom (float): Valor teórico del DICOM
    
    Returns:
        dict: Datos mapeados para la tabla espesor_corte
    """
    if not resultados_espesor:
        return None
        
    espesor_promedio = resultados_espesor.get("espesor_promedio_mm")
    diferencia = abs(espesor_promedio - espesor_teorico_dicom) if espesor_promedio and espesor_teorico_dicom else None
    
    # Extraer espesores individuales
    espesores_ind = resultados_espesor.get("espesores_individuales", {})
    
    return {
        "espesor_promedio_mm": espesor_promedio,
        "espesor_teorico_mm": espesor_teorico_dicom,
        "diferencia_mm": diferencia,
        "factor_correccion": resultados_espesor.get("factor_correccion", 0.42),
        "num_rampas_detectadas": resultados_espesor.get("num_rampas_detectadas"),
        "combinacion_slices": resultados_espesor.get("combinacion_slices", False),
        "espesor_izquierda": espesores_ind.get("Izquierda"),
        "espesor_abajo": espesores_ind.get("Abajo"),
        "espesor_derecha": espesores_ind.get("Derecha"),
        "espesor_arriba": espesores_ind.get("Arriba"),
        "imagen_analisis": resultados_espesor.get("imagen_analisis") # BLOB o None
    }

def mapear_tamano_pixel(resultados_tamano, tam_px_teorico):
    """
    Mapea los resultados de tamano_pixel() a la estructura de BD.
    
    Args:
        resultados_tamano (dict): Resultados de la función tamano_pixel()
        tam_px_teorico (float): Valor teórico del DICOM
    
    Returns:
        dict: Datos mapeados para la tabla tamaño_pixel
    """
    if not resultados_tamano:
        return None
        
    x = resultados_tamano.get("X", {})
    y = resultados_tamano.get("Y", {})
    
    # Calcular diferencias vs teórico
    diferencia_x = abs(x - tam_px_teorico) if x and tam_px_teorico else None
    diferencia_y = abs(y - tam_px_teorico) if y and tam_px_teorico else None

    prom_tam = (x + y) / 2 if x and y else None
    error_pct =  (abs(round(tam_px_teorico, 3) - round(prom_tam, 3)) / round(tam_px_teorico, 3)) * 100

    return {
        "valor_teorico_dicom": tam_px_teorico,
        "X": x,
        "Y": y,
        "diferencia_x": diferencia_x,
        "diferencia_y": diferencia_y,
        "error_pct": error_pct,
        "imagen_analisis": resultados_tamano.get("imagen_analisis") # BLOB o None
    }

def mapear_resolucion_contraste(resultados_resolucion):
    """
    Mapea los resultados de resolucion_contraste() a la estructura de BD.
    
    Args:
        resultados_resolucion (dict): Resultados de la función resolucion_contraste()
    
    Returns:
        tuple: (datos_resumen, lista_rois)
    """
    if not resultados_resolucion:
        return None, None
        
    resumen = resultados_resolucion.get("resumen", {})
    resultados_roi = resultados_resolucion.get("resultados_roi", {})
    
    # Datos para tabla resumen
    datos_resumen = {
        "rois_visibles_cnr": resumen.get("rois_visibles_cnr"),
        "rois_visibles_visibilidad": resumen.get("rois_visibles_visibilidad_lim"),
        "total_rois": resumen.get("total_rois"),
        "pasa_test_cnr": len([r for r in resultados_roi.values() if r.get("pasa_cnr", False)]) >= 4,
        "pasa_test_visibilidad": resumen.get("pasa_test_visibilidad_lim"),  
        "metodo_recomendado": "visibilidad_lim",
        "imagen_analisis": resumen.get("imagen_analisis") # BLOB o None
    }
    
    # Determinar diámetro mínimo visible
    diametros_visibles = [int(d.replace("mm", "")) for d, r in resultados_roi.items() 
                            if r.get("pasa_visibilidad_lim", False)]
    datos_resumen["diametro_minimo_visible"] = min(diametros_visibles) if diametros_visibles else None
    
    # Datos para tabla detalle por ROI
    lista_rois = []
    for diametro_str, roi_data in resultados_roi.items():
        diametro = int(diametro_str.replace("mm", ""))
        centro = roi_data.get("centro_roi", (None, None))
        
        roi_mapeado = {
            "diametro_mm": diametro,
            "centro_x": centro[0] if centro else None,
            "centro_y": centro[1] if centro else None,
            "roi_promedio_hu": roi_data.get("roi_prom"),
            "background_promedio_hu": roi_data.get("background_prom"),
            "contraste_michelson": roi_data.get("contraste_michelson"),
            "cnr": roi_data.get("cnr"),
            "snr": roi_data.get("snr"),
            "visibilidad_lim": roi_data.get("visibilidad_lim"),
            "pasa_cnr": roi_data.get("pasa_cnr", False),
            "pasa_visibilidad_lim": roi_data.get("pasa_visibilidad_lim", False)
        }
        lista_rois.append(roi_mapeado)
    
    return datos_resumen, lista_rois

def mapear_resolucion_espacial(resultados_resolucion):
    """
    Mapea los resultados de resolucion_espacial() a la estructura de BD.
    
    Args:
        resultados_resolucion (dict): Resultados de la función resolucion_espacial()
    
    Returns:
        tuple: (datos_resumen, lista_regiones)
    """
    if not resultados_resolucion:
        return None, None
        
    # CORREGIR: Acceder correctamente a los campos del diccionario
    region_results = resultados_resolucion.get("region_results", {})
    resolucion_limite = resultados_resolucion.get("resolucion_limite", {})
    mtf_lp_mm = resultados_resolucion.get("mtf_lp_mm", {})
    
    # Filtrar solo regiones con datos válidos
    regiones_validas = {k: v for k, v in region_results.items() 
                        if v.get("status") == "OK" and isinstance(v.get("lp/mm"), (int, float))}
    
    # Datos para tabla resumen 
    datos_resumen = {
        "regiones_analizadas": len(region_results),
        "regiones_exitosas": len(regiones_validas),
        "lp_mm_maximo": resolucion_limite.get("lp_mm_maximo"),  
        "ultima_region_exitosa": resolucion_limite.get("ultima_region"),  
        "gap_size_minimo_cm": resolucion_limite.get("gap_size_cm"), 
        "num_picos_totales": resultados_resolucion.get("num_picos"), 
        "mtf_10_pct": mtf_lp_mm.get("10"),
        "mtf_20_pct": mtf_lp_mm.get("20"), 
        "mtf_50_pct": mtf_lp_mm.get("50")
    }
    
    # Datos para tabla detalle por región
    lista_regiones = []
    for region_nombre, region_data in region_results.items():
        region_mapeada = {
            "region_nombre": region_nombre,
            "lp_mm": region_data.get("lp/mm"), 
            "peak_mean": region_data.get("peak_mean"), 
            "valley_mean": region_data.get("valley_mean"), 
            "gap_size_cm": region_data.get("gap_size_cm"),  
            "n_peaks_used": region_data.get("n_peaks_used"),  
            "n_valleys_used": region_data.get("n_valleys_used"), 
            "status": region_data.get("status", "Unknown")
        }
        lista_regiones.append(region_mapeada)
    
    return datos_resumen, lista_regiones

def mapear_valores_ct(resultados_ct):
    """
    Mapea los resultados de valor_numero_ct() a la estructura de BD.
    
    Args:
        resultados_ct (list): Resultados de la función valor_numero_ct()
    
    Returns:
        list: Lista de datos mapeados para la tabla valores_ct
    """
    if not resultados_ct:
        return []
        
    valores_mapeados = []
    
    # Mapeo de nombres de materiales
    mapeo_materiales = {
        "Acrilico": "Acrilico",
        "Teflon": "Teflon", 
        "Delrin": "Delrin",
        "Poliestireno": "Polystyrene",  # ✅ CORREGIR: función usa "Poliestireno"
        "LDPE": "LDPE",
        "PMP": "PMP",
        "Aire": "Aire"
    }
    
    for resultado in resultados_ct:
        material_original = resultado.get("material", "")  # ✅ CORREGIR: es "material", no "nombre_material"
        material_normalizado = mapeo_materiales.get(material_original, material_original)
        
        valor_mapeado = {
            "material": material_normalizado,
            "promedio_hu": resultado.get("promedio_hu"),
            "error_absoluto": resultado.get("error_abs"),  # ✅ CORREGIR: es "error_abs"
            "error_relativo": resultado.get("error_rel")   # ✅ CORREGIR: es "error_rel"
        }
        valores_mapeados.append(valor_mapeado)
    
    return valores_mapeados

def mapear_uniformidad(resultados_uniformidad):
    """
    Mapea los resultados de uniformidad() a la estructura de BD.
    
    Args:
        resultados_uniformidad (dict): Resultados de la función uniformidad()
    
    Returns:
        tuple: (datos_global, lista_regiones)
    """
    if not resultados_uniformidad:
        return None, None
        
    uniformidad_global = resultados_uniformidad.get("Uniformidad", {})
    
    # Datos para tabla uniformidad_global
    datos_global = {
        "max_diferencia": uniformidad_global.get("max_diferencia"),
        "desviacion_global": uniformidad_global.get("desviacion_global"), 
        "uniformity_index_max": uniformidad_global.get("uniformity_index_max"),
        "uniformity_index_roi": uniformidad_global.get("uniformity_index_roi"),
        "integral_non_uniformity": uniformidad_global.get("integral_non_uniformity"),
        "integral_non_uniformity_pct": uniformidad_global.get("integral_non_uniformity_pct"),
        "pasa_ui": uniformidad_global.get("pasa_ui"),
        "pasa_inu": uniformidad_global.get("pasa_inu"),
        "pasa_global": uniformidad_global.get("pasa_global"),
        "ui_threshold_pct": 2.0,  # Valor por defecto usado en la función
        "inu_threshold_pct": 2.0,  # Valor por defecto usado en la función
        "hu_tolerancia": 40.0  # Valor por defecto usado en la función
    }
    
    # ✅ CORREGIR: Datos para tabla uniformidad_ruido (regiones individuales)
    regiones_uniformidad = []
    # ✅ CAMBIAR: Los nombres reales que usa la función
    regiones_nombres = ["Centro", "Arriba", "Derecha", "Abajo", "Izquierda"]  # ✅ Usar "Arriba" no "Superior"
    
    for region_nombre in regiones_nombres:
        if region_nombre in resultados_uniformidad:
            region_data = resultados_uniformidad[region_nombre]
            if isinstance(region_data, dict):
                region_mapeada = {
                    "region_nombre": region_nombre,
                    "hu_promedio": region_data.get("promedio_hu"),
                    "desviacion": region_data.get("desviacion")
                }
                regiones_uniformidad.append(region_mapeada)
    
    return datos_global, regiones_uniformidad

def mapear_linealidad_ct(resultados_linealidad):
    """
    Mapea los resultados de linealidad_ct() a la estructura de BD.
    
    Args:
        resultados_linealidad (dict): Resultados de la función linealidad_ct()
    
    Returns:
        dict: Datos mapeados para la tabla linealidad_ct
    """
    if not resultados_linealidad:
        return None
        
    return {
        "pendiente": resultados_linealidad.get("pendiente"),
        "intercepto": resultados_linealidad.get("intercepto"),
        "r_cuadrado": resultados_linealidad.get("r_squared"),  # ✅ Nota: "r_squared" en función, "r_cuadrado" en BD
        "referencia": resultados_linealidad.get("referencia"),
        "escala_contraste": resultados_linealidad.get("escala_contraste"),
        "num_materiales": 7,        # Fijo: 7 materiales del CatPhan
        "rango_hu_min": -1000,      # Rango típico de análisis HU
        "rango_hu_max": 1000,       # Rango típico de análisis HU  
        "linealidad_aceptable": resultados_linealidad.get("r_squared", 0) >= 0.99  # Criterio: R² ≥ 0.99
    }

# ------------------------------------ FUNCIONES DE GUARDADO -------------------------------------------

def convertir_corte_dicom_a_blob(ruta_carpeta_dicom, indice_corte=None, wl=None, ww=None):
    """
    Convierte un corte específico de una carpeta DICOM a BLOB para almacenar en base de datos.
    Si no se especifica indice_corte, usa el corte central del volumen.
    
    Args:
        ruta_carpeta_dicom (str): Ruta a la carpeta que contiene archivos DICOM
        indice_corte (int, optional): Índice del corte a extraer. Si es None, usa el corte central
        wl (int, optional): Window Level para la visualización
        ww (int, optional): Window Width para la visualización
        
    Returns:
        bytes: Datos de la imagen del corte en formato BLOB (PNG), o None si hay error
    """
    if not ruta_carpeta_dicom or not os.path.exists(ruta_carpeta_dicom):
        #print(f"❌ Ruta de carpeta DICOM inválida: {ruta_carpeta_dicom}")
        return None
        
    try:
        #print(f"🔄 Cargando volumen DICOM desde: {ruta_carpeta_dicom}")
        
        # Cargar el volumen DICOM
        volumen = DicomVolume(ruta_carpeta_dicom)
        
        if volumen.volumen_hu is None:
            #print("❌ No se pudo cargar el volumen DICOM")
            return None
            
        num_cortes = volumen.get_num_cortes()
        #print(f"📊 Volumen cargado: {num_cortes} cortes")
        
        # Determinar el índice del corte
        if indice_corte is None:
            indice_corte = num_cortes // 2  # Corte central
            #print(f"🎯 Usando corte central: {indice_corte}")
        else:
            #print(f"🎯 Usando corte especificado: {indice_corte}")
            pass
        if indice_corte < 0 or indice_corte >= num_cortes:
            #print(f"❌ Índice de corte fuera de rango: {indice_corte} (0-{num_cortes-1})")
            return None
            
        # Obtener el corte
        if wl is not None and ww is not None:
            # Usar ventana específica
            volumen_ventana = volumen.get_volumen_normalizado(wl, ww)
            if volumen_ventana is not None:
                corte_imagen = volumen_ventana[indice_corte]
                #print(f"🖼️ Corte extraído con ventana WL={wl}, WW={ww}")
            else:
                #print("⚠️ Error al aplicar ventana, usando corte HU normalizado")
                corte_hu = volumen.get_corte(indice_corte)
                corte_imagen = np.uint8(np.clip((corte_hu + 1024) / 4096 * 255, 0, 255))
        else:
            # Usar normalización automática de HU
            corte_hu = volumen.get_corte(indice_corte)
            if corte_hu is not None:
                # Normalizar HU a rango 0-255 para visualización
                min_hu, max_hu = corte_hu.min(), corte_hu.max()
                corte_imagen = np.uint8((corte_hu - min_hu) / (max_hu - min_hu) * 255)
                #print(f"🖼️ Corte extraído y normalizado: HU [{min_hu:.1f}, {max_hu:.1f}]")
            else:
                #print("❌ No se pudo obtener el corte HU")
                return None
        
        # Convertir a imagen PIL y luego a BLOB
        imagen_pil = Image.fromarray(corte_imagen)
        
        # Guardar en buffer como PNG
        buffer = io.BytesIO()
        imagen_pil.save(buffer, format='PNG')
        blob_data = buffer.getvalue()
        buffer.close()
        
        #print(f"✅ Corte DICOM convertido a BLOB: {len(blob_data)} bytes (PNG)")
        return blob_data
        
    except Exception as e:
        #print(f"❌ Error al convertir corte DICOM a BLOB: {e}")
        traceback.print_exc()
        return None

def guardar_prueba_completa_catphan(user_id, fecha, equipo, kv, ma, espesor_corte, resultados_por_categoria, 
                                    tam_px_teorico=None, id_sesion=None, info_dicom=None, output_blob=None):
    conn = None
    print("Guardando")
    try:
        conn = Conexion().conectar()
        conn.execute("PRAGMA busy_timeout = 30000")
        cursor = conn.cursor()

        # Agregar columna equipo si no existe
        cursor.execute("PRAGMA table_info(pruebas)")
        columnas = [row[1] for row in cursor.fetchall()]
        if 'equipo' not in columnas:
            cursor.execute("ALTER TABLE pruebas ADD COLUMN equipo TEXT")
            conn.commit()
            print("✅ Columna 'equipo' agregada a pruebas")

        if id_sesion is None:
            fecha_formateada = datetime.strptime(fecha, "%Y-%m-%d").strftime("%Y%m%d")
            timestamp = int(datetime.now().timestamp() * 1000)
            id_sesion = f"{fecha_formateada}_{timestamp}"
        
        mapeo_tipos = {
            "espesor": 1,
            "tamano_pixel": 2,
            "resolucion_contraste": 3,
            "resolucion_espacial": 4,
            "valores_ct": 5,
            "linealidad_ct": 6,
            "uniformidad": 7
        }
        
        imagen_blob = None
        if info_dicom and info_dicom.get('ruta_carpeta'):
            ruta_carpeta = info_dicom['ruta_carpeta']
            indice_corte = info_dicom.get('indice_corte')
            wl = info_dicom.get('wl')
            ww = info_dicom.get('ww')
            imagen_blob = convertir_corte_dicom_a_blob(ruta_carpeta, indice_corte, wl, ww)

        # A6.7: se calcula aquí (antes vivía junto al registrar() de más
        # abajo) porque EB2c ya lo necesita dentro del bucle, para pasarlo
        # a reemplazar_bloque con auditar=False.
        _nombre_usuario = getattr(user_id, "_nombre", user_id)

        for categoria, resultados in resultados_por_categoria.items():
            id_tipo = mapeo_tipos.get(categoria)
            if not id_tipo:
                continue

            # EB2c (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB2c, 24-08): antes,
            # un `id_prueba` existente se MUTABA en sitio (UPDATE) y sus
            # hijas se borraban físicamente (`eliminar_datos_especificos`)
            # -- mismo patrón de EB2b/G1, sobre otra raíz. Ahora `pruebas`
            # se reemplaza como bloque: la fila anterior (si existía) se
            # ANULA, la nueva entra con un `id_prueba` NUEVO, y las hijas
            # del `id_prueba` ANTERIOR se anulan explícitamente (nunca se
            # borran) antes de insertar las hijas nuevas bajo el id nuevo.
            cursor.execute(f"""
                SELECT id_prueba, imagen_path, imagen_resultado FROM pruebas
                WHERE id_sesion = ? AND id_tipo = ?{filtro_activo('pruebas')}
            """, (id_sesion, id_tipo))
            entrada_existente = cursor.fetchone()

            if entrada_existente:
                id_prueba_anterior, imagen_path_anterior, imagen_resultado_anterior = entrada_existente
            else:
                id_prueba_anterior = imagen_path_anterior = imagen_resultado_anterior = None

            # Mismo criterio que el UPDATE/INSERT original: una imagen
            # nueva reemplaza a la anterior; sin imagen nueva, se conserva
            # la que ya hubiera (si la había).
            imagen_path_usar = imagen_blob if imagen_blob else imagen_path_anterior
            imagen_resultado_usar = output_blob if imagen_blob else imagen_resultado_anterior

            reemplazar_bloque(
                cursor, "pruebas", [("id_sesion", id_sesion), ("id_tipo", id_tipo)],
                """
                    INSERT INTO pruebas
                    (id_sesion, id_tipo, kv, ma, espesor_corte, created_at,
                     imagen_path, imagen_resultado, equipo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [(id_sesion, id_tipo, kv, ma, espesor_corte, fecha,
                  imagen_path_usar, imagen_resultado_usar, equipo)],
                _nombre_usuario, auditar=False)
            id_prueba = cursor.lastrowid

            if id_prueba_anterior is not None:
                anular_datos_especificos(cursor, categoria, id_prueba_anterior)

            if categoria == "espesor":
                guardar_espesor_corte(cursor, id_prueba, resultados, espesor_corte)
            elif categoria == "tamano_pixel":
                guardar_tamano_pixel(cursor, id_prueba, resultados, tam_px_teorico)
            elif categoria == "resolucion_contraste":
                guardar_resolucion_contraste(cursor, id_prueba, resultados)
            elif categoria == "resolucion_espacial":
                guardar_resolucion_espacial(cursor, id_prueba, resultados)
            elif categoria == "valores_ct":
                guardar_valores_ct(cursor, id_prueba, resultados)
            elif categoria == "linealidad_ct":
                guardar_linealidad_ct(cursor, id_prueba, resultados)
            elif categoria == "uniformidad":
                guardar_uniformidad(cursor, id_prueba, resultados)
        
        conn.commit()
        print(f"✅ Prueba CatPhan guardada exitosamente con ID de sesión: {id_sesion}")

        # A6.7 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): esta función es el
        # único punto de entrada real de las 9 de catphan_db.py (los 2
        # llamadores de tac_mensual.py no escriben directo) -- un solo
        # guardado puede tocar varias categorías (espesor, tamaño de
        # píxel, resolución...) en un bucle; 1 fila de auditoría para la
        # acción completa, no una por categoría ni por tabla (las llamadas
        # a `reemplazar_bloque` de dentro del bucle usan `auditar=False`
        # por eso). `_nombre_usuario` ya se calculó arriba, antes del
        # bucle. Corre DESPUÉS de `conn.commit()`: la transacción ya cerró,
        # así que abrir su propia conexión aquí (sin `con=`) no compite por
        # ningún lock (EB0 no aplica -- no hay transacción abierta que
        # compartir).
        _registrar_auditoria(_nombre_usuario, ACCION_GUARDAR, "pruebas", ref=id_sesion,
                             detalle=f"CatPhan: {', '.join(resultados_por_categoria)}")

        return id_sesion
        
    except Exception as e:
        if conn:
            conn.rollback()
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        if conn:
            conn.close()

_TABLAS_HIJAS_POR_CATEGORIA = {
    "espesor": ("espesor_corte",),
    "tamano_pixel": ("tamaño_pixel",),
    "resolucion_contraste": ("resolucion_contraste", "resolucion_contraste_rois"),
    "resolucion_espacial": ("resolucion_espacial", "resolucion_espacial_regiones"),
    "valores_ct": ("valores_ct",),
    "linealidad_ct": ("linealidad_ct",),
    "uniformidad": ("uniformidad_ruido", "uniformidad_global"),
}


def anular_datos_especificos(cursor, categoria, id_prueba):
    """EB2c (PLAN_CONTRATO_COMPLETO_19-08.md §6-EB2c, 24-08, cierra G6):
    anula (activo=0) las filas hijas del `id_prueba` ANTERIOR -- nunca las
    borra. Reemplaza a la antigua `eliminar_datos_especificos` (`DELETE`
    físico) ahora que `pruebas` reemplaza su bloque con un `id_prueba`
    NUEVO en cada reguardado (EB1): las hijas del id viejo quedarían
    huérfanas-pero-activas para siempre si no se anulan explícitamente.

    Sin `try/except`, a propósito: la versión anterior se tragaba
    cualquier fallo con un `print` -- G6 (auditoría del 24-08) señaló que
    eso convertía un fallo real en una duplicación SILENCIOSA. Un fallo
    aquí debe propagar hasta el `except`/`rollback` de
    `guardar_prueba_completa_catphan`, que ya revierte la transacción
    entera.
    """
    for tabla in _TABLAS_HIJAS_POR_CATEGORIA.get(categoria, ()):
        cursor.execute(sql_anular_bloque(tabla, ["id_prueba"]), (id_prueba,))

# Funciones específicas de guardado (solo campos existentes):

def guardar_espesor_corte(cursor, id_prueba, resultados, espesor_teorico):
    """Guarda resultados de espesor de corte - SOLO CAMPOS EXISTENTES"""
    datos = mapear_espesor_corte(resultados, espesor_teorico)
    if not datos:
        return False
        
    cursor.execute("""
        INSERT INTO espesor_corte (
            id_prueba, espesor_promedio_mm, espesor_teorico_mm, diferencia_mm, error_pct
        ) VALUES (?, ?, ?, ?, ?)
    """, (
        id_prueba, 
        round(datos["espesor_promedio_mm"], 3) if datos["espesor_promedio_mm"] is not None else "No disponible", 
        round(datos["espesor_teorico_mm"], 3) if datos["espesor_teorico_mm"] is not None else "No disponible", 
        round(datos["diferencia_mm"], 3) if datos["diferencia_mm"] is not None else "No disponible",
        error_pct := round(datos["diferencia_mm"] / datos["espesor_teorico_mm"] * 100, 3)
                    if datos["diferencia_mm"] and datos["espesor_teorico_mm"] else "No disponible"
    ))
    #print(f"  ✓ Espesor de corte guardado para prueba {id_prueba}")
    return True

def guardar_tamano_pixel(cursor, id_prueba, resultados, tam_px_teorico):
    """Guarda resultados de tamaño de pixel - SOLO CAMPOS EXISTENTES"""
    datos = mapear_tamano_pixel(resultados, tam_px_teorico)
    if not datos:
        return False
        
    cursor.execute("""
        INSERT INTO tamaño_pixel (
            id_prueba, valor_teorico_dicom, X, Y, diferencia_x, diferencia_y, error_pct
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        id_prueba,
        round(datos["valor_teorico_dicom"], 3) if datos["valor_teorico_dicom"] is not None else "No disponible",
        round(datos["X"], 3) if datos["X"] is not None else None,
        round(datos["Y"], 3) if datos["Y"] is not None else None,
        round(datos["diferencia_x"], 3) if datos["diferencia_x"] is not None else None,
        round(datos["diferencia_y"], 3) if datos["diferencia_y"] is not None else None,
        round(datos["error_pct"], 3) if datos["error_pct"] is not None else None
    ))
    #print(f"  ✓ Tamaño de pixel guardado para prueba {id_prueba}")
    return True

def guardar_resolucion_contraste(cursor, id_prueba, resultados):
    """Guarda resultados de resolución de contraste - SOLO CAMPOS EXISTENTES"""
    datos_resumen, lista_rois = mapear_resolucion_contraste(resultados)
    if not datos_resumen or not lista_rois:
        return False
    
    def to_native(val):
        if isinstance(val, (np.generic,)):
            return val.item()
        return val 

    # 1. Guardar resumen en tabla principal
    cursor.execute("""
        INSERT INTO resolucion_contraste (
            id_prueba, rois_visibles_cnr, rois_visibles_visibilidad, total_rois,
            diametro_minimo_visible, pasa_test_cnr, pasa_test_visibilidad, metodo_recomendado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        id_prueba,
        to_native(datos_resumen["rois_visibles_cnr"]),
        to_native(datos_resumen["rois_visibles_visibilidad"]),
        to_native(datos_resumen["total_rois"]),
        to_native(datos_resumen["diametro_minimo_visible"]),
        bool(datos_resumen["pasa_test_cnr"]),
        bool(datos_resumen["pasa_test_visibilidad"]),
        datos_resumen["metodo_recomendado"]
    ))

    # 2. Guardar detalles por ROI
    for roi in lista_rois:
        cursor.execute("""
            INSERT INTO resolucion_contraste_rois (
                id_prueba, diametro_mm, centro_x, centro_y, roi_promedio_hu,
                background_promedio_hu, contraste_michelson, cnr, snr,
                visibilidad_lim, pasa_cnr, pasa_visibilidad_lim
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            id_prueba,
            to_native(roi["diametro_mm"]),
            to_native(roi["centro_x"]),
            to_native(roi["centro_y"]),
            to_native(roi["roi_promedio_hu"]),
            to_native(roi["background_promedio_hu"]),
            to_native(roi["contraste_michelson"]),
            to_native(roi["cnr"]),
            to_native(roi["snr"]),
            to_native(roi["visibilidad_lim"]),
            bool(roi["pasa_cnr"]),
            bool(roi["pasa_visibilidad_lim"])
        ))
    return True

def guardar_resolucion_espacial(cursor, id_prueba, resultados):
    """Guarda resultados de resolución espacial - SOLO CAMPOS EXISTENTES"""
    datos_resumen, lista_regiones = mapear_resolucion_espacial(resultados)  # ✅ DESEMPAQUETAR CORRECTAMENTE
    if not datos_resumen or not lista_regiones:
        return False
    
    # 1. Guardar resumen en tabla principal
    cursor.execute("""
        INSERT INTO resolucion_espacial (
            id_prueba, regiones_analizadas, regiones_exitosas, lp_mm_maximo,
            ultima_region_exitosa, gap_size_minimo_cm, num_picos_totales,
            mtf_10_pct, mtf_20_pct, mtf_50_pct
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        id_prueba,
        datos_resumen["regiones_analizadas"],
        datos_resumen["regiones_exitosas"],
        datos_resumen["lp_mm_maximo"],
        datos_resumen["ultima_region_exitosa"],
        datos_resumen["gap_size_minimo_cm"],
        datos_resumen["num_picos_totales"],
        datos_resumen["mtf_10_pct"],
        datos_resumen["mtf_20_pct"],
        datos_resumen["mtf_50_pct"]
    ))
    
    # 2. Guardar detalles por región
    for region in lista_regiones:
        cursor.execute("""
            INSERT INTO resolucion_espacial_regiones (
                id_prueba, region_nombre, lp_mm, peak_mean, valley_mean,
                gap_size_cm, n_peaks_used, n_valleys_used, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            id_prueba,
            region["region_nombre"],
            region["lp_mm"],
            round(region["peak_mean"], 3) if region["peak_mean"] is not None else None,
            round(region["valley_mean"], 3) if region["valley_mean"] is not None else None,
            round(region["gap_size_cm"], 3) if region["gap_size_cm"] is not None else None,
            region["n_peaks_used"],
            region["n_valleys_used"],
            region["status"]
        ))
    
    #print(f"  ✓ Resolución espacial guardada para prueba {id_prueba}")
    return True

def guardar_valores_ct(cursor, id_prueba, resultados):
    """Guarda resultados de valores CT - SOLO CAMPOS EXISTENTES"""
    datos = mapear_valores_ct(resultados)
    if not datos:
        return False
    
    # Mapeo de nombres de materiales a IDs (según INSERT en crearTablasCatphan)
    mapeo_materiales = {
        "Aire": 1, "PMP": 2, "LDPE": 3, "Polystyrene": 4,
        "Acrilico": 5, "Delrin": 6, "Teflon": 7
    }
    
    for material_data in datos:
        material_nombre = material_data["material"]  # ✅ CORREGIR: usar "material"
        id_material = mapeo_materiales.get(material_nombre)
        
        if not id_material:
            #print(f"⚠️  Material desconocido: {material_nombre}")
            continue
            
        cursor.execute("""
            INSERT INTO valores_ct (
                id_prueba, id_material, promedio_hu, error_absoluto, error_relativo
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            id_prueba,
            id_material,
            material_data["promedio_hu"],
            material_data["error_absoluto"],
            material_data["error_relativo"]
        ))
    
    #print(f"  ✓ Valores CT guardados para prueba {id_prueba}")
    return True

def guardar_linealidad_ct(cursor, id_prueba, resultados):
    """
    Guarda los resultados de linealidad CT en la base de datos.
    
    Args:
        cursor: Cursor de la base de datos
        id_prueba (int): ID de la prueba
        resultados (dict): Resultados de la función linealidad_ct()
    """
    if not resultados:
        #print("No hay resultados de linealidad CT para guardar")
        return False
    
    try:
        # Mapear los resultados usando la función existente
        datos_mapeados = mapear_linealidad_ct(resultados)
        
        # Insertar en la tabla linealidad_ct
        sql_insert = """
            INSERT INTO linealidad_ct (
                id_prueba, pendiente, intercepto, r_cuadrado, 
                referencia, escala_contraste, num_materiales, 
                rango_hu_min, rango_hu_max, linealidad_aceptable
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        valores = (
            id_prueba,
            datos_mapeados["pendiente"],
            datos_mapeados["intercepto"],
            datos_mapeados["r_cuadrado"],
            datos_mapeados["referencia"],
            datos_mapeados["escala_contraste"],
            datos_mapeados["num_materiales"],
            datos_mapeados["rango_hu_min"],
            datos_mapeados["rango_hu_max"],
            datos_mapeados["linealidad_aceptable"]
        )
        
        cursor.execute(sql_insert, valores)
        #print(f"✓ Linealidad CT guardada para prueba {id_prueba}")
        return True
        
    except Exception as e:
        #print(f"✗ Error guardando linealidad CT: {e}")
        return False

def guardar_uniformidad(cursor, id_prueba, resultados):
    """Guarda resultados de uniformidad - SOLO CAMPOS EXISTENTES"""
    datos_global, regiones_detalle = mapear_uniformidad(resultados)  # DESEMPAQUETAR correctamente
    if not datos_global or not regiones_detalle:
        return False
    
    #  Mapeo de regiones a IDs
    mapeo_regiones = {
        "Centro": 1, "Arriba": 2, "Derecha": 3, "Abajo": 4, "Izquierda": 5  # "Arriba" no "Superior", "Abajo" no "Inferior"
    }
    
    # 1. Guardar datos por región
    for region_data in regiones_detalle:  # Usa la variable desempaquetada
        region_nombre = region_data["region_nombre"]
        id_region = mapeo_regiones.get(region_nombre)
        
        if not id_region:
            #print(f"⚠️  Región desconocida: {region_nombre}")
            continue
            
        cursor.execute("""
            INSERT INTO uniformidad_ruido (
                id_prueba, id_region, hu_promedio, desviacion
            ) VALUES (?, ?, ?, ?)
        """, (
            id_prueba,
            id_region,
            round(region_data["hu_promedio"], 3) if region_data["hu_promedio"] is not None else "No disponible",
            round(region_data["desviacion"], 3) if region_data["desviacion"] is not None else "No disponible"
        ))
    
    # 2. Guardar resultados globales
    cursor.execute("""
        INSERT INTO uniformidad_global (
            id_prueba, max_diferencia, desviacion_global, uniformity_index_max,
            uniformity_index_roi, integral_non_uniformity, integral_non_uniformity_pct,
            pasa_ui, pasa_inu, pasa_global, ui_threshold_pct, inu_threshold_pct,
            hu_tolerancia
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        id_prueba,
        datos_global["max_diferencia"],
        datos_global["desviacion_global"] if datos_global["desviacion_global"] is not None else "No disponible",
        datos_global["uniformity_index_max"] if datos_global["uniformity_index_max"] is not None else "No disponible",
        datos_global["uniformity_index_roi"] if datos_global["uniformity_index_roi"] is not None else "No disponible",
        datos_global["integral_non_uniformity"] if datos_global["integral_non_uniformity"] is not None else "No disponible",
        datos_global["integral_non_uniformity_pct"] if datos_global["integral_non_uniformity_pct"] is not None else "No disponible",
        datos_global["pasa_ui"] if datos_global["pasa_ui"] is not None else "No disponible",
        datos_global["pasa_inu"] if datos_global["pasa_inu"] is not None else "No disponible",
        datos_global["pasa_global"] if datos_global["pasa_global"] is not None else "No disponible",
        datos_global["ui_threshold_pct"] if datos_global["ui_threshold_pct"] is not None else "No disponible",
        datos_global["inu_threshold_pct"] if datos_global["inu_threshold_pct"] is not None else "No disponible",
        datos_global["hu_tolerancia"] if datos_global["hu_tolerancia"] is not None else "No disponible"
    ))
    
    #print(f"  ✓ Uniformidad guardada para prueba {id_prueba}")
    return True

# ------------------------------------ FUNCIÓN DE VALIDACIÓN ---------------------------------------------------

def validar_resultados_catphan(resultados_por_categoria, modo="completo"):
    """
    Valida los resultados de análisis CatPhan antes de guardar.
    
    Args:
        resultados_por_categoria (dict): Diccionario con categorías y sus resultados
        modo (str): "completo" para validar todas las categorías, "individual" para validar solo las presentes
    
    Returns:
        tuple: (es_valido, lista_errores)
    """
    errores = []
    
    # Definir categorías requeridas según el modo
    if modo == "completo":
        categorias_requeridas = ["espesor", "valores_ct", "uniformidad"]
    else:  # modo individual
        categorias_requeridas = []  # No requerir categorías específicas para guardado individual
    
    # Verificar categorías requeridas solo en modo completo
    for categoria in categorias_requeridas:
        if categoria not in resultados_por_categoria:
            errores.append(f"Falta la categoría requerida: {categoria}")
    
    # Validar cada categoría presente (independientemente del modo)
    for categoria, resultados in resultados_por_categoria.items():
        if not resultados:
            errores.append(f"La categoría '{categoria}' no tiene resultados válidos")
            continue
            
        # Validaciones específicas por categoría
        if categoria == "espesor":
            if not isinstance(resultados, dict):
                errores.append(f"Los resultados de {categoria} deben ser un diccionario")
            elif "espesor_promedio_mm" not in resultados:
                errores.append(f"Faltan datos de espesor promedio en {categoria}")
                
        elif categoria == "tamano_pixel":
            if not isinstance(resultados, dict):
                errores.append(f"Los resultados de {categoria} deben ser un diccionario")
                
        elif categoria == "valores_ct":
            if not isinstance(resultados, list):
                errores.append(f"Los resultados de {categoria} deben ser una lista")
            elif not resultados:
                errores.append(f"La lista de resultados de {categoria} está vacía")
                
        elif categoria == "uniformidad":
            if not isinstance(resultados, dict):
                errores.append(f"Los resultados de {categoria} deben ser un diccionario")
    
    return len(errores) == 0, errores

# ------------------------------------ FUNCIÓN DE CONSULTA ------------------------------------------------------ 

def consultar_pruebas_disponibles(id_sesion):
    """
    Consulta qué pruebas están disponibles para una sesión sin reconstruir los datos.    
    Returns:
        dict: Información de las pruebas disponibles
    """
    conn = None
    try:
        conn = Conexion().conectar()
        cursor = conn.cursor()
        
        filtro_p = filtro_activo('pruebas').replace("activo", "p.activo")
        cursor.execute(f"""
            SELECT p.id_prueba, p.id_tipo, tp.nombre_prueba, p.kv, p.ma, p.espesor_corte, p.created_at
            FROM pruebas p
            LEFT JOIN tipos_prueba tp ON p.id_tipo = tp.id_tipo
            WHERE p.id_sesion = ?{filtro_p}
            ORDER BY p.created_at
        """, (id_sesion,))
        
        pruebas = cursor.fetchall()
        
        if not pruebas:
            return {"sesion": id_sesion, "pruebas_disponibles": [], "total": 0}
        
        mapeo_tipos = {
            1: "espesor", 2: "tamano_pixel", 3: "resolucion_contraste",
            4: "resolucion_espacial", 5: "valores_ct", 6: "linealidad_ct", 7: "uniformidad"
        }
        
        pruebas_info = []
        for prueba in pruebas:
            id_prueba, id_tipo, nombre_prueba, kv, ma, espesor, created_at = prueba
            categoria = mapeo_tipos.get(id_tipo, f"Tipo_{id_tipo}")
            
            pruebas_info.append({
                "id_prueba": id_prueba,
                "id_tipo": id_tipo,
                "categoria": categoria,
                "nombre_prueba": nombre_prueba,
                "parametros": f"{kv}kV, {ma}mA, {espesor}mm",
                "fecha_guardado": created_at
            })
        
        return {
            "sesion": id_sesion,
            "pruebas_disponibles": pruebas_info,
            "total": len(pruebas_info),
            "categorias": [p["categoria"] for p in pruebas_info]
        }
        
    except Exception as e:
        #print(f"❌ Error al consultar pruebas disponibles: {e}")
        return {"sesion": id_sesion, "error": str(e)}
        
    finally:
        if conn:
            conn.close()

# ------------------------------------ FUNCIONES DE RECONSTRUCCIÓN -----------------------------------------------

def reconstruir_resultados_desde_bd(id_sesion, categorias=None, label=None, canvas=None):
    """
    Reconstruye la estructura de diccionarios de resultados desde la base de datos
    """
    conn = None
    try:
        conn = Conexion().conectar()
        cursor = conn.cursor()
        
        # Mapeo de tipos de prueba a nombres de categoría
        mapeo_tipos_reverso = {
            1: "espesor",           # ESPESOR_CORTE
            2: "tamano_pixel",      # TAMAÑO_PIXEL  
            3: "resolucion_contraste", # RESOLUCION_CONTRASTE
            4: "resolucion_espacial",  # RESOLUCION_ESPACIAL
            5: "valores_ct",        # VALORES_CT
            6: "linealidad_ct",     # LINEALIDAD_CT
            7: "uniformidad"        # UNIFORMIDAD_RUIDO
        }
        
        # Si no se especifican categorías, usar todas
        if categorias is None:
            categorias = list(mapeo_tipos_reverso.values())
        
        #print(f"🔍 Buscando datos para categorías: {categorias}")
        
        cursor.execute(f"""
            SELECT id_prueba, id_tipo, kv, ma, espesor_corte, imagen_path, imagen_resultado
            FROM pruebas
            WHERE id_sesion = ?{filtro_activo('pruebas')}
        """, (id_sesion,))
        
        pruebas = cursor.fetchall()
        
        if not pruebas:
            #print(f"❌ No se encontraron pruebas para la sesión: {id_sesion}")
            if label:
                label.setText("No hay datos guardados para esta categoría.")
            return {}
        
        resultados_reconstruidos = {}
        
        # Función mejorada para mostrar contenido con imagen
        def usar_label_seguro(contenido, kv=None, ma=None, espesor_corte=None, imagen_blob=None):
            if label is not None and label.parent() is not None:
                if isinstance(contenido, str):
                    # Función simplificada que actualiza label y canvas por separado
                    crear_widget_con_imagen_y_resultados(
                        contenido, imagen_blob, kv, ma, espesor_corte, label, canvas
                    )
                else:
                    # Para widgets/tablas, crear contenedor con parámetros e imagen
                    crear_widget_con_parametros_imagen_y_contenido(
                        contenido, label, kv, ma, espesor_corte, imagen_blob, canvas
                    )
            else:
                pass
                #print(f"⚠️ Label no disponible, saltando actualización UI")
        categoria_encontrada = False
        for prueba in pruebas:
            id_prueba, id_tipo, kv, ma, espesor_corte, imagen_path, imagen_resultado = prueba
            categoria = mapeo_tipos_reverso.get(id_tipo)
            
            if not categoria or categoria not in categorias:
                continue
                
            categoria_encontrada = True
            ##print(f"🔄 Reconstruyendo categoría: {categoria}")
            ##print(f"   Parámetros: kV={kv}, mA={ma}, espesor={espesor_corte}mm")
            #if imagen_resultado:
            #    #print(f"   📷 Imagen disponible: {len(imagen_resultado)} bytes")
            
            # Reconstruir según la categoría
            if categoria == "espesor":
                resultado = reconstruir_espesor_corte(cursor, id_prueba, imagen_resultado)
                texto = tabla_resultados_espesor(resultado)
                usar_label_seguro(texto, kv, ma, espesor_corte, imagen_resultado)
            elif categoria == "tamano_pixel":
                resultado = reconstruir_tamano_pixel(cursor, id_prueba, imagen_resultado)
                texto = tabla_resultados_tamano_pixel(resultado)
                usar_label_seguro(texto, kv, ma, espesor_corte, imagen_resultado)
            elif categoria == "resolucion_contraste":
                resultado = reconstruir_resolucion_contraste(cursor, id_prueba, imagen_resultado)
                contenido = tabla_resultados_resolucion_contraste(resultado)
                usar_label_seguro(contenido, kv, ma, espesor_corte, imagen_resultado)
            elif categoria == "resolucion_espacial":
                resultado = reconstruir_resolucion_espacial(cursor, id_prueba, imagen_resultado)
                contenido = tabla_resultados_resolucion_espacial(resultado)
                usar_label_seguro(contenido, kv, ma, espesor_corte, imagen_resultado)
            elif categoria == "valores_ct":
                resultado = reconstruir_valores_ct(cursor, id_prueba, imagen_resultado)
                contenido = tabla_resultados_ct(resultado)
                usar_label_seguro(contenido, kv, ma, espesor_corte, imagen_resultado)
            elif categoria == "linealidad_ct":
                resultado = reconstruir_linealidad_ct(cursor, id_prueba, imagen_resultado)
                texto = tabla_resultados_linealidad_ct(resultado)
                usar_label_seguro(texto, kv, ma, espesor_corte, imagen_resultado)
            elif categoria == "uniformidad":
                resultado = reconstruir_uniformidad(cursor, id_prueba, imagen_resultado)
                contenido = tabla_resultados_uniformidad(resultado)
                usar_label_seguro(contenido, kv, ma, espesor_corte, imagen_resultado)
            else:
                resultado = None
            
            if resultado:
                resultados_reconstruidos[categoria] = resultado
                #print(f"  ✅ {categoria} reconstruido exitosamente")
        
        # Si no se encontró ninguna categoría solicitada
        if not categoria_encontrada:
            mensaje = f"No hay datos guardados para: {', '.join(categorias)}"
            #print(f"⚠️ {mensaje}")
            if label:
                label.setText(mensaje)
        
        ##print(f"✅ Reconstrucción completada: {len(resultados_reconstruidos)} categorías")
        return resultados_reconstruidos
        
    except Exception as e:
        error_msg = f"Error al reconstruir resultados: {e}"
        #print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return {}
        
    finally:
        if conn:
            conn.close()
# ------------------------------------ FUNCIONES DE RECONSTRUCCIÓN POR PRUEBA  ------------------------------------

def reconstruir_espesor_corte(cursor, id_prueba, imagen_resultado):
    """
    Reconstruye los datos de espesor de corte desde la base de datos
    """
    cursor.execute(f"""
        SELECT espesor_promedio_mm, espesor_teorico_mm, diferencia_mm, error_pct
        FROM espesor_corte WHERE id_prueba = ?{filtro_activo('espesor_corte')}
    """, (id_prueba,))
    
    row = cursor.fetchone()
    if not row:
        return None
    
    espesor_promedio, espesor_teorico, diferencia, error_pct = row
    
    # Simular espesores individuales (no se guardan en BD, usar promedio)
    espesores_individuales = {
        "Izquierda": espesor_promedio,
        "Abajo": espesor_promedio,
        "Derecha": espesor_promedio,
        "Arriba": espesor_promedio
    }
    
    resultado = {
        "espesor_promedio_mm": espesor_promedio,
        "espesor_teorico_mm": espesor_teorico,
        "diferencia_mm": diferencia,
        "factor_correccion": 0.42,
        "num_rampas_detectadas": 4,
        "combinacion_slices": False,
        "espesores_individuales": espesores_individuales,
        "imagen_analisis": imagen_resultado  # ✅ Agregar imagen
    }
    
    return resultado

def reconstruir_tamano_pixel(cursor, id_prueba, imagen_resultado):
    """
    Reconstruye los datos de tamaño de pixel desde la base de datos
    """
    cursor.execute(f"""
        SELECT valor_teorico_dicom, X, Y, diferencia_x, diferencia_y
        FROM tamaño_pixel WHERE id_prueba = ?{filtro_activo('tamaño_pixel')}
    """, (id_prueba,))
    
    row = cursor.fetchone()
    if not row:
        return None

    (valor_teorico, x, y, diferencia_x, diferencia_y) = row

    resultado = {
        "X": x,
        "Y": x,
        "diferencia_x": diferencia_x,
        "diferencia_y": diferencia_y,
        "tam_px_teorico": valor_teorico,
        "imagen_analisis": imagen_resultado # Agregar imagen
    }
    return resultado

def reconstruir_resolucion_contraste(cursor, id_prueba, imagen_resultado):
    """Reconstruye los resultados de resolución de contraste desde la BD"""
    # 1. Obtener resumen
    cursor.execute(f"""
        SELECT rois_visibles_cnr, rois_visibles_visibilidad, total_rois, diametro_minimo_visible,
                    pasa_test_cnr, pasa_test_visibilidad, metodo_recomendado
        FROM resolucion_contraste WHERE id_prueba = ?{filtro_activo('resolucion_contraste')}
    """, (id_prueba,))
    
    resumen = cursor.fetchone()
    if not resumen:
        return None
    
    (rois_visibles_cnr, rois_visibles_visibilidad, total_rois, diametro_minimo, 
    pasa_test_cnr, pasa_test_visibilidad, metodo_recomendado) = resumen
    
    # 2. Obtener detalles por ROI
    cursor.execute(f"""
        SELECT diametro_mm, centro_x, centro_y, roi_promedio_hu, background_promedio_hu,
                contraste_michelson, cnr, snr, visibilidad_lim, pasa_cnr, pasa_visibilidad_lim
        FROM resolucion_contraste_rois WHERE id_prueba = ?{filtro_activo('resolucion_contraste_rois')}
        ORDER BY diametro_mm DESC
    """, (id_prueba,))
    
    rois = cursor.fetchall()
    
    # Reconstruir estructura de ROIs
    resultados_roi = {}
    for roi in rois:
        (diametro, centro_x, centro_y, roi_prom, bg_prom,
        contraste, cnr, snr, visibilidad, pasa_cnr, pasa_visibilidad) = roi
        
        nombre_roi = f"{diametro}mm"
        resultados_roi[nombre_roi] = {
            "centro_roi": (centro_x, centro_y),
            "diametro_mm": diametro,
            "roi_prom": roi_prom,
            "background_prom": bg_prom,
            "contraste_michelson": contraste,
            "cnr": cnr,
            "snr": snr,
            "visibilidad_lim": visibilidad,
            "pasa_cnr": pasa_cnr,
            "pasa_visibilidad_lim": pasa_visibilidad
        }
    
    resumen_dict = {
        "rois_visibles_cnr": rois_visibles_cnr,
        "rois_visibles_visibilidad_lim": rois_visibles_visibilidad,
        "total_rois": total_rois,
        "pasa_test_cnr": pasa_test_cnr,
        "pasa_test_visibilidad_lim": pasa_test_visibilidad,
        "metodo_recomendado": metodo_recomendado,
        "imagen_analisis": imagen_resultado  # ✅ RECUPERADA DE LA BD
    }
    
    return {
        "resultados_roi": resultados_roi,
        "resumen": resumen_dict
    }

def reconstruir_resolucion_espacial(cursor, id_prueba, imagen_resultado):
    """Reconstruye los resultados de resolución espacial desde la BD"""
    # 1. Obtener resumen
    cursor.execute(f"""
        SELECT regiones_analizadas, regiones_exitosas, lp_mm_maximo, ultima_region_exitosa, gap_size_minimo_cm,
                num_picos_totales, mtf_10_pct, mtf_20_pct, mtf_50_pct
        FROM resolucion_espacial WHERE id_prueba = ?{filtro_activo('resolucion_espacial')}
    """, (id_prueba,))
    
    resumen = cursor.fetchone()
    if not resumen:
        return None
    
    (regiones_analizadas, regiones_exitosas, lp_mm_maximo, ultima_region, gap_size_minimo, num_picos, mtf_10, mtf_20, mtf_50) = resumen
    
    # 2. Obtener detalles por región
    cursor.execute(f"""
        SELECT region_nombre, lp_mm, peak_mean, valley_mean, gap_size_cm, n_peaks_used, n_valleys_used, status
        FROM resolucion_espacial_regiones WHERE id_prueba = ?{filtro_activo('resolucion_espacial_regiones')}
        ORDER BY lp_mm
    """, (id_prueba,))
    
    regiones = cursor.fetchall()
    
    # Reconstruir estructura
    region_results = {}
    for region in regiones:
        (nombre, lp_mm, peak_mean, valley_mean, gap_size, n_peaks, n_valleys, status) = region
        
        region_results[nombre] = {
            "lp/mm": lp_mm,
            "peak_mean": peak_mean,
            "valley_mean": valley_mean,
            "gap_size_cm": gap_size,
            "n_peaks_used": n_peaks,
            "n_valleys_used": n_valleys,
            "status": status
        }
    
    # Reconstruir MTF
    mtf_lp_mm = {}
    if mtf_10: mtf_lp_mm["10"] = mtf_10
    if mtf_20: mtf_lp_mm["20"] = mtf_20
    if mtf_50: mtf_lp_mm["50"] = mtf_50
    
    resolucion_limite = {
        "ultima_region": ultima_region,
        "lp_mm_maximo": lp_mm_maximo,
        "gap_size_cm": gap_size_minimo
    }
    
    return {
        "region_results": region_results,
        "mtf_lp_mm": mtf_lp_mm,
        "num_picos": num_picos,
        "resolucion_limite": resolucion_limite,
        "imagen_analisis": imagen_resultado
    }

def reconstruir_valores_ct(cursor, id_prueba, imagen_resultado):
    """Reconstruye los resultados de valores CT desde la BD"""
    filtro_vc = filtro_activo('valores_ct').replace("activo", "vc.activo")
    cursor.execute(f"""
        SELECT m.nombre_material, vc.promedio_hu, vc.error_absoluto, vc.error_relativo,
                m.rango_referencia_min, m.rango_referencia_max
        FROM valores_ct vc
        JOIN materiales_ct m ON vc.id_material = m.id_material
        WHERE vc.id_prueba = ?{filtro_vc}
        ORDER BY m.id_material
    """, (id_prueba,))
    
    resultados = cursor.fetchall()
    if not resultados:
        return None
    
    valores_reconstruidos = []
    for material, promedio_hu, error_abs, error_rel, rango_min, rango_max in resultados:
        valores_reconstruidos.append({
            "material": material,
            "promedio_hu": promedio_hu,
            "error_abs": error_abs,
            "error_rel": error_rel,
            "rango_hu": [rango_min, rango_max]
        })
    
    # Agregar imagen
    if imagen_resultado:
        valores_reconstruidos.append({
            "_metadata": {
                "imagen_analisis": imagen_resultado
            }
        })
    
    return valores_reconstruidos

def reconstruir_linealidad_ct(cursor, id_prueba, imagen_resultado):
    """
    Reconstruye los resultados de linealidad CT desde la base de datos.
    
    Args:
        cursor: Cursor de la base de datos
        id_prueba (int): ID de la prueba
        imagen_resultado (bytes): Imagen del análisis en formato BLOB
    
    Returns:
        dict: Resultados reconstruidos
    """
    try:
        cursor.execute(f"""
            SELECT pendiente, intercepto, r_cuadrado, referencia, escala_contraste,
                    num_materiales, rango_hu_min, rango_hu_max, linealidad_aceptable
            FROM linealidad_ct
            WHERE id_prueba = ?{filtro_activo('linealidad_ct')}
        """, (id_prueba,))
        
        row = cursor.fetchone()
        if not row:
            return None
            
        return {
            "pendiente": row[0],
            "intercepto": row[1], 
            "r_squared": row[2],  # ✅ Mapear de vuelta a "r_squared"
            "referencia": row[3],
            "escala_contraste": row[4],
            "num_materiales": row[5],
            "rango_hu_min": row[6], 
            "rango_hu_max": row[7],
            "linealidad_aceptable": bool(row[8]) if row[8] is not None else None,
            "imagen_analisis": imagen_resultado
        }
        
    except Exception as e:
        #print(f"Error reconstruyendo linealidad CT: {e}")
        return None

def reconstruir_uniformidad(cursor, id_prueba, imagen_resultado):
    """Reconstruye los resultados de uniformidad desde la BD"""
    # 1. Obtener datos globales
    cursor.execute(f"""
        SELECT max_diferencia, desviacion_global, uniformity_index_max, uniformity_index_roi,
                    integral_non_uniformity, integral_non_uniformity_pct, pasa_ui, pasa_inu, pasa_global
        FROM uniformidad_global WHERE id_prueba = ?{filtro_activo('uniformidad_global')}
    """, (id_prueba,))
    
    global_data = cursor.fetchone()
    if not global_data:
        return None
    
    (max_diferencia, desviacion_global, ui_max, ui_roi, inu, inu_pct, pasa_ui, pasa_inu, pasa_global) = global_data
    
    # 2. Obtener datos por región
    filtro_ur = filtro_activo('uniformidad_ruido').replace("activo", "ur.activo")
    cursor.execute(f"""
        SELECT r.nombre_region, ur.hu_promedio, ur.desviacion
        FROM uniformidad_ruido ur
        JOIN regiones_uniformidad r ON ur.id_region = r.id_region
        WHERE ur.id_prueba = ?{filtro_ur}
        ORDER BY r.id_region
    """, (id_prueba,))
    
    regiones = cursor.fetchall()
    
    # Reconstruir estructura
    resultados_uniformidad = {}
    
    # Agregar datos por región
    for nombre_region, hu_promedio, desviacion in regiones:
        resultados_uniformidad[nombre_region] = {
            "promedio_hu": hu_promedio,
            "desviacion": desviacion
        }
    
    # Agregar resumen global
    resultados_uniformidad["Uniformidad"] = {
        "max_diferencia": max_diferencia,
        "desviacion_global": desviacion_global,
        "uniformity_index_max": ui_max,
        "uniformity_index_roi": ui_roi,
        "integral_non_uniformity": inu,
        "integral_non_uniformity_pct": inu_pct,
        "pasa_ui": pasa_ui,
        "pasa_inu": pasa_inu,
        "pasa_global": pasa_global,
        "imagen_analisis": imagen_resultado 
    }
    return resultados_uniformidad

# ------------------------------------ FUNCIONES DE INTERFAZ GRÁFICA ------------------------------------

def tabla_resultados_espesor(resultados):
    if not resultados:
        return "No hay resultados de espesor disponibles."
        
    lines = []
    lines.append("🔍 RESULTADOS DE ESPESOR DE CORTE")
    lines.append("-" * 50)
    lines.append(f"  Espesor promedio: {resultados.get('espesor_promedio_mm', 'N/A')} mm")
    lines.append(f"  Espesor teórico: {resultados.get('espesor_teorico_mm', 'N/A')} mm") 
    lines.append(f"  Diferencia: {resultados.get('diferencia_mm', 'N/A')} mm")
    lines.append(f"  Factor corrección: {resultados.get('factor_correccion', 'N/A')}")
    lines.append(f"  Rampas detectadas: {resultados.get('num_rampas_detectadas', 'N/A')}")
    lines.append(f"  Combinación slices: {'Sí' if resultados.get('combinacion_slices') else 'No'}")
    
    # Mostrar espesores individuales
    espesores_ind = resultados.get("espesores_individuales", {})
    if espesores_ind:
        lines.append("")
        lines.append("  📏 Espesores individuales:")
        for direccion, valor in espesores_ind.items():
            lines.append(f"    {direccion}: {valor} mm")

    lines.append("-" * 50)
    return "\n".join(lines)

def tabla_resultados_tamano_pixel(resultados):
    if not resultados:
        return "No hay resultados de tamaño de pixel disponibles."
        
    lines = []
    lines.append("📐 RESULTADOS DE TAMAÑO DE PIXEL")
    lines.append("-" * 50)

    # Mostrar medidas individuales
    lines.append(f"  X: {resultados.get('X', 'N/A')} mm")
    lines.append(f"  Y: {resultados.get('Y', 'N/A')} mm")
    
    # Mostrar valor teórico y diferencias - TAMBIÉN VERIFICAR AQUÍ
    tam_px_teorico = resultados.get('tam_px_teorico')
    if tam_px_teorico is not None and isinstance(tam_px_teorico, (int, float)):
        lines.append(f"  Teórico: {tam_px_teorico:.3f} mm")
    else:
        lines.append(f"  Teórico: {tam_px_teorico if tam_px_teorico is not None else 'N/A'}")
        
    diferencia_x = resultados.get('diferencia_x')
    if diferencia_x is not None and isinstance(diferencia_x, (int, float)):
        lines.append(f"  Diferencia X: {diferencia_x:.3f} mm")
    else:
        lines.append(f"  Diferencia X: {diferencia_x if diferencia_x is not None else 'N/A'}")
        
    diferencia_y = resultados.get('diferencia_y')
    if diferencia_y is not None and isinstance(diferencia_y, (int, float)):
        lines.append(f"  Diferencia Y: {diferencia_y:.3f} mm")
    else:
        lines.append(f"  Diferencia Y: {diferencia_y if diferencia_y is not None else 'N/A'}")

    error_pct = resultados.get('error_pct')
    lines.append(f"  Error porcentual: {error_pct:.3f}%" if error_pct is not None else "  Error porcentual: N/A")
    
    lines.append("-" * 50)
    return "\n".join(lines)

def tabla_resultados_resolucion_contraste(resultados):
    """
    Crea una tabla simplificada mostrando solo los círculos visibles
    con su diámetro y valor de contraste/visibilidad.
    """
    # Obtener datos de los resultados
    resultados_roi = resultados.get("resultados_roi", {})
    resumen = resultados.get("resumen", {})
    
    # Filtrar solo ROIs visibles según el método recomendado (visibilidad)
    rois_visibles = {}
    for nombre, roi_data in resultados_roi.items():
        if roi_data.get("pasa_visibilidad_lim", False):
            rois_visibles[nombre] = roi_data
    
    # Crear tabla si hay ROIs visibles
    if rois_visibles:
        headers = ["Diámetro (mm)", "Contraste", "Visibilidad", "Estado"]
        tabla_contraste = QTableWidget()
        tabla_contraste.setColumnCount(len(headers))
        tabla_contraste.setRowCount(len(rois_visibles))
        tabla_contraste.setHorizontalHeaderLabels(headers)
        
        # Configurar estilo de la tabla
        tabla_contraste.setAlternatingRowColors(True)
        tabla_contraste.setSelectionBehavior(QTableWidget.SelectRows)
        tabla_contraste.setEditTriggers(QTableWidget.NoEditTriggers)
        tabla_contraste.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
                font-family: 'Segoe UI';
                color: #2c3e50;
                alternate-background-color: #f5f5f5;
            }
            QHeaderView::section {
                background-color: #e8f4f8;
                border: 1px solid #d0d0d0;
                padding: 8px;
                font-weight: bold;
                color: #34495e;
            }
        """)
        
        # Configurar redimensionamiento de columnas
        for i in range(len(headers)):
            tabla_contraste.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
        
        # Llenar datos - ordenar por diámetro descendente
        rois_ordenados = sorted(rois_visibles.items(), 
                            key=lambda x: x[1].get("diametro_mm", 0), 
                            reverse=True)
        
        for i, (nombre, roi_data) in enumerate(rois_ordenados):
            diametro = roi_data.get("diametro_mm", "N/A")
            contraste = roi_data.get("contraste_michelson", "N/A")
            visibilidad = roi_data.get("visibilidad_lim", "N/A")
            
            # Formatear valores
            diametro_str = f"{diametro}" if diametro != "N/A" else "N/A"
            contraste_str = f"{contraste:.3f}" if contraste != "N/A" and contraste is not None else "N/A"
            visibilidad_str = f"{visibilidad:.3f}" if visibilidad != "N/A" and visibilidad is not None else "N/A"
            
            # Insertar datos con centrado
            item_diametro = QTableWidgetItem(diametro_str)
            item_diametro.setTextAlignment(Qt.AlignCenter)
            tabla_contraste.setItem(i, 0, item_diametro)
            
            item_contraste = QTableWidgetItem(contraste_str)
            item_contraste.setTextAlignment(Qt.AlignCenter)
            tabla_contraste.setItem(i, 1, item_contraste)
            
            item_visibilidad = QTableWidgetItem(visibilidad_str)
            item_visibilidad.setTextAlignment(Qt.AlignCenter)
            tabla_contraste.setItem(i, 2, item_visibilidad)
            
            # Estado (siempre visible ya que filtramos)
            item_estado = QTableWidgetItem("✓ Visible")
            item_estado.setTextAlignment(Qt.AlignCenter)
            item_estado.setForeground(QColor("#27ae60"))  # Verde
            font_estado = item_estado.font()
            font_estado.setBold(True)
            item_estado.setFont(font_estado)
            tabla_contraste.setItem(i, 3, item_estado)
        
        # Ajustar altura
        tabla_contraste.resizeRowsToContents()
        tabla_contraste.setMaximumHeight(250)
        
        # Crear widget contenedor con información adicional
        contenedor = QWidget()
        layout_contenedor = QVBoxLayout(contenedor)
        
        # Agregar información de resumen
        info_resumen = QLabel(
            f"✅ Círculos detectados: {len(rois_visibles)}/{resumen.get('total_rois', 'N/A')} | "
            f"Método: Visibilidad (Rose) | "
            f"Umbral: {resumen.get('visibility_threshold', 'N/A')}"
        )
        info_resumen.setAlignment(Qt.AlignCenter)
        info_resumen.setStyleSheet("""
            QLabel {
                color: #27ae60;
                font-size: 12px;
                font-weight: bold;
                padding: 8px;
                background-color: #eafaf1;
                border: 2px solid #a9dfbf;
                border-radius: 6px;
                margin-bottom: 5px;
            }
        """)
        
        layout_contenedor.addWidget(info_resumen)
        layout_contenedor.addWidget(tabla_contraste)
        layout_contenedor.setContentsMargins(0, 0, 0, 0)
        layout_contenedor.setSpacing(5)
        
        return contenedor
    else:
        # Si no hay ROIs visibles, crear un widget con mensaje
        no_visible_widget = QWidget()
        layout = QVBoxLayout(no_visible_widget)
        
        mensaje = QLabel("⚠️ No se detectaron círculos de contraste visibles")
        mensaje.setAlignment(Qt.AlignCenter)
        mensaje.setStyleSheet("""
            QLabel {
                color: #e74c3c;
                font-size: 14px;
                font-weight: bold;
                padding: 20px;
                background-color: #fdf2f2;
                border: 2px solid #fadbd8;
                border-radius: 8px;
            }
        """)
        
        # Agregar información del resumen
        info_resumen = QLabel(
            f"Método: Visibilidad (Rose) | "
            f"Umbral: {resumen.get('visibility_threshold', 'N/A')} | "
            f"ROIs analizados: {resumen.get('total_rois', 'N/A')}"
        )
        info_resumen.setAlignment(Qt.AlignCenter)
        info_resumen.setStyleSheet("""
            QLabel {
                color: #7f8c8d;
                font-size: 11px;
                padding: 10px;
            }
        """)
        
        layout.addWidget(mensaje)
        layout.addWidget(info_resumen)
        no_visible_widget.setMaximumHeight(120)
        
        return no_visible_widget

def tabla_resultados_resolucion_espacial(resultados):
    headers = ["Región", "lp/mm", "N° Picos","N° Valles", "Gap Size (cm)"]
    tabla_ct = QTableWidget()
    
    # Obtener datos válidos primero
    region_results = resultados.get("region_results", {})
    regiones = {"region 1": "Región 1", "region 2": "Región 2", "region 3": "Región 3", "region 4": "Región 4",
                "region 5": "Región 5", "region 6": "Región 6", "region 7": "Región 7", "region 8": "Región 8"}
    
    # FILTRAR SOLO REGIONES CON DATOS VÁLIDOS
    regiones_validas = {}
    max_lp_mm = -1
    region_maxima = None
    
    for region, res in region_results.items():
        lp_mm = res.get('lp/mm', -1)
        num_peaks = res.get("n_peaks_used", "N/A")
        num_valleys = res.get("n_valleys_used", "N/A")
        gap_size_cm = res.get("gap_size_cm", "N/A")
        
        # Verificar que todos los datos sean válidos (no N/A) y que lp/mm sea un número
        datos_completos = (
            isinstance(lp_mm, (int, float)) and lp_mm > 0 and
            num_peaks != "N/A" and isinstance(num_peaks, (int, float)) and
            num_valleys != "N/A" and isinstance(num_valleys, (int, float)) and
            gap_size_cm != "N/A" and isinstance(gap_size_cm, (int, float))
        )
        
        # SOLO AGREGAR SI TIENE DATOS COMPLETOS
        if datos_completos:
            regiones_validas[region] = res
            if lp_mm > max_lp_mm:
                max_lp_mm = lp_mm
                region_maxima = region
    
    #print(f"Regiones con datos válidos: {list(regiones_validas.keys())}")
    #print(f"Región máxima detectada: {region_maxima} con lp/mm = {max_lp_mm}")
    
    # Usar solo las regiones válidas para crear la tabla
    tabla_ct.setColumnCount(len(headers))
    tabla_ct.setRowCount(len(regiones_validas))  # ← Solo regiones válidas
    tabla_ct.setHorizontalHeaderLabels(headers)
    
    # Configurar el estilo de la tabla
    tabla_ct.setAlternatingRowColors(True)
    tabla_ct.setSelectionBehavior(QTableWidget.SelectRows)
    tabla_ct.setEditTriggers(QTableWidget.NoEditTriggers)
    tabla_ct.setStyleSheet("""
        QTableWidget {
            gridline-color: #d0d0d0;
            background-color: white;
            font-family: 'Segoe UI';
            color: #2c3e50;
            alternate-background-color: #f5f5f5;
        }
        QHeaderView::section {
            background-color: #e8f4f8;
            border: 1px solid #d0d0d0;
            padding: 8px;
            font-weight: bold;
            color: #34495e;
        }
    """)
    
    # Configurar redimensionamiento de columnas
    for i in range(len(headers)):
        tabla_ct.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)

    # Llenar datos SOLO CON REGIONES VÁLIDAS
    for i, (region, res) in enumerate(regiones_validas.items()):
        lp_mm = res.get('lp/mm','N/A')
        num_peaks = res.get("n_peaks_used", "N/A")
        num_valleys = res.get("n_valleys_used", "N/A")
        gap_size_cm = res.get("gap_size_cm", "N/A")
        
        # Formatear valores (ya sabemos que son válidos)
        lp_mm_str = f"{round(lp_mm, 2)}"
        num_peaks_str = str(num_peaks)
        num_valleys_str = str(num_valleys)
        gap_size_str = f"{round(gap_size_cm, 2)}"

        # Insertar datos en la tabla CON CENTRADO
        item_region = QTableWidgetItem(str(regiones.get(region, region)))
        item_region.setTextAlignment(Qt.AlignCenter)
        tabla_ct.setItem(i, 0, item_region)
        
        item_lp = QTableWidgetItem(lp_mm_str)
        item_lp.setTextAlignment(Qt.AlignCenter)
        tabla_ct.setItem(i, 1, item_lp)
        
        item_peaks = QTableWidgetItem(num_peaks_str)
        item_peaks.setTextAlignment(Qt.AlignCenter)
        tabla_ct.setItem(i, 2, item_peaks)
        
        item_valleys = QTableWidgetItem(num_valleys_str)
        item_valleys.setTextAlignment(Qt.AlignCenter)
        tabla_ct.setItem(i, 3, item_valleys)
        
        item_gap = QTableWidgetItem(gap_size_str)
        item_gap.setTextAlignment(Qt.AlignCenter)
        tabla_ct.setItem(i, 4, item_gap)

        # RESALTAR SOLO LA REGIÓN MÁXIMA
        if region == region_maxima:
            #print(f"Resaltando región: {region} (fila {i}) - MÁXIMA resolución con datos completos")
            for col in range(len(headers)):
                item = tabla_ct.item(i, col)
                if item is not None:
                    item.setBackground(QColor("#9aedc8"))  # Verde claro
                    item.setFont(QFont("Segoe UI", weight=QFont.Bold))
                    item.setForeground(QColor("#24c950"))  # Texto verde

    # Ajustar altura de filas al contenido
    tabla_ct.resizeRowsToContents()
    tabla_ct.setMaximumHeight(300)
    return tabla_ct

def tabla_resultados_ct(resultado_completo):
    """
    Crea una QTableWidget con los resultados de Valores CT.
    """
    # Extraer la lista de resultados del diccionario
    if isinstance(resultado_completo, dict) and "resultados" in resultado_completo:
        resultados = resultado_completo["resultados"]
    else:
        # Compatibilidad hacia atrás si se pasa directamente la lista
        resultados = resultado_completo
        
    headers = ["Material", "Promedio HU", "Rango HU Ref.", "Desviación. (HU)", "Rango"]
    tabla_ct = QTableWidget()
    tabla_ct.setColumnCount(len(headers))
    tabla_ct.setRowCount(len(resultados) - 1)  # Excluir el último elemento si es metadata
    tabla_ct.setHorizontalHeaderLabels(headers)
    
    # Configurar el estilo de la tabla
    tabla_ct.setAlternatingRowColors(True)
    tabla_ct.setSelectionBehavior(QTableWidget.SelectRows)
    tabla_ct.setEditTriggers(QTableWidget.NoEditTriggers)
    tabla_ct.setStyleSheet("""
        QTableWidget {
            gridline-color: #d0d0d0;
            background-color: white;
            font-family: 'Segoe UI';
            color: #2c3e50;
            alternate-background-color: #f5f5f5;
        }
        QHeaderView::section {
            background-color: #e8f4f8;
            border: 1px solid #d0d0d0;
            padding: 8px;
            font-weight: bold;
            color: #34495e;
        }
    """)
    
    # Configurar redimensionamiento de columnas
    for i in range(len(headers)):
        tabla_ct.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)

    materiales = {"Acrilico": "Acrílico", "Teflon": "Teflón"}

    # Llenar datos CON CENTRADO
    for i, res in enumerate(resultados[:-1]):
        material = materiales.get(str(res.get("material", "")), str(res.get("material", "")))
        promedio = res.get("promedio_hu", "")
        rango = res.get("rango_hu", ["N/A", "N/A"])
        err_abs = res.get("error_abs", "N/A")
        err_rel = res.get("error_rel", "N/A")
        
        # Formatear valores
        promedio_str = f"{round(promedio, 1)}" if promedio else "N/A"
        rango_str = f"{rango[0]} a {rango[1]}" if rango[0] is not None and rango[1] is not None else "N/A"
        err_abs_str = str(err_abs) if err_abs is not None else "N/A"
        err_rel_str = str(err_rel) if err_rel is not None else "N/A"

        # Insertar datos en la tabla CON CENTRADO
        item_material = QTableWidgetItem(material)
        item_material.setTextAlignment(Qt.AlignCenter)
        tabla_ct.setItem(i, 0, item_material) 
        
        item_promedio = QTableWidgetItem(promedio_str)
        item_promedio.setTextAlignment(Qt.AlignCenter)
        tabla_ct.setItem(i, 1, item_promedio)
        
        item_rango = QTableWidgetItem(rango_str)
        item_rango.setTextAlignment(Qt.AlignCenter)
        tabla_ct.setItem(i, 2, item_rango)
        
        item_err_abs = QTableWidgetItem(err_abs_str)
        item_err_abs.setTextAlignment(Qt.AlignCenter)
        tabla_ct.setItem(i, 3, item_err_abs)
        
        item_err_rel = QTableWidgetItem(err_rel_str)
        item_err_rel.setTextAlignment(Qt.AlignCenter)
        tabla_ct.setItem(i, 4, item_err_rel)

    # Ajustar altura de filas al contenido
    tabla_ct.resizeRowsToContents()
    tabla_ct.setMaximumHeight(300)
    
    return tabla_ct

def tabla_resultados_linealidad_ct(resultados):
    """
    Genera una tabla de texto con los resultados de linealidad CT.
    
    Args:
        resultados (dict): Resultados de linealidad CT
        
    Returns:
        str: Texto formateado con los resultados
    """
    if not resultados:
        return "No hay resultados de linealidad CT disponibles."
        
    lines = []
    lines.append("📈 RESULTADOS DE LINEALIDAD CT")
    lines.append("-" * 50)
    
    # Mostrar parámetros de la regresión
    pendiente = resultados.get('pendiente')
    if pendiente is not None:
        lines.append(f"  Pendiente: {pendiente:.3f}")
    else:
        lines.append(f"  Pendiente: N/A")
        
    intercepto = resultados.get('intercepto') 
    if intercepto is not None:
        lines.append(f"  Intercepto: {intercepto:.3f}")
    else:
        lines.append(f"  Intercepto: N/A")
        
    r_cuadrado = resultados.get('r_squared')
    if r_cuadrado is not None:
        lines.append(f"  R²: {r_cuadrado:.4f}")
    else:
        lines.append(f"  R²: N/A")
        
    referencia = resultados.get('referencia')
    if referencia is not None:
        lines.append(f"  Referencia: {referencia:.6f}")
    else:
        lines.append(f"  Referencia: N/A")
        
    escala_contraste = resultados.get('escala_contraste')
    if escala_contraste is not None:
        lines.append(f"  Escala de contraste: {escala_contraste:.6f}")
    else:
        lines.append(f"  Escala de contraste: N/A")
    
    # Mostrar evaluación de calidad
    linealidad_aceptable = resultados.get('linealidad_aceptable')
    if linealidad_aceptable is not None:
        estado = "✓ ACEPTABLE" if linealidad_aceptable else "✗ NO ACEPTABLE"
        lines.append(f"  Linealidad: {estado}")
    
    lines.append("-" * 50)
    return "\n".join(lines)

def tabla_resultados_uniformidad(uniformidad):
    headers = ["Posición", "Promedio HU", "Desviación"]
    tabla_un = QTableWidget()
    
    # Filtrar datos válidos excluyendo "Uniformidad"
    datos_validos = {k: v for k, v in uniformidad.items() 
                    if k != "Uniformidad" and isinstance(v, dict) and 
                    "promedio_hu" in v and "desviacion" in v and 
                    v["promedio_hu"] is not None}
    
    tabla_un.setColumnCount(len(headers))
    tabla_un.setRowCount(len(datos_validos) + 3)  # +3 para filas adicionales
    tabla_un.setHorizontalHeaderLabels(headers)

    # Configurar el estilo de la tabla
    tabla_un.setAlternatingRowColors(True)
    tabla_un.setSelectionBehavior(QTableWidget.SelectRows)
    tabla_un.setEditTriggers(QTableWidget.NoEditTriggers)
    tabla_un.setStyleSheet("""
        QTableWidget {
            gridline-color: #d0d0d0;
            background-color: white;
            font-family: 'Segoe UI';
            color: #2c3e50;
            alternate-background-color: #f5f5f5;
        }
        QHeaderView::section {
            background-color: #e8f4f8;
            border: 1px solid #d0d0d0;
            padding: 8px;
            font-weight: bold;
            color: #34495e;
        }
    """)
    
    # Configurar redimensionamiento de columnas
    for i in range(len(headers)):
        tabla_un.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
    
    # Llenar datos usando índices enteros
    fila_actual = 0
    for pos, res in datos_validos.items():
        item_pos = QTableWidgetItem(str(pos))
        item_pos.setTextAlignment(Qt.AlignCenter)
        tabla_un.setItem(fila_actual, 0, item_pos)
        
        item_promedio = QTableWidgetItem(str(round(res["promedio_hu"], 1)))
        item_promedio.setTextAlignment(Qt.AlignCenter)
        tabla_un.setItem(fila_actual, 1, item_promedio)
        
        item_desviacion = QTableWidgetItem(str(round(res["desviacion"], 1)))
        item_desviacion.setTextAlignment(Qt.AlignCenter)
        tabla_un.setItem(fila_actual, 2, item_desviacion)
        
        fila_actual += 1

    # Agregar datos de uniformidad global si existe
    if "Uniformidad" in uniformidad:
        u = uniformidad["Uniformidad"]
        inu_pct = u.get("integral_non_uniformity_pct")
        ui_max = u.get("uniformity_index_max")

        # ---------------------------- Fila para "No uniformidad integral" ----------------------------
        tabla_un.setSpan(fila_actual, 0, 1, 3)  # Combinar columnas 0 y 1
        item_inu = QTableWidgetItem(f"No uniformidad integral: {inu_pct:.2f}%" if isinstance(inu_pct, (int, float)) else "No uniformidad integral: N/A")
        item_inu.setTextAlignment(Qt.AlignCenter)
        # Poner el texto en negrita y azul:
        font_inu = item_inu.font()
        font_inu.setBold(True)
        item_inu.setFont(font_inu)
        item_inu.setForeground(QColor("#00B2BC"))  # Azul
        tabla_un.setItem(fila_actual, 0, item_inu)

        fila_actual += 1
        # -------------------------------------------------------------------------------------------

        # ---------------------------- Fila para "Índice de uniformidad" ----------------------------
        tabla_un.setSpan(fila_actual, 0, 1, 3)  # Combinar columnas 0 y 1
        item_ui = QTableWidgetItem(f"Índice de uniformidad (|UI|max): {ui_max:.2f}%" if isinstance(ui_max, (int, float)) else "Índice de uniformidad (|UI|max): N/A")
        item_ui.setTextAlignment(Qt.AlignCenter)
        tabla_un.setItem(fila_actual, 0, item_ui)
        font_ui = item_ui.font()
        font_ui.setBold(True)
        item_ui.setFont(font_ui)
        item_ui.setForeground(QColor("#00B2BC"))  # Azul
        fila_actual += 1

        # -------------------------------------------------------------------------------------------

        # Fila adicional con información extra (máx diferencia, desviación global, pasa)
        tabla_un.setSpan(fila_actual, 0, 1, 3)  # Combinar las 3 columnas
        info_extra = (f"Máx diferencia: {u.get('max_diferencia','N/A')} HU | "
                    f"Desv. global: {u.get('desviacion_global','N/A')} | "
                    f"Pasa (UI/INU): {u.get('pasa_global','N/A')}")
        item_extra = QTableWidgetItem(info_extra)
        item_extra.setTextAlignment(Qt.AlignCenter)
        font_extra = item_extra.font()
        font_extra.setBold(True)
        item_extra.setFont(font_extra)
        item_extra.setForeground(QColor("#00B2BC"))  # Azul
        # -------------------------------------------------------------------------------------------

        tabla_un.setItem(fila_actual, 0, item_extra)
        
    tabla_un.setMaximumHeight(300)  # Limitar altura máxima
    return tabla_un

def reemplazar_resultados_texto_con_tabla(contenido, label):
    """
    Reemplaza el contenido de un QLabel con el contenido proporcionado.
    Maneja strings, QTableWidget y QWidget contenedores.
    
    Args:
        contenido: Puede ser un string, QTableWidget o QWidget
        label: El QLabel que se va a actualizar o reemplazar
    """
    from PyQt5.QtWidgets import QTableWidget, QLabel, QWidget
    
    try:
        if label is None:
            #print("❌ Label es None, no se puede actualizar")
            return
            
        # Si es texto, simplemente actualizar el label
        if isinstance(contenido, str):
            label.setText(contenido)
            label.setStyleSheet("""
                QLabel { 
                    font-family: 'Segoe UI'; 
                    font-size: 15px; 
                    color: #2c3e50; 
                    background-color: #f8f9fa;
                    padding: 10px; 
                    border: 1px solid #dee2e6;
                    border-radius: 5px; 
                }
            """)
            #print("✅ Texto actualizado en QLabel")
            return
            
        # Si es una tabla o widget, intentar reemplazar
        if isinstance(contenido, (QTableWidget, QWidget)):
            parent_widget = label.parent()
            if parent_widget is None:
                #print("❌ No se pudo obtener el widget padre del QLabel")
                # Como fallback, mostrar mensaje en el label
                widget_type = "tabla" if isinstance(contenido, QTableWidget) else "widget"
                label.setText(f"Resultados mostrados en {widget_type} (padre no disponible)")
                return
                
            parent_layout = parent_widget.layout()
            if parent_layout is None:
                #print("❌ No se pudo obtener el layout padre")
                # Como fallback, mostrar mensaje en el label
                widget_type = "tabla" if isinstance(contenido, QTableWidget) else "widget"
                label.setText(f"Resultados mostrados en {widget_type} (layout no disponible)")
                return
            
            # Obtener la posición del QLabel en el layout
            index = -1
            for i in range(parent_layout.count()):
                item = parent_layout.itemAt(i)
                if item and item.widget() == label:
                    index = i
                    break
            
            if index == -1:
                #print("❌ No se encontró la posición del QLabel en el layout")
                # Como fallback, mantener el label pero cambiar el texto
                widget_type = "tabla" if isinstance(contenido, QTableWidget) else "widget"
                label.setText(f"Resultados mostrados en {widget_type}")
                return
            
            # Remover el QLabel actual
            label.setParent(None)
            
            # Insertar el contenido en la misma posición
            parent_layout.insertWidget(index, contenido)
            
            widget_type = "tabla" if isinstance(contenido, QTableWidget) else "widget"
            #print(f"✅ {widget_type.capitalize()} insertado correctamente en lugar del QLabel")
            
        else:
            #print(f"❌ Tipo no soportado para reemplazar: {type(contenido)}")
            label.setText(f"Error: Tipo de resultado no soportado ({type(contenido).__name__})")
            
    except Exception as e:
        #print(f"❌ Error al reemplazar resultados_texto: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback: mostrar error en el label
        if label is not None:
            try:
                label.setText(f"Error al mostrar resultados: {str(e)}")
            except:
                pass
        if label is None:
            #print("❌ Label es None, no se puede actualizar")
            return
            
        # Si es texto, simplemente actualizar el label
        if isinstance(contenido, str):
            label.setText(contenido)
            label.setStyleSheet("""
                QLabel { 
                    font-family: 'Segoe UI'; 
                    font-size: 15px; 
                    color: #2c3e50; 
                    background-color: #f8f9fa;
                    padding: 10px; 
                    border: 1px solid #dee2e6;
                    border-radius: 5px; 
                }
            """)
            #print("✅ Texto actualizado en QLabel")
            return
            
        # Si es una tabla o widget, intentar reemplazar
        if isinstance(contenido, (QTableWidget, QWidget)):
            parent_widget = label.parent()
            if parent_widget is None:
                #print("❌ No se pudo obtener el widget padre del QLabel")
                # Como fallback, mostrar mensaje en el label
                widget_type = "tabla" if isinstance(contenido, QTableWidget) else "widget"
                label.setText(f"Resultados mostrados en {widget_type} (padre no disponible)")
                return
                
            parent_layout = parent_widget.layout()
            if parent_layout is None:
                #print("❌ No se pudo obtener el layout padre")
                # Como fallback, mostrar mensaje en el label
                widget_type = "tabla" if isinstance(contenido, QTableWidget) else "widget"
                label.setText(f"Resultados mostrados en {widget_type} (layout no disponible)")
                return
            
            # Obtener la posición del QLabel en el layout
            index = -1
            for i in range(parent_layout.count()):
                item = parent_layout.itemAt(i)
                if item and item.widget() == label:
                    index = i
                    break
            
            if index == -1:
                #print("❌ No se encontró la posición del QLabel en el layout")
                # Como fallback, mantener el label pero cambiar el texto
                widget_type = "tabla" if isinstance(contenido, QTableWidget) else "widget"
                label.setText(f"Resultados mostrados en {widget_type}")
                return
            
            # Remover el QLabel actual
            label.setParent(None)
            
            # Insertar el contenido en la misma posición
            parent_layout.insertWidget(index, contenido)
            
            widget_type = "tabla" if isinstance(contenido, QTableWidget) else "widget"
            #print(f"✅ {widget_type.capitalize()} insertado correctamente en lugar del QLabel")
            
        else:
            #print(f"❌ Tipo no soportado para reemplazar: {type(contenido)}")
            label.setText(f"Error: Tipo de resultado no soportado ({type(contenido).__name__})")
            
    except Exception as e:
        #print(f"❌ Error al reemplazar resultados_texto: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback: mostrar error en el label
        if label is not None:
            try:
                label.setText(f"Error al mostrar resultados: {str(e)}")
            except:
                pass