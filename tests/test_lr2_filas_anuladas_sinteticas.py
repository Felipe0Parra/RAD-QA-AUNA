"""LR2 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LR2, [[DA-48]]): verificar la
regla de [[DA-47]] sobre las 7 raíces **fabricando** el escenario que hoy
no existe.

Por qué esta forma y no otra: la versión original de LR2 pedía medir el
impacto sobre las 3 BD de referencia. Medido el 2026-08-20, las 7 raíces
tienen **cero** filas anuladas sobre 1.200+ filas, así que esa cuenta daba
cero en todas las filas y no probaba nada -- un entregable vacío disfrazado
de garantía. Una fase PREVENTIVA solo se puede verificar construyendo la
condición que previene: aquí se anula una fila sintética de cada raíz, sobre
una BD temporal (nunca sobre las de referencia), y se comprueba, con el SQL
REAL copiado de cada sitio del censo de LR1, que:

  - **lista/bloque** -> la fila anulada NO aparece;
  - **identidad** -> la fila anulada SÍ se entrega al pedirla por su `id`;
  - **censo** -> se siguen viendo las dos ramas (es lo que sostiene DA-34).

Los tres bloques son necesarios juntos. Solo el primero certificaría un
"filtra todo" que rompería el formulario de un registro anulado abierto a
propósito (el defecto de LF4); solo el segundo certificaría un "no filtra
nada", que es el estado del que parte DA-48.

**La predicción de LR3**: para los 31 sitios de lista que todavía no
filtran (`PENDIENTES_LR3` en `test_lr1_censo_raices_qc.py`), este archivo
mide las DOS formas del mismo SQL sobre las mismas filas -- la de hoy y la
que dejará LR3 -- y fija por escrito qué cambia. LR3 no tiene que
"parecer" correcto: tiene que reproducir exactamente estas cuentas.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod  # noqa: E402
from data.ManejoDatos.conection import Conexion  # noqa: E402
from services.anulacion import filtro_activo  # noqa: E402

# ---------------------------------------------------------------------------
# Las filas sintéticas. Cada raíz recibe DOS filas que comparten su clave de
# bloque (la fecha, o (equipo, control, fecha) en `controles`) y se
# diferencian solo en `id` y `activo` -- exactamente la forma que deja un
# anular+insertar. `ID_ANULADA` es siempre la MENOR, a propósito: sin
# `ORDER BY`, un `LIMIT 1` tiende a devolver la primera insertada, que es
# justo la que no debe verse.
# ---------------------------------------------------------------------------
ID_ANULADA = 901
ID_VIGENTE = 902

FECHA_CONTROL = "15/03/2026"          # formato de `controles` (DD/MM/YYYY)
FECHA_BRAQUI = "2026-03-15 00:00:00"  # formato de TipoCalibracion/Linealidad
FECHA_DIARIA = "2026-03-15"           # formato `date` de las 4 diarias
EQUIPO = "Clinac 600"
TIPO_FUENTE = "Cambio de fuente"

SEMILLAS = {
    "controles": dict(equipo=EQUIPO, control="Mensual", fecha=FECHA_CONTROL,
                      user_id="fisico"),
    "TipoCalibracion": dict(user="fisico", fecha=FECHA_BRAQUI,
                            tipo=TIPO_FUENTE, serie="SN-1",
                            certificado="CERT-1", fecha_cer=FECHA_BRAQUI,
                            intensidad=1.0, conversion=1.0),
    "LinealidadBraquiterapia": dict(user="fisico", fecha=FECHA_BRAQUI,
                                    modelo="M1", serie_cp="C1"),
    "aceleradorlineal_600": dict(date=FECHA_DIARIA, user_id="fisico"),
    "aceleradorlineal_ix": dict(date=FECHA_DIARIA, user_id="fisico"),
    "halcyon": dict(date=FECHA_DIARIA, user_id="fisico"),
    "braqui": dict(date=FECHA_DIARIA, user_id="fisico"),
}


@pytest.fixture
def bd_raices(monkeypatch, tmp_path):
    """BD temporal con el esquema REAL (el que crea `Conexion()`, columna
    `activo` incluida vía `_asegurar_activo_bloque_qc`) y, en cada raíz, el
    par vigente/anulada del mismo bloque. Nunca toca las BD de referencia."""
    ruta = str(tmp_path / "raices.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()

    con = sqlite3.connect(ruta)
    for tabla, campos in SEMILLAS.items():
        for id_fila, activo in ((ID_ANULADA, 0), (ID_VIGENTE, 1)):
            valores = dict(campos, id=id_fila, activo=activo)
            cols = ", ".join(f'"{c}"' for c in valores)
            marcas = ", ".join("?" * len(valores))
            con.execute(f'INSERT INTO "{tabla}" ({cols}) VALUES ({marcas})',
                        list(valores.values()))
    con.commit()
    con.close()

    yield ruta
    conexion.con.close()
    Conexion._instance = None


def consultar(ruta, sql, params=()):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def ids(filas):
    return sorted(f[0] for f in filas)


# ---------------------------------------------------------------------------
# 0. La premisa: sin el par sintético, este archivo no probaría nada
# ---------------------------------------------------------------------------

def test_las_7_raices_tienen_el_par_vigente_anulada(bd_raices):
    """Si esta fixture dejara de anular de verdad, TODOS los tests de abajo
    pasarían en verde sin distinguir nada -- el mismo riesgo que hacía
    inútil la versión original de LR2 sobre las BD reales (0 anuladas)."""
    for tabla in SEMILLAS:
        filas = consultar(bd_raices, f'SELECT id, activo FROM "{tabla}" '
                                     'WHERE id IN (?, ?) ORDER BY id',
                          (ID_ANULADA, ID_VIGENTE))
        assert filas == [(ID_ANULADA, 0), (ID_VIGENTE, 1)], (
            f"{tabla}: la fixture no dejó el par vigente/anulada")
        assert filtro_activo(tabla) != "", (
            f"{tabla} no está en TABLAS_ANULABLES -- filtro_activo() sería "
            "un no-op y el test no distinguiría nada")


# ---------------------------------------------------------------------------
# 1. IDENTIDAD: la fila anulada SÍ se entrega al pedirla por su id
# ---------------------------------------------------------------------------

SITIOS_IDENTIDAD = {
    "models/PDF/Mensuales/reportes_mensuales.py:241":
        ("controles", "SELECT id, equipo, fecha FROM controles WHERE id = ?"),
    "models/PDF/Mensuales/reportes_mensuales.py:258":
        ("TipoCalibracion", "SELECT id, serie FROM TipoCalibracion WHERE id = ?"),
    "models/PDF/Mensuales/reportes_mensuales.py:281":
        ("LinealidadBraquiterapia",
         "SELECT id, modelo FROM LinealidadBraquiterapia WHERE id = ?"),
    "data/ManejoDatos/load.py:244":
        ("braqui", "SELECT id, pelicula FROM braqui WHERE id = ?"),
    "services/ventana_edicion.py:100":
        ("controles", "SELECT id, activo FROM controles WHERE id = ?"),
    "data/GraficasyTablas/tablas.py:213 (600)":
        ("aceleradorlineal_600",
         "SELECT id, date FROM aceleradorlineal_600 WHERE id = ?"),
    "data/GraficasyTablas/tablas.py:213 (ix)":
        ("aceleradorlineal_ix",
         "SELECT id, date FROM aceleradorlineal_ix WHERE id = ?"),
    "data/GraficasyTablas/tablas.py:213 (halcyon)":
        ("halcyon", "SELECT id, date FROM halcyon WHERE id = ?"),
}


@pytest.mark.parametrize("sitio", sorted(SITIOS_IDENTIDAD))
def test_identidad_entrega_la_fila_anulada(bd_raices, sitio):
    tabla, sql = SITIOS_IDENTIDAD[sitio]
    filas = consultar(bd_raices, sql, (ID_ANULADA,))
    assert ids(filas) == [ID_ANULADA], (
        f"{sitio}: pedir la fila {ID_ANULADA} por su id debe entregarla "
        f"aunque esté anulada ({tabla})")


@pytest.mark.parametrize("sitio", sorted(SITIOS_IDENTIDAD))
def test_identidad_con_filtro_devolveria_nada(bd_raices, sitio):
    """La medida del daño de la dirección contraria (DA-47/LF4): el mismo
    SQL CON filtro no devuelve "la generación vigente", devuelve NADA --
    el formulario se abre en blanco y nadie sabe por qué."""
    tabla, sql = SITIOS_IDENTIDAD[sitio]
    filas = consultar(bd_raices, sql + filtro_activo(tabla), (ID_ANULADA,))
    assert filas == [], (
        f"{sitio}: con filtro, la fila pedida por id desaparece -- es "
        "exactamente por lo que estos sitios NO filtran")


# ---------------------------------------------------------------------------
# 2. LISTA: la fila anulada NO aparece (con el filtro que LR3 pone)
#
# Cada entrada trae el SQL SIN filtro tal y como está hoy en el sitio. El
# test mide las dos formas sobre las mismas filas: la de hoy (devuelve las
# dos) y la de LR3 (devuelve solo la vigente). Esa diferencia ES la
# predicción que LR3 tiene que reproducir.
# ---------------------------------------------------------------------------

SITIOS_LISTA = {
    "models/PDF/Mensuales/reportes_mensuales.py:164": (
        "controles",
        "SELECT id FROM controles WHERE fecha = ? AND equipo = ? "
        "AND control = 'Mensual'",
        (FECHA_CONTROL, EQUIPO)),
    "models/PDF/Anual/reportes_anuales.py:137": (
        "controles",
        "SELECT id FROM controles WHERE fecha = ? AND equipo = ? "
        "AND control = 'Mensual'",
        (FECHA_CONTROL, EQUIPO)),
    "ui/.../seiscientos_mensual.py:238": (
        "controles",
        "SELECT id FROM controles WHERE equipo = ?",
        (EQUIPO,)),
    "ui/.../seiscientos_anual.py:51": (
        "controles",
        "SELECT id FROM controles WHERE fecha LIKE ? AND equipo = ?",
        ("%2026%", EQUIPO)),
    "ui/.../braq_mensual.py:135": (
        "TipoCalibracion",
        "SELECT id FROM TipoCalibracion WHERE DATE(fecha) = ?",
        (FECHA_DIARIA,)),
    "data/ManejoDatos/load.py:932": (
        "TipoCalibracion",
        "SELECT id FROM TipoCalibracion WHERE DATE(fecha) = DATE(?) AND tipo = ?",
        (FECHA_DIARIA, TIPO_FUENTE)),
    "ui/.../braquiterapia.py:1952": (
        "LinealidadBraquiterapia",
        "SELECT id FROM LinealidadBraquiterapia WHERE DATE(fecha) = ?",
        (FECHA_DIARIA,)),
    "ui/.../seiscientos.py:181": (
        "aceleradorlineal_600",
        "SELECT id FROM aceleradorlineal_600 WHERE date = ?",
        (FECHA_DIARIA,)),
    "ui/.../IX.py:265": (
        "aceleradorlineal_ix",
        "SELECT id FROM aceleradorlineal_ix WHERE date = ?",
        (FECHA_DIARIA,)),
    "ui/.../IX.py:430": (
        "aceleradorlineal_ix",
        "SELECT id FROM aceleradorlineal_ix "
        "WHERE date BETWEEN :start_date AND :end_date",
        {"start_date": FECHA_DIARIA, "end_date": FECHA_DIARIA}),
    "data/ManejoDatos/obtenerDatosHalcyon.py:202": (
        "halcyon",
        "SELECT id FROM halcyon WHERE date = ?",
        (FECHA_DIARIA,)),
    "ui/.../braquiterapia.py:340": (
        "braqui",
        "SELECT id FROM braqui WHERE date = ?",
        (FECHA_DIARIA,)),
    "ui/.../braquiterapia.py:1243": (
        "braqui",
        "SELECT id FROM braqui WHERE date BETWEEN :start_date AND :end_date",
        {"start_date": FECHA_DIARIA, "end_date": FECHA_DIARIA}),
}


@pytest.mark.parametrize("sitio", sorted(SITIOS_LISTA))
def test_lista_hoy_deja_pasar_la_anulada(bd_raices, sitio):
    """El estado del que parte DA-48, medido: hoy la fila anulada se cuela
    entre las vigentes en los 31 sitios de `PENDIENTES_LR3`."""
    _tabla, sql, params = SITIOS_LISTA[sitio]
    filas = consultar(bd_raices, sql, params)
    assert ids(filas) == [ID_ANULADA, ID_VIGENTE], (
        f"{sitio}: sin filtro, la consulta devuelve las DOS generaciones")


@pytest.mark.parametrize("sitio", sorted(SITIOS_LISTA))
def test_lista_con_filtro_excluye_la_anulada(bd_raices, sitio):
    """La predicción de LR3: el mismo SQL con `filtro_activo(tabla)` deja de
    ver la anulada y sigue viendo la vigente -- no devuelve nada de menos."""
    tabla, sql, params = SITIOS_LISTA[sitio]
    filas = consultar(bd_raices, sql + filtro_activo(tabla), params)
    assert ids(filas) == [ID_VIGENTE], (
        f"{sitio}: con filtro debe quedar SOLO la generación vigente")


def test_el_filtro_respeta_las_filas_historicas_con_activo_nulo(bd_raices):
    """Las filas anteriores a E7/C2 tienen `activo` NULL, no 1. El filtro
    de LE0 las cuenta como vigentes (`activo IS NULL OR activo = 1`); si
    alguien lo "simplificara" a `activo = 1`, LR3 haría desaparecer todo el
    histórico. Se fija aquí porque LR3 aplica ese filtro a 31 sitios de
    golpe.

    La fila legacy va en OTRO mes a propósito: `idx_controles_unico_mes`
    (U2) es un índice UNIQUE PARCIAL sobre las filas vigentes, así que un
    segundo control ACTIVO del mismo mes se rechaza -- y eso es justo lo que
    permite que el vigente y el anulado convivan (premisa de [[DA-49]],
    comprobada aquí de paso)."""
    con = sqlite3.connect(bd_raices)
    con.execute('INSERT INTO controles (id, equipo, control, fecha, activo) '
                'VALUES (?, ?, ?, ?, NULL)', (903, EQUIPO, "Mensual",
                                              "15/04/2026"))
    con.commit()
    con.close()
    filas = consultar(
        bd_raices,
        "SELECT id FROM controles WHERE equipo = ?" + filtro_activo("controles"),
        (EQUIPO,))
    assert ids(filas) == [ID_VIGENTE, 903]


# ---------------------------------------------------------------------------
# 3. CENSO: las dos ramas se siguen viendo
# ---------------------------------------------------------------------------

def test_censo_de_reactivacion_ve_las_dos_ramas(bd_raices):
    """`load.py:323` (create_control, DA-34): lee `activo` como DATO y
    clasifica en Python. Si LR3 lo filtrara, el candidato anulado
    desaparecería y con él la única forma de desbloquear el mes -- por eso
    se retira en LR7, después del visor de LR6, y no aquí."""
    filas = consultar(
        bd_raices,
        "SELECT id, fecha, activo FROM controles WHERE equipo = ? AND control = ?",
        (EQUIPO, "Mensual"))
    assert ids(filas) == [ID_ANULADA, ID_VIGENTE]
    assert {f[2] for f in filas} == {0, 1}, (
        "el censo tiene que poder distinguir las dos ramas, no solo verlas")


def test_censo_de_migracion_ve_las_dos_ramas(bd_raices):
    """`migrar_bd_a_estandar.py:121/339`: normalizar el centinela histórico
    de 2º físico tiene que alcanzar TAMBIÉN a las filas anuladas -- una
    fila anulada con el dato mal sigue teniendo el dato mal."""
    con = sqlite3.connect(bd_raices)
    con.execute("UPDATE controles SET user_id_f2 = ' ---- ' WHERE id IN (?, ?)",
                (ID_ANULADA, ID_VIGENTE))
    con.commit()
    con.close()
    filas = consultar(bd_raices,
                      "SELECT id FROM controles WHERE user_id_f2 = ?",
                      (" ---- ",))
    assert ids(filas) == [ID_ANULADA, ID_VIGENTE]


# ---------------------------------------------------------------------------
# 4. El desempate: filtrar no basta cuando hay LIMIT sin ORDER BY
# ---------------------------------------------------------------------------

def test_limit_sin_order_by_puede_devolver_la_generacion_equivocada(bd_raices):
    """AN1 marca `LIMIT` sin `ORDER BY` como motivo propio, y con razón: con
    dos generaciones vigentes del mismo bloque (lo que deja una BD anterior
    a MI0/CT2), `LIMIT 1` sin orden devuelve la que SQLite quiera -- en la
    práctica, la más antigua. Los 5 sitios de raíz con esa forma reciben
    `ORDER BY id DESC` en LR3, no solo el filtro."""
    con = sqlite3.connect(bd_raices)
    con.execute('UPDATE braqui SET activo = 1 WHERE id = ?', (ID_ANULADA,))
    con.commit()
    con.close()
    sin_orden = consultar(
        bd_raices,
        "SELECT id FROM braqui WHERE date = ?" + filtro_activo("braqui")
        + " LIMIT 1", (FECHA_DIARIA,))
    con_orden = consultar(
        bd_raices,
        "SELECT id FROM braqui WHERE date = ?" + filtro_activo("braqui")
        + " ORDER BY id DESC LIMIT 1", (FECHA_DIARIA,))
    assert ids(sin_orden) == [ID_ANULADA], (
        "medido: sin ORDER BY sale la fila más antigua del bloque")
    assert ids(con_orden) == [ID_VIGENTE], (
        "con ORDER BY id DESC sale la generación más reciente")
