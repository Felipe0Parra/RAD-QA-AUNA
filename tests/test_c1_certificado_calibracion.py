"""C1 (PLAN_ACTUALIZACION_HALCYON_CERT_PERMISOS_06-08.md §3.5): ver el
certificado de calibración (PDF o imagen) sin ambigüedad.

La tubería de almacenamiento/apertura ya funcionaba (bytes crudos + detección
`%PDF` + visor del sistema). Lo que faltaba, y esto cierra:

1. `clasificar_certificado` -- la celda decía "Imagen subida" tanto para un
   certificado real como para las 12 filas de basura (residuo del off-by-one
   corregido en `aa767fd`), y "Sin imagen" para NULL -- ahora distingue
   "PDF" / "Imagen" / "Sin certificado válido" por bytes mágicos, sin tocar
   ningún dato (DA-02/DA-28).
2. Afordancia: tooltip en la celda + doble clic reconoce "PDF" también, no
   solo el literal viejo "Imagen subida".
3. Vista previa honesta al subir un .pdf: antes `QPixmap(archivo)` con un PDF
   da un pixmap nulo, sin pintar nada y sin aviso -- ahora se muestra el
   nombre del archivo y un mensaje de que se guardará el PDF.

Hallazgo verificado contra producción durante esta tarea (no estaba en el
plan): las 12 filas de basura NO son bytes `b"1.0"`/`b"0.0"` literales --
SQLite las guardó con afinidad `REAL` (`typeof='real'`), así que
`imagen_certificado` llega como `float` de Python, no `bytes`.
`clasificar_certificado` debe filtrar el tipo antes de indexar o revienta
con `TypeError` sobre exactamente esas 12 filas reales.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QLineEdit, QTableWidget,
    QTableWidgetItem, QWidget,
)

import data.ManejoDatos.conection as conection_mod
import ui.paginasGuia.equipos as equipos_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasGuia.equipos import Config, clasificar_certificado
from ui.paginasControles.PruebasDiarias import PruebasDiarias as pruebas_diarias_mod
from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioActualFalso:
    _nombre = "Físico de Prueba"
    _usuario = "accastellanos"


BLOB_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\nresto del archivo pdf sintetico..."
BLOB_JPG = b"\xff\xd8\xff\xe0no es un jpg real pero trae la firma correcta"
BLOB_PNG = b"\x89PNG\r\n\x1a\nresto del archivo png sintetico"
BLOB_BMP = b"BMresto del archivo bmp sintetico"
BLOB_JUNK_BYTES = b"XYZ"  # basura que sí llegara como bytes, por si acaso


def _mock_messagebox(monkeypatch):
    monkeypatch.setattr(equipos_mod.QMessageBox, "information",
                         staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(equipos_mod.QMessageBox, "warning",
                         staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(equipos_mod.QMessageBox, "critical",
                         staticmethod(lambda *a, **k: None))


def _insertar_equipo(ruta, imagen_certificado, activo=1):
    import sqlite3
    con = sqlite3.connect(ruta)
    cur = con.execute("""
        INSERT INTO equipos (equip_type, model, serie, calibr_fact, calibr_fact2,
            fecha_calibr, fabricante, t_cal, p_cal, h_cal, v1, activo, vigente,
            imagen_certificado)
        VALUES ('Cámara de ionización', 'N31010', '1825', 0.3045, NULL,
            '16/03/2026', 'PTW', 22.0, 101.325, 50.0, 300.0, ?, 1, ?)
    """, (activo, imagen_certificado))
    id_equipo = cur.lastrowid
    con.commit()
    con.close()
    return id_equipo


class TestClasificarCertificado:
    """Función pura: sin Qt, sin BD."""

    def test_pdf(self):
        assert clasificar_certificado(BLOB_PDF) == "PDF"

    def test_jpg(self):
        assert clasificar_certificado(BLOB_JPG) == "Imagen"

    def test_png(self):
        assert clasificar_certificado(BLOB_PNG) == "Imagen"

    def test_bmp(self):
        assert clasificar_certificado(BLOB_BMP) == "Imagen"

    def test_none_es_sin_certificado_valido(self):
        assert clasificar_certificado(None) == "Sin certificado válido"

    def test_bytes_de_basura_sin_firma_conocida(self):
        assert clasificar_certificado(BLOB_JUNK_BYTES) == "Sin certificado válido"

    def test_float_real_de_produccion_no_revienta(self):
        """El hallazgo real: SQLite guardó las 12 filas de basura como REAL
        (typeof='real'), no como bytes -- blob[:4] sobre un float lanzaría
        TypeError sin el filtro isinstance."""
        assert clasificar_certificado(1.0) == "Sin certificado válido"
        assert clasificar_certificado(0.0) == "Sin certificado válido"


class TestCargartablaEtiquetaPorContenidoReal:
    def _obj(self):
        obj = Config.__new__(Config)
        QWidget.__init__(obj)
        obj.table = QTableWidget()
        return obj

    def _item_certificado(self, obj, id_equipo):
        col = obj.table.columnCount() - 1
        for row in range(obj.table.rowCount()):
            item = obj.table.item(row, col)
            if item is not None and item.data(Qt.UserRole) == id_equipo:
                return item
        return None

    def test_pdf_se_etiqueta_pdf_con_tooltip(self, app, bd_temporal):
        id_equipo = _insertar_equipo(bd_temporal, BLOB_PDF)
        obj = self._obj()
        Config.cargartabla(obj)

        item = self._item_certificado(obj, id_equipo)
        assert item.text() == "PDF"
        assert item.toolTip() == "Doble clic para abrir el certificado"

    def test_imagen_se_etiqueta_imagen_con_tooltip(self, app, bd_temporal):
        id_equipo = _insertar_equipo(bd_temporal, BLOB_JPG)
        obj = self._obj()
        Config.cargartabla(obj)

        item = self._item_certificado(obj, id_equipo)
        assert item.text() == "Imagen"
        assert item.toolTip() == "Doble clic para abrir el certificado"

    def test_basura_real_se_etiqueta_sin_certificado_valido_sin_tooltip(
            self, app, bd_temporal):
        """Reproduce exactamente la corrupción real: `activo`/`vigente`
        (0 o 1) escrito en la columna del BLOB -- SQLite lo guarda como
        REAL, no bytes."""
        id_equipo = _insertar_equipo(bd_temporal, 1.0)
        obj = self._obj()
        Config.cargartabla(obj)

        item = self._item_certificado(obj, id_equipo)
        assert item.text() == "Sin certificado válido"
        assert item.toolTip() == ""

    def test_sin_blob_se_etiqueta_sin_certificado_valido(self, app, bd_temporal):
        id_equipo = _insertar_equipo(bd_temporal, None)
        obj = self._obj()
        Config.cargartabla(obj)

        item = self._item_certificado(obj, id_equipo)
        assert item.text() == "Sin certificado válido"

    def test_encabezados_no_cambian_la_columna_certificado_sigue_siendo_la_ultima(
            self, app, bd_temporal):
        _insertar_equipo(bd_temporal, BLOB_PDF)
        obj = self._obj()
        Config.cargartabla(obj)

        headers = [obj.table.horizontalHeaderItem(c).text()
                   for c in range(obj.table.columnCount())]
        assert headers[-1] == "Certificado"
        assert headers[-2] == "Activo"


class TestAbrirCertificado:
    def _obj_con_item(self, texto, id_equipo=1):
        obj = Config.__new__(Config)
        QWidget.__init__(obj)
        obj.table = QTableWidget(1, 1)
        item = QTableWidgetItem(texto)
        item.setData(Qt.UserRole, id_equipo)
        obj.table.setItem(0, 0, item)
        return obj, item

    def test_doble_clic_sobre_pdf_llega_al_visor_del_sistema(
            self, app, bd_temporal, monkeypatch):
        id_equipo = _insertar_equipo(bd_temporal, BLOB_PDF)
        obj, item = self._obj_con_item("PDF", id_equipo)

        llamadas = []
        import subprocess
        monkeypatch.setattr(subprocess, "Popen",
                             lambda *a, **k: llamadas.append(a))
        monkeypatch.setattr(equipos_mod.sys, "platform", "linux")

        Config.abrir_certificado(obj, item)

        assert len(llamadas) == 1
        assert llamadas[0][0][0] == "xdg-open"
        assert llamadas[0][0][1].endswith(".pdf")

    def test_doble_clic_sobre_imagen_abre_el_dialogo_de_visor(
            self, app, bd_temporal, monkeypatch):
        id_equipo = _insertar_equipo(bd_temporal, BLOB_JPG)
        obj, item = self._obj_con_item("Imagen", id_equipo)

        llamadas = []
        # visor.exec_() es un diálogo MODAL -- en offscreen se colgaría
        # esperando un clic que nunca llega (trampa ya documentada del
        # proyecto). Se mockea exec_ para que solo registre que se llegó
        # a abrir el visor.
        monkeypatch.setattr(QDialog, "exec_", lambda self: llamadas.append(self) or 0)

        Config.abrir_certificado(obj, item)

        assert len(llamadas) == 1

    def test_doble_clic_sobre_sin_certificado_valido_no_abre_nada(
            self, app, bd_temporal, monkeypatch):
        id_equipo = _insertar_equipo(bd_temporal, 1.0)
        obj, item = self._obj_con_item("Sin certificado válido", id_equipo)

        def _conexion_no_debe_llamarse():
            raise AssertionError("no debe consultarse la BD para una fila sin certificado válido")
        monkeypatch.setattr(equipos_mod, "Conexion",
                             lambda: _conexion_no_debe_llamarse())

        Config.abrir_certificado(obj, item)  # no debe lanzar ni consultar nada


class TestSubirImagenVistaPrevia:
    def _obj(self):
        obj = PruebaBasico.__new__(PruebaBasico)
        QWidget.__init__(obj)
        # `imagenUpLoader` parenta label_imagen/scroll_area bajo el widget
        # que retorna -- sin guardar una referencia Python a ese widget, el
        # padre C++ se destruye y `self.label_imagen` queda un puntero
        # muerto ("wrapped C/C++ object... has been deleted").
        obj._widget_imagen = obj.imagenUpLoader(analisis=False)
        return obj

    def _mockear_seleccion(self, monkeypatch, ruta):
        monkeypatch.setattr(
            pruebas_diarias_mod.QFileDialog, "getOpenFileName",
            staticmethod(lambda *a, **k: (ruta, "")))

    def test_pdf_no_intenta_pixmap_y_muestra_nombre_del_archivo(
            self, app, tmp_path, monkeypatch):
        archivo = tmp_path / "certificado.pdf"
        archivo.write_bytes(BLOB_PDF)
        obj = self._obj()
        self._mockear_seleccion(monkeypatch, str(archivo))

        obj.subir_imagen(analisis=False)

        assert obj.pixmap_original.isNull()
        texto = obj.label_imagen.text()
        assert "certificado.pdf" in texto
        assert "PDF" in texto
        # DA-18: sin símbolos de correcto/incorrecto/advertencia
        for simbolo in ("✓", "✗", "⚠️"):
            assert simbolo not in texto

    def test_imagen_normal_sigue_usando_pixmap(self, app, tmp_path, monkeypatch):
        from PyQt5.QtGui import QImage
        archivo = tmp_path / "foto.png"
        QImage(4, 4, QImage.Format_RGB32).save(str(archivo), "PNG")
        obj = self._obj()
        self._mockear_seleccion(monkeypatch, str(archivo))

        obj.subir_imagen(analisis=False)

        assert not obj.pixmap_original.isNull()


class TestGuardadoByteAByteIdentico:
    """Protocolo §3.5, punto 4: subir un .pdf deja el blob idéntico al
    fichero de origen -- ninguna recodificación en el camino."""

    def _obj_editando(self, id_equipo, ruta_pdf):
        obj = Config.__new__(Config)
        QWidget.__init__(obj)
        obj.user_id = _UsuarioActualFalso()
        obj.cargartabla = lambda: None

        obj.tipo = QComboBox()
        obj.tipo.addItem("Cámara de ionización")
        obj.modelo = QLineEdit("N31010")
        obj.serie = QLineEdit("1825")
        obj.calib_factor = QLineEdit("0.3045")
        obj.calib_date = QLineEdit("16/03/2026")
        obj.fabricante = QLineEdit("PTW")
        obj.t_cal = QLineEdit("22.0")
        obj.p_cal = QLineEdit("101.325")
        obj.h_cal = QLineEdit("50.0")
        obj.v1_cal = QLineEdit("300.0")
        obj.sel_activo = QCheckBox()
        obj.sel_activo.setChecked(True)
        obj.imagen_path = ruta_pdf

        obj.table = QTableWidget(1, 1)
        item = QTableWidgetItem()
        item.setData(Qt.UserRole, id_equipo)
        obj.table.setItem(0, 0, item)
        obj.table.setCurrentCell(0, 0)
        return obj

    def test_blob_guardado_es_identico_byte_a_byte_al_pdf_de_origen(
            self, app, bd_temporal, tmp_path, monkeypatch):
        contenido_real = BLOB_PDF + b"\x00\x01binario-de-verdad" * 50
        archivo = tmp_path / "certificado_real.pdf"
        archivo.write_bytes(contenido_real)

        id_equipo = _insertar_equipo(bd_temporal, None)
        _mock_messagebox(monkeypatch)
        obj = self._obj_editando(id_equipo, str(archivo))

        Config.guardarCambios(obj)

        import sqlite3
        con = sqlite3.connect(bd_temporal)
        fila = con.execute(
            "SELECT imagen_certificado FROM equipos WHERE model=? AND serie=? "
            "ORDER BY id DESC LIMIT 1", ("N31010", "1825")).fetchone()
        con.close()

        assert fila[0] == contenido_real
