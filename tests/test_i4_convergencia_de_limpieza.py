"""I4 (PLAN_BRAQUI_IMAGEN_Y_PERFIL_02-09.md, Fase A): los dos caminos de
limpieza -- el botón "Limpiar" (`clean_info`) y rotar a un día sin registro
(`cargar_dailytest_desde_db`) -- deben dejar EXACTAMENTE el mismo estado. `I2`
ya unificó la implementación (`_restablecer_formulario_diario` como única
definición); este archivo es la garantía de que la unificación no se puede
desarmar sin que la suite lo note.

No compara cada camino contra una lista escrita a mano -- COMPARA LOS DOS
CAMINOS ENTRE SÍ. Si mañana alguien limpia algo en un camino y no en el otro
(exactamente como pasó entre `clean_info` y `_limpiar_widgets_diaria` antes
de `I0`-`I2`), la instantánea de un lado difiere de la del otro y la suite
se pone roja nombrando la pieza exacta que quedó descolgada.

Extiende `test_i2_limpiador_canonico.py` (que ya comparaba fueradeservicio/
botones/botón Añadir/botones_ordenados/df_lines) en tres direcciones que I2
no cubría:
  - el COLOR efectivo de los botones Funciona/No funciona (no solo la
    propiedad `estado`) -- reutiliza la técnica de `test_i1_botones_color_
    por_defecto.py` (cargar `estilo.qss` de verdad, muestrear el pixmap).
  - las piezas de estado de imagen que el censo derivado de `I5`
    (`test_h8_tripwire_estado_imagen_no_sobrevive.py::ATRIBUTOS_ESTADO_
    IMAGEN`, 6 nombres) encuentra -- NO escritas a mano aquí, para no
    repetir el error que `I5` ya corrigió una vez.
  - `figure`/`canvas` y la visibilidad de los 5 botones del uploader de
    imagen, que el censo de `I5` NO puede ver (los primeros los puebla
    `analizar_lineas` vía el parámetro `canvas=`, no una asignación
    `self.x = ...`; los segundos son llamadas `.hide()`/`.show()`, no
    asignaciones -- el AST de I5 solo mira asignaciones a propósito). Se
    comparan aparte, con su propio poblado en `_ensuciar` -- un hallazgo
    de la revisión adversarial de este mismo archivo (03-09): sin esto,
    una regresión como la que motivó H1/DP-63 ("el canvas seguía
    mostrando el render anterior") habría pasado por verde.

Halcyon queda FUERA del parametrize, con el motivo ya establecido en `I0`/
`I1`/`I2`/`I3`: su `initDATA` no llama a `init_data()`/`storeDailyTests()`,
así que una instancia real no tiene `df_bnt_funciona`/`botones_finales` --
llamar `clean_info()` o `cargar_dailytest_desde_db()` revienta con
AttributeError por una razón AJENA a este plan, no por una divergencia entre
los dos caminos.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq
from ui.paginasControles.PruebasDiarias.seiscientos import PruebaDiaria600
from ui.paginasControles.PruebasDiarias.IX import PruebaDiariaIX
# I4 reutiliza el censo derivado de I5 -- NO se vuelve a escribir a mano la
# lista de piezas de estado de imagen (sería repetir el error que I5 cerró).
import test_h8_tripwire_estado_imagen_no_sobrevive as _h8

FECHA_FUENTE = "2020-01-01 00:00:00"
FECHA_SIN_REGISTRO = QDate(2027, 8, 20)

RUTA_QSS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "resources", "estilo.qss")


@pytest.fixture(scope="module")
def app():
    instancia = QApplication.instance() or QApplication([])
    # Sin esto ningún color [estado=...] de estilo.qss se resuelve --
    # ver test_i1_botones_color_por_defecto.py.
    with open(RUTA_QSS, encoding="utf-8") as f:
        instancia.setStyleSheet(f.read())
    return instancia


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
    # Solo braqui la necesita (CAMPOS_DERIVADOS_DIARIA); inocua para iX/600.
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


def _color_efectivo(app, boton):
    boton.style().unpolish(boton)
    boton.style().polish(boton)
    boton.update()
    app.processEvents()
    pixmap = boton.grab()
    imagen = pixmap.toImage()
    return QColor(imagen.pixel(imagen.width() // 2, imagen.height() // 2)).getRgb()[:3]


def _valor_comparable_de_imagen(d, atributo):
    """Cada pieza de imagen necesita su propia extracción para ser
    comparable entre dos instancias DISTINTAS -- comparar los objetos
    Qt directamente no sirve: dos `QPixmap()` vacíos independientes NO son
    `==` entre sí [medido], y dos `QLabel` de instancias distintas nunca lo
    son por identidad."""
    valor = getattr(d, atributo)
    if atributo == "pixmap_original":
        return valor.isNull()
    if atributo == "resultado_label":
        return valor.text()
    return valor


def _ensuciar(d):
    """Deja el formulario en un estado que SOLO una limpieza completa puede
    revertir -- igual que `test_i2`, más el estado de imagen cuando la
    clase lo tiene (hoy, solo braqui)."""
    primer_fun = getattr(d, list(d.df_bnt_funciona)[0])
    primer_nofun = getattr(d, list(d.df_bnt_nofunciona)[0])
    primer_fun.setChecked(True)
    d.cambiar_estilo(primer_fun, primer_nofun)

    d.fueradeservicio = True
    d._texto_original_btn_add = "Agregar"
    d.btn_add.setText("FUERA DE SERVICIO")

    if getattr(d, "botones_ordenados", None) is not None:
        d.botones_ordenados.append(("x", "y"))

    if d.df_lines:
        getattr(d, list(d.df_lines)[0]).setText("9.9")
    if hasattr(d, "observaciones"):
        d.observaciones.setText("algo escrito ayer")

    # `subir_imagen` es un método HEREDADO por las 4 diarias (vive en la
    # base) -- existe siempre, se use o no. `label_imagen` en cambio solo
    # lo crea `imagenUpLoader()`, y SOLO braqui la llama en su `initUI`
    # (iX/600 no tienen uploader de imagen) -- es el hasattr correcto para
    # "esta instancia de verdad tiene estado de imagen que ensuciar".
    if hasattr(d, "label_imagen"):
        # Poblar estado de imagen sin pasar por QFileDialog/analizar_lineas
        # -- mismo criterio que test_i3 (imagen radiográfica real no hace
        # falta para probar limpieza de estado de UI).
        from PyQt5.QtGui import QPixmap
        d.imagen_path = "placa_de_ayer.jpg"
        d.archivo = "placa_de_ayer.jpg"
        d.pixmap_original = QPixmap(20, 20)
        d.zoom_factor = 0.5
        d._crear_interfaz_parametros()
        d.parametros_creados = True
        d.mostrar_texto(["Promedio = 10.01 mm", "Desviación estándar = 0.11 mm"])

        # HALLAZGO de la revisión adversarial (03-09): sin esto, `figure`
        # nunca queda con contenido real, y el censo de I5 (derivado por
        # AST de subir_imagen/_cargar_imagen_pelicula/mostrar_texto) NUNCA
        # puede ver `figure`/`canvas` -- los puebla `analizar_lineas` vía
        # el parámetro `canvas=`, no una asignación `self.x = ...` dentro
        # de esas tres funciones. [medido, con un experimento reproducible
        # de la revisión] sin este poblado y su comparación en
        # `_instantanea`, el test seguía en verde aunque `resetear_imagen_
        # ui` dejara de hacer `figure.clear()` -- exactamente la regresión
        # que motivó H1/DP-63 ("el canvas seguía mostrando el render
        # anterior"). Mismo patrón que `_poblar_estado_de_imagen` en
        # test_h8_tripwire_estado_imagen_no_sobrevive.py.
        d.figure.add_subplot(111).plot([1, 2, 3])
        d.canvas.draw()

        # HALLAZGO de la revisión adversarial: `subir_imagen` también deja
        # la visibilidad de los 5 botones del uploader en un estado
        # concreto -- reproducirla aquí (y compararla en `_instantanea`)
        # es lo único que de verdad prueba que los dos caminos restauran
        # el uploader igual, en vez de darlo por sentado porque ambos
        # llaman a la misma función hoy (la misma suposición que ya
        # falló una vez, DP-79, antes de I2/I3).
        d.boton_subir.hide()
        d.boton_aceptar.show()
        d.boton_cancel.show()
        d.boton_zoom_mas.setEnabled(True)
        d.boton_zoom_mas.show()
        d.boton_zoom_menos.setEnabled(True)
        d.boton_zoom_menos.show()


def _instantanea(app, d):
    snap = {
        "fueradeservicio": d.fueradeservicio,
        "btn_add_texto": d.btn_add.text(),
        "btn_add_habilitado": d.btn_add.isEnabled(),
        "btn_add_objectName": d.btn_add.objectName(),
        "botones_finales": set(d.botones_finales),
        "botones_ordenados": list(getattr(d, "botones_ordenados", []) or []),
        "observaciones": d.observaciones.text() if hasattr(d, "observaciones") else None,
    }
    for i, (fun, nofun) in enumerate(zip(d.df_bnt_funciona, d.df_bnt_nofunciona)):
        btn_fun = getattr(d, fun)
        btn_nofun = getattr(d, nofun)
        snap[f"boton_{i}_checked_fun"] = btn_fun.isChecked()
        snap[f"boton_{i}_checked_nofun"] = btn_nofun.isChecked()
        snap[f"boton_{i}_color_fun"] = _color_efectivo(app, btn_fun)
        snap[f"boton_{i}_color_nofun"] = _color_efectivo(app, btn_nofun)
    for nombre in d.df_lines:
        snap[f"df_lines::{nombre}"] = getattr(d, nombre).text()
    # I5: el censo de imagen se DERIVA, no se escribe aquí -- las clases
    # que no tienen la pieza (iX/600) simplemente no la aportan a la
    # instantánea ("por ausencia del atributo, no por una lista de
    # nombres de clase", tal como pide el plan).
    for atributo in _h8.ATRIBUTOS_ESTADO_IMAGEN:
        if hasattr(d, atributo):
            snap[f"imagen::{atributo}"] = _valor_comparable_de_imagen(d, atributo)

    # `figure`/`canvas` quedan FUERA del censo derivado de I5 a propósito
    # (los puebla `analizar_lineas` vía el parámetro `canvas=`, no una
    # asignación dentro de subir_imagen/_cargar_imagen_pelicula/
    # mostrar_texto -- el AST no puede verlos) -- se comparan aparte,
    # igual que test_h8 los comprueba a mano con `figure.axes == []`.
    # HALLAZGO de la revisión adversarial: sin esto el test no detectaba
    # que `resetear_imagen_ui` dejara de repintar el canvas (H1/DP-63).
    if hasattr(d, "figure"):
        snap["imagen::figure_num_ejes"] = len(d.figure.axes)

    # HALLAZGO de la revisión adversarial: la visibilidad de los 5
    # botones del uploader (que `subir_imagen` deja en un estado concreto)
    # no estaba en ningún lado de esta instantánea -- I4 daba por sentada
    # la convergencia ahí sin comprobarla.
    for nombre_boton in ("boton_subir", "boton_aceptar", "boton_cancel",
                         "boton_zoom_mas", "boton_zoom_menos"):
        if hasattr(d, nombre_boton):
            boton = getattr(d, nombre_boton)
            snap[f"uploader::{nombre_boton}_oculto"] = boton.isHidden()
            snap[f"uploader::{nombre_boton}_habilitado"] = boton.isEnabled()
    return snap


CASOS = [
    (PruebaDiariaBraq, True),
    (PruebaDiaria600, False),
    (PruebaDiariaIX, False),
]


@pytest.mark.parametrize("clase,imagenes", CASOS)
class TestLosDosCaminosConvergenEnTodo:

    def test_limpiar_y_rotar_a_dia_vacio_convergen_en_todo(
            self, app, bd_temporal, clase, imagenes):
        d_boton = clase(_UsuarioFalso())
        _ensuciar(d_boton)
        d_boton.clean_info(imagenes=imagenes)
        snap_boton = _instantanea(app, d_boton)

        d_rotar = clase(_UsuarioFalso())
        _ensuciar(d_rotar)
        d_rotar.cargar_dailytest_desde_db(FECHA_SIN_REGISTRO)
        snap_rotar = _instantanea(app, d_rotar)

        campos_derivados = set(getattr(clase, "CAMPOS_DERIVADOS_DIARIA", {}))
        claves_derivadas = {f"df_lines::{c}" for c in campos_derivados}

        assert set(snap_boton) == set(snap_rotar), (
            f"{clase.__name__}: las dos instantáneas no midieron lo mismo "
            f"-- una de las dos rutas ganó o perdió un atributo respecto "
            f"a la otra (p. ej. estado de imagen presente en una sola)")

        diferencias = {
            clave: (snap_boton[clave], snap_rotar[clave])
            for clave in snap_boton
            if clave not in claves_derivadas and snap_boton[clave] != snap_rotar[clave]
        }
        assert not diferencias, (
            f"{clase.__name__}: 'Limpiar' y rotar a un día sin registro "
            f"dejaron estados DISTINTOS -- (limpiar, rotar) por clave: "
            f"{diferencias}")

    def test_campo_derivado_es_la_unica_diferencia_legitima(
            self, app, bd_temporal, clase, imagenes):
        campos_derivados = getattr(clase, "CAMPOS_DERIVADOS_DIARIA", {})
        if not campos_derivados:
            pytest.skip(f"{clase.__name__} no declara CAMPOS_DERIVADOS_DIARIA")

        d_boton = clase(_UsuarioFalso())
        _ensuciar(d_boton)
        d_boton.clean_info(imagenes=imagenes)

        d_rotar = clase(_UsuarioFalso())
        _ensuciar(d_rotar)
        d_rotar.cargar_dailytest_desde_db(FECHA_SIN_REGISTRO)

        for campo in campos_derivados:
            texto_boton = getattr(d_boton, campo).text()
            texto_rotar = getattr(d_rotar, campo).text()
            assert texto_boton == "", (
                f"{clase.__name__}.{campo}: 'Limpiar' no debe recalcular "
                f"campos derivados -- quedó {texto_boton!r}")
            assert texto_rotar != "", (
                f"{clase.__name__}.{campo}: rotar a un día sin registro "
                f"SÍ debe recalcularlo -- quedó vacío")
