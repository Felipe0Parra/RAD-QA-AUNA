"""Test de ida y vuelta guardar↔cargar de DialogCalculadoraDosis (Fase D2.2).

Llena el diálogo REAL (offscreen) como lo haría el físico, lo guarda en una
BD SQLite temporal real (vía DosisService, sin mocks de persistencia), y
carga ese mismo registro en un SEGUNDO diálogo fresco para verificar que
cada campo vuelve idéntico. Es la única forma confiable de detectar
pérdida silenciosa de datos entre guardar y cargar.

EquiposService, QMessageBox y generar_reporte_calibracion van parcheados
(no hay catálogo real ni se genera PDF); todo lo demás — guardar_datos,
buscar_por_fecha, cargar_datos_desde_db — es el código de producción.
"""
import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

import ui.paginasGuia.dialogs as dialogs_mod
import services.dosis_service as dosis_service_mod
from ui.paginasGuia.dialogs import DialogCalculadoraDosis

EQUIPO_N31010 = {"id": 76, "equip_type": "Cámara de ionización", "model": "N31010",
                 "serie": "1825", "calibr_fact": 5.397, "t_cal": 20.0,
                 "p_cal": 101.325, "h_cal": 50.0}


class VentanaIX(QWidget):
    """Padre falso cuyo nombre termina en IX (el diálogo deduce el acelerador)."""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    monkeypatch.setattr(dosis_service_mod, "ruta_base_datos", lambda: ruta)
    yield ruta
    if os.path.exists(ruta):
        os.remove(ruta)


@pytest.fixture
def catalogo():
    """Catálogo mutable: permite simular una recalibración entre guardar y
    cargar, cambiando calibr_fact después de crear el registro original."""
    return dict(EQUIPO_N31010)


@pytest.fixture
def dialogo_factory(app, bd_temporal, catalogo, monkeypatch):
    reportes = []
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_modelos_unicos",
        staticmethod(lambda: [{"model": catalogo["model"], "equip_type": catalogo["equip_type"]}]))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_series_por_modelo",
        staticmethod(lambda m: [catalogo] if m == catalogo["model"] else []))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_por_id",
        staticmethod(lambda i: catalogo if i == catalogo["id"] else None))
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(
        dialogs_mod, "generar_reporte_calibracion",
        lambda **kwargs: reportes.append(kwargs))

    def _crear():
        return DialogCalculadoraDosis(energias=[], parent=VentanaIX())

    _crear.reportes = reportes
    return _crear


def llenar_flujo_fotones_completo(d):
    """Reproduce en el diálogo REAL una sesión típica de cálculo de dosis
    en fotones, tocando cada campo que guardar_db() persiste."""
    idx = d.combo_modelos.findData(EQUIPO_N31010["model"])
    d.combo_modelos.setCurrentIndex(idx)
    d.combo_series.setCurrentIndex(1)

    d.fotones.setChecked(True)
    d.SSD.setChecked(True)
    d.pulse.setChecked(True)
    d.combo_fieldsize.setCurrentIndex(0)

    d.humr_cal.setText("45.0")
    d.temp.setText("22.0")
    d.pressure.setText("101.325")
    d.humedad_r.setText("48.0")

    for campo, val in ((d.lDV1_1, "12.437"), (d.lDV1_2, "12.437"), (d.lDV1_3, "12.437")):
        campo.setText(val)
    d.unidades_monitor.setText("100")

    for campo in (d.Mminus1, d.Mminus2, d.Mminus3):
        campo.setText("-12.437")

    d.tension_v1.setText("400")
    d.tension_v2.setText("100")

    for campo, val in ((d.lect_m2_1, "12.430"), (d.lect_m2_2, "12.435"), (d.lect_m2_3, "12.440")):
        campo.setText(val)

    d.tpr2010.setText("0.68")
    d.pddzref.setText("66.6")
    return d


class TestIdaYVueltaCompleta:
    """Guarda un registro completo y lo recupera en un diálogo nuevo."""

    @pytest.fixture
    def registro_recuperado(self, dialogo_factory):
        original = llenar_flujo_fotones_completo(dialogo_factory())
        original.guardar_db()
        assert dialogo_factory.reportes, "guardar_db no llegó a generar el reporte (¿guardó?)"

        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)
        assert datos_bd is not None, "el registro no quedó en la BD"

        cargado = dialogo_factory()
        cargado.cargar_datos_desde_db(datos_bd)
        return original, cargado

    def test_factor_calibracion_no_se_pisa_con_el_catalogo_actual(
            self, dialogo_factory, catalogo):
        """El catálogo se recalibra DESPUÉS de guardar (5.397 → 5.500);
        cargar un registro histórico debe mostrar el factor CON EL QUE SE
        CALCULÓ en su momento, no el vigente hoy en equipos."""
        original = llenar_flujo_fotones_completo(dialogo_factory())
        assert original.visualize_calib.text() == "5.397"
        original.guardar_db()

        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)
        assert datos_bd["factor_calibracion"] == "5.397"

        catalogo["calibr_fact"] = 5.500  # recalibración posterior

        cargado = dialogo_factory()
        cargado.cargar_datos_desde_db(datos_bd)
        assert cargado.visualize_calib.text() == "5.397", (
            "se sobrescribió con el factor vigente del catálogo "
            f"({cargado.visualize_calib.text()}) en vez del histórico guardado")

    def test_lecturas_m2_individuales_sobreviven(self, registro_recuperado):
        original, cargado = registro_recuperado
        assert cargado.lect_m2_1.text() == "12.430"
        assert cargado.lect_m2_2.text() == "12.435"
        assert cargado.lect_m2_3.text() == "12.440"

    @pytest.mark.parametrize("campo", [
        "ktp", "Kpol", "cociente", "cociente_tensiones", "cociente_lecturas",
        "lect_m1", "a0", "a1", "a2", "ks", "Dzref",
    ])
    def test_campos_intermedios_sobreviven(self, registro_recuperado, campo):
        original, cargado = registro_recuperado
        original_val = getattr(original, campo).text()
        assert original_val, f"{campo} estaba vacío en el original — ajustar el flujo de llenado"
        assert getattr(cargado, campo).text() == original_val

    def test_equipo_id_se_recupera_para_poder_regrabar(self, registro_recuperado):
        original, cargado = registro_recuperado
        assert cargado.equipo_id == original.equipo_id == EQUIPO_N31010["id"]

    def test_resultado_final_sobrevive(self, registro_recuperado):
        original, cargado = registro_recuperado
        assert cargado.Kq_0.text() == original.Kq_0.text() == "0.99"
        assert cargado.dosis_maxima.text() == original.dosis_maxima.text()
        assert cargado.dosis_maxima.text() != ""


class TestProtocoloTrs398(object):
    """Trazabilidad del protocolo (2000/Rev.1) en guardar↔cargar (Fases K3+K4).

    guardar_db persiste "2000" por defecto (índice 0 del selector, el
    protocolo validado); cargar_datos_desde_db restaura el protocolo guardado
    y re-aplica Kq_0 al final (gana sobre cualquier recálculo intermedio); un
    registro legado sin la clave no rompe la carga.
    """

    def test_guardar_db_persiste_protocolo_2000_por_defecto(self, dialogo_factory):
        original = llenar_flujo_fotones_completo(dialogo_factory())
        assert original.combo_protocolo.currentData() == "2000"  # default (K4)
        original.guardar_db()

        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)
        assert datos_bd["protocolo_trs398"] == "2000"

    def test_round_trip_bd_preserva_protocolo_rev1(self, bd_temporal):
        """Round-trip a nivel de BD (sin pasar por el widget, que no existe
        aún): si el protocolo persistido es 'rev1', buscar_por_fecha lo
        devuelve intacto -- la columna no trunca ni normaliza el valor."""
        datos = {
            "Fecha": "09/07/2026", "Acelerador": "Clinac ix", "equipo_id": 1,
            "protocolo_trs398": "rev1",
        }
        assert dosis_service_mod.DosisService.guardar_datos(datos) is True
        recuperado = dosis_service_mod.DosisService.buscar_por_fecha("09/07/2026", "Clinac ix")
        assert recuperado["protocolo_trs398"] == "rev1"

    def test_cargar_con_protocolo_rev1_restaura_selector_y_kq_final_gana(
            self, dialogo_factory):
        """Un registro guardado con rev1: al cargarlo en un diálogo nuevo
        (que arranca en "2000" por default), el selector debe terminar en
        "rev1" -- restaurado ANTES que combo_modelos/tpr2010, para que
        cualquier cascada intermedia dispare on_modelo_cambiado/
        actualizar_kCharge ya con el protocolo correcto -- y el Kq_0 final
        debe ser el histórico guardado, no un recálculo intermedio."""
        original = llenar_flujo_fotones_completo(dialogo_factory())
        original.guardar_db()
        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)
        datos_bd["protocolo_trs398"] = "rev1"

        cargado = dialogo_factory()
        assert cargado.combo_protocolo.currentData() == "2000"  # default antes de cargar
        cargado.cargar_datos_desde_db(datos_bd)
        assert cargado.combo_protocolo.currentData() == "rev1"
        assert cargado.Kq_0.text() == datos_bd["Kq_0"]

    def test_registro_legado_sin_columna_protocolo_no_revienta(self, dialogo_factory):
        """Un registro guardado ANTES de K3 no tiene la clave en absoluto
        (dict.get devuelve None) -- cargar_datos_desde_db debe tratarlo como
        '2000' internamente, dejar el selector en '2000' y no fallar."""
        original = llenar_flujo_fotones_completo(dialogo_factory())
        original.guardar_db()
        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)
        del datos_bd["protocolo_trs398"]  # simula registro legado pre-K3

        cargado = dialogo_factory()
        cargado.cargar_datos_desde_db(datos_bd)  # no debe lanzar
        assert cargado.combo_protocolo.currentData() == "2000"
        assert cargado.Kq_0.text() == datos_bd["Kq_0"]

    def test_reporte_pdf_muestra_etiqueta_legible_del_protocolo(self):
        from models.PDF.reporte_calculadora_dos import datos_a_dataframe

        df_2000 = datos_a_dataframe({"protocolo_trs398": "2000"})
        assert df_2000["Valores"].iloc[0] == "TRS-398 (2000/2005)"

        df_rev1 = datos_a_dataframe({"protocolo_trs398": "rev1"})
        assert "Rev.1" in df_rev1["Valores"].iloc[0]
        assert "provisional" not in df_rev1["Valores"].iloc[0]

        # El código crudo persiste intacto en el dict de origen -- la
        # traducción es solo para mostrar en el PDF, no muta lo que se guarda.
        datos_originales = {"protocolo_trs398": "rev1"}
        datos_a_dataframe(datos_originales)
        assert datos_originales["protocolo_trs398"] == "rev1"


class TestMigracionColumnaProtocolo:
    """Fase K3: _asegurar_columna sobre una BD de esquema viejo (sin la
    columna protocolo_trs398), como sería cualquier copia de producción
    desplegada antes de esta fase."""

    def test_migracion_idempotente_sobre_esquema_viejo(self, bd_temporal):
        import sqlite3
        from services.dosis_service import DosisService

        # Crear la tabla en su forma VIEJA (sin protocolo_trs398), como
        # quedaría cualquier BD desplegada antes de K3.
        con = sqlite3.connect(bd_temporal)
        con.execute("""
            CREATE TABLE calculadora_dosimetrica (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Fecha TEXT, Acelerador TEXT
            )
        """)
        con.execute("INSERT INTO calculadora_dosimetrica (Fecha, Acelerador) VALUES ('01/01/2026', 'Clinac ix')")
        con.commit()
        con.close()

        # Primera corrida: agrega la columna.
        assert DosisService.crear_tabla() is True
        con = sqlite3.connect(bd_temporal)
        cols_1 = [c[1] for c in con.execute("PRAGMA table_info('calculadora_dosimetrica')").fetchall()]
        assert "protocolo_trs398" in cols_1
        assert con.execute("SELECT COUNT(*) FROM calculadora_dosimetrica").fetchone()[0] == 1
        valor = con.execute("SELECT protocolo_trs398 FROM calculadora_dosimetrica").fetchone()[0]
        assert valor == "2000"  # backfill vía DEFAULT, fila preexistente
        con.close()

        # Segunda corrida: idempotente, no duplica la columna ni pierde datos.
        assert DosisService.crear_tabla() is True
        con = sqlite3.connect(bd_temporal)
        cols_2 = [c[1] for c in con.execute("PRAGMA table_info('calculadora_dosimetrica')").fetchall()]
        assert cols_2.count("protocolo_trs398") == 1
        assert con.execute("SELECT COUNT(*) FROM calculadora_dosimetrica").fetchone()[0] == 1
        integridad = con.execute("PRAGMA integrity_check").fetchone()[0]
        assert integridad == "ok"
        con.close()


class TestAceleradorActualSiempreDefinido:
    """acelerador_actual se deriva del nombre de clase del padre; si no
    termina en IX/Hc/600 no debe quedar sin definir (AttributeError
    garantizado en guardar_db y cargar_datos_desde_db)."""

    def test_padre_de_tipo_desconocido_no_revienta(self, app, dialogo_factory):
        class VentanaDesconocida(QWidget):
            pass

        d = DialogCalculadoraDosis(energias=[], parent=VentanaDesconocida())
        assert d.acelerador_actual  # existe y no es None/""
