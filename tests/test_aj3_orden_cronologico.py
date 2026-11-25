"""Las listas de controles quedan en orden de fecha, la más reciente arriba.

- `services/orden_de_controles.py`: la clave (año, mes, día) de cada forma de `controles.fecha` y el orden estable.
- Las 8 listas (6 de `load.py` y 2 de `tablas_anuales.py`), con filas sintéticas y con la copia del 23-11, contra un generador independiente con `datetime`.
- Con la misma fecha, el registro más nuevo primero; una forma desconocida va al final y nunca da error; el texto que se ve no cambia.
- Datos reales: la copia del 23-11 (sus tres archivos, a un temporal).
"""
import ast
import hashlib
import importlib
import os
import random
import re
import shutil
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QTableWidget

import data.ManejoDatos.conection as conection_mod
import data.ManejoDatos.load as load_mod
import data.ManejoDatos.Tablas_Anuales.tablas_anuales as anuales_mod
from data.ManejoDatos.conection import Conexion

import _bd_referencia

RAIZ = Path(__file__).resolve().parent.parent
MODULO = "services.orden_de_controles"
USUARIO = "Fisico de Prueba"

# (nombre, módulo, función, equipo de la consulta, tipo de control, argumentos, la fecha se muestra como «aaaa-mm»)
LISTAS = [
    ("mensual del 600", load_mod, "mostrar_controles_mensuales", "Clinac 600", "Mensual", {"equipo_filtrar": "Clinac 600"}, False),
    ("mensual del iX", load_mod, "mostrar_controles_mensuales", "Clinac ix", "Mensual", {"equipo_filtrar": "Clinac ix"}, False),
    ("mensual del Halcyon", load_mod, "mostrar_controles_mensuales", "Halcyon", "Mensual", {"equipo_filtrar": "Halcyon"}, False),
    ("imagenes anual del iX", load_mod, "mostrar_controles_imgIX_anual", "Clinac ix", "Anual", {"usuario": USUARIO}, True),
    ("imagenes mensual del iX", load_mod, "mostrar_controles_imgIX", "Clinac ix", "Mensual", {"usuario": USUARIO}, False),
    ("imagenes anual del Halcyon", load_mod, "mostrar_controles_imgHC_anual", "Halcyon", "Anual", {"usuario": USUARIO}, True),
    ("imagenes mensual del Halcyon", load_mod, "mostrar_controles_imgHC", "Halcyon", "Mensual", {"usuario": USUARIO}, False),
    ("Tomografo", load_mod, "mostrar_controles_tac", "Tomógrafo", "Mensual", {"usuario": USUARIO}, False),
    ("anual del 600", anuales_mod, "mostrar_controles_anuales", "Clinac 600", "Anual", {"equipo_filtrar": "Clinac 600"}, False),
    ("anual del iX", anuales_mod, "mostrar_controles_anuales", "Clinac ix", "Anual", {"equipo_filtrar": "Clinac ix"}, False),
    ("anual del Halcyon", anuales_mod, "mostrar_controles_anuales", "Halcyon", "Anual", {"equipo_filtrar": "Halcyon"}, False),
]
IDS = [l[0] for l in LISTAS]

# (id, fecha guardada, activo): las dos formas guardadas, días sin cero, empates con textos distintos, formas desconocidas, la de 2029 y una anulada
SINTETICAS = [(11, "31/08/2026", 1), (3, "05/11/2026", 1), (8, "16/10/2026", 1), (2, "07/2026", 1), (14, "22/12/2025", 1),
              (5, "5/1/2026", 1), (9, "05/01/2026", 1), (12, "2026-01-05", 1), (6, "24/01/2029", 1), (4, "fecha por confirmar", 1),
              (10, "06/2026", 1), (13, "2026-06", 1), (7, "13/2026", 1), (15, "09/2026", 1), (1, "15/09/2026", 0)]
# Las dos listas anuales de imágenes: al menos 3 años y meses distintos, un empate en «aaaa-mm» y una forma que se muestra rara
SINTETICAS_ANUAL_IMG = [(4, "03/2024", 1), (9, "11/2026", 1), (2, "07/2025", 1), (7, "01/2029", 1), (5, "11/2026-b", 1),
                        (8, "15/03/2026", 1), (3, "02/2026", 1), (6, "12/2023", 1), (1, "05/2026", 0)]


# ====================================================================================================== la verdad, con datetime

FORMATOS = ("%d/%m/%Y", "%Y-%m-%d", "%m/%Y", "%Y-%m")


def instante(texto):
    """El instante de la fecha con `datetime`; sin día, medio día antes del día 1 de su mes; None si no se reconoce."""
    if not isinstance(texto, str) or not texto.isascii() or texto != texto.strip():
        return None
    for formato in FORMATOS:
        try:
            momento = datetime.strptime(texto, formato)
        except ValueError:
            continue
        return momento if "%d" in formato else momento - timedelta(hours=12)
    return None


def orden_verdadero(filas):
    """Filas (id, fecha mostrada): primero lo reconocido, de lo más reciente a lo más viejo; empates y desconocidas, el id mayor primero."""
    return sorted(filas, key=lambda f: (instante(f[1]) is not None, instante(f[1]) or datetime.min, f[0]), reverse=True)


def como_se_muestra(fecha, anual_img):
    """La fecha como la muestra la lista: en las anuales de imágenes, «aaaa-mm» (`substr(fecha, 4, 4) || '-' || substr(fecha, 1, 2)`) si ese texto tiene esa forma; si no, la guardada."""
    if not anual_img:
        return fecha
    de_hoy = f"{fecha[3:7]}-{fecha[0:2]}"
    return de_hoy if re.fullmatch(r"[0-9]{4}-[0-9]{2}", de_hoy) else fecha


# ====================================================================================================== fijaciones

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def orden():
    """El módulo nuevo; sin él, la prueba cae diciendo que falta."""
    try:
        return importlib.import_module(MODULO)
    except ImportError as error:
        pytest.fail(f"falta el módulo {MODULO}: {error}")


@pytest.fixture
def dialogos(monkeypatch):
    """Trampa 2: ningún modal se abre (en PyQt5 `exec` y `exec_` son dos métodos)."""
    abiertos = []
    for nombre in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, nombre, staticmethod(lambda *a, **k: abiertos.append(a) or QMessageBox.Ok))
    for nombre in ("exec_", "exec"):
        monkeypatch.setattr(QDialog, nombre, lambda self: abiertos.append(self) or 0)
    return abiertos


@pytest.fixture
def bd(app, monkeypatch, tmp_path, dialogos):
    """Una base temporal con el esquema de la app."""
    ruta = str(tmp_path / "aj3.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
    previa = Conexion._instance
    Conexion._instance = None
    Conexion().con.close()
    Conexion._instance = None
    yield ruta
    if Conexion._instance is not None:
        Conexion._instance.con.close()
    Conexion._instance = previa


def _md5(ruta):
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


@pytest.fixture(scope="module")
def copia_23_11(app, tmp_path_factory):
    """Los TRES archivos de la copia del 23-11 a un temporal; el original no se abre y su md5 no cambia."""
    original = _bd_referencia.BD_REBUILD_23_11
    if not original.exists():
        pytest.skip(f"HI-0: falta {original.name} en {_bd_referencia.CARPETA_BD}")
    destino = tmp_path_factory.mktemp("copia_23_11")
    nombres = [original.name, original.name + "-wal", original.name + "-shm"]
    antes = {n: _md5(original.parent / n) for n in nombres if (original.parent / n).exists()}
    for n in antes:
        shutil.copy2(original.parent / n, destino / n)
    assert antes == {n: _md5(original.parent / n) for n in antes}, "el md5 de la base de referencia cambió al copiarla"
    return str(destino / original.name)


@pytest.fixture
def real(copia_23_11, monkeypatch, tmp_path, dialogos):
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: copia_23_11)
    monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
    previa = Conexion._instance
    Conexion._instance = None
    yield copia_23_11
    if Conexion._instance is not None:
        Conexion._instance.con.close()
    Conexion._instance = previa


def sembrar(ruta, equipo, control, filas):
    con = sqlite3.connect(ruta)
    con.executemany("INSERT INTO controles (id, equipo, control, fecha, activo) VALUES (?, ?, ?, ?, ?)",
                    [(i, equipo, control, f, a) for i, f, a in filas])
    con.commit()
    con.close()


def consulta(ruta, sql, params=()):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def mostrada(modulo, funcion, argumentos):
    """La lista como la ve el físico: (id guardado en la fila, fecha que se ve), de arriba abajo."""
    tabla = QTableWidget()
    getattr(modulo, funcion)(None, tabla, **argumentos)
    filas = [(tabla.item(f, 0).data(Qt.UserRole), tabla.item(f, 0).text()) for f in range(tabla.rowCount())]
    tabla.deleteLater()
    return filas


# ====================================================================================================== 1. la clave

@pytest.mark.parametrize("texto, clave", [
    ("05/11/2026", (2026, 11, 5)), ("5/1/2026", (2026, 1, 5)), ("31/08/2026", (2026, 8, 31)), ("07/2026", (2026, 7, 0)),
    ("7/2026", (2026, 7, 0)), ("2026-07", (2026, 7, 0)), ("2026-07-05", (2026, 7, 5)), ("24/01/2029", (2029, 1, 24)),
    ("29/02/2028", (2028, 2, 29)), ("2026-7", (2026, 7, 0)), ("2026-7-5", (2026, 7, 5)),
])
def test_cada_forma_conocida_da_anio_mes_y_dia(orden, texto, clave):
    assert orden.clave_cronologica(texto) == clave


@pytest.mark.parametrize("texto", [None, "", "fecha por confirmar", "13/2026", "00/2026", "2026-13", "31/02/2026", "29/02/2026",
                                   "32/01/2026", "05-11-2026", "2026/07", "05/11/26", " 05/11/2026", "05/11/2026 ", "03/2-15",
                                   "٠٥/٢٠٢٦", "05/0000", 20261105, 3.5, b"05/11/2026", "03/26", "26-07", "26-07-05", "007/2026",
                                   "05/11/2026\n", "07/2026\n", "2026-07-05\n", "2026-07\n", "05/11/2026\r\n", "00/11/2026", "2026-11-00"])
def test_una_forma_desconocida_da_la_clave_que_va_al_final_y_nunca_lanza(orden, texto):
    clave = orden.clave_cronologica(texto)
    assert clave == orden.DESCONOCIDA
    assert clave < orden.clave_cronologica("01/0001") and clave < orden.clave_cronologica("01/01/0001")


def test_sin_dia_va_despues_de_los_dias_de_su_mes_y_antes_que_el_mes_siguiente(orden):
    c = orden.clave_cronologica
    assert c("01/08/2026") > c("08/2026") > c("31/07/2026")
    assert c("08/2026") == c("2026-08") and c("05/11/2026") == c("2026-11-05") == c("5/11/2026")


def test_anio_antes_que_mes_y_mes_antes_que_dia(orden):
    c = orden.clave_cronologica
    assert c("01/01/2027") > c("31/12/2026") > c("01/12/2026") > c("30/11/2026")
    assert c("12/2025") < c("01/2026")


def test_el_orden_es_estable_y_lo_mas_reciente_va_primero(orden):
    filas = [(9, "05/01/2026", "a"), (7, "07/2026", "b"), (5, "5/1/2026", "c"), (3, "raro", "d"), (2, "2026-01-05", "e"), (1, "x", "f")]
    assert orden.mas_reciente_primero(filas, 1) == [filas[1], filas[0], filas[2], filas[4], filas[3], filas[5]]
    assert orden.mas_reciente_primero([], 1) == []


@pytest.mark.parametrize("semilla", range(40))
def test_contra_el_generador_independiente_con_datetime(orden, semilla):
    azar = random.Random(semilla)
    inicio = date(2019, 1, 1).toordinal()
    raras = ["", "fecha", "13/2026", "31/02/2026", "2026/07", "05-11-2026", "03/2-15"]
    filas, ids = [], azar.sample(range(1, 10000), 60)
    for i in ids:
        d = date.fromordinal(inicio + azar.randrange(0, 4400))
        forma = azar.randrange(6)
        texto = [d.strftime("%d/%m/%Y"), f"{d.day}/{d.month}/{d.year}", d.strftime("%m/%Y"), d.strftime("%Y-%m"),
                 d.strftime("%Y-%m-%d"), azar.choice(raras)][forma]
        filas.append((i, texto))
    filas += [(ids[0] + 10000, filas[0][1]), (ids[1] + 10000, filas[1][1])]
    llegada = sorted(filas, key=lambda f: f[0], reverse=True)
    assert orden.mas_reciente_primero(llegada, 1) == orden_verdadero(filas)


def lectura_verdadera(texto):
    """(año, mes, día) con `strptime`, día 0 si la forma no lo trae; None si no se reconoce."""
    if not isinstance(texto, str) or not texto.isascii() or texto != texto.strip():
        return None
    for formato in FORMATOS:
        try:
            momento = datetime.strptime(texto, formato)
        except ValueError:
            continue
        return (momento.year, momento.month, momento.day if "%d" in formato else 0)
    return None


def textos_de_la_gramatica():
    """Las cuatro formas con 0 a 3 cifras de día y de mes y de 0 a 5 de año (ceros a la izquierda y cifras arábigas), y cada forma válida con un carácter de más."""
    dias = ["", "0", "00", "000", "1", "01", "001", "12", "31", "32", "100", "٠٥"]
    meses = ["", "0", "00", "000", "1", "01", "001", "12", "13", "100", "٠٧"]
    anios = ["", "1", "202", "2026", "0000", "0001", "20260", "٢٠٢٦"]
    for a in anios:
        for m in meses:
            yield f"{m}/{a}"
            yield f"{a}-{m}"
            for d in dias:
                yield f"{d}/{m}/{a}"
                yield f"{a}-{m}-{d}"
    for base in ("05/11/2026", "5/1/2026", "11/2026", "2026-11", "2026-11-05", "2026-1-5"):
        for sobra in ("\n", "\r\n", " ", "\t", "\u00a0", "\x00", "\n\n"):
            yield base + sobra
            yield sobra + base


def test_toda_combinacion_de_cifras_de_las_cuatro_formas_da_lo_mismo_que_strptime(orden):
    distintas = [(t, orden.clave_cronologica(t), lectura_verdadera(t) or orden.DESCONOCIDA) for t in textos_de_la_gramatica()
                 if orden.clave_cronologica(t) != (lectura_verdadera(t) or orden.DESCONOCIDA)]
    assert not distintas, f"{len(distintas)} textos que no dan lo que da strptime: {distintas[:6]}"


# ====================================================================================================== 2. las 8 listas, filas sintéticas

@pytest.mark.parametrize("nombre, modulo, funcion, equipo, control, argumentos, anual_img", LISTAS, ids=IDS)
def test_cada_lista_muestra_lo_mas_reciente_arriba_con_filas_sinteticas(bd, nombre, modulo, funcion, equipo, control, argumentos, anual_img):
    filas = SINTETICAS_ANUAL_IMG if anual_img else SINTETICAS
    sembrar(bd, equipo, control, filas)
    sembrar(bd, "Equipo ajeno", control, [(100, "01/2030", 1)])
    esperado = orden_verdadero([(i, como_se_muestra(f, anual_img)) for i, f, a in filas if a == 1])
    assert mostrada(modulo, funcion, argumentos) == esperado


def test_la_lista_sin_equipo_del_mensual_no_se_ordena(bd):
    sembrar(bd, "Clinac 600", "Mensual", SINTETICAS)
    vigentes = consulta(bd, "SELECT id, fecha FROM controles WHERE (activo IS NULL OR activo = 1)")
    assert mostrada(load_mod, "mostrar_controles_mensuales", {"equipo_filtrar": None}) == vigentes


def test_la_lista_anual_sin_equipo_tambien_va_en_orden_de_fecha(bd):
    sembrar(bd, "Clinac 600", "Anual", SINTETICAS)
    sembrar(bd, "Halcyon", "Anual", [(100, "01/2030", 1), (101, "2024-02", 1)])
    vigentes = consulta(bd, "SELECT id, fecha FROM controles WHERE control = 'Anual' AND (activo IS NULL OR activo = 1)")
    assert mostrada(anuales_mod, "mostrar_controles_anuales", {"equipo_filtrar": None}) == orden_verdadero(vigentes)


def test_ninguna_lista_abre_un_dialogo(bd, dialogos):
    for nombre, modulo, funcion, equipo, control, argumentos, anual_img in LISTAS:
        assert mostrada(modulo, funcion, argumentos) == [], nombre
    for k, (nombre, modulo, funcion, equipo, control, argumentos, anual_img) in enumerate(LISTAS):
        sembrar(bd, equipo, control, [(200 + k, f"{k + 1:02d}/2026", 1)])
        assert mostrada(modulo, funcion, argumentos), nombre
    assert dialogos == []


# ------------------------------------------------------------------------------------------- el anual de imágenes guardado con día

LISTAS_ANUAL_IMG = [l for l in LISTAS if l[6]]
# Lo que guarda la app: «mm/aaaa» (el anual de dosimetría) y «dd/mm/aaaa» (la página de imágenes, si el anual del año nace ahí)
ANUALES_CON_DIA = [(1, "03/2024", 1), (2, "05/2025", 1), (3, "02/2026", 1), (4, "15/01/2027", 1), (5, "20/06/2025", 1)]
SE_VEN = [(4, "15/01/2027"), (3, "2026-02"), (5, "20/06/2025"), (2, "2025-05"), (1, "2024-03")]
ANUALES_ANTERIORES = [(1, "03/2023", 1), (2, "05/2024", 1), (3, "02/2025", 1)]  # sin anual de 2026: la identidad de un anual es equipo y año


@pytest.mark.parametrize("nombre, modulo, funcion, equipo, control, argumentos, anual_img", LISTAS_ANUAL_IMG, ids=[l[0] for l in LISTAS_ANUAL_IMG])
def test_un_anual_de_imagenes_guardado_con_dia_se_ve_como_se_guardo_y_va_en_su_lugar(bd, nombre, modulo, funcion, equipo, control, argumentos, anual_img):
    sembrar(bd, equipo, control, ANUALES_CON_DIA)
    assert mostrada(modulo, funcion, argumentos) == SE_VEN


@pytest.mark.parametrize("nombre, modulo, funcion, equipo, control, argumentos, anual_img", LISTAS_ANUAL_IMG, ids=[l[0] for l in LISTAS_ANUAL_IMG])
def test_el_reporte_y_eliminar_de_un_anual_de_imagenes_usan_la_fecha_que_se_ve(bd, monkeypatch, nombre, modulo, funcion, equipo, control, argumentos, anual_img):
    import models.PDF.Imagenes.reportes_control_sistema_imagenes as reporte_mod
    from PyQt5.QtWidgets import QPushButton
    pedidos, preguntas = [], []
    monkeypatch.setattr(reporte_mod, "generar_reporte_sistema_imagenes", lambda padre, fecha, maquina, usuario, sesion, **kw: pedidos.append((sesion, fecha)))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: preguntas.append(a[2]) or QMessageBox.No))
    sembrar(bd, equipo, control, ANUALES_CON_DIA)
    tabla = QTableWidget()
    getattr(modulo, funcion)(object(), tabla, **argumentos)
    for fila in range(tabla.rowCount()):
        tabla.cellWidget(fila, 15).findChild(QPushButton).click()
        tabla.setCurrentCell(fila, 0)
        load_mod.eliminarRegistroCT_anual(None, tabla)
    tabla.deleteLater()
    assert pedidos == [(i, t.replace("/", "-")) for i, t in SE_VEN]
    assert preguntas == [f"¿Eliminar control anual de {t}?" for _, t in SE_VEN]
    assert consulta(bd, "SELECT COUNT(*) FROM controles WHERE activo = 0") == [(0,)]


@pytest.mark.parametrize("nombre, modulo, funcion, equipo, control, argumentos, anual_img", LISTAS_ANUAL_IMG, ids=[l[0] for l in LISTAS_ANUAL_IMG])
def test_un_anual_que_la_pagina_de_imagenes_crea_hoy_se_ve_con_su_fecha_y_va_arriba(bd, nombre, modulo, funcion, equipo, control, argumentos, anual_img):
    from PyQt5.QtCore import QDate
    from PyQt5.QtWidgets import QDateEdit
    from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
    con = sqlite3.connect(bd)
    con.execute("INSERT INTO users (fullname) VALUES (?)", (USUARIO,))
    con.commit()
    con.close()
    sembrar(bd, equipo, control, ANUALES_ANTERIORES)

    class Pagina:  # lo que la página de imágenes anual tiene al crear su control (el escritor real: limpiar_layout y create_control)
        anual = True
        esiX_images = equipo == "Clinac ix"
        esHC_images = equipo == "Halcyon"
        equipo_f = equipo
        user_id = USUARIO
        limpiar_layout = PruebaMensual600.limpiar_layout
        _fecha_real_del_control = PruebaMensual600._fecha_real_del_control

    pagina = Pagina()
    pagina.date_box = QDateEdit()
    pagina.date_box.setDate(QDate(2026, 1, 15))
    try:
        assert pagina.limpiar_layout([], USUARIO, equipo, nombre_fisico1=USUARIO)
    finally:
        pagina.date_box.deleteLater()
    assert consulta(bd, "SELECT control, fecha FROM controles WHERE id = ?", (pagina.ref,)) == [("Anual", "15/01/2026")]
    assert mostrada(modulo, funcion, argumentos) == [(pagina.ref, "15/01/2026"), (3, "2025-02"), (2, "2024-05"), (1, "2023-03")]


# ====================================================================================================== 3. la copia del 23-11

@pytest.mark.parametrize("nombre, modulo, funcion, equipo, control, argumentos, anual_img", LISTAS, ids=IDS)
def test_real_cada_lista_en_orden_de_fecha(real, nombre, modulo, funcion, equipo, control, argumentos, anual_img):
    vigentes = consulta(real, "SELECT id, fecha FROM controles WHERE equipo = ? AND control = ? AND (activo IS NULL OR activo = 1)", (equipo, control))
    esperado = orden_verdadero([(i, como_se_muestra(f, anual_img)) for i, f in vigentes])
    assert mostrada(modulo, funcion, argumentos) == esperado


def test_real_la_primera_pestana_del_600_empieza_en_noviembre(real):
    fechas = [f for _, f in mostrada(load_mod, "mostrar_controles_mensuales", {"equipo_filtrar": "Clinac 600"})]
    assert fechas[:3] == ["05/11/2026", "16/10/2026", "31/08/2026"]
    assert fechas.index("05/11/2026") < fechas.index("31/08/2026") < fechas.index("07/2026") < fechas.index("22/12/2025")


def test_real_el_halcyon_tiene_arriba_el_control_de_2029_porque_esa_es_su_fecha_guardada(real):
    filas = mostrada(load_mod, "mostrar_controles_mensuales", {"equipo_filtrar": "Halcyon"})
    assert filas[0] == (53, "24/01/2029")
    assert consulta(real, "SELECT fecha FROM controles WHERE id = 53") == [("24/01/2029",)]


# ====================================================================================================== 4. una sola definición y el empaquetado

FUENTES = {"data/ManejoDatos/load.py": [l[2] for l in LISTAS[:8]], "data/ManejoDatos/Tablas_Anuales/tablas_anuales.py": ["mostrar_controles_anuales"]}


def _arbol(rel):
    return ast.parse((RAIZ / rel).read_text(encoding="utf-8"))


@pytest.mark.parametrize("rel", sorted(FUENTES))
def test_las_listas_usan_la_funcion_unica_importada_de_forma_estatica(rel):
    arbol = _arbol(rel)
    importaciones = [n for n in arbol.body if isinstance(n, ast.ImportFrom) and n.module == MODULO]
    assert [[a.name for a in n.names] for n in importaciones] == [["mas_reciente_primero"]]
    funciones = {n.name: n for n in arbol.body if isinstance(n, ast.FunctionDef)}
    for nombre in sorted(set(FUENTES[rel])):
        llamadas = [n for n in ast.walk(funciones[nombre]) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "mas_reciente_primero"]
        assert len(llamadas) == 1, nombre
        texto = ast.get_source_segment((RAIZ / rel).read_text(encoding="utf-8"), funciones[nombre])
        assert "fecha DESC" not in texto, f"{nombre} ya no ordena por el texto de la fecha"


def test_el_modulo_no_tiene_sql_ni_interfaz():
    arbol = ast.parse((RAIZ / "services" / "orden_de_controles.py").read_text(encoding="utf-8"))
    modulos = {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names} | {n.module for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)}
    assert modulos == {"re", "datetime"}


def test_el_modulo_esta_una_vez_en_hidden_imports_despues_del_colimador():
    arbol = ast.parse((RAIZ / "build_exe.py").read_bytes().decode("utf-8"))
    lista = next(n.value for n in arbol.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "hidden_imports" for t in n.targets))
    nombres = [e.value for e in lista.elts]
    assert nombres.count(MODULO) == 1
    assert nombres.index(MODULO) == nombres.index("ui.paginasControles.PruebasMensuales.filas_por_nivel") + 1


def test_build_exe_sigue_en_crlf():
    crudo = (RAIZ / "build_exe.py").read_bytes()
    assert b"\r\n" in crudo and b"\n" not in crudo.replace(b"\r\n", b""), "build_exe.py sigue en CRLF"
