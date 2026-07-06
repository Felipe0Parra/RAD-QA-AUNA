
# Modulo para mostrar las tablas de las pruebas en la interfaz
from data.ManejoDatos.conection import Conexion
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QWidget, QGridLayout)
from PyQt5.QtCore import Qt
import sys
from pathlib import Path
from data.ManejoDatos.load import verificar_editar, guardarEdicion, cancelarEdicion, verificar_eliminar

# Tablas relacionadas al control para cada equipo

" ------------------------------------- Tablas que hacen conexion a la base de datos ------------------------------------- "
def tablas_relacionadas():
    tablas_600_ix = [
            "controles",
            'equipos_medicion',
            'energias',
            'tabla_factor_campo',
            'tabla_factores_transmision',
            'tabla_factores_sobre_eje',
            'tabla_control_camaras_monitoras'
            ]
    return {
        "Clinac ix": tablas_600_ix,
        "Clinac 600": tablas_600_ix,
        'Halcyon': [
            "controles",
            'equipos_medicion',
            'energias',
            'HC_fantomas',
            'HC_indicadores_colimador',
            'HC_indicadores_brazo',
            'HC_indicadores_laser',
            'HC_indicadores_camilla',
            'HC_desplazamiento_isocentro_mensual',
            'HC_velocidad_multilaminas_anual',
            'HC_precision_posicion_multilaminas_anual',
            'HC_imagen_perfil_mlc_anual',
            'HC_dosimetria_anual',
            'HC_linealidad_unidades_monitor_anual',
            'HC_tamanos_campo_radiacion'
        ]
    }

def buscar_datos_db(tabla, tipo_equipo, parametros, ref_id):
    """Busca datos de una tabla específica para un control anual"""
    con = Conexion().conectar()
    cursor = con.cursor()
    query = f"SELECT {parametros} FROM {tabla} WHERE ref = ?"
    cursor.execute(query, (ref_id,))
    datos = cursor.fetchall()
    con.close()
    return datos

def buscar_datos_db_energia(tabla, tipo_equipo, parametros, ref_id, id_energia):
    """Busca datos de una tabla específica filtrada por energía para un control anual"""
    con = Conexion().conectar()
    cursor = con.cursor()
    query = f"SELECT {parametros} FROM {tabla} WHERE ref = ? AND id_energia = ?"
    cursor.execute(query, (ref_id, id_energia))
    datos = cursor.fetchall()
    con.close()
    return datos

def buscar_datos_db_energia_pdd(tabla, tipo_equipo, parametros, ref_id, id_energia, pdd):
    """Busca datos de una tabla específica filtrada por energía y PDD para un control anual"""
    con = Conexion().conectar()
    cursor = con.cursor()
    query = f"SELECT {parametros} FROM {tabla} WHERE ref = ? AND id_energia = ? AND pdd = ?"
    cursor.execute(query, (ref_id, id_energia, pdd))
    datos = cursor.fetchall()
    con.close()
    return datos

" ------------------------------------- Mostrar tablas anuales en la interfaz ------------------------------------- "

def mostrar_controles_anuales(parent, tableWidget, equipo_filtrar=None):
    """
    Muestra todos los registros de controles anuales para un equipo específico
    Similar a mostrar_controles_mensuales pero para controles anuales
    """
    conn = Conexion().conectar()
    cursor = conn.cursor()

    query = """
    SELECT 
        c.id,
        c.fecha,
        u.fullname,
        c.equipo,
        c.control
    FROM controles c
    LEFT JOIN users u ON c.user_id = u.fullname
    WHERE c.control = 'Anual'
    """

    if equipo_filtrar:
        query += " AND c.equipo = ? ORDER BY c.fecha DESC"
        cursor.execute(query, (equipo_filtrar,))
    else:
        query += " ORDER BY c.fecha DESC"
        cursor.execute(query)

    rows = cursor.fetchall()
    conn.close()

    # Determinar headers según el equipo
    if equipo_filtrar in ['Clinac 600', 'Clinac ix']:
        headers = [
            ("Fecha", None),
            ("Usuario", None),
            ("Equipo", None),
            ("Eq. Medición", None),
            ("Factor Campo", None),
            ("Factores Transmisión", None),
            ("Factores Sobre Eje", None),
            ("Control Cámaras", None)
        ]
    elif equipo_filtrar == 'Halcyon':
        headers = [
            ("Fecha", None),
            ("Usuario", None),
            ("Equipo", None),
            ("Eq. Medición", None),
            ("Fantomas", None),
            ("Ind. Gantry", None),
            ("Ind. Colimador", None),
            ("Ind. Láser", None),
            ("Ind. Camilla", None),
            ("Vel. MLC", None),
            ("Precisión MLC", None),
            ("Imagen MLC", None),
            ("Dosimetría", None),
            ("Linealidad UM", None),
            ("Tamaños Campo", None)
        ]
    else:
        headers = [
            ("Fecha", None),
            ("Usuario", None),
            ("Equipo", None),
            ("Eq. Medición", None)
        ]

    tableWidget.setColumnCount(len(headers))
    tableWidget.setRowCount(len(rows))

    for i, (texto, meta) in enumerate(headers):
        header_item = QTableWidgetItem(texto)
        header_item.setData(Qt.UserRole, meta)
        tableWidget.setHorizontalHeaderItem(i, header_item)
    
    # Ajustar ancho de columnas al contenido con margen extra
    tableWidget.resizeColumnsToContents()
    for col in range(tableWidget.columnCount()):
        tableWidget.setColumnWidth(col, tableWidget.columnWidth(col) + 76)

    def crear_boton_tabla(texto, callback):
        btn = QPushButton(texto)
        btn.setFixedWidth(80)
        btn.setStyleSheet("background-color: rgb(186, 255, 201); color: black;")
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
        id_ref = row_data[0]  # ID real de controles
        equipo = row_data[3]  # Nombre del equipo

        # Col 0: Fecha
        item = QTableWidgetItem(valor_a_texto(row_data[1], 0))
        item.setData(Qt.UserRole, id_ref)
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

        # Col 3: Eq. Medición
        tableWidget.setCellWidget(row_idx, 3, crear_boton_tabla("Ver tabla", 
            lambda _, r=id_ref: mostrar_tabla_equipos_anual(parent, r)))

        # Botones específicos por equipo
        if equipo in ['Clinac 600', 'Clinac ix']:
            # Col 4: Factor Campo
            tableWidget.setCellWidget(row_idx, 4, crear_boton_tabla("Ver tabla", 
                lambda _, r=id_ref, eq=equipo: mostrar_tabla_factor_campo_anual(parent, r, eq)))

            # Col 5: Factores Transmisión
            tableWidget.setCellWidget(row_idx, 5, crear_boton_tabla("Ver tabla", 
                lambda _, r=id_ref, eq=equipo: mostrar_tabla_factores_transmision_anual(parent, r, eq)))

            # Col 6: Factores Sobre Eje
            tableWidget.setCellWidget(row_idx, 6, crear_boton_tabla("Ver tabla", 
                lambda _, r=id_ref, eq=equipo: mostrar_tabla_factores_sobre_eje_anual(parent, r, eq)))

            # Col 7: Control Cámaras
            tableWidget.setCellWidget(row_idx, 7, crear_boton_tabla("Ver tabla", 
                lambda _, r=id_ref, eq=equipo: mostrar_tabla_control_camaras_anual(parent, r, eq)))

        elif equipo == 'Halcyon':
            # Col 4: Fantomas
            tableWidget.setCellWidget(row_idx, 4, crear_boton_tabla("Ver tabla", 
                lambda _, r=id_ref: mostrar_tabla_fantomas_anual(parent, r)))

            # Col 5: Ind. Gantry
            tableWidget.setCellWidget(row_idx, 5, crear_boton_tabla("Ver tabla", 
                lambda _, r=id_ref: mostrar_tabla_simple_anual(parent, r, 'HC_indicadores_brazo',
                [('nivel', 'Nivel'), ('valor_medido', 'Indicador consola'), ('discrepancia', 'Diferencia')])))

            # Col 6: Ind. Colimador
            tableWidget.setCellWidget(row_idx, 6, crear_boton_tabla("Ver tabla", 
                lambda _, r=id_ref: mostrar_tabla_simple_anual(parent, r, 'HC_indicadores_colimador',
                [('nivel', 'Nivel'), ('valor_medido', 'Indicador consola'), ('discrepancia', 'Diferencia')])))

            # Col 7: Ind. Láser
            tableWidget.setCellWidget(row_idx, 7, crear_boton_tabla("Ver tabla", 
                lambda _, r=id_ref: mostrar_tabla_simple_anual(parent, r, 'HC_indicadores_laser',
                [('ubicacion', 'Ubicación\nLáser'), ('concordancia', 'Concordancia\nDrump-Phantom'), 
                ('dif_isocentro', 'Diferencia con\nisocentro (mm)')])))

            # Col 8: Ind. Camilla
            tableWidget.setCellWidget(row_idx, 8, crear_boton_tabla("Ver tabla", 
                lambda _, r=id_ref: mostrar_tabla_simple_anual(parent, r, 'HC_indicadores_camilla',
                [('ubicacion', 'Ubicación\nCamilla (cm)'), ('desplazamiento', 'Desplazamiento (cm)'), 
                ('medido_cm', 'Medido (cm)'), ('diferencia', 'Diferencia (%)')])))

            # Col 9: Vel. MLC
            tableWidget.setCellWidget(row_idx, 9, crear_boton_tabla("Ver tabla", 
                lambda _, r=id_ref: mostrar_tabla_simple_anual(parent, r, 'HC_velocidad_multilaminas_anual',
                [('banco', 'Banco'), ('velocidad_prom', 'Velocidad promedio'), ('desviacion_med', 'Desviación media')])))

            # Col 10: Precisión MLC
            tableWidget.setCellWidget(row_idx, 10, crear_boton_tabla("Ver tabla", 
                lambda _, r=id_ref: mostrar_tabla_simple_anual(parent, r, 'HC_precision_posicion_multilaminas_anual',
                [('medida', 'Valor medido'), ('esperada', 'Valor esperado'), ('discrepancia', 'Diferencia')])))

            # Col 11: Imagen MLC
            texto_imagen = 'Imagen subida' if check_imagen_mlc_subida(id_ref) else 'No subida'
            item = QTableWidgetItem(texto_imagen)
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            tableWidget.setItem(row_idx, 11, item)
            
            # Col 12: Dosimetría
            tableWidget.setCellWidget(row_idx, 12, crear_boton_tabla("Ver tabla", 
                lambda _, r=id_ref: mostrar_dosimetria_anual(parent, r)))

            # Col 13: Linealidad UM
            tableWidget.setCellWidget(row_idx, 13, crear_boton_tabla("Ver tabla", 
                lambda _, r=id_ref: mostrar_tabla_simple_anual(parent, r, 'HC_linealidad_unidades_monitor_anual',
                [('UM', 'Unidades Monitor'), ('Q1', 'Q1'), ('Q2', 'Q2'), ('Qprom', 'Q Promedio')])))

            # Col 14: Tamaños Campo
            tableWidget.setCellWidget(row_idx, 14, crear_boton_tabla("Ver tabla", 
                lambda _, r=id_ref: mostrar_tabla_simple_anual(parent, r, 'HC_tamanos_campo_radiacion',
                [('indicado_inplane', 'Ind. Inplane'), ('indicado_crossplane', 'Ind. Crossplane'), 
                ('medido_inplane', 'Med. Inplane'), ('medido_crossplane', 'Med. Crossplane')])))
    
def crear_ventanas_emergentes_tablas(self, headers, data, w, h, tabla_db=None, id_ref=None):
    dlg = QDialog(self)
    dlg.setWindowTitle("Detalle")
    if getattr(sys, 'frozen', False):
        # Ruta dentro del .exe
        base_path = Path(sys._MEIPASS)
    else:
        # Ruta normal cuando se ejecuta con Python
        base_path = Path(__file__).parent.parent.parent.parent

    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))

    layout = QVBoxLayout(dlg)

    # ----------------------- Tabla -----------------------
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
    
    # Ajustar ancho de columnas al contenido
    table.resizeColumnsToContents()
    layout.addWidget(table)

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

def mostrar_tablas_anuales_600_ix(self, tipo_equipo, ref_id):
    """
    Muestra todas las tablas anuales para Clinac 600 e iX
    Para iX: múltiples energías (6 MV, 15 MV, 6 MeV, 9 MeV, 12 MeV, 15 MeV)
    Para 600: una sola energía (6 MV)
    """
    # Diccionario de energías
    energia_ids = {0: "6 MV", 1: "15 MV", 2: "6 MeV", 3: "9 MeV", 4: "12 MeV", 5: "15 MeV"}
    
    # Determinar energías según el equipo
    if tipo_equipo == 'Clinac ix':
        energias = [0, 1, 2, 3, 4, 5]  # Todas las energías para iX
    else:  # Clinac 600
        energias = [0]  # Solo 6 MV para 600
    
    # Tabla 1: Equipos de Medición
    datos_equipos_medicion = buscar_datos_db('equipos_medicion', tipo_equipo, 'tipo_camara, equip_type, model, serie', ref_id)
    headers_equipos = [
        ('tipo_camara', 'Cámara'), 
        ('equip_type', 'Tipo Equipo'), 
        ('model', 'Modelo'), 
        ('serie', 'N° Serie')
    ]
    crear_ventanas_emergentes_tablas(self, headers=headers_equipos, data=datos_equipos_medicion, 
                                     w=600, h=400, tabla_db='equipos_medicion', id_ref=ref_id)

    # Tabla 2: Factor de Campo (una ventana por energía)
    for energia_id in energias:
        datos_factor_campo = buscar_datos_db_energia('tabla_factor_campo', tipo_equipo, 
                                                     'tamano_campo, factor_campo, factor_campo_esperado, discrepancia', 
                                                     ref_id, energia_id)
        headers_factor_campo = [
            ('tamano_campo', 'Tamaño de campo'),
            ('factor_campo', 'Factor de campo'),
            ('factor_campo_esperado', 'Factor esperado'),
            ('discrepancia', 'Discrepancia (%)')
        ]
        titulo_energia = f"Factor de Campo - {energia_ids[energia_id]}"
        crear_ventanas_emergentes_tablas(self, headers=headers_factor_campo, data=datos_factor_campo, 
                                        w=500, h=400, tabla_db='tabla_factor_campo', id_ref=ref_id)

    # Tabla 3: Factores de Transmisión (una ventana por energía)
    for energia_id in energias:
        datos_factores_transmision = buscar_datos_db_energia('tabla_factores_transmision', tipo_equipo, 
                                                             'angulo, factor_transmision, factor_transmision_esperado, discrepancia', 
                                                             ref_id, energia_id)
        headers_factores_transmision = [
            ('angulo', 'Accesorio'),
            ('factor_transmision', 'Factor de transmisión'),
            ('factor_transmision_esperado', 'Factor esperado'),
            ('discrepancia', 'Discrepancia (%)')
        ]
        titulo_energia = f"Factores de Transmisión - {energia_ids[energia_id]}"
        crear_ventanas_emergentes_tablas(self, headers=headers_factores_transmision, data=datos_factores_transmision, 
                                        w=550, h=350, tabla_db='tabla_factores_transmision', id_ref=ref_id)

    # Tabla 4: Factores Sobre el Eje (3 PPDs por energía)
    ppds = ["PDD (10 x 10)", "PDD (15 x 15)", "PDD (20 x 20)"]
    for energia_id in energias:
        for pdd in ppds:
            datos_factores_sobre_eje = buscar_datos_db_energia_pdd('tabla_factores_sobre_eje', tipo_equipo, 
                                                                   'profundidad, factor, factor_esperado, discrepancia', 
                                                                   ref_id, energia_id, pdd)
            headers_factores_sobre_eje = [
                ('profundidad', 'Profundidad (cm)'),
                ('factor', pdd),
                ('factor_esperado', 'PDD esperado'),
                ('discrepancia', 'Discrepancia (%)')
            ]
            titulo = f"Factores Sobre el Eje - {energia_ids[energia_id]} - {pdd}"
            crear_ventanas_emergentes_tablas(self, headers=headers_factores_sobre_eje, data=datos_factores_sobre_eje, 
                                           w=500, h=300, tabla_db='tabla_factores_sobre_eje', id_ref=ref_id)

    # Tabla 5: Control de Cámaras Monitoras (una ventana por energía)
    for energia_id in energias:
        datos_control_camaras = buscar_datos_db_energia('tabla_control_camaras_monitoras', tipo_equipo, 
                                                        'indicador, valor', 
                                                        ref_id, energia_id)
        headers_control_camaras = [
            ('indicador', 'Indicador'),
            ('valor', 'Valor')
        ]
        titulo_energia = f"Control de Cámaras Monitoras - {energia_ids[energia_id]}"
        crear_ventanas_emergentes_tablas(self, headers=headers_control_camaras, data=datos_control_camaras, 
                                        w=450, h=400, tabla_db='tabla_control_camaras_monitoras', id_ref=ref_id)


def mostrar_tablas_anuales_halcyon(self, ref_id):
    """
    Muestra todas las tablas anuales para Halcyon
    """
    # Tabla 1: Equipos de Medición
    datos_equipos_medicion = buscar_datos_db('equipos_medicion', 'Halcyon', 'tipo_camara, equip_type, model, serie', ref_id)
    headers_equipos = [
        ('tipo_camara', 'Cámara'), 
        ('equip_type', 'Tipo Equipo'), 
        ('model', 'Modelo'), 
        ('serie', 'N° Serie')
    ]
    crear_ventanas_emergentes_tablas(self, headers=headers_equipos, data=datos_equipos_medicion, 
                                     w=600, h=400, tabla_db='equipos_medicion', id_ref=ref_id)

    # Tabla 2: Fantomas
    mostrar_tabla_fantomas_anual(self, ref_id)

    # Tabla 3: Indicadores Angulares Gantry
    datos_indicadores_gantry = buscar_datos_db('HC_indicadores_brazo', 'Halcyon', 
                                               'nivel, indicador_consola, diferencia', ref_id)
    headers_indicadores_gantry = [
        ('nivel', 'Nivel'),
        ('indicador_consola', 'Indicador consola'),
        ('diferencia', 'Diferencia')
    ]
    crear_ventanas_emergentes_tablas(self, headers=headers_indicadores_gantry, data=datos_indicadores_gantry, 
                                     w=450, h=350, tabla_db='HC_indicadores_brazo', id_ref=ref_id)

    # Tabla 4: Indicadores Angulares Colimador
    datos_indicadores_colimador = buscar_datos_db('HC_indicadores_colimador', 'Halcyon', 
                                                  'nivel, indicador_consola, diferencia', ref_id)
    headers_indicadores_colimador = [
        ('nivel', 'Nivel'),
        ('indicador_consola', 'Indicador consola'),
        ('diferencia', 'Diferencia')
    ]
    crear_ventanas_emergentes_tablas(self, headers=headers_indicadores_colimador, data=datos_indicadores_colimador, 
                                     w=450, h=350, tabla_db='HC_indicadores_colimador', id_ref=ref_id)

    # Tabla 5: Indicadores Láser
    datos_indicadores_laser = buscar_datos_db('HC_indicadores_laser', 'Halcyon', 
                                             'ubicacion, concordancia_drump, diferencia_isocentro', ref_id)
    headers_indicadores_laser = [
        ('ubicacion', 'Ubicación\nLáser'),
        ('concordancia_drump', 'Concordancia\nDrump-Phantom'),
        ('diferencia_isocentro', 'Diferencia con\nisocentro (mm)')
    ]
    crear_ventanas_emergentes_tablas(self, headers=headers_indicadores_laser, data=datos_indicadores_laser, 
                                     w=500, h=300, tabla_db='HC_indicadores_laser', id_ref=ref_id)

    # Tabla 6: Indicadores Camilla
    datos_indicadores_camilla = buscar_datos_db('HC_indicadores_camilla', 'Halcyon', 
                                                'ubicacion, desplazamiento, medido, diferencia', ref_id)
    headers_indicadores_camilla = [
        ('ubicacion', 'Ubicación\nCamilla (cm)'),
        ('desplazamiento', 'Desplazamiento (cm)'),
        ('medido', 'Medido (cm)'),
        ('diferencia', 'Diferencia (%)')
    ]
    crear_ventanas_emergentes_tablas(self, headers=headers_indicadores_camilla, data=datos_indicadores_camilla, 
                                     w=550, h=450, tabla_db='HC_indicadores_camilla', id_ref=ref_id)

    # Tabla 7: Desplazamiento Isocentro
    datos_desplazamiento = buscar_datos_db('HC_desplazamiento_isocentro_mensual', 'Halcyon', 
                                          'tipo_medicion, valor', ref_id)
    headers_desplazamiento = [
        ('tipo_medicion', 'Tipo de Medición'),
        ('valor', 'Valor (mm)')
    ]
    crear_ventanas_emergentes_tablas(self, headers=headers_desplazamiento, data=datos_desplazamiento, 
                                     w=450, h=300, tabla_db='HC_desplazamiento_isocentro_mensual', id_ref=ref_id)

    # Tabla 8: Velocidad Multiláminas
    datos_velocidad_mlc = buscar_datos_db('HC_velocidad_multilaminas_anual', 'Halcyon', 'velocidad', ref_id)
    headers_velocidad_mlc = [
        ('velocidad', 'Velocidad de multiláminas')
    ]
    crear_ventanas_emergentes_tablas(self, headers=headers_velocidad_mlc, data=datos_velocidad_mlc, 
                                     w=400, h=250, tabla_db='HC_velocidad_multilaminas_anual', id_ref=ref_id)

    # Tabla 9: Precisión Posición Multiláminas
    datos_precision_mlc = buscar_datos_db('HC_precision_posicion_multilaminas_anual', 'Halcyon', 
                                         'posicion, valor_medido, diferencia', ref_id)
    headers_precision_mlc = [
        ('posicion', 'Posición'),
        ('valor_medido', 'Valor medido'),
        ('diferencia', 'Diferencia')
    ]
    crear_ventanas_emergentes_tablas(self, headers=headers_precision_mlc, data=datos_precision_mlc, 
                                     w=450, h=300, tabla_db='HC_precision_posicion_multilaminas_anual', id_ref=ref_id)

    # Tabla 10: Imagen Perfil MLC
    datos_imagen_mlc = buscar_datos_db('HC_imagen_perfil_mlc_anual', 'Halcyon', 'ruta_imagen', ref_id)
    headers_imagen_mlc = [
        ('ruta_imagen', 'Imagen Perfil MLC')
    ]
    crear_ventanas_emergentes_tablas(self, headers=headers_imagen_mlc, data=datos_imagen_mlc, 
                                     w=650, h=500, tabla_db='HC_imagen_perfil_mlc_anual', id_ref=ref_id)

    # Tabla 11: Dosimetría
    datos_dosimetria = buscar_datos_db('HC_dosimetria_anual', 'Halcyon', 
                                      'parametro, valor', ref_id)
    headers_dosimetria = [
        ('parametro', 'Parámetro'),
        ('valor', 'Valor')
    ]
    crear_ventanas_emergentes_tablas(self, headers=headers_dosimetria, data=datos_dosimetria, 
                                     w=500, h=400, tabla_db='HC_dosimetria_anual', id_ref=ref_id)

    # Tabla 12: Linealidad Unidades Monitor
    datos_linealidad_um = buscar_datos_db('HC_linealidad_unidades_monitor_anual', 'Halcyon', 
                                         'unidades_monitor, lectura, linealidad', ref_id)
    headers_linealidad_um = [
        ('unidades_monitor', 'Unidades Monitor'),
        ('lectura', 'Lectura'),
        ('linealidad', 'Linealidad')
    ]
    crear_ventanas_emergentes_tablas(self, headers=headers_linealidad_um, data=datos_linealidad_um, 
                                     w=500, h=350, tabla_db='HC_linealidad_unidades_monitor_anual', id_ref=ref_id)

    # Tabla 13: Tamaños Campo y Dosis
    datos_tamanos_campo = buscar_datos_db('HC_tamanos_campo_radiacion', 'Halcyon', 
                                         'campo_nominal_x, campo_nominal_y, dosis_medida_x, dosis_medida_y', ref_id)
    headers_tamanos_campo = [
        ('campo_nominal_x', 'Campo nominal X'),
        ('campo_nominal_y', 'Campo nominal Y'),
        ('dosis_medida_x', 'Dosis medida X'),
        ('dosis_medida_y', 'Dosis medida Y')
    ]
    crear_ventanas_emergentes_tablas(self, headers=headers_tamanos_campo, data=datos_tamanos_campo, 
                                     w=550, h=350, tabla_db='HC_tamanos_campo_radiacion', id_ref=ref_id)

" ---------------------------------- Funciones auxiliares para mostrar tablas individuales ------------------------------------ "

def mostrar_tabla_equipos_anual(parent, id_ref):
    """Muestra la tabla de equipos de medición para un control anual"""
    conn = Conexion().conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tipo_camara, equip_type, model, serie
        FROM equipos_medicion WHERE ref=?
    """, (id_ref,))
    data = cursor.fetchall()
    conn.close()

    headers = [('tipo_camara', 'Cámara'), ('equip_type', 'Tipo Equipo'), ('model', 'Modelo'), ('serie', 'N° Serie')]
    _mostrar_dialogo_anual(parent, headers, data,  500, 250, 'equipos_medicion', id_ref)

def mostrar_tabla_factor_campo_anual(parent, id_ref, equipo):
    """Muestra todas las tablas de factor de campo por energía"""
    energia_ids = {0: "6 MV", 1: "15 MV", 2: "6 MeV", 3: "9 MeV", 4: "12 MeV", 5: "15 MeV"}
    energias = [0, 1, 2, 3, 4, 5] if equipo == 'Clinac ix' else [0]

    # Crear diálogo con pestañas para múltiples energías
    dlg = QDialog(parent)
    dlg.setWindowTitle("Factor de Campo - Control Anual")
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent.parent.parent.parent
    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))

    layout = QVBoxLayout(dlg)
    
    from PyQt5.QtWidgets import QTabWidget
    tabs = QTabWidget()

    conn = Conexion().conectar()
    cursor = conn.cursor()

    for energia_id in energias:
        cursor.execute("""
            SELECT tamano_campo, factor_campo, factor_campo_esperado, discrepancia
            FROM tabla_factor_campo WHERE ref=? AND id_energia=?
        """, (id_ref, energia_id))
        data = cursor.fetchall()

        if data:
            table = QTableWidget()
            headers = ['Tamaño de campo', 'Factor de campo', 'Factor esperado', 'Discrepancia (%)']
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.setRowCount(len(data))

            for row_idx, row_data in enumerate(data):
                for col_idx, value in enumerate(row_data):
                    item = QTableWidgetItem(str(value) if value is not None else "")
                    item.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row_idx, col_idx, item)
            
            table.resizeColumnsToContents()
            for col in range(table.columnCount()):
                table.setColumnWidth(col, table.columnWidth(col) + 20)
            tabs.addTab(table, energia_ids[energia_id])

    conn.close()
    layout.addWidget(tabs)
    dlg.resize(650, 300)
    dlg.exec_()

def mostrar_tabla_factores_transmision_anual(parent, id_ref, equipo):
    """Muestra todas las tablas de factores de transmisión por energía"""
    energia_ids = {0: "6 MV", 1: "15 MV", 2: "6 MeV", 3: "9 MeV", 4: "12 MeV", 5: "15 MeV"}
    energias = [0, 1, 2, 3, 4, 5] if equipo == 'Clinac ix' else [0]

    dlg = QDialog(parent)
    dlg.setWindowTitle("Factores de Transmisión - Control Anual")
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent.parent.parent.parent
    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))

    layout = QVBoxLayout(dlg)
    
    from PyQt5.QtWidgets import QTabWidget
    tabs = QTabWidget()

    conn = Conexion().conectar()
    cursor = conn.cursor()

    for energia_id in energias:
        cursor.execute("""
            SELECT angulo, factor_transmision, factor_transmision_esperado, discrepancia
            FROM tabla_factores_transmision WHERE ref=? AND id_energia=?
        """, (id_ref, energia_id))
        data = cursor.fetchall()

        if data:
            table = QTableWidget()
            headers = ['Accesorio', 'Factor transmisión', 'Factor esperado', 'Discrepancia (%)']
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.setRowCount(len(data))

            for row_idx, row_data in enumerate(data):
                for col_idx, value in enumerate(row_data):
                    item = QTableWidgetItem(str(value) if value is not None else "")
                    item.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row_idx, col_idx, item)
            
            table.resizeColumnsToContents()
            for col in range(table.columnCount()):
                table.setColumnWidth(col, table.columnWidth(col) + 20)
            tabs.addTab(table, energia_ids[energia_id])

    conn.close()
    layout.addWidget(tabs)
    dlg.resize(530, 300)
    dlg.exec_()

def mostrar_tabla_factores_sobre_eje_anual(parent, id_ref, equipo):
    """Muestra todas las tablas de factores sobre el eje por energía y PDD"""
    energia_ids = {0: "6 MV", 1: "15 MV", 2: "6 MeV", 3: "9 MeV", 4: "12 MeV", 5: "15 MeV"}
    energias = [0, 1, 2, 3, 4, 5] if equipo == 'Clinac ix' else [0]
    ppds = ["PDD (10 x 10)", "PPD (15 x 15)", "PPD (20 x 20)"]

    dlg = QDialog(parent)
    dlg.setWindowTitle("Factores Sobre el Eje - Control Anual")
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent.parent.parent.parent
    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))

    layout = QVBoxLayout(dlg)
    
    from PyQt5.QtWidgets import QTabWidget
    tabs = QTabWidget()

    conn = Conexion().conectar()
    cursor = conn.cursor()

    for energia_id in energias:
        # Crear un widget contenedor para los 3 PPDs de esta energía
        energia_widget = QWidget()
        energia_layout = QVBoxLayout(energia_widget)

        for ppd in ppds:
            cursor.execute("""
                SELECT tam_pdd, profundidad, ppd, ppd_esperado, discrepancia
                FROM tabla_factores_sobre_eje WHERE ref=? AND id_energia=? AND tam_pdd=?
            """, (id_ref, energia_id, ppd))
            data = cursor.fetchall()

            if data:
                from PyQt5.QtWidgets import QLabel
                label = QLabel(f"<b>{ppd}</b>")
                energia_layout.addWidget(label)

                table = QTableWidget()
                headers = ['PDD', 'Profundidad (cm)', ppd, 'PDD esperado', 'Discrepancia (%)']
                table.setColumnCount(len(headers))
                table.setHorizontalHeaderLabels(headers)
                table.setRowCount(len(data))

                for row_idx, row_data in enumerate(data):
                    for col_idx, value in enumerate(row_data):
                        item = QTableWidgetItem(str(value) if value is not None else "")
                        item.setTextAlignment(Qt.AlignCenter)
                        table.setItem(row_idx, col_idx, item)
                
                table.resizeColumnsToContents()
                for col in range(table.columnCount()):
                    table.setColumnWidth(col, table.columnWidth(col) + 20)
                energia_layout.addWidget(table)

        tabs.addTab(energia_widget, energia_ids[energia_id])

    conn.close()
    layout.addWidget(tabs)
    dlg.resize(630, 600)
    dlg.exec_()

def mostrar_tabla_control_camaras_anual(parent, id_ref, equipo):
    """Muestra todas las tablas de control de cámaras monitoras por energía"""
    energia_ids = {0: "6 MV", 1: "15 MV", 2: "6 MeV", 3: "9 MeV", 4: "12 MeV", 5: "15 MeV"}
    energias = [0, 1, 2, 3, 4, 5] if equipo == 'Clinac ix' else [0]

    dlg = QDialog(parent)
    dlg.setWindowTitle("Control de Cámaras Monitoras - Control Anual")
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent.parent.parent.parent
    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))

    layout = QVBoxLayout(dlg)
    
    from PyQt5.QtWidgets import QTabWidget
    tabs = QTabWidget()

    conn = Conexion().conectar()
    cursor = conn.cursor()

    for energia_id in energias:
        cursor.execute("""
            SELECT indicador_medir, valor_medido
            FROM tabla_control_camaras_monitoras WHERE ref=? AND id_energia=?
        """, (id_ref, energia_id))
        data = cursor.fetchall()

        if data:
            table = QTableWidget()
            headers = ['Indicador', 'Valor']
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.setRowCount(len(data))

            for row_idx, row_data in enumerate(data):
                for col_idx, value in enumerate(row_data):
                    item = QTableWidgetItem(str(value) if value is not None else "")
                    item.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row_idx, col_idx, item)
            # Que el tamano de la celda sea del mismo del header:
            table.resizeColumnsToContents()
            for col in range(table.columnCount()):
                table.setColumnWidth(col, table.columnWidth(col) + 20)

            tabs.addTab(table, energia_ids[energia_id])

    conn.close()
    layout.addWidget(tabs)
    dlg.resize(400, 300)
    dlg.exec_()

def mostrar_tabla_fantomas_anual(parent, id_ref):
    """Muestra la tabla de fantomas transformando de columnas a filas"""
    conn = Conexion().conectar()
    cursor = conn.cursor()
    
    # Obtener datos de la base de datos
    cursor.execute("""
        SELECT modelo1, serie1, modelo2, serie2, modelo3, serie3
        FROM HC_fantomas WHERE ref=?
    """, (id_ref,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        # Transformar los datos de columnas a filas
        data = [
            (row[0], row[1]),  # modelo1, serie1
            (row[2], row[3]),  # modelo2, serie2
            (row[4], row[5])   # modelo3, serie3
        ]
        
        headers = [
            ('modelo', 'Modelo'),
            ('serie', 'Serie')
        ]
        
        _mostrar_dialogo_anual(parent, headers, data, 400, 250, 'HC_fantomas', id_ref)

def check_imagen_mlc_subida(id_ref):
    """Verifica si hay una imagen de perfil MLC subida para un control anual"""
    conn = Conexion().conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT imagen_perfil_horiz
        FROM HC_imagen_perfil_mlc_anual WHERE ref=?
    """, (id_ref,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return True
    return False

def mostrar_dosimetria_anual(parent, id_ref):
    """Muestra la tabla de dosimetría anual con formato personalizado"""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Dosimetría Anual")
    grid_layout = QGridLayout(dlg)

    conn = Conexion().conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT  dosis_ref_cgy_um, discrepancia_dosis, tolerancia_dosis,
            calidad_pdd20_10, discrepancia_calidad, tolerancia_calidad,
            simetria_inplane, simetria_crossplane, tolerancia_simetria,
            planicidad_inplane, planicidad_crossplane, tolerancia_planicidad
        FROM HC_dosimetria_anual
        WHERE ref = ?
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
    }

    max_cols = 3
    for idx, res in enumerate(resultados):
        dosis_ref, disc_dosis, tol_dosis = res[0], res[1], res[2]
        calidad, disc_calidad, tol_calidad = res[3], res[4], res[5]
        sim_in, sim_cross, tol_sim = res[6], res[7], res[8]
        plan_in, plan_cross, tol_plan = res[9], res[10], res[11]

        filas = [
            ["Energía Nominal (MV)", "6 MV", "", ""],
            ["Dosis Ref (cGy/UM)", dosis_ref, disc_dosis, tol_dosis],
            ["Calidad (PDD20/10)", calidad, disc_calidad, tol_calidad],
            ["Simetría (%) - Inplane", sim_in, "", tol_sim],
            ["Simetría (%) - Crossplane", sim_cross, "", tol_sim],
            ["Planicidad (%) - Inplane", plan_in, "", tol_plan],
            ["Planicidad (%) - Crossplane", plan_cross, "", tol_plan],
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

            for item in [item_desc, item_val, item_disc, item_tol]:
                item.setTextAlignment(Qt.AlignCenter)

            table.setItem(row, 0, item_desc)
            table.setItem(row, 1, item_val)
            table.setItem(row, 2, item_disc)
            table.setItem(row, 3, item_tol)

            # Metadata correcta para guardarEdicion
            if desc in mapa_columnas:
                for col in (1, 2, 3):  # columnas editables
                    col_name = mapa_columnas[desc].get(col)
                    if col_name:
                        cell_item = table.item(row, col)
                        # Guardar clave compuesta en UserRole (id_ref, energia)
                        cell_item.setData(Qt.UserRole, (id_ref, "6 MV"))
                        # Guardar tabla y columna en UserRole+1
                        cell_item.setData(Qt.UserRole + 1, ("HC_dosimetria_anual", col_name))

        # Ajuste de ancho de columnas
        font_metrics = table.fontMetrics()
        for col in range(table.columnCount()):
            header_text = table.horizontalHeaderItem(col).text()
            table.setColumnWidth(col, font_metrics.horizontalAdvance(header_text) + 70)

        row_grid = idx // max_cols
        col_grid = idx % max_cols
        grid_layout.addWidget(table, row_grid, col_grid)

    row_grid = (len(resultados) // max_cols) + 1  # fila después de las tabla
    dlg.resize(650, 400)
    if getattr(sys, 'frozen', False):
        # Ruta dentro del .exe
        base_path = Path(sys._MEIPASS)
    else:
        # Ruta normal cuando se ejecuta con Python
        base_path = Path(__file__).parent.parent.parent.parent

    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))
    dlg.exec_()

def mostrar_tabla_simple_anual(parent, id_ref, tabla_nombre, headers_config):
    """Muestra una tabla simple sin separación por energías (para Halcyon)"""
    conn = Conexion().conectar()
    cursor = conn.cursor()
    
    # Extraer nombres de columnas de la configuración de headers
    columnas = ', '.join([h[0] for h in headers_config])
    cursor.execute(f"""
        SELECT {columnas}
        FROM {tabla_nombre} WHERE ref=?
    """, (id_ref,))
    data = cursor.fetchall()
    conn.close()

    _mostrar_dialogo_anual(parent, headers_config, data, 500, 350, tabla_nombre, id_ref)

def _mostrar_dialogo_anual(parent, headers, data, w, h, tabla_db, id_ref):
    """Función auxiliar para mostrar un diálogo simple con una tabla"""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Detalle - Control Anual")
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent.parent.parent.parent

    qss_file = base_path / "resources" / "estilo.qss"
    dlg.setStyleSheet(qss_file.read_text(encoding="utf-8"))

    layout = QVBoxLayout(dlg)

    # Tabla
    table = QTableWidget()
    table.setColumnCount(len(headers))
    
    for idx, (db_name, alias) in enumerate(headers):
        item = QTableWidgetItem(alias)
        item.setData(Qt.UserRole, db_name)
        table.setHorizontalHeaderItem(idx, item)

    table.setRowCount(len(data))

    for row_idx, row_data in enumerate(data):
        for col_idx, value in enumerate(row_data):
            if isinstance(value, QWidget):
                table.setCellWidget(row_idx, col_idx, value)
            else:
                if isinstance(value, float):
                    value = f"{value:.3f}"
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setTextAlignment(Qt.AlignCenter)
                if col_idx == 0:
                    item.setData(Qt.UserRole, row_data[0])
                table.setItem(row_idx, col_idx, item)
    
    # Ajustar ancho de columnas al contenido
    table.resizeColumnsToContents()
    for col in range(table.columnCount()):
        table.setColumnWidth(col, table.columnWidth(col) + 20)
    layout.addWidget(table)

    dlg.resize(w, h)
    dlg.exec_()
