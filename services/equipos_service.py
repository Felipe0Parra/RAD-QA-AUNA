from data.ManejoDatos.conection import Conexion
class EquiposService:

    # H2.10 (PLAN_FASE_H, 2026-07-16): subquery correlacionado que define la
    # fila ACTUAL de una serie. Reemplaza el antiguo patrón
    # `id IN (SELECT MAX(id) FROM equipos GROUP BY serie)` usado en
    # braquiterapia.py/braq_mensual.py, que ignoraba `vigente`/`activo` por
    # completo: con datos sucios (duplicados, correcciones que dejan una fila
    # vieja con id más alto marcada histórica) esa consulta podía elegir una
    # fila inactiva y hacer desaparecer un equipo entero del selector (caso
    # real: el pozo A972662 desapareció de braquiterapia tras el saneamiento
    # H2.6 porque la fila de mayor id de esa serie quedó `activo=0`). Se
    # correlaciona por equip_type+serie (no por serie sola) para no mezclar
    # series que coincidan entre tipos de equipo distintos.
    #
    # F8 (PLAN_F_CIERRE_ESTANDAR_29-07.md §8.4/§9): la regla original
    # (`vigente DESC, id DESC`) confiaba en `equipos.vigente`, una columna
    # que se calcula UNA sola vez al guardar (contra la fecha de ESE
    # momento) y luego queda congelada -- puede mentir para siempre
    # (verificado: 3 filas activas de la BD real dicen `vigente=1` con la
    # calibración vencida desde hace meses). Ahora la fila ACTUAL es,
    # simplemente, la de mayor id ENTRE LAS ACTIVAS -- sin vigente
    # (retirada del contrato, ver services/vigencia_equipo.py) ni fallback a
    # una fila inactiva. Verificado contra la BD real: coincide con la regla
    # H2.10 en todas las series existentes y además ya no exige el fallback
    # "ninguna vigente" (ahora innecesario: sin la columna vigente, "más
    # reciente entre las activas" es la única noción de fila actual).
    # Una serie sin ninguna fila activa (equipo retirado, p.ej. la Somer)
    # simplemente no tiene fila ACTUAL -- coherente con que ningún llamador
    # muestra ni usa datos de un equipo inactivo.
    _FILA_ACTUAL = """id = (
            SELECT e2.id FROM equipos e2
            WHERE e2.equip_type = e1.equip_type AND e2.serie = e1.serie
                  AND e2.activo = 1
            ORDER BY e2.id DESC
            LIMIT 1
        )"""

    @staticmethod
    def modelos_actuales(equip_type):
        """Modelos con al menos una serie activa en su fila ACTUAL (ver
        _FILA_ACTUAL). Reemplaza consultas `MAX(id) GROUP BY serie` que no
        respetaban `vigente`."""
        con = Conexion().con
        cur = con.cursor()

        sql = f"""
        SELECT DISTINCT model FROM equipos e1
        WHERE equip_type = ? AND activo = 1 AND {EquiposService._FILA_ACTUAL}
        ORDER BY model
        """

        cur.execute(sql, (equip_type,))
        modelos = [fila[0] for fila in cur.fetchall()]
        cur.close()
        return modelos

    @staticmethod
    def series_actuales(equip_type, model):
        """Series de un modelo con (serie, activo, fecha_calibr, equip_type)
        de su fila ACTUAL (ver _FILA_ACTUAL).

        F8 (PLAN_F_CIERRE_ESTANDAR_29-07.md §9): ya NO devuelve `vigente` --
        esa columna queda retirada del contrato de los servicios. Devuelve
        los HECHOS (fecha_calibr, equip_type) para que cada consumidor
        derive la vigencia con `services.vigencia_equipo.es_vigente_en_fecha
        (fecha_calibr, equip_type, fecha_referencia)` contra la fecha que
        corresponda (hoy, o la del control que se está llenando)."""
        con = Conexion().con
        cur = con.cursor()

        sql = f"""
        SELECT serie, activo, fecha_calibr FROM equipos e1
        WHERE equip_type = ? AND model = ? AND {EquiposService._FILA_ACTUAL}
        """

        cur.execute(sql, (equip_type, model))
        filas = cur.fetchall()
        cur.close()
        return [(serie, activo, fecha_calibr, equip_type)
                for serie, activo, fecha_calibr in filas]

    @staticmethod
    def calibracion_actual(equip_type, model, serie):
        """Datos de calibración de la fila ACTUAL de una serie (ver
        _FILA_ACTUAL), o None si no existe ninguna fila para esa serie.

        F8: ya no devuelve `vigente` (retirada del contrato); agrega
        `equip_type` (parámetro ya conocido por el llamador, pero incluido
        para que el dict sea autosuficiente) junto a `fecha_calibr`."""
        con = Conexion().con
        cur = con.cursor()

        sql = f"""
        SELECT calibr_fact, t_cal, p_cal, h_cal, fecha_calibr, activo
        FROM equipos e1
        WHERE equip_type = ? AND model = ? AND serie = ?
              AND {EquiposService._FILA_ACTUAL}
        """

        cur.execute(sql, (equip_type, model, serie))
        fila = cur.fetchone()
        cur.close()

        if fila is None:
            return None

        columnas = ["calibr_fact", "t_cal", "p_cal", "h_cal",
                    "fecha_calibr", "activo"]
        resultado = dict(zip(columnas, fila))
        resultado["equip_type"] = equip_type
        return resultado

    @staticmethod
    def obtener_por_calibracion(calib_fact):
        con = Conexion().con
        cur = con.cursor()

        sql = """
        SELECT id, equip_type, model, serie, calibr_fact, t_cal, p_cal, h_cal
        FROM equipos
        WHERE calibr_fact = ?
        """

        cur.execute(sql, (calib_fact,))
        fila = cur.fetchone()
        cur.close()

        if fila is None:
            return None

        columnas = ["id", "equip_type", "model", "serie",
                    "calibr_fact", "t_cal", "p_cal", "h_cal"]

        return dict(zip(columnas, fila))
    
    @staticmethod
    def obtener_modelos_unicos():
        """Obtiene lista de modelos únicos.

        F8 (PLAN_F_CIERRE_ESTANDAR_29-07.md §8.4, primer invariante de la
        doctrina de vigencia): filtra `activo = 1` -- un equipo anulado no
        debe ofrecerse en el combo de modelos de la calculadora (único
        consumidor). `activo` decide visibilidad; la vigencia se deriva
        aparte, contra la fecha que corresponda.
        """
        con = Conexion().con
        cur = con.cursor()

        sql = """
        SELECT DISTINCT model, equip_type
        FROM equipos
        WHERE activo = 1
        ORDER BY equip_type, model
        """

        cur.execute(sql)
        filas = cur.fetchall()
        cur.close()

        return [{"model": fila[0], "equip_type": fila[1]} for fila in filas]
    
    @staticmethod
    def obtener_series_por_modelo(model):
        """Obtiene las series disponibles para un modelo específico.

        Incluye fecha_calibr (2026-07-09): un mismo número de serie puede
        tener varias filas históricas (recalibraciones) con factores
        distintos, y el combo de la calculadora no tenía forma de
        distinguirlas -- se veían idénticas salvo por el factor real.

        E2 (PLAN_E_INTEGRIDAD_Y_PERMISOS_28-07.md §3): filtra `activo = 1`
        -- antes un equipo anulado seguía ofreciéndose en el combo de la
        calculadora de dosis (única lectura de este método) pese a haber
        desaparecido del catálogo de Equipos. Mismo criterio ya usado por
        modelos_actuales()/series_actuales() (H2.10) para braquiterapia. Un
        control histórico que ya referencia el equipo por id no pasa por
        aquí -- sigue resolviendo su fila sin este filtro.

        F8 (PLAN_F_CIERRE_ESTANDAR_29-07.md §8.4/§9): ya NO devuelve
        `vigente` (columna congelada, retirada del contrato de los
        servicios) ni ordena por ella. El llamador deriva la vigencia con
        `services.vigencia_equipo.es_vigente_en_fecha(fecha_calibr,
        equip_type, fecha_referencia)`.
        """
        con = Conexion().con
        cur = con.cursor()

        sql = """
        SELECT id, equip_type, model, serie, calibr_fact, t_cal, p_cal, h_cal,
               fecha_calibr
        FROM equipos
        WHERE model = ? AND activo = 1
        ORDER BY serie, id DESC
        """
        # OJO: NO ordenar por fecha_calibr -- es TEXT en formato "dd/MM/yyyy"
        # con ceros a la izquierda inconsistentes en los datos reales
        # ("05/02/2024" vs "5/02/2024"); un ORDER BY de esa columna compara
        # lexicográficamente y NO refleja orden cronológico real (p. ej.
        # "5/02/2024" ordenaría antes que "21/07/2025" por empezar con "5").
        # `id DESC` es un orden confiable (autoincremental) sin depender de
        # ninguna columna congelada.

        cur.execute(sql, (model,))
        filas = cur.fetchall()
        cur.close()

        columnas = ["id", "equip_type", "model", "serie",
                    "calibr_fact", "t_cal", "p_cal", "h_cal",
                    "fecha_calibr"]

        return [dict(zip(columnas, fila)) for fila in filas]
    
    @staticmethod
    def obtener_por_id(equipo_id):
        """Obtiene un equipo por su ID"""
        con = Conexion().con
        cur = con.cursor()

        sql = """
        SELECT id, equip_type, model, serie, calibr_fact, t_cal, p_cal, h_cal
        FROM equipos
        WHERE id = ?
        """

        cur.execute(sql, (equipo_id,))
        fila = cur.fetchone()
        cur.close()

        if fila is None:
            return None

        columnas = ["id", "equip_type", "model", "serie",
                    "calibr_fact", "t_cal", "p_cal", "h_cal"]

        return dict(zip(columnas, fila))