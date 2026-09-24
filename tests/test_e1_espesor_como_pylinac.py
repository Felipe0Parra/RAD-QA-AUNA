"""E.1 (PLAN_ESPESOR_CORTE_24-09.md): el espesor de corte de la app se mide como pylinac.

Cada aserción está respaldada por una medición del diagnóstico del planificador (DIAGNOSTICO_ESPESOR.md).

CAUSA [medido]: `espesor_corte` tomaba la media altura contra el 0 que la máscara ponía fuera de la
ROI (umbral = pico/2 en vez de (pico + fondo)/2) y medía un solo corte: 2.82 mm en el tomógrafo
(pylinac 1.92), 3.15-3.21 en el Halcyon (1.82-1.86), 11.66 en el iX (2.34), y en un corte sin
alambre saturaba en "ROI entera" (17.48 archivado del Halcyon).

Qué garantiza cada prueba:
  (a) igual a pylinac (±0.02 mm; medido ±0.005) en el corte CTP404 de las 5 series reales;
  (b) no depende de la ventana (CONTROL: la función vieja ya era invariante -- pasa también en rojo);
  (c) por el camino de la pantalla: `DicomVolume` + índice de `slice_matcher` + `cortes_vecinos_espesor`;
  (d) fantoma sintético de espesor conocido (2.0 / 2.5 con cupping / 5.0 mm);
  (e) un corte sin alambre NO da número (antes: 17-20 mm; sin la guarda: 2.02 mm plausible);
  (f) la guarda no toca el corte de pylinac ni sus vecinos;
  (g) la regla de vecinos (nominal < 3.5 mm, extremos del volumen);
  (h) combinar cortes no trunca HU (antes: `.astype(np.uint8)`);
  (i) censo derivado del código: toda llamada de producción a `espesor_corte` pasa los vecinos.
"""
import ast
import functools
import os
import types
import warnings
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from scipy.special import erf

from _catphan_oro import ESPESOR_MM, LIMITE_HOMOGENEIDAD_IX
from _corpus import serie_catphan
from analisisImagenes.catphan import motor
from analisisImagenes.catphan.serie import leer_serie

CLAVES = ("TOMOGRAFO", "HALCYON_SEP", "HALCYON_JUN", "HALCYON_236", "IX_DIC")
_LIMITE = {"TOMOGRAFO": None, "HALCYON_SEP": None, "HALCYON_JUN": None, "HALCYON_236": None,
           "IX_DIC": LIMITE_HOMOGENEIDAD_IX}
TOL_PYLINAC_MM = 0.02          # medido: 0.005 (incluye el redondeo a 2 decimales del resultado)
TOL_VECINOS_MM = 0.15          # medido en los cortes +-1: peor caso iX -1, 2.20 frente a 2.336
VENTANAS = ((40, 400), (500, 2000), (-200, 100))
_RAIZ_CODIGO = Path(__file__).resolve().parent.parent


def _ventanear(hu, wl, ww):
    lo, hi = wl - ww / 2, wl + ww / 2
    return ((np.clip(hu, lo, hi) - lo) / (hi - lo) * 255).astype(np.uint8)


def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"serie {clave} no disponible")
    return ruta


@functools.lru_cache(maxsize=None)
def _ct(clave):
    """Objeto pylinac analizado (volteado si la serie está invertida), como `motor.analizar`."""
    ruta = _requerir(clave)
    serie = leer_serie(ruta)
    perfil = types.SimpleNamespace(limite_variacion_hu=_LIMITE[clave], nombre=clave)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resultado = motor.analizar(serie, perfil)
        ct = motor._construir([c.ruta for c in serie.cortes], _LIMITE[clave])
        if resultado.orientacion == "invertido":
            motor._voltear_volumen(ct)
        motor._analizar_una_vez(ct, None, {})
    return ct


def _corte(ct, desplazamiento=0):
    i = int(ct.ctp404.slice_num) + desplazamiento
    return np.asarray(ct.dicom_stack[i].array, dtype=np.float32)


def _px(ct):
    return float(ct.dicom_stack[int(ct.ctp404.slice_num)].dpmm) ** -1


def _medir(hu, vecinos, px, ventana=(40, 400)):
    from analisisImagenes.Analisis_Catphan_TAC import espesor_corte
    return espesor_corte(_ventanear(hu, *ventana), hu, px, visualizar=False,
                         combinar_slices=bool(vecinos), slices_adyacentes=vecinos)


# --------------------------------------------------------------------------------------------------
# Fantoma sintético (copia de scratchpad/espesor/sintetico.py): disco de 100 mm, 4 rampas de 23° a
# 38 mm, SSP = rect(T) (x) gauss, desenfoque en el plano, ruido. Verdad = FWHM del SSP.
# --------------------------------------------------------------------------------------------------
_TAN23 = float(np.tan(np.deg2rad(23.0)))
_K = 1.0 / (2.0 * np.sqrt(2.0 * np.log(2.0)))
_RAMPAS_SINT = {"Izquierda": (180.0, -1), "Abajo": (90.0, -1), "Derecha": (0.0, +1), "Arriba": (-90.0, +1)}


def _sintetico(z0, *, px, T, fwhm_z, lsf_fwhm, B0, C, A, ruido, seed, n=512):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    X = (xx - ((n - 1) / 2 + 3.0 / px)) * px
    Y = (yy - ((n - 1) / 2 - 2.0 / px)) * px
    r = np.hypot(X, Y)
    img = np.where(r <= 100.0, B0 + C * (r / 100.0) ** 2, -1000.0)
    sL = np.sqrt((lsf_fwhm * _K) ** 2 + px ** 2 / 12.0)
    s_al = np.sqrt((fwhm_z * _K / _TAN23) ** 2 + sL ** 2)
    W = T / _TAN23
    for (nombre, (ang, sgn)), zc in zip(_RAMPAS_SINT.items(), (0.3, -0.4, 0.2, -0.1)):
        a = np.deg2rad(ang)
        cx, cy = 38.0 * np.cos(a), 38.0 * np.sin(a)
        base = np.deg2rad(90.0 if nombre in ("Izquierda", "Derecha") else 0.0)
        ux, uy = np.cos(base), np.sin(base)
        s = (X - cx) * ux + (Y - cy) * uy
        t = -(X - cx) * uy + (Y - cy) * ux
        sc = sgn * (z0 - zc) / _TAN23
        g = 0.5 * (erf((s - sc + W / 2) / (np.sqrt(2) * s_al)) - erf((s - sc - W / 2) / (np.sqrt(2) * s_al)))
        g = np.where(np.abs(s) <= 30.0, g, 0.0)
        img = img + A * g * np.exp(-t ** 2 / (2 * sL ** 2))
    return (img + rng.normal(0.0, ruido, img.shape)).astype(np.float32)


_TOMO = dict(px=1.0742, T=2.0, fwhm_z=0.6, lsf_fwhm=1.66, B0=100.0, C=0.0, A=230.0, ruido=6.0)
_IX = dict(px=0.651, T=2.5, fwhm_z=0.6, lsf_fwhm=1.2, B0=536.0, C=-754.0, A=330.0, ruido=17.0)
_GRUESO = dict(px=1.0742, T=5.0, fwhm_z=0.6, lsf_fwhm=1.66, B0=100.0, C=0.0, A=230.0, ruido=6.0)


def _volumen_sintetico(p, z0=0.1, seed=1):
    return np.stack([_sintetico(z0 + k * p["T"], seed=seed + k + 1, **p) for k in (-1, 0, 1)])


# --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("clave", CLAVES)
def test_a_igual_a_pylinac_en_el_corte_de_pylinac(clave):
    ct = _ct(clave)
    r = _medir(_corte(ct), [_corte(ct, -1), _corte(ct, 1)], _px(ct))
    assert r["num_rampas_detectadas"] == 4 and r["combinacion_slices"] is True
    assert abs(r["espesor_promedio_mm"] - float(ct.ctp404.meas_slice_thickness)) <= TOL_PYLINAC_MM, r
    assert abs(r["espesor_promedio_mm"] - ESPESOR_MM[clave][0]) <= TOL_PYLINAC_MM, r


@pytest.mark.parametrize("clave", CLAVES)
def test_b_no_depende_de_la_ventana(clave):
    """CONTROL (la vieja ya medía sobre HU): pasa también en el rojo, y debe seguir pasando."""
    ct = _ct(clave)
    hu, vec, px = _corte(ct), [_corte(ct, -1), _corte(ct, 1)], _px(ct)
    valores = {_medir(hu, vec, px, v)["espesor_promedio_mm"] for v in VENTANAS}
    assert len(valores) == 1, valores


@pytest.mark.parametrize("clave", ["TOMOGRAFO", "HALCYON_SEP"])
def test_c_por_el_camino_de_la_pantalla(clave):
    """El volumen que carga la pantalla (`DicomVolume`, sin voltear), el índice que le da
    `slice_matcher` (ya traducido al marco sin voltear en la serie invertida) y la regla de vecinos
    de producción: el número es el de pylinac. Discrimina el orden de cortes (A.1) y el marco (D.1)."""
    from analisisImagenes.Analisis_Catphan_TAC import cortes_vecinos_espesor, espesor_corte
    from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume
    from data.ManejoDatos.catphan_TAC.slice_matcher import detectar_modulos_pylinac
    ruta = _requerir(clave)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        idx = detectar_modulos_pylinac(ruta)["CTP404"].idx_corte
        vol = DicomVolume(ruta)
    hu = vol.volumen_hu[idx]
    vecinos = cortes_vecinos_espesor(vol.volumen_hu, idx, vol.espesor_corte)
    assert len(vecinos) == 2
    r = espesor_corte(_ventanear(hu, 40, 400), hu, float(vol.get_pixel_spacing()[0]), visualizar=False,
                      combinar_slices=True, slices_adyacentes=vecinos)
    assert abs(r["espesor_promedio_mm"] - ESPESOR_MM[clave][0]) <= TOL_PYLINAC_MM, r


@pytest.mark.parametrize("p, verdad, tol", [(_TOMO, 2.0, 0.10), (_IX, 2.5, 0.15), (_GRUESO, 5.0, 0.15)],
                         ids=["tomografo_2mm", "iX_fondo_536_cupping", "grueso_5mm_sin_vecinos"])
def test_d_sintetico_de_espesor_conocido(p, verdad, tol):
    """Medido: 1.96 / 2.41 / 4.93 (la vieja: 2.84 / 11.55 / 5.65)."""
    from analisisImagenes.Analisis_Catphan_TAC import cortes_vecinos_espesor
    vol = _volumen_sintetico(p)
    vecinos = cortes_vecinos_espesor(vol, 1, p["T"])
    assert len(vecinos) == (2 if p["T"] < 3.5 else 0)
    r = _medir(vol[1], vecinos, p["px"])
    assert r["espesor_promedio_mm"] is not None and abs(r["espesor_promedio_mm"] - verdad) <= tol, r


def test_e_un_corte_sin_alambre_no_da_numero():
    """Real: el tomógrafo a 6 cortes del CTP404 (la vieja: 19.83). Sintético: z = 40 mm."""
    ct = _ct("TOMOGRAFO")
    r = _medir(_corte(ct, 6), [_corte(ct, 5), _corte(ct, 7)], _px(ct))
    assert r["espesor_promedio_mm"] is None and r["num_rampas_detectadas"] < 3, r
    lejos = _sintetico(40.0, seed=900, **_TOMO)
    r = _medir(lejos, None, _TOMO["px"])
    assert r["espesor_promedio_mm"] is None and r["num_rampas_detectadas"] < 3, r


@pytest.mark.parametrize("clave", CLAVES)
@pytest.mark.parametrize("desplazamiento", [-1, 0, 1])
def test_f_la_guarda_no_toca_el_corte_de_pylinac_ni_sus_vecinos(clave, desplazamiento):
    ct = _ct(clave)
    r = _medir(_corte(ct, desplazamiento), [_corte(ct, desplazamiento - 1), _corte(ct, desplazamiento + 1)], _px(ct))
    assert r["num_rampas_detectadas"] == 4, r
    assert abs(r["espesor_promedio_mm"] - ESPESOR_MM[clave][0]) <= TOL_VECINOS_MM, r


def test_g_regla_de_vecinos():
    from analisisImagenes.Analisis_Catphan_TAC import cortes_vecinos_espesor
    vol = np.arange(5 * 4 * 4, dtype=np.float32).reshape(5, 4, 4)
    v = cortes_vecinos_espesor(vol, 2, 2.0)
    assert len(v) == 2 and np.array_equal(v[0], vol[1]) and np.array_equal(v[1], vol[3])
    for nominal in (3.5, 5.0, None, 0.0, "no-numero"):
        assert cortes_vecinos_espesor(vol, 2, nominal) == [], nominal
    assert cortes_vecinos_espesor(vol, 0, 2.0) == [] and cortes_vecinos_espesor(vol, 4, 2.0) == []
    assert cortes_vecinos_espesor(None, 2, 2.0) == [] and cortes_vecinos_espesor(vol, None, 2.0) == []


def test_h_combinar_cortes_no_trunca_los_hu():
    """Sumar +1000 HU a los tres cortes no cambia nada (antes: la media se pasaba a uint8)."""
    vol = _volumen_sintetico(_TOMO)
    a = _medir(vol[1], [vol[0], vol[2]], _TOMO["px"])["espesor_promedio_mm"]
    b = _medir(vol[1] + 1000.0, [vol[0] + 1000.0, vol[2] + 1000.0], _TOMO["px"])["espesor_promedio_mm"]
    assert a is not None and a == b


def _llamadas_de_produccion(nombre):
    excluir = {"tests", ".venv", "build", "dist", "__pycache__", ".git"}
    for ruta in _RAIZ_CODIGO.rglob("*.py"):
        if any(p in excluir for p in ruta.relative_to(_RAIZ_CODIGO).parts):
            continue
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", getattr(nodo.func, "attr", None)) == nombre:
                yield str(ruta.relative_to(_RAIZ_CODIGO)), nodo


def test_i_toda_llamada_de_produccion_pasa_los_vecinos():
    """Censo derivado del código, no del arreglo: si aparece una llamada nueva a `espesor_corte`
    que mida un solo corte, sale aquí."""
    llamadas = list(_llamadas_de_produccion("espesor_corte"))
    assert llamadas, "el censo no encontró ninguna llamada (ya no es una prueba)"
    for rel, nodo in llamadas:
        claves = {k.arg for k in nodo.keywords}
        assert {"slices_adyacentes", "combinar_slices"} <= claves, (rel, nodo.lineno)


def test_j_con_cortes_solapados_no_da_la_mitad_del_espesor():
    """Reconstrucción cada T/2 (3 mm cada 1.5 mm): la regla de pylinac (un vecino a cada lado) daría 1.49 de
    3.00. La guarda lo convierte en "rampas no detectadas" en vez de un número que pasaría por bueno."""
    from analisisImagenes.Analisis_Catphan_TAC import cortes_vecinos_espesor
    p = dict(_GRUESO, T=3.0)
    vol = np.stack([_sintetico(0.1 + k * 1.5, seed=50 + k, **p) for k in (-1, 0, 1)])
    vecinos = cortes_vecinos_espesor(vol, 1, 3.0)
    assert len(vecinos) == 2
    r = _medir(vol[1], vecinos, p["px"])
    assert r["espesor_promedio_mm"] is None, r


def _rama_espesor_de_la_pantalla():
    """El árbol de la rama `categoria == 'espesor'` de `imagen_dicom_cargada` (la pantalla)."""
    ruta = _RAIZ_CODIGO / "ui" / "paginasControles" / "PruebasMensuales" / "tac_mensual.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    for func in ast.walk(arbol):
        if isinstance(func, ast.FunctionDef) and func.name == "imagen_dicom_cargada":
            for nodo in ast.walk(func):
                if (isinstance(nodo, ast.If) and isinstance(nodo.test, ast.Compare)
                        and isinstance(nodo.test.left, ast.Name) and nodo.test.left.id == "categoria"
                        and any(isinstance(c, ast.Constant) and c.value == "espesor" for c in nodo.test.comparators)):
                    return nodo
    raise AssertionError("no se encontró la rama 'espesor' de imagen_dicom_cargada")


def test_k_la_pantalla_pide_los_vecinos_a_la_regla_de_produccion():
    """Sin esto la pantalla mediría un solo corte (+0.1 a +0.7 mm) sin que nada avise: el vecino sale de
    `cortes_vecinos_espesor` y `espesor_corte` los recibe."""
    rama = _rama_espesor_de_la_pantalla()
    llamadas = [n for n in ast.walk(rama) if isinstance(n, ast.Call)
                and getattr(n.func, "id", getattr(n.func, "attr", None)) in ("espesor_corte", "cortes_vecinos_espesor")]
    nombres = {getattr(n.func, "id", getattr(n.func, "attr", None)) for n in llamadas}
    assert nombres == {"espesor_corte", "cortes_vecinos_espesor"}, nombres
    medir = next(n for n in llamadas if getattr(n.func, "id", None) == "espesor_corte")
    kw = {k.arg: k.value for k in medir.keywords}
    assert isinstance(kw["slices_adyacentes"], ast.Name), "los vecinos deben venir de una variable, no de un literal"


def test_l_sin_rampas_la_pantalla_no_guarda_ni_juzga():
    """Un corte sin alambre no da número: la rama anula el resultado y sigue con la siguiente categoría."""
    rama = _rama_espesor_de_la_pantalla()
    guardas = [n for n in ast.walk(rama) if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
               and any(isinstance(c, ast.Constant) and c.value is None for c in n.test.comparators)
               and any(isinstance(m, ast.Call) and getattr(m.func, "attr", None) == "get"
                       and m.args and getattr(m.args[0], "value", None) == "espesor_promedio_mm"
                       for m in ast.walk(n.test))]
    assert guardas, "la rama no comprueba el espesor None"
    cuerpo = ast.dump(ast.Module(body=guardas[0].body, type_ignores=[]))
    assert "resultados_espesor" in cuerpo and "Continue" in cuerpo


@pytest.mark.parametrize("z0", [4.0, 4.25, 4.5])
def test_m_con_el_alambre_en_el_borde_de_la_roi_no_da_numero(z0):
    """El alambre se acerca al extremo de la ROI: el ancho a media altura queda cortado (sin la guarda de margen
    daría 1.94 -> 1.88 mm, un número que parece bueno) y solo una o dos rampas siguen siendo medibles (sin el
    mínimo de rampas, una sola daría 1.96-1.98). La función debe decir "no detectadas"."""
    from analisisImagenes.Analisis_Catphan_TAC import cortes_vecinos_espesor
    vol = np.stack([_sintetico(z0 + k * _TOMO["T"], seed=7 + k, **_TOMO) for k in (-1, 0, 1)])
    r = _medir(vol[1], cortes_vecinos_espesor(vol, 1, _TOMO["T"]), _TOMO["px"])
    assert r["espesor_promedio_mm"] is None and r["num_rampas_detectadas"] < 3, r


def test_n_la_guarda_no_toca_un_alambre_bien_dentro_de_la_roi():
    """El mismo fantoma con el alambre a 3 mm del centro de la rampa: las cuatro rampas cuentan."""
    from analisisImagenes.Analisis_Catphan_TAC import cortes_vecinos_espesor
    vol = np.stack([_sintetico(3.0 + k * _TOMO["T"], seed=7 + k, **_TOMO) for k in (-1, 0, 1)])
    r = _medir(vol[1], cortes_vecinos_espesor(vol, 1, _TOMO["T"]), _TOMO["px"])
    assert r["num_rampas_detectadas"] == 4 and abs(r["espesor_promedio_mm"] - 1.95) <= 0.05, r

