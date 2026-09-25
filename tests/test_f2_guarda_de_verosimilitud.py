"""F.2 (PLAN_HANDOFF_IMAGENES_22-09.md §7): un valor que no se parece a nada de lo conocido para esa energía pide
confirmación explícita al fijar una referencia.

CAUSA [medida en la BD]: el 22-09 a las 10:22:44 se archivó `Clinac ix / 15mv / 0.483` -- el valor de 6 MeV bajo 15 MV
(fila 4 de `referencias_qc`; a las 10:24:07 se corrigió a 0.761). Nada avisó. El contrato anular+insertar protege la
unicidad, no el valor: de no haberlo visto el físico, todos los controles de 15 MV se habrían juzgado contra la referencia
de un haz de electrones.

Lo que este archivo garantiza:
  1. EL CASO REAL -- fijar 0.483 en `Clinac ix / 15mv` avisa; 0.761 no; 0.483 en `6mev` no.
  2. EL MARGEN NO SALTA CON LO NORMAL -- ni el mínimo ni el máximo de las 45 mediciones reales de calidad de cada pareja,
     ni los valores de referencia que de verdad se usan, disparan el aviso, y el margen (20 %) es el doble de la mayor
     dispersión medida (9.92 %).
  3. LAS DOS FUENTES -- el valor de respaldo de la aplicación y la mediana de lo guardado en los controles vigentes de esa
     pareja; concordar con UNA basta; sin nada con qué comparar no se dice nada.
  4. AVISA, NO BLOQUEA -- el servicio fija igual, la pantalla pregunta con "No" por omisión, y si se confirma queda anotado en
     la auditoría.
"""
import os
import sqlite3
import statistics

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services import referencias_qc as servicio
from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.paginasGuia.referencias import Referencias

RESPALDO = PruebaMensual600.VALORES_REFERENCIA_CALIDAD_RESPALDO
SIMBOLOS_PROHIBIDOS = "✓✔✗✘✕❌✅⚠ⓘ"

# Las 45 mediciones reales de `calidad_pdd20_10` de la copia del 21-09, por pareja (equipo, energía): min y max.
MEDIDAS_REALES = {
    ("Clinac 600", "6mv"): (0.657, 0.667), ("Clinac ix", "12mev"): (0.572, 0.593),
    ("Clinac ix", "15mev"): (0.567, 0.602), ("Clinac ix", "15mv"): (0.757, 0.765),
    ("Clinac ix", "6mev"): (0.461, 0.509), ("Clinac ix", "6mv"): (0.663, 0.668),
    ("Clinac ix", "9mev"): (0.482, 0.513), ("Halcyon", "6mv"): (0.620, 0.623),
}
# Las referencias que de verdad se usan (las 8 vigentes de `referencias_qc`)
REFERENCIAS_USADAS = {
    ("Clinac 600", "6mv"): 0.6667, ("Clinac ix", "6mv"): 0.665, ("Clinac ix", "15mv"): 0.761,
    ("Clinac ix", "6mev"): 0.483, ("Clinac ix", "9mev"): 0.500, ("Clinac ix", "12mev"): 0.606,
    ("Clinac ix", "15mev"): 0.605, ("Halcyon", "6mv"): 0.627,
}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    con = sqlite3.connect(ruta)
    con.execute("INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) "
                "VALUES ('lamaya', 'x', 'Luz Adriana Maya', 1, '1', 'Físico Médico', 'jefe')")
    con.commit()
    con.close()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


_MES = [0]


def _control(ruta, equipo, energia, val_teo, activo_control=1, activo_dosi=1):
    """Un control vigente (o anulado) de `equipo` con su dosimetría de `energia` guardada con la referencia `val_teo`.
    Cada uno en su propio mes: el índice único de `controles` no admite dos vigentes del mismo mes y equipo."""
    _MES[0] += 1
    con = sqlite3.connect(ruta)
    cur = con.execute("INSERT INTO controles (fecha, control, equipo, activo) VALUES (?,'Mensual',?,?)",
                      (f"{_MES[0] % 12 + 1:02d}/{2000 + _MES[0] // 12}", equipo, activo_control))
    con.execute("INSERT INTO dosimetriaMen (ref, energia, val_teo_calidad, activo) VALUES (?,?,?,?)",
                (cur.lastrowid, energia, val_teo, activo_dosi))
    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# 1. EL CASO REAL
# ---------------------------------------------------------------------------

def test_fijar_0483_en_15mv_del_ix_avisa_y_dice_las_dos_cifras(bd_temporal):
    v = servicio.evaluar_verosimilitud("Clinac ix", "calidad", "15mv", 0.483, respaldo=RESPALDO["15mv"])
    assert v is not None
    assert v.comparaciones[0].origen == "valor de respaldo de la aplicación"
    assert v.comparaciones[0].referencia == 0.761 and v.comparaciones[0].desviacion == pytest.approx(0.3653, abs=1e-3)
    texto = v.texto()
    assert "0.483" in texto and "0.761" in texto and "36.5 %" in texto and "Clinac ix (15mv)" in texto
    assert not any(s in texto for s in SIMBOLOS_PROHIBIDOS)                                  # DA-18


def test_fijar_0761_en_15mv_no_avisa(bd_temporal):
    assert servicio.evaluar_verosimilitud("Clinac ix", "calidad", "15mv", 0.761, respaldo=RESPALDO["15mv"]) is None


def test_fijar_0483_en_6mev_no_avisa(bd_temporal):
    assert servicio.evaluar_verosimilitud("Clinac ix", "calidad", "6mev", 0.483, respaldo=RESPALDO["6mev"]) is None


def test_el_error_del_22_09_es_el_de_la_fila_4_de_la_bd_real():
    """La prueba reproduce lo archivado: la fila 4 de `referencias_qc` de la copia del 21-09 (activo = 0, corregida a las
    10:24:07 por la fila 5)."""
    from _bd_referencia import BD_REBUILD_21_09
    if not BD_REBUILD_21_09.exists():
        pytest.skip("falta la BD de referencia")
    con = sqlite3.connect(f"file:{BD_REBUILD_21_09}?mode=ro", uri=True)
    filas = con.execute("SELECT equipo, magnitud, energia, valor, fecha FROM referencias_qc WHERE id IN (4, 5)"
                        " ORDER BY id").fetchall()
    con.close()
    assert filas == [("Clinac ix", "calidad", "15mv", 0.483, "2026-09-22 10:22:44"),
                     ("Clinac ix", "calidad", "15mv", 0.761, "2026-09-22 10:24:07")]
    assert servicio.evaluar_verosimilitud("Clinac ix", "calidad", "15mv", filas[0][3], respaldo=RESPALDO["15mv"]) is not None
    assert servicio.evaluar_verosimilitud("Clinac ix", "calidad", "15mv", filas[1][3], respaldo=RESPALDO["15mv"]) is None


# ---------------------------------------------------------------------------
# 2. EL MARGEN NO SALTA CON LO NORMAL
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pareja", sorted(MEDIDAS_REALES))
def test_ninguna_medicion_real_dispara_el_aviso(bd_temporal, pareja):
    equipo, energia = pareja
    for medida in MEDIDAS_REALES[pareja]:
        assert servicio.evaluar_verosimilitud(equipo, "calidad", energia, medida, respaldo=RESPALDO[energia]) is None, medida


@pytest.mark.parametrize("pareja", sorted(REFERENCIAS_USADAS))
def test_ninguna_referencia_realmente_usada_dispara_el_aviso(bd_temporal, pareja):
    equipo, energia = pareja
    assert servicio.evaluar_verosimilitud(equipo, "calidad", energia, REFERENCIAS_USADAS[pareja], respaldo=RESPALDO[energia]) is None


def test_el_margen_es_el_doble_de_la_mayor_dispersion_medida_y_menos_que_el_error_a_atrapar():
    dispersiones = [(hi - lo) / statistics.mean((lo, hi)) for lo, hi in MEDIDAS_REALES.values()]
    assert max(dispersiones) == pytest.approx(0.0992, abs=1e-3)
    assert servicio.MARGEN_VEROSIMILITUD == 0.20 and 2 * max(dispersiones) == pytest.approx(servicio.MARGEN_VEROSIMILITUD, abs=0.01)
    assert servicio.MARGEN_VEROSIMILITUD < abs(0.483 - 0.761) / 0.761                     # 36.5 %: el caso real queda fuera


def test_el_limite_es_inclusivo_del_lado_de_no_molestar(bd_temporal):
    base = RESPALDO["6mv"]
    assert servicio.evaluar_verosimilitud("Halcyon", "calidad", "6mv", base * 1.20, respaldo=base) is None
    assert servicio.evaluar_verosimilitud("Halcyon", "calidad", "6mv", base * 0.80, respaldo=base) is None
    assert servicio.evaluar_verosimilitud("Halcyon", "calidad", "6mv", base * 1.21, respaldo=base) is not None
    assert servicio.evaluar_verosimilitud("Halcyon", "calidad", "6mv", base * 0.79, respaldo=base) is not None


def test_un_decimal_corrido_avisa(bd_temporal):
    assert servicio.evaluar_verosimilitud("Halcyon", "calidad", "6mv", 0.0627, respaldo=RESPALDO["6mv"]) is not None
    assert servicio.evaluar_verosimilitud("Halcyon", "calidad", "6mv", 6.27, respaldo=RESPALDO["6mv"]) is not None


# ---------------------------------------------------------------------------
# 3. LAS DOS FUENTES
# ---------------------------------------------------------------------------

def test_lo_guardado_en_los_controles_es_la_segunda_fuente(bd_temporal):
    for _ in range(3):
        _control(bd_temporal, "Halcyon", "6mv", 0.627)
    v = servicio.evaluar_verosimilitud("Halcyon", "calidad", "6mv", 0.95, respaldo=RESPALDO["6mv"])
    origenes = [c.origen for c in v.comparaciones]
    assert origenes == ["valor de respaldo de la aplicación", "mediana de las referencias de 3 control(es) guardado(s)"]
    assert v.comparaciones[1].referencia == pytest.approx(0.627)
    assert "0.665" in v.texto() and "0.627" in v.texto() and "3 control(es)" in v.texto()


def test_concordar_con_lo_guardado_basta_aunque_el_respaldo_este_desactualizado(bd_temporal):
    """Un equipo cuyo respaldo quedó viejo: el valor nuevo coincide con lo que ya usan los controles."""
    for _ in range(2):
        _control(bd_temporal, "Halcyon", "6mv", 0.50)
    assert servicio.evaluar_verosimilitud("Halcyon", "calidad", "6mv", 0.50, respaldo=0.665) is None


def test_concordar_con_el_respaldo_basta_aunque_lo_guardado_sea_otra_cosa(bd_temporal):
    """Volver al respaldo tras un valor guardado por error no es sospechoso."""
    _control(bd_temporal, "Clinac ix", "15mv", 0.483)
    assert servicio.evaluar_verosimilitud("Clinac ix", "calidad", "15mv", 0.761, respaldo=0.761) is None


def test_la_mediana_no_se_deja_arrastrar_por_un_valor_guardado_por_error(bd_temporal):
    for valor in (0.761, 0.761, 0.483):
        _control(bd_temporal, "Clinac ix", "15mv", valor)
    v = servicio.evaluar_verosimilitud("Clinac ix", "calidad", "15mv", 0.30, respaldo=None)
    assert v.comparaciones[0].referencia == 0.761                    # la media daría 0.668


def test_lo_guardado_solo_cuenta_si_es_de_esa_pareja_y_vigente(bd_temporal):
    _control(bd_temporal, "Halcyon", "15mv", 0.9)                                  # otra energía
    _control(bd_temporal, "Clinac ix", "6mv", 0.9)                                 # otro equipo
    _control(bd_temporal, "Halcyon", "6mv", 0.9, activo_control=0)                 # control anulado
    _control(bd_temporal, "Halcyon", "6mv", 0.9, activo_dosi=0)                    # dosimetría anulada
    _control(bd_temporal, "Halcyon", "6mv", None)                                  # sin referencia guardada
    v = servicio.evaluar_verosimilitud("Halcyon", "calidad", "6mv", 0.30, respaldo=0.665)
    assert [c.origen for c in v.comparaciones] == ["valor de respaldo de la aplicación"]


def test_el_equipo_se_compara_sin_distinguir_mayusculas(bd_temporal):
    _control(bd_temporal, "Clinac iX", "6mv", 0.665)                               # la grafía histórica
    assert servicio.evaluar_verosimilitud("Clinac ix", "calidad", "6mv", 0.30, respaldo=None).comparaciones[0].referencia == 0.665


def test_sin_nada_con_que_comparar_no_se_dice_nada(bd_temporal):
    assert servicio.evaluar_verosimilitud("Halcyon", "calidad", "6mv", 0.30, respaldo=None) is None
    assert servicio.evaluar_verosimilitud("Halcyon", "calidad", "6mv", 0.30) is None


@pytest.mark.parametrize("valor", [0, -1, "abc", None, float("nan"), float("inf"), ""])
def test_un_valor_invalido_no_es_asunto_de_esta_guarda(bd_temporal, valor):
    """Un valor que no es un número válido lo rechaza `fijar_referencia`; aquí no se dice nada."""
    assert servicio.evaluar_verosimilitud("Halcyon", "calidad", "6mv", valor, respaldo=0.665) is None


def test_otra_magnitud_sin_historial_solo_usa_el_respaldo_que_se_le_pase(bd_temporal):
    assert servicio.evaluar_verosimilitud("Halcyon", "tol_dosis", "", 2.0) is None
    assert servicio.evaluar_verosimilitud("Halcyon", "tol_dosis", "", 20.0, respaldo=2.0) is not None


# ---------------------------------------------------------------------------
# 4. AVISA, NO BLOQUEA
# ---------------------------------------------------------------------------

def test_el_servicio_fija_igual_un_valor_inusual_y_anota_el_aviso_en_la_auditoria(bd_temporal):
    v = servicio.evaluar_verosimilitud("Clinac ix", "calidad", "15mv", 0.483, respaldo=RESPALDO["15mv"])
    assert servicio.fijar_referencia("Clinac ix", "calidad", "15mv", 0.483, "prueba", "confirmado por el físico", "lamaya",
                            advertencia=v.resumen()) == (True, None)
    con = sqlite3.connect(bd_temporal)
    (detalle,) = con.execute("SELECT detalle FROM audit_log WHERE tabla='referencias_qc'").fetchone()
    valor = con.execute("SELECT valor FROM referencias_qc").fetchone()[0]
    con.close()
    assert valor == 0.483
    assert "confirmado pese al aviso" in detalle and "valor de respaldo de la aplicación 0.761 (36.5 %)" in detalle


def test_sin_aviso_la_auditoria_no_lleva_esa_nota(bd_temporal):
    servicio.fijar_referencia("Clinac ix", "calidad", "15mv", 0.761, "prueba", "normal", "lamaya")
    con = sqlite3.connect(bd_temporal)
    (detalle,) = con.execute("SELECT detalle FROM audit_log WHERE tabla='referencias_qc'").fetchone()
    con.close()
    assert "pese al aviso" not in detalle


# ---------------------------------------------------------------------------
# 5. LA PESTAÑA
# ---------------------------------------------------------------------------

class _Usuario:
    def __init__(self, usuario):
        self._usuario = usuario


@pytest.fixture
def dialogos(monkeypatch):
    """Trampa 2: ningún diálogo real. Guarda lo que la pantalla preguntó y cómo (título, texto, botón por omisión)."""
    estado = {"respuesta": QMessageBox.Yes, "preguntas": [], "otros": []}

    def pregunta(*a, **k):
        estado["preguntas"].append({"titulo": a[1], "texto": a[2], "por_omision": a[4] if len(a) > 4 else None})
        return estado["respuesta"]

    monkeypatch.setattr(QMessageBox, "question", staticmethod(pregunta))
    for nombre in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, nombre, staticmethod(lambda *a, _n=nombre, **k: estado["otros"].append(_n)))
    return estado


def _fijar_desde_la_pantalla(valor, equipo="Clinac ix", energia="15mv"):
    p = Referencias(_Usuario("lamaya"))
    p.cb_equipo.setCurrentText(equipo)
    p.cb_energia.setCurrentIndex(p.cb_energia.findData(energia))
    p.in_valor.setText(valor)
    p.in_fuente.setText("prueba")
    p.in_observaciones.setText("prueba")
    p._on_fijar()
    return p


def _vigentes(ruta):
    con = sqlite3.connect(ruta)
    filas = con.execute("SELECT equipo, energia, valor FROM referencias_qc WHERE activo IS NULL OR activo=1").fetchall()
    con.close()
    return filas


def test_la_pantalla_avisa_con_las_cifras_y_pregunta_con_no_por_omision(app, bd_temporal, dialogos):
    _fijar_desde_la_pantalla("0.483")
    (pregunta,) = dialogos["preguntas"]
    assert pregunta["titulo"] == "Valor inusual"
    assert "0.483" in pregunta["texto"] and "0.761" in pregunta["texto"] and "36.5 %" in pregunta["texto"]
    assert "los ya guardados conservan el que tenían" in pregunta["texto"]          # el mensaje de siempre sigue
    assert pregunta["por_omision"] == QMessageBox.No


def test_si_la_persona_dice_que_no_no_se_fija_nada(app, bd_temporal, dialogos):
    dialogos["respuesta"] = QMessageBox.No
    _fijar_desde_la_pantalla("0.483")
    assert _vigentes(bd_temporal) == [] and dialogos["otros"] == []


def test_si_la_persona_confirma_se_fija_de_todas_formas_y_queda_anotado(app, bd_temporal, dialogos):
    """Avisa, no bloquea: el físico manda."""
    _fijar_desde_la_pantalla("0.483")
    assert _vigentes(bd_temporal) == [("Clinac ix", "15mv", 0.483)]
    con = sqlite3.connect(bd_temporal)
    (detalle,) = con.execute("SELECT detalle FROM audit_log WHERE tabla='referencias_qc'").fetchone()
    con.close()
    assert "confirmado pese al aviso" in detalle


def test_un_valor_normal_pregunta_lo_de_siempre_sin_aviso(app, bd_temporal, dialogos):
    _fijar_desde_la_pantalla("0.761")
    (pregunta,) = dialogos["preguntas"]
    assert pregunta["titulo"] == "Fijar referencia" and "se aparta" not in pregunta["texto"]
    assert _vigentes(bd_temporal) == [("Clinac ix", "15mv", 0.761)]


def test_0483_en_6mev_no_lleva_aviso_en_la_pantalla(app, bd_temporal, dialogos):
    _fijar_desde_la_pantalla("0.483", energia="6mev")
    (pregunta,) = dialogos["preguntas"]
    assert pregunta["titulo"] == "Fijar referencia"


def test_la_pantalla_toma_el_respaldo_del_mensual(app):
    for energia, valor in RESPALDO.items():
        assert Referencias._respaldo_de("calidad", energia) == valor
    assert Referencias._respaldo_de("calidad", "20mv") is None
    assert Referencias._respaldo_de("tol_dosis", "6mv") is None
