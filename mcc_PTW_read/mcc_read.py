"""
Este código busca leer de manera los archivos mcc que son generados por el software
PTW, con el cual se realizan los controles de calidad de los aceleradores 

-Leer archivo .mcc
 -Encontrar titulos BEGIN DATA, END DATA (generalmente son 3 pares)
 -Guardar información entre BEGIN DATA y END DATA
 -Generar los perfiles del haz, primero el descalibrado, luego el organizado
 -SI

-Juan Pablo Cárdenas
"""

from pylinac.core.profile import FWXMProfile, SingleProfile, FlatnessDifferenceMetric, FlatnessRatioMetric,SymmetryPointDifferenceMetric
from pylinac import FieldAnalysis, Protocol
import numpy as np 
from pylinac.metrics.profile import *
import pandas as pd 
import os
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QMessageBox

class read_mcc():
    def __init__(self):
        super().__init__()
        self.EXPECTED_MAX_DOSE_RATE = None
        self.lines_0 = []
        self.lines_1 = []
        self.lines_2 = []
        
    
    def load(self, file):
        self.procesar_mcc(file)
        self.pylinac_analysis(file)
        
        
        
    def procesar_mcc(self, file):
        """
        Funcion save_mcc:
            -Args: fichero
            -Output: filas de los datos obtenidos
        
        """
        copy = False
        copy_2 = False
        in_scan_1 = False
        in_scan_2 = False
        copy_3 = False
        in_scan_3 = False
        self.radiation_type = None
        self.energy_value=None
        
        # VARIABLES DEL SISTEMA

        with open(file) as f:
            # PARA SCAN 1
            for line in f:
                line=line.strip()
                #print(line)
                if line.startswith("ENERGY"):
                    self.energy_value = float(line.split("=")[1])
                if line.startswith("MODALITY"):
                    self.radiation_type = line.split("=")[1].strip().upper()
                if line.startswith("DETECTOR_HV"):
                    self.voltaje = float(line.split("=")[1])
                if line.split("=")[0]=="EXPECTED_MAX_DOSE_RATE":
                    self.EXPECTED_MAX_DOSE_RATE = float(line.split("=")[1])
                if line.startswith("BEGIN_SCAN") and "1" in line:
                    in_scan_1 = True
                    continue
                if in_scan_1 and line.startswith("BEGIN_DATA"):
                    copy=True
                    continue
                if in_scan_1 and line.startswith("END_DATA"):
                    copy=False
                if in_scan_1 and line.startswith("END_SCAN") and "1" in line:
                    in_scan_1 = False
                    continue
                if in_scan_1 and copy:
                    line=line.replace("\t", " ")
                    self.lines_0.append(line) 
                # SCAM 2
                if line.startswith("BEGIN_SCAN") and "2" in line:
                    in_scan_2 = True
                    continue
                if in_scan_2 and line.startswith("BEGIN_DATA"):
                    copy_2=True
                    continue
                if in_scan_2 and line.startswith("END_DATA"):
                    copy_2=False
                if in_scan_2 and line.startswith("END_SCAN") and "2" in line:
                    in_scan_2 = False
                    continue
                if in_scan_2 and copy_2:
                    line=line.replace("\t", " ")
                    self.lines_1.append(line)   
                # SCAN 3
                if line.startswith("BEGIN_SCAN") and "3" in line:
                    in_scan_3 = True
                    continue
                if in_scan_3 and line.startswith("BEGIN_DATA"):
                    copy_3=True
                    continue
                if in_scan_3 and line.startswith("END_DATA"):
                    copy_3=False
                if in_scan_3 and line.startswith("END_SCAN") and "3" in line:
                    in_scan_3 = False      
                    break
                if in_scan_3 and copy_3:
                    line=line.replace("\t", " ")
                    self.lines_2.append(line)
                                 
        self.pos, self.depth_calib, self.dose =self.convert_to_float(self.lines_0) # PDD
        self.pos_1, self.depth_calib_1, self.dose_1 =self.convert_to_float(self.lines_1) # INPLANE
        self.pos_2, self.depth_calib_2, self.dose_2 = self.convert_to_float(self.lines_2) # CROSSPLANE
        
        self.energia = self.normalizar_energia(self.energy_value, self.radiation_type)
        
    def convert_to_float(self, line):
        
        positions = []
        depth_calibration = []
        depth = []
        for i in line:
            position, depth_calib, depth_real = i.split()
            positions.append(float(position))
            depth_calibration.append(float(depth_calib))
            depth.append(float(depth_real))
        return positions, depth_calibration, depth
    
    def normalizar_energia(self, energy, radiation):
        if energy is None or radiation is None:
            raise ValueError("No se pudo detectar energía o tipo de radiación")

        energy_int = int(round(energy))

        if radiation == "X":
            return f"{energy_int}mv"
        elif radiation == "EL":
            return f"{energy_int}mev"
        else:
            raise ValueError(f"Tipo de radiación desconocido: {radiation}")
    
    def pylinac_analysis(self, file):
        my_mcc = pymcc.readmcc.read_file(file)
        # -------- PDD --------
        z = np.array(self.pos)        # profundidad (mm)
        dose = np.array(self.depth_calib)
        mcc_dict = {}
        for i in my_mcc:
            mcc_dict[i.curve_type] = i.calc_results()

        # provide object dict for composite tests
        read_mcc_6x_10x10 = mcc_dict
        print("Datos completos: ", mcc_dict)
        flatness = read_mcc_6x_10x10["PDD"]["R50"]["R50"]
        print(" FWHM ",flatness)
        
        

        #pdd = FWXMProfile(values=dose, x_values=z)
        # pdd.filter(size=5, kind="gaussian")

        dose = dose / dose.max() * 100
        
    
        print("ENERGÍA:", self.energia)
        
        #print("dmax =", round(dmax,2), "mm")
        # pdd.compute(metrics=[PDD(depth_mm=10)])
        # pdd.compute(metrics=[PDD(depth_mm=20)])
        
        ### 
        """ 
        Si la energia es mev, entonces es analisis de electrones
            No buscar pdd, buscar el 50% de la dosis maxima
        Si la energia es mv, entonces es analisis de fotones
            Buscar pdds
        """
        if self.energia.endswith("mev"):
            half_dose = dose.max() / 2

        # buscar donde cruza
            idx = np.argmin(np.abs(dose - half_dose))
            print("Posicion r50", idx)
            print("Dosis en r50: ", dose[idx] )
            print("Profundidad: ", z[idx])
            
            pdd1 = FWXMProfile(values=dose, x_values=z)
            pdd1.plot()
            
            

            
            
                        
      
      

        
        
        
       
        

        # # -------- INPLANE --------
        # x = np.array(self.pos_1)
        # prof_in = np.array(self.depth_calib_1)
        # prof_in = prof_in / prof_in.max() * 100

        # inplane = FWXMProfile(values=prof_in, x_values=x)
        # inplane.filter(size=2, kind = "gaussian")
        # symmetry_in =inplane.compute(metrics=[SymmetryPointDifferenceMetric(in_field_ratio=0.6)])
        # flatness_in = inplane.compute(metrics=[FlatnessRatioMetric(in_field_ratio=0.8)])
       
        # # print("Flatness ratio",inplane.compute(metrics=[FlatnessRatioMetric(in_field_ratio=0.6)]))       
        
        # #-------- CROSSPLANE --------#
        # ycross = np.array(self.pos_2)
        # prof_cross = np.array(self.depth_calib_2)
        # crossplane = FWXMProfile(values=prof_cross, x_values=ycross)
        # symmetry_cross = crossplane.compute(metrics=[SymmetryPointDifferenceMetric(in_field_ratio=0.8)])
        # flatness_cross = crossplane.compute(metrics=[FlatnessRatioMetric(in_field_ratio=0.8)])
        # crossplane.plot()
        
        # self.mcc_results = {"simetria_inplane": symmetry_in, "planicidad_inplane": flatness_in, "simetria_crossplane": symmetry_cross, "planicidad_crossplane": flatness_cross}
       
        
    

    
   


""" 
Para el PDD se usa una relación sencilla, que es la dosis a 20 sobre la dosis a 10
PDD = 100 D20/D10
"""
    
        
        
        
        
print(0.1+0.2) 
        
# if __name__=='__main__':
#     mcc = read_mcc()
#     mcc.load(r"C:\Users\juanp\Documents\Documents\EAFIT\S8\AUNA\IX\Octuɢre\E06 APP10X10 10X10 PDDCRIN WAT 251013 13'49'53.mcc")
#     #lineas = mcc.return_profile_data()


    
    
    
    
    