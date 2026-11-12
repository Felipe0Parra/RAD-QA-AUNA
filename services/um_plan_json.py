"""UM.6a (PLAN_CALCULADORA_UM_05-11.md, DC15, DC16): el lector del JSON de un plan. Del ARCHIVO a una `um_motor.Entrada` por campo, o al motivo por el que ese campo no se calcula; y de
cada entrada al resultado del motor (`um_motor.calcular`, la MISMA función de la parte manual), con su error y su estado. Sin Qt, sin base y sin `conection`: los datos del haz de cada campo
llegan por la función que se le pasa a `calcular_plan`.

  - LO QUE NO SE ENTIENDE NO SE IGNORA (H17). Una clave desconocida, dos nombres para lo mismo, lados y mandíbulas a la vez, un solo lado equivalente, una cuña con decimales, una orientación
    rara o un valor que no es del tipo que se espera dejan ESE campo sin calcular, con el motivo. Un archivo que no es un plan (no se lee, mide demasiado, no está en UTF-8, no es JSON, trae
    NaN o Infinity, repite una clave, trae una clave del plan que no se conoce, no trae campos o trae demasiados) se rechaza entero con `PlanInvalido`.
  - Un campo malo no tumba a los demás, tampoco un defecto propio: `calcular_plan` deja el motivo en ese campo.
  - Los nombres que el lector acepta viven en cuatro sitios: `NOMBRES` (los de cada concepto, de un campo o del plan), `IGNORADOS` (lo de un campo que el cálculo no usa), `CLAVES_DEL_PLAN` (las demás
    claves del plan) y las cuatro de las mandíbulas (x1, x2, y1 e y2), escritas en `_mandibulas`: adaptar el lector al JSON real es cambiar esos.
  - El lector no escribe lo que el plan no dice (UM2-D18): sin cuña, o con su factor escrito, la orientación queda en None (el motor no la usa); con cuña de tablas va la del plan, que es
    obligatoria. El centro, el punto y el TF van siempre como número: 0.0, 0.0 y 1.0 si el plan no los dice. Un `null` o un texto vacío valen como no dicho; un 0 escrito es 0.
  - Los rangos no se repiten aquí: los decide el motor. Aquí solo se exige que cada valor sea del tipo que se espera.
  - Lo que el plan escribe llega al motor como se escribió. Los lados y los centros de las mandíbulas se calculan en decimales, con los números tal como están en el archivo, y pasan a `float` una sola vez
    (en coma flotante 0.1 + 5.1 da 5.199999999999999, y el motor, que compara el campo efectivo con las mandíbulas por igualdad exacta, vería láminas donde no las hay). Y un archivo hostil no congela la
    pantalla: un equipo o una energía de más de `MAXIMO_RECONOCIDO` caracteres no se pasa al lector de Eclipse, y lo que un motivo cita va acortado.
  - PRIVACIDAD: los nombres del plan y de los campos solo se devuelven para mostrarlos; la clave «paciente» se acepta y no se lee. Ningún motivo cita un nombre, y lo que un motivo cita del
    archivo (claves, textos) va acortado y en número acotado. Este módulo no escribe nada: ni base, ni archivos, ni consola.
"""
import json
import math
import os
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from services import um_lector_eclipse as lector
from services import um_motor as motor

NOMBRES = {     # concepto -> los nombres con que el JSON lo puede decir (el primero es el del formato propuesto, `EJEMPLO_DE_PLAN`)
    "nombre": ("nombre", "campo", "field_name", "beam_name"),
    "equipo": ("equipo", "maquina", "machine", "treatment_machine"),
    "energia": ("energia", "energy"),
    "tecnica": ("tecnica", "technique"),
    "dosis": ("dosis_cgy", "dosis_campo_cgy", "dose_cgy"),
    "um_planeador": ("um_planeador", "um_eclipse", "mu_eclipse", "planned_mu"),
    "x": ("x_cm",),
    "y": ("y_cm",),
    "mandibulas": ("mandibulas_cm", "jaws_cm"),
    "x_ef": ("x_equivalente_cm",),
    "y_ef": ("y_equivalente_cm",),
    "lado_ef": ("lado_equivalente_cm", "equivalent_square_cm"),
    "ssd": ("ssd_cm",),
    "prof": ("profundidad_cm", "depth_cm"),
    "prof_ef": ("profundidad_efectiva_cm", "effective_depth_cm"),
    "punto_x": ("punto_x_cm",),
    "punto_y": ("punto_y_cm",),
    "oar": ("oar",),
    "cuna": ("cuna_grados", "wedge_deg"),
    "cuna_tipo": ("cuna_tipo", "wedge_type"),
    "cuna_orientacion": ("cuna_orientacion", "wedge_orientation"),
    "wf": ("factor_cuna", "wedge_factor"),
    "tf": ("factor_bandeja", "tray_factor"),
}
IGNORADOS = frozenset({"id", "comentario", "gantry_grados", "colimador_grados", "camilla_grados"})     # de un campo: se sabe que el cálculo no los usa
CLAVES_DEL_PLAN = frozenset({"plan", "paciente", "fecha", "formato", "version", "campos"})          # además de equipo, energía y técnica
DEL_PLAN = ("equipo", "energia", "tecnica")                                                        # los conceptos que el plan da para todos sus campos
CONOCIDAS_DEL_PLAN = CLAVES_DEL_PLAN | {n for concepto in DEL_PLAN for n in NOMBRES[concepto]}
CONOCIDAS_DEL_CAMPO = frozenset(n for nombres in NOMBRES.values() for n in nombres) | IGNORADOS
TECNICAS_QUE_SE_CALCULAN = frozenset({"", "STATIC", "ESTATICO", "ESTATICA", "3D", "3DCRT", "CONFORMAL", "CONFORMADA", "CONFORMADO"})     # sin tildes, espacios, guiones ni «_»
TIPOS_DE_CUNA_FISICA = frozenset({"FISICA", "PHYSICAL", "HARD", "STANDARD"})
TAMANO_MAXIMO_BYTES = 2 * 1024 * 1024      # UM6-D3: un plan real mide unos kB (el de ejemplo, 1.5 [kB]); uno mayor no se lee, y no se congela la pantalla
MAXIMO_DE_CAMPOS = 1000                    # UM6-D3: cada campo se calcula en el hilo de la pantalla (H14, sin hilo); medido en `logs/UM6_prevuelo/`
MAXIMO_CITADO, CITA_COMIENZO, CITA_FINAL = 30, 12, 8      # lo que un motivo cita del archivo: entero hasta 30 caracteres; si no, su comienzo, «…» y su final (como `_citar` de la pantalla)
CLAVES_NOMBRADAS = 5                       # un motivo nombra hasta 5 claves y dice cuántas más hay
MAXIMO_RECONOCIDO = 64                     # UM6-D9 (vetable): un equipo o una energía del archivo de más caracteres no se pasa a `um_lector_eclipse`, y no se reconoce (los reales miden menos de 25)
NO_ES_UN_PLAN = "El archivo no es un plan: debe ser un objeto JSON con la lista «campos»."
# El formato propuesto (DC15). Es lo que muestra «Ver formato» y lo que las pruebas calculan con las tablas reales: un solo texto (UM6-D2).
EJEMPLO_DE_PLAN = """{
  "plan": "Ejemplo de prueba (datos inventados, no es un paciente)",
  "equipo": "Clinac 600",
  "energia": "6 MV",
  "campos": [
    {
      "nombre": "AP abierto, isocéntrico",
      "dosis_cgy": 90.0,
      "um_planeador": 111.0,
      "mandibulas_cm": { "x1": 5.0, "x2": 5.0, "y1": 7.5, "y2": 7.5 },
      "ssd_cm": 90.0,
      "profundidad_cm": 10.0
    },
    {
      "nombre": "PA con láminas",
      "dosis_cgy": 90.0,
      "um_planeador": 114.0,
      "mandibulas_cm": { "x1": 6.0, "x2": 6.0, "y1": 8.0, "y2": 8.0 },
      "x_equivalente_cm": 8.0,
      "y_equivalente_cm": 10.0,
      "ssd_cm": 88.0,
      "profundidad_cm": 12.0,
      "profundidad_efectiva_cm": 10.5
    },
    {
      "nombre": "Lateral con cuña de 15",
      "dosis_cgy": 60.0,
      "um_planeador": 88.0,
      "x_cm": 8.0,
      "y_cm": 12.0,
      "ssd_cm": 92.0,
      "profundidad_cm": 8.0,
      "cuna_grados": 15,
      "cuna_tipo": "fisica",
      "cuna_orientacion": "IN"
    },
    {
      "nombre": "Lateral con cuña de 30, sin factor conocido",
      "dosis_cgy": 60.0,
      "um_planeador": 120.0,
      "x_cm": 8.0,
      "y_cm": 12.0,
      "ssd_cm": 92.0,
      "profundidad_cm": 8.0,
      "cuna_grados": 30,
      "cuna_tipo": "fisica",
      "cuna_orientacion": "IN"
    },
    {
      "nombre": "Arco VMAT",
      "tecnica": "VMAT",
      "dosis_cgy": 100.0,
      "um_planeador": 300.0,
      "x_cm": 10.0,
      "y_cm": 10.0,
      "ssd_cm": 90.0,
      "profundidad_cm": 10.0
    }
  ]
}
"""


class PlanInvalido(ValueError):
    """El archivo entero no se puede leer como un plan; el mensaje dice por qué."""


@dataclass(frozen=True)
class CampoImportado:
    nombre: str         # el del plan, o «Campo N» (N desde 1, su lugar en «campos»): solo para mostrarlo
    equipo: object      # «Clinac 600» o «Clinac iX» (la forma canónica del lector), o None si no se entendió
    energia: object     # «6 MV», o None si no se entendió
    entrada: object     # la `um_motor.Entrada`, o None si el campo no se puede calcular
    problema: object    # el motivo por el que no se calcula, o None


# ---------------------------------------------------------------------------------------------------------------- lo que un motivo cita

def _cita(texto):
    """Un texto del archivo, para citarlo en un motivo: los espacios y saltos de línea seguidos, como un espacio; entero si tiene `MAXIMO_CITADO` caracteres o menos; si no, su comienzo,
    «…» y su final. Un archivo hostil (una clave de un millón de caracteres) no hace un motivo enorme."""
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= MAXIMO_CITADO else texto[:CITA_COMIENZO] + "…" + texto[-CITA_FINAL:]


def _nombrar(claves):
    """Hasta `CLAVES_NOMBRADAS` claves, en orden, citadas, y cuántas más hay."""
    claves = sorted(claves)
    nombradas = ", ".join(f"«{_cita(c)}»" for c in claves[:CLAVES_NOMBRADAS])
    return nombradas + (f" y {len(claves) - CLAVES_NOMBRADAS} más" if len(claves) > CLAVES_NOMBRADAS else "")


def _tipo(valor):
    """Qué es un valor que no es el que se esperaba, en palabras."""
    if isinstance(valor, bool):
        return "un valor verdadero o falso"
    if isinstance(valor, (int, float)):
        return "un número"
    if isinstance(valor, str):
        return f"el texto «{_cita(valor)}»"
    return {list: "una lista", dict: "un objeto"}.get(type(valor), "nulo")


def _mayuscula(texto):
    return texto[:1].upper() + texto[1:]


def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").strip().upper()


def _reconocer(clave_de, texto):
    """La clave que `clave_de` (`um_lector_eclipse.clave_equipo` o `clave_energia`) da a un equipo o una energía del archivo, o None. Un texto de más de `MAXIMO_RECONOCIDO` caracteres no se le pasa: no se
    reconoce (UM6-D9). `clave_energia` retrocede en tiempo cuadrático con una tira de ceros sin unidad (32000 ceros: 10 [s]; 2000 en la energía del plan y 1000 campos: 41 [s]), y la lectura corre en el hilo
    de la pantalla. Todo texto del archivo que llega a ese lector pasa por aquí."""
    return clave_de(texto) if len(texto) <= MAXIMO_RECONOCIDO else None


# ---------------------------------------------------------------------------------------------------------------- el archivo

def _por_que_no_se_lee(fallo):
    if isinstance(fallo, FileNotFoundError):
        return "no existe"
    if isinstance(fallo, IsADirectoryError):
        return "es una carpeta"
    if isinstance(fallo, PermissionError):
        return "no hay permiso para leerlo"
    return f"el sistema no lo dejó leer ({type(fallo).__name__})"


def _megas(n_bytes):
    """Un tamaño en [MB], con las cifras que lo distinguen del tope (`um_motor.cifras`); el tope, tal cual."""
    tope = TAMANO_MAXIMO_BYTES / 1024 ** 2
    return f"{tope:g} [MB]" if n_bytes == TAMANO_MAXIMO_BYTES else f"{motor.cifras(n_bytes / 1024 ** 2, tope, 1)} [MB]"


def leer_archivo(ruta):
    """El texto del archivo `ruta`, o `PlanInvalido` con el motivo: no se puede abrir, mide más de `TAMANO_MAXIMO_BYTES` (se mira su tamaño ANTES de leerlo) o no está en UTF-8."""
    try:
        tamano = os.path.getsize(ruta)
        if tamano > TAMANO_MAXIMO_BYTES:
            raise PlanInvalido(f"El archivo mide {_megas(tamano)}: un plan no pasa de {_megas(TAMANO_MAXIMO_BYTES)}, y uno así no se lee.")
        with open(ruta, "rb") as archivo:
            contenido = archivo.read(TAMANO_MAXIMO_BYTES + 1)      # si creció después de mirar su tamaño, se lee solo hasta pasar el tope
    except OSError as fallo:
        raise PlanInvalido(f"No se pudo leer el archivo: {_por_que_no_se_lee(fallo)}.") from fallo
    return texto_del_archivo(contenido)


def texto_del_archivo(contenido):
    """El texto de los bytes de un archivo, o `PlanInvalido`: más de `TAMANO_MAXIMO_BYTES`, vacío, UTF-16 o binario (lleva bytes nulos) o un byte que no es UTF-8. UTF-8 con BOM vale."""
    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise PlanInvalido(f"El archivo mide más de {_megas(TAMANO_MAXIMO_BYTES)}: un plan no pasa de eso, y uno así no se lee.")
    if contenido.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in contenido:
        raise PlanInvalido("El archivo no está en UTF-8: parece UTF-16 o un archivo binario. Guárdelo como UTF-8.")
    try:
        texto = contenido.decode("utf-8")      # no `utf-8-sig`: con él el byte de un fallo se cuenta desde DESPUÉS del BOM, y el motivo señalaba uno tres lugares antes del verdadero
    except UnicodeDecodeError as fallo:
        raise PlanInvalido(f"El archivo no está en UTF-8: el byte {fallo.start + 1} no se entiende. Guárdelo como UTF-8.") from fallo
    return texto[1:] if texto.startswith("\ufeff") else texto      # el BOM no es parte del plan


# ---------------------------------------------------------------------------------------------------------------- el JSON

def _sin_no_finitos(constante):
    raise PlanInvalido(f"El archivo trae el valor {constante}, que no es un número: un plan solo lleva números finitos.")


def _sin_repetidas(pares):
    """Una clave repetida en un mismo objeto rechaza el archivo: `json` se quedaría con la última en silencio."""
    repetidas = [clave for clave, veces in Counter(clave for clave, _ in pares).items() if veces > 1]
    if repetidas:
        raise PlanInvalido(f"El archivo repite {'la clave' if len(repetidas) == 1 else 'las claves'} {_nombrar(repetidas)} dentro de un mismo objeto: no se sabe cuál vale.")
    return dict(pares)


def leer_json(texto):
    """El objeto del plan, o `PlanInvalido`: vacío, no es JSON (dice la línea y la columna), NaN o Infinity, una clave repetida, demasiado anidado, un entero de más de 4300 cifras, no es un
    objeto con la lista «campos», sin campos o con más de `MAXIMO_DE_CAMPOS`, o una clave del plan que no se conoce."""
    if not texto.strip():
        raise PlanInvalido("El archivo está vacío.")
    try:
        datos = json.loads(texto, parse_constant=_sin_no_finitos, object_pairs_hook=_sin_repetidas)
    except PlanInvalido:
        raise
    except json.JSONDecodeError as fallo:
        raise PlanInvalido(f"{NO_ES_UN_PLAN} No es un JSON válido: falla en la línea {fallo.lineno}, columna {fallo.colno}.") from fallo
    except RecursionError as fallo:
        raise PlanInvalido(f"{NO_ES_UN_PLAN} Anida demasiadas listas u objetos, uno dentro de otro.") from fallo
    except ValueError as fallo:          # un entero de más cifras de las que Python convierte
        raise PlanInvalido(f"{NO_ES_UN_PLAN} Trae un número de demasiadas cifras.") from fallo
    if not isinstance(datos, dict) or "campos" not in datos:
        raise PlanInvalido(NO_ES_UN_PLAN)
    if not isinstance(datos["campos"], list):
        raise PlanInvalido(f"La clave «campos» del plan debe ser una lista, con un objeto por campo, y es {_tipo(datos['campos'])}.")
    if not datos["campos"]:
        raise PlanInvalido("El plan no trae ningún campo: la lista «campos» está vacía.")
    if len(datos["campos"]) > MAXIMO_DE_CAMPOS:
        raise PlanInvalido(f"El plan trae {len(datos['campos'])} campos: esta calculadora lee hasta {MAXIMO_DE_CAMPOS} por archivo.")
    desconocidas = set(datos) - CONOCIDAS_DEL_PLAN
    if desconocidas:
        raise PlanInvalido(f"El plan trae claves que este lector no conoce: {_nombrar(desconocidas)}.")
    return datos


# ---------------------------------------------------------------------------------------------------------------- los valores de un campo

def _valor(objeto, concepto):
    """El valor de un concepto, sea cual sea su nombre (None si no está o es `null`). Dos nombres para lo mismo son un error, aunque digan lo mismo."""
    presentes = [n for n in NOMBRES[concepto] if n in objeto]
    if len(presentes) > 1:
        raise ValueError(f"Trae dos nombres para lo mismo: {_nombrar(presentes)}")
    return objeto[presentes[0]] if presentes else None


def _texto(objeto, concepto, que):
    """Un texto, o None si no está, es `null` o está vacío. Otra cosa (un número, una lista) no se convierte: es un error."""
    valor = _valor(objeto, concepto)
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise ValueError(f"{_mayuscula(que)} debe ser un texto y es {_tipo(valor)}")
    return valor.strip() or None


def _a_numero(valor, que):
    """Un número de verdad (ni un texto, ni verdadero o falso), como float. Si es posible o no lo decide el motor: los rangos están en un solo sitio."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"{_mayuscula(que)} debe ser un número y es {_tipo(valor)}")
    try:
        numero = float(valor)
    except OverflowError as fallo:
        raise ValueError(f"{_mayuscula(que)} es un número demasiado grande") from fallo
    if not math.isfinite(numero):      # 1e999 se lee como infinito
        raise ValueError(f"{_mayuscula(que)} es un número demasiado grande")
    return numero


def _numero(campo, concepto, que, obligatorio=True):
    valor = _valor(campo, concepto)
    if valor is None:
        if obligatorio:
            raise ValueError(f"Falta {que}")
        return None
    return _a_numero(valor, que)


def _decimal(numero):
    """Un número del archivo tal como se escribió: el decimal más corto que da ese `float` (`repr`). Sumar o restar `float` suma lo que cada uno aproxima, no lo escrito: 0.1 + 5.1 da 5.199999999999999."""
    return Decimal(repr(numero))


def _mandibulas(campo):
    """(X, Y, centro X, centro Y). x1, x2, y1 e y2 se miden desde el eje, positivos hacia el lado abierto, como los muestra Eclipse (DC15). Los lados y los centros se calculan con lo escrito, en
    decimales, y pasan a `float` una sola vez: son los números que el físico escribe en el formulario (el motor compara el campo efectivo con las mandíbulas por igualdad exacta)."""
    mandibulas = _valor(campo, "mandibulas")
    if mandibulas is None:
        return _numero(campo, "x", "el lado X"), _numero(campo, "y", "el lado Y"), 0.0, 0.0
    if _valor(campo, "x") is not None or _valor(campo, "y") is not None:
        raise ValueError("Trae a la vez las mandíbulas y los lados X e Y")
    if not isinstance(mandibulas, dict) or set(mandibulas) != {"x1", "x2", "y1", "y2"}:
        raise ValueError("Las mandíbulas deben traer exactamente x1, x2, y1 e y2")
    x1, x2, y1, y2 = (_decimal(_a_numero(mandibulas[k], f"la mandíbula {k}")) for k in ("x1", "x2", "y1", "y2"))
    if x1 + x2 <= 0 or y1 + y2 <= 0:
        raise ValueError("Las mandíbulas no dejan un campo abierto: x1, x2, y1 e y2 van desde el eje, positivos hacia el lado abierto")
    return float(x1 + x2), float(y1 + y2), float((x2 - x1) / 2), float((y2 - y1) / 2)


def _equivalente(campo):
    """(X, Y) del campo equivalente, o (None, None): el de las mandíbulas."""
    lado = _numero(campo, "lado_ef", "el lado equivalente", obligatorio=False)
    x_ef = _numero(campo, "x_ef", "el lado X equivalente", obligatorio=False)
    y_ef = _numero(campo, "y_ef", "el lado Y equivalente", obligatorio=False)
    if lado is not None:
        if x_ef is not None or y_ef is not None:
            raise ValueError("Trae a la vez un lado equivalente y los lados X e Y equivalentes")
        return lado, lado
    if (x_ef is None) != (y_ef is None):
        raise ValueError("Trae un solo lado equivalente: faltan X o Y")
    return x_ef, y_ef


def _cuna(campo):
    """(ángulo, orientación, factor escrito). Lo que se diga de una cuña exige su ángulo; una cuña sin su factor escrito exige el tipo físico y la orientación (nada se supone); con el
    factor escrito, ni el tipo ni la orientación pesan y la orientación no se pasa (UM2-D18)."""
    angulo = _numero(campo, "cuna", "el ángulo de la cuña", obligatorio=False)
    tipo = _texto(campo, "cuna_tipo", "el tipo de cuña")
    orientacion = _texto(campo, "cuna_orientacion", "la orientación de la cuña")
    wf = _numero(campo, "wf", "el factor de cuña", obligatorio=False)
    if not angulo:
        if tipo is not None or orientacion is not None or wf is not None:
            raise ValueError("Trae datos de cuña sin su ángulo («cuna_grados»): un campo así no se calcula como abierto")
        return None, None, None
    if angulo < 0 or angulo != int(angulo):
        raise ValueError(f"El ángulo de la cuña debe ser un número entero de grados, mayor que 0, y es {angulo:g}")
    angulo = int(angulo)
    if wf is not None:
        return angulo, None, wf
    if tipo is None or _sin_tildes(tipo) not in TIPOS_DE_CUNA_FISICA:
        dice = "" if tipo is None else f", y dice «{_cita(tipo)}»"
        raise ValueError(f"Una cuña sin su factor escrito («factor_cuna») debe ser física: el tipo de cuña («cuna_tipo») debe decir «fisica»{dice}. Una cuña dinámica no tiene "
                         "tablas y necesita su factor")
    if orientacion is None or _sin_tildes(orientacion) not in motor.ORIENTACIONES:
        dice = "falta" if orientacion is None else f"«{_cita(orientacion)}» no es una de las cuatro"
        raise ValueError(f"La orientación de la cuña ({dice}) debe ser {', '.join(motor.ORIENTACIONES[:-1])} o {motor.ORIENTACIONES[-1]}")
    return angulo, _sin_tildes(orientacion), None


def _entrada(campo):
    x, y, centro_x, centro_y = _mandibulas(campo)
    x_ef, y_ef = _equivalente(campo)
    cuna, orientacion, wf = _cuna(campo)
    tf = _numero(campo, "tf", "el factor de bandeja", obligatorio=False)
    punto_x = _numero(campo, "punto_x", "la posición X del punto", obligatorio=False)
    punto_y = _numero(campo, "punto_y", "la posición Y del punto", obligatorio=False)
    return motor.Entrada(
        dosis=_numero(campo, "dosis", "la dosis del campo"), x=x, y=y, ssd=_numero(campo, "ssd", "la SSD"), prof=_numero(campo, "prof", "la profundidad"), x_ef=x_ef, y_ef=y_ef,
        prof_ef=_numero(campo, "prof_ef", "la profundidad efectiva", obligatorio=False), centro_x=centro_x, centro_y=centro_y,
        punto_x=0.0 if punto_x is None else punto_x, punto_y=0.0 if punto_y is None else punto_y, oar_manual=_numero(campo, "oar", "el OAR", obligatorio=False),
        cuna=cuna, cuna_orientacion=orientacion, wf_manual=wf, tf=1.0 if tf is None else tf, um_planeador=_numero(campo, "um_planeador", "las UM de Eclipse", obligatorio=False))


# ---------------------------------------------------------------------------------------------------------------- el plan

def _del_plan(datos):
    """El nombre del plan y el equipo, la energía y la técnica que da para todos sus campos (textos o None), o `PlanInvalido`."""
    nombre = datos.get("plan")
    if nombre is not None and not isinstance(nombre, str):
        raise PlanInvalido(f"El nombre del plan («plan») debe ser un texto y es {_tipo(nombre)}.")
    try:
        equipo, energia, tecnica = (_texto(datos, c, q) for c, q in zip(DEL_PLAN, ("el equipo del plan", "la energía del plan", "la técnica del plan")))
    except ValueError as fallo:
        raise PlanInvalido(f"{fallo} (en el plan, fuera de «campos»).") from fallo
    return nombre or "", equipo, energia, tecnica


def leer_plan(texto):
    """(nombre del plan, [CampoImportado], uno por campo y en su orden). `PlanInvalido` solo si el archivo entero no se entiende. El equipo y la energía de un campo mandan sobre los del
    plan; la técnica también. Se reconocen con `um_lector_eclipse.clave_equipo` y `clave_energia`, por `_reconocer` (coincidencia exacta: «Clinac 2600» o un 6 sin unidad no pasan, DC15)."""
    datos = leer_json(texto)
    nombre_del_plan, equipo_del_plan, energia_del_plan, tecnica_del_plan = _del_plan(datos)
    campos = []
    for numero, campo in enumerate(datos["campos"], start=1):
        nombre, equipo, energia = f"Campo {numero}", None, None
        try:
            if not isinstance(campo, dict):
                raise ValueError(f"No es un objeto con los datos de un campo: es {_tipo(campo)}")
            nombre = _texto(campo, "nombre", "el nombre del campo") or nombre
            desconocidas = set(campo) - CONOCIDAS_DEL_CAMPO
            if desconocidas:
                raise ValueError(f"Trae claves que este lector no conoce: {_nombrar(desconocidas)}")
            dicho = _texto(campo, "equipo", "el equipo") or equipo_del_plan
            if dicho is None:
                raise ValueError("Falta el equipo: ni el campo ni el plan lo dicen")
            equipo = _reconocer(lector.clave_equipo, dicho)
            if equipo is None:
                raise ValueError(f"El equipo «{_cita(dicho)}» no es uno de esta calculadora: el Clinac 600 o el Clinac iX")
            dicha = _texto(campo, "energia", "la energía") or energia_del_plan
            if dicha is None:
                raise ValueError("Falta la energía: ni el campo ni el plan la dicen")
            energia = _reconocer(lector.clave_energia, dicha)
            if energia is None:
                raise ValueError(f"La energía «{_cita(dicha)}» no se reconoce: debe ser de fotones en MV, como 6X o 6 MV")
            tecnica = _texto(campo, "tecnica", "la técnica") or tecnica_del_plan or ""
            if re.sub(r"[\s_-]", "", _sin_tildes(tecnica)) not in TECNICAS_QUE_SE_CALCULAN:
                raise ValueError(f"La técnica «{_cita(tecnica)}» no se reconoce como un campo estático: la ecuación 3 de la TG-71 no cubre IMRT ni VMAT, y este campo no se calcula")
            campos.append(CampoImportado(nombre, equipo, energia, _entrada(campo), None))
        except ValueError as fallo:
            campos.append(CampoImportado(nombre, equipo, energia, None, str(fallo)))
    return nombre_del_plan, campos


def _inesperado(fallo):
    return f"El cálculo falló por un error inesperado ({type(fallo).__name__}: {_cita(fallo)}). Avise a quien mantiene la app."


def _haz(datos_de, equipo, energia):
    """(datos del haz, None) o (None, motivo)."""
    try:
        datos = datos_de(equipo, energia)
    except motor.NoCalculable as fallo:
        return None, str(fallo)
    except Exception as fallo:   # noqa: BLE001 -- un fallo al traer las tablas deja sin número a los campos de ese haz, con su motivo, y no a los demás
        return None, _inesperado(fallo)
    if datos is None:
        return None, f"No hay tablas cargadas del {equipo}, {energia}: sin ellas este campo no se calcula"
    return datos, None


def calcular_plan(campos, datos_de, dentro=motor.TOLERANCIA_DENTRO_PCT, fuera=motor.TOLERANCIA_FUERA_PCT):
    """[(campo, `um_motor.Resultado` o None, motivo o None)], uno por campo y en su orden. `datos_de(equipo, energia)` da los `um_motor.DatosHaz` de ese haz, None si no hay tablas cargadas,
    o lanza `um_motor.NoCalculable` con el motivo. Se llama UNA vez por haz en cada plan: todos los campos de un haz se calculan con las mismas tablas. Un fallo inesperado (del motor o de
    `datos_de`) queda en su campo, o en los de su haz, con su motivo, y no tumba a los demás."""
    haces, salida = {}, []
    for campo in campos:
        if campo.entrada is None:
            salida.append((campo, None, campo.problema))
            continue
        clave = (campo.equipo, campo.energia)
        if clave not in haces:
            haces[clave] = _haz(datos_de, *clave)
        datos, motivo = haces[clave]
        if datos is None:
            salida.append((campo, None, motivo))
            continue
        try:
            salida.append((campo, motor.calcular(datos, campo.entrada, dentro, fuera), None))
        except motor.NoCalculable as fallo:
            salida.append((campo, None, str(fallo)))
        except Exception as fallo:   # noqa: BLE001 -- un defecto propio tampoco tumba a los demás campos
            salida.append((campo, None, _inesperado(fallo)))
    return salida
