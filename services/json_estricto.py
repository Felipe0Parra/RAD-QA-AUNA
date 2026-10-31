"""CD.4 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, CD4-D1): la ÚNICA puerta estricta de los JSON que se guardan en la base (D1-PROD-03), compartida por el análisis mensual (`services/placa_mensual.py`, que la
nombra `_json_estricto` y le pone su `PlacaMensualError`) y la calibración de la curva de dosis (`services/curva_dosis.py`, con su `CurvaDosisError`).

`json.dumps` escribe NaN e infinito como `NaN` e `Infinity`, que no son JSON (SQLite `json_valid` da 0 y un lector estricto los rechaza), y no serializa un escalar de numpy: sin esta puerta un valor así
llegaría a la base como una columna que la tabla documenta como JSON y no se puede leer de vuelta. Vivía en `services/placa_mensual.py` (D.1); se subió aquí, con el mismo texto, para que la calibración
no la copie ni importe el servicio del mensual. Sin Qt ni base."""
import json


def json_estricto(valor, columna, error=ValueError, **opciones):
    """El texto JSON de `valor` para la columna `columna` (`opciones`: las de `json.dumps`, p. ej. `sort_keys`), o `error` -- y no se escribe nada -- si no cabe en JSON VÁLIDO: un número no finito (NaN
    o infinito) o un valor que JSON no admite (un escalar de numpy, un objeto). `error` es la clase con que lo dice cada servicio (por omisión `ValueError`); el texto es siempre el mismo."""
    try:
        return json.dumps(valor, allow_nan=False, **opciones)
    except (TypeError, ValueError) as fallo:
        raise error(f"lo que se guarda en la columna '{columna}' no es JSON válido ({fallo}): hay un número no finito (NaN o infinito) o un valor que JSON no admite") from fallo
