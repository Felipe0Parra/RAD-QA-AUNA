"""E7 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §11): soft-delete integral del
bloque de control de calidad.

Antes de esto, la app tenía CUATRO raíces independientes (`controles`,
`TipoCalibracion`, `LinealidadBraquiterapia`, las 4 diarias) y solo
`controles` tenía soft-delete (C2). El peligro más grave: anular
`TipoCalibracion` arrastraba en cascada `ResultadosActividad` (la actividad
calculada de la fuente de braquiterapia) sin dejar nada recuperable.

`services/anulacion.py::TABLAS_ANULABLES` es la lista blanca cerrada del
inventario del plan (§11.3): 26 tablas nuevas + `controles` (ya la tenía).
`anular_fila()` es el único punto de anulación -- rechaza cualquier tabla
fuera de la lista.
"""
import ast
import sqlite3
from pathlib import Path

import pytest
from PyQt5.QtSql import QSqlDatabase, QSqlQuery
from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.anulacion import TABLAS_ANULABLES, anular_fila

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "models", "mcc_PTW_read",
}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()  # DDL + TODAS las migraciones reales (incl. E7)
    yield ruta
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture
def db_qt(bd_temporal):
    """Conexión QSqlDatabase abierta contra la BD temporal -- mismo objeto
    que `anular_fila` espera recibir (patrón de eliminarRegistro/eliminarfilas)."""
    nombre = "conexion_test_e7"
    if QSqlDatabase.contains(nombre):
        QSqlDatabase.removeDatabase(nombre)
    db = QSqlDatabase.addDatabase("QSQLITE", nombre)
    db.setDatabaseName(bd_temporal)
    assert db.open()
    yield db
    db.close()
    QSqlDatabase.removeDatabase(nombre)


def _con(ruta):
    return sqlite3.connect(ruta)


def _abrir_conexion_default(ruta):
    """`load_table` construye `QSqlQuery(sql)` SIN pasar una conexión
    explícita -- Qt usa la conexión de nombre "qt_sql_default_connection".
    Mismo patrón real de `PruebaBasico.opeenDatabase()` (mensual: `addDatabase
    ("QSQLITE")` sin nombre = default)."""
    if not QSqlDatabase.contains("qt_sql_default_connection"):
        db = QSqlDatabase.addDatabase("QSQLITE")
    else:
        db = QSqlDatabase.database("qt_sql_default_connection")
    db.setDatabaseName(ruta)
    db.open()
    return db


class TestInventarioYEsquema:
    def test_todas_las_tablas_del_inventario_existen(self, bd_temporal):
        con = _con(bd_temporal)
        try:
            tablas_reales = {
                r[0] for r in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()
        faltantes = TABLAS_ANULABLES - tablas_reales
        assert faltantes == set(), f"tablas del inventario ausentes del esquema: {faltantes}"

    def test_todas_tienen_columna_activo(self, bd_temporal):
        con = _con(bd_temporal)
        try:
            sin_activo = []
            for tabla in sorted(TABLAS_ANULABLES):
                cols = {c[1] for c in con.execute(f"PRAGMA table_info('{tabla}')")}
                if "activo" not in cols:
                    sin_activo.append(tabla)
        finally:
            con.close()
        assert sin_activo == [], f"tablas del inventario sin 'activo': {sin_activo}"

    def test_migracion_es_idempotente(self, bd_temporal):
        conexion = Conexion()  # misma instancia (singleton), pero probamos el método
        conexion._asegurar_activo_bloque_qc()
        conexion._asegurar_activo_bloque_qc()
        con = _con(bd_temporal)
        try:
            for tabla in sorted(TABLAS_ANULABLES - {"controles"}):
                n = con.execute(f"SELECT COUNT(*) FROM pragma_table_info('{tabla}') "
                                "WHERE name='activo'").fetchone()[0]
                assert n == 1, f"{tabla}: 'activo' duplicada o ausente tras 2 corridas"
        finally:
            con.close()

    def test_filas_existentes_nacen_activas_sin_ningun_update(self, bd_temporal):
        """DEFAULT 1 -- coste cero, no reescribe ninguna fila existente."""
        con = _con(bd_temporal)
        try:
            con.execute(
                "INSERT INTO TipoCalibracion (user, fecha, tipo) "
                "VALUES ('Prueba', '01/01/2026', 'Cambio de fuente')")
            con.commit()
            activo = con.execute(
                "SELECT activo FROM TipoCalibracion").fetchone()[0]
        finally:
            con.close()
        assert activo == 1


class TestAnularFilaListaBlanca:
    def test_rechaza_tabla_fuera_de_la_lista_blanca(self, app, db_qt):
        with pytest.raises(ValueError, match="lista blanca"):
            anular_fila(db_qt, "users", 1, "Físico de Prueba")

    def test_rechaza_tabla_inventada(self, app, db_qt):
        with pytest.raises(ValueError):
            anular_fila(db_qt, "tabla_que_no_existe", 1, "Físico de Prueba")


class TestInvarianteCentral:
    """Para cada tabla del inventario, anular una fila la deja presente
    (COUNT(*) constante) con activo = 0."""

    @pytest.mark.parametrize("tabla,columnas_extra", [
        ("controles", "equipo, control, fecha"),
        ("TipoCalibracion", "user, fecha, tipo"),
        ("LinealidadBraquiterapia", "user, fecha"),
        ("aceleradorlineal_600", "date, user_id"),
        ("aceleradorlineal_ix", "date, user_id"),
        ("halcyon", "date, user_id"),
        ("braqui", "date, user_id"),
    ])
    def test_anular_raiz_preserva_la_fila(self, app, bd_temporal, db_qt, tabla, columnas_extra):
        con = _con(bd_temporal)
        valores = ", ".join(["'x'"] * len(columnas_extra.split(",")))
        cur = con.execute(f"INSERT INTO {tabla} ({columnas_extra}) VALUES ({valores})")
        id_fila = cur.lastrowid
        con.commit()
        con.close()

        anular_fila(db_qt, tabla, id_fila, "Físico de Prueba")

        con = _con(bd_temporal)
        try:
            n, activo = con.execute(
                f"SELECT COUNT(*), MAX(activo) FROM {tabla} WHERE id = ?",
                (id_fila,)).fetchone()
        finally:
            con.close()
        assert n == 1
        assert activo == 0


class TestCasoGraveTipoCalibracion:
    """El peligro #1 del plan: anular un TipoCalibracion NO borra ni una
    fila de sus 5 hijas, y todas siguen consultables."""

    HIJAS = ["SistemaMedicion", "CondicionesMedicion", "MaximosCamaras",
             "LecturasMaximos", "ResultadosActividad"]

    def test_anular_no_borra_ninguna_hija(self, app, bd_temporal, db_qt):
        con = _con(bd_temporal)
        cur = con.execute(
            "INSERT INTO TipoCalibracion (user, fecha, tipo) "
            "VALUES ('Prueba', '01/01/2026', 'Cambio de fuente')")
        ref = cur.lastrowid
        for hija in self.HIJAS:
            con.execute(f"INSERT INTO {hija} (ref, user, fecha) VALUES (?, 'Prueba', '01/01/2026')", (ref,))
        con.commit()
        con.close()

        anular_fila(db_qt, "TipoCalibracion", ref, "Físico de Prueba")

        con = _con(bd_temporal)
        try:
            for hija in self.HIJAS:
                n = con.execute(f"SELECT COUNT(*) FROM {hija} WHERE ref = ?", (ref,)).fetchone()[0]
                assert n == 1, f"{hija}: se perdió una fila al anular el padre"
            activo_padre = con.execute(
                "SELECT activo FROM TipoCalibracion WHERE id = ?", (ref,)).fetchone()[0]
        finally:
            con.close()
        assert activo_padre == 0


class TestD5NingunDeleteAlcanzableSobreDosimetria:
    """D5: ni dosimetriaMen, ni HC_dosimetria_anual, ni
    calculadora_dosimetrica tienen un DELETE alcanzable en producción."""

    TABLAS_PROHIBIDAS = ("dosimetriaMen", "HC_dosimetria_anual", "calculadora_dosimetrica")

    def _archivos_produccion(self):
        for p in ROOT.rglob("*.py"):
            if any(parte in EXCLUDE_DIRS for parte in p.relative_to(ROOT).parts):
                continue
            yield p

    def test_sin_delete_literal_sobre_las_tablas_sensibles(self):
        import re
        patron = re.compile(
            r"DELETE\s+FROM\s+[\"']?(" + "|".join(self.TABLAS_PROHIBIDAS) + r")\b",
            re.IGNORECASE)
        hallazgos = []
        for archivo in self._archivos_produccion():
            texto = archivo.read_text(encoding="utf-8")
            for m in patron.finditer(texto):
                hallazgos.append((str(archivo.relative_to(ROOT)), m.group(1)))
        assert hallazgos == [], f"DELETE alcanzable sobre tabla sensible: {hallazgos}"


class TestCT3NingunDeleteAlcanzableSobreGrupoC:
    """CT3 (PLAN_CONTRATO_GUARDADO_13-08.md §6-CT3): extiende la garantía de
    TestD5 (arriba, escrita para dosimetriaMen/HC_dosimetria_anual) a las 17
    tablas del grupo C -- las que loadtablacomplex versiona desde CT2.
    Mismo mecanismo: ningún archivo de producción puede tener un DELETE
    FROM literal sobre estas tablas. Encontró un sitio real al escribirse
    (guardar_analisis_placa600, un guardado de análisis de placa aparte de
    loadtablacomplex, con su propio DELETE de analisis_placa_franjas) --
    ya corregido; este test evita que vuelva."""

    TABLAS_GRUPO_C = (
        "tamano_campo", "analisis_placa_franjas",
        "tabla_factor_campo", "tabla_factores_transmision",
        "tabla_factores_sobre_eje", "tabla_control_camaras_monitoras",
        "HC_indicadores_brazo", "HC_indicadores_colimador", "HC_indicadores_laser",
        "HC_indicadores_camilla", "HC_desplazamiento_isocentro_mensual",
        "HC_velocidad_multilaminas_anual", "HC_precision_posicion_multilaminas_anual",
        "HC_imagen_perfil_mlc_anual", "HC_dosimetria_anual",
        "HC_linealidad_unidades_monitor_anual", "HC_tamanos_campo_radiacion",
    )

    def _archivos_produccion(self):
        for p in ROOT.rglob("*.py"):
            if any(parte in EXCLUDE_DIRS for parte in p.relative_to(ROOT).parts):
                continue
            yield p

    def test_sin_delete_literal_sobre_el_grupo_c(self):
        import re
        patron = re.compile(
            r"DELETE\s+FROM\s+[\"']?(" + "|".join(self.TABLAS_GRUPO_C) + r")\b",
            re.IGNORECASE)
        hallazgos = []
        for archivo in self._archivos_produccion():
            texto = archivo.read_text(encoding="utf-8")
            for m in patron.finditer(texto):
                linea = texto[:m.start()].count("\n") + 1
                hallazgos.append((str(archivo.relative_to(ROOT)), linea, m.group(1)))
        assert hallazgos == [], f"DELETE alcanzable sobre tabla del grupo C: {hallazgos}"


class TestTripwireDeAlcance:
    """Toda tabla que reciba una ruta de borrado nueva (verificar_eliminar/
    eliminarRegistro/_mostrar_dialogo/crear_ventanas_emergentes_tablas) debe
    estar en TABLAS_ANULABLES. Escaneo estático: literales de texto pasados
    a estas 4 funciones en cualquier archivo de producción."""

    FUNCIONES_CON_TABLA = {
        "verificar_eliminar", "eliminarRegistro", "_mostrar_dialogo",
        "crear_ventanas_emergentes_tablas",
    }
    # Tablas de detalle que YA salían con DELETE físico legítimo antes de E7
    # y NO pertenecen al bloque de anulación (no tienen `activo`, y su borrado
    # sigue auditado como ACCION_ELIMINAR -- A2). Ninguna se ha encontrado
    # hasta ahora (ver docstring de la clase), esta lista queda para que un
    # caso legítimo futuro se declare aquí en vez de romper el test a ciegas.
    EXCEPCIONES_DELETE_FISICO_LEGITIMO = frozenset()

    @staticmethod
    def _literal_str(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    def _nombre_llamada(self, node):
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return None

    def _tablas_referenciadas(self):
        encontradas = {}  # tabla -> (archivo, linea)
        for p in ROOT.rglob("*.py"):
            if any(parte in EXCLUDE_DIRS for parte in p.relative_to(ROOT).parts):
                continue
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if self._nombre_llamada(node) not in self.FUNCIONES_CON_TABLA:
                    continue
                candidatos = [self._literal_str(a) for a in node.args] + \
                             [self._literal_str(kw.value) for kw in node.keywords]
                for texto in candidatos:
                    if texto and texto not in encontradas:
                        encontradas[texto] = (str(p.relative_to(ROOT)), node.lineno)
        return encontradas

    def test_toda_tabla_alcanzada_esta_en_la_lista_blanca_o_declarada(self):
        encontradas = self._tablas_referenciadas()
        sin_explicar = {
            tabla: sitio for tabla, sitio in encontradas.items()
            if tabla not in TABLAS_ANULABLES
            and tabla not in self.EXCEPCIONES_DELETE_FISICO_LEGITIMO
        }
        assert sin_explicar == {}, (
            "Tabla(s) alcanzable(s) por una ruta de borrado, fuera de "
            "TABLAS_ANULABLES y sin excepción declarada -- añádela a "
            "services/anulacion.py::TABLAS_ANULABLES (si debe anular) o a "
            "EXCEPCIONES_DELETE_FISICO_LEGITIMO de este test (si el DELETE "
            f"físico es legítimo y ya auditado):\n{sin_explicar}")


def _reset_qtsql_default_connection():
    # "qt_sql_default_connection" es un registro GLOBAL de proceso (no por
    # test) -- mismo patrón de aislamiento que test_a2_auditar_borrado.py /
    # test_w2_foreign_keys_produccion_real.py.
    if QSqlDatabase.contains("qt_sql_default_connection"):
        QSqlDatabase.database("qt_sql_default_connection").close()
        QSqlDatabase.removeDatabase("qt_sql_default_connection")


class TestListados:
    """Una fila anulada no aparece en la consulta de listado correspondiente."""

    @pytest.fixture(autouse=True)
    def _aislar_qtsql(self):
        _reset_qtsql_default_connection()
        yield
        _reset_qtsql_default_connection()

    def test_diarias_load_table_oculta_fila_anulada(self, app, bd_temporal):
        from data.GraficasyTablas.tablas import load_table

        class _WidgetFalso:
            pass

        con = _con(bd_temporal)
        con.execute(
            "INSERT INTO aceleradorlineal_600 (date, user_id) VALUES ('01/07/2026', 'x')")
        con.execute(
            "INSERT INTO aceleradorlineal_600 (date, user_id, activo) VALUES ('02/07/2026', 'x', 0)")
        con.commit()
        con.close()

        w = _WidgetFalso()
        from PyQt5.QtWidgets import QTableWidget
        w.table = QTableWidget()
        w.opeenDatabase = lambda: _abrir_conexion_default(bd_temporal)

        load_table(w, boolean_keys=set(), dosis=None, maquina="aceleradorlineal_600")

        assert w.table.rowCount() == 1
        fechas = [w.table.item(0, c).text() for c in range(w.table.columnCount())
                  if w.table.item(0, c) is not None]
        assert "02/07/2026" not in fechas

    def test_diarias_load_table_oculta_columna_activo(self, app, bd_temporal):
        """MI0 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI0): antes se traía
        'activo' con SELECT * y se ocultaba después con setColumnHidden;
        ahora directamente no se selecciona -- ni siquiera aparece como
        columna. Mismo resultado observable para el físico (no la ve),
        conseguido sin traerla nunca de la BD."""
        from data.GraficasyTablas.tablas import load_table

        con = _con(bd_temporal)
        # "halcyon", no "braqui": esta última dispara una conexión de señal
        # (verificar_columna_pelicula) ajena a lo que prueba este test.
        con.execute("INSERT INTO halcyon (date, user_id) VALUES ('01/07/2026', 'x')")
        con.commit()
        con.close()

        class _WidgetFalso:
            pass
        from PyQt5.QtWidgets import QTableWidget
        w = _WidgetFalso()
        w.table = QTableWidget()
        w.opeenDatabase = lambda: _abrir_conexion_default(bd_temporal)

        load_table(w, boolean_keys=set(), dosis=None, maquina="halcyon")

        headers = [w.table.horizontalHeaderItem(c).text().lower()
                   for c in range(w.table.columnCount())]
        assert "activo" not in headers

    def test_tipocalibracion_anual_generico_oculta_fila_anulada(self, bd_temporal):
        from data.ManejoDatos.Tablas_Anuales.tablas_anuales import buscar_datos_db

        con = _con(bd_temporal)
        cur = con.execute(
            "INSERT INTO controles (equipo, control, fecha) VALUES ('Halcyon', 'Anual', '01/2026')")
        ref = cur.lastrowid
        con.execute(
            "INSERT INTO HC_indicadores_brazo (ref, nivel) VALUES (?, '0')", (ref,))
        con.execute(
            "INSERT INTO HC_indicadores_brazo (ref, nivel, activo) VALUES (?, '90', 0)", (ref,))
        con.commit()
        con.close()

        datos = buscar_datos_db("HC_indicadores_brazo", "Halcyon", "nivel", ref)
        assert datos == [(0.0,)]  # `nivel` es REAL por afinidad de columna

    def test_mensual_equipos_medicion_oculta_fila_anulada(self, bd_temporal):
        con = _con(bd_temporal)
        cur = con.execute(
            "INSERT INTO controles (equipo, control, fecha) VALUES ('Clinac 600', 'Mensual', '01/2026')")
        ref = cur.lastrowid
        con.execute(
            "INSERT INTO equipos_medicion (ref, equip_type) VALUES (?, 'Activa')", (ref,))
        con.execute(
            "INSERT INTO equipos_medicion (ref, equip_type, activo) VALUES (?, 'Anulada', 0)", (ref,))
        con.commit()
        con.close()

        con2 = _con(bd_temporal)
        try:
            filas = con2.execute(
                "SELECT equip_type FROM equipos_medicion WHERE ref=? "
                "AND (activo IS NULL OR activo = 1)", (ref,)).fetchall()
        finally:
            con2.close()
        assert filas == [("Activa",)]
