"""I3 (PLAN_BRAQUI_IMAGEN_Y_PERFIL_02-09.md, Fase A): `resetear_imagen_ui`
repone las 9 piezas de estado que `subir_imagen`/`_cargar_imagen_pelicula`
asignan -- antes reponía 6: faltaban `pixmap_original` (la fuente del zoom),
`zoom_factor`, y `parametros_creados` + la visibilidad de la interfaz de
análisis (`self.analizar`, `spin_umbral`, `spin_dist`, `label_umbral`,
`label_dist`, `boton_ayuda`). `cancelarbraqui` tenía su PROPIO conjunto,
distinto, ninguno de los dos superconjunto del otro.

Riesgo que el físico nombró: *"esto para mí representa un riesgo de subir
la imagen equivocada"*. Una placa del día anterior visible en pantalla puede
acabar guardada bajo el día actual -- la fila 447 de DP-63, ahora por la vía
de la UI. El test que de verdad importa no es leer los atributos: es
reproducir el gesto exacto que el físico usa (mover la rueda del zoom) y
comprobar que NO revive nada.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

FECHA_FUENTE = "2026-01-01 00:00:00"

# Las 9 piezas [medido, ver PLAN_BRAQUI_IMAGEN_Y_PERFIL_02-09.md §0], con el
# valor que cada una debe tener DESPUÉS de resetear_imagen_ui()/
# cancelarbraqui(). Se listan explícitamente para que las dos pruebas de
# "las 9 a la vez" y "cancelarbraqui deja el mismo estado" iteren sobre la
# MISMA fuente -- si mañana se añade una décima pieza, se agrega aquí y las
# dos pruebas la cubren solas.
PIEZAS_IMAGEN = (
    "imagen_path", "archivo", "pixmap_original", "zoom_factor",
    "parametros_creados", "resultado_label",
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.execute(
        "INSERT INTO TipoCalibracion (id, user, fecha, tipo, serie, "
        "certificado, fecha_cer, intensidad, conversion, activo) "
        "VALUES (1, 'fisico', ?, 'Cambio de fuente', 'SN1', 1.0, ?, 10.0, "
        "1.0, 1)",
        (FECHA_FUENTE, FECHA_FUENTE))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _simular_subir_y_analizar(d, ruta_archivo):
    """Reproduce el estado que dejan `subir_imagen()` + `analizar_imagen()`
    reales, sin ejercitar `analizar_lineas` (necesitaría una imagen
    radiográfica real de disco -- mismo criterio que H1). Cubre las 9
    piezas del censo del plan, más la visibilidad de botones que
    `subir_imagen` deja."""
    d.imagen_path = ruta_archivo
    d.archivo = ruta_archivo
    d.pixmap_original = QPixmap(20, 20)  # no-nulo, como QPixmap(archivo) real
    d.zoom_factor = 0.5  # el valor que pone subir_imagen, no el 1.0 inicial
    d.boton_subir.hide()
    d.boton_aceptar.show()
    d.boton_cancel.show()
    d.boton_zoom_mas.setEnabled(True)
    d.boton_zoom_mas.show()
    d.boton_zoom_menos.setEnabled(True)
    d.boton_zoom_menos.show()

    d.figure.add_subplot(111).plot([1, 2, 3])
    d.canvas.draw()
    d.mostrar_texto([
        "Distancias entre líneas (mm): [10.03, 10.16, 10.03]",
        "Promedio = 10.01 mm",
        "Desviación estándar = 0.11 mm",
    ])

    # _crear_interfaz_parametros() es lo que analizar_imagen() llama la
    # primera vez (parametros_creados es False) -- crea self.analizar,
    # self.boton_ayuda, self.parametros_layout con spin_umbral/spin_dist/
    # label_umbral/label_dist dentro.
    d._crear_interfaz_parametros()
    d.parametros_creados = True

    # actualizar_imagen() es la función real que el zoom/la rueda disparan
    # -- pinta self.label_imagen desde pixmap_original.
    d.actualizar_imagen()


class TestLasNuevePiezasQuedanRepuestas:

    def test_las_nueve_piezas_a_la_vez(self, app, bd_temporal, tmp_path):
        d = PruebaDiariaBraq(_UsuarioFalso())
        archivo_falso = str(tmp_path / "placa.jpg")
        open(archivo_falso, "wb").close()
        _simular_subir_y_analizar(d, archivo_falso)

        # precondición: hay algo que perder en las 9
        assert d.imagen_path is not None
        assert d.archivo is not None
        assert not d.pixmap_original.isNull()
        assert d.zoom_factor == 0.5
        assert d.parametros_creados is True
        assert d.resultado_label.text() != ""

        d.resetear_imagen_ui()

        assert d.imagen_path is None
        assert d.archivo is None
        assert d.pixmap_original.isNull(), (
            "pixmap_original sobrevivía -- es lo que actualizar_imagen() "
            "repinta en cada zoom")
        assert d.zoom_factor == 1.0, (
            "zoom_factor debe volver al 1.0 de imagenUpLoader, no quedar "
            "en el 0.5 que puso subir_imagen")
        assert d.parametros_creados is False, (
            "sin esto, la interfaz de análisis (spin_umbral/analizar) "
            "sigue viva -- 'la interfaz de analizar igual', dijo el físico")
        assert d.resultado_label.text() == ""
        assert d.figure.axes == []

    def test_zoom_tras_limpiar_no_revive_la_placa_anterior(
            self, app, bd_temporal, tmp_path):
        """El síntoma LITERAL del físico: *"la imagen anterior se queda
        pegada"*. No se prueba leyendo un atributo -- se reproduce el
        gesto (la rueda del mouse llama a actualizar_imagen()) y se
        comprueba que el QLabel sigue vacío."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        archivo_falso = str(tmp_path / "placa.jpg")
        open(archivo_falso, "wb").close()
        _simular_subir_y_analizar(d, archivo_falso)
        assert d.label_imagen.pixmap() is not None, (
            "precondición: la placa del 'día anterior' debe estar pintada")

        d.resetear_imagen_ui()
        d.actualizar_imagen()  # el gesto real: mover la rueda del zoom

        pix = d.label_imagen.pixmap()
        assert pix is None or pix.isNull(), (
            "tras limpiar, ni el zoom ni ningún otro gesto pueden hacer "
            "reaparecer la placa del día anterior")

    def test_interfaz_de_analisis_queda_oculta(self, app, bd_temporal, tmp_path):
        d = PruebaDiariaBraq(_UsuarioFalso())
        archivo_falso = str(tmp_path / "placa.jpg")
        open(archivo_falso, "wb").close()
        _simular_subir_y_analizar(d, archivo_falso)
        assert not d.analizar.isHidden(), "precondición: el botón debe estar visible"

        d.resetear_imagen_ui()

        # setParent(None) también oculta -- isHidden() es fiable sin
        # necesitar un show() del top-level (isVisible() no lo es: da
        # False siempre que la ventana nunca se mostró, [medido]).
        assert d.analizar.isHidden()
        assert d.boton_ayuda.isHidden()
        assert d.spin_umbral.isHidden()
        assert d.spin_dist.isHidden()

    def test_uploader_vuelve_a_su_estado_inicial(self, app, bd_temporal, tmp_path):
        d = PruebaDiariaBraq(_UsuarioFalso())
        archivo_falso = str(tmp_path / "placa.jpg")
        open(archivo_falso, "wb").close()
        _simular_subir_y_analizar(d, archivo_falso)
        assert d.boton_subir.isHidden(), "precondición: subir_imagen lo oculta"

        d.resetear_imagen_ui()

        assert not d.boton_subir.isHidden(), (
            "'Seleccionar Imagen' debe reaparecer -- antes solo lo hacía "
            "cancelarbraqui")
        assert d.boton_aceptar.isHidden()
        assert d.boton_cancel.isHidden()
        assert d.boton_zoom_mas.isHidden()
        assert d.boton_zoom_menos.isHidden()
        assert d.label_imagen.text() == "Subir imagen"


class TestCancelarbraquiDelegaEnResetearImagenUi:

    def _instantanea(self, d):
        return {
            "imagen_path": d.imagen_path,
            "archivo": d.archivo,
            "pixmap_es_null": d.pixmap_original.isNull(),
            "zoom_factor": d.zoom_factor,
            "parametros_creados": d.parametros_creados,
            "resultado_label_texto": d.resultado_label.text(),
            "boton_subir_oculto": d.boton_subir.isHidden(),
            "boton_aceptar_oculto": d.boton_aceptar.isHidden(),
            "analizar_oculto": d.analizar.isHidden(),
        }

    def test_cancelarbraqui_deja_el_mismo_estado_que_resetear_imagen_ui(
            self, app, bd_temporal, tmp_path):
        archivo_falso = str(tmp_path / "placa.jpg")
        open(archivo_falso, "wb").close()

        d_reset = PruebaDiariaBraq(_UsuarioFalso())
        _simular_subir_y_analizar(d_reset, archivo_falso)
        d_reset.resetear_imagen_ui()
        snap_reset = self._instantanea(d_reset)

        d_cancelar = PruebaDiariaBraq(_UsuarioFalso())
        _simular_subir_y_analizar(d_cancelar, archivo_falso)
        d_cancelar.cancelarbraqui()
        snap_cancelar = self._instantanea(d_cancelar)

        assert snap_reset == snap_cancelar, (
            "'Limpiar' (resetear_imagen_ui) y 'Cancelar' (cancelarbraqui) "
            "deben dejar EXACTAMENTE el mismo estado -- dos caminos "
            "distintos, un solo limpiador")


class TestPixmapOriginalSigueALaPeliculaCargada:

    def test_cargar_pelicula_desde_bd_fija_pixmap_del_tamano_correcto(
            self, app, bd_temporal):
        """[medido] antes, `_cargar_imagen_pelicula` reponía `imagen_path`/
        `archivo` pero NUNCA `pixmap_original` -- hacer zoom sobre una
        película recién cargada de la BD mostraba la del día anterior."""
        import io as iomod
        from PIL import Image

        buffer = iomod.BytesIO()
        Image.new("RGB", (37, 51), color=(200, 10, 10)).save(buffer, format="JPEG")
        blob = buffer.getvalue()

        d = PruebaDiariaBraq(_UsuarioFalso())
        # placa "del día anterior", de OTRO tamaño -- si pixmap_original no
        # se repusiera, seguiría siendo esta.
        d.pixmap_original = QPixmap(999, 999)

        d._cargar_imagen_pelicula(blob)

        assert not d.pixmap_original.isNull()
        assert (d.pixmap_original.width(), d.pixmap_original.height()) != (999, 999), (
            "pixmap_original debe venir de LA película que se acaba de "
            "cargar, no seguir siendo la del día anterior")
