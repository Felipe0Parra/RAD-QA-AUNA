"""LF4 (PLAN_CONTRATO_COMPLETO_19-08.md §4.6.1): defecto vivo introducido
por LF, no preexistente. `braq_mensual.py::addsomething::consulta`
llamaba a `filtro_activo(nombre_tabla)` incondicionalmente, decidiendo por
TABLA algo que depende de la SELECTIVIDAD del WHERE (DA-47). `uid="id"`
(TipoCalibracion) nombra UNA fila física -- filtrar ahí no oculta una fila
de una lista, vacía el formulario de una calibración anulada que el físico
abrió a propósito. `uid="ref"` (SistemaMedicion/CondicionesMedicion)
selecciona un BLOQUE -- ahí sí debe filtrar.

Rojo-antes-que-verde en las DOS direcciones (§4.6.1): revertir a
`filtro_activo(nombre_tabla)` sin condición debe romper
`test_identidad_anulada_sigue_poblando_el_formulario`; quitar el filtro
por completo debe romper
`test_clave_de_bloque_anulada_no_puebla_el_formulario`. Ninguna de las dos
solas certifica el fix -- hace falta que ambas convivan.

Segundo defecto, PREEXISTENTE, hallado escribiendo estos tests y corregido
en la misma tarea: la llamada era `consulta(nombre_tabla, ref)` contra la
firma `consulta(nombre_tabla, uid=uid, ref=ref)` -- `ref` entraba
POSICIONALMENTE en el hueco de `uid`. Dentro de `consulta`, `uid` nunca
valía "id"/"ref" sino el entero, con dos consecuencias: (1) el `uid != "id"`
de arriba era SIEMPRE cierto, así que el arreglo de LF4 nacía inerte; y (2)
el SQL salía `WHERE 5 = ?` con 5 atado como parámetro -- una TAUTOLOGÍA que
casa todas las filas de la tabla, y `fetchall()[0]` devolvía la primera que
diera SQLite, no la pedida. `TestLaClaveSeleccionaLaFilaPedida` lo fija en
las dos ramas: sin él, los tests de arriba certificarían un arreglo que en
producción no se ejecuta nunca.
"""
import os
import sqlite3

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLineEdit, QWidget

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
import services.anulacion as anulacion_mod
from data.ManejoDatos.conection import Conexion
from services.anulacion import filtro_activo
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq


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


@pytest.fixture
def sistema_medicion_anulable(monkeypatch, bd_temporal):
    """Adelanta el estado que dejará MI1 sobre `SistemaMedicion`.

    Hoy `SistemaMedicion` está en `EXCEPCIONES_INVENTARIO` como
    "PENDIENTE-LF: rama braquiterapia" -- NO está en `TABLAS_ANULABLES`,
    así que `_asegurar_activo_bloque_qc()` no le añade la columna `activo`
    y `filtro_activo('SistemaMedicion')` devuelve `""`. Con el filtro
    evaluando a cadena vacía, la rama `uid != "id"` sería indistinguible
    de no tener filtro y estos tests pasarían en verde sin probar nada.

    Por eso se simula la activación de MI1 en vez de esperarla: se añade la
    columna a mano (la migración real solo corre al construir `Conexion()`,
    antes de que este monkeypatch pudiera aplicarse) y se amplía la lista
    blanca. Así se verifica HOY el punto 3 del protocolo de LF4 -- "que MI1
    no encuentre este sitio desprotegido" -- y queda demostrado que el sitio
    no necesita ningún cambio de código el día que MI1 llegue.

    Se parchean DOS nombres porque los dos módulos leen la lista de forma
    distinta: `services.anulacion` la lee dinámicamente desde
    `filtro_activo` (basta con el módulo), mientras que `load.py` hizo
    `from services.anulacion import TABLAS_ANULABLES` y quedó con una
    referencia propia al frozenset -- `encontrar_columnas` la consulta para
    decidir si excluye `activo` de la lista de columnas del SELECT.
    """
    con = sqlite3.connect(bd_temporal)
    con.execute("ALTER TABLE SistemaMedicion ADD COLUMN activo INTEGER DEFAULT 1")
    con.commit()
    con.close()

    ampliado = anulacion_mod.TABLAS_ANULABLES | {"SistemaMedicion"}
    monkeypatch.setattr(anulacion_mod, "TABLAS_ANULABLES", ampliado)
    monkeypatch.setattr(load_mod, "TABLAS_ANULABLES", ampliado)
    return bd_temporal


def _insertar(ruta_bd, tabla, **campos):
    con = sqlite3.connect(ruta_bd)
    cols = list(campos)
    marcas = ", ".join("?" * len(cols))
    con.execute(f"INSERT INTO {tabla} ({', '.join(cols)}) VALUES ({marcas})",
                list(campos.values()))
    con.commit()
    con.close()


def _tipo_calibracion(ruta_bd, id_, user, activo):
    _insertar(ruta_bd, "TipoCalibracion", id=id_, user=user,
              fecha="01/01/2024", tipo=1.0, serie=f"SN{id_}",
              certificado=1.0, fecha_cer="01/01/2025",
              intensidad=1.0, conversion=1.0, activo=activo)


def _sistema_medicion(ruta_bd, ref, user, activo=None):
    campos = dict(ref=ref, user=user, fecha="01/01/2024", modelo="M1",
                  serie_cp="C1", calibracion=1.0, modelo_elec="E1",
                  serie_ele="S1", electrometro=1.0, t0=22.0, p0=101.325,
                  h0=50.0)
    if activo is not None:
        campos["activo"] = activo
    _insertar(ruta_bd, "SistemaMedicion", **campos)


def _braq_mensual_pelado(prueba, nombre_campo):
    """`PruebaMensualBraq` sin su __init__ pesado -- solo el atributo que
    `addsomething` va a rellenar vía `getattr(self, line_name)`."""
    obj = PruebaMensualBraq.__new__(PruebaMensualBraq)
    QWidget.__init__(obj)
    setattr(obj, nombre_campo, QLineEdit())
    return obj, pd.DataFrame({
        "widget_type": ["QLineEdit"],
        "prueba": [prueba],
        "nombres": [nombre_campo],
    })


class TestFiltroActivoNoEsVacioParaTipoCalibracion:
    """Premisa que el comentario falso negaba -- fijarla evita que el
    defecto vuelva disfrazado de optimización ("total, no hace nada")."""

    def test_filtro_activo_tipocalibracion_no_es_vacio(self):
        assert filtro_activo("TipoCalibracion") != ""


class TestLaClaveSeleccionaLaFilaPedida:
    """El `WHERE` tiene que nombrar la COLUMNA (`id`/`ref`), no el valor.

    Con `consulta(nombre_tabla, ref)` el SQL salía `WHERE <entero> = ?` con
    ese mismo entero atado: cierto para toda fila de la tabla. Estos dos
    tests son los únicos que distinguen "filtra bien" de "el arreglo de LF4
    ni siquiera se ejecuta": ambas ramas leen la fila EQUIVOCADA cuando hay
    más de una candidata, aunque todas estén activas."""

    def test_uid_id_devuelve_la_fila_de_ese_id(self, app, bd_temporal):
        _tipo_calibracion(bd_temporal, 3, "primera_calibracion", activo=1)
        _tipo_calibracion(bd_temporal, 5, "calibracion_pedida", activo=1)
        obj, df = _braq_mensual_pelado("tipo", "campo_user")

        obj.addsomething(QWidget(), df, "tipo", "TipoCalibracion", "id", 5)

        assert obj.campo_user.text() == "calibracion_pedida"

    def test_uid_ref_devuelve_el_bloque_de_ese_ref(self, app, bd_temporal):
        _tipo_calibracion(bd_temporal, 7, "dummy", activo=1)
        _tipo_calibracion(bd_temporal, 9, "dummy", activo=1)
        _sistema_medicion(bd_temporal, ref=7, user="bloque_ajeno")
        _sistema_medicion(bd_temporal, ref=9, user="bloque_pedido")
        obj, df = _braq_mensual_pelado("sistema", "campo_user")

        obj.addsomething(QWidget(), df, "sistema", "SistemaMedicion", "ref", 9)

        assert obj.campo_user.text() == "bloque_pedido"


class TestIdentidadAnuladaSiguePoblando:
    """uid="id": filtrar aquí vaciaría el formulario de una calibración
    anulada abierta a propósito -- el defecto real (LF4)."""

    def test_identidad_anulada_sigue_poblando_el_formulario(self, app, bd_temporal):
        _tipo_calibracion(bd_temporal, 5, "fis_anulado", activo=0)
        obj, df = _braq_mensual_pelado("tipo", "campo_user")

        obj.addsomething(QWidget(), df, "tipo", "TipoCalibracion", "id", 5)

        assert obj.campo_user.text() == "fis_anulado"


class TestClaveDeBloqueAnuladaNoPuebla:
    """uid="ref": selecciona un bloque (N generaciones) -- si la única
    generación disponible está anulada, el filtro debe excluirla.

    Corren sobre `sistema_medicion_anulable`, que adelanta MI1 (ver el
    docstring de la fixture): sin él `filtro_activo('SistemaMedicion')` es
    `""` hoy y estos tests no distinguirían nada."""

    def test_clave_de_bloque_anulada_no_puebla_el_formulario(
            self, app, sistema_medicion_anulable):
        bd = sistema_medicion_anulable
        assert filtro_activo("SistemaMedicion") != "", (
            "la fixture no activó el filtro -- el test sería vacío")
        _tipo_calibracion(bd, 7, "dummy", activo=1)
        _sistema_medicion(bd, ref=7, user="fis_anulado", activo=0)
        obj, df = _braq_mensual_pelado("sistema", "campo_user")

        obj.addsomething(QWidget(), df, "sistema", "SistemaMedicion", "ref", 7)

        assert obj.campo_user.text() == ""

    def test_clave_de_bloque_activa_si_puebla_el_formulario(
            self, app, sistema_medicion_anulable):
        """Caso sano: el filtro no rompe la lectura normal de un bloque
        vigente -- solo excluye generaciones anuladas."""
        bd = sistema_medicion_anulable
        _tipo_calibracion(bd, 8, "dummy", activo=1)
        _sistema_medicion(bd, ref=8, user="fis_vigente", activo=1)
        obj, df = _braq_mensual_pelado("sistema", "campo_user")

        obj.addsomething(QWidget(), df, "sistema", "SistemaMedicion", "ref", 8)

        assert obj.campo_user.text() == "fis_vigente"

    def test_generacion_vigente_gana_a_la_anulada_del_mismo_bloque(
            self, app, sistema_medicion_anulable):
        """El caso real del bloque: la anulada y la vigente conviven bajo
        el mismo `ref`. Sin filtro, `fetchall()[0]` entrega la anulada por
        ser la primera insertada."""
        bd = sistema_medicion_anulable
        _tipo_calibracion(bd, 9, "dummy", activo=1)
        _sistema_medicion(bd, ref=9, user="generacion_superada", activo=0)
        _sistema_medicion(bd, ref=9, user="generacion_vigente", activo=1)
        obj, df = _braq_mensual_pelado("sistema", "campo_user")

        obj.addsomething(QWidget(), df, "sistema", "SistemaMedicion", "ref", 9)

        assert obj.campo_user.text() == "generacion_vigente"
