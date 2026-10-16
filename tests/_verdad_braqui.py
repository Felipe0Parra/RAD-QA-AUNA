"""B.2 (PLAN_ANALISIS_PELICULAS_08-10.md): la comparacion del motor de la POSICION INICIAL de braquiterapia contra una VERDAD CONOCIDA. Modulo auxiliar de pruebas (no empieza por
`test_`: pytest no lo colecciona) que comparten las tres pruebas de B.2 y los guiones del anexo (el rojo con copias del motor y con las replicas del cuaderno del fisico, y las baterias de
mutaciones): los CRITERIOS se escriben UNA vez aqui y se evaluan sobre quien se quiera, asi que lo que le exigimos al motor es exactamente lo que le exigimos a su cuaderno.

LA VERDAD no sale de este archivo ni del motor: la dan los dos generadores de PF.0 (`_placa_braqui_sintetica.py`: el INDEPENDIENTE y el FISICO calibrado contra la mancha real; ninguno importa
el motor) y, para las placas reales, la referencia independiente (`_referencia_independiente_braqui.py`). Este modulo SI importa el motor, porque su trabajo es medir con el: `medir(placa)` hace
lo que hace la aplicacion (`leer_pelicula` -> `analizar` -> `resumen`).

CRITERIOS (OBJETIVO de B.2; cada uno es una funcion `fallos_de_...(casos)` que devuelve la lista de lo que NO se cumple, vacia si todo bien):
  * exactitud: error <= 0.05 mm en el gris y <= 0.10 mm en cada capa (R, G, B: cualquiera puede ser la reportada) en toda la rejilla de -4 a +4 mm cada 0.25 mm, con la linea vertical e
    inclinada 1.5 grados, en PNG y en JPEG. UN LIMITE CONOCIDO, de UNA sola capa (ronda 1 de la revision, hallazgo DL-01): con las semillas de la prueba y los dos generadores de PF.0, la unica
    comparacion de las 528 del modelo FISICO que EXCEDE el criterio literal del plan es la capa AZUL con JPEG, la linea inclinada y la linea sobre el BORDE de su meseta (d = +3.25 mm: 0.147 mm contra
    0.10; la meseta saturada de la azul mide 6.06 mm, la verde 6.19, la roja 6.56; el submuestreo 4:2:0 del JPEG emborrona los bordes de las capas de color). En esa banda (`BANDA_DEL_BORDE`, |d| de 2.5
    a 3.5 mm) SOLO la azul tiene un techo propio, el medido con margen (0.20 mm); el gris (maximo medido en la banda 0.045 mm), la roja (0.068) y la verde (0.098) conservan el techo del plan: relajarlo
    tambien para ellas dejaba una zona ciega de +0.10 mm en la roja y la verde y de +0.03 mm en el gris. LIMITE DE LA EVIDENCIA, dicho: con 20 semillas de ruido distintas (640 placas, guion
    `b2_corr_r1_semillas_banda.py` del anexo) la banda excede el techo del plan en el 2 % de las placas del gris (maximo 0.070 mm), el 1 % de la roja (0.148) y la verde (0.157) y el 4 % de la azul
    (0.292): el criterio vale para las placas de la prueba (deterministas), no es una garantia estadistica. Ni el generador independiente ni el PNG necesitan limite alguno;
  * pendiente medido/verdadero 1.00 +- 0.01 en cada capa;
  * mas alla de media meseta (|d| >= 3.25 mm) el motor da «No cumple» o «no medible» con su motivo, nunca «Cumple»;
  * veredicto: fuera de la zona de duda de la tolerancia de 1 mm (|d| de 0.75 y de 1.25 mm) la tasa de falsos «Cumple» y de falsos «No cumple» de cada capa es cero;
  * y los de cada caso dificil (`fallos_de_la_variante`).
"""
import gc
import math
from dataclasses import dataclass

import numpy as np

import _placa_braqui_sintetica as pb

CAPAS = ("gris", "R", "G", "B")
COLORES = ("R", "G", "B")
# --------------------------------------------------------------------------------------------------------------------------- los criterios del plan
TECHO_DEL_ERROR_MM = {"gris": 0.05, "R": 0.10, "G": 0.10, "B": 0.10}          # exactitud (OBJETIVO de B.2)
PENDIENTE_MINIMA, PENDIENTE_MAXIMA = 0.99, 1.01                                 # medido / verdadero: 1.00 +- 0.01
TOLERANCIA_MM = 1.0                                                             # la tolerancia fisica (D3 de DA-82); NO se lee del motor: lo que se juzga no puede decidir contra que se juzga
DESFASES_DE_LA_REJILLA = tuple(round(-4.0 + 0.25 * k, 2) for k in range(33))   # de -4 a +4 mm cada 0.25 mm
INCLINACION_DE_LA_LINEA_DEG = 1.5
FORMATOS = ("png", "jpeg")
MEDIA_MESETA_MM = 3.25                                                          # «mas alla de media meseta (~3.2 mm con la mancha calibrada)»: a partir de aqui la linea cae fuera del borde de la meseta
ZONA_PLENA_MM = 2.5                                                             # hasta aqui la linea queda dentro de la meseta de TODA capa (la azul, la mas angosta, tiene semiancho 3.03 mm)
# El limite conocido del modelo fisico con la linea sobre el borde de la meseta (ver el docstring del modulo): modelo -> (desde, hasta] de |d| y {capa: techo medido con margen} de las capas que lo
# necesitan. SOLO la azul (medido 0.147 mm con las semillas de la prueba, 0.29 con otras): las capas que no estan aqui conservan el techo del plan tambien dentro de la banda.
BANDA_DEL_BORDE = {"fisico": (2.5, 3.5, {"B": 0.20})}
# La zona de duda de la tolerancia: con |d| = 1.0 el veredicto depende de la ultima centesima (el limite es inclusivo); 0.75 y 1.25 estan a 0.25 mm: cinco veces el error del gris.
DESFASES_CLAROS_DENTRO, DESFASES_CLAROS_FUERA = 0.75, 1.25

MOTIVO_MINIMO = "no medible: "


# --------------------------------------------------------------------------------------------------------------------------- lo medido
@dataclass(frozen=True)
class Medida:
    """Lo que el motor (o quien se evalue) dice de UNA capa."""
    estado: str                     # 'ok' | 'no medible: <motivo>'
    mm: object                      # desfase en mm (float) o None si no se mide
    veredicto: str                  # 'Cumple' | 'No cumple' | 'No medible'
    sentido: object = None          # texto del sentido fisico (solo el motor lo da)


@dataclass(frozen=True)
class Medicion:
    medidas: dict                   # capa -> Medida
    lado_transito: object = None    # 'derecha' | 'izquierda' | None (solo el motor lo da)
    linea: str = ""                 # como se ubico la linea (solo el motor lo da)
    ancho_meseta_mm: object = None  # ancho (mm) de la meseta del gris del motor, medido como lo mide la referencia independiente de las placas reales (`ancho_central_de_la_meseta_mm`); None si no se mide


@dataclass(frozen=True)
class Caso:
    """Una placa generada, su verdad y lo que se midio."""
    etiqueta: str
    modelo: str                     # 'independiente' | 'fisico'
    desfase: float                  # el pedido al generador (antes de ubicar la escena en una pagina y rotarla)
    verdad: object                  # VerdadBraqui de la imagen devuelta
    medicion: Medicion
    objetivo: object = None         # contra que se juzga el error, si no es la verdad geometrica (el punto medio APARENTE de la fisica); None = la verdad

    @property
    def esperado_mm(self):
        return self.verdad.desfase_mm if self.objetivo is None else self.objetivo

    def error(self, capa):
        m = self.medicion.medidas[capa]
        return None if m.mm is None else m.mm - self.esperado_mm


def medir(placa, motor=None):
    """Lo que hace la aplicacion con una placa generada: leer, analizar con los dos clics y resumir cada capa. `motor` (por omision el de la aplicacion) permite medir una copia mutada."""
    return medir_bytes(placa.datos, placa.clics, motor)


def medir_bytes(datos, clics, motor=None):
    """Lo mismo con los bytes de cualquier archivo de pelicula (una placa real) y sus dos clics."""
    if motor is None:
        from analisisImagenes import posicion_inicial_braqui as motor
    from analisisImagenes.pelicula import leer_pelicula
    pelicula = leer_pelicula(datos)
    gris, color = pelicula.en_bgr()
    r = motor.analizar(gris, color, pelicula.dpi, [tuple(c) for c in clics], validos=pelicula.validos)
    medidas = {}
    for capa in CAPAS:
        s = motor.resumen(r, capa)
        medidas[capa] = Medida(s["estado"], s.get("desfase_mm"), s["veredicto"], s.get("sentido"))
    return Medicion(medidas, r["lado_transito"], r["mensaje_linea"], ancho_central_de_la_meseta_mm(r["perfiles"]["gris"]))


def ancho_central_de_la_meseta_mm(perfil, semialto=15):
    """El ancho (mm) de la meseta SATURADA del gris del motor, medido COMO LO MIDE la referencia independiente de las placas reales (`_referencia_independiente_braqui.referencia_de_la_imagen`): la mediana de las
    cuerdas (x_der - x_izq, subpixel) de las 2 * `semialto` + 1 filas centrales de la mancha (la central es la de los extremos de las filas que usa el motor). None si el perfil no se mide. Sirve para
    comprobar que la referencia mide una meseta de ancho comparable a la del motor (hallazgo DL-03 de la revision): el sentido del 6.4 mm con que la referencia elige su umbral."""
    if perfil.get("estado") != "ok":
        return None
    m, filas = perfil["m"], perfil["filas"]
    cuerdas = (m["x_der"] - m["x_izq"]) * pb.MM_POR_PX
    yc = int(round((filas.min() + filas.max()) / 2.0))
    centrales = [y for y in range(max(0, yc - semialto), min(len(cuerdas), yc + semialto + 1)) if m["inicio"][y] >= 0 and np.isfinite(cuerdas[y])]
    return float(np.median(cuerdas[centrales])) if centrales else None


def caso_de(etiqueta, modelo, desfase, placa, motor=None, objetivo=None):
    return Caso(etiqueta, modelo, desfase, placa.verdad, medir(placa, motor), objetivo)


@dataclass(frozen=True)
class Encargo:
    """Una placa por medir: lo que se genera (con su verdad) antes de medirla con quien sea (el motor, una copia mutada o una replica del cuaderno)."""
    etiqueta: str
    modelo: str
    desfase: float
    placa: object
    objetivo: object = None         # ver Caso.objetivo
    grupo: object = None            # a que grupo del criterio pertenece (p. ej. (giro, dv) de la elipse; 'recorte' o 'pagina')


def caso_a_mano(d, medidas=None, modelo="independiente", sentido=None, lado=None, objetivo=None, grupo=None):
    """Un `Caso` fabricado a mano para probar que cada criterio CAE con un caso malo: `medidas` = {capa: (mm, veredicto) | (None, estado)}; las capas que no se nombran miden exactamente `d`."""
    import types
    ms = {}
    for capa in CAPAS:
        valor = (medidas or {}).get(capa, (d, "Cumple" if abs(d) <= TOLERANCIA_MM else "No cumple"))
        ms[capa] = Medida(valor[1], None, "No medible", None) if valor[0] is None else Medida("ok", valor[0], valor[1], sentido)
    verdad = types.SimpleNamespace(desfase_mm=d, sentido_fisico=sentido, lado_transito=lado)
    return Caso(f"a_mano/d={d:+.2f}", modelo, d, verdad, Medicion(ms, lado), objetivo)


def hacer_casos(encargos, medidor=None):
    """Mide cada encargo con `medidor(placa) -> Medicion` (por omision el motor de la aplicacion) y devuelve los `Caso` en el mismo orden."""
    medidor = medidor or medir
    return [Caso(e.etiqueta, e.modelo, e.desfase, e.placa.verdad, medidor(e.placa), e.objetivo) for e in encargos]


# --------------------------------------------------------------------------------------------------------------------------- las placas
def placa_de_la_rejilla(modelo, inclinada, formato, desfase, indice):
    """La placa de la rejilla (un generador, linea vertical o inclinada 1.5 grados, un formato, un desfase); la semilla del ruido es el indice de la posicion (determinista)."""
    if modelo == "independiente":
        return pb.generar_independiente(desfase, formato=formato, semilla=indice, inclinacion_deg=INCLINACION_DE_LA_LINEA_DEG if inclinada else 0.0)
    return pb.generar_fisico(desfase, escenario="inclinada" if inclinada else "principal", formato=formato, semilla=indice)


_REJILLAS = {}


def liberar_las_rejillas():
    """Suelta las rejillas que `rejilla` guarda por proceso (B.4, deuda heredada de B.3, R1-LD-02). Cada modulo de pruebas que llena el cache la llama desde una fixture de modulo autouse, DESPUES de su yield:
    un cache de modulo vive lo que vive el proceso, y lo que guarda lo heredan los archivos siguientes de su reparto. Vaciar es siempre seguro: `rejilla` las recalcula (no dependen de nada que una prueba
    cambie). Hoy cada `Caso` guarda la verdad y la medicion de su placa (no la placa: ~0.7 MB las ocho combinaciones), pero el contrato no mira cuanto pesa lo que se guarda."""
    _REJILLAS.clear()
    gc.collect()


def rejilla(modelo, inclinada, formato):
    """Los 33 casos de una combinacion (se calculan una vez por proceso: no dependen de nada que una prueba cambie; la bateria de mutaciones corre cada mutacion en un proceso nuevo)."""
    clave = (modelo, bool(inclinada), formato)
    if clave not in _REJILLAS:
        _REJILLAS[clave] = tuple(
            caso_de(f"{modelo}/{'inclinada' if inclinada else 'vertical'}/{formato}/d={d:+.2f}", modelo, d, placa_de_la_rejilla(modelo, inclinada, formato, d, i))
            for i, d in enumerate(DESFASES_DE_LA_REJILLA))
    return _REJILLAS[clave]


def placa_de_la_variante(modelo, variante, desfase, indice, formato="jpeg", **cambios):
    """Una variante dificil de PF.0 CON ruido (el generador fisico es sin ruido por omision: se le da la semilla de la posicion) y, salvo que la variante fije otro, en JPEG."""
    args = pb.argumentos_de_la_variante(modelo, variante)
    args.update(cambios)
    args.setdefault("semilla", indice)
    args.setdefault("formato", formato)
    return (pb.generar_independiente if modelo == "independiente" else pb.generar_fisico)(desfase, **args)


# --------------------------------------------------------------------------------------------------------------------------- utilidades de los criterios
def estadisticos(casos, capa):
    """(errores con signo, n no medibles) de una capa sobre los casos."""
    errores = [c.error(capa) for c in casos if c.error(capa) is not None]
    return errores, sum(1 for c in casos if c.error(capa) is None)


def sesgo_y_dispersion(casos, capa):
    errores, _ = estadisticos(casos, capa)
    return (float(np.mean(errores)), float(np.std(errores))) if errores else (float("nan"), float("nan"))


def capas_con_limite_conocido(modelo):
    """Las capas del `modelo` que declaran un limite conocido en su banda (hoy solo la azul del modelo fisico); () si el modelo no tiene ninguno."""
    banda = BANDA_DEL_BORDE.get(modelo)
    return tuple(banda[2]) if banda is not None else ()


def en_la_banda_del_limite_conocido(modelo, desfase, capa=None):
    """True si `desfase` cae en la banda donde el `modelo` tiene un limite conocido (hoy solo el fisico: la linea sobre el borde de la meseta de la capa). Con `capa`, True solo si ESA capa declara el limite
    (la azul): el gris, la roja y la verde se juzgan con el techo del plan tambien dentro de la banda. Sin `capa`, True si la posicion esta en la banda del modelo (para cualquier capa)."""
    banda = BANDA_DEL_BORDE.get(modelo)
    return banda is not None and banda[0] < abs(desfase) <= banda[1] and (capa is None or capa in banda[2])


def techo_de(modelo, capa, desfase):
    """El techo del error de una capa a un desfase verdadero: el del plan, salvo el limite conocido de la capa azul del modelo fisico con la linea sobre el borde de su meseta."""
    if en_la_banda_del_limite_conocido(modelo, desfase, capa):
        return BANDA_DEL_BORDE[modelo][2][capa]
    return TECHO_DEL_ERROR_MM[capa]


def es_no_medible_con_motivo(medida):
    return medida.mm is None and medida.estado.startswith(MOTIVO_MINIMO) and len(medida.estado) > len(MOTIVO_MINIMO)


# --------------------------------------------------------------------------------------------------------------------------- los criterios de la rejilla
def fallos_de_exactitud(casos):
    """El criterio del plan: error del gris <= 0.05 mm y de cada capa <= 0.10 mm en TODA posicion y en TODA capa, SALVO la capa que declara un limite conocido en su banda (la azul del modelo fisico: la juzga
    `fallos_del_limite_conocido`). Toda capa se mide dentro de la zona plena y la que no se mide fuera de ella dice por que."""
    fallos = []
    for c in casos:
        d = c.verdad.desfase_mm
        for capa in CAPAS:
            if en_la_banda_del_limite_conocido(c.modelo, d, capa):
                continue
            e = c.error(capa)
            m = c.medicion.medidas[capa]
            if e is None:
                if abs(d) <= ZONA_PLENA_MM:
                    fallos.append(f"{c.etiqueta} {capa}: no se mide dentro de la zona plena ({m.estado})")
                elif not es_no_medible_con_motivo(m):
                    fallos.append(f"{c.etiqueta} {capa}: no medible SIN motivo ({m.estado!r})")
                continue
            if abs(e) > TECHO_DEL_ERROR_MM[capa]:
                fallos.append(f"{c.etiqueta} {capa}: error {e:+.3f} mm > {TECHO_DEL_ERROR_MM[capa]:.2f}")
    return fallos


def fallos_del_limite_conocido(casos):
    """La banda del limite conocido del modelo fisico (la linea sobre el borde de la meseta, |d| de 2.5 a 3.5 mm) para la capa que lo declara, la AZUL: su error queda bajo el techo MEDIDO (0.20 mm) y si no se
    mide dice por que. Las demas capas, tambien en la banda, las juzga `fallos_de_exactitud` con el techo del plan. Sin banda en el modelo (el independiente) no hay nada que juzgar aqui: su exactitud es la del
    plan en toda posicion."""
    fallos, vistos = [], 0
    for c in casos:
        d = c.verdad.desfase_mm
        for capa in capas_con_limite_conocido(c.modelo):
            if not en_la_banda_del_limite_conocido(c.modelo, d, capa):
                continue
            e = c.error(capa)
            m = c.medicion.medidas[capa]
            vistos += 1
            if e is None:
                if not es_no_medible_con_motivo(m):
                    fallos.append(f"{c.etiqueta} {capa}: no medible SIN motivo ({m.estado!r})")
                continue
            techo = techo_de(c.modelo, capa, d)
            if abs(e) > techo:
                fallos.append(f"{c.etiqueta} {capa}: error {e:+.3f} mm > el limite conocido {techo:.2f}")
    if BANDA_DEL_BORDE.get(casos[0].modelo) is not None and not vistos:
        fallos.append("ningun caso en la banda del limite conocido")
    return fallos


def fallos_de_la_pendiente(casos):
    """Medido contra verdadero: la recta ajustada sobre las posiciones que se miden tiene pendiente 1.00 +- 0.01 en cada capa."""
    fallos = []
    for capa in CAPAS:
        pares = [(c.esperado_mm, c.medicion.medidas[capa].mm) for c in casos if c.medicion.medidas[capa].mm is not None]
        if len(pares) < 20:
            fallos.append(f"{capa}: solo {len(pares)} posiciones medidas (se piden 20)")
            continue
        v, m = np.array(pares, float).T
        pendiente = float(np.polyfit(v, m, 1)[0])
        if not PENDIENTE_MINIMA <= pendiente <= PENDIENTE_MAXIMA:
            fallos.append(f"{capa}: pendiente {pendiente:.4f} fuera de [{PENDIENTE_MINIMA}, {PENDIENTE_MAXIMA}]")
    return fallos


def fallos_mas_alla_de_media_meseta(casos):
    """|d| >= media meseta: «No cumple» o «no medible» con su motivo, nunca «Cumple»."""
    fallos, vistos = [], 0
    for c in casos:
        if abs(c.verdad.desfase_mm) < MEDIA_MESETA_MM:
            continue
        for capa in CAPAS:
            m = c.medicion.medidas[capa]
            vistos += 1
            if m.mm is None:
                if not es_no_medible_con_motivo(m):
                    fallos.append(f"{c.etiqueta} {capa}: no medible SIN motivo ({m.estado!r}, veredicto {m.veredicto})")
            elif m.veredicto != "No cumple":
                fallos.append(f"{c.etiqueta} {capa}: veredicto {m.veredicto!r} con {m.mm:+.3f} mm medidos")
    if not vistos:
        fallos.append("ningun caso mas alla de media meseta")
    return fallos


def tasas_de_falsos(casos, capa):
    """(falsos «Cumple», casos claramente FUERA, falsos «No cumple», casos claramente DENTRO) entre 0.75 y 1.25 mm: dentro = |d| 0.75, fuera = |d| 1.25 (cada uno a 0.25 mm de la tolerancia)."""
    fuera = [c for c in casos if math.isclose(abs(c.verdad.desfase_mm), DESFASES_CLAROS_FUERA, abs_tol=1e-9)]
    dentro = [c for c in casos if math.isclose(abs(c.verdad.desfase_mm), DESFASES_CLAROS_DENTRO, abs_tol=1e-9)]
    falsos_cumple = sum(1 for c in fuera if c.medicion.medidas[capa].veredicto == "Cumple")
    falsos_no_cumple = sum(1 for c in dentro if c.medicion.medidas[capa].veredicto == "No cumple")
    return falsos_cumple, len(fuera), falsos_no_cumple, len(dentro)


def fallos_de_coherencia_del_veredicto(casos):
    """El veredicto sigue al numero que el motor da: «Cumple» si |desfase| <= 1 mm y «No cumple» si no (la tolerancia es la fisica, no se lee del motor); una capa que no se mide dice «No medible»."""
    fallos, vistos = [], 0
    for c in casos:
        for capa in CAPAS:
            m = c.medicion.medidas[capa]
            if m.mm is None:
                if m.veredicto != "No medible":
                    fallos.append(f"{c.etiqueta} {capa}: no se mide y el veredicto es {m.veredicto!r}")
                continue
            vistos += 1
            esperado = "Cumple" if abs(m.mm) <= TOLERANCIA_MM else "No cumple"
            if m.veredicto != esperado:
                fallos.append(f"{c.etiqueta} {capa}: {m.mm:+.3f} mm y el veredicto es {m.veredicto!r} (debia ser {esperado!r})")
    if not vistos:
        fallos.append("ninguna capa medida")
    return fallos


def fallos_del_veredicto(casos):
    """La tasa de falsos «Cumple» y de falsos «No cumple» de cada capa es cero fuera de la zona de duda (la tolerancia es de 1 mm y la medida se equivoca a lo sumo 0.10 mm)."""
    fallos = []
    for capa in CAPAS:
        fc, n_fuera, fnc, n_dentro = tasas_de_falsos(casos, capa)
        if n_fuera == 0 or n_dentro == 0:
            fallos.append(f"{capa}: no hay casos claros (fuera {n_fuera}, dentro {n_dentro})")
        if fc:
            fallos.append(f"{capa}: {fc} de {n_fuera} falsos «Cumple» con |d| = {DESFASES_CLAROS_FUERA} mm")
        if fnc:
            fallos.append(f"{capa}: {fnc} de {n_dentro} falsos «No cumple» con |d| = {DESFASES_CLAROS_DENTRO} mm")
    return fallos


def fallos_del_sentido_fisico(casos):
    """Solo con banda de transito (modelo fisico): dentro de la zona plena y a 0.25 mm o mas de la marca, el motor dice el mismo sentido fisico que la verdad (antes / despues de la marca)."""
    fallos, vistos = [], 0
    for c in casos:
        d = c.verdad.desfase_mm
        if abs(d) < 0.25 or abs(d) > ZONA_PLENA_MM or c.verdad.sentido_fisico is None:
            continue
        vistos += 1
        dicho = c.medicion.medidas["gris"].sentido
        if dicho != c.verdad.sentido_fisico:
            fallos.append(f"{c.etiqueta}: el motor dice {dicho!r} y la verdad es {c.verdad.sentido_fisico!r} (lado de la banda: motor {c.medicion.lado_transito!r})")
    if not vistos:
        fallos.append("ningun caso con sentido fisico que comparar")
    return fallos


def fallos_de_no_decir_un_sentido_sin_banda(casos):
    """Sin banda de transito (generador independiente) el motor NO inventa un sentido fisico: dice que no se distingue."""
    fallos = []
    for c in casos:
        if c.verdad.sentido_fisico is not None:
            continue
        m = c.medicion.medidas["gris"]
        if m.mm is not None and (c.medicion.lado_transito is not None or "no se distingue" not in (m.sentido or "")):
            fallos.append(f"{c.etiqueta}: sin banda y el motor dice lado {c.medicion.lado_transito!r}, sentido {m.sentido!r}")
    return fallos


# =========================================================================================================================== LAS PLACAS REALES
# Las cuatro peliculas reales de la posicion inicial (PF.0: `PELICULAS_BRAQUI`) con los clics con que se midieron en el anexo (`scripts/med_braqui_reales.py`): EPSON009 con los clics del cuaderno del fisico
# y con los de la suite de PI.1; braqui_00.jpeg con los del fisico; EPSON031 (la pagina entera del escaner: la linea queda HORIZONTAL) con los de G2 de PI.1; y braqui_00.JPG (otro recorte de la misma
# pelicula que braqui_00.jpeg y EPSON031) con los clics de aquel trasladados por la correlacion (desplazamiento (8, 7)). (nombre, archivo en tests/datos o clave del corpus, clics)
TOLERANCIA_CONTRA_LA_REFERENCIA_MM = 0.05     # en gris
DIFERENCIA_ENTRE_RECORTES_MM = {"gris": 0.02, "G": 0.03, "B": 0.03}   # braqui_00.jpeg, braqui_00.JPG y EPSON031 son la MISMA pelicula (dos recortes y la pagina): gris +-0.02 mm; la azul del otro recorte difiere 0.0204
PLACAS_REALES = (
    ("EPSON009 (clics del cuaderno)", "datos/EPSON009.jpeg", ((225, 137), (234, 480))),
    ("EPSON009 (clics de la suite)", "datos/EPSON009.jpeg", ((228, 185), (234, 545))),
    ("braqui_00.jpeg", "datos/braqui_00.jpeg", ((191, 377), (190, 56))),
    ("EPSON031 (pagina entera)", "datos/EPSON031.JPG", ((2511, 3687), (2832, 3686))),
    ("braqui_00.JPG (otro recorte)", "corpus:BRAQUI_00_JPG", ((199, 384), (198, 63))),
)
LA_MISMA_PELICULA = ("braqui_00.jpeg", "EPSON031 (pagina entera)", "braqui_00.JPG (otro recorte)")


def ruta_de_la_placa_real(archivo):
    """Ruta de una placa real: una copia de `tests/datos/` o, con `corpus:CLAVE`, la del corpus del fisico (None si el corpus no esta: skip honesto, HI-0)."""
    import os
    if archivo.startswith("corpus:"):
        import _corpus
        return _corpus.pelicula(archivo.split(":", 1)[1])
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), archivo)


# El acuerdo con la referencia independiente DEPENDE de la meseta que ella elige (hallazgo DL-03 de la revision, ronda 1; las cifras, en el docstring de `test_b2_braqui_placas_reales.py`): la referencia toma
# el umbral T cuya mancha mide el ancho mas cercano a 6.4 mm (la cuerda mas ancha del motor), y con otro umbral la diferencia con el motor es otra. Se fijan la PREMISA (la meseta que elige es de ancho comparable
# a la del motor) y el LIMITE CONOCIDO (con cualquier meseta de ancho comparable el motor coincide a TECHO_CON_OTRA_MESETA_MM).
ANCHO_COMPARABLE_DE_LA_MESETA_MM = 1.0     # dos mesetas son «de ancho comparable» si sus anchos centrales difieren a lo sumo esto. Medido el 14-10: la que elige la regla difiere 0.30 a 0.50 mm de la del motor; las que no lo son, 1.9 a 2.8 mm
TECHO_CON_OTRA_MESETA_MM = 0.12            # con cualquier umbral de meseta comparable el gris del motor difiere de la referencia a lo sumo esto. Medido el 14-10: 0.088 mm (T = 4 en braqui_00.JPG) + 0.03 de margen


def fallos_contra_la_referencia(nombre, motor_mm, referencia_mm, umbral=None):
    """El criterio del plan para una placa real: el gris del motor coincide con la referencia independiente (con el umbral que elige su regla) a <= TOLERANCIA_CONTRA_LA_REFERENCIA_MM."""
    if motor_mm is None:
        return [f"{nombre}: el motor no mide el gris"]
    if referencia_mm is None:
        return [f"{nombre}: la referencia no encontro la mancha"]
    if abs(motor_mm - referencia_mm) > TOLERANCIA_CONTRA_LA_REFERENCIA_MM:
        return [f"{nombre}: motor {motor_mm:+.3f} mm contra la referencia (T = {umbral}) {referencia_mm:+.3f} mm: difieren {abs(motor_mm - referencia_mm):.3f} mm > {TOLERANCIA_CONTRA_LA_REFERENCIA_MM}"]
    return []


def fallos_entre_recortes(valores_por_capa):
    """La MISMA pelicula (dos recortes y la pagina entera) da lo mismo: en cada capa de `DIFERENCIA_ENTRE_RECORTES_MM` los valores que miden las placas difieren a lo sumo lo que ella dice.
    `valores_por_capa` = {capa: {placa: mm | None}}; una capa sin valores, con uno solo o con una placa sin medir no se da por buena."""
    fallos = []
    for capa, tolerancia in DIFERENCIA_ENTRE_RECORTES_MM.items():
        valores = valores_por_capa.get(capa) or {}
        if len(valores) < 2 or any(v is None for v in valores.values()):
            fallos.append(f"{capa}: sin valores que comparar o con una placa sin medir ({valores})")
        elif max(valores.values()) - min(valores.values()) > tolerancia:
            fallos.append(f"{capa}: {valores} difieren mas de {tolerancia} mm")
    return fallos


def fallos_de_la_meseta_comparable(nombre, ancho_motor_mm, ancho_referencia_mm):
    """La PREMISA del acuerdo: la mancha que mide la referencia (con el umbral que elige su regla) es de ancho comparable a la meseta del motor; si midiera otra, ya no se compararia lo mismo."""
    if ancho_motor_mm is None or ancho_referencia_mm is None:
        return [f"{nombre}: falta un ancho de meseta (motor {ancho_motor_mm}, referencia {ancho_referencia_mm})"]
    if abs(ancho_referencia_mm - ancho_motor_mm) > ANCHO_COMPARABLE_DE_LA_MESETA_MM:
        return [f"{nombre}: la referencia mide una mancha de {ancho_referencia_mm:.2f} mm y el motor una meseta de {ancho_motor_mm:.2f} mm: no es la misma meseta (diferencia > {ANCHO_COMPARABLE_DE_LA_MESETA_MM} mm)"]
    return []


def umbrales_con_meseta_comparable(ancho_motor_mm, por_umbral):
    """{T: referencia} de los umbrales que dieron mancha y cuyo ancho es comparable al de la meseta del motor (`por_umbral` = {T: {'desfase_mm', 'ancho_mm', ...} | None})."""
    if ancho_motor_mm is None:
        return {}
    return {T: v for T, v in por_umbral.items() if v is not None and abs(v["ancho_mm"] - ancho_motor_mm) <= ANCHO_COMPARABLE_DE_LA_MESETA_MM}


def fallos_con_otras_mesetas(nombre, motor_mm, ancho_motor_mm, por_umbral):
    """El LIMITE CONOCIDO del acuerdo: con CUALQUIER umbral cuya mancha sea de ancho comparable a la meseta del motor (no solo con el que elige la regla del ancho) el gris del motor coincide con la referencia a
    <= TECHO_CON_OTRA_MESETA_MM. Sin ninguna meseta comparable no hay con que comparar."""
    if motor_mm is None:
        return [f"{nombre}: el motor no mide el gris"]
    comparables = umbrales_con_meseta_comparable(ancho_motor_mm, por_umbral)
    if not comparables:
        return [f"{nombre}: ninguna meseta de la referencia es de ancho comparable a la del motor ({ancho_motor_mm})"]
    return [f"{nombre}: motor {motor_mm:+.3f} mm contra la referencia con T = {T} ({v['ancho_mm']:.2f} mm de mancha) {v['desfase_mm']:+.3f} mm: difieren {abs(motor_mm - v['desfase_mm']):.3f} mm > {TECHO_CON_OTRA_MESETA_MM}"
            for T, v in sorted(comparables.items()) if abs(motor_mm - v["desfase_mm"]) > TECHO_CON_OTRA_MESETA_MM]


# =========================================================================================================================== LOS CASOS DIFICILES
# Cada receta devuelve los `Encargo` de un caso dificil del OBJETIVO de B.2 (las variantes de PF.0, con ruido y en JPEG); cada criterio juzga los `Caso` medidos. Los numeros de los techos salen del plan; donde
# el plan dice «limite conocido» el techo es el medido el 14-10 con un margen y esta dicho.
DESFASES_DIFICILES = (-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0)
TECHO_DE_LOS_CASOS_DIFICILES_MM = 0.10        # mancha corrida, meseta plana en JPEG y franja de transito: <= 0.10 mm en cada capa (gris incluido)
SESGO_DE_LA_ELIPSE_MM = 0.05                  # elipse 6 x 9 mm girada: sesgo (error medio con signo) <= 0.05 mm
DISPERSION_DE_LA_MANCHA_CHICA_MM = {"gris": 0.03, "R": 0.08, "G": 0.08, "B": 0.08}     # mancha chica de 4.5 mm: dispersion (desviacion del error) <= 0.03 mm en el gris (lo que se reporta); la roja llega a 0.052
DIFERENCIA_PAGINA_RECORTE_MM = 0.02           # la misma placa recortada y en pagina entera: +-0.02 mm
CORRIMIENTO_FISICO_MAXIMO_MM = 0.12           # lo que la fisica de la fuente (la franja de transito x 5) corre el punto medio aparente: se mide sobre la imagen sin ruido, sin el motor
GIROS_DE_LA_ELIPSE_DEG = (10.0, 15.0, 20.0)
DESPLAZAMIENTOS_DE_LA_ELIPSE_PX = (0.0, 60.0)            # centrada en los clics y corrida 60 px (2.5 mm) a lo largo de la linea
# El error maximo de la elipse girada es un LIMITE CONOCIDO (el motor descarta de forma asimetrica las filas con un borde tapado por la linea): se fija lo medido el 14-10 (17 desfases, JPEG con ruido,
# gris y las tres capas: 0.31, 0.41 y 0.49 mm con 10, 15 y 20 grados; el plan midio 0.31-0.33 mm) con un margen de 0.04 mm. `scripts/b2_calibrar_dificiles.py` del anexo repite la medicion.
LIMITE_CONOCIDO_DE_LA_ELIPSE_MM = {10.0: 0.35, 15.0: 0.45, 20.0: 0.53}


def semianchos_de_la_meseta_fisica(escenario="principal"):
    """{capa: semiancho (mm)} de la meseta SATURADA de cada capa del modelo fisico: la mitad de la cuerda de saturacion que mide PF.0 (`cuerdas_de_saturacion_px`, independiente del motor) sobre la imagen sin ruido y
    sin linea. Sirve para anclar `BANDA_DEL_BORDE` a la fisica: la linea cae sobre el borde de la meseta de una capa cuando |d| se acerca a su semiancho."""
    par = pb.parametros_del_escenario(escenario)
    cal = pb.calibracion_del_escenario(escenario)
    GF, NT = pb.componentes_dosis(par, 0.0)
    img = pb.escanear(cal["A"] * GF + cal["T_tr"] * NT, par, None, con_linea=False, cuantizar=False)

    def semiancho(canal):
        _, cuerda, _, _ = pb.cuerdas_de_saturacion_px(canal)
        return float(cuerda.max() * pb.MM_POR_PX) / 2.0
    return {"B": semiancho(img[:, :, 0]), "G": semiancho(img[:, :, 1]), "R": semiancho(img[:, :, 2]), "gris": pb.cuerda_de_saturacion_mm(img) / 2.0}


def encargos_de_la_rejilla(modelo, inclinada, formato):
    return [Encargo(f"{modelo}/{'inclinada' if inclinada else 'vertical'}/{formato}/d={d:+.2f}", modelo, d, placa_de_la_rejilla(modelo, inclinada, formato, d, i))
            for i, d in enumerate(DESFASES_DE_LA_REJILLA)]


def encargos_de_una_variante(modelo, variante, desfases=DESFASES_DIFICILES, **cambios):
    return [Encargo(f"{modelo}/{variante}/d={d:+.2f}", modelo, d, placa_de_la_variante(modelo, variante, d, i, **cambios)) for i, d in enumerate(desfases)]


def punto_medio_aparente(escenario, desfase):
    """El desfase APARENTE (mm, positivo = la mancha a la izquierda de la linea) del modelo fisico segun su region saturada, sobre la imagen SIN ruido y SIN linea: lo mide PF.0 (`punto_medio_aparente_mm`),
    sin el motor. No es la verdad (la verdad es el centro geometrico de la fuente): es lo que vale el punto medio de la mancha una vez que la anisotropia y el transito de la fuente lo corren (fisica)."""
    par = pb.parametros_del_escenario(escenario)
    cal = pb.calibracion_del_escenario(escenario)
    GF, NT = pb.componentes_dosis(par, desfase)
    img = pb.escanear(cal["A"] * GF + cal["T_tr"] * NT, par, None, con_linea=False, cuantizar=False)
    return pb.punto_medio_aparente_mm(img)


def encargos_del_transito(modelo):
    """La franja de transito de UN SOLO LADO. Independiente: al 90, 95 y 97 % del tope, a la derecha y a la izquierda (5 desfases cada una). Fisico: la franja x 5 (cable a la derecha; el punto medio aparente
    se corre ~-0.10 mm por fisica) contra el punto medio APARENTE que mide el generador sin ruido."""
    if modelo == "independiente":
        out = []
        for nivel in (0.90, 0.95, 0.97):
            for lado in (+1, -1):
                for i, d in enumerate((-2.0, -1.0, 0.0, 1.0, 2.0)):
                    out.append(Encargo(f"independiente/transito_un_lado/{nivel:.2f}/lado={lado:+d}/d={d:+.2f}", modelo, d,
                                       placa_de_la_variante(modelo, "transito_un_lado", d, i, transito=nivel, lado_transito=lado)))
        return out
    return [Encargo(f"fisico/transito_un_lado/d={d:+.2f}", modelo, d, placa_de_la_variante(modelo, "transito_un_lado", d, i), objetivo=punto_medio_aparente("transito_x5", d))
            for i, d in enumerate(DESFASES_DIFICILES)]


def encargos_de_la_elipse(modelo):
    """Elipse 6 x 9 mm girada 10, 15 y 20 grados respecto de la linea (independiente), centrada en los clics y corrida 60 px; con 17 desfases de -2 a +2 mm. Fisico: el analogo (cateter a 15 grados)."""
    if modelo == "fisico":
        return [Encargo(f"fisico/elipse_girada/d={d:+.2f}", modelo, d, placa_de_la_variante(modelo, "elipse_girada", d, i), grupo=("fisico", 15.0, 0.0))
                for i, d in enumerate(DESFASES_DIFICILES)]
    desfases = tuple(round(-2.0 + 0.25 * k, 2) for k in range(17))
    out = []
    for giro, dv in [(g, 60.0) for g in GIROS_DE_LA_ELIPSE_DEG] + [(15.0, 0.0)]:
        for i, d in enumerate(desfases):
            out.append(Encargo(f"independiente/elipse_girada/giro={giro:g}/dv={dv:g}/d={d:+.2f}", modelo, d,
                               placa_de_la_variante(modelo, "elipse_girada", d, i, giro_elipse_deg=giro, dv_mancha_px=dv), grupo=("independiente", giro, dv)))
    return out


def encargos_de_pagina_y_recorte(modelo, desfases=(-2.0, -1.0, 0.5, 2.0)):
    """La misma placa (misma semilla) recortada y en la pagina entera del escaner."""
    out = []
    for i, d in enumerate(desfases):
        for grupo, pagina in (("recorte", False), ("pagina", True)):
            out.append(Encargo(f"{modelo}/{grupo}/d={d:+.2f}", modelo, d, placa_de_la_variante(modelo, "pagina_entera", d, i, formato="png", pagina=pagina), grupo=(grupo, d)))
    return out


def placa_con_un_objeto_oscuro_fuera_de_la_ventana(placa):
    """La misma pagina con un bloque NEGRO (de 60 a 120 mm de la linea hacia la derecha): fuera de la ventana de analisis de +-20 mm y de la larga del transito de +-52 mm. Una cinta, la sombra de la tapa del
    escaner o un rotulo: si el motor mirara la fila entera, la franja negra (que es la mas ancha) le robaria la mancha."""
    v = placa.verdad
    x0, y0 = v.pagina["origen"]
    x_linea = x0 + v.x_linea
    img = np.array(placa.imagen)
    xa, xb = int(x_linea + 60.0 / pb.MM_POR_PX), min(img.shape[1] - 30, int(x_linea + 120.0 / pb.MM_POR_PX))
    alto_escena = pb.FORMA[0]
    img[max(0, y0 - 250):y0 + alto_escena + 250, xa:xb] = 0
    return pb.PlacaBraqui(pb.codificar(img, "png"), "png", img, placa.clics, v)


def encargos_con_un_objeto_oscuro(modelo, desfases=(-1.5, 0.0, 1.5)):
    out = []
    for i, d in enumerate(desfases):
        base = placa_de_la_variante(modelo, "pagina_entera", d, i, formato="png")
        out.append(Encargo(f"{modelo}/pagina_con_un_bloque_negro/d={d:+.2f}", modelo, d, placa_con_un_objeto_oscuro_fuera_de_la_ventana(base)))
    return out


def encargos_de_la_pagina_rotada(modelo, desfases=(-1.5, 0.75, 2.0), giros=(1, 2, 3)):
    """La pagina del escaner rotada 90, 180 y 270 grados: la VERDAD describe la imagen devuelta (el desfase cambia de signo con 1 y 2 giros), el sentido FISICO no cambia. Con 90 y 270 grados la linea
    queda HORIZONTAL (el motor del cuaderno divide por cero); ademas, con la linea inclinada 1.5 grados queda a 88.5 / 91.5 grados, donde el SENTIDO del giro que el motor aplica importa."""
    out = []
    for i, d in enumerate(desfases):
        for k in giros:
            out.append(Encargo(f"{modelo}/pagina_rotada_{90 * k}/d={d:+.2f}", modelo, d, placa_de_la_variante(modelo, "pagina_entera", d, i, formato="png", rotar_k90=k)))
    for i, d in enumerate((-1.0, 1.5)):
        for k in (1, 3):
            inclinada = {"inclinacion_deg": INCLINACION_DE_LA_LINEA_DEG} if modelo == "independiente" else {"escenario": "inclinada"}
            out.append(Encargo(f"{modelo}/pagina_rotada_{90 * k}_inclinada/d={d:+.2f}", modelo, d, placa_de_la_variante(modelo, "pagina_entera", d, 10 + i, formato="png", rotar_k90=k, **inclinada)))
    return out


# --------------------------------------------------------------------------------------------------------------------------- criterios de los casos dificiles
def fallos_de_error_maximo(casos, techo=TECHO_DE_LOS_CASOS_DIFICILES_MM, capas=CAPAS, admite_no_medible=False, minimo_medidas=1):
    """Cada capa se mide y su error es <= `techo`; si `admite_no_medible`, una capa que no se mide debe decir por que («nunca un numero peor»). Hay al menos `minimo_medidas` medidas por capa (no vacuidad)."""
    fallos = []
    medidas = {capa: 0 for capa in capas}
    for c in casos:
        for capa in capas:
            m = c.medicion.medidas[capa]
            e = c.error(capa)
            if e is None:
                if not (admite_no_medible and es_no_medible_con_motivo(m)):
                    fallos.append(f"{c.etiqueta} {capa}: no se mide ({m.estado!r})")
                continue
            medidas[capa] += 1
            if abs(e) > techo:
                fallos.append(f"{c.etiqueta} {capa}: error {e:+.3f} mm > {techo:.2f}")
    for capa, n in medidas.items():
        if n < minimo_medidas:
            fallos.append(f"{capa}: solo {n} medidas (se piden {minimo_medidas})")
    return fallos


def fallos_del_transito(casos):
    """La franja de transito de un solo lado: el gris, la roja y la verde se miden en TODOS los casos a <= 0.10 mm; la azul se mide a <= 0.10 mm o dice por que no (el plan: "se acepta, no da numero"; el
    verificador midio 20 de 60 imagenes sin la azul), y se mide en al menos un tercio de los casos (no vacuidad)."""
    return (fallos_de_error_maximo(casos, capas=("gris", "R", "G"), minimo_medidas=len(casos))
            + fallos_de_error_maximo(casos, capas=("B",), admite_no_medible=True, minimo_medidas=max(1, len(casos) // 3)))


def fallos_del_corrimiento_fisico(casos):
    """El corrimiento que se le descuenta a la verdad (punto medio aparente - verdad) es fisico y pequeno: lo mide el generador sin el motor; si fuera grande estaria escondiendo un error del motor."""
    fallos = []
    for c in casos:
        if c.objetivo is None:
            fallos.append(f"{c.etiqueta}: sin punto medio aparente")
        elif abs(c.objetivo - c.verdad.desfase_mm) > CORRIMIENTO_FISICO_MAXIMO_MM:
            fallos.append(f"{c.etiqueta}: el corrimiento fisico {c.objetivo - c.verdad.desfase_mm:+.3f} mm pasa de {CORRIMIENTO_FISICO_MAXIMO_MM}")
    return fallos


def grupos_de(encargos_y_casos):
    """{grupo: [Caso]} para (Encargo, Caso) pares."""
    out = {}
    for e, c in encargos_y_casos:
        out.setdefault(e.grupo, []).append(c)
    return out


def fallos_de_la_elipse(por_grupo):
    """Para cada grupo (generador, giro, desplazamiento): el sesgo de cada capa <= 0.05 mm y el error maximo bajo el LIMITE CONOCIDO de su giro."""
    fallos = []
    for grupo, casos in sorted(por_grupo.items(), key=str):
        giro = grupo[1]
        limite = LIMITE_CONOCIDO_DE_LA_ELIPSE_MM.get(giro, max(LIMITE_CONOCIDO_DE_LA_ELIPSE_MM.values())) if grupo[0] == "independiente" else TECHO_DE_LOS_CASOS_DIFICILES_MM
        for capa in CAPAS:
            errores, _ = estadisticos(casos, capa)
            if len(errores) < 0.8 * len(casos):
                fallos.append(f"{grupo} {capa}: solo {len(errores)} de {len(casos)} medidas")
                continue
            sesgo = float(np.mean(errores))
            if abs(sesgo) > SESGO_DE_LA_ELIPSE_MM:
                fallos.append(f"{grupo} {capa}: sesgo {sesgo:+.3f} mm > {SESGO_DE_LA_ELIPSE_MM}")
            peor = float(np.max(np.abs(errores)))
            if peor > limite:
                fallos.append(f"{grupo} {capa}: error maximo {peor:.3f} mm > el limite conocido {limite}")
    return fallos


def fallos_de_la_mancha_chica(casos):
    """Mancha de 4.5 mm: la dispersion del error (desviacion) <= 0.03 mm en el gris (<= 0.05 en las capas) y el sesgo <= 0.03 mm; las capas que no se miden dicen por que (la linea cae sobre el borde de una meseta tan chica)."""
    fallos = []
    for capa in CAPAS:
        errores, _ = estadisticos(casos, capa)
        if len(errores) < 6:
            fallos.append(f"{capa}: solo {len(errores)} medidas (se piden 6)")
            continue
        sesgo, dispersion = float(np.mean(errores)), float(np.std(errores))
        if dispersion > DISPERSION_DE_LA_MANCHA_CHICA_MM[capa]:
            fallos.append(f"{capa}: dispersion {dispersion:.3f} mm > {DISPERSION_DE_LA_MANCHA_CHICA_MM[capa]}")
        if abs(sesgo) > 0.03:
            fallos.append(f"{capa}: sesgo {sesgo:+.3f} mm > 0.03")
    for c in casos:
        for capa in CAPAS:
            m = c.medicion.medidas[capa]
            if m.mm is None and not es_no_medible_con_motivo(m):
                fallos.append(f"{c.etiqueta} {capa}: no medible SIN motivo ({m.estado!r})")
    return fallos


def fallos_de_pagina_contra_recorte(encargos_y_casos):
    """La misma placa recortada y en pagina entera mide lo mismo +-0.02 mm en cada capa."""
    fallos, pares = [], 0
    por_d = {}
    for e, c in encargos_y_casos:
        por_d.setdefault(e.grupo[1], {})[e.grupo[0]] = c
    for d, par in sorted(por_d.items()):
        for capa in CAPAS:
            a, b = par["recorte"].medicion.medidas[capa].mm, par["pagina"].medicion.medidas[capa].mm
            if a is None or b is None:
                fallos.append(f"d={d:+.2f} {capa}: una de las dos no se mide (recorte {a}, pagina {b})")
                continue
            pares += 1
            if abs(a - b) > DIFERENCIA_PAGINA_RECORTE_MM:
                fallos.append(f"d={d:+.2f} {capa}: recorte {a:+.3f} y pagina {b:+.3f} difieren {abs(a - b):.3f} mm > {DIFERENCIA_PAGINA_RECORTE_MM}")
    if not pares:
        fallos.append("ningun par recorte/pagina")
    return fallos


def fallos_de_la_pagina_rotada(casos):
    """La pagina rotada: el desfase medido sigue a la VERDAD DE LA IMAGEN DEVUELTA (gris <= 0.05, capas <= 0.10; la linea queda horizontal con 1 y 3 giros) y, en el modelo fisico, el sentido FISICO no cambia."""
    fallos = fallos_de_exactitud(casos)
    for c in casos:
        if c.verdad.sentido_fisico is not None and c.medicion.medidas["gris"].sentido != c.verdad.sentido_fisico:
            fallos.append(f"{c.etiqueta}: sentido {c.medicion.medidas['gris'].sentido!r} y la verdad es {c.verdad.sentido_fisico!r}")
    return fallos
