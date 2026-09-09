"""R2 (PLAN_REPORTES_LEGIBLES_08-09.md): declaración ÚNICA de qué le pasa
a cada columna de las 4 tablas diarias que NO viene del
`diccionario_invertido` de la pantalla (esas ya se muestran, con su
unidad -- R4). El resto de columnas de `PRAGMA table_info` de las 4
tablas debe caer en exactamente una de estas tres categorías, o el censo
de `tests/test_r1_r6_reportes_diarios_legibles.py (TestR2CensoColumnasDiario)` se pone rojo pidiendo que
alguien decida -- ninguna columna nueva puede aparecer sola en un PDF
firmado, ni desaparecer, sin que quede escrito aquí.

Vive en su propio módulo (no en `models/PDF/reportes.py`, aunque el plan
lo nombra así) porque `pdf.py` necesita leerlo para saber qué columnas
mover a la tabla de R6 y cuáles retirar -- y `reportes.py` ya importa
`pdf.py`, así que un import en el sentido contrario sería circular.
`reportes.py` re-exporta estos tres nombres para que siga siendo cierto
que la declaración se consulta "desde `models/PDF/reportes.py`"."""

# "identificación" -- comunes a las 4, ya se descartaban antes de este
# plan (el PDF las muestra en su cabecera, no en la tabla).
COLUMNAS_IDENTIFICACION = {"id", "date", "user_id"}

# "movida a otra tabla del reporte" -- sale de la tabla principal porque
# R6 la muestra en la suya propia: `promedio`/`desviacion` en la tabla de
# resumen del análisis, `pelicula` como la imagen de la placa.
COLUMNAS_MOVIDAS_A_OTRA_TABLA = {
    "braqui": {"promedio", "desviacion", "pelicula"},
}

# "retirada por decisión del físico" -- nombradas explícitamente por él:
# 07-09 (`distancias`/`desplazamientos` y sus dos estadísticos, en braqui),
# 08-09 (`activo`, en las 4 -- es la marca de anulación/soft-delete,
# contabilidad interna, no una prueba de control), 09-09 (`umbral_relativo`
# y `distancia_minima`, los parámetros con que corrió el análisis de la
# placa -- "no quiero incluir... esos detalles técnicos del análisis").
COLUMNAS_RETIRADAS = {
    "aceleradorlineal_600": {"activo"},
    "aceleradorlineal_ix": {"activo"},
    "halcyon": {"activo"},
    "braqui": {
        "distancias", "desplazamientos", "promedio_des", "desviacion_des",
        "activo", "umbral_relativo", "distancia_minima",
    },
}


def columnas_no_reportables(tabla):
    """Unión de lo retirado y lo movido para `tabla` -- lo que NO debe
    aparecer como fila cruda en la tabla principal del diario."""
    return (COLUMNAS_RETIRADAS.get(tabla, set())
            | COLUMNAS_MOVIDAS_A_OTRA_TABLA.get(tabla, set()))
