"""GI.8g (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, anotada por GI.3): el texto de la linealidad tiene UNA sola definicion, y las pantallas del Catphan no llevan marcas de correcto / incorrecto (DA-18).

CAUSA: la linealidad la decian dos funciones distintas: `tac_mensual.tabla_resultados_linealidad` (el analisis recien hecho: «Ecuacion de la recta...», sin energia ni veredicto) y
`catphan_db.tabla_resultados_linealidad_ct` (lo reabierto: «Pendiente / Intercepto / R²», con la energia y «✓ ACEPTABLE» / «✗ NO ACEPTABLE» y un emoji en el titulo): el mismo resultado se veia
distinto segun se acabara de analizar o se reabriera, y la segunda llevaba las marcas que DA-18 prohibe. El criterio heredado (R² >= 0.99) estaba escrito en el escritor y, aparte, en el rotulo
del informe. El mismo defecto de marcas (✓ ✗ ✅ ⚠) estaba en otros cuatro textos de `catphan_db` y en el aviso de carga de `tac_mensual`.

GARANTIAS, una por bloque:

  1. SE LEE IGUAL -- con el analisis REAL de una serie por equipo, el texto de lo recien analizado y el de lo reabierto de la base (escritor real) son identicos caracter a caracter.
  2. UN SOLO VEREDICTO -- el criterio (R² >= 0.99, inclusive) esta en `R2_MINIMO_LINEALIDAD` y lo usan el escritor, el texto y el rotulo del informe; lo guardado manda (un NULL no se juzga, un
     False guardado se dice aunque el R² lo apruebe, un BLOB de antes de GI.1 se lee por su valor) y un analisis recien hecho se juzga con la regla del escritor.
  3. SIN MARCAS -- ningun texto de pantalla de la familia del Catphan lleva ✓ ✗ ✔ ✖ ✅ ❌ ⚠ (censo por AST de las cadenas que no son docstring ni consola) ni pictogramas en los bloques de resultados.
  4. UNA SOLA DEFINICION -- `tac_mensual` no define ningun texto de resultados: importa el de `catphan_db`; nadie mas escribe el criterio HEREDADO 0.99 (el `tolerancia=0.99` de `perfiles.py` para `linealidad_r2` es otro criterio, el de G.3 por equipo, en estado «propuesta»).

Nunca se conecta a una BD de referencia: se copia a un temporal primero.
"""
import ast
import copy
import re
from pathlib import Path

import pytest
from PyQt5.QtWidgets import QLabel, QTableWidget

from data.ManejoDatos.catphan_TAC import catphan_db as C
from test_gi1_guardado_claves_del_analisis import (  # noqa: F401  (helpers y fixtures de GI.1: una sola definicion de la forma del productor)
    SERIES, _analisis_real, _crear_control, _guardar, _resultado_contraste, app, bd_nueva)
from test_gi2_lectura_es_lo_guardado import _reabrir, bd_copia_real          # noqa: F401
from _informe_imagenes import avisos, generar as _generar_informe, paginas as _paginas_del_informe  # noqa: F401

RAIZ = Path(__file__).resolve().parent.parent
MARCAS = re.compile("[✓✗✔✖✅❌⚠️✘✕☑☒❎⛔🚫❗]")                  # ✓ ✗ ✔ ✖ ✅ ❌ ⚠ y sus equivalentes ✘ ✕ ☑ ☒ ❎ ⛔ 🚫 ❗ (revision de GI.8g)                  # ✓ ✗ ✔ ✖ ✅ ❌ ⚠ (y el selector de variante)
PICTOGRAMAS = re.compile("[\U0001F300-\U0001FAFF]")
# La familia del Catphan en pantalla: los archivos donde se escribe el texto que ve la persona
FAMILIA = ["data/ManejoDatos/catphan_TAC/catphan_db.py", "data/ManejoDatos/catphan_TAC/leer_dicom.py", "data/ManejoDatos/catphan_TAC/slice_matcher.py",
           "data/ManejoDatos/catphan_TAC/ventana_metadatos.py", "ui/paginasControles/PruebasMensuales/tac_mensual.py", "analisisImagenes/Analisis_Catphan_TAC.py",
           "models/PDF/Imagenes/reportes_control_sistema_imagenes.py",
           # revision de GI.8g: las ventanas «Ver tabla» de las tablas de imagenes (Valores CT, Uniformidad, Resolucion Espacial, Linealidad, Espesor, Tamano de Pixel) arman su mensaje de «sin datos» en load.py
           "data/ManejoDatos/load.py"]
# Funciones de CONSOLA: arman una tabla de texto para `print` (el `.exe` no tiene consola) y no se ven en ninguna pantalla ni documento
FUNCIONES_DE_CONSOLA = {("analisisImagenes/Analisis_Catphan_TAC.py", "imprimir_resultados_contraste_bajo"): "tabla impresa por consola"}


# ---------------------------------------------------------------------------
# 1. SE LEE IGUAL
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clave", list(SERIES))
def test_lo_recien_analizado_y_lo_reabierto_dicen_exactamente_lo_mismo(bd_nueva, clave):
    equipo, px, nominal, salidas = _analisis_real(clave)
    recien = C.tabla_resultados_linealidad_ct(copy.deepcopy(salidas["linealidad_ct"]))
    sesion = _crear_control(bd_nueva, equipo)
    assert _guardar(sesion, copy.deepcopy(salidas), equipo=equipo, espesor_corte=nominal, tam_px_teorico=px) == sesion
    reabierto = C.tabla_resultados_linealidad_ct(_reabrir(bd_nueva, "linealidad_ct", sesion))
    assert recien == reabierto, f"\n--- recien analizado ---\n{recien}\n--- reabierto ---\n{reabierto}"
    # y es el texto completo: con la energia y el veredicto, que el texto anterior de lo recien analizado no traia
    assert "Energía [MeV]:" in recien and "no registrada" not in recien
    assert re.search(r"Linealidad: (ACEPTABLE|NO ACEPTABLE)$", recien, re.M)


# ---------------------------------------------------------------------------
# 2. UN SOLO VEREDICTO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("r2, esperado", [(0.99, True), (0.9900001, True), (0.999, True), (1.0, True), (0.9899999, False), (0.98, False), (0.0, False), (-0.5, False)])
def test_el_criterio_es_r2_mayor_o_igual_a_099_inclusive_y_es_el_mismo_del_escritor_y_del_texto(r2, esperado):
    assert C.R2_MINIMO_LINEALIDAD == 0.99
    assert C.linealidad_es_aceptable(r2) is esperado
    escrito = C.mapear_linealidad_ct({"r_squared": r2, "pendiente": 1.0, "intercepto": 0.0})["linealidad_aceptable"]
    assert escrito is esperado
    texto = C.tabla_resultados_linealidad_ct({"r_squared": r2, "pendiente": 1.0, "intercepto": 0.0})          # un analisis recien hecho: no trae la bandera
    assert f"Linealidad: {'ACEPTABLE' if esperado else 'NO ACEPTABLE'}" in texto


@pytest.mark.parametrize("resultados, linea", [
    ({"r_squared": 0.999, "linealidad_aceptable": None}, None),                      # reabierto con NULL: no se juzga (el informe PDF dice N/A)
    ({"r_squared": 0.999, "linealidad_aceptable": False}, "NO ACEPTABLE"),           # lo guardado manda aunque el R² lo apruebe
    ({"r_squared": 0.5, "linealidad_aceptable": True}, "ACEPTABLE"),
    ({"r_squared": 0.999, "linealidad_aceptable": b"\x00"}, "NO ACEPTABLE"),         # un BLOB de antes de GI.1 se lee por su valor (bool(b'\x00') seria True)
    ({"r_squared": 0.5, "linealidad_aceptable": b"\x01"}, "ACEPTABLE"),
    ({"r_squared": None}, None),                                                     # sin un R² numerico no hay veredicto
    ({"r_squared": "No disponible"}, None),
    ({}, None),
])
def test_lo_guardado_manda_y_sin_dato_no_se_inventa_un_veredicto(resultados, linea):
    texto = C.tabla_resultados_linealidad_ct(dict(resultados, pendiente=1.0))
    if linea is None:
        assert "Linealidad:" not in texto
    else:
        assert texto.rstrip().splitlines()[-2].strip() == f"Linealidad: {linea}", texto


def test_el_texto_no_lanza_ni_escribe_none_con_ningun_valor_hostil():
    hostiles = [None, "texto", "No disponible", "", b"\x01", 0, 0.0, -1, float("inf"), True]
    completo = {"pendiente": 1.5, "intercepto": -3.25, "r_squared": 0.99912345, "referencia": 0.5, "escala_contraste": 0.000123456789, "energia_mev": 0.12}
    texto = C.tabla_resultados_linealidad_ct(completo)
    assert "Pendiente: 1.500" in texto and "R²: 0.9991" in texto and "Energía [MeV]: 0.12" in texto
    for hostil in hostiles:
        for clave in completo:
            assert "None" not in C.tabla_resultados_linealidad_ct(dict(completo, **{clave: hostil})), (clave, hostil)
    assert C.tabla_resultados_linealidad_ct({}) == "No hay resultados de linealidad CT disponibles."


# ---------------------------------------------------------------------------
# 3. SIN MARCAS
# ---------------------------------------------------------------------------

def _cadenas(ruta):
    """(linea, funcion, texto) de toda cadena del archivo que no es docstring ni argumento de un `print` ni esta en una funcion de consola."""
    fuente = (RAIZ / ruta).read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    docstrings, impresas = set(), set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and nodo.body and isinstance(nodo.body[0], ast.Expr) \
                and isinstance(getattr(nodo.body[0], "value", None), ast.Constant):
            docstrings.add(id(nodo.body[0].value))
        if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", "") == "print":
            impresas.update(id(sub) for sub in ast.walk(nodo))
    dueno = {}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(nodo):
                dueno[id(sub)] = nodo.name                               # la funcion MAS interna gana (ast.walk va de afuera hacia adentro)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and id(nodo) not in docstrings and id(nodo) not in impresas:
            yield nodo.lineno, dueno.get(id(nodo), "<modulo>"), nodo.value


def test_ninguna_pantalla_del_catphan_lleva_marcas_de_correcto_o_incorrecto_DA18():
    inspeccionadas, con_marcas = 0, []
    for ruta in FAMILIA:
        for linea, funcion, texto in _cadenas(ruta):
            inspeccionadas += 1
            if MARCAS.search(texto) and (ruta, funcion) not in FUNCIONES_DE_CONSOLA:
                con_marcas.append((ruta, linea, funcion, texto[:60]))
    assert inspeccionadas > 600, f"el censo debe inspeccionar la familia entera (solo vio {inspeccionadas} cadenas)"
    assert con_marcas == [], "marcas de correcto / incorrecto en textos de pantalla (DA-18):\n" + "\n".join(map(str, con_marcas))


def test_la_lista_de_funciones_de_consola_no_esta_muerta():
    """Cada excepcion del censo tiene que seguir llevando marcas: si el codigo cambia, la excepcion se retira (no se acumulan permisos que ya no hacen falta)."""
    for (ruta, funcion), motivo in FUNCIONES_DE_CONSOLA.items():
        fuente = (RAIZ / ruta).read_text(encoding="utf-8")
        nodo = next(n for n in ast.walk(ast.parse(fuente)) if isinstance(n, ast.FunctionDef) and n.name == funcion)
        marcas = [c.value for c in ast.walk(nodo) if isinstance(c, ast.Constant) and isinstance(c.value, str) and MARCAS.search(c.value)]
        assert marcas, f"{funcion} ya no lleva marcas: se retira de FUNCIONES_DE_CONSOLA ({motivo})"


def test_los_bloques_de_resultados_de_catphan_db_no_llevan_pictogramas():
    """Los textos de resultados que se ven en la pestana (y los parametros que van encima) son texto llano, igual que los de la linealidad."""
    arbol = ast.parse((RAIZ / "data/ManejoDatos/catphan_TAC/catphan_db.py").read_text(encoding="utf-8"))
    revisadas, pictogramas = 0, []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.FunctionDef) and (nodo.name.startswith("tabla_resultados_") or nodo.name.startswith("crear_widget_")):
            revisadas += 1
            pictogramas += [(nodo.name, c.lineno, c.value[:50]) for c in ast.walk(nodo) if isinstance(c, ast.Constant) and isinstance(c.value, str) and PICTOGRAMAS.search(c.value)]
    assert revisadas >= 9
    assert pictogramas == [], pictogramas


def test_la_tabla_de_contraste_de_la_pantalla_dice_visible_y_circulos_detectados_sin_marcas(app):
    resultado = _resultado_contraste((15, 9, 8, 7), (15, 9, 8, 7))
    widget = C.tabla_resultados_resolucion_contraste(resultado)
    textos = [l.text() for l in widget.findChildren(QLabel)]
    tabla = widget.findChild(QTableWidget)
    celdas = [tabla.item(f, c).text() for f in range(tabla.rowCount()) for c in range(tabla.columnCount()) if tabla.item(f, c)]
    assert any(t.startswith("Círculos detectados: 4/6") for t in textos), textos
    assert celdas.count("Visible") == 4, celdas
    assert not [t for t in textos + celdas if MARCAS.search(t)], (textos, celdas)
    sin = C.tabla_resultados_resolucion_contraste(_resultado_contraste((), ()))
    assert [l.text() for l in sin.findChildren(QLabel)][0] == "No se detectaron círculos de contraste visibles"
    widget.deleteLater()
    sin.deleteLater()


def test_el_texto_de_espesor_y_de_tamano_de_pixel_van_en_texto_llano():
    espesor = C.tabla_resultados_espesor({"espesor_promedio_mm": 1.9, "espesor_teorico_mm": 2.0, "diferencia_mm": 0.1, "espesores_individuales": {"Izquierda": 1.9}})
    assert espesor.splitlines()[0] == "RESULTADOS DE ESPESOR DE CORTE" and "  Espesores individuales:" in espesor.splitlines()
    assert C.tabla_resultados_tamano_pixel({"X": 0.95, "Y": 0.96}).splitlines()[0] == "RESULTADOS DE TAMAÑO DE PIXEL"
    assert C.tabla_resultados_linealidad_ct({"pendiente": 1.0}).splitlines()[0] == "RESULTADOS DE LINEALIDAD CT"


# ---------------------------------------------------------------------------
# 4. UNA SOLA DEFINICION
# ---------------------------------------------------------------------------

def test_tac_mensual_no_define_ningun_texto_de_resultados_y_usa_el_de_catphan_db():
    ruta = "ui/paginasControles/PruebasMensuales/tac_mensual.py"
    arbol = ast.parse((RAIZ / ruta).read_text(encoding="utf-8"))
    assert [n.name for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name.startswith("tabla_resultados_")] == []
    importadas = {a.name for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("catphan_db") for a in n.names}
    siete = {"tabla_resultados_espesor", "tabla_resultados_tamano_pixel", "tabla_resultados_resolucion_contraste", "tabla_resultados_resolucion_espacial",
             "tabla_resultados_ct", "tabla_resultados_linealidad_ct", "tabla_resultados_uniformidad"}
    assert siete <= importadas
    import ui.paginasControles.PruebasMensuales.tac_mensual as tac
    for nombre in siete:
        assert getattr(tac, nombre) is getattr(C, nombre), nombre
    # y la pestana de linealidad lo llama por su nombre, no por un metodo propio
    fuente = (RAIZ / ruta).read_text(encoding="utf-8")
    assert "texto = tabla_resultados_linealidad_ct(linealidad)" in fuente and "self.tabla_resultados_linealidad(" not in fuente


def _numeros_099(ruta):
    arbol = ast.parse((RAIZ / ruta).read_text(encoding="utf-8"))
    return [n.lineno for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, float) and n.value == 0.99]


def test_el_099_de_la_linealidad_se_escribe_en_un_solo_sitio():
    assert len(_numeros_099("data/ManejoDatos/catphan_TAC/catphan_db.py")) == 1, "solo la definicion de R2_MINIMO_LINEALIDAD"
    assert _numeros_099("models/PDF/Imagenes/reportes_control_sistema_imagenes.py") == []
    fuente = (RAIZ / "models/PDF/Imagenes/reportes_control_sistema_imagenes.py").read_text(encoding="utf-8")
    assert "R²≥0.99" not in fuente and "R2_MINIMO_LINEALIDAD" in fuente


def test_el_informe_pdf_real_sigue_rotulando_la_linealidad_con_su_criterio(bd_copia_real, monkeypatch, avisos):
    ok, recibido = _generar_informe(bd_copia_real, monkeypatch, 42, "Tomógrafo", "07/2026")
    assert ok and not avisos, avisos
    plano = " ".join("\n".join(_paginas_del_informe(recibido["pdf"])).split())
    assert "Linealidad aceptable (R²≥0.99)" in plano


def test_el_texto_completo_de_la_linealidad_tiene_este_formato_exacto():
    """Revision de GI.8g (P3): el formato de CADA linea, incluidas Intercepto, Referencia y Escala de contraste, que ninguna prueba fijaba (la igualdad recien analizado / reabierto no las
    protege: las dos rutas usan la misma funcion)."""
    completo = {"pendiente": 1.5, "intercepto": -3.25, "r_squared": 0.99912345, "referencia": 0.5, "escala_contraste": 0.000123456789, "energia_mev": 0.12}
    esperado = "\n".join(["RESULTADOS DE LINEALIDAD CT", "-" * 50, "  Pendiente: 1.500", "  Intercepto: -3.250", "  R²: 0.9991", "  Referencia: 0.500000",
                          "  Escala de contraste: 0.000123", "  Energía [MeV]: 0.12", "  Linealidad: ACEPTABLE", "-" * 50])
    assert C.tabla_resultados_linealidad_ct(completo) == esperado
    sin_energia = dict(completo)
    del sin_energia["energia_mev"]
    assert "  Energía [MeV]: no registrada" in C.tabla_resultados_linealidad_ct(sin_energia).splitlines()
