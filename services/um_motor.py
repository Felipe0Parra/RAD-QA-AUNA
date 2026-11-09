"""Motor de la calculadora de UM: ecuación 3 de la TG-71, con el factor de campo compilado (Sc·Sp) que exporta Eclipse.

    UM = D · 100 / [ D'0 · OF · Sc(rc)/Sc(lectura) · PDD_N(d, r, SSD) · WF · TF · OAR · ((SSD0 + d0)/(SSD + d0))² · ((SSD + d)/(SSD + prof))² ]

OF·Sc(rc)/Sc(lectura) es el Sc(rc)·Sp(rd0) de la ecuación 3 leído en la tabla de Eclipse; el último término es la corrección por profundidad efectiva
(ecuación 7: vale 1 sin ella). Cada término sale de una función pequeña; `calcular` los junta y devuelve el resultado con todos sus factores, para que la
pantalla los muestre y nada quede escondido. No abre la base y no usa Qt. Lo que está fuera de las tablas no se extrapola (TG-71, 3.A.1): `NoCalculable` dice
por qué y ese campo queda sin número.

El paso del PDD a otra SSD es la ecuación 14 completa. Esa ecuación, con r' el campo que en la tabla de PDD mide a la profundidad d lo mismo que el del plan
(r'·f1(d) = r·f2(d)), se puede escribir como Sp(r·f2(d0))·PDD_N(d, r, SSD2) = F·PDD_N(d, r', SSD1)·Sp(r'·f1(d0)): basta leer el PDD y el factor de campo en r',
sin tablas de TPR y sin ignorar ningún término. Ver `factores_de_lectura`.

Con láminas o bloque (UM.2 v2, UM2-D9), el factor de campo se lee en el CUADRADO EQUIVALENTE del campo efectivo y el Sc se lleva al de las mandíbulas con su
intercambio X/Y, que da la propia tabla: ver `intercambio_de_mandibulas`. Sin curva de Sc (corrección apagada) la corrección vale 1, intercambio incluido (DC3).
"""
import math
from dataclasses import dataclass, field

import numpy as np

# Tabla IV de la TG-71: Sc de muestra de un haz de 6 MV. Se usa si no hay curva del propio haz, y solo como cociente.
SC_MUESTRA_TG71 = ((4.0, 0.957), (5.0, 0.968), (6.0, 0.977), (8.0, 0.990), (10.0, 1.000), (12.0, 1.008), (14.0, 1.014),
                   (16.0, 1.018), (20.0, 1.024), (24.0, 1.029), (28.0, 1.034), (32.0, 1.040), (40.0, 1.048))
SC_MUESTRA_ORIGEN = "tabla IV de la TG-71 (6 MV, otra máquina)"
SC_ESCRITA = "curva de Sc escrita"           # una curva propia que no dice de dónde sale
SC_APAGADA = "corrección de Sc apagada"      # sin curva (`sc=()`): el factor de campo de la tabla no se corrige
SAD_CM = 100.0                       # los dos Clinac
DISTANCIA_MINIMA_AL_BORDE_CM = 2.0   # TG-114: el punto a 2 cm o más del borde
LADO_MINIMO_SIN_AVISO_CM = 4.0       # TG-71, sección 6: por debajo de 4 × 4 pide verificar con medición
OAR_SIN_AVISO_CM = 10.0              # TG-71, 3.B.1.f: el perfil de un campo grande puede errar más de 5 % más allá de unos 10 cm
PERDIDA_AVISO = 0.02                 # si cerca del borde se estima una diferencia de más de 2 %, se avisa
ALARGADO_AVISO = 4.0                 # TG-71, 2.A.2: 4A/P debe verificarse en campos muy alargados (p. ej. 5 × 40)
LADO_MINIMO_CUNA_CM = 3.0            # las tablas de cuña dicen «2» donde la abierta dice 2.5: no se lee por debajo de 3
TOLERANCIA_LADO_CM = 0.1             # un lado equivalente redondeado no es un campo mayor que las mandíbulas
PUNTO_EN_EL_EJE_CM = 0.05            # medio milímetro del eje es estar sobre el eje
ORIENTACIONES_GRADIENTE_EN_X = ("LEFT", "RIGHT")
ORIENTACIONES = ("IN", "OUT") + ORIENTACIONES_GRADIENTE_EN_X
TOLERANCIA_DENTRO_PCT = 2.0          # TG-71, sección 6: «2%–3% agreement» es el criterio más usado
TOLERANCIA_FUERA_PCT = 3.0
SSD_RECHAZO_CM = (60.0, 140.0)
SSD_SIN_AVISO_CM = (80.0, 120.0)
RANGO_FACTOR_CUNA = (0.1, 1.1)       # lo que puede valer un factor de cuña escrito a mano, aquí o al cargar los datos del haz
RANGO_OAR = (0.7, 1.2)               # lo que puede valer un OAR escrito a mano; ningún perfil medido pasa de su máximo
RANGOS = {  # lo que un valor escrito a mano puede ser: (mínimo, máximo), ambos incluidos. Fuera de aquí es un error al escribirlo
    "La dosis": (1e-6, 5000.0), "La profundidad": (1e-6, 100.0), "El factor de cuña": RANGO_FACTOR_CUNA, "El factor de bandeja": (0.5, 1.05),
    "El OAR": RANGO_OAR, "Las UM de Eclipse": (1e-6, 20000.0), "La profundidad efectiva": (1e-6, 100.0),
}
UNIDADES = {"La dosis": "[cGy]", "La profundidad": "[cm]", "Las UM de Eclipse": "[UM]", "La profundidad efectiva": "[cm]"}


class NoCalculable(ValueError):
    """Este campo no tiene número, y el mensaje dice por qué."""


class FueraDeTabla(NoCalculable):
    """La entrada cae fuera de los datos medidos."""


class FaltaDato(NoCalculable):
    """Falta un dato o un dato escrito no es posible."""


class FueraDelCampo(NoCalculable):
    """El punto no está dentro del campo, o el campo no es posible."""


def es_numero(valor):
    """Un número finito de verdad: ni texto, ni booleano, ni NaN ni infinito. La única validación numérica de lo escrito a mano, aquí y al cargar."""
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def equivalente(x, y):
    """Lado del cuadrado equivalente de un rectángulo (4A/P)."""
    return 2 * x * y / (x + y)


def _cifras(valor, limite):
    """El valor con los decimales que hagan falta para que no se lea igual que el límite que pasó (con .2f, 30.004 se leía «30.00» frente a «30»)."""
    n = 2
    while n < 10 and f"{valor:.{n}f}" == f"{limite:.{n}f}":
        n += 1
    return f"{valor:.{n}f}"


def _dentro(valor, minimo, maximo, que):
    if not minimo - 1e-9 <= valor <= maximo + 1e-9:
        raise FueraDeTabla(f"{que} = {_cifras(valor, minimo if valor < minimo else maximo)} [cm] está fuera de la tabla ({minimo:g} a {maximo:g} [cm])")


@dataclass(frozen=True, eq=False)
class TablaFactores:
    """Factor de campo por lados X e Y: se interpola linealmente en el logaritmo de cada lado. Las clases que guardan arreglos de numpy se comparan por
    identidad (`eq=False`): un `==` campo a campo lanzaba ValueError. Para saber si dos haces dan lo mismo, compare sus UM."""
    x: np.ndarray
    y: np.ndarray
    m: np.ndarray

    def __call__(self, x, y, que="la tabla de factores"):
        _dentro(x, self.x[0], self.x[-1], f"El lado X que se lee en {que}")
        _dentro(y, self.y[0], self.y[-1], f"El lado Y que se lee en {que}")
        lx, ly = math.log(x), math.log(y)
        por_filas = [np.interp(lx, np.log(self.x), fila) for fila in self.m]
        return float(np.interp(ly, np.log(self.y), por_filas))

    def contiene(self, x, y):
        return self.x[0] <= x <= self.x[-1] and self.y[0] <= y <= self.y[-1]

    def celdas_usadas(self, x, y):
        """Las celdas de la tabla que pesan en una lectura: una sola si cae justo en ella."""
        def nodos(eje, v):
            j = int(np.clip(np.searchsorted(eje, v), 1, len(eje) - 1))
            return [eje[j]] if eje[j] == v else [eje[j - 1]] if eje[j - 1] == v else [eje[j - 1], eje[j]]
        return {(float(fila), float(col)) for fila in nodos(self.y, y) for col in nodos(self.x, x)}


@dataclass(frozen=True, eq=False)
class FamiliaPDD:
    """PDD [%] a una SSD fija: filas por lado del campo en la superficie, columnas por profundidad."""
    lados: np.ndarray
    z_cm: np.ndarray
    m: np.ndarray

    def __call__(self, d, r):
        _dentro(d, self.z_cm[0], self.z_cm[-1], "La profundidad")
        _dentro(r, self.lados[0], self.lados[-1], "El lado del campo en la superficie")
        i = int(np.clip(np.searchsorted(self.z_cm, d), 1, len(self.z_cm) - 1))
        t = (d - self.z_cm[i - 1]) / (self.z_cm[i] - self.z_cm[i - 1])
        en_d = self.m[:, i - 1] + t * (self.m[:, i] - self.m[:, i - 1])
        return float(np.interp(math.log(r), np.log(self.lados), en_d))

    def _cercano(self, r):
        return int(np.argmin(np.abs(np.log(self.lados) - math.log(r))))

    def dmax(self, r):
        """Profundidad del máximo en el campo medido más cercano."""
        return float(self.z_cm[int(np.argmax(self.m[self._cercano(r)]))])

    def maximo(self, r):
        """El máximo del PDD medido más cercano [%]: 100 si está normalizado como se espera."""
        return float(np.max(self.m[self._cercano(r)]))


@dataclass(frozen=True, eq=False)
class PerfilOAR:
    """D(x)/D(0) de un campo cuadrado a una profundidad y una SSD, con x en el plano de la medida [cm]."""
    prof: float
    lado: float
    x: np.ndarray
    oar: np.ndarray
    ssd: float = 100.0

    @property
    def medido_hasta(self):
        """Hasta dónde llega lo medido, en el plano del isocentro."""
        return float(self.x[-1]) * SAD_CM / (self.ssd + self.prof)

    @property
    def alcance(self):
        """Hasta dónde sirve, en el plano del isocentro: a 2 cm o más del borde de su campo y sin pasar de lo medido."""
        return min(self.lado / 2 - DISTANCIA_MINIMA_AL_BORDE_CM, self.medido_hasta)

    def __call__(self, x_iso):
        return float(np.interp(x_iso * (self.ssd + self.prof) / SAD_CM, self.x, self.oar))


def _par_que_rodea(perfiles, d):
    i = int(np.clip(np.searchsorted([p.prof for p in perfiles], d), 1, len(perfiles) - 1))
    return perfiles[i - 1], perfiles[i]


def _entre_profundidades(perfiles, d, x_iso):
    a, b = _par_que_rodea(perfiles, d)
    return a(x_iso) + (d - a.prof) / (b.prof - a.prof) * (b(x_iso) - a(x_iso))


def _si_alcanza(perfiles, d, x_iso):
    """El valor entre profundidades, o None si estos perfiles no llegan a esa profundidad o a esa distancia."""
    if len(perfiles) < 2 or not perfiles[0].prof <= d <= perfiles[-1].prof or any(x_iso > p.medido_hasta for p in _par_que_rodea(perfiles, d)):
        return None
    return _entre_profundidades(perfiles, d, x_iso)


@dataclass(frozen=True, eq=False)
class PerfilesOAR:
    """`grandes`: por profundidad, el perfil del campo más grande. `todos`: todos los perfiles, para estimar la pérdida junto al borde."""
    grandes: tuple
    todos: tuple

    @property
    def origen(self):
        return "; ".join(f"{p.lado:g} × {p.lado:g} a {p.prof:g} [cm]" for p in self.grandes)

    def __call__(self, d, x_iso):
        """OAR con el perfil del campo más grande, sin salir de lo que ese perfil mide dentro de su campo."""
        if not self.grandes[0].prof <= d <= self.grandes[-1].prof:
            raise FueraDeTabla(f"Los perfiles van de {self.grandes[0].prof:g} a {self.grandes[-1].prof:g} [cm] y el punto está a {d:g} [cm] de profundidad: "
                               "escriba el OAR a mano")
        for p in _par_que_rodea(self.grandes, d):
            if x_iso > p.alcance:
                raise FueraDeTabla(f"El punto está a {x_iso:.1f} [cm] del eje y el perfil de {p.lado:g} × {p.lado:g} [cm] a {p.prof:g} [cm] solo sirve hasta "
                                   f"{p.alcance:g} [cm]: escriba el OAR a mano")
        return _entre_profundidades(self.grandes, d, x_iso)

    def perdida_junto_al_borde(self, lados, distancias, d):
        """Cuánto cambia la dosis por estar cerca del borde, que el OAR de un campo grande no ve: por cada eje, el perfil del cuadrado
        medido como ese lado frente al perfil grande, a la distancia del punto al centro del campo. 1 si no se puede estimar."""
        medidos = sorted({p.lado for p in self.todos})
        total = 1.0
        for lado, distancia in zip(lados, distancias):
            cercano = min(medidos, key=lambda s: abs(math.log(s) - math.log(lado)))
            propio = _si_alcanza(sorted((p for p in self.todos if p.lado == cercano), key=lambda p: p.prof), d, distancia)
            grande = _si_alcanza(self.grandes, d, distancia)
            if propio is not None and grande is not None:
                total *= propio / grande
        return total


@dataclass(frozen=True, eq=False)
class DatosCuna:
    """Una cuña física: cómo varía su factor con el campo (su tabla) y con la profundidad, y su valor en 10 × 10 a d0.

    Lo de la profundidad es, por cada cuadrado medido, la pendiente de ln[WF(d)/WF(d0)]: cociente de los PDD con y sin cuña, hasta `prof_max_cm`.
    `gradiente_en` dice a lo largo de qué eje de la tabla va el gradiente."""
    tabla: TablaFactores
    lados_beta: np.ndarray
    betas: np.ndarray
    prof_max_cm: float
    gradiente_en: str = "Y"
    wf_ref: object = None          # None: no se tiene y no se calcula
    wf_origen: str = ""
    celdas_a_revisar: frozenset = frozenset()

    def por_profundidad(self, d, d0, r):
        beta = np.interp(math.log(r), np.log(self.lados_beta), self.betas)
        return math.exp(float(beta) * (d - d0))


@dataclass(frozen=True, eq=False)
class DatosHaz:
    """Lo que el motor necesita de un haz, ya leído. `d0_norm` es D'0 en las condiciones de la tabla de factores.

    `sc`: la curva de Sc, ((lado, Sc), ...); vacía, la corrección de Sc está apagada. `sc_origen`: de dónde sale, para los textos (`origen_de_sc`)."""
    equipo: str
    energia: str
    ssd0_cm: float
    d0_cm: float
    d0_norm: float
    pdd: FamiliaPDD
    of: TablaFactores
    ssd_pdd_cm: float = 100.0
    sc: tuple = SC_MUESTRA_TG71
    sc_origen: str = SC_MUESTRA_ORIGEN
    perfiles: object = None
    cunas: dict = field(default_factory=dict)
    celdas_a_revisar: frozenset = frozenset()


def origen_de_sc(datos):
    """Lo que hace la corrección de Sc, dicho para el físico: sin curva, que está apagada; con curva, de dónde sale (o que es una curva escrita)."""
    return (datos.sc_origen or SC_ESCRITA) if datos.sc else SC_APAGADA


def d0_en_normalizacion(pdd, d0_dmax, d0_cm):
    """D'0 a la profundidad d0, en 10 × 10 a la SSD de la tabla de PDD, desde D'0 en dmax a esa misma SSD: D'0(dmax)·PDD(d0)/PDD(dmax), con el máximo medido
    y no un 100 supuesto (un PDD con su máximo en 99.6 movía todas las UM un 0.4 %)."""
    return d0_dmax * pdd(d0_cm, 10.0) / pdd.maximo(10.0)


def factor_mayneord(d, d0, ssd, ssd_tabla):
    """Factor F de Mayneord (ecuación 15 de la TG-71): pasa PDD_N de la SSD de la tabla a otra SSD."""
    return ((ssd + d0) / (ssd + d) * (ssd_tabla + d) / (ssd_tabla + d0)) ** 2


def factores_de_lectura(datos, ssd, prof, d):
    """Por cuánto se multiplica un lado del isocentro para leer el PDD (en la superficie de su tabla) y el factor de campo (en su tabla).

    El campo del plan a su profundidad física mide rd = r_iso·(SSD + prof)/SAD. Se lee el campo que en la tabla de PDD mide lo mismo a la
    profundidad de lectura d, que con profundidad efectiva es otra (TG-71, ec. 7: TPR(d_ef, rd)). El factor de campo se lee donde su Sp es el de ese mismo campo.
    A la SSD de las tablas y sin profundidad efectiva, los dos valen exactamente 1."""
    a_la_superficie = (ssd + prof) * datos.ssd_pdd_cm / (SAD_CM * (datos.ssd_pdd_cm + d))
    return a_la_superficie, a_la_superficie * (datos.ssd_pdd_cm + datos.d0_cm) * SAD_CM / (datos.ssd_pdd_cm * (datos.ssd0_cm + datos.d0_cm))


def pdd_normalizado(datos, d, r, ssd):
    """PDD_N(d, r, SSD) en %: leído en r en la tabla, normalizado en d0 y llevado a la SSD pedida con F."""
    tabla = 100.0 * datos.pdd(d, r) / datos.pdd(datos.d0_cm, r)
    return tabla * factor_mayneord(d, datos.d0_cm, ssd, datos.ssd_pdd_cm)


def inverso_cuadrado(datos, ssd):
    """((SSD0 + d0)/(SSD + d0))² de la ecuación 3."""
    return ((datos.ssd0_cm + datos.d0_cm) / (ssd + datos.d0_cm)) ** 2


def correccion_por_profundidad_efectiva(ssd, prof, d):
    """((SSD + d)/(SSD + prof))²: con la profundidad efectiva d, el PDD_N y el inverso del cuadrado de la ecuación 3 quedan en d; esto los devuelve a la
    distancia real del punto (ecuación 7: TPR(d_ef) frente a TPR(d)). Vale 1 sin profundidad efectiva."""
    return ((ssd + d) / (ssd + prof)) ** 2


def sc_de(curva, r):
    """Sc de la curva, sin salir de sus extremos."""
    xs, ys = zip(*curva)
    return float(np.interp(math.log(max(min(r, xs[-1]), xs[0])), np.log(xs), ys))


def correccion_sc(curva, rc, r_lectura):
    """Sc(rc)/Sc(lectura): la tabla trae Sc del campo con que se lee, y la ecuación pide el Sc de las mandíbulas. Vale 1 si coinciden."""
    return sc_de(curva, rc) / sc_de(curva, r_lectura) if curva else 1.0


def intercambio_de_mandibulas(of, x, y):
    """E = OF(x, y)/OF(rc, rc): las dos lecturas tienen el mismo Sp (el del cuadrado equivalente, 4A/P, que es lo que supone la TG-71 en 2.A.2.b) y distinto
    Sc, así que E es lo que el Sc de las mandíbulas x × y se aparta del de su cuadrado equivalente, con su efecto de intercambio X/Y (2.A.2.a.i). Se lee en las
    mandíbulas del isocentro, que es de lo que depende el Sc. Vale 1 en un cuadrado."""
    rc = equivalente(x, y)
    return of(x, y) / of(rc, rc)


def _tolerancias(dentro, fuera):
    """Las tolerancias que el físico puede cambiar en la sesión (DC11): números, mayores que 0 y la de «dentro» no mayor que la de «fuera»."""
    if not (es_numero(dentro) and es_numero(fuera) and 0 < dentro <= fuera):
        raise FaltaDato(f"Las tolerancias deben ser números mayores que 0, la de dentro no mayor que la de fuera [%]: {dentro} y {fuera}")


def estado_de(error_pct, dentro=TOLERANCIA_DENTRO_PCT, fuera=TOLERANCIA_FUERA_PCT):
    """Dentro, Revisar o Fuera, según el valor absoluto del error."""
    _tolerancias(dentro, fuera)
    magnitud = abs(error_pct)
    return "Dentro" if magnitud <= dentro else "Revisar" if magnitud <= fuera else "Fuera"


@dataclass(frozen=True)
class Entrada:
    """Lo que dice el plan de un campo. Longitudes en cm en el plano del isocentro, dosis en cGy.

    `x`, `y`: las mandíbulas. `centro_x`, `centro_y`: el centro de ese campo respecto al eje (0 si es simétrico; con Eclipse, (x2 − x1)/2).
    `x_ef`, `y_ef`: el campo que deja el MLC o el bloque, como rectángulo o como su cuadrado equivalente (los dos iguales); si es el de las mandíbulas (igual,
    o su cuadrado equivalente a 0.1 cm), no hay láminas. `punto_x`, `punto_y`: el punto de cálculo respecto al eje (0, 0 en el isocentro).
    `cuna`: None o el ángulo de la cuña física en grados, un entero; su orientación solo cuenta si hay cuña."""
    dosis: float
    x: float
    y: float
    ssd: float
    prof: float
    x_ef: object = None
    y_ef: object = None
    prof_ef: object = None
    centro_x: float = 0.0
    centro_y: float = 0.0
    punto_x: float = 0.0
    punto_y: float = 0.0
    oar_manual: object = None
    cuna: object = None
    cuna_orientacion: object = None   # IN u OUT: gradiente a lo largo de Y; LEFT o RIGHT: a lo largo de X; None: no se dio (con cuña de tabla, se avisa)
    wf_manual: object = None
    tf: float = 1.0
    um_planeador: object = None


@dataclass(frozen=True)
class Factor:
    simbolo: str
    valor: float
    origen: str    # «tabla», «plan», «cálculo», «manual», y los de un factor que vale 1: «sin cuña», «sin bandeja», «sobre el eje»
    detalle: str = ""


@dataclass(frozen=True)
class Resultado:
    um: float
    d_um: float
    factores: tuple
    avisos: tuple
    campos: dict
    lectura_alterna_of: float
    error_pct: object = None
    estado: object = None


def _rango(nombre):
    minimo, maximo = RANGOS[nombre]
    unidad = f" {UNIDADES[nombre]}" if nombre in UNIDADES else ""
    return f"mayor que 0 y hasta {maximo:g}{unidad}" if minimo < 1e-3 else f"de {minimo:g} a {maximo:g}{unidad}"


def _validar(e):
    """Rechaza lo que no puede ser, antes de leer ninguna tabla. Un valor fuera de rango es un error al escribirlo, no un caso raro."""
    for nombre, valor, obligatorio in (("La dosis", e.dosis, True), ("La profundidad", e.prof, True), ("La profundidad efectiva", e.prof_ef, False), ("El factor de cuña", e.wf_manual, False),
                                       ("El factor de bandeja", e.tf, True), ("El OAR", e.oar_manual, False), ("Las UM de Eclipse", e.um_planeador, False)):
        if valor is None and not obligatorio:
            continue
        minimo, maximo = RANGOS[nombre]
        if not es_numero(valor) or not minimo <= valor <= maximo:
            raise FaltaDato(f"{nombre} no {'son' if nombre.startswith('Las ') else 'es'} un valor posible ({_rango(nombre)}): {valor}")
    for nombre, valor, obligatorio in (("El lado X", e.x, True), ("El lado Y", e.y, True), ("El lado X efectivo", e.x_ef, False), ("El lado Y efectivo", e.y_ef, False)):
        if (valor is not None or obligatorio) and not (es_numero(valor) and valor > 0):
            raise FaltaDato(f"{nombre} debe ser un número mayor que cero")
    if (e.x_ef is None) != (e.y_ef is None):
        raise FaltaDato("Del campo efectivo se necesitan los dos lados")
    if not es_numero(e.ssd) or not SSD_RECHAZO_CM[0] <= e.ssd <= SSD_RECHAZO_CM[1]:
        raise FaltaDato(f"La SSD no es un valor posible (de {SSD_RECHAZO_CM[0]:g} a {SSD_RECHAZO_CM[1]:g} [cm]): {e.ssd}")
    for nombre, valor in (("El centro del campo", e.centro_x), ("El centro del campo", e.centro_y), ("La posición del punto", e.punto_x), ("La posición del punto", e.punto_y)):
        if not es_numero(valor):
            raise FaltaDato(f"{nombre} debe ser un número")
    if e.cuna is not None:
        if not isinstance(e.cuna, int) or isinstance(e.cuna, bool):
            raise FaltaDato(f"La cuña se elige por su ángulo en grados, un número entero, y se recibió «{e.cuna}»")
        if e.cuna_orientacion is not None and e.cuna_orientacion not in ORIENTACIONES:
            raise FaltaDato(f"La orientación de la cuña debe ser {', '.join(ORIENTACIONES)}: «{e.cuna_orientacion}»")


def _margen(e):
    """Lo que hay del punto al borde más cercano de las mandíbulas: negativo o cero, fuera del campo."""
    return min(e.x / 2 - abs(e.punto_x - e.centro_x), e.y / 2 - abs(e.punto_y - e.centro_y))


def _comprobar_campo(datos, e, x_ef, y_ef):
    _dentro(e.x, datos.of.x[0], datos.of.x[-1], "El lado X de las mandíbulas")
    _dentro(e.y, datos.of.y[0], datos.of.y[-1], "El lado Y de las mandíbulas")
    if x_ef == y_ef:     # un cuadrado equivalente puede pasar del lado corto de las mandíbulas: se compara su 4A/P
        mayor = x_ef > equivalente(e.x, e.y) + TOLERANCIA_LADO_CM
    else:
        mayor = x_ef > e.x + TOLERANCIA_LADO_CM or y_ef > e.y + TOLERANCIA_LADO_CM
    if mayor:
        raise FueraDelCampo(f"El campo efectivo ({x_ef:g} × {y_ef:g} [cm]) no puede ser mayor que las mandíbulas ({e.x:g} × {e.y:g} [cm])")
    if _margen(e) <= 0:
        raise FueraDelCampo("El punto queda en el borde o fuera del campo de las mandíbulas: no hay número que comparar. Elija otro punto (TG-114: a 2 [cm] o más del borde)")


def _hay_laminas(e, x_ef, y_ef):
    """Hay láminas o bloque que cambian el campo: el efectivo no son las mandíbulas, ni escritas tal cual ni por su cuadrado equivalente (DC4 y DC15 admiten las
    dos formas; el cuadrado se compara con la misma tolerancia de redondeo que `_comprobar_campo`). Lo usan el cálculo y todos los avisos que dependen de ello."""
    if (x_ef, y_ef) == (e.x, e.y):
        return False
    return not (x_ef == y_ef and abs(x_ef - equivalente(e.x, e.y)) <= TOLERANCIA_LADO_CM)


def _alargamiento(e, x_ef, y_ef):
    """Relación de lados del campo que llega al paciente. Un cuadrado equivalente más ancho que el lado corto de las mandíbulas, a, no es una abertura cuadrada:
    la abertura tiene a lo sumo a de ancho y, con su 4A/P = s, es por lo menos s/(2a − s) veces más larga (2a − s > 0: s es menor que el 4A/P de las mandíbulas)."""
    corto = min(e.x, e.y)
    if x_ef == y_ef and x_ef > corto:
        return x_ef / (2 * corto - x_ef)
    return max(x_ef, y_ef) / min(x_ef, y_ef)


def _oar(datos, e, avisos):
    """OAR(d, x) de la ecuación 3, con d la profundidad física: la corrección de heterogeneidad multiplica la dosis homogénea (TG-71, 2.A.3). Se mide desde el EJE
    del haz, no desde el centro de un campo asimétrico: el perfil es el de un campo centrado en el eje."""
    x_r = math.hypot(e.punto_x, e.punto_y)
    if e.oar_manual is not None:
        return e.oar_manual, "manual", x_r
    if x_r <= PUNTO_EN_EL_EJE_CM:
        return 1.0, "sobre el eje", x_r
    if datos.perfiles is None:
        raise FaltaDato("No hay perfiles cargados: escriba el OAR a mano")
    oar = datos.perfiles(e.prof, x_r)
    if x_r > OAR_SIN_AVISO_CM:
        avisos.append(f"El punto está a {x_r:.1f} [cm] del eje: la TG-71 advierte que el perfil de un campo grande puede errar más de 5 [%] cerca del borde.")
    return oar, "tabla", x_r


def _aviso_de_perdida_junto_al_borde(datos, e, avisos, laminas):
    """Solo si las mandíbulas definen el campo: de las láminas no se sabe dónde queda el punto, y con un OAR a mano manda lo escrito."""
    if datos.perfiles is None or laminas or e.oar_manual is not None:
        return
    perdida = datos.perfiles.perdida_junto_al_borde((e.x, e.y), (abs(e.punto_x - e.centro_x), abs(e.punto_y - e.centro_y)), e.prof)
    if abs(perdida - 1) > PERDIDA_AVISO:
        avisos.append(f"Cerca del borde la ecuación no ve la pérdida de dispersión: según el perfil del cuadrado más parecido a este campo, la dosis cambiaría {100 * (perdida - 1):+.1f} [%].")


def _factor_cuna(datos, e, x_ef, y_ef, r, avisos, lecturas):
    """WF(d, ...) de la ecuación 3, con d la profundidad física. La tabla se lee con el campo efectivo del isocentro: la TG-71 considera el WF independiente de la SSD (3.B.1.i)."""
    if e.wf_manual is not None:
        return e.wf_manual, "manual", "escrito a mano"
    if e.cuna is None:
        return 1.0, "sin cuña", ""
    cuna = datos.cunas.get(e.cuna)
    if cuna is None:
        raise FaltaDato(f"No hay datos de la cuña de {e.cuna}°")
    if cuna.wf_ref is None:
        raise FaltaDato(f"Falta el factor de la cuña de {e.cuna}° en 10 × 10: escríbalo a mano")
    if math.hypot(e.punto_x, e.punto_y) > PUNTO_EN_EL_EJE_CM:
        raise FaltaDato("Con cuña y fuera del eje el factor depende de la posición a lo largo de la cuña: escríbalo a mano")
    if e.prof > cuna.prof_max_cm:
        raise FueraDeTabla(f"La cuña de {e.cuna}° se midió hasta {cuna.prof_max_cm:g} [cm] de profundidad: escriba el factor a mano")
    if e.cuna_orientacion is None:     # UM.2 v2 (UM2-D18): no se supone en silencio
        avisos.append(f"No se dio la orientación de la cuña de {e.cuna}°: se calculó como IN u OUT (gradiente a lo largo de Y); compruébela en el plan.")
    gradiente_del_plan = "X" if e.cuna_orientacion in ORIENTACIONES_GRADIENTE_EN_X else "Y"
    cruzar = gradiente_del_plan != cuna.gradiente_en
    x_c, y_c = (y_ef, x_ef) if cruzar else (x_ef, y_ef)   # los ejes de la tabla de la cuña
    x_m, y_m = (e.y, e.x) if cruzar else (e.x, e.y)
    if min(x_c, y_c) < LADO_MINIMO_CUNA_CM:
        raise FueraDeTabla(f"Con cuña no se lee por debajo de {LADO_MINIMO_CUNA_CM:g} [cm]: las tablas de cuña dicen 2 donde la abierta dice 2.5")
    _dentro(x_m, cuna.tabla.x[0], cuna.tabla.x[-1], f"El lado de las mandíbulas a lo ancho de la cuña de {e.cuna}°")
    _dentro(y_m, cuna.tabla.y[0], cuna.tabla.y[-1], f"El lado de las mandíbulas a lo largo de la cuña de {e.cuna}°")
    por_campo = cuna.tabla(x_c, y_c, f"la tabla de la cuña de {e.cuna}°") / datos.of(x_c, y_c)
    if not cuna.lados_beta[0] <= r <= cuna.lados_beta[-1]:
        avisos.append(f"La variación de la cuña con la profundidad se tomó del campo medido más cercano: el campo en la superficie ({r:.1f} [cm]) queda fuera de los medidos ({cuna.lados_beta[0]:g} a {cuna.lados_beta[-1]:g} [cm]).")
    if cuna.wf_origen:
        avisos.append(cuna.wf_origen)
    if cuna.celdas_a_revisar & cuna.tabla.celdas_usadas(x_c, y_c):
        avisos.append(f"La lectura usa un valor de la tabla de la cuña de {e.cuna}° marcado como fuera de tendencia.")
    lecturas.append((x_c, y_c))     # la lectura de la tabla abierta que divide a la de la cuña también entra en el aviso de celdas (UM.2 v2, A1)
    return cuna.wf_ref * por_campo * cuna.por_profundidad(e.prof, datos.d0_cm, r), "tabla", f"tabla en {x_c:.2f} × {y_c:.2f} [cm]; a {e.prof:g} [cm]"


def calcular(datos, e, dentro=TOLERANCIA_DENTRO_PCT, fuera=TOLERANCIA_FUERA_PCT):
    """UM de un campo con la ecuación 3. Lanza `NoCalculable` si no hay número que dar."""
    _validar(e)
    _tolerancias(dentro, fuera)
    d0, avisos = datos.d0_cm, []
    x_ef, y_ef = (e.x_ef, e.y_ef) if e.x_ef is not None else (e.x, e.y)
    _comprobar_campo(datos, e, x_ef, y_ef)
    laminas = _hay_laminas(e, x_ef, y_ef)
    if not laminas:
        x_ef, y_ef = e.x, e.y     # el efectivo escrito igual a las mandíbulas o como su cuadrado equivalente: el campo es el de las mandíbulas
    rc, r_iso = equivalente(e.x, e.y), equivalente(x_ef, y_ef)
    r = r_iso * e.ssd / SAD_CM
    d = e.prof if e.prof_ef is None else e.prof_ef
    k_pdd, k_of = factores_de_lectura(datos, e.ssd, e.prof, d)
    r_pdd = r_iso * k_pdd
    if laminas:
        # La tabla es Sc·Sp de un campo de MANDÍBULAS. Con láminas o bloque, el Sp es el del cuadrado equivalente del efectivo (TG-71, 2.A.2.b) y el Sc el de las
        # mandíbulas (2.A.2.a.ii): se lee el cuadrado, que no trae intercambio, y el de las mandíbulas se pone con E. Del rectángulo efectivo no se lee nada en la
        # tabla, así que sus lados no tienen que caber en ella; solo su lado corto no puede ser más estrecho que el campo más pequeño medido.
        if min(x_ef, y_ef) * k_of < min(datos.of.x[0], datos.of.y[0]) - 1e-9:      # UM.2 v2 (UM2-D19): más estrecho que lo medido no se calcula
            raise FueraDeTabla(f"El campo efectivo tiene un lado de {_cifras(min(x_ef, y_ef) * k_of, min(datos.of.x[0], datos.of.y[0]))} [cm] en la tabla, más "
                               f"estrecho que el campo más pequeño medido ({min(datos.of.x[0], datos.of.y[0]):g} [cm]): no se calcula")
        # Ronda 1 (F2, DC3 «sin curva, vale 1»): el intercambio es parte de la corrección de Sc, así que con ella apagada vale 1, y sus dos lecturas de la tabla no pesan en el número.
        intercambio = intercambio_de_mandibulas(datos.of, e.x, e.y) if datos.sc else 1.0
        lecturas = [(r_iso * k_of, r_iso * k_of)] + ([(e.x, e.y), (rc, rc)] if datos.sc else [])
    else:
        intercambio, lecturas = 1.0, [(e.x * k_of, e.y * k_of)]
    x_l, y_l = lecturas[0]
    r_lectura = equivalente(x_l, y_l)

    of = datos.of(x_l, y_l)
    c_sc = correccion_sc(datos.sc, rc, r_lectura) * intercambio
    pdd_n = pdd_normalizado(datos, d, r_pdd, e.ssd)
    c_prof = correccion_por_profundidad_efectiva(e.ssd, e.prof, d)
    isl = inverso_cuadrado(datos, e.ssd)
    oar, origen_oar, x_r = _oar(datos, e, avisos)
    wf, origen_wf, detalle_wf = _factor_cuna(datos, e, x_ef, y_ef, r, avisos, lecturas)

    d_um = datos.d0_norm * of * c_sc * (pdd_n / 100.0) * wf * e.tf * oar * isl * c_prof
    if not (math.isfinite(d_um) and d_um > 0):
        raise FaltaDato("El cálculo no dio un número válido: revise las tablas cargadas")
    um = e.dosis / d_um

    if abs(rc - r_lectura) > 1e-9:
        if not datos.sc:
            avisos.append("El campo que se lee en la tabla no es el de las mandíbulas y no hay curva de Sc: no se corrigió.")
        elif min(rc, r_lectura) < datos.sc[0][0] or max(rc, r_lectura) > datos.sc[-1][0]:
            avisos.append(f"La curva de Sc va de {datos.sc[0][0]:g} a {datos.sc[-1][0]:g} [cm] y aquí hizo falta {min(rc, r_lectura):.1f} a {max(rc, r_lectura):.1f} [cm]: se usó su extremo y la corrección puede quedar corta.")
    if laminas:
        sc_a_las_mandibulas = (f"el Sc se lleva al de las mandíbulas ({origen_de_sc(datos)}) con su intercambio X/Y de la tabla, {intercambio:.4f}" if datos.sc
                               else f"el Sc no se lleva al de las mandíbulas ({origen_de_sc(datos)})")
        avisos.append(f"Hay un campo efectivo de lado equivalente {r_iso:.1f} [cm] dentro de unas mandíbulas de lado equivalente {rc:.1f} [cm]: el factor de campo se lee en el "
                      f"cuadrado equivalente del efectivo, y {sc_a_las_mandibulas}. "
                      "La calculadora no conoce las láminas: compruebe que el punto queda dentro de la abertura, a 2 [cm] o más del borde."
                      + (" Con cuña, su factor se lee con el rectángulo efectivo tal como se escribió: escribirlo girado o como su cuadrado equivalente cambia la UM."
                         if e.cuna is not None and e.wf_manual is None else ""))
    if min(d, e.prof) < datos.pdd.dmax(r_pdd):
        avisos.append(f"La profundidad ({min(d, e.prof):.1f} [cm]) es menor que dmax ({datos.pdd.dmax(r_pdd):.1f} [cm]): la TG-71 pide verificar con medición.")
    if d > datos.pdd.z_cm[-2]:     # UM.2 v2 (A5, UM2-D20): ahí la revisión de los archivos deja pasar una cifra dañada del último punto (hasta 6.3 [%] de UM)
        avisos.append(f"La profundidad ({_cifras(d, datos.pdd.z_cm[-2])} [cm]) cae en el último tramo medido del PDD ({datos.pdd.z_cm[-2]:g} a {datos.pdd.z_cm[-1]:g} [cm]): "
                      "la revisión de los archivos no atrapa ahí una cifra dañada del último punto; compruebe ese valor en el archivo.")
    if r < LADO_MINIMO_SIN_AVISO_CM:
        avisos.append(f"Campo pequeño ({r:.1f} [cm] en la superficie): la TG-71 pide verificar con medición por debajo de 4 × 4.")
    if _alargamiento(e, x_ef, y_ef) >= ALARGADO_AVISO:
        avisos.append("Campo muy alargado: se lee con su cuadrado equivalente (4A/P), que la TG-71 pide verificar en estos campos.")
    if not SSD_SIN_AVISO_CM[0] <= e.ssd <= SSD_SIN_AVISO_CM[1]:
        avisos.append(f"SSD de {e.ssd:g} [cm]: las tablas se midieron a {datos.ssd_pdd_cm:g} [cm], y pasar de una a otra supone que el TPR no depende de la distancia.")
    if _margen(e) < DISTANCIA_MINIMA_AL_BORDE_CM:
        avisos.append(f"El punto queda a {_margen(e):.1f} [cm] del borde de las mandíbulas: la TG-114 pide 2 [cm] o más.")
    if abs(e.centro_x) >= e.x / 2 or abs(e.centro_y) >= e.y / 2:
        avisos.append("El eje queda en el borde o fuera del campo de las mandíbulas: compruebe x1, x2, y1 e y2, que van desde el eje y positivos hacia el lado abierto.")
    _aviso_de_perdida_junto_al_borde(datos, e, avisos, laminas)
    if datos.celdas_a_revisar & set().union(*(datos.of.celdas_usadas(a, b) for a, b in lecturas)):
        avisos.append("La lectura usa un valor de la tabla de factores marcado como fuera de tendencia.")

    factores = (
        Factor("D", e.dosis, "plan", "Dosis del campo en el punto [cGy]"),
        Factor("D'0", datos.d0_norm, "tabla", f"[cGy/UM] a SSD {datos.ssd0_cm:g} [cm], {d0:g} [cm] de profundidad, 10 × 10"),
        Factor("OF", of, "tabla", f"Sc·Sp leído en {x_l:.2f} × {y_l:.2f} [cm]" + (", el cuadrado equivalente del campo efectivo" if laminas else "")),
        Factor("Sc(rc)/Sc(lectura)", c_sc, "cálculo", f"rc = {rc:.2f} [cm]; lectura = {r_lectura:.2f} [cm]; {origen_de_sc(datos)}"
               + (f"; intercambio X/Y de las mandíbulas, OF({e.x:g} × {e.y:g})/OF({rc:.2f} × {rc:.2f}) = {intercambio:.4f}" if laminas and datos.sc else "")),
        Factor("PDD_N", pdd_n, "tabla", f"d = {d:.2f} [cm], leído en {r_pdd:.2f} [cm], SSD = {e.ssd:g} [cm]"),
        Factor("WF", wf, origen_wf, detalle_wf),
        Factor("TF", e.tf, "manual" if e.tf != 1.0 else "sin bandeja"),
        Factor("OAR", oar, origen_oar, f"x = {x_r:.2f} [cm], a {e.prof:g} [cm]"),
        Factor("Inverso del cuadrado", isl, "cálculo", f"(({datos.ssd0_cm:g} + {d0:g})/({e.ssd:g} + {d0:g}))²"),
        Factor("Corrección por profundidad efectiva", c_prof, "cálculo", f"(({e.ssd:g} + {d:.2f})/({e.ssd:g} + {e.prof:.2f}))²"),
    )
    error, estado = None, None
    if e.um_planeador is not None:
        error = 100.0 * (um - e.um_planeador) / e.um_planeador
        estado = estado_de(error, dentro, fuera)
    campos = {"rc": rc, "r": r, "rd0": r_iso * (e.ssd + d0) / SAD_CM, "r_pdd": r_pdd, "x_lectura": x_l, "y_lectura": y_l}
    return Resultado(um, d_um, factores, tuple(avisos), campos, datos.of(e.x, e.y), error, estado)
