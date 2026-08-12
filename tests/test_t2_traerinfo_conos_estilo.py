"""T2 (PLAN_CONOS_MENSUAL_12-08.md §4-T2): lo restaurado en Seguridad ->
Conos SE VE.

`Traerinfo_conos` (M3) marcaba `btn_fun.setChecked(valor == 1)` /
`btn_nofun.setChecked(valor == 0)` pero nunca llamaba a `cambiar_estilo`,
que es lo que pinta el botón -- las cuatro reglas de `estilo.qss` para
`#boton_funciona`/`#boton_nofunciona` dependen SOLO de la propiedad
dinámica `estado`, no existe ninguna regla `:checked`. `setChecked` por sí
solo no tiene ningún efecto visual. Al reabrir un control, el botón
correcto queda marcado internamente pero en pantalla se ve igual que uno
sin marcar -- el físico lo pulsa para "seleccionarlo", y ese clic (D2,
antes de T1) lo apagaba.

D3 cerrado: tras marcar, `Traerinfo_conos` aplica `cambiar_estilo` con el
mismo criterio que el clic real (`completar`) -- el botón seleccionado
queda con `estado="selected"`, el rechazado con `estado="noselected"`.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QPushButton, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import DatabaseManager


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO controles (id, equipo, control, fecha) "
        "VALUES (1, 'Clinac ix', 'Mensual', '06/2026')")
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


MEDIDAS = ("6", "10", "15", "20", "25")


def _insertar_bloque_conos(ruta_bd, ref, valores):
    """valores: dict medida(str, "6".."25") -> 0/1."""
    con = sqlite3.connect(ruta_bd)
    for medida, valor in valores.items():
        con.execute(
            "INSERT INTO control_conos (ref, medida, valor, activo) "
            "VALUES (?, ?, ?, 1)", (ref, f"{medida}x{medida}", valor))
    con.commit()
    con.close()


def _instancia_ix_sin_clics(ref):
    """PruebaMensualIX pelada, con los 10 botones de conos creados con
    `setObjectName` (igual que `setupButtonConnections` en producción) --
    SIN ningún clic ni cableado de señales. La instancia es NUEVA: ningún
    botón fue pulsado antes, así que si `property("estado")` sale
    "selected"/"noselected" solo pudo ponerlo `Traerinfo_conos`."""
    obj = PruebaMensualIX.__new__(PruebaMensualIX)
    QWidget.__init__(obj)
    obj.ref = ref
    obj.db_manager = DatabaseManager()
    for medida in MEDIDAS:
        fun = QPushButton("Funciona")
        fun.setCheckable(True)
        fun.setObjectName("boton_funciona")
        nofun = QPushButton("No funciona")
        nofun.setCheckable(True)
        nofun.setObjectName("boton_nofunciona")
        setattr(obj, f"btn_{medida}_fun", fun)
        setattr(obj, f"btn_{medida}_nofun", nofun)
    return obj


class TestRestauracionMixtaSeVe:
    """§5.3 caso 12: 5 conos con valores mixtos (1,0,1,0,1) -> instancia
    NUEVA -> Traerinfo_conos ⇒ los 5 botones marcados Y con
    property("estado") == "selected"/"noselected" correcto. Rojo sin T2
    (setChecked solo, sin cambiar_estilo, deja `estado` sin definir)."""

    VALORES = {"6": 1, "10": 0, "15": 1, "20": 0, "25": 1}

    def test_estado_visual_correcto_sin_ningun_clic_previo(self, app, bd_temporal):
        _insertar_bloque_conos(bd_temporal, ref=1, valores=self.VALORES)

        obj = _instancia_ix_sin_clics(ref=1)
        resultado = obj.Traerinfo_conos()
        assert resultado is True

        for medida, valor in self.VALORES.items():
            btn_fun = getattr(obj, f"btn_{medida}_fun")
            btn_nofun = getattr(obj, f"btn_{medida}_nofun")

            assert btn_fun.isChecked() == (valor == 1)
            assert btn_nofun.isChecked() == (valor == 0)

            seleccionado, otro = (
                (btn_fun, btn_nofun) if valor == 1 else (btn_nofun, btn_fun))
            assert seleccionado.property("estado") == "selected", (
                f"medida {medida}: el botón seleccionado no quedó pintado "
                f"(estado={seleccionado.property('estado')!r})")
            assert otro.property("estado") == "noselected", (
                f"medida {medida}: el botón rechazado no quedó pintado "
                f"(estado={otro.property('estado')!r})")


class TestElCasoRealDelFisico:
    """§5.3 caso 13: guardar los 5 -> reabrir -> volver a pulsar Subir SIN
    tocar nada ⇒ siguen siendo 5 filas activas con los mismos valores. Es
    el caso que hoy produce los bloques de 2 y 3 filas (D3 induce D2 sin
    T1+T2): el físico ve un botón "apagado" (aunque esté marcado), lo
    pulsa para corregirlo, y la fila desaparece del siguiente guardado."""

    VALORES = {"6": 1, "10": 0, "15": 1, "20": 0, "25": 1}

    def test_guardar_sin_tocar_nada_mantiene_las_5_filas(self, app, bd_temporal):
        _insertar_bloque_conos(bd_temporal, ref=1, valores=self.VALORES)

        obj = _instancia_ix_sin_clics(ref=1)
        obj.Traerinfo_conos()

        # "Subir" sin tocar nada -- mismo cuerpo que guardar_control_conos
        # (M2: anular+insertar), leyendo el estado YA restaurado.
        medidas = [
            (f"{m}x{m}", getattr(obj, f"btn_{m}_fun"), getattr(obj, f"btn_{m}_nofun"))
            for m in MEDIDAS
        ]
        filas_nuevas = []
        for medida, btn_fun, btn_nofun in medidas:
            if btn_fun.isChecked():
                valor = 1
            elif btn_nofun.isChecked():
                valor = 0
            else:
                valor = None
            if valor is not None:
                filas_nuevas.append((obj.ref, medida, valor))

        assert len(filas_nuevas) == 5, (
            f"con T1+T2 aplicados, restaurar sin clics no debe perder "
            f"ninguna medida: {filas_nuevas}")

        conn = Conexion().conectar()
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute(
            "UPDATE control_conos SET activo = 0 "
            "WHERE ref = ? AND (activo IS NULL OR activo = 1)", (obj.ref,))
        cursor.executemany(
            "INSERT INTO control_conos (ref, medida, valor) VALUES (?, ?, ?)",
            filas_nuevas)
        conn.commit()

        con = sqlite3.connect(bd_temporal)
        try:
            activas = con.execute(
                "SELECT medida, valor FROM control_conos "
                "WHERE ref = ? AND activo = 1", (obj.ref,)).fetchall()
        finally:
            con.close()

        assert len(activas) == 5
        activas_dict = {m: v for m, v in activas}
        esperado = {f"{m}x{m}": v for m, v in self.VALORES.items()}
        assert activas_dict == esperado
