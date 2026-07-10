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
EQUIPO_N34001 = {"id": 55, "equip_type": "Cámara de ionización", "model": "N34001",
                 "serie": "1069", "calibr_fact": 0.08563, "t_cal": 20.0,
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
def catalogo_electrones():
    return dict(EQUIPO_N34001)


@pytest.fixture
def dialogo_factory_electrones(app, bd_temporal, catalogo_electrones, monkeypatch):
    """Espejo de dialogo_factory pero con la Roos (N34001) en el catálogo
    simulado -- necesario para los tests de round-trip de ELECTRONES (E4)."""
    reportes = []
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_modelos_unicos",
        staticmethod(lambda: [{"model": catalogo_electrones["model"],
                              "equip_type": catalogo_electrones["equip_type"]}]))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_series_por_modelo",
        staticmethod(lambda m: [catalogo_electrones] if m == catalogo_electrones["model"] else []))
    monkeypatch.setattr(
        dialogs_mod.EquiposService, "obtener_por_id",
        staticmethod(lambda i: catalogo_electrones if i == catalogo_electrones["id"] else None))
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(
        dialogs_mod, "generar_reporte_calibracion",
        lambda **kwargs: reportes.append(kwargs))

    def _crear():
        return DialogCalculadoraDosis(energias=[], parent=VentanaIX())

    _crear.reportes = reportes
    return _crear


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
    d.Zref.setText("10.0")  # anotación manual, sin cascada -- F3 exige completo
    d.Zmax.setText("1.5")
    return d


def llenar_flujo_electrones_completo(d):
    """Reproduce en el diálogo REAL una sesión de electrones con la Roos
    (N34001) -- valores centinela de la hoja real Enero/iX 12 MeV (auditoría
    2026-07-10, mismos usados en TestFlujoElectronesRoos de la suite UI)."""
    idx = d.combo_modelos.findData(EQUIPO_N34001["model"])
    d.combo_modelos.setCurrentIndex(idx)
    d.combo_series.setCurrentIndex(1)

    d.electrones.setChecked(True)
    d.SSD.setChecked(True)
    d.pulse.setChecked(True)

    d.temp.setText("21.9")
    d.pressure.setText("85.43")
    d.humr_cal.setText("45.0")
    d.humedad_r.setText("48.0")

    for campo in (d.lDV1_1, d.lDV1_2, d.lDV1_3):
        campo.setText("21.36")
    d.unidades_monitor.setText("200")

    for campo in (d.Mminus1, d.Mminus2, d.Mminus3):
        campo.setText("-20.93")

    d.tension_v1.setText("200")
    d.tension_v2.setText("50")

    for campo, val in ((d.lect_m2_1, "20.52"), (d.lect_m2_2, "20.52"), (d.lect_m2_3, "20.52")):
        campo.setText(val)

    d.R50.setText("5.127")
    d.pddzrefE.setText("99.3")
    d.Zref.setText("3.0")  # anotación manual, sin cascada -- F3 exige completo
    d.Zmax.setText("2.7")
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


class TestIdaYVueltaElectrones:
    """E4 (auditoría 2026-07-10): antes de este fix, cargar un registro de
    ELECTRONES dejaba R50/calidad/zref/kQ-electrones/PDD vacíos y el kQ
    guardado (clave compartida "Kq_0") caía en el widget de FOTONES.
    Demostrado empíricamente offscreen antes de escribir el fix."""

    @pytest.fixture
    def registro_recuperado(self, dialogo_factory_electrones):
        original = llenar_flujo_electrones_completo(dialogo_factory_electrones())
        original.guardar_db()
        assert dialogo_factory_electrones.reportes, "guardar_db no generó el reporte (¿guardó?)"

        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)
        assert datos_bd is not None, "el registro no quedó en la BD"

        cargado = dialogo_factory_electrones()
        cargado.cargar_datos_desde_db(datos_bd)
        return original, cargado

    def test_r50_medido_persiste_y_se_guarda(self, dialogo_factory_electrones):
        original = llenar_flujo_electrones_completo(dialogo_factory_electrones())
        original.guardar_db()
        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)
        assert datos_bd["r50_medido"] == "5.127"
        assert datos_bd["pdd_zref_electrones"] == "99.3"
        assert datos_bd["Tipo_de_radiacion"] == "Electrones"

    def test_r50_se_restaura_y_reconstruye_calidad_y_zref(self, registro_recuperado):
        original, cargado = registro_recuperado
        assert cargado.R50.text() == original.R50.text() == "5.127"
        assert cargado.QualityR50.text() == original.QualityR50.text() == "5.2157"
        assert cargado.zrefR50.text() == original.zrefR50.text() == "3.0294"

    def test_kq_electrones_termina_en_el_widget_correcto_no_en_fotones(
            self, registro_recuperado):
        """El bug central: antes, el kQ de electrones guardado se restauraba
        siempre en self.Kq_0 (fotones); Kq0r50_widget quedaba vacío."""
        original, cargado = registro_recuperado
        assert cargado.Kq0r50_widget.text() == original.Kq0r50_widget.text() == "0.91027"
        assert cargado.Kq_0.text() == "", (
            f"Kq_0 (widget de FOTONES) no debería tener valor en un registro "
            f"de electrones, tiene {cargado.Kq_0.text()!r}")

    def test_pdd_electrones_persiste_y_dosis_maxima_se_recalcula_igual(
            self, registro_recuperado):
        original, cargado = registro_recuperado
        assert cargado.pddzrefE.text() == original.pddzrefE.text() == "99.3"
        assert cargado.Dzref.text() == original.Dzref.text() == "0.0099693"
        assert cargado.dosis_maxima.text() == original.dosis_maxima.text() == "0.0100396"

    def test_registro_legado_sin_r50_ni_pdd_no_revienta(self, dialogo_factory_electrones):
        """Un registro guardado ANTES de E4 no tiene 'r50_medido' ni
        'pdd_zref_electrones' (dict.get -> None). El kQ guardado sigue
        yendo al widget correcto (el fix principal no depende de las
        columnas nuevas); R50/PDD simplemente quedan vacíos, sin excepción."""
        original = llenar_flujo_electrones_completo(dialogo_factory_electrones())
        original.guardar_db()
        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)
        del datos_bd["r50_medido"]
        del datos_bd["pdd_zref_electrones"]

        cargado = dialogo_factory_electrones()
        cargado.cargar_datos_desde_db(datos_bd)  # no debe lanzar
        assert cargado.R50.text() == ""
        assert cargado.pddzrefE.text() == ""
        assert cargado.Kq0r50_widget.text() == "0.91027"  # el fix principal no depende de esto
        assert cargado.Kq_0.text() == ""


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


class TestMigracionColumnaR50PddElectrones:
    """E4 (auditoría 2026-07-10): _asegurar_columna sobre una BD de esquema
    viejo (sin r50_medido/pdd_zref_electrones), como sería cualquier copia
    de producción desplegada antes de esta auditoría. Mismo patrón que
    TestMigracionColumnaProtocolo (K3); ensayo previo repetido a mano contra
    una COPIA real de AUNA_2026_2/BaseDatosQA.db (32MB) confirmó lo mismo:
    idempotente, integrity_check=ok, conteos intactos, filas preexistentes
    leen NULL sin romper la carga."""

    def test_migracion_idempotente_sobre_esquema_viejo(self, bd_temporal):
        import sqlite3
        from services.dosis_service import DosisService

        con = sqlite3.connect(bd_temporal)
        con.execute("""
            CREATE TABLE calculadora_dosimetrica (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Fecha TEXT, Acelerador TEXT, protocolo_trs398 TEXT DEFAULT '2000'
            )
        """)
        con.execute("INSERT INTO calculadora_dosimetrica (Fecha, Acelerador) VALUES ('01/01/2026', 'Clinac ix')")
        con.commit()
        con.close()

        assert DosisService.crear_tabla() is True
        con = sqlite3.connect(bd_temporal)
        cols_1 = [c[1] for c in con.execute("PRAGMA table_info('calculadora_dosimetrica')").fetchall()]
        assert "r50_medido" in cols_1
        assert "pdd_zref_electrones" in cols_1
        assert con.execute("SELECT COUNT(*) FROM calculadora_dosimetrica").fetchone()[0] == 1
        fila = con.execute(
            "SELECT r50_medido, pdd_zref_electrones FROM calculadora_dosimetrica").fetchone()
        assert fila == (None, None)  # backfill: columna nueva sin DEFAULT -> NULL, no revienta
        con.close()

        # Segunda corrida: idempotente, no duplica columnas ni pierde datos.
        assert DosisService.crear_tabla() is True
        con = sqlite3.connect(bd_temporal)
        cols_2 = [c[1] for c in con.execute("PRAGMA table_info('calculadora_dosimetrica')").fetchall()]
        assert cols_2.count("r50_medido") == 1
        assert cols_2.count("pdd_zref_electrones") == 1
        assert con.execute("SELECT COUNT(*) FROM calculadora_dosimetrica").fetchone()[0] == 1
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        con.close()


class TestValidacionFormularioCompleto:
    """F3 (auditoría 2026-07-10): decisión explícita del usuario -- "todos
    los campos deben estar completos" antes de permitir guardar. Motivada por
    el único registro real de producción, guardado casi vacío sin ninguna
    validación previa (calculadora_dosimetrica id=1, 09/04/2026)."""

    def _espiar_avisos(self, monkeypatch):
        avisos = []
        monkeypatch.setattr(
            dialogs_mod.QMessageBox, "warning",
            staticmethod(lambda *a, **k: avisos.append(a[1:3])))
        return avisos

    def test_formulario_vacio_no_guarda_y_avisa(self, dialogo_factory, monkeypatch):
        avisos = self._espiar_avisos(monkeypatch)
        d = dialogo_factory()
        d.fotones.setChecked(True)  # nada más llenado
        d.guardar_db()

        fecha = d.date_edit.date().toString("dd/MM/yyyy")
        assert dosis_service_mod.DosisService.buscar_por_fecha(fecha, d.acelerador_actual) is None
        assert any("incompleto" in a[0].lower() for a in avisos), avisos
        assert not dialogo_factory.reportes, "no debía generarse el reporte con formulario vacío"

    def test_formulario_completo_guarda_sin_avisar(self, dialogo_factory, monkeypatch):
        avisos = self._espiar_avisos(monkeypatch)
        original = llenar_flujo_fotones_completo(dialogo_factory())
        original.guardar_db()
        assert not avisos, f"no debía avisar con el formulario completo: {avisos}"
        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        assert dosis_service_mod.DosisService.buscar_por_fecha(
            fecha, original.acelerador_actual) is not None

    def test_falta_un_solo_campo_bloquea_el_guardado(self, dialogo_factory, monkeypatch):
        """Zref/Zmax son anotación manual sin cascada de cálculo -- ningún
        otro campo los llena por sí solo. Si el físico olvida uno, debe
        bloquear (no basta con que el resto de la cadena esté completa)."""
        avisos = self._espiar_avisos(monkeypatch)
        d = llenar_flujo_fotones_completo(dialogo_factory())
        d.Zref.clear()
        d.guardar_db()
        assert avisos, "debía avisar con Zref vacío"
        assert "Zref" in avisos[0][1]
        fecha = d.date_edit.date().toString("dd/MM/yyyy")
        assert dosis_service_mod.DosisService.buscar_por_fecha(fecha, d.acelerador_actual) is None

    def test_electrones_exige_r50_y_pdd_no_pddzref(self, dialogo_factory_electrones, monkeypatch):
        """La exigencia de PDD es condicional al Tipo_de_radiacion: un
        registro de electrones no debe reclamar 'pddzref' (campo de fotones,
        que en electrones queda vacío por diseño -- mutuamente excluyentes)."""
        avisos = self._espiar_avisos(monkeypatch)
        d = dialogo_factory_electrones()
        d.electrones.setChecked(True)  # nada más llenado
        d.guardar_db()
        assert avisos
        faltantes_reportados = avisos[0][1]
        assert "r50_medido" in faltantes_reportados
        assert "pdd_zref_electrones" in faltantes_reportados
        assert "pddzref" not in faltantes_reportados.replace("pdd_zref_electrones", "")

    def test_electrones_completo_guarda_sin_avisar(
            self, dialogo_factory_electrones, monkeypatch):
        avisos = self._espiar_avisos(monkeypatch)
        original = llenar_flujo_electrones_completo(dialogo_factory_electrones())
        original.guardar_db()
        assert not avisos, f"no debía avisar con el formulario de electrones completo: {avisos}"
        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        assert dosis_service_mod.DosisService.buscar_por_fecha(
            fecha, original.acelerador_actual) is not None

    def test_pdd10_pdd20_tmrzref_no_se_exigen(self):
        """Hallazgo lateral (F3): pdd10/pdd20 existen como QLineEdit pero su
        bloque completo (pdd_box) nunca se agrega a ningún layout -- el
        físico no puede verlos ni llenarlos. tmrzref solo aplica a geometría
        SAD, desactivada. Exigirlos bloquearía el guardado para siempre."""
        requeridos = dialogs_mod.DialogCalculadoraDosis._CAMPOS_SIEMPRE_REQUERIDOS
        assert "pdd10" not in requeridos
        assert "pdd20" not in requeridos
        assert "tmrzref" not in requeridos


class TestAceleradorActualSiempreDefinido:
    """acelerador_actual se deriva del nombre de clase del padre; si no
    termina en IX/Hc/600 no debe quedar sin definir (AttributeError
    garantizado en guardar_db y cargar_datos_desde_db)."""

    def test_padre_de_tipo_desconocido_no_revienta(self, app, dialogo_factory):
        class VentanaDesconocida(QWidget):
            pass

        d = DialogCalculadoraDosis(energias=[], parent=VentanaDesconocida())
        assert d.acelerador_actual  # existe y no es None/""
