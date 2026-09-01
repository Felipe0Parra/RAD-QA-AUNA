"""T2 (PLAN_BRAQUI_ACTIVIDAD_CONFIABLE_28-08.md §Fase 0): "la zona horaria del
certificado: RESUELTA, correcta".

`calcular_decaimiento` (`analisisImagenes/ActividadFuente.py`) asume que
`fecha_inicio_str` (la fecha del certificado de la fuente) está en
`Europe/Berlin` y la convierte a `America/Bogota` antes de calcular el
decaimiento; `fecha_fin_str` se toma directamente en hora de Bogotá. El
físico confirmó el 28-08: *"el cálculo de la fecha del certificado está
bien"* -- la hora que teclea en `fecha_cer` viene tal cual del certificado
europeo del fabricante, sin convertir. El 0.274% de discrepancia que se
midió al considerar esta conversión NO es un sesgo: es la corrección
correcta, y quitarla introduciría el error.

No se toca el código (T2 es documentar + fijar con un test, no corregir
nada). Este test fija esa conversión como CONTRATO: si alguien la
"simplifica" más adelante creyendo que sobra, se pone rojo.

Caso conocido, verificable a mano: si `fecha_inicio_str` y `fecha_fin_str`
son la MISMA cadena literal, el único tiempo transcurrido que puede medir
`calcular_decaimiento` es el que introduce la conversión de zona horaria
-- ninguna otra fuente de delta existe en ese escenario. Berlín observa
horario de verano (CEST, UTC+2) en junio y horario estándar (CET, UTC+1)
en enero; Bogotá no tiene horario de verano (UTC-5 todo el año) -- el
desplazamiento resultante es de 7 h en junio y 6 h en enero, y este test
fija los dos."""
import numpy as np

from analisisImagenes.ActividadFuente import calcular_decaimiento


def _horas_transcurridas(fecha_str):
    """Con inicio == fin (misma cadena), despeja las horas transcurridas
    a partir de la fórmula de decaimiento -- sin depender de la vida
    media usada (T1), porque se resuelve algebraicamente por el propio
    log del cociente."""
    actividad_inicial = 10.0
    actividad_final = calcular_decaimiento(fecha_str, fecha_str, actividad_inicial)
    vida_media_horas = 73.827 * 24
    lam = np.log(2) / vida_media_horas
    horas = -np.log(actividad_final / actividad_inicial) / lam
    return horas


def test_junio_cest_desplaza_7_horas():
    # Berlín en junio: CEST = UTC+2. Bogotá: UTC-5. Desplazamiento = 7 h.
    horas = _horas_transcurridas("2026-06-05 11:36:24")
    assert abs(horas - 7.0) < 1e-6


def test_enero_cet_desplaza_6_horas():
    # Berlín en enero: CET = UTC+1. Bogotá: UTC-5. Desplazamiento = 6 h.
    horas = _horas_transcurridas("2026-01-15 09:00:00")
    assert abs(horas - 6.0) < 1e-6


def test_quitar_la_conversion_introduciria_el_sesgo_medido():
    """Confirma en números el hallazgo de DP-70: sobre una fuente real a
    ~84 días, ignorar la conversión (tratar el certificado como si ya
    estuviera en hora de Bogotá) cambia el resultado en la dirección y
    magnitud medidas -- por eso NO se retira la conversión."""
    actividad_inicial = 6.35  # Ci, del orden de las fuentes reales del proyecto
    fecha_cert = "2026-06-05 11:36:24"
    fecha_control = "2026-08-28 11:36:24"  # ~84 días después, misma hora de reloj

    con_conversion = calcular_decaimiento(fecha_cert, fecha_control, actividad_inicial)

    # Sin la conversión: se simula tratando el certificado como si ya
    # estuviera en hora de Bogotá -- se le suman las 7 h que la conversión
    # real le habría restado, para anular su efecto.
    from datetime import datetime, timedelta
    fecha_cert_sin_conversion = (
        datetime.strptime(fecha_cert, "%Y-%m-%d %H:%M:%S") + timedelta(hours=7)
    ).strftime("%Y-%m-%d %H:%M:%S")
    sin_conversion = calcular_decaimiento(fecha_cert_sin_conversion, fecha_control, actividad_inicial)

    diferencia_pct = abs(con_conversion - sin_conversion) / sin_conversion * 100
    assert diferencia_pct > 0.1, (
        "la conversión de zona horaria debe producir una diferencia "
        "medible frente a no aplicarla -- si da ~0, la conversión dejó "
        "de tener efecto y el contrato de T2 ya no está vigente")
