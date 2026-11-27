"""Las columnas nuevas de los anuales (tercera lectura de la tasa y dosis maxima del PDD del Halcyon), el guardado y la lectura que las aguantan, y el re-etiquetado por posicion de las tasas del anual del Clinac 600."""
import gc
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QCoreApplication, QEvent
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QWidget

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import loadtablacomplex
from scripts import migrar_bd_a_estandar as migrar_mod
from scripts.migrar_bd_a_estandar import migrar
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import DatabaseManager, PruebaMensual600

VIEJAS = ("Tasa mínima 100 cGy/min", "Tasa máxima 400 cGy/min", "Tasa máxima 600 cGy/min")
NUEVAS = ("Tasa mínima 80 cGy/min", "Tasa intermedia 240 cGy/min", "Tasa máxima 400 cGy/min")
DMAX = ["dmax_mm", "discrepancia_dmax_mm", "tolerancia_dmax_mm"]
CCM = "tabla_control_camaras_monitoras"


def reetiquetar_tasas_anual_600(ruta, usuario=None):
    return migrar_mod.reetiquetar_tasas_anual_600(ruta, usuario=usuario)


@pytest.fixture(scope="session")
def app():
    """La QApplication vive hasta el final de la sesion: si muriera al cerrar este modulo, la siguiente prueba crearia otra y Qt se cae al repintar."""
    return QApplication.instance() or QApplication([])


def _abrir(monkeypatch, ruta):
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    return Conexion()


@pytest.fixture
def bd(monkeypatch, tmp_path):
    ruta = str(tmp_path / "af1.db")
    conexion = _abrir(monkeypatch, ruta)
    conexion.con.executemany("INSERT INTO controles (id, equipo, control, fecha, activo) VALUES (?, ?, ?, ?, ?)",
                             [(10, "Clinac ix", "Anual", "07/2025", 1), (56, "Clinac 600", "Anual", "10/2025", 1),
                              (57, "Clinac ix", "Anual", "10/2025", 1), (58, "Clinac 600", "Mensual", "10/2025", 1),
                              (59, "Clinac 600", "Anual", "09/2025", 0), (60, " clinac 600 ", "Anual", "08/2025", 1)])
    conexion.con.commit()
    yield conexion, ruta
    conexion.con.close()
    Conexion._instance = None


def _columnas(con, tabla):
    return [c[1] for c in con.execute(f"PRAGMA table_info('{tabla}')").fetchall()]


def _tipos(con, tabla):
    return {c[1]: c[2] for c in con.execute(f"PRAGMA table_info('{tabla}')").fetchall()}


def _bloque(con, ref, tasas=VIEJAS, id_energia=0):
    filas = [("Fac. Calibración", 0.99), ("Reproducibilidad", ""), ("Linealidad R2", 1.0), *zip(tasas, (1.873, 1.85, 1.84)),
             ("Desviación estándar", 0.017), ("Observaciones", "Los indicadores de tasa de dosis no son los mismos que en el excel")]
    con.executemany(f"INSERT INTO {CCM} (ref, id_energia, indicador_medir, valor_medido) VALUES (?, ?, ?, ?)",
                    [(ref, id_energia, a, b) for a, b in filas])
    con.commit()


def _vigentes(con, ref):
    return con.execute(f"SELECT indicador_medir, valor_medido FROM {CCM} WHERE ref = ? AND (activo IS NULL OR activo = 1) ORDER BY id", (ref,)).fetchall()


def _tabla(creados, filas):
    tabla = QTableWidget(len(filas), len(filas[0]))
    creados.append(tabla)
    for f, fila in enumerate(filas):
        for c, texto in enumerate(fila):
            tabla.setItem(f, c, QTableWidgetItem(texto))
    return tabla


def _pelado(creados):
    obj = PruebaMensual600.__new__(PruebaMensual600)
    QWidget.__init__(obj)
    obj.db_manager = DatabaseManager()
    creados.append(obj)
    return obj


@pytest.fixture(autouse=True)
def creados():
    """Trampa 9: los widgets sueltos de la prueba se cierran y se borran al terminar cada caso (si no, una hoja de estilo posterior los repinta ya a medio destruir)."""
    widgets = []
    yield widgets
    for obj in widgets:
        obj.hide()
        obj.close()
        obj.deleteLater()
    widgets.clear()
    if QApplication.instance() is not None:
        for _ in range(3):
            QApplication.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


# --------------------------------------------------------------------------- el esquema

class TestLasColumnasNuevas:
    def test_la_lista_es_exactamente_la_autorizada_y_en_su_orden(self):
        assert conection_mod.COLUMNAS_NUEVAS_DE_LOS_ANUALES == (("anual_tasa_dosis", "med3", "REAL"), ("HC_dosimetria_anual", "dmax_mm", "REAL"),
                                                  ("HC_dosimetria_anual", "discrepancia_dmax_mm", "REAL"),
                                                  ("HC_dosimetria_anual", "tolerancia_dmax_mm", "REAL"))

    def test_una_base_nueva_las_tiene_al_final_y_son_real(self, bd):
        con = bd[0].con
        assert _columnas(con, "anual_tasa_dosis") == ["id", "ref", "id_energia", "tasa_um_min", "med1", "med2", "activo", "med3"]
        assert _columnas(con, "HC_dosimetria_anual")[-5:] == ["observaciones_dosi", "activo"] + DMAX
        tipos = {**_tipos(con, "anual_tasa_dosis"), **_tipos(con, "HC_dosimetria_anual")}
        assert [tipos[c] for c in ["med3"] + DMAX] == ["REAL"] * 4

    def test_una_base_vieja_las_gana_con_el_mismo_orden_sin_tocar_sus_filas(self, bd, monkeypatch):
        conexion, ruta = bd
        con = conexion.con
        for tabla, columna, _ in conection_mod.COLUMNAS_NUEVAS_DE_LOS_ANUALES:
            con.execute(f"ALTER TABLE {tabla} DROP COLUMN {columna}")
        con.execute("INSERT INTO anual_tasa_dosis (ref, id_energia, tasa_um_min, med1, med2) VALUES (10, 1, '100', 1.5, 1.6)")
        con.execute("INSERT INTO HC_dosimetria_anual (ref, id_energia, dosis_ref_cgy_um, observaciones_dosi) VALUES (10, 0, 1.0145, 'obs')")
        con.commit()
        antes = {t: con.execute(f"SELECT * FROM {t} ORDER BY id").fetchall() for t in ("anual_tasa_dosis", "HC_dosimetria_anual")}
        con.close()
        con = _abrir(monkeypatch, ruta).con
        assert _columnas(con, "anual_tasa_dosis")[-3:] == ["med2", "activo", "med3"]
        assert _columnas(con, "HC_dosimetria_anual")[-4:] == ["activo"] + DMAX
        for tabla, filas in antes.items():
            despues = con.execute(f"SELECT * FROM {tabla} ORDER BY id").fetchall()
            assert [f[:len(filas[0])] for f in despues] == filas
            assert all(v is None for f in despues for v in f[len(filas[0]):])

    def test_abrir_otra_vez_no_cambia_nada(self, bd, monkeypatch):
        conexion, ruta = bd
        esquema = lambda c: c.execute("SELECT name, sql FROM sqlite_master WHERE name IN ('anual_tasa_dosis', 'HC_dosimetria_anual') ORDER BY name").fetchall()
        antes = esquema(conexion.con)
        conexion.con.close()
        con = _abrir(monkeypatch, ruta).con
        assert esquema(con) == antes
        assert con.execute("SELECT COUNT(*) FROM anual_tasa_dosis").fetchone()[0] == 0

    def test_un_fallo_en_una_columna_avisa_y_no_corta_el_arranque(self, monkeypatch, tmp_path, capsys):
        original = conection_mod._asegurar_columna

        def falla_med3(cursor, tabla, columna, ddl):
            if columna == "med3":
                raise sqlite3.OperationalError("simulado")
            return original(cursor, tabla, columna, ddl)

        monkeypatch.setattr(conection_mod, "_asegurar_columna", falla_med3)
        con = _abrir(monkeypatch, str(tmp_path / "falla.db")).con
        try:
            assert "Aviso: no se pudo asegurar 'anual_tasa_dosis.med3'" in capsys.readouterr().out
            assert "med3" not in _columnas(con, "anual_tasa_dosis")
            assert _columnas(con, "HC_dosimetria_anual")[-3:] == DMAX
            nombres = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('trigger', 'index')").fetchall()}
            assert "idx_controles_unico_mes" in nombres
            assert sum(n.startswith("trg_no_borrar") for n in nombres) >= 4
        finally:
            con.close()
            Conexion._instance = None


# --------------------------------------------------------------------------- el guardado de una tabla anual

class TestElGuardadoCompletaSoloLaListaBlanca:
    def test_la_lista_blanca_es_solo_med3_de_la_tasa(self):
        assert load_mod.RELLENO_CON_NULL == {"anual_tasa_dosis": ("med3",)}

    def test_la_tasa_del_ix_sube_con_dos_lecturas_y_med3_queda_vacia(self, app, bd, creados):
        tabla = _tabla(creados, [["100", "1.0", "1.1"], ["300", "2.0", "2.1"], ["400", "3.0", "3.1"], ["600", "4.0", "4.1"]])
        assert loadtablacomplex("anual_tasa_dosis", tabla, [], reference=10, anual=True, id_energia=1, id=True) is True
        filas = bd[0].con.execute("SELECT tasa_um_min, med1, med2, med3 FROM anual_tasa_dosis WHERE ref = 10 AND activo = 1 ORDER BY id").fetchall()
        assert filas == [("100", 1.0, 1.1, None), ("300", 2.0, 2.1, None), ("400", 3.0, 3.1, None), ("600", 4.0, 4.1, None)]

    def test_la_tasa_con_tres_lecturas_guarda_med3(self, app, bd, creados):
        tabla = _tabla(creados, [["80", "1.87", "1.875", "1.875"], ["240", "1.85", "1.85", "1.85"], ["400", "1.84", "1.84", "1.84"]])
        assert loadtablacomplex("anual_tasa_dosis", tabla, [], reference=56, anual=True, id_energia=0, id=True) is True
        filas = bd[0].con.execute("SELECT tasa_um_min, med1, med2, med3 FROM anual_tasa_dosis WHERE ref = 56 AND activo = 1 ORDER BY id").fetchall()
        assert filas == [("80", 1.87, 1.875, 1.875), ("240", 1.85, 1.85, 1.85), ("400", 1.84, 1.84, 1.84)]

    def test_una_fila_con_mas_valores_que_columnas_sigue_fallando(self, app, bd, creados):
        tabla = _tabla(creados, [["100", "1", "2", "3", "4"]])
        assert loadtablacomplex("anual_tasa_dosis", tabla, [], reference=10, anual=True, id_energia=1, id=True) is False
        assert bd[0].con.execute("SELECT COUNT(*) FROM anual_tasa_dosis").fetchone()[0] == 0

    def test_la_tasa_con_una_sola_lectura_sigue_fallando(self, app, bd, creados):
        tabla = _tabla(creados, [["100", "1"]])
        assert loadtablacomplex("anual_tasa_dosis", tabla, [], reference=10, anual=True, id_energia=1, id=True) is False

    def test_otra_tabla_con_columnas_de_menos_sigue_fallando_y_no_anula_lo_vigente(self, app, bd, creados):
        con = bd[0].con
        con.execute("INSERT INTO anual_lecturas_transmision (ref, id_energia, accesorio, q1_in, q2_in, q1_out, q2_out, q_med, factor_t) "
                    "VALUES (10, 1, 'Open', 1, 1, 1, 1, 1, 1)")
        con.commit()
        tabla = _tabla(creados, [["Open", "1", "2", "3", "4"]])
        assert loadtablacomplex("anual_lecturas_transmision", tabla, [], reference=10, anual=True, id_energia=1, id=True) is False
        assert con.execute("SELECT COUNT(*) FROM anual_lecturas_transmision WHERE activo = 1").fetchone()[0] == 1


# --------------------------------------------------------------------------- la lectura (pruebatalas y la dosimetria por nombre)

class TestLaLecturaQuitaActivoPorNombre:
    def test_en_la_base_instalada_med3_no_se_lee_como_el_1_de_activo(self, app, bd, creados):
        con = bd[0].con
        con.execute("INSERT INTO anual_tasa_dosis (ref, id_energia, tasa_um_min, med1, med2, med3) VALUES (56, 0, '80', 1.87, 1.875, 1.876)")
        con.commit()
        filas = _pelado(creados).pruebatalas("anual_tasa_dosis", 56)
        assert [f[3:] for f in filas] == [("80", 1.87, 1.875, 1.876)]

    def test_en_una_base_con_med3_antes_de_activo_se_lee_igual(self, app, monkeypatch, tmp_path, creados):
        ruta = str(tmp_path / "otra_forma.db")
        crudo = sqlite3.connect(ruta)
        crudo.execute("CREATE TABLE anual_tasa_dosis (id INTEGER PRIMARY KEY AUTOINCREMENT, ref INTEGER, id_energia INTEGER, tasa_um_min TEXT, "
                      "med1 REAL, med2 REAL, med3 REAL, activo INTEGER DEFAULT 1)")
        crudo.commit()
        crudo.close()
        con = _abrir(monkeypatch, ruta).con
        try:
            assert _columnas(con, "anual_tasa_dosis")[-2:] == ["med3", "activo"]
            con.execute("INSERT INTO controles (id, equipo, control, fecha, activo) VALUES (56, 'Clinac 600', 'Anual', '10/2025', 1)")
            con.execute("INSERT INTO anual_tasa_dosis (ref, id_energia, tasa_um_min, med1, med2, med3) VALUES (56, 0, '80', 1.87, 1.875, 1.876)")
            con.commit()
            assert [f[3:] for f in _pelado(creados).pruebatalas("anual_tasa_dosis", 56)] == [("80", 1.87, 1.875, 1.876)]
        finally:
            con.close()
            Conexion._instance = None

    def test_la_dosimetria_del_halcyon_se_lee_con_cada_valor_en_su_columna(self, app, bd, monkeypatch, creados):
        con = bd[0].con
        con.execute("INSERT INTO HC_dosimetria_anual (ref, id_energia, dosis_ref_cgy_um, dmax_mm, discrepancia_dmax_mm, tolerancia_dmax_mm) "
                    "VALUES (10, 0, 1.0145, 12.01, 1.0, 1.5)")
        con.commit()
        obj, vistos = _pelado(creados), []
        monkeypatch.setattr(obj, "_rellenar_campos", lambda df, datos, readonly=False, nombre_tabla=None: vistos.append(datos))
        assert obj._cargar_de_bd([], "HC_dosimetria_anual", 10) is True
        datos = vistos[0]
        assert "activo" not in datos
        assert (datos["dosis_ref_cgy_um"], datos["dmax_mm"], datos["discrepancia_dmax_mm"], datos["tolerancia_dmax_mm"]) == (1.0145, 12.01, 1.0, 1.5)

    def test_la_dosimetria_mensual_conserva_su_origen_de_referencia(self, app, bd, monkeypatch, creados):
        con = bd[0].con
        assert _columnas(con, "dosimetriaMen")[-1] == "origen_referencia"
        con.execute("INSERT INTO dosimetriaMen (ref, origen_referencia) VALUES (58, 'tabla')")
        con.commit()
        obj, vistos = _pelado(creados), []
        monkeypatch.setattr(obj, "_rellenar_campos", lambda df, datos, readonly=False, nombre_tabla=None: vistos.append(datos))
        assert obj._cargar_de_bd([], "dosimetriaMen", 58) is True
        assert vistos[0]["origen_referencia"] == "tabla" and "activo" not in vistos[0]


# --------------------------------------------------------------------------- el re-etiquetado de las tasas del 600

class TestElReetiquetadoPorPosicion:
    def test_las_etiquetas_de_la_herramienta_son_las_del_formato(self):
        assert migrar_mod.ETIQUETAS_VIEJAS_TASA_600 == VIEJAS and migrar_mod.ETIQUETAS_NUEVAS_TASA_600 == NUEVAS

    def test_la_tasa_maxima_400_pasa_a_intermedia_240_y_no_a_maxima_400(self, bd):
        con, ruta = bd[0].con, bd[1]
        _bloque(con, 56)
        resultado = reetiquetar_tasas_anual_600(ruta, usuario="admin")
        vigentes = dict(_vigentes(con, 56))
        assert vigentes["Tasa intermedia 240 cGy/min"] == 1.85
        assert vigentes["Tasa mínima 80 cGy/min"] == 1.873 and vigentes["Tasa máxima 400 cGy/min"] == 1.84
        assert not set(VIEJAS[:1] + VIEJAS[2:]) & set(vigentes)
        assert [r["estado"] for r in resultado] == ["re-etiquetado"]
        assert resultado[0]["cambios"] == [(VIEJAS[0], NUEVAS[0], 1.873), (VIEJAS[1], NUEVAS[1], 1.85), (VIEJAS[2], NUEVAS[2], 1.84)]

    def test_el_equipo_se_compara_normalizado(self, bd):
        con, ruta = bd[0].con, bd[1]
        _bloque(con, 60)
        assert [r["ref"] for r in reetiquetar_tasas_anual_600(ruta)] == [60]
        assert set(NUEVAS) <= {d[0] for d in _vigentes(con, 60)} and not set(VIEJAS) - set(NUEVAS) & {d[0] for d in _vigentes(con, 60)}

    def test_el_resto_del_bloque_queda_igual_y_lo_viejo_queda_anulado(self, bd):
        con, ruta = bd[0].con, bd[1]
        _bloque(con, 56)
        antes = _vigentes(con, 56)
        reetiquetar_tasas_anual_600(ruta)
        despues = _vigentes(con, 56)
        assert [a for a in despues if a[0] not in NUEVAS] == [a for a in antes if a[0] not in VIEJAS]
        assert [d[0] for d in despues] == ["Fac. Calibración", "Reproducibilidad", "Linealidad R2", *NUEVAS, "Desviación estándar", "Observaciones"]
        anuladas = con.execute(f"SELECT indicador_medir, valor_medido FROM {CCM} WHERE ref = 56 AND activo = 0 ORDER BY id").fetchall()
        assert anuladas == antes

    def test_una_fila_de_auditoria_por_bloque_con_su_detalle(self, bd):
        con, ruta = bd[0].con, bd[1]
        _bloque(con, 56)
        _bloque(con, 56, id_energia=1)                # otra energia del mismo control es otro bloque: re-etiquetar uno no anula el otro
        _bloque(con, 60)
        reetiquetar_tasas_anual_600(ruta, usuario="admin")
        filas = con.execute("SELECT usuario, accion, ref, detalle FROM audit_log WHERE tabla = ? ORDER BY id", (CCM,)).fetchall()
        assert [(f[0], f[1], f[2]) for f in filas] == [("admin", "migracion", "56"), ("admin", "migracion", "56"), ("admin", "migracion", "60")]
        detalle = ("re-etiquetado por posicion de las tasas del anual del Clinac 600: 'Tasa mínima 100 cGy/min' -> 'Tasa mínima 80 cGy/min'; "
                   "'Tasa máxima 400 cGy/min' -> 'Tasa intermedia 240 cGy/min'; 'Tasa máxima 600 cGy/min' -> 'Tasa máxima 400 cGy/min'")
        assert [f[3] for f in filas] == [detalle] * 3
        vigentes = con.execute(f"SELECT id_energia, indicador_medir FROM {CCM} WHERE ref = 56 AND activo = 1 ORDER BY id_energia, id").fetchall()
        assert [e for e, _ in vigentes] == [0] * 8 + [1] * 8
        assert [d for _, d in vigentes if d in NUEVAS] == list(NUEVAS) * 2

    def test_una_segunda_corrida_no_cambia_nada(self, bd):
        con, ruta = bd[0].con, bd[1]
        _bloque(con, 56)
        reetiquetar_tasas_anual_600(ruta)
        filas = con.execute(f"SELECT COUNT(*) FROM {CCM}").fetchone()[0]
        auditoria = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        assert reetiquetar_tasas_anual_600(ruta) == []
        assert con.execute(f"SELECT COUNT(*) FROM {CCM}").fetchone()[0] == filas
        assert con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == auditoria

    def test_no_toca_el_ix_ni_el_mensual_ni_un_control_anulado(self, bd):
        con, ruta = bd[0].con, bd[1]
        for ref in (57, 58, 59):
            _bloque(con, ref)
        _bloque(con, 56, tasas=(), id_energia=1)      # un bloque vigente del 600 sin filas de tasa no es un caso saltado: ni se toca ni se informa
        antes = {ref: _vigentes(con, ref) for ref in (56, 57, 58, 59)}
        assert reetiquetar_tasas_anual_600(ruta) == []
        assert {ref: _vigentes(con, ref) for ref in (56, 57, 58, 59)} == antes

    @pytest.mark.parametrize("tasas", [(VIEJAS[0], VIEJAS[1], "Tasa x"), (VIEJAS[1], VIEJAS[0], VIEJAS[2]), (VIEJAS[0], VIEJAS[0], VIEJAS[2])])
    def test_sin_las_tres_etiquetas_viejas_en_su_orden_salta_y_avisa(self, bd, tasas):
        con, ruta = bd[0].con, bd[1]
        _bloque(con, 56, tasas=tasas)
        _bloque(con, 60, id_energia=None)             # las tres viejas en su orden pero sin energia: tampoco se toca
        antes = {ref: _vigentes(con, ref) for ref in (56, 60)}
        resultado = reetiquetar_tasas_anual_600(ruta)
        assert [(r["ref"], r["estado"].startswith("saltado")) for r in resultado] == [(56, True), (60, True)]
        assert {ref: _vigentes(con, ref) for ref in (56, 60)} == antes
        assert con.execute("SELECT COUNT(*) FROM audit_log WHERE tabla = ?", (CCM,)).fetchone()[0] == 0

    def test_la_corrida_en_seco_lo_reporta_y_no_toca_la_base(self, bd, capsys):
        con, ruta = bd[0].con, bd[1]
        _bloque(con, 56)
        con.close()
        Conexion._instance = None
        with open(ruta, "rb") as f:
            antes = f.read()
        resultado = migrar(ruta, aplicar=False)
        salida = capsys.readouterr().out
        with open(ruta, "rb") as f:
            assert f.read() == antes
        assert [r["estado"] for r in resultado["reetiquetado_tasas_600"]] == ["re-etiquetado"]
        assert "Re-etiquetado de las tasas del anual del Clinac 600 (por posicion)" in salida
        assert "'Tasa máxima 400 cGy/min' -> 'Tasa intermedia 240 cGy/min' (valor 1.85)" in salida

    def test_aplicar_la_herramienta_re_etiqueta(self, bd, capsys):
        con, ruta = bd[0].con, bd[1]
        _bloque(con, 56)
        con.close()
        Conexion._instance = None
        resultado = migrar(ruta, aplicar=True, usuario="admin")
        salida = capsys.readouterr().out
        assert [r["estado"] for r in resultado["reetiquetado_tasas_600"]] == ["re-etiquetado"]
        assert "Re-etiquetado de las tasas del anual del Clinac 600 (por posicion)" in salida
        assert "'Tasa máxima 400 cGy/min' -> 'Tasa intermedia 240 cGy/min' (valor 1.85)" in salida
        otra = sqlite3.connect(ruta)
        try:
            assert [d[0] for d in _vigentes(otra, 56)][3:6] == list(NUEVAS)
        finally:
            otra.close()
        assert migrar_mod.reetiquetar_tasas_anual_600(ruta) == []
