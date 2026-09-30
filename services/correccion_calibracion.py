"""RC.2 (PLAN_RECALCULO_CALIBRACION_BRAQUI_30-09.md): la política de
corrección de una calibración de braquiterapia guardada, y las cuentas
que reconstruyen los resultados "como al volver a guardar".

Puro (sin Qt ni BD): `data/ManejoDatos/load.py::corregir_calibracion` es
quien abre la conexión, muestra los diálogos y escribe; este módulo solo
CLASIFICA cada columna y CALCULA. La misma clasificación la usa `RC.3`
para comprobar que ninguna celda editable de la vista apunte a una
entrada del cálculo, a un resultado archivado o a una columna que no se
corrige en sitio, sin declarar su recálculo.

Decisión del físico (29-09, DP-138): "Todo, como al volver a guardar" --
corregir `conversion`, `intensidad` o `fecha_cer` recalcula las cinco
cifras de `ResultadosActividad` exactamente como volver a guardar: por
`ref`, medidas por papel, media de las guardadas, voltajes guardados,
TRS-398. `fecha`, `tipo`, `id` y `activo` no se corrigen en sitio (DP-44 y
el hecho de que no son datos del control).
"""
import math

from analisisImagenes.ActividadFuente import promedio_de_medidas, resultados_para_archivar
from services.lecturas_del_maximo import voltaje_de_texto

# Columna de TipoCalibracion -> clave del diccionario que devuelve
# `consulta_mesualBraq` -- para leer el valor guardado y, tras la
# corrección, construir la versión corregida de ese diccionario.
COLUMNAS_QUE_RECALCULAN = {
    "conversion": "conversion",
    "intensidad": "intensidad",
    "fecha_cer": "fecha_cer",
}

# No entran en ninguna cuenta de ResultadosActividad -- se corrigen con el
# UPDATE de siempre, sin recalcular ni preguntar.
COLUMNAS_SIN_EFECTO_EN_EL_CALCULO = frozenset({"user", "serie", "certificado"})

# No se corrigen EN SITIO -- `corregir_calibracion` las rechaza con este
# motivo, en castellano y sin símbolos (DA-18).
COLUMNAS_QUE_NO_SE_CORRIGEN_EN_SITIO = {
    "fecha": (
        "identifica la calibración y sus tablas asociadas se leen por "
        "fecha (DP-44): corregirla aquí dejaría el control sin sus datos."),
    "tipo": "forma, con la fecha, la clave de la calibración.",
    "id": "no es un dato del control.",
    "activo": "no es un dato del control.",
}

# Entradas de OTRAS tablas que participan en la cuenta -- las usa RC.3 para
# comprobar que ninguna celda editable apunte aquí sin su recálculo.
ENTRADAS_DE_OTRAS_TABLAS = {
    "CondicionesMedicion": ("t", "p"),
    "SistemaMedicion": ("t0", "p0", "calibracion", "electrometro"),
    "LecturasMaximos": ("voltaje", "V_300", "V_150", "Vn_300", "promediosV"),
}

RESULTADOS_ARCHIVADOS = ("Ks", "Kp", "Ktp", "actividad_calculada", "actividad_decaimiento")

NOMBRES_LEGIBLES_COLUMNA = {
    "conversion": "el factor de conversión",
    "intensidad": "la intensidad del certificado",
    "fecha_cer": "la fecha del certificado",
}

NOMBRES_LEGIBLES_RESULTADOS = {
    "Ks": "Ks",
    "Kp": "Kp",
    "Ktp": "Ktp",
    "actividad_calculada": "Actividad calculada",
    "actividad_decaimiento": "Actividad por decaimiento",
}


class CorreccionImposible(ValueError):
    """Su mensaje va tal cual a un `QMessageBox`: en castellano, sin
    símbolos (DA-18)."""


def datos_con_correccion(datos, columna, valor):
    """Diccionario NUEVO (no toca `datos`) con la clave de `columna`
    reemplazada por `valor`. `conversion`/`intensidad` se convierten con
    `float()`, como el formulario -- rechaza `bool`, NaN, infinito y
    valores no numéricos, y la conversión cero (divisor de
    `actividad_fuente`). `fecha_cer` guarda el texto tal cual: la fecha la
    valida la cuenta (`resultados_desde_lo_guardado`), no aquí."""
    clave = COLUMNAS_QUE_RECALCULAN[columna]
    corregidos = dict(datos)
    if columna in ("conversion", "intensidad"):
        if isinstance(valor, bool):
            raise CorreccionImposible(f"{NOMBRES_LEGIBLES_COLUMNA[columna]} debe ser un número.")
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            raise CorreccionImposible(f"{NOMBRES_LEGIBLES_COLUMNA[columna]} debe ser un número.")
        if not math.isfinite(numero):
            raise CorreccionImposible(f"{NOMBRES_LEGIBLES_COLUMNA[columna]} debe ser un número.")
        if columna == "conversion" and numero == 0:
            raise CorreccionImposible("el factor de conversión no puede ser cero.")
        corregidos[clave] = numero
    else:
        corregidos[clave] = valor
    return corregidos


def hay_que_recalcular(datos, corregidos):
    """False si la entrada corregida no cambió DE VERDAD -- comparación
    numérica para los números (ya convertidos por `datos_con_correccion`:
    "13.65" y "13.650" llegan como el mismo `float`), exacta para el
    texto de `fecha_cer`."""
    return any(datos.get(clave) != corregidos.get(clave)
               for clave in COLUMNAS_QUE_RECALCULAN.values())


def resultados_desde_lo_guardado(datos):
    """RC.1 (`resultados_para_archivar`), con TODAS las entradas leídas de
    `datos` (el diccionario de `consulta_mesualBraq`, con la corrección ya
    aplicada) -- exactamente lo que archivaría volver a guardar: voltajes
    guardados, medidas guardadas por papel (no `promediosV`), la misma
    cuenta que el botón Guardar."""
    alto, bajo, negativo = datos["lecturas"]
    # Puede lanzar VoltajesInvalidos (es un ValueError) -- se deja
    # propagar tal cual: `corregir_calibracion` la trata igual que
    # CorreccionImposible.
    v_alto = voltaje_de_texto(alto[0])
    v_bajo = voltaje_de_texto(bajo[0])

    def _promedio(bloque):
        try:
            m1, m2, m3 = (float(m) for m in bloque[1])
        except (TypeError, ValueError):
            raise CorreccionImposible(
                "una de las medidas guardadas de LECTURAS DEL MÁXIMO no es "
                "un número; no se puede recalcular.")
        return promedio_de_medidas(m1, m2, m3)

    prom_alto = _promedio(alto)
    prom_bajo = _promedio(bajo)
    prom_negativo = _promedio(negativo)

    try:
        return resultados_para_archivar(
            prom_alto, prom_bajo, prom_negativo,
            datos["t"], datos["p"], datos["t0"], datos["p0"],
            datos["calibracion_camara"], datos["calibracion_electrometro"],
            datos["conversion"], datos["fecha_cer"], datos["fecha_cal"],
            datos["intensidad"], v_alto=v_alto, v_bajo=v_bajo)
    except ZeroDivisionError:
        raise CorreccionImposible("una lectura guardada vale cero.")
    except ValueError:
        raise CorreccionImposible(
            f"la fecha del certificado ({datos['fecha_cer']!r}) o la fecha "
            f"de la calibración ({datos['fecha_cal']!r}) no tiene el "
            f"formato AAAA-MM-DD hh:mm:ss; no se puede recalcular.")


def lineas_antes_despues(archivado, nuevos):
    """[(columna, antes, después), ...] de las cinco cifras que cambian (o
    no), con el NOMBRE DE COLUMNA tal cual (Ks, Kp, Ktp,
    actividad_calculada, actividad_decaimiento) -- es lo que archiva el
    `detalle` de la auditoría (§RC.2 del plan, ejemplo literal). El
    diálogo de confirmación traduce a `NOMBRES_LEGIBLES_RESULTADOS` por su
    cuenta; esta función no lo hace, para no atar la auditoría a un texto
    pensado para la pantalla."""
    return [(clave, archivado[clave], nuevos[clave])
            for clave in RESULTADOS_ARCHIVADOS]
