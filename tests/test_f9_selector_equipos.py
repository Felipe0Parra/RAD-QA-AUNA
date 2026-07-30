"""F9 (PLAN_F_CIERRE_ESTANDAR_29-07.md §8.3/§8.6/§9): el selector de equipos
del formulario mensual funciona como la calculadora -- una entrada por
CALIBRACIÓN activa (no una por serie), sin símbolos, resolviendo el factor
por el ID del equipo elegido (nunca por el texto del combo).

Antes de F9, `obtenerSeriesConVigencia` colapsaba con `MAX(id) GROUP BY
serie`: escondía calibraciones históricas todavía en uso (A092535 conserva
activas 2022 y 2025, para reproducir un control retroactivo con los
parámetros que el equipo tenía entonces) y, si el colapso caía en un
duplicado `activo=0` de H2.6, hacía desaparecer la serie ENTERA del
selector -- medido: N30013/2123 (id13), N31014/0453 (id7) y HDR1000
Plus/A972662 (id16, vía braquiterapia con la MISMA `_FILA_ACTUAL`) quedaban
invisibles pese a estar activas. Y `setCalibracion` resolvía el factor con
`buscarModeloActivo('serie', 'calibr_fact', modelo)` -> `set()` -> `lista[0]`
(orden arbitrario, R3 del plan): al levantar el colapso, una serie con dos
calibraciones activas habría escrito un factor cualquiera.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QComboBox, QDateEdit, QLineEdit, QWidget
from PyQt5.QtCore import QDate

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import ui.paginasControles.PruebasMensuales.seiscientos_mensual as mensual_mod
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
    PruebaMensual600, DatabaseManager,
)
from services.equipos_service import EquiposService


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # crea el esquema completo (incl. equipos_medicion.equipo_id)
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _insertar_equipo(ruta_bd, eq_id, **campos):
    import sqlite3
    con = sqlite3.connect(ruta_bd)
    cols = ["id"] + list(campos)
    marcas = ", ".join("?" * len(cols))
    con.execute(f"INSERT INTO equipos ({', '.join(cols)}) VALUES ({marcas})",
                [eq_id] + list(campos.values()))
    con.commit()
    con.close()


def _insertar_control(ruta_bd, equipo="Clinac 600", control="Mensual", fecha="06/2026"):
    import sqlite3
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        (equipo, control, fecha))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _instancia_pelada(fecha_control, n_grupos=1):
    """PruebaMensual600 sin su __init__ pesado -- solo lo que
    setEquipoSeleccionado/setCalibracion/subirtodo_modificado necesitan:
    db_manager, date_box y n_grupos tripletes (modelo, serie, calibración)
    representando self.commenu (== self.combo_menu, ver controlTestWindow)."""
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    obj.date_box = QDateEdit()
    obj.date_box.setDate(fecha_control)

    obj.commenu = []
    for _ in range(n_grupos):
        combo_modelo = QComboBox()
        combo_modelo.addItems(["Seleccionar...", "ModeloTest"])
        combo_serie = QComboBox()
        lineedit_calib = QLineEdit()
        obj.commenu.extend([combo_modelo, combo_serie, lineedit_calib])
        combo_modelo.currentTextChanged.connect(obj.setEquipoSeleccionado)
        combo_serie.currentTextChanged.connect(obj.setCalibracion)
    return obj


def _seleccionar_modelo(obj, grupo=0, modelo="ModeloTest"):
    """Dispara setEquipoSeleccionado sobre el grupo `grupo` (0-indexado)."""
    obj.commenu[grupo * 3].setCurrentText(modelo)


def _combo_serie(obj, grupo=0):
    return obj.commenu[grupo * 3 + 1]


def _lineedit_calib(obj, grupo=0):
    return obj.commenu[grupo * 3 + 2]


class TestLasTresSeriesRealesAparecenEnElSelector:
    """§8.3 del plan: serie buena (id bajo, activa) + duplicado histórico
    (id alto, `activo=0`, herencia de H2.6) -- antes el MAX(id) GROUP BY
    serie colapsaba al duplicado inactivo y la serie entera desaparecía."""

    CASOS = [
        (13, 67, "Cámara de ionización", "N30013", "2123", "05/02/2024"),
        (7, 68, "Cámara de ionización", "N31014", "0453", "07/02/2024"),
        (16, 71, "Cámara de pozo", "HDR1000 Plus", "A972662", "07/02/2024"),
    ]

    def _poblar(self, ruta_bd, id_bueno, id_duplicado, equip_type, model, serie, fecha):
        _insertar_equipo(ruta_bd, id_bueno, equip_type=equip_type, model=model,
                         serie=serie, calibr_fact=1.0, fecha_calibr=fecha,
                         activo=1, vigente=1)
        _insertar_equipo(ruta_bd, id_duplicado, equip_type=equip_type, model=model,
                         serie=serie, calibr_fact=99.0, fecha_calibr="01/01/2025",
                         activo=0, vigente=0)

    @pytest.mark.parametrize("caso", CASOS, ids=["N30013", "N31014", "HDR1000-A972662"])
    def test_serie_aparece_en_el_combo(self, app, bd_temporal, caso):
        id_bueno, id_duplicado, equip_type, model, serie, fecha = caso
        self._poblar(bd_temporal, id_bueno, id_duplicado, equip_type, model, serie, fecha)

        obj = _instancia_pelada(QDate(2024, 3, 1))
        obj.commenu[0].clear()
        obj.commenu[0].addItems(["Seleccionar...", model])
        _seleccionar_modelo(obj, modelo=model)

        combo = _combo_serie(obj)
        textos = [combo.itemText(i) for i in range(combo.count())]
        assert any(serie in t for t in textos), (
            f"{model}/{serie} no aparece en el combo: {textos}")


class TestSerieConDosCalibracionesActivas:
    """A092535: dos calibraciones ACTIVAS de la misma serie (2022 y 2025),
    uso retroactivo legítimo. Deben aparecer como DOS entradas separadas, y
    elegir la de 2022 debe escribir el factor de 2022 -- no el que sea."""

    def _poblar(self, ruta_bd):
        _insertar_equipo(ruta_bd, 57, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A092535",
                         calibr_fact=46480, fecha_calibr="10/03/2022",
                         activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 77, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A092535",
                         calibr_fact=464700, fecha_calibr="21/07/2025",
                         activo=1, vigente=1)

    def test_produce_dos_entradas(self, app, bd_temporal):
        self._poblar(bd_temporal)
        obj = _instancia_pelada(QDate(2026, 7, 30))
        obj.commenu[0].clear()
        obj.commenu[0].addItems(["Seleccionar...", "HDR1000 Plus"])
        _seleccionar_modelo(obj, modelo="HDR1000 Plus")

        combo = _combo_serie(obj)
        textos_con_serie = [combo.itemText(i) for i in range(combo.count())
                            if "A092535" in combo.itemText(i)]
        assert len(textos_con_serie) == 2

    def test_elegir_2022_escribe_el_factor_de_2022(self, app, bd_temporal):
        self._poblar(bd_temporal)
        obj = _instancia_pelada(QDate(2022, 6, 1))  # control retroactivo, 2022
        obj.commenu[0].clear()
        obj.commenu[0].addItems(["Seleccionar...", "HDR1000 Plus"])
        _seleccionar_modelo(obj, modelo="HDR1000 Plus")

        combo = _combo_serie(obj)
        idx_2022 = next(i for i in range(combo.count())
                        if combo.itemData(i) == 57)
        combo.setCurrentIndex(idx_2022)

        assert _lineedit_calib(obj).text() == "46480"

    def test_elegir_2025_escribe_el_factor_de_2025(self, app, bd_temporal):
        self._poblar(bd_temporal)
        obj = _instancia_pelada(QDate(2026, 7, 30))
        obj.commenu[0].clear()
        obj.commenu[0].addItems(["Seleccionar...", "HDR1000 Plus"])
        _seleccionar_modelo(obj, modelo="HDR1000 Plus")

        combo = _combo_serie(obj)
        idx_2025 = next(i for i in range(combo.count())
                        if combo.itemData(i) == 77)
        combo.setCurrentIndex(idx_2025)

        assert _lineedit_calib(obj).text() == "464700"


class TestEtiquetaSinSimbolos:
    def test_ningun_item_del_combo_tiene_simbolos(self, app, bd_temporal):
        _insertar_equipo(bd_temporal, 1, equip_type="Cámara de ionización",
                         model="ModeloTest", serie="S1", calibr_fact=1.0,
                         fecha_calibr="01/01/2000", activo=1, vigente=1)
        obj = _instancia_pelada(QDate(2026, 7, 30))
        _seleccionar_modelo(obj)

        combo = _combo_serie(obj)
        for i in range(combo.count()):
            texto = combo.itemText(i)
            for simbolo in ("✓", "✗", "⚠️", "✅"):
                assert simbolo not in texto, f"símbolo {simbolo!r} en {texto!r}"


class TestEquipoInactivoNoApareceEnNingunCombo:
    def test_activo_cero_no_aparece(self, app, bd_temporal):
        _insertar_equipo(bd_temporal, 1, equip_type="Cámara de ionización",
                         model="ModeloTest", serie="S1", calibr_fact=1.0,
                         fecha_calibr="01/01/2020", activo=0, vigente=0)
        obj = _instancia_pelada(QDate(2026, 7, 30))
        _seleccionar_modelo(obj)

        combo = _combo_serie(obj)
        textos = [combo.itemText(i) for i in range(combo.count())]
        assert not any("S1" in t for t in textos)


class TestCalibracionVencidaApareceYEsSeleccionable:
    def _poblar(self, ruta_bd):
        _insertar_equipo(ruta_bd, 1, equip_type="Cámara de ionización",
                         model="ModeloTest", serie="S1", calibr_fact=0.5,
                         fecha_calibr="10/01/2020", activo=1, vigente=1)

    def test_aparece_marcada_vencida_y_se_puede_elegir(self, app, bd_temporal):
        self._poblar(bd_temporal)
        obj = _instancia_pelada(QDate(2026, 7, 30))  # muy posterior al vencimiento
        _seleccionar_modelo(obj)

        combo = _combo_serie(obj)
        idx = next(i for i in range(combo.count()) if "S1" in combo.itemText(i))
        assert "(vencida)" in combo.itemText(idx)

        combo.setCurrentIndex(idx)  # seleccionable
        assert _lineedit_calib(obj).text() == "0.5"


class TestMismaCalibracionVigenteOVencidaSegunFecha:
    """Misma fila, dos fechas de control distintas -- vigente/vencida cambia
    según self.date_box, no según ninguna columna congelada."""

    def _poblar(self, ruta_bd):
        _insertar_equipo(ruta_bd, 1, equip_type="Cámara de ionización",
                         model="ModeloTest", serie="S1", calibr_fact=0.5,
                         fecha_calibr="10/01/2024", activo=1, vigente=1)

    def test_vigente_en_control_retroactivo_vencida_en_control_actual(self, app, bd_temporal):
        self._poblar(bd_temporal)

        retro = _instancia_pelada(QDate(2024, 6, 15))
        _seleccionar_modelo(retro)
        combo_retro = _combo_serie(retro)
        idx_retro = next(i for i in range(combo_retro.count()) if "S1" in combo_retro.itemText(i))
        assert "(vencida)" not in combo_retro.itemText(idx_retro)

        actual = _instancia_pelada(QDate(2026, 7, 30))
        _seleccionar_modelo(actual)
        combo_actual = _combo_serie(actual)
        idx_actual = next(i for i in range(combo_actual.count()) if "S1" in combo_actual.itemText(i))
        assert "(vencida)" in combo_actual.itemText(idx_actual)


class TestGuardadoEquiposMedicion:
    """Integración de punta a punta con subirtodo_modificado: lo guardado
    en equipos_medicion es la serie limpia (nunca el texto decorado del
    combo) y equipo_id apunta a la fila elegida."""

    def _poblar(self, ruta_bd):
        _insertar_equipo(ruta_bd, 13, equip_type="Cámara de ionización",
                         model="N30013", serie="2123", calibr_fact=0.0545,
                         fecha_calibr="05/02/2024", activo=1, vigente=1)
        _insertar_equipo(ruta_bd, 999, equip_type="Cámara de ionización",
                         model="N30013", serie="2123", calibr_fact=9.99,
                         fecha_calibr="01/01/2010", activo=1, vigente=0)

    def _instancia_para_subir(self, bd_temporal, fecha_control):
        ref = _insertar_control(bd_temporal)
        obj = _instancia_pelada(fecha_control, n_grupos=3)
        obj.ref = ref
        return obj, ref

    def test_serie_guardada_es_limpia_sin_decoracion(self, app, bd_temporal):
        self._poblar(bd_temporal)
        obj, ref = self._instancia_para_subir(bd_temporal, QDate(2024, 3, 1))
        obj.commenu[0].clear()
        obj.commenu[0].addItems(["Seleccionar...", "N30013"])
        _seleccionar_modelo(obj, grupo=0, modelo="N30013")
        combo = _combo_serie(obj, grupo=0)
        idx_13 = next(i for i in range(combo.count()) if combo.itemData(i) == 13)
        combo.setCurrentIndex(idx_13)
        assert "—" in combo.currentText()  # de verdad viene decorado

        datos = ["N30013", combo.currentText(), _lineedit_calib(obj, 0).text(),
                "", "", "", "", "", ""]
        obj.subirtodo_modificado(datos)

        import sqlite3
        con = sqlite3.connect(bd_temporal)
        try:
            fila = con.execute(
                "SELECT serie, fecha_calibr, equipo_id FROM equipos_medicion WHERE ref=?",
                (ref,)).fetchone()
        finally:
            con.close()
        assert fila == ("2123", "05/02/2024", 13)

    def test_equipo_id_resuelve_a_la_misma_serie_y_fecha_que_la_copia(self, app, bd_temporal):
        self._poblar(bd_temporal)
        obj, ref = self._instancia_para_subir(bd_temporal, QDate(2024, 3, 1))
        obj.commenu[0].clear()
        obj.commenu[0].addItems(["Seleccionar...", "N30013"])
        _seleccionar_modelo(obj, grupo=0, modelo="N30013")
        combo = _combo_serie(obj, grupo=0)
        idx_13 = next(i for i in range(combo.count()) if combo.itemData(i) == 13)
        combo.setCurrentIndex(idx_13)

        datos = ["N30013", combo.currentText(), _lineedit_calib(obj, 0).text(),
                "", "", "", "", "", ""]
        obj.subirtodo_modificado(datos)

        import sqlite3
        con = sqlite3.connect(bd_temporal)
        try:
            serie_guardada, fecha_guardada, equipo_id = con.execute(
                "SELECT serie, fecha_calibr, equipo_id FROM equipos_medicion WHERE ref=?",
                (ref,)).fetchone()
        finally:
            con.close()

        catalogo = EquiposService.obtener_por_id(equipo_id)
        assert catalogo["serie"] == serie_guardada

    def test_dos_calibraciones_de_la_misma_serie_escriben_equipo_id_distinto(self, app, bd_temporal):
        """A092535: elegir la de 2022 y la de 2025 debe escribir equipo_id
        distinto -- el puntero desambigua lo que (modelo, serie, fecha) no
        garantiza por sí solo (§8.7 del plan)."""
        _insertar_equipo(bd_temporal, 57, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A092535",
                         calibr_fact=46480, fecha_calibr="10/03/2022",
                         activo=1, vigente=1)
        _insertar_equipo(bd_temporal, 77, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A092535",
                         calibr_fact=464700, fecha_calibr="21/07/2025",
                         activo=1, vigente=1)

        equipo_ids = []
        for id_esperado in (57, 77):
            ref = _insertar_control(bd_temporal, fecha=f"control-{id_esperado}")
            obj = _instancia_pelada(QDate(2026, 7, 30), n_grupos=3)
            obj.ref = ref
            obj.commenu[0].clear()
            obj.commenu[0].addItems(["Seleccionar...", "HDR1000 Plus"])
            _seleccionar_modelo(obj, grupo=0, modelo="HDR1000 Plus")
            combo = _combo_serie(obj, grupo=0)
            idx = next(i for i in range(combo.count()) if combo.itemData(i) == id_esperado)
            combo.setCurrentIndex(idx)

            datos = ["HDR1000 Plus", combo.currentText(), _lineedit_calib(obj, 0).text(),
                    "", "", "", "", "", ""]
            obj.subirtodo_modificado(datos)

            import sqlite3
            con = sqlite3.connect(bd_temporal)
            try:
                equipo_id = con.execute(
                    "SELECT equipo_id FROM equipos_medicion WHERE ref=?", (ref,)).fetchone()[0]
            finally:
                con.close()
            equipo_ids.append(equipo_id)

        assert equipo_ids[0] != equipo_ids[1]
        assert set(equipo_ids) == {57, 77}


class TestFilasHistoricasEquipoIdNull:
    def test_fila_sin_equipo_id_no_rompe_ninguna_consulta_de_listado(self, bd_temporal):
        import sqlite3
        ref = _insertar_control(bd_temporal)
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO equipos_medicion (ref, tipo_camara, equip_type, model, serie, "
            "calibr_fact, fecha_calibr) VALUES (?, 'Principal', 'Cámara de ionización', "
            "'N30013', '2123', 0.0545, '05/02/2024')", (ref,))
        con.commit()
        con.close()

        con = sqlite3.connect(bd_temporal)
        try:
            fila = con.execute(
                "SELECT tipo_camara, equip_type, model, serie, equipo_id "
                "FROM equipos_medicion WHERE ref=?", (ref,)).fetchone()
        finally:
            con.close()
        assert fila == ("Principal", "Cámara de ionización", "N30013", "2123", None)
