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
import shutil
from datetime import datetime

from data.ManejoDatos import conection as _conection
from services import audit_minimo

PREFIJO_RESPALDO = "BaseDatosQA_"
SUFIJO_RESPALDO = ".db"
NOMBRE_CARPETA_RESPALDOS = "respaldos_bd"
# N~10 (decisión del plan §17): historial suficiente para volver varias
# sesiones atrás sin que la carpeta crezca sin límite (~10 x tamaño de la BD).
MAX_RESPALDOS = 10


def carpeta_respaldos(ruta_origen=None):
    """Carpeta de respaldos: `respaldos_bd/` junto al archivo de la BD."""
    if ruta_origen is None:
        ruta_origen = _conection.ruta_base_datos()
    return os.path.join(os.path.dirname(os.path.abspath(ruta_origen)),
                        NOMBRE_CARPETA_RESPALDOS)


def _nombres_respaldo(carpeta):
    """Respaldos presentes en la carpeta, ordenados del más viejo al más
    reciente. El nombre fechado (YYYY-MM-DD_HHMMSS, con ceros a la izquierda)
    hace que el orden alfabético SEA el cronológico -- no se depende del mtime,
    que una copia manual de la carpeta puede alterar."""
    try:
        nombres = [n for n in os.listdir(carpeta)
                   if n.startswith(PREFIJO_RESPALDO) and n.endswith(SUFIJO_RESPALDO)]
    except OSError:
        return []
    return sorted(nombres)


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
                 max_copias=MAX_RESPALDOS, motivo=MOTIVO_CIERRE_APP):
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
        marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        base = f"{PREFIJO_RESPALDO}{marca}"
        existentes = _nombres_respaldo(carpeta_destino)
        tope = existentes[-1] if existentes else ""
        nombre = base + SUFIJO_RESPALDO
        contador = 2
        while nombre <= tope:
            nombre = f"{base}_{contador:02d}{SUFIJO_RESPALDO}"
            contador += 1
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
