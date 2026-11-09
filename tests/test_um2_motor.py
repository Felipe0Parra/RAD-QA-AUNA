"""UM.2 (PLAN_CALCULADORA_UM_05-11.md): el motor de la ecuación 3 de la TG-71 (`services/um_motor.py`) y el armado de los datos del haz (`services/um_armar.py`).

Los números esperados salen de la TG-71, de una cuenta a mano sobre el archivo o de un haz sintético generado sin el motor; nunca del propio motor. La única
excepción es la guarda del plan (§4-bis): las cifras de `logs/h_datos_reales.txt` del anexo, revisadas dos veces el 05-11, se copian aquí como texto y un cambio
que no se sepa explicar es un defecto nuevo. Cada clase de defecto de las dos revisiones independientes (05-11) tiene su prueba.

LOS DATOS: los 22 archivos de `tests/datos_um/600C/` (UM.1), leídos como bytes y decodificados con `lector.decodificar` (traen BOM y CRLF; el lector rechaza un
CRLF que no pase por ahí). 12 los lee el cálculo y 10 se ignoran. Lo que estas pruebas fabrican a partir de ellos sigue bien formado: sin blancos al final de una
línea con números y sin comentarios entre los datos (UM.1b).
EL MUNDO SIMULADO: `tests/_um_mundo_simulado.py`, el modelo físico del cuaderno de estudio reescrito sin importar el motor (H6).
Sin Qt, sin base y sin saltos. Las fixtures son de módulo y no hay caches de módulo (Trampa 10); el azar va con semilla fija.
"""
import dataclasses
import itertools
import json
import math
import os
import random
import re

import numpy as np
import pytest

import _um_mundo_simulado as ms
import services.um_motor as motor   # rojo por ModuleNotFoundError: No module named 'services.um_motor' (antes de UM.2)
import services.um_armar as um_armar
import services.um_lector_eclipse as lector

DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos_um", "600C")
PDD_ABIERTO = "CLINAC 600C_Open Field - 00_Measured Depth Doses.txt"
PERFILES = "CLINAC 600C_Open Field - 00_Processed Measured Profiles.txt"
E = motor.Entrada
WF15 = 0.6623 / 0.860   # la dosis de referencia de name.data entre D'0 a 5 cm


def texto(nombre):
    with open(os.path.join(DATOS, nombre), "rb") as f:
        return lector.decodificar(f.read())


@pytest.fixture(scope="module")
def archivos():
    return [texto(n) for n in sorted(os.listdir(DATOS))]


@pytest.fixture(scope="module")
def datos(archivos):
    return um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0)


def factor(resultado, simbolo):
    return {f.simbolo: f.valor for f in resultado.factores}[simbolo]


def avisos_de(d, *args, **kw):
    return " | ".join(motor.calcular(d, E(*args, **kw)).avisos)


def es_de(archivos, *marcas):
    return next(a for a in archivos if all(m in a for m in marcas))


def cambiar(archivos, viejo, nuevo):
    """Los mismos archivos, con uno de ellos sustituido por otro texto."""
    assert viejo != nuevo
    return [nuevo if a is viejo else a for a in archivos]


# ---------- Cuentas a mano sobre el archivo, sin usar el motor ----------
def log_entre(a, va, b, vb, c):
    return va + (vb - va) * (math.log(c) - math.log(a)) / (math.log(b) - math.log(a))


def _vecinos(eje, v):
    j = max(1, min(int(np.searchsorted(eje, v)), len(eje) - 1))
    return j - 1, j


def tabla_a_mano(t, x, y):
    i0, i1 = _vecinos(t.y, y)
    j0, j1 = _vecinos(t.x, x)
    fila = lambda i: log_entre(t.x[j0], t.m[i, j0], t.x[j1], t.m[i, j1], x)
    return log_entre(t.y[i0], fila(i0), t.y[i1], fila(i1), y)


def tabla_real(nombre="Open Field - 00"):
    return lector.leer_tabla_of(texto(f"CLINAC 600C_{nombre}_Output Factors.txt"))


def celda(t, y, x):
    return float(t.m[list(t.y).index(y), list(t.x).index(x)])


def pdd_a_mano(d, r):
    curvas = {c.campo_cm[0]: c for c in lector.leer_curvas(texto(PDD_ABIERTO))}
    lados = sorted(curvas)
    j0, j1 = _vecinos(lados, r)
    return log_entre(lados[j0], np.interp(d, curvas[lados[j0]].z_cm, curvas[lados[j0]].valor), lados[j1], np.interp(d, curvas[lados[j1]].z_cm, curvas[lados[j1]].valor), r)


def perfil_a_mano(lado, prof):
    c = next(c for c in lector.leer_curvas(texto("CLINAC 600C_Open Field - 00_Processed Measured Profiles.txt")) if c.campo_cm == (lado, lado) and abs(np.median(c.z_cm) - prof) < 0.2)
    orden = np.argsort(c.x_cm)
    x, v = c.x_cm[orden], c.valor[orden]
    cerca = (x > 0) & (x <= min(3.0, lado / 4))
    a = np.polyfit(x[cerca] ** 2, v[cerca], 1)[1]
    return np.concatenate(([0.0], x[x > 0])), np.concatenate(([1.0], v[x > 0] / a))


def oar_a_mano(lado, prof, x_iso):
    x, v = perfil_a_mano(lado, prof)
    return float(np.interp(x_iso * (100 + prof) / 100, x, v))


def beta_a_mano(angulo, lado):
    c = next(q for q in lector.leer_curvas(texto(f"CLINAC 600C_Standard Wedge - {angulo}_Measured Wedge Depth Doses.txt")) if q.campo_cm == (lado, lado))
    z = np.arange(5.0, 30.0 + 1e-9, 0.5)
    cociente = [(np.interp(q, c.z_cm, c.valor) / np.interp(5, c.z_cm, c.valor)) / (pdd_a_mano(q, lado) / pdd_a_mano(5, lado)) for q in z]
    return float(np.dot(z - 5, np.log(cociente)) / np.dot(z - 5, z - 5))


# ---------- Armado ----------
def test_d0_en_normalizacion_es_el_pdd_a_5_cm(datos):
    assert datos.d0_norm == pytest.approx(0.860)
    assert (datos.ssd0_cm, datos.d0_cm, datos.ssd_pdd_cm) == (100.0, 5.0, 100.0)


def test_tabla_a_otra_ssd_pide_d0_en_sus_condiciones(archivos):
    otra = [a.replace("%SourcePhantomDistance 1000", "%SourcePhantomDistance 950") for a in archivos]
    with pytest.raises(motor.FaltaDato, match="condiciones de la tabla"):
        um_armar.datos_haz(otra, "Clinac 600", "6 MV", d0_dmax=1.0)
    d = um_armar.datos_haz(otra, "Clinac 600", "6 MV", d0_tabla=0.945)
    assert (d.d0_norm, d.ssd0_cm) == (0.945, 95.0)


@pytest.mark.parametrize("cual, valor", [("d0_dmax", 100.0), ("d0_dmax", 0.0), ("d0_dmax", -1.0), ("d0_dmax", 0.49), ("d0_dmax", 1.51), ("d0_tabla", 86.0), ("d0_tabla", 0.086), ("d0_tabla", 0.0), ("d0_tabla", -0.86), ("d0_tabla", float("nan"))])
def test_d0_imposible_se_rechaza(archivos, cual, valor):
    with pytest.raises(motor.FaltaDato, match="posible"):
        um_armar.datos_haz(archivos, "Clinac 600", "6 MV", **{cual: valor})


@pytest.mark.parametrize("valor", [0.5, 1.5])
def test_d0_en_el_limite_se_acepta(archivos, valor):
    abiertos = [a for a in archivos if "add on: Open Field" in a]
    assert um_armar.datos_haz(abiertos, "Clinac 600", "6 MV", d0_dmax=valor).d0_norm == pytest.approx(valor * 0.86)


def test_se_da_d0_de_una_sola_manera(archivos):
    with pytest.raises(ValueError):
        um_armar.datos_haz(archivos, "Clinac 600", "6 MV")
    with pytest.raises(ValueError):
        um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, d0_tabla=0.86)


def test_archivos_de_dos_maquinas_o_energias_se_rechazan(archivos):
    otra = [archivos[0].replace("# machine: 600C, 6X", "# machine: iX, 15X")] + archivos[1:]
    with pytest.raises(lector.ArchivoNoReconocido, match="distintas"):
        um_armar.datos_haz(otra, "Clinac 600", "6 MV", d0_dmax=1.0)


def test_pdd_con_otra_normalizacion_o_ssd_se_rechaza(archivos):
    pdd = es_de(archivos, "data: OPD\n")
    en_fraccion = re.sub(r"^(<\S+ \S+ \S+ )\+([\d.]+)>", lambda m: f"{m.group(1)}+{float(m.group(2)) / 100:.5f}>", pdd, flags=re.M)
    with pytest.raises(lector.ArchivoNoReconocido, match="normalizado"):
        um_armar.datos_haz(cambiar(archivos, pdd, en_fraccion), "Clinac 600", "6 MV", d0_dmax=1.0)
    with pytest.raises(lector.ArchivoNoReconocido, match="una sola SSD"):
        um_armar.datos_haz(cambiar(archivos, pdd, pdd.replace("%SSD 1000", "%SSD 900", 1)), "Clinac 600", "6 MV", d0_dmax=1.0)


@pytest.mark.parametrize("viejo, nuevo, mensaje", [
    ("%FLSZ 100*100", "%FLSZ 100*200", "no es cuadrado"), ("%FLSZ 100*100", "%FLSZ 110*110", "10 × 10"), ("%FLSZ 150*150", "%FLSZ 100*100", "repetid"),
    ("<+000.0 +000.0 +150.0 ", "<+000.0 +000.0 +150.5 ", "rejilla"), ("+045.300", "+000.000", "nulo"),
])
def test_pdd_mal_armado_se_rechaza(archivos, viejo, nuevo, mensaje):
    pdd = es_de(archivos, "data: OPD\n")
    assert viejo in pdd
    with pytest.raises(lector.ArchivoNoReconocido, match=mensaje):
        um_armar.datos_haz(cambiar(archivos, pdd, pdd.replace(viejo, nuevo, 1)), "Clinac 600", "6 MV", d0_dmax=1.0)


@pytest.mark.parametrize("viejo, nuevo", [("%DetectorDepth 50", "%DetectorDepth 100"), ("%SourcePhantomDistance 1000", "%SourcePhantomDistance 950")])
def test_tabla_de_cuna_en_otras_condiciones_se_rechaza(archivos, viejo, nuevo):
    tabla = es_de(archivos, "Standard Wedge - 30", "data: OutputFactorTable")
    assert viejo in tabla
    with pytest.raises(lector.ArchivoNoReconocido, match="mismas condiciones"):
        um_armar.datos_haz(cambiar(archivos, tabla, tabla.replace(viejo, nuevo)), "Clinac 600", "6 MV", d0_dmax=1.0)


def test_el_pdd_se_corrige_desde_su_propia_ssd(archivos):
    """PDD medidos a SSD 90: a SSD 90 F vale 1, y a SSD 100 F = ((100 + 5)/(100 + 10) × (90 + 10)/(90 + 5))²."""
    pdd = es_de(archivos, "data: OPD\n")
    abiertos = [a for a in archivos if a is not pdd and "add on: Open Field" in a]
    d = um_armar.datos_haz(abiertos + [pdd.replace("%SSD 1000", "%SSD 900")], "Clinac 600", "6 MV", d0_tabla=0.86)
    assert d.ssd_pdd_cm == 90.0
    base = 100 * pdd_a_mano(10.0, 10.0) / pdd_a_mano(5.0, 10.0)
    assert motor.pdd_normalizado(d, 10.0, 10.0, 90.0) == pytest.approx(base)
    assert motor.pdd_normalizado(d, 10.0, 10.0, 100.0) == pytest.approx(base * (105 / 110 * 100 / 95) ** 2)


def test_la_cuna_con_pdd_a_otra_ssd_se_rechaza(archivos):
    wdd = es_de(archivos, "data: WDD\n")
    with pytest.raises(lector.ArchivoNoReconocido, match="no se pueden dividir"):
        um_armar.datos_haz(cambiar(archivos, wdd, wdd.replace("%SSD 1000", "%SSD 900", 1)), "Clinac 600", "6 MV", d0_dmax=1.0)


def _wdd_hasta(wdd, hasta_mm):
    """El PDD con cuña medido solo hasta cierta profundidad, con todas sus curvas bien cerradas."""
    return "\n".join(l for l in wdd.split("\n") if not (l.startswith("<") and float(l[1:-1].split()[2]) > hasta_mm))


def test_la_cuna_no_se_calcula_mas_alla_de_lo_medido(archivos):
    wdd = es_de(archivos, "Standard Wedge - 15", "data: WDD\n")
    d = um_armar.datos_haz(cambiar(archivos, wdd, _wdd_hasta(wdd, 150)), "Clinac 600", "6 MV", d0_dmax=1.0)
    assert d.cunas[15].prof_max_cm == 15.0
    assert motor.calcular(d, E(100.0, 10.0, 10.0, 100.0, 15.0, cuna=15)).um > 0
    with pytest.raises(motor.FueraDeTabla, match=r"hasta 15 \[cm\]"):
        motor.calcular(d, E(100.0, 10.0, 10.0, 100.0, 15.1, cuna=15))


def test_la_cuna_medida_hasta_15_da_casi_lo_mismo_que_hasta_30(archivos, datos):
    """Antes el valor se congelaba y el error llegaba a −23 %; ahora solo se ajusta en lo medido."""
    wdd = es_de(archivos, "Standard Wedge - 15", "data: WDD\n")
    d = um_armar.datos_haz(cambiar(archivos, wdd, _wdd_hasta(wdd, 150)), "Clinac 600", "6 MV", d0_dmax=1.0)
    corto, entero = motor.calcular(d, E(100.0, 10.0, 10.0, 100.0, 15.0, cuna=15)).um, motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 15.0, cuna=15)).um
    assert corto == pytest.approx(entero, rel=0.005)


def test_la_cuna_vale_hasta_donde_llega_su_curva_mas_corta(archivos):
    wdd = es_de(archivos, "Standard Wedge - 15", "data: WDD\n")
    primera, resto = wdd.split("%FLSZ 100*100", 1)
    d = um_armar.datos_haz(cambiar(archivos, wdd, _wdd_hasta(primera + "%FLSZ 100*100" + resto.split("$ENOM", 1)[0], 200) + "$ENOM" + resto.split("$ENOM", 1)[1]), "Clinac 600", "6 MV", d0_dmax=1.0)
    assert d.cunas[15].prof_max_cm == 20.0


@pytest.mark.parametrize("hasta_mm", [90, 50])
def test_la_cuna_con_un_tramo_medido_muy_corto_se_rechaza(archivos, hasta_mm):
    wdd = es_de(archivos, "Standard Wedge - 15", "data: WDD\n")
    with pytest.raises(lector.ArchivoNoReconocido, match="cubrir"):
        um_armar.datos_haz(cambiar(archivos, wdd, _wdd_hasta(wdd, hasta_mm)), "Clinac 600", "6 MV", d0_dmax=1.0)


def test_la_cuna_con_profundidades_al_reves_se_rechaza(archivos):
    wdd = es_de(archivos, "Standard Wedge - 15", "data: WDD\n")
    al_reves = []
    for b in re.split(r"(?=\$STOM)", wdd):
        cola = iter(reversed([l for l in b.split("\n") if l.startswith("<")]))
        al_reves.append("\n".join(next(cola) if l.startswith("<") else l for l in b.split("\n")))
    with pytest.raises(lector.ArchivoNoReconocido, match="creciente"):
        um_armar.datos_haz(cambiar(archivos, wdd, "".join(al_reves)), "Clinac 600", "6 MV", d0_dmax=1.0)


def test_la_cuna_con_un_cero_en_su_pdd_se_rechaza(archivos):
    wdd = es_de(archivos, "Standard Wedge - 15", "data: WDD\n")
    malo = re.sub(r"(<\+000\.0 \+000\.0 \+050\.0 )\+[\d.]+>", r"\1+000.000>", wdd)
    assert malo != wdd
    with pytest.raises(lector.ArchivoNoReconocido, match="nulo"):
        um_armar.datos_haz(cambiar(archivos, wdd, malo), "Clinac 600", "6 MV", d0_dmax=1.0)


def test_la_cuna_sin_cuadrados_medidos_se_rechaza(archivos):
    wdd = es_de(archivos, "Standard Wedge - 15", "data: WDD\n")
    sin_cuadrados = re.sub(r"%FLSZ (\d+)\*\d+", lambda m: f"%FLSZ {m.group(1)}*070", wdd)
    with pytest.raises(lector.ArchivoNoReconocido, match="cuadrado"):
        um_armar.datos_haz(cambiar(archivos, wdd, sin_cuadrados), "Clinac 600", "6 MV", d0_dmax=1.0)


def test_el_lado_de_la_cuna_sin_pdd_abierto_no_entra(archivos):
    wdd = es_de(archivos, "Standard Wedge - 15", "data: WDD\n")
    d = um_armar.datos_haz(cambiar(archivos, wdd, wdd.replace("%FLSZ 150*150", "%FLSZ 070*070")), "Clinac 600", "6 MV", d0_dmax=1.0)
    assert list(d.cunas[15].lados_beta) == [4.0, 10.0, 20.0]


def test_cuna_con_orientacion_que_no_cuadra_con_su_tabla_se_rechaza(archivos):
    nd = es_de(archivos, "data: WedgeParameters")
    with pytest.raises(lector.ArchivoNoReconocido, match="no cuadran"):
        um_armar.datos_haz(cambiar(archivos, nd, nd.replace("(IN/OUT/LEFT/RIGHT)[]:IN", "(IN/OUT/LEFT/RIGHT)[]:LEFT")), "Clinac 600", "6 MV", d0_dmax=1.0)


def test_cuna_con_orientacion_desconocida_se_rechaza(archivos):
    nd = es_de(archivos, "data: WedgeParameters")
    with pytest.raises(lector.ArchivoNoReconocido, match="DIAGONAL"):
        um_armar.datos_haz(cambiar(archivos, nd, nd.replace("(IN/OUT/LEFT/RIGHT)[]:IN", "(IN/OUT/LEFT/RIGHT)[]:DIAGONAL")), "Clinac 600", "6 MV", d0_dmax=1.0)


def test_el_angulo_del_name_data_debe_ser_el_de_su_cuna(archivos):
    nd = es_de(archivos, "data: WedgeParameters")
    with pytest.raises(lector.ArchivoNoReconocido, match="ángulo"):
        um_armar.datos_haz(cambiar(archivos, nd, nd.replace("Wedge angle[deg]:15.0", "Wedge angle[deg]:30.0")), "Clinac 600", "6 MV", d0_dmax=1.0)


def _cuadrada(tabla_texto):
    """La misma tabla de cuña, recortada a lados de 2 a 20 en filas y columnas."""
    lineas = tabla_texto.split("\n")
    i = next(k for k, l in enumerate(lineas) if l.startswith("2, ") or l.replace(" ", "").startswith("2,3,"))
    cuerpo = [[v.strip() for v in l.split(",")] for l in lineas[i:] if l.strip()]
    n = cuerpo[0].index("20") + 1
    return "\n".join(lineas[:i] + [", ".join(cuerpo[0][:n])] + [", ".join(f[:n + 1]) for f in cuerpo[1:]]) + "\n"


def _sin_el_campo_entero(wdd):
    """El mismo PDD con cuña sin su curva del campo entero (40 × 20): con la tabla recortada a 20 × 20, ese ya no es el campo entero de la tabla (UM2-D1).
    UM.2 (clase b): la referencia del 05-11 recortaba solo la tabla."""
    pre, *bloques = wdd.split("$STOM")
    quedan = [b for b in bloques if "%FLSZ 400*200" not in b]
    assert len(quedan) == len(bloques) - 1 and "$ENOF" in quedan[-1] and f"$NUMS {len(bloques):03d}" in pre
    return "$STOM".join([pre.replace(f"$NUMS {len(bloques):03d}", f"$NUMS {len(quedan):03d}")] + quedan)


def _con_la_tabla_de_15_cuadrada(archivos):
    tabla, wdd = es_de(archivos, "Standard Wedge - 15", "data: OutputFactorTable"), es_de(archivos, "Standard Wedge - 15", "data: WDD\n")
    return cambiar(cambiar(archivos, tabla, _cuadrada(tabla)), wdd, _sin_el_campo_entero(wdd))


def test_cuna_con_tabla_cuadrada_usa_la_orientacion_del_name_data(archivos):
    nd = es_de(archivos, "data: WedgeParameters")
    con_cuadrada = _con_la_tabla_de_15_cuadrada(archivos)
    assert um_armar.datos_haz(con_cuadrada, "Clinac 600", "6 MV", d0_dmax=1.0).cunas[15].gradiente_en == "Y"
    a_izquierda = cambiar(con_cuadrada, nd, nd.replace("(IN/OUT/LEFT/RIGHT)[]:IN", "(IN/OUT/LEFT/RIGHT)[]:LEFT"))
    assert um_armar.datos_haz(a_izquierda, "Clinac 600", "6 MV", d0_dmax=1.0).cunas[15].gradiente_en == "X"
    with pytest.raises(lector.ArchivoNoReconocido, match="gradiente"):
        um_armar.datos_haz([a for a in con_cuadrada if a is not nd], "Clinac 600", "6 MV", d0_dmax=1.0)


def test_la_mandibula_tampoco_pasa_del_ancho_de_la_tabla_de_la_cuna(archivos):
    d = um_armar.datos_haz(_con_la_tabla_de_15_cuadrada(archivos), "Clinac 600", "6 MV", d0_dmax=1.0)
    with pytest.raises(motor.FueraDeTabla, match="a lo ancho de la cuña"):
        motor.calcular(d, E(100.0, 25.0, 10.0, 100.0, 10.0, x_ef=10.0, y_ef=10.0, cuna=15))


def test_wf_escrito_manda_y_se_valida(archivos):
    d = um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={15: 0.72, 30: 0.65})
    assert d.cunas[15].wf_ref == 0.72 and d.cunas[15].wf_origen == "" and d.cunas[30].wf_ref == 0.65
    with pytest.raises(motor.FaltaDato, match="posible"):
        um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={15: 77.0})
    with pytest.raises(motor.FaltaDato, match="posible"):
        um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={15: 0.09})


def test_wf_escrito_vuelto_de_un_json_sigue_mandando(archivos):
    """La base lo guarda como JSON, y un JSON vuelve con las claves en texto: antes caía en silencio al valor deducido (−6.5 %)."""
    d = um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos=json.loads(json.dumps({15: 0.72})))
    assert d.cunas[15].wf_ref == 0.72


def test_wf_escrito_de_una_cuna_que_no_esta_o_que_no_se_entiende_se_rechaza(archivos):
    with pytest.raises(motor.FaltaDato, match="20"):
        um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={20: 0.7})
    with pytest.raises(motor.FaltaDato, match="número entero de grados"):
        um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={"quince": 0.7})


def test_perfiles_que_no_sirven_se_rechazan_al_cargar(archivos):
    perfiles = es_de(archivos, "Open Field", "data: OPP_processed")
    sin_cuadrados = re.sub(r"%FLSZ (\d+)\*(\d+)", lambda m: f"%FLSZ {m.group(1)}*{int(m.group(2)) + 1:03d}", perfiles)
    with pytest.raises(lector.ArchivoNoReconocido, match="cuadrado"):
        um_armar.datos_haz(cambiar(archivos, perfiles, sin_cuadrados), "Clinac 600", "6 MV", d0_dmax=1.0)


def test_perfil_sin_puntos_fuera_del_eje_o_sin_ssd_se_rechaza():
    x = np.arange(0.0, 20.0, 0.5)
    with pytest.raises(lector.ArchivoNoReconocido, match="fuera del eje"):
        um_armar.perfil_oar(lector.Curva((40.0, 40.0), 100.0, np.zeros(3), np.full(3, 10.0), np.full(3, 50.0)))
    with pytest.raises(lector.ArchivoNoReconocido, match="SSD"):
        um_armar.perfil_oar(lector.Curva((40.0, 40.0), None, x, np.full_like(x, 10.0), np.full_like(x, 50.0)))


def test_perfil_nulo_cerca_del_eje_se_rechaza():
    x = np.arange(0.0, 20.0, 0.5)
    with pytest.raises(lector.ArchivoNoReconocido, match="nulo"):
        um_armar.perfil_oar(lector.Curva((40.0, 40.0), 100.0, x, np.full_like(x, 10.0), np.zeros_like(x)))


def test_una_profundidad_medida_solo_con_campos_pequenos_no_cuenta():
    x = np.arange(0.0, 30.0, 0.5)
    curva = lambda lado, prof: lector.Curva((lado, lado), 100.0, x, np.full_like(x, prof), np.full_like(x, 50.0))
    p = um_armar.perfiles_oar([curva(40.0, 5.0), curva(40.0, 10.0), curva(3.0, 1.5)])
    assert [q.prof for q in p.grandes] == [5.0, 10.0] and len(p.todos) == 3
    with pytest.raises(lector.ArchivoNoReconocido, match="dos profundidades"):
        um_armar.perfiles_oar([curva(40.0, 5.0)])
    with pytest.raises(lector.ArchivoNoReconocido, match="ningún campo cuadrado"):      # UM.2: la sobreviviente R154 del pre-vuelo
        um_armar.perfiles_oar([])


def test_perfiles_de_un_campo_mas_pequeno_a_30_cm_cuentan():
    x = np.arange(0.0, 30.0, 0.5)
    curva = lambda lado, prof: lector.Curva((lado, lado), 100.0, x, np.full_like(x, prof), np.full_like(x, 50.0))
    assert [q.lado for q in um_armar.perfiles_oar([curva(40.0, 20.0), curva(35.0, 30.0), curva(20.0, 20.0)]).grandes] == [40.0, 35.0]


def test_revision_de_la_carga_dice_lo_que_entendio(archivos):
    pares = [(f"a{i}.txt", t) for i, t in enumerate(archivos)]
    r = um_armar.revisar_archivos(pares, "Clinac 600", "6 MV", d0_dmax=1.0)
    assert not r.problemas and len(r.usados) == 12 and len(r.ignorados) == 10
    unido = " ".join(r.avisos)
    assert "Y = 30 [cm], X = 25 [cm]" in unido and "Cuña de 45°" in unido and "falta su factor" in unido and "35 × 35 a 30 [cm]" in unido and "falta confirmarlo" in unido


def test_revision_tiene_en_cuenta_los_factores_escritos_y_la_curva_de_sc(archivos):
    pares = [(f"a{i}.txt", t) for i, t in enumerate(archivos)]
    r = um_armar.revisar_archivos(pares, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={30: 0.7}, sc=((5.0, 0.98), (10.0, 1.0)), sc_origen="medida")
    assert not any("Cuña de 30°: falta" in a for a in r.avisos) and any("Cuña de 45°: falta" in a for a in r.avisos) and any("Curva de Sc: medida" in a for a in r.avisos)


def test_revision_no_deja_cargar_tablas_de_otra_maquina_u_otra_energia(archivos):
    pares = [(f"a{i}.txt", t) for i, t in enumerate(archivos)]
    assert any("dice máquina 600C" in p for p in um_armar.revisar_archivos(pares, "Clinac iX", "6 MV", d0_dmax=1.0).problemas)
    assert any("dice haz 6X" in p for p in um_armar.revisar_archivos(pares, "Clinac 600", "15 MV", d0_dmax=1.0).problemas)


def test_revision_avisa_si_no_reconoce_la_maquina_o_el_haz(archivos):
    otros = [(f"a{i}.txt", re.sub(r"(?im)^(#?\s*machine:\s*).*$", r"\1Sala 2, X06", t)) for i, t in enumerate(archivos)]
    r = um_armar.revisar_archivos(otros, "Clinac 600", "6 MV", d0_dmax=1.0)
    assert not r.problemas and any("máquina Sala 2" in a and "no reconoce" in a for a in r.avisos) and any("haz X06" in a for a in r.avisos)


def test_revision_no_deja_guardar_un_archivo_cortado_ni_dos_distintos_para_lo_mismo(archivos):
    pares = [(f"a{i}.txt", t) for i, t in enumerate(archivos)]
    of = es_de(archivos, "Open Field", "OutputFactorTable")
    r = um_armar.revisar_archivos(pares + [("otra.txt", of.replace("0.870", "0.871"))], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert any("dos archivos distintos" in p for p in r.problemas)
    r = um_armar.revisar_archivos([("x.txt", "cualquier cosa")], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert any("x.txt" in p for p in r.problemas)
    pdd = es_de(archivos, "data: OPD\n")
    r = um_armar.revisar_archivos([(f"a{i}.txt", pdd[:len(pdd) * 9 // 10] if t is pdd else t) for i, t in enumerate(archivos)], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert any("cortado" in p or "punto" in p for p in r.problemas)


def test_revision_avisa_de_la_cuna_a_la_que_le_falta_un_archivo(archivos):
    sin_wdd = [t for t in archivos if not ("data: WDD\n" in t and "Wedge - 45" in t)]
    r = um_armar.revisar_archivos([(f"a{i}.txt", t) for i, t in enumerate(sin_wdd)], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert not r.problemas and "Cuña de 45°: falta su PDD medido con cuña; sus archivos no se usan y sus campos se escriben a mano." in r.avisos
    assert not any("Cuña de 30°: falta su PDD" in a for a in r.avisos)
    # UM.2 v2 (L-UM2-2): la tabla y el name.data de esa cuña no se usan, así que tampoco pesan en la carga aunque digan otra máquina (UM2-D4)
    nombres = {f"a{i}.txt": t for i, t in enumerate(sin_wdd)}
    de_la_45 = [n for n, t in nombres.items() if "Wedge - 45" in t]
    tabla_45 = next(n for n in de_la_45 if "data: OutputFactorTable" in nombres[n])
    assert set(de_la_45) <= set(r.ignorados) and not set(de_la_45) & set(r.usados)
    otra = um_armar.revisar_archivos([(n, t.replace("machine: 600C, 6X", "machine: iX, 6X") if n == tabla_45 else t) for n, t in nombres.items()], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert otra.problemas == () and otra.usados == r.usados


def test_revision_avisa_de_un_accesorio_que_no_reconoce(archivos):
    otros = [t.replace("add on: Standard Wedge - 60", "add on: Upper Wedge - 60") for t in archivos]
    r = um_armar.revisar_archivos([(f"a{i}.txt", t) for i, t in enumerate(otros)], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert not r.problemas and any("Upper Wedge - 60" in a and "no se reconoce" in a for a in r.avisos)
    assert not any("Standard Wedge - 15" in a and "no se reconoce" in a for a in r.avisos)


def test_revision_convierte_cualquier_fallo_de_lectura_en_un_motivo(archivos, monkeypatch):
    monkeypatch.setattr(um_armar, "datos_haz", lambda *a, **k: 1 / 0)
    r = um_armar.revisar_archivos([(f"a{i}.txt", t) for i, t in enumerate(archivos)], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert any("ZeroDivisionError" in p for p in r.problemas)


# ---------- La curva de Sc ----------
def test_sc_del_haz_sale_de_su_tabla_y_el_sp_de_la_tg71(datos):
    """Sc(J) = OF(J, J)/Sp(1.05·J), normalizado en 10, con las celdas de la tabla y Sp a mano: Sp(15.75) = 1.0295 y Sp(10.5) = 1.00305."""
    assert "este haz" in datos.sc_origen
    assert motor.sc_de(datos.sc, 10.0) == pytest.approx(1.0)
    assert motor.sc_de(datos.sc, 15.0) == pytest.approx(1.036 / 1.0295 * 1.00305, abs=2e-4)
    assert motor.sc_de(datos.sc, 5.0) == pytest.approx(0.9749, abs=5e-4)
    assert motor.sc_de(datos.sc, 35.0) == pytest.approx(1.0282, abs=5e-4)
    assert datos.sc[0][0] == 4.0 and datos.sc[-1][0] == pytest.approx(40 / 1.05)


def test_sc_del_haz_proyecta_con_la_ssd_de_su_tabla(datos):
    """Tabla a SSD 95 y 5 cm: el campo a 5 cm mide J, y Sp(15) = 1.0213 + 0.0093·ln(15/14)/ln(16/14) = 1.02611."""
    sc, origen = um_armar.sc_del_haz(datos.of, 95.0, 5.0, "6 MV")
    assert "este haz" in origen and motor.sc_de(sc, 15.0) == pytest.approx(1.036 / 1.02611, abs=1e-4) and sc[-1][0] == 40.0


def test_sp_a_5_cm_se_deduce_de_las_tablas_de_la_tg71():
    """Sp(r; 5 cm) = Sp(r; 10 cm) × TPR(5; r)/TPR(5; 10), con la tabla IV y la fila d = 5 de la tabla III, copiadas del documento."""
    sp10 = {4: .905, 5: .925, 6: .944, 8: .974, 10: 1.0, 12: 1.020, 14: 1.037, 16: 1.051, 20: 1.076, 24: 1.096, 28: 1.111, 32: 1.123, 40: 1.139}
    tpr5 = {4: 1.24, 5: 1.23, 6: 1.217, 8: 1.2, 10: 1.187, 12: 1.177, 14: 1.169, 16: 1.164, 20: 1.151, 24: 1.141, 28: 1.135, 32: 1.131, 40: 1.122}
    assert [r for r, _ in um_armar.SP_A_5CM_TG71] == list(sp10)
    for r, sp in um_armar.SP_A_5CM_TG71:
        assert sp == pytest.approx(sp10[r] * tpr5[r] / tpr5[10], abs=1e-4), r


def test_la_tabla_iv_es_la_del_documento():
    assert motor.SC_MUESTRA_TG71 == ((4.0, 0.957), (5.0, 0.968), (6.0, 0.977), (8.0, 0.990), (10.0, 1.000), (12.0, 1.008), (14.0, 1.014), (16.0, 1.018), (20.0, 1.024), (24.0, 1.029), (28.0, 1.034), (32.0, 1.040), (40.0, 1.048))


def test_sc_se_interpola_en_log_y_no_sale_de_sus_extremos():
    curva = motor.SC_MUESTRA_TG71
    assert motor.sc_de(curva, 9.0) == pytest.approx(0.990 + 0.010 * math.log(9 / 8) / math.log(10 / 8), abs=1e-9)
    assert motor.sc_de(curva, 2.0) == 0.957 and motor.sc_de(curva, 60.0) == 1.048


def test_otra_energia_usa_la_tabla_iv_y_lo_dice(archivos):
    """UM.2 v2 (IF-3): los archivos deben ser de la energía pedida; aquí dicen 15X."""
    d = um_armar.datos_haz([t.replace("machine: 600C, 6X", "machine: 600C, 15X") for t in archivos], "Clinac 600", "15 MV", d0_dmax=1.0)
    assert d.sc == motor.SC_MUESTRA_TG71 and "tabla IV" in d.sc_origen


def test_otra_profundidad_de_tabla_usa_la_tabla_iv(archivos):
    otros = [a.replace("%DetectorDepth 50", "%DetectorDepth 100") for a in archivos if "add on: Open Field" in a]
    assert "tabla IV" in um_armar.datos_haz(otros, "Clinac 600", "6 MV", d0_tabla=0.7).sc_origen


def test_una_tabla_de_6_mv_que_no_llega_a_38_cm_tambien_se_estima(archivos):
    """Antes se rechazaba: la curva pedía leer 38.1 cm en una tabla que llega a 35."""
    of = es_de(archivos, "Open Field", "OutputFactorTable")
    lineas = of.split("\n")
    i = next(k for k, l in enumerate(lineas) if l.replace(" ", "").startswith("2.5,3"))
    cuerpo = [[v.strip() for v in l.split(",")] for l in lineas[i:] if l.strip()]
    corta = "\n".join(lineas[:i] + [", ".join(cuerpo[0][:-1])] + [", ".join(f[:-1]) for f in cuerpo[1:-1]]) + "\n"
    d = um_armar.datos_haz([corta if a is of else a for a in archivos if "add on: Open Field" in a], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert d.of.x[-1] == 35.0 and "este haz" in d.sc_origen and d.sc[-1][0] == 35.0


def test_una_curva_de_sc_propia_manda(archivos):
    d = um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, sc=[[5.0, 0.98], [10.0, 1.0], [20.0, 1.01]], sc_origen="medida")
    assert d.sc_origen == "medida" and d.sc == ((5.0, 0.98), (10.0, 1.0), (20.0, 1.01))


def test_una_curva_de_sc_vacia_apaga_la_correccion(archivos):
    assert um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, sc=(), sc_origen="").sc == ()


@pytest.mark.parametrize("curva", [((10.0, 1.0), (5.0, 0.98)), ((5.0, 0.98), (5.0, 0.99)), ((5.0, 0.0), (10.0, 1.0)), ((5.0, float("nan")), (10.0, 1.0)), ((-5.0, 0.98), (10.0, 1.0)), ((5.0, 98.0), (10.0, 1.0)), ((10.0, 1.0),), "curva", ((1.0,),)])
def test_una_curva_de_sc_mala_se_rechaza(archivos, curva):
    with pytest.raises(motor.FaltaDato, match="curva de Sc"):
        um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, sc=curva, sc_origen="x")


# ---------- Términos de la ecuación, a mano ----------
def test_factor_f_a_mano():
    assert motor.factor_mayneord(6.0, 10.0, 94.0, 100.0) == pytest.approx(((104 / 100) * (106 / 110)) ** 2)
    assert motor.factor_mayneord(10.0, 5.0, 100.0, 100.0) == pytest.approx(1.0)


def test_inverso_del_cuadrado_a_mano(datos):
    assert motor.inverso_cuadrado(datos, 90.0) == pytest.approx((105 / 95) ** 2)
    assert motor.inverso_cuadrado(datos, 100.0) == pytest.approx(1.0)


def test_equivalente_a_mano():
    assert motor.equivalente(10.0, 15.0) == pytest.approx(12.0)


def test_la_lectura_cae_exacta_en_los_puntos_de_la_tabla(datos):
    assert datos.of(10.0, 10.0) == 1.0
    assert datos.of(5.0, 20.0) == pytest.approx(0.981)  # fila Y = 20, columna X = 5
    assert datos.of(20.0, 5.0) == pytest.approx(0.968)
    assert datos.pdd(10.0, 10.0) == pytest.approx(66.2)


def test_la_lectura_entre_puntos_es_lineal_en_log(datos):
    t = tabla_real()
    assert datos.of(7.0, 12.0) == pytest.approx(tabla_a_mano(t, 7.0, 12.0))
    assert datos.pdd(10.0, 8.0) == pytest.approx(pdd_a_mano(10.0, 8.0))
    assert datos.pdd(7.25, 10.0) == pytest.approx((np.interp(7.25, [7.2, 7.3], [datos.pdd(7.2, 10.0), datos.pdd(7.3, 10.0)])))


def test_dmax_es_el_del_campo_medido_mas_cercano(datos):
    curvas = {c.campo_cm[0]: c for c in lector.leer_curvas(texto(PDD_ABIERTO))}
    for lado in (2.5, 10.0, 40.0):
        assert datos.pdd.dmax(lado) == curvas[lado].z_cm[int(np.argmax(curvas[lado].valor))]
    assert datos.pdd.dmax(11.0) == datos.pdd.dmax(10.0) and datos.pdd.dmax(2.5) != datos.pdd.dmax(40.0)


def test_los_factores_de_lectura_a_mano(datos):
    assert motor.factores_de_lectura(datos, 100.0, 10.0, 10.0) == (1.0, 1.0)
    pdd, of = motor.factores_de_lectura(datos, 90.0, 10.0, 10.0)
    assert (pdd, of) == (pytest.approx(100 / 110), pytest.approx(100 / 110))
    pdd, of = motor.factores_de_lectura(datos, 100.0, 15.0, 8.0)     # con profundidad efectiva: el campo es el de la profundidad física
    assert (pdd, of) == (pytest.approx(115 / 108), pytest.approx(115 / 108))


def test_los_factores_de_lectura_con_tablas_a_otra_ssd():
    d = motor.DatosHaz("x", "x", 95.0, 5.0, 0.9, None, None, ssd_pdd_cm=100.0)
    pdd, of = motor.factores_de_lectura(d, 90.0, 10.0, 10.0)
    assert pdd == pytest.approx(100 / 110) and of == pytest.approx(100 / 110 * 105 / 100)   # Sp(c·(95 + 5)/100) = Sp(r'·(100 + 5)/100)


# ---------- La verdad de la TG-71: un haz sintético en el que el TPR no depende de la distancia ----------
def _sp(r):
    return 1 + 0.12 * math.log(r / 10)


def _sc(r):
    return 1 + 0.035 * math.log(r / 10)


def _tpr(d, r):
    return math.exp(-(0.048 - 0.006 * math.log(r / 10)) * (d - 5.0))


@pytest.fixture(scope="module")
def haz_sintetico():
    """Tablas hechas con la ecuación 16 de la TG-71 a SSD 100, sin usar el motor."""
    lados = np.geomspace(1.5, 90.0, 140)
    z = np.arange(0.0, 40.01, 0.25)
    f = lambda d: (100 + d) / 100
    pdd = np.array([[100 * _tpr(d, r * f(d)) * _sp(r * f(d)) / _sp(r * f(5.0)) * (105 / (100 + d)) ** 2 for d in z] for r in lados])
    of = np.array([[_sc(motor.equivalente(x, y)) * _sp(motor.equivalente(x, y) * 1.05) for x in lados] for y in lados])
    return motor.DatosHaz("S", "6 MV", 100.0, 5.0, 0.86, motor.FamiliaPDD(lados, z, pdd), motor.TablaFactores(lados, lados, of), sc=tuple((float(s), _sc(float(s))) for s in lados), sc_origen="verdadero")


@pytest.mark.parametrize("ssd", [70.0, 80.0, 90.0, 100.0, 110.0, 120.0, 130.0])
@pytest.mark.parametrize("campo", [(5.0, 5.0, None, None), (10.0, 10.0, None, None), (30.0, 30.0, None, None), (8.0, 20.0, None, None), (20.0, 20.0, 6.0, 6.0), (15.0, 15.0, 8.0, 12.0)])
@pytest.mark.parametrize("prof, prof_ef", [(3.0, None), (5.0, None), (10.0, None), (20.0, None), (30.0, None), (15.0, 8.0), (10.0, 14.0)])
def test_la_ecuacion_3_con_la_14_completa_da_la_ecuacion_1(haz_sintetico, ssd, campo, prof, prof_ef):
    """MU de la ecuación 1 = D'0·Sc(rc)·Sp(rd)·TPR(d_lectura, rd)·((SSD0 + d0)/(SSD + d))². Ignorar el cociente de TPR de la ecuación 14 daría hasta cerca de 1 %."""
    x, y, x_ef, y_ef = campo
    rc, r_iso = motor.equivalente(x, y), motor.equivalente(x_ef or x, y_ef or y)
    rd = r_iso * (ssd + prof) / 100
    verdad = 0.86 * _sc(rc) * _sp(rd) * _tpr(prof_ef or prof, rd) * (105 / (ssd + prof)) ** 2
    r = motor.calcular(haz_sintetico, E(100.0, x, y, ssd, prof, x_ef=x_ef, y_ef=y_ef, prof_ef=prof_ef))
    assert r.d_um == pytest.approx(verdad, rel=6e-4)


# ---------- Casos completos, con la cuenta a mano ----------
def test_campo_de_referencia_a_ssd_100(datos):
    """A SSD 100, UM = D / (PDD a 10 cm): 200 / 0.662, sin ningún otro factor."""
    r = motor.calcular(datos, E(200.0, 10.0, 10.0, 100.0, 10.0))
    assert r.um == pytest.approx(200 / 0.662, rel=1e-3)
    assert factor(r, "OF") == 1.0 and factor(r, "Sc(rc)/Sc(lectura)") == 1.0 and factor(r, "Inverso del cuadrado") == pytest.approx(1.0)
    assert r.avisos == ()


def test_en_dmax_a_ssd_100_una_um_da_d0(datos):
    """100 cGy en dmax, 10 × 10, SSD 100: 100 UM, porque D'0 es 1 cGy/UM en dmax."""
    dmax = datos.pdd.dmax(10.0)
    assert motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, dmax)).um == pytest.approx(100.0, rel=1e-3)


def test_isocentrico_cuenta_a_mano(datos):
    """10 × 10, SSD 90, d = 10, sin curva de Sc. Se lee en 10·(90 + 10)/(100 + 10) = 9.09 cm, tanto la tabla como el PDD."""
    sin_sc = motor.DatosHaz(datos.equipo, datos.energia, 100.0, 5.0, 0.860, datos.pdd, datos.of, sc=())
    lado = 10 * 100 / 110
    of = tabla_a_mano(tabla_real(), lado, lado)
    pdd_n = 100 * pdd_a_mano(10.0, lado) / pdd_a_mano(5.0, lado) * ((95 / 100) * (110 / 105)) ** 2
    r = motor.calcular(sin_sc, E(200.0, 10.0, 10.0, 90.0, 10.0))
    assert r.um == pytest.approx(200 / (0.860 * of * pdd_n / 100 * (105 / 95) ** 2))
    assert factor(r, "OF") == pytest.approx(of) and factor(r, "PDD_N") == pytest.approx(pdd_n)
    assert r.campos == {"rc": 10.0, "r": 9.0, "rd0": 9.5, "r_pdd": pytest.approx(lado), "x_lectura": pytest.approx(lado), "y_lectura": pytest.approx(lado)}
    assert r.lectura_alterna_of == 1.0


def test_la_salida_trae_cada_factor(datos):
    r = motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 10.0, um_planeador=150.0))
    assert [f.simbolo for f in r.factores] == ["D", "D'0", "OF", "Sc(rc)/Sc(lectura)", "PDD_N", "WF", "TF", "OAR", "Inverso del cuadrado", "Corrección por profundidad efectiva"]
    assert {f.simbolo: f.origen for f in r.factores}["D"] == "plan" and {f.simbolo: f.origen for f in r.factores}["OF"] == "tabla"
    producto = 1.0
    for f in r.factores[1:]:
        producto *= f.valor / (100 if f.simbolo == "PDD_N" else 1)
    assert r.d_um == pytest.approx(producto) and r.um == pytest.approx(100.0 / producto)


@pytest.fixture(scope="module")
def haz_tg71():
    """El haz de los ejemplos de la TG-71: tabla IV (Scp por cuadrado equivalente) y las filas de la tabla II que usan (PDD_N a SSD 100, d0 = 10 cm). SSD0 = 90, D'0 = 0.8."""
    lados = np.array([4.0, 5, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32, 40])
    scp = np.array([.866, .895, .922, .964, 1.0, 1.028, 1.051, 1.070, 1.102, 1.127, 1.149, 1.167, 1.194])
    m = np.array([[np.interp(math.log(motor.equivalente(x, y)), np.log(lados), scp) for x in lados] for y in lados])
    pdd = motor.FamiliaPDD(np.array([4.0, 5, 9, 10, 11, 12]), np.array([6.0, 9.5, 10.0]),
                           np.array([[127.7, 103.2, 100.0], [126.6, 102.7, 100.0], [123.8, 102.6, 100.0], [123.2, 102.5, 100.0], [122.7, 102.5, 100.0], [122.3, 102.6, 100.0]]))
    return motor.DatosHaz("TG-71", "6 MV", 90.0, 10.0, 0.8, pdd, motor.TablaFactores(lados, lados, m))


EJ2 = dict(dosis=90.0, x=18.0, y=12.0, ssd=90.0, prof=10.0, x_ef=14.0, y_ef=8.0, wf_manual=0.711)
EJ3 = dict(dosis=45.0, x=5.5, y=7.0, ssd=90.5, prof=9.5, x_ef=4.0, y_ef=5.0)


@pytest.mark.parametrize("publicado, entrada", [
    (266.0, dict(dosis=250.0, x=10.0, y=15.0, ssd=94.0, prof=6.0)),   # ejemplo 1, ecuación 26
    (156.0, EJ2),                                                     # ejemplo 2: mandíbulas 18 × 12, bloque 14 × 8, WF 0.711
    (135.0, {**EJ2, "prof_ef": 6.0}),                                 # ejemplo 2 con profundidad efectiva
    (73.0, {**EJ3, "wf_manual": 0.845}),                              # ejemplo 3
    (69.0, {**EJ3, "wf_manual": 0.892, "oar_manual": 1.005}),         # ejemplo 3 fuera del eje
])
def test_los_ejemplos_resueltos_de_la_tg71_salen(haz_tg71, publicado, entrada):
    """La TG-71 publica las UM en enteros: el motor debe caer dentro de ese redondeo."""
    assert motor.calcular(haz_tg71, E(**entrada)).um == pytest.approx(publicado, abs=0.5)


def test_ejemplo_resuelto_de_la_tg71_con_la_ecuacion_3(haz_tg71):
    """Ejemplo 1 de la sección 8 de la TG-71, término por término: 250 cGy, 10 × 15, SSD 94, d = 6, d0 = 10, SSD0 = 90, D'0 = 0.8: 266 UM (ecuación 26)."""
    r = motor.calcular(haz_tg71, E(250.0, 10.0, 15.0, 94.0, 6.0))
    assert factor(r, "PDD_N") == pytest.approx(123.1, abs=0.15)              # 1.231 en la ecuación 26
    assert factor(r, "Inverso del cuadrado") == pytest.approx(0.925, abs=0.001)
    assert factor(r, "OF") * factor(r, "Sc(rc)/Sc(lectura)") == pytest.approx(1.008 * 1.024, abs=0.002)  # Sc(12)·Sp(12.5)
    assert r.campos["r"] == pytest.approx(11.28) and r.campos["rd0"] == pytest.approx(12.48)                # 11.3 y 12.5 en el ejemplo


# ---------- Corrección de Sc ----------
def test_mandibulas_solas_a_ssd_100_no_se_corrige_nada(datos):
    assert factor(motor.calcular(datos, E(100.0, 7.0, 13.0, 100.0, 10.0)), "Sc(rc)/Sc(lectura)") == 1.0


def test_laminas_corrigen_con_el_sc_de_las_mandibulas(datos):
    """Mandíbulas 15 × 15, abertura 10 × 10, SSD 100: Sc(15)/Sc(10) de la curva de este haz, a mano como en `test_sc_del_haz...`."""
    r = motor.calcular(datos, E(100.0, 15.0, 15.0, 100.0, 10.0, x_ef=10.0, y_ef=10.0))
    assert factor(r, "Sc(rc)/Sc(lectura)") == pytest.approx(1.036 / 1.0295 * 1.00305, abs=2e-4)
    assert "campo efectivo" in " ".join(r.avisos)


def test_sin_curva_de_sc_no_hay_correccion_y_lo_dice(datos):
    sin_sc = motor.DatosHaz(datos.equipo, datos.energia, datos.ssd0_cm, datos.d0_cm, datos.d0_norm, datos.pdd, datos.of, sc=(), sc_origen="")
    r = motor.calcular(sin_sc, E(100.0, 15.0, 15.0, 90.0, 10.0))
    assert factor(r, "Sc(rc)/Sc(lectura)") == 1.0 and "no hay curva de Sc" in " ".join(r.avisos)


def test_cuando_la_curva_de_sc_no_alcanza_avisa(datos):
    aviso = avisos_de(datos, 100.0, 20.0, 20.0, 100.0, 10.0, x_ef=3.0, y_ef=3.0)
    assert "curva de Sc" in aviso and "corta" in aviso
    assert "corta" not in avisos_de(datos, 100.0, 20.0, 20.0, 100.0, 10.0, x_ef=5.0, y_ef=5.0)


# ---------- Campo y punto ----------
@pytest.mark.parametrize("kw", [dict(punto_x=6.0), dict(punto_y=-5.0), dict(centro_x=5.0), dict(centro_x=6.0), dict(centro_y=-5.0, punto_y=0.0)])
def test_punto_fuera_o_en_el_borde_no_da_numero(datos, kw):
    with pytest.raises(motor.FueraDelCampo, match="borde o fuera"):
        motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 10.0, **kw))


def test_en_un_campo_asimetrico_el_margen_se_mide_al_borde_real(datos):
    assert "[cm] del borde" not in avisos_de(datos, 100.0, 20.0, 20.0, 100.0, 10.0, centro_x=8.0, punto_x=8.0, oar_manual=1.0)   # x1 = 2, x2 = 18, punto a 10 cm de cada borde
    assert "a 1.0 [cm] del borde" in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, 10.0, centro_x=4.0)                            # x1 = 1, x2 = 9, punto a 1 cm


def test_el_limite_del_borde_son_2_cm(datos):
    assert "[cm] del borde" not in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, 10.0, punto_x=3.0)
    assert "a 1.9 [cm] del borde" in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, 10.0, punto_x=3.1)


@pytest.mark.parametrize("entrada", [dict(x=10.0, y=10.0, x_ef=20.0, y_ef=20.0), dict(x=10.0, y=40.0, x_ef=20.0, y_ef=13.33), dict(x=10.0, y=10.0, x_ef=5.0, y_ef=20.0), dict(x=10.0, y=10.0, x_ef=20.0, y_ef=5.0), dict(x=10.0, y=20.0, x_ef=14.0, y_ef=14.0)])
def test_efectivo_mayor_que_las_mandibulas_no_da_numero(datos, entrada):
    with pytest.raises(motor.FueraDelCampo, match="mayor que las mandíbulas"):
        motor.calcular(datos, E(100.0, ssd=100.0, prof=10.0, **entrada))


@pytest.mark.parametrize("x, y, lado", [(10.0, 20.0, 12.0), (8.0, 20.0, 10.0), (12.0, 18.0, 13.0), (6.0, 25.0, 8.5), (10.0, 20.0, 13.3)])
def test_un_cuadrado_equivalente_puede_pasar_del_lado_corto(datos, x, y, lado):
    """Era un rechazo falso: el equivalente de un rectángulo es mayor que su lado corto. Se compara con 4A/P. UM.2 v2 (UM2-D9): el 13.3 de un 10 × 20 es su 4A/P
    redondeado (13.33): no hay láminas, el campo es el de las mandíbulas y r = rc."""
    r = motor.calcular(datos, E(100.0, x, y, 100.0, 10.0, x_ef=lado, y_ef=lado))
    rc = motor.equivalente(x, y)
    assert r.campos["rc"] == pytest.approx(rc) and r.campos["r"] == pytest.approx(rc if lado == 13.3 else lado, rel=1e-12)


def test_el_redondeo_del_lado_efectivo_no_rechaza(datos):
    assert motor.calcular(datos, E(100.0, 10.0, 12.0, 100.0, 10.0, x_ef=10.04, y_ef=11.0)).um > 0
    assert motor.calcular(datos, E(100.0, 10.0, 12.0, 100.0, 10.0, x_ef=10.1, y_ef=11.0)).um > 0
    assert motor.calcular(datos, E(100.0, 12.0, 10.0, 100.0, 10.0, x_ef=11.0, y_ef=10.1)).um > 0       # lo mismo en Y
    with pytest.raises(motor.FueraDelCampo):
        motor.calcular(datos, E(100.0, 10.0, 12.0, 100.0, 10.0, x_ef=10.11, y_ef=11.0))
    with pytest.raises(motor.FueraDelCampo):
        motor.calcular(datos, E(100.0, 12.0, 10.0, 100.0, 10.0, x_ef=11.0, y_ef=10.11))


def test_efectivo_a_medias_no_da_numero(datos):
    with pytest.raises(motor.FaltaDato, match="dos lados"):
        motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 10.0, x_ef=5.0))


def test_con_laminas_avisa_que_no_las_conoce_y_no_inventa_un_borde(datos):
    """No se sabe dónde está la abertura: ni «a 0.0 cm del borde» ni silencio."""
    for kw in (dict(centro_x=8.0, x_ef=10.0, y_ef=10.0), dict(x_ef=10.0, y_ef=10.0, punto_x=8.0)):
        aviso = avisos_de(datos, 100.0, 20.0, 20.0, 100.0, 10.0, **kw)
        assert "no conoce las láminas" in aviso and "a 0.0 [cm] del borde" not in aviso


def test_sin_laminas_no_se_habla_de_laminas(datos):
    assert "láminas" not in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, 10.0)
    assert "láminas" not in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, 10.0, x_ef=10.0, y_ef=10.0)
    assert "campo efectivo" in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, 10.0, x_ef=9.5, y_ef=9.5)   # basta con que difiera
    assert "campo efectivo" in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, 10.0, x_ef=10.1, y_ef=10.0)   # también si es mayor, dentro del redondeo de 0.1 cm
    assert "campo efectivo" in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, 10.0, x_ef=10.0, y_ef=10.1)


@pytest.mark.parametrize("kw", [dict(centro_x=5.0, punto_x=5.0), dict(centro_y=-7.0, punto_y=-7.0),
                                dict(centro_x=6.0, punto_x=6.0), dict(centro_y=5.0, punto_y=5.0)])      # el eje justo en el borde de Y y claramente fuera de X
def test_avisa_si_el_eje_no_esta_dentro_del_campo(datos, kw):
    assert "eje queda en el borde o fuera" in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, 10.0, oar_manual=1.0, **kw)


def test_no_avisa_del_eje_si_esta_dentro(datos):
    assert "eje queda" not in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, 10.0, centro_x=4.0, centro_y=-4.0)


# ---------- Profundidad efectiva ----------
def test_profundidad_efectiva_a_mano(datos):
    """SSD 100, d = 10, d_ef = 6: el campo a la profundidad física, leído a 6 cm: 10·110/106. Distancia: ((100 + 6)/110)²."""
    lado = 10 * 110 / 106
    of = tabla_a_mano(tabla_real(), lado, lado)
    pdd_n = 100 * pdd_a_mano(6.0, lado) / pdd_a_mano(5.0, lado)
    r = motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 10.0, prof_ef=6.0))
    sc = factor(r, "Sc(rc)/Sc(lectura)")
    assert 0.995 < sc < 1.0
    assert r.d_um == pytest.approx(0.860 * of * sc * pdd_n / 100 * (106 / 110) ** 2)


def test_oar_y_cuna_se_leen_en_la_profundidad_fisica(datos):
    """TG-71, ec. 7 y ec. 3: la corrección de heterogeneidad multiplica la dosis homogénea, y sus OAR(d, x) y WF(d, ...) son de la profundidad física."""
    r = motor.calcular(datos, E(100.0, 30.0, 30.0, 100.0, 15.0, prof_ef=8.0, punto_x=8.0))
    assert factor(r, "OAR") == pytest.approx((oar_a_mano(40.0, 10.0, 8.0) + oar_a_mano(40.0, 20.0, 8.0)) / 2)
    r = motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 20.0, prof_ef=8.0, cuna=15))
    assert factor(r, "WF") == pytest.approx(WF15 * math.exp(beta_a_mano(15, 10.0) * 15))


@pytest.mark.parametrize("kw", [dict(prof=10.0, prof_ef=1.0), dict(prof=1.0, prof_ef=10.0)])
def test_build_up_mira_las_dos_profundidades(datos, kw):
    assert "dmax" in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, **kw)


# ---------- OAR ----------
def test_la_profundidad_del_perfil_es_la_de_sus_puntos():
    x = np.arange(0.0, 20.0, 0.5)
    assert um_armar.perfil_oar(lector.Curva((40.0, 40.0), 90.0, x, np.full_like(x, 10.0), np.full_like(x, 50.0))).prof == 10.0


def test_el_perfil_proyecta_x_con_su_propia_ssd():
    x, oar = np.array([0.0, 10.0, 20.0]), np.array([1.0, 1.1, 1.2])
    assert motor.PerfilOAR(10.0, 40.0, x, oar, 100.0)(10.0) == pytest.approx(1.1 + 0.1 * 1.0 / 10)  # x = 11 cm
    assert motor.PerfilOAR(10.0, 40.0, x, oar, 90.0)(10.0) == pytest.approx(1.1)                     # x = 10 cm


def test_el_perfil_guarda_la_ssd_de_su_archivo():
    x = np.arange(0.0, 20.0, 0.5)
    assert um_armar.perfil_oar(lector.Curva((40.0, 40.0), 90.0, x, np.full_like(x, 10.0), np.full_like(x, 50.0))).ssd == 90.0


def test_el_centro_del_perfil_no_es_la_muestra_del_pdd():
    """La muestra en x = 0 es el valor del PDD: el centro sale de ajustar a + b·x² sin ella, hasta 3 cm."""
    x = np.arange(0.0, 20.0, 0.25)
    v = 50.0 + 0.1 * x ** 2
    v[0] = 66.0
    v[x > 3.0] *= 1.1           # lo de más allá de 3 cm no debe pesar
    p = um_armar.perfil_oar(lector.Curva((40.0, 40.0), 100.0, x, np.full_like(x, 10.0), v))
    assert p.oar[0] == 1.0 and p.x[0] == 0.0 and p.x[1] > 0
    assert np.interp(1.0, p.x, p.oar) == pytest.approx(50.1 / 50.0)


def test_el_centro_de_un_perfil_pequeno_se_ajusta_hasta_un_cuarto_del_lado():
    x = np.arange(0.0, 6.0, 0.25)
    v = 50.0 + 0.1 * x ** 2
    v[x > 2.0] *= 1.1
    p = um_armar.perfil_oar(lector.Curva((8.0, 8.0), 100.0, x, np.full_like(x, 10.0), v))
    assert np.interp(1.0, p.x, p.oar) == pytest.approx(50.1 / 50.0)


def test_el_centro_de_un_perfil_muy_pequeno_es_su_primer_punto():
    x = np.array([0.0, 0.5, 1.0, 1.5])
    p = um_armar.perfil_oar(lector.Curva((2.0, 2.0), 100.0, x, np.full_like(x, 10.0), np.array([66.0, 50.0, 40.0, 10.0])))
    assert p.oar[1] == 1.0 and p.oar[2] == pytest.approx(0.8)


def test_oar_sale_del_perfil_del_40_con_x_proyectado(datos):
    esperado = oar_a_mano(40.0, 10.0, 5.0)
    assert datos.perfiles(10.0, 5.0) == pytest.approx(esperado)
    r = motor.calcular(datos, E(100.0, 30.0, 30.0, 100.0, 10.0, punto_x=3.0, punto_y=4.0))   # x radial = 5
    assert factor(r, "OAR") == pytest.approx(esperado)


def test_oar_entre_dos_profundidades_es_lineal(datos):
    assert datos.perfiles(15.0, 8.0) == pytest.approx((oar_a_mano(40.0, 10.0, 8.0) + oar_a_mano(40.0, 20.0, 8.0)) / 2)
    assert datos.perfiles(12.0, 8.0) == pytest.approx(0.8 * oar_a_mano(40.0, 10.0, 8.0) + 0.2 * oar_a_mano(40.0, 20.0, 8.0))


def test_sobre_el_eje_el_oar_vale_1_sin_leer_perfiles(datos):
    sin_perfiles = motor.DatosHaz(datos.equipo, datos.energia, datos.ssd0_cm, datos.d0_cm, datos.d0_norm, datos.pdd, datos.of)
    assert factor(motor.calcular(sin_perfiles, E(100.0, 10.0, 10.0, 100.0, 10.0)), "OAR") == 1.0
    assert factor(motor.calcular(sin_perfiles, E(100.0, 10.0, 10.0, 100.0, 10.0, punto_x=0.04)), "OAR") == 1.0    # medio milímetro no es fuera del eje
    with pytest.raises(motor.FaltaDato, match="perfiles"):
        motor.calcular(sin_perfiles, E(100.0, 10.0, 10.0, 100.0, 10.0, punto_x=2.0))


def test_el_oar_no_se_lee_por_encima_del_primer_perfil(datos):
    with pytest.raises(motor.FueraDeTabla, match="profundidad.*a mano"):
        datos.perfiles(1.0, 5.0)


def test_el_oar_a_mano_entra_a_la_cuenta_y_manda(datos):
    r = motor.calcular(datos, E(100.0, 20.0, 20.0, 100.0, 10.0, punto_x=3.0, oar_manual=0.98))
    assert factor(r, "OAR") == 0.98
    assert r.um == pytest.approx(motor.calcular(datos, E(100.0, 20.0, 20.0, 100.0, 10.0)).um / 0.98)


def test_la_bandeja_entra_a_la_cuenta(datos):
    assert motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 10.0, tf=0.95)).um == pytest.approx(motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 10.0)).um / 0.95)


def test_a_30_cm_usa_el_35_porque_falta_el_40_y_no_sale_de_su_campo(datos):
    assert "35 × 35 a 30 [cm]" in datos.perfiles.origen and "40 × 40 a 20 [cm]" in datos.perfiles.origen
    with pytest.raises(motor.FueraDeTabla, match="35 × 35"):
        datos.perfiles(30.0, 18.0)
    with pytest.raises(motor.FueraDeTabla, match="35 × 35"):
        datos.perfiles(25.0, 15.6)
    assert datos.perfiles(25.0, 15.5) == pytest.approx((oar_a_mano(40.0, 20.0, 15.5) + oar_a_mano(35.0, 30.0, 15.5)) / 2)
    assert datos.perfiles(15.0, 18.0) == pytest.approx((oar_a_mano(40.0, 10.0, 18.0) + oar_a_mano(40.0, 20.0, 18.0)) / 2)
    with pytest.raises(motor.FueraDeTabla, match="40 × 40"):
        datos.perfiles(15.0, 18.1)


def test_el_alcance_mira_los_dos_perfiles_que_se_interpolan():
    x, oar = np.arange(0.0, 30.0, 1.0), np.ones(30)
    p = motor.PerfilesOAR((motor.PerfilOAR(5.0, 20.0, x, oar), motor.PerfilOAR(10.0, 40.0, x, oar)), ())
    with pytest.raises(motor.FueraDeTabla, match="20 × 20"):
        p(7.0, 9.0)
    assert p(7.0, 8.0) == 1.0


def test_el_alcance_tampoco_pasa_de_lo_medido():
    """Antes el valor se congelaba al final del perfil (−5.1 %)."""
    x, oar = np.arange(0.0, 12.01, 1.0), np.ones(13)
    p = motor.PerfilesOAR((motor.PerfilOAR(5.0, 40.0, x, oar), motor.PerfilOAR(10.0, 40.0, x, oar)), ())
    with pytest.raises(motor.FueraDeTabla, match="solo sirve"):
        p(7.0, 11.5)   # a 10 cm, 12/1.10 = 10.9
    assert p(7.0, 10.9) == 1.0


def test_oar_lejos_del_eje_avisa(datos):
    assert "TG-71 advierte" not in avisos_de(datos, 100.0, 40.0, 40.0, 100.0, 10.0, punto_x=10.0)
    assert "TG-71 advierte" in avisos_de(datos, 100.0, 40.0, 40.0, 100.0, 10.0, punto_x=10.1)


@pytest.mark.parametrize("campo, punto", [(20.0, 8.0), (15.0, 5.0), (25.0, 10.0), (10.0, 3.0)])
def test_avisa_de_la_perdida_cerca_del_borde_con_lo_que_miden_los_perfiles(datos, campo, punto):
    aviso = avisos_de(datos, 100.0, campo, campo, 100.0, 10.0, punto_x=punto)
    assert "no ve la pérdida" in aviso
    medido = float(re.search(r"cambiaría ([+-][\d.]+) \[%\]", aviso).group(1))
    a_mano = 100 * (oar_a_mano(campo, 10.0, punto) / oar_a_mano(40.0, 10.0, punto) - 1)
    assert medido == pytest.approx(a_mano, abs=0.06) and a_mano < -2


@pytest.mark.parametrize("kw", [dict(x=30.0, y=30.0, punto_x=5.0), dict(x=20.0, y=20.0, punto_x=5.0), dict(x=40.0, y=40.0, punto_x=10.0), dict(x=30.0, y=5.0, punto_x=4.0),
                                dict(x=20.0, y=20.0, centro_x=8.0, punto_x=8.0), dict(x=10.0, y=20.0, centro_x=5.0, punto_x=5.0)])
def test_no_avisa_de_la_perdida_lejos_del_borde(datos, kw):
    """Los tres últimos eran avisos falsos: la distancia que cuenta es la del punto al centro del campo, eje por eje."""
    assert "no ve la pérdida" not in avisos_de(datos, 100.0, ssd=100.0, prof=10.0, **kw)


def test_avisa_de_la_perdida_tambien_en_un_campo_asimetrico(datos):
    """x1 = 0, x2 = 10, punto a 8: a 2 cm del borde, como 10 × 10 con x = 3. Antes no decía nada."""
    assert "no ve la pérdida" in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, 10.0, centro_x=5.0, punto_x=8.0)


def test_avisa_de_la_perdida_a_lo_largo_de_y(datos):
    assert "no ve la pérdida" in avisos_de(datos, 100.0, 30.0, 10.0, 100.0, 10.0, punto_y=3.0)


def test_el_aviso_de_perdida_mide_desde_el_centro_del_campo_tambien_en_y(datos):
    """Con el centro de Y corrido a 2 cm y el punto en 5, el punto está a 3 cm del centro (a 2 del borde): la misma pérdida que con el centro en 0 y el punto en 3,
    y no la de 7 cm. Antes de este caso, solo el signo de X lo fijaba."""
    aviso = avisos_de(datos, 100.0, 30.0, 10.0, 100.0, 10.0, centro_y=2.0, punto_y=5.0)
    medido = float(re.search(r"cambiaría ([+-][\d.]+) \[%\]", aviso).group(1))
    assert medido == pytest.approx(100 * (oar_a_mano(10.0, 10.0, 3.0) / oar_a_mano(40.0, 10.0, 3.0) - 1), abs=0.06)


def test_el_aviso_de_perdida_mira_la_profundidad_fisica(datos):
    a_20 = avisos_de(datos, 100.0, 20.0, 20.0, 100.0, 20.0, punto_x=8.0, prof_ef=10.0)
    medido = float(re.search(r"cambiaría ([+-][\d.]+) \[%\]", a_20).group(1))
    assert medido == pytest.approx(100 * (oar_a_mano(20.0, 20.0, 8.0) / oar_a_mano(40.0, 20.0, 8.0) - 1), abs=0.06)


def test_con_oar_a_mano_o_con_laminas_no_se_estima_la_perdida(datos):
    assert "no ve la pérdida" not in avisos_de(datos, 100.0, 20.0, 20.0, 100.0, 10.0, punto_x=8.0, oar_manual=0.98)
    assert "no ve la pérdida" not in avisos_de(datos, 100.0, 20.0, 20.0, 100.0, 10.0, punto_x=8.0, x_ef=10.0, y_ef=10.0)


# ---------- Cuñas ----------
def test_cuna_de_15_con_su_factor_y_el_aviso(datos):
    """WF(10 × 10; 5 cm) = 0.6623/0.860; a 5 cm, SSD 100, sin más factores."""
    r = motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 5.0, cuna=15))
    assert factor(r, "WF") == pytest.approx(WF15, abs=1e-4)
    assert "falta confirmarlo" in " ".join(r.avisos)


def test_los_betas_salen_del_cociente_de_los_pdd(datos):
    for angulo, lado in ((15, 10.0), (60, 15.0)):
        c = datos.cunas[angulo]
        assert c.betas[list(c.lados_beta).index(lado)] == pytest.approx(beta_a_mano(angulo, lado), rel=1e-6)
    assert datos.cunas[15].prof_max_cm == 30.0


def test_cuna_endurece_con_la_profundidad_y_mas_cuanto_mas_gruesa(datos):
    assert 0 < datos.cunas[15].por_profundidad(20.0, 5.0, 10.0) - 1 < datos.cunas[60].por_profundidad(20.0, 5.0, 10.0) - 1


def test_factor_de_cuna_a_mano_con_campo_y_profundidad(datos):
    """15 × 15 a 20 cm, SSD 100: 0.770 × OF_cuña(15, 15)/OF_abierto(15, 15) × exp[β(15)·15], con las celdas de las tablas."""
    r = motor.calcular(datos, E(100.0, 15.0, 15.0, 100.0, 20.0, cuna=15))
    assert factor(r, "WF") == pytest.approx(WF15 * celda(tabla_real("Standard Wedge - 15"), 15, 15) / celda(tabla_real(), 15, 15) * math.exp(beta_a_mano(15, 15.0) * 15), rel=1e-6)


def test_la_variacion_de_la_cuna_con_la_profundidad_usa_el_campo_de_la_superficie(datos):
    """15 × 15 a SSD 80: r = 12 en la superficie, entre los cuadrados medidos de 10 y de 15."""
    beta = log_entre(10.0, beta_a_mano(15, 10.0), 15.0, beta_a_mano(15, 15.0), 12.0)
    r = motor.calcular(datos, E(100.0, 15.0, 15.0, 80.0, 10.0, cuna=15))
    assert factor(r, "WF") == pytest.approx(WF15 * celda(tabla_real("Standard Wedge - 15"), 15, 15) / celda(tabla_real(), 15, 15) * math.exp(beta * 5), rel=1e-6)


def test_la_cuna_se_lee_con_el_efectivo_sin_proyectar(datos):
    """TG-71: «effective field size is used to determine the physical WF» (ejemplo 2) y «these data are considered independent of SSD» (3.B.1.i)."""
    a_5 = WF15 * celda(tabla_real("Standard Wedge - 15"), 5, 5) / celda(tabla_real(), 5, 5)
    assert factor(motor.calcular(datos, E(100.0, 20.0, 20.0, 100.0, 5.0, x_ef=5.0, y_ef=5.0, cuna=15)), "WF") == pytest.approx(a_5, rel=1e-6)
    assert factor(motor.calcular(datos, E(100.0, 10.0, 10.0, 90.0, 5.0, cuna=15)), "WF") == pytest.approx(WF15, abs=1e-4)


@pytest.mark.parametrize("x, y", [(3.5, 3.5), (40.0, 20.0)])
def test_avisa_si_la_variacion_de_la_cuna_con_la_profundidad_viene_del_campo_mas_cercano(datos, x, y):
    assert "campo medido más cercano" in avisos_de(datos, 100.0, x, y, 100.0, 10.0, cuna=15)


def test_no_avisa_si_la_variacion_de_la_cuna_con_la_profundidad_esta_medida(datos):
    assert "campo medido más cercano" not in avisos_de(datos, 100.0, 15.0, 15.0, 100.0, 10.0, cuna=15)


def test_cuna_left_right_lee_la_tabla_con_y_a_lo_largo_del_gradiente(datos):
    """Plan X = 15, Y = 25 con LEFT: gradiente a lo largo de X, se lee la tabla con Y = 15 y X = 25, en sus celdas."""
    with pytest.raises(motor.FueraDeTabla):
        motor.calcular(datos, E(100.0, 15.0, 25.0, 100.0, 5.0, cuna=15))
    esperado = WF15 * celda(tabla_real("Standard Wedge - 15"), 15, 25) / celda(tabla_real(), 15, 25)
    for orientacion in ("LEFT", "RIGHT"):
        assert factor(motor.calcular(datos, E(100.0, 15.0, 25.0, 100.0, 5.0, cuna=15, cuna_orientacion=orientacion)), "WF") == pytest.approx(esperado, rel=1e-6)
    assert factor(motor.calcular(datos, E(100.0, 25.0, 15.0, 100.0, 5.0, cuna=15, cuna_orientacion="OUT")), "WF") == pytest.approx(esperado, rel=1e-6)


def test_cuna_con_mandibula_mayor_que_la_cuna_no_da_numero(datos):
    with pytest.raises(motor.FueraDeTabla, match="a lo largo de la cuña"):
        motor.calcular(datos, E(100.0, 10.0, 21.0, 90.0, 10.0, cuna=15))         # la proyección no debe esconderlo
    with pytest.raises(motor.FueraDeTabla, match="a lo largo de la cuña"):
        motor.calcular(datos, E(100.0, 25.0, 10.0, 100.0, 10.0, cuna=15, cuna_orientacion="LEFT"))
    assert motor.calcular(datos, E(100.0, 10.0, 20.0, 90.0, 10.0, cuna=15)).um == pytest.approx(motor.calcular(datos, E(100.0, 10.0, 20.0, 90.0, 10.0, wf_manual=factor(motor.calcular(datos, E(100.0, 10.0, 20.0, 90.0, 10.0, cuna=15)), "WF"))).um)


def test_con_cuna_no_se_lee_por_debajo_de_3_cm(datos):
    """Las tablas de cuña dicen «2» donde la abierta dice 2.5: leer entre 2 y 3 sería interpolar con un lado equivocado."""
    with pytest.raises(motor.FueraDeTabla, match=r"por debajo de 3 \[cm\]"):
        motor.calcular(datos, E(100.0, 2.8, 10.0, 100.0, 10.0, cuna=15))
    assert factor(motor.calcular(datos, E(100.0, 3.0, 10.0, 100.0, 5.0, cuna=15)), "WF") == pytest.approx(WF15 * celda(tabla_real("Standard Wedge - 15"), 10, 3) / celda(tabla_real(), 10, 3), rel=1e-6)


def test_aviso_de_valor_a_revisar_en_la_tabla_de_la_cuna(datos):
    aviso = avisos_de(datos, 100.0, 4.0, 6.0, 100.0, 10.0, cuna=15)   # Y = 6, X = 4 está marcado
    assert "cuña de 15°" in aviso and "fuera de tendencia" in aviso
    assert "fuera de tendencia" not in avisos_de(datos, 100.0, 6.0, 4.0, 100.0, 10.0, cuna=15)
    assert "fuera de tendencia" in avisos_de(datos, 100.0, 6.0, 4.0, 100.0, 10.0, cuna=15, cuna_orientacion="LEFT")


def test_cuna_sin_factor_no_se_calcula_y_a_mano_si(datos):
    with pytest.raises(motor.FaltaDato, match="30°"):
        motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 5.0, cuna=30))
    r = motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 5.0, cuna=30, wf_manual=0.63))
    assert r.um == pytest.approx(100 / (0.860 * 0.63), rel=1e-6)


def test_cuna_fuera_del_eje_pide_el_factor_a_mano(datos):
    with pytest.raises(motor.FaltaDato, match="fuera del eje"):
        motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 5.0, cuna=15, punto_x=3.0))
    with pytest.raises(motor.FaltaDato, match="fuera del eje"):
        motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 5.0, cuna=15, punto_y=3.0))
    assert factor(motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 5.0, cuna=15, punto_x=0.04)), "WF") == pytest.approx(WF15, abs=1e-4)   # medio milímetro no es fuera del eje


def test_cuna_que_no_existe_no_se_calcula(datos):
    with pytest.raises(motor.FaltaDato, match="20°"):
        motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 5.0, cuna=20))


# ---------- Lo que no se calcula ----------
@pytest.mark.parametrize("entrada, mensaje", [
    (dict(x=2.5, y=2.5, ssd=90.0, prof=10.0), "tabla de factores"),   # el lado proyectado baja de 2.5
    (dict(x=10.0, y=10.0, ssd=100.0, prof=31.0), "profundidad"),
    (dict(x=40.0, y=40.0, ssd=110.0, prof=10.0), "tabla de factores"),
    (dict(x=45.0, y=10.0, ssd=85.0, prof=10.0), "mandíbulas"),        # la proyección no debe esconderlo
    (dict(x=10.0, y=45.0, ssd=85.0, prof=10.0), "mandíbulas"),
])
def test_fuera_de_tabla_no_se_extrapola(datos, entrada, mensaje):
    with pytest.raises(motor.FueraDeTabla, match=mensaje):
        motor.calcular(datos, E(100.0, **entrada))


@pytest.mark.parametrize("campo", [dict(x=-1.0), dict(y=0.0), dict(ssd=float("nan")), dict(prof=float("inf")), dict(prof=0.0), dict(prof=-1.0), dict(prof_ef=0.0), dict(dosis=True), dict(dosis="100"), dict(x_ef=-1.0, y_ef=5.0),
                                   dict(cuna=15, cuna_orientacion="left"), dict(cuna=15, cuna_orientacion="DIAGONAL"), dict(cuna="15"), dict(cuna=15.0), dict(cuna=True), dict(punto_x=float("nan")), dict(centro_y=float("inf"))])
def test_entradas_imposibles_se_rechazan(datos, campo):
    base = dict(dosis=100.0, x=10.0, y=10.0, ssd=100.0, prof=10.0)
    base.update(campo)
    with pytest.raises(motor.FaltaDato):
        motor.calcular(datos, E(**base))


@pytest.mark.parametrize("campo, valen, no_valen", [
    ("ssd", (60.0, 140.0), (59.9, 140.1, 10.0, 190.0)),
    ("wf_manual", (0.1, 1.1), (0.09, 1.11, 77.0, 0.0)),
    ("tf", (0.5, 1.05), (0.49, 1.06, 95.0, 0.0)),
    ("oar_manual", (0.7, 1.2), (0.69, 1.21, 103.0, 0.0)),
    ("dosis", (0.01, 5000.0), (0.0, -1.0, 5000.1)),
    ("um_planeador", (0.01, 20000.0), (0.0, -1.0, 20000.1)),
])
def test_los_rangos_son_los_del_plan(datos, campo, valen, no_valen):
    base = dict(dosis=100.0, x=10.0, y=10.0, ssd=100.0, prof=10.0)
    for v in valen:
        assert motor.calcular(datos, E(**{**base, campo: v})).um > 0
    for v in no_valen:
        with pytest.raises(motor.FaltaDato):
            motor.calcular(datos, E(**{**base, campo: v}))


@pytest.mark.parametrize("cambio", [dict(d0_norm=float("nan")), dict(d0_norm=-0.86), dict(d0_norm=0.0), dict(sc=((5.0, float("nan")), (20.0, 1.0)))])
def test_el_motor_nunca_devuelve_un_numero_que_no_sirve(datos, cambio):
    base = dict(equipo="x", energia="x", ssd0_cm=100.0, d0_cm=5.0, d0_norm=0.86, pdd=datos.pdd, of=datos.of, sc=motor.SC_MUESTRA_TG71)
    with pytest.raises(motor.NoCalculable, match="número válido"):
        motor.calcular(motor.DatosHaz(**{**base, **cambio}), E(100.0, 15.0, 15.0, 90.0, 10.0))


# ---------- Avisos ----------
def test_avisos_de_build_up_campo_pequeno_alargado_ssd_y_celda(datos):
    assert "dmax" in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, 1.0)
    assert "dmax" not in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, 10.0)
    assert "Campo pequeño" in avisos_de(datos, 100.0, 3.0, 3.0, 100.0, 10.0)
    assert "Campo pequeño" in avisos_de(datos, 100.0, 4.4, 4.4, 90.0, 10.0)        # 3.96 en la superficie
    assert "Campo pequeño" not in avisos_de(datos, 100.0, 4.0, 4.0, 110.0, 10.0)   # 4.4 en la superficie
    assert "alargado" in avisos_de(datos, 100.0, 5.0, 20.0, 100.0, 10.0)
    assert "alargado" not in avisos_de(datos, 100.0, 5.0, 19.9, 100.0, 10.0)
    assert "alargado" in avisos_de(datos, 100.0, 5.0, 40.0, 100.0, 10.0)                # 8:1, no solo la frontera de 4:1
    assert "Campo pequeño" not in avisos_de(datos, 100.0, 4.0, 4.0, 100.0, 10.0)       # 4.0 en la superficie justo: no es menor que 4
    dmax = float(datos.pdd.z_cm[int(np.argmax(datos.pdd.m[list(datos.pdd.lados).index(10.0)]))])   # 1.4 cm: el nodo donde el PDD de 10 × 10 vale 100
    assert "dmax" in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, dmax - 0.1) and "dmax" not in avisos_de(datos, 100.0, 10.0, 10.0, 100.0, dmax)   # justo en dmax no avisa
    assert "alargado" not in avisos_de(datos, 100.0, 5.0, 30.0, 100.0, 10.0, x_ef=5.0, y_ef=5.0)
    assert "alargado" in avisos_de(datos, 100.0, 30.0, 30.0, 100.0, 10.0, x_ef=5.0, y_ef=20.0)
    assert "SSD de 75" in avisos_de(datos, 100.0, 10.0, 10.0, 75.0, 10.0)
    assert "SSD de 79.9" in avisos_de(datos, 100.0, 10.0, 10.0, 79.9, 10.0)
    assert "SSD de" not in avisos_de(datos, 100.0, 10.0, 10.0, 80.0, 10.0)
    assert "SSD de" not in avisos_de(datos, 100.0, 10.0, 10.0, 120.0, 10.0)
    assert "SSD de 120.1" in avisos_de(datos, 100.0, 10.0, 10.0, 120.1, 10.0)


def test_aviso_de_celda_de_la_abierta_con_la_lectura(datos):
    assert "fuera de tendencia" in avisos_de(datos, 100.0, 25.0, 30.0, 100.0, 10.0)        # Y = 30, X = 25
    assert "fuera de tendencia" in avisos_de(datos, 100.0, 27.0, 28.0, 100.0, 10.0)        # la rodean sus vecinas
    assert "fuera de tendencia" not in avisos_de(datos, 100.0, 30.0, 25.0, 100.0, 10.0)    # X e Y cruzados no es esa celda
    assert "fuera de tendencia" not in avisos_de(datos, 100.0, 30.0, 30.0, 100.0, 10.0)    # cae justo en su celda, no pesa la vecina
    assert "fuera de tendencia" not in avisos_de(datos, 100.0, 25.0, 30.0, 80.0, 10.0)     # se lee en 20.5 × 24.5: esa celda no pesa


# ---------- Tolerancia ----------
@pytest.mark.parametrize("error, estado", [(0.0, "Dentro"), (2.0, "Dentro"), (-2.0, "Dentro"), (2.01, "Revisar"), (-3.0, "Revisar"), (3.01, "Fuera"), (-5.0, "Fuera")])
def test_tolerancia(error, estado):
    assert motor.estado_de(error) == estado


def test_error_contra_eclipse(datos):
    um = 200 / 0.662
    r = motor.calcular(datos, E(200.0, 10.0, 10.0, 100.0, 10.0, um_planeador=um / 1.025))
    assert r.error_pct == pytest.approx(2.5, abs=0.01) and r.estado == "Revisar"
    assert motor.calcular(datos, E(200.0, 10.0, 10.0, 100.0, 10.0, um_planeador=um / 1.025), 3.0, 4.0).estado == "Dentro"
    assert motor.calcular(datos, E(200.0, 10.0, 10.0, 100.0, 10.0, um_planeador=um / 1.025), 1.0, 2.0).estado == "Fuera"
    assert motor.calcular(datos, E(200.0, 10.0, 10.0, 100.0, 10.0)).estado is None


# ---------- UM.2: lo que arrastran UM.1 y UM.1b, y las barreras nuevas del armado (UM2-D1 a UM2-D4) ----------
def _una_vez(texto_de_archivo, viejo, nuevo, cual=1):
    """El texto con la `cual`-ésima aparición de `viejo` cambiada por `nuevo` (una sola)."""
    partes = texto_de_archivo.split(viejo)
    assert len(partes) > cual, (viejo, len(partes) - 1)
    return viejo.join(partes[:cual]) + nuevo + viejo.join(partes[cual:])


def test_el_perfil_va_a_la_profundidad_de_sus_puntos_y_no_a_la_de_su_cabecera(datos):
    """Los perfiles «a 1.4 cm» dicen `%DPTH 014` y sus puntos están en z = 13.5 mm: el armado usa la z de los puntos (UM.1, H17 «Menores»)."""
    t = texto(PERFILES)
    assert "%DPTH 014" in t and "<+002.5 +000.0 +013.5 +099.521>" in t and "+014.0 +" not in t
    assert [p.prof for p in datos.perfiles.grandes] == [1.35, 5.0, 10.0, 20.0, 30.0]
    assert sorted({p.prof for p in datos.perfiles.todos}) == [1.35, 5.0, 10.0, 20.0, 30.0]


def test_un_perfil_con_puntos_a_dos_profundidades_se_rechaza():
    """UM2-D2: un perfil se mide a una sola profundidad; se admite medio milímetro (en los 659 perfiles reales la diferencia es 0; el archivo da z en [mm] con un decimal)."""
    x = np.arange(0.0, 20.0, 0.5)
    z = np.full_like(x, 10.0)
    assert um_armar.perfil_oar(lector.Curva((40.0, 40.0), 100.0, x, z + np.where(x == 5.0, 0.04, 0.0), np.full_like(x, 50.0))).prof == 10.0
    with pytest.raises(lector.ArchivoNoReconocido, match="profundidades distintas"):
        um_armar.perfil_oar(lector.Curva((40.0, 40.0), 100.0, x, z + np.where(x == 5.0, 0.06, 0.0), np.full_like(x, 50.0)))


def test_un_punto_del_perfil_a_otra_profundidad_impide_guardar(archivos):
    perfiles = es_de(archivos, "Open Field", "data: OPP_processed")
    malo = perfiles.replace("<+002.5 +000.0 +013.5 +099.521>", "<+002.5 +000.0 +018.5 +099.521>")
    assert malo != perfiles
    r = um_armar.revisar_archivos([(f"a{i}.txt", t) for i, t in enumerate(cambiar(archivos, perfiles, malo))], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert any("profundidades distintas" in p for p in r.problemas)


@pytest.mark.parametrize("viejo, nuevo", [("%FLSZ 350*350", "%FLSZ  50*350"), ("%FLSZ 350*350", "%FLSZ \t50*350"), ("%FLSZ 150*150", "%FLSZ 150*250"),
                                          ("%FLSZ 400*400", "%FLSZ 400*300")])
def test_un_perfil_abierto_que_no_es_cuadrado_se_rechaza(archivos, viejo, nuevo):
    """UM2-D1: antes se saltaba en silencio. Dañar el 35 × 35 de 30 cm (« 50*350», el 1 sustituido por un blanco) quitaba el perfil grande de esa
    profundidad y el OAR más allá de 20 cm se leía en el 30 × 30."""
    perfiles = es_de(archivos, "Open Field", "data: OPP_processed")
    malo = _una_vez(perfiles, viejo, nuevo, cual=5 if "350" in viejo else 1)
    with pytest.raises(lector.ArchivoNoReconocido, match="no es cuadrado"):
        um_armar.datos_haz(cambiar(archivos, perfiles, malo), "Clinac 600", "6 MV", d0_dmax=1.0)
    r = um_armar.revisar_archivos([(f"a{i}.txt", t) for i, t in enumerate(cambiar(archivos, perfiles, malo))], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert any("no es cuadrado" in p for p in r.problemas)


def test_dos_perfiles_del_mismo_campo_a_la_misma_profundidad_se_rechazan(archivos):
    """UM2-D3: antes se elegía uno en silencio, y en la estimación junto al borde dos perfiles a la misma profundidad dividían por cero."""
    perfiles = es_de(archivos, "Open Field", "data: OPP_processed")
    with pytest.raises(lector.ArchivoNoReconocido, match="dos perfiles del campo de 25 × 25"):
        um_armar.datos_haz(cambiar(archivos, perfiles, _una_vez(perfiles, "%FLSZ 300*300", "%FLSZ 250*250")), "Clinac 600", "6 MV", d0_dmax=1.0)


@pytest.mark.parametrize("nuevo", ["%FLSZ  50*150", "%FLSZ \t50*150", "%FLSZ 250*150", "%FLSZ 150*140", "%FLSZ 400*150"])
def test_un_pdd_de_cuna_que_no_es_cuadrado_ni_su_campo_entero_se_rechaza(archivos, nuevo):
    """UM2-D1 (el hallazgo del cierre de UM.1b): «%FLSZ 150*150» de la cuña de 30° con el 1 sustituido por un blanco se leía 5 × 15 y el 15 × 15
    salía del ajuste en silencio (de −0.166 % a +0.033 % en las UM de esa cuña). Solo el campo entero de la tabla (40 × 20) puede no ser cuadrado."""
    wdd = es_de(archivos, "Standard Wedge - 30", "data: WDD\n")
    with pytest.raises(lector.ArchivoNoReconocido, match="ni el campo entero de su tabla"):
        um_armar.datos_haz(cambiar(archivos, wdd, wdd.replace("%FLSZ 150*150", nuevo)), "Clinac 600", "6 MV", d0_dmax=1.0)


def test_una_tabla_de_cuna_cortada_al_final_de_una_fila_ya_no_se_acepta(archivos):
    """Una tabla de factores no tiene marca de final: cortada justo al final de una fila se lee como una tabla más pequeña. Con UM2-D1 la de una cuña ya no
    pasa, porque su PDD del campo entero (40 × 20) deja de ser el de la tabla (4 de los 3600 cortes de `scripts/h_azar.py`; la referencia los aceptaba)."""
    tabla = es_de(archivos, "Standard Wedge - 15", "data: OutputFactorTable")
    cortada = tabla[:tabla.index("\n15, ") + 1]
    assert lector.leer_tabla_of(cortada).y.tolist() == [2, 3, 4, 5, 6, 10]
    with pytest.raises(lector.ArchivoNoReconocido, match=r"ni el campo entero de su tabla \(40 × 10 \[cm\]\)"):
        um_armar.datos_haz(cambiar(archivos, tabla, cortada), "Clinac 600", "6 MV", d0_dmax=1.0)


@pytest.mark.parametrize("hasta", ["\n35, ", "\n40, "])
def test_una_tabla_abierta_cortada_al_final_de_una_fila_se_rechaza(archivos, hasta):
    """UM2-D5: la tabla abierta cortada al final de la fila de 30 cm se leía como una tabla de 30 cm y la curva de Sc estimada se quedaba en 30 cm: 9 de 252
    casos con otras UM, de +0.30 a +0.47 % (`logs/UM2_prevuelo/efecto_en_um.log`). Ahora debe llegar al mismo lado en X y en Y (40 cm en el 600C y en las 10 carpetas
    de fotones del paquete de Varian); una tabla que llega a 35 en los dos sigue valiendo (`test_una_tabla_de_6_mv_que_no_llega_a_38_cm_tambien_se_estima`)."""
    tabla = es_de(archivos, "Open Field", "data: OutputFactorTable")
    cortada = tabla[:tabla.index(hasta) + 1]
    assert lector.leer_tabla_of(cortada).y[-1] == (30.0 if "35" in hasta else 35.0)
    with pytest.raises(lector.ArchivoNoReconocido, match="parece cortada al final de una fila"):
        um_armar.datos_haz(cambiar(archivos, tabla, cortada), "Clinac 600", "6 MV", d0_dmax=1.0)
    lineas = tabla.split("\n")
    i = next(k for k, l in enumerate(lineas) if l.replace(" ", "").startswith("2.5,3"))
    sin_la_columna_de_40 = "\n".join(lineas[:i] + [", ".join(l.split(", ")[:-1]) if l else l for l in lineas[i:]])
    assert lector.leer_tabla_of(sin_la_columna_de_40).x[-1] == 35.0 and lector.leer_tabla_of(sin_la_columna_de_40).y[-1] == 40.0
    with pytest.raises(lector.ArchivoNoReconocido, match="parece cortada al final de una fila"):
        um_armar.datos_haz(cambiar(archivos, tabla, sin_la_columna_de_40), "Clinac 600", "6 MV", d0_dmax=1.0)


def test_el_campo_entero_de_cada_cuna_no_entra_en_el_ajuste(datos):
    """El 600C mide el PDD con cuña también en 40 × 20 (40 × 15 la de 60°), el campo entero de su tabla: se acepta y no entra en β."""
    for angulo, campo, cuadrados in ((15, "400*200", [4, 10, 15, 20]), (30, "400*200", [4, 10, 15, 20]), (45, "400*200", [4, 10, 15, 20]), (60, "400*150", [4, 10, 15])):
        assert f"%FLSZ {campo}" in texto(f"CLINAC 600C_Standard Wedge - {angulo}_Measured Wedge Depth Doses.txt")
        assert datos.cunas[angulo].lados_beta.tolist() == cuadrados
        assert (float(datos.cunas[angulo].tabla.x[-1]), float(datos.cunas[angulo].tabla.y[-1])) == tuple(float(v) / 10 for v in campo.split("*"))


def test_dos_pdd_de_cuna_del_mismo_cuadrado_se_rechazan(archivos):
    wdd = es_de(archivos, "Standard Wedge - 30", "data: WDD\n")
    with pytest.raises(lector.ArchivoNoReconocido, match="dos PDD con cuña del campo de 10 × 10"):
        um_armar.datos_haz(cambiar(archivos, wdd, wdd.replace("%FLSZ 150*150", "%FLSZ 100*100")), "Clinac 600", "6 MV", d0_dmax=1.0)


def test_un_cuadrado_de_cuna_sin_pdd_abierto_se_salta_y_sin_ninguno_se_rechaza(archivos):
    """El paquete de Varian mide 22 × 22 y 27 × 27 solo con cuña: ese cuadrado no entra en β y no impide cargar. Si no queda ninguno, no hay β."""
    wdd = es_de(archivos, "Standard Wedge - 30", "data: WDD\n")
    d = um_armar.datos_haz(cambiar(archivos, wdd, wdd.replace("%FLSZ 150*150", "%FLSZ 220*220")), "Clinac 600", "6 MV", d0_dmax=1.0)
    assert d.cunas[30].lados_beta.tolist() == [4, 10, 20]
    sin_abiertos = wdd
    for viejo, nuevo in (("%FLSZ 040*040", "%FLSZ 220*220"), ("%FLSZ 100*100", "%FLSZ 270*270"), ("%FLSZ 150*150", "%FLSZ 330*330"), ("%FLSZ 200*200", "%FLSZ 370*370")):
        sin_abiertos = sin_abiertos.replace(viejo, nuevo)
    with pytest.raises(lector.ArchivoNoReconocido, match="ningún cuadrado medido también sin cuña"):
        um_armar.datos_haz(cambiar(archivos, wdd, sin_abiertos), "Clinac 600", "6 MV", d0_dmax=1.0)


def test_un_pdd_o_un_perfil_sin_ssd_se_rechaza_diciendolo(archivos):
    """UM.1: una `Curva` sin `%SSD` queda con `ssd_cm = None`; el armado no la toma por otra SSD."""
    for marca, que in (("data: OPD\n", "una sola SSD"), ("data: OPP_processed", "no dice su SSD"), ("data: WDD\n", "no dice su SSD")):
        original = es_de(archivos, "Standard Wedge - 30" if "WDD" in marca else "Open Field", marca)
        sin_ssd = original.replace("%SSD 1000\n", "", 1)
        assert sin_ssd != original
        with pytest.raises(lector.ArchivoNoReconocido, match=que):
            um_armar.datos_haz(cambiar(archivos, original, sin_ssd), "Clinac 600", "6 MV", d0_dmax=1.0)


def test_un_archivo_que_el_calculo_no_lee_se_ignora_antes_de_leer_sus_curvas(archivos):
    """UM.1b rechaza una curva con y distinta de 0 (UM1b-D1), y el paquete de Varian trae 7 perfiles de cuña así. Un archivo que el cálculo no lee se
    decide por su identidad, sin leer sus curvas: no impide guardar ni da un motivo."""
    perfil_cuna = es_de(archivos, "Standard Wedge - 15", "data: WDP")
    fuera_de_y = perfil_cuna.replace("<-131.0 +000.0 +013.5 +008.200>", "<-131.0 +010.0 +013.5 +008.200>")
    with pytest.raises(lector.ArchivoNoReconocido, match="fuera de y = 0"):
        lector.leer_curvas(fuera_de_y)
    pares = [(f"a{i}.txt", t) for i, t in enumerate(cambiar(archivos, perfil_cuna, fuera_de_y))]
    r = um_armar.revisar_archivos(pares, "Clinac 600", "6 MV", d0_dmax=1.0)
    nombre = next(n for n, t in pares if t is fuera_de_y)
    assert not r.problemas and nombre in r.ignorados and len(r.usados) == 12 and len(r.ignorados) == 10
    assert not any(nombre in a for a in r.avisos)


@pytest.mark.parametrize("de, a, que", [("add on: Open Field - 00", "add on: EDW 60", "no se reconoce como una cuña física"),
                                       ("add on: Open Field - 00", "add on: Standard Wedge - 15", "el cálculo no lee «OPD» de «Standard Wedge - 15»")])
def test_lo_que_el_calculo_no_lee_se_ignora_aunque_sea_de_otra_maquina(archivos, de, a, que):
    """UM2-D4: antes contaba como usado (y el resumen decía a la vez que «no se usa»), y una máquina distinta impedía guardar."""
    copia = texto("CLINAC 600C_Open Field - 00_Calculated Depth Doses.txt").replace("data: OPD_calculated", "data: OPD").replace(de, a).replace("machine: 600C, 6X", "machine: iX, 6X")
    pares = [(f"a{i}.txt", t) for i, t in enumerate(archivos)] + [("otro.txt", copia)]
    r = um_armar.revisar_archivos(pares, "Clinac 600", "6 MV", d0_dmax=1.0)
    assert not r.problemas and "otro.txt" in r.ignorados and "otro.txt" not in r.usados and len(r.usados) == 12
    assert any(a.startswith("otro.txt: ") and que in a for a in r.avisos)


def test_un_pdd_de_cuna_del_campo_abierto_se_ignora_y_se_dice(archivos):
    """Un PDD con cuña que dice ser del campo abierto no lo lee el cálculo: se ignora y se dice (UM2-D4)."""
    wdd = es_de(archivos, "Standard Wedge - 30", "data: WDD\n")
    del_abierto = wdd.replace("add on: Standard Wedge - 30", "add on: Open Field - 00")
    r = um_armar.revisar_archivos([(f"a{i}.txt", t) for i, t in enumerate(archivos)] + [("abierto.txt", del_abierto)], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert "abierto.txt" in r.ignorados and any("el cálculo no lee «WDD» de «Open Field - 00»" in a for a in r.avisos) and not r.problemas



# ---------- Los huecos que dejó ver el barrido de mutantes automáticos del armado (pre-vuelo de UM.2; scripts/um2_mutantes_automaticos.py) ----------
def _pdd_curvas():
    return lector.leer_curvas(texto(PDD_ABIERTO))


def _con(c, **cambios):
    """La misma `Curva` con algunos campos cambiados."""
    return lector.Curva(**{**{k: getattr(c, k) for k in ("campo_cm", "ssd_cm", "x_cm", "z_cm", "valor")}, **cambios})


def test_faltan_el_pdd_o_la_tabla_abiertos_o_no_hay_archivos(archivos):
    for marca in ("data: OPD\n", "data: OutputFactorTable"):
        sin = [t for t in archivos if not ("add on: Open Field" in t and marca in t)]
        with pytest.raises(lector.ArchivoNoReconocido, match="faltan el PDD medido o la tabla de factores del campo abierto"):
            um_armar.datos_haz(sin, "Clinac 600", "6 MV", d0_dmax=1.0)
    with pytest.raises(lector.ArchivoNoReconocido, match="faltan el PDD medido"):
        um_armar.datos_haz([], "Clinac 600", "6 MV", d0_dmax=1.0)
    with pytest.raises(lector.ArchivoNoReconocido, match="dos archivos distintos para Open Field - 00, OPD"):
        pdd = es_de(archivos, "data: OPD\n")
        um_armar.datos_haz(archivos + [pdd.replace("+045.300", "+045.400", 1)], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert um_armar.datos_haz(archivos + [es_de(archivos, "data: OPD\n")], "Clinac 600", "6 MV", d0_dmax=1.0).pdd.lados.tolist() == [2.5, 3, 4, 5, 6, 10, 15, 20, 25, 30, 35, 40]


def test_familia_pdd_mira_cada_curva_y_no_depende_del_orden():
    """Cada comprobación de `familia_pdd` mira TODAS las curvas (la primera y la última también) y el orden de llegada no cambia la familia."""
    curvas = _pdd_curvas()
    base = um_armar.familia_pdd(curvas)[0]
    revuelta = um_armar.familia_pdd(list(reversed(curvas)))[0]
    assert revuelta.lados.tolist() == base.lados.tolist() and np.array_equal(revuelta.m, base.m) and np.array_equal(revuelta.z_cm, base.z_cm)
    for k in (0, -1):
        otra = list(curvas)
        for cambio, motivo in ((dict(campo_cm=(curvas[k].campo_cm[0], curvas[k].campo_cm[0] * 0.8)), "no es cuadrado"),
                               (dict(campo_cm=(curvas[k].campo_cm[0], curvas[k].campo_cm[0] * 1.2)), "no es cuadrado"),
                               (dict(valor=np.where(np.arange(len(curvas[k].valor)) == 7, -1.0, curvas[k].valor)), "nulo"),
                               (dict(valor=curvas[k].valor * 1.00502), "máximo"), (dict(valor=curvas[k].valor * 0.99498), "máximo"),
                               (dict(z_cm=curvas[k].z_cm[:-1], valor=curvas[k].valor[:-1]), "rejilla"), (dict(ssd_cm=None), "una sola SSD")):
            otra[k] = _con(curvas[k], **cambio)
            with pytest.raises(lector.ArchivoNoReconocido, match=motivo):
                um_armar.familia_pdd(otra)
        otra[k] = _con(curvas[k], valor=np.where(curvas[k].valor == curvas[k].valor.max(), 100.5, curvas[k].valor))      # máximo 100.5: en el límite se acepta
        assert um_armar.familia_pdd(otra)[0].m.max() == pytest.approx(100.5)
    for z in (np.concatenate(([0.0], curvas[0].z_cm[:-1])), curvas[0].z_cm[::-1].copy()):      # la rejilla común repite un punto o va al revés
        with pytest.raises(lector.ArchivoNoReconocido, match="rejilla"):
            um_armar.familia_pdd([_con(c, z_cm=z) for c in curvas])
    with pytest.raises(lector.ArchivoNoReconocido, match="una sola SSD"):
        um_armar.familia_pdd([_con(c, ssd_cm=None) for c in curvas])
    with pytest.raises(lector.ArchivoNoReconocido, match="una sola SSD"):
        um_armar.familia_pdd([])


def test_el_perfil_y_sus_bordes():
    """`perfil_oar`: medio perfil (lo de x < 0 no cuenta), la tolerancia de la profundidad justo en su límite, el ajuste del centro con dos puntos o con el
    respaldo, y el centro positivo pero pequeño."""
    x = np.arange(0.0, 20.01, 0.5)
    v = 50.0 - 0.01 * x ** 2
    medio = um_armar.perfil_oar(lector.Curva((40.0, 40.0), 100.0, x, np.full_like(x, 5.0), v))
    entero = um_armar.perfil_oar(lector.Curva((40.0, 40.0), 100.0, np.concatenate((-x[::-1], x[1:])), np.full(2 * len(x) - 1, 5.0), np.concatenate((v[::-1], v[1:]))))
    assert np.array_equal(entero.x, medio.x) and np.allclose(entero.oar, medio.oar)
    for dz, pasa in ((0.05, True), (0.0498, True), (0.0502, False)):        # z = 0 y z = dz: la diferencia es exactamente dz
        curva = lector.Curva((40.0, 40.0), 100.0, x, np.where(x == 5.0, dz, 0.0), v)
        if pasa:
            assert um_armar.perfil_oar(curva).prof == 0.0
        else:
            with pytest.raises(lector.ArchivoNoReconocido, match="profundidades distintas"):
                um_armar.perfil_oar(curva)
    dos = np.array([0.0, 0.5, 1.0, 2.0, 3.0])                                 # lado 4: el centro se ajusta hasta 1 cm, con dos puntos
    p = um_armar.perfil_oar(lector.Curva((4.0, 4.0), 100.0, dos, np.full(5, 5.0), np.array([50.5, 50.0, 49.0, 45.0, 40.0])))
    assert p.oar[1] == pytest.approx(50.0 / (50.0 + 1.0 / 3.0))
    uno = um_armar.perfil_oar(lector.Curva((2.0, 2.0), 100.0, np.array([0.0, 0.5, 1.0]), np.full(3, 5.0), np.array([50.5, 50.0, 49.0])))
    assert uno.oar[1] == 1.0                                                 # un solo punto cerca del eje: se normaliza con él
    ocho = um_armar.perfil_oar(lector.Curva((8.0, 8.0), 100.0, np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5]), np.full(6, 5.0), np.array([60, 50.0, 49.9, 49.6, 48.0, 47.0])))
    xs, vs = np.array([0.5, 1.0, 1.5, 2.0]), np.array([50.0, 49.9, 49.6, 48.0])
    assert ocho.oar[1] == pytest.approx(50.0 / np.polyfit(xs ** 2, vs, 1)[1])   # hasta lado/4 = 2 cm, incluido
    largo = um_armar.perfil_oar(lector.Curva((40.0, 40.0), 100.0, np.array([0.0, 1.0, 2.0, 3.0, 3.02, 5.0]), np.full(6, 5.0), np.array([60, 50.0, 49.9, 49.6, 40.0, 45.0])))
    xs, vs = np.array([1.0, 2.0, 3.0]), np.array([50.0, 49.9, 49.6])
    assert largo.oar[1] == pytest.approx(50.0 / np.polyfit(xs ** 2, vs, 1)[1])  # hasta 3 cm, no 3.02
    assert um_armar.perfil_oar(lector.Curva((40.0, 40.0), 100.0, x, np.full_like(x, 5.0), np.full_like(x, 0.5))).oar[1] == pytest.approx(1.0)   # un centro de 0.5 vale
    with pytest.raises(lector.ArchivoNoReconocido, match="nulo"):
        um_armar.perfil_oar(lector.Curva((40.0, 40.0), 100.0, x, np.full_like(x, 5.0), np.full_like(x, -50.0)))


def test_los_perfiles_grandes_van_por_profundidad_y_cuentan_desde_la_mitad_del_mayor():
    x = np.arange(0.0, 30.0, 0.5)
    curva = lambda lado, prof: lector.Curva((lado, lado), 100.0, x, np.full_like(x, prof), np.full_like(x, 50.0))
    assert [q.prof for q in um_armar.perfiles_oar([curva(40.0, 10.0), curva(40.0, 5.0), curva(20.0, 30.0)]).grandes] == [5.0, 10.0, 30.0]
    assert [q.prof for q in um_armar.perfiles_oar([curva(40.0, 10.0), curva(40.0, 5.0), curva(15.0, 30.0)]).grandes] == [5.0, 10.0]


def _wdd(lado, z, valor=None, ssd=100.0):
    return lector.Curva((lado, lado), ssd, np.zeros_like(z), z, np.linspace(100.0, 40.0, len(z)) if valor is None else valor)


@pytest.mark.parametrize("z, pasa", [(np.linspace(5.0, 10.0, 51), True), (np.arange(5.0, 9.9701, 0.01), False), (np.arange(5.1, 12.0, 0.1), False),
                                     (np.concatenate(([5.0, 5.0], np.arange(5.1, 12.0, 0.1))), False)])
def test_el_tramo_del_pdd_con_cuna_en_sus_limites(datos, z, pasa):
    """De d0 = 5 cm a 10 cm por lo menos, en orden creciente: justo 10 cm se acepta; 9.97 cm, empezar en 5.1 o repetir una profundidad, no."""
    if pasa:
        assert um_armar.betas_de_cuna([_wdd(10.0, z)], datos.pdd, 5.0, 100.0, (40.0, 20.0))[2] == pytest.approx(10.0)
    else:
        with pytest.raises(lector.ArchivoNoReconocido, match="debe cubrir|creciente"):
            um_armar.betas_de_cuna([_wdd(10.0, z)], datos.pdd, 5.0, 100.0, (40.0, 20.0))


def test_el_pdd_con_cuna_otros_bordes(datos):
    z = np.arange(50, 150) / 10      # como el lector: [mm] / 10
    for valor in (np.where(np.arange(len(z)) == 5, -1.0, 80.0), np.where(np.arange(len(z)) == 5, 0.0, 80.0)):      # z = 5.5, una de las profundidades del ajuste
        with pytest.raises(lector.ArchivoNoReconocido, match="nulo"):
            um_armar.betas_de_cuna([_wdd(10.0, z, valor)], datos.pdd, 5.0, 100.0, (40.0, 20.0))
    assert um_armar.betas_de_cuna([_wdd(10.0, z, np.full_like(z, 0.5))], datos.pdd, 5.0, 100.0, (40.0, 20.0))[0].tolist() == [10.0]
    for ssd in (90.0, 110.0):
        with pytest.raises(lector.ArchivoNoReconocido, match="no se pueden dividir"):
            um_armar.betas_de_cuna([_wdd(10.0, z, ssd=ssd)], datos.pdd, 5.0, 100.0, (40.0, 20.0))


@pytest.mark.parametrize("viejo, nuevo", [("%DetectorDepth 50", "%DetectorDepth 30"), ("%SourcePhantomDistance 1000", "%SourcePhantomDistance 1050")])
def test_tabla_de_cuna_en_otras_condiciones_tambien_por_el_otro_lado(archivos, viejo, nuevo):
    tabla = es_de(archivos, "Standard Wedge - 30", "data: OutputFactorTable")
    with pytest.raises(lector.ArchivoNoReconocido, match="mismas condiciones"):
        um_armar.datos_haz(cambiar(archivos, tabla, tabla.replace(viejo, nuevo)), "Clinac 600", "6 MV", d0_dmax=1.0)


def test_d0_en_dmax_con_la_tabla_a_una_ssd_mayor_pide_las_condiciones_de_la_tabla(archivos):
    otra = [a.replace("%SourcePhantomDistance 1000", "%SourcePhantomDistance 1050") for a in archivos]
    with pytest.raises(motor.FaltaDato, match="condiciones de la tabla"):
        um_armar.datos_haz(otra, "Clinac 600", "6 MV", d0_dmax=1.0)
    abiertos = [a for a in archivos if "add on: Open Field" in a]      # sin cuñas: el WF de 15° deducido con 0.497 también se saldría de su rango
    with pytest.raises(motor.FaltaDato, match=r"D'0 no es un valor posible \(de 0.5 a 1.5 \[cGy/UM\]\): 0.497"):
        um_armar.datos_haz(abiertos, "Clinac 600", "6 MV", d0_dmax=0.497)


def _transpuesta(tabla_texto):
    """La misma tabla con filas y columnas intercambiadas (X pasa a ser el lado corto, como en una cuña LEFT o RIGHT)."""
    lineas = tabla_texto.split("\n")
    i = next(k for k, l in enumerate(lineas) if l.startswith("2, "))
    filas = [[v.strip() for v in l.split(",")] for l in lineas[i:] if l.strip()]
    ys, cuerpo = [f[0] for f in filas[1:]], [f[1:] for f in filas[1:]]
    nuevas = [", ".join(ys)] + [", ".join([x] + [cuerpo[j][k] for j in range(len(ys))]) for k, x in enumerate(filas[0])]
    return "\n".join(lineas[:i] + nuevas) + "\n"


def test_una_tabla_de_cuna_con_x_corto_lleva_el_gradiente_en_x(archivos):
    """El eje del gradiente es el lado corto de la tabla; con X corto, «X», y si el name.data dice IN, no cuadran. Las cuatro del 600C, «Y»."""
    assert {a: c.gradiente_en for a, c in um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={30: 0.6}).cunas.items()} == {15: "Y", 30: "Y", 45: "Y", 60: "Y"}
    tabla, wdd = es_de(archivos, "Standard Wedge - 30", "data: OutputFactorTable"), es_de(archivos, "Standard Wedge - 30", "data: WDD\n")
    girados = cambiar(cambiar(archivos, tabla, _transpuesta(tabla)), wdd, wdd.replace("%FLSZ 400*200", "%FLSZ 200*400"))
    d = um_armar.datos_haz(girados, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={30: 0.6})
    assert (d.cunas[30].gradiente_en, d.cunas[30].tabla.x[-1], d.cunas[30].tabla.y[-1]) == ("X", 20.0, 40.0)
    tabla15, wdd15, nd = es_de(archivos, "Standard Wedge - 15", "data: OutputFactorTable"), es_de(archivos, "Standard Wedge - 15", "data: WDD\n"), es_de(archivos, "data: WedgeParameters")
    con_in = cambiar(cambiar(archivos, tabla15, _transpuesta(tabla15)), wdd15, wdd15.replace("%FLSZ 400*200", "%FLSZ 200*400"))
    with pytest.raises(lector.ArchivoNoReconocido, match="no cuadran"):
        um_armar.datos_haz(con_in, "Clinac 600", "6 MV", d0_dmax=1.0)
    con_left = cambiar(con_in, nd, nd.replace("(IN/OUT/LEFT/RIGHT)[]:IN", "(IN/OUT/LEFT/RIGHT)[]:LEFT"))
    assert um_armar.datos_haz(con_left, "Clinac 600", "6 MV", d0_dmax=1.0).cunas[15].gradiente_en == "X"


def test_una_tabla_de_otro_accesorio_con_su_pdd_no_es_una_cuna(archivos):
    tabla, wdd = es_de(archivos, "Standard Wedge - 30", "data: OutputFactorTable"), es_de(archivos, "Standard Wedge - 30", "data: WDD\n")
    extra = [t.replace("add on: Standard Wedge - 30", "add on: EDW 60") for t in (tabla, wdd)]
    assert sorted(um_armar.datos_haz(archivos + extra, "Clinac 600", "6 MV", d0_dmax=1.0).cunas) == [15, 30, 45, 60]


def test_curva_de_sc_en_sus_limites():
    assert um_armar.curva_de_sc([(4.0, 0.5), (10.0, 1.0), (40.0, 1.5)]) == ((4.0, 0.5), (10.0, 1.0), (40.0, 1.5))
    assert um_armar.curva_de_sc([(0.5, 0.9), (10.0, 1.0)])[0] == (0.5, 0.9)
    for mala in ([(4.0, 0.497), (10.0, 1.0)], [(4.0, 1.0), (10.0, 1.503)], [(0.0, 0.9), (10.0, 1.0)], [(4.0, 0.9), (10.0, 1.0), (40.0, 1.6)]):
        with pytest.raises(motor.FaltaDato, match="curva de Sc"):
            um_armar.curva_de_sc(mala)


def test_sc_del_haz_en_otra_energia_o_profundidad_y_en_tablas_de_otros_lados():
    lados = np.array([4.0, 5.0, 10.0, 20.0, 38.5])
    tabla = motor.TablaFactores(lados, lados, np.array([[0.9 + 0.005 * (x + y) for x in lados] for y in lados]))
    for energia, d0 in (("8 MV", 5.0), ("6 MV", 3.0), ("6 MV", 10.0)):
        assert um_armar.sc_del_haz(tabla, 100.0, d0, energia) == (motor.SC_MUESTRA_TG71, "tabla IV de la TG-71 (6 MV, otra máquina)")
    sc, _ = um_armar.sc_del_haz(tabla, 100.0, 5.0, "6 MV")
    assert [round(j, 4) for j, _ in sc] == [4.0, 5.0, 10.0, 20.0, 38.0952]    # el 4 de la tabla cuenta, y 38.1 está dentro de una tabla de 38.5
    x_mas = np.array([4.0, 5.0, 7.0, 10.0, 20.0, 38.5])
    con_x_de_mas = motor.TablaFactores(x_mas, lados, np.array([[0.9 + 0.005 * (x + y) for x in x_mas] for y in lados]))
    assert 7.0 not in [j for j, _ in um_armar.sc_del_haz(con_x_de_mas, 100.0, 5.0, "6 MV")[0]]  # un lado que no está en las filas no da Sc


def test_la_revision_dice_cada_cosa_una_vez_y_en_orden(archivos):
    """El resumen que verá el físico, entero y en su orden, no depende del orden de los archivos; un archivo que no se entiende da UN problema; dos copias
    idénticas no son dos archivos distintos; sin perfiles lo dice; un factor escrito no deja un aviso vacío."""
    pares = [(f"a{i}.txt", t) for i, t in enumerate(archivos)]
    r = um_armar.revisar_archivos(pares, "Clinac 600", "6 MV", d0_dmax=1.0)
    assert um_armar.revisar_archivos(list(reversed(pares)), "Clinac 600", "6 MV", d0_dmax=1.0).avisos == r.avisos
    assert r.avisos == RESUMEN_DE_LA_CARGA
    assert um_armar.revisar_archivos(pares + [("basura.txt", "hola")], "Clinac 600", "6 MV", d0_dmax=1.0).problemas == (
        "basura.txt: la cabecera no dice máquina, accesorio y tipo de dato: no parece una exportación de Eclipse",)
    of = es_de(archivos, "Open Field", "OutputFactorTable")
    assert not um_armar.revisar_archivos(pares + [("copia.txt", of)], "Clinac 600", "6 MV", d0_dmax=1.0).problemas
    otra = of.replace("0.870", "0.871")
    for orden in ((("otra.txt", otra), *pares), (*pares, ("otra.txt", otra))):      # la revisión lo dice con el nombre del archivo, en los dos órdenes
        assert any(re.match(r"\w+\.txt: hay dos archivos distintos para Open Field - 00, OutputFactorTable", q)
                   for q in um_armar.revisar_archivos(list(orden), "Clinac 600", "6 MV", d0_dmax=1.0).problemas)
    otra_maquina = um_armar.revisar_archivos(pares, "Clinac iX", "6 MV", d0_dmax=1.0)
    assert len(otra_maquina.problemas) == 12 and otra_maquina.avisos == ()      # con un problema no se arma ni se resume
    of_dos_raras = of.replace("\n4, 0.892, 0.899, 0.913, 0.917, 0.925,", "\n4, 0.892, 0.899, 0.913, 0.917, 0.940,")
    assert of_dos_raras != of
    raras = [a for a in um_armar.revisar_archivos([(n, of_dos_raras if t is of else t) for n, t in pares], "Clinac 600", "6 MV", d0_dmax=1.0).avisos
             if a.startswith("Tabla abierta")]
    assert raras == ["Tabla abierta: el valor en Y = 4 [cm], X = 6 [cm] se sale de la tendencia.", "Tabla abierta: el valor en Y = 30 [cm], X = 25 [cm] se sale de la tendencia."]
    sin_perfiles = [(n, t) for n, t in pares if "data: OPP_processed" not in t]
    assert "No hay perfiles: el OAR fuera del eje se escribirá a mano." in um_armar.revisar_archivos(sin_perfiles, "Clinac 600", "6 MV", d0_dmax=1.0).avisos
    assert "" not in um_armar.revisar_archivos(pares, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={15: 0.72}).avisos
    sin_dos = [(n, t) for n, t in pares if not ("data: WDD\n" in t and ("Wedge - 30" in t or "Wedge - 60" in t))]
    faltan = [a for a in um_armar.revisar_archivos(list(reversed(sin_dos)), "Clinac 600", "6 MV", d0_dmax=1.0).avisos if ": falta su PDD medido con cuña" in a]
    assert [a[:12] for a in faltan] == ["Cuña de 30°:", "Cuña de 60°:"]
    assert um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, sc=[(5.0, 0.98), (10.0, 1.0)]).sc_origen == motor.SC_ESCRITA       # UM.2 v2 (IF-1): ya no ""
    assert um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={15: 0.1, 30: 1.1}).cunas[30].wf_ref == 1.1



# ---------- Los huecos que dejó ver el barrido de mutantes automáticos del motor (pre-vuelo de UM.2) ----------
def test_las_constantes_son_las_del_plan():
    """Cada umbral sale de la TG-71, de la TG-114 o del plan (DC7, DC8, DC9, DC11, DC13): se fijan por su valor, para que mover uno se vea."""
    assert (motor.SAD_CM, motor.DISTANCIA_MINIMA_AL_BORDE_CM, motor.LADO_MINIMO_SIN_AVISO_CM, motor.OAR_SIN_AVISO_CM, motor.PERDIDA_AVISO, motor.ALARGADO_AVISO,
            motor.LADO_MINIMO_CUNA_CM, motor.TOLERANCIA_LADO_CM, motor.PUNTO_EN_EL_EJE_CM, motor.TOLERANCIA_DENTRO_PCT, motor.TOLERANCIA_FUERA_PCT) == (
        100.0, 2.0, 4.0, 10.0, 0.02, 4.0, 3.0, 0.1, 0.05, 2.0, 3.0)
    assert (motor.SSD_RECHAZO_CM, motor.SSD_SIN_AVISO_CM, motor.ORIENTACIONES) == ((60.0, 140.0), (80.0, 120.0), ("IN", "OUT", "LEFT", "RIGHT"))
    assert motor.RANGOS == {"La dosis": (1e-6, 5000.0), "La profundidad": (1e-6, 100.0), "El factor de cuña": (0.1, 1.1), "El factor de bandeja": (0.5, 1.05),
                            "El OAR": (0.7, 1.2), "Las UM de Eclipse": (1e-6, 20000.0), "La profundidad efectiva": (1e-6, 100.0)}
    assert (um_armar.TRAMO_MINIMO_AJUSTE_CUNA_CM, um_armar.D0_RANGO, um_armar.SC_RANGO, um_armar.X_AJUSTE_CENTRO_CM, um_armar.PERFIL_A_UNA_PROFUNDIDAD_CM) == (
        5.0, (0.5, 1.5), (0.5, 1.5), 3.0, 0.05)
    assert motor.PerfilOAR(5.0, 40.0, np.array([0.0, 1.0]), np.array([1.0, 1.0])).ssd == 100.0
    d = motor.DatosCuna(motor.TablaFactores(np.array([3.0, 40.0]), np.array([3.0, 20.0]), np.ones((2, 2))), np.array([4.0, 20.0]), np.zeros(2), 30.0)
    assert d.gradiente_en == "Y" and motor.DatosHaz.__dataclass_fields__["sc_origen"].default == "tabla IV de la TG-71 (6 MV, otra máquina)"


def _origen(r, simbolo):
    return {f.simbolo: (f.origen, f.detalle) for f in r.factores}[simbolo]


def test_cada_factor_dice_su_origen(datos):
    """El desglose que verá el físico (DC14): de dónde sale cada factor."""
    base = dict(dosis=100.0, x=20.0, y=20.0, ssd=100.0, prof=10.0)
    assert _origen(motor.calcular(datos, E(**base)), "OAR")[0] == "sobre el eje"
    assert _origen(motor.calcular(datos, E(**base, punto_x=0.05)), "OAR")[0] == "sobre el eje"      # medio milímetro es el eje, incluido
    assert _origen(motor.calcular(datos, E(**base, punto_x=0.0498)), "OAR")[0] == "sobre el eje"
    assert _origen(motor.calcular(datos, E(**base, punto_x=0.0502)), "OAR")[0] == "tabla"
    assert _origen(motor.calcular(datos, E(**base, punto_x=5.0)), "OAR")[0] == "tabla"
    assert _origen(motor.calcular(datos, E(**base, punto_x=5.0, oar_manual=1.02)), "OAR")[0] == "manual"
    assert _origen(motor.calcular(datos, E(**base)), "WF") == ("sin cuña", "")
    assert _origen(motor.calcular(datos, E(**base, cuna=30, wf_manual=0.7)), "WF") == ("manual", "escrito a mano")
    assert _origen(motor.calcular(datos, E(**base, cuna=15)), "WF")[0] == "tabla"
    assert motor.calcular(datos, E(**base, cuna=15, punto_x=0.05)).um > 0        # con cuña, en el eje (medio milímetro) sí hay número
    assert _origen(motor.calcular(datos, E(**base, tf=0.97)), "TF")[0] == "manual"


@pytest.mark.parametrize("cambio, clase, motivo", [
    (dict(x=0.0), motor.FaltaDato, "El lado X debe ser"), (dict(y=0.0), motor.FaltaDato, "El lado Y debe ser"),
    (dict(x_ef=0.0, y_ef=10.0), motor.FaltaDato, "El lado X efectivo debe ser"), (dict(x_ef=10.0, y_ef=-1.0), motor.FaltaDato, "El lado Y efectivo debe ser"),
    (dict(centro_x="0"), motor.FaltaDato, "El centro del campo debe ser"), (dict(punto_y=float("nan")), motor.FaltaDato, "La posición del punto debe ser"),
    (dict(centro_y="0"), motor.FaltaDato, "El centro del campo debe ser"), (dict(punto_x=float("nan")), motor.FaltaDato, "La posición del punto debe ser"),   # los dos ejes, cada uno con su nombre
    (dict(x=0.5), motor.FueraDeTabla, "El lado X de las mandíbulas"), (dict(y=1.0), motor.FueraDeTabla, "El lado Y de las mandíbulas"),
])
def test_cada_dato_malo_dice_cual_es(datos, cambio, clase, motivo):
    with pytest.raises(clase, match=motivo):
        motor.calcular(datos, E(**{**dict(dosis=100.0, x=10.0, y=10.0, ssd=100.0, prof=10.0), **cambio}))


def test_los_extremos_de_las_tablas(datos):
    """Las lecturas justo en el primer y el último nodo de cada tabla: el PDD a 0 y a 30 cm, el factor de campo en 2.5 y 40, el OAR en la primera y la última
    profundidad de sus perfiles, y las celdas que pesan en una lectura."""
    curvas = {c.campo_cm[0]: c for c in lector.leer_curvas(texto(PDD_ABIERTO))}
    for lado in (2.5, 10.0, 40.0):
        assert datos.pdd(0.0, lado) == pytest.approx(float(curvas[lado].valor[0])) and datos.pdd(30.0, lado) == pytest.approx(float(curvas[lado].valor[-1]))
    t = tabla_real()
    assert datos.of(2.5, 2.5) == celda(t, 2.5, 2.5) and datos.of(40.0, 40.0) == celda(t, 40.0, 40.0) and datos.of(2.5, 40.0) == celda(t, 40.0, 2.5)
    assert datos.perfiles(1.35, 5.0) == pytest.approx(datos.perfiles.grandes[0](5.0))
    assert datos.perfiles(30.0, 5.0) == pytest.approx(datos.perfiles.grandes[-1](5.0))
    assert motor.calcular(datos, E(100.0, 20.0, 20.0, 100.0, 1.35, punto_x=5.0)).um > 0
    of = datos.of
    assert of.celdas_usadas(10.0, 10.0) == {(10.0, 10.0)} and of.celdas_usadas(2.5, 40.0) == {(40.0, 2.5)} and of.celdas_usadas(40.0, 2.5) == {(2.5, 40.0)}
    assert of.celdas_usadas(12.0, 8.0) == {(6.0, 10.0), (6.0, 15.0), (10.0, 10.0), (10.0, 15.0)}
    assert of.celdas_usadas(3.0, 25.0) == {(25.0, 3.0)} and of.celdas_usadas(3.5, 2.5) == {(2.5, 3.0), (2.5, 4.0)}
    assert of.contiene(2.5, 40.0) and of.contiene(40.0, 2.5) and not of.contiene(2.4, 10.0) and not of.contiene(10.0, 40.1) and not of.contiene(41.0, 10.0)


def test_los_avisos_en_sus_limites(datos):
    base = dict(dosis=100.0, x=20.0, y=20.0, ssd=100.0, prof=10.0)
    assert not any("más de 5 [%]" in a for a in motor.calcular(datos, E(**base, punto_x=5.0)).avisos)
    sin_sc = motor.DatosHaz(datos.equipo, datos.energia, 100.0, 5.0, 0.86, datos.pdd, datos.of, sc=(), perfiles=datos.perfiles, cunas=datos.cunas)
    assert motor.calcular(sin_sc, E(**base)).avisos == ()
    for lado in (4.0, 20.0):                                     # r justo en el primer y en el último cuadrado medido con cuña
        assert not any("campo medido más cercano" in a for a in motor.calcular(datos, E(100.0, lado, lado, 100.0, 10.0, cuna=15)).avisos)
    escrito = um_armar.datos_haz([texto(n) for n in sorted(os.listdir(DATOS))], "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={15: 0.72})
    assert "" not in motor.calcular(escrito, E(**base, cuna=15)).avisos
    assert motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 10.0, x_ef=10.1, y_ef=10.0)).um > 0         # 0.1 cm de redondeo, incluido
    lado = motor.equivalente(10.0, 20.0) + 0.1
    assert motor.calcular(datos, E(100.0, 10.0, 20.0, 100.0, 10.0, x_ef=lado, y_ef=lado)).um > 0
    con_inf = motor.DatosHaz(datos.equipo, datos.energia, 100.0, 5.0, 0.86, datos.pdd, motor.TablaFactores(datos.of.x, datos.of.y, np.where(datos.of.m > 0, np.inf, 0.0)))
    with pytest.raises(motor.FaltaDato, match="no dio un número válido"):
        motor.calcular(con_inf, E(100.0, 10.0, 10.0, 100.0, 10.0))



def test_con_una_tabla_de_cuna_de_gradiente_en_x_se_cruza_solo_lo_que_hay_que_cruzar(archivos):
    """Con la tabla girada (gradiente a lo largo de X), un campo IN de 10 × 20 y uno LEFT de 20 × 10 leen la tabla en el mismo sitio."""
    tabla, wdd = es_de(archivos, "Standard Wedge - 30", "data: OutputFactorTable"), es_de(archivos, "Standard Wedge - 30", "data: WDD\n")
    d = um_armar.datos_haz(cambiar(cambiar(archivos, tabla, _transpuesta(tabla)), wdd, wdd.replace("%FLSZ 400*200", "%FLSZ 200*400")), "Clinac 600", "6 MV",
                           d0_dmax=1.0, wf_escritos={30: 0.6})
    wf = lambda x, y, o: factor(motor.calcular(d, E(100.0, x, y, 100.0, 10.0, cuna=30, cuna_orientacion=o)), "WF")
    assert wf(10.0, 20.0, "IN") == pytest.approx(wf(20.0, 10.0, "LEFT")) and wf(10.0, 20.0, "IN") != pytest.approx(wf(10.0, 20.0, "LEFT"), rel=1e-6)

def test_la_perdida_junto_al_borde_en_sus_limites():
    """La estimación (solo da un aviso) compara el perfil del cuadrado más parecido con el grande, en las profundidades donde los dos llegan."""
    x = np.arange(0.0, 25.0, 0.5)
    caida = lambda lado: np.clip(1.0 - np.maximum(x - (lado / 2 - 3), 0) * 0.1, 0.05, 1.0)
    perfil = lambda lado, prof: motor.PerfilOAR(prof, lado, x, caida(lado))
    grandes = (perfil(40.0, 5.0), perfil(40.0, 10.0))
    todos = grandes + (perfil(10.0, 10.0), perfil(10.0, 5.0))
    p = motor.PerfilesOAR(grandes, todos)
    a5 = p.perdida_junto_al_borde((10.0, 10.0), (4.0, 0.0), 5.0)
    assert a5 == pytest.approx(float(np.interp(4.0 * 1.05, x, caida(10.0)) / np.interp(4.0 * 1.05, x, caida(40.0))))
    assert p.perdida_junto_al_borde((10.0, 10.0), (4.0, 0.0), 10.0) == pytest.approx(float(np.interp(4.0 * 1.1, x, caida(10.0))))
    assert p.perdida_junto_al_borde((10.0, 10.0), (4.0, 0.0), 12.0) == 1.0          # más allá de lo medido: no se estima
    assert p.perdida_junto_al_borde((10.0, 10.0), (30.0, 0.0), 5.0) == 1.0          # más allá de lo que mide el perfil
    assert motor.PerfilesOAR(grandes[:1], todos[:1]).perdida_junto_al_borde((10.0, 10.0), (4.0, 0.0), 5.0) == 1.0
    assert p.perdida_junto_al_borde((12.0, 10.0), (4.0, 0.0), 5.0) == pytest.approx(a5)      # el cuadrado medido más parecido a 12 es el 10
    assert motor.PerfilesOAR(grandes, todos[::-1]).perdida_junto_al_borde((10.0, 10.0), (4.0, 0.0), 7.5) == pytest.approx(
        p.perdida_junto_al_borde((10.0, 10.0), (4.0, 0.0), 7.5))


# ---------- Lo que dejó vivo el barrido de mutantes automáticos del motor, cerrado por el implementador (UM.2, 08-11; pistas §7-bis) ----------
def test_cada_factor_dice_su_origen_en_el_desglose_completo(datos):
    """El desglose entero que verá el físico (DC14), factor por factor y en su orden: de dónde sale cada uno, con y sin cuña, con el OAR de la tabla o sobre el eje, con
    y sin bandeja. La etiqueta de la bandeja depende de que valga 1 (por encima y por debajo de 1 es «manual»)."""
    simbolos = ["D", "D'0", "OF", "Sc(rc)/Sc(lectura)", "PDD_N", "WF", "TF", "OAR", "Inverso del cuadrado", "Corrección por profundidad efectiva"]
    con_cuna = motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 10.0, cuna=15, tf=0.97))
    assert [f.simbolo for f in con_cuna.factores] == simbolos
    assert [f.origen for f in con_cuna.factores] == ["plan", "tabla", "tabla", "cálculo", "tabla", "tabla", "manual", "sobre el eje", "cálculo", "cálculo"]
    fuera_del_eje = motor.calcular(datos, E(100.0, 20.0, 20.0, 100.0, 10.0, punto_x=5.0))
    assert [f.origen for f in fuera_del_eje.factores] == ["plan", "tabla", "tabla", "cálculo", "tabla", "sin cuña", "sin bandeja", "tabla", "cálculo", "cálculo"]
    assert con_cuna.factores[0].detalle == "Dosis del campo en el punto [cGy]"
    for tf, origen in ((1.0, "sin bandeja"), (0.97, "manual"), (1.03, "manual")):
        assert _origen(motor.calcular(datos, E(100.0, 10.0, 10.0, 100.0, 10.0, tf=tf)), "TF")[0] == origen


def test_cada_tabla_dice_que_lado_o_que_profundidad_se_salio(datos):
    """El mensaje de una lectura fuera de tabla nombra qué se salió (el lado en la superficie, la profundidad, el lado X o el lado Y de la tabla de factores) y con qué valor."""
    with pytest.raises(motor.FueraDeTabla, match="El lado del campo en la superficie = 2.40"):
        datos.pdd(10.0, 2.4)
    with pytest.raises(motor.FueraDeTabla, match="La profundidad = 30.10"):
        datos.pdd(30.1, 10.0)
    with pytest.raises(motor.FueraDeTabla, match="El lado X que se lee en la tabla de factores = 2.40"):
        datos.of(2.4, 10.0)
    with pytest.raises(motor.FueraDeTabla, match="El lado Y que se lee en la tabla de factores = 2.40"):
        datos.of(10.0, 2.4)


def test_el_margen_de_1e_9_cm_de_las_tablas_es_ruido_de_redondeo_y_nada_mas(datos):
    """Una lectura que se aparta del borde de una tabla 1e-9 cm o menos (ruido de coma flotante) se lee en el borde, y por más no se lee: nunca se extrapola.
    Se prueba el margen en sí (justo en él y medio por ciento más allá) y lo que hacen con él la interpolación y las celdas que pesan en una lectura."""
    pdd, of = datos.pdd, datos.of
    z0, z1, r0, r1 = float(pdd.z_cm[0]), float(pdd.z_cm[-1]), float(pdd.lados[0]), float(pdd.lados[-1])
    x0, x1, y0, y1 = float(of.x[0]), float(of.x[-1]), float(of.y[0]), float(of.y[-1])
    lecturas = (lambda m: pdd(z0 - m, 10.0), lambda m: pdd(z1 + m, 10.0), lambda m: pdd(10.0, r0 - m), lambda m: pdd(10.0, r1 + m),
                lambda m: of(x0 - m, 10.0), lambda m: of(x1 + m, 10.0), lambda m: of(10.0, y0 - m), lambda m: of(10.0, y1 + m))
    for leer in lecturas:
        assert leer(1e-9) > 0 and leer(5e-10) > 0                               # el margen mismo y la mitad
        with pytest.raises(motor.FueraDeTabla):
            leer(1.005e-9)
    assert pdd(z1 + 1e-9, 10.0) == pytest.approx(pdd(z1, 10.0), rel=1e-6) and of(x1 + 1e-9, 10.0) == pytest.approx(of(x1, 10.0), rel=1e-6)
    assert of.celdas_usadas(x1 + 5e-10, 10.0) == {(10.0, 35.0), (10.0, 40.0)} and of.celdas_usadas(x0 - 5e-10, 10.0) == {(10.0, 2.5), (10.0, 3.0)}
    assert of.celdas_usadas(10.0, y1 + 5e-10) == {(35.0, 10.0), (40.0, 10.0)} and of.celdas_usadas(10.0, y0 - 5e-10) == {(2.5, 10.0), (3.0, 10.0)}


CURVA_DE_SC_DE_PRUEBA = ((6.0, 0.97), (10.0, 1.0), (14.0, 1.02), (20.0, 1.05))


@pytest.mark.parametrize("x, ef, hizo_falta", [
    (17.0, 8.0, None),            # los dos dentro de la curva: el menor entre el primer y el segundo lado, el mayor entre el penúltimo y el último
    (15.0, 5.0, "5.0 a 15.0"),    # solo el menor se sale, por debajo del primer lado
    (25.0, 12.0, "12.0 a 25.0"),  # solo el mayor se sale, por encima del último lado
    (25.0, 5.0, "5.0 a 25.0"),    # se salen los dos
    (15.0, 6.0, None),            # el menor justo en el primer lado: la curva llega
    (20.0, 12.0, None),           # el mayor justo en el último lado: la curva llega
])
def test_el_aviso_de_que_la_curva_de_sc_no_llega_mira_cada_extremo_y_solo_ese(datos, x, ef, hizo_falta):
    con_curva = motor.DatosHaz(datos.equipo, datos.energia, 100.0, 5.0, 0.86, datos.pdd, datos.of, sc=CURVA_DE_SC_DE_PRUEBA, sc_origen="curva de prueba",
                               perfiles=datos.perfiles, cunas=datos.cunas)
    avisos = " | ".join(motor.calcular(con_curva, E(100.0, x, x, 100.0, 10.0, x_ef=ef, y_ef=ef)).avisos)
    if hizo_falta is None:
        assert "La curva de Sc va de" not in avisos
    else:
        assert f"La curva de Sc va de 6 a 20 [cm] y aquí hizo falta {hizo_falta} [cm]" in avisos


def test_sin_curva_de_sc_avisa_si_el_campo_de_lectura_difiere_y_no_si_solo_es_ruido_de_redondeo(datos):
    """Con SSD 80.2, d = 1.8 y 21.6 cm de profundidad el campo de lectura es, álgebra mediante, el de las mandíbulas; en coma flotante difiere en 4e-15 cm y no es
    otro campo. A SSD 95 la diferencia es de 0.45 cm, menos de 1 cm, y sí lo es."""
    sin_sc = motor.DatosHaz(datos.equipo, datos.energia, 100.0, 5.0, 0.86, datos.pdd, datos.of, sc=(), perfiles=datos.perfiles, cunas=datos.cunas)
    assert "no hay curva de Sc" not in avisos_de(sin_sc, 100.0, 10.0, 10.0, 80.2, 21.6, prof_ef=1.8)
    assert 0 < abs(motor.calcular(sin_sc, E(100.0, 10.0, 10.0, 80.2, 21.6, prof_ef=1.8)).campos["x_lectura"] - 10.0) < 1e-12      # y no es una igualdad exacta
    assert "no hay curva de Sc" in avisos_de(sin_sc, 100.0, 10.0, 10.0, 95.0, 10.0)
    assert "no hay curva de Sc" in avisos_de(sin_sc, 100.0, 10.0, 10.0, 90.0, 10.0)


@pytest.mark.parametrize("x, y", [(2.5, 20.0), (20.0, 2.5)])
def test_la_mandibula_de_2_5_cm_con_cuna_se_lee_si_su_cuadrado_equivalente_pasa_de_3(datos, x, y):
    """La tabla de la cuña empieza en 2 cm y la abierta en 2.5: una mandíbula de 2.5 cm, a lo ancho o a lo largo de la cuña, con láminas cuyo cuadrado equivalente
    es de 4 cm, se lee. UM.2 v2 (UM2-D9): el 4A/P de las mandíbulas (4.44) escrito como efectivo NO son láminas, es el campo de las mandíbulas, y con cuña no se lee
    por debajo de 3 cm, como las mandíbulas solas."""
    r = motor.calcular(datos, E(100.0, x, y, 100.0, 10.0, x_ef=4.0, y_ef=4.0, cuna=15))
    assert _origen(r, "WF")[0] == "tabla" and 0.5 < factor(r, "WF") < 1.0 and r.um > 0
    for kw in (dict(), dict(x_ef=2 * 2.5 * 20.0 / 22.5, y_ef=2 * 2.5 * 20.0 / 22.5)):
        with pytest.raises(motor.FueraDeTabla, match=r"por debajo de 3 \[cm\]"):
            motor.calcular(datos, E(100.0, x, y, 100.0, 10.0, cuna=15, **kw))


def _perfil_sintetico(prof, lado, hasta, pendiente=0.1):
    """OAR de un cuadrado `lado` a `prof` cm: plano hasta 3 cm antes de su borde y de ahí cae `pendiente` por cm; medido hasta `hasta` cm en el plano del perfil."""
    x = np.arange(0.0, hasta + 0.25, 0.5)
    return motor.PerfilOAR(prof, lado, x, np.clip(1.0 - np.maximum(x - (lado / 2 - 3), 0) * pendiente, 0.05, 1.0))


def test_la_perdida_sin_perfil_grande_a_esa_profundidad_no_se_estima_y_no_revienta():
    """Un campo pequeño medido a una profundidad donde no hay perfil grande: no hay con qué compararlo, y la pérdida vale 1 (no un cociente con nada)."""
    grandes = (_perfil_sintetico(5.0, 40.0, 24.0), _perfil_sintetico(10.0, 40.0, 24.0))
    p = motor.PerfilesOAR(grandes, grandes + tuple(_perfil_sintetico(pr, 10.0, 24.0) for pr in (1.0, 2.0, 3.0, 5.0, 10.0)))
    assert p.perdida_junto_al_borde((10.0, 10.0), (4.0, 0.0), 2.0) == 1.0
    assert p.perdida_junto_al_borde((10.0, 10.0), (4.0, 0.0), 5.0) == pytest.approx(0.78)       # a 5 cm sí hay con qué compararlo: 1 − (4.2 − 2)·0.1 frente a 1


def test_la_perdida_se_estima_hasta_donde_mide_el_perfil_incluido():
    """Un perfil medido hasta 21 cm a 5 cm de profundidad (hasta 22 a 10) llega, en el plano del isocentro, justo a 20.0 cm: ahí todavía se estima."""
    grandes = (_perfil_sintetico(5.0, 40.0, 21.0), _perfil_sintetico(10.0, 40.0, 22.0))
    todos = grandes + (_perfil_sintetico(5.0, 10.0, 21.0), _perfil_sintetico(10.0, 10.0, 22.0))
    p = motor.PerfilesOAR(grandes, todos)
    assert grandes[0].medido_hasta == 20.0 and grandes[1].medido_hasta == 20.0
    esperado = float(todos[2].oar[-1] / grandes[0].oar[-1])        # a 20 cm del eje y 5 cm de profundidad se lee el último punto de los dos perfiles
    assert esperado < 0.5 and p.perdida_junto_al_borde((10.0, 10.0), (20.0, 0.0), 5.0) == pytest.approx(esperado)
    assert p.perdida_junto_al_borde((10.0, 10.0), (20.1, 0.0), 5.0) == 1.0


def test_en_la_primera_profundidad_el_par_que_se_interpola_es_el_primero_y_el_segundo(datos):
    """A la profundidad del primer perfil se interpola entre el primero y el segundo (con peso 0 en el segundo): los dos deben llegar hasta el punto, y el último
    perfil no tiene nada que ver."""
    p = motor.PerfilesOAR((_perfil_sintetico(5.0, 40.0, 21.0), _perfil_sintetico(10.0, 40.0, 11.0), _perfil_sintetico(20.0, 40.0, 24.0)), ())
    with pytest.raises(motor.FueraDeTabla, match=r"40 × 40 \[cm\] a 10 \[cm\] solo sirve hasta 10 \[cm\]"):
        p(5.0, 12.0)
    assert p(5.0, 9.0) == 1.0
    # UM.2 v2 (PR-3): con los perfiles reales, a 1.35 cm y a 16 cm del eje el alcance es el del 40 × 40 de 5 cm (18 cm), no el del 35 × 35 de 30 cm (15.5)
    assert datos.perfiles(1.35, 16.0) == pytest.approx(oar_a_mano(40.0, 1.35, 16.0), rel=1e-12)


def test_en_un_empate_el_cuadrado_medido_mas_parecido_es_el_menor_estén_como_estén_los_perfiles():
    """16 equidista, en logaritmo, de 8 y de 32 (en coma flotante también: las dos distancias son idénticas bit a bit, y el primer assert lo comprueba por si otra libm lo
    redondeara distinto): se toma el menor, y el orden de los perfiles no cambia nada."""
    assert abs(math.log(16.0) - math.log(8.0)) == abs(math.log(32.0) - math.log(16.0))
    grandes = (_perfil_sintetico(5.0, 40.0, 24.0), _perfil_sintetico(10.0, 40.0, 24.0))
    de_8 = tuple(_perfil_sintetico(pr, 8.0, 24.0, pendiente=0.2) for pr in (5.0, 10.0))
    de_32 = tuple(_perfil_sintetico(pr, 32.0, 24.0, pendiente=0.2) for pr in (5.0, 10.0))
    esperado = float(np.interp(4.0 * 1.05, de_8[0].x, de_8[0].oar) / np.interp(4.0 * 1.05, grandes[0].x, grandes[0].oar))      # el de 8 × 8 a 5 cm: 0.36
    assert esperado == pytest.approx(0.36)
    for bloques in itertools.permutations((grandes, de_8, de_32)):          # los seis ordenes de los perfiles (el orden de un conjunto depende del de insercion)
        todos = sum(bloques, ())
        assert motor.PerfilesOAR(grandes, todos).perdida_junto_al_borde((16.0, 16.0), (4.0, 0.0), 5.0) == pytest.approx(esperado)


def test_el_eje_del_gradiente_se_decide_con_hasta_donde_llega_cada_eje_y_no_con_el_lado_de_antes():
    """Una tabla que llega a 38 cm en Y y a 40 en X es de gradiente en Y aunque el penúltimo lado de X (35) sea menor que 38; una que llega a 20 en X y a 21 en Y (con 20 como
    penúltimo lado de Y) es de gradiente en X. En las del 600C el penúltimo lado nunca queda entre los dos últimos y estos dos casos no se daban."""
    tabla = lambda x, y: motor.TablaFactores(np.array(x), np.array(y), np.ones((len(y), len(x))))
    assert um_armar._eje_del_gradiente(tabla([2.0, 35.0, 40.0], [2.0, 38.0]), None, 15) == "Y"
    assert um_armar._eje_del_gradiente(tabla([2.0, 20.0], [2.0, 20.0, 21.0]), None, 15) == "X"


def test_sc_del_haz_incluye_el_lado_que_cae_justo_en_el_primer_lado_de_la_tabla_iv():
    """Con la tabla a SSD 95 y d0 = 5 el factor de proyección vale 1 y el lado de 4 cm cae justo en el primer lado de la tabla IV (4 cm): entra, como el de 40 en el último."""
    lados = np.array([3.0, 4.0, 5.0, 6.0, 10.0, 20.0, 40.0])
    curva, origen = um_armar.sc_del_haz(motor.TablaFactores(lados, lados, np.ones((7, 7))), 95.0, 5.0, "6 MV")
    assert [j for j, _ in curva] == [4.0, 5.0, 6.0, 10.0, 20.0, 40.0] and origen == "estimada de la tabla de este haz y el Sp de la TG-71"


def test_los_factores_de_cuna_escritos_que_sobran_se_nombran_en_orden(archivos):
    """El motivo nombra los ángulos de menor a mayor, no en el orden en que un conjunto de enteros los devuelva (45, 30, 15)."""
    abiertos = [a for a in archivos if "add on: Open Field" in a]
    with pytest.raises(motor.FaltaDato, match="entre los archivos: 15°, 30°, 45°"):
        um_armar.datos_haz(abiertos, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={45: 0.5, 15: 0.7, 30: 0.6})


def test_los_avisos_de_las_celdas_a_revisar_de_una_cuna_van_ordenados(datos, archivos, monkeypatch):
    """Las celdas de la tabla de una cuña que se salen de la tendencia se avisan de menor a mayor (Y y luego X), no en el orden en que un conjunto las devuelva: las dos de la
    cuña de 45° del 600C ya salen en orden de casualidad, y esto lo fija con seis celdas cuyo orden natural no es el ordenado."""
    celdas = [(10.0, 3.0), (3.0, 10.0), (2.0, 40.0), (20.0, 5.0), (6.0, 15.0), (15.0, 6.0)]
    assert list(frozenset(celdas)) != sorted(celdas)      # la premisa: si otra versión de Python ordenara el conjunto, este caso dejaría de discriminar y hay que cambiar las celdas
    falso = dataclasses.replace(datos, cunas={45: dataclasses.replace(datos.cunas[45], celdas_a_revisar=frozenset(celdas))}, celdas_a_revisar=frozenset())
    monkeypatch.setattr(um_armar, "datos_haz", lambda *a, **k: falso)
    r = um_armar.revisar_archivos([(f"a{i}.txt", t) for i, t in enumerate(archivos)], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert [a for a in r.avisos if "se sale de la tendencia" in a] == [f"Cuña de 45°: el valor en Y = {y:g} [cm], X = {x:g} [cm] se sale de la tendencia." for y, x in sorted(celdas)]


RESUMEN_DE_LA_CARGA = (   # revisar_archivos de los 22 archivos del 600C, tal como lo verá el físico (UM.5): medido en el pre-vuelo de UM.2
    "Perfiles para el OAR: 40 × 40 a 1.35 [cm]; 40 × 40 a 5 [cm]; 40 × 40 a 10 [cm]; 40 × 40 a 20 [cm]; 35 × 35 a 30 [cm].",
    "Curva de Sc: estimada de la tabla de este haz y el Sp de la TG-71.",
    "D'0 = 0.8600 [cGy/UM] a 5 [cm] de profundidad, SSD 100 [cm], 10 × 10: sale de 1 [cGy/UM] en dmax con el máximo medido del PDD de 10 × 10, 100.00 [%].",  # v2 (A6)
    "Tabla abierta: el valor en Y = 30 [cm], X = 25 [cm] se sale de la tendencia.",
    "Cuña de 15°: su tabla de factores va de 2 a 40 [cm] en X y de 2 a 20 [cm] en Y.",      # ronda 1 (F3): hasta dónde llega la tabla de cada cuña
    "Cuña de 15°: el valor en Y = 6 [cm], X = 4 [cm] se sale de la tendencia.",
    "El factor de la cuña de 15° en 10 × 10 es 0.7701: se dedujo de su dosis de referencia, 0.6623 [cGy/UM], entre D'0, 0.8600 [cGy/UM], suponiendo que esa dosis es a 5 [cm]: "
    "falta confirmarlo.",      # ronda 1 (F1): con su valor y los dos datos de que sale (DC13, 2)
    "Cuña de 30°: su tabla de factores va de 2 a 40 [cm] en X y de 2 a 20 [cm] en Y.",
    "Cuña de 30°: falta su factor en 10 × 10; hasta tenerlo se escribe por campo.",
    "Cuña de 45°: su tabla de factores va de 2 a 40 [cm] en X y de 2 a 20 [cm] en Y.",
    "Cuña de 45°: el valor en Y = 3 [cm], X = 30 [cm] se sale de la tendencia.",
    "Cuña de 45°: el valor en Y = 15 [cm], X = 35 [cm] se sale de la tendencia.",
    "Cuña de 45°: falta su factor en 10 × 10; hasta tenerlo se escribe por campo.",
    "Cuña de 60°: su tabla de factores va de 2 a 40 [cm] en X y de 2 a 15 [cm] en Y.",
    "Cuña de 60°: falta su factor en 10 × 10; hasta tenerlo se escribe por campo.",
)

# ---------- La guarda del plan (§4-bis): las cifras de logs/h_datos_reales.txt, copiadas como texto ----------
CASOS_DE_LA_PUERTA = [   # (entrada, la fila de logs/h_datos_reales.txt: OF, C_Sc, PDD_N, WF, OAR, ISL, C_prof | UM)
    (dict(x=10, y=10, ssd=100, prof=10), "1.000 1.0000  76.98 1.0000 1.000 1.000 1.000 |  302.1"),
    (dict(x=10, y=10, ssd=90, prof=10), "0.989 1.0032  75.86 1.0000 1.000 1.222 1.000 |  252.8"),
    (dict(x=10, y=15, ssd=92, prof=8), "1.009 1.0018  85.94 1.0000 1.000 1.172 1.000 |  228.4"),
    (dict(x=15, y=15, ssd=90, prof=10, x_ef=10, y_ef=10), "0.989 1.0127  75.86 1.0000 1.000 1.222 1.000 |  250.5"),
    (dict(x=20, y=20, ssd=90, prof=10, punto_x=5), "1.050 1.0020  78.73 1.0000 1.022 1.222 1.000 |  224.9"),
    (dict(x=20, y=20, ssd=90, prof=10, punto_x=8), "1.050 1.0020  78.73 1.0000 1.029 1.222 1.000 |  223.3"),
    (dict(x=10, y=10, ssd=90, prof=15, prof_ef=8), "0.997 1.0010  85.46 1.0000 1.000 1.222 0.871 |  256.3"),
    (dict(x=10, y=10, ssd=90, prof=10, cuna=15), "0.989 1.0032  75.86 0.7735 1.000 1.222 1.000 |  326.8"),
    (dict(x=15, y=15, ssd=90, prof=10, cuna=15), "1.026 1.0022  77.66 0.7769 1.000 1.222 1.000 |  306.7"),
    (dict(x=5, y=5, ssd=90, prof=10), "0.923 1.0040  73.47 1.0000 1.000 1.222 1.000 |  279.6"),
]


@pytest.mark.parametrize("entrada, fila", CASOS_DE_LA_PUERTA)
def test_la_guarda_los_casos_de_la_puerta_dan_lo_del_log(datos, entrada, fila):
    """§8, paso 4: las UM que el físico verá en la puerta, con cada factor como lo imprime `scripts/h_datos_reales.py`."""
    r = motor.calcular(datos, E(200.0, **{k: float(v) if k != "cuna" else v for k, v in entrada.items()}))
    f = {q.simbolo: q.valor for q in r.factores}
    assert (f"{f['OF']:.3f} {f['Sc(rc)/Sc(lectura)']:.4f} {f['PDD_N']:6.2f} {f['WF']:.4f} {f['OAR']:.3f} {f['Inverso del cuadrado']:.3f} "
            f"{f['Corrección por profundidad efectiva']:.3f} | {r.um:6.1f}") == fila


def test_la_guarda_el_haz_armado_da_lo_del_log(datos):
    assert f"{datos.d0_norm:.4f}" == "0.8600"
    assert datos.perfiles.origen == "40 × 40 a 1.35 [cm]; 40 × 40 a 5 [cm]; 40 × 40 a 10 [cm]; 40 × 40 a 20 [cm]; 35 × 35 a 30 [cm]"
    assert datos.sc_origen == "estimada de la tabla de este haz y el Sp de la TG-71"
    assert "  ".join(f"{j:g}: {v:.4f}" for j, v in datos.sc) == ("4: 0.9657  5: 0.9749  6: 0.9826  10: 1.0000  15: 1.0094  20: 1.0154  25: 1.0205  30: 1.0227  "
                                                              "35: 1.0282  38.0952: 1.0287")
    assert sorted(datos.celdas_a_revisar) == [(30.0, 25.0)]
    betas = {15: "4: 0.00101  10: 0.00087  15: 0.00050  20: 0.00019", 30: "4: 0.00146  10: 0.00155  15: 0.00103  20: 0.00085",
             45: "4: 0.00206  10: 0.00212  15: 0.00151  20: 0.00137", 60: "4: 0.00258  10: 0.00271  15: 0.00241"}
    for angulo, esperado in betas.items():
        c = datos.cunas[angulo]
        assert "  ".join(f"{lado:g}: {beta:.5f}" for lado, beta in zip(c.lados_beta, c.betas)) == esperado


def test_la_guarda_el_oar_del_40_por_40_da_lo_del_log(datos):
    tabla = {1.4: "  1.011  1.026  1.037  1.047  1.050  1.059  1.065", 5: "  1.010  1.023  1.033  1.039  1.043  1.046  1.046",
             10: "  1.008  1.020  1.027  1.029  1.027  1.027  1.014", 15: "  1.007  1.016  1.020  1.018  1.012  1.005  0.980",
             20: "  1.006  1.012  1.012  1.008  0.998  0.983  0.947", 25: "  1.005  1.009  1.005  0.994  0.978  0.953  0.895"}
    for prof, fila in tabla.items():
        assert "".join(f"{datos.perfiles(float(prof), float(x)):7.3f}" for x in (2, 4, 6, 8, 10, 12, 15)) == fila


def test_la_guarda_los_ejemplos_de_la_tg71_dan_lo_del_log(haz_tg71):
    ej2, ej3 = EJ2, EJ3
    for publicado, entrada in (("266.08", dict(dosis=250.0, x=10.0, y=15.0, ssd=94.0, prof=6.0)), ("155.65", ej2), ("135.28", {**ej2, "prof_ef": 6.0}),
                               ("72.84", {**ej3, "wf_manual": 0.845}), ("68.65", {**ej3, "wf_manual": 0.892, "oar_manual": 1.005})):
        assert f"{motor.calcular(haz_tg71, E(**entrada)).um:.2f}" == publicado


# ---------- El mundo simulado (H6): la dosis exacta se conoce, y las tablas tienen la rejilla y el redondeo de las reales ----------
LADOS_SIMULADOS = [2.5, 3, 4, 5, 6, 10, 15, 20, 25, 30, 35, 40]
SSDS_SIMULADAS = (80, 85, 90, 95, 100, 105, 110)
PROFS_SIMULADAS = (3, 5, 7.5, 10, 15, 20, 25)
ABIERTOS = [(5, 5), (10, 10), (15, 15), (20, 20), (30, 30), (5, 20), (20, 5), (10, 15), (8, 12), (4, 4), (3, 3), (6, 25)]
RECORTADOS = [(15, 15, 10, 10), (20, 20, 10, 10), (10, 10, 6, 6), (15, 15, 6, 6), (20, 15, 12, 8), (12, 12, 10, 10), (25, 25, 15, 15)]


@pytest.fixture(scope="module")
def mundo():
    """El haz simulado con la curva de Sc por omisión de la calculadora (la estimada de su propia tabla, DC3) y con el Sc verdadero."""
    z, pdd, of, d0_dmax = ms.tablas_medidas(LADOS_SIMULADOS, LADOS_SIMULADOS, LADOS_SIMULADOS)
    lados = np.array(LADOS_SIMULADOS, float)
    familia, tabla = motor.FamiliaPDD(lados, z, pdd), motor.TablaFactores(lados, lados, of)
    d0_norm = motor.d0_en_normalizacion(familia, d0_dmax, 5.0)
    sc, origen = um_armar.sc_del_haz(tabla, 100.0, 5.0, "6 MV")
    del_haz = motor.DatosHaz("Simulado", "6 MV", 100.0, 5.0, d0_norm, familia, tabla, sc=sc, sc_origen=origen)
    verdadero = motor.DatosHaz("Simulado", "6 MV", 100.0, 5.0, d0_norm, familia, tabla, sc=tuple((float(s), ms.sc_cuadrado(float(s))) for s in LADOS_SIMULADOS), sc_origen="verdadero")
    return del_haz, verdadero


def _errores_contra_la_verdad(datos, casos):
    """100·(UM del motor / UM verdaderas − 1) de los casos calculables; los que caen fuera de la tabla no cuentan."""
    errores = []
    for (x, y, xe, ye), ssd, d in casos:
        try:
            um = motor.calcular(datos, E(200.0, x, y, ssd, d, x_ef=xe, y_ef=ye)).um
        except motor.FueraDeTabla:
            continue
        errores.append(100 * (um * ms.dosis_por_um(x, y, xe, ye, ssd, d) / 200.0 - 1))
    return np.array(errores)


@pytest.mark.parametrize("que, n, maximo, dentro_de_1, media", [
    ("SSD 100, mandíbulas solas", 84, 0.6, 1.0, (-0.08, 0.02)),       # H6: máximo 0.53 %, 100 % dentro de 1 %, media −0.03 %
    ("SSD 80 a 110, mandíbulas solas", 583, 1.2, 0.99, (-0.03, 0.07)),  # H6: máximo 1.12 %, 99.3 %, media +0.02 %
    ("SSD 80 a 110, láminas", 343, 1.1, 0.99, (-0.58, -0.48)),          # H6: máximo 0.99 %, 100 %, media −0.53 %
])
def test_el_mundo_simulado_con_la_curva_de_sc_por_omision(mundo, que, n, maximo, dentro_de_1, media):
    abiertos = [((x, y, x, y), s, d) for (x, y) in ABIERTOS for s in SSDS_SIMULADAS for d in PROFS_SIMULADAS]
    casos = {"SSD 100, mandíbulas solas": [c for c in abiertos if c[1] == 100], "SSD 80 a 110, mandíbulas solas": abiertos,
             "SSD 80 a 110, láminas": [(c, s, d) for c in RECORTADOS for s in SSDS_SIMULADAS for d in PROFS_SIMULADAS]}[que]
    e = _errores_contra_la_verdad(mundo[0], casos)
    assert len(e) == n
    assert np.abs(e).max() <= maximo and np.mean(np.abs(e) <= 1.0) >= dentro_de_1 and media[0] <= e.mean() <= media[1]


def test_el_mundo_simulado_con_el_sc_verdadero_casi_no_se_equivoca(mundo):
    """Con el Sc verdadero lo que queda es el redondeo de las tablas y la interpolación: H6, máximo 0.59 % y 0.26 %."""
    abiertos = [((x, y, x, y), s, d) for (x, y) in ABIERTOS for s in SSDS_SIMULADAS for d in PROFS_SIMULADAS]
    recortados = [(c, s, d) for c in RECORTADOS for s in SSDS_SIMULADAS for d in PROFS_SIMULADAS]
    assert np.abs(_errores_contra_la_verdad(mundo[1], abiertos)).max() <= 0.6 and np.abs(_errores_contra_la_verdad(mundo[1], recortados)).max() <= 0.3


@pytest.mark.parametrize("lado, ssd, d, d_ef", [(10, 100, 10, 6), (10, 90, 10, 6), (10, 90, 15, 8), (20, 90, 10, 6), (5, 90, 10, 6), (10, 90, 10, 12), (15, 85, 15, 8), (10, 92, 8, 5)])
def test_la_profundidad_efectiva_da_el_cf_de_la_ecuacion_7(mundo, lado, ssd, d, d_ef):
    """DC10: el factor del motor frente a CF = TMR(d_ef; rd)/TMR(d; rd) del mundo simulado; H7 y `logs/h_mundo_simulado.txt` §7: de −0.03 a +0.15 %."""
    rd = lado * (ssd + d) / 100
    cf = float(ms.tmr(d_ef, rd, rd) / ms.tmr(d, rd, rd))
    con, sin = (motor.calcular(mundo[1], E(200.0, lado, lado, ssd, d, prof_ef=q)).d_um for q in (d_ef, None))
    assert -0.1 <= 100 * (con / sin / cf - 1) <= 0.2


# ---------- Al azar, con semilla fija (scripts/h_azar.py, con menos entradas) ----------
MALOS = [None, 0, -1, -0.0, 1e-9, 1e12, float("nan"), float("inf"), True, "10", [], {}]


def _entrada_al_azar(azar):
    valor = lambda normal: azar.choice(MALOS) if azar.random() < 0.04 else normal()
    x, y = valor(lambda: azar.uniform(1, 45)), valor(lambda: azar.uniform(1, 45))
    k = {}
    if azar.random() < 0.3:
        k["x_ef"], k["y_ef"] = valor(lambda: azar.uniform(1, 45)), valor(lambda: azar.uniform(1, 45))
    if azar.random() < 0.2:
        k["prof_ef"] = valor(lambda: azar.uniform(0, 35))
    if azar.random() < 0.4:
        k["punto_x"], k["punto_y"] = valor(lambda: azar.uniform(-25, 25)), valor(lambda: azar.uniform(-25, 25))
    if azar.random() < 0.3:
        k["centro_x"], k["centro_y"] = valor(lambda: azar.uniform(-20, 20)), valor(lambda: azar.uniform(-20, 20))
    if azar.random() < 0.3:
        k["cuna"], k["cuna_orientacion"] = azar.choice([15, 30, 45, 60, 20]), azar.choice(motor.ORIENTACIONES)
    if azar.random() < 0.1:
        k["wf_manual"] = valor(lambda: azar.uniform(0.05, 1.2))
    if azar.random() < 0.1:
        k["oar_manual"] = valor(lambda: azar.uniform(0.6, 1.3))
    if azar.random() < 0.1:
        k["tf"] = valor(lambda: azar.uniform(0.4, 1.1))
    if azar.random() < 0.3:
        k["um_planeador"] = valor(lambda: azar.uniform(1, 500))
    return E(valor(lambda: azar.uniform(1, 300)), x, y, valor(lambda: azar.uniform(55, 145)), valor(lambda: azar.uniform(0, 35)), **k)


def test_al_azar_el_motor_da_un_numero_valido_o_dice_por_que(datos):
    """20 000 entradas, con valores imposibles mezclados: o un número finito y positivo, o `NoCalculable`; ninguna otra salida."""
    azar, numeros, rechazos = random.Random(20261105), 0, 0
    for _ in range(20_000):
        try:
            r = motor.calcular(datos, _entrada_al_azar(azar))
        except motor.NoCalculable:
            rechazos += 1
            continue
        assert math.isfinite(r.um) and r.um > 0 and math.isfinite(r.d_um) and all(math.isfinite(f.valor) for f in r.factores)
        numeros += 1
    assert (numeros, rechazos) == NUMEROS_Y_RECHAZOS_AL_AZAR


def test_al_azar_un_archivo_cortado_impide_guardar_o_da_las_mismas_um(archivos):
    """H14: un archivo cortado (8 cortes al azar en cada archivo que lee el cálculo, y el name.data en cada final de línea, donde UM1-D8 lo acepta con
    menos parámetros): o la carga no deja guardar, o las UM son las de siempre, o no hay número. Nunca otro número."""
    nombres = sorted(os.listdir(DATOS))
    pares = list(zip(nombres, archivos))
    casos = [E(100.0, 10.0, 10.0, 100.0, 10.0), E(100.0, 15.0, 20.0, 90.0, 12.0), E(100.0, 20.0, 20.0, 100.0, 15.0, punto_x=6.0), E(100.0, 12.0, 15.0, 95.0, 15.0, cuna=15),
             E(100.0, 40.0, 40.0, 100.0, 20.0, punto_x=15.0), E(100.0, 4.0, 4.0, 100.0, 20.0, cuna=15)]
    base = um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0)
    esperadas = [motor.calcular(base, c).um for c in casos]
    azar = random.Random(20261108)
    cortes = [(n, azar.randint(1, len(t) - 1)) for n, t in pares if lector.identidad(t).dato in um_armar.TIPOS_QUE_LEE_EL_MOTOR for _ in range(8)]
    name_data = dict(pares)["name.data"]
    cortes += [("name.data", k + 1) for k, letra in enumerate(name_data[:-1]) if letra == "\n"]
    cuentas = {"impide guardar": 0, "las mismas UM": 0, "sin número": 0}
    for nombre, corte in cortes:
        cortados = [(n, t[:corte] if n == nombre else t) for n, t in pares]
        if um_armar.revisar_archivos(cortados, "Clinac 600", "6 MV", d0_dmax=1.0).problemas:
            cuentas["impide guardar"] += 1
            continue
        haz = um_armar.datos_haz([t for _, t in cortados], "Clinac 600", "6 MV", d0_dmax=1.0)
        for c, um in zip(casos, esperadas):
            try:
                assert motor.calcular(haz, c).um == pytest.approx(um, rel=1e-12), (nombre, corte, c)
                cuentas["las mismas UM"] += 1
            except motor.NoCalculable:
                cuentas["sin número"] += 1
    assert cuentas == CORTES_AL_AZAR


NUMEROS_Y_RECHAZOS_AL_AZAR = (2025, 17975)   # medido: (2014, 17986) hasta la v2 de la primera vuelta; 11 rechazos menos en la segunda (A2: con láminas, el rectángulo escalado no se lee)
CORTES_AL_AZAR = {"impide guardar": 106, "las mismas UM": 98, "sin número": 10}   # 124 cortes; los 18 que la carga acepta son finales de línea del name.data


# ---------- UM.2 v2: los 41 hallazgos de la auditoría previa del 08-11 (borradores/UM2/v2/auditoria_previa_resultado.json). Cada caso cae contra la v1 ----------
OPD, OPP, OF_ABIERTA = PDD_ABIERTO, PERFILES, "CLINAC 600C_Open Field - 00_Output Factors.txt"
WDD15, OF30 = "CLINAC 600C_Standard Wedge - 15_Measured Wedge Depth Doses.txt", "CLINAC 600C_Standard Wedge - 30_Output Factors.txt"


def _pares(archivos):
    return list(zip(sorted(os.listdir(DATOS)), archivos))


def _cambiado(pares, nombre, nuevo):
    return [(n, nuevo if n == nombre else t) for n, t in pares]


def _tras(texto_de_archivo, marca, viejo, nuevo):
    """El texto con la primera aparición de `viejo` DESPUÉS de `marca` cambiada por `nuevo`."""
    i = texto_de_archivo.index(marca)
    j = texto_de_archivo.index(viejo, i)
    return texto_de_archivo[:j] + nuevo + texto_de_archivo[j + len(viejo):]


@pytest.mark.parametrize("archivo, viejo, nuevo, motivo", [      # DR-1, DR-2, DR-3 (estudio A1, casos.md F1 a F16): un carácter que el lector acepta
    (OPD, "+150.0 +052.800>", "+150.0 +05.800>", r"^el PDD abierto de .*un valor está dañado$"),            # DR-2: +167.8 % de UM sin aviso
    (OPD, "+150.0 +052.800>", "+150.0 +042.800>", r"^el PDD abierto de .*un valor está dañado$"),
    (OPD, "+046.0 +086.300>", "+046.0 +086300>", r"^el PDD abierto de .* tiene su máximo en 86300 \[%\]"),  # DR-1: un punto decimal borrado
    (OPD, "+300.0 +021.700>", "+300.0 +02.700>", r"^el PDD abierto de 10 × 10 \[cm\] se aparta .* en z = 29.9 \[cm\]"),
    (WDD15, "+050.0 +086.300>", "+050.0 +086300>", r"^el PDD con la cuña de 15° de 10 × 10 \[cm\] tiene su máximo en 86300"),   # DR-1: +678 % sin aviso
    (OPP, "+100.0 +072.570>", "+100.0 +072570>", r"^el perfil abierto de 40 × 40 \[cm\] a 10 \[cm\] de profundidad tiene un OAR de .*no puede pasar de 1.2"),
    (OPP, "<+055.0 +000.0 +100.0 +072.570>", "<+055.0 +000.0 +100.0 +062.570>", r"^el perfil abierto de 40 × 40 \[cm\] a 10 \[cm\] de profundidad tiene un pico en x = 5\.\d+ \[cm\], dentro del campo"),
    (OPP, "<+055.0 +000.0 +100.0 +072.570>", "<+055.0 +000.0 +100.0 +000.000>", r"tiene un OAR de 0 en x = 5.5 \[cm\], y debe ser mayor que 0"),
    (OPP, "<+055.0 +000.0 +100.0 +072.570>", "<+095.3 +000.0 +100.0 +072.570>", r"sus puntos no van en posición creciente \(x = 9.53 \[cm\]"),
    (OPP, "%SSD 1000", "%SSD 1100", r"^los perfiles abiertos deben decir una sola SSD y dicen 100 \[cm\], 110 \[cm\]"),            # DR-3: +2.7 % fuera del eje
    (OPP, "%SSD 1000", "%SSD 950", r"una sola SSD y dicen 95 \[cm\], 100 \[cm\]"),        # en orden (un conjunto de 100 y 95 los daría al revés)
    (OF_ABIERTA, "0.951, 0.950, 0.950\n", "0.951, 0.950, 1.950\n", r"^la tabla abierta salta entre la celda .* y la Y = 4 \[cm\], X = 40 \[cm\] \(valor 1.95\)"),
    (OF_ABIERTA, ", 0.951, 0.950, 0.950\n", ", 0.51, 0.950, 0.950\n", r"^la tabla abierta "),
    (OF30, "0.911, 0.912, 0.914, 0.916", "0.911, 0.512, 0.914, 0.916", r"^la tabla de la cuña de 30° "),
    (OF_ABIERTA, "\n10, 0.918, 0.930, 0.950, 0.964, 0.973, 1.000, 1.013,", "\n10, 0.918, 0.930, 0.950, 0.964, 0.973, 1.000, 1.040,",   # sin salto, fuera de la recta
     r"^la tabla abierta: el valor en Y = 10 \[cm\], X = 15 \[cm\] se aparta 2.\d+ \[%\] de lo que dicen sus dos vecinas"),
])
def test_un_valor_imposible_de_una_curva_o_una_tabla_impide_guardar(archivos, archivo, viejo, nuevo, motivo):
    pares = _pares(archivos)
    r = um_armar.revisar_archivos(_cambiado(pares, archivo, _una_vez(dict(pares)[archivo], viejo, nuevo)), "Clinac 600", "6 MV", d0_dmax=1.0,
                                  wf_escritos={15: 0.77, 30: 0.6, 45: 0.5, 60: 0.4})
    assert len(r.problemas) == 1 and re.search(motivo, r.problemas[0]), r.problemas


def test_las_barreras_que_los_datos_del_600c_no_alcanzan():
    """El último punto de un PDD con un paso final largo (la recta de sus vecinos casi no lo ve) y un pico en la penumbra de un perfil: lo que la rejilla de 1 mm del
    600C nunca deja ver, con curvas armadas a mano."""
    import services.um_plausibilidad as plausibilidad
    z = np.concatenate((np.arange(1.5, 20.01, 1.0), [30.0]))
    recto = lector.Curva((10.0, 10.0), 100.0, np.zeros(len(z)), z, 100.0 - 2.5 * (z - 1.5))
    plausibilidad.revisar_pdd_abiertos([recto])
    roto = lector.Curva((10.0, 10.0), 100.0, recto.x_cm, z, np.concatenate((recto.valor[:-1], [recto.valor[-1] - 3.0])))
    with pytest.raises(plausibilidad.BarreraDePlausibilidad, match=r"^el último punto del PDD abierto de 10 × 10 \[cm\] \(z = 30 \[cm\]\) se aparta 3 \[%\]"):
        plausibilidad.revisar_pdd_abiertos([roto])
    x = np.arange(0.0, 15.01, 0.5)
    oar = np.clip(1.0 - np.maximum(x - 10.0, 0.0) * 0.15, 0.05, 1.0)      # plano en el núcleo (hasta 9 cm: el borde, 11, menos 2)
    plausibilidad.revisar_perfil(motor.PerfilOAR(10.0, 20.0, x, oar))
    with pytest.raises(plausibilidad.BarreraDePlausibilidad, match=r"^el perfil abierto de 20 × 20 \[cm\] a 10 \[cm\] de profundidad tiene un pico en x = 11.5 \[cm\]: "):
        plausibilidad.revisar_perfil(motor.PerfilOAR(10.0, 20.0, x, np.where(x == 12.0, oar + 0.3, oar)))


def test_un_pdd_con_cuna_real_que_termina_antes_se_acepta(archivos):
    """H-UM2-16: el WDD de 45° del 600C medido solo hasta 13.4 cm: su 10 × 10 termina en un punto real que se aparta 1.7 % de la recta de los dos anteriores (el ruido
    de un decimal en 1 mm). Con el umbral de A1 (0.8 %) un archivo real exportado hasta ahí no cargaba; con el de la v2 (2.5 %) carga y da las mismas betas de lo medido."""
    wdd = es_de(archivos, "Standard Wedge - 45", "data: WDD\n")
    d = um_armar.datos_haz(cambiar(archivos, wdd, _wdd_hasta(wdd, 134)), "Clinac 600", "6 MV", d0_dmax=1.0)
    assert d.cunas[45].prof_max_cm == pytest.approx(13.4)


def _pdd_de(v, z=None):
    v = np.asarray(v, float)
    z = np.arange(0.5, 0.5 * len(v) + 0.25, 0.5) if z is None else np.asarray(z, float)
    return lector.Curva((10.0, 10.0), 100.0, np.zeros(len(z)), z, v)


def _bajada(n=30, maximo=100.0):
    """Un PDD de mentira: sube hasta su máximo en z = 1.5 cm y baja 2 [%] cada 0.5 cm (recto: ninguna barrera lo ve)."""
    return np.array([90.0, 95.0] + [maximo - 2.0 * i for i in range(n - 2)])


def _plano_tras_el_maximo(sube_en=16, salto=0.0):
    """Sube hasta 100 en z = 1.5, baja hasta 91 en 3 cm y sigue plano (con un escalón de `salto` en el punto `sube_en`)."""
    v = np.array([90.0, 95.0, 100.0, 97.0, 94.0] + [91.0] * 25)
    v[sube_en:] += salto
    return v


def _con_un_punto(v, i, cambio):
    v = np.array(v, float)
    v[i] += cambio
    return v


def _perfil_de(oar, x=None, lado=20.0):
    x = np.arange(0.0, 0.5 * len(oar) - 0.25, 0.5) if x is None else np.asarray(x, float)
    return motor.PerfilOAR(10.0, lado, x, np.asarray(oar, float))


def _tabla_de(m, x=(2.0, 4.0, 8.0, 16.0), y=(2.0, 4.0, 8.0, 16.0)):
    return lector.TablaOF(np.array(x), np.array(y), np.asarray(m, float), 100.0, 5.0)


_Z_HASTA_20_CM = np.concatenate((np.arange(0.5, 10.25, 0.5), [20.0]))     # el último paso, de 10 cm: la recta de sus vecinos casi no ve el último punto


def _recta_hasta_20_cm():
    return np.where(_Z_HASTA_20_CM < 1.5, 90.0 + 5.0 * (_Z_HASTA_20_CM - 0.5) / 0.5, 100.0 - 4.0 * (_Z_HASTA_20_CM - 1.5))


_LADOS_RAROS = (2.0, 30.0, 32.0, 34.0)      # dos celdas de dentro muy juntas: una celda de borde que se mueve casi no mueve la recta de las de dentro
_UMBRALES = {   # (qué se revisa, cómo se arma con el umbral × f): a × 0.995 debe pasar y a × 1.005 no (fija cada umbral, también contra un 1 % de cambio)
    "máximo del PDD abierto": ("abiertos", lambda f: _bajada(maximo=100.0 + 0.5 * f)),
    "máximo del PDD con cuña": ("cuña", lambda f: _bajada(maximo=100.0 + 1.0 * f)),
    "salto en la zona del máximo": ("abiertos", lambda f: _con_un_punto(_bajada(), 4, 2.0 + 1.0 * f)),
    "salto fuera de la zona, abierto": ("abiertos", lambda f: _plano_tras_el_maximo(salto=0.3 * f)),
    "salto fuera de la zona, con cuña": ("cuña", lambda f: _plano_tras_el_maximo(salto=0.6 * f)),
    "desvío en la cola, abierto": ("abiertos", lambda f: _con_un_punto(_bajada(), 12, -0.6 * f)),
    "desvío en la cola, con cuña": ("cuña", lambda f: _con_un_punto(_bajada(), 12, -1.3 * f)),
    "último punto, abierto": ("abiertos", lambda f: (_recta_hasta_20_cm(), _Z_HASTA_20_CM, -1.2 * f)),
    "último punto, con cuña": ("cuña", lambda f: (_recta_hasta_20_cm(), _Z_HASTA_20_CM, -2.5 * f)),
    "OAR máximo": ("perfil", lambda f: 1.0 + (1.2 * f - 1.0) * np.arange(31) / 30),
    "pico en el núcleo": ("perfil", lambda f: _con_un_punto(np.ones(31), 8, 0.008 * f)),
    "pico fuera del núcleo": ("perfil", lambda f: _con_un_punto(np.ones(31), 24, 0.05 * f)),
    "pendiente de la tabla, hacia arriba": ("tabla", lambda f: np.tile(np.array([2.0, 4.0, 8.0, 16.0]) ** (0.35 * f), (4, 1))),
    "pendiente de la tabla, hacia abajo": ("tabla", lambda f: np.tile(np.array([2.0, 4.0, 8.0, 16.0]) ** (-0.08 * f), (4, 1))),
    "celda de dentro fuera de la recta": ("tabla", lambda f: _con_un_punto(np.ones((4, 4)), (1, 1), math.exp(0.025 * f) - 1.0)),
    "celda de borde fuera de la recta": ("tabla raro", lambda f: _con_un_punto(np.ones((4, 4)), (0, 0), math.exp(0.07 * f) - 1.0)),
}


@pytest.mark.parametrize("f, pasa", [(0.995, True), (1.005, False)])
@pytest.mark.parametrize("cual", list(_UMBRALES))
def test_las_barreras_en_sus_umbrales(cual, f, pasa):
    """Cada umbral de `um_plausibilidad` con una curva o una tabla armada a mano justo por debajo y justo por encima (las de los datos reales no llegan cerca)."""
    import services.um_plausibilidad as plausibilidad
    que, armar = _UMBRALES[cual]
    hecho = armar(f)
    if que in ("abiertos", "cuña"):
        v, z, cambio = hecho if isinstance(hecho, tuple) else (hecho, None, 0.0)
        curva = _pdd_de(_con_un_punto(v, -1, cambio) if cambio else v, z)
        revisar = (lambda: plausibilidad.revisar_pdd_abiertos([curva])) if que == "abiertos" else (lambda: plausibilidad.revisar_pdd_con_cuna([curva], 15))
    elif que == "perfil":
        revisar = lambda: plausibilidad.revisar_perfil(_perfil_de(hecho))      # noqa: E731 - lado 20 a 10 cm: el borde, a 11 cm; el núcleo, hasta 9
    else:
        tabla = _tabla_de(hecho, _LADOS_RAROS, _LADOS_RAROS) if que == "tabla raro" else _tabla_de(hecho)
        revisar = lambda: plausibilidad.revisar_tabla(tabla, "la tabla")      # noqa: E731
    if pasa:
        revisar()
    else:
        with pytest.raises(plausibilidad.BarreraDePlausibilidad):
            revisar()


def test_el_borde_del_nucleo_la_zona_del_maximo_y_la_penumbra_en_su_sitio():
    """Dónde empieza el núcleo de un perfil (2 cm antes del borde proyectado: lado 20 a 10 cm, 9 cm), dónde acaba la zona del máximo de un PDD (1.5 cm) y cuánto se
    admite en la penumbra (0.05 más la mitad de lo que se separan los vecinos): a un lado y al otro de cada frontera."""
    import services.um_plausibilidad as plausibilidad

    def revisa(funcion, que, pasa, motivo):
        if pasa:
            funcion(que)
        else:
            with pytest.raises(plausibilidad.BarreraDePlausibilidad, match=motivo):
                funcion(que)
    hasta = np.arange(0.0, 8.75, 0.5)
    for donde, pasa in ((9.0, False), (9.01, True)):      # un pico de 0.012 justo en el borde del núcleo no se admite (0.008); un centésimo más allá, sí (0.05)
        x = np.concatenate((hasta, [donde, 9.5, 10.0]))
        revisa(plausibilidad.revisar_perfil, _perfil_de(np.where(x == donde, 1.012, 1.0), x), pasa, "dentro del campo")
    for z_antes, pasa in ((3.0, True), (3.01, False)):    # una subida de 0.5 [%] que empieza justo a 1.5 cm del máximo es ruido; un centésimo más allá, no
        z = np.array([0.5, 1.0, 1.5, 2.0, 2.5, z_antes, 3.5] + list(np.arange(4.0, 10.01, 0.5)))
        revisa(plausibilidad.revisar_pdd_abiertos, [_pdd_de([90.0, 95.0, 100.0, 97.0, 94.0, 91.0] + [91.5] * 14, z)], pasa, r"sube 0.5 \[%\]")
    for pico, pasa in ((0.1296, True), (0.1301, False)):  # penumbra que baja 0.08 por punto: se admite 0.05 + 0.5·0.16 = 0.13
        oar = np.concatenate((np.ones(20), 1.0 - 0.08 * np.arange(1, 11)))
        oar[25] += pico
        revisa(plausibilidad.revisar_perfil, _perfil_de(oar), pasa, "más de lo que admite la pendiente")


def _revisa(funcion, que, pasa, motivo=""):
    import services.um_plausibilidad as plausibilidad
    if pasa:
        funcion(que)
    else:
        with pytest.raises(plausibilidad.BarreraDePlausibilidad, match=motivo):
            funcion(que)


def test_las_barreras_en_sus_casos_de_forma():
    """Lo que decide cada regla además de su umbral: cuántos puntos tiene la cola, el primer paso de la curva, una profundidad o una posición repetida, el último
    punto de un perfil, un OAR negativo, tablas de dos o tres celdas por eje, las cuatro esquinas y el penúltimo interior de una tabla, el máximo en el primer
    punto, la curvatura natural junto al máximo y la zona del máximo cuando este está hondo; y los umbrales justo en su valor (se admiten)."""
    import services.um_plausibilidad as P
    pdd, cuna, perfil = P.revisar_pdd_abiertos, (lambda c: P.revisar_pdd_con_cuna(c, 15)), P.revisar_perfil
    recta = lambda z: list(100.0 - 4.0 * (np.asarray(z) - 1.5))      # noqa: E731
    z_corta = [0.5, 1.0, 1.5, 2.0, 2.5]
    _revisa(pdd, [_pdd_de([90.0, 95.0, 100.0, 98.0, 93.0], z_corta)], True)                                   # sin cola: el último punto no se mira
    z_uno = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    _revisa(pdd, [_pdd_de([90.0, 95.0] + recta(z_uno[2:-1]) + [85.0], z_uno)], True)                         # un punto en la cola: tampoco
    z_dos = z_uno + [9.0]
    _revisa(pdd, [_pdd_de([90.0, 95.0] + recta(z_dos[2:-1]) + [recta([9.0])[0] - 3.0], z_dos)], False, "el último punto")   # dos: sí
    _revisa(pdd, [_pdd_de([90.0, 95.0, 100.0, 98.0, 96.0], [0.5, 1.0, 1.5, 1.5, 2.0])], False, "no van en profundidad creciente")
    _revisa(pdd, [_pdd_de([95.0, 93.0, 100.0, 98.0, 96.0])], False, "baja 2")                                 # el primer paso también se mira
    _revisa(pdd, [_pdd_de([100.0, 96.0, 92.0, 88.0, 84.0, 80.0, 76.0, 72.0])], True)                          # el máximo en el primer punto
    _revisa(pdd, [_pdd_de([90.0, 95.0, 100.0, 99.0, 96.0, 92.0, 88.0, 84.0])], True)                          # la curvatura junto al máximo no es la cola
    z_hondo = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]                                                  # máximo a 3 cm: la zona va de 1.5 a 4.5 cm
    _revisa(pdd, [_pdd_de([95.0, 94.5, 100.0, 96.0, 92.0, 88.0, 84.0, 80.0, 76.0], z_hondo)], True)           # baja 0.5 entre 1 y 2 cm: dentro de la zona
    _revisa(pdd, [_pdd_de([90.0, 95.0, 100.0, 96.0, 96.5, 92.0, 88.0, 84.0, 80.0], z_hondo)], True)           # sube 0.5 entre 4 y 5 cm: dentro de la zona
    exactos = [(pdd, [90.0, 95.0, 100.0, 97.0, 98.0, 92.0] + [91.0] * 8), (pdd, [90.0, 95.0, 100.0, 50.0, 0.2, 0.2, 0.2, 0.2, 0.5, 0.5, 0.5, 0.5]),
               (cuna, [90.0, 95.0, 100.0, 50.0, 0.4, 0.4, 0.4, 0.4, 1.0, 1.0, 1.0, 1.0]),
               (pdd, [90.0, 95.0, 100.0, 50.0, 10.0, 8.4, 6.8, 5.2, 3.6, 2.0, 0.4, 0.0, 0.0, 0.0]), (cuna, [90.0, 95.0, 100.0, 50.0, 7.8, 6.5, 5.2, 3.9, 2.6, 0.0, 0.0, 0.0])]
    for revisar, v in exactos:       # una subida de 1, 0.3 y 0.6 [%] y un desvío de 0.6 y 1.3 [%] justo en el umbral (las cuentas dan el umbral exacto)
        _revisa(revisar, [_pdd_de(v)], True)
    lejos = np.concatenate((np.arange(0.5, 5.25, 0.5), [15.0]))
    for revisar, ultimo in ((pdd, 0.8), (cuna, -0.5)):    # el último punto, 1.2 y 2.5 [%] por debajo de la recta plana de los dos anteriores
        _revisa(revisar, [_pdd_de([90.0, 95.0, 100.0, 50.0] + [2.0] * 6 + [ultimo], lejos)], True)
    x = np.arange(0.0, 6.25, 0.5)
    _revisa(perfil, _perfil_de(np.where(x == 6.0, 1.15, 1.0), x, lado=10.0), False, "en x = 6 \\[cm\\]: ")     # el último punto medido, con un pico (en la penumbra)
    _revisa(perfil, _perfil_de(np.where(x == 6.0, 1.01, 1.0), x, lado=40.0), True)                         # una curva suave en el último punto se admite
    _revisa(perfil, _perfil_de(np.where(x == 3.0, -0.2, 1.0), x, lado=40.0), False, "debe ser mayor que 0")
    _revisa(perfil, _perfil_de(np.where(x == 0.5, 1.02, 1.0), x, lado=40.0), False, "en x = 0.5 \\[cm\\]")  # el primer punto fuera del eje también se mira
    _revisa(perfil, _perfil_de(np.linspace(1.0, 1.2, 13), x, lado=40.0), True)                         # un OAR de 1.2 justo se admite
    rep = lector.Curva((10.0, 10.0), 100.0, np.array([0.0, 0.5, 0.5, 1.0]), np.full(4, 10.0), np.array([100.0, 99.0, 99.0, 98.0]))
    _revisa(P.revisar_curvas_de_perfiles, [rep], False, "no van en posición creciente")
    tabla = lambda m, x=(2.0, 4.0, 8.0, 16.0), y=(2.0, 4.0, 8.0, 16.0): (lambda: P.revisar_tabla(_tabla_de(m, x, y), "la tabla"))      # noqa: E731
    for filas, columnas in ((2, 4), (4, 2), (2, 2)):      # con dos celdas en un eje no hay recta de vecinas: solo el salto
        tabla(np.ones((filas, columnas)), (2.0, 4.0, 8.0, 16.0)[:columnas], (2.0, 4.0, 8.0, 16.0)[:filas])()
    with pytest.raises(P.BarreraDePlausibilidad, match="sus dos vecinas"):
        tabla(_con_un_punto(np.ones((3, 3)), (1, 1), 0.03), (2.0, 4.0, 8.0), (2.0, 4.0, 8.0))()
    lejos_del_primero, lejos_del_ultimo = _LADOS_RAROS, (2.0, 4.0, 6.0, 34.0)
    for fila, columna in ((0, 0), (0, 3), (3, 0), (3, 3)):        # cada esquina, contra la recta de las dos de dentro
        with pytest.raises(P.BarreraDePlausibilidad, match="las dos celdas de dentro"):
            tabla(_con_un_punto(np.ones((4, 4)), (fila, columna), 0.075), lejos_del_ultimo if columna == 3 else lejos_del_primero,
                  lejos_del_ultimo if fila == 3 else lejos_del_primero)()
    with pytest.raises(P.BarreraDePlausibilidad, match="sus dos vecinas"):
        tabla(_con_un_punto(np.ones((4, 4)), (2, 2), 0.03))()
    for t in ((0.0, 1.0, 1.3, 1.6), (0.0, 0.3, 0.6, 1.6)):        # curvatura en logaritmos: el borde lejano se mira con las DOS de dentro (otra pareja lo rechazaría)
        lados = tuple(float(np.exp(q)) for q in t)
        tabla(np.tile(np.exp(0.049 * np.array(t) ** 2), (4, 1)), lados, lados)()
    z = np.arange(0.5, 10.25, 0.5)
    _revisa(pdd, [_pdd_de(_con_un_punto([90.0, 95.0] + recta(z[2:]), 7, -0.9), z)], False, "en z = 4 \\[cm\\]")   # el PRIMER punto de la cola
    _revisa(pdd, [_pdd_de(100.0 * np.exp(-0.05 * np.arange(20)))], True)        # el máximo en el primer punto y una bajada curva: la cola empieza a 1.5 cm de él
    bueno, roto = _pdd_de(_bajada()), _pdd_de(_con_un_punto(_bajada(), 12, -0.9))
    _revisa(pdd, [bueno, roto], False, "se aparta")                                # la ÚLTIMA curva del archivo también se mira
    _revisa(cuna, [bueno, _pdd_de(_con_un_punto(_bajada(), 12, -1.9))], False, "se aparta")
    desordenada = lector.Curva((10.0, 10.0), 100.0, np.array([0.0, 1.0, 0.5, 1.5]), np.full(4, 10.0), np.full(4, 99.0))
    _revisa(P.revisar_curvas_de_perfiles, [rep.__class__((10.0, 10.0), 100.0, np.array([0.0, 0.5, 1.0]), np.full(3, 10.0), np.ones(3)), desordenada], False, "posición creciente")
    _revisa(P.revisar_curvas_de_perfiles, [rep.__class__((10.0, 10.0), 100.0, np.array([0.0, 0.5]), np.full(2, 10.0), np.ones(2)),
                                           rep.__class__((10.0, 10.0), 95.0, np.array([0.0, 0.5]), np.full(2, 10.0), np.ones(2))], False, "dicen 95 \\[cm\\], 100 \\[cm\\]")
    x = np.arange(0.0, 6.25, 0.5)
    _revisa(perfil, _perfil_de(np.where(x == 5.5, 1.01, 1.0), x, lado=40.0), False, "en x = 5.5 \\[cm\\], dentro del campo")   # el penúltimo, en el núcleo, estricto
    x_cola = np.concatenate((np.arange(0.0, 9.25, 0.5), [14.0]))                  # el último punto se mira con los DOS anteriores, no con otros
    _revisa(perfil, _perfil_de(np.where(x_cola == 8.0, 1.03, 1.0), x_cola, lado=10.0), True)
    z_cola = np.concatenate((np.arange(0.5, 11.25, 0.5), [21.0]))                # el último punto del PDD, igual: la recta de los dos anteriores
    v_cola = np.array([90.0, 95.0] + recta(z_cola[2:]))
    v_cola[-4] += 0.5
    _revisa(pdd, [_pdd_de(v_cola, z_cola)], True)
    _revisa(perfil, _perfil_de(np.where(np.arange(13) == 6, 0.016, 0.008), x, lado=40.0), True)   # un pico de 0.008 justo, en el núcleo (las cuentas dan 0.008 exacto)
    _revisa(perfil, _perfil_de(np.where(np.arange(13) == 6, 0.1, 0.05), x, lado=2.0), True)       # y uno de 0.05 justo fuera de él
    _revisa(perfil, _perfil_de(np.concatenate((np.ones(11), [0.9, 0.8])), x, lado=10.0), True)        # el penúltimo se mira entre sus dos vecinos, no hacia atrás
    for lados_x, valores in (((1.0, 5792.618751480199), (1.0, 0.5)), ((1.0, 1.037584107392455), (1.0, 1.0129969992498122))):   # pendientes de −0.08 y 0.35 exactas
        tabla(np.tile(valores, (2, 1)), lados_x, (1.0, 2.0))()
    m0, centro = 1.0052059425593252, 1.0306528521470866                          # una celda de dentro a 2.5 [%] exactos (en logaritmo) de sus vecinas
    tabla(np.where(np.arange(9).reshape(3, 3) == 4, centro, m0), (2.0, 4.0, 8.0), (2.0, 4.0, 8.0))()
    m0, esquina = 1.002100221986995, 1.0747606865177186                          # una esquina a 7 [%] exactos de la recta de las de dentro
    tabla(np.where(np.arange(16).reshape(4, 4) == 0, esquina, m0), _LADOS_RAROS, _LADOS_RAROS)()


def test_el_pdd_con_cuna_del_campo_entero_tambien_se_revisa(archivos):
    """El 40 × 20 de la cuña de 15° no entra en el ajuste, y antes nadie miraba sus puntos (estudio A1, F16)."""
    pares = _pares(archivos)
    roto = _tras(dict(pares)[WDD15], "%FLSZ 400*200", "+000.0 +000.0 +050.0 ", "+000.0 +000.0 +005.0 ")
    r = um_armar.revisar_archivos(_cambiado(pares, WDD15, roto), "Clinac 600", "6 MV", d0_dmax=1.0)
    assert r.problemas == ("el PDD con la cuña de 15° de 40 × 20 [cm]: sus puntos no van en profundidad creciente (z = 4.8 [cm] y luego 0.5 [cm]): una profundidad "
                           "está dañada",)


def test_un_pdd_con_su_maximo_en_99_6_da_las_mismas_um(archivos, datos):
    """S-2: D'0 se lleva de dmax a d0 con el máximo medido del 10 × 10, no con un 100 supuesto (antes, −0.40 % en todas las UM sin aviso)."""
    pares = dict(_pares(archivos))
    escalado = re.sub(r"^<(\S+ \S+ \S+) \+(\d+\.\d+)>$", lambda m: f"<{m.group(1)} +{float(m.group(2)) * 0.996:07.3f}>", pares[OPD], flags=re.M)
    assert "+099.600>" in escalado and "+100.000>" not in escalado
    d = um_armar.datos_haz([escalado if n == OPD else t for n, t in pares.items()], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert d.d0_norm == pytest.approx(0.86, rel=1e-12)
    for e in (E(200.0, 10.0, 10.0, 100.0, 10.0), E(200.0, 15.0, 15.0, 110.0, 15.0, punto_x=5.0)):
        assert motor.calcular(d, e).um == pytest.approx(motor.calcular(datos, e).um, rel=1e-4)


A2_CASOS = [   # estudio A2, casos.md: mandíbulas, efectivo y las UM esperadas a mano (200 cGy, SSD 100, d = 10, el 600C con la curva de Sc por omisión)
    ((20.0, 20.0), (15.0, 8.0), 296.11), ((20.0, 20.0), (8.0, 15.0), 296.11), ((20.0, 20.0), (240 / 23, 240 / 23), 296.11),
    ((32.0, 32.0), (30.0, 10.0), 280.38), ((32.0, 32.0), (10.0, 30.0), 280.38), ((40.0, 40.0), (40.0, 5.0), 298.21), ((40.0, 40.0), (5.0, 40.0), 298.21),
    ((30.0, 10.0), (20.0, 8.0), 297.32), ((10.0, 30.0), (8.0, 20.0), 294.17), ((30.0, 10.0), (80 / 7, 80 / 7), 297.32),
    ((5.0, 40.0), (5.0, 30.0), 308.50), ((5.0, 40.0), (60 / 7, 60 / 7), 308.50),
]


@pytest.mark.parametrize("mandibulas, efectivo, esperado", A2_CASOS)
def test_con_laminas_la_um_no_depende_del_giro_ni_de_escribir_el_cuadrado(datos, mandibulas, efectivo, esperado):
    """F-FIS-1 (UM2-D9): con láminas el factor de campo se lee en el cuadrado equivalente del efectivo y el Sc se lleva al de las mandíbulas con su intercambio,
    E = OF(X, Y)/OF(rc, rc). Antes se leía el rectángulo de láminas como si fueran mandíbulas: hasta +1.9 % según el giro, sin aviso."""
    r = motor.calcular(datos, E(200.0, *mandibulas, 100.0, 10.0, x_ef=efectivo[0], y_ef=efectivo[1]))
    assert r.um == pytest.approx(esperado, rel=2e-4)
    assert factor(r, "Sc(rc)/Sc(lectura)") == pytest.approx(motor.correccion_sc(datos.sc, motor.equivalente(*mandibulas), r.campos["x_lectura"])
                                                            * datos.of(*mandibulas) / datos.of(motor.equivalente(*mandibulas), motor.equivalente(*mandibulas)), rel=1e-12)
    assert r.campos["x_lectura"] == r.campos["y_lectura"] == pytest.approx(motor.equivalente(*efectivo), rel=1e-12)
    assert "intercambio X/Y de las mandíbulas" in _origen(r, "Sc(rc)/Sc(lectura)")[1] and "cuadrado equivalente del campo efectivo" in _origen(r, "OF")[1]


def test_el_efectivo_igual_a_las_mandibulas_es_el_campo_de_las_mandibulas(datos):
    """S-1: el efectivo escrito igual a las mandíbulas (o, si son cuadradas, como su lado) da las MISMAS UM y los MISMOS avisos que sin efectivo; antes se
    perdía el aviso de la pérdida junto al borde (hasta −12 % estimado, sin ningún aviso). Y el 4A/P de unas mandíbulas rectangulares también."""
    azar = random.Random(2026)
    casos = [(20.0, 20.0, dict(punto_x=8.0)), (10.0, 10.0, dict(punto_x=3.0)), (15.0, 15.0, dict(centro_x=3.0, punto_x=8.0)), (10.0, 20.0, dict(punto_x=3.0))]
    casos += [(azar.uniform(3, 40), azar.uniform(3, 40), dict(punto_x=azar.uniform(-12, 12), punto_y=azar.uniform(-12, 12), prof=azar.uniform(3, 20),
                                                              ssd=azar.uniform(80, 120))) for _ in range(300)]
    comparados = 0
    for x, y, kw in casos:
        base = dict(dosis=200.0, x=x, y=y, ssd=100.0, prof=10.0, **kw) if "ssd" not in kw else dict(dosis=200.0, x=x, y=y, **kw)
        try:
            sin = motor.calcular(datos, E(**base))
        except motor.NoCalculable as fallo:
            for ef in ((x, y), (motor.equivalente(x, y),) * 2):
                with pytest.raises(type(fallo)):
                    motor.calcular(datos, E(**base, x_ef=ef[0], y_ef=ef[1]))
            continue
        for ef in ((x, y), (motor.equivalente(x, y),) * 2):
            con = motor.calcular(datos, E(**base, x_ef=ef[0], y_ef=ef[1]))
            assert (con.um, con.avisos) == (sin.um, sin.avisos), (x, y, kw, ef)
        comparados += 1
    assert comparados > 150 and "la dosis cambiaría" in avisos_de(datos, 200.0, 20.0, 20.0, 100.0, 10.0, punto_x=8.0, x_ef=20.0, y_ef=20.0)


def test_un_cuadrado_equivalente_mas_ancho_que_la_mandibula_corta_es_un_campo_alargado(datos):
    """S-3: unas mandíbulas de 5 × 40 con un efectivo de 8.57 × 8.57 (el 4A/P de 5 × 30) son una abertura de por lo menos 6 : 1."""
    assert "alargado" in avisos_de(datos, 200.0, 5.0, 40.0, 100.0, 10.0, x_ef=60 / 7, y_ef=60 / 7)
    assert "alargado" in avisos_de(datos, 200.0, 4.0, 40.0, 100.0, 10.0, x_ef=7.27, y_ef=7.27)
    assert "alargado" not in avisos_de(datos, 200.0, 10.0, 20.0, 100.0, 10.0, x_ef=8.0, y_ef=8.0)


@pytest.fixture(scope="module")
def mundo_con_intercambio():
    """El mundo simulado con el intercambio de las mandíbulas calibrado con la tabla real (estudio A2) y el maniquí por 4A/P, con el Sc verdadero."""
    w = ms.Mundo("loglineal", "4A/P")
    z, pdd, of, d0_dmax = w.tablas_medidas(LADOS_SIMULADOS, LADOS_SIMULADOS, LADOS_SIMULADOS)
    lados = np.array(LADOS_SIMULADOS, float)
    familia = motor.FamiliaPDD(lados, z, pdd)
    sc = tuple((float(s), ms.sc_cuadrado(float(s))) for s in LADOS_SIMULADOS)
    return w, motor.DatosHaz("Simulado", "6 MV", 100.0, 5.0, motor.d0_en_normalizacion(familia, d0_dmax, 5.0), familia, motor.TablaFactores(lados, lados, of), sc=sc)


def test_el_mundo_con_intercambio_y_laminas_no_depende_del_giro(mundo_con_intercambio):
    """B (UM2-D9): 288 campos con láminas en mandíbulas cuadradas y alargadas, en los dos giros. Medido (v2): máximo 0.12 % y ninguna dependencia del giro; la
    v1 daba 0.71 % y 0.80 % entre un giro y el otro. En el mundo original (maniquí por el rectángulo), el giro tampoco cuenta ya."""
    w, datos = mundo_con_intercambio
    errores, giros = [], []
    for (x, y), (a, b), ssd, d in itertools.product([(20, 20), (30, 30), (30, 10), (10, 30), (40, 10), (10, 40), (25, 15), (15, 25)],
                                                    [(15, 8), (8, 15), (12, 6), (6, 12), (10, 10)], (90, 100, 110), (5, 10, 20)):
        if a > x or b > y:
            continue
        um = motor.calcular(datos, E(200.0, x, y, ssd, d, x_ef=a, y_ef=b)).um
        errores.append(100 * (um * w.dosis_por_um(x, y, a, b, ssd, d) / 200.0 - 1))
        if x == y:
            giros.append(abs(um / motor.calcular(datos, E(200.0, x, y, ssd, d, x_ef=b, y_ef=a)).um - 1))
    assert len(errores) == 288 and np.abs(errores).max() <= 0.2 and max(giros) <= 1e-12


def test_en_el_mundo_original_el_giro_de_las_laminas_tampoco_cuenta(mundo):
    for ssd, d in ((100, 10), (90, 15)):
        a = motor.calcular(mundo[1], E(200.0, 30.0, 30.0, ssd, d, x_ef=20.0, y_ef=8.0)).um
        assert a == pytest.approx(motor.calcular(mundo[1], E(200.0, 30.0, 30.0, ssd, d, x_ef=8.0, y_ef=20.0)).um, rel=1e-12)


def test_dos_accesorios_que_son_la_misma_cuna_no_se_pisan(archivos):
    """DR-4: «Standard Wedge - 15» y «Standard Wedge - 015» son la cuña de 15°: antes la que llegaba última pisaba a la otra (−2.3 % según el orden)."""
    pares = [(n.replace("Wedge - 30", "Wedge - 015"), t.replace("add on: Standard Wedge - 30", "add on: Standard Wedge - 015")) for n, t in _pares(archivos)]
    for orden in (pares, pares[::-1]):
        r = um_armar.revisar_archivos(orden, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={15: 0.77})
        assert len(r.problemas) == 1 and r.problemas[0].endswith(": son la misma cuña de 15°, con dos nombres")
        assert "CLINAC 600C_Standard Wedge - 015_Output Factors.txt («Standard Wedge - 015»)" in r.problemas[0] and "(«Standard Wedge - 15»)" in r.problemas[0]
    with pytest.raises(lector.ArchivoNoReconocido, match="«Standard Wedge - 015» y «Standard Wedge - 15» son la misma cuña de 15°"):
        um_armar.datos_haz([t for _, t in pares], "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={15: 0.77})


def test_la_revision_de_las_cunas_dice_todo_y_en_orden(archivos):
    """Lo que el barrido del armado dejó ver: el motivo de dos accesorios que son la misma cuña nombra TODOS sus archivos; con dos ángulos repetidos se dice
    primero el menor; una cuña sin su tabla lo dice; una cuña incompleta no se lleva los archivos de otra, estén donde estén en la lista."""
    pares = _pares(archivos)
    dos = [(n.replace("Wedge - 30", "Wedge - 015").replace("Wedge - 60", "Wedge - 045"),
            t.replace("add on: Standard Wedge - 30", "add on: Standard Wedge - 015").replace("add on: Standard Wedge - 60", "add on: Standard Wedge - 045")) for n, t in pares]
    primero_la_de_45 = sorted(dos, key=lambda p: "Wedge - 045_Output" not in p[0])      # el ángulo de 45° aparece antes que el de 15°
    with pytest.raises(lector.ArchivoNoReconocido, match="son la misma cuña de 15°"):
        um_armar.datos_haz([t for _, t in primero_la_de_45], "Clinac 600", "6 MV", d0_dmax=1.0)
    solo = [(n, t) for n, t in _pares(archivos) if "Wedge - 15_" in n or "Wedge - 30_" in n or "Open Field" in n]
    solo = [(n.replace("Wedge - 30", "Wedge - 015"), t.replace("add on: Standard Wedge - 30", "add on: Standard Wedge - 015")) for n, t in solo]
    r = um_armar.revisar_archivos(sorted(solo, key=lambda p: "Wedge" not in p[0]), "Clinac 600", "6 MV", d0_dmax=1.0)      # las cuñas primero
    assert r.problemas == ("CLINAC 600C_Standard Wedge - 15_Measured Wedge Depth Doses.txt («Standard Wedge - 15») y CLINAC 600C_Standard Wedge - 15_Output Factors.txt "
                           "(«Standard Wedge - 15») y CLINAC 600C_Standard Wedge - 015_Measured Wedge Depth Doses.txt («Standard Wedge - 015») y CLINAC 600C_Standard Wedge - "
                           "015_Output Factors.txt («Standard Wedge - 015»): son la misma cuña de 15°, con dos nombres",)      # en el orden en que llegan
    sin_tabla = [(n, t) for n, t in pares if not ("Wedge - 30" in n and "Output Factors" in n)]
    assert "Cuña de 30°: falta su tabla de factores; sus archivos no se usan y sus campos se escriben a mano." in um_armar.revisar_archivos(sin_tabla, "Clinac 600", "6 MV", d0_dmax=1.0).avisos
    sin_wdd = [(n, t) for n, t in pares if not ("Wedge - 45" in n and "Depth Doses" in n)]
    tabla_45 = next(p for p in sin_wdd if "Wedge - 45_Output" in p[0])
    for orden in ([tabla_45] + [p for p in sin_wdd if p is not tabla_45], [p for p in sin_wdd if p is not tabla_45] + [tabla_45]):
        r = um_armar.revisar_archivos(orden, "Clinac 600", "6 MV", d0_dmax=1.0)
        assert r.problemas == () and len(r.usados) == 10 and tabla_45[0] in r.ignorados and not set(r.usados) & set(r.ignorados)


def test_el_mismo_archivo_elegido_dos_veces_se_usa_una_vez(archivos):
    """IF-6: una copia idéntica con otro nombre va a `ignorados` con su aviso (UM.3 guarda los usados por (accesorio, dato))."""
    pares = _pares(archivos)
    r = um_armar.revisar_archivos(pares + [("copia/" + OPD, dict(pares)[OPD])], "Clinac 600", "6 MV", d0_dmax=1.0)
    assert r.problemas == () and r.usados == um_armar.revisar_archivos(pares, "Clinac 600", "6 MV", d0_dmax=1.0).usados and r.ignorados[-1] == "copia/" + OPD
    assert f"copia/{OPD}: es copia idéntica de {OPD}: se usa una sola vez." in r.avisos


def test_el_origen_de_la_curva_de_sc_dice_lo_que_hace_el_numero(archivos):
    """IF-1, L-UM2-1, S-4, IF-4: una curva escrita sin origen es «curva de Sc escrita» (antes «sin corrección» y «Sc se corrige con nada» con un factor de 1.02);
    () o [] es «corrección de Sc apagada»; None es la de omisión."""
    e = E(200.0, 20.0, 20.0, 100.0, 10.0, x_ef=10.0, y_ef=10.0)
    escrita = um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, sc=[(4, 0.96), (10, 1.0), (40, 1.04)])
    r = motor.calcular(escrita, e)
    assert factor(r, "Sc(rc)/Sc(lectura)") == pytest.approx(1.02) and _origen(r, "Sc(rc)/Sc(lectura)")[1].startswith("rc = 20.00 [cm]; lectura = 10.00 [cm]; curva de Sc escrita;")
    assert any("mandíbulas (curva de Sc escrita)" in a for a in r.avisos) and not any("nada" in a for a in r.avisos)
    um = {}
    for sc in ([], (), None):
        d = um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, sc=sc)
        r = motor.calcular(d, e)
        um[repr(sc)] = r.um
        texto_esperado = "corrección de Sc apagada" if sc is not None else "estimada de la tabla de este haz y el Sp de la TG-71"
        assert motor.origen_de_sc(d) == texto_esperado and texto_esperado in _origen(r, "Sc(rc)/Sc(lectura)")[1]
        assert f"Curva de Sc: {texto_esperado}." in um_armar.revisar_archivos(_pares(archivos), "Clinac 600", "6 MV", d0_dmax=1.0, sc=sc).avisos
    assert um["[]"] == um["()"] and um["[]"] / um["None"] == pytest.approx(1.0154, abs=1e-4)
    assert "Curva de Sc: curva de Sc escrita." in um_armar.revisar_archivos(_pares(archivos), "Clinac 600", "6 MV", d0_dmax=1.0, sc=[(4, 0.96), (10, 1.0)]).avisos
    assert um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, sc=[(4, 0.96), (10, 1.0)], sc_origen="medida en 2026").sc_origen == "medida en 2026"
    assert um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, sc=[], sc_origen="medida en 2026").sc_origen == motor.SC_APAGADA
    armado_a_mano = um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0)       # un DatosHaz hecho sin `datos_haz`: el texto sale de lo que hace el número
    assert motor.origen_de_sc(dataclasses.replace(armado_a_mano, sc=())) == motor.SC_APAGADA
    assert motor.origen_de_sc(dataclasses.replace(armado_a_mano, sc_origen="")) == motor.SC_ESCRITA


def test_la_energia_y_el_equipo_se_comparan_por_su_clave(archivos):
    """IF-3: «6X», «6MV» y «6 mv» son «6 MV» (antes la curva de Sc por omisión pasaba en silencio a la tabla IV: −0.47 %); unos archivos de otra máquina u otra
    energía ya no los acepta `datos_haz` (UM.3 lo llama sin `revisar_archivos`); lo que no se reconoce se dice."""
    base = um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0)
    e = E(200.0, 20.0, 20.0, 100.0, 10.0, x_ef=12.0, y_ef=12.0, um_planeador=250.0)
    for equipo, energia in (("Clinac 600", "6X"), ("600C", "6MV"), ("Varian Clinac 600", "6 mv")):
        d = um_armar.datos_haz(archivos, equipo, energia, d0_dmax=1.0)
        assert (d.equipo, d.energia, d.sc) == ("Clinac 600", "6 MV", base.sc) and motor.calcular(d, e).um == motor.calcular(base, e).um
        assert um_armar.revisar_archivos(_pares(archivos), equipo, energia, d0_dmax=1.0).problemas == ()
        assert um_armar.sc_del_haz(base.of, 100.0, 5.0, energia) == um_armar.sc_del_haz(base.of, 100.0, 5.0, "6 MV")
    for equipo, energia, motivo in (("Clinac iX", "6 MV", "dicen máquina 600C, y se están cargando para Clinac iX"), ("Clinac 600", "18 MV", "dicen haz 6X, y se están cargando para 18 MV"),
                                    ("Halcyon", "6 MV", "El equipo «Halcyon» no se reconoce"), ("Clinac 600", "6 FFF", "La energía «6 FFF» no se reconoce")):
        with pytest.raises(ValueError, match=motivo):
            um_armar.datos_haz(archivos, equipo, energia, d0_dmax=1.0)
    r = um_armar.revisar_archivos(_pares(archivos), "Clinac iX", "6X", d0_dmax=1.0)
    assert len(r.problemas) == 12 and all(p.endswith("dice máquina 600C, y se está cargando para Clinac iX.") for p in r.problemas)
    assert um_armar.revisar_archivos(_pares(archivos), "Halcyon", "6 MV", d0_dmax=1.0).problemas == (
        "El equipo «Halcyon» no se reconoce: la calculadora conoce el Clinac 600 y el Clinac iX",)


def test_un_archivo_cortado_dice_cual_es_y_los_demas_siguen(archivos):
    """IF-2: el motivo nombra el archivo y ese archivo no queda entre los usados (antes: «anuncia 12 curvas y trae 8: parece cortado», sin nombre)."""
    pares = _pares(archivos)
    for nombre, hasta in ((OPD, 2 / 3), ("CLINAC 600C_Standard Wedge - 45_Measured Wedge Depth Doses.txt", 1 / 2)):
        t = dict(pares)[nombre]
        r = um_armar.revisar_archivos(_cambiado(pares, nombre, t[:int(len(t) * hasta)]), "Clinac 600", "6 MV", d0_dmax=1.0)
        assert len(r.problemas) == 1 and r.problemas[0].startswith(f"{nombre}: ") and "cortado" in r.problemas[0]
        assert nombre not in r.usados and len(r.usados) == 11


def test_un_error_inesperado_al_leer_se_dice_sin_esconderlo(archivos, monkeypatch):
    """L-UM2-4: lo que no es un `ArchivoNoReconocido` ni un `NoCalculable` se dice como error inesperado, con su tipo y el archivo; y el rango del factor de cuña
    es una constante con nombre (antes, cambiar la redacción de un motivo del motor bloqueaba toda carga con `KeyError`)."""
    monkeypatch.setitem(um_armar.LECTORES, "OPD", lambda texto: 1 / 0)
    r = um_armar.revisar_archivos(_pares(archivos), "Clinac 600", "6 MV", d0_dmax=1.0)
    assert r.problemas == (f"{OPD}: error inesperado al leerlo (ZeroDivisionError): avise al administrador",)
    monkeypatch.undo()
    monkeypatch.delitem(motor.RANGOS, "El factor de cuña")
    assert um_armar.revisar_archivos(_pares(archivos), "Clinac 600", "6 MV", d0_dmax=1.0).problemas == ()


@pytest.mark.parametrize("cual, valor, motivo", [("d0_dmax", "1.0", r"D'0 no es un valor posible \(de 0.5 a 1.5 \[cGy/UM\]\): 1.0"), ("d0_dmax", True, "D'0 no es un valor posible"),
                                                  ("d0_tabla", "0.86", "D'0 no es un valor posible")])
def test_d0_escrito_que_no_es_un_numero_se_rechaza_con_su_motivo(archivos, cual, valor, motivo):
    """IF-8, L-UM2-3: antes un texto daba `TypeError` y un booleano se aceptaba como 1.0 cGy/UM."""
    with pytest.raises(motor.FaltaDato, match=motivo):
        um_armar.datos_haz(archivos, "Clinac 600", "6 MV", **{cual: valor})
    assert re.search(motivo, um_armar.revisar_archivos(_pares(archivos), "Clinac 600", "6 MV", **{cual: valor}).problemas[0])


@pytest.mark.parametrize("escritos, motivo", [({15.0: 0.77}, "número entero de grados, y se recibió «15.0»"), ({"15.0": 0.77}, "se recibió «15.0»"), ({15.5: 0.77}, "«15.5»"),
                                              ({True: 0.77}, "«True»"), ({15: True}, "debe ser un número, y se recibió «True»"), ({"15": "0.77"}, "se recibió «0.77»"),
                                              ({15: 0.77, "15": 0.78}, "Hay dos factores escritos para la cuña de 15°")])
def test_los_factores_de_cuna_escritos_son_estrictos(archivos, escritos, motivo):
    """IF-5, L-UM2-3: un ángulo con decimales no se podía releer del JSON (int('15.0') falla) y 15.9 iba a la cuña de 15°; un WF en texto o booleano se aceptaba."""
    with pytest.raises(motor.FaltaDato, match=motivo):
        um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos=escritos)
    assert um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos=json.loads(json.dumps({15: 0.77}))).cunas[15].wf_ref == 0.77


def test_la_cuna_se_elige_por_un_entero_y_su_orientacion_solo_cuenta_con_cuna(datos):
    """IF-9: una cuña «15» en texto decía «No hay datos de la cuña de 15°»; sin cuña, una orientación vacía se rechazaba con un motivo de cuña."""
    with pytest.raises(motor.FaltaDato, match="La cuña se elige por su ángulo en grados, un número entero, y se recibió «15»"):
        motor.calcular(datos, E(200.0, 10.0, 10.0, 100.0, 10.0, cuna="15"))
    base = motor.calcular(datos, E(200.0, 10.0, 10.0, 100.0, 10.0)).um
    for orientacion in (None, "", "diagonal"):
        assert motor.calcular(datos, E(200.0, 10.0, 10.0, 100.0, 10.0, cuna_orientacion=orientacion)).um == base


@pytest.mark.parametrize("campo, motivo", [(dict(dosis=0), "La dosis no es un valor posible (mayor que 0 y hasta 5000 [cGy]): 0"),
                                           (dict(um_planeador=0), "Las UM de Eclipse no son un valor posible (mayor que 0 y hasta 20000 [UM]): 0"),
                                           (dict(tf=2.0), "El factor de bandeja no es un valor posible (de 0.5 a 1.05): 2.0"),
                                           (dict(prof=-1.0), "La profundidad no es un valor posible (mayor que 0 y hasta 100 [cm]): -1.0"),
                                           (dict(ssd=150.0), "La SSD no es un valor posible (de 60 a 140 [cm]): 150.0"),
                                           (dict(prof=100.5), "La profundidad no es un valor posible (mayor que 0 y hasta 100 [cm]): 100.5"),         # F1: el tope alto
                                           (dict(prof_ef=100.5), "La profundidad efectiva no es un valor posible (mayor que 0 y hasta 100 [cm]): 100.5")])
def test_los_motivos_de_lo_escrito_a_mano_se_leen_bien(datos, campo, motivo):
    """IF-7: sin notación científica («de 1e-06 a 5000»), con su unidad y con la concordancia («Las UM de Eclipse no es»)."""
    with pytest.raises(motor.FaltaDato) as fallo:
        motor.calcular(datos, E(**{**dict(dosis=200.0, x=10.0, y=10.0, ssd=100.0, prof=10.0), **campo}))
    assert str(fallo.value) == motivo


def test_una_curva_de_sc_con_texto_se_rechaza_sin_ingles(archivos):
    for curva in ([("4", "0.96"), (10.0, 1.0)], [(4.0, True), (10.0, 1.0)], [(4.0, "a"), (10.0, 1.0)], [("4", 0.96), (10.0, 1.0)], [(True, 0.96), (10.0, 1.0)]):
        with pytest.raises(motor.FaltaDato) as fallo:
            um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, sc=curva)
        assert str(fallo.value) == "La curva de Sc debe tener al menos dos puntos (lado [cm], Sc), con números, lados crecientes y valores de 0.5 a 1.5"


TEXTOS_DE_PRUEBA = [dict(x=45.0), dict(ssd=150.0), dict(prof=30.004), dict(x=40.000001), dict(x=3.0, y=3.0), dict(prof=1.0), dict(x=30.0, y=30.0, punto_x=12.0),
                    dict(ssd=125.0), dict(punto_x=3.1), dict(x=20.0, y=20.0, punto_x=8.0), dict(cuna=15, x_ef=2.6, y_ef=2.6), dict(cuna=15, x=40.0, y=20.0, x_ef=26.0, y_ef=26.0),
                    dict(cuna=15, x=3.5, y=3.5), dict(cuna=15, prof=25.0), dict(x=20.0, y=20.0, x_ef=10.0, y_ef=10.0, ssd=90.0), dict(prof=60.0), dict(prof=0.5, punto_x=1.0),
                    dict(x=38.0, y=38.0, ssd=105.0), dict(punto_x=12.0, x=40.0, y=40.0, prof=25.0), dict(dosis=0), dict(x=5.0, y=40.0), dict(cuna=15, x=12.0, y=15.0)]


def test_los_textos_que_ve_el_fisico_llevan_las_unidades_entre_corchetes(datos, archivos):
    """F-FIS-2, S-5, DR-5, IF-7, L-UM2-7, L-UM2-8: avisos, motivos y detalles con las unidades entre corchetes, punto decimal, sin notación científica, sin la
    contradicción del .2f («= 30.00 cm está fuera de la tabla (0 a 30 cm)» con 30.004) y diciendo de QUÉ tabla se habla."""
    textos = []
    for kw in TEXTOS_DE_PRUEBA:
        try:
            r = motor.calcular(datos, E(**{**dict(dosis=200.0, x=10.0, y=10.0, ssd=100.0, prof=10.0), **kw}))
            textos += list(r.avisos) + [f.detalle for f in r.factores]
        except motor.NoCalculable as fallo:
            textos.append(str(fallo))
    pares = _pares(archivos)
    for kw in (dict(d0_dmax=1.7), dict(d0_dmax=1.0, wf_escritos={20: 0.7}), dict(d0_dmax=1.0)):
        r = um_armar.revisar_archivos(pares, "Clinac 600", "6 MV", **kw)
        textos += list(r.problemas) + list(r.avisos)
    otra_ssd = [(n, t.replace("%SourcePhantomDistance 1000", "%SourcePhantomDistance 950")) for n, t in pares]
    textos += list(um_armar.revisar_archivos(otra_ssd, "Clinac 600", "6 MV", d0_dmax=1.0).problemas)
    unido = " | ".join(textos)
    assert len(textos) > 60
    for t in textos:
        assert not re.search(r"\d (cm|cGy|UM|%)\b|\d ?%|\(cm\)|\d,\d|e-0\d|e\+\d|[✓✔✗✘⚠]", t), t
    assert re.search(r"= 30\.004 \[cm\] está fuera de la tabla \(\S+ a 30 \[cm\]\)", unido) and "= 40.000001 [cm] está fuera de la tabla (2.5 a 40 [cm])" in unido
    assert "El lado Y que se lee en la tabla de la cuña de 15° = 26.00 [cm] está fuera de la tabla (2 a 20 [cm])" in unido
    assert "las tablas de cuña dicen 2 donde la abierta dice 2.5" in unido


def test_lo_que_el_barrido_del_motor_dejo_ver(datos):
    """El valor por debajo de la tabla con sus dos decimales; el lado del rectángulo efectivo que se sale de la tabla dice cuál; el alargamiento de un efectivo
    casi tan ancho como la mandíbula y el de un cuadrado que no llega a 4:1; la cuña booleana; los detalles sin láminas no hablan de láminas; y el máximo del PDD se
    toma en el 10 × 10 aunque haya lados medidos cerca."""
    textos = []
    for kw in (dict(x=2.0), dict(x_ef=2.0, y_ef=8.0), dict(x_ef=8.0, y_ef=2.0)):
        with pytest.raises(motor.FueraDeTabla) as fallo:
            motor.calcular(datos, E(200.0, **{**dict(x=10.0, y=10.0, ssd=100.0, prof=10.0), **kw}))
        textos.append(str(fallo.value))
    assert textos == ["El lado X de las mandíbulas = 2.00 [cm] está fuera de la tabla (2.5 a 40 [cm])"] + [      # UM.2 v2 (A2, F5): con láminas, el lado corto
                      "El campo efectivo tiene un lado de 2.00 [cm] en la tabla, más estrecho que el campo más pequeño medido (2.5 [cm]): no se calcula"] * 2
    assert "alargado" in avisos_de(datos, 200.0, 5.0, 40.0, 100.0, 10.0, x_ef=5.05, y_ef=30.0)      # 5.05 pasa del lado corto, 5, dentro del redondeo: es un rectángulo
    assert "alargado" not in avisos_de(datos, 200.0, 10.0, 40.0, 100.0, 10.0, x_ef=15.0, y_ef=15.0)  # 15/(2·10 − 15) = 3: menos de 4:1
    with pytest.raises(motor.FaltaDato, match="se recibió «True»"):
        motor.calcular(datos, E(200.0, 10.0, 10.0, 100.0, 10.0, cuna=True))
    for r in (motor.calcular(datos, E(200.0, 10.0, 20.0, 90.0, 10.0)), motor.calcular(datos, E(200.0, 10.0, 10.0, 100.0, 10.0, x_ef=10.0, y_ef=10.0))):
        assert "cuadrado equivalente" not in _origen(r, "OF")[1] and "intercambio" not in _origen(r, "Sc(rc)/Sc(lectura)")[1]
    lados = np.array([8.5, 9.85, 10.0, 10.15, 12.0])
    m = np.array([[99.0, 99.0, 99.0]] * 2 + [[100.0, 90.0, 80.0]] + [[99.0, 99.0, 99.0]] * 2)
    familia = motor.FamiliaPDD(lados, np.array([1.0, 5.0, 10.0]), m)
    assert motor.d0_en_normalizacion(familia, 1.0, 5.0) == pytest.approx(0.9, rel=1e-12)      # 90/100, el 10 × 10 y no un vecino


def test_los_haces_se_comparan_sin_reventar(archivos):
    """IF-10: los datos del haz guardan arreglos de numpy; un `==` campo a campo lanzaba ValueError (y un `except ValueError` lo habría tomado por un caso no
    calculable). Se comparan por identidad y tienen hash; para saber si dos haces dan lo mismo se comparan sus UM."""
    d, d2 = (um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0) for _ in range(2))
    assert d == d and not d == d2 and d.of != d2.of and d.pdd != d2.pdd and len({d, d2, d.of, d.pdd, d.perfiles, d.cunas[15]}) == 6
    assert motor.calcular(d, E(200.0, 10.0, 10.0, 100.0, 10.0)).um == motor.calcular(d2, E(200.0, 10.0, 10.0, 100.0, 10.0)).um


def test_el_cuadrado_medido_mas_parecido_se_busca_en_logaritmo(datos):
    """F2 (de `FUERA` de la referencia, que se daba por equivalente): 7.9 está más cerca de 10 que de 6 en logaritmo (el punto medio es √60 = 7.75) y más cerca de 6
    en lineal (8): la pérdida junto al borde de un campo de 7.9 se estima con el perfil del 10 × 10."""
    p = datos.perfiles
    assert p.perdida_junto_al_borde((7.9, 7.9), (2.95, 0.0), 10.0) == pytest.approx(p.perdida_junto_al_borde((10.0, 10.0), (2.95, 0.0), 10.0), rel=1e-12)
    assert p.perdida_junto_al_borde((7.9, 7.9), (2.95, 0.0), 10.0) != pytest.approx(p.perdida_junto_al_borde((6.0, 6.0), (2.95, 0.0), 10.0), rel=1e-6)


def test_la_formula_y_sus_partes_tienen_nombre(datos, monkeypatch):
    """L-UM2-5, L-UM2-9: la fórmula del módulo trae la corrección por profundidad efectiva, que es una función con nombre; y `sc_del_haz` toma los dos límites del
    Sp de la TG-71 (antes el inferior salía de la tabla IV: un punto de 3 cm en ella metía un lado cuyo Sp se recortaba en silencio)."""
    assert "((SSD + d)/(SSD + prof))²" in motor.__doc__
    assert motor.correccion_por_profundidad_efectiva(110.0, 6.0, 7.5) == pytest.approx((117.5 / 116.0) ** 2, rel=1e-15)
    lados = [j for j, _ in um_armar.sc_del_haz(datos.of, 100.0, 5.0, "6 MV")[0]]
    monkeypatch.setattr(motor, "SC_MUESTRA_TG71", ((3.0, 0.94),) + motor.SC_MUESTRA_TG71)
    assert [j for j, _ in um_armar.sc_del_haz(datos.of, 100.0, 5.0, "6 MV")[0]] == lados


def test_los_huecos_de_la_prueba_v1_pr1_a_pr9(archivos, datos):
    """PR-1 a PR-9: conductas que ninguna prueba fijaba por su razón."""
    # PR-1: la barrera de 3 cm de la cuña mira el campo EFECTIVO, con el que se lee su tabla
    for x_ef, y_ef in ((2.8, 8.0), (2.6, 2.6)):
        with pytest.raises(motor.FueraDeTabla, match=r"por debajo de 3 \[cm\]"):
            motor.calcular(datos, E(200.0, 10.0, 10.0, 100.0, 10.0, x_ef=x_ef, y_ef=y_ef, cuna=15))
    # PR-2: D'0 en dmax se lleva a la profundidad REAL de la tabla de factores (aquí, 10 cm)
    a_10 = um_armar.datos_haz([a.replace("%DetectorDepth 50", "%DetectorDepth 100") for a in archivos], "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={30: 0.6})
    assert a_10.d0_cm == 10.0 and a_10.d0_norm == pytest.approx(pdd_a_mano(10.0, 10.0) / 100.0, rel=1e-12)
    # PR-4: el OAR se mide desde el EJE, no desde el centro de un campo asimétrico
    assert factor(motor.calcular(datos, E(200.0, 20.0, 20.0, 100.0, 10.0, centro_x=5.0, punto_x=8.0)), "OAR") == pytest.approx(oar_a_mano(40.0, 10.0, 8.0), rel=1e-12)
    assert factor(motor.calcular(datos, E(200.0, 20.0, 20.0, 100.0, 10.0, centro_x=4.0)), "OAR") == 1.0
    # PR-5: los avisos en el lado NEGATIVO de X
    assert "El eje queda en el borde" in avisos_de(datos, 200.0, 10.0, 10.0, 100.0, 10.0, centro_x=-5.0, punto_x=-5.0)
    assert "la dosis cambiaría" in avisos_de(datos, 200.0, 20.0, 20.0, 100.0, 10.0, punto_x=-7.0)
    # PR-6: los avisos de Sc con la lectura MAYOR que las mandíbulas (SSD por encima de 100)
    sin_sc = um_armar.datos_haz(archivos, "Clinac 600", "6 MV", d0_dmax=1.0, sc=())
    assert "no hay curva de Sc" in avisos_de(sin_sc, 200.0, 20.0, 20.0, 110.0, 10.0)
    assert "La curva de Sc va de 4 a 38.0952 [cm] y aquí hizo falta 38.0 a 39.7 [cm]" in avisos_de(datos, 200.0, 38.0, 38.0, 105.0, 10.0)
    # PR-7: con láminas, el aviso de la TG-114 sigue mirando el borde de las mandíbulas
    assert "El punto queda a 1.0 [cm] del borde de las mandíbulas" in avisos_de(datos, 200.0, 10.0, 10.0, 100.0, 10.0, x_ef=8.0, y_ef=8.0, punto_x=4.0)
    # PR-8: rd0 con láminas es el del efectivo; la lectura alterna es la celda de las mandíbulas
    assert motor.calcular(datos, E(200.0, 20.0, 20.0, 100.0, 10.0, x_ef=10.0, y_ef=10.0)).campos["rd0"] == pytest.approx(10.5, rel=1e-12)
    assert motor.calcular(datos, E(200.0, 5.0, 20.0, 100.0, 10.0)).lectura_alterna_of == celda(tabla_real(), 20.0, 5.0) == 0.981
    # PR-9: la curva de Sc por omisión se proyecta con la SSD de la TABLA, también al armar
    a_95 = um_armar.datos_haz([a.replace("%SourcePhantomDistance 1000", "%SourcePhantomDistance 950") for a in archivos], "Clinac 600", "6 MV", d0_tabla=0.945)
    assert a_95.sc[-1][0] == pytest.approx(40.0, rel=1e-12)


# --- UM.2 v2, segunda vuelta (borradores/UM2/v2/hallazgos_segunda_vuelta.md del plan): cada prueba cae contra la v2 de la primera vuelta o contra su mutación ---

def test_toda_lectura_de_la_tabla_abierta_entra_en_el_aviso_de_celdas(datos):
    """A1 y F2: la lectura de la tabla abierta que divide a la de la cuña (con láminas, y sin láminas con la cuña girada, donde se leen las mandíbulas
    traspuestas) y las dos del intercambio E de las mandíbulas con láminas entran en el aviso de las celdas fuera de tendencia."""
    marcada = dataclasses.replace(datos, celdas_a_revisar=frozenset({(15.0, 6.0)}))
    for kw in (dict(x=20.0, y=20.0, x_ef=6.0, y_ef=15.0, cuna=15, cuna_orientacion="IN"), dict(x=20.0, y=20.0, x_ef=15.0, y_ef=6.0, cuna=15, cuna_orientacion="LEFT"),
               dict(x=15.0, y=6.0, cuna=15, cuna_orientacion="LEFT")):
        assert "fuera de tendencia" in avisos_de(marcada, 200.0, ssd=100.0, prof=10.0, **kw), kw
    assert "fuera de tendencia" not in avisos_de(marcada, 200.0, 20.0, 20.0, 100.0, 10.0, x_ef=6.0, y_ef=15.0)      # sin cuña esa celda no se lee
    for x_ef, y_ef in ((15.0, 15.0), (20.0, 12.0)):      # la celda marcada del 600C (Y = 30, X = 25) solo la lee E = OF(25, 30)/OF(rc, rc)
        assert "fuera de tendencia" in avisos_de(datos, 200.0, 25.0, 30.0, 100.0, 10.0, x_ef=x_ef, y_ef=y_ef)


def test_con_laminas_solo_se_comprueba_lo_que_se_lee(datos):
    """A2 y F5: mandíbulas 40 × 40 con láminas 36 × 10 a SSD 115 y 120 (una craneoespinal) dan número, y el mismo que escrito como su cuadrado equivalente (antes
    el rectángulo escalado «no cabía en la tabla», aunque no se lee); un lado corto más estrecho que lo medido sigue sin calcularse, con su motivo (UM2-D19)."""
    q = motor.equivalente(36.0, 10.0)
    for ssd in (115.0, 120.0):
        rectangulo = motor.calcular(datos, E(200.0, 40.0, 40.0, ssd, 10.0, x_ef=36.0, y_ef=10.0)).um
        assert rectangulo == pytest.approx(motor.calcular(datos, E(200.0, 40.0, 40.0, ssd, 10.0, x_ef=q, y_ef=q)).um, rel=1e-12)
    with pytest.raises(motor.FueraDeTabla, match=r"^El campo efectivo tiene un lado de 2.00 \[cm\] en la tabla, más estrecho que el campo más pequeño medido \(2.5 \[cm\]\)"):
        motor.calcular(datos, E(200.0, 10.0, 10.0, 100.0, 10.0, x_ef=2.0, y_ef=8.0))


def test_la_orientacion_de_la_cuna_no_se_supone_en_silencio(datos):
    """A3 (UM2-D18): sin orientación, una cuña de tabla se calcula con el gradiente a lo largo de Y y lo dice; con la orientación o con el factor escrito, no."""
    sin = motor.calcular(datos, E(200.0, 10.0, 15.0, 100.0, 10.0, cuna=15))
    assert sin.um == motor.calcular(datos, E(200.0, 10.0, 15.0, 100.0, 10.0, cuna=15, cuna_orientacion="IN")).um
    assert "No se dio la orientación de la cuña de 15°: se calculó como IN u OUT (gradiente a lo largo de Y); compruébela en el plan." in sin.avisos
    for kw in (dict(cuna_orientacion="IN"), dict(cuna_orientacion="LEFT"), dict(wf_manual=0.77)):
        assert not any("orientación" in a for a in motor.calcular(datos, E(200.0, 10.0, 15.0, 100.0, 10.0, cuna=15, **kw)).avisos), kw


@pytest.mark.parametrize("dentro, fuera", [(float("inf"), float("inf")), (3.0, 2.0), (True, 3.0), (2.0, False), (float("nan"), 3.0), ("2", 3.0), (0.0, 3.0),
                                           (-1.0, 3.0), (2.0, None)])
def test_las_tolerancias_de_la_sesion_se_validan(datos, dentro, fuera):
    """A4: las tolerancias que el físico cambia en la sesión (DC11) son números, mayores que 0, y la de dentro no mayor que la de fuera; en `calcular` y en
    `estado_de`, con la misma validación."""
    with pytest.raises(motor.FaltaDato, match=r"^Las tolerancias deben ser números mayores que 0, la de dentro no mayor que la de fuera \[%\]"):
        motor.calcular(datos, E(200.0, 10.0, 10.0, 100.0, 10.0), dentro, fuera)
    with pytest.raises(motor.FaltaDato, match=r"^Las tolerancias deben ser"):
        motor.estado_de(1.0, dentro, fuera)


def test_las_tolerancias_iguales_se_admiten():
    assert (motor.estado_de(2.0, 2.0, 2.0), motor.estado_de(2.01, 2.0, 2.0), motor.estado_de(0.5, 0.5, 3.0)) == ("Dentro", "Fuera", "Dentro")


def test_el_ultimo_tramo_medido_del_pdd_se_avisa(datos):
    """A5 (UM2-D20): en el último tramo del PDD la revisión de los archivos deja pasar una cifra dañada del último punto (hasta 6.3 % de UM en d = 30, medido por
    la segunda auditoría): el cálculo lo dice, con la profundidad en las cifras que la distinguen del límite."""
    z = datos.pdd.z_cm
    assert "cae en el último tramo medido del PDD (29.9 a 30 [cm])" in avisos_de(datos, 200.0, 10.0, 10.0, 100.0, float(z[-1]))
    assert "La profundidad (29.901 [cm]) cae en el último tramo" in avisos_de(datos, 200.0, 10.0, 10.0, 100.0, float(z[-2]) + 0.001)
    assert "último tramo" not in avisos_de(datos, 200.0, 10.0, 10.0, 100.0, float(z[-2]))
    assert "último tramo" in avisos_de(datos, 200.0, 10.0, 10.0, 100.0, 29.0, prof_ef=29.95)      # se mira la profundidad con que se lee el PDD


def test_la_revision_dice_el_d0_y_el_maximo_del_10x10_que_se_usaron(archivos, datos):
    """A6: D'0 depende del máximo medido del PDD de 10 × 10 (UM2-D11); la revisión lo dice al cargar, con el D'0 en las condiciones de la tabla."""
    r = um_armar.revisar_archivos(_pares(archivos), "Clinac 600", "6 MV", d0_dmax=1.0)
    assert (f"D'0 = {datos.d0_norm:.4f} [cGy/UM] a 5 [cm] de profundidad, SSD 100 [cm], 10 × 10: sale de 1 [cGy/UM] en dmax con el máximo medido del PDD de "
            f"10 × 10, {datos.pdd.maximo(10.0):.2f} [%].") in r.avisos and datos.d0_norm == pytest.approx(0.86, abs=0.002)
    r = um_armar.revisar_archivos(_pares(archivos), "Clinac 600", "6 MV", d0_tabla=0.86)
    assert "D'0 = 0.8600 [cGy/UM] a 5 [cm] de profundidad, SSD 100 [cm], 10 × 10, escrito en las condiciones de la tabla." in r.avisos


def test_un_factor_escrito_para_una_cuna_incompleta_dice_que_hacer(archivos):
    """B4: a la cuña de 45° le falta su PDD con cuña y el físico escribió su factor: el motivo dice eso (sus archivos SÍ estaban entre los elegidos) y qué hacer."""
    sin = [(n, t) for n, t in _pares(archivos) if n != "CLINAC 600C_Standard Wedge - 45_Measured Wedge Depth Doses.txt"]
    assert len(sin) == len(archivos) - 1
    r = um_armar.revisar_archivos(sin, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={45: 0.5})
    assert r.problemas == ("Cuña de 45°: hay un factor escrito, pero le falta su PDD medido con cuña y sus archivos no se usan: quite el factor escrito o agregue "
                           "su PDD medido con cuña.",)
    assert not um_armar.revisar_archivos(sin, "Clinac 600", "6 MV", d0_dmax=1.0).problemas
    sin_cuna = [(n, t) for n, t in _pares(archivos) if "Wedge - 45" not in n]
    assert um_armar.revisar_archivos(sin_cuna, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={45: 0.5}).problemas == (
        "Hay un factor escrito para una cuña que no está entre los archivos: 45°; quite el factor escrito o agregue sus archivos",)


def test_los_motivos_no_muestran_la_representacion_de_python(archivos):
    """C3: las SSD con sus unidades y las máquinas con su nombre, también por el camino de UM.3 (`datos_haz` sin la revisión)."""
    otra = [a.replace("600C, 6X", "600C, 18X") if i == 0 else a for i, a in enumerate(archivos)]
    with pytest.raises(lector.ArchivoNoReconocido, match=r"^los archivos son de máquinas o energías distintas: máquina 600C con haz 18X y máquina 600C con haz 6X$"):
        um_armar.datos_haz(otra, "Clinac 600", "6 MV", d0_dmax=1.0)
    pares = _pares(archivos)
    for viejo, nuevo, dicen in (("%SSD 1000", "%SSD 950", "95 [cm], 100 [cm]"),      # en orden: un conjunto de 100 y 95 los da al revés
                                ("%SSD 1000\n", "", "100 [cm], una curva sin SSD")):
        r = um_armar.revisar_archivos(_cambiado(pares, OPD, _una_vez(dict(pares)[OPD], viejo, nuevo)), "Clinac 600", "6 MV", d0_dmax=1.0)
        assert len(r.problemas) == 1 and r.problemas[0].endswith(f"los PDD abiertos deben decir una sola SSD y dicen {dicen}"), r.problemas


def test_los_comentarios_no_citan_guiones_que_el_repositorio_no_tiene():
    """C4: los comentarios dicen de dónde sale un número sin citar un guion del anexo del plan, que quien lea el repositorio no tiene."""
    import services.um_plausibilidad as plausibilidad
    for modulo in (motor, um_armar, plausibilidad):
        with open(modulo.__file__, encoding="utf-8") as f:
            assert not re.search(r"scripts/\w+\.py", f.read()), modulo.__name__


def test_el_aviso_de_los_10_cm_mira_la_distancia_al_eje(datos):
    """F3: el aviso de la TG-71 fuera de 10 [cm] del eje mira la distancia, no solo X: un punto a 12 [cm] sobre Y y uno a 11.3 [cm] en diagonal."""
    for px, py in ((0.0, 12.0), (8.0, 8.0)):
        assert "del eje: la TG-71 advierte" in avisos_de(datos, 200.0, 30.0, 30.0, 100.0, 10.0, punto_x=px, punto_y=py), (px, py)
    assert "del eje: la TG-71 advierte" not in avisos_de(datos, 200.0, 30.0, 30.0, 100.0, 10.0, punto_x=7.0, punto_y=7.0)


@pytest.mark.parametrize("archivo, viejo, nuevo, motivo", [
    # F1: la última columna de una fila interior solo la ve la pasada por COLUMNAS (la fila usa ahí el umbral del borde)
    (OF_ABIERTA, "1.054, 1.055, 1.056\n", "1.054, 1.055, 1.096\n", r"^la tabla abierta: el valor en Y = 15 \[cm\], X = 40 \[cm\] se aparta"),
    # F4: el PRIMER perfil del archivo también se mira (un punto decimal perdido en el 2.5 × 2.5 a 1.35 cm)
    (OPP, "<+010.0 +000.0 +013.5 +073.933>", "<+010.0 +000.0 +013.5 +073933>", r"^el perfil abierto de 2.5 × 2.5 \[cm\] a 1.35 \[cm\] de profundidad tiene un OAR"),
    # B2: una cifra perdida pasado el máximo: el motivo nombra los dos puntos del salto (antes, solo el de 15.1, el sano)
    (OPD, "+150.0 +052.800>", "+150.0 +02.800>", r" sube 49.7 \[%\] entre z = 15 \[cm\] y z = 15.1 \[cm\], pasado su máximo"),     # el dañado es el de 15
    # B3: un salto entre dos celdas nombra las dos
    (OF_ABIERTA, "0.951, 0.950, 0.950\n", "0.951, 0.950, 1.950\n", r"^la tabla abierta salta entre la celda Y = 4 \[cm\], X = 35 \[cm\] \(valor 0.95\) y la Y = 4 \[cm\], X = 40 \[cm\] \(valor 1.95\)"),
])
def test_la_segunda_vuelta_de_los_valores_imposibles(archivos, archivo, viejo, nuevo, motivo):
    pares = _pares(archivos)
    r = um_armar.revisar_archivos(_cambiado(pares, archivo, _una_vez(dict(pares)[archivo], viejo, nuevo)), "Clinac 600", "6 MV", d0_dmax=1.0,
                                  wf_escritos={15: 0.77, 30: 0.6, 45: 0.5, 60: 0.4})
    assert len(r.problemas) == 1 and re.search(motivo, r.problemas[0]), r.problemas


def test_con_cuna_y_laminas_el_aviso_dice_que_la_forma_escrita_pesa(datos):
    """D1 (UM2-D9 v): con cuña y láminas, el factor de la cuña se lee con el rectángulo efectivo tal como se escribió, y el aviso de las láminas lo dice;
    sin cuña o con el factor escrito a mano, no."""
    frase = "Con cuña, su factor se lee con el rectángulo efectivo tal como se escribió"
    assert frase in avisos_de(datos, 200.0, 20.0, 20.0, 100.0, 10.0, x_ef=8.0, y_ef=15.0, cuna=15, cuna_orientacion="IN")
    for kw in (dict(), dict(cuna=15, cuna_orientacion="IN", wf_manual=0.77)):
        assert frase not in avisos_de(datos, 200.0, 20.0, 20.0, 100.0, 10.0, x_ef=8.0, y_ef=15.0, **kw), kw


def test_la_guarda_del_lado_corto_en_su_limite(datos):
    """El barrido de la segunda vuelta (12 sobrevivientes en la guarda de UM2-D19): el lado corto justo en el campo más pequeño medido se calcula; la tolerancia de
    redondeo es de 1e-9 [cm] (a SSD 100 no se escala); y el límite es el menor de los dos ejes de la tabla, sea X o Y (tablas sin su primera columna o fila)."""
    def da_numero(d, x_ef):
        try:
            motor.calcular(d, E(200.0, 10.0, 10.0, 100.0, 10.0, x_ef=x_ef, y_ef=8.0))
            return True
        except motor.FueraDeTabla:
            return False
    assert (da_numero(datos, 2.5), da_numero(datos, 2.5 - 0.995e-9), da_numero(datos, 2.5 - 1e-9), da_numero(datos, 2.5 - 1.005e-9)) == (True, True, True, False)
    of = datos.of
    sin_columna = dataclasses.replace(datos, of=motor.TablaFactores(of.x[1:], of.y, of.m[:, 1:]))
    sin_fila = dataclasses.replace(datos, of=motor.TablaFactores(of.x, of.y[1:], of.m[1:, :]))
    assert (of.x[0], of.x[1], of.y[0], of.y[1]) == (2.5, 3.0, 2.5, 3.0)
    assert (da_numero(sin_columna, 2.7), da_numero(sin_fila, 2.7), da_numero(sin_columna, 2.4), da_numero(sin_fila, 2.4)) == (True, True, False, False)


# ---------- UM.2, ronda 1 de los revisores (09-11-2026): una prueba por hallazgo reproducido; cada una cae contra la producción de antes o contra su mutación ----------
# F1 a F4 son defectos de producción (el rojo fue contra el árbol sin corregir: 11 casos caían por la razón de su nombre); PRU-1 a PRU-3 son mutaciones plausibles que ninguna prueba
# con nombre propio atrapaba (la primera sobrevivía a los 740 casos; las otras dos solo caían por una aserción incidental). Las mutaciones X01 a X20 están en `um2_mutaciones.py`.
@pytest.mark.parametrize("viejo, nuevo, dosis_gy, mu", [
    (None, None, 0.6623, 100.0),                              # el name.data del 600C
    ("[MU]:100.000000", "[MU]:160.000000", 0.6623, 160.0),    # unas MU de referencia dañadas
    ("[Gy]:0.662300", "[Gy]:0.62300", 0.623, 100.0),          # una cifra borrada de la dosis de referencia
])
def test_la_revision_y_el_calculo_muestran_el_factor_de_cuna_deducido(archivos, viejo, nuevo, dosis_gy, mu):
    """F1 (ronda 1 de los revisores): un valor dañado del name.data cambia el factor de la cuña deducido (MU de 100 a 160: el WF baja de 0.7701 a 0.4813 y la UM de la cuña sube
    60 %; una cifra borrada de la dosis, 6.3 %) y la revisión lo aceptaba sin decir cuánto valía: solo «falta confirmarlo». Nada en los archivos permite comprobarlo (la
    transmisión de la cuña es otra magnitud), así que DC13 (2) pide que el resumen muestre «el WF deducido»: su valor y los dos datos de que sale, para compararlo con Eclipse.
    El mismo texto sale en cada resultado con esa cuña. El valor esperado sale de una cuenta a mano, no del armado."""
    nd = es_de(archivos, "data: WedgeParameters")
    cambiados = archivos if viejo is None else cambiar(archivos, nd, _una_vez(nd, viejo, nuevo))
    dosis_por_um = 100.0 * dosis_gy / mu      # Gy a cGy, por UM
    wf = dosis_por_um / 0.860                 # entre D'0 a 5 cm
    r = um_armar.revisar_archivos(_pares(cambiados), "Clinac 600", "6 MV", d0_dmax=1.0)
    assert not r.problemas
    deducido = [a for a in r.avisos if "falta confirmarlo" in a]
    assert len(deducido) == 1
    assert f"{wf:.4f}" in deducido[0] and f"{dosis_por_um:.4f} [cGy/UM]" in deducido[0] and "0.8600 [cGy/UM]" in deducido[0] and "5 [cm]" in deducido[0]
    d = um_armar.datos_haz(cambiados, "Clinac 600", "6 MV", d0_dmax=1.0)
    assert d.cunas[15].wf_ref == pytest.approx(wf, rel=1e-12)      # lo que dice el aviso es lo que usa el cálculo
    assert deducido[0] in motor.calcular(d, E(100.0, 10.0, 10.0, 100.0, 10.0, cuna=15, cuna_orientacion="IN")).avisos


def test_sin_curva_de_sc_el_factor_de_sc_vale_1_tambien_con_laminas(datos):
    """F2 (ronda 1 de los revisores; DC3: «sin curva, vale 1 y lo dice»): con la corrección de Sc apagada y láminas, el factor Sc(rc)/Sc(lectura) llevaba el intercambio X/Y de
    las mandíbulas (hasta −2.15 % en el 600C: 40 × 3 con un efectivo de 20 × 3) mientras un aviso decía «no se corrigió». Sin curva el factor vale 1 exacto: la UM es la del
    cuadrado equivalente del efectivo, sea cual sea la mandíbula que lo contiene, y los textos dicen que el Sc no se lleva al de las mandíbulas."""
    sin_sc = dataclasses.replace(datos, sc=(), sc_origen="")
    lado = motor.equivalente(4.0, 20.0)
    de_referencia = motor.calcular(sin_sc, E(100.0, lado, lado, 100.0, 10.0))      # sin láminas: unas mandíbulas cuadradas del lado equivalente del efectivo
    for mandibulas, efectivo in (((5.0, 30.0), (4.0, 20.0)), ((30.0, 5.0), (20.0, 4.0)), ((20.0, 20.0), (4.0, 20.0)), ((40.0, 40.0), (20.0, 4.0))):
        r = motor.calcular(sin_sc, E(100.0, *mandibulas, 100.0, 10.0, x_ef=efectivo[0], y_ef=efectivo[1]))
        assert factor(r, "Sc(rc)/Sc(lectura)") == 1.0 and r.um == pytest.approx(de_referencia.um, rel=1e-12), (mandibulas, efectivo)
        assert "intercambio" not in _origen(r, "Sc(rc)/Sc(lectura)")[1] and not any("intercambio" in a for a in r.avisos), (mandibulas, efectivo)
    con_curva = motor.calcular(datos, E(100.0, 5.0, 30.0, 100.0, 10.0, x_ef=4.0, y_ef=20.0))      # la premisa: con la curva de Sc el factor sí corrige, con el intercambio
    assert factor(con_curva, "Sc(rc)/Sc(lectura)") != 1.0 and "intercambio X/Y" in _origen(con_curva, "Sc(rc)/Sc(lectura)")[1]
    r = motor.calcular(sin_sc, E(100.0, 5.0, 30.0, 100.0, 10.0, x_ef=4.0, y_ef=20.0))
    assert _origen(r, "Sc(rc)/Sc(lectura)")[1] == "rc = 8.57 [cm]; lectura = 6.67 [cm]; corrección de Sc apagada"
    assert "El campo que se lee en la tabla no es el de las mandíbulas y no hay curva de Sc: no se corrigió." in r.avisos
    assert any("y el Sc no se lleva al de las mandíbulas (corrección de Sc apagada). La calculadora no conoce las láminas" in a for a in r.avisos)
    # las dos lecturas que solo servían al intercambio no pesan en el número: no entran en el aviso de las celdas fuera de tendencia (con la curva, la celda Y = 30, X = 25 sí)
    assert "fuera de tendencia" not in avisos_de(sin_sc, 200.0, 25.0, 30.0, 100.0, 10.0, x_ef=15.0, y_ef=15.0)
    assert "fuera de tendencia" in avisos_de(datos, 200.0, 25.0, 30.0, 100.0, 10.0, x_ef=15.0, y_ef=15.0)


@pytest.mark.parametrize("angulo, campo_del_pdd, ultimo_lado", [(15, "40 × 20", 15), (30, "40 × 20", 15), (45, "40 × 20", 15), (60, "40 × 15", 10)])
def test_el_motivo_de_una_tabla_de_cuna_cortada_no_culpa_solo_al_pdd(archivos, angulo, campo_del_pdd, ultimo_lado):
    """F3 (ronda 1 de los revisores): la tabla cortada al final de su última fila de cada cuña del 600C sí impide guardar (su PDD del campo entero deja de ser el de la tabla),
    pero el motivo decía solo que ese PDD «no es el campo entero de su tabla», como si el dañado fuera el PDD, que está entero. Ahora manda revisar los dos."""
    tabla = es_de(archivos, f"Standard Wedge - {angulo}", "data: OutputFactorTable")
    cortada = "\n".join(tabla.rstrip("\n").split("\n")[:-1]) + "\n"
    assert lector.leer_tabla_of(cortada).y[-1] == ultimo_lado
    motivo = (f"hay un PDD con cuña de {campo_del_pdd} [cm], que no es un cuadrado ni el campo entero de su tabla (40 × {ultimo_lado} [cm]): revise ese PDD y la tabla de factores "
              "de la cuña, que puede estar cortada al final de una fila")
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(motivo) + "$"):
        um_armar.datos_haz(cambiar(archivos, tabla, cortada), "Clinac 600", "6 MV", d0_dmax=1.0)
    assert um_armar.revisar_archivos(_pares(cambiar(archivos, tabla, cortada)), "Clinac 600", "6 MV", d0_dmax=1.0).problemas == (motivo,)


def test_la_revision_dice_hasta_donde_llega_la_tabla_de_cada_cuna(archivos):
    """F3 (ronda 1 de los revisores): si el PDD con cuña no trae su curva del campo entero, nada en los archivos delata una tabla de cuña cortada al final de una fila: se lee
    como una tabla más pequeña y el rango de la cuña baja en silencio (de 20 a 15 [cm] en Y: un 20 × 18 deja de calcularse). La revisión dice hasta dónde llega la tabla de cada
    cuña, para que el físico lo vea al cargar."""
    r = um_armar.revisar_archivos(_pares(archivos), "Clinac 600", "6 MV", d0_dmax=1.0)
    assert [a for a in r.avisos if "su tabla de factores va de" in a] == [
        f"Cuña de {angulo}°: su tabla de factores va de 2 a 40 [cm] en X y de 2 a {y} [cm] en Y." for angulo, y in ((15, 20), (30, 20), (45, 20), (60, 15))]
    tabla, wdd = es_de(archivos, "Standard Wedge - 15", "data: OutputFactorTable"), es_de(archivos, "Standard Wedge - 15", "data: WDD\n")
    cortada = "\n".join(tabla.rstrip("\n").split("\n")[:-1]) + "\n"
    pares = _cambiado(_cambiado(_pares(archivos), "CLINAC 600C_Standard Wedge - 15_Output Factors.txt", cortada), WDD15, _sin_el_campo_entero(wdd))
    r = um_armar.revisar_archivos(pares, "Clinac 600", "6 MV", d0_dmax=1.0)
    assert r.problemas == () and "Cuña de 15°: su tabla de factores va de 2 a 40 [cm] en X y de 2 a 15 [cm] en Y." in r.avisos
    d = um_armar.datos_haz([t for _, t in pares], "Clinac 600", "6 MV", d0_dmax=1.0)
    with pytest.raises(motor.FueraDeTabla, match=r"\(2 a 15 \[cm\]\)"):
        motor.calcular(d, E(200.0, 20.0, 18.0, 100.0, 10.0, cuna=15, cuna_orientacion="IN"))


def test_los_factores_escritos_se_entienden_igual_con_la_clave_entera_o_en_texto(archivos):
    """F4 (ronda 1 de los revisores): las claves de un JSON vuelven de la base como texto (DC12), «30» y 30 son la misma cuña. La revisión comparaba el ángulo sin normalizar la
    clave: con «30» y una cuña sin su PDD con cuña daba dos cosas contradictorias a la vez (un aviso que dice que sus campos se escriben a mano y un problema que dice que la cuña
    no está entre los archivos, cuando sí está). `datos_haz` ya la normalizaba; ahora la revisión usa la misma definición."""
    sin = [(n, t) for n, t in _pares(archivos) if n != "CLINAC 600C_Standard Wedge - 30_Measured Wedge Depth Doses.txt"]
    por_entero = um_armar.revisar_archivos(sin, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={30: 0.6})
    assert por_entero.problemas == ("Cuña de 30°: hay un factor escrito, pero le falta su PDD medido con cuña y sus archivos no se usan: quite el factor escrito o agregue su "
                                    "PDD medido con cuña.",)
    assert not any("Cuña de 30°: falta su PDD" in a for a in por_entero.avisos)
    for clave in ("30", "030"):
        assert um_armar.revisar_archivos(sin, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={clave: 0.6}) == por_entero, clave
    sin_cuna = [(n, t) for n, t in _pares(archivos) if "Wedge - 30" not in n]      # sin los archivos de esa cuña, el motivo es otro, el mismo para las dos claves
    for clave in (30, "30"):
        assert um_armar.revisar_archivos(sin_cuna, "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={clave: 0.6}).problemas == (
            "Hay un factor escrito para una cuña que no está entre los archivos: 30°; quite el factor escrito o agregue sus archivos",)
    r = um_armar.revisar_archivos(_pares(archivos), "Clinac 600", "6 MV", d0_dmax=1.0, wf_escritos={"quince": 0.7})      # una clave que no es un ángulo la dice `datos_haz`
    assert r.problemas == ("El ángulo de un factor de cuña escrito debe ser un número entero de grados, y se recibió «quince»",)


def test_cada_lado_de_las_mandibulas_se_comprueba_contra_el_rango_de_su_propio_eje(datos):
    """PRU-1 (ronda 1 de los revisores): la tabla abierta que arma `datos_haz` es cuadrada (UM2-D5), pero `calcular` recibe cualquier `DatosHaz` y las tablas de otros equipos
    llegarán por UM.3 y UM.5: con una tabla que llega más lejos en un eje que en el otro, X se compara con el rango de X y Y con el de Y. Comprobar el lado Y contra el rango de
    X rechazaba con FueraDeTabla un campo que sí se calcula (10 × 38 con X hasta 35 e Y hasta 40), y la mutación sobrevivía a las 740 pruebas porque todas las tablas eran cuadradas."""
    of = datos.of
    assert (of.x[-1], of.y[-1]) == (40.0, 40.0)
    x_hasta_35 = dataclasses.replace(datos, of=motor.TablaFactores(of.x[:-1], of.y, of.m[:, :-1]))
    y_hasta_35 = dataclasses.replace(datos, of=motor.TablaFactores(of.x, of.y[:-1], of.m[:-1, :]))
    for ssd in (100.0, 90.0):      # el lado que cabe en su eje, aunque pase del otro, se calcula, con las mismas celdas que la tabla entera
        assert motor.calcular(x_hasta_35, E(200.0, 10.0, 38.0, ssd, 10.0)).um == pytest.approx(motor.calcular(datos, E(200.0, 10.0, 38.0, ssd, 10.0)).um, rel=1e-12)
        assert motor.calcular(y_hasta_35, E(200.0, 38.0, 10.0, ssd, 10.0)).um == pytest.approx(motor.calcular(datos, E(200.0, 38.0, 10.0, ssd, 10.0)).um, rel=1e-12)
    with pytest.raises(motor.FueraDeTabla, match=r"^El lado X de las mandíbulas = 37.00 \[cm\] está fuera de la tabla \(2.5 a 35 \[cm\]\)$"):
        motor.calcular(x_hasta_35, E(200.0, 37.0, 10.0, 100.0, 10.0))
    with pytest.raises(motor.FueraDeTabla, match=r"^El lado Y de las mandíbulas = 37.00 \[cm\] está fuera de la tabla \(2.5 a 35 \[cm\]\)$"):
        motor.calcular(y_hasta_35, E(200.0, 10.0, 37.0, 100.0, 10.0))


def test_la_tabla_de_la_cuna_se_lee_solo_dentro_de_su_rango_en_cada_eje(datos):
    """PRU-2 (ronda 1 de los revisores): fuera de tabla, nunca un número, también para la lectura de la tabla de una cuña. La de 15° va de 2 a 40 [cm] en X y de 2 a 20 [cm] en
    Y. Un efectivo de 26 × 26 [cm] con mandíbulas de 40 × 20 está en la tabla en X y no en Y: FueraDeTabla (comprobar el lado Y contra el rango de X daba 348.19 UM, y solo una
    aserción de formato de las unidades lo veía). Y al revés: 30 [cm] en X, que sí cabe en X aunque pase del rango de Y, se lee."""
    t = datos.cunas[15].tabla
    assert (t.x[0], t.x[-1], t.y[0], t.y[-1]) == (2.0, 40.0, 2.0, 20.0)
    with pytest.raises(motor.FueraDeTabla, match=r"^El lado Y que se lee en la tabla de la cuña de 15° = 26.00 \[cm\] está fuera de la tabla \(2 a 20 \[cm\]\)$"):
        motor.calcular(datos, E(200.0, 40.0, 20.0, 100.0, 10.0, x_ef=26.0, y_ef=26.0, cuna=15, cuna_orientacion="IN"))
    r = motor.calcular(datos, E(200.0, 40.0, 20.0, 100.0, 10.0, x_ef=30.0, y_ef=12.0, cuna=15, cuna_orientacion="IN"))
    assert _origen(r, "WF") == ("tabla", "tabla en 30.00 × 12.00 [cm]; a 10 [cm]")


def test_con_cuna_el_punto_se_mide_desde_el_eje_y_no_desde_el_centro_del_campo(datos):
    """PRU-3 (ronda 1 de los revisores): «fuera del eje» es la distancia del punto al EJE del haz (DC9), no al centro del campo de las mandíbulas, que en un campo asimétrico es
    otro sitio. Un punto sobre el eje de un campo de centro (3, 2) está en el eje y se calcula; el punto en el centro de ese campo está a 3.6 [cm] del eje y pide el factor a
    mano. Medir desde el centro lo hacía al revés, y solo el recuento exacto de la prueba al azar lo veía, sin decir por qué."""
    base = dict(cuna=15, cuna_orientacion="IN")
    simetrico = motor.calcular(datos, E(200.0, 20.0, 10.0, 100.0, 10.0, **base))
    en_el_eje = motor.calcular(datos, E(200.0, 20.0, 10.0, 100.0, 10.0, centro_x=3.0, centro_y=2.0, **base))
    assert _origen(en_el_eje, "WF")[0] == "tabla" and factor(en_el_eje, "WF") == factor(simetrico, "WF")
    with pytest.raises(motor.FaltaDato, match="Con cuña y fuera del eje"):
        motor.calcular(datos, E(200.0, 20.0, 10.0, 100.0, 10.0, centro_x=3.0, centro_y=2.0, punto_x=3.0, punto_y=2.0, **base))


def test_la_tabla_busca_cada_lado_en_su_propio_eje():
    """PRU-1, la misma clase en `contiene` y `celdas_usadas` (dos mutaciones hermanas que tampoco veía ninguna prueba): con una tabla de ejes distintos (X de 2 a 16, Y de 3 a 12)
    cada lado se busca en su eje. Las tablas del 600C tienen el mismo eje en X y en Y, o uno prefijo del otro, y por eso cambiarlos de sitio no se notaba; las de otros equipos
    llegarán por UM.3 y UM.5."""
    t = motor.TablaFactores(np.array([2.0, 4.0, 8.0, 16.0]), np.array([3.0, 6.0, 12.0]), np.ones((3, 4)))
    assert t.contiene(16.0, 3.0) and t.contiene(2.0, 12.0) and t.contiene(5.0, 9.0)
    assert not t.contiene(1.9, 5.0) and not t.contiene(16.1, 5.0) and not t.contiene(5.0, 2.9) and not t.contiene(5.0, 12.1)
    assert t.celdas_usadas(5.0, 9.0) == {(6.0, 4.0), (6.0, 8.0), (12.0, 4.0), (12.0, 8.0)}      # (fila = Y, columna = X)
    assert t.celdas_usadas(4.0, 6.0) == {(6.0, 4.0)} and t.celdas_usadas(16.0, 12.0) == {(12.0, 16.0)} and t.celdas_usadas(2.0, 3.0) == {(3.0, 2.0)}
