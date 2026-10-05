"""PI.9 (PLAN_POSICION_INICIAL_BRAQUI_01-10.md, DP-139, DA-82 D1 «reemplazo completo»): el código viejo de posición inicial ya no existe.

CAUSA. Tras PI.6 la página vieja ya no se mostraba, pero se seguía CONSTRUYENDO dentro de cada mensual de braquiterapia (y de cada
`CalRedundanteFuente`, que hereda de `PruebaMensualBraq`), con sus consultas a la BD, y su ruta de escritura (`actualizar_desplazamiento_en_db`,
un UPDATE de `CondicionesMedicion.desplazamiento_ini`) seguía viva: código muerto con escrituras vivas es el tipo de cosa que reaparece.

Lo que se garantiza, cada cosa con su prueba:
  1. el árbol de PRODUCCIÓN (todo `.py` fuera de `tests/` y de los entornos) no nombra ni una vez la clase vieja, su señal ni sus dos métodos de
     escritura, ni escribe `SET desplazamiento_ini`. Se cuenta el TEXTO, no solo el AST: un comentario o una cadena que los nombre también
     cuenta, porque es lo que reaparece. El barrido tiene un piso de archivos leídos y un control (Trampa 8: sin ellos pasaría en vacío);
  2. el mensual de braquiterapia y la calibración redundante se construyen SIN crear ninguna otra página (espía sobre `PruebaBasico.__init__`:
     cada uno una sola vez) y sin el atributo `posicionamiento` ni los dos métodos;
  3. lo que PI.9 NO toca sigue igual: `desplazamiento_ini` nace en `None`, `normalizar_fechas_db` corre una vez al construir y sigue existiendo
     `actualizar_ref_bd` (el método que venía justo después de lo retirado: un recorte por líneas que se pasara lo borraría);
  4. el guardado escribe `desplazamiento_ini` como siempre: `None` en «Cambio de fuente» y «No Aplica» en la calibración redundante y en el
     control mensual (`guardar_DB`, que PI.9 no toca).
La huella de estado del formulario contra HEAD (§6.5), el inventario de clases y métodos del árbol antes y después y los ids de pruebas recogidas
antes y después son scripts del anexo (`pi9_compuerta_huella.py`, `pi9_compuerta_inventario.py`, `pi9_ids.py`)."""
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import data.ManejoDatos.load  # noqa: F401  (ciclo de importaciones preexistente)
from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico
from ui.paginasControles.PruebasDiarias.braquiterapia import CalRedundanteFuente
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq
from test_t2_braqui_guarda_la_serie import _combo_con_calibracion, _EspiaGuardado, _pantalla_braqui_para_guardar

RAIZ = Path(__file__).resolve().parents[1]
EXCLUIDOS = {".venv", "build", "dist", "tests", "__pycache__", ".git", "node_modules", ".pytest_cache"}
RETIRADOS = re.compile(r"PosicionamientoInicial|desplazamientoReady|actualizar_desplazamiento|SET\s+desplazamiento_ini")
PISO_DE_ARCHIVOS = 100          # el árbol de producción tiene hoy 133 archivos: si el barrido lee menos de 100, no está barriendo el árbol


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _archivos_de_produccion():
    for carpeta, subcarpetas, archivos in os.walk(RAIZ):
        subcarpetas[:] = [s for s in subcarpetas if s not in EXCLUIDOS]
        for nombre in archivos:
            if nombre.endswith(".py"):
                yield Path(carpeta) / nombre


def _menciones(texto):
    return [(texto.count("\n", 0, m.start()) + 1, m.group(0)) for m in RETIRADOS.finditer(texto)]


# ------------------------------------------------------------------------------------------------------ 1. el árbol de producción

class TestElArbolDeProduccionNoLoNombra:
    def test_ningun_archivo_de_produccion_nombra_la_clase_la_senal_ni_los_metodos_retirados(self):
        leidos, halladas = 0, []
        for ruta in _archivos_de_produccion():
            leidos += 1
            for linea, nombre in _menciones(ruta.read_text(encoding="utf-8", errors="replace")):
                halladas.append(f"{ruta.relative_to(RAIZ)}:{linea} {nombre}")
        assert leidos >= PISO_DE_ARCHIVOS, f"el barrido solo leyó {leidos} archivos: no está barriendo el árbol de producción"
        assert not halladas, "el código viejo de posición inicial reapareció en producción:\n  " + "\n  ".join(halladas[:12])

    def test_el_detector_ve_los_cuatro_nombres_y_el_update(self):
        """Control del barrido: sobre una cadena que los trae, el detector los encuentra; si no, la prueba de arriba pasaría en vacío."""
        texto = ("class PosicionamientoInicial(PruebaBasico):\n    desplazamientoReady = pyqtSignal(object)\n"
                 "    def actualizar_desplazamiento(self, v): pass\n    def actualizar_desplazamiento_en_db(self, d): pass\n"
                 "    cursor.execute('UPDATE CondicionesMedicion\\n SET   desplazamiento_ini = ?')\n")
        encontrados = [n for _, n in _menciones(texto)]
        assert encontrados.count("PosicionamientoInicial") == 1 and encontrados.count("desplazamientoReady") == 1
        assert encontrados.count("actualizar_desplazamiento") == 2          # el método y su variante `_en_db`
        assert any(re.match(r"SET\s+desplazamiento_ini", n) for n in encontrados)

    def test_el_barrido_no_cuenta_los_tests_ni_los_entornos(self):
        rutas = {str(r.relative_to(RAIZ)) for r in _archivos_de_produccion()}
        assert "ui/paginasControles/PruebasMensuales/braq_mensual.py" in rutas and "ui/paginasControles/PruebasDiarias/braquiterapia.py" in rutas
        assert not any(r.startswith(("tests/", ".venv/", "build/")) for r in rutas)


# -------------------------------------------------------------------------------- 2. el mensual no construye ninguna otra página

def _construccion(clase, monkeypatch):
    construidas = []
    original = PruebaBasico.__init__

    def espia(self, *args, **kwargs):
        construidas.append(type(self).__name__)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(PruebaBasico, "__init__", espia)
    return clase(_UsuarioFalso()), construidas


class TestElMensualNoConstruyeOtraPagina:
    @pytest.mark.parametrize("clase", [PruebaMensualBraq, CalRedundanteFuente], ids=lambda c: c.__name__)
    def test_se_construye_una_sola_pagina(self, app, bd_temporal, monkeypatch, clase):
        formulario, construidas = _construccion(clase, monkeypatch)
        assert construidas == [clase.__name__], f"construir {clase.__name__} creó otras páginas: {construidas}"
        assert not hasattr(formulario, "posicionamiento")

    @pytest.mark.parametrize("clase", [PruebaMensualBraq, CalRedundanteFuente], ids=lambda c: c.__name__)
    def test_ya_no_tiene_los_dos_metodos_de_escritura(self, clase):
        assert not hasattr(clase, "actualizar_desplazamiento")
        assert not hasattr(clase, "actualizar_desplazamiento_en_db")


# ------------------------------------------------------------------------------------------ 3. lo que PI.9 no toca sigue igual

class TestLoQueNoSeToca:
    def test_desplazamiento_ini_nace_en_none(self, app, bd_temporal):
        assert PruebaMensualBraq(_UsuarioFalso()).desplazamiento_ini is None

    def test_normalizar_fechas_corre_una_vez_al_construir_y_actualizar_ref_bd_sigue_ahi(self, app, bd_temporal, monkeypatch):
        llamadas = []
        original = PruebaMensualBraq.normalizar_fechas_db
        monkeypatch.setattr(PruebaMensualBraq, "normalizar_fechas_db", lambda self: (llamadas.append(1), original(self))[1])
        PruebaMensualBraq(_UsuarioFalso())
        assert llamadas == [1], "normalizar_fechas_db debe correr exactamente una vez al construir el mensual"
        assert callable(PruebaMensualBraq.actualizar_ref_bd) and callable(PruebaMensualBraq.guardar_DB)


# ------------------------------------------------------------------------------------ 4. el guardado escribe lo mismo que antes

class TestElGuardadoEscribeDesplazamientoComoSiempre:
    @pytest.mark.parametrize("tipo,esperado", [("Cambio de fuente", None), ("Calibración Redundante", "No Aplica"), ("Control Mensual", "No Aplica")])
    def test_desplazamiento_ini_que_guardar_db_manda_al_servicio(self, app, monkeypatch, tipo, esperado):
        espia = _EspiaGuardado()
        obj = _pantalla_braqui_para_guardar(app, monkeypatch, serie_cp_combo=_combo_con_calibracion(17, "A092535"),
                                            serie_ele_combo=_combo_con_calibracion(79, "002343"), ref_bd_spy=espia)
        obj.desplazamiento_ini = None                      # como lo deja `PruebaMensualBraq.__init__`
        if tipo == "Calibración Redundante":
            obj.es_calibracion_redundante = True
        elif tipo == "Control Mensual":
            from PyQt5.QtWidgets import QPushButton
            obj.pri_cal = QPushButton()
            obj.pri_cal.setCheckable(True)
            obj.pri_cal.setChecked(True)
        obj.guardar_DB()
        assert len(espia.llamadas) == 1, "guardar_DB no llamó al servicio de guardado exactamente una vez"
        args, _ = espia.llamadas[0]
        assert args[2] == tipo
        assert args[-2] == esperado, f"{tipo}: desplazamiento_ini = {args[-2]!r} (siempre fue {esperado!r})"
