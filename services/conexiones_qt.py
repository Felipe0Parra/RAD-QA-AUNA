"""SN1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-SN1): conexión única de señal.

Hallado en el rebuild del 19-08: `mostrar_resultados_AnalisisImagen`
(`seiscientos_mensual.py`) conecta `self.guardar_analisis.clicked` a
`self.guardar_analisis_e_imagen` bajo una guarda `hasattr` -- el widget no se
recrea, pero el método que lo conecta se vuelve a llamar cada vez que se
analiza una imagen. Cada llamada AÑADE una conexión nueva encima de las
anteriores, así que N análisis seguidos + un solo clic en "Guardar" disparan
N guardados y N filas de auditoría (medido: 3 análisis, 3 filas en
`audit_log`, 3 generaciones en `analisis_placa_franjas` por un solo clic).

El censo de la sesión encontró 315 `connect` sin `disconnect` fuera de
métodos de construcción única en todo el árbol -- la mayoría son
construcción legítima (un `connect` dentro de `__init__`/`setupUi`, que
corre una sola vez). Este helper NO los reemplaza a todos: es para el patrón
específico -- señal guardada en `self`, conectada dentro de un método
alcanzable más de una vez -- donde acumular conexiones es un defecto, no una
inicialización.
"""


def conectar_unico(senal, slot):
    """Conecta `slot` a `senal` garantizando que sea la ÚNICA conexión hacia
    ese slot exacto: desconecta cualquier conexión previa hacia `slot` antes
    de crear la nueva.

    `senal.disconnect(slot)` desconecta solo las conexiones hacia ESE slot
    (no toca las de otros slots sobre la misma señal); si no había ninguna
    -- el caso normal la primera vez que se llama -- PyQt5 lanza
    `TypeError`, que aquí es el caso esperado, no un error.
    """
    try:
        senal.disconnect(slot)
    except TypeError:
        pass
    senal.connect(slot)
