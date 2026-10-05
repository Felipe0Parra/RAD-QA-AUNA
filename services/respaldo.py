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
`checkpoint_wal()` PRIMERO, respaldo después -- así el .db copiado ya contiene
todos los commits que vivían en el "-wal" (lección R2).
"""

import os
import re
import shutil
from datetime import datetime, timedelta

from data.ManejoDatos import conection as _conection
from services import audit_minimo

PREFIJO_RESPALDO = "BaseDatosQA_"
SUFIJO_RESPALDO = ".db"
NOMBRE_CARPETA_RESPALDOS = "respaldos_bd"
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


def _rotar(carpeta, max_copias):
    """Elimina los respaldos más viejos hasta dejar `max_copias`."""
    nombres = _nombres_respaldo(carpeta)
    for nombre in nombres[:-max_copias] if max_copias > 0 else nombres:
        try:
            os.remove(os.path.join(carpeta, nombre))
        except OSError as ex:
            print(f"[respaldo] no se pudo rotar {nombre}: {ex}")


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
    """
    try:
        if ruta_origen is None:
            ruta_origen = _conection.ruta_base_datos()
        if not os.path.isfile(ruta_origen):
            print(f"[respaldo] no existe la BD de origen, no se respalda: {ruta_origen}")
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

        shutil.copy2(ruta_origen, destino)
        _rotar(carpeta_destino, max_copias)

        audit_minimo.registrar(
            usuario, audit_minimo.ACCION_GUARDAR, tabla="backup",
            ref=os.path.basename(destino),
            detalle=f"{motivo}: {destino}",
            ruta_db=ruta_origen)
        print(f"Respaldo de la base de datos creado en: {destino}")
        return destino
    except Exception as ex:
        print(f"[respaldo] no se pudo respaldar la base de datos: {ex}")
        return None
