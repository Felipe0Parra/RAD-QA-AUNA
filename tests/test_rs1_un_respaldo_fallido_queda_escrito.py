"""RS.1 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, DP-153): un respaldo que no se pudo hacer queda escrito en `error_log.txt`.

Antes `respaldar_bd` y `respaldar_al_cerrar` devolvian `None` y solo hacian `print`: el `.exe` se construye `--noconsole`, asi que un respaldo que fallaba en CADA cierre (carpeta sin escritura,
origen ilegible, disco lleno...) dejaba al servicio sin red de seguridad y nada lo decia (V4 lo midio con la salida estandar anulada: ni un byte, y `error_log.txt` no se creaba).

Ahora cada fallo conserva su `print` y ademas anade un bloque con fecha, motivo (y rastro, si hay excepcion) al registro de `services.registro_errores` -- el MISMO archivo que escribe `main.py`, junto
al ejecutable --; el aviso de exito no escribe nada; y un registro que no se puede escribir no impide cerrar la app. `tests/conftest.py` redirige ese archivo a uno temporal de la sesion (las
pruebas de respaldo recorren 36 avisos por corrida: sin eso crearian `Codigo_radqa/error_log.txt`).

Revision de la tarea (dos revisores escepticos, hallazgos reproducidos): los avisos de la copia, de la integridad y de la base danada nombran la base y la carpeta; un error al rotar (la
carpeta creceria sin limite) tambien queda escrito; un fallo se escribe UNA vez (con la base de origen danada son dos entradas, de dos fallos distintos: la copia y el estado de la base); la
rama de «no se pudo conservar la copia» conserva el rastro; el fixture de sesion de `tests/conftest.py` se prueba por si mismo (una variable ya exportada en el entorno no lo tapa); y la
guarda de la salida estandar se prueba con una que LANZA al escribir (con `sys.stdout = None` un `print` desnudo tampoco falla).

Sobre el rojo contra el codigo anterior: todas las pruebas de comportamiento usan solo API que ya existia y caen por su asercion.
"""
import ast
import os
import re
import sqlite3

import pytest

import services.registro_errores as registro
import services.respaldo as respaldo

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _crear_bd(ruta, filas=3):
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE datos (id INTEGER PRIMARY KEY, valor TEXT)")
    con.executemany("INSERT INTO datos (valor) VALUES (?)", [(f"fila {i}",) for i in range(filas)])
    con.commit()
    con.close()


@pytest.fixture
def log(tmp_path, monkeypatch):
    """El registro de errores de ESTA prueba: un archivo propio, que se lee entero."""
    ruta = tmp_path / "registro" / "error_log.txt"
    ruta.parent.mkdir()
    monkeypatch.setattr(registro, "ruta_error_log", lambda: str(ruta))

    class _Log:
        def texto(self):
            return ruta.read_text(encoding="utf-8") if ruta.exists() else ""

        existe = property(lambda self: ruta.exists())

    return _Log()


@pytest.fixture
def origen(tmp_path):
    ruta = str(tmp_path / "BaseDatosQA.db")
    _crear_bd(ruta)
    return ruta


# ---------------------------------------------------------------------------------------------------- cada camino de fallo
class TestCadaFalloDeRespaldoQuedaEscrito:

    def test_la_base_de_origen_no_existe(self, tmp_path, log, capsys):
        assert respaldo.respaldar_bd(ruta_origen=str(tmp_path / "no_existe.db"), carpeta_destino=str(tmp_path / "r")) is None
        assert "[respaldo] no existe la BD de origen, no se respalda" in log.texto()
        assert "no existe la BD de origen" in capsys.readouterr().out, "el print de siempre se conserva"

    def test_la_base_de_origen_no_existe_al_cerrar(self, tmp_path, log):
        assert respaldo.respaldar_al_cerrar(ruta_origen=str(tmp_path / "no_existe.db"), carpeta_destino=str(tmp_path / "r")) is None
        assert "[respaldo] no existe la BD de origen, no se respalda" in log.texto()

    def test_la_copia_no_se_pudo_hacer(self, tmp_path, origen, log, monkeypatch):
        def falla(ruta_origen, ruta_parcial):
            raise OSError("No queda espacio en el dispositivo")
        monkeypatch.setattr(respaldo, "_copiar_con_api", falla)
        assert respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "r")) is None
        texto = log.texto()
        assert f"[respaldo] la copia no se pudo hacer ({origen} -> {tmp_path / 'r'}): No queda espacio en el dispositivo" in texto, "la linea nombra la base y la carpeta"
        assert "Traceback" in texto and "OSError" in texto, "con excepcion, el registro lleva el rastro"

    def test_la_copia_no_pasa_la_integridad(self, tmp_path, origen, log, monkeypatch):
        llamadas = []

        def integridad(ruta):
            llamadas.append(ruta)
            return (respaldo.ESTADO_DEFECTO, "malformed") if len(llamadas) == 1 else (respaldo.ESTADO_OK, None)
        monkeypatch.setattr(respaldo, "_integridad", integridad)
        assert respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "r")) is None
        assert f"[respaldo] la copia de {origen} no pasa la comprobacion de integridad (malformed): se descarta" in log.texto()

    def test_la_base_de_origen_esta_danada(self, tmp_path, origen, log, monkeypatch):
        monkeypatch.setattr(respaldo, "_integridad", lambda ruta: (respaldo.ESTADO_DEFECTO, "database disk image is malformed"))
        assert respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "r")) is None
        assert f"[respaldo] ATENCION: la base de datos de origen ({origen}) no pasa la comprobacion de integridad: database disk image is malformed" in log.texto()

    def test_no_se_pudo_conservar_la_copia_para_revisar(self, tmp_path, origen, log, monkeypatch):
        monkeypatch.setattr(respaldo, "_integridad", lambda ruta: (respaldo.ESTADO_DEFECTO, "malformed"))

        def falla(*a, **k):
            raise OSError("sin permiso")
        monkeypatch.setattr(respaldo.shutil, "copy2", falla)
        monkeypatch.setattr(respaldo, "_copiar_con_api", lambda o, p: (_ for _ in ()).throw(OSError("no copia")))
        respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "r"))
        texto = log.texto()
        assert f"[respaldo] no se pudo conservar la copia para revisar de {origen}" in texto and "sin permiso" in texto
        assert re.search(r"Traceback[\s\S]*OSError: sin permiso", texto), "el rastro de la rama de «no se pudo conservar la copia» no se pierde"

    def test_un_error_inesperado_al_respaldar(self, tmp_path, origen, log, monkeypatch):
        monkeypatch.setattr(respaldo, "_nombres_respaldo", lambda carpeta: (_ for _ in ()).throw(RuntimeError("fallo inesperado")))
        assert respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "r")) is None
        texto = log.texto()
        assert "[respaldo] no se pudo respaldar la base de datos: fallo inesperado" in texto and "RuntimeError" in texto

    def test_un_error_inesperado_al_cerrar(self, tmp_path, origen, log, monkeypatch):
        monkeypatch.setattr(respaldo, "franja_de", lambda ahora: (_ for _ in ()).throw(RuntimeError("fallo del cierre")))
        assert respaldo.respaldar_al_cerrar(ruta_origen=origen, carpeta_destino=str(tmp_path / "r")) is None
        texto = log.texto()
        assert "[respaldo] no se pudo respaldar al cerrar: fallo del cierre" in texto and "RuntimeError" in texto

    def test_sin_permiso_para_crear_la_marca_de_la_franja(self, tmp_path, log, monkeypatch):
        real = os.open

        def sin_permiso(ruta, *a, **k):
            if os.path.basename(str(ruta)).startswith(respaldo.PREFIJO_FRANJA):
                raise PermissionError(13, "Permiso denegado")
            return real(ruta, *a, **k)
        monkeypatch.setattr(respaldo.os, "open", sin_permiso)
        assert respaldo._crear_exclusivo(str(tmp_path / f"{respaldo.PREFIJO_FRANJA}2026-10-08_1.reclamo"), "x") is False
        assert "[respaldo] sin permiso para crear" in log.texto() and "Permiso denegado" in log.texto()

    def test_un_error_al_rotar_queda_escrito_con_la_carpeta(self, tmp_path, origen, log, monkeypatch):
        """Revision (PROD-2): una rotacion que no puede borrar deja crecer la carpeta sin limite; en el `.exe` sin consola nadie lo veria."""
        carpeta = tmp_path / "r"
        carpeta.mkdir()
        for dia in (1, 2, 3):
            (carpeta / f"BaseDatosQA_2026-10-0{dia}_090000.db").write_bytes(b"x")
        real = os.remove

        def sin_permiso(ruta, *a, **k):
            if os.path.basename(str(ruta)).startswith("BaseDatosQA_2026-10-01"):
                raise PermissionError(13, "Permiso denegado")
            return real(ruta, *a, **k)
        monkeypatch.setattr(respaldo.os, "remove", sin_permiso)
        respaldo._rotar(str(carpeta), 1)
        texto = log.texto()
        assert f"[respaldo] no se pudo rotar BaseDatosQA_2026-10-01_090000.db (en {carpeta})" in texto and "Permiso denegado" in texto and "Traceback" in texto

    def test_cada_fallo_deja_su_fecha(self, tmp_path, log):
        respaldo.respaldar_bd(ruta_origen=str(tmp_path / "no_existe.db"), carpeta_destino=str(tmp_path / "r"))
        assert log.texto().lstrip().startswith("["), "cada bloque empieza con [fecha hora]"
        import re
        assert re.match(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[respaldo\]", log.texto().lstrip())


def _bloques(texto):
    return re.findall(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] ", texto, re.M)


class TestUnFalloSeEscribeUnaSolaVez:
    """Revision (H3 de las pruebas): el plan decia «una linea por cierre fallido»; con una prueba que solo busca subcadenas, un fallo escrito DOS veces no caia."""

    def test_la_base_no_existe(self, tmp_path, log):
        respaldo.respaldar_bd(ruta_origen=str(tmp_path / "no_existe.db"), carpeta_destino=str(tmp_path / "r"))
        assert len(_bloques(log.texto())) == 1
        respaldo.respaldar_al_cerrar(ruta_origen=str(tmp_path / "no_existe.db"), carpeta_destino=str(tmp_path / "r"))
        assert len(_bloques(log.texto())) == 2, "un fallo por cierre"

    def test_la_copia_no_se_pudo_hacer(self, tmp_path, origen, log, monkeypatch):
        monkeypatch.setattr(respaldo, "_copiar_con_api", lambda o, p: (_ for _ in ()).throw(OSError("disco lleno")))
        monkeypatch.setattr(respaldo, "_integridad", lambda ruta: (respaldo.ESTADO_OK, None))        # el origen esta sano: solo falla la copia
        respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "r"))
        assert len(_bloques(log.texto())) == 1

    def test_un_error_inesperado(self, tmp_path, origen, log, monkeypatch):
        monkeypatch.setattr(respaldo, "_nombres_respaldo", lambda carpeta: (_ for _ in ()).throw(RuntimeError("fallo inesperado")))
        respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "r"))
        assert len(_bloques(log.texto())) == 1

    def test_con_la_base_de_origen_danada_son_dos_entradas_de_dos_fallos_distintos(self, tmp_path, origen, log, monkeypatch):
        """La copia no pasa la comprobacion Y la base de origen tampoco: dos hechos distintos (el respaldo y el estado de la base), cada uno con su causa."""
        monkeypatch.setattr(respaldo, "_integridad", lambda ruta: (respaldo.ESTADO_DEFECTO, "database disk image is malformed"))
        respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "r"))
        texto = log.texto()
        assert len(_bloques(texto)) == 2 and "la copia de" in texto and "ATENCION" in texto


# ---------------------------------------------------------------------------------------------------- lo que NO escribe
class TestLoQueNoSeEscribe:

    def test_un_respaldo_bueno_no_escribe_nada(self, tmp_path, origen, log):
        destino = respaldo.respaldar_bd(ruta_origen=origen, carpeta_destino=str(tmp_path / "r"))
        assert destino is not None and not log.existe, "el aviso de exito no va al registro"

    def test_un_cierre_bueno_no_escribe_nada(self, tmp_path, origen, log):
        assert respaldo.respaldar_al_cerrar(ruta_origen=origen, carpeta_destino=str(tmp_path / "r")) is not None
        assert not log.existe

    def test_la_franja_ya_hecha_no_es_un_fallo(self, tmp_path, origen, log):
        carpeta = str(tmp_path / "r")
        assert respaldo.respaldar_al_cerrar(ruta_origen=origen, carpeta_destino=carpeta) is not None
        assert respaldo.respaldar_al_cerrar(ruta_origen=origen, carpeta_destino=carpeta) is None
        assert not log.existe, "no volver a respaldar en la misma franja es el diseno (D2), no un error"


# ---------------------------------------------------------------------------------------------------- el registro nunca rompe
class TestElRegistroNuncaRompeElCierre:

    def test_un_registro_que_no_se_puede_escribir_no_cambia_el_resultado(self, tmp_path, monkeypatch):
        monkeypatch.setattr(registro, "ruta_error_log", lambda: str(tmp_path / "carpeta" / "inexistente" / "error_log.txt"))
        assert respaldo.respaldar_bd(ruta_origen=str(tmp_path / "no_existe.db"), carpeta_destino=str(tmp_path / "r")) is None
        assert respaldo.respaldar_al_cerrar(ruta_origen=str(tmp_path / "no_existe.db"), carpeta_destino=str(tmp_path / "r")) is None

    def test_una_salida_estandar_ausente_tampoco(self, tmp_path, log, monkeypatch):
        """El `.exe --noconsole` no tiene `sys.stdout` (`None`): el aviso por consola no puede romper el respaldo ni impedir el registro."""
        monkeypatch.setattr("sys.stdout", None)
        assert respaldo.respaldar_bd(ruta_origen=str(tmp_path / "no_existe.db"), carpeta_destino=str(tmp_path / "r")) is None
        assert "no existe la BD de origen" in log.texto(), "con la consola ausente el registro es lo unico que queda"

    def test_una_salida_estandar_que_lanza_al_escribir_tampoco(self, tmp_path, log, monkeypatch):
        """Revision (H7): con `sys.stdout = None` un `print` desnudo tampoco falla; lo que protege `avisar_consola` es una salida que LANZA (una consola cerrada, o una codificacion que no
        sabe un caracter): sin esa guarda el cierre de la aplicacion reventaba ANTES de escribir en el registro."""
        class _Rota:
            def write(self, texto):
                raise UnicodeEncodeError("ascii", texto, 0, 1, "la consola no sabe este caracter")

            def flush(self):
                raise OSError("consola cerrada")
        monkeypatch.setattr("sys.stdout", _Rota())
        assert respaldo.respaldar_bd(ruta_origen=str(tmp_path / "no_existe.db"), carpeta_destino=str(tmp_path / "r")) is None
        assert "no existe la BD de origen" in log.texto()


# ---------------------------------------------------------------------------------------------------- una sola ruta, ningun print nuevo
def _arbol():
    with open(os.path.join(RAIZ, "services", "respaldo.py"), encoding="utf-8") as f:
        return ast.parse(f.read())


def test_el_registro_se_escribe_por_la_funcion_unica_y_no_por_un_archivo_propio():
    """Tripwire: `respaldo.py` no arma la ruta de `error_log.txt` ni lo abre: importa `avisar_consola` y `registrar_error` de `registro_errores` (la misma funcion que `main.py` y las
    pruebas redirigen) y `_avisar` las llama a las dos."""
    arbol = _arbol()
    importados = {a.name for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) and n.module == "services.registro_errores" for a in n.names}
    assert {"avisar_consola", "registrar_error"} <= importados, importados
    avisar = next(f for f in ast.walk(arbol) if isinstance(f, ast.FunctionDef) and f.name == "_avisar")
    llamadas = {c.func.id for c in ast.walk(avisar) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert {"avisar_consola", "registrar_error"} <= llamadas, llamadas
    cadenas = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.strip() == "error_log.txt"]
    assert cadenas == [], "respaldo.py no escribe su propio error_log.txt"


def test_los_unicos_print_son_el_de_exito_y_los_de_limpieza():
    """Tripwire (DP-153): todo aviso de FALLO de respaldo pasa por `_avisar`. Los `print` que quedan son el de exito (una sola vez, en `respaldar_bd`) y el de limpieza de un archivo
    provisional (`_quitar`: el respaldo ya esta hecho; las marcas y los provisionales huerfanos se retiran por edad). Un error al ROTAR ya no es un `print` (revision de RS.1): una rotacion
    rota deja crecer la carpeta sin limite. Un `print` nuevo en este modulo es un aviso que el `.exe` no mostraria: tiene que decidirse."""
    esperados = {"respaldar_bd": 1, "_quitar": 1}
    halladas = {}
    for f in ast.walk(_arbol()):
        if isinstance(f, ast.FunctionDef):
            n = sum(1 for c in ast.walk(f) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "print")
            if n:
                halladas[f.name] = n
    assert halladas == esperados, halladas


class TestLaVariableDeEntornoRedirigeElRegistro:
    """Las pruebas de RB.1 lanzan procesos hijos que respaldan «como otro equipo»: un monkeypatch del proceso padre no llega a ellos y escribian `Codigo_radqa/error_log.txt`. La variable de
    entorno `RADQA_ERROR_LOG` la heredan."""

    def test_la_variable_manda_sobre_la_ruta_por_omision(self, tmp_path, monkeypatch):
        destino = str(tmp_path / "otro" / "error_log.txt")
        monkeypatch.setenv(registro.VARIABLE_DE_RUTA, destino)
        assert registro.ruta_error_log() == destino
        monkeypatch.delenv(registro.VARIABLE_DE_RUTA)
        assert registro.ruta_error_log() == os.path.join(RAIZ, "error_log.txt"), "sin la variable, la ruta de siempre (la de main.py)"

    def test_un_proceso_hijo_escribe_donde_dice_la_variable(self, tmp_path):
        import subprocess
        import sys
        destino = tmp_path / "hijo" / "error_log.txt"
        destino.parent.mkdir()
        codigo = ("import sys; sys.path.insert(0, sys.argv[1]); import services.respaldo as r; "
                  "r.respaldar_bd(ruta_origen=sys.argv[2], carpeta_destino=sys.argv[3])")
        env = {**os.environ, registro.VARIABLE_DE_RUTA: str(destino), "QT_QPA_PLATFORM": "offscreen"}
        r = subprocess.run([sys.executable, "-c", codigo, RAIZ, str(tmp_path / "no_existe.db"), str(tmp_path / "r")], capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=120)
        assert r.returncode == 0, r.stderr
        assert "no existe la BD de origen" in destino.read_text(encoding="utf-8")


def test_la_ruta_del_registro_de_la_suite_no_es_la_del_arbol_de_trabajo():
    """Guarda de `tests/conftest.py`: ninguna prueba debe escribir `Codigo_radqa/error_log.txt` (36 avisos de respaldo por corrida, mas los de guardado y carga)."""
    ruta = os.path.abspath(registro.ruta_error_log())
    assert os.path.dirname(ruta) != RAIZ and not ruta.startswith(RAIZ + os.sep), ruta


def test_el_fixture_de_sesion_que_fija_la_variable_existe_y_la_fija():
    """Revision (H5): la prueba de arriba mide el estado final de la ruta, no que el fixture la fije: con `RADQA_ERROR_LOG` ya exportada en el entorno (como cuando un revisor o una
    herramienta la fijan) quitar el fixture no la hacia caer. Aqui se prueba el fixture MISMO, por AST: un fixture automatico de sesion que asigna `os.environ[VARIABLE_DE_RUTA]`."""
    with open(os.path.join(RAIZ, "tests", "conftest.py"), encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    fixture = next((n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "_error_log_de_sesion"), None)
    assert fixture is not None, "tests/conftest.py ya no define el fixture `_error_log_de_sesion`"
    decorador = ast.dump(fixture.decorator_list[0])
    assert "autouse" in decorador and "session" in decorador, decorador
    asignaciones = [n for n in ast.walk(fixture) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Subscript) and isinstance(t.value, ast.Attribute) and t.value.attr == "environ" for t in n.targets)]
    assert asignaciones, "el fixture no asigna os.environ[...]"
