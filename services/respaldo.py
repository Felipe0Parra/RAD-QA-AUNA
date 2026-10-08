"""E9 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §17): respaldo real de la BD al
cerrar la app.

Antes de E9 el respaldo NO existía: `MainWindow.closeEvent` imprimía
"Guardando datos o haciendo respaldo..." con la llamada a `hacer_respaldo()`
comentada -- y aunque se descomentara, esa función copiaba desde una ruta de
red fija (ignorando `ruta_base_datos()`), con nombre de archivo fijo (cada
copia pisaba la anterior), ANTES del checkpoint del WAL (copia incompleta) y
con un `sys.exit(1)` que mataba la app al cerrar si el origen no existía.

Diseño de este módulo:
- Origen resuelto con `conection.ruta_base_datos()` (resolución dinámica por
  módulo, no captura por valor -- lección de H2.4/HI-1).
- Destino: carpeta `respaldos_bd/` JUNTO a la base de datos (junto al .exe en
  producción, raíz del repo en desarrollo). Mismo disco que la BD: si la BD es
  escribible, el respaldo también; protege contra corrupción y borrado
  accidental. Contra fallo del disco completo, el físico puede copiar la
  carpeta a otra unidad -- no hay ruta de red confiable que codificar aquí
  (la vieja ruta de red codificada era precisamente el defecto 3 de E9).
- Nombre fechado + rotación (se conservan las MAX_RESPALDOS copias más
  recientes): siempre hay historial y la carpeta no crece sin límite.
  RB.0 (05-10-2026): solo cuenta como respaldo un nombre con la forma exacta
  `BaseDatosQA_AAAA-MM-DD_HHMMSS[_NN].db`, y el nombre nuevo se decide en un
  solo paso, siempre posterior al último existente -- el respaldo termina
  siempre, aunque en la carpeta (compartida por todos los equipos) haya una
  copia de otro equipo con el reloj adelantado o un archivo ajeno.
- Best-effort: nunca lanza -- un fallo de respaldo jamás debe impedir cerrar
  la app (mismo principio que `registrar()` y `checkpoint_wal()`).
- Cada respaldo exitoso queda auditado (ACCION_GUARDAR / "backup") en la BD
  de origen: constancia de cuándo se respaldó DE VERDAD, contra el mensaje
  engañoso que había antes.

El orden correcto lo garantiza el llamador (`MainWindow.closeEvent`):
`checkpoint_wal()` PRIMERO, respaldo después -- así el .db principal ya
contiene todos los commits que vivían en el "-wal" (lección R2). Desde RB.1 la
copia ya no depende de ese orden: se hace con la API de respaldo de SQLite, que
da una foto consistente aunque el checkpoint haya quedado a medias.
"""

import os
import re
import shutil
import socket
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone

from data.ManejoDatos import conection as _conection
from services import audit_minimo
from services.registro_errores import avisar_consola, registrar_error

PREFIJO_RESPALDO = "BaseDatosQA_"
SUFIJO_RESPALDO = ".db"
NOMBRE_CARPETA_RESPALDOS = "respaldos_bd"
# RS.2 (C1 de la auditoria del 06-10, medido por V4): copiar un respaldo encima de `BaseDatosQA.db` dejando al lado un `-wal` con contenido NO restaura: SQLite aplica ese `-wal` viejo sobre el
# archivo restaurado (595 filas de `audit_log` en vez de las 554 del respaldo, con `integrity_check` en ok y sin aviso) o lo deja danado. La carpeta de respaldos lleva, una sola vez, el
# procedimiento correcto. Solo texto ASCII (se abre con cualquier editor, sin simbolos, DA-18); cuatro lineas.
NOMBRE_LEEME_RESTAURAR = "LEEME_RESTAURAR.txt"
TEXTO_LEEME_RESTAURAR = (
    "COMO RESTAURAR UN RESPALDO DE LA BASE DE DATOS\n"
    "1. Cierre RAD-QA en todos los equipos.\n"
    "2. Mueva a otra carpeta (no los borre) BaseDatosQA.db y, si existen, BaseDatosQA.db-wal y BaseDatosQA.db-shm: un -wal viejo junto al archivo restaurado se aplica encima y lo deshace.\n"
    "3. Copie el respaldo elegido con el nombre BaseDatosQA.db a la carpeta donde estaba la base de datos (la que contiene la carpeta respaldos_bd), abra la aplicacion y compruebe un par de controles conocidos.\n"
    "Lo que se guardo despues de la fecha del respaldo elegido no estara en la base restaurada: por eso los archivos del paso 2 se mueven y no se borran.\n"
)
# N~10 (decisión del plan §17): historial suficiente para volver varias
# sesiones atrás sin que la carpeta crezca sin límite (~10 x tamaño de la BD).
MAX_RESPALDOS = 10

_FORMATO_MARCA = "%Y-%m-%d_%H%M%S"
# RB.0 (05-10-2026, DP-150): un respaldo es EXACTAMENTE `BaseDatosQA_AAAA-MM-DD_HHMMSS.db` o `..._NN.db`, con una fecha
# y una hora reales. Cualquier otro archivo de la carpeta (una copia manual, un `.parcial`, un
# `BaseDatosQA_Rebuild_14-09-2026.db`) ni cuenta, ni se rota, ni decide el nombre del respaldo nuevo.
# Solo digitos ASCII (`re.ASCII`: `\d` aceptaria `\u0662\u0660\u0662\u0666`) y el nombre ENTERO (`fullmatch`: `$` aceptaria un salto de linea final).
_PATRON_RESPALDO = re.compile(
    re.escape(PREFIJO_RESPALDO) + r"(\d{4}-\d{2}-\d{2}_\d{6})(?:_(\d{2}))?" + re.escape(SUFIJO_RESPALDO), re.ASCII)
# Una marca a menos de un segundo del fin del calendario no es una hora de este mundo: su "segundo siguiente" (lo que `_nombre_nuevo` calcula cuando
# el contador llega a 99) se sale del rango (`OverflowError`) y el cierre no podria respaldar nunca mas. Esa marca no cuenta como respaldo.
_ULTIMA_MARCA_UTIL = datetime.max - timedelta(seconds=1)

# RB.1 (05-10-2026, DP-150): la copia es una FOTO CONSISTENTE de la base, hecha con la API de respaldo de SQLite, y se
# comprueba antes de contar como respaldo. Copiar el archivo `.db` (como hacía E9) daba una copia DAÑADA si en ese
# instante otro equipo tenía una operación abierta y el checkpoint quedaba a medias (medido, M6): un checkpoint
# incompleto deja en el `.db` páginas nuevas y viejas mezcladas, que solo forman una base válida junto a su `-wal`.
SUFIJO_PARCIAL = ".parcial"     # la copia mientras se hace y se comprueba: no cuenta como respaldo
SUFIJOS_LATERALES = ("-journal", "-wal", "-shm")     # lo que SQLite puede dejar junto a un archivo (una copia que falla a medias deja un `-journal`)
SUFIJO_REVISAR = ".revisar"     # copia aparte de una base que NO pasa la comprobación: ni cuenta ni se rota como respaldo
MAX_COPIAS_A_REVISAR = 3        # cada cierre con la base dañada deja una; sin tope crecerían sin límite (con relojes distintos entre equipos, una más: la recién hecha no se borra)
# `Connection.backup` reintenta SIN FIN mientras la base de origen está ocupada (SQLITE_BUSY / SQLITE_LOCKED): sin un
# corte, el cierre de la aplicación se quedaría colgado como en M13. Pasado este tiempo la copia se rinde y el
# siguiente cierre reintenta.
ESPERA_MAXIMA_COPIA_S = 30
_ESPERA_CONEXION_S = 5
_SQLITE_BUSY, _SQLITE_LOCKED = 5, 6
ESTADO_OK, ESTADO_DEFECTO, ESTADO_NO_CONCLUYENTE = "ok", "defecto", "no_concluyente"
# B-02 de la segunda revision: `PRAGMA integrity_check` no solo detecta DAÑO; tambien verifica las restricciones (CHECK, NOT NULL) fila por fila. Una fila que viola una
# restriccion NO es un daño: la base se abre, se lee, se escribe y se copia bien. Tratarla como `defecto` apagaba TODOS los respaldos (ninguno, sin rotar, una `.revisar`
# y una fila ATENCION por cierre -- y, con RB.2, una copia completa por cierre sin dar ningun respaldo) y frenaba el respaldo previo a la migracion (F1). Solo se clasifica
# asi si TODOS los mensajes son de restriccion: cualquier otro mensaje -- o uno que no se reconozca -- sigue siendo `defecto`.
ESTADO_OK_CON_AVISO = "ok_con_aviso"
_MENSAJE_DE_RESTRICCION = re.compile(r"(?:CHECK constraint failed in|NULL value in) ")
# `integrity_check` corta en 100 mensajes por defecto: con mas de 100 filas infractoras, un daño de indice que se emita DESPUES quedaria fuera de la lista y se clasificaria
# mal (medido por el esceptico). Se pide un tope alto y, si aun asi se llena, no se puede afirmar que sean solo restricciones: `defecto`.
_TOPE_MENSAJES_INTEGRIDAD = 1000


def carpeta_respaldos(ruta_origen=None):
    """Carpeta de respaldos: `respaldos_bd/` junto al archivo de la BD."""
    if ruta_origen is None:
        ruta_origen = _conection.ruta_base_datos()
    return os.path.join(os.path.dirname(os.path.abspath(ruta_origen)),
                        NOMBRE_CARPETA_RESPALDOS)


def _marca_y_contador(nombre):
    """`(marca, contador)` de un nombre con la forma exacta de un respaldo (el contador es 1 si no lleva `_NN`), o `None`
    si no la tiene o si la marca no es una fecha y hora reales."""
    m = _PATRON_RESPALDO.fullmatch(nombre)
    if m is None:
        return None
    try:
        fecha = datetime.strptime(m.group(1), _FORMATO_MARCA)
    except ValueError:
        return None
    if fecha > _ULTIMA_MARCA_UTIL:
        return None
    return (m.group(1), int(m.group(2)) if m.group(2) else 1)


def _nombres_respaldo(carpeta):
    """Respaldos presentes en la carpeta, ordenados del más viejo al más
    reciente. El nombre fechado (YYYY-MM-DD_HHMMSS, con ceros a la izquierda)
    hace que el orden alfabético SEA el cronológico -- no se depende del mtime,
    que una copia manual de la carpeta puede alterar. Solo cuentan los nombres
    con la forma exacta de un respaldo (RB.0)."""
    try:
        nombres = [n for n in os.listdir(carpeta)
                   if _marca_y_contador(n) is not None]
    except OSError:
        return []
    return sorted(nombres)


def _nombre_nuevo(existentes, ahora):
    """Nombre del respaldo nuevo, decidido en UN paso (RB.0): el que toca por la hora `ahora` si ordena DESPUÉS del último
    respaldo existente; si no, la marca de ese último con su contador más uno (o, si el contador ya está en 99, el
    segundo siguiente a esa marca). El nombre nuevo es SIEMPRE posterior a todos los existentes -- la rotación borra por
    orden de nombre y no puede borrarlo primero -- y no hay bucle: antes, un bucle que solo cambiaba el contador no
    terminaba nunca si en la carpeta había una copia con hora posterior a la de este equipo (otro equipo con el reloj
    adelantado, o un archivo ajeno con el prefijo) y `closeEvent` no llegaba a `event.accept()`. Un respaldo nombrado con
    la marca de otro equipo lleva una hora que no es la de este: la hora real queda en su fila de auditoría.

    `existentes`: los nombres válidos, ordenados (`_nombres_respaldo`)."""
    candidato = f"{PREFIJO_RESPALDO}{ahora.strftime(_FORMATO_MARCA)}{SUFIJO_RESPALDO}"
    if not existentes or candidato > existentes[-1]:
        return candidato
    marca_ultimo, contador_ultimo = _marca_y_contador(existentes[-1])
    if contador_ultimo < 99:
        return f"{PREFIJO_RESPALDO}{marca_ultimo}_{contador_ultimo + 1:02d}{SUFIJO_RESPALDO}"
    segundo_siguiente = datetime.strptime(marca_ultimo, _FORMATO_MARCA) + timedelta(seconds=1)
    return f"{PREFIJO_RESPALDO}{segundo_siguiente.strftime(_FORMATO_MARCA)}{SUFIJO_RESPALDO}"


def _dejar_leeme(carpeta):
    """RS.2: deja en la carpeta de respaldos el procedimiento para restaurar, UNA sola vez (si el archivo ya esta, no se reescribe). No cuenta como respaldo: la rotacion solo reconoce el
    nombre exacto de un respaldo (RB.0). Nunca lanza: un LEEME que no se pudo escribir no impide el respaldo."""
    ruta = os.path.join(carpeta, NOMBRE_LEEME_RESTAURAR)
    try:
        if os.path.isfile(ruta) and os.path.getsize(ruta) == 0:
            os.remove(ruta)         # RS.2 (revision): un LEEME de 0 bytes (el proceso cayo entre crearlo y escribirlo) no existe: se rehace
        _crear_exclusivo(ruta, TEXTO_LEEME_RESTAURAR)
    except Exception:
        pass


def _avisar(texto, excepcion=None):
    """RS.1 (DP-153): un respaldo que NO se pudo hacer se dice por consola (el `print` de siempre) Y queda escrito en `error_log.txt`, junto al ejecutable. El `.exe` se construye `--noconsole`
    (`build_exe.py`): ahi un `print` no lo ve nadie, y un respaldo que falla en cada cierre dejaba al servicio sin red de seguridad sin que nada lo dijera. La ruta del archivo sale de UNA
    sola funcion (`registro_errores.ruta_error_log`, la de `main.py`), que las pruebas redirigen. Nunca lanza: un aviso que falla no puede impedir cerrar la app."""
    avisar_consola(texto)
    registrar_error(texto, excepcion)


def _rotar(carpeta, max_copias):
    """Elimina los respaldos más viejos hasta dejar `max_copias`."""
    nombres = _nombres_respaldo(carpeta)
    for nombre in nombres[:-max_copias] if max_copias > 0 else nombres:
        try:
            os.remove(os.path.join(carpeta, nombre))
        except OSError as ex:
            _avisar(f"[respaldo] no se pudo rotar {nombre} (en {carpeta}): {ex}", ex)      # RS.1 (revision): una rotacion rota deja crecer la carpeta sin limite y en el .exe nadie lo veria


def _quitar(ruta):
    """Borra `ruta` si existe. Nunca lanza."""
    try:
        os.remove(ruta)
    except FileNotFoundError:
        pass
    except OSError as ex:
        print(f"[respaldo] no se pudo borrar {os.path.basename(ruta)}: {ex}")


def _quitar_con_laterales(ruta):
    """Borra `ruta` y lo que SQLite pudo dejar a su lado (`-journal`, `-wal`, `-shm`): una copia que falla a medias (disco lleno...) deja un
    `-journal` huerfano que nada mas limpiaria (H6 de la revision). Nunca lanza."""
    for sufijo in SUFIJOS_LATERALES:
        _quitar(ruta + sufijo)
    _quitar(ruta)


def _nombre_provisional(destino):
    """Nombre PROPIO del archivo provisional de ESTA copia: `<respaldo>.<pid>-<aleatorio>.parcial` (H1 de la revision). Antes era
    `<respaldo>.parcial`, el mismo para todos los procesos: dos `respaldar_bd` que elegian el mismo nombre (dos equipos con el reloj atrasado
    respecto a la ultima copia, o un cierre que retoma el reclamo de otro que se habia caido pero sigue trabajando; el respaldo previo a una
    migracion, F1, escribe en otra carpeta, `pre_migracion/`) se pisaban el provisional -- uno borraba el del otro al empezar y al fallar -- y llegaron a dejar un archivo de 0 bytes con nombre
    de respaldo. Con un nombre propio, nadie toca un provisional ajeno."""
    return f"{destino}.{os.getpid()}-{uuid.uuid4().hex[:8]}{SUFIJO_PARCIAL}"


def _copiar_con_api(ruta_origen, ruta_parcial):
    """Copia la base `ruta_origen` a `ruta_parcial` con la API de respaldo de SQLite, en UN solo paso (RB.1).

    Es una foto consistente de lo confirmado hasta ese instante aunque otros estén trabajando y aunque el checkpoint
    del WAL no haya terminado. La copia hereda el modo WAL de la base: se deja en el modo normal para que sea un solo
    archivo autocontenido, y abrirla (aunque sea en una carpeta de solo lectura o de red) no cree `-wal` ni `-shm`.
    Cierra SIEMPRE las dos conexiones: en Windows no se renombra un archivo abierto.

    `Connection.backup` reintenta sin fin mientras la base de origen está ocupada; la función de progreso corta ese
    reintento pasado `ESPERA_MAXIMA_COPIA_S` (lanza `TimeoutError`), así que esta función termina siempre."""
    inicio = time.monotonic()

    def _no_esperar_sin_fin(estado, restantes, total):
        if estado in (_SQLITE_BUSY, _SQLITE_LOCKED) and time.monotonic() - inicio > ESPERA_MAXIMA_COPIA_S:
            raise TimeoutError(f"la base de datos de origen sigue ocupada tras {ESPERA_MAXIMA_COPIA_S} s")

    origen = destino = None
    try:
        origen = sqlite3.connect(ruta_origen, timeout=min(ESPERA_MAXIMA_COPIA_S, _ESPERA_CONEXION_S))
        destino = sqlite3.connect(ruta_parcial)
        origen.backup(destino, progress=_no_esperar_sin_fin)
        destino.execute("PRAGMA journal_mode=DELETE")
    finally:
        for con in (destino, origen):
            if con is not None:
                try:
                    con.close()
                except Exception:
                    pass


def _integridad(ruta):
    """`(estado, detalle)` de `PRAGMA integrity_check` sobre `ruta`, con una conexión NUEVA (lo que hay en disco, no lo
    que una conexión recuerda): `('ok', None)`, `('defecto', texto)` si la base está dañada o no es una base SQLite,
    `('ok_con_aviso', texto)` si lo único que reporta son filas que violan una restricción (CHECK, NOT NULL: la estructura está bien y la
    copia es fiel, B-02), o `('no_concluyente', texto)` si no se pudo comprobar (ocupada por otro, sin acceso...): eso no es un defecto de la
    base y no debe disparar una alarma.

    H1 de la revision: un archivo que NO esta no se comprueba (`sqlite3.connect` lo CREARIA vacio y `integrity_check` lo daria por
    bueno: se habria renombrado un archivo de 0 bytes como respaldo valido), y uno de 0 bytes es un defecto: no es una copia."""
    try:
        tamano = os.path.getsize(ruta)
    except FileNotFoundError:
        return (ESTADO_NO_CONCLUYENTE, "el archivo no existe")
    except OSError as ex:
        return (ESTADO_NO_CONCLUYENTE, str(ex))
    if tamano == 0:
        return (ESTADO_DEFECTO, "el archivo esta vacio (0 bytes)")
    con = None
    try:
        con = sqlite3.connect(ruta, timeout=min(ESPERA_MAXIMA_COPIA_S, _ESPERA_CONEXION_S))
        filas = con.execute(f"PRAGMA integrity_check({_TOPE_MENSAJES_INTEGRIDAD})").fetchall()
    except sqlite3.OperationalError as ex:
        return (ESTADO_NO_CONCLUYENTE, str(ex))
    except sqlite3.DatabaseError as ex:
        return (ESTADO_DEFECTO, str(ex))
    except Exception as ex:
        return (ESTADO_NO_CONCLUYENTE, f"{type(ex).__name__}: {ex}")
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass
    # B-04 de la segunda revision: si el archivo desaparecio o fue reemplazado entre medir y conectar, `connect` lo CREO vacio y `integrity_check` lo da por bueno
    # (con un proceso que reacciona al cierre del provisional, medido en 1.9-3.7 % de los cierres). Un archivo que sigue en 0 bytes tras la comprobacion nunca fue una base.
    try:
        if os.path.getsize(ruta) == 0:
            return (ESTADO_DEFECTO, "el archivo esta vacio (0 bytes)")
    except OSError as ex:
        return (ESTADO_NO_CONCLUYENTE, str(ex))
    if len(filas) == 1 and filas[0][0] == "ok":
        return (ESTADO_OK, None)
    mensajes = [str(f[0]).replace("\n", " ") for f in filas]
    detalle = "; ".join(mensajes[:3])
    if len(filas) < _TOPE_MENSAJES_INTEGRIDAD and all(_MENSAJE_DE_RESTRICCION.match(m) for m in mensajes):
        return (ESTADO_OK_CON_AVISO, detalle)
    return (ESTADO_DEFECTO, detalle)


def _nombres_a_revisar(carpeta):
    """Copias aparte (`<nombre de respaldo>.revisar`) presentes en la carpeta, de la más vieja a la más reciente."""
    try:
        nombres = [n for n in os.listdir(carpeta)
                   if n.endswith(SUFIJO_REVISAR) and _marca_y_contador(n[:-len(SUFIJO_REVISAR)]) is not None]
    except OSError:
        return []
    return sorted(nombres)


def _conservar_para_revisar(ruta_origen, parcial, destino, copia_hecha):
    """Cuando la base de origen NO pasa la comprobación hace falta conservar algo para revisarla: es el momento en que más
    falta hace. Se guarda la copia que ya se hizo (o, si la copia no se pudo hacer, el archivo tal cual) con un nombre
    que NO es el de un respaldo (`<nombre>.revisar`): no entra en la rotación ni cuenta como respaldo. Conserva a lo
    sumo `MAX_COPIAS_A_REVISAR`: la primera (la mas cercana al momento del daño, la que mas vale) y las mas recientes (una mas si los
    relojes de los equipos difieren: la recien hecha no se borra). La primera de un incidente ya resuelto sigue ocupando su plaza hasta que
    alguien borre las `.revisar` a mano (limite declarado, B-03 de la segunda revision). Devuelve la ruta, o `None` si no se pudo."""
    revisar = destino + SUFIJO_REVISAR
    try:
        if copia_hecha and os.path.isfile(parcial):
            os.replace(parcial, revisar)
        else:
            shutil.copy2(ruta_origen, revisar)
    except Exception as ex:
        _avisar(f"[respaldo] no se pudo conservar la copia para revisar de {ruta_origen} ({revisar}): {ex}", ex)
        return None
    carpeta = os.path.dirname(revisar)
    nombres = _nombres_a_revisar(carpeta)
    # H4 de la revision: se conserva la PRIMERA copia (la mas cercana al momento en que la base se daño) y las `MAX - 1` ultimas; antes se
    # conservaban solo las mas recientes y la primera se perdia a los 3 cierres siguientes, el mismo dia. La que se acaba de hacer tampoco se
    # borra: con el reloj de este equipo atrasado respecto al de otros que tambien dejaron copias, su nombre puede quedar en medio.
    conservar = set(nombres[:1]) | set(nombres[max(len(nombres) - (MAX_COPIAS_A_REVISAR - 1), 0):]) | {os.path.basename(revisar)}
    for viejo in nombres:
        if viejo not in conservar:
            _quitar(os.path.join(carpeta, viejo))
    return revisar


MOTIVO_CIERRE_APP = "respaldo al cerrar la aplicacion"


def respaldar_bd(usuario=None, ruta_origen=None, carpeta_destino=None,
                 max_copias=MAX_RESPALDOS, motivo=MOTIVO_CIERRE_APP, ahora=None):
    """Crea una copia fechada de la BD y rota las viejas. Nunca lanza.

    Devuelve la ruta de la copia creada, o None si no se pudo (origen
    inexistente, destino no escribible, etc. -- se avisa por consola y se
    sigue: el cierre de la app no debe bloquearse por esto).

    `motivo` (F6, PLAN_F_CIERRE_ESTANDAR_29-07.md): el detalle auditado debe
    describir el evento REAL que disparó el respaldo -- antes de F6, un
    respaldo previo a la migración estructural (F1) se auditaba con el texto
    fijo "respaldo al cerrar la aplicacion", una etiqueta incorrecta para un
    evento que nada tiene que ver con cerrar la app. Por defecto conserva el
    texto histórico de E9 (cierre de la app), así que el camino de
    `MainWindow.closeEvent` no cambia.

    `ahora` (RB.0): la hora con la que se nombra el respaldo; por omisión la de
    este equipo, como antes. Permite fijarla en las pruebas y en `RB.2`. El
    nombre se decide en un solo paso (`_nombre_nuevo`): el respaldo termina
    siempre, con cualquier contenido de la carpeta.

    RB.1: la copia es una foto consistente hecha con la API de respaldo de
    SQLite a un nombre provisional (`.parcial`), y solo cuenta como respaldo
    (se renombra, se rota y se audita) si pasa `PRAGMA integrity_check`.
    Si no la pasa: con la base de origen sana, la copia se descarta y se
    devuelve `None` (el siguiente cierre reintenta); con la base de origen
    dañada (o que SQLite no puede leer) no se rota nada, se conserva una copia
    aparte (`<hora de este equipo>.revisar`, fuera de la rotación) y se deja una
    fila de auditoría que lo dice -- si la base permite escribirla: cuando SQLite
    no puede ni abrirla (cabecera pisada, archivo que no es una base) la
    auditoría vive en esa misma base y no se puede escribir, y la constancia es
    la copia aparte y el aviso por consola (H3 de la revisión). Una base ocupada
    por otro no es un defecto: se devuelve `None` sin alarma. Sigue siendo
    best-effort y termina siempre.
    """
    parcial = None
    try:
        if ruta_origen is None:
            ruta_origen = _conection.ruta_base_datos()
        if not os.path.isfile(ruta_origen):
            _avisar(f"[respaldo] no existe la BD de origen, no se respalda: {ruta_origen}")
            return None
        if carpeta_destino is None:
            carpeta_destino = carpeta_respaldos(ruta_origen)
        os.makedirs(carpeta_destino, exist_ok=True)

        # Con segundos + contador de colisión: dos cierres muy seguidos nunca
        # se pisan entre sí (el nombre de archivo fijo era el defecto 1 de E9).
        # El nombre nuevo debe ordenar DESPUÉS de todos los existentes -- no
        # basta con "que no exista": la rotación borra el más viejo y liberaría
        # su nombre, y reutilizarlo daría a un respaldo nuevo un nombre
        # alfabéticamente viejo (la rotación siguiente lo borraría primero).
        # Contador con cero a la izquierda para que _10 ordene tras _09.
        # RB.0: se decide en UN paso (`_nombre_nuevo`), nunca con un bucle que
        # pueda no terminar con lo que haya en la carpeta (M13).
        if ahora is None:
            ahora = datetime.now()
        nombre = _nombre_nuevo(_nombres_respaldo(carpeta_destino), ahora)
        destino = os.path.join(carpeta_destino, nombre)

        # RB.1: una foto consistente (API de respaldo de SQLite, en un paso) con un nombre PROVISIONAL, que no cuenta
        # como respaldo hasta que se comprueba. Antes: `shutil.copy2` del `.db`, que sale dañado si el checkpoint quedó a
        # medias, y aun así se rotaba y se auditaba como respaldo hecho.
        parcial = _nombre_provisional(destino)
        copia_hecha = False
        try:
            _copiar_con_api(ruta_origen, parcial)
            copia_hecha = True
        except Exception as ex:
            _avisar(f"[respaldo] la copia no se pudo hacer ({ruta_origen} -> {carpeta_destino}): {ex}", ex)
        if copia_hecha:
            estado, detalle = _integridad(parcial)
            if estado in (ESTADO_OK, ESTADO_OK_CON_AVISO):
                os.replace(parcial, destino)
                parcial = None
                _rotar(carpeta_destino, max_copias)
                _dejar_leeme(carpeta_destino)        # RS.2: el procedimiento de restauracion aparece junto al primer respaldo HECHO (un fallo no deja nada en la carpeta)

                audit_minimo.registrar(
                    usuario, audit_minimo.ACCION_GUARDAR, tabla="backup",
                    ref=os.path.basename(destino),
                    detalle=f"{motivo}: {destino}",
                    ruta_db=ruta_origen)
                if estado == ESTADO_OK_CON_AVISO:
                    # B-02: la base viola una restriccion de su esquema (la estructura esta bien y la copia es fiel): el respaldo se hizo y queda constancia del aviso.
                    audit_minimo.registrar(
                        usuario, audit_minimo.ACCION_GUARDAR, tabla="backup",
                        ref=os.path.basename(destino),
                        detalle=("AVISO: la base de datos viola una restriccion de su esquema (la estructura esta bien y el respaldo se hizo): "
                                 f"{str(detalle)[:200]}"),
                        ruta_db=ruta_origen)
                print(f"Respaldo de la base de datos creado en: {destino}")
                return destino
            _avisar(f"[respaldo] la copia de {ruta_origen} no pasa la comprobacion de integridad ({detalle}): se descarta")

        # No hay un respaldo valido. Si la base de origen esta sana, el problema era de la copia: se descarta y el
        # siguiente cierre reintenta. Si el origen NO pasa la comprobacion (o SQLite no puede ni leerlo), no se rota
        # ni se cuenta nada como respaldo: se conserva una copia aparte para revisarla y se deja constancia visible.
        estado_origen, detalle_origen = _integridad(ruta_origen)
        if estado_origen != ESTADO_DEFECTO:
            return None
        # H4 de la revision: la copia aparte se nombra con la hora de ESTE equipo, no con el nombre que habria tenido el respaldo (que se
        # repite en cada cierre si hay una copia de otro equipo con el reloj adelantado, y entonces cada cierre pisaria la anterior).
        a_revisar = os.path.join(carpeta_destino, f"{PREFIJO_RESPALDO}{ahora.strftime(_FORMATO_MARCA)}{SUFIJO_RESPALDO}")
        revisar = _conservar_para_revisar(ruta_origen, parcial, a_revisar, copia_hecha)
        audit_minimo.registrar(
            usuario, audit_minimo.ACCION_GUARDAR, tabla="backup",
            ref=os.path.basename(revisar) if revisar else nombre,
            detalle=("ATENCION, respaldo NO hecho: la base de datos de origen no pasa la comprobacion de integridad "
                     f"({str(detalle_origen)[:200]}). "
                     + (f"Copia aparte para revisar, fuera de la rotacion: {revisar}" if revisar
                        else "No se pudo conservar ninguna copia aparte.")),
            ruta_db=ruta_origen)
        _avisar(f"[respaldo] ATENCION: la base de datos de origen ({ruta_origen}) no pasa la comprobacion de integridad: {detalle_origen}")
        return None
    except Exception as ex:
        _avisar(f"[respaldo] no se pudo respaldar la base de datos: {ex}", ex)
        return None
    finally:
        if parcial is not None:
            _quitar_con_laterales(parcial)


# ---------------------------------------------------------------------------------------------------------------------
# RB.2 (05-10-2026, DP-150, decision D2 del fisico: "maximo dos por dia"): a lo sumo UN respaldo por franja del dia.
#
# Antes se respaldaba en CADA cierre, y volver a "Inicio" es un cierre (`MainWindow.cerrar` -> `close` -> `closeEvent`): en
# produccion 39 respaldos en 18 dias, 5 dias con mas de dos, hasta 6 en un dia (M9). Ahora: una copia por franja -- mañana (antes
# de `HORA_DE_CORTE`) y tarde (desde ella) --, hecha en el PRIMER cierre de la franja. A cambio, lo guardado despues de la copia de
# la tarde espera a la primera del dia siguiente (P4 del plan).
#
# La franja NO se deduce del nombre de los respaldos (con relojes distintos entre equipos el nombre puede llevar la hora de otro
# equipo, RB.0): se lleva con archivos pequeños en la misma carpeta (compartida por todos los equipos),
# `franja_<fecha>_<N>.reclamo` (alguien la esta haciendo) y `franja_<fecha>_<N>.hecha` (ya esta hecha).
HORA_DE_CORTE = 12
# A-1 de la segunda revision: la franja y el nombre se leen en la zona del SERVICIO (Colombia: UTC-5 todo el año, sin horario de verano), no en la del equipo que cierra:
# con `datetime.fromtimestamp` a secas, dos equipos con zonas horarias distintas veian el MISMO instante del servidor en franjas distintas (dos copias a la vez, o la franja
# de la tarde consumida antes de las 12:00 reales). Un desfase fijo y no `ZoneInfo`: el desfase no puede fallar (no depende de la base de zonas horarias del equipo).
ZONA_DEL_SERVICIO = timezone(timedelta(hours=-5))
PREFIJO_FRANJA = "franja_"
SUFIJO_RECLAMO = ".reclamo"
SUFIJO_HECHA = ".hecha"
EDAD_MAXIMA_RECLAMO_S = 600                  # un reclamo de mas de 10 minutos es de un cierre que se cayo: se puede retomar
EDAD_MAXIMA_MARCAS_S = 7 * 24 * 3600         # las marcas de franja de mas de 7 dias se retiran
EDAD_MAXIMA_PROVISIONAL_S = 24 * 3600        # los provisionales huerfanos de mas de un dia se retiran
# Puntos de corte inyectables: las pruebas de concurrencia intercalan dos cierres en un punto exacto (intercalados deterministas;
# lanzar procesos a la vez no basta: con bases pequeñas la copia dura milisegundos y la carrera puede no ocurrir). En produccion
# `_GANCHOS` esta vacio y `_punto` no hace nada.
_GANCHOS = {}


def franja_de(momento):
    """`(fecha, n)` de la franja a la que pertenece `momento`: `fecha` es `AAAA-MM-DD`; `n` es 1 (antes de `HORA_DE_CORTE`) o 2
    (desde ella)."""
    return momento.strftime("%Y-%m-%d"), (1 if momento.hour < HORA_DE_CORTE else 2)


def _punto(nombre):
    gancho = _GANCHOS.get(nombre)
    if gancho is not None:
        gancho()


def _marca_de_franja(carpeta, franja, sufijo):
    return os.path.join(carpeta, f"{PREFIJO_FRANJA}{franja[0]}_{franja[1]}{sufijo}")


def _crear_exclusivo(ruta, texto):
    """Crea `ruta` SOLO si no existe (creacion exclusiva: si varios equipos lo intentan a la vez, uno solo lo logra).
    `True` si la creo. Un `PermissionError` con el archivo YA presente (en Windows, uno con borrado pendiente) se toma como "ocupado"; si
    el archivo no esta, es falta de permiso sobre la carpeta (E1 de la revision): no se obtiene y se avisa (por consola y en `error_log.txt`, RS.1/DP-153: el .exe
    `--noconsole` no tiene consola)."""
    try:
        fd = os.open(ruta, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except PermissionError as ex:
        if not os.path.exists(ruta):
            _avisar(f"[respaldo] sin permiso para crear {os.path.basename(ruta)}: {ex}", ex)
        return False
    try:
        os.write(fd, texto.encode("utf-8"))
    except BaseException:
        os.close(fd)
        fd = None
        _quitar(ruta)               # RS.2 (revision): un archivo creado y NO escrito (disco lleno...) queda de 0 bytes y, al existir, nada lo reescribiria: se quita
        raise
    finally:
        if fd is not None:
            os.close(fd)
    return True


def _reloj_del_servidor(carpeta):
    """La hora que ve el servidor de archivos de `carpeta`: la fecha de modificacion de un archivo recien creado ahi. Los equipos de
    la red no comparten reloj: la edad de un reclamo se mide con el MISMO reloj en los dos extremos."""
    sonda = os.path.join(carpeta, f"{PREFIJO_FRANJA}sonda_{uuid.uuid4().hex}.tmp")
    try:
        with open(sonda, "wb") as f:
            f.write(b"x")
        return os.stat(sonda).st_mtime
    finally:
        _quitar(sonda)


def _hora_segun_el_servidor(carpeta):
    """La hora de ESTE cierre con el reloj del servidor de archivos de `carpeta`, en la zona del servicio (C1 y A-1 de la revision). Los equipos de la red
    no comparten reloj, y la franja y el nombre del respaldo tienen que salir del MISMO reloj en todos: con el de cada equipo, un PC
    adelantado consumiria por adelantado la franja de OTRO dia (o de otra mitad del dia) y los cierres reales de esa franja no
    respaldarian nada, sin ningun aviso. Si no se puede leer (carpeta sin permiso...), la hora de este equipo."""
    try:
        return datetime.fromtimestamp(_reloj_del_servidor(carpeta), tz=ZONA_DEL_SERVICIO).replace(tzinfo=None)
    except Exception:
        return datetime.now()


def _edad_del_reclamo(reclamo, carpeta):
    """Segundos que lleva el reclamo, o `None` si ya no existe."""
    try:
        creado = os.stat(reclamo).st_mtime
    except FileNotFoundError:
        return None
    return _reloj_del_servidor(carpeta) - creado


def _ruta_reclamo(carpeta, franja, generacion):
    """El reclamo de la franja en su `generacion`: la 1 es `.reclamo`; las siguientes, `.reclamo.2`, `.reclamo.3`..."""
    base = _marca_de_franja(carpeta, franja, SUFIJO_RECLAMO)
    return base if generacion == 1 else f"{base}.{generacion}"


def _reclamos_de(carpeta, franja):
    """`{generacion: ruta}` de los reclamos que hay de la franja."""
    base = os.path.basename(_marca_de_franja(carpeta, franja, SUFIJO_RECLAMO))
    encontrados = {}
    for n in os.listdir(carpeta):
        if n == base:
            encontrados[1] = os.path.join(carpeta, n)
        # solo digitos ASCII: `str.isdigit()` acepta '²' y `int('²')` lanza (misma clase que H7): un archivo ajeno en la carpeta compartida detenia los respaldos de la franja
        elif n.startswith(base + ".") and re.fullmatch(r"[0-9]+", n[len(base) + 1:]) and int(n[len(base) + 1:]) >= 2:
            encontrados[int(n[len(base) + 1:])] = os.path.join(carpeta, n)
    return encontrados


def _reclamar(carpeta, franja, ahora):
    """La ruta del reclamo si ESTE cierre lo obtuvo, o `None` (alguien mas la esta haciendo).

    Si hay un reclamo reciente, lo tiene otro cierre. Si el ultimo reclamo es viejo (de un cierre que se cayo), se retoma creando,
    en EXCLUSIVA, el de la generacion siguiente (`.reclamo.2`...): de varios equipos que vieron el mismo reclamo viejo, uno solo
    lo crea. No se renombra el reclamo viejo: un renombrado no distingue el viejo del que otro acaba de retomar (mismo nombre) y
    dos equipos podrian retomarlo a la vez."""
    texto = f"{socket.gethostname()} pid={os.getpid()} {ahora.isoformat(timespec='seconds')}"
    existentes = _reclamos_de(carpeta, franja)
    generacion = max(existentes) if existentes else 0
    if generacion:
        edad = _edad_del_reclamo(existentes[generacion], carpeta)
        if edad is not None:
            # `abs`: un reclamo con fecha en el FUTURO (reloj del servidor corrido hacia atras) tampoco es de un cierre en curso (C2 de la
            # revision); sin `abs` su edad es negativa, parece reciente y bloquea la franja hasta que el reloj lo alcance.
            if abs(edad) < EDAD_MAXIMA_RECLAMO_S:
                return None
            _punto("antes_de_retomar")
    siguiente = _ruta_reclamo(carpeta, franja, generacion + 1)
    return siguiente if _crear_exclusivo(siguiente, texto) else None


def _consumir(reclamo, hecha, carpeta, franja):
    """Convierte el reclamo en la marca de franja hecha (renombrado) y retira los reclamos viejos que la retomaron. Si el reclamo
    ya no existia (otro equipo lo retiro al terminar antes), la franja queda marcada igual: este cierre SI hizo su copia."""
    try:
        os.replace(reclamo, hecha)
    except OSError:
        _crear_exclusivo(hecha, "hecha")
    try:
        for ruta in _reclamos_de(carpeta, franja).values():
            _quitar(ruta)
    except OSError:
        pass


# Un provisional de RB.1 es `<respaldo>.<pid>-<aleatorio>.parcial` (o, de antes de H1, `<respaldo>.parcial`), con sus laterales de SQLite.
_PATRON_PROVISIONAL = re.compile(r"(.+?\.db)(?:\.[0-9]+-[0-9a-f]+)?" + re.escape(SUFIJO_PARCIAL)
                                 + "(?:" + "|".join(re.escape(s) for s in SUFIJOS_LATERALES) + ")?", re.ASCII)


def _es_provisional(nombre):
    """`True` si `nombre` es un provisional de `respaldar_bd` (o un lateral suyo): lo que deja un cierre que se cayo a medias."""
    m = _PATRON_PROVISIONAL.fullmatch(nombre)
    return m is not None and _marca_y_contador(m.group(1)) is not None


def _limpiar_marcas(carpeta):
    """Retira las marcas de franja de mas de 7 dias y los provisionales huerfanos de mas de un dia. Best-effort."""
    try:
        reloj = _reloj_del_servidor(carpeta)
        nombres = os.listdir(carpeta)
    except OSError:
        return
    for n in nombres:
        es_reclamo = SUFIJO_RECLAMO in n and (n.endswith(SUFIJO_RECLAMO) or n.rsplit(".", 1)[-1].isdigit())
        if n.startswith(PREFIJO_FRANJA) and (n.endswith(SUFIJO_HECHA) or es_reclamo):
            limite = EDAD_MAXIMA_MARCAS_S
        elif (n.startswith(PREFIJO_FRANJA) and n.endswith(".tmp")) or _es_provisional(n):
            limite = EDAD_MAXIMA_PROVISIONAL_S
        else:
            continue
        ruta = os.path.join(carpeta, n)
        try:
            if reloj - os.stat(ruta).st_mtime > limite:
                _quitar(ruta)
        except OSError:
            pass


def respaldar_al_cerrar(usuario=None, ruta_origen=None, carpeta_destino=None, max_copias=MAX_RESPALDOS, ahora=None):
    """A lo sumo UN respaldo por franja del dia (mañana: antes de `HORA_DE_CORTE`; tarde: desde ella) y por base de datos, hecho en
    el primer cierre de la franja (RB.2, decision D2 del fisico: "maximo dos por dia"). Nunca lanza: devuelve la ruta de la copia
    si este cierre la hizo, o `None` (la franja ya estaba hecha o la esta haciendo otro equipo, o la copia no se pudo hacer: en ese
    caso la franja NO queda consumida y el siguiente cierre reintenta).

    Pasos: (1) si existe la marca `.hecha` de la franja, nada; (2) se crea el reclamo en EXCLUSIVA (si hay uno reciente, otro la
    esta haciendo: nada; si el ultimo es viejo, se retoma con la generacion siguiente, tambien en exclusiva); (3) se vuelve a mirar
    si entretanto aparecio la `.hecha` (otro termino entre el paso 1 y el 2): se suelta el reclamo y nada; (4) `respaldar_bd`: si
    sale bien, el reclamo pasa a `.hecha`; si falla, se retira; (5) se retiran las marcas viejas.

    La franja y el nombre del respaldo salen de la hora del SERVIDOR de archivos de la carpeta (`_hora_segun_el_servidor`), no del reloj de
    este equipo (C1 de la revision): asi, equipos con la hora distinta -- y con otra zona horaria, se lee en `ZONA_DEL_SERVICIO` -- se ponen de acuerdo en la franja. Con `ahora` se fija la hora.

    `respaldar_bd` directo (el respaldo previo a una migracion, F1) NO se limita. Si un equipo se cae entre hacer la copia y dejar
    la `.hecha`, a los 10 minutos otro cierre puede hacer una segunda: se acepta."""
    try:
        if ruta_origen is None:
            ruta_origen = _conection.ruta_base_datos()
        if not os.path.isfile(ruta_origen):
            _avisar(f"[respaldo] no existe la BD de origen, no se respalda: {ruta_origen}")
            return None
        if carpeta_destino is None:
            carpeta_destino = carpeta_respaldos(ruta_origen)
        os.makedirs(carpeta_destino, exist_ok=True)
        if ahora is None:
            ahora = _hora_segun_el_servidor(carpeta_destino)          # C1: la franja sale del reloj del servidor, no del de este equipo

        franja = franja_de(ahora)
        hecha = _marca_de_franja(carpeta_destino, franja, SUFIJO_HECHA)
        if os.path.exists(hecha):
            return None
        _punto("tras_mirar_hecha")
        reclamo = _reclamar(carpeta_destino, franja, ahora)
        if reclamo is None:
            return None
        _punto("tras_reclamar")
        destino = None
        try:
            if os.path.exists(hecha):
                return None
            _punto("antes_de_respaldar")
            destino = respaldar_bd(usuario=usuario, ruta_origen=ruta_origen, carpeta_destino=carpeta_destino,
                                   max_copias=max_copias, ahora=ahora)
            return destino
        finally:
            if destino is not None:
                _consumir(reclamo, hecha, carpeta_destino, franja)
                _limpiar_marcas(carpeta_destino)
            else:
                _quitar(reclamo)
    except Exception as ex:
        _avisar(f"[respaldo] no se pudo respaldar al cerrar: {ex}", ex)
        return None
