"""GI.8d (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, anotada por GI.3): el rango «HU esperado» de Valores CT es el que usó el análisis.

CAUSA: `Analisis_Catphan_TAC.valor_numero_ct` decide «Dentro del Rango» / «Fuera de Rango» con el rango de su propia tabla de insertos (`rango_hu`: Acrilico 92 a 137, Aire -1046 a -986...) y guarda ese
veredicto en `valores_ct.error_relativo`. Al reabrir, y en el informe PDF firmado, el «Rango HU Ref.» salía de OTRO sitio, el catálogo `materiales_ct` (Acrilico 110 a 140, Aire -1000 a -970...): el
documento podía mostrar un rango y un veredicto que no corresponden entre sí (con el Halcyon de junio: Acrílico, PMP y Aire; 4 contradicciones en 49 filas reales).

GARANTIAS, una por bloque:

  1. ESTRUCTURA -- `valores_ct.rango_referencia_min` y `rango_referencia_max` (REAL, admiten NULL) van en el `CREATE TABLE`; una base ya desplegada las recibe al abrirla (aditiva, idempotente, sin
     relleno retroactivo). Sobre COPIAS de las CINCO BD de referencia la migración añade EXACTAMENTE esas dos columnas, vacías, y nada más cambia (huella de cada una de las demás tablas idéntica a
     la de abrir la misma BD sin el paso, `integrity_check = ok`, `foreign_key_check` en su línea base 109 / 116, y una segunda apertura no cambia nada). Un paso que falla no impide el resto del arranque.
  2. MAPEADOR, ESCRITOR Y LECTOR -- el mapeador lleva el rango que el análisis usó (un par de números; roto o ausente es None, nunca un rango inventado); el escritor lo guarda; el lector entrega
     el GUARDADO y solo si el control no lo guardó (NULL) cae al catálogo, como hasta ahora; con un solo límite guardado usa el par del catálogo entero, nunca uno mezclado; y si el catálogo cambia
     DESPUÉS, lo guardado no se mueve («la copia guardada manda»).
  3. DE PUNTA A PUNTA CON EL ANALISIS REAL (una serie por equipo) -- para cada uno de los siete materiales el rango reabierto es el del análisis y el veredicto guardado es COHERENTE con él (dentro del
     rango si y solo si «Dentro del Rango»); con el catálogo del Halcyon habría tres contradicciones (control de que la prueba discrimina).
  4. LO QUE VE EL FISICO -- la pantalla de lo guardado y el informe PDF REAL imprimen el rango guardado.

Nunca se conecta a una BD de referencia: se copia a un temporal primero.
"""
import copy
import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.catphan_TAC import catphan_db as C
from data.ManejoDatos.conection import Conexion
from test_gi0_estructura_lp_cm_y_error_pct import (  # noqa: F401  (ayudas de GI.0: ensayo sobre copias de las cinco BD)
    CINCO, FK_LINEA_BASE, _abrir_con_la_app, _cols, _copiar, _fk, _huella_filas, _integridad, _tablas, requiere_drop_column)
from test_gi1_guardado_claves_del_analisis import (  # noqa: F401  (helpers y fixtures de GI.1: una sola definicion de la forma del productor)
    _analisis_real, _crear_control, _guardar, _id_prueba, _leer, app, base_real, bd_nueva)
from test_gi2_lectura_es_lo_guardado import _ejecutar, _materiales_ct, _reabrir, bd_copia_real          # noqa: F401
from _informe_imagenes import avisos, generar as _generar_informe, paginas as _paginas_del_informe  # noqa: F401

TABLA = "valores_ct"
COLUMNAS = ("rango_referencia_min", "rango_referencia_max")
CATALOGO = {"Aire": (-1000.0, -970.0), "PMP": (-200.0, -180.0), "LDPE": (-120.0, -90.0), "Poliestireno": (-65.0, -25.0),
            "Acrilico": (110.0, 140.0), "Delrin": (340.0, 380.0), "Teflon": (940.0, 1000.0)}       # lo que siembra `_asegurar_catalogos_base`


def _con_las_columnas_quitadas(ruta):
    """La BD como la tienen las ya desplegadas: la tabla SIN las dos columnas (el estado de las cinco BD de referencia)."""
    con = sqlite3.connect(ruta)
    try:
        for columna in COLUMNAS:
            con.execute(f'ALTER TABLE "{TABLA}" DROP COLUMN {columna}')
        con.commit()
    finally:
        con.close()


def _maestro(ruta):
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

def test_el_create_table_declara_las_dos_columnas_como_real_que_admite_null_sin_depender_de_la_migracion(app, tmp_path, monkeypatch):
    """`ALTER TABLE ... ADD COLUMN` reescribe el texto del esquema: una base nueva se abre con el paso de la migración desactivado y las columnas tienen que estar igual."""
    ruta = str(tmp_path / "nueva_sin_paso.db")
    with monkeypatch.context() as m:
        m.setattr(Conexion, "_asegurar_rango_referencia_valores_ct", lambda self: None)
        m.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        Conexion._instance = None
        Conexion().con.close()
        Conexion._instance = None
    con = sqlite3.connect(ruta)
    try:
        info = {c[1]: c for c in con.execute(f"PRAGMA table_info('{TABLA}')")}
    finally:
        con.close()
    for columna in COLUMNAS:
        assert columna in info, f"el CREATE TABLE no declara {columna}: una instalacion nueva dependeria de la migracion"
        assert info[columna][2].upper() == "REAL" and info[columna][3] == 0, info[columna]          # tipo REAL, notnull = 0
        assert info[columna][4] is None, f"el CREATE TABLE no puede rellenar un rango por omision: {info[columna]}"       # sin DEFAULT: una fila sin rango es NULL (cae al catalogo), igual que en las migradas


@requiere_drop_column
def test_una_bd_ya_desplegada_recibe_las_dos_columnas_al_abrir_y_una_segunda_apertura_no_cambia_nada(bd_nueva, monkeypatch):
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"valores_ct": _materiales_ct(False)}) == sesion
    Conexion._instance.con.close()
    Conexion._instance = None
    _con_las_columnas_quitadas(bd_nueva)
    assert not set(COLUMNAS) & set(_cols(bd_nueva, TABLA))
    _abrir_con_la_app(bd_nueva, monkeypatch)
    assert set(COLUMNAS) <= set(_cols(bd_nueva, TABLA))
    con = sqlite3.connect(bd_nueva)
    try:
        info = {c[1]: c for c in con.execute(f"PRAGMA table_info('{TABLA}')")}
    finally:
        con.close()
    assert [(info[c][2].upper(), info[c][3], info[c][4]) for c in COLUMNAS] == [("REAL", 0, None)] * 2, "la migracion declara REAL, admite NULL y no lleva DEFAULT"
    despues = _huella_sin_la_hora(bd_nueva)
    _abrir_con_la_app(bd_nueva, monkeypatch)                                                # segunda apertura: nada cambia
    assert _huella_sin_la_hora(bd_nueva) == despues
    con = sqlite3.connect(bd_nueva)
    try:
        assert con.execute(f"SELECT COUNT(*) FROM {TABLA} WHERE rango_referencia_min IS NOT NULL OR rango_referencia_max IS NOT NULL").fetchone()[0] == 0
    finally:
        con.close()


@requiere_drop_column
@pytest.mark.parametrize("origen", CINCO, ids=lambda p: p.name)
def test_la_migracion_anade_exactamente_dos_columnas_vacias_y_no_toca_nada_mas(origen, tmp_path, monkeypatch):
    """El diferencial de la tarea sobre COPIAS de las cinco BD de referencia: abrir la copia con la app SIN el paso de GI.8d contra abrirla CON el paso."""
    sin_paso = _copiar(origen, tmp_path, "sin_paso.db")
    con_paso = _copiar(origen, tmp_path, "con_paso.db")
    with monkeypatch.context() as m:
        m.setattr(Conexion, "_asegurar_rango_referencia_valores_ct", lambda self: None)
        _abrir_con_la_app(sin_paso, m)
    assert not set(COLUMNAS) & set(_cols(sin_paso, TABLA)), "las columnas ya estaban en la BD de referencia: el ensayo no mide la migracion"
    _abrir_con_la_app(con_paso, monkeypatch)

    assert _cols(con_paso, TABLA) == _cols(sin_paso, TABLA) + list(COLUMNAS), "la migracion tiene que anadir EXACTAMENTE esas dos columnas, al final"
    a, b = sqlite3.connect(sin_paso), sqlite3.connect(con_paso)
    try:
        assert _tablas(a) == _tablas(b)
        for tabla in _tablas(a):
            if tabla == TABLA:
                viejas = _cols(sin_paso, TABLA)
                assert _huella_filas(a, tabla, viejas) == _huella_filas(b, tabla, viejas), f"{tabla}: cambio una columna que ya existia"
            elif tabla == "audit_log":
                quien = ["id", "usuario", "accion", "tabla"]
                assert _huella_filas(a, tabla, quien) == _huella_filas(b, tabla, quien), f"{tabla}: cambio su contenido"
            else:
                assert _huella_filas(a, tabla) == _huella_filas(b, tabla), f"{tabla}: cambio su contenido"
        n = b.execute(f"SELECT COUNT(*) FROM {TABLA}").fetchone()[0]
        assert n > 0 and b.execute(f"SELECT COUNT(*) FROM {TABLA} WHERE rango_referencia_min IS NULL AND rango_referencia_max IS NULL").fetchone()[0] == n, \
            "las columnas nuevas tienen que quedar vacias en todo lo anterior"
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
    """Un `ALTER TABLE` que falla se avisa y NO corta la cadena (que vive en UN try/except): un paso POSTERIOR (el renombrado de GI.0) se hace igual."""
    ruta = str(tmp_path / "nueva.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    Conexion().con.close()
    Conexion._instance = None
    _con_las_columnas_quitadas(ruta)
    con = sqlite3.connect(ruta)
    con.execute('ALTER TABLE "resolucion_espacial" RENAME COLUMN "lp_cm_maximo" TO "lp_mm_maximo"')
    con.commit()
    con.close()

    original = conection_mod._asegurar_columna

    def falla_solo_para_el_rango(cursor, tabla, columna, ddl):
        if tabla == TABLA and columna in COLUMNAS:
            raise sqlite3.OperationalError("falla de prueba")
        return original(cursor, tabla, columna, ddl)

    monkeypatch.setattr(conection_mod, "_asegurar_columna", falla_solo_para_el_rango)
    _abrir_con_la_app(ruta, monkeypatch)
    assert not set(COLUMNAS) & set(_cols(ruta, TABLA))
    salida = capsys.readouterr().out
    assert all(f"Aviso: no se pudo asegurar 'valores_ct.{c}'" in salida for c in COLUMNAS), "cada columna tiene su propio intento y su propio aviso"
    assert "lp_cm_maximo" in _cols(ruta, "resolucion_espacial"), "el paso posterior (renombrado de GI.0) no se hizo: el fallo corto el arranque"


def test_una_sola_columna_fallida_no_impide_la_otra(tmp_path, monkeypatch):
    """Cada columna tiene SU intento: si falla la primera, la segunda se intenta igual (el lector las exige juntas, pero un fallo no debe esconder al otro)."""
    ruta = str(tmp_path / "una.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    Conexion().con.close()
    Conexion._instance = None
    if sqlite3.sqlite_version_info < (3, 35, 0):
        pytest.skip("SQLite < 3.35: sin DROP COLUMN")
    _con_las_columnas_quitadas(ruta)
    original = conection_mod._asegurar_columna

    def falla_la_primera(cursor, tabla, columna, ddl):
        if tabla == TABLA and columna == "rango_referencia_min":
            raise sqlite3.OperationalError("falla de prueba")
        return original(cursor, tabla, columna, ddl)

    monkeypatch.setattr(conection_mod, "_asegurar_columna", falla_la_primera)
    _abrir_con_la_app(ruta, monkeypatch)
    assert "rango_referencia_max" in _cols(ruta, TABLA) and "rango_referencia_min" not in _cols(ruta, TABLA)


def test_la_herramienta_de_migracion_deja_las_dos_columnas(tmp_path):
    """`scripts/migrar_bd_a_estandar.py` crea `Conexion()`: usa el mismo paso. Sobre una copia de la BD del 21-09."""
    import contextlib
    import io
    from _bd_referencia import BD_REBUILD_21_09
    from scripts.migrar_bd_a_estandar import migrar
    ruta = _copiar(BD_REBUILD_21_09, tmp_path, "migrar.db")
    assert not set(COLUMNAS) & set(_cols(ruta, TABLA))
    with contextlib.redirect_stdout(io.StringIO()):
        migrar(ruta, aplicar=True)
    assert set(COLUMNAS) <= set(_cols(ruta, TABLA))
    Conexion._instance = None


# ---------------------------------------------------------------------------
# 2. MAPEADOR, ESCRITOR Y LECTOR
# ---------------------------------------------------------------------------

def _resultados_ct(rangos):
    """La forma de `valor_numero_ct`: un diccionario por material con `rango_hu` (un par) y el veredicto contra ESE rango."""
    filas = []
    for nombre, (promedio, rango) in rangos.items():
        dentro = rango is not None and rango[0] <= promedio <= rango[1]
        filas.append({"centro": (100, 100), "material": nombre, "promedio_hu": promedio, "std_hu": 5.0, "rango_hu": rango,
                      "error_abs": 0.0 if dentro else 1.5, "error_rel": "Dentro del Rango" if dentro else "Fuera de Rango"})
    return filas


# Rangos DISTINTOS de los del catalogo en cada material, y un promedio dentro del suyo pero fuera del catalogo (o al reves): un cruce se nota
RANGOS_DEL_ANALISIS = {"Aire": (-1046, -986), "PMP": (-220, -172), "LDPE": (-121, -87), "Poliestireno": (-65, -29), "Acrilico": (92, 137), "Delrin": (344, 387), "Teflon": (941, 1060)}
PROMEDIOS = {"Aire": -981.8, "PMP": -201.5, "LDPE": -111.4, "Poliestireno": -62.3, "Acrilico": 96.0, "Delrin": 313.2, "Teflon": 886.7}


def _con_rangos_del_analisis():
    return _resultados_ct({m: (PROMEDIOS[m], RANGOS_DEL_ANALISIS[m]) for m in ORDEN_MATERIALES_ANALISIS})


ORDEN_MATERIALES_ANALISIS = ("Aire", "PMP", "LDPE", "Poliestireno", "Acrilico", "Delrin", "Teflon")


def test_el_mapeador_lleva_el_rango_que_uso_el_analisis():
    mapeados = {m["material"]: m for m in C.mapear_valores_ct(_con_rangos_del_analisis())}
    for material, (minimo, maximo) in RANGOS_DEL_ANALISIS.items():
        nombre = "Polystyrene" if material == "Poliestireno" else material                                  # el mapeador normaliza el nombre del poliestireno
        assert (mapeados[nombre]["rango_referencia_min"], mapeados[nombre]["rango_referencia_max"]) == (float(minimo), float(maximo))
        assert isinstance(mapeados[nombre]["rango_referencia_min"], float) and isinstance(mapeados[nombre]["rango_referencia_max"], float)


@pytest.mark.parametrize("rango", [None, (1,), (1, 2, 3), "texto", ("a", "b"), (float("nan"), 5.0), (1.0, float("inf")), (1.0, None), ()],
                         ids=["none", "un_elemento", "tres", "texto", "par_de_textos", "nan", "infinito", "con_none", "vacio"])
def test_un_rango_ausente_o_roto_queda_en_none_y_nunca_se_inventa(rango):
    fila = _resultados_ct({"Aire": (-990.0, (-1046, -986))})[0]
    fila["rango_hu"] = rango
    mapeado = C.mapear_valores_ct([fila])[0]
    assert (mapeado["rango_referencia_min"], mapeado["rango_referencia_max"]) == (None, None)


def test_un_resultado_sin_la_clave_rango_hu_queda_en_none():
    fila = _resultados_ct({"Aire": (-990.0, (-1046, -986))})[0]
    fila.pop("rango_hu")
    mapeado = C.mapear_valores_ct([fila])[0]
    assert (mapeado["rango_referencia_min"], mapeado["rango_referencia_max"]) == (None, None)


@pytest.mark.parametrize("rango", [(0, 50), (-65, 0), (0, 0), (91.5, 137.25), (-1045.5, -985.75)], ids=["min_cero", "max_cero", "ambos_cero", "decimales", "decimales_negativos"])
def test_un_limite_en_cero_o_con_decimales_se_guarda_y_se_lee_tal_cual(bd_nueva, rango):
    """0 es un numero valido (no «vacio»: un `if limite:` lo descartaria) y los limites no se redondean: el mapeador, el escritor y el lector los conservan."""
    resultados = _con_rangos_del_analisis()
    resultados[0]["rango_hu"] = rango                                               # el Aire
    mapeado = next(m for m in C.mapear_valores_ct(resultados) if m["material"] == "Aire")
    assert (mapeado["rango_referencia_min"], mapeado["rango_referencia_max"]) == (float(rango[0]), float(rango[1]))
    sesion = _crear_control(bd_nueva)
    assert _guardar(sesion, {"valores_ct": resultados}) == sesion
    assert _rangos_reabiertos(bd_nueva, sesion)["Aire"] == (float(rango[0]), float(rango[1]))


def _guardar_y_reabrir(ruta):
    sesion = _crear_control(ruta)
    assert _guardar(sesion, {"valores_ct": _con_rangos_del_analisis()}) == sesion
    return sesion


def _rangos_reabiertos(ruta, sesion):
    return {f["material"]: tuple(f["rango_hu"]) for f in _reabrir(ruta, "valores_ct", sesion) if "material" in f}


def test_el_escritor_guarda_el_rango_de_cada_material_en_su_fila(bd_nueva):
    sesion = _guardar_y_reabrir(bd_nueva)
    con = _leer(bd_nueva)
    try:
        filas = con.execute("SELECT m.nombre_material, vc.rango_referencia_min, vc.rango_referencia_max FROM valores_ct vc JOIN materiales_ct m ON m.id_material = vc.id_material "
                            "WHERE vc.id_prueba = ?", (_id_prueba(con, sesion, "valores_ct"),)).fetchall()
        assert {f["nombre_material"]: (f["rango_referencia_min"], f["rango_referencia_max"]) for f in filas} == {m: (float(a), float(b)) for m, (a, b) in RANGOS_DEL_ANALISIS.items()}
    finally:
        con.close()


def test_el_lector_devuelve_el_rango_guardado_y_no_el_del_catalogo(bd_nueva):
    sesion = _guardar_y_reabrir(bd_nueva)
    reabiertos = _rangos_reabiertos(bd_nueva, sesion)
    assert reabiertos == {m: (float(a), float(b)) for m, (a, b) in RANGOS_DEL_ANALISIS.items()}
    assert all(reabiertos[m] != CATALOGO[m] for m in CATALOGO), "el ensayo no discrimina: algun rango del analisis coincide con el del catalogo"


def test_si_el_catalogo_cambia_despues_lo_guardado_no_se_mueve(bd_nueva):
    """«La copia guardada manda»: reescribir el catalogo no cambia el rango de un control ya guardado."""
    sesion = _guardar_y_reabrir(bd_nueva)
    _ejecutar(bd_nueva, "UPDATE materiales_ct SET rango_referencia_min = rango_referencia_min - 500, rango_referencia_max = rango_referencia_max + 500")
    assert _rangos_reabiertos(bd_nueva, sesion) == {m: (float(a), float(b)) for m, (a, b) in RANGOS_DEL_ANALISIS.items()}


def test_un_control_anterior_sin_rango_guardado_sigue_mostrando_el_del_catalogo(bd_nueva):
    sesion = _guardar_y_reabrir(bd_nueva)
    _ejecutar(bd_nueva, "UPDATE valores_ct SET rango_referencia_min = NULL, rango_referencia_max = NULL")          # como quedaron todos los controles anteriores a GI.8d
    assert _rangos_reabiertos(bd_nueva, sesion) == CATALOGO
    _ejecutar(bd_nueva, "UPDATE materiales_ct SET rango_referencia_min = 1.5, rango_referencia_max = 2.5 WHERE nombre_material = 'Aire'")
    assert _rangos_reabiertos(bd_nueva, sesion)["Aire"] == (1.5, 2.5), "sin rango guardado manda el catalogo de hoy, exactamente como antes de la tarea"


@pytest.mark.parametrize("columna_vacia", ["rango_referencia_min", "rango_referencia_max"])
def test_con_un_solo_limite_guardado_se_usa_el_par_del_catalogo_entero(bd_nueva, columna_vacia):
    sesion = _guardar_y_reabrir(bd_nueva)
    _ejecutar(bd_nueva, f"UPDATE valores_ct SET {columna_vacia} = NULL")
    assert _rangos_reabiertos(bd_nueva, sesion) == CATALOGO, "nunca un rango mezclado (un limite del analisis y otro del catalogo)"


@pytest.mark.parametrize("columna", COLUMNAS)
@pytest.mark.parametrize("valor", ["texto", b"\x01", float("inf"), float("-inf")], ids=["texto", "blob", "mas_infinito", "menos_infinito"])
def test_un_limite_guardado_que_no_es_un_numero_finito_cae_al_catalogo(bd_nueva, valor, columna):
    """Los dos limites, cada uno: el rango guardado solo vale si LOS DOS son numeros finitos."""
    sesion = _guardar_y_reabrir(bd_nueva)
    _ejecutar(bd_nueva, f"UPDATE valores_ct SET {columna} = ?", (valor,))
    assert _rangos_reabiertos(bd_nueva, sesion) == CATALOGO


# ---------------------------------------------------------------------------
# 3. DE PUNTA A PUNTA CON EL ANALISIS REAL
# ---------------------------------------------------------------------------

def _coherente(promedio, rango, veredicto):
    return (rango[0] <= promedio <= rango[1]) == (veredicto == "Dentro del Rango")


def test_real_cada_material_reabre_con_el_rango_del_analisis(base_real):
    analisis = {r["material"]: r for r in base_real.salidas["valores_ct"] if "material" in r}
    reabiertos = {f["material"]: f for f in _reabrir(base_real.ruta, "valores_ct", base_real.sesion) if "material" in f}
    assert len(reabiertos) == 7
    for material, fila in reabiertos.items():
        esperado = analisis[material]["rango_hu"]
        assert tuple(fila["rango_hu"]) == (float(esperado[0]), float(esperado[1])), material


def test_real_el_veredicto_guardado_es_coherente_con_el_rango_que_se_muestra(base_real):
    for fila in (f for f in _reabrir(base_real.ruta, "valores_ct", base_real.sesion) if "material" in f):
        assert _coherente(fila["promedio_hu"], fila["rango_hu"], fila["error_rel"]), (base_real.clave, fila["material"], fila["promedio_hu"], fila["rango_hu"], fila["error_rel"])


def test_real_con_el_catalogo_el_halcyon_tendria_contradicciones_control_de_que_la_prueba_discrimina():
    """Control de que las pruebas de arriba discriminan: con el rango del CATALOGO el Halcyon de junio muestra filas incoherentes (un veredicto que no corresponde al rango impreso).
    Va con la serie del Halcyon directamente (no parametrizada: un `skip` para las otras dos series movia el conteo de omitidas de la suite)."""
    equipo, px, nominal, salidas = _analisis_real("HALCYON_JUN")
    contradicciones = [r["material"] for r in salidas["valores_ct"] if "material" in r and not _coherente(r["promedio_hu"], CATALOGO[r["material"]], r["error_rel"])]
    assert len(contradicciones) >= 1, "el catalogo no contradice ningun veredicto de esta serie: la prueba anterior no discriminaria"
    assert set(contradicciones) == {"Acrilico", "PMP", "Aire"}, contradicciones          # exactamente las tres filas que midio la tarea


# ---------------------------------------------------------------------------
# 5. UN RESULTADO REABIERTO NO SELLA EL RANGO DEL CATALOGO COMO SI FUERA DEL ANALISIS (hallazgo de la revision)
# ---------------------------------------------------------------------------
# La pantalla de Linealidad carga los Valores CT guardados (`cargar_valores_ct_desde_bd` -> `reconstruir_valores_ct`) y «Guardar todos» los vuelve a mandar al escritor. De un control
# anterior a GI.8d el lector entrega el rango del CATALOGO (no guardo el suyo); si el mapeador lo tomara, la fila nueva quedaria con ese rango sellado como «el contra el que se juzgo» junto a
# un veredicto que el analisis decidio con otro: justo la contradiccion que la tarea elimina, ahora escrita en la base.

def _volver_a_guardar_lo_reabierto(ruta, sesion):
    reabierto = [f for f in _reabrir(ruta, "valores_ct", sesion) if "material" in f]
    nueva = _crear_control(ruta, "Tomógrafo", "07/2026")
    assert _guardar(nueva, {"valores_ct": reabierto}) == nueva
    con = _leer(ruta)
    try:
        filas = con.execute("SELECT m.nombre_material, vc.rango_referencia_min, vc.rango_referencia_max, vc.error_relativo FROM valores_ct vc JOIN materiales_ct m ON m.id_material = vc.id_material "
                            "WHERE vc.id_prueba = ?", (_id_prueba(con, nueva, "valores_ct"),)).fetchall()
        return {f["nombre_material"]: (f["rango_referencia_min"], f["rango_referencia_max"], f["error_relativo"]) for f in filas}
    finally:
        con.close()


def test_el_lector_dice_de_donde_sale_el_rango_de_cada_material(bd_nueva):
    sesion = _guardar_y_reabrir(bd_nueva)
    guardados = [f for f in _reabrir(bd_nueva, "valores_ct", sesion) if "material" in f]
    assert len(guardados) == 7 and [f["rango_hu_de_catalogo"] for f in guardados] == [False] * 7
    _ejecutar(bd_nueva, "UPDATE valores_ct SET rango_referencia_min = NULL, rango_referencia_max = NULL")
    assert [f["rango_hu_de_catalogo"] for f in _reabrir(bd_nueva, "valores_ct", sesion) if "material" in f] == [True] * 7
    _ejecutar(bd_nueva, "UPDATE valores_ct SET rango_referencia_min = -1.0, rango_referencia_max = 1.0 WHERE id_material = 1")      # un solo material con rango guardado
    marcas = {f["material"]: f["rango_hu_de_catalogo"] for f in _reabrir(bd_nueva, "valores_ct", sesion) if "material" in f}
    assert sorted(marcas.values()) == [False] + [True] * 6


def test_volver_a_guardar_lo_reabierto_de_un_control_anterior_no_sella_el_rango_del_catalogo(bd_nueva):
    sesion = _guardar_y_reabrir(bd_nueva)
    _ejecutar(bd_nueva, "UPDATE valores_ct SET rango_referencia_min = NULL, rango_referencia_max = NULL")          # como quedaron todos los controles anteriores a GI.8d
    nuevas = _volver_a_guardar_lo_reabierto(bd_nueva, sesion)
    assert len(nuevas) == 7
    assert all(f[0] is None and f[1] is None for f in nuevas.values()), f"el rango del catalogo quedo sellado como el del analisis: {nuevas}"
    assert {m: f[2] for m, f in nuevas.items()}["Acrilico"] == "Dentro del Rango"                           # y el veredicto del analisis se conserva


def test_volver_a_guardar_lo_reabierto_con_rango_guardado_lo_conserva(bd_nueva):
    sesion = _guardar_y_reabrir(bd_nueva)
    nuevas = _volver_a_guardar_lo_reabierto(bd_nueva, sesion)
    assert {m: (f[0], f[1]) for m, f in nuevas.items()} == {m: (float(a), float(b)) for m, (a, b) in RANGOS_DEL_ANALISIS.items()}


def test_un_resultado_con_la_marca_del_catalogo_no_aporta_su_rango_al_mapeador():
    fila = _resultados_ct({"Aire": (-990.0, (-1000.0, -970.0))})[0]
    fila["rango_hu_de_catalogo"] = True
    mapeado = C.mapear_valores_ct([fila])[0]
    assert (mapeado["rango_referencia_min"], mapeado["rango_referencia_max"]) == (None, None)
    fila["rango_hu_de_catalogo"] = False
    mapeado = C.mapear_valores_ct([fila])[0]
    assert (mapeado["rango_referencia_min"], mapeado["rango_referencia_max"]) == (-1000.0, -970.0)


# ---------------------------------------------------------------------------
# 4. LO QUE VE EL FISICO
# ---------------------------------------------------------------------------

def test_la_pantalla_de_lo_guardado_dice_el_rango_guardado(bd_nueva, app):
    from PyQt5.QtWidgets import QTableWidget
    sesion = _guardar_y_reabrir(bd_nueva)
    widget = C.tabla_resultados_ct(_reabrir(bd_nueva, "valores_ct", sesion))
    try:
        tabla = widget if isinstance(widget, QTableWidget) else widget.findChild(QTableWidget)
        filas = {tabla.item(f, 0).text(): tabla.item(f, 2).text() for f in range(tabla.rowCount())}
    finally:
        widget.deleteLater()
    assert filas["Acrílico"] == "92.0 a 137.0" and filas["Aire"] == "-1046.0 a -986.0", filas


def test_el_pdf_real_imprime_el_rango_guardado(bd_copia_real, monkeypatch, avisos):
    """La sesion 42 (tomografo, las siete categorias) con un rango guardado DISTINTO al del catalogo en el Aire: el informe lo imprime una vez y ademas nada cambia; sin rango guardado sale el del catalogo."""
    con = sqlite3.connect(bd_copia_real)
    try:
        id_prueba = con.execute("SELECT id_prueba FROM pruebas WHERE id_sesion = 42 AND id_tipo = 5 AND (activo IS NULL OR activo = 1)").fetchone()[0]
        cat = {r[0]: (r[1], r[2]) for r in con.execute("SELECT nombre_material, rango_referencia_min, rango_referencia_max FROM materiales_ct")}
        equipo, fecha = con.execute("SELECT equipo, fecha FROM controles WHERE id = 42").fetchone()
    finally:
        con.close()
    ok, recibido = _generar_informe(bd_copia_real, monkeypatch, 42, equipo, fecha)
    assert ok and not avisos, avisos
    antes = " ".join("\n".join(_paginas_del_informe(recibido["pdf"])).split())
    assert "123.4 a 567.8" not in antes
    _ejecutar(bd_copia_real, "UPDATE valores_ct SET rango_referencia_min = 123.4, rango_referencia_max = 567.8 "
                             "WHERE id_prueba = ? AND id_material = (SELECT id_material FROM materiales_ct WHERE nombre_material = 'Aire')", (id_prueba,))
    ok, recibido = _generar_informe(bd_copia_real, monkeypatch, 42, equipo, fecha)
    assert ok and not avisos, avisos
    despues = " ".join("\n".join(_paginas_del_informe(recibido["pdf"])).split())
    assert despues.count("123.4 a 567.8") == 1, "el informe tiene que imprimir el rango guardado del Aire, una vez"
    lo_demas_antes, lo_demas_despues = antes.replace(f"{cat['Aire'][0]:.1f} a {cat['Aire'][1]:.1f}", ""), despues.replace("123.4 a 567.8", "")
    assert lo_demas_antes == lo_demas_despues, "ademas del rango del Aire, nada del informe cambia"
