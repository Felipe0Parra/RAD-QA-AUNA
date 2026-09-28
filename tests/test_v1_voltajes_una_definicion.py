"""V.1 (PLAN_VOLTAJES_EDITABLES_BRAQUI_28-09.md, tercera ronda -- TRS-398,
decisión del físico del 28-09): una sola definición de los tres voltajes de
"LECTURAS DEL MÁXIMO", compartida por todo lo que calcula, guarda y lee.

CAUSA. `ActividadFuente.py::factores_correccion` tenía el cociente 300/150
escrito a mano en la fórmula de Ks (`(4/3) - .../(3*...)`); con cualquier
otro voltaje el resultado salía mal sin avisar. Y "¿cuál voltaje es el
alto?" tenía dos respuestas distintas en el código (§1.2 del plan): una
regla en `braq_mensual.py` (max/min de las lecturas) y otra en
`load.py::guardarEdicion` (`max(key=abs)`).

Esta tarea deja: (1) un módulo puro, `services/lecturas_del_maximo.py`, que
decide el papel de cada voltaje y reconstruye un bloque guardado sin
depender del orden de sus filas; (2) `factores_correccion`/
`CalcularActividad` generalizados a cualquier par (v_alto, v_bajo), con la
fórmula de TRS-398 (decisión del físico del 28-09, §R.2 punto 2 del plan --
absorbe la tarea K.1: `Ks = [(V1/V2)^2 - 1] / [(V1/V2)^2 - M1/M2]`,
`Kpol = (|M+| + |M-|) / (2|M+|)`).

Lo que NO cambia: el escritor (`guardar_resultado_CambioFuente`), el
esquema, y ningún llamador real -- eso lo tocan V.3/V.5. Aquí solo se prueba
el módulo nuevo y la fórmula, con los valores por defecto (300.0/150.0)
para no alterar ningún resultado existente hasta que V.5 permita escribir
otros voltajes.
"""
import itertools
import math
import os
import shutil
import sqlite3
import sys

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(__file__))

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import guardar_resultado_CambioFuente
from analisisImagenes.ActividadFuente import factores_correccion, CalcularActividad
from services.lecturas_del_maximo import (
    VoltajesInvalidos,
    voltaje_de_texto,
    validar_roles,
    roles_de_voltajes,
    lecturas_por_voltaje,
    texto_espejo,
    VOLTAJES_POR_DEFECTO,
)
from _bd_referencia import (
    BD_QA, BD_A_AJUSTAR, BD_REBUILD_11_09, BD_REBUILD_14_09, BD_REBUILD_21_09,
)

TODAS_LAS_BD = (BD_QA, BD_A_AJUSTAR, BD_REBUILD_11_09, BD_REBUILD_14_09, BD_REBUILD_21_09)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _filtro_activo(con):
    cols = [c[1] for c in con.execute("PRAGMA table_info(LecturasMaximos)")]
    return " AND (activo IS NULL OR activo = 1)" if "activo" in cols else ""


def _bloques_reales():
    """(archivo, ref, filas) de cada bloque VIGENTE de LecturasMaximos en
    las 5 BD de referencia, leídas SIEMPRE por sqlite3 en modo solo lectura
    (regla de sesión: nunca conectar directo a una BD de referencia para
    escribir; `mode=ro` no puede escribir nada, ni siquiera el WAL)."""
    bloques = []
    for bd in TODAS_LAS_BD:
        if not bd.exists():
            continue
        con = sqlite3.connect(f"file:{bd}?mode=ro", uri=True)
        filtro = _filtro_activo(con)
        refs = [r[0] for r in con.execute(
            f"SELECT DISTINCT ref FROM LecturasMaximos WHERE 1=1{filtro}")]
        for ref in refs:
            filas = con.execute(
                f"SELECT voltaje, V_300, V_150, Vn_300, promediosV "
                f"FROM LecturasMaximos WHERE ref = ?{filtro}", (ref,)).fetchall()
            bloques.append((bd.name, ref, filas))
        con.close()
    return bloques


def _ulp3(promedio):
    """Una unidad en la tercera cifra significativa de `promedio` (el
    formato con el que el escritor guarda, `.2e`) -- la tolerancia de
    redondeo con la que el promedio guardado puede diferir de la media
    exacta de sus tres medidas."""
    p = abs(promedio)
    if p == 0:
        return 1e-300
    exp = math.floor(math.log10(p))
    return 10 ** (exp - 2)


BLOQUES_REALES = _bloques_reales()


# ---------------------------------------------------------------------------
# (a) Ks con otros voltajes -- TRS-398, contra la cuenta hecha a mano.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("v_alto, v_bajo, ks_esperado", [
    (300.0, 150.0, 1.0068493150684932),
    (250.0, 100.0, 1.0039024390243902),
    (300.0, 100.0, 1.0025575447570332),
    (400.0, 200.0, 1.0068493150684932),  # mismo cociente que 300/150 -> mismo Ks
    (300.0, 50.0, 1.000583430571762),
])
def test_ks_trs398_con_otros_voltajes(v_alto, v_bajo, ks_esperado):
    """Lecturas alto=5.00e-08, bajo=4.90e-08 (Vn_300 no interviene en Ks).
    Rojo real en HEAD: `factores_correccion` no acepta `v_alto`/`v_bajo` ->
    TypeError."""
    Ks, _Kpol, _Ktp = factores_correccion(
        5.00e-08, 5.00e-08, 4.90e-08, 21.0, 760.0, 22.0, 760.0,
        v_alto=v_alto, v_bajo=v_bajo)
    assert Ks == pytest.approx(ks_esperado, rel=0, abs=1e-12)


def test_kpol_trs398_con_polaridad_opuesta():
    """Kpol = (|M+| + |M-|) / (2|M+|); con M+ == M- da 1.0 exacto, y con
    magnitudes distintas refleja la asimetría real (no su recíproco)."""
    _Ks, Kpol, _Ktp = factores_correccion(
        5.00e-08, 5.00e-08, 4.90e-08, 21.0, 760.0, 22.0, 760.0)
    assert Kpol == 1.0
    _Ks, Kpol2, _Ktp = factores_correccion(
        5.00e-08, 4.80e-08, 4.90e-08, 21.0, 760.0, 22.0, 760.0)
    assert Kpol2 == pytest.approx((5.00e-08 + 4.80e-08) / (2 * 5.00e-08))


def test_division_por_cero_sigue_igual():
    with pytest.raises(ZeroDivisionError):
        factores_correccion(1.0, 1.0, 0.0, 21.0, 760.0, 22.0, 760.0)


# ---------------------------------------------------------------------------
# (a-2) Aceptación con los controles reales del físico, formato IDC-F-RT-143
# V.03 del 27-09-2026 (300/50/-300 V) -- lo que el plan prometió al físico.
# ---------------------------------------------------------------------------

def test_aceptacion_control_principal_27_09_2026():
    ma = (7.133e-08 + 7.134e-08 + 7.135e-08) / 3
    mb = (7.043e-08 + 7.045e-08 + 7.048e-08) / 3
    mn = 7.14e-08
    Ks, Kpol, Ktp = factores_correccion(
        ma, mn, mb, 21.8, 638.9, 22.0, 760.0, v_alto=300.0, v_bajo=50.0)
    assert Ks == pytest.approx(1.0003597054201927, abs=1e-9)
    assert Kpol == pytest.approx(1.000420521446594, abs=1e-9)
    A = ma * Ks * Ktp * (464700.0 * 1e-5) * (1.0 * 1e8) * Kpol * ((1 / 0.11) * (1 / 37))
    assert round(A, 3) == 9.690
    discrepancia = abs(A - 9.458) / 9.458 * 100
    assert discrepancia == pytest.approx(2.46, abs=0.01)


def test_aceptacion_control_redundante_27_09_2026():
    ma = 7.118e-08
    mb = 7.028e-08
    mn = (7.127e-08 + 7.128e-08 + 7.13e-08) / 3
    Ks, Kpol, Ktp = factores_correccion(
        ma, mn, mb, 21.8, 639.8, 22.0, 760.0, v_alto=300.0, v_bajo=50.0)
    A = ma * Ks * Ktp * (464700.0 * 1e-5) * (1.0 * 1e8) * Kpol * ((1 / 0.11) * (1 / 37))
    assert round(A, 3) == 9.658
    discrepancia = abs(A - 9.458) / 9.458 * 100
    assert discrepancia == pytest.approx(2.11, abs=0.01)


# ---------------------------------------------------------------------------
# (b) roles_de_voltajes / validar_roles.
# ---------------------------------------------------------------------------

def test_roles_de_voltajes_igual_en_las_6_permutaciones():
    for permutacion in itertools.permutations((300.0, 150.0, -300.0)):
        assert roles_de_voltajes(permutacion) == (300.0, 150.0, -300.0)


@pytest.mark.parametrize("voltajes, fragmento_mensaje", [
    ((300.0, 150.0, 120.0), "positivo"),          # tres positivos
    ((300.0, -150.0, -300.0), "positivo"),        # dos negativos
    ((300.0, 300.0, -300.0), "distintos"),        # repetidos
    ((300.0, 0.0, -300.0), "cero"),               # cero
    ((300.0, 150.0, -250.0), "polaridad opuesta"),  # 300/150/-250
])
def test_roles_de_voltajes_rechaza_tries_invalidos(voltajes, fragmento_mensaje):
    with pytest.raises(VoltajesInvalidos, match=fragmento_mensaje):
        roles_de_voltajes(voltajes)


def test_validar_roles_rechaza_bajo_mayor_o_igual_que_alto():
    """Caso que `roles_de_voltajes` nunca puede producir (asigna alto=máximo
    positivo por construcción), pero que sí puede llegar por otra vía (la
    UI de V.5 pasa alto/bajo por POSICIÓN de fila, no por magnitud)."""
    with pytest.raises(VoltajesInvalidos, match="menor que el alto"):
        validar_roles(alto=150.0, bajo=300.0, negativo=-150.0)


def test_voltaje_de_texto_acepta_signo_tipografico_y_rechaza_lo_invalido():
    assert voltaje_de_texto("300") == 300.0
    assert voltaje_de_texto(" -300 ") == -300.0
    assert voltaje_de_texto("−300") == -300.0
    with pytest.raises(VoltajesInvalidos):
        voltaje_de_texto("")
    with pytest.raises(VoltajesInvalidos):
        voltaje_de_texto("abc")
    with pytest.raises(VoltajesInvalidos):
        voltaje_de_texto("0")


# ---------------------------------------------------------------------------
# (c) lecturas_por_voltaje sobre los bloques REALES de las 5 BD de referencia.
# ---------------------------------------------------------------------------

def test_hay_bloques_reales_que_medir():
    """Compuerta de la propia medición: si esto da 0, las BD de referencia
    no están donde el resto de la suite las espera y el resto de este
    archivo estaría midiendo el vacío."""
    assert len(BLOQUES_REALES) >= 70, (
        f"se esperaban ~72 bloques reales, se encontraron {len(BLOQUES_REALES)}")


def test_lecturas_por_voltaje_invariante_a_las_6_permutaciones_reales():
    for _archivo, _ref, filas in BLOQUES_REALES:
        base = lecturas_por_voltaje(filas)
        for permutacion in itertools.permutations(filas):
            assert lecturas_por_voltaje(list(permutacion)) == base


def test_promedio_guardado_es_la_media_de_sus_propias_medidas():
    """210/210 (ahora 72*3) filas: el promedio que guardó el escritor
    coincide, dentro del redondeo de `.2e`, con la media de las TRES
    medidas de su propio voltaje -- nunca con las de otro voltaje (eso es
    justo lo que el ref 24 delata: leído por fila, no cuadra)."""
    total_filas = 0
    for _archivo, _ref, filas in BLOQUES_REALES:
        for voltaje, medidas, promedio in lecturas_por_voltaje(filas):
            total_filas += 1
            media = sum(float(m) for m in medidas) / 3
            assert abs(media - float(promedio)) <= _ulp3(float(promedio)) * 1.0000001, (
                f"voltaje {voltaje}: medidas {medidas} -> media {media}, "
                f"guardado {promedio}")
    assert total_filas == len(BLOQUES_REALES) * 3


def test_ref_24_da_la_tabla_correcta():
    """El caso citado en el plan: Calibración Redundante del 29-12-2025,
    ref 24, presente en las 5 BD de referencia. Leído por FILA (como
    hacían los cuatro lectores antes de V.3) el promedio de 300 V y de
    150 V no cuadra con sus propias celdas; por PAPEL, sí."""
    con = sqlite3.connect(f"file:{BD_REBUILD_21_09}?mode=ro", uri=True)
    filtro = _filtro_activo(con)
    filas = con.execute(
        f"SELECT voltaje, V_300, V_150, Vn_300, promediosV "
        f"FROM LecturasMaximos WHERE ref = ?{filtro}", (24,)).fetchall()
    con.close()
    assert lecturas_por_voltaje(filas) == [
        ("300.0", ["6.87e-08", "6.87e-08", "6.87e-08"], "6.87e-08"),
        ("150.0", ["6.83e-08", "6.86e-08", "6.86e-08"], "6.85e-08"),
        ("-300.0", ["6.87e-08", "6.87e-08", "6.87e-08"], "6.87e-08"),
    ]


def test_lecturas_por_voltaje_rechaza_un_bloque_que_no_tiene_3_filas():
    with pytest.raises(VoltajesInvalidos):
        lecturas_por_voltaje([("300.0", "1e-8", "1e-8", "1e-8", "1e-8")])


# ---------------------------------------------------------------------------
# (d) Ida y vuelta con el escritor REAL: lo que se escribe es lo que se lee.
# ---------------------------------------------------------------------------

ARGS_BASE = dict(
    tipo="Cambio de fuente", serie="A092535", certificado="HDR12899",
    fecha_cer="2025-07-28", intensidad=1.1, conversion=1.0,
    modelo="HDR1000 Plus", serie_cp="1825", calibracion=464700,
    modelo_elec="Unidos-E", serie_ele="2343", electrometro="T10010",
    t0=22.0, p0=101.325, h0=50.0, t=22.0, p=101.325, h=50.0,
    posiciones=["A", "B"], medida1=[1.0, 2.0], medida2=[1.1, 2.1],
    promedios=[1.05, 2.05],
    Ks=1.0, Kp=1.0, Ktp=1.0,
    actividad_monitor=1.0, actividad_calculada=1.0,
    actividad_decaimiento=1.0, desplazamiento_ini="No Aplica",
    observaciones="sin observaciones",
)


def _guardar_lecturas(fecha, voltaje, V_300, V_150, Vn_300, promediosV):
    kwargs = dict(ARGS_BASE)
    kwargs.update(voltaje=voltaje, V_300=V_300, V_150=V_150, Vn_300=Vn_300,
                  promediosV=promediosV)
    return guardar_resultado_CambioFuente("Físico de Prueba", fecha, **kwargs)


@pytest.mark.parametrize("alto, bajo, negativo", [(300.0, 150.0, -300.0), (250.0, 100.0, -250.0)])
def test_ida_y_vuelta_con_el_escritor_real(bd_temporal, alto, bajo, negativo):
    medidas_alto = [1e-8, 2e-8, 3e-8]
    medidas_bajo = [4e-8, 5e-8, 6e-8]
    medidas_neg = [7e-8, 8e-8, 9e-8]
    promedios = [sum(medidas_alto) / 3, sum(medidas_bajo) / 3, sum(medidas_neg) / 3]
    ref = _guardar_lecturas(
        "2026-01-01 00:00:00",
        voltaje=[alto, bajo, negativo],
        V_300=medidas_alto, V_150=medidas_bajo, Vn_300=medidas_neg,
        promediosV=promedios)

    con = sqlite3.connect(bd_temporal)
    filas_guardadas = con.execute(
        "SELECT voltaje, V_300, V_150, Vn_300, promediosV "
        "FROM LecturasMaximos WHERE ref = ?", (ref,)).fetchall()
    con.close()

    for orden in itertools.permutations(filas_guardadas):
        resultado = lecturas_por_voltaje(list(orden))
        voltajes_leidos = [float(v) for v, _m, _p in resultado]
        assert voltajes_leidos == [alto, bajo, negativo]
        medidas_leidas = [[float(m) for m in m_lista] for _v, m_lista, _p in resultado]
        # Comparación con la misma tolerancia .2e con la que se escribió.
        assert medidas_leidas[0] == pytest.approx(medidas_alto, rel=0.005)
        assert medidas_leidas[1] == pytest.approx(medidas_bajo, rel=0.005)
        assert medidas_leidas[2] == pytest.approx(medidas_neg, rel=0.005)


# ---------------------------------------------------------------------------
# (e) texto_espejo.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto, signo, esperado", [
    ("250", -1, "-250"),
    ("-250", +1, "250"),
    ("−250", +1, "250"),
    (" +300 ", +1, "300"),
    ("-", -1, ""),
    ("", +1, ""),
    ("250.5", -1, "-250.5"),
])
def test_texto_espejo(texto, signo, esperado):
    assert texto_espejo(texto, signo) == esperado


# ---------------------------------------------------------------------------
# (f) Lo viejo NO sigue igual, y hay que decirlo con precisión: Ks(TRS-398)
# es el RECÍPROCO de Ks(formato V.03) a n2=4 -- ya lo había medido DP-135
# ("el valor del código es exactamente 1/k_s de TRS-398"). Este bloque
# documenta la magnitud real del cambio con la fórmula congelada como
# referencia histórica, no como compuerta de identidad (sería falsa).
# ---------------------------------------------------------------------------

def _ks_formato_v03(V_300prom, V_150prom):
    """Fórmula congelada del formato IDC-F-RT-143 V.03 (y de la app antes
    de esta tarea): `(4/3) - V_300prom/(3*V_150prom)`, válida solo para
    300/150. Se conserva aquí SOLO como referencia histórica para el
    cuadro antes/después -- la producción ya no la usa (K.1 absorbida)."""
    return (4 / 3) - V_300prom / (3 * V_150prom)


def test_forma_v03_es_el_reciproco_de_trs398_a_300_150():
    """DP-135, confirmado analíticamente: con n2=4 (300/150),
    Ks_TRS398 = 3/(4-r) y Ks_V03 = (4-r)/3 -- son recíprocos, nunca
    iguales salvo en r=1 (las dos lecturas idénticas, Ks=1 en ambas)."""
    rng = np.random.default_rng(20260928)
    for a, b in rng.uniform(1e-9, 1e-6, size=(5000, 2)):
        viejo = _ks_formato_v03(a, b)
        nuevo, _kp, _kt = factores_correccion(a, 1.0, b, 21.0, 760.0, 22.0, 760.0)
        assert nuevo == pytest.approx(1 / viejo, rel=1e-9), (a, b)
    # El punto fijo real: lecturas iguales -> Ks=1 en las dos fórmulas.
    igual_viejo = _ks_formato_v03(5.0e-08, 5.0e-08)
    igual_nuevo, _kp, _kt = factores_correccion(5.0e-08, 1.0, 5.0e-08, 21.0, 760.0, 22.0, 760.0)
    assert igual_viejo == igual_nuevo == 1.0


def test_cuadro_antes_despues_sobre_los_controles_reales_guardados_a_300_150():
    """El cuadro que la tarea le debe al físico antes del commit (riesgo
    ALTO, §5.1): para cada bloque real guardado a 300/150 V, cuánto se
    mueve Ks al pasar de la fórmula del formato a TRS-398. Ninguna
    diferencia debe superar el ~1 % medido al planear (ref 24: 0.999 vs
    1.001); esto es evidencia archivada, no una compuerta de identidad."""
    diferencias = []
    for archivo, ref, filas in BLOQUES_REALES:
        try:
            (va, ma, _pa), (vb, mb, _pb), (_vn, _mn, _pn) = lecturas_por_voltaje(filas)
        except VoltajesInvalidos:
            continue
        if float(va) != 300.0 or float(vb) != 150.0:
            continue
        Ma = sum(float(x) for x in ma) / 3
        Mb = sum(float(x) for x in mb) / 3
        viejo = _ks_formato_v03(Ma, Mb)
        nuevo, _kp, _kt = factores_correccion(Ma, 1.0, Mb, 21.0, 760.0, 22.0, 760.0)
        diferencias.append((archivo, ref, viejo, nuevo, abs(nuevo - viejo) / viejo * 100))
    assert diferencias, "no se encontró ningún bloque real a 300/150 V"
    assert all(d[-1] < 2.0 for d in diferencias), diferencias


def test_calcularactividad_con_y_sin_voltajes_explicitos_da_lo_mismo():
    """Los valores por defecto (300.0/150.0) hacen que omitir v_alto/v_bajo
    sea indistinguible de pasarlos explícitos -- así ningún llamador que
    todavía no fue tocado (V.3/V.4/V.5 lo harán) cambia de comportamiento."""
    args = (5.0e-08, 5.0e-08, 4.9e-08, 21.0, 760.0, 22.0, 760.0,
            464700.0, 1.0, 0.11, 9.0, 11.0,
            "2025-01-01 00:00:00", "2026-01-01 00:00:00")
    con_default = CalcularActividad(*args)
    con_explicito = CalcularActividad(*args, v_alto=300.0, v_bajo=150.0)
    assert con_default == con_explicito


# ---------------------------------------------------------------------------
# Mutaciones que el test debe matar (documentadas; se aplican y verifican
# manualmente en el protocolo de la tarea, no como parte de la suite).
# ---------------------------------------------------------------------------

def test_voltajes_por_defecto_es_el_texto_del_formato_vigente():
    """Decisión del físico (§R.2 punto 1): 300/50/-300, no 300/150/-300."""
    assert VOLTAJES_POR_DEFECTO == ("300", "50", "-300")
