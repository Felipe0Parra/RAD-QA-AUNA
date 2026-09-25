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

F.1 (PLAN_HANDOFF_IMAGENES_22-09.md): una referencia dice EN QUÉ UNIDAD está y
QUIÉN LA FIRMA. Las 10 filas fijadas el 22-09 quedaron con `unidad = NULL` y
`fijada_por = 'Administrador'` (una cuenta que no es un físico: `role = NULL`).
Ahora la unidad es obligatoria (con la de la magnitud por omisión) y
`fijada_por` es siempre un FÍSICO MÉDICO ACTIVO: la propia cuenta si lo es, o el
que se elija como responsable -- igual que la aplicación ya pide el segundo
físico. Quién PUEDE escribir sigue siendo `es_fisico_jefe` de la cuenta que
actúa, y la auditoría sigue registrando a esa cuenta: cambiar quién firma no
afloja quién escribe.
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
UNIDAD_OBLIGATORIA = "la unidad es obligatoria"
RESPONSABLE_OBLIGATORIO = "debe indicar el físico responsable"
RESPONSABLE_INVALIDO = "el responsable no es un físico médico activo"

# La unidad de cada magnitud que la pestaña ofrece, escrita SIN corchetes (los corchetes son de presentación). La
# calidad del haz (PDD 20/10 en fotones, J2/J1 en electrones) es un cociente: adimensional, "1".
UNIDAD_POR_MAGNITUD = {"calidad": "1"}

CARGO_FISICO = "Físico Médico"       # `users.role`: el cargo mostrado (no `rol_sistema`, que es el permiso)


def _nombre_completo(cursor, username):
    """Resuelve el fullname de `username` (columna `user`, login) para
    auditar con la MISMA identidad que el resto del audit_log (A6.2-bis) --
    si no se resuelve, se audita con el propio login en vez de perder el
    rastro. Idéntico a services/gestion_usuarios.py::_nombre_completo."""
    cursor.execute("SELECT fullname FROM users WHERE user=?", (username,))
    fila = cursor.fetchone()
    return fila[0] if fila else username


def _fisicos_activos(cursor):
    """{nombre sin espacios sobrantes: nombre tal como se guarda} de los físicos médicos ACTIVOS. `COALESCE(active,1)`: un
    NULL histórico no oculta a nadie (mismo criterio que el selector de físicos del mensual, U2)."""
    cursor.execute("SELECT fullname FROM users WHERE role = ? AND COALESCE(active,1)=1 ORDER BY fullname",
                   (CARGO_FISICO,))
    return {nombre.strip(): nombre for (nombre,) in cursor.fetchall() if nombre}


def nombre_de_usuario(username):
    """El `fullname` de la cuenta `username` (como figura en `users`), o `None` si no existe."""
    if not username:
        return None
    with Conexion().conectar() as db:
        cursor = db.cursor()
        cursor.execute("SELECT fullname FROM users WHERE user=?", (username,))
        fila = cursor.fetchone()
        return fila[0] if fila else None


def fisicos_responsables():
    """Los físicos médicos activos que pueden figurar como responsables de una referencia, con su nombre tal como se
    guarda en `fijada_por`. La pestaña los ofrece; el servicio los vuelve a comprobar."""
    with Conexion().conectar() as db:
        return list(_fisicos_activos(db.cursor()).values())


def _resolver_firmante(cursor, username_solicitante, responsable):
    """`(nombre, None)` con el físico que firma la referencia, o `(None, motivo)`. Si se eligió un responsable, debe ser un
    físico médico activo; si no, firma la propia cuenta, y solo si ES un físico médico activo (un administrador sin cargo
    de físico debe elegir a quién)."""
    activos = _fisicos_activos(cursor)
    elegido = str(responsable).strip() if responsable is not None else ""
    if elegido:
        return (activos[elegido], None) if elegido in activos else (None, RESPONSABLE_INVALIDO)
    propio = _nombre_completo(cursor, username_solicitante).strip()
    return (activos[propio], None) if propio in activos else (None, RESPONSABLE_OBLIGATORIO)


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
                      username_solicitante, unidad=None, responsable=None):
    """Anula la referencia vigente para (equipo, magnitud, energia), si la
    hay, e inserta la nueva. Exige `es_fisico_jefe(username_solicitante)` --
    si el rol no resuelve o no es jefe/admin, se deniega y se audita el
    intento (mismo criterio que `gestion_usuarios.dar_de_baja`).

    `fuente` y `observaciones` son obligatorias (C.1: el jefe debe decir de
    dónde salió el número, no solo teclearlo) -- validado aquí y no solo en
    la pantalla, por la misma razón que el permiso. `valor` debe ser un
    número finito mayor que cero (`VALOR_INVALIDO` si no).

    F.1: `unidad` es OBLIGATORIA -- si no se da, se usa la de la magnitud
    (`UNIDAD_POR_MAGNITUD`), y sin ninguna se rechaza (`UNIDAD_OBLIGATORIA`).
    `responsable` es el físico médico que firma; si no se da, firma la propia
    cuenta solo si es un físico médico activo (`RESPONSABLE_OBLIGATORIO` si no
    lo es), y uno que no es físico activo se rechaza (`RESPONSABLE_INVALIDO`).
    El permiso NO cambia: lo decide `es_fisico_jefe` de la cuenta que actúa,
    y la auditoría registra a esa cuenta, no al responsable.

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
        unidad = (str(unidad).strip() if unidad is not None else "") or UNIDAD_POR_MAGNITUD.get(magnitud)
        if not unidad:
            return False, UNIDAD_OBLIGATORIA
        firmante, motivo = _resolver_firmante(cursor, username_solicitante, responsable)
        if firmante is None:
            return False, motivo

        clave = [("equipo", equipo), ("magnitud", magnitud), ("energia", energia)]
        sql_insert = (
            f"INSERT INTO {TABLA} (equipo, magnitud, energia, valor, unidad, "
            "fuente, observaciones, fijada_por, fecha) VALUES (?,?,?,?,?,?,?,?,?)")
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fila = (equipo, magnitud, energia, valor, unidad, fuente, observaciones,
                 firmante, fecha)
        quien = "" if firmante == nombre_solicitante else f"; responsable: {firmante}"

        reemplazar_bloque(
            cursor, TABLA, clave, sql_insert, [fila], nombre_solicitante,
            ref=f"{equipo}/{magnitud}/{energia}",
            detalle=f"{magnitud} {equipo} {energia or '(global)'}: {valor} [{unidad}] ({fuente}){quien}")
        db.commit()
        return True, None
