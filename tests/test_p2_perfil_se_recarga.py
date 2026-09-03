"""P2 (PLAN_BRAQUI_IMAGEN_Y_PERFIL_02-09.md, Fase B): `G1` ya reconstruye el
TEXTO del informe al cargar un día con análisis guardado; el CANVAS seguía
vacío -- `H1` hizo que `resetear_imagen_ui` deje la figura limpia con
`canvas.draw()`, así que la pantalla mostraba un recuadro vacío junto a un
informe con números, sugiriendo que no había análisis cuando sí lo había.

`_recargar_perfil_intensidad` repinta la curva llamando de nuevo a
`analizar_lineas` con los parámetros de `P1` (o 1.0/40 -- los defaults de
los spins -- si la fila es histórica y no los registró), descartando el
texto que devuelve: el informe en pantalla sigue siendo el reconstruido
desde las columnas, el dato guardado.

**Obstáculo, no anticipado por el plan escrito**: el protocolo de
verificación original pedía "una película real" para afirmar
`len(self.figure.axes) == 3` contra el pipeline REAL de detección de
picos/marcadores. No existe en el repo ninguna imagen radiográfica de
placa apta para ese pipeline (los tests previos que tocan esta misma
pantalla -- `test_h1_reseteo_imagen_ui_limpia_todo.py`,
`test_i3_estado_imagen_completo.py` -- ya habían llegado a la misma
conclusión y la anotan explícitamente: *"sin ejercitar `analizar_lineas`,
necesitaría una imagen radiográfica real de disco"*). Se sigue el mismo
criterio aquí: se monkeypatchea `analizar_lineas` (el nombre importado en
el módulo `braquiterapia`, no la función original) simulando lo que
`graficar_resultados` deja -- 3 ejes sobre `self.figure` -- y se verifican
los PARÁMETROS con los que `_recargar_perfil_intensidad` la invoca, que es
la lógica que este plan realmente agrega (la detección de picos en sí no
cambió)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
import ui.paginasControles.PruebasDiarias.braquiterapia as braq_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

FECHA_FUENTE = "2020-01-01 00:00:00"


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


def _llenar_campos_numericos(d, valor="1.0"):
    for campo in ("line_1_rep_act_ci", "line_1_exp_act_ci",
                  "line_1_cyc_dummy", "line_1_cyc_rad"):
        getattr(d, campo).setText(valor)


def _crear_jpeg_real(tmp_path, nombre="placa.jpg"):
    from PIL import Image
    ruta = str(tmp_path / nombre)
    Image.new("RGB", (37, 51), color=(200, 10, 10)).save(ruta, format="JPEG")
    return ruta


def _fake_analizar_lineas(llamadas, texto_falso, canvas_axes=3):
    """Sustituto de `analizar_lineas`: registra los kwargs de la llamada,
    deja `canvas_axes` ejes en la figura (como `graficar_resultados` real)
    y devuelve un texto DISTINTO del reconstruido -- para probar que se
    descarta."""
    def _fake(**kwargs):
        llamadas.append(kwargs)
        canvas = kwargs.get("canvas")
        if canvas is not None:
            canvas.figure.clear()
            for i in range(canvas_axes):
                canvas.figure.add_subplot(canvas_axes, 1, i + 1)
            canvas.draw()
        return texto_falso
    return _fake


class TestPerfilSeRecargaConParametrosGuardados:

    def test_recalcula_con_los_parametros_guardados_y_descarta_el_texto(
            self, app, bd_temporal, monkeypatch, tmp_path):
        ruta_jpeg = _crear_jpeg_real(tmp_path)

        # Guardar un día con película, análisis y parámetros no-default.
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 7, 20))
        _llenar_campos_numericos(d)
        d.archivo = ruta_jpeg
        d.imagen_path = ruta_jpeg
        d._crear_interfaz_parametros()
        d.spin_umbral.setValue(1.4)
        d.spin_dist.setValue(55)
        d.mostrar_texto([
            "Distancias entre líneas(mm): [10.03, 10.16, 10.03]",
            "Promedio = 10.01 mm", "Desviación estándar = 0.11 mm"])
        d.ordenar_botones('braqui', False, "Diario")

        # Abrir el registro en una pantalla NUEVA (simula el cambio de día).
        llamadas = []
        monkeypatch.setattr(
            braq_mod, "analizar_lineas",
            _fake_analizar_lineas(llamadas, "TEXTO_FALSO_QUE_DEBE_DESCARTARSE"))

        d2 = PruebaDiariaBraq(_UsuarioFalso())
        d2.date_box.setDate(QDate(2026, 7, 20))

        assert len(llamadas) == 1, "analizar_lineas debía llamarse una sola vez"
        kwargs = llamadas[0]
        assert kwargs["imagen_path"] == d2.imagen_path
        assert kwargs["umbral_relativo"] == pytest.approx(1.4)
        assert kwargs["distancia_minima"] == 55
        assert kwargs["canvas"] is d2.canvas

        assert len(d2.figure.axes) == 3, "el canvas debía quedar repintado"

        texto_mostrado = d2.resultado_label.text()
        assert "TEXTO_FALSO_QUE_DEBE_DESCARTARSE" not in texto_mostrado, (
            "el texto que analizar_lineas devuelve NO debe pintarse -- "
            "el informe en pantalla es el reconstruido de las columnas")
        assert "10.01" in texto_mostrado and "0.11" in texto_mostrado

        assert d2.aviso_perfil_default.isHidden(), (
            "con parámetros guardados no corresponde ningún aviso")

    def test_dia_sin_parametros_guardados_usa_los_defaults_de_los_spins_y_avisa(
            self, app, bd_temporal, monkeypatch, tmp_path):
        """Fila histórica (guardada antes de que existiera P1): tiene
        película y análisis, pero `umbral_relativo`/`distancia_minima`
        quedaron NULL -- se recalcula con 1.0/40 (los defaults reales de
        `spin_umbral`/`spin_dist`, no el 20 interno de `analizar_lineas`,
        [medido] en DP-80) y la pantalla avisa que son por defecto."""
        ruta_jpeg = _crear_jpeg_real(tmp_path)

        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 7, 21))
        _llenar_campos_numericos(d)
        d.archivo = ruta_jpeg
        d.imagen_path = ruta_jpeg
        # Sin _crear_interfaz_parametros(): no hay spin_umbral/spin_dist,
        # igual que una fila guardada antes de que P1 existiera.
        assert not hasattr(d, "spin_umbral")
        d.mostrar_texto([
            "Distancias entre líneas(mm): [9.51, 9.49]",
            "Promedio = 9.50 mm", "Desviación estándar = 0.20 mm"])
        d.ordenar_botones('braqui', False, "Diario")

        llamadas = []
        monkeypatch.setattr(
            braq_mod, "analizar_lineas",
            _fake_analizar_lineas(llamadas, "TEXTO_FALSO"))

        d2 = PruebaDiariaBraq(_UsuarioFalso())
        d2.date_box.setDate(QDate(2026, 7, 21))

        assert len(llamadas) == 1
        assert llamadas[0]["umbral_relativo"] == pytest.approx(1.0)
        assert llamadas[0]["distancia_minima"] == 40

        assert not d2.aviso_perfil_default.isHidden(), (
            "sin parámetros guardados debe avisar que se usaron los "
            "valores por defecto")
        assert "por defecto" in d2.aviso_perfil_default.text().lower()

    def test_sin_pelicula_no_llama_analizar_lineas_ni_avisa(
            self, app, bd_temporal, monkeypatch):
        """Un día sin película (nunca se subió imagen) no tiene nada que
        recalcular -- ni análisis guardado ni imagen que pasarle a
        `analizar_lineas`."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 7, 22))
        _llenar_campos_numericos(d)
        d.ordenar_botones('braqui', False, "Diario")

        llamadas = []
        monkeypatch.setattr(
            braq_mod, "analizar_lineas",
            _fake_analizar_lineas(llamadas, "TEXTO_FALSO"))

        d2 = PruebaDiariaBraq(_UsuarioFalso())
        d2.date_box.setDate(QDate(2026, 7, 22))

        assert llamadas == []
        assert d2.aviso_perfil_default.isHidden()


class TestImg1SigueVivoYNoAbortaLaCargaDelDia:
    """IMG-1 (metadata()/detección de picos falla con DPI fuera de
    200/300/600) sigue sin cerrarse -- con P2 pasa a ser alcanzable en
    CUALQUIER cambio de día sobre una placa afectada, no solo al pulsar
    "Analizar". El recálculo va en try/except propio: canvas vacío + aviso,
    nunca una excepción que aborte el resto de la carga del día."""

    def test_analizar_lineas_lanza_deja_canvas_vacio_aviso_y_termina_de_cargar(
            self, app, bd_temporal, monkeypatch, tmp_path):
        ruta_jpeg = _crear_jpeg_real(tmp_path)

        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 7, 23))
        _llenar_campos_numericos(d)
        d.archivo = ruta_jpeg
        d.imagen_path = ruta_jpeg
        d._crear_interfaz_parametros()
        d.spin_umbral.setValue(1.4)
        d.spin_dist.setValue(55)
        d.mostrar_texto([
            "Distancias entre líneas(mm): [10.03, 10.16, 10.03]",
            "Promedio = 10.01 mm", "Desviación estándar = 0.11 mm"])
        d.ordenar_botones('braqui', False, "Diario")

        def _fake_que_revienta(**kwargs):
            raise ValueError("No se encontró punto en abajo_izq")

        monkeypatch.setattr(braq_mod, "analizar_lineas", _fake_que_revienta)

        d2 = PruebaDiariaBraq(_UsuarioFalso())
        # No debe propagar -- si lo hiciera, este setDate ya habría fallado.
        d2.date_box.setDate(QDate(2026, 7, 23))

        assert len(d2.figure.axes) == 0, "el canvas debe quedar vacío"
        assert not d2.aviso_perfil_default.isHidden()
        assert "no fue posible" in d2.aviso_perfil_default.text().lower()

        # El resto del día sí se terminó de cargar.
        assert float(d2.line_1_rep_act_ci.text()) == 1.0
        assert d2.date_box.date() == QDate(2026, 7, 23)
