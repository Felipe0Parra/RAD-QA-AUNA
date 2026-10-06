"""RB.2 (PLAN_GUARDADO_SIN_ESPESOR_Y_RESPALDOS_05-10.md, DP-150, decision D2 del fisico: "maximo dos por dia"): a lo sumo UN respaldo
por franja del dia -- mañana (antes de las 12:00) y tarde (desde las 12:00) --, hecho en el PRIMER cierre de la franja.

Antes se respaldaba en cada cierre, y volver a "Inicio" es un cierre: en produccion 39 respaldos en 18 dias, 5 dias con mas de dos,
hasta 6 en un dia (M9). La franja no se deduce del nombre de los respaldos (con relojes distintos entre equipos el nombre puede
llevar la hora de otro equipo): se lleva con `franja_<fecha>_<N>.reclamo` (alguien la esta haciendo) y `franja_<fecha>_<N>.hecha`.

Las carreras se prueban con INTERCALADOS DETERMINISTAS (puntos de corte inyectados en `respaldo._GANCHOS`), no solo lanzando procesos a
la vez: con bases pequeñas la copia dura milisegundos y la carrera puede no ocurrir. Ademas, 8 procesos reales a la vez, que es una
PRUEBA DE HUMO (F-05 de la revision): no fija ninguna carrera concreta -- eso lo hacen los intercalados --, solo comprueba que el
conjunto no deja dos copias ni marcas a medias.

Revision adversarial de RB.2 (05-10-2026): la franja y el nombre salen de la hora del SERVIDOR de la carpeta, no del reloj de cada equipo
(C1/F-01: con relojes distintos los equipos tambien se ponen de acuerdo); un reclamo con fecha en el futuro no bloquea la franja (C2); sin
permiso sobre la carpeta se avisa (E1/F-11); el cierre propaga `usuario` y `max_copias` (F-07); los umbrales de edad se prueban en sus
bordes (F-08).
"""
import ast
import errno
import inspect
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services import respaldo
from services.respaldo import HORA_DE_CORTE, franja_de, respaldar_al_cerrar, respaldar_bd

RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMITE_S = 40


def _dia(hora, minuto=0, segundo=0, dia=5):
    return datetime(2026, 10, dia, hora, minuto, segundo)


def _bd(ruta, filas=20):
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE datos (id INTEGER PRIMARY KEY, valor TEXT)")
    con.executemany("INSERT INTO datos (valor) VALUES (?)", [(f"fila {i}",) for i in range(filas)])
    con.commit()
    con.close()


@pytest.fixture
def entorno(tmp_path):
    origen = str(tmp_path / "BaseDatosQA.db")
    _bd(origen)
    carpeta = str(tmp_path / "respaldos_bd")
    return origen, carpeta


def _cerrar(entorno_, ahora, **kw):
    origen, carpeta = entorno_
    return respaldar_al_cerrar(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, ahora=ahora, **kw)


def _respaldos(carpeta):
    return respaldo._nombres_respaldo(carpeta)


def _marcas(carpeta):
    return sorted(n for n in os.listdir(carpeta) if n.startswith("franja_"))


def _reclamos(carpeta):
    return [n for n in _marcas(carpeta) if ".reclamo" in n]


_RELOJ_REAL = time.time        # algunas pruebas adelantan `time.time`; las fechas de los archivos se calculan siempre con el real


def _envejecer(ruta, segundos):
    """Hace que `ruta` parezca creada hace `segundos` (el reloj del servidor, en las pruebas, es el de este equipo)."""
    t = _RELOJ_REAL() - segundos
    os.utime(ruta, (t, t))


def _filas_de_auditoria(origen):
    con = sqlite3.connect(origen)
    try:
        try:
            return con.execute("SELECT ref FROM audit_log WHERE tabla = 'backup' ORDER BY id").fetchall()
        except sqlite3.OperationalError:
            return []
    finally:
        con.close()


# ------------------------------------------------------------------------------------------------------------ las franjas
class TestLasFranjas:
    def test_la_hora_de_corte_es_las_12(self):
        assert HORA_DE_CORTE == 12

    @pytest.mark.parametrize("momento, esperada", [
        (_dia(0, 0, 0), ("2026-10-05", 1)),
        (_dia(7, 30), ("2026-10-05", 1)),
        (_dia(11, 59, 59), ("2026-10-05", 1)),
        (_dia(12, 0, 0), ("2026-10-05", 2)),
        (_dia(15, 45), ("2026-10-05", 2)),
        (_dia(23, 59, 59), ("2026-10-05", 2)),
        (_dia(0, 0, 0, dia=6), ("2026-10-06", 1)),
    ])
    def test_franja_de(self, momento, esperada):
        assert franja_de(momento) == esperada


class TestDosPorDia:
    def test_cinco_cierres_por_la_mañana_hacen_un_respaldo(self, entorno):
        _, carpeta = entorno
        resultados = [_cerrar(entorno, h) for h in (_dia(7, 30), _dia(8, 10), _dia(9, 0), _dia(10, 30), _dia(11, 59, 59))]
        assert [r is not None for r in resultados] == [True, False, False, False, False]
        assert len(_respaldos(carpeta)) == 1
        assert _marcas(carpeta) == ["franja_2026-10-05_1.hecha"]

    def test_tres_cierres_por_la_tarde_se_suman_a_la_mañana_y_hacen_dos_en_el_dia(self, entorno):
        _, carpeta = entorno
        resultados = [_cerrar(entorno, h) for h in (_dia(8, 0), _dia(12, 0, 0), _dia(15, 0), _dia(18, 30))]
        assert [r is not None for r in resultados] == [True, True, False, False]
        assert len(_respaldos(carpeta)) == 2
        assert _marcas(carpeta) == ["franja_2026-10-05_1.hecha", "franja_2026-10-05_2.hecha"]

    def test_al_dia_siguiente_vuelven_a_hacerse(self, entorno):
        _, carpeta = entorno
        for momento in (_dia(8), _dia(14), _dia(8, dia=6)):
            assert _cerrar(entorno, momento) is not None
        assert _cerrar(entorno, _dia(9, dia=6)) is None
        assert len(_respaldos(carpeta)) == 3

    def test_las_11_59_59_y_las_12_00_00_caen_en_franjas_distintas(self, entorno):
        _, carpeta = entorno
        assert _cerrar(entorno, _dia(11, 59, 59)) is not None
        assert _cerrar(entorno, _dia(12, 0, 0)) is not None
        assert len(_respaldos(carpeta)) == 2

    def test_el_respaldo_se_nombra_con_la_hora_dada(self, entorno):
        ruta = _cerrar(entorno, _dia(9, 30, 5))
        assert os.path.basename(ruta) == "BaseDatosQA_2026-10-05_093005.db"

    def test_un_respaldo_de_otro_equipo_con_la_hora_adelantada_no_consume_la_franja(self, entorno):
        """La franja se lleva con marcas propias: una copia con nombre de mañana (u otro dia) no la consume."""
        _, carpeta = entorno
        os.makedirs(carpeta)
        for nombre in ("BaseDatosQA_2026-10-05_090000.db", "BaseDatosQA_2026-10-05_235959.db", "BaseDatosQA_2026-10-07_080000.db"):
            Path(carpeta, nombre).write_bytes(b"copia de otro equipo")
        ruta = _cerrar(entorno, _dia(9, 30))
        assert ruta is not None and os.path.basename(ruta) > "BaseDatosQA_2026-10-07_080000.db", "ordena despues de la copia adelantada (RB.0)"
        assert _cerrar(entorno, _dia(10, 0)) is None

    def test_una_marca_hecha_sin_ningun_respaldo_basta_para_no_hacer_otro(self, entorno):
        """Tampoco la libera el nombre: la franja esta hecha porque lo dice su marca, aunque nadie vea un respaldo con esa hora."""
        _, carpeta = entorno
        os.makedirs(carpeta)
        Path(carpeta, "franja_2026-10-05_1.hecha").write_text("hecha")
        assert _cerrar(entorno, _dia(9, 30)) is None
        assert _respaldos(carpeta) == []

    def test_la_carpeta_pre_migracion_no_cuenta(self, entorno):
        _, carpeta = entorno
        pre = Path(carpeta, "pre_migracion")
        pre.mkdir(parents=True)
        for nombre in ("BaseDatosQA_2026-10-05_081500.db", "BaseDatosQA_2026-10-05_081501.db"):
            (pre / nombre).write_bytes(b"respaldo previo a una migracion")
        assert _cerrar(entorno, _dia(9, 0)) is not None
        assert len(_respaldos(carpeta)) == 1
        assert sorted(os.listdir(str(pre))) == ["BaseDatosQA_2026-10-05_081500.db", "BaseDatosQA_2026-10-05_081501.db"]

    def test_el_respaldo_directo_no_se_limita_a_dos_por_dia(self, entorno):
        """El respaldo previo a una migracion (F1) llama a `respaldar_bd` y respalda siempre."""
        origen, carpeta = entorno
        for i in range(3):
            assert respaldar_bd(ruta_origen=origen, carpeta_destino=carpeta, ahora=_dia(9, i)) is not None
        assert len(_respaldos(carpeta)) == 3
        assert _marcas(carpeta) == []

    def test_una_fila_de_auditoria_por_respaldo_hecho_y_ninguna_por_cierre_sin_respaldo(self, entorno):
        origen, _ = entorno
        for h in (_dia(8), _dia(9), _dia(10), _dia(13), _dia(14)):
            _cerrar(entorno, h)
        assert len(_filas_de_auditoria(origen)) == 2

    def test_sin_la_base_de_origen_no_se_crea_ninguna_marca(self, tmp_path):
        carpeta = str(tmp_path / "respaldos_bd")
        assert respaldar_al_cerrar(ruta_origen=str(tmp_path / "no_existe.db"), carpeta_destino=carpeta, ahora=_dia(9)) is None
        assert not os.path.exists(carpeta)


# ------------------------------------------------------------------------------ una copia que falla no consume la franja
class TestSiFallaLaFranjaNoQuedaConsumida:
    def test_el_respaldo_falla_el_siguiente_cierre_reintenta(self, entorno, monkeypatch):
        _, carpeta = entorno
        monkeypatch.setattr(respaldo, "respaldar_bd", lambda *a, **k: None)
        assert _cerrar(entorno, _dia(9, 0)) is None
        assert _marcas(carpeta) == [], "ni `.hecha` ni un `.reclamo` colgado"
        monkeypatch.undo()
        assert _cerrar(entorno, _dia(9, 5)) is not None
        assert _marcas(carpeta) == ["franja_2026-10-05_1.hecha"]

    def test_una_excepcion_dentro_del_respaldo_tampoco_la_consume_ni_se_propaga(self, entorno, monkeypatch):
        _, carpeta = entorno

        def revienta(*a, **k):
            raise RuntimeError("fallo inesperado")

        monkeypatch.setattr(respaldo, "respaldar_bd", revienta)
        assert _cerrar(entorno, _dia(9, 0)) is None
        assert _marcas(carpeta) == []


# ---------------------------------------------------------------------------------------------- la edad de un reclamo
class TestElReclamo:
    def _con_reclamo(self, entorno_, segundos):
        _, carpeta = entorno_
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, "franja_2026-10-05_1.reclamo")
        Path(ruta).write_text("otro equipo")
        _envejecer(ruta, segundos)
        return ruta

    def test_un_reclamo_de_un_minuto_se_respeta(self, entorno):
        _, carpeta = entorno
        ruta = self._con_reclamo(entorno, 60)
        assert _cerrar(entorno, _dia(9, 0)) is None
        assert _respaldos(carpeta) == []
        assert os.path.exists(ruta), "el reclamo de otro no se toca"

    def test_un_reclamo_de_once_minutos_se_retoma(self, entorno):
        _, carpeta = entorno
        self._con_reclamo(entorno, 11 * 60)
        assert _cerrar(entorno, _dia(9, 0)) is not None
        assert len(_respaldos(carpeta)) == 1
        assert _marcas(carpeta) == ["franja_2026-10-05_1.hecha"]

    def test_la_edad_se_mide_con_el_reloj_del_servidor_no_con_el_de_este_equipo(self, entorno, monkeypatch):
        """Con el reloj de este equipo 10 horas adelantado, un reclamo de un minuto sigue siendo de un minuto y uno de once sigue siendo
        viejo: la edad sale de las fechas de modificacion del servidor, no de `time.time()`."""
        _, carpeta = entorno
        real = time.time
        reciente = self._con_reclamo(entorno, 60)
        monkeypatch.setattr(time, "time", lambda: real() + 10 * 3600)
        assert _cerrar(entorno, _dia(9, 0)) is None
        assert os.path.exists(reciente)
        os.remove(reciente)
        self._con_reclamo(entorno, 11 * 60)
        assert _cerrar(entorno, _dia(9, 1)) is not None

    def test_el_umbral_de_diez_minutos_se_prueba_en_su_borde(self, entorno):
        """F-08: 11 minutos contra 1 no distinguen un umbral de 10 minutos de uno de 100 ni de uno de 2: se prueba a ambos lados del borde."""
        _, carpeta = entorno
        ruta = self._con_reclamo(entorno, 590)
        assert _cerrar(entorno, _dia(9, 0)) is None, "a los 9 min 50 s sigue siendo de un cierre en curso"
        _envejecer(ruta, 610)
        assert _cerrar(entorno, _dia(9, 1)) is not None, "a los 10 min 10 s ya es de un cierre que se cayo"

    def test_un_reclamo_con_fecha_en_el_futuro_se_retoma_como_uno_viejo(self, entorno):
        """C2 de la revision: un reclamo huerfano con fecha de modificacion en el FUTURO (el reloj del servidor se corrio hacia atras)
        tenia una edad NEGATIVA, parecia reciente y bloqueaba la franja hasta que el reloj lo alcanzara (+10 minutos)."""
        _, carpeta = entorno
        self._con_reclamo(entorno, -3 * 3600)
        assert _cerrar(entorno, _dia(9, 0)) is not None
        assert _marcas(carpeta) == ["franja_2026-10-05_1.hecha"]

    def test_un_reclamo_apenas_en_el_futuro_se_respeta(self, entorno):
        """Una diferencia de reloj de un minuto no vuelve viejo al reclamo de otro cierre en curso."""
        _, carpeta = entorno
        ruta = self._con_reclamo(entorno, -60)
        assert _cerrar(entorno, _dia(9, 0)) is None
        assert os.path.exists(ruta)

    def test_un_archivo_ajeno_con_digitos_raros_no_detiene_los_respaldos(self, entorno):
        """H7 en `_reclamos_de` (segunda revision): `str.isdigit()` acepta '²' y `int('²')` lanza `ValueError`: un archivo
        `franja_<fecha>_1.reclamo.²` en la carpeta compartida hacia que el cierre devolviera None en esa franja mientras existiera."""
        _, carpeta = entorno
        os.makedirs(carpeta)
        Path(carpeta, "franja_2026-10-05_1.reclamo.²").write_text("ajeno")
        assert _cerrar(entorno, _dia(9, 0)) is not None
        assert respaldo._reclamos_de(carpeta, ("2026-10-05", 1)) == {}, "ese archivo no es un reclamo"

    def test_una_cadena_de_tres_generaciones_cuenta_la_ultima(self, entorno):
        """El reclamo `.reclamo.3` (el mas nuevo) es el que cuenta. Con las generaciones 1 y 2 viejas y la 3 de un minuto, la franja esta tomada; cuando
        la 3 tambien envejece, se retoma desde ELLA (generacion 4). Tomar la mas vieja (la 1) daria `None` en los dos casos: intentaria crear la 2, que existe."""
        _, carpeta = entorno
        os.makedirs(carpeta)
        rutas = {}
        for nombre, edad in (("franja_2026-10-05_1.reclamo", 3600), ("franja_2026-10-05_1.reclamo.2", 3000), ("franja_2026-10-05_1.reclamo.3", 60)):
            rutas[nombre] = os.path.join(carpeta, nombre)
            Path(rutas[nombre]).write_text("otro equipo")
            _envejecer(rutas[nombre], edad)
        assert _cerrar(entorno, _dia(9, 0)) is None, "la ultima generacion es reciente: otro cierre esta en curso"
        _envejecer(rutas["franja_2026-10-05_1.reclamo.3"], 700)
        assert _cerrar(entorno, _dia(9, 1)) is not None, "la ultima generacion ya es vieja: se retoma desde ella"


# ------------------------------------------------------- la franja sale del reloj del SERVIDOR (C1 / F-01 de la revision)
def _reloj_local(momento):
    """El `datetime` del modulo, con la hora LOCAL de un equipo fijada en `momento` (para probar que la franja no sale de ella)."""
    class _Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(momento.year, momento.month, momento.day, momento.hour, momento.minute, momento.second)
    return _Reloj


def _epoch(momento):
    """El instante del SERVIDOR para una hora de Colombia (UTC-5, escrito AQUI y no leido de `respaldo.ZONA_DEL_SERVICIO`: derivarlo de la constante
    que se prueba haria invisible un cambio de zona): no depende de la zona horaria del equipo que corre la prueba."""
    return momento.replace(tzinfo=timezone(timedelta(hours=-5))).timestamp()


class TestLaFranjaSaleDelRelojDelServidor:
    """Los equipos de la red no comparten reloj. Con el de cada equipo, uno adelantado consumia por adelantado la franja de OTRO dia (o de
    otra mitad del dia) y los cierres reales de esa franja no respaldaban nada, sin ningun aviso; y con relojes que caen a lados distintos de
    las 12:00 salian dos copias en el mismo instante real. La franja y el nombre del respaldo salen ahora del reloj del servidor."""

    def test_sin_ahora_la_franja_y_el_nombre_salen_del_reloj_del_servidor(self, entorno, monkeypatch):
        origen, carpeta = entorno
        monkeypatch.setattr(respaldo, "datetime", _reloj_local(_dia(20, 0)))                          # este equipo: las 20:00 (franja 2)
        monkeypatch.setattr(respaldo, "_reloj_del_servidor", lambda c: _epoch(_dia(8, 15)))      # el servidor: las 08:15 (franja 1)
        ruta = respaldar_al_cerrar(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta)
        assert os.path.basename(ruta) == "BaseDatosQA_2026-10-05_081500.db"
        assert _marcas(carpeta) == ["franja_2026-10-05_1.hecha"]

    def test_equipos_con_el_reloj_distinto_se_ponen_de_acuerdo_en_la_franja(self, entorno, monkeypatch):
        """F-01: tres equipos cierran en el mismo instante real (para el servidor, las 11:55): uno con la hora bien, uno una hora adelantado
        (ya en la franja de la tarde) y uno cuyo reloj ya paso la medianoche. Solo el primero respalda."""
        origen, carpeta = entorno
        monkeypatch.setattr(respaldo, "_reloj_del_servidor", lambda c: _epoch(_dia(11, 55)))
        resultados = []
        for local in (_dia(11, 50), _dia(12, 50), _dia(0, 50, dia=6)):
            monkeypatch.setattr(respaldo, "datetime", _reloj_local(local))
            resultados.append(respaldar_al_cerrar(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta))
        assert [r is not None for r in resultados] == [True, False, False]
        assert _marcas(carpeta) == ["franja_2026-10-05_1.hecha"]
        assert len(_respaldos(carpeta)) == 1

    def test_si_no_se_puede_leer_el_reloj_del_servidor_se_usa_el_de_este_equipo(self, entorno, monkeypatch):
        origen, carpeta = entorno

        def sin_reloj(carpeta_):
            raise OSError(errno.EACCES, "sin permiso para crear la sonda")

        monkeypatch.setattr(respaldo, "_reloj_del_servidor", sin_reloj)
        monkeypatch.setattr(respaldo, "datetime", _reloj_local(_dia(9, 30)))
        ruta = respaldar_al_cerrar(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta)
        assert ruta is not None and os.path.basename(ruta) == "BaseDatosQA_2026-10-05_093000.db"

    def test_con_ahora_la_hora_dada_manda_sobre_el_servidor(self, entorno, monkeypatch):
        """`ahora` (las pruebas, RB.0) fija la hora de la franja y del nombre: no se le pide la hora al servidor. (La edad de las marcas
        si se mide con su reloj: eso es otra consulta.)"""
        monkeypatch.setattr(respaldo, "_hora_segun_el_servidor", lambda c: pytest.fail("no se debe pedir la hora al servidor"))
        assert os.path.basename(_cerrar(entorno, _dia(9, 30, 5))) == "BaseDatosQA_2026-10-05_093005.db"

    @pytest.mark.skipif(not hasattr(time, "tzset"), reason="`time.tzset` solo existe en Unix")
    @pytest.mark.parametrize("zona", ["America/Bogota", "UTC", "Asia/Tokyo", "America/New_York", "Europe/Madrid"])
    def test_la_franja_no_depende_de_la_zona_horaria_del_equipo(self, entorno, zona):
        """A-1 de la segunda revision: C1 cambiaba la dependencia del RELOJ de cada equipo por la de su ZONA HORARIA (`datetime.fromtimestamp` usa la del SO):
        el mismo instante del servidor caia en franjas distintas segun la zona (dos copias a la vez, o la franja de la tarde consumida antes de las 12:00
        reales). Ahora se lee en la zona del servicio: 11:55 del servidor es la franja 1 y el mismo nombre desde cualquier zona."""
        origen, carpeta = entorno
        anterior = os.environ.get("TZ")
        os.environ["TZ"] = zona
        time.tzset()
        real = respaldo._reloj_del_servidor
        respaldo._reloj_del_servidor = lambda c: _epoch(_dia(11, 55))
        try:
            ruta = respaldar_al_cerrar(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta)
        finally:
            respaldo._reloj_del_servidor = real
            if anterior is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = anterior
            time.tzset()
        assert ruta is not None and os.path.basename(ruta) == "BaseDatosQA_2026-10-05_115500.db"
        assert _marcas(carpeta) == ["franja_2026-10-05_1.hecha"]

    def test_la_zona_del_servicio_es_utc_menos_5(self):
        """Colombia: UTC-5 todo el año, sin horario de verano (el desfase fijo no puede fallar, a diferencia de una base de zonas horarias)."""
        assert respaldo.ZONA_DEL_SERVICIO.utcoffset(None) == timedelta(hours=-5)

    @pytest.mark.parametrize("valor", [float("nan"), float("inf"), -1e18, 1e20])
    def test_un_sello_absurdo_del_servidor_cae_a_la_hora_de_este_equipo_sin_lanzar(self, entorno, monkeypatch, valor):
        _, carpeta = entorno
        monkeypatch.setattr(respaldo, "_reloj_del_servidor", lambda c: valor)
        monkeypatch.setattr(respaldo, "datetime", _reloj_local(_dia(9, 30)))
        assert respaldo._hora_segun_el_servidor(carpeta) == _dia(9, 30)

    def test_la_sonda_del_reloj_se_crea_dentro_de_la_carpeta_compartida(self, entorno, monkeypatch):
        """A-3 de la segunda revision: la fecha de la sonda la pone el SERVIDOR solo si la sonda vive en su carpeta. Con la sonda en el directorio de
        trabajo, en el temporal del sistema o en la carpeta padre, todas las demas pruebas pasaban igual (en ellas servidor y equipo son el mismo disco)
        y C1 quedaba sin efecto en produccion."""
        _, carpeta = entorno
        os.makedirs(carpeta)
        vistos = []
        stat_real = os.stat

        def espia(p, *a, **k):
            vistos.append(str(p))
            return stat_real(p, *a, **k)

        monkeypatch.setattr(os, "stat", espia)
        respaldo._reloj_del_servidor(carpeta)
        sondas = [p for p in vistos if "sonda" in os.path.basename(p)]
        assert sondas, "no se midio ninguna sonda"
        assert all(os.path.dirname(p) == carpeta for p in sondas), sondas

    def test_cada_sonda_lleva_su_propio_nombre(self, entorno, monkeypatch):
        """C-5: dos cierres a la vez en la carpeta compartida no pueden pisarse la sonda (si el nombre fuera fijo, uno leeria el sello del otro)."""
        _, carpeta = entorno
        os.makedirs(carpeta)
        monkeypatch.setattr(respaldo, "_quitar", lambda ruta: None)           # las sondas no se retiran: quedan a la vista
        respaldo._reloj_del_servidor(carpeta)
        respaldo._reloj_del_servidor(carpeta)
        assert len([n for n in os.listdir(carpeta) if "sonda" in n]) == 2

    def test_el_primer_cierre_con_la_carpeta_sin_crear_usa_la_sonda_real_y_su_hora(self, entorno, monkeypatch):
        """C-5 (el camino de PRODUCCION de `closeEvent`: `ahora=None`, la carpeta aun no existe y la sonda es de verdad): la hora que lleva el nombre es la del
        sello de la sonda, no la del reloj de este equipo. Si `ahora` se calculara antes de crear la carpeta, la sonda no podria crearse y se usaria la hora local."""
        origen, carpeta = entorno
        assert not os.path.exists(carpeta)
        stat_real = os.stat

        class _Sello:
            def __init__(self, st_mtime):
                self.st_mtime = st_mtime

        def stat_con_la_sonda_tres_horas_adelantada(p, *a, **k):
            if "sonda" in os.path.basename(str(p)):
                return _Sello(stat_real(p, *a, **k).st_mtime + 3 * 3600)
            return stat_real(p, *a, **k)

        monkeypatch.setattr(os, "stat", stat_con_la_sonda_tres_horas_adelantada)
        ruta = respaldar_al_cerrar(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta)
        assert ruta is not None
        marca = datetime.strptime(os.path.basename(ruta)[len("BaseDatosQA_"):][:17], "%Y-%m-%d_%H%M%S")
        esperada = datetime.fromtimestamp(time.time() + 3 * 3600, tz=respaldo.ZONA_DEL_SERVICIO).replace(tzinfo=None)
        assert abs((marca - esperada).total_seconds()) < 300, (marca, esperada)

    def test_el_nombre_del_provisional_que_se_genera_es_el_que_la_limpieza_reconoce(self):
        """C-5: un contrato entre dos piezas: el nombre que genera `_nombre_provisional` (y sus laterales de SQLite) tiene que ser lo que
        `_es_provisional` reconoce, o la limpieza dejaria los provisionales huerfanos para siempre."""
        destino = "/carpeta/BaseDatosQA_2026-10-05_120000.db"
        nombre = os.path.basename(respaldo._nombre_provisional(destino))
        assert respaldo._es_provisional(nombre)
        for lateral in respaldo.SUFIJOS_LATERALES:
            assert respaldo._es_provisional(nombre + lateral), lateral
        assert not respaldo._es_provisional("notas.db.parcial")
        assert not respaldo._es_provisional(os.path.basename(destino))
        assert not respaldo._es_provisional(os.path.basename(destino) + ".revisar")


# ------------------------------------------ la creacion del reclamo es EXCLUSIVA (C-1 de la segunda revision)
class TestLaCreacionDelReclamoEsExclusiva:
    @pytest.mark.parametrize("sufijo", [".reclamo", ".reclamo.2"], ids=["nuevo", "retoma"])
    def test_el_competidor_que_llega_entre_la_comprobacion_y_la_creacion_gana(self, entorno, monkeypatch, sufijo):
        """Intercalado determinista que faltaba: el cierre A crea el reclamo JUSTO antes de que B llame a `os.open`. Los tres intercalados de arriba prueban que un
        reclamo que YA existe se respeta, y eso lo cumple cualquier `if exists`: una `_crear_exclusivo` que comprobara `exists` y abriera SIN `O_EXCL` sobrevivia
        (solo la prueba de 8 procesos la atrapaba, y solo a veces). Aqui solo la creacion exclusiva detecta que A llego primero."""
        origen, carpeta = entorno
        os.makedirs(carpeta)
        if sufijo == ".reclamo.2":
            viejo = os.path.join(carpeta, "franja_2026-10-05_1.reclamo")
            Path(viejo).write_text("de un cierre que se cayo")
            _envejecer(viejo, 20 * 60)
        real = os.open

        def a_llega_justo_antes(p, *a, **k):
            if str(p).endswith(sufijo) and not os.path.exists(p):
                Path(p).write_text("A")
            return real(p, *a, **k)

        monkeypatch.setattr(os, "open", a_llega_justo_antes)
        assert respaldar_al_cerrar(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, ahora=_dia(9, 0)) is None
        assert _respaldos(carpeta) == [], "B no hizo ninguna copia: el reclamo era de A"

    def test_crear_exclusivo_no_pisa_un_archivo_que_ya_existe_aunque_no_se_vea(self, tmp_path, monkeypatch):
        """La exclusividad la da el sistema operativo (`O_CREAT | O_EXCL`), no una consulta previa: aunque `os.path.exists` diga que no esta, no se pisa."""
        ruta = str(tmp_path / "franja_2026-10-05_1.reclamo")
        Path(ruta).write_text("de otro")
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        assert respaldo._crear_exclusivo(ruta, "mio") is False
        assert Path(ruta).read_text() == "de otro"


# -------------------------------------------------------------- sin permiso sobre la carpeta (E1 / F-11 de la revision)
class TestSinPermisoSobreLaCarpeta:
    @pytest.mark.skipif(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                        reason="como administrador (o en Windows) `chmod` no impide escribir")
    def test_una_carpeta_de_solo_lectura_avisa_y_no_lanza(self, entorno, capsys):
        """E1: sin permiso, `respaldar_al_cerrar` no hacia nada y NO dejaba ni un mensaje (el `PermissionError` se tomaba por 'ocupado'):
        un respaldo imposible de forma permanente quedaba invisible."""
        _, carpeta = entorno
        os.makedirs(carpeta)
        os.chmod(carpeta, 0o555)
        try:
            assert _cerrar(entorno, _dia(9, 0)) is None
        finally:
            os.chmod(carpeta, 0o755)
        assert "sin permiso para crear" in capsys.readouterr().out
        assert _marcas(carpeta) == [] and _respaldos(carpeta) == []

    def test_un_permission_error_sin_el_archivo_avisa_por_consola(self, tmp_path, monkeypatch, capsys):
        """C-6 de la segunda revision: la rama de E1 no puede depender de `chmod` (que no impide escribir como administrador ni en Windows): aqui el
        sistema niega la creacion y el archivo no existe. (Por consola: en el .exe sin consola el aviso no se ve; deuda DP-153.)"""
        ruta = str(tmp_path / "franja_2026-10-05_1.reclamo")

        def negado(p, *a, **k):
            raise PermissionError(errno.EACCES, "sin permiso")

        monkeypatch.setattr(os, "open", negado)
        assert respaldo._crear_exclusivo(ruta, "x") is False
        assert "sin permiso para crear" in capsys.readouterr().out

    def test_un_permission_error_con_el_archivo_presente_es_ocupado_y_no_alarma(self, tmp_path, monkeypatch, capsys):
        """En Windows, un archivo con borrado pendiente da `PermissionError` al crearlo: es 'ocupado', no falta de permiso."""
        ruta = str(tmp_path / "franja_2026-10-05_1.reclamo")
        Path(ruta).write_text("de otro")
        real = os.open

        def negado(p, *a, **k):
            if p == ruta:
                raise PermissionError(errno.EACCES, "borrado pendiente")
            return real(p, *a, **k)

        monkeypatch.setattr(os, "open", negado)
        assert respaldo._crear_exclusivo(ruta, "x") is False
        assert "sin permiso" not in capsys.readouterr().out

    def test_un_error_de_disco_al_crear_las_marcas_no_se_propaga(self, entorno, monkeypatch):
        """F-11: el camino de error de un disco lleno (o la red caida): el cierre no lanza y la franja no queda a medias."""
        _, carpeta = entorno
        real = os.open

        def lleno(p, *a, **k):
            if str(p).endswith(".reclamo"):
                raise OSError(errno.ENOSPC, "No space left on device")
            return real(p, *a, **k)

        monkeypatch.setattr(os, "open", lleno)
        assert _cerrar(entorno, _dia(9, 0)) is None
        assert _marcas(carpeta) == [] and _respaldos(carpeta) == []


# ------------------------------------------- una fila que viola una restriccion no rompe el limite de dos por dia (B-02 de la segunda revision)
class TestConUnaFilaQueViolaUnaRestriccion:
    def test_los_cierres_siguen_haciendo_a_lo_sumo_uno_por_franja(self, tmp_path):
        """Con `integrity_check` tomando por DAÑO una fila que viola un CHECK, ningun cierre daba respaldo, la franja no se consumia y se hacia UNA COPIA COMPLETA
        POR CIERRE (a una `.revisar`): se anulaba el limite de dos por dia justo cuando no se producia ningun respaldo."""
        origen = str(tmp_path / "BaseDatosQA.db")
        con = sqlite3.connect(origen)
        con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v INTEGER CHECK (v >= 0))")
        con.executemany("INSERT INTO t (v) VALUES (?)", [(i,) for i in range(20)])
        con.execute("PRAGMA ignore_check_constraints = ON")
        con.execute("INSERT INTO t (v) VALUES (-5)")
        con.commit()
        con.close()
        carpeta = str(tmp_path / "respaldos_bd")
        resultados = [respaldar_al_cerrar(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, ahora=h)
                      for h in (_dia(8), _dia(9), _dia(10), _dia(13), _dia(14), _dia(15))]
        assert [r is not None for r in resultados] == [True, False, False, True, False, False]
        assert len(_respaldos(carpeta)) == 2
        assert [n for n in os.listdir(carpeta) if n.endswith(".revisar")] == []


# --------------------------------------------------------------------- el cierre propaga sus parametros (F-07 de la revision)
class TestElCierrePropagaSusParametros:
    def test_el_usuario_y_el_maximo_de_copias_llegan_al_respaldo(self, entorno):
        """F-07: el rastro de QUIEN hizo el respaldo (`usuario`) y el tope de copias (`max_copias`) pasan de `respaldar_al_cerrar` a
        `respaldar_bd`; se podian perder sin que nada fallara."""
        origen, carpeta = entorno
        os.makedirs(carpeta)
        for i in range(4):
            Path(carpeta, f"BaseDatosQA_2026-10-0{i + 1}_080000.db").write_bytes(b"copia vieja")
        ruta = respaldar_al_cerrar(usuario="Dra. Mesa", ruta_origen=origen, carpeta_destino=carpeta, max_copias=2, ahora=_dia(9))
        assert ruta is not None
        assert len(_respaldos(carpeta)) == 2, "`max_copias` llega a la rotacion"
        con = sqlite3.connect(origen)
        try:
            usuarios = [u for (u,) in con.execute("SELECT usuario FROM audit_log WHERE tabla = 'backup'")]
        finally:
            con.close()
        assert usuarios == ["Dra. Mesa"], "el nombre de quien respalda llega a la auditoria"


# ------------------------------------------------------------------------------------ intercalados deterministas
class TestIntercaladosDeterministas:
    def test_B_mira_A_termina_y_deja_su_hecha_B_reclama_y_desiste(self, entorno, monkeypatch):
        """B mira (no hay `.hecha`), A hace su copia y deja la `.hecha`, B reclama (el reclamo de A ya no esta): B vuelve a mirar y
        desiste, suelta su reclamo y no hace una segunda copia."""
        _, carpeta = entorno
        resultados = {}

        def gancho():
            monkeypatch.delitem(respaldo._GANCHOS, "tras_mirar_hecha")
            resultados["A"] = _cerrar(entorno, _dia(9, 0))

        monkeypatch.setitem(respaldo._GANCHOS, "tras_mirar_hecha", gancho)
        resultados["B"] = _cerrar(entorno, _dia(9, 0))
        assert resultados["A"] is not None and resultados["B"] is None
        assert len(_respaldos(carpeta)) == 1
        assert _marcas(carpeta) == ["franja_2026-10-05_1.hecha"], "ni un reclamo colgado"
        assert len(_filas_de_auditoria(entorno[0])) == 1

    def test_dos_cierres_ven_el_mismo_reclamo_viejo_solo_uno_lo_retoma(self, entorno, monkeypatch):
        """B y A ven el MISMO reclamo viejo. A lo retoma (crea la generacion siguiente) y sigue trabajando; B, que se quedo justo
        antes de retomar, intenta lo mismo: la creacion exclusiva se lo impide."""
        _, carpeta = entorno
        os.makedirs(carpeta)
        viejo = os.path.join(carpeta, "franja_2026-10-05_1.reclamo")
        Path(viejo).write_text("equipo que se cayo")
        _envejecer(viejo, 20 * 60)
        resultados = {}
        # F-06 de la revision: una asercion DENTRO de un gancho la traga el `except Exception` del codigo bajo prueba (y B daria `None`
        # justo como la prueba espera): una sincronizacion rota pasaria en vacio. Los fallos de sincronizacion se anotan aqui y se
        # exigen vacios al final.
        fallos = []
        b_esta_en_el_punto, a_tiene_el_reclamo, b_termino = threading.Event(), threading.Event(), threading.Event()

        def en_antes_de_retomar():
            if threading.current_thread().name == "cierre_B":
                b_esta_en_el_punto.set()
                if not a_tiene_el_reclamo.wait(20):
                    fallos.append("A no llego a retomar el reclamo")

        def en_tras_reclamar():
            if threading.current_thread().name == "cierre_A":
                a_tiene_el_reclamo.set()
                if not b_termino.wait(20):
                    fallos.append("B no termino su intento")

        monkeypatch.setitem(respaldo._GANCHOS, "antes_de_retomar", en_antes_de_retomar)
        monkeypatch.setitem(respaldo._GANCHOS, "tras_reclamar", en_tras_reclamar)

        def cierre(nombre, esperar=None):
            if esperar is not None and not esperar.wait(20):
                fallos.append("B no llego al punto de retomar el reclamo")
                return
            resultados[nombre] = _cerrar(entorno, _dia(9, 0))
            if nombre == "B":
                b_termino.set()

        hilo_b = threading.Thread(target=cierre, args=("B",), name="cierre_B")
        hilo_a = threading.Thread(target=cierre, args=("A", b_esta_en_el_punto), name="cierre_A")
        hilo_b.start()
        hilo_a.start()
        hilo_b.join(40)
        hilo_a.join(40)
        assert not hilo_a.is_alive() and not hilo_b.is_alive()
        assert not fallos, fallos
        assert resultados["B"] is None and resultados["A"] is not None
        assert len(_respaldos(carpeta)) == 1, "dos cierres retomaron el mismo reclamo viejo y hicieron dos copias"
        assert _marcas(carpeta) == ["franja_2026-10-05_1.hecha"]

    def test_un_dueño_lento_al_que_retomaron_su_reclamo_no_rompe_la_marca(self, entorno, monkeypatch):
        """El cierre que tardo mas de 10 minutos termina despues de que otro retomo su reclamo: la franja queda marcada y no queda
        ningun reclamo colgado (se acepta una segunda copia, declarada en el plan)."""
        _, carpeta = entorno
        resultados = {}

        def gancho():
            monkeypatch.delitem(respaldo._GANCHOS, "antes_de_respaldar")
            for ruta in respaldo._reclamos_de(carpeta, ("2026-10-05", 1)).values():
                _envejecer(ruta, 20 * 60)                       # el reclamo de A "tiene 20 minutos"
            resultados["B"] = _cerrar(entorno, _dia(9, 5))      # B lo retoma y hace su copia

        monkeypatch.setitem(respaldo._GANCHOS, "antes_de_respaldar", gancho)
        resultados["A"] = _cerrar(entorno, _dia(9, 0))
        assert resultados["A"] is not None and resultados["B"] is not None
        assert len(_respaldos(carpeta)) == 2
        assert _marcas(carpeta) == ["franja_2026-10-05_1.hecha"]


_HIJO = r'''
import json, os, sys, time
from datetime import datetime
sys.path.insert(0, sys.argv[1])
from services.respaldo import respaldar_al_cerrar
origen, carpeta, ir = sys.argv[2], sys.argv[3], sys.argv[4]
print("listo", flush=True)
while not os.path.exists(ir):
    time.sleep(0.001)
r = respaldar_al_cerrar(usuario="Fisico", ruta_origen=origen, carpeta_destino=carpeta, ahora=datetime(2026, 10, 5, 9, 30, 0))
print(json.dumps(os.path.basename(r) if r else None), flush=True)
'''


class TestOchoProcesosAlMismoTiempo:
    """PRUEBA DE HUMO (F-05 de la revision): 8 procesos reales a la vez. NO fija ninguna carrera concreta -- con bases pequeñas la copia dura
    milisegundos y la carrera puede no ocurrir --: pasa tambien sin la creacion exclusiva y sin la segunda mirada. Esas carreras las fijan
    los intercalados deterministas de arriba y `TestLaCreacionDelReclamoEsExclusiva` (mutaciones MC3, MC4 y MC5); esta solo comprueba que el conjunto real no deja dos copias ni
    marcas a medias."""

    def _carrera(self, tmp_path, entorno_, con_reclamo_viejo):
        origen, carpeta = entorno_
        os.makedirs(carpeta, exist_ok=True)
        if con_reclamo_viejo:
            viejo = os.path.join(carpeta, "franja_2026-10-05_1.reclamo")
            Path(viejo).write_text("equipo que se cayo")
            _envejecer(viejo, 30 * 60)
        ir = str(tmp_path / "ir")
        env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
        hijos = [subprocess.Popen([sys.executable, "-c", _HIJO, RAIZ_REPO, origen, carpeta, ir],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=RAIZ_REPO) for _ in range(8)]
        try:
            for h in hijos:
                assert h.stdout.readline().strip() == "listo"
            Path(ir).write_text("ya")
            salidas = []
            for h in hijos:
                salida, error = h.communicate(timeout=LIMITE_S)
                assert h.returncode == 0, error[-1500:]
                salidas.append(json.loads([l for l in salida.strip().splitlines() if l.strip()][-1]))
        finally:
            for h in hijos:
                if h.poll() is None:
                    h.kill()
        return salidas, carpeta

    @pytest.mark.parametrize("con_reclamo_viejo", [False, True], ids=["franja_vacia", "con_un_reclamo_viejo"])
    def test_exactamente_un_respaldo_y_ninguna_marca_a_medias(self, tmp_path, entorno, con_reclamo_viejo):
        salidas, carpeta = self._carrera(tmp_path, entorno, con_reclamo_viejo)
        assert sum(1 for s in salidas if s is not None) == 1, salidas
        assert len(_respaldos(carpeta)) == 1
        assert _marcas(carpeta) == ["franja_2026-10-05_1.hecha"]
        assert [n for n in os.listdir(carpeta) if n.endswith(".parcial")] == []


# ------------------------------------------------------------------------------------------------------ la limpieza
class TestLimpiezaDeMarcas:
    def test_las_marcas_viejas_y_los_provisionales_huerfanos_se_retiran_y_lo_reciente_se_conserva(self, entorno):
        _, carpeta = entorno
        os.makedirs(carpeta)
        dias = 24 * 3600
        archivos = {                                                   # nombre: edad en segundos
            "franja_2026-09-20_1.hecha": 8 * dias,                     # se retira
            "franja_2026-09-20_2.reclamo": 8 * dias,                   # se retira
            "franja_2026-09-20_2.reclamo.2": 8 * dias,                 # se retira
            "franja_sonda_abc.tmp": 2 * dias,                          # se retira
            "BaseDatosQA_2026-10-01_090000.db.parcial": 2 * dias,      # se retira
            "franja_2026-10-04_2.hecha": 1 * dias,                     # se conserva
            "BaseDatosQA_2026-10-05_080000.db.parcial": 3600,          # se conserva (es de hace una hora)
            "notas.txt": 30 * dias,                                    # ajeno: no se toca
            "BaseDatosQA_00_copia_manual.db": 30 * dias,               # ajeno: no se toca
            # F-08: los umbrales se prueban a ambos lados de su borde (con margenes enormes sobreviven umbrales equivocados)
            "franja_2026-09-28_1.hecha": 6 * dias + 23 * 3600,         # se conserva: aun no cumple los 7 dias
            "franja_2026-09-27_2.hecha": 7 * dias + 3600,              # se retira: ya paso de los 7 dias
            "BaseDatosQA_2026-10-05_070000.db.4242-0a1b2c3d.parcial": 23 * 3600,        # se conserva: aun no cumple el dia
            # H6: los provisionales con nombre propio (`<respaldo>.<pid>-<aleatorio>.parcial`) y sus laterales de SQLite
            "BaseDatosQA_2026-10-01_090000.db.4242-0a1b2c3d.parcial": 25 * 3600,        # se retira: mas de un dia
            "BaseDatosQA_2026-10-01_090000.db.4242-0a1b2c3d.parcial-journal": 25 * 3600,  # se retira: su lateral
            "BaseDatosQA_2026-10-01_090000.db.4242-0a1b2c3d.parcial-wal": 25 * 3600,      # se retira: su lateral
            "BaseDatosQA_2026-10-01_090000.db.4242-0a1b2c3d.parcial-shm": 25 * 3600,      # se retira: su lateral
            "franja_2026-09-20_1.reclamo.3": 8 * dias,                 # se retira: una cadena de tres generaciones
            "notas.db.parcial": 30 * dias,                             # ajeno (no es un provisional de un respaldo): no se toca
        }
        for nombre, edad in archivos.items():
            ruta = os.path.join(carpeta, nombre)
            Path(ruta).write_bytes(b"x")
            _envejecer(ruta, edad)
        assert _cerrar(entorno, _dia(9, 0)) is not None
        quedan = set(os.listdir(carpeta))
        for retirado in ("franja_2026-09-20_1.hecha", "franja_2026-09-20_2.reclamo", "franja_2026-09-20_2.reclamo.2",
                         "franja_sonda_abc.tmp", "BaseDatosQA_2026-10-01_090000.db.parcial", "franja_2026-09-27_2.hecha",
                         "BaseDatosQA_2026-10-01_090000.db.4242-0a1b2c3d.parcial",
                         "BaseDatosQA_2026-10-01_090000.db.4242-0a1b2c3d.parcial-journal",
                         "BaseDatosQA_2026-10-01_090000.db.4242-0a1b2c3d.parcial-wal",
                         "BaseDatosQA_2026-10-01_090000.db.4242-0a1b2c3d.parcial-shm", "franja_2026-09-20_1.reclamo.3"):
            assert retirado not in quedan, retirado
        for conservado in ("franja_2026-10-04_2.hecha", "BaseDatosQA_2026-10-05_080000.db.parcial", "notas.txt",
                           "BaseDatosQA_00_copia_manual.db", "franja_2026-10-05_1.hecha", "franja_2026-09-28_1.hecha",
                           "BaseDatosQA_2026-10-05_070000.db.4242-0a1b2c3d.parcial", "notas.db.parcial"):
            assert conservado in quedan, conservado

    def test_la_limpieza_mide_la_edad_con_el_reloj_del_servidor_no_con_el_de_este_equipo(self, entorno, monkeypatch):
        """C-5: con el reloj de ESTE equipo 30 dias adelantado, una marca y un provisional recientes siguen siendo recientes (la edad sale del servidor)."""
        _, carpeta = entorno
        os.makedirs(carpeta)
        recientes = {"franja_2026-10-04_2.hecha": 86400, "BaseDatosQA_2026-10-05_070000.db.4242-0a1b2c3d.parcial": 3600}
        for nombre, edad in recientes.items():
            ruta = os.path.join(carpeta, nombre)
            Path(ruta).write_bytes(b"x")
            _envejecer(ruta, edad)
        real = time.time
        monkeypatch.setattr(time, "time", lambda: real() + 30 * 24 * 3600)
        assert _cerrar(entorno, _dia(9, 0)) is not None
        for nombre in recientes:
            assert nombre in os.listdir(carpeta), nombre

    def test_la_sonda_del_reloj_no_deja_rastro(self, entorno):
        _, carpeta = entorno
        _cerrar(entorno, _dia(9, 0))
        assert [n for n in os.listdir(carpeta) if "sonda" in n] == []


# -------------------------------------------------------------------------------------- el cierre real de la ventana
class TestElCierreDeLaVentana:
    @staticmethod
    def _llamadas_de_close_event():
        import textwrap
        import ui.mainpages as mainpages_mod
        arbol = ast.parse(textwrap.dedent(inspect.getsource(mainpages_mod.MainWindow.closeEvent)))
        nombres = set()
        for n in ast.walk(arbol):
            if isinstance(n, ast.Call):
                nombres.add(n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", ""))
        return nombres

    def test_close_event_pide_el_respaldo_por_franja_y_no_el_respaldo_directo(self):
        llamadas = self._llamadas_de_close_event()
        assert "respaldar_al_cerrar" in llamadas
        assert "respaldar_bd" not in llamadas

    def test_nadie_mas_en_produccion_llama_a_respaldar_al_cerrar(self):
        """Solo `closeEvent` aplica la regla de las franjas; el respaldo previo a una migracion (F1) sigue siendo directo."""
        quien = []
        for raiz, _, archivos in os.walk(RAIZ_REPO):
            if any(p in raiz for p in (os.sep + ".venv", os.sep + "tests", os.sep + "build", "__pycache__")):
                continue
            for a in archivos:
                if a.endswith(".py"):
                    ruta = os.path.join(raiz, a)
                    with open(ruta, encoding="utf-8") as f:
                        if "respaldar_al_cerrar(" in f.read():
                            quien.append(os.path.relpath(ruta, RAIZ_REPO))
        assert sorted(quien) == ["services/respaldo.py", "ui/mainpages.py"]


# --------------------------------------------------------------------------------------------- con datos reales
class TestConLasMarcasReales:
    def test_la_regla_aplicada_a_las_39_marcas_de_produccion_da_25_respaldos(self, tmp_path):
        """M9: los 39 respaldos reales (carpeta de red, 12-08 al 14-09-2026, del `audit_log` de la copia de produccion del 14-09)
        con la regla de una copia por franja habrian sido 25, y ningun dia pasa de dos. Se aplica la funcion REAL a cada cierre."""
        from _bd_referencia import BD_REBUILD_14_09
        if not os.path.isfile(str(BD_REBUILD_14_09)):
            pytest.skip("la copia de produccion del 14-09 no esta en esta maquina (HI-0)")
        copia = str(tmp_path / "produccion_14_09.db")
        shutil.copy2(str(BD_REBUILD_14_09), copia)                        # nunca se abre la BD de referencia: se copia primero
        con = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
        try:
            marcas = [datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") for ts, detalle in
                      con.execute("SELECT timestamp, detalle FROM audit_log WHERE tabla = 'backup' ORDER BY id")
                      if "VARIANDB" in (detalle or "").upper()]
        finally:
            con.close()
        assert len(marcas) == 39, "la copia de referencia ya no trae los 39 respaldos medidos en M9"
        origen = str(tmp_path / "BaseDatosQA.db")
        _bd(origen)
        carpeta = str(tmp_path / "respaldos_bd")
        hechos = [m for m in marcas if respaldar_al_cerrar(ruta_origen=origen, carpeta_destino=carpeta, ahora=m) is not None]
        assert len(hechos) == 25
        por_dia = {}
        for m in hechos:
            por_dia[m.date()] = por_dia.get(m.date(), 0) + 1
        assert max(por_dia.values()) == 2
