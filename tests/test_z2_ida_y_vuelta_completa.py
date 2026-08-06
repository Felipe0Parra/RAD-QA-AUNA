"""Z2 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): todo lo que la
calculadora guarda, la calculadora lo restaura.

Es la TERCERA vez que aparece este patrón en el proyecto: D2.2 (2026-07-08,
las 3 lecturas lect_m2_* nunca se restauraban), E4 (2026-07-10, R50/calidad/
zref/kQ de electrones), y ahora la humedad (Z1, handoff 05-08). El entregable
de esta tarea NO es el arreglo puntual -- es el TRIPWIRE, para que la cuarta
vez no ocurra en silencio: extrae por AST las claves del dict de `guardar_db`
y falla si alguna no tiene restauración correspondiente en
`cargar_datos_desde_db`, salvo que esté en la ALLOWLIST con su justificación.

Barrido hecho antes de escribir el tripwire (documentado aquí para no tener
que re-derivarlo): de 58 claves, 43 tenían `datos.get(...)` directo, y de las
15 restantes, 13 están genuinamente cubiertas por otro mecanismo (ver
ALLOWLIST) y 2 eran un hueco real -- Humedad_calibracion y Humedad_relativa,
cerrado en este mismo commit.
"""
import ast
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import ui.paginasGuia.dialogs as dialogs_mod

# Claves de guardar_db() que NO se restauran vía `datos.get('<clave>')` en
# cargar_datos_desde_db(), con la razón verificada de por qué NO es un hueco:
ALLOWLIST_NO_RESTAURADO = {
    # Restaurado INDIRECTAMENTE: al restaurar 'Numero_serie' (el id del
    # combo, F1) se dispara combo_series.setCurrentIndex -> on_serie_cambiada
    # (dialogs.py), que asigna self.equipo_id = equipo_id. Confirmado con
    # test_equipo_id_se_recupera_para_poder_regrabar (test_calculadora_
    # dosis_guardar_cargar.py).
    "equipo_id": "cascada de on_serie_cambiada al restaurar Numero_serie",
    # Campos INTERMEDIOS de la cascada de cálculo TRS-398 (D2.2, 2026-07-08):
    # self.blockSignals(True) en cargar_datos_desde_db NO bloquea señales de
    # widgets HIJOS -- al restaurar los campos crudos (lecturas, T/P,
    # tensiones), la cascada de textChanged los recalcula sola con el MISMO
    # valor que tenían al guardar. Confirmado con
    # test_campos_intermedios_sobreviven (mismo archivo), parametrizado
    # exactamente sobre estos 11 widgets.
    "ktp": "recalculado por la cascada desde temperatura/presión restauradas",
    "cociente_ldv1_um": "recalculado por la cascada desde lecturas Q restauradas",
    "Kpol": "recalculado por la cascada desde Mplus/Mminus restaurados",
    "cociente_tensiones": "recalculado por la cascada desde tension_v1/v2 restauradas",
    "lectura_m1": "recalculado por la cascada (lect_m1) desde lecturas restauradas",
    "cociente_lecturas": "recalculado por la cascada desde lect_m1/lect_m2 restaurados",
    "a0": "recalculado por la cascada desde cociente_tensiones restaurado",
    "a1": "recalculado por la cascada desde cociente_tensiones restaurado",
    "a2": "recalculado por la cascada desde cociente_tensiones restaurado",
    "ks": "recalculado por la cascada desde a0/a1/a2 y cociente_lecturas",
    "Dzref": "recalculado por la cascada desde Mq/Kq_0 restaurados",
    # Metadato de B3.3 (PLAN_AUDITORIA_DOS_EJES_21-07.md §7.7c): qué energía
    # generó el cálculo, para el esquema de vigencia (Acelerador, energia) --
    # NO tiene widget correspondiente en el formulario (no hay un "energía
    # seleccionada" que mostrar al recargar). Mismo tipo de exclusión que
    # 'vigente' (columna de B3, tampoco un campo del formulario).
    "energia": "metadato de versionado (B3.3), sin widget en el formulario",
}

# Mapeo clave de guardar_db -> nombre de atributo del widget en el diálogo,
# SOLO para las claves cuyo nombre de widget difiere de la clave (la mayoría
# coincide o el código ya usa datos.get(clave) directo -- este mapeo es
# exclusivamente para poder pedirle a la instancia real el valor del widget
# al verificar los 2 casos de la ALLOWLIST que si tienen restauracion).
_WIDGET_DE_CLAVE = {
    "cociente_ldv1_um": "cociente",
    "lectura_m1": "lect_m1",
}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _dict_literal_de_funcion(nombre_funcion, nombre_variable_ancla):
    """Extrae por AST las claves del primer dict-literal dentro de
    `nombre_funcion` que contenga la clave `nombre_variable_ancla` (para
    distinguirlo de dicts anidados menores, p.ej. kwargs internos)."""
    src = open(dialogs_mod.__file__, encoding="utf-8").read()
    tree = ast.parse(src)
    encontrado = []

    class V(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            if node.name == nombre_funcion:
                for n in ast.walk(node):
                    if isinstance(n, ast.Dict):
                        claves = [k.value for k in n.keys if isinstance(k, ast.Constant)]
                        if nombre_variable_ancla in claves:
                            encontrado.append(claves)
            self.generic_visit(node)

    V().visit(tree)
    assert encontrado, f"no se encontró el dict-literal esperado en {nombre_funcion}"
    return encontrado[0]


def _claves_restauradas(nombre_funcion):
    """Por AST: todas las claves usadas como `datos.get('<clave>')` dentro
    de `nombre_funcion`."""
    src = open(dialogs_mod.__file__, encoding="utf-8").read()
    tree = ast.parse(src)
    claves = set()

    class V(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            if node.name == nombre_funcion:
                for n in ast.walk(node):
                    if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                            and n.func.attr == "get" and n.args
                            and isinstance(n.args[0], ast.Constant)):
                        claves.add(n.args[0].value)
            self.generic_visit(node)

    V().visit(tree)
    return claves


class TestTripwireIdaYVuelta:

    def test_toda_clave_de_guardar_db_se_restaura_o_esta_en_la_allowlist(self):
        claves_guardadas = _dict_literal_de_funcion("guardar_db", "Fecha")
        claves_restauradas = _claves_restauradas("cargar_datos_desde_db")

        faltantes = [
            c for c in claves_guardadas
            if c not in claves_restauradas and c not in ALLOWLIST_NO_RESTAURADO
        ]
        assert faltantes == [], (
            f"guardar_db persiste {faltantes} pero cargar_datos_desde_db no "
            "los restaura, y no están en la ALLOWLIST_NO_RESTAURADO con "
            "justificación -- o se restauran, o se documenta por qué no.")

    def test_la_allowlist_no_tiene_entradas_obsoletas(self):
        """Si una clave de la allowlist YA se restaura de verdad (alguien
        cerró el hueco sin quitarla de la lista), que se note -- una entrada
        vieja en la allowlist puede esconder una regresión futura al mismo
        nombre de clave."""
        claves_restauradas = _claves_restauradas("cargar_datos_desde_db")
        redundantes = [c for c in ALLOWLIST_NO_RESTAURADO if c in claves_restauradas]
        assert redundantes == [], (
            f"{redundantes} ya se restauran directamente -- sobra en la "
            "ALLOWLIST_NO_RESTAURADO, puede estar ocultando el nombre real "
            "de un hueco distinto")


class TestHumedadIdaYVuelta:
    """Los dos campos que SÍ eran un hueco real (Z1/Z2) -- ida y vuelta
    explícita, más allá del tripwire estructural de arriba."""

    def test_humedad_calibracion_y_relativa_sobreviven(self, app, monkeypatch, tmp_path):
        import tempfile
        import services.dosis_service as dosis_service_mod
        import data.ManejoDatos.conection as conection_mod
        from ui.paginasGuia.dialogs import DialogCalculadoraDosis
        from PyQt5.QtWidgets import QWidget

        class VentanaIX(QWidget):
            pass

        ruta = tempfile.mktemp(suffix=".db")
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)

        catalogo = {"id": 76, "equip_type": "Cámara de ionización", "model": "N31010",
                   "serie": "1825", "calibr_fact": 5.397, "t_cal": 20.0,
                   "p_cal": 101.325, "h_cal": 50.0}
        monkeypatch.setattr(
            dialogs_mod.EquiposService, "obtener_modelos_unicos",
            staticmethod(lambda: [{"model": catalogo["model"], "equip_type": catalogo["equip_type"]}]))
        monkeypatch.setattr(
            dialogs_mod.EquiposService, "obtener_series_por_modelo",
            staticmethod(lambda m: [catalogo] if m == catalogo["model"] else []))
        monkeypatch.setattr(
            dialogs_mod.EquiposService, "obtener_por_id",
            staticmethod(lambda i: catalogo if i == catalogo["id"] else None))
        for tipo in ("information", "warning", "critical"):
            monkeypatch.setattr(dialogs_mod.QMessageBox, tipo, staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(dialogs_mod, "generar_reporte_calibracion", lambda **kw: None)

        def _crear():
            return DialogCalculadoraDosis(energias=[], parent=VentanaIX())

        original = _crear()
        idx = original.combo_modelos.findData(catalogo["model"])
        original.combo_modelos.setCurrentIndex(idx)
        original.combo_series.setCurrentIndex(1)
        original.fotones.setChecked(True)
        original.SSD.setChecked(True)
        original.pulse.setChecked(True)
        original.combo_fieldsize.setCurrentIndex(0)
        original.humr_cal.setText("45.0")
        original.temp.setText("22.0")
        original.pressure.setText("101.325")
        original.humedad_r.setText("48.0")
        for campo, val in ((original.lDV1_1, "12.437"), (original.lDV1_2, "12.437"),
                          (original.lDV1_3, "12.437")):
            campo.setText(val)
        original.unidades_monitor.setText("100")
        for campo in (original.Mminus1, original.Mminus2, original.Mminus3):
            campo.setText("-12.437")
        original.tension_v1.setText("400")
        original.tension_v2.setText("100")
        for campo, val in ((original.lect_m2_1, "12.430"), (original.lect_m2_2, "12.435"),
                          (original.lect_m2_3, "12.440")):
            campo.setText(val)
        original.tpr2010.setText("0.68")
        original.pddzref.setText("66.6")
        original.Zref.setText("10.0")
        original.Zmax.setText("1.5")

        original.guardar_db()

        fecha = original.date_edit.date().toString("dd/MM/yyyy")
        datos_bd = dosis_service_mod.DosisService.buscar_por_fecha(fecha, original.acelerador_actual)
        assert datos_bd["Humedad_calibracion"] == "45.0"
        assert datos_bd["Humedad_relativa"] == "48.0"

        cargado = _crear()
        cargado.cargar_datos_desde_db(datos_bd)

        assert cargado.humr_cal.text() == "45.0"
        assert cargado.humedad_r.text() == "48.0"
