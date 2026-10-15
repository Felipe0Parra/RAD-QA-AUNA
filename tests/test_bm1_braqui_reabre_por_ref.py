"""BM.1 (PLAN_GUARDADO_BRAQUI_MENSUAL_15-10.md): reabrir una calibración de braquiterapia trae SUS cinco tablas hijas
(por `ref`), y pasar a una fecha sin calibración no hereda medidas de otro día.

CAUSA medida (§0.2 del plan, `DP-44`/`DP-158`): al cambiar la fecha, `braq_mensual.py` elegía la calibración por (fecha, tipo) pero
leía `SistemaMedicion`, `CondicionesMedicion`, `ResultadosActividad`, `MaximosCamaras` y `LecturasMaximos` SOLO por la fecha. Con dos
calibraciones el mismo día (cambio de fuente y redundante: 27-09-2026, refs 37 y 39) la tabla de máximos recibía las 20 filas de las dos
y quedaba con cada posición repetida; al guardar, el índice parcial `(ref, posicion)` la rechazaba con
`UNIQUE constraint failed: MaximosCamaras.ref, MaximosCamaras.posicion`. Y pasar a una fecha sin calibración dejaba las dos tablas y la
actividad del monitor con las medidas del otro día.

Todo aquí corre con la pantalla REAL (`PruebaMensualBraq` / `CalRedundanteFuente`), sobre COPIAS de la BD del físico
(`Rebuild_08-10-2026`; nunca se abre la de referencia), moviendo la fecha como lo haría el físico. Lo esperado sale de la BD con SQL
independiente de los cargadores (una foto tomada con `sqlite3` de la copia intacta, antes de que Qt toque nada).

Organización: (a) y (b) la secuencia del físico con el guardado completo; (c) los cinco días con dos calibraciones, en las dos páginas;
(d) cambiar de fecha (tablas en blanco) y `None -> None` (lo escrito a mano sobrevive); (e) la gráfica de máximos; (f) una calibración
con menos filas no deja restos de la anterior; (g) los días con un solo control se ven como se guardaron; (h) reabrir y volver a guardar
sin tocar nada; (t) tripwires: una sola conexión de la fecha, ninguna hija se lee por fecha, una sola definición de las posiciones.
"""
import ast
import gc
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QCoreApplication, QDate, QDateTime, QEvent
from PyQt5.QtSql import QSqlDatabase, QSqlQuery
from PyQt5.QtWidgets import QApplication, QDateEdit, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.load import guardar_resultado_CambioFuente
import ui.paginasControles.PruebasMensuales.braq_mensual as braq_mensual_mod
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq
from ui.paginasControles.PruebasDiarias.braquiterapia import CalRedundanteFuente
from services.combo_equipo_guardado import serie_de_item
from services.etiqueta_equipo import serie_de_etiqueta
from services.lecturas_del_maximo import VOLTAJES_POR_DEFECTO, lecturas_por_voltaje
from _bd_referencia import BD_REBUILD_08_10

RAIZ = Path(__file__).resolve().parent.parent
BRAQ_MENSUAL = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "braq_mensual.py"
FORMATO = "yyyy-MM-dd HH:mm:ss"
CAMBIO, REDUNDANTE, MENSUAL = "Cambio de fuente", "Calibración Redundante", "Control Mensual"

# Las 10 posiciones estándar, ESCRITAS AQUÍ A MANO (no importadas): la prueba no puede depender de la constante que verifica.
POSICIONES_ESTANDAR = ["127.5", "127", "126.5", "126", "125.5", "125", "124.5", "124", "123.5", "123"]

# Calibraciones vigentes de la copia del 08-10 (§0.4 del plan, d01/d05 del anexo): refs 16, 23, 25, 29, 32, 35 y 36 son controles
# mensuales ÚNICOS en su día; los cinco días con dos calibraciones son estos:
REFS_SOLOS = [16, 23, 25, 29, 32, 35, 36]
DIAS_CON_DOS = [
    # (fecha ISO, tipo de la casilla elegida, ref que debe abrirse)
    ("2025-09-27", CAMBIO, 14),
    ("2025-09-27", REDUNDANTE, 15),        # ref 15: fecha guardada como DD-MM-YYYY, sin hora
    ("2025-12-29", REDUNDANTE, 24),        # el ref 17 del mismo día tiene el tipo vacío: no se puede elegir
    ("2026-04-26", CAMBIO, 28),
    ("2026-04-26", REDUNDANTE, 34),
    ("2026-06-26", CAMBIO, 30),
    ("2026-06-26", REDUNDANTE, 33),
    ("2026-09-27", CAMBIO, 37),
    ("2026-09-27", REDUNDANTE, 39),
]
# Fechas SIN ninguna calibracion en la copia del 08-10 (las que hay: ver REFS_SOLOS y DIAS_CON_DOS), SIEMPRE pasadas: una fecha de prueba que pudiera
# ser «hoy» no emitiria `dateChanged` (DP-94).
DIA_SIN_CALIBRACION = "2026-03-15"
HIJAS = ("SistemaMedicion", "CondicionesMedicion", "MaximosCamaras", "LecturasMaximos", "ResultadosActividad")
VIGENTE = "(activo IS NULL OR activo = 1)"


# ---------------------------------------------------------------------------------------------------------------------------
# Infraestructura
# ---------------------------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _reset_qtsql_default_connection():
    """Trampa 4: la conexion por omision de QtSql se cachea por PROCESO; hay que soltarla entre pruebas."""
    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")


def _soltar_qt_antes_de_escribir():
    """Suelta la conexion QtSql por omision de la pantalla justo antes de pulsar «Anadir». Medido por Opus el 15-10: con una conexion Qt ABIERTA en el
    mismo proceso, el guardado (que escribe con el `sqlite3` de Python) dice «guardado» pero un lector posterior -otra conexion o un proceso nuevo- puede
    no verlo: son dos copias de SQLite en un proceso en Linux, cuyos candados POSIX no se ven entre si (la familia de DP-147). Es un artefacto de ESTE
    entorno de pruebas, no de la app [inferido: en Windows los candados son por manija y si se ven; lo confirma la puerta de salida]. Soltarla hace la
    prueba determinista y deja que la relectura desde otro proceso compruebe que lo guardado esta de verdad en el archivo."""
    _reset_qtsql_default_connection()


@pytest.fixture(autouse=True)
def dialogos(monkeypatch):
    """Trampa 2: ningun QMessageBox real bajo offscreen. Registra (tipo, titulo, texto); `question` responde Si."""
    registro = []

    def _hacer(tipo):
        def _f(*a, **k):
            registro.append((tipo, str(a[1]) if len(a) > 1 else "", str(a[2]) if len(a) > 2 else ""))
            return QMessageBox.Yes if tipo == "question" else QMessageBox.Ok
        return staticmethod(_f)

    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, _hacer(tipo))
    return registro


@pytest.fixture(autouse=True)
def _grafica_espia(monkeypatch):
    """`graficar_resultados` (matplotlib) no interviene en lo que se prueba; se registra lo que recibiria."""
    llamadas = []
    monkeypatch.setattr(braq_mensual_mod, "graficar_resultados", lambda canvas, **k: llamadas.append(k))
    return llamadas


@pytest.fixture(autouse=True)
def _limpieza_global():
    _reset_qtsql_default_connection()
    yield
    if conection_mod.Conexion._instance is not None:
        try:
            conection_mod.Conexion._instance.con.close()
        except Exception:
            pass
    conection_mod.Conexion._instance = None
    _reset_qtsql_default_connection()


def _copiar_bd(origen, destino):
    """Copia la BD y, si existen, su -wal / -shm (regla de sesion: nunca abrir la original)."""
    shutil.copy2(origen, destino)
    for sufijo in ("-wal", "-shm"):
        aux = Path(str(origen) + sufijo)
        if aux.exists():
            shutil.copy2(aux, Path(str(destino) + sufijo))


def _requiere_bd():
    if not BD_REBUILD_08_10.exists():
        pytest.skip(f"falta la BD de referencia {BD_REBUILD_08_10.name}")


@pytest.fixture
def bd_08_10(monkeypatch, tmp_path):
    """Copia de trabajo de la BD del rebuild del 08-10 (la del fisico), con las migraciones idempotentes ya corridas."""
    _requiere_bd()
    copia = tmp_path / "copia.db"
    _copiar_bd(BD_REBUILD_08_10, copia)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: str(copia))
    conection_mod.Conexion._instance = None
    return copia


def _txt(v):
    """Como `str(query.value(...))` de QtSql: un NULL es la cadena vacia."""
    return "" if v is None else str(v)


def _foto(ruta):
    """Lo guardado de cada calibracion vigente, con SQL propio y `sqlite3` (independiente de los cargadores de la pantalla)."""
    con = sqlite3.connect(str(ruta))
    foto = {}
    for (ref,) in con.execute(f"SELECT id FROM TipoCalibracion WHERE {VIGENTE}").fetchall():
        tc = con.execute("SELECT fecha, tipo, serie, certificado, fecha_cer, intensidad, conversion, user FROM TipoCalibracion WHERE id = ?",
                         (ref,)).fetchone()
        sis = con.execute(f"SELECT modelo, serie_cp, modelo_elec, serie_ele, calibracion, electrometro, t0, p0, h0 FROM SistemaMedicion "
                          f"WHERE ref = ? AND {VIGENTE}", (ref,)).fetchall()
        cond = con.execute(f"SELECT t, p, h FROM CondicionesMedicion WHERE ref = ? AND {VIGENTE}", (ref,)).fetchall()
        maximos = con.execute(f"SELECT posicion, medida1, medida2, promedio FROM MaximosCamaras WHERE ref = ? AND {VIGENTE} "
                              f"ORDER BY posicion DESC", (ref,)).fetchall()
        lecturas = con.execute(f"SELECT voltaje, V_300, V_150, Vn_300, promediosV FROM LecturasMaximos WHERE ref = ? AND {VIGENTE}",
                               (ref,)).fetchall()
        act = con.execute(f"SELECT actividad_monitor FROM ResultadosActividad WHERE ref = ? AND {VIGENTE}", (ref,)).fetchall()
        foto[ref] = {
            "tipo": dict(zip(("fecha", "tipo", "serie", "certificado", "fecha_cer", "intensidad", "conversion", "user"), tc)),
            "sistema": dict(zip(("modelo", "serie_cp", "modelo_elec", "serie_ele", "calibracion", "electrometro", "t0", "p0", "h0"), sis[0]))
            if sis else None,
            "n_sistema": len(sis), "n_cond": len(cond), "n_act": len(act),
            "condiciones": cond[0] if cond else None,
            "maximos": maximos,
            "lecturas": lecturas,
            "actividad": act[0][0] if act else None,
        }
    con.close()
    return foto


@pytest.fixture(scope="module")
def foto(tmp_path_factory):
    """La foto de la BD INTACTA (tomada una vez, antes de que ninguna prueba abra Qt sobre una copia)."""
    _requiere_bd()
    carpeta = tmp_path_factory.mktemp("bm1_foto")
    copia = carpeta / "foto.db"
    _copiar_bd(BD_REBUILD_08_10, copia)
    return _foto(copia)


class _UsuarioFalso:
    def __init__(self, nombre="Físico de Prueba"):
        self._nombre = nombre
        self.nombre = nombre
        self.id = 1

    def __getattr__(self, item):
        return None


def _cerrar(p):
    """Trampa 9: liberar la pagina DE VERDAD (hide/close/deleteLater + sendPostedEvents + processEvents + gc)."""
    p.hide()
    p.close()
    p.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


@pytest.fixture
def abrir(app, bd_08_10):
    """`abrir(tipo)` -> pagina real con la casilla de ese tipo elegida (ANTES de mover la fecha, como el fisico)."""
    paginas = []

    def _abrir(tipo):
        if tipo == REDUNDANTE:
            p = CalRedundanteFuente(_UsuarioFalso())
        else:
            p = PruebaMensualBraq(_UsuarioFalso())
            (p.pri_cal if tipo == MENSUAL else p.red_cal).setChecked(True)
        assert p._tipo_calibracion_seleccionado() == tipo
        paginas.append(p)
        return p

    yield _abrir
    for p in paginas:
        _cerrar(p)


def _fecha(iso):
    return QDate.fromString(iso, "yyyy-MM-dd")


def _tablas(p):
    return ([[c.text() for c in fila] for fila in p.campos_maximos], [[c.text() for c in fila] for fila in p.campos_lecturas])


def _lecturas_esperadas(f):
    """Lo que la pantalla muestra de LecturasMaximos: por PAPEL (V.3), no por fila."""
    return [[_txt(v), *(_txt(m) for m in medidas), _txt(prom)] for v, medidas, prom in lecturas_por_voltaje(f["lecturas"])]


def _maximos_esperados(f):
    return [[_txt(x) for x in fila] for fila in f["maximos"]]


def _verifica_pantalla(p, f, ref):
    """La pantalla muestra EXACTAMENTE lo guardado de la calibracion `ref` en las seis tablas."""
    assert p.ref_bd == ref
    tc, sis = f["tipo"], f["sistema"]
    # --- TipoCalibracion
    assert p.serie.text() == _txt(tc["serie"])
    assert p.certificado.text() == _txt(tc["certificado"])
    assert p.intensidad.text() == _txt(tc["intensidad"])
    assert p.conversion.text() == _txt(tc["conversion"])
    if QDateTime.fromString(_txt(tc["fecha_cer"]), FORMATO).isValid():
        assert p.fecha_cer.dateTime().toString(FORMATO) == tc["fecha_cer"]
    if QDateTime.fromString(_txt(tc["fecha"]), FORMATO).isValid():
        assert p.fecha_cal.dateTime().toString(FORMATO) == tc["fecha"]
    # --- SistemaMedicion (equipos y valores historicos)
    assert p.modelo.currentText() == _txt(sis["modelo"])
    # (el ref 36 guardó la ETIQUETA decorada como serie -- DP-105, ya corregido hacia adelante en T.2; la pantalla muestra la serie real)
    assert serie_de_item(p.serie_cp, p.serie_cp.currentIndex()) == serie_de_etiqueta(_txt(sis["serie_cp"]))
    assert p.modelo_elec.currentText() == _txt(sis["modelo_elec"])
    assert serie_de_item(p.serie_ele, p.serie_ele.currentIndex()) == serie_de_etiqueta(_txt(sis["serie_ele"]))
    assert (p.calibracion.text(), p.electrometro.text(), p.t0.text(), p.p0.text(), p.h0.text()) == \
        tuple(_txt(sis[k]) for k in ("calibracion", "electrometro", "t0", "p0", "h0"))
    # --- CondicionesMedicion
    assert (p.t.text(), p.p.text(), p.h.text()) == tuple(_txt(x) for x in f["condiciones"])
    # --- MaximosCamaras y LecturasMaximos
    maximos, lecturas = _tablas(p)
    assert maximos == _maximos_esperados(f)
    assert lecturas == _lecturas_esperadas(f)
    # --- ResultadosActividad (actividad del monitor)
    assert p.ref.text() == _txt(f["actividad"])


def _tablas_en_blanco(p):
    """Estado de las dos tablas «en blanco»: posiciones y voltajes por omision, medidas vacias, promedios en «-»."""
    maximos, lecturas = _tablas(p)
    assert maximos == [[pos, "", "", "-"] for pos in POSICIONES_ESTANDAR]
    assert lecturas == [[v, "", "", "", "-"] for v in VOLTAJES_POR_DEFECTO]
    assert list(VOLTAJES_POR_DEFECTO) == ["300", "50", "-300"]


def _qt_filas(p, sql, *params):
    """Relee por una conexión QtSql NUEVA y de un solo uso (la misma biblioteca que usa la pantalla). No sirve la conexión por omisión de la
    pantalla: en modo WAL una consulta sin terminar (p. ej. el modelo de la tabla de la derecha) fija la «foto» de esa conexión y no vería lo
    que acaba de guardar el `sqlite3` del escritor. La ruta es la de la copia de trabajo (la que parchea la fixture `bd_08_10`)."""
    nombre = "bm1_lectura"
    db = QSqlDatabase.addDatabase("QSQLITE", nombre)
    db.setDatabaseName(conection_mod.ruta_base_datos())
    try:
        assert db.open(), db.lastError().text()
        q = QSqlQuery(db)
        q.prepare(sql)
        for v in params:
            q.addBindValue(v)
        assert q.exec_(), q.lastError().text()
        filas = []
        while q.next():
            filas.append(tuple(q.value(i) for i in range(q.record().count())))
        q.finish()
        return filas
    finally:
        q = None
        db.close()
        del db
        QSqlDatabase.removeDatabase(nombre)


_LECTOR_OTRO_PROCESO = (
    "import json, sqlite3, sys\n"
    "con = sqlite3.connect(sys.argv[1])\n"
    "print(json.dumps(con.execute(sys.argv[2], json.loads(sys.argv[3])).fetchall()))\n")


def _filas_otro_proceso(sql, *params):
    """Relee la copia de trabajo desde un PROCESO NUEVO (no el de la prueba): lo guardado esta de verdad en el archivo. Opus midio el 15-10 que, con
    dos SQLite en un mismo proceso en Linux (la de Python que escribe y la de Qt que lee), un guardado «exitoso» puede no verse desde fuera (la familia
    de DP-147; en Windows no aplica): leer en este mismo proceso no lo descartaria."""
    r = subprocess.run([sys.executable, "-I", "-c", _LECTOR_OTRO_PROCESO, conection_mod.ruta_base_datos(), sql, json.dumps(list(params))],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return [tuple(f) for f in json.loads(r.stdout)]


def _llenar_control_a_mano(p):
    """Escribe a mano un control completo, con los equipos reales del catalogo de la copia (los combos nacen en "Seleccionar Modelo…" y la serie solo
    aparece al elegir el modelo; elegir la serie pone el factor de la camara y T0, P0, H0 del catalogo)."""
    p.serie.setText("24-05-0000-003-010126-10000-26")
    p.certificado.setText("003")
    p.intensidad.setText("11.96")
    p.conversion.setText("0.11")
    p.fecha_cer.setDateTime(QDateTime.fromString("2026-01-02 08:00:00", FORMATO))
    p.combo_modelo.setCurrentText("HDR1000 Plus")
    assert p.combo_serie.count() > 1, "el catalogo no ofrece series para HDR1000 Plus"
    p.combo_serie.setCurrentIndex(1)
    p.combo_modelo_elec.setCurrentText("Unidos-E")
    assert p.combo_serie_elec.count() > 1, "el catalogo no ofrece series para Unidos-E"
    p.combo_serie_elec.setCurrentIndex(1)
    p.t.setText("21.5")
    p.p.setText("638")
    p.h.setText("52.0")
    p.ref.setText("9.5")
    p.observaciones.setText("escrito a mano (BM.1)")
    for i, fila in enumerate(p.campos_maximos):
        fila[1].setText(f"{60 + i * 1.1:.3f}")
        fila[2].setText(f"{60.2 + i * 1.1:.3f}")
    for fila, medidas in zip(p.campos_lecturas, (("7.13e-08", "7.12e-08", "7.14e-08"), ("7.03e-08", "7.04e-08", "7.02e-08"),
                                                 ("7.12e-08", "7.13e-08", "7.11e-08"))):
        for celda, m in zip(fila[1:4], medidas):
            celda.setText(m)


def _estado_hijas(p, ref):
    """Todo lo guardado de `ref` (vigente o no) en las seis tablas, para comprobar que NO se tocó."""
    estado = {"TipoCalibracion": _qt_filas(p, "SELECT * FROM TipoCalibracion WHERE id = ?", ref)}
    for tabla in HIJAS:
        estado[tabla] = _qt_filas(p, f"SELECT * FROM {tabla} WHERE ref = ? ORDER BY rowid", ref)
    return estado


def _vigentes(p, tabla, campo, valor):
    return _qt_filas(p, f"SELECT COUNT(*) FROM {tabla} WHERE {campo} = ? AND {VIGENTE}", valor)[0][0]


def _escribir_voltajes(p, alto, bajo, negativo):
    for fila, v in zip(p.campos_lecturas, (alto, bajo, negativo)):
        fila[0].setText(v)


# ---------------------------------------------------------------------------------------------------------------------------
# (a) y (b): la secuencia del fisico -- abrir el 27-09, voltajes 300 / 50 / -300, Ok, Anadir.
# ---------------------------------------------------------------------------------------------------------------------------

CASOS_27_09 = [(REDUNDANTE, 39, 37), (CAMBIO, 37, 39)]


@pytest.mark.parametrize("tipo,ref,otro_ref", CASOS_27_09)
def test_a_b_27_09_las_10_posiciones_y_las_medidas_son_las_del_ref_propio(abrir, foto, tipo, ref, otro_ref):
    p = abrir(tipo)
    p.date_box.setDate(_fecha("2026-09-27"))

    # Las 10 posiciones son las estandar y distintas; cada fila trae las medidas del ref propio y NO las del otro del mismo dia.
    maximos, lecturas = _tablas(p)
    assert [float(f[0]) for f in maximos] == sorted({float(x) for x in POSICIONES_ESTANDAR}, reverse=True)
    assert len({f[0] for f in maximos}) == 10
    assert maximos == _maximos_esperados(foto[ref])
    assert maximos != _maximos_esperados(foto[otro_ref]), "la fixture no discrimina: los dos refs tendrían las mismas medidas"
    assert lecturas == _lecturas_esperadas(foto[ref])
    _verifica_pantalla(p, foto[ref], ref)


@pytest.mark.parametrize("tipo,ref,otro_ref", CASOS_27_09)
def test_a_b_27_09_voltajes_300_50_menos300_ok_y_anadir_guarda(abrir, foto, dialogos, tipo, ref, otro_ref):
    """La secuencia del físico (anotación del rebuild, 15-10): abrir el 27-09, voltajes 300 / 50 / -300, Ok, Añadir. Con dos
    calibraciones el mismo día esto fallaba con `UNIQUE constraint failed: MaximosCamaras.ref, MaximosCamaras.posicion`."""
    p = abrir(tipo)
    p.date_box.setDate(_fecha("2026-09-27"))
    assert p.ref_bd == ref
    maximos, _lecturas = _tablas(p)

    # El otro control del dia, intacto desde ya (foto previa por Qt, para comparar despues con el mismo lector).
    otro_antes = _estado_hijas(p, otro_ref)
    viejo_antes = _estado_hijas(p, ref)

    # 3. El fisico escribe 300 / 50 / -300 (lo que de verdad midio; lo guardado dice 150), Ok y Anadir.
    _escribir_voltajes(p, "300", "50", "-300")
    p.aceptar.click()
    assert p.btn_add.isEnabled(), "tras «Ok» con todo el formulario lleno, «Añadir» debe quedar habilitado"
    dialogos.clear()
    _soltar_qt_antes_de_escribir()
    p.btn_add.click()

    guardados = [d for d in dialogos if d[0] == "information"]
    assert any("Datos guardados correctamente" in d[2] for d in guardados), dialogos
    assert not [d for d in dialogos if d[0] in ("warning", "critical") and "Error al guardar" in d[2]], dialogos

    # 4. UNA calibracion vigente de ese tipo ese dia, con un id nuevo, y sus 5 hijas vigentes son las de la pantalla.
    vigentes = _qt_filas(p, f"SELECT id FROM TipoCalibracion WHERE DATE(fecha) = ? AND tipo = ? AND {VIGENTE}", "2026-09-27", tipo)
    assert len(vigentes) == 1 and vigentes[0][0] > 39, vigentes
    nuevo = vigentes[0][0]
    assert p.ref_bd == nuevo
    assert _vigentes(p, "SistemaMedicion", "ref", nuevo) == 1
    assert _vigentes(p, "CondicionesMedicion", "ref", nuevo) == 1
    assert _vigentes(p, "ResultadosActividad", "ref", nuevo) == 1
    assert _vigentes(p, "MaximosCamaras", "ref", nuevo) == 10
    assert _vigentes(p, "LecturasMaximos", "ref", nuevo) == 3
    posiciones_guardadas = [r[0] for r in _qt_filas(
        p, f"SELECT posicion FROM MaximosCamaras WHERE ref = ? AND {VIGENTE} ORDER BY posicion DESC", nuevo)]
    assert [float(x) for x in posiciones_guardadas] == [float(f[0]) for f in maximos]
    voltajes_guardados = sorted(float(r[0]) for r in _qt_filas(
        p, f"SELECT voltaje FROM LecturasMaximos WHERE ref = ? AND {VIGENTE}", nuevo))
    assert voltajes_guardados == [-300.0, 50.0, 300.0], "el voltaje bajo guardado es 50 (lo que midió), no el 150 de antes"

    # 4-bis. Y esta DE VERDAD en el archivo: se relee desde un proceso nuevo (la nueva vigente, la anterior y la otra del dia).
    assert _filas_otro_proceso("SELECT id, COALESCE(activo, 1) FROM TipoCalibracion WHERE id IN (?, ?, ?) ORDER BY id", ref, otro_ref, nuevo) == \
        sorted([(ref, 0), (otro_ref, 1), (nuevo, 1)])
    assert _filas_otro_proceso("SELECT COUNT(*) FROM MaximosCamaras WHERE ref = ? AND (activo IS NULL OR activo = 1)", nuevo) == [(10,)]

    # 5. La anterior y sus hijas quedaron anuladas (nunca borradas); la OTRA calibracion del dia sigue vigente e intacta.
    assert _vigentes(p, "TipoCalibracion", "id", ref) == 0
    for tabla in HIJAS:
        assert _vigentes(p, tabla, "ref", ref) == 0, tabla
    despues = _estado_hijas(p, ref)
    assert {t: len(f) for t, f in despues.items()} == {t: len(f) for t, f in viejo_antes.items()}, "la calibración anulada no pierde filas"
    assert _estado_hijas(p, otro_ref) == otro_antes, "la otra calibración del día debe quedar vigente e intacta"
    assert _vigentes(p, "TipoCalibracion", "id", otro_ref) == 1


# ---------------------------------------------------------------------------------------------------------------------------
# (c): los cinco dias con dos calibraciones, en las dos paginas -- cada una muestra lo de SU ref.
# ---------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("iso,tipo,ref", DIAS_CON_DOS, ids=[f"{i}-{t[:4]}-ref{r}" for i, t, r in DIAS_CON_DOS])
def test_c_dias_con_dos_calibraciones_cada_pagina_muestra_la_suya(abrir, foto, iso, tipo, ref):
    p = abrir(tipo)
    p.date_box.setDate(_fecha(iso))
    _verifica_pantalla(p, foto[ref], ref)


def test_c_ref_15_con_fecha_dd_mm_yyyy_se_abre(abrir, foto):
    """La redundante del 27-09-2025 guardó su fecha como `27-09-2025` (DP-32): para resolver su ref hace falta el predicado de los
    DOS formatos. Sin él, el ref 15 no se abre y la página se queda con None."""
    assert foto[15]["tipo"]["fecha"] == "27-09-2025"
    p = abrir(REDUNDANTE)
    p.date_box.setDate(_fecha("2025-09-27"))
    assert p.ref_bd == 15
    assert p.ref.text() == _txt(foto[15]["actividad"])


# ---------------------------------------------------------------------------------------------------------------------------
# (d): cambiar de fecha deja las tablas en blanco; None -> None conserva lo escrito.
# ---------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("tipo,fecha_con_control", [(REDUNDANTE, "2026-09-27"), (CAMBIO, "2026-09-27"), (MENSUAL, "2026-08-31")])
def test_d_pasar_a_una_fecha_sin_calibracion_deja_las_tablas_en_blanco(abrir, foto, tipo, fecha_con_control):
    p = abrir(tipo)
    p.date_box.setDate(_fecha(fecha_con_control))
    assert p.ref_bd is not None and p.ref.text() != ""
    assert any(c.text() not in ("", "-") for fila in p.campos_maximos for c in fila[1:3]), "antes de pasar, la tabla tiene medidas"

    p.date_box.setDate(_fecha(DIA_SIN_CALIBRACION))          # sin ninguna calibracion

    assert p.ref_bd is None
    _tablas_en_blanco(p)
    assert p.ref.text() == "", "la actividad del monitor tampoco se hereda de otro dia"
    # los campos de linea quedan como hoy (limpiar_todos_los_campos): vacios
    for nombre in ("serie", "certificado", "intensidad", "conversion", "t", "p", "h", "calibracion", "electrometro", "t0", "p0", "h0"):
        assert getattr(p, nombre).text() == "", nombre


def test_d_none_a_none_lo_escrito_a_mano_sobrevive(abrir):
    """El fisico escribe un control NUEVO en una fecha sin calibracion y ajusta la fecha: nada de lo escrito se borra."""
    p = abrir(MENSUAL)
    p.date_box.setDate(_fecha("2026-03-14"))
    assert p.ref_bd is None
    p.serie.setText("24-05-0000-003-010126-10000-26")
    p.t.setText("21.5")
    p.p.setText("638")
    p.ref.setText("9.5")
    p.campos_maximos[0][1].setText("61.5")
    p.campos_maximos[3][2].setText("62.5")
    p.campos_lecturas[1][2].setText("7.04e-08")
    p.campos_lecturas[0][0].setText("250")

    antes = (_tablas(p), p.serie.text(), p.t.text(), p.p.text(), p.ref.text())
    p.date_box.setDate(_fecha("2026-03-16"))          # otra fecha sin calibracion: None -> None

    assert p.ref_bd is None
    assert (_tablas(p), p.serie.text(), p.t.text(), p.p.text(), p.ref.text()) == antes


def test_d_cargar_otra_calibracion_reemplaza_todo_lo_anterior(abrir, foto):
    p = abrir(MENSUAL)
    p.date_box.setDate(_fecha("2026-07-29"))
    _verifica_pantalla(p, foto[35], 35)
    p.date_box.setDate(_fecha("2026-08-31"))
    _verifica_pantalla(p, foto[36], 36)


def test_limpiar_deja_las_dos_tablas_con_la_misma_definicion_de_en_blanco(abrir, foto):
    """«Limpiar» y «pasar a una fecha sin calibración» usan UNA definición de «tablas en blanco». Antes, «Limpiar» no reponía las
    posiciones: lo que quedara en esa columna se quedaba."""
    p = abrir(MENSUAL)
    p.date_box.setDate(_fecha("2026-08-31"))
    p.campos_maximos[2][0].setText("999")            # una posicion alterada
    p.btn_clean.click()
    _tablas_en_blanco(p)


# ---------------------------------------------------------------------------------------------------------------------------
# (e): la grafica de maximos del mensual dibuja la calibracion del tipo elegido, no las dos del dia.
# ---------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("tipo,ref", [(REDUNDANTE, 39), (CAMBIO, 37)])
def test_e_la_grafica_de_maximos_dibuja_los_10_puntos_del_tipo_elegido(abrir, foto, _grafica_espia, tipo, ref):
    p = abrir(tipo)
    _grafica_espia.clear()
    p._ejecutar_grafico_mensual("Máximos de la cámara", "2026-09-27")
    assert len(_grafica_espia) == 1
    posiciones, promedios = _grafica_espia[0]["posiciones"], _grafica_espia[0]["promedio"]
    assert len(posiciones) == 10 and len(promedios) == 10, "10 puntos (los de UNA calibración), no 20"
    esperado = sorted(((float(pos), float(prom)) for pos, _m1, _m2, prom in foto[ref]["maximos"]))
    assert sorted(zip(posiciones, promedios)) == esperado


# ---------------------------------------------------------------------------------------------------------------------------
# (f): una calibracion con MENOS filas no deja restos de la anterior (tablas en blanco antes de llenarlas).
# ---------------------------------------------------------------------------------------------------------------------------

def _sembrar(fecha, tipo=CAMBIO, n_posiciones=10, escala=60.0, equipos=("HDR1000 Plus", "A092535", "CDX-2000B", "B091982"),
             calibracion=464700.0, electrometro=1.0, t0=22.0, p0=760.0, h0=50.0, t=21.0, p=638.0, h=50.0, actividad=9.5, base_lecturas=7.0e-08,
             certificado="003", intensidad=10.0):
    """Guarda por el escritor REAL una calibración sintética con `n_posiciones` filas de máximos y valores propios en TODAS las tablas."""
    posiciones = [float(x) for x in POSICIONES_ESTANDAR[:n_posiciones]]
    m1 = [round(escala + i, 3) for i in range(n_posiciones)]
    m2 = [round(escala + i + 0.1, 3) for i in range(n_posiciones)]
    prom = [round((a + b) / 2, 3) for a, b in zip(m1, m2)]
    modelo, serie_cp, modelo_elec, serie_ele = equipos
    guardar_resultado_CambioFuente(
        "Físico de Prueba", fecha, tipo, "24-05-0000-003-010126-10000-26", certificado, "2026-01-02 08:00:00", intensidad, 0.11,
        modelo, serie_cp, calibracion, modelo_elec, serie_ele, electrometro, t0, p0, h0, t, p, h,
        posiciones, m1, m2, prom,
        [300.0, 150.0, -300.0],
        [base_lecturas * 1.02, base_lecturas * 1.01, base_lecturas * 1.03],
        [base_lecturas * 0.98, base_lecturas * 0.99, base_lecturas * 0.97],
        [base_lecturas * 1.00, base_lecturas * 1.005, base_lecturas * 0.995],
        [base_lecturas * 1.02, base_lecturas * 0.98, base_lecturas * 1.00], 1.0, 1.0, 1.19, actividad, actividad + 0.1, actividad + 0.2, None, "sintetica")


def test_f_una_calibracion_con_menos_filas_no_deja_restos_de_la_anterior(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "sintetica.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    conection_mod.Conexion._instance = None
    conection_mod.Conexion().con.close()              # crea el esquema
    conection_mod.Conexion._instance = None
    _sembrar("2026-03-10 10:00:00", n_posiciones=10, escala=60.0)         # diez filas
    _sembrar("2026-03-11 10:00:00", n_posiciones=6, escala=30.0)          # solo seis
    p = PruebaMensualBraq(_UsuarioFalso())
    try:
        p.red_cal.setChecked(True)
        p.date_box.setDate(_fecha("2026-03-10"))
        assert [f[1].text() for f in p.campos_maximos] == [str(round(60.0 + i, 3)) for i in range(10)]

        p.date_box.setDate(_fecha("2026-03-11"))

        maximos, _lecturas = _tablas(p)
        assert [f[1] for f in maximos[:6]] == [str(round(30.0 + i, 3)) for i in range(6)]
        assert maximos[6:] == [[pos, "", "", "-"] for pos in POSICIONES_ESTANDAR[6:]], \
            "las filas 7 a 10 no pueden conservar las medidas del día anterior"
    finally:
        _cerrar(p)


def test_f2_dos_calibraciones_del_mismo_dia_con_valores_distintos_en_las_seis_tablas(abrir, bd_08_10, app):
    """Las cinco hijas con dos calibraciones de DISTINTO tipo el mismo día, cada tabla con valores propios. Con la copia real del físico las
    hijas `SistemaMedicion` y la actividad del monitor de los dos controles de un mismo día son IDÉNTICAS (d03 del diagnóstico), así que solo
    una siembra sintética las distingue -- sin ella, leer esas dos por fecha pasaría desapercibido."""
    _sembrar("2026-03-12 10:00:00", CAMBIO, escala=40.0, equipos=("HDR1000 Plus", "A092535", "CDX-2000B", "B091982"),
             calibracion=464700.0, electrometro=1.0, t0=22.0, p0=760.0, h0=50.0, t=20.0, p=630.0, h=40.0, actividad=7.5,
             base_lecturas=5.0e-08, certificado="111", intensidad=10.0)
    _sembrar("2026-03-12 11:30:00", REDUNDANTE, escala=50.0, equipos=("HDR1000 Plus", "A092535", "Unidos-E", "002343"),
             calibracion=466700.0, electrometro=1.02, t0=21.0, p0=758.0, h0=55.0, t=23.5, p=645.0, h=60.0, actividad=8.25,
             base_lecturas=6.0e-08, certificado="222", intensidad=11.0)
    foto2 = _foto(bd_08_10)
    refs = {f["tipo"]["tipo"]: ref for ref, f in foto2.items() if f["tipo"]["fecha"][:10] == "2026-03-12"}
    assert set(refs) == {CAMBIO, REDUNDANTE}
    # la fixture discrimina: ninguna de las cinco hijas coincide entre las dos
    a, b = foto2[refs[CAMBIO]], foto2[refs[REDUNDANTE]]
    assert a["sistema"] != b["sistema"] and a["condiciones"] != b["condiciones"] and a["actividad"] != b["actividad"]
    assert a["maximos"] != b["maximos"] and a["lecturas"] != b["lecturas"]
    for tipo in (CAMBIO, REDUNDANTE):
        p = abrir(tipo)
        p.date_box.setDate(_fecha("2026-03-12"))
        _verifica_pantalla(p, foto2[refs[tipo]], refs[tipo])


def test_si_la_consulta_del_ref_falla_no_se_toca_el_formulario(abrir, foto, monkeypatch):
    """Si la consulta que resuelve el `ref` falla (la BD no responde), el formulario queda como estaba: no se confunde «no pude leer» con
    «no hay calibración» y se borran las tablas."""
    p = abrir(MENSUAL)
    p.date_box.setDate(_fecha("2026-08-31"))
    _verifica_pantalla(p, foto[36], 36)
    antes = (_tablas(p), p.serie.text(), p.t.text(), p.ref.text(), p.ref_bd, p.fecha_cal.dateTime().toString(FORMATO))

    monkeypatch.setattr(p, "_ref_de_la_calibracion", lambda db, fecha: (False, None))
    p.date_box.setDate(_fecha(DIA_SIN_CALIBRACION))

    assert (_tablas(p), p.serie.text(), p.t.text(), p.ref.text(), p.ref_bd, p.fecha_cal.dateTime().toString(FORMATO)) == antes


# ---------------------------------------------------------------------------------------------------------------------------
# (k): la «Fecha del control» (`fecha_cal`, la fecha con que se GUARDA) sigue al DIA de la fecha de arriba (`date_box`).
# DECISION VETABLE POR EL FISICO, diagnosticada por Opus el 15-10: sin ella, abrir una calibracion y pasar a otro dia para escribir un control
# NUEVO lo guardaba, en silencio, con la fecha de la calibracion abierta -- y la anulaba (HEAD lo frenaba, por accidente, con el UNIQUE).
# ---------------------------------------------------------------------------------------------------------------------------

def test_k_none_a_none_la_fecha_del_control_sigue_a_la_fecha_de_arriba(abrir):
    p = abrir(MENSUAL)
    hora = p.fecha_cal.time()                          # la hora con que nace la pagina
    p.date_box.setDate(_fecha("2026-03-14"))
    assert p.ref_bd is None
    assert p.fecha_cal.date() == QDate(2026, 3, 14) and p.fecha_cal.time() == hora
    p.date_box.setDate(_fecha("2026-03-16"))           # otra fecha sin calibracion: None -> None
    assert p.fecha_cal.date() == QDate(2026, 3, 16) and p.fecha_cal.time() == hora, "solo cambia el DIA: la hora no se toca"


def test_k_tras_pasar_de_una_calibracion_abierta_a_una_fecha_vacia_la_fecha_del_control_deja_la_de_la_calibracion(abrir, foto):
    p = abrir(REDUNDANTE)
    p.date_box.setDate(_fecha("2026-09-27"))
    assert p.fecha_cal.dateTime().toString(FORMATO) == foto[39]["tipo"]["fecha"] == "2026-09-27 18:00:00"   # la guardada manda al abrir

    p.date_box.setDate(_fecha(DIA_SIN_CALIBRACION))    # X -> None

    assert p.ref_bd is None
    assert p.fecha_cal.date() == QDate(2026, 3, 15), "no puede quedar con el 27-09 de la calibracion que acaba de cerrarse"
    assert p.fecha_cal.time().toString("HH:mm:ss") == "18:00:00", "solo cambia el DIA: la hora no se toca"
    p.date_box.setDate(_fecha("2026-09-27"))           # volver a abrirla trae su fecha guardada, no la de paso
    assert p.ref_bd == 39 and p.fecha_cal.dateTime().toString(FORMATO) == "2026-09-27 18:00:00"


@pytest.mark.parametrize("tipo", [CAMBIO, MENSUAL])
def test_k_puerta_de_salida_paso_5_el_control_nuevo_se_guarda_con_la_fecha_de_arriba_y_no_anula_el_abierto(abrir, foto, dialogos, tipo):
    """El paso 5 de §3 del plan al pie de la letra: abrir el 27-09, pasar a otra fecha (las tablas quedan en blanco), escribir un control completo,
    cambiar a otra fecha sin calibracion (lo escrito sigue) y Anadir. Medido por Opus: SIN `fecha_cal` siguiendo a la fecha de arriba, esto se guardaba
    con `2026-09-27 17:00:17` y anulaba el cambio de fuente 37 (y decia «guardado»). Con la casilla «Control Mensual» no hay nada que abrir el 27-09:
    es el mismo recorrido desde un formulario en blanco."""
    p = abrir(tipo)
    abierta = None
    if tipo == CAMBIO:
        p.date_box.setDate(_fecha("2026-09-27"))
        assert p.ref_bd == 37
        abierta = _estado_hijas(p, 37)
    p.date_box.setDate(_fecha(DIA_SIN_CALIBRACION))
    _tablas_en_blanco(p)
    _llenar_control_a_mano(p)
    escrito = (_tablas(p), p.serie.text(), p.t.text(), p.ref.text())

    p.date_box.setDate(_fecha("2026-03-16"))           # otra fecha sin calibracion: lo escrito sigue
    assert (_tablas(p), p.serie.text(), p.t.text(), p.ref.text()) == escrito
    assert p.fecha_cal.date() == QDate(2026, 3, 16)

    p.aceptar.click()
    assert p.btn_add.isEnabled()
    dialogos.clear()
    _soltar_qt_antes_de_escribir()
    p.btn_add.click()

    assert any(d[0] == "information" and "Datos guardados correctamente" in d[2] for d in dialogos), dialogos
    nuevos = _filas_otro_proceso("SELECT id, fecha, tipo, COALESCE(activo, 1) FROM TipoCalibracion WHERE id > 39 ORDER BY id")
    assert len(nuevos) == 1, nuevos
    nuevo, fecha_guardada, tipo_guardado, vigente = nuevos[0]
    assert fecha_guardada[:10] == "2026-03-16" and tipo_guardado == tipo and vigente == 1, \
        "el control nuevo se guarda con la fecha que muestra la pantalla (16-03), no con la de la calibracion abierta antes"
    assert p.ref_bd == nuevo
    if tipo == CAMBIO:
        assert _filas_otro_proceso("SELECT COALESCE(activo, 1) FROM TipoCalibracion WHERE id = 37") == [(1,)], "el 37 (el abierto) sigue vigente"
        assert _estado_hijas(p, 37) == abierta, "y sus seis tablas, intactas"
    assert _filas_otro_proceso("SELECT COUNT(*) FROM MaximosCamaras WHERE ref = ? AND (activo IS NULL OR activo = 1)", nuevo) == [(10,)]


# ---------------------------------------------------------------------------------------------------------------------------
# (g): los dias con un solo control se ven como se guardaron.
# ---------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("ref", REFS_SOLOS)
def test_g_un_solo_control_en_su_dia_se_ve_como_se_guardo(abrir, foto, ref):
    p = abrir(MENSUAL)
    p.date_box.setDate(_fecha(foto[ref]["tipo"]["fecha"][:10]))
    _verifica_pantalla(p, foto[ref], ref)


# ---------------------------------------------------------------------------------------------------------------------------
# (h): reabrir y volver a guardar SIN tocar nada funciona en todos los casos (el reclamo del fisico), y no mezcla.
# ---------------------------------------------------------------------------------------------------------------------------

REABRIR_Y_GUARDAR = [(i, t, r) for i, t, r in DIAS_CON_DOS if r != 15] + [("2026-08-31", MENSUAL, 36), ("2026-07-29", MENSUAL, 35)]


@pytest.mark.parametrize("iso,tipo,ref", REABRIR_Y_GUARDAR, ids=[f"{i}-{t[:4]}-ref{r}" for i, t, r in REABRIR_Y_GUARDAR])
def test_h_reabrir_y_volver_a_guardar_sin_tocar_nada(abrir, foto, dialogos, iso, tipo, ref):
    p = abrir(tipo)
    p.date_box.setDate(_fecha(iso))
    _verifica_pantalla(p, foto[ref], ref)
    otros = [r for r, f in foto.items() if r != ref and f["tipo"]["fecha"][:10] == iso]
    otros_antes = {r: _estado_hijas(p, r) for r in otros}

    p.aceptar.click()
    assert p.btn_add.isEnabled()
    dialogos.clear()
    _soltar_qt_antes_de_escribir()
    p.btn_add.click()

    assert any(d[0] == "information" and "Datos guardados correctamente" in d[2] for d in dialogos), dialogos
    nuevo = p.ref_bd
    assert nuevo != ref and nuevo is not None
    assert _vigentes(p, "TipoCalibracion", "id", nuevo) == 1 and _vigentes(p, "TipoCalibracion", "id", ref) == 0
    assert _vigentes(p, "MaximosCamaras", "ref", nuevo) == 10 and _vigentes(p, "LecturasMaximos", "ref", nuevo) == 3
    assert _filas_otro_proceso("SELECT id, COALESCE(activo, 1) FROM TipoCalibracion WHERE id IN (?, ?) ORDER BY id", ref, nuevo) == \
        sorted([(ref, 0), (nuevo, 1)]), "lo guardado esta de verdad en el archivo (relectura desde otro proceso)"
    for r in otros:
        assert _estado_hijas(p, r) == otros_antes[r], f"el ref {r} (otro del mismo día) no debe tocarse"


# ---------------------------------------------------------------------------------------------------------------------------
# (t): tripwires.
# ---------------------------------------------------------------------------------------------------------------------------

def _arbol():
    return ast.parse(BRAQ_MENSUAL.read_text(encoding="utf-8"))


def _clase(arbol, nombre):
    return next(n for n in arbol.body if isinstance(n, ast.ClassDef) and n.name == nombre)


def _cadena(nodo):
    """Texto de una constante o de un f-string (cada `{...}` como `{}`)."""
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value
    if isinstance(nodo, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in nodo.values)
    return None


def test_t_exactamente_una_conexion_de_la_fecha_por_ast():
    """Una sola conexión `date_box.dateChanged` en la clase, y apunta a `actualizar_ref_bd`."""
    conexiones = []
    for nodo in ast.walk(_clase(_arbol(), "PruebaMensualBraq")):
        if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "connect"
                and isinstance(nodo.func.value, ast.Attribute) and nodo.func.value.attr == "dateChanged"):
            conexiones.append((ast.unparse(nodo.func.value.value), ast.unparse(nodo.args[0]) if nodo.args else None))
    assert conexiones == [("self.date_box", "self.actualizar_ref_bd")], conexiones


@pytest.mark.parametrize("tipo", [CAMBIO, REDUNDANTE, MENSUAL])
def test_t_exactamente_una_conexion_de_la_fecha_en_la_pagina_real(abrir, tipo):
    """`receivers(...)` sobre la pagina real: un `QDateEdit` solo ya trae 1 (interno de Qt); la clase añade exactamente UNA mas."""
    base = QDateEdit()
    p = abrir(tipo)
    assert p.date_box.receivers(p.date_box.dateChanged) == base.receivers(base.dateChanged) + 1


def _sentencias_de_texto(arbol):
    """Cada cadena COMPLETA (constante o f-string) del archivo, sin los fragmentos sueltos de un f-string ni los docstrings."""
    partes_de_fstring = {id(v) for n in ast.walk(arbol) if isinstance(n, ast.JoinedStr) for v in n.values}
    docstrings = {id(n.body[0].value) for n in ast.walk(arbol)
                  if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)
                  and isinstance(n.body[0].value.value, str)}
    for nodo in ast.walk(arbol):
        if id(nodo) in partes_de_fstring or id(nodo) in docstrings:
            continue
        texto = _cadena(nodo)
        if texto:
            yield texto


def test_t_ninguna_hija_de_braquiterapia_se_lee_por_la_fecha():
    """Ningún SQL de `braq_mensual.py` lee las cinco hijas por fecha: o `WHERE ref = ?`, o (la gráfica) el JOIN por `ref` a la
    calibración del TIPO elegido."""
    lecturas = []
    for sql in _sentencias_de_texto(_arbol()):
        if re.search(r"\b(FROM|JOIN)\s+(" + "|".join(HIJAS) + r")\b", sql):
            lecturas.append(" ".join(sql.split()))
    assert len(lecturas) >= 6, f"no vacuidad: se esperaban al menos 6 lecturas de hijas, hay {len(lecturas)}"
    malas = []
    for sql in lecturas:
        por_ref = re.search(r"\bWHERE\s+ref\s*=\s*\?", sql) is not None and "DATE(" not in sql
        grafica = "mc.ref = tc.id" in sql and "tc.tipo = ?" in sql
        if not (por_ref or grafica):
            malas.append(sql)
    assert malas == [], malas


def test_t_las_posiciones_estandar_tienen_una_sola_definicion():
    """«La tabla recién construida» y «la tabla en blanco» salen de la MISMA constante: el literal de las posiciones aparece una vez."""
    texto = BRAQ_MENSUAL.read_text(encoding="utf-8")
    assert texto.count('"127.5"') == 1
    assert list(braq_mensual_mod.POSICIONES_POR_DEFECTO) == POSICIONES_ESTANDAR
