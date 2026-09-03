"""I2 (PLAN_BRAQUI_IMAGEN_Y_PERFIL_02-09.md, Fase A): `_restablecer_formulario_
diario()` es la ÚNICA definición de "formulario diario en blanco". El botón
"Limpiar" (`clean_info`) y el cambio de día a una fecha sin registro
(`cargar_dailytest_desde_db`, rama `else`) delegan los dos en ella -- antes
llamaban a dos pilas independientes que discrepaban en 4 puntos [medido, ver
el plan §0]: el modo "fuera de servicio", el color de los botones Funciona/
No funciona, `botones_ordenados`, y el botón "Añadir".

Pedido literal del físico: *"garantizar el buen funcionamiento del botón de
limpiar, que realmente limpie todas las funciones, y replicar el
funcionamiento para cuando se cambie de día"*. Este archivo no compara cada
camino contra una lista escrita a mano -- COMPARA LOS DOS CAMINOS ENTRE SÍ
(la instantánea del formulario tras "Limpiar" contra la instantánea tras
rotar a un día vacío) y exige que sean iguales salvo la única diferencia
LEGÍTIMA: los campos derivados (`CAMPOS_DERIVADOS_DIARIA`, solo en braqui)
se recalculan al rotar de día y quedan vacíos tras "Limpiar".

Antes de `I2` este archivo habría fallado en las 4 discrepancias -- no se
dejó un commit intermedio para demostrarlo en rojo (habría significado
commitear un estado a medias), pero la comparación por INSTANTÁNEA, no por
lista, es la garantía que impide que las dos pilas vuelvan a divergir en el
futuro sin que la suite lo note (corolario de arquitectura #3 de la sesión).
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QMessageBox

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from ui.paginasControles.PruebasDiarias.braquiterapia import PruebaDiariaBraq
from ui.paginasControles.PruebasDiarias.seiscientos import PruebaDiaria600
from ui.paginasControles.PruebasDiarias.IX import PruebaDiariaIX

FECHA_FUENTE = "2020-01-01 00:00:00"
FECHA_SIN_REGISTRO = QDate(2027, 6, 15)


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
    # Solo braqui la necesita (CAMPOS_DERIVADOS_DIARIA -> actividad_braq_
    # automatica), pero insertarla siempre es inocuo para iX/600.
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


def _ensuciar(d):
    """Deja el formulario en un estado que SOLO una limpieza completa puede
    revertir: un botón marcado, "fuera de servicio" activo con texto
    propio, algo en `botones_ordenados`, y un campo de texto lleno."""
    primer_fun = getattr(d, list(d.df_bnt_funciona)[0])
    primer_nofun = getattr(d, list(d.df_bnt_nofunciona)[0])
    primer_fun.setChecked(True)
    d.cambiar_estilo(primer_fun, primer_nofun)

    d.fueradeservicio = True
    d._texto_original_btn_add = "Agregar"
    d.btn_add.setText("FUERA DE SERVICIO")

    if getattr(d, "botones_ordenados", None) is not None:
        d.botones_ordenados.append(("x", "y"))

    if d.df_lines:
        getattr(d, list(d.df_lines)[0]).setText("9.9")
    if hasattr(d, "observaciones"):
        d.observaciones.setText("algo escrito ayer")


def _instantanea(d):
    primer_fun = getattr(d, list(d.df_bnt_funciona)[0])
    primer_nofun = getattr(d, list(d.df_bnt_nofunciona)[0])
    return {
        "fueradeservicio": d.fueradeservicio,
        "btn_add_texto": d.btn_add.text(),
        "btn_add_habilitado": d.btn_add.isEnabled(),
        "btn_add_estado": d.btn_add.property("estado"),
        "primer_fun_checked": primer_fun.isChecked(),
        "primer_fun_estado": primer_fun.property("estado"),
        "primer_nofun_checked": primer_nofun.isChecked(),
        "primer_nofun_estado": primer_nofun.property("estado"),
        "botones_ordenados": list(getattr(d, "botones_ordenados", []) or []),
        "botones_finales": set(d.botones_finales),
        "df_lines": {nombre: getattr(d, nombre).text() for nombre in d.df_lines},
        "observaciones": d.observaciones.text() if hasattr(d, "observaciones") else None,
    }


CASOS = [
    (PruebaDiariaBraq, True),
    (PruebaDiaria600, False),
    (PruebaDiariaIX, False),
]


@pytest.mark.parametrize("clase,imagenes", CASOS)
class TestLimpiarYRotarDejanElMismoEstado:

    def test_limpiar_y_rotar_a_dia_vacio_convergen(
            self, app, bd_temporal, clase, imagenes):
        d_boton = clase(_UsuarioFalso())
        _ensuciar(d_boton)
        d_boton.clean_info(imagenes=imagenes)
        snap_boton = _instantanea(d_boton)

        d_rotar = clase(_UsuarioFalso())
        _ensuciar(d_rotar)
        d_rotar.cargar_dailytest_desde_db(FECHA_SIN_REGISTRO)
        snap_rotar = _instantanea(d_rotar)

        campos_derivados = set(getattr(clase, "CAMPOS_DERIVADOS_DIARIA", {}))

        for clave in snap_boton:
            if clave == "df_lines":
                for nombre, valor_boton in snap_boton["df_lines"].items():
                    valor_rotar = snap_rotar["df_lines"][nombre]
                    if nombre in campos_derivados:
                        continue  # única diferencia legítima -- ver el otro test
                    assert valor_boton == valor_rotar, (
                        f"{clase.__name__}.{nombre}: 'Limpiar' dejó "
                        f"{valor_boton!r}, rotar de día dejó {valor_rotar!r} "
                        f"-- los dos caminos deben limpiar exactamente igual")
                continue
            assert snap_boton[clave] == snap_rotar[clave], (
                f"{clase.__name__}: '{clave}' difiere entre 'Limpiar' "
                f"({snap_boton[clave]!r}) y rotar a un día sin registro "
                f"({snap_rotar[clave]!r}) -- los dos caminos deben dejar "
                f"EXACTAMENTE el mismo estado")

    def test_campo_derivado_solo_se_recalcula_al_rotar_no_al_limpiar(
            self, app, bd_temporal, clase, imagenes):
        campos_derivados = getattr(clase, "CAMPOS_DERIVADOS_DIARIA", {})
        if not campos_derivados:
            pytest.skip(f"{clase.__name__} no declara CAMPOS_DERIVADOS_DIARIA")

        d_boton = clase(_UsuarioFalso())
        _ensuciar(d_boton)
        d_boton.clean_info(imagenes=imagenes)

        d_rotar = clase(_UsuarioFalso())
        _ensuciar(d_rotar)
        d_rotar.cargar_dailytest_desde_db(FECHA_SIN_REGISTRO)

        for campo in campos_derivados:
            texto_boton = getattr(d_boton, campo).text()
            texto_rotar = getattr(d_rotar, campo).text()
            assert texto_boton == "", (
                f"{clase.__name__}.{campo}: 'Limpiar' NO debe recalcular "
                f"campos derivados -- quedó {texto_boton!r}")
            assert texto_rotar != "", (
                f"{clase.__name__}.{campo}: rotar a un día sin registro "
                f"SÍ debe recalcularlo -- quedó vacío")
