"""CD.4 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, DA-90): la ÚNICA puerta a las dos tablas de una calibración de película (`calibracion_pelicula`, raíz propia sin FK, y `calibracion_pelicula_pieza`, su hija por
`ref`) y a la carpeta de sus escaneos junto a la base.

Sin ella la ventana de calibración (CD.5) tendría SQL propio y el motor mensual (CD.6) su propia lectura de «la curva vigente»: dos definiciones de lo que es una calibración guardada. Aquí viven guardar,
anular, listar, leer, las vigentes válidas, volver a ajustar lo guardado y compararlo con lo guardado. Qué se mide de una pieza lo dice CD.2 (`medir_pieza_uniforme`) y qué es la curva lo dice CD.3
(`curva_dosis.ajustar`): este módulo nunca calcula una media, una densidad óptica ni un parámetro de la curva.

Reglas de este servicio, cada una con su motivo:
  - `guardar` MIDE él mismo cada pieza desde sus bytes (CD.2, con la escala que declara el archivo, DC15) y AJUSTA (CD.3), una sola vez: no recibe una curva ajena, porque nada garantiza que sea la de
    esos escaneos (la clase de error de IM3/DA-65). Lo que se guarda sale de esa medición y de ese ajuste, nunca de una lectura propia.
  - La película virgen montada llega por argumento (`virgen`, la `ReferenciaVirgen` que la ventana lee junto a la base), como en D.1: este módulo no lee ese archivo. Su copia se guarda con la calibración
    (`virgen`, DC3), haga o no de cero, para que CD.6 compare la virgen del análisis con la de la curva.
  - Los escaneos NO van a la base (DP-144): se copian a `calibraciones_pelicula_escaneos/<sha256><extensión>` junto a la base (DC6) con la misma copia que la película virgen (CD.2), y la copia se
    comprueba leyéndola de vuelta: su sha256 debe ser el de la pieza. Un archivo que ya está con ese nombre y otro contenido no se sobrescribe. Una copia que ya estaba y no es su huella no se toca: el
    guardado se rechaza diciendo que hay que apartarla a mano. Una copia que este guardado escribió y no coincide con su huella se quita y el guardado se rechaza. Las copias se hacen ANTES de abrir la
    transacción: si una falla no se escribe nada en la base; si después falla la base, la copia queda (su nombre es su huella y un guardado posterior la reusa).
  - UNA transacción (`reemplazar_bloque`): anula la calibración vigente con la misma clave de bloque (`lote`, `DATE(fecha_irradiacion)`, `energia`) y sus piezas, inserta la nueva con las suyas y
    escribe UNA fila de auditoría (`guardar`, o `reemplazo` con el `id` de la reemplazada), con el lote, la fecha y el estado de cada capa; si algo falla a mitad no queda nada (DA-52).
  - `anular` va por identidad (`WHERE id = ?`) y anula también sus piezas, con UNA fila de auditoría en la misma transacción. El permiso de anular NO se comprueba aquí: es del diálogo de la ventana
    (`DialogAdminPermisoEliminar`, DA-01), igual que la posición inicial (PI.3/PI.4).
  - Lecturas según la selectividad (DA-47): `listar` y `vigentes_validas` leen el bloque y filtran `activo` con `{filtro_activo(...)}` dentro del f-string (Trampa 6); `leer(id)` lee por identidad y
    no filtra: una calibración anulada (o reemplazada) se abre igual, con sus piezas (las de UNA raíz: nunca se insertan piezas bajo un `ref` que ya tiene).
  - Los JSON pasan por la puerta estricta de D.1, que CD.4 subió a `services/json_estricto.py` (la ÚNICA definición: rechaza NaN, infinito y lo que JSON no admite) con la clase de error de este servicio.
  - El ajuste se guarda (la copia de `CurvaDeDosis.como_dict()`): es la excepción declarada a la regla del 09-09, porque es la REFERENCIA con que se medirán los análisis (DA-81). `recalcular` lo rehace
    desde lo medido guardado (sin los escaneos) y, si están todos, volviendo a medir las piezas; `diferencias` dice lo que no coincide.

Contrato del llamador (CD4-R3-D8). Los llamadores cooperantes -- la ventana de calibración (CD.5), el motor mensual (CD.6) y los PDF -- pasan tipos básicos de Python y de numpy (textos, números, bytes, listas,
diccionarios, y los escalares y arreglos de numpy). Lo que no es de su tipo, está fuera de rango o no se puede escribir se rechaza con `CurvaDosisError` (la ventana lo dice tal cual), y un rechazo de la validación
significa que no se escribió nada: ni filas, ni auditoría, ni copias de escaneos. Si falla una copia, o la base ya con las copias hechas, quedan las copias (su nombre es su huella y el guardado siguiente las reusa) y
nunca filas ni auditoría a medias. `recalcular` responde `CurvaDosisError` a un registro de `leer` alterado. Fuera de contrato: los objetos cuyo `__repr__`, `__hash__`, `__eq__` o `__bool__` lanzan; `recalcular` llamado
con algo que no es lo que da `leer` (un escalar o un arreglo de numpy lanza `IndexError`); `guardar` con unas condiciones de irradiación anidadas del orden de 1000 niveles o más (la serialización a JSON agota el límite
de recursión de Python y lanza `RecursionError`, antes de escribir nada; el recorrido de las claves, que es iterativo, no); y los ayudantes internos `diferencias` y `ruta_del_escaneo` llamados con otra cosa que lo que
dan `leer`, `recalcular` y la procedencia de CD.2 (lanzan los `TypeError`, `AttributeError`, `KeyError` o `IndexError` naturales de Python).

Sin Qt."""
import copy
import dataclasses
import hashlib
import json
import math
import numbers
import os
import re
import stat
import sys
from datetime import datetime

from analisisImagenes import curva_dosis as motor
from analisisImagenes.pelicula import (CAPAS_DEL_PISO, ReferenciaVirgen, _copiar_el_escaneo, _extension_del_escaneo, _json_normal, medir_pieza_uniforme,
                                       referencia_virgen_desde_dict)
from analisisImagenes.placa_mensual import VALORES_DE_LA_GEOMETRIA
from data.ManejoDatos import conection as _conection
from data.ManejoDatos.conection import Conexion
from services.anulacion import filtro_activo, reemplazar_bloque
from services.audit_minimo import ACCION_ANULAR, ACCION_GUARDAR, ACCION_REEMPLAZO
from services.audit_minimo import registrar as _registrar_auditoria
from services.json_estricto import json_estricto

TABLA = "calibracion_pelicula"
TABLA_PIEZAS = "calibracion_pelicula_pieza"

# DC6: la carpeta de los escaneos, junto a la base (como `piso_pelicula_virgen_escaneos` de la película virgen).
CARPETA_ESCANEOS_CALIBRACION = "calibraciones_pelicula_escaneos"

# Lo que trae el encabezado de una calibración: lo obligatorio (decide la clave de bloque o qué se calibró: sin valor por omisión) y lo que puede faltar.
CLAVES_OBLIGATORIAS_DEL_ENCABEZADO = ("lote", "tipo_pelicula", "fecha_irradiacion", "energia")
CLAVES_OPCIONALES_DEL_ENCABEZADO = ("acelerador", "condiciones", "camara", "electrometro", "u_dosis_medida_pct", "escaner_declarado", "modo_de_escaneo", "observaciones", "parametros_de_la_curva")
CLAVES_DE_UN_EQUIPO = ("modelo", "serie", "factor", "equipo_id")          # la copia (modelo, serie, factor) y el puntero (DA-13, DP-105)
MODOS_DE_ESCANEO = ("transmisión", "reflexión")
# Lo que trae cada pieza del formulario.
CLAVES_OBLIGATORIAS_DE_UNA_PIEZA = ("orden", "dosis_nominal_cgy", "dosis_medida_cgy", "datos", "nombre_archivo")
CLAVES_OPCIONALES_DE_UNA_PIEZA = ("fecha_escaneo",)

# Cuánto se pueden apartar lo guardado y lo recalculado para que `diferencias` los dé por iguales (relativo, y absoluto cerca de cero). El mismo código sobre los mismos números da el mismo resultado al
# bit; esto solo absorbe el ruido de punto flotante de otra máquina.
TOLERANCIA_RELATIVA_AL_RECALCULAR = 1e-9
TOLERANCIA_ABSOLUTA_AL_RECALCULAR = 1e-12

_RE_FECHA = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

_COLUMNAS_DE_LA_CALIBRACION = (
    "lote", "tipo_pelicula", "fecha_irradiacion", "acelerador", "energia", "condiciones",
    "camara_modelo", "camara_serie", "camara_factor", "camara_equipo_id", "electrometro_modelo", "electrometro_serie", "electrometro_factor", "electrometro_equipo_id",
    "u_dosis_medida_pct", "cadena_de_captura", "cero", "virgen", "parametros", "modelo", "version", "ajuste", "estado", "observaciones", "usuario", "fecha_registro")
_COLUMNAS_DE_LA_PIEZA = (
    "ref", "orden", "dosis_nominal_cgy", "dosis_medida_cgy", "nombre_archivo", "sha256", "bytes", "formato", "bits", "dpi_declarado", "equipo", "fecha_exif", "dimensiones_px",
    "escaner_declarado", "fecha_escaneo", "posicion_mm", "medida", "estado")
_COLUMNAS_JSON_DE_LA_CALIBRACION = ("condiciones", "cadena_de_captura", "cero", "virgen", "parametros", "ajuste", "estado")
_COLUMNAS_JSON_DE_LA_PIEZA = ("dimensiones_px", "posicion_mm", "medida")

SQL_INSERT_CALIBRACION = f"INSERT INTO calibracion_pelicula ({', '.join(_COLUMNAS_DE_LA_CALIBRACION)}) VALUES ({', '.join('?' * len(_COLUMNAS_DE_LA_CALIBRACION))})"
SQL_INSERT_PIEZA = f"INSERT INTO calibracion_pelicula_pieza ({', '.join(_COLUMNAS_DE_LA_PIEZA)}) VALUES ({', '.join('?' * len(_COLUMNAS_DE_LA_PIEZA))})"

TEXTO_DE_LA_CALIBRACION = "lote {lote}, irradiada el {fecha}, {energia}"
TEXTO_COPIA_QUE_NO_COINCIDE = ("la pieza {orden} ({archivo}): su copia {copia} junto a la base ya no coincide con su huella sha256 (no es el escaneo que se midió), así que no se volvió a medir "
                               "ninguna pieza desde su escaneo")
TEXTO_NO_SE_PUEDE_ESCRIBIR = "{que} tiene un carácter que no se puede escribir en la base"          # CD4-R3-D7: una sola definición, para _texto, _nombre_de_archivo, _json y _usuario


class CurvaDosisError(ValueError):
    """Lo que el servicio rechaza ANTES de escribir nada en la base (y todo `ValueError` del motor, de la medición o de la copia de un escaneo, con su mensaje): la ventana lo dice tal cual."""


@dataclasses.dataclass(frozen=True, eq=False)
class Recalculo:
    """Lo que da `recalcular`: la curva rehecha desde lo medido guardado (sin los escaneos), la rehecha volviendo a medir las piezas desde sus escaneos (None si falta alguno o alguno ya no coincide con
    su huella), los escaneos que faltan (sus nombres de archivo en la carpeta de la calibración) y las copias que están pero ya no coinciden con su huella (sus nombres)."""
    desde_lo_medido: object
    desde_los_escaneos: object
    escaneos_que_faltan: tuple
    escaneos_que_no_coinciden: tuple = ()


# ================================================================================================================================== ayudas

def _json(valor, columna):
    """El texto JSON de una columna, por la puerta estricta de D.1 (`services/json_estricto.py`, la ÚNICA definición): `CurvaDosisError` -- y no se escribe nada -- si no cabe en JSON válido o si el texto
    tiene un carácter que no se puede escribir en la base (CD4-R3-D7: se mira aquí, sobre el texto JSON resultante, que lleva las claves y los valores de las condiciones; la puerta común es de D.1 y no se edita)."""
    texto = json_estricto(valor, columna, CurvaDosisError, sort_keys=True, ensure_ascii=False)
    if not _se_puede_escribir(texto):
        raise CurvaDosisError(TEXTO_NO_SE_PUEDE_ESCRIBIR.format(que=f"lo que se guarda en la columna '{columna}'"))
    return texto


def _es_real_finito(valor):
    """Un número real finito (de Python o de numpy), nunca un bool; un entero que no cabe en un float no es finito (sin esto escapa `OverflowError`)."""
    if isinstance(valor, bool) or not isinstance(valor, numbers.Real):
        return False
    try:
        return math.isfinite(float(valor))
    except OverflowError:
        return False


def _entero_que_cabe_en_la_base(valor):
    """Un entero (de Python o de numpy), nunca un bool, que cabe en un INTEGER de SQLite (de -2**63 a 2**63 - 1) y por eso también en un float finito. Sin esto, un entero mayor escapa como
    `OverflowError` crudo al escribir la fila o al comparar (`math.isclose`)."""
    return not isinstance(valor, bool) and isinstance(valor, numbers.Integral) and -2**63 <= int(valor) < 2**63


def _como_texto(valor):
    """`repr` de lo que se rechaza, para el mensaje; sin que un entero de más de `sys.get_int_max_str_digits()` cifras (4300 en Python 3.11) haga escapar un `ValueError` al escribirlo, ni un valor cuyo `repr` lanza
    cualquier otra excepción (CD4-R3-D6): ese se dice por su tipo."""
    try:
        return repr(valor)
    except ValueError:
        return f"un {type(valor).__name__} con un entero de más de {sys.get_int_max_str_digits()} cifras"
    except Exception:
        return f"un {type(valor).__name__} que no se puede escribir"


def _se_puede_escribir(texto):
    """True si el texto se puede escribir en la base, que guarda UTF-8. Un surrogado suelto (un nombre de archivo de Linux con bytes inválidos lo produce) no se puede: SQLite lo rechaza al escribir con un
    `UnicodeEncodeError`, y lo hacía DESPUÉS de copiar los escaneos (CD4-R3-D7)."""
    try:
        texto.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _texto(valor, que, obligatorio=True):
    if valor is None and not obligatorio:
        return None
    if not isinstance(valor, str) or not valor.strip():
        raise CurvaDosisError(f"falta {que}" if obligatorio else f"{que} debe ser un texto o nada, no {_como_texto(valor)}")
    texto = valor.strip()
    if not _se_puede_escribir(texto):
        raise CurvaDosisError(TEXTO_NO_SE_PUEDE_ESCRIBIR.format(que=que))
    return texto


def _numero(valor, que, minimo=None):
    if valor is None:
        return None
    if not _es_real_finito(valor) or (minimo is not None and float(valor) < minimo):
        raise CurvaDosisError(f"{que} debe ser un número finito{'' if minimo is None else f' de {minimo:g} o más'} o nada, no {_como_texto(valor)}")
    return float(valor)


def fecha_iso(valor):
    """'aaaa-mm-dd' de una fecha válida (texto 'aaaa-mm-dd'), o None. La clave de bloque compara `DATE(fecha_irradiacion)`, así que se guarda SIEMPRE así: el año con cuatro cifras y el mes y el día con dos, escritos
    aquí y no con `strftime` (en Linux `%Y` da '999' para el año 999, y `DATE('999-12-31')` de SQLite es NULL: la clave de bloque dejaba de funcionar y quedaban dos calibraciones vigentes del mismo bloque; CD4-R3-D5).
    El año no se rechaza: 0001 a 9999 son fechas válidas."""
    if not isinstance(valor, str):
        return None
    m = _RE_FECHA.match(valor.strip())
    if m is None:
        return None
    try:
        fecha = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return f"{fecha.year:04d}-{fecha.month:02d}-{fecha.day:02d}"


def _usuario(usuario, que):
    """El usuario que guarda o anula, validado UNA vez en la frontera (CD4-R3-D1) y devuelto SIN los espacios de los lados: ESE texto es el que va a la columna `usuario` de la fila, a `reemplazar_bloque` y a la
    auditoría, en `guardar` y en `anular` (nunca el valor crudo). Antes se validaba `str(usuario).strip()` y se pasaba el crudo: con una lista, un `Path`, un `Fraction` o un entero de más de 64 bits la calibración se
    guardaba (o se anulaba) SIN su fila de auditoría y sin aviso (`audit_minimo` se traga el error por diseño) y con «  ana  » la fila y la auditoría guardaban usuarios distintos. `que` es lo que hace
    («guarda la calibración», «anula la calibración»). `CurvaDosisError` si falta (nada o solo espacios), si no es un texto o si tiene un carácter que no se puede escribir en la base (CD4-R3-D7)."""
    if usuario is None:
        raise CurvaDosisError(f"falta el usuario que {que}")
    if not isinstance(usuario, str):
        raise CurvaDosisError(f"el usuario que {que} debe ser un texto, no {_como_texto(usuario)}")
    texto = usuario.strip()
    if not texto:
        raise CurvaDosisError(f"falta el usuario que {que}")
    if not _se_puede_escribir(texto):
        raise CurvaDosisError(TEXTO_NO_SE_PUEDE_ESCRIBIR.format(que=f"el usuario que {que}"))
    return texto


def _id_de_calibracion(id_calibracion):
    """El id de una calibración como `int` (CD4-R3-D2): un entero de Python o de numpy que cabe en un INTEGER de SQLite, nunca un bool (para SQLite `True == 1`: `leer(True)` devolvía la calibración 1 y `anular(True)` la
    anulaba). Antes `anular` y `leer` lo pasaban tal cual a SQLite: un entero de más de 64 bits salía como `OverflowError`, un `Fraction`, un `Path` o una lista como `sqlite3.ProgrammingError`, un texto con un surrogado
    como `UnicodeEncodeError`, y un `np.int64` se ligaba como bytes y no encontraba nada. `CurvaDosisError` con los dos textos del `equipo_id` (`_equipo`)."""
    if isinstance(id_calibracion, bool) or not isinstance(id_calibracion, numbers.Integral):
        raise CurvaDosisError(f"el id de la calibración debe ser un entero, no {_como_texto(id_calibracion)}")
    if not _entero_que_cabe_en_la_base(id_calibracion):
        raise CurvaDosisError(f"el id de la calibración no cabe en la base (un entero de -9223372036854775808 a 9223372036854775807), no {_como_texto(id_calibracion)}")
    return int(id_calibracion)


def _nombre_de_archivo(nombre, orden=None):
    """Solo el nombre, sin la carpeta (con '/' o con '\\'): en la base no se guarda la ruta del equipo de quien lo subió. `CurvaDosisError` (que nombra la pieza `orden`, y solo si hay que rechazar) si lo que se guarda tiene un
    carácter que no se puede escribir en la base (CD4-R3-D7); solo se mira el nombre, no la carpeta, porque la carpeta no se guarda."""
    texto = str(nombre).replace("\\", "/").rsplit("/", 1)[-1].strip()
    if texto and not _se_puede_escribir(texto):
        raise CurvaDosisError(TEXTO_NO_SE_PUEDE_ESCRIBIR.format(que="el nombre del archivo" if orden is None else f"el nombre del archivo de la pieza {orden}"))
    return texto or None


def _equipo(datos, que):
    """La copia y el puntero de la cámara o del electrómetro (DA-13): None, o un diccionario con EXACTAMENTE `CLAVES_DE_UN_EQUIPO`, cada una nada o de su tipo."""
    if datos is None:
        return dict.fromkeys(CLAVES_DE_UN_EQUIPO)
    if not isinstance(datos, dict) or set(datos) != set(CLAVES_DE_UN_EQUIPO):
        raise CurvaDosisError(f"{que} es un diccionario con {', '.join(CLAVES_DE_UN_EQUIPO)}, o nada")
    puntero = datos["equipo_id"]
    if puntero is not None and (isinstance(puntero, bool) or not isinstance(puntero, numbers.Integral)):
        raise CurvaDosisError(f"el equipo_id de {que} es un entero o nada, no {_como_texto(puntero)}")
    if puntero is not None and not _entero_que_cabe_en_la_base(puntero):
        raise CurvaDosisError(f"el equipo_id de {que} no cabe en la base (un entero de -9223372036854775808 a 9223372036854775807), no {_como_texto(puntero)}")
    return {"modelo": _texto(datos["modelo"], f"el modelo de {que}", False), "serie": _texto(datos["serie"], f"la serie de {que}", False),
            "factor": _numero(datos["factor"], f"el factor de {que}"), "equipo_id": None if puntero is None else int(puntero)}


def _parametros_de_la_curva(parametros):
    """Los parámetros de la curva validados por el tipo de su valor de fábrica (`motor.VALORES_DE_LA_CURVA`, la ÚNICA definición), con el tipo de Python con que se guardan: un entero de 1 o
    más que cabe en la base (int), un número finito de 0 o más (float; -0.0 se guarda 0.0), o el nombre del motor (modelo y versión no se eligen: se admiten solo iguales, porque `recalcular`
    pasa el diccionario guardado entero). `CurvaDosisError` con el nombre del parámetro si no. Los rangos son de significado, no físicos: los umbrales los decide el físico (P1 de CD.4) y los
    recalibra CD.10."""
    if not isinstance(parametros, dict) or set(parametros) - set(motor.VALORES_DE_LA_CURVA):
        raise CurvaDosisError(f"los parámetros de la curva son un diccionario con nombres de PARAMETROS_DE_LA_CURVA, no {_como_texto(parametros)}")
    validos = {}
    for nombre in sorted(parametros):
        valor, fabrica = parametros[nombre], motor.VALORES_DE_LA_CURVA[nombre]
        if isinstance(fabrica, str):
            if not isinstance(valor, str) or valor != fabrica:
                raise CurvaDosisError(f"el parámetro de la curva {nombre!r} es el del motor ({fabrica!r}) y no se elige, no {_como_texto(valor)}")
            validos[nombre] = fabrica
        elif isinstance(fabrica, int) and not isinstance(fabrica, bool):
            if not _entero_que_cabe_en_la_base(valor) or int(valor) < 1:
                raise CurvaDosisError(f"el parámetro de la curva {nombre!r} debe ser un entero de 1 o más, no {_como_texto(valor)}")
            validos[nombre] = int(valor)
        elif isinstance(fabrica, float):
            if not _es_real_finito(valor) or float(valor) < 0.0:
                raise CurvaDosisError(f"el parámetro de la curva {nombre!r} debe ser un número finito de 0 o más, no {_como_texto(valor)}")
            validos[nombre] = float(valor) + 0.0
        else:
            raise CurvaDosisError(f"el parámetro de la curva {nombre!r} no es un número ni un nombre: este servicio no sabe validarlo")
    return validos


def _claves_de_las_condiciones(condiciones):
    """Toda clave de diccionario de las condiciones, a cualquier profundidad (dentro de diccionarios, listas y tuplas), es un texto: JSON vuelve texto cualquier otra clave y `leer` devolvía otras claves que las que entraron
    ({1: 2} se guardaba {"1": 2}, {True: 1} {"true": 1}, {None: 1} {"null": 1}). `CurvaDosisError` con la primera que no lo es. Los VALORES siguen libres (CD4-R2-D2). El recorrido es ITERATIVO y recuerda los contenedores que
    ya vio: una estructura que se contiene a sí misma ni cuelga ni lanza `RecursionError` (la puerta estricta de JSON la rechaza después), y una muy honda tampoco agota la recursión de Python en este recorrido (CD4-R3-D3);
    guardar entera, en cambio, sí puede agotarla hacia los 1000 niveles, en la serialización a JSON (`RecursionError`, antes de escribir nada: fuera de contrato, ver el docstring del módulo; CD4-R4-D2)."""
    pendientes, vistos = [condiciones], set()
    while pendientes:
        actual = pendientes.pop()
        if id(actual) in vistos:
            continue
        vistos.add(id(actual))
        if isinstance(actual, dict):
            for clave, hijo in actual.items():
                if not isinstance(clave, str):
                    raise CurvaDosisError(f"las condiciones de irradiación solo admiten claves de texto, no {_como_texto(clave)}")
                if isinstance(hijo, (dict, list, tuple)):
                    pendientes.append(hijo)
        else:
            pendientes.extend(hijo for hijo in actual if isinstance(hijo, (dict, list, tuple)))


def _encabezado_valido(encabezado):
    if not isinstance(encabezado, dict):
        raise CurvaDosisError("el encabezado de la calibración es un diccionario")
    sobran = sorted(set(encabezado) - set(CLAVES_OBLIGATORIAS_DEL_ENCABEZADO) - set(CLAVES_OPCIONALES_DEL_ENCABEZADO))
    if sobran:
        raise CurvaDosisError(f"el encabezado trae claves que la calibración no conoce: {sobran}")
    faltan = [k for k in CLAVES_OBLIGATORIAS_DEL_ENCABEZADO if k not in encabezado]
    if faltan:
        raise CurvaDosisError(f"al encabezado le faltan {faltan} (sin valor por omisión: deciden qué se calibró)")
    fecha = fecha_iso(encabezado["fecha_irradiacion"])
    if fecha is None:
        raise CurvaDosisError(f"la fecha de irradiación debe ser 'aaaa-mm-dd', no {_como_texto(encabezado['fecha_irradiacion'])}")
    condiciones = encabezado.get("condiciones")
    condiciones = {} if condiciones is None else condiciones
    if not isinstance(condiciones, dict):
        raise CurvaDosisError("las condiciones de irradiación son un diccionario (profundidad, DFS y campo)")
    _claves_de_las_condiciones(condiciones)
    parametros = encabezado.get("parametros_de_la_curva")
    parametros = None if parametros is None else _parametros_de_la_curva(parametros)
    modo = encabezado.get("modo_de_escaneo")
    if modo is not None and (not isinstance(modo, str) or modo not in MODOS_DE_ESCANEO):
        raise CurvaDosisError(f"el modo de escaneo es {' o '.join(MODOS_DE_ESCANEO)}, o nada, no {_como_texto(modo)}")
    return {"lote": _texto(encabezado["lote"], "el lote de la película"), "tipo_pelicula": _texto(encabezado["tipo_pelicula"], "el tipo de película"), "fecha_irradiacion": fecha,
            "energia": _texto(encabezado["energia"], "la energía"), "acelerador": _texto(encabezado.get("acelerador"), "el acelerador", False), "condiciones": condiciones,
            "camara": _equipo(encabezado.get("camara"), "la cámara"), "electrometro": _equipo(encabezado.get("electrometro"), "el electrómetro"),
            "u_dosis_medida_pct": _numero(encabezado.get("u_dosis_medida_pct"), "la incertidumbre de la dosis medida", 0.0),
            "escaner_declarado": _texto(encabezado.get("escaner_declarado"), "el escáner declarado", False), "modo_de_escaneo": modo,
            "observaciones": _texto(encabezado.get("observaciones"), "las observaciones", False), "parametros_de_la_curva": parametros}


def _piezas_validas(piezas):
    try:
        lista = list(piezas)
    except TypeError:
        raise CurvaDosisError("las piezas son una lista de diccionarios, una por escaneo") from None
    if not lista:
        raise CurvaDosisError("una calibración necesita al menos una pieza")
    validas, ordenes = [], set()
    for i, p in enumerate(lista, 1):
        if not isinstance(p, dict):
            raise CurvaDosisError(f"la pieza {i} de la lista no es un diccionario")
        sobran = sorted(set(p) - set(CLAVES_OBLIGATORIAS_DE_UNA_PIEZA) - set(CLAVES_OPCIONALES_DE_UNA_PIEZA))
        faltan = [k for k in CLAVES_OBLIGATORIAS_DE_UNA_PIEZA if k not in p]
        if sobran or faltan:
            raise CurvaDosisError(f"la pieza {i} de la lista: le faltan {faltan} o trae claves que no se conocen {sobran}")
        if isinstance(p["orden"], bool) or not isinstance(p["orden"], numbers.Integral) or p["orden"] in ordenes:
            raise CurvaDosisError(f"el orden de la pieza {i} de la lista debe ser un entero que no se repite, no {_como_texto(p['orden'])}")
        if not _entero_que_cabe_en_la_base(p["orden"]):
            raise CurvaDosisError(f"el orden de la pieza {i} de la lista no cabe en la base (un entero de -9223372036854775808 a 9223372036854775807), no {_como_texto(p['orden'])}")
        for campo, que in (("dosis_nominal_cgy", "nominal"), ("dosis_medida_cgy", "medida")):
            if isinstance(p[campo], numbers.Integral) and not isinstance(p[campo], bool) and not _es_real_finito(p[campo]):
                raise CurvaDosisError(f"la dosis {que} de la pieza {p['orden']} debe ser un número finito, no {_como_texto(p[campo])}")
        ordenes.add(p["orden"])
        if not isinstance(p["datos"], (bytes, bytearray)) or not p["datos"]:
            raise CurvaDosisError(f"falta el escaneo de la pieza {p['orden']}")
        nombre = _nombre_de_archivo(p["nombre_archivo"], p["orden"]) if isinstance(p["nombre_archivo"], str) else None
        if nombre is None:
            raise CurvaDosisError(f"falta el nombre del archivo de la pieza {p['orden']}")
        fecha_escaneo = p.get("fecha_escaneo")
        if fecha_escaneo is not None and fecha_iso(fecha_escaneo) is None:
            raise CurvaDosisError(f"la fecha de escaneo de la pieza {p['orden']} debe ser 'aaaa-mm-dd' o nada, no {_como_texto(fecha_escaneo)}")
        validas.append({"orden": int(p["orden"]), "dosis_nominal_cgy": p["dosis_nominal_cgy"], "dosis_medida_cgy": p["dosis_medida_cgy"], "datos": bytes(p["datos"]), "nombre_archivo": nombre,
                        "fecha_escaneo": None if fecha_escaneo is None else fecha_iso(fecha_escaneo)})
    return validas


def _cadena_de_la_calibracion(curva, encabezado):
    """La cadena de captura que guarda la calibración (DA-90): la de las piezas (`CurvaDeDosis.cadena`: el escáner que declara el archivo, los bits, la resolución y el formato; None si no es una sola),
    más lo que declara el físico (el escáner y si escaneó por transmisión o por reflexión). Lo que compara la condición 3 de DC8 es la de las piezas."""
    return {"piezas": _json_normal(curva.cadena), "escaner_declarado": encabezado["escaner_declarado"], "modo_de_escaneo": encabezado["modo_de_escaneo"]}


def _estado_por_capa(curva):
    return {c: curva.estado(c) for c in CAPAS_DEL_PISO}


def _medida_de_la_pieza(pieza):
    """El JSON `medida` de una pieza: la pieza tal como entró a la curva (por capa el valor, su u, si está recortada, su netOD contra el cero con su u, su dosis desde el cero, el residuo y si está en el
    rango útil; su posición, el blanco del fondo y su cadena de captura: lo que `recalcular` necesita para rehacer la curva sin el escaneo) y la medición entera de CD.2 (la región, la mediana, la
    media, n y la desviación de la región central, las pruebas y la procedencia)."""
    medicion = None if pieza.medida is None else _json_normal(dataclasses.asdict(pieza.medida))
    return {"pieza": {"capas": _json_normal(pieza.capas), "posicion_mm": _json_normal(pieza.posicion_mm), "fondo_blanco": pieza.fondo_blanco, "cadena": _json_normal(pieza.cadena)},
            "medicion": medicion}


def _fila_de_la_pieza(ref, pieza, entrada, encabezado):
    procedencia = pieza.medida.procedencia
    return {"ref": ref, "orden": pieza.orden, "dosis_nominal_cgy": pieza.dosis_nominal_cgy, "dosis_medida_cgy": pieza.dosis_medida_cgy, "nombre_archivo": entrada["nombre_archivo"],
            "sha256": procedencia["sha256"], "bytes": procedencia.get("bytes"), "formato": procedencia.get("formato"), "bits": procedencia.get("bits"),
            "dpi_declarado": procedencia.get("dpi_declarado"), "equipo": procedencia.get("equipo"),
            "fecha_exif": procedencia.get("fecha_escaneo"), "dimensiones_px": None if procedencia.get("forma") is None else _json(procedencia["forma"], "dimensiones_px"),
            "escaner_declarado": encabezado["escaner_declarado"], "fecha_escaneo": entrada["fecha_escaneo"],
            "posicion_mm": None if pieza.posicion_mm is None else _json(pieza.posicion_mm, "posicion_mm"), "medida": _json(_medida_de_la_pieza(pieza), "medida"), "estado": pieza.estado}


def carpeta_de_los_escaneos():
    """La carpeta de los escaneos de las calibraciones, junto a la base (DC6)."""
    return os.path.join(os.path.dirname(_conection.ruta_base_datos()), CARPETA_ESCANEOS_CALIBRACION)


def ruta_del_escaneo(sha256, procedencia):
    """Dónde está (o estará) la copia del escaneo de una pieza: `<carpeta>/<sha256><extensión>`."""
    return os.path.join(carpeta_de_los_escaneos(), sha256 + _extension_del_escaneo(procedencia))


def _nombre_de_la_copia(fila):
    """El nombre de la copia del escaneo de una pieza guardada (`<sha256><extensión>`), sin la carpeta: el mismo que `ruta_del_escaneo`."""
    return fila["sha256"] + _extension_del_escaneo({"archivo": fila["nombre_archivo"], "formato": fila["formato"]})


def _copiar_y_verificar(medida, datos):
    """Copia el escaneo junto a la base (nunca sobrescribe: CD.2) y lo lee de vuelta: su sha256 debe ser el de la pieza. `CurvaDosisError` si no. Una copia que ya estaba se mide ANTES: si no es su huella,
    se rechaza sin tocarla y el texto dice que hay que apartarla a mano. Si la copia que escribió esta llamada no coincide, se quita (su nombre mentiría y bloquearía los guardados siguientes); lo que ya
    estaba no se toca nunca."""
    sha = medida.procedencia["sha256"]
    if hashlib.sha256(datos).hexdigest() != sha:
        raise CurvaDosisError(f"el escaneo {medida.procedencia.get('archivo')!r} no es el que se midió: su huella sha256 es otra")
    destino = ruta_del_escaneo(sha, medida.procedencia)
    ya_estaba = os.path.exists(destino)
    if ya_estaba and os.path.isfile(destino):
        try:
            with open(destino, "rb") as archivo:
                previo = hashlib.sha256(archivo.read()).hexdigest()
        except OSError as error:
            raise CurvaDosisError(f"no se pudo leer la copia del escaneo {os.path.basename(destino)} que ya estaba junto a la base: {error}") from error
        if previo != sha:
            raise CurvaDosisError(f"no se pudo copiar el escaneo {medida.procedencia.get('archivo')!r} junto a la base: la copia {os.path.basename(destino)} que ya estaba no coincide con su huella "
                                  f"(da {previo}), así que no es el escaneo que se midió; no se sobrescribe ni se toca: hay que apartarla a mano de {os.path.dirname(destino)} para volver a guardar este escaneo")
    try:
        _copiar_el_escaneo(os.path.dirname(_conection.ruta_base_datos()), medida, datos, subcarpeta=CARPETA_ESCANEOS_CALIBRACION)
    except (OSError, ValueError) as error:
        raise CurvaDosisError(f"no se pudo copiar el escaneo {medida.procedencia.get('archivo')!r} junto a la base: {error}") from error
    try:
        with open(destino, "rb") as archivo:
            copiado = hashlib.sha256(archivo.read()).hexdigest()
    except OSError as error:
        raise CurvaDosisError(f"no se pudo leer de vuelta la copia del escaneo {os.path.basename(destino)} junto a la base: {error}") from error
    if copiado == sha:
        return
    texto = f"la copia del escaneo {os.path.basename(destino)} no coincide con su huella: se esperaba {sha} y la copia da {copiado}"
    if ya_estaba:
        raise CurvaDosisError(f"{texto}; es la que ya estaba junto a la base: cambió mientras se guardaba y no se toca; hay que apartarla a mano para volver a guardar este escaneo")
    try:
        os.remove(destino)
    except OSError as error:
        raise CurvaDosisError(f"{texto}; no se pudo quitar ({error}): hay que quitarla a mano antes de volver a guardar") from error
    raise CurvaDosisError(f"{texto}; la copia que escribió este guardado se quitó")


def _detalle(encabezado, curva, n_piezas):
    estados = "; ".join(f"{c}: {curva.estado(c)}" for c in CAPAS_DEL_PISO)
    return f"{TEXTO_DE_LA_CALIBRACION.format(lote=encabezado['lote'], fecha=encabezado['fecha_irradiacion'], energia=encabezado['energia'])}; {n_piezas} piezas; {estados}"


# ================================================================================================================================== guardar y anular

def guardar(usuario, encabezado, piezas, virgen=None):
    """Guarda una calibración y devuelve el `id` nuevo. MIDE cada pieza desde sus bytes (CD.2, `escala="declarada"`) y AJUSTA la curva (CD.3), una sola vez (ver el docstring del módulo). Rechaza con
    `CurvaDosisError` (que es un `ValueError`) y SIN escribir nada en la base: usuario (que falta, que no es un texto o que no se puede escribir), encabezado (claves que faltan o sobran, una fecha que no es 'aaaa-mm-dd', un equipo mal formado, parámetros de la
    curva que no existen o cuyo valor no es de su tipo (un entero de 1 o más, un número finito de 0 o más, o el nombre del motor), condiciones que no son un diccionario o con una clave que no es un texto, o un número que no cabe en la base), piezas (ninguna, claves que faltan o sobran, un orden repetido, un escaneo vacío), una virgen que no es una `ReferenciaVirgen` «ok», lo que no cabe en JSON válido, un texto con un carácter que no se puede escribir en la base (CD4-R3-D7), y una copia
    de un escaneo que no se puede hacer o no coincide con su huella.

    `encabezado`: {lote, tipo_pelicula, fecha_irradiacion ('aaaa-mm-dd'), energia} obligatorios y {acelerador, condiciones (dict), camara y electrometro ({modelo, serie, factor, equipo_id}),
    u_dosis_medida_pct, escaner_declarado, modo_de_escaneo («transmisión» o «reflexión»), observaciones, parametros_de_la_curva (los de PARAMETROS_DE_LA_CURVA que se quieran cambiar)} opcionales.
    `piezas`: [{orden, dosis_nominal_cgy, dosis_medida_cgy (None si falta: la curva queda «incompleta»), datos (los bytes del escaneo tal como se subió), nombre_archivo} y, opcional, fecha_escaneo].
    `virgen`: la película virgen montada (`ReferenciaVirgen` «ok») o None.

    UNA transacción: anula la calibración vigente con la misma clave de bloque y sus piezas, inserta la nueva con las suyas y escribe UNA fila de auditoría (`guardar`, o `reemplazo` con el `id` de
    la reemplazada)."""
    usuario = _usuario(usuario, "guarda la calibración")
    cabeza = _encabezado_valido(encabezado)
    entradas = _piezas_validas(piezas)
    if virgen is not None and not (isinstance(virgen, ReferenciaVirgen) and virgen.estado == "ok"):
        raise CurvaDosisError("la película virgen montada debe ser una referencia válida («ok») o nada")
    parametros_de_la_medida = copy.deepcopy(VALORES_DE_LA_GEOMETRIA)
    hoy = datetime.now().strftime("%Y-%m-%d")
    medidas, calibradas = [], []
    try:
        for e in entradas:
            medida = medir_pieza_uniforme(e["datos"], parametros_de_la_medida, e["nombre_archivo"], hoy, escala="declarada")
            medidas.append(medida)
            calibradas.append(motor.pieza_de_calibracion(e["orden"], e["dosis_nominal_cgy"], e["dosis_medida_cgy"], medida))
        curva = motor.ajustar(calibradas, P=cabeza["parametros_de_la_curva"], virgen=virgen, u_dosis_medida_pct=cabeza["u_dosis_medida_pct"])
    except ValueError as error:
        raise CurvaDosisError(str(error)) from error
    por_orden = {p.orden: p for p in curva.piezas}
    fila = {
        "lote": cabeza["lote"], "tipo_pelicula": cabeza["tipo_pelicula"], "fecha_irradiacion": cabeza["fecha_irradiacion"], "acelerador": cabeza["acelerador"], "energia": cabeza["energia"],
        "condiciones": _json(cabeza["condiciones"], "condiciones"),
        **{f"camara_{k}": cabeza["camara"][k] for k in CLAVES_DE_UN_EQUIPO}, **{f"electrometro_{k}": cabeza["electrometro"][k] for k in CLAVES_DE_UN_EQUIPO},
        "u_dosis_medida_pct": cabeza["u_dosis_medida_pct"], "cadena_de_captura": _json(_cadena_de_la_calibracion(curva, cabeza), "cadena_de_captura"),
        "cero": None if curva.cero is None else _json(curva.cero, "cero"), "virgen": None if virgen is None else _json(virgen.como_dict(), "virgen"),
        "modelo": curva.modelo, "version": curva.version,
        "parametros": _json({"medida": parametros_de_la_medida, "curva": curva.parametros}, "parametros"), "ajuste": _json(curva.como_dict(), "ajuste"),
        "estado": _json(_estado_por_capa(curva), "estado"), "observaciones": cabeza["observaciones"], "usuario": usuario,
        "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    filas_de_las_piezas = [_fila_de_la_pieza(None, por_orden[e["orden"]], e, cabeza) for e in entradas]
    for medida, e in zip(medidas, entradas):                          # ANTES de la transacción: una copia que falla no deja nada en la base
        _copiar_y_verificar(medida, e["datos"])
    clave = [("lote", cabeza["lote"]), ("DATE(fecha_irradiacion)", cabeza["fecha_irradiacion"]), ("energia", cabeza["energia"])]
    with Conexion().conectar() as db:
        cursor = db.cursor()
        cursor.execute(f"SELECT id FROM calibracion_pelicula WHERE lote = ? AND DATE(fecha_irradiacion) = DATE(?) AND energia = ?{filtro_activo('calibracion_pelicula')} ORDER BY id DESC",
                       (cabeza["lote"], cabeza["fecha_irradiacion"], cabeza["energia"]))
        previa = cursor.fetchone()
        detalle = _detalle(cabeza, curva, len(entradas))
        if previa is not None:
            detalle += f"; reemplaza id={previa[0]}"
        reemplazar_bloque(cursor, TABLA, clave, SQL_INSERT_CALIBRACION, [tuple(fila[c] for c in _COLUMNAS_DE_LA_CALIBRACION)], usuario, detalle=detalle,
                          accion=ACCION_REEMPLAZO if previa is not None else ACCION_GUARDAR)
        nuevo_id = cursor.lastrowid
        if previa is not None:
            cursor.execute(f"UPDATE calibracion_pelicula_pieza SET activo = 0 WHERE ref = ?{filtro_activo('calibracion_pelicula_pieza')}", (previa[0],))
        for f in filas_de_las_piezas:
            f["ref"] = nuevo_id
        reemplazar_bloque(cursor, TABLA_PIEZAS, [("ref", nuevo_id)], SQL_INSERT_PIEZA, [tuple(f[c] for c in _COLUMNAS_DE_LA_PIEZA) for f in filas_de_las_piezas], usuario, auditar=False)
        db.commit()
    return nuevo_id


def anular(id_calibracion, usuario):
    """Anula (`activo = 0`) la calibración con ese `id` y sus piezas, con UNA fila de auditoría en la MISMA transacción. Devuelve True, o False (sin escribir ni auditar nada) si no existe o ya estaba
    anulada. Por identidad (DA-47). El permiso es del diálogo de la ventana (ver el docstring del módulo). `CurvaDosisError` -- y no se escribe ni se audita nada -- si el usuario falta, no es un texto o no se puede
    escribir (CD4-R3-D1), o si el id no es un entero que cabe en la base (CD4-R3-D2)."""
    usuario = _usuario(usuario, "anula la calibración")
    id_calibracion = _id_de_calibracion(id_calibracion)
    with Conexion().conectar() as db:
        cursor = db.cursor()
        cursor.execute("SELECT activo, lote, fecha_irradiacion, energia FROM calibracion_pelicula WHERE id = ?", (id_calibracion,))
        fila = cursor.fetchone()
        if fila is None or fila[0] == 0:
            return False
        cursor.execute("UPDATE calibracion_pelicula SET activo = 0 WHERE id = ?", (id_calibracion,))
        cursor.execute(f"UPDATE calibracion_pelicula_pieza SET activo = 0 WHERE ref = ?{filtro_activo('calibracion_pelicula_pieza')}", (id_calibracion,))
        detalle = f"id={id_calibracion} ({TEXTO_DE_LA_CALIBRACION.format(lote=fila[1], fecha=fila[2], energia=fila[3])})"
        _registrar_auditoria(usuario, ACCION_ANULAR, TABLA, ref=id_calibracion, detalle=detalle, con=db)
        db.commit()
    return True


# ================================================================================================================================== lecturas

def _a_dict(cursor, fila, columnas_json):
    registro = {d[0]: v for d, v in zip(cursor.description, fila)}
    for c in columnas_json:
        if c in registro and registro[c] is not None:
            registro[c] = json.loads(registro[c])
    return registro


_TODA_LA_CALIBRACION = "id, " + ", ".join(_COLUMNAS_DE_LA_CALIBRACION) + ", activo"          # columnas explicitas (MI0); por nombre, nunca `SELECT *`


def listar():
    """Las calibraciones VIGENTES, sin el ajuste ni las piezas, de la más reciente a la más antigua (por la fecha de irradiación y, en el mismo día, la guardada después). Lee el bloque: filtra la
    vigencia (DA-47)."""
    with Conexion().conectar() as db:
        cursor = db.cursor()
        cursor.execute(f"SELECT id, lote, tipo_pelicula, fecha_irradiacion, acelerador, energia, modelo, version, estado, cadena_de_captura, usuario, fecha_registro, activo "
                       f"FROM calibracion_pelicula WHERE 1=1{filtro_activo('calibracion_pelicula')} ORDER BY DATE(fecha_irradiacion) DESC, id DESC")
        return [_a_dict(cursor, f, ("estado", "cadena_de_captura")) for f in cursor.fetchall()]


def vigentes_validas():
    """Las calibraciones VIGENTES con al menos una capa «válida» (DC5), completas (lo que da `leer`: el ajuste ya convertido de JSON y sus piezas), en el orden de `listar`: la más reciente primero. Es lo
    que leerá `curva_efectiva` (CD.6), que elige por la cadena de captura y la capa. Sale de `listar` (la lectura del bloque, que filtra la vigencia, DA-47) y de `leer` de cada una: sin SQL propio."""
    validas = [f["id"] for f in listar() if any(estado == motor.ESTADO_VALIDA for estado in f["estado"].values())]
    return [r for r in (leer(i) for i in validas) if r is not None]


def leer(id_calibracion):
    """La calibración COMPLETA (todas sus columnas, los JSON ya convertidos, `activo`, y `piezas`: sus filas en el orden del formulario), o None. Lectura de IDENTIDAD (`WHERE id = ?`): no filtra la
    vigencia a propósito (DA-47) -- abrir una calibración anulada o reemplazada debe dar la calibración, no «nada». Sus piezas son las de ESA raíz (`ref` = su id; nunca se insertan piezas bajo un `ref`
    que ya las tiene), así que tampoco se filtran: una calibración anulada se abre con sus piezas. `CurvaDosisError` si el id no es un entero que cabe en la base (CD4-R3-D2); un id válido que no existe da `None`."""
    id_calibracion = _id_de_calibracion(id_calibracion)
    with Conexion().conectar() as db:
        cursor = db.cursor()
        cursor.execute(f"SELECT {_TODA_LA_CALIBRACION} FROM calibracion_pelicula WHERE id = ?", (id_calibracion,))
        fila = cursor.fetchone()
        if fila is None:
            return None
        registro = _a_dict(cursor, fila, _COLUMNAS_JSON_DE_LA_CALIBRACION)
        cursor.execute("SELECT id, ref, orden, dosis_nominal_cgy, dosis_medida_cgy, nombre_archivo, sha256, bytes, formato, bits, dpi_declarado, equipo, fecha_exif, dimensiones_px, "
                       "escaner_declarado, fecha_escaneo, posicion_mm, medida, estado, activo FROM calibracion_pelicula_pieza WHERE ref = ? ORDER BY orden", (id_calibracion,))
        registro["piezas"] = [_a_dict(cursor, f, _COLUMNAS_JSON_DE_LA_PIEZA) for f in cursor.fetchall()]
    return registro


# ================================================================================================================================== recalcular y comparar

def _pieza_desde_la_fila(fila):
    """La `PiezaDeCalibracion` de una pieza guardada, sin su escaneo: lo medido (`medida["pieza"]`), su dosis y su archivo. La netOD y lo que sale del ajuste los vuelve a poner `ajustar`."""
    guardada = fila["medida"]["pieza"]
    capas = {c: {**guardada["capas"][c], "netod": None, "u_netod": None, "dosis_cgy": None, "residuo_pct": None, "en_el_rango": False} for c in CAPAS_DEL_PISO}
    return motor.PiezaDeCalibracion(fila["orden"], float(fila["dosis_nominal_cgy"]), fila["dosis_medida_cgy"], fila["estado"], capas, guardada["posicion_mm"], guardada["fondo_blanco"],
                                    fila["nombre_archivo"] or "", fila["sha256"], guardada["cadena"])


def _ajustar_como_al_guardar(registro, piezas):
    virgen = None if registro["virgen"] is None else referencia_virgen_desde_dict(registro["virgen"])
    curva_guardada = _parametros_de_la_curva(registro["parametros"]["curva"])
    return motor.ajustar(piezas, P=curva_guardada, virgen=virgen, u_dosis_medida_pct=registro["u_dosis_medida_pct"])


def recalcular(registro):
    """Vuelve a ajustar lo guardado (`registro`: lo que devuelve `leer`) -> `Recalculo`. Desde lo medido guardado de cada pieza (sin los escaneos) y, si están TODOS en la carpeta de la calibración y cada uno sigue siendo su huella sha256,
    volviendo a medir cada pieza desde su escaneo con los parámetros de medida GUARDADOS; los dos con los parámetros de la curva, la virgen y la incertidumbre de la dosis GUARDADOS (DA-81: la copia
    guardada manda, nunca lo de hoy). `CurvaDosisError` si lo guardado ya no se puede leer o si una copia de un escaneo existe y no se puede leer, o no se puede ni comprobar (una carpeta sin permiso de recorrido, una carpeta de
    red caída: DP-152): lo ilegible no se confunde con lo que falta (CD4-R3-D4); falta solo lo que no está (o no es un archivo).
    Todo `CurvaDosisError` de `recalcular` sale con el prefijo «lo guardado de la calibración no se puede volver a ajustar:» (el `except` de más abajo envuelve todo `ValueError`, y `CurvaDosisError` lo es), también el de
    la copia que no se puede leer ni comprobar, que ya trae su causa: es el mismo doble prefijo de los rechazos de los parámetros de la curva y la ventana lo dice tal cual (CD4-R2-D1, CD4-R4-D3). Un `registro` que no es
    lo que da `leer` (un escalar o un arreglo de numpy) está fuera de contrato: lanza `IndexError` (CD4-R4-D2)."""
    try:
        piezas = sorted(registro["piezas"], key=lambda f: f["orden"])
        desde_lo_medido = _ajustar_como_al_guardar(registro, [_pieza_desde_la_fila(f) for f in piezas])
        faltan, no_coinciden, datos = [], [], {}
        for f in piezas:
            nombre = _nombre_de_la_copia(f)
            ruta = os.path.join(carpeta_de_los_escaneos(), nombre)
            try:
                estado = os.stat(ruta)
            except (FileNotFoundError, NotADirectoryError):
                faltan.append(nombre)
                continue
            except OSError as error:
                # una carpeta sin permiso de recorrido, una carpeta de red caída (DP-152): no se pudo comprobar, que no es lo mismo que «falta»
                raise CurvaDosisError(f"no se pudo comprobar la copia del escaneo {nombre} junto a la base: {error}") from error
            if not stat.S_ISREG(estado.st_mode):
                # una carpeta donde debía estar la copia: falta la copia
                faltan.append(nombre)
                continue
            try:
                with open(ruta, "rb") as archivo:
                    contenido = archivo.read()
            except OSError as error:
                raise CurvaDosisError(f"no se pudo leer la copia del escaneo {nombre} junto a la base: {error}") from error
            if hashlib.sha256(contenido).hexdigest() == f["sha256"]:
                datos[f["orden"]] = contenido
            else:
                no_coinciden.append(nombre)
        desde_los_escaneos = None
        if not faltan and not no_coinciden:
            medidas = registro["parametros"]["medida"]
            hoy = datetime.now().strftime("%Y-%m-%d")
            vueltas = [motor.pieza_de_calibracion(f["orden"], f["dosis_nominal_cgy"], f["dosis_medida_cgy"],
                                                  medir_pieza_uniforme(datos[f["orden"]], copy.deepcopy(medidas), f["nombre_archivo"], hoy, escala="declarada")) for f in piezas]
            desde_los_escaneos = _ajustar_como_al_guardar(registro, vueltas)
    except (KeyError, TypeError, ValueError) as error:
        raise CurvaDosisError(f"lo guardado de la calibración no se puede volver a ajustar: {error}") from error
    return Recalculo(desde_lo_medido, desde_los_escaneos, tuple(faltan), tuple(no_coinciden))


def _iguales(guardado, recalculado):
    if isinstance(guardado, bool) or isinstance(recalculado, bool):
        return guardado is recalculado
    if isinstance(guardado, numbers.Real) and isinstance(recalculado, numbers.Real):
        return math.isclose(guardado, recalculado, rel_tol=TOLERANCIA_RELATIVA_AL_RECALCULAR, abs_tol=TOLERANCIA_ABSOLUTA_AL_RECALCULAR)
    return guardado == recalculado


def _comparar(guardado, recalculado, camino, encontradas):
    if isinstance(guardado, dict) and isinstance(recalculado, dict):
        for k in sorted(set(guardado) | set(recalculado), key=str):
            if k not in guardado or k not in recalculado:
                encontradas.append(f"{camino} › {k}: {'falta en lo guardado' if k not in guardado else 'falta en lo recalculado'}")
            else:
                _comparar(guardado[k], recalculado[k], f"{camino} › {k}", encontradas)
    elif isinstance(guardado, list) and isinstance(recalculado, list):
        if len(guardado) != len(recalculado):
            encontradas.append(f"{camino}: guardado {len(guardado)} elementos, recalculado {len(recalculado)}")
        for i, (a, b) in enumerate(zip(guardado, recalculado)):
            _comparar(a, b, f"{camino} › {i + 1}", encontradas)
    elif not _iguales(guardado, recalculado):
        encontradas.append(f"{camino}: guardado {_como_texto(guardado)}, recalculado {_como_texto(recalculado)}")


def diferencias(registro, recalculo):
    """Lo recalculado (`recalculo`, de `recalcular`) contra lo guardado (`registro`, de `leer`): una lista de textos, vacía si no hay ninguna diferencia. Compara el ajuste guardado ENTERO (la copia de
    la curva) y el estado de cada capa con la curva rehecha desde lo medido y, si se volvieron a medir los escaneos, también con esa y lo medido de cada pieza. Lo numérico se compara a
    `TOLERANCIA_RELATIVA_AL_RECALCULAR`. Una copia que ya no coincide con su huella es una diferencia (una línea por pieza); un escaneo que falta no lo es (los escaneos no van en el respaldo). Sin símbolos de
    correcto o incorrecto (DA-18)."""
    encontradas = []
    for f in sorted(registro["piezas"], key=lambda f: f["orden"]):
        copia = _nombre_de_la_copia(f)
        if copia in recalculo.escaneos_que_no_coinciden:
            encontradas.append(TEXTO_COPIA_QUE_NO_COINCIDE.format(orden=f["orden"], archivo=f["nombre_archivo"], copia=copia))
    for nombre, curva in (("desde lo medido", recalculo.desde_lo_medido), ("desde los escaneos", recalculo.desde_los_escaneos)):
        if curva is None:
            continue
        _comparar(registro["ajuste"], _json_normal(curva.como_dict()), f"ajuste ({nombre})", encontradas)
        _comparar(registro["estado"], _estado_por_capa(curva), f"estado ({nombre})", encontradas)
    if recalculo.desde_los_escaneos is not None:
        por_orden = {p.orden: p for p in recalculo.desde_los_escaneos.piezas}
        for f in registro["piezas"]:
            p = por_orden.get(f["orden"])
            if p is None:
                encontradas.append(f"la pieza {f['orden']}: no está en lo recalculado")
                continue
            _comparar(f["medida"]["pieza"], _medida_de_la_pieza(p)["pieza"], f"la pieza {f['orden']} (desde su escaneo)", encontradas)
    return encontradas
