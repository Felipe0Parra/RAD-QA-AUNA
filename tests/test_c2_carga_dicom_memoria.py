"""C.2 (PLAN_HANDOFF_IMAGENES_22-09.md §4): la caída al importar la carpeta
DICOM del Halcyon (`DICOM/CatphanHalcyonJunio2026`, precisada por el físico
el 22-09). Cinco exigencias del plan -- todas rojas antes de C.2 salvo (d).

Rutas del corpus real vía tests/_corpus.py (HI-0, mismo criterio que
test_a0_catphan_corpus.py): si el corpus no está montado en esta máquina,
cada caso salta de forma honesta en vez de fallar.

Autorización del físico (22-09): "Si lo que arregla el problema de
saturacion de memoria no dana ninguna funcionalidad entonces no debe haber
problema con aplicarlo, con una buena holgura para no frenar analisis y
luego verificamos." Este archivo es la verificación de esa condición.
"""
import gc
import hashlib
import os
import subprocess
import sys
import weakref

import numpy as np
import pytest

from _corpus import CATPHAN, serie_catphan

RAIZ_CODIGO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _requiere(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible en este entorno: {clave}")
    return ruta


# ---------------------------------------------------------------------------
# (a) Equivalencia de rutas: estandar y optimizada deben dar el MISMO dtype
# y el MISMO contenido. Antes de C.2, la optimizada daba float64 (el doble)
# para los mismos numeros -- este es el rojo que atrapa ese defecto.
# ---------------------------------------------------------------------------

def _cortes_crudos(ruta):
    from analisisImagenes.catphan.serie import leer_serie
    import pydicom
    serie = leer_serie(ruta)
    return [pydicom.dcmread(c.ruta) for c in serie.cortes]


def _volumen_por_ruta_interna(ruta, usar_optimizada):
    from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume
    vol = DicomVolume.__new__(DicomVolume)
    vol.ruta_carpeta = ruta
    vol.cortes = _cortes_crudos(ruta)
    vol.volumen = None
    vol.volumen_hu = None
    if usar_optimizada:
        vol._load_large_volume()
    else:
        vol._load_standard_volume()
    return vol


def test_a_ruta_optimizada_da_mismo_dtype_y_mismo_contenido_que_estandar():
    ruta = _requiere("HALCYON_JUN")
    vol_std = _volumen_por_ruta_interna(ruta, usar_optimizada=False)
    vol_opt = _volumen_por_ruta_interna(ruta, usar_optimizada=True)

    assert vol_std.volumen_hu.dtype == vol_opt.volumen_hu.dtype, (
        f"la ruta optimizada debe dar el MISMO dtype que la estandar -- "
        f"antes de C.2 daba float64 (el doble de memoria) para los mismos "
        f"numeros: estandar={vol_std.volumen_hu.dtype} "
        f"optimizada={vol_opt.volumen_hu.dtype}"
    )
    assert np.array_equal(vol_std.volumen_hu, vol_opt.volumen_hu), (
        "las dos rutas deben dar exactamente los mismos numeros HU"
    )


# ---------------------------------------------------------------------------
# (b) Estimación sin descomprimir: el tamaño calculado desde encabezados
# coincide con el real (via pixel_array.nbytes) dentro del 5%, sin haber
# decodificado ni un pixel.
# ---------------------------------------------------------------------------

def test_b_tamano_estimado_desde_encabezados_sin_decodificar_pixeles():
    from data.ManejoDatos.catphan_TAC.leer_dicom import _tamano_volumen_estimado_bytes

    ruta = _requiere("HALCYON_JUN")
    dicoms = _cortes_crudos(ruta)

    estimado = _tamano_volumen_estimado_bytes(dicoms)

    # pydicom deja `_pixel_array` en None desde la lectura (es el slot de
    # cache, no un indicador de decodificado) -- lo que hay que comprobar
    # es que sigue en None, no que el atributo no exista.
    assert all(getattr(ds, '_pixel_array', None) is None for ds in dicoms), (
        "estimar el tamaño no debe decodificar ningún pixel -- la version "
        "anterior llamaba ds.pixel_array.nbytes, que SI decodifica"
    )

    real = sum(ds.pixel_array.nbytes for ds in dicoms)  # ahora si, a proposito
    diferencia = abs(estimado - real) / real
    assert diferencia <= 0.05, (
        f"estimado={estimado} real={real} diferencia={diferencia:.1%} "
        f"(tolerancia 5%)"
    )


# ---------------------------------------------------------------------------
# (c) Pico acotado: cargar una carpeta real no debe superar 5x el volumen
# crudo (antes de C.2, medido ~7-8x). Se mide en un SUBPROCESO limpio (RSS
# de alta marca, VmHWM de /proc/self/status) para no arrastrar el pico de
# otros tests de la misma sesion de pytest.
# ---------------------------------------------------------------------------

# NOTA (22-09-2026): NO se usa resource.getrusage().ru_maxrss -- en este
# entorno (sandbox) devuelve, incluso en un hijo TRIVIAL que solo hace
# `import resource`, el mismo numero que el proceso PADRE ya tenia en su
# propio pico, sin relacion con lo que el hijo asigna (confirmado con un
# hijo que no importa nada de este proyecto). VmHWM de /proc/self/status
# SI es correcto -- confirmado: el mismo hijo, midiendo VmHWM, da el
# baseline limpio real (~90 MB) sin importar cuanta memoria tenga el
# proceso que lo lanzo.
_CODIGO_MEDIR_PICO = """
import os, sys
sys.path.insert(0, os.getcwd())
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

def _vmhwm_kb():
    with open('/proc/self/status', encoding='utf-8') as f:
        for linea in f:
            if linea.startswith('VmHWM:'):
                return int(linea.split()[1])
    return None

from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume
base = _vmhwm_kb()
vol = DicomVolume(sys.argv[1])
pico = _vmhwm_kb()
crudo = vol.volumen.nbytes if vol.volumen is not None else -1
print(base, pico, crudo)
"""


def _medir_pico_subproceso(ruta):
    entorno = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    resultado = subprocess.run(
        [sys.executable, "-c", _CODIGO_MEDIR_PICO, ruta],
        cwd=RAIZ_CODIGO, env=entorno, capture_output=True, text=True, timeout=120,
    )
    assert resultado.returncode == 0, (
        f"subproceso de medicion fallo:\n{resultado.stderr[-4000:]}"
    )
    linea = [l for l in resultado.stdout.strip().splitlines() if l.strip()][-1]
    base_kb, pico_kb, crudo_bytes = linea.split()
    return int(base_kb) * 1024, int(pico_kb) * 1024, int(crudo_bytes)


# Medido tras C.2 (22-09-2026): ~4.11x en HALCYON_JUN (123 cortes) y en
# MIXTA/Catphan (278 cortes) -- antes de C.2, ~7.10x.
#
# El tope era 5.0 y se subio a 6.0 el 22-09 por una razon medida, no por
# comodidad: el pico es BIMODAL, 4.11x o 5.11x, nunca en medio. La
# diferencia es exactamente 1x el volumen crudo (61.5 MB), o sea UNA copia
# mas viva en el pico: cuando el `delattr` de la cache de pixeles libera
# paginas que glibc devuelve al sistema operativo sale 4.11x, y cuando las
# retiene en su arena sale 5.11x. Con la instalacion normal del venv salen
# 8/8 en 4.11x; basta cargar pydicom desde otra ruta (`pip install
# --target` + PYTHONPATH) para que aparezca el modo de 5.11x en ~2 de cada
# 8 corridas -- comprobado que ocurre IGUAL con pydicom 2.4.4 y 2.4.5, asi
# que es el asignador de memoria, no la version.
#
# Con 5.0 el tope caia DENTRO del modo alto: prueba intermitente, que es
# peor que no tener prueba. 6.0 deja ~0.9x de holgura sobre el peor caso
# medido y sigue separando con claridad del 7.10x de antes de C.2, que es
# la regresion que esta prueba existe para atrapar. En Windows el
# asignador es otro; el margen tiene que aguantar eso tambien.
UMBRAL_MULTIPLICADOR_PICO_ACEPTADO = 6.0


@pytest.mark.parametrize("clave", ["HALCYON_JUN", "MIXTA"])
def test_c_pico_de_memoria_acotado(clave):
    ruta = _requiere(clave)
    base, pico, crudo = _medir_pico_subproceso(ruta)
    delta = pico - base
    assert crudo > 0, "no se pudo determinar el tamaño crudo del volumen"
    razon = delta / crudo
    assert delta <= UMBRAL_MULTIPLICADOR_PICO_ACEPTADO * crudo, (
        f"{clave}: pico={delta / (1024*1024):.1f} MB para "
        f"crudo={crudo / (1024*1024):.1f} MB ({razon:.2f}x) -- supera el "
        f"tope de {UMBRAL_MULTIPLICADOR_PICO_ACEPTADO}x"
    )


# ---------------------------------------------------------------------------
# (d) Sin regresión de resultados: las seis series reales dan EXACTAMENTE
# los mismos números que antes de C.2. Nace verde a propósito (ver plan,
# §4/C.2): ya estaba comprobado que las dos rutas daban array_equal=True.
# Huella capturada con el código de ANTES de C.2 (git stash, 22-09-2026) y
# reconfirmada bit a bit después de cada cambio de este archivo.
# ---------------------------------------------------------------------------

HUELLA_PRE_C2 = {
    # clave: (shape, dtype, kv, ma, espesor, sha256 de volumen_hu.tobytes())
    "TOMOGRAFO": ((102, 512, 512), "float32", 120, 200, 2,
                  "d2c25f56e88a5e3d8bfb3a26a4b31c553a5a4f7a75cca8514fcaf7b0a542f47f"),
    "HALCYON_SEP": ((122, 512, 512), "float32", 125, 80, 2,
                     "2accbecaaedd5c8305b0e70f376af3376ed775a1501a63474491a76178ecc8bb"),
    "HALCYON_JUN": ((123, 512, 512), "float32", 125, 100, 2,
                     "7d3ec503ea60d7cc048cac5a196f7a13ef8c40e4c2f348f9613d1df10270d044"),
    "HALCYON_236": ((123, 512, 512), "float32", 140, 90, 1.99102978191527,
                     "74e16501bfa36db71fdac85664ee8f4315a04b1e393f051bf826561ef19d7c52"),
    "IX_DIC": ((70, 384, 384), "float32", 100, 80, 2.5,
                "d6fdee5297730894048a124ec5b953bb5cc72312812f6f2ac61d355908429ac8"),
    "MIXTA": ((278, 512, 512), "float32", 120, 200, 1,
               "8b9c1d225fd844e266ef143f7e66ad975c0d7e27ad47cf01908975cf94f72e9d"),
}


def test_todas_las_claves_de_la_huella_estan_en_catphan():
    assert set(HUELLA_PRE_C2) == set(CATPHAN)


@pytest.mark.parametrize("clave", sorted(HUELLA_PRE_C2))
def test_d_sin_regresion_de_resultados(clave):
    from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume

    ruta = _requiere(clave)
    shape_esperada, dtype_esperado, kv_esperado, ma_esperado, espesor_esperado, hash_esperado = HUELLA_PRE_C2[clave]

    vol = DicomVolume(ruta)
    assert vol.volumen_hu is not None, f"{clave}: volumen_hu es None"

    assert tuple(vol.volumen_hu.shape) == shape_esperada
    assert str(vol.volumen_hu.dtype) == dtype_esperado
    assert vol.kv == kv_esperado
    assert vol.ma == ma_esperado
    assert vol.espesor_corte == espesor_esperado

    hash_actual = hashlib.sha256(vol.volumen_hu.tobytes()).hexdigest()
    assert hash_actual == hash_esperado, (
        f"{clave}: volumen_hu cambio de contenido tras C.2 -- esto NO debe "
        f"pasar (C.2 no mueve ningun numero, ver §13.1 criterio de rechazo)"
    )


# ---------------------------------------------------------------------------
# (e) Un solo volumen vivo, SIEMPRE. Corrige la lectura original del plan:
# no hace falta "recarga bajo demanda" porque la carga real
# (tac_mensual.py:692-701, "Un solo visualizador, una sola carga") YA pasa
# por un unico VisualizadorDicom.vol que se REASIGNA -- Python libera el
# volumen anterior por conteo de referencias en cuanto se reasigna, sin
# necesitar codigo nuevo. Esta prueba FIJA esa garantia por si algo futuro
# (p. ej. arreglar el TypeError dormido de sincronizar_con_principal, ver
# CLAUDE.md) la rompe sin darse cuenta.
# ---------------------------------------------------------------------------

def test_e_un_solo_volumen_vivo_siempre():
    # Canvas REAL, como en la app (imagenUpLoader: VisualizadorDicom(
    # target_canvas=self.canvas), tac_mensual.py:786/912) -- con
    # target_canvas=None, VisualizadorDicom toma la rama que crea su
    # PROPIO pg.ImageView, un camino que la app real nunca ejercita y que
    # es inestable bajo pytest+offscreen (no es lo que se quiere probar
    # aqui).
    ruta1 = _requiere("HALCYON_JUN")
    ruta2 = _requiere("IX_DIC")

    pytest.importorskip("PyQt5")
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from resources.utils.matplotlib_lazy import get_matplotlib_components
    from data.ManejoDatos.catphan_TAC.leer_dicom import VisualizadorDicom, DicomVolume

    mpl = get_matplotlib_components()
    canvas = mpl['FigureCanvas'](mpl['Figure'](figsize=(4, 4)))

    v = VisualizadorDicom(target_canvas=canvas)
    assert v.use_external_canvas is True

    v.visualizar_imagen_cargada(ruta1)
    assert v.vol is not None
    referencia_debil = weakref.ref(v.vol)

    v.visualizar_imagen_cargada(ruta2)
    gc.collect()

    assert referencia_debil() is None, (
        "el DicomVolume de la carga anterior debe liberarse al cargar uno "
        "nuevo en el MISMO visualizador (mecanismo real de "
        "_cargar_carpeta_dicom: un solo visualizador, una sola carga)"
    )
    vivos = sum(1 for o in gc.get_objects() if isinstance(o, DicomVolume))
    assert vivos == 1, f"debe quedar 1 solo DicomVolume vivo, hay {vivos}"
