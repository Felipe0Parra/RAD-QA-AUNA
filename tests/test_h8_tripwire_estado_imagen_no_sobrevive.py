"""H8 (PLAN_BRAQUI_DIARIO_HORA_IMAGEN_28-08.md, Fase 4 -- "que no vuelva a
pasar") -- REESCRITO por `I5` (PLAN_BRAQUI_IMAGEN_Y_PERFIL_02-09.md, Fase C).

Causa de la reescritura, medida: `ATRIBUTOS_ESTADO_IMAGEN` declaraba
`["archivo", "imagen_path"]` -- las DOS piezas que `H1` acababa de arreglar
en ese mismo commit. Un censo copiado del arreglo solo puede confirmar el
arreglo; nunca encuentra lo que el arreglo omitió -- y así fue: `subir_imagen`
también asigna `pixmap_original`/`zoom_factor`, y `_cargar_imagen_pelicula`
asigna `parametros_creados`, sin que este tripwire lo notara durante DOS
rebuilds (`DP-79`).

La lista `ATRIBUTOS_ESTADO_IMAGEN` ya NO se escribe a mano: se DERIVA por
AST de lo que `subir_imagen` (`PruebasDiarias.py`), `_cargar_imagen_pelicula`
y `mostrar_texto` (`braquiterapia.py::PruebaDiariaBraq`) asignan de verdad.
Si mañana alguien agrega un `self.lo_que_sea` nuevo en cualquiera de esas
tres funciones, aparece aquí solo -- y si `resetear_imagen_ui` no lo
menciona ni está en la lista blanca (`SITIOS_NO_ESTADO_DE_IMAGEN`, con su
motivo escrito), la suite se pone roja señalándolo por nombre.

Dos frentes, complementarios (el AST no ve efectos):
  - ESTRUCTURAL (este archivo): ¿toda pieza asignada está cubierta o
    justificada?
  - DINÁMICO (este archivo + `test_i3_estado_imagen_completo.py`): ¿de
    verdad desaparece tras un cambio de día real, con ida y vuelta a la BD?
"""
import ast
import io
import os
import pathlib

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq

FECHA_FUENTE = "2026-01-01 00:00:00"

RAIZ = pathlib.Path(__file__).resolve().parent.parent
RUTA_PRUEBAS_DIARIAS = RAIZ / "ui" / "paginasControles" / "PruebasDiarias" / "PruebasDiarias.py"
RUTA_BRAQUITERAPIA = RAIZ / "ui" / "paginasControles" / "PruebasDiarias" / "braquiterapia.py"

# I5: las funciones que ENSUCIAN estado de imagen -- el censo se deriva de
# ellas, nunca de resetear_imagen_ui (eso sería copiar el arreglo otra vez).
FUENTES_DE_ESTADO_DE_IMAGEN = [
    (RUTA_PRUEBAS_DIARIAS, "subir_imagen", None),
    (RUTA_BRAQUITERAPIA, "_cargar_imagen_pelicula", "PruebaDiariaBraq"),
    (RUTA_BRAQUITERAPIA, "mostrar_texto", "PruebaDiariaBraq"),
]

# I5: nombres que el censo SÍ encuentra pero que NO son "estado de imagen
# del día" -- cada uno con su motivo, para que la excepción se decida leyendo,
# no por descarte silencioso.
SITIOS_NO_ESTADO_DE_IMAGEN = {
    "zoomConnected": (
        "flag de conexión de la señal de la rueda del zoom -- no es "
        "estado de imagen, es un guardia de 'ya conectado'. Reconectarla "
        "en cada limpieza duplicaría el handler de scroll."),
    "toolbar": (
        "chrome de UI ligado al canvas, no al día -- mostrar_texto lo "
        "crea UNA sola vez a propósito ('Elimina todo menos canvas y "
        "toolbar') y lo preserva entre controles; resetearlo lo "
        "destruiría y recrearía sin necesidad en cada cambio de día."),
}


def _nombres_asignados_en(ruta, nombre_funcion, nombre_clase=None):
    """Todo `self.<algo> = ...` (o `+=`) dentro de `nombre_funcion`, con su
    línea -- si `nombre_clase` se da, restringe la búsqueda al cuerpo de esa
    clase (dos clases del mismo archivo pueden tener un método homónimo,
    igual que `_limpiar_widgets_diaria` antes de `I0`)."""
    arbol = ast.parse(io.open(ruta, encoding="utf-8").read(), str(ruta))
    encontrados = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.ClassDef):
            continue
        if nombre_clase is not None and nodo.name != nombre_clase:
            continue
        for miembro in nodo.body:
            if not (isinstance(miembro, ast.FunctionDef)
                    and miembro.name == nombre_funcion):
                continue
            for n in ast.walk(miembro):
                objetivos = []
                if isinstance(n, ast.Assign):
                    objetivos = n.targets
                elif isinstance(n, ast.AugAssign):
                    objetivos = [n.target]
                for t in objetivos:
                    if (isinstance(t, ast.Attribute)
                            and isinstance(t.value, ast.Name)
                            and t.value.id == "self"):
                        encontrados.append((t.attr, n.lineno))
    return encontrados


def _censar_estado_de_imagen():
    """El censo completo: nombre -> lista de (archivo, línea) donde se
    asigna. Un `dict` y no un `set` para que un fallo pueda señalar DÓNDE
    se originó cada pieza, no solo su nombre."""
    censo = {}
    for ruta, funcion, clase in FUENTES_DE_ESTADO_DE_IMAGEN:
        for nombre, lineno in _nombres_asignados_en(ruta, funcion, clase):
            censo.setdefault(nombre, []).append((ruta.name, lineno))
    return censo


def _resetear_imagen_ui_menciona(nombre):
    """¿El cuerpo de `PruebaDiariaBraq.resetear_imagen_ui` hace referencia
    a `self.<nombre>` -- asignación o llamada de método (`.clear()`,
    `.setParent(None)`, etc.)? Se busca por AST sobre el archivo real, no
    por introspección en runtime: así detecta también 'está pero
    comentado', que es exactamente como este defecto vivió dos rebuilds."""
    arbol = ast.parse(io.open(RUTA_BRAQUITERAPIA, encoding="utf-8").read(),
                       str(RUTA_BRAQUITERAPIA))
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.ClassDef) and nodo.name == "PruebaDiariaBraq"):
            continue
        for miembro in nodo.body:
            if not (isinstance(miembro, ast.FunctionDef)
                    and miembro.name == "resetear_imagen_ui"):
                continue
            for n in ast.walk(miembro):
                if (isinstance(n, ast.Attribute)
                        and isinstance(n.value, ast.Name)
                        and n.value.id == "self"
                        and n.attr == nombre):
                    return True
    return False


# El censo derivado, calculado UNA vez al importar -- las pruebas de abajo
# lo consumen; ninguna lo escribe a mano.
CENSO_ESTADO_IMAGEN = _censar_estado_de_imagen()
ATRIBUTOS_ESTADO_IMAGEN = sorted(
    n for n in CENSO_ESTADO_IMAGEN if n not in SITIOS_NO_ESTADO_DE_IMAGEN)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _sin_dialogos_modales(monkeypatch):
    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: None))


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


def _poblar_estado_de_imagen(d, tmp_path):
    archivo_falso = str(tmp_path / "placa.jpg")
    open(archivo_falso, "wb").close()
    d.archivo = archivo_falso
    d.imagen_path = archivo_falso
    d.figure.add_subplot(111).plot([1, 2, 3])
    d.canvas.draw()
    d.mostrar_texto(["Promedio = 10.01 mm", "Desviación estándar = 0.11 mm"])


def _esta_vacio(d, atributo):
    """Cada pieza tiene su propio valor "vacío" -- no todas vuelven a
    `None` (I3): `pixmap_original` es un `QPixmap()` nulo, `zoom_factor`
    vuelve a 1.0, `parametros_creados` a `False`. Escribir esto a mano por
    atributo es aceptable porque son solo TRES excepciones documentadas al
    contrato general "None" -- no una lista paralela de lo que hay que
    limpiar."""
    valor = getattr(d, atributo)
    if atributo == "pixmap_original":
        return valor.isNull()
    if atributo == "zoom_factor":
        return valor == 1.0
    if atributo == "parametros_creados":
        return valor is False
    if atributo == "resultado_label":
        # mostrar_texto lo asigna una vez y nunca se vuelve a poner en
        # None -- resetear_imagen_ui lo vacía con .clear() (texto), no
        # reasignando el atributo.
        return valor.text() == ""
    return valor is None


class TestI5CensoEstructuralDerivadoDelProductor:
    """Frente ESTRUCTURAL: ¿toda pieza que las funciones productoras
    asignan está cubierta por `resetear_imagen_ui` o justificada en la
    lista blanca? No ejecuta nada -- es puro AST."""

    def test_el_censo_no_esta_vacio(self):
        """Si esto queda vacío, el tripwire está inerte -- igual que el
        `ATRIBUTOS_ESTADO_IMAGEN` hardcodeado que este archivo reemplaza."""
        assert CENSO_ESTADO_IMAGEN, (
            "el censo derivado no encontró NINGUNA asignación -- revisar "
            "si subir_imagen/_cargar_imagen_pelicula/mostrar_texto se "
            "renombraron o movieron de archivo/clase")

    def test_el_censo_encuentra_las_piezas_que_motivaron_I3(self):
        """Prueba de que la derivación es real y no un placebo: tiene que
        encontrar EXACTAMENTE las piezas que `I3` tuvo que agregar a
        `resetear_imagen_ui` (si no las encuentra, la derivación está mal
        hecha, no es que ya no haga falta cubrirlas)."""
        esperadas = {"pixmap_original", "zoom_factor", "parametros_creados"}
        assert esperadas <= set(CENSO_ESTADO_IMAGEN), (
            f"el censo no encontró {esperadas - set(CENSO_ESTADO_IMAGEN)} -- "
            f"la derivación por AST no está viendo lo que de verdad asignan "
            f"subir_imagen/_cargar_imagen_pelicula")

    def test_toda_pieza_censada_esta_cubierta_o_en_lista_blanca(self):
        sin_cubrir = []
        for nombre, sitios in CENSO_ESTADO_IMAGEN.items():
            if nombre in SITIOS_NO_ESTADO_DE_IMAGEN:
                continue
            if not _resetear_imagen_ui_menciona(nombre):
                sin_cubrir.append((nombre, sitios))
        assert not sin_cubrir, (
            "Pieza de estado de imagen que subir_imagen/_cargar_imagen_"
            "pelicula/mostrar_texto asignan y resetear_imagen_ui NUNCA "
            "menciona -- ni la repone ni está en SITIOS_NO_ESTADO_DE_"
            f"IMAGEN con su motivo: {sin_cubrir}")

    def test_la_lista_blanca_no_tiene_entradas_sobrantes(self):
        """Si una entrada de la lista blanca deja de aparecer en el censo
        (la función que la asignaba cambió o se borró), limpiarla -- una
        lista blanca con sitios fantasma es tan mala señal como un sitio
        sin cubrir."""
        sobrantes = set(SITIOS_NO_ESTADO_DE_IMAGEN) - set(CENSO_ESTADO_IMAGEN)
        assert not sobrantes, (
            f"{sobrantes} ya no aparecen en el censo -- limpiar "
            f"SITIOS_NO_ESTADO_DE_IMAGEN")


class TestH8NingunEstadoDeImagenSobreviveARotarDeDia:
    """Frente DINÁMICO: construir la pantalla real, ensuciar TODO lo que
    el censo derivado encontró, rotar de día de verdad (con ida y vuelta a
    la BD), y exigir que cada pieza quede en su valor vacío."""

    def test_censo_completo_queda_limpio_al_rotar_a_dia_sin_registro(
            self, app, bd_temporal, tmp_path):
        d = PruebaDiariaBraq(_UsuarioFalso())
        _poblar_estado_de_imagen(d, tmp_path)
        assert d.guardar_datos() != ("", None, None, "", None, None), (
            "precondición: debe haber algo real que perder")

        d.date_box.setDate(QDate(2026, 9, 9))  # día sin registro

        for atributo in ATRIBUTOS_ESTADO_IMAGEN:
            assert _esta_vacio(d, atributo), (
                f"{atributo!r} sobrevivió a un cambio de día -- estado de "
                f"UI que se guarda y nadie limpia, la clase de defecto de "
                f"todo este plan")
        assert d.resultado_label.text() == "", (
            "resultado_label sobrevivió a un cambio de día")
        assert d.figure.axes == [], (
            "la figura del canvas sobrevivió a un cambio de día")
        assert d.guardar_datos() == ("", None, None, "", None, None), (
            "intuición de garantía de H8: guardar_datos() inmediatamente "
            "después de rotar de día no puede devolver nada del día "
            "anterior, sea cual sea la variable")

    def test_censo_completo_queda_limpio_al_rotar_a_dia_con_registro_sin_imagen(
            self, app, bd_temporal, tmp_path):
        """La otra rama (H2): un día CON registro pero SIN película -- el
        caso exacto que produjo la fila 447 del handoff."""
        conexion = Conexion()
        conexion.con.execute(
            "INSERT INTO braqui (date, user_id, int_con_box, emerg_con, "
            "blq_puerta, pos_fuente, res_fuente, key_fuente, mon_area, "
            "lum_puerta, tub_guia, visual_sys, intercom, mon_rad_port, "
            "tol_rep_act_ci, tol_exp_act, tol_cyc_dummy, tol_cyc_rad, "
            "observaciones, pelicula, activo) VALUES "
            "('2026-09-10', 'Físico de Prueba', 1,1,1,1,1,1,1,1,1,1,1,1, "
            "1.0,1.0,1.0,1.0, '', NULL, 1)")
        conexion.con.commit()

        d = PruebaDiariaBraq(_UsuarioFalso())
        _poblar_estado_de_imagen(d, tmp_path)

        d.date_box.setDate(QDate(2026, 9, 10))  # registro real, sin imagen

        for atributo in ATRIBUTOS_ESTADO_IMAGEN:
            assert _esta_vacio(d, atributo), (
                f"{atributo!r} sobrevivió a un día con registro pero sin "
                f"imagen -- exactamente la fila 447 del handoff")
        assert d.resultado_label.text() == ""
        assert d.figure.axes == []
