"""RB.0 (PLAN_GUARDADO_SIN_ESPESOR_Y_RESPALDOS_05-10.md, DP-150): el respaldo no puede dejar colgado el cierre de la aplicacion.

Defecto vivo (medido en M13): `respaldar_bd` buscaba un nombre que ordenara DESPUES de todos los respaldos existentes y, si no lo
lograba, le sumaba un contador (`_02`, `_03`...) a la hora de ESTE equipo. Con una copia de hora POSTERIOR en la carpeta -- otro equipo
con el reloj 2 s adelantado que cerro antes, o cualquier archivo que alguien deje con el prefijo `BaseDatosQA_` -- ningun contador la
alcanza y `while nombre <= tope` no terminaba nunca: `closeEvent` no llegaba a `event.accept()` y la aplicacion quedaba sin cerrar, a CPU
plena. La carpeta es compartida por todos los equipos (`\\\\VARIANDB\\...\\respaldos_bd`).

Contrato nuevo:
  - solo cuenta como respaldo un nombre con la forma EXACTA `BaseDatosQA_AAAA-MM-DD_HHMMSS.db` o `..._NN.db` (con una fecha real): un
    archivo ajeno ni se rota ni decide el nombre del respaldo nuevo;
  - el nombre se decide en UN paso, sin bucle, y es SIEMPRE posterior al ultimo existente;
  - `ahora=None` (por omision, la hora de este equipo, como antes) permite fijar la hora en las pruebas y en RB.2.

Un bucle infinito no se prueba esperandolo: cada caso de "termina" corre en un PROCESO aparte con limite de tiempo.
"""
import ast
import inspect
import json
import os
import random
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta

import pytest

from services import respaldo
from services.respaldo import MAX_RESPALDOS, PREFIJO_RESPALDO, respaldar_bd

RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMITE_S = 25          # el respaldo real tarda milisegundos; casi todo el limite es el arranque del interprete y de PyQt


def _bd(ruta, filas=3):
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE datos (id INTEGER PRIMARY KEY, valor TEXT)")
    con.executemany("INSERT INTO datos (valor) VALUES (?)", [(f"fila {i}",) for i in range(filas)])
    con.commit()
    con.close()


def _nombre(momento, contador=None):
    sufijo = f"_{contador:02d}" if contador else ""
    return f"{PREFIJO_RESPALDO}{momento.strftime('%Y-%m-%d_%H%M%S')}{sufijo}.db"


def _tocar(carpeta, nombre):
    with open(os.path.join(carpeta, nombre), "wb") as f:
        f.write(b"copia")


# El hijo crea la copia "del futuro" JUSTO antes de llamar a `respaldar_bd` (despues de importar, que tarda segundos): una hora calculada
# antes de arrancar el proceso se quedaria vieja y el caso de "2 s adelantada" dejaria de serlo (leccion de M13).
_CODIGO_HIJO = r'''
import json, os, sys
from datetime import datetime, timedelta
sys.path.insert(0, sys.argv[1])
from services.respaldo import respaldar_bd
origen, destino, caso = sys.argv[2], sys.argv[3], sys.argv[4]
os.makedirs(destino, exist_ok=True)
def crear(nombre):
    with open(os.path.join(destino, nombre), "wb") as f:
        f.write(b"copia")
ahora = datetime.now()
if caso.startswith("adelantada:"):
    segundos = int(caso.split(":")[1])
    crear("BaseDatosQA_" + (ahora + timedelta(seconds=segundos)).strftime("%Y-%m-%d_%H%M%S") + ".db")
elif caso == "ajeno":
    crear("BaseDatosQA_Rebuild_14-09-2026.db")
elif caso == "ajeno_y_adelantada":
    crear("BaseDatosQA_Rebuild_14-09-2026.db")
    crear("BaseDatosQA_" + (ahora + timedelta(seconds=20)).strftime("%Y-%m-%d_%H%M%S") + ".db")
r = respaldar_bd(ruta_origen=origen, carpeta_destino=destino)
print(json.dumps(os.path.basename(r) if r else None))
'''


def _correr_en_proceso(tmp_path, caso):
    """(nombre devuelto por `respaldar_bd`, carpeta de destino). Si el proceso no termina en LIMITE_S, la prueba FALLA (M13)."""
    origen = str(tmp_path / "BaseDatosQA.db")
    destino = str(tmp_path / "respaldos_bd")
    _bd(origen)
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    try:
        r = subprocess.run([sys.executable, "-c", _CODIGO_HIJO, RAIZ_REPO, origen, destino, caso],
                           capture_output=True, text=True, timeout=LIMITE_S, env=env, cwd=RAIZ_REPO)
    except subprocess.TimeoutExpired:
        pytest.fail(f"respaldar_bd NO TERMINA en {LIMITE_S} s con el caso {caso!r}: el cierre de la aplicacion quedaria colgado (M13)")
    assert r.returncode == 0, f"el proceso hijo fallo (caso {caso!r}):\n{r.stderr[-1500:]}"
    ultima = [l for l in r.stdout.strip().splitlines() if l.strip()][-1]
    return json.loads(ultima), destino


def _respaldos_validos(destino):
    return sorted(respaldo._nombres_respaldo(destino))


class TestRespaldarBdTerminaSiempre:
    """El caso del hospital: en la carpeta ya hay algo que ordena DESPUES de lo que tocaria ahora."""

    @pytest.mark.parametrize("segundos", [2, 20, 180])
    def test_con_una_copia_de_otro_equipo_con_el_reloj_adelantado(self, tmp_path, segundos):
        devuelto, destino = _correr_en_proceso(tmp_path, f"adelantada:{segundos}")
        assert devuelto is not None
        validos = _respaldos_validos(destino)
        assert len(validos) == 2
        assert validos[-1] == devuelto, "el respaldo nuevo debe ordenar AL FINAL (si no, la rotacion lo borraria primero)"
        assert devuelto > validos[0]

    def test_con_un_archivo_ajeno_con_el_prefijo(self, tmp_path):
        devuelto, destino = _correr_en_proceso(tmp_path, "ajeno")
        assert devuelto is not None
        assert "BaseDatosQA_Rebuild_14-09-2026.db" in os.listdir(destino), "un archivo ajeno no se toca"
        assert _respaldos_validos(destino) == [devuelto]

    def test_con_un_archivo_ajeno_y_una_copia_adelantada(self, tmp_path):
        devuelto, destino = _correr_en_proceso(tmp_path, "ajeno_y_adelantada")
        assert devuelto is not None
        validos = _respaldos_validos(destino)
        assert validos[-1] == devuelto and len(validos) == 2
        assert "BaseDatosQA_Rebuild_14-09-2026.db" in os.listdir(destino)

    @pytest.mark.parametrize("con_futuras", [False, True])
    def test_con_cincuenta_copias_termina_rota_y_no_borra_lo_ajeno(self, tmp_path, con_futuras):
        """50 copias (las ultimas, opcionalmente, con hora de otro equipo adelantada) mas un archivo ajeno: termina, el nuevo ordena
        al final, la rotacion deja las 10 mas recientes y el archivo ajeno sigue ahi."""
        origen = str(tmp_path / "BaseDatosQA.db")
        destino = str(tmp_path / "respaldos_bd")
        os.makedirs(destino)
        _bd(origen)
        base = datetime(2026, 1, 1, 8, 0, 0)
        for i in range(50):
            _tocar(destino, _nombre(base + timedelta(days=i)))
        _tocar(destino, "BaseDatosQA_Rebuild_14-09-2026.db")                    # ordena DESPUES de todos
        _tocar(destino, "BaseDatosQA_00_copia_manual.db")                       # ordena ANTES que todos: el codigo viejo lo rotaria primero
        if con_futuras:
            for minutos in (1, 2, 3):
                _tocar(destino, _nombre(datetime.now() + timedelta(minutes=minutos)))
        env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
        try:
            r = subprocess.run(
                [sys.executable, "-c",
                 "import json,os,sys\nsys.path.insert(0, sys.argv[1])\nfrom services.respaldo import respaldar_bd\n"
                 "r = respaldar_bd(ruta_origen=sys.argv[2], carpeta_destino=sys.argv[3])\nprint(json.dumps(os.path.basename(r) if r else None))",
                 RAIZ_REPO, origen, destino],
                capture_output=True, text=True, timeout=LIMITE_S, env=env, cwd=RAIZ_REPO)
        except subprocess.TimeoutExpired:
            pytest.fail(f"respaldar_bd NO TERMINA con 50 copias (M13); con_futuras={con_futuras}")
        assert r.returncode == 0, r.stderr[-1500:]
        devuelto = json.loads([l for l in r.stdout.strip().splitlines() if l.strip()][-1])
        validos = _respaldos_validos(destino)
        assert len(validos) == MAX_RESPALDOS
        assert validos[-1] == devuelto
        assert "BaseDatosQA_Rebuild_14-09-2026.db" in os.listdir(destino)
        assert "BaseDatosQA_00_copia_manual.db" in os.listdir(destino)


class TestNombreEnUnPaso:
    """El nombre se decide con `ahora` inyectada, sin esperar al reloj y sin bucle."""

    AHORA = datetime(2026, 10, 5, 12, 0, 0)

    def test_sin_copias_usa_la_hora_dada(self, tmp_path):
        origen = str(tmp_path / "BaseDatosQA.db")
        _bd(origen)
        r = respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "r"), ahora=self.AHORA)
        assert os.path.basename(r) == "BaseDatosQA_2026-10-05_120000.db"

    def test_ahora_por_omision_es_la_hora_de_este_equipo(self, tmp_path):
        origen = str(tmp_path / "BaseDatosQA.db")
        _bd(origen)
        antes = datetime.now().replace(microsecond=0)
        r = respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "r"))
        marca = datetime.strptime(os.path.basename(r)[len(PREFIJO_RESPALDO):][:17], "%Y-%m-%d_%H%M%S")
        assert antes <= marca <= datetime.now() + timedelta(seconds=1)

    @pytest.mark.parametrize("existente, esperado", [
        ("BaseDatosQA_2026-10-05_120000.db",     "BaseDatosQA_2026-10-05_120000_02.db"),     # misma hora, sin contador -> _02
        ("BaseDatosQA_2026-10-05_120000_07.db",  "BaseDatosQA_2026-10-05_120000_08.db"),     # con contador -> el siguiente
        ("BaseDatosQA_2026-10-05_120009_09.db",  "BaseDatosQA_2026-10-05_120009_10.db"),     # _10 ordena despues de _09
        ("BaseDatosQA_2026-10-05_120200.db",     "BaseDatosQA_2026-10-05_120200_02.db"),     # copia 2 min adelantada: toma SU marca
        ("BaseDatosQA_2026-10-06_080000_03.db",  "BaseDatosQA_2026-10-06_080000_04.db"),     # copia de manana
        ("BaseDatosQA_2026-10-05_120000_99.db",  "BaseDatosQA_2026-10-05_120001.db"),        # sin sitio para el contador: el segundo siguiente
        ("BaseDatosQA_2026-10-05_235959_99.db",  "BaseDatosQA_2026-10-06_000000.db"),        # y cruza el dia
    ])
    def test_si_la_hora_no_supera_al_ultimo_toma_su_marca_y_suma_el_contador(self, tmp_path, existente, esperado):
        origen = str(tmp_path / "BaseDatosQA.db")
        destino = tmp_path / "r"
        destino.mkdir()
        _bd(origen)
        _tocar(str(destino), existente)
        r = respaldar_bd(ruta_origen=origen, carpeta_destino=str(destino), ahora=self.AHORA)
        assert os.path.basename(r) == esperado
        assert _respaldos_validos(str(destino)) == sorted([existente, esperado])

    def test_si_la_hora_supera_al_ultimo_no_hay_contador(self, tmp_path):
        origen = str(tmp_path / "BaseDatosQA.db")
        destino = tmp_path / "r"
        destino.mkdir()
        _bd(origen)
        _tocar(str(destino), "BaseDatosQA_2026-10-05_115959_07.db")
        r = respaldar_bd(ruta_origen=origen, carpeta_destino=str(destino), ahora=self.AHORA)
        assert os.path.basename(r) == "BaseDatosQA_2026-10-05_120000.db"

    def test_una_copia_con_la_hora_del_fin_del_calendario_no_impide_respaldar(self, tmp_path):
        """H7 (revision de RB.1): con el contador en 99 `_nombre_nuevo` suma un segundo a la marca del ultimo respaldo; con
        `BaseDatosQA_9999-12-31_235959_99.db` en la carpeta eso lanzaba `OverflowError` y `respaldar_bd` devolvia `None` PARA SIEMPRE.
        Ahora esa marca no es una hora de este mundo: no cuenta como respaldo, no decide el nombre y no se toca."""
        origen = str(tmp_path / "BaseDatosQA.db")
        destino = tmp_path / "r"
        destino.mkdir()
        _bd(origen)
        _tocar(str(destino), "BaseDatosQA_9999-12-31_235959_99.db")
        r = respaldar_bd(ruta_origen=origen, carpeta_destino=str(destino), ahora=self.AHORA)
        assert r is not None and os.path.basename(r) == "BaseDatosQA_2026-10-05_120000.db"
        assert "BaseDatosQA_9999-12-31_235959_99.db" in os.listdir(destino), "lo que no es un respaldo no se toca"

    def test_la_ultima_marca_representable_no_lanza(self):
        """El borde exacto: con el contador agotado en la ultima marca valida, el segundo siguiente es el ultimo del calendario."""
        assert respaldo._nombre_nuevo(["BaseDatosQA_9999-12-31_235958_99.db"], self.AHORA) == "BaseDatosQA_9999-12-31_235959.db"

    def test_el_nombre_nuevo_siempre_es_posterior_al_ultimo_y_nunca_existe(self):
        """Propiedad, con 400 carpetas al azar (semilla fija): sea cual sea el contenido valido de la carpeta y la hora, el nombre
        nuevo ordena estrictamente DESPUES de todos y no coincide con ninguno (por eso no hace falta un bucle)."""
        azar = random.Random(20261005)
        base = datetime(2026, 1, 1)
        for _ in range(400):
            existentes = set()
            for _ in range(azar.randint(0, 25)):
                momento = base + timedelta(seconds=azar.randint(0, 400 * 86400))
                existentes.add(_nombre(momento, azar.choice([None, None, 2, 3, 9, 10, 57, 98, 99])))
            existentes = sorted(existentes)
            ahora = base + timedelta(seconds=azar.randint(0, 400 * 86400))
            nuevo = respaldo._nombre_nuevo(existentes, ahora)
            assert respaldo._marca_y_contador(nuevo) is not None, nuevo
            assert nuevo not in existentes
            if existentes:
                assert nuevo > existentes[-1], (existentes[-3:], ahora, nuevo)


class TestSoloCuentaLoQueTieneLaFormaDeUnRespaldo:
    @pytest.mark.parametrize("nombre", [
        "BaseDatosQA_2026-10-05_120000.db",
        "BaseDatosQA_2026-10-05_120000_02.db",
        "BaseDatosQA_2026-02-28_235959_99.db",
        "BaseDatosQA_9999-12-31_235958_99.db",                # la ultima marca cuyo "segundo siguiente" existe
    ])
    def test_los_nombres_de_un_respaldo(self, nombre):
        assert respaldo._marca_y_contador(nombre) is not None

    @pytest.mark.parametrize("nombre", [
        "BaseDatosQA_Rebuild_14-09-2026.db",                  # un archivo ajeno con el prefijo
        "BaseDatosQA_2026-10-05_120000.db.parcial",           # la copia provisional de RB.1
        "BaseDatosQA_2026-10-05_120000.db.revisar",           # la copia aparte de RB.1
        "BaseDatosQA_2026-13-45_999999.db",                   # tiene forma de fecha y no lo es
        "BaseDatosQA_2026-10-05_246000.db",                   # hora imposible
        "BaseDatosQA_2026-10-05_120000_1.db",                 # contador de una cifra
        "BaseDatosQA_2026-10-05_120000_007.db",               # contador de tres
        "BaseDatosQA_2026-10-05_120000_ab.db",
        "BaseDatosQA_\u0662\u0660\u0662\u0666-10-05_120000.db",   # digitos Unicode (arabe-indicos): `\\d` sin `re.ASCII` los aceptaria (H7)
        "BaseDatosQA_9999-12-31_235959.db",                   # a un segundo del fin del calendario: su "segundo siguiente" no existe (H7)
        "BaseDatosQA_9999-12-31_235959_99.db",
        "basedatosqa_2026-10-05_120000.db",                   # otras mayusculas
        "BaseDatosQA_2026-10-05_120000.sqlite",
        "BaseDatosQA.db",
        "franja_2026-10-05_1.hecha",
    ])
    def test_los_demas_nombres_no_cuentan(self, nombre):
        assert respaldo._marca_y_contador(nombre) is None

    def test_un_salto_de_linea_final_no_es_un_respaldo(self):
        """H7: con `$` en el patron, `BaseDatosQA_..._120000.db\\n` contaba como respaldo (el `$` acepta un salto de linea antes del final)."""
        assert respaldo._marca_y_contador("BaseDatosQA_2026-10-05_120000.db\n") is None
        assert respaldo._marca_y_contador("BaseDatosQA_2026-10-05_120000_02.db\n") is None

    def test_la_lista_de_respaldos_ignora_lo_ajeno_y_ordena_cronologicamente(self, tmp_path):
        carpeta = str(tmp_path)
        for nombre in ("BaseDatosQA_2026-10-05_120000_02.db", "BaseDatosQA_Rebuild_14-09-2026.db",
                       "BaseDatosQA_2026-10-05_120000.db", "BaseDatosQA_2026-10-05_120000.db.parcial",
                       "BaseDatosQA_\u0662\u0660\u0662\u0666-10-05_120000.db", "BaseDatosQA_9999-12-31_235959_99.db",
                       "BaseDatosQA_2026-10-04_090000.db", "notas.txt"):
            _tocar(carpeta, nombre)
        assert respaldo._nombres_respaldo(carpeta) == [
            "BaseDatosQA_2026-10-04_090000.db", "BaseDatosQA_2026-10-05_120000.db", "BaseDatosQA_2026-10-05_120000_02.db"]

    def test_la_rotacion_no_borra_lo_ajeno_ni_lo_provisional(self, tmp_path):
        carpeta = str(tmp_path)
        base = datetime(2026, 3, 1, 9, 0, 0)
        for i in range(6):
            _tocar(carpeta, _nombre(base + timedelta(days=i)))
        ajenos = ("BaseDatosQA_Rebuild_14-09-2026.db",          # ordena despues de todos
                  "BaseDatosQA_00_copia_manual.db",             # ordena ANTES que todos (el codigo viejo lo rotaria primero)
                  "BaseDatosQA_2026-03-01_090000.db.parcial", "notas.txt")
        for ajeno in ajenos:
            _tocar(carpeta, ajeno)
        respaldo._rotar(carpeta, 3)
        assert len(respaldo._nombres_respaldo(carpeta)) == 3
        for ajeno in ajenos:
            assert os.path.exists(os.path.join(carpeta, ajeno)), ajeno


class TestSinBucle:
    """El nombre se decide en un paso: ni `while` ni `for` en la funcion que lo decide, ni `while` en `respaldar_bd`."""

    @staticmethod
    def _funcion(nombre):
        arbol = ast.parse(inspect.getsource(respaldo))
        return next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == nombre)

    def test_la_funcion_que_decide_el_nombre_no_tiene_bucles(self):
        f = self._funcion("_nombre_nuevo")
        assert not [n for n in ast.walk(f) if isinstance(n, (ast.While, ast.For))]

    def test_respaldar_bd_no_tiene_while(self):
        f = self._funcion("respaldar_bd")
        assert not [n for n in ast.walk(f) if isinstance(n, ast.While)]
