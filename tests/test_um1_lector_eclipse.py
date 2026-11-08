"""UM.1 (PLAN_CALCULADORA_UM_05-11.md): el lector de las exportaciones de Eclipse, `services/um_lector_eclipse.py`.

Lo que se fija: lo que la app lee de un archivo de Eclipse es exactamente lo que dice el archivo, y si no lo entiende lo dice, con su motivo, en vez
de adivinar (intuicion de garantia del bloque UM.1; H1, H2, H4, H5 y DC13 del plan).

LOS DATOS (`tests/datos_um/600C/`) son copia byte a byte, con su marca de orden de bytes (BOM UTF-8) y sus finales CRLF, de la exportacion del
Clinac 600C del 05-11-2026: los 21 archivos de `Archivos_UseApp/Archivos QA/Calculadora_UM/Datos 600 Felipe/Nuevos/` y el `name.data` de la
carpeta de arriba. Viven dentro del repositorio para que la prueba corra en cualquier equipo y NUNCA se salte (la suite da exactamente 4 skipped).
Los 12 que el motor lee y los 10 que la carga ignora (lo calculado por AAA, los perfiles de cuna y la transmision): las tareas siguientes (el armado,
la carga) prueban tambien que esos 10 se ignoran. El sha256 de cada original esta escrito aqui: si git, un editor o una copia cambian un byte (un
CRLF que pasa a LF), la prueba lo dice.

Los valores esperados salen del plan y de los archivos leidos aqui a mano (con expresiones regulares sobre el texto), nunca del propio lector.
Sin Qt y sin base de datos. El modulo se importa dentro de la fixture `lector`: sin el, cada caso que lo usa cae por ModuleNotFoundError (el rojo de
UM.1) y los que solo miran los datos pasan.
"""
import hashlib
import importlib
import os
import random
import re

import numpy as np
import pytest

DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos_um", "600C")
PDD_ABIERTO = "CLINAC 600C_Open Field - 00_Measured Depth Doses.txt"
OF_ABIERTA = "CLINAC 600C_Open Field - 00_Output Factors.txt"
PERFILES = "CLINAC 600C_Open Field - 00_Processed Measured Profiles.txt"
NAME_DATA = "name.data"
BOM = b"\xef\xbb\xbf"

# sha256 y tamano en bytes de cada original (Archivos_UseApp/Archivos QA/Calculadora_UM/Datos 600 Felipe/), medidos en el pre-vuelo de UM.1.
ORIGINALES = {
    "CLINAC 600C_Open Field - 00_Calculated Depth Doses.txt": ("949c2b05cf10f926f0f5370e5f3836a553ddfc99f2d6b3c9d598f34e222f6bfe", 61857),
    "CLINAC 600C_Open Field - 00_Calculated Profiles.txt": ("9d170c5fbacb148bae3bc8351eedbe4c7c5119646a28bb28922e2b3eac4adce5", 151379),
    "CLINAC 600C_Open Field - 00_Measured Depth Doses.txt": ("d2cdeeca5012b7ed44c7c589cebdf1005c19ff9c9914a6c427a874477b1b6f03", 122181),
    "CLINAC 600C_Open Field - 00_Output Factors.txt": ("662a0d3d3ce2a4d61b0ad82b94ee810a72b73c9255cc2c06720694c39910e03f", 1376),
    "CLINAC 600C_Open Field - 00_Processed Measured Profiles.txt": ("263ad26cc1b573f68d18c69d56b179f4de96107893f6ade3e29416deb7b6d7d7", 111067),
    "CLINAC 600C_Standard Wedge - 15_Measured Wedge Depth Doses.txt": ("03a016e1dd329c0f1c3e25092db3d3514a78eda299c189b9eb38092690fff280", 28666),
    "CLINAC 600C_Standard Wedge - 15_Measured Wedge Profiles.txt": ("b5c5d513f1466f96548eacc89bb759fab679a971904b42de1a884f38ad6a5c98", 184606),
    "CLINAC 600C_Standard Wedge - 15_Output Factors.txt": ("911ec2fefcbcf4799d45191977b5f5eb8bc2a6632cdbcea645586d998380698d", 1024),
    "CLINAC 600C_Standard Wedge - 15_Wedge Transmission.txt": ("356a251e71e448d8f9dd8fb024bafc52dfcd94866f6e2aefdeb15f524e17b33f", 930),
    "CLINAC 600C_Standard Wedge - 30_Measured Wedge Depth Doses.txt": ("0dcdb1ad492277876f585adaec0a8cbed554db65075d40eaa7456e61e060d1a8", 28666),
    "CLINAC 600C_Standard Wedge - 30_Measured Wedge Profiles.txt": ("72d5aa4b330190fea620e5604a9b2d172ec5526a18583a9a25bb52acf7c08cc7", 188236),
    "CLINAC 600C_Standard Wedge - 30_Output Factors.txt": ("8c12a244795a7c39cb8118e99a8eecba4f54f6538bbdde15f0528f5dd8b55dbf", 1024),
    "CLINAC 600C_Standard Wedge - 30_Wedge Transmission.txt": ("37bf389e94665c436b0714b25a9f08eaf787844ce60a3a84175c952b767be852", 930),
    "CLINAC 600C_Standard Wedge - 45_Measured Wedge Depth Doses.txt": ("0161ca574f7853b46cb422a2b4a457e11b54058182eeaee69ca24a5dfbc181b4", 28666),
    "CLINAC 600C_Standard Wedge - 45_Measured Wedge Profiles.txt": ("41bfb55e75f922d9eb04d850eca03c2d46af8bad5f276a173fc7eb5694b66703", 184540),
    "CLINAC 600C_Standard Wedge - 45_Output Factors.txt": ("781fea0c2425edf245dc7173885a8f33359c101fab1394c43ee393796b672e27", 1024),
    "CLINAC 600C_Standard Wedge - 45_Wedge Transmission.txt": ("116f71921d3526381442d14123355c605624dfbd5b48338085ec81a6e36681cd", 930),
    "CLINAC 600C_Standard Wedge - 60_Measured Wedge Depth Doses.txt": ("ef60cf005251376eae4351a6944bfacd2e30c1592105cbf158df880a63a21faa", 22937),
    "CLINAC 600C_Standard Wedge - 60_Measured Wedge Profiles.txt": ("6b06d1caa311273b5081980d85eefaca464217a2fcbf2ca1e3f93585985e5a1d", 129011),
    "CLINAC 600C_Standard Wedge - 60_Output Factors.txt": ("fd95dcc8395a2d27fb17e3988619c9a13a5de8b938342802096ce69bcc63994f", 936),
    "CLINAC 600C_Standard Wedge - 60_Wedge Transmission.txt": ("0f4ba542d70f61b7a5fc8483db54323e4674ec46b6d209f41dfe934237a7d005", 930),
    "name.data": ("285ffa41286e3a81b37c7f85dde63ada36530c552a8ccba5be1d7c2428565694", 1183),
}
# Lo que dice la cabecera de cada archivo (accesorio, dato), leido con grep en el pre-vuelo; todos dicen «machine: 600C, 6X».
IDENTIDADES = {
    "CLINAC 600C_Open Field - 00_Calculated Depth Doses.txt": ("Open Field - 00", "OPD_calculated"),
    "CLINAC 600C_Open Field - 00_Calculated Profiles.txt": ("Open Field - 00", "OPP_calculated"),
    "CLINAC 600C_Open Field - 00_Measured Depth Doses.txt": ("Open Field - 00", "OPD"),
    "CLINAC 600C_Open Field - 00_Output Factors.txt": ("Open Field - 00", "OutputFactorTable"),
    "CLINAC 600C_Open Field - 00_Processed Measured Profiles.txt": ("Open Field - 00", "OPP_processed"),
    **{f"CLINAC 600C_Standard Wedge - {a}_{n}": (f"Standard Wedge - {a}", d) for a in (15, 30, 45, 60)
       for n, d in (("Measured Wedge Depth Doses.txt", "WDD"), ("Measured Wedge Profiles.txt", "WDP"), ("Output Factors.txt", "OutputFactorTable"),
                    ("Wedge Transmission.txt", "WedgeTransmission"))},
    "name.data": ("Standard Wedge - 15", "WedgeParameters"),
}
TABLAS = ["CLINAC 600C_Open Field - 00_Output Factors.txt"] + [f"CLINAC 600C_Standard Wedge - {a}_Output Factors.txt" for a in (15, 30, 45, 60)]
CURVAS_QUE_LEE_EL_MOTOR = [PDD_ABIERTO, PERFILES] + [f"CLINAC 600C_Standard Wedge - {a}_Measured Wedge Depth Doses.txt" for a in (15, 30, 45, 60)]


@pytest.fixture(scope="module")
def lector():
    return importlib.import_module("services.um_lector_eclipse")


def crudo(nombre):
    with open(os.path.join(DATOS, nombre), "rb") as f:
        return f.read()


def texto(lector, nombre):
    return lector.decodificar(crudo(nombre))


def tabla(lector, nombre=OF_ABIERTA):
    return lector.leer_tabla_of(texto(lector, nombre))


def celda(t, y, x):
    return float(t.m[list(t.y).index(y), list(t.x).index(x)])


def fila_a_mano(nombre, y):
    """Los numeros de la fila Y de una tabla (su lado Y y sus valores), leidos sobre los bytes del archivo sin el lector: las lineas que siguen a la
    de los lados X, que es la primera despues de «# Data»."""
    filas = crudo(nombre).split(b"# Data\r\n", 1)[1].split(b"\r\n")[1:]
    return next([float(v) for v in f.split(b",")] for f in filas if f.split(b",")[0] == f"{y:g}".encode())


def puntos_a_mano(nombre):
    """Los puntos de CADA curva de un archivo (x, z en mm y valor), leidos sobre los bytes con una expresion regular y sin el lector: [[(x, z, valor), ...], ...]."""
    return [[(float(x), float(z), float(v)) for x, _, z, v in re.findall(rb"<([-+]\d+\.\d) ([-+]\d+\.\d) ([-+]\d+\.\d) ([-+]\d+\.\d+)>", bloque)]
            for bloque in (b.split(b"$ENOM")[0] for b in crudo(nombre).split(b"$STOM")[1:])]


# ---------- Los datos: copia exacta de la exportacion ----------
def test_la_carpeta_trae_exactamente_los_22_archivos_de_la_exportacion():
    assert sorted(os.listdir(DATOS)) == sorted(ORIGINALES)


@pytest.mark.parametrize("nombre", sorted(ORIGINALES))
def test_cada_archivo_es_copia_byte_a_byte_del_original(nombre):
    contenido = crudo(nombre)
    assert (hashlib.sha256(contenido).hexdigest(), len(contenido)) == ORIGINALES[nombre]


def test_los_archivos_traen_la_marca_de_orden_y_finales_crlf():
    """H1: UTF-8 con BOM y CRLF en todas las lineas; si un final de linea se convirtiera, esto dice cual archivo."""
    for nombre in ORIGINALES:
        contenido = crudo(nombre)
        assert contenido.startswith(BOM) and contenido.endswith(b"\r\n"), nombre
        assert contenido.count(b"\n") == contenido.count(b"\r\n") == contenido.count(b"\r"), nombre


# ---------- Quien es cada archivo ----------
def test_el_lector_identifica_cada_archivo(lector):
    for nombre, (accesorio, dato) in IDENTIDADES.items():
        i = lector.identidad(texto(lector, nombre))
        assert (i.maquina, i.haz, i.accesorio, i.dato) == ("600C", "6X", accesorio, dato), nombre
        assert i.angulo_cuna == (int(accesorio.rsplit(" ", 1)[1]) if accesorio.startswith("Standard Wedge") else None), nombre
    assert sorted(IDENTIDADES) == sorted(ORIGINALES)


@pytest.mark.parametrize("quitar", ["# machine: 600C, 6X\n", "# add on: Open Field - 00\n", "# data: OPD\n"])
def test_una_cabecera_sin_maquina_accesorio_o_tipo_de_dato_se_rechaza(lector, quitar):
    t = texto(lector, PDD_ABIERTO)
    assert t.count(quitar) == 12
    with pytest.raises(lector.ArchivoNoReconocido, match="la cabecera no dice máquina, accesorio y tipo de dato: no parece una exportación de Eclipse"):
        lector.identidad(t.replace(quitar, ""))


def test_decodificar_admite_marca_de_orden_latin1_y_finales_de_linea(lector):
    assert lector.decodificar("﻿a\r\nb\rc".encode("utf-8")) == "a\nb\nc"
    assert lector.decodificar("﻿a\r\nb") == "a\nb"
    assert lector.decodificar("ñ".encode("latin-1")) == "ñ"
    for nombre in ORIGINALES:
        t = texto(lector, nombre)
        assert "\r" not in t and not t.startswith("﻿") and t.endswith("\n"), nombre


# ---------- Lo que dicen las curvas (H1, H3) ----------
def test_el_pdd_tiene_lo_que_dice_el_archivo(lector):
    curvas = lector.leer_curvas(texto(lector, PDD_ABIERTO))
    assert [c.campo_cm for c in curvas] == [(lado, lado) for lado in (2.5, 3.0, 4.0, 5.0, 6.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0)]
    for c in curvas:
        assert c.ssd_cm == 100.0 and len(c.z_cm) == 301
        assert np.array_equal(c.z_cm, np.arange(301) / 10) and not np.any(c.x_cm)     # z de 0 a 30 cm cada 1 mm, sobre el eje: las columnas no se cruzan
    diez = next(c for c in curvas if c.campo_cm == (10.0, 10.0))
    bloque = crudo(PDD_ABIERTO).split(b"%FLSZ 100*100")[1].split(b"$ENOM")[0]
    a_mano = {float(z) / 10: float(v) for z, v in re.findall(rb"<\+000\.0 \+000\.0 \+(\d+\.\d) \+(\d+\.\d+)>", bloque)}
    assert len(a_mano) == 301 and a_mano[5.0] == 86.0 and a_mano[10.0] == 66.2
    assert diez.valor[50] == 86.0 and diez.valor[100] == 66.2       # DA-95: PDD(5; 10 x 10) = 86.0 y PDD(10; 10 x 10) = 66.2
    assert {z: v for z, v in zip(diez.z_cm.tolist(), diez.valor.tolist())} == a_mano
    # (UM.1, implementador) Lo que el archivo no dice no se inventa: una curva sin %SSD queda con ssd_cm None (no con 100), y un campo positivo, por chico que sea, se lee tal cual.
    sin_ssd = lector.leer_curvas(texto(lector, PDD_ABIERTO).replace("%SSD 1000\n", "", 1))
    assert sin_ssd[0].ssd_cm is None and all(c.ssd_cm == 100.0 for c in sin_ssd[1:])
    assert lector.leer_curvas(texto(lector, PDD_ABIERTO).replace("%FLSZ 025*025", "%FLSZ 005*005", 1))[0].campo_cm == (0.5, 0.5)
    assert len(lector.leer_curvas(texto(lector, PDD_ABIERTO).replace("$NUMS 012\n", "", 1))) == 12       # un archivo que no anuncia cuantas curvas trae se lee igual


def test_los_perfiles_son_los_de_h1(lector):
    """59 curvas a 1.4, 5, 10, 20 y 30 cm, medio perfil; falta solo el 40 x 40 a 30 cm. La z de cada perfil es constante y la x recorre el campo."""
    curvas = lector.leer_curvas(texto(lector, PERFILES))
    assert len(curvas) == 59 and all(c.ssd_cm == 100.0 for c in curvas)
    for c in curvas:
        assert np.ptp(c.z_cm) == 0 and np.ptp(c.x_cm) > 0
    por_profundidad = {}
    for c in curvas:
        por_profundidad.setdefault(round(float(c.z_cm[0]), 1), set()).add(c.campo_cm)
    assert sorted(por_profundidad) == [1.4, 5.0, 10.0, 20.0, 30.0]
    assert (40.0, 40.0) not in por_profundidad[30.0] and (35.0, 35.0) in por_profundidad[30.0]
    assert all((40.0, 40.0) in por_profundidad[d] for d in (1.4, 5.0, 10.0, 20.0))
    # (UM.1, implementador) La posicion x (cm), la z y el valor de CADA punto, contra los bytes leidos con una expresion regular: sin esto ninguna asercion fijaba la escala (mm a cm)
    # ni el signo de x de un perfil (un perfil leido en mm, o sin el signo, da otro OAR). Los perfiles medidos son medio perfil (x de 0 a 24.75 cm en el de 40 x 40; su primer
    # punto es «-000.0», un cero negativo) y los de cuna son enteros, con x negativo.
    entero = "CLINAC 600C_Standard Wedge - 15_Measured Wedge Profiles.txt"
    for nombre in (PERFILES, entero):
        leidas, a_mano = lector.leer_curvas(texto(lector, nombre)), puntos_a_mano(nombre)
        assert len(leidas) == len(a_mano) and len(a_mano) > 0
        for c, puntos in zip(leidas, a_mano):
            assert c.x_cm.tolist() == [x / 10 for x, _, _ in puntos] and c.z_cm.tolist() == [z / 10 for _, z, _ in puntos] and c.valor.tolist() == [v for _, _, v in puntos]
    assert max(c.x_cm.max() for c in curvas) == 24.75
    assert min(c.x_cm.min() for c in lector.leer_curvas(texto(lector, entero))) < -13


@pytest.mark.parametrize("angulo, campos", [(15, {4, 10, 15, 20, 40}), (30, {4, 10, 15, 20, 40}), (45, {4, 10, 15, 20, 40}), (60, {4, 10, 15, 40})])
def test_los_pdd_de_cuna_son_los_de_h1(lector, angulo, campos):
    """H1: PDD de cuna de 4, 10, 15, 20 y 40 x 20 (en la de 60, 4, 10, 15 y 40 x 15)."""
    curvas = lector.leer_curvas(texto(lector, f"CLINAC 600C_Standard Wedge - {angulo}_Measured Wedge Depth Doses.txt"))
    largo = 15.0 if angulo == 60 else 20.0
    assert {c.campo_cm for c in curvas} == {(float(l), float(l)) if l < 40 else (40.0, largo) for l in campos}
    assert all(c.ssd_cm == 100.0 and not np.any(c.x_cm) for c in curvas)


# ---------- Lo que dicen las tablas (H2, H4) ----------
@pytest.mark.parametrize("nombre", TABLAS)
def test_las_tablas_de_factores_declaran_ssd_100_y_5_cm_y_valen_1_en_10_x_10(lector, nombre):
    t = tabla(lector, nombre)
    assert (t.ssd_cm, t.prof_cm) == (100.0, 5.0) and celda(t, 10, 10) == 1.0


def test_filas_y_columnas_por_la_fisica_y_por_la_cuna(lector):
    t = tabla(lector)
    assert celda(t, 5, 40) == 0.969 and celda(t, 40, 5) == 0.990     # H4 (a): cerrar Y (superiores) baja mas que cerrar X
    for y in (2.5, 5, 10, 30, 40):
        assert t.m[list(t.y).index(y)].tolist() == fila_a_mano(OF_ABIERTA, y)[1:]    # cada fila del archivo es una Y
    assert t.x.tolist() == [2.5, 3, 4, 5, 6, 10, 15, 20, 25, 30, 35, 40] == t.y.tolist()
    for angulo, hasta in ((15, 20), (30, 20), (45, 20), (60, 15)):
        c = tabla(lector, f"CLINAC 600C_Standard Wedge - {angulo}_Output Factors.txt")
        assert c.y[-1] == hasta and c.x[-1] == 40, angulo      # H4 (b): la cuna es de 40 x 20 (40 x 15) con el gradiente a lo largo de Y
        assert c.m[-1].tolist() == fila_a_mano(f"CLINAC 600C_Standard Wedge - {angulo}_Output Factors.txt", hasta)[1:]


def test_marca_los_valores_fuera_de_tendencia(lector):
    """H5: las cuatro celdas, exactas, con lo que indican sus vecinos (el plan da el rango redondeado a la milesima)."""
    hallados = {}
    for nombre, cual in ((OF_ABIERTA, "abierta"), (TABLAS[1], "15"), (TABLAS[3], "45"), (TABLAS[2], "30"), (TABLAS[4], "60")):
        for y, x, v, por_fila, por_columna in lector.valores_fuera_de_tendencia(tabla(lector, nombre)):
            hallados[(cual, y, x)] = (v, round(min(por_fila, por_columna), 3), round(max(por_fila, por_columna), 3))
    assert sorted(hallados) == sorted([("abierta", 30.0, 25.0), ("15", 6.0, 4.0), ("45", 3.0, 30.0), ("45", 15.0, 35.0)])
    t = tabla(lector)        # la celda Y = 30, X = 25 de la abierta, a mano: interpolacion en log(lado) entre sus vecinos de fila (X = 20 y 30) y de columna (Y = 25 y 35)
    entre = lambda a, va, b, vb, c: va + (vb - va) * (np.log(c) - np.log(a)) / (np.log(b) - np.log(a))
    (_, _, _, por_fila, por_columna), = lector.valores_fuera_de_tendencia(t)
    assert por_fila == pytest.approx(entre(20, celda(t, 30, 20), 30, celda(t, 30, 30), 25), abs=1e-12)
    assert por_columna == pytest.approx(entre(25, celda(t, 25, 25), 35, celda(t, 35, 25), 30), abs=1e-12)
    assert hallados[("abierta", 30.0, 25.0)][0] == 1.073 and 1.083 <= hallados[("abierta", 30.0, 25.0)][1] <= hallados[("abierta", 30.0, 25.0)][2] <= 1.085
    assert hallados[("15", 6.0, 4.0)][0] == 0.936 and 0.929 <= hallados[("15", 6.0, 4.0)][1] <= hallados[("15", 6.0, 4.0)][2] <= 0.930
    assert hallados[("45", 3.0, 30.0)][0] == 0.924 and 0.932 <= hallados[("45", 3.0, 30.0)][1] <= hallados[("45", 3.0, 30.0)][2] <= 0.940
    assert hallados[("45", 15.0, 35.0)][0] == 1.087 and 1.096 <= hallados[("45", 15.0, 35.0)][1] <= hallados[("45", 15.0, 35.0)][2] <= 1.097


def test_una_celda_en_silla_no_es_un_valor_fuera_de_tendencia(lector):
    """H5 exige el MISMO sentido en fila y en columna: una celda por encima de sus vecinos de fila y por debajo de los de columna (una silla, 0.7 % a
    cada lado) es curvatura, no un valor raro; en el mismo sentido si se marca. Tabla sintetica de 3 x 3 con el centro en 10 x 10."""
    lados = np.array([5.0, 10.0, 20.0])
    silla = lector.TablaOF(lados, lados, np.array([[0.95, 1.000, 0.96], [0.980, 1.0, 1.006], [0.97, 1.014, 0.98]]), 100.0, 5.0)
    mismo_sentido = lector.TablaOF(lados, lados, np.array([[0.95, 0.990, 0.96], [0.980, 1.0, 1.006], [0.97, 0.996, 0.98]]), 100.0, 5.0)
    assert lector.valores_fuera_de_tendencia(silla) == []
    (y, x, v, por_fila, por_columna), = lector.valores_fuera_de_tendencia(mismo_sentido)
    assert (y, x, v) == (10.0, 10.0, 1.0) and por_fila == pytest.approx(0.993) and por_columna == pytest.approx(0.993)


def test_lo_que_dice_el_name_data(lector):
    t = texto(lector, NAME_DATA)
    assert lector.dosis_de_referencia_cuna(t) == pytest.approx(0.6623 * 100 / 100)      # 0.6623 Gy por 100 MU = 0.6623 cGy/MU
    assert lector.dosis_de_referencia_cuna(t.replace("calibration depth[Gy]:0.662300", "calibration depth[cGy]:66.23")) == pytest.approx(0.6623)
    with pytest.raises(lector.ArchivoNoReconocido, match=r"viene en \[mGy\] por \[MU\]: se esperaba \[Gy\] o \[cGy\] por \[MU\]"):
        lector.dosis_de_referencia_cuna(t.replace("calibration depth[Gy]", "calibration depth[mGy]"))
    with pytest.raises(lector.ArchivoNoReconocido, match=r"viene en \[Gy\] por \[cGy\]: se esperaba \[Gy\] o \[cGy\] por \[MU\]"):       # (UM.1, implementador) las MU tambien deben venir en [MU]
        lector.dosis_de_referencia_cuna(t.replace("[MU]:100.000000", "[cGy]:100.000000"))
    assert lector.orientacion_de_cuna(t) == "IN" and lector.orientacion_de_cuna(t.replace("RIGHT)[]:IN", "RIGHT)[]:left")) == "LEFT"
    assert lector.angulo_en_parametros(t) == 15.0
    parametros = lector.leer_parametros(t)
    assert parametros["Wedge angle"] == ("15.0", "deg") and parametros["Reference MU for hard wedge at calibration depth"] == ("100.000000", "MU")


# ---------- Lo que no entiende lo rechaza con su motivo (DC13) ----------
def test_el_lector_rechaza_lo_que_no_entiende(lector):
    with pytest.raises(lector.ArchivoNoReconocido, match="no parece una exportación de Eclipse"):
        lector.identidad("cualquier cosa")
    with pytest.raises(lector.ArchivoNoReconocido, match="anuncia 2 curvas y trae 1: parece cortado"):
        lector.leer_curvas("$NUMS 002\n$STOM\n%FLSZ 100*100\n<+0 +0 +0 +1>\n$ENOM\n$ENOF\n")
    with pytest.raises(lector.ArchivoNoReconocido, match="no tiene curvas W2CAD"):
        lector.leer_curvas(texto(lector, OF_ABIERTA))
    with pytest.raises(lector.ArchivoNoReconocido, match="no vale 1.000 en 10 × 10"):
        lector.leer_tabla_of("%TYPE OutputFactorTable\n%SourcePhantomDistance 1000\n%DetectorDepth 50\n# Data\n5, 10\n5, 0.9, 0.95\n10, 0.95, 1.1\n")
    with pytest.raises(lector.ArchivoNoReconocido, match="no es una tabla de factores"):
        lector.leer_tabla_of(texto(lector, PDD_ABIERTO))
    with pytest.raises(lector.ArchivoNoReconocido, match="no tiene parámetros"):
        lector.leer_parametros("machine: 600C, 6X\nData parameters:\n")
    # (UM.1, implementador) Una tabla a la que le falta la SSD, la profundidad o su tipo no es una tabla de factores (arriba solo se probaba el PDD, al que le faltan las tres cosas a la
    # vez); y los lados de la tabla deben ser positivos y crecer de verdad, en X y en Y (repetidos o al reves no se aceptan), pero cualquier lado mayor que 0 sirve.
    tabla_de_factores = texto(lector, OF_ABIERTA)
    for viejo, nuevo in (("%SourcePhantomDistance 1000\n", ""), ("%DetectorDepth 50\n", ""), ("%TYPE OutputFactorTable\n", "%TYPE OPD\n")):
        assert tabla_de_factores.count(viejo) == 1, viejo
        with pytest.raises(lector.ArchivoNoReconocido, match="no es una tabla de factores con SSD y profundidad en la cabecera"):
            lector.leer_tabla_of(tabla_de_factores.replace(viejo, nuevo))
    for viejo, nuevo in (("\n2.5, 0.870", "\n0, 0.870"), ("\n3, 0.879", "\n2.5, 0.879"), ("\n4, 0.892", "\n2, 0.892"), ("3, 4, 5", "3, 3, 5")):     # Y en 0, Y repetida, Y que baja, X repetida
        assert tabla_de_factores.count(viejo) == 1, viejo
        with pytest.raises(lector.ArchivoNoReconocido, match="los lados de la tabla de factores deben ser positivos y crecientes"):
            lector.leer_tabla_of(tabla_de_factores.replace(viejo, nuevo))
    chica = lector.leer_tabla_of(tabla_de_factores.replace("2.5, 3, 4", "0.5, 3, 4", 1).replace("\n2.5, 0.870", "\n0.5, 0.870", 1))
    assert (chica.x[0], chica.y[0]) == (0.5, 0.5)
    for viejo, nuevo in (("6, 10, 15", "6, 11, 15"), ("\n10, 0.918", "\n11, 0.918")):      # sin columna X = 10 y sin fila Y = 10: no hay donde exigir el 1.000
        assert tabla_de_factores.count(viejo) == 1, viejo
        with pytest.raises(lector.ArchivoNoReconocido, match="no vale 1.000 en 10 × 10"):
            lector.leer_tabla_of(tabla_de_factores.replace(viejo, nuevo))


@pytest.mark.parametrize("fraccion", [0.5, 0.2, 0.9])
@pytest.mark.parametrize("nombre", [PDD_ABIERTO, "CLINAC 600C_Standard Wedge - 15_Measured Wedge Depth Doses.txt", PERFILES])
def test_un_archivo_cortado_dentro_de_su_ultima_curva_se_nota(lector, nombre, fraccion):
    t = texto(lector, nombre)
    ultima = t.rindex("$STOM")
    with pytest.raises(lector.ArchivoNoReconocido, match="cortado|punto"):
        lector.leer_curvas(t[:ultima + int((len(t) - ultima) * fraccion)])


@pytest.mark.parametrize("nombre", CURVAS_QUE_LEE_EL_MOTOR)
def test_cortes_al_azar_de_un_archivo_de_curvas(lector, nombre):
    """Semilla fija. Un corte de los BYTES dentro de la ultima curva (hasta su $ENOF) siempre se rechaza por cortado; uno en cualquier punto del
    archivo se rechaza o, si cae despues de $ENOF, da exactamente las mismas curvas: nunca otras."""
    entero = crudo(nombre)
    completas = lector.leer_curvas(lector.decodificar(entero))
    azar = random.Random("UM.1 " + nombre)      # semilla fija (una cadena: la misma secuencia en cada corrida y en cada equipo)
    desde, hasta = entero.rindex(b"$STOM"), entero.rindex(b"$ENOF") + len(b"$ENOF")
    for corte in [azar.randrange(desde, hasta) for _ in range(25)]:
        with pytest.raises(lector.ArchivoNoReconocido, match="cortado"):
            lector.leer_curvas(lector.decodificar(entero[:corte]))
    for corte in [azar.randrange(1, len(entero)) for _ in range(25)] + [hasta, hasta + 1]:
        try:
            leidas = lector.leer_curvas(lector.decodificar(entero[:corte]))
        except lector.ArchivoNoReconocido:
            assert corte < hasta, corte
            continue
        assert corte >= hasta and len(leidas) == len(completas), corte
        for a, b in zip(leidas, completas):
            assert a.campo_cm == b.campo_cm and a.ssd_cm == b.ssd_cm and np.array_equal(a.x_cm, b.x_cm) and np.array_equal(a.z_cm, b.z_cm) and np.array_equal(a.valor, b.valor)


@pytest.mark.parametrize("nombre", TABLAS)
def test_cada_corte_de_una_tabla_se_rechaza_o_es_un_prefijo_exacto(lector, nombre):
    """Todos los cortes posibles de los BYTES de cada tabla: la tabla no trae marca de fin, asi que un corte justo al final de una fila que ya tiene
    la de 10 cm se lee como una tabla con menos filas (el motor no extrapola: sin las filas grandes no hay numero); cualquier otro corte se rechaza,
    y ninguno cambia un valor."""
    entero = crudo(nombre)
    completa = lector.leer_tabla_of(lector.decodificar(entero))
    filas_aceptadas = set()
    for corte in range(1, len(entero) + 1):
        try:
            leida = lector.leer_tabla_of(lector.decodificar(entero[:corte]))
        except lector.ArchivoNoReconocido:
            continue
        n = len(leida.y)
        assert entero[:corte].endswith((b"\r", b"\r\n")), corte
        assert leida.x.tolist() == completa.x.tolist() and leida.y.tolist() == completa.y[:n].tolist() and leida.m.tolist() == completa.m[:n].tolist(), corte
        assert (leida.ssd_cm, leida.prof_cm) == (completa.ssd_cm, completa.prof_cm)
        filas_aceptadas.add(n)
    assert filas_aceptadas == set(range(list(completa.y).index(10.0) + 1, len(completa.y) + 1))


def test_un_archivo_sin_su_final_se_nota(lector):
    t = texto(lector, PDD_ABIERTO)
    assert len(lector.leer_curvas(t)) == 12
    with pytest.raises(lector.ArchivoNoReconocido, match="el archivo no termina: parece cortado"):
        lector.leer_curvas(t[:t.rindex("$ENOF")])


def test_un_punto_sin_cerrar_o_una_curva_sin_puntos_se_rechazan(lector):
    t = texto(lector, PDD_ABIERTO)
    with pytest.raises(lector.ArchivoNoReconocido, match="hay un punto que no se puede leer"):
        lector.leer_curvas(t.replace("+045.300>", "+045.300", 1))
    with pytest.raises(lector.ArchivoNoReconocido, match="hay una curva sin puntos"):
        lector.leer_curvas("$NUMS 001\n$STOM\n%FLSZ 100*100\n$ENOM\n$ENOF\n")
    with pytest.raises(lector.ArchivoNoReconocido, match="cuatro números válidos"):
        lector.leer_curvas(t.replace("<+000.0 +000.0 +000.0 +045.300>", "<+000.0 +000.0 +045.300>", 1))


def test_una_tabla_cortada_dentro_de_un_numero_se_nota(lector):
    """Daba 1.1 en la celda 40 x 40 en vez de su valor: -10 % en las UM."""
    t = texto(lector, OF_ABIERTA)
    assert t.endswith("\n")
    with pytest.raises(lector.ArchivoNoReconocido, match="no termina en un final de línea: parece cortada"):
        lector.leer_tabla_of(t.rstrip("\n")[:-2])


def test_una_curva_que_no_termina_se_nota(lector):
    with pytest.raises(lector.ArchivoNoReconocido, match="no se entiende|no termina"):
        lector.leer_curvas(texto(lector, PDD_ABIERTO).replace("$ENOM\n", "", 1))
    with pytest.raises(lector.ArchivoNoReconocido, match="una curva no termina: parece cortado"):
        lector.leer_curvas("$NUMS 001\n$STOM\n%FLSZ 100*100\n<+0 +0 +0 +1>\n$ENOF\n")


def test_una_linea_que_no_se_entiende_no_se_salta(lector):
    t = texto(lector, PDD_ABIERTO).replace("<+000.0 +000.0 +100.0 ", "+000.0 +000.0 +100.0 ", 1)
    with pytest.raises(lector.ArchivoNoReconocido, match="hay una línea que no se entiende: «\\+000.0"):
        lector.leer_curvas(t)


def test_lo_que_sigue_al_final_de_una_curva_no_se_salta(lector):
    """Tras $ENOM solo caben comentarios (los trae el paquete de Varian) y el $ENOF del final: un punto o una linea suelta entre dos curvas se rechaza."""
    t = texto(lector, PDD_ABIERTO)
    for intruso in ("<+000.0 +000.0 +050.0 +086.000>", "basura", "!basura"):       # (UM.1, corrector) «!» es menor que «$»: ninguna linea suelta, por rara que sea, se salta
        with pytest.raises(lector.ArchivoNoReconocido, match=f"después del final de una curva \\(\\$ENOM\\) que no se entiende: «{re.escape(intruso[:10])}"):
            lector.leer_curvas(t.replace("$ENOM\n$STOM", f"$ENOM\n{intruso}\n$STOM", 1))
    with pytest.raises(lector.ArchivoNoReconocido, match="después del final"):
        lector.leer_curvas(t + "<+000.0 +000.0 +050.0 +086.000>\n")
    # (UM.1, corrector) la ultima linea del texto tambien cuenta aunque no lleve final de linea, y el motivo cita la PRIMERA linea suelta
    with pytest.raises(lector.ArchivoNoReconocido, match="después del final de una curva \\(\\$ENOM\\) que no se entiende: «basura»"):
        lector.leer_curvas(t.rstrip("\n") + "\nbasura")
    with pytest.raises(lector.ArchivoNoReconocido, match="que no se entiende: «primera»"):
        lector.leer_curvas(t + "primera\nsegunda\n")
    con_comentarios = t.replace("$ENOM\n$STOM", "$ENOM\n#\n# siguiente curva\n\n$STOM").replace("$ENOM\n$ENOF", "$ENOM\n#\n$ENOF\n#")
    assert [c.campo_cm for c in lector.leer_curvas(con_comentarios)] == [c.campo_cm for c in lector.leer_curvas(t)]


def test_una_curva_sin_campo_se_rechaza_con_su_motivo(lector):
    with pytest.raises(lector.ArchivoNoReconocido, match="hay una curva que no dice su campo"):
        lector.leer_curvas(texto(lector, PDD_ABIERTO).replace("%FLSZ 100*100\n", "", 1))


@pytest.mark.parametrize("viejo, nuevo, mensaje", [("%SSD 1000", "%SSD cien", "La SSD de una curva no se puede leer: «cien»"), ("%FLSZ 100*100", "%FLSZ 100", "no dice su campo"),
                                                    ("%FLSZ 100*100", "%FLSZ a*b", "El campo de una curva no se puede leer: «a»"),
                                                    ("%FLSZ 400*400", "%FLSZ inf*inf", "El campo de una curva no se puede leer: «inf»")])
def test_una_cabecera_que_no_se_lee_da_su_motivo(lector, viejo, nuevo, mensaje):
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(mensaje)):
        lector.leer_curvas(texto(lector, PDD_ABIERTO).replace(viejo, nuevo))


@pytest.mark.parametrize("campo", ["%FLSZ 000*000", "%FLSZ 100*000", "%FLSZ -10*100"])
def test_una_curva_con_un_campo_imposible_se_rechaza(lector, campo):
    with pytest.raises(lector.ArchivoNoReconocido, match="hay una curva con un campo imposible"):
        lector.leer_curvas(texto(lector, PDD_ABIERTO).replace("%FLSZ 100*100", campo))


@pytest.mark.parametrize("ssd, mensaje", [("0", "es 0 [cm] y debe estar entre 60 y 140 [cm]"), ("100", "es 10 [cm] y debe estar entre 60 y 140 [cm]"),
                                          ("500", "es 50 [cm]"), ("1500", "es 150 [cm]"), ("-1000", "es -100 [cm]"), ("599", "es 59.9 [cm]"),
                                          ("1401", "es 140.1 [cm]"), ("nan", "no se puede leer: «nan»"), ("inf", "no se puede leer: «inf»")])
def test_una_ssd_que_no_es_de_un_acelerador_se_rechaza(lector, ssd, mensaje):
    """Hallazgo del pre-vuelo de UM.1: con la SSD de los perfiles en 0, en cm (100) o en 50 o 150 cm, la referencia leia el archivo y el motor daba
    229.6, 229.5, 227.8 y 223.3 UM en vez de 224.9 (20 x 20, SSD 90, 10 cm, x = 5), sin aviso. La misma regla para la tabla de factores."""
    with pytest.raises(lector.ArchivoNoReconocido, match="La SSD de una curva " + re.escape(mensaje)):
        lector.leer_curvas(texto(lector, PERFILES).replace("%SSD 1000", f"%SSD {ssd}"))
    with pytest.raises(lector.ArchivoNoReconocido, match="La SSD de la tabla " + re.escape(mensaje)):
        lector.leer_tabla_of(texto(lector, OF_ABIERTA).replace("%SourcePhantomDistance 1000", f"%SourcePhantomDistance {ssd}"))


@pytest.mark.parametrize("ssd", ["600", "950", "1400", "1000.0"])
def test_una_ssd_de_60_a_140_cm_se_acepta(lector, ssd):
    curvas = lector.leer_curvas(texto(lector, PERFILES).replace("%SSD 1000", f"%SSD {ssd}"))
    assert {c.ssd_cm for c in curvas} == {float(ssd) / 10}
    assert lector.leer_tabla_of(texto(lector, OF_ABIERTA).replace("%SourcePhantomDistance 1000", f"%SourcePhantomDistance {ssd}")).ssd_cm == float(ssd) / 10


@pytest.mark.parametrize("profundidad, mensaje", [("0", "es 0 [cm] y debe ser mayor que 0 [cm]"), ("-50", "es -5 [cm] y debe ser mayor que 0 [cm]"),
                                                  ("nan", "no se puede leer: «nan»"), ("inf", "no se puede leer: «inf»"), ("cinco", "no se puede leer: «cinco»")])
def test_una_profundidad_de_tabla_imposible_se_rechaza(lector, profundidad, mensaje):
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(mensaje)):
        lector.leer_tabla_of(texto(lector, OF_ABIERTA).replace("%DetectorDepth 50", f"%DetectorDepth {profundidad}"))


def test_cabecera_con_decimales_se_lee(lector):
    t = texto(lector, OF_ABIERTA).replace("%DetectorDepth 50", "%DetectorDepth 50.0").replace("%SourcePhantomDistance 1000", "%SourcePhantomDistance 1000.0")
    assert (lector.leer_tabla_of(t).prof_cm, lector.leer_tabla_of(t).ssd_cm) == (5.0, 100.0)
    assert lector.leer_tabla_of(texto(lector, OF_ABIERTA).replace("%DetectorDepth 50", "%DetectorDepth 5")).prof_cm == 0.5      # (UM.1, implementador) cualquier profundidad mayor que 0 sirve


@pytest.mark.parametrize("donde, viejo, nuevo, mensaje", [
    ("tabla", "%SourcePhantomDistance 1000\n", "%SourcePhantomDistance 1000\n%SourcePhantomDistance 900\n", "la cabecera de la tabla de factores dice dos veces «SourcePhantomDistance», con «1000» y con «900»"),
    ("curva", "%SSD 1000\n", "%SSD 1000\n%SSD 900\n", "una curva dice dos veces «SSD», con «1000» y con «900»"),
    ("name", "Wedge angle[deg]:15.0\n", "Wedge angle[deg]:15.0\nWedge angle[deg]:30.0\n", "el name.data dice dos veces «Wedge angle», con «15.0 [deg]» y con «30.0 [deg]»"),
])
def test_un_dato_dicho_dos_veces_con_valores_distintos_no_se_elige_en_silencio(lector, donde, viejo, nuevo, mensaje):
    nombre = {"tabla": OF_ABIERTA, "curva": PDD_ABIERTO, "name": NAME_DATA}[donde]
    leer = {"tabla": lector.leer_tabla_of, "curva": lector.leer_curvas, "name": lector.leer_parametros}[donde]
    t = texto(lector, nombre)
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(mensaje)):
        leer(t.replace(viejo, nuevo, 1))
    leer(t.replace(viejo, viejo + viejo, 1))      # dicho dos veces con el MISMO valor no contradice nada


@pytest.mark.parametrize("viejo, nuevo", [("2.5, 3, 4", "0, 3, 4"), ("\n2.5, ", "\n0, "), ("3, 4, 5", "4, 3, 5")])
def test_una_tabla_con_lados_imposibles_se_rechaza(lector, viejo, nuevo):
    t = texto(lector, OF_ABIERTA)
    assert viejo in t, viejo
    with pytest.raises(lector.ArchivoNoReconocido, match="los lados de la tabla de factores deben ser positivos y crecientes"):
        lector.leer_tabla_of(t.replace(viejo, nuevo, 1))


@pytest.mark.parametrize("malo", ["0.0", "1000", "-0.9", "9.0", "0.29", "2.01"])      # UM.1b: «nan» e «inf» ya no son numeros (tests/test_um1b_lector_estricto.py)
def test_una_celda_imposible_se_rechaza(lector, malo):
    t = texto(lector, OF_ABIERTA).replace("0.870", malo, 1)
    with pytest.raises(lector.ArchivoNoReconocido, match="tiene un valor imposible \\(fuera de 0.3 a 2\\)"):
        lector.leer_tabla_of(t)


@pytest.mark.parametrize("bueno", ["0.3", "2.0"])
def test_una_celda_en_el_limite_se_acepta(lector, bueno):
    assert celda(lector.leer_tabla_of(texto(lector, OF_ABIERTA).replace("0.870", bueno, 1)), 2.5, 2.5) == float(bueno)


def test_una_fila_incompleta_o_de_mas_dice_cual_y_cuantos_numeros(lector):
    """Hallazgo del pre-vuelo: la referencia decia el texto de numpy («setting an array element with a sequence ... inhomogeneous shape»)."""
    t = texto(lector, OF_ABIERTA)
    menos = re.sub(r"(?m)^(5, 0\.900, .*), 0\.969$", r"\1", t, count=1)
    with pytest.raises(lector.ArchivoNoReconocido, match="la fila «5, 0.900, 0.908.*» de la tabla de factores trae 12 números y debe traer 13: su lado Y y un valor por cada uno de los 12 lados X"):
        lector.leer_tabla_of(menos)
    with pytest.raises(lector.ArchivoNoReconocido, match="trae 14 números y debe traer 13"):
        lector.leer_tabla_of(t.replace("0.969\n", "0.969, 0.970\n", 1))
    with pytest.raises(lector.ArchivoNoReconocido, match="trae 13 números y debe traer 12"):
        lector.leer_tabla_of(t.replace("35, 40\n", "35\n", 1))


def test_una_tabla_sin_filas_o_con_una_linea_que_no_son_numeros_lo_dice(lector):
    t = texto(lector, OF_ABIERTA)
    with pytest.raises(lector.ArchivoNoReconocido, match="no trae su línea de lados X y por lo menos una fila de valores"):
        lector.leer_tabla_of(t[:t.index("2.5, 0.870")])
    with pytest.raises(lector.ArchivoNoReconocido, match="no trae su línea de lados X"):
        lector.leer_tabla_of(t[:t.index("2.5, 3, 4")])
    with pytest.raises(lector.ArchivoNoReconocido, match="tiene una línea que no son números separados por comas: «# comentario»"):
        lector.leer_tabla_of(t.replace("# Data\n", "# Data\n  # comentario\n"))
    with pytest.raises(lector.ArchivoNoReconocido, match="no son números separados por comas: «5; 0.900"):
        lector.leer_tabla_of(t.replace("5, 0.900, ", "5; 0.900, ", 1))
    # (UM.1, implementador) El minimo que dice el motivo, «su línea de lados X y por lo menos una fila de valores», es valido: una fila basta.
    una_fila = lector.leer_tabla_of("%TYPE OutputFactorTable\n%SourcePhantomDistance 1000\n%DetectorDepth 50\n# Data\n10\n10, 1.000\n")
    assert (una_fila.x.tolist(), una_fila.y.tolist(), una_fila.m.tolist()) == ([10.0], [10.0], [[1.0]])


def test_un_punto_negativo_o_no_numerico_en_una_curva_se_rechaza(lector):
    t = texto(lector, PDD_ABIERTO)
    for malo, mensaje in (("-045.300", "cuatro números válidos"), ("abc", "cuatro números válidos"), ("nan", "cuatro números válidos"), ("inf", "cuatro números válidos")):
        with pytest.raises(lector.ArchivoNoReconocido, match=mensaje):
            lector.leer_curvas(t.replace("+045.300", malo, 1))
    assert lector.leer_curvas(t.replace("+045.300", "+000.000", 1))[0].valor[0] == 0.0     # un cero es un valor: lo juzga el armado, no el lector


# ---------- El name.data ----------
@pytest.mark.parametrize("viejo, nuevo", [("[Gy]:0.662300", "[Gy]:0"), ("[Gy]:0.662300", "[Gy]:-0.6623"), ("[Gy]:0.662300", "[Gy]:nan"), ("[Gy]:0.662300", "[Gy]:inf"),
                                          ("[Gy]:0.662300", "[Gy]:abc"), ("[MU]:100.000000", "[MU]:0"), ("[MU]:100.000000", "[MU]:-100"), ("[MU]:100.000000", "[MU]:nan")])
def test_una_dosis_de_referencia_imposible_se_rechaza_y_cero_no_es_ausente(lector, viejo, nuevo):
    """Hallazgo del pre-vuelo: con 0 Gy la referencia devolvia 0.0 y el armado lo tomaba como «no dice nada»; con 0 MU el motivo era «float division by zero»."""
    valor = nuevo.split(":", 1)[1]      # (UM.1, implementador) el motivo muestra los DOS valores tal como vienen, con su unidad: el que se cambio y el que no
    dosis, ums = (valor, "100.000000") if "[Gy]" in nuevo else ("0.662300", valor)
    with pytest.raises(lector.ArchivoNoReconocido, match=rf"la dosis de referencia de la cuña es «{re.escape(dosis)}» \[Gy\] por «{re.escape(ums)}» \[MU\]: las dos deben ser números mayores que 0"):
        lector.dosis_de_referencia_cuna(texto(lector, NAME_DATA).replace(viejo, nuevo))


def test_la_dosis_sin_sus_mu_o_las_mu_sin_su_dosis_se_rechazan(lector):
    t = texto(lector, NAME_DATA)
    sin_mu = re.sub(r"(?m)^Reference MU for hard wedge.*\n", "", t)
    sin_dosis = re.sub(r"(?m)^Reference dose for hard wedge.*\n", "", t)
    with pytest.raises(lector.ArchivoNoReconocido, match="dice la dosis de referencia de la cuña y no sus MU: hacen falta las dos"):
        lector.dosis_de_referencia_cuna(sin_mu)
    with pytest.raises(lector.ArchivoNoReconocido, match="dice las MU de referencia de la cuña y no su dosis: hacen falta las dos"):
        lector.dosis_de_referencia_cuna(sin_dosis)
    assert lector.dosis_de_referencia_cuna(re.sub(r"(?m)^Reference dose for hard wedge.*\n", "", sin_mu)) is None      # sin ninguna de las dos: no la dice


@pytest.mark.parametrize("viejo, nuevo, mensaje", [("angle[deg]:15.0", "angle[rad]:15.0", "viene en [rad]: se esperaba [deg]"),
                                                   ("angle[deg]:15.0", "angle[arcmin]:15.0", "viene en [arcmin]: se esperaba [deg]"),       # (UM.1, corrector) una unidad menor que «deg» en el orden de las letras tambien se rechaza
                                                   ("angle[deg]:15.0", "angle[deg]:0", "«0» [deg]: debe ser un número mayor que 0"),
                                                   ("angle[deg]:15.0", "angle[deg]:-15", "«-15» [deg]: debe ser un número mayor que 0"),
                                                   ("angle[deg]:15.0", "angle[deg]:nan", "«nan» [deg]"), ("angle[deg]:15.0", "angle[deg]:quince", "no se puede leer: «quince»")])
def test_el_angulo_del_name_data_en_otra_unidad_o_imposible_se_rechaza(lector, viejo, nuevo, mensaje):
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(mensaje)):
        lector.angulo_en_parametros(texto(lector, NAME_DATA).replace(viejo, nuevo))


def test_un_name_data_sin_angulo_ni_orientacion_no_los_inventa(lector):
    t = re.sub(r"(?m)^Wedge (angle|orientation).*\n", "", texto(lector, NAME_DATA))
    assert lector.angulo_en_parametros(t) is None and lector.orientacion_de_cuna(t) is None


# ---------- Nombres de equipo y de energia (DC15) ----------
@pytest.mark.parametrize("nombre, clave", [("Clinac 600", "Clinac 600"), ("600C", "Clinac 600"), ("CLINAC 600C", "Clinac 600"), ("600CD", "Clinac 600"), ("Varian Clinac 600", "Clinac 600"),
                                           ("Seiscientos", "Clinac 600"), ("Clinac iX", "Clinac iX"), ("iX", "Clinac iX"), ("CLINAC IX", "Clinac iX"),
                                           ("Halcyon", None), ("", None), (None, None), ("Clinac 2600", None), ("Synergy 600", None), ("Unique 6000", None), ("Phoenix", None)])
def test_clave_de_equipo(lector, nombre, clave):
    assert lector.clave_equipo(nombre) == clave


@pytest.mark.parametrize("texto_e, clave", [("6X", "6 MV"), ("6 MV", "6 MV"), ("06X", "6 MV"), ("15X", "15 MV"), (6, None), ("06.00", None), ("6E", None), ("6 MeV", None), ("6XFFF", None), ("", None), (None, None)])
def test_clave_de_energia(lector, texto_e, clave):
    assert lector.clave_energia(texto_e) == clave


# ---------- Correccion de la revision de UM.1 (ronda 1, 06-11-2026): R1-H1 a R1-H5. Cada prueba cae contra el lector de antes de la correccion por lo que dice su nombre ----------
def con_lado(t, eje, valor):
    """La tabla de factores abierta con su ULTIMO lado X (la linea de lados) o Y (la primera columna de la ultima fila) cambiado por `valor`."""
    lineas = t.split("\n")
    if eje == "X":
        i = lineas.index("2.5, 3, 4, 5, 6, 10, 15, 20, 25, 30, 35, 40")
        lineas[i] = lineas[i].replace(", 40", f", {valor}")
    else:
        i = max(k for k, l in enumerate(lineas) if l.startswith("40, "))
        lineas[i] = lineas[i].replace("40, ", f"{valor}, ", 1)
    assert lineas != t.split("\n")
    return "\n".join(lineas)


def test_un_name_data_cortado_se_rechaza_o_es_un_prefijo_exacto(lector):
    """R1-H1. El name.data no trae marca de fin: un corte dentro de las MU daba 66.23 o 6.623 cGy/UM en vez de 0.6623, y dentro del angulo, 1.0 en vez de 15.0, sin error.
    Con TODOS los cortes posibles de sus bytes: uno dentro de una linea se rechaza; uno justo en un final de linea es un name.data con menos parametros (igual que la tabla, UM1-D7:
    el lector no puede saber cuantos faltan, y lo que falte lo pide la carga), y NINGUNO cambia un valor: lo que trae es exactamente lo que trae el archivo entero."""
    entero = crudo(NAME_DATA)
    completo = lector.leer_parametros(lector.decodificar(entero))
    nombres = list(completo)
    aceptados = 0
    for corte in range(1, len(entero) + 1):
        t = lector.decodificar(entero[:corte])
        try:
            leidos = lector.leer_parametros(t)
        except lector.ArchivoNoReconocido:
            continue
        aceptados += 1
        assert entero[:corte].endswith((b"\r", b"\n")), f"se acepto un corte dentro de una linea: ...{entero[:corte][-40:]!r}"
        assert leidos == {k: completo[k] for k in nombres[:len(leidos)]}, f"el corte {corte} cambia lo que dice el archivo: {leidos}"
    assert 0 < aceptados < len(entero)
    # los casos de la revision, con su motivo: dentro del valor de las MU, dentro del angulo y dentro de la ultima linea
    i_mu = entero.index(b"[MU]:100.000000") + len(b"[MU]:")
    for sobran in (1, 2, 5):
        with pytest.raises(lector.ArchivoNoReconocido, match="el name.data no termina en un final de línea: parece cortado"):
            lector.dosis_de_referencia_cuna(lector.decodificar(entero[:i_mu + sobran]))
    with pytest.raises(lector.ArchivoNoReconocido, match="el name.data no termina en un final de línea: parece cortado"):
        lector.angulo_en_parametros(lector.decodificar(entero[:entero.index(b"Wedge angle[deg]:15.0") + len(b"Wedge angle[deg]:1")]))
    with pytest.raises(lector.ArchivoNoReconocido, match="el name.data no termina en un final de línea: parece cortado"):
        lector.leer_parametros(lector.decodificar(entero.rstrip(b"\r\n")))
    # justo en un final de linea: sin las MU (y con la dosis) no se entiende; con las dos, lo que dice el archivo; sin ninguna de las dos, «no la dice» (UM1-D7)
    despues = lambda frase: entero.index(frase) + len(frase) + 2       # hasta el final de esa linea (CRLF)
    with pytest.raises(lector.ArchivoNoReconocido, match="dice la dosis de referencia de la cuña y no sus MU: hacen falta las dos"):
        lector.dosis_de_referencia_cuna(lector.decodificar(entero[:despues(b"calibration depth[Gy]:0.662300")]))
    assert lector.dosis_de_referencia_cuna(lector.decodificar(entero[:despues(b"calibration depth[MU]:100.000000")])) == pytest.approx(0.6623)
    tras_el_angulo = lector.decodificar(entero[:despues(b"Wedge angle[deg]:15.0")])
    assert lector.dosis_de_referencia_cuna(tras_el_angulo) is None and lector.angulo_en_parametros(tras_el_angulo) == 15.0


def test_un_name_data_sin_la_linea_data_parameters_se_rechaza(lector):
    """R1-H1. Sin la linea «Data parameters:» lo que se tomaba por un parametro era la cabecera («energy [MV]: 6»), y la dosis salia «no la dice»."""
    entero = crudo(NAME_DATA)
    sin_parametros = lector.decodificar(entero[:entero.index(b"Data parameters:")])
    assert sin_parametros.endswith("\n") and "energy [MV]: 6" in sin_parametros       # termina en un final de linea: lo que falta es la marca y todo lo que sigue
    for leer in (lector.leer_parametros, lector.dosis_de_referencia_cuna, lector.orientacion_de_cuna, lector.angulo_en_parametros):
        with pytest.raises(lector.ArchivoNoReconocido, match="el name.data no trae la línea «Data parameters:»: no es un name.data o está cortado"):
            leer(sin_parametros)


@pytest.mark.parametrize("eje", ["X", "Y"])
@pytest.mark.parametrize("valor", ["1000000000", "1000", "200", "100.5", "101"])      # UM.1b: «inf», «nan» y «1e9» ya no son numeros (tests/test_um1b_lector_estricto.py)
def test_una_tabla_con_un_lado_infinito_o_desmedido_se_rechaza(lector, eje, valor):
    """R1-H2. Un lado «inf» o «1e9» se aceptaba: la rejilla de la tabla ya no era la medida, el motor calculaba el factor de 40 x 40 con -0.45 % de error y daba un numero a 60 x 40,
    donde la tabla real dice «fuera de la tabla». Un campo infinito o desmedido no existe (el plan, UM.1)."""
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape("los lados de la tabla de factores deben ser positivos y crecientes, y no pasar de 100 [cm]")):
        lector.leer_tabla_of(con_lado(texto(lector, OF_ABIERTA), eje, valor))


def test_un_lado_de_hasta_100_cm_se_acepta_en_la_tabla_y_en_la_curva(lector):
    t = lector.leer_tabla_of(con_lado(con_lado(texto(lector, OF_ABIERTA), "X", "100"), "Y", "100.0"))
    assert (t.x[-1], t.y[-1]) == (100.0, 100.0) and t.x[-2] == 35.0 and celda(t, 10, 10) == 1.0
    assert lector.leer_curvas(texto(lector, PDD_ABIERTO).replace("%FLSZ 400*400", "%FLSZ 1000*1000"))[-1].campo_cm == (100.0, 100.0)


@pytest.mark.parametrize("campo, lado", [("%FLSZ 1001*1001", "100.1"), ("%FLSZ 100*5000", "500"), ("%FLSZ 5000*100", "500"), ("%FLSZ 100000*100000", "10000")])
def test_una_curva_con_un_campo_desmedido_se_rechaza(lector, campo, lado):
    """R1-H2, misma regla en las curvas: el campo de la cabecera viene en mm y no puede pasar de 100 cm (un lado en otra unidad o un dato roto)."""
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(f"El campo de una curva es {lado} [cm] y no puede pasar de 100 [cm]")):
        lector.leer_curvas(texto(lector, PDD_ABIERTO).replace("%FLSZ 400*400", campo))


@pytest.mark.parametrize("nombre, viejo, nuevo", [
    (PDD_ABIERTO, "# machine: 600C, 6X\n", "# machine:\n"), (PDD_ABIERTO, "# machine: 600C, 6X\n", "# machine: \n"),
    (PDD_ABIERTO, "# add on: Open Field - 00\n", "# add on:\n"), (PDD_ABIERTO, "# add on: Open Field - 00\n", "# add on: \n"),
    (PDD_ABIERTO, "# data: OPD\n", "# data:\n"), (PDD_ABIERTO, "# data: OPD\n", "# data: \n"),
    (NAME_DATA, "machine: 600C, 6X\n", "machine:\n"), (NAME_DATA, "add on: Standard Wedge - 15\n", "add on:\n"), (NAME_DATA, "data: WedgeParameters\n", "data:\n")])
def test_un_dato_vacio_de_la_cabecera_no_toma_la_linea_siguiente(lector, nombre, viejo, nuevo):
    """R1-H4. `\\s*` cruzaba el salto de linea: con «# machine:» vacio la maquina era «# generated from», y con «add on:» vacio en el name.data, «data: WedgeParameters»."""
    t = texto(lector, nombre)
    assert viejo in t
    with pytest.raises(lector.ArchivoNoReconocido, match="la cabecera no dice máquina, accesorio y tipo de dato: no parece una exportación de Eclipse"):
        lector.identidad(t.replace(viejo, nuevo))


@pytest.mark.parametrize("viejo, nuevo", [("%DetectorDepth 50\n", "%DetectorDepth\n"), ("%SourcePhantomDistance 1000\n", "%SourcePhantomDistance\n"), ("%TYPE OutputFactorTable\n", "%TYPE\n")])
def test_un_dato_vacio_de_la_cabecera_de_una_tabla_se_dice_como_falta(lector, viejo, nuevo):
    """R1-H4, la misma regex en la tabla: con «%DetectorDepth» vacio el motivo citaba la linea siguiente («# Data») como si fuera su valor."""
    t = texto(lector, OF_ABIERTA)
    assert t.count(viejo) == 1
    with pytest.raises(lector.ArchivoNoReconocido, match="no es una tabla de factores con SSD y profundidad en la cabecera"):
        lector.leer_tabla_of(t.replace(viejo, nuevo))


@pytest.mark.parametrize("cual", [0, 5, 11])
@pytest.mark.parametrize("clave, normal, otro", [("machine", "600C, 6X", "iX, 15X"), ("add on", "Open Field - 00", "Standard Wedge - 60"), ("data", "OPD", "WDD")])
def test_una_curva_que_dice_otra_maquina_energia_o_accesorio_no_se_elige_en_silencio(lector, clave, normal, otro, cual):
    """R1-H5. Cada curva de un archivo repite su cabecera (12 «# machine:» en el PDD): la identidad salia de la primera, y una curva que decia otra maquina, otra energia o otro accesorio
    pasaba (el PDD «de 600C, 6X» con una curva de «iX, 15X» se cargaba sin un aviso). Un dato dicho dos veces con valores distintos no se elige en silencio (UM1-D2)."""
    linea, intrusa = f"# {clave}: {normal}\n", f"# {clave}: {otro}\n"
    partes = texto(lector, PDD_ABIERTO).split(linea)
    assert len(partes) == 13
    mezclado = linea.join(partes[:cual + 1]) + intrusa + linea.join(partes[cual + 1:])
    primero, segundo = (otro, normal) if cual == 0 else (normal, otro)
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(f"la cabecera dice dos veces «{clave}», con «{primero}» y con «{segundo}»: no se sabe cuál vale")):
        lector.identidad(mezclado)
    assert len(lector.leer_curvas(mezclado)) == 12       # el lector de curvas no mira la identidad: es de quien la pide


def test_un_archivo_que_trae_mas_curvas_de_las_que_anuncia_se_rechaza(lector):
    """R1-H3 (M1). `$NUMS` dice cuantas curvas trae: ni menos (cortado) ni mas (unido o editado a mano) de las que dice. Solo se probaba «anuncia 2 y trae 1»."""
    t = texto(lector, PDD_ABIERTO)
    with pytest.raises(lector.ArchivoNoReconocido, match="anuncia 11 curvas y trae 12: no coinciden"):
        lector.leer_curvas(t.replace("$NUMS 012", "$NUMS 011", 1))
    with pytest.raises(lector.ArchivoNoReconocido, match="anuncia 13 curvas y trae 12: parece cortado"):
        lector.leer_curvas(t.replace("$NUMS 012", "$NUMS 013", 1))
    assert len(lector.leer_curvas(t)) == 12


@pytest.mark.parametrize("columna", [0, 1, 2, 3])
@pytest.mark.parametrize("malo", ["nan", "inf", "-inf"])
def test_un_punto_con_un_numero_no_finito_en_cualquiera_de_sus_cuatro_columnas_se_rechaza(lector, columna, malo):
    """R1-H3 (M2). Solo se probaba la columna del valor: un punto con x, y o z en nan o inf pasaba (aguas abajo, un perfil con x = nan perdia el punto sin avisar: nan > 0 es falso)."""
    punto = ["+000.0", "+000.0", "+000.0", "+045.300"]
    t = texto(lector, PDD_ABIERTO)
    assert t.count("<" + " ".join(punto) + ">") == 1
    punto[columna] = malo
    with pytest.raises(lector.ArchivoNoReconocido, match="hay un punto que no tiene cuatro números válidos"):
        lector.leer_curvas(t.replace("<+000.0 +000.0 +000.0 +045.300>", "<" + " ".join(punto) + ">", 1))


@pytest.mark.parametrize("vacia", ["%SSD\n", "%SSD \n"])
def test_una_curva_con_la_ssd_vacia_se_rechaza_y_no_se_toma_por_que_no_la_dice(lector, vacia):
    """R1-H3 (M3). «%SSD» sin valor no es una curva que no dice su SSD (esa queda en None): es una cabecera que no se puede leer."""
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape("La SSD de una curva no se puede leer: «»")):
        lector.leer_curvas(texto(lector, PDD_ABIERTO).replace("%SSD 1000\n", vacia, 1))


@pytest.mark.parametrize("valor", ["1.001", "0.999", "1.002", "0.998", "1.0001", "0.9999", "1.1"])
def test_la_celda_de_10_x_10_debe_valer_exactamente_1_000(lector, valor):
    """R1-H3 (M4). La tabla se normaliza a 1.000 en 10 x 10 (H2): ni 1.001 ni 1.0001 son 1.000. Solo se probaba 1.1."""
    fila = "10, 0.918, 0.930, 0.950, 0.964, 0.973, 1.000, "
    t = texto(lector, OF_ABIERTA)
    assert t.count(fila) == 1
    with pytest.raises(lector.ArchivoNoReconocido, match="la tabla de factores no vale 1.000 en 10 × 10"):
        lector.leer_tabla_of(t.replace(fila, fila.replace("1.000", valor)))


# ---------- Lo que dejo vivo el barrido de mutantes automaticos de la correccion (scripts/um1_mutantes_automaticos_2.py): cada prueba cierra uno de esos huecos ----------
def test_un_campo_de_curva_con_tres_lados_no_es_un_campo(lector):
    """Un `%FLSZ` de tres numeros no dice un campo X*Y: se rechazaba solo si traia menos de dos."""
    with pytest.raises(lector.ArchivoNoReconocido, match="hay una curva que no dice su campo"):
        lector.leer_curvas(texto(lector, PDD_ABIERTO).replace("%FLSZ 100*100", "%FLSZ 100*100*100"))


@pytest.mark.parametrize("unidad", ["Gy", "A", "cGy", "mu", "MUs"])
def test_unas_mu_en_otra_unidad_se_rechazan_sea_cual_sea_su_nombre(lector, unidad):
    """Las MU vienen en [MU]: ninguna otra unidad vale, ni la que se escribe antes ni la que se escribe despues de «MU» en el abecedario."""
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(f"viene en [Gy] por [{unidad}]: se esperaba [Gy] o [cGy] por [MU]")):
        lector.dosis_de_referencia_cuna(texto(lector, NAME_DATA).replace("[MU]:100.000000", f"[{unidad}]:100.000000"))


@pytest.mark.parametrize("malo", ["+000.0 +000.0 +000.0 +000.0 +045.300", "+000.0 +000.0 +045.300", "+000.0 +000.0 +000.0 -000.100", "+000.0 +000.0 +000.0 -000.001"])
def test_un_punto_con_mas_o_menos_de_cuatro_numeros_o_un_valor_negativo_por_poco_se_rechaza(lector, malo):
    """Un punto trae exactamente cuatro numeros (x, y, z y el valor), y el valor no es negativo ni por una milesima (solo se probaba -045.300)."""
    t = texto(lector, PDD_ABIERTO)
    assert t.count("<+000.0 +000.0 +000.0 +045.300>") == 1
    with pytest.raises(lector.ArchivoNoReconocido, match="hay un punto que no tiene cuatro números válidos"):
        lector.leer_curvas(t.replace("<+000.0 +000.0 +000.0 +045.300>", f"<{malo}>", 1))


@pytest.mark.parametrize("viejo, nuevo", [("2.5, 3, 4", "-2.5, 3, 4"), ("\n2.5, 0.870", "\n-2.5, 0.870"), ("2.5, 3, 4", "-1, 3, 4"), ("\n2.5, 0.870", "\n-1, 0.870")])
def test_un_lado_negativo_de_la_tabla_se_rechaza(lector, viejo, nuevo):
    """Solo se probaba un lado en 0 o fuera de orden: un primer lado negativo (con los demas crecientes) tampoco es positivo."""
    t = texto(lector, OF_ABIERTA)
    assert t.count(viejo) == 1
    with pytest.raises(lector.ArchivoNoReconocido, match="los lados de la tabla de factores deben ser positivos y crecientes"):
        lector.leer_tabla_of(t.replace(viejo, nuevo))


@pytest.mark.parametrize("raro", [(1, 0), (1, 2), (0, 1), (2, 1)])
def test_las_celdas_del_borde_de_la_tabla_no_se_juzgan_solo_las_interiores(lector, raro):
    """H5 mira las celdas INTERIORES (con vecinos a los dos lados): una celda rara en el borde no se marca, porque no hay con que compararla. La unica interior, la del centro, queda a
    mitad de camino entre una vecina rara y una normal en su fila (o su columna) y sin desviacion en la otra: tampoco se marca."""
    m = np.ones((3, 3))
    m[raro] = 1.05
    lados = np.array([5.0, 10.0, 20.0])
    assert lector.valores_fuera_de_tendencia(lector.TablaOF(lados, lados, m, 100.0, 5.0)) == []


@pytest.mark.parametrize("vecinos, marcada", [(1.00603, True), (1.00597, False), (0.99397, True), (0.99403, False)])
def test_el_umbral_de_valores_fuera_de_tendencia_es_0_6_por_ciento(lector, vecinos, marcada):
    """El plan dice 0.6 %: una celda que se aparta 0.603 % de sus vecinos en la fila y en la columna se marca, y una que se aparta 0.597 % no (los datos reales dejan la ventana de 0.42 a 0.64 %)."""
    lados = np.array([5.0, 10.0, 20.0])
    tabla = lector.TablaOF(lados, lados, np.array([[1.0, vecinos, 1.0], [vecinos, 1.0, vecinos], [1.0, vecinos, 1.0]]), 100.0, 5.0)
    assert bool(lector.valores_fuera_de_tendencia(tabla)) is marcada


def test_una_celda_que_se_aparta_justo_el_umbral_se_marca(lector):
    """El umbral es inclusivo («0.6 % o mas»): con centro 0 y vecinos 0.006 la desviacion es exactamente UMBRAL_FUERA_DE_TENDENCIA."""
    lados = np.array([5.0, 10.0, 20.0])
    tabla = lector.TablaOF(lados, lados, np.array([[0.0, 0.006, 0.0], [0.006, 0.0, 0.006], [0.0, 0.006, 0.0]]), 100.0, 5.0)
    assert lector.UMBRAL_FUERA_DE_TENDENCIA == 0.006
    assert [(y, x) for y, x, *_ in lector.valores_fuera_de_tendencia(tabla)] == [(10.0, 10.0)]


def test_los_espacios_de_mas_en_una_linea_no_cambian_lo_que_se_lee(lector):
    """Los espacios y tabuladores que un editor deja al final de una linea (o antes de un punto, o en un parametro del name.data) no son parte de lo que dice el archivo: ni cambian la
    identidad, ni las curvas, ni la tabla, ni hacen que dos curvas que dicen lo mismo parezcan decir cosas distintas. (UM.1b, ronda 1, clase b: SOLO los de una linea que no lleva un numero
    hasta el final -- comentarios, marcadores, puntos tras su «>», lineas en blanco --; un blanco al final de «%CLAVE valor», de una fila de la tabla o de un parametro del name.data puede ser la
    ultima cifra danada y se rechaza: ver tests/test_um1b_lector_estricto.py, R2.)"""
    t = texto(lector, PDD_ABIERTO)
    sucio = "\n".join(((" \t" + l if l.startswith("<") else l) + ("" if l.startswith("%") else "  \t")) if l else l for l in t.split("\n"))
    assert sucio != t and lector.identidad(sucio) == lector.identidad(t)
    for a, b in zip(lector.leer_curvas(sucio), lector.leer_curvas(t)):
        assert a.campo_cm == b.campo_cm and a.ssd_cm == b.ssd_cm and np.array_equal(a.x_cm, b.x_cm) and np.array_equal(a.z_cm, b.z_cm) and np.array_equal(a.valor, b.valor)
    assert lector.identidad("# machine: 600C , 6X  \n# add on: Open Field - 00 \n# data: OPD\t\n") == lector.Identidad("600C", "6X", "Open Field - 00", "OPD")
    assert lector.leer_curvas(t.replace("%SSD 1000\n", "%SSD 1000\n%SSD  1000\n", 1))[0].ssd_cm == 100.0       # dicho dos veces con el MISMO valor y un espacio de mas: no contradice nada
    una_tabla = texto(lector, OF_ABIERTA)
    con_linea_en_blanco = una_tabla.replace("# Data\n", "# Data  \t\n  \t\n", 1)
    assert con_linea_en_blanco != una_tabla and lector.leer_tabla_of(con_linea_en_blanco).m.tolist() == lector.leer_tabla_of(una_tabla).m.tolist()
    parametros = lector.leer_parametros(texto(lector, NAME_DATA).replace("Wedge angle[deg]:15.0", "  Wedge angle [ deg ]:  15.0"))
    assert parametros["Wedge angle"] == ("15.0", "deg")
