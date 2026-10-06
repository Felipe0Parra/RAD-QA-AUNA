"""Constructores de series DICOM SINTETICAS minimas para las pruebas de la carga (SE.0, SE.1 de PLAN_GUARDADO_SIN_ESPESOR_Y_RESPALDOS_05-10.md).

Un corte es de 64 x 64 con lo justo para que `leer_serie` y `DicomVolume` lo carguen. Lo que cambia entre casos es lo que el equipo publica: el espesor puede venir con
un numero, VACIO (`None`: la etiqueta esta pero sin valor, como en el topograma real) o AUSENTE (`AUSENTE`: la etiqueta no se escribe).

Este archivo NO empieza por `test_`, asi pytest no lo colecciona.
"""
import os

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from analisisImagenes.catphan.serie import CT_IMAGE_STORAGE

AUSENTE = object()          # el espesor (u otra etiqueta) NO se escribe en el archivo
DESCRIPCION_AXIAL = "RT_ABDOMEN_PELVIS 2,00 Br36 S3 CD"
DESCRIPCION_TOPOGRAMA = "Topograma 0,60 Tr20 cor"


def escribir_corte(ruta, serie_uid, z, kv, ma, espesor, descripcion, tipo_de_imagen, instancia, con_slice_location=True):
    """Escribe UN corte CT sintetico en `ruta`. `espesor`: numero, `None` (etiqueta vacia) o `AUSENTE` (sin etiqueta)."""
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = CT_IMAGE_STORAGE
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
    ds.SOPClassUID = CT_IMAGE_STORAGE
    ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
    ds.SeriesInstanceUID = serie_uid
    ds.Modality = "CT"
    ds.Manufacturer = "Siemens Healthineers"
    ds.ManufacturerModelName = "SOMATOM go.Sim"
    ds.StationName = "CT128260"
    ds.SeriesDescription = descripcion
    ds.ImageType = tipo_de_imagen
    ds.InstanceNumber = instancia
    ds.KVP = str(kv)                                    # DS como lo escribe el equipo real ("120"), no 120.0
    ds.XRayTubeCurrent = ma
    if espesor is not AUSENTE:
        ds.SliceThickness = espesor                     # `None` = la etiqueta presente pero VACIA (como el topograma real)
    ds.Rows = 64
    ds.Columns = 64
    ds.PixelSpacing = [1.0, 1.0]
    ds.RescaleSlope = 1
    ds.RescaleIntercept = -1024
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.ImagePositionPatient = [0, 0, float(z)]
    if con_slice_location:
        ds.SliceLocation = float(z)
    ds.PixelData = (np.random.default_rng(int(abs(z)) + 1).integers(900, 1100, (64, 64))).astype(np.int16).tobytes()
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 1
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.save_as(ruta, write_like_original=False)


def serie_axial(carpeta, espesor=2.0, n=5, kv=120, ma=343, espesores_por_corte=None):
    """`n` cortes axiales (de 0 a 2*(n-1) mm). Los archivos se nombran en un orden de disco que NO coincide con el espacial
    (`corte_<permutacion>.dcm`). `espesores_por_corte`: `{indice espacial: espesor}` para que un corte traiga otro distinto."""
    os.makedirs(carpeta, exist_ok=True)
    uid = generate_uid()
    permutacion = [(i * 3 + 1) % n for i in range(n)] if n in (5,) else list(range(n))
    for i in range(n):
        esp = (espesores_por_corte or {}).get(i, espesor)
        escribir_corte(f"{carpeta}/corte_{permutacion[i]}.dcm", uid, i * 2.0, kv, ma, esp, DESCRIPCION_AXIAL,
                       ["ORIGINAL", "PRIMARY", "AXIAL"], i + 2)
    return carpeta


def serie_axial_con_localizador(carpeta, espesor=2.0):
    """5 cortes axiales y UN localizador (110 kV, 20 mA, espesor vacio) con `SliceLocation` -135.5, menor que todos, cuyo archivo (`0_topograma.dcm`) ordena PRIMERO
    en disco: la misma situacion de la carpeta real del hospital (28-09-2026)."""
    serie_axial(carpeta, espesor=espesor)
    escribir_corte(f"{carpeta}/0_topograma.dcm", generate_uid(), -135.5, 110, 20, None, DESCRIPCION_TOPOGRAMA,
                   ["ORIGINAL", "PRIMARY", "LOCALIZER"], 1)
    return carpeta
