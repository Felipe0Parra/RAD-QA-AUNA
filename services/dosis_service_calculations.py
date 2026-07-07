import numpy as np

# Dosis en profundidad de referencia
def Dwref_calc(Ndwq0, Mq, kqq0):
    return round(Ndwq0*Mq*kqq0,7)
#Dosis en profundidad maxima  
def Dwqzmax_calc(Dwref,pd):
    if pd==0:
        return 0
    else:
        return round(100*Dwref/pd,7)
    
# Dosis pero para electrones y SSD 
def Dwqz(Dwref, pdd_elec):
    if pdd_elec==0:
        return 0
    else:
        return round(100*Dwref/pdd_elec,7)
#Dosis maxima para geometría SAD     
def DwqzmaxSAD_calc(dwqz,tmr_sad):
    if tmr_sad==0:
        return 0
    else:
        return round(dwqz/tmr_sad, 6)

def calcular_mq_fotones(M1, ktp, kpol, ks):
    ke = 1
    mq = M1 * ktp * ke * kpol * ks
    return round(mq, 6)


def calcular_mq_electrones(M1, ktp, kpol, ks):
    ke = 1
    mq = M1 * ktp * ke * kpol  * ks
    return round(mq, 4)

    
def cociente_LDV1_UM(ldv1, um):
    if um==0:
        return 0
    else:
        cociente_ldv1um = round(ldv1/um, 6)
        return round(cociente_ldv1um,5)
        
def factor_ktp(t, p, t_0, p_0):
    kpt = (273.2+t)*p_0/((273.2+t_0)*p)
   
    return round(kpt,4)
 
        

def factor_polaridad(Mplus, Mminus):
    if Mplus==0:
        return 0
    else: 
        factor = (abs(Mplus)+abs(Mminus))/(2*Mplus)
        factor = round(factor, 5)
        return round(factor,5)
def cociente_v1v2(v1, v2):
    if v2==0:
        return 0
    else: 
        cociente = v1/v2
        cociente = round(cociente, 4)
        return round(cociente,5)
    
def cociente_m1m2(m1, m2):
    if m2==0:
        return 0
    else: 
        cociente = m1/m2
        cociente = round(cociente, 4)
        return round(cociente,5)


def ks_factor(a0,a1,a2, cocientem1m2):
    ks = a0 + a1*cocientem1m2 + a2*cocientem1m2**2
    ks = round(ks, 4)
    return ks
   
def interpolar_coeficientes_ks(tabla, c):
    xs = np.array(sorted(tabla.keys()))

    if not (xs.min() <= c <= xs.max()):
        raise ValueError(
            f"Cociente fuera de rango ({xs.min()} – {xs.max()})"
        )

    a0s = np.array([tabla[x]["a0"] for x in xs])
    a1s = np.array([tabla[x]["a1"] for x in xs])
    a2s = np.array([tabla[x]["a2"] for x in xs])

    a0 = np.interp(c, xs, a0s)
    a1 = np.interp(c, xs, a1s)
    a2 = np.interp(c, xs, a2s)

    return a0, a1, a2

def charge(PDD_20, PDD_10):
    if PDD_10 != 0:
        Q = 1.2661*(PDD_20/PDD_10) - 0.0595
        return round(Q,5)
    else:
        return 0

def quality_kq0(Q0, Q, A):
    quality_charge_factor_num = 1 + np.exp(A*(0.57-Q0))
    quality_charge_factor_den = 1 + np.exp(A*(Q-Q0))
    if quality_charge_factor_den != 0:
        K_q0 = quality_charge_factor_num/quality_charge_factor_den
        return round(K_q0,5)
    else:
        return 0 
     
def get_AQ(camara_ionizacion):
    if camara_ionizacion in Q0_TABLE:
        A = Q0_TABLE[camara_ionizacion].get("A")
        Q = Q0_TABLE[camara_ionizacion].get("Q0")
        return A, Q
    else:
        return 0

def get_ab(camara_ionizacion):
    if camara_ionizacion in Q0_FIT_TABLE:
        a = Q0_FIT_TABLE[camara_ionizacion].get("a")
        b = Q0_FIT_TABLE[camara_ionizacion].get("b")
        return a, b
    else:
        return 0, 0
    
def KQ_TPR2010_BASED(tpr2010, a, b):
    KqTPR2010_num = (1+np.exp((a-0.57)/b))
    KqTPR2010_dem = (1+np.exp((a-tpr2010)/b))
    if KqTPR2010_dem != 0:
        KqTPR2010 = KqTPR2010_num/KqTPR2010_dem
        return round(KqTPR2010,5)
    else:
        return 0

def beam_quality_r50(R50):
    beam_quality = 1.029*R50-0.06 
    return round(beam_quality,4)

def zref_r50(R50):
    zref_ref50 = 0.6*R50-0.1
    return round(zref_ref50,4)