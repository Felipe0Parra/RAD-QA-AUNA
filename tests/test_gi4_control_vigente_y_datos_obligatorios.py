"""GI.4 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, A10 y lectores-7): antes de guardar una prueba de imagen, el control debe estar vigente y kV, mA y
espesor deben ser utilizables, y cuando no lo son la aplicacion dice CUAL dato falta y POR QUE.

Dos defectos, un solo momento (el instante de guardar):

(1) A10: el guardado de imagenes no consultaba la puerta W1 (`services/ventana_edicion.py`). Tras anular el control, "Guardar Espesor" escribio `pruebas` y
    `espesor_corte`, dijo "Guardado exitoso" y auditó. Ahora la pantalla (`_verificar_datos_basicos`) y el propio escritor (`guardar_prueba_completa_catphan`) la
    consultan: ningun llamador futuro la salta.
(2) `_verificar_datos_basicos` daba UN aviso ("Asegurate de haber cargado una imagen DICOM") para todo, miraba los globales del ULTIMO volumen y no la adquisicion
    de la categoria que se guarda, y con dos carpetas pasaba cuando no debia (el guardado reventaba con `IntegrityError`) o bloqueaba cuando no debia (datos
    completos). Ahora UNA funcion (`obligatorios.evaluar_categoria`) resuelve kV/mA/espesor de la categoria y la usan la guarda Y el escritor.

Los imports de lo NUEVO son perezosos (dentro de cada prueba) a proposito: contra el codigo anterior la coleccion funciona y cada prueba cae por su aserción, no
por un `ImportError` generico. kV, mA y espesor SIGUEN SIENDO OBLIGATORIOS (decision D1 del fisico, 06-10): nada de aqui relaja esa regla.
"""
import ast
import gc
import os

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox, QPushButton, QTableWidget, QTableWidgetItem

from _formularios_imagenes import FORMULARIOS, app, bd_temporal, iniciar, sin_dialogos  # noqa: F401  (fixtures)
from _serie_sintetica import AUSENTE, serie_axial
from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYLOAD_ESPESOR = {"espesor_promedio_mm": 1.9, "espesor_teorico_mm": 2.0, "diferencia_mm": 0.1,
                   "espesores_individuales": {"Izquierda": 1.9, "Abajo": 1.9, "Derecha": 1.9, "Arriba": 1.9},
                   "num_rampas_detectadas": 4}
PAYLOAD_LINEALIDAD = {"pendiente": 1.0, "intercepto": 0.0, "r_squared": 0.999}


def _nuevo():
    """Lo NUEVO de GI.4, importado al usarlo."""
    import analisisImagenes.catphan.obligatorios as obligatorios
    return obligatorios


@pytest.fixture
def formularios():
    """Las pantallas que arma una prueba; al terminar se les suelta el volumen (`test_c2` cuenta los `DicomVolume` vivos de todo el proceso)."""
    lista = []
    yield lista
    for obj in lista:
        visualizador = getattr(obj, "visualizador_principal", None)
        if visualizador is not None:
            visualizador.vol = None
    lista.clear()
    gc.collect()


@pytest.fixture
def avisos(monkeypatch):
    """Los QMessageBox.warning / critical que ve el fisico: [(titulo, texto)]."""
    visto = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, titulo, texto, *a, **k: visto.append((titulo, texto)))
    monkeypatch.setattr(QMessageBox, "critical", lambda parent, titulo, texto, *a, **k: visto.append((titulo, texto)))
    return visto


def _pantalla(formularios, clave="tomografo"):
    obj = iniciar(FORMULARIOS[clave][0]())
    formularios.append(obj)
    obj.user_id = "Fisico Real"
    return obj


def _cargar(obj, carpeta):
    """Lo que hace la carga de una carpeta: el volumen queda en el visor y los globales se fijan (como `imagen_cargada`)."""
    obj.visualizador_principal.vol = DicomVolume(carpeta)
    obj.asignar_parametros_adquisicion()


def _filas(con, ref, activo=1):
    return con.execute("SELECT id_tipo, kv, ma, espesor_corte FROM pruebas WHERE id_sesion = ? AND activo = ? ORDER BY id_tipo",
                       (ref, activo)).fetchall()


def _todas(con, ref):
    return con.execute("SELECT COUNT(*) FROM pruebas WHERE id_sesion = ?", (ref,)).fetchone()[0]


def _anular(con, ref):
    con.execute("UPDATE controles SET activo = 0 WHERE id = ?", (ref,))
    con.commit()


def _guardar_espesor(obj):
    """El camino del fisico: se corre la prueba (queda registrada su adquisicion) y se pulsa "Guardar Espesor"."""
    obj._registrar_adquisicion("espesor")
    obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
    return obj.guardar_resultado_individual("espesor", obj.resultados_espesor)


def _guardar_todos(obj):
    """"Guardar Todos" (`guardar_resultados_catphan`): hoy NINGUN boton la conecta ni crea `self.guardar_catphan` (codigo muerto, A13 del plan), asi que el
    boton se pone a mano para ejercitar la funcion: su guarda es la misma y no debe quedar atras."""
    obj.guardar_catphan = QPushButton()
    obj.guardar_resultados_catphan()


# ------------------------------------------------------------------------------------------- el resolver puro
class TestResolverPuro:
    def test_la_categoria_registrada_manda_sobre_los_globales(self):
        o = _nuevo()
        p = o.evaluar_categoria("espesor", {"espesor": {"kv": 120, "ma": 343, "espesor_corte": 2.0}}, 80, 10, 5.0)
        assert (p.kv, p.ma, p.espesor_corte, p.origen) == (120, 343, 2.0, "categoria") and p.completo and not p.faltantes

    def test_sin_registro_de_la_categoria_se_usan_los_globales(self):
        o = _nuevo()
        p = o.evaluar_categoria("espesor", {}, 125, 80, 2.0)
        assert (p.kv, p.ma, p.espesor_corte, p.origen) == (125, 80, 2.0, "globales") and p.completo

    def test_no_se_mezclan_los_datos_de_la_categoria_con_los_globales(self):
        """Dos carpetas: la categoria se corrio con una serie sin espesor; los globales son de la otra, con espesor. El espesor NO se toma de la otra serie."""
        o = _nuevo()
        p = o.evaluar_categoria("espesor", {"espesor": {"kv": 120, "ma": 343, "espesor_corte": None}}, 125, 80, 2.0)
        assert p.espesor_corte is None and [f.dato for f in p.faltantes] == ["espesor_corte"]

    @pytest.mark.parametrize("valor,causa", [(None, "no_publicado"), (0, "no_valido"), (0.0, "no_valido"), (-1.5, "no_valido"),
                                             (float("nan"), "no_valido"), (float("inf"), "no_valido"), (True, "no_valido"),
                                             ("2.0", "no_valido")])
    def test_cada_valor_inutilizable_tiene_su_causa(self, valor, causa):
        o = _nuevo()
        p = o.evaluar_categoria("espesor", {"espesor": {"kv": 120, "ma": 343, "espesor_corte": valor}}, None, None, None)
        assert [(f.dato, f.causa) for f in p.faltantes] == [("espesor_corte", causa)]

    @pytest.mark.parametrize("valor", [1, 2.0, 120, 0.6, 343.0])
    def test_un_numero_positivo_basta(self, valor):
        o = _nuevo()
        assert o.evaluar_categoria("espesor", {"espesor": {"kv": valor, "ma": valor, "espesor_corte": valor}}, None, None, None).completo

    def test_los_escalares_de_numpy_cuentan_como_numeros(self):
        import numpy as np
        o = _nuevo()
        assert o.evaluar_categoria("espesor", {"espesor": {"kv": np.float64(120), "ma": np.int64(343), "espesor_corte": np.float32(2.0)}}, None, None, None).completo

    def test_sin_serie_ni_globales_el_aviso_es_el_de_no_hay_dicom(self):
        o = _nuevo()
        p = o.evaluar_categoria("espesor", {}, None, None, None)
        assert [f.causa for f in p.faltantes] == ["sin_serie"]
        assert "no hay una serie dicom" in o.aviso_de_faltantes(p, "Espesor de corte").lower()

    def test_el_aviso_nombra_el_dato_la_causa_y_que_es_obligatorio(self):
        o = _nuevo()
        p = o.evaluar_categoria("espesor", {"espesor": {"kv": 120, "ma": 343, "espesor_corte": None}}, None, None, None)
        texto = o.aviso_de_faltantes(p, "Espesor de corte")
        assert "espesor de corte" in texto.lower() and "El espesor de corte [mm]: la serie con la que se corrió esta prueba no publica este dato; es obligatorio para guardar." in texto
        assert "None" not in texto and "Asegúrate de haber cargado" not in texto

    def test_varios_datos_faltantes_se_nombran_todos(self):
        o = _nuevo()
        p = o.evaluar_categoria("espesor", {"espesor": {"kv": 0, "ma": None, "espesor_corte": 2.0}}, None, None, None)
        texto = o.aviso_de_faltantes(p, "Espesor de corte")
        assert [f.dato for f in p.faltantes] == ["kv", "ma"]
        assert "La tensión del tubo [kV]:" in texto and "La corriente del tubo [mA]:" in texto and "El espesor de corte [mm]" not in texto

    def test_ningun_aviso_lleva_simbolos_de_correcto_o_incorrecto(self):
        """DA-18: sin chulito, equis ni advertencia en los textos del usuario."""
        o = _nuevo()
        for valor in (None, 0, "x"):
            p = o.evaluar_categoria("espesor", {"espesor": {"kv": valor, "ma": valor, "espesor_corte": valor}}, None, None, None)
            assert not any(s in o.aviso_de_faltantes(p, "X") for s in "✓✗✔✘⚠❌✅")


class TestResolverCasosLimite:
    """Lo que los dos revisores mutaron y la primera version de esta prueba no ataba."""

    def test_una_adquisicion_vacia_registrada_cae_a_los_globales(self):
        o = _nuevo()
        p = o.evaluar_categoria("espesor", {"espesor": {}}, 120, 343, 2.0)
        assert (p.origen, p.completo) == ("globales", True)

    def test_con_la_adquisicion_registrada_sin_ningun_dato_se_dice_que_la_serie_no_los_publica_y_no_que_no_hay_serie(self):
        o = _nuevo()
        p = o.evaluar_categoria("espesor", {"espesor": {"kv": None, "ma": None, "espesor_corte": None}}, 120, 343, 2.0)
        assert [(f.dato, f.causa) for f in p.faltantes] == [("kv", "no_publicado"), ("ma", "no_publicado"), ("espesor_corte", "no_publicado")]

    def test_sin_adquisicion_y_con_solo_algunos_globales_cada_uno_dice_lo_suyo(self):
        o = _nuevo()
        assert [(f.dato, f.causa) for f in o.evaluar_categoria("espesor", {}, 120, None, None).faltantes] == [("ma", "no_publicado"), ("espesor_corte", "no_publicado")]
        assert [(f.dato, f.causa) for f in o.evaluar_categoria("espesor", {}, 0, 343, 2.0).faltantes] == [("kv", "no_valido")]
        assert [(f.dato, f.causa) for f in o.evaluar_categoria("espesor", {}, 120, 0, 2.0).faltantes] == [("ma", "no_valido")]

    def test_los_faltantes_salen_en_el_orden_kv_ma_espesor(self):
        o = _nuevo()
        assert [f.dato for f in o.evaluar_categoria("espesor", {"espesor": {"kv": 0, "ma": 0, "espesor_corte": 0}}, None, None, None).faltantes] == ["kv", "ma", "espesor_corte"]

    def test_un_numero_de_pydicom_se_dice_sin_comillas_y_con_su_valor(self):
        """pydicom entrega `DSfloat`/`IS`, cuyo `repr` lleva comillas (`'0.0'`): el aviso decia «publica '0.0'»."""
        import pydicom.valuerep as vr
        o = _nuevo()
        p = o.evaluar_categoria("espesor", {"espesor": {"kv": vr.DSfloat("0.0"), "ma": vr.IS("0"), "espesor_corte": 2.0}}, None, None, None)
        texto = o.aviso_de_faltantes(p, "Espesor de corte")
        assert "'" not in texto and "publica 0, que no es un valor válido" in texto

    def test_el_aviso_dice_de_que_prueba_se_trata_y_cada_prueba_tiene_su_nombre(self):
        o = _nuevo()
        p = o.evaluar_categoria("x", {"x": {"kv": None, "ma": 1, "espesor_corte": 1}}, None, None, None)
        for categoria, nombre in (("espesor", "Espesor de corte"), ("tamano_pixel", "Tamaño de píxel"), ("resolucion_contraste", "Resolución de contraste"),
                                  ("resolucion_espacial", "Resolución espacial"), ("valores_ct", "Valores CT"), ("linealidad_ct", "Linealidad CT"),
                                  ("uniformidad", "Uniformidad")):
            assert o.etiqueta_de(categoria) == nombre
            assert f"«{nombre}»" in o.aviso_de_faltantes(p, o.etiqueta_de(categoria))

    def test_cada_dato_se_rotula_con_su_unidad_entre_corchetes_y_sin_parentesis(self):
        o = _nuevo()
        texto = o.aviso_de_faltantes(o.evaluar_categoria("x", {"x": {"kv": None, "ma": None, "espesor_corte": None}}, None, None, None), "X")
        assert "[kV]" in texto and "[mA]" in texto and "[mm]" in texto and "(" not in texto

    def test_el_aviso_dice_que_hacer_salvo_cuando_no_hay_serie(self):
        o = _nuevo()
        con_serie = o.aviso_de_faltantes(o.evaluar_categoria("x", {"x": {"kv": None, "ma": 1, "espesor_corte": 1}}, None, None, None), "X")
        sin_serie = o.aviso_de_faltantes(o.evaluar_categoria("x", {}, None, None, None), "X")
        assert "Repita el análisis con una serie que publique estos datos." in con_serie and "Repita el análisis con una serie" not in sin_serie
        assert con_serie.count("es obligatorio para guardar") == 1, "la frase se repite en el mismo aviso"

    def test_los_parametros_del_volumen_se_redondean_igual_que_en_la_ventana(self):
        """`_parametros_de_volumen` (lo que se guarda y se evalua) y la ventana usan la MISMA definicion del redondeo del espesor."""
        from types import SimpleNamespace
        from ui.paginasControles.PruebasMensuales.tac_mensual import _parametros_de_volumen
        assert _parametros_de_volumen(SimpleNamespace(kv=120, ma=100, espesor_corte=2.04)) == (120, 100, 2.0)
        assert _parametros_de_volumen(SimpleNamespace(kv=120, ma=100, espesor_corte=0.04)) == (120, 100, 0.0)
        assert _parametros_de_volumen(SimpleNamespace(kv=120, ma=100, espesor_corte=None)) == (120, 100, None)

    def test_el_espesor_se_redondea_a_un_decimal_como_se_registra(self):
        o = _nuevo()
        assert o.redondear_espesor(0.04) == 0.0 and o.redondear_espesor(2.04) == 2.0 and o.redondear_espesor(None) is None and o.redondear_espesor("x") == "x"
        assert o.redondear_espesor(2.54) == 2.5 and o.redondear_espesor(0.62) == 0.6, "se redondea a UN decimal, no a entero"


# ------------------------------------------------------------------- la guarda de la pantalla: un aviso por situacion
SITUACIONES = {
    "espesor_ausente": dict(espesor=AUSENTE),
    "espesor_vacio": dict(espesor=None),
    "espesor_cero": dict(espesor=0.0),
    "ma_cero": dict(ma=0),
    "kv_cero": dict(kv=0),
}


class TestCadaSituacionDiceSuCausa:
    @pytest.mark.parametrize("nombre", list(SITUACIONES))
    def test_no_se_guarda_nada_y_el_aviso_nombra_el_dato(self, app, bd_temporal, avisos, formularios, tmp_path, nombre):
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "serie"), **SITUACIONES[nombre]))
        ok = _guardar_espesor(obj)
        assert ok is False
        assert _todas(bd_temporal, obj.ref) == 0, "se guardo una prueba con un dato obligatorio inutilizable"
        assert len(avisos) == 1
        titulo, texto = avisos[0]
        assert "Asegúrate de haber cargado" not in texto, "el aviso unico de siempre: no dice cual dato ni por que"
        dato = {"espesor": "El espesor de corte [mm]", "ma": "La corriente del tubo [mA]", "kv": "La tensión del tubo [kV]"}[next(iter(SITUACIONES[nombre]))]
        assert f"{dato}: la serie con la que se corrió esta prueba" in texto and "es obligatorio para guardar" in texto

    def test_ausente_y_vacio_son_el_mismo_hecho_para_el_fisico_los_otros_tres_difieren(self, app, bd_temporal, avisos, formularios, tmp_path):
        """Cinco situaciones, cuatro avisos: que la etiqueta falte o venga vacia es el MISMO hecho (la serie no publica el dato) y desde SE.1 el cargador
        los dice igual (`None`). Las otras tres (espesor 0, mA 0, kV 0) son cada una la suya."""
        textos = {}
        for nombre, kw in SITUACIONES.items():
            obj = _pantalla(formularios)
            avisos.clear()
            _cargar(obj, serie_axial(str(tmp_path / nombre), **kw))
            _guardar_espesor(obj)
            textos[nombre] = avisos[0][1] if avisos else ""
            obj.visualizador_principal.vol = None
        assert textos["espesor_ausente"] == textos["espesor_vacio"] != ""
        distintos = {textos["espesor_ausente"], textos["espesor_cero"], textos["ma_cero"], textos["kv_cero"]}
        assert len(distintos) == 4

    def test_un_cero_se_dice_como_valor_invalido_y_no_como_dato_ausente(self, app, bd_temporal, avisos, formularios, tmp_path):
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "s"), espesor=0.0))
        _guardar_espesor(obj)
        texto = avisos[0][1]
        assert "no publica este dato" not in texto and "publica 0, que no es un valor válido" in texto

    def test_una_serie_completa_guarda_sin_ningun_aviso(self, app, bd_temporal, avisos, formularios, tmp_path):
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "s")))
        assert _guardar_espesor(obj) is not False and avisos == []
        assert _filas(bd_temporal, obj.ref) == [(1, 120, 343, 2.0)]

    def test_sin_ninguna_carpeta_el_aviso_es_el_de_no_hay_dicom(self, app, bd_temporal, avisos, formularios):
        obj = _pantalla(formularios)
        obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
        assert obj.guardar_resultado_individual("espesor", obj.resultados_espesor) is False
        assert "no hay una serie dicom" in avisos[0][1].lower() and _todas(bd_temporal, obj.ref) == 0


# ------------------------------------------------------------------------------- dos carpetas en la misma sesion
class TestDosCarpetas:
    def test_carpeta_completa_para_la_prueba_y_despues_otra_sin_espesor_no_bloquea_datos_completos(
            self, app, bd_temporal, avisos, formularios, tmp_path):
        """La prueba se corrio con la carpeta A (completa); despues se cargo la B (sin espesor). Los globales ahora estan vacios, pero la adquisicion de la
        prueba es la de A: se guarda con 120 / 343 / 2.0 (antes la guarda miraba los globales y bloqueaba)."""
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "A"), espesor=2.0, kv=120, ma=343))
        obj._registrar_adquisicion("espesor")
        _cargar(obj, serie_axial(str(tmp_path / "B"), espesor=AUSENTE, kv=100, ma=80))
        assert obj.espesor_corte_val is None, "premisa: los globales ya son los de la carpeta sin espesor"
        obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
        assert obj.guardar_resultado_individual("espesor", obj.resultados_espesor) is not False
        assert avisos == []
        assert _filas(bd_temporal, obj.ref) == [(1, 120, 343, 2.0)], "se guardo con los parametros de la otra carpeta"

    def test_prueba_corrida_sin_espesor_y_despues_otra_carpeta_completa_no_revienta_y_no_guarda(
            self, app, bd_temporal, avisos, formularios, tmp_path):
        """La prueba se corrio con la carpeta B (sin espesor); despues se cargo la A (completa). Los globales estan completos y la guarda de antes PASABA; el
        guardado reventaba con `IntegrityError` (pruebas.espesor_corte es NOT NULL) y el fisico veia el aviso generico. Ahora: un aviso que nombra el
        espesor y nada guardado."""
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "B"), espesor=AUSENTE))
        obj._registrar_adquisicion("espesor")
        _cargar(obj, serie_axial(str(tmp_path / "A"), espesor=2.0))
        assert obj.espesor_corte_val == 2.0, "premisa: los globales son los de la carpeta completa"
        obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
        assert obj.guardar_resultado_individual("espesor", obj.resultados_espesor) is False
        assert len(avisos) == 1 and "El espesor de corte [mm]:" in avisos[0][1] and "no publica este dato" in avisos[0][1]
        assert "Error al guardar" not in avisos[0][1]
        assert _todas(bd_temporal, obj.ref) == 0

    def test_guardar_todos_con_una_prueba_incompleta_no_guarda_nada_y_nombra_la_prueba(self, app, bd_temporal, avisos, formularios, tmp_path):
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "B"), espesor=AUSENTE))
        obj._registrar_adquisicion("espesor")
        _cargar(obj, serie_axial(str(tmp_path / "A"), espesor=2.0))
        obj._registrar_adquisicion("linealidad_ct")
        obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
        obj.resultados_linealidad_ct = dict(PAYLOAD_LINEALIDAD)
        _guardar_todos(obj)
        assert _todas(bd_temporal, obj.ref) == 0, "guardo la prueba completa y dejo la otra, o guardo ambas"
        assert len(avisos) == 1 and "«Espesor de corte»" in avisos[0][1] and "no publica este dato" in avisos[0][1]

    def test_guardar_todos_con_dos_pruebas_inutilizables_las_nombra_a_las_dos_en_un_solo_aviso(self, app, bd_temporal, avisos, formularios, tmp_path):
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "B"), espesor=AUSENTE))
        obj._registrar_adquisicion("espesor")
        obj._registrar_adquisicion("linealidad_ct")
        obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
        obj.resultados_linealidad_ct = dict(PAYLOAD_LINEALIDAD)
        _guardar_todos(obj)
        assert _todas(bd_temporal, obj.ref) == 0 and len(avisos) == 1
        assert "«Espesor de corte»" in avisos[0][1] and "«Linealidad CT»" in avisos[0][1]

    def test_guardar_todos_con_ambas_completas_guarda_las_dos_con_su_adquisicion(self, app, bd_temporal, avisos, formularios, tmp_path):
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "A"), kv=120, ma=343))
        obj._registrar_adquisicion("espesor")
        _cargar(obj, serie_axial(str(tmp_path / "C"), kv=100, ma=80, espesor=2.5))
        obj._registrar_adquisicion("linealidad_ct")
        obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
        obj.resultados_linealidad_ct = dict(PAYLOAD_LINEALIDAD)
        _guardar_todos(obj)
        assert avisos == []
        assert _filas(bd_temporal, obj.ref) == [(1, 120, 343, 2.0), (6, 100, 80, 2.5)]


# ------------------------------------------------------------------------------------ el escritor tambien lo exige
class TestElEscritorNoDependeDeLaPantalla:
    def _guardar(self, ruta_ref, **kw):
        from data.ManejoDatos.catphan_TAC.catphan_db import guardar_prueba_completa_catphan
        base = dict(user_id="fisico1", fecha="2026-06-01", equipo="Tomógrafo", kv=120, ma=100, espesor_corte=2.0,
                    resultados_por_categoria={"espesor": {"espesor_promedio_mm": 1.9}}, id_sesion=ruta_ref)
        base.update(kw)
        return guardar_prueba_completa_catphan(**base)

    def _control(self, con):
        con.execute("INSERT INTO controles (equipo, control, fecha) VALUES ('Tomógrafo', 'Mensual', '06/2026')")
        con.commit()
        return con.execute("SELECT MAX(id) FROM controles").fetchone()[0]

    @pytest.mark.parametrize("campo", ["kv", "ma", "espesor_corte"])
    @pytest.mark.parametrize("valor", [None, 0])
    def test_un_dato_obligatorio_inutilizable_lanza_la_excepcion_con_el_motivo_y_no_escribe(self, app, bd_temporal, campo, valor):
        from analisisImagenes.catphan.obligatorios import ParametrosObligatoriosFaltantes
        ref = self._control(bd_temporal)
        with pytest.raises(ParametrosObligatoriosFaltantes) as e:
            self._guardar(ref, **{campo: valor})
        assert {"kv": "La tensión del tubo [kV]", "ma": "La corriente del tubo [mA]", "espesor_corte": "El espesor de corte [mm]"}[campo] in str(e.value)
        assert _todas(bd_temporal, ref) == 0

    def test_sin_adquisicion_de_la_categoria_cuentan_los_argumentos_de_la_llamada(self, app, bd_temporal):
        ref = self._control(bd_temporal)
        assert self._guardar(ref) == ref and _filas(bd_temporal, ref) == [(1, 120, 100, 2.0)]

    def test_varias_pruebas_inutilizables_se_nombran_todas(self, app, bd_temporal):
        from analisisImagenes.catphan.obligatorios import ParametrosObligatoriosFaltantes
        ref = self._control(bd_temporal)
        malo = {"kv": 120, "ma": 100, "espesor_corte": None}
        with pytest.raises(ParametrosObligatoriosFaltantes) as e:
            self._guardar(ref, resultados_por_categoria={"espesor": {"espesor_promedio_mm": 1.9}, "linealidad_ct": dict(PAYLOAD_LINEALIDAD)},
                          adquisicion_por_categoria={"espesor": malo, "linealidad_ct": malo})
        assert "«Espesor de corte»" in str(e.value) and "«Linealidad CT»" in str(e.value)
        assert _todas(bd_temporal, ref) == 0

    def test_la_adquisicion_de_la_categoria_manda_sobre_los_argumentos(self, app, bd_temporal):
        ref = self._control(bd_temporal)
        self._guardar(ref, adquisicion_por_categoria={"espesor": {"kv": 100, "ma": 80, "espesor_corte": 2.5}})
        assert _filas(bd_temporal, ref) == [(1, 100, 80, 2.5)]

    def test_con_una_prueba_inutilizable_entre_varias_no_se_guarda_ninguna(self, app, bd_temporal):
        from analisisImagenes.catphan.obligatorios import ParametrosObligatoriosFaltantes
        ref = self._control(bd_temporal)
        with pytest.raises(ParametrosObligatoriosFaltantes):
            self._guardar(ref, resultados_por_categoria={"espesor": {"espesor_promedio_mm": 1.9}, "linealidad_ct": dict(PAYLOAD_LINEALIDAD)},
                          adquisicion_por_categoria={"linealidad_ct": {"kv": 120, "ma": 100, "espesor_corte": None}})
        assert _todas(bd_temporal, ref) == 0

    def test_una_sesion_sin_control_id_none_no_consulta_la_puerta(self, app, bd_temporal, monkeypatch):
        """La ruta antigua (`id_sesion=None`: el escritor inventa una sesion `AAAAMMDD_marca`) no tiene control al que preguntarle: la puerta no se consulta.
        (Con `foreign_keys=ON` esa sesion inventada ya no puede entrar a `pruebas` -- la FK apunta a `controles` --: es anterior a este plan y no se toca.)"""
        import data.ManejoDatos.catphan_TAC.catphan_db as db
        monkeypatch.setattr(db, "puede_editarse", lambda *a, **k: pytest.fail("se consulto la puerta W1 sin control"))
        self._guardar(None)

    def test_una_excepcion_que_no_es_nuestra_sigue_devolviendo_none_como_antes(self, app, bd_temporal, monkeypatch):
        """GI.6 es quien decide que hacer con los demas errores del escritor: aqui solo se relanzan los dos nuevos, con motivo."""
        import data.ManejoDatos.catphan_TAC.catphan_db as db

        def _falla(*a, **k):
            raise RuntimeError("fallo simulado (GI.4)")

        monkeypatch.setattr(db, "guardar_espesor_corte", _falla)
        ref = self._control(bd_temporal)
        assert self._guardar(ref) is None and _todas(bd_temporal, ref) == 0


# ------------------------------------------------------------------------------------------ la puerta W1 (A10)
class TestPuertaW1:
    def test_control_vigente_guarda(self, app, bd_temporal, avisos, formularios, tmp_path):
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "s")))
        assert _guardar_espesor(obj) is not False and avisos == []

    def test_control_anulado_la_pantalla_avisa_con_el_motivo_de_w1_y_no_guarda(self, app, bd_temporal, sin_dialogos, avisos, formularios, tmp_path):
        """El caso de V1: el control se anula mientras el formulario sigue abierto; "Guardar Espesor" antes escribia, decia "Guardado exitoso" y auditaba."""
        from services.ventana_edicion import mensaje_bloqueo_edicion
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "s")))
        obj._registrar_adquisicion("espesor")
        _anular(bd_temporal, obj.ref)
        n_auditoria = bd_temporal.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
        assert obj.guardar_resultado_individual("espesor", obj.resultados_espesor) is False
        assert _todas(bd_temporal, obj.ref) == 0
        assert bd_temporal.execute("SELECT COUNT(*) FROM espesor_corte").fetchone()[0] == 0
        assert bd_temporal.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == n_auditoria, "audito un guardado que no ocurrio"
        assert [t for t, _ in sin_dialogos if t == "Guardado exitoso"] == []
        assert avisos == [("Control cerrado", mensaje_bloqueo_edicion(obj.ref))]
        assert "anulado" in avisos[0][1]

    def test_guardar_todos_con_el_control_anulado_tampoco_guarda(self, app, bd_temporal, sin_dialogos, avisos, formularios, tmp_path):
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "s")))
        obj._registrar_adquisicion("espesor")
        _anular(bd_temporal, obj.ref)
        obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
        _guardar_todos(obj)
        assert _todas(bd_temporal, obj.ref) == 0 and [t for t, _ in sin_dialogos if t == "Guardado exitoso"] == []
        assert avisos and avisos[0][0] == "Control cerrado"

    def test_el_escritor_se_niega_aunque_el_llamador_se_salte_la_guarda(self, app, bd_temporal, sin_dialogos, avisos, formularios, tmp_path, monkeypatch):
        """"Ningun llamador futuro la salta": con la guarda de la pantalla anulada, el escritor lanza `ControlNoEditable` y la pantalla lo dice."""
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "s")))
        obj._registrar_adquisicion("espesor")
        _anular(bd_temporal, obj.ref)
        monkeypatch.setattr(type(obj), "_verificar_datos_basicos", lambda self, *a, **k: True)
        obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
        assert obj.guardar_resultado_individual("espesor", obj.resultados_espesor) is False
        assert _todas(bd_temporal, obj.ref) == 0 and [t for t, _ in sin_dialogos if t == "Guardado exitoso"] == []
        assert avisos and avisos[0][0] == "Control cerrado" and "anulado" in avisos[0][1]

    def test_con_el_control_anulado_la_pantalla_ni_siquiera_llama_al_escritor(self, app, bd_temporal, avisos, formularios, tmp_path, monkeypatch):
        """La guarda de la PANTALLA es la primera barrera: con el control anulado el escritor no se invoca (la barrera del escritor es la segunda)."""
        import ui.paginasControles.PruebasMensuales.tac_mensual as tac_mod
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "s")))
        obj._registrar_adquisicion("espesor")
        _anular(bd_temporal, obj.ref)
        monkeypatch.setattr(tac_mod, "guardar_prueba_completa_catphan", lambda *a, **k: pytest.fail("la pantalla llamo al escritor con el control anulado"))
        obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
        assert obj.guardar_resultado_individual("espesor", obj.resultados_espesor) is False
        assert avisos and avisos[0][0] == "Control cerrado"

    def test_control_anulado_y_dato_faltante_dice_primero_que_el_control_esta_cerrado(self, app, bd_temporal, avisos, formularios, tmp_path):
        """Si el control esta cerrado, de nada sirve decir que falta un dato: el aviso es el del control."""
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "s"), espesor=AUSENTE))
        obj._registrar_adquisicion("espesor")
        _anular(bd_temporal, obj.ref)
        obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
        assert obj.guardar_resultado_individual("espesor", obj.resultados_espesor) is False
        assert [t for t, _ in avisos] == ["Control cerrado"]

    def test_el_escritor_se_niega_a_datos_inutilizables_aunque_el_llamador_se_salte_la_guarda(
            self, app, bd_temporal, sin_dialogos, avisos, formularios, tmp_path, monkeypatch):
        """La segunda barrera de los datos obligatorios: con la guarda de la pantalla anulada, el escritor lanza y la pantalla lo dice, sin guardar nada."""
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "s"), espesor=AUSENTE))
        obj._registrar_adquisicion("espesor")
        monkeypatch.setattr(type(obj), "_verificar_datos_basicos", lambda self, *a, **k: True)
        obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
        assert obj.guardar_resultado_individual("espesor", obj.resultados_espesor) is False
        assert _todas(bd_temporal, obj.ref) == 0 and [t for t, _ in sin_dialogos if t == "Guardado exitoso"] == []
        assert len(avisos) == 1 and avisos[0][0] == "Falta un dato obligatorio" and "no publica este dato" in avisos[0][1]

    def test_el_escritor_lanza_control_no_editable_con_el_mensaje_de_w1(self, app, bd_temporal):
        from data.ManejoDatos.catphan_TAC.catphan_db import ControlNoEditable, guardar_prueba_completa_catphan
        from services.ventana_edicion import mensaje_bloqueo_edicion
        bd_temporal.execute("INSERT INTO controles (equipo, control, fecha) VALUES ('Tomógrafo', 'Mensual', '06/2026')")
        bd_temporal.commit()
        ref = bd_temporal.execute("SELECT MAX(id) FROM controles").fetchone()[0]
        _anular(bd_temporal, ref)
        with pytest.raises(ControlNoEditable) as e:
            guardar_prueba_completa_catphan("f", "2026-06-01", "Tomógrafo", 120, 100, 2.0, {"espesor": {"espesor_promedio_mm": 1.9}}, id_sesion=ref)
        assert str(e.value) == mensaje_bloqueo_edicion(ref)
        assert _todas(bd_temporal, ref) == 0

    def test_un_control_que_no_existe_tambien_se_niega(self, app, bd_temporal):
        from data.ManejoDatos.catphan_TAC.catphan_db import ControlNoEditable, guardar_prueba_completa_catphan
        with pytest.raises(ControlNoEditable) as e:
            guardar_prueba_completa_catphan("f", "2026-06-01", "Tomógrafo", 120, 100, 2.0, {"espesor": {"espesor_promedio_mm": 1.9}}, id_sesion=987654)
        assert "ya no existe" in str(e.value)
        assert _todas(bd_temporal, 987654) == 0

    @pytest.mark.parametrize("clave", list(FORMULARIOS))
    def test_en_las_cinco_pantallas_un_control_legitimo_sigue_guardando(self, app, bd_temporal, avisos, formularios, tmp_path, clave):
        """V1 midio que `puede_editarse` da True en los controles legitimos de las cinco pantallas (anuales incluidas); aqui se guarda de verdad."""
        from services.ventana_edicion import puede_editarse
        obj = _pantalla(formularios, clave)
        assert puede_editarse(obj.ref) is True
        _cargar(obj, serie_axial(str(tmp_path / "s")))
        assert _guardar_espesor(obj) is not False and avisos == []
        assert _filas(bd_temporal, obj.ref) == [(1, 120, 343, 2.0)]

    @pytest.mark.parametrize("clave", list(FORMULARIOS))
    def test_en_las_cinco_pantallas_un_control_anulado_no_guarda(self, app, bd_temporal, avisos, formularios, tmp_path, clave):
        obj = _pantalla(formularios, clave)
        _cargar(obj, serie_axial(str(tmp_path / "s")))
        obj._registrar_adquisicion("espesor")
        _anular(bd_temporal, obj.ref)
        obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
        assert obj.guardar_resultado_individual("espesor", obj.resultados_espesor) is False
        assert _todas(bd_temporal, obj.ref) == 0 and avisos and avisos[0][0] == "Control cerrado"

    def test_anulado_con_la_funcion_real_de_la_app_tambien_se_niega(self, app, bd_temporal, sin_dialogos, avisos, formularios, tmp_path):
        """`load.eliminarRegistroCT` es la que anula el control desde la vista de registros del CT (la de V1): su efecto es el que la puerta lee."""
        import data.ManejoDatos.load as load_mod
        obj = _pantalla(formularios)
        _cargar(obj, serie_axial(str(tmp_path / "s")))
        obj._registrar_adquisicion("espesor")
        tabla = QTableWidget(1, 1)
        item = QTableWidgetItem("06/2026")
        item.setData(Qt.UserRole, obj.ref)
        tabla.setItem(0, 0, item)
        tabla.setCurrentCell(0, 0)
        load_mod.eliminarRegistroCT(obj, tabla)
        assert bd_temporal.execute("SELECT activo FROM controles WHERE id = ?", (obj.ref,)).fetchone()[0] == 0, "premisa: el control quedo anulado"
        obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
        assert obj.guardar_resultado_individual("espesor", obj.resultados_espesor) is False and _todas(bd_temporal, obj.ref) == 0


# ------------------------------------------------------------------------------------- la ventana de metadatos (A.3)
class TestVentanaAdvierteQueNoSePodraGuardar:
    def _modelo(self, carpeta, equipo="Tomógrafo"):
        from data.ManejoDatos.catphan_TAC.ventana_metadatos import construir_modelo_ventana
        return construir_modelo_ventana(DicomVolume(carpeta), equipo)

    def test_serie_sin_espesor_la_ventana_dice_que_no_se_podra_guardar_y_cual_dato(self, tmp_path):
        m = self._modelo(serie_axial(str(tmp_path / "s"), espesor=AUSENTE))
        assert m.aviso_guardado and "no se podrá guardar" in m.aviso_guardado and "espesor de corte" in m.aviso_guardado
        assert m.requiere_confirmacion is True
        confirmacion = m.texto_confirmacion()
        assert "no se podrá guardar" in confirmacion and "Se puede analizar igual" not in confirmacion

    @pytest.mark.parametrize("kw,dato", [(dict(espesor=0.0), "espesor de corte"), (dict(ma=0), "mA"), (dict(kv=0), "kV")])
    def test_cada_dato_inutilizable_se_nombra_en_la_ventana(self, tmp_path, kw, dato):
        m = self._modelo(serie_axial(str(tmp_path / "s"), **kw))
        assert m.aviso_guardado and dato in m.aviso_guardado

    def test_en_un_equipo_que_no_exige_espesor_la_falta_igual_pide_confirmacion(self, tmp_path):
        """En el iX el espesor no aplica al protocolo («No se exige»): sin el aviso de guardado no habria motivo para confirmar, y el fisico entraria sin saber que
        no podra guardar."""
        m = self._modelo(serie_axial(str(tmp_path / "s"), espesor=AUSENTE), equipo="Clinac ix")
        assert m.aviso_guardado and "no se podrá guardar" in m.texto_confirmacion()
        assert m.requiere_confirmacion is True

    def test_la_falta_de_un_dato_pide_confirmacion_aunque_el_protocolo_conforme(self, tmp_path, monkeypatch):
        """Aislado del protocolo: la comparacion dice que la serie es del equipo y que ninguna fila incumple, asi que SOLO el aviso de guardado puede pedir la
        segunda confirmacion. Sin el aviso (serie completa) no la pide."""
        from types import SimpleNamespace
        import data.ManejoDatos.catphan_TAC.ventana_metadatos as ventana
        from analisisImagenes.catphan.protocolos import COINCIDE
        monkeypatch.setattr(ventana, "comparar_con_protocolo", lambda equipo, adq: SimpleNamespace(
            identidad=COINCIDE, imagenes_de="X", equipo_identificado=equipo, equipo_seleccionado=equipo, advertencia_identidad=None, filas=[],
            desviacion_texto=lambda: None))
        sin_espesor = self._modelo(serie_axial(str(tmp_path / "a"), espesor=AUSENTE))
        completa = self._modelo(serie_axial(str(tmp_path / "b")))
        assert sin_espesor.requiere_confirmacion is True and completa.requiere_confirmacion is False

    def test_la_ventana_y_la_guarda_dicen_lo_mismo_de_un_espesor_que_redondea_a_cero(self, tmp_path):
        """0.04 mm se registra como 0.0 (un decimal): la ventana avisaba «nada» y el guardado bloqueaba."""
        m = self._modelo(serie_axial(str(tmp_path / "s"), espesor=0.04))
        assert m.aviso_guardado and "El espesor de corte [mm]" in m.aviso_guardado and "publica 0, que no es un valor válido" in m.aviso_guardado

    def test_una_serie_sin_ninguno_de_los_tres_datos_dice_que_no_los_publica_y_no_que_no_hay_serie(self, tmp_path):
        class _Vol:
            adquisicion = {"kv": None, "ma": None, "espesor_mm": None, "modelo": "SOMATOM go.Sim"}
            series_descartadas = {}
            detalle_series_descartadas = {}
            no_imagen = 0
            avisos = []
        from data.ManejoDatos.catphan_TAC.ventana_metadatos import construir_modelo_ventana
        m = construir_modelo_ventana(_Vol(), "Tomógrafo")
        assert "No hay una serie DICOM" not in m.aviso_guardado
        assert m.aviso_guardado.count("esta serie no publica este dato") == 3

    def test_la_ventana_nombra_la_serie_que_se_acaba_de_cargar_y_no_la_de_una_prueba(self, tmp_path):
        m = self._modelo(serie_axial(str(tmp_path / "s"), espesor=AUSENTE))
        assert "esta serie no publica este dato" in m.aviso_guardado and "con la que se corrió esta prueba" not in m.aviso_guardado

    def test_el_aviso_es_visible_en_el_dialogo(self, app, tmp_path):
        from data.ManejoDatos.catphan_TAC.ventana_metadatos import VentanaMetadatos
        m = self._modelo(serie_axial(str(tmp_path / "s"), espesor=AUSENTE))
        dialogo = VentanaMetadatos(None, m)
        assert "no se podrá guardar" in dialogo.texto_visible()
        dialogo.deleteLater()

    def test_serie_completa_no_lleva_aviso_de_guardado(self, tmp_path):
        m = self._modelo(serie_axial(str(tmp_path / "s")))
        assert not m.aviso_guardado

    def test_serie_completa_fuera_de_protocolo_conserva_el_texto_de_siempre(self, tmp_path):
        """El texto de A.3 para una serie que solo se desvia del protocolo NO cambia (lo fija `test_a3`)."""
        m = self._modelo(serie_axial(str(tmp_path / "s"), kv=100))
        assert m.requiere_confirmacion and not m.aviso_guardado
        assert "Se puede analizar igual" in m.texto_confirmacion()

    def test_serie_sin_espesor_y_fuera_de_protocolo_dice_las_dos_cosas(self, tmp_path):
        m = self._modelo(serie_axial(str(tmp_path / "s"), kv=100, espesor=AUSENTE))
        texto = m.texto_confirmacion()
        assert "no se podrá guardar" in texto and "kV" in texto


# --------------------------------------------------------------------------------------------- el texto fresco
class TestElTextoNoDiceNone:
    def test_espesor_teorico_no_publicado_se_dice_asi(self):
        from data.ManejoDatos.catphan_TAC.catphan_db import tabla_resultados_espesor
        texto = tabla_resultados_espesor({"espesor_promedio_mm": 1.9, "espesor_teorico_mm": None, "diferencia_mm": None})
        assert "Espesor teórico: (no publicado)" in texto and "None" not in texto

    def test_con_espesor_teorico_el_texto_es_el_de_siempre(self):
        from data.ManejoDatos.catphan_TAC.catphan_db import tabla_resultados_espesor
        texto = tabla_resultados_espesor({"espesor_promedio_mm": 1.9, "espesor_teorico_mm": 2.0, "diferencia_mm": 0.1})
        assert "  Espesor teórico: 2.0 mm" in texto and "  Diferencia: 0.1 mm" in texto and "no publicado" not in texto

    def test_un_cero_legitimo_no_se_confunde_con_dato_ausente(self):
        """DP-52: un 0.0 es un dato; solo `None` es «no hay dato»."""
        from data.ManejoDatos.catphan_TAC.catphan_db import tabla_resultados_espesor
        texto = tabla_resultados_espesor({"espesor_promedio_mm": 0.0, "espesor_teorico_mm": 0.0, "diferencia_mm": 0.0})
        assert "  Espesor promedio: 0.0 mm" in texto and "  Espesor teórico: 0.0 mm" in texto and "  Diferencia: 0.0 mm" in texto
        assert "N/A" not in texto and "no publicado" not in texto

    def test_ningun_valor_none_se_escribe_como_none_ni_con_su_unidad_pegada(self):
        from data.ManejoDatos.catphan_TAC.catphan_db import tabla_resultados_espesor
        texto = tabla_resultados_espesor({"espesor_promedio_mm": None, "espesor_teorico_mm": None, "diferencia_mm": None})
        assert "None" not in texto and "  Espesor promedio: N/A\n" in texto and "  Diferencia: N/A\n" in texto and "N/A mm" not in texto

    def test_sin_las_claves_sigue_diciendo_n_a_como_antes(self):
        from data.ManejoDatos.catphan_TAC.catphan_db import tabla_resultados_espesor
        texto = tabla_resultados_espesor({"espesor_promedio_mm": 1.9})
        assert "Espesor teórico: N/A mm" in texto and "Diferencia: N/A mm" in texto


# ----------------------------------------------------------------------- tripwires: una sola definicion, sin atajos
def _funcion(ruta, nombre):
    arbol = ast.parse(open(os.path.join(RAIZ, ruta), encoding="utf-8").read())
    return next(n for n in ast.walk(arbol) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nombre)


def _nombres(nodo):
    return ({n.id for n in ast.walk(nodo) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(nodo) if isinstance(n, ast.Attribute)})


class TestUnaSolaDefinicion:
    TAC = "ui/paginasControles/PruebasMensuales/tac_mensual.py"
    DB = "data/ManejoDatos/catphan_TAC/catphan_db.py"

    def test_la_guarda_y_el_escritor_usan_la_misma_funcion_de_resolucion(self):
        assert "evaluar_categoria" in _nombres(_funcion(self.TAC, "_parametros_de_guardado"))
        assert "_parametros_de_guardado" in _nombres(_funcion(self.TAC, "_verificar_datos_basicos"))
        assert "evaluar_categoria" in _nombres(_funcion(self.DB, "guardar_prueba_completa_catphan"))

    def test_la_guarda_ya_no_mira_solo_los_globales_con_un_unico_aviso(self):
        fuente = ast.unparse(_funcion(self.TAC, "_verificar_datos_basicos"))
        assert "Asegúrate de haber cargado una imagen DICOM" not in fuente
        assert "self.kv_actual and self.ma_actual and self.espesor_corte_val" not in fuente

    def test_la_guarda_y_el_escritor_consultan_la_puerta_w1(self):
        assert {"puede_editarse", "motivo_bloqueo", "_puede_editarse_control"} & _nombres(_funcion(self.TAC, "_verificar_datos_basicos"))
        assert {"puede_editarse", "motivo_bloqueo", "_puede_editarse_control"} & _nombres(_funcion(self.DB, "guardar_prueba_completa_catphan"))

    def test_los_dos_guardados_de_la_pantalla_atrapan_las_dos_excepciones_nuevas(self):
        for nombre in ("guardar_resultado_individual", "guardar_resultados_catphan"):
            f = _funcion(self.TAC, nombre)
            atrapadas = {n.id for h in ast.walk(f) if isinstance(h, ast.ExceptHandler) and h.type is not None
                         for n in ast.walk(h.type) if isinstance(n, ast.Name)}
            assert {"ControlNoEditable", "ParametrosObligatoriosFaltantes"} <= atrapadas, nombre

    def test_los_dos_guardados_pasan_las_categorias_a_la_guarda(self):
        for nombre in ("guardar_resultado_individual", "guardar_resultados_catphan"):
            llamadas = [n for n in ast.walk(_funcion(self.TAC, nombre)) if isinstance(n, ast.Call)
                        and getattr(n.func, "attr", "") == "_verificar_datos_basicos"]
            assert llamadas and all(c.args or c.keywords for c in llamadas), nombre
