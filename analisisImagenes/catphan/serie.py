"""A.1 (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md): lectura de una serie CT
por posición física real, no por `SliceLocation` ni por orden de disco.

D-01: los CBCT de Varian (Halcyon, iX) no traen `SliceLocation` -> el
volumen de la app queda barajado si se ordena por esa etiqueta. D-06: sin
control de serie única, un RTSTRUCT (u otra serie DICOM en la misma
carpeta) se mezclaría con los cortes de imagen.

Esta es la única definición del orden espacial -- la usa el visor
(`leer_dicom.py`, vía `DicomVolume._load_dicoms`) y el motor (`motor.py`,
B.1), para que las dos lecturas no puedan volver a divergir (corolario 1,
CLAUDE.md: "una operación, una definición").
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pydicom

# CT Image Storage. Excluye RTSTRUCT (1.2.840.10008.5.1.4.1.1.481.3) y
# cualquier otro SOP Class que pudiera colarse en la misma carpeta.
CT_IMAGE_STORAGE = "1.2.840.10008.5.1.4.1.1.2"

# Etiquetas que identifican equipo y protocolo de adquisición (A.3, B.1).
ETIQUETAS_SERIE = (
    "Manufacturer",
    "ManufacturerModelName",
    "DeviceSerialNumber",
    "StationName",
    "SoftwareVersions",
    "SeriesDescription",
    "KVP",
    "XRayTubeCurrent",
    "Exposure",
    "ReconstructionDiameter",
    "ConvolutionKernel",
    "PatientPosition",
)


@dataclass(frozen=True)
class CorteCT:
    """Un corte de la serie elegida, ya resuelto a su posición espacial."""

    ruta: str
    sop_uid: str
    posicion_mm: float
    ipp: tuple
    instancia: Optional[int]


@dataclass
class SerieCT:
    """Una serie CT completa, ordenada por posición física ascendente."""

    carpeta: str
    serie_uid: str
    cortes: list  # list[CorteCT], en orden espacial ascendente
    series_descartadas: dict  # {serie_uid: n_archivos}
    no_imagen: int
    pixel_mm: tuple
    espesor_mm: float
    filas: int
    columnas: int
    etiquetas: dict
    # No estaba en la lista literal del plan (§3, A.1); se añade porque el
    # propio CAMBIO exige avisar del paso no uniforme "sin fallar", y una
    # SerieCT es el único objeto que viaja hasta el llamador para hacerlo.
    avisos: list = field(default_factory=list)


def _normal_desde_orientacion(iop):
    fila = np.array(iop[0:3], dtype=float)
    columna = np.array(iop[3:6], dtype=float)
    return np.cross(fila, columna)


def leer_serie(carpeta: str) -> SerieCT:
    """Lee la serie CT mayoritaria de `carpeta`, en orden espacial real.

    - Filtra por `SOPClassUID` de CT Image Storage (D-06): un RTSTRUCT u
      otro objeto no-imagen no pasa el filtro.
    - Si hay más de una `SeriesInstanceUID`, se queda con la mayoritaria y
      reporta las demás en `series_descartadas` (no se mezclan).
    - Ordena por la proyección de `ImagePositionPatient` sobre la normal
      del plano de corte (`row × col` de `ImageOrientationPatient`), no
      por `SliceLocation` ni por `z` a secas -- correcto incluso si el
      equipo escanea con una inclinación (el iX, ~0.2°).
    - Lanza `ValueError` si `PixelSpacing`/`Rows`/`Columns`/rescale no son
      uniformes dentro de la serie elegida: un volumen así no se puede
      apilar de forma consistente.
    - Si el paso entre cortes no es uniforme, lo anota en `avisos` sin
      fallar (algunas reconstrucciones legítimas varían el paso).
    """
    candidatos = []
    no_imagen = 0
    for nombre in sorted(os.listdir(carpeta)):
        if not nombre.lower().endswith(".dcm"):
            continue
        ruta = os.path.join(carpeta, nombre)
        try:
            ds = pydicom.dcmread(ruta, stop_before_pixels=True)
        except Exception:
            no_imagen += 1
            continue
        if str(getattr(ds, "SOPClassUID", "")) != CT_IMAGE_STORAGE:
            no_imagen += 1
            continue
        candidatos.append((ruta, ds))

    if not candidatos:
        raise ValueError(f"No hay cortes de CT Image Storage en {carpeta!r}")

    por_serie = {}
    for ruta, ds in candidatos:
        uid = str(getattr(ds, "SeriesInstanceUID", ""))
        por_serie.setdefault(uid, []).append((ruta, ds))

    serie_uid = max(por_serie, key=lambda k: len(por_serie[k]))
    elegidos = por_serie[serie_uid]
    series_descartadas = {
        uid: len(items) for uid, items in por_serie.items() if uid != serie_uid
    }

    primero = elegidos[0][1]
    pixel_mm = tuple(float(v) for v in getattr(primero, "PixelSpacing", (1.0, 1.0)))
    filas = int(getattr(primero, "Rows"))
    columnas = int(getattr(primero, "Columns"))
    slope0 = float(getattr(primero, "RescaleSlope", 1))
    intercept0 = float(getattr(primero, "RescaleIntercept", 0))
    espesor_mm = float(getattr(primero, "SliceThickness", 0.0))

    for ruta, ds in elegidos:
        pixel_i = tuple(float(v) for v in getattr(ds, "PixelSpacing", (1.0, 1.0)))
        if (
            pixel_i != pixel_mm
            or int(getattr(ds, "Rows")) != filas
            or int(getattr(ds, "Columns")) != columnas
            or float(getattr(ds, "RescaleSlope", 1)) != slope0
            or float(getattr(ds, "RescaleIntercept", 0)) != intercept0
        ):
            raise ValueError(
                f"La serie {serie_uid} en {carpeta!r} no es uniforme: "
                "PixelSpacing/Rows/Columns/rescale difieren entre cortes"
            )

    iop = getattr(primero, "ImageOrientationPatient", None)
    normal = _normal_desde_orientacion(iop) if iop is not None else np.array([0.0, 0.0, 1.0])

    cortes = []
    for ruta, ds in elegidos:
        ipp = tuple(float(v) for v in getattr(ds, "ImagePositionPatient", (0.0, 0.0, 0.0)))
        posicion_mm = float(np.dot(np.array(ipp), normal))
        instancia = getattr(ds, "InstanceNumber", None)
        cortes.append(
            CorteCT(
                ruta=ruta,
                sop_uid=str(getattr(ds, "SOPInstanceUID", "")),
                posicion_mm=posicion_mm,
                ipp=ipp,
                instancia=int(instancia) if instancia is not None else None,
            )
        )

    cortes.sort(key=lambda c: c.posicion_mm)

    avisos = []
    if len(cortes) > 1:
        pasos = np.diff([c.posicion_mm for c in cortes])
        mediana = float(np.median(pasos))
        if mediana != 0 and float(np.ptp(pasos)) > 0.05 * abs(mediana):
            avisos.append(
                "El paso entre cortes no es uniforme "
                f"(mín={pasos.min():.3f} mm, máx={pasos.max():.3f} mm)"
            )

    etiquetas = {clave: getattr(primero, clave, None) for clave in ETIQUETAS_SERIE}

    return SerieCT(
        carpeta=carpeta,
        serie_uid=serie_uid,
        cortes=cortes,
        series_descartadas=series_descartadas,
        no_imagen=no_imagen,
        pixel_mm=pixel_mm,
        espesor_mm=espesor_mm,
        filas=filas,
        columnas=columnas,
        etiquetas=etiquetas,
        avisos=avisos,
    )
