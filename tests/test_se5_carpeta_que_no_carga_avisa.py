"""SE.5 (PLAN_GUARDADO_SIN_ESPESOR_Y_RESPALDOS_05-10.md, DP-149; propuesta P6): una carpeta que no carga lo dice.

Defecto (medido en el diagnostico del 05-10): elegir la carpeta de ARRIBA (`QA Tac Septiembre 2026`, que solo contiene la subcarpeta con los `.dcm`), una carpeta sin
archivos `.dcm`, con archivos sin extension, o una serie que la lectura rechaza, no hacia NADA en pantalla: `_load_dicoms` atrapa cualquier excepcion con un `print` y
`visualizar_imagen_cargada` imprimia "No se pudo cargar el volumen DICOM" y volvia. El fisico no sabia si habia elegido mal o si el programa habia fallado; con el campo de
espesor de solo lectura, eso terminaba en "no deja guardar" (la misma clase que `H3` / `IMG-1`: un fallo que solo ve la consola).

Contrato nuevo: `DicomVolume.error_de_carga` (el motivo, o None); una funcion PURA `motivo_de_no_carga(carpeta, error)` que lo dice para una persona (y nombra la subcarpeta si
los `.dcm` estan una carpeta mas adentro); y `visualizar_imagen_cargada` muestra UN aviso con ese texto, sin simbolos (DA-18), y el volumen anterior, si lo habia, sigue activo.
La funcion se prueba con el error REAL del cargador (no con un texto escrito a mano), para que no pueda desfasarse.
"""
import ast
import gc
import inspect
import os
import shutil
import textwrap

import pydicom
import pytest
from PyQt5.QtWidgets import QMessageBox

from _corpus import serie_hospital
from _serie_sintetica import serie_axial
from data.ManejoDatos.catphan_TAC import leer_dicom as leer_dicom_mod
from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume, motivo_de_no_carga

SIMBOLOS = "✓✔✗✘❌✅⚠"


@pytest.fixture(scope="module")
def app():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _motivo(carpeta):
    """Lo que la persona leeria: el motivo calculado con el error REAL del cargador."""
    vol = DicomVolume(carpeta)
    assert vol.volumen_hu is None, "la carpeta debia NO cargar"
    assert vol.error_de_carga, "una carpeta que no carga debe dejar su motivo"
    return motivo_de_no_carga(carpeta, vol.error_de_carga)


# -------------------------------------------------------------------------------- el error y la funcion pura
class TestErrorDeCarga:
    def test_una_carpeta_que_carga_no_tiene_error(self, tmp_path):
        vol = DicomVolume(serie_axial(str(tmp_path)))
        assert vol.volumen_hu is not None and vol.error_de_carga is None

    def test_una_carpeta_que_no_carga_deja_el_texto_del_error(self, tmp_path):
        vol = DicomVolume(str(tmp_path))
        assert vol.volumen_hu is None and isinstance(vol.error_de_carga, str) and vol.error_de_carga

    def test_la_funcion_es_pura_no_toca_qt(self):
        arbol = ast.parse(textwrap.dedent(inspect.getsource(motivo_de_no_carga)))
        nombres = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
        assert not (nombres & {"QMessageBox", "QDialog", "QApplication", "QWidget", "warning", "exec_", "show"})


class TestMotivoDeNoCarga:
    def test_carpeta_vacia(self, tmp_path):
        assert "vacía" in _motivo(str(tmp_path))

    def test_carpeta_inexistente(self, tmp_path):
        texto = motivo_de_no_carga(str(tmp_path / "no_existe"), None)
        assert "no existe" in texto and "no_existe" in texto
        assert "no existe" in motivo_de_no_carga(None, None)

    def test_los_dcm_estan_una_carpeta_mas_adentro_nombra_la_subcarpeta(self, tmp_path):
        """El caso del hospital: se eligio `QA Tac Septiembre 2026`, que solo contiene `20260928 QA Tomografo Septiembre`."""
        serie_axial(str(tmp_path / "20260928 QA Tomografo Septiembre"), n=5)
        texto = _motivo(str(tmp_path))
        assert "'20260928 QA Tomografo Septiembre'" in texto
        assert "una carpeta más adentro" in texto and "Elija esa subcarpeta" in texto

    def test_varias_subcarpetas_nombra_hasta_tres_y_cuenta_el_resto(self, tmp_path):
        for nombre in ("a", "b", "c", "d", "e"):
            serie_axial(str(tmp_path / nombre), n=5)
        texto = _motivo(str(tmp_path))
        assert "'a', 'b', 'c'" in texto and "y 2 más" in texto

    def test_una_subcarpeta_sin_dcm_no_se_nombra(self, tmp_path):
        os.makedirs(str(tmp_path / "vacia"))
        os.makedirs(str(tmp_path / "con_dicom"))
        serie_axial(str(tmp_path / "con_dicom"), n=5)
        texto = _motivo(str(tmp_path))
        assert "'con_dicom'" in texto and "'vacia'" not in texto

    def test_archivos_sin_extension_dcm(self, tmp_path):
        origen = serie_axial(str(tmp_path / "origen_"), n=5)
        destino = tmp_path / "sin_extension"
        destino.mkdir()
        for n in sorted(os.listdir(origen)):
            shutil.copy(os.path.join(origen, n), str(destino / n[:-4]))
        texto = _motivo(str(destino))
        assert ".dcm" in texto and "5 archivo(s) sin extensión" in texto and "corte_" in texto

    def test_otros_archivos_pero_ninguno_dcm(self, tmp_path):
        (tmp_path / "notas.txt").write_text("hola")
        texto = _motivo(str(tmp_path))
        assert "no tiene archivos DICOM (.dcm)" in texto

    def test_dcm_que_no_son_imagenes_de_ct(self, tmp_path):
        carpeta = serie_axial(str(tmp_path), n=5)
        for n in os.listdir(carpeta):
            ruta = os.path.join(carpeta, n)
            ds = pydicom.dcmread(ruta)
            ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.481.3"          # RT Structure Set
            ds.file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
            ds.save_as(ruta)
        texto = _motivo(carpeta)
        assert "ninguno es una imagen de CT" in texto and "5 archivo(s) .dcm" in texto

    def test_serie_no_uniforme(self, tmp_path):
        carpeta = serie_axial(str(tmp_path), n=5)
        ruta = os.path.join(carpeta, sorted(os.listdir(carpeta))[2])
        ds = pydicom.dcmread(ruta)
        ds.PixelSpacing = [2.0, 2.0]
        ds.save_as(ruta)
        texto = _motivo(carpeta)
        assert "no tienen el mismo tamaño, espaciado o escala" in texto and "no es uniforme" in texto

    def test_ningun_motivo_lleva_simbolos_de_correcto_o_incorrecto(self, tmp_path):
        """DA-18: sin chulito, equis ni advertencia en los textos que ve la persona."""
        textos = [motivo_de_no_carga(None, None), motivo_de_no_carga(str(tmp_path), None), motivo_de_no_carga(str(tmp_path / "x"), None),
                  motivo_de_no_carga(str(tmp_path), "No hay cortes de CT Image Storage"), motivo_de_no_carga(str(tmp_path), "otro")]
        for texto in textos:
            assert not any(simbolo in texto for simbolo in SIMBOLOS), texto

    def test_la_carpeta_real_de_arriba_nombra_la_subcarpeta(self):
        """El caso medido en M1: `QA Tac Septiembre 2026` no carga ni con el cargador de antes ni con el de ahora, y no avisaba."""
        ruta_real = serie_hospital("TOMOGRAFO_SEP26")
        if ruta_real is None:
            pytest.skip("corpus del hospital no disponible en esta maquina: TOMOGRAFO_SEP26")
        texto = _motivo(os.path.dirname(ruta_real))
        assert f"'{os.path.basename(ruta_real)}'" in texto


# -------------------------------------------------------------------------------------------------- la pantalla
@pytest.fixture
def visualizador(app, monkeypatch):
    """Un visualizador con la deteccion de modulos y el cuadro de cortes SUSTITUIDOS por espias (el orden de la carga lo prueba A.3; pylinac, sus propias pruebas),
    un registro de eventos y los avisos (`QMessageBox.warning`) capturados: Trampa 2, ningun dialogo modal real."""
    from resources.utils.matplotlib_lazy import get_matplotlib_components
    eventos, avisos = [], []
    monkeypatch.setattr(leer_dicom_mod, "detectar_y_resolver_modulos", lambda ruta_dicom: (eventos.append("detectar"), ({}, {}))[1])
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, titulo, texto, *a, **k: avisos.append((titulo, texto)))
    mpl = get_matplotlib_components()
    v = leer_dicom_mod.VisualizadorDicom(target_canvas=mpl["FigureCanvas"](mpl["Figure"](figsize=(4, 4))))
    monkeypatch.setattr(v, "mostrar_popup_cortes", lambda resultados: eventos.append("popup"))
    v.imagen_cargada.connect(lambda _vol: eventos.append("emitida"))
    v.confirmador_de_carga = lambda parent, vol, equipo: True
    v.eventos, v.avisos = eventos, avisos
    yield v
    v.vol = None
    gc.collect()


class TestLaPantalla:
    def test_una_carpeta_que_no_carga_avisa_una_vez_con_el_motivo_y_no_activa_nada(self, visualizador, tmp_path):
        visualizador.visualizar_imagen_cargada(str(tmp_path))
        assert len(visualizador.avisos) == 1
        titulo, texto = visualizador.avisos[0]
        assert titulo == "Carpeta DICOM" and texto == _motivo(str(tmp_path))
        assert visualizador.vol is None and visualizador.ruta_carpeta is None
        assert visualizador.eventos == [], "ni deteccion de modulos, ni senal, ni cuadro de cortes"

    def test_la_carpeta_de_arriba_avisa_y_nombra_la_subcarpeta(self, visualizador, tmp_path):
        serie_axial(str(tmp_path / "20260928 QA Tomografo Septiembre"), n=5)
        visualizador.visualizar_imagen_cargada(str(tmp_path))
        assert len(visualizador.avisos) == 1 and "'20260928 QA Tomografo Septiembre'" in visualizador.avisos[0][1]

    def test_el_volumen_anterior_queda_activo_e_intacto(self, visualizador, tmp_path):
        buena = tmp_path / "buena"
        serie_axial(str(buena), n=5)
        visualizador.visualizar_imagen_cargada(str(buena))
        anterior = visualizador.vol
        assert anterior is not None and visualizador.avisos == []
        visualizador.eventos.clear()

        mala = tmp_path / "mala"
        mala.mkdir()
        visualizador.visualizar_imagen_cargada(str(mala))

        assert len(visualizador.avisos) == 1
        assert visualizador.vol is anterior and anterior.volumen_hu is not None
        assert visualizador.ruta_carpeta == anterior.ruta_carpeta == str(buena)
        assert visualizador.eventos == [], "una carga fallida no emite la senal ni vuelve a detectar modulos"

    def test_con_una_carpeta_sana_no_hay_ningun_aviso(self, visualizador, tmp_path):
        serie_axial(str(tmp_path), n=5)
        visualizador.visualizar_imagen_cargada(str(tmp_path))
        assert visualizador.avisos == [] and visualizador.vol is not None
        assert visualizador.eventos == ["detectar", "emitida", "popup"]

    def test_cancelar_la_ventana_de_metadatos_no_avisa(self, visualizador, tmp_path):
        """Cancelar es una decision de la persona, no un fallo (A.3): sin aviso."""
        serie_axial(str(tmp_path), n=5)
        visualizador.confirmador_de_carga = lambda parent, vol, equipo: False
        visualizador.visualizar_imagen_cargada(str(tmp_path))
        assert visualizador.avisos == [] and visualizador.vol is None

    def test_cada_intento_fallido_avisa_de_nuevo_una_vez(self, visualizador, tmp_path):
        visualizador.visualizar_imagen_cargada(str(tmp_path))
        visualizador.visualizar_imagen_cargada(str(tmp_path))
        assert len(visualizador.avisos) == 2

    def test_la_rama_de_fallo_no_reemplaza_el_volumen_activo_por_estructura(self):
        """Por AST: la rama de fallo (la que pregunta por `volumen_hu is None`) no asigna `self.vol` (A.3 solo toleraba esa asignacion de siempre)."""
        arbol = ast.parse(textwrap.dedent(inspect.getsource(leer_dicom_mod.VisualizadorDicom.visualizar_imagen_cargada)))
        ramas = [n for n in ast.walk(arbol) if isinstance(n, ast.If) and "volumen_hu" in ast.dump(n.test) and "None" in ast.dump(n.test)]
        assert ramas, "no se encontro la rama de fallo de carga"
        for rama in ramas:
            asignan_vol = [n for b in rama.body for n in ast.walk(b) if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Attribute) and t.attr == "vol" for t in n.targets)]
            assert asignan_vol == []
            avisa = [n for b in rama.body for n in ast.walk(b) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "warning"]
            assert len(avisa) == 1
