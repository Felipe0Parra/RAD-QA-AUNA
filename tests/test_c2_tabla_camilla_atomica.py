"""C2 (PLAN_REPARACION_ANUAL_27-08.md §Fase 1): `tabla_icam`
("Indicadores de posición de la camilla") como una sola operación atómica.

`AN-4` -- columnas invertidas: `halcyon_anual.py` registraba
`(tabla_icam, 1, 2, 3, 'porcentaje')` con `columna_real=1` (la columna
"Desplazamiento", el nominal) y `columna_esperada=2` (la columna
"Medido (cm)"). El numerador sobrevivía; el denominador no -- el porcentaje
subestimaba siempre, y más cuanto menor el desplazamiento.

`AN-5` -- un segundo callback destruiría el dato medido. `tabla_icam`
también vivía en `grupo_tablas_mecanicos`, que la registraba OTRA VEZ con
`(tabla_icam, 0, 1, 2, 'absoluta')`: `columna_real=0` es la etiqueta
("Longitudinal"/"Lateral"/"Vertical", texto, no número) y
`columna_discrepancia=2` es la columna "Medido (cm)" -- el dato que el
físico tecleó. `float("Longitudinal")` lanza `ValueError`; el `except`
escribiría "N/A" encima de ese dato. Hoy no ocurre solo porque los dos
registros comparten `timer_key` y el segundo cancela el temporizador del
primero -- un accidente, no una garantía.

La reparación son las DOS mitades juntas: corregir el orden de columnas
**y** sacar `tabla_icam` de `grupo_tablas_mecanicos`. Este test verifica
las dos, porque limpiar solo una arma la otra.
"""
import ast
import inspect
import os
import re
import textwrap

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QWidget

from ui.paginasControles.PruebasAnuales.halcyon_anual import PruebaAnualHalcyon
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _halcyon_pelado():
    obj = PruebaAnualHalcyon.__new__(PruebaAnualHalcyon)
    QWidget.__init__(obj)
    return obj


def _tabla_icam_con_fila(nominal, medido):
    # Headers reales: ["", "Desplazamiento", "Medido (cm)", "Diferencia (%)"]
    tabla = QTableWidget(1, 4)
    tabla.setItem(0, 0, QTableWidgetItem("Longitudinal"))
    tabla.setItem(0, 1, QTableWidgetItem(str(nominal)))
    tabla.setItem(0, 2, QTableWidgetItem(str(medido)))
    return tabla


class TestAN4PorcentajeSobreElNominal:
    @pytest.mark.parametrize("nominal, medido, esperado_pct", [
        (20, 20.4, "2.00"),
        (5, 5.3, "6.00"),
        (1, 1.2, "20.00"),
    ])
    def test_columnas_correctas_dan_el_porcentaje_real(self, app, nominal, medido, esperado_pct):
        obj = _halcyon_pelado()
        tabla = _tabla_icam_con_fila(nominal, medido)
        # Registro corregido: columna_real=2 (Medido), columna_esperada=1
        # (Desplazamiento nominal, el denominador correcto).
        calcular = PruebaAnual600._calcular_discrepancias_tablas(
            obj, tabla, 2, 1, 3, diferencia_tipo="porcentaje")
        calcular()
        assert tabla.item(0, 3).text() == esperado_pct


class TestAN5SoloUnCallbackParaTablaIcam:
    """Estructural: `tabla_icam` no puede tener dos registros de
    `_configurar_eventos` -- uno de ellos, con las columnas de
    `grupo_tablas_mecanicos`, destruiría "Medido (cm)"."""

    def _fuente_configurar_subtoolbox(self):
        return inspect.getsource(PruebaAnualHalcyon._configurar_subtoolbox)

    def test_grupo_tablas_mecanicos_no_incluye_tabla_icam(self, app):
        fuente = self._fuente_configurar_subtoolbox()
        m = re.search(r"grupo_tablas_mecanicos\s*=\s*\[([^\]]*)\]", fuente)
        assert m, "no se encontró la asignación de grupo_tablas_mecanicos"
        elementos = [e.strip() for e in m.group(1).split(",") if e.strip()]
        assert "tabla_icam" not in elementos, (
            "tabla_icam sigue en grupo_tablas_mecanicos -- eso arma un "
            "segundo callback que destruiría 'Medido (cm)'")

    def test_tabla_icam_tiene_un_solo_registro_de_configurar_eventos(self, app):
        fuente = self._fuente_configurar_subtoolbox()
        ocurrencias = re.findall(r"_configurar_eventos\(\s*tabla_icam\b", fuente)
        assert len(ocurrencias) == 1, (
            f"se esperaba exactamente 1 registro de _configurar_eventos "
            f"para tabla_icam, hay {len(ocurrencias)}")

    def test_el_unico_registro_usa_columna_2_como_real_y_1_como_esperada(self, app):
        fuente = self._fuente_configurar_subtoolbox()
        m = re.search(
            r"_calcular_discrepancias_tablas\(\s*tabla_icam\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)",
            fuente)
        assert m, "no se encontró la llamada a _calcular_discrepancias_tablas para tabla_icam"
        columna_real, columna_esperada, columna_discrepancia = m.groups()
        assert columna_real == "2", "columna_real debe ser 2 (Medido (cm))"
        assert columna_esperada == "1", "columna_esperada debe ser 1 (Desplazamiento nominal)"
        assert columna_discrepancia == "3", "columna_discrepancia debe ser 3 (Diferencia (%))"


class TestAN5CicloDeEventosCompletoNoDestruyeElMedido:
    """Reproduce el ciclo de eventos con los registros TAL COMO quedan en
    `_configurar_subtoolbox` (vía AST, sin instanciar la ventana completa
    -- createSimpleTable1 exige BD real): si algo reintroduce un segundo
    callback destructivo para tabla_icam, este test lo atrapa incluso si
    los dos comparten timer_key (el "accidente" que hoy lo salva)."""

    def _registros_para_tabla_icam(self):
        """Extrae, por AST, cada llamada a _configurar_eventos cuyo primer
        argumento posicional es el nombre de variable 'tabla_icam', dentro
        del bucle o fuera de él (cubre el caso de que vuelva a entrar en
        grupo_tablas_mecanicos con el nombre de variable 'tabla')."""
        arbol = ast.parse(textwrap.dedent(
            inspect.getsource(PruebaAnualHalcyon._configurar_subtoolbox)))
        registros = []
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                    and nodo.func.attr == "_configurar_eventos"):
                registros.append(nodo)
        return registros

    def test_ningun_registro_ademas_del_directo_puede_alcanzar_tabla_icam(self, app):
        # El bucle "for tabla in grupo_tablas_mecanicos" usa la variable
        # genérica 'tabla', no 'tabla_icam' -- por eso AN5 se valida por
        # contenido de la lista (test anterior), no por nombre de variable
        # en la llamada. Este test deja constancia de que, tras el fix,
        # solo existe UNA llamada cuyo primer argumento es 'tabla_icam'.
        registros = self._registros_para_tabla_icam()
        directos = [
            r for r in registros
            if r.args and isinstance(r.args[0], ast.Name) and r.args[0].id == "tabla_icam"
        ]
        assert len(directos) == 1
