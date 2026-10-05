"""PI.7 (PLAN_POSICION_INICIAL_BRAQUI_01-10.md, DA-82 D2): la fila "Desplazamiento inicial (mm)" del PDF mensual de braquiterapia
imprime la posición inicial de la FUENTE EN USO (el texto breve de la prueba que vale en la fecha y para la serie de esa
calibración), con su incertidumbre, y dura lo que dura la fuente. Sin prueba vigente (o con la serie de otra fuente, DD8) queda
EXACTAMENTE el valor que ya traía la calibración: los PDF de siempre no cambian una letra.

Lo que se garantiza, cada cosa con su prueba:
  - con prueba: el cambio de fuente S1, su calibración redundante y un control mensual de la misma serie dentro del período
    dicen el texto breve (con "±" y "(k = 2)", y el cambio de fuente al que pertenece);
  - sin prueba aplicable: el valor viejo IDÉNTICO (el mismo objeto: un REAL como 0.13, un texto, 'No Aplica' o la clave ausente)
    -- otra serie (DD8), el cambio de fuente siguiente, una prueba anulada, serie vacía o ausente, fecha ilegible o ausente;
  - un "No medible" se imprime (manda la prueba, no el valor del método retirado);
  - sin `CondicionesMedicion` no hay fila y el servicio ni se llama; un fallo del servicio no se traga (un PDF firmado no sale
    con un valor que no es el de la fuente en uso);
  - la regla vive en el servicio: el PDF solo llama a `texto_para_pdf` (AST), y la etiqueta de la fila no cambia (08-09);
  - de punta a punta, sobre `reporte_mensual` real y el PDF generado, leído con `fitz`.
La siembra y la BD temporal son las de PI.3. Se siembra TODO antes de abrir ninguna conexión de Qt: una escritura por sqlite3 entre
aperturas de la conexión Qt rompe el reporte (medido por Opus el 03-10, 'disk I/O error'; la causa probable son dos SQLite en un
proceso)."""
import ast
import inspect
import os
import sqlite3
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from services import posicion_inicial_braqui as svc
from test_pi3_servicio_posicion_inicial import (S1, S2, SERIE_A, SERIE_B, _calibracion, _guardar, _sembrar,  # noqa: F401
                                                _sembrar_prueba, _sql, bd, plantilla)

ETIQUETA = "Desplazamiento inicial (mm)"
AUSENTE = object()          # la clave `desplazamiento_ini` ni siquiera viene en la fila de CondicionesMedicion


@pytest.fixture(scope="module")
def rm():
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import data.ManejoDatos.load  # noqa: F401  (antes que models.PDF: el ciclo de importaciones, como test_r1_r6)
    from models.PDF.Mensuales import reportes_mensuales
    return reportes_mensuales


def _datos(fecha, serie, desplazamiento=0.13, con_condiciones=True, tipo="Cambio de fuente"):
    condiciones = {"t": 21.5, "p": 640, "h": 40}
    if desplazamiento is not AUSENTE:
        condiciones["desplazamiento_ini"] = desplazamiento
    return {"fecha": fecha, "serie": serie, "tipo": tipo,
            "CondicionesMedicion": [condiciones] if con_condiciones else []}


def _filas(df):
    """{etiqueta: valor} de la tabla de condiciones (sin la fila de encabezado)."""
    return {fila[0]: fila[1] for fila in df.values.tolist() if fila[0] != "Campo"}


def _celda(rm, datos):
    return _filas(rm._crear_tabla_condiciones_medicion(datos))[ETIQUETA]


@pytest.fixture
def con_p1(bd):
    """Dos cambios de fuente (S1, serie A; S2, serie B), las calibraciones de la siembra de PI.3 y la prueba P1 de S1 guardada de
    verdad por el servicio (placa sintética): lo que vale para todo el período de S1."""
    ids = _sembrar(bd)
    id_p1 = _guardar(S1)
    # lo que imprime un PDF: el texto breve con la cifra unida a su unidad (PI.8, `unir_numero_y_unidad`; la prueba de la regla está en
    # test_pi8, con el espacio duro escrito a mano: aquí solo se exige que la fila diga lo que `texto_para_pdf` entrega)
    esperado = svc.unir_numero_y_unidad(svc.texto_breve(svc.posicion_inicial_para(S1)))
    return bd, ids, id_p1, esperado


# -------------------------------------------------------------------------------------------------- con prueba vigente

class TestConPruebaVigente:
    def test_el_texto_esperado_es_de_verdad_una_posicion_inicial(self, con_p1):
        _, _, _, esperado = con_p1
        assert "±" in esperado and "(k = 2)" in esperado and f"Cambio de fuente del {S1}" in esperado

    @pytest.mark.parametrize("fecha,serie,tipo", [
        (f"{S1} 15:03:03", SERIE_A, "Cambio de fuente"),                  # el propio cambio de fuente
        (f"{S1} 15:20:00", SERIE_A, "Calibración Redundante"),            # la calibración redundante del mismo día
        ("2026-02-20 10:00:00", SERIE_A, "Control Mensual"),              # un control mensual de la misma serie dentro del período
        ("2026-04-14 23:59:00", SERIE_A, "Control Mensual"),              # el último día del período
        ("2026-02-20 10:00:00", SERIE_A, ""),                             # una fila de tipo vacío (las hay en la BD real)
    ])
    def test_la_fila_dice_el_texto_breve_en_los_tres_tipos(self, rm, con_p1, fecha, serie, tipo):
        _, _, _, esperado = con_p1
        assert _celda(rm, _datos(fecha, serie, tipo=tipo)) == esperado

    def test_manda_la_prueba_y_no_el_valor_del_metodo_retirado(self, rm, con_p1):
        _, _, _, esperado = con_p1
        for viejo in (0.13, "No Aplica", 5.46, AUSENTE):
            assert _celda(rm, _datos(f"{S1} 15:03:03", SERIE_A, viejo)) == esperado

    def test_las_otras_filas_de_la_tabla_no_cambian(self, rm, con_p1):
        df = rm._crear_tabla_condiciones_medicion(_datos(f"{S1} 15:03:03", SERIE_A))
        filas = _filas(df)
        assert filas["Temperatura de medida (°C)"] == 21.5
        assert filas["Presión de medida (mmHg)"] == 640
        assert filas["Humedad de medida (%)"] == 40
        assert list(df.columns) == ["Condiciones de medición", ""]
        assert df.values.tolist()[0] == ["Campo", "Valor"] and len(df) == 5

    def test_el_texto_no_lleva_marcado_ni_simbolos_que_rompan_el_paragraph(self, rm, con_p1):
        texto = _celda(rm, _datos(f"{S1} 15:03:03", SERIE_A))
        assert not any(c in texto for c in "<>&")


# ------------------------------------------------------------------------------ sin prueba aplicable: el valor de siempre

class TestSinPruebaAplicable:
    @pytest.mark.parametrize("fecha,serie,por_que", [
        ("2026-03-01 08:00:00", "OTRA-SERIE", "otra serie dentro del período de S1 (DD8)"),
        ("2026-02-20 10:00:00", SERIE_B, "la serie de S2 en el período de S1 (DD8)"),
        (f"{S2} 09:30:00", SERIE_B, "el cambio de fuente siguiente: otra fuente, sin prueba"),
        ("2026-05-20 10:00:00", SERIE_B, "un control mensual de S2"),
        ("2025-12-01 10:00:00", SERIE_A, "antes de que existiera el cambio de fuente S1"),
        ("2026-02-20 10:00:00", "", "serie vacía"),
        ("2026-02-20 10:00:00", None, "serie ausente"),
        ("27-09-2025", SERIE_A, "fecha en el formato histórico, ilegible"),
        (None, SERIE_A, "fecha ausente"),
        ("no es una fecha", SERIE_A, "fecha que no es una fecha"),
    ])
    @pytest.mark.parametrize("viejo", [0.13, 5.46, "No Aplica", "", None, AUSENTE])
    def test_queda_exactamente_el_valor_que_ya_traia(self, rm, con_p1, fecha, serie, por_que, viejo):
        celda = _celda(rm, _datos(fecha, serie, viejo))
        if viejo is AUSENTE:
            assert celda == "No Aplica"
        elif viejo is None:
            assert celda is None or celda != celda      # None o NaN de pandas: la celda vacía de siempre
        else:
            assert celda == viejo and type(celda) is type(viejo), por_que

    def test_con_la_prueba_anulada_vuelve_el_valor_viejo(self, rm, con_p1):
        bd, _, id_p1, esperado = con_p1
        assert _celda(rm, _datos(f"{S1} 15:03:03", SERIE_A)) == esperado
        svc.anular(id_p1, "Fisico de prueba", "prueba")
        assert _celda(rm, _datos(f"{S1} 15:03:03", SERIE_A)) == 0.13

    def test_sin_ninguna_prueba_en_la_bd_todo_queda_como_hoy(self, rm, bd):
        _sembrar(bd)
        assert _celda(rm, _datos(f"{S1} 15:03:03", SERIE_A)) == 0.13
        assert _celda(rm, _datos(f"{S1} 15:03:03", SERIE_A, "No Aplica")) == "No Aplica"


# ------------------------------------------------------------------------------------------------------- no medible

class TestNoMedible:
    def test_un_no_medible_se_imprime_y_no_se_vuelve_al_valor_viejo(self, rm, bd):
        _sembrar(bd)
        _sembrar_prueba(bd, S1)         # sin estado del gris: el servicio lo dice "No medible"
        esperado = svc.texto_breve(svc.posicion_inicial_para(S1))
        assert esperado.startswith("No medible")
        celda = _celda(rm, _datos(f"{S1} 15:03:03", SERIE_A, 0.13))
        assert celda == esperado and "0.13" not in celda


# --------------------------------------------------------------------------- sin CondicionesMedicion y fallos del servicio

class TestSinCondicionesYFallos:
    def test_sin_condiciones_de_medicion_no_hay_fila_y_el_servicio_no_se_llama(self, rm, con_p1, monkeypatch):
        def prohibido(*a, **k):
            raise AssertionError("el servicio no debe llamarse sin CondicionesMedicion")
        monkeypatch.setattr(svc, "texto_para_pdf", prohibido)
        df = rm._crear_tabla_condiciones_medicion(_datos(f"{S1} 15:03:03", SERIE_A, con_condiciones=False))
        assert df.empty and list(df.columns) == ["Condiciones de medición", ""]

    def test_un_fallo_del_servicio_no_se_traga(self, rm, con_p1, monkeypatch):
        def revienta(*a, **k):
            raise sqlite3.OperationalError("disco lleno")
        monkeypatch.setattr(svc, "posicion_inicial_para", revienta)
        with pytest.raises(sqlite3.OperationalError):
            rm._crear_tabla_condiciones_medicion(_datos(f"{S1} 15:03:03", SERIE_A))

    def test_la_regla_recibe_la_fecha_y_la_serie_de_la_calibracion(self, rm, con_p1, monkeypatch):
        llamadas = []
        original = svc.posicion_inicial_para
        monkeypatch.setattr(svc, "posicion_inicial_para", lambda fecha, serie=svc.SIN_FILTRO_DE_SERIE:
                            (llamadas.append((fecha, serie)), original(fecha, serie))[1])
        _celda(rm, _datos("2026-02-20 10:00:00", SERIE_A))
        assert llamadas == [("2026-02-20 10:00:00", SERIE_A)]


# --------------------------------------------------------------------------------------------- una sola definición (AST)

class TestUnaSolaDefinicion:
    def _arbol(self):
        import models.PDF.Mensuales.reportes_mensuales as rm
        return ast.parse(Path(inspect.getsourcefile(rm)).read_text(encoding="utf-8"))

    def test_el_pdf_solo_importa_texto_para_pdf_del_servicio(self):
        importados = [(nodo.module, a.name) for nodo in ast.walk(self._arbol()) if isinstance(nodo, ast.ImportFrom)
                      and nodo.module and nodo.module.startswith("services.posicion_inicial_braqui") for a in nodo.names]
        assert importados == [("services.posicion_inicial_braqui", "texto_para_pdf")]

    def test_el_pdf_no_busca_ni_arma_la_prueba_por_su_cuenta(self):
        import models.PDF.Mensuales.reportes_mensuales as rm
        texto = Path(inspect.getsourcefile(rm)).read_text(encoding="utf-8")
        for resto in ("braqui_posicion_inicial", "posicion_inicial_para", "texto_breve", "cambios_de_fuente"):
            assert resto not in texto, f"el PDF mensual no debe conocer {resto}: lo único que llama es texto_para_pdf"

    def test_la_etiqueta_de_la_fila_no_cambia(self, rm, con_p1):
        # Regla del 08-09: no se quita ni se renombra una fila que el físico nombró; cambia su valor.
        df = rm._crear_tabla_condiciones_medicion(_datos(f"{S1} 15:03:03", SERIE_A))
        assert ETIQUETA in _filas(df)
        assert [f[0] for f in df.values.tolist()] == ["Campo", "Temperatura de medida (°C)", "Presión de medida (mmHg)",
                                                       "Humedad de medida (%)", ETIQUETA]

    def test_el_servicio_devuelve_none_sin_prueba_y_el_texto_breve_con_ella(self, con_p1):
        _, _, _, esperado = con_p1
        assert svc.texto_para_pdf(f"{S1} 15:03:03", serie=SERIE_A) == esperado
        assert svc.texto_para_pdf(f"{S1} 15:03:03") == esperado                    # sin serie (el diario)
        assert svc.texto_para_pdf(f"{S2} 09:30:00", serie=SERIE_B) is None
        assert svc.texto_para_pdf("2026-02-20", serie=SERIE_B) is None
        assert svc.texto_para_pdf("no es una fecha") is None


# ------------------------------------------------------------------------------------------- de punta a punta (PDF real)

def _con_condiciones(ruta, id_calibracion, fecha, desplazamiento):
    """La fila de CondicionesMedicion de una calibración ya sembrada (lo que imprime la tabla de la fila) y la mínima de
    MaximosCamaras: sin ella el constructor del gráfico de máximos devuelve None y el generador del PDF revienta."""
    _sql(ruta, "INSERT INTO CondicionesMedicion (ref, fecha, t, p, h, desplazamiento_ini, activo) VALUES (?, ?, 21.5, 640, 40, ?, 1)",
         (id_calibracion, fecha, desplazamiento))
    _sql(ruta, "INSERT INTO MaximosCamaras (ref, user, fecha, posicion, medida1, medida2, promedio) VALUES (?, 'Siembra', ?, '0', '1', '1', '1')",
         (id_calibracion, fecha))


def _texto_del_pdf(rm, ruta, fecha, tipo, monkeypatch):
    """El PDF mensual REAL de `reporte_mensual` (sin abrir el visor), como texto plano. Vacía la captura antes de cada PDF y da la
    prueba por fallida si el reporte avisa de un error (reporte_mensual se traga los errores en un QMessageBox.critical)."""
    import fitz
    from PyQt5.QtSql import QSqlDatabase
    from PyQt5.QtWidgets import QMessageBox

    errores, captura = [], {}
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: errores.append(a)))
    for tipo_aviso in ("information", "warning"):
        monkeypatch.setattr(QMessageBox, tipo_aviso, staticmethod(lambda *a, **k: None))

    class FalsoVisor:
        def __init__(self, pdf_data=None, **k):
            captura["pdf"] = pdf_data

        def show(self):
            pass

    class Pantalla:
        def opeenDatabase(self):
            if QSqlDatabase.contains("qt_sql_default_connection"):
                QSqlDatabase.removeDatabase("qt_sql_default_connection")
            db = QSqlDatabase.addDatabase("QSQLITE")
            db.setDatabaseName(ruta)
            db.open()
            return db

    monkeypatch.setattr(rm, "PdfViewer", FalsoVisor)
    rm.reporte_mensual(Pantalla(), fecha, "Braquiterapia", "IDC", tipo, None, None, "")
    assert not errores, f"el reporte avisó de un error: {errores}"
    assert "pdf" in captura, "no se generó ningún PDF"
    doc = fitz.open(stream=captura["pdf"], filetype="pdf")
    try:
        return " ".join("\n".join(pagina.get_text() for pagina in doc).split())
    finally:
        doc.close()


class TestPdfRealDeBraquiterapia:
    def test_el_pdf_dice_la_posicion_inicial_de_la_fuente_en_uso_y_los_otros_no_cambian(self, rm, bd, monkeypatch):
        # Todo se siembra ANTES de abrir ninguna conexión de Qt (ver el docstring del archivo).
        ids = _sembrar(bd)
        _con_condiciones(bd, ids["s1"], f"{S1} 15:03:03", 0.13)
        _con_condiciones(bd, ids["mensual_a"], "2026-02-20 10:00:00", "No Aplica")
        _con_condiciones(bd, ids["s2"], f"{S2} 09:30:00", 0.13)           # otra fuente: sin prueba
        _guardar(S1)
        esperado = " ".join(svc.texto_breve(svc.posicion_inicial_para(S1)).split())

        cambio = _texto_del_pdf(rm, bd, S1, "Cambio de fuente", monkeypatch)
        assert ETIQUETA in cambio
        assert esperado in cambio, "el PDF no dice el texto breve de la prueba"
        mensual = _texto_del_pdf(rm, bd, "2026-02-20", "Control Mensual", monkeypatch)
        assert esperado in mensual, "el control mensual de la misma serie dentro del período también lo dice"
        siguiente = _texto_del_pdf(rm, bd, S2, "Cambio de fuente", monkeypatch)
        assert ETIQUETA in siguiente and esperado not in siguiente and "±" not in siguiente
        assert "0.13" in siguiente, "sin prueba, el PDF conserva el valor que traía la calibración"
