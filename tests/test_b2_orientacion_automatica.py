"""B.2 (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md): orientación
automática del fantoma.

D-03/D-13: la serie de septiembre del Halcyon entró girada 180° respecto
de junio y del tomógrafo, y ni la app ni pylinac 3.45 (ni 3.46-3.48) lo
detectan -- los números CT salen en espejo. La regla (correlación de
Pearson HU medido vs nominal + HU del centro del CTP486) separa 0.999 de
0.26 con margen amplio y no depende del nivel absoluto de HU del equipo.
"""
import os
import tempfile
import types
import warnings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from _catphan_oro import LIMITE_HOMOGENEIDAD_IX
from _corpus import serie_catphan
from analisisImagenes.catphan import motor
from analisisImagenes.catphan.serie import leer_serie

_LIMITE_POR_SERIE = {
    "TOMOGRAFO": None,
    "HALCYON_JUN": None,
    "HALCYON_236": None,
    "HALCYON_SEP": None,
    "IX_DIC": LIMITE_HOMOGENEIDAD_IX,
}


def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return ruta


def _analizar(clave):
    ruta = _requerir(clave)
    serie = leer_serie(ruta)
    perfil = types.SimpleNamespace(limite_variacion_hu=_LIMITE_POR_SERIE[clave], nombre=clave)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return motor.analizar(serie, perfil)


@pytest.mark.parametrize(
    "clave,esperado",
    [
        ("TOMOGRAFO", "normal"),
        ("HALCYON_JUN", "normal"),
        ("HALCYON_236", "normal"),
        ("HALCYON_SEP", "invertido"),
        ("IX_DIC", "normal"),
    ],
)
def test_orientacion_detectada(clave, esperado):
    resultado = _analizar(clave)
    assert resultado.orientacion == esperado


def test_halcyon_sep_da_los_hu_correctos_ya_volteada():
    resultado = _analizar("HALCYON_SEP")
    m404 = resultado.modulos["CTP404"].metricas
    # §0.8: Teflón/PMP/etc. de la serie YA VOLTEADA, no los de espejo.
    assert m404["hu_teflon"].valor == pytest.approx(894.5, abs=0.5)
    assert m404["hu_pmp"].valor == pytest.approx(-180, abs=0.5)


def test_rojo_sin_b2_halcyon_sep_da_teflon_en_espejo():
    """Reproduce el defecto D-03 tal cual estaría sin la detección de
    orientación: analizar SOLO en orientación normal (sin el paso de
    volteo de B.2) da el Teflón donde debería estar el PMP."""
    ruta = _requerir("HALCYON_SEP")
    serie = leer_serie(ruta)
    rutas = [c.ruta for c in serie.cortes]
    ct = motor._construir(rutas, None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        motor._analizar_una_vez(ct, None, {})
    teflon_sin_voltear = ct.ctp404.rois["Teflon"].pixel_value
    assert teflon_sin_voltear == pytest.approx(-180, abs=1.0)


def test_orientacion_indeterminada_en_volumen_sin_fantoma(tmp_path):
    """Un volumen de puro ruido (sin fantoma) no debe medir NADA -- debe
    fallar explícitamente, no devolver un número inventado."""
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    from analisisImagenes.catphan.serie import CT_IMAGE_STORAGE

    serie_uid = generate_uid()
    rng = np.random.default_rng(0)
    n = 45
    for i in range(n):
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta.MediaStorageSOPClassUID = CT_IMAGE_STORAGE
        ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
        ds.SOPClassUID = CT_IMAGE_STORAGE
        ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
        ds.SeriesInstanceUID = serie_uid
        ds.Modality = "CT"
        ds.Rows = 256
        ds.Columns = 256
        ds.PixelSpacing = [1.0, 1.0]
        ds.RescaleSlope = 1
        ds.RescaleIntercept = -1024
        ds.SliceThickness = 2.0
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.ImagePositionPatient = [0, 0, float(i * 2)]
        arr = (rng.normal(0, 20, (256, 256)) + 1024).astype(np.uint16)
        ds.PixelData = arr.tobytes()
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 0
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.is_little_endian = True
        ds.is_implicit_VR = False
        ds.save_as(str(tmp_path / f"corte_{i:03d}.dcm"), write_like_original=False)

    serie = leer_serie(str(tmp_path))
    perfil = types.SimpleNamespace(limite_variacion_hu=None, nombre="SINTETICO")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(motor.OrientacionIndeterminada):
            motor.analizar(serie, perfil)
