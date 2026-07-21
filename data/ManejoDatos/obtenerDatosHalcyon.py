import os
import re
import pandas as pd
from PyQt5.QtWidgets import QMessageBox, QFileDialog
import data.ManejoDatos.conection as con
from services.audit_minimo import registrar as _registrar_auditoria

def addSpace(cadena):
    """Agrega un espacio antes de cada letra mayúscula en una cadena, excepto la inicial."""
    return re.sub(r'(?<!^)([A-Z])', r' \1', cadena)

def addInfo2(self, user):
    
    archivo = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
    if archivo is None:
        QMessageBox.critical(self, "Error", f"No se encontró la carpeta.")
        return None
    elif archivo == "":
        print('Se cancelo')
        return None
    
    patron_fecha = re.compile(r'(\d{4}-\d{2}-\d{2})')
    match = patron_fecha.search(archivo)
    fecha = match.group(1)
    
    print(fecha)
    
    nombre_archivo = os.path.join(archivo,'Results.csv')
    df = pd.read_csv(nombre_archivo)

    df[['hipergroup', 'group', 'subgroup', 'subsubgroup']] = df['Name [Unit]'].str.split('/', expand=True)
    df.fillna('', inplace=True)
    df_widgets = addInfoWidgets(df)
    
    df_csv = df_widgets.copy()
    df_csv = df_csv.loc[df_csv['type'] == 'resultado']
    df_csv.to_csv('infoWidgets.csv', index=False)
    df_csv['fecha'] = fecha
    df_csv['user_id'] = user
    #print(df_csv)

    try:
        with con.Conexion().conectar() as db:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM halcyon WHERE date=?", (fecha,))
            fila = cursor.fetchone()
            
            if fila: # Si ya existe, actualizar
                print("Ya existe la fecha")
            else:
                createDB(df_csv, fecha, user)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error al agregar datos de la fecha: {fecha}:", e)
        
    return df_widgets

RUTA_MPC_POR_DEFECTO = r"\\VARIANDB\Va_Transfer\TDS\HAL1161\MPCChecks"

PATRON_CARPETA_MPC = re.compile(r'(\d{4}-\d{2}-\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{4})')


def ruta_mpc_halcyon():
    """Ruta base de los reportes MPC del Halcyon.

    Lee `RADQA_HALCYON_MPC` si está definida (para probar con una copia local
    de reportes, p.ej. en Windows sin acceso al share del hospital); si no,
    usa la ruta de red real -- en producción nadie define esa variable, así
    que el comportamiento queda igual que antes.
    """
    return os.environ.get("RADQA_HALCYON_MPC", RUTA_MPC_POR_DEFECTO)


def _results_csv_tiene_datos(carpeta):
    """True si `carpeta` tiene Results.csv con al menos una fila de datos.

    Una corrida abortada del MPC no genera Results.csv; una parcial lo genera
    con solo la línea de cabecera. Solo una corrida completa trae filas de
    datos detrás de la cabecera -- por eso este es el marcador de completitud
    (confirmado con carpetas reales del Halcyon, ver PLAN_HALCYON_SELECCION_
    CARPETA_21-07.md). Se leen solo las dos primeras líneas, no toda la
    carpeta (~124 MB con las imágenes .xim).
    """
    ruta_csv = os.path.join(carpeta, 'Results.csv')
    try:
        with open(ruta_csv, 'r', encoding='utf-8', errors='ignore') as f:
            f.readline()  # cabecera
            segunda_linea = f.readline()
    except OSError:
        return False
    return bool(segunda_linea.strip())


def carpetas_mpc_de_fecha(ruta_base, fecha):
    """Carpetas MPC de `fecha`, ordenadas de más antigua a más reciente.

    Discrimina por día PRIMERO (solo entran candidatas cuyo nombre trae
    exactamente esa fecha) -- la completitud se evalúa después, entre esas
    candidatas, nunca a través de fechas distintas. Puede lanzar OSError si
    `ruta_base` no es accesible; se deja propagar para que quien llama decida
    cómo informarlo (red caída vs. sin datos para la fecha son cosas distintas).
    """
    candidatas = []
    for carpeta in os.listdir(ruta_base):
        ruta_carpeta = os.path.join(ruta_base, carpeta)
        if not os.path.isdir(ruta_carpeta):
            continue
        match = PATRON_CARPETA_MPC.search(carpeta)
        if not match or match.group(1) != fecha:
            continue
        clave_orden = match.group(2) + match.group(3) + match.group(4) + match.group(5)
        candidatas.append((clave_orden, ruta_carpeta))
    candidatas.sort(key=lambda par: par[0])
    return [ruta for _, ruta in candidatas]


def seleccionar_carpeta_mpc(ruta_base, fecha):
    """Carpeta MPC correcta de `fecha`: la más reciente entre las COMPLETAS.

    Nunca lanza -- ante cualquier problema para listar `ruta_base` devuelve
    None, igual que si no hay ninguna corrida completa para esa fecha.
    """
    try:
        candidatas = carpetas_mpc_de_fecha(ruta_base, fecha)
    except OSError:
        return None
    completas = [c for c in candidatas if _results_csv_tiene_datos(c)]
    if not completas:
        return None
    return completas[-1]


def addInfo(self, fecha, user):

    ruta_actual = ruta_mpc_halcyon()

    print("Listando carpetas...")
    folder_found = seleccionar_carpeta_mpc(ruta_actual, fecha)

    if folder_found:
        print(f"Carpeta encontrada: {folder_found}")
        QMessageBox.information(self, "Encontrada", f"Se encontró la carpeta:\n{folder_found}")
    else:
        try:
            candidatas = carpetas_mpc_de_fecha(ruta_actual, fecha)
        except Exception as e:
            print(f"Error al listar carpetas: {e}")
            QMessageBox.critical(self, "Error", f"No se pudo acceder a la ruta.\n{e}")
            return
        if candidatas:
            print(f"Hay {len(candidatas)} carpeta(s) para {fecha}, ninguna corrida completa.")
            QMessageBox.warning(
                self, "Sin corrida completa",
                f"Hay {len(candidatas)} carpeta(s) para el {fecha} pero ninguna corrida "
                f"del MPC está completa (falta Results.csv con datos). Revise el equipo."
            )
        else:
            print("No se encontró carpeta para esa fecha.")
            QMessageBox.warning(self, "No encontrada", "No se encontró una carpeta para esa fecha.")
        return

    nombre_archivo = os.path.join(folder_found,'Results.csv')
    
    try:
        df = pd.read_csv(nombre_archivo)
    
    except FileNotFoundError:
        QMessageBox.critical(self, "Error", f"No se encontró el archivo Results.csv en la carpeta {fecha}.")
        return

    df[['hipergroup', 'group', 'subgroup', 'subsubgroup']] = df['Name [Unit]'].str.split('/', expand=True)
    df.fillna('', inplace=True)
    df_widgets = addInfoWidgets(df)
    
    df_csv = df_widgets.copy()
    df_csv = df_csv.loc[df_csv['type'] == 'resultado']
    df_csv.to_csv('infoWidgets.csv', index=False)
    df_csv['fecha'] = fecha
    df_csv['user_id'] = user
    #print(df_csv)

    try:
        with con.Conexion().conectar() as db:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM halcyon WHERE date=?", (fecha,))
            fila = cursor.fetchone()
            
            if fila: # Si ya existe, actualizar
                print("Ya existe la fecha")
            else:
                createDB(df_csv, fecha, user)
                _registrar_auditoria(
                    user, "guardar", "halcyon", ref=fecha,
                    detalle=f"carpeta MPC: {os.path.basename(folder_found)}"
                )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error al agregar datos de la fecha: {fecha}:", e)

    return df_widgets

def addInfoWidgets(df):
    def get_last_group_level(row):
        """Determina el último nivel de grupo no vacío en una fila."""
        group_levels = ['subsubgroup', 'subgroup', 'group']
        for level in group_levels:
            if row[level].strip():
                return level, row[level]
        return 'group', row['group']  # Valor por defecto si todos están vacíos

    hipergroups = df['hipergroup'].unique()
    #print(f'Hay {len(hipergroups)} hipergrupos: {hipergroups}')

    #translator = Translator()

    nombres = []
    descripcion = []
    widget_type = []
    valor = []

    for hipergroup in hipergroups:
        df_hipergrupo = df.loc[df.hipergroup == hipergroup]
        #print()
        #print(f"Procesando hipergrupo: {hipergroup}")
        
        if hipergroup == 'CollimationGroup':
            continue
        
        for index, row in df_hipergrupo.iterrows():
            # Obtener el último nivel de grupo y su valor
            level, group_name = get_last_group_level(row)
            #print(f'en el nivel: {level} se tiene: {group_name}')
            
            # Limpiar el nombre
            nombre = re.sub(r' \[(mm|°|%)\]', r'', group_name)
            #print(nombre)
            
            # Set 1: Nombre
            nombres.append(f'{nombre}_name1')
            texto = addSpace(nombre)
            descripcion.append(texto)
            widget_type.append('QLabel')
            valor.append('text')
            
            # Set 2: Info
            nombres.append(f'{nombre}_name2')
            nombre_value = row[' Value']
            descripcion.append(nombre_value)
            widget_type.append('QLineEdit block')
            valor.append('resultado')
            
            if hipergroup != 'MVImagerGroup':
                # Set 4: Threshold
                nombres.append(f'{nombre}_thres')
                nombre_thres = row[' Threshold']
                descripcion.append(nombre_thres)
                widget_type.append('QLineEdit block')
                valor.append('threshold')
                
            # Set 3: Evaluación
            nombres.append(f'{nombre}_eval')
            nombre_evaluacion = row[' Evaluation Result']
            descripcion.append(nombre_evaluacion)
            widget_type.append('QLineEdit block')
            valor.append('boolean')

    df_result = pd.DataFrame({
        'nombres': nombres,
        'widget_type': widget_type,
        'descripcion': descripcion,
        'type': valor
    })
    return df_result

def createDB(df, fecha, user):
    try:
        #print("try createDB")
        with con.Conexion().conectar() as db:
            #print("Creando tabla halcyon")
            cursor = db.cursor()
            
            # Obtener los nombres de las columnas de la tabla (excepto 'id')
            cursor.execute("PRAGMA table_info(halcyon)")
            columnas = [col[1] for col in cursor.fetchall() if col[1] != 'id']
            #print(columnas)
            descripciones = df['descripcion'].tolist()
            # Armar la consulta SQL dinámicamente
            #columnas = [f"col{i+1}" for i in range(len(descripciones))]
            sql = f"INSERT INTO halcyon ({', '.join(columnas)}) VALUES ({', '.join(['?'] * len(columnas))})"
            cursor.execute(sql, [fecha] + [user] + descripciones)
            
            db.commit()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error al agregar datos de la fecha NEA NO SE: {fecha}:", e)

'''def addInfoDB(df, fecha):
    print(fecha)
    '''
    
'''def store_in_databases(df_widgets, fecha):
    try:
        with con.Conexion().conectar() as db:
            cursor = db.cursor()
            cursor.execute("SELECT COUNT(*) FROM halcyon_widgets WHERE date=?", (fecha,))
            if cursor.fetchone()[0] > 0:
                cursor.execute("DELETE FROM halcyon_widgets WHERE date=?", (fecha,))
                db.commit()
            
            for index, row in df_widgets.iterrows():
                cursor.execute("INSERT INTO halcyon_widgets (date, IsoCenterSize_name2, IsoCenterMVOffset, IsoCenterKVOffset, BeamOutputChange, BeamUniformityChange, BeamMu1GainChange, BeamMu2GainChange, GantryAbsolute, GantryRelative, CouchLat, CouchLng, CouchVrt, CouchLatLong, CouchLngLong, CouchVrtLong, VirtualToIsoLat, VirtualToIsoLng, VirtualToIsoVrt, MVImagerCalibrationGain, MVImagerCalibrationUniformity) VALUES (?,
    '''


    

    
