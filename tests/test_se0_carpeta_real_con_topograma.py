"""SE.0 (PLAN_GUARDADO_SIN_ESPESOR_Y_RESPALDOS_05-10.md, DP-149): la carpeta real que no dejo guardar en el hospital queda como prueba.

El 28-09-2026 el tomografo del hospital exporto una carpeta con DOS cosas: la serie axial de 151 cortes (`RT_ABDOMEN_PELVIS 2,00 Br36 S3 CD`: 120 kV,
343 mA, 2.0 mm) y UN topograma (`Topograma 0,60 Tr20 cor`, `LOCALIZER`, 110 kV, 20 mA, `SliceLocation` -135.5 y `SliceThickness` vacio). La version
desplegada (el cargador anterior al 17-09) ordenaba todo lo que fuera CT con pixeles por `SliceLocation` y tomaba los datos del PRIMERO: el topograma. La
pantalla mostraba `110 kV`, `20 mA` y el espesor vacio (campos de solo lectura) y no dejaba guardar; y lo que habria guardado eran los kV y mA del topograma.
`A.1` (20-09) lo cambio por "la serie mayoritaria" y con eso la carpeta carga bien, pero NINGUNA prueba lo fijaba con un localizador.

Esta prueba lo fija: con esa carpeta, la serie analizada es la axial y lo que se guarda son SUS parametros (120 / 343 / 2.0), nunca los del topograma. Mismo caso
con una serie SINTETICA minima (5 cortes de 64 x 64 mas un localizador con `SliceLocation` menor y espesor vacio), que corre siempre aunque falte la carpeta real.
El CONTROL de cada caso escribe la regla anterior en pocas lineas y comprueba que sobre la misma carpeta da 110 / 20 / None: la prueba discrimina.
"""
import functools
import os

import gc

import pydicom
import pytest

from _corpus import serie_hospital
from _formularios_imagenes import FORMULARIOS, app, bd_temporal, iniciar, sin_dialogos  # noqa: F401  (fixtures)
from _serie_sintetica import DESCRIPCION_AXIAL, DESCRIPCION_TOPOGRAMA, serie_axial_con_localizador
from analisisImagenes.catphan.serie import adquisicion_de_serie, leer_serie
from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume

CLAVE = "TOMOGRAFO_SEP26"


def _regla_anterior(carpeta):
    """El cargador DESPLEGADO hasta el 17-09-2026 (8ff2e55~1), en pocas lineas: todo archivo CT con pixeles, ordenado por `SliceLocation` (ausente = 0),
    y los parametros del PRIMERO. Devuelve `(n cortes, kV, mA, espesor, descripcion del primero)`."""
    cortes = []
    for nombre in os.listdir(carpeta):
        if nombre.endswith(".dcm"):
            ds = pydicom.dcmread(os.path.join(carpeta, nombre))
            if "CT" in getattr(ds, "Modality", "") and "PixelData" in ds:
                cortes.append(ds)
    cortes.sort(key=lambda d: float(getattr(d, "SliceLocation", 0)))
    primero = cortes[0]
    return (len(cortes), primero.KVP, primero.XRayTubeCurrent, getattr(primero, "SliceThickness", None),
            getattr(primero, "SeriesDescription", None))


@pytest.fixture
def formularios():
    """Los formularios que arma una prueba. Al terminar se les suelta el volumen cargado: `test_c2` cuenta los `DicomVolume` vivos de TODO el proceso y exige que
    quede uno, asi que una prueba que arma una pantalla con una carpeta cargada no puede dejarlo vivo para las que corran despues."""
    lista = []
    yield lista
    for obj in lista:
        visualizador = getattr(obj, "visualizador_principal", None)
        if visualizador is not None:
            visualizador.vol = None
    lista.clear()
    gc.collect()


# ------------------------------------------------------------------------------------------------ la carpeta REAL
@pytest.fixture(scope="module")
def ruta_real():
    ruta = serie_hospital(CLAVE)
    if ruta is None:
        pytest.skip(f"corpus del hospital no disponible en esta maquina: {CLAVE}")
    return ruta


@functools.lru_cache(maxsize=None)
def _serie_real(ruta):
    return leer_serie(ruta)


class TestCarpetaRealDelHospital:
    def test_la_carpeta_trae_152_archivos(self, ruta_real):
        assert sum(1 for f in os.listdir(ruta_real) if f.lower().endswith(".dcm")) == 152

    def test_a_leer_serie_elige_la_axial_y_descarta_el_topograma(self, ruta_real):
        serie = _serie_real(ruta_real)
        assert len(serie.cortes) == 151
        assert list(serie.series_descartadas.values()) == [1]
        detalle = next(iter(serie.detalle_series_descartadas.values()))
        assert detalle["n"] == 1 and detalle["descripcion_serie"] == DESCRIPCION_TOPOGRAMA

    def test_b_la_adquisicion_es_la_de_la_serie_axial(self, ruta_real):
        adq = adquisicion_de_serie(_serie_real(ruta_real))
        assert (adq["kv"], adq["ma"], adq["espesor_mm"]) == (120, 343, 2.0)
        assert adq["kernel"] == "Br36f, 3" and adq["descripcion_serie"] == DESCRIPCION_AXIAL
        assert adq["n_cortes"] == 151

    def test_c_el_primer_corte_del_volumen_es_axial_y_los_parametros_son_los_suyos(self, ruta_real):
        vol = DicomVolume(ruta_real)
        assert len(vol.cortes) == 151
        assert "AXIAL" in list(vol.cortes[0].ImageType) and "LOCALIZER" not in list(vol.cortes[0].ImageType)
        assert (vol.kv, vol.ma, float(vol.espesor_corte)) == (120, 343, 2.0)

    def test_e_control_la_regla_anterior_da_los_parametros_del_topograma(self, ruta_real):
        """Sobre la MISMA carpeta, la regla desplegada elige el topograma: 152 cortes, 110 kV, 20 mA y el espesor vacio."""
        n, kv, ma, espesor, descripcion = _regla_anterior(ruta_real)
        assert (n, kv, ma, espesor, descripcion) == (152, 110, 20, None, DESCRIPCION_TOPOGRAMA)

    def test_d_la_pantalla_real_del_tomografo_muestra_los_de_la_axial_deja_guardar_y_el_guardado_entra(
            self, app, bd_temporal, sin_dialogos, formularios, ruta_real, monkeypatch):
        """El camino completo del hospital, con la pantalla real y una BD temporal: la ventana de metadatos (decidida sin una persona), los tres campos
        de solo lectura, la guarda y un guardado real. La fila guardada lleva 120 / 343 / 2.0 y la desviacion del protocolo nombra mA, FOV y kernel."""
        from PyQt5.QtWidgets import QMessageBox
        avisos = []
        monkeypatch.setattr(QMessageBox, "warning", lambda parent, titulo, texto, *a, **k: avisos.append((titulo, texto)))
        obj = iniciar(FORMULARIOS["tomografo"][0]())
        formularios.append(obj)
        obj.user_id = "Fisico Real"
        visualizador = obj.visualizador_principal
        visualizador.mostrar_popup_cortes = lambda resultados: None
        visualizador.confirmador_de_carga = lambda parent, vol, equipo: True
        visualizador.visualizar_imagen_cargada(ruta_real)

        assert (obj.kv_val_esp.text(), obj.ma_val_esp.text(), obj.ec_val_esp.text()) == ("120 kV", "343 mA", "2.0 mm")
        assert obj._verificar_datos_basicos() is True and avisos == []

        obj._registrar_adquisicion("espesor")
        ok = obj.guardar_resultado_individual("espesor", {
            "espesor_promedio_mm": 1.9, "espesor_teorico_mm": obj.espesor_corte_val, "diferencia_mm": 0.1,
            "espesores_individuales": {"Izquierda": 1.9, "Abajo": 1.9, "Derecha": 1.9, "Arriba": 1.9}, "num_rampas_detectadas": 4})
        assert ok is not False and avisos == []
        filas = bd_temporal.execute(
            "SELECT kv, ma, espesor_corte, desviacion_protocolo FROM pruebas WHERE id_sesion = ? AND activo = 1", (obj.ref,)).fetchall()
        assert len(filas) == 1
        kv, ma, espesor, desviacion = filas[0]
        assert (kv, ma, espesor) == (120, 343, 2.0), "se guardaron los parametros del topograma"
        assert "mA: 343" in desviacion and "FOV [mm]: 599.85" in desviacion and "Kernel: Br36f" in desviacion


# --------------------------------------------------------------------------------- la serie SINTETICA (siempre corre)
@pytest.fixture
def carpeta_sintetica(tmp_path):
    """5 cortes axiales (120 kV, 343 mA, 2.0 mm, de 0 a 8 mm) y UN localizador (110 kV, 20 mA, espesor vacio) con `SliceLocation` -135.5, menor que todos: la misma
    situacion de la carpeta real, donde el topograma es TAMBIEN el primer archivo en orden de disco (`0_topograma.dcm` ordena antes que `corte_*.dcm`). Los cortes axiales
    se nombran en un orden que no coincide con el espacial. El constructor vive en `tests/_serie_sintetica.py` (lo comparte SE.1)."""
    return serie_axial_con_localizador(str(tmp_path))


class TestSerieSinteticaConLocalizador:
    def test_a_leer_serie_elige_la_axial_y_descarta_el_localizador(self, carpeta_sintetica):
        serie = leer_serie(carpeta_sintetica)
        assert len(serie.cortes) == 5
        assert list(serie.series_descartadas.values()) == [1]
        detalle = next(iter(serie.detalle_series_descartadas.values()))
        assert detalle["descripcion_serie"] == DESCRIPCION_TOPOGRAMA

    def test_b_la_adquisicion_es_la_de_la_serie_axial(self, carpeta_sintetica):
        adq = adquisicion_de_serie(leer_serie(carpeta_sintetica))
        assert (adq["kv"], adq["ma"], adq["espesor_mm"], adq["n_cortes"]) == (120, 343, 2.0, 5)

    def test_c_el_primer_corte_del_volumen_es_axial(self, carpeta_sintetica):
        vol = DicomVolume(carpeta_sintetica)
        assert len(vol.cortes) == 5
        assert "AXIAL" in list(vol.cortes[0].ImageType)
        assert (vol.kv, vol.ma, float(vol.espesor_corte)) == (120, 343, 2.0)

    def test_e_control_la_regla_anterior_da_los_parametros_del_localizador(self, carpeta_sintetica):
        n, kv, ma, espesor, descripcion = _regla_anterior(carpeta_sintetica)
        assert (n, kv, ma, espesor, descripcion) == (6, 110, 20, None, DESCRIPCION_TOPOGRAMA)

    def test_los_campos_de_la_pantalla_dicen_los_de_la_axial_y_la_guarda_deja_guardar(
            self, app, bd_temporal, sin_dialogos, formularios, carpeta_sintetica, monkeypatch):
        from PyQt5.QtWidgets import QMessageBox
        avisos = []
        monkeypatch.setattr(QMessageBox, "warning", lambda parent, titulo, texto, *a, **k: avisos.append((titulo, texto)))
        obj = iniciar(FORMULARIOS["tomografo"][0]())
        formularios.append(obj)
        obj.user_id = "Fisico Real"
        obj.visualizador_principal.vol = DicomVolume(carpeta_sintetica)
        obj.asignar_parametros_adquisicion()
        assert (obj.kv_val_esp.text(), obj.ma_val_esp.text(), obj.ec_val_esp.text()) == ("120 kV", "343 mA", "2.0 mm")
        assert obj._verificar_datos_basicos() is True and avisos == []
