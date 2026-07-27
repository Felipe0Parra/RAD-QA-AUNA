from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
from PyQt5.QtWidgets import (QWidget, QToolBox, QVBoxLayout, QHBoxLayout, QPushButton)
from data.ManejoDatos.load import loadtablacomplex
from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
# P1 (PLAN_P1_POOL_CONEXIONES_27-07.md): la clase con estado que vivía aquí
# fue reemplazada por la fachada sin estado de services/db_pool.py.
from services.db_pool import DatabaseManager


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
        
        