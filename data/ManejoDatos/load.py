from data.GraficasyTablas.tablas import load_table
from data.ManejoDatos.conection import Conexion
import sqlite3, re, traceback, sys
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QGridLayout, QDialog, 
                            QTableWidgetItem, QPushButton, QTabWidget, QTextBrowser )
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtSql import QSqlQuery
from pathlib import Path
from PyQt5.QtGui import QPixmap
from ui.paginasGuia.dialogs import DialogAdminPermisoEliminar
from services.audit_minimo import registrar as _registrar_auditoria
from services.audit_minimo import usuario_actual as _usuario_actual
from services.audit_minimo import (
    ACCION_GUARDAR, ACCION_REEMPLAZO, ACCION_EDITAR, ACCION_ELIMINAR, ACCION_ANULAR)
from services.fechas_control import mismo_mes as _mismo_mes
from services.fechas_control import mes_anio_de_fecha as _mes_anio_de_fecha
from services.ventana_edicion import puede_editarse as _puede_editarse_control
from services.ventana_edicion import mensaje_bloqueo_edicion as _mensaje_bloqueo_edicion
from services.ventana_edicion import motivo_bloqueo as _motivo_bloqueo
from services.anulacion import TABLAS_ANULABLES, anular_fila
from services.reactivacion import reactivar_control as _reactivar_control
def _dialogo_con_identidad(dlg, parent):
    """Propaga al diálogo la identidad del físico del formulario que lo abre.

    A6.2-bis (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7 bis). `guardarEdicion` y
    `eliminarRegistro*` auditan con `_usuario_actual(dlg)`. Cuando los llama
    el formulario mensual/diario directamente, `dlg` ES el formulario y trae
    `user_id`; pero los diálogos emergentes de "Ver tabla" creaban un
    `QDialog(parent)` pelado, así que toda edición o borrado hecho desde ahí
    quedaba en `audit_log` con `usuario` NULL -- mismo defecto que el rebuild
    del físico (27-07-2026) destapó en la pestaña Equipos.

    `parent` es siempre el formulario (mensual o anual): los `mostrar_*` lo
    reciben como primer argumento desde `self`. Devolver el propio `dlg`
    permite usarlo en línea sobre el `QDialog(...)` ya existente.
    """
    dlg.user_id = getattr(parent, "user_id", None)
    return dlg


def guardar_imagen(imagen_path):
    """
    Convierte una imagen en BLOB para guardarla en la base de datos.
    """
    with open(imagen_path, 'rb') as file:
        return file.read()


def dicom_to_png_blob(dcm_path):
    import pydicom
    import numpy as np
    from PIL import Image
    from io import BytesIO

    ds = pydicom.dcmread(dcm_path)

    img = ds.pixel_array

    img = img.astype(np.float32)
    img = (img - img.min()) / (img.max() - img.min()) * 255
    img = img.astype(np.uint8)

    pil_img = Image.fromarray(img)

    buffer = BytesIO()
    pil_img.save(buffer, format="PNG")

    return buffer.getvalue()

def _confirmar_reemplazo_reporte_diario(self, nombre_tabla, fecha):
    """Pregunta antes de reemplazar un reporte diario ya existente para esa
    fecha (H2.2). Aislada en su propia función -- no un QMessageBox armado a
    mano -- para que los tests puedan sustituir QMessageBox.question sin
    disparar un diálogo modal real."""
    respuesta = QMessageBox.question(
        self, "Reporte existente",
        f"Ya existe un reporte para {fecha} -- ¿reemplazarlo?",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    return respuesta == QMessageBox.Yes


def _ofrecer_reactivar_control(self, control_id):
    """N2 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md, DA-34): ofrece
    reactivar un control anulado, en la misma ventana que hoy da la
    advertencia de "no se puede subir sobre un registro anulado".

    Autenticación PERSONAL (DialogAdminPermisoEditar, no
    DialogAdminPermisoEliminar) -- decisión del físico: reactivar es una
    operación de edición del propio físico (DA-07), no un cambio fuerte que
    exija administrador.

    Aislada y mockeable (mismo patrón que _confirmar_reemplazo_reporte_
    diario, H2.2): los tests sustituyen QMessageBox.question y el diálogo
    sin disparar nada modal real.

    Returns:
        True si reactivó de verdad. False en cualquier otro caso (el
        físico declinó, la reautenticación falló, o reactivar_control
        rechazó la operación -- p.ej. por la guarda de unicidad de U2).
    """
    from ui.paginasGuia.dialogs import DialogAdminPermisoEditar

    respuesta = QMessageBox.question(
        self, "Control anulado",
        "Este control fue anulado -- ¿desea reactivarlo?",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    if respuesta != QMessageBox.Yes:
        return False

    dialogo = DialogAdminPermisoEditar(self.user_id)
    if dialogo.exec() != QDialog.DialogCode.Accepted:
        return False

    ok, motivo = _reactivar_control(control_id, _usuario_actual(self))
    if not ok:
        QMessageBox.warning(self, "No se pudo reactivar", motivo)
        return False
    return True

"Función que almecena la información en la base de datos de los controles diarios"
def add_info(self, nombre_tabla, boolean_columns, imagenes=None,
            distancias=None, promedio=None, desviacion=None,
            desplazamientos=None, promedio_des=None, desviacion_des=None):
    print(f"Entra a la función add_info en load.py con tabla: {nombre_tabla}")
    try:
        columnas_str, placeholders = encontrar_columnas(nombre_tabla, delete=0)
        
        conn = Conexion().conectar()
        cursor = conn.cursor()

        # Construir los valores a insertar
        lista = []
        lista.append(self.date_box.date().toString('yyyy-MM-dd'))

        user_id = self.user_id._nombre
        cursor.execute("SELECT fullname FROM users WHERE fullname = ?", (user_id,))
        if cursor.fetchone() is None:
            QMessageBox.critical(self, "Error", f"El usuario '{user_id}' no existe en la base de datos.")
            return
        lista.append(user_id)

        # Valores de botones
        if self.botones_ordenados:
            for dato in self.botones_ordenados:
                lista.append(1 if dato[0].text() == 'Funciona' else 0)
        else:
            for _ in self.boolean_colums:
                lista.append(None)

        # Valores de QLineEdit
        for line in self.df_lines:
            if line not in self.df_lines_dosis:
                dato = getattr(self, line)
                try:
                    lista.append(float(dato.text()))
                except ValueError:
                    QMessageBox.critical(self, "Error", f"El campo '{line}' contiene '{dato.text()}' lo cual no es un número válido.")
                    return

        for line in self.df_lines_dosis:
            dato = getattr(self, line)
            try:
                lista.append(float(dato.text()))
            except ValueError:
                QMessageBox.critical(self, "Error", f"El campo '{line}' contiene '{dato.text()}' lo cual no es un número válido.")
                return

        # Observaciones
        observaciones_text = self.observaciones.text() if self.observaciones else ""
        lista.append(observaciones_text)

        # Imagen y datos extra SOLO para braqui
        if nombre_tabla == "braqui":
            # Imagen (BLOB o None)
            # Imagen (BLOB o None)
            if imagenes:
                imagen_blob = guardar_imagen(imagenes)
                lista.append(imagen_blob)
            else:
                lista.append(None)

            # Datos extra
            lista.append(distancias)
            lista.append(promedio)
            lista.append(desviacion)
            lista.append(desplazamientos)
            lista.append(promedio_des)
            lista.append(desviacion_des)
        fecha_actual = self.date_box.date().toString("yyyy-MM-dd")

        # H2.2 (auditoría 2026-07-14): antes, un reporte existente para esta
        # fecha se reemplazaba en silencio (DELETE+INSERT sin rastro ni
        # confirmación -- hallazgo PLAN_FASE_H sección 1.6.2). El DELETE+
        # INSERT se mantiene (decisión de producto existente), pero ahora
        # requiere confirmación explícita si ya hay un registro.
        # D3 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): "activo" filtra
        # las filas ANULADAS (E7/hallazgo S1) -- sin este filtro, guardar un
        # control diario normal para una fecha que tuviera una fila anulada
        # la borraría FÍSICAMENTE, contra la política de soft-delete
        # (DA-03). Una fila anulada de esa fecha ya no cuenta como
        # "reemplazo" ni se toca: el guardado normal simplemente inserta la
        # suya al lado.
        cursor.execute(
            f"SELECT COUNT(*) FROM {nombre_tabla} WHERE DATE(date) = ? "
            "AND (activo IS NULL OR activo = 1)",
            (fecha_actual,))
        es_reemplazo = cursor.fetchone()[0] > 0
        if es_reemplazo:
            fecha_legible = self.date_box.date().toString("dd/MM/yyyy")
            if not _confirmar_reemplazo_reporte_diario(self, nombre_tabla, fecha_legible):
                return
            # H2.4: el reemplazo confirmado en H2.2 queda en audit_log.
            _registrar_auditoria(user_id, ACCION_REEMPLAZO, nombre_tabla, ref=fecha_actual)

        cursor.execute(
            f"DELETE FROM {nombre_tabla} WHERE DATE(date) = ? "
            "AND (activo IS NULL OR activo = 1)",
            (fecha_actual,))
        # Ejecutar la inserción
        sql = f"INSERT INTO {nombre_tabla} ({columnas_str}) VALUES ({placeholders})"
        cursor.execute(sql, lista)
        conn.commit()
        _registrar_auditoria(user_id, ACCION_GUARDAR, nombre_tabla, ref=fecha_actual)
        QMessageBox.information(self, "Éxito", "Datos insertados correctamente.")

        if isinstance(boolean_columns, list):
            load_table(self, boolean_columns[0], boolean_columns[1], nombre_tabla)
        else:
            load_table(self, boolean_columns, nombre_tabla)

    except sqlite3.Error as e:
        import traceback
        traceback.print_exc()
        QMessageBox.critical(self, "Error", f"Error en la consulta: {e}")

def abrir_pelicula(self, id_registro):
    """
    Recupera la imagen almacenada en el campo 'pelicula' de la tabla 'braqui'
    y la muestra en un visor.
    """
    conn = Conexion().conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT pelicula FROM braqui WHERE id = ?", (id_registro,))
    row = cursor.fetchone()
    conn.close()

    if row and row[0]:  # hay BLOB
        blob = row[0]
        pixmap = QPixmap()
        pixmap.loadFromData(blob)

        visor = QDialog(self)
        visor.setWindowTitle("Película (braqui)")
        visor.resize(800, 600)

        layout = QVBoxLayout(visor)
        label = QLabel()
        label.setPixmap(pixmap.scaled( 
            780, 580,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        ))
        layout.addWidget(label)

        visor.exec_()
    else:
        QMessageBox.warning(self, "Sin imagen", "No hay película cargada para este registro.")

"Lleva el registro del control mensual (no de braqui)"
def create_control(self, maquina, fecha, user_id, user_id_f2=None):
    print("Entrando a crear control")
    print(maquina)
    try:
        conn = Conexion().conectar()
        cursor = conn.cursor()

        # Validar usuario
        #user_id = self.user_id._nombre
        cursor.execute("SELECT fullname FROM users WHERE fullname = ?", (user_id,))
        if cursor.fetchone() is None:
            QMessageBox.critical(self, "Error", f"El usuario '{user_id}' no existe en la base de datos.")
            return

        # X1 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md §8): antes se guardaba
        # el centinela de texto " ---- " cuando no había 2º físico --
        # user_id_f2 tiene FOREIGN KEY a users(fullname), así que ese
        # centinela viola la integridad referencial (7 filas así en
        # producción) y además bloquearía activar PRAGMA foreign_keys=ON
        # (W2). NULL es la representación correcta de "sin 2º físico"; todo
        # lector existente ya lo trata igual (`if user_id_f2:`/`if
        # resultado[1]:` -- ambos falsy con None).
        _nombre_fisico2 = None
        if user_id_f2:
            cursor.execute("SELECT fullname FROM users WHERE id = ?", (user_id_f2,))
            row = cursor.fetchone()
            if row is None:
                QMessageBox.critical(self, "Error", f"El usuario '{user_id_f2}' no existe en la base de datos.")
                return
            _nombre_fisico2 = row[0]

        # Determinar tipo y fecha según si es anual o mensual
        es_anual = hasattr(self, 'esiX_images') and self.esiX_images or (hasattr(self, 'esHC_images') and self.esHC_images)
        tipo_control = "Anual" if es_anual else "Mensual"
        

        # F2 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4): la identidad de un
        # control mensual es (equipo, mes, anio, tipo) -- el dia NUNCA es
        # parte de la llave (H14/B5). Comparar "fecha = ?" como texto exacto
        # dejaba inalcanzables las 3 fichas de produccion que ya traen dia
        # (con datos reales colgando de dosimetriaMen/tamano_campo) y, una
        # vez que el formulario empiece a guardar el dia real (F3), habria
        # creado un control nuevo cada vez que se abriera un dia distinto
        # del mismo mes.
        # N1 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): antes esta
        # consulta no filtraba "activo" -- un control ANULADO se devolvía
        # igual que uno activo, y como "Subir" ya bloquea sobre un control
        # anulado (W1), el mes quedaba inutilizable en silencio (el físico
        # tuvo que crear el siguiente control en el mes SIGUIENTE). Ahora se
        # clasifica en dos candidatos independientes del mismo mes: el
        # activo (comportamiento de siempre) y el anulado (se ofrece
        # reactivar, DA-34).
        cursor.execute(
            "SELECT id, fecha, activo FROM controles WHERE equipo = ? AND control = ?",
            (maquina, tipo_control)
        )
        control_activo_id, fecha_activo = None, None
        control_anulado_id, fecha_anulado = None, None
        for fila_id, fecha_existente, activo in cursor.fetchall():
            if not _mismo_mes(fecha_existente, fecha):
                continue
            if activo is None or activo == 1:
                if control_activo_id is None:
                    control_activo_id, fecha_activo = fila_id, fecha_existente
            else:
                if control_anulado_id is None:
                    control_anulado_id, fecha_anulado = fila_id, fecha_existente

        if control_activo_id is None and control_anulado_id is not None:
            if _ofrecer_reactivar_control(self, control_anulado_id):
                control_activo_id, fecha_activo = control_anulado_id, fecha_anulado
            else:
                # Fallback seguro: NUNCA devolver None aquí -- con self.ref
                # nulo, puede_editarse() deja pasar cualquier escritura sin
                # ancla (incidente H-A, 2026-07-23: dosimetría huérfana tras
                # borrar el control desde otra vista). Devolver el id
                # anulado conserva el bloqueo de "Subir" que ya existe.
                return control_anulado_id

        if control_activo_id is not None:
            control_id = control_activo_id
            fecha_existente = fecha_activo

            # Actualizar el físico aunque ya exista el registro
            cursor.execute(
                "UPDATE controles SET user_id = ?, user_id_f2 = ? WHERE id = ?",
                (user_id, _nombre_fisico2, control_id)
            )
            conn.commit()

            if hasattr(self, 'equipo_f') and self.equipo_f in ('Tomógrafo', 'Clinac ix', 'Halcyon'):
                self.old_id = True
            # F4 (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4): decisión del
            # físico -- no se pregunta nada, solo se avisa y se carga. El
            # aviso menciona la fecha REALMENTE registrada
            # (fecha_existente), no la fecha elegida para buscar, para que
            # quede claro que se está continuando un control ya existente.
            mes_encontrado, anio_encontrado = _mes_anio_de_fecha(fecha_existente)
            if mes_encontrado is not None:
                referencia_mes = f"{mes_encontrado:02d}/{anio_encontrado}"
            else:
                referencia_mes = fecha_existente
            QMessageBox.information(
                self, "Control existente",
                f"Se cargó el control mensual de {maquina} correspondiente "
                f"a {referencia_mes}, con fecha registrada {fecha_existente}. "
                f"Puede continuar el llenado de datos."
            )
            return control_id

        # Insertar nuevo registro
        lista = [maquina, tipo_control, fecha, user_id, _nombre_fisico2]
        sql = "INSERT INTO controles (equipo, control, fecha, user_id, user_id_f2) VALUES (?,?,?,?,?)"
        cursor.execute(sql, lista)
        conn.commit()

        new_id = cursor.lastrowid
        if hasattr(self, 'equipo_f') and (self.equipo_f == 'Tomógrafo' or self.equipo_f == 'Clinac ix' or self.equipo_f == 'Halcyon') and new_id:
            self.old_id = False
        QMessageBox.information(self, "Éxito", "Datos insertados correctamente.")

        # F4c/F4d (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4): create_control
        # nunca dejaba rastro de auditoría -- sin esto, la ventana de
        # edición de dos meses (F4b) no tendría ancla alguna para ningún
        # control nuevo. `detalle` es legible (equipo + mes/año), no solo
        # el id numérico, para que el visor "Registros" no obligue a
        # cruzar ids contra `controles` a mano.
        mes_creado, anio_creado = _mes_anio_de_fecha(fecha)
        if mes_creado is not None:
            detalle_legible = f"{maquina} -- {tipo_control} {mes_creado:02d}/{anio_creado}"
        else:
            detalle_legible = f"{maquina} -- {tipo_control} {fecha}"
        _registrar_auditoria(_usuario_actual(self), ACCION_GUARDAR, "controles",
                              ref=new_id, detalle=detalle_legible)

        return new_id

    except sqlite3.Error as e:
        QMessageBox.critical(self, "Error", f"Error en la consulta: {e}")

def buscarModelo(self, filter_column, selected_column, valor_ref):
    conn = Conexion().conectar()
    cursor = conn.cursor()
    modelos = set()
    try:
        cursor.execute(f"""
        SELECT {selected_column}
        FROM equipos
        WHERE {filter_column} = ?
        AND id IN (
            SELECT MAX(id) FROM equipos GROUP BY serie
        )
        """, (valor_ref,))
        
        rows = cursor.fetchall()
        for row in rows:
            modelos.add(row[0])
    except Exception as e:
        traceback.print_exc()
        print("Error en la consulta:", e)
    finally:
        conn.commit()
    return modelos

def crear_algo(self, ref, imagen):
    print(f"\nEntra a la función crear_algo en load.py con ref: {ref} y imagen: {imagen}")
    conn = Conexion().conectar()
    cursor = conn.cursor()

    if hasattr(self, "imagen_path") and self.imagen_path:
        imagen = self.imagen_path
    else:
        QMessageBox.critical(self, "Error", "No se ha seleccionado ninguna imagen.")
        return
    
    with open(imagen, 'rb') as file:
        imagen_blob = file.read()
    
    lista = [imagen_blob, ref]
    lista2 = [ref, imagen_blob]
    cursor.execute("SELECT ref FROM preguntas WHERE ref = ?", (ref,))
    if cursor.fetchone() is None:
        QMessageBox.information(self, "Éxito", f"No existía")
        sql = f"INSERT INTO preguntas (ref, imagen) VALUES (?,?)"
        cursor.execute(sql, lista2)
        conn.commit()
        QMessageBox.information(self, "Éxito", "Se guardó la imagen.")
    else:
        sql = "UPDATE preguntas SET imagen = ? WHERE ref = ?"
        cursor.execute(sql, lista)
        conn.commit()
        QMessageBox.information(self, "Éxito", "Se guardó la imagen.")

def loadtablacomplex(nombre_tabla, table, datos, reference, from_range = 0, id_energia = 0, anual = False, pdd = None, id=False):
    # Obtener la conexión desde la clase Conexion
    if anual:
        id_ = True
    if id:
        id_ = True
    else:
        id_ = False

    #print(f"Argumentos para encontrar_columnas: nombre_tabla={nombre_tabla}, delete=0, id={id}")
    columnas_str, placeholders = encontrar_columnas(nombre_tabla, delete = 0, id = id_)
    #print(columnas_str, placeholders)
    
    ref = reference
    datos = []

    # A1 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md §A1): las columnas que
    # identifican el BLOQUE que este "Subir" reemplaza. Se calculan UNA sola
    # vez y las usan las DOS mitades de la operación -- el prefijo de cada
    # fila insertada y el DELETE de más abajo -- para que no puedan
    # divergir: se borra exactamente el bloque que se vuelve a escribir, ni
    # una fila más.
    #
    # Antes el DELETE era `WHERE ref=?` a secas, así que cada guardado
    # arrasaba con TODO el control anual, no con el bloque en curso:
    #   - subir la energía 15 MV borraba lo ya guardado de 6 MV en
    #     tabla_factor_campo / tabla_factores_transmision /
    #     tabla_control_camaras_monitoras (las 3 tienen `id_energia`);
    #   - y en tabla_factores_sobre_eje ni siquiera sobrevivía UN clic: el
    #     bucle de `guardar_todas_fse` llama aquí una vez por cada tamaño de
    #     PDD, y cada llamada borraba las PDD que las anteriores acababan de
    #     escribir -- de las 9 filas de una energía quedaban solo las 3 de
    #     la última PDD del bucle.
    #
    # El desglose reproduce EXACTAMENTE el que tenía la cadena if/elif de
    # abajo (`tam_pdd` solo cuenta en la rama anual con energía y pdd),
    # para no cambiar de paso qué se inserta.
    identificadores = [("ref", ref)]
    if id_energia is not None:
        identificadores.append(("id_energia", id_energia))
    if anual and id_energia is not None and pdd is not None:
        identificadores.append(("tam_pdd", pdd))

    print(f"Bloque identificado por {[col for col, _ in identificadores]} "
          f"para la tabla {nombre_tabla}, id = {id}")

    for fila in range(from_range, table.rowCount()):
        datafila = [valor for _, valor in identificadores]
        for columna in range(0, table.columnCount()):
            dato_item = table.item(fila, columna)
            dato = dato_item.text() if dato_item else ""
            datafila.append(dato)
        datos.append(datafila)

    print(f"\n▥ Datos a insertar en {nombre_tabla}:")
    for fila in datos:
        print(f"  - {fila}")

    #print(datos)

    # INSERT en la base de datos
    # conn = Conexion().conectar()
    # cursor = conn.cursor()
    
    #revisar que no exista ya una fila con esa info
    
    
    # Ejecutar la inserción
    sql = f"INSERT INTO {nombre_tabla} ({columnas_str}) VALUES ({placeholders})"
    
    try:
        conn = Conexion().conectar()
        cursor = conn.cursor()

        conn.execute("BEGIN TRANSACTION")

        # borrar el bloque anterior -- solo ESTE bloque (A1, ver arriba).
        # Se acota contra las columnas que la tabla tiene de verdad: si un
        # llamador pasara `pdd` para una tabla sin `tam_pdd`, un DELETE
        # contra una columna inexistente lanzaría, el rollback dejaría al
        # físico sin guardar nada y el `except` de abajo solo lo imprime en
        # consola. Acotar de menos es el fallo seguro (es lo que hacía
        # antes); acotar contra una columna que no existe, no.
        columnas_reales = {fila[1] for fila in
                           cursor.execute(f"PRAGMA table_info({nombre_tabla})")}
        acotacion = [(col, valor) for col, valor in identificadores
                     if col in columnas_reales]
        if acotacion:
            where = " AND ".join(f"{col}=?" for col, _ in acotacion)
            cursor.execute(
                f"DELETE FROM {nombre_tabla} WHERE {where}",
                tuple(valor for _, valor in acotacion)
            )

        cursor.executemany(sql, datos)

        conn.commit()

    except Exception:
        conn.rollback()
        traceback.print_exc()

    finally:
        cursor.close()
        conn.close()
            
        

ENERGIAS = {"6mv", "15mv", "6mev", "9mev", "12mev", "15mev", "9mv"}  # energías

def widget_a_columna(line, energias=ENERGIAS):
    """ÚNICA traducción nombre-de-widget -> columna de dosimetriaMen, usada
    tanto al GUARDAR (subirlineasmensuales / subirlineasmensuales_ix) como al
    CARGAR (_rellenar_campos / _cargar_dosimetria_bd_ix). H2.7: antes cada
    ruta tenía su propia normalización (una función anidada en el iX, un
    removeprefix en la carga del 600) y ya habían divergido -- la carga del
    600 buscaba columnas con el nombre del widget sin normalizar (no
    encontraba ninguna) y la del iX mapeaba POR POSICIÓN (valores corridos).

    Casos especiales:
    - lbl_*: tablas tipo `preguntas`, la columna es el nombre sin prefijo.
    - ln_calidad_j2_j1_{e} (electrones) y ln_calidad_pdd20_10_{e} (fotones)
      son el MISMO concepto y comparten la columna calidad_pdd20_10.
    - val_teo_{e} es la CALIDAD teórica (ver discrepancias():
      VALORES_REFERENCIA_CALIDAD -- 0.665/0.761/... coincide con la columna
      val_teo_calidad de la BD de producción, no con val_teo_dosis).
    """
    if line.startswith("lbl_"):
        return line.removeprefix("lbl_")
    if line.startswith("ln_calidad_j2_j1_"):
        line = line.replace("ln_calidad_j2_j1_", "ln_calidad_pdd20_10_")
    if line.startswith("val_teo_"):
        return "val_teo_calidad"
    nombre = line.removeprefix("ln_")
    for e in energias:
        if nombre.endswith(f"_{e}"):
            nombre = nombre[: -(len(e) + 1)]
            break
    return nombre

def subirlineasmensuales(self, nombre_tabla, num_delet, ref, usarid, id_energia=0, anual=False):
    # F4b (PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md SS2.4, tarea C1): un control
    # mensual de QC solo admite UPDATE dentro de la ventana de 2 meses
    # desde su creación -- decisión del físico. Anual queda fuera (su
    # create_control es otro, sin ancla de auditoría; el plan no lo cubre).
    if not anual:
        motivo = _motivo_bloqueo(ref)
        if motivo is not None:
            # N3 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md, DA-34): si el
            # bloqueo es porque el control está ANULADO, ofrecer reactivarlo
            # aquí mismo -- "la pregunta en la misma ventana que da la
            # advertencia". Cualquier otro motivo (inexistente, fuera de la
            # ventana de 2 meses de F4b) mantiene el aviso de siempre --
            # ofrecer reactivar ahí se tragaría el bloqueo de F4b.
            reactivado = motivo == "anulado" and _ofrecer_reactivar_control(self, ref)
            if not reactivado or not _puede_editarse_control(ref):
                QMessageBox.warning(self, "Control cerrado", _mensaje_bloqueo_edicion(ref))
                return
    conn = Conexion().conectar()
    cursor = conn.cursor()

    columnas_str, placeholders = encontrar_columnas(nombre_tabla, delete=num_delet, id=usarid)
    columnas_lista = columnas_str.split(", ")

    # 1. Construir diccionario nombre_columna → valor
    valores_por_columna = {}
    for line in self.df_lines:
        dato = getattr(self, line)
        if nombre_tabla == "dosimetriaMen":
            nombre_col = widget_a_columna(line)
        else:
            nombre_col = line.removeprefix("lbl_")

        try:
            if line in ('ln_observaciones_dosi', 'observaciones', 'modelo1', 'serie1',
                        'modelo2', 'serie2', 'modelo3', 'serie3'):
                valores_por_columna[nombre_col] = dato.text().strip() or None
            else:
                texto = dato.text().strip()
                valores_por_columna[nombre_col] = float(texto) if texto else None
        except ValueError:
            QMessageBox.critical(self, "Error",
                f"El campo '{line}' contiene '{dato.text()}', no es un número válido.")
            raise

    # 2. Armar datos EN EL ORDEN DEL ESQUEMA
    if anual and id_energia is not None:
        datos = [ref, id_energia]
    else:
        datos = [ref]

    for col in columnas_lista:
        if col in ("ref", "id_energia"):
            continue
        if col not in valores_por_columna:
            print(f"ADVERTENCIA: columna '{col}' no tiene widget correspondiente → None")
        datos.append(valores_por_columna.get(col, None))

    if columnas_lista[-1] == "energia":
        datos[-1] = "6mv"  # ya fue appendeado como None, sobreescribir

    # 3. INSERT o UPDATE
    cursor.execute(f"SELECT ref FROM {nombre_tabla} WHERE ref = ?", (ref,))
    if cursor.fetchone() is None:
        sql = f"INSERT INTO {nombre_tabla} ({columnas_str}) VALUES ({placeholders})"
    else:
        # H2.8 (auditoría 2026-07-16): el UPDATE SOLO toca columnas con un
        # widget presente en ESTE guardado -- antes ponía en NULL cualquier
        # columna del esquema sin widget correspondiente (p.ej. el panel
        # MLCS de Halcyon, con un único widget ajeno a dosimetriaMen, borraba
        # TODA la dosimetría ya guardada de ese mes con solo pulsar "Subir"
        # ahí). Si este guardado no aporta NINGUNA columna real, no hay nada
        # que actualizar -- no se toca la fila existente.
        columnas_a_actualizar = [col for col in columnas_lista
                                  if col != "ref" and col in valores_por_columna]
        if not columnas_a_actualizar:
            print(f"Nada que actualizar en {nombre_tabla} para ref={ref} "
                  "(ningún widget de este guardado corresponde a una columna real).")
            cursor.close()
            return
        set_clause = ", ".join([f"{col} = ?" for col in columnas_a_actualizar])
        sql = f"UPDATE {nombre_tabla} SET {set_clause} WHERE ref = ?"
        datos = [valores_por_columna[col] for col in columnas_a_actualizar] + [ref]

    try:
        cursor.execute(sql, datos)
        conn.commit()
        print("Datos guardados correctamente.")
        # H2.4: guardado mensual (600/iX, tabla única -- el multi-energía de
        # iX tiene su propio registro en subirlineasmensuales_ix).
        _registrar_auditoria(_usuario_actual(self), ACCION_GUARDAR, nombre_tabla, ref=ref)
    except Exception as ex:
        traceback.print_exc()
        print("Error al guardar:", ex)
    finally:
        cursor.close()

COLUMNAS_IDENTIFICADORAS = ("id", "ref", "id_energia", "tam_pdd")


def columnas_identificadoras(nombre_tabla):
    """Prefijo de columnas con las que el esquema identifica un bloque de
    datos anual, ANTES de los datos visibles de la tabla.

    A1 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md §A1): ÚNICA fuente para
    las dos mitades de la operación, igual que `widget_a_columna` lo es
    para dosimetriaMen -- `loadtablacomplex` acota su DELETE al bloque que
    reemplaza, y `_llenar_tabla_bd` sabe cuántas columnas recortar al
    releerlo. Que las dos lo deriven del MISMO esquema evita que vuelvan a
    divergir: el recorte estaba fijo en 3 y `tabla_factores_sobre_eje`
    tiene CUATRO identificadoras (id, ref, id_energia, tam_pdd, porque
    dentro de cada energía hay una tabla PDD por tamaño de campo), así que
    `tam_pdd` se colaba en la primera columna de la vista y corría todas
    las demás una posición.

    Se leen del esquema en orden y solo mientras sigan siendo
    identificadoras: la primera columna de datos corta el prefijo aunque
    más adelante hubiera otra columna con uno de estos nombres.
    """
    conn = Conexion().conectar()
    cursor = conn.cursor()
    try:
        columnas = [fila[1] for fila in
                    cursor.execute(f"PRAGMA table_info({nombre_tabla})")]
    except Exception:
        traceback.print_exc()
        return ()
    finally:
        cursor.close()
        conn.close()

    prefijo = []
    for columna in columnas:
        if columna not in COLUMNAS_IDENTIFICADORAS:
            break
        prefijo.append(columna)
    return tuple(prefijo)


def encontrar_columnas(nombre_tabla, id = True, delete = 1):

    conn = Conexion().conectar()
    cursor = conn.cursor()

    try:
        # Obtener los nombres de las columnas de la tabla (omitiendo la primera columna)
        cursor.execute(f"PRAGMA table_info({nombre_tabla})")
        columnas = [row[1] for row in cursor.fetchall()]

        if id == True:
            print("Manteniendo columna ID")
            columnas.pop(0)
    except Exception as e:
        traceback.print_exc()
        print('Error al obtener las columnas:', e)
        return

    # E7 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §11): `activo` es metadato de
    # anulación, agregado SIEMPRE al final por `_asegurar_activo_bloque_qc`
    # -- se excluye ANTES del recorte por `delete` para que ese recorte
    # (tuneado por cada llamador contra el esquema previo a E7) siga
    # quitando las MISMAS columnas de siempre, no la nueva columna de
    # metadato. Acotado a TABLAS_ANULABLES: `equipos` también tiene una
    # columna `activo` propia (anterior a E7, con otro significado) y no
    # debe verse afectada.
    if nombre_tabla in TABLAS_ANULABLES and columnas and columnas[-1] == "activo":
        columnas.pop()

    for _  in range(delete):
        columnas.pop(-1)
    print(f"\n▥ Columnas detectadas: {columnas} para {nombre_tabla}\n")

    # Construir la sentencia SQL
    columnas_str = ", ".join(columnas)
    placeholders = ", ".join(["?"] * len(columnas))

    return columnas_str, placeholders

def conectarfueradeservicio(self, nombre_tabla):
    conn = Conexion().conectar()
    cursor = conn.cursor()

    fecha_actual = self.date_box.date().toString('yyyy-MM-dd')
    lista = []
    lista.append(fecha_actual)

    user_id = self.user_id._nombre
    cursor.execute("SELECT fullname FROM users WHERE fullname = ?", (user_id,))
    if cursor.fetchone() is None:
        QMessageBox.critical(self, "Error", f"El usuario '{user_id}' no existe en la base de datos.")
        return

    lista.append(user_id)
    observaciones_text = self.observaciones.text() if self.observaciones else ""
    lista.append(observaciones_text)

    # D2 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): mismo contrato de
    # reemplazo por fecha que add_info (H2.2) -- antes este INSERT no
    # borraba la fila previa de esa fecha, así que dos declaraciones para
    # el mismo día (o una normal seguida de otra fuera de servicio, o
    # viceversa) acumulaban filas vacías. Causa raíz de las 7 filas del
    # 2026-08-05 en aceleradorlineal_ix.
    # D3: "activo" filtra las filas ANULADAS (E7/hallazgo S1) -- una fila
    # anulada de esa fecha no cuenta como "reemplazo" ni se borra.
    cursor.execute(
        f"SELECT COUNT(*) FROM {nombre_tabla} WHERE DATE(date) = ? "
        "AND (activo IS NULL OR activo = 1)",
        (fecha_actual,))
    es_reemplazo = cursor.fetchone()[0] > 0
    if es_reemplazo:
        fecha_legible = self.date_box.date().toString("dd/MM/yyyy")
        if not _confirmar_reemplazo_reporte_diario(self, nombre_tabla, fecha_legible):
            return
        _registrar_auditoria(user_id, ACCION_REEMPLAZO, nombre_tabla, ref=fecha_actual)

    cursor.execute(
        f"DELETE FROM {nombre_tabla} WHERE DATE(date) = ? "
        "AND (activo IS NULL OR activo = 1)",
        (fecha_actual,))
    sql = f"INSERT INTO {nombre_tabla} (date, user_id, observaciones) VALUES (?, ?, ?)"
    cursor.execute(sql, lista)
    conn.commit()

    # A6.5 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): declarar un equipo
    # fuera de servicio el día. D2: detalle explícito -- antes esta fila
    # era indistinguible en audit_log de un control diario normal.
    _registrar_auditoria(user_id, ACCION_GUARDAR, nombre_tabla, ref=fecha_actual,
                         detalle="equipo fuera de servicio")

    QMessageBox.information(self, "Éxito", "Datos insertados correctamente.")

def guardar_resultado_CambioFuente(
    user, fecha, tipo, serie, certificado, fecha_cer, intensidad, conversion,
    modelo, serie_cp, calibracion, modelo_elec, serie_ele, 
    electrometro, t0, p0, h0, t, p, h,
    posiciones, medida1, medida2, promedios,
    voltaje, V_300, V_150, Vn_300, promediosV,
    Ks, Kp, Ktp, actividad_monitor, actividad_calculada, actividad_decaimiento,
    desplazamiento_ini, observaciones):

    conn = Conexion().conectar()
    cursor = conn.cursor()
    
    cursor.execute(""" SELECT id FROM TipoCalibracion WHERE DATE(fecha) = DATE(?) AND tipo = ?""", (fecha, tipo))
    row = cursor.fetchone()
    print(fecha)
    if row:
        ref = row[0]
       
        cursor.execute("DELETE FROM SistemaMedicion WHERE ref = ?", (ref,))
        cursor.execute("DELETE FROM CondicionesMedicion WHERE ref = ?", (ref,))
        cursor.execute("DELETE FROM MaximosCamaras WHERE ref = ?", (ref,))
        cursor.execute("DELETE FROM LecturasMaximos WHERE ref = ?", (ref,))
        cursor.execute("DELETE FROM ResultadosActividad WHERE ref = ?", (ref,))
        cursor.execute("""
            UPDATE TipoCalibracion
            SET user=?, serie=?, certificado=?, fecha_cer=?, intensidad=?, conversion=?
            WHERE id=?
        """, (user, serie, certificado, fecha_cer, intensidad, conversion, ref))
    else:
    # --- Insert principal en TipoCalibracion ---
        cursor.execute("""
            INSERT INTO TipoCalibracion (user, fecha, tipo, serie, certificado, fecha_cer, intensidad, conversion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user, fecha, tipo, serie, certificado, fecha_cer, intensidad, conversion))

        ref = cursor.lastrowid  # ID generado automáticamente

    # --- SistemaMedicion ---
    cursor.execute("""
        INSERT INTO SistemaMedicion (ref, user, fecha, modelo, serie_cp, calibracion, modelo_elec, serie_ele, electrometro, t0, p0, h0)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ref, user, fecha, modelo, serie_cp, calibracion, modelo_elec, serie_ele, electrometro, t0, p0, h0))

    # --- CondicionesMedicion ---
    cursor.execute("""
        INSERT INTO CondicionesMedicion (ref, user, fecha, t, p, h, desplazamiento_ini, observaciones)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (ref, user, fecha, t, p, h, desplazamiento_ini, observaciones))

    # --- MaximosCamaras ---
    for pos, m1, m2, prom in zip(posiciones, medida1, medida2, promedios):
        cursor.execute("""
            INSERT INTO MaximosCamaras (ref, user, fecha, posicion, medida1, medida2, promedio)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ref, user, fecha, str(pos), str(m1), str(m2), str(prom)))

    # --- LecturasMaximos ---
    for idx, voltaje_val in enumerate(voltaje):
        V_300_val = f"{V_300[idx]:.2e}" if idx < len(V_300) else ""
        V_150_val = f"{V_150[idx]:.2e}" if idx < len(V_150) else ""
        Vn_300_val = f"{Vn_300[idx]:.2e}" if idx < len(Vn_300) else ""
        promedio_val = f"{promediosV[idx]:.2e}" if idx < len(promediosV) else ""

        cursor.execute("""
            INSERT INTO LecturasMaximos (ref, user, fecha, voltaje, V_300, V_150, Vn_300, promediosV)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ref, user, fecha, voltaje_val, V_300_val, V_150_val, Vn_300_val, promedio_val))

    # --- ResultadosActividad ---
    cursor.execute("""
        INSERT INTO ResultadosActividad (ref, user, fecha, Ks, Kp, Ktp, actividad_monitor, actividad_calculada, actividad_decaimiento)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ref, user, fecha, Ks, Kp, Ktp, actividad_monitor, actividad_calculada, actividad_decaimiento))

    conn.commit()
    conn.close()

    # A6.6 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): 11 escrituras (cambio
    # de fuente completo: TipoCalibracion + 5 tablas hijas) -- 1 sola fila
    # de auditoría para la acción, no una por INSERT/DELETE/UPDATE.
    _registrar_auditoria(user, ACCION_GUARDAR, "TipoCalibracion", ref=ref,
                         detalle="cambio de fuente (braquiterapia)")

    return ref  # devolver la ref generada

def mostrar_db_CambioFuente(self, tabla_a_mostrar="ResultadosActividad"):
    try:
        conn = Conexion().conectar()
        if conn is None:
            raise Exception("No se pudo obtener conexión con la base de datos.")
            

        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({tabla_a_mostrar})")
        columnas = [col[1] for col in cursor.fetchall()]
        cursor.execute(f"SELECT * FROM {tabla_a_mostrar}")
        filas = cursor.fetchall()

        self.resultados_table.setRowCount(0)
        self.resultados_table.setColumnCount(len(columnas))
        self.resultados_table.setHorizontalHeaderLabels(columnas)

        # Color de fondo igual al de los títulos
        header_brush = self.resultados_table.horizontalHeaderItem(0).background()
        insert_every = None
        if tabla_a_mostrar == "MaximosCamaras":
            insert_every = 10
        elif tabla_a_mostrar == "LecturasMaximos":
            insert_every = 3

        row_idx = 0
        for i, fila in enumerate(filas):
            if insert_every and i > 0 and i % insert_every == 0:
                self.resultados_table.insertRow(row_idx)
                for col in range(len(columnas)):
                    item = QTableWidgetItem("")
                    item.setBackground(header_brush)
                    self.resultados_table.setItem(row_idx, col, item)
                row_idx += 1

            self.resultados_table.insertRow(row_idx)
            for col_idx, valor in enumerate(fila):
                self.resultados_table.setItem(row_idx, col_idx, QTableWidgetItem(str(valor)))
            row_idx += 1

        self.resultados_table.resizeColumnsToContents()
        conn.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        QMessageBox.critical(self, "Error", f"No se pudo cargar la base de datos:\n{e}")

def mostrar_db_linealidad(self):
    # Configurar cabecera
    self.table.clear()
    headers_lin = [("ID", "id"), ("Usuario", "user"), ("Fecha", "fecha"), ("Modelo CP", "modelo"), ("Serie CP", "serie_cp"),
    ("Calibración CP", "calibracion"), ("Modelo Elec", "modelo_elec"), ("Serie Ele", "serie_ele"), ("Electrómetro", "electrometro"),
    ("Carga en 60s", None), ("Q_est", "q_est"), ("t_integrado", "t_integrado"), ("i_est", "i_est"),
    ("Ver Linealidad", None), ("Reproducibilidad", "reproducibilidad"), ("Exactitud", "exactitud"), ("Tiempo tránsito", "tiempo_transito")]

    self.table.setColumnCount(len(headers_lin))
    self.table.setHorizontalHeaderLabels([h[0] for h in headers_lin])
    self.table.setRowCount(0)

    # Cargar datos desde base de datos
    conn = Conexion().conectar()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM LinealidadBraquiterapia "
        "WHERE (activo IS NULL OR activo = 1) ORDER BY id DESC")
    resultados = cursor.fetchall()
    conn.close()

    self.table.setRowCount(len(resultados))

    for fila_idx, fila in enumerate(resultados):
        # Desempaquetar valores clave
        id_pk = fila[0]
        usuario, fecha = fila[1], fila[2]
        modelo, serie_cp, calibracion = fila[3], fila[4], fila[5]
        modelo_elec, serie_ele, electrometro = fila[6], fila[7], fila[8]
        q_est, t_integrado, i_est = fila[9], fila[10], fila[11]
        repro, exac, t_transito = fila[12], fila[13], fila[14]

        # Preparar lista de valores a mostrar
        datos_visibles = [
            id_pk, fecha, usuario, modelo, serie_cp, calibracion,
            modelo_elec, serie_ele, electrometro,
            "btn_carga",        # marcador para botón de carga
            q_est, t_integrado, i_est,
            "btn_linealidad",   # marcador para botón de linealidad
            repro, exac, t_transito
        ]

        for col_idx, dato in enumerate(datos_visibles):
            if dato == "btn_carga":
                # Botón para mostrar reproducibilidad
                btn = QPushButton("Ver tabla")
                btn.setFixedWidth(80)
                btn.setStyleSheet("background-color: rgb(255, 186, 186); color: black;")
                btn.clicked.connect(lambda _, f=fila: self.mostrar_tabla_carga(f))

                contenedor = QWidget()
                layout = QHBoxLayout(contenedor)
                layout.addWidget(btn)
                layout.setAlignment(Qt.AlignCenter)
                layout.setContentsMargins(0, 0, 0, 0)
                self.table.setCellWidget(fila_idx, col_idx, contenedor)

            elif dato == "btn_linealidad":
                # Botón para mostrar linealidad
                btn = QPushButton("Ver tabla")
                btn.setFixedWidth(80)
                btn.setStyleSheet("background-color: rgb(255, 186, 186); color: black;")
                btn.clicked.connect(lambda _, f=fila: self.mostrar_tabla_linealidad(f))

                contenedor = QWidget()
                layout = QHBoxLayout(contenedor)
                layout.addWidget(btn)
                layout.setAlignment(Qt.AlignCenter)
                layout.setContentsMargins(0, 0, 0, 0)
                self.table.setCellWidget(fila_idx, col_idx, contenedor)

            else:
                item = QTableWidgetItem(str(dato))
                item.setTextAlignment(Qt.AlignCenter)

                # Guardar metadata para edición
                # fila = (todos los valores del registro en BD)
                col_name = headers_lin[col_idx][1]  # el nombre de la columna en BD
                if col_name:  # si tiene campo en BD (no es botón)
                    # Guardamos: (id de la fila, nombre de la tabla y columna)
                    item.setData(Qt.UserRole, id_pk)
                    item.setData(Qt.UserRole + 1, ("LinealidadBraquiterapia", col_name))

                self.table.setItem(fila_idx, col_idx, item)

def mostrar_db_mensualBraqui(self):
    self.table.clear()
    headers = [ "ID", "Fecha", "Usuario", "Tipo", "Serie Fuente", "#Certificado", "Fecha_cer", "Actividad", "Factor Conversión","Modelo CP", 
                "Serie CP", "Calibración CP", "Modelo Elec", "Serie Ele","Electrómetro", "t0", "p0", "h0", "t", "p", "h", 
                "Desp. Inicial", "Observaciones", "Máximos", "Lecturas","Ks", "Kp", "Ktp", "Act. Monitor", "Act. Calculada", "Act. Decaimiento"]

    self.table.setColumnCount(len(headers))
    self.table.setHorizontalHeaderLabels(headers)
    self.table.setRowCount(0)

    # ---- Mapeo de columnas a tablas, todas están en None para que no se puedan editar ----
    col_mapeo = {
        0: None,   1: None,  2: None,  3: None, 4: None, 5: None, 6: None, 7: None, 8: None,
        9:  None, 10: None, 11: None, 12: None, 13: None, 14: None, 15: None, 16: None, 17: None,
        18: None, 19: None, 20: None,
        21: None,   # desplazamiento_ini, nace del analisis de la imagen
        22: None,   # Botón Máximos
        23: None,   # Botón Lecturas
        24: None,   # Ks     ─────────>  Nacen de un calculo
        25: None,   # Kpol   ───────────────────┘          ↑ 
        26: None,   # Ktp    ───────────────────┘          |
        27: ("ResultadosActividad", "actividad_monitor"),# |
        28: None,   # Actividad calculada──────────────────┘
        29: None,   # Actividad de decaimiento ────────────┘
        
    }

    conn = Conexion().conectar()
    cursor = conn.cursor()

    # Obtener todas las entradas base
    cursor.execute("""
        SELECT id, user, fecha, tipo, serie, certificado, fecha_cer, intensidad, conversion
        FROM TipoCalibracion WHERE (activo IS NULL OR activo = 1) ORDER BY id DESC
    """)
    entradas = cursor.fetchall()
    self.table.setRowCount(len(entradas))

    for fila_idx, (ref, user, fecha, tipo, serie, certificado, fecha_cer, intensidad, conversion) in enumerate(entradas):
        # Extraer datos vinculados por ref
        cursor.execute("SELECT modelo, serie_cp, calibracion, modelo_elec, serie_ele, electrometro, t0, p0, h0 FROM SistemaMedicion WHERE ref=?", (ref,))
        sistema = cursor.fetchone()

        cursor.execute("SELECT t, p, h, desplazamiento_ini, observaciones FROM CondicionesMedicion WHERE ref=?", (ref,))
        condiciones = cursor.fetchone()

        cursor.execute("SELECT Ks, Kp, Ktp, actividad_monitor, actividad_calculada, actividad_decaimiento FROM ResultadosActividad WHERE ref=?", (ref,))
        resultados = cursor.fetchone()

        if not (sistema and condiciones and resultados):
            continue  # Saltar fila si falta info

        datos_visibles = [
            ref, fecha, user,
            tipo, serie, certificado, fecha_cer, intensidad, conversion,
            *sistema,            # modelo, serie_cp, calibracion, modelo_elec, serie_ele, electrometro, t0, p0, h0
            *condiciones,        # t, p, h, desplazamiento_ini
            "btn_maximos",       # Botón
            "btn_lecturas",      # Botón
            *resultados          # Ks, Kp, Ktp, actividad_monitor, actividad_calculada, actividad_decaimiento
        ]

        for col_idx, dato in enumerate(datos_visibles):
            # Botón Máximos
            if dato == "btn_maximos":
                btn = QPushButton("Ver tabla")
                btn.setFixedWidth(90)
                btn.setStyleSheet("background-color: rgb(255, 186, 186); color: black;")
                btn.clicked.connect(lambda _, ses=ref: self.mostrar_tabla_maximos(ses))

                contenedor = QWidget()
                layout = QHBoxLayout(contenedor)
                layout.addWidget(btn)
                layout.setAlignment(Qt.AlignCenter)
                layout.setContentsMargins(0, 0, 0, 0)
                self.table.setCellWidget(fila_idx, col_idx, contenedor)

            # Botón Lecturas
            elif dato == "btn_lecturas":
                btn = QPushButton("Ver tabla")
                btn.setFixedWidth(90)
                btn.setStyleSheet("background-color: rgb(255, 186, 186); color: black;")
                btn.clicked.connect(lambda _, ses=ref: self.mostrar_tabla_lecturas(ses))

                contenedor = QWidget()
                layout = QHBoxLayout(contenedor)
                layout.addWidget(btn)
                layout.setAlignment(Qt.AlignCenter)
                layout.setContentsMargins(0, 0, 0, 0)
                self.table.setCellWidget(fila_idx, col_idx, contenedor)

            else:
                item = QTableWidgetItem(str(dato))
                item.setTextAlignment(Qt.AlignCenter)

                # Asignar metadata si corresponde
                if col_idx in col_mapeo and col_mapeo[col_idx]:
                    table_name, col_name = col_mapeo[col_idx]
                    item.setData(Qt.UserRole, ref)                 # siempre guardamos el ref
                    item.setData(Qt.UserRole + 1, (table_name, col_name))

                self.table.setItem(fila_idx, col_idx, item)

    conn.close()
def guardar_analisis_placa600(ref, datos, parent=None, cm_por_pixel=None):
    """
    Guarda en la base de datos los datos de análisis de la placa relacionado el id de control mensual 'ref'
    y el diccionario 'datos' que devuelve la función principal.
    """

    try:
        conn = Conexion().conectar()
        cursor = conn.cursor()

        mm_por_pixel = datos["cm_por_pixel"] * 10

        # =========================
        # ELIMINAR DATOS DUPLICADOS
        # =========================

        # Borra análisis anteriores de este ref
        cursor.execute(
            "DELETE FROM analisis_placa_franjas WHERE ref = ?",
            (ref,)
        )

        cursor.execute(
            "DELETE FROM analisis_placa_verificaciones WHERE ref = ?",
            (ref,)
        )

        cursor.execute(
            "DELETE FROM analisis_placa_correcciones WHERE ref = ?",
            (ref,)
        )

        # Función auxiliar para redondear
        def rd(v):
            return round(v, 3) if isinstance(v, (int, float)) else None

        # =========================
        # GUARDAR FRANJAS
        # =========================

        for franja_idx, franja in enumerate(datos["franjas"], start=1):

            cursor.execute("""
                INSERT INTO analisis_placa_franjas (
                    ref, franja, ancho_media_h, ancho_media_v,
                    penumbra_izq_h, penumbra_izq_v,
                    penumbra_der_h, penumbra_der_v,
                    diferencia_arriba_izq, diferencia_arriba_der,
                    diferencia_abajo_izq, diferencia_abajo_der
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ref,
                f"Franja {franja_idx}",

                rd(franja["anchura"]["horizontal"] * mm_por_pixel)
                if franja["anchura"]["horizontal"] is not None else None,

                rd(franja["anchura"]["vertical"] * mm_por_pixel)
                if franja["anchura"]["vertical"] is not None else None,

                rd(franja["penumbra_izquierda"]["horizontal"] * mm_por_pixel)
                if franja["penumbra_izquierda"]["horizontal"] is not None else None,

                rd(franja["penumbra_izquierda"]["vertical"] * mm_por_pixel)
                if franja["penumbra_izquierda"]["vertical"] is not None else None,

                rd(franja["penumbra_derecha"]["horizontal"] * mm_por_pixel)
                if franja["penumbra_derecha"]["horizontal"] is not None else None,

                rd(franja["penumbra_derecha"]["vertical"] * mm_por_pixel)
                if franja["penumbra_derecha"]["vertical"] is not None else None,

                rd(franja["excesos"][0] * mm_por_pixel)
                if franja["excesos"] else None,

                rd(franja["excesos"][1] * mm_por_pixel)
                if franja["excesos"] else None,

                rd(franja["excesos"][2] * mm_por_pixel)
                if franja["excesos"] else None,

                rd(franja["excesos"][3] * mm_por_pixel)
                if franja["excesos"] else None
            ))

        # =========================
        # GUARDAR VERIFICACIONES
        # =========================

        for tipo in ["verificacion_inicial", "verificacion_ideal"]:

            ver = datos["verificacion"][tipo]

            cursor.execute("""
                INSERT INTO analisis_placa_verificaciones (
                    ref, tipo, angulo1, angulo2, angulo3, angulo4,
                    lado_arriba, lado_abajo, lado_izquierda, lado_derecha,
                    desv_vert_izq, desv_vert_der,
                    desv_horiz_arriba, desv_horiz_abajo,
                    ortogonal, simetrico,
                    alineado_horizontal, alineado_vertical, torcido
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ref,
                tipo,

                rd(ver["angulos"][0]),
                rd(ver["angulos"][1]),
                rd(ver["angulos"][2]),
                rd(ver["angulos"][3]),

                rd(ver["lados_mm"]["arriba"]),
                rd(ver["lados_mm"]["abajo"]),
                rd(ver["lados_mm"]["izquierda"]),
                rd(ver["lados_mm"]["derecha"]),

                rd(ver["alineacion_mm"]["vertical_izquierda"]),
                rd(ver["alineacion_mm"]["vertical_dererecha"]),

                rd(ver["alineacion_mm"]["horizontal_arriba"]),
                rd(ver["alineacion_mm"]["horizontal_abajo"]),

                int(ver["estado"]["ortogonal"]),
                int(ver["estado"]["simetrico"]),
                int(ver["estado"]["alineado_horizontal"]),
                int(ver["estado"]["alineado_vertical"]),
                int(ver["estado"]["torcido"])
            ))

        # =========================
        # GUARDAR CORRECCIONES
        # =========================

        for vertice, valores in datos["verificacion"]["correcciones"].items():

            dif = datos["verificacion"]["excesos_ideal"]

            cursor.execute("""
                INSERT INTO analisis_placa_correcciones (
                    ref, vertice, delta_x, delta_y,
                    diferencia_arriba, diferencia_abajo,
                    diferencia_izquierda, diferencia_derecha
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ref,
                vertice,

                rd(float(valores["Δx"])),
                rd(float(valores["Δy"])),

                rd(dif["arriba_izq"]),
                rd(dif["arriba_der"]),
                rd(dif["abajo_izq"]),
                rd(dif["abajo_der"])
            ))

        conn.commit()
        conn.close()

        QMessageBox.information(
            parent,
            "Éxito",
            "Datos guardados correctamente en la base de datos."
        )

    except Exception as e:

        print("\nError en guardar_analisis_placa600:")
        print(traceback.format_exc())

        QMessageBox.critical(
            parent,
            "Error",
            f"No se pudo guardar el análisis:\n{str(e)}"
        )
# ..................................... Funciones_controles_mensuales ............................................

" ---------------------------------------- MOSTRAR CONTROLES MENSUALES HALCYON ----------------------"

def mostrar_controles_mensuales(parent, tableWidget, equipo_filtrar=None):
    conn = Conexion().conectar()
    cursor = conn.cursor()

    if equipo_filtrar == "Halcyon":
        query = """
        SELECT 
            cm.id,
            cm.fecha,
            u.fullname,
            cm.equipo,
            (SELECT dosis_ref_cgy_um FROM dosimetriaMen 
            WHERE ref = cm.id AND energia = '6mv' LIMIT 1) as dosis_ref_cgy_um
        FROM controles cm
        LEFT JOIN users u ON cm.user_id = u.fullname
        LEFT JOIN preguntas p ON cm.id = p.ref
        """
    else:
        query = """
        SELECT 
            cm.id,
            cm.fecha,
            u.fullname,
            cm.equipo,
            p.iso_mec,
            p.reticulo_cent,
            p.bordes_coin,
            p.camilla_vert_rango,
            p.camilla_vert_desp,
            p.camilla_iso_desp,
            p.telem_rango,
            p.telem_desp,
            p.puntero_telem_diff,
            p.laser_techo,
            p.laser_lateral9,
            p.laser_lateral27,
            (SELECT dosis_ref_cgy_um FROM dosimetriaMen 
            WHERE ref = cm.id AND energia = '6mv' LIMIT 1) as dosis_ref_cgy_um
        FROM controles cm
        LEFT JOIN users u ON cm.user_id = u.fullname
        LEFT JOIN preguntas p ON cm.id = p.ref
        """

    # C2 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md): un control anulado
    # (activo=0, ver eliminarRegistro) no debe seguir apareciendo en el
    # listado -- sigue en la BD (soft-delete), solo se oculta de la vista.
    if equipo_filtrar:
        query += (" WHERE cm.equipo = ? AND cm.control = 'Mensual' "
                  "AND (cm.activo IS NULL OR cm.activo = 1) ORDER BY cm.fecha DESC")
        cursor.execute(query, (equipo_filtrar,))
    else:
        query += " WHERE (cm.activo IS NULL OR cm.activo = 1)"
        cursor.execute(query)

    rows = cursor.fetchall()
    conn.close()

    if equipo_filtrar == "Halcyon":
        headers = [ 
            ("Fecha", ("controles", "fecha")),
            ("Usuario", None),
            ("Equipo", None),
            ("Eq. Medición", None),
            ("Laseres", None),
            ("Indc. Angulares", None),
            ("Indc. Camilla", None),
            ("Desp. Isocentro", None),
            ("Tam. Campos", None),
            ("Análisis Img", None),
            ("Imagen", None),
            ("Dosimetría", None),
            ("Reporte PDF", None)
        ]
    else:
        headers = [ 
            ("Fecha", ("controles", "fecha")),
            ("Usuario", None),
            ("Equipo", None),
            ("Eq. Medición", None),
            ("Seguridad", None),
            ("Indc. Angulares", None),
            ("Tam. Isocentro", ("preguntas", "iso_mec")),
            ("Centrado Ret.", ("preguntas", "reticulo_cent")),
            ("Coincidencia Bor.", ("preguntas", "bordes_coin")),
            ("Tam. Campos", None),
            ("Cami. Rango", ("preguntas", "camilla_vert_rango")),
            ("Cami. Desp", ("preguntas", "camilla_vert_desp")),
            ("Des. Isocentro", ("preguntas", "camilla_iso_desp")),
            ("Rango Tel.", ("preguntas", "telem_rango")),
            ("Des. Tel", ("preguntas", "telem_desp")),
            ("Análisis Img", None),
            ("Dif. Punt - Tel", ("preguntas", "puntero_telem_diff")),
            ("Lás. Techo", ("preguntas", "laser_techo")),
            ("Lás. 90°", ("preguntas", "laser_lateral9")),
            ("Lás. 270°", ("preguntas", "laser_lateral27")),
            ("Imagen", None),
            ("Dosimetría", None),
            ("Reporte PDF", None)
        ]

    tableWidget.setColumnCount(len(headers))
    tableWidget.setRowCount(len(rows))

    for i, (texto, meta) in enumerate(headers):
        header_item = QTableWidgetItem(texto)
        header_item.setData(Qt.UserRole, meta)
        tableWidget.setHorizontalHeaderItem(i, header_item)

    def crear_boton_tabla(texto, callback):
        btn = QPushButton(texto)
        btn.setFixedWidth(80)
        btn.setStyleSheet("background-color: rgb(255, 186, 186); color: black;")
        btn.clicked.connect(callback)
        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.addWidget(btn)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        return contenedor

    def valor_a_texto(val, decimales=3):
        if val is None:
            return ""
        if isinstance(val, (float, int)):
            return f"{val:.{decimales}f}" if isinstance(val, float) else str(val)
        return str(val)

    for row_idx, row_data in enumerate(rows):
        id_ref = row_data[0]  # ID real de controles_mensuales

        # --- Col 0: Fecha (pero guardamos el ID real en UserRole) ---
        item = QTableWidgetItem(valor_a_texto(row_data[1], 0))  # fecha visible
        item.setData(Qt.UserRole, id_ref)  # <-- aquí guardamos el ID real
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 0, item)

        # Col 1: Usuario
        item = QTableWidgetItem(valor_a_texto(row_data[2]))
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 1, item)

        # Col 2: Equipo
        item = QTableWidgetItem(valor_a_texto(row_data[3]))
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 2, item)

        # Col 3: Eq. Medición
        tableWidget.setCellWidget(row_idx, 3, crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_equipos(parent, r)))

        # Col 4: Seguridad
        # ix_arg = True if equipo_filtrar == "Clinac ix" else False
        # tableWidget.setCellWidget(row_idx, 4, crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_seguridad(parent, r, ix=ix_arg)))

        # # Col 5: Indc. Angulares
        # if equipo_filtrar == "Halcyon":
        #     tableWidget.setCellWidget(row_idx, 5, crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_indc_brazo_HC(parent, r)))
        # else:
        #     tableWidget.setCellWidget(row_idx, 5, crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_indc_angulares(parent, r)))
            
            
        if equipo_filtrar!="Halcyon":
            ####################################################################################
            ix_arg = True if equipo_filtrar == "Clinac ix" else False
            tableWidget.setCellWidget(row_idx, 4, crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_seguridad(parent, r, ix=ix_arg)))
            #####################################################################################
            tableWidget.setCellWidget(row_idx, 5, crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_indc_angulares(parent, r)))
            ## Cols 6–8 valores (preguntas)
            for col, data in zip(range(6, 9), row_data[4:7]):  # iso_mec, reticulo_cent, bordes_coin
                item = QTableWidgetItem(valor_a_texto(data))
                header_meta = tableWidget.horizontalHeaderItem(col).data(Qt.UserRole)
                if header_meta:
                    table_name, col_name = header_meta
                    item.setData(Qt.UserRole, id_ref)                # clave primaria (id_ref)
                    item.setData(Qt.UserRole + 1, (table_name, col_name))  # metadata tabla/columna
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignCenter)
                tableWidget.setItem(row_idx, col, item)

            # Col 9: Tam. Campos (BOTÓN)
            tableWidget.setCellWidget(
                row_idx,
                9,
                crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_tam_campos(parent, r))
            )

            # Cols 10–15 valores (preguntas)
            for col, data in zip(range(10, 16), row_data[7:13]):
                item = QTableWidgetItem(valor_a_texto(data))
                header_meta = tableWidget.horizontalHeaderItem(col).data(Qt.UserRole)
                if header_meta:
                    table_name, col_name = header_meta
                    item.setData(Qt.UserRole, id_ref)                # clave primaria (id_ref)
                    item.setData(Qt.UserRole + 1, (table_name, col_name))  # metadata tabla/columna
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignCenter)
                tableWidget.setItem(row_idx, col, item)

            # Col 16: Eq. Medición
            tableWidget.setCellWidget(row_idx, 15, crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_analisis_franjas(parent, r)))


            # Cols 16–19 valores (preguntas)
            for col, data in zip(range(16, 20), row_data[12:16]):
                item = QTableWidgetItem(valor_a_texto(data))
                header_meta = tableWidget.horizontalHeaderItem(col).data(Qt.UserRole)
                if header_meta:
                    table_name, col_name = header_meta
                    item.setData(Qt.UserRole, id_ref)                # clave primaria (id_ref)
                    item.setData(Qt.UserRole + 1, (table_name, col_name))  # metadata tabla/columna
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignCenter)
                tableWidget.setItem(row_idx, col, item)

            # Col 20: Dos. Ref.
            valor_img = row_data[16]
            if valor_img:  # si no es None ni vacío
                texto_imagen = "Imagen Cargada"
            else:
                texto_imagen = ""

            item = QTableWidgetItem(texto_imagen)

            header_meta = tableWidget.horizontalHeaderItem(20).data(Qt.UserRole)
            if header_meta:
                table_name, col_name = header_meta
                item.setData(Qt.UserRole, id_ref)
                item.setData(Qt.UserRole + 1, (table_name, col_name))
                item.setFlags(item.flags() | Qt.ItemIsEditable)
            else:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            item.setTextAlignment(Qt.AlignCenter)
            tableWidget.setItem(row_idx, 20, item)


            # Col 21: Dosimetría
            tableWidget.setCellWidget(row_idx, 21, crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_dosimetria(parent, r)))

            # Col 22: Reporte
            tableWidget.setCellWidget(row_idx, 22, crear_boton_tabla("Ver reporte", lambda _, r=id_ref, f=row_data[1]: _generar_reporte_desde_tabla(parent, f, equipo_filtrar)))
        else:
            tableWidget.setCellWidget(row_idx, 4, crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_laseres(parent, r)))
            
            tableWidget.setCellWidget(row_idx, 5, crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_indc_brazo_HC(parent, r)))

            tableWidget.setCellWidget(row_idx, 6, crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_indicadores_camilla(parent, r)))
            
            tableWidget.setCellWidget(
                row_idx,
                7,
                crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_des_isoc(parent, r))
            )
            
            tableWidget.setCellWidget(
                row_idx,
                8,
                crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_tam_campos_HC(parent, r))
            )

           
            tableWidget.setCellWidget(row_idx, 9, crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_analisis_franjas(parent, r)))


            valor_img = row_data[3]
            if valor_img:  # si no es None ni vacío
                texto_imagen = "Imagen Cargada"
            else:
                texto_imagen = ""

            item = QTableWidgetItem(texto_imagen)

            header_meta = tableWidget.horizontalHeaderItem(9).data(Qt.UserRole)
            if header_meta:
                table_name, col_name = header_meta
                item.setData(Qt.UserRole, id_ref)
                item.setData(Qt.UserRole + 1, (table_name, col_name))
                item.setFlags(item.flags() | Qt.ItemIsEditable)
            else:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            item.setTextAlignment(Qt.AlignCenter)
            tableWidget.setItem(row_idx, 10, item)


            # Col 21: Dosimetría
            tableWidget.setCellWidget(row_idx, 11, crear_boton_tabla("Ver tabla", lambda _, r=id_ref: mostrar_dosimetria(parent, r)))

            # Col 22: Reporte
            tableWidget.setCellWidget(row_idx, 12, crear_boton_tabla("Reporte", lambda _, r=id_ref, f=row_data[1]: _generar_reporte_desde_tabla(parent, f, equipo_filtrar)))
            
    def _generar_reporte_desde_tabla(parent, fecha, maquina):
        if parent is None:
            QMessageBox.warning(None, "Error", "No hay contexto disponible para generar el reporte.")
            return
        from models.PDF.Mensuales.reportes_mensuales import guardarPDF_mensual, obtener_diccionario_600, obtener_diccionario_ix, obtener_diccionario_halcyon
        
        if equipo_filtrar == 'Clinac 600':
            diccionario = obtener_diccionario_600()
        if equipo_filtrar == 'Clinac ix':
            diccionario = obtener_diccionario_ix()
        if equipo_filtrar == "Halcyon":
            diccionario = obtener_diccionario_halcyon()
        guardarPDF_mensual(parent, fecha, maquina, diccionario=diccionario)


"------------------------------------------------------------------------------------------------------------------"
def mostrar_controles_imgIX_anual(parent, tableWidget, usuario, equipo_filtrar=None):
    
    conn = Conexion().conectar()
    cursor = conn.cursor()

    tableWidget.clearContents()
    tableWidget.setRowCount(0)
    tableWidget.setColumnCount(0)
    cursor.execute("""
    SELECT c.id, c.fecha, c.equipo, c.control, COUNT(p.id_prueba) as num_pruebas
    FROM controles c
    LEFT JOIN pruebas p ON p.id_sesion = c.id
    WHERE c.equipo = 'Clinac ix' AND c.control = 'Anual'
        AND (c.activo IS NULL OR c.activo = 1)
        GROUP BY c.id
    """)
    print("Usted está aquí mostrar controles imgIX anual ")
    print(cursor.fetchall())
   
    query = """
    SELECT 
        c.id as id_sesion,
        substr(c.fecha, 4, 4) || '-' || substr(c.fecha, 1, 2) as fecha,
        u.fullname,
        c.equipo,
        MAX(p.kv) as kv,
        MAX(p.ma) as ma,
        MAX(p.espesor_corte) as espesor_corte,
        MAX(p.imagen_path) as imagen_path,
        MAX(p.imagen_resultado) as imagen_resultado,
        MIN(p.id_prueba) as id_prueba
    FROM controles c
    LEFT JOIN pruebas p ON p.id_sesion = c.id
    LEFT JOIN users u ON c.user_id = u.fullname
    WHERE c.equipo = 'Clinac ix'
    AND c.control = 'Anual'
    AND (c.activo IS NULL OR c.activo = 1)
    GROUP BY c.id, c.fecha, c.equipo
    ORDER BY c.fecha DESC
    """
    

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.commit()
    conn.close()
    # ... resto igual

    headers = [ 
        ("Fecha", None),
        ("Usuario", None),
        ("Equipo", None),
        ("kV", None),
        ("mA", None),
        ("Espesor Corte", None),
        ("Valores CT", None),
        ("Uniformidad Ruido", None),
        ("Uniformidad Global", None),
        ("Resolución Espacial", None),
        ("Linealidad CT", None),
        ("Espesor Corte Análisis", None),
        ("Tamaño Pixel", None),
        ("Imagen", None),
        ("Resultado", None),
        ("Reporte", None),
    ]

    tableWidget.setColumnCount(len(headers))
    tableWidget.setRowCount(len(rows))

    for i, (texto, meta) in enumerate(headers):
        header_item = QTableWidgetItem(texto)
        header_item.setData(Qt.UserRole, meta)
        tableWidget.setHorizontalHeaderItem(i, header_item)

    def crear_boton_tabla(texto, callback):
        btn = QPushButton(texto)
        btn.setFixedWidth(80)
        btn.setStyleSheet("background-color: #b7ffc9;color: black;")
        btn.clicked.connect(callback)
        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.addWidget(btn)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        return contenedor

    def valor_a_texto(val, decimales=3):
        if val is None:
            return ""
        if isinstance(val, (float, int)):
            return f"{val:.{decimales}f}" if isinstance(val, float) else str(val)
        return str(val)

    for row_idx, row_data in enumerate(rows):
        id_prueba = row_data[9]
        mes_control = row_data[1]
        mes_control = mes_control.replace('/', '-')
        
        equipo = row_data[3]
        id_session = row_data[0]

        # Col 0: Fecha
        item = QTableWidgetItem(valor_a_texto(row_data[1], 0))
        item.setData(Qt.UserRole, id_session)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 0, item)

        # Col 1: Usuario
        item = QTableWidgetItem(valor_a_texto(row_data[2]))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 1, item)

        # Col 2: Equipo
        item = QTableWidgetItem(valor_a_texto(row_data[3]))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 2, item)

        # Col 3: kV
        item = QTableWidgetItem(valor_a_texto(row_data[4], 0))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 3, item)

        # Col 4: mA
        item = QTableWidgetItem(valor_a_texto(row_data[5], 0))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 4, item)

        # Col 5: Espesor Corte
        item = QTableWidgetItem(valor_a_texto(row_data[6], 2))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 5, item)

        # Col 6: Valores CT
        tableWidget.setCellWidget(row_idx, 6, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_valores_ct(parent, m)))

        # Col 7: Uniformidad Ruido
        tableWidget.setCellWidget(row_idx, 7, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_uniformidad_ruido(parent, m)))

        # Col 8: Uniformidad Global
        tableWidget.setCellWidget(row_idx, 8, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_uniformidad_global(parent, m)))

        # Col 9: Resolución Espacial
        tableWidget.setCellWidget(row_idx, 9, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_resolucion_espacial(parent, m)))

        # Col 10: Linealidad CT
        tableWidget.setCellWidget(row_idx, 10, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_linealidad_ct(parent, m)))

        # Col 11: Espesor Corte Análisis
        tableWidget.setCellWidget(row_idx, 11, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_espesor_corte_analisis(parent, m)))

        # Col 12: Tamaño Pixel
        tableWidget.setCellWidget(row_idx, 12, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_tamaño_pixel(parent, m)))

        # Col 13: Imagen
        valor_img = row_data[7]
        texto_imagen = "Imagen Cargada" if valor_img else ""
        item = QTableWidgetItem(texto_imagen)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        tableWidget.setItem(row_idx, 13, item)

        # Col 14: Resultado
        valor_resultado = row_data[8]
        texto_resultado = "Imagen Cargada" if valor_resultado else ""
        item = QTableWidgetItem(texto_resultado)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        tableWidget.setItem(row_idx, 14, item)
        
        # Col 15: reporte
        tableWidget.setCellWidget(row_idx, 15, crear_boton_tabla("Reporte", lambda _, m=mes_control, e=equipo ,s= id_session: _generar_reporte_desde_tabla(parent, m, equipo, s)))
        print("Equipo seleccionado para reporte ")
        print(equipo)
        
    def _generar_reporte_desde_tabla(parent, fecha, maquina, id_sesion):
        
        if parent is None:
            QMessageBox.warning(None, "Error", "No hay contexto disponible para generar el reporte.")
            return
        
        
       
        from models.PDF.Imagenes.reportes_control_sistema_imagenes import generar_reporte_sistema_imagenes
    
          # O el atributo que corresponda a tu usuario
        generar_reporte_sistema_imagenes(parent, fecha, maquina, usuario, id_sesion, sistema_imagenes=True)
def mostrar_controles_imgIX(parent, tableWidget,usuario,equipo_filtrar=None):
    conn = Conexion().conectar()
    cursor = conn.cursor()
    tableWidget.clearContents()
    tableWidget.setRowCount(0)
    tableWidget.setColumnCount(0)
    cursor.execute("""
    SELECT c.id, c.fecha, c.equipo, c.control, COUNT(p.id_prueba) as num_pruebas
    FROM controles c
    LEFT JOIN pruebas p ON p.id_sesion = c.id
    WHERE c.equipo = 'Clinac ix' AND c.control = 'Mensual'
        AND (c.activo IS NULL OR c.activo = 1)
        GROUP BY c.id
    """)
    conn.commit()
    cursor.execute("PRAGMA table_info(pruebas)")
    columns = [col[1] for col in cursor.fetchall()]
    if "mes_control" not in columns:
        print("mes control")
        cursor.execute("ALTER TABLE pruebas ADD COLUMN mes_control TEXT")
        
    query_addmonth = """ 
                    UPDATE pruebas
                    SET mes_control = strftime('%Y-%m', created_at)
                    WHERE mes_control IS NULL    
                    """
    cursor.execute(query_addmonth)
    conn.commit()
    
    
    "-----------------------------------------------------------------------------------------------------------------"
    
    query = """
    SELECT 
    c.id as id_sesion,
    c.fecha as fecha,
    u.fullname,
    c.equipo,
    MAX(p.kv) as kv,
    MAX(p.ma) as ma,
    MAX(p.espesor_corte) as espesor_corte,
    MAX(p.imagen_path) as imagen_path,
    MAX(p.imagen_resultado) as imagen_resultado,
    MIN(p.id_prueba) as id_prueba
    FROM controles c
    LEFT JOIN pruebas p ON p.id_sesion = c.id
    LEFT JOIN users u ON c.user_id = u.fullname
    WHERE c.equipo = 'Clinac ix'
    AND c.control = 'Mensual'
    AND (c.activo IS NULL OR c.activo = 1)
    GROUP BY c.id, c.equipo
    ORDER BY c.fecha DESC
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.commit()
    conn.close()

    headers = [ 
        ("Fecha", None),
        ("Usuario", None),
        ("Equipo", None),
        ("kV", None),
        ("mA", None),
        ("Espesor Corte", None),
        ("Valores CT", None),
        ("Uniformidad Ruido", None),
        ("Uniformidad Global", None),
        ("Resolución Espacial", None),
        ("Linealidad CT", None),
        ("Espesor Corte Análisis", None),
        ("Tamaño Pixel", None),
        ("Imagen", None),
        ("Resultado", None),
        ("Reporte", None),
    ]

    tableWidget.setColumnCount(len(headers))
    tableWidget.setRowCount(len(rows))

    for i, (texto, meta) in enumerate(headers):
        header_item = QTableWidgetItem(texto)
        header_item.setData(Qt.UserRole, meta)
        tableWidget.setHorizontalHeaderItem(i, header_item)

    def crear_boton_tabla(texto, callback):
        btn = QPushButton(texto)
        btn.setFixedWidth(80)
        btn.setStyleSheet("background-color: rgb(255, 186, 186); color: black;")
        btn.clicked.connect(callback)
        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.addWidget(btn)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        return contenedor

    def valor_a_texto(val, decimales=3):
        if val is None:
            return ""
        if isinstance(val, (float, int)):
            return f"{val:.{decimales}f}" if isinstance(val, float) else str(val)
        return str(val)

    for row_idx, row_data in enumerate(rows):
        id_prueba = row_data[9]
        mes_control = row_data[1]
        mes_control = row_data[1].replace('/', '-')          # "04-2026" para queries... pero aun así el orden es mes/año
        # convierte a año-mes para que coincida con mes_control en pruebas
        partes = row_data[1].split('/')                      
        mes_control = f"{partes[1]}-{partes[0]}" if len(partes) == 2 else row_data[1]  # "2026-04"
        equipo = row_data[3]
        id_session = row_data[0]
 
        # Col 0: Fecha
        item = QTableWidgetItem(valor_a_texto(row_data[1], 0))
        item.setData(Qt.UserRole, id_session)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 0, item)

        # Col 1: Usuario
        item = QTableWidgetItem(valor_a_texto(row_data[2]))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 1, item)

        # Col 2: Equipo
        item = QTableWidgetItem(valor_a_texto(row_data[3]))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 2, item)

        # Col 3: kV
        item = QTableWidgetItem(valor_a_texto(row_data[4], 0))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 3, item)

        # Col 4: mA
        item = QTableWidgetItem(valor_a_texto(row_data[5], 0))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 4, item)

        # Col 5: Espesor Corte
        item = QTableWidgetItem(valor_a_texto(row_data[6], 2))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 5, item)

        # Col 6: Valores CT
        tableWidget.setCellWidget(row_idx, 6, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_valores_ct(parent, m)))

        # Col 7: Uniformidad Ruido
        tableWidget.setCellWidget(row_idx, 7, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_uniformidad_ruido(parent, m)))

        # Col 8: Uniformidad Global
        tableWidget.setCellWidget(row_idx, 8, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_uniformidad_global(parent, m)))

        # Col 9: Resolución Espacial
        tableWidget.setCellWidget(row_idx, 9, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_resolucion_espacial(parent, m)))

        # Col 10: Linealidad CT
        tableWidget.setCellWidget(row_idx, 10, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_linealidad_ct(parent, m)))

        # Col 11: Espesor Corte Análisis
        tableWidget.setCellWidget(row_idx, 11, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_espesor_corte_analisis(parent, m)))

        # Col 12: Tamaño Pixel
        tableWidget.setCellWidget(row_idx, 12, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_tamaño_pixel(parent, m)))

        # Col 13: Imagen
        valor_img = row_data[7]
        texto_imagen = "Imagen Cargada" if valor_img else ""
        item = QTableWidgetItem(texto_imagen)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        tableWidget.setItem(row_idx, 13, item)

        # Col 14: Resultado
        valor_resultado = row_data[8]
        texto_resultado = "Imagen Cargada" if valor_resultado else ""
        item = QTableWidgetItem(texto_resultado)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        tableWidget.setItem(row_idx, 14, item)
        
        # Col 15: reporte
        tableWidget.setCellWidget(row_idx, 15, crear_boton_tabla("Reporte", lambda _, m=mes_control, e=equipo ,s= id_session: _generar_reporte_desde_tabla(parent, m, equipo, s)))
        print("Equipo seleccionado para reporte ")
        print(equipo)
        
    def _generar_reporte_desde_tabla(parent, fecha, maquina, id_sesion):
        if parent is None:
            QMessageBox.warning(None, "Error", "No hay contexto disponible para generar el reporte.")
            return
        
        
       
        from models.PDF.Imagenes.reportes_control_sistema_imagenes import generar_reporte_sistema_imagenes
    
          # O el atributo que corresponda a tu usuario
        generar_reporte_sistema_imagenes(parent, fecha, maquina, usuario, id_sesion, sistema_imagenes=True)
        
 
 
        
def mostrar_controles_imgHC_anual(parent, tableWidget,usuario,equipo_filtrar=None):
    
    conn = Conexion().conectar()
    cursor = conn.cursor()

    tableWidget.clearContents()
    tableWidget.setRowCount(0)
    tableWidget.setColumnCount(0)
    cursor.execute("""
    SELECT c.id, c.fecha, c.equipo, c.control, COUNT(p.id_prueba) as num_pruebas
    FROM controles c
    LEFT JOIN pruebas p ON p.id_sesion = c.id
    WHERE c.equipo = 'Halcyon' AND c.control = 'Anual'
        AND (c.activo IS NULL OR c.activo = 1)
        GROUP BY c.id
    """)
    print("Usted está aquí mostrar controles HC anual ")
    print(cursor.fetchall())
   
    query = """
    SELECT 
        c.id as id_sesion,
        substr(c.fecha, 4, 4) || '-' || substr(c.fecha, 1, 2) as fecha,
        u.fullname,
        c.equipo,
        MAX(p.kv) as kv,
        MAX(p.ma) as ma,
        MAX(p.espesor_corte) as espesor_corte,
        MAX(p.imagen_path) as imagen_path,
        MAX(p.imagen_resultado) as imagen_resultado,
        MIN(p.id_prueba) as id_prueba
    FROM controles c
    LEFT JOIN pruebas p ON p.id_sesion = c.id
    LEFT JOIN users u ON c.user_id = u.fullname
    WHERE c.equipo = 'Halcyon'
    AND c.control = 'Anual'
    AND (c.activo IS NULL OR c.activo = 1)
    GROUP BY c.id, c.fecha, c.equipo
    ORDER BY c.fecha DESC
    """
    

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.commit()
    conn.close()
    # ... resto igual

    headers = [ 
        ("Fecha", None),
        ("Usuario", None),
        ("Equipo", None),
        ("kV", None),
        ("mA", None),
        ("Espesor Corte", None),
        ("Valores CT", None),
        ("Uniformidad Ruido", None),
        ("Uniformidad Global", None),
        ("Resolución Espacial", None),
        ("Linealidad CT", None),
        ("Espesor Corte Análisis", None),
        ("Tamaño Pixel", None),
        ("Imagen", None),
        ("Resultado", None),
        ("Reporte", None),
    ]

    tableWidget.setColumnCount(len(headers))
    tableWidget.setRowCount(len(rows))

    for i, (texto, meta) in enumerate(headers):
        header_item = QTableWidgetItem(texto)
        header_item.setData(Qt.UserRole, meta)
        tableWidget.setHorizontalHeaderItem(i, header_item)

    def crear_boton_tabla(texto, callback):
        btn = QPushButton(texto)
        btn.setFixedWidth(80)
        btn.setStyleSheet("background-color: #b7ffc9;color: black;")
        btn.clicked.connect(callback)
        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.addWidget(btn)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        return contenedor

    def valor_a_texto(val, decimales=3):
        if val is None:
            return ""
        if isinstance(val, (float, int)):
            return f"{val:.{decimales}f}" if isinstance(val, float) else str(val)
        return str(val)

    for row_idx, row_data in enumerate(rows):
        id_prueba = row_data[9]
        mes_control = row_data[1]
        mes_control = mes_control.replace('/', '-')
        
        equipo = row_data[3]
        id_session = row_data[0]

        # Col 0: Fecha
        item = QTableWidgetItem(valor_a_texto(row_data[1], 0))
        item.setData(Qt.UserRole, id_session)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 0, item)

        # Col 1: Usuario
        item = QTableWidgetItem(valor_a_texto(row_data[2]))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 1, item)

        # Col 2: Equipo
        item = QTableWidgetItem(valor_a_texto(row_data[3]))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 2, item)

        # Col 3: kV
        item = QTableWidgetItem(valor_a_texto(row_data[4], 0))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 3, item)

        # Col 4: mA
        item = QTableWidgetItem(valor_a_texto(row_data[5], 0))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 4, item)

        # Col 5: Espesor Corte
        item = QTableWidgetItem(valor_a_texto(row_data[6], 2))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 5, item)

        # Col 6: Valores CT
        tableWidget.setCellWidget(row_idx, 6, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_valores_ct(parent, m)))

        # Col 7: Uniformidad Ruido
        tableWidget.setCellWidget(row_idx, 7, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_uniformidad_ruido(parent, m)))

        # Col 8: Uniformidad Global
        tableWidget.setCellWidget(row_idx, 8, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_uniformidad_global(parent, m)))

        # Col 9: Resolución Espacial
        tableWidget.setCellWidget(row_idx, 9, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_resolucion_espacial(parent, m)))

        # Col 10: Linealidad CT
        tableWidget.setCellWidget(row_idx, 10, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_linealidad_ct(parent, m)))

        # Col 11: Espesor Corte Análisis
        tableWidget.setCellWidget(row_idx, 11, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_espesor_corte_analisis(parent, m)))

        # Col 12: Tamaño Pixel
        tableWidget.setCellWidget(row_idx, 12, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_tamaño_pixel(parent, m)))

        # Col 13: Imagen
        valor_img = row_data[7]
        texto_imagen = "Imagen Cargada" if valor_img else ""
        item = QTableWidgetItem(texto_imagen)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        tableWidget.setItem(row_idx, 13, item)

        # Col 14: Resultado
        valor_resultado = row_data[8]
        texto_resultado = "Imagen Cargada" if valor_resultado else ""
        item = QTableWidgetItem(texto_resultado)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        tableWidget.setItem(row_idx, 14, item)
        
        # Col 15: reporte
        tableWidget.setCellWidget(row_idx, 15, crear_boton_tabla("Reporte", lambda _, m=mes_control, e=equipo ,s= id_session: _generar_reporte_desde_tabla(parent, m, equipo, s)))
        print("Equipo seleccionado para reporte ")
        print(equipo)
        
    def _generar_reporte_desde_tabla(parent, fecha, maquina, id_sesion):
        
        if parent is None:
            QMessageBox.warning(None, "Error", "No hay contexto disponible para generar el reporte.")
            return
        
        
       
        from models.PDF.Imagenes.reportes_control_sistema_imagenes import generar_reporte_sistema_imagenes
    
          # O el atributo que corresponda a tu usuario
        generar_reporte_sistema_imagenes(parent, fecha, maquina, usuario, id_sesion, sistema_imagenes=True)      
        
        
def mostrar_controles_imgHC(parent, tableWidget,usuario,equipo_filtrar=None):
    
    print("Entra a imagenes HC")
    conn = Conexion().conectar()
    
    cursor = conn.cursor()
    tableWidget.clearContents()
    tableWidget.setRowCount(0)
    tableWidget.setColumnCount(0)
    cursor.execute("""
    SELECT c.id, c.fecha, c.equipo, c.control, COUNT(p.id_prueba) as num_pruebas
    FROM controles c
    LEFT JOIN pruebas p ON p.id_sesion = c.id
    WHERE c.equipo = 'Halcyon' AND c.control = 'Mensual'
        AND (c.activo IS NULL OR c.activo = 1)
        GROUP BY c.id
    """)
    conn.commit()
    cursor.execute("PRAGMA table_info(pruebas)")
    columns = [col[1] for col in cursor.fetchall()]
    if "mes_control" not in columns:
        print("mes control")
        cursor.execute("ALTER TABLE pruebas ADD COLUMN mes_control TEXT")
        
    query_addmonth = """ 
                    UPDATE pruebas
                    SET mes_control = strftime('%Y-%m', created_at)
                    WHERE mes_control IS NULL    
                    """
    cursor.execute(query_addmonth)
    conn.commit()
    
    
    "-----------------------------------------------------------------------------------------------------------------"
    
    query = """
    SELECT 
    c.id as id_sesion,
    c.fecha as fecha,
    u.fullname,
    c.equipo,
    MAX(p.kv) as kv,
    MAX(p.ma) as ma,
    MAX(p.espesor_corte) as espesor_corte,
    MAX(p.imagen_path) as imagen_path,
    MAX(p.imagen_resultado) as imagen_resultado,
    MIN(p.id_prueba) as id_prueba
    FROM controles c
    LEFT JOIN pruebas p ON p.id_sesion = c.id
    LEFT JOIN users u ON c.user_id = u.fullname
    WHERE c.equipo = 'Halcyon'
    AND c.control = 'Mensual'
    AND (c.activo IS NULL OR c.activo = 1)
    GROUP BY c.id, c.equipo
    ORDER BY c.fecha DESC
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.commit()
    conn.close()

    headers = [ 
        ("Fecha", None),
        ("Usuario", None),
        ("Equipo", None),
        ("kV", None),
        ("mA", None),
        ("Espesor Corte", None),
        ("Valores CT", None),
        ("Uniformidad Ruido", None),
        ("Uniformidad Global", None),
        ("Resolución Espacial", None),
        ("Linealidad CT", None),
        ("Espesor Corte Análisis", None),
        ("Tamaño Pixel", None),
        ("Imagen", None),
        ("Resultado", None),
        ("Reporte", None),
    ]

    tableWidget.setColumnCount(len(headers))
    tableWidget.setRowCount(len(rows))

    for i, (texto, meta) in enumerate(headers):
        header_item = QTableWidgetItem(texto)
        header_item.setData(Qt.UserRole, meta)
        tableWidget.setHorizontalHeaderItem(i, header_item)

    def crear_boton_tabla(texto, callback):
        btn = QPushButton(texto)
        btn.setFixedWidth(80)
        btn.setStyleSheet("background-color: rgb(255, 186, 186); color: black;")
        btn.clicked.connect(callback)
        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.addWidget(btn)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        return contenedor

    def valor_a_texto(val, decimales=3):
        if val is None:
            return ""
        if isinstance(val, (float, int)):
            return f"{val:.{decimales}f}" if isinstance(val, float) else str(val)
        return str(val)

    for row_idx, row_data in enumerate(rows):
        id_prueba = row_data[9]
        mes_control = row_data[1]
        mes_control = row_data[1].replace('/', '-')          # "04-2026" para queries... pero aun así el orden es mes/año
        # convierte a año-mes para que coincida con mes_control en pruebas
        partes = row_data[1].split('/')                      
        mes_control = f"{partes[1]}-{partes[0]}" if len(partes) == 2 else row_data[1]  # "2026-04"
        equipo = row_data[3]
        id_session = row_data[0]
 
        # Col 0: Fecha
        item = QTableWidgetItem(valor_a_texto(row_data[1], 0))
        item.setData(Qt.UserRole, id_session)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 0, item)

        # Col 1: Usuario
        item = QTableWidgetItem(valor_a_texto(row_data[2]))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 1, item)

        # Col 2: Equipo
        item = QTableWidgetItem(valor_a_texto(row_data[3]))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 2, item)

        # Col 3: kV
        item = QTableWidgetItem(valor_a_texto(row_data[4], 0))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 3, item)

        # Col 4: mA
        item = QTableWidgetItem(valor_a_texto(row_data[5], 0))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 4, item)

        # Col 5: Espesor Corte
        item = QTableWidgetItem(valor_a_texto(row_data[6], 2))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 5, item)

        # Col 6: Valores CT
        tableWidget.setCellWidget(row_idx, 6, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_valores_ct(parent, m)))

        # Col 7: Uniformidad Ruido
        tableWidget.setCellWidget(row_idx, 7, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_uniformidad_ruido(parent, m)))

        # Col 8: Uniformidad Global
        tableWidget.setCellWidget(row_idx, 8, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_uniformidad_global(parent, m)))

        # Col 9: Resolución Espacial
        tableWidget.setCellWidget(row_idx, 9, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_resolucion_espacial(parent, m)))

        # Col 10: Linealidad CT
        tableWidget.setCellWidget(row_idx, 10, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_linealidad_ct(parent, m)))

        # Col 11: Espesor Corte Análisis
        tableWidget.setCellWidget(row_idx, 11, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_espesor_corte_analisis(parent, m)))

        # Col 12: Tamaño Pixel
        tableWidget.setCellWidget(row_idx, 12, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_tamaño_pixel(parent, m)))

        # Col 13: Imagen
        valor_img = row_data[7]
        texto_imagen = "Imagen Cargada" if valor_img else ""
        item = QTableWidgetItem(texto_imagen)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        tableWidget.setItem(row_idx, 13, item)

        # Col 14: Resultado
        valor_resultado = row_data[8]
        texto_resultado = "Imagen Cargada" if valor_resultado else ""
        item = QTableWidgetItem(texto_resultado)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        tableWidget.setItem(row_idx, 14, item)
        
        # Col 15: reporte
        tableWidget.setCellWidget(row_idx, 15, crear_boton_tabla("Reporte", lambda _, m=mes_control, e=equipo ,s= id_session: _generar_reporte_desde_tabla(parent, m, equipo, s)))
        print("Equipo seleccionado para reporte ")
        print(equipo)
        
    def _generar_reporte_desde_tabla(parent, fecha, maquina, id_sesion):
        if parent is None:
            QMessageBox.warning(None, "Error", "No hay contexto disponible para generar el reporte.")
            return
        
        
       
        from models.PDF.Imagenes.reportes_control_sistema_imagenes import generar_reporte_sistema_imagenes
    
          # O el atributo que corresponda a tu usuario
        generar_reporte_sistema_imagenes(parent, fecha, maquina, usuario, id_sesion, sistema_imagenes=True)
              
def mostrar_controles_tac(parent, tableWidget,usuario,equipo_filtrar=None):
    conn = Conexion().conectar()
    cursor = conn.cursor()
    tableWidget.clearContents()
    tableWidget.setRowCount(0)
    tableWidget.setColumnCount(0)
    cursor.execute("""
    SELECT c.id, c.fecha, c.equipo, c.control, COUNT(p.id_prueba) as num_pruebas
    FROM controles c
    LEFT JOIN pruebas p ON p.id_sesion = c.id
    WHERE c.equipo = 'Tomógrafo' AND c.control = 'Mensual'
        AND (c.activo IS NULL OR c.activo = 1)
        GROUP BY c.id
    """)
    conn.commit()
    cursor.execute("PRAGMA table_info(pruebas)")
    columns = [col[1] for col in cursor.fetchall()]
    if "mes_control" not in columns:
        print("mes control")
        cursor.execute("ALTER TABLE pruebas ADD COLUMN mes_control TEXT")
        
    query_addmonth = """ 
                    UPDATE pruebas
                    SET mes_control = strftime('%Y-%m', created_at)
                    WHERE mes_control IS NULL    
                    """
    cursor.execute(query_addmonth)
    conn.commit()
    
    
    "-----------------------------------------------------------------------------------------------------------------"
    
    query = """
    SELECT 
    c.id as id_sesion,
    c.fecha as fecha,
    u.fullname,
    c.equipo,
    MAX(p.kv) as kv,
    MAX(p.ma) as ma,
    MAX(p.espesor_corte) as espesor_corte,
    MAX(p.imagen_path) as imagen_path,
    MAX(p.imagen_resultado) as imagen_resultado,
    MIN(p.id_prueba) as id_prueba
    FROM controles c
    LEFT JOIN pruebas p ON p.id_sesion = c.id
    LEFT JOIN users u ON c.user_id = u.fullname
    WHERE c.equipo = 'Tomógrafo'
    AND c.control = 'Mensual'
    AND (c.activo IS NULL OR c.activo = 1)
    GROUP BY c.id, c.equipo
    ORDER BY c.fecha DESC
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.commit()
    conn.close()

    headers = [ 
        ("Fecha", None),
        ("Usuario", None),
        ("Equipo", None),
        ("kV", None),
        ("mA", None),
        ("Espesor Corte", None),
        ("Valores CT", None),
        ("Uniformidad Ruido", None),
        ("Uniformidad Global", None),
        ("Resolución Espacial", None),
        ("Linealidad CT", None),
        ("Espesor Corte Análisis", None),
        ("Tamaño Pixel", None),
        ("Imagen", None),
        ("Resultado", None),
        ("Reporte", None),
    ]

    tableWidget.setColumnCount(len(headers))
    tableWidget.setRowCount(len(rows))

    for i, (texto, meta) in enumerate(headers):
        header_item = QTableWidgetItem(texto)
        header_item.setData(Qt.UserRole, meta)
        tableWidget.setHorizontalHeaderItem(i, header_item)

    def crear_boton_tabla(texto, callback):
        btn = QPushButton(texto)
        btn.setFixedWidth(80)
        btn.setStyleSheet("background-color: rgb(255, 186, 186); color: black;")
        btn.clicked.connect(callback)
        contenedor = QWidget()
        layout = QHBoxLayout(contenedor)
        layout.addWidget(btn)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        return contenedor

    def valor_a_texto(val, decimales=3):
        if val is None:
            return ""
        if isinstance(val, (float, int)):
            return f"{val:.{decimales}f}" if isinstance(val, float) else str(val)
        return str(val)

    for row_idx, row_data in enumerate(rows):
        id_prueba = row_data[9]
        mes_control = row_data[1]
        mes_control = row_data[1].replace('/', '-')          # "04-2026" para queries... pero aun así el orden es mes/año
        # convierte a año-mes para que coincida con mes_control en pruebas
        partes = row_data[1].split('/')                      
        mes_control = f"{partes[1]}-{partes[0]}" if len(partes) == 2 else row_data[1]  # "2026-04"
        equipo = row_data[3]
        id_session = row_data[0]

        # Col 0: Fecha
        item = QTableWidgetItem(valor_a_texto(row_data[1], 0))
        item.setData(Qt.UserRole, id_session)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 0, item)

        # Col 1: Usuario
        item = QTableWidgetItem(valor_a_texto(row_data[2]))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 1, item)

        # Col 2: Equipo
        item = QTableWidgetItem(valor_a_texto(row_data[3]))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 2, item)

        # Col 3: kV
        item = QTableWidgetItem(valor_a_texto(row_data[4], 0))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 3, item)

        # Col 4: mA
        item = QTableWidgetItem(valor_a_texto(row_data[5], 0))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 4, item)

        # Col 5: Espesor Corte
        item = QTableWidgetItem(valor_a_texto(row_data[6], 2))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        tableWidget.setItem(row_idx, 5, item)

        # Col 6: Valores CT
        tableWidget.setCellWidget(row_idx, 6, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_valores_ct(parent, m)))

        # Col 7: Uniformidad Ruido
        tableWidget.setCellWidget(row_idx, 7, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_uniformidad_ruido(parent, m)))

        # Col 8: Uniformidad Global
        tableWidget.setCellWidget(row_idx, 8, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_uniformidad_global(parent, m)))

        # Col 9: Resolución Espacial
        tableWidget.setCellWidget(row_idx, 9, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_resolucion_espacial(parent, m)))

        # Col 10: Linealidad CT
        tableWidget.setCellWidget(row_idx, 10, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_linealidad_ct(parent, m)))

        # Col 11: Espesor Corte Análisis
        tableWidget.setCellWidget(row_idx, 11, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_espesor_corte_analisis(parent, m)))

        # Col 12: Tamaño Pixel
        tableWidget.setCellWidget(row_idx, 12, crear_boton_tabla("Ver tabla", lambda _, m=id_session: mostrar_tamaño_pixel(parent, m)))

        # Col 13: Imagen
        valor_img = row_data[7]
        texto_imagen = "Imagen Cargada" if valor_img else ""
        item = QTableWidgetItem(texto_imagen)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        tableWidget.setItem(row_idx, 13, item)

        # Col 14: Resultado
        valor_resultado = row_data[8]
        texto_resultado = "Imagen Cargada" if valor_resultado else ""
        item = QTableWidgetItem(texto_resultado)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)
        tableWidget.setItem(row_idx, 14, item)
        
        # Col 15: reporte
        tableWidget.setCellWidget(row_idx, 15, crear_boton_tabla("Reporte", lambda _, m=mes_control, e=equipo ,s= id_session: _generar_reporte_desde_tabla(parent, m, equipo, s)))
        print("Equipo seleccionado para reporte ")
        print(equipo)
        
    def _generar_reporte_desde_tabla(parent, fecha, maquina, id_sesion):
        if parent is None:
            QMessageBox.warning(None, "Error", "No hay contexto disponible para generar el reporte.")
            return
        
        
       
        from models.PDF.Imagenes.reportes_control_sistema_imagenes import generar_reporte_sistema_imagenes
    
          # O el atributo que corresponda a tu usuario
        generar_reporte_sistema_imagenes(parent, fecha, maquina, usuario, id_sesion, sistema_imagenes=True)
def _mostrar_tabla_generica(parent, mes_control, config):

    dialog = QDialog(parent)
    dialog.setWindowTitle(config['titulo'])
    dialog.setModal(True)
    dialog.resize(800, 600)
    print(mes_control)
    layout = QVBoxLayout(dialog)

    lbl_info = QLabel(f"{config['titulo']} para la sesión: {mes_control}")
    lbl_info.setStyleSheet("font-weight: bold; margin: 10px;")
    layout.addWidget(lbl_info)

    table = QTableWidget()

    conn = Conexion().conectar()
    cursor = conn.cursor()

    col_names = ', '.join([col[1] for col in config['columnas']])
    col_names = ', '.join([f"t.{col[1]}" for col in config['columnas']])
    query = f"""
    SELECT {col_names}
    FROM {config['tabla']} t
    JOIN pruebas p ON t.id_prueba = p.id_prueba
    WHERE p.id_sesion = ?
    """

    cursor.execute(query, (mes_control,))
    result = cursor.fetchall()

    conn.close()

    if result and len(result) > 0:

        headers = [col[0] for col in config['columnas']]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(result))

        for i, row in enumerate(result):
            for j, value in enumerate(row):
                item = QTableWidgetItem(str(value) if value is not None else "")
                table.setItem(i, j, item)

        table.resizeColumnsToContents()
        layout.addWidget(table)

    else:
        lbl_no_data = QLabel(config['mensaje_vacio'])
        lbl_no_data.setStyleSheet("color: orange; font-size: 12px; padding: 20px;")
        layout.addWidget(lbl_no_data)

    btn_cerrar = QPushButton("Cerrar")
    btn_cerrar.clicked.connect(dialog.accept)
    layout.addWidget(btn_cerrar)

    dialog.exec_()

def mostrar_valores_ct(parent, id_control):
    config = {
        'titulo': 'Valores CT',
        'tabla': 'valores_ct',
        'columnas': [
            ('ID Prueba', 'id_prueba'),
            ('ID Material', 'id_material'),
            ('Promedio HU', 'promedio_hu'),
            ('Error Absoluto', 'error_absoluto'),
            ('Error Relativo', 'error_relativo')
        ],
        'mensaje_vacio': '⚠️ No se encontraron datos de Valores CT para este control'
    }
    _mostrar_tabla_generica(parent, id_control, config)


def mostrar_uniformidad_ruido(parent, id_control):
    config = {
        'titulo': 'Uniformidad y Ruido',
        'tabla': 'uniformidad_ruido',
        'columnas': [
            ('ID Prueba', 'id_prueba'),
            ('ID Región', 'id_region'),
            ('HU Promedio', 'hu_promedio'),  # ⚠️ TYPO en tu BD: debería ser "hu_promedio"
            ('Desviación', 'desviacion')
        ],
        'mensaje_vacio': '⚠️ No se encontraron datos de Uniformidad y Ruido para este control'
    }
    _mostrar_tabla_generica(parent, id_control, config)


def mostrar_uniformidad_global(parent, id_control):
    config = {
        'titulo': 'Uniformidad Global',
        'tabla': 'uniformidad_global',
        'columnas': [
            ('ID Prueba', 'id_prueba'),
            ('Max Diferencia', 'max_diferencia'),
            ('Desviación Global', 'desviacion_global'),
            ('UI Max', 'uniformity_index_max'),
            ('UI ROI', 'uniformity_index_roi'),
            ('INU', 'integral_non_uniformity'),
            ('INU %', 'integral_non_uniformity_pct'),
            ('Pasa UI', 'pasa_ui'),
            ('Pasa INU', 'pasa_inu'),
            ('Pasa Global', 'pasa_global'),
            ('UI Threshold %', 'ui_threshold_pct'),
            ('INU Threshold %', 'inu_threshold_pct'),
            ('HU Tolerancia', 'hu_tolerancia')
        ],
        'mensaje_vacio': '⚠️ No se encontraron datos de Uniformidad Global para este control'
    }
    _mostrar_tabla_generica(parent, id_control, config)


def mostrar_resolucion_espacial(parent, id_control):
    config = {
        'titulo': 'Resolución Espacial',
        'tabla': 'resolucion_espacial',
        'columnas': [
            ('ID Prueba', 'id_prueba'),
            ('Regiones Analizadas', 'regiones_analizadas'),
            ('Regiones Exitosas', 'regiones_exitosas'),
            ('LP/mm Máximo', 'lp_mm_maximo'),
            ('Última Región Exitosa', 'ultima_region_exitosa'),
            ('Gap Size Mínimo (cm)', 'gap_size_minimo_cm'),
            ('Nº Picos Totales', 'num_picos_totales'),
            ('MTF 10%', 'mtf_10_pct'),
            ('MTF 20%', 'mtf_20_pct'),
            ('MTF 50%', 'mtf_50_pct')
        ],
        'mensaje_vacio': '⚠️ No se encontraron datos de Resolución Espacial para este control'
    }
    _mostrar_tabla_generica(parent, id_control, config)


def mostrar_linealidad_ct(parent, id_control):
    config = {
        'titulo': 'Linealidad CT',
        'tabla': 'linealidad_ct',
        'columnas': [
            ('ID Prueba', 'id_prueba'),
            ('Pendiente', 'pendiente'),
            ('Intercepto', 'intercepto'),
            ('R²', 'r_cuadrado'),
            ('Referencia', 'referencia'),
            ('Escala Contraste', 'escala_contraste'),
            ('Nº Materiales', 'num_materiales'),
            ('Rango HU Min', 'rango_hu_min'),
            ('Rango HU Max', 'rango_hu_max')
        ],
        'mensaje_vacio': '⚠️ No se encontraron datos de Linealidad CT para este control'
    }
    _mostrar_tabla_generica(parent, id_control, config)


def mostrar_espesor_corte_analisis(parent, id_control):
    config = {
        'titulo': 'Espesor de Corte',
        'tabla': 'espesor_corte',
        'columnas': [
            ('ID Prueba', 'id_prueba'),
            ('Espesor Promedio (mm)', 'espesor_promedio_mm'),
            ('Espesor Teórico (mm)', 'espesor_teorico_mm'),
            ('Diferencia (mm)', 'diferencia_mm'),
            ('Error (%)', 'error_pct')  # ⚠️ TYPO en tu BD: debería ser "error_pct"
        ],
        'mensaje_vacio': '⚠️ No se encontraron datos de Espesor de Corte para este control'
    }
    _mostrar_tabla_generica(parent, id_control, config)


def mostrar_tamaño_pixel(parent, id_control):
    config = {
        'titulo': 'Tamaño de Pixel',
        'tabla': 'tamaño_pixel',
        'columnas': [
            ('ID Prueba', 'id_prueba'),
            ('Valor Teórico DICOM', 'valor_teorico_dicom'),
            ('X', 'X'),
            ('Y', 'Y'),
            ('Diferencia X', 'diferencia_x'),
            ('Diferencia Y', 'diferencia_y'),
            ('Error (%)', 'error_pct')
        ],
        'mensaje_vacio': '⚠️ No se encontraron datos de Tamaño de Pixel para este control'
    }
    _mostrar_tabla_generica(parent, id_control, config)






" ---------------------------------- Funciones para mostrar tablas emergentes ------------------------------------ "
def mostrar_equipos(parent, id_ref):
    conn = Conexion().conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, equip_type, model, serie, calibr_fact, fecha_calibr
        FROM equipos_medicion WHERE ref=? AND (activo IS NULL OR activo = 1)
    """, (id_ref,))
    data = cursor.fetchall()

    # Lista de tuplas, cada tupla corresponde al titulo del campo en la base de datos y el titulo bonito pata la tabla
    headers = [("id", "ID"), ("equip_type", "Equipo"), ("model", "Modelo"), ("serie", "Serie"), ("calibr_fact", "Factor Cal."), 
                ("fecha_calibr", "Fecha. Cal")]
    conn.close()
    _mostrar_dialogo(parent, headers, data, 650, 250, "equipos_medicion", id_ref)

def mostrar_seguridad(parent, id_ref, ix=False):
    conn = Conexion().conectar()
    cursor = conn.cursor()

    def cargar_datos(tabla, columnas, id_ref):
        cols = ", ".join(columnas)
        # M1 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md): el filtro de
        # `activo` ya no está codificado contra "control_cunas" -- se aplica
        # a cualquier tabla de la lista blanca de anulación
        # (services/anulacion.py::TABLAS_ANULABLES), para que la próxima
        # tabla que entre a esa lista no repita el olvido.
        filtro_activo = " AND (activo IS NULL OR activo = 1)" if tabla in TABLAS_ANULABLES else ""
        cursor.execute(f"""SELECT {cols} FROM {tabla} WHERE ref=?{filtro_activo}""", (id_ref,))
        return cursor.fetchall()

    # Datos de cunas y conos
    cunas = cargar_datos( "control_cunas", ["angulo", "in_val", "out_val", "right_val", "left_val", "observaciones"], id_ref)
    conos = cargar_datos( "control_conos", ["medida", "valor"], id_ref)
    conn.close()

    # Función para convertir 0/1 en botones
    def transformar_filas(datos):
        filas_transformadas = []
        for fila in datos:
            nueva_fila = []
            for valor in fila:
                if valor in (0, 1):  # 0/1 -> botón
                    btn = QPushButton("Funciona" if valor == 1 else "No Funciona")
                    if valor == 1:
                        btn.setObjectName("boton_funciona") 
                    else:
                        btn.setObjectName("boton_nofunciona") 
                    btn.setEnabled(False)
                    nueva_fila.append(btn)
                else:
                    nueva_fila.append(valor)
            filas_transformadas.append(nueva_fila)
        return filas_transformadas

    cunas_transformadas = transformar_filas(cunas)
    conos_transformados = transformar_filas(conos)

    headers_cunas = [("angulo", "Ángulo (°)"), ("in_val", "In"), ("out_val", "Out"), ("right_val", "Right"), ("left_val", "Left"), 
                    ("observaciones", "Obs.")]

    headers_conos = [("medida", "Medida"), ("valor", "Valor")]

    # Pestañas para mostrar conos y cuñas
    if ix:
        dlg = QDialog(parent)
        dlg.setWindowTitle("Seguridad")
        if getattr(sys, 'frozen', False):
            # Ruta dentro del .exe
            base_path = Path(sys._MEIPASS)
        else:
            # Ruta normal cuando se ejecuta con Python
            base_path = Path(__file__).parent.parent.parent

        qss_file = base_path / "resources" / "estilo.qss"
        dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))

        layout = QVBoxLayout(dlg)
        tabs = QTabWidget()

        def crear_tab(headers, data):
            table = QTableWidget()
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels([alias for _, alias in headers])
            table.setRowCount(len(data))

            for row_idx, row_data in enumerate(data):
                for col_idx, value in enumerate(row_data):
                    if isinstance(value, QPushButton):
                        table.setCellWidget(row_idx, col_idx, value)
                    else:
                        item = QTableWidgetItem(str(value))
                        item.setTextAlignment(Qt.AlignCenter)
                        table.setItem(row_idx, col_idx, item)        
            return table

        tabs.addTab(crear_tab(headers_cunas, cunas_transformadas), "Cunas")
#        tabs.setSpan(0, -1, -1, -1) # Span desde la fila 0, última columna, hasta la última fila
        tabs.addTab(crear_tab(headers_conos, conos_transformados), "Conos")

        layout.addWidget(tabs)
        dlg.resize(1000, 400)
        dlg.exec_()
        return

    _mostrar_dialogo(parent, headers=headers_cunas, data=cunas_transformadas, w=750, h=300, tabla_db = "control_cunas", id_ref = id_ref)

def mostrar_indc_angulares(parent, id_ref):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Información indicadores angulares")
    layout = QVBoxLayout(dlg)

    conn = Conexion().conectar()
    cursor = conn.cursor()

    def cargar_datos(tabla):
        cursor.execute(f"""
            SELECT nivel, indicador_luminoso_consola, indicador_luminoso_equipo
            FROM {tabla}
            WHERE ref=?
        """, (id_ref,))
        datos = cursor.fetchall()

        datos_limpios = {}
        for nivel, cons, equi in datos:
            try:
                nivel_int = int(str(nivel).replace("°", "").strip())
            except:
                continue
            datos_limpios[nivel_int] = (cons, equi)

        return [datos_limpios.get(n, ("", "")) for n in [0, 90, 180, 270]]
    

    datos_brazo = cargar_datos("indicadores_brazo")
    datos_colimador = cargar_datos("indicadores_angulares_colimador")
    conn.close()

    table = QTableWidget()
    table.setColumnCount(4)
    table.setRowCount(8)
    table.setHorizontalHeaderLabels(["", "Nivel", "Ind. Luminoso Cons.", "Ind. Luminoso Equi."])

    niveles = ["0", "90", "180", "270"]
    niveles_colimador = ["0","90", "180" ,"270"]
    
    # Brazo
    table.setSpan(0, 0, 4, 1)
    table.setItem(0, 0, QTableWidgetItem("Brazo"))
    for i, nivel in enumerate(niveles):
        
        table.setItem(i, 1, QTableWidgetItem(nivel))
        table.setItem(i, 2, QTableWidgetItem(str(datos_brazo[i][0])))
        table.setItem(i, 3, QTableWidgetItem(str(datos_brazo[i][1])))

    # Colimador
    table.setSpan(4, 0, 4, 1)
    table.setItem(4, 0, QTableWidgetItem("Colimador"))
    for i, nivel in enumerate(niveles_colimador):
        row = 4 + i
        table.setItem(row, 1, QTableWidgetItem(nivel))
        table.setItem(row, 2, QTableWidgetItem(str(datos_colimador[i][0])))
        table.setItem(row, 3, QTableWidgetItem(str(datos_colimador[i][1])))

    # Ajustar ancho según headers
    font_metrics = table.fontMetrics()
    for col in range(table.columnCount()):
        header_text = table.horizontalHeaderItem(col).text()
        text_width = font_metrics.horizontalAdvance(header_text)
        table.setColumnWidth(col, text_width + 80)

    layout.addWidget(table)
    dlg.resize(650, 415)
    if getattr(sys, 'frozen', False):
        # Ruta dentro del .exe
        base_path = Path(sys._MEIPASS)
    else:
        # Ruta normal cuando se ejecuta con Python
        base_path = Path(__file__).parent.parent.parent

    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))
    dlg.exec_()

def mostrar_tam_campos(parent, id_ref):
    conn = Conexion().conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT campo_nominal, ie_largoy1, ie_largoy2, ie_anchox1, ie_anchox2,
            ic_largoy1, ic_largoy2, ic_anchox1, ic_anchox2
        FROM tamano_campo WHERE ref=? AND (activo IS NULL OR activo = 1)
    """, (id_ref,))
    data = cursor.fetchall()

    headers =  [("campo_nominal", "Campo nominal"), ("ie_largoy1", "Eq Largo Y1"), ("ie_largoy2", "Eq Largo Y2"),
                ("ie_anchox1", "Eq Ancho X1"), ("ie_anchox2", "Eq Ancho X2"), ("ic_largoy1", "Cons Largo Y1"), ("ic_largoy2", "Cons Largo Y2"),
                ("ic_anchox1", "Cons Ancho X1"), ("ic_anchox2", "Cons Ancho X2")]
    conn.close()
    _mostrar_dialogo(parent, headers, data, 1400, 250,"tamano_campo", id_ref)

def mostrar_analisis_img(parent, id_ref):
    conn = Conexion().conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT caracteristica, franja1, franja2, franja3
        FROM analisis_placa_franjas WHERE ref=? AND (activo IS NULL OR activo = 1)
    """, (id_ref,))
    data = cursor.fetchall()
    conn.close()

    # Convertimos la lista de strings a lista de tuplas (db_name, alias)
    headers = [(h, h) for h in ["Característica", "Franja 1", "Franja 2", "Franja 3"]]

    _mostrar_dialogo(parent, headers, data, 1000, 1000, "analisis_placa_franjas", id_ref)

def mostrar_dosimetria(parent, id_ref):
    # A6.2-bis: este diálogo permite editar (guardarEdicion más abajo) -- sin
    # la identidad, esa edición se auditaba con `usuario` NULL.
    dlg = _dialogo_con_identidad(QDialog(parent), parent)
    dlg.setWindowTitle("Dosimetría Mensual")
    grid_layout = QGridLayout(dlg)

    conn = Conexion().conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            energia,
            dosis_ref_cgy_um, discrepancia_dosis, tolerancia_dosis,
            calidad_pdd20_10, discrepancia_calidad, tolerancia_calidad,
            simetria_inplane, simetria_crossplane, tolerancia_simetria,
            planicidad_inplane, planicidad_crossplane, tolerancia_planicidad, observaciones_dosi
        FROM dosimetriaMen
        WHERE ref = ? AND (activo IS NULL OR activo = 1)
        ORDER BY energia
    """, (id_ref,))
    resultados = cursor.fetchall()
    conn.close()

    if not resultados:
        print("No hay datos para esta referencia.")
        return

    # Diccionario de mapeo (desc → col BD por cada col visual)
    mapa_columnas = {
        "Dosis Ref (cGy/UM)": {1: "dosis_ref_cgy_um", 2: "discrepancia_dosis", 3: "tolerancia_dosis"},
        "Calidad (PDD20/10)": {1: "calidad_pdd20_10", 2: "discrepancia_calidad", 3: "tolerancia_calidad"},
        "Simetría (%) - Inplane": {1: "simetria_inplane", 3: "tolerancia_simetria"},
        "Simetría (%) - Crossplane": {1: "simetria_crossplane", 3: "tolerancia_simetria"},
        "Planicidad (%) - Inplane": {1: "planicidad_inplane", 3: "tolerancia_planicidad"},
        "Planicidad (%) - Crossplane": {1: "planicidad_crossplane", 3: "tolerancia_planicidad"},
        "Observaciones dosimetría": {1: "" , 3: "observaciones_dosi"},
    }

    max_cols = 4
    for idx, res in enumerate(resultados):
        energia = res[0]
        dosis_ref, disc_dosis, tol_dosis = res[1], res[2], res[3]
        calidad, disc_calidad, tol_calidad = res[4], res[5], res[6]
        sim_in, sim_cross, tol_sim = res[7], res[8], res[9]
        plan_in, plan_cross, tol_plan = res[10], res[11], res[12]
        observaciones = res[-1]

        filas = [
            ["Energía Nominal (MV)", energia, "", ""],
            ["Dosis Ref (cGy/UM)", dosis_ref, disc_dosis, tol_dosis],
            ["Calidad (PDD20/10)", calidad, disc_calidad, tol_calidad],
            ["Simetría (%) - Inplane", sim_in, "", tol_sim],
            ["Simetría (%) - Crossplane", sim_cross, "", tol_sim],
            ["Planicidad (%) - Inplane", plan_in, "", tol_plan],
            ["Planicidad (%) - Crossplane", plan_cross, "", tol_plan],
            ["Observaciones","x", "x" ,observaciones]
        ]

        table = QTableWidget()
        table.setColumnCount(4)
        table.setRowCount(len(filas))
        table.setHorizontalHeaderLabels([
            "                          ", "Valor Correspondiente", "Discrepancia (%)", "Tolerancia (%)"
        ])

        for row, (desc, val, disc, tol) in enumerate(filas):
            item_desc = QTableWidgetItem(str(desc))
            item_val = QTableWidgetItem(str(val))
            item_disc = QTableWidgetItem("" if disc == "" else str(disc))
            item_tol = QTableWidgetItem(str(tol))
            #item_obs = QTableWidgetItem(obs)

            for item in [item_desc, item_val, item_disc, item_tol]:
                item.setTextAlignment(Qt.AlignCenter)

            table.setItem(row, 0, item_desc)
            table.setItem(row, 1, item_val)
            table.setItem(row, 2, item_disc)
            table.setItem(row, 3, item_tol)
            #table.setItem(row, 4, item_obs)

            # G5 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md §5-a): identidad
            # (id_ref, energia) en TODAS las celdas de la fila, no solo las
            # editables -- "Energía Nominal" y "Observaciones" identifican
            # el mismo registro (ref, energia) que las demás filas, aunque
            # no tengan columna editable (no están en mapa_columnas). Antes
            # se quedaban sin ningún Qt.UserRole y eliminarRegistro no
            # encontraba metadata al seleccionarlas ("No se encontró
            # metadata (id/ref) en la fila seleccionada"). UserRole+1
            # (tabla+columna, que consume guardarEdicion) se sigue poniendo
            # SOLO en las editables -- la edición no cambia de comportamiento.
            for col in (0, 1, 2, 3):
                table.item(row, col).setData(Qt.UserRole, (id_ref, energia))

            if desc in mapa_columnas:
                for col in (1, 2, 3):  # columnas editables
                    col_name = mapa_columnas[desc].get(col)
                    if col_name:
                        # Guardar tabla y columna en UserRole+1
                        table.item(row, col).setData(
                            Qt.UserRole + 1, ("dosimetriaMen", col_name))

        # Ajuste de ancho de columnas
        font_metrics = table.fontMetrics()
        for col in range(table.columnCount()):
            header_text = table.horizontalHeaderItem(col).text()
            table.setColumnWidth(col, font_metrics.horizontalAdvance(header_text) + 70)

        # G5 (§5-a, hallazgo adicional durante la ejecución): Editar/
        # Aceptar/Eliminar se conectan UNA sola vez, DESPUÉS de este bucle
        # -- sin este seguimiento, sus lambdas cerraban sobre `table` (la
        # variable del bucle, capturada por REFERENCIA) y siempre operaban
        # sobre la ÚLTIMA energía creada (la que ordena última
        # alfabéticamente), sin importar en cuál tabla el físico seleccionó
        # la fila. Verificado contra producción real: 5 refs (16, 13, 30,
        # 35, y el ref 1 de prueba) tienen 6 energías simultáneas -- el
        # defecto era alcanzable, no hipotético. `t=table` congela el valor
        # de ESTA iteración como argumento por defecto (idiom estándar
        # contra el late binding de closures en un bucle); la primera
        # tabla queda activa por defecto para que "Eliminar" sin haber
        # seleccionado nada dé el aviso correcto ("elija una fila") en vez
        # de operar a ciegas sobre una tabla ajena.
        table.itemSelectionChanged.connect(
            lambda t=table: setattr(dlg, '_tabla_dosimetria_activa', t))
        if idx == 0:
            dlg._tabla_dosimetria_activa = table

        row_grid = idx // max_cols
        col_grid = idx % max_cols
        grid_layout.addWidget(table, row_grid, col_grid)

    # ------------------ Botones ------------------
    dlg.btn_delete = QPushButton('Eliminar')    
    dlg.edit_table = QPushButton('Editar')
    dlg.accept_edit = QPushButton('Aceptar')
    dlg.accept_edit.hide()
    dlg.cancel_edit = QPushButton('Cancelar')
    dlg.cancel_edit.hide()

    edit_table_tools = QHBoxLayout()
    edit_table_tools.addWidget(dlg.btn_delete)
    edit_table_tools.addWidget(dlg.edit_table)
    edit_table_tools.addWidget(dlg.accept_edit)
    edit_table_tools.addWidget(dlg.cancel_edit)

    row_grid = (len(resultados) // max_cols) + 1  # fila después de las tablas
    grid_layout.addLayout(edit_table_tools, row_grid, 0, 1, max_cols)

    # ------------------ Conexiones ------------------
    # G5: leen dlg._tabla_dosimetria_activa (actualizada por
    # itemSelectionChanged en cada tabla, ver el bucle arriba) en vez de
    # cerrar sobre `table` -- esa variable, tras el bucle, quedaría fija en
    # la última tabla creada.
    dlg.edit_table.clicked.connect(
        lambda: verificar_editar(dlg, dlg._tabla_dosimetria_activa, "dosimetriaMen", "ref", id_ref)
    )
    dlg.accept_edit.clicked.connect(
        lambda: guardarEdicion(dlg, dlg._tabla_dosimetria_activa, "dosimetriaMen", id_ref)
    )
    dlg.cancel_edit.clicked.connect(
        lambda: cancelarEdicion(dlg)
    )
    # E5 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §6, D3/D5): el botón se
    # creaba (arriba) y se agregaba al layout, pero nunca se conectaba --
    # un botón visible que no hacía nada. Se conecta DESPUÉS de E7 a
    # propósito: "dosimetriaMen" ya está en
    # services.anulacion.TABLAS_ANULABLES, así que verificar_eliminar (vía
    # eliminarRegistro) anula (activo=0) en vez de borrar -- conectarlo
    # antes de E7 habría creado un DELETE físico sobre el bloque de
    # dosimetría, justo lo que D5 prohibió. `dlg` ya lleva identidad desde
    # A6.2-bis, así que queda auditado con el nombre del físico sin trabajo
    # extra.
    dlg.btn_delete.clicked.connect(
        lambda: verificar_eliminar(dlg, dlg._tabla_dosimetria_activa, "dosimetriaMen", id_ref)
    )

    dlg.resize(1200, 700)
    if getattr(sys, 'frozen', False):
        # Ruta dentro del .exe
        base_path = Path(sys._MEIPASS)
    else:
        # Ruta normal cuando se ejecuta con Python
        base_path = Path(__file__).parent.parent.parent

    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))
    dlg.exec_()
    
    
"--------------------------------------TABLAS DEL HALYCION---------------------------------------------------------------------------------" 

def mostrar_tam_campos_HC(parent, id_ref):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Información desplazamiento del isocentro")
    layout = QVBoxLayout(dlg)

    conn = Conexion().conectar()
    cursor = conn.cursor()

    def cargar_datos(tabla):
        cursor.execute(f"""
            SELECT indicado_inplane, indicado_crossplane, medido_inplane, medido_crossplane
            FROM {tabla}
            WHERE ref=?
        """, (id_ref,))
        datos = cursor.fetchall()

       

        return datos

    datos_brazo = cargar_datos("HC_tamanos_campo_radiacion")
    conn.close()

    table = QTableWidget()
    table.setColumnCount(5)
    table.setRowCount(3)
    table.setHorizontalHeaderLabels(["", "Indicado - Inplane (cm)", "Indicado - Crossplane (cm)", "Medido - Inplane (cm)", "Medido - Crossplane (cm)"])

    niveles = ["5", "10", "20"]

    # Brazo
    table.setSpan(0, 0, 5, 1)
    table.setItem(0, 0, QTableWidgetItem("Tamaño campos"))
    for i, nivel in enumerate(niveles):
        ind_in, ind_cross, med_in, med_cross = datos_brazo[i]
        table.setItem(i, 1, QTableWidgetItem(nivel))
        table.setItem(i, 2, QTableWidgetItem(str(ind_in)))
        table.setItem(i, 3, QTableWidgetItem(str(ind_cross)))
        table.setItem(i, 4, QTableWidgetItem(str(med_in)))
        table.setItem(i, 5, QTableWidgetItem(str(med_cross)))
       
     
        

   
    # Ajustar ancho según headers
    font_metrics = table.fontMetrics()
    for col in range(table.columnCount()):
        header_text = table.horizontalHeaderItem(col).text()
        text_width = font_metrics.horizontalAdvance(header_text)
        table.setColumnWidth(col, text_width + 80)

    layout.addWidget(table)
    dlg.resize(650, 415)
    if getattr(sys, 'frozen', False):
        # Ruta dentro del .exe
        base_path = Path(sys._MEIPASS)
    else:
        # Ruta normal cuando se ejecuta con Python
        base_path = Path(__file__).parent.parent.parent

    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))
    dlg.exec_()
    

    

def mostrar_des_isoc(parent, id_ref):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Información desplazamiento del isocentro")
    layout = QVBoxLayout(dlg)

    conn = Conexion().conectar()
    cursor = conn.cursor()

    def cargar_datos(tabla):
        cursor.execute(f"""
            SELECT ubicacion, teorico, medido, diferencia
            FROM {tabla}
            WHERE ref=?
        """, (id_ref,))
        datos = cursor.fetchall()

        datos_limpios = {}
        for ubi, teo, med, diff in datos:
            try:
                ubi = (str(ubi).replace("°", "").strip())
            except Exception as e:
                print(f"Error en mostrar desp isocentro: {e}")
                continue
            datos_limpios[ubi] = (teo, med, diff)

        return [datos_limpios.get(n, ("", "")) for n in ["Longitudinal", "Vertical", "Lateral"]]

    datos_brazo = cargar_datos("HC_desplazamiento_isocentro_mensual")
    conn.close()

    table = QTableWidget()
    table.setColumnCount(5)
    table.setRowCount(3)
    table.setHorizontalHeaderLabels(["", "Ubicacion", "Teorico", "Medido (cm)", "Diferencia (%)"])

    niveles = ["Longitudinal", "Vertical", "Lateral"]

    # Brazo
    table.setSpan(0, 0, 4, 1)
    table.setItem(0, 0, QTableWidgetItem("Isocentro"))
    for i, nivel in enumerate(niveles):
        table.setItem(i, 1, QTableWidgetItem(nivel))
        table.setItem(i, 2, QTableWidgetItem(str(datos_brazo[i][0])))
        table.setItem(i, 3, QTableWidgetItem(str(datos_brazo[i][1])))
        table.setItem(i, 4, QTableWidgetItem(str(datos_brazo[i][2])))
        

   
    # Ajustar ancho según headers
    font_metrics = table.fontMetrics()
    for col in range(table.columnCount()):
        header_text = table.horizontalHeaderItem(col).text()
        text_width = font_metrics.horizontalAdvance(header_text)
        table.setColumnWidth(col, text_width + 80)

    layout.addWidget(table)
    dlg.resize(650, 415)
    if getattr(sys, 'frozen', False):
        # Ruta dentro del .exe
        base_path = Path(sys._MEIPASS)
    else:
        # Ruta normal cuando se ejecuta con Python
        base_path = Path(__file__).parent.parent.parent

    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))
    dlg.exec_()
    

def mostrar_indicadores_camilla(parent, id_ref):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Información indicadores de la camilla")
    layout = QVBoxLayout(dlg)

    conn = Conexion().conectar()
    cursor = conn.cursor()

    def cargar_datos(tabla):
        cursor.execute(f"""
            SELECT ubicacion, desplazamiento, medido_cm, diferencia
            FROM {tabla}
            WHERE ref=?
        """, (id_ref,))
        datos = cursor.fetchall()

        # Agrupar por ubicación → lista de (desp, med, dif)
        datos_limpios = {"Longitudinal": [], "Vertical": [], "Lateral": []}

        for ubi, desp, med, dif in datos:
            ubicacion = str(ubi).replace("°", "").strip()
            if ubicacion in datos_limpios:
                datos_limpios[ubicacion].append((desp, med, dif))

        return [datos_limpios[n] for n in ["Longitudinal", "Vertical", "Lateral"]]

    datos_brazo = cargar_datos("HC_indicadores_camilla")
    conn.close()

    table = QTableWidget()
    table.setColumnCount(4)
    table.setRowCount(9)
    table.setHorizontalHeaderLabels(["", "Desplazamiento", "Medido", "Diferencia (%)"])

    niveles = ["1", "5", "20"]
    
    secciones = [
        ("Longitudinal", 0),
        ("Vertical",     3),
        ("Lateral",      6),
    ]

    for idx, (nombre, fila_base) in enumerate(secciones):
        table.setSpan(fila_base, 0, 3, 1)
        table.setItem(fila_base, 0, QTableWidgetItem(nombre))

        for i, (desp, med, dif) in enumerate(datos_brazo[idx]):
            fila = fila_base + i
            table.setItem(fila, 1, QTableWidgetItem(str(desp)))
            table.setItem(fila, 2, QTableWidgetItem(str(med)))
            table.setItem(fila, 3, QTableWidgetItem(str(dif)))

   

   
    # Ajustar ancho según headers
    font_metrics = table.fontMetrics()
    for col in range(table.columnCount()):
        header_text = table.horizontalHeaderItem(col).text()
        text_width = font_metrics.horizontalAdvance(header_text)
        table.setColumnWidth(col, text_width + 80)

    layout.addWidget(table)
    dlg.resize(650, 415)
    if getattr(sys, 'frozen', False):
        # Ruta dentro del .exe
        base_path = Path(sys._MEIPASS)
    else:
        # Ruta normal cuando se ejecuta con Python
        base_path = Path(__file__).parent.parent.parent

    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))
    dlg.exec_()

def mostrar_laseres(parent, id_ref):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Información indicadores del brazo")
    layout = QVBoxLayout(dlg)

    conn = Conexion().conectar()
    cursor = conn.cursor()

    def cargar_datos(tabla):
        cursor.execute(f"""
            SELECT ubicacion, concordancia, dif_isocentro
            FROM {tabla}
            WHERE ref=?
        """, (id_ref,))
        datos = cursor.fetchall()

        datos_limpios = {}
        for nivel, cons, equi in datos:
            try:
                nivel_int = (str(nivel).replace("°", "").strip())
            except Exception as e:
                print(f"Error en mostrar laseres: {e}")
                continue
            datos_limpios[nivel_int] = (cons, equi)

        return [datos_limpios.get(n, ("", "")) for n in ["Longitudinal", "Vertical", "Lateral"]]

    datos_brazo = cargar_datos("HC_indicadores_laser")
    conn.close()

    table = QTableWidget()
    table.setColumnCount(4)
    table.setRowCount(3)
    table.setHorizontalHeaderLabels(["", "Ubicacion Laser", "Concordancia Drump-Phantom", "Diferencia con isocentro"])

    niveles = ["Longitudinal", "Vertical", "Lateral"]

    # Brazo
    table.setSpan(0, 0, 3, 1)
    table.setItem(0, 0, QTableWidgetItem("Laseres"))
    for i, nivel in enumerate(niveles):
        table.setItem(i, 1, QTableWidgetItem(nivel))
        table.setItem(i, 2, QTableWidgetItem(str(datos_brazo[i][0])))
        table.setItem(i, 3, QTableWidgetItem(str(datos_brazo[i][1])))

   
    # Ajustar ancho según headers
    font_metrics = table.fontMetrics()
    for col in range(table.columnCount()):
        header_text = table.horizontalHeaderItem(col).text()
        text_width = font_metrics.horizontalAdvance(header_text)
        table.setColumnWidth(col, text_width + 80)

    layout.addWidget(table)
    dlg.resize(650, 415)
    if getattr(sys, 'frozen', False):
        # Ruta dentro del .exe
        base_path = Path(sys._MEIPASS)
    else:
        # Ruta normal cuando se ejecuta con Python
        base_path = Path(__file__).parent.parent.parent

    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))
    dlg.exec_()
    

def mostrar_indc_brazo_HC(parent, id_ref):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Información indicadores del brazo")
    layout = QVBoxLayout(dlg)

    conn = Conexion().conectar()
    cursor = conn.cursor()

    def cargar_datos(tabla):
        cursor.execute(f"""
            SELECT nivel, valor_medido, discrepancia
            FROM {tabla}
            WHERE ref=?
        """, (id_ref,))
        datos = cursor.fetchall()

        datos_limpios = {}
        for nivel, cons, equi in datos:
            try:
                nivel_int = float(str(nivel).replace("°", "").strip())
            except:
                continue
            datos_limpios[nivel_int] = (cons, equi)

        return [datos_limpios.get(n, ("", "")) for n in [0, 90, 180, 270]]

    datos_brazo = cargar_datos("HC_indicadores_brazo")
    datos_colimador = cargar_datos("HC_indicadores_colimador")
    conn.close()

    table = QTableWidget()
    table.setColumnCount(4)
    table.setRowCount(8)
    table.setHorizontalHeaderLabels(["", "Nivel", "Medido", "Diferencia"])

    niveles = ["0", "90", "180", "270"]

    # Brazo
    table.setSpan(0, 0, 4, 1)
    table.setItem(0, 0, QTableWidgetItem("Brazo"))
    for i, nivel in enumerate(niveles):
        table.setItem(i, 1, QTableWidgetItem(nivel))
        table.setItem(i, 2, QTableWidgetItem(str(datos_brazo[i][0])))
        table.setItem(i, 3, QTableWidgetItem(str(datos_brazo[i][1])))

    # Colimador
    table.setSpan(4, 0, 4, 1)
    table.setItem(4, 0, QTableWidgetItem("Colimador"))
    for i, nivel in enumerate(niveles):
        row = 4 + i
        table.setItem(row, 1, QTableWidgetItem(nivel))
        table.setItem(row, 2, QTableWidgetItem(str(datos_colimador[i][0])))
        table.setItem(row, 3, QTableWidgetItem(str(datos_colimador[i][1])))

    # Ajustar ancho según headers
    font_metrics = table.fontMetrics()
    for col in range(table.columnCount()):
        header_text = table.horizontalHeaderItem(col).text()
        text_width = font_metrics.horizontalAdvance(header_text)
        table.setColumnWidth(col, text_width + 80)

    layout.addWidget(table)
    dlg.resize(650, 415)
    if getattr(sys, 'frozen', False):
        # Ruta dentro del .exe
        base_path = Path(sys._MEIPASS)
    else:
        # Ruta normal cuando se ejecuta con Python
        base_path = Path(__file__).parent.parent.parent

    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))
    dlg.exec_()


" ---------------------------------- Función genérica para mostrar QDialog --------------------------------------- "
def _mostrar_dialogo(parent, headers, data, w, h, tabla_db=None, id_ref=None):
    # A6.2-bis: diálogo con botones de editar y eliminar (guardarEdicion /
    # verificar_eliminar más abajo) -- sin la identidad, ambas acciones se
    # auditaban con `usuario` NULL.
    dlg = _dialogo_con_identidad(QDialog(parent), parent)
    dlg.setWindowTitle("Detalle")
    if getattr(sys, 'frozen', False):
        # Ruta dentro del .exe
        base_path = Path(sys._MEIPASS)
    else:
        # Ruta normal cuando se ejecuta con Python
        base_path = Path(__file__).parent.parent.parent

    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))

    layout = QVBoxLayout(dlg)

    # ------------------ Tabla ------------------
    table = QTableWidget()
    table.setColumnCount(len(headers))
    # headers es una lista de tuplas (db_name, alias)
    for idx, (db_name, alias) in enumerate(headers):  
        item = QTableWidgetItem(alias)          # lo que ve el usuario  
        item.setData(Qt.UserRole, db_name)      # nombre real de BD  
        table.setHorizontalHeaderItem(idx, item)

    table.setRowCount(len(data))

    for row_idx, row_data in enumerate(data):
        for col_idx, value in enumerate(row_data):
            if isinstance(value, QWidget):
                table.setCellWidget(row_idx, col_idx, value)
            else:
                if isinstance(value, float):
                    value = f"{value:.3f}"
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignCenter)
                if col_idx == 0:
                    item.setData(Qt.UserRole, row_data[0])  
                table.setItem(row_idx, col_idx, item)
    layout.addWidget(table)

    # ------------------ Botones ------------------
    if tabla_db != "analisis_placa_franjas":
        dlg.btn_delete = QPushButton('Eliminar')    
        dlg.edit_table = QPushButton('Editar')
        dlg.accept_edit = QPushButton('Aceptar')
        dlg.accept_edit.hide()
        dlg.cancel_edit = QPushButton('Cancelar')
        dlg.cancel_edit.hide()

        edit_table_tools = QHBoxLayout()
        edit_table_tools.addWidget(dlg.btn_delete)
        edit_table_tools.addWidget(dlg.edit_table)
        edit_table_tools.addWidget(dlg.accept_edit)
        edit_table_tools.addWidget(dlg.cancel_edit)

        layout.addLayout(edit_table_tools)

        # ------------------ Conexiones ------------------
        dlg.edit_table.clicked.connect(
            lambda: verificar_editar(dlg, table, tabla_db, "ref", id_ref)
        )
        dlg.accept_edit.clicked.connect(
            lambda: guardarEdicion(dlg, table, tabla_db, id_ref)
        )
        dlg.cancel_edit.clicked.connect(
            lambda: cancelarEdicion(dlg)
        )
        dlg.btn_delete.clicked.connect(
            lambda: verificar_eliminar(dlg, table, tabla_db, id_ref)
        )

    dlg.resize(w, h)
    dlg.exec_()

" ---------------------------------- Función para mostrar la tabla de analisi de imagen -------------------------- "
def mostrar_analisis_franjas(parent, id_ref):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Análisis de franjas")
    main_layout = QHBoxLayout(dlg)  # Horizontal para poner tabla + nota

    conn = Conexion().conectar()
    cursor = conn.cursor()

    # Si no se pasa id_ref, usamos el último guardado
    if id_ref is None:
        cursor.execute("SELECT MAX(ref) FROM analisis_placa_franjas")
        id_ref = cursor.fetchone()[0]

    cursor.execute("""
        SELECT franja, ancho_media_h, ancho_media_v,
            penumbra_izq_h, penumbra_izq_v,
            penumbra_der_h, penumbra_der_v,
            diferencia_arriba_izq, diferencia_arriba_der,
            diferencia_abajo_izq, diferencia_abajo_der
        FROM analisis_placa_franjas
        WHERE ref=?
    """, (id_ref,))
    filas = cursor.fetchall()
    conn.close()

    # Ordenar por número de franja usando regex
    filas.sort(key=lambda f: int(re.search(r"\d+", f[0]).group()))

    franja_labels = [f[0] for f in filas]

    caracteristicas = [
        ("Tam. Campo H",  lambda f: f[1]),
        ("Tam. Campo V",  lambda f: f[2]),
        ("Penumbra Izq. H", lambda f: f[3]),
        ("Penumbra Izq. V", lambda f: f[4]),
        ("Penumbra Der. H", lambda f: f[5]),
        ("Penumbra Der. V", lambda f: f[6]),
        ("Diferencia Camp. 1", lambda f: f[7]),
        ("Diferencia Camp. 2", lambda f: f[8]),
        ("Diferencia Camp. 3", lambda f: f[9]),
        ("Diferencia Camp. 4", lambda f: f[10]),
    ]

    # ---------------- Tabla ----------------
    table = QTableWidget()
    table.setColumnCount(1 + len(franja_labels))
    table.setRowCount(len(caracteristicas))
    table.setHorizontalHeaderLabels(["Característica"] + franja_labels)

    for row, (nombre, getter) in enumerate(caracteristicas):
        table.setItem(row, 0, QTableWidgetItem(nombre))
        for col, franja_data in enumerate(filas):
            valor = getter(franja_data)
            table.setItem(row, col + 1, QTableWidgetItem("No Disponible" if valor is None else f"{valor:.3f}"))

    # ---------------- Nota al lado ----------------
    nota_texto = """
    <p style="font-family:'Arial'; font-size:10pt;">
    <b>Nota:</b> Las diferencias de campo para cada franja se asignan así:<br><br>
    <b>&nbsp;&nbsp;&nbsp;Franja 1:</b><br>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Dif 1: Arriba Izquierda<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Dif 2: Arriba Derecha<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Dif 3: Izquierda Arriba<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Dif 4: Izquierda Abajo<br><br>
    <b>&nbsp;&nbsp;&nbsp;Franja 2:</b><br>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Dif 1: Arriba Medio<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Dif 2: Abajo Medio<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Dif 3: Izquierda Medio<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Dif 4: Derecha Medio<br><br>
    <b>&nbsp;&nbsp;&nbsp;Franja 3:</b><br>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Dif 1: Abajo Izquierda<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Dif 2: Abajo Derecha<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Dif 3: Derecha Arriba<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Dif 4: Derecha Abajo
    </p>
    """

    nota = QTextBrowser()
    nota.setHtml(nota_texto)
    nota.setOpenExternalLinks(False)
    nota.setReadOnly(True)
    nota.setMinimumWidth(250)

    correcciones_btn = QPushButton("Ver Correcciones")
    correcciones_btn.clicked.connect(lambda: mostrar_veri_corr(parent = parent, id_ref = id_ref))

    # Layout vertical para nota + botón
    nota_layout = QVBoxLayout()
    nota_layout.addWidget(nota)
    nota_layout.addWidget(correcciones_btn, alignment=Qt.AlignCenter)

    # Añadir widgets al layout horizontal principal
    main_layout.addWidget(table, stretch=4)
    main_layout.addLayout(nota_layout, stretch=2)

    if getattr(sys, 'frozen', False):
        # Ruta dentro del .exe
        base_path = Path(sys._MEIPASS)
    else:
        # Ruta normal cuando se ejecuta con Python
        base_path = Path(__file__).parent.parent.parent

    dlg.resize(1050, 470)
    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))
    dlg.exec_()

def mostrar_veri_corr(parent, id_ref):
    try:
        dlg = QDialog(parent)
        dlg.setWindowTitle("Análisis de franjas")

        conn = Conexion().conectar()
        cursor = conn.cursor()

        # --------- TABLA 1: VERIFICACIONES ---------
        cursor.execute("""
            SELECT lado_arriba, lado_abajo, lado_izquierda, lado_derecha,
                desv_vert_izq, desv_vert_der, desv_horiz_arriba, desv_horiz_abajo,
                alineado_horizontal, simetrico
            FROM analisis_placa_verificaciones
            WHERE ref = ? AND tipo = 'verificacion_inicial'
        """, (id_ref,))
        datos_inicial = cursor.fetchone()

        cursor.execute("""
            SELECT lado_arriba, lado_abajo, lado_izquierda, lado_derecha,
                desv_vert_izq, desv_vert_der, desv_horiz_arriba, desv_horiz_abajo,
                alineado_horizontal, simetrico
            FROM analisis_placa_verificaciones
            WHERE ref = ? AND tipo = 'verificacion_ideal'
        """, (id_ref,))
        datos_ideal = cursor.fetchone()

        tabla_verif = QTableWidget()
        tabla_verif.setRowCount(10)
        tabla_verif.setColumnCount(4)
        tabla_verif.setHorizontalHeaderLabels(["      ", "        ", "Cuadro Original", "Cuadro Ajustado"])

        tabla_verif.setSpan(0, 0, 4, 1)
        tabla_verif.setSpan(4, 0, 4, 1)
        tabla_verif.setSpan(8, 0, 1, 2)
        tabla_verif.setSpan(9, 0, 1, 2)

        tabla_verif.setItem(0, 0, QTableWidgetItem("Dimensiones"))
        tabla_verif.setItem(4, 0, QTableWidgetItem("Desviaciones"))
        tabla_verif.setItem(8, 0, QTableWidgetItem("Alineación"))
        tabla_verif.setItem(9, 0, QTableWidgetItem("Simetría"))

        subtitulos = [
            "Arriba (mm)", "Abajo (mm)", "Izquierda (mm)", "Derecha (mm)",
            "Incl. Vertical Izq. (mm)", "Incl. Vertical Der. (mm)",
            "Incl. Horizontal Arr.(mm)", "Incl. Horizontal Aba.(mm)"
        ]
        for i, texto in enumerate(subtitulos):
            tabla_verif.setItem(i, 1, QTableWidgetItem(texto))

        def asignar_datos(datos, col):
            if datos:
                for i, valor in enumerate(datos):
                    fila = i if i < 8 else (8 if i == 8 else 9)
                    tabla_verif.setItem(fila, col, QTableWidgetItem(str(valor)))

        asignar_datos(datos_inicial, 2)
        asignar_datos(datos_ideal, 3)
        font_metrics = tabla_verif.fontMetrics()

        for col in range(tabla_verif.columnCount()):
            header_text = tabla_verif.horizontalHeaderItem(col).text()
            text_width = font_metrics.horizontalAdvance(header_text)
            # Agregamos un pequeño margen
            tabla_verif.setColumnWidth(col, text_width + 70)

        # --------- TABLA 2: CORRECCIONES (dx, dy) ---------
        cursor.execute("""
            SELECT vertice, delta_x, delta_y
            FROM analisis_placa_correcciones
            WHERE ref = ?
        """, (id_ref,))
        datos_correcciones = cursor.fetchall()

        tabla_corr = QTableWidget()
        tabla_corr.setRowCount(len(datos_correcciones))
        tabla_corr.setColumnCount(3)
        tabla_corr.setHorizontalHeaderLabels(["Correcciones", "ΔX (mm)", "ΔY(mm)"])

        for i, (vertice, dx, dy) in enumerate(datos_correcciones):
            tabla_corr.setItem(i, 0, QTableWidgetItem(vertice))
            tabla_corr.setItem(i, 1, QTableWidgetItem(str(dx)))
            tabla_corr.setItem(i, 2, QTableWidgetItem(str(dy)))
        tabla_corr.setItem(0, 0, QTableWidgetItem("Arriba Izq."))
        tabla_corr.setItem(1, 0, QTableWidgetItem("Arriba Der."))
        tabla_corr.setItem(2, 0, QTableWidgetItem("Abajo Izq."))
        tabla_corr.setItem(3, 0, QTableWidgetItem("Abajo Der."))
        font_metrics = tabla_corr.fontMetrics()

        for col in range(tabla_corr.columnCount()):
            header_text = tabla_corr.horizontalHeaderItem(col).text()
            text_width = font_metrics.horizontalAdvance(header_text)
            # Agregamos un pequeño margen
            tabla_corr.setColumnWidth(col, text_width + 70)
        # --------- TABLA 3: DIFERENCIAS ---------
        cursor.execute("""
            SELECT diferencia_arriba, diferencia_abajo, diferencia_izquierda, diferencia_derecha
            FROM analisis_placa_correcciones
            WHERE ref = ?
            LIMIT 1
        """, (id_ref,))
        fila = cursor.fetchone()

        tabla_diff = QTableWidget()
        tabla_diff.setRowCount(4)
        tabla_diff.setColumnCount(2)
        tabla_diff.setHorizontalHeaderLabels(["Lado", "Diferencia Camp. (mm)"])

        if fila:  # Si encontró datos
            lados = ["Arriba", "Abajo", "Izquierda", "Derecha"]
            for i, lado in enumerate(lados):
                tabla_diff.setItem(i, 0, QTableWidgetItem(lado))
                tabla_diff.setItem(i, 1, QTableWidgetItem(str(fila[i])))

        font_metrics = tabla_diff.fontMetrics()

        for col in range(tabla_diff.columnCount()):
            header_text = tabla_diff.horizontalHeaderItem(col).text()
            text_width = font_metrics.horizontalAdvance(header_text)
            # Agregamos un pequeño margen
            tabla_diff.setColumnWidth(col, text_width + 70)
        conn.close()
        # --------- LAYOUT ---------
        layout_principal = QHBoxLayout()  # Dividir en dos columnas

        # Columna 1: solo la tabla de verificaciones
        layout_col1 = QVBoxLayout()
        layout_col1.addWidget(tabla_verif)

        # Columna 2: correcciones y diferencias una arriba de la otra
        layout_col2 = QVBoxLayout()
        layout_col2.addWidget(tabla_corr)
        layout_col2.addWidget(tabla_diff)

        # Añadir columnas al layout principal
        layout_principal.addLayout(layout_col1)
        layout_principal.addLayout(layout_col2)

        layout_principal.setStretch(0, 2)  # Columna 1 → peso 2
        layout_principal.setStretch(1, 1)  # Columna 2 → peso 1

        dlg.setLayout(layout_principal)


        if getattr(sys, 'frozen', False):
            # Ruta dentro del .exe
            base_path = Path(sys._MEIPASS)
        else:
            # Ruta normal cuando se ejecuta con Python
            base_path = Path(__file__).parent.parent.parent

        dlg.resize(1050, 470)
        qss_file = base_path / "resources" / "estilo.qss"
        dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))
        dlg.exec_()

    except Exception:
        print("Error en mostrar_veri_corr():")
        print(traceback.format_exc())

" ---------------------------------- Función general para  la edición de tablas ---------------------------------- "
def verificar_editar(self, table, tabla_db, id_columna, id_ref):
    from ui.paginasGuia.dialogs import DialogAdminPermisoEditar
    print(f"\n* Pide el usuario para editar")
    row = table.currentRow()
    col = table.currentColumn()

    if row == -1 or col == -1:
        QMessageBox.warning(self, 'Error', 'Por favor elija una celda para editar')
        return

    # 📌 Revisar metadata de la celda
    item = table.item(row, col)
    if item:
        col_data = item.data(Qt.UserRole + 1)  # aquí guardaste (tabla, columna) o None
        if col_data is None:
            QMessageBox.warning(self, "Edición no permitida",
                                "Este campo no se puede editar.")
            return

    # Si pasa la validación, pedir permiso
    dialogo = DialogAdminPermisoEditar(self.user_id)
    respuesta = dialogo.exec()
    if respuesta == QDialog.DialogCode.Accepted:
        editar_tablas(self, table, tabla_db, id_columna, id_ref)

def editar_tablas(dlg, tabla_widget, nombre_tabla=None, id_columna="ref", id_valor=None):
    row = tabla_widget.currentRow()
    col = tabla_widget.currentColumn()

    if row == -1 or col == -1:
        QMessageBox.warning(dlg, 'Error', 'Por favor elija una celda para editar')
        return

    item = tabla_widget.item(row, col)
    if not item:
        QMessageBox.warning(dlg, 'Error', 'Celda vacía o no editable')
        return

    dlg.old_value = item.text()
    dlg.editing_item = item
    dlg.editing_row = row
    dlg.editing_col = col

    # Hacemos editable la celda
    item.setFlags(item.flags() | Qt.ItemIsEditable)
    tabla_widget.editItem(item)

    # Ajustar botones
    dlg.btn_delete.hide()
    dlg.edit_table.hide()
    dlg.accept_edit.show()
    dlg.cancel_edit.show()

def guardarEdicion(dlg, tabla_widget, nombre_tabla, id_ref):
    from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico

    db = None
    datos_iniciales, datos_finales = None, None  # 🔹 Evita UnboundLocalError si no es TipoCalibracion

    try:
        #                   Obtener valores editados
        # ---------------------------------------------------------------
        item = dlg.editing_item
        old_value = dlg.old_value
        new_value_raw = item.text().strip()

        print("\n- Entra a guardarEdicion ")
        print(f"    · Old value: {old_value}")
        print(f"    · New value: {new_value_raw}")

        # Si no hubo cambios, cancelar
        if new_value_raw == str(old_value).strip():
            QMessageBox.information(dlg, "Info", "No se realizaron cambios.")
            print("    · No hubo cambios en el valor, se cancela UPDATE")
            return

        # Intentar convertir a número (int o float); si no, se guarda como texto
        try:
            if "." in new_value_raw:
                new_value = float(new_value_raw)
            else:
                new_value = int(new_value_raw)
        except ValueError:
            new_value = new_value_raw

        #                Obtener metadatos de la celda
        # ---------------------------------------------------------------
        row = dlg.editing_row
        id_item = tabla_widget.item(row, dlg.editing_col)

        # Metadata en UserRole
        row_id = id_item.data(Qt.UserRole)          # normalmente PK o ref
        col_data = id_item.data(Qt.UserRole + 1)    # puede ser (tabla, columna) o solo columna

        # Determinar tabla y columna
        if isinstance(col_data, tuple):
            table_name, col_name = col_data
        else:
            table_name, col_name = nombre_tabla, col_data

        # Si es TipoCalibracion, guardar datos iniciales para comparar luego
        if table_name == "TipoCalibracion":
            datos_iniciales = consulta_mesualBraq(dlg, row_id)

        #           Determinar cláusula WHERE según la tabla
        # ---------------------------------------------------------------
        if table_name in ("controles_mensuales", "equipos_medicion", "users",
                        "LinealidadBraquiterapia", "TipoCalibracion"):
            id_where = '"id" = ?'
            valor_where = [row_id]

        elif table_name in ("preguntas", "SistemaMedicion", "CondicionesMedicion", "ResultadosActividad"):
            id_where = '"ref" = ?'
            valor_where = [row_id]

        elif table_name == "tamano_campo":
            campo_nominal_item = tabla_widget.item(row, 0)
            if campo_nominal_item:
                campo_nominal_valor = campo_nominal_item.text()
            else:
                raise Exception("No se pudo obtener el valor de campo_nominal")
            id_where = '"ref" = ? AND "campo_nominal" = ?'
            valor_where = [id_ref, campo_nominal_valor]

        elif table_name == "dosimetriaMen":
            clave = id_item.data(Qt.UserRole)  # debería contener (id_ref, energia)
            if clave:
                id_ref, energia = clave
            else:
                raise Exception("No se encontró metadata (id_ref, energia)")
            id_where = '"ref" = ? AND "energia" = ?'
            valor_where = [id_ref, energia]

        else:
            id_where = '"id" = ?'
            valor_where = [row_id]

        print(f"    → Tabla destino: {table_name}")
        print(f"    → Columna destino: {col_name}")
        print(f"    → WHERE: {id_where} con valores {valor_where}")

        #                     Ejecutar UPDATE
        # ---------------------------------------------------------------
        db = PruebaBasico().opeenDatabase()
        query = QSqlQuery(db)

        sql = f'UPDATE "{table_name}" SET "{col_name}" = ? WHERE {id_where}'
        print(f"    · SQL generado: {sql}")
        print(f"    · Valores: [{new_value}, {valor_where}]")

        query.prepare(sql)
        query.addBindValue(new_value)
        for v in valor_where:
            query.addBindValue(v)

        if not query.exec_():
            error_msg = query.lastError().text()
            print(f" ! Error en query: {error_msg}")
            raise Exception(error_msg)

        # A3 (PLAN_AUDITORIA_DOS_EJES_21-07): edición in-place -- el valor
        # anterior ya se conoce en esta función (old_value, arriba), así que
        # no hace falta un SELECT extra para dejar "col: viejo→nuevo".
        _registrar_auditoria(
            _usuario_actual(dlg), ACCION_EDITAR, table_name,
            ref="|".join(str(v) for v in valor_where),
            detalle=f"{col_name}: {old_value!r} → {new_value!r}")

        QMessageBox.information(dlg, "Éxito", "Registro actualizado correctamente.")
        print("UPDATE ejecutado correctamente")

        #       Recalculo específico para TipoCalibracion
        # ---------------------------------------------------------------
        if table_name == "TipoCalibracion":
            datos_finales = consulta_mesualBraq(dlg, row_id)
            if datos_iniciales is not None and datos_finales != datos_iniciales:
                try:
                    from analisisImagenes.ActividadFuente import factores_correccion, actividad_fuente, calcular_decaimiento

                    # Extraer voltajes válidos
                    voltajes = [float(v) for v in datos_finales["lecturas"].keys()if datos_finales["lecturas"][v] is not None]

                    if not voltajes:
                        raise Exception("No se encontraron lecturas válidas")

                    # Detectar voltaje máximo en valor absoluto
                    X = max(voltajes, key=abs)

                    # Obtener lecturas en +V y -V
                    Vprom = datos_finales["lecturas"].get(str(X))
                    Vnprom = datos_finales["lecturas"].get(str(-X))

                    # Buscar un valor intermedio
                    V = None
                    for v in voltajes:
                        if abs(v) != abs(X):
                            V = datos_finales["lecturas"].get(str(v))
                            break

                    # Calcular factores de corrección
                    Ks, Kpol, Ktp = factores_correccion(Vprom, Vnprom, V, datos_finales["t"], datos_finales["p"],
                        datos_finales["t0"], datos_finales["p0"])

                    # Calcular actividad
                    A = actividad_fuente(
                        Ks, Kpol, Ktp, datos_finales["calibracion_camara"], datos_finales["calibracion_electrometro"],
                        datos_finales["conversion"], Vprom)

                    # Calcular decaimiento
                    dec_valor = calcular_decaimiento(datos_finales["fecha_cer"], datos_finales["fecha_cal"],
                        datos_finales["intensidad"], vida_media_dias=74.2)

                    # Debug
                    print("\n-----------------------------------------------------------------------")
                    print("          Actividad de la fuente (Mensual de braquiterapia)\n")
                    print(f" Ks={round(Ks, 3)}, Kp={round(Kpol, 3)}, Ktp={round(Ktp, 3)}")
                    print(f" A={round(A, 3)}, dec_valor={round(dec_valor, 3)}")
                    print("-----------------------------------------------------------------------")

                    if A is None or dec_valor is None:
                        raise Exception("Los cálculos devolvieron None, no se actualiza la BD")

                    # Actualizar ResultadosActividad
                    query_update = QSqlQuery(db)
                    sql = """
                        UPDATE ResultadosActividad
                        SET Ks = ?, Kp = ?, Ktp = ?,
                            actividad_calculada = ?, actividad_decaimiento = ?
                        WHERE ref = ?
                    """
                    query_update.prepare(sql)
                    query_update.addBindValue(round(Ks, 3))
                    query_update.addBindValue(round(Kpol, 3))
                    query_update.addBindValue(round(Ktp, 3))
                    query_update.addBindValue(round(A, 3))
                    query_update.addBindValue(round(dec_valor, 3))
                    query_update.addBindValue(row_id)

                    if not query_update.exec_():
                        print(" ! Error en query ResultadosActividad:", query_update.lastError().text())
                    else:
                        mostrar_db_mensualBraqui(dlg)
                        print("→ Recalculo y actualización de ResultadosActividad exitoso")

                except Exception as e:
                    traceback.print_exc()
                    print(f"⚠ Error al recalcular actividad: {e}")

    except Exception as e:
        traceback.print_exc()
        QMessageBox.critical(dlg, "Error", f"Error al actualizar: {e}")

    finally:
        if db:
            db.close()
        print("Fin de guardarEdicion\n")

    #                   Restaurar interfaz
    # ---------------------------------------------------------------
    dlg.accept_edit.hide()
    dlg.cancel_edit.hide()
    dlg.btn_delete.show()
    dlg.edit_table.show()

def cancelarEdicion(dlg):
    if hasattr(dlg, "editing_item") and hasattr(dlg, "old_value"):
        dlg.editing_item.setText(dlg.old_value)

    dlg.accept_edit.hide()
    dlg.cancel_edit.hide()
    dlg.btn_delete.show()
    dlg.edit_table.show()

def verificar_eliminar(self, tabla_widget, nombre_tabla, id_ref=None):
    

    selected_row = tabla_widget.currentRow()  # Revisa qué fila está seleccionada

    if selected_row == -1:
        QMessageBox.warning(self, 'Error', 'Por favor elija una fila para eliminar')
        return  
    
    dialogo = DialogAdminPermisoEliminar(self.user_id)
    respuesta = dialogo.exec()
    eliminarRegistro(self, tabla_widget, nombre_tabla, id_ref) if respuesta == QDialog.DialogCode.Accepted else None
"------------------------------------------------PARA REGISTROS DEL CATPHAN-----------------------------------------------------"
def verificar_eliminarCT(self, tabla_widget, nombre_tabla, id_ref=None):
    

    selected_row = tabla_widget.currentRow()  # Revisa qué fila está seleccionada

    if selected_row == -1:
        QMessageBox.warning(self, 'Error', 'Por favor elija una fila para eliminar')
        return  
    
    dialogo = DialogAdminPermisoEliminar(self.user_id)
    respuesta = dialogo.exec()
    eliminarRegistroCT(self, tabla_widget) if respuesta == QDialog.DialogCode.Accepted else None
    
def _serializar_fila_actual(query):
    """Texto 'col=valor; col=valor; ...' de la fila actual de `query` (tras
    next()) -- A2 (PLAN_AUDITORIA_DOS_EJES_21-07.md): el DELETE aquí es
    físico, así que esto va en `detalle` de audit_log para poder reconstruir
    qué se borró. Cadena vacía si no hay fila (nada que serializar)."""
    record = query.record()
    return "; ".join(
        f"{record.fieldName(i)}={query.value(i)}" for i in range(record.count()))


def eliminarRegistroCT(dlg, tabla_widget):
    from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico

    row = tabla_widget.currentRow()
    if row == -1:
        QMessageBox.warning(dlg, 'Error', 'Selecciona una fila')
        return

    item = tabla_widget.item(row, 0)
    mes_control = item.text()  # Solo para mostrar en el mensaje
    id_sesion = int(item.data(Qt.UserRole))  # El id único del control

    if not id_sesion:
        QMessageBox.warning(dlg, 'Error', 'No se pudo obtener el ID del control')
        return

    confirm = QMessageBox.question(
        dlg,
        "Confirmar eliminación",
        f"¿Eliminar control de {mes_control}?",
        QMessageBox.Yes | QMessageBox.No
    )
    if confirm != QMessageBox.Yes:
        return

    db = PruebaBasico().opeenDatabase()

    try:
        # A2: capturar la fila de `controles` ANTES de anular -- deja
        # constancia de qué estado tenía el control al anularse.
        query_fila = QSqlQuery(db)
        query_fila.prepare("SELECT * FROM controles WHERE id = ?")
        query_fila.addBindValue(id_sesion)
        query_fila.exec_()
        fila_controles = _serializar_fila_actual(query_fila) if query_fila.next() else ""

        # C2 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md / PLAN_AUDITORIA_DOS_EJES
        # §7 P4): el físico pidió soft-delete ("no veo ningún soft-delete,
        # ¿dónde queda el registro borrado?"). Anular (activo=0) en vez de
        # DELETE -- `pruebas` y las 7 tablas de resultados CT YA NO se
        # borran: quedan colgadas del mismo id_sesion, recuperables si el
        # control se reactiva. Antes se borraban físicamente (7 DELETE + el
        # de pruebas), lo que iba contra la regla del proyecto de nunca
        # eliminar registros históricos.
        q = QSqlQuery(db)
        q.prepare("UPDATE controles SET activo = 0 WHERE id = ?")
        q.addBindValue(id_sesion)
        if not q.exec_():
            raise Exception(q.lastError().text())

        _registrar_auditoria(
            _usuario_actual(dlg), ACCION_ANULAR, "controles", ref=str(id_sesion),
            detalle=f"CT diario ({mes_control}); {fila_controles}")

        tabla_widget.removeRow(row)
        QMessageBox.information(dlg, "Éxito", "Control anulado")

    except Exception as e:
        QMessageBox.critical(dlg, "Error", str(e))
    finally:
        db.close()



def verificar_eliminarCT_anual(self, tabla_widget, nombre_tabla, id_ref=None):
    

    selected_row = tabla_widget.currentRow()  # Revisa qué fila está seleccionada

    if selected_row == -1:
        QMessageBox.warning(self, 'Error', 'Por favor elija una fila para eliminar')
        return  
    
    dialogo = DialogAdminPermisoEliminar(self.user_id)
    respuesta = dialogo.exec()
    eliminarRegistroCT_anual(self, tabla_widget) if respuesta == QDialog.DialogCode.Accepted else None
    
def eliminarRegistroCT_anual(dlg, tabla_widget):
    from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico

    row = tabla_widget.currentRow()
    if row == -1:
        QMessageBox.warning(dlg, 'Error', 'Selecciona una fila')
        return

    item = tabla_widget.item(row, 0)
    year_control = item.text()  # Solo para mostrar en el mensaje
    id_sesion = item.data(Qt.UserRole)  # El id único del control

    if not id_sesion:
        QMessageBox.warning(dlg, 'Error', 'No se pudo obtener el ID del control')
        return

    confirm = QMessageBox.question(
        dlg,
        "Confirmar eliminación",
        f"¿Eliminar control anual de {year_control}?",
        QMessageBox.Yes | QMessageBox.No
    )
    if confirm != QMessageBox.Yes:
        return

    db = PruebaBasico().opeenDatabase()

    try:
        # A2: capturar la fila de `controles` ANTES de anular (mismo criterio
        # que eliminarRegistroCT -- ver su comentario).
        query_fila = QSqlQuery(db)
        query_fila.prepare("SELECT * FROM controles WHERE id = ?")
        query_fila.addBindValue(id_sesion)
        query_fila.exec_()
        fila_controles = _serializar_fila_actual(query_fila) if query_fila.next() else ""

        # C2 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md / PLAN_AUDITORIA_DOS_EJES
        # §7 P4): anular en vez de borrar (mismo criterio que
        # eliminarRegistroCT -- ver su comentario). Las 7 tablas de detalle
        # CT + pruebas quedan intactas, colgadas del mismo id_sesion.
        q = QSqlQuery(db)
        q.prepare("UPDATE controles SET activo = 0 WHERE id = ?")
        q.addBindValue(id_sesion)
        if not q.exec_():
            raise Exception(q.lastError().text())

        _registrar_auditoria(
            _usuario_actual(dlg), ACCION_ANULAR, "controles", ref=str(id_sesion),
            detalle=f"CT anual ({year_control}); {fila_controles}")

        tabla_widget.removeRow(row)
        QMessageBox.information(dlg, "Éxito", "Control anual anulado")

    except Exception as e:
        QMessageBox.critical(dlg, "Error", str(e))
    finally:
        db.close()
"--------....-.-.-.-----------------------------------------------..-.-.-----------------------------------..-.-.--.-------.--.."
def eliminarRegistro(dlg, tabla_widget, nombre_tabla, id_ref=None):
    from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico

    row = tabla_widget.currentRow()
    if row == -1:
        QMessageBox.warning(dlg, 'Error', 'Por favor selecciona una fila para eliminar')
        return

    # G5 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md §5-b): el escaneo de
    # metadata se movió ANTES de la confirmación (antes vivía dentro del
    # try, después de preguntar) para poder anunciar QUÉ se va a anular --
    # en dosimetriaMen, el texto genérico ("¿desea eliminar este
    # registro?") no avisaba que se anula el bloque COMPLETO de una
    # energía (dosis, calidad, simetría y planicidad juntas), consecuencia
    # de la clave compuesta (ref, energia) sin id propio.
    row_id, col_data = None, None
    for col in range(tabla_widget.columnCount()):
        item = tabla_widget.item(row, col)
        if item and item.data(Qt.UserRole) is not None:
            row_id = item.data(Qt.UserRole)
            col_data = item.data(Qt.UserRole + 1)
            break

    if row_id is None:
        QMessageBox.critical(dlg, "Error",
                              "Error al eliminar: No se encontró metadata "
                              "(id/ref) en la fila seleccionada")
        return

    if (nombre_tabla == "dosimetriaMen"
            and isinstance(row_id, (tuple, list)) and len(row_id) == 2):
        _, energia = row_id
        texto_confirmacion = (
            f"Se anulará el registro completo de la energía {energia} de "
            f"este control (dosis, calidad, simetría y planicidad). Las "
            f"filas quedan en el historial, no se borran."
        )
    else:
        texto_confirmacion = "¿Está seguro que desea eliminar este registro?"

    # Confirmación
    confirm = QMessageBox.question(
        dlg,
        "Confirmar eliminación",
        texto_confirmacion,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    if confirm != QMessageBox.Yes:
        return

    db = None
    try:
        table_name = nombre_tabla

        # E5 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §6): dosimetriaMen (y
        # tamano_campo) NO tienen columna "id" -- su identidad real es una
        # clave compuesta. El "id"=? por defecto de abajo cae al fallback de
        # SQLite para identificadores entre comillas sin columna (compara
        # contra el LITERAL 'id', nunca encuentra nada): silenciosamente no
        # hacía nada antes de E7, y desde E7 revienta con "No se encontró el
        # registro" (el chequeo `existe` nuevo lo destapó al conectar este
        # botón). Mismo dispatch por tabla que ya usa guardarEdicion, misma
        # razón: sin esto, el botón de Dosimetría quedaría "conectado" pero
        # inservible -- justo el defecto que E5 vino a cerrar.
        if table_name == "dosimetriaMen":
            if not (isinstance(row_id, (tuple, list)) and len(row_id) == 2):
                raise Exception("No se encontró metadata (id_ref, energia) en la fila seleccionada")
            id_where = '"ref" = ? AND "energia" = ?'
            valor_where = list(row_id)
        elif table_name == "tamano_campo":
            campo_nominal_item = tabla_widget.item(row, 0)
            if not campo_nominal_item:
                raise Exception("No se pudo obtener el valor de campo_nominal")
            id_where = '"ref" = ? AND "campo_nominal" = ?'
            valor_where = [id_ref, campo_nominal_item.text()]
        else:
            id_where = '"id" = ?'
            valor_where = [row_id]

        print(f"→ Eliminando en tabla {table_name}, WHERE {id_where}, valores {valor_where}")

        # --- Ejecutar la operación ---
        db = PruebaBasico().opeenDatabase()
        query = QSqlQuery(db)
        query.exec_("PRAGMA foreign_keys = ON;")

        # A2: capturar la fila ANTES de anular/borrar -- si sigue siendo un
        # DELETE físico (tablas de detalle/catálogo), es la única forma de
        # reconstruir qué se eliminó.
        query_fila = QSqlQuery(db)
        query_fila.prepare(f'SELECT * FROM "{table_name}" WHERE {id_where}')
        for v in valor_where:
            query_fila.addBindValue(v)
        query_fila.exec_()
        existe = query_fila.next()
        fila_actual = _serializar_fila_actual(query_fila) if existe else ""

        # E7 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §11): "controles" era la
        # ÚNICA tabla del bloque de QC con soft-delete (C2); las demás
        # (dosimetriaMen, preguntas, tamano_campo, TipoCalibracion, las 4
        # diarias...) se borraban físicamente una a una -- el caso más grave,
        # anular un TipoCalibracion arrastraba en cascada ResultadosActividad
        # (la actividad calculada de la fuente de braquiterapia) sin dejar
        # nada recuperable. Ahora TODA tabla en la lista blanca cerrada del
        # inventario del plan (services/anulacion.py::TABLAS_ANULABLES)
        # anula en vez de borrar. Fuera de esa lista (subtablas de detalle
        # sin botón de borrado propio, catálogos) sigue con DELETE físico --
        # ya auditado (A2).
        if table_name in TABLAS_ANULABLES:
            if not existe:
                raise Exception("No se encontró el registro a eliminar")
            ref_legible = ("/".join(str(v) for v in valor_where)
                          if len(valor_where) > 1 else str(row_id))
            anular_fila(db, table_name, row_id, _usuario_actual(dlg),
                       detalle=fila_actual, id_where=id_where,
                       valor_where=valor_where, ref=ref_legible)
            QMessageBox.information(dlg, "Éxito", "Registro anulado correctamente.")
            tabla_widget.removeRow(row)
            print("UPDATE (anular) ejecutado correctamente")
        else:
            sql = f'DELETE FROM "{table_name}" WHERE {id_where}'
            query.prepare(sql)
            for v in valor_where:
                query.addBindValue(v)

            if not query.exec_():
                error_msg = query.lastError().text()
                print(f" ! Error en {sql.split()[0]}: {error_msg}")
                raise Exception(error_msg)

            _registrar_auditoria(_usuario_actual(dlg), ACCION_ELIMINAR, table_name,
                                 ref=str(row_id), detalle=fila_actual)

            QMessageBox.information(dlg, "Éxito", "Registro eliminado correctamente.")
            tabla_widget.removeRow(row)
            print(f"{sql.split()[0]} ejecutado correctamente")

    except Exception as e:
        traceback.print_exc()
        QMessageBox.critical(dlg, "Error", f"Error al eliminar: {e}")

    finally:
        if db:
            db.close()
        print("Fin de eliminarRegistro\n")

def consulta_mesualBraq(self, id):
    #Hacer una consulta inicial:
    datos_iniciales = {}
    conn = Conexion.conectar(self)
    cursor = conn.cursor()

    # --- CondicionesMedicion ---
    cursor.execute("""
        SELECT t, p
        FROM CondicionesMedicion
        WHERE ref = ?
    """, (id,))
    row = cursor.fetchone()
    if row:
        datos_iniciales["t"], datos_iniciales["p"] = row
    else:
        raise Exception(f"No se encontraron condiciones de medición con ref={id}")
    
    # --- SistemasMedicion ---
    cursor.execute("""
        SELECT t0, p0, calibracion, electrometro
        FROM SistemaMedicion
        WHERE ref = ?
    """, (id,))
    row = cursor.fetchone()
    if row:
        datos_iniciales["t0"], datos_iniciales["p0"], datos_iniciales["calibracion_camara"], datos_iniciales["calibracion_electrometro"] = row

    else:
        raise Exception(f"No se encontraron condiciones de medición con ref={id}")

    # --- LecturasMaximos (traer todas las lecturas de ese ref) ---
    cursor.execute("""
        SELECT voltaje, promediosV
        FROM LecturasMaximos
        WHERE ref = ?
    """, (id,))
    rows = cursor.fetchall()
    if not rows:
        raise Exception(f"No se encontraron lecturas en LecturasMaximos con ref={id}")

    # Convertimos a diccionario {voltaje: promediosV}
    lecturas = {
        str(voltaje): float(prom) if prom is not None else None
        for voltaje, prom in rows   
        }
    datos_iniciales["lecturas"] = lecturas

    # --- Otros datos necesarios (ejemplo: calibraciones, fechas, etc.) ---
    cursor.execute("""
        SELECT  conversion, fecha_cer, fecha, intensidad
        FROM TipoCalibracion
        WHERE id = ?
    """, (id,))
    row = cursor.fetchone()
    if row:
        (datos_iniciales["conversion"],
        datos_iniciales["fecha_cer"],
        datos_iniciales["fecha_cal"],
        datos_iniciales["intensidad"]) = row
    else:
        raise Exception(f"No se encontraron datos de calibración con id={id}")
    conn.close()

    print(f"\n  ● Datos de consulta_mesualBraq: {datos_iniciales}, en la ref = {id}") 
    return datos_iniciales
