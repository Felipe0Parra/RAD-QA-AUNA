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
    
    # Reemplazando los Valores booleanos en la columna "Valores" para las filas correspondientes
    if hasattr(self, 'boolean_columns'):
        for key in self.boolean_columns:
            mask = df[df.columns[0]] == key
            df.loc[mask & (df['Valores'] == 1), 'Evaluación'] = 'Funciona'
            df.loc[mask & (df['Valores'] == 1), 'Valores'] = ''
            df.loc[mask & (df['Valores'] == 0), 'Evaluación'] = 'No funciona'
            df.loc[mask & (df['Valores'] == 0), 'Valores'] = ''
    
    
    for key, values in diccionario.items():
        df.replace(key, values[0], inplace=True)
        if not umbrales is None:
            df.loc[df[df.columns[0]] == values[0], 'Umbrales'] = values[1]
            #print(f"Valor: {df.loc[df[df.columns[0]] == values[0], 'Valores'].values[0]}\nUmbral : {values[1]}")
            if isinstance(values[1], (int, float)):
                
                if df.loc[df[df.columns[0]] == values[0], 'Valores'].values[0] == '':
                    df.loc[df[df.columns[0]] == values[0], 'Evaluación'] = 'No aplica'
                elif df.loc[df[df.columns[0]] == values[0], 'Valores'].values[0] > values[1]:
                    df.loc[df[df.columns[0]] == values[0], 'Evaluación'] = 'Fuera del umbral'
                else:
                    df.loc[df[df.columns[0]] == values[0], 'Evaluación'] = 'Dentro del umbral'
    
    #haga el reporte
    ICONO =  resource_path('resources/icons/iconoPDF.png')

    buffer = generar_reporte_pdf(df=df, fecha=fecha, user=usuario, tipo_reporte=tipo_reporte, maquina=maquina, 
                                id_maquina=id_maquina, logo_path=ICONO, firma=temp_image_path, role=rol, temp=True)

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
