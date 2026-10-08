"""GI.6 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, A9): lo que se le dice al fisico cuando un guardado de una prueba de imagen FALLA, con la causa.

Antes el escritor (`guardar_prueba_completa_catphan`) hacia rollback, imprimia el rastro (a una consola que el `.exe` no tiene) y devolvia `None`, y la pantalla decia siempre
«Error al guardar X en la base de datos»: una base sin la columna `error_pct`, un bloqueo real de otro proceso (30 s de congelacion) o un `FOREIGN KEY` eran lo mismo. Ahora el
escritor relanza y la pantalla traduce los casos conocidos con esto -- sin texto crudo de SQLite -- y deja la causa tecnica completa en `error_log.txt`
(`services/registro_errores.py`).

Sin Qt ni BD: la usan la pantalla y las pruebas. Todo mensaje dice QUE no se guardo («No se guardo nada»: el escritor revierte la transaccion entera) y QUE hacer.
"""
import re
from dataclasses import dataclass

from analisisImagenes.catphan.obligatorios import etiqueta_de

CAUSA_SIN_DATOS = "sin_datos"                  # el analisis de esa prueba no entrego nada que guardar
CAUSA_NO_CONVERTIBLES = "no_convertibles"      # lo que entrego no tiene la forma que el guardado espera (un campo vacio donde hacia falta un numero...)

GRAVEDAD_AVISO = "aviso"       # se arregla esperando o repitiendo
GRAVEDAD_ERROR = "error"       # hace falta que alguien intervenga


class CategoriaNoGuardada(Exception):
    """El escritor se niega a dar por guardada una prueba cuyas filas no entraron: antes `guardar_prueba_completa_catphan` ignoraba lo que devolvian los `guardar_*` de cada
    categoria, y una prueba sin filas hijas anulaba la vigente buena y se daba por guardada (GI.1, anotacion de la revision). Las demas pruebas de la llamada tampoco se guardan."""

    def __init__(self, categoria, causa=CAUSA_SIN_DATOS):
        super().__init__(f"{categoria}: {causa}")
        self.categoria = categoria
        self.causa = causa


@dataclass(frozen=True)
class MensajeDeError:
    titulo: str
    texto: str
    gravedad: str
    conocido: bool


def _sujeto(prueba):
    return f"No se pudo guardar «{prueba}»" if prueba else "No se pudo guardar la prueba"


def _coincide(mensaje, *fragmentos):
    return any(f in mensaje for f in fragmentos)


def _detalle(registrado):
    """Donde quedo la causa tecnica. Solo se promete `error_log.txt` si de verdad se pudo escribir (revision de GI.6, P5): con la carpeta sin permiso o el disco lleno el `.exe` no tiene
    consola y no queda rastro alguno, y decir lo contrario deja al fisico sin saber que debe anotar el aviso."""
    return "el detalle quedó en error_log.txt" if registrado else "no se pudo escribir el detalle en error_log.txt; anote este aviso"


def traducir(excepcion, prueba=None, registrado=True) -> MensajeDeError:
    """El mensaje para el fisico de la excepcion `excepcion` ocurrida al guardar la prueba `prueba` (su nombre tal como lo ve, o `None`). `registrado` dice si la causa tecnica pudo
    escribirse en `error_log.txt` (lo que devuelve `registrar_error`). Nunca lanza: una excepcion cualquiera tiene mensaje."""
    if prueba is None and isinstance(excepcion, CategoriaNoGuardada):
        prueba = etiqueta_de(excepcion.categoria)            # «Guardar todos» no sabe cual de las pruebas fallo; la excepcion si
    sujeto = _sujeto(prueba)
    detalle = _detalle(registrado)
    crudo = str(excepcion)
    bajo = crudo.lower()

    if isinstance(excepcion, CategoriaNoGuardada):
        if excepcion.causa == CAUSA_NO_CONVERTIBLES:
            return MensajeDeError(
                "Resultados incompletos",
                f"{sujeto}: los resultados del análisis están incompletos o no tienen la forma esperada y no se pudieron convertir en datos para guardar. No se guardó nada. "
                f"Repita el análisis; si vuelve a pasar, avise al responsable ({detalle}).", GRAVEDAD_ERROR, True)
        return MensajeDeError(
            "Prueba sin datos",
            f"{sujeto}: el análisis no entregó datos que guardar. No se guardó nada. Repita el análisis antes de guardar.", GRAVEDAD_ERROR, True)

    if _coincide(bajo, "database is locked", "database table is locked", "database schema is locked", "database is busy"):
        return MensajeDeError(
            "Base de datos ocupada",
            f"{sujeto}: la base de datos está ocupada por otro proceso. No se guardó nada. Espere unos segundos y repita el guardado.", GRAVEDAD_AVISO, True)

    m = re.search(r"table (\S+) has no column named (\S+)", crudo)
    tabla = columna = None
    if m:
        tabla, columna = m.group(1), m.group(2)
    else:
        m = re.search(r"no such column:\s*(\S+)", crudo, re.IGNORECASE)         # revision de GI.6 (P8): sin los dos puntos y el nombre no hay columna que decir
        if m:
            columna = m.group(1)
    if columna:
        donde = f"a la tabla «{tabla}» de la base de datos le falta la columna «{columna}»" if tabla else f"a la base de datos le falta la columna «{columna}»"
        return MensajeDeError(
            "Falta una columna en la base de datos",
            f"{sujeto}: {donde}. No se guardó nada. La base de datos debe pasarse por la herramienta de migración (migrar_bd_a_estandar) antes de seguir; después, vuelva a abrir la aplicación.",
            GRAVEDAD_ERROR, True)

    m = re.search(r"no such table: (\S+)", crudo)
    if m:
        return MensajeDeError(
            "Falta una tabla en la base de datos",
            f"{sujeto}: a la base de datos le falta la tabla «{m.group(1)}». No se guardó nada. La base de datos debe pasarse por la herramienta de migración (migrar_bd_a_estandar) antes de seguir.",
            GRAVEDAD_ERROR, True)

    if "foreign key constraint failed" in bajo:
        # Revision de GI.6 (P4): SQLite no dice CUAL clave foranea fallo. La del control ya la valida la puerta W1 antes de escribir, de modo que lo mas probable es otro padre (un material, un
        # tipo de prueba, una region que la base no trae sembrados): no se culpa a uno solo.
        return MensajeDeError(
            "Falta un dato relacionado",
            f"{sujeto}: falta un dato del que depende esta prueba en la base de datos (por ejemplo, el control de esta sesión ya no existe). No se guardó nada. "
            f"Cierre el control y ábralo de nuevo; si vuelve a pasar, avise al responsable ({detalle}).", GRAVEDAD_ERROR, True)

    m = re.search(r"UNIQUE constraint failed: (.+)", crudo)
    if m and m.group(1).strip():
        origen = m.group(1).strip()
        if origen.lower().startswith("index"):                       # un indice con EXPRESION no trae «tabla.columna» sino «index 'nombre'»: no se presenta como si fuera una tabla
            nombre = origen.split(None, 1)[1].strip("' ") if len(origen.split(None, 1)) > 1 else ""
            donde = f"la base de datos ya tiene un registro vigente igual (restricción «{nombre}»)" if nombre else "la base de datos ya tiene un registro vigente igual"
        else:
            donde = f"la tabla «{origen.split('.')[0].strip()}» ya tiene un registro vigente igual"
        return MensajeDeError(
            "Registro duplicado",
            f"{sujeto}: {donde}. No se guardó nada. Avise al responsable de la base de datos ({detalle}).", GRAVEDAD_ERROR, True)

    m = re.search(r"NOT NULL constraint failed: (\w+)\.(\w+)", crudo)
    if m:
        return MensajeDeError(
            "Falta un dato obligatorio",
            f"{sujeto}: falta el dato obligatorio «{m.group(2)}» de la tabla «{m.group(1)}». No se guardó nada. Repita el análisis; si vuelve a pasar, avise al responsable ({detalle}).",
            GRAVEDAD_ERROR, True)

    if "check constraint failed" in bajo:
        return MensajeDeError(
            "Dato fuera de lo permitido",
            f"{sujeto}: un valor no cumple lo que la base de datos permite guardar. No se guardó nada. Repita el análisis; si vuelve a pasar, avise al responsable ({detalle}).",
            GRAVEDAD_ERROR, True)

    if _coincide(bajo, "disk i/o error", "unable to open database file", "readonly database", "database or disk is full"):
        return MensajeDeError(
            "No se pudo escribir en la base de datos",
            f"{sujeto}: no se pudo escribir en el archivo de la base de datos (disco, red o permisos). No se guardó nada. Compruebe que la carpeta de la base de datos esté disponible y "
            "que tenga permiso de escritura, y repita el guardado.", GRAVEDAD_ERROR, True)

    if _coincide(bajo, "database disk image is malformed", "file is not a database", "file is encrypted"):
        return MensajeDeError(
            "Base de datos dañada",
            f"{sujeto}: la base de datos parece estar dañada. No se guardó nada. No siga trabajando: avise al responsable y recupere el último respaldo (carpeta respaldos_bd).",
            GRAVEDAD_ERROR, True)

    return MensajeDeError(
        "Error inesperado",
        f"{sujeto} por un error que la aplicación no reconoce ({type(excepcion).__name__}). No se guardó nada. Avise al responsable ({detalle}).", GRAVEDAD_ERROR, False)
