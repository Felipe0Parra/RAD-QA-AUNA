"""B.3 (PLAN_HANDOFF_IMAGENES_22-09.md): declarar la escala de HU de cada serie.

CAUSA: el OBI del Clinac iX entrega "números de CBCT", no HU calibrados: el material del fantoma da ≈ +490 donde un equipo
calibrado da ≈ 0. Nada se lo decía al físico, ni la carga, ni el informe, ni la comparación con el protocolo.

Esto NO corrige las imágenes (restar un número a un CBCT y presentarlo como HU sería inventar una calibración): solo
DECLARA la escala.

Lo que este archivo garantiza:
  1. EL ESTIMADOR -- sobre las seis series reales el iX da ≈ +490 ± 30 y el tomógrafo y el Halcyon ≈ 0 ± 30 (la
     verificación del plan); no cambia con el muestreo; no lo mueven los vóxeles de artefacto; y sin fantoma no hay número.
  2. EL VOLUMEN lo declara en su adquisición (que es lo que se muestra, se compara y se archiva).
  3. EL CATÁLOGO lo compara: un mes que sale muy distinto del esperado del equipo es la señal de otro preset.
  4. LA VENTANA DE LA CARGA (A.3) y EL PDF (E.2) lo dicen, con la nota cuando la serie no es de HU calibrados; un control
     anterior dice que no lo registró.
  5. ESTRUCTURA -- se mide después de cargar el volumen; una sola definición de la etiqueta y de la nota.
"""
import ast
import functools
import json
import pathlib
import re
import sqlite3
import types

import numpy as np
import pytest

from _informe_imagenes import app, avisos, bd_copia, generar, paginas  # noqa: F401  (fixtures)
from _corpus import CATPHAN, serie_catphan

from analisisImagenes.catphan import escala as escala_mod
from analisisImagenes.catphan.descripcion import filas_medidas
from analisisImagenes.catphan.escala import (
    UMBRAL_ESCALA_NO_CALIBRADA_HU, desplazamiento_hu, es_escala_no_calibrada, nota_escala)
from analisisImagenes.catphan.protocolos import PROTOCOLOS, comparar_con_protocolo, texto_encontrado, texto_exigido
from analisisImagenes.catphan.serie import adquisicion_de_serie, leer_serie
from data.ManejoDatos.catphan_TAC import leer_dicom as leer_dicom_mod
from data.ManejoDatos.catphan_TAC.catphan_db import mapear_identidad_dicom
from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume
from data.ManejoDatos.catphan_TAC.ventana_metadatos import CUMPLE, NO_CUMPLE, construir_modelo_ventana

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SIMBOLOS_PROHIBIDOS = "✓✗✔✘⚠❌✅☑☒"
ETIQUETA = "Corrimiento de escala [HU]"
NOTA_CLAVE = "no son HU calibrados"
ESCALA_NO_REGISTRADA = "no registrado (control anterior al 25-09-2026)"

# Lo medido sobre las seis series reales [25-09]: resolución de ±10 HU (el ancho de la moda).
ESPERADO = {"TOMOGRAFO": 15.0, "HALCYON_SEP": 5.0, "HALCYON_JUN": -15.0, "HALCYON_236": -35.0,
            "IX_DIC": 475.0, "MIXTA": 15.0}

SESION_30 = (30, "Clinac ix", "05/2026")
SESION_42 = (42, "Tomógrafo", "07/2026")


def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return ruta


_CACHE = {}


def _medido(clave):
    """`(volumen_hu, desplazamiento)` de una serie real, calculado una vez y sin conservar el volumen."""
    if clave not in _CACHE:
        v = DicomVolume(_requerir(clave)).volumen_hu
        _CACHE[clave] = desplazamiento_hu(v)
    return _CACHE[clave]


@functools.lru_cache(maxsize=None)
def _adq_real(clave):
    return adquisicion_de_serie(leer_serie(_requerir(clave)))


CLAVES = sorted(CATPHAN)


# ---------------------------------------------------------------------------
# 1. EL ESTIMADOR
# ---------------------------------------------------------------------------

def test_el_ix_da_cerca_de_490_y_el_tomografo_y_el_halcyon_cerca_de_0():
    """La verificación del plan: Catphandiciembre ≈ +490 ± 30; QA Halcyon Catphan y QA tomografo Catphan ≈ 0 ± 30."""
    assert abs(_medido("IX_DIC") - 490) <= 30
    assert abs(_medido("HALCYON_SEP")) <= 30
    assert abs(_medido("TOMOGRAFO")) <= 30


@pytest.mark.parametrize("clave", CLAVES)
def test_las_seis_series_dan_lo_medido(clave):
    assert _medido(clave) == pytest.approx(ESPERADO[clave], abs=10)


def test_el_muestreo_no_cambia_el_resultado(monkeypatch):
    """Un vóxel de cada 1, 8 y 27 dan lo mismo: el número es del volumen, no del muestreo."""
    v = DicomVolume(_requerir("IX_DIC")).volumen_hu
    base = desplazamiento_hu(v)
    for paso in (1, 3):
        monkeypatch.setattr(escala_mod, "PASO_DE_MUESTREO", paso)
        assert desplazamiento_hu(v) == pytest.approx(base, abs=10)


def _fantoma(cuerpo=0.0, forma=(30, 96, 96), seed=0, radio=40):
    """Aire (-1000) alrededor de un cilindro de un material de HU `cuerpo`, con un segundo material más denso."""
    rng = np.random.default_rng(seed)
    z, y, x = np.mgrid[: forma[0], : forma[1], : forma[2]]
    r = np.hypot(y - forma[1] / 2, x - forma[2] / 2)
    v = np.full(forma, -1000.0, np.float32)
    dentro = r < radio
    v[dentro] = rng.normal(cuerpo, 8.0, dentro.sum()).astype(np.float32)
    v[(r < 10) & (z < 8)] = rng.normal(cuerpo + 90, 8.0, ((r < 10) & (z < 8)).sum()).astype(np.float32)
    return v


def test_un_fantoma_calibrado_da_cerca_de_cero():
    assert abs(desplazamiento_hu(_fantoma(0.0))) <= 15


@pytest.mark.parametrize("corrimiento", [490.0, -410.0, 250.0])
def test_un_fantoma_corrido_da_su_corrimiento(corrimiento):
    assert desplazamiento_hu(_fantoma(corrimiento)) == pytest.approx(corrimiento, abs=15)


def test_los_voxeles_de_artefacto_no_lo_mueven():
    v = _fantoma(0.0)
    base = desplazamiento_hu(v)
    v.reshape(-1)[: int(v.size * 0.0003)] = 7000.0
    v.reshape(-1)[-int(v.size * 0.0003):] = 30000.0
    assert desplazamiento_hu(v) == pytest.approx(base, abs=10)


def test_el_relleno_de_aire_no_cuenta_como_fantoma():
    v = _fantoma(0.0)
    v[v < -900] = -3024.0                                   # otro valor de relleno: sigue siendo "no fantoma"
    assert abs(desplazamiento_hu(v)) <= 15


@pytest.mark.parametrize("volumen", [
    np.zeros((0, 4, 4), np.float32),                        # vacío
    np.full((20, 64, 64), -1000.0, np.float32),             # solo aire
    np.full((20, 64, 64), np.nan, np.float32),              # sin valores finitos
    np.full((3, 8, 8), 40.0, np.float32),                   # material, pero muy poco: no hay fantoma
])
def test_sin_fantoma_no_hay_numero(volumen):
    assert desplazamiento_hu(volumen) is None


def test_los_valores_no_finitos_no_entran_en_la_moda():
    v = _fantoma(0.0)
    base = desplazamiento_hu(v)
    v[0, :2, :] = np.nan
    v[1, :2, :] = np.inf
    v[2, :2, :] = -np.inf
    assert desplazamiento_hu(v) == pytest.approx(base, abs=10)


def test_una_imagen_2d_tambien_se_mide():
    corte = _fantoma(0.0, forma=(1, 256, 256), radio=100)[0]              # un corte real tiene decenas de miles de vóxeles de fantoma
    assert corte.ndim == 2 and abs(desplazamiento_hu(corte)) <= 15


def test_es_una_escala_no_calibrada_desde_el_umbral():
    assert es_escala_no_calibrada(475.0) and es_escala_no_calibrada(-410.0)
    assert es_escala_no_calibrada(UMBRAL_ESCALA_NO_CALIBRADA_HU)
    assert not es_escala_no_calibrada(UMBRAL_ESCALA_NO_CALIBRADA_HU - 1)
    assert not es_escala_no_calibrada(None)
    # el umbral queda claramente por encima de lo que dan los equipos calibrados del corpus (≤ 35) y por debajo del iX
    calibrados = [abs(ESPERADO[c]) for c in ESPERADO if c != "IX_DIC"]
    assert max(calibrados) * 2 < UMBRAL_ESCALA_NO_CALIBRADA_HU < ESPERADO["IX_DIC"] / 2


def test_la_nota_solo_sale_para_una_escala_no_calibrada_y_lleva_el_valor():
    assert nota_escala(15.0) is None and nota_escala(None) is None
    nota = nota_escala(475.0)
    assert NOTA_CLAVE in nota and "+475" in nota and "No se corrigen las imágenes" in nota
    assert not any(s in nota for s in SIMBOLOS_PROHIBIDOS)               # DA-18


# ---------------------------------------------------------------------------
# 2. EL VOLUMEN LO DECLARA EN SU ADQUISICIÓN
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clave", ["IX_DIC", "TOMOGRAFO", "HALCYON_SEP"])
def test_el_volumen_declara_el_corrimiento_en_su_adquisicion(clave):
    vol = DicomVolume(_requerir(clave))
    assert vol.desplazamiento_hu == pytest.approx(ESPERADO[clave], abs=10)
    assert vol.adquisicion["desplazamiento_hu"] == round(vol.desplazamiento_hu, 1)
    json.dumps(vol.adquisicion)                                            # se puede archivar


def test_lo_que_se_archiva_con_la_prueba_lleva_el_corrimiento():
    """El mapeador de A.1 serializa la adquisición COMPLETA: la clave nueva llega a `pruebas.adquisicion_dicom`."""
    adq = {**_adq_real("IX_DIC"), "desplazamiento_hu": 475.0}
    _equipo, _uid, _fecha, js = mapear_identidad_dicom(adq)
    assert json.loads(js)["desplazamiento_hu"] == 475.0


# ---------------------------------------------------------------------------
# 3. EL CATÁLOGO LO COMPARA
# ---------------------------------------------------------------------------

def _fila_escala(comparacion):
    return next((f for f in comparacion.filas if f.campo == "desplazamiento_hu"), None)


def test_el_ix_con_su_corrimiento_esperado_cumple_y_no_hay_desviacion():
    adq = {**_adq_real("IX_DIC"), "desplazamiento_hu": 475.0}
    c = comparar_con_protocolo("Clinac ix", adq)
    f = _fila_escala(c)
    assert f.cumple is True and (texto_exigido(f), texto_encontrado(f)) == ("+490 ± 30", "+475")
    assert c.desviacion_texto() is None


@pytest.mark.parametrize("equipo,clave,medido,cumple", [
    ("Clinac ix", "IX_DIC", 0.0, False),          # un mes que sale calibrado: otro preset (la sesión 30 dio -410)
    ("Clinac ix", "IX_DIC", -410.0, False),
    ("Tomógrafo", "TOMOGRAFO", 15.0, True),
    ("Tomógrafo", "TOMOGRAFO", 475.0, False),
    ("Halcyon", "HALCYON_SEP", 5.0, True),
    ("Halcyon", "HALCYON_SEP", -60.0, False),
])
def test_el_corrimiento_se_compara_con_el_esperado_de_cada_equipo(equipo, clave, medido, cumple):
    c = comparar_con_protocolo(equipo, {**_adq_real(clave), "desplazamiento_hu": medido})
    assert _fila_escala(c).cumple is cumple
    assert (c.desviacion_texto() is None) is cumple                        # el resto de la adquisición es conforme


def test_el_corrimiento_fuera_de_lo_esperado_entra_en_la_desviacion_archivada():
    c = comparar_con_protocolo("Clinac ix", {**_adq_real("IX_DIC"), "desplazamiento_hu": -410.0})
    texto = c.desviacion_texto()
    assert "Corrimiento de escala de HU [HU]: -410 (exigido +490 ± 30)" in texto


def test_sin_la_medicion_la_comparacion_de_encabezados_no_cambia():
    """Una comparación hecha solo con encabezados (o un control anterior) no tiene la medición: no hay fila ni se le
    cobra un 'no cumple'."""
    for clave, equipo in (("IX_DIC", "Clinac ix"), ("TOMOGRAFO", "Tomógrafo"), ("HALCYON_SEP", "Halcyon")):
        c = comparar_con_protocolo(equipo, _adq_real(clave))
        assert _fila_escala(c) is None and c.desviacion_texto() is None


def test_una_medicion_que_no_se_pudo_hacer_no_se_le_cobra_al_fisico():
    c = comparar_con_protocolo("Clinac ix", {**_adq_real("IX_DIC"), "desplazamiento_hu": None})
    f = _fila_escala(c)
    assert f.cumple is None and texto_encontrado(f) == "no se pudo medir"
    assert f not in c.fuera_de_protocolo and c.desviacion_texto() is None


def test_el_catalogo_fija_lo_esperado_de_cada_equipo():
    assert {e: p.corrimiento_hu_esperado for e, p in PROTOCOLOS.items()} == {
        "Tomógrafo": 0.0, "Halcyon": 0.0, "Clinac ix": 490.0}
    assert all(p.corrimiento_hu_tolerancia == 30.0 for p in PROTOCOLOS.values())


# ---------------------------------------------------------------------------
# 4. LA VENTANA DE LA CARGA
# ---------------------------------------------------------------------------

def _vol_de(clave, medido="__omitir__"):
    adq = dict(_adq_real(clave))
    if medido != "__omitir__":
        adq["desplazamiento_hu"] = medido
    return types.SimpleNamespace(adquisicion=adq, series_descartadas={}, detalle_series_descartadas={},
                                 no_imagen=0, avisos=[])


def _textos_carpeta(modelo):
    return [t for _nivel, t in modelo.carpeta]


def test_la_ventana_del_ix_muestra_el_corrimiento_y_dice_que_no_son_hu_calibrados():
    m = construir_modelo_ventana(_vol_de("IX_DIC", 475.0), "Clinac ix")
    assert (ETIQUETA, "+475") in m.adquisicion
    assert any(NOTA_CLAVE in t for t in _textos_carpeta(m))
    fila = next(f for f in m.protocolo if f.etiqueta == "Corrimiento de escala de HU [HU]")
    assert (fila.exigido, fila.encontrado, fila.estado) == ("+490 ± 30", "+475", CUMPLE)
    assert not m.requiere_confirmacion


def test_un_ix_que_sale_calibrado_pide_confirmar_porque_es_otro_preset():
    m = construir_modelo_ventana(_vol_de("IX_DIC", 0.0), "Clinac ix")
    fila = next(f for f in m.protocolo if f.etiqueta == "Corrimiento de escala de HU [HU]")
    assert fila.estado == NO_CUMPLE and m.requiere_confirmacion
    assert not any(NOTA_CLAVE in t for t in _textos_carpeta(m))            # +0: sus unidades sí son HU calibrados


def test_la_ventana_del_tomografo_muestra_el_corrimiento_sin_nota():
    m = construir_modelo_ventana(_vol_de("TOMOGRAFO", 15.0), "Tomógrafo")
    assert (ETIQUETA, "+15") in m.adquisicion
    assert not any(NOTA_CLAVE in t for t in _textos_carpeta(m))
    assert not m.requiere_confirmacion


def test_una_ventana_sin_la_medicion_no_muestra_la_fila_ni_la_nota():
    m = construir_modelo_ventana(_vol_de("IX_DIC"), "Clinac ix")
    assert all(e != ETIQUETA for e, _ in m.adquisicion)
    assert not any(NOTA_CLAVE in t for t in _textos_carpeta(m))


def test_una_medicion_que_fallo_se_dice():
    m = construir_modelo_ventana(_vol_de("IX_DIC", None), "Clinac ix")
    assert (ETIQUETA, "no se pudo medir") in m.adquisicion


def test_la_ventana_real_con_una_carpeta_real_trae_lo_medido():
    vol = DicomVolume(_requerir("IX_DIC"))
    m = construir_modelo_ventana(vol, "Clinac ix")
    valor = dict(m.adquisicion)[ETIQUETA]
    assert valor == f"{vol.adquisicion['desplazamiento_hu']:+.0f}"
    assert any(NOTA_CLAVE in t for t in _textos_carpeta(m)) and not m.requiere_confirmacion


# ---------------------------------------------------------------------------
# 5. EL PDF (E.2)
# ---------------------------------------------------------------------------

def _archivar(bd, ref, adq, equipo):
    desviacion = comparar_con_protocolo(equipo, adq).desviacion_texto()
    equipo_dicom, serie_uid, fecha, js = mapear_identidad_dicom(adq)
    con = sqlite3.connect(bd)
    n = con.execute(
        "UPDATE pruebas SET equipo_dicom=?, serie_uid=?, fecha_adquisicion=?, adquisicion_dicom=?, "
        "desviacion_protocolo=?, kv=?, ma=?, espesor_corte=? WHERE id_sesion=? AND (activo IS NULL OR activo=1)",
        [equipo_dicom, serie_uid, fecha, js, desviacion, adq.get("kv"), adq.get("ma"), adq.get("espesor_mm"),
         ref]).rowcount
    con.commit()
    con.close()
    assert n > 0


def _pdf(app, avisos, bd_copia, monkeypatch, sesion):
    ref, equipo, fecha = sesion
    ok, visor = generar(bd_copia, monkeypatch, ref, equipo, fecha, True)
    assert ok is True and avisos == [], f"la generación falló: {avisos}"
    return re.sub(r"\s+", " ", "\n".join(paginas(visor["pdf"])))


def test_el_pdf_del_ix_dice_el_corrimiento_y_declara_que_no_son_hu_calibrados(app, avisos, bd_copia, monkeypatch):
    _archivar(bd_copia, 30, {**_adq_real("IX_DIC"), "desplazamiento_hu": 475.0}, "Clinac ix")
    texto = _pdf(app, avisos, bd_copia, monkeypatch, SESION_30)
    assert ETIQUETA in texto and "+475" in texto
    assert "Escala de HU" in texto and NOTA_CLAVE in texto
    assert texto.count(NOTA_CLAVE) == 1


def test_el_pdf_del_tomografo_dice_el_corrimiento_sin_nota(app, avisos, bd_copia, monkeypatch):
    _archivar(bd_copia, 42, {**_adq_real("TOMOGRAFO"), "desplazamiento_hu": 15.0}, "Tomógrafo")
    texto = _pdf(app, avisos, bd_copia, monkeypatch, SESION_42)
    assert ETIQUETA in texto and "+15" in texto
    assert NOTA_CLAVE not in texto and "Escala de HU" not in texto


def test_un_control_con_metadata_pero_sin_medicion_dice_que_no_la_registro(app, avisos, bd_copia, monkeypatch):
    """Guardado entre A.1 y B.3: tiene identidad DICOM pero no el corrimiento. Se dice, no se inventa ni se mide de
    nuevo (§12.4: lo archivado no se recalcula)."""
    _archivar(bd_copia, 42, _adq_real("TOMOGRAFO"), "Tomógrafo")
    texto = _pdf(app, avisos, bd_copia, monkeypatch, SESION_42)
    assert ETIQUETA in texto and ESCALA_NO_REGISTRADA in texto and NOTA_CLAVE not in texto


def test_un_control_anterior_a_A1_no_lleva_la_fila_del_corrimiento(app, avisos, bd_copia, monkeypatch):
    texto = _pdf(app, avisos, bd_copia, monkeypatch, SESION_42)
    assert ETIQUETA not in texto and NOTA_CLAVE not in texto


def test_la_medicion_que_fallo_se_dice_en_el_pdf(app, avisos, bd_copia, monkeypatch):
    _archivar(bd_copia, 42, {**_adq_real("TOMOGRAFO"), "desplazamiento_hu": None}, "Tomógrafo")
    texto = _pdf(app, avisos, bd_copia, monkeypatch, SESION_42)
    assert ETIQUETA in texto and "no se pudo medir" in texto


def test_la_pieza_del_pdf_y_de_la_ventana_dicen_lo_mismo():
    """`filas_medidas` es la única que escribe el valor: la ventana y el PDF no pueden discrepar."""
    assert filas_medidas({"desplazamiento_hu": 475.0}) == [(ETIQUETA, "+475")]
    assert filas_medidas({"desplazamiento_hu": -35.4}) == [(ETIQUETA, "-35")]
    assert filas_medidas({"desplazamiento_hu": None}) == [(ETIQUETA, "no se pudo medir")]
    assert filas_medidas({}) == []
    assert filas_medidas({}, ESCALA_NO_REGISTRADA) == [(ETIQUETA, ESCALA_NO_REGISTRADA)]


# ---------------------------------------------------------------------------
# 6. ESTRUCTURA
# ---------------------------------------------------------------------------

def _linea_de_llamada(func, nombre):
    lineas = [n.lineno for n in ast.walk(func) if isinstance(n, ast.Call)
              and getattr(n.func, "attr", getattr(n.func, "id", None)) == nombre]
    return min(lineas) if lineas else None


def test_la_escala_se_mide_despues_de_cargar_el_volumen():
    arbol = ast.parse((RAIZ / "data/ManejoDatos/catphan_TAC/leer_dicom.py").read_text(encoding="utf-8"))
    (f,) = [n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "_load_dicoms"]
    medir = _linea_de_llamada(f, "_medir_escala_de_hu")
    assert medir is not None
    for antes in ("_load_standard_volume", "_load_large_volume"):
        assert _linea_de_llamada(f, antes) < medir, antes


def _fuentes_de_produccion():
    for carpeta in ("ui", "data", "models", "services", "analisisImagenes"):
        yield from (RAIZ / carpeta).rglob("*.py")


def test_la_etiqueta_y_la_nota_se_escriben_en_un_solo_archivo():
    donde_etiqueta = {str(p.relative_to(RAIZ)) for p in _fuentes_de_produccion() if ETIQUETA in p.read_text(encoding="utf-8")}
    donde_nota = {str(p.relative_to(RAIZ)) for p in _fuentes_de_produccion() if NOTA_CLAVE in p.read_text(encoding="utf-8")}
    assert donde_etiqueta == {"analisisImagenes/catphan/descripcion.py"}, donde_etiqueta
    assert donde_nota == {"analisisImagenes/catphan/escala.py"}, donde_nota


def test_el_corrimiento_no_se_le_resta_al_volumen():
    """B.3 declara, no corrige: ningún archivo de producción modifica `volumen_hu` con el corrimiento medido."""
    for ruta in _fuentes_de_produccion():
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if isinstance(n, ast.AugAssign):
                destinos, valor = [n.target], n.value
            elif isinstance(n, ast.Assign):
                destinos, valor = n.targets, n.value
            else:
                continue
            escribe_el_volumen = any("volumen_hu" in ast.unparse(d) for d in destinos)
            assert not (escribe_el_volumen and "desplazamiento" in ast.unparse(valor)), (str(ruta), ast.unparse(n))
