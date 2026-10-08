"""GI.5 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, A7 y B7): la imagen de cada prueba se FIJA AL ANALIZAR, no al guardar.

Antes, al guardar, el escritor volvia a abrir la carpeta DICOM (un `DicomVolume` mas, con el pico de memoria de +0.6 a +1.5 GB) y tomaba el corte de UN solo
`corte_seleccionado_info`: el ultimo que se hubiera elegido, para cualquiera de las siete pruebas. Los tres escenarios que midio V1 con la pantalla real:

  E1  el espesor se analiza en el corte 47 (CTP404) y la uniformidad en el 15 (CTP486): "Guardar Espesor" archivaba el 15 (20 914 B; el 47 pesa 21 364 B).
  E2  la carpeta ya no esta (se retiro o se desmonto la unidad de red): la prueba se guardaba SIN imagen original ni de resultado aunque `output_blob`
      (62 934 B) llego, y con "Guardado exitoso". En la copia de `Rebuild_21-09`: 12 de 50 filas vigentes sin ninguna imagen.
  E3  testigo: carpeta disponible y un solo corte -> imagen_path = ese corte, imagen_resultado = la imagen del analisis (no cambia).

Ahora la pantalla codifica el PNG del corte tal como se eligio (`png_de_corte`) cuando registra la adquisicion de cada prueba y el escritor lo recibe por
`imagenes_corte_por_categoria`; "Elegir corte" normaliza solo el corte elegido. Los imports de lo NUEVO son perezosos donde conviene para que contra el codigo
anterior cada prueba caiga por su aserción y no por un `ImportError` generico.
"""
import ast
import gc
import io
import json
import os
import shutil
import subprocess
import sys
import textwrap

import numpy as np
import pytest
from PIL import Image
from PyQt5.QtWidgets import QMessageBox, QPushButton

from _corpus import serie_catphan
from _formularios_imagenes import FORMULARIOS, app, bd_temporal, iniciar, sin_dialogos  # noqa: F401  (fixtures)
from _informe_imagenes import FalsoVisor
from _serie_sintetica import serie_axial
from data.ManejoDatos.catphan_TAC import catphan_db
from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLBOX = {"espesor": 0, "tamano_pixel": 1, "resolucion_contraste": 2, "resolucion_espacial": 3, "valores_ct": 4, "linealidad_ct": 5, "uniformidad": 6}
ID_TIPO = {"espesor": 1, "tamano_pixel": 2, "resolucion_contraste": 3, "resolucion_espacial": 4, "valores_ct": 5, "linealidad_ct": 6, "uniformidad": 7}
GUARDAR = {"espesor": "guardar_espesor_corte", "uniformidad": "guardar_uniformidad", "valores_ct": "guardar_valores_ct", "tamano_pixel": "guardar_tamano_pixel",
           "resolucion_contraste": "guardar_resolucion_contraste", "resolucion_espacial": "guardar_resolucion_espacial", "linealidad_ct": "guardar_linealidad_ct"}
# el modulo del Catphan donde cada prueba se analiza (los cortes que sugiere la deteccion automatica)
MODULO = {"espesor": "CTP404", "tamano_pixel": "CTP404", "resolucion_contraste": "CTP515", "resolucion_espacial": "CTP528", "valores_ct": "CTP404", "uniformidad": "CTP486"}
SIMBOLOS = ("✅", "❌", "✓", "✗", "⚠", "✔", "✖")
PAYLOAD_ESPESOR = {"espesor_promedio_mm": 1.9, "espesor_teorico_mm": 2.0, "diferencia_mm": 0.1,
                   "espesores_individuales": {"Izquierda": 1.9, "Abajo": 1.9, "Derecha": 1.9, "Arriba": 1.9}, "num_rampas_detectadas": 4}


# ------------------------------------------------------------------------------------------------ ayudas
def _cerrar_pantalla(obj):
    """Receta de cierre de la Trampa 9 del CLAUDE.md (PT-09 de la revision): `deleteLater()` + `gc.collect()` no bastan; sin el bucle de eventos las pantallas con una serie real
    quedaban vivas y la memoria del proceso crecia 115-170 MB por prueba. Ademas se suelta la vista del volumen que retiene `corte_seleccionado_info`."""
    from PyQt5.QtCore import QCoreApplication, QEvent
    visualizador = getattr(obj, "visualizador_principal", None)
    if visualizador is not None:
        visualizador.vol = None
    obj.corte_seleccionado_info = None
    obj.hide()
    obj.close()
    obj.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QCoreApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


def _png(blob):
    """El corte de 8 bits que hay dentro de un PNG guardado."""
    return np.array(Image.open(io.BytesIO(blob)))


@pytest.fixture(autouse=True)
def _hay_qapplication(app):
    """Todo lo de aqui construye pantallas o las usa: la QApplication tiene que existir antes (Trampa 1: sin ella `QWidget.__init__` aborta el proceso)."""
    return app


@pytest.fixture
def dialogos(monkeypatch):
    """Todo lo que ve el fisico: [(tipo, titulo, texto)]. Ningun QMessageBox real (Trampa 2)."""
    visto = []
    for tipo in ("warning", "critical", "information"):
        monkeypatch.setattr(QMessageBox, tipo, lambda parent, titulo, texto, *a, _t=tipo, **k: visto.append((_t, titulo, texto)))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    return visto


class _Sesion:
    """El tomografo REAL con una serie REAL cargada por el camino del fisico (`visualizar_imagen_cargada`)."""

    def __init__(self, con):
        self.con = con
        self.obj = iniciar(FORMULARIOS["tomografo"][0]())
        self.obj.user_id = "Fisico Real"
        self.obj.show()
        self.vis = self.obj.visualizador_principal
        self.vis.mostrar_popup_cortes = lambda resultados: None
        self.vis.confirmador_de_carga = lambda parent, vol, equipo: True

    def cargar(self, carpeta):
        self.vis.visualizar_imagen_cargada(carpeta)
        self.cortes = dict(self.vis.cortes)
        return self

    def elegir(self, categoria, corte):
        """Lo que hace el fisico: pone el cuadro de la prueba, mueve a un corte y pulsa "Elegir Corte"."""
        self.obj.toolbox.setCurrentIndex(TOOLBOX[categoria])
        self.vis.idx_actual = corte
        self.vis.elegir_corte()
        self.ultima_ventana = (self.obj.corte_seleccionado_info["wl"], self.obj.corte_seleccionado_info["ww"])

    def guardar(self, categoria):
        return getattr(self.obj, GUARDAR[categoria])()

    def boton_guardar(self, pestana):
        tab = self.obj.dynamic_tabs[pestana]["tab"]
        return [b for b in tab.findChildren(QPushButton) if "Guardar" in b.text()][0]

    def fila(self, categoria):
        return self.con.execute("SELECT imagen_path, imagen_resultado FROM pruebas WHERE id_sesion = ? AND id_tipo = ? AND activo = 1",
                                (self.obj.ref, ID_TIPO[categoria])).fetchone()

    def corte_normalizado(self, corte, ventana=None):
        """El corte tal como lo da el volumen entero normalizado -- la referencia INDEPENDIENTE de lo que se pega al analizar."""
        wl, ww = ventana or self.ultima_ventana
        return self.vis.vol.get_volumen_normalizado(wl, ww)[corte]

    def cerrar(self):
        _cerrar_pantalla(self.obj)


@pytest.fixture
def sesion(bd_temporal, dialogos, monkeypatch):
    carpeta = serie_catphan("TOMOGRAFO")
    if not carpeta:
        pytest.skip("sin el corpus real de Catphan (HI-0)")
    # Valores CT y Resolucion de contraste abren un posicionador manual (`dlg.exec_()`, modal) antes de medir: sin esto la prueba espera un clic que nunca llega (Trampa 2).
    monkeypatch.setattr("data.ManejoDatos.catphan_TAC.posicionador_manual.PosicionadorDialogCT.exec_", lambda self: 0)
    monkeypatch.setattr("data.ManejoDatos.catphan_TAC.posicionador_manual.PosicionadorDialog.exec_", lambda self: 0)
    s = _Sesion(bd_temporal).cargar(carpeta)
    yield s
    s.cerrar()


def _crear_control(con, equipo="Tomógrafo", fecha="06/2026"):
    con.execute("INSERT INTO controles (equipo, control, fecha) VALUES (?, 'Mensual', ?)", (equipo, fecha))
    con.commit()
    return con.execute("SELECT id FROM controles ORDER BY id DESC LIMIT 1").fetchone()[0]


def _guardar(ref, categorias, **extra):
    base = dict(user_id="Fisico Real", fecha="2026-06-01", equipo="Tomógrafo", kv=120, ma=100, espesor_corte=2.0,
                resultados_por_categoria=categorias, id_sesion=ref)
    base.update(extra)
    return catphan_db.guardar_prueba_completa_catphan(**base)


def _fila_de(con, ref, categoria):
    return con.execute("SELECT imagen_path, imagen_resultado FROM pruebas WHERE id_sesion = ? AND id_tipo = ? AND activo = 1",
                       (ref, ID_TIPO[categoria])).fetchone()


# ---------------------------------------------------------------------------------- los escenarios de V1, con la pantalla real
class TestEscenariosDeV1:

    def test_E1_la_imagen_guardada_es_la_del_corte_con_que_se_analizo(self, sesion):
        """Espesor en el corte CTP404, luego uniformidad en el CTP486, y se guarda el ESPESOR: su imagen es la del CTP404, no la del ultimo corte elegido."""
        sesion.elegir("espesor", sesion.cortes["CTP404"])
        esperado_espesor = sesion.corte_normalizado(sesion.cortes["CTP404"]).copy()
        sesion.elegir("uniformidad", sesion.cortes["CTP486"])
        otro = sesion.corte_normalizado(sesion.cortes["CTP486"])
        assert not np.array_equal(esperado_espesor, otro), "los dos cortes deben ser distintos para que la prueba discrimine"

        sesion.boton_guardar("Espesor de corte").click()

        original, _ = sesion.fila("espesor")
        assert original is not None
        assert np.array_equal(_png(original), esperado_espesor), "la imagen guardada del espesor no es la del corte CTP404 con que se analizo"

    @pytest.mark.parametrize("categoria", list(MODULO))
    def test_cada_una_de_las_pruebas_guarda_el_corte_con_que_se_analizo(self, sesion, categoria):
        """Las seis pruebas con corte propio, una por una: se elige y analiza la prueba, se elige OTRA prueba en otro corte (el «ultimo corte elegido» de HEAD) y se guarda la primera."""
        corte = sesion.cortes[MODULO[categoria]] - (3 if categoria == "tamano_pixel" else 0)
        otra, corte_otra = ("uniformidad", sesion.cortes["CTP486"]) if corte != sesion.cortes["CTP486"] else ("espesor", sesion.cortes["CTP404"])
        sesion.elegir(categoria, corte)
        esperado = sesion.corte_normalizado(corte).copy()
        sesion.elegir(otra, corte_otra)
        assert not np.array_equal(esperado, sesion.corte_normalizado(corte_otra)), "los dos cortes deben ser distintos para que la prueba discrimine"
        assert sesion.guardar(categoria) is not False
        original, resultado = sesion.fila(categoria)
        assert original is not None and np.array_equal(_png(original), esperado), categoria
        assert resultado is not None, f"{categoria}: falta la imagen del resultado"

    @pytest.mark.parametrize("categoria, primero, segundo", [("uniformidad", "CTP486", -1), ("tamano_pixel", "CTP404", -3), ("resolucion_espacial", "CTP528", 1)])
    def test_volver_a_analizar_la_misma_prueba_en_otro_corte_guarda_el_ultimo(self, sesion, categoria, primero, segundo):
        """PT-01 de la revision: la imagen guardada es la del ULTIMO analisis (los resultados tambien lo son), no la del primero."""
        c1 = sesion.cortes[primero]
        c2 = c1 + segundo
        sesion.elegir(categoria, c1)
        sesion.elegir(categoria, c2)
        esperado = sesion.corte_normalizado(c2).copy()
        assert not np.array_equal(esperado, sesion.corte_normalizado(c1)), "los dos cortes deben ser distintos"
        assert sesion.guardar(categoria) is not False
        assert np.array_equal(_png(sesion.fila(categoria)[0]), esperado), f"{categoria}: la imagen guardada no es la del ultimo analisis"

    def test_valores_ct_analizado_dos_veces_la_linealidad_hereda_la_del_ultimo(self, sesion):
        c1 = sesion.cortes["CTP404"]
        sesion.elegir("valores_ct", c1)
        sesion.elegir("valores_ct", c1 - 1)
        esperado = sesion.corte_normalizado(c1 - 1).copy()
        propias = sesion.obj.imagenes_corte_por_categoria
        assert propias["linealidad_ct"] == propias["valores_ct"] and np.array_equal(_png(propias["linealidad_ct"]), esperado)

    def test_guardar_valores_ct_y_despues_la_linealidad_sin_volver_a_elegir_corte_conserva_su_imagen(self, sesion):
        """El flujo real que recorre el diferencial: Valores CT sale de la sesion al guardarse, pero la linealidad que ya heredo su imagen sigue siendo guardable."""
        sesion.elegir("valores_ct", sesion.cortes["CTP404"])
        esperado = sesion.corte_normalizado(sesion.cortes["CTP404"]).copy()
        assert sesion.guardar("valores_ct") is not False
        assert "linealidad_ct" in sesion.obj.imagenes_corte_por_categoria
        assert sesion.obj.guardar_linealidad_ct() is not False
        original, resultado = sesion.fila("linealidad_ct")
        assert np.array_equal(_png(original), esperado) and resultado is not None

    def test_con_valores_ct_en_la_sesion_el_corte_elegido_en_la_pagina_de_linealidad_no_pisa_la_herencia(self, sesion):
        """Mientras Valores CT este en la sesion, los HU de la linealidad son los suyos: su imagen es la de Valores CT, no la que se elija despues en la pagina de Linealidad."""
        sesion.elegir("valores_ct", sesion.cortes["CTP404"])
        heredada = sesion.obj.imagenes_corte_por_categoria["linealidad_ct"]
        sesion.elegir("linealidad_ct", sesion.cortes["CTP404"] + 3)
        assert sesion.obj.imagenes_corte_por_categoria["linealidad_ct"] == heredada

    def test_E1_cada_prueba_guarda_su_propio_corte(self, sesion):
        sesion.elegir("espesor", sesion.cortes["CTP404"])
        sesion.elegir("uniformidad", sesion.cortes["CTP486"])
        e404 = sesion.corte_normalizado(sesion.cortes["CTP404"]).copy()
        e486 = sesion.corte_normalizado(sesion.cortes["CTP486"]).copy()
        sesion.guardar("espesor")
        sesion.guardar("uniformidad")
        assert np.array_equal(_png(sesion.fila("espesor")[0]), e404)
        assert np.array_equal(_png(sesion.fila("uniformidad")[0]), e486)

    def test_E2_con_la_carpeta_retirada_la_prueba_se_guarda_con_sus_dos_imagenes(self, bd_temporal, dialogos, tmp_path):
        origen = serie_catphan("TOMOGRAFO")
        if not origen:
            pytest.skip("sin el corpus real de Catphan (HI-0)")
        copia = str(tmp_path / "serie")
        shutil.copytree(origen, copia)                                   # una COPIA: el corpus del fisico no se toca
        s = _Sesion(bd_temporal).cargar(copia)
        try:
            s.elegir("espesor", s.cortes["CTP404"])
            esperado = s.corte_normalizado(s.cortes["CTP404"]).copy()
            imagen_del_analisis = s.obj.resultados_espesor["imagen_analisis"]
            shutil.rmtree(copia)                                         # la carpeta ya no esta (se desmonto la unidad, se movio...)
            assert not os.path.exists(copia)

            s.boton_guardar("Espesor de corte").click()

            original, resultado = s.fila("espesor")
            assert original is not None and resultado is not None, "la prueba quedo sin alguna de sus imagenes"
            assert np.array_equal(_png(original), esperado)
            assert resultado == imagen_del_analisis
            assert [d for d in dialogos if d[0] == "information" and "Guardado exitoso" in d[1]]
            assert not [d for d in dialogos if d[0] in ("warning", "critical")], "no falto ninguna imagen: no hay nada que avisar"
        finally:
            s.cerrar()

    def test_E2_el_informe_pdf_trae_las_imagenes_de_la_prueba_guardada_sin_la_carpeta(self, bd_temporal, dialogos, tmp_path):
        """PT-08 de la revision: la razon de ser de GI.5 es que «el PDF sale sin ninguna imagen» (`reportes_control_sistema_imagenes` exige las dos). Se genera el informe REAL
        de la sesion, EN UN PROCESO APARTE (el generador abre la base con QtSql y la escritura con `sqlite3` de este proceso da `disk I/O error`: DP-147), con el par guardado y con
        la original quitada (lo que dejaba HEAD con la carpeta ausente): con el par trae mas imagenes."""
        from data.ManejoDatos.conection import ruta_base_datos
        origen = serie_catphan("TOMOGRAFO")
        if not origen:
            pytest.skip("sin el corpus real de Catphan (HI-0)")
        copia = str(tmp_path / "serie")
        shutil.copytree(origen, copia)
        s = _Sesion(bd_temporal).cargar(copia)
        try:
            s.elegir("espesor", s.cortes["CTP404"])
            shutil.rmtree(copia)
            assert s.guardar("espesor") is not False
            original, resultado = s.fila("espesor")
            assert original is not None and resultado is not None
            ref = s.obj.ref
        finally:
            s.cerrar()
        bd_temporal.commit()

        def imagenes_del_informe():
            r = subprocess.run([sys.executable, "-c", _SONDA_INFORME.replace("RUTA_BD", repr(ruta_base_datos())).replace("REF_SESION", str(ref))],
                               cwd=RAIZ, capture_output=True, text=True, timeout=240)
            linea = next((l for l in r.stdout.splitlines() if l.startswith("RESULTADO ")), None)
            assert linea, f"el informe no se genero: {r.stderr[-600:]} {r.stdout[-400:]}"
            return int(linea.split()[1])

        con_el_par = imagenes_del_informe()
        bd_temporal.execute("UPDATE pruebas SET imagen_path = NULL WHERE id_sesion = ? AND id_tipo = 1 AND activo = 1", (ref,))
        bd_temporal.commit()
        sin_la_original = imagenes_del_informe()
        assert con_el_par > sin_la_original, (con_el_par, sin_la_original)

    def test_E3_testigo_carpeta_disponible_y_un_solo_corte(self, sesion):
        sesion.elegir("espesor", sesion.cortes["CTP404"])
        esperado = sesion.corte_normalizado(sesion.cortes["CTP404"]).copy()
        imagen_del_analisis = sesion.obj.resultados_espesor["imagen_analisis"]
        sesion.guardar("espesor")
        original, resultado = sesion.fila("espesor")
        assert np.array_equal(_png(original), esperado)
        assert resultado == imagen_del_analisis

    def test_guardar_no_vuelve_a_abrir_la_carpeta(self, sesion, monkeypatch):
        """Ningun `DicomVolume` nuevo (ni la relectura de `convertir_corte_dicom_a_blob`) durante el guardado."""
        sesion.elegir("espesor", sesion.cortes["CTP404"])
        construidos = []
        original = DicomVolume.__init__

        def espia(self, *a, **k):
            construidos.append(a[0] if a else k.get("ruta_carpeta"))
            return original(self, *a, **k)

        monkeypatch.setattr(DicomVolume, "__init__", espia)
        sesion.boton_guardar("Espesor de corte").click()
        assert construidos == [], f"el guardado volvio a abrir la carpeta: {construidos}"

    def test_elegir_corte_no_normaliza_el_volumen_entero(self, sesion, monkeypatch):
        llamadas = []
        original = DicomVolume.get_volumen_normalizado
        monkeypatch.setattr(DicomVolume, "get_volumen_normalizado", lambda self, *a, **k: (llamadas.append(a), original(self, *a, **k))[1])
        sesion.elegir("espesor", sesion.cortes["CTP404"])
        assert llamadas == [], "'Elegir corte' normalizo el volumen entero para quedarse con un corte"

    def test_el_corte_que_se_analiza_es_bit_a_bit_el_del_volumen_normalizado(self, sesion):
        """Normalizar solo el corte elegido da EXACTAMENTE lo que daba normalizar el volumen entero."""
        for categoria, corte in (("espesor", sesion.cortes["CTP404"]), ("uniformidad", sesion.cortes["CTP486"]),
                                 ("tamano_pixel", sesion.cortes["CTP404"] - 3)):
            sesion.elegir(categoria, corte)
            wl, ww = sesion.ultima_ventana
            _, imagen_grafica, _ = sesion.obj.procesar_corte_seleccionado(corte)
            assert imagen_grafica.dtype == np.uint8
            assert np.array_equal(imagen_grafica, sesion.vis.vol.get_volumen_normalizado(wl, ww)[corte]), (categoria, corte, wl, ww)

    def test_la_imagen_del_corte_es_una_copia_y_no_el_array_de_la_cache(self, sesion, monkeypatch):
        """`get_corte_normalizado` devuelve el array de su cache: si el analisis o nadie lo altera, el visor mostraria otro corte. Se copia."""
        monkeypatch.setattr(sesion.obj, "imagen_dicom_cargada", lambda *a, **k: None)          # solo la normalizacion
        corte = sesion.cortes["CTP404"]
        wl, ww = sesion.vis.slider_wl.value(), sesion.vis.slider_ww.value()
        sesion.vis.idx_actual = corte
        antes = sesion.vis.vol.get_corte_normalizado(corte, wl - ww / 2, wl + ww / 2).copy()
        _, imagen_grafica, _ = sesion.obj.procesar_corte_seleccionado(corte)
        imagen_grafica[:] = 0
        despues = sesion.vis.vol.get_corte_normalizado(corte, wl - ww / 2, wl + ww / 2)
        assert np.array_equal(despues, antes), "alterar la imagen devuelta altero la cache del visor"

    def test_la_linealidad_hereda_la_imagen_de_valores_ct(self, sesion):
        """La linealidad se calcula con los HU del CTP404 que acaba de medir Valores CT: su imagen es la de ESE corte, y es lo que se guarda."""
        sesion.elegir("valores_ct", sesion.cortes["CTP404"])
        esperado = sesion.corte_normalizado(sesion.cortes["CTP404"]).copy()
        propias = sesion.obj.imagenes_corte_por_categoria
        assert propias["linealidad_ct"] == propias["valores_ct"] and propias["valores_ct"]
        sesion.elegir("uniformidad", sesion.cortes["CTP486"])          # otro corte despues: no debe arrastrar a la linealidad
        sesion.obj.try_actualizar_linealidad_ct()                      # y la linealidad se recalcula (p. ej. al cambiar la energia) con los HU de Valores CT
        propias = sesion.obj.imagenes_corte_por_categoria
        assert propias["linealidad_ct"] == propias["valores_ct"] != propias["uniformidad"]
        assert sesion.obj.guardar_linealidad_ct() is not False
        assert np.array_equal(_png(sesion.fila("linealidad_ct")[0]), esperado)

    def test_con_ancho_de_ventana_cero_el_corte_es_el_mismo_que_daba_el_volumen_entero(self, sesion, monkeypatch):
        """`get_volumen_normalizado` tapa un ancho <= 0 con 1; la normalizacion de un solo corte conserva esa guarda (el deslizador no baja de 1, pero la regla es de la funcion)."""
        monkeypatch.setattr(sesion.obj, "imagen_dicom_cargada", lambda *a, **k: None)
        corte = sesion.cortes["CTP404"]
        monkeypatch.setattr(sesion.vis.slider_ww, "value", lambda: 0)
        _, imagen_grafica, _ = sesion.obj.procesar_corte_seleccionado(corte)
        assert np.array_equal(imagen_grafica, sesion.vis.vol.get_volumen_normalizado(sesion.vis.slider_wl.value(), 0)[corte])

    def test_un_corte_que_no_se_puede_normalizar_no_se_analiza(self, sesion, monkeypatch):
        monkeypatch.setattr(sesion.vis.vol, "get_corte_normalizado", lambda *a, **k: None)
        assert sesion.obj.procesar_corte_seleccionado(sesion.cortes["CTP404"]) == (None, None, None)

    def test_al_guardar_se_limpia_solo_la_imagen_de_esa_prueba(self, sesion):
        sesion.elegir("espesor", sesion.cortes["CTP404"])
        sesion.elegir("uniformidad", sesion.cortes["CTP486"])
        assert {"espesor", "uniformidad"} <= set(sesion.obj.imagenes_corte_por_categoria)
        sesion.guardar("espesor")
        assert "espesor" not in sesion.obj.imagenes_corte_por_categoria
        assert "uniformidad" in sesion.obj.imagenes_corte_por_categoria
        sesion.obj.limpiar_resultados_catphan()
        assert sesion.obj.imagenes_corte_por_categoria == {}

    def test_la_linealidad_con_valores_ct_ya_guardado_toma_el_corte_que_se_elige_en_su_pagina(self, sesion, dialogos):
        """Hallazgo de la revision (HEAD guardaba el par con el corte elegido): con Valores CT ya guardado, los HU de la linealidad salen de la base y su imagen es el corte que el fisico
        elige EN LA PAGINA DE LINEALIDAD; no se pierde ni se avisa un «no se pudo obtener al analizar» falso."""
        sesion.elegir("valores_ct", sesion.cortes["CTP404"])
        assert sesion.guardar("valores_ct") is not False
        assert "valores_ct" not in sesion.obj.adquisicion_por_categoria
        corte = sesion.cortes["CTP404"] + 3
        del dialogos[:]
        sesion.elegir("linealidad_ct", corte)
        esperado = sesion.corte_normalizado(corte).copy()
        assert np.array_equal(_png(sesion.obj.imagenes_corte_por_categoria["linealidad_ct"]), esperado)
        assert sesion.obj.guardar_linealidad_ct() is not False
        assert np.array_equal(_png(sesion.fila("linealidad_ct")[0]), esperado)
        assert not [d for d in dialogos if d[1] == "Imagen sin guardar"]

    def test_si_falta_la_imagen_del_resultado_se_guarda_la_otra_y_se_avisa(self, sesion, dialogos):
        sesion.elegir("espesor", sesion.cortes["CTP404"])
        sesion.obj.resultados_espesor.pop("imagen_analisis")
        sesion.guardar("espesor")
        original, resultado = sesion.fila("espesor")
        assert original is not None and resultado is None
        avisos = [d for d in dialogos if d[0] == "warning" and d[1] == "Imagen sin guardar"]
        assert len(avisos) == 1 and "resultado" in avisos[0][2] and "Espesor" in avisos[0][2]
        assert not any(s in avisos[0][1] + avisos[0][2] for s in SIMBOLOS), "DA-18: sin simbolos de correcto/incorrecto"
        assert "el informe PDF no muestra las imágenes de esta prueba" in avisos[0][2], "el aviso dice que consecuencia tiene para el informe"

    def test_si_falta_la_imagen_del_corte_se_guarda_la_otra_y_se_avisa(self, sesion, dialogos):
        sesion.elegir("espesor", sesion.cortes["CTP404"])
        sesion.obj.imagenes_corte_por_categoria.pop("espesor")
        sesion.guardar("espesor")
        original, resultado = sesion.fila("espesor")
        assert original is None and resultado is not None
        avisos = [d for d in dialogos if d[0] == "warning" and d[1] == "Imagen sin guardar"]
        assert len(avisos) == 1 and "corte analizado" in avisos[0][2]


# ---------------------------------------------------------------- el escritor: cada categoria con su imagen, y la original no ata a la del resultado
class TestEscritor:

    def test_el_escritor_usa_la_imagen_fijada_y_no_abre_la_carpeta(self, bd_temporal, monkeypatch):
        monkeypatch.setattr(catphan_db, "convertir_corte_dicom_a_blob", lambda *a, **k: pytest.fail("se releyo la carpeta"))
        monkeypatch.setattr(catphan_db, "DicomVolume", lambda *a, **k: pytest.fail("se abrio un DicomVolume"))
        ref = _crear_control(bd_temporal)
        _guardar(ref, {"espesor": PAYLOAD_ESPESOR}, output_blob=b"RESULTADO", imagenes_corte_por_categoria={"espesor": b"CORTE"})
        assert _fila_de(bd_temporal, ref, "espesor") == (b"CORTE", b"RESULTADO")

    def test_cada_categoria_recibe_su_imagen(self, bd_temporal):
        ref = _crear_control(bd_temporal)
        _guardar(ref, {"espesor": PAYLOAD_ESPESOR, "linealidad_ct": {"pendiente": 1.0, "intercepto": 0.0, "r_squared": 0.999}},
                 imagenes_corte_por_categoria={"espesor": b"CORTE-E", "linealidad_ct": b"CORTE-L"})
        assert _fila_de(bd_temporal, ref, "espesor")[0] == b"CORTE-E"
        assert _fila_de(bd_temporal, ref, "linealidad_ct")[0] == b"CORTE-L"

    def test_la_imagen_del_resultado_no_depende_de_que_haya_una_original(self, bd_temporal, tmp_path):
        """El defecto de E2 en el escritor: con `info_dicom` apuntando a una carpeta que ya no esta, el `output_blob` que SI llego se descartaba."""
        ref = _crear_control(bd_temporal)
        avisos = []
        _guardar(ref, {"espesor": PAYLOAD_ESPESOR}, output_blob=b"RESULTADO", info_dicom={"ruta_carpeta": str(tmp_path / "no_existe")}, avisos=avisos)
        original, resultado = _fila_de(bd_temporal, ref, "espesor")
        assert original is None and resultado == b"RESULTADO"
        assert len(avisos) == 1 and "corte analizado" in avisos[0] and "Espesor" in avisos[0]

    def test_sin_imagen_nueva_conserva_las_anteriores_y_no_avisa(self, bd_temporal):
        ref = _crear_control(bd_temporal)
        _guardar(ref, {"espesor": PAYLOAD_ESPESOR}, output_blob=b"R1", imagenes_corte_por_categoria={"espesor": b"C1"})
        avisos = []
        _guardar(ref, {"espesor": dict(PAYLOAD_ESPESOR, espesor_promedio_mm=2.1)}, avisos=avisos)           # reguardado sin imagenes
        assert _fila_de(bd_temporal, ref, "espesor") == (b"C1", b"R1")
        assert avisos == []

    def test_una_imagen_nueva_reemplaza_a_la_anterior(self, bd_temporal):
        ref = _crear_control(bd_temporal)
        _guardar(ref, {"espesor": PAYLOAD_ESPESOR}, output_blob=b"R1", imagenes_corte_por_categoria={"espesor": b"C1"})
        _guardar(ref, {"espesor": PAYLOAD_ESPESOR}, output_blob=b"R2", imagenes_corte_por_categoria={"espesor": b"C2"})
        assert _fila_de(bd_temporal, ref, "espesor") == (b"C2", b"R2")

    def test_con_varias_categorias_el_aviso_nombra_a_la_que_le_falta_la_imagen(self, bd_temporal):
        """PT-05 de la revision."""
        ref = _crear_control(bd_temporal)
        avisos = []
        _guardar(ref, {"espesor": PAYLOAD_ESPESOR, "linealidad_ct": {"pendiente": 1.0, "intercepto": 0.0, "r_squared": 0.999}},
                 output_blob=b"R", imagenes_corte_por_categoria={"espesor": b"C"}, avisos=avisos)
        assert len(avisos) == 1 and "Linealidad CT" in avisos[0] and "Espesor" not in avisos[0] and "corte analizado" in avisos[0]

    def test_en_una_llamada_mixta_cada_categoria_usa_lo_suyo(self, bd_temporal, monkeypatch):
        """PT-07 de la revision: una categoria con su imagen fijada (esa manda) y otra sin ella (la relectura, conducta de los llamadores anteriores) en la misma llamada."""
        monkeypatch.setattr(catphan_db, "convertir_corte_dicom_a_blob", lambda *a, **k: b"RELEIDO")
        ref = _crear_control(bd_temporal)
        _guardar(ref, {"espesor": PAYLOAD_ESPESOR, "linealidad_ct": {"pendiente": 1.0, "intercepto": 0.0, "r_squared": 0.999}},
                 output_blob=b"R", info_dicom={"ruta_carpeta": "/x"}, imagenes_corte_por_categoria={"espesor": b"FIJADO"})
        assert _fila_de(bd_temporal, ref, "espesor")[0] == b"FIJADO"
        assert _fila_de(bd_temporal, ref, "linealidad_ct")[0] == b"RELEIDO"

    def test_faltan_las_dos_imagenes_avisa_de_las_dos(self, bd_temporal):
        ref = _crear_control(bd_temporal)
        avisos = []
        _guardar(ref, {"espesor": PAYLOAD_ESPESOR}, avisos=avisos)
        assert _fila_de(bd_temporal, ref, "espesor") == (None, None)
        assert len(avisos) == 2 and "corte analizado" in avisos[0] and "resultado" in avisos[1]

    def test_si_no_falta_ninguna_no_avisa(self, bd_temporal):
        ref = _crear_control(bd_temporal)
        avisos = []
        _guardar(ref, {"espesor": PAYLOAD_ESPESOR}, output_blob=b"R", imagenes_corte_por_categoria={"espesor": b"C"}, avisos=avisos)
        assert avisos == []

    def test_lo_fijado_manda_sobre_info_dicom_y_no_se_relee(self, bd_temporal, monkeypatch):
        llamadas = []
        monkeypatch.setattr(catphan_db, "convertir_corte_dicom_a_blob", lambda *a, **k: llamadas.append(a) or b"RELEIDO")
        ref = _crear_control(bd_temporal)
        _guardar(ref, {"espesor": PAYLOAD_ESPESOR}, info_dicom={"ruta_carpeta": "/x"}, imagenes_corte_por_categoria={"espesor": b"FIJADO"})
        assert llamadas == [] and _fila_de(bd_temporal, ref, "espesor")[0] == b"FIJADO"

    def test_una_categoria_sin_imagen_fijada_sigue_releyendo_la_carpeta_de_los_llamadores_anteriores(self, bd_temporal, monkeypatch):
        """Conducta de hoy por omision: un llamador que solo trae `info_dicom` sigue funcionando igual."""
        monkeypatch.setattr(catphan_db, "convertir_corte_dicom_a_blob", lambda *a, **k: b"RELEIDO")
        ref = _crear_control(bd_temporal)
        _guardar(ref, {"espesor": PAYLOAD_ESPESOR}, info_dicom={"ruta_carpeta": "/x"}, output_blob=b"R")
        assert _fila_de(bd_temporal, ref, "espesor") == (b"RELEIDO", b"R")

    def test_convertir_corte_dicom_a_blob_usa_el_unico_codificador(self, tmp_path, monkeypatch):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        monkeypatch.setattr(catphan_db, "png_de_corte", lambda corte: b"CODIFICADO-UNA-VEZ")
        assert catphan_db.convertir_corte_dicom_a_blob(carpeta, 2, 40, 400) == b"CODIFICADO-UNA-VEZ"

    def test_png_de_corte_es_un_png_valido_e_identico_a_la_relectura(self, tmp_path):
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        vol = DicomVolume(carpeta)
        a_mano = catphan_db.png_de_corte(vol.get_volumen_normalizado(40, 400)[2])
        assert a_mano[:8] == b"\x89PNG\r\n\x1a\n"
        assert a_mano == catphan_db.convertir_corte_dicom_a_blob(carpeta, 2, 40, 400)


# ------------------------------------------------- 9 casos en 3 series reales: lo fijado en memoria == lo que daba releer (`a7_fix_viable`)
@pytest.mark.parametrize("clave", ["TOMOGRAFO", "HALCYON_JUN", "IX_DIC"])
def test_el_png_desde_memoria_es_identico_al_de_la_relectura(clave):
    ruta = serie_catphan(clave)
    if not ruta:
        pytest.skip("sin el corpus real de Catphan (HI-0)")
    vol = DicomVolume(ruta)
    n = vol.get_num_cortes()
    try:
        for corte, wl, ww in ((n // 2, 40, 200), (n // 3, 40, 400), (n - 5, 100, 800)):
            relectura = catphan_db.convertir_corte_dicom_a_blob(ruta, corte, wl, ww)
            en_memoria = catphan_db.png_de_corte(vol.get_corte_normalizado(corte, wl - ww / 2, wl + ww / 2).copy())
            assert relectura == en_memoria, (clave, corte, wl, ww)
    finally:
        vol.clear_cache()


# ----------------------------------------------------------------------- las cinco pantallas de imagenes comparten el codigo
@pytest.mark.parametrize("clave", list(FORMULARIOS))
class TestCincoPantallas:

    def _pantalla(self, clave, tmp_path):
        obj = iniciar(FORMULARIOS[clave][0]())
        obj.user_id = "Fisico Real"
        carpeta = serie_axial(str(tmp_path / "s"), n=5)
        obj.visualizador_principal.vol = DicomVolume(carpeta)
        obj.asignar_parametros_adquisicion()
        return obj

    def test_se_guarda_con_la_imagen_fijada_sin_abrir_la_carpeta(self, clave, tmp_path, bd_temporal, dialogos, monkeypatch):
        obj = self._pantalla(clave, tmp_path)
        try:
            obj._registrar_adquisicion("espesor", b"PNG-DEL-CORTE")
            obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
            construidos = []
            original = DicomVolume.__init__
            monkeypatch.setattr(DicomVolume, "__init__", lambda self, *a, **k: (construidos.append(a), original(self, *a, **k))[1])
            assert obj.guardar_resultado_individual("espesor", obj.resultados_espesor, output_blob=b"RESULTADO") is True
            assert construidos == []
            assert _fila_de(bd_temporal, obj.ref, "espesor") == (b"PNG-DEL-CORTE", b"RESULTADO")
        finally:
            _cerrar_pantalla(obj)

    def test_registrar_sin_imagen_no_deja_la_de_otra_prueba(self, clave, tmp_path, bd_temporal):
        obj = self._pantalla(clave, tmp_path)
        try:
            obj._registrar_adquisicion("espesor", b"PNG-A")
            obj._registrar_adquisicion("espesor")                   # esta vez sin imagen: la anterior NO se arrastra
            assert "espesor" not in obj.imagenes_corte_por_categoria
        finally:
            _cerrar_pantalla(obj)

    def test_guardar_todos_sin_nada_que_avisar_no_avisa(self, clave, tmp_path, bd_temporal, dialogos):
        """Si el reguardado conserva la imagen del resultado de un guardado anterior y trae la del corte, no falta ninguna: ningun aviso (ni vacio)."""
        obj = self._pantalla(clave, tmp_path)
        try:
            obj._registrar_adquisicion("espesor", b"PNG-1")
            obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
            assert obj.guardar_resultado_individual("espesor", obj.resultados_espesor, output_blob=b"RES-1") is True
            del dialogos[:]
            obj._registrar_adquisicion("espesor", b"PNG-2")
            obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
            obj.guardar_catphan = QPushButton()
            obj.guardar_resultados_catphan()
            assert not [d for d in dialogos if d[0] in ("warning", "critical")], dialogos
            assert _fila_de(bd_temporal, obj.ref, "espesor") == (b"PNG-2", b"RES-1")
        finally:
            _cerrar_pantalla(obj)

    def test_sin_volumen_no_queda_imagen_fijada(self, clave, tmp_path, bd_temporal):
        obj = self._pantalla(clave, tmp_path)
        try:
            obj._registrar_adquisicion("espesor", b"PNG-A")
            obj.visualizador_principal.vol = None
            obj._registrar_adquisicion("espesor", b"PNG-B")
            assert "espesor" not in obj.imagenes_corte_por_categoria and "espesor" not in obj.adquisicion_por_categoria
        finally:
            gc.collect()

    def test_un_recalculo_de_la_linealidad_sin_corte_nuevo_conserva_la_imagen_si_es_la_misma_serie(self, clave, tmp_path, bd_temporal):
        obj = self._pantalla(clave, tmp_path)
        try:
            obj._registrar_adquisicion_linealidad(b"PNG-DE-LA-PAGINA")
            assert obj.imagenes_corte_por_categoria["linealidad_ct"] == b"PNG-DE-LA-PAGINA"
            obj._registrar_adquisicion_linealidad()                                 # p. ej. el cambio de energia: mismo volumen
            assert obj.imagenes_corte_por_categoria["linealidad_ct"] == b"PNG-DE-LA-PAGINA"
        finally:
            _cerrar_pantalla(obj)

    def test_un_recalculo_de_la_linealidad_tras_cargar_otra_serie_no_le_presta_la_imagen_vieja(self, clave, tmp_path, bd_temporal):
        obj = self._pantalla(clave, tmp_path)
        try:
            obj._registrar_adquisicion_linealidad(b"PNG-DE-LA-PAGINA")
            obj.visualizador_principal.vol = DicomVolume(serie_axial(str(tmp_path / "otra"), n=5))
            obj._registrar_adquisicion_linealidad()
            assert "linealidad_ct" not in obj.imagenes_corte_por_categoria, "la imagen de una serie quedo pegada a una prueba corrida con otra"
        finally:
            _cerrar_pantalla(obj)

    def test_si_valores_ct_no_trae_imagen_la_linealidad_no_conserva_una_vieja(self, clave, tmp_path, bd_temporal):
        """PT-03/D1 de la revision: la herencia manda (Valores CT en la sesion) y, si Valores CT no tiene imagen, la linealidad tampoco: no se queda con la de una vez anterior."""
        obj = self._pantalla(clave, tmp_path)
        try:
            obj._registrar_adquisicion_linealidad(b"PNG-VIEJA-DE-LA-PAGINA")             # sin Valores CT en la sesion: la imagen es la de la pagina
            obj._registrar_adquisicion("valores_ct")                                       # ahora Valores CT esta en la sesion, pero sin imagen fijada
            obj._registrar_adquisicion_linealidad()
            assert "linealidad_ct" not in obj.imagenes_corte_por_categoria
        finally:
            _cerrar_pantalla(obj)

    def test_limpiar_retira_las_imagenes(self, clave, tmp_path, bd_temporal):
        obj = self._pantalla(clave, tmp_path)
        try:
            obj._registrar_adquisicion("espesor", b"E")
            obj._registrar_adquisicion("uniformidad", b"U")
            obj.limpiar_resultados_catphan("espesor")
            assert obj.imagenes_corte_por_categoria == {"uniformidad": b"U"}
            obj.limpiar_resultados_catphan()
            assert obj.imagenes_corte_por_categoria == {}
        finally:
            _cerrar_pantalla(obj)

    def test_guardar_todos_tambien_usa_lo_fijado_y_avisa_de_lo_que_falta(self, clave, tmp_path, bd_temporal, dialogos):
        """"Guardar Todos" es codigo muerto (A13: nadie crea `self.guardar_catphan`); el boton se pone a mano para que no quede atras."""
        obj = self._pantalla(clave, tmp_path)
        try:
            obj._registrar_adquisicion("espesor", b"PNG-DEL-CORTE")
            obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
            obj.guardar_catphan = QPushButton()
            obj.guardar_resultados_catphan()
            fila = _fila_de(bd_temporal, obj.ref, "espesor")
            assert fila is not None and fila[0] == b"PNG-DEL-CORTE"
            # el camino muerto no entrega la imagen del resultado: se guarda lo que hay y se avisa de lo que falta
            avisos = [d for d in dialogos if d[0] == "warning" and d[1] == "Imagen sin guardar"]
            assert len(avisos) == 1 and "resultado" in avisos[0][2] and "corte analizado" not in avisos[0][2]
            assert "el informe PDF no muestra las imágenes de esta prueba" in avisos[0][2] and not any(s in avisos[0][2] for s in SIMBOLOS)
        finally:
            _cerrar_pantalla(obj)


# ------------------------------------------------------------------- tripwires por AST sobre el arbol de produccion
def _archivos_de_produccion():
    for carpeta, subcarpetas, archivos in os.walk(RAIZ):
        subcarpetas[:] = [s for s in subcarpetas if s not in (".venv", "tests", "build", "dist", "node_modules", "__pycache__", ".git", "scripts")]
        for a in archivos:
            if a.endswith(".py"):
                yield os.path.join(carpeta, a)


def _llamadas_al_escritor():
    sitios = []
    for ruta in _archivos_de_produccion():
        with open(ruta, encoding="utf-8") as f:
            arbol = ast.parse(f.read())
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call):
                nombre = nodo.func.id if isinstance(nodo.func, ast.Name) else getattr(nodo.func, "attr", None)
                if nombre == "guardar_prueba_completa_catphan":
                    sitios.append((os.path.relpath(ruta, RAIZ), nodo.lineno, {k.arg for k in nodo.keywords}))
    return sitios


def test_los_textos_nuevos_que_ve_el_fisico_no_llevan_simbolos():
    """PT-06 de la revision (DA-18): las lineas que el escritor agrega a `avisos` y la nota sobre el informe."""
    import ui.paginasControles.PruebasMensuales.tac_mensual as tac
    assert not any(s in tac.AVISO_PAR_DE_IMAGENES for s in SIMBOLOS)
    with open(os.path.join(RAIZ, "data/ManejoDatos/catphan_TAC/catphan_db.py"), encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    escritor = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "guardar_prueba_completa_catphan")
    llamadas = [n for n in ast.walk(escritor) if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "append"
                and getattr(n.func.value, "id", None) == "avisos"]
    assert len(llamadas) == 2
    assert not any(s in ast.unparse(c) for c in llamadas for s in SIMBOLOS)


def test_hay_llamadores_del_escritor_y_ninguno_le_pasa_info_dicom():
    """Pasar `info_dicom` es lo que hace volver a abrir la carpeta al guardar: solo los llamadores anteriores (y sus pruebas) lo usan."""
    sitios = _llamadas_al_escritor()
    assert len(sitios) >= 2, sitios
    con_info = [(a, n) for a, n, claves in sitios if "info_dicom" in claves]
    assert con_info == [], f"un llamador de produccion pasa info_dicom: {con_info}"


def test_todo_llamador_de_produccion_pasa_las_imagenes_fijadas():
    sitios = _llamadas_al_escritor()
    sin = [(a, n) for a, n, claves in sitios if "imagenes_corte_por_categoria" not in claves]
    assert sin == [], f"llamadores que no pasan las imagenes fijadas al analizar: {sin}"


def _funcion(ruta_relativa, nombre):
    with open(os.path.join(RAIZ, ruta_relativa), encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == nombre:
            return nodo
    return None


def _nombres_llamados(funcion):
    return {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", None) for n in ast.walk(funcion) if isinstance(n, ast.Call)}


def test_elegir_corte_no_llama_a_get_volumen_normalizado():
    f = _funcion("ui/paginasControles/PruebasMensuales/tac_mensual.py", "procesar_corte_seleccionado")
    assert f is not None
    llamados = _nombres_llamados(f)
    assert "get_volumen_normalizado" not in llamados and "get_corte_normalizado" in llamados


def test_la_relectura_de_la_carpeta_usa_el_unico_codificador():
    f = _funcion("data/ManejoDatos/catphan_TAC/catphan_db.py", "convertir_corte_dicom_a_blob")
    assert f is not None
    llamados = _nombres_llamados(f)
    assert "png_de_corte" in llamados and "fromarray" not in llamados


def test_la_pantalla_no_conserva_el_extractor_de_la_ruta_de_la_carpeta():
    assert _funcion("ui/paginasControles/PruebasMensuales/tac_mensual.py", "_obtener_info_imagen_dicom") is None


def test_cada_prueba_que_se_registra_pasa_la_imagen_del_corte():
    """Toda llamada a `_registrar_adquisicion` de `imagen_dicom_cargada` lleva la imagen del corte (la linealidad la hereda de Valores CT)."""
    f = _funcion("ui/paginasControles/PruebasMensuales/tac_mensual.py", "imagen_dicom_cargada")
    llamadas = [n for n in ast.walk(f) if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "_registrar_adquisicion"]
    assert len(llamadas) == 6, [ast.dump(n.args[0]) for n in llamadas]
    assert all(len(n.args) == 2 for n in llamadas)


# -------------------------------------------------------------------------------------------------- la memoria (proceso aparte)
_SONDA_INFORME = textwrap.dedent('''
    import os, sqlite3, sys
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    sys.path[:0] = [".", "tests"]
    import data.ManejoDatos.conection as cm
    cm.ruta_base_datos = lambda: RUTA_BD
    from PyQt5.QtWidgets import QApplication, QMessageBox
    for n in ("warning", "critical", "information"):
        setattr(QMessageBox, n, staticmethod(lambda *a, **k: None))
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    app = QApplication([])
    import fitz
    import models.PDF.Imagenes.reportes_control_sistema_imagenes as rep_mod
    from models.PDF.Imagenes.reportes_control_sistema_imagenes import generar_reporte_sistema_imagenes
    from _informe_imagenes import FalsoVisor, Padre
    rep_mod.PdfViewer = FalsoVisor
    con = sqlite3.connect(RUTA_BD)
    fecha, equipo = con.execute("SELECT fecha, equipo FROM controles WHERE id = ?", (REF_SESION,)).fetchone()
    con.close()
    generar_reporte_sistema_imagenes(Padre(RUTA_BD), fecha, equipo, "x", ref=REF_SESION, sistema_imagenes=True)
    n = sum(len(p.get_images()) for p in fitz.open(stream=FalsoVisor.ultimo["pdf"], filetype="pdf")) if FalsoVisor.ultimo else -1
    print("RESULTADO", n)
''')


_SONDA_MEMORIA = textwrap.dedent('''
    import json, os, sys, tempfile
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    sys.path[:0] = [".", "tests"]
    import data.ManejoDatos.conection as cm
    ruta_bd = os.path.join(tempfile.mkdtemp(), "t.db")
    cm.ruta_base_datos = lambda: ruta_bd
    from PyQt5.QtWidgets import QApplication, QMessageBox
    for n in ("warning", "critical", "information"):
        setattr(QMessageBox, n, staticmethod(lambda *a, **k: None))
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    app = QApplication([])
    from data.ManejoDatos.conection import Conexion
    c = Conexion(); c.con.execute("INSERT INTO users (fullname) VALUES ('Fisico Real')"); c.con.commit()
    import _formularios_imagenes as ff
    obj = ff.iniciar(ff._tomografo()); obj.user_id = "Fisico Real"; obj.show()
    vis = obj.visualizador_principal
    vis.mostrar_popup_cortes = lambda r: None
    vis.confirmador_de_carga = lambda p, v, e: True
    vis.visualizar_imagen_cargada(RUTA)
    corte = vis.cortes["CTP404"]

    def hwm_kb():
        with open("/proc/self/status") as f:
            return next(int(l.split()[1]) for l in f if l.startswith("VmHWM"))

    def reiniciar_pico():
        with open("/proc/self/clear_refs", "w") as f:
            f.write("5")

    # calentamiento: una eleccion y un guardado completos (importes perezosos, matplotlib, cache de SQLite) para que la medicion vea SOLO lo que pide cada operacion
    obj.toolbox.setCurrentIndex(0); vis.idx_actual = corte; vis.elegir_corte(); obj.guardar_espesor_corte()
    volumen_mb = vis.vol.volumen_hu.nbytes / 1048576

    reales = obj.imagen_dicom_cargada
    obj.imagen_dicom_cargada = lambda *a, **k: None          # solo la normalizacion, sin el analisis
    reiniciar_pico(); base = hwm_kb()
    obj.procesar_corte_seleccionado(corte)
    elegir_kb = hwm_kb() - base
    obj.imagen_dicom_cargada = reales

    obj.toolbox.setCurrentIndex(0); vis.idx_actual = corte; vis.elegir_corte()
    reiniciar_pico(); base = hwm_kb()
    obj.guardar_espesor_corte()
    guardar_kb = hwm_kb() - base
    print("RESULTADO", json.dumps({"volumen_mb": volumen_mb, "elegir_mb": elegir_kb / 1024, "guardar_mb": guardar_kb / 1024}))
''')


@pytest.mark.skipif(not os.path.exists("/proc/self/clear_refs"), reason="mide VmHWM de /proc (Linux)")
def test_el_pico_de_memoria_de_elegir_corte_y_de_guardar_no_depende_del_tamano_del_volumen():
    ruta = serie_catphan("TOMOGRAFO")
    if not ruta:
        pytest.skip("sin el corpus real de Catphan (HI-0)")
    codigo = _SONDA_MEMORIA.replace("RUTA", repr(ruta))
    r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, timeout=300)
    linea = next((l for l in r.stdout.splitlines() if l.startswith("RESULTADO ")), None)
    assert linea, f"la sonda no termino: {r.stderr[-800:]}"
    medida = json.loads(linea[len("RESULTADO "):])
    # Antes del arreglo ambos costaban del orden de 2-4 veces el volumen (normalizar el volumen entero / abrir otro DicomVolume); ahora solo un corte.
    assert medida["elegir_mb"] <= 10, medida
    assert medida["guardar_mb"] <= 10, medida
