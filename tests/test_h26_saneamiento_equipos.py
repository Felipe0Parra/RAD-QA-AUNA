"""H2.6 (auditoría 2026-07-16) -- script de saneamiento del catálogo
`equipos`, verificado sobre una BD temporal (nunca la de producción real).

Ver el docstring de scripts/saneamiento_equipos_h26.py para el origen de
cada cambio (certificados de calibración reales + confirmación del físico).
Estos tests solo verifican el COMPORTAMIENTO del script (aplica lo correcto,
es idempotente, no sobrescribe filas que hayan derivado) -- la aplicación a
la BD de producción real es un paso manual aparte, documentado en CLAUDE.md.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion

from scripts.saneamiento_equipos_h26 import CAMBIOS, aplicar_saneamiento


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
    con = sqlite3.connect(ruta_bd)
    cols = ["id"] + list(campos)
    marcas = ", ".join("?" * len(cols))
    con.execute(f"INSERT INTO equipos ({', '.join(cols)}) VALUES ({marcas})",
                [eq_id] + list(campos.values()))
    con.commit()
    con.close()


def _leer_equipo(ruta_bd, eq_id, *columnas):
    con = sqlite3.connect(ruta_bd)
    cur = con.execute(f"SELECT {','.join(columnas)} FROM equipos WHERE id=?",
                       (eq_id,))
    fila = cur.fetchone()
    con.close()
    return dict(zip(columnas, fila)) if fila else None


def _audit_log_filas(ruta_bd):
    con = sqlite3.connect(ruta_bd)
    con.execute("CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY)")
    cur = con.execute("SELECT COUNT(*) FROM audit_log WHERE accion='saneamiento_h26'")
    n = cur.fetchone()[0]
    con.close()
    return n


class TestRenombrarTNaN:
    def test_unifica_modelo_y_marca_historico(self, bd_temporal):
        _insertar_equipo(bd_temporal, 26, equip_type="Cámara de ionización",
                         model="TN34001", serie="001069", calibr_fact=0.08563,
                         fecha_calibr="9/08/2022", activo=1, vigente=None)

        r = aplicar_saneamiento(bd_temporal, usuario="test")

        fila = _leer_equipo(bd_temporal, 26, "model", "serie", "fecha_calibr",
                             "activo", "vigente")
        assert fila == {"model": "N34001", "serie": "1069",
                        "fecha_calibr": "09/08/2022", "activo": 0, "vigente": 0}
        assert any(c["id"] == 26 for c in r["aplicados"])
        assert _audit_log_filas(bd_temporal) >= 1


class TestCorreccionTCalPCal:
    def test_corrige_condiciones_ambientales_a_referencia(self, bd_temporal):
        _insertar_equipo(bd_temporal, 13, equip_type="Cámara de ionización",
                         model="N30013", serie="2123", calibr_fact=0.05451,
                         t_cal=20.9, p_cal=98.91, activo=1, vigente=1)

        aplicar_saneamiento(bd_temporal, usuario="test")

        fila = _leer_equipo(bd_temporal, 13, "t_cal", "p_cal", "activo", "vigente")
        assert fila["t_cal"] == 22.0
        assert fila["p_cal"] == 101.325
        # la fila sigue vigente/activa -- el fix es de valor, no de estado
        assert fila["activo"] == 1
        assert fila["vigente"] == 1


class TestCorreccionEscalaPozo:
    def test_corrige_coeficiente_de_calibracion(self, bd_temporal):
        _insertar_equipo(bd_temporal, 16, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A972662",
                         calibr_fact=46670, activo=1, vigente=1)

        aplicar_saneamiento(bd_temporal, usuario="test")

        fila = _leer_equipo(bd_temporal, 16, "calibr_fact")
        assert fila["calibr_fact"] == 466700


class TestRetiroYDeduplicacion:
    def test_pozo_somer_queda_inactivo(self, bd_temporal):
        _insertar_equipo(bd_temporal, 56, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A132690 Somer",
                         calibr_fact=467900, p_cal=760, activo=1, vigente=1)

        aplicar_saneamiento(bd_temporal, usuario="test")

        fila = _leer_equipo(bd_temporal, 56, "activo", "vigente")
        assert fila == {"activo": 0, "vigente": 0}

    def test_duplicado_exacto_queda_historico(self, bd_temporal):
        _insertar_equipo(bd_temporal, 59, equip_type="Cámara de ionización",
                         model="N31022", serie="152342", calibr_fact=2.673,
                         activo=1, vigente=1)

        aplicar_saneamiento(bd_temporal, usuario="test")

        fila = _leer_equipo(bd_temporal, 59, "activo", "vigente")
        assert fila == {"activo": 0, "vigente": 0}


class TestCorreccionTCalPCalPozo:
    """H2.10: mismo bug que TestCorreccionTCalPCal (N30013/N31014) pero en
    el pozo A972662 -- se encontró al investigar por qué desapareció del
    selector de braquiterapia tras el saneamiento H2.6."""
    def test_corrige_condiciones_ambientales_a_referencia(self, bd_temporal):
        _insertar_equipo(bd_temporal, 16, equip_type="Cámara de pozo",
                         model="HDR1000 Plus", serie="A972662",
                         calibr_fact=466700, t_cal=21.4, p_cal=98.52,
                         activo=1, vigente=1)

        aplicar_saneamiento(bd_temporal, usuario="test")

        fila = _leer_equipo(bd_temporal, 16, "t_cal", "p_cal", "activo", "vigente")
        assert fila["t_cal"] == 22.0
        assert fila["p_cal"] == 101.325
        # la fila sigue vigente/activa -- el fix es de valor, no de estado
        assert fila["activo"] == 1
        assert fila["vigente"] == 1


class TestDobleVigenteElectrometro:
    """H2.10: el electrómetro CDX-2000B/B091982 tenía dos filas vigentes a
    la vez (id18 de 2024 e id79, la recalibración 2026) -- una sola vigente
    por serie."""
    def test_fila_vieja_queda_historica(self, bd_temporal):
        _insertar_equipo(bd_temporal, 18, equip_type="Electrómetro",
                         model="CDX-2000B", serie="B091982", calibr_fact=1,
                         fecha_calibr="05/02/2024", activo=1, vigente=1)

        aplicar_saneamiento(bd_temporal, usuario="test")

        fila = _leer_equipo(bd_temporal, 18, "vigente", "activo")
        assert fila["vigente"] == 0
        # activo no cambia -- el equipo sigue existiendo, solo deja de ser
        # "la" calibración vigente (la 2026 lo es)
        assert fila["activo"] == 1


class TestIdempotencia:
    def test_segunda_corrida_no_cambia_nada(self, bd_temporal):
        _insertar_equipo(bd_temporal, 13, equip_type="Cámara de ionización",
                         model="N30013", serie="2123", calibr_fact=0.05451,
                         t_cal=20.9, p_cal=98.91, activo=1, vigente=1)

        r1 = aplicar_saneamiento(bd_temporal, usuario="test")
        assert any(c["id"] == 13 for c in r1["aplicados"])
        n_audit_tras_primera = _audit_log_filas(bd_temporal)

        r2 = aplicar_saneamiento(bd_temporal, usuario="test")

        assert not any(c["id"] == 13 for c in r2["aplicados"])
        assert any(c["id"] == 13 for c in r2["ya_aplicados"])
        assert _audit_log_filas(bd_temporal) == n_audit_tras_primera


class TestDeriva:
    def test_fila_que_no_coincide_ni_antes_ni_despues_no_se_toca(self, bd_temporal):
        # id 13 esperaba t_cal=20.9/p_cal=98.91 (antes) o 22/101.325
        # (después) -- un tercer valor significa que la fila cambió por otra
        # vía desde el análisis: no se debe sobrescribir a ciegas.
        _insertar_equipo(bd_temporal, 13, equip_type="Cámara de ionización",
                         model="N30013", serie="2123", calibr_fact=0.05451,
                         t_cal=21.5, p_cal=99.50, activo=1, vigente=1)

        r = aplicar_saneamiento(bd_temporal, usuario="test")

        fila = _leer_equipo(bd_temporal, 13, "t_cal", "p_cal")
        assert fila == {"t_cal": 21.5, "p_cal": 99.50}
        assert any(c["id"] == 13 for c in r["con_deriva"])
        assert _audit_log_filas(bd_temporal) == 0


class TestDryRun:
    def test_dry_run_no_escribe_en_la_bd(self, bd_temporal):
        _insertar_equipo(bd_temporal, 13, equip_type="Cámara de ionización",
                         model="N30013", serie="2123", calibr_fact=0.05451,
                         t_cal=20.9, p_cal=98.91, activo=1, vigente=1)

        r = aplicar_saneamiento(bd_temporal, usuario="test", dry_run=True)

        fila = _leer_equipo(bd_temporal, 13, "t_cal", "p_cal")
        assert fila == {"t_cal": 20.9, "p_cal": 98.91}
        assert any(c["id"] == 13 for c in r["aplicados"])
        assert _audit_log_filas(bd_temporal) == 0


class TestFilaInexistente:
    def test_id_ausente_no_revienta(self, bd_temporal):
        # BD vacía de equipos -- ningún id de CAMBIOS existe.
        r = aplicar_saneamiento(bd_temporal, usuario="test")

        assert r["aplicados"] == []
        assert r["ya_aplicados"] == []
        assert r["con_deriva"] == []


def test_todos_los_cambios_tienen_antes_y_despues_sobre_las_mismas_columnas():
    # Invariante que aplicar_saneamiento asume: la deteccion de deriva
    # compara "antes" contra las columnas leidas (= claves de "despues");
    # si "antes" trajera una columna ausente en "despues" la comparacion
    # quedaria mal formada (dict.get devolveria None en vez del valor real).
    for cambio in CAMBIOS:
        assert set(cambio["antes"]) == set(cambio["despues"])
        assert cambio["antes"] != cambio["despues"]
        assert cambio["motivo"]
