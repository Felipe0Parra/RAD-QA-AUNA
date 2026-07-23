"""Audit trail mínimo (H2.4, auditoría 2026-07-14): quién/qué/cuándo en los
puntos de guardado.

NO revive el diseño comentado de `services/auditorias.py`/`decoradores_audit.py`
(AuditEngine con QObject/señales/excepthook -- sobredimensionado para lo que
hace falta hoy). `ui/paginasGuia/console_logs.py` sigue huérfano tal cual
(arreglar su visor es una fase futura, no parte de H2.4).

Principio de diseño: la inserción es SIEMPRE best-effort. Un fallo al
registrar la auditoría (BD bloqueada, columna inesperada, lo que sea) NUNCA
debe impedir ni revertir el guardado principal que la originó -- por eso todo
el cuerpo de `registrar()` va en try/except con un simple print, sin relanzar.
"""
import sqlite3
import traceback
from datetime import datetime

# Se importa el MÓDULO, no la función (`from ... import ruta_base_datos`
# capturaría el objeto función tal como es al importar `audit_minimo` --
# si un test más tarde parchea `conection_mod.ruta_base_datos` con
# monkeypatch, esa referencia ya capturada NO vería el parche y `registrar()`
# escribiría en la ruta real de desarrollo en vez de la BD temporal del
# test. Referenciar el módulo y resolver el atributo en cada llamada
# (`_conection.ruta_base_datos()`) sí ve cualquier parche vigente).
from data.ManejoDatos import conection as _conection

_DDL_AUDIT_LOG = """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        usuario TEXT,
        accion TEXT NOT NULL,
        tabla TEXT,
        ref TEXT,
        detalle TEXT
    )
"""

# A5 (PLAN_AUDITORIA_DOS_EJES_21-07): vocabulario cerrado de acciones -- antes
# cada call-site escribía su propio string suelto ("guardar", "eliminar"...);
# un typo nuevo (p.ej. "elimnar") habría quedado invisible en `audit_log` sin
# que nada lo detectara. Cubre exactamente los 7 verbos ya en uso.
ACCION_GUARDAR = "guardar"
ACCION_REEMPLAZO = "reemplazo"
ACCION_ACTUALIZAR = "actualizar"
ACCION_EDITAR = "editar"
ACCION_ELIMINAR = "eliminar"
# C2 (PLAN_INTEGRIDAD_MENSUAL_Y_RUTAS_23-07.md / PLAN_AUDITORIA_DOS_EJES_21-07
# §7 P4): "eliminar" un control (la raíz de la jerarquía mensual/anual/CT) ya
# no es un DELETE físico -- es anular (activo=0), recuperable. Un verbo
# propio evita que el audit_log confunda "se anuló, el dato sigue ahí" con
# "se borró de verdad, sin rastro" (que sigue aplicando a tablas de detalle
# y catálogos, fuera del alcance de esta tarea).
ACCION_ANULAR = "anular"
ACCION_LOGIN = "login"
ACCION_LOGOUT = "logout"
# A8 (§8.1 H3, PLAN_AUDITORIA_DOS_EJES_21-07): re-autenticación para AUTORIZAR
# una operación (los diálogos DialogAdminPermiso*), no para iniciar sesión.
# Antes usaba ACCION_LOGIN y ensuciaba el rastro: 36 de 72 filas del audit_log
# del rebuild 22-07 eran "login", la mitad de ellas simples confirmaciones de
# permiso -- el físico las leía como "mi borrado quedó registrado como login".
ACCION_AUTORIZACION = "autorizacion"


def usuario_actual(obj):
    """Nombre del usuario logueado, leído de `obj.user_id._nombre`.

    Centraliza el patrón `getattr(getattr(obj, "user_id", None), "_nombre",
    None)` que estaba copiado igual en cada call-site de guardado (equipos,
    mensuales) -- un único lugar para resolverlo reduce el riesgo de que un
    call-site nuevo lo haga distinto y termine con `usuario=NULL` en
    `audit_log` (A1, PLAN_AUDITORIA_DOS_EJES_21-07.md). Devolver None si no
    existe es preferible a reventar, igual que `registrar()`: la auditoría
    es best-effort.
    """
    return getattr(getattr(obj, "user_id", None), "_nombre", None)


def registrar(usuario, accion, tabla=None, ref=None, detalle="", ruta_db=None):
    """Inserta una fila en audit_log. Nunca lanza (ver docstring del módulo).

    Args:
        usuario: nombre del físico (p.ej. self.user_id._nombre) o None si no
            hay uno disponible en el contexto que llama (mejor registrar sin
            usuario que no registrar nada).
        accion: verbo corto ("guardar", "reemplazar", "actualizar"...).
        tabla: tabla de destino del guardado que se está auditando.
        ref: identificador de la fila/registro (fecha+acelerador, id, etc.).
            Se guarda como texto -- este campo es solo trazabilidad, no FK.
        detalle: contexto adicional libre, opcional.
        ruta_db: ruta de la BD a auditar. Si es None, se resuelve con
            `data.ManejoDatos.conection.ruta_base_datos()` -- correcto para
            todo lo que guarda vía `Conexion().conectar()` (load.py,
            equipos.py, formularios mensuales). La calculadora de dosis
            guarda por un camino APARTE (`DosisService`, su propia conexión
            -- el "doble patrón de conexión" ya documentado, pendiente de
            unificar en H2.5): sus llamadores deben pasar explícitamente la
            ruta que YA resuelve ese camino, para que la auditoría caiga en
            la MISMA base que el guardado que la originó (y para que los
            tests que aíslan esa ruta con monkeypatch aíslen también esto).
    """
    try:
        # Timestamp en ISO 8601 (no dd/MM/yyyy): ordena correctamente como
        # texto y evita la ambigüedad de fechas mixtas ya detectada en el
        # catálogo de equipos (H2.6, "5/02/2024" vs "05/02/2024").
        marca = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ruta = ruta_db if ruta_db is not None else _conection.ruta_base_datos()
        con = sqlite3.connect(ruta)
        try:
            cur = con.cursor()
            cur.execute(_DDL_AUDIT_LOG)
            cur.execute(
                "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (marca, usuario, accion, tabla,
                 str(ref) if ref is not None else None, detalle))
            con.commit()
        finally:
            con.close()
    except Exception as e:
        print(f"[audit_minimo] no se pudo registrar auditoría ({accion}/{tabla}): {e}")
        traceback.print_exc()
