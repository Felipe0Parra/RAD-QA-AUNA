import os
import re
import pandas as pd
from PyQt5.QtWidgets import QMessageBox
import data.ManejoDatos.conection as con
from services.audit_minimo import registrar as _registrar_auditoria
from services.audit_minimo import ACCION_GUARDAR
from services.anulacion import filtro_activo

def addSpace(cadena):
    """Agrega un espacio antes de cada letra mayúscula en una cadena, excepto la inicial."""
    return re.sub(r'(?<!^)([A-Z])', r' \1', cadena)

# A6.0 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.5): addInfo2 (variante manual de
# ingesta MPC, selección de carpeta con QFileDialog) se borró -- cero
# llamadores en todo el repo (halcyon.py solo importa addInfo). addInfo la
# reemplazó hace tiempo con localización automática por fecha, validación de
# corrida completa y auditoría; addInfo2 ni auditaba ni avisaba en UI al
# reimportar un día ya existente (hallazgo de HANDOFF_BUILD_WINDOWS).

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


def _contar_filas_datos(carpeta):
    """Filas de datos del Results.csv de `carpeta`; 0 si no existe o no se lee.

    Una corrida abortada del MPC no genera Results.csv; una parcial lo genera
    con solo la cabecera, o truncado a unas pocas filas; una completa trae el
    juego entero (253 filas en el corpus real). Se lee ese único fichero
    (~20 KB) y nunca las imágenes `.xim` (~124 MB por carpeta).
    """
    ruta_csv = os.path.join(carpeta, 'Results.csv')
    try:
        with open(ruta_csv, 'r', encoding='utf-8', errors='ignore') as f:
            lineas = [linea for linea in f if linea.strip()]
    except OSError:
        return 0
    return max(0, len(lineas) - 1)  # descontando la cabecera


def _results_csv_tiene_datos(carpeta):
    """True si `carpeta` tiene Results.csv con al menos una fila de datos.

    Marcador mínimo de J1 (PLAN_HALCYON_SELECCION_CARPETA_21-07.md): descarta
    abortadas (sin Results.csv) y vacías (solo cabecera). H2 lo refina con el
    GRADO de completitud, ver `seleccionar_carpeta_mpc`.
    """
    return _contar_filas_datos(carpeta) > 0


def _tiene_imagenes_adquiridas(carpeta):
    """True si `carpeta` conserva las imágenes `.xim` de la adquisición.

    Es lo que separa una corrida real de una REPUBLICACIÓN: cuando el MPC
    vuelve a escribir un resultado ya cerrado deja una carpeta de 2-13
    ficheros, con el mismo Results.csv completo pero SIN imágenes. Verificado
    en el corpus real: 2026-07-02 05:17:44 (163 ficheros, 50 `.xim`) y
    06-26-58 (2 ficheros, 0 `.xim`) traen un Results.csv byte-idéntico; ídem
    2026-07-10. Sin este criterio, "la última del día" se queda con la
    republicación, que no contiene toda la información de la prueba.
    """
    try:
        return any(n.lower().endswith('.xim') for n in os.listdir(carpeta))
    except OSError:
        return False


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
    """Carpeta MPC de `fecha`: la ÚLTIMA de entre las MÁS COMPLETAS.

    H2 (PLAN_ACTUALIZACION_HALCYON_CERT_PERMISOS_06-08.md §3.3). Dos
    criterios, en este orden:

    1. **Completitud primero.** El grado de completitud de una carpeta es la
       pareja `(filas de datos del Results.csv, conserva las imágenes .xim)`,
       y se toma el MÁXIMO de ese día. Es un criterio RELATIVO a las corridas
       del propio día: no hay ningún umbral fijo que envejezca si Varian
       cambia la plantilla. Descarta las dos formas de carpeta incompleta que
       deja el MPC -- las corridas PARCIALES (Results.csv truncado: 2 filas
       en vez de 253) y las REPUBLICACIONES del resultado ya cerrado
       (Results.csv completo pero sin imágenes) -- que además suelen
       generarse DESPUÉS de la corrida buena.

    2. **Entre las empatadas, la última.** Si ese día el equipo repitió la
       prueba -- p.ej. porque quedó un objeto en la zona de irradiación y la
       primera corrida salió con artefactos -- la válida es la repetición, la
       más reciente. Medido sobre el corpus real: 7 días con varias corridas
       completas de contenido distinto, uno de ellos (2026-07-20) con OCHO.

    Nunca lanza -- ante cualquier problema para listar `ruta_base` devuelve
    None, igual que si no hay ninguna corrida con datos para esa fecha.
    """
    try:
        candidatas = carpetas_mpc_de_fecha(ruta_base, fecha)
    except OSError:
        return None

    # Una sola lectura de Results.csv por carpeta: esto corre sobre el share
    # de red del hospital. Las imágenes solo se miran en las que YA traen
    # datos, que son pocas -- un día normal deja decenas de carpetas de
    # arranque fallido (sin CSV o solo cabecera) y una o dos corridas buenas.
    con_datos = []
    for carpeta in candidatas:
        filas = _contar_filas_datos(carpeta)
        if filas > 0:
            con_datos.append((carpeta, filas))
    if not con_datos:
        return None

    grados = [(carpeta, (filas, _tiene_imagenes_adquiridas(carpeta)))
              for carpeta, filas in con_datos]
    mejor_grado = max(grado for _, grado in grados)
    # `carpetas_mpc_de_fecha` devuelve de más antigua a más reciente (J1), así
    # que el último de los empatados en el grado máximo es el más reciente.
    return [carpeta for carpeta, grado in grados if grado == mejor_grado][-1]


def _localizar_y_leer_mpc(self, fecha):
    """Localiza la carpeta MPC de `fecha` y lee su Results.csv -- lógica
    COMPARTIDA por la previsualización (`dateChanged`) y el guardado
    ("Agregar"), H3 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md §H3).
    Nunca escribe en la BD. Devuelve `(folder_found, df_widgets)`, o
    `(None, None)` si no hay carpeta completa o el CSV no se pudo leer --
    en ese caso ya se avisó en pantalla (ruta inaccesible, sin corrida
    completa, o no encontrada)."""
    ruta_actual = ruta_mpc_halcyon()

    print("Listando carpetas...")
    folder_found = seleccionar_carpeta_mpc(ruta_actual, fecha)

    if not folder_found:
        try:
            candidatas = carpetas_mpc_de_fecha(ruta_actual, fecha)
        except Exception as e:
            print(f"Error al listar carpetas: {e}")
            QMessageBox.critical(self, "Error", f"No se pudo acceder a la ruta.\n{e}")
            return None, None
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
        return None, None

    print(f"Carpeta encontrada: {folder_found}")
    nombre_archivo = os.path.join(folder_found, 'Results.csv')

    try:
        df = pd.read_csv(nombre_archivo)
    except FileNotFoundError:
        QMessageBox.critical(self, "Error", f"No se encontró el archivo Results.csv en la carpeta {fecha}.")
        return None, None

    df[['hipergroup', 'group', 'subgroup', 'subsubgroup']] = df['Name [Unit]'].str.split('/', expand=True)
    df.fillna('', inplace=True)
    return folder_found, addInfoWidgets(df)


def _fecha_ya_importada(fecha):
    with con.Conexion().conectar() as db:
        cursor = db.cursor()
        # LR3 (DA-47/DA-48): "¿existe reporte de esta fecha?" es una lectura
        # de BLOQUE. Gemelo sin filtrar de load.py:204 (D3), que ya filtra:
        # un reporte ANULADO de esa fecha no cuenta como importado.
        cursor.execute(
            f"SELECT 1 FROM halcyon WHERE date=?{filtro_activo('halcyon')}",
            (fecha,))
        return cursor.fetchone() is not None


def previsualizar_halcyon(self, fecha):
    """H3: la fecha elegida (`dateChanged`) SOLO llena los campos --
    localiza la carpeta, lee el Results.csv, y avisa si la fecha ya está
    importada (informativo, no bloquea la previsualización). CERO
    escrituras en la BD; para guardar hace falta pulsar "Agregar"
    (`agregar_halcyon`)."""
    folder_found, df_widgets = _localizar_y_leer_mpc(self, fecha)
    if df_widgets is None:
        return None

    if _fecha_ya_importada(fecha):
        print("Ya existe la fecha")
        QMessageBox.information(
            self, "Fecha ya importada",
            f"La fecha {fecha} ya está importada en el diario del Halcyon."
        )

    return df_widgets


def agregar_halcyon(self, fecha, user):
    """H3: "Agregar" -- localiza la carpeta MPC de `fecha` (misma ruta que
    la previsualización), comprueba que la fecha no exista ya, llama a
    `createDB` y audita. Único punto de escritura del diario del Halcyon;
    antes lo hacía `addInfo` en la MISMA pasada que `dateChanged`, así que
    seleccionar la fecha ya guardaba sin que el físico lo pidiera."""
    folder_found, df_widgets = _localizar_y_leer_mpc(self, fecha)
    if df_widgets is None:
        return None

    if _fecha_ya_importada(fecha):
        # H1 (PLAN_ACTUALIZACION_HALCYON_CERT_PERMISOS_06-08.md §3.4,
        # hallazgo F7 del 2026-07-07): NO se reemplaza (a diferencia de
        # add_info/H2.2, otra función): solo se informa.
        print("Ya existe la fecha")
        QMessageBox.information(
            self, "Fecha ya importada",
            f"La fecha {fecha} ya está importada en el diario del Halcyon."
        )
        return df_widgets

    df_csv = df_widgets.copy()
    df_csv = df_csv.loc[df_csv['type'] == 'resultado']
    df_csv.to_csv('infoWidgets.csv', index=False)
    df_csv['fecha'] = fecha
    df_csv['user_id'] = user

    try:
        if createDB(df_csv, fecha, user):
            _registrar_auditoria(
                user, ACCION_GUARDAR, "halcyon", ref=fecha,
                detalle=f"carpeta MPC: {os.path.basename(folder_found)}"
            )
        else:
            # H1-bis: createDB ya no falla en silencio -- si devuelve
            # False, el físico se entera en vez de pulsar "Agregar" y no
            # ver ningún efecto.
            QMessageBox.critical(
                self, "Error al guardar",
                f"No se pudo guardar el diario del Halcyon para la "
                f"fecha {fecha}. Revise que el Results.csv de la "
                f"carpeta MPC tenga el formato esperado."
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
    """Devuelve True si la fila se guardó, False si no.

    H1-bis (PLAN_ACTUALIZACION_HALCYON_CERT_PERMISOS_06-08.md, hallazgo del
    2026-08-06, diagnosticado por subagente Opus): el INSERT se arma
    dinámicamente y POSICIONALMENTE desde PRAGMA table_info -- correcto
    mientras la tabla tuviera exactamente 22 columnas no-`id` (date,
    user_id + 20 de medición). Desde E7 (28-07,
    PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md) `halcyon` -- como toda tabla de
    `TABLAS_ANULABLES` -- tiene además `activo`, sin valor que ofrecerle
    desde `descripciones`. El INSERT revenía SIEMPRE con "Incorrect number
    of bindings supplied" desde entonces, atrapado en silencio por el
    `except` de abajo -- nadie lo notó porque nadie reimportó un diario de
    Halcyon con una BD ya migrada hasta este hallazgo (verificado contra
    producción: 254 filas, la más reciente 2026-07-01, antes de E7).
    """
    try:
        with con.Conexion().conectar() as db:
            cursor = db.cursor()

            # Columnas reales de la tabla, excepto 'id' (autoincremental) y
            # 'activo' (E7 -- su DEFAULT=1 la llena sola; este INSERT no
            # tiene un valor que darle porque inserta posicionalmente, no
            # por nombre).
            cursor.execute("PRAGMA table_info(halcyon)")
            columnas = [col[1] for col in cursor.fetchall()
                        if col[1] not in ('id', 'activo')]
            descripciones = df['descripcion'].tolist()

            # Guarda de longitud: verificado contra el corpus real que una
            # corrida degenerada del MPC puede traer menos resultados de
            # los 20 esperados -- sin esto, esa carpeta produciría el mismo
            # error de bindings, solo que con una causa distinta.
            esperadas = len(columnas) - 2  # menos fecha y user_id
            if len(descripciones) != esperadas:
                print(
                    f"createDB: el Results.csv trajo {len(descripciones)} "
                    f"resultados, se esperaban {esperadas} -- no se guarda "
                    f"la fecha {fecha}.")
                return False

            sql = f"INSERT INTO halcyon ({', '.join(columnas)}) VALUES ({', '.join(['?'] * len(columnas))})"
            cursor.execute(sql, [fecha, user] + descripciones)

            db.commit()
            return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error al agregar datos de la fecha: {fecha}:", e)
        return False

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


    

    
