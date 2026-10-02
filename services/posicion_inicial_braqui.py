"""PI.3 (PLAN_POSICION_INICIAL_BRAQUI_01-10.md, DA-82): la ÚNICA puerta a la tabla `braqui_posicion_inicial` y la única
regla de vigencia de la prueba de posición inicial de la fuente de braquiterapia.

Sin ella, la página tendría SQL propio y los dos PDF (diario y mensual) tendrían cada uno su búsqueda de "la fuente en
uso" y su texto: tres definiciones del mismo dato y dos de la misma regla. Aquí viven: guardar y anular (todo o nada, con
su fila de auditoría en la misma transacción, DA-52), listar y leer, la regla de qué prueba vale en una fecha, el cambio
de fuente que se propone por defecto y el texto breve que imprimen la tabla de registros y los PDF.

LA REGLA DE VIGENCIA (§0.2 del plan, `posicion_inicial_para`). La prueba pertenece a un CAMBIO DE FUENTE y vale lo que dura
la fuente: para una fecha D (la del diario, o la de la calibración del mensual) se busca PRIMERO el cambio de fuente
vigente más reciente con fecha <= D (`TipoCalibracion`, `tipo = 'Cambio de fuente'`, con `DATE()` legible) y DESPUÉS la
prueba vigente guardada con la fecha de ESE cambio. Nunca "la prueba más reciente <= D": eso daría la prueba de la fuente
anterior el día en que entra la nueva. En el mensual, además, la serie de la calibración debe ser la que la prueba copió
al guardarse (DD8): la serie cambió el 2025-12-29 SIN un registro "Cambio de fuente" y, solo por fecha, la posición de una
fuente saldría en los mensuales de otra. El enlace es por la FECHA y no por `id` porque reguardar un cambio de fuente
anula e inserta (`id` nuevo, misma fecha): un `id` dejaría huérfana la prueba al primer reguardado.

DOS LIMITACIONES QUE EL PLAN ACEPTA, MEDIDAS Y FIJADAS CON PRUEBA (revisión de Opus del 02-10): (1) un cambio de fuente
ANULADO sin reguardar hace que la regla caiga al cambio anterior: el diario (que no guarda serie) imprimiría la prueba de la
fuente anterior; el mensual se salva por DD8; (2) el día del cambio la regla usa `DATE()` (todo el día es de la fuente
nueva) mientras la actividad esperada del diario compara fechas con hora: ese día pueden convivir dos "fuente en uso" en
un mismo PDF (no se toca braquiterapia).

Reglas de este servicio, cada una con su motivo:
  - `guardar` ANALIZA él mismo desde los bytes y los puntos (no recibe un `resultado` ajeno): nada garantiza que un
    resultado recibido sea el de esa imagen, y guardar un análisis viejo contra una imagen nueva es la clase de `IM3`/
    `DA-65`. De ese análisis salen `dpi`, parámetros, versión, md5 y tolerancia: una sola fuente para el veredicto.
  - Lo que se guarda sale de `motor.valores_medidos` (px y mm del gris y de cada capa, la incertidumbre): este módulo
    nunca recalcula `px x escala` ni suma incertidumbres.
  - La fecha se normaliza SIEMPRE a 'yyyy-MM-dd' (`fecha_iso`): la clave del índice único es la fecha cruda, y guardar
    '2026-06-26 11:42:13' y luego '2026-06-26' dejaría dos pruebas vigentes del mismo cambio.
  - `reemplazar=False` por omisión: con una prueba vigente para esa fecha, `guardar` RECHAZA; la confirmación del físico
    ("¿reemplazarla?") es de la página, que pasa `reemplazar=True` después del "Sí".
  - `anular` va por identidad (`WHERE id = ?`), sin el `AND` de vigencia de `sql_anular_bloque`: ese helper es para claves
    de bloque, y sobre una lectura de identidad el filtro convierte "la fila que pediste" en "nada" (DA-47, tripwire RT1).
  - El permiso de anular NO se comprueba aquí: es del diálogo de la app (`DialogAdminPermisoEliminar`, DA-01), igual que
    `anular_fila`; la página lo pide antes de llamar (PI.4).
  - Texto: el desfase que imprime `texto_breve` es el FÍSICO cuando se conoce el lado del tránsito (negativo = antes de
    la marca). Con el de la imagen, la misma fuente saldría con signos distintos según cómo se colocó la película (V4
    dentro de un PDF firmado).

Sin Qt. Lecturas con `{filtro_activo(...)}` dentro del f-string (Trampa 6: AN1/ES1/RT1 solo lo reconocen así)."""
import hashlib
import json
import math
import re
from datetime import date, datetime

from analisisImagenes import posicion_inicial_braqui as motor
from data.ManejoDatos.conection import Conexion
from services.anulacion import filtro_activo, reemplazar_bloque
from services.audit_minimo import (ACCION_ANULAR, ACCION_GUARDAR, ACCION_REEMPLAZO,
                                   registrar as _registrar_auditoria)

TABLA = "braqui_posicion_inicial"

# Lo que escribe `braq_mensual._tipo_calibracion_seleccionado` para el botón "Cambio de Fuente" (una prueba ata las dos
# cadenas). `TipoCalibracion.tipo` está declarada REAL pero guarda texto: `tipo = ?` con un parámetro de texto funciona
# (SQLite aplica afinidad numérica al parámetro, no puede convertirlo y compara como texto).
TIPO_CAMBIO_DE_FUENTE = "Cambio de fuente"

DIAS_PARA_PROPONER = 7      # DD7: el cambio de fuente por defecto, solo si está a 7 días o menos de la fecha del escaneo

# Las columnas que se piden al leer (todas menos `imagen` y `activo`): las claves del dict salen del propio SELECT
# (`cursor.description`), no de una segunda lista que pudiera desordenarse.
_COLUMNAS_SQL = (
    "id, fecha, serie_fuente, user, imagen_nombre, imagen_md5, dpi, tamano_pixel_mm, puntos, parametros, "
    "version_algoritmo, estado_gris, desfase_gris_px, desfase_gris_mm, incertidumbre_gris_px, dispersion_gris_px, "
    "filas_gris, estado_r, desfase_r_px, desfase_r_mm, estado_g, desfase_g_px, desfase_g_mm, estado_b, desfase_b_px, "
    "desfase_b_mm, lado_transito, tolerancia_mm, observaciones")

# Lo que se inserta, en este orden (MI0: columnas explícitas). Los 17 valores del motor entran por su nombre.
_COLUMNAS_INSERT = (
    "fecha", "serie_fuente", "user", "imagen", "imagen_nombre", "imagen_md5", "dpi", "puntos", "parametros",
    "version_algoritmo", "tolerancia_mm", "observaciones",
    "tamano_pixel_mm", "lado_transito",
    "estado_gris", "desfase_gris_px", "desfase_gris_mm", "incertidumbre_gris_px", "dispersion_gris_px", "filas_gris",
    "estado_r", "desfase_r_px", "desfase_r_mm", "estado_g", "desfase_g_px", "desfase_g_mm",
    "estado_b", "desfase_b_px", "desfase_b_mm")
_SQL_INSERT = (f"INSERT INTO braqui_posicion_inicial ({', '.join(_COLUMNAS_INSERT)}) "
               f"VALUES ({', '.join('?' * len(_COLUMNAS_INSERT))})")


class PosicionInicialError(ValueError):
    """Lo que el servicio rechaza ANTES de escribir nada."""


class FechaSinCambioDeFuente(PosicionInicialError):
    """La fecha no es la de un cambio de fuente vigente (la prueba pertenece a un cambio de fuente)."""


class PruebaYaGuardada(PosicionInicialError):
    """Ya hay una prueba vigente para ese cambio de fuente y no se pidió reemplazarla."""


class _SinFiltroDeSerie:
    def __repr__(self):
        return "SIN_FILTRO_DE_SERIE"


# `posicion_inicial_para(fecha)` (el diario, que no guarda serie) frente a `posicion_inicial_para(fecha, serie=...)` (el
# mensual): una serie `None` o vacía en el mensual NO es "sin filtro", es "no se puede comprobar" y da `None` (QtSql entrega
# un NULL como '').
SIN_FILTRO_DE_SERIE = _SinFiltroDeSerie()

_RE_FECHA = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?$")


def fecha_iso(valor):
    """'yyyy-MM-dd' de lo que sea una fecha de verdad, o None. Acepta `date`, `datetime` y el texto ISO con o sin hora
    ('2026-06-26', '2026-06-26 11:42:13'). Rechaza lo que `fromisoformat` acepta y el `DATE()` de SQLite vuelve NULL
    ('20260626', '2026-W26-5'), lo que ninguna otra parte lee ('27-09-2025') y los días que no existen. El único
    normalizador de fechas del servicio: guardar, la regla, `existe_vigente` y el cambio de fuente por defecto lo usan, y
    a SQL solo llega el valor ya normalizado."""
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, str):
        coincidencia = _RE_FECHA.match(valor.strip())
        if coincidencia:
            try:
                return date(int(coincidencia.group(1)), int(coincidencia.group(2)), int(coincidencia.group(3))).isoformat()
            except ValueError:
                return None
    return None


def _serie(valor):
    """La serie sin espacios sobrantes, o None si falta. Es lo único que se normaliza de una serie: dos series que difieren
    en algo más NO son la misma fuente (DD8 es conservador)."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _a_dict(cursor, fila):
    """{columna: valor} con los nombres que trae el propio SELECT."""
    return {descripcion[0]: valor for descripcion, valor in zip(cursor.description, fila)}


def _filas_de_cambio_de_fuente(cursor):
    """[(fecha 'yyyy-MM-dd', serie | None)] de los "Cambio de fuente" VIGENTES con fecha legible (`DATE()` no NULL), del más
    reciente al más antiguo; un mismo día, el de `id` mayor primero. Es la ÚNICA lectura de `TipoCalibracion` de este
    servicio: la usan el listado de cambios, la regla de vigencia, el indicador de `listar` y la validación de `guardar`,
    así que no pueden discrepar. Solo trae dos filas de un mismo día si falta el índice `(DATE(fecha), tipo)` de EB6."""
    cursor.execute(
        "SELECT DATE(fecha), serie FROM TipoCalibracion WHERE tipo = ? AND DATE(fecha) IS NOT NULL"
        f"{filtro_activo('TipoCalibracion')} ORDER BY DATE(fecha) DESC, id DESC",
        (TIPO_CAMBIO_DE_FUENTE,))
    return [(fecha, _serie(serie)) for fecha, serie in cursor.fetchall()]


def _vigente_por_fecha(cursor, fecha):
    """La prueba VIGENTE guardada con esa fecha (sin la imagen), como dict, o None. La comparten `existe_vigente`, la regla
    y `guardar` (dentro de su transacción)."""
    cursor.execute(
        f"SELECT {_COLUMNAS_SQL} FROM braqui_posicion_inicial WHERE fecha = ?"
        f"{filtro_activo('braqui_posicion_inicial')} ORDER BY id DESC",
        (fecha,))
    fila = cursor.fetchone()
    return _a_dict(cursor, fila) if fila is not None else None


def cambios_de_fuente():
    """[(fecha 'yyyy-MM-dd', serie | None)] de los cambios de fuente vigentes, del más reciente al más antiguo: lo que
    ofrece el selector de la página. Un cambio de fuente con la fecha ilegible (`27-09-2025`) no entra: no se corrige,
    queda fuera."""
    with Conexion().conectar() as db:
        filas = _filas_de_cambio_de_fuente(db.cursor())
    vistas, resultado = set(), []
    for fecha, serie in filas:
        if fecha not in vistas:
            vistas.add(fecha)
            resultado.append((fecha, serie))
    return resultado


def cambio_de_fuente_por_defecto(fecha_escaneo=None, hoy=None):
    """DD7: el cambio de fuente más cercano a la fecha del escaneo (la que el escáner escribe en la imagen; sin ella, hoy),
    SOLO si está a 7 días o menos (inclusive); a igual distancia, el ANTERIOR. Si no hay ninguno cerca, o la fecha del
    escaneo no es una fecha, None: el selector queda sin elegir y se escoge a mano (sin esto, una película escaneada meses
    después se pegaría sola a la fuente anterior y ese error duraría meses en todos los PDF). La distancia es simétrica
    (un cambio de fuente posterior al escaneo también cuenta). Devuelve `(fecha, serie)` o None."""
    if fecha_escaneo is None:
        fecha_escaneo = hoy if hoy is not None else date.today()
    referencia = fecha_iso(fecha_escaneo)
    if referencia is None:
        return None
    base = date.fromisoformat(referencia)
    candidatos = [(abs((date.fromisoformat(fecha) - base).days), fecha, serie) for fecha, serie in cambios_de_fuente()]
    if not candidatos:
        return None
    distancia, fecha, serie = min(candidatos, key=lambda c: (c[0], c[1]))
    return (fecha, serie) if distancia <= DIAS_PARA_PROPONER else None


def existe_vigente(fecha):
    """True si hay una prueba vigente guardada con esa fecha (la del cambio de fuente)."""
    dia = fecha_iso(fecha)
    if dia is None:
        return False
    with Conexion().conectar() as db:
        return _vigente_por_fecha(db.cursor(), dia) is not None


def posicion_inicial_para(fecha, serie=SIN_FILTRO_DE_SERIE):
    """LA regla de vigencia (§0.2 del plan): la prueba que vale en `fecha`, como dict sin la imagen (lo que `texto_breve`
    consume), o None. Dos pasos obligatorios: el cambio de fuente vigente más reciente con fecha <= `fecha` y, de ese, la
    prueba vigente guardada con su fecha. Con `serie` (el mensual, DD8) la prueba debe haber copiado esa misma serie; una
    serie None o vacía da None. `fecha` que no es una fecha: None (un PDF no debe reventar ni adivinar)."""
    dia = fecha_iso(fecha)
    if dia is None:
        return None
    pedida = None
    if serie is not SIN_FILTRO_DE_SERIE:
        pedida = _serie(serie)
        if pedida is None:
            return None
    with Conexion().conectar() as db:
        cursor = db.cursor()
        cambio = next((f for f, _ in _filas_de_cambio_de_fuente(cursor) if f <= dia), None)
        prueba = _vigente_por_fecha(cursor, cambio) if cambio is not None else None
    if prueba is None:
        return None
    if serie is not SIN_FILTRO_DE_SERIE and _serie(prueba["serie_fuente"]) != pedida:
        return None
    return prueba


def listar():
    """Las pruebas VIGENTES, sin la imagen, de la más reciente a la más antigua. Cada fila trae además
    `cambio_de_fuente_vigente` (False si su cambio de fuente ya no existe vigente: la prueba se conserva pero no sale en
    ningún PDF), calculado con la misma lectura que la regla: si lo calculara la página serían dos definiciones."""
    with Conexion().conectar() as db:
        cursor = db.cursor()
        cursor.execute(
            f"SELECT {_COLUMNAS_SQL} FROM braqui_posicion_inicial WHERE 1=1{filtro_activo('braqui_posicion_inicial')} "
            "ORDER BY fecha DESC, id DESC")
        filas = [_a_dict(cursor, fila) for fila in cursor.fetchall()]
        vigentes = {fecha for fecha, _ in _filas_de_cambio_de_fuente(cursor)}
    for fila in filas:
        fila["cambio_de_fuente_vigente"] = fila["fecha"] in vigentes
    return filas


def leer(id_registro):
    """La fila COMPLETA (con los bytes de la imagen y con `activo`) o None. Lectura de IDENTIDAD (`WHERE id = ?`): no filtra
    la vigencia a propósito (DA-47) -- abrir un registro anulado debe dar la fila, no "nada"."""
    with Conexion().conectar() as db:
        cursor = db.cursor()
        cursor.execute(f"SELECT {_COLUMNAS_SQL}, imagen, activo FROM braqui_posicion_inicial WHERE id = ?", (id_registro,))
        fila = cursor.fetchone()
        return _a_dict(cursor, fila) if fila is not None else None


def _puntos_validos(puntos):
    """[[x1, y1], [x2, y2]] en `float`: dos pares de números finitos y distintos (un `np.int64` no entra a `json.dumps`)."""
    try:
        (x0, y0), (x1, y1) = puntos
        pares = [[float(x0), float(y0)], [float(x1), float(y1)]]
    except (TypeError, ValueError):
        raise PosicionInicialError("los puntos deben ser dos pares (x, y)") from None
    if not all(math.isfinite(v) for par in pares for v in par):
        raise PosicionInicialError("los puntos deben ser numeros finitos")
    if pares[0] == pares[1]:
        raise PosicionInicialError("los dos puntos coinciden: marque dos puntos distintos de la linea")
    return pares


def analizar_imagen(imagen_bytes, puntos, parametros=None):
    """`leer_imagen` + `analizar` sobre los BYTES tal como se guardan: la misma función para guardar y para reabrir un
    registro (PI.4, que pasa los `parametros` guardados), de modo que lo recalculado al abrir es lo que se firmó (DD3)."""
    gris, color, dpi, _ = motor.leer_imagen(bytes(imagen_bytes))
    return motor.analizar(gris, color, dpi, _puntos_validos(puntos), parametros)


def _nombre_de_archivo(nombre):
    """Solo el nombre, sin la carpeta (con '/' o con '\\'): en la base no se guarda la ruta del equipo de quien la subió."""
    if nombre is None:
        return None
    texto = re.split(r"[\\/]", str(nombre))[-1].strip()
    return texto or None


def guardar(usuario, fecha, imagen_bytes, imagen_nombre, puntos, reemplazar=False, observaciones=None):
    """Guarda la prueba de un cambio de fuente y devuelve el `id` nuevo. ANALIZA desde los bytes y los puntos (ver el
    docstring del módulo). Rechaza con `ValueError` y SIN escribir nada: `PosicionInicialError` (con sus hijas
    `FechaSinCambioDeFuente` y `PruebaYaGuardada`) cuando decide el servicio -- usuario, fecha, imagen vacía, puntos,
    cambio de fuente sin serie (DD8: el mensual no la imprimiría) o con dos series, prueba ya vigente sin
    `reemplazar=True` --, y el `ValueError` simple del motor si la imagen no se reconoce o tiene transparencias.

    UNA transacción (`reemplazar_bloque`): anula la vigente de esa fecha, inserta la nueva y escribe UNA fila de
    auditoría (`guardar` si no había prueba, `reemplazo` si la había, con el `id` de la reemplazada en el detalle); si
    el INSERT falla -- p. ej. un milímetro que no es píxeles por escala (el CHECK de PI.2) -- no queda nada a medias."""
    if usuario is None or not str(usuario).strip():
        raise PosicionInicialError("falta el usuario que guarda la prueba")
    dia = fecha_iso(fecha)
    if dia is None:
        raise PosicionInicialError("la fecha debe ser 'aaaa-mm-dd': la del cambio de fuente al que pertenece la prueba")
    if not isinstance(imagen_bytes, (bytes, bytearray)) or not imagen_bytes:
        raise PosicionInicialError("falta la imagen")
    imagen = bytes(imagen_bytes)
    pares = _puntos_validos(puntos)
    resultado = analizar_imagen(imagen, pares)
    valores = motor.valores_medidos(resultado)
    nombre = _nombre_de_archivo(imagen_nombre)

    with Conexion().conectar() as db:
        cursor = db.cursor()
        series = {serie for fecha_cambio, serie in _filas_de_cambio_de_fuente(cursor) if fecha_cambio == dia}
        if not series:
            raise FechaSinCambioDeFuente(
                f"el {dia} no es la fecha de un cambio de fuente vigente: guarde primero el cambio de fuente "
                "en el mensual de braquiterapia")
        if None in series:
            raise PosicionInicialError(
                f"el cambio de fuente del {dia} no tiene serie: sin ella la prueba no saldria en el mensual")
        if len(series) > 1:
            raise PosicionInicialError(
                f"hay mas de un cambio de fuente vigente el {dia} con series distintas: no se sabe a cual pertenece")
        serie = next(iter(series))
        previa = _vigente_por_fecha(cursor, dia)
        if previa is not None and not reemplazar:
            raise PruebaYaGuardada(f"ya hay una posicion inicial guardada para el cambio de fuente del {dia}")

        parametros = resultado["parametros"]
        fila_valores = {
            "fecha": dia, "serie_fuente": serie, "user": usuario, "imagen": imagen, "imagen_nombre": nombre,
            "imagen_md5": hashlib.md5(imagen).hexdigest(), "dpi": resultado["dpi"],
            "puntos": json.dumps(pares), "parametros": json.dumps(parametros, sort_keys=True),
            "version_algoritmo": resultado["version"], "tolerancia_mm": parametros["tolerancia_mm"],
            "observaciones": observaciones, **valores}
        detalle = f"{dia} (fuente {serie}); {nombre or 'sin nombre de archivo'}; {resultado['version']}"
        if previa is not None:
            detalle += f"; reemplaza id={previa['id']}"
        reemplazar_bloque(
            cursor, TABLA, [("fecha", dia)], _SQL_INSERT, [tuple(fila_valores[c] for c in _COLUMNAS_INSERT)], usuario,
            detalle=detalle, accion=ACCION_REEMPLAZO if previa is not None else ACCION_GUARDAR)
        nuevo_id = cursor.lastrowid
        db.commit()
    return nuevo_id


def anular(id_registro, usuario, detalle=""):
    """Anula (`activo = 0`) la prueba con ese `id`, con su fila de auditoría en la MISMA transacción. Devuelve True, o
    False (sin escribir ni auditar nada) si no existe o ya estaba anulada. Por identidad, sin el `AND` de vigencia (ver
    el docstring del módulo). El permiso es del diálogo de la página."""
    if usuario is None or not str(usuario).strip():
        raise PosicionInicialError("falta el usuario que anula la prueba")
    with Conexion().conectar() as db:
        cursor = db.cursor()
        cursor.execute("SELECT activo, fecha FROM braqui_posicion_inicial WHERE id = ?", (id_registro,))
        fila = cursor.fetchone()
        if fila is None or fila[0] == 0:
            return False
        cursor.execute("UPDATE braqui_posicion_inicial SET activo = 0 WHERE id = ?", (id_registro,))
        texto = f"id={id_registro} (cambio de fuente del {fila[1]})"
        _registrar_auditoria(usuario, ACCION_ANULAR, TABLA, ref=id_registro,
                             detalle=f"{texto}; {detalle}" if detalle else texto, con=db)
        db.commit()
    return True


# ----------------------------------------------------------------------------- texto breve

def _numero(valor):
    """Dos decimales, y nunca '-0.00'."""
    texto = f"{valor:.2f}"
    return "0.00" if texto == "-0.00" else texto


def _tolerancia(valor):
    """'1.0' (y no '1'), '0.25', '1.5': siempre con decimales, sin perder los que haya."""
    texto = f"{valor:g}"
    return texto if "." in texto else texto + ".0"


def _parametros_del_registro(registro):
    """Los parámetros con que corrió el análisis guardado; la tolerancia es la del PROPIO registro (se guarda con cada
    uno: cambiarla en el código no reescribe veredictos guardados)."""
    parametros = dict(motor.PARAMETROS)
    try:
        guardados = json.loads(registro.get("parametros") or "{}")
    except (TypeError, ValueError):
        guardados = {}
    if isinstance(guardados, dict):
        parametros.update(guardados)
    if registro.get("tolerancia_mm") is not None:
        parametros["tolerancia_mm"] = registro["tolerancia_mm"]
    return parametros


def texto_breve(registro, con_cambio_de_fuente=True):
    """La posición inicial en una línea, de lo GUARDADO (una fila de `listar`, `leer` o `posicion_inicial_para`): la usan
    la tabla de registros de la página y los dos PDF, así que dicen lo mismo. Sentido, veredicto y aviso salen de
    `motor.interpretar` (la única definición); aquí solo se da formato. Ejemplos:
      -0.36 ± 0.09 mm (k = 2), antes de la marca. Cumple (tolerancia 1.0 mm). Cambio de fuente del 2026-06-26
      -0.60 ± 0.03 mm (k = 2) a la derecha de la linea en la imagen (no se distingue la banda de transito). Cumple (...)
      No medible: la mancha esta cortada por el borde de la pelicula. Cambio de fuente del 2026-06-26
      -8.55 ± 2.12 px (k = 2); la imagen declara 300 dpi y el procedimiento es de 600 dpi: parece escaneada a otra
      resolucion; escanee la pelicula a 600 dpi. Sin milimetros ni veredicto. Cambio de fuente del 2026-06-26
    Con el lado del tránsito conocido el desfase es el FÍSICO (negativo = antes de la marca); sin él, el de la imagen. Sin
    símbolos de correcto o incorrecto (DA-18) y sin `<`, `>` ni `&` (el PDF mensual mete la celda en un `Paragraph`).
    `con_cambio_de_fuente=False` omite el final (la tabla de la página ya tiene su columna de cambio de fuente)."""
    parametros = _parametros_del_registro(registro)
    estado = registro.get("estado_gris")
    px, u_px = registro.get("desfase_gris_px"), registro.get("incertidumbre_gris_px")
    tam, dpi = registro.get("tamano_pixel_mm"), registro.get("dpi")
    if not estado:
        estado = "no medible: sin dato"
    elif estado == "ok" and (px is None or u_px is None):
        estado = "no medible: registro incompleto"
    if estado != "ok":
        motivo = estado.split(":", 1)[1].strip() if estado.lower().startswith("no medible:") else estado
        cuerpo = f"{motor.interpretar(estado, None, None, None, None, None, parametros)['veredicto']}: {motivo}"
    elif tam is None and not dpi:
        cuerpo = (f"{_numero(px)} ± {_numero(u_px)} px (k = 2); sin milimetros ni veredicto "
                  "(la imagen no declara una resolucion valida)")
    else:
        r = motor.interpretar(estado, px, u_px, tam, registro.get("lado_transito"), dpi, parametros)
        if tam is None:
            cuerpo = f"{_numero(px)} ± {_numero(u_px)} px (k = 2); {r['aviso']}"
        else:
            fisico = r["desfase_fisico_mm"]
            desfase, union = (fisico, ", ") if fisico is not None else (r["desfase_mm"], " ")
            cuerpo = (f"{_numero(desfase)} ± {_numero(r['U_mm'])} mm (k = 2){union}{r['sentido']}. {r['veredicto']} "
                      f"(tolerancia {_tolerancia(parametros['tolerancia_mm'])} mm)")
    if con_cambio_de_fuente and registro.get("fecha"):
        cuerpo += f". Cambio de fuente del {registro['fecha']}"
    return cuerpo
