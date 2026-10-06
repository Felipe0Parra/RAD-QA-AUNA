"""FS.1 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, DP-154): UNA sola identidad de control por tipo, y el Físico 1 de
un control NUEVO es quien tiene la sesión (D2).

Hasta FS.1 había tres búsquedas del «control de este periodo», cada una con su regla: `load.py::create_control` (por mes,
filtrando `control`), `PruebaAnual600.create_control` (`fecha LIKE '%AAAA%'`) y la precarga de físicos (por mes y SIN
filtrar `control`). «Imágenes anual» usa la del mensual con tipo «Anual» -> identidad por MES -> iniciada en otro mes que
el anual, creaba un SEGUNDO control anual del mismo año (`verificacion/verif_imagenes_anual_identidad.log`). Además un
control nuevo guardaba como Físico 1 lo que dijera el combo (el mensual) o reescribía el Físico 1 de un anual existente
con la sesión (el anual).

La identidad es un dato del dominio: mensual = (equipo, «Mensual», mes y año); anual = (equipo, «Anual», año). Una sola
función (`services/identidad_control.py::buscar_control_vigente`) decide qué control vigente corresponde a
(equipo, tipo, fecha), y la regla del Físico 1 se aplica en el SERVICIO (`create_control`), no solo en la pantalla.

Cada prueba de comportamiento corre contra las pantallas reales (constructor de producción) sobre una BD temporal; nunca
una BD de referencia (el ensayo (e) copia `Rebuild_21-09` a un temporal). Trampa 2: ningún `QMessageBox` real.
Trampa 9: las páginas se cierran con `deleteLater` + `sendPostedEvents(DeferredDelete)`.
"""
import ast
import gc
import os
import shutil
import sqlite3
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate, QEvent
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.user import Usuario

RAIZ = Path(__file__).resolve().parent.parent
USUARIOS = ("Fisico A", "Fisico B", "Fisico C", "Fisico D")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd(monkeypatch, tmp_path):
    """BD temporal con cuatro físicos (A, B, C, D); `ruta_base_datos` parchado ANTES de cualquier `Conexion()`."""
    ruta = str(tmp_path / "fs1.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    for n in USUARIOS:
        conexion.con.execute(
            "INSERT INTO users (user, fullname, active, role, rol_sistema) VALUES (?,?,1,'Físico Médico','fisico')",
            (n.replace(" ", "").lower(), n))
    conexion.con.commit()
    yield conexion.con
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture(autouse=True)
def _sin_dialogos(monkeypatch):
    """Trampa 2: ningún QMessageBox real; `information` registra lo que se le pide."""
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.Ok))


def _identidad():
    """El módulo nuevo se importa DENTRO de cada prueba: contra `HEAD` las pruebas de comportamiento fallan por su razón
    (no por un ImportError de colección)."""
    import services.identidad_control as identidad
    return identidad


def _controles(con):
    return con.execute("SELECT id, equipo, control, fecha, user_id, user_id_f2, activo FROM controles ORDER BY id").fetchall()


def _sembrar(con, equipo, control, fecha, f1, f2=None, activo=1):
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha, user_id, user_id_f2, activo) VALUES (?,?,?,?,?,?)",
        (equipo, control, fecha, f1, f2, activo))
    con.commit()
    return cur.lastrowid


def _cerrar(p):
    """Libera la página DE VERDAD (Trampa 9): `deleteLater` + `gc.collect()` no bastan."""
    p.hide()
    p.close()
    p.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


def _sesion(nombre="Fisico C", rol="Físico Médico"):
    return Usuario(username=nombre.replace(" ", "").lower(), fullname=nombre, active=1, role=rol)


class _PantallaFalsa:
    """Lo mínimo que `create_control` necesita de `self`: la sesión (como `PruebaMensual600.user_id`)."""

    def __init__(self, sesion=None, **atributos):
        if sesion is not None:
            self.user_id = sesion
        for k, v in atributos.items():
            setattr(self, k, v)


# ------------------------------------------------------------------------------------------ (d) el periodo
class TestPeriodo:

    @pytest.mark.parametrize("fecha", ["15/06/2026", "06/2026", "01/06/2026", "30/06/2026"])
    def test_mensual_acepta_las_dos_formas_de_fecha_y_da_el_mismo_periodo(self, fecha):
        assert _identidad().periodo("Mensual", fecha) == (6, 2026)

    @pytest.mark.parametrize("fecha", ["15/06/2026", "06/2026", "02/2026", "31/12/2026", "2026"])
    def test_anual_es_el_anio_sin_importar_el_mes_ni_el_dia(self, fecha):
        assert _identidad().periodo("Anual", fecha) == 2026

    @pytest.mark.parametrize("tipo", ["Mensual", "Anual"])
    @pytest.mark.parametrize("fecha", ["", None, "texto", "13", "ab/cd", "06/20x6"])
    def test_una_fecha_ilegible_no_tiene_periodo(self, tipo, fecha):
        assert _identidad().periodo(tipo, fecha) is None

    @pytest.mark.parametrize("fecha", ["06/\u00b2\u00b2\u00b2\u00b2", "06/\u0662\u0660\u0662\u0666", "\u0662\u0660\u0662\u0666"])
    def test_el_anio_del_anual_solo_acepta_digitos_ascii(self, fecha):
        """Un dígito Unicode (`'²'.isdigit()` es True, pero `int('²')` lanza; el árabe-índico sí se convierte) no es un año:
        el año del anual lo lee este módulo y exige 4 dígitos ASCII (lección H7 de RB.0)."""
        assert _identidad().periodo("Anual", fecha) is None

    def test_el_dia_nunca_es_parte_de_la_identidad(self):
        identidad = _identidad()
        assert identidad.periodo("Mensual", "01/06/2026") == identidad.periodo("Mensual", "30/06/2026")
        assert identidad.periodo("Mensual", "30/06/2026") != identidad.periodo("Mensual", "30/07/2026")

    def test_un_tipo_desconocido_lanza_en_vez_de_adivinar(self):
        with pytest.raises(ValueError):
            _identidad().periodo("Diario", "06/2026")


# ------------------------------------------------------------------------------- buscar_control_vigente
class TestBuscarControlVigente:

    def _buscar(self, con, equipo, tipo, fecha):
        return _identidad().buscar_control_vigente(con.cursor(), equipo, tipo, fecha)

    def test_mensual_por_mes_y_anio(self, bd):
        a = _sembrar(bd, "Clinac 600", "Mensual", "15/06/2026", "Fisico A", "Fisico B")
        _sembrar(bd, "Clinac 600", "Mensual", "15/07/2026", "Fisico C")
        fila = self._buscar(bd, "Clinac 600", "Mensual", "01/06/2026")
        assert fila == (a, "15/06/2026", "Fisico A", "Fisico B")

    def test_las_dos_formas_de_fecha_guardada_dan_el_mismo_control(self, bd):
        """DP-32: `controles.fecha` mezcla «MM/yyyy» y «dd/MM/yyyy»; las dos deben encontrar el control del mes."""
        a = _sembrar(bd, "Clinac iX", "Mensual", "12/2025", "Fisico A")
        b = _sembrar(bd, "Clinac iX", "Mensual", "14/01/2026", "Fisico B")
        assert self._buscar(bd, "Clinac iX", "Mensual", "03/12/2025")[0] == a
        assert self._buscar(bd, "Clinac iX", "Mensual", "01/2026")[0] == b

    def test_anual_por_anio_sin_importar_el_mes_con_el_que_se_busca(self, bd):
        a = _sembrar(bd, "Clinac ix", "Anual", "02/2026", "Fisico A", "Fisico B")
        for fecha in ("02/2026", "06/10/2026", "12/2026", "31/12/2026"):
            assert self._buscar(bd, "Clinac ix", "Anual", fecha)[0] == a
        assert self._buscar(bd, "Clinac ix", "Anual", "02/2027") is None

    def test_no_mezcla_el_anual_con_el_mensual(self, bd):
        """El defecto de la precarga (H3): un mes con control ANUAL prestaba sus físicos al mensual y al revés."""
        _sembrar(bd, "Clinac 600", "Anual", "06/2026", "Fisico A", "Fisico B")
        m = _sembrar(bd, "Clinac 600", "Mensual", "15/06/2026", "Fisico D", "Fisico C")
        assert self._buscar(bd, "Clinac 600", "Mensual", "15/06/2026")[0] == m
        assert self._buscar(bd, "Clinac 600", "Anual", "15/06/2026")[2:] == ("Fisico A", "Fisico B")
        assert self._buscar(bd, "Clinac 600", "Mensual", "15/07/2026") is None

    def test_otro_equipo_no_cuenta(self, bd):
        _sembrar(bd, "Clinac 600", "Mensual", "15/06/2026", "Fisico A")
        assert self._buscar(bd, "Clinac ix", "Mensual", "15/06/2026") is None

    def test_la_grafia_del_equipo_se_compara_exacta_da15(self, bd):
        """DA-15: la grafía histórica de `controles.equipo` no se normaliza al buscar ('Clinac iX' y 'Clinac ix' son dos equipos
        para esta búsqueda, como siempre lo fueron). Lo hizo notar la revisión escéptica: ninguna prueba lo fijaba."""
        _sembrar(bd, "Clinac iX", "Mensual", "15/06/2026", "Fisico A")
        assert self._buscar(bd, "Clinac ix", "Mensual", "15/06/2026") is None
        assert self._buscar(bd, "Clinac iX", "Mensual", "15/06/2026") is not None

    def test_ignora_los_controles_anulados(self, bd):
        """DA-47/LR3: lectura de BLOQUE -- un control anulado no es el vigente; el índice parcial deja convivir uno nuevo."""
        _sembrar(bd, "Clinac 600", "Mensual", "15/06/2026", "Fisico A", activo=0)
        assert self._buscar(bd, "Clinac 600", "Mensual", "15/06/2026") is None
        nuevo = _sembrar(bd, "Clinac 600", "Mensual", "20/06/2026", "Fisico B")
        assert self._buscar(bd, "Clinac 600", "Mensual", "15/06/2026")[0] == nuevo

    def test_varios_anuales_vigentes_del_mismo_anio_elige_el_de_menor_id_y_avisa(self, bd, capsys):
        """Lo que H4 fabricaba: dos anuales vigentes del mismo año. Se elige el primero (menor `id`) y se avisa en consola."""
        primero = _sembrar(bd, "Clinac ix", "Anual", "02/2026", "Fisico A", "Fisico B")
        _sembrar(bd, "Clinac ix", "Anual", "06/10/2026", "Fisico C")
        assert self._buscar(bd, "Clinac ix", "Anual", "10/2026")[0] == primero
        salida = capsys.readouterr().out
        assert "identidad_control" in salida and "Anual" in salida

    def test_sin_coincidencias_devuelve_none(self, bd):
        assert self._buscar(bd, "Clinac 600", "Mensual", "15/06/2026") is None

    def test_una_fecha_ilegible_no_encuentra_nada(self, bd):
        _sembrar(bd, "Clinac 600", "Mensual", "15/06/2026", "Fisico A")
        assert self._buscar(bd, "Clinac 600", "Mensual", "texto") is None


# --------------------------------------------------------- create_control mensual (load.py) -- el servicio
class TestCreateControlMensual:

    def _crear(self, pantalla, fecha, f1, f2=None, maquina="Clinac 600"):
        from data.ManejoDatos.load import create_control
        return create_control(pantalla, maquina=maquina, fecha=fecha, user_id=f1, user_id_f2=f2)

    def test_un_control_nuevo_guarda_la_sesion_como_fisico_1_aunque_el_combo_diga_otro(self, bd):
        ref = self._crear(_PantallaFalsa(_sesion("Fisico C")), "15/06/2026", "Fisico A")
        assert bd.execute("SELECT user_id FROM controles WHERE id=?", (ref,)).fetchone()[0] == "Fisico C"

    def test_sin_objeto_de_sesion_se_conserva_el_parametro_conducta_de_hoy(self, bd):
        """Llamadores antiguos / pruebas que no tienen `self.user_id`: el Físico 1 es el parámetro, como siempre."""
        ref = self._crear(_PantallaFalsa(), "15/06/2026", "Fisico A")
        assert bd.execute("SELECT user_id FROM controles WHERE id=?", (ref,)).fetchone()[0] == "Fisico A"

    def test_un_control_existente_se_actualiza_con_los_fisicos_recibidos_se_conserva(self, bd):
        """D2: «Iniciar» actualiza los físicos de un control existente («si así está funcionando así debería seguir»)."""
        viejo = _sembrar(bd, "Clinac 600", "Mensual", "15/06/2026", "Fisico A", "Fisico B")
        ref = self._crear(_PantallaFalsa(_sesion("Fisico C")), "20/06/2026", "Fisico A",
                          f2=bd.execute("SELECT id FROM users WHERE fullname='Fisico D'").fetchone()[0])
        assert ref == viejo
        assert _controles(bd)[0][4:6] == ("Fisico A", "Fisico D")

    def test_un_fisico_1_inexistente_sigue_bloqueando(self, bd):
        """A3: el aviso de Físico 1 inexistente no inserta nada (ni con sesión)."""
        ref = self._crear(_PantallaFalsa(_sesion("Fisico C")), "15/06/2026", "Nombre Que No Existe")
        assert ref is None
        assert _controles(bd) == []

    def test_la_sesion_que_no_existe_en_users_no_inserta_y_el_aviso_la_nombra(self, bd, monkeypatch):
        """El Físico 1 de un control nuevo es la sesión: si no existe, el aviso dice CUÁL (no el error genérico de la FK)."""
        avisos = []
        monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: avisos.append(a[2])))
        ref = self._crear(_PantallaFalsa(_sesion("Nadie Existe")), "15/06/2026", "Fisico A")
        assert ref is None
        assert _controles(bd) == []
        assert avisos == ["El usuario 'Nadie Existe' no existe en la base de datos."], avisos

    def test_imagenes_anual_iniciada_en_otro_mes_reutiliza_el_anual_del_mismo_anio(self, bd):
        """H4 a nivel de servicio: `esiX_images` -> tipo «Anual»; la identidad es el AÑO, no el mes."""
        anual = _sembrar(bd, "Clinac ix", "Anual", "02/2026", "Fisico A", "Fisico B")
        ref = self._crear(_PantallaFalsa(_sesion("Fisico C"), esiX_images=True), "06/10/2026", "Fisico A", maquina="Clinac ix")
        assert ref == anual
        assert len([f for f in _controles(bd) if f[2] == "Anual"]) == 1

    def test_el_aviso_de_un_control_existente_nombra_su_tipo(self, bd, monkeypatch):
        """El texto decía siempre «control mensual»: con «Imágenes anual» reutilizando el anual (FS.1) mentiría."""
        avisos = []
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: avisos.append(a[2])))
        _sembrar(bd, "Clinac ix", "Anual", "02/2026", "Fisico A", "Fisico B")
        self._crear(_PantallaFalsa(_sesion("Fisico C"), esiX_images=True), "15/06/2026", "Fisico A", maquina="Clinac ix")
        assert len(avisos) == 1 and "Se cargó el control anual de Clinac ix" in avisos[0] and "mensual" not in avisos[0], avisos
        avisos.clear()
        _sembrar(bd, "Clinac ix", "Mensual", "06/2026", "Fisico A")
        self._crear(_PantallaFalsa(_sesion("Fisico C")), "15/06/2026", "Fisico A", maquina="Clinac ix")
        assert len(avisos) == 1 and avisos[0].startswith("Se cargó el control mensual de Clinac ix correspondiente a 06/2026"), avisos

    def test_el_mensual_de_ese_mes_no_se_confunde_con_el_anual(self, bd):
        _sembrar(bd, "Clinac ix", "Anual", "06/2026", "Fisico A", "Fisico B")
        ref = self._crear(_PantallaFalsa(_sesion("Fisico C")), "15/06/2026", "Fisico C", maquina="Clinac ix")
        assert [f[2] for f in _controles(bd)] == ["Anual", "Mensual"]
        assert _controles(bd)[1][0] == ref


# ----------------------------------------------------------------- create_control anual (seiscientos_anual)
class TestCreateControlAnual:

    def _crear(self, pantalla, fecha, f1, f2=None, maquina="Clinac 600"):
        from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
        return PruebaAnual600.create_control(pantalla, maquina, fecha, f1, user_id_f2=f2)

    def test_un_control_nuevo_guarda_la_sesion_como_fisico_1(self, bd):
        ref = self._crear(_PantallaFalsa(_sesion("Fisico C")), "06/2026", "Fisico A")
        assert bd.execute("SELECT user_id FROM controles WHERE id=?", (ref,)).fetchone()[0] == "Fisico C"

    def test_un_anual_existente_se_actualiza_con_el_fisico_1_recibido_no_con_la_sesion(self, bd):
        """Rojo hoy: el anual reescribía el Físico 1 de un control existente con la sesión (`seiscientos_anual.py:31`)."""
        viejo = _sembrar(bd, "Clinac 600", "Anual", "02/2026", "Fisico A", "Fisico B")
        ref = self._crear(_PantallaFalsa(_sesion("Fisico C")), "06/2026", "Fisico A")
        assert ref == viejo
        assert _controles(bd)[0][4] == "Fisico A"

    def test_un_anual_existente_actualiza_los_dos_fisicos_recibidos(self, bd):
        """D2: el combo es libre y «Iniciar» guarda lo que muestre (el segundo físico ya se actualizaba; el primero no)."""
        viejo = _sembrar(bd, "Clinac 600", "Anual", "02/2026", "Fisico A", "Fisico B")
        d = bd.execute("SELECT id FROM users WHERE fullname='Fisico D'").fetchone()[0]
        ref = self._crear(_PantallaFalsa(_sesion("Fisico C")), "06/2026", "Fisico A", f2=d)
        assert ref == viejo
        assert _controles(bd)[0][4:6] == ("Fisico A", "Fisico D")

    @pytest.mark.parametrize("recibido", [3, None, "", "  "])
    def test_un_fisico_1_recibido_que_no_es_un_nombre_cae_a_la_sesion_conducta_de_hoy(self, bd, recibido):
        """Hoy la pantalla anual pasaba el `id` del combo (un entero) y el servicio lo ignoraba: sin nombre, manda la sesión."""
        viejo = _sembrar(bd, "Clinac 600", "Anual", "02/2026", "Fisico A", "Fisico B")
        ref = self._crear(_PantallaFalsa(_sesion("Fisico C")), "06/2026", recibido)
        assert ref == viejo
        assert _controles(bd)[0][4] == "Fisico C"

    @pytest.mark.parametrize("recibido", ["Físico 1", "Nombre Que No Existe"])
    def test_un_fisico_1_recibido_que_no_es_un_usuario_cae_a_la_sesion_y_no_bloquea(self, bd, monkeypatch, recibido):
        """Lo recibido es el texto del combo: una sesión que no es «Físico Médico» (administrador, jefe) lo trae en el marcador
        «Físico 1». `HEAD` ignoraba lo recibido y continuaba con la sesión; bloquear sería una regresión para esas sesiones
        (hallazgo de la revisión escéptica de FS.1, reproducido)."""
        viejo = _sembrar(bd, "Clinac 600", "Anual", "02/2026", "Fisico A", "Fisico B")
        b = bd.execute("SELECT id FROM users WHERE fullname='Fisico B'").fetchone()[0]
        avisos = []
        monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: avisos.append(a[2])))
        ref = self._crear(_PantallaFalsa(_sesion("Fisico C")), "06/2026", recibido, f2=b)
        assert ref == viejo
        assert _controles(bd)[0][4:6] == ("Fisico C", "Fisico B")
        assert avisos == [], avisos

    def test_el_administrador_puede_reabrir_un_anual_existente_con_el_combo_en_el_marcador(self, bd):
        viejo = _sembrar(bd, "Clinac 600", "Anual", "02/2026", "Fisico A", "Fisico B")
        ref = self._crear(_PantallaFalsa(_sesion("Administrador", "admin")), "06/2026", "Físico 1")
        assert ref == viejo
        assert _controles(bd)[0][4] == "Administrador"

    def test_la_sesion_inexistente_sigue_bloqueando(self, bd):
        ref = self._crear(_PantallaFalsa(_sesion("Nadie Existe")), "06/2026", "Nadie Existe")
        assert ref is None
        assert _controles(bd) == []


# ------------------------------------------------------------------------------ pantallas reales (a)(b)(c)
def _combo_a(p, combo, nombre):
    i = combo.findText(nombre)
    assert i >= 0, f"el combo no ofrece a {nombre}: {[combo.itemText(k) for k in range(combo.count())]}"
    combo.setCurrentIndex(i)


class TestPantallasReales:

    def test_a_imagenes_anual_iniciada_en_otro_mes_no_crea_un_segundo_anual(self, app, bd):
        """El defecto H4, con la pantalla real del iX: el anual es de febrero y la pantalla se inicia en el mes de hoy."""
        from ui.paginasControles.PruebasAnuales.ix_anual import PruebaImagenesIX
        anio = QDate.currentDate().year()
        mes_del_anual = 2 if QDate.currentDate().month() != 2 else 3
        anual = _sembrar(bd, "Clinac ix", "Anual", f"{mes_del_anual:02d}/{anio}", "Fisico A", "Fisico B")
        p = PruebaImagenesIX(_sesion("Fisico C"), ref=None)
        try:
            p.iniciar.click()
            anuales = [f for f in _controles(bd) if f[2] == "Anual"]
            assert len(anuales) == 1, f"se creó un segundo anual del mismo año: {anuales}"
            assert p.ref == anual
        finally:
            _cerrar(p)

    def test_b_mensual_nuevo_guarda_la_sesion_como_fisico_1_aunque_el_combo_diga_otro(self, app, bd):
        from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
        p = PruebaMensual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            _combo_a(p, p.fisico1, "Fisico A")
            p.iniciar.click()
            filas = [f for f in _controles(bd) if f[2] == "Mensual"]
            assert len(filas) == 1
            assert filas[0][4] == "Fisico C", f"el control nuevo nació con {filas[0][4]} y no con la sesión"
        finally:
            _cerrar(p)

    def test_b_anual_nuevo_guarda_la_sesion_como_fisico_1_aunque_el_combo_diga_otro(self, app, bd):
        from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
        p = PruebaAnual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            _combo_a(p, p.fisico1, "Fisico A")
            p.iniciar.click()
            filas = [f for f in _controles(bd) if f[2] == "Anual"]
            assert len(filas) == 1
            assert filas[0][4] == "Fisico C"
        finally:
            _cerrar(p)

    def test_c_reabrir_un_anual_existente_con_el_combo_en_su_fisico_1_no_lo_cambia(self, app, bd):
        """Rojo hoy (A2 de la verificación del 06-10): «Iniciar» dejaba el anual en (sesión, Físico 2)."""
        from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
        anio = QDate.currentDate().year()
        viejo = _sembrar(bd, "Clinac 600", "Anual", f"02/{anio}", "Fisico A", "Fisico B")
        p = PruebaAnual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            _combo_a(p, p.fisico1, "Fisico A")
            _combo_a(p, p.fisico2, "Fisico B")
            p.iniciar.click()
            fila = _controles(bd)[0]
            assert fila[0] == viejo and fila[4:6] == ("Fisico A", "Fisico B"), f"quedó {fila}"
            assert len(_controles(bd)) == 1
        finally:
            _cerrar(p)

    def test_c_reabrir_un_anual_existente_deja_cambiar_el_segundo_fisico(self, app, bd):
        """Lo que se conserva (D2): el combo es libre y «Iniciar» guarda lo que muestre."""
        from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
        anio = QDate.currentDate().year()
        _sembrar(bd, "Clinac 600", "Anual", f"02/{anio}", "Fisico A", "Fisico B")
        p = PruebaAnual600(_sesion("Fisico C"), equipo_f="Clinac 600")
        try:
            _combo_a(p, p.fisico1, "Fisico A")
            _combo_a(p, p.fisico2, "Fisico D")
            p.iniciar.click()
            assert _controles(bd)[0][4:6] == ("Fisico A", "Fisico D")
        finally:
            _cerrar(p)


# ------------------------------------------------------------------ (e) cero diferencias en lo que no se nombra
def _copia_de(origen, destino):
    shutil.copy(origen, destino)
    return str(destino)


class TestSinCambiosEnLoQueNoSeNombra:
    """(e) Ensayo sobre una COPIA de `Rebuild_21-09`: cada control vigente, buscado por su propio periodo, resuelve al mismo
    `id` que resolvían las búsquedas de antes (el bucle por mes del mensual y el `LIKE '%AAAA%'` del anual)."""

    def test_los_controles_vigentes_reales_resuelven_al_mismo_id_que_antes(self, tmp_path):
        from _bd_referencia import BD_REBUILD_21_09
        if not BD_REBUILD_21_09.exists():
            pytest.skip("falta la BD de referencia Rebuild_21-09 (HI-0)")
        from services.fechas_control import mes_anio_de_fecha, mismo_mes
        ruta = _copia_de(BD_REBUILD_21_09, tmp_path / "copia.db")
        con = sqlite3.connect(ruta)
        try:
            filas = con.execute(
                "SELECT id, equipo, control, fecha FROM controles WHERE activo IS NULL OR activo = 1 ORDER BY id").fetchall()
            assert len(filas) >= 30, "la copia no trae los controles vigentes esperados"
            antes = {}
            for id_, equipo, control, fecha in filas:
                if control == "Mensual":
                    # la búsqueda de antes: bucle por mes sobre (equipo, control)
                    vigentes = con.execute(
                        "SELECT id, fecha FROM controles WHERE equipo = ? AND control = ? AND (activo IS NULL OR activo = 1)",
                        (equipo, control)).fetchall()
                    antes[id_] = next(i for i, f in vigentes if mismo_mes(f, fecha))
                elif control == "Anual":
                    anio = mes_anio_de_fecha(fecha)[1]
                    antes[id_] = con.execute(
                        "SELECT id FROM controles WHERE fecha LIKE ? AND equipo = ? AND control = 'Anual' "
                        "AND (activo IS NULL OR activo = 1) ORDER BY id DESC", (f"%{anio}%", equipo)).fetchone()[0]
            identidad = _identidad()
            cursor = con.cursor()
            despues = {}
            for id_, equipo, control, fecha in filas:
                if control in ("Mensual", "Anual"):
                    despues[id_] = identidad.buscar_control_vigente(cursor, equipo, control, fecha)[0]
            assert despues == antes, {k: (antes[k], despues[k]) for k in antes if antes[k] != despues[k]}
            assert all(k == v for k, v in despues.items()), "cada control vigente se resuelve a sí mismo"
            assert len(despues) >= 30
        finally:
            con.close()


# ---------------------------------------------------------------------------- una sola búsqueda (tripwire)
def _funcion(ruta, nombre, clase=None):
    arbol = ast.parse((RAIZ / ruta).read_text(encoding="utf-8"))
    cuerpo = arbol.body
    if clase:
        cuerpo = next(n for n in arbol.body if isinstance(n, ast.ClassDef) and n.name == clase).body
    return next(n for n in cuerpo if isinstance(n, ast.FunctionDef) and n.name == nombre)


def _consultas_a_controles(nodo):
    """Literales (y f-strings) dentro de `nodo` que consultan `FROM controles`."""
    hallados = []
    for n in ast.walk(nodo):
        if isinstance(n, (ast.Constant, ast.JoinedStr)):
            texto = ast.unparse(n)
            if "FROM controles" in texto and "SELECT" in texto:
                hallados.append(texto)
    return hallados


class TestUnaSolaBusquedaDelControl:

    def test_los_dos_create_control_no_buscan_por_su_cuenta_y_usan_la_funcion_unica(self):
        for ruta, nombre, clase in (("data/ManejoDatos/load.py", "create_control", None),
                                    ("ui/paginasControles/PruebasAnuales/seiscientos_anual.py", "create_control", "PruebaAnual600")):
            nodo = _funcion(ruta, nombre, clase)
            assert _consultas_a_controles(nodo) == [], f"{ruta}::{nombre} vuelve a buscar el control por su cuenta"
            llamadas = {n.func.id if isinstance(n.func, ast.Name) else n.func.attr
                        for n in ast.walk(nodo) if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))}
            assert "buscar_control_vigente" in llamadas, f"{ruta}::{nombre} no usa buscar_control_vigente"

    def test_el_modulo_nuevo_es_puro_no_importa_qt_ni_la_capa_de_datos(self):
        arbol = ast.parse((RAIZ / "services/identidad_control.py").read_text(encoding="utf-8"))
        importados = set()
        for n in ast.walk(arbol):
            if isinstance(n, ast.Import):
                importados.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module:
                importados.add(n.module.split(".")[0])
        assert not importados & {"PyQt5", "data", "ui", "models"}, importados
