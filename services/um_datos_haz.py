"""UM.3 (PLAN_CALCULADORA_UM_05-11.md, DC12, DA-95): la ÚNICA puerta a las dos tablas de los datos de haz de la calculadora de UM, `um_datos_haz` (raíz propia, sin FK, clave de bloque
(`equipo`, `energia`)) y `um_archivo_haz` (hija por `ref`, clave (`ref`, `accesorio`, `dato`)). Nadie más las escribe ni las lee (lo vigila el censo de la prueba nueva).

  - Se guarda el ARCHIVO TAL COMO SE EXPORTÓ (UM3-D1): sus bytes en un BLOB, con su BOM y sus finales de línea, y el sha256 de esos mismos bytes. Nunca números ya interpretados (un derivado no
    se almacena, regla del 09-09): `datos_del_haz` vuelve a leer lo guardado con el lector y el armado de hoy, que con los mismos bytes dan exactamente lo mismo que con los archivos directos.
  - El equipo y la energía se normalizan con la regla de UM.2 (`um_armar._claves_pedidas`: «600C», «6X» y «6 mv» son «Clinac 600» y «6 MV»), al escribir y al leer (UM3-D14); se guarda la
    clave canónica. Una forma que no se reconoce no se guarda, con su motivo, y al leer no encuentra nada.
  - `revisar` es la frontera de la carga (DC13) y la MISMA comprobación que hace `guardar` (UM3-D2): valida lo escrito, pasa cada archivo por `um_lector_eclipse.decodificar`, llama a
    `um_armar.revisar_archivos` y agrega al resumen la curva de Sc que usará el cálculo. Con un problema no se guarda nada; los avisos no lo impiden.
  - `guardar` exige `es_fisico_jefe` (DA-81; hoy, el jefe y el administrador: DA-35 no alcanza a esta función). Sin permiso se deniega y se audita la denegación, sin escribir nada más.
  - UNA transacción (`BEGIN IMMEDIATE`, DA-52): anula el conjunto vigente de la misma clave (`reemplazar_bloque`) y sus archivos, inserta el nuevo con los suyos y escribe UNA fila de auditoría
    (`guardar`, o `reemplazo` con el `id` del anterior). Si la fila de auditoría no queda escrita, o cualquier sentencia o el `commit` fallan, no queda nada: ni filas, ni el anterior anulado
    sin su reemplazo (DA-54). Lo anulado no se reactiva (DA-49). Un rechazo de la base se dice en español; su texto crudo va a la consola (UM3-D17).
  - Las lecturas van en UNA transacción de lectura (`BEGIN`: la raíz y sus archivos son de la misma foto de la base, aunque otro equipo guarde a la vez; UM3-D15) y según la selectividad
    (DA-47): `vigente`, `energias_cargadas` y `datos_del_haz` leen el bloque y filtran `activo` con `{filtro_activo(...)}` dentro del f-string; `historial` lee las dos ramas A PROPÓSITO
    (DA-48) y trae `activo` como dato. Dos conjuntos vigentes de la misma clave no deberían existir: si los hay, se dice (`DatosHazError`), no se elige uno.
  - Los JSON (`wf_escritos`, `curva_sc`) pasan por la puerta estricta (`services/json_estricto.py`). Las claves de `wf_escritos` son ángulos enteros: en un JSON vuelven como texto y aquí se
    normalizan antes de guardar, así que lo guardado y lo escrito arman el mismo haz.
  - Costo medido de `datos_del_haz`: de 46 a 63 ms por llamada (lee y arma los archivos guardados). No hay caché aquí: `vigente(...)["id"]` cambia con cada carga y sirve de clave a quien la
    quiera (UM.4, DC16).

Sin Qt."""
import hashlib
import json
import math
import numbers
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from data.ManejoDatos.conection import Conexion
from services import um_armar
from services import um_lector_eclipse as lector
from services.anulacion import filtro_activo, reemplazar_bloque
from services.audit_minimo import ACCION_GUARDAR, ACCION_REEMPLAZO
from services.audit_minimo import registrar as _registrar_auditoria
from services.json_estricto import json_estricto
from services.permisos import es_fisico_jefe
from services.referencias_qc import nombre_de_usuario

TABLA_DATOS_HAZ = "um_datos_haz"
_COLUMNAS = ("equipo", "energia", "d0_dmax", "d0_tabla", "d0_origen", "wf_escritos", "curva_sc", "sc_origen", "observaciones", "usuario", "fecha_registro")
_COLUMNAS_ARCHIVO = ("ref", "accesorio", "dato", "nombre_archivo", "sha256", "contenido")
SQL_INSERT = f"INSERT INTO um_datos_haz ({', '.join(_COLUMNAS)}) VALUES ({', '.join('?' * len(_COLUMNAS))})"
SQL_INSERT_ARCHIVO = f"INSERT INTO um_archivo_haz ({', '.join(_COLUMNAS_ARCHIVO)}) VALUES ({', '.join('?' * len(_COLUMNAS_ARCHIVO))})"
_LEIDAS = "id, " + ", ".join(_COLUMNAS)          # columnas explícitas (MI0); por nombre, nunca `SELECT *`

DENEGADO = "denegado: solo el físico jefe o el administrador pueden cargar las tablas de un acelerador"
NO_SE_GUARDA = "No se guardó nada: "
USUARIO_INVALIDO = "falta el usuario que carga las tablas, o no es un texto"
SIN_BASE = "no se pudo abrir la base de datos (¿la carpeta de red está disponible?)"
# UM3-D17: lo que se dice cuando la base no acepta el guardado, por causa conocida; el texto crudo de SQLite (en inglés) va a la consola, no a la pantalla.
RECHAZOS_DE_LA_BASE = (("locked", "la base de datos está ocupada por otro guardado: espere un momento y vuelva a intentarlo"),
                       ("readonly", "la base de datos es de solo lectura en este equipo"),
                       ("full", "no queda espacio en el disco de la base de datos"))
RECHAZO_GENERICO = "la base de datos no aceptó el guardado"
SIN_AUDITORIA = "no se pudo escribir la fila de auditoría"


class DatosHazError(ValueError):
    """Lo guardado no se puede usar (dañado, el lector de hoy ya no lo entiende, dos vigentes de la misma clave, o la base no se abre): se dice por qué, nunca se cae en silencio a «no hay
    tablas»."""


class _Rechazo(ValueError):
    """Un dato de la carga que no se entiende: es un problema de la revisión y no se guarda nada."""


class _SinAuditoria(RuntimeError):
    """La fila de auditoría no quedó escrita (`audit_minimo.registrar` no relanza): sin ella no se guarda nada."""


@contextmanager
def _conexion():
    """La conexión de la app (`Conexion().conectar()`), o `DatosHazError` si la base no se abre (devuelve None: una carpeta de red caída)."""
    db = Conexion().conectar()
    if db is None:
        raise DatosHazError(SIN_BASE)
    with db as con:
        yield con


@contextmanager
def _lectura():
    """Un cursor dentro de UNA transacción de lectura (UM3-D15): todo lo que se lee sale de la misma foto de la base. Se suelta sin escribir nada."""
    with _conexion() as con:
        con.execute("BEGIN")
        yield con.cursor()


# ================================================================================================================================== la frontera

def _real(valor, que):
    """Un número real y finito (también un escalar de numpy), nunca un booleano ni un texto; o `_Rechazo`. Un entero que no cabe en un float (10**400) también es un rechazo."""
    if isinstance(valor, bool) or not isinstance(valor, numbers.Real):
        raise _Rechazo(f"{que} debe ser un número")
    try:
        convertido = float(valor)
    except OverflowError:
        raise _Rechazo(f"{que} debe ser un número") from None
    if not math.isfinite(convertido):
        raise _Rechazo(f"{que} debe ser un número")
    return convertido


def _texto(valor, que, obligatorio):
    """Un texto sin los blancos de los lados, que se puede guardar (UTF-8, sin bytes nulos); None si falta y no es obligatorio."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if obligatorio:
            raise _Rechazo(f"falta {que}")
        return None
    if not isinstance(valor, str):
        raise _Rechazo(f"{que} debe ser un texto")
    texto = valor.strip()
    try:
        texto.encode("utf-8")
    except UnicodeEncodeError as fallo:
        raise _Rechazo(f"{que} trae caracteres que no se pueden guardar") from fallo
    if "\x00" in texto:
        raise _Rechazo(f"{que} trae caracteres que no se pueden guardar")
    return texto


def _clave(equipo, energia):
    """La clave canónica, con la regla de UM.2 (`um_armar._claves_pedidas`, la misma que usa `datos_haz`): una sola normalización para escribir y para leer (UM3-D14)."""
    try:
        return um_armar._claves_pedidas(equipo, energia)
    except ValueError as fallo:
        raise _Rechazo(str(fallo)) from fallo


def _clave_o_nada(equipo, energia):
    """Para leer: la clave canónica, o None si el lector no reconoce la forma (no hay nada guardado con ella)."""
    try:
        return um_armar._claves_pedidas(equipo, energia)
    except ValueError:
        return None


def _d0(d0_dmax, d0_tabla):
    dmax = None if d0_dmax is None else _real(d0_dmax, "D'0 en dmax")
    tabla = None if d0_tabla is None else _real(d0_tabla, "D'0 en las condiciones de la tabla")
    if (dmax is None) == (tabla is None):
        raise _Rechazo("se escribe D'0 en dmax o en las condiciones de la tabla, uno de los dos")
    return dmax, tabla


def _factores_de_cuna(wf_escritos):
    """{ángulo entero: WF}. La regla es la de UM.2 (`um_armar._factores_escritos`: un entero o el texto de sus cifras; «15.0», 15.5 y True no), escrita aquí porque la de UM.2 deja escapar
    un `OverflowError` con un WF de 10**400 y la prueba compara las dos reglas (C4 de la auditoría)."""
    if wf_escritos is None:
        return {}
    if not isinstance(wf_escritos, dict):
        raise _Rechazo("los factores de cuña escritos deben ser {ángulo: factor}")
    salida = {}
    for angulo, wf in wf_escritos.items():
        if isinstance(angulo, numbers.Integral) and not isinstance(angulo, bool):
            grados = int(angulo)
        elif isinstance(angulo, str) and re.fullmatch(r"[0-9]+", angulo):
            grados = int(angulo)
        else:
            raise _Rechazo(f"el ángulo «{angulo}» de los factores de cuña escritos no es un número entero de grados")
        if grados in salida:
            raise _Rechazo(f"hay dos factores escritos para la cuña de {grados}°")
        salida[grados] = _real(wf, f"el factor escrito de la cuña de {grados}°")
    return salida


def _curva_de_sc(curva_sc, sc_origen):
    """None (la curva de omisión, DC3, que calcula el armado y dice su origen), () o [] (sin corrección) o la curva propia, con su origen escrito (PC-14: solo la PROPIA lo pide;
    UM3-D11). Los pares los comprueba `um_armar.curva_de_sc` (la regla de UM.2)."""
    if curva_sc is None or (isinstance(curva_sc, (list, tuple)) and not curva_sc):
        if _texto(sc_origen, "el origen de la curva de Sc", False) is not None:
            raise _Rechazo("el origen de la curva de Sc solo se escribe con una curva propia")
        return (None if curva_sc is None else ()), None
    if not isinstance(curva_sc, (list, tuple)) or not all(isinstance(p, (list, tuple)) and len(p) == 2 for p in curva_sc):
        raise _Rechazo("la curva de Sc debe ser una lista de pares (lado, valor)")
    pares = [(_real(j, "el lado de la curva de Sc"), _real(v, "el valor de la curva de Sc")) for j, v in curva_sc]
    try:
        curva = um_armar.curva_de_sc(pares)
    except ValueError as fallo:
        raise _Rechazo(str(fallo)) from fallo
    return curva, _texto(sc_origen, "el origen de la curva de Sc", True)


def _archivos(archivos):
    """[(nombre, bytes)] -> [(nombre, bytes, texto o None, problema o None)]. Los nombres no se repiten: con dos iguales no se sabría cuál guardar (la pantalla da la ruta completa)."""
    if not isinstance(archivos, (list, tuple)) or not archivos:
        raise _Rechazo("no hay archivos que cargar")
    salida, nombres = [], set()
    for par in archivos:
        if not isinstance(par, (list, tuple)) or len(par) != 2:
            raise _Rechazo("cada archivo se da como (nombre, contenido)")
        nombre = _texto(par[0], "el nombre de un archivo", True)
        if nombre in nombres:
            raise _Rechazo(f"hay dos archivos con el mismo nombre «{nombre}»: dé la ruta completa de cada uno")
        nombres.add(nombre)
        if not isinstance(par[1], (bytes, bytearray)):
            raise _Rechazo(f"{nombre}: el contenido debe ser el archivo tal como se leyó (bytes)")
        contenido = bytes(par[1])
        try:
            salida.append((nombre, contenido, lector.decodificar(contenido), None))
        except lector.ArchivoNoReconocido as fallo:
            salida.append((nombre, contenido, None, f"{nombre}: {fallo}"))
    return salida


def _avisos_de_sc(revision, leidos, equipo, energia, dmax, tabla, wf, sc, sc_origen):
    """La curva de Sc que usará el cálculo, para el resumen (DC13, punto 2): sus pares lado [cm] y Sc, o que la corrección está apagada."""
    usados = set(revision.usados)
    datos = um_armar.datos_haz([t for n, _, t, _ in leidos if n in usados], equipo, energia, dmax, tabla, wf, sc, sc_origen)
    if not datos.sc:
        return ("Curva de Sc que usa el cálculo: ninguna, la corrección de Sc está apagada.",)
    return ("Curva de Sc que usa el cálculo (lado [cm]: Sc): " + ", ".join(f"{j:g}: {v:.3f}" for j, v in datos.sc) + ".",)


def _carga(equipo, energia, archivos, d0_dmax, d0_tabla, d0_origen, wf_escritos, curva_sc, sc_origen, observaciones):
    """La revisión de una carga y lo que hace falta para guardarla: (Revision, {lo validado} o None). La ÚNICA comprobación, para `revisar` y para `guardar` (UM3-D2). Si lo escrito no
    se entiende, el resumen conserva igual qué archivos se usan y cuáles se ignoran (UM3-D16)."""
    try:
        equipo, energia = _clave(equipo, energia)
        leidos = _archivos(archivos)
    except _Rechazo as fallo:
        return um_armar.Revision((), (), (str(fallo),), ()), None
    malos = tuple(p for *_, p in leidos if p)
    if malos:
        return um_armar.Revision((), (), malos, ()), None
    textos = [(n, t) for n, _, t, _ in leidos]
    try:
        dmax, tabla = _d0(d0_dmax, d0_tabla)
        origen = _texto(d0_origen, "el origen de D'0", True)
        wf = _factores_de_cuna(wf_escritos)
        sc, sc_origen = _curva_de_sc(curva_sc, sc_origen)
        notas = _texto(observaciones, "el campo de observaciones", False)
    except _Rechazo as fallo:
        clasificados = um_armar.revisar_archivos(textos, equipo, energia, 1.0, None)
        return um_armar.Revision(clasificados.usados, clasificados.ignorados, (str(fallo),), ()), None
    revision = um_armar.revisar_archivos(textos, equipo, energia, dmax, tabla, wf, sc, sc_origen)
    if revision.problemas:
        return revision, None
    revision = um_armar.Revision(revision.usados, revision.ignorados, (), revision.avisos + _avisos_de_sc(revision, leidos, equipo, energia, dmax, tabla, wf, sc, sc_origen))
    return revision, {"equipo": equipo, "energia": energia, "d0_dmax": dmax, "d0_tabla": tabla, "d0_origen": origen, "wf": wf, "sc": sc, "sc_origen": sc_origen,
                      "observaciones": notas, "leidos": leidos}


def revisar(equipo, energia, archivos, d0_dmax, d0_tabla, wf_escritos=None, curva_sc=None, sc_origen=None, d0_origen=None, observaciones=None):
    """Lo que entendió la carga antes de guardar (`um_armar.Revision`: usados, ignorados, problemas y avisos), la MISMA comprobación que repite `guardar` (UM3-D2): con los mismos datos,
    `guardar` guarda si y solo si aquí no hay problemas. `archivos`: [(nombre, bytes del archivo tal como se leyó)]. El origen de D'0 es obligatorio también aquí."""
    return _carga(equipo, energia, archivos, d0_dmax, d0_tabla, d0_origen, wf_escritos, curva_sc, sc_origen, observaciones)[0]


# ================================================================================================================================== guardar

def _filas_de_los_archivos(revision, leidos):
    """Los archivos que el cálculo lee (`usados`: UM.2 no repite un mismo accesorio y dato), en el orden en que llegaron: (accesorio, dato, nombre, sha256, bytes)."""
    por_nombre = {n: (b, t) for n, b, t, _ in leidos}
    filas = []
    for nombre in revision.usados:
        contenido, texto = por_nombre[nombre]
        identidad = lector.identidad(texto)
        filas.append((identidad.accesorio, identidad.dato, nombre, hashlib.sha256(contenido).hexdigest(), contenido))
    return filas


def _auditar(db, usuario, accion, ref, detalle):
    """La fila de auditoría de la acción, en la MISMA transacción (`con=db`), y comprobada: `registrar` se traga su error por diseño, así que sin esta comprobación un guardado podría quedar
    sin su rastro."""
    cursor = db.cursor()
    (antes,) = cursor.execute("SELECT COALESCE(MAX(id), 0) FROM audit_log").fetchone()
    _registrar_auditoria(usuario, accion, TABLA_DATOS_HAZ, ref=ref, detalle=detalle, con=db)
    (escritas,) = cursor.execute("SELECT COUNT(*) FROM audit_log WHERE id > ? AND tabla = ? AND ref = ?", (antes, TABLA_DATOS_HAZ, str(ref))).fetchone()
    if not escritas:
        raise _SinAuditoria(SIN_AUDITORIA)


def _rechazo_de_la_base(fallo):
    """El motivo, en español, de un rechazo de la base (UM3-D17); el texto crudo va a la consola."""
    print(f"[um_datos_haz] la base rechazó el guardado: {type(fallo).__name__}: {fallo}")
    if isinstance(fallo, _SinAuditoria):
        return SIN_AUDITORIA
    crudo = str(fallo).lower()
    return next((motivo for clave, motivo in RECHAZOS_DE_LA_BASE if clave in crudo), RECHAZO_GENERICO)


def _auditar_denegacion(quien, equipo, energia):
    """La fila de la denegación, por la conexión de la app (su WAL y su espera, la de toda la app) y en su propia transacción (UM3-D18), con la clave canónica (UM3-D14) o, si el lector no la
    reconoce, con lo pedido. Si la base no la acepta, `registrar` lo dice en la consola: no hay nada más que deshacer."""
    with _conexion() as con:
        _registrar_auditoria(quien, ACCION_GUARDAR, TABLA_DATOS_HAZ, ref="{}/{}".format(*_clave_o_nada(equipo, energia) or (equipo, energia)), detalle=DENEGADO, con=con)
        con.commit()


def guardar(equipo, energia, archivos, d0_dmax, d0_tabla, d0_origen, wf_escritos, curva_sc, sc_origen, observaciones, usuario):
    """Guarda los datos de haz de (`equipo`, `energia`) y devuelve `(True, None, id)`, o `(False, motivo, None)` sin escribir nada (salvo la fila de auditoría de una denegación).

    `archivos`: [(nombre, bytes)], todos los de una energía (los que el cálculo no lee se ignoran y no se guardan). D'0 en dmax (`d0_dmax`) o en las condiciones de la tabla (`d0_tabla`), uno de
    los dos, con su origen escrito (`d0_origen`). `wf_escritos`: {ángulo: WF en 10 × 10 a d0}. `curva_sc`: None (la de omisión), () (sin corrección) o [(lado, valor)], con su `sc_origen`.
    `usuario`: el login de quien carga (el permiso es de esa cuenta; la fila y la auditoría llevan su nombre completo)."""
    login = usuario.strip() if isinstance(usuario, str) else None
    if not login:
        return False, USUARIO_INVALIDO, None
    try:                                    # A4: una carpeta de red caída da None; se dice antes de leer el usuario o el permiso (que también la abren). Sin una conexión pelada (R5)
        with _conexion():
            pass
    except DatosHazError:
        return False, NO_SE_GUARDA + SIN_BASE, None
    quien = nombre_de_usuario(login) or login
    if not es_fisico_jefe(login):
        _auditar_denegacion(quien, equipo, energia)
        return False, DENEGADO, None
    revision, v = _carga(equipo, energia, archivos, d0_dmax, d0_tabla, d0_origen, wf_escritos, curva_sc, sc_origen, observaciones)
    if v is None:
        return False, NO_SE_GUARDA + "; ".join(revision.problemas), None
    filas = _filas_de_los_archivos(revision, v["leidos"])
    fila = (v["equipo"], v["energia"], v["d0_dmax"], v["d0_tabla"], v["d0_origen"], json_estricto({str(a): wf for a, wf in sorted(v["wf"].items())}, "wf_escritos"),
            None if v["sc"] is None else json_estricto([list(p) for p in v["sc"]], "curva_sc"), v["sc_origen"], v["observaciones"], quien, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    d0, donde = (v["d0_dmax"], "en dmax") if v["d0_tabla"] is None else (v["d0_tabla"], "en las condiciones de la tabla")
    detalle = f"{v['equipo']} {v['energia']}: {len(filas)} archivos; D'0 = {d0:g} [cGy/UM] {donde} ({v['d0_origen']})"
    try:
        with _conexion() as con:
            con.execute("BEGIN IMMEDIATE")
            cursor = con.cursor()
            cursor.execute(f"SELECT id FROM um_datos_haz WHERE equipo = ? AND energia = ?{filtro_activo('um_datos_haz')} ORDER BY id", (v["equipo"], v["energia"]))
            previas = [ident for (ident,) in cursor.fetchall()]
            reemplazar_bloque(cursor, TABLA_DATOS_HAZ, [("equipo", v["equipo"]), ("energia", v["energia"])], SQL_INSERT, [fila], quien, auditar=False)
            nuevo_id = cursor.lastrowid
            for previa in previas:
                cursor.execute(f"UPDATE um_archivo_haz SET activo = 0 WHERE ref = ?{filtro_activo('um_archivo_haz')}", (previa,))
            cursor.executemany(SQL_INSERT_ARCHIVO, [(nuevo_id, *f) for f in filas])          # los archivos de un conjunto NUEVO: no hay bloque anterior bajo este `ref`
            _auditar(con, quien, ACCION_REEMPLAZO if previas else ACCION_GUARDAR, nuevo_id,
                     detalle + (f"; reemplaza id={', '.join(map(str, previas))}" if previas else ""))
            con.commit()
    except DatosHazError:
        return False, NO_SE_GUARDA + SIN_BASE, None
    except (sqlite3.Error, _SinAuditoria) as fallo:
        return False, NO_SE_GUARDA + _rechazo_de_la_base(fallo), None
    return True, None, nuevo_id


# ================================================================================================================================== lecturas

def _registro(fila, columnas):
    """La fila como dict, con los JSON convertidos (`wf_escritos` como {ángulo: WF}, `curva_sc` como tupla de pares o None); `DatosHazError` si lo guardado no se puede leer."""
    registro = dict(zip(columnas, fila))
    try:
        registro["wf_escritos"] = {int(a): float(wf) for a, wf in json.loads(registro["wf_escritos"]).items()}
        registro["curva_sc"] = None if registro["curva_sc"] is None else tuple((float(j), float(v)) for j, v in json.loads(registro["curva_sc"]))
    except (TypeError, ValueError, AttributeError) as fallo:
        raise DatosHazError(f"lo guardado del conjunto id={registro.get('id', '?')} no se puede usar: sus factores de cuña o su curva de Sc están dañados ({type(fallo).__name__})") from None
    return registro


_RESUMEN_DEL_ARCHIVO = ("accesorio", "dato", "nombre_archivo", "sha256", "bytes")


def _archivos_del_conjunto(cursor, ref, vigentes):
    """Los archivos de UN conjunto, en el orden en que se guardaron, sin su contenido. `vigentes`: solo los vigentes (la lectura del bloque, DA-47) o las dos ramas (el historial)."""
    if vigentes:
        cursor.execute(f"SELECT accesorio, dato, nombre_archivo, sha256, length(contenido) FROM um_archivo_haz WHERE ref = ?{filtro_activo('um_archivo_haz')} ORDER BY id", (ref,))
        return [dict(zip(_RESUMEN_DEL_ARCHIVO, f)) for f in cursor.fetchall()]
    cursor.execute("SELECT accesorio, dato, nombre_archivo, sha256, length(contenido), activo FROM um_archivo_haz WHERE ref = ? ORDER BY id", (ref,))
    return [dict(zip(_RESUMEN_DEL_ARCHIVO + ("activo",), f)) for f in cursor.fetchall()]


def _unico(filas, equipo, energia):
    """La fila del conjunto vigente, None si no hay, o `DatosHazError` si hay más de uno de la misma clave (no se elige: el número cambiaría sin aviso)."""
    if len(filas) > 1:
        raise DatosHazError(f"hay {len(filas)} conjuntos vigentes de {equipo}, {energia} (ids {', '.join(str(f[0]) for f in filas)}): la base no está como debe; cargue las tablas otra vez")
    return filas[0] if filas else None


def vigente(equipo, energia):
    """El conjunto VIGENTE de (`equipo`, `energia`), como dict (sus columnas, `wf_escritos` como {ángulo: WF}, `curva_sc` como tupla de pares o None, y `archivos`), o None si no hay (o si
    el lector no reconoce la forma del equipo o de la energía)."""
    clave = _clave_o_nada(equipo, energia)
    if clave is None:
        return None
    with _lectura() as cursor:
        cursor.execute(f"SELECT {_LEIDAS} FROM um_datos_haz WHERE equipo = ? AND energia = ?{filtro_activo('um_datos_haz')} ORDER BY id DESC", clave)
        fila = _unico(cursor.fetchall(), *clave)
        if fila is None:
            return None
        registro = _registro(fila, ("id",) + _COLUMNAS)
        registro["archivos"] = _archivos_del_conjunto(cursor, registro["id"], True)
        return registro


def _mv(energia):
    return float(energia.split()[0])


def energias_cargadas(equipo):
    """Las energías de `equipo` con un conjunto vigente, de la menor a la mayor («6 MV» antes que «10 MV»); [] si no hay ninguna o si el lector no reconoce el equipo."""
    equipo_k = lector.clave_equipo(equipo)
    if equipo_k is None:
        return []
    with _lectura() as cursor:
        cursor.execute(f"SELECT DISTINCT energia FROM um_datos_haz WHERE equipo = ?{filtro_activo('um_datos_haz')}", (equipo_k,))
        return sorted((energia for (energia,) in cursor.fetchall()), key=lambda e: (_mv(e), e))


def historial(equipo, energia):
    """TODOS los conjuntos de (`equipo`, `energia`), vigente y anulados, del más reciente al más antiguo, cada uno con `activo`, sus archivos (también anulados) y `problema` (None, o por qué
    lo guardado de ese conjunto no se puede leer: una fila dañada no esconde las demás). Lee las dos ramas A PROPÓSITO (DA-48): es justo lo que `filtro_activo` esconde."""
    clave = _clave_o_nada(equipo, energia)
    if clave is None:
        return []
    registros = []
    with _lectura() as cursor:
        cursor.execute(f"SELECT {_LEIDAS}, activo FROM um_datos_haz WHERE equipo = ? AND energia = ? ORDER BY id DESC", clave)
        for fila in cursor.fetchall():
            columnas = ("id",) + _COLUMNAS + ("activo",)
            try:
                registro = {**_registro(fila, columnas), "problema": None}
            except DatosHazError as fallo:
                registro = {**dict(zip(columnas, fila)), "wf_escritos": None, "curva_sc": None, "problema": str(fallo)}
            registros.append(registro)
        for registro in registros:
            registro["archivos"] = _archivos_del_conjunto(cursor, registro["id"], False)
    return registros


def datos_del_haz(equipo, energia):
    """El `um_motor.DatosHaz` del conjunto vigente, armado con lo guardado exactamente como `um_armar.datos_haz` arma los archivos directos; None si no hay conjunto vigente (o si el lector
    no reconoce la forma del equipo o de la energía). `DatosHazError` si lo guardado no se puede usar: un archivo que no coincide con su huella o con su accesorio y dato, una columna JSON
    dañada, dos conjuntos vigentes de la misma clave, o lo que el lector o el armado de hoy no entienden."""
    clave = _clave_o_nada(equipo, energia)
    if clave is None:
        return None
    with _lectura() as cursor:
        cursor.execute(f"SELECT id, d0_dmax, d0_tabla, wf_escritos, curva_sc, sc_origen FROM um_datos_haz WHERE equipo = ? AND energia = ?{filtro_activo('um_datos_haz')} ORDER BY id DESC",
                       clave)
        fila = _unico(cursor.fetchall(), *clave)
        if fila is None:
            return None
        cursor.execute(f"SELECT accesorio, dato, nombre_archivo, sha256, contenido FROM um_archivo_haz WHERE ref = ?{filtro_activo('um_archivo_haz')} ORDER BY id", (fila[0],))
        archivos = cursor.fetchall()
    registro = _registro(fila, ("id", "d0_dmax", "d0_tabla", "wf_escritos", "curva_sc", "sc_origen"))
    error = f"Las tablas guardadas de {clave[0]}, {clave[1]} no se pueden usar: "
    textos = []
    for accesorio, dato, nombre, sha256, contenido in archivos:
        if not isinstance(contenido, bytes) or hashlib.sha256(contenido).hexdigest() != sha256:
            raise DatosHazError(f"{error}el archivo «{nombre}» guardado no coincide con su huella")
        try:
            texto = lector.decodificar(contenido)
            identidad = lector.identidad(texto)
        except lector.ArchivoNoReconocido as fallo:
            raise DatosHazError(f"{error}{nombre}: {fallo}") from fallo
        if (identidad.accesorio, identidad.dato) != (accesorio, dato):
            raise DatosHazError(f"{error}el archivo «{nombre}» dice {identidad.accesorio}, {identidad.dato} y se guardó como {accesorio}, {dato}")
        textos.append(texto)
    try:
        return um_armar.datos_haz(textos, *clave, registro["d0_dmax"], registro["d0_tabla"], registro["wf_escritos"], registro["curva_sc"], registro["sc_origen"])
    except ValueError as fallo:
        raise DatosHazError(f"{error}{fallo}") from fallo
