from PyQt5.QtWidgets import QMessageBox , QWidget, QHBoxLayout, QLabel, QTableWidgetItem
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtSql import QSqlDatabase, QSqlQuery
from data.ManejoDatos.conection import ruta_base_datos
import traceback

def load_table(self, boolean_keys=None, dosis=None, maquina=""):
    try:
        db = self.opeenDatabase()
        query = QSqlQuery(f"SELECT * FROM {maquina} ORDER BY date DESC")
    except Exception as e:
        traceback.print_exc()
        return

    column_count = query.record().count()
    headers = [query.record().fieldName(i) for i in range(column_count)]

    self.table.setColumnCount(column_count)
    self.table.setHorizontalHeaderLabels(headers)
    self.table.setRowCount(0)

    # Deshabilitar actualizaciones visuales mientras se carga
    self.table.setUpdatesEnabled(False),
    self.table.setSortingEnabled(False)

    row = 0
    while query.next():
        self.table.insertRow(row)
        for col in range(column_count):
            column_name = headers[col].lower()
            value = query.value(col)

            if column_name == "date":
                item = QTableWidgetItem(str(value))
                item.setForeground(QColor(0, 86, 179))
                self.table.setItem(row, col, item)

            elif boolean_keys is not None and column_name in boolean_keys and value in (0, 1):
                # Texto simple en lugar de QWidget completo
                text = "Funciona" if value == 1 else "No Funciona"
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                item.setForeground(QColor(0, 150, 0) if value == 1 else QColor(200, 0, 0))
                self.table.setItem(row, col, item)

            elif dosis is not None and column_name in dosis and maquina != 'braqui':
                if value is None or value == '':
                    # Dosis vacía: la celda queda en blanco. Incrementar row aquí
                    # (dentro del bucle de columnas) desalineaba el render de todos
                    # los registros posteriores.
                    continue
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignCenter)
                if value < 2:
                    item.setForeground(QColor(0, 150, 0))
                elif value < 3:
                    item.setForeground(QColor(200, 150, 0))
                else:
                    item.setForeground(QColor(200, 0, 0))
                self.table.setItem(row, col, item)

            elif column_name == "pelicula":
                item = QTableWidgetItem("Imagen cargada" if value else "Sin imagen")
                item.setData(Qt.UserRole, query.value(0))
                self.table.setItem(row, col, item)

            else:
                self.table.setItem(row, col, QTableWidgetItem(str(value)))

        row += 1

    self.table.setUpdatesEnabled(True)
    self.table.resizeColumnsToContents()

    if maquina == "braqui":
        self.table.itemDoubleClicked.connect(self.verificar_columna_pelicula)

    db.close()
def asignar_encabezados(self, nombre_tabla):
    encabezados_por_tabla = {
    "braqui": [("ID", "id"), ("Fecha", "date"), ("Usuario", "user_id"), ("Int. Consola", "int_con_box"), ("Parada Emerg.", "emerg_con"),
        ("Bloq. Puerta", "blq_puerta"),  ("Ind. Posición", "pos_fuente"), ("Resp. Retorno", "res_fuente"), ("Int. LLave", "key_fuente"),
        ("Monit. Área", "mon_area"), ("Ind. Luminoso", "lum_puerta"), ("Con. Tubo", "tub_guia"), ("Sis. Visualización", "visual_sys"),
        ("Intercom.", "intercom"),  ("Monit. Portátil", "mon_rad_port"), ("Act. Reportada", "tol_rep_act_ci"),
        ("Act. Esperada", "tol_exp_act"), ("Ciclos Dummy", "tol_cyc_dummy"), ("Ciclos", "tol_cyc_rad"), ("Observación", "observaciones"),
        ("Imagen", "pelicula"), ("Dist. Parada", "distancias"), ("Prom. Dist.", "promedio"), ("Desv. Dist.", "desviacion"),
        ("Desplazamiento", "desplazamientos"),  ("Prom. Desplaz.", "promedio_des"), ("Desv. Desplaz.", "desviacion_des")],

    "aceleradorlineal_600": [("ID", "id"), ("Fecha", "date"), ("Usuario", "user_id"), ("Luces Cons.", "luces_consola"),
        ("Luces Puerta", "luces_puerta"), ("Luces Irrad.", "luces_irradiacion"), ("Sis. Visualización", "sistema_visualizacion"),
        ("Sis. Anticolisión", "sistema_anticolision"), ("Int. Puerta", "interruptor_radiacion_puerta"),  
        ("Int. Panel", "interruptor_radiacion_panel"), ("Int. UM", "interrupcion_um"),
        ("Ver. Monitores", "verificacion_monitoras"), ("Mov. Brazos", "movimiento_brazo"), ("Mov.Colimador", "movimiento_colimador"),
        ("Mov. Camilla", "movimientos_camilla"), ("Láseres", "laseres"), ("Telémetro", "telemetro"), ("Tam. Campo", "tamano_campo"),
        ("Cent. Retículo", "centrado_reticulo"), ("Ref. Dósis", "dosis_referencia"), ("Observaciones", "observaciones")],

    "aceleradorlineal_ix": [("ID", "id"), ("Fecha", "date"), ("Usuario", "user_id"), ("Luces Cons.", "luces_consola"),
        ("Luces Puerta", "luces_puerta"), ("Luces Irrad.", "luces_irradiacion"), ("Sis. Visualización", "sistema_visualizacion"),
        ("Sis. Anticolisión", "sistema_anticolision"), ("Int. Puerta", "interruptor_radiacion_puerta"),
        ("Int. Panel.", "interruptor_radiacion_panel"), ("Int. UM", "interrupcion_um"), ("Ver. Monitores", "verificacion_monitoras"),
        ("Mov. Brazos", "movimiento_brazo"), ("Mov.Colimador", "movimiento_colimador"), ("Mov. Camilla", "movimientos_camilla"),
        ("Láseres", "laseres"), ("Telémetro", "telemetro"), ("Tam. Campo", "tamano_campo"), ("Cent. Retículo", "centrado_reticulo"),
        ("CDR. Fot. 6MV", "tol_fot_6mv"), ("CDR. Fot. 15MV", "tol_fot_15mv"), ("CDR. Elec. 6MeV", "tol_ele_6mev"),
        ("CDR. Elec. 9MeV", "tol_ele_9mev"), ("CDR. Elec. 12MeV", "tol_ele_12mev"), ("CDR. Elec. 15MeV", "tol_ele_15mev"),
        ("Observaciones", "observaciones")
    ],

    "halcyon": [("ID", "id"), ("Fecha", "date"), ("Usuario", "user_id"), ("Tam.Isocentro", "IsoCenterSize_name2"),
        ("Desv. Detector MV", "IsoCenterMVOffset"), ("Desv. Detector kV", "IsoCenterKVOffset"),
        ("Camb. Salida", "BeamOutputChange"), ("Camb. Uni.", "BeamUniformityChange"), ("Camb. Ganancia UM1", "BeamMu1GainChange"),
        ("Camb. Ganancia UM2", "BeamMu2GainChange"), ("Gantry Abs.", "GantryAbsolute"), ("Gantry Rel.", "GantryRelative"),
        ("Cam. Lateral", "CouchLat"), ("Cam. Longitudinal", "CouchLng"), ("Cam. Vertical", "CouchVrt"),
        ("Cam. Lat. Long.", "CouchLatLong"), ("Cam. Lon. Long.", "CouchLngLong"), ("Cam. Vert. Long.", "CouchVrtLong"),
        ("Vir.Isocentro Lat.", "VirtualToIsoLat"), ("Vir.Isocentro Lon.", "VirtualToIsoLng"), ("Vir.Isocentro Ver.", "VirtualToIsoVrt"),
        ("Ganancia. Cal", "MVImagerCalibrationGain"), ("Uniformidad. Cal", "MVImagerCalibrationUniformity")]
}

    headers = encabezados_por_tabla.get(nombre_tabla)
    if headers:
        # Solo los nombres bonitos para mostrar
        header_labels = [h[0] for h in headers]
        self.table.setColumnCount(len(header_labels))
        self.table.setHorizontalHeaderLabels(header_labels)

        font_metrics = self.table.fontMetrics()
        for col, header_text in enumerate(header_labels):
            text_width = font_metrics.horizontalAdvance(header_text)
            self.table.setColumnWidth(col, text_width + 30)

        # Guardamos el mapeo índice → nombre real
        self.encabezados_actuales = {i: h[1] for i, h in enumerate(headers)}

    else:
        QMessageBox.warning(self, "Advertencia", f"No se definieron encabezados personalizados para la tabla: {nombre_tabla}")

def eliminarfilas(self, maquina):
    selected_row = self.table.currentRow()  # Revisa qué fila está seleccionada

    if selected_row == -1:
        QMessageBox.warning(self, 'Error', 'Por favor elija una fila para eliminar')
        return  

    pac_id = int(self.table.item(selected_row, 0).text())

    confirm = QMessageBox.question(
        self, 'Usted esta seguro de esta accion?', 'Eliminar este registro',
        QMessageBox.Yes | QMessageBox.No
    )

    if confirm == QMessageBox.No:
        return

    if not QSqlDatabase.contains("qt_sql_default_connection"):
        db = QSqlDatabase.addDatabase("QSQLITE")
        db.setDatabaseName(ruta_base_datos())
    else:
        db = QSqlDatabase.database("qt_sql_default_connection")

    if not db.open():
        QMessageBox.critical(self, "Error", f"No se pudo conectar a la base de datos: {db.lastError().text()}")
        return

    query = QSqlQuery()
    query.prepare(f'DELETE FROM {maquina} WHERE id = ?')
    query.addBindValue(pac_id)

    if not query.exec():  # En PyQt5, exec() devuelve False si falla
        QMessageBox.critical(self, "Error", "Falló la eliminación: " + query.lastError().text())

