"""Lector de las exportaciones de Beam Configuration de Eclipse: curvas W2CAD, tablas de factores y parámetros de cuña.

Solo convierte texto en datos y dice lo que encuentra raro: no calcula UM, no abre la base y no usa Qt. Lo que no entiende
lo rechaza con `ArchivoNoReconocido`, con un motivo que el físico pueda leer.
"""
import math
import re
from dataclasses import dataclass

import numpy as np

UMBRAL_FUERA_DE_TENDENCIA = 0.006   # 0.6 %: la curvatura normal de las tablas aparta un valor de sus vecinos hasta 0.47 %
FACTOR_MINIMO, FACTOR_MAXIMO = 0.3, 2.0   # lo que puede valer un factor de campo; fuera de aquí el archivo está dañado
SSD_DE_LOS_DATOS_CM = (60.0, 140.0)   # UM.1 (pre-vuelo, UM1-D2): la SSD que puede decir una curva o una tabla; la misma franja que el motor admite en un plan (DC7)
LADO_MAXIMO_CM = 100.0                # UM.1 (revisión, R1-H2): lo más que puede medir el lado de un campo (ningún acelerador pasa de 40 cm); más allá el archivo está dañado o no dice mm
UNIDAD_DEL_ANGULO = "deg"             # UM.1 (UM1-D4): la única unidad del ángulo de cuña que se ha visto en un name.data de Eclipse
_MARCA_DE_PARAMETROS = "Data parameters:"   # la línea del name.data que separa su cabecera de sus parámetros


class ArchivoNoReconocido(ValueError):
    """El archivo no es una exportación que este lector entienda."""


@dataclass(frozen=True)
class Identidad:
    """Lo que el archivo dice de sí mismo."""
    maquina: str
    haz: str        # p. ej. «6X»
    accesorio: str  # p. ej. «Open Field - 00» o «Standard Wedge - 15»
    dato: str       # p. ej. «OPD» o «OutputFactorTable»

    @property
    def angulo_cuna(self):
        coincide = re.fullmatch(r"Standard Wedge - (\d+)", self.accesorio)
        return int(coincide.group(1)) if coincide else None


@dataclass(frozen=True)
class Curva:
    """Una curva W2CAD: campo y SSD en cm según su cabecera (SSD None si no la dice), posiciones en cm y valores."""
    campo_cm: tuple
    ssd_cm: object
    x_cm: np.ndarray
    z_cm: np.ndarray
    valor: np.ndarray


@dataclass(frozen=True)
class TablaOF:
    """Tabla de factores: filas Y, columnas X, en cm; medida a `ssd_cm` y `prof_cm`."""
    x: np.ndarray
    y: np.ndarray
    m: np.ndarray
    ssd_cm: float
    prof_cm: float


def decodificar(contenido):
    """El texto del archivo, sin marca de orden de bytes y con finales de línea unificados."""
    if isinstance(contenido, bytes):
        try:
            contenido = contenido.decode("utf-8-sig")
        except UnicodeDecodeError:
            contenido = contenido.decode("latin-1")
    return contenido.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")


def clave_equipo(nombre):
    """«Clinac 600» o «Clinac iX» para las formas conocidas de escribirlos; None para cualquier otro equipo."""
    texto = re.sub(r"[^a-z0-9]", "", str(nombre or "").lower())
    if re.fullmatch(r"(varian)?(clinac)?(600(c|cd)?|seiscientos)", texto):
        return "Clinac 600"
    return "Clinac iX" if re.fullmatch(r"(varian)?(clinac)?ix", texto) else None


def clave_energia(texto):
    """«6 MV» para «6X» o «6 MV»; None para un número sin unidad, electrones, FFF o lo que no se entienda."""
    coincide = re.fullmatch(r"0*(\d+(?:\.\d+)?)(X|MV)", str(texto or "").replace(" ", "").upper())
    return f"{float(coincide.group(1)):g} MV" if coincide else None


def _comentarios(texto, clave):
    """Lo que dice cada línea «# clave: valor» (en el name.data, «clave: valor»), en su orden: una por curva en un archivo de curvas. Solo espacios y tabuladores separan la clave de
    su valor: con `\\s` el salto de línea también valía, y un valor vacío se llevaba la línea siguiente."""
    return [valor.strip() for valor in re.findall(rf"^#?[ \t]*{re.escape(clave)}:[ \t]*(.*)$", texto, re.M)]


def identidad(texto):
    """Quién es el archivo, según su propia cabecera. Cada curva de un archivo de curvas repite la suya (12 «# machine:» en un PDD): si dos dicen cosas distintas el archivo no se
    entiende, en vez de elegir la primera en silencio."""
    pares = [(clave, valor) for clave in ("machine", "add on", "data") for valor in _comentarios(texto, clave)]
    dicho = _sin_repetir(pares, "la cabecera")
    maquina, accesorio, dato = (dicho.get(c) for c in ("machine", "add on", "data"))
    if not (maquina and accesorio and dato):
        raise ArchivoNoReconocido("la cabecera no dice máquina, accesorio y tipo de dato: no parece una exportación de Eclipse")
    nombre, _, haz = maquina.partition(",")
    return Identidad(nombre.strip(), haz.strip(), accesorio, dato)


def _en_cm(valor, que):
    """Una longitud de la cabecera, que viene en mm: un número finito, o el archivo no se entiende."""
    try:
        if not math.isfinite(float(valor)):
            raise ValueError("no es un número finito")
        return float(valor) / 10
    except ValueError as fallo:
        raise ArchivoNoReconocido(f"{que} no se puede leer: «{valor}»") from fallo


def _ssd(valor, que):
    """La SSD de una curva o de una tabla, en cm. Fuera de `SSD_DE_LOS_DATOS_CM` no es una medida de un acelerador: el archivo está dañado o no
    dice la SSD en mm (con 0 o con la SSD en cm, el OAR de un perfil se proyectaba mal y daba un número equivocado en silencio)."""
    ssd = _en_cm(valor, que)
    if not SSD_DE_LOS_DATOS_CM[0] <= ssd <= SSD_DE_LOS_DATOS_CM[1]:
        raise ArchivoNoReconocido(f"{que} es {ssd:g} [cm] y debe estar entre {SSD_DE_LOS_DATOS_CM[0]:g} y {SSD_DE_LOS_DATOS_CM[1]:g} [cm] "
                                  f"(la cabecera la da en [mm]: «{valor}»)")
    return ssd


def _lado(valor, que):
    """Un lado de campo de la cabecera, en cm: finito y no mayor que `LADO_MAXIMO_CM` (más allá no es un campo: el archivo está dañado o no lo dice en [mm])."""
    lado = _en_cm(valor, que)
    if lado > LADO_MAXIMO_CM:
        raise ArchivoNoReconocido(f"{que} es {lado:g} [cm] y no puede pasar de {LADO_MAXIMO_CM:g} [cm] (la cabecera lo da en [mm]: «{valor}»)")
    return lado


def _exigir_final_de_linea(texto, que, cortado):
    """La tabla de factores y el `name.data` no traen marca de fin: sin un final de línea el último número puede estar cortado y valer otra cosa (66.23 por 0.6623)."""
    if not texto.endswith("\n"):
        raise ArchivoNoReconocido(f"{que} no termina en un final de línea: parece {cortado}")


def _sin_repetir(pares, donde):
    """{clave: valor} de una cabecera; una clave dicha dos veces con valores distintos no se entiende (no se elige una en silencio)."""
    mostrar = lambda v: f"{v[0]} [{v[1]}]" if isinstance(v, tuple) else v      # noqa: E731 - un parámetro de name.data es (valor, unidad)
    cabecera = {}
    for clave, valor in pares:
        if clave in cabecera and cabecera[clave] != valor:
            raise ArchivoNoReconocido(f"{donde} dice dos veces «{clave}», con «{mostrar(cabecera[clave])}» y con «{mostrar(valor)}»: no se sabe cuál vale")
        cabecera[clave] = valor
    return cabecera


def _punto(linea):
    try:
        if not linea.endswith(">"):
            raise ValueError("sin cerrar")
        valores = [float(v) for v in linea[1:-1].split()]
    except ValueError as fallo:
        raise ArchivoNoReconocido(f"hay un punto que no se puede leer: «{linea[:40]}»") from fallo
    if len(valores) != 4 or not all(math.isfinite(v) for v in valores) or valores[3] < 0:
        raise ArchivoNoReconocido(f"hay un punto que no tiene cuatro números válidos: «{linea[:40]}»")
    return valores


def _curva(bloque):
    pares, puntos = [], []
    lineas = [l.strip() for l in bloque.split("\n")]
    for k, linea in enumerate(lineas):
        if linea.startswith("$ENOM"):
            break
        if linea.startswith("<"):
            puntos.append(_punto(linea))
        elif linea.startswith("%"):
            clave, _, valor = linea[1:].partition(" ")
            pares.append((clave, valor.strip()))
        elif linea and not linea.startswith(("#", "$ENOF")):
            raise ArchivoNoReconocido(f"hay una línea que no se entiende: «{linea[:40]}»")
    else:
        raise ArchivoNoReconocido("una curva no termina: parece cortado")
    sobra = [l for l in lineas[k + 1:] if l and l != "$ENOF" and not l.startswith("#")]     # tras $ENOM, comentarios (los trae el paquete de Varian) y el final del archivo: lo demás no se salta
    if sobra:
        raise ArchivoNoReconocido(f"hay una línea después del final de una curva ($ENOM) que no se entiende: «{sobra[0][:40]}»")
    cabecera = _sin_repetir(pares, "una curva")
    lados = cabecera.get("FLSZ", "").split("*")
    if len(lados) != 2:
        raise ArchivoNoReconocido("hay una curva que no dice su campo")
    if not puntos:
        raise ArchivoNoReconocido("hay una curva sin puntos")
    campo = tuple(_lado(v, "El campo de una curva") for v in lados)
    if not min(campo) > 0:
        raise ArchivoNoReconocido(f"hay una curva con un campo imposible: {cabecera['FLSZ']}")
    datos = np.array(puntos)
    return Curva(campo, _ssd(cabecera["SSD"], "La SSD de una curva") if "SSD" in cabecera else None, datos[:, 0] / 10, datos[:, 2] / 10, datos[:, 3])


def leer_curvas(texto):
    """Las curvas de un archivo W2CAD. Comprueba que estén todas las que anuncia `$NUMS`, que cada una termine y que sus números sean válidos."""
    bloques = texto.split("$STOM")[1:]
    if not bloques:
        raise ArchivoNoReconocido("no tiene curvas W2CAD")
    anunciadas = re.search(r"\$NUMS\s+(\d+)", texto)
    if anunciadas and int(anunciadas.group(1)) != len(bloques):
        raise ArchivoNoReconocido(f"anuncia {int(anunciadas.group(1))} curvas y trae {len(bloques)}: " + ("parece cortado" if len(bloques) < int(anunciadas.group(1)) else "no coinciden"))
    if "$ENOF" not in bloques[-1]:
        raise ArchivoNoReconocido("el archivo no termina: parece cortado")
    return [_curva(b) for b in bloques]


def leer_tabla_of(texto):
    """La tabla de factores. Exige SSD y profundidad en la cabecera, valores posibles y 1.000 en 10 × 10."""
    pares = re.findall(r"^%(\w+)[ \t]+(.*)$", texto, re.M)     # solo espacios: con `\s` un valor vacío se llevaba la línea siguiente (R1-H4)
    cabecera = dict(pares)
    if cabecera.get("TYPE") != "OutputFactorTable" or "SourcePhantomDistance" not in cabecera or "DetectorDepth" not in cabecera:
        raise ArchivoNoReconocido("no es una tabla de factores con SSD y profundidad en la cabecera")
    cabecera = _sin_repetir(pares, "la cabecera de la tabla de factores")
    _exigir_final_de_linea(texto, "la tabla de factores", "cortada")      # la tabla no trae marca de fin: sin esto, un corte dentro de su último número pasaría por un valor
    filas = [l.strip() for l in texto.split("\n") if l.strip() and not l.startswith(("#", "%"))]
    if len(filas) < 2:
        raise ArchivoNoReconocido("la tabla de factores no trae su línea de lados X y por lo menos una fila de valores")
    numeros = []
    for linea in filas:
        try:
            numeros.append([float(v) for v in linea.split(",")])
        except ValueError as fallo:
            raise ArchivoNoReconocido(f"la tabla de factores tiene una línea que no son números separados por comas: «{linea[:40]}»") from fallo
    x = np.array(numeros[0])
    for linea, fila in zip(filas[1:], numeros[1:]):
        if len(fila) != len(x) + 1:
            raise ArchivoNoReconocido(f"la fila «{linea[:40]}» de la tabla de factores trae {len(fila)} números y debe traer {len(x) + 1}: "
                                      f"su lado Y y un valor por cada uno de los {len(x)} lados X de la cabecera")
    cuerpo = np.array(numeros[1:])
    profundidad = _en_cm(cabecera["DetectorDepth"], "La profundidad de la tabla")
    if not profundidad > 0:
        raise ArchivoNoReconocido(f"la profundidad de la tabla de factores es {profundidad:g} [cm] y debe ser mayor que 0 [cm] (la cabecera la da en [mm])")
    tabla = TablaOF(x, cuerpo[:, 0], cuerpo[:, 1:], _ssd(cabecera["SourcePhantomDistance"], "La SSD de la tabla"), profundidad)
    if not (np.all(np.diff(tabla.x) > 0) and np.all(np.diff(tabla.y) > 0) and tabla.x[0] > 0 and tabla.y[0] > 0 and tabla.x[-1] <= LADO_MAXIMO_CM and tabla.y[-1] <= LADO_MAXIMO_CM):
        raise ArchivoNoReconocido(f"los lados de la tabla de factores deben ser positivos y crecientes, y no pasar de {LADO_MAXIMO_CM:g} [cm]")
    if not np.all(np.isfinite(tabla.m)) or np.any(tabla.m < FACTOR_MINIMO) or np.any(tabla.m > FACTOR_MAXIMO):
        raise ArchivoNoReconocido(f"la tabla de factores tiene un valor imposible (fuera de {FACTOR_MINIMO:g} a {FACTOR_MAXIMO:g})")
    i, j = np.flatnonzero(tabla.y == 10), np.flatnonzero(tabla.x == 10)
    if len(i) != 1 or len(j) != 1 or tabla.m[i[0], j[0]] != 1.0:
        raise ArchivoNoReconocido("la tabla de factores no vale 1.000 en 10 × 10")
    return tabla


def leer_parametros(texto):
    """Los parámetros de un `name.data`: {nombre: (valor, unidad)}, con el valor en texto, tal como viene. Como la tabla de factores, no trae marca de fin: exige el final de línea
    (un corte dentro de las MU daba 66.23 cGy/UM en vez de 0.6623) y la línea «Data parameters:» (sin ella lo que se tomaba por parámetros era la cabecera)."""
    _exigir_final_de_linea(texto, "el name.data", "cortado")
    if _MARCA_DE_PARAMETROS not in texto:
        raise ArchivoNoReconocido(f"el name.data no trae la línea «{_MARCA_DE_PARAMETROS}»: no es un name.data o está cortado")
    pares = []
    for linea in texto.split(_MARCA_DE_PARAMETROS, 1)[1].split("\n"):
        coincide = re.match(r"^(.*?)\[(.*?)\]:(.*)$", linea)
        if coincide:
            pares.append((coincide.group(1).strip(), (coincide.group(3).strip(), coincide.group(2).strip())))
    parametros = _sin_repetir(pares, "el name.data")
    if not parametros:
        raise ArchivoNoReconocido("no tiene parámetros")
    return parametros


def _positivo(texto_valor):
    """El número de un parámetro si es finito y mayor que 0; None si no lo es (0 no es «ausente»: es un valor imposible)."""
    try:
        valor = float(texto_valor)
    except ValueError:
        return None
    return valor if math.isfinite(valor) and valor > 0 else None


def dosis_de_referencia_cuna(texto):
    """cGy por UM de una cuña según su `name.data`, o None si el archivo no dice ninguna de las dos. Rechaza una unidad que no conoce, una de las dos
    sin la otra y un valor que no sea un número mayor que 0."""
    parametros = leer_parametros(texto)
    dosis, ums = parametros.get("Reference dose for hard wedge at calibration depth"), parametros.get("Reference MU for hard wedge at calibration depth")
    if dosis is None and ums is None:
        return None
    if dosis is None or ums is None:
        raise ArchivoNoReconocido("el name.data dice " + ("la dosis de referencia de la cuña y no sus MU" if ums is None else "las MU de referencia de la cuña y no su dosis")
                                  + ": hacen falta las dos")
    por_unidad = {"Gy": 100.0, "cGy": 1.0}
    if dosis[1] not in por_unidad or ums[1] != "MU":
        raise ArchivoNoReconocido(f"la dosis de referencia viene en [{dosis[1]}] por [{ums[1]}]: se esperaba Gy o cGy por MU")
    valor, unidades = _positivo(dosis[0]), _positivo(ums[0])
    if valor is None or unidades is None:
        raise ArchivoNoReconocido(f"la dosis de referencia de la cuña es «{dosis[0]}» [{dosis[1]}] por «{ums[0]}» [MU]: las dos deben ser números mayores que 0")
    return por_unidad[dosis[1]] * valor / unidades


def _parametro(texto, inicio):
    """(valor, unidad) del primer parámetro cuyo nombre empieza por `inicio`, o (None, None)."""
    for nombre, par in leer_parametros(texto).items():
        if nombre.startswith(inicio):
            return par
    return None, None


def orientacion_de_cuna(texto):
    """La orientación de la cuña en su tabla de factores, tal como la dice su `name.data`, o None si no la dice."""
    valor, _ = _parametro(texto, "Wedge orientation")
    return valor.upper() if valor else None


def angulo_en_parametros(texto):
    """El ángulo que dice el `name.data`, en grados, o None si no lo dice. Rechaza otra unidad y lo que no sea un número mayor que 0."""
    valor, unidad = _parametro(texto, "Wedge angle")
    if not valor:
        return None
    if unidad != UNIDAD_DEL_ANGULO:
        raise ArchivoNoReconocido(f"el ángulo de la cuña viene en [{unidad}]: se esperaba [{UNIDAD_DEL_ANGULO}]")
    angulo = _positivo(valor)
    if angulo is None:
        raise ArchivoNoReconocido(f"el ángulo de la cuña no se puede leer: «{valor}» [{unidad}]: debe ser un número mayor que 0")
    return angulo


def valores_fuera_de_tendencia(tabla):
    """Celdas interiores apartadas de lo que dicen sus vecinos en la fila y en la columna, en el mismo sentido: (y, x, valor, por_fila, por_columna)."""
    x, y, m = tabla.x, tabla.y, tabla.m

    def entre(a, va, b, vb, c):
        return va + (vb - va) * (math.log(c) - math.log(a)) / (math.log(b) - math.log(a))

    hallados = []
    for i in range(1, len(y) - 1):
        for j in range(1, len(x) - 1):
            v = m[i, j]
            por_fila = entre(x[j - 1], m[i, j - 1], x[j + 1], m[i, j + 1], x[j])
            por_columna = entre(y[i - 1], m[i - 1, j], y[i + 1], m[i + 1, j], y[i])
            if (v - por_fila) * (v - por_columna) > 0 and min(abs(v - por_fila), abs(v - por_columna)) >= UMBRAL_FUERA_DE_TENDENCIA:
                hallados.append((float(y[i]), float(x[j]), float(v), float(por_fila), float(por_columna)))
    return hallados
