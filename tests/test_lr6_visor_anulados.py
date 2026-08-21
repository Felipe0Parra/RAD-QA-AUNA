"""LR6 (PLAN_CONTRATO_COMPLETO_19-08.md §6-LR6, [[DA-49]]): visor de solo
lectura de registros anulados.

Sustituye a la reactivación ([[DA-34]], retirada en `LR7`) como forma de
"llegar" a un registro anulado -- el físico confirmó que lo único que
necesitaba de la reactivación era poder VER esos datos de nuevo, y este
visor lo cubre sin deshacer la anulación. Contrato mínimo verificado aquí:
alcance derivado de `TABLAS_ANULABLES` (nunca a mano), muestra vigentes e
históricas, cruza con `audit_log` cuando la convención de `ref` lo permite,
y no ofrece NINGÚN control de escritura.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtSql import QSqlDatabase
from PyQt5.QtWidgets import QApplication, QPushButton

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.anulacion import TABLAS_ANULABLES, anular_fila
from services import visor_anulados as va


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture
def db_qt(bd_temporal):
    nombre = "conexion_test_lr6"
    if QSqlDatabase.contains(nombre):
        QSqlDatabase.removeDatabase(nombre)
    db = QSqlDatabase.addDatabase("QSQLITE", nombre)
    db.setDatabaseName(bd_temporal)
    assert db.open()
    yield db
    db.close()
    QSqlDatabase.removeDatabase(nombre)


def _insertar_control(ruta_bd, **campos):
    con = sqlite3.connect(ruta_bd)
    cols = list(campos)
    marcas = ", ".join("?" * len(cols))
    con.execute(f"INSERT INTO controles ({', '.join(cols)}) VALUES ({marcas})",
                list(campos.values()))
    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# 1. Capa de datos (services/visor_anulados.py) -- sin PyQt5
# ---------------------------------------------------------------------------

class TestSecciones:
    def test_las_7_raices_estan_todas(self, bd_temporal):
        secc = va.secciones()
        assert set(secc) == {
            "controles", "TipoCalibracion", "LinealidadBraquiterapia",
            "aceleradorlineal_600", "aceleradorlineal_ix", "halcyon", "braqui",
        }

    def test_cada_seccion_incluye_a_su_propia_raiz(self, bd_temporal):
        secc = va.secciones()
        for raiz, tablas in secc.items():
            assert raiz in tablas

    def test_alcance_es_tablas_anulables_completo(self, bd_temporal):
        """El alcance del visor es TODO TABLAS_ANULABLES, sin excepción --
        ninguna tabla del contrato queda fuera del visor."""
        secc = va.secciones()
        todas_las_tablas = {t for tablas in secc.values() for t in tablas}
        assert todas_las_tablas == TABLAS_ANULABLES


class TestColumnasDe:
    def test_rechaza_tabla_fuera_del_alcance(self, bd_temporal):
        with pytest.raises(ValueError, match="TABLAS_ANULABLES"):
            va.columnas_de("users")

    def test_controles_no_incluye_id_como_columna_perdida(self, bd_temporal):
        cols = va.columnas_de("controles")
        assert "id" in cols
        assert "activo" in cols  # aquí SÍ, columnas_de no filtra -- filas_de sí


class TestFilasDe:
    def test_activo_no_aparece_en_las_columnas_mostradas(self, bd_temporal):
        """El pill de Estado ya representa `activo` -- mostrarlo también
        como columna cruda sería ruido duplicado."""
        columnas, _ = va.filas_de("controles")
        assert "activo" not in columnas
        assert "id" in columnas

    def test_muestra_vigentes_e_historicas(self, bd_temporal):
        _insertar_control(bd_temporal, equipo="Clinac 600", control="Mensual",
                          fecha="01/2026", activo=1)
        _insertar_control(bd_temporal, equipo="Clinac 600", control="Mensual",
                          fecha="12/2025", activo=0)
        _, filas = va.filas_de("controles")
        estados = {f["estado"] for f in filas}
        assert estados == {"vigente", "anulado"}
        assert len(filas) == 2

    def test_busqueda_filtra_por_substring_en_cualquier_columna(self, bd_temporal):
        _insertar_control(bd_temporal, equipo="Clinac 600", control="Mensual",
                          fecha="01/2026", activo=1)
        _insertar_control(bd_temporal, equipo="Halcyon", control="Mensual",
                          fecha="02/2026", activo=1)
        _, filas = va.filas_de("controles", busqueda="halcyon")
        assert len(filas) == 1
        assert "Halcyon" in filas[0]["valores"]

    def test_rowid_es_estable_y_universal_exista_o_no_columna_id(self, bd_temporal):
        """`preguntas`/`dosimetriaMen`/etc. no tienen columna `id` propia --
        `rowid` debe seguir identificando la fila igual."""
        assert "id" not in va.columnas_de("preguntas")
        _, filas = va.filas_de("preguntas")
        # Tabla vacía en una BD nueva -- lo que se prueba es que no lanza
        # y que la función sabe pedir `rowid` sin que la tabla lo declare.
        assert filas == []


class TestAuditoriaDe:
    def test_sin_fila_anulada_no_hay_auditoria(self, bd_temporal):
        _insertar_control(bd_temporal, equipo="Clinac 600", control="Mensual",
                          fecha="01/2026", activo=1)
        assert va.auditoria_de("controles", 1) is None

    def test_encuentra_la_auditoria_de_anular_fila(self, bd_temporal, app, db_qt):
        """Camino real: anular_fila registra ref=str(id) por defecto --
        el mismo id que rowid para una tabla con INTEGER PRIMARY KEY."""
        _insertar_control(bd_temporal, equipo="Clinac 600", control="Mensual",
                          fecha="01/2026", activo=1)
        anular_fila(db_qt, "controles", 1, "fisico_prueba",
                    detalle="Duplicado por error de digitación")

        auditoria = va.auditoria_de("controles", 1)
        assert auditoria is not None
        assert auditoria["usuario"] == "fisico_prueba"
        assert "Duplicado" in auditoria["detalle"]

    def test_no_inventa_auditoria_para_un_ref_que_no_coincide(self, bd_temporal):
        """Protocolo de LR6: sin coincidencia exacta, `None` -- nunca una
        adivinanza (p.ej. tomar cualquier entrada de esa tabla)."""
        _insertar_control(bd_temporal, equipo="Clinac 600", control="Mensual",
                          fecha="01/2026", activo=0)
        import services.audit_minimo as am
        am.registrar("otro_fisico", am.ACCION_ANULAR, tabla="controles",
                     ref="ref-de-bloque-no-el-rowid",
                     detalle="Anulación con ref de otra convención (SA1/SA2)",
                     ruta_db=bd_temporal)
        assert va.auditoria_de("controles", 1) is None


# ---------------------------------------------------------------------------
# 2. Widget (ui/paginasGuia/visor_anulados.py)
# ---------------------------------------------------------------------------

class TestVisorAnuladosWidget:
    def test_se_instancia_y_carga_la_primera_seccion(self, app, bd_temporal):
        from ui.paginasGuia.visor_anulados import VisorAnulados
        w = VisorAnulados()
        assert w._seccion_actual == "controles"
        assert w._tabla_actual == "controles"

    def test_no_expone_ningun_boton_de_escritura(self, app, bd_temporal):
        """Contrato explícito de DA-49: ni editar, ni eliminar, ni
        reactivar. Único botón de acción permitido: Actualizar (recarga,
        no escribe)."""
        from ui.paginasGuia.visor_anulados import VisorAnulados
        w = VisorAnulados()
        botones = w.findChildren(QPushButton)
        textos = {b.text() for b in botones}
        # Los botones de sección son "chips" (uno por raíz) + "Actualizar".
        assert textos - set(va.secciones()) == {"↻ Actualizar", "×"}
        for boton in botones:
            texto = boton.text()
            assert "eliminar" not in texto.lower()
            assert "editar" not in texto.lower()
            assert "reactivar" not in texto.lower()
            assert "guardar" not in texto.lower()
            assert "subir" not in texto.lower()

    def test_tabla_es_de_solo_lectura(self, app, bd_temporal):
        from PyQt5.QtWidgets import QTableWidget
        from ui.paginasGuia.visor_anulados import VisorAnulados
        w = VisorAnulados()
        assert w._tabla.editTriggers() == QTableWidget.NoEditTriggers

    def test_clic_en_fila_anulada_muestra_el_detalle(self, app, bd_temporal, db_qt):
        _insertar_control(bd_temporal, equipo="Clinac 600", control="Mensual",
                          fecha="01/2026", activo=1)
        anular_fila(db_qt, "controles", 1, "fisico_prueba",
                    detalle="Duplicado por error de digitación")

        from ui.paginasGuia.visor_anulados import VisorAnulados
        w = VisorAnulados()
        assert w._panel_detalle.isHidden() is True

        fila_encontrada = None
        for row in range(w._tabla.rowCount()):
            item = w._tabla.item(row, 0)
            if item.data(Qt.UserRole + 1) == "anulado":
                fila_encontrada = row
                break
        assert fila_encontrada is not None, "la fila anulada debe listarse"

        w._on_click_fila(fila_encontrada, 0)
        assert w._panel_detalle.isHidden() is False
        assert w._lbl_detalle_usuario.text() == "fisico_prueba"

    def test_clic_en_fila_vigente_no_muestra_detalle(self, app, bd_temporal):
        _insertar_control(bd_temporal, equipo="Clinac 600", control="Mensual",
                          fecha="01/2026", activo=1)
        from ui.paginasGuia.visor_anulados import VisorAnulados
        w = VisorAnulados()
        w._on_click_fila(0, 0)
        assert w._panel_detalle.isHidden() is True

    def test_clic_repetido_en_la_misma_fila_anulada_cierra_el_detalle(
            self, app, bd_temporal, db_qt):
        _insertar_control(bd_temporal, equipo="Clinac 600", control="Mensual",
                          fecha="01/2026", activo=1)
        anular_fila(db_qt, "controles", 1, "fisico_prueba", detalle="x")

        from ui.paginasGuia.visor_anulados import VisorAnulados
        w = VisorAnulados()
        w._on_click_fila(0, 0)
        assert w._panel_detalle.isHidden() is False
        w._on_click_fila(0, 0)
        assert w._panel_detalle.isHidden() is True

    def test_cambiar_de_seccion_repuebla_el_combo_de_tabla(self, app, bd_temporal):
        from ui.paginasGuia.visor_anulados import VisorAnulados
        w = VisorAnulados()
        w._on_cambiar_seccion("TipoCalibracion")
        assert w._seccion_actual == "TipoCalibracion"
        assert w._tabla_actual == "TipoCalibracion"
        assert w._combo_tabla.count() == 1
        assert w._combo_tabla.currentText() == "TipoCalibracion"

    def test_buscar_filtra_la_tabla_mostrada(self, app, bd_temporal):
        _insertar_control(bd_temporal, equipo="Clinac 600", control="Mensual",
                          fecha="01/2026", activo=1)
        _insertar_control(bd_temporal, equipo="Halcyon", control="Mensual",
                          fecha="02/2026", activo=1)
        from ui.paginasGuia.visor_anulados import VisorAnulados
        w = VisorAnulados()
        assert w._tabla.rowCount() == 2
        w._input_buscar.setText("halcyon")
        assert w._tabla.rowCount() == 1
