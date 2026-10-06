"""FS.2 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, DP-154): la pestaña inicial muestra los físicos correctos ANTES de «Iniciar».

Hasta FS.2 la precarga (`actualizar_fisicos`) solo corría al CAMBIAR la fecha (`date_box.dateChanged`), y la fecha ya estaba
fijada al construir la pantalla: con la pantalla abierta en el mes de un control firmado (A, B), «Iniciar» lo dejaba en
(quien abrió la sesión, NULL). Además la consulta no distinguía Mensual/Anual (un mes con control anual prestaba sus físicos
al mensual y al revés) y pasar a un mes SIN control conservaba los físicos anteriores (el control nuevo nacía con ellos).
Medido el 06-10 en `PLAN_GUARDADO_SIN_ESPESOR_Y_RESPALDOS_05-10_anexo/logs/VERIF_06-10/` (M1-M3, A1-A2, R1-R2).

Regla vigente (D2, palabras del físico): *«que el físico 1 para crear un control nuevo sea obligatoriamente el que tiene la
sesión iniciada, que para cargarla se carguen con los que se guardaron, ajustar eso tanto para el mensual como el anual»* y
*«el combo de los físicos debe ser libre de seleccionar a ambos físicos»* (vale para un control existente):

* el periodo (mes y año del mensual; año del anual) CON control -> los dos físicos guardados, combos libres (U2-bis: un
  nombre hoy inactivo se agrega al combo);
* SIN control -> Físico 1 = la sesión (se agrega si no es «Físico Médico»), BLOQUEADO; Físico 2 en «Seleccione el Físico 2…»
  y libre;
* igual al abrir la pantalla y al cambiar la fecha, en el mensual y en el anual (las 11 familias).

Pantallas reales (constructor de producción) sobre BD temporal; nunca una BD de referencia. Trampa 2: ningún QMessageBox real.
Trampa 9: las páginas se cierran con `deleteLater` + `sendPostedEvents(DeferredDelete)`.
"""
import ast
import gc
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate, QEvent
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.user import Usuario

RAIZ = Path(__file__).resolve().parent.parent
PLACEHOLDER_F1 = "Físico 1"
PLACEHOLDER_F2 = "Seleccione el Físico 2…"
HOY = QDate.currentDate()


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd(monkeypatch, tmp_path):
    ruta = str(tmp_path / "fs2.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    for n in ("Fisico A", "Fisico B", "Fisico C", "Fisico D", "Fisico E"):
        conexion.con.execute(
            "INSERT INTO users (user, fullname, active, role, rol_sistema) VALUES (?,?,1,'Físico Médico','fisico')",
            (n.replace(" ", "").lower(), n))
    conexion.con.commit()
    yield conexion.con
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.Ok))


def _sesion(nombre="Fisico C", rol="Físico Médico"):
    return Usuario(username=nombre.replace(" ", "").lower(), fullname=nombre, active=1, role=rol)


def _cerrar(p):
    p.hide()
    p.close()
    p.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


def _controles(con, control=None):
    sql = "SELECT id, equipo, control, fecha, user_id, user_id_f2 FROM controles"
    if control:
        return con.execute(sql + " WHERE control = ? ORDER BY id", (control,)).fetchall()
    return con.execute(sql + " ORDER BY id").fetchall()


def _sembrar(con, equipo, control, fecha, f1, f2=None, activo=1):
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha, user_id, user_id_f2, activo) VALUES (?,?,?,?,?,?)",
        (equipo, control, fecha, f1, f2, activo))
    con.commit()
    return cur.lastrowid


def _fecha_de(control, qdate):
    """Cómo guarda la fecha cada tipo: el mensual con el día («dd/MM/yyyy»), el anual por mes («MM/yyyy»)."""
    return qdate.toString("dd/MM/yyyy" if control == "Mensual" else "MM/yyyy")


def _combos(p):
    return p.fisico1.currentText(), p.fisico2.currentText()


# ------------------------------------------------------------------------------------------ las 11 familias
def _crear(familia, sesion):
    if familia == "600_mensual":
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        return PruebaMensual600(sesion, equipo_f="Clinac 600")
    if familia == "ix_mensual":
        from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
        return PruebaMensualIX(sesion)
    if familia == "halcyon_mensual":
        from ui.paginasControles.PruebasMensuales.halcyon_mensual import PruebaMensualHc
        return PruebaMensualHc(sesion)
    if familia == "tomografo_mensual":
        from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
        return PruebaMensualTAC(sesion)
    if familia == "600_anual":
        from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
        return PruebaAnual600(sesion, equipo_f="Clinac 600")
    if familia == "ix_anual":
        from ui.paginasControles.PruebasAnuales.ix_anual import PruebaAnualIX
        return PruebaAnualIX(sesion)
    if familia == "halcyon_anual":
        from ui.paginasControles.PruebasAnuales.halcyon_anual import PruebaAnualHalcyon
        return PruebaAnualHalcyon(sesion)
    if familia == "imagenes_ix_anual":
        from ui.paginasControles.PruebasAnuales.ix_anual import PruebaImagenesIX
        return PruebaImagenesIX(sesion, ref=None)
    if familia == "imagenes_halcyon_anual":
        from ui.paginasControles.PruebasAnuales.halcyon_anual import PruebaImagenesHalcyon
        return PruebaImagenesHalcyon(sesion, ref=None)
    if familia == "imagenes_ix_mensual":
        from ui.paginasControles.PruebasMensuales.ix_imagenes_mensual import PruebaImagenesIX
        return PruebaImagenesIX(sesion, ref=None)
    if familia == "imagenes_halcyon_mensual":
        from ui.paginasControles.PruebasMensuales.HC_imagenes_mensual import PruebaImagenesHC
        return PruebaImagenesHC(sesion, ref=None)
    raise AssertionError(familia)


# familia -> (equipo con el que guarda `controles.equipo`, tipo de control)
FAMILIAS = {
    "600_mensual": ("Clinac 600", "Mensual"),
    "ix_mensual": ("Clinac ix", "Mensual"),
    "halcyon_mensual": ("Halcyon", "Mensual"),
    "tomografo_mensual": ("Tomógrafo", "Mensual"),
    "600_anual": ("Clinac 600", "Anual"),
    "ix_anual": ("Clinac ix", "Anual"),
    "halcyon_anual": ("Halcyon", "Anual"),
    "imagenes_ix_anual": ("Clinac ix", "Anual"),
    "imagenes_halcyon_anual": ("Halcyon", "Anual"),
    "imagenes_ix_mensual": ("Clinac ix", "Mensual"),
    "imagenes_halcyon_mensual": ("Halcyon", "Mensual"),
}


class TestLasOnceFamiliasMuestranLosFisicosAlAbrir:

    @pytest.mark.parametrize("familia", sorted(FAMILIAS))
    def test_al_abrir_en_un_periodo_con_control_muestra_los_dos_fisicos_guardados_y_los_deja_libres(self, app, bd, familia):
        equipo, control = FAMILIAS[familia]
        _sembrar(bd, equipo, control, _fecha_de(control, HOY), "Fisico A", "Fisico B")
        p = _crear(familia, _sesion("Fisico C"))
        try:
            assert _combos(p) == ("Fisico A", "Fisico B"), f"{familia}: los combos dicen {_combos(p)}"
            assert p.fisico1.isEnabled() and p.fisico2.isEnabled()
            assert p.user_id_f1 == p.fisico1.currentData() and p.user_id_f2 == p.fisico2.currentData()
        finally:
            _cerrar(p)

    @pytest.mark.parametrize("familia", sorted(FAMILIAS))
    def test_al_abrir_en_un_periodo_sin_control_el_fisico_1_es_la_sesion_bloqueado_y_el_2_queda_libre(self, app, bd, familia):
        p = _crear(familia, _sesion("Fisico C"))
        try:
            assert _combos(p) == ("Fisico C", PLACEHOLDER_F2), f"{familia}: {_combos(p)}"
            assert not p.fisico1.isEnabled(), "el Físico 1 de un control nuevo es la sesión: bloqueado"
            assert p.fisico2.isEnabled()
            assert p.user_id_f1 == p.fisico1.currentData() and p.user_id_f2 is None
        finally:
            _cerrar(p)

    @pytest.mark.parametrize("familia", sorted(FAMILIAS))
    def test_al_mover_la_fecha_a_otro_periodo_y_volver_se_recalculan_los_combos(self, app, bd, familia):
        equipo, control = FAMILIAS[familia]
        _sembrar(bd, equipo, control, _fecha_de(control, HOY), "Fisico A", "Fisico B")
        p = _crear(familia, _sesion("Fisico C"))
        try:
            otro = HOY.addYears(-1) if control == "Anual" else HOY.addMonths(-2)      # un periodo SIN control
            p.date_box.setDate(otro)
            assert _combos(p) == ("Fisico C", PLACEHOLDER_F2), f"{familia} sin control: {_combos(p)}"
            assert not p.fisico1.isEnabled() and p.fisico2.isEnabled()
            p.date_box.setDate(HOY)
            assert _combos(p) == ("Fisico A", "Fisico B")
            assert p.fisico1.isEnabled() and p.fisico2.isEnabled()
        finally:
            _cerrar(p)


class TestIdaYVueltaConElEscritorReal:
    """Nadie siembra el control: «Iniciar» lo escribe con el codigo de produccion y una pantalla NUEVA de la misma familia lo tiene
    que encontrar. Las demas pruebas siembran el control con el equipo que se CREE que escribe cada familia (`FAMILIAS`); como la
    precarga compara el equipo EXACTO (DA-15), si `create_control` escribiera otra grafia que `self.equipo_f` la precarga no
    encontraria nunca el control y todas las sembradas pasarian igual."""

    @pytest.mark.parametrize("familia", sorted(FAMILIAS))
    def test_lo_que_escribe_iniciar_lo_vuelve_a_encontrar_la_precarga(self, app, bd, familia):
        equipo_esperado, tipo = FAMILIAS[familia]
        p = _crear(familia, _sesion("Fisico C"))
        try:
            assert _combos(p) == ("Fisico C", PLACEHOLDER_F2)
            p.fisico2.setCurrentIndex(p.fisico2.findText("Fisico D"))
            p.iniciar.click()
        finally:
            _cerrar(p)
        filas = _controles(bd)
        assert len(filas) == 1, f"{familia}: Iniciar debia crear UN control, hay {filas}"
        _, equipo_escrito, tipo_escrito, _, f1, f2 = filas[0]
        assert (f1, f2) == ("Fisico C", "Fisico D"), filas
        assert tipo_escrito == tipo, f"{familia}: escribio tipo {tipo_escrito!r}, la familia declara {tipo!r}"
        assert equipo_escrito == equipo_esperado, f"{familia}: escribio equipo {equipo_escrito!r}, la familia declara {equipo_esperado!r}"
        q = _crear(familia, _sesion("Fisico C"))
        try:
            assert _combos(q) == ("Fisico C", "Fisico D"), f"{familia}: la precarga no encontro el control recien escrito: {_combos(q)}"
            assert q.fisico1.isEnabled() and q.fisico2.isEnabled()
        finally:
            _cerrar(q)


# ------------------------------------------------------------------------- las filas medidas de H3 (06-10)
class TestLasFilasMedidasDeH3:

    def test_m1_el_mensual_abierto_en_el_mes_de_un_control_firmado_muestra_a_sus_firmantes(self, app, bd):
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        _sembrar(bd, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico A", "Fisico B")
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            assert _combos(p) == ("Fisico A", "Fisico B")
        finally:
            _cerrar(p)

    def test_m3_iniciar_sin_tocar_la_fecha_no_cambia_los_firmantes_del_control_existente(self, app, bd):
        """Rojo hoy: el control pasaba de (A, B) a (la sesión, NULL)."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        viejo = _sembrar(bd, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico A", "Fisico B")
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            p.iniciar.click()
            assert _controles(bd) == [(viejo, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico A", "Fisico B")]
        finally:
            _cerrar(p)

    def test_iniciar_sobre_un_control_existente_sigue_actualizando_con_lo_que_muestren_los_combos(self, app, bd):
        """D2: se conserva («si así está funcionando así debería seguir»)."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        _sembrar(bd, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico A", "Fisico B")
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            p.fisico2.setCurrentIndex(p.fisico2.findText("Fisico D"))
            p.iniciar.click()
            assert _controles(bd)[0][4:6] == ("Fisico A", "Fisico D")
        finally:
            _cerrar(p)

    def _pasar_por_el_mes_del_control(self, p):
        """Lleva la fecha al mes CON control por `dateChanged` (la única vía que existía antes de FS.2) para que los combos
        muestren a los firmantes y SOLO ENTONCES pasar a un mes sin control: sin este paso la pantalla de `HEAD` nunca llega a
        mostrar a (A, B) y la prueba no reproduce R2 (pasaba en `HEAD` sin merecerlo)."""
        p.date_box.setDate(HOY.addMonths(-1))
        p.date_box.setDate(HOY)
        assert _combos(p) == ("Fisico A", "Fisico B"), "el mes del control debe mostrar a sus firmantes"

    def test_r2_pasar_a_un_mes_sin_control_no_deja_los_fisicos_del_mes_anterior(self, app, bd):
        """Rojo hoy: al pasar al mes siguiente (sin control) los combos conservaban (A, B), los del mes que se acababa de dejar."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        _sembrar(bd, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico A", "Fisico B")
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            self._pasar_por_el_mes_del_control(p)
            p.date_box.setDate(HOY.addMonths(1))
            assert _combos(p) == ("Fisico C", PLACEHOLDER_F2)
        finally:
            _cerrar(p)

    def test_r2_el_control_nuevo_de_un_mes_sin_control_nace_con_la_sesion_no_con_los_del_mes_anterior(self, app, bd):
        """Rojo hoy: nacía con (A, B), los del mes que se acababa de dejar."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        viejo = _sembrar(bd, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico A", "Fisico B")
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            self._pasar_por_el_mes_del_control(p)
            p.date_box.setDate(HOY.addMonths(1))
            p.iniciar.click()
            nuevo = [f for f in _controles(bd) if f[0] != viejo]
            assert len(nuevo) == 1 and nuevo[0][4:6] == ("Fisico C", None), nuevo
            assert _controles(bd)[0][4:6] == ("Fisico A", "Fisico B"), "el control del mes anterior no se toca"
        finally:
            _cerrar(p)

    def test_iniciar_en_un_periodo_sin_control_deja_la_pantalla_y_la_bd_con_el_mismo_fisico_1(self, app, bd):
        """Hallazgo R-A3/R-B3 de la revisión de FS.1: `self.nombre_fisico1` (texto del combo) alimenta
        `configuracion_picketfence.fisico_1` y Starshot; tiene que ser el mismo que `controles.user_id` (la sesión). Con el combo
        LIBRE en un periodo sin control las dos podían diferir: lo que lo vuelve una garantía y no una coincidencia es que el
        combo del Físico 1 esté bloqueado en la sesión antes de «Iniciar»."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            assert not p.fisico1.isEnabled(), "sin control, el Físico 1 no se puede cambiar: es la sesión"
            p.iniciar.click()
            fila = _controles(bd)[0]
            assert fila[4] == "Fisico C" and p.nombre_fisico1 == fila[4]
        finally:
            _cerrar(p)

    def test_a2_el_anual_con_el_combo_en_su_fisico_1_no_se_reescribe_con_la_sesion_al_iniciar(self, app, bd):
        from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
        viejo = _sembrar(bd, "Clinac 600", "Anual", HOY.toString("MM/yyyy"), "Fisico A", "Fisico B")
        p = PruebaAnual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            assert _combos(p) == ("Fisico A", "Fisico B")
            p.iniciar.click()
            assert _controles(bd) == [(viejo, "Clinac 600", "Anual", HOY.toString("MM/yyyy"), "Fisico A", "Fisico B")]
        finally:
            _cerrar(p)


# --------------------------------------------------------------------------- la mezcla anual / mensual
class TestElAnualYElMensualNoSeMezclan:

    def _sembrar_mezcla(self, bd):
        _sembrar(bd, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico D", "Fisico E")
        _sembrar(bd, "Clinac 600", "Anual", HOY.toString("MM/yyyy"), "Fisico A", "Fisico B")

    def test_el_mensual_de_un_mes_con_control_anual_muestra_los_del_mensual(self, app, bd):
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        self._sembrar_mezcla(bd)
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            assert _combos(p) == ("Fisico D", "Fisico E")
            p.date_box.setDate(HOY.addMonths(-2))
            p.date_box.setDate(HOY)
            assert _combos(p) == ("Fisico D", "Fisico E")
        finally:
            _cerrar(p)

    def test_el_anual_de_un_anio_con_control_mensual_muestra_los_del_anual(self, app, bd):
        from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
        self._sembrar_mezcla(bd)
        p = PruebaAnual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            assert _combos(p) == ("Fisico A", "Fisico B")
            p.date_box.setDate(HOY.addMonths(-2) if HOY.month() > 2 else HOY.addMonths(1))     # otro mes del MISMO año
            assert _combos(p) == ("Fisico A", "Fisico B")
        finally:
            _cerrar(p)

    def test_iniciar_el_anual_en_un_mes_con_control_mensual_no_toma_el_segundo_fisico_del_mensual(self, app, bd):
        """R1 de la verificación del 06-10: el anual quedaba en (la sesión, Físico 2 del MENSUAL)."""
        from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
        self._sembrar_mezcla(bd)
        p = PruebaAnual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            p.iniciar.click()
            assert _controles(bd, "Anual")[0][4:6] == ("Fisico A", "Fisico B")
            assert _controles(bd, "Mensual")[0][4:6] == ("Fisico D", "Fisico E"), "el mensual no se toca"
        finally:
            _cerrar(p)

    def test_imagenes_anual_abre_con_los_fisicos_del_anual_y_iniciar_no_los_reescribe(self, app, bd):
        """El defecto H4 + H3 juntos (hallazgo R-A1/R-B1 de la revisión de FS.1): «Imágenes anual» identifica el control por el
        año y precarga a sus firmantes; sin la precarga al abrir, «Iniciar» reescribía el anual con (sesión, NULL)."""
        from ui.paginasControles.PruebasAnuales.ix_anual import PruebaImagenesIX
        mes = 2 if HOY.month() != 2 else 3
        viejo = _sembrar(bd, "Clinac ix", "Anual", f"{mes:02d}/{HOY.year()}", "Fisico A", "Fisico B")
        p = PruebaImagenesIX(_sesion("Fisico C"), ref=None)
        try:
            assert _combos(p) == ("Fisico A", "Fisico B")
            p.iniciar.click()
            assert _controles(bd, "Anual") == [(viejo, "Clinac ix", "Anual", f"{mes:02d}/{HOY.year()}", "Fisico A", "Fisico B")]
        finally:
            _cerrar(p)


# -------------------------------------------------------------------------------- la sesión y los inactivos
class TestLaSesionYLosInactivos:

    def test_una_sesion_que_no_es_fisico_medico_aparece_como_fisico_1_bloqueado_y_puede_iniciar(self, app, bd):
        """El administrador abre un control nuevo: hoy el combo queda en «Físico 1» y «Iniciar» se bloquea."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        p = PruebaMensual600(_sesion("Administrador", "admin"), equipo_f="Clinac 600")
        try:
            assert _combos(p) == ("Administrador", PLACEHOLDER_F2)
            assert not p.fisico1.isEnabled()
            assert p.user_id_f1 == bd.execute("SELECT id FROM users WHERE fullname='Administrador'").fetchone()[0]
            p.iniciar.click()
            assert _controles(bd)[0][4:6] == ("Administrador", None)
        finally:
            _cerrar(p)

    def test_un_firmante_hoy_inactivo_se_agrega_al_combo_con_su_id_y_iniciar_no_lo_borra(self, app, bd):
        """U2-bis, ahora también al ABRIR: el nombre guardado se agrega al combo CON su `id` (sin él, `user_id_f2` quedaba en
        None y «Iniciar» dejaba el control sin segundo físico)."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        bd.execute("UPDATE users SET active = 0 WHERE fullname IN ('Fisico A', 'Fisico B')")
        bd.commit()
        viejo = _sembrar(bd, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico A", "Fisico B")
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            assert _combos(p) == ("Fisico A", "Fisico B")
            assert p.fisico2.currentData() == bd.execute("SELECT id FROM users WHERE fullname='Fisico B'").fetchone()[0]
            p.iniciar.click()
            assert _controles(bd)[0][0] == viejo and _controles(bd)[0][4:6] == ("Fisico A", "Fisico B")
        finally:
            _cerrar(p)

    def test_un_control_sin_segundo_fisico_repone_el_marcador_al_pasar_de_uno_con_dos(self, app, bd):
        """Con control pero SIN segundo físico guardado, el Físico 2 vuelve al marcador (no conserva el del mes anterior)."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        _sembrar(bd, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico A", "Fisico B")
        siguiente = HOY.addMonths(1)
        _sembrar(bd, "Clinac 600", "Mensual", siguiente.toString("dd/MM/yyyy"), "Fisico D", None)
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            assert _combos(p) == ("Fisico A", "Fisico B")
            p.date_box.setDate(siguiente)
            assert _combos(p) == ("Fisico D", PLACEHOLDER_F2)
            assert p.fisico1.isEnabled() and p.fisico2.isEnabled()
        finally:
            _cerrar(p)

    def test_el_marcador_solo_se_repone_si_el_primer_item_no_lleva_dato(self, app):
        """`_seleccionar_fisico(cursor, combo, None)`: el marcador es el primer ítem SIN dato; un combo cuyo primer ítem es un
        físico (lleva `id`) no se toca."""
        from PyQt5.QtWidgets import QComboBox
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        con_marcador, sin_marcador = QComboBox(), QComboBox()
        con_marcador.addItem("Seleccione el Físico 2…")
        con_marcador.addItem("Fisico A", 2)
        con_marcador.setCurrentIndex(1)
        sin_marcador.addItem("Fisico A", 2)
        sin_marcador.addItem("Fisico B", 3)
        sin_marcador.setCurrentIndex(1)
        PruebaMensual600._seleccionar_fisico(None, con_marcador, None)
        PruebaMensual600._seleccionar_fisico(None, sin_marcador, None)
        assert con_marcador.currentIndex() == 0
        assert sin_marcador.currentText() == "Fisico B", "sin marcador no hay a qué volver: no se toca"

    def test_un_control_anulado_no_presta_sus_fisicos(self, app, bd):
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        _sembrar(bd, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico A", "Fisico B", activo=0)
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            assert _combos(p) == ("Fisico C", PLACEHOLDER_F2)
        finally:
            _cerrar(p)

    def test_un_objeto_sin_sesion_no_cambia_nada_conducta_de_hoy(self, app, bd):
        """Las pruebas antiguas construyen pantallas con `user_id=None`: sin sesión no hay Físico 1 que imponer ni que bloquear."""
        from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
        p = PruebaMensualTAC(user_id=None)
        try:
            assert p.fisico1.isEnabled()
        finally:
            _cerrar(p)


# ------------------------------------------------- lo que el fisico eligio no se pierde y lo de otro periodo no se arrastra
def _dia_de_este_mes_distinto_de_hoy():
    """Otro dia del MISMO mes (y por tanto del mismo anio): el periodo no cambia, solo cambia el dia."""
    return QDate(HOY.year(), HOY.month(), 15 if HOY.day() != 15 else 14)


def _nombres(combo):
    return [combo.itemText(i) for i in range(combo.count())]


class TestRevisionEscepticaDeFS2:
    """Hallazgos H1-H3 y huecos de la prueba que dejo la revision escéptica de FS.2 (06-10-2026); cada uno se reprodujo aqui
    (rojo) antes de tocar produccion."""

    @pytest.mark.parametrize("familia", sorted(FAMILIAS))
    def test_h1_el_fisico_2_elegido_en_un_periodo_sin_control_sobrevive_a_cambiar_el_dia(self, app, bd, familia):
        """En un periodo SIN control el Fisico 2 es libre: corregir el dia de la fecha dentro del MISMO periodo no lo devuelve al
        marcador (en HEAD se conservaba; perderlo en silencio deja el control sin segundo fisico sin que nadie lo note)."""
        p = _crear(familia, _sesion("Fisico C"))
        try:
            p.fisico2.setCurrentIndex(p.fisico2.findText("Fisico D"))
            p.date_box.setDate(_dia_de_este_mes_distinto_de_hoy())
            assert _combos(p) == ("Fisico C", "Fisico D"), f"{familia}: {_combos(p)}"
            assert not p.fisico1.isEnabled() and p.fisico2.isEnabled()
        finally:
            _cerrar(p)

    def test_h1_pero_lo_que_viene_de_un_control_guardado_si_se_repone_al_salir_de_el(self, app, bd):
        """R2 sigue en pie: si el Fisico 2 que se ve venia de un control GUARDADO (no de una eleccion del fisico) y el periodo pasa a
        no tener control, vuelve al marcador."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        _sembrar(bd, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico A", "Fisico B")
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            assert _combos(p) == ("Fisico A", "Fisico B")
            p.date_box.setDate(HOY.addMonths(1))
            assert _combos(p) == ("Fisico C", PLACEHOLDER_F2)
            p.fisico2.setCurrentIndex(p.fisico2.findText("Fisico D"))
            p.date_box.setDate(HOY.addMonths(2))                    # otro periodo SIN control: la eleccion del fisico se conserva
            assert _combos(p) == ("Fisico C", "Fisico D")
        finally:
            _cerrar(p)

    def test_con_control_cambiar_el_dia_recarga_los_firmantes_guardados(self, app, bd):
        """Conducta que se conserva de HEAD: con control, lo que se ve es lo guardado; mover la fecha dentro del periodo lo recarga."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        _sembrar(bd, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico A", "Fisico B")
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            p.fisico2.setCurrentIndex(p.fisico2.findText("Fisico D"))
            p.date_box.setDate(_dia_de_este_mes_distinto_de_hoy())
            assert _combos(p) == ("Fisico A", "Fisico B")
        finally:
            _cerrar(p)

    def test_h2_un_control_sin_fisico_1_guardado_muestra_el_marcador_y_no_el_del_periodo_anterior(self, app, bd):
        """Un control SIN Fisico 1 guardado (user_id NULL): el combo no arrastra el Fisico 1 del periodo que se acaba de dejar; muestra
        el marcador (lo que no esta guardado no se inventa) y Iniciar pide elegir uno."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        _sembrar(bd, "Clinac 600", "Mensual", HOY.addMonths(-1).toString("dd/MM/yyyy"), "Fisico A", "Fisico B")
        _sembrar(bd, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), None, None)
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            p.date_box.setDate(HOY.addMonths(-1))
            assert _combos(p) == ("Fisico A", "Fisico B")
            p.date_box.setDate(HOY)
            assert _combos(p) == (PLACEHOLDER_F1, PLACEHOLDER_F2), f"arrastro lo del periodo anterior: {_combos(p)}"
            assert p.fisico1.isEnabled() and p.fisico2.isEnabled()
            assert p.user_id_f1 is None and p.user_id_f2 is None
        finally:
            _cerrar(p)

    def test_h3_un_firmante_hoy_inactivo_no_queda_como_candidato_de_un_control_nuevo(self, app, bd):
        """U2: un fisico inactivo no se ofrece para un control NUEVO. FS.2 lo agrega al combo para mostrar al firmante real de un
        control existente; al pasar a un periodo sin control esa entrada se retira (la lista vuelve a ser la de candidatos)."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        bd.execute("UPDATE users SET active = 0 WHERE fullname = 'Fisico B'")
        bd.commit()
        _sembrar(bd, "Clinac 600", "Mensual", HOY.addMonths(-1).toString("dd/MM/yyyy"), "Fisico A", "Fisico B")
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            candidatos_f1, candidatos_f2 = _nombres(p.fisico1), _nombres(p.fisico2)
            assert "Fisico B" not in candidatos_f2, "precondicion: el inactivo no es candidato"
            p.date_box.setDate(HOY.addMonths(-1))
            assert _combos(p) == ("Fisico A", "Fisico B")
            p.date_box.setDate(HOY)                                  # periodo sin control
            assert _nombres(p.fisico1) == candidatos_f1 and _nombres(p.fisico2) == candidatos_f2, (
                f"quedo un candidato agregado: {_nombres(p.fisico1)} / {_nombres(p.fisico2)}")
        finally:
            _cerrar(p)

    def test_hueco_el_firmante_que_reabre_su_propio_control_lo_encuentra_con_los_combos_libres(self, app, bd):
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        _sembrar(bd, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico C", "Fisico B")
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            assert _combos(p) == ("Fisico C", "Fisico B")
            assert p.fisico1.isEnabled() and p.fisico2.isEnabled(), "control existente: combos libres, tambien para su propio firmante"
        finally:
            _cerrar(p)

    def test_hueco_un_nombre_con_espacio_inicial_se_encuentra_tal_cual_y_conserva_su_id(self, app, bd):
        """Existe un `users.fullname` real con espacio inicial (' Andres David Loaiza Baena'): el nombre se compara EXACTO, sin
        recortarlo, y el control se guarda con ese mismo texto."""
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        bd.execute("INSERT INTO users (user, fullname, active, role, rol_sistema) VALUES ('espacio', ' Fisico Espacio', 1, "
                   "'Físico Médico', 'fisico')")
        bd.commit()
        id_espacio = bd.execute("SELECT id FROM users WHERE fullname = ' Fisico Espacio'").fetchone()[0]
        viejo = _sembrar(bd, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico A", " Fisico Espacio")
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            assert _combos(p) == ("Fisico A", " Fisico Espacio")
            assert p.fisico2.currentData() == id_espacio and p.user_id_f2 == id_espacio
            p.iniciar.click()
            assert _controles(bd) == [(viejo, "Clinac 600", "Mensual", HOY.toString("dd/MM/yyyy"), "Fisico A", " Fisico Espacio")]
        finally:
            _cerrar(p)


# --------------------------------------------------------------------- una sola regla de identidad (tripwire)
def _produccion():
    for carpeta in ("ui", "data", "services", "models", "scripts"):
        for ruta in (RAIZ / carpeta).rglob("*.py"):
            yield ruta
    yield RAIZ / "main.py"


class TestUnaSolaReglaDeIdentidadEnProduccion:

    def test_ningun_archivo_de_produccion_usa_mismo_mes_para_decidir_el_control_de_un_periodo(self):
        """La regla «el mismo mes» vive en `services/identidad_control.py::periodo`. `mismo_mes` (el bucle por mes de la
        precarga) no debe volver a importarse ni llamarse fuera de su propio módulo."""
        sospechosos = []
        for ruta in _produccion():
            if not ruta.exists() or ruta.name == "fechas_control.py":
                continue
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
            for n in ast.walk(arbol):
                if isinstance(n, ast.ImportFrom) and any(a.name == "mismo_mes" for a in n.names):
                    sospechosos.append(f"{ruta.relative_to(RAIZ)}:{n.lineno} importa mismo_mes")
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("mismo_mes", "_mismo_mes"):
                    sospechosos.append(f"{ruta.relative_to(RAIZ)}:{n.lineno} llama {n.func.id}")
        assert not sospechosos, sospechosos

    def test_la_precarga_de_fisicos_usa_la_funcion_unica_de_identidad(self):
        arbol = ast.parse((RAIZ / "ui/paginasControles/PruebasMensuales/seiscientos_mensual.py").read_text(encoding="utf-8"))
        clase = next(n for n in arbol.body if isinstance(n, ast.ClassDef) and n.name == "PruebaMensual600")
        funcion = next(n for n in clase.body if isinstance(n, ast.FunctionDef) and n.name == "actualizar_fisicos")
        llamadas = {n.func.id if isinstance(n.func, ast.Name) else n.func.attr
                    for n in ast.walk(funcion) if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))}
        assert "buscar_control_vigente" in llamadas
        consultas = [ast.unparse(n) for n in ast.walk(funcion)
                     if isinstance(n, (ast.Constant, ast.JoinedStr)) and "FROM controles" in ast.unparse(n)]
        assert consultas == [], "actualizar_fisicos vuelve a buscar el control por su cuenta"

    def test_preINIGI_aplica_la_regla_una_vez_al_construir_la_pantalla(self):
        arbol = ast.parse((RAIZ / "ui/paginasControles/PruebasMensuales/seiscientos_mensual.py").read_text(encoding="utf-8"))
        clase = next(n for n in arbol.body if isinstance(n, ast.ClassDef) and n.name == "PruebaMensual600")
        funcion = next(n for n in clase.body if isinstance(n, ast.FunctionDef) and n.name == "preINIGI")
        llamadas = [n for n in ast.walk(funcion) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "actualizar_fisicos"]
        assert len(llamadas) == 1, "preINIGI debe llamar a actualizar_fisicos exactamente una vez (la precarga al abrir)"
