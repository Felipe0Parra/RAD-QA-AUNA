from data.ManejoDatos.conection import Conexion
class EquiposService:

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
        """Obtiene las series disponibles para un modelo específico"""
        con = Conexion().con
        cur = con.cursor()

        sql = """
        SELECT id, equip_type, model, serie, calibr_fact, t_cal, p_cal, h_cal
        FROM equipos
        WHERE model = ?
        ORDER BY serie
        """

        cur.execute(sql, (model,))
        filas = cur.fetchall()
        cur.close()

        columnas = ["id", "equip_type", "model", "serie",
                    "calibr_fact", "t_cal", "p_cal", "h_cal"]

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