"""A.2 (PLAN_HANDOFF_IMAGENES_22-09.md, ajuste 23-09): el protocolo de
adquisición FIJO de cada equipo vive en un catálogo versionado
(`analisisImagenes/catphan/protocolos.py`), y cada prueba archiva por qué su
adquisición no es la del protocolo (`pruebas.desviacion_protocolo`).

CAUSA (§0.4): tres sesiones archivadas (6, 30 y 48) llevan la adquisición de un
equipo distinto al declarado, o de otro preset del mismo, y el programa no tenía
con qué compararlas. Verificación corregida (§0.10.1): las sesiones 6 y 48
reproducen OTRO EQUIPO (la identidad no coincide); la 30 reproduce el MISMO
equipo FUERA DE PROTOCOLO (iX a 125 kV). La matriz distingue los dos casos.

Lo que este archivo garantiza:

  1. CENSO -- un protocolo por cada equipo de `perfiles.PERFILES`, con la
     identidad coherente con las reglas de identificación y las tolerancias solo
     sobre campos comparados.
  2. MATRIZ -- las seis series reales x los cuatro equipos de la app, con el
     veredicto exacto de cada pareja.
  3. SEMANTICA -- "fuera de protocolo" NO bloquea; lo que el equipo no publica no
     se exige; lo que se exige y no se publica no cumple; la tolerancia es del
     catálogo.
  4. PERSISTENCIA -- la desviación se guarda por categoría y sin ella el
     comportamiento es el de siempre.
  5. PANTALLA -- `_registrar_adquisicion` la calcula contra el equipo
     SELECCIONADO.
  6. UNA DEFINICION -- el texto "fuera de protocolo" solo lo produce
     `protocolos.py`.
"""
import ast
import dataclasses
import os
import pathlib
import shutil
import sqlite3
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.catphan_TAC.catphan_db import guardar_prueba_completa_catphan
from analisisImagenes.catphan import protocolos as prot
from analisisImagenes.catphan.perfiles import PERFILES
from analisisImagenes.catphan.protocolos import (
    CAMPOS_COMPARADOS, COINCIDE, NO_IDENTIFICADO, OTRO_EQUIPO, PROTOCOLOS, SIN_EQUIPO,
    SIN_PROTOCOLO, comparar_con_protocolo)
from analisisImagenes.catphan.serie import (
    _REGLAS_EQUIPO, adquisicion_de_serie, identificar_equipo, identificar_equipo_por_datos,
    leer_serie)
from _bd_referencia import BD_QA, BD_REBUILD_14_09
from _corpus import serie_catphan

RAIZ = pathlib.Path(__file__).resolve().parent.parent
EQUIPOS_DE_LA_APP = ("Tomógrafo", "Halcyon", "Clinac ix", "Clinac 600")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _adquisicion(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return adquisicion_de_serie(leer_serie(ruta))


# ---------------------------------------------------------------------------
# 1. CENSO del catálogo
# ---------------------------------------------------------------------------

def test_hay_un_protocolo_por_cada_equipo_de_imagen():
    """Una prueba de imagen nueva no puede nacer sin protocolo: mismas claves
    que `perfiles.PERFILES` (que es lo que la pantalla usa para nombrar equipos)."""
    assert set(PROTOCOLOS) == set(PERFILES)


def test_cada_protocolo_se_llama_como_su_clave():
    for clave, p in PROTOCOLOS.items():
        assert p.equipo == clave


def test_la_identidad_del_catalogo_coincide_con_las_reglas_de_identificacion():
    """El catálogo declara la identidad ESPERADA y `_REGLAS_EQUIPO` la usa para
    RECONOCER el equipo: dos tablas con los mismos literales. Este censo las
    ata: si una cambia sin la otra, falla."""
    for equipo, p in PROTOCOLOS.items():
        regla = _REGLAS_EQUIPO[equipo]
        assert p.fabricante == regla["manufacturer"], equipo
        assert p.modelo == regla["model"], equipo
        if regla["station"] is not None:
            assert p.estacion == regla["station"], equipo
        if regla["serial"] is not None:
            assert p.numero_serie_equipo == regla["serial"], equipo


def test_cada_campo_comparado_existe_en_el_catalogo_y_en_la_adquisicion():
    adq = _adquisicion("IX_DIC")
    for _grupo, campo, _etiqueta, _numerico in CAMPOS_COMPARADOS:
        assert campo in adq, f"`adquisicion_de_serie` no trae '{campo}'"
        for p in PROTOCOLOS.values():
            assert hasattr(p, campo), f"el protocolo de {p.equipo} no tiene '{campo}'"


def test_las_tolerancias_solo_nombran_campos_comparados_numericos():
    numericos = {c for _g, c, _e, num in CAMPOS_COMPARADOS if num}
    for p in PROTOCOLOS.values():
        assert set(p.tolerancias) <= numericos, (p.equipo, set(p.tolerancias) - numericos)


def test_cada_protocolo_dice_de_donde_salio_y_que_falta_confirmar():
    for p in PROTOCOLOS.values():
        assert "23-09-2026" in p.origen and "§0.8" in p.origen, p.equipo
        assert p.condiciones_pendientes, f"{p.equipo}: sin condiciones de consola declaradas"
        assert p.posicion_fantoma


def test_los_valores_decididos_el_23_09():
    """Cambiar un protocolo corta la línea base del equipo: tiene que ser un acto
    deliberado. Este test fija lo decidido (§0.8); si falla, o se cometió un
    error o hay una decisión nueva que debe llegar con su commit y su motivo."""
    t, h, i = PROTOCOLOS["Tomógrafo"], PROTOCOLOS["Halcyon"], PROTOCOLOS["Clinac ix"]
    assert (t.descripcion_serie, t.kv, t.ma, t.mas, t.espesor_mm, t.fov_mm, t.kernel) == (
        "RT_CABEZA 2,00 Qr40 S2", 120.0, 200, 250, 2.0, 550.0, "Qr40f")
    assert (h.descripcion_serie, h.kv, h.ma, h.mas, h.espesor_mm, h.fov_mm) == (
        "Pelvis_iCBCT_2.0_IQ!", 125.0, 80, 1074, 2.0, 491.0)
    assert (i.descripcion_serie, i.kv, i.ma, i.mas, i.espesor_mm, i.fov_mm, i.kernel) == (
        None, 100.0, 80, 724, 2.5, 250.0, "Ram-Lak")
    # la energía de la linealidad (G.2) = kV del protocolo, en MeV
    assert (t.energia_linealidad_mev, h.energia_linealidad_mev, i.energia_linealidad_mev) == (0.120, 0.125, 0.100)
    for p in (t, h, i):
        assert p.energia_linealidad_mev * 1000 == pytest.approx(p.kv)
    # el corrimiento de escala esperado (B.3): ≈ +490 en el iX, ≈ 0 en los otros
    assert (t.corrimiento_hu_esperado, h.corrimiento_hu_esperado, i.corrimiento_hu_esperado) == (0.0, 0.0, 490.0)


# ---------------------------------------------------------------------------
# 2. MATRIZ: las seis series reales x los cuatro equipos de la app
#    Identidad por serie [medida]; campos fuera de protocolo derivados a mano de
#    la tabla de §0.8 (no de la propia función).
# ---------------------------------------------------------------------------

EQUIPO_DE_LA_SERIE = {
    "TOMOGRAFO": "Tomógrafo", "MIXTA": "Tomógrafo", "HALCYON_JUN": "Halcyon",
    "HALCYON_SEP": "Halcyon", "HALCYON_236": "Halcyon", "IX_DIC": "Clinac ix",
}

# Para la pareja (serie, su propio equipo): qué campos de adquisición NO cumplen.
FUERA_DE_PROTOCOLO = {
    "TOMOGRAFO": set(),                                         # RT_CABEZA 2,00 -> el protocolo
    "MIXTA": {"descripcion_serie", "espesor_mm"},               # RT_CABEZA 1,00: mismo equipo, 1 mm
    "HALCYON_SEP": set(),                                       # Pelvis_iCBCT_2.0_IQ! -> el protocolo
    "HALCYON_JUN": {"descripcion_serie", "ma", "mas"},          # Pelvis Fast: 100 mA / 591 mAs
    "HALCYON_236": {"descripcion_serie", "kv", "ma", "mas", "fov_mm"},  # 140 kV/90 mA, sin nombre
    "IX_DIC": set(),                                            # Catphandiciembre -> el protocolo
}


@pytest.mark.parametrize("equipo", EQUIPOS_DE_LA_APP)
@pytest.mark.parametrize("serie", sorted(EQUIPO_DE_LA_SERIE))
def test_matriz_series_reales_por_equipo(serie, equipo):
    adq = _adquisicion(serie)
    c = comparar_con_protocolo(equipo, adq)
    propio = EQUIPO_DE_LA_SERIE[serie]
    if equipo not in PROTOCOLOS:                                # 'Clinac 600': sin equipo de imagen
        assert c.identidad == SIN_PROTOCOLO
        assert c.filas == ()
        assert "no tiene protocolo de imagen" in c.desviacion_texto()
    elif equipo != propio:                                      # otro equipo (sesiones 6 y 48)
        assert c.identidad == OTRO_EQUIPO
        assert c.equipo_identificado == propio
        assert propio in c.desviacion_texto() and equipo in c.desviacion_texto()
    else:
        assert c.identidad == COINCIDE
        assert {f.campo for f in c.fuera_de_protocolo} == FUERA_DE_PROTOCOLO[serie], serie
        assert (c.desviacion_texto() is None) == (not FUERA_DE_PROTOCOLO[serie])


def test_las_tres_series_del_protocolo_decidido_no_tienen_desviacion():
    """El protocolo fijo se eligió DE estas series: contra sí mismas no puede
    haber desviación (si la hubiera, el catálogo no describe lo que dice)."""
    for serie in ("TOMOGRAFO", "HALCYON_SEP", "IX_DIC"):
        assert comparar_con_protocolo(EQUIPO_DE_LA_SERIE[serie], _adquisicion(serie)).desviacion_texto() is None


def test_sesion_6_un_halcyon_archivado_como_clinac_ix_es_otro_equipo():
    """Sesión 6: declarada 'Clinac ix', con 140/90/2.0 = `CATPHANKV` (Halcyon)."""
    c = comparar_con_protocolo("Clinac ix", _adquisicion("HALCYON_236"))
    assert c.identidad == OTRO_EQUIPO and c.equipo_identificado == "Halcyon"
    # las filas siguen disponibles (la ventana de A.3 las muestra), pero el texto
    # ARCHIVADO habla de la identidad, no de un protocolo que no aplica a otro equipo
    assert c.fuera_de_protocolo, "las filas de comparación deben seguir existiendo"
    assert "kV" not in c.desviacion_texto() and "exigido" not in c.desviacion_texto()


def test_sesion_48_un_halcyon_archivado_como_tomografo_es_otro_equipo():
    """Sesión 48 (22-09): declarada 'Tomógrafo', con 140/90/2.0 = `CATPHANKV`."""
    c = comparar_con_protocolo("Tomógrafo", _adquisicion("HALCYON_236"))
    assert c.identidad == OTRO_EQUIPO and c.equipo_identificado == "Halcyon"


def test_sesion_30_el_mismo_ix_con_otro_preset_esta_fuera_de_protocolo():
    """Sesión 30: declarada 'Clinac ix', 125 kV / 80 mA / 2.5 mm. NO es otro
    equipo (§0.10.1): es el iX con otro preset. Se reproduce con la identidad
    real del iX y el kV de esa sesión."""
    adq = dict(_adquisicion("IX_DIC"), kv=125.0)
    c = comparar_con_protocolo("Clinac ix", adq)
    assert c.identidad == COINCIDE
    assert [f.campo for f in c.fuera_de_protocolo] == ["kv"]
    assert c.desviacion_texto() == "Adquisición fuera de protocolo: kV: 125 (exigido 100)"


# ---------------------------------------------------------------------------
# 3. SEMANTICA de la comparación
# ---------------------------------------------------------------------------

def _ix(**cambios):
    return dict(_adquisicion("IX_DIC"), **cambios)


def _hc(**cambios):
    return dict(_adquisicion("HALCYON_SEP"), **cambios)


def test_fuera_de_protocolo_no_bloquea_devuelve_un_resultado_no_lanza():
    """El físico: 'no lo podemos controlar con la aplicación, pero se puede
    avisar y delimitar'."""
    for equipo in EQUIPOS_DE_LA_APP + ("esHC", "", None, "Equipo Inventado"):
        comparar_con_protocolo(equipo, _adquisicion("HALCYON_236"))
        comparar_con_protocolo(equipo, {})
        comparar_con_protocolo(equipo, None)


def test_sin_equipo_seleccionado_no_hay_nada_que_comparar():
    for vacio in (None, ""):
        c = comparar_con_protocolo(vacio, _adquisicion("IX_DIC"))
        assert c.identidad == SIN_EQUIPO and c.desviacion_texto() is None


def test_lo_que_el_equipo_no_publica_y_el_protocolo_no_exige_no_cuenta():
    """El iX no publica descripción ni filtro y su protocolo no los exige: filas
    con `cumple=None`, no ✗."""
    c = comparar_con_protocolo("Clinac ix", _adquisicion("IX_DIC"))
    filas = {f.campo: f for f in c.filas}
    assert filas["descripcion_serie"].cumple is None and filas["filtro"].cumple is None
    assert all(f.cumple is not False for f in c.filas)


def test_lo_que_se_exige_y_el_dicom_no_publica_no_cumple():
    """Se exige el nombre del protocolo del Halcyon; la serie 236 no lo trae:
    no se puede verificar, y verificar-no-se-puede no es cumplir."""
    c = comparar_con_protocolo("Halcyon", _adquisicion("HALCYON_236"))
    fila = {f.campo: f for f in c.filas}["descripcion_serie"]
    assert fila.encontrado is None and fila.cumple is False
    assert "no publicado" in c.desviacion_texto()


@pytest.mark.parametrize("espesor,cumple", [(2.0, True), (2.05, True), (1.951, True), (2.06, False), (1.94, False)])
def test_la_tolerancia_del_espesor_es_la_del_catalogo(espesor, cumple):
    c = comparar_con_protocolo("Halcyon", _hc(espesor_mm=espesor))
    assert {f.campo: f for f in c.filas}["espesor_mm"].cumple is cumple


@pytest.mark.parametrize("fov,cumple", [(491.0, True), (492.0, True), (490.0, True), (492.1, False), (489.9, False)])
def test_la_tolerancia_del_fov_es_la_del_catalogo(fov, cumple):
    c = comparar_con_protocolo("Halcyon", _hc(fov_mm=fov))
    assert {f.campo: f for f in c.filas}["fov_mm"].cumple is cumple


@pytest.mark.parametrize("campo,valor", [("ma", 81), ("ma", 79), ("mas", 1075), ("kv", 126.0)])
def test_ma_mas_y_kv_son_exactos(campo, valor):
    c = comparar_con_protocolo("Halcyon", _hc(**{campo: valor}))
    assert {f.campo: f for f in c.filas}[campo].cumple is False


def test_un_valor_no_numerico_no_cumple_ni_lanza():
    c = comparar_con_protocolo("Halcyon", _hc(kv="mucho"))
    assert {f.campo: f for f in c.filas}["kv"].cumple is False


def test_equipo_no_reconocido_advierte_sin_bloquear():
    adq = dict(_hc(), fabricante="Otro Fabricante", modelo="Modelo Nuevo", estacion="X1")
    c = comparar_con_protocolo("Halcyon", adq)
    assert c.identidad == NO_IDENTIFICADO
    assert "no reconocido" in c.desviacion_texto() and "Modelo Nuevo" in c.desviacion_texto()


def test_misma_maquina_con_otra_estacion_advierte_no_calla():
    """Modelo igual, estación distinta (consola renombrada): sigue siendo ese
    equipo, pero NO se calla -- ni siquiera cuando la regla de identificación
    (que para el tomógrafo no exige estación) no genera texto."""
    adq = dict(_adquisicion("TOMOGRAFO"), estacion="CT999999")
    c = comparar_con_protocolo("Tomógrafo", adq)
    assert c.identidad == COINCIDE
    assert c.advertencia_identidad and "CT999999" in c.advertencia_identidad
    assert c.desviacion_texto().startswith("Identidad: ")


def test_identificar_equipo_y_la_comparacion_usan_la_misma_regla():
    """Una regla, dos llamadores: sobre las 6 series reales, lo que devuelve
    `identificar_equipo(serie)` es lo mismo que `identificar_equipo_por_datos`
    con la adquisición, y la comparación lo respeta."""
    for clave in EQUIPO_DE_LA_SERIE:
        ruta = serie_catphan(clave)
        if ruta is None:
            pytest.skip(f"corpus Catphan no disponible: {clave}")
        serie = leer_serie(ruta)
        adq = adquisicion_de_serie(serie)
        por_datos = identificar_equipo_por_datos(
            adq["fabricante"], adq["modelo"], adq["numero_serie_equipo"], adq["estacion"])
        assert por_datos == identificar_equipo(serie)
        assert comparar_con_protocolo("Clinac 600", adq).equipo_identificado == por_datos[0]


def test_el_catalogo_es_inmutable_por_asignacion():
    with pytest.raises(dataclasses.FrozenInstanceError):
        PROTOCOLOS["Halcyon"].kv = 140.0


# ---------------------------------------------------------------------------
# 4. PERSISTENCIA
# ---------------------------------------------------------------------------

def _abrir_con_la_app(ruta, monkeypatch):
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    con = Conexion()
    con.con.close()
    Conexion._instance = None


def _columnas(ruta):
    con = sqlite3.connect(ruta)
    try:
        return {f[1]: (f[2], f[3]) for f in con.execute("PRAGMA table_info(pruebas)")}
    finally:
        con.close()


def test_bd_nueva_tiene_la_columna_text_y_admite_null(tmp_path, monkeypatch):
    ruta = str(tmp_path / "nueva.db")
    _abrir_con_la_app(ruta, monkeypatch)
    assert _columnas(ruta)["desviacion_protocolo"] == ("TEXT", 0)


def test_bd_legada_la_gana_y_una_segunda_apertura_no_la_duplica(tmp_path, monkeypatch):
    ruta = str(tmp_path / "legada.db")
    _abrir_con_la_app(ruta, monkeypatch)
    if sqlite3.sqlite_version_info < (3, 35, 0):
        pytest.skip("SQLite < 3.35: sin DROP COLUMN")
    con = sqlite3.connect(ruta)
    con.execute("ALTER TABLE pruebas DROP COLUMN desviacion_protocolo")
    con.commit()
    con.close()
    assert "desviacion_protocolo" not in _columnas(ruta)
    _abrir_con_la_app(ruta, monkeypatch)
    uno = _columnas(ruta)
    _abrir_con_la_app(ruta, monkeypatch)
    assert "desviacion_protocolo" in uno and _columnas(ruta) == uno


@pytest.mark.parametrize("origen", [BD_QA, BD_REBUILD_14_09], ids=lambda p: p.name)
def test_ensayo_sobre_copia_de_bd_real(origen, tmp_path, monkeypatch):
    if not origen.exists():
        pytest.skip(f"BD de referencia ausente: {origen}")
    ruta = str(tmp_path / "copia.db")
    shutil.copy(origen, ruta)
    con = sqlite3.connect(ruta)
    n_antes = con.execute("SELECT COUNT(*) FROM pruebas").fetchone()[0]
    con.close()
    _abrir_con_la_app(ruta, monkeypatch)
    con = sqlite3.connect(ruta)
    try:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("SELECT COUNT(*) FROM pruebas").fetchone()[0] == n_antes
        # las filas históricas quedan sin desviación: no hay forma honesta de saberlo
        assert con.execute("SELECT COUNT(*) FROM pruebas WHERE desviacion_protocolo IS NOT NULL").fetchone()[0] == 0
    finally:
        con.close()


@pytest.fixture
def bd_temporal(app, monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _crear_control(ruta):
    con = sqlite3.connect(ruta)
    con.execute("INSERT INTO controles (equipo, control, fecha) VALUES ('Halcyon', 'Mensual', '06/2026')")
    con.commit()
    ref = con.execute("SELECT id FROM controles ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.close()
    return ref


UNIFORMIDAD = {"Uniformidad": {"max_diferencia": 1.0}, "Centro": {"promedio_hu": 1.0, "desviacion": 2.0}}


def _snap(desviacion, **extra):
    return {"kv": 125.0, "ma": 80, "espesor_corte": 2.0,
            "adquisicion": {"modelo": "Halcyon - PVA", "estacion": "Halcyon", "serie_uid": "u",
                            "fecha_adquisicion": "2026-09-12"},
            "desviacion_protocolo": desviacion, **extra}


def _desviacion(ruta, sesion, id_tipo):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(
            "SELECT desviacion_protocolo FROM pruebas WHERE id_sesion=? AND id_tipo=? "
            "AND (activo IS NULL OR activo=1)", (sesion, id_tipo)).fetchone()[0]
    finally:
        con.close()


def _guardar(sesion, categorias, **kw):
    base = dict(user_id="fisico1", fecha="2026-06-01", equipo="Halcyon", kv=120, ma=100, espesor_corte=1.5,
                resultados_por_categoria=categorias, id_sesion=sesion)
    base.update(kw)
    return guardar_prueba_completa_catphan(**base)


def test_cada_categoria_guarda_su_propia_desviacion(bd_temporal):
    sesion = _crear_control(bd_temporal)
    _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.0}, "uniformidad": UNIFORMIDAD},
             adquisicion_por_categoria={"espesor": _snap("kV: 140 (exigido 125)"), "uniformidad": _snap(None)})
    assert _desviacion(bd_temporal, sesion, 1) == "kV: 140 (exigido 125)"
    assert _desviacion(bd_temporal, sesion, 7) is None


def test_sin_adquisicion_la_desviacion_queda_null_como_siempre(bd_temporal):
    sesion = _crear_control(bd_temporal)
    _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.0}})
    assert _desviacion(bd_temporal, sesion, 1) is None


def test_reguardar_conserva_la_desviacion_de_la_generacion_anulada(bd_temporal):
    sesion = _crear_control(bd_temporal)
    _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.0}},
             adquisicion_por_categoria={"espesor": _snap("primera")})
    _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.1}},
             adquisicion_por_categoria={"espesor": _snap(None)})
    con = sqlite3.connect(bd_temporal)
    try:
        filas = con.execute("SELECT desviacion_protocolo, activo FROM pruebas WHERE id_sesion=? AND id_tipo=1 "
                            "ORDER BY id_prueba", (sesion,)).fetchall()
    finally:
        con.close()
    assert filas == [("primera", 0), (None, 1)]


# ---------------------------------------------------------------------------
# 5. PANTALLA: la desviación se calcula contra el equipo SELECCIONADO
# ---------------------------------------------------------------------------

def _pantalla(app, equipo_f):
    from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
    obj = PruebaMensualTAC.__new__(PruebaMensualTAC)
    QWidget.__init__(obj)
    obj.adquisicion_por_categoria = {}
    obj.imagenes_corte_por_categoria = {}      # GI.5
    if equipo_f is not None:
        obj.equipo_f = equipo_f
    return obj


def _vol(adq):
    return types.SimpleNamespace(kv=adq["kv"], ma=adq["ma"], espesor_corte=adq["espesor_mm"], adquisicion=adq)


def test_la_pantalla_calcula_la_desviacion_contra_su_equipo(app):
    pantalla = _pantalla(app, "Halcyon")
    pantalla.visualizador_principal = types.SimpleNamespace(vol=_vol(_adquisicion("HALCYON_JUN")))
    pantalla._registrar_adquisicion("espesor")
    assert pantalla.adquisicion_por_categoria["espesor"]["desviacion_protocolo"] == (
        "Adquisición fuera de protocolo: Protocolo (descripción de la serie): Pelvis Fast_iCBCT_2.0 "
        "(exigido Pelvis_iCBCT_2.0_IQ!); mA: 100 (exigido 80); mAs: 591 (exigido 1074)")


def test_la_pantalla_no_marca_desviacion_si_cumple_el_protocolo(app):
    pantalla = _pantalla(app, "Halcyon")
    pantalla.visualizador_principal = types.SimpleNamespace(vol=_vol(_adquisicion("HALCYON_SEP")))
    pantalla._registrar_adquisicion("espesor")
    assert pantalla.adquisicion_por_categoria["espesor"]["desviacion_protocolo"] is None


def test_la_pantalla_detecta_un_halcyon_cargado_en_el_formulario_del_tomografo(app):
    """El caso de la sesión 48, en la pantalla real."""
    pantalla = _pantalla(app, "Tomógrafo")
    pantalla.visualizador_principal = types.SimpleNamespace(vol=_vol(_adquisicion("HALCYON_236")))
    pantalla._registrar_adquisicion("espesor")
    texto = pantalla.adquisicion_por_categoria["espesor"]["desviacion_protocolo"]
    assert "Halcyon" in texto and "Tomógrafo" in texto


def test_la_pantalla_sin_equipo_no_inventa_una_desviacion(app):
    pantalla = _pantalla(app, None)
    pantalla.visualizador_principal = types.SimpleNamespace(vol=_vol(_adquisicion("HALCYON_JUN")))
    pantalla._registrar_adquisicion("espesor")
    assert pantalla.adquisicion_por_categoria["espesor"]["desviacion_protocolo"] is None


def test_end_to_end_una_prueba_fuera_de_protocolo_se_guarda_marcada(app, bd_temporal):
    """No bloquea: se guarda, con la desviación archivada."""
    pantalla = _pantalla(app, "Halcyon")
    pantalla.visualizador_principal = types.SimpleNamespace(vol=_vol(_adquisicion("HALCYON_JUN")))
    pantalla._registrar_adquisicion("espesor")
    sesion = _crear_control(bd_temporal)
    assert _guardar(sesion, {"espesor": {"espesor_promedio_mm": 2.0}},
                    adquisicion_por_categoria=pantalla.adquisicion_por_categoria) is not None
    assert "mA: 100 (exigido 80)" in _desviacion(bd_temporal, sesion, 1)


# ---------------------------------------------------------------------------
# 6. UNA DEFINICION del mensaje
# ---------------------------------------------------------------------------

def test_solo_protocolos_py_produce_el_texto_de_desviacion():
    """Si otro archivo armara a mano un "fuera de protocolo", habría dos
    definiciones del mismo aviso que pueden divergir (corolario 1)."""
    hallados = set()
    for ruta in RAIZ.rglob("*.py"):
        rel = ruta.relative_to(RAIZ).as_posix()
        if rel.startswith(("tests/", ".venv/", "build/", "dist/")):
            continue
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if (isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
                    and "fuera de protocolo" in nodo.value.lower()):
                hallados.add(rel)
    assert hallados == {"analisisImagenes/catphan/protocolos.py"}, hallados


def test_los_llamadores_del_guardado_traen_la_desviacion_por_la_misma_via(app):
    """`_registrar_adquisicion` es el único sitio de la pantalla que arma el
    registro por categoría, y siempre incluye `desviacion_protocolo`."""
    arbol = ast.parse((RAIZ / "ui/paginasControles/PruebasMensuales/tac_mensual.py").read_text(encoding="utf-8"))
    claves = set()
    for func in ast.walk(arbol):
        if isinstance(func, ast.FunctionDef) and func.name == "_registrar_adquisicion":
            for d in ast.walk(func):
                if isinstance(d, ast.Dict):
                    claves |= {k.value for k in d.keys if isinstance(k, ast.Constant)}
    assert {"kv", "ma", "espesor_corte", "adquisicion", "desviacion_protocolo"} <= claves
