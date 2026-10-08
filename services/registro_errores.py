"""GI.6 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md): el archivo de texto donde queda la CAUSA de lo que falla sin que el fisico la vea.

El `.exe` se distribuye con --noconsole: lo que se imprime no lo ve nadie. `main.py` ya escribe en `error_log.txt` las excepciones NO capturadas; esto es para las que la
aplicacion SI captura y le explica al fisico (un guardado que falla, un respaldo que no se pudo hacer, DP-153): la causa tecnica completa -- con su rastro -- queda en
`error_log.txt`, junto al ejecutable (o en la raiz del proyecto en desarrollo, el mismo sitio que usa `main.py`), y a la pantalla solo llega el mensaje traducido.

Nunca lanza: un registro de errores que falla no puede producir otro error (mismo criterio que el de `main.py`).
"""
import os
import sys
import traceback
from datetime import datetime


VARIABLE_DE_RUTA = "RADQA_ERROR_LOG"


def ruta_error_log():
    """`error_log.txt` junto al ejecutable si esta congelado (--noconsole); en desarrollo, en la raiz del proyecto. Mismo sitio que escribe `main.py`.

    RS.1: si la variable de entorno `RADQA_ERROR_LOG` trae una ruta, esa manda. Es lo que usa la suite de pruebas para que NINGUN proceso -- tampoco los hijos que algunas pruebas lanzan
    para simular a otro equipo escribiendo a la vez -- cree `error_log.txt` en el arbol de trabajo; en produccion la variable no existe."""
    explicita = os.environ.get(VARIABLE_DE_RUTA)
    if explicita:
        return explicita
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'error_log.txt')


def registrar_error(contexto, excepcion=None, detalle=""):
    """Añade al final de `error_log.txt`: `[fecha hora] contexto`, el `detalle` si lo hay y, si viene una excepcion, su tipo, su mensaje y su rastro completo (con las
    causas encadenadas). Devuelve `True` si pudo escribir y `False` si no; no lanza nunca."""
    try:
        lineas = [f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] {contexto}\n"]
        if detalle:
            lineas.append(f"{detalle}\n")
        if excepcion is not None:
            lineas.append(''.join(traceback.format_exception(type(excepcion), excepcion, excepcion.__traceback__)))
        with open(ruta_error_log(), 'a', encoding='utf-8') as f:
            f.write(''.join(lineas))
        return True
    except Exception:
        return False


def avisar_consola(texto):
    """Un aviso por consola que NUNCA rompe lo que lo emite (revision de GI.6, P3). El `.exe` no tiene consola (`sys.stdout` es `None`) y en desarrollo la salida puede estar redirigida,
    cerrada o ser cp1252/ascii: un `print` con un simbolo lanzaba `UnicodeEncodeError` DESPUES del `commit` y convertia un guardado bueno en «No se guardo nada». Devuelve `True` si
    pudo escribir."""
    try:
        print(texto)
        return True
    except Exception:
        return False
