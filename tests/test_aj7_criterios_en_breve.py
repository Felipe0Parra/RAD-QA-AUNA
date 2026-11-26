"""AJ.7: el criterio de cada prueba del Catphan, en breve: la regla, el numero y la norma, sin identificadores internos, el mismo texto en la pestana y en el PDF,
y en la tabla del PDF la fuente de filas seguidas de la misma prueba, una vez, en una celda unida. Ningun criterio, tolerancia ni veredicto cambia; lo guardado se imprime como se guardo.
Datos reales: una COPIA de los tres archivos de la copia 23-11 (Tomografo 01/10/2026, con su criterio archivado; Halcyon 06/2026; iX 05/2026)."""
import ast
import bisect
import html
import json
import os
import re
import shutil
import sqlite3
from collections import Counter
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz  # noqa: E402
import pandas as pd  # noqa: E402
from PyQt5 import sip  # noqa: E402
from PyQt5.QtWidgets import QMessageBox  # noqa: E402

import data.ManejoDatos.conection as conection_mod  # noqa: E402
import models.PDF.Imagenes.reportes_control_sistema_imagenes as rep_mod  # noqa: E402
import models.PDF.pdf as pdf_mod  # noqa: E402
from _bd_referencia import BD_REBUILD_23_11  # noqa: E402
from _e1_ayudas import cerrar  # noqa: E402
from _formularios_imagenes import FORMULARIOS, app, bd_temporal, iniciar, sin_dialogos  # noqa: E402,F401  (fixtures)
from _informe_imagenes import FalsoVisor, Padre  # noqa: E402
from analisisImagenes.catphan import criterios  # noqa: E402
from analisisImagenes.catphan.criterios import MOTIVO_PENDIENTE, juzgar, texto_criterio, texto_fuente, texto_html  # noqa: E402
from analisisImagenes.catphan.perfiles import PERFILES, ReglaPrueba  # noqa: E402
from models.PDF.Imagenes.reportes_control_sistema_imagenes import ReporteControlSistemaImagenes  # noqa: E402
from ui.paginasControles.PruebasMensuales.tac_mensual import CategoriasMapping  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
EQUIPOS = ("Tomógrafo", "Clinac ix", "Halcyon")
TITULO = "Criterio y veredicto del equipo"
MARCO_X = (40.0, 572.0)  # margenes izquierdo y derecho de la pagina carta [pt]

# La tabla del plan (22 filas, aprobadas por el fisico): (equipo, prueba, campo) -> texto nuevo
FUENTES = {
    ("Tomógrafo", "geometria"): "AAPM TG-66 (integridad espacial, 1 mm)",
    ("Tomógrafo", "espesor"): "AAPM TG-66 (espesor de corte, ±1 mm)",
    ("Tomógrafo", "numeros_ct"): "TG-66, constancia mensual: 20 HU tejido blando; 50 HU pulmón y hueso",
    ("Tomógrafo", "linealidad"): "Criterio de la app, sin norma; por confirmar",
    ("Tomógrafo", "uniformidad"): "AAPM TG-66 (uniformidad de campo, mensual)",
    ("Tomógrafo", "ruido"): "TG-66 remite al fabricante",
    ("Tomógrafo", "bajo_contraste"): "Con el juicio visual del físico como complemento",
    ("Tomógrafo", "resolucion_espacial"): "Línea base (TG-66: según el fabricante); máximo medible ≈4.65 lp/cm con FOV 550 mm",
    ("Clinac ix", "geometria"): "AAPM TG-142 Tabla VI (≤2 mm; ≤1 mm en SRS/SBRT)",
    ("Clinac ix", "espesor"): "Jefe de física, 18-09-2026",
    ("Clinac ix", "numeros_ct"): "AAPM TG-142 y TG-179; HU sin calibrar: solo contra su línea base",
    ("Clinac ix", "linealidad"): "AAPM TG-142 no la pide para CBCT",
    ("Clinac ix", "uniformidad"): "Varian / AAPM TG-142 (línea base)",
    ("Clinac ix", "ruido"): "AAPM TG-142 (línea base)",
    ("Clinac ix", "bajo_contraste"): "Con el juicio visual del físico como complemento",
    ("Clinac ix", "resolucion_espacial"): "Varian (full-fan, ≥6 lp/cm); métrica por confirmar",
    ("Halcyon", "geometria"): "Formato anual del servicio, 2025 (hoy CLA-F-RT-120)",
    ("Halcyon", "espesor"): "Jefe de física, 18-09-2026",
    ("Halcyon", "numeros_ct"): "AAPM TG-179 (±30 HU tejido; ±50 HU pulmón y hueso) y Varian (±50 HU)",
    ("Halcyon", "linealidad"): "Informativo",
    ("Halcyon", "uniformidad"): "Formato anual del servicio, 2025 (hoy CLA-F-RT-120)",
    ("Halcyon", "ruido"): "AAPM TG-142 (línea base)",
    ("Halcyon", "bajo_contraste"): "El formato anual pide además el menor círculo visible en 1 %, 0.5 % y 0.3 %",
    ("Halcyon", "resolucion_espacial"): "Formato anual (≥5 lp/cm, visual) y TG-179; máximo medible ≈5.2 lp/cm",
}
MOTIVO_ESPESOR = "No aplica a la CBCT de acelerador (TG-142 Tabla VI no lo incluye)"
MOTIVOS = {
    "geometria": "la app mide el tamaño del píxel, no las cuatro distancias de 50 mm",
    "bajo_contraste": "la regla cuenta insertos de 1 % visibles; la app cuenta ROI por CNR y por visibilidad (5 o 6 de 6 en todas las series); decide el físico",
    "resolucion_espacial": "la regla pide la MTF al 10 %; la app reporta los pares de líneas que resuelve, que con el píxel del Halcyon no demuestran 5 lp/cm",
}

# Cada norma y cada numero que hoy definen el criterio siguen escritos
DEBEN_SEGUIR = {
    ("Tomógrafo", "espesor"): ("TG-66", "±1 mm"), ("Tomógrafo", "numeros_ct"): ("TG-66", "20 HU", "50 HU"),
    ("Tomógrafo", "ruido"): ("TG-66",), ("Tomógrafo", "resolucion_espacial"): ("TG-66", "4.65 lp/cm", "550 mm"),
    ("Clinac ix", "geometria"): ("TG-142", "≤2 mm", "≤1 mm", "SRS/SBRT"), ("Clinac ix", "numeros_ct"): ("TG-142", "TG-179"),
    ("Clinac ix", "linealidad"): ("TG-142",), ("Clinac ix", "uniformidad"): ("Varian", "TG-142"), ("Clinac ix", "ruido"): ("TG-142",),
    ("Clinac ix", "resolucion_espacial"): ("Varian", "≥6 lp/cm"), ("Halcyon", "geometria"): ("Formato anual", "CLA-F-RT-120"),
    ("Halcyon", "uniformidad"): ("Formato anual", "CLA-F-RT-120"), ("Halcyon", "numeros_ct"): ("TG-179", "±30 HU", "±50 HU", "Varian"),
    ("Halcyon", "ruido"): ("TG-142",), ("Halcyon", "bajo_contraste"): ("Formato anual", "1 %", "0.5 %", "0.3 %"),
    ("Halcyon", "resolucion_espacial"): ("Formato anual", "≥5 lp/cm", "TG-179", "5.2 lp/cm"),
}
MOTIVOS_DEBEN_SEGUIR = {"geometria": ("50 mm",), "bajo_contraste": ("1 %", "5 o 6 de 6"), "resolucion_espacial": ("MTF al 10 %", "5 lp/cm")}
IDENTIFICADORES = re.compile(r"\bP[1-9]\b|\bB\.1\b|\bG\.3\b|\bDA-|\bDP-|del plan", re.IGNORECASE)

# Lo que juzga cada regla, medido antes de la tarea: (aplica, tipo, nominal, tolerancia, unidad, estado); las metricas, las mismas en los tres equipos
METRICAS_DE_HOY = {
    "geometria": ("geo_x1_mm", "geo_x2_mm", "geo_y1_mm", "geo_y2_mm"), "espesor": ("espesor_mm",),
    "numeros_ct": ("hu_aire", "hu_pmp", "hu_ldpe", "hu_poliestireno", "hu_acrilico", "hu_delrin", "hu_teflon"), "linealidad": ("linealidad_r2",),
    "uniformidad": ("unif_max_dif_hu",), "ruido": ("ruido_centro_hu",), "bajo_contraste": ("lc_visibles_1pct",), "resolucion_espacial": ("mtf10_lpcm",),
}
REGLAS_DE_HOY = {
    "Tomógrafo": {"geometria": ("si", "abs_nominal", 50.0, 1.0, "mm", "norma"), "espesor": ("si", "abs_nominal", None, 1.0, "mm", "norma"),
                  "numeros_ct": ("si", "linea_base_abs", None, {"hu_pmp": 20.0, "hu_ldpe": 20.0, "hu_poliestireno": 20.0, "hu_acrilico": 20.0, "hu_aire": 50.0, "hu_delrin": 50.0, "hu_teflon": 50.0}, "HU", "propuesta"),
                  "linealidad": ("si", "min", None, 0.99, "1", "propuesta"), "uniformidad": ("si", "max", None, 5.0, "HU", "norma"),
                  "ruido": ("si", "linea_base_rel", None, 0.2, "1", "propuesta"), "bajo_contraste": ("si", "linea_base_min", None, 1.0, "conteo", "propuesta"),
                  "resolucion_espacial": ("si", "linea_base_min", None, 0.0, "lp/cm", "propuesta")},
    "Clinac ix": {"geometria": ("si", "abs_nominal", 50.0, 2.0, "mm", "norma"), "espesor": ("no", None, None, None, "", ""),
                  "numeros_ct": ("si", "linea_base_abs", None, 50.0, "HU", "norma"), "linealidad": ("informativo", None, None, None, "", "norma"),
                  "uniformidad": ("si", "max", None, 40.0, "HU", "norma"), "ruido": ("si", "linea_base_rel", None, 0.2, "1", "norma"),
                  "bajo_contraste": ("si", "linea_base_min", None, 1.0, "conteo", "propuesta"), "resolucion_espacial": ("si", "min", None, 6.0, "lp/cm", "norma")},
    "Halcyon": {"geometria": ("si", "abs_nominal", 50.0, 0.5, "mm", "confirmada"), "espesor": ("no", None, None, None, "", ""),
                "numeros_ct": ("si", "linea_base_abs", None, {"hu_pmp": 30.0, "hu_ldpe": 30.0, "hu_poliestireno": 30.0, "hu_acrilico": 30.0, "hu_aire": 50.0, "hu_delrin": 50.0, "hu_teflon": 50.0}, "HU", "norma"),
                "linealidad": ("informativo", None, None, None, "", "propuesta"), "uniformidad": ("si", "max", None, 40.0, "HU", "confirmada"),
                "ruido": ("si", "linea_base_rel", None, 0.2, "1", "norma"), "bajo_contraste": ("si", "linea_base_min", None, 1.0, "conteo", "propuesta"),
                "resolucion_espacial": ("si", "min", None, 5.0, "lp/cm", "confirmada")},
}

# El conjunto sintetico de cada equipo (las siete pruebas) y la altura [pt] de su tabla de criterio antes de la tarea
MATERIALES = ("Aire", "PMP", "LDPE", "Poliestireno", "Acrílico", "Delrin", "Teflón")
HU = (-999.1, -186.0, -94.3, -36.5, 122.0, 322.8, 917.3)
UNIF = {"Centro": {"promedio_hu": 0.0, "desviacion": 5.0}, "Arriba": {"promedio_hu": 2.0, "desviacion": 15.0},
        "Abajo": {"promedio_hu": -1.0, "desviacion": 15.0}, "Izquierda": {"promedio_hu": 0.0, "desviacion": 15.0},
        "Derecha": {"promedio_hu": 0.5, "desviacion": 15.0}, "Uniformidad": {"max_diferencia": 2.0, "pasa_global": True}}
MEDIDAS = [("Espesor de corte", "espesor", 1, {"espesor_promedio_mm": 1.92, "espesor_teorico_mm": 2.0}),
           ("Tamaño de pixel", "tamano_pixel", 2, {"X": 1.07, "Y": 1.07, "tam_px_teorico": 1.074}),
           ("Resolución de contraste", "resolucion_contraste", 3, {"resumen": {"rois_visibles_cnr": 5}}),
           ("Resolución espacial", "resolucion_espacial", 4, {"regiones": {}}),
           ("Valores CT", "valores_ct", 5, [{"material": m, "promedio_hu": v, "std_hu": 5.0, "rango_hu": (0, 0)} for m, v in zip(MATERIALES, HU)]),
           ("Linealidad CT", "linealidad_ct", 6, {"r_squared": 0.999}),
           ("Uniformidad", "uniformidad", 7, UNIF)]
ALTO_DE_HOY_PT = {"Tomógrafo": 1327.0, "Clinac ix": 1555.0, "Halcyon": 1123.0}  # medido sobre la base, logs del pre-vuelo
SESIONES = {"Tomógrafo": (48, "01/10/2026"), "Halcyon": (34, "06/2026"), "Clinac ix": (30, "05/2026")}


def _plano(texto):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", texto.replace("&mdash;", "—")))).strip()


def _textos_de(equipo):
    """Todos los textos de criterio y fuente que un analisis nuevo de las siete pruebas archiva para `equipo`."""
    return [j for _, cat, _, res in MEDIDAS for j in juzgar(equipo, cat, res)]


# 1. CADA TEXTO ES LITERALMENTE EL DE LA TABLA

@pytest.mark.parametrize("equipo, prueba", sorted(FUENTES))
def test_la_fuente_de_cada_regla_es_la_de_la_tabla(equipo, prueba):
    assert PERFILES[equipo].reglas[prueba].fuente == FUENTES[(equipo, prueba)]


@pytest.mark.parametrize("equipo", ("Clinac ix", "Halcyon"))
def test_el_espesor_de_los_aceleradores_dice_su_motivo_breve(equipo):
    regla = PERFILES[equipo].reglas["espesor"]
    assert regla.motivo_no_aplica == MOTIVO_ESPESOR and texto_criterio(regla, "espesor_mm") == MOTIVO_ESPESOR


@pytest.mark.parametrize("prueba", sorted(MOTIVOS))
def test_el_motivo_de_cada_pendiente_es_el_de_la_tabla(prueba):
    assert MOTIVO_PENDIENTE[prueba] == MOTIVOS[prueba]


def test_con_tolerancia_cero_el_criterio_no_dice_menos_cero():
    regla = PERFILES["Tomógrafo"].reglas["resolucion_espacial"]
    assert texto_criterio(regla, "mtf10_lpcm") == "no menos de la línea base"
    assert texto_criterio(ReglaPrueba("si", ("x",), "linea_base_min", tolerancia=0.0, unidad="mm"), "x") == "no menos de la línea base"
    assert texto_criterio(PERFILES["Tomógrafo"].reglas["bajo_contraste"], "lc_visibles_1pct") == "no menos de la línea base − 1 conteo"
    assert texto_criterio(ReglaPrueba("si", ("x",), "linea_base_min", tolerancia=0.5, unidad="lp/cm"), "x") == "no menos de la línea base − 0.5 lp/cm"


# 2. SIN IDENTIFICADORES INTERNOS Y SIN REPETIR LO QUE AGREGA texto_fuente

@pytest.mark.parametrize("equipo", EQUIPOS)
def test_ningun_texto_lleva_identificadores_internos_ni_del_plan(equipo):
    malos = [(j.prueba, t) for j in _textos_de(equipo) for t in (j.criterio, texto_fuente(j)) if IDENTIFICADORES.search(t)]
    assert not malos, malos


@pytest.mark.parametrize("equipo", EQUIPOS)
def test_ninguna_fuente_repite_su_estado(equipo):
    repetidas = [(p, r.fuente) for p, r in PERFILES[equipo].reglas.items() if r.estado and r.estado in r.fuente.lower()]
    assert not repetidas, repetidas
    dos_veces = [texto_fuente(j) for j in _textos_de(equipo) if j.estado_regla and texto_fuente(j).lower().count(j.estado_regla) != 1]
    assert not dos_veces, dos_veces


# 3. LAS NORMAS Y LOS NUMEROS SIGUEN ESCRITOS; LAS REGLAS NO CAMBIAN

@pytest.mark.parametrize("equipo, prueba", sorted(DEBEN_SEGUIR))
def test_cada_norma_y_cada_numero_siguen_escritos(equipo, prueba):
    regla = PERFILES[equipo].reglas[prueba]
    texto = f"{regla.fuente} {regla.motivo_no_aplica or ''}".lower()
    assert all(t.lower() in texto for t in DEBEN_SEGUIR[(equipo, prueba)]), (texto, DEBEN_SEGUIR[(equipo, prueba)])


@pytest.mark.parametrize("prueba", sorted(MOTIVOS_DEBEN_SEGUIR))
def test_cada_motivo_conserva_sus_numeros(prueba):
    assert all(t in MOTIVO_PENDIENTE[prueba] for t in MOTIVOS_DEBEN_SEGUIR[prueba])


@pytest.mark.parametrize("equipo", EQUIPOS)
def test_las_tolerancias_y_los_estados_de_cada_regla_no_cambian(equipo):
    hoy = {p: (r.aplica, r.tipo_tolerancia, r.nominal, r.tolerancia, r.unidad, r.estado, r.metricas) for p, r in PERFILES[equipo].reglas.items()}
    assert hoy == {p: (*v, METRICAS_DE_HOY[p]) for p, v in REGLAS_DE_HOY[equipo].items()}


# 4. LA PESTANA MUESTRA LOS MISMOS TEXTOS QUE ARCHIVA PARA EL PDF

@pytest.fixture
def formularios(app, bd_temporal):
    """Las pantallas que arma una prueba: al terminar se cierran (Trampa 9) y se exige que queden destruidas."""
    armadas = []
    yield armadas
    for obj in armadas:
        cerrar(obj)
    vivas = [type(obj).__name__ for obj in armadas if not sip.isdeleted(obj)]
    assert not vivas, f"formularios sin destruir: {vivas}"


@pytest.mark.parametrize("clave", sorted(FORMULARIOS))
def test_la_pestana_muestra_los_mismos_textos_que_imprime_el_pdf(formularios, clave):
    constructor, equipo, _hoja = FORMULARIOS[clave]
    obj = constructor()
    formularios.append(obj)
    iniciar(obj)
    obj.criterios_por_categoria = {}
    for _, cat, _, res in MEDIDAS:
        nombre = CategoriasMapping.MAPEO_COMPLETO[cat]["pestaña"]
        pestana = obj._widgets_de(nombre) or obj._crear_nueva_tab(nombre)
        obj._mostrar_criterio(cat, res)
        panel = _plano(pestana["criterio"].text())
        archivados = [criterios.Juicio(**d) for d in obj.criterios_por_categoria[cat]]
        assert archivados == juzgar(equipo, cat, res)
        for j in archivados:
            assert _plano(j.criterio) in panel and _plano(texto_fuente(j)) in panel, (cat, j.criterio, texto_fuente(j), panel)
    assert texto_html(juzgar(equipo, "valores_ct", MEDIDAS[4][3])).count(FUENTES[(equipo, "numeros_ct")]) == 7


# 5. LA FUENTE REPETIDA, UNA VEZ, EN UNA CELDA UNIDA

def _maqueta_uniones():
    from models.PDF.Imagenes import maqueta_catphan
    assert hasattr(maqueta_catphan, "uniones_de_criterio"), "la maqueta no une las celdas de la fuente"
    return maqueta_catphan.uniones_de_criterio


def _df(filas):
    cab = [["Prueba", "Métrica", "Valor", "Criterio", "Veredicto", "Fuente"]]
    return pd.DataFrame(cab + [list(f) for f in filas], columns=[TITULO, "", "", "", "", ""], dtype=object)


def _fila(prueba, fuente, metrica="m"):
    return [prueba, metrica, "---", "c", "Sin línea base", fuente]


@pytest.mark.parametrize("filas, esperado", [
    ([_fila("Valores CT", "F (norma)", m) for m in MATERIALES], [("SPAN", (5, 2), (5, 8))]),
    ([_fila("Espesor de corte", "A"), _fila("Valores CT", "F")] + [_fila("Valores CT", "F")] * 6 + [_fila("Linealidad CT", "L")], [("SPAN", (5, 3), (5, 9))]),
    ([_fila("Uniformidad", "U"), _fila("Uniformidad", "R")], []),
    ([_fila("Tamaño de pixel", "X"), _fila("Uniformidad", "X")], []),
    ([_fila("Valores CT", "---")] * 3, []),
    ([_fila("Valores CT", "F")] * 2 + [_fila("Valores CT", "G")] * 3, [("SPAN", (5, 2), (5, 3)), ("SPAN", (5, 4), (5, 6))]),
    ([_fila("Valores CT", "F")], []),
    ([], []),
])
def test_la_fuente_de_filas_seguidas_de_una_prueba_se_une_en_una_celda(filas, esperado):
    assert _maqueta_uniones()(_df(filas)) == esperado


@pytest.mark.parametrize("equipo", EQUIPOS)
def test_ninguna_fila_pierde_su_fuente_al_unir(equipo):
    df = _tabla_de(equipo)
    uniones = _maqueta_uniones()(df)
    filas = df.values.tolist()[1:]
    for _, (c0, r0), (c1, r1) in uniones:
        assert c0 == c1 == 5 and r1 > r0
        assert len({(filas[r - 2][0], filas[r - 2][5]) for r in range(r0, r1 + 1)}) == 1, "una union cubre filas con otra fuente u otra prueba"
    cubiertas = {r for _, (_, r0), (_, r1) in uniones for r in range(r0, r1 + 1)}
    for r in range(2, len(filas) + 2):
        siguiente = r + 1 < len(filas) + 2 and filas[r - 1][0] == filas[r - 2][0] and filas[r - 1][5] == filas[r - 2][5] != "---"
        assert not siguiente or r in cubiertas, f"la fila {r} repite la fuente de la siguiente y no se unio"
    assert [(r0, r1) for _, (_, r0), (_, r1) in uniones] == [(6, 12)], "las siete filas de los materiales"


def _tabla_de(equipo):
    infos = [(nombre, {"criterio_veredicto": json.dumps(criterios.a_json_ready(juzgar(equipo, cat, res)), ensure_ascii=False)})
             for nombre, cat, _, res in MEDIDAS]
    return ReporteControlSistemaImagenes._crear_tabla_criterios(object.__new__(ReporteControlSistemaImagenes), infos)


@pytest.mark.parametrize("equipo", EQUIPOS)
def test_el_anual_une_la_fuente_de_los_materiales(equipo):
    tabla = pdf_mod._crear_tabla_pdf_anual(_tabla_de(equipo), "criterios_veredictos", equipo)
    tabla.wrap(sum(pdf_mod.ANCHOS_CRITERIOS_VEREDICTOS_PT), 100000)
    unidas = {(r[1], r[3]) for r in tabla._spanRanges.values() if r is not None and (r[0], r[2]) == (5, 5) and r[3] > r[1]}
    assert unidas == {(6, 12)}, unidas


@pytest.mark.parametrize("equipo", EQUIPOS)
def test_la_tabla_de_criterio_de_un_analisis_nuevo_mide_al_menos_25_por_ciento_menos(equipo):
    tabla = pdf_mod._crear_tabla_pdf_anual(_tabla_de(equipo), "criterios_veredictos", equipo)
    _, alto = tabla.wrap(sum(pdf_mod.ANCHOS_CRITERIOS_VEREDICTOS_PT), 100000)
    assert alto <= 0.75 * ALTO_DE_HOY_PT[equipo], f"{equipo}: {alto:.0f} [pt] contra {ALTO_DE_HOY_PT[equipo]:.0f} [pt] de antes"


def test_las_dos_ramas_del_criterio_de_pdf_py_unen_sus_celdas():
    arbol = ast.parse((RAIZ / "models" / "PDF" / "pdf.py").read_text(encoding="utf-8"))
    llamadas = {f.name: sum(1 for n in ast.walk(f) if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "uniones_de_criterio")
                for f in ast.walk(arbol) if isinstance(f, ast.FunctionDef)}
    assert {k: v for k, v in llamadas.items() if v} == {"generar_reporte_pdf_multitabla_mensual": 1, "_crear_tabla_pdf_anual": 1}, llamadas


# 6. EL PDF REAL: LO NUEVO EN BREVE Y LO GUARDADO COMO SE GUARDO

def _copia(tmp):
    for sufijo in ("", "-wal", "-shm"):
        origen = Path(str(BD_REBUILD_23_11) + sufijo)
        if origen.exists():
            shutil.copy2(origen, tmp / (BD_REBUILD_23_11.name + sufijo))
    return str(tmp / BD_REBUILD_23_11.name)


def _archivar_nuevo(ruta, sesion, equipo):
    con = sqlite3.connect(ruta)
    try:
        for _, cat, tipo, res in MEDIDAS:
            juicios = json.dumps(criterios.a_json_ready(juzgar(equipo, cat, res)), ensure_ascii=False, sort_keys=True)
            con.execute("UPDATE pruebas SET criterio_veredicto=? WHERE id_sesion=? AND id_tipo=? AND (activo IS NULL OR activo=1)", (juicios, sesion, tipo))
        con.commit()
    finally:
        con.close()


def _mensual(ruta, sesion, equipo, fecha, mp):
    mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    conection_mod.Conexion._instance = None
    conection_mod.Conexion()
    try:
        FalsoVisor.ultimo = {}
        assert rep_mod.generar_reporte_sistema_imagenes(Padre(ruta), fecha, equipo, "x", ref=sesion, sistema_imagenes=True)
        return FalsoVisor.ultimo["pdf"]
    finally:
        conection_mod.Conexion._instance.con.close()
        conection_mod.Conexion._instance = None


@pytest.fixture(scope="module")
def pdfs(app, tmp_path_factory):
    """El mensual del 01/10/2026 tal como se archivo, y los de un analisis nuevo de cada equipo (su criterio archivado en una COPIA); todo QMessageBox parchado (Trampa 2)."""
    if not BD_REBUILD_23_11.exists():
        pytest.skip(f"falta la BD de referencia {BD_REBUILD_23_11.name}")
    salida = {}
    with pytest.MonkeyPatch.context() as mp:
        for nombre in ("critical", "warning", "information", "question"):
            mp.setattr(QMessageBox, nombre, staticmethod(lambda *a, **k: QMessageBox.Ok))
        mp.setattr(rep_mod, "PdfViewer", FalsoVisor)
        ruta = _copia(tmp_path_factory.mktemp("copia_23_11"))  # una sola copia: la conexion de Qt del informe queda abierta sobre ella
        salida["archivado"] = _mensual(ruta, 48, "Tomógrafo", "01/10/2026", mp)
        for equipo, (sesion, fecha) in SESIONES.items():
            _archivar_nuevo(ruta, sesion, equipo)
            salida[equipo] = _mensual(ruta, sesion, equipo, fecha, mp)
    return salida


def _texto_del_criterio(pdf):
    doc = fitz.open(stream=pdf, filetype="pdf")
    texto = " ".join(p.get_text() for p in doc)
    plano = re.sub(r"\s+", " ", texto)
    assert plano.count(TITULO) == 1
    return doc, plano


def _impresos(equipo):
    """Los juicios que el PDF de la sesion de `equipo` imprime (la del iX tiene cuatro pruebas)."""
    return [j for _, cat, tipo, res in MEDIDAS for j in juzgar(equipo, cat, res) if equipo != "Clinac ix" or tipo in (3, 4, 5, 7)]


@pytest.mark.parametrize("equipo", EQUIPOS)
def test_el_pdf_de_un_analisis_nuevo_imprime_la_fuente_de_los_materiales_una_vez(pdfs, equipo):
    _, plano = _texto_del_criterio(pdfs[equipo])
    fuente = f"{FUENTES[(equipo, 'numeros_ct')]} ({PERFILES[equipo].reglas['numeros_ct'].estado})"
    assert plano.count(fuente) == 1, (equipo, plano.count(fuente))
    for m in MATERIALES:
        assert f"HU de {criterios._norm(m)}" in plano, m
    for j in _impresos(equipo):
        assert _plano(j.criterio) in plano and _plano(texto_fuente(j)) in plano, (j.prueba, j.criterio)


@pytest.mark.parametrize("equipo", EQUIPOS)
def test_en_el_pdf_ningun_texto_del_criterio_lleva_identificadores_internos(pdfs, equipo):
    _, plano = _texto_del_criterio(pdfs[equipo])
    fin = max(plano.rfind(_plano(texto_fuente(j))) + len(_plano(texto_fuente(j))) for j in _impresos(equipo))
    tabla = plano[plano.index(TITULO):fin]
    assert fin > plano.index(TITULO) and not IDENTIFICADORES.search(tabla), tabla


CABECERAS = ("Prueba", "Métrica", "Valor", "Criterio", "Veredicto", "Fuente")


def _palabras_esperadas(filas):
    """Por columna, cuantas veces debe verse cada palabra: la cabecera y cada celda; la fuente de filas seguidas de una prueba, una sola vez."""
    columnas, anterior = [Counter([c]) for c in CABECERAS], None
    for n, j in filas:
        fuente = texto_fuente(j) or "---"
        unida = fuente != "---" and (n, fuente) == anterior
        anterior = (n, fuente)
        for columna, celda in zip(columnas, (n, j.etiqueta, criterios.texto_valor(j) or "---", j.criterio, j.estado, "" if unida else fuente)):
            columna.update(celda.split())
    return columnas


def _verticales(pagina):
    """Las lineas verticales dibujadas en la pagina: {x: (y desde, y hasta)}."""
    lineas = {}
    for dibujo in pagina.get_drawings():
        for operacion, *puntos in dibujo["items"]:
            if operacion == "l" and abs(puntos[0].x - puntos[1].x) < 0.1:
                x, (y0, y1) = round(puntos[0].x, 1), sorted((puntos[0].y, puntos[1].y))
                antes = lineas.get(x, (y0, y1))
                lineas[x] = (min(antes[0], y0), max(antes[1], y1))
    return lineas


def _palabras_por_columna(doc):
    """Las palabras dentro de la rejilla de la tabla de criterio, contadas por columna, en cada pagina que ocupa (bajo su titulo); y esas paginas."""
    paginas = list(doc)
    desde = next(i for i, p in enumerate(paginas) if p.search_for(TITULO))
    titulo = paginas[desde].search_for(TITULO)[0]
    cabecera = next(w for w in paginas[desde].get_text("words") if w[4] == CABECERAS[4] and w[1] > titulo.y1)
    centro = (cabecera[1] + cabecera[3]) / 2
    bordes = sorted(x for x, (y0, y1) in _verticales(paginas[desde]).items() if y0 < centro < y1)
    assert len(bordes) == len(CABECERAS) + 1, f"no se hallaron los bordes de las columnas: {bordes}"
    columnas, ocupadas = [Counter() for _ in CABECERAS], []
    for p in paginas[desde:]:
        lineas = _verticales(p)
        if not all(x in lineas for x in bordes):
            break
        arriba = titulo.y1 if not ocupadas else max(lineas[x][0] for x in bordes)
        abajo = min(lineas[x][1] for x in bordes)
        for x0, y0, x1, y1, palabra, *_ in p.get_text("words"):
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if bordes[0] < cx < bordes[-1] and arriba < cy < abajo:
                columnas[bisect.bisect(bordes, cx) - 1][palabra] += 1
        ocupadas.append(p)
    return columnas, ocupadas


@pytest.mark.parametrize("clave", ["archivado", *EQUIPOS])
def test_la_tabla_con_la_celda_unida_cabe_y_ninguna_palabra_se_parte(pdfs, clave):
    doc, _ = _texto_del_criterio(pdfs[clave])
    filas = _filas_archivadas_48() if clave == "archivado" else [(n, j) for n, cat, tipo, res in MEDIDAS for j in juzgar(clave, cat, res) if clave != "Clinac ix" or tipo in (3, 4, 5, 7)]
    columnas, paginas = _palabras_por_columna(doc)
    for p in paginas:
        assert all(MARCO_X[0] <= w[0] and w[2] <= MARCO_X[1] for w in p.get_text("words") if 245 <= w[1] <= 692), "nada fuera de los margenes del marco"
    faltan = {c: sorted((e - v).elements()) for c, e, v in zip(CABECERAS, _palabras_esperadas(filas), columnas) if e - v}
    assert not faltan, f"{clave}: palabras partidas o perdidas en su columna {faltan}"


@pytest.mark.parametrize("equipo", EQUIPOS)
def test_ninguna_palabra_de_la_tabla_es_mas_ancha_que_su_columna(equipo):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfbase.pdfmetrics import stringWidth
    estilo = getSampleStyleSheet()["Normal"]  # el de los parrafos de cada celda
    anchas = [(c, p) for fila in _tabla_de(equipo).values.tolist() for c, celda in enumerate(fila) for p in html.unescape(str(celda)).split()
              if stringWidth(p, estilo.fontName, estilo.fontSize) + 12 > pdf_mod.ANCHOS_CRITERIOS_VEREDICTOS_PT[c]]
    assert not anchas, anchas


def _filas_archivadas_48():
    """(prueba, juicio) de lo que archivo el 01/10/2026 (sesion 48), leido de una COPIA."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        ruta = _copia(Path(tmp))
        con = sqlite3.connect(ruta)
        try:
            crudo = con.execute("SELECT id_tipo, criterio_veredicto FROM pruebas WHERE id_sesion=48 AND criterio_veredicto IS NOT NULL "
                                "AND (activo IS NULL OR activo=1) ORDER BY id_tipo").fetchall()
        finally:
            con.close()
    nombres = {tipo: n for n, _, tipo, _ in MEDIDAS}
    return [(nombres[t], criterios.Juicio(**d)) for t, c in crudo for d in json.loads(c)]


def test_el_pdf_del_01_10_2026_imprime_su_texto_archivado(pdfs):
    _, plano = _texto_del_criterio(pdfs["archivado"])
    assert plano.count("Propuesta del plan: TG-66 pide constancia mensual; 20 HU ≈ 1 % de dosis en tejido blando y 50 HU en pulmón/hueso (propuesta)") == 1, "lo archivado, una vez"
    for viejo in ("Criterio actual de la app, sin fuente normativa (P8, requiere confirmación del físico) (propuesta)",
                  "no menos de la línea base − 0 lp/cm. Pendiente de métrica",
                  "AAPM TG-66 (ancho del perfil de sensibilidad / espesor, ±1 mm) (norma)"):
        assert viejo in plano, viejo
    for nuevo in ("TG-66, constancia mensual", "Criterio de la app, sin norma", "AAPM TG-66 (espesor de corte"):
        assert nuevo not in plano, nuevo
