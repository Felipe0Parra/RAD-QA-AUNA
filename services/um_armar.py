"""Arma los datos del haz (`um_motor.DatosHaz`) desde los archivos exportados de Eclipse. Sin Qt ni base."""
import contextlib
import re
from dataclasses import dataclass

import numpy as np

from services import um_lector_eclipse as lector
from services import um_motor as motor
from services import um_plausibilidad as plausibilidad

TIPO_PDD, TIPO_PERFIL, TIPO_WDD, TIPO_OF, TIPO_CUNA = "OPD", "OPP_processed", "WDD", "OutputFactorTable", "WedgeParameters"
TIPOS_QUE_LEE_EL_MOTOR = (TIPO_PDD, TIPO_PERFIL, TIPO_WDD, TIPO_OF, TIPO_CUNA)
ABIERTO = "Open Field - 00"
LEE_DEL_ABIERTO, LEE_DE_UNA_CUNA = (TIPO_PDD, TIPO_PERFIL, TIPO_OF), (TIPO_OF, TIPO_WDD, TIPO_CUNA)   # UM.2 (UM2-D4): lo que el armado lee de cada accesorio
LECTORES = {TIPO_PDD: lector.leer_curvas, TIPO_PERFIL: lector.leer_curvas, TIPO_WDD: lector.leer_curvas, TIPO_OF: lector.leer_tabla_of, TIPO_CUNA: lector.leer_parametros}
PERFIL_A_UNA_PROFUNDIDAD_CM = 0.05   # UM.2 (UM2-D2): los puntos de un perfil, a una sola profundidad; medido: 0.0 en los 659 perfiles reales (59 del 600C y 600 del paquete de Varian)
TRAMO_MINIMO_AJUSTE_CUNA_CM = 5.0    # con menos, no se ve cómo varía la cuña con la profundidad
D0_RANGO = (0.5, 1.5)                # cGy/UM, en dmax o en las condiciones de la tabla: fuera de aquí es un error al escribirlo
SC_RANGO = (0.5, 1.5)
X_AJUSTE_CENTRO_CM = 3.0             # el centro de un perfil se ajusta de 0 a 3 cm, o a un cuarto del lado si es menor
# Sp de la TG-71 (6 MV) llevado a d = 5 cm: tabla IV × TPR(5; r)/TPR(5; 10) de la tabla III, normalizado en r = 10 (la cuenta está en el anexo del plan de la calculadora de UM, no en el repositorio).
SP_A_5CM_TG71 = ((4.0, 0.9454), (5.0, 0.9585), (6.0, 0.9679), (8.0, 0.9847), (10.0, 1.0000), (12.0, 1.0114), (14.0, 1.0213),
                 (16.0, 1.0306), (20.0, 1.0434), (24.0, 1.0535), (28.0, 1.0623), (32.0, 1.0700), (40.0, 1.0766))


def familia_pdd(curvas):
    """FamiliaPDD y su SSD, desde las curvas abiertas medidas. Exige cuadrados sin repetir, una sola SSD, la misma rejilla, valores positivos y posibles
    (`um_plausibilidad`: máximo 100 y la forma de un PDD) y el 10 × 10."""
    orden = sorted(curvas, key=lambda c: c.campo_cm[0])
    if any(c.campo_cm[0] != c.campo_cm[1] for c in orden):
        raise lector.ArchivoNoReconocido("hay un PDD abierto de un campo que no es cuadrado")
    ssds = {c.ssd_cm for c in orden}
    if len(ssds) != 1 or None in ssds:
        dicen = [f"{s:g} [cm]" for s in sorted(ssds - {None})] + (["una curva sin SSD"] if None in ssds else [])
        raise lector.ArchivoNoReconocido(f"los PDD abiertos deben decir una sola SSD y dicen {', '.join(dicen)}")
    z = orden[0].z_cm
    if any(len(c.z_cm) != len(z) or not np.allclose(c.z_cm, z) for c in orden) or np.any(np.diff(z) <= 0):
        raise lector.ArchivoNoReconocido("los PDD abiertos no tienen la misma rejilla de profundidad")
    if any(np.any(c.valor <= 0) for c in orden):
        raise lector.ArchivoNoReconocido("un PDD abierto tiene un valor nulo")
    plausibilidad.revisar_pdd_abiertos(orden)
    lados = np.array([c.campo_cm[0] for c in orden])
    if len(set(lados.tolist())) != len(lados):
        raise lector.ArchivoNoReconocido("hay un PDD abierto repetido para el mismo campo")
    if 10.0 not in lados:
        raise lector.ArchivoNoReconocido("falta el PDD del campo de 10 × 10")
    return motor.FamiliaPDD(lados, z, np.array([c.valor for c in orden])), ssds.pop()


def perfil_oar(c):
    """D(x)/D(0) de una curva. La muestra en x = 0 no se usa: en estos archivos es el valor del PDD, no el del perfil. El centro sale de ajustar a + b·x² cerca del eje."""
    if c.ssd_cm is None:
        raise lector.ArchivoNoReconocido("hay un perfil que no dice su SSD")
    if np.ptp(c.z_cm) > PERFIL_A_UNA_PROFUNDIDAD_CM:      # UM.2 (UM2-D2): la profundidad del perfil es la z de sus puntos, no su «%DPTH» (los de «1.4» están a 1.35 cm)
        raise lector.ArchivoNoReconocido(f"hay un perfil con puntos a profundidades distintas (de {c.z_cm.min():g} a {c.z_cm.max():g} [cm]): un perfil se mide a una sola profundidad")
    orden = np.argsort(c.x_cm)
    x, v = c.x_cm[orden], c.valor[orden]
    fuera = x > 0
    if not fuera.any():
        raise lector.ArchivoNoReconocido("hay un perfil sin puntos fuera del eje")
    lado = c.campo_cm[0]
    cerca = fuera & (x <= min(X_AJUSTE_CENTRO_CM, lado / 4))
    a = float(np.polyfit(x[cerca] ** 2, v[cerca], 1)[1]) if cerca.sum() >= 2 else float(v[fuera][0])
    if not a > 0:
        raise lector.ArchivoNoReconocido("hay un perfil con un valor nulo cerca del eje")
    return motor.PerfilOAR(float(np.median(c.z_cm)), lado, np.concatenate(([0.0], x[fuera])), np.concatenate(([1.0], v[fuera] / a)), c.ssd_cm)


def perfiles_oar(curvas):
    """Los perfiles abiertos cuadrados y, por profundidad, el del campo más grande (en el 600C, 40 × 40 y a 30 cm 35 × 35).
    Una profundidad medida solo con campos pequeños no cuenta: no sirve para leer OAR lejos del eje.
    UM.2 (UM2-D1, UM2-D3): un perfil de un campo que no es cuadrado, o dos del mismo campo a la misma profundidad, no se entienden: antes se saltaba el primero
    (un «%FLSZ 350*350» dañado como « 50*350» quitaba el 35 × 35 de 30 cm) y se elegía en silencio uno de los dos. UM.2 v2: una sola SSD y valores posibles."""
    for c in curvas:
        if c.campo_cm[0] != c.campo_cm[1]:
            raise lector.ArchivoNoReconocido(f"hay un perfil abierto de un campo que no es cuadrado ({c.campo_cm[0]:g} × {c.campo_cm[1]:g} [cm]): los perfiles abiertos son de campos cuadrados")
    plausibilidad.revisar_curvas_de_perfiles(curvas)
    todos = tuple(perfil_oar(c) for c in curvas)
    if not todos:
        raise lector.ArchivoNoReconocido("los perfiles no traen ningún campo cuadrado")
    vistos = set()
    for p in todos:
        plausibilidad.revisar_perfil(p)
        if (p.lado, p.prof) in vistos:
            raise lector.ArchivoNoReconocido(f"hay dos perfiles del campo de {p.lado:g} × {p.lado:g} [cm] a {p.prof:g} [cm] de profundidad: no se sabe cuál usar")
        vistos.add((p.lado, p.prof))
    mayor, mejor = max(p.lado for p in todos), {}
    for p in todos:
        if p.lado >= mayor / 2 and (p.prof not in mejor or p.lado > mejor[p.prof].lado):
            mejor[p.prof] = p
    if len(mejor) < 2:
        raise lector.ArchivoNoReconocido("los perfiles deben traer campos grandes a dos profundidades por lo menos")
    return motor.PerfilesOAR(tuple(mejor[q] for q in sorted(mejor)), todos)


def betas_de_cuna(curvas_cuna, pdd, d0, ssd_pdd, campo_entero):
    """Por cada cuadrado medido con y sin cuña, la pendiente de ln[WF(d)/WF(d0)], ajustada en todo lo medido: (lados, pendientes, hasta dónde sirve).
    Exige la SSD de los PDD abiertos, porque es un cociente, y profundidades en orden que cubran un tramo suficiente.
    UM.2 (UM2-D1): el único PDD con cuña que puede no ser cuadrado es el del campo entero de su tabla (`campo_entero`, X × Y: 40 × 20 en el 600C, 40 × 15 en la
    de 60°), y no entra en el ajuste; cualquier otro rectángulo, o dos curvas del mismo cuadrado, no se entienden (un «%FLSZ 150*150» dañado como « 50*150»
    quitaba en silencio el 15 × 15 del ajuste). Un cuadrado sin PDD abierto se sigue saltando: el paquete de Varian mide 22 × 22 y 27 × 27 solo con cuña."""
    lados, betas, hasta = [], [], []
    for c in sorted(curvas_cuna, key=lambda q: q.campo_cm):
        if c.ssd_cm is None:
            raise lector.ArchivoNoReconocido("hay un PDD con cuña que no dice su SSD")
        if c.ssd_cm != ssd_pdd:
            raise lector.ArchivoNoReconocido(f"un PDD con cuña está a SSD {c.ssd_cm:g} [cm] y los abiertos a SSD {ssd_pdd:g} [cm]: no se pueden dividir")
        lado = c.campo_cm[0]
        if lado != c.campo_cm[1]:
            if c.campo_cm != campo_entero:
                fallo = lector.ArchivoNoReconocido(f"hay un PDD con cuña de {lado:g} × {c.campo_cm[1]:g} [cm], que no es un cuadrado ni el campo entero de su tabla "
                                                   f"({campo_entero[0]:g} × {campo_entero[1]:g} [cm]): revise ese PDD y la tabla de factores de la cuña, que puede estar cortada al final de una fila")
                fallo.tipos_del_motivo = (TIPO_WDD, TIPO_OF)      # UM.2b (B1 con F3 de la ronda 1): el motivo es de dos archivos, el PDD y la tabla; la revisión nombra los dos
                raise fallo
            continue
        if lado in lados:
            raise lector.ArchivoNoReconocido(f"hay dos PDD con cuña del campo de {lado:g} × {lado:g} [cm]: no se sabe cuál usar")
        if lado not in pdd.lados:
            continue
        if np.any(np.diff(c.z_cm) <= 0):
            raise lector.ArchivoNoReconocido(f"el PDD con cuña de {lado:g} × {lado:g} [cm] no va en orden creciente de profundidad")
        limite = min(float(c.z_cm[-1]), float(pdd.z_cm[-1]))
        if c.z_cm[0] > d0 or limite < d0 + TRAMO_MINIMO_AJUSTE_CUNA_CM:
            raise lector.ArchivoNoReconocido(f"el PDD con cuña de {lado:g} × {lado:g} [cm] debe cubrir de {d0:g} a {d0 + TRAMO_MINIMO_AJUSTE_CUNA_CM:g} [cm] por lo menos")
        d = np.arange(d0, limite + 1e-9, 0.5)
        medido = np.interp(d, c.z_cm, c.valor)
        if np.any(medido <= 0):
            raise lector.ArchivoNoReconocido(f"el PDD con cuña de {lado:g} × {lado:g} [cm] tiene un valor nulo")
        cociente = (medido / medido[0]) / np.array([pdd(float(q), lado) / pdd(d0, lado) for q in d])
        x, y = d - d0, np.log(cociente)
        lados.append(lado)
        betas.append(float(np.dot(x, y) / np.dot(x, x)))
        hasta.append(limite)
    if not lados:
        raise lector.ArchivoNoReconocido("el PDD con cuña no trae ningún cuadrado medido también sin cuña")
    return np.array(lados), np.array(betas), min(hasta)


def sc_del_haz(of, ssd0, d0, energia):
    """La curva de Sc por omisión y su origen. En 6 MV a 5 cm: Sc(J) = OF(J, J)/Sp(J·(SSD0 + d0)/SAD), con el Sp de la TG-71, porque
    «Sp should display little to no variation between linear accelerators with the same beam quality» y Sc sí varía. En lo demás, la tabla IV.
    La energía se compara por su clave (`lector.clave_energia`): «6X», «6MV» y «6 mv» son «6 MV»."""
    if lector.clave_energia(energia) != "6 MV" or d0 != 5.0:
        return motor.SC_MUESTRA_TG71, motor.SC_MUESTRA_ORIGEN
    k = (ssd0 + d0) / motor.SAD_CM
    r_min, r_max = SP_A_5CM_TG71[0][0], SP_A_5CM_TG71[-1][0]
    lados = {float(s) for s in of.x if s in of.y and r_min <= s * k <= r_max}
    if of.contiene(r_max / k, r_max / k):
        lados.add(r_max / k)
    sc = [(j, of(j, j) / motor.sc_de(SP_A_5CM_TG71, j * k)) for j in sorted(lados)]
    ref = of(10.0, 10.0) / motor.sc_de(SP_A_5CM_TG71, 10.0 * k)
    return tuple((j, float(v / ref)) for j, v in sc), "estimada de la tabla de este haz y el Sp de la TG-71"


def curva_de_sc(sc):
    """La curva de Sc escrita, como tupla de pares (lado [cm], Sc). Rechaza lo que no sea una curva creciente en el lado, con números (no texto) y valores
    posibles. Lo que significa cada forma (UM.3 la guarda así): None, la curva por omisión (no pasa por aquí); () o [], la corrección apagada; una lista de
    pares, la curva escrita."""
    mensaje = "La curva de Sc debe tener al menos dos puntos (lado [cm], Sc), con números, lados crecientes y valores de {:g} a {:g}".format(*SC_RANGO)
    try:
        curva = tuple((j, v) for j, v in sc)
    except (TypeError, ValueError):
        raise motor.FaltaDato(mensaje) from None
    if (len(curva) == 1 or not all(motor.es_numero(j) and motor.es_numero(v) and j > 0 and SC_RANGO[0] <= v <= SC_RANGO[1] for j, v in curva)
            or any(b <= a for (a, _), (b, _) in zip(curva, curva[1:]))):
        raise motor.FaltaDato(mensaje)
    return tuple((float(j), float(v)) for j, v in curva)


def _factores_escritos(wf_escritos):
    """{ángulo: WF}. El ángulo es un entero o el texto de un entero (las claves de un JSON son texto): «15» sí; «15.0» y 15.5 no, para que lo que se guarda se
    pueda volver a leer y ninguna cuña de 15.9° pase por la de 15°. El WF, un número (su rango se mira con el de la cuña)."""
    escritos = {}
    for angulo, wf in (wf_escritos or {}).items():
        entero = int(angulo) if isinstance(angulo, str) and re.fullmatch(r"[0-9]+", angulo) else angulo
        if not isinstance(entero, int) or isinstance(entero, bool):
            raise motor.FaltaDato(f"El ángulo de un factor de cuña escrito debe ser un número entero de grados, y se recibió «{angulo}»")
        if not motor.es_numero(wf):
            raise motor.FaltaDato(f"El factor escrito de la cuña de {entero}° debe ser un número, y se recibió «{wf}»")
        if entero in escritos:
            raise motor.FaltaDato(f"Hay dos factores escritos para la cuña de {entero}°")
        escritos[entero] = float(wf)
    return escritos


def _factor_posible(angulo, wf):
    """UM.2b (B1): el factor de una cuña, escrito o deducido del `name.data`, dentro de lo posible (`motor.RANGO_FACTOR_CUNA`): la única definición. De qué archivo es el rechazo lo dice quien llama (`datos_haz`)."""
    if not motor.RANGO_FACTOR_CUNA[0] <= wf <= motor.RANGO_FACTOR_CUNA[1]:
        raise motor.FaltaDato(f"El factor de la cuña de {angulo}° = {motor.cifras(wf, motor.RANGO_FACTOR_CUNA[0] if wf < motor.RANGO_FACTOR_CUNA[0] else motor.RANGO_FACTOR_CUNA[1], 3)} no es un valor posible (de {motor.RANGO_FACTOR_CUNA[0]:g} a {motor.RANGO_FACTOR_CUNA[1]:g})")


def _eje_del_gradiente(tabla, orientacion, angulo):
    """A lo largo de qué eje de la tabla va el gradiente: el lado corto de la tabla, comprobado con la orientación del `name.data`."""
    if orientacion is not None and orientacion not in motor.ORIENTACIONES:
        fallo = lector.ArchivoNoReconocido(f"la cuña de {angulo}° dice orientación {orientacion}, y se esperaba {', '.join(motor.ORIENTACIONES)}")
        fallo.tipos_del_motivo = TIPO_CUNA      # UM.2b (B1, UM2-D22): una orientación ilegible es solo del name.data (un solo tipo, como cualquier rechazo de un archivo); los otros dos motivos son de la tabla y del name.data a la vez (`datos_haz` los atribuye a esos dos)
        raise fallo
    por_forma = "Y" if tabla.y[-1] < tabla.x[-1] else "X" if tabla.x[-1] < tabla.y[-1] else None
    por_nombre = None if orientacion is None else "X" if orientacion in motor.ORIENTACIONES_GRADIENTE_EN_X else "Y"
    if por_forma and por_nombre and por_forma != por_nombre:
        raise lector.ArchivoNoReconocido(f"la cuña de {angulo}° dice orientación {orientacion} y su tabla tiene el lado corto en {por_forma}: filas y columnas no cuadran")
    if not (por_forma or por_nombre):
        raise lector.ArchivoNoReconocido(f"la tabla de la cuña de {angulo}° es cuadrada y falta su name.data: no se sabe el eje del gradiente")
    return por_forma or por_nombre


@contextlib.contextmanager
def _de(tipo, accesorio, angulo=None):
    """UM.2b (B1): un rechazo al armar lleva de qué archivo sale (`fallo.archivo` = (tipo de dato, accesorio); el tipo puede ser una tupla de tipos, la que da el sitio o,
    si el motivo marca `tipos_del_motivo`, la del motivo, o `None`, todos los de ese accesorio), para que la revisión ponga su nombre, y, si es de una cuña y el motivo no
    lo dice, su ángulo."""
    try:
        yield
    except (lector.ArchivoNoReconocido, motor.NoCalculable) as fallo:
        fallo.archivo = (getattr(fallo, "tipos_del_motivo", tipo), accesorio)
        if angulo is not None and f"{angulo}°" not in str(fallo):
            fallo.args = (f"la cuña de {angulo}°: {fallo}",)
        raise


def _uno(por_tipo, tipo, accesorio):
    """El texto de ese dato y ese accesorio, o None. UM.2 (UM2-D3): dos textos distintos para lo mismo no se entienden (antes se usaba el primero en silencio)."""
    hallados = [t for i, t in por_tipo.get(tipo, ()) if i.accesorio == accesorio]
    if len(set(hallados)) > 1:
        raise lector.ArchivoNoReconocido(f"hay dos archivos distintos para {accesorio}, {tipo}")
    return hallados[0] if hallados else None


def _claves_pedidas(equipo, energia):
    """El equipo y la energía pedidos, por su clave (`lector.clave_equipo`, `lector.clave_energia`): «6X», «6MV» y «6 mv» son «6 MV»."""
    equipo_k, energia_k = lector.clave_equipo(equipo), lector.clave_energia(energia)
    if equipo_k is None:
        raise motor.FaltaDato(f"El equipo «{equipo}» no se reconoce: la calculadora conoce el Clinac 600 y el Clinac iX")
    if energia_k is None:
        raise motor.FaltaDato(f"La energía «{energia}» no se reconoce: se escribe como «6 MV» o «6X»")
    return equipo_k, energia_k


def datos_haz(archivos, equipo, energia, d0_dmax=None, d0_tabla=None, wf_escritos=None, sc=None, sc_origen=None):
    """`archivos`: textos ya decodificados, todos de la misma máquina y energía, que deben ser las pedidas (`equipo`, `energia`, por su clave).

    D'0 es el de Eclipse, porque se compara con Eclipse y porque el WF deducido de su dosis de referencia se divide por él. Se da en dmax (`d0_dmax`) si la
    tabla de factores está a la SSD de los PDD; si no, a las condiciones de la tabla (`d0_tabla`).
    `wf_escritos`: {ángulo: WF en 10 × 10 a d0}, que manda sobre la dosis de referencia.
    `sc`: None, la curva por omisión (`sc_del_haz`); () o [], la corrección de Sc apagada; una lista de pares, la curva escrita, que manda. `sc_origen`: de dónde
    sale la escrita (por omisión, «curva de Sc escrita»)."""
    equipo, energia = _claves_pedidas(equipo, energia)
    por_tipo, maquinas = {}, set()
    for texto in archivos:
        i = lector.identidad(texto)
        maquinas.add((i.maquina, i.haz))
        por_tipo.setdefault(i.dato, []).append((i, texto))
    if len(maquinas) > 1:
        raise lector.ArchivoNoReconocido("los archivos son de máquinas o energías distintas: " + " y ".join(f"máquina {m} con haz {h}" for m, h in sorted(maquinas, key=str)))
    for maquina, haz in maquinas:
        for que, escrito, leido, pedido in (("máquina", maquina, lector.clave_equipo(maquina), equipo), ("haz", haz, lector.clave_energia(haz), energia)):
            if leido is not None and leido != pedido:
                raise lector.ArchivoNoReconocido(f"los archivos dicen {que} {escrito}, y se están cargando para {pedido}")
    por_angulo = {}
    for i, _ in (par for pares in por_tipo.values() for par in pares):
        if i.angulo_cuna is not None:
            por_angulo.setdefault(i.angulo_cuna, set()).add(i.accesorio)
    for angulo, accesorios in sorted(por_angulo.items()):
        if len(accesorios) > 1:
            raise lector.ArchivoNoReconocido(f"{' y '.join(f'«{a}»' for a in sorted(accesorios))} son la misma cuña de {angulo}°: no se sabe cuál usar")
    if not _uno(por_tipo, TIPO_PDD, ABIERTO) or not _uno(por_tipo, TIPO_OF, ABIERTO):
        raise lector.ArchivoNoReconocido("faltan el PDD medido o la tabla de factores del campo abierto")
    with _de(TIPO_PDD, ABIERTO):
        pdd, ssd_pdd = familia_pdd(lector.leer_curvas(_uno(por_tipo, TIPO_PDD, ABIERTO)))
    with _de(TIPO_OF, ABIERTO):
        of_a = lector.leer_tabla_of(_uno(por_tipo, TIPO_OF, ABIERTO))
        if of_a.y[-1] != of_a.x[-1]:      # UM.2 (UM2-D5): una tabla no tiene marca de final; cortada al final de una fila se leía como una tabla más pequeña
            raise lector.ArchivoNoReconocido(f"la tabla de factores abierta llega a {of_a.x[-1]:g} [cm] en X y a {of_a.y[-1]:g} [cm] en Y: parece cortada al final de una fila")
        plausibilidad.revisar_tabla(of_a, "la tabla abierta")
    of = motor.TablaFactores(of_a.x, of_a.y, of_a.m)
    d0 = of_a.prof_cm

    if (d0_dmax is None) == (d0_tabla is None):
        raise motor.FaltaDato("Escriba D'0 en dmax o en las condiciones de la tabla, uno de los dos")
    escrito = d0_tabla if d0_dmax is None else d0_dmax
    if not motor.es_numero(escrito) or not D0_RANGO[0] <= escrito <= D0_RANGO[1]:
        raise motor.FaltaDato(f"D'0 no es un valor posible (de {D0_RANGO[0]:g} a {D0_RANGO[1]:g} [cGy/UM]): {escrito}")
    if d0_dmax is not None and of_a.ssd_cm != ssd_pdd:
        raise motor.FaltaDato(f"La tabla de factores está a SSD {of_a.ssd_cm:g} [cm] y los PDD a SSD {ssd_pdd:g} [cm]: escriba D'0 en las condiciones de la tabla")
    d0_norm = d0_tabla if d0_dmax is None else motor.d0_en_normalizacion(pdd, d0_dmax, d0)

    if sc is None:
        sc, sc_origen = sc_del_haz(of, of_a.ssd_cm, d0, energia)
    else:
        sc = curva_de_sc(sc)
        sc_origen = (sc_origen or motor.SC_ESCRITA) if sc else motor.SC_APAGADA

    cunas, escritos = {}, _factores_escritos(wf_escritos)
    for i, texto in por_tipo.get(TIPO_OF, ()):
        angulo = i.angulo_cuna
        wdd = _uno(por_tipo, TIPO_WDD, i.accesorio)
        if angulo is None or not wdd:
            continue
        with _de(TIPO_OF, i.accesorio, angulo):
            tabla = lector.leer_tabla_of(texto)
            if tabla.ssd_cm != of_a.ssd_cm or tabla.prof_cm != d0:
                raise lector.ArchivoNoReconocido(f"la tabla de la cuña de {angulo}° no está en las mismas condiciones que la abierta")
            plausibilidad.revisar_tabla(tabla, f"la tabla de la cuña de {angulo}°")
        parametros = _uno(por_tipo, TIPO_CUNA, i.accesorio)
        wf, origen, orientacion = escritos.get(angulo), "", None
        if parametros:
            with _de(TIPO_CUNA, i.accesorio, angulo):
                orientacion = lector.orientacion_de_cuna(parametros)
                if lector.angulo_en_parametros(parametros) not in (None, float(angulo)):
                    raise lector.ArchivoNoReconocido(f"el name.data de la cuña de {angulo}° dice otro ángulo: {lector.angulo_en_parametros(parametros):g}°")
                dosis = lector.dosis_de_referencia_cuna(parametros)
            if wf is None and dosis:
                wf = dosis / d0_norm
                origen = (f"El factor de la cuña de {angulo}° en 10 × 10 es {wf:.4f}: se dedujo de su dosis de referencia, {dosis:.4f} [cGy/UM], entre D'0, {d0_norm:.4f} [cGy/UM], "
                          f"suponiendo que esa dosis es a {d0:g} [cm]: falta confirmarlo.")      # ronda 1 (F1, DC13 2): con su valor y los dos datos de que sale; un dato dañado del name.data se ve aquí
        with _de((TIPO_OF, TIPO_CUNA), i.accesorio, angulo):      # la tabla y el name.data se contradicen: los dos archivos (la orientación ilegible, solo el name.data: lo marca `_eje_del_gradiente`)
            gradiente = _eje_del_gradiente(tabla, orientacion, angulo)
        # UM.2b (B1): el rango del factor, de dónde salga. Uno deducido sale del name.data, y es ese archivo el que hay que exportar de nuevo; uno escrito no es de ningún archivo (la lista cerrada de la prueba por AST)
        if origen:
            with _de(TIPO_CUNA, i.accesorio, angulo):
                _factor_posible(angulo, wf)
        elif wf is not None:
            _factor_posible(angulo, wf)
        with _de(TIPO_WDD, i.accesorio, angulo):
            curvas_cuna = lector.leer_curvas(wdd)
            lados_beta, betas, prof_max = betas_de_cuna(curvas_cuna, pdd, d0, ssd_pdd, (float(tabla.x[-1]), float(tabla.y[-1])))
            plausibilidad.revisar_pdd_con_cuna(curvas_cuna, angulo)      # después: los motivos de `betas_de_cuna` dicen más; esta mira también el campo entero
        revisar = frozenset((y, x) for y, x, *_ in lector.valores_fuera_de_tendencia(tabla))
        cunas[angulo] = motor.DatosCuna(motor.TablaFactores(tabla.x, tabla.y, tabla.m), lados_beta, betas, prof_max, gradiente, wf, origen, revisar)
    sobran = sorted(set(escritos) - set(cunas))
    if sobran:
        raise motor.FaltaDato(f"Hay un factor escrito para una cuña que no está entre los archivos: {', '.join(f'{a}°' for a in sobran)}; quite el factor escrito o "
                              "agregue sus archivos")

    perfil = _uno(por_tipo, TIPO_PERFIL, ABIERTO)
    with _de(TIPO_PERFIL, ABIERTO):
        perfiles = perfiles_oar(lector.leer_curvas(perfil)) if perfil else None
    return motor.DatosHaz(
        equipo=equipo, energia=energia, ssd0_cm=of_a.ssd_cm, d0_cm=d0, d0_norm=d0_norm, pdd=pdd, of=of, ssd_pdd_cm=ssd_pdd, sc=sc, sc_origen=sc_origen,
        perfiles=perfiles, cunas=cunas,
        celdas_a_revisar=frozenset((y, x) for y, x, *_ in lector.valores_fuera_de_tendencia(of_a)))


@dataclass(frozen=True)
class Revision:
    """Lo que entendió la carga antes de guardar. `problemas` impide guardar; `avisos` no. `usados`: los archivos que se guardan (uno por accesorio y dato)."""
    usados: tuple
    ignorados: tuple
    problemas: tuple
    avisos: tuple


def _error_inesperado(que, fallo):
    return f"error inesperado al {que} ({type(fallo).__name__}): avise al administrador"


def revisar_archivos(archivos, equipo, energia, d0_dmax=None, d0_tabla=None, wf_escritos=None, sc=None, sc_origen=None):
    """`archivos`: [(nombre, texto)]. Dice qué se usa, qué se ignora, qué impide guardar y qué conviene mirar. Es la frontera de la carga: un fallo conocido
    (`ArchivoNoReconocido`, `NoCalculable`) es un motivo para no guardar, con el nombre del archivo que lo da; cualquier otro se dice como error inesperado."""
    usados, ignorados, problemas, avisos, textos, vistos, candidatos = [], [], [], [], [], {}, []
    try:
        pedidos = _claves_pedidas(equipo, energia)
    except motor.NoCalculable as fallo:
        pedidos = None
        problemas.append(str(fallo))
    try:
        escritos = _factores_escritos(wf_escritos)      # ronda 1 (F4): las claves como en `datos_haz` (un JSON las devuelve en texto); una que no es posible la dice `datos_haz`
    except motor.NoCalculable:
        escritos = {}
    for nombre, texto in archivos:
        try:
            i = lector.identidad(texto)
        except lector.ArchivoNoReconocido as fallo:
            problemas.append(f"{nombre}: {fallo}")
            continue
        if i.dato not in TIPOS_QUE_LEE_EL_MOTOR:
            ignorados.append(nombre)
            continue
        if i.dato not in (LEE_DEL_ABIERTO if i.accesorio == ABIERTO else LEE_DE_UNA_CUNA if i.angulo_cuna is not None else ()):
            # UM.2 (UM2-D4): lo que el armado no lee se ignora y no pesa en la carga (antes contaba como usado y una máquina distinta impedía guardar)
            ignorados.append(nombre)
            avisos.append(f"{nombre}: el accesorio «{i.accesorio}» no se reconoce como una cuña física y no se usa." if i.accesorio != ABIERTO and i.angulo_cuna is None
                          else f"{nombre}: el cálculo no lee «{i.dato}» de «{i.accesorio}»: no se usa.")
            continue
        clave = (i.accesorio, i.dato)
        if clave in vistos:
            primero, texto_primero = vistos[clave]
            if texto_primero == texto:     # UM.2 v2 (IF-6): el mismo archivo elegido dos veces se usa una vez (UM.3 guarda uno por accesorio y dato)
                ignorados.append(nombre)
                avisos.append(f"{nombre}: es copia idéntica de {primero}: se usa una sola vez.")
            else:
                problemas.append(f"{nombre}: hay dos archivos distintos para {i.accesorio}, {i.dato}")
            continue
        vistos[clave] = (nombre, texto)
        candidatos.append((nombre, texto, i))
    cunas = {}
    for nombre, _, i in candidatos:
        if i.angulo_cuna is not None:
            cunas.setdefault(i.angulo_cuna, {}).setdefault(i.accesorio, set()).add(i.dato)
    for angulo, accesorios in sorted(cunas.items()):
        if len(accesorios) > 1:     # UM.2 v2 (DR-4): «Standard Wedge - 15» y «- 015» son la misma cuña: antes la que llegaba última pisaba a la otra
            problemas.append(" y ".join(f"{n} («{i.accesorio}»)" for n, _, i in candidatos if i.angulo_cuna == angulo) + f": son la misma cuña de {angulo}°, con dos nombres")
            continue
        (accesorio, datos_de_la_cuna), = accesorios.items()
        faltan = [que for tipo, que in ((TIPO_OF, "su tabla de factores"), (TIPO_WDD, "su PDD medido con cuña")) if tipo not in datos_de_la_cuna]
        if faltan:     # UM.2 v2 (L-UM2-2): una cuña sin su tabla o sin su PDD no se arma; sus archivos no se usan ni pesan en la carga (UM2-D4)
            ignorados.extend(n for n, _, i in candidatos if i.accesorio == accesorio)
            candidatos = [(n, t, i) for n, t, i in candidatos if i.accesorio != accesorio]
            if angulo in escritos:     # UM.2 v2 (B4): el factor escrito no se puede usar sin el PDD con cuña; se dice qué pasa y qué hacer
                problemas.append(f"Cuña de {angulo}°: hay un factor escrito, pero le falta {' y '.join(faltan)} y sus archivos no se usan: quite el factor escrito "
                                 f"o agregue {' y '.join(faltan)}.")
            else:
                avisos.append(f"Cuña de {angulo}°: falta {' y '.join(faltan)}; sus archivos no se usan y sus campos se escriben a mano.")
    for nombre, texto, i in candidatos:
        if pedidos:
            for que, escrito, leido, pedido in (("máquina", i.maquina, lector.clave_equipo(i.maquina), pedidos[0]), ("haz", i.haz, lector.clave_energia(i.haz), pedidos[1])):
                if leido is None:
                    avisos.append(f"{nombre} dice {que} {escrito}, que este lector no reconoce: compruebe que es de {pedido}.")
                elif leido != pedido:
                    problemas.append(f"{nombre} dice {que} {escrito}, y se está cargando para {pedido}.")
        try:
            LECTORES[i.dato](texto)
        except (lector.ArchivoNoReconocido, motor.NoCalculable) as fallo:
            problemas.append(f"{nombre}: {fallo}")
            continue
        except Exception as fallo:      # la frontera de la carga: lo que no se esperaba se dice, no revienta ni se esconde
            problemas.append(f"{nombre}: {_error_inesperado('leerlo', fallo)}")
            continue
        usados.append(nombre)
        textos.append(texto)
    if not problemas:
        try:
            datos = datos_haz(textos, equipo, energia, d0_dmax, d0_tabla, wf_escritos, sc, sc_origen)
        except (lector.ArchivoNoReconocido, motor.NoCalculable) as fallo:
            tipo, accesorio = getattr(fallo, "archivo", (None, None))     # UM.2 v2 (B1): el nombre de los archivos de los que sale el rechazo
            tipos = (tipo,) if isinstance(tipo, str) else tipo
            nombres = [n for n, _, i in candidatos if i.accesorio == accesorio and (tipos is None or i.dato in tipos)]      # todo archivo leído tiene accesorio (`identidad`)
            problemas.append(f"{' y '.join(nombres)}: {fallo}" if nombres else str(fallo))
        except Exception as fallo:      # la frontera de la carga
            problemas.append(_error_inesperado("armar los datos del haz", fallo))
        else:
            if datos.perfiles is None:
                avisos.append("No hay perfiles: el OAR fuera del eje se escribirá a mano.")
            else:
                avisos.append(f"Perfiles para el OAR: {datos.perfiles.origen}.")
            avisos.append(f"Curva de Sc: {motor.origen_de_sc(datos)}.")
            avisos.append(f"D'0 = {datos.d0_norm:.4f} [cGy/UM] a {datos.d0_cm:g} [cm] de profundidad, SSD {datos.ssd0_cm:g} [cm], 10 × 10"     # UM.2 v2 (A6)
                          + (f": sale de {d0_dmax:g} [cGy/UM] en dmax con el máximo medido del PDD de 10 × 10, {datos.pdd.maximo(10.0):.2f} [%]." if d0_dmax is not None
                             else ", escrito en las condiciones de la tabla."))
            for y, x in sorted(datos.celdas_a_revisar):
                avisos.append(f"Tabla abierta: el valor en Y = {y:g} [cm], X = {x:g} [cm] se sale de la tendencia.")
            for angulo, cuna in sorted(datos.cunas.items()):
                t = cuna.tabla      # ronda 1 (F3): una tabla cortada al final de una fila se lee como una más pequeña y nada en los archivos lo delata si falta el PDD del campo entero: se dice hasta dónde llega
                avisos.append(f"Cuña de {angulo}°: su tabla de factores va de {t.x[0]:g} a {t.x[-1]:g} [cm] en X y de {t.y[0]:g} a {t.y[-1]:g} [cm] en Y.")
                for y, x in sorted(cuna.celdas_a_revisar):
                    avisos.append(f"Cuña de {angulo}°: el valor en Y = {y:g} [cm], X = {x:g} [cm] se sale de la tendencia.")
                if cuna.wf_ref is None:
                    avisos.append(f"Cuña de {angulo}°: falta su factor en 10 × 10; hasta tenerlo se escribe por campo.")
                elif cuna.wf_origen:
                    avisos.append(cuna.wf_origen)
    return Revision(tuple(usados), tuple(ignorados), tuple(problemas), tuple(avisos))
