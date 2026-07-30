"""F8 (PLAN_F_CIERRE_ESTANDAR_29-07.md §8.4/§9): vigencia derivada, una sola
fuente de verdad.

Antes de F8, `equipos.vigente` se calculaba UNA sola vez al guardar la fila
(alta o edición), contra la fecha de ESE momento, y quedaba congelada para
siempre -- una calibración que vence después de guardarse sigue diciendo
`vigente=1` indefinidamente (medido: 3 filas activas de la BD real, todas
calibradas 05-07/02/2024 con 2 años de vigencia, dicen `vigente=1` pese a
estar vencidas desde febrero de 2026). F8 retira esa columna del contrato de
lectura de los servicios -- `services/vigencia_equipo.py::es_vigente_en_fecha`
es la única fuente, siempre evaluada en el punto de uso contra la fecha que
corresponda (hoy, o la del control que se está llenando).

Esta suite cubre los puntos de prueba del plan que no quedaban ya cubiertos
por `test_v1_vigencia_equipo_servicio.py` (aniversario de calendario, caso
bisiesto) ni por `test_h210_braqui_selector_vigente.py` (contrato nuevo de
`EquiposService`): las tres filas reales de §8.4/§8.3, el filtro de
`obtener_modelos_unicos`, y el tripwire estático de que ningún módulo de
producción lee `equipos.vigente` para decidir o mostrar.
"""
import ast
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.equipos_service import EquiposService
from services.vigencia_equipo import es_vigente_en_fecha


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


def _insertar_equipo(ruta_bd, eq_id, **campos):
    import sqlite3
    con = sqlite3.connect(ruta_bd)
    cols = ["id"] + list(campos)
    marcas = ", ".join("?" * len(cols))
    con.execute(f"INSERT INTO equipos ({', '.join(cols)}) VALUES ({marcas})",
                [eq_id] + list(campos.values()))
    con.commit()
    con.close()


class TestAniversarioDeCalendarioExacto:
    """Reemplaza la aproximación `daysTo <= 365*años` (ver
    test_v1_vigencia_equipo_servicio.py, ya actualizado) por el aniversario
    de calendario real -- este caso bisiesto explícito es el que el plan
    pide (§8.4: calibración 05/02/2024, 2 años) y el único donde ambas
    reglas discrepan por 1 día."""

    def test_caso_bisiesto_05_02_2024_dos_anios(self):
        calibr = "05/02/2024"
        aniversario = QDate(2026, 2, 5)
        un_dia_despues = QDate(2026, 2, 6)
        assert es_vigente_en_fecha(calibr, "Cámara de ionización", aniversario)
        assert not es_vigente_en_fecha(calibr, "Cámara de ionización", un_dia_despues)

    def test_la_aproximacion_365_dias_hubiera_dado_un_dia_antes(self):
        """Documenta la discrepancia: con la regla vieja (730 días exactos
        desde 05/02/2024, atravesando el 29/02/2024 bisiesto) el corte caía
        en 04/02/2026, un día antes del aniversario real."""
        calibr_qdate = QDate(2024, 2, 5)
        corte_regla_vieja = calibr_qdate.addDays(365 * 2)
        assert corte_regla_vieja == QDate(2026, 2, 4)
        corte_regla_nueva = calibr_qdate.addYears(2)
        assert corte_regla_nueva == QDate(2026, 2, 5)
        assert corte_regla_vieja != corte_regla_nueva


class TestCuatroCasosPermisivos:
    """Ya fijados en test_v1_vigencia_equipo_servicio.py; repetidos aquí,
    breves, para que este archivo (el de F8) sea autocontenido según el
    plan."""

    def test_sin_fecha(self):
        assert es_vigente_en_fecha(None, "Cámara de ionización", QDate(2030, 1, 1))

    def test_tipo_desconocido(self):
        assert es_vigente_en_fecha("01/01/2020", "Tipo Inexistente", QDate(2030, 1, 1))

    def test_vigencia_anos_none(self):
        assert es_vigente_en_fecha("01/01/2000", "Detector Rad.", QDate(2030, 1, 1))

    def test_fecha_formato_invalido(self):
        assert es_vigente_en_fecha("no-es-una-fecha", "Cámara de ionización", QDate(2030, 1, 1))


class TestLasTresFilasRealesDeLaDoctrina:
    """§8.4 del plan: las tres filas activas de la BD real que dicen
    `vigente=1` en la columna pero cuya calibración (2 años, 05-07/02/2024)
    ya venció. Se reproducen aquí con datos equivalentes -- la prueba es que
    `es_vigente_en_fecha` da `False` HOY (2026-07-30 en adelante) SIN mirar
    la columna `vigente` en absoluto, y que `EquiposService` ya no la
    devuelve para que nadie la consulte por error."""

    FILAS = [
        (13, "Cámara de ionización", "N30013", "2123", "05/02/2024"),
        (7, "Cámara de ionización", "N31014", "0453", "07/02/2024"),
        (16, "Cámara de pozo", "HDR1000 Plus", "A972662", "07/02/2024"),
    ]

    def _poblar(self, ruta_bd):
        for eq_id, equip_type, model, serie, fecha in self.FILAS:
            _insertar_equipo(ruta_bd, eq_id, equip_type=equip_type, model=model,
                             serie=serie, calibr_fact=1.0, fecha_calibr=fecha,
                             activo=1, vigente=1)

    def test_las_tres_dan_no_vigente_hoy_pese_a_columna_vigente_1(self, bd_temporal):
        self._poblar(bd_temporal)
        hoy = QDate(2026, 7, 30)
        for eq_id, equip_type, model, serie, fecha in self.FILAS:
            assert not es_vigente_en_fecha(fecha, equip_type, hoy), (
                f"id={eq_id} {model}/{serie} debería salir vencida hoy")

    def test_series_actuales_no_expone_la_columna_vigente(self, bd_temporal):
        self._poblar(bd_temporal)
        for eq_id, equip_type, model, serie, fecha in self.FILAS:
            filas = EquiposService.series_actuales(equip_type, model)
            encontrada = [f for f in filas if f[0] == serie]
            assert encontrada, f"{model}/{serie} debería seguir apareciendo (activo=1)"
            assert len(encontrada[0]) == 4  # (serie, activo, fecha_calibr, equip_type) -- sin vigente


class TestFilaActualEligeLaBuenaSobreElDuplicadoInactivo:
    """F8 punto 6 (`_FILA_ACTUAL`): para una serie con la fila buena de id
    menor y un duplicado `activo=0` de id mayor (patrón real de H2.6), se
    elige la buena -- los mismos tres casos de §8.3, pero verificando la
    consulta genérica (agnóstica de qué UI la consuma)."""

    def test_n30013_elige_id_bajo_activo_sobre_duplicado_id_alto_inactivo(self, bd_temporal):
        _insertar_equipo(bd_temporal, 13, equip_type="Cámara de ionización",
                         model="N30013", serie="2123", calibr_fact=0.0545,
                         fecha_calibr="05/02/2024", activo=1, vigente=1)
        _insertar_equipo(bd_temporal, 67, equip_type="Cámara de ionización",
                         model="N30013", serie="2123", calibr_fact=0.545,
                         fecha_calibr="05/02/2025", activo=0, vigente=0)

        datos = EquiposService.calibracion_actual(
            "Cámara de ionización", "N30013", "2123")
        assert datos["calibr_fact"] == 0.0545  # id13, no el duplicado id67

    def test_n31014_elige_id_bajo_activo_sobre_duplicado_id_alto_inactivo(self, bd_temporal):
        _insertar_equipo(bd_temporal, 7, equip_type="Cámara de ionización",
                         model="N31014", serie="0453", calibr_fact=2.40,
                         fecha_calibr="07/02/2024", activo=1, vigente=1)
        _insertar_equipo(bd_temporal, 68, equip_type="Cámara de ionización",
                         model="N31014", serie="0453", calibr_fact=24.0,
                         fecha_calibr="07/02/2025", activo=0, vigente=0)

        datos = EquiposService.calibracion_actual(
            "Cámara de ionización", "N31014", "0453")
        assert datos["calibr_fact"] == 2.40  # id7, no el duplicado id68


class TestObtenerModelosUnicosFiltraActivo:
    def test_modelo_con_solo_fila_inactiva_no_aparece(self, bd_temporal):
        _insertar_equipo(bd_temporal, 1, equip_type="Cámara de ionización",
                         model="ModeloRetirado", serie="X1", calibr_fact=1.0,
                         activo=0, vigente=0)
        _insertar_equipo(bd_temporal, 2, equip_type="Cámara de ionización",
                         model="ModeloActivo", serie="X2", calibr_fact=1.0,
                         activo=1, vigente=1)

        modelos = [m["model"] for m in EquiposService.obtener_modelos_unicos()]
        assert "ModeloActivo" in modelos
        assert "ModeloRetirado" not in modelos


class TestTripwireNingunModuloLeeEquiposVigente:
    """Estático, mismo espíritu que test_a6_1_tripwire_auditoria.py: recorre
    todo el árbol de producción y falla si aparece un sitio NUEVO que lea
    `equipos.vigente` para decidir o mostrar.

    Dos detectores:
    1. SQL: ningún `execute()`/`executemany()` fuera de la allowlist recibe
       un literal `SELECT ... vigente ... FROM equipos` (o viceversa). Los
       3 sitios permitidos están todos en `ui/paginasGuia/equipos.py`: dos
       fetches que ya NO leen la posición de `vigente` en el resultado
       (`cargartabla`, `editarEquipo` -- verificado que ninguno hace
       `r[12]`/`equipo[12]`) y uno que sí la lee para CONSERVARLA sin
       cambios como dato histórico inerte (`guardarCambios`, F8 punto 3).
    2. Acceso por clave: `.get('vigente')`/`['vigente']` sobre un dict de
       EquiposService. El único sitio conocido es `dialogs.py` (calculadora,
       K-fix.4) -- ya inofensivo (la clave nunca llega, `obtener_series_por_
       modelo` ya no la expone) pero migrarlo de verdad es F9 (§9, punto 2
       del plan), no F8. Marcado explícito como PENDIENTE-F9: si aparece en
       CUALQUIER otro archivo, o si desaparece de dialogs.py sin que se
       actualice esta lista, el test debe fallar.
    """

    ROOT = Path(__file__).resolve().parent.parent
    EXCLUDE_DIRS = {
        ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
        "resources", "models", "mcc_PTW_read",
    }

    SQL_PERMITIDO = {
        "ui/paginasGuia/equipos.py",
    }
    ACCESO_POR_CLAVE_PENDIENTE_F9 = {
        "ui/paginasGuia/dialogs.py",
    }

    def _archivos_produccion(self):
        for path in sorted(self.ROOT.rglob("*.py")):
            rel = path.relative_to(self.ROOT)
            if any(parte in self.EXCLUDE_DIRS for parte in rel.parts):
                continue
            yield rel, path

    @staticmethod
    def _literal_str(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            partes = [v.value for v in node.values
                      if isinstance(v, ast.Constant) and isinstance(v.value, str)]
            return "".join(partes) if partes else None
        return None

    def test_ningun_sql_nuevo_lee_vigente_de_equipos(self):
        EXEC_METHODS = {"execute", "executemany"}
        encontrados = set()
        for rel, path in self._archivos_produccion():
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except Exception:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (isinstance(func, ast.Attribute) and func.attr in EXEC_METHODS):
                    continue
                if not node.args:
                    continue
                texto = self._literal_str(node.args[0])
                if texto is None:
                    continue
                bajo = texto.lower()
                if "vigente" in bajo and "equipos" in bajo and "select" in bajo:
                    encontrados.add(str(rel))
        assert encontrados == self.SQL_PERMITIDO, (
            f"SQL nuevo leyendo equipos.vigente fuera de la allowlist: "
            f"{encontrados - self.SQL_PERMITIDO}")

    def test_ningun_archivo_nuevo_lee_vigente_por_clave(self):
        patron = re.compile(r"""\.get\(\s*['"]vigente['"]|\[\s*['"]vigente['"]\s*\]""")
        encontrados = set()
        for rel, path in self._archivos_produccion():
            texto = path.read_text(encoding="utf-8")
            if patron.search(texto):
                encontrados.add(str(rel))
        assert encontrados == self.ACCESO_POR_CLAVE_PENDIENTE_F9, (
            f"Acceso por clave 'vigente' fuera de lo ya inventariado: "
            f"{encontrados - self.ACCESO_POR_CLAVE_PENDIENTE_F9} (nuevo) / "
            f"{self.ACCESO_POR_CLAVE_PENDIENTE_F9 - encontrados} (ya no está, "
            f"actualizar esta allowlist -- probablemente F9 ya lo migró)")

    def test_equipos_service_ya_no_devuelve_vigente_en_su_codigo_fuente(self):
        """Cinturón y tirantes: el propio código fuente de EquiposService no
        debe volver a mencionar `vigente` como columna seleccionada."""
        fuente = Path(
            "services/equipos_service.py").read_text(encoding="utf-8")
        # Los únicos usos legítimos que quedan son en comentarios/docstrings
        # explicando la doctrina (F8/H2.10) -- ninguna línea de código real
        # (no comentario) debe tener "vigente" dentro de una cadena SQL.
        tree = ast.parse(fuente)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "SELECT" in node.value and "vigente" in node.value.lower():
                    pytest.fail(
                        "equipos_service.py todavía selecciona `vigente` en SQL")
