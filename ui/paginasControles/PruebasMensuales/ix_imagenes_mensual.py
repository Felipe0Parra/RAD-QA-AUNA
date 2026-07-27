from ui.paginasControles.PruebasMensuales.seiscientos_mensual import PruebaMensual600
from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
from PyQt5.QtWidgets import (QWidget, QToolBox, QVBoxLayout, QHBoxLayout, QPushButton)
from data.ManejoDatos.load import loadtablacomplex
from ui.paginasControles.PruebasMensuales.tac_mensual import PruebaMensualTAC
# P1 (PLAN_P1_POOL_CONEXIONES_27-07.md): la clase con estado que vivía aquí
# fue reemplazada por la fachada sin estado de services/db_pool.py.
from services.db_pool import DatabaseManager


class PruebaImagenesIX(PruebaMensualTAC):
    def __init__(self, user_id, ref=None):
        print("PruebaImagenesIX  __init__ called")
        self.esiX_images_mensu = True
        
        self.db_manager = DatabaseManager()
        self.equipo_f = "Clinac ix"
        self.img_analysis = True
        print(self.equipo_f)
        print("ENTRANDO A PRUEBA IMAGENES IX")
       
        super().__init__(user_id)
        self.ref = ref
        self.ref_ix_img = ref  # Ahora recibe el ref compartido
        print(f"PruebaImagenesIX received ref: {self.ref_ix_img}")
        
        