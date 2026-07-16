from data.ManejoDatos.conection import Conexion
class EquiposService:

    # H2.10 (PLAN_FASE_H, 2026-07-16): subquery correlacionado que define la
    # fila ACTUAL de una serie como "la vigente de mayor id si existe alguna
    # vigente, si no la de mayor id sin más". Reemplaza el antiguo patrón
    # `id IN (SELECT MAX(id) FROM equipos GROUP BY serie)` usado en
    # braquiterapia.py/braq_mensual.py, que ignoraba `vigente` por completo:
    # con datos sucios (duplicados, correcciones que dejan una fila vieja con
    # id más alto marcada histórica) esa consulta podía elegir una fila
    # inactiva y hacer desaparecer un equipo entero del selector (caso real:
    # el pozo A972662 desapareció de braquiterapia tras el saneamiento H2.6
    # porque la fila de mayor id de esa serie quedó `activo=0`). Se
    # correlaciona por equip_type+serie (no por serie sola) para no mezclar
    # series que coincidan entre tipos de equipo distintos.
    _FILA_ACTUAL = """id = (
            SELECT e2.id FROM equipos e2
            WHERE e2.equip_type = e1.equip_type AND e2.serie = e1.serie
            ORDER BY e2.vigente DESC, e2.id DESC
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
        """Series de un modelo con (serie, activo, vigente) de su fila
        ACTUAL (ver _FILA_ACTUAL)."""
        con = Conexion().con
        cur = con.cursor()

        sql = f"""
        SELECT serie, activo, vigente FROM equipos e1
        WHERE equip_type = ? AND model = ? AND {EquiposService._FILA_ACTUAL}
        """

        cur.execute(sql, (equip_type, model))
        filas = cur.fetchall()
        cur.close()
        return filas

    @staticmethod
    def calibracion_actual(equip_type, model, serie):
        """Datos de calibración de la fila ACTUAL de una serie (ver
        _FILA_ACTUAL), o None si no existe ninguna fila para esa serie."""
        con = Conexion().con
        cur = con.cursor()

        sql = f"""
        SELECT calibr_fact, t_cal, p_cal, h_cal, fecha_calibr, vigente, activo
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
                    "fecha_calibr", "vigente", "activo"]
        return dict(zip(columnas, fila))

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
        """Obtiene lista de modelos únicos"""
        con = Conexion().con
        cur = con.cursor()

        sql = """
        SELECT DISTINCT model, equip_type
        FROM equipos
        ORDER BY equip_type, model
        """

        cur.execute(sql)
        filas = cur.fetchall()
        cur.close()

        return [{"model": fila[0], "equip_type": fila[1]} for fila in filas]
    
    @staticmethod
    def obtener_series_por_modelo(model):
        """Obtiene las series disponibles para un modelo específico.

        Incluye fecha_calibr/vigente (2026-07-09): un mismo número de serie
        puede tener varias filas históricas (recalibraciones) con factores
        distintos, y el combo de la calculadora no tenía forma de
        distinguirlas -- se veían idénticas salvo por el factor real.
        """
        con = Conexion().con
        cur = con.cursor()

        sql = """
        SELECT id, equip_type, model, serie, calibr_fact, t_cal, p_cal, h_cal,
               fecha_calibr, vigente
        FROM equipos
        WHERE model = ?
        ORDER BY serie, vigente DESC
        """
        # OJO: NO ordenar por fecha_calibr -- es TEXT en formato "dd/MM/yyyy"
        # con ceros a la izquierda inconsistentes en los datos reales
        # ("05/02/2024" vs "5/02/2024"); un ORDER BY de esa columna compara
        # lexicográficamente y NO refleja orden cronológico real (p. ej.
        # "5/02/2024" ordenaría antes que "21/07/2025" por empezar con "5").
        # "vigente" es un flag booleano limpio (0.0/1.0): confiable para
        # traer primero la calibración vigente sin fingir orden por fecha.

        cur.execute(sql, (model,))
        filas = cur.fetchall()
        cur.close()

        columnas = ["id", "equip_type", "model", "serie",
                    "calibr_fact", "t_cal", "p_cal", "h_cal",
                    "fecha_calibr", "vigente"]

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