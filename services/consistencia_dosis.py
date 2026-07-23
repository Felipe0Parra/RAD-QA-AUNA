"""B3.7 (PLAN_AUDITORIA_DOS_EJES_21-07.md §7.7f): chequeo de consistencia
entre `calculadora_dosimetrica` (la calculadora) y `dosimetriaMen` (el oro
transcrito del PTW). SOLO REPORTA -- nunca escribe en `dosimetriaMen`, que
es el patrón oro y no debe tocarse.

Compara, para cada fila de `dosimetriaMen`, la dosis del cálculo VIGENTE de
`calculadora_dosimetrica` para la misma (acelerador canónico, energía, mes)
-- reutiliza `DosisService.buscar_vigente_del_mes`, la misma consulta que
usa el botón "Cargar cálculo" (B3-e) -- contra `dosis_ref_cgy_um`.

Unidades (hallazgo H11 del rebuild 22-07-2026, §8.5 del plan): la
calculadora guarda `dosis_maxima` en Gy/UM y `dosimetriaMen.dosis_ref_cgy_um`
está en cGy/UM (factor 100). El físico decidió explícitamente NO agregar
columnas nuevas para esto -- la conversión se hace aquí, al comparar, sin
tocar el motor de cálculo ni el esquema de ninguna tabla.
"""
import sqlite3

from data.ManejoDatos import conection as _conection
from services.dosis_service import DosisService
from services.nombres_acelerador import nombre_canonico
from services.fechas_control import mes_anio_de_fecha as _mes_anio_de_fecha

TOLERANCIA_DEFECTO = 0.03  # 3%, del mismo orden que tolerancia_dosis real


def verificar_consistencia(mes=None, anio=None, tolerancia=TOLERANCIA_DEFECTO):
    """Lista de comparaciones, una por fila de `dosimetriaMen` con energía y
    dosis registradas. `mes`/`anio`: filtro opcional (None = todo el
    histórico).

    Cada elemento es un dict:
        ref, acelerador, energia, mes, anio,
        dosis_dosimetriamen_cgy_um,
        dosis_calculadora_cgy_um (None si no hay vigente para esa clave/mes),
        discrepancia_pct (None si no hay con qué comparar),
        dentro_de_tolerancia (None si no hay con qué comparar).

    Nunca lanza por una fila individual rara (dosis no numérica, fecha sin
    formato reconocible) -- la salta y sigue con las demás; es un reporte
    de auditoría, no debe caerse por un dato sucio aislado.
    """
    con = sqlite3.connect(_conection.ruta_base_datos())
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("""
        SELECT d.ref, d.energia, d.dosis_ref_cgy_um, c.equipo, c.fecha
        FROM dosimetriaMen d
        JOIN controles c ON c.id = d.ref
        WHERE d.energia IS NOT NULL AND d.dosis_ref_cgy_um IS NOT NULL
        ORDER BY d.ref
    """)
    filas = cur.fetchall()
    con.close()

    resultados = []
    for fila in filas:
        mes_fila, anio_fila = _mes_anio_de_fecha(fila["fecha"])
        if mes_fila is None:
            continue
        if mes is not None and mes_fila != mes:
            continue
        if anio is not None and anio_fila != anio:
            continue

        try:
            dosis_men = float(fila["dosis_ref_cgy_um"])
        except (TypeError, ValueError):
            continue

        acelerador = nombre_canonico(fila["equipo"])
        vigente = DosisService.buscar_vigente_del_mes(
            acelerador, fila["energia"], mes_fila, anio_fila)

        entrada = {
            "ref": fila["ref"], "acelerador": acelerador, "energia": fila["energia"],
            "mes": mes_fila, "anio": anio_fila,
            "dosis_dosimetriamen_cgy_um": dosis_men,
            "dosis_calculadora_cgy_um": None,
            "discrepancia_pct": None,
            "dentro_de_tolerancia": None,
        }

        if vigente is not None:
            try:
                dosis_calc = float(vigente.get("dosis_maxima")) * 100
            except (TypeError, ValueError):
                resultados.append(entrada)
                continue
            if dosis_men:
                entrada["dosis_calculadora_cgy_um"] = dosis_calc
                entrada["discrepancia_pct"] = abs(dosis_calc - dosis_men) / dosis_men
                entrada["dentro_de_tolerancia"] = entrada["discrepancia_pct"] <= tolerancia

        resultados.append(entrada)

    return resultados
