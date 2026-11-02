"""CD.8 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, DA-92, DA-93, DC12, DC16, DC17, DA-81, DA-83): EL PDF MENSUAL DICE LA BASE Y LA CURVA.

CAUSA: la seccion de F.1 imprimia los numeros de la capa reportada sin decir con que curva se midio la dosis, llevaba el cuadro «Parametros fijos del analisis guardado» (mas de 1500 caracteres de prosa,
el pie de la ventana, sin un numero medido) que el fisico pidio quitar (31-10, «SI a todo»: sin dejar ninguna linea), no imprimia los desfases de centro, la meseta, las penumbras ni los largos de cada lado
hasta el piso que la ventana muestra (31-10: «Tanto en esa tabla como en el pdf») y su grafico salia siempre en netOD («se debe ajustar a la escala» de lo que se guarde).

LO QUE SE GARANTIZA, contra verdades que NO salen de la seccion (lo GUARDADO leido con `svc.leer`, la tabla de la ventana `filas_de_la_capa_reportada` sobre el analisis vuelto a medir por el
servicio, la curva de la placa sintetica de CD.6/CD.7 y el texto EXTRAIDO del PDF real del `reporte_mensual`):
  EL CUADRO SALE: ni la clave en la seccion ni en las dos listas de `pdf.py`, ni su titulo ni su texto en el PDF, y ninguna linea en su lugar.
  LA TABLA DE VALORES: lo guardado (FWHM y desfase por lado) sale UNA vez, de lo guardado, con sus rotulos de F.1; las demas filas de la ventana (los dos desfases de centro, la meseta, las cuatro
    penumbras y los cuatro largos) del analisis reconstruido, en su orden; «Base de la medida», «Piso», «Referencia» y las notas se quedan; sin el gris; sin reconstruir, solo lo guardado y la frase que
    dice TODO lo que no sale.
  LA DOSIS: un registro sin dosis no gana ninguna linea ni tabla; uno con dosis gana la tabla en dosis con la base, la linea de la curva de la COPIA (lote, fecha, calibracion, modelo y rango util de la
    capa; nunca la curva vigente), lo guardado en dosis y las filas de la ventana en dosis; el grafico sale en dosis con el eje fijo de la copia; una copia danada, una dosis que no coincide o un analisis
    de otra version lo dicen y no tumban el PDF.
  SIN VEREDICTO, sin comparar capas, sin simbolos y con las unidades entre corchetes; ningun rotulo dice «umbra».
  LA PAGINACION: cada titulo en la pagina de su primera fila, la figura de 384 x 400 pt en la de su titulo; la seccion ocupa las paginas medidas.
Lo que NO se prueba aqui y si en la compuerta del anexo (`cd8_diferencial.py`): un PDF sin dosis es palabra por palabra el de F.1 salvo lo nombrado.

Rojo contra el commit de CD.6b: la seccion trae `placa_mensual_parametros`, no tiene `ROTULOS_DE_LA_VENTANA`, `reconstruir_en_dosis` ni `texto_de_la_curva`, no imprime las filas nuevas ni la dosis y su
figura mide 384 x 340 pt. La produccion se importa POR PRUEBA (`_f1_ayudas`). Lo caro (la placa de 600 ppp a 16 bits y su curva, de la prueba de CD.7, y los PDF) son fixtures de modulo.

RONDA 1 DE LA REVISION (CD8-REV1-PROD-01 a PROD-05 y CD8-RP-1 a RP-4; cada hallazgo se reprodujo con una mutacion sobre un espejo que sobrevivia a los 48 casos de entonces): el fixture gana el registro de la
capa AZUL con dosis y una curva de rango util DISTINTO por capa (antes todos los registros con dosis eran de la verde y la curva de la escena tiene 600 cGy en las tres) y el registro cuya capa quedo «no
medible en dosis» (P30), y las pruebas ganan: el rango util de CADA capa reportada; el camino completo de un registro P30 por `tablas_de_la_seccion` y por el PDF; la lista COMPLETA de las filas de la tabla en dosis;
la nota de que los perfiles van en netOD solo si se imprimen; la identificacion de la copia sin literales de Python; el error_log de lo que no coincide con lo mismo que dice la nota del PDF; y el tripwire de las
bases tambien para «en dosis».
"""
import ast
import copy
import html
import json
import re
from pathlib import Path

import fitz
import pytest
from reportlab.platypus import Paragraph

import _placa_mensual_sintetica as gen
from _f1_ayudas import (CAPA_EN_UNA_FRASE, NO_MEDIBLE, SIMBOLOS_DA18, TITULO_DE_LA_PELICULA, TITULO_DE_LA_SECCION, USUARIO, app, cerrar_mundo, dibujo, imagenes_de, mundo_nuevo,  # noqa: F401
                        normal, paginas_de, parametros, plantilla, pm, seccion, svc, texto_de)
from test_cd7_ventana_mensual_en_dosis import calibracion, con_capa, escena  # noqa: F401  (la placa de la verdad en dosis y su curva, de CD.7)

RAIZ = Path(__file__).resolve().parent.parent
SECCION_PY = RAIZ / "models" / "PDF" / "Mensuales" / "seccion_placa_mensual.py"
PDF_PY = RAIZ / "models" / "PDF" / "pdf.py"
DIBUJO_PY = RAIZ / "analisisImagenes" / "dibujo_placa_mensual.py"          # H-CD9-3/4/5 (los arreglos que pidio la revision de CD.9): una sola definicion de cada texto
# Escrito AQUI a mano (el ancla externa): lo que el fisico pidio quitar y como se llamaba.
TITULO_DEL_CUADRO = "Parámetros fijos del análisis guardado"
PRINCIPIO_DEL_CUADRO = "Parámetros fijos del método"
CLAVE_DEL_CUADRO = "placa_mensual_parametros"
CLAVE_DE_LA_DOSIS = "placa_mensual_dosis"
# Lo guardado (rotulos de F.1) y su fila en la tabla de la ventana: escritos a mano.
GUARDADAS = {"fwhm_crossplane_mm": ("FWHM crossplane [mm]", "FWHM crossplane [mm]"), "fwhm_inplane_mm": ("FWHM inplane [mm]", "FWHM inplane [mm]"),
             "desfase_izquierdo_mm": ("Desfase del lado izquierdo [mm]", "Lado izquierdo (radiación − luz) [mm]"),
             "desfase_derecho_mm": ("Desfase del lado derecho [mm]", "Lado derecho (radiación − luz) [mm]"),
             "desfase_superior_mm": ("Desfase del lado superior [mm]", "Lado superior (radiación − luz) [mm]"),
             "desfase_inferior_mm": ("Desfase del lado inferior [mm]", "Lado inferior (radiación − luz) [mm]")}
LOTE, FECHA_IRR, ID_CAL = "L-31", "2026-10-30", 7
LINEA_DE_UNA_CAPA = "la copia guardada con el registro: lote «L-31», irradiada el 2026-10-30 (calibración 7), modelo de Devic; la capa {adjetivo} es útil de 0 a {rango:g} [cGy]"
LINEA_DE_LA_CURVA = LINEA_DE_UNA_CAPA.replace("{adjetivo}", "verde")          # la de la capa verde, que es la de casi todos los registros del fixture
RANGO_POR_CAPA = {"R": 500.0, "G": 450.0, "B": 550.0}          # rango util DISTINTO por capa: desde CD.5b la curva de la escena tiene 600 cGy en las tres y la linea de una capa no se distinguia de la de otra
ADJETIVO_POR_CAPA = {"R": "roja", "G": "verde", "B": "azul"}
LO_QUE_NO_SALE = ("desfases de centro", "meseta", "penumbras", "largo de cada lado hasta el piso", "medidas estadísticas", "perfiles")          # lo que un analisis que no se reconstruye no imprime (H-CD8-12)
ANCHO_FIGURA, ALTO_FIGURA = 384, 400
VEREDICTOS = ("cumple", "no cumple", "aprobad", "rechazad", "fuera de tolerancia", "dentro de tolerancia", "veredicto")
NOMBRES = ("netod", "pixel", "no_medible", "otra_version", "dosis", "dosis_otra_curva", "copia_danada", "dosis_no_coincide", "dosis_otra_version", "dosis_azul", "dosis_no_medible")


def _celda(c):
    return html.unescape(c.text) if isinstance(c, Paragraph) else ("" if c is None else str(c))


def _filas(df):
    return [[_celda(c) for c in fila] for fila in [list(df.columns)] + df.values.tolist()]


def _tablas(m, nombre):
    return seccion().tablas_de_la_seccion(svc().leer(m.refs[nombre]))


def _la_seccion(pdf):
    """El texto de la seccion, normalizado: desde su titulo hasta «Dosimetría» (la tabla que le sigue)."""
    lineas = [normal(l) for l in texto_de(pdf).splitlines() if normal(l)]
    inicio = next(i for i, l in enumerate(lineas) if l.startswith(TITULO_DE_LA_SECCION))
    fin = next((i for i in range(inicio, len(lineas)) if lineas[i] == "Dosimetría"), len(lineas))
    return " ".join(lineas[inicio:fin])


def _ventana(resultado, capa="G"):
    """La tabla de la pestana 1 de la ventana (CD.7) del analisis `resultado`: la verdad de las filas nuevas."""
    return [list(f) for f in dibujo().filas_de_la_capa_reportada(resultado, capa)]


def _nuevas(resultado, capa="G"):
    fuera = {"Capa reportada", "Estado"} | {v[1] for v in GUARDADAS.values()}
    return [f for f in _ventana(resultado, capa) if f[0] not in fuera]


def _efectiva(curva):
    return pm().CurvaEfectiva(curva, ID_CAL, LOTE, FECHA_IRR)


def _sql_json(m, ref, cambio):
    fila = m.consulta("SELECT id, curva FROM analisis_placa_mensual WHERE ref = ? AND activo = 1", (ref,))[0]
    copia = json.loads(fila[1])
    cambio(copia)
    m.sql("UPDATE analisis_placa_mensual SET curva = ? WHERE id = ?", (json.dumps(copia, sort_keys=True), fila[0]))


def _curva_de_rangos_distintos(curva):
    """`curva` con el rango util de cada capa distinto (`RANGO_POR_CAPA`): solo cambia lo que se imprime (el tope en netOD no cambia, asi que lo que se mide es lo mismo)."""
    for capa, rango in RANGO_POR_CAPA.items():
        curva = con_capa(curva, capa, rango_cgy=rango)
    return curva


def _dejar_no_medible_en_dosis(m, ref, curva):
    """CD8-REV1-PROD-02 / RP-1 / RP-2 (P30 de la curva, el segundo caso de CD6b-D3): deja el registro `ref` (guardado con dosis) como lo dejaria un guardado cuya capa reportada, al medirse en dosis, pasa el rango
    util de la curva: la COPIA guardada con el tope del rango util de la verde por debajo de su meseta y, en las columnas de la dosis, EXACTAMENTE lo que el motor mide con esa copia (`estado_dosis` «no medible en
    dosis: <motivo>» y los seis numeros vacios: NULL y no cero), de modo que reabrirlo da lo mismo (`diferencias_en_dosis` vacia). Se hace con sqlite3, como los demas registros estropeados, antes de abrir QtSql."""
    registro = svc().leer(ref)
    copia = dict(registro["curva"], curva=con_capa(curva, "G", netod_maxima=0.05, rango_cgy=60.0).como_dict())
    medido = svc().recalcular_en_dosis(dict(registro, curva=copia))
    copia["bases"] = {c: {"base": cm.base, "motivo": cm.motivo_de_la_base} for c, cm in medido.capas.items()}
    valores = pm().valores_medidos_en_dosis(medido, registro["capa"])
    assert valores["estado_dosis"].startswith("no medible en dosis: ") and all(v is None for k, v in valores.items() if k != "estado_dosis"), valores
    m.sql("UPDATE analisis_placa_mensual SET curva = ?, " + ", ".join(f"{n} = ?" for n in valores) + " WHERE id = ?", (json.dumps(copia, sort_keys=True), *valores.values(), registro["id"]))


@pytest.fixture(scope="module")
def mundo(app, plantilla, tmp_path_factory, escena):
    """Los registros de las pruebas, sembrados TODOS con el escritor real (y sqlite3 para estropear lo que se estropea) ANTES de abrir QtSql (DP-147); los PDF se generan al pedirlos."""
    m, mp, previo = mundo_nuevo(plantilla, tmp_path_factory)
    mp.setenv("RADQA_ERROR_LOG", str(tmp_path_factory.mktemp("cd8_errores") / "error_log.txt"))         # lo que la seccion registra (una copia danada...) no va al error_log de la app
    placa = gen.generar("png")
    clics = [tuple(float(x) for x in placa.verdad.marcas_px[k]) for k in ("UL", "UR", "DR", "DL", "C")]
    for nombre in ("netod", "otra_version"):
        m.control(nombre)
        m.guardar(nombre, placa.datos, clics, "G", parametros("netOD"))
    m.control("pixel")
    m.guardar("pixel", placa.datos, clics, "G", parametros("pixel"))
    m.control("no_medible")
    with pytest.MonkeyPatch.context() as regla:          # un registro de antes del 20-10 (D.1b): la capa roja, recortada en netOD, se guardaba igual
        regla.setattr(svc(), "motivo_para_no_guardar", lambda resultado, capa: None)
        m.guardar("no_medible", placa.datos, clics, "R", parametros("netOD"))
    for nombre in ("dosis", "dosis_otra_curva", "copia_danada", "dosis_no_coincide", "dosis_otra_version"):
        m.control(nombre)
        svc().guardar(m.refs[nombre], USUARIO, escena.placa.datos, "placa_dosis.tif", escena.clics, copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA), "G", "virgen",
                      referencia_virgen=escena.ref, curva=_efectiva(escena.otra if nombre == "dosis_otra_curva" else escena.curva))
    m.control("dosis_azul")          # CD8-REV1-PROD-01: con dosis y la capa reportada AZUL (todos los demas son de la verde), con una curva de rango util distinto por capa
    svc().guardar(m.refs["dosis_azul"], USUARIO, escena.placa.datos, "placa_dosis.tif", escena.clics, copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA), "B", "virgen",
                  referencia_virgen=escena.ref, curva=_efectiva(_curva_de_rangos_distintos(escena.curva)))
    m.control("dosis_no_medible")          # CD8-REV1-PROD-02 / RP-1 / RP-2: con dosis y la capa reportada «no medible en dosis: <motivo>» (P30)
    svc().guardar(m.refs["dosis_no_medible"], USUARIO, escena.placa.datos, "placa_dosis.tif", escena.clics, copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA), "G", "virgen",
                  referencia_virgen=escena.ref, curva=_efectiva(escena.curva))
    _dejar_no_medible_en_dosis(m, m.refs["dosis_no_medible"], escena.curva)
    for nombre in ("otra_version", "dosis_otra_version"):
        m.sql("UPDATE analisis_placa_mensual SET version = 'PM-0' WHERE ref = ?", (m.refs[nombre],))
    _sql_json(m, m.refs["copia_danada"], lambda c: c.__setitem__("curva", {"version": c["curva"]["version"]}))
    m.sql("UPDATE analisis_placa_mensual SET fwhm_crossplane_dosis_mm = fwhm_crossplane_dosis_mm + 0.5 WHERE ref = ?", (m.refs["dosis_no_coincide"],))
    m.escena = escena
    yield m
    cerrar_mundo(mp, previo)


# ===================================================================================================== el cuadro de parametros sale

class TestSinElCuadroDeParametros:
    def test_la_seccion_no_tiene_la_clave_y_tiene_la_de_la_dosis_tras_la_de_valores(self):
        claves = tuple(seccion().CLAVES)
        assert CLAVE_DEL_CUADRO not in claves and claves[:2] == ("placa_mensual_valores", CLAVE_DE_LA_DOSIS)
        assert not hasattr(seccion(), "TITULO_DE_LOS_PARAMETROS") and not hasattr(seccion(), "FRASE_NO_SE_PUDO_EL_PIE") and not hasattr(seccion(), "_tabla_de_los_parametros")

    def test_las_dos_listas_de_pdf_py_no_la_nombran_y_ponen_la_de_la_dosis_tras_la_de_valores(self):
        arbol = ast.parse(PDF_PY.read_text(encoding="utf-8"))
        listas = [[e.value for e in n.elts if isinstance(e, ast.Constant)] for n in ast.walk(arbol) if isinstance(n, ast.List)]
        con_valores = [l for l in listas if "placa_mensual_valores" in l]
        assert len(con_valores) == 2, "el orden de las tablas y la lista de estilos con SPAN"
        for lista in con_valores:
            assert CLAVE_DEL_CUADRO not in lista
            assert lista[lista.index("placa_mensual_valores") + 1] == CLAVE_DE_LA_DOSIS
        assert CLAVE_DEL_CUADRO not in PDF_PY.read_text(encoding="utf-8")

    @pytest.mark.parametrize("nombre", ["netod", "no_medible", "dosis", "otra_version"])
    def test_el_pdf_no_lo_trae_ni_deja_una_linea_en_su_lugar(self, mundo, nombre):
        assert CLAVE_DEL_CUADRO not in _tablas(mundo, nombre)
        texto = normal(texto_de(mundo.pdf(nombre)))
        assert TITULO_DEL_CUADRO not in texto and PRINCIPIO_DEL_CUADRO not in texto
        assert "parámetros fijos" not in texto.lower(), "ninguna linea en su lugar (ni la frase de lo que no se imprime los nombra)"


# ===================================================================================================== la tabla de valores

class TestLaTablaDeValores:
    def test_lo_guardado_sale_una_vez_de_lo_guardado_con_su_rotulo_de_f1(self, mundo):
        registro = svc().leer(mundo.refs["netod"])
        filas = _filas(_tablas(mundo, "netod")["placa_mensual_valores"])
        rotulos = [f[0] for f in filas]
        for nombre, (de_f1, de_la_ventana) in GUARDADAS.items():
            assert rotulos.count(de_f1) == 1, f"{de_f1} una sola vez"
            assert dict((f[0], f[1]) for f in filas if len(f) == 2)[de_f1] == dibujo().numero(registro[nombre], 3, nombre.startswith("desfase"))
            if de_la_ventana != de_f1:
                assert de_la_ventana not in rotulos, f"{de_la_ventana} repetiria {de_f1}"

    def test_las_filas_nuevas_son_las_de_la_ventana_del_analisis_reconstruido_en_su_orden(self, mundo):
        registro = svc().leer(mundo.refs["netod"])
        nuevas = _nuevas(svc().recalcular(registro))
        assert len(nuevas) == 11 and [f[0] for f in nuevas][:3] == ["Radiación − cruce de diagonales (x; y) [mm]", "Radiación − retículo (x; y) [mm]",
                                                                   "Densidad óptica neta media de la meseta [1]"]
        filas = _filas(_tablas(mundo, "netod")["placa_mensual_valores"])
        i = filas.index(nuevas[0])
        assert filas[i:i + len(nuevas)] == nuevas, "las mismas filas, con los mismos numeros y en el orden de la ventana"
        assert [f[0] for f in filas[i - 1:i]] == ["Desfase del lado inferior [mm]"] and filas[i + len(nuevas)][0] == "Piso"

    def test_cada_rotulo_de_la_ventana_de_lo_guardado_esta_en_la_ventana_con_lo_guardado(self, mundo):
        """El tripwire de `ROTULOS_DE_LA_VENTANA`: si la ventana cambia un rotulo, la medida se imprimiria dos veces; aqui cae."""
        registro = svc().leer(mundo.refs["netod"])
        ventana = dict((f[0], f[1]) for f in _ventana(svc().recalcular(registro)))
        assert seccion().ROTULOS_DE_LA_VENTANA == {k: v[1] for k, v in GUARDADAS.items()}
        for nombre, rotulo in seccion().ROTULOS_DE_LA_VENTANA.items():
            assert ventana[rotulo] == dibujo().numero(registro[nombre], 3, nombre.startswith("desfase")), rotulo

    @pytest.mark.parametrize("nombre", ["netod", "dosis"])
    def test_el_pdf_trae_cada_fila_nueva_con_su_valor(self, mundo, nombre):
        texto = _la_seccion(mundo.pdf(nombre))
        for rotulo, valor in _nuevas(svc().recalcular(svc().leer(mundo.refs[nombre]))):
            assert normal(rotulo) in texto and normal(valor) in texto, (rotulo, valor)
        assert "Largo bajo el 20 %, lado superior [mm]" in texto and "Penumbra lado inferior, del 80 al 20 % [mm]" in texto

    def test_conserva_la_base_el_piso_la_referencia_y_la_capa(self, mundo):
        filas = _filas(_tablas(mundo, "netod")["placa_mensual_valores"])
        assert filas[0][0] == f"{TITULO_DE_LA_SECCION}, capa verde" and filas[1] == ["Campo", "Valor"]
        assert filas[2] == ["Capa reportada", "capa verde"] and filas[3] == ["Base de la medida", pm().BASE_DENSIDAD_OPTICA]
        assert [f[0] for f in filas[-2:]] == ["Piso", "Referencia"]

    def test_en_valor_de_pixel_la_meseta_en_niveles(self, mundo):
        filas = _filas(_tablas(mundo, "pixel")["placa_mensual_valores"])
        assert ["Base de la medida", pm().BASE_VALOR_DE_PIXEL] in filas and any(f[0] == "Meseta media [nivel]" for f in filas)

    def test_sin_el_gris_ni_otra_capa(self, mundo):
        texto = _la_seccion(mundo.pdf("netod"))
        assert "gris" not in texto.lower(), "ni una fila ni un titulo del gris (DC17)"
        assert "capa roja" not in texto and "capa azul" not in texto

    def test_una_capa_no_medible_trae_su_estado_y_ninguna_fila_nueva(self, mundo):
        registro = svc().leer(mundo.refs["no_medible"])
        assert registro["estado"] != "ok"
        filas = _filas(_tablas(mundo, "no_medible")["placa_mensual_valores"])
        assert ["Estado", registro["estado"]] in filas and [f[0] for f in filas].count("Estado") == 1
        assert not any(f[0].startswith(("Radiación −", "Penumbra", "Largo", "Densidad óptica neta media")) for f in filas)
        assert all(f[1] == NO_MEDIBLE for f in filas if f[0] in {v[0] for v in GUARDADAS.values()})

    def test_sin_reconstruir_solo_lo_guardado_y_la_frase_dice_todo_lo_que_no_sale(self, mundo):
        filas = _filas(_tablas(mundo, "otra_version")["placa_mensual_valores"])
        assert not any(f[0].startswith(("Radiación −", "Penumbra", "Largo", "Densidad óptica neta media")) for f in filas)
        notas = [f[1] for f in filas if f[0] == "Nota"]
        assert notas == [seccion().FRASE_OTRA_VERSION.format(guardada="PM-0", hoy=pm().VERSION_ALGORITMO)]
        for parte in LO_QUE_NO_SALE:
            assert parte in notas[0], parte
        assert "parámetros" not in notas[0]

    def test_el_error_log_de_lo_que_no_coincide_nombra_lo_mismo_que_la_nota_del_pdf(self, mundo, monkeypatch):
        """CD8-REV1-PROD-05 (ronda 1): al volver a medir y no dar lo guardado, el detalle va a `error_log.txt` con lo que el PDF NO imprime. Decia «sin medidas estadisticas, perfiles ni parametros» (el texto de antes de
        CD.8: los parametros ya no se imprimen nunca y faltaban las filas nuevas) mientras la nota del PDF dice todo lo que no sale: las dos dicen lo mismo."""
        contextos = []
        monkeypatch.setattr(seccion(), "registrar_error", lambda contexto, *a, **k: contextos.append(contexto))
        registro = svc().leer(mundo.refs["netod"])
        resultado, frase = seccion().reconstruir(dict(registro, fwhm_crossplane_mm=registro["fwhm_crossplane_mm"] + 0.5))
        assert resultado is None and frase == seccion().FRASE_NO_COINCIDE
        assert len(contextos) == 1, contextos
        for parte in LO_QUE_NO_SALE:
            assert parte in contextos[0], (parte, contextos[0])
        assert "parámetros" not in contextos[0]


# ===================================================================================================== la dosis

class TestLaDosis:
    @pytest.mark.parametrize("nombre", ["netod", "pixel", "no_medible", "otra_version"])
    def test_un_registro_sin_dosis_no_gana_ninguna_linea_ni_tabla(self, mundo, nombre):
        tablas = _tablas(mundo, nombre)
        assert CLAVE_DE_LA_DOSIS not in tablas
        texto = _la_seccion(mundo.pdf(nombre))
        assert "en dosis" not in texto and "Curva de dosis" not in texto and "cGy" not in texto
        if "placa_mensual_perfiles" in tablas:
            assert _filas(tablas["placa_mensual_perfiles"])[0][0] == f"Perfiles de la {CAPA_EN_UNA_FRASE[svc().leer(mundo.refs[nombre])['capa']]}"

    def test_la_tabla_en_dosis_trae_la_base_la_linea_de_la_copia_y_lo_guardado_en_dosis(self, mundo):
        registro = svc().leer(mundo.refs["dosis"])
        assert registro["estado_dosis"] == "ok"
        filas = _filas(_tablas(mundo, "dosis")[CLAVE_DE_LA_DOSIS])
        assert filas[0][0] == f"{TITULO_DE_LA_SECCION}, capa verde, en dosis" and filas[1] == ["Campo", "Valor"]
        assert filas[2] == ["Base de la medida", pm().BASE_DOSIS]
        assert filas[3] == ["Curva de dosis", LINEA_DE_LA_CURVA.format(rango=mundo.escena.curva.rango("G"))]
        valores = dict((f[0], f[1]) for f in filas[1:] if len(f) == 2)
        for nombre, (de_f1, _v) in GUARDADAS.items():
            assert valores[de_f1] == dibujo().numero(registro[nombre.replace("_mm", "_dosis_mm")], 3, nombre.startswith("desfase"))
        assert abs(registro["fwhm_crossplane_dosis_mm"] - 100.0) < 0.05 and abs(registro["fwhm_inplane_dosis_mm"] - 99.0) < 0.05, "la verdad de la placa"
        assert "Estado" not in valores and not any(f[0] == "Nota" for f in filas)

    def test_la_tabla_en_dosis_tiene_exactamente_las_filas_de_su_diseno_y_ninguna_mas(self, mundo):
        """CD8-RP-3 (ronda 1; CD8-D3): en un registro sano la tabla en dosis es la base, la linea de la curva, lo guardado en dosis con los rotulos de F.1 y las filas nuevas de la ventana en dosis: SIN «Piso» ni
        «Referencia» (ya estan en la de netOD), ni «Capa reportada», ni «Estado», ni notas. La lista COMPLETA y en su orden (las demas pruebas miran un tramo y los valores por rotulo)."""
        registro = svc().leer(mundo.refs["dosis"])
        guardadas = ["FWHM crossplane [mm]", "FWHM inplane [mm]", "Desfase de cada lado", "Desfase del lado izquierdo [mm]", "Desfase del lado derecho [mm]", "Desfase del lado superior [mm]",
                     "Desfase del lado inferior [mm]"]
        esperadas = ["Campo", "Base de la medida", "Curva de dosis"] + guardadas + [f[0] for f in _nuevas(svc().recalcular_en_dosis(registro))]
        assert [f[0] for f in _filas(_tablas(mundo, "dosis")[CLAVE_DE_LA_DOSIS])[1:]] == esperadas

    def test_las_filas_en_dosis_son_las_de_la_ventana_en_dosis(self, mundo):
        registro = svc().leer(mundo.refs["dosis"])
        nuevas = _nuevas(svc().recalcular_en_dosis(registro))
        assert ["Dosis media de la meseta [cGy]", "300.0"] in nuevas and any(f[0].startswith("U de la dosis de la meseta") for f in nuevas)
        filas = _filas(_tablas(mundo, "dosis")[CLAVE_DE_LA_DOSIS])
        i = filas.index(nuevas[0])
        assert filas[i:i + len(nuevas)] == nuevas

    def test_la_linea_y_las_filas_son_de_la_copia_y_nunca_de_la_curva_vigente(self, mundo, monkeypatch):
        """DA-81: el registro guardo la dosis con OTRA curva (las dosis x 1.25): la linea y la dosis son las de esa copia aunque la vigente sea la de siempre; la seccion no lee las calibraciones."""
        import importlib
        leidas = []
        monkeypatch.setattr(importlib.import_module("services.curva_dosis"), "vigentes_validas", lambda *a, **k: leidas.append(1) or [calibracion(mundo.escena.curva)])
        registro = svc().leer(mundo.refs["dosis_otra_curva"])
        filas = _filas(seccion().tablas_de_la_seccion(registro)[CLAVE_DE_LA_DOSIS])
        assert filas[3][1] == LINEA_DE_LA_CURVA.format(rango=mundo.escena.otra.rango("G")) and mundo.escena.otra.rango("G") != mundo.escena.curva.rango("G")
        assert ["Dosis media de la meseta [cGy]", "375.0"] in filas, "300 cGy con las dosis de la otra curva"
        assert leidas == []

    def test_el_grafico_sale_en_dosis_con_el_eje_fijo_de_la_copia(self, mundo, monkeypatch):
        sec = seccion()
        pedidas = []
        real = sec.componer_figura
        monkeypatch.setattr(sec, "componer_figura", lambda figura, resultado, capa: (pedidas.append(resultado), real(figura, resultado, capa))[1])
        registro = svc().leer(mundo.refs["dosis_otra_curva"])
        tablas = sec.tablas_de_la_seccion(registro)
        assert len(pedidas) == 1 and pedidas[0].base == pm().BASE_DOSIS
        assert _filas(tablas["placa_mensual_perfiles"])[0][0] == "Perfiles de la capa verde, en dosis"
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        figura = Figure(figsize=(ANCHO_FIGURA / 72.0, ALTO_FIGURA / 72.0), layout="constrained")
        FigureCanvasAgg(figura)
        sec.componer_figura(figura, pedidas[0], "G")
        tope = dibujo().eje_de_la_dosis(mundo.escena.otra)
        assert tope != dibujo().eje_de_la_dosis(mundo.escena.curva)
        for eje in [a for a in figura.axes if a.get_title()]:
            assert eje.get_ylabel() == "dosis [cGy]" and eje.get_ylim() == (0.0, tope), (eje.get_ylabel(), eje.get_ylim())

    @pytest.mark.parametrize("nombre", ["netod", "otra_version"])
    def test_sin_dosis_el_grafico_sale_en_netod(self, mundo, monkeypatch, nombre):
        sec = seccion()
        pedidas = []
        real = sec.componer_figura
        monkeypatch.setattr(sec, "componer_figura", lambda figura, resultado, capa: (pedidas.append(resultado.base), real(figura, resultado, capa))[1])
        sec.tablas_de_la_seccion(svc().leer(mundo.refs[nombre]))
        assert pedidas == ([pm().BASE_DENSIDAD_OPTICA] if nombre == "netod" else [])

    def test_una_copia_danada_lo_dice_imprime_lo_guardado_y_dibuja_en_netod(self, mundo, monkeypatch):
        errores = []
        monkeypatch.setattr(seccion(), "registrar_error", lambda contexto, *a, **k: errores.append(contexto))
        registro = svc().leer(mundo.refs["copia_danada"])
        tablas = seccion().tablas_de_la_seccion(registro)
        filas = _filas(tablas[CLAVE_DE_LA_DOSIS])
        assert filas[3][0] == "Curva de dosis" and "no se puede leer" in filas[3][1] and "«L-31»" in filas[3][1]
        notas = [f[1] for f in filas if f[0] == "Nota"]
        assert notas == [seccion().FRASE_DOSIS_NO_SE_PUDO, seccion().FRASE_PERFILES_EN_NETOD]
        assert dict((f[0], f[1]) for f in filas[1:])["FWHM crossplane [mm]"] == dibujo().numero(registro["fwhm_crossplane_dosis_mm"], 3), "lo guardado en dosis sale igual"
        assert _filas(tablas["placa_mensual_perfiles"])[0][0] == "Perfiles de la capa verde"
        assert len(errores) == 1 and "dosis" in errores[0]
        assert normal(seccion().FRASE_DOSIS_NO_SE_PUDO) in _la_seccion(mundo.pdf("copia_danada"))

    def test_lo_guardado_en_dosis_que_no_coincide_lo_dice_con_el_detalle_y_dibuja_en_netod(self, mundo, monkeypatch):
        detalles = []
        monkeypatch.setattr(seccion(), "registrar_error", lambda contexto, *a, **k: detalles.append(k.get("detalle", "")))
        tablas = seccion().tablas_de_la_seccion(svc().leer(mundo.refs["dosis_no_coincide"]))
        filas = _filas(tablas[CLAVE_DE_LA_DOSIS])
        assert [f[1] for f in filas if f[0] == "Nota"] == [seccion().FRASE_DOSIS_NO_COINCIDE, seccion().FRASE_PERFILES_EN_NETOD]
        assert not any(f[0].startswith(("Dosis media", "Penumbra")) for f in filas)
        assert len(detalles) == 1 and "fwhm_crossplane_dosis_mm" in detalles[0]
        assert _filas(tablas["placa_mensual_perfiles"])[0][0] == "Perfiles de la capa verde"

    @pytest.mark.parametrize("nombre", ["dosis_no_coincide", "copia_danada"])
    def test_si_la_figura_no_se_pudo_dibujar_la_dosis_no_dice_que_los_perfiles_se_imprimen_en_netod(self, mundo, monkeypatch, nombre):
        """CD8-REV1-PROD-03 (ronda 1): «Los perfiles se imprimen en densidad optica neta y no en dosis.» es verdad solo si se imprimen. Si la figura no se pudo dibujar (F1R-9: la parte que falla no tumba el PDF)
        la tabla de valores dice «Los perfiles no se imprimen: no se pudieron dibujar.» y la de la dosis no puede decir lo contrario en el mismo documento firmado."""
        sec = seccion()
        monkeypatch.setattr(sec, "png_de_los_perfiles", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no hay figura")))
        monkeypatch.setattr(sec, "registrar_error", lambda *a, **k: None)
        tablas = sec.tablas_de_la_seccion(svc().leer(mundo.refs[nombre]))
        assert "placa_mensual_perfiles" not in tablas
        assert sec.FRASE_NO_SE_PUDIERON_DIBUJAR in [f[1] for f in _filas(tablas["placa_mensual_valores"]) if f[0] == "Nota"]
        assert sec.FRASE_PERFILES_EN_NETOD not in [f[1] for f in _filas(tablas[CLAVE_DE_LA_DOSIS]) if f[0] == "Nota"]

    def test_otra_version_con_dosis_imprime_lo_guardado_en_dosis_y_dice_por_que(self, mundo):
        tablas = _tablas(mundo, "dosis_otra_version")
        filas = _filas(tablas[CLAVE_DE_LA_DOSIS])
        assert [f[1] for f in filas if f[0] == "Nota"] == [seccion().FRASE_DOSIS_SIN_LA_NETOD]
        assert "placa_mensual_perfiles" not in tablas and "placa_mensual_barrido" not in tablas

    def test_un_registro_no_medible_en_dosis_dice_su_estado(self, mundo):
        registro = dict(svc().leer(mundo.refs["dosis"]), estado_dosis="no medible en dosis: la meseta pasa el rango útil de la curva", fwhm_crossplane_dosis_mm=None)
        filas = _filas(seccion()._tabla_de_la_dosis(registro, None, [], seccion()._estilo_del_texto()))
        assert ["Estado", registro["estado_dosis"]] in filas and ["FWHM crossplane [mm]", NO_MEDIBLE] in filas

    def test_un_registro_no_medible_en_dosis_imprime_su_linea_su_estado_y_dibuja_en_netod(self, mundo):
        """CD8-REV1-PROD-02 / RP-1 / RP-2 (el escenario P30 del PROTOCOLO, por `tablas_de_la_seccion` y no por la funcion privada con un diccionario): el registro se guardo con la copia de la curva y la capa
        reportada «no medible en dosis: <motivo>»; se reconstruye en dosis (coherente con lo guardado) y la capa no es medible en dosis. Imprime SU LINEA de la curva y su «Estado», lo guardado «no medible», ninguna
        fila nueva en dosis, y el grafico en netOD con la nota que lo dice (una vista nunca mezcla las bases, DA-92)."""
        registro = svc().leer(mundo.refs["dosis_no_medible"])
        estado = registro["estado_dosis"]
        assert registro["estado"] == "ok" and estado.startswith("no medible en dosis: ") and registro["fwhm_crossplane_dosis_mm"] is None
        tablas = _tablas(mundo, "dosis_no_medible")
        filas = _filas(tablas[CLAVE_DE_LA_DOSIS])
        assert filas[2:5] == [["Base de la medida", pm().BASE_DOSIS], ["Curva de dosis", LINEA_DE_LA_CURVA.format(rango=60.0)], ["Estado", estado]]
        assert [f[1] for f in filas if f[0] in {v[0] for v in GUARDADAS.values()}] == [NO_MEDIBLE] * 6
        assert not any(f[0].startswith(("Dosis media", "U de la dosis", "Penumbra", "Largo", "Radiación −")) for f in filas)
        assert [f[1] for f in filas if f[0] == "Nota"] == [seccion().FRASE_PERFILES_EN_NETOD]
        assert _filas(tablas["placa_mensual_perfiles"])[0][0] == "Perfiles de la capa verde"

    def test_el_pdf_de_un_registro_no_medible_en_dosis_dice_su_estado_su_linea_y_que_los_perfiles_van_en_netod(self, mundo):
        texto = _la_seccion(mundo.pdf("dosis_no_medible"))
        for parte in (svc().leer(mundo.refs["dosis_no_medible"])["estado_dosis"], LINEA_DE_LA_CURVA.format(rango=60.0), seccion().FRASE_PERFILES_EN_NETOD, "Perfiles de la capa verde"):
            assert normal(parte) in texto, parte
        assert "Perfiles de la capa verde, en dosis" not in texto

    def test_la_linea_dice_si_la_capa_no_tiene_rango_util(self, mundo, monkeypatch):
        """Una copia cuya capa reportada no tiene rango util (la calibracion cambio de estado; en la base no puede pasar con la regla del boton, pero la linea no debe caerse): lo dice con su estado."""
        sin_rango = con_capa(mundo.escena.curva, "G", rango_cgy=None, estado="no válida: el ajuste no converge")
        monkeypatch.setattr(svc(), "curva_guardada", lambda registro: _efectiva(sin_rango))
        linea = seccion().texto_de_la_curva(svc().leer(mundo.refs["dosis"]))
        assert linea == ("la copia guardada con el registro: lote «L-31», irradiada el 2026-10-30 (calibración 7), modelo de Devic; la capa verde no tiene rango útil: no válida: el ajuste no "
                         "converge"), linea

    @pytest.mark.parametrize("capa", ["R", "G", "B"])
    def test_la_linea_dice_el_rango_util_de_la_capa_reportada_y_no_el_de_otra(self, mundo, monkeypatch, capa):
        """MB01 (re-medicion del 01-11) y CD8-REV1-PROD-01 (ronda 1): desde CD.5b (DA-94) la curva de la escena tiene el MISMO rango util en sus tres capas (600 cGy), asi que la tabla en dosis no distingue que capa
        da el rango; aqui cada capa tiene el suyo y la linea debe decir el de la capa reportada, sea cual sea. Los registros del fixture son de la verde: con solo ella `curva.rango('G')` pasaba sin que se viera."""
        monkeypatch.setattr(svc(), "curva_guardada", lambda registro: _efectiva(_curva_de_rangos_distintos(mundo.escena.curva)))
        registro = dict(svc().leer(mundo.refs["dosis"]), capa=capa)
        assert seccion().texto_de_la_curva(registro) == LINEA_DE_UNA_CAPA.format(adjetivo=ADJETIVO_POR_CAPA[capa], rango=RANGO_POR_CAPA[capa])

    @pytest.mark.parametrize("calibracion, esperado", [
        ({"id": None, "lote": "L-31", "fecha_irradiacion": "2026-10-30"}, "lote «L-31», irradiada el 2026-10-30 (calibración sin número), modelo de Devic; la capa verde es útil de 0 a"),
        ({"id": 7, "lote": None, "fecha_irradiacion": "2026-10-30"}, "lote «sin lote», irradiada el 2026-10-30 (calibración 7), modelo de Devic; la capa verde es útil de 0 a"),
        ({"id": 7, "lote": "L-31", "fecha_irradiacion": None}, "lote «L-31», irradiada el sin fecha (calibración 7), modelo de Devic; la capa verde es útil de 0 a"),
        ({"id": None, "lote": None, "fecha_irradiacion": None}, "lote «sin lote», irradiada el sin fecha (calibración sin número), modelo de Devic; la capa verde es útil de 0 a"),
        ("danada", "lote «sin lote», irradiada el sin fecha (calibración sin número): la copia de la curva guardada con el registro no se puede leer: ")],
        ids=["id_ausente", "lote_ausente", "fecha_ausente", "ninguno_de_los_tres", "no_es_un_diccionario"])          # ids cortos y sin espacios: los nombres de los casos van a los logs del rojo y de las mutaciones
    def test_la_linea_no_imprime_un_literal_de_python_si_a_la_copia_le_falta_su_identificacion(self, mundo, calibracion, esperado):
        """CD8-REV1-PROD-04 (ronda 1): una copia a la que le falta el lote o la fecha dice «sin lote» o «sin fecha»; al id de la calibracion le faltaba su respaldo y el documento firmado imprimia «(calibración None)»
        (una copia danada cuya calibracion no es un diccionario, el caso que `_leer_la_copia` atiende a proposito)."""
        registro = copy.deepcopy(svc().leer(mundo.refs["dosis"]))
        registro["curva"]["calibracion"] = calibracion
        linea = seccion().texto_de_la_curva(registro)
        assert esperado in linea and "None" not in linea, linea

    def test_reconstruir_en_dosis_de_un_registro_sin_dosis_no_mide(self, mundo, monkeypatch):
        monkeypatch.setattr(svc(), "recalcular_en_dosis", lambda registro: (_ for _ in ()).throw(AssertionError("no se mide en dosis sin la copia")))
        assert seccion().reconstruir_en_dosis(svc().leer(mundo.refs["netod"])) == (None, None)

    def test_el_barrido_dice_su_base_solo_si_el_registro_guardo_la_dosis(self, mundo):
        assert _filas(_tablas(mundo, "dosis")["placa_mensual_barrido"])[0][0] == "Medidas estadísticas del barrido, capa verde, en densidad óptica neta"
        assert _filas(_tablas(mundo, "netod")["placa_mensual_barrido"])[0][0] == "Medidas estadísticas del barrido, capa verde"

    def test_un_registro_de_la_capa_azul_lo_dice_en_toda_la_dosis_y_trae_el_rango_de_la_azul(self, mundo):
        """CD8-REV1-PROD-01 (ronda 1): la capa reportada que se imprime es la GUARDADA tambien en la tabla en dosis: ni los titulos, ni la linea de la curva, ni las filas, ni la figura son los de la verde. El
        registro tiene una curva de rango util distinto por capa."""
        registro = svc().leer(mundo.refs["dosis_azul"])
        assert registro["capa"] == "B" and registro["estado_dosis"] == "ok"
        tablas = _tablas(mundo, "dosis_azul")
        valores, dosis = _filas(tablas["placa_mensual_valores"]), _filas(tablas[CLAVE_DE_LA_DOSIS])
        assert valores[0][0] == f"{TITULO_DE_LA_SECCION}, capa azul" and ["Capa reportada", "capa azul"] in valores
        assert dosis[0][0] == f"{TITULO_DE_LA_SECCION}, capa azul, en dosis"
        assert dosis[3] == ["Curva de dosis", LINEA_DE_UNA_CAPA.format(adjetivo="azul", rango=RANGO_POR_CAPA["B"])]
        propios = dict((f[0], f[1]) for f in dosis[1:] if len(f) == 2)
        for nombre, (de_f1, _v) in GUARDADAS.items():
            assert propios[de_f1] == dibujo().numero(registro[nombre.replace("_mm", "_dosis_mm")], 3, nombre.startswith("desfase"))
        nuevas = _nuevas(svc().recalcular_en_dosis(registro), "B")
        assert nuevas and dosis[dosis.index(nuevas[0]):][:len(nuevas)] == nuevas
        assert _filas(tablas["placa_mensual_barrido"])[0][0] == "Medidas estadísticas del barrido, capa azul, en densidad óptica neta"
        assert _filas(tablas["placa_mensual_perfiles"])[0][0] == "Perfiles de la capa azul, en dosis"


# ===================================================================================================== sin veredicto, sin simbolos, sin «umbra»

class TestLosTextos:
    @pytest.mark.parametrize("nombre", ["netod", "dosis", "copia_danada", "dosis_no_medible"])
    def test_sin_veredicto_sin_simbolos_y_sin_umbra(self, mundo, nombre):
        texto = _la_seccion(mundo.pdf(nombre)).lower()
        assert not any(v in texto for v in VEREDICTOS), [v for v in VEREDICTOS if v in texto]
        assert not any(s in texto for s in SIMBOLOS_DA18) and "umbra" not in texto.replace("penumbra", "")

    @pytest.mark.parametrize("nombre", ["netod", "dosis", "dosis_no_medible"])
    def test_ningun_literal_de_python_en_el_texto_del_pdf(self, mundo, nombre):
        """CD8-REV1-PROD-04 (ronda 1): lo que no se midio o no se sabe dice «no medible» o «sin ...», nunca el literal de Python (None, nan, inf, True, False) en un documento firmado. No incluye `copia_danada`:
        de una copia que no se lee la linea imprime el motivo TAL CUAL lo da el lector de la curva (CD.4), que puede traer un repr («es del modelo None»): su redaccion no es de esta tarea (la identificacion de
        la copia, que si es de esta seccion, la vigila el caso de la linea)."""
        encontrados = re.findall(r"\b(None|nan|inf|True|False)\b", _la_seccion(mundo.pdf(nombre)))
        assert not encontrados, encontrados

    def test_las_constantes_nuevas_dicen_sus_unidades_entre_corchetes_y_no_dicen_umbra(self):
        fuente = SECCION_PY.read_text(encoding="utf-8")
        arbol = ast.parse(fuente)
        textos = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        assert not any(re.search(r"\((mm|cGy|nivel)\)", t) for t in textos)
        assert "umbra" not in fuente.replace("penumbra", "").replace("Penumbra", "")
        assert "[cGy]" in seccion().TEXTO_DE_LA_CURVA


# ===================================================================================================== la estructura

class TestEstructura:
    def test_la_seccion_no_lee_la_curva_vigente_ni_la_base_ni_qt(self):
        """DA-81: la curva es la copia del registro (`svc.curva_guardada`, `svc.recalcular_en_dosis`); la seccion no busca la vigente, no abre la base, no importa Qt ni pyplot."""
        arbol = ast.parse(SECCION_PY.read_text(encoding="utf-8"))
        importados = {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names} | {n.module or "" for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)}
        nombres = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
        assert not [m for m in importados if m.startswith(("PyQt5", "sqlite3", "services.curva_dosis", "matplotlib.pyplot", "data.ManejoDatos"))], importados
        assert not ({"vigentes_validas", "curva_efectiva", "pyplot", "Conexion"} & nombres)
        docstrings = {id(n.value) for n in ast.walk(arbol) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
        assert not [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings and "SELECT " in n.value]

    def test_ninguna_base_se_escribe_a_mano(self):
        """Tripwire del bloque: la fila «Base de la medida» y los textos que nombran una base la toman del motor (`motor.BASE_*`) o de lo guardado, nunca de un literal. «dosis» es tambien un sustantivo
        («Curva de dosis», «la dosis de la meseta»): de ella se vigila la base como complemento, «en dosis» (CD8-RP-4, ronda 1: antes solo se miraban las otras dos y la promesa no valia para la base de esta
        tarea; un texto que dice «en dosis» escrito a mano no sigue al motor si el nombre de la base cambia)."""
        arbol = ast.parse(SECCION_PY.read_text(encoding="utf-8"))
        for lista in (n for n in ast.walk(arbol) if isinstance(n, ast.List) and n.elts and isinstance(n.elts[0], ast.Constant) and n.elts[0].value == "Base de la medida"):
            assert not isinstance(lista.elts[1], ast.Constant), ast.unparse(lista)
        docstrings = {id(n.value) for n in ast.walk(arbol) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
        literales = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]
        for base in (pm().BASE_DENSIDAD_OPTICA, pm().BASE_VALOR_DE_PIXEL):
            assert not [t for t in literales if base in t], base
        en_la_base_dosis = re.compile(rf"\ben {re.escape(pm().BASE_DOSIS)}\b", re.IGNORECASE)
        assert not [t for t in literales if en_la_base_dosis.search(t)], [t for t in literales if en_la_base_dosis.search(t)]

    def test_componer_figura_pasa_la_curva_del_analisis(self):
        arbol = ast.parse(SECCION_PY.read_text(encoding="utf-8"))
        funcion = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "componer_figura")
        llamada = next(n for n in ast.walk(funcion) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "dibujar_perfil")
        curva = [k.value for k in llamada.keywords if k.arg == "curva"]
        assert len(curva) == 1 and ast.unparse(curva[0]) == "resultado.curva"


def _literales_de(ruta, funcion=None):
    """Los literales de texto (sin docstrings) del archivo `ruta`, o solo de su funcion `funcion`; de un f-string, sus partes fijas."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    if funcion:
        arbol = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == funcion)
    docstrings = {id(n.value) for n in ast.walk(arbol) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
    return [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]


class TestUnaSolaDefinicionDelTexto:
    """H-CD9-3, H-CD9-4 y H-CD9-5 (pre-vuelo de CD.9, llevados por CD.8): el dibujo nombra las bases con `motor.BASE_*` y el rotulo del desfase de cada lado es UNA constante del dibujo
    (`ROTULO_DEL_LADO`) que usan la tabla de la ventana y la seccion. Ningun texto que se ve o se imprime cambia: lo vigilan las pruebas de CD.7, CD.6b, B.8 y F.1 y el diferencial."""

    def test_texto_se_guarda_nombra_las_bases_del_motor(self):
        assert dibujo().texto_se_guarda("G", "G", None, en_dosis=True) == "se guarda (en densidad óptica neta y en dosis)"
        assert dibujo().texto_se_guarda("G", "G", "x", en_dosis=True) == "no se guarda: no es medible (en densidad óptica neta)"
        assert not [t for t in _literales_de(DIBUJO_PY, "texto_se_guarda") if pm().BASE_DENSIDAD_OPTICA in t.lower() or "y en dosis" in t], "H-CD9-3: la base escrita a mano"

    def test_la_meseta_en_netod_nombra_la_base_del_motor(self):
        assert not [t for t in _literales_de(DIBUJO_PY, "_meseta_de_la_capa") if pm().BASE_DENSIDAD_OPTICA in t.lower()], "H-CD9-4: la base escrita a mano"

    def test_el_rotulo_del_lado_es_uno_y_lo_usan_la_ventana_y_la_seccion(self):
        assert dibujo().ROTULO_DEL_LADO == "Lado {lado} (radiación − luz) [mm]"          # escrito aqui a mano: el texto de hoy
        assert [t for t in _literales_de(DIBUJO_PY) if "(radiación − luz) [mm]" in t] == [dibujo().ROTULO_DEL_LADO], "H-CD9-5: el dibujo escribe el rotulo del lado una sola vez"
        assert not [t for t in _literales_de(SECCION_PY) if "radiación − luz) [mm]" in t], "H-CD9-5: la seccion copia el rotulo de la ventana"
        lados = ("izquierdo", "derecho", "superior", "inferior")
        assert {f"desfase_{lado}_mm": seccion().ROTULOS_DE_LA_VENTANA[f"desfase_{lado}_mm"] for lado in lados} == {f"desfase_{lado}_mm": dibujo().ROTULO_DEL_LADO.format(lado=lado) for lado in lados}


# ===================================================================================================== la paginacion

def _juntos(pdf, *marcas):
    return bool(set.intersection(*(set(paginas_de(pdf, m)) for m in marcas)))


class TestLaPaginacion:
    @pytest.mark.parametrize("nombre", ["netod", "dosis"])
    def test_cada_titulo_en_la_pagina_de_su_primera_fila_y_la_figura_de_384_x_400_en_la_de_su_titulo(self, mundo, nombre):
        pdf = mundo.pdf(nombre)
        assert _juntos(pdf, f"{TITULO_DE_LA_SECCION}, capa verde", "Capa reportada capa verde")
        assert _juntos(pdf, "Medidas estadísticas del barrido, capa verde", "Corte central")
        titulo = "Perfiles de la capa verde" + (", en dosis" if nombre == "dosis" else "")
        figuras = [i for i in imagenes_de(pdf) if abs(i[1].width - ANCHO_FIGURA) < 1 and abs(i[1].height - ALTO_FIGURA) < 1]
        assert len(figuras) == 1 and figuras[0][0] in paginas_de(pdf, titulo)
        if nombre == "dosis":
            assert _juntos(pdf, f"{TITULO_DE_LA_SECCION}, capa verde, en dosis", "Curva de dosis")

    @pytest.mark.parametrize("nombre, paginas", [("netod", 4), ("dosis", 6)])
    def test_la_seccion_ocupa_las_paginas_medidas(self, mundo, nombre, paginas):
        """Medido en el pre-vuelo (logs/CD8_prevuelo/sonda/ del anexo): netOD de la pagina 5 a la 8 (la tabla de valores sigue en la 6), dosis de la 5 a la 10. Una regresion que sume una pagina cae."""
        pdf = mundo.pdf(nombre)
        primera = min(paginas_de(pdf, TITULO_DE_LA_SECCION))
        ultima = max(paginas_de(pdf, TITULO_DE_LA_PELICULA))
        assert ultima - primera + 1 <= paginas, (primera, ultima)
