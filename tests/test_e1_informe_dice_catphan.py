"""E.1 (PLAN_HANDOFF_IMAGENES_22-09.md §6): el informe PDF del sistema de imágenes
DICE que es un análisis de CatPhan.

CAUSA. **[medido sobre el PDF real de la sesión 47 del 21-09]** el encabezado de cada
página decía *"Control de calidad Control Sistema de Imágenes Halcyon"* y la caja del
título *"Control de calidad Control Sistema de Imágenes"*: ni una vez la palabra
CatPhan. El nombre `reporte_catphan_{equipo}_{fecha}.pdf` que el plan daba por el
nombre del archivo es un argumento MUERTO en esta ruta (`temp=True` escribe a memoria
y nunca lo usa); el visor sugiere `Control Sistema de Imágenes_{fecha}.pdf`. Y hay un
SEGUNDO productor de las mismas tablas: la sección de imágenes del PDF anual de
Halcyon y del iX, con su propio título escrito a mano.

Lo que este archivo garantiza:

  1. UN SOLO SITIO -- el nombre del análisis, el título y el nombre del archivo salen de
     `reportes_control_sistema_imagenes.py`; ningún otro archivo de producción escribe
     ese título (tripwire por AST).
  2. EL DOCUMENTO -- cada página del PDF real de las sesiones 47 (Halcyon), 48
     (Tomógrafo) y 42 (Tomógrafo, formato de fecha viejo) lleva el título, el equipo,
     la fecha y el número de sesión, y ya no lleva el encabezado anterior.
  3. LAS DOS RUTAS -- `sistema_imagenes=True/False`: con False (o con un equipo que no
     tiene informe de imágenes) el encabezado NO dice CatPhan. El título y la elección
     de tablas leen el mismo predicado.
  4. LO QUE NO SE NOMBRÓ NO CAMBIA -- un mensual de dosimetría sale con su encabezado de
     siempre, sin "Sesión" ni "CatPhan".
  5. EL ANUAL -- la sección de imágenes del PDF anual toma el título de la misma función.
"""
import ast
import os
import pathlib

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
import pandas as pd

import models.PDF.Imagenes.reportes_control_sistema_imagenes as rep_mod
from models.PDF.Imagenes.reportes_control_sistema_imagenes import (
    NOMBRE_ANALISIS, nombre_archivo_pdf, titulo_del_informe)
from models.PDF.pdf import generar_reporte_pdf_multitabla_mensual
# Fixtures y ayudas compartidas con E.3 y E.2 (BD copia, avisos sin diálogos, visor falso).
from _informe_imagenes import app, avisos, bd_copia, generar, paginas  # noqa: F401  (fixtures)

RAIZ = pathlib.Path(__file__).resolve().parent.parent

TITULO = "Análisis de CatPhan — Control de calidad del sistema de imágenes"
ENCABEZADO_ANTERIOR = "Control de calidad Control Sistema de Imágenes"

# (sesión, equipo, fecha tal como la guarda `controles`)
SESIONES = [
    (47, "Halcyon", "22/09/2026"),
    (48, "Tomógrafo", "22/09/2026"),
    (42, "Tomógrafo", "07/2026"),
]


def _paginas(pdf_bytes):
    return paginas(pdf_bytes)


def _generar(app, bd_copia, monkeypatch, ref, equipo, fecha, flag=True):
    return generar(bd_copia, monkeypatch, ref, equipo, fecha, flag)


# ---------------------------------------------------------------------------
# 1. UN SOLO SITIO
# ---------------------------------------------------------------------------

def test_el_titulo_es_el_del_plan():
    assert titulo_del_informe() == TITULO


def test_el_nombre_del_archivo_y_el_titulo_salen_del_mismo_nombre_del_analisis():
    """Intuición de garantía del plan: no pueden discrepar."""
    assert NOMBRE_ANALISIS in titulo_del_informe()
    nombre = nombre_archivo_pdf("Halcyon", "22/09/2026")
    assert nombre == "reporte_catphan_Halcyon_22/09/2026.pdf"
    assert NOMBRE_ANALISIS.lower() in nombre


def test_cambiar_el_nombre_del_analisis_cambia_el_titulo_y_el_archivo(monkeypatch):
    """Si el título o el nombre del archivo llevaran el nombre escrito a mano en vez de
    leer `NOMBRE_ANALISIS`, el cambio no llegaría a los dos: aquí se comprueba."""
    monkeypatch.setattr(rep_mod, "NOMBRE_ANALISIS", "Ejemplo")
    assert "Ejemplo" in rep_mod.titulo_del_informe()
    assert "CatPhan" not in rep_mod.titulo_del_informe()
    assert "ejemplo" in rep_mod.nombre_archivo_pdf("Halcyon", "22/09/2026")
    assert "catphan" not in rep_mod.nombre_archivo_pdf("Halcyon", "22/09/2026")


def _constantes_de_texto_de_produccion():
    """(archivo, línea, texto) de toda cadena de los .py de producción, salvo
    docstrings y tests."""
    for ruta in RAIZ.rglob("*.py"):
        rel = ruta.relative_to(RAIZ).as_posix()
        if rel.startswith(("tests/", ".venv/", "build/", "dist/")) or "/.venv/" in rel:
            continue
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        docstrings = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if (nodo.body and isinstance(nodo.body[0], ast.Expr)
                        and isinstance(nodo.body[0].value, ast.Constant)
                        and isinstance(nodo.body[0].value.value, str)):
                    docstrings.add(id(nodo.body[0].value))
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
                    and id(nodo) not in docstrings):
                yield rel, nodo.lineno, nodo.value


def test_solo_el_modulo_del_informe_escribe_el_titulo_del_control_de_imagenes():
    """Tripwire de CLASE: el título del control de imágenes escrito a mano en otro
    archivo (como estaba en el PDF anual) puede divergir del que sale del informe."""
    frase = "control de calidad del sistema de im"
    propios = []
    for rel, linea, texto in _constantes_de_texto_de_produccion():
        if frase in texto.lower():
            propios.append((rel, linea, texto))
    ajenos = [p for p in propios
              if p[0] != "models/PDF/Imagenes/reportes_control_sistema_imagenes.py"]
    assert ajenos == [], (
        "el título del control de imágenes está escrito a mano fuera de "
        f"reportes_control_sistema_imagenes.py: {ajenos}")
    assert propios, "el módulo del informe debe definir el título (una sola vez)"


def test_el_anual_toma_el_titulo_de_la_misma_funcion():
    """La sección de imágenes del PDF anual de Halcyon/iX es el SEGUNDO productor de
    estas tablas: su título sale de `titulo_del_informe()`, no de un literal."""
    fuente = (RAIZ / "models/PDF/Anual/reportes_anuales.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    asignaciones = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Assign):
            for destino in nodo.targets:
                if (isinstance(destino, ast.Subscript)
                        and isinstance(destino.slice, ast.Constant)
                        and destino.slice.value == "titulo_sistema_imagenes"):
                    asignaciones.append(nodo)
    assert len(asignaciones) == 1, "debe haber exactamente una asignación del título del anual"
    valor = asignaciones[0].value
    assert (isinstance(valor, ast.Call) and isinstance(valor.func, ast.Name)
            and valor.func.id == "titulo_del_informe"), (
        f"el título del anual debe salir de titulo_del_informe(); línea {asignaciones[0].lineno}")


# ---------------------------------------------------------------------------
# 2. EL DOCUMENTO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ref,equipo,fecha", SESIONES)
def test_cada_pagina_del_pdf_real_dice_que_es_un_analisis_de_catphan(
        app, bd_copia, avisos, monkeypatch, ref, equipo, fecha):
    ok, visor = _generar(app, bd_copia, monkeypatch, ref, equipo, fecha)
    assert ok is True and avisos == [], f"la generación falló: {avisos}"

    paginas = _paginas(visor["pdf"])
    assert len(paginas) >= 1
    for n, texto in enumerate(paginas, 1):
        assert TITULO in texto, f"la página {n} no lleva el título"
        assert ENCABEZADO_ANTERIOR not in texto, f"la página {n} conserva el encabezado anterior"
        assert equipo in texto, f"la página {n} no dice el equipo"
        assert fecha in texto, f"la página {n} no dice la fecha"
        assert f"Sesión N° {ref}" in texto, f"la página {n} no dice el número de sesión"
    # El título aparece dos veces por página: arriba a la derecha y en la caja.
    assert paginas[0].count(TITULO) == 2


def test_el_titulo_cabe_en_la_caja_y_no_pisa_el_logo(app, bd_copia, avisos, monkeypatch):
    """Medido sobre el PDF real, no calculado: un título más largo que el actual
    desbordaría la caja gris o se montaría sobre el logo (x < 165 pt)."""
    ok, visor = _generar(app, bd_copia, monkeypatch, 47, "Halcyon", "22/09/2026")
    assert ok is True
    doc = fitz.open(stream=visor["pdf"], filetype="pdf")
    pagina = doc[0]
    ancho = pagina.rect.width
    spans = [s for b in pagina.get_text("dict")["blocks"] if b.get("type") == 0
             for l in b["lines"] for s in l["spans"] if TITULO in s["text"]]
    assert len(spans) == 2
    caja = next(s for s in spans if s["size"] >= 13)            # la caja: Helvetica-Bold 14
    derecha = next(s for s in spans if s["size"] < 13)          # arriba a la derecha: 10
    assert caja["bbox"][0] >= 40 and caja["bbox"][2] <= ancho - 40, (
        f"el título desborda la caja del encabezado: {caja['bbox']}")
    assert derecha["bbox"][0] >= 165, f"el título pisa el logo: {derecha['bbox']}"
    assert derecha["bbox"][2] <= ancho - 40


def test_el_visor_recibe_los_mismos_argumentos_que_antes(app, bd_copia, avisos, monkeypatch):
    """Lo no nombrado no cambia: el nombre sugerido al guardar sigue saliendo de
    `tipo_reporte` (decisión abierta del físico, ver las notas de E.1)."""
    ok, visor = _generar(app, bd_copia, monkeypatch, 47, "Halcyon", "22/09/2026")
    assert ok is True
    assert visor["tipo_reporte"] == "Control Sistema de Imágenes"
    assert visor["maquina"] == "Halcyon" and visor["fecha"] == "22/09/2026"


# ---------------------------------------------------------------------------
# 3. LAS DOS RUTAS
# ---------------------------------------------------------------------------

def test_con_sistema_imagenes_false_el_encabezado_no_dice_catphan(
        app, bd_copia, avisos, monkeypatch):
    """La otra ruta (`sistema_imagenes=False`) es el informe de dosimetría: su
    encabezado no puede afirmar un análisis de CatPhan."""
    ok, visor = _generar(app, bd_copia, monkeypatch, 48, "Tomógrafo", "22/09/2026", flag=False)
    assert ok is True
    for texto in _paginas(visor["pdf"]):
        assert "CatPhan" not in texto
        assert "Sesión N°" not in texto
        assert ENCABEZADO_ANTERIOR in texto


def _tablas_con_marcas():
    """Una tabla de dosimetría y una de imágenes, cada una con una marca propia, para
    ver CUÁL de las dos imprime el generador."""
    return {
        "equipos": pd.DataFrame([["M_DOSI", "x"]], columns=["Métrica", "Valor"]),
        "espesor": pd.DataFrame([["M_IMAG", "x"]], columns=["Métrica", "Valor"]),
    }


def _texto(pdf):
    return "\n".join(_paginas(bytes(pdf.data())))


@pytest.mark.parametrize("maquina,flag", [
    ("Halcyon", False),          # dosimetría de Halcyon: NO es el informe de imágenes
    ("Clinac ix", False),        # dosimetría del iX
    ("Clinac 600", True),        # el 600 no tiene informe de imágenes aunque se pida
    ("Tomógrafo", False),        # sin la bandera, el tomógrafo tampoco
])
def test_el_generador_ignora_el_titulo_si_las_tablas_de_imagenes_no_se_imprimen(
        app, maquina, flag):
    """El título y la elección de tablas leen el MISMO predicado: sin las tablas de
    imágenes, el título de CatPhan no se puede colar en el encabezado -- y a la
    inversa, las tablas de imágenes no salen bajo un encabezado de dosimetría."""
    pdf = generar_reporte_pdf_multitabla_mensual(
        tablas=_tablas_con_marcas(), fecha="22/09/2026", user="Físico", tipo_reporte="Mensual",
        maquina=maquina, id_maquina=maquina, sistema_imagenes=flag, temp=True,
        titulo_informe=TITULO, sesion=99)
    texto = _texto(pdf)
    assert "CatPhan" not in texto
    assert "Sesión N°" not in texto
    assert "Control de calidad Mensual" in texto
    assert "M_IMAG" not in texto
    assert "M_DOSI" in texto


def test_braquiterapia_no_lleva_el_titulo_aunque_se_pida_el_informe_de_imagenes(app):
    pdf = generar_reporte_pdf_multitabla_mensual(
        tablas=_tablas_con_marcas(), fecha="22/09/2026", user="Físico", tipo_reporte="Mensual",
        maquina="Braquiterapia", id_maquina="Braquiterapia", sistema_imagenes=True, temp=True,
        titulo_informe=TITULO, sesion=99)
    texto = _texto(pdf)
    assert "CatPhan" not in texto and "Sesión N°" not in texto and "M_IMAG" not in texto


@pytest.mark.parametrize("maquina", ["Tomógrafo", "Halcyon", "Clinac ix"])
def test_el_generador_pone_el_titulo_cuando_si_se_imprimen_las_tablas_de_imagenes(app, maquina):
    pdf = generar_reporte_pdf_multitabla_mensual(
        tablas=_tablas_con_marcas(), fecha="22/09/2026", user="Físico",
        tipo_reporte="Control Sistema de Imágenes", maquina=maquina, id_maquina=maquina,
        sistema_imagenes=True, temp=True, titulo_informe=TITULO, sesion=7)
    texto = _texto(pdf)
    assert TITULO in texto and "Sesión N° 7" in texto and maquina in texto
    assert ENCABEZADO_ANTERIOR not in texto
    assert "M_IMAG" in texto and "M_DOSI" not in texto


# ---------------------------------------------------------------------------
# 4. LO QUE NO SE NOMBRÓ NO CAMBIA
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("maquina", ["Clinac 600", "Clinac ix", "Halcyon", "Tomógrafo"])
def test_un_mensual_de_dosimetria_conserva_su_encabezado(app, maquina):
    df = pd.DataFrame([["a", "b"]], columns=["Métrica", "Valor"])
    pdf = generar_reporte_pdf_multitabla_mensual(
        tablas={"equipos": df}, fecha="22/09/2026", user="Físico", tipo_reporte="Mensual",
        maquina=maquina, id_maquina=maquina, temp=True)
    texto = _paginas(bytes(pdf.data()))[0]
    assert f"Control de calidad Mensual {maquina}" in texto
    assert "Control de calidad Mensual" in texto
    assert "CatPhan" not in texto and "Sesión N°" not in texto
    assert "Fecha: 22/09/2026" in texto
