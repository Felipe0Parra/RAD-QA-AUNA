"""CD.1 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, B1 y B2): cargar otra carpeta o cancelar el selector no deja la pantalla a medias.

Antes `visualizar_imagen_cargada` instalaba el volumen nuevo y abria el `LoadingDialog` modal sin `try/finally` y sin acotar `idx_actual` (V2 midio: de 122 cortes con el deslizador en 100 a una
serie de 70, `TypeError` en el dibujo, el cuadro de carga queda visible y modal, `imagen_cargada` no se emite, la etiqueta dice «Corte: 101/122» y recargar apila otro dialogo), y cancelar el
selector asignaba `''` a `ruta_carpeta` con el volumen anterior activo.

Ahora, o la carpeta nueva queda instalada ENTERA (corte 0 de la serie nueva, deslizadores, ayudas y etiquetas de la serie nueva, parametros de adquisicion, dialogo cerrado), o la anterior sigue activa
INTACTA (volumen, ruta, corte, deslizadores con sus rangos y ayudas, etiquetas, lienzo, orientacion, giro, resultados, parametros y controles) y se avisa con el motivo; cancelar el selector no cambia
nada. La instalacion termina con el `try`: lo que viene despues solo ANUNCIA la carpeta ya instalada (la señal `imagen_cargada`) y muestra el cuadro informativo de cortes, y un fallo de ese cuadro no
deshace una instalacion que ya termino. El volumen anterior NO se guarda vivo durante la deteccion de modulos (medido: subia el pico de memoria de la carga hasta +205 MB, justo lo que C.2 habia bajado):
se guarda su ruta y la firma de su serie, y si hace falta volver se vuelve a leer la carpeta y se comprueba que sigue siendo LA MISMA serie (si la carpeta cambio en disco, el visor queda sin carpeta
cargada y lo dice). Los marcos del rastro de la excepcion se sueltan antes de volver a leer (retenian el volumen nuevo y el pico sumaba las dos series).

Series sinteticas de `_serie_sintetica` (cortes de 64 x 64; la serie «nueva» con otra semilla y otro rango de pixeles para que el lienzo y los rangos de la ventana las distingan); la deteccion de
modulos (pylinac, que tiene sus propias pruebas) y el cuadro de cortes se sustituyen, y la confirmacion de A.3 se acepta sin persona (Trampa 2). Los fallos se provocan en tres puntos: la
deteccion, el dibujo y el ajuste de la ventana.
"""
import ast
import gc
import hashlib
import os
import shutil
import weakref

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pydicom
import pytest
from pydicom.uid import generate_uid
from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox
from PyQt5.QtTest import QTest

from _formularios_imagenes import app  # noqa: F401  (fixture)
from _serie_sintetica import serie_axial
import data.ManejoDatos.catphan_TAC.leer_dicom as leer_dicom_mod
import services.registro_errores as registro

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DicomVolume = leer_dicom_mod.DicomVolume          # la clase real: una prueba la sustituye por una funcion mientras corre
_AUSENTE = "<ausente>"
ATRIBUTOS = ("orientacion", "roll_deg", "kv", "ma", "espesor_corte", "cortes", "resultados", "rango_ventana")
SERIE_NUEVA = dict(semilla=7, rango_pixeles=(100, 3000), kv=100, ma=200, espesor=3.0)    # otros pixeles, otro rango de HU y otra adquisicion que la anterior (900-1100, 120 kV, 343 mA, 2.0 mm)
PUNTOS_DE_FALLO = [
    ("deteccion", RuntimeError("fallo simulado de pylinac")),
    ("deteccion", ValueError("serie rara")),
    ("deteccion", TypeError("el tipo del defecto que midio V2")),
    ("deteccion", MemoryError("sin memoria")),
    ("dibujo", TypeError("Image data of dtype object cannot be converted to float")),
    ("ventana", RuntimeError("fallo al derivar el rango de la ventana")),
]
IDS_DE_FALLO = [f"{punto}-{type(e).__name__}" for punto, e in PUNTOS_DE_FALLO]


@pytest.fixture(autouse=True)
def _hay_qapplication(app):
    """Las pruebas construyen widgets: la QApplication tiene que existir antes (Trampa 1)."""
    return app


def _visualizador():
    from resources.utils.matplotlib_lazy import get_matplotlib_components
    mpl = get_matplotlib_components()
    canvas = mpl["FigureCanvas"](mpl["Figure"](figsize=(4, 4)))
    return leer_dicom_mod.VisualizadorDicom(target_canvas=canvas)


class _Visor:
    """El visor real + lo que ve el fisico: los avisos (`QMessageBox.warning`) y cuantas veces se emitio `imagen_cargada`."""

    def __init__(self, monkeypatch, tmp_path):
        self.monkeypatch = monkeypatch
        self.avisos = []
        self.dialogo_abierto_al_avisar = []
        self.emitidas = []
        self.detecciones = []
        self.ruta_log = tmp_path / "error_log.txt"
        monkeypatch.setattr(registro, "ruta_error_log", lambda: str(self.ruta_log))        # la causa de un fallo nunca va al arbol de trabajo
        monkeypatch.setattr(QMessageBox, "warning", self._avisar)
        monkeypatch.setattr(leer_dicom_mod, "detectar_y_resolver_modulos", self._detectar)
        self.v = _visualizador()
        monkeypatch.setattr(self.v, "mostrar_popup_cortes", lambda resultados: None)
        self.v.confirmador_de_carga = lambda parent, vol, equipo: True
        self.v.imagen_cargada.connect(lambda vol: self.emitidas.append(vol))
        self.tmp = tmp_path
        self.falla = None                                  # una excepcion que `detectar_y_resolver_modulos` lanzara en la proxima carga

    def _avisar(self, parent, titulo, texto, *a, **k):
        """Lo que ve el fisico: el aviso, y si en ese instante el cuadro modal «Detectando modulos...» seguia abierto (no puede: taparia el aviso)."""
        self.avisos.append((titulo, texto))
        self.dialogo_abierto_al_avisar.append(any(isinstance(w, leer_dicom_mod.LoadingDialog) and w.isVisible() for w in QApplication.topLevelWidgets()))

    def _detectar(self, ruta_dicom):
        self.detecciones.append(ruta_dicom)
        if self.falla is not None:
            raise self.falla
        return {}, {"CTP404": 3}

    def provocar(self, punto, excepcion):
        """El fallo que la PROXIMA carga encontrara: 'deteccion' (pylinac), 'dibujo' (la primera llamada a `actualizar_ventana`) o 'ventana' (`_ajustar_ventana_al_volumen`)."""
        excepcion = type(excepcion)(*excepcion.args)           # una instancia NUEVA por prueba: re-lanzar la misma acumula sus rastros, y con ellos los visores de las pruebas anteriores
        if punto == "deteccion":
            self.falla = excepcion
            return
        nombre = {"dibujo": "actualizar_ventana", "ventana": "_ajustar_ventana_al_volumen"}[punto]
        original = getattr(self.v, nombre)
        llamadas = []

        def una_vez(*a, **k):
            llamadas.append(1)
            if len(llamadas) == 1:
                raise excepcion
            return original(*a, **k)               # la restauracion vuelve a dibujar con normalidad

        self.monkeypatch.setattr(self.v, nombre, una_vez)

    def serie(self, nombre, n, **k):
        return serie_axial(str(self.tmp / nombre), n=n, **k)

    def cerrar(self):
        """Receta de la Trampa 9: `deleteLater()` solo no basta (sin bucle de eventos nunca se procesa) y el visor seguiria vivo con su señal conectada a `emitidas`, que guarda los volumenes
        (`test_e_un_solo_volumen_vivo_siempre` de C.2 contaba entonces 6 volumenes de mas si corria despues en el mismo proceso)."""
        QTest.qWait(120)                      # la precarga de cortes (`QTimer.singleShot(100, lambda: self._ejecutar_precarga(...))`) retiene al visor hasta que vence
        self.falla = None                     # la excepcion lanzada lleva su rastro, y el rastro los marcos de la carga: cada uno con el visor entre sus variables
        self.emitidas.clear()
        lienzo = self.v.target_canvas
        self.v.vol = None
        self.v.hide()
        self.v.close()
        self.v.deleteLater()
        lienzo.close()
        lienzo.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QApplication.processEvents()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.v = None
        del lienzo
        gc.collect()


def _volumenes_vivos():
    gc.collect()
    return sum(1 for o in gc.get_objects() if isinstance(o, _DicomVolume))


def _visores_vivos():
    gc.collect()
    return sum(1 for o in gc.get_objects() if isinstance(o, leer_dicom_mod.VisualizadorDicom))


@pytest.fixture
def visor(monkeypatch, tmp_path):
    antes, visores_antes = _volumenes_vivos(), _visores_vivos()
    s = _Visor(monkeypatch, tmp_path)
    yield s
    s.cerrar()
    monkeypatch.undo()                  # el monkeypatch guarda una referencia al visor por cada `setattr` sobre la instancia: se suelta antes de contar
    assert _volumenes_vivos() <= antes, "estas pruebas dejaron volumenes DICOM vivos (rompen la cuenta de C.2 si corren antes en el mismo proceso)"
    assert _visores_vivos() <= visores_antes, "estas pruebas dejaron visores vivos (cada uno retiene su volumen, su lienzo y sus señales)"


def _lienzo(v):
    """Lo que el lienzo muestra: titulo y huella de la imagen de cada eje."""
    return [(ax.get_title(), hashlib.md5(np.asarray(ax.images[0].get_array()).tobytes()).hexdigest()) for ax in v.target_canvas.figure.axes if ax.images]


def _foto(v):
    """Todo lo que el fisico ve y lo que otras pantallas leen del visor."""
    return {
        "vol": None if v.vol is None else (v.vol.ruta_carpeta, v.vol.get_num_cortes(), hashlib.md5(v.vol.volumen_hu.tobytes()).hexdigest()), "ruta": v.ruta_carpeta, "idx": v.idx_actual, "etiqueta": v.info_label.text(),
        "corte": (v.slider_corte.minimum(), v.slider_corte.maximum(), v.slider_corte.value()),
        "wl": (v.slider_wl.minimum(), v.slider_wl.maximum(), v.slider_wl.value()), "ww": (v.slider_ww.minimum(), v.slider_ww.maximum(), v.slider_ww.value()),
        "etiquetas": (v.slider_wl_label.text(), v.slider_ww_label.text()),
        "ayudas": (v.slider_wl.toolTip(), v.slider_ww.toolTip()),
        "ocultos": (v.slider_wl.isHidden(), v.slider_ww.isHidden(), v.slider_wl_label.isHidden(), v.slider_ww_label.isHidden(), v.info_label.isHidden(), v.elegir_corte_btn.isHidden(),
                    v.sel_imagen_btn.isHidden()),
        "lienzo": _lienzo(v),
        "serie": {k: v.__dict__.get(k, _AUSENTE) for k in ATRIBUTOS},
    }


def _diferencias(antes, despues):
    return {k: (antes[k], despues[k]) for k in antes if antes[k] != despues[k]}


def _debe_estar_sin_carpeta(v):
    """El estado «sin carpeta cargada»: sin volumen ni ruta, controles ocultos y el boton de seleccionar a la vista, el lienzo vacio y ningun resultado ni parametro de ninguna serie."""
    assert v.vol is None and v.ruta_carpeta is None and v.idx_actual == 0
    assert v.sel_imagen_btn.isHidden() is False and v.slider_wl.isHidden() and v.slider_ww.isHidden() and v.info_label.isHidden() and v.elegir_corte_btn.isHidden()
    assert _lienzo(v) == []
    assert not any(hasattr(v, k) for k in ATRIBUTOS), "sin carpeta no quedan resultados, parametros de adquisicion ni orientacion de ninguna serie"


def _procesar_borrados():
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def _cuadros_de_carga():
    return [w for w in QApplication.allWidgets() if isinstance(w, leer_dicom_mod.LoadingDialog)]


class TestCargarUnaSerieMasCortaConElDeslizadorLejos:
    """El escenario de V2: de una serie larga con el deslizador lejos a una corta."""

    def test_la_serie_nueva_queda_instalada_entera(self, visor):
        v = visor.v
        larga, corta = visor.serie("larga", 40), visor.serie("corta", 15)
        v.visualizar_imagen_cargada(larga)
        v.slider_corte.setValue(35)
        assert v.idx_actual == 35
        v.visualizar_imagen_cargada(corta)                                   # antes: TypeError en el dibujo y el dialogo de carga quedaba visible
        assert v.vol.get_num_cortes() == 15 and v.ruta_carpeta == corta
        assert v.idx_actual == 0 and v.slider_corte.value() == 0 and v.slider_corte.maximum() == 14
        assert v.info_label.text() == "Corte: 1/15"
        assert len(visor.emitidas) == 2 and visor.emitidas[-1] is v.vol, "la serie nueva SI se anuncia"
        assert visor.avisos == []

    def test_el_dialogo_de_carga_no_queda_abierto(self, visor):
        v = visor.v
        v.visualizar_imagen_cargada(visor.serie("a", 40))
        v.slider_corte.setValue(35)
        v.visualizar_imagen_cargada(visor.serie("b", 15))
        assert "loading_dialog" not in v.__dict__
        assert not [w for w in QApplication.topLevelWidgets() if isinstance(w, leer_dicom_mod.LoadingDialog) and w.isVisible()]

    def test_una_serie_mas_larga_tambien_arranca_en_el_corte_cero(self, visor):
        v = visor.v
        v.visualizar_imagen_cargada(visor.serie("a", 15))
        v.slider_corte.setValue(10)
        v.visualizar_imagen_cargada(visor.serie("b", 40))
        assert v.idx_actual == 0 and v.info_label.text() == "Corte: 1/40" and v.slider_corte.maximum() == 39

    def test_el_corte_fuera_de_rango_se_acota_en_vez_de_romper_el_dibujo(self, visor):
        """La guarda del dibujo (plan, `:1306`): un `idx_actual` que no cabe en el volumen activo no lanza; se acota al ultimo corte y se dibuja ese (no se deja en el lienzo el corte
        de la serie anterior). Incluye el borde exacto: un corte IGUAL al numero de cortes (en V2: 122 cortes con el deslizador en 70 y una serie de 70)."""
        v = visor.v
        v.visualizar_imagen_cargada(visor.serie("a", 15))
        for fuera in (999, 15):
            v.idx_actual = fuera
            v.actualizar_ventana()
            assert v.idx_actual == 14 and "15/15" in v.info_label.text(), fuera
        v.idx_actual = -3
        v.actualizar_ventana()
        assert v.idx_actual == 0

    def test_el_dibujo_diferido_tambien_acota_el_corte(self, visor):
        """El redibujo que dispara el deslizador de nivel y ventana (`_actualizar_ventana_debounced`) es otra puerta al dibujo: un corte fuera de rango tampoco la rompe."""
        v = visor.v
        v.visualizar_imagen_cargada(visor.serie("a", 15))
        v.idx_actual = 999
        v._pending_update = True
        v._actualizar_ventana_debounced()                                    # antes: TypeError (el corte 999 no existe)
        assert v.idx_actual == 14


class TestSiAlgoFallaALaMitad:

    @pytest.mark.parametrize("punto, excepcion", PUNTOS_DE_FALLO, ids=IDS_DE_FALLO)
    def test_la_carpeta_anterior_sigue_activa_e_intacta(self, visor, punto, excepcion):
        v = visor.v
        anterior = visor.serie("anterior", 40)
        v.visualizar_imagen_cargada(anterior)
        v.slider_corte.setValue(7)
        v.slider_wl.setValue(60)
        v._actualizar_ventana_debounced()                                    # lo que el fisico ve cuando el temporizador de los deslizadores termina: el corte 8 con ese nivel
        antes = _foto(v)
        emitidas_antes = len(visor.emitidas)
        visor.provocar(punto, excepcion)
        nueva = visor.serie("nueva", 15, **SERIE_NUEVA)
        v.visualizar_imagen_cargada(nueva)                                   # no lanza hacia la pantalla
        despues = _foto(v)
        assert despues == antes, _diferencias(antes, despues)
        assert v.ruta_carpeta == anterior and v.idx_actual == 7 and v.vol.ruta_carpeta == anterior
        assert len(visor.emitidas) == emitidas_antes, "la serie que no se instalo no se anuncia"
        assert "loading_dialog" not in v.__dict__
        assert len(visor.avisos) == 1 and visor.avisos[0][0] == "Carpeta DICOM"
        assert visor.dialogo_abierto_al_avisar == [False], "el cuadro de carga se cierra ANTES del aviso (si no, el aviso queda debajo de un cuadro modal)"
        texto = visor.avisos[0][1]
        assert str(excepcion) in texto and f"«{nueva}»" in texto, texto
        assert f"Sigue activa la carpeta anterior: {anterior}" in texto and "No hay ninguna carpeta" not in texto, texto

    @pytest.mark.parametrize("punto, excepcion", PUNTOS_DE_FALLO, ids=IDS_DE_FALLO)
    def test_sin_nada_cargado_el_visor_queda_como_recien_creado(self, visor, punto, excepcion):
        v = visor.v
        inicial = _foto(v)
        visor.provocar(punto, excepcion)
        v.visualizar_imagen_cargada(visor.serie("nueva", 15, **SERIE_NUEVA))
        despues = _foto(v)
        assert despues == inicial, _diferencias(inicial, despues)
        assert despues["vol"] is None and v.ruta_carpeta is None and despues["lienzo"] == [], "el lienzo no se queda con el corte de la serie que no se instalo"
        assert all(valor == _AUSENTE for valor in despues["serie"].values()), "sin carpeta no quedan resultados, cortes ni orientacion de ninguna serie"
        assert "loading_dialog" not in v.__dict__ and len(visor.avisos) == 1 and str(excepcion) in visor.avisos[0][1]
        assert "No hay ninguna carpeta cargada" in visor.avisos[0][1], visor.avisos[0][1]

    def test_los_resultados_de_la_deteccion_de_la_serie_anterior_se_reponen_si_falla_despues_de_detectar(self, visor):
        """El fallo puede llegar DESPUES de que la deteccion de modulos devolvio (aqui, al leer la confianza de un resultado): `resultados` y `cortes` ya son los de la serie que no se instalo
        y tienen que volver a los de la anterior."""
        class _Roto:
            @property
            def confiable(self):
                raise RuntimeError("resultado roto")

        v = visor.v
        v.visualizar_imagen_cargada(visor.serie("anterior", 40))
        antes = _foto(v)
        visor.monkeypatch.setattr(leer_dicom_mod, "detectar_y_resolver_modulos", lambda ruta_dicom: ({"CTP404": _Roto()}, {"CTP404": 99}))
        v.visualizar_imagen_cargada(visor.serie("nueva", 15, **SERIE_NUEVA))
        despues = _foto(v)
        assert despues == antes, _diferencias(antes, despues)
        assert v.cortes == {"CTP404": 3} and "resultado roto" in visor.avisos[-1][1]

    def test_sin_nada_cargado_y_un_fallo_tras_asignar_resultados_y_cortes_no_deja_nada_de_la_serie_nueva(self, visor):
        class _Roto:
            @property
            def confiable(self):
                raise RuntimeError("resultado roto")

        v = visor.v
        inicial = _foto(v)
        visor.monkeypatch.setattr(leer_dicom_mod, "detectar_y_resolver_modulos", lambda ruta_dicom: ({"CTP404": _Roto()}, {"CTP404": 99}))
        v.visualizar_imagen_cargada(visor.serie("nueva", 15, **SERIE_NUEVA))
        assert _foto(v) == inicial, _diferencias(inicial, _foto(v))
        assert not any(hasattr(v, k) for k in ATRIBUTOS)

    def test_una_excepcion_sin_mensaje_dice_al_menos_su_clase(self, visor):
        v = visor.v
        v.visualizar_imagen_cargada(visor.serie("anterior", 40))
        visor.falla = AssertionError()
        nueva = visor.serie("nueva", 15)
        v.visualizar_imagen_cargada(nueva)
        assert f"«{nueva}»: AssertionError. No se cambió nada" in visor.avisos[0][1], visor.avisos[0][1]

    def test_el_volumen_anterior_no_se_retiene_durante_la_deteccion_de_modulos(self, visor):
        """Medido: guardar vivo el volumen anterior mientras pylinac detecta los modulos subia el pico de memoria de la carga hasta +205 MB (TOMOGRAFO -> HALCYON_JUN, 912 -> 1117 MB), justo lo
        que C.2 habia bajado. Se suelta al instalar el nuevo, como antes de CD.1; si hace falta volver, se vuelve a leer la carpeta."""
        v = visor.v
        v.visualizar_imagen_cargada(visor.serie("anterior", 40))
        visor.emitidas.clear()                                               # la prueba misma guardaba una referencia al volumen en cada señal
        referencia = weakref.ref(v.vol)
        vivo_al_detectar = []
        original = visor._detectar

        def detectar(ruta_dicom):
            gc.collect()
            vivo_al_detectar.append(referencia() is not None)
            return original(ruta_dicom)

        visor.monkeypatch.setattr(leer_dicom_mod, "detectar_y_resolver_modulos", detectar)
        v.visualizar_imagen_cargada(visor.serie("nueva", 15))
        assert vivo_al_detectar == [False], "el volumen anterior seguia en memoria mientras se detectaban los modulos de la nueva"

    def test_si_la_carpeta_anterior_ya_no_se_puede_volver_a_abrir_el_visor_queda_vacio_y_lo_dice(self, visor):
        v = visor.v
        anterior = visor.serie("anterior", 40)
        v.visualizar_imagen_cargada(anterior)

        def detectar_y_perder_la_carpeta(ruta_dicom):
            shutil.rmtree(anterior)                                          # la unidad de red se cae, el USB se retira...
            raise RuntimeError("fallo simulado de pylinac")

        visor.monkeypatch.setattr(leer_dicom_mod, "detectar_y_resolver_modulos", detectar_y_perder_la_carpeta)
        v.visualizar_imagen_cargada(visor.serie("nueva", 15, **SERIE_NUEVA))
        _debe_estar_sin_carpeta(v)
        assert len(visor.avisos) == 1 and "fallo simulado de pylinac" in visor.avisos[0][1] and "Tampoco se pudo volver a abrir la carpeta que estaba cargada" in visor.avisos[0][1]
        assert "Sigue activa" not in visor.avisos[0][1] and "No se cambió nada" not in visor.avisos[0][1], visor.avisos[0][1]
        assert visor.dialogo_abierto_al_avisar == [False]

    def test_el_visor_sigue_dibujando_la_carpeta_anterior(self, visor):
        v = visor.v
        v.visualizar_imagen_cargada(visor.serie("anterior", 40))
        v.slider_corte.setValue(7)
        visor.falla = RuntimeError("x")
        v.visualizar_imagen_cargada(visor.serie("nueva", 15))
        visor.falla = None
        v.actualizar_ventana()                                               # no revienta con el corte 7 de 40
        assert v.info_label.text() == "Corte: 8/40"

    def test_y_se_puede_volver_a_cargar_despues_del_fallo(self, visor):
        v = visor.v
        v.visualizar_imagen_cargada(visor.serie("a", 40))
        visor.falla = RuntimeError("x")
        nueva = visor.serie("b", 15)
        v.visualizar_imagen_cargada(nueva)
        visor.falla = None
        v.visualizar_imagen_cargada(nueva)
        assert v.vol.get_num_cortes() == 15 and v.ruta_carpeta == nueva and v.idx_actual == 0

    def test_el_fallo_deja_la_causa_en_error_log(self, visor):
        v = visor.v
        v.visualizar_imagen_cargada(visor.serie("a", 40))
        visor.falla = RuntimeError("fallo simulado de pylinac")
        v.visualizar_imagen_cargada(visor.serie("b", 15))
        texto = visor.ruta_log.read_text(encoding="utf-8")
        assert "RuntimeError: fallo simulado de pylinac" in texto and "Traceback" in texto


COMO_CAMBIA_LA_CARPETA = ["otra serie del mismo tamano", "cortes retirados", "un corte cambiado"]


def _cambiar_la_carpeta(carpeta, como):
    """Lo que puede pasarle a una carpeta en disco entre la primera lectura y la recuperacion tras un fallo."""
    if como == "otra serie del mismo tamano":
        shutil.rmtree(carpeta)
        serie_axial(carpeta, n=40, **SERIE_NUEVA)                           # los mismos nombres de archivo y el mismo numero de cortes, otra serie
    elif como == "cortes retirados":
        for nombre in sorted(os.listdir(carpeta))[:2]:
            os.remove(os.path.join(carpeta, nombre))
    elif como == "un corte cambiado":                                       # la misma serie y el mismo numero de cortes, pero UN corte es otro
        ruta_corte = os.path.join(carpeta, sorted(os.listdir(carpeta))[3])
        ds = pydicom.dcmread(ruta_corte)
        ds.SOPInstanceUID = generate_uid()
        ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
        ds.save_as(ruta_corte, write_like_original=False)
    elif como == "un archivo ajeno":                                        # control: lo que NO cambia la serie
        with open(os.path.join(carpeta, "notas.txt"), "w", encoding="utf-8") as f:
            f.write("no es DICOM")
    else:
        raise AssertionError(como)


class TestLaCarpetaAnteriorSeRecuperaSoloSiSigueSiendoLaMismaSerie:
    """Revision de CD.1 (R2-01): el visor no guarda el volumen anterior (memoria), asi que al volver VUELVE A LEER su carpeta, y esa pudo cambiar entre la primera lectura y la recuperacion: otra
    serie copiada encima, cortes agregados o retirados. Dar por «recuperada» una serie distinta seria decirle al fisico "sigue activa la carpeta anterior" sobre imagenes que ya no son las que veia."""

    @pytest.mark.parametrize("como", COMO_CAMBIA_LA_CARPETA)
    def test_una_carpeta_que_cambio_no_se_da_por_recuperada(self, visor, como):
        v = visor.v
        anterior = visor.serie("anterior", 40)
        v.visualizar_imagen_cargada(anterior)
        emitidas_antes = len(visor.emitidas)

        def detectar_y_cambiar_la_carpeta(ruta_dicom):
            _cambiar_la_carpeta(anterior, como)
            raise RuntimeError("fallo simulado de pylinac")

        visor.monkeypatch.setattr(leer_dicom_mod, "detectar_y_resolver_modulos", detectar_y_cambiar_la_carpeta)
        v.visualizar_imagen_cargada(visor.serie("nueva", 15, **SERIE_NUEVA))
        _debe_estar_sin_carpeta(v)
        assert len(visor.avisos) == 1 and visor.dialogo_abierto_al_avisar == [False]
        texto = visor.avisos[0][1]
        assert "fallo simulado de pylinac" in texto and f"La carpeta que estaba cargada ({anterior}) ya no contiene la misma serie" in texto, texto
        assert "no hay ninguna carpeta cargada" in texto and "Sigue activa" not in texto and "Tampoco se pudo volver a abrir" not in texto, texto
        assert "ya no contiene la misma serie" in visor.ruta_log.read_text(encoding="utf-8")
        assert len(visor.emitidas) == emitidas_antes

    def test_un_archivo_ajeno_en_la_carpeta_no_cambia_la_serie(self, visor):
        """Control: la firma es la de la SERIE, no la de la carpeta; agregar un archivo que no es DICOM no impide la recuperacion."""
        v = visor.v
        anterior = visor.serie("anterior", 40)
        v.visualizar_imagen_cargada(anterior)
        antes = _foto(v)

        def detectar_y_dejar_una_nota(ruta_dicom):
            _cambiar_la_carpeta(anterior, "un archivo ajeno")
            raise RuntimeError("fallo simulado de pylinac")

        visor.monkeypatch.setattr(leer_dicom_mod, "detectar_y_resolver_modulos", detectar_y_dejar_una_nota)
        v.visualizar_imagen_cargada(visor.serie("nueva", 15, **SERIE_NUEVA))
        assert _foto(v) == antes, _diferencias(antes, _foto(v))
        assert f"Sigue activa la carpeta anterior: {anterior}" in visor.avisos[0][1] and "ya no contiene" not in visor.avisos[0][1]

    def test_la_firma_es_estable_y_distingue_una_serie_de_otra(self, visor):
        a, b = visor.serie("a", 15), visor.serie("b", 15)
        primera, segunda, otra = _DicomVolume(a), _DicomVolume(a), _DicomVolume(b)
        assert primera.firma_de_serie() == segunda.firma_de_serie()
        assert primera.firma_de_serie() != otra.firma_de_serie()
        uid, n, huella = primera.firma_de_serie()
        assert uid == primera.serie_uid and n == 15 and len(huella) == 64

    def test_el_texto_del_aviso_dice_la_razon(self):
        texto = leer_dicom_mod.motivo_de_fallo_al_instalar("N", RuntimeError("x"), "A", False, "ya no contiene la misma serie que estaba cargada")
        assert texto == ("No se pudo cargar la carpeta «N»: x. La carpeta que estaba cargada (A) ya no contiene la misma serie que estaba cargada: no hay ninguna carpeta cargada. "
                         "Elija la carpeta otra vez.")
        sin_razon = leer_dicom_mod.motivo_de_fallo_al_instalar("N", RuntimeError("x"), "A", False)
        assert "Tampoco se pudo volver a abrir la carpeta que estaba cargada (A)" in sin_razon


class TestLaSerieQueNoSeInstaloSeSueltaAntesDeVolverALeerLaAnterior:
    """Revision de CD.1 (R2-02): los marcos del rastro de la excepcion retienen sus variables locales -- un corte, una vista del volumen nuevo, que mantiene vivo el volumen ENTERO --, y mientras
    el rastro viva el pico de memoria suma las dos series. `traceback.clear_frames` los suelta antes de volver a leer la carpeta anterior."""

    def _leer_con_espia(self, visor, nuevo):
        v, original = visor.v, leer_dicom_mod.DicomVolume
        lecturas = []

        def dicom_volume(ruta):
            volumen = original(ruta)
            lecturas.append(ruta)
            if len(lecturas) == 1:
                nuevo["ref"] = weakref.ref(volumen)                         # la serie que se esta instalando
            else:                                                           # la lectura de la carpeta anterior, al volver
                nuevo["v_vol_al_releer"] = v.vol
                gc.collect()
                nuevo["vivo_al_releer"] = nuevo["ref"]() is not None
            return volumen

        visor.monkeypatch.setattr(leer_dicom_mod, "DicomVolume", dicom_volume)
        return lecturas

    def test_el_volumen_nuevo_no_sigue_vivo_cuando_se_vuelve_a_leer_la_carpeta_anterior(self, visor):
        v = visor.v
        v.visualizar_imagen_cargada(visor.serie("anterior", 40))
        visor.emitidas.clear()

        def detectar(ruta_dicom):
            volumen = v.vol                                                 # una variable LOCAL del marco que falla: el rastro la retiene mientras viva
            raise RuntimeError("fallo con el volumen nuevo en las variables locales")

        visor.monkeypatch.setattr(leer_dicom_mod, "detectar_y_resolver_modulos", detectar)
        nuevo = {}
        lecturas = self._leer_con_espia(visor, nuevo)
        v.visualizar_imagen_cargada(visor.serie("nueva", 15, **SERIE_NUEVA))
        assert len(lecturas) == 2, "se esperaba la lectura de la carpeta nueva y la de la anterior"
        assert nuevo["v_vol_al_releer"] is None, "el visor todavia tenia la serie nueva instalada al volver a leer la anterior"
        assert nuevo["vivo_al_releer"] is False, "la serie nueva seguia en memoria al volver a leer la anterior (la retenian los marcos del rastro de la excepcion)"
        assert v.vol is not None and v.vol.get_num_cortes() == 40

    def test_el_rastro_completo_se_registra_antes_de_soltar_los_marcos(self, visor):
        """Soltar los marcos no pierde informacion: el rastro (archivos, lineas, funciones) ya esta en `error_log.txt`."""
        v = visor.v
        v.visualizar_imagen_cargada(visor.serie("a", 40))
        visor.falla = RuntimeError("fallo simulado de pylinac")
        v.visualizar_imagen_cargada(visor.serie("b", 15))
        texto = visor.ruta_log.read_text(encoding="utf-8")
        assert "Traceback" in texto and "_detectar" in texto and "visualizar_imagen_cargada" in texto and "RuntimeError: fallo simulado de pylinac" in texto


class TestParametrosDeAdquisicionYRegistroDelFallo:

    def test_los_parametros_de_la_serie_nueva_se_instalan_con_ella(self, visor):
        v = visor.v
        v.visualizar_imagen_cargada(visor.serie("anterior", 15))
        assert (v.kv, v.ma, v.espesor_corte) == (v.vol.kv, v.vol.ma, v.vol.espesor_corte)
        antes = (v.kv, v.ma, v.espesor_corte)
        v.visualizar_imagen_cargada(visor.serie("nueva", 15, **SERIE_NUEVA))
        assert (v.kv, v.ma, v.espesor_corte) == (v.vol.kv, v.vol.ma, v.vol.espesor_corte) and (v.kv, v.ma, v.espesor_corte) != antes

    def test_un_fallo_del_cuadro_de_cortes_no_deja_parametros_de_otra_serie(self, visor):
        """Revision de CD.1 (R2-04): antes `kv`, `ma` y `espesor_corte` se asignaban DESPUES del cuadro informativo de cortes; si ese cuadro fallaba, la carpeta nueva quedaba instalada
        (volumen, ruta, señal) con los parametros de la anterior. La instalacion termina con el `try`; el cuadro viene despues y su fallo no la deshace (ni se traga)."""
        v = visor.v
        v.visualizar_imagen_cargada(visor.serie("anterior", 15))
        antes = (v.kv, v.ma, v.espesor_corte)

        def cuadro_roto(resultados):
            raise RuntimeError("el cuadro de cortes fallo")

        visor.monkeypatch.setattr(v, "mostrar_popup_cortes", cuadro_roto)
        nueva = visor.serie("nueva", 15, **SERIE_NUEVA)
        with pytest.raises(RuntimeError, match="el cuadro de cortes fallo"):
            v.visualizar_imagen_cargada(nueva)
        assert v.ruta_carpeta == nueva and v.vol.ruta_carpeta == nueva, "la instalacion ya habia terminado"
        assert (v.kv, v.ma, v.espesor_corte) == (v.vol.kv, v.vol.ma, v.vol.espesor_corte)
        assert (v.kv, v.ma, v.espesor_corte) != antes
        assert len(visor.emitidas) == 2 and visor.emitidas[-1] is v.vol

    def test_la_carpeta_anterior_que_no_abre_deja_su_causa_en_error_log(self, visor):
        """Revision de CD.1 (R2-06): `DicomVolume` atrapa sus propios errores de lectura y no lanza; antes ese caso volvia sin dejar ningun rastro de por que la anterior no se recupero."""
        v = visor.v
        anterior = visor.serie("anterior", 40)
        v.visualizar_imagen_cargada(anterior)

        def detectar_y_perder_la_carpeta(ruta_dicom):
            shutil.rmtree(anterior)
            raise RuntimeError("fallo simulado de pylinac")

        visor.monkeypatch.setattr(leer_dicom_mod, "detectar_y_resolver_modulos", detectar_y_perder_la_carpeta)
        v.visualizar_imagen_cargada(visor.serie("nueva", 15, **SERIE_NUEVA))
        texto = visor.ruta_log.read_text(encoding="utf-8")
        assert f"No se pudo volver a abrir la carpeta anterior «{anterior}»" in texto and "Detalle:" in texto

    def test_la_carpeta_anterior_cuya_lectura_lanza_deja_el_rastro_y_lo_dice(self, visor):
        v = visor.v
        anterior = visor.serie("anterior", 40)
        v.visualizar_imagen_cargada(anterior)
        original, llamadas = leer_dicom_mod.DicomVolume, []

        def dicom_volume(ruta):
            llamadas.append(ruta)
            if len(llamadas) == 2:
                raise OSError("la unidad de red se cayo")
            return original(ruta)

        visor.monkeypatch.setattr(leer_dicom_mod, "DicomVolume", dicom_volume)
        visor.falla = RuntimeError("fallo simulado de pylinac")
        v.visualizar_imagen_cargada(visor.serie("nueva", 15, **SERIE_NUEVA))
        _debe_estar_sin_carpeta(v)
        texto = visor.ruta_log.read_text(encoding="utf-8")
        assert f"No se pudo volver a abrir la carpeta anterior «{anterior}»" in texto and "OSError: la unidad de red se cayo" in texto
        assert "Tampoco se pudo volver a abrir la carpeta que estaba cargada" in visor.avisos[0][1]

    def test_sin_argumento_se_vuelve_a_cargar_la_carpeta_activa(self, visor):
        v = visor.v
        carpeta = visor.serie("a", 15)
        v.visualizar_imagen_cargada(carpeta)
        v.slider_corte.setValue(5)
        v.visualizar_imagen_cargada()
        assert visor.detecciones == [carpeta, carpeta] and v.ruta_carpeta == carpeta and v.idx_actual == 0 and len(visor.emitidas) == 2

    def test_el_cuadro_de_carga_se_destruye_no_solo_se_oculta(self, visor):
        v = visor.v
        _procesar_borrados()
        antes = len(_cuadros_de_carga())
        v.visualizar_imagen_cargada(visor.serie("a", 15))
        _procesar_borrados()
        assert len(_cuadros_de_carga()) <= antes, "el cuadro de «Detectando modulos...» sigue vivo tras una carga buena"
        visor.falla = RuntimeError("x")
        v.visualizar_imagen_cargada(visor.serie("b", 15))
        _procesar_borrados()
        assert len(_cuadros_de_carga()) <= antes, "el cuadro de «Detectando modulos...» sigue vivo tras una carga que fallo"


class TestUnaExcepcionAntesDeInstalarNoMueveLaRuta:

    def test_el_confirmador_lanza(self, visor):
        v = visor.v
        anterior = visor.serie("anterior", 40)
        v.visualizar_imagen_cargada(anterior)

        def confirmar(parent, vol, equipo):
            raise RuntimeError("la ventana de metadatos fallo")
        v.confirmador_de_carga = confirmar
        with pytest.raises(RuntimeError):
            v.visualizar_imagen_cargada(visor.serie("nueva", 15))
        assert v.ruta_carpeta == anterior and v.vol.ruta_carpeta == anterior, "la ruta activa sigue siendo la del volumen activo"

    def test_la_ventana_de_a3_cancelada_deja_la_ruta(self, visor):
        v = visor.v
        anterior = visor.serie("anterior", 40)
        v.visualizar_imagen_cargada(anterior)
        v.confirmador_de_carga = lambda parent, vol, equipo: False
        v.visualizar_imagen_cargada(visor.serie("nueva", 15))
        assert v.ruta_carpeta == anterior and v.vol.ruta_carpeta == anterior

    def test_sin_ruta_no_se_carga_la_carpeta_de_trabajo(self, visor):
        """Con `ruta_carpeta = None` de origen, llamar sin ruta no puede acabar leyendo el directorio actual (`os.listdir(None)` lista el cwd)."""
        v = visor.v
        visor.monkeypatch.setattr(leer_dicom_mod, "DicomVolume", lambda ruta: (_ for _ in ()).throw(AssertionError("no debia leer ninguna carpeta")))
        v.visualizar_imagen_cargada()
        assert v.vol is None and v.ruta_carpeta is None and visor.avisos == []


class TestCancelarElSelector:

    def test_cancelar_no_cambia_nada(self, visor, monkeypatch):
        v = visor.v
        anterior = visor.serie("anterior", 40)
        v.visualizar_imagen_cargada(anterior)
        antes = _foto(v)
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))
        assert v.seleccionar_carpeta() is None
        assert _foto(v) == antes and v.ruta_carpeta == anterior, "antes: ruta_carpeta quedaba en ''"
        assert len(visor.emitidas) == 1 and visor.avisos == []

    def test_cancelar_sin_nada_cargado_deja_la_ruta_en_none(self, visor, monkeypatch):
        v = visor.v
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))
        assert v.seleccionar_carpeta() is None and v.ruta_carpeta is None and v.vol is None

    def test_elegir_una_carpeta_la_carga_y_devuelve_su_ruta(self, visor, monkeypatch):
        v = visor.v
        nueva = visor.serie("nueva", 15)
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: nueva))
        assert v.seleccionar_carpeta() == nueva and v.ruta_carpeta == nueva and v.vol.get_num_cortes() == 15

    def test_elegir_una_carpeta_que_no_carga_devuelve_la_activa(self, visor, monkeypatch):
        """Si la carpeta elegida no se puede cargar, lo que devuelve es la carpeta que sigue activa (la anterior), no la elegida."""
        v = visor.v
        anterior = visor.serie("anterior", 15)
        v.visualizar_imagen_cargada(anterior)
        vacia = str(visor.tmp / "vacia")
        os.makedirs(vacia)
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: vacia))
        assert v.seleccionar_carpeta() == anterior and v.ruta_carpeta == anterior
        assert len(visor.avisos) == 1

    def test_el_visor_nuevo_no_tiene_ruta(self, visor):
        assert visor.v.ruta_carpeta is None


class TestLoQueNoCambiaAlCargarUnaSolaVez:
    """Control: el camino feliz con una carpeta sola es el de siempre (la ventana, los cortes sugeridos, la senal)."""

    def test_una_carpeta_sola_se_instala_como_siempre(self, visor):
        v = visor.v
        carpeta = visor.serie("a", 15)
        v.visualizar_imagen_cargada(carpeta)
        assert v.vol.get_num_cortes() == 15 and v.ruta_carpeta == carpeta and v.idx_actual == 0
        assert v.cortes == {"CTP404": 3} and (v.orientacion, v.roll_deg) == ("normal", 0.0)
        assert (v.kv, v.ma, v.espesor_corte) == (v.vol.kv, v.vol.ma, v.vol.espesor_corte)
        assert not v.slider_wl.isHidden() and not v.elegir_corte_btn.isHidden() and v.sel_imagen_btn.isHidden()
        assert visor.emitidas == [v.vol] and visor.avisos == [] and visor.detecciones == [carpeta]


ATRIBUTOS_QUE_NO_SON_DE_LA_SERIE = {
    "_current_figure": "la figura del lienzo en la que dibuja `actualizar_ventana`: `_restaurar_la_carga` la vuelve a dibujar (carpeta recuperada) o la limpia (sin carpeta)",
    "_scroll_connection_id": "la conexion de la rueda del raton con el lienzo, que `_cleanup_canvas_connections` renueva en cada dibujo: infraestructura del lienzo, no estado de la serie",
}


def _atributos_que_escribe(nodo):
    """Los `self.<atributo>` que escribe un trozo de codigo: `=`, `+=` (y demas operadores en sitio), `x: T = ...`, la escritura en un elemento (`self.d[k] = ...`) y `setattr(self, "<nombre>", ...)`."""
    escritos = set()
    for n in ast.walk(nodo):
        objetivos = []
        if isinstance(n, ast.Assign):
            objetivos = n.targets
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
            objetivos = [n.target]
        for objetivo in objetivos:
            for destino in ast.walk(objetivo):
                if isinstance(destino, ast.Attribute) and isinstance(destino.value, ast.Name) and destino.value.id == "self":
                    escritos.add(destino.attr)
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "setattr" and len(n.args) >= 2 and isinstance(n.args[0], ast.Name)
                and n.args[0].id == "self" and isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, str)):
            escritos.add(n.args[1].value)
    return escritos


def _metodos_que_llama(nodo, metodos):
    return {n.func.attr for n in ast.walk(nodo) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "self" and n.func.attr in metodos}


def _lo_que_escribe_la_instalacion(arbol):
    """Los atributos del visor que escribe el `try` de `visualizar_imagen_cargada`, ademas de los que escribe cualquier metodo del visor al que llegue (cierre transitivo): `rango_ventana` lo
    escribe `_ajustar_ventana_al_volumen`, no el `try`. Devuelve `(atributos escritos, metodos alcanzados)`."""
    clase = next(n for n in arbol.body if isinstance(n, ast.ClassDef) and n.name == "VisualizadorDicom")
    metodos = {f.name: f for f in clase.body if isinstance(f, ast.FunctionDef)}
    intento = next(n for n in metodos["visualizar_imagen_cargada"].body if isinstance(n, ast.Try))
    cuerpo = ast.Module(body=intento.body, type_ignores=[])
    escritos, alcanzados, pendientes = _atributos_que_escribe(cuerpo), set(), list(_metodos_que_llama(cuerpo, metodos))
    while pendientes:
        nombre = pendientes.pop()
        if nombre in alcanzados:
            continue
        alcanzados.add(nombre)
        escritos |= _atributos_que_escribe(metodos[nombre])
        pendientes.extend(_metodos_que_llama(metodos[nombre], metodos))
    return escritos, alcanzados


def test_todo_lo_que_la_carga_asigna_al_visor_esta_en_la_foto():
    """Tripwire (revision de CD.1, P-03/P-05, R2-05): cada atributo del visor que escribe la instalacion -- el `try` de `visualizar_imagen_cargada` y todo metodo del visor al que llegue, con `=`,
    `+=`, `x: T = ...` o `setattr` -- tiene que estar cubierto por la foto (la ruta, el volumen, el corte, el cuadro de carga o `ATRIBUTOS_DE_LA_SERIE`) o ser infraestructura del lienzo
    justificada. Un atributo nuevo que la carga escriba y la foto no repusiera quedaria con el valor de la serie que NO se instalo."""
    with open(os.path.join(RAIZ, "data/ManejoDatos/catphan_TAC/leer_dicom.py"), encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    escritos, alcanzados = _lo_que_escribe_la_instalacion(arbol)
    serie = set(leer_dicom_mod.VisualizadorDicom.ATRIBUTOS_DE_LA_SERIE)
    sueltos = {"vol", "ruta_carpeta", "idx_actual", "loading_dialog"}
    assert {"vol", "ruta_carpeta", "idx_actual", "loading_dialog", "resultados", "cortes", "orientacion", "roll_deg", "kv", "ma", "espesor_corte"} <= escritos, f"el censo no ve lo conocido: {sorted(escritos)}"
    assert {"_ajustar_ventana_al_volumen", "actualizar_ventana", "_reponer_deslizador_de_cortes"} <= alcanzados, f"el censo no llega a los metodos que la instalacion llama: {sorted(alcanzados)}"
    assert escritos <= sueltos | serie | set(ATRIBUTOS_QUE_NO_SON_DE_LA_SERIE), f"la carga escribe {sorted(escritos - sueltos - serie - set(ATRIBUTOS_QUE_NO_SON_DE_LA_SERIE))} y la foto no lo repone"
    assert serie <= escritos, f"la foto repone {sorted(serie - escritos)} y la carga no lo escribe (sobra)"
    assert set(ATRIBUTOS_QUE_NO_SON_DE_LA_SERIE) <= escritos, "una excepcion justificada que la carga ya no escribe sobra"


def test_el_censo_ve_todas_las_formas_de_escribir_un_atributo_y_llega_a_los_metodos_llamados():
    """Control del tripwire: sobre una clase sintetica con la misma forma, el censo encuentra `=`, `+=`, `x: T = ...`, la escritura en un elemento, `setattr` y lo que escribe un metodo llamado
    desde otro metodo llamado (dos niveles)."""
    fuente = """
class VisualizadorDicom:
    def visualizar_imagen_cargada(self):
        try:
            self.a = 1
            self.b += 1
            self.c: int = 2
            self.d[0] = 3
            setattr(self, "e", 4)
            (self.f, g) = 5, 6
            self.metodo_uno()
        except Exception:
            self.no_cuenta = 1
    def metodo_uno(self):
        self.h = 1
        self.metodo_dos()
    def metodo_dos(self):
        self.i = 2
    def metodo_ajeno(self):
        self.j = 3
"""
    escritos, alcanzados = _lo_que_escribe_la_instalacion(ast.parse(fuente))
    assert escritos == {"a", "b", "c", "d", "e", "f", "h", "i"} and alcanzados == {"metodo_uno", "metodo_dos"}, (escritos, alcanzados)
