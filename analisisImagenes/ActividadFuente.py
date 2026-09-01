import numpy as np
from datetime import datetime
from zoneinfo import ZoneInfo #Para manejo de zonas horarias

# T1 (PLAN_BRAQUI_ACTIVIDAD_CONFIABLE_28-08.md): única vida media del Ir-192
# para toda la app. 73.827 d es el valor NNDC/IAEA; el diario usaba 73.83
# (ese valor redondeado) y el mensual/CalcularActividad/load.py usaban 74.2,
# que no corresponde a ningún valor aceptado -- divergían hasta 1.416% a 300
# días contra una tolerancia del 3%. Ningún llamador debe volver a pasar un
# literal: o se omite el parámetro, o se pasa esta constante por nombre.
VIDA_MEDIA_IR192_DIAS = 73.827

def factores_correccion(V_300prom,Vn_300prom, V_150prom, t, p, t0,p0):
    #print("     ● Ingresa al cálculo de los factores de corrección")
    Ks = (4/3) - V_300prom / (3*V_150prom)  # Factor de corrección para la cámara de pozo
    Kpol = (1 + (np.abs(V_300prom/ Vn_300prom)))/2  # Factor de corrección para el polarímetro
    Ktp = ((t + 273.15)/(t0 + 273.15)) * (p0/p)  # Factor de corrección para temperatura, presión y humedad

    return Ks,Kpol,Ktp

def actividad_fuente(Ks, Kpol, Ktp, calibracion_camara,calibracion_electrometro, conversion, V_300prom,):
    ##print("     ● Ingresa al cálculo de la actividad fuente")
    print(f"Actividad fuente: {(V_300prom)*Ks*Ktp*(calibracion_camara)*(calibracion_electrometro)*Kpol*((1/conversion)*(1/37))}")
    print(f"Ks: {Ks} ")
    print(f"Ktp: {Ktp} ")
    print(f"calibracion camara: {calibracion_camara} ")
    print(f"calibracion electrometro: {calibracion_electrometro} ")
    print(f"KPol: {Kpol} ")
    print(f"Conversion: {conversion}")
    return (V_300prom)*Ks*Ktp*(calibracion_camara*1e-5)*(calibracion_electrometro*1e8)*Kpol*((1/conversion)*(1/37))

def error_porcentual(ref, A, dec):
    #print("     ● Ingresa al cálculo del error porcentual")

    e_dec = round(np.abs((A - dec) / dec)*100, 2)

    e = round(np.abs((ref-dec)/dec)*100, 2)
    return e, e_dec

def graficar_resultados(canvas=None, posiciones=None, promedio=None): 
    if canvas is None or posiciones is None or promedio is None:
        #print("Faltan datos")
        return
    fig = canvas.figure
    fig.clear()

    ax = fig.add_subplot(111)
    ax.plot(posiciones, promedio, marker='o', linestyle='--', color='purple', label='Promedio (nA)')

    ax.set_title('Máximo de la Cámara')
    ax.set_xlabel('Distancia (mm)')
    ax.set_ylabel('Medida promedio (nA)')
    ax.grid(True)
    ax.legend()

    fig.tight_layout()
    canvas.draw()

def generar_reporte(Ks, Kpol, Ktp, A, e, dec, e_dec,ref):
    reporte = []
    reporte.append("<b>Factores de corrección:</b>")
    reporte.append(f"&emsp;&emsp;K<sub>s</sub> = {Ks:.3f}")
    reporte.append(f"&emsp;&emsp;K<sub>pol</sub> = {Kpol:.3f}")
    reporte.append(f"&emsp;&emsp;K<sub>pt</sub> = {Ktp:.3f}")
    #reporte.append("<br>")
    reporte.append(f"<b>La Actividad reportada en el monitor es:</b> A<sub>m</sub> = {ref:.3f} Ci")
    reporte.append(f"<b>La Actividad de la fuente calculada es:</b> A = {A:.5f} Ci")
    reporte.append(f"<b>La Actividad luego del decaimiento es:</b> A<sub>f</sub> = {dec:.3f} Ci")
    reporte.append("<b>Errores porcentuales:</b>")

    reporte.append(f"&emsp;&emsp; Entre la A<sub>f</sub> y A<sub>m</sub>: %&epsilon; = {e:.3f} %")
    reporte.append(f"&emsp;&emsp; Entre la A<sub>f</sub> y A: %&epsilon; = {e_dec:.3f} %")

    return reporte
def calcular_decaimiento(fecha_inicio_str, fecha_fin_str, actividad_inicial, vida_media_dias=VIDA_MEDIA_IR192_DIAS):
    #print("     ● Ingresa al cálculo del decaimiento")
    """
    Calcula la actividad después del decaimiento,
    convirtiendo fecha de inicio de CET/CEST a COT.
    """
    formato = "%Y-%m-%d %H:%M:%S"

    # Definir zonas horarias
    tz_cet = ZoneInfo("Europe/Berlin")   # fecha de inicio (certificado en CET)
    tz_cot = ZoneInfo("America/Bogota")  # fecha final y cálculo en COT

    # Parsear inicio como CET y convertir a COT
    fecha_inicio_cet = datetime.strptime(fecha_inicio_str, formato).replace(tzinfo=tz_cet)
    fecha_inicio = fecha_inicio_cet.astimezone(tz_cot)

    # Parsear fin directamente como COT
    fecha_fin = datetime.strptime(fecha_fin_str, formato).replace(tzinfo=tz_cot)

    print(f"Fecha Inicio CET: {fecha_inicio_cet} (Fecha del certificado)")
    print(f"Fecha Inicio convertido a COT: {fecha_inicio}")
    print(f"Fecha Final COT: {fecha_fin}")

    # Calcular el tiempo en horas correctamente
    delta = fecha_fin - fecha_inicio
    horas = delta.total_seconds() / 3600

    # Calcular lambda
    vida_media_horas = vida_media_dias * 24
    lam = np.log(2) / vida_media_horas
    print(f"Horas transcurridas desde {fecha_fin_str}: {horas}")
    print(f"Dias transcurridos: {horas/(24)}")
    actividad_final = actividad_inicial * np.exp(-lam * horas)

    ##print(f"Tiempo en horas (fecha_fin - fecha_inicio): {horas}")
    return actividad_final

def CalcularActividad(V_300prom,Vn_300prom, V_150prom, t, p, t0,p0, calibracion_camara,calibracion_electrometro, conversion,ref,intensidad, fecha_inicio_str, fecha_fin_str):
    #print("\n-----------------------------------------------------------------------")
    #print("          Actividad de la fuente (Mensual de braquiterapia)\n")

    Ks, Kpol, Ktp = factores_correccion(V_300prom,Vn_300prom, V_150prom, t, p, t0,p0)

    A = actividad_fuente(Ks, Kpol, Ktp, calibracion_camara,calibracion_electrometro, conversion, V_300prom)
    
    dec_valor = calcular_decaimiento(fecha_inicio_str, fecha_fin_str, intensidad)

    e, e_dec = error_porcentual(ref, A, dec_valor)

    reporte = generar_reporte(Ks, Kpol, Ktp, A, e, dec_valor, e_dec, ref)
    #print("-----------------------------------------------------------------------")
    return reporte

def graficar_linealidad(canvas=None, tp=None, tf=None): 
    if canvas is None or tp is None or tf is None:
        #print("Faltan datos")
        return

    fig = canvas.figure
    fig.clear()

    ax = fig.add_subplot(111)
    ax.plot(tf, tp, marker='o', linestyle='--', color='purple')

    ax.set_title('Linealidad de la Fuente')
    ax.set_ylabel('Tiempo Efectivo (s)')
    ax.set_xlabel('Tiempo de Parada (s)')
    ax.grid(True)

    fig.tight_layout()
    canvas.draw()
