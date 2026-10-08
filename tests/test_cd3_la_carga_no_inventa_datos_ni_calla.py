"""CD.3 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, B5 y B6): la carga no inventa datos ni calla lo que dejo fuera.

Antes: (a) si la conversion a HU fallaba con el volumen ya apilado, la ruta estandar dejaba `volumen_hu` = el volumen CRUDO sin escala como si fueran HU (solo un `print`); (b) un fallo al
decodificar los pixeles dejaba `error_de_carga = None` y el aviso decia «Detalle: sin detalle» (las dos rutas); (c) con al menos un `.dcm` en la carpeta, los cortes sin la extension .dcm se
ignoraban sin aviso (se cargaban 101 cortes de 102) y los `.dcm` ilegibles se contaban como «no son imagen CT: es normal»; con nombres tipo UID («1.2.840...») el aviso decia «no tiene archivos
DICOM»; (d) sin `PixelSpacing` la ventana de metadatos decia «Pixel [mm] = 1», un dato inventado (la misma clase que el espesor `0.0` que cerro SE.1).

Ahora: si la conversion o la decodificacion fallan no hay volumen y el motivo real llega al aviso; la ventana de metadatos cuenta como ATENCION los `.dcm` ilegibles y los cortes de CT sin
extension .dcm; lo que el DICOM no publica queda vacio, nunca un numero.

Revision de la tarea (dos revisores escepticos, hallazgos reproducidos): un subdirectorio `x.dcm` y los `._x.dcm` de macOS no cuentan como archivos dañados; solo los cortes de CT sin
`.dcm` DE LA SERIE QUE SE CARGA hacen decir «la serie puede estar incompleta» (los de otra serie son informativos); el aviso de no carga tambien cuenta los `.dcm` ilegibles y los cortes de CT
sin `.dcm` cuando hay un `.dcm` que no es CT, no se inventa un numero pasado de 2000 archivos («al menos N») y una falta de memoria se dice como tal; una carga que falla suelta los cortes
que leyo; y las excepciones sin texto (`MemoryError()`) siguen diciendo al menos su clase.

Sobre el rojo contra el codigo anterior: las pruebas usan atributos nuevos (`ilegibles`, `sin_extension`) solo donde hace falta; las de la conversion, la decodificacion, el pixel y el aviso de
no carga usan API que ya existia y caen por su asercion.
"""
import ast
import gc
import os
import shutil
import types
import weakref

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pydicom
import pytest
from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication, QMessageBox

from _corpus import CATPHAN, serie_catphan
from _formularios_imagenes import app  # noqa: F401  (fixture)
from _serie_sintetica import DESCRIPCION_AXIAL, escribir_corte, serie_axial
import data.ManejoDatos.catphan_TAC.leer_dicom as leer_dicom_mod
from analisisImagenes.catphan.serie import CT_IMAGE_STORAGE, adquisicion_de_serie, leer_serie
from pydicom.uid import generate_uid

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RT_STRUCT = "1.2.840.10008.5.1.4.1.1.481.3"


@pytest.fixture(autouse=True)
def _hay_qapplication(app):
    """Las pruebas del visor construyen widgets: la QApplication tiene que existir antes (Trampa 1)."""
    return app


def _visores_vivos():
    gc.collect()
    return sum(1 for o in gc.get_objects() if isinstance(o, leer_dicom_mod.VisualizadorDicom))


@pytest.fixture
def visor(monkeypatch):
    """El visor real con la deteccion de modulos y el cuadro de cortes sustituidos y la confirmacion de A.3 aceptada sin persona (Trampa 2). Al terminar la prueba (pase o falle), la receta de
    cierre de la Trampa 9: `hide(); close(); deleteLater()`, entregar los borrados diferidos, procesar eventos, `gc.collect()`; y comprueba que no queda ningun visor vivo."""
    from resources.utils.matplotlib_lazy import get_matplotlib_components
    antes = _visores_vivos()
    mpl = get_matplotlib_components()
    lienzo = mpl["FigureCanvas"](mpl["Figure"](figsize=(4, 4)))
    v = leer_dicom_mod.VisualizadorDicom(target_canvas=lienzo)
    monkeypatch.setattr(v, "mostrar_popup_cortes", lambda resultados: None)
    monkeypatch.setattr(leer_dicom_mod, "detectar_y_resolver_modulos", lambda ruta_dicom: ({}, {}))
    v.confirmador_de_carga = lambda parent, vol, equipo: True
    soporte = types.SimpleNamespace(v=v)            # pytest guarda el valor de cada fixture hasta DESPUES del cierre: si fuera el visor mismo, seguiria "vivo" al contarlo
    yield soporte
    soporte.v = None
    v.vol = None
    v.hide()
    v.close()
    v.deleteLater()
    lienzo.close()
    lienzo.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    del v, lienzo
    monkeypatch.undo()                  # el monkeypatch guarda una referencia al visor por cada `setattr` sobre la instancia
    assert _visores_vivos() <= antes, "la prueba dejo visores vivos (Trampa 9)"


def _avisos(monkeypatch):
    lista = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, titulo, texto, *a, **k: lista.append((titulo, texto)))
    return lista


class _FallaUnaVez(np.ndarray):
    """Un arreglo cuya PRIMERA conversion falla (la memoria que falta en ese instante, un tipo que no cabe...) y las siguientes funcionan: es lo que deja al descubierto el defecto de B5 --
    el manejador de antes volvia a convertir el volumen, esa vez sin escala, y lo dejaba como si fuera HU. Con un arreglo que fallara SIEMPRE, el manejador viejo tambien fallaba y la prueba pasaba."""
    llamadas = 0
    texto = "sin memoria para convertir a HU"           # "" = una excepcion SIN texto (`MemoryError()`)

    def astype(self, *a, **k):
        if _FallaUnaVez.llamadas == 0:
            _FallaUnaVez.llamadas += 1
            raise MemoryError(_FallaUnaVez.texto) if _FallaUnaVez.texto else MemoryError()
        return super().astype(*a, **k)


def _romper_la_conversion(monkeypatch, texto="sin memoria para convertir a HU"):
    """Rompe la PRIMERA conversion DESPUES de apilar (ruta estandar: `np.stack`; ruta optimizada: `np.empty` de tres dimensiones)."""
    _FallaUnaVez.llamadas = 0
    _FallaUnaVez.texto = texto
    stack, empty = np.stack, np.empty
    monkeypatch.setattr(np, "stack", lambda arrays, axis=0: stack(arrays, axis=axis).view(_FallaUnaVez))
    monkeypatch.setattr(np, "empty", lambda shape, dtype=float, *a, **k: empty(shape, dtype, *a, **k).view(_FallaUnaVez) if hasattr(shape, "__len__") and len(shape) == 3 else empty(shape, dtype, *a, **k))


def _forzar_ruta_optimizada(monkeypatch):
    monkeypatch.setattr(leer_dicom_mod, "_ram_libre_bytes", lambda: 1)


def _romper_la_decodificacion(monkeypatch, texto="no se pudo decodificar los pixeles (¿falta un decodificador?)"):
    def _falla(self):
        raise RuntimeError(texto) if texto else RuntimeError()
    monkeypatch.setattr(pydicom.dataset.Dataset, "pixel_array", property(_falla))
    return texto


# ---------------------------------------------------------------------------------------------------- B5: la conversion y la decodificacion
class TestSiLaConversionAHuFalla:

    @pytest.mark.parametrize("optimizada", [False, True], ids=["ruta estandar", "ruta optimizada"])
    def test_no_queda_volumen_con_unidades_equivocadas_y_el_motivo_es_el_real(self, tmp_path, monkeypatch, optimizada):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        if optimizada:
            _forzar_ruta_optimizada(monkeypatch)
        _romper_la_conversion(monkeypatch)
        vol = leer_dicom_mod.DicomVolume(carpeta)
        assert vol.volumen_hu is None, "antes quedaba el volumen CRUDO sin escala como si fuera HU"
        assert vol.volumen is None
        assert vol.get_num_cortes() == 0
        assert "sin memoria para convertir a HU" in (vol.error_de_carga or ""), vol.error_de_carga

    @pytest.mark.parametrize("optimizada", [False, True], ids=["ruta estandar", "ruta optimizada"])
    def test_el_visor_no_instala_nada_y_dice_el_motivo(self, tmp_path, monkeypatch, visor, optimizada):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        v = visor.v
        avisos = _avisos(monkeypatch)
        if optimizada:
            _forzar_ruta_optimizada(monkeypatch)
        _romper_la_conversion(monkeypatch)
        v.visualizar_imagen_cargada(carpeta)
        assert v.vol is None and v.ruta_carpeta is None
        assert len(avisos) == 1 and "sin memoria para convertir a HU" in avisos[0][1] and "sin detalle" not in avisos[0][1], avisos

    def test_sin_fallo_la_conversion_es_la_de_siempre(self, tmp_path):
        vol = leer_dicom_mod.DicomVolume(serie_axial(str(tmp_path / "s"), n=5))
        assert vol.error_de_carga is None and vol.volumen_hu is not None and vol.volumen_hu.dtype == np.float32
        assert float(vol.volumen_hu.min()) >= -1024 + 900 - 1 and float(vol.volumen_hu.max()) <= -1024 + 1100


class TestSiLaDecodificacionDeLosPixelesFalla:

    @pytest.mark.parametrize("optimizada", [False, True], ids=["ruta estandar", "ruta optimizada"])
    def test_el_error_de_carga_es_el_motivo_real_y_no_sin_detalle(self, tmp_path, monkeypatch, optimizada):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        if optimizada:
            _forzar_ruta_optimizada(monkeypatch)
        texto = _romper_la_decodificacion(monkeypatch)
        vol = leer_dicom_mod.DicomVolume(carpeta)
        assert vol.volumen_hu is None and texto in (vol.error_de_carga or ""), vol.error_de_carga
        mensaje = leer_dicom_mod.motivo_de_no_carga(carpeta, vol.error_de_carga)
        assert texto in mensaje and "sin detalle" not in mensaje, mensaje

    @pytest.mark.parametrize("optimizada", [False, True], ids=["ruta estandar", "ruta optimizada"])
    def test_el_aviso_del_visor_dice_la_causa(self, tmp_path, monkeypatch, visor, optimizada):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        v = visor.v
        avisos = _avisos(monkeypatch)
        if optimizada:
            _forzar_ruta_optimizada(monkeypatch)
        texto = _romper_la_decodificacion(monkeypatch)
        v.visualizar_imagen_cargada(carpeta)
        assert len(avisos) == 1 and texto in avisos[0][1] and "sin detalle" not in avisos[0][1], avisos


class TestUnaExcepcionSinTexto:
    """Revision (T-H2): `str(MemoryError())` es vacio; sin el respaldo `or type(e).__name__` volvia el «Detalle: sin detalle» que B5 cierra."""

    @pytest.mark.parametrize("optimizada", [False, True], ids=["ruta estandar", "ruta optimizada"])
    def test_la_conversion_sin_texto_dice_al_menos_su_clase(self, tmp_path, monkeypatch, optimizada):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        if optimizada:
            _forzar_ruta_optimizada(monkeypatch)
        _romper_la_conversion(monkeypatch, texto="")
        vol = leer_dicom_mod.DicomVolume(carpeta)
        assert vol.volumen_hu is None and vol.error_de_carga == "MemoryError", repr(vol.error_de_carga)
        assert "memoria" in leer_dicom_mod.motivo_de_no_carga(carpeta, vol.error_de_carga)

    @pytest.mark.parametrize("optimizada", [False, True], ids=["ruta estandar", "ruta optimizada"])
    def test_la_decodificacion_sin_texto_dice_al_menos_su_clase(self, tmp_path, monkeypatch, optimizada):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        if optimizada:
            _forzar_ruta_optimizada(monkeypatch)
        _romper_la_decodificacion(monkeypatch, texto="")
        vol = leer_dicom_mod.DicomVolume(carpeta)
        assert vol.volumen_hu is None and vol.error_de_carga == "RuntimeError", repr(vol.error_de_carga)
        assert "sin detalle" not in leer_dicom_mod.motivo_de_no_carga(carpeta, vol.error_de_carga)


class TestUnaFaltaDeMemoriaSeDiceComoTal:

    def test_el_motivo_de_la_falta_de_memoria(self, tmp_path):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        for texto in ("MemoryError", "Unable to allocate 1.23 GiB for an array with shape (300, 512, 512) and data type uint16"):
            m = leer_dicom_mod.motivo_de_no_carga(carpeta, texto)
            assert m.startswith("No hay memoria suficiente para cargar esta carpeta.") and texto in m and "como una serie de CT" not in m, m

    def test_otro_error_no_se_confunde_con_memoria(self, tmp_path):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        assert leer_dicom_mod.motivo_de_no_carga(carpeta, "boom").startswith("No se pudo cargar la carpeta como una serie de CT.")


class TestUnaCargaQueFallaSueltaLoQueLeyo:
    """Revision (P-H5): tras un fallo en `np.stack` el volumen fallido retenia los arreglos decodificados y el `PixelData` de cada corte (2x el volumen crudo) mientras el aviso modal estaba
    abierto -- justo cuando falta memoria y la carpeta anterior sigue activa."""

    @pytest.mark.parametrize("optimizada", [False, True], ids=["ruta estandar", "ruta optimizada"])
    def test_no_quedan_cortes_ni_arreglos_vivos(self, tmp_path, monkeypatch, optimizada):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        if optimizada:
            _forzar_ruta_optimizada(monkeypatch)
        decodificados = []

        def decodificar(self):
            if getattr(self, "_pixel_array", None) is None:
                self._pixel_array = np.zeros((64, 64), dtype=np.int16)
                decodificados.append(weakref.ref(self._pixel_array))
            return self._pixel_array
        monkeypatch.setattr(pydicom.dataset.Dataset, "pixel_array", property(decodificar))
        monkeypatch.setattr(np, "stack", lambda arrays, axis=0: (_ for _ in ()).throw(MemoryError("sin memoria al apilar")))
        monkeypatch.setattr(np, "empty", lambda *a, **k: (_ for _ in ()).throw(MemoryError("sin memoria al apilar")))
        vol = leer_dicom_mod.DicomVolume(carpeta)
        gc.collect()
        assert vol.volumen is None and vol.volumen_hu is None and "sin memoria al apilar" in (vol.error_de_carga or "")
        assert vol.cortes == [], "el volumen fallido sigue guardando los cortes leidos"
        assert decodificados and all(r() is None for r in decodificados), "un arreglo decodificado sigue vivo"


def _funcion(arbol, clase, nombre):
    for n in ast.walk(arbol):
        if isinstance(n, ast.ClassDef) and n.name == clase:
            for f in n.body:
                if isinstance(f, ast.FunctionDef) and f.name == nombre:
                    return f
    raise AssertionError(f"{clase}.{nombre} no existe")


@pytest.mark.parametrize("metodo", ["_load_standard_volume", "_load_large_volume", "_load_dicoms"])
def test_ningun_fallo_de_la_carga_deja_un_volumen_hu_que_no_sea_none(metodo):
    """Tripwire (B5): en el manejador de excepciones de cada ruta, el motivo se guarda en `error_de_carga` y se llama a `_soltar_lo_leido()` -- que deja `volumen`/`volumen_hu` en `None` y suelta
    los cortes leidos--; nunca `volumen_hu` asignado a otra cosa."""
    with open(os.path.join(RAIZ, "data/ManejoDatos/catphan_TAC/leer_dicom.py"), encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    manejadores = [n for n in ast.walk(_funcion(arbol, "DicomVolume", metodo)) if isinstance(n, ast.ExceptHandler)]
    assert manejadores, "la prueba no encuentra el manejador (vacua)"
    for m in manejadores:
        asignados, llamadas = {}, set()
        for n in ast.walk(m):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
                        asignados[t.attr] = n.value
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "self":
                llamadas.add(n.func.attr)
        assert "volumen_hu" not in asignados, f"{metodo}: el manejador asigna volumen_hu a mano (que sea `_soltar_lo_leido()` quien lo deja en None)"
        assert "_soltar_lo_leido" in llamadas, f"{metodo}: el manejador no suelta lo leido"
        assert "error_de_carga" in asignados, f"{metodo}: el manejador no dice el motivo en error_de_carga"
    soltar = _funcion(arbol, "DicomVolume", "_soltar_lo_leido")
    asignados = {t.attr: n.value for n in ast.walk(soltar) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Attribute)}
    assert all(isinstance(asignados.get(k), ast.Constant) and asignados[k].value is None for k in ("volumen", "volumen_hu")), asignados
    assert isinstance(asignados.get("cortes"), ast.List) and not asignados["cortes"].elts, "no deja `cortes` vacio"


# ---------------------------------------------------------------------------------------------------- B6: lo que la carga dejo fuera
def _quitar_extension(carpeta, nombre, nuevo):
    os.rename(os.path.join(carpeta, nombre), os.path.join(carpeta, nuevo))


def _filas_carpeta(vol):
    from data.ManejoDatos.catphan_TAC.ventana_metadatos import ATENCION, INFO, construir_modelo_ventana
    return construir_modelo_ventana(vol, None).carpeta, ATENCION, INFO


class TestCortesSinExtensionDcm:

    def test_se_cuentan_se_nombran_y_la_ventana_los_pone_como_atencion(self, tmp_path):
        carpeta = serie_axial(str(tmp_path / "s"), n=6)
        _quitar_extension(carpeta, "corte_1.dcm", "corte_1")
        _quitar_extension(carpeta, "corte_4.dcm", "1.2.840.99.4")                 # nombre tipo UID: tiene puntos pero no termina en .dcm
        serie = leer_serie(carpeta)
        assert len(serie.cortes) == 4 and serie.sin_extension == ["1.2.840.99.4", "corte_1"] and serie.ilegibles == 0 and serie.no_imagen == 0
        vol = leer_dicom_mod.DicomVolume(carpeta)
        assert vol.sin_extension == serie.sin_extension and vol.get_num_cortes() == 4
        filas, ATENCION, INFO = _filas_carpeta(vol)
        atencion = [t for nivel, t in filas if nivel == ATENCION and "no termina en .dcm" in t]
        assert len(atencion) == 1 and "2 corte(s) de CT" in atencion[0] and "'1.2.840.99.4'" in atencion[0] and "'corte_1'" in atencion[0], filas
        assert "incompleta" in atencion[0]

    def test_una_carpeta_completa_no_dice_nada(self, tmp_path):
        vol = leer_dicom_mod.DicomVolume(serie_axial(str(tmp_path / "s"), n=5))
        filas, ATENCION, _ = _filas_carpeta(vol)
        assert vol.sin_extension == [] and vol.ilegibles == 0 and not [t for nivel, t in filas if nivel == ATENCION]

    def test_un_archivo_que_no_es_dicom_no_cuenta(self, tmp_path):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        (tmp_path / "s" / "LEEME").write_text("notas de la exportacion")
        (tmp_path / "s" / "otra.txt").write_text("x")
        serie = leer_serie(carpeta)
        assert serie.sin_extension == [] and serie.sin_extension_otras == []

    def test_un_dicom_que_no_es_corte_de_ct_no_cuenta(self, tmp_path):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        ds = pydicom.dcmread(os.path.join(carpeta, "corte_0.dcm"))
        ds.SOPClassUID = RT_STRUCT
        ds.file_meta.MediaStorageSOPClassUID = RT_STRUCT
        ds.save_as(os.path.join(carpeta, "RTSTRUCT_sin_extension"))
        serie = leer_serie(carpeta)
        assert serie.sin_extension == [] and serie.sin_extension_otras == []

    def test_un_subdirectorio_no_cuenta(self, tmp_path):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        os.makedirs(os.path.join(carpeta, "subcarpeta_sin_punto"))
        assert leer_serie(carpeta).sin_extension == []

    def test_si_ninguno_termina_en_dcm_el_aviso_de_no_carga_los_nombra(self, tmp_path, monkeypatch, visor):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        for i in range(5):
            _quitar_extension(carpeta, f"corte_{i}.dcm", f"1.2.840.99.{i}")      # los cortes con nombre de UID: antes «no tiene archivos DICOM»
        vol = leer_dicom_mod.DicomVolume(carpeta)
        assert vol.volumen_hu is None
        mensaje = leer_dicom_mod.motivo_de_no_carga(carpeta, vol.error_de_carga)
        assert "5 archivo(s) sin extensión .dcm" in mensaje and "'1.2.840.99.0'" in mensaje, mensaje
        v = visor.v
        avisos = _avisos(monkeypatch)
        v.visualizar_imagen_cargada(carpeta)
        assert len(avisos) == 1 and "5 archivo(s) sin extensión .dcm" in avisos[0][1]


class TestLoQueNoEsUnArchivoDañado:
    """Revision (P-H3 / T-H4): HEAD contaba un subdirectorio llamado `x.dcm` y los `._x.dcm` de macOS como «no son imagen CT» (informativo); con CD.3 se volvieron «archivos dañados»
    (ATENCION): una falsa alarma en cada carga desde una memoria FAT/exFAT escrita en un Mac."""

    def test_un_subdirectorio_llamado_x_dcm_no_cuenta_en_nada(self, tmp_path):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        os.makedirs(os.path.join(carpeta, "subcarpeta.dcm"))
        serie = leer_serie(carpeta)
        assert serie.ilegibles == 0 and serie.no_imagen == 0 and len(serie.cortes) == 5
        filas, ATENCION, _ = _filas_carpeta(leer_dicom_mod.DicomVolume(carpeta))
        assert not [t for nivel, t in filas if nivel == ATENCION]

    def test_los_archivos_de_recurso_de_macos_son_informativos(self, tmp_path):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        for i in range(5):
            with open(os.path.join(carpeta, f"._corte_{i}.dcm"), "wb") as f:
                f.write(b"\x00\x05\x16\x07" + b"\x00" * 60)               # cabecera AppleDouble
        serie = leer_serie(carpeta)
        assert serie.ilegibles == 0 and serie.no_imagen == 5 and len(serie.cortes) == 5
        filas, ATENCION, INFO = _filas_carpeta(leer_dicom_mod.DicomVolume(carpeta))
        assert not [t for nivel, t in filas if nivel == ATENCION] and [t for nivel, t in filas if nivel == INFO and "5 archivo(s) que no son imagen CT" in t]

    def test_un_dcm_de_verdad_dañado_sigue_siendo_ilegible_aunque_se_parezca_a_un_recurso(self, tmp_path):
        """Solo el prefijo `._` exime: un `.dcm` con otro nombre y bytes basura es un archivo dañado."""
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        with open(os.path.join(carpeta, "_roto.dcm"), "wb") as f:
            f.write(b"basura" * 20)
        assert leer_serie(carpeta).ilegibles == 1


class TestCortesSinExtensionDeOtraSerie:
    """Revision (T-H5): un localizador de OTRA serie sin la extension .dcm no hace incompleta la serie que se carga; no dispara «la serie puede estar incompleta»."""

    def _con_localizador_sin_extension(self, tmp_path):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        escribir_corte(os.path.join(carpeta, "localizador_otra_serie"), generate_uid(), -135.5, 110, 20, 2.0, DESCRIPCION_AXIAL, ["ORIGINAL", "PRIMARY", "AXIAL"], 1)
        return carpeta

    def test_se_cuenta_aparte_y_no_hace_incompleta_la_serie(self, tmp_path):
        carpeta = self._con_localizador_sin_extension(tmp_path)
        serie = leer_serie(carpeta)
        assert len(serie.cortes) == 5 and serie.sin_extension == [] and serie.sin_extension_otras == ["localizador_otra_serie"]
        vol = leer_dicom_mod.DicomVolume(carpeta)
        assert vol.sin_extension == [] and vol.sin_extension_otras == ["localizador_otra_serie"]

    def test_la_ventana_lo_dice_como_informacion_y_no_como_atencion(self, tmp_path):
        filas, ATENCION, INFO = _filas_carpeta(leer_dicom_mod.DicomVolume(self._con_localizador_sin_extension(tmp_path)))
        assert not [t for nivel, t in filas if nivel == ATENCION], filas
        info = [t for nivel, t in filas if nivel == INFO and "de otra serie" in t]
        assert len(info) == 1 and "1 corte(s) de CT de otra serie" in info[0] and "'localizador_otra_serie'" in info[0] and "no pertenecen a la serie que se carga" in info[0]

    def test_los_de_la_serie_elegida_siguen_siendo_atencion_aunque_haya_de_otra(self, tmp_path):
        carpeta = self._con_localizador_sin_extension(tmp_path)
        _quitar_extension(carpeta, "corte_1.dcm", "corte_1")
        serie = leer_serie(carpeta)
        assert serie.sin_extension == ["corte_1"] and serie.sin_extension_otras == ["localizador_otra_serie"]


class TestLaDeteccionDeCortesYArchivos:

    def test_la_extension_en_mayuscula_se_lee(self, tmp_path):
        """Revision (T-H3, MC): `.DCM` y `.Dcm` son archivos .dcm; sin `.lower()` se declaraban «sin extension» y la carga fallaba."""
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        for i, ext in enumerate(["DCM", "Dcm", "dCm", "dcm", "DCM"]):
            os.rename(os.path.join(carpeta, f"corte_{i}.dcm"), os.path.join(carpeta, f"CORTE_{i}.{ext}"))
        serie = leer_serie(carpeta)
        assert len(serie.cortes) == 5 and serie.sin_extension == [] and serie.ilegibles == 0

    def test_un_archivo_que_no_se_puede_abrir_no_tumba_la_carga(self, tmp_path, monkeypatch):
        """Revision (T-H3, ME): un archivo ajeno sin permiso de lectura (o cualquier error al abrirlo) no apaga la carga entera."""
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        (tmp_path / "s" / "bloqueado_sin_permiso").write_bytes(b"x")
        original = pydicom.dcmread

        def con_permiso_denegado(ruta, *a, **k):
            if str(ruta).endswith("bloqueado_sin_permiso"):
                raise PermissionError(13, "Permission denied")
            return original(ruta, *a, **k)
        monkeypatch.setattr(pydicom, "dcmread", con_permiso_denegado)
        serie = leer_serie(carpeta)
        assert len(serie.cortes) == 5 and serie.sin_extension == []


class TestElAvisoDeNoCargaCuentaLoQueHay:
    """Revision (P-H2 / T-H1): con al menos un `.dcm` pero ninguno legible como corte de CT, el aviso decia siempre «ninguno es una imagen de CT: pueden ser estructuras de radioterapia»:
    falso con archivos dañados (una copia de red interrumpida) y mudo ante cortes de CT sin `.dcm` que bastaria renombrar."""

    def _rtstruct(self, ruta):
        ds = pydicom.dcmread(ruta)
        ds.SOPClassUID = RT_STRUCT
        ds.file_meta.MediaStorageSOPClassUID = RT_STRUCT
        return ds

    def _mensaje(self, carpeta):
        vol = leer_dicom_mod.DicomVolume(carpeta)
        assert vol.volumen_hu is None
        return leer_dicom_mod.motivo_de_no_carga(carpeta, vol.error_de_carga)

    def test_todos_los_dcm_ilegibles_se_dicen_dañados_y_no_estructuras_de_radioterapia(self, tmp_path):
        carpeta = str(tmp_path / "s")
        os.makedirs(carpeta)
        for i in range(4):
            (tmp_path / "s" / f"corte_{i}.dcm").write_bytes(b"copia interrumpida" * 5)
        m = self._mensaje(carpeta)
        assert "4 no se pudieron leer (dañados o incompletos)" in m and "ninguno se pudo leer como imagen de CT" in m, m
        assert "estructuras de radioterapia" not in m, m

    def test_un_rtstruct_mas_cortes_de_ct_sin_dcm_los_nombra_y_dice_que_hay_que_renombrar(self, tmp_path):
        origen = serie_axial(str(tmp_path / "origen"), n=6)
        carpeta = str(tmp_path / "s")
        os.makedirs(carpeta)
        self._rtstruct(os.path.join(origen, "corte_0.dcm")).save_as(os.path.join(carpeta, "RS.dcm"))
        for i in range(1, 6):
            shutil.copy(os.path.join(origen, f"corte_{i}.dcm"), os.path.join(carpeta, f"CT.1.2.840.99.{i}"))
        self._rtstruct(os.path.join(origen, "corte_0.dcm")).save_as(os.path.join(carpeta, "RS_sin_extension"))        # un DICOM que no es CT, sin .dcm: no es un corte que falte
        (tmp_path / "s" / "notas.txt").write_text("no es DICOM")
        m = self._mensaje(carpeta)
        assert "ninguno es una imagen de CT" in m and "Además hay 5 corte(s) de CT cuyo archivo no termina en .dcm" in m, m
        assert "'CT.1.2.840.99.1'" in m and "y 2 más" in m and "Renómbrelos con la extensión .dcm" in m, m

    def test_dañados_y_estructuras_se_cuentan_cada_uno(self, tmp_path):
        origen = serie_axial(str(tmp_path / "origen"), n=1)
        carpeta = str(tmp_path / "s")
        os.makedirs(carpeta)
        self._rtstruct(os.path.join(origen, "corte_0.dcm")).save_as(os.path.join(carpeta, "RS.dcm"))
        (tmp_path / "s" / "roto_1.dcm").write_bytes(b"x" * 30)
        (tmp_path / "s" / "roto_2.dcm").write_bytes(b"y" * 30)
        m = self._mensaje(carpeta)
        assert "La carpeta tiene 3 archivo(s) .dcm, pero ninguno se pudo leer como imagen de CT: 2 no se pudieron leer (dañados o incompletos) y 1 no son imagen de CT" in m, m
        assert "Además" not in m

    def test_solo_estructuras_de_radioterapia_es_el_texto_de_siempre(self, tmp_path):
        origen = serie_axial(str(tmp_path / "origen"), n=1)
        carpeta = str(tmp_path / "s")
        os.makedirs(carpeta)
        self._rtstruct(os.path.join(origen, "corte_0.dcm")).save_as(os.path.join(carpeta, "RS.dcm"))
        m = self._mensaje(carpeta)
        assert m == ("La carpeta tiene 1 archivo(s) .dcm, pero ninguno es una imagen de CT (CT Image Storage): pueden ser estructuras de radioterapia u otros objetos DICOM."), m

    def test_los_archivos_de_recurso_de_macos_no_se_cuentan_como_dañados(self, tmp_path):
        origen = serie_axial(str(tmp_path / "origen"), n=1)
        carpeta = str(tmp_path / "s")
        os.makedirs(carpeta)
        self._rtstruct(os.path.join(origen, "corte_0.dcm")).save_as(os.path.join(carpeta, "RS.dcm"))
        (tmp_path / "s" / "._RS.dcm").write_bytes(b"\x00\x05\x16\x07" + b"\x00" * 60)
        m = self._mensaje(carpeta)
        assert "no se pudieron leer" not in m and "ninguno es una imagen de CT" in m, m


class TestElTopeDeArchivosRevisados:
    """Revision (P-H1): el aviso topaba en 200 y decia «Hay 200 archivo(s)» aunque hubiera 300; ahora el tope es 2000 y, pasado, el aviso dice «al menos N»."""

    def test_pasado_el_tope_dice_al_menos(self, tmp_path, monkeypatch):
        monkeypatch.setattr(leer_dicom_mod, "TOPE_ARCHIVOS_A_REVISAR", 5)
        carpeta = serie_axial(str(tmp_path / "s"), n=8)
        for i in range(8):
            _quitar_extension(carpeta, f"corte_{i}.dcm", f"1.2.840.99.{i}")
        m = leer_dicom_mod.motivo_de_no_carga(carpeta, "No hay cortes de CT Image Storage")
        assert "Hay al menos 5 archivo(s) sin extensión .dcm" in m, m

    def test_sin_pasar_el_tope_dice_el_numero_exacto(self, tmp_path, monkeypatch):
        monkeypatch.setattr(leer_dicom_mod, "TOPE_ARCHIVOS_A_REVISAR", 5)
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        for i in range(5):
            _quitar_extension(carpeta, f"corte_{i}.dcm", f"1.2.840.99.{i}")
        m = leer_dicom_mod.motivo_de_no_carga(carpeta, "No hay cortes de CT Image Storage")
        assert "Hay 5 archivo(s) sin extensión .dcm" in m and "al menos" not in m, m

    def test_el_tope_tambien_aplica_a_los_cortes_sin_dcm_del_aviso_con_un_rtstruct(self, tmp_path, monkeypatch):
        monkeypatch.setattr(leer_dicom_mod, "TOPE_ARCHIVOS_A_REVISAR", 3)
        origen = serie_axial(str(tmp_path / "origen"), n=7)
        carpeta = str(tmp_path / "s")
        os.makedirs(carpeta)
        ds = pydicom.dcmread(os.path.join(origen, "corte_0.dcm"))
        ds.SOPClassUID = RT_STRUCT
        ds.file_meta.MediaStorageSOPClassUID = RT_STRUCT
        ds.save_as(os.path.join(carpeta, "RS.dcm"))
        for i in range(1, 7):
            shutil.copy(os.path.join(origen, f"corte_{i}.dcm"), os.path.join(carpeta, f"CT.1.2.840.99.{i}"))
        m = leer_dicom_mod.motivo_de_no_carga(carpeta, "No hay cortes de CT Image Storage")
        assert "Además hay al menos 3 corte(s) de CT" in m, m

    def test_el_tope_real_es_de_dos_mil(self):
        assert leer_dicom_mod.TOPE_ARCHIVOS_A_REVISAR == 2000

    def test_un_dicom_sin_preambulo_y_sin_punto_en_el_nombre_se_cuenta_por_su_nombre(self, tmp_path):
        """Revision (T-H3, MF): un DICOM sin el preambulo «DICM» (`dcmread` sin `force` lo rechaza) y con nombres sin punto (`IM0000`...) no se reconoce por contenido; el respaldo por nombre sigue diciendolo."""
        origen = serie_axial(str(tmp_path / "origen"), n=5)
        carpeta = str(tmp_path / "s")
        os.makedirs(carpeta)
        for i in range(5):
            ds = pydicom.dcmread(os.path.join(origen, f"corte_{i}.dcm"))
            ds.preamble = None
            ds.save_as(os.path.join(carpeta, f"IM{i:04d}"), write_like_original=True)
        assert not leer_dicom_mod.es_archivo_dicom(os.path.join(carpeta, "IM0000")), "el caso ya no es un DICOM sin preambulo: la prueba no mide lo que dice"
        m = leer_dicom_mod.motivo_de_no_carga(carpeta, "No hay cortes de CT Image Storage")
        assert "Hay 5 archivo(s) sin extensión .dcm, por ejemplo 'IM0000'." in m, m


class TestLosTextosDeLaVentana:
    """Revision (T-H3, MB y MD): la arimetica de «y N mas» y las frases completas de las dos filas de ATENCION."""

    @staticmethod
    def _vol(**k):
        base = dict(adquisicion={}, series_descartadas={}, detalle_series_descartadas={}, no_imagen=0, avisos=[], ilegibles=0, sin_extension=[], sin_extension_otras=[])
        base.update(k)
        return types.SimpleNamespace(**base)

    def _filas(self, vol):
        from data.ManejoDatos.catphan_TAC.ventana_metadatos import ATENCION, INFO, construir_modelo_ventana
        return construir_modelo_ventana(vol, None).carpeta, ATENCION, INFO

    def test_mas_de_tres_cortes_sin_extension_dicen_cuantos_mas(self):
        filas, ATENCION, _ = self._filas(self._vol(sin_extension=[f"c{i}" for i in range(7)]))
        t = next(t for nivel, t in filas if nivel == ATENCION)
        assert t == ("7 corte(s) de CT no se leyeron porque su archivo no termina en .dcm ('c0', 'c1', 'c2' y 4 más): la serie puede estar incompleta. "
                     "Renómbrelos con la extensión .dcm y cargue la carpeta de nuevo."), t

    def test_hasta_tres_no_llevan_y_mas(self):
        filas, ATENCION, _ = self._filas(self._vol(sin_extension=["a", "b", "c"]))
        t = next(t for nivel, t in filas if nivel == ATENCION)
        assert "('a', 'b', 'c')" in t and " más" not in t.replace("la serie puede estar incompleta", ""), t

    def test_los_archivos_ilegibles_dicen_la_frase_completa(self):
        filas, ATENCION, _ = self._filas(self._vol(ilegibles=3))
        t = next(t for nivel, t in filas if nivel == ATENCION)
        assert t == "3 archivo(s) .dcm no se pudieron leer (dañados o incompletos) y se ignoraron: la serie puede estar incompleta.", t

    def test_los_de_otra_serie_son_informacion_y_con_mas_de_tres_dicen_cuantos_mas(self):
        filas, ATENCION, INFO = self._filas(self._vol(sin_extension_otras=[f"o{i}" for i in range(5)]))
        assert not [t for nivel, t in filas if nivel == ATENCION]
        t = next(t for nivel, t in filas if nivel == INFO and "de otra serie" in t)
        assert t == "5 corte(s) de CT de otra serie tampoco se leyeron porque su archivo no termina en .dcm ('o0', 'o1', 'o2' y 2 más): no pertenecen a la serie que se carga.", t

    def test_una_carpeta_sin_nada_fuera_no_dice_nada(self):
        filas, ATENCION, _ = self._filas(self._vol())
        assert not [t for nivel, t in filas if nivel == ATENCION]


class TestDcmIlegibles:

    def test_se_cuentan_aparte_y_la_ventana_no_los_llama_normales(self, tmp_path):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        with open(os.path.join(carpeta, "roto.dcm"), "wb") as f:
            f.write(b"esto no es un archivo DICOM" * 10)
        serie = leer_serie(carpeta)
        assert serie.ilegibles == 1 and serie.no_imagen == 0 and len(serie.cortes) == 5
        vol = leer_dicom_mod.DicomVolume(carpeta)
        assert vol.ilegibles == 1 and vol.no_imagen == 0
        filas, ATENCION, INFO = _filas_carpeta(vol)
        assert [t for nivel, t in filas if nivel == ATENCION and "1 archivo(s) .dcm no se pudieron leer" in t], filas
        assert not [t for nivel, t in filas if "es normal" in t], "un archivo ilegible no es «normal»"

    def test_un_dicom_que_no_es_ct_sigue_siendo_normal(self, tmp_path):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        ds = pydicom.dcmread(os.path.join(carpeta, "corte_0.dcm"))
        ds.SOPClassUID = RT_STRUCT
        ds.file_meta.MediaStorageSOPClassUID = RT_STRUCT
        ds.save_as(os.path.join(carpeta, "rtstruct.dcm"))
        serie = leer_serie(carpeta)
        assert serie.no_imagen == 1 and serie.ilegibles == 0
        filas, ATENCION, INFO = _filas_carpeta(leer_dicom_mod.DicomVolume(carpeta))
        assert [t for nivel, t in filas if nivel == INFO and "es normal" in t] and not [t for nivel, t in filas if nivel == ATENCION]


# ---------------------------------------------------------------------------------------------------- (d) el pixel
def _sin_pixel_spacing(carpeta, solo=None):
    for nombre in sorted(os.listdir(carpeta)):
        if solo and nombre not in solo:
            continue
        ruta = os.path.join(carpeta, nombre)
        ds = pydicom.dcmread(ruta)
        del ds["PixelSpacing"]
        ds.save_as(ruta)


class TestLoQueElDicomNoPublicaQuedaVacio:

    def test_sin_pixel_spacing_el_tamano_de_pixel_queda_vacio(self, tmp_path):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        _sin_pixel_spacing(carpeta)
        serie = leer_serie(carpeta)
        assert serie.pixel_mm is None, "antes (1.0, 1.0): un tamaño de pixel inventado"
        adq = adquisicion_de_serie(serie)
        assert adq["pixel_mm"] is None
        from analisisImagenes.catphan.descripcion import NO_PUBLICADO
        from data.ManejoDatos.catphan_TAC.ventana_metadatos import construir_modelo_ventana
        modelo = construir_modelo_ventana(leer_dicom_mod.DicomVolume(carpeta), None)
        assert dict(modelo.adquisicion)["Píxel [mm]"] == NO_PUBLICADO

    def test_con_pixel_spacing_se_dice_el_que_publica(self, tmp_path):
        serie = leer_serie(serie_axial(str(tmp_path / "s"), n=5))
        assert serie.pixel_mm == (1.0, 1.0) and adquisicion_de_serie(serie)["pixel_mm"] == 1.0

    def test_pixel_spacing_en_un_corte_si_y_en_otros_no_es_una_serie_no_uniforme(self, tmp_path):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        _sin_pixel_spacing(carpeta, solo={"corte_2.dcm"})
        with pytest.raises(ValueError, match="no es uniforme"):
            leer_serie(carpeta)


# ---------------------------------------------------------------------------------------------------- las series reales
CLAVES = ["TOMOGRAFO", "HALCYON_JUN", "HALCYON_236", "HALCYON_SEP", "IX_DIC", "MIXTA"]


@pytest.mark.parametrize("clave", CLAVES)
def test_las_series_reales_no_dejan_nada_fuera(clave):
    """Control: ninguna de las seis carpetas reales tiene cortes de CT sin .dcm ni archivos .dcm ilegibles (si no, la ventana de cada carga real mostraria una atencion que no existia)."""
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    serie = leer_serie(ruta)
    assert serie.ilegibles == 0 and serie.sin_extension == [], (clave, serie.ilegibles, serie.sin_extension)
    assert serie.pixel_mm is not None
