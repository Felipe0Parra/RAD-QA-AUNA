"""G.1 (PLAN_HANDOFF_IMAGENES_22-09.md, ajuste 23-09): el encabezado del
formulario de imágenes dice el PROTOCOLO OBLIGATORIO del equipo, arriba de la
fecha, EN LUGAR de "Atencion en Radioterapia".

CAUSA: nada en la pantalla decía con qué protocolo debe adquirirse la imagen.
El físico lo sabe o no lo sabe, y el archivo muestra que no siempre se supo (el
tomógrafo pasó por 179, 200, 272 y 400 mA en siete meses). `A.2` avisa DESPUÉS de
cargar; este texto avisa ANTES de irradiar, que es cuando todavía se puede
corregir. La frase que estaba ahí es la celda `D3` (`Subtittle1`) de las hojas de
encabezado de `data/widgets.xlsx` -- nueve hojas, de las cuales solo tres son de
imágenes.

Lo que este archivo garantiza:

  1. TEXTO -- sale del catálogo de `A.2` (equipo, protocolo, kV, mA, espesor, FOV,
     fantoma), dice las condiciones de consola sin confirmar, y un equipo sin
     protocolo lo dice en vez de inventar uno.
  2. LAS CINCO PANTALLAS DE IMAGENES -- tomógrafo, iX (mensual y anual), Halcyon
     (mensual y anual): cada una dice el protocolo de SU equipo, antes y después de
     "Iniciar" (el encabezado se reconstruye, DP-54), y ninguna dice "Atencion en
     Radioterapia".
  3. LA DOSIMETRIA NO CAMBIA -- 600, iX y Halcyon mensual y anual siguen diciendo
     lo que dice su hoja.
  4. UNA SOLA FUENTE -- el texto no está copiado en el Excel, y solo
     `protocolos.py` produce "Protocolo obligatorio".
  5. EL ENLACE -- "de dónde sale" muestra el origen, la fecha y lo que falta
     confirmar, una sola vez por clic.
  6. LA RAMA `esHC` ES INALCANZABLE -- verificado, no supuesto (el plan lo pedía).
"""
import ast
import os
import pathlib

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import openpyxl
import pytest
from PyQt5.QtWidgets import QApplication, QLabel, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from analisisImagenes.catphan.protocolos import (
    PROTOCOLOS, SIN_PROTOCOLO_ENCABEZADO, texto_encabezado, texto_origen)

RAIZ = pathlib.Path(__file__).resolve().parent.parent
FRASE_ANTERIOR = "Atencion en Radioterapia"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute("INSERT INTO users (fullname) VALUES ('Fisico Real')")
    conexion.con.commit()
    yield conexion.con
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture(autouse=True)
def sin_dialogos(monkeypatch):
    """Trampa 2: ningún QMessageBox real. `information` registra lo que se le pide."""
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    llamadas = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda parent, titulo, texto, *a, **k: llamadas.append((titulo, texto)))
    return llamadas


def _celda_subtittle1(hoja):
    ws = openpyxl.load_workbook(RAIZ / "data/widgets.xlsx", read_only=True, data_only=True)[hoja]
    for fila in ws.iter_rows(values_only=True):
        if fila and any(str(c) == "Subtittle1" for c in fila if c is not None):
            return next(str(c) for c in fila[3:4] if c is not None)
    raise AssertionError(f"la hoja {hoja} no tiene Subtittle1")


# ---------------------------------------------------------------------------
# 1. TEXTO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("equipo", sorted(PROTOCOLOS))
def test_el_texto_sale_del_catalogo(equipo):
    p, t = PROTOCOLOS[equipo], texto_encabezado(equipo)
    assert t.startswith("Protocolo obligatorio: ")
    for parte in (f"{p.kv:g} kV", f"{p.ma:g} mA", f"{p.espesor_mm:.1f} mm", f"FOV {p.fov_mm:g} mm", "fantoma"):
        assert parte in t, (equipo, parte)
    assert (p.descripcion_serie in t) if p.descripcion_serie else True
    # las condiciones de consola sin confirmar se DICEN, no se esconden
    assert p.condiciones_pendientes and "sin confirmar" in t


def test_el_texto_del_halcyon_es_el_del_plan():
    assert texto_encabezado("Halcyon") == (
        "Protocolo obligatorio: Pelvis_iCBCT_2.0_IQ! · 125 kV · 80 mA · 2.0 mm · FOV 491 mm · "
        "fantoma en posición estándar, la misma en los tres equipos (sin invertir 180°) · "
        "con condiciones de consola sin confirmar")


def test_el_ix_no_publica_nombre_y_el_texto_lo_describe_por_sus_parametros():
    t = texto_encabezado("Clinac ix")
    assert t.startswith("Protocolo obligatorio: 100 kV · 80 mA · 2.5 mm · FOV 250 mm")
    assert "None" not in t


def test_cada_equipo_tiene_un_texto_distinto():
    assert len({texto_encabezado(e) for e in PROTOCOLOS}) == len(PROTOCOLOS)


@pytest.mark.parametrize("equipo", ["Clinac 600", "esHC", "", None, "Equipo Inventado"])
def test_un_equipo_sin_protocolo_lo_dice_no_inventa_uno(equipo):
    assert texto_encabezado(equipo) == SIN_PROTOCOLO_ENCABEZADO
    assert "kV" not in texto_encabezado(equipo)


def test_el_origen_dice_de_donde_sale_cuando_y_que_falta():
    for equipo, p in PROTOCOLOS.items():
        o = texto_origen(equipo)
        assert p.origen in o and "23-09-2026" in o
        assert "corta la línea base" in o
        for condicion in p.condiciones_pendientes:
            assert condicion in o
    assert "no se inventa" in texto_origen("Clinac 600")


# ---------------------------------------------------------------------------
# 2. LAS CINCO PANTALLAS DE IMAGENES
# ---------------------------------------------------------------------------

def _tomografo():
    from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
    return PruebaMensualTAC(user_id=None)


def _ix_mensual():
    from ui.paginasControles.PruebasMensuales.ix_imagenes_mensual import PruebaImagenesIX
    return PruebaImagenesIX(user_id=None)


def _hc_mensual():
    from ui.paginasControles.PruebasMensuales.HC_imagenes_mensual import PruebaImagenesHC
    return PruebaImagenesHC(user_id=None)


def _ix_anual():
    from ui.paginasControles.PruebasAnuales.ix_anual import PruebaImagenesIX
    return PruebaImagenesIX(user_id=None)


def _hc_anual():
    from ui.paginasControles.PruebasAnuales.halcyon_anual import PruebaImagenesHalcyon
    return PruebaImagenesHalcyon(user_id=None)


FORMULARIOS = {
    "tomografo": (_tomografo, "Tomógrafo", "encabezado_mensu_TAC"),
    "ix_mensual": (_ix_mensual, "Clinac ix", "encabezado_images_ix"),
    "ix_anual": (_ix_anual, "Clinac ix", "encabezado_images_ix"),
    "hc_mensual": (_hc_mensual, "Halcyon", "encabezado_images_HC"),
    "hc_anual": (_hc_anual, "Halcyon", "encabezado_images_HC"),
}


@pytest.mark.parametrize("clave", sorted(FORMULARIOS))
def test_cada_pantalla_de_imagenes_dice_el_protocolo_de_su_equipo_antes_de_iniciar(app, bd_temporal, clave):
    construir, equipo, hoja = FORMULARIOS[clave]
    obj = construir()
    assert obj.equipo_f == equipo
    texto = obj.Subtittle1.text()
    assert html_a_texto(texto).startswith(texto_encabezado(equipo)), texto
    assert FRASE_ANTERIOR not in texto
    assert _celda_subtittle1(hoja) == FRASE_ANTERIOR, "la celda del Excel no se edita: seria una segunda copia"


def html_a_texto(html_str):
    """El QLabel guarda el HTML que se le puso; lo que el físico lee es su texto."""
    import html as _h
    import re
    return _h.unescape(re.sub(r"<[^>]+>", "", html_str))


def test_el_texto_cambia_con_el_equipo_y_coincide_entre_mensual_y_anual(app, bd_temporal):
    textos = {k: html_a_texto(FORMULARIOS[k][0]().Subtittle1.text()) for k in FORMULARIOS}
    assert textos["ix_mensual"] == textos["ix_anual"]
    assert textos["hc_mensual"] == textos["hc_anual"]
    assert len({textos["tomografo"], textos["ix_mensual"], textos["hc_mensual"]}) == 3


def test_tras_iniciar_el_encabezado_se_reconstruye_y_sigue_diciendo_el_protocolo(app, bd_temporal):
    """DP-54: `setupBox` crea un `Subtittle1` NUEVO al iniciar. Sin volver a
    escribirlo, el protocolo desaparecería justo cuando el físico empieza."""
    obj = _tomografo()
    antes = obj.Subtittle1
    obj.fisico1.addItem("Fisico Real", 1)
    obj.fisico1.setCurrentIndex(obj.fisico1.count() - 1)
    obj.user_id_f1 = "Fisico Real"
    obj.user_id_f2 = None
    obj._iniciar_moviendo_tabla(
        ["encabezado_mensu_TAC", "Control mensual", "Iniciar control mensual", "Tomógrafo", "preguntas_mensu_TAC"])
    assert obj.ref is not None
    assert obj.Subtittle1 is not antes, "el encabezado debia reconstruirse (DP-54): el test no probaria nada"
    texto = html_a_texto(obj.Subtittle1.text())
    assert texto.startswith(texto_encabezado("Tomógrafo")) and FRASE_ANTERIOR not in texto


@pytest.mark.parametrize("clave", ["ix_mensual", "hc_mensual"])
def test_las_pantallas_de_imagenes_de_los_aceleradores_tambien_lo_conservan_tras_iniciar(app, bd_temporal, clave):
    construir, equipo, _hoja = FORMULARIOS[clave]
    obj = construir()
    obj.fisico1.addItem("Fisico Real", 1)
    obj.fisico1.setCurrentIndex(obj.fisico1.count() - 1)
    obj.user_id_f1 = "Fisico Real"
    obj.user_id_f2 = None
    antes = obj.Subtittle1
    # lo mismo que hace `iniGUI` de TAC: primero los gráficos (crean `canvas`),
    # luego el formulario, que reconstruye el encabezado
    obj.graphicsWindow()
    obj.controlTestWindow(sheet_name="preguntas_mensu_TAC")
    assert obj.Subtittle1 is not antes
    assert html_a_texto(obj.Subtittle1.text()).startswith(texto_encabezado(equipo))


# ---------------------------------------------------------------------------
# 3. LA DOSIMETRIA NO CAMBIA
# ---------------------------------------------------------------------------

def test_los_formularios_de_dosimetria_siguen_diciendo_lo_que_dice_su_hoja(app, bd_temporal):
    from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
    from ui.paginasControles.PruebasMensuales.ix_mensual import PruebaMensualIX
    from ui.paginasControles.PruebasMensuales.halcyon_mensual import PruebaMensualHc
    esperados = {
        "600": (PruebaMensual600(user_id=None, equipo_f="Clinac 600"), "encabezado_mensu_600"),
        "ix": (PruebaMensualIX(user_id=None), "encabezado_mensu_IX"),
        "halcyon": (PruebaMensualHc(user_id=None), "encabezado_mensu_Halcyon"),
    }
    for nombre, (obj, hoja) in esperados.items():
        assert obj.Subtittle1.text() == _celda_subtittle1(hoja) == FRASE_ANTERIOR, nombre
        assert "Protocolo" not in obj.Subtittle1.text()


def test_los_formularios_de_dosimetria_no_llaman_a_la_funcion_del_encabezado():
    """Estructural: solo `PruebaMensualTAC` define y llama a
    `_escribir_protocolo_en_encabezado`; ninguna clase de dosimetría."""
    duenos = set()
    for ruta in RAIZ.rglob("*.py"):
        rel = ruta.relative_to(RAIZ).as_posix()
        if rel.startswith(("tests/", ".venv/", "build/", "dist/")):
            continue
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if isinstance(n, ast.Attribute) and n.attr == "_escribir_protocolo_en_encabezado":
                duenos.add(rel)
            if isinstance(n, ast.FunctionDef) and n.name == "_escribir_protocolo_en_encabezado":
                duenos.add(rel)
    assert duenos == {"ui/paginasControles/PruebasMensuales/tac_mensual.py"}, duenos


# ---------------------------------------------------------------------------
# 4. UNA SOLA FUENTE
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hoja", ["encabezado_mensu_TAC", "encabezado_images_ix", "encabezado_images_HC"])
def test_el_excel_no_lleva_una_segunda_copia_del_protocolo(hoja):
    celda = _celda_subtittle1(hoja)
    assert celda == FRASE_ANTERIOR and "rotocolo" not in celda and "kV" not in celda


def test_solo_protocolos_py_produce_la_frase_del_encabezado():
    hallados = set()
    for ruta in RAIZ.rglob("*.py"):
        rel = ruta.relative_to(RAIZ).as_posix()
        if rel.startswith(("tests/", ".venv/", "build/", "dist/")):
            continue
        for n in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and "Protocolo obligatorio" in n.value:
                hallados.add(rel)
    assert hallados == {"analisisImagenes/catphan/protocolos.py"}, hallados


# ---------------------------------------------------------------------------
# 5. EL ENLACE "de dónde sale"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clave", ["tomografo", "ix_mensual", "hc_mensual"])
def test_el_enlace_muestra_el_origen_de_SU_equipo_una_sola_vez_por_clic(app, bd_temporal, sin_dialogos, clave):
    """Los tres equipos, y el TEXTO completo (no solo el titulo): un enlace que
    mostrara el origen de otro equipo pasaria una prueba hecha con uno solo."""
    construir, equipo, _hoja = FORMULARIOS[clave]
    obj = construir()
    etiqueta = obj.Subtittle1
    assert "de dónde sale" in etiqueta.text() and "href" in etiqueta.text()

    etiqueta.linkActivated.emit("origen")
    assert len(sin_dialogos) == 1
    titulo, texto = sin_dialogos[0]
    assert titulo == f"Protocolo de {equipo}"
    assert texto == texto_origen(equipo)
    assert PROTOCOLOS[equipo].origen in texto
    otros = [e for e in PROTOCOLOS if e != equipo]
    assert all(PROTOCOLOS[o].origen not in texto for o in otros)

    obj._escribir_protocolo_en_encabezado()                  # se vuelve a escribir sobre el MISMO widget
    etiqueta.linkActivated.emit("origen")
    assert len(sin_dialogos) == 2, "reescribir el encabezado no debe duplicar la conexion del enlace"


def test_el_enlace_del_encabezado_reconstruido_tambien_funciona(app, bd_temporal, sin_dialogos):
    obj = _tomografo()
    obj.fisico1.addItem("Fisico Real", 1)
    obj.fisico1.setCurrentIndex(obj.fisico1.count() - 1)
    obj.user_id_f1 = "Fisico Real"
    obj.user_id_f2 = None
    obj._iniciar_moviendo_tabla(
        ["encabezado_mensu_TAC", "Control mensual", "Iniciar control mensual", "Tomógrafo", "preguntas_mensu_TAC"])
    sin_dialogos.clear()                 # "Iniciar" ya avisó de su propio éxito
    obj.Subtittle1.linkActivated.emit("origen")
    assert sin_dialogos == [("Protocolo de Tomógrafo", texto_origen("Tomógrafo"))]


def test_el_texto_del_encabezado_no_se_interpreta_como_html(app, bd_temporal):
    """El texto del catálogo se escapa: un `<` o `&` en un protocolo no puede
    romper el encabezado ni inyectar marcado."""
    import analisisImagenes.catphan.protocolos as prot
    original = prot.PROTOCOLOS["Halcyon"]
    try:
        import dataclasses
        prot.PROTOCOLOS["Halcyon"] = dataclasses.replace(original, descripcion_serie="A<b>&B")
        obj = _hc_mensual()
        assert "&lt;b&gt;" in obj.Subtittle1.text() and "<b>" not in obj.Subtittle1.text()
    finally:
        prot.PROTOCOLOS["Halcyon"] = original


# ---------------------------------------------------------------------------
# 6. LA RAMA `esHC` ES INALCANZABLE
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clave", sorted(FORMULARIOS))
def test_ninguna_pantalla_de_imagenes_cae_en_la_rama_esHC(app, bd_temporal, clave):
    """`PruebaMensualTAC.__init__` tiene una rama `equipo_f = 'esHC'` (hoja de
    dosimetria anual de Halcyon para un formulario de imagenes). El plan pedia
    comprobar si se alcanza antes de reescribir su rotulo: no se alcanza."""
    obj = FORMULARIOS[clave][0]()
    assert obj.equipo_f != "esHC" and obj.equipo_f in PROTOCOLOS


def test_esHc_solo_lo_asigna_la_dosimetria_de_halcyon_que_no_hereda_del_tac():
    asignan = set()
    for ruta in (RAIZ / "ui").rglob("*.py"):
        for n in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Assign) and any(
                    isinstance(t, ast.Attribute) and t.attr == "esHc" for t in n.targets):
                asignan.add(ruta.relative_to(RAIZ).as_posix())
    assert asignan == {"ui/paginasControles/PruebasMensuales/halcyon_mensual.py"}, asignan
    from ui.paginasControles.PruebasMensuales.halcyon_mensual import PruebaMensualHc
    from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
    assert not issubclass(PruebaMensualHc, PruebaMensualTAC)
    assert not issubclass(PruebaMensualTAC, PruebaMensualHc)
