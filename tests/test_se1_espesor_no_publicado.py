"""SE.1 (PLAN_GUARDADO_SIN_ESPESOR_Y_RESPALDOS_05-10.md, DP-149): `leer_serie` dice lo que el archivo publica: sin espesor es "no publicado" (`None`), no `0` ni una
carga que se cae.

Defecto (medido en el diagnostico del 05-10): `serie.py` hacia `float(getattr(primero, "SliceThickness", 0.0))`:
  - etiqueta AUSENTE -> `0.0`: un numero que el archivo no trae. Llegaba a la ventana de metadatos ("0", "No cumple"), al JSON que se archiva con la prueba
    (`espesor_mm: 0.0`), al texto de desviacion y al PDF firmado ("Espesor de corte [mm]: 0");
  - etiqueta VACIA -> `float(None)` lanzaba, `_load_dicoms` lo atrapaba con un `print` y la carpeta NO CARGABA, sin aviso;
  - y `DicomVolume` releia la misma etiqueta por su cuenta (dos lecturas de un dato) y de OTRO corte: `serie.py` tomaba el primer archivo del DISCO, `DicomVolume` el primer
    corte en el ESPACIO, que es de donde salen kV y mA.

Contrato nuevo: lo que el DICOM no publica es `None` de punta a punta (serie, volumen, adquisicion, JSON archivado, ventana, texto de desviacion), y el espesor sale del MISMO
corte que kV y mA. Los consumidores ya saben tratar un `None` (la comparacion con el protocolo dice "No cumple" y "no publicado"): el defecto estaba solo en el origen.
"""
import ast
import inspect
import json
import os
import textwrap

import pydicom
import pytest

from _corpus import serie_catphan
from _serie_sintetica import AUSENTE, serie_axial, serie_axial_con_localizador
from analisisImagenes.catphan.descripcion import NO_PUBLICADO
from analisisImagenes.catphan.protocolos import comparar_con_protocolo
from analisisImagenes.catphan.serie import _primer_numero, adquisicion_de_serie, leer_serie
from data.ManejoDatos.catphan_TAC import leer_dicom as leer_dicom_mod
from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume
from data.ManejoDatos.catphan_TAC.ventana_metadatos import CUMPLE, NO_CUMPLE, construir_modelo_ventana

CASOS = [("ausente", AUSENTE, None), ("vacia", None, None), ("sana", 2.0, 2.0)]      # (nombre, lo que se escribe, lo que debe leerse)
EQUIPO = "Tomógrafo"


# --------------------------------------------------------------------------------------------- una serie sintetica
class TestSerieSintetica:
    @pytest.mark.parametrize("nombre, escrito, esperado", CASOS, ids=[c[0] for c in CASOS])
    def test_carga_en_los_tres_casos(self, tmp_path, nombre, escrito, esperado):
        """Antes, con la etiqueta VACIA `leer_serie` lanzaba y la carpeta no abria."""
        carpeta = serie_axial(str(tmp_path), espesor=escrito)
        serie = leer_serie(carpeta)
        assert len(serie.cortes) == 5
        vol = DicomVolume(carpeta)
        assert vol.volumen_hu is not None and len(vol.cortes) == 5

    @pytest.mark.parametrize("nombre, escrito, esperado", CASOS, ids=[c[0] for c in CASOS])
    def test_la_serie_el_volumen_y_la_adquisicion_dicen_lo_mismo(self, tmp_path, nombre, escrito, esperado):
        carpeta = serie_axial(str(tmp_path), espesor=escrito)
        serie = leer_serie(carpeta)
        vol = DicomVolume(carpeta)
        adq = adquisicion_de_serie(serie)
        assert serie.espesor_mm == esperado
        assert vol.espesor_corte == esperado and vol.slice_thickness == esperado
        assert adq["espesor_mm"] == esperado
        assert vol.get_slice_thickness() == esperado
        if esperado is None:
            assert serie.espesor_mm is None and vol.espesor_corte is None and adq["espesor_mm"] is None
        else:
            assert isinstance(serie.espesor_mm, float)

    @pytest.mark.parametrize("nombre, escrito, esperado", CASOS, ids=[c[0] for c in CASOS])
    def test_la_ventana_de_metadatos_dice_que_no_lo_publica_y_el_protocolo_no_cumple(self, tmp_path, nombre, escrito, esperado):
        modelo = construir_modelo_ventana(DicomVolume(serie_axial(str(tmp_path), espesor=escrito)), EQUIPO)
        valor = dict(modelo.adquisicion)["Espesor de corte [mm]"]
        fila = next(f for f in modelo.protocolo if f.etiqueta.startswith("Espesor de corte"))
        if esperado is None:
            assert valor == NO_PUBLICADO, valor
            assert fila.estado == NO_CUMPLE and fila.encontrado == "no publicado"
            assert "Espesor de corte [mm]: no publicado" in modelo.resumen_desviacion
        else:
            assert valor == "2" and fila.estado == CUMPLE
            assert "Espesor de corte" not in (modelo.resumen_desviacion or "")

    @pytest.mark.parametrize("nombre, escrito, esperado", CASOS[:2], ids=["ausente", "vacia"])
    def test_el_texto_de_desviacion_dice_no_publicado_y_no_un_cero(self, tmp_path, nombre, escrito, esperado):
        adq = adquisicion_de_serie(leer_serie(serie_axial(str(tmp_path), espesor=escrito)))
        texto = comparar_con_protocolo(EQUIPO, adq).desviacion_texto()
        assert "Espesor de corte [mm]: no publicado (exigido 2 ± 0.05)" in texto
        assert ": 0 " not in texto and ": 0.0" not in texto

    @pytest.mark.parametrize("nombre, escrito, esperado", CASOS[:2], ids=["ausente", "vacia"])
    def test_el_json_que_se_archiva_con_la_prueba_no_lleva_un_cero_inventado(self, tmp_path, nombre, escrito, esperado):
        adq = adquisicion_de_serie(leer_serie(serie_axial(str(tmp_path), espesor=escrito)))
        archivado = json.loads(json.dumps(adq))
        assert "espesor_mm" in archivado and archivado["espesor_mm"] is None
        assert comparar_con_protocolo(EQUIPO, archivado).desviacion_texto() == comparar_con_protocolo(EQUIPO, adq).desviacion_texto()

    def test_con_un_localizador_de_espesor_vacio_y_la_serie_axial_sin_etiqueta_tambien_es_none(self, tmp_path):
        """El topograma real trae el espesor vacio; la serie que se analiza es la axial, y esa tampoco lo publica."""
        carpeta = serie_axial_con_localizador(str(tmp_path), espesor=AUSENTE)
        serie = leer_serie(carpeta)
        assert len(serie.cortes) == 5 and list(serie.series_descartadas.values()) == [1]
        assert serie.espesor_mm is None and DicomVolume(carpeta).espesor_corte is None


# ------------------------------------------------------------------------------- `_primer_numero`: lo que no es un numero es None
class TestPrimerNumero:
    """`serie._primer_numero` es la definicion de "el archivo publica un numero": ausente, vacio, texto o no finito son `None`; un multivalor da su primer valor."""

    @pytest.mark.parametrize("valor", [None, "", b"", "   ", "abc", "2,5 mm", [], (), float("nan"), float("inf"), float("-inf"), object()])
    def test_lo_que_no_es_un_numero_es_none(self, valor):
        assert _primer_numero(valor) is None

    @pytest.mark.parametrize("valor, esperado", [
        (2.0, 2.0), (2, 2.0), ("2.5", 2.5), (b"3", 3.0), ([1.5, 9.0], 1.5), (("4", "5"), 4.0), (0, 0.0), (0.0, 0.0), (-1.0, -1.0)])
    def test_un_numero_se_devuelve_como_float(self, valor, esperado):
        resultado = _primer_numero(valor)
        assert resultado == esperado and isinstance(resultado, float)

    def test_un_multivalor_de_pydicom_da_su_primer_valor(self):
        from pydicom.multival import MultiValue
        from pydicom.valuerep import DSfloat
        assert _primer_numero(MultiValue(DSfloat, [DSfloat("2.5"), DSfloat("3.0")])) == 2.5

    def test_un_cero_publicado_es_un_numero_y_no_un_dato_ausente(self):
        """Un `0.0` que el equipo SI publica es un numero (la guarda del guardado, SE.3, decide que hace con el): solo lo AUSENTE es `None`."""
        assert _primer_numero(0.0) == 0.0 and _primer_numero(0.0) is not None


# --------------------------------------------------- el espesor sale del primer corte ESPACIAL, no del primero del disco
class TestSaleDelMismoCorteQueKvYMa:
    def test_gana_el_corte_espacial_y_no_el_primer_archivo_del_disco(self, tmp_path):
        """En la serie, el primer archivo en el DISCO (`corte_0.dcm`) es el corte espacial 3 (3.0 mm); el primer corte en el ESPACIO es el 0 (2.0 mm). kV y mA salen del
        espacial; el espesor tiene que salir del mismo."""
        carpeta = serie_axial(str(tmp_path), espesor=3.0, espesores_por_corte={0: 2.0})
        primero_del_disco = pydicom.dcmread(os.path.join(carpeta, sorted(os.listdir(carpeta))[0]), stop_before_pixels=True)
        assert float(primero_del_disco.SliceThickness) == 3.0, "la preparacion no se armo: el primero del disco debia traer 3.0"
        serie = leer_serie(carpeta)
        assert serie.espesor_mm == 2.0
        assert DicomVolume(carpeta).espesor_corte == 2.0

    def test_si_el_corte_espacial_no_lo_publica_es_none_aunque_el_primero_del_disco_si(self, tmp_path):
        carpeta = serie_axial(str(tmp_path), espesor=2.0, espesores_por_corte={0: AUSENTE})
        serie = leer_serie(carpeta)
        assert serie.espesor_mm is None
        assert DicomVolume(carpeta).espesor_corte is None

    def test_leer_dicom_no_vuelve_a_leer_la_etiqueta(self):
        """Una sola lectura del espesor: la de `leer_serie`. Por AST (no por texto: los comentarios pueden nombrar la etiqueta)."""
        arbol = ast.parse(inspect.getsource(leer_dicom_mod))
        usos = [n for n in ast.walk(arbol)
                if (isinstance(n, ast.Attribute) and n.attr == "SliceThickness")
                or (isinstance(n, ast.Call) and any(isinstance(a, ast.Constant) and a.value == "SliceThickness" for a in n.args))]
        assert usos == [], [getattr(u, "lineno", None) for u in usos]

    def test_el_volumen_toma_el_espesor_de_la_serie(self):
        arbol = ast.parse(textwrap.dedent(inspect.getsource(leer_dicom_mod.DicomVolume._load_dicoms)))
        asignaciones = {}
        for n in ast.walk(arbol):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Attribute) and t.attr in ("slice_thickness", "espesor_corte"):
                        asignaciones[t.attr] = ast.unparse(n.value)
        assert asignaciones == {"slice_thickness": "serie.espesor_mm", "espesor_corte": "serie.espesor_mm"}


# ----------------------------------------------------------- la carpeta REAL del tomografo, reescrita en un directorio temporal
@pytest.fixture(scope="module")
def cortes_reales():
    ruta = serie_catphan("TOMOGRAFO")
    if ruta is None:
        pytest.skip("corpus Catphan no disponible en esta maquina: TOMOGRAFO")
    return [os.path.join(ruta, n) for n in sorted(os.listdir(ruta)) if n.lower().endswith(".dcm")][:8]


def _reescribir(cortes, destino, cambio):
    for ruta in cortes:
        ds = pydicom.dcmread(ruta)
        cambio(ds)
        ds.save_as(os.path.join(destino, os.path.basename(ruta)))
    return str(destino)


class TestCarpetaRealReescrita:
    """8 cortes REALES del tomografo con la etiqueta de espesor quitada o vaciada (como `variantes.py` del anexo del plan, V3 y V4)."""

    def test_sana_conserva_su_espesor(self, cortes_reales, tmp_path):
        carpeta = _reescribir(cortes_reales, tmp_path, lambda ds: None)
        assert leer_serie(carpeta).espesor_mm == 2.0 and DicomVolume(carpeta).espesor_corte == 2.0

    def test_sin_la_etiqueta_carga_y_dice_none(self, cortes_reales, tmp_path):
        carpeta = _reescribir(cortes_reales, tmp_path, lambda ds: delattr(ds, "SliceThickness"))
        serie = leer_serie(carpeta)
        vol = DicomVolume(carpeta)
        assert len(serie.cortes) == 8 and vol.volumen_hu is not None
        assert serie.espesor_mm is None and vol.espesor_corte is None
        assert (vol.kv, vol.ma) == (120, 200), "kV y mA no cambian: solo falta el espesor"

    def test_con_la_etiqueta_vacia_carga_y_dice_none(self, cortes_reales, tmp_path):
        def vaciar(ds):
            ds.SliceThickness = None

        carpeta = _reescribir(cortes_reales, tmp_path, vaciar)
        serie = leer_serie(carpeta)                       # antes: `float(None)` lanzaba y la carpeta no abria
        vol = DicomVolume(carpeta)
        assert len(serie.cortes) == 8 and vol.volumen_hu is not None
        assert serie.espesor_mm is None and vol.espesor_corte is None
        assert adquisicion_de_serie(serie)["espesor_mm"] is None
