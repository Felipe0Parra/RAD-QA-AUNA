"""PI.3 (PLAN_POSICION_INICIAL_BRAQUI_01-10.md): el servicio de la posición inicial de braquiterapia -- la ÚNICA puerta a la
tabla `braqui_posicion_inicial` y la única regla de vigencia (qué prueba vale en una fecha), más el texto breve que
imprimen la tabla de registros y los dos PDF.

Lo que se garantiza, cada cosa con su prueba (ver el docstring de `services/posicion_inicial_braqui.py` para el porqué):
  - `guardar` ANALIZA él mismo desde los bytes y los puntos y guarda lo que da `valores_medidos` (px y mm sin recalcular);
    rechaza SIN escribir nada lo que no es válido; reguardar la misma fecha exige `reemplazar=True`; una sola transacción
    con una sola fila de auditoría (`guardar` o `reemplazo`); si el INSERT falla no queda nada a medias.
  - `anular` va por identidad, deja `activo = 0` y una fila de auditoría en la misma transacción.
  - La regla de vigencia, con los casos del plan (§0.2) sobre una siembra que imita la BD real (fechas con hora, una
    calibración redundante el mismo día del cambio de fuente, una fila de tipo vacío y otra serie, un cambio de fuente de
    fecha ilegible): el cambio de fuente vigente más reciente con fecha <= D y, de ese, su prueba; nunca "la prueba más
    reciente <= D". DD8 (la serie del mensual), DD7 (el cambio por defecto a <= 7 días) y las dos limitaciones medidas
    por Opus (cambio de fuente anulado sin reguardar; el día del cambio).
  - El texto breve sale de lo GUARDADO (`guardar` -> BD -> `listar`/`posicion_inicial_para`), en los seis casos del plan
    con el texto exacto, y con el desfase FÍSICO cuando se conoce el lado del tránsito: la misma película escaneada
    girada 180 grados dice lo mismo (con el desfase de la imagen saldría con el signo contrario: V4 dentro de un PDF).
  - Una sola definición: `motor.interpretar` es la única que dice "antes/después de la marca", "Cumple/No cumple" y el
    aviso de la resolución; el servicio solo da formato (AST).

Ninguna prueba compara el servicio consigo mismo: los números salen de los valores de control de PI.1 (placa real
braqui_00, EPSON009) y las pruebas de regla no pasan por el análisis (siembran las filas con SQL).

Compuertas de no vacuidad (Trampa 8): cada tabla de casos declara cuántos corrió; la siembra afirma que tiene lo que dice
tener (cambios de fuente legibles, el ilegible, el anulado) antes de afirmar lo que la regla hace con ellos.
Todo contra una BD temporal copiada de una plantilla: nunca se abre una BD de referencia."""
import ast
import hashlib
import inspect
import io
import json
import os
import re
import shutil
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import pytest
from PIL import Image

import data.ManejoDatos.conection as conection_mod
from analisisImagenes import posicion_inicial_braqui as motor
from data.ManejoDatos.conection import Conexion
from scripts.indices_bloque_qc import crear_indices, nombre_indice
from services import posicion_inicial_braqui as svc
from test_pi1_motor_posicion_inicial import (CLICS_EPSON009, CLICS_PLACA_REAL, CONTROL_EPSON009, CONTROL_G1_MM,
                                             CONTROL_G1_PX, CONTROL_G1_U_MM, HOJA_ALTO, HOJA_ANCHO, MD5_PLACA_REAL,
                                             _clics_en_la_hoja, _hoja_incrustada)

TABLA = "braqui_posicion_inicial"
RAIZ = Path(__file__).resolve().parent.parent
DATOS = Path(__file__).resolve().parent / "datos"
BRAQUI_00 = (DATOS / "braqui_00.jpeg").read_bytes()
EPSON009 = (DATOS / "EPSON009.jpeg").read_bytes()
TAM = 25.4 / 600.0
USUARIO = "Fisico de prueba"
SERIE_A = "24-05-0001-A"
SERIE_B = "24-05-0002-B"
S1, S2 = "2026-01-10", "2026-04-15"          # los dos cambios de fuente de la siembra (con hora en la BD, como la real)


# ---------------------------------------------------------------------------------------------------- BD y siembra

@pytest.fixture(scope="module")
def plantilla(tmp_path_factory):
    """La BD nueva con todo el esquema y los índices únicos, hecha UNA vez; cada prueba trabaja sobre su copia."""
    ruta = str(tmp_path_factory.mktemp("pi3") / "plantilla.db")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = None
        try:
            Conexion().con.close()
            Conexion._instance = None
            assert crear_indices(ruta)[TABLA] == "creado"
        finally:
            Conexion._instance = previo
    return ruta


@pytest.fixture
def bd(plantilla, monkeypatch, tmp_path):
    """Copia de la plantilla y un `Conexion` sin arranque (el esquema ya está): `conectar()` es el real."""
    ruta = str(tmp_path / "pi3.db")
    shutil.copy(plantilla, ruta)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    previo = Conexion._instance
    Conexion._instance = object.__new__(Conexion)
    yield ruta
    Conexion._instance = previo


def _sql(ruta, sql, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        cursor = con.execute(sql, parametros)
        con.commit()
        return cursor.lastrowid
    finally:
        con.close()


def _consulta(ruta, sql, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(sql, parametros).fetchall()
    finally:
        con.close()


def _calibracion(ruta, fecha, tipo, serie, activo=1):
    return _sql(ruta, "INSERT INTO TipoCalibracion (user, fecha, tipo, serie, activo) VALUES ('Siembra', ?, ?, ?, ?)",
                (fecha, tipo, serie, activo))


def _sembrar(ruta):
    """Lo que tiene la BD real (§0.2 del plan), con las horas que tiene: dos cambios de fuente legibles, una calibración
    redundante el mismo día del primero, controles mensuales de las dos series, una fila de tipo vacío con otra serie, un
    cambio de fuente con la fecha ilegible y otro ANULADO. Devuelve los ids por nombre."""
    ids = {
        "s1": _calibracion(ruta, f"{S1} 15:03:03", "Cambio de fuente", SERIE_A),
        "redundante": _calibracion(ruta, f"{S1} 15:20:00", "Calibración Redundante", SERIE_A),
        "mensual_a": _calibracion(ruta, "2026-02-20 10:00:00", "Control Mensual", SERIE_A),
        "vacio": _calibracion(ruta, "2026-03-01 08:00:00", "", "OTRA-SERIE"),
        "s2": _calibracion(ruta, f"{S2} 09:30:00", "Cambio de fuente", SERIE_B),
        "mensual_b": _calibracion(ruta, "2026-05-20 10:00:00", "Control Mensual", SERIE_B),
        "ilegible": _calibracion(ruta, "27-09-2025", "Cambio de fuente", SERIE_A),
        "anulado": _calibracion(ruta, "2026-06-26 11:42:13", "Cambio de fuente", "24-05-0003-C", activo=0),
    }
    assert [f for f, _ in svc.cambios_de_fuente()] == [S2, S1], "la siembra no tiene lo que dice tener"
    return ids


def _sembrar_prueba(ruta, fecha, serie=SERIE_A, activo=1):
    """Una prueba SIN pasar por el análisis (las pruebas de la regla no dependen de la imagen)."""
    return _sql(ruta, "INSERT INTO braqui_posicion_inicial (fecha, serie_fuente, user, imagen, puntos, parametros, "
                      "version_algoritmo, activo) VALUES (?, ?, 'Siembra', ?, '[]', '{}', 'PI-1', ?)",
                (fecha, serie, b"x", activo))


def _auditoria(ruta):
    return _consulta(ruta, "SELECT accion, usuario, ref, detalle FROM audit_log WHERE tabla = ? ORDER BY id", (TABLA,))


def _filas(ruta):
    return _consulta(ruta, "SELECT id, fecha, activo FROM braqui_posicion_inicial ORDER BY id")


# --------------------------------------------------------------------------------------------------------- imágenes

def _png(gris):
    return cv2.imencode(".png", gris)[1].tobytes()


def _sintetica(desfase_mm):
    """(bytes, puntos) de la placa sintética del físico, sin resolución declarada y sin banda de tránsito."""
    gris, _, _, puntos = motor.placa_sintetica(desfase_mm, 2.2, 1.1, 0.5)
    return _png(gris), puntos


def _hoja(rotar):
    """La película real incrustada en la página completa del escáner; con `rotar`, girada 180 grados."""
    gris, color, _, _ = motor.leer_imagen(BRAQUI_00)
    _, hoja_color = _hoja_incrustada(gris, color)
    clics = _clics_en_la_hoja(CLICS_PLACA_REAL)
    if rotar:
        hoja_color = cv2.rotate(hoja_color, cv2.ROTATE_180)
        clics = [(HOJA_ANCHO - 1 - x, HOJA_ALTO - 1 - y) for x, y in clics]
    return _png(hoja_color), clics


def _a_300_dpi():
    """La placa real, sin pérdida, declarando 300 dpi (TIFF): una resolución 'otra'."""
    _, color, _, _ = motor.leer_imagen(BRAQUI_00)
    buffer = io.BytesIO()
    Image.fromarray(cv2.cvtColor(color, cv2.COLOR_BGR2RGB)).save(buffer, "TIFF", dpi=(300, 300))
    return buffer.getvalue()


def _guardar(fecha=S1, imagen=None, puntos=None, **extra):
    if imagen is None:
        imagen, puntos = _sintetica(-0.6)
    return svc.guardar(extra.pop("usuario", USUARIO), fecha, imagen, extra.pop("nombre", "placa.png"), puntos, **extra)


# ------------------------------------------------------------------------------------------------------ fecha_iso

class TestFechaIso:
    @pytest.mark.parametrize("valor,esperado", [
        ("2026-06-26", "2026-06-26"), ("2026-06-26 11:42:13", "2026-06-26"), ("2026-06-26T11:42", "2026-06-26"),
        ("  2026-06-26  ", "2026-06-26"), ("2026-06-26 11:42:13.250", "2026-06-26"),
        (date(2026, 6, 26), "2026-06-26"), (datetime(2026, 6, 26, 23, 59, 59), "2026-06-26")])
    def test_acepta_lo_que_es_una_fecha(self, valor, esperado):
        assert svc.fecha_iso(valor) == esperado

    @pytest.mark.parametrize("valor", [
        "20260626", "2026-W26-5", "27-09-2025", "26/06/2026", "2026-02-30", "2026-13-01", "", "   ", "hoy",
        None, 20260626, 2026.0626, b"2026-06-26", ["2026-06-26"]])
    def test_rechaza_lo_que_no_lo_es(self, valor):
        """'20260626' y '2026-W26-5' los acepta `date.fromisoformat` y el `DATE()` de SQLite los vuelve NULL: a SQL solo
        llega lo que este normalizador deja pasar."""
        assert svc.fecha_iso(valor) is None


# ---------------------------------------------------------------------------------------------------- interpretar

class TestInterpretar:
    """La función pura del motor que usan `resumen` y `texto_breve`: lo que se guarda -> lo que se muestra."""
    P = dict(motor.PARAMETROS)

    def test_un_perfil_que_no_se_midio_solo_dice_no_medible(self):
        assert motor.interpretar("no medible: x", None, None, TAM, "derecha", 600.0, self.P) == {"veredicto": "No medible"}

    def test_sin_escala_no_hay_milimetros_ni_veredicto_y_dice_por_que(self):
        r = motor.interpretar("ok", -8.55, 2.12, None, "derecha", 300.0, self.P)
        assert r == {"desfase_mm": None, "veredicto": "No medible", "aviso": (
            "la imagen declara 300 dpi y el procedimiento es de 600 dpi: parece escaneada a otra resolucion; "
            "escanee la pelicula a 600 dpi. Sin milimetros ni veredicto")}

    def test_lado_derecha_el_desfase_de_la_imagen_es_el_fisico(self):
        r = motor.interpretar("ok", -8.55, 2.12, TAM, "derecha", 600.0, self.P)
        assert r["desfase_mm"] == pytest.approx(-8.55 * TAM) and r["desfase_fisico_mm"] == r["desfase_mm"]
        assert r["sentido"] == "antes de la marca" and r["veredicto"] == "Cumple"
        assert r["U_mm"] == pytest.approx(2.12 * TAM) and r["U_px"] == 2.12

    def test_lado_izquierda_invierte_el_signo_y_el_sentido_fisico_no_cambia(self):
        a = motor.interpretar("ok", -8.55, 2.12, TAM, "derecha", 600.0, self.P)
        b = motor.interpretar("ok", 8.55, 2.12, TAM, "izquierda", 600.0, self.P)        # la película girada 180 grados
        assert b["desfase_mm"] == pytest.approx(-a["desfase_mm"])
        assert b["desfase_fisico_mm"] == pytest.approx(a["desfase_fisico_mm"]) and b["sentido"] == a["sentido"]

    def test_despues_de_la_marca_con_el_desfase_fisico_positivo(self):
        r = motor.interpretar("ok", 30.0, 2.0, TAM, "derecha", 600.0, self.P)
        assert r["desfase_fisico_mm"] > 0 and r["sentido"] == "despues de la marca" and r["veredicto"] == "No cumple"

    def test_sin_banda_de_transito_habla_de_la_imagen_y_lo_dice(self):
        izquierda = motor.interpretar("ok", 14.0, 1.0, TAM, None, 600.0, self.P)
        derecha = motor.interpretar("ok", -14.0, 1.0, TAM, None, 600.0, self.P)
        assert izquierda["desfase_fisico_mm"] is None and derecha["desfase_fisico_mm"] is None
        assert izquierda["sentido"] == "a la izquierda de la linea en la imagen (no se distingue la banda de transito)"
        assert derecha["sentido"] == "a la derecha de la linea en la imagen (no se distingue la banda de transito)"

    def test_la_tolerancia_es_inclusiva_y_es_la_que_se_recibe(self):
        en_el_limite = motor.interpretar("ok", 1.0 / TAM, 1.0, TAM, "derecha", 600.0, self.P)
        encima = motor.interpretar("ok", 1.0 / TAM + 0.5, 1.0, TAM, "derecha", 600.0, self.P)
        assert en_el_limite["veredicto"] == "Cumple" and encima["veredicto"] == "No cumple"
        estricta = dict(self.P, tolerancia_mm=0.5)
        assert motor.interpretar("ok", 0.7 / TAM, 1.0, TAM, "derecha", 600.0, estricta)["veredicto"] == "No cumple"
        assert motor.interpretar("ok", 0.7 / TAM, 1.0, TAM, "derecha", 600.0, self.P)["veredicto"] == "Cumple"

    @pytest.mark.parametrize("clics,datos", [(CLICS_PLACA_REAL, BRAQUI_00), (CLICS_EPSON009, EPSON009)])
    def test_resumen_y_la_funcion_pura_dicen_lo_mismo_sobre_placas_reales(self, clics, datos):
        gris, color, dpi, _ = motor.leer_imagen(datos)
        resultado = motor.analizar(gris, color, dpi, clics)
        r = motor.resumen(resultado)
        v = motor.valores_medidos(resultado)
        p = motor.interpretar(v["estado_gris"], v["desfase_gris_px"], v["incertidumbre_gris_px"], v["tamano_pixel_mm"],
                              v["lado_transito"], dpi, resultado["parametros"])
        assert p and all(r[k] == p[k] for k in p), (r, p)


# ---------------------------------------------------------------------------------------------------------- guardar

class TestGuardar:
    def test_lo_guardado_es_lo_que_mide_el_motor_sobre_la_placa_real(self, bd):
        _sembrar(bd)
        nuevo = svc.guardar(USUARIO, S1, BRAQUI_00, "C:\\Users\\alguien\\Pictures\\braqui_00.jpeg", CLICS_PLACA_REAL,
                            observaciones="placa de control")
        r = svc.leer(nuevo)
        assert r["id"] == nuevo and r["activo"] == 1 and r["observaciones"] == "placa de control"
        assert r["imagen"] == BRAQUI_00 and r["imagen_md5"] == hashlib.md5(BRAQUI_00).hexdigest() == MD5_PLACA_REAL
        assert (r["fecha"], r["serie_fuente"], r["user"]) == (S1, SERIE_A, USUARIO)
        assert r["imagen_nombre"] == "braqui_00.jpeg"                      # solo el nombre: no la carpeta del equipo
        assert r["dpi"] == 600.0 and r["tamano_pixel_mm"] == pytest.approx(TAM)
        assert r["desfase_gris_px"] == pytest.approx(CONTROL_G1_PX, abs=1e-6)
        assert r["desfase_gris_mm"] == pytest.approx(CONTROL_G1_MM, abs=1e-6)
        assert r["incertidumbre_gris_px"] * TAM == pytest.approx(CONTROL_G1_U_MM, abs=5e-5)
        assert r["estado_gris"] == "ok" and r["lado_transito"] == "derecha"
        assert r["estado_r"] == "no medible: la mancha esta cortada por el borde de la pelicula"
        assert r["estado_g"] == "ok" and r["estado_b"] == "ok" and r["filas_gris"] > 10
        assert (r["tolerancia_mm"], r["version_algoritmo"]) == (1.0, "PI-1")
        assert json.loads(r["puntos"]) == [[191.0, 377.0], [190.0, 56.0]]
        assert json.loads(r["parametros"]) == motor.PARAMETROS

    def test_reabrir_con_los_bytes_los_puntos_y_los_parametros_guardados_da_lo_mismo_al_bit(self, bd):
        """La base del 'recalcular y comparar' de PI.4 (DD3): lo recalculado al abrir es lo que se firmó."""
        _sembrar(bd)
        r = svc.leer(svc.guardar(USUARIO, S1, BRAQUI_00, "braqui_00.jpeg", CLICS_PLACA_REAL))
        de_nuevo = motor.valores_medidos(svc.analizar_imagen(r["imagen"], json.loads(r["puntos"]),
                                                              json.loads(r["parametros"])))
        assert de_nuevo and all(r[k] == v for k, v in de_nuevo.items())

    def test_la_firma_no_recibe_un_resultado_ajeno(self):
        """Nada garantiza que un `resultado` recibido sea el de esa imagen (IM3/DA-65): se analiza desde los bytes."""
        parametros = list(inspect.signature(svc.guardar).parameters)
        assert parametros == ["usuario", "fecha", "imagen_bytes", "imagen_nombre", "puntos", "reemplazar", "observaciones"]

    def test_guarda_un_perfil_no_medible_con_su_estado(self, bd):
        _sembrar(bd)
        imagen, puntos = _sintetica(15)
        nuevo = _guardar(imagen=imagen, puntos=puntos)
        r = svc.leer(nuevo)
        assert r["estado_gris"] == "no medible: la mancha se sale de la zona marcada" and r["desfase_gris_px"] is None
        assert r["desfase_gris_mm"] is None and r["incertidumbre_gris_px"] is None

    CASOS_RECHAZADOS = {
        "usuario vacio": dict(usuario="   "),
        "usuario None": dict(usuario=None),
        "fecha ilegible": dict(fecha="26-06-2026"),
        "fecha None": dict(fecha=None),
        "fecha que no es de un cambio de fuente": dict(fecha="2026-03-01"),
        "fecha del cambio de fuente de fecha ilegible": dict(fecha="2025-09-27"),
        "fecha de un cambio de fuente anulado": dict(fecha="2026-06-26"),
        "imagen vacia": dict(imagen=b""),
        "imagen que no es bytes": dict(imagen="texto"),
        "imagen ilegible": dict(imagen=b"esto no es una imagen"),
        "un solo punto": dict(puntos=[(1, 2)]),
        "tres puntos": dict(puntos=[(1, 2), (3, 4), (5, 6)]),
        "punto no numerico": dict(puntos=[("a", 1), (2, 3)]),
        "punto infinito": dict(puntos=[(float("inf"), 1), (2, 3)]),
        "punto NaN": dict(puntos=[(float("nan"), 1), (2, 3)]),
        "puntos que coinciden": dict(puntos=[(5, 5), (5, 5)]),
    }

    @pytest.mark.parametrize("caso", sorted(CASOS_RECHAZADOS))
    def test_rechaza_y_no_escribe_nada(self, bd, caso):
        _sembrar(bd)
        argumentos = dict(usuario=USUARIO, fecha=S1, imagen=_sintetica(-0.6)[0], puntos=_sintetica(-0.6)[1])
        argumentos.update(self.CASOS_RECHAZADOS[caso])
        with pytest.raises(ValueError):
            svc.guardar(argumentos["usuario"], argumentos["fecha"], argumentos["imagen"], "x.png", argumentos["puntos"])
        assert _filas(bd) == [] and _auditoria(bd) == [], caso

    def test_la_tabla_de_casos_rechazados_no_esta_vacia(self):
        assert len(self.CASOS_RECHAZADOS) >= 16

    def test_un_cambio_de_fuente_sin_serie_se_rechaza_porque_el_mensual_jamas_la_imprimiria(self, bd):
        for serie in (None, "   "):
            _calibracion(bd, "2026-07-01 10:00:00", "Cambio de fuente", serie)
            with pytest.raises(svc.PosicionInicialError, match="no tiene serie"):
                _guardar(fecha="2026-07-01")
            _sql(bd, "UPDATE TipoCalibracion SET activo = 0")
        assert _filas(bd) == []

    def test_dos_cambios_de_fuente_del_mismo_dia_con_series_distintas_se_rechazan(self, bd):
        _sql(bd, f'DROP INDEX "{nombre_indice("TipoCalibracion")}"')          # sin el indice de EB6 podria haber dos
        _calibracion(bd, "2026-07-01 10:00:00", "Cambio de fuente", SERIE_A)
        _calibracion(bd, "2026-07-01 18:00:00", "Cambio de fuente", SERIE_B)
        with pytest.raises(svc.PosicionInicialError, match="series distintas"):
            _guardar(fecha="2026-07-01")
        assert _filas(bd) == []

    def test_dos_filas_del_mismo_cambio_con_la_misma_serie_no_estorban(self, bd):
        _sql(bd, f'DROP INDEX "{nombre_indice("TipoCalibracion")}"')
        _calibracion(bd, "2026-07-01 10:00:00", "Cambio de fuente", SERIE_A)
        _calibracion(bd, "2026-07-01 18:00:00", "Cambio de fuente", f" {SERIE_A} ")
        assert svc.leer(_guardar(fecha="2026-07-01"))["serie_fuente"] == SERIE_A

    def test_reguardar_la_misma_fecha_exige_reemplazar_y_anula_la_anterior(self, bd):
        _sembrar(bd)
        primera = _guardar()
        with pytest.raises(svc.PruebaYaGuardada):
            _guardar()
        assert _filas(bd) == [(primera, S1, 1)] and len(_auditoria(bd)) == 1        # el intento rechazado no dejo nada
        segunda = _guardar(reemplazar=True)
        assert segunda != primera and _filas(bd) == [(primera, S1, 0), (segunda, S1, 1)]
        guardado, reemplazo = _auditoria(bd)
        assert (guardado[0], guardado[1], guardado[2]) == ("guardar", USUARIO, str(primera))
        assert (reemplazo[0], reemplazo[1], reemplazo[2]) == ("reemplazo", USUARIO, str(segunda))
        assert f"reemplaza id={primera}" in reemplazo[3] and S1 in reemplazo[3] and SERIE_A in reemplazo[3]

    def test_la_fecha_se_normaliza_asi_que_la_misma_cambio_no_puede_tener_dos_vigentes(self, bd):
        """La clave del indice es la fecha cruda: con hora y sin hora serian dos 'fechas' distintas."""
        _sembrar(bd)
        primera = _guardar(fecha=f"{S1} 15:03:03")
        assert svc.leer(primera)["fecha"] == S1
        with pytest.raises(svc.PruebaYaGuardada):
            _guardar(fecha=S1)
        segunda = _guardar(fecha=datetime(2026, 1, 10, 8, 0, 0), reemplazar=True)
        assert [(f, a) for _, f, a in _filas(bd)] == [(S1, 0), (S1, 1)] and svc.posicion_inicial_para(S1)["id"] == segunda

    def test_reemplazar_sin_una_prueba_previa_solo_guarda(self, bd):
        _sembrar(bd)
        nueva = _guardar(reemplazar=True)
        assert _filas(bd) == [(nueva, S1, 1)] and [a[0] for a in _auditoria(bd)] == ["guardar"]

    def test_entero_o_nada_si_el_insert_falla_no_se_anula_ni_se_audita(self, bd, monkeypatch):
        """Un milimetro que no es pixeles por escala lo rechaza el CHECK de PI.2: la anulacion de la vigente, que ya se
        habia ejecutado en la misma transaccion, tiene que deshacerse, y la auditoria tampoco queda."""
        _sembrar(bd)
        primera = _guardar()
        antes = _auditoria(bd)
        real = motor.valores_medidos

        def con_milimetros_que_no_cuadran(resultado):
            valores = real(resultado)
            valores["desfase_gris_mm"] = valores["desfase_gris_mm"] + 1.0
            return valores
        monkeypatch.setattr(motor, "valores_medidos", con_milimetros_que_no_cuadran)
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            _guardar(reemplazar=True)
        assert _filas(bd) == [(primera, S1, 1)] and _auditoria(bd) == antes

    def test_devuelve_el_id_de_la_prueba_vigente(self, bd):
        _sembrar(bd)
        assert _guardar() == svc.posicion_inicial_para(S1)["id"]

    def test_la_imagen_se_guarda_tal_como_se_subio_y_el_nombre_sin_carpeta(self, bd):
        _sembrar(bd)
        imagen, puntos = _sintetica(-0.6)
        for nombre, esperado in (("C:\\carpeta\\sub\\placa.png", "placa.png"), ("/home/x/placa.png", "placa.png"),
                                 ("placa.png", "placa.png"), (None, None), ("  ", None)):
            fila = svc.leer(svc.guardar(USUARIO, S1, bytearray(imagen), nombre, puntos, reemplazar=True))
            assert fila["imagen"] == imagen and fila["imagen_nombre"] == esperado


# ----------------------------------------------------------------------------------------------------------- anular

class TestAnular:
    def test_anula_audita_en_la_misma_transaccion_y_deja_de_listarse(self, bd):
        _sembrar(bd)
        nuevo = _guardar()
        assert svc.anular(nuevo, USUARIO, "porque se repitio la placa") is True
        assert _filas(bd) == [(nuevo, S1, 0)] and svc.listar() == [] and not svc.existe_vigente(S1)
        accion, usuario, ref, detalle = _auditoria(bd)[-1]
        assert (accion, usuario, ref) == ("anular", USUARIO, str(nuevo))
        assert f"id={nuevo}" in detalle and S1 in detalle and "porque se repitio la placa" in detalle
        assert [a[0] for a in _auditoria(bd)] == ["guardar", "anular"]

    def test_anular_otra_vez_o_un_id_que_no_existe_no_escribe_ni_audita(self, bd):
        _sembrar(bd)
        nuevo = _guardar()
        assert svc.anular(nuevo, USUARIO) and not svc.anular(nuevo, USUARIO) and not svc.anular(99999, USUARIO)
        assert [a[0] for a in _auditoria(bd)] == ["guardar", "anular"]

    def test_sin_usuario_no_se_anula(self, bd):
        _sembrar(bd)
        nuevo = _guardar()
        with pytest.raises(svc.PosicionInicialError):
            svc.anular(nuevo, "  ")
        assert _filas(bd) == [(nuevo, S1, 1)]

    def test_una_prueba_anulada_se_puede_volver_a_guardar_para_ese_cambio(self, bd):
        _sembrar(bd)
        primera = _guardar()
        svc.anular(primera, USUARIO)
        segunda = _guardar()                                   # no hay vigente: no pide reemplazar
        assert svc.posicion_inicial_para(S1)["id"] == segunda and _filas(bd) == [(primera, S1, 0), (segunda, S1, 1)]


# ----------------------------------------------------------------------------------------------- listar, leer, existe

class TestListarYLeer:
    def test_listar_trae_las_vigentes_sin_los_bytes_la_mas_reciente_primero(self, bd):
        _sembrar(bd)
        _guardar(fecha=S1)
        _guardar(fecha=S2)
        filas = svc.listar()
        assert [f["fecha"] for f in filas] == [S2, S1]
        assert all("imagen" not in f and "activo" not in f for f in filas)
        assert {"id", "fecha", "serie_fuente", "user", "parametros", "desfase_gris_px", "tolerancia_mm"} <= set(filas[0])

    def test_listar_marca_si_el_cambio_de_fuente_sigue_vigente(self, bd):
        ids = _sembrar(bd)
        _guardar(fecha=S1)
        _guardar(fecha=S2)
        assert {f["fecha"]: f["cambio_de_fuente_vigente"] for f in svc.listar()} == {S1: True, S2: True}
        _sql(bd, "UPDATE TipoCalibracion SET activo = 0 WHERE id = ?", (ids["s2"],))
        assert {f["fecha"]: f["cambio_de_fuente_vigente"] for f in svc.listar()} == {S1: True, S2: False}

    def test_listar_no_trae_las_anuladas(self, bd):
        _sembrar(bd)
        _sembrar_prueba(bd, S1, activo=0)
        vigente = _sembrar_prueba(bd, S1)
        assert [f["id"] for f in svc.listar()] == [vigente]

    def test_leer_trae_la_fila_completa_con_la_imagen_aunque_este_anulada(self, bd):
        """Lectura de IDENTIDAD (DA-47): abrir un registro anulado debe dar la fila, no 'nada'."""
        _sembrar(bd)
        nuevo = _guardar(imagen=BRAQUI_00, puntos=CLICS_PLACA_REAL)
        svc.anular(nuevo, USUARIO)
        fila = svc.leer(nuevo)
        assert fila["activo"] == 0 and fila["imagen"] == BRAQUI_00 and fila["id"] == nuevo
        assert svc.leer(99999) is None

    def test_existe_vigente(self, bd):
        _sembrar(bd)
        _sembrar_prueba(bd, S1)
        _sembrar_prueba(bd, S2, activo=0)
        assert svc.existe_vigente(S1) and svc.existe_vigente(f"{S1} 23:59:59") and svc.existe_vigente(date(2026, 1, 10))
        assert not svc.existe_vigente(S2) and not svc.existe_vigente("2026-03-01")
        assert not svc.existe_vigente("20260110") and not svc.existe_vigente(None) and not svc.existe_vigente("")


# ----------------------------------------------------------------------------------------------- cambios de fuente

class TestCambiosDeFuente:
    def test_solo_los_cambios_de_fuente_vigentes_y_legibles_del_mas_reciente_al_mas_antiguo(self, bd):
        _sembrar(bd)
        assert svc.cambios_de_fuente() == [(S2, SERIE_B), (S1, SERIE_A)]
        # lo que NO entra: la calibracion redundante del mismo dia, los controles mensuales, la fila de tipo vacio, el
        # cambio de fuente de fecha ilegible y el anulado (la siembra afirma que existen)

    def test_las_horas_no_cambian_la_fecha(self, bd):
        _calibracion(bd, "2026-03-05 23:59:59", "Cambio de fuente", SERIE_A)
        assert svc.cambios_de_fuente() == [("2026-03-05", SERIE_A)]

    def test_un_mismo_dia_aparece_una_vez_con_la_serie_de_la_fila_mas_nueva(self, bd):
        _sql(bd, f'DROP INDEX "{nombre_indice("TipoCalibracion")}"')
        _calibracion(bd, "2026-03-05 08:00:00", "Cambio de fuente", SERIE_A)
        _calibracion(bd, "2026-03-05 20:00:00", "Cambio de fuente", SERIE_B)
        assert svc.cambios_de_fuente() == [("2026-03-05", SERIE_B)]

    def test_sin_cambios_de_fuente_no_hay_lista(self, bd):
        assert svc.cambios_de_fuente() == []

    def test_el_tipo_es_el_que_escribe_el_boton_de_cambio_de_fuente(self):
        """Una cadena escrita aqui y otra en `braq_mensual` se pueden separar sin que nada falle: se atan por el AST."""
        arbol = ast.parse((RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "braq_mensual.py").read_text("utf-8"))
        retornos = [n.value.value for f in ast.walk(arbol) if isinstance(f, ast.FunctionDef)
                    and f.name == "_tipo_calibracion_seleccionado" for n in ast.walk(f)
                    if isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)]
        assert retornos and svc.TIPO_CAMBIO_DE_FUENTE in retornos, retornos


class TestCambioDeFuentePorDefecto:
    """DD7: el más cercano a la fecha del escaneo, solo si está a 7 días o menos de calendario; empate, el anterior."""

    @pytest.fixture
    def con_cambios(self, bd):
        _sembrar(bd)
        return bd

    @pytest.mark.parametrize("escaneo,esperado", [
        ("2026-01-10", (S1, SERIE_A)), ("2026-01-13", (S1, SERIE_A)), ("2026-01-17", (S1, SERIE_A)),   # 7 dias: inclusive
        ("2026-01-18", None),                                                                          # 8 dias
        ("2026-01-07", (S1, SERIE_A)), ("2026-01-03", (S1, SERIE_A)), ("2026-01-02", None),
        ("2026-04-12", (S2, SERIE_B)), ("2026-04-22", (S2, SERIE_B)), ("2026-04-23", None),            # uno POSTERIOR cuenta
        ("2026-03-01", None), ("2025-09-27", None)])
    def test_a_siete_dias_o_menos(self, con_cambios, escaneo, esperado):
        assert svc.cambio_de_fuente_por_defecto(escaneo) == esperado

    def test_acepta_fechas_y_datetimes(self, con_cambios):
        assert svc.cambio_de_fuente_por_defecto(date(2026, 1, 12)) == (S1, SERIE_A)
        assert svc.cambio_de_fuente_por_defecto(datetime(2026, 1, 12, 23, 59)) == (S1, SERIE_A)
        # la hora del escaneo no cuenta: 7 dias de calendario (en horas serian 7.5) siguen siendo 7, e inclusive
        assert svc.cambio_de_fuente_por_defecto(datetime(2026, 1, 17, 12, 0)) == (S1, SERIE_A)
        assert svc.cambio_de_fuente_por_defecto(datetime(2026, 1, 18, 0, 1)) is None

    @pytest.mark.parametrize("escaneo", ["20260110", "10/01/2026", "no es fecha", 20260110])
    def test_una_fecha_de_escaneo_que_no_es_fecha_no_propone_nada(self, con_cambios, escaneo):
        assert svc.cambio_de_fuente_por_defecto(escaneo) is None

    def test_a_igual_distancia_el_anterior(self, bd):
        _calibracion(bd, "2026-01-10 10:00:00", "Cambio de fuente", SERIE_A)
        _calibracion(bd, "2026-01-24 10:00:00", "Cambio de fuente", SERIE_B)
        assert svc.cambio_de_fuente_por_defecto("2026-01-17") == ("2026-01-10", SERIE_A)       # 7 y 7: el anterior
        assert svc.cambio_de_fuente_por_defecto("2026-01-18") == ("2026-01-24", SERIE_B)       # 8 contra 6

    def test_la_distancia_es_de_dias_de_calendario_no_de_horas(self, bd):
        """23:50 del dia del cambio, y la fecha del escaneo 7 dias antes: 7 dias de calendario (en horas serian casi 8)."""
        _calibracion(bd, "2026-04-15 23:50:00", "Cambio de fuente", SERIE_B)
        assert svc.cambio_de_fuente_por_defecto("2026-04-08") == ("2026-04-15", SERIE_B)
        assert svc.cambio_de_fuente_por_defecto("2026-04-07") is None

    def test_un_cambio_de_fuente_anulado_no_se_propone(self, bd):
        _calibracion(bd, "2026-03-01 10:00:00", "Cambio de fuente", SERIE_A, activo=0)
        assert svc.cambio_de_fuente_por_defecto("2026-03-03") is None

    def test_sin_fecha_de_escaneo_se_usa_hoy(self, bd):
        hoy = date.today()
        _calibracion(bd, f"{(hoy - timedelta(days=3)).isoformat()} 10:00:00", "Cambio de fuente", SERIE_A)
        assert svc.cambio_de_fuente_por_defecto() == ((hoy - timedelta(days=3)).isoformat(), SERIE_A)
        assert svc.cambio_de_fuente_por_defecto(None, hoy=hoy + timedelta(days=30)) is None

    def test_sin_cambios_de_fuente_no_hay_propuesta(self, bd):
        assert svc.cambio_de_fuente_por_defecto("2026-01-10") is None


# ------------------------------------------------------------------------------------- la regla de vigencia (§0.2)

class TestReglaDeVigencia:
    """S1 = 2026-01-10 (serie A) y S2 = 2026-04-15 (serie B); una prueba P1 guardada para S1 y NINGUNA para S2."""

    @pytest.fixture
    def con_p1(self, bd):
        ids = _sembrar(bd)
        ids["p1"] = _sembrar_prueba(bd, S1, SERIE_A)
        return ids

    @pytest.mark.parametrize("fecha", ["2026-01-10", "2026-01-10 00:00:01", "2026-03-01", "2026-03-01 23:59:59",
                                       "2026-04-14", date(2026, 3, 1), datetime(2026, 4, 14, 23, 59, 59)])
    def test_en_todo_el_periodo_de_la_fuente_vale_su_prueba(self, bd, con_p1, fecha):
        assert svc.posicion_inicial_para(fecha)["id"] == con_p1["p1"]

    @pytest.mark.parametrize("fecha", ["2026-04-15", "2026-04-15 08:00:00", "2026-05-20", "2026-12-31",
                                       "2026-01-09", "2025-09-27", "2025-10-15"])
    def test_fuera_del_periodo_o_sin_prueba_en_su_fuente_no_vale_ninguna(self, bd, con_p1, fecha):
        """El 15-04 entra la fuente S2, que no tiene prueba: NO vale 'la mas reciente <= D' (que seria P1)."""
        assert svc.posicion_inicial_para(fecha) is None

    @pytest.mark.parametrize("fecha", [None, "", "27-09-2025", "20260110", "hoy", 20260110])
    def test_una_fecha_que_no_es_fecha_da_none_y_no_revienta(self, bd, con_p1, fecha):
        assert svc.posicion_inicial_para(fecha) is None
        assert svc.posicion_inicial_para(fecha, serie=SERIE_A) is None

    def test_la_prueba_de_la_otra_fuente_aparece_en_su_propio_periodo(self, bd, con_p1):
        p2 = _sembrar_prueba(bd, S2, SERIE_B)
        assert svc.posicion_inicial_para("2026-04-14")["id"] == con_p1["p1"]
        assert svc.posicion_inicial_para("2026-04-15")["id"] == p2 and svc.posicion_inicial_para("2026-09-30")["id"] == p2

    def test_con_la_prueba_anulada_no_vale_ninguna(self, bd, con_p1):
        _sql(bd, "UPDATE braqui_posicion_inicial SET activo = 0")
        assert svc.posicion_inicial_para("2026-03-01") is None

    def test_reguardar_el_cambio_de_fuente_cambia_su_id_pero_no_su_fecha_y_la_prueba_sigue(self, bd, con_p1):
        _sql(bd, "UPDATE TipoCalibracion SET activo = 0 WHERE id = ?", (con_p1["s1"],))
        nuevo = _calibracion(bd, f"{S1} 18:00:00", "Cambio de fuente", SERIE_A)
        assert nuevo != con_p1["s1"] and svc.posicion_inicial_para("2026-03-01")["id"] == con_p1["p1"]

    def test_un_cambio_de_fuente_anulado_con_su_prueba_vigente_no_vale(self, bd, con_p1):
        _sql(bd, "UPDATE TipoCalibracion SET activo = 0 WHERE id IN (?, ?)", (con_p1["s1"], con_p1["s2"]))
        assert svc.posicion_inicial_para("2026-03-01") is None
        assert [(f["fecha"], f["cambio_de_fuente_vigente"]) for f in svc.listar()] == [(S1, False)]

    def test_limitacion_medida_cambio_de_fuente_anulado_sin_reguardar_el_diario_cae_a_la_fuente_anterior(self, bd, con_p1):
        """Opus, 02-10 (§0.1 de la revision): si S2 se anula y no se reguarda, la regla cae a S1. El diario (que no guarda
        serie) imprime la prueba de la fuente anterior; el mensual se salva por DD8. Se fija para que nadie lo cambie sin
        saberlo; queda la pregunta al fisico de si se exige la serie tambien en el diario."""
        _sql(bd, "UPDATE TipoCalibracion SET activo = 0 WHERE id = ?", (con_p1["s2"],))
        assert svc.posicion_inicial_para("2026-05-01")["id"] == con_p1["p1"]                 # el diario
        assert svc.posicion_inicial_para("2026-05-01", serie=SERIE_B) is None                # el mensual de la fuente B
        assert svc.posicion_inicial_para("2026-05-01", serie=SERIE_A)["id"] == con_p1["p1"]

    def test_el_dia_del_cambio_todo_el_dia_es_de_la_fuente_nueva_aunque_el_cambio_se_guardara_por_la_tarde(self, bd, con_p1):
        """La regla usa DATE(): un diario del dia del cambio tomado a las 08:00 ya es de S2 (S2 se guardo a las 09:30).
        La actividad esperada del diario compara fechas con hora y puede ver la fuente anterior ese dia (1 de 342 en la
        copia del 21-09): son dos 'fuente en uso' en un mismo PDF. Se fija; no se toca braquiterapia."""
        p2 = _sembrar_prueba(bd, S2, SERIE_B)
        assert svc.posicion_inicial_para(f"{S2} 08:00:00")["id"] == p2

    @pytest.mark.parametrize("serie,vale", [
        (SERIE_A, True), (f"  {SERIE_A}  ", True), (SERIE_B, False), (SERIE_A.lower(), False), (SERIE_A + "X", False)])
    def test_dd8_en_el_mensual_la_serie_debe_ser_la_que_la_prueba_copio(self, bd, con_p1, serie, vale):
        r = svc.posicion_inicial_para("2026-03-01", serie=serie)
        assert (r is not None and r["id"] == con_p1["p1"]) == vale

    @pytest.mark.parametrize("serie", [None, "", "   "])
    def test_una_serie_vacia_en_el_mensual_no_es_sin_filtro_es_no_se_puede_comprobar(self, bd, con_p1, serie):
        assert svc.posicion_inicial_para("2026-03-01", serie=serie) is None
        assert svc.posicion_inicial_para("2026-03-01")["id"] == con_p1["p1"]                  # sin serie: el diario

    def test_una_prueba_sin_serie_copiada_no_sale_en_ningun_mensual_pero_si_en_el_diario(self, bd):
        _sembrar(bd)
        p = _sembrar_prueba(bd, S1, serie=None)
        assert svc.posicion_inicial_para("2026-03-01")["id"] == p
        assert svc.posicion_inicial_para("2026-03-01", serie=SERIE_A) is None
        assert svc.posicion_inicial_para("2026-03-01", serie=None) is None        # NULL contra NULL no es una coincidencia
        assert svc.posicion_inicial_para("2026-03-01", serie="") is None

    def test_los_controles_mensuales_y_la_calibracion_redundante_no_son_cambios_de_fuente(self, bd, con_p1):
        """El 2026-02-20 hay un control mensual de la serie A y el 2026-01-10 una redundante: no abren periodo nuevo."""
        assert svc.posicion_inicial_para("2026-02-21")["id"] == con_p1["p1"]
        assert svc.posicion_inicial_para("2026-03-02")["id"] == con_p1["p1"]               # tras la fila de tipo vacio

    def test_la_prueba_de_un_cambio_de_fuente_de_fecha_ilegible_no_se_alcanza(self, bd):
        _sembrar(bd)
        _sembrar_prueba(bd, "2025-09-27", SERIE_A)
        assert svc.posicion_inicial_para("2025-12-01") is None and svc.posicion_inicial_para("2025-09-27") is None

    def test_la_siembra_tiene_lo_que_dice_tener(self, bd, con_p1):
        assert {r[0] for r in _consulta(bd, "SELECT tipo FROM TipoCalibracion")} == {
            "Cambio de fuente", "Calibración Redundante", "Control Mensual", ""}
        assert _consulta(bd, "SELECT COUNT(*) FROM TipoCalibracion WHERE activo = 0")[0][0] == 1


# ---------------------------------------------------------------------------------------------------- texto breve

CABECERA_S1 = f". Cambio de fuente del {S1}"


def _registro(desfase_mm=-0.36, u_mm=0.09, lado="derecha", tam=TAM, dpi=600.0, tolerancia=1.0, estado="ok", **extra):
    """Una fila como la que devuelve `listar` (lo que `texto_breve` consume), construida desde milimetros."""
    escala = TAM if tam is None else tam               # sin escala guardada los pixeles siguen siendo pixeles
    fila = {"fecha": S1, "estado_gris": estado, "desfase_gris_px": None if desfase_mm is None else desfase_mm / escala,
            "incertidumbre_gris_px": None if u_mm is None else u_mm / escala, "tamano_pixel_mm": tam, "lado_transito": lado,
            "dpi": dpi, "tolerancia_mm": tolerancia, "parametros": json.dumps(motor.PARAMETROS)}
    fila.update(extra)
    return fila


class TestTextoBreveSobreLoGuardado:
    """Los seis casos del plan, de punta a punta: `guardar` -> BD -> `posicion_inicial_para`, texto exacto."""

    def _texto(self, **argumentos):
        _guardar(reemplazar=True, **argumentos)
        return svc.texto_breve(svc.posicion_inicial_para(S1))

    def test_cumple_con_el_sentido_fisico_la_placa_real(self, bd):
        _sembrar(bd)
        assert self._texto(imagen=BRAQUI_00, puntos=CLICS_PLACA_REAL) == (
            "-0.36 ± 0.09 mm (k = 2), antes de la marca. Cumple (tolerancia 1.0 mm)" + CABECERA_S1)

    def test_no_cumple_sin_banda_de_transito(self, bd):
        _sembrar(bd)
        imagen, puntos = _sintetica(1.5)
        assert self._texto(imagen=imagen, puntos=puntos) == (
            "1.50 ± 0.02 mm (k = 2) a la izquierda de la linea en la imagen (no se distingue la banda de transito). "
            "No cumple (tolerancia 1.0 mm)" + CABECERA_S1)

    def test_sin_banda_de_transito_y_sin_resolucion_declarada_cumple(self, bd):
        _sembrar(bd)
        imagen, puntos = _sintetica(-0.6)
        assert self._texto(imagen=imagen, puntos=puntos) == (
            "-0.60 ± 0.03 mm (k = 2) a la derecha de la linea en la imagen (no se distingue la banda de transito). "
            "Cumple (tolerancia 1.0 mm)" + CABECERA_S1)

    def test_no_medible_dice_el_motivo(self, bd):
        _sembrar(bd)
        imagen, puntos = _sintetica(15)
        assert self._texto(imagen=imagen, puntos=puntos) == (
            "No medible: la mancha se sale de la zona marcada" + CABECERA_S1)

    def test_otra_resolucion_declarada_da_pixeles_y_el_aviso_sin_milimetros_ni_veredicto(self, bd):
        _sembrar(bd)
        imagen = _a_300_dpi()
        gris, color, dpi, _ = motor.leer_imagen(imagen)
        assert dpi == 300.0
        valores = motor.valores_medidos(motor.analizar(gris, color, dpi, CLICS_PLACA_REAL))
        esperado = (f"{valores['desfase_gris_px']:.2f} ± {valores['incertidumbre_gris_px']:.2f} px (k = 2); la imagen "
                    "declara 300 dpi y el procedimiento es de 600 dpi: parece escaneada a otra resolucion; escanee la "
                    "pelicula a 600 dpi. Sin milimetros ni veredicto" + CABECERA_S1)
        texto = self._texto(imagen=imagen, puntos=CLICS_PLACA_REAL)
        assert texto == esperado and re.match(r"^-?\d+\.\d{2} ± \d+\.\d{2} px \(k = 2\); ", texto)
        registro = svc.posicion_inicial_para(S1)
        assert registro["tamano_pixel_mm"] is None and registro["desfase_gris_mm"] is None and registro["dpi"] == 300.0

    def test_resolucion_de_editor_da_milimetros_con_el_mismo_formato(self, bd):
        """EPSON009 declara 96.012 dpi (lo que Paint escribe al recortar): la nota es solo de pantalla, el texto es normal."""
        _sembrar(bd)
        assert self._texto(imagen=EPSON009, puntos=CLICS_EPSON009) == (
            "-0.11 ± 0.18 mm (k = 2), antes de la marca. Cumple (tolerancia 1.0 mm)" + CABECERA_S1)
        assert svc.posicion_inicial_para(S1)["dpi"] == pytest.approx(96.012, abs=1e-3)
        assert CONTROL_EPSON009["gris_mm"] == pytest.approx(-0.110204)

    def test_la_misma_pelicula_girada_180_grados_dice_lo_mismo_aunque_el_signo_de_la_imagen_cambie(self, bd):
        """V4 dentro de un PDF firmado: con el desfase de la IMAGEN, la misma fuente saldria '-0.38 ... antes' y
        '0.38 ... antes' segun como se coloco la pelicula. Con el fisico, el texto es el mismo."""
        _sembrar(bd)
        imagen0, clics0 = _hoja(rotar=False)
        imagen180, clics180 = _hoja(rotar=True)
        texto0 = self._texto(imagen=imagen0, puntos=clics0)
        fila0 = svc.posicion_inicial_para(S1)
        texto180 = self._texto(imagen=imagen180, puntos=clics180)
        fila180 = svc.posicion_inicial_para(S1)
        assert (fila0["lado_transito"], fila180["lado_transito"]) == ("derecha", "izquierda")
        assert fila0["desfase_gris_mm"] < 0 < fila180["desfase_gris_mm"]                    # el signo de la imagen SI cambia
        assert texto0 == texto180 and texto0.startswith("-0.38 ± ") and ", antes de la marca. Cumple" in texto0

    def test_el_texto_dice_lo_mismo_que_resumen_sobre_el_mismo_analisis(self, bd):
        """Corolario 3: las dos formas de mostrar lo mismo, comparadas (tres placas, las dos ramas del sentido)."""
        _sembrar(bd)
        casos = [(BRAQUI_00, CLICS_PLACA_REAL), (EPSON009, CLICS_EPSON009), _sintetica(-0.6), _sintetica(1.5)]
        for imagen, puntos in casos:
            texto = self._texto(imagen=imagen, puntos=puntos)
            gris, color, dpi, _ = motor.leer_imagen(imagen)
            r = motor.resumen(motor.analizar(gris, color, dpi, puntos))
            desfase = r["desfase_fisico_mm"] if r["desfase_fisico_mm"] is not None else r["desfase_mm"]
            assert texto.startswith(f"{desfase:.2f} ± {r['U_mm']:.2f} mm (k = 2)")
            assert r["sentido"] in texto and f". {r['veredicto']} (tolerancia" in texto

    def test_ningun_texto_lleva_simbolos_ni_caracteres_de_marcado(self, bd):
        _sembrar(bd)
        imagen15, puntos15 = _sintetica(15)
        for imagen, puntos in ((BRAQUI_00, CLICS_PLACA_REAL), (imagen15, puntos15), (_a_300_dpi(), CLICS_PLACA_REAL)):
            texto = self._texto(imagen=imagen, puntos=puntos)
            assert not set(texto) & set("<>&✓✗✔✘❌⚠"), texto            # DA-18, y la celda del PDF va en un Paragraph


class TestTextoBreveDeUnaFila:
    """`texto_breve` es una función de lo guardado: estas pruebas no pasan por el análisis."""

    def test_no_imprime_menos_cero(self):
        assert _registro(desfase_mm=-0.001).get("fecha") and svc.texto_breve(_registro(desfase_mm=-0.001)).startswith("0.00 ± ")

    def test_veredicto_sobre_el_valor_sin_redondear(self):
        """1.003 mm se imprime '1.00' y NO cumple: el veredicto es del valor, no del texto."""
        texto = svc.texto_breve(_registro(desfase_mm=1.003))
        assert texto.startswith("1.00 ± 0.09 mm (k = 2), despues de la marca. No cumple (tolerancia 1.0 mm)")

    def test_en_el_limite_cumple(self):
        assert ". Cumple (tolerancia 1.0 mm)" in svc.texto_breve(_registro(desfase_mm=1.0))

    def test_cero_exacto_es_despues_de_la_marca(self):
        assert svc.texto_breve(_registro(desfase_mm=0.0)).startswith("0.00 ± 0.09 mm (k = 2), despues de la marca. Cumple")

    @pytest.mark.parametrize("tolerancia,texto", [(0.5, "0.5"), (1.0, "1.0"), (0.25, "0.25"), (1.5, "1.5"), (2, "2.0")])
    def test_la_tolerancia_es_la_del_propio_registro(self, tolerancia, texto):
        """Cambiar la tolerancia en el codigo no reescribe veredictos guardados: manda la columna, no PARAMETROS."""
        assert f"(tolerancia {texto} mm)" in svc.texto_breve(_registro(desfase_mm=0.7, tolerancia=tolerancia))

    def test_con_tolerancia_de_medio_milimetro_0_7_no_cumple_aunque_el_codigo_diga_1(self):
        assert ". No cumple (tolerancia 0.5 mm)" in svc.texto_breve(_registro(desfase_mm=0.7, tolerancia=0.5))
        assert ". Cumple (tolerancia 1.0 mm)" in svc.texto_breve(_registro(desfase_mm=0.7, tolerancia=1.0))

    def test_sin_el_cambio_de_fuente_al_final_para_la_tabla_de_la_pagina(self):
        completo = svc.texto_breve(_registro())
        corto = svc.texto_breve(_registro(), con_cambio_de_fuente=False)
        assert completo == corto + CABECERA_S1 and "Cambio de fuente" not in corto
        assert "Cambio de fuente" not in svc.texto_breve(_registro(fecha=None))

    def test_un_registro_incompleto_no_revienta_y_lo_dice(self):
        assert svc.texto_breve(_registro(desfase_mm=None, u_mm=0.09, estado="ok")) == (
            "No medible: registro incompleto" + CABECERA_S1)
        assert svc.texto_breve(_registro(estado=None)) == "No medible: sin dato" + CABECERA_S1
        assert svc.texto_breve(_registro(estado="")) == "No medible: sin dato" + CABECERA_S1
        sin_escala_ni_dpi = svc.texto_breve(_registro(tam=None, dpi=None))
        assert "sin milimetros ni veredicto" in sin_escala_ni_dpi and " mm " not in sin_escala_ni_dpi

    def test_parametros_ilegibles_usan_los_del_motor(self):
        assert svc.texto_breve(_registro(parametros="no es json")).startswith("-0.36 ± 0.09 mm")
        assert svc.texto_breve(_registro(parametros=None)).startswith("-0.36 ± 0.09 mm")

    def test_un_estado_que_no_empieza_por_no_medible_se_antepone(self):
        assert svc.texto_breve(_registro(estado="algo raro")).startswith("No medible: algo raro")


# ---------------------------------------------------------------------------------------- una sola definición (AST)

def _literales_fuera_de_docstrings(arbol):
    docstrings = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and nodo.body:
            primero = nodo.body[0]
            if isinstance(primero, ast.Expr) and isinstance(getattr(primero, "value", None), ast.Constant):
                docstrings.add(id(primero.value))
    return [n.value for n in ast.walk(arbol)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]


class TestUnaSolaDefinicion:
    FUENTE = (RAIZ / "services" / "posicion_inicial_braqui.py").read_text(encoding="utf-8")
    ARBOL = ast.parse(FUENTE)

    def test_el_servicio_no_dice_antes_despues_cumple_ni_el_aviso_de_la_resolucion(self):
        """Esas frases las define `motor.interpretar`; el servicio solo da formato."""
        prohibidas = ("antes de la marca", "despues de la marca", "Cumple", "No cumple", "No medible",
                      "Sin milimetros ni veredicto", "parece escaneada", "linea en la imagen")
        propias = _literales_fuera_de_docstrings(self.ARBOL)
        assert propias and not [t for t in propias for p in prohibidas if p in t]

    def test_el_servicio_no_calcula_escalas_ni_milimetros(self):
        assert "25.4" not in self.FUENTE and "escala_mm" not in self.FUENTE and "resolucion_escaneo_dpi" not in self.FUENTE

    def test_usa_las_dos_funciones_del_motor(self):
        llamadas = {n.func.attr for n in ast.walk(self.ARBOL) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "motor"}
        assert {"valores_medidos", "interpretar", "leer_imagen", "analizar"} <= llamadas, llamadas

    def test_no_importa_qt(self):
        importados = {a.name.split(".")[0] for n in ast.walk(self.ARBOL) if isinstance(n, ast.Import) for a in n.names}
        importados |= {n.module.split(".")[0] for n in ast.walk(self.ARBOL) if isinstance(n, ast.ImportFrom) and n.module}
        assert not {m for m in importados if m.startswith(("PyQt", "PySide"))}

    def test_el_insert_y_las_lecturas_cubren_las_columnas_de_la_tabla(self, bd):
        """Una columna nueva de la tabla que el servicio no escribe o no lee se nota aqui."""
        columnas = [c[1] for c in _consulta(bd, f"PRAGMA table_info('{TABLA}')")]
        assert set(svc._COLUMNAS_INSERT) == set(columnas) - {"id", "activo"} and len(set(svc._COLUMNAS_INSERT)) == len(
            svc._COLUMNAS_INSERT)
        leidas = [c.strip() for c in svc._COLUMNAS_SQL.split(",")]
        assert set(leidas) == set(columnas) - {"imagen", "activo"}
        gris, color, dpi, _ = motor.leer_imagen(BRAQUI_00)
        assert set(motor.valores_medidos(motor.analizar(gris, color, dpi, CLICS_PLACA_REAL))) <= set(svc._COLUMNAS_INSERT)

    def test_el_centinela_de_serie_no_se_confunde_con_ningun_valor_de_una_serie(self):
        assert svc.SIN_FILTRO_DE_SERIE not in (None, "", " ") and repr(svc.SIN_FILTRO_DE_SERIE) == "SIN_FILTRO_DE_SERIE"
        assert inspect.signature(svc.posicion_inicial_para).parameters["serie"].default is svc.SIN_FILTRO_DE_SERIE
