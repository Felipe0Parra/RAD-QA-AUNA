"""UM.3 (PLAN_CALCULADORA_UM_05-11.md, DC12, DA-95): las tablas de cada acelerador quedan guardadas, con historial.

Lo que fija: las dos tablas nuevas (`um_datos_haz`, raíz propia sin FK; `um_archivo_haz`, hija por `ref`), aditivas e idempotentes, dentro del contrato de QC; la única puerta
`services/um_datos_haz.py` (permiso, una transacción, una fila de auditoría comprobada, reemplazo con historial); y la IDA Y VUELTA EXACTA: lo guardado y vuelto a leer da, para una
batería fija de entradas, exactamente las mismas UM (igualdad de float) que los archivos directos, y los bytes guardados son los del archivo, con su huella. Sin Qt. Las bases son
temporales (nunca una de BasesDeDatos/)."""
import ast
import hashlib
import json
import os
import re
import shutil
import sqlite3
import unicodedata

import numpy as np
import pytest

import services.um_datos_haz as servicio          # primero: sin UM.3 la colección cae por `ModuleNotFoundError: No module named 'services.um_datos_haz'`
import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from scripts import observador_contrato as observador
from scripts.indices_bloque_qc import CLAVES_INDICE, crear_indices
from services import lectura_vigente as lv
from services import permisos
from services import um_armar
from services import um_lector_eclipse as lector
from services import um_motor as motor
from services.anulacion import TABLAS_ANULABLES

DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos_um", "600C")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EQUIPO, ENERGIA = "Clinac 600", "6 MV"
ORIGEN = "Eclipse: 1 cGy/UM en dmax"
BOM = b"\xef\xbb\xbf"
COLUMNAS_DATOS = [("id", "INTEGER", 0), ("equipo", "TEXT", 1), ("energia", "TEXT", 1), ("d0_dmax", "REAL", 0), ("d0_tabla", "REAL", 0), ("d0_origen", "TEXT", 1),
                  ("wf_escritos", "TEXT", 1), ("curva_sc", "TEXT", 0), ("sc_origen", "TEXT", 0), ("observaciones", "TEXT", 0), ("usuario", "TEXT", 1),
                  ("fecha_registro", "TEXT", 1), ("activo", "INTEGER", 0)]
COLUMNAS_ARCHIVO = [("id", "INTEGER", 0), ("ref", "INTEGER", 1), ("accesorio", "TEXT", 1), ("dato", "TEXT", 1), ("nombre_archivo", "TEXT", 1), ("sha256", "TEXT", 1),
                    ("contenido", "BLOB", 1), ("activo", "INTEGER", 0)]
# Los 12 que el cálculo lee (DC12): (accesorio, dato), en el orden en que llegan (los nombres ordenados).
GUARDADOS = (("Open Field - 00", "OPD"), ("Open Field - 00", "OutputFactorTable"), ("Open Field - 00", "OPP_processed"),
             ("Standard Wedge - 15", "WDD"), ("Standard Wedge - 15", "OutputFactorTable"), ("Standard Wedge - 30", "WDD"), ("Standard Wedge - 30", "OutputFactorTable"),
             ("Standard Wedge - 45", "WDD"), ("Standard Wedge - 45", "OutputFactorTable"), ("Standard Wedge - 60", "WDD"), ("Standard Wedge - 60", "OutputFactorTable"),
             ("Standard Wedge - 15", "WedgeParameters"))
CURVA = [(4.0, 0.966), (10.0, 1.0), (20.0, 1.015), (35.0, 1.028)]


# ================================================================================================================================== bases y ayudas

@pytest.fixture(scope="module")
def originales():
    """Los 22 archivos reales del 600C como BYTES (con su BOM y sus CRLF), en el orden de sus nombres."""
    salida = []
    for nombre in sorted(os.listdir(DATOS)):
        with open(os.path.join(DATOS, nombre), "rb") as f:
            salida.append((nombre, f.read()))
    return salida


def _abrir_con_la_app(ruta):
    """El arranque REAL de la app sobre `ruta` (crea o migra el esquema) y lo suelta."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = None
        try:
            Conexion().con.close()
        finally:
            Conexion._instance = previo


@pytest.fixture(scope="module")
def plantilla(tmp_path_factory):
    ruta = str(tmp_path_factory.mktemp("um3") / "plantilla.db")
    _abrir_con_la_app(ruta)
    _sql(ruta, "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) VALUES ('jefa', 'x', 'Jefa de Física', 1, 901, 'Físico Médico', 'jefe')")
    _sql(ruta, "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) VALUES ('fisico1', 'x', 'Físico Uno', 1, 902, 'Físico Médico', 'fisico')")
    return ruta


@pytest.fixture
def bd(plantilla, monkeypatch, tmp_path):
    """Una copia de la plantilla y un `Conexion` sin arranque (`conectar()` es el real). Con filas de auditoría ajenas, para que los ids no coincidan por casualidad."""
    ruta = str(tmp_path / "um3.db")
    shutil.copy(plantilla, ruta)
    for i in range(3):
        _sql(ruta, "INSERT INTO audit_log (timestamp, usuario, accion, tabla, ref, detalle) VALUES ('2026-11-01 08:00:00', 'otro', 'guardar', 'controles', ?, 'ajena')", (str(i + 1),))
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    previo = Conexion._instance
    Conexion._instance = object.__new__(Conexion)
    yield ruta
    Conexion._instance = previo


def _sql(ruta, sql, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        filas = con.execute(sql, parametros).fetchall()
        con.commit()
        return filas
    finally:
        con.close()


def _huella(ruta):
    """Todo el contenido de la base, tabla por tabla (esquema y filas)."""
    con = sqlite3.connect(ruta)
    try:
        esquema = con.execute("SELECT type, name, sql FROM sqlite_master ORDER BY type, name").fetchall()
        tablas = [t for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        return esquema, {t: con.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in tablas}
    finally:
        con.close()


def _guardar(archivos, **cambios):
    datos = {"equipo": EQUIPO, "energia": ENERGIA, "archivos": archivos, "d0_dmax": 1.0, "d0_tabla": None, "d0_origen": ORIGEN,
             "wf_escritos": None, "curva_sc": None, "sc_origen": None, "observaciones": None, "usuario": "admin"}
    datos.update(cambios)
    return servicio.guardar(**datos)


def _auditoria(ruta):
    return _sql(ruta, "SELECT usuario, accion, tabla, ref, detalle FROM audit_log WHERE tabla = 'um_datos_haz' ORDER BY id")


def _cambiar(archivos, viejo, nuevo):
    return [(n, b.replace(viejo, nuevo)) for n, b in archivos]


def _bateria():
    """La batería fija de la ida y vuelta: 64 entradas que recorren cada factor (campo abierto a cuatro SSD y profundidades, rectángulos, campo efectivo, fuera del eje, profundidad
    efectiva, las cuatro cuñas con su orientación, centro asimétrico, TF, UM de Eclipse) y las tres barreras (fuera de tabla, fuera del campo, falta un dato)."""
    E = motor.Entrada
    b = [E(dosis=200.0, x=float(l), y=float(l), ssd=float(s), prof=float(p)) for l in (3, 4, 5, 7, 10, 15, 20, 30, 40) for s, p in ((100, 10), (90, 10), (85, 15), (110, 5))]
    b += [E(dosis=200.0, x=x, y=y, ssd=90.0, prof=10.0) for x, y in ((5.0, 25.0), (25.0, 5.0), (10.0, 15.0), (40.0, 3.0))]
    b += [E(dosis=200.0, x=15.0, y=15.0, ssd=90.0, prof=10.0, x_ef=10.0, y_ef=10.0), E(dosis=180.0, x=20.0, y=20.0, ssd=95.0, prof=8.0, x_ef=12.0, y_ef=8.0)]
    b += [E(dosis=200.0, x=20.0, y=20.0, ssd=90.0, prof=10.0, punto_x=5.0), E(dosis=200.0, x=30.0, y=30.0, ssd=100.0, prof=12.0, punto_x=8.0, punto_y=3.0),
          E(dosis=150.0, x=40.0, y=40.0, ssd=100.0, prof=20.0, punto_x=12.0)]
    b += [E(dosis=200.0, x=10.0, y=10.0, ssd=90.0, prof=15.0, prof_ef=8.0), E(dosis=200.0, x=10.0, y=10.0, ssd=100.0, prof=10.0, centro_x=2.0, punto_x=2.0),
          E(dosis=200.0, x=10.0, y=10.0, ssd=100.0, prof=10.0, tf=0.97), E(dosis=200.0, x=10.0, y=10.0, ssd=100.0, prof=10.0, um_planeador=300.0)]
    for angulo in (15, 30, 45, 60):
        b += [E(dosis=200.0, x=10.0, y=10.0, ssd=100.0, prof=10.0, cuna=angulo), E(dosis=200.0, x=15.0, y=15.0, ssd=90.0, prof=15.0, cuna=angulo, cuna_orientacion="OUT"),
              E(dosis=200.0, x=8.0, y=12.0, ssd=95.0, prof=7.0, cuna=angulo)]
    b += [E(dosis=200.0, x=2.5, y=2.5, ssd=90.0, prof=10.0), E(dosis=200.0, x=10.0, y=10.0, ssd=100.0, prof=35.0), E(dosis=200.0, x=10.0, y=10.0, ssd=100.0, prof=10.0, punto_x=6.0)]
    return b


def _resultados(datos):
    """Lo que da `calcular` para cada entrada de la batería: el `Resultado` entero (UM, factores con su origen, avisos...) o la clase y el texto de su `NoCalculable`."""
    salida = []
    for e in _bateria():
        try:
            salida.append(("ok", motor.calcular(datos, e)))
        except motor.NoCalculable as fallo:
            salida.append((type(fallo).__name__, str(fallo)))
    return salida


def _directo(archivos, d0_dmax=1.0, d0_tabla=None, wf_escritos=None, curva_sc=None, sc_origen=None):
    return um_armar.datos_haz([lector.decodificar(b) for _, b in archivos], EQUIPO, ENERGIA, d0_dmax, d0_tabla, wf_escritos, curva_sc, sc_origen)


# ================================================================================================================================== el esquema

def test_las_dos_tablas_nacen_con_sus_columnas_en_su_orden(bd):
    for tabla, esperadas in (("um_datos_haz", COLUMNAS_DATOS), ("um_archivo_haz", COLUMNAS_ARCHIVO)):
        columnas = [(c[1], c[2], c[3]) for c in _sql(bd, f'PRAGMA table_info("{tabla}")')]
        assert columnas == esperadas, tabla
        assert _sql(bd, f'SELECT COUNT(*) FROM "{tabla}"') == [(0,)]


def test_la_hija_apunta_a_su_raiz_con_restrict(bd):
    fk = _sql(bd, 'PRAGMA foreign_key_list("um_archivo_haz")')
    assert [(f[2], f[3], f[4], f[5], f[6]) for f in fk] == [("um_datos_haz", "ref", "id", "CASCADE", "RESTRICT")]
    assert _sql(bd, 'PRAGMA foreign_key_list("um_datos_haz")') == []


def _raiz(ruta, d0_dmax=1.0, d0_tabla=None):
    return _sql(ruta, "INSERT INTO um_datos_haz (equipo, energia, d0_dmax, d0_tabla, d0_origen, wf_escritos, usuario, fecha_registro) VALUES "
                      "('Clinac 600', '6 MV', ?, ?, 'x', '{}', 'u', '2026-11-01 08:00:00') RETURNING id", (d0_dmax, d0_tabla))[0][0]


@pytest.mark.parametrize("d0_dmax, d0_tabla", [(None, None), (1.0, 0.86)])
def test_d0_va_en_dmax_o_en_las_condiciones_de_la_tabla_y_nunca_en_los_dos_ni_en_ninguno(bd, d0_dmax, d0_tabla):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        _raiz(bd, d0_dmax, d0_tabla)


@pytest.mark.parametrize("d0_dmax, d0_tabla", [(1.0, None), (None, 0.86)])
def test_uno_de_los_dos_d0_basta(bd, d0_dmax, d0_tabla):
    assert _raiz(bd, d0_dmax, d0_tabla) >= 1


def test_un_archivo_sin_su_raiz_no_entra_y_una_raiz_con_archivos_no_se_borra(bd):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        _sql(bd, "INSERT INTO um_archivo_haz (ref, accesorio, dato, nombre_archivo, sha256, contenido) VALUES (999, 'a', 'b', 'c', 'd', x'00')")
    ref = _raiz(bd)
    _sql(bd, "INSERT INTO um_archivo_haz (ref, accesorio, dato, nombre_archivo, sha256, contenido) VALUES (?, 'a', 'b', 'c', 'd', x'00')", (ref,))
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        _sql(bd, "DELETE FROM um_datos_haz WHERE id = ?", (ref,))


@pytest.mark.parametrize("columna", ["equipo", "energia", "d0_origen", "wf_escritos", "usuario", "fecha_registro"])
def test_lo_obligatorio_de_la_raiz_no_admite_nulo(bd, columna):
    valores = {"equipo": "Clinac 600", "energia": "6 MV", "d0_dmax": 1.0, "d0_origen": "x", "wf_escritos": "{}", "usuario": "u", "fecha_registro": "2026-11-01 08:00:00", columna: None}
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
        _sql(bd, f"INSERT INTO um_datos_haz ({', '.join(valores)}) VALUES ({', '.join('?' * len(valores))})", tuple(valores.values()))


@pytest.mark.parametrize("columna", ["accesorio", "dato", "nombre_archivo", "sha256", "contenido"])
def test_lo_obligatorio_de_un_archivo_no_admite_nulo(bd, columna):
    ref = _raiz(bd)
    valores = {"ref": ref, "accesorio": "a", "dato": "b", "nombre_archivo": "c", "sha256": "d", "contenido": b"\x00", columna: None}
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
        _sql(bd, f"INSERT INTO um_archivo_haz ({', '.join(valores)}) VALUES ({', '.join('?' * len(valores))})", tuple(valores.values()))


def test_volver_a_abrir_la_base_no_cambia_nada(bd):
    antes = _huella(bd)
    assert {"um_datos_haz", "um_archivo_haz"} <= set(antes[1])          # la base que se vuelve a abrir YA tiene las dos: sin ellas la prueba pasaría también con el código de antes de UM.3 (PR-7)
    _abrir_con_la_app(bd)
    assert _huella(bd) == antes


def test_una_base_vieja_gana_las_dos_tablas_al_abrirse_y_nada_mas_cambia(plantilla, tmp_path):
    """La migración de una base ya desplegada (DA-80, en pequeño; el ensayo sobre copias de las 8 bases de referencia es aparte): sin las dos tablas, abrirla con la app las crea vacías
    y con sus columnas; todas las demás tablas, índices y disparadores quedan idénticos; `integrity_check` ok, `foreign_key_check` igual; el observador de contrato solo informa las dos
    tablas nuevas; y una segunda apertura no cambia nada."""
    ruta = str(tmp_path / "vieja.db")
    shutil.copy(plantilla, ruta)
    _sql(ruta, "DROP TABLE um_archivo_haz")
    _sql(ruta, "DROP TABLE um_datos_haz")
    esquema0, filas0 = _huella(ruta)
    foto0 = observador.capturar(ruta, tolerar_tablas_ausentes=True)
    fk0 = _sql(ruta, "PRAGMA foreign_key_check")
    _abrir_con_la_app(ruta)
    esquema1, filas1 = _huella(ruta)
    assert set(filas1) - set(filas0) == {"um_datos_haz", "um_archivo_haz"}
    assert {t: f for t, f in filas1.items() if t in filas0} == filas0
    assert [e for e in esquema1 if e[1] not in ("um_datos_haz", "um_archivo_haz")] == esquema0
    assert [(c[1], c[2], c[3]) for c in _sql(ruta, 'PRAGMA table_info("um_archivo_haz")')] == COLUMNAS_ARCHIVO
    assert _sql(ruta, "PRAGMA integrity_check") == [("ok",)]
    assert _sql(ruta, "PRAGMA foreign_key_check") == fk0
    fallos, informativo = observador.comparar(foto0, observador.capturar(ruta, tolerar_tablas_ausentes=True))
    assert fallos == []
    assert {t for t in ("um_datos_haz", "um_archivo_haz") if any(t in linea for linea in informativo)} == {"um_datos_haz", "um_archivo_haz"}
    antes = _huella(ruta)
    _abrir_con_la_app(ruta)
    assert _huella(ruta) == antes


def test_la_creacion_va_junto_a_la_de_cd4_en_el_arranque():
    with open(os.path.join(RAIZ, "data", "ManejoDatos", "conection.py"), encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    clase = next(n for n in arbol.body if isinstance(n, ast.ClassDef) and n.name == "Conexion")
    inicio = next(n for n in clase.body if isinstance(n, ast.FunctionDef) and n.name == "__init_connection")
    llamadas = [n.func.attr for n in ast.walk(inicio) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr.startswith("crearTabla")]
    assert llamadas[llamadas.index("crearTablasCalibracionPelicula") + 1] == "crearTablasDatosHazUM"
    assert llamadas.count("crearTablasDatosHazUM") == 1


def test_las_dos_tablas_estan_en_el_contrato_de_qc():
    assert {"um_datos_haz", "um_archivo_haz"} <= TABLAS_ANULABLES
    assert "um_datos_haz" in lv.RAICES_QC and "um_archivo_haz" not in lv.RAICES_QC
    assert lv.tablas_anulables() >= {"um_datos_haz", "um_archivo_haz"}
    assert CLAVES_INDICE["um_datos_haz"] == ("equipo", "energia")
    assert CLAVES_INDICE["um_archivo_haz"] == ("ref", "accesorio", "dato")


def test_los_indices_de_la_herramienta_de_migracion_protegen_cada_clave(bd):
    informe = crear_indices(bd)
    assert (informe["um_datos_haz"], informe["um_archivo_haz"]) == ("creado", "creado")
    assert (crear_indices(bd)["um_datos_haz"], crear_indices(bd)["um_archivo_haz"]) == ("ya existía", "ya existía")
    uno = _raiz(bd)
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        _raiz(bd)
    _sql(bd, "UPDATE um_datos_haz SET activo = 0 WHERE id = ?", (uno,))
    otro = _raiz(bd)
    fila = "INSERT INTO um_archivo_haz (ref, accesorio, dato, nombre_archivo, sha256, contenido) VALUES (?, 'Open Field - 00', ?, 'n', 'h', x'00')"
    _sql(bd, fila, (otro, "OPD"))
    _sql(bd, fila, (otro, "OutputFactorTable"))
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        _sql(bd, fila, (otro, "OPD"))
    _sql(bd, fila, (uno, "OPD"))


# ================================================================================================================================== guardar, reemplazar, historial

def test_guardar_deja_el_conjunto_con_sus_12_archivos_tal_como_se_exportaron(bd, originales):
    ok, motivo, ident = _guardar(originales)
    assert (ok, motivo) == (True, None) and isinstance(ident, int)
    fila = _sql(bd, "SELECT equipo, energia, d0_dmax, d0_tabla, d0_origen, wf_escritos, curva_sc, sc_origen, observaciones, usuario, fecha_registro, activo FROM um_datos_haz")
    assert len(fila) == 1
    assert fila[0][:10] == (EQUIPO, ENERGIA, 1.0, None, "Eclipse: 1 cGy/UM en dmax", "{}", None, None, None, "Administrador")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", fila[0][10]) and fila[0][11] == 1
    archivos = _sql(bd, "SELECT ref, accesorio, dato, nombre_archivo, sha256, contenido, typeof(contenido), activo FROM um_archivo_haz ORDER BY id")
    assert tuple((a[1], a[2]) for a in archivos) == GUARDADOS
    por_nombre = dict(originales)
    for ref, _, _, nombre, sha256, contenido, tipo, activo in archivos:
        assert (ref, tipo, activo) == (ident, "blob", 1)
        assert contenido == por_nombre[nombre] and sha256 == hashlib.sha256(por_nombre[nombre]).hexdigest()
    ignorados = sorted(set(por_nombre) - {a[3] for a in archivos})
    assert len(ignorados) == 10 and all(("Calculated" in n or "Wedge Profiles" in n or "Transmission" in n) for n in ignorados)
    assert _auditoria(bd) == [("Administrador", "guardar", "um_datos_haz", str(ident), "Clinac 600 6 MV: 12 archivos; D'0 = 1 [cGy/UM] en dmax (Eclipse: 1 cGy/UM en dmax)")]
    assert _sql(bd, "SELECT tabla, accion FROM audit_log WHERE detalle != 'ajena'") == [("um_datos_haz", "guardar")]       # UNA fila por acción: ninguna de los archivos


def test_cargar_otra_vez_anula_el_conjunto_y_sus_archivos_y_deja_el_historial(bd, originales):
    _, _, uno = _guardar(originales)
    ok, motivo, dos = _guardar(originales, d0_dmax=0.9989, d0_origen="medida del servicio", observaciones="  segunda carga  ", usuario="jefa")
    assert (ok, motivo) == (True, None) and dos > uno
    assert _sql(bd, "SELECT id, activo FROM um_datos_haz ORDER BY id") == [(uno, 0), (dos, 1)]
    assert _sql(bd, "SELECT ref, COUNT(*), SUM(activo) FROM um_archivo_haz GROUP BY ref ORDER BY ref") == [(uno, 12, 0), (dos, 12, 12)]
    assert _auditoria(bd)[-1] == ("Jefa de Física", "reemplazo", "um_datos_haz", str(dos),
                                  f"Clinac 600 6 MV: 12 archivos; D'0 = 0.9989 [cGy/UM] en dmax (medida del servicio); reemplaza id={uno}")
    historial = servicio.historial(EQUIPO, ENERGIA)
    assert [(h["id"], h["activo"], h["usuario"], h["observaciones"]) for h in historial] == [(dos, 1, "Jefa de Física", "segunda carga"), (uno, 0, "Administrador", None)]
    assert [len(h["archivos"]) for h in historial] == [12, 12]
    assert {a["activo"] for a in historial[1]["archivos"]} == {0} and {a["activo"] for a in historial[0]["archivos"]} == {1}
    assert [{k: v for k, v in a.items() if k != "activo"} for a in historial[0]["archivos"]] == servicio.vigente(EQUIPO, ENERGIA)["archivos"]
    assert servicio.vigente(EQUIPO, ENERGIA)["id"] == dos
    _, _, tres = _guardar(originales)
    assert _sql(bd, "SELECT id, activo FROM um_datos_haz ORDER BY id") == [(uno, 0), (dos, 0), (tres, 1)]
    assert [h["id"] for h in servicio.historial(EQUIPO, ENERGIA)] == [tres, dos, uno]


def _cadenas_de(arbol):
    """Cada cadena de un `.py` (también las partes fijas de un f-string) menos las docstrings: donde vive el SQL."""
    documentacion = {id(n.body[0].value) for n in ast.walk(arbol) if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and n.body
                     and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    return [n for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in documentacion]


ANULAR = r"\bUPDATE\s+\w+\s+SET\s+activo\s*=\s*0(?=\s*(?:WHERE\b|;|$))"      # lo ÚNICO que el servicio le hace a `activo` a mano: anular (la raíz la anula `reemplazar_bloque`; esta sentencia, los archivos de lo reemplazado)


def _lo_que_puede_reactivar_o_borrar(fuente):
    """Lo que, en las cadenas de SQL de `fuente`, podría reactivar, sustituir, editar en sitio o borrar una fila: todo UPDATE que no sea «SET activo = 0» (anular), y cualquier DELETE, REPLACE, DROP o
    `activo =` suelto (el verbo puede venir de una variable). Es una lista de lo PERMITIDO y no de lo prohibido: «SET activo = ?» con (1, id), «= NULL» y «= TRUE» reactivan igual que «= 1» (PR-6 de
    la ronda 1). A qué filas alcanza la anulación no es asunto de este tripwire: lo fijan las pruebas de comportamiento."""
    resto = re.sub(ANULAR, "", "\n".join(c.value for c in _cadenas_de(ast.parse(fuente))), flags=re.I | re.M)
    return re.findall(r"\bUPDATE\b[^\n]*|\bDELETE\b[^\n]*|\bREPLACE\b[^\n]*|\bDROP\b[^\n]*|\bactivo\s*=[^\n]*", resto, re.I)


def _fuente_del_servicio():
    with open(os.path.join(RAIZ, "services", "um_datos_haz.py"), encoding="utf-8") as f:
        return f.read()


def test_lo_anulado_no_se_reactiva_nunca():
    """DA-49 y DA-03: el servicio solo ANULA (`reemplazar_bloque` y una sentencia, la de los archivos del conjunto que reemplaza); no reactiva, no sustituye y no borra una fila de ninguna forma."""
    assert _lo_que_puede_reactivar_o_borrar(_fuente_del_servicio()) == []


@pytest.mark.parametrize("reactivar", ['cursor.execute("UPDATE um_datos_haz SET activo = 1 WHERE id = ?", (ident,))', 'cursor.execute("UPDATE um_datos_haz SET activo = ? WHERE id = ?", (1, ident))',
                                       'cursor.execute("UPDATE um_datos_haz SET activo = NULL WHERE id = ?", (ident,))', 'cursor.execute("UPDATE um_archivo_haz SET activo = TRUE WHERE ref = ?", (ident,))',
                                       'cursor.execute("UPDATE um_archivo_haz SET activo=1 WHERE ref = ?", (ident,))', 'cursor.execute("UPDATE um_datos_haz SET observaciones = NULL, activo = 1 WHERE id = ?", (ident,))',
                                       'cursor.execute(f"UPDATE {tabla} SET activo = {valor} WHERE id = ?", (ident,))', 'cursor.executescript("DELETE FROM um_datos_haz")',
                                       'cursor.execute("UPDATE um_datos_haz SET activo = 0 + 1 WHERE id = ?", (ident,))', 'cursor.execute("UPDATE um_datos_haz SET observaciones = ? WHERE id = ?", (tabla, ident))',
                                       'cursor.execute(f"{valor} um_datos_haz SET activo = {ident}")', 'cursor.executescript("DROP TABLE um_archivo_haz")',
                                       'cursor.execute("INSERT OR REPLACE INTO um_datos_haz (id, activo) VALUES (?, 1)", (ident,))'])
def test_el_tripwire_de_lo_anulado_ve_cada_forma_de_reactivar(reactivar):
    """El tripwire discrimina: el servicio real MÁS una función que reactiva o borra de cualquiera de estas formas (en memoria, nunca en el árbol) aparece; el real solo, no."""
    fuente = _fuente_del_servicio()
    assert _lo_que_puede_reactivar_o_borrar(fuente) == []
    assert _lo_que_puede_reactivar_o_borrar(fuente + f"\n\ndef _intruso(cursor, ident, tabla=None, valor=None):\n    {reactivar}\n") != []


def test_cada_equipo_y_cada_energia_son_un_bloque_aparte(bd, originales):
    ix = _cambiar(originales, b"600C, 6X", b"iX, 6X")
    diez = _cambiar(originales, b", 6X", b", 10X")
    _, _, de_diez = _guardar(diez, energia="10 MV")
    _, _, seis = _guardar(originales)
    _, _, del_ix = _guardar(ix, equipo="Clinac iX")
    assert _sql(bd, "SELECT id, equipo, energia, activo FROM um_datos_haz ORDER BY id") == [(de_diez, EQUIPO, "10 MV", 1), (seis, EQUIPO, "6 MV", 1), (del_ix, "Clinac iX", "6 MV", 1)]
    assert servicio.energias_cargadas(EQUIPO) == ["6 MV", "10 MV"]
    assert servicio.energias_cargadas("Clinac iX") == ["6 MV"]
    _guardar(diez, energia="10 MV")
    assert _sql(bd, "SELECT COUNT(*) FROM um_datos_haz WHERE activo = 1") == [(3,)]
    assert servicio.vigente(EQUIPO, "6 MV")["id"] == seis and servicio.vigente("Clinac iX", "6 MV")["id"] == del_ix
    assert [len(servicio.vigente(e, n)["archivos"]) for e, n in ((EQUIPO, "6 MV"), (EQUIPO, "10 MV"), ("Clinac iX", "6 MV"))] == [12, 12, 12]
    assert servicio.vigente(EQUIPO, "10 MV")["id"] != de_diez
    assert [f[1] for f in _auditoria(bd)] == ["guardar", "guardar", "guardar", "reemplazo"]


def _archivos_por_raiz(ruta):
    """[(id de la raíz, vigente, archivos que tiene, archivos vigentes que tiene)] de todas las raíces, anuladas incluidas."""
    return _sql(ruta, "SELECT r.id, r.activo, COUNT(a.id), COALESCE(SUM(a.activo), 0) FROM um_datos_haz r LEFT JOIN um_archivo_haz a ON a.ref = r.id GROUP BY r.id ORDER BY r.id")


def test_reemplazar_una_clave_no_anula_los_archivos_de_las_otras(bd, originales):
    """PR-1 de la ronda 1: cada clave es un bloque aparte también en sus ARCHIVOS. Al reemplazar una, los archivos vigentes siguen siendo exactamente los de las raíces vigentes (12 por cada una,
    ninguno por las anuladas), sea la reemplazada la de menor id, la del medio o la de mayor: tanto las claves guardadas antes como las guardadas después conservan los suyos."""
    diez = _cambiar(originales, b", 6X", b", 10X")
    ix = _cambiar(originales, b"600C, 6X", b"iX, 6X")
    cargas = [(originales, EQUIPO, "6 MV"), (diez, EQUIPO, "10 MV"), (ix, "Clinac iX", "6 MV")]
    for archivos, equipo, energia in cargas:
        assert _guardar(archivos, equipo=equipo, energia=energia)[0] is True
    for paso, (archivos, equipo, energia) in enumerate(cargas + cargas[::-1], 1):
        assert _guardar(archivos, equipo=equipo, energia=energia)[0] is True
        filas = _archivos_por_raiz(bd)
        assert len(filas) == 3 + paso and sum(vigente for _, vigente, _, _ in filas) == 3, (paso, filas)
        assert all(total == 12 and vigentes == 12 * vigente for _, vigente, total, vigentes in filas), (paso, filas)
    assert [len(servicio.vigente(e, n)["archivos"]) for e, n in ((EQUIPO, "6 MV"), (EQUIPO, "10 MV"), ("Clinac iX", "6 MV"))] == [12, 12, 12]


def test_sin_nada_guardado_las_lecturas_dicen_que_no_hay(bd):
    assert servicio.vigente(EQUIPO, ENERGIA) is None
    assert servicio.datos_del_haz(EQUIPO, ENERGIA) is None
    assert servicio.energias_cargadas(EQUIPO) == []
    assert servicio.historial(EQUIPO, ENERGIA) == []


def test_las_lecturas_del_bloque_no_ven_lo_anulado(bd, originales):
    _, _, uno = _guardar(originales)
    _sql(bd, "UPDATE um_datos_haz SET activo = 0 WHERE id = ?", (uno,))
    assert servicio.vigente(EQUIPO, ENERGIA) is None and servicio.datos_del_haz(EQUIPO, ENERGIA) is None
    assert servicio.energias_cargadas(EQUIPO) == []
    assert [h["id"] for h in servicio.historial(EQUIPO, ENERGIA)] == [uno]


def test_un_archivo_anulado_no_entra_al_haz(bd, originales):
    _, _, uno = _guardar(originales)
    _sql(bd, "UPDATE um_archivo_haz SET activo = 0 WHERE ref = ? AND accesorio = 'Open Field - 00' AND dato = 'OutputFactorTable'", (uno,))
    assert len(servicio.vigente(EQUIPO, ENERGIA)["archivos"]) == 11
    with pytest.raises(servicio.DatosHazError, match="abierto"):
        servicio.datos_del_haz(EQUIPO, ENERGIA)
    assert len(servicio.historial(EQUIPO, ENERGIA)[0]["archivos"]) == 12


def test_vigente_dice_lo_escrito_al_cargar_y_cada_archivo(bd, originales):
    _guardar(originales, wf_escritos={"30": 0.75, 15: 0.77}, curva_sc=CURVA, sc_origen="medida 2025", d0_dmax=None, d0_tabla=0.86, d0_origen="tabla")
    v = servicio.vigente(EQUIPO, ENERGIA)
    assert (v["d0_dmax"], v["d0_tabla"], v["d0_origen"], v["wf_escritos"], v["curva_sc"], v["sc_origen"]) == (None, 0.86, "tabla", {15: 0.77, 30: 0.75}, tuple(CURVA), "medida 2025")
    por_nombre = dict(originales)
    assert [(a["accesorio"], a["dato"]) for a in v["archivos"]] == list(GUARDADOS)
    assert all(a["bytes"] == len(por_nombre[a["nombre_archivo"]]) and a["sha256"] == hashlib.sha256(por_nombre[a["nombre_archivo"]]).hexdigest() for a in v["archivos"])
    assert _auditoria(bd)[-1][4] == "Clinac 600 6 MV: 12 archivos; D'0 = 0.86 [cGy/UM] en las condiciones de la tabla (tabla)"


# ================================================================================================================================== la ida y vuelta exacta

VARIANTES_DEL_HAZ = {
    "lo de omisión": {},
    "D'0 medido y los cuatro factores de cuña escritos": {"d0_dmax": 0.9989, "wf_escritos": {15: 0.771, 30: 0.69, 45: 0.61, 60: 0.52}},
    "las claves de los factores como en un JSON y sin corrección de Sc": {"wf_escritos": {"30": 0.69, "60": 0.52}, "curva_sc": []},
    "una curva de Sc propia": {"curva_sc": CURVA, "sc_origen": "medida en 2025"},
    "D'0 en las condiciones de la tabla": {"d0_dmax": None, "d0_tabla": 0.86, "wf_escritos": {45: 0.61}},
}
# Cuántas de las 64 dan número, COMO MÍNIMO (medido el 08-11 con la referencia de UM.2: 51, 60, 57, 51 y 54; las demás dan su `NoCalculable`, el mismo en los dos caminos). Es un piso y
# no una cifra exacta a propósito: la igualdad entre los dos caminos es el criterio, y una versión más estricta del motor de UM.2 puede dejar sin número alguna entrada más.
CON_NUMERO = {"lo de omisión": 40, "D'0 medido y los cuatro factores de cuña escritos": 50, "las claves de los factores como en un JSON y sin corrección de Sc": 40,
              "una curva de Sc propia": 40, "D'0 en las condiciones de la tabla": 40}


@pytest.mark.parametrize("variante", list(VARIANTES_DEL_HAZ))
def test_lo_guardado_da_exactamente_las_mismas_um_que_los_archivos_directos(bd, originales, variante):
    """El criterio del bloque: con lo guardado y vuelto a leer, cada una de las 64 entradas da el MISMO `Resultado` (igualdad de float en las UM y en cada factor, los mismos avisos)
    o el mismo motivo que con los archivos directos; y dan número por lo menos las contadas."""
    assert len(_bateria()) == 64
    cambios = VARIANTES_DEL_HAZ[variante]
    ok, motivo, _ = _guardar(originales, **cambios)
    assert (ok, motivo) == (True, None)
    guardado = _resultados(servicio.datos_del_haz(EQUIPO, ENERGIA))
    directo = _resultados(_directo(originales, **{k: v for k, v in cambios.items() if k in ("d0_dmax", "d0_tabla", "wf_escritos", "curva_sc", "sc_origen")}))
    assert guardado == directo
    assert sum(r[0] == "ok" for r in guardado) >= CON_NUMERO[variante]
    assert all(type(r[1].um) is float for r in guardado if r[0] == "ok")


def test_los_numeros_de_la_puerta_salen_de_lo_guardado(bd, originales):
    """Los casos de la puerta (§8, paso 4) con las tablas guardadas, a dos decimales como `logs/h_datos_reales.txt`."""
    _guardar(originales)
    datos = servicio.datos_del_haz(EQUIPO, ENERGIA)
    E = motor.Entrada
    casos = [(E(dosis=200.0, x=10.0, y=10.0, ssd=100.0, prof=10.0), 302.1), (E(dosis=200.0, x=10.0, y=10.0, ssd=90.0, prof=10.0), 252.8),
             (E(dosis=200.0, x=10.0, y=15.0, ssd=92.0, prof=8.0), 228.4), (E(dosis=200.0, x=15.0, y=15.0, ssd=90.0, prof=10.0, x_ef=10.0, y_ef=10.0), 250.5),
             (E(dosis=200.0, x=20.0, y=20.0, ssd=90.0, prof=10.0, punto_x=5.0), 224.9), (E(dosis=200.0, x=10.0, y=10.0, ssd=90.0, prof=15.0, prof_ef=8.0), 256.3),
             (E(dosis=200.0, x=10.0, y=10.0, ssd=90.0, prof=10.0, cuna=15), 326.8)]
    assert [round(motor.calcular(datos, e).um, 1) for e, _ in casos] == [um for _, um in casos]


def _variante(archivos, como):
    """Los mismos datos con otros bytes: lo que cambia es la codificación del archivo, no lo que dice."""
    def texto_no_ascii(b, nfd, codificacion):
        t = b.decode("utf-8-sig")
        t = t.replace("exporting date: Thursday, November 5, 2026", "exporting date: miércoles, 5 de noviembre de 2026, año ñandú 15°")
        t = t.replace("# beam data: CLINAC 600C", "# beam data: CLINAC 600C, sala Ñuñoa, cuña física")
        if nfd:
            t = unicodedata.normalize("NFD", t)
        return (BOM if codificacion == "utf-8" else b"") + t.encode(codificacion)
    hacer = {
        "tal cual": lambda b: b,
        "sin BOM": lambda b: b[len(BOM):] if b.startswith(BOM) else b,
        "dos BOM": lambda b: BOM + b,
        "LF": lambda b: b.replace(b"\r\n", b"\n"),
        "CR": lambda b: b.replace(b"\r\n", b"\r"),
        "sin el último salto de línea": lambda b: b[:-2] if b.endswith(b"\r\n") else b,
        "no ASCII en NFC": lambda b: texto_no_ascii(b, False, "utf-8"),
        "no ASCII en NFD": lambda b: texto_no_ascii(b, True, "utf-8"),
        "latin-1 sin BOM": lambda b: texto_no_ascii(b, False, "latin-1"),
    }[como]
    return [(n, hacer(b)) for n, b in archivos]


# Lo medido en el pre-vuelo: todas las variantes se guardan salvo la que corta el último salto de línea (la tabla de factores pide su final de línea: UM.1b).
SE_GUARDA = {"tal cual": True, "sin BOM": True, "dos BOM": True, "LF": True, "CR": True, "sin el último salto de línea": False, "no ASCII en NFC": True, "no ASCII en NFD": True,
             "latin-1 sin BOM": True}


@pytest.mark.parametrize("como", list(SE_GUARDA))
def test_la_clase_de_los_bytes_se_guarda_tal_cual_y_da_las_mismas_um(bd, originales, como):
    """La CLASE, no un caso: el BOM, los finales de línea, el último salto, los caracteres no ASCII en las dos normalizaciones de Unicode y otra codificación. Se guarda EXACTAMENTE lo que
    llegó (sin normalizar nada) con la huella de esos bytes; lo que la revisión rechaza no se guarda, con el mismo motivo; y lo guardado da las mismas UM que esos archivos directos y
    que los originales."""
    archivos = _variante(originales, como)
    revision = servicio.revisar(EQUIPO, ENERGIA, archivos, 1.0, None, d0_origen=ORIGEN)
    ok, motivo, _ = _guardar(archivos)
    assert ok is SE_GUARDA[como] is (not revision.problemas)
    if not ok:
        assert motivo == servicio.NO_SE_GUARDA + "; ".join(revision.problemas) and _sql(bd, "SELECT COUNT(*) FROM um_datos_haz") == [(0,)]
        return
    por_nombre = dict(archivos)
    for nombre, sha256, contenido in _sql(bd, "SELECT nombre_archivo, sha256, contenido FROM um_archivo_haz ORDER BY id"):
        assert contenido == por_nombre[nombre] and sha256 == hashlib.sha256(por_nombre[nombre]).hexdigest()
    guardado = _resultados(servicio.datos_del_haz(EQUIPO, ENERGIA))
    assert guardado == _resultados(_directo(archivos)) == _resultados(_directo(originales))


def test_los_bytes_no_son_el_texto_y_por_eso_se_guardan_los_bytes(bd, originales):
    """Por qué el BLOB (UM3-D1): el texto que da `decodificar` ya no tiene el BOM ni los CRLF, así que su huella no es la del archivo exportado; guardar el texto perdería la comprobación. Y lo que
    SE GUARDA son los bytes del archivo, con la huella de esos bytes: se lee de la base, no se supone (PR-7 de la ronda 1)."""
    for nombre, b in originales:
        assert hashlib.sha256(lector.decodificar(b).encode("utf-8")).hexdigest() != hashlib.sha256(b).hexdigest(), nombre
    assert _guardar(originales)[0] is True
    guardados = _sql(bd, "SELECT nombre_archivo, sha256, contenido FROM um_archivo_haz ORDER BY id")
    por_nombre = dict(originales)
    assert len(guardados) == 12
    for nombre, sha256, contenido in guardados:
        texto = lector.decodificar(por_nombre[nombre]).encode("utf-8")
        assert contenido == por_nombre[nombre] and contenido != texto, nombre
        assert sha256 == hashlib.sha256(por_nombre[nombre]).hexdigest() and sha256 != hashlib.sha256(texto).hexdigest(), nombre


def test_los_nombres_se_guardan_tal_cual_tambien_en_una_base_en_utf16(plantilla, originales, monkeypatch, tmp_path):
    """La codificación de SQLite: en una base creada en UTF-16 los nombres (texto) vuelven idénticos, en NFC o en NFD, y los archivos (BLOB) byte a byte."""
    ruta = str(tmp_path / "utf16.db")
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA encoding = 'UTF-16le'")
    con.execute("CREATE TABLE _arranque (x)")
    con.commit()
    con.close()
    _abrir_con_la_app(ruta)
    assert _sql(ruta, "PRAGMA encoding") == [("UTF-16le",)]
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    monkeypatch.setattr(Conexion, "_instance", object.__new__(Conexion))
    nombres = {n: (unicodedata.normalize("NFD" if i % 2 else "NFC", f"C:\\Física\\cuña {i}° ñ\\{n}")) for i, (n, _) in enumerate(originales)}
    archivos = [(nombres[n], b) for n, b in originales]
    assert _guardar(archivos)[0] is True
    guardados = _sql(ruta, "SELECT nombre_archivo, contenido FROM um_archivo_haz ORDER BY id")
    por_nombre = dict(archivos)
    assert len(guardados) == 12 and all(por_nombre[n] == c for n, c in guardados)
    assert {unicodedata.is_normalized("NFC", n) for n, _ in guardados} == {True, False}
    assert _resultados(servicio.datos_del_haz(EQUIPO, ENERGIA)) == _resultados(_directo(originales))


def test_dos_archivos_iguales_se_guardan_una_vez(bd, originales):
    otro = [("copia/" + originales[2][0], originales[2][1])]
    revision = servicio.revisar(EQUIPO, ENERGIA, originales + otro, 1.0, None, d0_origen=ORIGEN)
    assert revision.problemas == () and otro[0][0] in revision.ignorados and len(revision.usados) == 12
    _, _, ident = _guardar(originales + otro)
    assert _sql(bd, "SELECT COUNT(*) FROM um_archivo_haz WHERE ref = ?", (ident,)) == [(12,)]
    assert _sql(bd, "SELECT nombre_archivo FROM um_archivo_haz WHERE ref = ? AND dato = 'OPD'", (ident,)) == [(originales[2][0],)]


# ================================================================================================================================== lo guardado que no se puede usar

def test_un_archivo_dañado_en_la_base_se_dice_y_no_arma_otro_haz(bd, originales):
    _, _, ident = _guardar(originales)
    _sql(bd, "UPDATE um_archivo_haz SET contenido = ? WHERE ref = ? AND dato = 'OPD'", (originales[2][1].replace(b"+100.0", b"+099.0", 1), ident))
    with pytest.raises(servicio.DatosHazError, match="no coincide con su huella"):
        servicio.datos_del_haz(EQUIPO, ENERGIA)
    _sql(bd, "UPDATE um_archivo_haz SET contenido = ? WHERE ref = ? AND dato = 'OPD'", (originales[2][1], ident))
    assert servicio.datos_del_haz(EQUIPO, ENERGIA) is not None
    for huella in ("0" * 64, "f" * 64):                                # una huella distinta, por debajo y por encima de la verdadera
        _sql(bd, "UPDATE um_archivo_haz SET sha256 = ? WHERE ref = ? AND dato = 'OPD'", (huella, ident))
        with pytest.raises(servicio.DatosHazError, match="no coincide con su huella"):
            servicio.datos_del_haz(EQUIPO, ENERGIA)


def test_un_contenido_que_no_es_bytes_se_dice(bd, originales):
    _, _, ident = _guardar(originales)
    _sql(bd, "UPDATE um_archivo_haz SET contenido = CAST(contenido AS TEXT) WHERE ref = ? AND dato = 'OPD'", (ident,))
    with pytest.raises(servicio.DatosHazError, match="no coincide con su huella"):
        servicio.datos_del_haz(EQUIPO, ENERGIA)


def test_un_archivo_guardado_con_otro_accesorio_se_dice(bd, originales):
    _, _, ident = _guardar(originales)
    _sql(bd, "UPDATE um_archivo_haz SET accesorio = 'Standard Wedge - 30' WHERE ref = ? AND accesorio = 'Standard Wedge - 15' AND dato = 'WDD'", (ident,))
    with pytest.raises(servicio.DatosHazError, match="dice Standard Wedge - 15, WDD y se guardó como Standard Wedge - 30, WDD"):
        servicio.datos_del_haz(EQUIPO, ENERGIA)
    _sql(bd, "UPDATE um_archivo_haz SET accesorio = 'Standard Wedge - 15', dato = 'OPD' WHERE ref = ? AND nombre_archivo = ?", (ident, originales[5][0]))       # el mismo archivo, solo él
    with pytest.raises(servicio.DatosHazError, match="dice Standard Wedge - 15, WDD y se guardó como Standard Wedge - 15, OPD"):
        servicio.datos_del_haz(EQUIPO, ENERGIA)


def test_lo_que_el_lector_de_hoy_no_entiende_se_dice(bd, originales):
    _, _, ident = _guardar(originales)
    roto = originales[2][1].replace(b"$ENOF", b"$FIN!", 1)
    _sql(bd, "UPDATE um_archivo_haz SET contenido = ?, sha256 = ? WHERE ref = ? AND dato = 'OPD'", (roto, hashlib.sha256(roto).hexdigest(), ident))
    with pytest.raises(servicio.DatosHazError, match=re.escape(f"Las tablas guardadas de {EQUIPO}, {ENERGIA} no se pueden usar: ")):
        servicio.datos_del_haz(EQUIPO, ENERGIA)
    nulo = b"\x00" + originales[2][1]
    _sql(bd, "UPDATE um_archivo_haz SET contenido = ?, sha256 = ? WHERE ref = ? AND dato = 'OPD'", (nulo, hashlib.sha256(nulo).hexdigest(), ident))
    with pytest.raises(servicio.DatosHazError, match="bytes nulos"):
        servicio.datos_del_haz(EQUIPO, ENERGIA)


def test_un_d0_guardado_fuera_de_rango_se_dice(bd, originales):
    _guardar(originales)
    _sql(bd, "UPDATE um_datos_haz SET d0_dmax = 86.0")
    with pytest.raises(servicio.DatosHazError, match="86"):
        servicio.datos_del_haz(EQUIPO, ENERGIA)


# ================================================================================================================================== el permiso

@pytest.mark.parametrize("login, nombre", [("admin", "Administrador"), ("jefa", "Jefa de Física"), ("  jefa ", "Jefa de Física")])
def test_el_jefe_y_el_administrador_pueden_cargar(bd, originales, login, nombre):
    ok, motivo, ident = _guardar(originales, usuario=login)
    assert (ok, motivo) == (True, None)
    assert _sql(bd, "SELECT usuario FROM um_datos_haz WHERE id = ?", (ident,)) == [(nombre,)] and _auditoria(bd)[0][0] == nombre


@pytest.mark.parametrize("login, nombre", [("fisico1", "Físico Uno"), ("nadie", "nadie"), ("lamaya", "lamaya")])
def test_sin_permiso_se_deniega_se_audita_y_no_se_escribe_nada(bd, originales, login, nombre):
    """`es_fisico_jefe`: el rol `fisico` NO puede, aunque DA-35 lo haga administrador en el resto de la app; un login que no existe tampoco (sin el respaldo legado de `lamaya`)."""
    antes = _huella(bd)
    assert _guardar(originales, usuario=login) == (False, servicio.DENEGADO, None)
    esquema, filas = _huella(bd)
    nuevas = filas["audit_log"][len(antes[1]["audit_log"]):]
    assert [(f[2], f[3], f[4], f[5], f[6]) for f in nuevas] == [(nombre, "guardar", "um_datos_haz", "Clinac 600/6 MV", servicio.DENEGADO)]
    fuera = ("audit_log", "sqlite_sequence")
    assert esquema == antes[0] and {t: f for t, f in filas.items() if t not in fuera} == {t: f for t, f in antes[1].items() if t not in fuera}


@pytest.mark.parametrize("equipo, energia, ref", [("Clinac 600", "6 MV", "Clinac 600/6 MV"), ("600C", "6X", "Clinac 600/6 MV"), (" clinac-600 ", "06 mv", "Clinac 600/6 MV"),
                                                  ("iX", "10X", "Clinac iX/10 MV"), ("Halcyon", "6 MV", "Halcyon/6 MV"), ("600C", "6", "600C/6"), (None, "6X", "None/6X")])
def test_la_denegacion_se_audita_con_la_clave_canonica_de_la_carga(bd, originales, equipo, energia, ref):
    """R1-PROD-1 de la ronda 1 (UM3-D14, una sola normalización): la fila de la denegación lleva la MISMA clave con que se guarda y se lee todo lo demás. «600C»/«6X» y «Clinac 600»/«6 MV» son la misma
    clave y una sola fila de auditoría la nombra; si el lector no reconoce la pareja (otro equipo, una energía sin unidad, nada) queda lo que se pidió, tal cual."""
    assert _guardar(originales, usuario="fisico1", equipo=equipo, energia=energia) == (False, servicio.DENEGADO, None)
    assert [f[3] for f in _auditoria(bd)] == [ref]


@pytest.mark.parametrize("usuario", [None, "", "   ", 5, b"admin", ["admin"]])
def test_sin_usuario_no_se_hace_nada(bd, originales, usuario):
    antes = _huella(bd)
    assert _guardar(originales, usuario=usuario) == (False, servicio.USUARIO_INVALIDO, None)
    assert _huella(bd) == antes


def test_el_permiso_no_depende_de_da35(bd, originales, monkeypatch):
    """Quitar o ampliar `ROLES_ADMIN_EQUIVALENTE` (DA-35) no cambia quién carga tablas: lo decide `ROLES_GESTION_USUARIOS`. Si alguien la cambia, es una decisión del físico (P9)."""
    assert permisos.ROLES_GESTION_USUARIOS == {"admin", "jefe"}
    monkeypatch.setattr(permisos, "ROLES_ADMIN_EQUIVALENTE", set())
    assert _guardar(originales, usuario="jefa")[0] is True
    monkeypatch.setattr(permisos, "ROLES_ADMIN_EQUIVALENTE", {"admin", "jefe", "fisico"})
    assert _guardar(originales, usuario="fisico1")[1] == servicio.DENEGADO
    monkeypatch.setattr(permisos, "ROLES_GESTION_USUARIOS", {"admin", "jefe", "fisico"})
    assert _guardar(originales, usuario="fisico1")[0] is True


def test_el_permiso_se_comprueba_antes_de_revisar_los_archivos(bd, originales, monkeypatch):
    def no_debe_llamarse(*_a, **_k):
        raise AssertionError("se revisaron los archivos de quien no tiene permiso")
    monkeypatch.setattr(um_armar, "revisar_archivos", no_debe_llamarse)
    assert _guardar(originales, usuario="fisico1")[1] == servicio.DENEGADO


# ================================================================================================================================== qué impide guardar

def _sin(archivos, *fragmentos):
    return [(n, b) for n, b in archivos if not any(f in n for f in fragmentos)]


# Lo que dice cada problema, por su CONTENIDO CLAVE y no por su redacción (los motivos del armado son de UM.2, y su versión final puede redactarlos de otro modo): todas las subcadenas
# deben estar en un mismo problema. Los dos últimos y el UTF-16 son textos de UM.3 y del lector (UM.1b), y van exactos.
CARGAS_QUE_NO_SE_GUARDAN = {
    "de otra máquina": lambda o: (o, {"equipo": "Clinac iX"}, ("600C", "Clinac iX")),
    "de otra energía": lambda o: (o, {"energia": "10 MV"}, ("6X", "10 MV")),
    "sin la tabla abierta": lambda o: (_sin(o, "Open Field - 00_Output Factors"), {}, ("falta", "abierto")),
    "sin el PDD abierto": lambda o: (_sin(o, "Open Field - 00_Measured Depth"), {}, ("falta", "abierto")),
    "un archivo cortado": lambda o: ([(n, b[: len(b) // 2] if "Measured Depth" in n and "Open" in n else b) for n, b in o], {}, ("cortado",)),
    "un archivo en UTF-16": lambda o: (o + [("unicode.txt", "# machine: 600C, 6X".encode("utf-16"))], {}, ("unicode.txt: el archivo trae bytes nulos",)),
    "D'0 imposible": lambda o: (o, {"d0_dmax": 86.0}, ("86",)),
    "un factor de una cuña que no está": lambda o: (o, {"wf_escritos": {20: 0.8}}, ("cuña", "20")),
    "un factor de cuña imposible": lambda o: (o, {"wf_escritos": {15: 7.7}}, ("7.7",)),
    "D'0 a la tabla sin decir cuál": lambda o: (o, {"d0_dmax": None}, ("se escribe D'0 en dmax o en las condiciones de la tabla, uno de los dos",)),
    "los dos D'0": lambda o: (o, {"d0_tabla": 0.86}, ("se escribe D'0 en dmax o en las condiciones de la tabla, uno de los dos",)),
}


@pytest.mark.parametrize("caso", list(CARGAS_QUE_NO_SE_GUARDAN))
def test_un_problema_de_la_revision_impide_guardar_y_se_dice(bd, originales, caso):
    """El servicio repite la revisión de la carga ÉL MISMO: lo que `revisar` llama problema no se guarda, con ese mismo motivo."""
    archivos, cambios, texto = CARGAS_QUE_NO_SE_GUARDAN[caso](originales)
    antes = _huella(bd)
    parametros = {"d0_dmax": 1.0, "d0_tabla": None, **{k: v for k, v in cambios.items() if k in ("d0_dmax", "d0_tabla", "wf_escritos")}}
    revision = servicio.revisar(cambios.get("equipo", EQUIPO), cambios.get("energia", ENERGIA), archivos, d0_origen=ORIGEN, **parametros)
    assert revision.problemas and any(all(t in p for t in texto) for p in revision.problemas)
    ok, motivo, ident = _guardar(archivos, **cambios)
    assert (ok, ident) == (False, None) and motivo == servicio.NO_SE_GUARDA + "; ".join(revision.problemas)
    assert _huella(bd) == antes


def test_el_orden_de_los_archivos_no_importa(bd, originales):
    """El primer archivo de la carga cuenta como los demás (al revés, el primero es el `name.data`), y un archivo que no se decodifica impide guardar aunque llegue primero."""
    al_reves = list(reversed(originales))
    revision = servicio.revisar(EQUIPO, ENERGIA, al_reves, 1.0, None, d0_origen=ORIGEN)
    assert revision.problemas == () and len(revision.usados) == 12
    assert _guardar(al_reves)[0] is True
    assert _resultados(servicio.datos_del_haz(EQUIPO, ENERGIA)) == _resultados(_directo(originales))
    primero = [("unicode.txt", "# machine: 600C, 6X".encode("utf-16"))] + originales
    assert servicio.revisar(EQUIPO, ENERGIA, primero, 1.0, None, d0_origen=ORIGEN).problemas[0].startswith("unicode.txt: el archivo trae bytes nulos")


def test_los_avisos_no_impiden_guardar(bd, originales):
    revision = servicio.revisar(EQUIPO, ENERGIA, originales, 1.0, None, d0_origen=ORIGEN)
    assert revision.problemas == () and len(revision.usados) == 12 and len(revision.ignorados) == 10
    assert any("tendencia" in a for a in revision.avisos) and any("30°" in a for a in revision.avisos)
    assert _guardar(originales)[0] is True


@pytest.mark.parametrize("equipo, energia", [("600C", "6X"), ("clinac 600", "6MV"), ("Clinac 600 ", "6 mv"), ("CLINAC-600", "06 MV"), ("Varian Clinac 600CD", "6 MV")])
def test_el_equipo_y_la_energia_se_guardan_y_se_leen_por_su_clave(bd, originales, equipo, energia):
    """Una sola normalización, la de UM.2 (`_claves_pedidas`), al escribir y al leer (UM3-D14): se guarda la clave canónica y las lecturas la encuentran con cualquier forma que el lector
    reconoce."""
    ok, motivo, ident = _guardar(originales, equipo=equipo, energia=energia)
    assert (ok, motivo) == (True, None)
    assert _sql(bd, "SELECT equipo, energia FROM um_datos_haz WHERE id = ?", (ident,)) == [(EQUIPO, ENERGIA)]
    assert servicio.vigente(equipo, energia)["id"] == ident and servicio.energias_cargadas(equipo) == [ENERGIA]
    assert [h["id"] for h in servicio.historial(equipo, energia)] == [ident] and servicio.datos_del_haz(equipo, energia) is not None


@pytest.mark.parametrize("equipo, energia, texto", [("Clinac 2600", ENERGIA, "Clinac 2600"), (None, ENERGIA, "«None»"), ("Clinac 6000", ENERGIA, "Clinac 6000"),
                                                    ("Halcyon", ENERGIA, "Halcyon"), (EQUIPO, "6", "«6»"), (EQUIPO, "6 MeV", "6 MeV"), (EQUIPO, "6 MV FFF", "6 MV FFF"),
                                                    (EQUIPO, None, "no se reconoce"), (EQUIPO, 6.0, "«6.0»")])
def test_un_equipo_o_una_energia_que_no_se_reconocen_no_se_guardan_ni_se_encuentran(bd, originales, equipo, energia, texto):
    _guardar(originales)
    ok, motivo, _ = _guardar(originales, equipo=equipo, energia=energia)
    assert ok is False and motivo.startswith(servicio.NO_SE_GUARDA) and "no se reconoce" in motivo and texto in motivo
    assert servicio.vigente(equipo, energia) is None and servicio.datos_del_haz(equipo, energia) is None and servicio.historial(equipo, energia) == []
    assert servicio.energias_cargadas(equipo) == ([ENERGIA] if equipo == EQUIPO else [])


DATOS_MAL_ESCRITOS = [
    ({"d0_dmax": True}, "D'0 en dmax debe ser un número"), ({"d0_dmax": "1.0"}, "D'0 en dmax debe ser un número"), ({"d0_dmax": float("nan")}, "D'0 en dmax debe ser un número"),
    ({"d0_dmax": None, "d0_tabla": float("inf")}, "D'0 en las condiciones de la tabla debe ser un número"),
    ({"d0_origen": None}, "falta el origen de D'0"), ({"d0_origen": "  "}, "falta el origen de D'0"), ({"d0_origen": 1}, "el origen de D'0 debe ser un texto"),
    ({"observaciones": 3}, "el campo de observaciones debe ser un texto"), ({"observaciones": "a\x00b"}, "el campo de observaciones trae caracteres que no se pueden guardar"),
    ({"observaciones": "\ud800"}, "el campo de observaciones trae caracteres que no se pueden guardar"),
    ({"wf_escritos": [15, 0.77]}, "los factores de cuña escritos deben ser {ángulo: factor}"),
    ({"wf_escritos": {15.0: 0.77}}, "el ángulo «15.0» de los factores de cuña escritos no es un número entero de grados"),
    ({"wf_escritos": {True: 0.77}}, "el ángulo «True» de los factores de cuña escritos no es un número entero de grados"),
    ({"wf_escritos": {"15°": 0.77}}, "el ángulo «15°» de los factores de cuña escritos no es un número entero de grados"),
    ({"wf_escritos": {" 15": 0.77}}, "el ángulo « 15» de los factores de cuña escritos no es un número entero de grados"),
    ({"wf_escritos": {15: 0.77, "15": 0.78}}, "hay dos factores escritos para la cuña de 15°"),
    ({"wf_escritos": {15: "0.77"}}, "el factor escrito de la cuña de 15° debe ser un número"),
    ({"wf_escritos": {15: float("nan")}}, "el factor escrito de la cuña de 15° debe ser un número"),
    ({"curva_sc": "4:0.97"}, "la curva de Sc debe ser una lista de pares (lado, valor)"),
    ({"curva_sc": 5, "sc_origen": "x"}, "la curva de Sc debe ser una lista de pares (lado, valor)"),
    ({"curva_sc": ["ab", "cd"], "sc_origen": "x"}, "la curva de Sc debe ser una lista de pares (lado, valor)"),
    ({"curva_sc": [(4.0,), (10.0, 1.0)], "sc_origen": "x"}, "la curva de Sc debe ser una lista de pares (lado, valor)"),
    ({"curva_sc": None, "sc_origen": 5}, "el origen de la curva de Sc debe ser un texto"),
    ({"curva_sc": [(4.0, 0.97, 1.0)], "sc_origen": "x"}, "la curva de Sc debe ser una lista de pares (lado, valor)"),
    ({"curva_sc": [(4.0, "0.97"), (10.0, 1.0)], "sc_origen": "x"}, "el valor de la curva de Sc debe ser un número"),
    ({"curva_sc": [(True, 0.97), (10.0, 1.0)], "sc_origen": "x"}, "el lado de la curva de Sc debe ser un número"),
    ({"curva_sc": [(4.0, 0.97)], "sc_origen": "x"}, "La curva de Sc debe tener al menos dos puntos"),
    ({"curva_sc": [(10.0, 1.0), (4.0, 0.97)], "sc_origen": "x"}, "La curva de Sc debe tener al menos dos puntos"),
    ({"curva_sc": CURVA}, "falta el origen de la curva de Sc"),
    ({"curva_sc": None, "sc_origen": "medida"}, "el origen de la curva de Sc solo se escribe con una curva propia"),
    ({"curva_sc": [], "sc_origen": "sin corrección"}, "el origen de la curva de Sc solo se escribe con una curva propia"),
    ({"curva_sc": ""}, "la curva de Sc debe ser una lista de pares (lado, valor)"), ({"curva_sc": 0}, "la curva de Sc debe ser una lista de pares (lado, valor)"),
    ({"d0_dmax": 10 ** 400}, "D'0 en dmax debe ser un número"), ({"wf_escritos": {15: 10 ** 400}}, "el factor escrito de la cuña de 15° debe ser un número"),
    ({"curva_sc": [(10 ** 400, 1.0), (10.0, 1.0)], "sc_origen": "x"}, "el lado de la curva de Sc debe ser un número"),
    ({"curva_sc": [(4.0, 10 ** 400), (10.0, 1.0)], "sc_origen": "x"}, "el valor de la curva de Sc debe ser un número"),
]


@pytest.mark.parametrize("cambios, texto", DATOS_MAL_ESCRITOS)
def test_lo_escrito_al_cargar_se_valida_en_el_servicio(bd, originales, cambios, texto):
    antes = _huella(bd)
    ok, motivo, ident = _guardar(originales, **cambios)
    assert (ok, ident) == (False, None) and motivo.startswith(servicio.NO_SE_GUARDA) and texto in motivo
    assert _huella(bd) == antes


ARCHIVOS_MAL_DADOS = [
    ([], "no hay archivos que cargar"), ("todos", "no hay archivos que cargar"), ([("a.txt", b"x", b"y")], "cada archivo se da como (nombre, contenido)"),
    (["ab"], "cada archivo se da como (nombre, contenido)"), ([("a.txt",)], "cada archivo se da como (nombre, contenido)"),
    ([(None, b"x")], "falta el nombre de un archivo"), ([("a.txt", "# texto")], "a.txt: el contenido debe ser el archivo tal como se leyó (bytes)"),
]


@pytest.mark.parametrize("archivos, texto", ARCHIVOS_MAL_DADOS)
def test_los_archivos_se_dan_como_nombre_y_bytes(bd, archivos, texto):
    assert _guardar(archivos) == (False, servicio.NO_SE_GUARDA + texto, None)


def test_dos_archivos_con_el_mismo_nombre_no_se_distinguirian(bd, originales):
    archivos = originales + [(originales[-1][0], originales[-1][1].replace(b"Standard Wedge - 15", b"Standard Wedge - 30"))]
    assert _guardar(archivos) == (False, servicio.NO_SE_GUARDA + "hay dos archivos con el mismo nombre «name.data»: dé la ruta completa de cada uno", None)


def test_un_bytearray_y_los_escalares_de_numpy_valen(bd, originales):
    archivos = [(n, bytearray(b)) for n, b in originales]
    ok, _, ident = _guardar(archivos, d0_dmax=np.float64(1.0), wf_escritos={np.int64(15): np.float64(0.77)})
    assert ok is True and _sql(bd, "SELECT d0_dmax, wf_escritos FROM um_datos_haz WHERE id = ?", (ident,)) == [(1.0, '{"15": 0.77}')]


# ================================================================================================================================== los JSON

def test_los_json_guardados_son_estrictos_y_con_las_claves_normalizadas(bd, originales):
    _, _, uno = _guardar(originales, wf_escritos={30: 0.69, "15": 0.771}, curva_sc=CURVA, sc_origen="medida")
    _, _, dos = _guardar(originales, curva_sc=())
    filas = _sql(bd, "SELECT wf_escritos, curva_sc, json_valid(wf_escritos), json_valid(curva_sc) FROM um_datos_haz ORDER BY id")
    assert filas == [('{"15": 0.771, "30": 0.69}', "[[4.0, 0.966], [10.0, 1.0], [20.0, 1.015], [35.0, 1.028]]", 1, 1), ("{}", "[]", 1, 1)]
    for wf, curva, _, _ in filas:
        json.loads(wf, parse_constant=lambda c: pytest.fail(c))
        json.loads(curva, parse_constant=lambda c: pytest.fail(c))
    assert servicio.vigente(EQUIPO, ENERGIA)["curva_sc"] == ()
    assert [h["wf_escritos"] for h in servicio.historial(EQUIPO, ENERGIA)] == [{}, {15: 0.771, 30: 0.69}]


# ================================================================================================================================== atomicidad

def _disparador(ruta, sql):
    _sql(ruta, sql)


FALLOS_A_MITAD = {
    "en el quinto archivo": "CREATE TRIGGER _falla BEFORE INSERT ON um_archivo_haz WHEN NEW.accesorio = 'Standard Wedge - 15' AND NEW.dato = 'OutputFactorTable' "
                            "BEGIN SELECT RAISE(ABORT, 'fallo inyectado'); END",
    "en la fila de auditoría": "CREATE TRIGGER _falla BEFORE INSERT ON audit_log WHEN NEW.tabla = 'um_datos_haz' BEGIN SELECT RAISE(ABORT, 'fallo inyectado'); END",
    "al anular los archivos del anterior": "CREATE TRIGGER _falla BEFORE UPDATE OF activo ON um_archivo_haz WHEN NEW.activo = 0 BEGIN SELECT RAISE(ABORT, 'fallo inyectado'); END",
    "en la raíz": "CREATE TRIGGER _falla BEFORE INSERT ON um_datos_haz BEGIN SELECT RAISE(ABORT, 'fallo inyectado'); END",
}


@pytest.mark.parametrize("donde", list(FALLOS_A_MITAD))
def test_un_fallo_a_mitad_no_deja_nada_y_el_anterior_sigue_vigente(bd, originales, donde, capsys):
    _, _, uno = _guardar(originales)
    _disparador(bd, FALLOS_A_MITAD[donde])
    antes = _huella(bd)
    ok, motivo, ident = _guardar(originales, observaciones="segunda")
    esperado = servicio.SIN_AUDITORIA if donde == "en la fila de auditoría" else servicio.RECHAZO_GENERICO
    assert (ok, motivo, ident) == (False, servicio.NO_SE_GUARDA + esperado, None)
    assert "fallo inyectado" in capsys.readouterr().out       # el texto crudo va a la consola, no a la pantalla
    assert _huella(bd) == antes
    assert servicio.vigente(EQUIPO, ENERGIA)["id"] == uno
    _sql(bd, "DROP TRIGGER _falla")
    assert _guardar(originales)[0] is True


def test_sin_la_fila_de_auditoria_no_se_guarda_nada_ni_la_primera_vez(bd, originales):
    _disparador(bd, FALLOS_A_MITAD["en la fila de auditoría"])
    antes = _huella(bd)
    assert _guardar(originales) == (False, servicio.NO_SE_GUARDA + servicio.SIN_AUDITORIA, None)
    assert _huella(bd) == antes


class _Proxy:
    def __init__(self, con, falla, sentencias):
        self._con, self._falla, self._sentencias = con, falla, sentencias

    def __getattr__(self, nombre):
        return getattr(self._con, nombre)

    def execute(self, sql, *parametros):
        self._sentencias.append(sql)
        return self._con.execute(sql, *parametros)

    def cursor(self):
        return _CursorQueAnota(self._con.cursor(), self._sentencias)

    def commit(self):
        if self._falla:
            raise sqlite3.OperationalError(self._falla if isinstance(self._falla, str) else "disk I/O error (inyectado)")
        return self._con.commit()


class _CursorQueAnota:
    def __init__(self, cursor, sentencias):
        self._cursor, self._sentencias = cursor, sentencias

    def __getattr__(self, nombre):
        return getattr(self._cursor, nombre)

    def execute(self, sql, *parametros):
        self._sentencias.append(sql)
        return self._cursor.execute(sql, *parametros)


class _Envoltorio:
    def __init__(self, real, falla, sentencias):
        self._real, self._falla, self._sentencias = real, falla, sentencias

    def __enter__(self):
        return _Proxy(self._real.__enter__(), self._falla, self._sentencias)

    def __exit__(self, *excepcion):
        return self._real.__exit__(*excepcion)

    def __getattr__(self, nombre):
        return getattr(self._real, nombre)


def _envolver(monkeypatch, falla):
    sentencias, original = [], Conexion.conectar
    monkeypatch.setattr(Conexion, "conectar", lambda self: _Envoltorio(original(self), falla, sentencias))
    return sentencias


def test_un_fallo_en_el_commit_no_deja_nada(bd, originales):
    _, _, uno = _guardar(originales)
    antes = _huella(bd)
    with pytest.MonkeyPatch.context() as mp:
        _envolver(mp, True)
        assert _guardar(originales) == (False, servicio.NO_SE_GUARDA + servicio.RECHAZO_GENERICO, None)
    assert _huella(bd) == antes and servicio.vigente(EQUIPO, ENERGIA)["id"] == uno


def test_la_transaccion_toma_el_candado_de_escritura_antes_de_leer_el_vigente(bd, originales, monkeypatch):
    """`BEGIN IMMEDIATE`: con dos equipos guardando a la vez, el segundo espera al primero en vez de leer un vigente que ya cambió (una base, un escritor)."""
    sentencias = _envolver(monkeypatch, False)
    assert _guardar(originales)[0] is True
    vigentes = [k for k, s in enumerate(sentencias) if s.startswith("SELECT id FROM um_datos_haz WHERE equipo")]
    assert vigentes and "BEGIN IMMEDIATE" in sentencias[:vigentes[0]]       # el candado ANTES de leer el vigente que se reemplaza (D1)


# ================================================================================================================================== lo que darán por supuesto UM.4 y UM.5

def test_los_textos_que_vera_el_fisico_no_llevan_simbolos_y_las_unidades_van_entre_corchetes():
    textos = [servicio.DENEGADO, servicio.NO_SE_GUARDA, servicio.USUARIO_INVALIDO]
    assert textos == ["denegado: solo el físico jefe o el administrador pueden cargar las tablas de un acelerador", "No se guardó nada: ",
                      "falta el usuario que carga las tablas, o no es un texto"]
    textos += [servicio.SIN_BASE, servicio.RECHAZO_GENERICO, servicio.SIN_AUDITORIA] + [m for _, m in servicio.RECHAZOS_DE_LA_BASE]
    assert (servicio.SIN_BASE, servicio.SIN_AUDITORIA) == ("no se pudo abrir la base de datos (¿la carpeta de red está disponible?)", "no se pudo escribir la fila de auditoría")
    assert all(not re.search(r"[✓✔✗✘⚠✅❌]", t) for t in textos)
    with open(os.path.join(RAIZ, "services", "um_datos_haz.py"), encoding="utf-8") as f:
        assert not re.search(r"\((?:cGy|UM|cGy/UM|cm|MV|%)\)", f.read())


def test_la_api_de_la_puerta_es_la_del_plan():
    import inspect
    assert list(inspect.signature(servicio.guardar).parameters) == ["equipo", "energia", "archivos", "d0_dmax", "d0_tabla", "d0_origen", "wf_escritos", "curva_sc", "sc_origen",
                                                                   "observaciones", "usuario"]
    assert list(inspect.signature(servicio.revisar).parameters) == ["equipo", "energia", "archivos", "d0_dmax", "d0_tabla", "wf_escritos", "curva_sc", "sc_origen", "d0_origen",
                                                                   "observaciones"]
    for nombre in ("vigente", "energias_cargadas", "historial", "datos_del_haz"):
        assert callable(getattr(servicio, nombre))
    assert issubclass(servicio.DatosHazError, ValueError)


# ================================================================================================================================== lo que cerró la auditoría previa (09-11)

def test_si_la_base_no_se_abre_se_dice_en_vez_de_reventar(bd, originales, monkeypatch):
    """A4: `Conexion().conectar()` devuelve None con la carpeta de red caída: `guardar` lo dice y las lecturas lanzan `DatosHazError` con el mismo motivo (antes, `TypeError`)."""
    monkeypatch.setattr(Conexion, "conectar", lambda self: None)
    assert _guardar(originales) == (False, servicio.NO_SE_GUARDA + servicio.SIN_BASE, None)
    for leer in (lambda: servicio.vigente(EQUIPO, ENERGIA), lambda: servicio.datos_del_haz(EQUIPO, ENERGIA), lambda: servicio.historial(EQUIPO, ENERGIA),
                 lambda: servicio.energias_cargadas(EQUIPO)):
        with pytest.raises(servicio.DatosHazError, match=re.escape(servicio.SIN_BASE)):
            leer()


class _ReemplazoEntreLasDosLecturas:
    """Envuelve `Conexion.conectar`: justo después de que una lectura del servicio lee la raíz de un conjunto, otro equipo guarda un conjunto nuevo de la misma clave (una vez)."""

    def __init__(self, monkeypatch, originales):
        self.hecho, self.raiz_leida, self.original, self.originales = False, False, Conexion.conectar, originales
        monkeypatch.setattr(Conexion, "conectar", lambda conexion: self._conectar(conexion))

    def _conectar(self, conexion):
        real = self.original(conexion)
        return real if self.hecho or real is None else _Envoltorio(real, False, _Disparador(self))


class _Disparador(list):
    def __init__(self, dueno):
        super().__init__()
        self.dueno = dueno

    def append(self, sql):
        """Se anota ANTES de ejecutarse: el reemplazo entra cuando la sentencia que sigue a la lectura de la raíz está por correr."""
        if self.dueno.raiz_leida and not self.dueno.hecho:
            self.dueno.hecho = True
            assert _guardar(self.dueno.originales, observaciones="el otro equipo")[0] is True
        super().append(sql)
        if "FROM um_datos_haz WHERE equipo" in sql:
            self.dueno.raiz_leida = True


def test_las_lecturas_ven_una_sola_foto_de_la_base_aunque_otro_guarde_a_la_vez(bd, originales):
    """A2 (UM3-D15): la raíz y sus archivos se leen en UNA transacción; un reemplazo que entra entre las dos sentencias no deja un conjunto sin archivos ni un `DatosHazError` falso."""
    _, _, uno = _guardar(originales)
    with pytest.MonkeyPatch.context() as mp:
        _ReemplazoEntreLasDosLecturas(mp, originales)
        v = servicio.vigente(EQUIPO, ENERGIA)
    assert v["id"] == uno and len(v["archivos"]) == 12
    with pytest.MonkeyPatch.context() as mp:
        _ReemplazoEntreLasDosLecturas(mp, originales)
        assert _resultados(servicio.datos_del_haz(EQUIPO, ENERGIA)) == _resultados(_directo(originales))
    with pytest.MonkeyPatch.context() as mp:
        _ReemplazoEntreLasDosLecturas(mp, originales)
        historial = servicio.historial(EQUIPO, ENERGIA)
    assert [len(h["archivos"]) for h in historial] == [12, 12, 12]
    assert all(a["activo"] == h["activo"] for h in historial for a in h["archivos"]), [(h["id"], h["activo"], sorted({a["activo"] for a in h["archivos"]})) for h in historial]      # PR-4: la raíz y sus archivos, de la MISMA foto
    assert len(servicio.historial(EQUIPO, ENERGIA)) == 4


def test_dos_vigentes_de_la_misma_clave_se_dicen_y_no_se_elige_uno(bd, originales):
    """A3, defensa en profundidad: sin el índice único (solo lo crea la herramienta de migración) dos conjuntos vigentes de la misma clave darían números distintos según cuál se eligiera; las
    lecturas lo dicen. Un guardado nuevo los reemplaza a los dos, en orden."""
    _, _, uno = _guardar(originales)
    otro = _sql(bd, f"INSERT INTO um_datos_haz ({', '.join(servicio._COLUMNAS)}) SELECT {', '.join(servicio._COLUMNAS)} FROM um_datos_haz WHERE id = ? RETURNING id", (uno,))[0][0]
    _sql(bd, "INSERT INTO um_archivo_haz (ref, accesorio, dato, nombre_archivo, sha256, contenido) SELECT ?, accesorio, dato, nombre_archivo, sha256, contenido FROM um_archivo_haz WHERE ref = ?", (otro, uno))
    for leer in (lambda: servicio.vigente(EQUIPO, ENERGIA), lambda: servicio.datos_del_haz(EQUIPO, ENERGIA)):
        with pytest.raises(servicio.DatosHazError, match=f"hay 2 conjuntos vigentes de Clinac 600, 6 MV \\(ids {otro}, {uno}\\)"):
            leer()
    assert servicio.energias_cargadas(EQUIPO) == [ENERGIA]                      # PR-8: la energía, una vez (no una por cada vigente)
    assert [h["id"] for h in servicio.historial(EQUIPO, ENERGIA)] == [otro, uno]
    _, _, tres = _guardar(originales)
    assert _auditoria(bd)[-1][4].endswith(f"; reemplaza id={uno}, {otro}") and servicio.vigente(EQUIPO, ENERGIA)["id"] == tres
    assert _sql(bd, "SELECT ref, COUNT(*), SUM(activo) FROM um_archivo_haz GROUP BY ref ORDER BY ref") == [(uno, 12, 0), (otro, 12, 0), (tres, 12, 12)]       # PR-5: los archivos de LOS DOS reemplazados


_PERMITIDOS = {"services/um_datos_haz.py": "la puerta", "data/ManejoDatos/conection.py": "el CREATE TABLE", "services/anulacion.py": "TABLAS_ANULABLES",
               "services/lectura_vigente.py": "RAICES_QC", "scripts/indices_bloque_qc.py": "CLAVES_INDICE"}


PUERTA = "services/um_datos_haz.py"
# Lo que la puerta exporta y da acceso a las tablas SIN escribir su nombre (PR-2 de la ronda 1): un escritor fuera de ella con `reemplazar_bloque(c, TABLA_DATOS_HAZ, ..., SQL_INSERT, ...)` o con
# `cursor.execute(SQL_INSERT, fila)` no tiene ninguna cadena con `um_datos_haz`, y ningún otro tripwire lo ve (miran las cadenas de SQL o los f-strings con la constante en un SELECT o un UPDATE).
NOMBRES_DE_LA_PUERTA = ("TABLA_DATOS_HAZ", "SQL_INSERT", "SQL_INSERT_ARCHIVO")


def _quien_nombra_las_tablas(raiz):
    """{archivo: [(línea, texto)]} de cada cadena (también las partes fijas de un f-string; no las docstrings) de un `.py` fuera de `tests/` que nombra `um_datos_haz` o `um_archivo_haz`, y de cada uso,
    FUERA de la puerta, de lo que ella exporta y da acceso a las tablas sin escribir su nombre (`NOMBRES_DE_LA_PUERTA`): importado, por atributo del módulo o como cadena de un `getattr`."""
    hallados = {}
    for carpeta, subcarpetas, archivos in os.walk(raiz):
        subcarpetas[:] = [s for s in subcarpetas if s not in ("tests", ".venv", ".git", "build", "dist", "__pycache__")]
        for nombre in archivos:
            if not nombre.endswith(".py"):
                continue
            ruta = os.path.join(carpeta, nombre)
            relativa = os.path.relpath(ruta, raiz).replace(os.sep, "/")
            with open(ruta, encoding="utf-8", errors="replace") as f:
                arbol = ast.parse(f.read())
            for nodo in _cadenas_de(arbol):
                if re.search(r"\bum_(datos|archivo)_haz\b", nodo.value) or (relativa != PUERTA and nodo.value in NOMBRES_DE_LA_PUERTA):
                    hallados.setdefault(relativa, []).append((nodo.lineno, nodo.value))
            for nodo in (ast.walk(arbol) if relativa != PUERTA else ()):
                uso = nodo.id if isinstance(nodo, ast.Name) else nodo.attr if isinstance(nodo, ast.Attribute) else nodo.name if isinstance(nodo, ast.alias) else None
                if uso in NOMBRES_DE_LA_PUERTA:
                    hallados.setdefault(relativa, []).append((nodo.lineno, uso))
    return hallados


def test_solo_la_puerta_lee_y_escribe_las_dos_tablas():
    """A3 (CONTRATO-1), el censo de CD.4 para estas tablas: fuera de las pruebas, solo la puerta tiene SQL sobre ellas; los demás solo las nombran donde las registran, y nadie fuera de ella usa lo que
    ella exporta con el nombre de una tabla (PR-2 de la ronda 1)."""
    exportadas = {n for n in dir(servicio) if n.isupper() and not n.startswith("_") and isinstance(getattr(servicio, n), str) and re.search(r"\bum_(datos|archivo)_haz\b", getattr(servicio, n))}
    assert exportadas == set(NOMBRES_DE_LA_PUERTA), exportadas ^ set(NOMBRES_DE_LA_PUERTA)          # la lista que el censo vigila es EXACTAMENTE lo que la puerta exporta con el nombre de una tabla
    hallados = _quien_nombra_las_tablas(RAIZ)
    assert set(hallados) <= set(_PERMITIDOS), sorted(set(hallados) - set(_PERMITIDOS))
    for archivo in ("services/anulacion.py", "services/lectura_vigente.py", "scripts/indices_bloque_qc.py"):
        assert all(texto in ("um_datos_haz", "um_archivo_haz") for _, texto in hallados.get(archivo, ())), archivo
    assert all("CREATE TABLE IF NOT EXISTS um_" in texto for _, texto in hallados["data/ManejoDatos/conection.py"])
    assert any("INSERT INTO um_archivo_haz" in texto for _, texto in hallados["services/um_datos_haz.py"])


@pytest.mark.parametrize("intruso", ['cursor.execute("INSERT INTO um_archivo_haz (ref) VALUES (1)")', 'reemplazar_bloque(c, "um_datos_haz", [], "", [], "x")',
                                     'con.execute(f"UPDATE um_datos_haz SET activo = 0 WHERE id = {i}")', 'cursor.execute("SELECT contenido FROM um_archivo_haz")',
                                     'reemplazar_bloque(c, TABLA_DATOS_HAZ, [], SQL_INSERT, [], "x")',                                      # sin escribir el nombre de ninguna tabla
                                     'from services.um_datos_haz import SQL_INSERT_ARCHIVO as consulta; cursor.execute(consulta, ())',         # importado de la puerta, con otro nombre
                                     'from services import um_datos_haz; cursor.execute(um_datos_haz.SQL_INSERT, ())',                         # por el módulo
                                     'cursor.execute(getattr(modulo, "SQL_INSERT_ARCHIVO"), ())'])                                            # por su nombre como cadena
def test_el_censo_ve_a_un_intruso(tmp_path, intruso):
    """El censo discrimina: un escritor o un lector nuevo fuera de la puerta (en una copia, nunca en el árbol: sin la carrera de los intrusos, H-UM1-12) aparece, también el que usa lo que la puerta
    exporta sin escribir el nombre de una tabla."""
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "_intruso_um3.py").write_text(f"def f(cursor, c, con, i, reemplazar_bloque):\n    {intruso}\n", encoding="utf-8")
    assert list(_quien_nombra_las_tablas(str(tmp_path))) == ["services/_intruso_um3.py"]


def test_lo_guardado_dañado_en_sus_json_se_dice_y_no_esconde_el_resto_del_historial(bd, originales):
    """A6: una columna JSON dañada (edición a mano, una migración) da `DatosHazError` en español en las lecturas del vigente, y el historial la marca sin esconder las demás."""
    _, _, uno = _guardar(originales)
    _, _, dos = _guardar(originales, wf_escritos={30: 0.69})
    for columna, valor in (("wf_escritos", '{"15": '), ("wf_escritos", '{"x": 1}'), ("curva_sc", '[[4.0]]'), ("wf_escritos", '[1, 2]')):
        _sql(bd, f"UPDATE um_datos_haz SET {columna} = ? WHERE id = ?", (valor, dos))
        for leer in (lambda: servicio.vigente(EQUIPO, ENERGIA), lambda: servicio.datos_del_haz(EQUIPO, ENERGIA)):
            with pytest.raises(servicio.DatosHazError, match=f"lo guardado del conjunto id={dos} no se puede usar"):
                leer()
        historial = servicio.historial(EQUIPO, ENERGIA)
        assert [(h["id"], h["problema"] is None) for h in historial] == [(dos, False), (uno, True)] and len(historial[0]["archivos"]) == 12
        assert (historial[0]["wf_escritos"], historial[0]["curva_sc"]) == (None, None) and historial[1]["wf_escritos"] == {}
        _sql(bd, "UPDATE um_datos_haz SET wf_escritos = '{\"30\": 0.69}', curva_sc = NULL WHERE id = ?", (dos,))


def test_la_revision_dice_la_curva_de_sc_y_el_factor_deducido(bd, originales):
    """B1 (DC13, punto 2): el resumen dice la curva de Sc que usará el cálculo (sus pares) y el factor de cuña deducido (el aviso de UM.2)."""
    revision = servicio.revisar(EQUIPO, ENERGIA, originales, 1.0, None, d0_origen=ORIGEN)
    assert revision.avisos[-1].startswith("Curva de Sc que usa el cálculo (lado [cm]: Sc): 4: 0.9") and revision.avisos[-1].count(":") > 10
    assert any("15°" in a and "dedujo" in a for a in revision.avisos)
    propia = servicio.revisar(EQUIPO, ENERGIA, originales, 1.0, None, curva_sc=CURVA, sc_origen="medida", d0_origen=ORIGEN)
    assert propia.avisos[-1] == "Curva de Sc que usa el cálculo (lado [cm]: Sc): 4: 0.966, 10: 1.000, 20: 1.015, 35: 1.028."
    abierta = [a for a in originales if "Open Field - 00_Output Factors" in a[0]]
    pdd = [a for a in originales if "Open Field - 00_Measured Depth" in a[0]]
    en_los_extremos = abierta + [a for a in originales if a not in abierta + pdd] + pdd       # la tabla abierta, la primera; el PDD abierto, el último
    assert servicio.revisar(EQUIPO, ENERGIA, en_los_extremos, 1.0, None, d0_origen=ORIGEN).avisos[-1] == revision.avisos[-1]
    apagada = servicio.revisar(EQUIPO, ENERGIA, originales, 1.0, None, curva_sc=[], d0_origen=ORIGEN)
    assert apagada.avisos[-1] == "Curva de Sc que usa el cálculo: ninguna, la corrección de Sc está apagada."


ENTRADAS_DE_LA_COMPARACION = [{}, {"d0_origen": None}, {"d0_origen": 5}, {"observaciones": 3}, {"observaciones": "nota"}, {"wf_escritos": {15.0: 0.7}}, {"wf_escritos": {30: 0.69}},
                              {"curva_sc": CURVA}, {"curva_sc": CURVA, "sc_origen": "medida"}, {"curva_sc": []}, {"d0_dmax": None}, {"d0_dmax": 86.0}, {"energia": "10 MV"},
                              {"equipo": "Clinac iX"}, {"equipo": "600C", "energia": "6X"}]


@pytest.mark.parametrize("cambios", ENTRADAS_DE_LA_COMPARACION, ids=[str(c) for c in ENTRADAS_DE_LA_COMPARACION])
def test_revisar_y_guardar_dicen_lo_mismo(bd, originales, cambios):
    """B2 (UM3-D2 literal): con los mismos datos, `guardar` guarda si y solo si `revisar` no da problemas, y su motivo son esos mismos problemas."""
    datos = {"d0_dmax": 1.0, "d0_tabla": None, "d0_origen": ORIGEN, **cambios}
    revision = servicio.revisar(datos.pop("equipo", EQUIPO), datos.pop("energia", ENERGIA), originales, **datos)
    ok, motivo, _ = _guardar(originales, **cambios)
    assert ok is (not revision.problemas)
    assert ok or motivo == servicio.NO_SE_GUARDA + "; ".join(revision.problemas)


def test_un_rechazo_de_lo_escrito_conserva_lo_que_se_usa_y_lo_que_se_ignora(bd, originales):
    """B3 (UM3-D16): si lo escrito no se entiende, el resumen dice igual qué archivos se usan y cuáles se ignoran; no dice avisos de una carga que no es la escrita."""
    revision = servicio.revisar(EQUIPO, ENERGIA, originales, 1.0, None, wf_escritos={15.5: 0.7}, d0_origen=ORIGEN)
    assert revision.problemas == ("el ángulo «15.5» de los factores de cuña escritos no es un número entero de grados",)
    assert (len(revision.usados), len(revision.ignorados), revision.avisos) == (12, 10, ())


@pytest.mark.parametrize("crudo, motivo", [("database is locked", "la base de datos está ocupada por otro guardado: espere un momento y vuelva a intentarlo"),
                                           ("attempt to write a readonly database", "la base de datos es de solo lectura en este equipo"),
                                           ("database or disk is full", "no queda espacio en el disco de la base de datos"), ("disk I/O error", "la base de datos no aceptó el guardado")])
def test_un_rechazo_de_la_base_se_dice_en_español(bd, originales, capsys, crudo, motivo):
    """C1 (UM3-D17): el motivo, en español y por causa conocida; el texto crudo de SQLite va a la consola. (Con la base tomada, la espera es el `busy_timeout` de toda la app.)"""
    antes = _huella(bd)
    with pytest.MonkeyPatch.context() as mp:
        _envolver(mp, crudo)
        assert _guardar(originales) == (False, servicio.NO_SE_GUARDA + motivo, None)
    assert crudo in capsys.readouterr().out
    assert _huella(bd) == antes


def test_la_denegacion_se_audita_por_la_conexion_de_la_app(bd, originales, monkeypatch):
    """C2 (UM3-D18): la fila de la denegación va por una conexión que dio `Conexion().conectar()` (su WAL y la espera de toda la app), no por una propia con la espera corta de `sqlite3`: es la MISMA
    conexión que `conectar()` entregó (PR-3 de la ronda 1: antes solo se miraba que hubiera alguna) y tiene la espera de la app, que no es la de una conexión cruda."""
    with Conexion().conectar() as de_la_app:
        espera_de_la_app = de_la_app.execute("PRAGMA busy_timeout").fetchone()[0]
    cruda = sqlite3.connect(bd)
    espera_cruda = cruda.execute("PRAGMA busy_timeout").fetchone()[0]
    cruda.close()
    assert espera_de_la_app != espera_cruda                              # sin esto la espera no distinguiría nada
    entregadas, original = [], Conexion.conectar

    def conectar(conexion):
        entregada = original(conexion)
        entregadas.append(entregada)
        return entregada
    monkeypatch.setattr(Conexion, "conectar", conectar)
    usadas, registrar = [], servicio._registrar_auditoria

    def registrar_y_anotar(*argumentos, **opciones):
        con = opciones.get("con")
        usadas.append((con, None if con is None else con.execute("PRAGMA busy_timeout").fetchone()[0]))
        return registrar(*argumentos, **opciones)
    monkeypatch.setattr(servicio, "_registrar_auditoria", registrar_y_anotar)
    assert _guardar(originales, usuario="fisico1")[1] == servicio.DENEGADO
    assert len(usadas) == 1 and len(_auditoria(bd)) == 1
    con, espera = usadas[0]
    assert any(con is entregada.__enter__() for entregada in entregadas) and espera == espera_de_la_app


@pytest.mark.parametrize("escritos", [{}, {15: 0.77}, {"15": 0.77}, {"15": 0.77, 30: 0.7}, {15.0: 0.7}, {15.5: 0.7}, {True: 0.7}, {"15°": 0.7}, {" 15": 0.7}, {15: "0.7"},
                                      {15: float("nan")}, {15: True}, {15: 0.7, "15": 0.8}])
def test_la_regla_de_los_factores_de_cuna_es_la_de_um2(escritos):
    """C4: UM.3 valida los factores escritos con su propia función, que acepta y rechaza lo mismo que la de UM.2 salvo dos diferencias a propósito: un WF de 10**400 (la de UM.2 deja escapar
    un `OverflowError`; UM.3 lo rechaza) y un ángulo que es un entero de numpy (UM.3 lo acepta y pasa a UM.2 el entero de Python: la carga desde una tabla de la pantalla)."""
    if escritos == {}:
        with pytest.raises(OverflowError):
            um_armar._factores_escritos({15: 10 ** 400})
        assert servicio._factores_de_cuna({np.int64(15): np.float64(0.77)}) == {15: 0.77}
    try:
        mia = servicio._factores_de_cuna(escritos)
    except ValueError:
        mia = "rechazo"
    try:
        de_um2 = um_armar._factores_escritos(escritos)
    except ValueError:
        de_um2 = "rechazo"
    assert mia == de_um2


def test_d0_en_dmax_y_en_la_tabla_no_son_lo_mismo(bd, originales):
    """D2: con la tabla a otra SSD que los PDD, D'0 en dmax se rechaza (no se puede llevar con el PDD) y en las condiciones de la tabla se guarda y se usa tal cual."""
    a_95 = _cambiar(originales, b"%SourcePhantomDistance 1000", b"%SourcePhantomDistance 950")
    en_dmax = servicio.revisar(EQUIPO, ENERGIA, a_95, 1.0, None, d0_origen=ORIGEN)
    assert any("SSD 95" in p and "condiciones de la tabla" in p for p in en_dmax.problemas)
    assert _guardar(a_95)[0] is False
    ok, _, ident = _guardar(a_95, d0_dmax=None, d0_tabla=0.86)
    assert ok is True and _sql(bd, "SELECT d0_dmax, d0_tabla FROM um_datos_haz WHERE id = ?", (ident,)) == [(None, 0.86)]
    assert servicio.datos_del_haz(EQUIPO, ENERGIA).d0_norm == 0.86


@pytest.mark.parametrize("orden", ["6 MV primero", "10 MV primero"])
def test_los_archivos_que_se_leen_son_solo_los_del_conjunto_pedido(bd, originales, orden):
    """D3: con dos energías vigentes (ids más altos y más bajos que el pedido), `datos_del_haz` lee SOLO los archivos de su `ref`."""
    diez = _cambiar(originales, b", 6X", b", 10X")
    cargas = [(originales, ENERGIA), (diez, "10 MV")] if orden == "6 MV primero" else [(diez, "10 MV"), (originales, ENERGIA)]
    for archivos, energia in cargas + cargas[:1]:
        assert _guardar(archivos, energia=energia)[0] is True
    assert _resultados(servicio.datos_del_haz(EQUIPO, ENERGIA)) == _resultados(_directo(originales))
    assert servicio.datos_del_haz(EQUIPO, "10 MV").energia == "10 MV"


def test_la_fecha_de_registro_es_la_del_momento_del_guardado(bd, originales, monkeypatch):
    """D5: la fecha que se guarda es la del reloj al guardar, en el formato de la app (con un reloj fijo, no con una expresión regular)."""
    import datetime as reloj

    class _Reloj(reloj.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 2, 3, 4, 5)
    monkeypatch.setattr(servicio, "datetime", _Reloj)
    _, _, ident = _guardar(originales)
    assert _sql(bd, "SELECT fecha_registro FROM um_datos_haz WHERE id = ?", (ident,)) == [("2026-11-02 03:04:05",)]


def test_si_la_base_se_cae_entre_la_prueba_y_el_guardado_se_dice(bd, originales, monkeypatch):
    """A4, el resto de la clase: la base se abre para la prueba y para leer el usuario, y ya no al guardar (la red se cae a mitad): el mismo motivo, nada escrito."""
    antes, llamadas, original = _huella(bd), [], Conexion.conectar
    monkeypatch.setattr(Conexion, "conectar", lambda conexion: (llamadas.append(1), original(conexion) if len(llamadas) <= 2 else None)[1])
    assert _guardar(originales) == (False, servicio.NO_SE_GUARDA + servicio.SIN_BASE, None)
    assert len(llamadas) == 3 and _huella(bd) == antes
