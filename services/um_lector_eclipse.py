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
_NUMERO = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?")   # UM.1b: lo único que Eclipse escribe como número (medido en los 522 archivos reales): sin exponente, sin «_», sin espacios y terminado en cifra
_CLAVE = re.compile(r"%([A-Za-z]+)(?:[ \t]+(.*))?")   # UM.1b: «%CLAVE valor» de una cabecera; la clave es de letras y la separan del valor espacios o tabuladores
_BLANCOS = " \t"                                    # UM.1b: lo único que se recorta (str.strip() quitaba también un espacio Unicode que había reemplazado una cifra); y solo la sangría y el final de lo que no lleva números (`_linea`)


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
        coincide = re.fullmatch(r"Standard Wedge - ([0-9]+)", self.accesorio)
        return int(coincide.group(1)) if coincide else None


@dataclass(frozen=True)
class Curva:
    """Una curva W2CAD por el eje (y = 0 en todos sus puntos): campo y SSD en cm según su cabecera (SSD None si no la dice), posiciones en cm y valores."""
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
    """El texto del archivo, sin marca de orden de bytes y con finales de línea unificados. UM.1b (REAL-3): un archivo vuelto a guardar como «Unicode» (UTF-16) trae
    bytes nulos; se rechazaba más adelante con motivos falsos («parece cortado», «no tiene curvas W2CAD»)."""
    if isinstance(contenido, bytes):
        if b"\x00" in contenido:
            raise ArchivoNoReconocido("el archivo trae bytes nulos: parece guardado como «Unicode» (UTF-16) y no como lo exporta Eclipse (UTF-8); "
                                      "vuelva a exportarlo o guárdelo como UTF-8")
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
    coincide = re.fullmatch(r"0*([0-9]+(?:\.[0-9]+)?)(X|MV)", str(texto or "").replace(" ", "").upper())
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


def _numero(texto):
    """El número que dice el archivo, o None si el texto no es exactamente un número como los que escribe Eclipse (`_NUMERO`) o no es finito. UM.1b (S1): TODO
    número del archivo pasa por aquí; `float()` aceptaba «1.1_7» (1.17 por 1.107), «0.8e0» y «+073.e91», y un número dañado entraba como otro número."""
    if not _NUMERO.fullmatch(texto):
        return None
    valor = float(texto)
    return valor if math.isfinite(valor) else None


def _linea(texto):
    """Una línea del archivo sin su sangría y, salvo que sea «%CLAVE valor», sin los blancos del final. UM.1b, ronda 1 (R2): el valor de una clave llega hasta el final de la línea y un
    blanco ahí puede ser su última cifra dañada («%DetectorDepth 50» → «5 », «%FLSZ 100*100» → «100*10 »): no se recorta y `_numero` lo rechaza. Los puntos, los marcadores y los
    comentarios no llevan nada tras su cierre (`>`, `$ENOM`...), así que sus blancos finales no esconden nada. Ninguna línea de los 522 archivos reales empieza ni termina en blanco."""
    texto = texto.lstrip(_BLANCOS)
    return texto if texto.startswith("%") else texto.rstrip(_BLANCOS)


def _clave(linea):
    """(clave, valor) de una línea «%CLAVE valor» de una cabecera, o None si no lo es. UM.1b (S2, REAL-2): lo que empieza por «%» y no es eso («%20, 0.928»,
    «%SSD1000», «% SSD 1000») se saltaba o se tomaba por una clave que no existe; ahora quien llama rechaza el archivo."""
    coincide = _CLAVE.fullmatch(linea)
    return (coincide.group(1), coincide.group(2) or "") if coincide else None      # quien llama no recorta el final (R2): el valor llega con sus blancos; `[ \t]+` se lleva todo el separador


def _en_cm(valor, que):
    """Una longitud de la cabecera, que viene en mm: un número (`_numero`), o el archivo no se entiende."""
    mm = _numero(valor)
    if mm is None:
        raise ArchivoNoReconocido(f"{que} no se puede leer: «{valor}» (la cabecera la da en [mm])")
    return mm / 10


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
    if not linea.endswith(">"):
        raise ArchivoNoReconocido(f"hay un punto que no se puede leer: «{linea[:40]}»")
    valores = [_numero(v) for v in re.split(r"[ \t]+", linea[1:-1])]      # R4: `.split()` separaba también con un blanco de Unicode; R2: un blanco al final deja un número vacío y se rechaza
    if len(valores) != 4 or None in valores or valores[3] < 0:
        raise ArchivoNoReconocido(f"hay un punto que no tiene cuatro números válidos: «{linea[:40]}»")
    return valores


def _curva(bloque, final):
    """Una curva: sus líneas hasta `$ENOM` son puntos, claves, comentarios o vacías; después, comentarios (los trae el paquete de Varian) y, en la última curva
    (`final`), el `$ENOF` del archivo (UM.1b, P-12: un `$ENOF` suelto entre dos curvas se aceptaba)."""
    pares, puntos = [], []
    lineas = [_linea(l) for l in bloque.split("\n")]
    for k, linea in enumerate(lineas):
        if linea in ("$ENOM", "$ENOF"):
            break
        if linea.startswith("<"):
            puntos.append(_punto(linea))
        elif linea.startswith("%") and (par := _clave(linea)):
            pares.append(par)
        elif linea.startswith("#") and (pares or puntos):      # UM.1b, ronda 1 (R1): en los 5890 bloques reales todo comentario va antes de la primera clave; uno entre los datos esconde un punto o una clave
            raise ArchivoNoReconocido(f"hay un comentario («#») entre las claves o los puntos de una curva: «{linea[:40]}» "
                                      "(en los archivos de Eclipse los comentarios van antes de la primera clave; un punto o una clave comentados se perderían sin aviso)")
        elif linea and not linea.startswith("#"):
            raise ArchivoNoReconocido(f"hay una línea que no se entiende: «{linea[:40]}»")
    if lineas[k] != "$ENOM":      # se acabó el bloque, o llegó el $ENOF del archivo, sin el $ENOM de la curva
        raise ArchivoNoReconocido("una curva no termina: parece cortado")
    sobra = [l for l in lineas[k + 1:] if l and not (final and l == "$ENOF") and not l.startswith("#")]
    if sobra:
        raise ArchivoNoReconocido(f"hay una línea después del final de una curva ($ENOM) que no se entiende: «{sobra[0][:40]}»")
    cabecera = _sin_repetir(pares, "una curva")
    lados = cabecera.get("FLSZ", "").split("*")      # R2: sin recortar los blancos junto al «*» («100*10 » era 10 × 1 cm y «10 *100» 1 × 10); los 5886 «%FLSZ» reales son «NNN*NNN»
    if len(lados) != 2:
        raise ArchivoNoReconocido("hay una curva que no dice su campo")
    if not puntos:
        raise ArchivoNoReconocido("hay una curva sin puntos")
    campo = tuple(_lado(v, "El campo de una curva") for v in lados)
    if not min(campo) > 0:
        raise ArchivoNoReconocido(f"hay una curva con un campo imposible: {campo[0]:g} × {campo[1]:g} [cm] (la cabecera lo da en [mm]: «{cabecera['FLSZ']}»)")
    datos = np.array(puntos)
    if np.any(datos[:, 1] != 0):      # UM.1b (REAL-1, O5): `Curva` no guarda y; un perfil en diagonal, a lo largo de y o fuera del eje se leería como uno cruzado por el eje
        raise ArchivoNoReconocido(f"hay una curva con puntos fuera de y = 0 (y de {datos[:, 1].min() / 10:g} a {datos[:, 1].max() / 10:g} [cm]): este lector solo lee "
                                  "curvas a lo largo de x o de z por el eje (un perfil en diagonal, a lo largo de y o fuera del eje no se puede leer sin su y)")
    return Curva(campo, _ssd(cabecera["SSD"], "La SSD de una curva") if "SSD" in cabecera else None, datos[:, 0] / 10, datos[:, 2] / 10, datos[:, 3])


def leer_curvas(texto):
    """Las curvas de un archivo W2CAD. Comprueba que estén todas las que anuncia `$NUMS`, que cada una termine y que sus números sean válidos."""
    preambulo, *bloques = texto.split("$STOM")
    if not bloques:
        raise ArchivoNoReconocido("no tiene curvas W2CAD")
    anunciadas = _anunciadas(preambulo)
    if anunciadas is not None and anunciadas != len(bloques):
        raise ArchivoNoReconocido(f"anuncia {anunciadas} curvas y trae {len(bloques)}: " + ("parece cortado" if len(bloques) < anunciadas else "no coinciden"))
    if "$ENOF" not in [_linea(l) for l in bloques[-1].split("\n")]:
        raise ArchivoNoReconocido("el archivo no termina: parece cortado")
    return [_curva(b, k == len(bloques) - 1) for k, b in enumerate(bloques)]


def _anunciadas(preambulo):
    """Las curvas que anuncia `$NUMS` antes de la primera curva, o None si no lo dice. Ahí solo caben `$NUMS`, comentarios y líneas vacías (UM.1b, P-12:
    «$NUMS doce» o «$NUMS011» se aceptaban sin contar las curvas)."""
    pares = []
    for linea in (_linea(l) for l in preambulo.split("\n")):
        coincide = re.fullmatch(r"\$NUMS[ \t]+([0-9]+)", linea)
        if coincide:
            pares.append(("$NUMS", int(coincide.group(1))))
        elif linea and not linea.startswith("#"):
            raise ArchivoNoReconocido(f"hay una línea antes de la primera curva que no se entiende: «{linea[:40]}»")
    return _sin_repetir(pares, "el archivo").get("$NUMS")


def leer_tabla_of(texto):
    """La tabla de factores. Exige SSD y profundidad en la cabecera, valores posibles y 1.000 en 10 × 10."""
    lineas = [l for l in texto.split("\n") if l.strip(_BLANCOS)]
    claves = [(l, _clave(l)) for l in lineas if l.startswith("%")]      # R2: el valor no se recorta a la derecha (un blanco al final de «50» puede ser su «0»); `_numero` rechaza el que lo trae
    pares = [par for _, par in claves if par]
    cabecera = {clave: valor for clave, valor in pares if valor}      # un dato vacío es un dato que falta (R1-H4)
    if cabecera.get("TYPE", "").rstrip(_BLANCOS) != "OutputFactorTable" or "SourcePhantomDistance" not in cabecera or "DetectorDepth" not in cabecera:      # UM1b-D5, acotada (R2): el TIPO es un texto y se compara entero
        raise ArchivoNoReconocido("no es una tabla de factores con SSD y profundidad en la cabecera")
    ilegibles = [l for l, par in claves if par is None]
    if ilegibles:      # UM.1b (S2): una fila de valores con «%» delante se saltaba y la tabla quedaba con una fila menos
        raise ArchivoNoReconocido(f"la cabecera de la tabla de factores tiene una línea que no se entiende: «{ilegibles[0][:40]}»")
    cabecera = _sin_repetir(pares, "la cabecera de la tabla de factores")
    _exigir_final_de_linea(texto, "la tabla de factores", "cortada")      # la tabla no trae marca de fin: sin esto, un corte dentro de su último número pasaría por un valor
    filas = [l.lstrip(_BLANCOS) for l in lineas if not l.startswith(("#", "%"))]      # la sangría no es parte de la fila; el final sí (R2)
    primera = next((k for k, l in enumerate(lineas) if not l.startswith(("#", "%"))), len(lineas))      # la línea de lados X: el primer dato
    comentadas = [l for l in lineas[primera:] if l.startswith("#")]
    if comentadas:      # UM.1b, ronda 1 (R1): en las 105 tablas reales todo comentario va antes de la línea de lados X; un «3» que se vuelve «#» (un bit) hacía desaparecer la fila Y 30, 35 o 3
        raise ArchivoNoReconocido(f"la tabla de factores tiene un comentario entre sus datos: «{comentadas[0][:40]}» "
                                  "(en los archivos de Eclipse los comentarios van antes de la línea de lados X; una fila comentada se perdería sin aviso)")
    if len(filas) < 2:
        raise ArchivoNoReconocido("la tabla de factores no trae su línea de lados X y por lo menos una fila de valores")
    numeros = [[_numero(v.lstrip(_BLANCOS)) for v in linea.split(",")] for linea in filas]      # R2: solo el blanco de DESPUES de la coma; uno antes de la coma o al final de la fila se rechaza
    malas = [linea for linea, fila in zip(filas, numeros) if None in fila]
    if malas:
        raise ArchivoNoReconocido(f"la tabla de factores tiene una línea que no son números separados por comas: «{malas[0][:40]}»")
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
    if np.any(tabla.m < FACTOR_MINIMO) or np.any(tabla.m > FACTOR_MAXIMO):      # finitos ya los deja `_numero`
        raise ArchivoNoReconocido(f"la tabla de factores tiene un valor imposible (fuera de {FACTOR_MINIMO:g} a {FACTOR_MAXIMO:g})")
    i, j = np.flatnonzero(tabla.y == 10), np.flatnonzero(tabla.x == 10)
    if len(i) != 1 or len(j) != 1 or tabla.m[i[0], j[0]] != 1.0:
        raise ArchivoNoReconocido("la tabla de factores no vale 1.000 en 10 × 10 [cm]")
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
            pares.append((coincide.group(1).strip(), (coincide.group(3).lstrip(_BLANCOS), coincide.group(2).strip())))      # R2: el valor llega hasta el final de la línea y no se recorta (lo rechaza `_numero`)
        elif linea.strip(_BLANCOS):      # UM.1b (P-13, IX13): «Wedge angle[deg] :15.0» o una segunda «Data parameters:» se saltaban y el ángulo quedaba en None
            raise ArchivoNoReconocido(f"el name.data tiene una línea de parámetros que no es «nombre[unidad]:valor»: «{linea.strip(_BLANCOS)[:40]}»")
    parametros = _sin_repetir(pares, "el name.data")
    if not parametros:
        raise ArchivoNoReconocido("no tiene parámetros")
    return parametros


def _positivo(texto_valor):
    """El número de un parámetro (`_numero`) si es mayor que 0; None si no lo es (0 no es «ausente»: es un valor imposible)."""
    valor = _numero(texto_valor)
    return valor if valor is not None and valor > 0 else None


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
        raise ArchivoNoReconocido(f"la dosis de referencia viene en [{dosis[1]}] por [{ums[1]}]: se esperaba [Gy] o [cGy] por [MU]")
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
    return valor.rstrip(_BLANCOS).upper() if valor else None      # un texto: se compara entero, así que sus blancos finales no esconden nada


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
