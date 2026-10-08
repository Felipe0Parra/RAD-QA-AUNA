"""CD.2 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, B3): el aviso de pylinac dice la causa real.

Antes `motor.analizar` tragaba la excepcion de pylinac (`except Exception: r = None`) y, si ninguna orientacion servia, la sustituia por «Ninguna orientacion del fantoma en '<ruta>'
correlaciona con los HU nominales (normal: r=None, invertido: r=None...)», que el cuadro de cortes cortaba a 50 caracteres: «Ninguna orientacion del fantoma en '/tmp/claude-10». V2 midio que
sin `SliceThickness` pylinac lanza `AttributeError` y el fisico veia ESO en los cuatro modulos: recolocaba un fantoma por un dato que faltaba en el DICOM.

Ahora el aviso nombra la causa primero («pylinac no pudo analizar la serie: falta el espesor de corte (SliceThickness) en el DICOM»), no habla de orientacion si el fallo fue del analisis, no lleva
la ruta y el cuadro de cortes lo dice COMPLETO, una vez por motivo. El tipo `OrientacionIndeterminada` se conserva (lo fijan `test_b1_motor_referencias_de_oro` y `test_b2_orientacion_automatica`).

Revision de la tarea (dos revisores escepticos, hallazgos reproducidos): el espesor presente pero VACIO (pylinac lanza `TypeError`, no `AttributeError`) tambien se dice; el barrido incompleto se
traduce; ninguna causa termina en «..»; cuando un intento falla y el otro analiza ya no se afirma que la orientacion que nunca se midio «no correlaciona»; una correlacion que llega al umbral
pero cuyo centro de CTP486 es aire lo dice; la advertencia del intento normal ya no dice `r=None`; el cuadro de cortes abre con la altura que el motivo necesita y parte las palabras largas; y
`analizar()` se prueba con resultados ASIMETRICOS (un intento analiza y el otro lanza), que las series reales del corpus no dan.

Sobre el rojo contra el codigo anterior: las pruebas de las dos funciones puras importan nombres que el codigo anterior no tiene (`descripcion_del_fallo`, `_mensaje_sin_orientacion`) y caen por
`ImportError`; las de comportamiento (`motor.analizar` y `detectar_modulos_pylinac` sobre series reales, el cuadro de cortes) usan solo API que ya existia y caen por su aserción.
"""
import ast
import gc
import os
import types
import warnings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pydicom
import pytest
from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtWidgets import QApplication, QDialog, QLabel

from _corpus import serie_catphan
from _formularios_imagenes import app  # noqa: F401  (fixture)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAUSA_ESPESOR = "falta el espesor de corte (SliceThickness) en el DICOM"


@pytest.fixture(autouse=True)
def _hay_qapplication(app):
    """Las pruebas del cuadro de cortes construyen widgets: la QApplication tiene que existir antes (Trampa 1)."""
    return app


def _requerir(clave):
    ruta = serie_catphan(clave)
    if ruta is None:
        pytest.skip(f"corpus Catphan no disponible: {clave}")
    return ruta


# ---------------------------------------------------------------------------------------------------- las funciones puras
class TestLaCausaDichaParaUnaPersona:

    def test_el_espesor_que_falta(self):
        from analisisImagenes.catphan.motor import descripcion_del_fallo
        assert descripcion_del_fallo(AttributeError("'FileDataset' object has no attribute 'SliceThickness'")) == CAUSA_ESPESOR

    def test_ningun_corte_se_parece_a_ctp404(self):
        from analisisImagenes.catphan.motor import descripcion_del_fallo
        d = descripcion_del_fallo(ValueError("No slices were found that resembled the HU linearity module"))
        assert "CTP404" in d and "linealidad" in d and "No slices" not in d

    def test_el_espesor_presente_pero_vacio_tambien_se_dice(self):
        """Con la etiqueta VACIA pylinac la multiplica y lanza `TypeError` (no `AttributeError`): la causa es la misma y se reconoce por el dato (la serie no publica espesor)."""
        from analisisImagenes.catphan.motor import descripcion_del_fallo
        e = TypeError("unsupported operand type(s) for *: 'NoneType' and 'int'")
        assert descripcion_del_fallo(e, types.SimpleNamespace(espesor_mm=None)) == CAUSA_ESPESOR

    def test_el_mismo_typeerror_con_una_serie_que_si_publica_espesor_o_sin_serie_no_se_traduce(self):
        from analisisImagenes.catphan.motor import descripcion_del_fallo
        e = TypeError("unsupported operand type(s) for *: 'NoneType' and 'int'")
        for serie in (types.SimpleNamespace(espesor_mm=2.0), None, types.SimpleNamespace()):
            d = descripcion_del_fallo(e, serie)
            assert d.startswith("TypeError: ") and "espesor" not in d, (serie, d)
        otro = TypeError("expected non-empty vector for x")
        assert descripcion_del_fallo(otro, types.SimpleNamespace(espesor_mm=None)).startswith("TypeError: expected non-empty vector"), "un TypeError que no habla de NoneType no es el espesor"

    def test_solo_un_atributo_que_falta_es_un_espesor_que_falta(self):
        """Contrato: un error que nombra `SliceThickness` pero NO es un atributo ausente (otra cosa del espesor) no se dice «falta»."""
        from analisisImagenes.catphan.motor import descripcion_del_fallo
        d = descripcion_del_fallo(ValueError("SliceThickness is inconsistent between slices"))
        assert d.startswith("ValueError: ") and "falta" not in d

    def test_el_barrido_que_no_cubre_los_modulos_se_dice_en_castellano(self):
        from analisisImagenes.catphan.motor import descripcion_del_fallo
        d = descripcion_del_fallo(ValueError("The physical scan extent does not match the module configuration. Rescan the phantom to include allrelevant modules, or remove modules from the analysis."))
        assert "barrido" in d and "no cubre" in d and "volver a escanear" in d
        assert "Rescan" not in d and "allrelevant" not in d and "physical scan extent" not in d

    def test_un_atributo_que_falta_pero_no_es_el_espesor_no_se_confunde(self):
        from analisisImagenes.catphan.motor import descripcion_del_fallo
        d = descripcion_del_fallo(AttributeError("'FileDataset' object has no attribute 'PixelSpacing'"))
        assert d.startswith("AttributeError: ") and "PixelSpacing" in d and "espesor" not in d

    def test_lo_desconocido_dice_su_clase_y_su_texto_en_una_sola_linea(self):
        from analisisImagenes.catphan.motor import descripcion_del_fallo
        assert descripcion_del_fallo(RuntimeError("algo\n   raro  paso")) == "RuntimeError: algo raro paso"

    def test_una_excepcion_sin_texto_dice_al_menos_su_clase(self):
        from analisisImagenes.catphan.motor import descripcion_del_fallo
        assert descripcion_del_fallo(KeyError()) == "KeyError"


class TestElTextoDeOrientacionIndeterminada:

    def test_si_pylinac_no_pudo_analizar_ni_derecha_ni_volteada_la_causa_va_primero_y_no_se_habla_de_orientacion(self):
        from analisisImagenes.catphan.motor import _mensaje_sin_orientacion
        e = AttributeError("'FileDataset' object has no attribute 'SliceThickness'")
        m = _mensaje_sin_orientacion(None, None, e, e)
        assert m == f"pylinac no pudo analizar la serie: {CAUSA_ESPESOR}."
        assert "orientación" not in m and "r=" not in m and "None" not in m

    def test_si_las_dos_causas_difieren_se_dicen_las_dos(self):
        from analisisImagenes.catphan.motor import _mensaje_sin_orientacion
        m = _mensaje_sin_orientacion(None, None, AttributeError("no attribute 'SliceThickness'"), ValueError("No slices were found that resembled the HU linearity module"))
        assert m.startswith(f"pylinac no pudo analizar la serie: {CAUSA_ESPESOR} (al voltearla: ") and "CTP404" in m

    def test_si_un_intento_analizo_se_dice_su_correlacion_y_la_causa_del_otro(self):
        from analisisImagenes.catphan.motor import UMBRAL_CORRELACION_ORIENTACION, _mensaje_sin_orientacion
        m = _mensaje_sin_orientacion(0.123456, None, None, RuntimeError("boom"))
        assert "normal: r=0.123" in m and "invertido: no se pudo analizar: RuntimeError: boom" in m and f"umbral={UMBRAL_CORRELACION_ORIENTACION}" in m
        assert "None" not in m

    def test_si_un_intento_fallo_no_se_afirma_que_su_orientacion_no_correlaciona(self):
        """Revision (R-06): la orientacion cuyo analisis lanzo nunca se midio; el texto no puede abrir diciendo que «ninguna correlaciona»."""
        from analisisImagenes.catphan.motor import _mensaje_sin_orientacion
        for m in (_mensaje_sin_orientacion(0.3, None, None, RuntimeError("boom")), _mensaje_sin_orientacion(None, 0.3, RuntimeError("boom"), None)):
            assert m.startswith("No se pudo determinar la orientación del fantoma (") and "Ninguna orientación" not in m, m

    def test_una_correlacion_que_llega_al_umbral_pero_con_el_centro_de_ctp486_en_aire_lo_dice(self):
        """Revision (H7): con r por encima del umbral el aviso no puede decir «no correlaciona»; lo que fallo es el control del centro de CTP486."""
        from analisisImagenes.catphan.motor import _mensaje_sin_orientacion
        m = _mensaje_sin_orientacion(0.99, 0.2, None, None, None, -950.0, 100.0)
        assert m == ("No se pudo determinar la orientación del fantoma (normal: r=0.990, pero el centro de CTP486 mide -950 HU (aire: ese corte no es el módulo de uniformidad); "
                     "invertido: r=0.200; umbral=0.95).")
        assert "Ninguna orientación" not in m

    def test_ninguna_causa_termina_en_doble_punto(self):
        """Revision (R-03): una causa que ya termina en punto (el texto de pylinac) no lleva el punto final del mensaje encima."""
        from analisisImagenes.catphan.motor import _mensaje_sin_orientacion
        e = ValueError("el barrido es corto.")
        for m in (_mensaje_sin_orientacion(None, None, e, e), _mensaje_sin_orientacion(None, None, e, ValueError("otra cosa.")), _mensaje_sin_orientacion(0.3, None, None, e)):
            assert ".." not in m and ". ." not in m and m.endswith(".") and not m.endswith(".."), m

    def test_si_los_dos_analizaron_pero_ninguno_correlaciona_es_el_texto_de_siempre_con_numeros_legibles(self):
        from analisisImagenes.catphan.motor import _mensaje_sin_orientacion
        m = _mensaje_sin_orientacion(0.1, 0.2, None, None)
        assert m.startswith("Ninguna orientación del fantoma correlaciona con los HU nominales (normal: r=0.100; invertido: r=0.200;")

    def test_el_mensaje_no_lleva_ruta_de_carpeta(self):
        from analisisImagenes.catphan.motor import _mensaje_sin_orientacion
        for m in (_mensaje_sin_orientacion(None, None, ValueError("x"), ValueError("x")), _mensaje_sin_orientacion(0.1, 0.2, None, None)):
            assert "/" not in m and "\\" not in m and "'" not in m


# ---------------------------------------------------------------------------------------------------- analizar() con resultados ASIMETRICOS
class _CTFalso:
    def __init__(self, etiqueta):
        self.etiqueta = etiqueta
        self.dicom_stack = types.SimpleNamespace(metadatas=[types.SimpleNamespace(SOPInstanceUID="u1")])


ESPESOR_AUSENTE = AttributeError("'FileDataset' object has no attribute 'SliceThickness'")
SIN_CTP404 = ValueError("No slices were found that resembled the HU linearity module")
CAUSA_CTP404 = "pylinac no encontró ningún corte parecido al módulo de linealidad de HU (CTP404)"


def _analizar_con_piezas_falsas(monkeypatch, normal, volteado, espesor_mm=2.0):
    """Corre `motor.analizar` con pylinac sustituido: `normal` y `volteado` son una excepcion (ese intento lanza) o `(r, centro_de_CTP486)` (ese intento analiza). Las series reales del corpus
    solo dan resultados SIMETRICOS (los dos intentos fallan igual): nada distinguiria que se crucen los argumentos de `_mensaje_sin_orientacion`. Devuelve lo que `analizar` devuelve o lanza."""
    from analisisImagenes.catphan import motor
    construidos = []

    def construir(rutas, limite):
        construidos.append(1)
        return _CTFalso("normal" if len(construidos) == 1 else "volteado")

    def resultado(ct):
        return normal if ct.etiqueta == "normal" else volteado

    def una_vez(ct, origen, ajustes):
        r = resultado(ct)
        if isinstance(r, Exception):
            raise r

    monkeypatch.setattr(motor, "_construir", construir)
    monkeypatch.setattr(motor, "_voltear_volumen", lambda ct: None)
    monkeypatch.setattr(motor, "_analizar_una_vez", una_vez)
    monkeypatch.setattr(motor, "_correlacion_y_centro", resultado)
    monkeypatch.setattr(motor, "_resultado_desde_ct", lambda ct, equipo, orientacion, advertencias: (orientacion, advertencias))
    serie = types.SimpleNamespace(carpeta="/ruta/serie", espesor_mm=espesor_mm, cortes=[types.SimpleNamespace(ruta="a.dcm", sop_uid="u1")])
    return motor.analizar(serie, types.SimpleNamespace(limite_variacion_hu=None, nombre="X"))


class TestAnalizarArmaElTextoConLosDatosDeCadaIntento:

    def _lanza(self, monkeypatch, normal, volteado, **k):
        from analisisImagenes.catphan.motor import OrientacionIndeterminada
        with pytest.raises(OrientacionIndeterminada) as e:
            _analizar_con_piezas_falsas(monkeypatch, normal, volteado, **k)
        return str(e.value)

    def test_causas_distintas_la_del_intento_normal_va_primero(self, monkeypatch):
        assert self._lanza(monkeypatch, ESPESOR_AUSENTE, SIN_CTP404) == f"pylinac no pudo analizar la serie: {CAUSA_ESPESOR} (al voltearla: {CAUSA_CTP404})."

    def test_el_normal_analiza_y_el_volteado_lanza(self, monkeypatch):
        assert self._lanza(monkeypatch, (0.30, 100.0), RuntimeError("boom")) == (
            "No se pudo determinar la orientación del fantoma (normal: r=0.300; invertido: no se pudo analizar: RuntimeError: boom; umbral=0.95).")

    def test_el_normal_lanza_y_el_volteado_analiza_sin_llegar_al_umbral(self, monkeypatch):
        assert self._lanza(monkeypatch, ESPESOR_AUSENTE, (0.40, 100.0)) == (
            f"No se pudo determinar la orientación del fantoma (normal: no se pudo analizar: {CAUSA_ESPESOR}; invertido: r=0.400; umbral=0.95).")

    def test_los_dos_analizan_y_ninguno_correlaciona_cada_numero_en_su_sitio(self, monkeypatch):
        assert self._lanza(monkeypatch, (0.30, 100.0), (0.40, 100.0)) == (
            "Ninguna orientación del fantoma correlaciona con los HU nominales (normal: r=0.300; invertido: r=0.400; umbral=0.95).")

    def test_la_correlacion_alcanza_el_umbral_pero_el_centro_es_aire(self, monkeypatch):
        assert self._lanza(monkeypatch, (0.99, -950.0), (0.20, 100.0)) == (
            "No se pudo determinar la orientación del fantoma (normal: r=0.990, pero el centro de CTP486 mide -950 HU (aire: ese corte no es el módulo de uniformidad); "
            "invertido: r=0.200; umbral=0.95).")
        assert self._lanza(monkeypatch, (0.20, 100.0), (0.98, -980.0)) == (
            "No se pudo determinar la orientación del fantoma (normal: r=0.200; invertido: r=0.980, pero el centro de CTP486 mide -980 HU (aire: ese corte no es el módulo de uniformidad); "
            "umbral=0.95).")

    def test_el_espesor_vacio_se_reconoce_por_la_serie_que_analizar_pasa(self, monkeypatch):
        """Los dos intentos lanzan el `TypeError` de pylinac y la serie que `analizar` recibio no publica espesor."""
        e = TypeError("unsupported operand type(s) for *: 'NoneType' and 'int'")
        assert self._lanza(monkeypatch, e, e, espesor_mm=None) == f"pylinac no pudo analizar la serie: {CAUSA_ESPESOR}."
        assert "falta" not in self._lanza(monkeypatch, e, e, espesor_mm=2.0)

    def test_si_el_volteado_sirve_la_advertencia_del_normal_dice_su_causa_y_no_r_none(self, monkeypatch):
        orientacion, advertencias = _analizar_con_piezas_falsas(monkeypatch, ESPESOR_AUSENTE, (0.99, 100.0))
        assert orientacion == "invertido"
        assert advertencias[0] == f"orientación normal: no se pudo analizar: {CAUSA_ESPESOR}"
        assert advertencias[1] == "correlación orientación invertida: r=0.990"
        assert not any("None" in a for a in advertencias), advertencias

    def test_si_el_volteado_sirve_con_el_normal_analizado_la_advertencia_no_cambia(self, monkeypatch):
        """Camino bueno: el formato de la correlacion del normal (sin redondear) es el de siempre."""
        orientacion, advertencias = _analizar_con_piezas_falsas(monkeypatch, (0.2662381, 100.0), (0.99, 100.0))
        assert orientacion == "invertido" and advertencias[0] == "correlación orientación normal: r=0.2662381"

    def test_se_conserva_el_tipo_de_la_excepcion(self, monkeypatch):
        from analisisImagenes.catphan.motor import OrientacionIndeterminada
        assert issubclass(OrientacionIndeterminada, Exception)
        for normal, volteado in ((ESPESOR_AUSENTE, SIN_CTP404), ((0.3, 1.0), RuntimeError("x")), ((0.3, 1.0), (0.4, 1.0))):
            with pytest.raises(OrientacionIndeterminada):
                _analizar_con_piezas_falsas(monkeypatch, normal, volteado)


# ---------------------------------------------------------------------------------------------------- series reales
def _serie_con_espesor(tmp_path_factory, origen, nombre, como):
    destino = tmp_path_factory.mktemp(nombre)
    for archivo in sorted(os.listdir(origen)):
        ds = pydicom.dcmread(os.path.join(origen, archivo))
        if como == "ausente":
            if "SliceThickness" in ds:
                del ds["SliceThickness"]
        else:
            ds.SliceThickness = None                   # la etiqueta presente pero VACIA (el caso del topograma real del hospital, DP-149)
        ds.save_as(os.path.join(str(destino), archivo))
    return str(destino)


@pytest.fixture(scope="module", params=["ausente", "vacio"])
def serie_sin_espesor(request, tmp_path_factory):
    """El tomografo real con `SliceThickness` quitado (o dejado VACIO) de TODOS sus cortes (el caso del revisor V2)."""
    return _serie_con_espesor(tmp_path_factory, _requerir("TOMOGRAFO"), f"sin_espesor_{request.param}", request.param)


class TestConSeriesReales:

    def test_sin_espesor_el_motor_dice_que_falta_el_espesor(self, serie_sin_espesor):
        from analisisImagenes.catphan import motor
        from analisisImagenes.catphan.serie import leer_serie
        perfil = types.SimpleNamespace(limite_variacion_hu=None, nombre="TOMOGRAFO")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with pytest.raises(motor.OrientacionIndeterminada) as e:
                motor.analizar(leer_serie(serie_sin_espesor), perfil)
        texto = str(e.value)
        assert CAUSA_ESPESOR in texto, texto
        assert "Ninguna orientación" not in texto and "r=None" not in texto and serie_sin_espesor not in texto, texto

    def test_la_deteccion_de_modulos_entrega_la_causa_en_los_cuatro_modulos(self, serie_sin_espesor):
        from data.ManejoDatos.catphan_TAC.slice_matcher import detectar_modulos_pylinac
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            resultados = detectar_modulos_pylinac(serie_sin_espesor)
        assert sorted(resultados) == ["CTP404", "CTP486", "CTP515", "CTP528"]
        for nombre, r in resultados.items():
            assert not r.confiable and r.idx_corte is None, nombre
            assert CAUSA_ESPESOR in (r.error or ""), (nombre, r.error)

    def test_el_ix_sin_el_limite_de_homogeneidad_dice_que_ningun_corte_se_parece_a_ctp404(self):
        from analisisImagenes.catphan import motor
        from analisisImagenes.catphan.serie import leer_serie
        ruta = _requerir("IX_DIC")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with pytest.raises(motor.OrientacionIndeterminada) as e:
                motor.analizar(leer_serie(ruta), types.SimpleNamespace(limite_variacion_hu=None, nombre="IX_DIC"))
        texto = str(e.value)
        assert "módulo de linealidad de HU (CTP404)" in texto and "No slices were found" not in texto and ruta not in texto, texto


# ---------------------------------------------------------------------------------------------------- el cuadro de cortes
def _visualizador():
    import data.ManejoDatos.catphan_TAC.leer_dicom as leer
    from resources.utils.matplotlib_lazy import get_matplotlib_components
    mpl = get_matplotlib_components()
    return leer.VisualizadorDicom(target_canvas=mpl["FigureCanvas"](mpl["Figure"](figsize=(4, 4))))


def _textos_del_cuadro(visualizador):
    dialogos = visualizador.findChildren(QDialog)
    assert len(dialogos) == 1, dialogos
    return dialogos[0], [l.text() for l in dialogos[0].findChildren(QLabel)]


def _dialogos_vivos():
    return [w for w in QApplication.allWidgets() if isinstance(w, QDialog)]


@pytest.fixture
def visor():
    """Un visor y, al terminar la prueba (pase o falle), la receta de cierre de la Trampa 9: `hide(); close(); deleteLater()`, entregar los borrados diferidos, procesar eventos, `gc.collect()`; y
    comprueba que no queda ningun cuadro de dialogo vivo (antes cada prueba dejaba uno con ~25 widgets)."""
    antes = len(_dialogos_vivos())
    v = _visualizador()
    yield v
    for d in v.findChildren(QDialog):
        d.hide()
        d.close()
        d.deleteLater()
    v.hide()
    v.close()
    v.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()
    assert len(_dialogos_vivos()) <= antes, "la prueba dejo cuadros de dialogo vivos (Trampa 9)"


def _modulo(nombre, idx=None, error=None):
    from data.ManejoDatos.catphan_TAC.slice_matcher import DESCRIPCION_MODULOS, ResultadoModulo
    return ResultadoModulo(nombre=nombre, descripcion=DESCRIPCION_MODULOS[nombre], idx_corte=idx, confiable=idx is not None, error=error)


MODULOS = ("CTP404", "CTP486", "CTP515", "CTP528")
MOTIVO_255 = ("pylinac no pudo analizar la serie: el barrido no cubre todos los módulos del fantoma (la extensión física del barrido no coincide con la configuración de los módulos): "
              "hay que volver a escanear el fantoma completo, con los cuatro módulos dentro del campo de visión y todos los cortes de la serie, sin quitar ninguno antes de cargar la carpeta.")
MOTIVO_400 = MOTIVO_255 + " " + MOTIVO_255[:150]
MOTIVO_CON_RUTA_LARGA = ("no se pudo leer " + "/home/usuario/Documentos/Controles/Catphan/serie_de_septiembre/cortes_del_tomografo/de_la_unidad_de_red_del_servicio/"
                         "carpeta_de_trabajo_del_fisico_medico/corte_0001_de_0102.dcm" + " del disco")


class TestElCuadroDeCortesDiceElMotivoCompleto:

    def test_un_motivo_largo_sale_entero_una_sola_vez_con_los_modulos_que_aplica(self, visor):
        motivo = f"pylinac no pudo analizar la serie: {CAUSA_ESPESOR} y ademas esta frase es larga a proposito para pasar de los 50 caracteres de antes."
        assert len(motivo) > 120
        visor.mostrar_popup_cortes({n: _modulo(n, error=motivo) for n in MODULOS})
        dialogo, textos = _textos_del_cuadro(visor)
        con_motivo = [t for t in textos if motivo in t]
        assert len(con_motivo) == 1, "el motivo se dice una vez, entero"
        assert "CTP404, CTP486, CTP515, CTP528" in con_motivo[0]
        etiqueta = next(l for l in dialogo.findChildren(QLabel) if motivo in l.text())
        assert etiqueta.wordWrap(), "un motivo largo se ajusta a la anchura del cuadro y no se sale de el"
        assert etiqueta.textFormat() == Qt.RichText, "sin texto enriquecido el cuadro mostraria las etiquetas <small><b> literales"
        assert sum("No detectado" in t for t in textos) == 4
        assert not any(motivo[:50] in t and motivo not in t for t in textos), "ningun texto lleva el motivo cortado"

    def test_motivos_distintos_salen_cada_uno_con_su_modulo(self, visor):
        visor.mostrar_popup_cortes({"CTP404": _modulo("CTP404", idx=10), "CTP486": _modulo("CTP486", error="motivo A"), "CTP515": _modulo("CTP515", error="motivo B"),
                                    "CTP528": _modulo("CTP528", error="motivo A")})
        dialogo, textos = _textos_del_cuadro(visor)
        a = [t for t in textos if "motivo A" in t]
        b = [t for t in textos if "motivo B" in t]
        assert len(a) == 1 and "CTP486, CTP528" in a[0] and len(b) == 1 and "CTP515" in b[0] and "CTP486" not in b[0]
        assert sum("No detectado" in t for t in textos) == 3 and any("Corte <b>11" in t for t in textos)

    def test_los_motivos_salen_en_el_orden_en_que_aparecen_los_modulos(self, visor):
        visor.mostrar_popup_cortes({"CTP404": _modulo("CTP404", error="motivo A"), "CTP486": _modulo("CTP486", error="motivo B"), "CTP515": _modulo("CTP515", error="motivo C"),
                                    "CTP528": _modulo("CTP528", error="motivo A")})
        dialogo, textos = _textos_del_cuadro(visor)
        motivos = [next(m for m in ("motivo A", "motivo B", "motivo C") if m in t) for t in textos if "<small><b>CTP" in t]
        assert motivos == ["motivo A", "motivo B", "motivo C"], motivos

    def test_el_motivo_es_texto_no_html(self, visor):
        visor.mostrar_popup_cortes({"CTP404": _modulo("CTP404", error="<b>negrita</b> & mas")})
        dialogo, textos = _textos_del_cuadro(visor)
        assert any("&lt;b&gt;negrita&lt;/b&gt; &amp; mas" in t for t in textos), textos

    def test_sin_modulos_fallidos_no_hay_lineas_de_motivo(self, visor):
        visor.mostrar_popup_cortes({n: _modulo(n, idx=3) for n in ("CTP404", "CTP486")})
        dialogo, textos = _textos_del_cuadro(visor)
        assert not any("No detectado" in t for t in textos) and not any("<small><b>CTP" in t for t in textos)

    @pytest.mark.parametrize("motivo", [MOTIVO_255, MOTIVO_400, MOTIVO_CON_RUTA_LARGA], ids=["255 caracteres", "400 caracteres", "una ruta de 170 caracteres sin espacios"])
    def test_el_motivo_cabe_en_el_cuadro_sin_recortarse(self, visor, motivo):
        """Revision (R-02): `Qt` abre un cuadro de nivel superior con a lo sumo 2/3 de la altura de la pantalla y una etiqueta con ajuste de linea cuyo texto no cabe lo recorta por abajo SIN
        aviso. Cada etiqueta con ajuste de linea recibe, al ancho que tiene, la altura que su texto necesita. Con una palabra larga sin espacios (una ruta) el ancho del cuadro se topa en 480
        px y la altura se calculaba para un ancho mayor: Qt parte la palabra por si solo, pero el cuadro no se abria con la altura que esa division necesita."""
        visor.mostrar_popup_cortes({n: _modulo(n, error=motivo) for n in MODULOS})
        QApplication.processEvents()
        dialogo, _ = _textos_del_cuadro(visor)
        etiquetas = [l for l in dialogo.findChildren(QLabel) if l.wordWrap()]
        assert etiquetas
        for l in etiquetas:
            necesario = l.heightForWidth(l.width())
            assert l.height() >= necesario, f"la etiqueta mide {l.height()} px y su texto necesita {necesario} px: {l.text()[:60]!r}"
        con_motivo = next(l for l in etiquetas if "CTP404" in l.text())
        assert motivo.replace(" ", "") in con_motivo.text().replace(" ", ""), "el motivo no sale entero"

    def test_un_motivo_de_339_caracteres_sale_entero(self, visor):
        """Revision (N6): ninguna rebanada del motivo en el cuadro, ni siquiera una con otro nombre que `error`."""
        motivo = "x" + " ".join(f"palabra{i:03d}" for i in range(38))
        assert len(motivo) >= 339
        visor.mostrar_popup_cortes({"CTP404": _modulo("CTP404", error=motivo)})
        dialogo, textos = _textos_del_cuadro(visor)
        assert any(motivo in t for t in textos), "el motivo no sale entero"

    def test_ningun_motivo_se_corta_en_el_codigo(self):
        """Tripwire: ninguna rebanada `...error[:N]` en el visor (el recorte a 50 caracteres es lo que dejaba el aviso ilegible)."""
        with open(os.path.join(RAIZ, "data/ManejoDatos/catphan_TAC/leer_dicom.py"), encoding="utf-8") as f:
            arbol = ast.parse(f.read())
        rebanadas = [n.lineno for n in ast.walk(arbol) if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Slice)
                     and isinstance(n.value, ast.Attribute) and n.value.attr == "error"]
        assert rebanadas == [], f"se corta un motivo de error en las lineas {rebanadas}"
