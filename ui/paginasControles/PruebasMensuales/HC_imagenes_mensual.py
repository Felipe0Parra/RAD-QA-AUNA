from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
from PyQt5.QtWidgets import (QWidget, QToolBox, QVBoxLayout, QHBoxLayout, QPushButton)
from data.ManejoDatos.load import loadtablacomplex
from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
from data.ManejoDatos.conection import Conexion

class DatabaseManager:
    _instance = None
    _connections = {}
    _max_connections = 5
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def obtener_conexion(self):
        """Obtiene una conexión reutilizable del pool"""
        try:
            for conn_id, conn in self._connections.items():
                if conn and not conn.in_transaction:
                    return conn
            
            if len(self._connections) < self._max_connections:
                conn = Conexion().conectar()
                conn_id = id(conn)
                self._connections[conn_id] = conn
                return conn
            else:
                # Usar la primera conexión disponible
                return next(iter(self._connections.values()))
        except Exception as e:
            print(f"Error al obtener conexión: {e}")
            return Conexion().conectar()
    
    def cerrar_conexiones(self):
        """Cierra todas las conexiones del pool"""
        for conn in self._connections.values():
            try:
                if conn:
                    conn.close()
            except:
                pass
        self._connections.clear()
class PruebaImagenesHC(PruebaMensualTAC):
    def __init__(self, user_id, ref=None):
        print("PruebaImagenesHC  __init__ called")
        self.esHC_images_mensu = True
        
        self.db_manager = DatabaseManager()
        self.equipo_f = "Halcyon"
        self.img_analysis_HC = True
        print(self.equipo_f)
        print("ENTRANDO A PRUEBA IMAGENES HC")
       
        super().__init__(user_id)
        self.ref = ref
        self.ref_HC_img = ref  # Ahora recibe el ref compartido
        print(f"PruebaImagenesHC received ref: {self.ref_HC_img}")
        
        