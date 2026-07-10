from data.GraficasyTablas.calculadora_dosis_Tablas import *
from services.dosis_service_calculations import *
from data.ManejoDatos.conection import ruta_base_datos
import sqlite3
from typing import Optional, Dict, List
class DosisService():
    
    
    @staticmethod
    def calcular_dwref(Ndwq0, Mq, kqq0):
        return Dwref_calc(Ndwq0, Mq, kqq0)
    
    @staticmethod
    def dwqzmax_calc(Dwref, pd):
        return Dwqzmax_calc(Dwref,pd)
    
    @staticmethod
    def dwqz(Dwref, pdd_elec):
        return Dwqz(Dwref, pdd_elec)
    
    @staticmethod
    def dwqzmaxSAD_calc(dwqz,tmr_sad):
        return DwqzmaxSAD_calc(dwqz,tmr_sad)
    
    @staticmethod
    def calcular_mq_elec(M1, ktp, kpol, ks):
        return calcular_mq_electrones(M1, ktp, kpol, ks)
    def calcular_mq_fot(M1, ktp, kpol, ks):
        return calcular_mq_fotones(M1, ktp, kpol, ks)
    
    @staticmethod
    def calcular_mq(modo, **params):
        if modo == "fotones":
            return calcular_mq_fotones(
                params["M1"],
                params["ktp"],
                params["kpol"],
                params["ks"]
            )

        elif modo == "electrones":
            return calcular_mq_electrones(
                params["M1"],
                params["ktp"],
                params["kpol"],
                params["ks"],
                params["hs"]
            )

        else:
            raise ValueError("Modo de radiación inválido")
        
    @staticmethod
    def cociente_ldv1_um(ldv1, um):
        return cociente_LDV1_UM(ldv1, um)
    
    @staticmethod
    def factor_tp(t, p, t_0, p_0):
        return factor_ktp(t, p, t_0, p_0)
    
    @staticmethod
    def factor_k_polaridad(Mplus, Mminus):
        return factor_polaridad(Mplus, Mminus)

    @staticmethod
    def cociente_V1V2(v1, v2):
        return cociente_v1v2(v1, v2)
    @staticmethod
    def cociente_M1M2(m1, m2):
        return cociente_m1m2(m1, m2)
    
    @staticmethod
    def obtener_coeficientes_ks(modo, cociente_v1v2):
        if modo not in COEFICIENTES_KS:
            raise ValueError("Modo invalido")

        tabla = COEFICIENTES_KS[modo]

        # interpolar devuelve un dict {"a0":..., "a1":..., "a2":...}
        a0, a1, a2 = interpolar_coeficientes_ks(tabla, cociente_v1v2)

        return round(a0,6), round(a1,6), round(a2,6)
    @staticmethod
    def Ks_factor(a0,a1,a2, m1m2):
        return ks_factor(a0,a1,a2, m1m2)
    @staticmethod
    def get_AQ(camara_ionizacion):
        if camara_ionizacion in Q0_TABLE:
            A = Q0_TABLE[camara_ionizacion].get("A")
            Q = Q0_TABLE[camara_ionizacion].get("Q0")
            #print(camara_ionizacion)
            return A, Q
        else:
            return 0,0
    @staticmethod   
    def get_ab(camara_ionizacion):
        if camara_ionizacion in Q0_FIT_TABLE:
            a = Q0_FIT_TABLE[camara_ionizacion].get("a")
            b = Q0_FIT_TABLE[camara_ionizacion].get("b")
            return a, b
        else:
            return 0, 0
    @staticmethod
    def calcular_Q0(pdd20, pdd10):
        return charge(pdd20, pdd10)
    @staticmethod
    def calculate_chargefactor(Q0, Q, A):
        return quality_kq0(Q0, Q, A)
    @staticmethod
    def calculate_chargefactor_tprbased(tpr2010, a, b):
        return KQ_TPR2010_BASED(tpr2010, a, b)
    
    @staticmethod
    def r50_quality(R50):
        return beam_quality_r50(R50)
    
    @staticmethod
    def r50_depth(r50):
        return zref_r50(r50)
    
    @staticmethod
    def camara_tiene_kq(camara, protocolo="2000"):
        """True si el modelo tiene coeficientes kQ(TPR20,10) en la tabla del protocolo.

        Guarda de la Fase D2: parte del inventario activo (N31014, N31022,
        N34001, TN34001) aún no tiene fila en la tabla; la UI usa esto para
        avisar y dejar el kQ en ingreso manual en vez de fallar. Al completar
        una tabla la guarda se desactiva sola para ese modelo.

        `protocolo`: "2000" (TRS-398 original, default) o "rev1" (TRS-398
        Rev.1, Fase K2). Protocolo desconocido -> KeyError (fallo ruidoso).
        """
        return camara in KQ_TABLAS_POR_PROTOCOLO[protocolo]

    @staticmethod
    def camara_tiene_kq_electrones(camara, protocolo="2000"):
        """True si el modelo tiene fila kQ(R50) en la tabla de ELECTRONES del
        protocolo. Guarda paralela a camara_tiene_kq (que es de fotones): la
        UI la usa para dejar el kQ de electrones en ingreso manual cuando la
        cámara no tiene datos, en vez de interpolar la tabla equivocada.
        """
        return camara in Q0_R50_TABLAS_POR_PROTOCOLO[protocolo]

    @staticmethod
    def interpolar_r50(camara, r50, protocolo="2000"):
        """Interpola kQ(R50) para ELECTRONES desde la tabla del protocolo.

        Corregido en la auditoría 2026-07-09: leía KQ_TPR_TABLE (la tabla de
        FOTONES, indexada por TPR20,10 0.50-0.84) — cualquier R50 clínico
        (1-20 g/cm2) caía fuera de rango y devolvía el kQ del borde en
        silencio. Ahora lee Q0_R50_TABLAS_POR_PROTOCOLO: "2000" (Cuadro 18,
        default, valida las 53 hojas de electrones del corpus 2024 con dif.
        máx. 0.0006%) o "rev1" (Table 20). Protocolo desconocido -> KeyError.
        """
        datos = Q0_R50_TABLAS_POR_PROTOCOLO[protocolo][camara]

        xf = sorted(datos.keys())
        yf = [datos[x] for x in xf]
        if r50 < xf[0]:
            return yf[0]
        if r50 > xf[-1]:
            return yf[-1]
        for i in range(len(xf)-1):
            if xf[i] <= r50 <= xf[i+1]:
                x0, x1 = xf[i], xf[i+1]
                y0, y1 = yf[i], yf[i+1]
                
                kq_factor = y0 + (y1-y0)*(r50-x0)/(x1-x0)
                kq = round(kq_factor, 5)
                return kq
        
    @staticmethod
    def interpolar_kq0(camara, r50, protocolo="2000"):
        """Interpola kQ(TPR20,10) para fotones desde la tabla del protocolo.

        `protocolo`: "2000" (TRS-398 original, default, validado en D3 contra
        hoja real) o "rev1" (TRS-398 Rev.1, Fase K2, provisional). Protocolo
        desconocido -> KeyError (fallo ruidoso, no degradar en silencio).
        """
        datos = KQ_TABLAS_POR_PROTOCOLO[protocolo][camara]

        xf = sorted(datos.keys())
        yf = [datos[x] for x in xf]
        if r50 < xf[0]:
            return yf[0]
        if r50 > xf[-1]:
            return yf[-1]
        for i in range(len(xf)-1):
            if xf[i] <= r50 <= xf[i+1]:
                x0, x1 = xf[i], xf[i+1]
                y0, y1 = yf[i], yf[i+1]
                
                kq_factor = y0 + (y1-y0)*(r50-x0)/(x1-x0)
                kq = round(kq_factor, 4)
                return kq
    DB_NAME = "BaseDatosQA.db"  # se conserva solo por compatibilidad; la ruta real la resuelve ruta_base_datos()

    @classmethod
    def _get_connection(cls):
        """Get database connection"""
        return sqlite3.connect(ruta_base_datos())
    
    @classmethod
    def crear_tabla(cls):
        """Create the dosimetry table if it doesn't exist"""
        try:
            conn = cls._get_connection()
            cursor = conn.cursor()
            conn.commit
            query = """
                CREATE TABLE IF NOT EXISTS calculadora_dosimetrica (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    Fecha TEXT,
                    Acelerador TEXT,
                    equipo_id INTEGER,
                    Modelo_equipo TEXT,
                    Numero_serie TEXT,
                    factor_calibracion TEXT,
                    Tamano_campo TEXT,
                    Tipo_de_radiacion TEXT,
                    Tipo_de_escaneo TEXT,
                    Tipo_de_medicion TEXT,
                    temperatura TEXT,
                    presion TEXT,
                    Humedad_calibracion TEXT,
                    temp_clinica TEXT,
                    presion_clinica TEXT,
                    Humedad_relativa TEXT,
                    ktp TEXT,
                    lectura_Q1 TEXT,
                    lectura_Q2 TEXT,
                    lectura_Q3 TEXT,
                    lectura_dosimetro TEXT,
                    unidades_monitor TEXT,
                    cociente_ldv1_um TEXT,
                    Mplus TEXT,
                    Lectura_neg_1 TEXT,
                    Lectura_neg_3 TEXT,
                    Lectura_neg_2 TEXT,
                    Lectura_neg_prom TEXT,
                    Kpol TEXT,
                    tension_v1 TEXT,
                    tension_v2 TEXT,
                    cociente_tensiones TEXT,
                    lectura_m1 TEXT,
                    lectura_m2_1 TEXT,
                    lectura_m2_2 TEXT,
                    lectura_m2_3 TEXT,
                    lectura_m2 TEXT,
                    cociente_lecturas TEXT,
                    a0 TEXT,
                    a1 TEXT,
                    a2 TEXT,
                    ks TEXT,
                    Mq TEXT,
                    Zref TEXT,
                    Zmax TEXT,
                    Kq_0 TEXT,
                    Dzref TEXT,
                    pdd20 TEXT,
                    pdd10 TEXT,
                    pddzref TEXT,
                    tmrzref TEXT,
                    dosis_maxima TEXT,
                    protocolo_trs398 TEXT DEFAULT '2000',
                    r50_medido TEXT,
                    pdd_zref_electrones TEXT
                )
            """

            cursor.execute(query)
            cls._asegurar_columna(cursor, "calculadora_dosimetrica",
                                   "protocolo_trs398", "TEXT DEFAULT '2000'")
            # E4 (auditoría 2026-07-10): faltaban columnas para persistir el
            # R50 medido y el PDD de electrones -- cargar_datos_desde_db no
            # tenía de dónde restaurarlos (ver hallazgo en CLAUDE.md/plan E4).
            cls._asegurar_columna(cursor, "calculadora_dosimetrica",
                                   "r50_medido", "TEXT")
            cls._asegurar_columna(cursor, "calculadora_dosimetrica",
                                   "pdd_zref_electrones", "TEXT")
            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error creating table: {e}")
            return False

    @staticmethod
    def _asegurar_columna(cursor, tabla, columna, ddl):
        """Migración mínima idempotente: agrega la columna si no existe.

        Patrón del proyecto para cambios de esquema (no hay sistema de
        migraciones, deuda conocida): `CREATE TABLE IF NOT EXISTS` solo cubre
        bases de datos nuevas; las existentes (como copias de producción ya
        desplegadas) necesitan un ALTER TABLE explícito. Con DEFAULT
        constante, SQLite hace que las filas ya existentes devuelvan ese
        valor al leerse sin necesidad de un UPDATE.
        """
        cols = [c[1] for c in cursor.execute(f"PRAGMA table_info('{tabla}')").fetchall()]
        if columna not in cols:
            cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {ddl}")
    
    @classmethod
    def guardar_datos(cls, datos: Dict) -> bool:
        """
        Save dosimetry data to database
        
        Args:
            datos: Dictionary containing all dosimetry measurements
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure table exists
            cls.crear_tabla()
            
            conn = cls._get_connection()
            cursor = conn.cursor()
            
            # Prepare data for insertion
            columnas = list(datos.keys())
            valores = list(datos.values())
            
            # Create query with placeholders
            placeholders = ', '.join(['?'] * len(valores))
            query_insert = f"""
                INSERT INTO calculadora_dosimetrica ({', '.join(columnas)}) 
                VALUES ({placeholders})
            """
            
            cursor.execute(query_insert, valores)
            conn.commit()
            conn.close()
            
            print(f"Data saved successfully for date: {datos.get('Fecha', 'Unknown')}")
            return True
            
        except Exception as e:
            print(f"Error saving to database: {e}")
            return False
    
    @classmethod
    def buscar_por_fecha(cls, fecha: str, acelerador: str):
        """
        Search for dosimetry data by date and optionally by equipment ID
        
        Args:
            fecha: Date in format 'dd/MM/yyyy' or similar
            equipo_id: Optional equipment ID to filter results
            
        Returns:
            Dict with dosimetry data if found, None otherwise
        """
        try:
            conn = cls._get_connection()
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            if acelerador is not None:
                query = """
                    SELECT * FROM calculadora_dosimetrica 
                    WHERE Fecha = ? AND Acelerador = ?
                    ORDER BY id DESC
                    LIMIT 1
                """
                cursor.execute(query, (fecha, acelerador))
            else:
                query = """
                    SELECT * FROM calculadora_dosimetrica 
                    WHERE Fecha = ?
                    ORDER BY id DESC
                    LIMIT 1
                """
                cursor.execute(query, (fecha,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                # Convert Row object to dictionary
                return dict(row)
            else:
                print(f"No data found for date: {fecha}")
                return None
                
        except Exception as e:
            print(f"Error searching database: {e}")
            return None
    
    @classmethod
    def obtener_fechas_disponibles(cls, acelerador):
        """
        """
        try:
            conn = cls._get_connection()
            cursor = conn.cursor()
            
            if acelerador is not None:
                query = """
                    SELECT DISTINCT Fecha FROM calculadora_dosimetrica 
                    WHERE Acelerador = ?
                    ORDER BY id DESC
                """
                cursor.execute(query, (acelerador,))
            else:
                query = """
                    SELECT DISTINCT Fecha FROM calculadora_dosimetrica 
                    ORDER BY id DESC
                """
                cursor.execute(query)
            
            fechas = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            return fechas
            
        except Exception as e:
            print(f"Error getting available dates: {e}")
            return []
    
    @classmethod
    def eliminar_por_id(cls, id: int) -> bool:
        """
        Delete a dosimetry record by ID
        
        Args:
            id: Record ID to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = cls._get_connection()
            cursor = conn.cursor()
            
            query = "DELETE FROM calculadora_dosimetrica WHERE id = ?"
            cursor.execute(query, (id,))
            
            conn.commit()
            conn.close()
            
            print(f"Record {id} deleted successfully")
            return True
            
        except Exception as e:
            print(f"Error deleting record: {e}")
            return False
    
    @classmethod
    def actualizar_datos(cls, id: int, datos: Dict) -> bool:
        """
        Update an existing dosimetry record
        
        Args:
            id: Record ID to update
            datos: Dictionary with updated values
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = cls._get_connection()
            cursor = conn.cursor()
            
            # Build SET clause
            set_clause = ', '.join([f"{key} = ?" for key in datos.keys()])
            valores = list(datos.values())
            valores.append(id)  # Add ID for WHERE clause
            
            query = f"UPDATE calculadora_dosimetrica SET {set_clause} WHERE id = ?"
            cursor.execute(query, valores)
            
            conn.commit()
            conn.close()
            
            print(f"Record {id} updated successfully")
            return True
            
        except Exception as e:
            print(f"Error updating record: {e}")
            return False
    
    
    