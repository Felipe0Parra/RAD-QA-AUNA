"""F.1 (PLAN_HANDOFF_IMAGENES_22-09.md §7): una referencia dice en qué unidad está y quién la firma.

CAUSA [medida sobre la copia de la BD del 21-09]: las 10 filas de `referencias_qc` tienen `unidad = NULL` y
`fijada_por = 'Administrador'` -- una cuenta con `role = NULL`, que no es un físico. El servicio guardaba la unidad si
alguien la tecleaba (la pantalla decía "Opcional") y firmaba con la cuenta que actuaba, fuera quien fuera.

Lo que este archivo garantiza:
  1. LA UNIDAD ES OBLIGATORIA -- con la de la magnitud por omisión (calidad: 1, adimensional); sin ninguna, se rechaza.
  2. QUIEN FIRMA ES UN FÍSICO MÉDICO ACTIVO -- la propia cuenta si lo es; si no (un administrador sin cargo de físico),
     hay que elegirlo, como ya se elige el segundo físico; un responsable que no es físico activo se rechaza.
  3. EL PERMISO NO CAMBIA -- quién PUEDE escribir sigue siendo `es_fisico_jefe` de la cuenta que actúa; nombrar a un
     responsable no le da permiso a nadie, y la auditoría sigue registrando a la cuenta que actuó.
  4. LA PESTAÑA lo pide (unidad con su valor por omisión, físico responsable) y muestra "sin registrar" donde una fila
     anterior no trae unidad.
  5. LO YA FIJADO NO SE REESCRIBE -- las 10 filas reales quedan tal cual (son datos del físico; reemitirlas es decisión suya).
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from _informe_imagenes import app, bd_copia  # noqa: F401  (fixtures)
from services import referencias_qc as servicio
from ui.paginasGuia import referencias as pantalla
from ui.paginasGuia.referencias import Referencias


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _usuario(ruta, user, fullname, rol_sistema, role="Físico Médico", active=1):
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
        "VALUES (?, 'x', ?, ?, '1', ?, ?)", (user, fullname, active, role, rol_sistema))
    con.commit()
    con.close()


@pytest.fixture
def usuarios(bd_temporal):
    """Los casos de la BD real: una jefe que es física, una física, un físico INACTIVO, y el administrador, que NO es un
    físico (`role = NULL`, como `Administrador` en la copia del 21-09). Una BD nueva ya trae sembrado a ese administrador
    (`user='admin'`, `role NULL`, `rol_sistema='admin'`): no se vuelve a insertar."""
    _usuario(bd_temporal, "lamaya", "Luz Adriana Maya", "jefe")
    _usuario(bd_temporal, "jjcastillo", "Javier Castillo", "fisico")
    _usuario(bd_temporal, "adloaiza", " Andres David Loaiza Baena", "fisico", active=0)
    return bd_temporal


def _filas(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute("SELECT equipo, magnitud, energia, valor, unidad, fijada_por FROM referencias_qc "
                        "ORDER BY id").fetchall()
    con.close()
    return filas


def _auditoria(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute("SELECT usuario, accion, detalle FROM audit_log WHERE tabla='referencias_qc' "
                        "ORDER BY id").fetchall()
    con.close()
    return filas


def _fijar(usuario, **kw):
    args = dict(equipo="Halcyon", magnitud="calidad", energia="6mv", valor=0.627, fuente="puesta en servicio",
                observaciones="medido en la puesta en servicio")
    args.update(kw)
    return servicio.fijar_referencia(args.pop("equipo"), args.pop("magnitud"), args.pop("energia"),
                                     args.pop("valor"), args.pop("fuente"), args.pop("observaciones"),
                                     usuario, **args)


# ---------------------------------------------------------------------------
# 1. LA UNIDAD
# ---------------------------------------------------------------------------

def test_la_calidad_sin_unidad_se_guarda_en_1_adimensional(usuarios):
    assert _fijar("lamaya") == (True, None)
    assert _filas(usuarios) == [("Halcyon", "calidad", "6mv", 0.627, "1", "Luz Adriana Maya")]


@pytest.mark.parametrize("unidad", ["", "   ", None])
def test_una_unidad_en_blanco_toma_la_de_la_magnitud(usuarios, unidad):
    assert _fijar("lamaya", unidad=unidad) == (True, None)
    assert _filas(usuarios)[0][4] == "1"


def test_una_unidad_explicita_se_respeta_sin_espacios_sobrantes(usuarios):
    _fijar("lamaya", magnitud="tol_dosis", energia="", valor=2.0, unidad="  %  ")
    assert _filas(usuarios)[0][4] == "%"


def test_una_magnitud_sin_unidad_declarada_y_sin_unidad_se_rechaza_y_no_escribe(usuarios):
    resultado = _fijar("lamaya", magnitud="tol_dosis", energia="", valor=2.0)
    assert resultado == (False, servicio.UNIDAD_OBLIGATORIA)
    assert _filas(usuarios) == []


def test_ninguna_referencia_nueva_queda_sin_unidad(usuarios):
    for magnitud, unidad in (("calidad", None), ("calidad", "1"), ("tol_dosis", "%")):
        _fijar("lamaya", magnitud=magnitud, energia="", valor=1.5, unidad=unidad)
    assert all(fila[4] for fila in _filas(usuarios))


# ---------------------------------------------------------------------------
# 2. QUIÉN FIRMA
# ---------------------------------------------------------------------------

def test_una_cuenta_que_es_fisico_firma_ella(usuarios):
    assert _fijar("lamaya") == (True, None)
    assert _filas(usuarios)[0][5] == "Luz Adriana Maya"


def test_el_administrador_sin_cargo_de_fisico_debe_elegir_al_responsable(usuarios):
    """El caso real de las 10 filas: `Administrador` (`role = NULL`) firmaba como 'Administrador'. Ahora no puede."""
    assert _fijar("admin") == (False, servicio.RESPONSABLE_OBLIGATORIO)
    assert _filas(usuarios) == []
    assert _auditoria(usuarios) == []                    # no hubo acción: nada que registrar


def test_el_administrador_elige_a_un_fisico_y_la_referencia_lleva_su_nombre(usuarios):
    assert _fijar("admin", responsable="Luz Adriana Maya") == (True, None)
    assert _filas(usuarios)[0][5] == "Luz Adriana Maya"


def test_la_auditoria_registra_a_quien_actuo_y_dice_quien_firma(usuarios):
    """Cambiar quién firma no cambia a quién se le pide cuentas: la fila de auditoría es de la cuenta que actuó."""
    _fijar("admin", responsable="Javier Castillo")
    (usuario, accion, detalle), = _auditoria(usuarios)
    assert usuario == "Administrador"
    assert "responsable: Javier Castillo" in detalle and "[1]" in detalle


def test_la_auditoria_no_repite_el_responsable_cuando_firma_la_propia_cuenta(usuarios):
    _fijar("lamaya")
    (usuario, _accion, detalle), = _auditoria(usuarios)
    assert usuario == "Luz Adriana Maya" and "responsable" not in detalle


@pytest.mark.parametrize("responsable", [
    "Administrador",                # una cuenta que no es un físico
    " Andres David Loaiza Baena",   # un físico INACTIVO
    "Fulano Inexistente",
])
def test_un_responsable_que_no_es_un_fisico_activo_se_rechaza(usuarios, responsable):
    assert _fijar("admin", responsable=responsable) == (False, servicio.RESPONSABLE_INVALIDO)
    assert _filas(usuarios) == []


def test_una_cuenta_fisico_puede_nombrar_a_otro_fisico(usuarios):
    assert _fijar("lamaya", responsable="Javier Castillo") == (True, None)
    assert _filas(usuarios)[0][5] == "Javier Castillo"


def test_el_nombre_del_responsable_tolera_espacios_sobrantes(usuarios):
    assert _fijar("admin", responsable="  Javier Castillo ") == (True, None)
    assert _filas(usuarios)[0][5] == "Javier Castillo"


def test_fijada_por_nunca_es_una_cuenta_que_no_es_fisico(usuarios):
    for cuenta, responsable in (("lamaya", None), ("admin", "Luz Adriana Maya"), ("admin", "Javier Castillo"),
                                ("lamaya", "Javier Castillo")):
        _fijar(cuenta, responsable=responsable, valor=0.6)
    firmantes = {fila[5] for fila in _filas(usuarios)}
    assert firmantes <= {"Luz Adriana Maya", "Javier Castillo"} and firmantes


def test_los_fisicos_que_se_ofrecen_como_responsables_son_los_activos(usuarios):
    assert sorted(servicio.fisicos_responsables()) == ["Javier Castillo", "Luz Adriana Maya"]


# ---------------------------------------------------------------------------
# 3. EL PERMISO NO CAMBIA
# ---------------------------------------------------------------------------

def test_un_fisico_sin_permiso_no_puede_aunque_nombre_un_responsable_valido(usuarios):
    assert _fijar("jjcastillo", responsable="Luz Adriana Maya") == (False, servicio.DENEGADO_SIN_PERMISO)
    assert _filas(usuarios) == []


def test_un_fisico_sin_permiso_no_puede_ni_firmando_el_mismo(usuarios):
    assert _fijar("jjcastillo") == (False, servicio.DENEGADO_SIN_PERMISO)


def test_el_permiso_se_comprueba_antes_que_el_responsable(usuarios):
    """Sin permiso, ni siquiera se dice si el responsable era válido: no se filtra información a quien no puede actuar."""
    assert _fijar("jjcastillo", responsable="Fulano Inexistente") == (False, servicio.DENEGADO_SIN_PERMISO)


def test_una_cuenta_desconocida_no_puede(usuarios):
    assert _fijar("nadie", responsable="Luz Adriana Maya") == (False, servicio.DENEGADO_SIN_PERMISO)


# ---------------------------------------------------------------------------
# 4. LA PESTAÑA
# ---------------------------------------------------------------------------

class _Usuario:
    def __init__(self, usuario):
        self._usuario = usuario


@pytest.fixture
def avisos(monkeypatch):
    estado = {"pregunta": QMessageBox.Yes, "mostrados": []}
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda *a, **k: estado["mostrados"].append(("question", a[2] if len(a) > 2 else "")) or estado["pregunta"]))
    for nombre in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, nombre, staticmethod(
            lambda *a, _n=nombre, **k: estado["mostrados"].append((_n, a[2] if len(a) > 2 else "")) or QMessageBox.Ok))
    return estado


def _rellenar(p, valor="0.627"):
    p.cb_equipo.setCurrentText("Halcyon")
    p.cb_energia.setCurrentIndex(p.cb_energia.findData("6mv"))
    p.in_valor.setText(valor)
    p.in_fuente.setText("puesta en servicio 2026")
    p.in_observaciones.setText("medido tras el servicio técnico")


def test_la_pestana_trae_la_unidad_por_omision_y_ya_no_es_opcional(app, usuarios, avisos):
    p = Referencias(_Usuario("lamaya"))
    assert p.in_unidad.text() == "1"
    assert "Opcional" not in p.in_unidad.placeholderText() and "Obligatoria" in p.in_unidad.placeholderText()


def test_la_pestana_ofrece_a_los_fisicos_activos_y_preselecciona_al_de_la_sesion(app, usuarios, avisos):
    p = Referencias(_Usuario("lamaya"))
    ofrecidos = [p.cb_responsable.itemText(i) for i in range(1, p.cb_responsable.count())]
    assert sorted(ofrecidos) == ["Javier Castillo", "Luz Adriana Maya"]
    assert p.cb_responsable.currentData() == "Luz Adriana Maya"


def test_la_pestana_del_administrador_no_preselecciona_a_nadie_y_lo_pide(app, usuarios, avisos):
    p = Referencias(_Usuario("admin"))
    assert p.cb_responsable.currentData() is None and p.cb_responsable.isEnabled()
    _rellenar(p)
    p._on_fijar()
    assert _filas(usuarios) == []
    assert ("warning", pantalla.MENSAJES_RECHAZO[servicio.RESPONSABLE_OBLIGATORIO]) in avisos["mostrados"]


def test_el_administrador_elige_y_la_pestana_guarda_con_ese_nombre(app, usuarios, avisos):
    p = Referencias(_Usuario("admin"))
    _rellenar(p)
    p.cb_responsable.setCurrentIndex(p.cb_responsable.findData("Javier Castillo"))
    p._on_fijar()
    assert _filas(usuarios) == [("Halcyon", "calidad", "6mv", 0.627, "1", "Javier Castillo")]


def test_la_pestana_guarda_la_unidad_que_muestra(app, usuarios, avisos):
    p = Referencias(_Usuario("lamaya"))
    _rellenar(p)
    p._on_fijar()
    assert _filas(usuarios)[0][4] == "1" and p.in_unidad.text() == "1"           # y se repone tras fijar


def test_una_fila_anterior_sin_unidad_se_muestra_como_sin_registrar(app, usuarios, avisos):
    con = sqlite3.connect(usuarios)
    con.execute("INSERT INTO referencias_qc (equipo, magnitud, energia, valor, unidad, fuente, observaciones, "
                "fijada_por, fecha) VALUES ('Halcyon','calidad','6mv',0.627,NULL,'x','y','Administrador','2026-09-22')")
    con.commit()
    con.close()
    p = Referencias(_Usuario("lamaya"))
    fila = [p._tabla.item(0, c).text() for c in range(p._tabla.columnCount())]
    assert fila[4] == pantalla.SIN_UNIDAD_REGISTRADA == "sin registrar" and fila[7] == "Administrador"


def test_el_selector_de_responsable_queda_deshabilitado_para_quien_solo_consulta(app, usuarios, avisos):
    p = Referencias(_Usuario("jjcastillo"))
    assert not p.cb_responsable.isEnabled() and not p.btn_fijar.isEnabled()


# ---------------------------------------------------------------------------
# 5. LO YA FIJADO NO SE REESCRIBE (datos reales del físico: copia de la BD del 21-09)
# ---------------------------------------------------------------------------

def _antes(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute("SELECT * FROM referencias_qc ORDER BY id").fetchall()
    con.close()
    return filas


def test_las_diez_filas_reales_quedan_tal_cual(app, bd_copia):
    """La copia se abre con `Conexion()` (migraciones) y con la pestaña: las 10 filas de `referencias_qc` siguen con
    `unidad NULL` y `fijada_por 'Administrador'`. Reemitirlas es decisión del físico, desde la pantalla."""
    filas = _antes(bd_copia)
    assert len(filas) == 10
    Referencias(_Usuario("lamaya"))                       # abre la pestaña sobre la BD real
    assert _antes(bd_copia) == filas
    assert {f[5] for f in filas} == {None} and {f[8] for f in filas} == {"Administrador"}


def test_la_pestana_sobre_la_bd_real_pide_al_responsable_al_administrador_y_ofrece_a_los_cinco(app, bd_copia, avisos):
    p = Referencias(_Usuario("admin"))
    ofrecidos = sorted(p.cb_responsable.itemText(i) for i in range(1, p.cb_responsable.count()))
    assert ofrecidos == sorted(["Cristian Castellanos", "Luz Adriana Maya", "Daniela Mesa Lotero", "Javier Castillo",
                                "José Antonio Diaz Merchán"])                     # sin el físico inactivo ni 'Administrador'
    unidades = {p._tabla.item(f, 4).text() for f in range(p._tabla.rowCount())}
    assert unidades == {"sin registrar"}


def test_fijar_sobre_la_bd_real_como_administrador_deja_una_fila_con_unidad_y_fisico(app, bd_copia, avisos):
    p = Referencias(_Usuario("admin"))
    p.cb_equipo.setCurrentText("Halcyon")
    p.cb_energia.setCurrentIndex(p.cb_energia.findData("6mv"))
    p.in_valor.setText("0.627")
    p.in_fuente.setText("recalibración")
    p.in_observaciones.setText("reemisión con unidad y responsable")
    p.cb_responsable.setCurrentIndex(p.cb_responsable.findData("Luz Adriana Maya"))
    p._on_fijar()
    con = sqlite3.connect(bd_copia)
    vigente = con.execute("SELECT unidad, fijada_por FROM referencias_qc WHERE equipo='Halcyon' AND magnitud='calidad' "
                          "AND energia='6mv' AND (activo IS NULL OR activo=1)").fetchall()
    total = con.execute("SELECT COUNT(*) FROM referencias_qc").fetchone()[0]
    con.close()
    assert vigente == [("1", "Luz Adriana Maya")]
    assert total == 11                                                             # la anterior queda como historial
