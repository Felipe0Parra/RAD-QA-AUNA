from PyQt5.QtSql import QSqlQuery
from PyQt5.QtWidgets import QMessageBox
import pandas as pd
from PyQt5.QtGui import QPixmap
import tempfile
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
from models.PDF.pdf import generar_reporte_pdf_multitabla_anual
from models.PDF.PDFWindow import PdfViewer
from models.PDF.Mensuales.reportes_mensuales import (_obtener_datos_tabla_relacionada, _obtener_info_usuario, 
                                                    _obtener_datos_tabla_principal, 
                                                    _crear_tabla_equipos)
from models.PDF.Imagenes.reportes_control_sistema_imagenes import ReporteControlSistemaImagenes
from services.anulacion import filtro_activo
from data.ManejoDatos.catphan_TAC.catphan_db import reconstruir_resultados_desde_bd


class ReporteMensual:
    """Clase para generar reportes PDF de controles mensuales"""
    
    def __init__(self):
        tablas_relacionadas_600_ix = {
                'principal': 'controles',
                'tablas_relacionadas': [
                    'tabla_factor_campo',
                    'tabla_factores_transmision', 
                    'tabla_factores_sobre_eje',
                    'tabla_control_camaras_monitoras',
                    'equipos_medicion'
                ],
                'accesorios': []  # Sin accesorios
            }

        self.tablas_por_maquina = {
            'Clinac 600': tablas_relacionadas_600_ix,

            'Clinac ix': tablas_relacionadas_600_ix,

            'Halcyon': {
                'principal': 'controles',
                'tablas_relacionadas': [
                    'HC_indicadores_brazo',
                    'HC_indicadores_colimador',
                    'HC_indicadores_laser',
                    'HC_tamanos_campo_radiacion',
                    'HC_indicadores_camilla',
                    'equipos_medicion',
                    'HC_dosimetria_anual',
                    'HC_velocidad_multilaminas_anual',
                    'HC_precision_posicion_multilaminas_anual',
                    'HC_linealidad_unidades_monitor_anual',
                    'HC_tamanos_campo_radiacion',
                    'HC_imagen_perfil_mlc_anual',
                    # No tiene control_cunas ni control_conos
                ],
                'accesorios': []  # Sin accesorios
            }
        }

def guardarPDF_anual(self, fecha, maquina="", id_maquina="", 
                        tipo_reporte='Control Anual', diccionario={}, umbrales=None):
    """Función para guardar PDF de control anual"""

    reporte_anual(self, fecha=fecha, maquina=maquina, id_maquina=id_maquina, 
                        tipo_reporte=tipo_reporte, diccionario=diccionario, 
                        umbrales=umbrales, file_name=f"control_anual_{maquina}_{fecha}.pdf")

def reporte_anual(self, fecha, maquina="", id_maquina="", 
                    tipo_reporte='Control Anual', diccionario={}, 
                    umbrales=None, file_name=""):
    """Genera reporte PDF completo de control anual"""

    # Verificar máquina soportada
    if maquina not in ['Clinac 600', 'Clinac ix', 'Halcyon']:
        QMessageBox.critical(self, "Error", f"Máquina {maquina} no soportada para reportes anuales")
        return
    
    # Obtener configuración de tablas
    config_tablas = ReporteMensual().tablas_por_maquina[maquina]
    
    try:
        # Conectar a base de datos
        db = self.opeenDatabase()
        
        # Buscar registro principal
        ref_id = _obtener_referencia_principal(db, fecha, maquina)
        if not ref_id:
            QMessageBox.critical(self, "Error", 
                                f"No se encontró control anual para {maquina} en {fecha}")
            return
        
        # Recopilar datos de todas las tablas
        datos_completos = _recopilar_datos_completos(db, ref_id, config_tablas, maquina)
        
        # Obtener información del usuario (usuario 1 y usuario 2 si existe)
        usuario_info = _obtener_info_usuario(db, datos_completos.get('user_id', ''), datos_completos.get('user_id_f2'))
        
        # Procesar datos para el reporte anual (múltiples tablas)
        tablas_reporte = _procesar_datos_para_reporte_anual(datos_completos, diccionario, umbrales, maquina)
        
        # --- INTEGRAR SISTEMA DE IMÁGENES SI EXISTE (solo para Halcyon e iX) ---
        if maquina in ['Clinac ix', 'Halcyon']:
            print(f"Verificando datos del sistema de imágenes para {maquina}...")
            tablas_img = obtener_tablas_sistema_imagenes_para_pdf(db, ref_id)
            if tablas_img:
                print(f"Se encontraron {len(tablas_img)} tablas del sistema de imágenes")
                # Añadir las tablas del sistema de imágenes al diccionario principal
                tablas_reporte['titulo_sistema_imagenes'] = 'Control de Calidad del sistema de imágenes'
                tablas_reporte.update(tablas_img)
            else:
                print("No se encontraron datos del sistema de imágenes para esta sesión")
        
        # Generar y mostrar PDF
        _generar_mostrar_pdf_multitabla_anual(self, tablas_reporte, fecha, maquina, id_maquina, 
                                        tipo_reporte, usuario_info, datos_completos)
        db.close()
        
    except Exception as e:
        QMessageBox.critical(self, "Error", f"Error generando reporte: {str(e)}")
        print(f"Error en reporte_mensual: {e}")
        import traceback
        traceback.print_exc()

def _obtener_referencia_principal(db, fecha, maquina):
    """Obtiene el ID de referencia del control anual"""
    query = QSqlQuery(db)
    # LR3 (DA-47/DA-48): lectura de BLOQUE -- (fecha, equipo, control) puede
    # casar un control anulado y otro vigente del mismo mes.
    query.prepare(
        "SELECT id FROM controles WHERE fecha = ? AND equipo = ? "
        f"AND control = 'Anual'{filtro_activo('controles')} ORDER BY id DESC")
    query.addBindValue(fecha)
    query.addBindValue(maquina)
    
    if query.exec() and query.next():
        return query.value(0)
    return None

def _recopilar_datos_completos(db, ref_id, config_tablas, maquina):
    """Recopila datos de todas las tablas relacionadas"""
    datos_completos = {'ref_id': ref_id, 'maquina': maquina, "control": "Anual"}
    
    # Obtener datos de tabla principal
    datos_principal = _obtener_datos_tabla_principal(db, ref_id)
    datos_completos.update(datos_principal)
    
    # Obtener datos de tablas relacionadas
    for tabla in config_tablas['tablas_relacionadas']:
        datos_tabla = _obtener_datos_tabla_relacionada(db, ref_id, tabla)
        datos_completos[tabla] = datos_tabla
    
    return datos_completos

def obtener_tablas_sistema_imagenes_para_pdf(db, ref):
    """
    Obtiene solo las tablas del sistema de imágenes para incluir en el PDF anual
    Sin generar un PDF separado, solo retorna las tablas procesadas
    
    Args:
        db: Conexión a la base de datos
        ref (int): ID de la sesión
    
    Returns:
        dict: Diccionario con las tablas del sistema de imágenes procesadas
    """
    try:
        reporte_img = ReporteControlSistemaImagenes()
        
        # Verificar si hay datos disponibles
        if not reporte_img._verificar_pruebas_disponibles(db, ref):
            return {}
        
        # Obtener información de la sesión
        info_sesion = reporte_img._obtener_info_sesion(db, ref)
        if not info_sesion:
            return {}
        
        # Agregar db y ref al info_sesion para procesamiento
        info_sesion['db'] = db
        info_sesion['ref'] = ref
        
        # Obtener imágenes BLOB
        imagenes_originales, imagenes_resultados = reporte_img._obtener_imagenes_blob(db, ref)
        
        # Reconstruir resultados desde la base de datos
        resultados = reconstruir_resultados_desde_bd(
            ref, 
            categorias=reporte_img.categorias_disponibles,
            label=None,
            canvas=None
        )
        
        if not resultados:
            return {}
        
        # Procesar resultados para generar las tablas
        tablas_reporte = reporte_img._procesar_resultados_para_reporte(
            resultados, 
            info_sesion, 
            imagenes_originales, 
            imagenes_resultados
        )
        
        return tablas_reporte
        
    except Exception as e:
        print(f"Error obteniendo tablas del sistema de imágenes: {e}")
        import traceback
        traceback.print_exc()
        return {}

def obtener_energia(db, id_energia):
    """Obtiene la energía a partir del ID"""
    query = QSqlQuery(db)
    query.prepare("SELECT energia FROM energias WHERE id = ?")
    query.addBindValue(id_energia)
    if query.exec() and query.next():
        return query.value(0)
    return 'Desconocida'

def _procesar_datos_para_reporte_anual(datos_completos, diccionario, umbrales, maquina):
    """Procesa y estructura los datos para múltiples tablas del reporte anual"""
    
    # Crear estructura de tablas
    tablas_reporte = {}
    
    # Tabla 1: Equipos de medición
    tablas_reporte['equipos'] = _crear_tabla_equipos(datos_completos.get('equipos_medicion', []), maquina)
    
    # Tablas según la máquina
    if maquina == 'Clinac ix':
        # Para iX: crear tablas por cada energía
        tablas_reporte['factores_campo'] = _crear_tablas_factor_campo_ix(
            datos_completos.get('tabla_factor_campo', [])
        )
        tablas_reporte['factores_transmision'] = _crear_tablas_factores_transmision_ix(
            datos_completos.get('tabla_factores_transmision', [])
        )
        tablas_reporte['factores_sobre_eje'] = _crear_tablas_factores_sobre_eje_ix(
            datos_completos.get('tabla_factores_sobre_eje', [])
        )
        tablas_reporte['control_camaras'] = _crear_tablas_control_camaras_ix(
            datos_completos.get('tabla_control_camaras_monitoras', [])
        )
    elif maquina == 'Clinac 600':
        # Para 600: una sola tabla por tipo
        tablas_reporte['factores_campo'] = _crear_tabla_factor_campo_600(
            datos_completos.get('tabla_factor_campo', [])
        )
        tablas_reporte['factores_transmision'] = _crear_tabla_factores_transmision_600(
            datos_completos.get('tabla_factores_transmision', [])
        )
        tablas_reporte['factores_sobre_eje'] = _crear_tablas_factores_sobre_eje_600(
            datos_completos.get('tabla_factores_sobre_eje', [])
        )
        tablas_reporte['control_camaras'] = _crear_tabla_control_camaras_600(
            datos_completos.get('tabla_control_camaras_monitoras', [])
        )
    elif maquina == 'Halcyon':
        tablas_reporte['indicadores_angulares_gantry'] = [{
            'titulo': 'Indicadores angulares gantry',
            'dataframe': _crear_tabla_indicadores_angulares_g(datos_completos, maquina)
        }]
        tablas_reporte['indicadores_angulares_colimador'] = [{
            'titulo': 'Indicadores angulares colimador',
            'dataframe': _crear_tabla_indicadores_angulares_c(datos_completos, maquina)
        }]
        tablas_reporte['indicadores_laser'] = [{
            'titulo': 'Indicadores láser',
            'dataframe': _crear_tabla_indicadores_laser(datos_completos, maquina)
        }]
        tablas_reporte['indicadores_camilla'] = [{
            'titulo': 'Indicadores camilla',
            'dataframe': _crear_tabla_indicadores_camilla(datos_completos, maquina)
        }]
        tablas_reporte['velocidad_multilaminas'] = [{
            'titulo': 'Velocidad de multiláminas',
            'dataframe': _crear_tabla_velocidad_multilaminas(datos_completos, maquina)
        }]
        tablas_reporte['precision_posicion_multilaminas'] = [{
            'titulo': 'Precisión de posicionamiento de multiláminas',
            'dataframe': _crear_tabla_precision_posicion_multilaminas(datos_completos, maquina)
        }]
        tablas_reporte['imagen_perfil_mlc'] = [{
            'titulo': 'Imagen y perfil de MLC',
            'dataframe': _crear_tabla_imagen_perfil_mlc(datos_completos, maquina)
        }]
        tablas_reporte['dosimetria'] = [{
            'titulo': 'Dosimetría',
            'dataframe': _crear_tabla_dosimetria(datos_completos.get('HC_dosimetria_anual', []))
        }]
        tablas_reporte['linealidad_unidades_monitor'] = [{
            'titulo': 'Linealidad de unidades monitoras',
            'dataframe': _crear_tabla_linealidad_unidades_monitor(datos_completos, maquina)
        }]
        tablas_reporte['tamanos_campo_dosis'] = [{
            'titulo': 'Tamaños de campo dosis',
            'dataframe': __crear_tabla_tamanos_campo_dosis_halcyon(datos_completos.get('HC_tamanos_campo_radiacion', []))
        }]
    
    return tablas_reporte

def _obtener_nombre_energia(id_energia):
    """Mapea el ID de energía a su nombre correspondiente"""
    energia_ids = {
        0: "6 MV", 
        1: "15 MV", 
        2: "6 MeV", 
        3: "9 MeV", 
        4: "12 MeV", 
        5: "15 MeV"
    }
    return energia_ids.get(id_energia, f"Energía {id_energia}")

# ==================== FUNCIONES PARA CLINAC iX (múltiples energías) ====================

def _crear_tablas_factor_campo_ix(factor_campo_data):
    """Crea múltiples tablas de factor de campo, una por cada energía (iX)"""
    energias = [0, 1, 2, 3, 4, 5]  # 6 MV, 15 MV, 6 MeV, 9 MeV, 12 MeV, 15 MeV
    tablas = []
    
    for energia_id in energias:
        # Filtrar datos por energía
        datos_energia = [d for d in factor_campo_data if d.get('id_energia') == energia_id]
        
        if not datos_energia:
            continue
        
        # Crear tabla para esta energía
        tabla_data = []
        tabla_data.append(['Tamaño de campo', 'Factor de campo', 'Factor esperado', 'Discrepancia (%)'])
        
        for dato in datos_energia:
            tabla_data.append([
                dato.get('tamano_campo', ''),
                dato.get('factor_campo', ''),
                dato.get('factor_campo_esperado', ''),
                dato.get('discrepancia', '')
            ])
        
        # Crear DataFrame con título que incluye la energía
        columnas = ['Tamaño de campo', 'Factor de campo', 'Factor esperado', 'Discrepancia (%)']
        df = pd.DataFrame(tabla_data[1:], columns=columnas)
        
        tablas.append({
            'titulo': f'Factor de campo - {_obtener_nombre_energia(energia_id)}',
            'dataframe': df
        })
    
    return tablas

def _crear_tablas_factores_transmision_ix(factores_transmision_data):
    """Crea múltiples tablas de factores de transmisión, una por cada energía (iX)"""
    energias = [0, 1, 2, 3, 4, 5]
    tablas = []
    
    for energia_id in energias:
        datos_energia = [d for d in factores_transmision_data if d.get('id_energia') == energia_id]
        
        if not datos_energia:
            continue
        
        tabla_data = []
        tabla_data.append(['Accesorio', 'Factor de transmisión', 'Factor esperado', 'Discrepancia (%)'])
        
        for dato in datos_energia:
            tabla_data.append([
                dato.get('angulo', ''),
                dato.get('factor_transmision', ''),
                dato.get('factor_transmision_esperado', ''),
                dato.get('discrepancia', '')
            ])
        
        columnas = ['Cuña', 'Factor de transmisión', 'Factor esperado', 'Discrepancia (%)']
        df = pd.DataFrame(tabla_data[1:], columns=columnas)
        
        tablas.append({
            'titulo': f'Factores de transmisión de accesorios - {_obtener_nombre_energia(energia_id)}',
            'dataframe': df
        })
    
    return tablas

def _crear_tablas_factores_sobre_eje_ix(factores_sobre_eje_data):
    """Crea múltiples tablas de factores sobre el eje, agrupadas por energía y PDD (iX)"""
    energias = [0, 1, 2, 3, 4, 5]
    # E1 (PLAN_REPARACION_ANUAL_27-08.md §Fase 2): los electrones (id 2-5)
    # ya guardan sus propios PDD de cono y su profundidad en mm (ver
    # ix_anual.py::DEFINICIONES_ENERGIA) -- con un solo `ppds` fotón, este
    # filtro por `tam_pdd` no encontraba coincidencia para electrones y
    # los saltaba en silencio (dato guardado, invisible en el PDF firmado).
    ppds_por_energia = {
        0: ["PDD (10 x 10)", "PPD (15 x 15)", "PPD (20 x 20)"],
        1: ["PDD (10 x 10)", "PPD (15 x 15)", "PPD (20 x 20)"],
        2: ["PDD (6 x 6)", "PDD (10 x 10)", "PDD (20 x 20)"],
        3: ["PDD (6 x 6)", "PDD (10 x 10)", "PDD (20 x 20)"],
        4: ["PDD (6 x 6)", "PDD (10 x 10)", "PDD (20 x 20)"],
        5: ["PDD (6 x 6)", "PDD (10 x 10)", "PDD (20 x 20)"],
    }
    unidad_profundidad_por_energia = {0: "cm", 1: "cm", 2: "mm", 3: "mm", 4: "mm", 5: "mm"}
    tablas = []

    for energia_id in energias:
        # Para cada energía, crear una tabla combinada con los 3 PPDs
        datos_energia = [d for d in factores_sobre_eje_data if d.get('id_energia') == energia_id]

        if not datos_energia:
            continue

        # Agrupar por PDD
        encabezado_profundidad = f"Profundidad ({unidad_profundidad_por_energia[energia_id]})"
        for pdd in ppds_por_energia[energia_id]:
            datos_pdd = [d for d in datos_energia if d.get('tam_pdd') == pdd]

            if not datos_pdd:
                continue

            tabla_data = []
            tabla_data.append([encabezado_profundidad, pdd, 'PPD esperado', 'Discrepancia (%)'])

            for dato in datos_pdd:
                tabla_data.append([
                    dato.get('profundidad', ''),
                    dato.get('ppd', ''),
                    dato.get('ppd_esperado', ''),
                    dato.get('discrepancia', '')
                ])

            columnas = [encabezado_profundidad, pdd, 'PPD esperado', 'Discrepancia (%)']
            df = pd.DataFrame(tabla_data[1:], columns=columnas)

            tablas.append({
                'titulo': f'Factores sobre el eje - {_obtener_nombre_energia(energia_id)} - {pdd}',
                'dataframe': df
            })

    return tablas

def _crear_tablas_control_camaras_ix(control_camaras_data):
    """Crea múltiples tablas de control de cámaras monitoras, una por cada energía (iX)"""
    energias = [0, 1, 2, 3, 4, 5]
    tablas = []
    
    for energia_id in energias:
        datos_energia = [d for d in control_camaras_data if d.get('id_energia') == energia_id]
        
        if not datos_energia:
            continue
        
        tabla_data = []
        tabla_data.append(['Indicador', 'Valor'])
        
        # Los indicadores están en filas individuales
        for dato in datos_energia:
            tabla_data.append([
                dato.get('indicador_medir', ''),
                dato.get('valor_medido', '')
            ])
        
        columnas = ['Indicador', 'Valor']
        df = pd.DataFrame(tabla_data[1:], columns=columnas)
        
        tablas.append({
            'titulo': f'Control de cámaras monitoras - {_obtener_nombre_energia(energia_id)}',
            'dataframe': df
        })
    
    return tablas

# ==================== FUNCIONES PARA CLINAC 600 (una sola energía) ====================

def _crear_tabla_factor_campo_600(factor_campo_data):
    """Crea tabla única de factor de campo para Clinac 600"""
    tabla_data = []
    tabla_data.append(['Tamaño de campo', 'Factor de campo', 'Factor esperado', 'Discrepancia (%)'])
    
    for dato in factor_campo_data:
        tabla_data.append([
            dato.get('tamano_campo', ''),
            dato.get('factor_campo', ''),
            dato.get('factor_campo_esperado', ''),
            dato.get('discrepancia', '')
        ])
    
    columnas = ['Tamaño de campo', 'Factor de campo', 'Factor esperado', 'Discrepancia (%)']
    df = pd.DataFrame(tabla_data[1:], columns=columnas)
    
    return [{
        'titulo': 'Factor de campo',
        'dataframe': df
    }]

def _crear_tabla_factores_transmision_600(factores_transmision_data):
    """Crea tabla única de factores de transmisión para Clinac 600"""
    tabla_data = []
    tabla_data.append(['Cuña', 'Factor de transmisión', 'Factor esperado', 'Discrepancia (%)'])
    
    for dato in factores_transmision_data:
        tabla_data.append([
            dato.get('angulo', ''),
            dato.get('factor_transmision', ''),
            dato.get('factor_transmision_esperado', ''),
            dato.get('discrepancia', '')
        ])
    
    columnas = ['Cuña', 'Factor de transmisión', 'Factor esperado', 'Discrepancia (%)']
    df = pd.DataFrame(tabla_data[1:], columns=columnas)
    
    return [{
        'titulo': 'Factores de transmisión de accesorios',
        'dataframe': df
    }]

def _crear_tablas_factores_sobre_eje_600(factores_sobre_eje_data):
    """Crea tablas de factores sobre el eje para Clinac 600 (3 PPDs)"""
    ppds = ["PDD (10 x 10)", "PPD (15 x 15)", "PPD (20 x 20)"]
    tablas = []
    
    for pdd in ppds:
        datos_pdd = [d for d in factores_sobre_eje_data if d.get('tam_pdd') == pdd]
        
        if not datos_pdd:
            continue
        
        tabla_data = []
        tabla_data.append(['Profundidad (cm)', pdd, 'PPD esperado', 'Discrepancia (%)'])
        
        for dato in datos_pdd:
            tabla_data.append([
                dato.get('profundidad', ''),
                dato.get('ppd', ''),
                dato.get('ppd_esperado', ''),
                dato.get('discrepancia', '')
            ])
        
        columnas = ['Profundidad (cm)', pdd, 'PPD esperado', 'Discrepancia (%)']
        df = pd.DataFrame(tabla_data[1:], columns=columnas)
        
        tablas.append({
            'titulo': f'Factores sobre el eje - {pdd}',
            'dataframe': df
        })
    
    return tablas

def _crear_tabla_control_camaras_600(control_camaras_data):
    """Crea tabla única de control de cámaras monitoras para Clinac 600"""
    tabla_data = []
    tabla_data.append(['Indicador', 'Valor'])
    
    for dato in control_camaras_data:
        tabla_data.append([
            dato.get('indicador_medir', ''),
            dato.get('valor_medido', '')
        ])
    
    columnas = ['Indicador', 'Valor']
    df = pd.DataFrame(tabla_data[1:], columns=columnas)
    
    return [{
        'titulo': 'Control de cámaras monitoras',
        'dataframe': df
    }]

def _generar_mostrar_pdf_multitabla_anual(self, tablas_reporte, fecha, maquina, id_maquina, tipo_reporte, usuario_info, datos_completos):
    """Genera y muestra el PDF con múltiples tablas para reportes anuales"""
    
    # Generar PDF con múltiples tablas (versión anual)
    ICONO = resource_path('resources/icons/iconoPDF.png')
    
    # Preparar información de usuarios
    usuario1_info = usuario_info.get('usuario1', {})
    usuario2_info = usuario_info.get('usuario2', None)
    
    buffer = generar_reporte_pdf_multitabla_anual(
        tablas_dict=tablas_reporte,
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

# =================== FUNCIONES PARA HALCYON (mismo que mensual) ===================

def _crear_tabla_indicadores_angulares_g(datos_completos, maquina):
    """Crea la Tabla 3: Aspectos mecánicos (indicadores angulares)"""
    tabla = []   
    niveles_brazo = ['0°', '90°', '180°', '270°']
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

def _crear_tabla_velocidad_multilaminas(datos_completos, maquina):
    """Crea la Tabla 4: Velocidad de multiláminas"""
    tabla = []   
    tabla.append(['Banco', 'Velocidad promedio\n(cm/s)', 'Desviacion media\n(cm/s)'])     
    bancos = ["A Proximal", "A Distal", "B Proximal", "B Distal"]
    velocidad_data = datos_completos.get('HC_velocidad_multilaminas_anual', [])

    for dato in velocidad_data:
        banco = next((b for b in bancos if b == dato.get('banco', '')), None)
        if banco:
            tabla.append([
                dato.get('banco', ''),
                dato.get('velocidad_prom', ''),
                dato.get('desviacion_med', ''),
            ])

    return pd.DataFrame(tabla, columns=['Velocidad de multiláminas', '', ''])

def _crear_tabla_precision_posicion_multilaminas(datos_completos, maquina):
    """Crea la Tabla 5: Precisión de posicionamiento de multiláminas"""
    tabla = []   
    tabla.append(['Medida (cm)', 'Esperada (cm)', 'Diferencia(%)'])     

    precision_data = datos_completos.get('HC_precision_posicion_multilaminas_anual', [])

    for dato in precision_data:
        tabla.append([
                dato.get('medida', ''),
                dato.get('esperada', ''),
                dato.get('discrepancia', ''),
            ])

    return pd.DataFrame(tabla, columns=['Distancia entre picos', '', ''])

def _crear_tabla_dosimetria(dosimetria_data):
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
        tabla.append([f'Dosis de referencia medida (cGy/UM): {dosis_ref}    Discrepancia (%): {disc_dosis}    Tolerancia (%): 2'])
        
        # Calidad
        calidad = dosi.get('calidad_pdd20_10', '')
        disc_calidad = dosi.get('discrepancia_calidad', '')
        tabla.append([f'Calidad (PDD20/10): {calidad}                Discrepancia (%): {disc_calidad}              Tolerancia (%): 2'])
        
        # Simetría
        sim_in = dosi.get('simetria_inplane', '')
        sim_cross = dosi.get('simetria_crossplane', '')
        tabla.append([f'Simetría Inplane: {sim_in}          Simetría Crossplane: {sim_cross}                       Tolerancia (%): 2'])
        
        # Planicidad
        plan_in = dosi.get('planicidad_inplane', '')
        plan_cross = dosi.get('planicidad_crossplane', '')
        tabla.append([f'Planicidad Inplane: {plan_in}           Planicidad Crossplane: {plan_cross}                    Tolerancia (%): 3'])
    
    return pd.DataFrame(tabla, columns=['Dosimetría'])

def _crear_tabla_linealidad_unidades_monitor(datos_completos, maquina):
    """Crea la Tabla 8: Linealidad de unidades monitoras"""
    tabla = []   
    tabla.append(['UM', 'Q1 (nC)', 'Q2 (nC)', 'Q promedio (nC)'])     

    linealidad_data = datos_completos.get('HC_linealidad_unidades_monitor_anual', [])

    for dato in linealidad_data:
        tabla.append([
                dato.get('UM', ''),
                dato.get('Q1', ''),
                dato.get('Q2', ''),
                dato.get('Qprom', ''),
            ])

    return pd.DataFrame(tabla, columns=['Linealidad de unidades monitoras', '', '', ''])

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
    nominal = [6, 8, 10, 20, 28]
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

def _crear_tabla_imagen_perfil_mlc(datos_completos, maquina):
    """Crea la Tabla de imagen de perfil de MLC (si aplica)"""
    mlc_data = datos_completos.get('HC_imagen_perfil_mlc_anual', [])
    
    imagen = None
    if mlc_data:
        for dato in mlc_data:
            imagen = dato.get('imagen_perfil_horiz', '')
            break  # Solo necesitamos el primero
    
    # La imagen esta en formato BLOB
    # Convertir de BLOB a QPixmap si es necesario
    if imagen:
        try:
            pixmap = QPixmap() # Crear pixmap desde datos BLOB
            if pixmap.loadFromData(imagen): # Cargar datos en pixmap
                # Guardar pixmap en archivo temporal
                temp_fd, temp_image_path = tempfile.mkstemp(suffix=".png")
                pixmap.save(temp_image_path, "PNG")
                imagen = temp_image_path # Ruta temporal de la imagen
            else:
                print("Error: No se pudo cargar la imagen desde los datos BLOB")
                imagen = None
        except Exception as e:
            print(f"Error procesando imagen de MLC: {e}")
            imagen = None
    
    tabla = []
    if imagen:
        tabla.append([imagen]) # Solo una celda con la ruta de la imagen
    else:
        tabla.append(['Sin imagen disponible']) # Texto alternativo si no hay imagen

    return pd.DataFrame(tabla, columns=['Imagen'])