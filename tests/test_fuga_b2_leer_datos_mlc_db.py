"""B2 (PLAN_FUGA_CONEXIONES_01-09.md §2.3/§4): `models/PDF/pdf.py::
_leer_datos_mlc_db` -- RIESGO BAJO, de solo lectura (5 SELECT sobre 4
tablas): nunca cierra `conn`. [medido, §1.3] 3 descriptores por llamada,
no bloquea a nadie.

P2: `filtro_activo` (importado por nombre en el módulo) se sustituye por
una versión que revienta SOLO para `highest_leaf_errors` -- la ÚLTIMA de
las 5 consultas, para que el fallo ocurra bien entrado el `with`, con las
otras 4 ya ejecutadas."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion, _ConexionUnaVez
from services.anulacion import filtro_activo as _filtro_activo_real
import models.PDF.pdf as pdf_mod
from models.PDF.pdf import _leer_datos_mlc_db


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture(autouse=True)
def _sin_conversion_dicom(monkeypatch):
    """La conversión DICOM->PNG real no es lo que este test verifica --
    se hace passthrough para no depender de un archivo DICOM sintético."""
    monkeypatch.setattr(pdf_mod, "dicom_to_png_blob", lambda blob: blob)


def _insertar_control(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(
        "INSERT INTO controles (equipo, control, fecha) VALUES (?, ?, ?)",
        ("Clinac ix", "Mensual", "06/2026"))
    con.commit()
    ref = cur.lastrowid
    con.close()
    return ref


def _insertar_configuracion(ruta_bd, ref):
    con = sqlite3.connect(ruta_bd)
    con.execute(
        "INSERT INTO configuracion_picketfence (ref, fecha, equipo, "
        "fisico_1, fisico_2, tolerancia, action_tolerance, imagen_mlc) "
        "VALUES (?, '01/06/2026', 'Clinac ix', 'Físico 1', NULL, 1.0, 2.0, NULL)",
        (ref,))
    con.commit()
    con.close()


class _ConexionUnaVezEspia(_ConexionUnaVez):
    llamadas = []

    def __exit__(self, exc_type, exc, tb):
        _ConexionUnaVezEspia.llamadas.append("exit")
        return super().__exit__(exc_type, exc, tb)


class TestB2LeerDatosMlcDbCierraSiempre:
    def test_ultimo_select_revienta_y_aun_asi_se_invoca_exit(
            self, bd_temporal, monkeypatch):
        monkeypatch.setattr(conection_mod, "_ConexionUnaVez", _ConexionUnaVezEspia)
        _ConexionUnaVezEspia.llamadas.clear()
        ref = _insertar_control(bd_temporal)
        _insertar_configuracion(bd_temporal, ref)

        def _filtro_que_revienta_al_final(tabla):
            if tabla == "highest_leaf_errors":
                raise RuntimeError("fallo inyectado por el test")
            return _filtro_activo_real(tabla)

        monkeypatch.setattr(pdf_mod, "filtro_activo", _filtro_que_revienta_al_final)

        with pytest.raises(RuntimeError, match="fallo inyectado"):
            _leer_datos_mlc_db(ref)

        assert _ConexionUnaVezEspia.llamadas == ["exit"], (
            "el with debe invocar __exit__ exactamente una vez, incluso "
            f"cuando la última consulta revienta -- se registró: {_ConexionUnaVezEspia.llamadas}")

    def test_camino_normal_sigue_leyendo_igual(self, bd_temporal):
        ref = _insertar_control(bd_temporal)
        _insertar_configuracion(bd_temporal, ref)

        datos = _leer_datos_mlc_db(ref)

        assert datos["equipo"] == "Clinac ix"
        assert datos["fisico_1"] == "Físico 1"
        assert datos["picket_rows"] == []
        assert datos["leaf_rows"] == []
        assert datos["worst_rows"] == []
