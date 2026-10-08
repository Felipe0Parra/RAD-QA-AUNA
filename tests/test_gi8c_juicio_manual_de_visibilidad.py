"""GI.8c (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, anotada por GI.1): el juicio manual de visibilidad del bajo contraste queda registrado.

CAUSA: por cada inserto de CTP515 el analisis devuelve `criterio_visibilidad` («manual» si el fisico se pronuncio sobre ese inserto en el posicionador, «calculo» si la visibilidad
calculada lo dio por visible, «ninguno» si no) y `visible_manual`, y el conteo `rois_visibles_visibilidad` y el veredicto `pasa_test_visibilidad` INCLUYEN ese juicio. El escritor
no guardaba el criterio: un control reabierto o impreso no distinguia lo medido de lo que una persona decidio a ojo.

GARANTIAS, una por bloque:

  1. ESTRUCTURA -- `resolucion_contraste_rois.criterio_visibilidad` (TEXT, admite NULL) va en el `CREATE TABLE`; una base ya desplegada la recibe al abrirla (aditiva, idempotente, sin
     relleno retroactivo). Sobre COPIAS de las CINCO BD de referencia la migracion anade EXACTAMENTE esa columna, vacia, y nada mas cambia (huella de cada una de las demas tablas
     identica a la de abrir la misma BD sin el paso, `integrity_check = ok`, `foreign_key_check` en su linea base 109 / 116, y una segunda apertura no cambia nada). Un paso que
     falla no impide el resto del arranque.
  2. ESCRITOR Y LECTOR -- el mapeador lleva el criterio de cada inserto, el escritor lo guarda en su columna y el lector lo devuelve tal cual; un control anterior (NULL) lo devuelve
     como `None` y nunca se inventa.
  3. DE PUNTA A PUNTA CON EL ANALISIS REAL -- un juicio manual sobre dos insertos de una serie real (tomografo y iX): la fila guarda «manual» en esos y «calculo» / «ninguno» en los
     demas, el conteo y el veredicto del resumen son los del analisis, y lo reabierto lo devuelve.
  4. LA NOTA -- «Visibilidad: N de M insertos juzgados a mano» sale en la pantalla y en el PDF REAL solo cuando N > 0, desde UNA sola definicion; sin juicio manual (o en un control
     anterior) no se dice nada.
  5. UN INSERTO QUE NO SE PUDO MEDIR NO TIENE JUICIO -- `resolucion_contraste` dejaba `pasa_vis_final`, `pasa_cnr_final`, `manual_para_este_roi` y `criterio` con lo del inserto ANTERIOR
     del bucle (o reventaba con `UnboundLocalError` si el no medido era el primero): el criterio que ahora se guarda habria salido mal. Hallado al ejecutar la tarea.

Nunca se conecta a una BD de referencia: se copia a un temporal primero.
"""
import copy
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PyQt5.QtWidgets import QLabel

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.catphan_TAC import catphan_db as C
from data.ManejoDatos.conection import Conexion
from test_gi0_estructura_lp_cm_y_error_pct import (  # noqa: F401  (ayudas de GI.0: ensayo sobre copias de las cinco BD)
    CINCO, FK_LINEA_BASE, _abrir_con_la_app, _cols, _copiar, _fk, _huella_filas, _integridad, _tablas, requiere_drop_column)
from test_gi1_guardado_claves_del_analisis import (  # noqa: F401  (helpers y fixtures de GI.1: una sola definicion de la forma del productor)
    SERIES, _analisis_real, _crear_control, _filas, _guardar, _id_prueba, _leer, _resultado_contraste, app, bd_nueva)
from test_gi2_lectura_es_lo_guardado import _ejecutar, _reabrir, bd_copia_real          # noqa: F401
from _informe_imagenes import avisos, generar as _generar_informe, paginas as _paginas_del_informe  # noqa: F401

TABLA = "resolucion_contraste_rois"
COLUMNA = "criterio_visibilidad"
NOTA = "Visibilidad: {n} de {m} insertos juzgados a mano"


def _con_la_columna_quitada(ruta):
    """La BD como la tienen las ya desplegadas: la tabla SIN la columna (el estado de las cinco BD de referencia)."""
    con = sqlite3.connect(ruta)
    try:
        con.execute(f'ALTER TABLE "{TABLA}" DROP COLUMN {COLUMNA}')
        con.commit()
    finally:
        con.close()


def _maestro(ruta):
    """(tipo, nombre, tabla) de todo lo que hay en sqlite_master: tablas, indices y triggers (sin su texto: ALTER TABLE lo reescribe)."""
    con = sqlite3.connect(ruta)
    try:
        return sorted(con.execute("SELECT type, name, tbl_name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall())
    finally:
        con.close()


def _huella_sin_la_hora(ruta):
    """La huella de TODAS las tablas; la de `audit_log` sin la marca de tiempo ni el detalle (abrir la app escribe un `login` cada vez)."""
    con = sqlite3.connect(ruta)
    try:
        return {t: _huella_filas(con, t, ["id", "usuario", "accion", "tabla"] if t == "audit_log" else None) for t in _tablas(con)}
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 1. ESTRUCTURA
# ---------------------------------------------------------------------------

def test_el_create_table_declara_la_columna_como_texto_que_admite_null_sin_depender_de_la_migracion(app, tmp_path, monkeypatch):
    """`ALTER TABLE ... ADD COLUMN` reescribe el texto del esquema, asi que una base cuya columna la puso la migracion es indistinguible de una que la declara el CREATE: se abre una
    base NUEVA con el paso de la migracion desactivado y la columna tiene que estar igual."""
    ruta = str(tmp_path / "nueva_sin_paso.db")
    with monkeypatch.context() as m:
        m.setattr(Conexion, "_asegurar_criterio_visibilidad_roi", lambda self: None)
        m.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        Conexion._instance = None
        Conexion().con.close()
        Conexion._instance = None
    con = sqlite3.connect(ruta)
    try:
        info = {c[1]: c for c in con.execute(f"PRAGMA table_info('{TABLA}')")}
    finally:
        con.close()
    assert COLUMNA in info, "el CREATE TABLE no la declara: una instalacion nueva dependeria de la migracion"
    assert info[COLUMNA][2].upper() == "TEXT" and info[COLUMNA][3] == 0, info[COLUMNA]          # tipo TEXT, notnull = 0
    assert info[COLUMNA][4] is None, f"el CREATE TABLE no puede rellenar un criterio por omision: {info[COLUMNA]}"      # sin DEFAULT: una fila sin criterio es NULL, igual que en las migradas


@requiere_drop_column
def test_una_bd_ya_desplegada_recibe_la_columna_al_abrir_y_una_segunda_apertura_no_cambia_nada(bd_nueva, tmp_path, monkeypatch):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": _resultado_contraste((15, 9, 8, 7), (15, 9, 8, 7))}) == sesion
    Conexion._instance.con.close()
    Conexion._instance = None
    _con_la_columna_quitada(bd_nueva)
    assert COLUMNA not in _cols(bd_nueva, TABLA)
    _abrir_con_la_app(bd_nueva, monkeypatch)
    assert COLUMNA in _cols(bd_nueva, TABLA)
    con = sqlite3.connect(bd_nueva)
    try:
        info = {c[1]: c for c in con.execute(f"PRAGMA table_info('{TABLA}')")}[COLUMNA]
    finally:
        con.close()
    assert (info[2].upper(), info[3], info[4]) == ("TEXT", 0, None), info                  # la migrada tambien: TEXT, admite NULL, sin DEFAULT
    despues = _huella_sin_la_hora(bd_nueva)
    _abrir_con_la_app(bd_nueva, monkeypatch)                                                # segunda apertura: nada cambia
    assert _huella_sin_la_hora(bd_nueva) == despues
    con = sqlite3.connect(bd_nueva)
    try:
        assert con.execute(f"SELECT COUNT(*) FROM {TABLA} WHERE {COLUMNA} IS NOT NULL").fetchone()[0] == 0
    finally:
        con.close()


@requiere_drop_column
@pytest.mark.parametrize("origen", CINCO, ids=lambda p: p.name)
def test_la_migracion_anade_exactamente_una_columna_vacia_y_no_toca_nada_mas(origen, tmp_path, monkeypatch):
    """El diferencial de la tarea sobre COPIAS de las cinco BD de referencia: abrir la copia con la app SIN el paso de GI.8c contra abrirla CON el paso."""
    sin_paso = _copiar(origen, tmp_path, "sin_paso.db")
    con_paso = _copiar(origen, tmp_path, "con_paso.db")
    with monkeypatch.context() as m:
        m.setattr(Conexion, "_asegurar_criterio_visibilidad_roi", lambda self: None)
        _abrir_con_la_app(sin_paso, m)
    # una base que la app aun no creo con la columna (las cinco son anteriores): sin el paso, no la tiene
    assert COLUMNA not in _cols(sin_paso, TABLA), "la columna ya estaba en la BD de referencia: el ensayo no mide la migracion"
    _abrir_con_la_app(con_paso, monkeypatch)

    assert _cols(con_paso, TABLA) == _cols(sin_paso, TABLA) + [COLUMNA], "la migracion tiene que anadir EXACTAMENTE esa columna, al final"
    a, b = sqlite3.connect(sin_paso), sqlite3.connect(con_paso)
    try:
        assert _tablas(a) == _tablas(b)
        for tabla in _tablas(a):
            if tabla == TABLA:
                viejas = _cols(sin_paso, TABLA)
                assert _huella_filas(a, tabla, viejas) == _huella_filas(b, tabla, viejas), f"{tabla}: cambio una columna que ya existia"
            elif tabla == "audit_log":
                # abrir la app escribe un `login` / «respaldo al cerrar» con su marca de tiempo: dos aperturas dan marcas distintas; se compara lo que no es la hora
                quien = ["id", "usuario", "accion", "tabla"]
                assert _huella_filas(a, tabla, quien) == _huella_filas(b, tabla, quien), f"{tabla}: cambio su contenido"
            else:
                assert _huella_filas(a, tabla) == _huella_filas(b, tabla), f"{tabla}: cambio su contenido"
        n = b.execute(f"SELECT COUNT(*) FROM {TABLA}").fetchone()[0]
        assert n > 0 and b.execute(f"SELECT COUNT(*) FROM {TABLA} WHERE {COLUMNA} IS NULL").fetchone()[0] == n, "la columna nueva tiene que quedar vacia en todo lo anterior"
    finally:
        a.close()
        b.close()
    assert _maestro(sin_paso) == _maestro(con_paso), "cambio un indice, un trigger o una tabla"
    assert _integridad(con_paso) == "ok"
    assert _fk(con_paso) == FK_LINEA_BASE[origen.name], "foreign_key_check se aparto de su linea base (DA-43)"
    huella = _huella_sin_la_hora(con_paso)
    _abrir_con_la_app(con_paso, monkeypatch)                                                       # segunda corrida: idempotente
    assert _huella_sin_la_hora(con_paso) == huella
    assert _maestro(sin_paso) == _maestro(con_paso)


@requiere_drop_column
def test_si_el_paso_no_se_puede_hacer_el_resto_del_arranque_sigue(tmp_path, monkeypatch, capsys):
    """Igual que el resto de pasos aditivos: un `ALTER TABLE` que falla se avisa y NO corta la cadena (que vive en UN try/except). Prueba de que la cadena sigue: un paso POSTERIOR
    (el renombrado de GI.0) se hace igual."""
    ruta = str(tmp_path / "nueva.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    Conexion().con.close()
    Conexion._instance = None
    _con_la_columna_quitada(ruta)
    _con_nombres_viejos_solo_renombres(ruta)

    original = conection_mod._asegurar_columna

    def falla_solo_para_la_columna(cursor, tabla, columna, ddl):
        if columna == COLUMNA:
            raise sqlite3.OperationalError("falla de prueba")
        return original(cursor, tabla, columna, ddl)

    monkeypatch.setattr(conection_mod, "_asegurar_columna", falla_solo_para_la_columna)
    _abrir_con_la_app(ruta, monkeypatch)
    assert COLUMNA not in _cols(ruta, TABLA)
    assert f"Aviso: no se pudo asegurar '{TABLA}.{COLUMNA}'" in capsys.readouterr().out
    assert "lp_cm_maximo" in _cols(ruta, "resolucion_espacial"), "el paso posterior (renombrado de GI.0) no se hizo: el fallo corto el arranque"


def _con_nombres_viejos_solo_renombres(ruta):
    """Solo los nombres viejos de GI.0 (lp_mm...), sin tocar `error_pct`: lo unico que hace falta para probar que un paso POSTERIOR del arranque sigue corriendo."""
    con = sqlite3.connect(ruta)
    try:
        con.execute('ALTER TABLE "resolucion_espacial" RENAME COLUMN "lp_cm_maximo" TO "lp_mm_maximo"')
        con.commit()
    finally:
        con.close()


def test_la_herramienta_de_migracion_deja_la_columna(tmp_path):
    """`scripts/migrar_bd_a_estandar.py` crea `Conexion()`: usa el mismo paso. Sobre una copia de la BD del 21-09 y SIN guardar la columna antes."""
    from _bd_referencia import BD_REBUILD_21_09
    from scripts.migrar_bd_a_estandar import migrar
    ruta = _copiar(BD_REBUILD_21_09, tmp_path, "migrar.db")
    assert COLUMNA not in _cols(ruta, TABLA)
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        migrar(ruta, aplicar=True)
    assert COLUMNA in _cols(ruta, TABLA)
    Conexion._instance = None


# ---------------------------------------------------------------------------
# 2. ESCRITOR Y LECTOR
# ---------------------------------------------------------------------------

def test_el_mapeador_lleva_el_criterio_de_cada_inserto_y_none_si_no_viene():
    resultado = _resultado_contraste((15, 9), (15, 9, 8))
    resultado["resultados_roi"]["15mm"]["criterio_visibilidad"] = "manual"
    resultado["resultados_roi"]["8mm"].pop("criterio_visibilidad")             # un resultado reconstruido de un control anterior no lo trae
    _, lista = C.mapear_resolucion_contraste(resultado)
    por_diametro = {r["diametro_mm"]: r["criterio_visibilidad"] for r in lista}
    assert por_diametro == {15: "manual", 9: "calculo", 8: None, 7: "ninguno", 6: "ninguno", 5: "ninguno"}


def test_el_escritor_guarda_cada_criterio_en_su_fila_y_el_lector_lo_devuelve(bd_nueva):
    resultado = _resultado_contraste((15, 9, 8, 7), (15, 9, 8, 7))
    esperado = {15: "manual", 9: "calculo", 8: "manual", 7: "calculo", 6: "ninguno", 5: "ninguno"}
    for d, criterio in esperado.items():
        resultado["resultados_roi"][f"{d}mm"]["criterio_visibilidad"] = criterio
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": resultado}) == sesion
    con = _leer(bd_nueva)
    try:
        filas = _filas(con, TABLA, _id_prueba(con, sesion, "resolucion_contraste"))
        assert {f["diametro_mm"]: f[COLUMNA] for f in filas} == esperado
    finally:
        con.close()
    leido = _reabrir(bd_nueva, "resolucion_contraste", sesion)["resultados_roi"]
    assert {int(k.replace("mm", "")): v["criterio_visibilidad"] for k, v in leido.items()} == esperado
    assert C.insertos_juzgados_a_mano(leido) == (2, 6)


@pytest.mark.parametrize("como", ["none", "ausente"])
def test_un_criterio_ausente_pasa_por_el_escritor_real_y_queda_null_nunca_vacio(bd_nueva, como):
    """Un resultado reconstruido de la base (sin la clave) o con `None` se guarda con NULL: el escritor no inventa ni un criterio ni una cadena vacia."""
    resultado = _resultado_contraste((15, 9, 8, 7), (15, 9, 8, 7))
    for roi in resultado["resultados_roi"].values():
        if como == "none":
            roi["criterio_visibilidad"] = None
        else:
            roi.pop("criterio_visibilidad", None)
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": resultado}) == sesion
    con = _leer(bd_nueva)
    try:
        filas = _filas(con, TABLA, _id_prueba(con, sesion, "resolucion_contraste"))
        assert len(filas) == 6 and [f[COLUMNA] for f in filas] == [None] * 6
    finally:
        con.close()


def test_un_control_anterior_sin_criterio_devuelve_none_y_no_inventa_nada(bd_nueva):
    resultado = _resultado_contraste((15, 9, 8, 7), (15, 9, 8, 7))
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"resolucion_contraste": resultado}) == sesion
    _ejecutar(bd_nueva, f"UPDATE {TABLA} SET {COLUMNA} = NULL")                               # como quedaron todos los controles anteriores a GI.8c
    leido = _reabrir(bd_nueva, "resolucion_contraste", sesion)
    assert all(v["criterio_visibilidad"] is None for v in leido["resultados_roi"].values())
    assert C.insertos_juzgados_a_mano(leido["resultados_roi"]) == (0, 6)
    assert C.nota_visibilidad_a_mano(leido["resultados_roi"]) is None
    # el resumen no depende del criterio: lo guardado manda
    assert leido["resumen"]["rois_visibles_visibilidad"] == 4 and leido["resumen"]["pasa_test_visibilidad"] is True


# ---------------------------------------------------------------------------
# 3. DE PUNTA A PUNTA CON EL ANALISIS REAL
# ---------------------------------------------------------------------------

JUICIO = {"15mm": False, "7mm": True}      # el fisico descarta el de 15 mm y da por visible el de 7 mm


@pytest.fixture(scope="module", params=("TOMOGRAFO", "IX_DIC"))
def base_con_juicio(request, app, tmp_path_factory):
    """El analisis REAL de una serie con un juicio manual sobre dos insertos, guardado con el escritor real en una BD nueva.

    `_analisis_real` de test_gi1 es un `lru_cache`: se llama SU funcion sin cache (`__wrapped__`). Con la cache, si otra prueba (test_gi1, que corre antes en el orden alfabetico de la suite) ya
    habia analizado la serie, el analisis con juicio nunca se ejecutaria (8 errores); y si esta corriera primero dejaria SU analisis, con el juicio inyectado, en la cache de las demas."""
    from analisisImagenes import Analisis_Catphan_TAC as AN
    clave = request.param
    original = AN.resolucion_contraste
    llamadas = []

    def con_juicio(*a, **kw):
        llamadas.append((a, dict(kw)))
        kw["visibilidad_manual"] = dict(JUICIO)
        return original(*a, **kw)

    mp = pytest.MonkeyPatch()
    mp.setattr(AN, "resolucion_contraste", con_juicio)
    try:
        equipo, px, nominal, salidas = _analisis_real.__wrapped__(clave)
    finally:
        mp.undo()
    assert len(llamadas) == 1
    a0, kw0 = llamadas[0]

    def reanalizar(juicio):
        """El MISMO analisis de contraste (mismo corte, mismos parametros del equipo) con otro juicio manual: la parte barata de volver a medir."""
        return original(*a0, **{**kw0, "visualizar": False, "visibilidad_manual": juicio})

    ruta = str(tmp_path_factory.mktemp("gi8c") / "real.db")
    mp = pytest.MonkeyPatch()
    mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    try:
        sesion = _crear_control(ruta, equipo)
        assert _guardar(sesion, copy.deepcopy(salidas), equipo=equipo, espesor_corte=nominal, tam_px_teorico=px) == sesion
    finally:
        conexion.con.close()
        Conexion._instance = None
        mp.undo()
    import types
    return types.SimpleNamespace(clave=clave, equipo=equipo, ruta=ruta, sesion=sesion, contraste=salidas["resolucion_contraste"], reanalizar=reanalizar)


def test_real_el_analisis_marca_manual_solo_los_insertos_juzgados(base_con_juicio):
    rois = base_con_juicio.contraste["resultados_roi"]
    assert {n: r["criterio_visibilidad"] for n, r in rois.items() if r["criterio_visibilidad"] == "manual"} == {"15mm": "manual", "7mm": "manual"}
    assert rois["15mm"]["visible_manual"] is False and rois["15mm"]["pasa_visibilidad_lim"] is False
    assert rois["7mm"]["visible_manual"] is True and rois["7mm"]["pasa_visibilidad_lim"] is True
    for n in ("9mm", "8mm", "6mm", "5mm"):
        # el que el fisico no toco queda con el criterio EXACTO del calculo: «calculo» si la visibilidad calculada lo dio por visible y «ninguno» si no
        esperado = "calculo" if rois[n]["pasa_visibilidad_lim"] else "ninguno"
        assert rois[n]["criterio_visibilidad"] == esperado and rois[n]["visible_manual"] is None, n
    assert any(rois[n]["criterio_visibilidad"] == "ninguno" for n in ("9mm", "8mm", "6mm", "5mm")), "la serie debe tener algun inserto no visible para que la prueba discrimine"


def test_real_el_conteo_y_el_veredicto_del_resumen_incluyen_el_juicio(base_con_juicio):
    rois = base_con_juicio.contraste["resultados_roi"]
    resumen = base_con_juicio.contraste["resumen"]
    assert resumen["rois_visibles_visibilidad"] == sum(1 for r in rois.values() if r["pasa_visibilidad_lim"])
    assert resumen["pasa_test_visibilidad"] == (resumen["rois_visibles_visibilidad"] >= resumen["min_rois_visibles"])


def test_real_un_juicio_que_cruza_el_minimo_cambia_el_conteo_y_el_veredicto_del_resumen(base_con_juicio):
    """Con el calculo solo la serie no llega al minimo de insertos visibles; un juicio que da por visibles a todos SI llega, y uno que los descarta a todos deja el conteo en cero: el
    conteo y el veredicto del resumen INCLUYEN el juicio (no son los del calculo). El juicio de la fixture (2 insertos) no basta: en una serie se compensa y en la otra no cruza el minimo."""
    nombres = list(base_con_juicio.contraste["resultados_roi"])
    minimo = base_con_juicio.contraste["resumen"]["min_rois_visibles"]
    solo_calculo = base_con_juicio.reanalizar(None)["resumen"]
    todos = base_con_juicio.reanalizar({n: True for n in nombres})["resumen"]
    ninguno = base_con_juicio.reanalizar({n: False for n in nombres})["resumen"]
    assert solo_calculo["rois_visibles_visibilidad"] < minimo and bool(solo_calculo["pasa_test_visibilidad"]) is False, "el calculo solo no debe llegar al minimo en estas series"
    assert todos["rois_visibles_visibilidad"] == len(nombres) and bool(todos["pasa_test_visibilidad"]) is True
    assert ninguno["rois_visibles_visibilidad"] == 0 and bool(ninguno["pasa_test_visibilidad"]) is False


def test_real_la_fila_guarda_el_criterio_de_cada_inserto_y_el_resumen_no_cambia(base_con_juicio):
    rois = base_con_juicio.contraste["resultados_roi"]
    con = _leer(base_con_juicio.ruta)
    try:
        id_prueba = _id_prueba(con, base_con_juicio.sesion, "resolucion_contraste")
        guardado = {f["diametro_mm"]: f for f in _filas(con, TABLA, id_prueba)}
        assert {d: f[COLUMNA] for d, f in guardado.items()} == {int(n.replace("mm", "")): r["criterio_visibilidad"] for n, r in rois.items()}
        for d, f in guardado.items():
            assert bool(f["pasa_visibilidad_lim"]) is bool(rois[f"{d}mm"]["pasa_visibilidad_lim"]), d      # el veredicto por inserto sigue siendo el del analisis
        resumen = con.execute("SELECT * FROM resolucion_contraste WHERE id_prueba = ?", (id_prueba,)).fetchone()
        assert resumen["rois_visibles_visibilidad"] == base_con_juicio.contraste["resumen"]["rois_visibles_visibilidad"]
        assert bool(resumen["pasa_test_visibilidad"]) is bool(base_con_juicio.contraste["resumen"]["pasa_test_visibilidad"])
    finally:
        con.close()


def test_real_lo_reabierto_devuelve_el_criterio_y_la_nota_dice_dos_de_seis(base_con_juicio):
    leido = _reabrir(base_con_juicio.ruta, "resolucion_contraste", base_con_juicio.sesion)
    rois = base_con_juicio.contraste["resultados_roi"]
    assert {k: v["criterio_visibilidad"] for k, v in leido["resultados_roi"].items()} == {k: v["criterio_visibilidad"] for k, v in rois.items()}
    assert C.nota_visibilidad_a_mano(leido["resultados_roi"]) == NOTA.format(n=2, m=6)


def test_real_el_juicio_con_la_forma_del_posicionador_real_cuenta_todos_los_insertos_DP156(base_con_juicio):
    """El posicionador real, una vez que el fisico entra al modo manual, entrega las SEIS casillas y todas arrancan en True (DP-156): aceptar sin desmarcar es un juicio «visible» sobre cada
    inserto. La tarea no cambia ese arranque (decision del fisico, DP-156); lo vuelve visible: el analisis lo registra como «manual» en los seis y la nota dice «6 de 6». Cuando el fisico
    decida otro arranque, esta prueba se actualiza A PROPOSITO."""
    nombres = list(base_con_juicio.contraste["resultados_roi"])
    rois = base_con_juicio.reanalizar({n: True for n in nombres})["resultados_roi"]
    assert {n: r["criterio_visibilidad"] for n, r in rois.items()} == {n: "manual" for n in nombres}
    assert C.nota_visibilidad_a_mano(rois) == NOTA.format(n=len(nombres), m=len(nombres))


# ---------------------------------------------------------------------------
# 4. LA NOTA: una definicion, la pantalla y el PDF real
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rois, esperado", [
    (None, None),
    ({}, None),
    ({"15mm": {"criterio_visibilidad": "calculo"}, "9mm": {"criterio_visibilidad": "ninguno"}}, None),
    ({"15mm": {"criterio_visibilidad": None}, "9mm": {}}, None),                                  # un control anterior: NULL, no se sabe -> no se dice nada
    ({"15mm": {"criterio_visibilidad": "manual"}, "9mm": {"criterio_visibilidad": "calculo"}}, NOTA.format(n=1, m=2)),
    ({f"{d}mm": {"criterio_visibilidad": "manual"} for d in (15, 9, 8, 7, 6, 5)}, NOTA.format(n=6, m=6)),
    ({"15mm": {"criterio_visibilidad": "manual"}, "texto": "no es un inserto"}, NOTA.format(n=1, m=1)),   # solo cuentan los diccionarios
    ({"15mm": {"criterio_visibilidad": "MANUAL"}}, None),                                          # el criterio es exacto: ningun valor parecido cuenta
])
def test_la_nota_sale_solo_con_al_menos_un_inserto_juzgado_a_mano(rois, esperado):
    assert C.nota_visibilidad_a_mano(rois) == esperado


def _notas_de_pantalla(resultados):
    widget = C.tabla_resultados_resolucion_contraste(resultados)
    try:
        return [l.text() for l in widget.findChildren(QLabel, "nota_visibilidad_a_mano")]
    finally:
        widget.deleteLater()


@pytest.mark.parametrize("visibles", [(15, 9, 8, 7), ()], ids=["con_visibles", "sin_ninguno_visible"])
def test_la_pantalla_dice_la_nota_en_las_dos_ramas_y_solo_con_juicio_manual(app, visibles):
    resultado = _resultado_contraste(visibles, visibles)
    assert _notas_de_pantalla(resultado) == []
    resultado["resultados_roi"]["9mm"]["criterio_visibilidad"] = "manual"
    resultado["resultados_roi"]["5mm"]["criterio_visibilidad"] = "manual"
    assert _notas_de_pantalla(resultado) == [NOTA.format(n=2, m=6)]


def test_en_la_rama_sin_insertos_visibles_el_alto_maximo_deja_sitio_a_la_nota(app):
    """Sin la nota la tarjeta mide 120 px como siempre; con ella el maximo crece lo que ocupa la etiqueta (si no, la nota le quitaria el sitio al mensaje y al resumen)."""
    sin_nota = C.tabla_resultados_resolucion_contraste(_resultado_contraste((), ()))
    resultado = _resultado_contraste((), ())
    resultado["resultados_roi"]["9mm"]["criterio_visibilidad"] = "manual"
    con_nota = C.tabla_resultados_resolucion_contraste(resultado)
    try:
        etiqueta = con_nota.findChildren(QLabel, "nota_visibilidad_a_mano")
        assert len(etiqueta) == 1 and sin_nota.maximumHeight() == 120
        assert con_nota.maximumHeight() >= sin_nota.maximumHeight() + etiqueta[0].sizeHint().height()
    finally:
        sin_nota.deleteLater()
        con_nota.deleteLater()


def _id_de_prueba_real(ruta, sesion):
    con = _leer(ruta)
    try:
        return _id_prueba(con, sesion, "resolucion_contraste")
    finally:
        con.close()


def _equipo_y_fecha(ruta, sesion):
    con = _leer(ruta)
    try:
        fila = con.execute("SELECT equipo, fecha FROM controles WHERE id = ?", (sesion,)).fetchone()
    finally:
        con.close()
    return fila["equipo"], fila["fecha"]


def test_el_pdf_real_dice_la_nota_una_vez_con_juicio_manual_y_no_la_dice_sin_el(bd_copia_real, monkeypatch, avisos):
    equipo, fecha = _equipo_y_fecha(bd_copia_real, 48)
    ok, recibido = _generar_informe(bd_copia_real, monkeypatch, 48, equipo, fecha)
    assert ok and not avisos, avisos
    sin = " ".join("\n".join(_paginas_del_informe(recibido["pdf"])).split())
    assert "juzgados a mano" not in sin, "un control anterior (criterio NULL) no puede decir nada"
    id_prueba = _id_de_prueba_real(bd_copia_real, 48)
    _ejecutar(bd_copia_real, f"UPDATE {TABLA} SET {COLUMNA} = 'manual' WHERE id_prueba = ? AND diametro_mm IN (15, 9)", (id_prueba,))
    ok, recibido = _generar_informe(bd_copia_real, monkeypatch, 48, equipo, fecha)
    assert ok and not avisos, avisos
    con_nota = " ".join("\n".join(_paginas_del_informe(recibido["pdf"])).split())
    assert con_nota.count(NOTA.format(n=2, m=6)) == 1, con_nota.count("juzgados a mano")
    # lo demas del bloque de contraste del informe no cambia: el resumen sigue diciendo lo mismo
    assert con_nota.split("ROIs visibles")[1].lstrip().startswith("6 Sí")


def test_el_pdf_de_una_sesion_sin_juicio_manual_es_el_de_siempre(bd_copia_real, monkeypatch, avisos):
    """Control: la sesion 21 (3 visibles, «No»): la columna nueva vacia no cambia una sola palabra del bloque de contraste."""
    equipo, fecha = _equipo_y_fecha(bd_copia_real, 21)
    ok, recibido = _generar_informe(bd_copia_real, monkeypatch, 21, equipo, fecha)
    assert ok and not avisos, avisos
    plano = " ".join("\n".join(_paginas_del_informe(recibido["pdf"])).split())
    assert "juzgados a mano" not in plano
    assert plano.split("ROIs visibles")[1].lstrip().startswith("3 No")


# ---------------------------------------------------------------------------
# 5. UN INSERTO QUE NO SE PUDO MEDIR NO TIENE JUICIO
# ---------------------------------------------------------------------------

class _GeometriaDeDosInsertos:
    """La interfaz minima que usa `resolucion_contraste` cuando se le pasa `catphan`: dos insertos y un fantoma de 100 px de radio en el centro de una imagen de 256 px. Un inserto
    cuyo centro cae fuera del fantoma no se puede medir."""
    ROI_CONFIG = {"15mm": {"angulo": 0.0, "radio_mm": 7.5, "diametro_mm": 15}, "9mm": {"angulo": 60.0, "radio_mm": 4.5, "diametro_mm": 9}}
    ROI_DIST_MM = 58.0
    centro_int, radio_int = (128, 128), 100

    def __init__(self, centros):
        self._centros = centros

    def posicion_roi(self, angulo, dist_mm, radio_mm):
        return (60, 60), 6                                       # el fondo, dentro de la imagen y en el ruido

    def obtener_roi(self, nombre):
        return self._centros[nombre], 8

    def obtener_roi_float(self, nombre):
        return tuple(float(v) for v in self._centros[nombre]), 8.0


def _contraste_con(centros, manual=None):
    from analisisImagenes import Analisis_Catphan_TAC as AN
    rng = np.random.default_rng(7)
    hu = rng.normal(0.0, 5.0, (256, 256)).astype(np.float32)
    yy, xx = np.mgrid[0:256, 0:256]
    hu[(xx - 128) ** 2 + (yy - 128) ** 2 <= 8 ** 2] += 60.0         # un disco brillante en el centro del fantoma: el inserto que SI se mide es visible por el calculo
    return AN.resolucion_contraste(np.full((256, 256), 128, np.uint8), hu, 1.0, catphan=_GeometriaDeDosInsertos(centros), visualizar=False,
                                   cnr_lim=1.0, visibilidad_lim=0.1, min_rois_visibles=1, visibilidad_manual=manual)


DENTRO, FUERA = (128, 128), (250, 250)


@pytest.mark.parametrize("manual", [None, {"15mm": True, "9mm": True}], ids=["sin_juicio", "juicio_a_todos"])
def test_un_inserto_no_medido_que_sigue_a_uno_visible_no_hereda_su_juicio(manual):
    rois = _contraste_con({"15mm": DENTRO, "9mm": FUERA}, manual)["resultados_roi"]
    assert rois["15mm"]["roi_prom"] is not None and bool(rois["15mm"]["pasa_visibilidad_lim"]) is True        # el analisis devuelve numpy.bool_: se compara por valor
    assert rois["15mm"]["criterio_visibilidad"] == ("manual" if manual else "calculo")
    no_medido = rois["9mm"]
    assert no_medido["roi_prom"] is None
    assert (no_medido["criterio_visibilidad"], no_medido["visible_manual"]) == ("ninguno", None)
    assert not no_medido["pasa_visibilidad_lim"] and not no_medido["pasa_visibilidad"] and not no_medido["pasa_cnr"]
    assert all(isinstance(no_medido[k], bool) for k in ("pasa_visibilidad_lim", "pasa_visibilidad", "pasa_cnr")), "un inserto no medido dice False, no un valor heredado"


@pytest.mark.parametrize("manual", [None, {"15mm": True, "9mm": True}], ids=["sin_juicio", "juicio_a_todos"])
def test_un_inserto_no_medido_que_es_el_primero_ya_no_revienta_el_analisis(manual):
    resultado = _contraste_con({"15mm": FUERA, "9mm": DENTRO}, manual)
    rois = resultado["resultados_roi"]
    assert rois["15mm"]["roi_prom"] is None and (rois["15mm"]["criterio_visibilidad"], rois["15mm"]["pasa_visibilidad_lim"]) == ("ninguno", False)
    assert bool(rois["9mm"]["pasa_visibilidad_lim"]) is True
    assert resultado["resumen"]["rois_visibles_visibilidad"] == 1               # solo cuenta el que se midio


def test_los_insertos_no_medidos_no_entran_a_la_nota_de_juicio_manual():
    rois = _contraste_con({"15mm": DENTRO, "9mm": FUERA}, {"15mm": True, "9mm": True})["resultados_roi"]
    assert C.insertos_juzgados_a_mano(rois) == (1, 2)


# ---------------------------------------------------------------------------
# 6. EL SITIO DE LLAMADA: un Cancelar del posicionador no es un juicio
# ---------------------------------------------------------------------------
# Hallado por la revision de GI.8c: `tac_mensual` calculaba `visibilidad` solo si el fisico ACEPTABA el posicionador, pero le pasaba al analisis `dlg.visibilidad_manual` (que no depende de
# aceptar o cancelar). Desde que el criterio se archiva, entrar al modo manual y pulsar Cancelar habria quedado escrito como «6 de 6 insertos juzgados a mano». La pantalla REAL del
# tomografo con la serie REAL y el posicionador REAL (solo su `exec_` modal se sustituye por lo que haria una persona).

from test_gi5_imagen_se_fija_al_analizar import MODULO, TOOLBOX, _Sesion, bd_temporal, dialogos      # noqa: E402,F401  (la pantalla real con una serie real, y sus fixtures)
from _corpus import serie_catphan                                                                    # noqa: E402

QDIALOG_ACEPTADO, QDIALOG_RECHAZADO = 1, 0


@pytest.fixture
def pantalla_del_tomografo(app, bd_temporal, dialogos):
    carpeta = serie_catphan("TOMOGRAFO")
    if not carpeta:
        pytest.skip("sin el corpus real de Catphan (HI-0)")
    sesion = _Sesion(bd_temporal).cargar(carpeta)
    yield sesion
    sesion.cerrar()


def _analizar_el_contraste(sesion, monkeypatch, que_hace_la_persona):
    """La persona abre el posicionador, hace `que_hace_la_persona(dialogo)` y devuelve su resultado (1 acepta, 0 cancela); el analisis es el de la pantalla real."""
    from data.ManejoDatos.catphan_TAC.posicionador_manual import PosicionadorDialog
    monkeypatch.setattr(PosicionadorDialog, "exec_", que_hace_la_persona)
    sesion.elegir("resolucion_contraste", sesion.cortes[MODULO["resolucion_contraste"]])
    return sesion.obj.resultados_resolucion_contraste["resultados_roi"]


def _entra_al_modo_manual_y(aceptar, desmarca=()):
    def exec_(dialogo):
        dialogo._cambiar_modo("manual")                      # la persona pulsa «Manual»
        for nombre in desmarca:
            dialogo._checkboxes_visibilidad[nombre].setChecked(False)
        return QDIALOG_ACEPTADO if aceptar else QDIALOG_RECHAZADO
    return exec_


def test_cancelar_el_posicionador_despues_de_entrar_al_modo_manual_no_registra_ningun_juicio(pantalla_del_tomografo, monkeypatch):
    rois = _analizar_el_contraste(pantalla_del_tomografo, monkeypatch, _entra_al_modo_manual_y(aceptar=False, desmarca=("15mm",)))
    assert [n for n, r in rois.items() if r["criterio_visibilidad"] == "manual"] == [], "un Cancelar no es un juicio"
    assert all(r["visible_manual"] is None for r in rois.values())
    assert C.nota_visibilidad_a_mano(rois) is None
    assert all(r["criterio_visibilidad"] in ("calculo", "ninguno") for r in rois.values())


def test_aceptar_el_posicionador_en_el_modo_manual_registra_el_juicio_de_cada_inserto(pantalla_del_tomografo, monkeypatch):
    """Aceptar sin desmarcar da por visibles a los seis (DP-156); desmarcar el de 15 mm lo descarta a mano."""
    rois = _analizar_el_contraste(pantalla_del_tomografo, monkeypatch, _entra_al_modo_manual_y(aceptar=True, desmarca=("15mm",)))
    assert {n: r["criterio_visibilidad"] for n, r in rois.items()} == {n: "manual" for n in rois}
    assert rois["15mm"]["visible_manual"] is False and rois["15mm"]["pasa_visibilidad_lim"] is False
    assert all(r["visible_manual"] is True for n, r in rois.items() if n != "15mm")
    assert C.nota_visibilidad_a_mano(rois) == NOTA.format(n=len(rois), m=len(rois))


@pytest.mark.parametrize("aceptar", [True, False], ids=["acepta", "cancela"])
def test_sin_entrar_al_modo_manual_no_hay_juicio_se_acepte_o_se_cancele(pantalla_del_tomografo, monkeypatch, aceptar):
    rois = _analizar_el_contraste(pantalla_del_tomografo, monkeypatch, lambda dialogo: QDIALOG_ACEPTADO if aceptar else QDIALOG_RECHAZADO)
    assert [n for n, r in rois.items() if r["criterio_visibilidad"] == "manual"] == []
    assert C.nota_visibilidad_a_mano(rois) is None
