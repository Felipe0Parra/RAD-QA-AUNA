"""A.3 (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md): la app sabe de qué
equipo es la serie.

D-07: nada impide guardar una serie del Halcyon bajo el control del
tomógrafo -- la carpeta `Catphan/` real mezcla los dos equipos. La
identificación se lee del propio DICOM (Manufacturer + Model como
requisito; DeviceSerialNumber/StationName como confirmación), nunca de la
pantalla en la que se cargó.
"""
import dataclasses

import pytest

from _corpus import serie_catphan
from analisisImagenes.catphan.serie import identificar_equipo, leer_serie


def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return ruta


@pytest.mark.parametrize(
    "clave,esperado",
    [
        ("TOMOGRAFO", "Tomógrafo"),
        ("HALCYON_SEP", "Halcyon"),
        ("HALCYON_JUN", "Halcyon"),
        ("HALCYON_236", "Halcyon"),
        ("IX_DIC", "Clinac ix"),
    ],
)
def test_las_5_series_reales_se_identifican_bien(clave, esperado):
    ruta = _requerir(clave)
    serie = leer_serie(ruta)
    equipo, advertencia = identificar_equipo(serie)
    assert equipo == esperado
    assert advertencia is None


def test_fabricante_desconocido_da_none():
    ruta = _requerir("TOMOGRAFO")
    serie = leer_serie(ruta)
    serie_falsa = dataclasses.replace(
        serie,
        etiquetas={**serie.etiquetas, "Manufacturer": "Otro Fabricante S.A.",
                   "ManufacturerModelName": "Modelo Inventado"},
    )
    equipo, advertencia = identificar_equipo(serie_falsa)
    assert equipo is None
    assert advertencia is None


def test_halcyon_con_otro_serial_da_equipo_mas_advertencia():
    ruta = _requerir("HALCYON_JUN")
    serie = leer_serie(ruta)
    serie_otra_consola = dataclasses.replace(
        serie, etiquetas={**serie.etiquetas, "DeviceSerialNumber": "9999", "StationName": "OtraConsola"}
    )
    equipo, advertencia = identificar_equipo(serie_otra_consola)
    assert equipo == "Halcyon"
    assert advertencia is not None
    assert "Halcyon" in advertencia


def test_ix_usa_el_serial_de_las_imagenes_no_el_del_rtstruct():
    """DeviceSerialNumber difiere entre las imágenes (505) y el RTSTRUCT
    (5005) del iX. `leer_serie` ya excluye el RTSTRUCT (A.1), así que
    `identificar_equipo` nunca ve el 5005."""
    ruta = _requerir("IX_DIC")
    serie = leer_serie(ruta)
    assert serie.etiquetas["DeviceSerialNumber"] == "505"
    equipo, advertencia = identificar_equipo(serie)
    assert equipo == "Clinac ix"
    assert advertencia is None


def test_halcyon_y_ix_comparten_fabricante_pero_no_modelo():
    """El requisito real que separa Halcyon de iX es el modelo, no el
    fabricante (los dos son Varian)."""
    ruta_hc = _requerir("HALCYON_JUN")
    ruta_ix = _requerir("IX_DIC")
    hc = leer_serie(ruta_hc)
    ix = leer_serie(ruta_ix)
    assert hc.etiquetas["Manufacturer"] == ix.etiquetas["Manufacturer"]
    assert hc.etiquetas["ManufacturerModelName"] != ix.etiquetas["ManufacturerModelName"]
