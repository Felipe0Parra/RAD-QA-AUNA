"""RC.1 (PLAN_RECALCULO_CALIBRACION_BRAQUI_30-09.md): una sola cuenta para
lo que se archiva en ResultadosActividad. `promedio_de_medidas` y
`resultados_para_archivar` (`analisisImagenes/ActividadFuente.py`, solo
líneas AÑADIDAS al final) son ahora la única definición de "la media de
las tres medidas de un voltaje" y "las cinco cifras que se archivan
(Ks, Kp, Ktp, actividad_calculada, actividad_decaimiento)". Antes de esta
tarea esa cuenta estaba escrita tres veces (`guardar_DB`, el recálculo de
`guardarEdicion` y la vista previa `CalcularActividad`), cada una distinta
-- por eso el recálculo al corregir una calibración no podía dar lo mismo
que volver a guardar (§1.5 del plan).

`guardar_DB` sigue produciendo EXACTAMENTE los mismos bits que en HEAD
7553a49: (a) prueba que `resultados_para_archivar` es `==` a una copia de
la aritmética de HEAD, ESCRITA A MANO en este archivo (no importada de
`resultados_para_archivar`, para que un cambio futuro en el orden de los
`round()` la delate); (b) argumentos solo-nombre y sin valor por defecto
(lección de V.2: un 300/150 por defecto calculó mal sin avisar); (c)
`promedio_de_medidas` es la misma división de siempre; (d) el camino REAL
del usuario -- construir el formulario sobre una copia de `Rebuild_21-09`,
navegar a la fecha, pulsar Guardar con el escritor espiado -- archiva
exactamente lo que el plan aceptó en su §1.5 (columna NUEVO) para los 7
controles que están solos en su día.

Rojo real en HEAD: `resultados_para_archivar`/`promedio_de_medidas` no
existen en `analisisImagenes/ActividadFuente.py` -> `ImportError` al
recolectar este archivo entero.

Lo que este archivo NO prueba (protocolo manual, fuera de pytest):
- Forma del `diff` (RC.1, ítem f): se verificó con `git show HEAD:...`
  contra el árbol de trabajo antes del commit -- ver VERIFICACIÓN REAL del
  plan. Un test permanente que comparara "el archivo actual" contra
  "HEAD" dejaría de tener sentido en cuanto este commit exista (HEAD ya
  sería el archivo actual), así que no se deja en la suite.
- Que los 6 archivos de §2.2-12 sigan verdes sin tocarlos (RC.1, ítem e):
  se corrieron aparte -- ver VERIFICACIÓN REAL.
- Las mutaciones (aplicadas, vistas en rojo, restauradas con `cmp`): son
  ediciones manuales del protocolo, no código de este archivo.
"""
import os
import random
import sqlite3
import shutil
import sys

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QMessageBox

sys.path.insert(0, os.path.dirname(__file__))

import data.ManejoDatos.conection as conection_mod
from analisisImagenes.ActividadFuente import (
    factores_correccion, actividad_fuente, calcular_decaimiento,
    promedio_de_medidas, resultados_para_archivar,
)
import ui.paginasControles.PruebasMensuales.braq_mensual as braq_mensual_mod
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq
from services.lecturas_del_maximo import lecturas_por_voltaje
from _bd_referencia import (
    BD_QA, BD_A_AJUSTAR, BD_REBUILD_11_09, BD_REBUILD_14_09, BD_REBUILD_21_09,
)

TODAS_LAS_BD = (BD_QA, BD_A_AJUSTAR, BD_REBUILD_11_09, BD_REBUILD_14_09, BD_REBUILD_21_09)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


# ---------------------------------------------------------------------------
# (a) resultados_para_archivar == copia congelada de la aritmética de HEAD.
# ---------------------------------------------------------------------------

def _frozen_head_arithmetic(prom_alto, prom_bajo, prom_negativo, t, p, t0, p0,
                             calibracion_camara, calibracion_electrometro, conversion,
                             fecha_cer, fecha_cal, intensidad, v_alto, v_bajo):
    """Copia INDEPENDIENTE, escrita a mano, de la composición exacta de
    `guardar_DB` en HEAD 7553a49 -- Ks/Kp/Ktp redondeados a 3 ANTES de
    calcular la actividad; actividad y decaimiento redondeados a 3
    después. No llama a `resultados_para_archivar`: si esa función
    cambiara el orden algún día, esta copia no cambiaría con ella."""
    Ks, Kp, Ktp = factores_correccion(prom_alto, prom_negativo, prom_bajo,
                                       t, p, t0, p0, v_alto=v_alto, v_bajo=v_bajo)
    Ks, Kp, Ktp = round(Ks, 3), round(Kp, 3), round(Ktp, 3)
    actividad_calculada = round(actividad_fuente(
        Ks, Kp, Ktp, calibracion_camara, calibracion_electrometro, conversion, prom_alto), 3)
    actividad_decaimiento = round(calcular_decaimiento(fecha_cer, fecha_cal, intensidad), 3)
    return {"Ks": Ks, "Kp": Kp, "Ktp": Ktp,
            "actividad_calculada": actividad_calculada,
            "actividad_decaimiento": actividad_decaimiento}


# t, p, t0, p0 reales (CondicionesMedicion/SistemaMedicion de Rebuild_21-09).
CONDICIONES_REALES = [
    (20.1, 639.0, 22.0, 760.0), (20.3, 639.0, 22.0, 758.0),
    (22.6, 639.0, 22.0, 758.0), (21.0, 637.0, 22.0, 760.0),
    (19.4, 637.0, 22.0, 760.0), (21.1, 638.0, 22.0, 760.0),
    (19.4, 636.0, 22.0, 760.0), (21.0, 639.0, 22.0, 760.0),
    (20.0, 638.0, 22.0, 760.0), (21.0, 640.0, 22.0, 760.0),
]
PARES_VOLTAJE = [(300.0, 150.0), (300.0, 50.0), (250.0, 100.0), (400.0, 200.0)]


def _casos_congelados(n=10000, semilla=20260930):
    rng = random.Random(semilla)
    casos = []
    for i in range(n):
        prom_alto = rng.uniform(1e-8, 1e-7)
        prom_bajo = rng.uniform(1e-8, 1e-7)
        prom_neg = rng.uniform(1e-8, 1e-7)
        v_alto, v_bajo = PARES_VOLTAJE[i % len(PARES_VOLTAJE)]
        t, p, t0, p0 = CONDICIONES_REALES[i % len(CONDICIONES_REALES)]
        conversion = 0.11
        fecha_cer = f"2026-{1 + (i % 12):02d}-{1 + (i % 28):02d} 10:00:00"
        fecha_cal = f"2026-{1 + ((i + 1) % 12):02d}-{1 + ((i + 5) % 28):02d} 09:00:00"
        intensidad = rng.uniform(5.0, 15.0)
        cal_camara = rng.choice([464700.0, 466700.0, 467900.0])
        cal_electrometro = 1.0
        if i % 7 == 0:
            # también con numpy.float64, como llegan de Kpol/np.abs en producción.
            prom_alto, prom_bajo, prom_neg = (
                np.float64(prom_alto), np.float64(prom_bajo), np.float64(prom_neg))
        casos.append((prom_alto, prom_bajo, prom_neg, t, p, t0, p0,
                      cal_camara, cal_electrometro, conversion,
                      fecha_cer, fecha_cal, intensidad, v_alto, v_bajo))
    return casos


CASOS_CONGELADOS = _casos_congelados()


def test_resultados_para_archivar_es_igual_a_la_copia_congelada():
    assert len(CASOS_CONGELADOS) == 10000
    for caso in CASOS_CONGELADOS:
        (prom_alto, prom_bajo, prom_neg, t, p, t0, p0, cal_camara, cal_electrometro,
         conversion, fecha_cer, fecha_cal, intensidad, v_alto, v_bajo) = caso
        esperado = _frozen_head_arithmetic(
            prom_alto, prom_bajo, prom_neg, t, p, t0, p0, cal_camara,
            cal_electrometro, conversion, fecha_cer, fecha_cal, intensidad,
            v_alto, v_bajo)
        real = resultados_para_archivar(
            prom_alto, prom_bajo, prom_neg, t, p, t0, p0, cal_camara,
            cal_electrometro, conversion, fecha_cer, fecha_cal, intensidad,
            v_alto=v_alto, v_bajo=v_bajo)
        assert real == esperado, caso


def test_sin_v_alto_o_sin_v_bajo_es_typeerror():
    base = dict(
        prom_alto=5e-8, prom_bajo=4.9e-8, prom_negativo=5e-8,
        t=21.0, p=760.0, t0=22.0, p0=760.0,
        calibracion_camara=464700.0, calibracion_electrometro=1.0, conversion=0.11,
        fecha_cer="2026-01-01 00:00:00", fecha_cal="2026-01-02 00:00:00", intensidad=10.0,
    )
    with pytest.raises(TypeError):
        resultados_para_archivar(**base, v_alto=300.0)
    with pytest.raises(TypeError):
        resultados_para_archivar(**base, v_bajo=150.0)
    with pytest.raises(TypeError):
        resultados_para_archivar(**base)


# ---------------------------------------------------------------------------
# (c) promedio_de_medidas: 10 000 tríos + las medidas guardadas de los
# bloques reales de las 5 BD (por papel, con lecturas_por_voltaje -- las
# tres medidas de UN voltaje no viven en una sola fila, ver services/
# lecturas_del_maximo.py).
# ---------------------------------------------------------------------------

def test_promedio_de_medidas_en_10000_trios():
    rng = random.Random(20260930)
    for _ in range(10000):
        a, b, c = (rng.uniform(1e-8, 1e-7) for _ in range(3))
        assert promedio_de_medidas(a, b, c) == (a + b + c) / 3


def _filtro_activo(con, tabla):
    cols = [c[1] for c in con.execute(f"PRAGMA table_info({tabla})")]
    return " AND (activo IS NULL OR activo = 1)" if "activo" in cols else ""


def _bloques_reales():
    """(archivo, ref, filas) de cada bloque VIGENTE de LecturasMaximos en
    las 5 BD de referencia -- solo lectura `mode=ro` (no puede escribir
    nada, ni el WAL; no hace falta copiar a un temporal)."""
    bloques = []
    for bd in TODAS_LAS_BD:
        if not bd.exists():
            continue
        con = sqlite3.connect(f"file:{bd}?mode=ro", uri=True)
        filtro = _filtro_activo(con, "LecturasMaximos")
        refs = [r[0] for r in con.execute(f"SELECT DISTINCT ref FROM LecturasMaximos WHERE 1=1{filtro}")]
        for ref in refs:
            filas = con.execute(
                f"SELECT voltaje, V_300, V_150, Vn_300, promediosV "
                f"FROM LecturasMaximos WHERE ref = ?{filtro}", (ref,)).fetchall()
            bloques.append((bd.name, ref, filas))
        con.close()
    return bloques


BLOQUES_REALES = _bloques_reales()


def test_hay_bloques_reales_que_medir():
    assert len(BLOQUES_REALES) >= 70, (
        f"se esperaban ~72 bloques reales, se encontraron {len(BLOQUES_REALES)}")


def test_promedio_de_medidas_en_las_medidas_guardadas_de_los_72_bloques():
    total_voltajes = 0
    for archivo, ref, filas in BLOQUES_REALES:
        try:
            reconstruido = lecturas_por_voltaje(filas)
        except Exception:
            continue  # bloque inválido: no es lo que esta prueba mide
        for _voltaje, medidas, _promedio in reconstruido:
            m1, m2, m3 = (float(m) for m in medidas)
            total_voltajes += 1
            assert promedio_de_medidas(m1, m2, m3) == (m1 + m2 + m3) / 3, (archivo, ref, medidas)
    assert total_voltajes >= 70 * 3, total_voltajes


# ---------------------------------------------------------------------------
# (d) Por el camino del usuario: los 7 controles solos en su día archivan
# exactamente la columna NUEVO de §1.5 del plan.
# ---------------------------------------------------------------------------

class _UsuarioFalso:
    def __init__(self, nombre="Físico de Prueba"):
        self._nombre = nombre
        self.nombre = nombre
        self.id = 1

    def __getattr__(self, item):
        return None


@pytest.fixture
def bd_copia_real(monkeypatch, tmp_path):
    if not BD_REBUILD_21_09.exists():
        pytest.skip(f"falta la BD de referencia {BD_REBUILD_21_09.name}")
    import shutil as _shutil
    copia = tmp_path / "copia.db"
    _shutil.copy2(BD_REBUILD_21_09, copia)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: str(copia))
    conection_mod.Conexion._instance = None
    yield copia
    if conection_mod.Conexion._instance is not None:
        conection_mod.Conexion._instance.con.close()
    conection_mod.Conexion._instance = None


# (ref, Ks, Kp, Ktp, actividad_calculada, actividad_decaimiento) -- columna
# NUEVO de §1.5 de PLAN_RECALCULO_CALIBRACION_BRAQUI_30-09.md, los 7
# controles "Control Mensual" solos en su día (§1.4).
NUEVO_7_CONTROLES = [
    (16, 1.0, 1.0, 1.189, 5.454, 5.349),
    (23, 1.001, 1.0, 1.183, 6.902, 6.79),
    (25, 1.0, 1.0, 1.184, 5.133, 22.983),
    (29, 1.0, 1.0, 1.183, 3.998, 3.939),
    (32, 1.0, 1.0, 1.191, 5.97, 5.848),
    (35, 1.001, 1.0, 1.191, 8.317, 3.271),
    (36, 1.001, 1.002, 1.186, 6.139, 6.005),
]


def test_recarga_del_formulario_archiva_lo_que_acepto_el_fisico_en_7_controles(app, bd_copia_real, monkeypatch):
    con = sqlite3.connect(f"file:{bd_copia_real}?mode=ro", uri=True)
    fechas = dict(con.execute(
        "SELECT id, fecha FROM TipoCalibracion WHERE id IN (16,23,25,29,32,35,36)"))
    con.close()
    assert len(fechas) == 7

    capturas = []
    monkeypatch.setattr(
        braq_mensual_mod, "guardar_resultado_CambioFuente",
        lambda *a, **k: capturas.append((a, k)) or 999)

    for ref, Ks, Kp, Ktp, A, dec in NUEVO_7_CONTROLES:
        capturas.clear()
        obj = PruebaMensualBraq(_UsuarioFalso())
        obj.pri_cal.setChecked(True)
        qd = QDate.fromString(str(fechas[ref])[:10], "yyyy-MM-dd")
        obj.date_box.setDate(qd.addDays(1))  # fuerza dateChanged real
        obj.date_box.setDate(qd)
        obj.guardar_DB()
        assert capturas, f"ref {ref} no guardó nada"
        a, _k = capturas[0]
        capturado = (round(a[29], 3), round(a[30], 3), round(a[31], 3), round(a[33], 3), round(a[34], 3))
        assert capturado == (Ks, Kp, Ktp, A, dec), f"ref {ref}: {capturado} != esperado"
