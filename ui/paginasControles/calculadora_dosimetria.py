import numpy as np 
import matplotlib.pyplot as plt 
import PyQt5
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QLineEdit, QMessageBox, QApplication
import sys
# class IxCalculator():
#     def __init__(self, maquina, ionization_chamber, electrometer, energy, beam_quality, reference_distance, kT_P,dosimeter_reading, polarizing_voltage, calibration_depth, calibration_pressure, calibration_temp, calibration_humidity, actual_temp, actual_pressure, electrometer_k, M_plus, M_minus, polarity, beam_type, M_1, M_2, k_electro):
#         self.maquina = maquina
#         self.ionization_chamber = ionization_chamber
#         self.electrometer = electrometer
#         self.energy = energy
#         self.beam_quality = beam_quality
#         self.reference_distance = reference_distance
#         self.kT_P = kT_P
        
#         self.polarizing_voltage = polarizing_voltage
#         self.calibration_depth = calibration_depth
#         self.calibration_pressure = calibration_pressure
#         self.calibration_temp = calibration_temp
#         self.calibration_humidity = calibration_humidity
#         self.actual_temp = actual_temp
#         self.actual_pressure = actual_pressure
#         self.electrometer_k = electrometer_k
#         self.dosimeter_reading = dosimeter_reading
      
#         # Polarity correction
#         self.M_plus = M_plus 
#         self.M_minus = M_minus
#         # Polarity 
#         self.polarity = bool(polarity)
#         # Beam type: pulsed - pulsed scanned
#         self.beam_type = beam_type
#         self.M_1 = M_1
#         self.M_2 = M_2
#         self.k_electro = k_electro
    
#     def calibration_kTP_calculation(self):
#         self.calibrationKTP = ((273.2+self.actual_temp)*(self.calibration_pressure))/((273.2+self.calibration_temp)*(self.actual_pressure))
#         return self.calibrationKTP
#     def calibration_KPol_calculation(self):
#         self.monitor_units_M1 = self.dosimeter_reading/self.monitor_units_M1
#         self.k_PolQ0 = (abs(self.M_plus)+abs(self.M_minus))/(2*self.M_plus)
#         return self.k_PolQ0
#     def recombination_ks(self):
        
#         if self.beam_type=='pulsed':
#             a_0 = 1.1980
#             a_1 = -0.8753
#             a_2 = 0.6773
#             self.Ksfactor = a_0 + a_1*(self.M_1/self.M_2)+a_2*(self.M_1/self.M_2)**2
#             return self.Ksfactor
#         elif self.beam_type=='pulsed-scanned':
#             a_0 = 2.0010
#             a_1 = -2.4020
#             a_2 = 1.4040
#             self.Ksfactor = a_0 + a_1*(self.M_1/self.M_2)+a_2*(self.M_1/self.M_2)**2
#             return self.Ksfactor
#     def corrected_dos_v1(self):
#         self.MQ_V1 = self.M_1 * self.k_PolQ0 * self.k_electro * self.kT_P * self.Ksfactor
            
    

class DialogCalculadoraDosis(QDialog):
    def __init__(self, datos_calibracion, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.setWindowTitle("Calculadora de dosis de referencia")
        self.dosis_calculada = None
        
        self.temp, self.pressure = QLineEdit(), QLineEdit()
        self.temp.setPlaceholderText("Temperatura (°C)");self.pressure.setPlaceholderText("Presión (KPa)")
        layout.addWidget(self.temp);layout.addWidget(self.pressure)
        
        
       
        
        
        self.lbl_info = QLabel("Calculadora de dosis de referencia")
        layout.addWidget(self.lbl_info)
        
        self.btn_calcular = QPushButton("Calcular dosis")
        self.btn_calcular.clicked.connect(self.calcular)
        
        self.btn_ok = QPushButton("Aceptar")
        self.btn_ok.clicked.connect(self.accept)
        
        layout.addWidget(self.btn_calcular);layout.addWidget(self.btn_ok)
         
        self.datos = datos_calibracion
        self.visualize_calib = QLineEdit()
        self.visualize_calib.setText("")
        layout.addWidget(self.visualize_calib)
        
        
        
        
    
    def calcular(self):
        try:
            t = float(self.temp.text())
            p = float(self.pressure.text())
            self.dosis_calculada = self.calcular_dosis(t,p, self.datos)
            self.lbl_info.setText(f"Dosis calculada: {self.dosis_calculada}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Se produjo error: {e}")
    def calcular_dosis(self, temperatura, presion, datos):
        if temperatura == 0 or presion==0:
            QMessageBox.critical(self, "Error", "Ingrese valores válidos")
            return 0
        q = temperatura*presion*datos
        return q
        
if __name__=='__main__':
    App = QApplication(sys.argv)
    ventana = DialogCalculadoraDosis(1.25)
    ventana.show()
    sys.exit(App.exec_())
    
    
        
        
    
        
        
         
        
        