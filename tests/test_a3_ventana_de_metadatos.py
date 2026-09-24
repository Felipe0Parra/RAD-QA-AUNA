"""A.3 (PLAN_HANDOFF_IMAGENES_22-09.md, reformulada el 23-09): una ventana de
metadatos en CADA carga de una carpeta DICOM.

CAUSA: al cargar una carpeta, nada le decía al físico de qué máquina era ni con
qué protocolo se adquirió; el aviso de carpeta mixta iba a `stdout`, que en
Windows nadie mira (la carpeta `Catphan` descarta 123 de 401 cortes en silencio
y el físico creía estar abriendo el iX con el tomógrafo).

Lo que este archivo garantiza:

  1. CONTENIDO -- las seis carpetas reales frente al equipo seleccionado: lo que
     dice el DICOM, lo que exige el protocolo y qué cumple; el banner de otro
     equipo; la carpeta mixta con sus dos modelos; lo que el iX no publica se
     dice, no se deja en blanco ni se escribe "None".
  2. DIALOGO -- los cuatro bloques y los dos botones; sin símbolos de
     correcto/incorrecto (DA-18).
  3. DECISION -- Cancelar no continúa; Continuar con una fila que no cumple pide
     una segunda confirmación explícita, que también puede negarse.
  4. ORDEN -- la ventana aparece ANTES de detectar módulos, de emitir
     `imagen_cargada` y del cuadro de cortes recomendados; Cancelar no deja nada
     cargado (un volumen anterior sigue siendo el activo) ni emite señal alguna.
  5. TRIPWIRES -- el orden es estructural (por AST), el equipo seleccionado llega
     al visualizador, y ningún texto lleva símbolos prohibidos.

Ningún test deja un `exec_()` modal sin contestar (Trampa 2 de CLAUDE.md): se
sustituyen `QDialog.exec_` y `QMessageBox.question`.
"""
import ast
import gc
import os
import pathlib
import types
import weakref

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QDialog, QGroupBox, QLabel, QMessageBox, QPushButton

from analisisImagenes.catphan.serie import adquisicion_de_serie, leer_serie
from data.ManejoDatos.catphan_TAC import leer_dicom as leer_dicom_mod
from data.ManejoDatos.catphan_TAC import ventana_metadatos as vm
from data.ManejoDatos.catphan_TAC.ventana_metadatos import (
    ATENCION, AVISO, CUMPLE, ERROR, INFO, NO_CUMPLE, NO_PUBLICADO, NO_SE_EXIGE, VentanaMetadatos,
    construir_modelo_ventana, mostrar_ventana_metadatos)
from _corpus import serie_catphan

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SIMBOLOS_PROHIBIDOS = "✓✗✔✘⚠❌✅☑☒"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return ruta


def _vol_de(clave):
    """Un objeto con lo que la ventana lee de un `DicomVolume`, armado desde
    los encabezados (sin cargar píxeles: la ventana solo usa metadatos)."""
    s = leer_serie(_requerir(clave))
    return types.SimpleNamespace(
        adquisicion=adquisicion_de_serie(s), series_descartadas=s.series_descartadas,
        detalle_series_descartadas=s.detalle_series_descartadas, no_imagen=s.no_imagen, avisos=s.avisos)


def _filas(modelo):
    return {f.etiqueta: f for f in modelo.protocolo}


# ---------------------------------------------------------------------------
# 1. CONTENIDO
# ---------------------------------------------------------------------------

def test_leer_serie_dice_de_que_modelo_es_la_serie_descartada():
    s = leer_serie(_requerir("MIXTA"))
    assert list(s.series_descartadas.values()) == [123]                # la forma de siempre, intacta
    (detalle,) = s.detalle_series_descartadas.values()
    assert detalle["n"] == 123
    assert detalle["modelo"] == "Halcyon - PVA" and detalle["estacion"] == "Halcyon"
    assert detalle["descripcion_serie"] == "Pelvis Fast_iCBCT_2.0"


def test_dicomvolume_expone_el_detalle_de_las_series_descartadas():
    """La ventana lee del `DicomVolume` REAL, no de `leer_serie`: el detalle tiene
    que llegar hasta ahí (carpeta mixta real: 278 cortes leídos, 123 descartados)."""
    ruta = _requerir("MIXTA")
    vol = leer_dicom_mod.DicomVolume(ruta)
    esperado = leer_serie(ruta)
    assert vol.detalle_series_descartadas == esperado.detalle_series_descartadas
    assert vol.series_descartadas == esperado.series_descartadas
    assert construir_modelo_ventana(vol, "Tomógrafo").carpeta[1:] == \
        construir_modelo_ventana(_vol_de("MIXTA"), "Tomógrafo").carpeta[1:]


def test_catphankv_con_halcyon_identidad_coincide_y_kv_no_cumple():
    """Ejemplo literal del plan: `CATPHANKV` con Halcyon -> identidad bien y kV
    140 fuera de protocolo."""
    m = construir_modelo_ventana(_vol_de("HALCYON_236"), "Halcyon")
    assert m.banner is None
    f = _filas(m)
    assert f["Modelo"].estado == CUMPLE and f["Estación"].estado == CUMPLE
    assert (f["kV"].estado, f["kV"].encontrado, f["kV"].exigido) == (NO_CUMPLE, "140", "125")
    assert m.requiere_confirmacion is True


def test_catphandiciembre_con_ix_todo_cumple_y_no_pide_confirmacion():
    m = construir_modelo_ventana(_vol_de("IX_DIC"), "Clinac ix")
    assert m.banner is None
    assert all(f.estado in (CUMPLE, NO_SE_EXIGE) for f in m.protocolo)
    assert m.requiere_confirmacion is False and m.resumen_desviacion is None


def test_catphankv_con_tomografo_es_otro_equipo_y_lo_dice_arriba_y_en_rojo():
    m = construir_modelo_ventana(_vol_de("HALCYON_236"), "Tomógrafo")
    nivel, texto = m.banner
    assert nivel == ERROR
    assert "Halcyon - PVA" in texto and "Tomógrafo" in texto
    assert m.requiere_confirmacion is True


def test_catphan_mixta_muestra_278_y_123_con_los_dos_modelos():
    m = construir_modelo_ventana(_vol_de("MIXTA"), "Tomógrafo")
    textos = [t for _n, t in m.carpeta]
    assert any("278" in t for t in textos)
    (mixta,) = [t for n, t in m.carpeta if n == ATENCION]
    assert "123" in mixta and "Halcyon - PVA" in mixta and "SOMATOM go.Sim" in mixta
    assert "equipos distintos" in mixta


@pytest.mark.parametrize("clave", ["TOMOGRAFO", "HALCYON_JUN", "HALCYON_SEP", "HALCYON_236", "IX_DIC"])
def test_las_cinco_carpetas_sin_mezcla_no_gritan(clave):
    """Un RTSTRUCT en la carpeta es normal: a lo sumo un aviso informativo."""
    m = construir_modelo_ventana(_vol_de(clave), "Halcyon")
    assert [n for n, _t in m.carpeta if n == ATENCION] == []


def test_un_rtstruct_es_informativo():
    m = construir_modelo_ventana(_vol_de("IX_DIC"), "Clinac ix")
    (nota,) = [t for n, t in m.carpeta if "no son imagen CT" in t]
    assert (INFO, nota) in m.carpeta


def test_lo_que_el_ix_no_publica_se_dice_no_se_deja_en_blanco_ni_se_escribe_none():
    m = construir_modelo_ventana(_vol_de("IX_DIC"), "Clinac ix")
    valores = dict(m.adquisicion)
    for etiqueta in ("Descripción de la serie", "CTDIvol [mGy]", "Filtro"):
        assert valores[etiqueta] == NO_PUBLICADO, etiqueta
    todo = [v for _k, v in m.identidad + m.adquisicion] + [f.encontrado for f in m.protocolo]
    assert "None" not in todo and "" not in todo


def test_equipo_sin_imagen_y_sin_equipo_se_advierten_sin_bloquear():
    vol = _vol_de("IX_DIC")
    m = construir_modelo_ventana(vol, "Clinac 600")
    assert m.banner[0] == AVISO and m.protocolo == [] and m.protocolo_nota
    assert m.requiere_confirmacion is False            # no hay ninguna fila que incumplir
    m = construir_modelo_ventana(vol, None)
    assert m.banner is None and "No hay un equipo seleccionado" in m.protocolo_nota


def test_equipo_no_reconocido_avisa():
    vol = _vol_de("HALCYON_SEP")
    vol.adquisicion = dict(vol.adquisicion, fabricante="Otro", modelo="Nuevo", estacion="X")
    m = construir_modelo_ventana(vol, "Halcyon")
    assert m.banner[0] == AVISO and "no se reconoce" in m.banner[1].lower()
    assert m.requiere_confirmacion is True


def test_misma_maquina_con_otra_estacion_advierte_y_pide_confirmacion():
    vol = _vol_de("TOMOGRAFO")
    vol.adquisicion = dict(vol.adquisicion, estacion="CT999999")
    m = construir_modelo_ventana(vol, "Tomógrafo")
    assert m.banner[0] == AVISO and "CT999999" in m.banner[1]
    assert m.requiere_confirmacion is True


def test_carpeta_con_otra_serie_del_mismo_equipo_es_atencion_sin_decir_equipos_distintos():
    vol = _vol_de("HALCYON_SEP")
    vol.series_descartadas = {"uid-x": 40}
    vol.detalle_series_descartadas = {"uid-x": {"n": 40, "modelo": "Halcyon - PVA", "estacion": "Halcyon",
                                                "descripcion_serie": "Pelvis Fast_iCBCT_2.0"}}
    m = construir_modelo_ventana(vol, "Halcyon")
    (aviso,) = [t for n, t in m.carpeta if n == ATENCION]
    assert "40" in aviso and "equipos distintos" not in aviso


def test_paso_no_uniforme_es_atencion():
    vol = _vol_de("TOMOGRAFO")
    vol.avisos = ["El paso entre cortes no es uniforme (mín=1.9 mm, máx=2.1 mm)"]
    m = construir_modelo_ventana(vol, "Tomógrafo")
    assert (ATENCION, vol.avisos[0]) in m.carpeta


# ---------------------------------------------------------------------------
# 2. DIALOGO
# ---------------------------------------------------------------------------

def test_el_dialogo_trae_los_cuatro_bloques_y_los_dos_botones(app):
    d = VentanaMetadatos(None, construir_modelo_ventana(_vol_de("HALCYON_SEP"), "Halcyon"))
    titulos = {c.title() for c in d.findChildren(QGroupBox)}
    assert titulos == {"Equipo (leído del DICOM)", "Adquisición", "Protocolo exigido para Halcyon", "La carpeta"}
    assert {b.text() for b in d.findChildren(QPushButton)} == {"Continuar", "Cancelar"}
    texto = d.texto_visible()
    assert "Pelvis_iCBCT_2.0_IQ!" in texto and "Halcyon - PVA" in texto and "Cumple" in texto


def test_el_dialogo_de_otro_equipo_lleva_el_banner_arriba(app):
    d = VentanaMetadatos(None, construir_modelo_ventana(_vol_de("HALCYON_236"), "Tomógrafo"))
    banner = d.findChild(QLabel, "banner")
    assert banner is not None and "usted seleccionó Tomógrafo" in banner.text()
    assert "c0392b" in banner.styleSheet()                      # rojo


def test_el_dialogo_sin_desviacion_no_lleva_banner(app):
    d = VentanaMetadatos(None, construir_modelo_ventana(_vol_de("HALCYON_SEP"), "Halcyon"))
    assert d.findChild(QLabel, "banner") is None


@pytest.mark.parametrize("clave,equipo", [("HALCYON_236", "Halcyon"), ("HALCYON_236", "Tomógrafo"),
                                          ("MIXTA", "Tomógrafo"), ("IX_DIC", "Clinac 600")])
def test_ningun_texto_visible_lleva_simbolos_de_correcto_o_incorrecto(app, clave, equipo):
    """DA-18. El plan decía ✓/✗; la regla vigente del físico manda: palabras y color."""
    d = VentanaMetadatos(None, construir_modelo_ventana(_vol_de(clave), equipo))
    assert not [c for c in d.texto_visible() if c in SIMBOLOS_PROHIBIDOS]


def test_el_modulo_no_contiene_simbolos_prohibidos_en_ninguna_cadena():
    arbol = ast.parse((RAIZ / "data/ManejoDatos/catphan_TAC/ventana_metadatos.py").read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            assert not [c for c in nodo.value if c in SIMBOLOS_PROHIBIDOS], nodo.value[:60]


# ---------------------------------------------------------------------------
# 3. DECISION
# ---------------------------------------------------------------------------

class _Espias:
    def __init__(self, monkeypatch, exec_devuelve, pregunta_devuelve=QMessageBox.Yes):
        self.preguntas = []
        monkeypatch.setattr(QDialog, "exec_", lambda self: exec_devuelve)
        monkeypatch.setattr(
            QMessageBox, "question",
            staticmethod(lambda parent, titulo, texto, *a, **k: (self.preguntas.append((titulo, texto)),
                                                                 pregunta_devuelve)[1]))


def test_cancelar_no_continua_ni_pregunta(app, monkeypatch):
    e = _Espias(monkeypatch, QDialog.Rejected)
    assert mostrar_ventana_metadatos(None, _vol_de("HALCYON_236"), "Halcyon") is False
    assert e.preguntas == []


def test_continuar_sin_filas_que_incumplan_no_pide_segunda_confirmacion(app, monkeypatch):
    e = _Espias(monkeypatch, QDialog.Accepted)
    assert mostrar_ventana_metadatos(None, _vol_de("HALCYON_SEP"), "Halcyon") is True
    assert e.preguntas == []


def test_continuar_con_una_fila_que_no_cumple_pide_confirmacion_y_se_puede_aceptar(app, monkeypatch):
    e = _Espias(monkeypatch, QDialog.Accepted, QMessageBox.Yes)
    assert mostrar_ventana_metadatos(None, _vol_de("HALCYON_236"), "Halcyon") is True
    (titulo, texto), = e.preguntas
    assert titulo == "Adquisición fuera de protocolo"
    assert "kV: 140 (exigido 125)" in texto and "no será comparable con la línea base" in texto


def test_la_segunda_confirmacion_tambien_se_puede_negar(app, monkeypatch):
    _Espias(monkeypatch, QDialog.Accepted, QMessageBox.No)
    assert mostrar_ventana_metadatos(None, _vol_de("HALCYON_236"), "Halcyon") is False


def test_otro_equipo_dice_como_se_guardaran_las_pruebas(app, monkeypatch):
    e = _Espias(monkeypatch, QDialog.Accepted, QMessageBox.Yes)
    mostrar_ventana_metadatos(None, _vol_de("HALCYON_236"), "Tomógrafo")
    assert "se guardarán como de 'Tomógrafo'" in e.preguntas[0][1]


# ---------------------------------------------------------------------------
# 4. ORDEN en el visualizador real (canvas real, como la app; carpeta real
#    pequeña: el iX, 70 cortes)
# ---------------------------------------------------------------------------

def _visualizador():
    from resources.utils.matplotlib_lazy import get_matplotlib_components
    mpl = get_matplotlib_components()
    canvas = mpl["FigureCanvas"](mpl["Figure"](figsize=(4, 4)))
    return leer_dicom_mod.VisualizadorDicom(target_canvas=canvas)


@pytest.fixture
def visualizador(app, monkeypatch):
    """Un visualizador con la detección de módulos y el cuadro de cortes
    SUSTITUIDOS por espías (el orden es lo que se prueba; pylinac ya tiene sus
    propias pruebas) y un registro de eventos."""
    eventos = []
    monkeypatch.setattr(leer_dicom_mod, "detectar_y_resolver_modulos",
                        lambda ruta_dicom: (eventos.append("detectar"), ({}, {}))[1])
    v = _visualizador()
    monkeypatch.setattr(v, "mostrar_popup_cortes", lambda resultados: eventos.append("popup"))
    v.imagen_cargada.connect(lambda _vol: eventos.append("emitida"))
    v.eventos = eventos
    return v


def test_la_ventana_aparece_antes_de_detectar_emitir_y_mostrar_los_cortes(visualizador):
    ruta = _requerir("IX_DIC")
    recibido = {}

    def confirmador(parent, vol, equipo):
        visualizador.eventos.append("confirmar")
        recibido.update(vol=vol, equipo=equipo, hay_vol_activo=visualizador.vol is not None)
        return True

    visualizador.confirmador_de_carga = confirmador
    visualizador.equipo_seleccionado = "Clinac ix"
    visualizador.visualizar_imagen_cargada(ruta)

    assert visualizador.eventos == ["confirmar", "detectar", "emitida", "popup"]
    assert recibido["equipo"] == "Clinac ix"                      # el equipo seleccionado llega a la ventana
    assert recibido["vol"].adquisicion["modelo"] == "OBI Cone-beam CT"
    assert recibido["hay_vol_activo"] is False                    # todavía no es el volumen activo
    assert visualizador.vol is recibido["vol"]                    # y lo es después de Continuar


def test_cancelar_no_carga_nada_ni_emite_ni_detecta(visualizador):
    ruta = _requerir("IX_DIC")
    visualizador.confirmador_de_carga = lambda parent, vol, equipo: (visualizador.eventos.append("confirmar"), False)[1]
    visualizador.visualizar_imagen_cargada(ruta)

    assert visualizador.eventos == ["confirmar"]                  # ni detectar, ni emitir, ni cortes
    assert visualizador.vol is None
    assert visualizador.ruta_carpeta is None
    assert not visualizador.sel_imagen_btn.isHidden()            # el botón de cargar sigue disponible


def test_cancelar_una_segunda_carga_deja_el_volumen_anterior_y_libera_el_rechazado(visualizador):
    ruta = _requerir("IX_DIC")
    visualizador.confirmador_de_carga = lambda parent, vol, equipo: True
    visualizador.visualizar_imagen_cargada(ruta)
    anterior = visualizador.vol
    visualizador.eventos.clear()

    rechazado = {}

    def rechaza(parent, vol, equipo):
        rechazado["ref"] = weakref.ref(vol)
        return False

    visualizador.confirmador_de_carga = rechaza
    visualizador.visualizar_imagen_cargada(ruta)
    gc.collect()

    assert visualizador.vol is anterior                           # nada cambió
    assert visualizador.ruta_carpeta == anterior.ruta_carpeta
    assert visualizador.eventos == []                             # ni detección ni señal
    assert rechazado["ref"]() is None, "el volumen rechazado debe liberarse (C.2)"


def test_por_defecto_el_visualizador_usa_la_ventana_real():
    assert leer_dicom_mod.VisualizadorDicom.confirmador_de_carga is mostrar_ventana_metadatos
    assert leer_dicom_mod.VisualizadorDicom.equipo_seleccionado is None


def test_camino_completo_con_la_ventana_real_y_exec_sustituido(visualizador, monkeypatch):
    """El camino de produccion (sin sustituir `confirmador_de_carga`): la
    ventana real se construye con el volumen real, y Continuar carga."""
    ruta = _requerir("IX_DIC")
    _Espias(monkeypatch, QDialog.Accepted)
    visualizador.equipo_seleccionado = "Clinac ix"
    visualizador.visualizar_imagen_cargada(ruta)
    assert visualizador.vol is not None and visualizador.eventos == ["detectar", "emitida", "popup"]


# ---------------------------------------------------------------------------
# 5. TRIPWIRES
# ---------------------------------------------------------------------------

def _linea_de_llamada(func, nombre_atributo):
    """Primera línea (en la función) de una llamada `self.<nombre>(...)` o `<nombre>(...)`."""
    lineas = []
    for n in ast.walk(func):
        if isinstance(n, ast.Call):
            f = n.func
            if (isinstance(f, ast.Attribute) and f.attr == nombre_atributo) or \
               (isinstance(f, ast.Name) and f.id == nombre_atributo):
                lineas.append(n.lineno)
    return min(lineas) if lineas else None


def test_el_orden_es_estructural_la_confirmacion_precede_a_todo():
    arbol = ast.parse((RAIZ / "data/ManejoDatos/catphan_TAC/leer_dicom.py").read_text(encoding="utf-8"))
    (func,) = [n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "visualizar_imagen_cargada"]
    confirmar = _linea_de_llamada(func, "confirmador_de_carga")
    assert confirmar is not None
    for despues in ("detectar_y_resolver_modulos", "emit", "mostrar_popup_cortes", "actualizar_ventana"):
        assert confirmar < _linea_de_llamada(func, despues), despues
    # `self.vol = vol_nuevo`: la ÚNICA asignación anterior a la confirmación es la
    # rama de FALLO de carga (`volumen_hu is None`, comportamiento de siempre);
    # la activación real va después.
    padres = {hijo: padre for padre in ast.walk(func) for hijo in ast.iter_child_nodes(padre)}
    asignaciones = [n for n in ast.walk(func)
                    if isinstance(n, ast.Assign) and isinstance(n.value, ast.Name) and n.value.id == "vol_nuevo"
                    and any(isinstance(t, ast.Attribute) and t.attr == "vol" for t in n.targets)]
    assert asignaciones, "no se encontro la activacion del volumen"
    for a in asignaciones:
        if a.lineno < confirmar:
            ancestro, en_rama_de_error = padres.get(a), False
            while ancestro is not None and ancestro is not func:
                if isinstance(ancestro, ast.If) and "volumen_hu" in ast.dump(ancestro.test):
                    en_rama_de_error = True
                ancestro = padres.get(ancestro)
            assert en_rama_de_error, f"linea {a.lineno}: el volumen pasa a ser el activo antes de confirmar"
    assert max(a.lineno for a in asignaciones) > confirmar, "falta la activacion posterior a la confirmacion"


def test_la_pantalla_pasa_su_equipo_al_visualizador_principal():
    arbol = ast.parse((RAIZ / "ui/paginasControles/PruebasMensuales/tac_mensual.py").read_text(encoding="utf-8"))
    (func,) = [n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "imagenUpLoader"]
    asignaciones = [n for n in ast.walk(func) if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Attribute) and t.attr == "equipo_seleccionado"
                            and isinstance(t.value, ast.Attribute) and t.value.attr == "visualizador_principal"
                            for t in n.targets)]
    assert len(asignaciones) == 1
    assert "equipo_f" in ast.dump(asignaciones[0].value)


def test_solo_un_sitio_de_produccion_construye_un_visualizador_que_carga():
    """Si otro archivo instanciara `VisualizadorDicom` y cargara carpetas, tendría
    que recibir también el equipo seleccionado: hoy solo lo hace `tac_mensual`."""
    duenos = set()
    for ruta in RAIZ.rglob("*.py"):
        rel = ruta.relative_to(RAIZ).as_posix()
        if rel.startswith(("tests/", ".venv/", "build/", "dist/")):
            continue
        for n in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", None)) == "VisualizadorDicom":
                duenos.add(rel)
    assert duenos == {"ui/paginasControles/PruebasMensuales/tac_mensual.py"}, duenos
