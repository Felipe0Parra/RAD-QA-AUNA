"""GI.0b (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md): el observador de contrato aprende los renombrados de columna
declarados en `RENOMBRES_DE_COLUMNAS` (conection.py, GI.0) y sigue dando luz verde o roja por lo que de verdad pasa.

Por que: GI.0 renombra EN SITIO dos columnas (`resolucion_espacial.lp_mm_maximo` -> `lp_cm_maximo` y
`resolucion_espacial_regiones.lp_mm` -> `lp_cm`) sin tocar un valor. Medido el 06-10 sobre una copia de `Rebuild_21-09`
(`logs/GI0/observador_dp86.log`): el observador de HEAD reporta 2 fallos `[esquema] <tabla>.<columna> desaparecio` que
`--esperado` no puede declarar, y 80 bloques `[vigente] cambia` porque la huella de cada fila lleva el NOMBRE de la columna.
El paso 3b de la puerta de salida ("el cambio de esquema sale declarado, ningun valor cambia") no podia dar luz verde, y
declarar los 80 bloques con la receta de DP-86 habria dejado sin vigilar un valor alterado dentro de ellos.

Lo que fija esta prueba:
  1. la fuente de los renombrados es la MISMA que usa la app (`RENOMBRES_DE_COLUMNAS`, leida por AST como `TABLAS_ANULABLES`);
  2. una base con los nombres viejos y la misma base abierta con la app (renombrada) comparan con 0 fallos y exactamente 2
     lineas informativas de renombrado: en una base nueva sembrada con el escritor real y en las 5 BD de referencia (sobre copia);
  3. la huella de cada bloque es la misma bajo el nombre viejo y el nuevo (tambien con otra capitalizacion, como compara SQLite);
  4. lo que el renombrado NO debe tapar sigue siendo fallo: un valor alterado en una tabla renombrada (sin declarar nada), una
     columna que desaparece de verdad, un renombrado declarado para OTRA tabla, una "columna nueva" que ya existia antes (una baja
     disfrazada de renombrado) y dos instantaneas tomadas por versiones distintas del observador;
  5. el lector de `RENOMBRES_DE_COLUMNAS` falla ruidosamente si el literal cambia de forma o desaparece.
"""
import json
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import RENOMBRES_DE_COLUMNAS, Conexion
import scripts.observador_contrato as obs
from _bd_referencia import BD_A_AJUSTAR, BD_QA, BD_REBUILD_14_09, BD_REBUILD_21_09, CARPETA_BD

RAIZ = pathlib.Path(__file__).resolve().parent.parent
BD_PRIMITIVA = CARPETA_BD / "BaseDatosQA(Primitiva-01).db"
CINCO = [BD_QA, BD_REBUILD_14_09, BD_A_AJUSTAR, BD_PRIMITIVA, BD_REBUILD_21_09]

TABLA_ESP, TABLA_REG = "resolucion_espacial", "resolucion_espacial_regiones"
RENOMBRADAS = {TABLA_ESP: ("lp_mm_maximo", "lp_cm_maximo"), TABLA_REG: ("lp_mm", "lp_cm")}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# ayudas
# ---------------------------------------------------------------------------

def _requerir(origen):
    if not origen.exists():
        pytest.skip(f"BD de referencia ausente: {origen}")


def _copiar(origen, tmp_path, nombre="copia.db"):
    _requerir(origen)
    ruta = str(tmp_path / nombre)
    shutil.copy(origen, ruta)
    return ruta


def _abrir_con_la_app(ruta, monkeypatch):
    """Abre la base con `Conexion()` (DDL + todas las migraciones reales, GI.0 incluida) y la cierra."""
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    con = Conexion()
    con.con.close()
    Conexion._instance = None


def _renombrar(ruta, cambios):
    """`cambios` = [(tabla, de, a), ...]: ALTER TABLE ... RENAME COLUMN, como lo haria una base ya desplegada."""
    con = sqlite3.connect(ruta)
    try:
        for tabla, de, a in cambios:
            con.execute(f'ALTER TABLE "{tabla}" RENAME COLUMN "{de}" TO "{a}"')
        con.commit()
    finally:
        con.close()


def _a_nombres_viejos(ruta):
    """Devuelve las dos columnas a como las tienen las bases ya desplegadas (y las 27 de BasesDeDatos/)."""
    _renombrar(ruta, [(t, nueva, vieja) for t, (vieja, nueva) in RENOMBRADAS.items()])


def _cols(ruta, tabla):
    con = sqlite3.connect(ruta)
    try:
        return [f[1] for f in con.execute(f"PRAGMA table_info('{tabla}')")]
    finally:
        con.close()


def _crear_control(ruta, equipo="Tomógrafo", fecha="06/2026"):
    con = sqlite3.connect(ruta)
    con.execute("INSERT INTO controles (equipo, control, fecha) VALUES (?, 'Mensual', ?)", (equipo, fecha))
    con.commit()
    ref = con.execute("SELECT id FROM controles ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.close()
    return ref


def _guardar(sesion, categorias, **kw):
    from data.ManejoDatos.catphan_TAC.catphan_db import guardar_prueba_completa_catphan
    base = dict(user_id="fisico1", fecha="2026-06-01", equipo="Tomógrafo", kv=120, ma=200, espesor_corte=2.0,
                resultados_por_categoria=categorias, id_sesion=sesion, tam_px_teorico=1.074)
    base.update(kw)
    return guardar_prueba_completa_catphan(**base)


# Forma del resultado real de `Analisis_Catphan_TAC.resolucion_espacial` con las claves de GI.0 (la misma de test_gi0): seis
# regiones con todos los numeros distintos, `'lp/cm'` y `'lp/mm'` con el mismo valor para no depender de cual lea el mapeador (hasta GI.1 leia `'lp/mm'`; desde GI.1, `'lp/cm'`).
RESULTADO_ESPACIAL = {
    "region_results": {
        f"region {n}": {"lp/cm": 2.0 * n, "lp/mm": 2.0 * n, "peak_mean": 100.0 + n, "valley_mean": 50.0 + n,
                        "gap_size_cm": round(0.5 / n, 3), "n_peaks_used": 3 + n, "n_valleys_used": 2 + n,
                        "status": "OK" if n <= 5 else "Picos insuficientes"}
        for n in range(1, 7)
    },
    "mtf_lp_cm": {"10": 5.2, "20": 4.1, "50": 3.1},
    "num_picos": 12,
    "resolucion_limite": {"ultima_region": "region 5", "lp_cm_maximo": 10.0, "gap_size_cm": 0.1},
    "imagen_analisis": None,
}


@pytest.fixture
def bd_sembrada(app, monkeypatch, tmp_path):
    """Base NUEVA (nombres en lp/cm) con una sesion de Catphan guardada por el escritor real: 1 fila en `resolucion_espacial`,
    6 en `resolucion_espacial_regiones` y 1 en `tamaño_pixel`."""
    ruta = str(tmp_path / "nueva.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    sesion = _crear_control(ruta)
    assert _guardar(sesion, {"resolucion_espacial": RESULTADO_ESPACIAL, "tamano_pixel": {"X": 1.08, "Y": 1.06}}) is not None
    conexion.con.close()
    Conexion._instance = None
    con = sqlite3.connect(ruta)
    try:
        assert con.execute(f'SELECT COUNT(*) FROM "{TABLA_REG}"').fetchone()[0] == 6
        assert con.execute(f'SELECT COUNT(*) FROM "{TABLA_ESP}"').fetchone()[0] == 1
    finally:
        con.close()
    yield ruta
    Conexion._instance = None


def _antes_y_despues(ruta, monkeypatch):
    """La foto de una base con los nombres VIEJOS y la foto de la misma base tras abrirla con la app (renombrada)."""
    _a_nombres_viejos(ruta)
    assert "lp_mm_maximo" in _cols(ruta, TABLA_ESP) and "lp_mm" in _cols(ruta, TABLA_REG)
    antes = obs.capturar(ruta)
    _abrir_con_la_app(ruta, monkeypatch)
    assert "lp_cm_maximo" in _cols(ruta, TABLA_ESP) and "lp_cm" in _cols(ruta, TABLA_REG)
    despues = obs.capturar(ruta)
    return antes, despues


def _lineas_de_renombrado(info):
    return [linea for linea in info if "renombrada" in linea]


def _afirmar_solo_los_dos_renombrados(fallos, info):
    assert fallos == [], fallos
    renombradas = _lineas_de_renombrado(info)
    assert len(renombradas) == 2, info
    for tabla, (vieja, nueva) in RENOMBRADAS.items():
        assert any(f"{tabla}.{vieja} -> {nueva}" in linea for linea in renombradas), (tabla, info)
    assert not any("columna nueva" in linea for linea in info), \
        "el destino del renombrado no se anuncia ademas como 'columna nueva': " + repr(info)
    assert not any("desapareci" in linea for linea in info), info
    assert len(info) == 2, "nada mas que los dos renombrados: " + repr(info)


# ---------------------------------------------------------------------------
# 1. la fuente de los renombrados es la de la app
# ---------------------------------------------------------------------------

def test_los_renombrados_que_conoce_el_observador_son_los_que_declara_conection():
    declarados = obs._renombres_declarados()
    assert declarados == tuple(tuple(r) for r in RENOMBRES_DE_COLUMNAS)
    assert (TABLA_ESP, "lp_mm_maximo", "lp_cm_maximo") in declarados
    assert (TABLA_REG, "lp_mm", "lp_cm") in declarados


def test_el_lector_de_renombres_falla_ruidosamente_si_el_literal_cambia_de_forma_o_desaparece(tmp_path, monkeypatch):
    falso = tmp_path / "conection_falsa.py"
    monkeypatch.setattr(obs, "CONEXION_PATH", falso)

    falso.write_text("X = 1\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="RENOMBRES_DE_COLUMNAS"):
        obs._renombres_declarados()

    falso.write_text("RENOMBRES_DE_COLUMNAS = tuple(x for x in [])\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="RENOMBRES_DE_COLUMNAS"):
        obs._renombres_declarados()

    falso.write_text('RENOMBRES_DE_COLUMNAS = (("t", "a", "b"), ("t", "c"),)\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="RENOMBRES_DE_COLUMNAS"):
        obs._renombres_declarados()

    falso.write_text('RENOMBRES_DE_COLUMNAS = (\n    ("t", "a", "b"),\n)\n', encoding="utf-8")
    assert obs._renombres_declarados() == (("t", "a", "b"),)


# ---------------------------------------------------------------------------
# 2. la base con los nombres viejos y la misma base renombrada por la app comparan sin fallos
# ---------------------------------------------------------------------------

def test_la_base_con_nombres_viejos_y_la_misma_abierta_con_la_app_comparan_sin_fallos(bd_sembrada, monkeypatch):
    """La titular: contra HEAD caen 2 fallos `desaparecio` (que nada declara) y 7 `[vigente] cambia`."""
    antes, despues = _antes_y_despues(bd_sembrada, monkeypatch)
    assert "lp_mm_maximo" in antes["esquema"][TABLA_ESP], "la foto de antes dice la verdad del esquema"
    assert "lp_cm_maximo" in despues["esquema"][TABLA_ESP]
    fallos, info = obs.comparar(antes, despues)
    _afirmar_solo_los_dos_renombrados(fallos, info)


def test_la_huella_de_cada_bloque_es_la_misma_bajo_el_nombre_viejo_y_el_nuevo(bd_sembrada, monkeypatch):
    antes, despues = _antes_y_despues(bd_sembrada, monkeypatch)
    for tabla in (TABLA_ESP, TABLA_REG):
        assert antes["vigente"][tabla], tabla
        assert antes["vigente"][tabla] == despues["vigente"][tabla], tabla
    assert antes["censo"] == despues["censo"]
    assert antes["vigente"] == despues["vigente"]


def test_la_foto_dice_que_columnas_hasheo_bajo_otro_nombre(bd_sembrada, monkeypatch):
    antes, despues = _antes_y_despues(bd_sembrada, monkeypatch)
    aplicados = {tuple(x) for x in antes["renombres_aplicados"]}
    assert aplicados == {(t, vieja, nueva) for t, (vieja, nueva) in RENOMBRADAS.items()}
    assert despues["renombres_aplicados"] == [], "con los nombres nuevos no hay nada que traducir"
    assert antes["observador"] == despues["observador"]
    assert antes["observador"]["renombres_declarados"] == [list(r) for r in RENOMBRES_DE_COLUMNAS]


def test_con_otra_capitalizacion_tambien_se_reconoce_como_sqlite(bd_sembrada, monkeypatch):
    """SQLite no distingue mayusculas en los nombres de columna; GI.0 (A-H1) renombra `LP_MM_MAXIMO` igual que `lp_mm_maximo`."""
    _renombrar(bd_sembrada, [(TABLA_ESP, "lp_cm_maximo", "LP_MM_MAXIMO"), (TABLA_REG, "lp_cm", "LP_MM")])
    antes = obs.capturar(bd_sembrada)
    assert "LP_MM_MAXIMO" in antes["esquema"][TABLA_ESP]
    _abrir_con_la_app(bd_sembrada, monkeypatch)
    despues = obs.capturar(bd_sembrada)
    assert "lp_cm_maximo" in despues["esquema"][TABLA_ESP] and "lp_cm" in despues["esquema"][TABLA_REG]
    fallos, info = obs.comparar(antes, despues)
    assert fallos == [], fallos
    assert len(_lineas_de_renombrado(info)) == 2, info
    assert antes["vigente"] == despues["vigente"]


def test_sin_los_renombrados_declarados_vuelven_los_fallos_de_dp86(bd_sembrada, monkeypatch):
    """Control: lo que explica la luz verde es la declaracion, no otra cosa. Con la lista de renombrados vacia (al capturar y al
    comparar) el observador es el de HEAD: los 2 `desaparecio` y 7 `cambia` (1 bloque de `resolucion_espacial`, por id_prueba, y
    6 de regiones, donde cada fila es su propio bloque porque la tabla tiene `id`)."""
    monkeypatch.setattr(obs, "_renombres_declarados", lambda: ())
    antes, despues = _antes_y_despues(bd_sembrada, monkeypatch)
    assert antes["renombres_aplicados"] == [] and antes["observador"]["renombres_declarados"] == []
    fallos, _info = obs.comparar(antes, despues)
    desaparecidas = [f for f in fallos if "desapareci" in f]
    assert len(desaparecidas) == 2, fallos
    assert any(f"{TABLA_ESP}.lp_mm_maximo" in f for f in desaparecidas)
    assert any(f"{TABLA_REG}.lp_mm" in f for f in desaparecidas)
    cambian = [f for f in fallos if "[vigente]" in f and "cambia" in f]
    assert len(cambian) == 7, fallos
    assert sum(f"[vigente] {TABLA_ESP} " in f for f in cambian) == 1
    assert sum(f"[vigente] {TABLA_REG} " in f for f in cambian) == 6
    assert len(fallos) == 9, fallos


@pytest.mark.parametrize("origen", CINCO, ids=[b.name for b in CINCO])
def test_las_cinco_bd_de_referencia_comparan_sin_fallos_a_traves_del_renombrado(origen, tmp_path, monkeypatch):
    """La medicion de DP-86 del 06-10, ahora en verde: copia, abierta con la app para que existan todas las tablas del contrato,
    devuelta a los nombres viejos (como la tiene producion), foto, abierta con la app (renombra), foto, comparar."""
    ruta = _copiar(origen, tmp_path)
    _abrir_con_la_app(ruta, monkeypatch)
    antes, despues = _antes_y_despues(ruta, monkeypatch)
    fallos, info = obs.comparar(antes, despues)
    _afirmar_solo_los_dos_renombrados(fallos, info)
    assert antes["censo"] == despues["censo"]
    assert antes["vigente"] == despues["vigente"]
    assert antes["integridad"] == despues["integridad"]


# ---------------------------------------------------------------------------
# 3. lo que el renombrado NO debe tapar
# ---------------------------------------------------------------------------

def test_un_valor_alterado_en_una_tabla_renombrada_sigue_siendo_fallo_sin_declarar_nada(bd_sembrada, monkeypatch):
    """La ventaja sobre declarar los bloques con la receta de DP-86: con la receta, un valor alterado dentro de un bloque
    declarado quedaba silenciado (medido en DP-86). Aqui no hay nada declarado y el valor alterado se ve, y solo el."""
    _a_nombres_viejos(bd_sembrada)
    antes = obs.capturar(bd_sembrada)
    _abrir_con_la_app(bd_sembrada, monkeypatch)
    con = sqlite3.connect(bd_sembrada)
    try:
        # en esta tabla cada fila es su propio bloque (tiene `id`): el observador nombra la fila alterada por su `id`
        id_fila = con.execute(f'SELECT id FROM "{TABLA_REG}" WHERE region_nombre = ?', ("region 3",)).fetchone()[0]
        con.execute(f'UPDATE "{TABLA_REG}" SET lp_cm = lp_cm + 1 WHERE region_nombre = ?', ("region 3",))
        con.commit()
    finally:
        con.close()
    despues = obs.capturar(bd_sembrada)
    fallos, info = obs.comparar(antes, despues)
    assert fallos == [f"[vigente] {TABLA_REG} ref={id_fila}: cambia (NO declarado)"], fallos
    assert len(_lineas_de_renombrado(info)) == 2, info


def test_una_columna_que_desaparece_de_verdad_sigue_siendo_fallo(bd_sembrada, monkeypatch):
    _antes_y_despues(bd_sembrada, monkeypatch)
    despues = obs.capturar(bd_sembrada)
    mutilada = json.loads(json.dumps(despues))
    mutilada["esquema"][TABLA_ESP].remove("mtf_10_pct")
    fallos, _info = obs.comparar(despues, mutilada)
    assert fallos == [f"[esquema] {TABLA_ESP}.mtf_10_pct desapareció"], fallos


def test_una_baja_disfrazada_de_renombrado_sigue_siendo_fallo(bd_sembrada, monkeypatch):
    """Si `lp_cm_maximo` YA existia antes y `lp_mm_maximo` desaparece, no es un renombrado: es una columna perdida."""
    _antes_y_despues(bd_sembrada, monkeypatch)
    despues = obs.capturar(bd_sembrada)
    con_las_dos = json.loads(json.dumps(despues))
    con_las_dos["esquema"][TABLA_ESP].append("lp_mm_maximo")
    fallos, info = obs.comparar(con_las_dos, despues)
    assert fallos == [f"[esquema] {TABLA_ESP}.lp_mm_maximo desapareció"], fallos
    assert _lineas_de_renombrado(info) == [], info


def test_un_renombrado_declarado_para_otra_tabla_no_vale(bd_sembrada, monkeypatch):
    """`lp_mm` -> `lp_cm` esta declarado para `resolucion_espacial_regiones`; en `espesor_corte` seria una columna perdida."""
    _antes_y_despues(bd_sembrada, monkeypatch)
    despues = obs.capturar(bd_sembrada)
    otra = json.loads(json.dumps(despues))
    otra["esquema"]["espesor_corte"].append("lp_mm")
    despues_con_lp_cm = json.loads(json.dumps(despues))
    despues_con_lp_cm["esquema"]["espesor_corte"].append("lp_cm")
    fallos, info = obs.comparar(otra, despues_con_lp_cm)
    assert fallos == ["[esquema] espesor_corte.lp_mm desapareció"], fallos
    assert _lineas_de_renombrado(info) == [], info
    assert info == ["[esquema] columna nueva espesor_corte.lp_cm"], info


def test_un_renombrado_declarado_cuyo_destino_no_aparece_sigue_siendo_fallo(bd_sembrada, monkeypatch):
    _antes_y_despues(bd_sembrada, monkeypatch)
    despues = obs.capturar(bd_sembrada)
    sin_destino = json.loads(json.dumps(despues))
    sin_destino["esquema"][TABLA_REG].remove("lp_cm")
    antes_viejo = json.loads(json.dumps(despues))
    antes_viejo["esquema"][TABLA_REG] = ["lp_mm" if c == "lp_cm" else c for c in antes_viejo["esquema"][TABLA_REG]]
    fallos, info = obs.comparar(antes_viejo, sin_destino)
    assert fallos == [f"[esquema] {TABLA_REG}.lp_mm desapareció"], fallos
    assert _lineas_de_renombrado(info) == [], info


def test_dos_fotos_de_versiones_distintas_del_observador_no_se_comparan(bd_sembrada, monkeypatch):
    """Una foto tomada por el observador anterior (huellas con los nombres REALES y sin registro `observador`) contra una de este
    daria 7 `cambia` falsos: la comparacion se niega con UNA sola linea que pide volver a capturar, sin ruido detras (H4 de la
    revision: antes se apilaban los 7 `cambia` tras el fallo de version). La foto vieja se fabrica como la tomaria HEAD: lista
    de renombrados vacia al capturar y sin la clave `observador`."""
    lista = {"v": ()}
    monkeypatch.setattr(obs, "_renombres_declarados", lambda: lista["v"])
    _a_nombres_viejos(bd_sembrada)
    vieja = obs.capturar(bd_sembrada)
    assert vieja["renombres_aplicados"] == []
    vieja.pop("observador")
    lista["v"] = tuple(tuple(r) for r in RENOMBRES_DE_COLUMNAS)
    _abrir_con_la_app(bd_sembrada, monkeypatch)
    despues = obs.capturar(bd_sembrada)
    assert despues["observador"]["version"] == obs.VERSION_OBSERVADOR
    fallos, info = obs.comparar(vieja, despues)
    assert len(fallos) == 1, fallos
    assert "[observador]" in fallos[0] and "versi" in fallos[0] and "capturar" in fallos[0], fallos
    assert info == [], "tras negarse no se reporta nada mas: lo demas seria ruido del instrumento"

    otra_regla = json.loads(json.dumps(despues))
    otra_regla["observador"]["renombres_declarados"].append(["x", "a", "b"])
    fallos, info = obs.comparar(otra_regla, despues)
    assert len(fallos) == 1 and "[observador]" in fallos[0], fallos
    assert info == []


def test_la_lista_que_manda_al_comparar_es_la_que_registran_las_fotos(tmp_path, monkeypatch):
    """H3 de la revision: dos fotos tomadas SIN renombrados declarados (huellas con nombres reales, lista vacia registrada) entre
    las que una columna se dio de baja y otra de alta. Si `comparar` mirara el arbol de HOY (que si declara lp_mm -> lp_cm) lo
    tomaria por un renombrado; mirando lo que las fotos registran, es una columna perdida. Base vacia para que solo hable el
    esquema."""
    ruta = str(tmp_path / "vacia.db")
    _abrir_con_la_app(ruta, monkeypatch)
    lista = {"v": ()}
    monkeypatch.setattr(obs, "_renombres_declarados", lambda: lista["v"])
    _a_nombres_viejos(ruta)
    antes = obs.capturar(ruta)
    _abrir_con_la_app(ruta, monkeypatch)
    despues = obs.capturar(ruta)
    assert antes["observador"]["renombres_declarados"] == [] == despues["observador"]["renombres_declarados"]
    lista["v"] = tuple(tuple(r) for r in RENOMBRES_DE_COLUMNAS)        # el arbol de hoy SI los declara
    fallos, info = obs.comparar(antes, despues)
    assert sorted(fallos) == sorted([f"[esquema] {TABLA_ESP}.lp_mm_maximo desapareció",
                                     f"[esquema] {TABLA_REG}.lp_mm desapareció"]), fallos
    assert _lineas_de_renombrado(info) == [], info
    assert sorted(info) == sorted([f"[esquema] columna nueva {TABLA_ESP}.lp_cm_maximo",
                                   f"[esquema] columna nueva {TABLA_REG}.lp_cm"]), info
    # y pasando la lista a mano, manda la que se pasa (base vacia: las huellas no distinguen nada, solo habla el esquema)
    fallos, info = obs.comparar(antes, despues, renombres=lista["v"])
    assert fallos == [] and len(_lineas_de_renombrado(info)) == 2, (fallos, info)


def test_la_canonizacion_es_por_tabla_y_no_por_nombre(bd_sembrada, monkeypatch):
    """MO7 del arnes y H6 de la revision: `lp_mm` -> `lp_cm` esta declarado para `resolucion_espacial_regiones`; una columna
    `lp_mm` de OTRA tabla (p. ej. la MTF de pylinac, que si es lp/mm) no se traduce ni se registra como traducida. Con datos
    reales no se nota (ninguna otra tabla del contrato se llama asi): se fabrica la columna. Y el nombre NUEVO con otra
    capitalizacion (`LP_CM`) tambien se canoniza (MX1)."""
    renombres = obs._renombres_declarados()
    assert obs._nombre_canonico(TABLA_REG, "lp_mm", renombres) == "lp_cm"
    assert obs._nombre_canonico(TABLA_REG, "LP_CM", renombres) == "lp_cm"
    assert obs._nombre_canonico(TABLA_REG, "lp_cm", renombres) == "lp_cm"
    assert obs._nombre_canonico("espesor_corte", "lp_mm", renombres) == "lp_mm"
    assert obs._nombre_canonico("espesor_corte", "lp_cm", renombres) == "lp_cm"
    assert obs._destino_declarado("espesor_corte", "lp_mm", renombres) is None

    con = sqlite3.connect(bd_sembrada)
    try:
        con.execute('ALTER TABLE "espesor_corte" ADD COLUMN lp_mm REAL')
        con.execute(f'ALTER TABLE "{TABLA_REG}" RENAME COLUMN lp_cm TO LP_CM')
        con.commit()
    finally:
        con.close()
    _renombrar(bd_sembrada, [(TABLA_ESP, "lp_cm_maximo", "lp_mm_maximo")])
    antes = obs.capturar(bd_sembrada)
    assert "lp_mm" in antes["esquema"]["espesor_corte"] and "LP_CM" in antes["esquema"][TABLA_REG]
    aplicados = {tuple(x) for x in antes["renombres_aplicados"]}
    assert aplicados == {(TABLA_ESP, "lp_mm_maximo", "lp_cm_maximo"), (TABLA_REG, "LP_CM", "lp_cm")}, \
        "la columna fabricada de otra tabla no se traduce; LP_CM se canoniza: " + repr(antes["renombres_aplicados"])
    _abrir_con_la_app(bd_sembrada, monkeypatch)
    despues = obs.capturar(bd_sembrada)
    assert "lp_mm" in despues["esquema"]["espesor_corte"], "GI.0 no toca una columna de otra tabla"
    fallos, info = obs.comparar(antes, despues)
    assert fallos == [], fallos
    assert len(_lineas_de_renombrado(info)) == 1 and f"{TABLA_ESP}.lp_mm_maximo -> lp_cm_maximo" in info[0], info
    assert antes["vigente"] == despues["vigente"]


def test_la_version_del_observador_es_la_2_y_cambiar_la_huella_exige_subirla():
    """MX2 de la revision: la version viaja en cada foto y decide si dos fotos son comparables. 1 = huellas con el nombre real
    de cada columna (hasta GI.0); 2 = con el nombre canonico de los renombrados declarados (GI.0b). Quien cambie como se
    hashea tiene que subirla, o dos fotos incomparables pasarian por comparables."""
    assert obs.VERSION_OBSERVADOR == 2


@pytest.mark.parametrize("orden", ["lp_cm anadida a una base con los nombres viejos", "lp_mm anadida a una base nueva"])
def test_con_las_dos_columnas_presentes_la_foto_se_niega_en_vez_de_quedar_ciega(bd_sembrada, orden):
    """H1 de la revision (alta): con el nombre viejo Y el nuevo a la vez (el caso que GI.0 deja sin tocar, `existen las dos
    columnas`), las dos caerian bajo una sola clave de la huella y la que perdiera la clave quedaria ciega: medido, alterar
    `lp_cm` con `lp_mm` al lado daba 0 fallos. La foto se niega nombrando la tabla y las columnas."""
    con = sqlite3.connect(bd_sembrada)
    try:
        if orden.startswith("lp_cm"):
            for tabla, (vieja, nueva) in RENOMBRADAS.items():
                con.execute(f'ALTER TABLE "{tabla}" RENAME COLUMN "{nueva}" TO "{vieja}"')
                con.execute(f'ALTER TABLE "{tabla}" ADD COLUMN "{nueva}" REAL')
        else:
            for tabla, (vieja, _nueva) in RENOMBRADAS.items():
                con.execute(f'ALTER TABLE "{tabla}" ADD COLUMN "{vieja}" REAL')
        con.commit()
    finally:
        con.close()
    with pytest.raises(RuntimeError, match="a la vez el nombre viejo y el nuevo") as e:
        obs.capturar(bd_sembrada)
    assert TABLA_ESP in str(e.value) and "lp_cm_maximo" in str(e.value) and "lp_mm_maximo" in str(e.value), str(e.value)
    with pytest.raises(RuntimeError, match="a la vez el nombre viejo y el nuevo"):
        obs.capturar(bd_sembrada, tolerar_tablas_ausentes=True)     # la tolerancia de tablas ausentes no la salta
    # resueltas las dos columnas (se retira la vacia), la foto vuelve a tomarse
    con = sqlite3.connect(bd_sembrada)
    try:
        for tabla, (vieja, nueva) in RENOMBRADAS.items():
            con.execute(f'ALTER TABLE "{tabla}" DROP COLUMN "{nueva if orden.startswith("lp_cm") else vieja}"')
        con.commit()
    finally:
        con.close()
    assert obs.capturar(bd_sembrada)["vigente"][TABLA_REG]


def test_el_lector_rechaza_listas_con_las_que_la_huella_no_sabria_que_hacer(tmp_path, monkeypatch):
    """H5 de la revision: encadenados (a->b, b->c: `_nombre_canonico` no sigue cadenas y una base que paso a->c daria falso rojo),
    vieja repetida, vieja == nueva, dos que desembocan en el mismo nombre, y una clave de bloque o `activo`."""
    falso = tmp_path / "conection_falsa.py"
    monkeypatch.setattr(obs, "CONEXION_PATH", falso)
    casos = {
        "encadenados": 'RENOMBRES_DE_COLUMNAS = (("t", "a", "b"), ("t", "b", "c"),)\n',
        "declarada dos veces": 'RENOMBRES_DE_COLUMNAS = (("t", "a", "b"), ("t", "A", "c"),)\n',
        "no renombra nada": 'RENOMBRES_DE_COLUMNAS = (("t", "a", "A"),)\n',
        "desembocan en": 'RENOMBRES_DE_COLUMNAS = (("t", "a", "c"), ("t", "b", "C"),)\n',
        "clave o de vigencia": 'RENOMBRES_DE_COLUMNAS = (("t", "activo", "activo_x"),)\n',
    }
    for motivo, texto in casos.items():
        falso.write_text(texto, encoding="utf-8")
        with pytest.raises(RuntimeError, match=motivo):
            obs._renombres_declarados()
    for clave in sorted(obs.CLAVES_NO_RENOMBRABLES):
        falso.write_text(f'RENOMBRES_DE_COLUMNAS = (("t", "x", "{clave}"),)\n', encoding="utf-8")
        with pytest.raises(RuntimeError, match="clave o de vigencia"):
            obs._renombres_declarados()
    # la misma pareja en DOS tablas distintas no es cadena ni repeticion
    falso.write_text('RENOMBRES_DE_COLUMNAS = (("t", "a", "b"), ("u", "a", "b"), ("u", "b", "zz"))\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="encadenados"):
        obs._renombres_declarados()                       # ... salvo la de `u`, que si encadena b
    falso.write_text('RENOMBRES_DE_COLUMNAS = (("t", "a", "b"), ("u", "a", "b"))\n', encoding="utf-8")
    assert obs._renombres_declarados() == (("t", "a", "b"), ("u", "a", "b"))


# ---------------------------------------------------------------------------
# 3b. la foto de ANTES del rebuild se toma sobre la copia CRUDA de produccion (H2 de la revision)
# ---------------------------------------------------------------------------

PRODUCCION_06_10 = CARPETA_BD / "BaseDatosQA(Produccion_2026-10-06).db"
CRUDAS = [BD_REBUILD_21_09, PRODUCCION_06_10]


def _copiar_con_wal(origen, tmp_path):
    """La copia de produccion del 06-10 son TRES archivos: el `-wal` guarda su ultima transaccion."""
    ruta = _copiar(origen, tmp_path)
    for sufijo in ("-wal", "-shm"):
        companero = pathlib.Path(str(origen) + sufijo)
        if companero.exists():
            shutil.copy(companero, ruta + sufijo)
    return ruta


def _tablas_de(ruta):
    con = sqlite3.connect(ruta)
    try:
        return {t[0] for t in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()


@pytest.mark.parametrize("origen", CRUDAS, ids=[b.name for b in CRUDAS])
def test_la_foto_de_antes_se_toma_sobre_la_copia_cruda_y_el_rebuild_da_luz_verde(origen, tmp_path, monkeypatch):
    """El paso 3b de la puerta de salida tal cual: foto de la copia cruda (le faltan las tablas que la app nueva crea al abrir,
    asi que por omision `capturar` se niega y con `--tolerar-tablas-ausentes` las anota y las omite), abrir con la app (crea
    las tablas, renombra las dos columnas Y ANADE columnas a otras tablas: tareas del 21 al 25-09 que la copia desplegada no
    tenia), foto, comparar. Lo que GI.0b garantiza: las dos tablas renombradas salen LIMPIAS (ni `desaparecio` ni `cambia`), y
    los unicos fallos que quedan son los bloques de las tablas que GANARON columnas (DP-86 clasico: columnas nuevas en NULL
    cambian la huella; fuera del alcance de GI.0b), que se declaran con la receta de DP-86 y entonces la puerta da luz verde."""
    ruta = _copiar_con_wal(origen, tmp_path)
    faltan = [t for t in obs._tablas_en_alcance() if t not in _tablas_de(ruta)]
    assert faltan, "la copia cruda debe carecer de alguna tabla del contrato para que el caso sea el real"
    assert "lp_mm_maximo" in _cols(ruta, TABLA_ESP), "la copia cruda trae los nombres viejos"
    with pytest.raises(RuntimeError, match="no existe"):
        obs.capturar(ruta)                                           # por omision sigue siendo estricto
    antes = obs.capturar(ruta, tolerar_tablas_ausentes=True)
    assert antes["tablas_ausentes"] == faltan
    assert not any(t in antes["esquema"] or t in antes["vigente"] for t in faltan)
    assert {tuple(x) for x in antes["renombres_aplicados"]} == {(t, v, n) for t, (v, n) in RENOMBRADAS.items()}
    _abrir_con_la_app(ruta, monkeypatch)
    despues = obs.capturar(ruta)
    assert despues["tablas_ausentes"] == [] and all(t in despues["esquema"] for t in faltan)
    fallos, info = obs.comparar(antes, despues)

    # 1. las dos tablas renombradas: limpias, con sus dos lineas informativas y sin `columna nueva`
    assert not any(TABLA_ESP in f or TABLA_REG in f for f in fallos), [f for f in fallos if TABLA_ESP in f or TABLA_REG in f]
    assert len(_lineas_de_renombrado(info)) == 2, info
    assert not any("columna nueva" in l and (f" {TABLA_ESP}." in l or f" {TABLA_REG}." in l) for l in info), info
    assert antes["censo"][TABLA_ESP] == despues["censo"][TABLA_ESP] and antes["vigente"][TABLA_ESP] == despues["vigente"][TABLA_ESP]
    assert antes["censo"][TABLA_REG] == despues["censo"][TABLA_REG] and antes["vigente"][TABLA_REG] == despues["vigente"][TABLA_REG]
    # 2. las tablas que faltaban: `tabla nueva`, informativo
    assert sorted(l for l in info if "tabla nueva" in l) == sorted(f"[esquema] tabla nueva '{t}'" for t in faltan), info
    # 3. lo que queda son SOLO bloques `cambia` de tablas que ganaron columnas (DP-86, declarable), nunca una perdida
    con_columnas_nuevas = {l.split("columna nueva ")[1].split(".")[0] for l in info if "columna nueva" in l}
    assert con_columnas_nuevas, "la copia desplegada tiene que ganar columnas al abrirse con la app de hoy (A.1, A.2, G.2, G.3, B.4...)"
    for f in fallos:
        assert f.startswith("[vigente] ") and f.endswith(": cambia (NO declarado)"), f
        assert f.split(" ")[1] in con_columnas_nuevas, "un `cambia` en una tabla que NO gano columnas seria un dato alterado: " + f
    assert not any(("desapareci" in f) or f.startswith(("[censo]", "[integridad]", "[indices]", "[observador]")) for f in fallos)
    for tabla in antes["censo"]:
        assert antes["censo"][tabla] == despues["censo"][tabla], tabla
    # 4. con la receta de DP-86 (declarar los bloques de las tablas que ganaron columnas) la puerta da luz verde
    esperado = {"vigente_cambios_esperados": {}}
    for f in fallos:
        tabla, ref = f.split(" ")[1], f.split("ref=")[1].split(":")[0]
        esperado["vigente_cambios_esperados"].setdefault(tabla, []).append(ref)
    fallos2, info2 = obs.comparar(antes, despues, esperado)
    assert fallos2 == [], fallos2
    assert len(_lineas_de_renombrado(info2)) == 2 and len(info2) >= 2 + len(faltan) + len(fallos), info2


def test_por_la_linea_de_ordenes_la_foto_cruda_necesita_la_opcion_y_la_anota(tmp_path, monkeypatch):
    ruta = _copiar(BD_REBUILD_21_09, tmp_path)
    salida = tmp_path / "antes.json"
    orden = [sys.executable, str(RAIZ / "scripts" / "observador_contrato.py"), "capturar", ruta, "--salida", str(salida)]
    r = subprocess.run(orden, cwd=str(RAIZ), capture_output=True, text=True)
    assert r.returncode != 0 and "no existe" in (r.stderr + r.stdout), r.stderr
    r = subprocess.run(orden + ["--tolerar-tablas-ausentes"], cwd=str(RAIZ), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "AVISO" in r.stderr and "la foto la omite" in r.stderr, r.stderr
    foto = json.loads(salida.read_text(encoding="utf-8"))
    assert foto["tablas_ausentes"] and foto["observador"]["version"] == 2


# ---------------------------------------------------------------------------
# 4. por la linea de ordenes, como en la puerta de salida
# ---------------------------------------------------------------------------

def test_por_la_linea_de_ordenes_el_renombrado_da_luz_verde_y_exit_0(bd_sembrada, monkeypatch, tmp_path):
    antes, despues = _antes_y_despues(bd_sembrada, monkeypatch)
    a, d = tmp_path / "antes.json", tmp_path / "despues.json"
    a.write_text(json.dumps(antes, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    d.write_text(json.dumps(despues, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "observador_contrato.py"), "comparar", str(a), str(d)],
                       cwd=str(RAIZ), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK -- todos los cambios están declarados." in r.stdout, r.stdout
    assert r.stdout.count("columna renombrada") == 2, r.stdout
    assert "FALLOS" not in r.stdout
