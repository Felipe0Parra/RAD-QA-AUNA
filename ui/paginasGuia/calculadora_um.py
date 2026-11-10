"""UM.4 (PLAN_CALCULADORA_UM_05-11.md, DC14, DC16): la pestaña «Calculadora UM», con la parte manual.

Sin SQL y sin física: la ecuación vive solo en `services.um_motor.calcular`, y las tablas solo se leen con `services.um_datos_haz` (la única puerta a la base). El archivo tiene dos capas:

  - La CAPA PURA (sin Qt, arriba): de los textos del formulario a una `um_motor.Entrada` o a un motivo (`entrada_desde_textos`), de los umbrales escritos a un par o a un motivo
    (`umbrales_desde_textos`), del `Resultado` a las filas y los textos que se ven (`filas_del_desglose`, `filas_de_los_campos`, `texto_de_las_um`, `texto_del_error`, `texto_del_estado`,
    `texto_para_copiar`) y los textos de «sin tablas» (`texto_sin_tablas`) y de volver a leer el haz (`texto_de_la_relectura`). Se prueba sin crear ningún widget.
  - La CAPA DE WIDGETS (abajo): `CalculadoraUM` y el cuadro `_DialogoInfo`, que solo arman la pantalla y llaman a la capa pura, al servicio y al motor.

Lo que no se puede calcular no da número (DC7): el motivo es el mensaje de `NoCalculable` tal cual, o el de la lectura del formulario. Un cambio en lo escrito, en el equipo o en la energía
borra el resultado anterior: nunca queda en pantalla un número que no corresponde a lo escrito. Los umbrales solo cambian el estado (el error no depende de ellos). No se guarda ningún cálculo
(P7). Los datos de cada haz se guardan en un diccionario de la pantalla por el `id` del conjunto vigente (Trampa 10: sin caché global).

Segunda pasada (10-11, auditoría independiente): ninguna etiqueta fija el ancho de la pestaña según su texto (el texto que cita un motivo se acota); Info y las ayudas dicen la profundidad efectiva y el
plano del punto; al volver a leer las tablas la cuña elegida se conserva si sigue; la lista de avisos se lee entera; sin tablas se vuelve a mirar la base al calcular; un carácter que no se ve se dice;
Enter calcula también desde el botón y las listas; lo copiado empieza con el contexto."""
import math
import re
import unicodedata
from dataclasses import dataclass

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QPushButton, QScrollArea, QSizePolicy, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from services import um_datos_haz, um_motor

# ================================================================================================================================== capa pura (sin Qt)

EQUIPOS = ("Clinac 600", "Clinac iX")    # los de la calculadora, en la forma canónica del lector (`um_lector_eclipse.clave_equipo`); el servicio no los define (UM.3 v2)
SIN_CUNA = "Sin cuña"
ELIJA_ORIENTACION = "Elija la orientación"
TITULO_DE_LA_INFO = "Calculadora UM: de dónde sale cada número"
TAMANO_DE_LA_INFO = (760, 620)
ANCHO_DE_UN_CAMPO = 160          # [px]: cabe «Elija la orientación» con la hoja de estilo de la app
ALTO_DE_UNA_FILA = 24            # [px] de las filas del desglose: las diez caben a 1366 x 768
ECUACION_TEXTO = "UM = D · 100 / [D'0 · Sc(rc) · Sp(rd0) · PDD_N(d, r, SSD) · WF · TF · OAR · ((SSD0 + d0)/(SSD + d0))²]"
ECUACION_MATHTEXT = (r"$UM = \dfrac{D \cdot 100}{D'_0 \cdot S_c(r_c) \cdot S_p(r_{d_0}) \cdot PDD_N(d, r, SSD) \cdot WF \cdot TF \cdot OAR \cdot "
                     r"\left(\dfrac{SSD_0 + d_0}{SSD + d_0}\right)^2}$")
SIN_RESULTADO = "Sin resultado"
SIN_UM_DE_ECLIPSE = "Sin UM de Eclipse: no hay error ni estado."
LA_JSON_LLEGA_DESPUES = ("La parte automática, que calcula cada campo de un plan a partir de un JSON con la misma cuenta de la parte manual, llega en una próxima entrega "
                         "de la calculadora.")
CARGAR_TABLAS_LLEGA_DESPUES = "La carga de tablas se habilita en la próxima entrega de la calculadora; la hacen el físico jefe o el administrador."
_NUMERO = re.compile(r"[+-]?(?:[0-9]+(?:[.,][0-9]*)?|[.,][0-9]+)")      # cifras ASCII, un punto o una coma decimal; nada más (ni exponente, ni unidades, ni separadores de miles)
MAXIMO_CITADO = 30               # caracteres del texto escrito que un motivo cita: un token enorme pegado en un campo no ensancha la ventana (E2)


@dataclass(frozen=True)
class Campo:
    """Un campo de texto del formulario. `clave`: el atributo de `um_motor.Entrada`; `etiqueta`: lo que ve el físico, con la unidad entre corchetes; `nombre`: cómo lo nombra un motivo;
    `obligatorio`; `omision`: lo que vale si se deja vacío (None: el motor no lo usa); `inicial`: el texto con que arranca; `ayuda`: el texto gris del campo vacío, que en un opcional
    empieza por «opcional»; `explicacion`: la ayuda emergente (qué es y qué pasa si se deja vacío)."""
    clave: str
    etiqueta: str
    nombre: str
    obligatorio: bool
    omision: object = None
    inicial: str = ""
    ayuda: str = ""
    explicacion: str = ""


# El orden es el de lectura y el de tabulación (DC14 y el bloque UM.4). La cuña y su orientación (dos listas) van entre el OAR y el WF: ver `ORDEN`.
CAMPOS = (
    Campo("dosis", "Dosis del campo en el punto [cGy]", "la dosis del campo en el punto [cGy]", True, explicacion="La dosis que da este campo en el punto de cálculo, según el plan."),
    Campo("x", "Lado X de las mandíbulas [cm]", "el lado X de las mandíbulas [cm]", True, explicacion="En el isocentro. Con Eclipse, x1 + x2."),
    Campo("y", "Lado Y de las mandíbulas [cm]", "el lado Y de las mandíbulas [cm]", True, explicacion="En el isocentro. Con Eclipse, y1 + y2."),
    Campo("centro_x", "Centro del campo X [cm]", "el centro del campo X [cm]", False, 0.0, ayuda="opcional: 0",
          explicacion="Opcional. El centro del campo de las mandíbulas respecto al eje; vacío vale 0, un campo simétrico. Con Eclipse, (x2 − x1)/2."),
    Campo("centro_y", "Centro del campo Y [cm]", "el centro del campo Y [cm]", False, 0.0, ayuda="opcional: 0",
          explicacion="Opcional. El centro del campo de las mandíbulas respecto al eje; vacío vale 0, un campo simétrico. Con Eclipse, (y2 − y1)/2."),
    Campo("x_ef", "Lado X del campo equivalente [cm]", "el lado X del campo equivalente [cm]", False, ayuda="opcional",
          explicacion="Opcional. El campo que dejan las láminas o el bloque en el isocentro, como rectángulo o como su cuadrado equivalente; vacío, el de las mandíbulas."),
    Campo("y_ef", "Lado Y del campo equivalente [cm]", "el lado Y del campo equivalente [cm]", False, ayuda="opcional",
          explicacion="Opcional. El campo que dejan las láminas o el bloque en el isocentro, como rectángulo o como su cuadrado equivalente; vacío, el de las mandíbulas."),
    Campo("ssd", "SSD [cm]", "la SSD [cm]", True, explicacion="La distancia de la fuente a la superficie."),
    Campo("prof", "Profundidad [cm]", "la profundidad [cm]", True, explicacion="La profundidad física del punto de cálculo."),
    Campo("prof_ef", "Profundidad efectiva [cm]", "la profundidad efectiva [cm]", False, ayuda="opcional",
          explicacion="Opcional. Si el plan corrige por heterogeneidad; vacío, no se corrige. Con ella se mueve el campo de lectura del PDD y del factor de campo; el OAR y el factor de cuña siguen en "
                      "la profundidad física."),
    Campo("punto_x", "Punto X desde el eje [cm]", "el punto X desde el eje [cm]", False, 0.0, ayuda="opcional: 0",
          explicacion="Opcional. La posición del punto de cálculo respecto al eje del haz, en el plano del isocentro (no a la profundidad del cálculo); vacío vale 0, el punto sobre el eje del haz."),
    Campo("punto_y", "Punto Y desde el eje [cm]", "el punto Y desde el eje [cm]", False, 0.0, ayuda="opcional: 0",
          explicacion="Opcional. La posición del punto de cálculo respecto al eje del haz, en el plano del isocentro (no a la profundidad del cálculo); vacío vale 0, el punto sobre el eje del haz."),
    Campo("oar_manual", "OAR", "el OAR", False, ayuda="opcional",
          explicacion="Opcional. Vacío, sale de los perfiles cargados (sobre el eje vale 1); escrito, manda lo escrito."),
    Campo("wf_manual", "Factor de cuña WF", "el factor de cuña WF", False, ayuda="opcional",
          explicacion="Opcional. Vacío, sale de las tablas de la cuña elegida; escrito, manda lo escrito, también sin cuña elegida (una cuña dinámica)."),
    Campo("tf", "Factor de bandeja TF", "el factor de bandeja TF", True, inicial="1.000", explicacion="1.000 sin bandeja."),
    Campo("um_planeador", "UM de Eclipse [UM]", "las UM de Eclipse [UM]", False, ayuda="opcional",
          explicacion="Opcional. Con ellas se calculan el error y el estado; vacío, no se compara."),
)
POR_CLAVE = {campo.clave: campo for campo in CAMPOS}
ORDEN = ("dosis", "x", "y", "centro_x", "centro_y", "x_ef", "y_ef", "ssd", "prof", "prof_ef", "punto_x", "punto_y", "oar_manual", "cuna", "cuna_orientacion", "wf_manual", "tf",
         "um_planeador")
UMBRALES = (("dentro", "Dentro hasta [%]", "el umbral de Dentro [%]", um_motor.TOLERANCIA_DENTRO_PCT),
            ("fuera", "Revisar hasta [%]; más es Fuera", "el umbral de Revisar [%]", um_motor.TOLERANCIA_FUERA_PCT))

# Info (DC14, el bloque UM.4 con los pares del pre-vuelo): un tema por entrada, en este orden. Se buscan por su TÍTULO (la prueba no mira internos de Qt).
INFO = (
    ("La ecuación",
     "Es la ecuación 3 de la TG-71, la del PDD normalizado (PDD_N). Sirve para tratamientos a SSD fija y para isocéntricos: " + ECUACION_TEXTO + ". Con profundidad efectiva, el "
     "desglose suma su corrección, ((SSD + d_ef)/(SSD + d))², para que el inverso del cuadrado siga siendo el de la distancia real. Cada factor se ve en el desglose con su valor y su "
     "origen: tabla, plan, cálculo o manual; y «sin cuña», «sin bandeja» o «sobre el eje» cuando el factor vale 1 porque no hay cuña, ni bandeja, ni un punto fuera del eje."),
    ("El factor de campo (OF) compila Sc y Sp",
     "La tabla de Eclipse se midió en agua y trae los dos juntos. Sc es la dispersión del cabezal, y depende de las mandíbulas. Sp es la del maniquí, y depende del campo en el paciente. "
     "La tabla mide los dos con el mismo campo, en las condiciones de su cabecera: en el Clinac 600, SSD 100 [cm] y 5 [cm] de profundidad."),
    ("Cuándo se corrige",
     "Si la SSD no es la de la tabla, el campo a la profundidad del cálculo ya no es el mismo: la tabla y el PDD se leen en el campo que, a esa profundidad, mide lo mismo que el del plan. "
     "Así se aplica completa la ecuación 14 de la TG-71, sin tablas de TPR. Si las láminas o un bloque recortan el campo, el factor de campo se lee en el cuadrado equivalente del campo "
     "efectivo, que da su Sp, y el Sc se lleva al de las mandíbulas con su intercambio X/Y, que da la propia tabla. Con profundidad efectiva, el PDD y el factor de campo se leen con ella en lugar de la profundidad física, y el campo de lectura se mueve con ella. En los tres casos "
     "Sc se corrige con un cociente, Sc(rc)/Sc(lectura): la "
     "tabla trae el Sc del campo con que se leyó y la ecuación pide el de las mandíbulas. La curva de Sc, y de dónde sale, aparece en el desglose: en 6 MV a 5 [cm] se estima de la tabla de "
     "este haz y del Sp de la TG-71; en otro caso es la tabla IV de la TG-71, de otra máquina; una curva medida las reemplaza y se guarda con su origen. Sin curva, la corrección está "
     "apagada, también el intercambio X/Y, y el desglose lo dice. A la SSD de la tabla, sin láminas y sin profundidad efectiva la corrección vale 1."),
    ("Tres campos",
     "El de las mandíbulas en el isocentro (rc), el del campo efectivo en la superficie (r) y el mismo a la profundidad d0 de la tabla (rd0), como los define la TG-71. Los tres se ven "
     "encima del desglose, en la línea «Campos». El desglose dice en qué campo se leyó cada factor, por lo que un factor suelto puede diferir un poco de una cuenta a mano con r y rd0; su producto es el de la "
     "ecuación 14 completa. La lectura alterna del OF es el de la tabla leído directamente en las mandíbulas, sin corregir, para comparar."),
    ("D'0",
     "El servicio lo maneja en dmax (Eclipse usa 1 [cGy/UM]): se escribe al cargar las tablas, con su origen, y queda guardado con ellas. El cálculo lo usa a la profundidad d0 de la "
     "tabla, pasándolo con el PDD del 10 × 10: su valor en d0 dividido por su máximo medido; el desglose dice el valor que usó y en qué condiciones. Si la tabla no está a la SSD de los PDD, se escribe al cargar en "
     "las condiciones de la tabla."),
    ("PDD_N",
     "El PDD medido a la SSD de los PDD (100 [cm] en el Clinac 600), normalizado en d0, leído en ese campo y pasado a la SSD del plan con el factor F de Mayneord."),
    ("De dónde sale el OAR",
     "De los perfiles de campo abierto, las curvas de distancia al eje frente a dosis relativa. Es la dosis fuera del eje dividida por la del eje, a la misma profundidad. Se usa el campo "
     "más grande, con x proyectado al plano de la medida, a la profundidad física. x es la distancia del punto al eje, en el plano del isocentro (no a la profundidad del cálculo); el perfil es a lo largo de X y no hay perfil diagonal. Sobre el eje "
     "vale 1. Cerca del borde se estima la pérdida con el perfil del campo más parecido y se avisa si pasa de 2 [%]. La TG-71 prefiere el perfil primario, advierte errores de más de "
     "5 [%] cerca del borde (x mayor que 10 [cm]) y recomienda mantener el cálculo sobre el eje. Escrito a mano, manda lo escrito; sin perfiles cargados y fuera del eje, hay que escribirlo."),
    ("La cuña",
     "WF = WF(10 × 10; d0) · [OF de la cuña / OF abierto](campo leído) · exp[β · (d − d0)]. El primer término es la dosis de referencia que exporta Eclipse dividida por D'0 a d0, o el valor "
     "escrito al cargar, que manda. El de 15° se dedujo suponiendo que esa dosis es a 5 [cm]: está por confirmar, y cada resultado con esa cuña lo avisa con su valor y los dos datos de que "
     "sale. Las de 30°, 45° y 60° no lo tienen: sin él no hay número, salvo que se escriba el factor a mano. El cociente de tablas se lee con el campo efectivo del isocentro, sin "
     "proyectar, porque la TG-71 considera el factor de cuña independiente de la SSD; con láminas se lee con el rectángulo efectivo tal como se escribió, así que escribirlo girado o "
     "como su cuadrado equivalente cambia las UM, y se avisa. β sale de los PDD con y sin cuña de cada campo medido, y se aplica en la profundidad física. La orientación dice a lo largo "
     "de qué eje va el gradiente: IN u OUT, a lo largo de Y; LEFT o RIGHT, a lo largo de X; aquí siempre se elige. Con cuña y fuera del eje el factor depende de la posición a lo largo de "
     "la cuña: hay que escribirlo a mano. Con un factor escrito a mano manda lo escrito, también para una cuña dinámica."),
    ("Tolerancia",
     "Error = 100 · (UM calculadas − UM de Eclipse)/UM de Eclipse. Dentro hasta 2 [%], Revisar de 2 a 3 [%] y Fuera más de 3 [%]: es el criterio de 2 a 3 [%] que la TG-71 llama el más "
     "usado. La TG-71 pide que cada servicio fije sus criterios de acción, y la TG-114 da niveles de 2 a 5 [%] según el caso. El físico fija el criterio: los dos umbrales se pueden cambiar "
     "aquí, solo para esta sesión, y cambiarlos cambia el estado, no las UM ni el error."),
    ("Lo que no cubre",
     "IMRT, VMAT, electrones, y cuñas dinámicas sin su factor escrito. No conoce las láminas: un punto bajo una lámina da un número, así que D debe ser la dosis real del campo en el punto. "
     "Por eso, con campo efectivo, no se puede saber a cuánto queda el punto del borde de la abertura, y se avisa. El PDD, y con láminas el factor de campo, se leen en el cuadrado "
     "equivalente, que no distingue entre X e Y: en campos muy alargados, de una relación de lados de 4 o más, se avisa. Una profundidad en el último tramo medido del PDD también se "
     "avisa: ahí una cifra dañada del último punto no se puede detectar al cargar. No se guarda ningún cálculo."),
)


def _citar(texto):
    """El texto escrito, para que un motivo lo cite: los `MAXIMO_CITADO` primeros caracteres y «…» si hay más (un token enorme no ensancha la ventana)."""
    texto = texto.strip()
    return texto if len(texto) <= MAXIMO_CITADO else texto[:MAXIMO_CITADO] + "…"


def _no_se_ve(texto):
    """Si `texto` lleva un carácter que no se ve (formato Cf, control Cc o un espacio Zs que no es el normal) o un guion que no es el signo menos (categoría Pd distinta de «-»)."""
    for caracter in texto:
        categoria = unicodedata.category(caracter)
        if categoria in ("Cf", "Cc") or (categoria == "Zs" and caracter != " ") or (categoria == "Pd" and caracter != "-"):
            return True
    return False


def leer_numero(texto, campo):
    """El número que dice `texto` para `campo`, o `campo.omision` si está vacío y es opcional. `um_motor.FaltaDato` si falta o no se entiende: nunca un número adivinado. Acepta cifras con
    un punto o una coma decimal y el signo (también «−»); rechaza unidades, exponentes, separadores de miles, `inf`, `nan` y cifras que no son ASCII. Un 0 escrito es 0, no el valor por
    omisión: el motor decide si es posible."""
    limpio = texto.strip().replace("\u2212", "-")
    if not limpio:
        if campo.obligatorio:
            raise um_motor.FaltaDato(f"Falta escribir {campo.nombre}.")
        return campo.omision
    if not _NUMERO.fullmatch(limpio):
        if _no_se_ve(limpio):       # E3: pegado desde un PDF, un correo o un archivo: el motivo dice qué sobra, no solo lo que se ve
            raise um_motor.FaltaDato(f"No se entiende {campo.nombre}: «{_citar(texto)}» contiene un carácter que no se ve o un guion que no es el signo menos: bórrelo y escriba el número de nuevo.")
        raise um_motor.FaltaDato(f"No se entiende {campo.nombre}: «{_citar(texto)}». Escriba solo el número, con punto o coma decimal y sin unidades.")
    valor = float(limpio.replace(",", "."))
    if not math.isfinite(valor):
        raise um_motor.FaltaDato(f"{campo.nombre[0].upper()}{campo.nombre[1:]} tiene demasiadas cifras: «{_citar(texto)}».")
    return valor


def entrada_desde_textos(textos, cuna, orientacion):
    """La `um_motor.Entrada` de lo escrito: `textos` {clave: texto} de los campos de `CAMPOS`; `cuna` None o el ángulo; `orientacion` None (sin elegir) o una de `um_motor.ORIENTACIONES`.
    Todos los motivos de lectura juntos, uno por línea, en el orden del formulario. Los rangos NO se repiten aquí: los decide el motor."""
    valores, motivos = {}, []
    for campo in CAMPOS:
        try:
            valores[campo.clave] = leer_numero(textos.get(campo.clave, ""), campo)
        except um_motor.FaltaDato as fallo:
            motivos.append(str(fallo))
    if cuna is not None:
        if orientacion is None:
            motivos.append("Con cuña, elija su orientación: IN u OUT si el gradiente va a lo largo de Y; LEFT o RIGHT si va a lo largo de X.")
        valores["cuna"], valores["cuna_orientacion"] = cuna, orientacion
    if motivos:
        raise um_motor.FaltaDato("\n".join(motivos))
    return um_motor.Entrada(**valores)


def umbrales_desde_textos(texto_dentro, texto_fuera):
    """(dentro, fuera) de los dos umbrales escritos [%], o `um_motor.FaltaDato` con el motivo. La pantalla solo LEE los dos números; la regla de qué umbrales sirven (0 < dentro <= fuera)
    es la del motor, la misma con que `um_motor.estado_de` decide el estado: una sola definición."""
    (_, _, nombre_dentro, _), (_, _, nombre_fuera, _) = UMBRALES
    dentro = leer_numero(texto_dentro, Campo("dentro", "", nombre_dentro, True))
    fuera = leer_numero(texto_fuera, Campo("fuera", "", nombre_fuera, True))
    um_motor.estado_de(0.0, dentro, fuera)
    return dentro, fuera


def texto_sin_tablas(equipo):
    """El aviso de «sin tablas». Dice lo mismo que la ayuda de «Cargar tablas» (`CARGAR_TABLAS_LLEGA_DESPUES`: la carga llega en la próxima entrega, y quién la hace) y no manda a ese botón mientras
    esté deshabilitado."""
    return f"No hay tablas cargadas del {equipo}: sin ellas no se puede calcular. {CARGAR_TABLAS_LLEGA_DESPUES} Se hace una vez por energía, con los archivos que exporta Eclipse."


def texto_de_la_relectura(id_antes, id_ahora, aviso, cuna_perdida=None):
    """Por qué `calcular` se detuvo al volver a leer el haz (UM4-D9): lo que dice la pantalla es lo que pasó con esa lectura. `id_antes`: el conjunto con que se llenó la lista de cuñas (None: no se pudo
    leer al elegir la energía); `id_ahora`: el que dejó la relectura (None: tampoco se pudo); `aviso`: lo que dice la pantalla tras la relectura; `cuna_perdida`: el ángulo de la cuña elegida
    que el conjunto nuevo ya no trae (None: se conservó, o no había)."""
    if id_ahora is None:
        return aviso
    if id_antes is None:
        return "Las tablas de este haz no se habían podido leer al elegir la energía: ya se leyeron. Revise la cuña y pulse Calcular otra vez."
    perdida = "" if cuna_perdida is None else f" La cuña de {cuna_perdida}° ya no está en las tablas nuevas: volvió a Sin cuña."
    return f"Las tablas de este haz cambiaron desde que se eligió la energía: se volvieron a leer.{perdida} Revise la cuña y pulse Calcular otra vez."


def texto_de_las_tablas_nuevas(equipo, id_ahora, aviso):
    """Por qué `calcular` se detuvo tras volver a mirar la base sin energías (EST-2): ahora hay tablas y falta elegir la energía y la cuña (nunca un número con una energía que nadie eligió); si
    el haz sigue sin poder leerse (`id_ahora` None), el motivo es ese fallo, el mismo del aviso (no se mezclan con los de `texto_de_la_relectura`)."""
    if id_ahora is None:
        return aviso
    return f"Ahora hay tablas cargadas del {equipo}. Elija la energía y la cuña y pulse Calcular otra vez."


def _cuatro(valor):
    return f"{valor:.4f}"


def filas_del_desglose(resultado):
    """Una fila por factor del motor, en su orden: (factor, valor, origen, detalle). El valor con cuatro decimales; nada se redondea antes."""
    return [(f.simbolo, _cuatro(f.valor), f.origen, f.detalle) for f in resultado.factores]


def filas_de_los_campos(resultado):
    """Los tres campos de la TG-71 (rc, r y rd0) y la lectura alterna del OF: (nombre, valor, qué es)."""
    c = resultado.campos
    return [("rc", f"{c['rc']:.2f} [cm]", "Campo de las mandíbulas en el isocentro"),
            ("r", f"{c['r']:.2f} [cm]", "Campo efectivo en la superficie"),
            ("rd0", f"{c['rd0']:.2f} [cm]", "Campo efectivo a la profundidad d0 de la tabla"),
            ("OF en las mandíbulas", _cuatro(resultado.lectura_alterna_of), "Lectura alterna: la tabla leída directamente en las mandíbulas del isocentro, sin corregir")]


def texto_de_los_campos(resultado):
    """Los mismos, en una línea, para la pantalla (lo que es cada uno va en su ayuda emergente y en Info)."""
    filas = filas_de_los_campos(resultado)
    return "Campos: " + "; ".join(f"{nombre} {valor}" for nombre, valor, _ in filas[:3]) + f". {filas[3][0]}: {filas[3][1]}"


def texto_de_las_um(resultado):
    return f"UM calculadas: {resultado.um:.1f} [UM]"


def texto_de_d_um(resultado):
    return f"D/UM: {resultado.d_um:.4f} [cGy/UM]"


def texto_del_error(error_pct, umbrales):
    """El error con signo y dos decimales; con más si con dos se leería igual que un umbral que no es el suyo (con dos, 2.004 se leía «2.00» y su estado es Revisar). Las cifras junto a
    un límite las decide `um_motor.cifras`, el único formato de un valor junto a su límite (desde UM.2b, un valor IGUAL al límite va con el formato normal)."""
    n = max([len(um_motor.cifras(abs(error_pct), u).split(".")[1]) for u in umbrales] + [2])
    return f"Error frente a Eclipse: {error_pct:+.{n}f} [%]"


def texto_del_estado(error_pct, textos_de_umbrales):
    """«Estado: Dentro/Revisar/Fuera» con el error SIN redondear y la regla del motor (`um_motor.estado_de`), o el motivo si los umbrales escritos no sirven."""
    try:
        dentro, fuera = umbrales_desde_textos(*textos_de_umbrales)
    except um_motor.FaltaDato as fallo:
        return f"Estado sin evaluar: {fallo}"
    return f"Estado: {um_motor.estado_de(error_pct, dentro, fuera)}"


def texto_del_contexto(equipo, energia, cuna, orientacion, um_planeador, texto_error, texto_estado):
    """La primera línea de lo que se copia (UM4-D11): a qué haz y a qué cuña corresponde el desglose, las UM de Eclipse y cómo quedó frente a ellas, con los mismos textos que la pantalla
    (`texto_error` y `texto_estado` son los de sus etiquetas: sin UM de Eclipse dicen que no hay error ni estado, y no se inventan)."""
    partes = [f"Equipo: {equipo}", f"Energía: {energia}", "Cuña: " + (SIN_CUNA if cuna is None else f"{cuna}° ({orientacion})")]
    if um_planeador is not None:
        partes.append(f"UM de Eclipse: {um_planeador:g} [UM]")
    return " | ".join(partes + [texto for texto in (texto_error, texto_estado) if texto])


def texto_para_copiar(resultado, contexto=None):
    """El desglose, los tres campos y los avisos en texto separado por tabuladores, para pegarlo en una hoja de cálculo o un correo; con `contexto` (`texto_del_contexto`), empieza con esa línea."""
    lineas = [texto_de_las_um(resultado), texto_de_d_um(resultado), "", "Factor\tValor\tOrigen\tDetalle"]
    lineas += ["\t".join(fila) for fila in filas_del_desglose(resultado)]
    lineas += ["", "Campo\tValor\tQué es"] + ["\t".join(fila) for fila in filas_de_los_campos(resultado)]
    lineas += ["", "Avisos"] + list(resultado.avisos)
    return "\n".join(([contexto] if contexto else []) + lineas)


# ================================================================================================================================== capa de widgets

def dibujar_ecuacion(alto=76, ancho=700):
    """La ecuación con mathtext sobre `FigureCanvasAgg`, como `QPixmap`; None si matplotlib falla (la pantalla deja el texto plano). Sin `pyplot`: no toca el backend global ni deja
    figuras vivas."""
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        figura = Figure(figsize=(ancho / 100, alto / 100), dpi=100)
        figura.patch.set_alpha(0.0)
        figura.text(0.01, 0.5, ECUACION_MATHTEXT, fontsize=13, va="center", ha="left")
        lienzo = FigureCanvasAgg(figura)
        lienzo.draw()
        ancho_px, alto_px = lienzo.get_width_height()
        imagen = QImage(bytes(lienzo.buffer_rgba()), ancho_px, alto_px, QImage.Format_RGBA8888)
        return QPixmap.fromImage(imagen.copy())
    except Exception:   # noqa: BLE001 -- cualquier fallo del dibujo deja el texto plano; la ecuación nunca se pierde
        return None


class _DialogoInfo(QDialog):
    """El cuadro «Info» (modelo: `placa_mensual._DialogoInfo`): un título y un texto por tema de `INFO`, en un área con barra. No es modal (`show`, nunca `exec_`), es hijo de la pestaña (se
    destruye con ella) y se cierra con la cruz o con Esc."""

    def __init__(self, padre):
        super().__init__(padre)
        self.setWindowTitle(TITULO_DE_LA_INFO)
        self.setModal(False)
        interior = QWidget()
        capa = QVBoxLayout(interior)
        self.etiquetas = []
        for titulo, texto in INFO:
            cabeza, cuerpo = QLabel(f"<b>{titulo}</b>"), QLabel(texto)
            cuerpo.setWordWrap(True)
            cuerpo.setTextInteractionFlags(Qt.TextSelectableByMouse)
            capa.addWidget(cabeza)
            capa.addWidget(cuerpo)
            self.etiquetas.append((cabeza, cuerpo))
        capa.addStretch(1)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setWidget(interior)
        QVBoxLayout(self).addWidget(area)
        self.resize(*TAMANO_DE_LA_INFO)

    def textos(self):
        """Lo que dice el cuadro, tema por tema: (título, texto)."""
        return [(re.sub(r"</?b>", "", cabeza.text()), cuerpo.text()) for cabeza, cuerpo in self.etiquetas]


def _tabla(columnas):
    tabla = QTableWidget(0, len(columnas))
    tabla.setHorizontalHeaderLabels(list(columnas))
    tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
    tabla.setSelectionMode(QAbstractItemView.ExtendedSelection)
    tabla.verticalHeader().setVisible(False)
    tabla.verticalHeader().setDefaultSectionSize(ALTO_DE_UNA_FILA)
    cabecera = tabla.horizontalHeader()
    cabecera.setSectionResizeMode(QHeaderView.ResizeToContents)
    cabecera.setStretchLastSection(True)
    cabecera.setFixedHeight(ALTO_DE_UNA_FILA + 10)
    return tabla


def _llenar(tabla, filas):
    tabla.setRowCount(len(filas))
    for i, fila in enumerate(filas):
        for j, texto in enumerate(fila):
            celda = QTableWidgetItem(texto)
            celda.setToolTip(texto)
            tabla.setItem(i, j, celda)


class CalculadoraUM(QWidget):
    """La pestaña. `usuario` es la identidad de la sesión (la de `MainWindow`): UM.4 no la usa (no guarda nada) y la recibe para que «Cargar tablas» se conecte sin tocar `mainpages.py`."""

    def __init__(self, usuario=None, parent=None):
        super().__init__(parent)
        self.usuario = usuario
        self._haces = {}             # id del conjunto vigente -> um_motor.DatosHaz (Trampa 10)
        self._id_del_haz = None      # el conjunto con que se llenó la lista de cuñas
        self.resultado = None
        self._contexto = None        # (equipo, energía, cuña, orientación, UM de Eclipse) con que se calculó el resultado que se ve: lo que lleva la primera línea de lo copiado
        self.dialogo_info = None
        self._armar()
        self._al_cambiar_equipo()

    # ------------------------------------------------------------------ armado
    def _armar(self):
        principal = QVBoxLayout(self)
        barra = QHBoxLayout()
        self.combo_equipo, self.combo_energia = QComboBox(), QComboBox()
        self.combo_equipo.addItems(EQUIPOS)
        self.boton_cargar, self.boton_info = QPushButton("Cargar tablas"), QPushButton("Info")
        self.boton_cargar.setEnabled(False)
        self.boton_cargar.setToolTip(CARGAR_TABLAS_LLEGA_DESPUES)
        for texto, widget in (("Equipo", self.combo_equipo), ("Energía", self.combo_energia)):
            barra.addWidget(QLabel(texto))
            barra.addWidget(widget)
        barra.addWidget(self.boton_cargar)
        self.ecuacion = QLabel()
        dibujo = dibujar_ecuacion()
        if dibujo is None:
            self.ecuacion.setText(ECUACION_TEXTO)
        else:
            self.ecuacion.setPixmap(dibujo)
        self.ecuacion.setToolTip(ECUACION_TEXTO)
        barra.addWidget(self.ecuacion, 1, Qt.AlignCenter)
        barra.addWidget(self.boton_info)
        principal.addLayout(barra)
        self.aviso_tablas = QLabel()
        self.aviso_tablas.setWordWrap(True)
        principal.addWidget(self.aviso_tablas)

        self.subpestanas = QTabWidget()
        self.subpestanas.addTab(self._armar_manual(), "Manual")
        json = QLabel(LA_JSON_LLEGA_DESPUES)
        json.setWordWrap(True)
        json.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.subpestanas.addTab(json, "Desde JSON")
        principal.addWidget(self.subpestanas, 1)

        self.combo_equipo.currentIndexChanged.connect(self._al_cambiar_equipo)
        self.combo_energia.currentIndexChanged.connect(self._al_cambiar_energia)
        self.boton_info.clicked.connect(self.mostrar_info)

    def _armar_manual(self):
        """El formulario en dos columnas (las nueve primeras entradas de `ORDEN` y las nueve siguientes), «Calcular» y los umbrales debajo; a la derecha el resultado."""
        self.campos, self.umbrales, self.etiquetas = {}, {}, {}
        izquierda = QWidget()
        rejilla = QGridLayout(izquierda)
        mitad = (len(ORDEN) + 1) // 2
        for i, clave in enumerate(ORDEN):
            if clave == "cuna":
                etiqueta, widget = "Cuña", QComboBox()
                self.combo_cuna = widget
            elif clave == "cuna_orientacion":
                etiqueta, widget = "Orientación de la cuña", QComboBox()
                widget.addItem(ELIJA_ORIENTACION, None)
                for orientacion in um_motor.ORIENTACIONES:
                    widget.addItem(orientacion, orientacion)
                self.combo_orientacion = widget
            else:
                campo = POR_CLAVE[clave]
                etiqueta, widget = campo.etiqueta, QLineEdit(campo.inicial)
                widget.setPlaceholderText(campo.ayuda)
                widget.setToolTip(campo.explicacion)
                widget.setMaximumWidth(ANCHO_DE_UN_CAMPO)
                self.campos[clave] = widget
            fila, columna = i % mitad, 2 * (i // mitad)
            self.etiquetas[clave] = QLabel(etiqueta)
            rejilla.addWidget(self.etiquetas[clave], fila, columna)
            rejilla.addWidget(widget, fila, columna + 1)
        self.boton_calcular = QPushButton("Calcular")
        rejilla.addWidget(self.boton_calcular, mitad, 0, 1, 4)
        for i, (clave, etiqueta, _, valor) in enumerate(UMBRALES):
            self.umbrales[clave], self.etiquetas[clave] = QLineEdit(f"{valor:g}"), QLabel(etiqueta)
            rejilla.addWidget(self.etiquetas[clave], mitad + 1, 2 * i)
            rejilla.addWidget(self.umbrales[clave], mitad + 1, 2 * i + 1)
        rejilla.setRowStretch(mitad + 2, 1)

        derecha = QWidget()
        capa = QVBoxLayout(derecha)
        self.etiqueta_um, self.etiqueta_d_um, self.etiqueta_error, self.etiqueta_estado = QLabel(), QLabel(), QLabel(), QLabel()
        self.etiqueta_motivo, self.etiqueta_campos = QLabel(), QLabel()
        for etiquetas in ((self.etiqueta_um, self.etiqueta_d_um), (self.etiqueta_error, self.etiqueta_estado), (self.etiqueta_motivo,), (self.etiqueta_campos,)):
            linea = QHBoxLayout()
            for etiqueta, peso in zip(etiquetas, (3, 2)):      # en una fila de dos, la primera (la UM, el error) lleva más ancho: cabe en una línea
                etiqueta.setTextInteractionFlags(Qt.TextSelectableByMouse)
                linea.addWidget(etiqueta, peso)
            capa.addLayout(linea)
        self.etiqueta_um.setStyleSheet("font-size: 14pt; font-weight: bold;")
        self.etiqueta_campos.setToolTip("rc: el campo de las mandíbulas en el isocentro; r: el campo efectivo en la superficie; rd0: el mismo a la profundidad d0 de la tabla. "
                                        "OF en las mandíbulas: la tabla leída directamente en las mandíbulas, sin corregir, para comparar (ver Info).")
        self.tabla_desglose = _tabla(("Factor", "Valor", "Origen", "Detalle"))
        self.lista_avisos = QListWidget()
        self.lista_avisos.setWordWrap(True)
        self.lista_avisos.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)      # TP-1: por ítem, un aviso más alto que el panel quedaba cortado y sin barra
        self.titulo_avisos = QLabel()
        # E2: cada etiqueta cuyo texto cambia con lo escrito o con el resultado ajusta la línea y se reparte el ancho de su fila: ninguna fija el ancho mínimo de la pestaña según su texto
        for etiqueta in (self.etiqueta_um, self.etiqueta_d_um, self.etiqueta_error, self.etiqueta_estado, self.etiqueta_motivo, self.etiqueta_campos, self.aviso_tablas, self.titulo_avisos):
            etiqueta.setWordWrap(True)
            etiqueta.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        avisos = QWidget()
        capa_avisos = QVBoxLayout(avisos)
        capa_avisos.setContentsMargins(0, 0, 0, 0)
        capa_avisos.addWidget(self.titulo_avisos)
        capa_avisos.addWidget(self.lista_avisos)
        partes = QSplitter(Qt.Vertical)
        partes.setChildrenCollapsible(False)      # TP-1: el divisor no deja el panel de los avisos en cero
        self.divisor_del_resultado = partes
        for parte, peso in ((self.tabla_desglose, 3), (avisos, 1)):
            partes.addWidget(parte)
            partes.setStretchFactor(partes.count() - 1, peso)
        capa.addWidget(partes, 1)
        self.boton_copiar = QPushButton("Copiar el desglose")
        capa.addWidget(self.boton_copiar)

        divisor = QSplitter(Qt.Horizontal)
        divisor.addWidget(izquierda)
        divisor.addWidget(derecha)
        divisor.setStretchFactor(0, 0)
        divisor.setStretchFactor(1, 1)

        # El orden de tabulación es el de creación (Qt): los campos se crean en el orden de `ORDEN`, y luego «Calcular» y los dos umbrales; la prueba lo fija.
        for linea in self.campos.values():
            linea.returnPressed.connect(self.calcular)
            linea.textEdited.connect(self.limpiar_resultado)
        self.combo_cuna.currentIndexChanged.connect(self._al_cambiar_cuna)
        self.combo_orientacion.currentIndexChanged.connect(self.limpiar_resultado)
        for linea in self.umbrales.values():
            linea.textEdited.connect(self._mostrar_estado)
            linea.returnPressed.connect(self.calcular)
        self.boton_calcular.clicked.connect(self.calcular)
        self.boton_copiar.clicked.connect(self.copiar)
        for widget in (self.boton_calcular, self.combo_cuna, self.combo_orientacion):
            widget.installEventFilter(self)       # EST-4: Enter calcula también con el foco en el botón y en las dos listas (en un campo ya lo hace `returnPressed`)
        self.limpiar_resultado()
        return divisor

    def eventFilter(self, objeto, evento):
        if evento.type() == QEvent.KeyPress and evento.key() in (Qt.Key_Return, Qt.Key_Enter) and objeto in (self.boton_calcular, self.combo_cuna, self.combo_orientacion):
            self.calcular()
            return True
        return super().eventFilter(objeto, evento)

    # ------------------------------------------------------------------ el haz
    def _equipo_y_energia(self):
        return self.combo_equipo.currentText(), self.combo_energia.currentData()

    def _al_cambiar_equipo(self):
        equipo = self.combo_equipo.currentText()
        self.combo_energia.blockSignals(True)
        self.combo_energia.clear()
        try:
            energias = um_datos_haz.energias_cargadas(equipo)
        except Exception as fallo:   # noqa: BLE001 -- se dice, no se traga: sin energías no hay número
            energias, self.aviso_tablas_texto = [], f"No se pudieron leer las tablas guardadas del {equipo}: {fallo}"
        else:
            self.aviso_tablas_texto = "" if energias else texto_sin_tablas(equipo)
        for energia in energias:
            self.combo_energia.addItem(energia, energia)
        self.combo_energia.setEnabled(bool(energias))
        self.combo_energia.blockSignals(False)
        self._al_cambiar_energia()

    def _leer_haz(self):
        """(id, DatosHaz) del conjunto vigente del equipo y la energía elegidos, o `um_motor.FaltaDato` con el motivo (sin tablas, o lo guardado no se puede usar)."""
        equipo, energia = self._equipo_y_energia()
        if energia is None:
            raise um_motor.FaltaDato(self.aviso_tablas_texto or texto_sin_tablas(equipo))
        try:
            registro = um_datos_haz.vigente(equipo, energia)
            if registro is None:
                raise um_motor.FaltaDato(f"Ya no hay tablas vigentes del {equipo}, {energia}.")
            if registro["id"] not in self._haces:
                datos = um_datos_haz.datos_del_haz(equipo, energia)
                if datos is None:
                    raise um_motor.FaltaDato(f"Ya no hay tablas vigentes del {equipo}, {energia}.")
                self._haces[registro["id"]] = datos
        except um_motor.FaltaDato:
            raise
        except um_datos_haz.DatosHazError as fallo:
            raise um_motor.FaltaDato(str(fallo)) from fallo
        except Exception as fallo:   # noqa: BLE001 -- un fallo de la base se dice con su texto, nunca cae en silencio a otro haz
            raise um_motor.FaltaDato(f"No se pudieron leer las tablas guardadas del {equipo}, {energia}: {fallo}") from fallo
        return registro["id"], self._haces[registro["id"]]

    def _al_cambiar_energia(self, *_, conservar_cuna=False):
        """Rehace la lista de cuñas del haz de la energía elegida. `conservar_cuna` (solo al volver a leer un conjunto nuevo dentro de `calcular`): la cuña elegida sigue elegida si el conjunto
        nuevo la trae, con su orientación (que no se toca); si no, vuelve a «Sin cuña». Como slot de la lista de energías, `conservar_cuna` queda en False."""
        elegida = self.combo_cuna.currentData() if conservar_cuna else None
        self.combo_cuna.blockSignals(True)
        self.combo_cuna.clear()
        self.combo_cuna.addItem(SIN_CUNA, None)
        self._id_del_haz = None
        texto = self.aviso_tablas_texto
        if self.combo_energia.currentData() is not None:
            try:
                self._id_del_haz, datos = self._leer_haz()
            except um_motor.FaltaDato as fallo:
                texto = str(fallo)
            else:
                for angulo in sorted(datos.cunas):
                    self.combo_cuna.addItem(f"{angulo}°", angulo)
                if elegida in datos.cunas:
                    self.combo_cuna.setCurrentIndex(self.combo_cuna.findData(elegida))
        self.combo_cuna.blockSignals(False)
        self.aviso_tablas.setText(texto)
        self.aviso_tablas.setVisible(bool(texto))
        self._al_cambiar_cuna()

    def _al_cambiar_cuna(self):
        con_cuna = self.combo_cuna.currentData() is not None
        if not con_cuna:
            self.combo_orientacion.setCurrentIndex(0)
        self.combo_orientacion.setEnabled(con_cuna)
        self.limpiar_resultado()

    # ------------------------------------------------------------------ el cálculo
    def textos(self):
        return {clave: linea.text() for clave, linea in self.campos.items()}

    def _textos_de_umbrales(self):
        return self.umbrales["dentro"].text(), self.umbrales["fuera"].text()

    def limpiar_resultado(self, *_):
        self.resultado = None
        self._contexto = None
        self.etiqueta_um.setText(SIN_RESULTADO)
        for etiqueta in (self.etiqueta_d_um, self.etiqueta_error, self.etiqueta_estado, self.etiqueta_motivo, self.etiqueta_campos):
            etiqueta.setText("")
        self.etiqueta_motivo.setVisible(False)
        self.etiqueta_campos.setVisible(False)
        self.tabla_desglose.setRowCount(0)
        self.lista_avisos.clear()
        self.titulo_avisos.setText("Avisos")
        self.boton_copiar.setEnabled(False)

    def calcular(self):
        """Lee el formulario, pide al motor las UM con los datos del haz vigente y muestra el resultado, o el motivo y ningún número."""
        self.limpiar_resultado()
        try:
            if self.combo_energia.currentData() is None:       # EST-2: sin energías (no había tablas, o la base falló al listarlas): se vuelve a mirar antes de decir que faltan
                self._al_cambiar_equipo()
                if self.combo_energia.currentData() is not None:
                    raise um_motor.FaltaDato(texto_de_las_tablas_nuevas(self.combo_equipo.currentText(), self._id_del_haz, self.aviso_tablas.text()))
            ident, datos = self._leer_haz()
            if ident != self._id_del_haz:
                antes, cuna = self._id_del_haz, self.combo_cuna.currentData()
                self._al_cambiar_energia(conservar_cuna=True)
                raise um_motor.FaltaDato(texto_de_la_relectura(antes, self._id_del_haz, self.aviso_tablas.text(), cuna if self.combo_cuna.currentData() is None else None))
            entrada = entrada_desde_textos(self.textos(), self.combo_cuna.currentData(), self.combo_orientacion.currentData())
            resultado = um_motor.calcular(datos, entrada)
        except um_motor.NoCalculable as fallo:
            self._poner_motivo(str(fallo))
            return
        except Exception as fallo:   # noqa: BLE001 -- un error que no es un motivo se dice como tal y no deja número
            self._poner_motivo(f"El cálculo falló por un error inesperado ({type(fallo).__name__}: {fallo}). Avise a quien mantiene la app.")
            return
        self.resultado = resultado
        self._contexto = (self.combo_equipo.currentText(), self.combo_energia.currentText(), entrada.cuna, entrada.cuna_orientacion, entrada.um_planeador)
        self.etiqueta_um.setText(texto_de_las_um(resultado))
        self.etiqueta_d_um.setText(texto_de_d_um(resultado))
        _llenar(self.tabla_desglose, filas_del_desglose(resultado))
        self.etiqueta_campos.setText(texto_de_los_campos(resultado))
        self.etiqueta_campos.setVisible(True)
        for aviso in resultado.avisos:
            self.lista_avisos.addItem(QListWidgetItem(aviso))
        self.titulo_avisos.setText(f"Avisos ({len(resultado.avisos)})")
        self.boton_copiar.setEnabled(True)
        self._mostrar_estado()

    def _poner_motivo(self, texto):
        self.etiqueta_motivo.setText(texto)
        self.etiqueta_motivo.setVisible(True)

    def _mostrar_estado(self, *_):
        """El error y el estado del resultado que se ve, con los umbrales escritos ahora: cambiarlos no cambia las UM ni el error."""
        if self.resultado is None:
            return
        if self.resultado.error_pct is None:
            self.etiqueta_error.setText(SIN_UM_DE_ECLIPSE)
            self.etiqueta_estado.setText("")
            return
        textos = self._textos_de_umbrales()
        try:
            umbrales = umbrales_desde_textos(*textos)
        except um_motor.FaltaDato:
            umbrales = ()        # sin umbrales que sirvan, el error va con dos decimales y el estado dice el motivo
        self.etiqueta_error.setText(texto_del_error(self.resultado.error_pct, umbrales))
        self.etiqueta_estado.setText(texto_del_estado(self.resultado.error_pct, textos))

    def copiar(self):
        if self.resultado is not None:
            contexto = texto_del_contexto(*self._contexto, self.etiqueta_error.text(), self.etiqueta_estado.text())
            QApplication.clipboard().setText(texto_para_copiar(self.resultado, contexto))

    def mostrar_info(self):
        if self.dialogo_info is None:
            self.dialogo_info = _DialogoInfo(self)
        self.dialogo_info.show()
        self.dialogo_info.raise_()
