"""Nombres canónicos de acelerador (B3-N, PLAN_AUDITORIA_DOS_EJES_21-07.md §7.7b).

La calculadora usa códigos cortos internos -- "IX"/"Hc"/"Seiscientos"
(dialogs.py, deducidos en el constructor de DialogCalculadoraDosis) -- y
`controles.equipo` usa nombres más largos pero con una inconsistencia de
mayúsculas ("Clinac ix", con la "ix" en minúscula). El físico pidió que
ambas tablas muestren el nombre MÁS COMPLETO: "Clinac iX".

Decisión de arquitectura (2026-07-21, confirmada por el físico): NO se
reescribe el histórico de `controles.equipo`. Son datos de producción y
decenas de puntos del código comparan por igualdad literal contra
"Clinac ix"/"Clinac 600"/"Halcyon" (ix_mensual.py, ix_anual.py, load.py,
seiscientos_mensual.py, entre otros); reescribir el histórico exigiría
auditar y actualizar cada uno de esos puntos como una migración aparte.
En su lugar, `nombre_canonico()` normaliza al comparar/mostrar, sin tocar
la base de datos.
"""

NOMBRES_CANONICOS = {
    "seiscientos": "Clinac 600",
    "clinac 600": "Clinac 600",
    "ix": "Clinac iX",
    "clinac ix": "Clinac iX",
    "hc": "Halcyon",
    "halcyon": "Halcyon",
}


def nombre_canonico(nombre):
    """Nombre canónico ("Clinac 600" / "Clinac iX" / "Halcyon") para
    cualquier variante conocida (código corto de la calculadora o texto
    histórico de `controles.equipo`).

    Si `nombre` no es una variante reconocida (p. ej. "Tomógrafo", fuera del
    dominio de la calculadora), o no es un string no vacío (None, "", o un
    id numérico de otro catálogo colado por error -- caso real:
    dialogs.py pasa combo_series.currentData(), un id entero, a
    obtener_fechas_disponibles), se devuelve sin cambios -- nunca lanza ni
    inventa un valor.
    """
    if not nombre or not isinstance(nombre, str):
        return nombre
    return NOMBRES_CANONICOS.get(nombre.strip().lower(), nombre)


def mismo_acelerador(nombre_a, nombre_b):
    """True si `nombre_a` y `nombre_b`, tras canonizar, son el mismo acelerador."""
    return nombre_canonico(nombre_a) == nombre_canonico(nombre_b)
