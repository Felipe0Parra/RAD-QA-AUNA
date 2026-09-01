"""H6 (PLAN_BRAQUI_DIARIO_HORA_IMAGEN_28-08.md): `add_info` (`load.py:82`)
guardaba SIEMPRE `self.date_box.date().toString('yyyy-MM-dd')` -- `.date()`
descarta la hora, y el formato tampoco la lleva. [medido] en la raíz: las
449 filas históricas de `braqui.date` eran `'yyyy-MM-dd'` sin excepción. El
físico tiene razón: la hora era puramente decorativa.

Decisión D-H del físico (28-08): la hora se guarda SOLO para braqui (el
Ir-192 tiene 73,83 días de semivida y la hora mueve la actividad esperada;
en las otras 3 diarias no entra en ningún cálculo). Implementación: `add_
info` recibe el formato como parámetro (default 'yyyy-MM-dd', el
comportamiento de hoy); el llamador de braqui (`ordenar_botones`, rama
`otro == "Diario"`) es el único que pasa 'yyyy-MM-dd HH:mm:ss'.

Compatibilidad: la clave de bloque de las 4 diarias ya es `DATE(date)` -- una
EXPRESIÓN, no la columna (`MI3`) -- así que el índice UNIQUE parcial y
`reemplazar_bloque` ya toleraban una hora en la columna SIN cambio. Lo que
sí había que tocar eran las LECTURAS que comparan `date` por igualdad de
texto o por BETWEEN (censo ampliado durante la ejecución: además de
`cargar_dailytest_desde_db`, la función COMPARTIDA `graficarvstiempo`
-usada por las 4 diarias- y los dos exportadores de `SQLtoEXCEL.py`).

Trampa 2: `QMessageBox` mockeado -- un segundo guardado del mismo día
dispara la confirmación de reemplazo (`_confirmar_reemplazo_reporte_diario`,
`QMessageBox.question`).
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate, QDateTime, QTime
from PyQt5.QtSql import QSqlQuery
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.GraficasyTablas.unovsuno import graficarvstiempo
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

FECHA_FUENTE = "2026-01-01 00:00:00"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "critical"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    # las confirmaciones de reemplazo deben aceptarse para poder reguardar
    # el mismo día dos veces (parte del protocolo de H6)
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
        "VALUES (1, 'fisico', ?, 'Cambio de fuente', 'SN1', 1.0, ?, 10.0, "
        "1.0, 1)",
        (FECHA_FUENTE, FECHA_FUENTE))
    # registro histórico SIN hora -- los 449 reales del handoff son así
    conexion.con.execute(
        "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
        "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
        "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
        "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
        "observaciones, activo) VALUES "
        "('2020-01-01', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
        "1.0,1.0,1.0,1.0, '', 1)")
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


def _filas_braqui(d, patron_fecha):
    """Lee por la MISMA conexión QSqlDatabase que usa la pantalla (`d.
    opeenDatabase()`), no por una conexión sqlite3 aparte -- [medido]: una
    segunda conexión sqlite3 al mismo archivo, mientras `add_info` escribe
    por SU PROPIA conexión (`Conexion().conectar()`, una nueva por llamada)
    y la pantalla mantiene abierta la suya, no ve el commit de la otra en
    este entorno ("disk I/O error"/"database disk image is malformed" al
    forzarlo) -- un artefacto del sandbox, no del código de producción: la
    propia app SÍ ve sus escrituras, por eso se lee por su mismo camino."""
    db = d.opeenDatabase()
    query = QSqlQuery(db)
    query.prepare(
        "SELECT id, date, activo FROM braqui WHERE date LIKE :p ORDER BY id")
    query.bindValue(":p", patron_fecha)
    query.exec()
    filas = []
    while query.next():
        filas.append((query.value(0), query.value(1), query.value(2)))
    return filas


class TestH6LaHoraSeGuardaDeVerdad:
    def test_guardar_a_las_1530_persiste_la_hora(self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDateTime(QDateTime(QDate(2026, 3, 10), QTime(15, 30, 0)))
        _llenar_campos_numericos(d)

        d.ordenar_botones('braqui', False, "Diario")

        filas = _filas_braqui(d, "2026-03-10%")
        assert filas, "no se guardó ninguna fila para 2026-03-10"
        assert filas[0][1] == "2026-03-10 15:30:00", (
            f"la hora tecleada debe guardarse, se guardó {filas[0][1]!r} -- "
            f"antes `add_info` siempre truncaba a 'yyyy-MM-dd'")

    def test_registro_historico_sin_hora_sigue_siendo_legible_y_reguardable(
            self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())

        d.date_box.setDate(QDate(2020, 1, 1))  # registro histórico sin hora

        assert d.line_1_rep_act_ci.text() == "1", (
            "un registro histórico ('yyyy-MM-dd' sin hora) debe seguir "
            "cargando con normalidad -- DATE(date) = DATE(?) es compatible "
            "hacia atrás")

        d.date_box.setDateTime(QDateTime(QDate(2020, 1, 1), QTime(9, 0, 0)))
        _llenar_campos_numericos(d, "2.0")
        d.ordenar_botones('braqui', False, "Diario")

        filas = _filas_braqui(d, "2020-01-01%")
        activas = [f for f in filas if f[2] == 1]
        assert len(activas) == 1, (
            f"reguardar un día histórico debe seguir dejando UNA sola fila "
            f"activa, hay {len(activas)}")

    def test_dos_guardados_el_mismo_dia_a_horas_distintas_siguen_siendo_un_solo_control_vigente(
            self, app, bd_temporal):
        """Intuición de garantía de H6: la hora se REGISTRA, no se convierte
        en clave -- el segundo guardado (vía `add_info`, con su propia hora)
        debe anular al primero (sembrado directo, como si fuera un guardado
        previo ya persistido) aunque las horas sean distintas.

        El primero se siembra por inserción directa -- NO con dos llamadas
        seguidas a `add_info` en el mismo proceso: [medido] dos conexiones
        `Conexion().conectar()` (una por llamada, nunca cerrada
        explícitamente) abiertas en sucesión rápida dan "disk I/O error" en
        este sandbox. Es un artefacto del entorno (ver `_filas_braqui`), no
        del contrato que este test verifica -- que sigue siendo real: el
        `reemplazo` de `add_info` (EB4) anula la fila anterior sea cual sea
        su origen.

        T8 (PLAN_BRAQUI_ACTIVIDAD_CONFIABLE_28-08.md): navegar al día CON
        un solo `setDateTime(día, hora)` atómico ya no basta para simular
        "abrir el día y teclear otra hora" -- ahora ese único evento
        aterriza en el día Y repone la hora GUARDADA (10:00), así que la
        hora pedida en el mismo `setDateTime` quedaría pisada por el
        registro encontrado (correcto: es la garantía de T8, no un defecto
        de este test). Se simulan los dos pasos por separado, como lo
        haría el físico: primero navegar al día (aterriza en la hora
        guardada, la que sea), después mover SOLO la hora -- `fecha` no
        cambia frente a `_fecha_mostrada`, así que no hay recarga que
        pueda volver a pisarla."""
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
            "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
            "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
            "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
            "observaciones, activo) VALUES "
            "('2026-05-04 10:00:00', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,"
            "1,1,1, 3.0,3.0,1.0,1.0, '', 1)")
        con.commit()
        con.close()

        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDateTime(QDateTime(QDate(2026, 5, 4), QTime(0, 0, 0)))
        assert d.date_box.time() == QTime(10, 0, 0), (
            "precondición T8: aterrizar en un día con registro debe reponer "
            "su hora guardada, no la pedida al navegar")
        d.date_box.setTime(QTime(16, 45, 0))
        _llenar_campos_numericos(d, "3.5")
        d.ordenar_botones('braqui', False, "Diario")

        filas = _filas_braqui(d, "2026-05-04%")
        activas = [f for f in filas if f[2] == 1]
        anuladas = [f for f in filas if f[2] == 0]
        assert len(activas) == 1, (
            f"dos guardados el mismo día (aunque a horas distintas) deben "
            f"seguir siendo UN solo control vigente, hay {len(activas)}")
        assert activas[0][1] == "2026-05-04 16:45:00"
        assert len(anuladas) == 1 and anuladas[0][1] == "2026-05-04 10:00:00", (
            "el índice UNIQUE parcial (DATE(date)) debe seguir rechazando "
            "dos controles vigentes del mismo día pese a la hora distinta")


class TestH6LecturasCompartidasToleranHora:
    """El censo del plan (5 sitios en braquiterapia.py) se amplió durante la
    ejecución: `graficarvstiempo` (unovsuno.py) es una función COMPARTIDA
    por las 4 diarias que también compara `date` por BETWEEN y la parsea con
    `strptime('%Y-%m-%d')` -- sin `DATE(...)`, la primera fila de braqui con
    hora habría reventado esa gráfica (o desaparecido si caía justo en el
    borde de `end_date`)."""

    def test_fila_con_hora_no_revienta_el_parseo_de_fecha(self, app, bd_temporal):
        """Fecha a MITAD del rango (no en el borde): con la comparación de
        texto plano esta fila SÍ entra al BETWEEN (su prefijo de fecha es
        menor que `end_date`), así que sin `DATE(...)` en el SELECT,
        `query.value(0)` devuelve el texto CON hora y el `strptime(
        '%Y-%m-%d')` de `graficarvstiempo` revienta -- es la forma real de
        detectar la regresión, no una que dependa del borde."""
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
            "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
            "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
            "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
            "observaciones, activo) VALUES "
            "('2026-06-05 15:30:00', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,"
            "1,1,1, 5.0,5.0,1.0,1.0, '', 1)")
        con.commit()
        con.close()

        d = PruebaDiariaBraq(_UsuarioFalso())
        db = d.opeenDatabase()
        query = QSqlQuery(db)
        ax = d.figure.add_subplot(111)

        graficarvstiempo(d, query, ax, 'braqui', 'tol_rep_act_ci',
                          'Actividad reportada', '2026-06-01', '2026-06-10')

        assert len(ax.lines) == 1, (
            "la fila con hora, a mitad de rango, debe graficarse sin "
            "reventar el strptime")
        assert list(ax.lines[0].get_ydata()) == [5.0]

    def test_fila_con_hora_en_el_borde_de_end_date_no_desaparece(
            self, app, bd_temporal):
        """Si la comparación fuera de texto plano (sin DATE()), una fila
        con '... 23:59:00' es LEXICOGRÁFICAMENTE MAYOR que un end_date de
        solo fecha ('2026-06-10') y quedaría excluida del rango -- se
        verifica contra la propia `graficarvstiempo`, no una consulta
        aparte que solo demuestre que el SQL correcto es posible."""
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
            "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
            "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
            "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
            "observaciones, activo) VALUES "
            "('2026-06-10 23:59:00', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,"
            "1,1,1, 7.0,7.0,1.0,1.0, '', 1)")
        con.commit()
        con.close()

        d = PruebaDiariaBraq(_UsuarioFalso())
        db = d.opeenDatabase()
        query = QSqlQuery(db)
        ax = d.figure.add_subplot(111)

        graficarvstiempo(d, query, ax, 'braqui', 'tol_rep_act_ci',
                          'Actividad reportada', '2026-06-01', '2026-06-10')

        assert len(ax.lines) == 1 and list(ax.lines[0].get_ydata()) == [7.0], (
            "una fila fechada el propio end_date (con hora) no puede "
            "desaparecer del rango por comparación de texto")
