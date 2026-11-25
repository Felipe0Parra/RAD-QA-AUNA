"""El orden cronológico de `controles.fecha` en las listas de controles: lo más reciente arriba.

Una sola definición para todas las listas. El texto que se ve no cambia: solo se lee para ordenar.
"""
import re
from datetime import date

# Una fecha con otra forma va al final de la lista y nunca da error.
DESCONOCIDA = (0, 0, 0)

_FORMAS = (
    re.compile(r"(?P<d>[0-9]{1,2})/(?P<m>[0-9]{1,2})/(?P<a>[0-9]{4})"),
    re.compile(r"(?P<m>[0-9]{1,2})/(?P<a>[0-9]{4})"),
    re.compile(r"(?P<a>[0-9]{4})-(?P<m>[0-9]{1,2})-(?P<d>[0-9]{1,2})"),
    re.compile(r"(?P<a>[0-9]{4})-(?P<m>[0-9]{1,2})"),
)


def clave_cronologica(texto):
    """(año, mes, día) de «dd/mm/aaaa», «d/m/aaaa», «mm/aaaa», «aaaa-mm» o «aaaa-mm-dd»; sin día, el día es 0."""
    if not isinstance(texto, str):
        return DESCONOCIDA
    for forma in _FORMAS:
        hallada = forma.fullmatch(texto)
        if hallada is None:
            continue
        partes = hallada.groupdict()
        anio, mes, dia = int(partes["a"]), int(partes["m"]), int(partes.get("d") or 0)
        try:
            date(anio, mes, dia if "d" in partes else 1)
        except ValueError:
            return DESCONOCIDA
        return (anio, mes, dia)
    return DESCONOCIDA


def mas_reciente_primero(filas, indice_fecha):
    """Las filas de la fecha más reciente a la más vieja; con la misma fecha conservan el orden en que llegaron."""
    return sorted(filas, key=lambda fila: clave_cronologica(fila[indice_fecha]), reverse=True)
