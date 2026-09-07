"""E4 (PLAN_BRAQUI_HORA_EDITABLE_07-09.md): al aterrizar en un día SIN
registro, la hora pasa a ser la ACTUAL -- decisión del físico (07-09):
*"Que se ponga la actual, igual realmente ninguna de las dos es correcta
pero se nota mejor si se actualiza a la actual."*

Especificación auditada (no la primera, que rompía `test_h6`/`R-4` --
ver `E4.0`/`E4.1` del plan y `DP-87`): el reloj pone la hora SOLO cuando
nadie la eligió. `_al_mover_el_date_box` decide si la hora "venía
arrastrada" (comparándola contra `_hora_mostrada`, la que el widget tenía
ANTES de este movimiento) y se lo pasa al cargador como `hora_al_reloj`.

Tres casos, cada uno rojo por su cuenta contra el código de HOY (antes de
aplicar `E4`) -- verificados uno a uno, no en bloque, para que cada uno
falle por SU razón y no por un efecto en cascada:

  (a) navegar a un día sin registro pone la hora al reloj;
  (b) una hora ELEGIDA en el mismo cambio se respeta -- el caso que la
      primera especificación rompía (`test_h6`/`R-4`, `DP-87`);
  (c) la actividad mostrada corresponde al INSTANTE que quedó en el
      widget, no a uno recalculado con otra hora -- exige el REORDEN
      (fijar antes de recalcular)."""
import datetime
import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate, QDateTime, QTime
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from analisisImagenes.ActividadFuente import VIDA_MEDIA_IR192_DIAS
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

FECHA_CERTIFICADO = "2026-01-01 11:36:24"
A0_CI = 10.0
TOLERANCIA_RELOJ_SEGUNDOS = 10  # margen para el tiempo que tarda el test en correr


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
    """Misma reimplementación independiente de `test_e3`."""
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


class TestE4CasoA_LaHoraSePonalAlReloj:
    def test_dia_sin_registro_hora_al_reloj(self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())
        # Deja el widget con una hora vieja, claramente distinta de "ahora".
        d.date_box.setDateTime(QDateTime(QDate(2026, 9, 6), QTime(3, 0, 0)))

        # Navega SOLO el día (mismo patrón que el físico usando el
        # calendario) a un día sin registro.
        d.date_box.setDate(QDate(2026, 9, 8))

        ahora = QTime.currentTime()
        hora_widget = d.date_box.time()
        diferencia = abs(hora_widget.msecsSinceStartOfDay()
                          - ahora.msecsSinceStartOfDay())
        assert diferencia < TOLERANCIA_RELOJ_SEGUNDOS * 1000, (
            f"al aterrizar en un día sin registro la hora debía ponerse al "
            f"reloj (~{ahora.toString('HH:mm:ss')}), quedó "
            f"{hora_widget.toString('HH:mm:ss')} -- la vieja (03:00) "
            f"sigue arrastrada")


class TestE4CasoB_UnaHoraElegidaEnElMismoCambioSeRespeta:
    def test_setdatetime_con_hora_elegida_no_se_pisa(self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDateTime(QDateTime(QDate(2026, 9, 6), QTime(3, 0, 0)))

        # El físico (o un llamador directo) elige DÍA Y HORA en el MISMO
        # evento -- una hora que casi seguro no coincide con "ahora".
        hora_elegida = QTime(22, 17, 5)
        d.date_box.setDateTime(QDateTime(QDate(2026, 9, 9), hora_elegida))

        assert d.date_box.time() == hora_elegida, (
            f"una hora ELEGIDA en el mismo cambio de día NO debe pisarse "
            f"con el reloj -- quedó {d.date_box.time().toString('HH:mm:ss')}, "
            f"se eligió {hora_elegida.toString('HH:mm:ss')}. Este es "
            f"EXACTAMENTE el caso que la primera especificación de E4 "
            f"rompía (DP-87, test_h6/R-4)")


class TestE4CasoC_LaActividadCorrespondeAlInstanteQueQuedoEnElWidget:
    def test_actividad_coincide_con_el_instante_final(self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDateTime(QDateTime(QDate(2026, 9, 6), QTime(3, 0, 0)))

        d.date_box.setDate(QDate(2026, 9, 8))  # sin registro -> hora al reloj

        instante_widget = d.date_box.dateTime()
        esperado = _actividad_esperada_independiente(instante_widget)
        assert float(d.line_1_exp_act_ci.text()) == pytest.approx(esperado, rel=1e-3), (
            f"la actividad mostrada debe corresponder al INSTANTE que "
            f"quedó en el widget ({instante_widget.toString('yyyy-MM-dd HH:mm:ss')}), "
            f"no a otro -- si esto falla con un valor cercano pero distinto, "
            f"el REORDEN (fijar el instante ANTES de recalcular) no se "
            f"aplicó: la pantalla mostraría la hora nueva junto a la "
            f"actividad de un instante viejo")


class TestE4RojoDirigidoContraLaVarianteSinReorden:
    """P-6.3 / E4.PROTOCOLO paso 2: aplicar el cambio SIN el reorden --
    recalcular con el instante VIEJO (el que el widget tenía antes de
    este movimiento) y solo DESPUÉS fijar el nuevo -- y comprobar que el
    caso (c) de arriba lo caza. No se simula parcheando una función
    aislada (eso puede no reproducir el orden real, como se comprobó al
    escribir este test: un primer intento no discriminaba nada); se
    reproduce la secuencia de instrucciones tal cual sería si el orden se
    invirtiera, llamando a los métodos reales de producción en ese orden."""

    def test_variante_sin_reorden_falla_en_c(self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDateTime(QDateTime(QDate(2026, 9, 6), QTime(3, 0, 0)))
        instante_viejo = d.date_box.dateTime()

        momento_nuevo = QDateTime(QDate(2026, 9, 8), QTime.currentTime())

        # La variante mala: recalcular ANTES de fijar el instante nuevo en
        # el widget (el orden de HOY, antes de E4) -- usa el instante VIEJO.
        d._recalcular_campos_derivados_diaria(instante_viejo)
        d.date_box.blockSignals(True)
        d.date_box.setDateTime(momento_nuevo)
        d.date_box.blockSignals(False)

        instante_widget = d.date_box.dateTime()
        esperado_del_widget = _actividad_esperada_independiente(instante_widget)
        mostrado = float(d.line_1_exp_act_ci.text())
        assert mostrado != pytest.approx(esperado_del_widget, rel=1e-3), (
            f"la variante 'sin reorden' (recalcular con el instante VIEJO, "
            f"{instante_viejo.toString('yyyy-MM-dd HH:mm:ss')}, antes de "
            f"fijar el nuevo, {instante_widget.toString('yyyy-MM-dd HH:mm:ss')}) "
            f"debía producir una actividad DISTINTA de la del instante que "
            f"quedó en pantalla -- si coincide, el caso (c) no está "
            f"discriminando de verdad")


class TestE4RojoDirigidoContraElPrimerDiseno:
    """P-6.3 / E4.PROTOCOLO paso 3: quitar la bandera `hora_al_reloj`
    (reloj SIEMPRE, la primera especificación de este plan) y comprobar
    que `test_h6` y el invariante R-4 de `test_b1` caen -- es la prueba
    de que el tripwire de la garantía titular sigue vivo."""

    def test_reloj_siempre_rompe_la_hora_tecleada(self, app, bd_temporal, monkeypatch):
        original = PruebaDiariaBraq.cargar_dailytest_desde_db

        def _cargador_reloj_siempre(self, fecha=None, hora_al_reloj=False):
            return original(self, fecha, hora_al_reloj=True)

        monkeypatch.setattr(PruebaDiariaBraq, "cargar_dailytest_desde_db",
                             _cargador_reloj_siempre)

        d = PruebaDiariaBraq(_UsuarioFalso())

        # Reproduce el escenario EXACTO de test_h6 que la primera
        # especificación rompía: teclear una hora concreta sobre un día
        # SIN registro, mediante navegación (dos setDateTime seguidos,
        # como hace la UI real -- primero el día, luego el ajuste fino
        # de hora, cada uno disparando la señal).
        d.date_box.setDateTime(QDateTime(QDate(2026, 3, 9), QTime(0, 0, 0)))
        d.date_box.setDateTime(QDateTime(QDate(2026, 3, 10), QTime(15, 30, 0)))

        assert d.date_box.time() != QTime(15, 30, 0), (
            "con el reloj SIEMPRE activo, la hora tecleada (15:30) debía "
            "quedar pisada -- si esto no ocurre, el monkeypatch de este "
            "test no está reproduciendo el primer diseño y el rojo "
            "dirigido no sirve de nada")


class TestE4NoSeFueDeRama:
    """`test_t8::test_registro_historico_sin_hora_no_inventa_ninguna` no
    se toca (es intocable por decisión de este plan) -- aquí se repite su
    esencia como cinturón adicional: un registro EXISTENTE sin hora no
    debe ganar la hora del reloj."""

    def test_registro_existente_sin_hora_no_gana_el_reloj(self, app, bd_temporal):
        conn = Conexion()
        conn.con.execute(
            "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
            "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
            "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
            "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
            "observaciones, activo) VALUES "
            "('2020-01-01', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
            "1.0,1.0,1.0,1.0, '', 1)")
        conn.con.commit()

        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDateTime(QDateTime(QDate(2026, 9, 6), QTime(3, 0, 0)))
        d.date_box.setDate(QDate(2020, 1, 1))  # registro histórico, sin hora

        assert d.date_box.time() == QTime(3, 0, 0), (
            f"un registro EXISTENTE sin hora no debe inventar ninguna -- "
            f"debía conservar 03:00, quedó "
            f"{d.date_box.time().toString('HH:mm:ss')}")
