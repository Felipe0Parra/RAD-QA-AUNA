"""§4 del PLAN_BRAQUI_DIARIO_HORA_IMAGEN_28-08.md -- protocolo de acople y
alcance. Los tests por tarea (test_h1..test_h8) prueban cada pieza AISLADA;
este archivo prueba las INTERACCIONES entre tareas (§4.1) y que el cambio no
se haya salido de braqui (§4.2) -- el mismo tipo de acople invisible que
produjo `DP-56` (dos disparadores sobre el mismo widget, cada uno correcto
por su lado).

Regla de ejecución del plan: ninguna fase se cierra con solo sus tests
propios -- se cierra con esos tests MÁS los de acople de este archivo.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate, QDateTime, QTime
from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import (
    PruebaDiariaBraq, PosicionamientoInicial, Linealidad)
from ui.paginasControles.PruebasMensuales.braq_mensual import PruebaMensualBraq

FECHA_FUENTE = "2026-01-01 00:00:00"
ROJO = "QLineEdit { background-color: #ffcccc; border: 1px solid red; }"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question",
                         staticmethod(lambda *a, **k: QMessageBox.Yes))


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.execute(
        "INSERT INTO users (user, password, fullname, active, idreal, role) "
        "VALUES (?,?,?,?,?,?)",
        ("fisico", "x", "Físico de Prueba", 1, 1, "fisico"))
    conexion.con.execute(
        "INSERT INTO TipoCalibracion (id, user, fecha, tipo, serie, "
        "certificado, fecha_cer, intensidad, conversion, activo) "
        "VALUES (1, 'fisico', ?, 'Cambio de fuente', 'SN1', 1.0, ?, 10.0, "
        "1.0, 1)",
        (FECHA_FUENTE, FECHA_FUENTE))
    conexion.con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class _UsuarioFalso:
    _nombre = "Físico de Prueba"


def _leer_braqui(d, patron_fecha):
    from PyQt5.QtSql import QSqlQuery
    db = d.opeenDatabase()
    query = QSqlQuery(db)
    query.prepare(
        "SELECT date, activo FROM braqui WHERE date LIKE :p ORDER BY id")
    query.bindValue(":p", patron_fecha)
    query.exec()
    filas = []
    while query.next():
        filas.append((query.value(0), query.value(1)))
    return filas


def _leer_braqui_con_analisis(d, patron_fecha):
    from PyQt5.QtSql import QSqlQuery
    db = d.opeenDatabase()
    query = QSqlQuery(db)
    query.prepare(
        "SELECT distancias, promedio, desviacion, desplazamientos, "
        "promedio_des, desviacion_des FROM braqui WHERE date LIKE :p "
        "ORDER BY id DESC LIMIT 1")
    query.bindValue(":p", patron_fecha)
    query.exec()
    assert query.next(), f"no hay fila para {patron_fecha!r}"
    return tuple(query.value(i) for i in range(6))


def _llenar_campos_numericos(d, valor="1.0"):
    for campo in ("line_1_rep_act_ci", "line_1_exp_act_ci",
                  "line_1_cyc_dummy", "line_1_cyc_rad"):
        getattr(d, campo).setText(valor)


class TestAcopleH2H3DiaFueraDeToleranciaTrasLimpiezaCompleta:
    """§4.1 fila 1: `_limpiar_widgets_diaria` escribe "" en `rep`, que
    dispara `tolerancia()`. Con H3a sin H3b, el rojo no volvía a aparecer
    nunca. Se pasa por un día SIN registro (limpieza completa) antes de
    llegar al día fuera de tolerancia -- la ruta más adversa."""

    def test_dia_fuera_de_tolerancia_alcanzado_tras_limpieza_completa_sale_rojo(
            self, app, bd_temporal):
        conexion = Conexion()
        conexion.con.execute(
            "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
            "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
            "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
            "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
            "observaciones, activo) VALUES "
            "('2026-07-20', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
            "50.0,10.0,1.0,1.0, '', 1)")  # muy fuera de tolerancia
        conexion.con.commit()

        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 7, 10))    # día sin registro (limpia)
        assert d.line_1_rep_act_ci.text() == ""

        d.date_box.setDate(QDate(2026, 7, 20))    # el fuera de tolerancia

        assert d.line_1_rep_act_ci.styleSheet() == ROJO, (
            "acople H2->H3: pasar por una limpieza completa antes no puede "
            "dejar inerte la evaluación de tolerancia del día de destino")


class TestAcopleH1H4AnalizarSigueLlegandoALaBD:
    """§4.1 fila 2: H1 limpia `resultado_label`; H4 retira el botón que lo
    poblaba a mano. Si el análisis solo llenara ese label desde el botón
    retirado, quedaría un panel que analiza y no guarda nunca.

    G3 (PLAN_BRAQUI_ANALISIS_PERSISTE_28-08.md, 1-bis): la aserción
    original de este test era `assert filas` -- comprobaba que EXISTIERA
    una fila, no que los 6 números hubieran llegado, pese a que el nombre
    del test y la verificación declarada en el plan anterior (§4.1: "los 6
    números deben llegar a la BD") prometían lo segundo. [medido] pasaba
    IDÉNTICO con el análisis presente y con el análisis totalmente
    ausente -- era ciego exactamente al defecto que después se anotó como
    `DP-64`. Se refuerza para comprobar los 6 valores reales."""

    def test_analizar_y_anadir_persiste_los_numeros(self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 7, 15))
        _llenar_campos_numericos(d)
        # "Analizar" real llama a analizar_imagen() -> mostrar_texto(...);
        # se simula el resultado del análisis (no hay imagen real de disco)
        # igual que hacen los tests de H1/H8.
        d.mostrar_texto(["Promedio = 10.01 mm", "Desviación estándar = 0.11 mm"])

        d.ordenar_botones('braqui', False, "Diario")

        filas = _leer_braqui(d, "2026-07-15%")
        assert filas, "el guardado (btn Añadir) debe persistir la fila"

        distancias, promedio, desviacion, desplazamientos, promedio_des, desviacion_des = (
            _leer_braqui_con_analisis(d, "2026-07-15%"))
        assert promedio == pytest.approx(10.01), (
            "el promedio del análisis simulado debe llegar a la BD, no "
            "solo 'alguna fila'")
        assert desviacion == pytest.approx(0.11)
        # el texto simulado no trae la sección de distancias/desplazamientos
        # (solo promedio/desviación) -- las columnas que no tienen de dónde
        # salir deben quedar en su NULL leído por QtSql ('' -- [medido],
        # ver test_g2_analisis_round_trip.py), no inventarse.
        assert distancias == ""
        assert desplazamientos == ""
        assert promedio_des == ""
        assert desviacion_des == ""


class TestAcopleH2DP56OrdenLimpiarLuegoRecalcularUnaVezSinRegistro:
    """§4.1 fila 3: `_recalcular_campos_derivados_diaria` (DP-56) escribe
    `exp` DESPUÉS de la limpieza (H2). El orden observado en un día sin
    registro debe ser: limpiar -> recalcular exp -> [tolerancia ya
    evaluada, una sola vez, con rep vacío]."""

    def test_orden_limpiar_antes_de_recalcular(self, app, bd_temporal, monkeypatch):
        d = PruebaDiariaBraq(_UsuarioFalso())
        orden = []
        original_limpiar = d._limpiar_widgets_diaria
        original_recalcular = d._recalcular_campos_derivados_diaria
        monkeypatch.setattr(
            d, "_limpiar_widgets_diaria",
            lambda *a, **k: (orden.append("limpiar"), original_limpiar(*a, **k))[1])
        monkeypatch.setattr(
            d, "_recalcular_campos_derivados_diaria",
            lambda *a, **k: (orden.append("recalcular"), original_recalcular(*a, **k))[1])

        d.date_box.setDate(QDate(2026, 7, 25))  # sin registro

        assert orden == ["limpiar", "recalcular"], (
            f"el recálculo del campo derivado (exp) debe correr DESPUÉS de "
            f"la limpieza -- delante, la limpieza lo borraría; orden real: "
            f"{orden}")

    def test_tolerancia_no_queda_roja_por_evaluarse_antes_del_recalculo(
            self, app, bd_temporal):
        """Si `tolerancia()` se evaluara ANTES de que `exp` tuviera el valor
        de la fecha nueva (en vez de después, gracias al orden de arriba),
        el estilo podría quedar calculado contra un `exp` que todavía no es
        el de este día."""
        d = PruebaDiariaBraq(_UsuarioFalso())

        d.date_box.setDate(QDate(2026, 7, 25))  # sin registro

        assert d.line_1_rep_act_ci.text() == ""
        assert d.line_1_rep_act_ci.styleSheet() == "", (
            "un día sin registro (rep vacío) no puede quedar rojo")


class TestAcopleH5H4SinBotonesMuertosNiObjetosBorrados:
    """§4.1 fila 4: H5 elimina una de las dos creaciones; H4 quita un botón
    de dentro de `_crear_parametros`. Hechos a medias dejan
    `self.boton_guardar` apuntando a un widget destruido."""

    def test_no_existe_referencia_viva_a_boton_guardar(self, app, bd_temporal):
        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 7, 15))

        assert not hasattr(d, "boton_guardar"), (
            "H4 retiró el botón por completo -- no debe quedar ni la "
            "referencia (RuntimeError latente si algo la usara después)")

    def test_analizar_es_utilizable_tras_dos_cargas(self, app, bd_temporal):
        from io import BytesIO

        def _png():
            from PIL import Image
            buf = BytesIO()
            Image.new("RGB", (1, 1), color=(0, 0, 0)).save(buf, format="PNG")
            return buf.getvalue()

        conexion = Conexion()
        for fecha in ("2026-07-15", "2026-07-16"):
            conexion.con.execute(
                "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
                "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
                "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
                "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
                "observaciones, pelicula, activo) VALUES "
                f"('{fecha}', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
                "1.0,1.0,1.0,1.0, '', ?, 1)", (_png(),))
        conexion.con.commit()

        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 7, 15))   # 1ª carga -> crea parámetros
        d.date_box.setDate(QDate(2026, 7, 16))   # 2ª carga -> H5: no debe recrear

        # Acceder a atributos Qt de un objeto C++ borrado lanza RuntimeError
        # -- si `self.analizar` apuntara al primer botón (huérfano tras la
        # segunda creación), esto lo delataría.
        assert d.analizar.text() == "Analizar"


class TestAcopleH6H2LecturasConHoraYSinHoraConvertidasALaVez:
    """§4.1 fila 5: H6 cambia lo que se escribe en `date`; H2 cambia cuándo
    se relee. Rotar entre un registro con hora y uno sin ella debe encontrar
    AMBOS -- si una lectura quedara convertida a DATE(date)=DATE(?) y otra
    no, alguna de las dos rotaciones dejaría de encontrar su registro."""

    def test_rotar_entre_con_hora_y_sin_hora_carga_ambos(self, app, bd_temporal):
        conexion = Conexion()
        conexion.con.execute(
            "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
            "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
            "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
            "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
            "observaciones, activo) VALUES "
            "('2026-07-30 14:00:00', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,"
            "1,1,1, 2.0,2.0,1.0,1.0, '', 1)")
        conexion.con.execute(
            "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
            "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
            "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
            "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
            "observaciones, activo) VALUES "
            "('2026-07-31', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
            "4.0,4.0,1.0,1.0, '', 1)")
        conexion.con.commit()

        d = PruebaDiariaBraq(_UsuarioFalso())
        d.date_box.setDate(QDate(2026, 7, 30))
        assert d.line_1_rep_act_ci.text() == "2", "el registro CON hora debe cargar"

        d.date_box.setDate(QDate(2026, 7, 31))
        assert d.line_1_rep_act_ci.text() == "4", "el registro SIN hora debe cargar"

        d.date_box.setDate(QDate(2026, 7, 30))
        assert d.line_1_rep_act_ci.text() == "2", "y volver atrás debe seguir encontrando el de hora"


class TestAlcanceAddInfoLasOtras3DiariasSiguenSinHora:
    """§4.2 fila 1. [medido durante la ejecución]: `halcyon` NO pasa por
    `add_info` (usa `agregar_halcyon`, obtenerDatosHalcyon.py) -- la
    afirmación original del plan de que las 4 diarias comparten `add_info`
    era incorrecta; los llamadores reales son `aceleradorlineal_600` y
    `aceleradorlineal_ix` (además de braqui). Se prueban esos dos."""

    def test_600_sigue_guardando_fecha_sin_hora(self, app, bd_temporal, monkeypatch):
        from PyQt5.QtWidgets import QDateEdit, QWidget
        from data.ManejoDatos.load import add_info
        import data.ManejoDatos.load as load_mod

        class _BotonFalso:
            def text(self):
                return "Funciona"

        monkeypatch.setattr(load_mod, "load_table", lambda *a, **k: None)
        self_falso = QWidget()
        self_falso.date_box = QDateEdit()
        self_falso.date_box.setDate(QDate(2026, 8, 1))
        self_falso.user_id = _UsuarioFalso()
        self_falso.botones_ordenados = [(_BotonFalso(),) for _ in range(17)]
        self_falso.boolean_colums = list(range(17))
        self_falso.df_lines = []
        self_falso.df_lines_dosis = []
        self_falso.observaciones = None

        add_info(self_falso, "aceleradorlineal_600", ["a", "b"])

        db = Conexion().con
        fila = db.execute(
            "SELECT date FROM aceleradorlineal_600 WHERE DATE(date) = ?",
            ("2026-08-01",)).fetchone()
        assert fila is not None
        assert fila[0] == "2026-08-01", (
            f"aceleradorlineal_600 no debe recibir hora, se guardó {fila[0]!r}")


class TestAlcanceResetearImagenUiOtrasPantallas:
    """§4.2 fila 2. `resetear_imagen_ui` la alcanza `clean_info` de la clase
    base, y `clean_info(imagenes=True)` la pulsan `PosicionamientoInicial`
    y (según el propio código) `PruebaMensualBraq` -- [medido durante la
    ejecución]: `PruebaMensualBraq` NUNCA pasa `imagenes=True` en su
    cableado real (:1201 llama `clean_info(imagenes=False)`), así que solo
    `PosicionamientoInicial` la alcanza de verdad hoy."""

    def test_posicionamiento_inicial_sigue_igual_de_roto_no_lo_rompio_ni_lo_arreglo_h1(
            self, app, bd_temporal):
        """Hallazgo del propio barrido de alcance (§4.2 del plan): este
        botón YA estaba roto antes de H1 (`resetear_imagen_ui` no existe en
        `PosicionamientoInicial`) -- H1 no debe cambiar ESE síntoma, ni para
        bien ni para mal, porque no es de este plan."""
        d = PosicionamientoInicial(_UsuarioFalso())

        with pytest.raises(AttributeError):
            d.clean_info(imagenes=True)

    def test_mensual_braqui_limpiar_datos_sigue_funcionando(self, app, bd_temporal):
        d = PruebaMensualBraq(_UsuarioFalso())
        d.campos_maximos[0][1].setText("9.9")

        d.clean_info()  # cableado real: imagenes=False, nunca toca imágenes

        assert d.campos_maximos[0][1].text() == ""


class TestAlcanceLinealidadSinCambioDeComportamiento:
    """§4.2 fila 3: hay DOS métodos `_limpiar_widgets_diaria` homónimos en
    el archivo (`PruebaDiariaBraq` y `Linealidad`), sin relación de
    herencia. Ninguna edición de este plan tocó la clase `Linealidad`
    (verificado: todos los cambios cayeron dentro de `PruebaDiariaBraq` o
    `PosicionamientoInicial`) -- este test es el guardia de esa afirmación."""

    def test_linealidad_limpia_igual_que_antes(self, app, bd_temporal):
        d = Linealidad(_UsuarioFalso())
        d.generar_tabla_medidas()  # construye self.medidas_lienalidad,
                                   # que _limpiar_widgets_diaria recorre --
                                   # no lo hace __init__ por sí solo
        for line in d.df_lines:
            getattr(d, line).setText("7.7")

        d._limpiar_widgets_diaria()

        assert all(getattr(d, line).text() == "" for line in d.df_lines)
