"""Formato único de fecha para `controles` (F1, PLAN_TPR_Y_FECHAS_MENSUAL_23-07.md).

`controles.fecha` convive hoy en dos formatos ("MM/yyyy" para los mensuales
nuevos, "dd/MM/yyyy" para 3 filas históricas de diciembre/2025) porque la
identidad de un control mensual se decidía comparando esa columna como texto
exacto -- ver `create_control` en `data/ManejoDatos/load.py`. La identidad
real de un control mensual es (equipo, mes, año, tipo); el día es un dato que
se muestra y se guarda, pero nunca debe ser parte de la llave de búsqueda.

Este módulo es la única fuente de verdad para: el formato de guardado/
visualización (F3, con día) y el parseo tolerante mes/año (ya usado antes de
esta tarea por `services/consistencia_dosis.py::_mes_anio_de_fecha`, que se
reutiliza aquí en vez de duplicarse -- mismo criterio que
`services/nombres_acelerador.py` en B3-N).
"""

FORMATO_FECHA_CONTROL = "dd/MM/yyyy"


def mes_anio_de_fecha(fecha):
    """Extrae (mes, anio) de `controles.fecha` -- tolera "MM/yyyy" (formato
    viejo, sin día) y "dd/MM/yyyy" (formato nuevo, F3): los dos últimos
    segmentos separados por "/" son siempre mes y año. (None, None) si el
    texto no tiene esa forma. Nunca lanza."""
    partes = (fecha or "").split("/")
    if len(partes) < 2:
        return None, None
    try:
        return int(partes[-2]), int(partes[-1])
    except ValueError:
        return None, None


def mismo_mes(fecha_a, fecha_b):
    """True si `fecha_a` y `fecha_b` caen en el mismo (mes, año), sin
    importar si alguna trae día y la otra no, ni el orden de los campos."""
    mes_a, anio_a = mes_anio_de_fecha(fecha_a)
    mes_b, anio_b = mes_anio_de_fecha(fecha_b)
    if mes_a is None or mes_b is None:
        return False
    return (mes_a, anio_a) == (mes_b, anio_b)
