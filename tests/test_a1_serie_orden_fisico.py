"""A.1 (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md): los cortes se ordenan
por su posición física real, y se analiza una sola serie.

D-01: el Halcyon y el iX no traen SliceLocation -> `DicomVolume` (orden
viejo, por SliceLocation) barajaba el volumen. D-06: sin control de serie
única, una carpeta con dos series (o un RTSTRUCT) se mezclaba.

Verifica `analisisImagenes.catphan.serie.leer_serie` contra pylinac (que
ordena correctamente por construcción) y contra `DicomVolume`, que ahora
delega en la misma función (corolario 1: una operación, una definición).
"""
import os

import numpy as np
import pydicom
import pytest

from _corpus import serie_catphan
from analisisImagenes.catphan.serie import CT_IMAGE_STORAGE, leer_serie


def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return ruta


@pytest.mark.parametrize(
    "clave", ["TOMOGRAFO", "HALCYON_SEP", "HALCYON_JUN", "HALCYON_236", "IX_DIC"]
)
def test_z_estrictamente_creciente(clave):
    ruta = _requerir(clave)
    serie = leer_serie(ruta)
    zs = [c.posicion_mm for c in serie.cortes]
    assert all(zs[i] < zs[i + 1] for i in range(len(zs) - 1)), (
        f"{clave}: la posición no es estrictamente creciente"
    )


@pytest.mark.parametrize(
    "clave", ["TOMOGRAFO", "HALCYON_SEP", "HALCYON_JUN", "HALCYON_236", "IX_DIC"]
)
def test_orden_identico_al_de_pylinac(clave):
    """La secuencia de SOPInstanceUID debe coincidir con la que arma
    pylinac internamente (`CatPhan504.dicom_stack`, que ordena por
    ImagePositionPatient proyectado sobre la normal) -- si difieren, el
    índice de corte que sugiere pylinac (A.2) apuntaría a otro corte del
    volumen de la app."""
    from pylinac.ct import CatPhan504

    ruta = _requerir(clave)
    serie = leer_serie(ruta)
    ct = CatPhan504(ruta)
    esperado = [str(m.SOPInstanceUID) for m in ct.dicom_stack.metadatas]
    obtenido = [c.sop_uid for c in serie.cortes]
    assert obtenido == esperado


def test_ix_rtstruct_queda_fuera():
    ruta = _requerir("IX_DIC")
    serie = leer_serie(ruta)
    for corte in serie.cortes:
        ds = pydicom.dcmread(corte.ruta, stop_before_pixels=True)
        assert str(ds.SOPClassUID) == CT_IMAGE_STORAGE
    assert serie.no_imagen >= 1, "el RTSTRUCT de la carpeta debía contarse en no_imagen"


def test_carpeta_mixta_descarta_la_serie_minoritaria():
    ruta = _requerir("MIXTA")
    serie = leer_serie(ruta)
    assert len(serie.cortes) == 278
    assert serie.series_descartadas == {
        "1.2.246.352.62.2.4676414310890163757.614667284510613388": 123
    }


def test_serie_sintetica_sin_slicelocation_se_ordena_por_ipp(tmp_path):
    """Réplica mínima del defecto D-01: una serie sin `SliceLocation` (como
    el Halcyon/iX reales) debe ordenarse igual por `ImagePositionPatient`,
    no colapsar a un orden arbitrario."""
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    serie_uid = generate_uid()
    orden_disco = [2, 0, 3, 1]  # a propósito, no coincide con el orden espacial
    for i in orden_disco:
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta.MediaStorageSOPClassUID = CT_IMAGE_STORAGE
        ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
        ds.SOPClassUID = CT_IMAGE_STORAGE
        ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
        ds.SeriesInstanceUID = serie_uid
        ds.Modality = "CT"
        ds.Rows = 4
        ds.Columns = 4
        ds.PixelSpacing = [1.0, 1.0]
        ds.RescaleSlope = 1
        ds.RescaleIntercept = -1024
        ds.SliceThickness = 2.0
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds.ImagePositionPatient = [0, 0, float(i * 2)]  # espacio real: 0,2,4,6 mm
        # a propósito, SIN SliceLocation -- igual que Halcyon/iX reales
        ds.PixelData = np.zeros((4, 4), dtype=np.int16).tobytes()
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 1
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.is_little_endian = True
        ds.is_implicit_VR = False
        ds.save_as(str(tmp_path / f"corte_{i}.dcm"), write_like_original=False)

    serie = leer_serie(str(tmp_path))
    zs = [c.ipp[2] for c in serie.cortes]
    assert zs == [0.0, 2.0, 4.0, 6.0]


def test_dicomvolume_delega_en_leer_serie_y_orden_coincide():
    """Compuerta de daño colateral + verificación de A.1 sobre `DicomVolume`
    (el visor): en el tomógrafo (que ya ordenaba bien por casualidad, todas
    sus imágenes SÍ traen SliceLocation), el volumen debe salir
    BYTE A BYTE igual; en el Halcyon/iX, el atributo `cortes` debe quedar
    ordenado por posición física real, y `series_descartadas`/`no_imagen`
    deben reflejar lo que `leer_serie` reportó."""
    from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume

    ruta = _requerir("TOMOGRAFO")
    vol = DicomVolume(ruta)
    serie = leer_serie(ruta)
    assert [str(ds.SOPInstanceUID) for ds in vol.cortes] == [c.sop_uid for c in serie.cortes]
    assert vol.no_imagen == 0
    assert vol.series_descartadas == {}

    ruta_ix = _requerir("IX_DIC")
    vol_ix = DicomVolume(ruta_ix)
    serie_ix = leer_serie(ruta_ix)
    assert [str(ds.SOPInstanceUID) for ds in vol_ix.cortes] == [c.sop_uid for c in serie_ix.cortes]
    assert vol_ix.no_imagen == serie_ix.no_imagen == 1
