"""E3 (PLAN_BRAQUI_HORA_EDITABLE_07-09.md): el test que faltaba.

`H6` y `T8` prueban la persistencia y la reposición de la hora poniéndola
**por código** (`setDateTime`/`setTime`) -- ese camino funcionaba incluso
con el defecto vivo (`DP-87`, un `QDateEdit` con formato de hora). Nadie
probó nunca el camino del físico: pararse en la sección de la hora y mover
la flecha, o teclear.

El pedido del físico no es "que la hora se guarde": es *"que la hora sea
editable y quede registrado el valor que uno introduzca"*. Mientras la
aserción de un test sea `setDateTime(...)` seguida de `assert`, el test
puede seguir verde con la pantalla rota -- ya ocurrió durante 10 días
(`DP-87`, `DP-68`).

Cadena completa, tal como la vive el físico: pararse en la hora -> moverla
con la flecha -> la actividad esperada se recalcula -> "Añadir" guarda esa
hora y esa actividad -> salir del día y volver repone ambas."""
import datetime
import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate, QDateTime, QTime
from PyQt5.QtSql import QSqlQuery
from PyQt5.QtWidgets import QApplication, QDateTimeEdit, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from analisisImagenes.ActividadFuente import VIDA_MEDIA_IR192_DIAS
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

# Igual que T8/B1: certificado con hora REAL (no medianoche) -- el test es
# más honesto si el A0 se parece al real (fecha_cer = '...11:36:24' en la
# BD del físico, DP-87 §0.1).
FECHA_CERTIFICADO = "2026-01-01 11:36:24"
A0_CI = 10.0


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "critical", "warning"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.Yes))


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
        "VALUES (1, 'fisico', ?, 'Cambio de fuente', 'SN1', 1.0, ?, ?, "
        "1.0, 1)",
        (FECHA_CERTIFICADO, FECHA_CERTIFICADO, A0_CI))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _actividad_esperada_independiente(momento):
    """Reimplementación INDEPENDIENTE (no llama a `calcular_decaimiento`)
    de la misma convención que `ActividadFuente.py` documenta y `test_b1`
    ya verificó: el certificado se interpreta en CET (Europe/Berlin), la
    medida en COT (America/Bogota)."""
    from zoneinfo import ZoneInfo
    f, h = momento.date(), momento.time()
    fin = datetime.datetime(f.year(), f.month(), f.day(),
                             h.hour(), h.minute(), h.second(),
                             tzinfo=ZoneInfo("America/Bogota"))
    inicio = (datetime.datetime.strptime(FECHA_CERTIFICADO, "%Y-%m-%d %H:%M:%S")
              .replace(tzinfo=ZoneInfo("Europe/Berlin")))
    horas = (fin - inicio).total_seconds() / 3600
    lam = math.log(2) / (VIDA_MEDIA_IR192_DIAS * 24)
    return A0_CI * math.exp(-lam * horas)


def _filas_braqui(d, patron_fecha):
    """Por la MISMA conexión QSqlDatabase que usa la pantalla (mismo
    motivo documentado en `test_h6`/`test_t8`: una segunda conexión
    sqlite3 no ve el commit de `add_info` en este entorno)."""
    db = d.opeenDatabase()
    query = QSqlQuery(db)
    query.prepare(
        "SELECT id, date, tol_exp_act, activo FROM braqui "
        "WHERE date LIKE :p ORDER BY id")
    query.bindValue(":p", patron_fecha)
    query.exec()
    filas = []
    while query.next():
        filas.append((query.value(0), query.value(1), query.value(2), query.value(3)))
    return filas


def _llenar_campos_numericos(d, valor="1.0"):
    for campo in ("line_1_rep_act_ci", "line_1_cyc_dummy", "line_1_cyc_rad"):
        getattr(d, campo).setText(valor)


class TestE3LaCadenaCompletaQueViveElFisico:

    def test_pararse_en_la_hora_y_mover_la_flecha_recalcula_y_se_guarda(
            self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())

        # Punto de partida conocido: un día con una hora central (evita
        # desbordar el día al sumar unas pocas horas -- P-3 de este
        # protocolo, obstáculo previsto).
        d.date_box.setDateTime(QDateTime(QDate(2026, 2, 7), QTime(8, 0, 0)))
        actividad_a_las_8 = d.line_1_exp_act_ci.text()

        # 1. El físico se para en la sección de la hora.
        d.date_box.setCurrentSection(QDateTimeEdit.HourSection)
        assert d.date_box.currentSection() == QDateTimeEdit.HourSection, (
            "el físico debe poder pararse en la HORA -- si esto falla, el "
            "widget sigue sin tener esa sección (E1 no llegó, o se revirtió)")

        # 2. Mueve la flecha 7 veces: 08:00 -> 15:00.
        for _ in range(7):
            d.date_box.stepBy(1)
        assert d.date_box.date() == QDate(2026, 2, 7), (
            "el DÍA no debía moverse -- si se movió, la flecha sigue "
            "cayendo sobre otra sección (la trampa de DP-87 §0.1)")
        assert d.date_box.time() == QTime(15, 0, 0), (
            f"se esperaba 15:00 tras 7 pasos desde las 08:00, quedó "
            f"{d.date_box.time().toString('HH:mm:ss')}")

        # 3. La actividad esperada se recalculó para el NUEVO instante.
        actividad_a_las_15 = d.line_1_exp_act_ci.text()
        assert actividad_a_las_15 != actividad_a_las_8, (
            "la actividad esperada debe cambiar al mover SOLO la hora -- "
            "si no cambió, R-1/_al_mover_el_date_box no está recalculando")
        esperado = _actividad_esperada_independiente(d.date_box.dateTime())
        assert float(actividad_a_las_15) == pytest.approx(esperado, rel=1e-3), (
            f"el valor debe coincidir con calcular_decaimiento para el "
            f"instante 2026-09-07 15:00:00: mostrado={actividad_a_las_15!r}, "
            f"esperado≈{esperado}")

        # 4. "Añadir" guarda la hora tecleada Y la actividad recalculada.
        _llenar_campos_numericos(d)
        d.ordenar_botones('braqui', False, "Diario")

        filas = _filas_braqui(d, "2026-02-07%")
        activas = [f for f in filas if f[3] == 1]
        assert len(activas) == 1, f"se esperaba 1 fila activa, hay {len(activas)}: {filas}"
        _id, fecha_guardada, tol_exp_guardado, _activo = activas[0]
        assert fecha_guardada == "2026-02-07 15:00:00", (
            f"la hora TECLEADA (vía flecha) debe guardarse tal cual, se "
            f"guardó {fecha_guardada!r}")
        assert float(tol_exp_guardado) == pytest.approx(float(actividad_a_las_15), rel=1e-9), (
            "la actividad guardada debe ser EXACTAMENTE la que la pantalla "
            "mostraba en el momento de guardar")

        # 5. Navega a otro día y vuelve: se repone fecha Y hora exactas,
        #    y la actividad mostrada es la GUARDADA (no una recalculada
        #    de nuevo contra "ahora").
        d.date_box.setDate(QDate(2026, 2, 10))  # otro día, sin registro
        d.date_box.setDate(QDate(2026, 2, 7))   # vuelve

        assert d.date_box.dateTime().toString("yyyy-MM-dd HH:mm:ss") == "2026-02-07 15:00:00", (
            f"al volver, date_box debía reponer fecha Y hora exactas del "
            f"registro guardado, quedó "
            f"{d.date_box.dateTime().toString('yyyy-MM-dd HH:mm:ss')!r}")
        assert d.line_1_exp_act_ci.text() == actividad_a_las_15, (
            "la actividad mostrada al reabrir debe ser la GUARDADA, no "
            "una recalculada de nuevo")


class TestE3RojoAntesQueVerdeContraElXlsxSinE1:
    """Rojo-antes-que-verde real, no por reversión de código: contra el
    `.xlsx` SIN el cambio de E1 (encabezado_braq/date_box = QDateEdit),
    el paso 1 de la cadena debe fallar -- no más tarde por un efecto
    secundario. Es lo que convierte a E3 en la prueba del PEDIDO del
    físico y no en un test decorativo (E2 certifica la declaración; esto
    certifica el comportamiento)."""

    def test_sin_e1_currentsection_no_es_hourssection(
            self, app, bd_temporal, tmp_path, monkeypatch):
        import openpyxl
        import data.ManejoDatos.lectorWidgets as lw

        ruta_original = lw.resource_path("data/widgets.xlsx")
        copia = tmp_path / "widgets_sin_e1.xlsx"
        wb = openpyxl.load_workbook(ruta_original)
        ws = wb["encabezado_braq"]
        for row in ws.iter_rows(min_row=2):
            if row[1].value == "date_box":
                assert row[2].value == "QDateTimeEdit", (
                    "precondición: el .xlsx real debe tener E1 aplicado "
                    "hoy (QDateTimeEdit) para poder revertirlo aquí")
                row[2].value = "QDateEdit"
        wb.save(copia)

        _orig = lw.resource_path
        monkeypatch.setattr(
            lw, "resource_path",
            lambda r: str(copia) if str(r).endswith("widgets.xlsx") else _orig(r))

        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDateTime(QDateTime(QDate(2026, 2, 7), QTime(8, 0, 0)))
        d.date_box.setCurrentSection(QDateTimeEdit.HourSection)
        assert d.date_box.currentSection() != QDateTimeEdit.HourSection, (
            "sin E1 el widget sigue siendo un QDateEdit -- si esto pasa, "
            "significa que el .xlsx revertido no llegó al widget "
            "(comprobar el parche de resource_path)")
        assert type(d.date_box).__name__ == "QDateEdit"
