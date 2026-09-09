from PyQt5.QtSql import QSqlQuery
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtGui import QPixmap
import tempfile
import pandas as pd
try:
    from utils import resource_path
except Exception:
    import importlib.util, os
    # Fallback: load utils.py directly from project root when package imports fail
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    utils_path = os.path.join(project_root, 'utils.py')
    if os.path.isfile(utils_path):
        spec = importlib.util.spec_from_file_location('utils', utils_path)
        utils = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(utils)
        resource_path = getattr(utils, 'resource_path')
    else:
        raise
from models.PDF.pdf import generar_reporte_pdf
from models.PDF.PDFWindow import PdfViewer
from services.anulacion import filtro_activo
from services.unidades_qc import unidad_de
# R2: la declaración vive en `clasificacion_diario.py` (que `pdf.py`
# también necesita leer) y se re-exporta aquí porque el plan la nombra
# como "la declaración en `models/PDF/reportes.py`" -- ver el docstring
# de ese módulo para el porqué de la separación (import circular).
from models.PDF.clasificacion_diario import (
    COLUMNAS_IDENTIFICACION, COLUMNAS_MOVIDAS_A_OTRA_TABLA, COLUMNAS_RETIRADAS)


def _campos_booleanos(diccionario):
    """R1 (PLAN_REPORTES_LEGIBLES_08-09.md): deriva qué claves son
    booleanas directamente del `diccionario_invertido` que cada pantalla
    ya declara -- `v[2] == "scatter"` es la marca que las 4 pantallas usan
    para armar sus propios menús de gráfica (`graficos_mapeo1`), así que
    ya es la fuente de verdad; leerla aquí es no inventar una segunda.

    Antes se leía `self.boolean_columns` -- 3 de las 4 pantallas declaran
    `boolean_colums` (sin la "n"), así que `hasattr` daba False y la
    conversión no corría nunca en 600/iX/braqui; en Halcyon SÍ existe el
    atributo, pero `Halcyon.diccionario_invertido` no tiene marca
    "scatter" en absoluto (sus valores son `[label, umbral]`, 2
    elementos) -- por eso el resultado correcto para Halcyon es un
    conjunto VACÍO, no una lista de sus 20 métricas numéricas."""
    return {
        clave for clave, valores in diccionario.items()
        if len(valores) > 2 and valores[2] == "scatter"
    }


def _valor_booleano(valor):
    """Normaliza `valor` a 1, 0 o None antes de decidir el veredicto.

    `QSqlQuery.value()` puede devolver int, float o str según cómo SQLite
    tipó la columna en ese registro concreto; la comparación estricta
    `== 1` de antes solo cazaba el caso int. Un valor no reconociblemente
    1 ni 0 (None, '', texto) NO es un campo que falló: se deja sin
    veredicto -- "sin dato" y "no funciona" son cosas distintas."""
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, (int, float)):
        if valor == 1:
            return 1
        if valor == 0:
            return 0
        return None
    if isinstance(valor, str):
        texto = valor.strip()
        if texto in ("1", "1.0"):
            return 1
        if texto in ("0", "0.0"):
            return 0
    return None


def guardarPDF(self, fecha, maquina = "", id_maquina = "",
        tipo_reporte = '', diccionario = {}, umbrales = None):
    file_name, _ = QFileDialog.getSaveFileName(
        self, "Guardar PDF Mensual",
        f"Control_{maquina}_{fecha}.pdf",
        "Archivos PDF (*.pdf)"
    )
    #nea = QFileDialog.getSaveFileName()
    if file_name:
        # Crear un DataFrame de ejemplo
        reporte(self, fecha, maquina, id_maquina, tipo_reporte,
            diccionario, umbrales, file_name)

def reporte(self, fecha, maquina = "", id_maquina = "",
            tipo_reporte = '', diccionario = {},
            umbrales = None, file_name = ""):

    #Reconoce la amaquina
    maquinas_dict = {
        'Clinac 600': 'aceleradorlineal_600',
        'iX': 'aceleradorlineal_ix',
        'Gammamed Plus i X': 'braqui',
        'HALCYON': 'halcyon'
    }
    loto = maquinas_dict.get(maquina, None)

    if loto is None:
        print("Máquina no reconocida")
        return

    #busque en la base de datos de esa maquina
    db = self.opeenDatabase()
    query = QSqlQuery(db)
    # Obtener nombres de columnas
    query_cols = QSqlQuery(db)
    query_cols.exec(f"PRAGMA table_info({loto})")

    columnas = []
    while query_cols.next():
        columnas.append(query_cols.value(1))

    columna_fecha = "fecha" if "fecha" in columnas else "date"

    # LR3 (DA-47/DA-48): `loto` es siempre una de las 4 diarias, y la
    # lectura es por FECHA (bloque), no por id -- filtra sobre la MISMA
    # variable dinámica, así queda protegida por construcción.
    query.prepare(f"SELECT * FROM {loto} WHERE DATE({columna_fecha}) = ?"
                  f"{filtro_activo(loto)} ORDER BY id DESC")
    query.addBindValue(fecha)

    # Ejecutar la consulta
    if query.exec():
        column_names = [query.record().fieldName(i) for i in range(query.record().count())]
        if query.next():
            row_values = [query.value(i) for i in range(len(column_names))]
            # Crear el DataFrame con nombre de los campos. la evaluacion y los valores
            df = pd.DataFrame({
                "": column_names,
                'Evaluación': None,
                "Valores": row_values
            })
        else:
            QMessageBox.critical(self, "Error", f"Error en la consulta, no se encontraron registros para la fecha {fecha}")
            return
    else:
        print("Error ejecutando la consulta SQL.")
        db.close()
        return

    #print(df)
    #Use el diccionario para buscar los Valores CORRESPONDIENTES A la descripcion
    usuario = df.loc[df[df.columns[0]]=='user_id', df.columns[2]].values[0]

    temp_image_path = None
    rol = None

    query2 = QSqlQuery(db)
    query2.prepare("SELECT firma, role FROM users WHERE fullname = ?")
    query2.addBindValue(usuario)
    if query2.exec():
        if query2.next():
            firma = query2.value(0)
            rol = query2.value(1)
            # Convertir el BLOB a QPixmap (si es que vas a mostrarlo)
            if firma:
                try:
                    # firma puede ser bytes o QByteArray desde la BD; convertir si es necesario
                    if isinstance(firma, str):
                        # Si es string (base64, path, etc), intentar convertir
                        try:
                            import base64
                            firma_bytes = base64.b64decode(firma)
                        except:
                            # Si falla, asumir que es una ruta válida
                            firma_bytes = None
                    else:
                        # Asumir que es bytes o similar
                        firma_bytes = bytes(firma) if firma else None

                    if firma_bytes:
                        pixmap = QPixmap()
                        if pixmap.loadFromData(firma_bytes):
                            temp_fd, temp_image_path = tempfile.mkstemp(suffix=".png")
                            pixmap.save(temp_image_path, "PNG")
                        else:
                            print("No se pudo cargar la imagen de firma desde los datos binarios.")
                except Exception as e:
                    print(f"Error procesando firma: {e}")
        else:
            print("No se encontró 'firma' para el usuario.")
    else:
        print("Error ejecutando la consulta en la tabla users.")

    # Cerrar la base de datos una vez que ya no se necesita
    db.close()

    # R1: el veredicto "Funciona"/"No funciona" se deriva de la propia
    # declaración (`v[2] == "scatter"`), no de un atributo de la UI leído
    # por su nombre -- ver `_campos_booleanos`.
    col0 = df.columns[0]
    for key in _campos_booleanos(diccionario):
        mask = df[col0] == key
        for idx in df.index[mask]:
            veredicto = _valor_booleano(df.at[idx, 'Valores'])
            if veredicto == 1:
                df.at[idx, 'Evaluación'] = 'Funciona'
                df.at[idx, 'Valores'] = ''
            elif veredicto == 0:
                df.at[idx, 'Evaluación'] = 'No funciona'
                df.at[idx, 'Valores'] = ''

    # R3: la columna "Umbrales" queda SIEMPRE presente cuando `umbrales`
    # no es None (antes braqui llamaba con `umbrales=None` y se quedaba
    # sin columna) y ninguna celda queda vacía: número si lo hay, "No
    # aplica" si la prueba no tiene umbral -- una celda vacía no permite
    # distinguir "no aplica" de "nadie lo llenó".
    #
    # Se declara con dtype `object` desde el principio (no dejar que
    # pandas la infiera float64 del primer número que reciba): esa
    # columna termina con texto ("No aplica") mezclado con números, y
    # asignar texto sobre una columna que pandas cree numérica es un
    # `FutureWarning` hoy y un error en versiones futuras.
    if umbrales is not None:
        df['Umbrales'] = pd.Series([None] * len(df), dtype=object)

    for key, values in diccionario.items():
        # R4: la unidad va en corchetes junto al identificador, en la
        # MISMA celda del texto -- nunca en la de "Valores" (que debe
        # seguir siendo un número puro). `df[col0].replace` en vez de
        # `df.replace`: acotado a la columna de identificadores, para no
        # tocar por accidente un valor que coincidiera con `key`.
        etiqueta = values[0] + unidad_de(key)
        df[col0] = df[col0].replace(key, etiqueta)
        if not umbrales is None:
            umbral = values[1]
            fila = df[col0] == etiqueta
            if isinstance(umbral, (int, float)):
                df.loc[fila, 'Umbrales'] = umbral
                valor_fila = df.loc[fila, 'Valores'].values[0]
                if valor_fila == '':
                    df.loc[fila, 'Evaluación'] = 'No aplica'
                elif valor_fila > umbral:
                    df.loc[fila, 'Evaluación'] = 'Fuera del umbral'
                else:
                    df.loc[fila, 'Evaluación'] = 'Dentro del umbral'
            else:
                df.loc[fila, 'Umbrales'] = 'No aplica'

    #haga el reporte
    ICONO =  resource_path('resources/icons/iconoPDF.png')

    buffer = generar_reporte_pdf(df=df, fecha=fecha, user=usuario, tipo_reporte=tipo_reporte, maquina=maquina,
                                id_maquina=id_maquina, logo_path=ICONO, firma=temp_image_path, role=rol, temp=True,
                                es_diario_qc=True)

    if isinstance(buffer, bytes):
        pdf_bytes = buffer
    elif hasattr(buffer, 'getvalue'):
        pdf_bytes = buffer.getvalue()
    elif hasattr(buffer, 'data'):
        pdf_bytes = bytes(buffer.data())
    else:
        raise TypeError("Buffer type not supported")
    self.window = PdfViewer(pdf_data=pdf_bytes, fecha=fecha, maquina=maquina, tipo_reporte=tipo_reporte)
    self.window.show()


    #pregunte a donde enviarla
