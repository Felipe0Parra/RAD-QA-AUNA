"""B.2 (PLAN_REFERENCIAS_EDITABLES_21-09.md): único punto de escritura y
lectura de `referencias_qc` -- las líneas base y valores de referencia
(calidad de haz, dosis, tolerancias) editables desde la app.

El permiso se comprueba AQUÍ, no solo en la UI (mismo patrón que
`services/gestion_usuarios.py`, U3): ocultar un botón no es un control de
acceso -- ninguna ruta futura (otra pantalla, un script) puede saltárselo.

Las lecturas (`leer_referencia`/`listar_vigentes`/`historial`) no llevan
permiso -- el físico lo pidió explícito: "todos pueden ver". Solo
`fijar_referencia` exige `es_fisico_jefe`.

`leer_referencia` devuelve `None` cuando no hay referencia -- NUNCA un
valor por defecto silencioso; ese respaldo ya existe donde corresponde
(A.1: `VALORES_REFERENCIA_CALIDAD_RESPALDO`), no aquí.

`fijar_referencia` nunca hace `UPDATE` en sitio: anula la vigente e
inserta la nueva vía `reemplazar_bloque` (EB1, DA-52) -- la anterior queda
recuperable en `historial()`, y la auditoría se escribe en la MISMA
transacción que el reemplazo.
"""
import math
from datetime import datetime

from data.ManejoDatos.conection import Conexion
from services.anulacion import filtro_activo, reemplazar_bloque
from services.audit_minimo import ACCION_REEMPLAZO, registrar as _registrar_auditoria
from services.permisos import es_fisico_jefe

TABLA = "referencias_qc"
COLUMNAS = ("id", "equipo", "magnitud", "energia", "valor", "unidad",
            "fuente", "observaciones", "fijada_por", "fecha")

DENEGADO_SIN_PERMISO = "denegado: solo el físico jefe puede fijar una referencia"
FUENTE_OBLIGATORIA = "la fuente es obligatoria"
OBSERVACIONES_OBLIGATORIAS = "las observaciones son obligatorias"
VALOR_INVALIDO = "el valor debe ser un número mayor que cero"


def _nombre_completo(cursor, username):
    """Resuelve el fullname de `username` (columna `user`, login) para
    auditar con la MISMA identidad que el resto del audit_log (A6.2-bis) --
    si no se resuelve, se audita con el propio login en vez de perder el
    rastro. Idéntico a services/gestion_usuarios.py::_nombre_completo."""
    cursor.execute("SELECT fullname FROM users WHERE user=?", (username,))
    fila = cursor.fetchone()
    return fila[0] if fila else username


def _normalizar_energia(energia):
    """§1.3 del plan: la clave de bloque es (equipo, magnitud, energia) --
    `energia` guarda '' (nunca NULL/None) cuando la magnitud no depende de
    la energía. En SQLite dos NULL no colisionan en el índice UNIQUE, así
    que None dejaría esas filas sin proteger."""
    return "" if energia is None else energia


def leer_referencia(equipo, magnitud, energia=""):
    """La referencia VIGENTE para (equipo, magnitud, energia), como dict,
    o `None` si no hay ninguna fijada todavía."""
    energia = _normalizar_energia(energia)
    # El filtro va como `{filtro_activo(...)}` DENTRO de un f-string: es la
    # única forma que el analizador de lectura vigente (AN1/ES1) reconoce
    # como "filtra activo" -- `sql += filtro_activo(...)` lo ve opaco.
    sql = (f"SELECT id, equipo, magnitud, energia, valor, unidad, fuente, "
           f"observaciones, fijada_por, fecha FROM referencias_qc "
           f"WHERE equipo=? AND magnitud=? AND energia=?{filtro_activo('referencias_qc')}")
    with Conexion().conectar() as db:
        cursor = db.cursor()
        cursor.execute(sql, (equipo, magnitud, energia))
        fila = cursor.fetchone()
        return dict(zip(COLUMNAS, fila)) if fila is not None else None


def listar_vigentes():
    """Todas las referencias VIGENTES -- para la pestaña (C.1), que las
    lista con su fuente y observación."""
    sql = (f"SELECT id, equipo, magnitud, energia, valor, unidad, fuente, "
           f"observaciones, fijada_por, fecha FROM referencias_qc WHERE 1=1"
           f"{filtro_activo('referencias_qc')} ORDER BY equipo, magnitud, energia")
    with Conexion().conectar() as db:
        cursor = db.cursor()
        cursor.execute(sql)
        return [dict(zip(COLUMNAS, fila)) for fila in cursor.fetchall()]


def historial(equipo, magnitud, energia=""):
    """TODAS las filas (vigentes e históricas) de esa clave de bloque, más
    recientes primero -- para que el jefe compruebe quién cambió qué y
    cuándo (puerta de salida del plan, paso 8). Incluye `activo` a
    propósito: es la única de las cuatro funciones que lo hace, porque aquí
    SÍ importa distinguir cuál fila es la vigente entre varias."""
    energia = _normalizar_energia(energia)
    with Conexion().conectar() as db:
        cursor = db.cursor()
        # Lectura CENSAL a propósito (contrato, regla 5, excepción explícita):
        # el historial de una clave es justo lo que `filtro_activo` esconde.
        cursor.execute(
            "SELECT id, equipo, magnitud, energia, valor, unidad, fuente, "
            "observaciones, fijada_por, fecha, activo FROM referencias_qc "
            "WHERE equipo=? AND magnitud=? AND energia=? ORDER BY id DESC",
            (equipo, magnitud, energia))
        columnas = COLUMNAS + ("activo",)
        return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def _valor_valido(valor):
    """Un número finito y positivo: una referencia de calidad o de dosis
    entra como divisor en la discrepancia (A.1), y una tolerancia de cero
    o negativa no tiene sentido físico. Se valida aquí, en la frontera del
    servicio, no en cada pantalla."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v > 0 else None


def fijar_referencia(equipo, magnitud, energia, valor, fuente, observaciones,
                      username_solicitante, unidad=None):
    """Anula la referencia vigente para (equipo, magnitud, energia), si la
    hay, e inserta la nueva. Exige `es_fisico_jefe(username_solicitante)` --
    si el rol no resuelve o no es jefe/admin, se deniega y se audita el
    intento (mismo criterio que `gestion_usuarios.dar_de_baja`).

    `fuente` y `observaciones` son obligatorias (C.1: el jefe debe decir de
    dónde salió el número, no solo teclearlo) -- validado aquí y no solo en
    la pantalla, por la misma razón que el permiso. `valor` debe ser un
    número finito mayor que cero (`VALOR_INVALIDO` si no). `unidad` es
    opcional y solo informativa.

    Devuelve `(True, None)` si se fijó, o `(False, motivo)` si no."""
    energia = _normalizar_energia(energia)
    with Conexion().conectar() as db:
        cursor = db.cursor()
        nombre_solicitante = _nombre_completo(cursor, username_solicitante)

        if not es_fisico_jefe(username_solicitante):
            _registrar_auditoria(
                nombre_solicitante, ACCION_REEMPLAZO, TABLA,
                ref=f"{equipo}/{magnitud}/{energia}", detalle=DENEGADO_SIN_PERMISO)
            return False, DENEGADO_SIN_PERMISO

        if not fuente or not str(fuente).strip():
            return False, FUENTE_OBLIGATORIA
        if not observaciones or not str(observaciones).strip():
            return False, OBSERVACIONES_OBLIGATORIAS
        valor = _valor_valido(valor)
        if valor is None:
            return False, VALOR_INVALIDO

        clave = [("equipo", equipo), ("magnitud", magnitud), ("energia", energia)]
        sql_insert = (
            f"INSERT INTO {TABLA} (equipo, magnitud, energia, valor, unidad, "
            "fuente, observaciones, fijada_por, fecha) VALUES (?,?,?,?,?,?,?,?,?)")
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fila = (equipo, magnitud, energia, valor, unidad, fuente, observaciones,
                 nombre_solicitante, fecha)

        reemplazar_bloque(
            cursor, TABLA, clave, sql_insert, [fila], nombre_solicitante,
            ref=f"{equipo}/{magnitud}/{energia}",
            detalle=f"{magnitud} {equipo} {energia or '(global)'}: {valor} ({fuente})")
        db.commit()
        return True, None
