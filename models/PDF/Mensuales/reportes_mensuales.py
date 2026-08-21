from PyQt5.QtSql import QSqlQuery
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QPixmap
import tempfile
import pandas as pd
try:
    from utils import resource_path
except Exception:
    import importlib.util, os
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
    utils_path = os.path.join(project_root, 'utils.py')
    if os.path.isfile(utils_path):
        spec = importlib.util.spec_from_file_location('utils', utils_path)
        utils = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(utils)
        resource_path = getattr(utils, 'resource_path')
    else:
        raise
from models.PDF.pdf import generar_reporte_pdf_multitabla_mensual
from models.PDF.PDFWindow import PdfViewer
from services.anulacion import filtro_activo

class ReporteMensual:
    """Clase para generar reportes PDF de controles mensuales"""
    
    def __init__(self):
        self.tablas_por_maquina = {
            'Clinac 600': {
                'principal': 'controles',
                'tablas_relacionadas': [
                    'indicadores_brazo',
                    'indicadores_angulares_colimador', 
                    'tamano_campo',
                    'preguntas',
                    'equipos_medicion',
                    'dosimetriaMen',
                    'control_cunas',  # Solo cuñas
                    'analisis_placa_franjas',
                    'analisis_placa_verificaciones',
                    'analisis_placa_correcciones'
                ],
                'accesorios': ['cunas']  # Solo cuñas
            },
            'Clinac ix': {
                'principal': 'controles',
                'tablas_relacionadas': [
                    'indicadores_brazo',
                    'indicadores_angulares_colimador',
                    'tamano_campo', 
                    'preguntas',
                    'equipos_medicion',
                    'dosimetriaMen',  # Múltiples registros por energía
                    'control_cunas',  # Cuñas
                    'control_conos',  # Y conos
                    'analisis_placa_franjas',
                    'analisis_placa_verificaciones',
                    'analisis_placa_correcciones'
                ],
                'accesorios': ['cunas', 'conos'],  # Ambos
                'energias': ['6MV', '15MV', '6MeV', '9MeV', '12MeV', '15MeV']
            },
            'Halcyon': {
                'principal': 'controles',
                'tablas_relacionadas': [
                    'HC_indicadores_brazo',
                    'HC_indicadores_colimador',
                    'HC_indicadores_laser',
                    'HC_indicadores_camilla',
                    'HC_tamanos_campo_radiacion',
                    'equipos_medicion',
                    'dosimetriaMen',
                    'HC_desplazamiento_isocentro_mensual'
                    # No tiene control_cunas ni control_conos
                ],
                'accesorios': []  # Sin accesorios
            },
            'Tomógrafo': {  # <--- AGREGAR ESTA SECCIÓN
                'principal': 'controles',
                'tablas_relacionadas': [
                    'pruebas',  # Tabla principal de pruebas CatPhan/TAC
                    'espesor_corte',
                    'tamaño_pixel',
                    'resolucion_contraste',
                    'resolucion_espacial',
                    'materiales_ct',
                    'valores_ct',
                    'uniformidad_ruido',
                    'uniformidad_global',
                    'linealidad_ct',
                ],
                'accesorios': []
            },
            'Braquiterapia': {
                'principal': 'TipoCalibracion',
                'tablas_relacionadas': [
                    'SistemaMedicion',
                    'CondicionesMedicion',
                    'MaximosCamaras',
                    'LecturasMaximos',
                    'ResultadosActividad'
                ],
                'accesorios': []
            }
        }

def guardarPDF_mensual(self, fecha, maquina="", id_maquina="", 
                        tipo_reporte='Control Mensual', diccionario={}, umbrales=None):
    """Función para guardar PDF de control mensual"""

    reporte_mensual(self, fecha, maquina, id_maquina, 
                        tipo_reporte, diccionario, umbrales, f"control_mensual_{maquina}_{fecha}.pdf")

def reporte_mensual(self, fecha, maquina="", id_maquina="", 
                    tipo_reporte='Control Mensual', diccionario={}, 
                    umbrales=None, file_name=""):
    """Genera reporte PDF completo de control mensual"""
    
    # Verificar máquina soportada
    if maquina not in ['Clinac 600', 'Clinac ix', 'Halcyon', 'Tomógrafo', 'Braquiterapia']:
        QMessageBox.critical(self, "Error", f"Máquina {maquina} no soportada para reportes mensuales")
        return
    
    # Obtener configuración de tablas
    config_tablas = ReporteMensual().tablas_por_maquina[maquina]
    
    try:
        # Conectar a base de datos
        db = self.opeenDatabase()
        
        # Buscar registro principal (depende del tipo de máquina)
        if maquina == 'Braquiterapia':
            ref_id = _obtener_referencia_braquiterapia(db, fecha, tipo_reporte)
        else:
            ref_id = _obtener_referencia_principal(db, fecha, maquina)
        
        if not ref_id:
            QMessageBox.critical(self, "Error", 
                                f"No se encontró control mensual para {maquina} en {fecha}")
            return
        
        # Recopilar datos de todas las tablas
        datos_completos = _recopilar_datos_completos(db, ref_id, config_tablas, maquina)
        
        # Obtener información del usuario (usuario 1 y usuario 2 si existe)
        usuario_info = _obtener_info_usuario(db, datos_completos.get('user_id', ''), datos_completos.get('user_id_f2'))
        print(f"Información de usuario obtenida: {usuario_info}")
        # Procesar datos para el reporte (múltiples tablas)
        tablas_reporte = _procesar_datos_para_reporte(datos_completos, diccionario, umbrales, maquina, tipo_reporte)
        
        # Generar y mostrar PDF
        _generar_mostrar_pdf_multitabla(self, tablas_reporte, fecha, maquina, id_maquina, 
                                        tipo_reporte, usuario_info, datos_completos)
        db.close()
        
    except Exception as e:
        QMessageBox.critical(self, "Error", f"Error generando reporte: {str(e)}")
        print(f"Error en reporte_mensual: {e}")
        import traceback
        traceback.print_exc()

def _obtener_referencia_principal(db, fecha, maquina):
    """Obtiene el ID de referencia del control mensual"""
    query = QSqlQuery(db)
    # LR3 (DA-47/DA-48): lectura de BLOQUE, igual que su gemela anual.
    query.prepare(
        "SELECT id FROM controles WHERE fecha = ? AND equipo = ? "
        f"AND control = 'Mensual'{filtro_activo('controles')} ORDER BY id DESC")
    query.addBindValue(fecha)
    query.addBindValue(maquina)
    
    if query.exec() and query.next():
        return query.value(0)
    return None

def _obtener_referencia_braquiterapia(db, fecha, tipo_reporte):
    query = QSqlQuery(db)
    
    if tipo_reporte == 'Linealidad Braquiterapia' or 'Linealidad' in tipo_reporte:
        query.prepare(f"""
            SELECT id FROM LinealidadBraquiterapia 
            WHERE DATE(fecha) = ?{filtro_activo('LinealidadBraquiterapia')}
            ORDER BY id DESC LIMIT 1
        """)
        query.addBindValue(fecha)
    else:
        # Buscar primero por fecha Y tipo exacto
        query.prepare(f"""
            SELECT id FROM TipoCalibracion 
            WHERE DATE(fecha) = ? AND tipo = ?{filtro_activo('TipoCalibracion')}
            ORDER BY id DESC LIMIT 1
        """)
        query.addBindValue(fecha)
        query.addBindValue(tipo_reporte)
        
        if query.exec() and query.next():
            return query.value(0)
        
        # Si no encuentra por tipo, buscar solo por fecha (cualquier tipo de braquiterapia)
        query.prepare(f"""
            SELECT id FROM TipoCalibracion 
            WHERE DATE(fecha) = ?{filtro_activo('TipoCalibracion')}
            ORDER BY id DESC LIMIT 1
        """)
        query.addBindValue(fecha)
    
    if query.exec() and query.next():
        return query.value(0)
    
    return None

def _recopilar_datos_completos(db, ref_id, config_tablas, maquina):
    """Recopila datos de todas las tablas relacionadas"""
    datos_completos = {'ref_id': ref_id, 'maquina': maquina, "control": "Mensual"}
    
    # Obtener datos de tabla principal (varía según máquina)
    if maquina == 'Braquiterapia':
        # Verificar si es Linealidad intentando obtener de LinealidadBraquiterapia
        datos_linealidad = _obtener_datos_linealidad_braquiterapia(db, ref_id)
        if datos_linealidad:
            # Es un registro de Linealidad
            datos_completos.update(datos_linealidad)
            return datos_completos  # Linealidad no tiene tablas relacionadas
        else:
            # Es Control Mensual/Cambio de Fuente
            datos_principal = _obtener_datos_tabla_principal_braquiterapia(db, ref_id)
    else:
        datos_principal = _obtener_datos_tabla_principal(db, ref_id)
    datos_completos.update(datos_principal)
    
    # Obtener datos de tablas relacionadas
    for tabla in config_tablas['tablas_relacionadas']:
        # Para dosimetriaMen del iX, obtener todos los registros por energía
        if tabla == 'dosimetriaMen' and maquina == 'iX':
            datos_tabla = _obtener_datos_dosimetria_ix(db, ref_id)
        else:
            datos_tabla = _obtener_datos_tabla_relacionada(db, ref_id, tabla)
        datos_completos[tabla] = datos_tabla
    
    return datos_completos

def _obtener_datos_tabla_principal(db, ref_id):
    """Obtiene datos de la tabla controles"""
    query = QSqlQuery(db)
    query.prepare("SELECT * FROM controles WHERE id = ?")
    query.addBindValue(ref_id)
    
    if query.exec() and query.next():
        datos = {
            'equipo': query.value('equipo'),
            'fecha': query.value('fecha'), 
            'user_id': query.value('user_id'),
            'user_id_f2': query.value('user_id_f2')
        }
        print(f"Datos tabla principal obtenidos: {datos}")
        return datos
    return {}

def _obtener_datos_tabla_principal_braquiterapia(db, ref_id):
    """Obtiene datos de la tabla TipoCalibracion para braquiterapia"""
    query = QSqlQuery(db)
    query.prepare("SELECT * FROM TipoCalibracion WHERE id = ?")
    query.addBindValue(ref_id)
    
    if query.exec() and query.next():
        datos = {
            'equipo': 'Braquiterapia',  # Asignar nombre fijo
            'fecha': query.value('fecha'),
            'user_id': query.value('user'),
            'user_id_f2': None,  # Braquiterapia no tiene segundo usuario
            'tipo': query.value('tipo'),
            'serie': query.value('serie'),
            'certificado': query.value('certificado'),
            'fecha_cer': query.value('fecha_cer'),
            'intensidad': query.value('intensidad'),
            'conversion': query.value('conversion')
        }
        print(f"Datos tabla principal braquiterapia obtenidos: {datos}")
        return datos
    return {}

def _obtener_datos_linealidad_braquiterapia(db, ref_id):
    """Obtiene datos de la tabla LinealidadBraquiterapia"""
    query = QSqlQuery(db)
    query.prepare("SELECT * FROM LinealidadBraquiterapia WHERE id = ?")
    query.addBindValue(ref_id)
    
    if query.exec() and query.next():
        datos = {
            'equipo': 'Braquiterapia',
            'fecha': query.value('fecha'),
            'user_id': query.value('user'),
            'user_id_f2': None,
            'tipo': 'Linealidad',
            # Sistema de medición
            'modelo': query.value('modelo'),
            'serie_cp': query.value('serie_cp'),
            'calibracion': query.value('calibracion'),
            'modelo_elec': query.value('modelo_elec'),
            'serie_ele': query.value('serie_ele'),
            'electrometro': query.value('electrometro'),
            # Carga colectada
            'q_est': query.value('q_est'),
            't_integrado': query.value('t_integrado'),
            'i_est': query.value('i_est'),
            # Reproducibilidad
            'repro_m1': query.value('repro_m1'),
            'repro_m2': query.value('repro_m2'),
            'repro_m3': query.value('repro_m3'),
            'repro_m4': query.value('repro_m4'),
            'repro_m5': query.value('repro_m5'),
            'repro_prom': query.value('repro_prom'),
            # Resultados
            'reproducibilidad': query.value('reproducibilidad'),
            'exactitud': query.value('exactitud'),
            'tiempo_transito': query.value('tiempo_transito'),
            # Datos de linealidad (10 puntos)
            'datos_linealidad': []
        }
        
        # Extraer los 10 puntos de medición de linealidad
        for i in range(10):
            punto = {
                'tp': query.value(f'lin_tp_{i}'),
                'q1': query.value(f'lin_q1_{i}'),
                'q2': query.value(f'lin_q2_{i}'),
                'qprom': query.value(f'lin_qprom_{i}'),
                'te': query.value(f'lin_te_{i}')
            }
            datos['datos_linealidad'].append(punto)
        
        print(f"Datos linealidad braquiterapia obtenidos: {datos.keys()}")
        return datos
    return {}

def _obtener_datos_tabla_relacionada(db, ref_id, tabla):
    """Obtiene datos de una tabla relacionada específica"""
    query = QSqlQuery(db)
    # LE1/LE2 (PLAN_CONTRATO_GUARDADO_13-08.md §6-LE): `tabla` recorre
    # `tablas_por_maquina` (mezcla tablas del bloque de QC con otras que no
    # lo son) -- filtro_activo() no hace nada si `tabla` no está en la
    # lista blanca, así que este único punto cubre equipos_medicion,
    # tamano_campo, dosimetriaMen, control_cunas/conos,
    # analisis_placa_franjas y las 4 HC_* de Halcyon sin distinguir caso
    # por caso.
    query.prepare(f"SELECT * FROM {tabla} WHERE ref = ?{filtro_activo(tabla)}")
    query.addBindValue(ref_id)
    
    datos = []
    if query.exec():
        while query.next():
            record = {}
            for i in range(query.record().count()):
                field_name = query.record().fieldName(i)
                record[field_name] = query.value(i)
            datos.append(record)
    
    return datos

def _obtener_datos_dosimetria_ix(db, ref_id):
    """Obtiene datos de dosimetría para iX (múltiples energías)"""
    query = QSqlQuery(db)
    # Asumiendo que hay un campo 'energia' en dosimetriaMen para identificar cada energía
    # LE1 (PLAN_CONTRATO_GUARDADO_13-08.md §6-LE1): dosimetriaMen empieza a
    # versionar con DO1 -- sin este filtro, un bloque anulado saldría
    # impreso en el PDF junto al vigente.
    query.prepare(f"SELECT * FROM dosimetriaMen WHERE ref = ?{filtro_activo('dosimetriaMen')} ORDER BY energia")
    query.addBindValue(ref_id)
    
    datos_por_energia = []
    if query.exec():
        while query.next():
            record = {}
            for i in range(query.record().count()):
                field_name = query.record().fieldName(i)
                record[field_name] = query.value(i)
            datos_por_energia.append(record)
    
    return datos_por_energia

def _obtener_info_usuario(db, user_id, user_id_f2=None):
    """Obtiene información del usuario principal y del usuario 2 (si existe) incluyendo firma"""
    info = {}

    # Usuario principal (por fullname)
    query = QSqlQuery(db)
    query.prepare("SELECT firma, role FROM users WHERE fullname = ?")
    query.addBindValue(user_id)
    print(f"Buscando información del usuario principal: {user_id}")
    
    if query.exec() and query.next():
        firma = query.value(0)
        rol = query.value(1)
        temp_image_path = None
        if firma:
            pixmap = QPixmap()
            pixmap.loadFromData(firma)
            temp_fd, temp_image_path = tempfile.mkstemp(suffix=".png")
            pixmap.save(temp_image_path, "PNG")
        info['usuario1'] = {
            'usuario': user_id,
            'rol': rol,
            'firma_path': temp_image_path
        }
    else:
        print(f"Usuario principal {user_id} no encontrado en la base de datos.")
        info['usuario1'] = {'usuario': user_id, 'rol': '', 'firma_path': None}

    # Usuario 2 (por id)
    if user_id_f2:
        query2 = QSqlQuery(db)
        query2.prepare("SELECT firma, role FROM users WHERE fullname = ?")
        query2.addBindValue(user_id_f2)
        print(f"Buscando información del usuario 2 con ID: {user_id_f2}")
        
        if query2.exec() and query2.next():
            firma2 = query2.value(0)
            rol2 = query2.value(1)
            temp_image_path2 = None
            if firma2:
                pixmap2 = QPixmap()
                pixmap2.loadFromData(firma2)
                temp_fd2, temp_image_path2 = tempfile.mkstemp(suffix=".png")
                pixmap2.save(temp_image_path2, "PNG")
            info['usuario2'] = {
                'usuario': user_id_f2,
                'rol': rol2,
                'firma_path': temp_image_path2
            }
        else:
            print(f"Usuario 2 con ID {user_id_f2} no encontrado en la base de datos.")
            info['usuario2'] = {'usuario': str(user_id_f2), 'rol': '', 'firma_path': None}
    
    return info

def _procesar_datos_para_reporte(datos_completos, diccionario, umbrales, maquina, tipo_reporte='Control Mensual'):
    """Procesa y estructura los datos para múltiples tablas del reporte"""
    
    # Crear estructura de tablas
    tablas_reporte = {}
    
    # Para braquiterapia, usar estructura diferente
    if maquina == 'Braquiterapia':
        # Determinar si es Linealidad o Control Mensual/Cambio de Fuente
        if tipo_reporte == 'Linealidad Braquiterapia' or datos_completos.get('tipo') == 'Linealidad':
            # Reporte de Linealidad
            tablas_reporte['sistema_medicion_linealidad'] = _crear_tabla_sistema_medicion_linealidad(datos_completos)
            tablas_reporte['carga_colectada'] = _crear_tabla_carga_colectada(datos_completos)
            tablas_reporte['medidas_linealidad'] = _crear_tabla_medidas_linealidad(datos_completos)
            tablas_reporte['resultados_linealidad'] = _crear_tabla_resultados_linealidad(datos_completos)
            tablas_reporte['grafico_linealidad'] = _crear_grafico_linealidad(datos_completos)
        else:
            # Reporte de Control Mensual/Cambio de Fuente
            tablas_reporte['tipo_calibracion'] = _crear_tabla_tipo_calibracion(datos_completos)
            tablas_reporte['sistema_medicion'] = _crear_tabla_sistema_medicion(datos_completos)
            tablas_reporte['condiciones_medicion'] = _crear_tabla_condiciones_medicion(datos_completos)
            tablas_reporte['maximos_camaras'] = _crear_tabla_maximos_camaras(datos_completos.get('MaximosCamaras', []))
            tablas_reporte['lecturas_maximos'] = _crear_tabla_lecturas_maximos(datos_completos.get('LecturasMaximos', []))
            tablas_reporte['resultados_actividad'] = _crear_tabla_resultados_actividad(datos_completos.get('ResultadosActividad', []))
            # Agregar gráficos
            tablas_reporte['grafico_maximos'] = _crear_grafico_maximos_camaras(datos_completos.get('MaximosCamaras', []))
            tablas_reporte['grafico_lecturas'] = _crear_grafico_lecturas_maximos(datos_completos.get('LecturasMaximos', []))
        return tablas_reporte
    
    # Tabla 1: Equipos de medición
    tablas_reporte['equipos'] = _crear_tabla_equipos(datos_completos.get('equipos_medicion', []), maquina)
    
    # Tabla 2: Seguridad (Control de cuñas/conos según máquina)
    if maquina in ['Clinac 600', 'Clinac ix']:
        tablas_reporte['seguridad'] = _crear_tabla_seguridad(datos_completos, maquina)
    
    # Tabla 3: Aspectos mecánicos (indicadores angulares del gantry)
    tablas_reporte['aspectos_mecanicos_gantry'] = _crear_tabla_indicadores_angulares_g(datos_completos, maquina)
    
    # Tabla 3b: Aspectos mecánicos (indicadores angulares del colimador)
    tablas_reporte['aspectos_mecanicos_colimador'] = _crear_tabla_indicadores_angulares_c(datos_completos, maquina)

    # Tabla 4: Preguntas (campos y valores)
    tablas_reporte['preguntas'] = _crear_tabla_preguntas(datos_completos.get('preguntas', []))
    
    # Tabla 5: Tamaños de campo
    if maquina == 'Halcyon':
        tablas_reporte['tamanos_campo'] = __crear_tabla_tamanos_campo_dosis_halcyon(datos_completos.get('HC_tamanos_campo_radiacion', []))
    else:
        tablas_reporte['tamanos_campo'] = _crear_tabla_tamanos_campo(datos_completos.get('tamano_campo', []))
    
    # Tabla 6: Análisis de imagen (solo para 600 e iX)
    if maquina in ['Clinac 600', 'Clinac ix']:
        tablas_reporte['analisis_imagen'] = _crear_tabla_analisis_imagen(datos_completos)
        tablas_reporte['imagen'] = _crear_espacio_imagen(datos_completos.get('preguntas', []))
    
    # Tabla 7: Aspectos dosimétricos
    if maquina == 'Clinac ix':
        tablas_reporte['dosimetricos'] = _crear_tabla_dosimetria_ix(datos_completos.get('dosimetriaMen', []), umbrales)
    else:
        tablas_reporte['dosimetricos'] = _crear_tabla_dosimetria(datos_completos.get('dosimetriaMen', []), umbrales)
    
    if maquina == 'Halcyon':
        tablas_reporte['desplazamiento_isocentro'] = _crear_tabla_desplazamiento_isocentro(datos_completos, maquina)
        tablas_reporte['indicadores_laser'] = _crear_tabla_indicadores_laser(datos_completos, maquina)
        tablas_reporte['indicadores_camilla'] = _crear_tabla_indicadores_camilla(datos_completos, maquina)
        
    return tablas_reporte

def _crear_tabla_equipos(equipos_data, maquina):
    """Crea la Tabla 1: Equipos de medición"""
    tabla = []
    
    # Encabezado
    #tabla.append(['EQUIPOS DE MEDICIÓN'])
    #tabla.append([''])  # Espacio

    # Formato de la tabla:
    # Tipo de equipo                   Modelo     Serie                Factor de calibración
    #--------------------------------------------------------------------------------------------
    # "Camára principal fotones", "# del modelo", "<# del serie>",     "# del factor (Gy/nC)"
    #--------------------------------------------------------------------------------------------
    # "Cámara secundaria",        "# del modelo", "<# del serie>",     "# del factor (Gy/nC)"
    #--------------------------------------------------------------------------------------------
    # "Electrómetro",             "# del modelo", "<# del serie>",     "# del factor (nC/Lectura)"
    #--------------------------------------------------------------------------------------------
    # Fila de encabezados de columna

    # Filas de datos
    tabla.append(['Tipo de equipo', 'Modelo', 'Serie', 'Factor de calibración'])
    if maquina != 'Clinac ix':
        nombres = ['Cámara principal fotones', 'Cámara secundaria', 'Electrómetro']
    else:
        nombres = ['Cámara principal fotones', 'Cámara principal electrones', 'Cámara secundaria', 'Electrómetro']

    unidades_fc = {'Cámara principal fotones': 'Gy/nC', 
                    'Cámara secundaria': 'Gy/nC', 
                    'Cámara principal electrones': 'Gy/nC',
                    'Electrómetro': 'nC/Lectura'}
    for i, equipo in enumerate(equipos_data):
        tipo = nombres[i] if i < len(nombres) else equipo.get('tipo', '')
        modelo = equipo.get('model', '')
        serie = equipo.get('serie', '')
        # Quitar el emoji no reconocido en serie
        if "⚠️" in serie:
            print("Reemplazando emoji en número de serie del equipo")
            # Formato para mostrar el emoji correctamente
            serie = serie.replace("⚠️", "!!").strip()
        factor = equipo.get('calibr_fact', '')
        tabla.append([tipo, modelo, serie, f'{factor} {unidades_fc.get(tipo, "")}'])
    return pd.DataFrame(tabla, columns=['Equipos de medición', '', '', ''])

def _crear_tabla_seguridad(datos_completos, maquina):
    """Crea la Tabla 2: Seguridad (Control de cuñas/conos)"""
    import pandas as pd
    tabla = []
    if maquina == 'Clinac ix':
        # Control de conos para iX
        tabla.append(['Cono', 'Estado'])
        conos_data = datos_completos.get('control_conos', [])
        medidas_cono = ['6x6', '10x10', '15x15', '20x20', '25x25']
        for medida in medidas_cono:
            cono = next((c for c in conos_data if c.get('medida') == medida), None)
            if cono:
                valor = cono.get('valor', '')
                estado = 'Funciona' if valor == 1 else 'No funciona' if valor == 0 else ''
            else:
                estado = ''
            tabla.append([medida, estado])
        # Encabezado explícito
        df = pd.DataFrame(tabla, columns=['Control de conos', ''])  # Saltar la fila de título
        return df

    elif maquina == 'Clinac 600' or maquina == 'Clinac ix':
        # Control de cuñas para 600 e iX
        encabezado = ['Cuña', 'In', 'Out', 'Right', 'Left']
        tabla.append(encabezado)
        cunas_data = datos_completos.get('control_cunas', [])
        angulos = ['15°', '30°', '45°', '60°']
        for angulo in angulos:
            # angulo no es un string y no tiene el símbolo °
            cuna = next((c for c in cunas_data if c.get('angulo') == int(angulo.replace('°', ''))), None) 
            if cuna:
                in_val = 'Funciona' if cuna.get('in_val') == 1 else 'No funciona'
                out_val = 'Funciona' if cuna.get('out_val') == 1 else 'No funciona'
                right_val = 'Funciona' if cuna.get('right_val') == 1 else 'No funciona'
                left_val = 'Funciona' if cuna.get('left_val') == 1 else 'No funciona'
            else:
                in_val = out_val = right_val = left_val = ''
            tabla.append([angulo, in_val, out_val, right_val, left_val])
        # Siempre usar encabezado explícito
        df = pd.DataFrame(tabla, columns=['Control de cuñas', '', '', '', ''])
        return df

    else:
        tabla.append(['Sin controles de seguridad requeridos'])
        return pd.DataFrame(tabla, columns=['Información'])

def _crear_tabla_indicadores_angulares_g(datos_completos, maquina):
    """Crea la Tabla 3: Aspectos mecánicos (indicadores angulares)"""
    tabla = []   
    niveles_brazo = ['0°', '90°', '180°', '270°']
    if maquina != "Halcyon":
        tabla.append(['Nivel', 'Indicador consola', 'Indicador equipo', 'Indicador mecánico'])     
        brazo_data = datos_completos.get('indicadores_brazo', [])
        
        for nivel in niveles_brazo:
            indicador = next((i for i in brazo_data if str(i.get('nivel', '')) == nivel), None) # asume que nivel es string y ya tiene el símbolo °
            
            if indicador:
                consola = indicador.get('indicador_luminoso_consola', '')
                equipo = indicador.get('indicador_luminoso_equipo', '')
                mecanico = indicador.get('indicador_mecanico', 'NA')
            else:
                consola = equipo = mecanico = ''
            
            tabla.append([nivel, consola, equipo, mecanico])

        return pd.DataFrame(tabla, columns=['Indicadores angulares gantry', '', '', ''])
    else:
        tabla.append(['Nivel', 'Indicador consola', 'Diferencia'])     
        brazo_data = datos_completos.get('HC_indicadores_brazo', [])
        for nivel in niveles_brazo:
            # Extrae el número del string, por ejemplo '90°' -> 90
            nivel_num = int(nivel.replace('°', ''))
            # Busca el registro cuyo nivel (REAL) coincide con el número
            indicador = next((i for i in brazo_data if int(float(i.get('nivel', 0))) == nivel_num), None)
            if indicador:
                consola = indicador.get('valor_medido', '')
                diferencia = indicador.get('discrepancia', 'NA')
            else:
                consola = diferencia = ''

            tabla.append([nivel, consola, diferencia])

        return pd.DataFrame(tabla, columns=['Indicadores angulares gantry', '', ''])

def _crear_tabla_indicadores_angulares_c(datos_completos, maquina):
    """Crea la Tabla 3: Aspectos mecánicos (indicadores angulares)"""
    tabla = []    
    niveles_colimador = ['0°', '90°', '270°']
    # Indicadores angulares del colimador    
    if maquina != "Halcyon":
        tabla.append(['Nivel', 'Indicador consola', 'Indicador equipo', 'Indicador mecánico'])
        colimador_data = datos_completos.get('indicadores_angulares_colimador', [])
        
        for nivel in niveles_colimador:
            indicador = next((i for i in colimador_data if str(i.get('nivel', ''))  == nivel), None)
            
            if indicador:
                consola = indicador.get('indicador_luminoso_consola', '')
                equipo = indicador.get('indicador_luminoso_equipo', '')
                mecanico = indicador.get('indicador_mecanico', 'NA')
            else:
                consola = equipo = mecanico = ''
            
            tabla.append([nivel, consola, equipo, mecanico])
        
        return pd.DataFrame(tabla, columns=['Indicadores angulares colimador', '', '', ''])
    
    else:
        tabla.append(['Nivel', 'Indicador consola', 'Diferencia'])
        colimador_data = datos_completos.get('HC_indicadores_colimador', [])
        
        for nivel in niveles_colimador:
            # Extrae el número del string, por ejemplo '90°' -> 90
            nivel_num = int(nivel.replace('°', ''))
            # Busca el registro cuyo nivel (REAL) coincide con el número
            indicador = next((i for i in colimador_data if int(float(i.get('nivel', 0))) == nivel_num), None)
            if indicador:
                consola = indicador.get('valor_medido', '')
                diferencia = indicador.get('discrepancia', 'NA')
            else:
                consola = diferencia = ''

            tabla.append([nivel, consola, diferencia])

        return pd.DataFrame(tabla, columns=['Indicadores angulares colimador', '', ''])

def _crear_tabla_preguntas(preguntas_data):
    """Crea la Tabla 4: Preguntas (campos y valores)"""
    tabla = []
    
    if preguntas_data:
        pregunta = preguntas_data[0]  
        
        campos = [
            ('Tamaño Isocentro mecánico', 'iso_mec'),
            ('Centrado del retículo', 'reticulo_cent'),
            ('Verticalidad de la camilla - Rango', 'camilla_vert_rango'),
            ('Verticalidad de la camilla - Desplazamiento', 'camilla_vert_desp'),
            ('Desplazamiento del Isocentro de la camilla', 'camilla_iso_desp'),
            ('Telémetro - Rango', 'telem_rango'),
            ('Telémetro - Desplazamiento', 'telem_desp'),
            ('Coincidencia puntero mecánico - telémetro óptico', 'puntero_telem_diff'),
            ('Láser techo', 'laser_techo'),
            ('Láser lateral 270°', 'laser_lateral27'),
            ('Láser lateral 90°', 'laser_lateral9'),
            ('Observaciones', 'observaciones')
        ]
        
        tabla.append(['Campo', 'Resultado'])
        for descripcion, campo_bd in campos:
            valor = pregunta.get(campo_bd, '')
            tabla.append([descripcion, str(valor)])

    return pd.DataFrame(tabla, columns=['Resultados aspectos mecánicos', ''])

def _crear_tabla_tamanos_campo(tamano_data):
    """Crea la Tabla 5: Tamaños de campo con estructura de encabezados agrupados"""
    tabla = []
    # Fila 0: Encabezados principales
    tabla.append([
        "Campo nominal\n(cm x cm)", "Indicador del equipo", "", "", "", "Indicador de la consola", "", "", ""
    ])
    # Fila 1: Sub-encabezados "Largo" y "Ancho"
    tabla.append([
        "", "Largo", "", "Ancho", "", "Largo", "", "Ancho", ""
    ])
    # Fila 2: Sub-encabezados Y1, Y2, X1, X2
    tabla.append([
        "", "Y1", "Y2", "X1", "X2", "Y1", "Y2", "X1", "X2"
    ])

    # Filas de datos para cada campo nominal
    campos_nominales = ['5 x 5', '10 x 10', '15 x 15', '20 x 20']
    for campo_nom in campos_nominales:
        # Buscar datos para este campo
        campo = next((c for c in tamano_data if c.get('campo_nominal', '') == campo_nom), None)
        if campo:
            ie_y1 = campo.get('ie_largoy1', '')
            ie_y2 = campo.get('ie_largoy2', '')
            ie_x1 = campo.get('ie_anchox1', '')
            ie_x2 = campo.get('ie_anchox2', '')
            ic_y1 = campo.get('ic_largoy1', '')
            ic_y2 = campo.get('ic_largoy2', '')
            ic_x1 = campo.get('ic_anchox1', '')
            ic_x2 = campo.get('ic_anchox2', '')
        else:
            ie_y1 = ie_y2 = ie_x1 = ie_x2 = ic_y1 = ic_y2 = ic_x1 = ic_x2 = ''
        tabla.append([
            campo_nom, ie_y1, ie_y2, ie_x1, ie_x2, ic_y1, ic_y2, ic_x1, ic_x2
        ])

    # Definir columnas apropiadas (solo para pandas, el PDF usará los spans)
    columnas = [
        "Tamaño de campo", "", "", "", "", "", "", "", ""
    ]
    return pd.DataFrame(tabla, columns=columnas)

def __crear_tabla_tamanos_campo_dosis_halcyon(tamano_data):
    #print("Creando tabla de tamaños de campo para Halcyon")
    #print(tamano_data)
    """Crea la Tabla 5: Tamaños de campo para Halcyon con encabezados agrupados"""
    tabla = []
    # Fila 0: Encabezados agrupados
    tabla.append([
        "Indicador del equipo", "", "Tamaño Medido", ""
    ])
    # Fila 1: Sub-encabezados
    tabla.append([
        "CrossPlane (cm)", "Inplane (cm)", "CrossPlane (cm)", "Inplane (cm)"
    ])
    # Filas de datos
    nominal = [5, 10, 20]
    for n in nominal:
        campo = next((c for c in tamano_data if int(round(float(c.get('indicado_inplane', 0)))) == n), None)
        if campo:
            ie_crossplane = campo.get('indicado_crossplane', '')
            ie_inplane = campo.get('indicado_inplane', '')
            ic_crossplane = campo.get('medido_crossplane', '')
            ic_inplane = campo.get('medido_inplane', '')
        else:
            ie_crossplane = ie_inplane = ic_crossplane = ic_inplane = ''
        tabla.append([ie_crossplane, ie_inplane, ic_crossplane, ic_inplane])
    columnas = [
        "Tamaño del equipo", "", "", ""
    ]
   # print("Tabla generada para Halcyon:")
    for fila in tabla:
        pass
        #   print(fila, "->", len(fila), "columnas")
    # print("Columnas:", columnas, "->", len(columnas), "columnas")
    return pd.DataFrame(tabla, columns=columnas)

def _crear_tabla_analisis_imagen(datos_completos):
    """Crea la Tabla 6: Análisis de imagen"""
    import re
    
    franjas_data = datos_completos.get('analisis_placa_franjas', [])
    
    if not franjas_data:
        return pd.DataFrame([['No hay datos de análisis de imagen']], columns=['Información'])
    
    # Ordenar por número de franja
    franjas_data.sort(key=lambda f: int(re.search(r"\d+", f.get('franja', '0')).group()))
    
    franja_labels = [f.get('franja', '') for f in franjas_data]
    
    caracteristicas = [
        ("Tam. Campo H", lambda f: f.get('ancho_media_h')),
        ("Tam. Campo V", lambda f: f.get('ancho_media_v')),
        ("Penumbra Izq. H", lambda f: f.get('penumbra_izq_h')),
        ("Penumbra Izq. V", lambda f: f.get('penumbra_izq_v')),
        ("Penumbra Der. H", lambda f: f.get('penumbra_der_h')),
        ("Penumbra Der. V", lambda f: f.get('penumbra_der_v')),
        ("Diferencia Camp. 1", lambda f: f.get('diferencia_arriba_izq')),
        ("Diferencia Camp. 2", lambda f: f.get('diferencia_arriba_der')),
        ("Diferencia Camp. 3", lambda f: f.get('diferencia_abajo_izq')),
        ("Diferencia Camp. 4", lambda f: f.get('diferencia_abajo_der')),
    ]
    
    tabla = []

    # Encabezados
    headers = ['Característica'] + franja_labels
    tabla.append(headers)
    
    # Datos
    for nombre, getter in caracteristicas:
        fila = [nombre]
        for franja_data in franjas_data:
            valor = getter(franja_data)
            if valor is None or valor == '':
                fila.append('No Disponible')
            else:
                # Intentar convertir a float si es string
                try:
                    if isinstance(valor, str):
                        valor_num = float(valor)
                        fila.append(f'{valor_num:.3f}')
                    else:
                        fila.append(f'{valor:.3f}')
                except (ValueError, TypeError):
                    # Si no se puede convertir, usar el valor tal cual
                    fila.append(str(valor))
        
        # Completar fila si faltan columnas
        while len(fila) < len(headers):
            fila.append('')
        
        tabla.append(fila)
    
    # Crear DataFrame con columnas apropiadas
    columnas = ['Característica'] + [f'Franja_{i+1}' for i in range(len(franja_labels))]
    return pd.DataFrame(tabla, columns=['Análisis de imagen'] + [''] * (len(columnas) - 1))

def _crear_espacio_imagen(preguntas_data):
    """Crea un espacio reservado para imágenes en el reporte"""
    pregunta = preguntas_data[0]
    imagen  = pregunta.get('imagen', '')
    # Convertir de BLOB a QPixmap si es necesario
    if imagen:
        pixmap = QPixmap() # Crear pixmap desde datos BLOB
        pixmap.loadFromData(imagen) # Cargar datos en pixmap
        # Guardar pixmap en archivo temporal
        temp_fd, temp_image_path = tempfile.mkstemp(suffix=".png")
        pixmap.save(temp_image_path, "PNG")
        imagen = temp_image_path # Ruta temporal de la imagen
    else:
        imagen = None
    
    tabla = []
    tabla.append([imagen]) # Solo una celda con la ruta de la imagen

    return pd.DataFrame(tabla, columns=['Imagen'])

def _crear_tabla_dosimetria(dosimetria_data, umbrales):
    """Crea la Tabla 7: Aspectos dosimétricos (600 y Halcyon)"""
    tabla = []
    tabla.append([' HACES DE FOTONES'])
    
    if dosimetria_data:
        dosi = dosimetria_data[0]
        
        # Energía nominal
        energia = dosi.get('energia', '6 MV')
        tabla.append([f'Energía Nominal: {energia.replace("mv", " MV")}'])
        
        # Dosis de referencia
        dosis_ref = dosi.get('dosis_ref_cgy_um', '')
        disc_dosis = dosi.get('discrepancia_dosis', '')
        # Usar espacios no separables (\u00A0) para mantener el espaciado
        tabla.append([f'Dosis de referencia medida (cGy/UM): {dosis_ref}\u00A0\u00A0\u00A0\u00A0Discrepancia (%): {disc_dosis}\u00A0\u00A0\u00A0\u00A0Tolerancia (%): 2'])
        
        # Calidad
        calidad = dosi.get('calidad_pdd20_10', '')
        disc_calidad = dosi.get('discrepancia_calidad', '')
        tabla.append([f'Calidad (PDD20/10): {calidad}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Discrepancia (%): {disc_calidad}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Tolerancia (%): 2'])
        
        # Simetría
        sim_in = dosi.get('simetria_inplane', '')
        sim_cross = dosi.get('simetria_crossplane', '')
        tabla.append([f'Simetría Inplane: {sim_in}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Simetría Crossplane: {sim_cross}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Tolerancia (%): 2'])
        
        # Planicidad
        plan_in = dosi.get('planicidad_inplane', '')
        plan_cross = dosi.get('planicidad_crossplane', '')
        tabla.append([f'Planicidad Inplane: {plan_in}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Planicidad Crossplane: {plan_cross}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Tolerancia (%): 3'])
    
    return pd.DataFrame(tabla, columns=['Dosimetría'])

def _crear_tabla_dosimetria_ix(dosimetria_data, umbrales):
    """Crea la Tabla 7: Aspectos dosimétricos (iX con múltiples energías)"""
    tabla = []
    tabla.append(['1. HACES DE FOTONES'])
    
    # Energías fotones
    energias_fotones = ['6MV', '15MV']
    
    for energia in energias_fotones:
        # Buscar datos para esta energía
        datos_energia = next((d for d in dosimetria_data if d.get('energia') == energia.lower()), None)
        
        if datos_energia:
            tabla.append([f'Energía Nominal: {energia.replace("mv", " MV")}'])
            
            # Dosis de referencia
            dosis_ref = datos_energia.get('dosis_ref_cgy_um', '')
            disc_dosis = datos_energia.get('discrepancia_dosis', '')
            tabla.append([f'Dosis de referencia medida (cGy/UM): {dosis_ref}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Discrepancia (%): {disc_dosis}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Tolerancia (%): 2'])
            
            # Calidad
            calidad = datos_energia.get('calidad_pdd20_10', '')
            disc_calidad = datos_energia.get('discrepancia_calidad', '')
            tabla.append([f'Calidad (PDD20/10): {calidad}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Discrepancia (%): {disc_calidad}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Tolerancia (%): 2'])
            
            # Simetría
            sim_in = datos_energia.get('simetria_inplane', '')
            sim_cross = datos_energia.get('simetria_crossplane', '')
            tabla.append([f'Simetría Inplane: {sim_in}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Simetría Crossplane: {sim_cross}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Tolerancia (%): 2'])
            
            # Planicidad
            plan_in = datos_energia.get('planicidad_inplane', '')
            plan_cross = datos_energia.get('planicidad_crossplane', '')
            tabla.append([f'Planicidad Inplane: {plan_in}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Planicidad Crossplane: {plan_cross}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Tolerancia (%): 3'])
    
    # Energías electrones
    tabla.append(['2. HACES DE ELECTRONES'])
    
    energias_electrones = ['6MeV', '9MeV', '12MeV', '15MeV']
    
    for energia in energias_electrones:
        # Buscar datos para esta energía
        datos_energia = next((d for d in dosimetria_data if d.get('energia') == energia.lower()), None)
        
        if datos_energia:
            tabla.append([f'Energía Nominal: {energia.replace("mev", " MeV")}'])
            
            # Dosis de referencia
            dosis_ref = datos_energia.get('dosis_ref_cgy_um', '')
            disc_dosis = datos_energia.get('discrepancia_dosis', '')
            tabla.append([f'Dosis de referencia medida (cGy/UM): {dosis_ref}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Discrepancia (%): {disc_dosis}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Tolerancia (%): 3'])
            
            # Calidad (J2/J1 para electrones)
            calidad = datos_energia.get('calidad_j2_j1', datos_energia.get('calidad_pdd20_10', ''))
            disc_calidad = datos_energia.get('discrepancia_calidad', '')
            tabla.append([f'Calidad (J2/J1): {calidad}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Discrepancia (%): {disc_calidad}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Tolerancia (%): 3'])
            
            # Simetría
            sim_in = datos_energia.get('simetria_inplane', '')
            sim_cross = datos_energia.get('simetria_crossplane', '')
            tabla.append([f'Simetría Inplane: {sim_in}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Simetría Crossplane: {sim_cross}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Tolerancia (%): 3'])
            
            # Planicidad
            plan_in = datos_energia.get('planicidad_inplane', '')
            plan_cross = datos_energia.get('planicidad_crossplane', '')
            tabla.append([f'Planicidad Inplane: {plan_in}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Planicidad Crossplane: {plan_cross}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0Tolerancia (%): 4.5'])

    return pd.DataFrame(tabla, columns=['Dosimetría'])

def _crear_tabla_indicadores_laser(datos_completos, maquina):
    """Crea la Tabla 3: Aspectos mecánicos (indicadores angulares)"""
    tabla = []    
    ubicacion_laser = ['Longitudinal', 'Vertical', 'Lateral']
    tabla.append(['Ubicación\nLáser', 'Concordancia\nDrump-Phantom', 'Diferencia con\nisocentro (mm)'])
    laser_data = datos_completos.get('HC_indicadores_laser', [])
    
    for ubicacion in ubicacion_laser:
        # Busca el registro cuyo nivel (REAL) coincide con el nombre
        indicador = next((i for i in laser_data if i.get('ubicacion', '') == ubicacion), None)
        if indicador:
            concordancia = indicador.get('concordancia', '')
            diferencia = indicador.get('dif_isocentro', 'NA')
        else:
            concordancia = diferencia = ''

        tabla.append([ubicacion, concordancia, diferencia])

    return pd.DataFrame(tabla, columns=['Indicadores láser', '', ''])

def _crear_tabla_indicadores_camilla(datos_completos, maquina):
    import pandas as pd
    tabla = []
    ubicacion_camilla = ['Longitudinal', 'Lateral', 'Vertical']
    desplazamiento_camilla = [1.0, 5.0, 20.0] 
    tabla.append(['Ubicación\nCamilla (cm)', 'Desplazamiento (cm)', 'Medido (cm)', 'Diferencia (%)'])
    camilla_data = datos_completos.get('HC_indicadores_camilla', [])
    for ubicacion in ubicacion_camilla:
        for posicion in desplazamiento_camilla:
            registro = next(
                (i for i in camilla_data if i.get('ubicacion', '') == ubicacion and float(i.get('desplazamiento', 0)) == float(posicion)), None)
            if registro:
                medido = registro.get('medido_cm', '')
                diferencia = registro.get('diferencia', 'NA')
            else:
                medido = diferencia = ''
            tabla.append([ubicacion, str(int(posicion)), medido, diferencia])

    return pd.DataFrame(tabla, columns=['Indicadores camilla', '', '', ''])

def _crear_tabla_desplazamiento_isocentro(datos_completos, maquina):
    """Crea la Tabla 3: Aspectos mecánicos (indicadores angulares)"""
    tabla = []    
    ubicacion = ['Longitudinal', 'Vertical', 'Lateral']
    tabla.append(['Ubicación', 'Teórico (cm)', 'Medido (cm)', 'Diferencia (cm)'])
    des_iso_data = datos_completos.get('HC_desplazamiento_isocentro_mensual', [])
    
    for ubi in ubicacion:
        # Busca el registro cuyo nivel (REAL) coincide con el nombre
        indicador = next((i for i in des_iso_data if i.get('ubicacion', '') == ubi), None)
        if indicador:
            teorico = indicador.get('teorico', '')
            medido = indicador.get('medido', 'NA')
            diferencia = indicador.get('diferencia', 'NA')
            tabla.append([ubi, teorico, medido, diferencia])
        else:
            tabla.append([ubi, '', '', ''])

    return pd.DataFrame(tabla, columns=['Desplazamientos al isocentro real', '', '', ''])

# Funciones de utilidad para integración con las clases mensuales
def obtener_diccionario_600():
    """Diccionario específico para Clinac 600 mensual"""
    return {
        # Equipos
        'equip_type': ['Tipo de Equipo', None],
        'calibr_fact': ['Factor de Calibración', None],
        
        # Indicadores
        'indicador_luminoso_consola': ['Indicador Consola', None],
        'indicador_luminoso_equipo': ['Indicador Equipo', None],
        
        # Aspectos mecánicos
        'iso_mec': ['Isocentro Mecánico (mm)', 1.0],
        'reticulo_cent': ['Retículo Centrado (mm)', 1.0],
        'camilla_vert_desp': ['Desplazamiento Vertical Camilla (mm)', 2.0],
        
        # Dosimetría
        'discrepancia_dosis': ['Discrepancia Dosis (%)', 2.0],
        'discrepancia_calidad': ['Discrepancia Calidad (%)', 2.0],
        'simetria_inplane': ['Simetría Inplane (%)', 2.0],
        'simetria_crossplane': ['Simetría Crossplane (%)', 2.0],
        'planicidad_inplane': ['Planicidad Inplane (%)', 3.0],
        'planicidad_crossplane': ['Planicidad Crossplane (%)', 3.0],
        
        # Cuñas (solo 600)
        'in_val': ['Cuña Entrada', None],
        'out_val': ['Cuña Salida', None],
        'right_val': ['Cuña Derecha', None],
        'left_val': ['Cuña Izquierda', None]
    }

def obtener_diccionario_ix():
    """Diccionario específico para iX mensual"""
    diccionario = obtener_diccionario_600()
    
    # Agregar campos específicos para múltiples energías en iX
    energias = ['6MV', '15MV', '6MeV', '9MeV', '12MeV', '15MeV']
    tolerancias = {'6MV': 2.0, '15MV': 2.0, '6MeV': 3.0, '9MeV': 3.0, '12MeV': 3.0, '15MeV': 3.0}
    
    # Dosimetría por energía
    for energia in energias:
        tolerancia = tolerancias[energia]
        diccionario.update({
            f'discrepancia_dosis_{energia}': [f'Discrepancia Dosis {energia} (%)', tolerancia],
            f'discrepancia_calidad_{energia}': [f'Discrepancia Calidad {energia} (%)', tolerancia],
            f'simetria_inplane_{energia}': [f'Simetría Inplane {energia} (%)', 2.0],
            f'simetria_crossplane_{energia}': [f'Simetría Crossplane {energia} (%)', 2.0],
            f'planicidad_inplane_{energia}': [f'Planicidad Inplane {energia} (%)', 3.0],
            f'planicidad_crossplane_{energia}': [f'Planicidad Crossplane {energia} (%)', 3.0]
        })
    
    # Agregar conos (específico del iX)
    diccionario.update({
        'valor': ['Estado Cono', None]  # Para control_conos
    })
    
    return diccionario

def _generar_mostrar_pdf_multitabla(self, tablas_reporte, fecha, maquina, id_maquina, tipo_reporte, usuario_info, datos_completos):
    """Genera y muestra el PDF con múltiples tablas"""
    
    # Generar PDF con múltiples tablas
    ICONO = resource_path('resources/icons/iconoPDF.png')
    
    # Preparar información de usuarios
    usuario1_info = usuario_info.get('usuario1', {})
    usuario2_info = usuario_info.get('usuario2', None)
    
    buffer = generar_reporte_pdf_multitabla_mensual(
        tablas=tablas_reporte,
        fecha=fecha,
        user=usuario1_info.get('usuario', ''),
        tipo_reporte=tipo_reporte, 
        maquina=maquina,
        id_maquina=id_maquina,
        logo_path=ICONO,
        firma=usuario1_info.get('firma_path'),
        role=usuario1_info.get('rol', ''),
        user2=usuario2_info.get('usuario', '') if usuario2_info else None,
        firma2=usuario2_info.get('firma_path') if usuario2_info else None,
        role2=usuario2_info.get('rol', '') if usuario2_info else None,
        temp=True
    )
    
    # Convertir buffer a bytes
    if isinstance(buffer, bytes):
        pdf_bytes = buffer
    elif hasattr(buffer, 'getvalue'):
        pdf_bytes = buffer.getvalue()
    elif hasattr(buffer, 'data'):
        pdf_bytes = bytes(buffer.data())
    else:
        raise TypeError("Tipo de buffer no soportado")
    
    # Mostrar PDF
    self.window = PdfViewer(
        pdf_data=pdf_bytes,
        fecha=fecha,
        maquina=maquina,
        tipo_reporte=tipo_reporte
    )
    self.window.show()

def obtener_diccionario_halcyon():
    """Diccionario específico para Halcyon mensual"""
    return {
        # Equipos
        'equip_type': ['Tipo de Equipo', None],
        'calibr_fact': ['Factor de Calibración', None],
        
        # Indicadores (similar a otros)
        'indicador_luminoso_consola': ['Indicador Consola', None], 
        'indicador_luminoso_equipo': ['Indicador Equipo', None],
        
        # Aspectos mecánicos
        'iso_mec': ['Isocentro Mecánico (mm)', 1.0],
        'reticulo_cent': ['Retículo Centrado (mm)', 1.0],
        
        # Dosimetría (Halcyon típicamente usa solo 6MV)
        'discrepancia_dosis': ['Discrepancia Dosis (%)', 2.0],
        'discrepancia_calidad': ['Discrepancia Calidad (%)', 2.0],
        'simetria_inplane': ['Simetría Inplane (%)', 2.0],
        'simetria_crossplane': ['Simetría Crossplane (%)', 2.0],
        'planicidad_inplane': ['Planicidad Inplane (%)', 3.0],
        'planicidad_crossplane': ['Planicidad Crossplane (%)', 3.0]
        
        # Sin cuñas ni conos
    }

# ============================================================================
#  FUNCIONES ESPECÍFICAS PARA BRAQUITERAPIA MENSUAL
# ============================================================================

def _crear_tabla_tipo_calibracion(datos_completos):
    """Crea tabla con información del tipo de calibración para braquiterapia"""
    tabla = []
    
    # Encabezado
    tabla.append(['Campo', 'Valor'])
    
    # Extraer datos de la tabla principal
    tipo = datos_completos.get('tipo', '')
    serie = datos_completos.get('serie', '')
    certificado = datos_completos.get('certificado', '')
    fecha_cer = datos_completos.get('fecha_cer', '')
    intensidad = datos_completos.get('intensidad', '')
    conversion = datos_completos.get('conversion', '')
    
    # Agregar filas
    tabla.append(['Tipo de calibración', tipo])
    tabla.append(['Número de serie de la fuente', serie])
    tabla.append(['Número del certificado', certificado])
    tabla.append(['Fecha del certificado', fecha_cer])
    tabla.append(['Intensidad de la fuente (GBq)', intensidad])
    tabla.append(['Factor de conversión', conversion])
    
    return pd.DataFrame(tabla, columns=['Tipo de calibración', ''])

def _crear_tabla_sistema_medicion(datos_completos):
    """Crea tabla con información del sistema de medición para braquiterapia"""
    tabla = []
    
    # Obtener datos de SistemaMedicion
    sistema_data = datos_completos.get('SistemaMedicion', [])
    
    if sistema_data:
        sistema = sistema_data[0]  # Primer registro
        
        # Encabezado
        tabla.append(['Campo', 'Valor'])
        
        # Datos de la cámara de pozo
        modelo = sistema.get('modelo', '')
        serie_cp = sistema.get('serie_cp', '')
        calibracion = sistema.get('calibracion', '')
        
        # Datos del electrómetro
        modelo_elec = sistema.get('modelo_elec', '')
        serie_ele = sistema.get('serie_ele', '')
        electrometro = sistema.get('electrometro', '')
        
        # Condiciones de calibración
        t0 = sistema.get('t0', '')
        p0 = sistema.get('p0', '')
        h0 = sistema.get('h0', '')
        
        # Agregar filas
        tabla.append(['Modelo de la cámara de pozo', modelo])
        tabla.append(['Serie de la cámara de pozo', serie_cp])
        tabla.append(['Factor de calibración (U/A)', calibracion])
        tabla.append(['Modelo del electrómetro', modelo_elec])
        tabla.append(['Serie del electrómetro', serie_ele])
        tabla.append(['Factor de calibración electrómetro', electrometro])
        tabla.append(['Temperatura de calibración (°C)', t0])
        tabla.append(['Presión de calibración (mmHg)', p0])
        tabla.append(['Humedad de calibración (%)', h0])
    
    return pd.DataFrame(tabla, columns=['Sistema de medición', ''])

def _crear_tabla_condiciones_medicion(datos_completos):
    """Crea tabla con condiciones de medición para braquiterapia"""
    tabla = []
    
    # Obtener datos de CondicionesMedicion
    condiciones_data = datos_completos.get('CondicionesMedicion', [])
    
    if condiciones_data:
        condiciones = condiciones_data[0]  # Primer registro
        
        # Encabezado
        tabla.append(['Campo', 'Valor'])
        
        t = condiciones.get('t', '')
        p = condiciones.get('p', '')
        h = condiciones.get('h', '')
        desplazamiento_ini = condiciones.get('desplazamiento_ini', 'No Aplica')
        
        # Agregar filas
        tabla.append(['Temperatura de medida (°C)', t])
        tabla.append(['Presión de medida (mmHg)', p])
        tabla.append(['Humedad de medida (%)', h])
        tabla.append(['Desplazamiento inicial (mm)', desplazamiento_ini])
    
    return pd.DataFrame(tabla, columns=['Condiciones de medición', ''])

def _crear_tabla_maximos_camaras(maximos_data):
    """Crea tabla con medidas de máximos de cámaras para braquiterapia"""
    tabla = []
    
    # Encabezado
    tabla.append(['Posición (mm)', 'Medida 1 (nA)', 'Medida 2 (nA)', 'Promedio (nA)'])
    
    # Ordenar por posición
    maximos_ordenados = sorted(maximos_data, key=lambda x: float(x.get('posicion', 0)), reverse=True)
    
    for medida in maximos_ordenados:
        posicion = medida.get('posicion', '')
        medida1 = medida.get('medida1', '')
        medida2 = medida.get('medida2', '')
        promedio = medida.get('promedio', '')
        
        tabla.append([posicion, medida1, medida2, promedio])
    
    return pd.DataFrame(tabla, columns=['Máximos de cámaras', '', '', ''])

def _crear_tabla_lecturas_maximos(lecturas_data):
    """Crea tabla con lecturas de máximos para braquiterapia"""
    tabla = []
    
    # Encabezado
    tabla.append(['Voltaje (V)', 'Medida 1 (A)', 'Medida 2 (A)', 'Medida 3 (A)', 'Promedio (A)'])
    
    # Ordenar por voltaje descendente
    lecturas_ordenadas = sorted(lecturas_data, key=lambda x: float(x.get('voltaje', 0)), reverse=True)
    
    for lectura in lecturas_ordenadas:
        voltaje = lectura.get('voltaje', '')
        v_300 = lectura.get('V_300', '')
        v_150 = lectura.get('V_150', '')
        vn_300 = lectura.get('Vn_300', '')
        promedio = lectura.get('promediosV', '')
        
        tabla.append([voltaje, v_300, v_150, vn_300, promedio])
    
    return pd.DataFrame(tabla, columns=['Lecturas de máximos', '', '', '', ''])

def _crear_tabla_resultados_actividad(resultados_data):
    """Crea tabla con resultados de actividad para braquiterapia"""
    tabla = []
    
    if resultados_data:
        resultado = resultados_data[0]  # Primer registro
        
        # Encabezado
        tabla.append(['Parámetro', 'Valor'])
        
        # Factores de corrección
        ks = resultado.get('Ks', '')
        kp = resultado.get('Kp', '')
        ktp = resultado.get('Ktp', '')
        
        # Actividades
        actividad_monitor = resultado.get('actividad_monitor', '')
        actividad_calculada = resultado.get('actividad_calculada', '')
        actividad_decaimiento = resultado.get('actividad_decaimiento', '')
        
        # Agregar filas
        tabla.append(['Factor de corrección por saturación (Ks)', ks])
        tabla.append(['Factor de corrección de polaridad (Kp)', kp])
        tabla.append(['Factor de corrección Temp/Presión (Ktp)', ktp])
        tabla.append(['Actividad en el monitor (U)', actividad_monitor])
        tabla.append(['Actividad calculada (U)', actividad_calculada])
        tabla.append(['Actividad por decaimiento (GBq)', actividad_decaimiento])
        
        # Calcular discrepancia si existen ambos valores
        if actividad_calculada and actividad_monitor:
            try:
                calc = float(actividad_calculada)
                monitor = float(actividad_monitor)
                discrepancia = abs((calc - monitor) / monitor) * 100
                tabla.append(['Discrepancia (%)', f'{discrepancia:.2f}'])
            except (ValueError, ZeroDivisionError):
                tabla.append(['Discrepancia (%)', 'N/A'])
    
    return pd.DataFrame(tabla, columns=['Resultados de actividad', ''])

# ============================================================================
#  FUNCIONES DE GRÁFICOS PARA BRAQUITERAPIA MENSUAL
# ============================================================================

def _crear_grafico_maximos_camaras(maximos_data):
    """Crea gráfico de máximos de cámaras como imagen para el PDF"""
    import matplotlib
    matplotlib.use('Agg')  # Backend sin GUI
    import matplotlib.pyplot as plt
    import io
    import base64
    
    if not maximos_data:
        return None
    
    # Ordenar por posición
    maximos_ordenados = sorted(maximos_data, key=lambda x: float(x.get('posicion', 0)), reverse=True)
    
    posiciones = [float(m.get('posicion', 0)) for m in maximos_ordenados]
    promedios = [float(m.get('promedio', 0)) for m in maximos_ordenados]
    
    # Crear figura
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(posiciones, promedios, 'o-', color='#4a8892', linewidth=2, markersize=8)
    ax.set_xlabel('Posición (mm)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Promedio (nA)', fontsize=12, fontweight='bold')
    ax.set_title('Máximos de Cámaras', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Guardar como imagen en memoria
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    # Convertir a base64 para incluir en PDF
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    
    # Retornar DataFrame con referencia a la imagen
    return pd.DataFrame([[img_base64]], columns=['Gráfico de máximos'])

def _crear_grafico_lecturas_maximos(lecturas_data):
    """Crea gráfico de lecturas de máximos como imagen para el PDF"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import io
    import base64
    
    if not lecturas_data:
        return None
    
    # Ordenar por voltaje
    lecturas_ordenadas = sorted(lecturas_data, key=lambda x: float(x.get('voltaje', 0)), reverse=True)
    
    voltajes = [float(l.get('voltaje', 0)) for l in lecturas_ordenadas]
    promedios = [float(l.get('promediosV', 0)) for l in lecturas_ordenadas]
    
    # Crear figura
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(voltajes, promedios, 's-', color='#c1df08', linewidth=2, markersize=10)
    ax.set_xlabel('Voltaje (V)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Corriente promedio (A)', fontsize=12, fontweight='bold')
    ax.set_title('Lecturas de Máximos', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.ticklabel_format(style='scientific', axis='y', scilimits=(0,0))
    
    # Guardar como imagen en memoria
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    
    return pd.DataFrame([[img_base64]], columns=['Gráfico de lecturas'])

# ============================================================================
#  FUNCIONES PARA REPORTE DE LINEALIDAD DE BRAQUITERAPIA
# ============================================================================

def _crear_tabla_sistema_medicion_linealidad(datos_completos):
    """Crea tabla de sistema de medición para linealidad"""
    tabla = []
    
    tabla.append(['Campo', 'Valor'])
    tabla.append(['Modelo de la cámara de pozo', datos_completos.get('modelo', '')])
    tabla.append(['Serie de la cámara de pozo', datos_completos.get('serie_cp', '')])
    tabla.append(['Factor de calibración (U/A)', datos_completos.get('calibracion', '')])
    tabla.append(['Modelo del electrómetro', datos_completos.get('modelo_elec', '')])
    tabla.append(['Serie del electrómetro', datos_completos.get('serie_ele', '')])
    tabla.append(['Factor de calibración electrómetro', datos_completos.get('electrometro', '')])
    
    return pd.DataFrame(tabla, columns=['Sistema de medición', ''])

def _crear_tabla_carga_colectada(datos_completos):
    """Crea tabla de carga colectada en 60s - Reproducibilidad"""
    tabla = []
    
    tabla.append(['Medida', 'Valor (nC)'])
    tabla.append(['Medida 1', datos_completos.get('repro_m1', '')])
    tabla.append(['Medida 2', datos_completos.get('repro_m2', '')])
    tabla.append(['Medida 3', datos_completos.get('repro_m3', '')])
    tabla.append(['Medida 4', datos_completos.get('repro_m4', '')])
    tabla.append(['Medida 5', datos_completos.get('repro_m5', '')])
    tabla.append(['Promedio', datos_completos.get('repro_prom', '')])
    tabla.append(['', ''])
    tabla.append(['Carga estacionaria (nC)', datos_completos.get('q_est', '')])
    tabla.append(['Tiempo integrado (s)', datos_completos.get('t_integrado', '')])
    tabla.append(['Corriente estacionaria (nA)', datos_completos.get('i_est', '')])
    
    return pd.DataFrame(tabla, columns=['Carga colectada en 60s', ''])

def _crear_tabla_medidas_linealidad(datos_completos):
    """Crea tabla con medidas de linealidad"""
    tabla = []
    
    tabla.append(['Tiempo parada (s)', 'Q1 (nC)', 'Q2 (nC)', 'Q promedio (nC)', 'Tiempo efectivo (s)'])
    
    datos_linealidad = datos_completos.get('datos_linealidad', [])
    for punto in datos_linealidad:
        if punto.get('tp') is not None:  # Solo agregar si hay datos
            tabla.append([
                f"{punto.get('tp', ''):.2f}" if punto.get('tp') else '',
                f"{punto.get('q1', ''):.2f}" if punto.get('q1') else '',
                f"{punto.get('q2', ''):.2f}" if punto.get('q2') else '',
                f"{punto.get('qprom', ''):.2f}" if punto.get('qprom') else '',
                f"{punto.get('te', ''):.4f}" if punto.get('te') else ''
            ])
    
    return pd.DataFrame(tabla, columns=['Medidas de linealidad', '', '', '', ''])

def _crear_tabla_resultados_linealidad(datos_completos):
    """Crea tabla con resultados de linealidad"""
    tabla = []
    
    tabla.append(['Parámetro', 'Valor'])
    tabla.append(['Reproducibilidad (%)', datos_completos.get('reproducibilidad', '')])
    tabla.append(['Exactitud (R²)', datos_completos.get('exactitud', '')])
    tabla.append(['Tiempo de tránsito (s)', datos_completos.get('tiempo_transito', '')])
    
    return pd.DataFrame(tabla, columns=['Resultados', ''])

def _crear_grafico_linealidad(datos_completos):
    """Crea gráfico de linealidad de la fuente"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    import io
    import base64
    
    datos_linealidad = datos_completos.get('datos_linealidad', [])
    if not datos_linealidad:
        return None
    
    # Extraer datos válidos
    tiempo_parada = []
    tiempo_efectivo = []
    
    for punto in datos_linealidad:
        if punto.get('tp') is not None and punto.get('te') is not None:
            tiempo_parada.append(float(punto.get('tp')))
            tiempo_efectivo.append(float(punto.get('te')))
    
    if not tiempo_parada or not tiempo_efectivo:
        return None
    
    # Convertir a arrays numpy
    x = np.array(tiempo_parada)
    y = np.array(tiempo_efectivo)
    
    # Ajuste lineal
    m, b = np.polyfit(x, y, 1)
    y_pred = m * x + b
    
    # Calcular R²
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1 - (ss_res / ss_tot)
    
    # Crear figura
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(x, y, 'o', color='#4a8892', markersize=8, label='Datos medidos')
    ax.plot(x, y_pred, '-', color='#c1df08', linewidth=2, label=f'Ajuste lineal (R² = {r2:.4f})')
    ax.set_xlabel('Tiempo de parada (s)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Tiempo efectivo (s)', fontsize=12, fontweight='bold')
    ax.set_title('Linealidad de la Fuente', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Agregar texto con resultados
    textstr = f'Ecuación: y = {m:.4f}x + {b:.4f}\nR² = {r2:.4f}'
    ax.text(0.05, 0.95, textstr, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # Guardar como imagen
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    
    return pd.DataFrame([[img_base64]], columns=['Gráfico de linealidad'])

