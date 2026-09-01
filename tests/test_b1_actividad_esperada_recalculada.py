"""B1/B2/B4 (PLAN_ACTIVIDAD_ESPERADA_BRAQUI_27-08.md): la "Actividad
esperada" del diario de braquiterapia (`line_1_exp_act_ci`) es un campo
DERIVADO -- lo calcula la app por decaimiento del Ir-192 desde la fuente
vigente, no lo teclea el físico.

`A4` (26-08) añadió `_limpiar_widgets_diaria`, que vacía TODO `df_lines` al
llegar a una fecha sin registro. Correcto para lo tecleado; para este campo
no: quedaba vacío, y al guardar `load.py` hacía `float("")` y abortaba el
control diario ENTERO con un `QMessageBox.critical` -- cero filas escritas,
ni para este campo ni para ningún otro del día.

Línea base medida del defecto (§1 del plan), que estos tests deben ver roja
si se revierte la corrección:

    actividad al construir la pantalla       -> '1.0651'   se calcula bien
    tras ir a un día sin registro            -> ''         borrada
    llenar el resto y guardar                -> abortado, 0 filas

El invariante que se fija aquí: *tras cambiar a una fecha sin registro, todo
campo que el físico teclea queda vacío, y todo campo que la app deriva queda
con el valor que le corresponde a ESA fecha.*

Cubre además los dos defectos que `B2` cierra y el tripwire de `B4`:
  - `BQ-3`: sin fuente aplicable a la fecha, el campo queda vacío y el
    método RETORNA -- antes seguía al desempaquetado de un `row` que era
    `None` y reventaba con `TypeError`, tragado por el `except` general.
    Ese `return` es imprescindible para que `B1` pueda recalcular.
    **No** se avisa al físico: el cálculo tiene dos disparadores por cambio
    de fecha, así que un diálogo se vería dos veces, modal. Avisarlo bien es
    deuda registrada (riesgo `R-2` del plan), no parte de esta corrección.
  - `BQ-4`: acepta `QDate` además de `QDateTime` (`QDate` no tiene
    `toPyDateTime()`, y es lo que entrega la señal `dateChanged`).
  - `B4`: ningún campo declarado en `CAMPOS_DERIVADOS_DIARIA` puede
    limpiarse sin que la rama `else` del cargador lo recalcule.

Trampa 2 (CLAUDE.md): todo test de este archivo mockea `QMessageBox` ANTES
de ejercitar nada -- bajo `QT_QPA_PLATFORM=offscreen` un diálogo real cuelga
el proceso para siempre, y estas rutas abren diálogos de verdad.
"""
import ast
import datetime
import io
import math
import os
import pathlib

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate, QDateTime
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
import ui.paginasControles.PruebasDiarias.braquiterapia as braq_mod
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

# La fuente de referencia de este archivo: 10 Ci certificados a medianoche
# del 01-01-2026. Todas las actividades esperadas se derivan de aquí.
FECHA_FUENTE = "2026-01-01 00:00:00"
A0_CI = 10.0
VIDA_MEDIA_DIAS = 73.83  # Ir-192


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialogos(monkeypatch):
    """Trampa 2 + instrumento de medida: sustituye las 4 variantes de
    `QMessageBox` por un registrador. Devuelve la lista de
    `(tipo, titulo, texto)` para poder afirmar CUÁNTOS avisos se vieron y
    con qué contenido -- no solo que no colgó."""
    vistos = []

    def _registrar(tipo):
        def f(*a, **k):
            vistos.append((tipo,
                           a[1] if len(a) > 1 else None,
                           a[2] if len(a) > 2 else None))
            return QMessageBox.Ok
        return staticmethod(f)

    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, _registrar(tipo))
    return vistos


def _bd(monkeypatch, tmp_path, con_fuente=True):
    """BD temporal REAL (esquema completo vía `Conexion()`), nunca una BD de
    referencia. `con_fuente=False` reproduce `BQ-3`: ninguna fila de
    `TipoCalibracion` con `Tipo='Cambio de fuente'`."""
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    if con_fuente:
        conexion.con.execute(
            "INSERT INTO TipoCalibracion (id, user, fecha, tipo, serie, "
            "certificado, fecha_cer, intensidad, conversion, activo) "
            "VALUES (1, 'fisico', ?, 'Cambio de fuente', 'SN1', 1.0, ?, ?, "
            "1.0, 1)",
            (FECHA_FUENTE, FECHA_FUENTE, A0_CI))
    conexion.con.commit()
    conexion.con.close()
    Conexion._instance = None
    return ruta


@pytest.fixture
def bd_con_fuente(monkeypatch, tmp_path):
    return _bd(monkeypatch, tmp_path, con_fuente=True)


@pytest.fixture
def bd_sin_fuente(monkeypatch, tmp_path):
    return _bd(monkeypatch, tmp_path, con_fuente=False)


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def actividad_esperada(momento):
    """Reimplementación INDEPENDIENTE del decaimiento que la app calcula, para
    no comprobar el código contra sí mismo.

    Replica la convención de husos que `calcular_decaimiento`
    (`analisisImagenes/ActividadFuente.py`) documenta y aplica: la fecha del
    CERTIFICADO se interpreta en CET (Europe/Berlin) y la fecha de la MEDIDA
    en COT (America/Bogota) -- 6 h de diferencia el 01-01, que a esta escala
    valen ~0,25 % en la actividad. Sin replicarla, el valor esperado no
    coincidiría, y esa convención es parte del resultado clínico.

    `momento` es un `QDateTime` (o un `QDate`, que se toma a medianoche).
    `R-4`: la app calcula con la HORA que el `date_box` muestra, no con
    medianoche -- un test que asuma medianoche pasa o falla según la hora a
    la que se corra la suite."""
    from zoneinfo import ZoneInfo
    if isinstance(momento, QDateTime):
        f, h = momento.date(), momento.time()
        fin = datetime.datetime(f.year(), f.month(), f.day(),
                                h.hour(), h.minute(), h.second(),
                                tzinfo=ZoneInfo("America/Bogota"))
    else:
        fin = datetime.datetime(momento.year(), momento.month(), momento.day(),
                                tzinfo=ZoneInfo("America/Bogota"))
    inicio = (datetime.datetime.strptime(FECHA_FUENTE, "%Y-%m-%d %H:%M:%S")
              .replace(tzinfo=ZoneInfo("Europe/Berlin")))
    horas = (fin - inicio).total_seconds() / 3600
    lam = math.log(2) / (VIDA_MEDIA_DIAS * 24)
    return A0_CI * math.exp(-lam * horas)


class TestB1FechaSinRegistroRecalculaElCampoDerivado:
    """Integración de verdad: `PruebaDiariaBraq` real, BD temporal real con
    una fuente real. Sin dobles de `QSqlQuery` -- lo que se prueba es el
    comportamiento observable del formulario, no su cableado."""

    def test_lo_tecleado_se_vacia_y_la_actividad_se_recalcula_para_esa_fecha(
            self, app, bd_con_fuente, dialogos):
        d = PruebaDiariaBraq(_UsuarioFalso())
        al_construir = d.line_1_exp_act_ci.text()
        assert al_construir, (
            "precondición: al construir la pantalla la actividad esperada "
            "ya debe estar calculada")
        # el físico llena el resto del formulario para el día en curso
        for campo in ("line_1_rep_act_ci", "line_1_cyc_dummy", "line_1_cyc_rad"):
            getattr(d, campo).setText("7.7")
        d.observaciones.setText("nota del día anterior")

        d.date_box.setDate(QDate(2026, 3, 15))   # día SIN registro

        # (a) lo que el físico teclea queda vacío -- A4 sigue en pie
        for campo in ("line_1_rep_act_ci", "line_1_cyc_dummy", "line_1_cyc_rad"):
            assert getattr(d, campo).text() == "", (
                f"{campo} es dato tecleado: debe quedar vacío en una fecha "
                f"sin registro (A4)")
        assert d.observaciones.text() == ""
        # (b) lo que la app deriva queda con el valor DE ESA FECHA
        texto = d.line_1_exp_act_ci.text()
        assert texto != "", (
            "línea base del defecto (§1 del plan): aquí quedaba '' y el "
            "guardado del control entero abortaba con float('')")
        assert float(texto) == pytest.approx(
            actividad_esperada(d.date_box.dateTime()), rel=1e-3)
        assert texto != al_construir, (
            "no basta con que no esté vacío: debe ser la actividad de la "
            "fecha NUEVA, no la que quedó de la fecha anterior")

    def test_el_valor_es_correcto_llamando_al_cargador_directamente(
            self, app, bd_con_fuente, dialogos):
        """Intuición de garantía de B1: el recálculo vive DENTRO del
        cargador, no colgado de una señal. Se llama al cargador a pelo, sin
        pasar por el `date_box`, y el campo derivado debe quedar bien igual
        -- si dependiera de la señal, aquí quedaría vacío."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        try:
            d.date_box.dateTimeChanged.disconnect()
        except TypeError:
            pass

        d.cargar_dailytest_desde_db(QDate(2026, 5, 10))

        # R-4: el instante es esa fecha con la hora que muestra el date_box,
        # no medianoche -- los dos caminos de recálculo usan el mismo.
        assert float(d.line_1_exp_act_ci.text()) == pytest.approx(
            actividad_esperada(QDateTime(QDate(2026, 5, 10),
                                         d.date_box.time())), rel=1e-3)

    def test_cambiar_solo_la_hora_tambien_recalcula(
            self, app, bd_con_fuente, dialogos):
        """El `date_box` muestra "dd/MM/yyyy HH:mm:ss", así que el físico
        puede cambiar SOLO la hora -- y [medido] un cambio de hora emite
        `dateTimeChanged` pero NO `dateChanged`. Por eso el dueño único
        (`R-1`) se conecta a `dateTimeChanged`, no a `dateChanged`: si se
        cambiara, ajustar la hora dejaría de recalcular."""
        from PyQt5.QtCore import QTime

        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDateTime(QDateTime(QDate(2026, 5, 10), QTime(0, 0, 0)))
        a_medianoche = float(d.line_1_exp_act_ci.text())

        d.date_box.setTime(QTime(23, 0, 0))     # mismo día, otra hora

        a_las_23 = float(d.line_1_exp_act_ci.text())
        assert a_las_23 < a_medianoche, (
            f"la actividad debe decaer también dentro del mismo día: "
            f"medianoche={a_medianoche}, 23:00={a_las_23}")

    def test_un_cambio_de_dia_ejecuta_el_calculo_una_sola_vez(
            self, app, bd_con_fuente, dialogos, monkeypatch):
        """`R-1`: antes colgaban DOS conexiones del mismo `date_box`
        (`dateChanged -> cargador` y `dateTimeChanged -> cálculo`) y cada
        paso de la flecha ejecutaba el decaimiento dos veces -- dos consultas
        y dos conexiones sqlite3. Ahora hay un dueño único que decide."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        veces = []
        original = d.actividad_braq_automatica
        monkeypatch.setattr(
            d, "actividad_braq_automatica",
            lambda *a, **k: (veces.append(1), original(*a, **k))[1])

        d.date_box.setDate(QDate(2026, 5, 10))

        assert len(veces) == 1, (
            f"el cálculo debe correr UNA vez por cambio de fecha, corrió "
            f"{len(veces)}")

    def test_el_instante_es_el_mismo_llegando_por_dia_o_por_hora(
            self, app, bd_con_fuente, dialogos):
        """`R-4`: los dos caminos deben calcular con EL MISMO instante. Antes
        el del cargador normalizaba a medianoche y el de la señal usaba la
        hora real -- el mismo control mostraba dos valores según por dónde se
        llegara."""
        from PyQt5.QtCore import QTime

        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDateTime(QDateTime(QDate(2026, 4, 1), QTime(14, 30, 0)))
        llegando_por_dia = d.line_1_exp_act_ci.text()

        # volver a pedir el mismo instante, ahora por el camino de la hora
        d.date_box.setTime(QTime(14, 30, 1))
        d.date_box.setTime(QTime(14, 30, 0))
        llegando_por_hora = d.line_1_exp_act_ci.text()

        assert llegando_por_dia == llegando_por_hora != "", (
            f"mismo instante, mismo número: por día={llegando_por_dia}, "
            f"por hora={llegando_por_hora}")

    def test_fechas_distintas_dan_actividades_distintas_y_decrecientes(
            self, app, bd_con_fuente, dialogos):
        """Que el campo no quede vacío no basta: tiene que SEGUIR a la fecha.
        Un valor congelado (p. ej. el de construcción) pasaría el test
        anterior por casualidad si la fecha elegida coincidiera."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        valores = []
        for fecha in (QDate(2026, 2, 1), QDate(2026, 5, 10), QDate(2026, 9, 3)):
            d.date_box.setDate(fecha)
            valores.append(float(d.line_1_exp_act_ci.text()))

        assert valores[0] > valores[1] > valores[2], (
            f"la actividad debe decaer con la fecha, se obtuvo {valores}")


class TestB2SinFuenteAplicableAvisaUnaVez:
    """`BQ-3`: antes, sin fila de `TipoCalibracion` anterior a la fecha, el
    código seguía al desempaquetado de un `row` que era `None`, reventaba con
    `TypeError` y el `except Exception` general lo tragaba con un `print`.
    El físico veía el campo vacío y CERO avisos -- el mismo síntoma que el
    defecto principal, por otra causa. Ese `TypeError` es además lo que
    impedía que `B1` recalculara.

    `R-2`: el aviso solo se pudo poner tras unificar el disparador (`R-1`).
    Con las dos conexiones que había sobre el `date_box`, este diálogo se
    veía DOS veces, modal, por cada paso de la flecha del calendario."""

    def test_sin_ninguna_fuente_el_campo_queda_vacio_y_avisa_una_vez(
            self, app, bd_sin_fuente, dialogos):
        d = PruebaDiariaBraq(_UsuarioFalso())
        del dialogos[:]          # lo de la construcción no se cuenta

        d.date_box.setDate(QDate(2026, 3, 15))

        assert d.line_1_exp_act_ci.text() == "", (
            "sin fuente no hay actividad esperada que calcular")
        avisos = [a for a in dialogos if a[0] == "warning"]
        assert len(avisos) == 1, (
            f"debe verse EXACTAMENTE un aviso por paso de la flecha; se "
            f"vieron {len(avisos)}: {avisos}. Dos significan que el cálculo "
            f"volvió a tener dos dueños sobre el mismo `date_box` (R-1)")
        assert avisos[0][1], "el aviso debe tener título"
        assert avisos[0][2] and "fuente" in avisos[0][2].lower(), (
            "el aviso debe nombrar el problema (no hay fuente registrada), "
            "no dejar al físico deduciéndolo de un campo vacío")

    def test_no_avisa_durante_la_construccion(self, app, bd_sin_fuente, dialogos):
        """`R-2`: la llamada de `__init__` pasa `avisar=False` -- corre antes
        de que la ventana exista, y un modal ahí aparecería suelto, sin su
        pantalla detrás."""
        PruebaDiariaBraq(_UsuarioFalso())

        assert not [a for a in dialogos if a[0] == "warning"], (
            f"construir la pantalla no debe abrir diálogos: {dialogos}")

    def test_cinco_pasos_de_la_flecha_dan_cinco_avisos_no_diez(
            self, app, bd_sin_fuente, dialogos):
        """La forma medible de `R-1`: antes de unificar, cada paso disparaba
        el cálculo dos veces y por tanto dos diálogos modales seguidos."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        del dialogos[:]

        for dia in (16, 17, 18, 19, 20):
            d.date_box.setDate(QDate(2026, 3, dia))

        assert len([a for a in dialogos if a[0] == "warning"]) == 5

    def test_fuente_posterior_a_la_fecha_consultada_tambien_avisa(
            self, app, bd_con_fuente, dialogos):
        """La forma exacta que midió el plan: la fuente existe, pero se
        instaló DESPUÉS de la fecha que se está consultando."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        del dialogos[:]

        d.date_box.setDate(QDate(2025, 6, 1))   # anterior a la fuente

        assert d.line_1_exp_act_ci.text() == ""
        assert [a for a in dialogos if a[0] == "warning"], (
            "sin aviso, este caso es indistinguible del defecto original")

    def test_no_se_propaga_ninguna_excepcion(self, app, bd_sin_fuente, dialogos):
        """El `TypeError` de `BQ-3` no debe volver, ni siquiera tragado: se
        llama al método directamente, fuera de cualquier `try` de Qt."""
        d = PruebaDiariaBraq(_UsuarioFalso())

        d.actividad_braq_automatica(QDate(2026, 3, 15))   # no debe lanzar


class TestB2AceptaQDateYQDateTime:
    """`BQ-4`: `cargar_dailytest_desde_db` recibe un `QDate` (lo entrega
    `dateChanged`) y se lo pasa al recálculo. `QDate` no tiene
    `toPyDateTime()`; antes eso era un `AttributeError` tragado por el
    `except` general, y era el detalle que decidía si B1 funcionaba."""

    def test_qdate_puro_no_revienta_y_calcula(self, app, bd_con_fuente, dialogos):
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.line_1_exp_act_ci.setText("")
        del dialogos[:]

        d.actividad_braq_automatica(QDate(2026, 3, 15))

        assert float(d.line_1_exp_act_ci.text()) == pytest.approx(
            actividad_esperada(QDate(2026, 3, 15)), rel=1e-3)
        assert not [a for a in dialogos if a[0] == "warning"], (
            f"un QDate es entrada legítima, no un error: {dialogos}")

    def test_qdate_y_qdatetime_del_mismo_dia_dan_el_mismo_valor(
            self, app, bd_con_fuente, dialogos):
        """La normalización `QDateTime(QDate)` debe ser exactamente la
        medianoche de ese día, no una hora arbitraria: los dos llamadores
        tienen que producir el mismo número clínico."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        fecha = QDate(2026, 3, 15)

        d.actividad_braq_automatica(fecha)
        por_qdate = d.line_1_exp_act_ci.text()
        d.line_1_exp_act_ci.setText("")
        d.actividad_braq_automatica(QDateTime(fecha))
        por_qdatetime = d.line_1_exp_act_ci.text()

        assert por_qdate == por_qdatetime != ""


RUTA_DIARIAS = pathlib.Path(__file__).resolve().parent.parent / "ui" / \
    "paginasControles" / "PruebasDiarias"


def _clases_diarias():
    """Censo AST de TODA clase diaria que declare limpieza al cambiar de
    fecha -- no una lista escrita a mano que se quede atrás."""
    encontradas = []
    for ruta in sorted(RUTA_DIARIAS.glob("*.py")):
        arbol = ast.parse(io.open(ruta, encoding="utf-8").read(), str(ruta))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.ClassDef):
                continue
            metodos = {n.name: n for n in nodo.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            if "_limpiar_widgets_diaria" not in metodos:
                continue
            derivados = None
            for n in nodo.body:
                if (isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name)
                                and t.id == "CAMPOS_DERIVADOS_DIARIA"
                                for t in n.targets)):
                    derivados = ast.literal_eval(n.value)
            encontradas.append((ruta, nodo.name, metodos, derivados))
    return encontradas


def _llama_a(nodo, nombre):
    """Devuelve la lista de statements (con su lineno) que llaman a
    `self.<nombre>(...)` dentro de `nodo`."""
    return [n.lineno for n in ast.walk(nodo)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == nombre
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "self"]


class TestB4NingunCampoDerivadoSeLimpiaSinRecalcularse:
    """Tripwire. Hoy vigila un solo campo; el valor está en que vigile el
    PRÓXIMO que alguien añada -- es lo que habría atrapado esta regresión el
    26-08, el día que se escribió A4, en vez de un día de uso real."""

    def test_hay_al_menos_una_clase_diaria_censada(self):
        """Si el censo se queda vacío (renombre de método, reorganización de
        carpetas), los demás tests de esta clase pasarían por vacuidad."""
        assert _clases_diarias(), (
            "el censo AST no encontró ninguna clase diaria con "
            "`_limpiar_widgets_diaria`: el tripwire estaría inerte")

    def test_toda_clase_con_campos_derivados_los_recalcula_tras_limpiar(self):
        revisadas = 0
        for ruta, clase, metodos, derivados in _clases_diarias():
            if not derivados:
                continue   # sin campos derivados, la limpieza de A4 basta
            revisadas += 1
            cargador = metodos.get("cargar_dailytest_desde_db")
            assert cargador is not None, (
                f"{ruta.name}::{clase} declara CAMPOS_DERIVADOS_DIARIA pero "
                f"no tiene `cargar_dailytest_desde_db` donde recalcularlos")
            limpia = _llama_a(cargador, "_limpiar_widgets_diaria")
            recalcula = _llama_a(cargador, "_recalcular_campos_derivados_diaria")
            assert limpia, (
                f"{ruta.name}::{clase}: `cargar_dailytest_desde_db` no llama "
                f"a `_limpiar_widgets_diaria` (¿se movió la limpieza de A4?)")
            assert recalcula, (
                f"{ruta.name}::{clase} declara los campos derivados "
                f"{sorted(derivados)} pero `cargar_dailytest_desde_db` nunca "
                f"llama a `_recalcular_campos_derivados_diaria`: la limpieza "
                f"de A4 los dejaría vacíos y el guardado del día abortaría")
            assert min(recalcula) > min(limpia), (
                f"{ruta.name}::{clase}: el recálculo debe ir DESPUÉS de la "
                f"limpieza; delante, la limpieza borraría lo recalculado")
        assert revisadas, (
            "ninguna clase diaria declara CAMPOS_DERIVADOS_DIARIA -- si el "
            "atributo desapareció, este tripwire dejó de vigilar nada")

    def test_todo_metodo_declarado_existe_de_verdad(self):
        """`_recalcular_campos_derivados_diaria` protege la llamada con
        `hasattr`: un nombre de método mal escrito no reventaría, no haría
        NADA, y el campo volvería a quedar vacío en silencio."""
        for ruta, clase, _metodos, derivados in _clases_diarias():
            if not derivados:
                continue
            obj = getattr(braq_mod, clase, None)
            if obj is None:
                continue
            for campo, metodo in derivados.items():
                assert callable(getattr(obj, metodo, None)), (
                    f"{clase}.CAMPOS_DERIVADOS_DIARIA declara "
                    f"{campo!r} -> {metodo!r}, pero {metodo!r} no es un "
                    f"método de la clase: el `hasattr` lo saltaría en "
                    f"silencio")

    def test_todo_campo_declarado_es_de_los_que_la_limpieza_vacia(
            self, app, bd_con_fuente, dialogos):
        """La otra mitad: declarar derivado un campo que `_limpiar_widgets_
        diaria` no toca sería ruido, y declarar uno que sí toca sin
        recalcularlo es el defecto. Se mide sobre la instancia real."""
        d = PruebaDiariaBraq(_UsuarioFalso())

        for campo in PruebaDiariaBraq.CAMPOS_DERIVADOS_DIARIA:
            assert campo in d.df_lines, (
                f"{campo!r} se declara derivado pero no está en `df_lines`, "
                f"así que `_limpiar_widgets_diaria` no lo vacía: la "
                f"declaración no vigila nada")

    def test_un_campo_derivado_nuevo_se_recalcula_sin_tocar_el_cargador(
            self, app, bd_con_fuente, dialogos):
        """El tripwire con dientes: el mecanismo tiene que ser GENÉRICO. Se
        añade un campo derivado inventado y debe recalcularse solo. Si
        alguien reescribe la rama `else` llamando a
        `actividad_braq_automatica` a pelo (en vez de recorrer
        `CAMPOS_DERIVADOS_DIARIA`), este test cae."""
        d = PruebaDiariaBraq(_UsuarioFalso())
        llamadas = []
        d._calculo_inventado = lambda momento: llamadas.append(momento)
        d.CAMPOS_DERIVADOS_DIARIA = dict(
            PruebaDiariaBraq.CAMPOS_DERIVADOS_DIARIA,
            line_inventada="_calculo_inventado")

        d.date_box.setDate(QDate(2026, 7, 21))

        assert len(llamadas) == 1, (
            f"un campo derivado declarado debe recalcularse por el solo hecho "
            f"de estar declarado; se llamó {len(llamadas)} veces")
        # R-4: recibe el INSTANTE (fecha + hora del date_box), no un QDate a
        # medianoche -- es lo que hace que ambos caminos den el mismo número.
        assert isinstance(llamadas[0], QDateTime), (
            f"debe recibir un QDateTime, recibió {type(llamadas[0]).__name__}")
        assert llamadas[0].date() == QDate(2026, 7, 21)
        assert float(d.line_1_exp_act_ci.text()) == pytest.approx(
            actividad_esperada(d.date_box.dateTime()), rel=1e-3), (
            "y el campo real debe seguir recalculándose igual")
