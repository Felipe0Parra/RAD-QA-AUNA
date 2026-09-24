"""E.2 (PLAN_HANDOFF_IMAGENES_22-09.md §6): la tabla de parámetros de adquisición, UNA sola vez,
al inicio del informe -- y con la información general del equipo, como sale de la metadata.

CAUSA. **[código]** `_crear_tabla_parametros` se llamaba siete veces, una por categoría, y cada una
rotulaba su columna con la categoría: siete tablas casi idénticas. **[medido]** en el PDF real de la
sesión 47 salían "Parámetros de adquisición Espesor de corte", "... Tamaño de pixel", etc. Anotación 10
del físico: *"es suficiente con que en el reporte solo salga una vez al inicio"*. Y pidió (23-09) que
el informe diga *"la información general del equipo como sale de la metadata, el protocolo"*.

Lo que este archivo garantiza:

  1. UNA VEZ -- el PDF real (mensual) y la sección de imágenes del PDF anual (Halcyon y iX) llevan la
     tabla una sola vez, y ya no las siete con nombre de categoría.
  2. LO QUE YA ESTABA NO SE PIERDE -- kV, mA y espesor de corte siguen saliendo; en un control anterior
     a A.1 (23-09-2026), donde no hay identidad DICOM, la tabla lo DICE y no inventa nada.
  3. LA METADATA, DESDE LA BD -- identidad (fabricante, modelo, estación, serie, software), adquisición
     (serie, fecha, kV, mA, mAs, CTDIvol, espesor, kernel, filtro, FOV, píxel, cortes) y el veredicto
     del protocolo salen de lo GUARDADO en `pruebas`, no de la sesión (§12.4). Lo que el equipo no
     publica se dice; la desviación archivada sale tal cual.
  4. SI DIVERGEN, LO DICE -- si las pruebas de una sesión se corrieron con adquisiciones distintas, la
     tabla lo avisa y las lista, en vez de ocultarlo con un resumen.
  5. NINGUNA TABLA SE PIERDE -- el generador mensual y el anual leen UNA lista de las tablas del
     informe de imágenes (antes eran cinco copias, y el anual descarta en silencio lo que no conoce).
  6. UNA SOLA DEFINICIÓN de las filas de identidad y de adquisición, compartida con la ventana de A.3.
"""
import ast
import functools
import pathlib
import re
import sqlite3

import pytest

import fitz

from _informe_imagenes import Padre, app, avisos, bd_copia, generar, paginas  # noqa: F401  (fixtures)
from _corpus import serie_catphan

import models.PDF.pdf as pdf_mod
from analisisImagenes.catphan.protocolos import comparar_con_protocolo
from analisisImagenes.catphan.serie import adquisicion_de_serie, leer_serie
from data.ManejoDatos.catphan_TAC.catphan_db import mapear_identidad_dicom
from models.PDF.Anual.reportes_anuales import obtener_tablas_sistema_imagenes_para_pdf
from models.PDF.pdf import generar_reporte_pdf_multitabla_anual, generar_reporte_pdf_multitabla_mensual

RAIZ = pathlib.Path(__file__).resolve().parent.parent

TITULO_TABLA = "Parámetros de adquisición"
LEGADO = "no registrado (control anterior al 23-09-2026)"
NO_PUBLICADO = "(no lo publica el equipo)"
CATEGORIAS = ["Espesor de corte", "Tamaño de pixel", "Resolución de contraste", "Resolución espacial",
              "Valores CT", "Linealidad CT", "Uniformidad"]

# (sesión, equipo, fecha) -- sesiones reales de la copia del 21-09, ANTERIORES a A.1: sin identidad DICOM
SESION_47 = (47, "Halcyon", "22/09/2026")
SESION_48 = (48, "Tomógrafo", "22/09/2026")
SESION_42 = (42, "Tomógrafo", "07/2026")      # las 7 categorías
SESION_30 = (30, "Clinac ix", "05/2026")


@functools.lru_cache(maxsize=None)
def _adq_real(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return adquisicion_de_serie(leer_serie(ruta))


def _archivar(bd, ref, adq, desviacion="__calcular__", equipo=None, tipos=None):
    """Escribe en `pruebas` de la COPIA lo que A.1/A.2 habrían guardado: la identidad DICOM y la
    desviación del protocolo. Con el mismo mapeador que usa el guardado real."""
    if desviacion == "__calcular__":
        desviacion = comparar_con_protocolo(equipo, adq).desviacion_texto()
    equipo_dicom, serie_uid, fecha, js = mapear_identidad_dicom(adq)
    con = sqlite3.connect(bd)
    sql = ("UPDATE pruebas SET equipo_dicom=?, serie_uid=?, fecha_adquisicion=?, adquisicion_dicom=?, "
           "desviacion_protocolo=?, kv=?, ma=?, espesor_corte=? "
           "WHERE id_sesion=? AND (activo IS NULL OR activo=1)")
    args = [equipo_dicom, serie_uid, fecha, js, desviacion, adq.get("kv"), adq.get("ma"),
            adq.get("espesor_mm"), ref]
    if tipos is not None:
        sql += " AND id_tipo IN (%s)" % ",".join("?" * len(tipos))
        args += list(tipos)
    n = con.execute(sql, args).rowcount
    con.commit()
    con.close()
    assert n > 0, "no se archivó nada: ¿la sesión no tiene pruebas vigentes?"


def _pdf(app, avisos, bd_copia, monkeypatch, sesion, flag=True):
    ref, equipo, fecha = sesion
    ok, visor = generar(bd_copia, monkeypatch, ref, equipo, fecha, flag)
    assert ok is True and avisos == [], f"la generación falló: {avisos}"
    return paginas(visor["pdf"])


def _texto(paginas_):
    return "\n".join(paginas_)


def _plano(paginas_):
    """El texto con los saltos de línea de las celdas que se parten, unificados."""
    return re.sub(r"\s+", " ", _texto(paginas_))


def _tabla_de_parametros(paginas_):
    """Solo la tabla de parámetros: desde su título hasta su última fila (más su valor)."""
    plano = _plano(paginas_)
    ini = plano.index(TITULO_TABLA)
    for ultima in ("Frente al protocolo", "Identidad y adquisición DICOM"):
        if ultima in plano[ini:]:
            return plano[ini: plano.index(ultima, ini) + len(ultima) + 90]
    raise AssertionError("la tabla de parámetros no trae su última fila")


# ---------------------------------------------------------------------------
# 1. UNA VEZ
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sesion", [SESION_47, SESION_48, SESION_42], ids=lambda s: f"sesion{s[0]}")
def test_el_pdf_real_lleva_la_tabla_de_parametros_una_sola_vez(app, avisos, bd_copia, monkeypatch, sesion):
    texto = _texto(_pdf(app, avisos, bd_copia, monkeypatch, sesion))
    assert texto.count(TITULO_TABLA) == 1
    for categoria in CATEGORIAS:
        assert f"{TITULO_TABLA} {categoria}" not in texto, (
            f"sigue saliendo la tabla por categoría: {categoria}")


def test_la_tabla_va_al_inicio_antes_de_los_resultados(app, avisos, bd_copia, monkeypatch):
    texto = _texto(_pdf(app, avisos, bd_copia, monkeypatch, SESION_47))
    assert texto.index(TITULO_TABLA) < texto.index("Espesor promedio medido")


# ---------------------------------------------------------------------------
# 2. LO QUE YA ESTABA NO SE PIERDE; UN CONTROL VIEJO LO DICE
# ---------------------------------------------------------------------------

def test_un_control_anterior_a_A1_conserva_kv_ma_espesor_y_dice_que_no_hay_mas(
        app, avisos, bd_copia, monkeypatch):
    """Sesión 47 tal cual está en la BD del 21-09: 125 kV / 100 mA / 2.0 mm y ninguna identidad DICOM."""
    paginas_ = _pdf(app, avisos, bd_copia, monkeypatch, SESION_47)
    texto = _texto(paginas_)
    for etiqueta, valor in (("kV", "125"), ("mA", "100"), (r"Espesor de corte \[mm\]", "2")):
        assert re.search(rf"{etiqueta}\s+{valor}\b", _tabla_de_parametros(paginas_)), (
            f"{etiqueta} = {valor} debe seguir saliendo, una vez")
    assert LEGADO in _plano(paginas_)
    assert "Fabricante" not in texto, "no se inventa una identidad que no se guardó"
    assert NO_PUBLICADO not in texto, "'no registrado' no es lo mismo que 'no lo publica el equipo'"


# ---------------------------------------------------------------------------
# 3. LA METADATA, DESDE LA BD
# ---------------------------------------------------------------------------

def test_un_control_con_metadata_guardada_la_imprime_completa(app, avisos, bd_copia, monkeypatch):
    adq = _adq_real("HALCYON_SEP")
    _archivar(bd_copia, 47, adq, equipo="Halcyon")
    paginas_ = _pdf(app, avisos, bd_copia, monkeypatch, SESION_47)
    texto = _plano(paginas_)          # las etiquetas largas se parten en dos líneas en la celda

    for etiqueta in ("Fabricante", "Modelo", "Estación", "Número de serie del equipo", "Software",
                     "Descripción de la serie", "Fecha de adquisición", "kV", "mA", "mAs",
                     "CTDIvol [mGy]", "Espesor de corte [mm]", "Kernel", "Filtro", "FOV [mm]",
                     "Píxel [mm]", "Cortes"):
        assert etiqueta in texto, f"falta la fila {etiqueta!r}"
    for clave in ("fabricante", "modelo", "estacion", "descripcion_serie", "fecha_adquisicion"):
        assert str(adq[clave]) in texto, f"falta el valor de {clave}: {adq[clave]!r}"
    assert str(adq["n_cortes"]) in texto
    assert LEGADO not in texto
    assert _texto(paginas_).count(TITULO_TABLA) == 1


def test_una_adquisicion_conforme_dice_que_no_hay_desviacion(app, avisos, bd_copia, monkeypatch):
    adq = _adq_real("HALCYON_SEP")                         # Pelvis_iCBCT_2.0_IQ!: el protocolo decidido
    assert comparar_con_protocolo("Halcyon", adq).desviacion_texto() is None
    _archivar(bd_copia, 47, adq, equipo="Halcyon")
    paginas_ = _pdf(app, avisos, bd_copia, monkeypatch, SESION_47)
    assert "Sin desviación registrada respecto del protocolo de Halcyon" in _plano(paginas_)
    assert "fuera de protocolo" not in _texto(paginas_)


def _lineas_de_texto(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return [" ".join(s["text"] for s in l["spans"])
            for p in doc for b in p.get_text("dict")["blocks"] if b.get("type") == 0 for l in b["lines"]]


def test_el_veredicto_ocupa_el_ancho_completo_de_la_tabla(app, avisos, bd_copia, monkeypatch):
    """La fila 'Frente al protocolo' es de ANCHO COMPLETO: su texto largo cabe en una sola línea (en una
    celda de valor de 137 pt se partiría en tres)."""
    _archivar(bd_copia, 47, _adq_real("HALCYON_SEP"), equipo="Halcyon")
    ok, visor = generar(bd_copia, monkeypatch, *SESION_47)
    assert ok is True
    frase = "Sin desviación registrada respecto del protocolo de Halcyon"
    assert any(frase in l for l in _lineas_de_texto(visor["pdf"])), (
        "el veredicto se partió en varias líneas: la fila no ocupa el ancho completo")


def test_una_desviacion_archivada_sale_tal_cual(app, avisos, bd_copia, monkeypatch):
    """`Pelvis Fast` con 100 mA: el texto que A.2 archivó, palabra por palabra."""
    adq = _adq_real("HALCYON_JUN")
    archivado = comparar_con_protocolo("Halcyon", adq).desviacion_texto()
    assert archivado and archivado.startswith("Adquisición fuera de protocolo")
    _archivar(bd_copia, 47, adq, equipo="Halcyon")
    texto = _texto(_pdf(app, avisos, bd_copia, monkeypatch, SESION_47))
    plano = re.sub(r"\s+", " ", texto)
    assert re.sub(r"\s+", " ", archivado) in plano
    assert "Sin desviación registrada" not in texto


def test_lo_que_el_equipo_no_publica_se_dice(app, avisos, bd_copia, monkeypatch):
    """El iX no publica descripción de la serie, CTDIvol ni filtro (medido)."""
    adq = _adq_real("IX_DIC")
    assert adq.get("descripcion_serie") is None
    _archivar(bd_copia, 30, adq, equipo="Clinac ix")
    tabla = _tabla_de_parametros(_pdf(app, avisos, bd_copia, monkeypatch, SESION_30))
    assert re.sub(r"\s+", " ", tabla).count(NO_PUBLICADO) >= 3
    assert "None" not in tabla


def test_el_pdf_sale_de_la_bd_no_de_la_sesion(app, avisos, bd_copia, monkeypatch):
    """Reabrir el control dos veces da el mismo documento; y si la BD cambia, cambia el documento."""
    _archivar(bd_copia, 47, _adq_real("HALCYON_SEP"), equipo="Halcyon")
    uno = _texto(_pdf(app, avisos, bd_copia, monkeypatch, SESION_47))
    otro = _texto(_pdf(app, avisos, bd_copia, monkeypatch, SESION_47))
    assert uno == otro
    _archivar(bd_copia, 47, _adq_real("HALCYON_JUN"), equipo="Halcyon")
    assert _texto(_pdf(app, avisos, bd_copia, monkeypatch, SESION_47)) != uno


def test_los_caracteres_de_marcado_en_la_metadata_no_rompen_el_pdf(app, avisos, bd_copia, monkeypatch):
    adq = dict(_adq_real("HALCYON_SEP"))
    adq["descripcion_serie"] = "Pelvis <b>&</b> 2.0"
    _archivar(bd_copia, 47, adq, desviacion="Fuera: kV <140> & mA", equipo="Halcyon")
    plano = re.sub(r"\s+", " ", _texto(_pdf(app, avisos, bd_copia, monkeypatch, SESION_47)))
    assert "Pelvis <b>&</b> 2.0" in plano
    assert "kV <140> & mA" in plano


def test_una_adquisicion_ilegible_se_dice_y_no_rompe_el_informe(app, avisos, bd_copia, monkeypatch):
    con = sqlite3.connect(bd_copia)
    con.execute("UPDATE pruebas SET adquisicion_dicom = '{no es json' WHERE id_sesion = 47")
    con.commit()
    con.close()
    texto = _texto(_pdf(app, avisos, bd_copia, monkeypatch, SESION_47))
    assert texto.count(TITULO_TABLA) == 1
    assert "no se pudo leer" in texto


# ---------------------------------------------------------------------------
# 4. SI DIVERGEN, LO DICE
# ---------------------------------------------------------------------------

def test_si_las_pruebas_se_corrieron_con_adquisiciones_distintas_la_tabla_lo_dice(
        app, avisos, bd_copia, monkeypatch):
    _archivar(bd_copia, 47, _adq_real("HALCYON_SEP"), equipo="Halcyon")                  # todas
    _archivar(bd_copia, 47, _adq_real("HALCYON_JUN"), equipo="Halcyon", tipos=[5])       # valores CT: otra toma
    texto = _texto(_pdf(app, avisos, bd_copia, monkeypatch, SESION_47))
    plano = re.sub(r"\s+", " ", texto)
    # Es UNA tabla: si es más alta que una página se parte y repite su encabezado (una vez por página).
    con_titulo = [i for i, p in enumerate(_pdf(app, avisos, bd_copia, monkeypatch, SESION_47)) if TITULO_TABLA in p]
    assert con_titulo == list(range(len(con_titulo))) and con_titulo[0] == 0
    assert "distintas" in plano
    assert "Adquisición 1" in plano and "Adquisición 2" in plano
    assert "Valores CT" in plano.split("Adquisición 2")[1][:200], "la adquisición distinta debe nombrar su categoría"
    assert "Pelvis Fast_iCBCT_2.0" in plano and "Pelvis_iCBCT_2.0_IQ!" in plano


def test_la_divergencia_tambien_se_ve_en_un_control_anterior_a_A1(app, avisos, bd_copia, monkeypatch):
    """Sin identidad DICOM, dos pruebas con kV distinto ya son adquisiciones distintas."""
    con = sqlite3.connect(bd_copia)
    con.execute("UPDATE pruebas SET kv = 140 WHERE id_sesion = 47 AND id_tipo = 5")
    con.commit()
    con.close()
    plano = re.sub(r"\s+", " ", _texto(_pdf(app, avisos, bd_copia, monkeypatch, SESION_47)))
    assert "distintas" in plano and "Adquisición 2" in plano
    assert "140" in plano and "125" in plano


def test_si_diverge_la_tabla_empieza_en_la_primera_pagina(app, avisos, bd_copia, monkeypatch):
    """Con dos adquisiciones la tabla es más alta que una página: no debe dejar la primera en blanco."""
    _archivar(bd_copia, 47, _adq_real("HALCYON_JUN"), equipo="Halcyon")
    _archivar(bd_copia, 47, _adq_real("HALCYON_SEP"), equipo="Halcyon", tipos=[5])
    paginas_ = _pdf(app, avisos, bd_copia, monkeypatch, SESION_47)
    assert TITULO_TABLA in paginas_[0], "la primera página quedó en blanco: la tabla pasó entera a la segunda"


def test_si_la_tabla_se_parte_repite_su_encabezado(app, avisos, bd_copia, monkeypatch):
    """Toda página que trae filas de la tabla (cada adquisición cierra con 'Frente al protocolo')
    trae también el título de la tabla."""
    _archivar(bd_copia, 47, _adq_real("HALCYON_JUN"), equipo="Halcyon")
    _archivar(bd_copia, 47, _adq_real("HALCYON_SEP"), equipo="Halcyon", tipos=[5])
    paginas_ = _pdf(app, avisos, bd_copia, monkeypatch, SESION_47)
    con_filas = [i for i, p in enumerate(paginas_) if "Frente al" in re.sub(r"\s+", " ", p)]
    assert len(con_filas) >= 2, "esta prueba necesita que la tabla se parta entre dos páginas"
    for i in con_filas:
        assert TITULO_TABLA in paginas_[i], f"la página {i + 1} trae filas de la tabla sin su encabezado"


def test_una_divergencia_solo_en_la_identidad_tambien_se_detecta(app, avisos, bd_copia, monkeypatch):
    """Mismo kV, mA y espesor, pero otra serie DICOM: la firma de la adquisición incluye la identidad."""
    adq = _adq_real("HALCYON_SEP")
    otra = dict(adq, serie_uid="1.2.3.4.5.OTRA", descripcion_serie="Otra serie con los mismos kV", numero_serie_equipo="9999")
    _archivar(bd_copia, 47, adq, equipo="Halcyon")
    _archivar(bd_copia, 47, otra, desviacion=None, tipos=[5])
    plano = re.sub(r"\s+", " ", _texto(_pdf(app, avisos, bd_copia, monkeypatch, SESION_47)))
    assert "distintas" in plano and "Adquisición 2" in plano
    assert "Otra serie con los mismos kV" in plano


def test_sin_divergencia_no_aparece_el_aviso(app, avisos, bd_copia, monkeypatch):
    _archivar(bd_copia, 47, _adq_real("HALCYON_SEP"), equipo="Halcyon")
    plano = re.sub(r"\s+", " ", _texto(_pdf(app, avisos, bd_copia, monkeypatch, SESION_47)))
    assert "distintas" not in plano and "Adquisición 1" not in plano


# ---------------------------------------------------------------------------
# 5. NINGUNA TABLA SE PIERDE, EN NINGÚN GENERADOR
# ---------------------------------------------------------------------------

def _tablas_reales(bd_copia, ref):
    return obtener_tablas_sistema_imagenes_para_pdf(Padre(bd_copia).opeenDatabase(), ref)


def test_las_claves_del_productor_estan_en_la_lista_del_generador(app, avisos, bd_copia):
    tablas = _tablas_reales(bd_copia, 42)
    assert "parametros_adquisicion" in tablas
    assert not [k for k in tablas if k.startswith("parametros_") and k != "parametros_adquisicion"]
    faltan = [k for k in tablas if k not in pdf_mod.TABLAS_INFORME_IMAGENES]
    assert faltan == [], f"el productor emite claves que el generador no conoce: {faltan}"
    assert pdf_mod.TABLAS_INFORME_IMAGENES[0] == "parametros_adquisicion"


def _encabezados(tablas):
    return {k: str(df.columns[0]) for k, df in tablas.items() if len(df.columns) and not df.empty}


@pytest.mark.parametrize("generador", ["mensual_tomografo", "anual_halcyon", "anual_ix"])
def test_ninguna_tabla_del_informe_se_pierde_en_el_generador(app, avisos, bd_copia, generador):
    tablas = _tablas_reales(bd_copia, 42)
    esperados = _encabezados(tablas)
    assert len(esperados) >= 15, "la sesión 42 (7 categorías) debe dar parámetros + 7 resultados + 7 imágenes"
    if generador == "mensual_tomografo":
        pdf = generar_reporte_pdf_multitabla_mensual(
            tablas=dict(tablas), fecha="07/2026", user="Físico", tipo_reporte="Control Sistema de Imágenes",
            maquina="Tomógrafo", id_maquina="Tomógrafo", sistema_imagenes=True, temp=True)
    else:
        maquina = "Halcyon" if generador == "anual_halcyon" else "Clinac ix"
        pdf = generar_reporte_pdf_multitabla_anual(
            tablas_dict={"titulo_sistema_imagenes": "Título de la sección", **tablas},
            fecha="2026", user="Físico", tipo_reporte="Anual", maquina=maquina, id_maquina=maquina,
            temp=True)
    datos = pdf.data() if hasattr(pdf, "data") else pdf
    texto = _texto(paginas(bytes(datos)))
    perdidas = [k for k, enc in esperados.items() if enc not in texto]
    assert perdidas == [], f"el generador descartó en silencio: {perdidas}"
    assert texto.count(TITULO_TABLA) == 1


# ---------------------------------------------------------------------------
# 6. PAGINACIÓN
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("archivar", [False, True], ids=["control_viejo", "control_con_metadata"])
def test_la_tabla_no_queda_partida_entre_paginas(app, avisos, bd_copia, monkeypatch, archivar):
    if archivar:
        _archivar(bd_copia, 47, _adq_real("HALCYON_JUN"), equipo="Halcyon")
    paginas_ = _pdf(app, avisos, bd_copia, monkeypatch, SESION_47)
    donde = [i for i, p in enumerate(paginas_) if TITULO_TABLA in p]
    assert len(donde) == 1
    ultima = "Frente al protocolo" if archivar else "Identidad y adquisición DICOM"
    assert ultima in re.sub(r"\s+", " ", paginas_[donde[0]]), "la última fila de la tabla quedó en otra página"
    # y no deja la primera página vacía: la tabla cabe donde empieza el informe
    assert donde[0] == 0, "la tabla no cupo en la primera página y pasó entera a la segunda"


# ---------------------------------------------------------------------------
# 7. UNA SOLA DEFINICIÓN de las filas
# ---------------------------------------------------------------------------

def _cadenas_de_produccion():
    for ruta in RAIZ.rglob("*.py"):
        rel = ruta.relative_to(RAIZ).as_posix()
        if rel.startswith(("tests/", ".venv/", "build/", "dist/")) or "/.venv/" in rel:
            continue
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                yield rel, nodo.value


@pytest.mark.parametrize("etiqueta", ["Número de serie del equipo", "Descripción de la serie", "Fecha de adquisición",
                                      "(no lo publica el equipo)"])
def test_las_etiquetas_de_la_metadata_se_escriben_en_un_solo_archivo(etiqueta):
    """La ventana de A.3 y el PDF de E.2 muestran la MISMA metadata: si cada uno escribiera sus
    etiquetas, podrían divergir."""
    sitios = sorted({rel for rel, texto in _cadenas_de_produccion() if texto == etiqueta})
    assert sitios == ["analisisImagenes/catphan/descripcion.py"], sitios
