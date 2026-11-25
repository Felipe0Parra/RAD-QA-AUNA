"""UM.6b (PLAN_CALCULADORA_UM_05-11.md, DC14, DC15, DC16): la subpestaña «Desde JSON» de la pestaña «Calculadora UM» (`ui/paginasGuia/calculadora_um_json.py`).

Lo que fija:
  - la CAPA PURA sin crear widgets: UNA clasificación de cada fila para la tabla y para el resumen, que suma el total en toda combinación; los textos de las celdas, de la cuña, del nombre que se ve,
    del motivo sin tablas (dice quién carga y con qué botón) y de lo copiado;
  - el PANEL por el camino del físico, con las tablas reales del 600C guardadas por el servicio de UM.3 en una base TEMPORAL: importar el plan de ejemplo da la tabla y el resumen exactos; elegir una
    fila da el MISMO desglose que la parte manual con lo mismo escrito; los umbrales de la parte manual cambian los estados y no las UM; un archivo que no es un plan deja la tabla vacía con su
    motivo; importar otro reemplaza sin mezclar; cancelar no cambia nada; un plan con dos equipos; un campo sin tablas dice quién carga; tras «Cargar tablas» el plan se vuelve a calcular; cambiar
    de subpestaña no pierde nada; nada se guarda; ninguna excepción escapa de un slot (llegaría a `error_log.txt`); «Ver formato» muestra el texto que las pruebas calculan;
  - el ancho: un plan de 200 campos con nombres enormes o con saltos de línea no ensancha la pestaña; las etiquetas nuevas están en la lista única de la pestaña;
  - la cabecera: `columnas_quietas` no mide adentro y vuelve a medir al salir (también si el llenado falla); tras llenar o refrescar cada tabla sus columnas miden su contenido;
  - `build_exe.py` lista el módulo una vez, después del diálogo de la carga, en CRLF; el módulo no tiene SQL ni física; DA-18 y NAV-D1.
Trampa 2: todo cuadro de diálogo se parcha y un modal hace caer la prueba; `QFileDialog.getOpenFileName` devuelve la ruta de cada caso. Trampa 9: cada pantalla se cierra con la receta completa.
Nunca una base de BasesDeDatos/."""
import ast
import gc
import json
import os
import re
import shutil
import sqlite3
import sys
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ui.paginasGuia.calculadora_um_json as dj      # primero: sin UM.6b la colección cae porque el módulo no existe (el rojo)
import ui.paginasGuia.calculadora_um as pantalla
import ui.paginasGuia.calculadora_um_cargar as carga
from PyQt5 import sip
from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QFontMetrics, QTextDocument
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QDialog, QFileDialog, QHeaderView, QMessageBox, QTableWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services import um_datos_haz, um_plan_json
from services import um_motor as motor

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "tests", "datos_um", "600C")
EQUIPO, ENERGIA = "Clinac 600", "6 MV"
SIMBOLOS = re.compile("[✓✔✕✖✗✘⚠❌❎✅☑☒]")
ENTRE_PARENTESIS = re.compile(r"\s\((cm|mm|cGy|Gy|UM|MU|%|cGy/UM|grados|MB)\)")
B = {"dosis_cgy": 100, "x_cm": 10, "y_cm": 10, "ssd_cm": 100, "profundidad_cm": 10}
# Lo que muestra la tabla con el plan de ejemplo (el de VMAT no llega a ser una entrada: ni su cuña ni sus UM de Eclipse se leen) y las tablas reales (umbrales 2 y 3 [%]); los números son los de logs/UM6_prevuelo/a (H-UM6-4 de UM.6)
TABLA_DEL_EJEMPLO = [   # en el orden de COLUMNAS: campo, estado, error, UM calculadas, UM de Eclipse, cuña, equipo, energía, avisos o motivo
    ("AP abierto, isocéntrico", "Dentro", "-0.26", "110.7", "111", "Sin cuña", EQUIPO, ENERGIA, "Sin avisos"),
    ("PA con láminas", "Revisar", "+2.18", "116.5", "114", "Sin cuña", EQUIPO, ENERGIA, "1 aviso"),
    ("Lateral con cuña de 15", "Fuera", "+3.63", "91.2", "88", "15° IN", EQUIPO, ENERGIA, "1 aviso"),
    ("Lateral con …conocido", "Sin calcular", "", "", "120", "30° IN", EQUIPO, ENERGIA, "Falta el factor de la cuña de 30° en 10 × 10: escríbalo a mano"),
    ("Arco VMAT", "Sin calcular", "", "", "", "", EQUIPO, ENERGIA,
     "La técnica «VMAT» no se reconoce como un campo estático: la ecuación 3 de la TG-71 no cubre IMRT ni VMAT, y este campo no se calcula"),
]
CAMPO, ESTADO, ERROR, UM, ECLIPSE, CUNA, EQUIPO_, ENERGIA_, AVISOS = range(9)
RESUMEN_DEL_EJEMPLO = "5 campos: 1 dentro, 1 revisar, 1 fuera y 2 sin calcular."


# ================================================================================================================================== bases, pantallas y ayudas

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def dialogos(monkeypatch):
    """Trampa 2: ningún camino abre un cuadro modal; `QFileDialog.getOpenFileName` lo pone cada caso con `elegir`."""
    def prohibido(*a, **k):
        raise AssertionError("la pantalla abrió un cuadro modal")
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(prohibido))
    for tipo in ("getOpenFileName", "getOpenFileNames", "getSaveFileName", "getExistingDirectory"):
        monkeypatch.setattr(QFileDialog, tipo, staticmethod(prohibido))
    monkeypatch.setattr(QDialog, "exec_", prohibido)
    monkeypatch.setattr(QDialog, "exec", prohibido)


def elegir(monkeypatch, ruta):
    llamadas = []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: llamadas.append(a) or (ruta, "")))
    return llamadas


@pytest.fixture(scope="module")
def originales():
    return [(nombre, open(os.path.join(DATOS, nombre), "rb").read()) for nombre in sorted(os.listdir(DATOS))]


def _sql(ruta, sql, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        filas = con.execute(sql, parametros).fetchall()
        con.commit()
        return filas
    finally:
        con.close()


def _guardar_600(ruta, originales):
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = object.__new__(Conexion)
        try:
            ok, motivo, _ = um_datos_haz.guardar(equipo=EQUIPO, energia=ENERGIA, archivos=originales, d0_dmax=1.0, d0_tabla=None, d0_origen="Eclipse: 1 [cGy/UM] en dmax",
                                                 wf_escritos=None, curva_sc=None, sc_origen=None, observaciones=None, usuario="jefa")
        finally:
            Conexion._instance = previo
    assert ok, motivo


@pytest.fixture(scope="module")
def plantilla_vacia(tmp_path_factory):
    ruta = str(tmp_path_factory.mktemp("um6b") / "vacia.db")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = None
        try:
            Conexion().con.close()
        finally:
            Conexion._instance = previo
    _sql(ruta, "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) VALUES ('jefa', 'x', 'Jefa de Física', 1, 901, 'Físico Médico', 'jefe')")
    return ruta


@pytest.fixture(scope="module")
def plantilla(plantilla_vacia, originales, tmp_path_factory):
    ruta = str(tmp_path_factory.mktemp("um6b") / "cargada.db")
    shutil.copy(plantilla_vacia, ruta)
    _guardar_600(ruta, originales)
    return ruta


def _usar(ruta, monkeypatch, tmp_path):
    copia = str(tmp_path / os.path.basename(ruta))
    shutil.copy(ruta, copia)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: copia)
    monkeypatch.setattr(Conexion, "_instance", object.__new__(Conexion))
    return copia


@pytest.fixture
def bd(plantilla, monkeypatch, tmp_path):
    return _usar(plantilla, monkeypatch, tmp_path)


@pytest.fixture
def bd_vacia(plantilla_vacia, monkeypatch, tmp_path):
    return _usar(plantilla_vacia, monkeypatch, tmp_path)


def cerrar(w):
    if sip.isdeleted(w):
        return
    w.hide()
    w.close()
    w.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


@pytest.fixture
def fabrica(app):
    hechas = []

    def nueva():
        hechas.append(pantalla.CalculadoraUM("jefa"))
        return hechas[-1]
    yield nueva
    for w in hechas:
        cerrar(w)


@pytest.fixture
def p(bd, fabrica):
    return fabrica()


def archivo(tmp_path, contenido, nombre="plan.json"):
    ruta = tmp_path / nombre
    ruta.write_bytes(contenido.encode("utf-8") if isinstance(contenido, str) else contenido)
    return str(ruta)


def importar(p, monkeypatch, ruta):
    llamadas = elegir(monkeypatch, ruta)
    QTest.mouseClick(p.panel_json.boton_importar, Qt.LeftButton)
    assert len(llamadas) == 1
    return p.panel_json


def celdas(tabla):
    return [tuple(tabla.item(i, j).text() for j in range(tabla.columnCount())) for i in range(tabla.rowCount())]


def elegir_fila(panel, i):
    panel.tabla_campos.selectRow(i)


def escribir_umbrales(p, dentro, fuera):
    for clave, texto in (("dentro", dentro), ("fuera", fuera)):
        p.umbrales[clave].selectAll()
        QTest.keyClick(p.umbrales[clave], Qt.Key_Delete)
        QTest.keyClicks(p.umbrales[clave], texto)


def un_plan(*campos, **del_plan):
    return json.dumps({"equipo": "600C", "energia": "6X", **del_plan, "campos": list(campos)})


# ================================================================================================================================== la capa pura

def _fila(um=None, error=None, motivo=None, avisos=()):
    resultado = None if um is None else motor.Resultado(um, 1.0, (), tuple(avisos), {}, 1.0, error, None)
    campo = um_plan_json.CampoImportado("c", EQUIPO, ENERGIA, motor.Entrada(dosis=1, x=10, y=10, ssd=100, prof=10, um_planeador=None if error is None else 100.0), None)
    return dj.Fila(campo, resultado, motivo if resultado is None else None)


@pytest.mark.parametrize("fila, umbrales, clase", [
    (_fila(motivo="x"), (2.0, 3.0), "Sin calcular"), (_fila(um=100.0), (2.0, 3.0), "Sin UM de Eclipse"), (_fila(um=100.0, error=1.0), None, "Sin evaluar"),
    (_fila(um=100.0, error=2.0), (2.0, 3.0), "Dentro"), (_fila(um=100.0, error=-2.0000001), (2.0, 3.0), "Revisar"), (_fila(um=100.0, error=3.0), (2.0, 3.0), "Revisar"),
    (_fila(um=100.0, error=-3.0001), (2.0, 3.0), "Fuera"),
])
def test_una_sola_clase_por_fila_con_el_error_sin_redondear(fila, umbrales, clase):
    assert dj.clase_de_la_fila(fila, umbrales) == clase


@pytest.mark.parametrize("filas, umbrales, texto", [
    ([_fila(um=1.0, error=0.5), _fila(um=1.0, error=2.5), _fila(um=1.0, error=9.0), _fila(motivo="a"), _fila(motivo="b")], (2.0, 3.0), RESUMEN_DEL_EJEMPLO),
    ([_fila(motivo="a")], (2.0, 3.0), "1 campo: 0 dentro, 0 revisar, 0 fuera y 1 sin calcular."),
    ([_fila(um=1.0, error=0.5)], (2.0, 3.0), "1 campo: 1 dentro, 0 revisar y 0 fuera."),
    ([_fila(um=1.0), _fila(um=1.0, error=0.1)], (2.0, 3.0), "2 campos: 1 dentro, 0 revisar, 0 fuera y 1 sin UM de Eclipse."),
    ([_fila(um=1.0, error=0.5), _fila(um=1.0, error=5.0), _fila(um=1.0), _fila(motivo="a")], None, "4 campos: 0 dentro, 0 revisar, 0 fuera, 2 sin evaluar, 1 sin UM de Eclipse y 1 sin calcular."),
])
def test_el_resumen_cuenta_las_clases_de_la_tabla(filas, umbrales, texto):
    assert dj.texto_del_resumen(filas, umbrales) == texto


def test_el_resumen_suma_el_total_y_coincide_con_la_tabla_para_toda_combinacion():
    """La lección de UM.5 (UM5-S8): el conteo y la tabla salen de la MISMA clasificación, y los números suman el total."""
    import itertools
    tipos = [_fila(motivo="m"), _fila(um=1.0), _fila(um=1.0, error=0.1), _fila(um=1.0, error=2.5), _fila(um=1.0, error=-7.0)]
    for n in range(1, 4):
        for combinacion in itertools.product(tipos, repeat=n):
            for umbrales in ((2.0, 3.0), None):
                texto = dj.texto_del_resumen(list(combinacion), umbrales)
                numeros = [int(x) for x in re.findall(r"(\d+) [a-z]", texto.split(": ", 1)[1])]
                assert sum(numeros) == n and texto.startswith(f"{n} campo")
                clases = [dj.clase_de_la_fila(f, umbrales) for f in combinacion]
                for clase, nombre in dj.EN_EL_RESUMEN.items():
                    if clases.count(clase) or clase in dj.SIEMPRE:
                        assert f"{clases.count(clase)} {nombre}" in texto


def test_la_cuna_se_dice_como_la_leyo_el_lector():
    e = lambda **k: motor.Entrada(dosis=1, x=10, y=10, ssd=100, prof=10, **k)      # noqa: E731
    assert [dj.texto_de_la_cuna(e()), dj.texto_de_la_cuna(e(cuna=15, cuna_orientacion="LEFT")), dj.texto_de_la_cuna(e(cuna=30, wf_manual=0.8))] == ["Sin cuña", "15° LEFT", "30° (factor escrito)"]


@pytest.mark.parametrize("nombre, visto", [("AP", "AP"), ("A" * 30, "A" * 30), ("A" * 31, "AAAAAAAAAAAA…AAAAAAAA"), ("Campo\ncon\tsaltos  y espacios", "Campo con saltos y espacios"),
                                           ("Lateral con cuña de 30, sin factor conocido", "Lateral con …conocido")])
def test_el_nombre_que_se_ve_va_en_una_linea_y_acortado(nombre, visto):
    assert dj.nombre_para_mostrar(nombre) == visto


def test_sin_tablas_el_motivo_dice_quien_las_carga_y_con_que_boton():
    assert dj.motivo_sin_tablas("Clinac iX", "6 MV") == f"No hay tablas cargadas del Clinac iX, 6 MV: sin ellas este campo no se calcula. {pantalla.QUIEN_CARGA}"
    assert "«Cargar tablas»" in dj.motivo_sin_tablas("Clinac iX", "6 MV")


def test_lo_copiado_empieza_por_el_campo_y_la_cuna_como_en_la_tabla():
    campo = um_plan_json.leer_plan(un_plan({**B, "nombre": "Lateral\ncon factor", "cuna_grados": 30, "cuna_tipo": "EDW", "factor_cuna": 0.8, "um_planeador": 150}))[1][0]
    fila = dj.Fila(campo, None, None)
    assert dj.texto_del_contexto_del_campo(fila, "Error frente a Eclipse: +1.00 [%]", "Estado: Dentro") == (
        "Campo: Lateral con factor | Equipo: Clinac 600 | Energía: 6 MV | Cuña: 30° (factor escrito) | UM de Eclipse: 150 [UM] | Error frente a Eclipse: +1.00 [%] | Estado: Dentro")


def test_lo_que_se_importo_se_dice_con_el_nombre_del_plan_y_el_del_archivo():
    assert dj.texto_del_archivo("Ejemplo de prueba (datos inventados, no es un paciente)", "/d/planes/plan.json") == "Plan: Ejemplo de p…aciente) (archivo plan.json)"
    assert dj.texto_del_archivo("  ", "/d/planes/plan.json") == "Archivo: plan.json"


# ================================================================================================================================== el panel: el camino del físico

def test_sin_plan_dice_que_pulsar(p):
    panel = p.panel_json
    assert p.subpestanas.widget(1) is panel and p.subpestanas.tabText(1) == "Desde JSON"
    assert panel.etiqueta_archivo.text() == dj.NADA_IMPORTADO and panel.tabla_campos.rowCount() == 0 and not panel.etiqueta_resumen.isVisibleTo(panel)
    assert panel.nota.text() == dj.NOTA and panel.etiqueta_um.text() == dj.ELIJA_UNA_FILA and not panel.boton_copiar.isEnabled()
    assert [panel.tabla_campos.horizontalHeaderItem(j).text() for j in range(panel.tabla_campos.columnCount())] == list(dj.COLUMNAS)
    assert dj.COLUMNAS == ("Campo", "Estado", "Error [%]", "UM calculadas [UM]", "UM de Eclipse [UM]", "Cuña", "Equipo", "Energía", "Avisos o motivo")
    assert panel.tabla_campos.selectionMode() == panel.tabla_campos.SingleSelection and panel.tabla_campos.selectionBehavior() == panel.tabla_campos.SelectRows


def test_importar_el_plan_de_ejemplo_da_la_tabla_y_el_resumen_exactos(p, monkeypatch, tmp_path):
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    assert celdas(panel.tabla_campos) == TABLA_DEL_EJEMPLO
    assert panel.etiqueta_resumen.text() == RESUMEN_DEL_EJEMPLO and panel.etiqueta_resumen.isVisibleTo(panel)
    assert panel.etiqueta_archivo.text() == "Plan: Ejemplo de p…aciente) (archivo plan.json)" and not panel.etiqueta_rechazo.isVisibleTo(panel)
    assert [panel.tabla_campos.item(i, 0).toolTip() for i in range(5)] == [c["nombre"] for c in json.loads(um_plan_json.EJEMPLO_DE_PLAN)["campos"]]       # la ayuda lleva el nombre entero


@pytest.mark.parametrize("fila", [0, 1, 2])
def test_elegir_una_fila_da_el_mismo_desglose_de_la_parte_manual(p, monkeypatch, tmp_path, fila):
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    elegir_fila(panel, fila)
    r = panel.filas[fila].resultado
    _, datos = p.haz_vigente(EQUIPO, ENERGIA)
    directo = motor.calcular(datos, panel.filas[fila].campo.entrada)
    assert r == directo
    assert panel.etiqueta_um.text() == pantalla.texto_de_las_um(r) and panel.etiqueta_d_um.text() == pantalla.texto_de_d_um(r)
    assert celdas(panel.tabla_desglose) == pantalla.filas_del_desglose(r) and panel.etiqueta_campos.text() == pantalla.texto_de_los_campos(r)
    assert [panel.lista_avisos.item(i).text() for i in range(panel.lista_avisos.count())] == list(r.avisos) and panel.titulo_avisos.text() == f"Avisos ({len(r.avisos)})"
    assert panel.etiqueta_error.text() == pantalla.texto_del_error(r.error_pct, (2.0, 3.0)) and panel.etiqueta_estado.text() == f"Estado: {TABLA_DEL_EJEMPLO[fila][ESTADO]}"
    assert panel.boton_copiar.isEnabled() and not panel.etiqueta_motivo.isVisibleTo(panel)


def test_lo_mismo_escrito_en_la_parte_manual_da_el_mismo_desglose(p, monkeypatch, tmp_path):
    """La convergencia por la pantalla: el campo «AP abierto» del ejemplo (mandíbulas 10 × 15, SSD 90, 10 [cm], 90 [cGy], 111 [UM]) escrito en el formulario."""
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    elegir_fila(panel, 0)
    for clave, texto in {"dosis": "90", "x": "10", "y": "15", "ssd": "90", "prof": "10", "um_planeador": "111"}.items():
        p.campos[clave].setText(texto)
    p.calcular()
    assert p.resultado == panel.filas[0].resultado
    assert celdas(p.tabla_desglose) == celdas(panel.tabla_desglose) and p.etiqueta_um.text() == panel.etiqueta_um.text()
    assert p.etiqueta_error.text() == panel.etiqueta_error.text() and p.etiqueta_estado.text() == panel.etiqueta_estado.text()


@pytest.mark.parametrize("fila", [3, 4])
def test_una_fila_sin_calcular_da_su_motivo_y_ningun_numero(p, monkeypatch, tmp_path, fila):
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    elegir_fila(panel, fila)
    assert panel.etiqueta_motivo.text() == TABLA_DEL_EJEMPLO[fila][AVISOS] and panel.etiqueta_motivo.isVisibleTo(panel)
    assert panel.etiqueta_um.text() == pantalla.SIN_RESULTADO and panel.tabla_desglose.rowCount() == 0 and panel.lista_avisos.count() == 0 and not panel.boton_copiar.isEnabled()
    assert panel.etiqueta_error.text() == "" and panel.etiqueta_estado.text() == ""


def test_copiar_lleva_el_campo_y_el_desglose(p, monkeypatch, tmp_path):
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    elegir_fila(panel, 2)
    QTest.mouseClick(panel.boton_copiar, Qt.LeftButton)
    texto = QApplication.clipboard().text()
    r = panel.filas[2].resultado
    assert texto == pantalla.texto_para_copiar(r, f"Campo: Lateral con cuña de 15 | Equipo: Clinac 600 | Energía: 6 MV | Cuña: 15° (IN) | UM de Eclipse: 88 [UM] | "
                                                  f"{pantalla.texto_del_error(r.error_pct, (2.0, 3.0))} | Estado: Fuera")


def test_los_umbrales_de_la_parte_manual_cambian_los_estados_y_no_las_um(p, monkeypatch, tmp_path):
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    elegir_fila(panel, 1)
    um_antes = [panel.tabla_campos.item(i, UM).text() for i in range(5)]
    escribir_umbrales(p, "2.5", "4")
    assert [panel.tabla_campos.item(i, ESTADO).text() for i in range(5)] == ["Dentro", "Dentro", "Revisar", "Sin calcular", "Sin calcular"]
    assert panel.etiqueta_resumen.text() == "5 campos: 2 dentro, 1 revisar, 0 fuera y 2 sin calcular." and panel.etiqueta_estado.text() == "Estado: Dentro"
    assert [panel.tabla_campos.item(i, UM).text() for i in range(5)] == um_antes and [f.resultado for f in panel.filas][:3] == [f.resultado for f in panel.filas][:3]
    escribir_umbrales(p, "5", "3")         # no sirven: dentro mayor que fuera
    assert [panel.tabla_campos.item(i, ESTADO).text() for i in range(5)] == ["Sin evaluar"] * 3 + ["Sin calcular"] * 2
    assert panel.etiqueta_resumen.text() == "5 campos: 0 dentro, 0 revisar, 0 fuera, 3 sin evaluar y 2 sin calcular."
    assert panel.etiqueta_estado.text().startswith("Estado sin evaluar: Las tolerancias deben ser números mayores que 0") and panel.tabla_campos.item(1, ERROR).text() == "+2.18"
    assert [panel.tabla_campos.item(i, UM).text() for i in range(5)] == um_antes


def test_el_error_lleva_las_cifras_que_piden_los_umbrales(p, monkeypatch, tmp_path):
    """Con un umbral de 2.18 [%], +2.1835 no se lee «+2.18» (se leería igual que el umbral): `cifras_del_error`, la misma de la etiqueta de la parte manual."""
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    escribir_umbrales(p, "2.18", "3")
    assert panel.tabla_campos.item(1, ERROR).text() == pantalla.cifras_del_error(panel.filas[1].resultado.error_pct, (2.18, 3.0)) == "+2.183"
    elegir_fila(panel, 1)
    assert panel.etiqueta_error.text() == "Error frente a Eclipse: +2.183 [%]"


def test_cargar_tablas_sin_plan_importado_no_dice_nada(p):
    p.tablas_guardadas(EQUIPO, ENERGIA)
    panel = p.panel_json
    assert panel.campos is None and panel.tabla_campos.rowCount() == 0 and panel.etiqueta_rechazo.text() == "" and not panel.etiqueta_rechazo.isVisibleTo(panel)


@pytest.mark.parametrize("contenido, motivo", [
    ("no es json", "No se importó el archivo «plan.json»: El archivo no es un plan: debe ser un objeto JSON con la lista «campos». No es un JSON válido: falla en la línea 1, columna 1."),
    ("[]", "No se importó el archivo «plan.json»: El archivo no es un plan: debe ser un objeto JSON con la lista «campos»."),
    ("", "No se importó el archivo «plan.json»: El archivo está vacío."),
    ('{"campos": [{"dosis_cgy": NaN}]}', "No se importó el archivo «plan.json»: El archivo trae el valor NaN, que no es un número: un plan solo lleva números finitos."),
])
def test_un_archivo_que_no_es_un_plan_deja_la_tabla_vacia_con_su_motivo(p, monkeypatch, tmp_path, contenido, motivo):
    panel = importar(p, monkeypatch, archivo(tmp_path, contenido))
    assert panel.etiqueta_rechazo.text() == motivo and panel.etiqueta_rechazo.isVisibleTo(panel)
    assert panel.tabla_campos.rowCount() == 0 and panel.campos is None and not panel.etiqueta_resumen.isVisibleTo(panel) and panel.etiqueta_archivo.text() == dj.NADA_IMPORTADO


def test_un_archivo_en_utf16_se_rechaza_con_su_motivo(p, monkeypatch, tmp_path):
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN.encode("utf-16")))
    assert panel.etiqueta_rechazo.text().endswith("El archivo no está en UTF-8: parece UTF-16 o un archivo binario. Guárdelo como UTF-8.") and panel.tabla_campos.rowCount() == 0


def test_importar_otro_reemplaza_el_anterior_sin_mezclar(p, monkeypatch, tmp_path):
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN, "uno.json"))
    elegir_fila(panel, 0)
    importar(p, monkeypatch, archivo(tmp_path, un_plan({**B, "nombre": "solo", "um_planeador": 151}), "dos.json"))
    assert [f[CAMPO] for f in celdas(panel.tabla_campos)] == ["solo"] and panel.etiqueta_resumen.text() == "1 campo: 1 dentro, 0 revisar y 0 fuera."
    assert panel.etiqueta_um.text() == dj.ELIJA_UNA_FILA and panel.tabla_desglose.rowCount() == 0          # nada de la fila elegida del plan anterior
    importar(p, monkeypatch, archivo(tmp_path, "no es json", "tres.json"))
    assert panel.tabla_campos.rowCount() == 0 and panel.filas == [] and "tres.json" in panel.etiqueta_rechazo.text()


def test_cancelar_no_cambia_nada(p, monkeypatch, tmp_path):
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    antes = celdas(panel.tabla_campos)
    importar(p, monkeypatch, "")
    assert celdas(panel.tabla_campos) == antes and panel.etiqueta_resumen.text() == RESUMEN_DEL_EJEMPLO


def test_un_plan_con_dos_equipos_usa_las_tablas_de_cada_uno_y_sin_ellas_dice_quien_carga(p, monkeypatch, tmp_path):
    panel = importar(p, monkeypatch, archivo(tmp_path, un_plan({**B, "nombre": "en el 600", "um_planeador": 151}, {**B, "nombre": "en el iX", "equipo": "iX"})))
    assert [f[ESTADO] for f in celdas(panel.tabla_campos)] == ["Dentro", "Sin calcular"]
    assert celdas(panel.tabla_campos)[1][AVISOS] == dj.motivo_sin_tablas("Clinac iX", "6 MV") and panel.etiqueta_resumen.text() == "2 campos: 1 dentro, 0 revisar, 0 fuera y 1 sin calcular."


def test_el_equipo_de_arriba_no_manda_sobre_el_plan(p, monkeypatch, tmp_path):
    p.combo_equipo.setCurrentIndex(p.combo_equipo.findText("Clinac iX"))
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    assert celdas(panel.tabla_campos) == TABLA_DEL_EJEMPLO


def test_tras_cargar_tablas_el_plan_se_vuelve_a_calcular(bd_vacia, fabrica, monkeypatch, tmp_path, originales):
    p = fabrica()
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    assert [f[ESTADO] for f in celdas(panel.tabla_campos)] == ["Sin calcular"] * 5 and celdas(panel.tabla_campos)[0][AVISOS] == dj.motivo_sin_tablas(EQUIPO, ENERGIA)
    _guardar_600(bd_vacia, originales)
    p.tablas_guardadas(EQUIPO, ENERGIA)
    assert celdas(panel.tabla_campos) == TABLA_DEL_EJEMPLO and panel.etiqueta_resumen.text() == RESUMEN_DEL_EJEMPLO
    assert panel.etiqueta_archivo.text() == f"Plan: Ejemplo de p…aciente) (archivo plan.json) {dj.RECALCULADO}"      # el recálculo se dice
    importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    assert panel.etiqueta_archivo.text() == "Plan: Ejemplo de p…aciente) (archivo plan.json)"


def test_la_nota_dice_que_si_otro_puesto_carga_tablas_hay_que_importar_otra_vez(p):
    assert p.panel_json.nota.text() == dj.NOTA and dj.NOTA.endswith("Si otro puesto carga tablas, vuelva a importar el plan.")
    assert dj.RECALCULADO == "Recalculado con las tablas cargadas hace un momento." and not SIMBOLOS.search(dj.NOTA + dj.RECALCULADO)


def test_cambiar_de_subpestana_no_pierde_la_tabla(p, monkeypatch, tmp_path):
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    elegir_fila(panel, 2)
    p.subpestanas.setCurrentIndex(0)
    p.subpestanas.setCurrentIndex(1)
    assert celdas(panel.tabla_campos) == TABLA_DEL_EJEMPLO and panel.etiqueta_um.text() == pantalla.texto_de_las_um(panel.filas[2].resultado)


def test_importar_no_guarda_nada(p, bd, monkeypatch, tmp_path):
    tablas = [t for (t,) in _sql(bd, "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    antes = {t: _sql(bd, f'SELECT COUNT(*) FROM "{t}"')[0][0] for t in tablas}
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    elegir_fila(panel, 1)
    QTest.mouseClick(panel.boton_copiar, Qt.LeftButton)
    assert {t: _sql(bd, f'SELECT COUNT(*) FROM "{t}"')[0][0] for t in tablas} == antes


def test_ninguna_excepcion_escapa_de_un_slot(p, monkeypatch, tmp_path):
    """Lo que escapa de un slot llega a `error_log.txt` por el `excepthook` de `main.py`: con un archivo hostil, un fallo inesperado del lector y uno del cálculo, nada escapa y la pantalla lo dice."""
    escapadas = []
    monkeypatch.setattr(sys, "excepthook", lambda *a: escapadas.append(a))
    panel = importar(p, monkeypatch, archivo(tmp_path, '{"plan": "Juana Pérez", "campos": [{"nombre": "Juana", "wedge": 1}, "x", null, {"dosis_cgy": 1e999}]}'))
    assert [f[ESTADO] for f in celdas(panel.tabla_campos)] == ["Sin calcular"] * 4
    with pytest.MonkeyPatch.context() as m:
        m.setattr(um_plan_json, "leer_plan", lambda texto: 1 / 0)
        importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    assert panel.etiqueta_rechazo.text() == "No se importó el archivo: la lectura falló por un error inesperado (ZeroDivisionError). Avise a quien mantiene la app."
    with pytest.MonkeyPatch.context() as m:
        m.setattr(um_plan_json, "calcular_plan", lambda *a, **k: 1 / 0)
        importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    assert panel.etiqueta_rechazo.text() == "El cálculo del plan falló por un error inesperado (ZeroDivisionError). Avise a quien mantiene la app." and panel.tabla_campos.rowCount() == 0
    assert escapadas == []


def test_un_motivo_o_un_rechazo_no_citan_el_nombre_del_plan(p, monkeypatch, tmp_path):
    panel = importar(p, monkeypatch, archivo(tmp_path, json.dumps({"plan": "Juana Pérez HC-0042", "paciente": "Juana Pérez HC-0042", "wedge": 1, "campos": [B]})))
    assert "Juana" not in panel.etiqueta_rechazo.text() and "HC-0042" not in panel.etiqueta_rechazo.text()


def test_ver_formato_muestra_el_ejemplo_que_las_pruebas_calculan_y_no_es_modal(p):
    QTest.mouseClick(p.panel_json.boton_formato, Qt.LeftButton)
    d = p.panel_json.dialogo_formato
    assert d.isVisible() and not d.isModal() and d.parent() is p.panel_json and d.windowTitle() == dj.TITULO_DEL_FORMATO
    assert d.ejemplo.toPlainText() == um_plan_json.EJEMPLO_DE_PLAN and d.ejemplo.isReadOnly() and d.explicacion.text() == dj.EXPLICACION_DEL_FORMATO
    assert um_plan_json.leer_plan(d.ejemplo.toPlainText())[0] == "Ejemplo de prueba (datos inventados, no es un paciente)"
    QTest.mouseClick(p.panel_json.boton_formato, Qt.LeftButton)
    assert p.panel_json.dialogo_formato is d                      # uno solo
    QTest.mouseClick(d.boton_copiar, Qt.LeftButton)
    assert QApplication.clipboard().text() == um_plan_json.EJEMPLO_DE_PLAN


# ================================================================================================================================== el ancho, las listas y el empaquetado

def test_las_etiquetas_nuevas_estan_en_la_lista_unica_de_la_pestana(p):
    assert all(e in p.etiquetas_que_cambian for e in p.panel_json.etiquetas_que_cambian) and len(set(p.etiquetas_que_cambian)) == len(p.etiquetas_que_cambian)
    assert all(e.wordWrap() for e in p.panel_json.etiquetas_que_cambian)


def test_un_plan_de_200_campos_con_nombres_enormes_no_ensancha_la_pestana(p, monkeypatch, tmp_path):
    p.subpestanas.setCurrentIndex(1)
    p.show()
    QApplication.processEvents()
    antes = p.minimumSizeHint().width()
    campos = [{**B, "nombre": ("Nombre enorme " if i % 2 else "N") * 40 + "\n" + "W" * 300, "um_planeador": 150 + i} for i in range(200)]
    panel = importar(p, monkeypatch, archivo(tmp_path, json.dumps({"plan": "P" * 500, "equipo": "600C", "energia": "6X", "campos": campos + [{"wedge": "x" * 400}]})))
    elegir_fila(panel, 200)
    QApplication.processEvents()
    assert panel.tabla_campos.rowCount() == 201 and p.minimumSizeHint().width() <= antes
    elegir_fila(panel, 0)
    QApplication.processEvents()
    assert p.minimumSizeHint().width() <= antes


def test_build_exe_lista_el_panel_una_vez_despues_del_dialogo_de_la_carga_y_sigue_en_crlf():
    crudo = open(os.path.join(RAIZ, "build_exe.py"), "rb").read()
    assert b"\r\n" in crudo and b"\n" not in crudo.replace(b"\r\n", b""), "build_exe.py sigue en CRLF"
    arbol = ast.parse(crudo.decode("utf-8"))
    lista = next(n.value for n in arbol.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "hidden_imports" for t in n.targets))
    nombres = [e.value for e in lista.elts]
    assert nombres.count("ui.paginasGuia.calculadora_um_json") == 1
    assert nombres.index("ui.paginasGuia.calculadora_um_json") == nombres.index("ui.paginasGuia.calculadora_um_cargar") + 1
    assert nombres.index("ui.paginasGuia.calculadora_um_cargar") == nombres.index("ui.paginasGuia.calculadora_um") + 1


def test_el_panel_no_tiene_sql_ni_fisica_y_sus_textos_siguen_las_reglas():
    fuente = open(os.path.join(RAIZ, "ui", "paginasGuia", "calculadora_um_json.py"), encoding="utf-8").read()
    arbol = ast.parse(fuente)
    importados = {n.module for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m and (m == "data" or m.startswith("data.") or "sqlite" in m or "matplotlib" in m or m == "services.um_datos_haz" or m == "services.um_armar") for m in importados), importados
    assert not re.search(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", fuente) and "motor.calcular(" not in fuente and "conectar(" not in fuente
    textos = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not any(SIMBOLOS.search(t) for t in textos) and not any(ENTRE_PARENTESIS.search(t) for t in textos)


# ================================================================================================================================== lo que dejó la cobertura (pre-vuelo, 12-11, 09:28)

def test_una_fila_sin_um_de_eclipse_da_su_numero_sin_error_ni_estado(p, monkeypatch, tmp_path):
    panel = importar(p, monkeypatch, archivo(tmp_path, un_plan({**B, "nombre": "sin Eclipse"})))
    elegir_fila(panel, 0)
    assert celdas(panel.tabla_campos)[0][ESTADO] == "Sin UM de Eclipse" and panel.etiqueta_resumen.text() == "1 campo: 0 dentro, 0 revisar, 0 fuera y 1 sin UM de Eclipse."
    assert panel.etiqueta_um.text() == "UM calculadas: 151.1 [UM]" and panel.etiqueta_error.text() == pantalla.SIN_UM_DE_ECLIPSE and panel.etiqueta_estado.text() == ""


def test_cambiar_los_umbrales_sin_plan_no_cambia_nada(p):
    escribir_umbrales(p, "2.5", "4")
    panel = p.panel_json
    assert panel.tabla_campos.rowCount() == 0 and panel.etiqueta_resumen.text() == "" and panel.etiqueta_um.text() == dj.ELIJA_UNA_FILA


@pytest.mark.parametrize("fallo, motivo", [(um_datos_haz.DatosHazError("Las tablas guardadas de Clinac 600, 6 MV no se pueden usar: el archivo «x» guardado no coincide con su huella"),
                                            "Las tablas guardadas de Clinac 600, 6 MV no se pueden usar: el archivo «x» guardado no coincide con su huella"),
                                           (OSError("disco"), "No se pudieron leer las tablas guardadas del Clinac 600, 6 MV: disco")])
def test_un_fallo_al_leer_las_tablas_queda_en_los_campos_de_ese_haz_con_el_motivo_de_la_parte_manual(p, monkeypatch, tmp_path, fallo, motivo):
    def falla(equipo, energia):
        raise fallo
    monkeypatch.setattr(um_datos_haz, "datos_del_haz", falla)
    p._haces.clear()
    panel = importar(p, monkeypatch, archivo(tmp_path, un_plan(B, {**B, "equipo": "iX"})))
    assert [f[AVISOS] for f in celdas(panel.tabla_campos)] == [motivo, dj.motivo_sin_tablas("Clinac iX", "6 MV")]


# ================================================================================================================================== segunda vuelta de la auditoría previa

def _lo_que_dibuja(ayuda):
    """El texto que Qt dibuja en una ayuda: la que parece HTML se dibuja como HTML."""
    if not Qt.mightBeRichText(ayuda):
        return ayuda
    documento = QTextDocument()
    documento.setHtml(ayuda)
    return documento.toPlainText()


def _plan_de(n, nombre=lambda i: f"C{i}"):
    return json.dumps({"equipo": "600C", "energia": "6X", "campos": [{**B, "nombre": nombre(i), "um_planeador": 100 + i % 9} for i in range(n)]})


def _a_la_vista(p, ancho, alto):
    p.resize(ancho, alto)
    p.show()
    p.subpestanas.setCurrentIndex(1)
    QApplication.processEvents()


def _huella_de_la_tabla(tabla):
    QApplication.processEvents()
    return celdas(tabla), [tabla.item(i, j).toolTip() for i in range(tabla.rowCount()) for j in range(tabla.columnCount())], \
        [tabla.columnWidth(j) for j in range(tabla.columnCount())]


def test_volver_a_calcular_1000_campos_no_congela_la_pantalla_y_deja_la_misma_tabla(p, monkeypatch, tmp_path):
    """Con la cabecera midiendo cada celda, volver a llenar 1000 filas (tras «Cargar tablas») tardaba 112 [s] y una tecla en un umbral 12 [s]. El límite es holgado (carga normal de la máquina)."""
    _a_la_vista(p, 1366, 768)
    panel = importar(p, monkeypatch, archivo(tmp_path, _plan_de(1000)))
    antes = _huella_de_la_tabla(panel.tabla_campos)
    inicio = time.perf_counter()
    panel.recalcular()
    QApplication.processEvents()
    assert time.perf_counter() - inicio < 3, f"recalcular 1000 campos: {time.perf_counter() - inicio:.1f} [s]"
    assert _huella_de_la_tabla(panel.tabla_campos) == antes
    inicio = time.perf_counter()
    p.umbrales["dentro"].setText("")
    p.umbrales["dentro"].textEdited.emit("")
    QApplication.processEvents()
    assert time.perf_counter() - inicio < 3, f"una tecla en un umbral con 1000 campos: {time.perf_counter() - inicio:.1f} [s]"
    assert {f[ESTADO] for f in celdas(panel.tabla_campos)} == {dj.SIN_EVALUAR}


HOSTILES = ["<b>NEGRITA</b> uno", "<img src=x> dos", "a &amp; b &lt;i&gt;", "&lt;b&gt;", "linea1\nlinea2<b>x</b>", "AP\u202eodnarpalg\u202c fin", "A\u200bB\u200b", "S\ud800S"]


@pytest.mark.parametrize("valor", HOSTILES)
def test_el_texto_del_archivo_se_ve_tal_cual_y_nunca_como_html(p, monkeypatch, tmp_path, valor):
    """Las etiquetas y las ayudas dibujaban como HTML un nombre o una clave con «<b>» o «&lt;» (el texto citado desaparecía); las marcas bidireccionales o de ancho cero no se veían."""
    plan = {"plan": valor, "equipo": "600C", "energia": "6X", "campos": [{**B, "nombre": valor, "um_planeador": 100},
                                                                           {**{k: v for k, v in B.items() if k != "dosis_cgy"}, "nombre": "malo", "dosis_cgy": valor}, {**B, valor: 1}]}
    panel = importar(p, monkeypatch, archivo(tmp_path, json.dumps(plan)))
    assert all(e.textFormat() == Qt.PlainText for e in p.etiquetas_que_cambian)
    assert panel.etiqueta_archivo.text() == pantalla.sin_palabras_enormes(f"Plan: {dj.nombre_para_mostrar(valor)} (archivo plan.json)")
    tabla = panel.tabla_campos
    for i in range(tabla.rowCount()):
        for j in range(tabla.columnCount()):
            assert _lo_que_dibuja(tabla.item(i, j).toolTip()) == (dj.nombre_completo(valor) if (i, j) == (0, 0) else tabla.item(i, j).text())
    for i in (1, 2):
        elegir_fila(panel, i)
        assert panel.etiqueta_motivo.text() == pantalla.sin_palabras_enormes(panel.filas[i].motivo) and panel.etiqueta_motivo.textFormat() == Qt.PlainText
    vistos = [panel.etiqueta_archivo.text()] + [tabla.item(0, 0).text(), tabla.item(0, 0).toolTip()]
    assert not any(c in t for t in vistos for c in "\u202e\u202c\u200b\ud800")       # lo que no se ve, con su código


def test_una_ayuda_sin_html_queda_igual_y_la_regla_comun_vale_para_los_dialogos():
    assert pantalla.ayuda_en_texto_plano("AP & PA") == "AP & PA" and pantalla.ayuda_en_texto_plano("R&amp;D") == "R&amp;D"       # sin HTML, igual: nunca «&amp;» de más
    assert _lo_que_dibuja(pantalla.ayuda_en_texto_plano("<b>x</b> & y")) == "<b>x</b> & y"
    tabla = QTableWidget(0, 1)
    carga._llenar(tabla, [("<b>archivo</b>.txt",)])
    assert _lo_que_dibuja(tabla.item(0, 0).toolTip()) == "<b>archivo</b>.txt"


def test_el_nombre_se_ve_con_lo_que_no_se_ve_escrito_con_su_codigo():
    assert dj.nombre_para_mostrar("AP\u202eodnarpalg\u202c fin") == "AP<U+202E>odnarpalg<U+202C> fin"
    assert dj.nombre_para_mostrar("A\u200bB") == "A<U+200B>B" != dj.nombre_para_mostrar("AB")
    assert dj.nombre_completo("A\u200bB") == "A<U+200B>B"


def test_el_nombre_entero_va_en_la_ayuda_y_en_lo_copiado(p, monkeypatch, tmp_path):
    """Tres campos que difieren en el medio se veían iguales en la celda, en su ayuda y en lo copiado."""
    nombres = [f"Lateral derecho segmento {n} Clinac 600 6 MV sin cuña" for n in (1, 2, 3)]
    panel = importar(p, monkeypatch, archivo(tmp_path, _plan_de(3, lambda i: nombres[i])))
    assert len({f[CAMPO] for f in celdas(panel.tabla_campos)}) == 1 and [panel.tabla_campos.item(i, 0).toolTip() for i in range(3)] == nombres
    for i in range(3):
        elegir_fila(panel, i)
        QTest.mouseClick(panel.boton_copiar, Qt.LeftButton)
        assert QApplication.clipboard().text().split("\n")[0].startswith(f"Campo: {nombres[i]} | ")
    absurdo = "palabra " * 1000
    assert len(dj.nombre_completo(absurdo)) == 2 * dj.MITAD_DEL_NOMBRE + 1 and dj.nombre_completo("x" * dj.MAXIMO_DEL_NOMBRE) == "x" * dj.MAXIMO_DEL_NOMBRE


@pytest.mark.parametrize("ancho, alto, filas_que_se_ven", [(1366, 768, 7), (1920, 1080, 10)])
def test_el_desglose_de_la_fila_elegida_se_ve_casi_entero(p, monkeypatch, tmp_path, ancho, alto, filas_que_se_ven):
    """A 1366 x 768 el desglose de la fila elegida se veía en 79 [px]: 2 de sus 10 filas (la parte manual, 8)."""
    _a_la_vista(p, ancho, alto)
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    elegir_fila(panel, 1)
    QApplication.processEvents()
    tabla = panel.tabla_desglose
    assert tabla.rowCount() == 10 and min(10, tabla.viewport().height() // pantalla.ALTO_DE_UNA_FILA) >= filas_que_se_ven
    izquierda, derecha = panel.divisor.sizes()
    assert 0.55 < izquierda / (izquierda + derecha) < 0.65       # el reparto de 3 a 2, no el ancho que pide el texto de la nota
    assert [panel.divisor.widget(i).sizePolicy().horizontalStretch() for i in range(2)] == [3, 2]
    estiramiento = lambda divisor: [divisor.widget(i).sizePolicy().verticalStretch() for i in range(2)]      # noqa: E731
    assert estiramiento(panel.divisor_del_desglose) == estiramiento(p.divisor_del_resultado) == [3, 1]       # el desglose y los avisos, como en la parte manual


def test_los_textos_fijos_y_las_medidas_del_panel_son_los_que_ve_el_fisico(p):
    assert dj.NADA_IMPORTADO == "Ningún plan importado. Pulse «Importar JSON» y elija el archivo del plan; «Ver formato» muestra cómo es."
    assert dj.ELIJA_UNA_FILA == "Elija una fila de la tabla para ver su desglose."
    assert dj.TITULO_DEL_FORMATO == "Calculadora UM: el formato del JSON de un plan" and dj.FILTRO == "Planes JSON (*.json);;Todos los archivos (*)"
    assert dj.EXPLICACION_DEL_FORMATO.startswith("Un objeto con «equipo», «energia» y la lista «campos»") and dj.EXPLICACION_DEL_FORMATO.endswith("reales del Clinac 600, 6 MV:")
    QTest.mouseClick(p.panel_json.boton_formato, Qt.LeftButton)
    assert (p.panel_json.dialogo_formato.width(), p.panel_json.dialogo_formato.height()) == (760, 620)
    assert dj.nombre_completo("x" * 200) == "x" * 200 and dj.nombre_completo("x" * 99 + "yyy" + "z" * 99) == "x" * 99 + "…" + "z" * 99


def test_unas_um_de_eclipse_absurdas_no_ensanchan_la_columna_y_su_motivo_las_cita(p, monkeypatch, tmp_path):
    _a_la_vista(p, 1366, 768)
    panel = importar(p, monkeypatch, archivo(tmp_path, un_plan({**B, "nombre": "e200", "um_planeador": 1e200}, {**B, "nombre": "e300", "um_planeador": 1e300}, {**B, "um_planeador": 151})))
    QApplication.processEvents()
    tabla = panel.tabla_campos
    assert [len(tabla.item(i, ECLIPSE).text()) for i in range(3)] == [pantalla.MAXIMO_CITADO - 9, pantalla.MAXIMO_CITADO - 9, 3]
    assert tabla.columnWidth(ECLIPSE) < 300       # con el número entero, 1966 [px]
    elegir_fila(panel, 0)
    assert panel.etiqueta_motivo.text().endswith("1e+200")


# ================================================================================================================================== auditoría de la ronda 2

@pytest.mark.parametrize("nombre, visto", [
    ("x" * 22 + "\u200b" * 2, "x" * 22 + "<U+200B>" * 2), ("x" * 23 + "\u200b" * 2, "x" * 20 + "…" + "<U+200B>" * 2), ("Campo" + "\u200b" * 4, "Campo" + "<U+200B>" * 4),
    ("Campo" + "\u200b" * 5, "Campo<U+200B>…" + "<U+200B>" * 2), ("\u200b" * 30, "<U+200B>" * 2 + "…" + "<U+200B>" * 2), ("\u202e" * 30, "<U+202E>" * 2 + "…" + "<U+202E>" * 2),
    ("\u200b" * 200, "<U+200B>" * 2 + "…" + "<U+200B>" * 2), ("\u200b" * 12 + "x" * 30, "<U+200B>" * 2 + "…" + "x" * 16), ("a" * 5 + "\u200b" * 25, "aaaaa<U+200B>…" + "<U+200B>" * 2),
    ("Campo  de\npelvis" + "\u200b" * 3, "Campo de pelvis…" + "<U+200B>" * 2)],
    ids=["38 entero", "39 cortado", "Campo y 4", "Campo y 5", "30 U+200B", "30 U+202E", "200 U+200B", "12 U+200B y 30 x", "5 a y 25 U+200B", "con espacios y saltos"])
def test_lo_que_no_se_ve_no_alarga_el_nombre_de_su_celda(nombre, visto):
    """Cada carácter que no se ve se escribe con su código de 8 caracteres: 30 de ellos daban una celda de 240. El tope va sobre lo que se ve, sin partir un código."""
    assert dj.nombre_para_mostrar(nombre) == visto


def test_cuantos_caracteres_caben_con_sus_codigos():
    assert [dj._caben("ab\u200b", largo) for largo in (9, 10, 11)] == [2, 3, 3] and dj._caben("\u200bab", 7) == 0


def test_un_nombre_de_puro_invisible_no_ensancha_la_columna_del_campo(p, monkeypatch, tmp_path):
    """Con 30 caracteres que no se ven la columna «Campo» medía 2461 [px] y «Estado» y las demás quedaban fuera de vista."""
    _a_la_vista(p, 1366, 768)
    nombres = ["\u200b" * 30, "\u202e" * 30, "\u200b" * 200, "\u200b" * 12 + "x" * 30, "Campo" + "\u200b" * 20]
    panel = importar(p, monkeypatch, archivo(tmp_path, _plan_de(len(nombres), lambda i: nombres[i])))
    QApplication.processEvents()
    tabla = panel.tabla_campos
    assert max(len(f[CAMPO]) for f in celdas(tabla)) <= um_plan_json.MAXIMO_CITADO + len("<U+200B>")
    assert tabla.columnWidth(CAMPO) < 450 and tabla.columnViewportPosition(ESTADO) + tabla.columnWidth(ESTADO) <= tabla.viewport().width()
    assert [_lo_que_dibuja(tabla.item(i, CAMPO).toolTip()) for i in range(len(nombres))] == [dj.nombre_completo(n) for n in nombres]      # el nombre entero, en su ayuda


# ================================================================================================================================== revisión de la ronda 1 (24-11): la salida de las columnas quietas

def _ancho_del_texto(tabla, j):
    metricas = QFontMetrics(tabla.font())
    return max(metricas.horizontalAdvance(tabla.item(i, j).text()) for i in range(tabla.rowCount()))


def _la_cabecera_mide_su_contenido(tabla):
    """La cabecera quedó midiendo (no fija) y cada columna, salvo la última (toma lo que sobra), es tan ancha como su texto más ancho."""
    QApplication.processEvents()
    assert tabla.rowCount() > 0
    cabecera = tabla.horizontalHeader()
    assert [cabecera.sectionResizeMode(j) for j in range(tabla.columnCount())] == [QHeaderView.ResizeToContents] * tabla.columnCount()
    cortadas = [(j, tabla.columnWidth(j), _ancho_del_texto(tabla, j)) for j in range(tabla.columnCount() - 1) if tabla.columnWidth(j) < _ancho_del_texto(tabla, j)]
    assert not cortadas, f"(columna, ancho, texto) de las que cortan su texto: {cortadas}"


def test_las_columnas_quietas_no_miden_adentro_y_vuelven_a_medir_al_salir(p):
    tabla = p.tabla_desglose
    modos = lambda: [tabla.horizontalHeader().sectionResizeMode(j) for j in range(tabla.columnCount())]      # noqa: E731
    assert modos() == [QHeaderView.ResizeToContents] * tabla.columnCount()
    with pantalla.columnas_quietas(tabla):
        assert modos() == [QHeaderView.Fixed] * tabla.columnCount()
    assert modos() == [QHeaderView.ResizeToContents] * tabla.columnCount()


def test_las_columnas_quietas_vuelven_a_medir_aunque_el_llenado_falle_a_medias(p):
    tabla = p.tabla_desglose
    with pytest.raises(ZeroDivisionError):
        with pantalla.columnas_quietas(tabla):
            1 / 0
    assert [tabla.horizontalHeader().sectionResizeMode(j) for j in range(tabla.columnCount())] == [QHeaderView.ResizeToContents] * tabla.columnCount()


def _llenada_a_mano(p, monkeypatch, tmp_path):
    for clave, texto in {"dosis": "90", "x": "10", "y": "15", "ssd": "90", "prof": "10", "um_planeador": "111"}.items():
        p.campos[clave].setText(texto)
    p.calcular()
    return p.tabla_desglose


def _llenada_con_el_plan(p, monkeypatch, tmp_path):
    return importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN)).tabla_campos


def _llenada_con_la_fila_elegida(p, monkeypatch, tmp_path):
    panel = importar(p, monkeypatch, archivo(tmp_path, um_plan_json.EJEMPLO_DE_PLAN))
    elegir_fila(panel, 1)
    return panel.tabla_desglose


def _refrescada_con_umbrales_que_no_sirven(p, monkeypatch, tmp_path):
    panel = importar(p, monkeypatch, archivo(tmp_path, un_plan({**B, "nombre": "uno", "um_planeador": 151})))
    assert celdas(panel.tabla_campos)[0][ESTADO] == "Dentro"
    escribir_umbrales(p, "5", "3")
    assert celdas(panel.tabla_campos)[0][ESTADO] == dj.SIN_EVALUAR
    return panel.tabla_campos


@pytest.mark.parametrize("llenar", [_llenada_a_mano, _llenada_con_el_plan, _llenada_con_la_fila_elegida, _refrescada_con_umbrales_que_no_sirven],
                         ids=["desglose de la parte manual", "tabla de campos del JSON", "desglose de la fila elegida del JSON", "tabla de campos tras cambiar los umbrales"])
def test_despues_de_llenar_o_refrescar_una_tabla_sus_columnas_miden_su_contenido(p, monkeypatch, tmp_path, llenar):
    _la_cabecera_mide_su_contenido(llenar(p, monkeypatch, tmp_path))
