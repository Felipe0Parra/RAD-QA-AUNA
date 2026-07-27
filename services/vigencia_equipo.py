"""V1 (PLAN_AUDITORIA_DOS_EJES_21-07.md SS7.5): vigencia de un equipo relativa
a una fecha de referencia arbitraria, no siempre "hoy".

Antes de V1, `ui/paginasGuia/equipos.py::verificar_vigencia_equipo` solo
comparaba `fecha_calibr` contra `QDate.currentDate()`, y el selector de
series del formulario mensual/anual (`seiscientos_mensual.py::
setEquipoSeleccionado`) marcaba "vencido" leyendo el flag `vigente`
**congelado** en la columna de `equipos` (calculado una sola vez, con la
fecha de ESE momento, al insertar/editar la fila). Ninguna de las dos rutas
comparaba contra la fecha del CONTROL que se está llenando -- por eso una
cámara que venció hace poco aparecía "vencida" aunque el control se hiciera
(con fecha pasada) cuando aún estaba vigente.

`es_vigente_en_fecha` es la misma regla (años de vigencia por tipo de
equipo), parametrizada por `fecha_referencia` en vez de asumir siempre hoy.
Función de SOLO LECTURA: no consulta ni escribe la BD, no depende de
`equipos.vigente`. Quien la llama decide qué fecha usar como referencia
(hoy, o la fecha del control del formulario).
"""
from PyQt5.QtCore import QDate

# Mismos valores que ui/paginasGuia/equipos.py::Config.__init__ (única
# fuente ahora; ese módulo importa este diccionario en vez de duplicarlo).
VIGENCIA_ANOS_POR_TIPO = {
    "Cámara de ionización": 2,
    "Cámara de pozo": 2,
    "Electrómetro": 2,
    "Barómetro": 1,
    "Termohigrómetro": 1,
    "Detector Rad.": None,
}


def es_vigente_en_fecha(fecha_calibr, tipo_equipo, fecha_referencia):
    """True si la calibración `fecha_calibr` (texto "dd/MM/yyyy") de un
    equipo de tipo `tipo_equipo` seguía vigente en `fecha_referencia`
    (QDate).

    Replica los mismos valores por defecto que `verificar_vigencia_equipo`
    (sin fecha, tipo desconocido, vigencia_anos=None, o fecha con formato
    inválido -> se considera vigente) para no cambiar ningún caso ya
    aceptado, solo la fecha contra la que se compara.
    """
    if not fecha_calibr or tipo_equipo not in VIGENCIA_ANOS_POR_TIPO:
        return True

    vigencia_anos = VIGENCIA_ANOS_POR_TIPO[tipo_equipo]
    if vigencia_anos is None:
        return True

    try:
        dia, mes, anio = map(int, fecha_calibr.split('/'))
        fecha_cal = QDate(anio, mes, dia)
        diferencia_dias = fecha_cal.daysTo(fecha_referencia)
        return diferencia_dias <= (365 * vigencia_anos)
    except (ValueError, AttributeError):
        return True
