"""CD.5 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, DA-92): los DIBUJOS y los TEXTOS de la ventana de calibración de las películas (`ui/paginasControles/PruebasMensuales/curva_dosis.py`).

Es lo que la ventana compone, separado de ella para probarlo sin Qt (como `dibujo_placa_mensual.py` hace con la ventana mensual): cada función de dibujo recibe un eje que le da quien llama y dibuja lo que el
MOTOR midió y ajustó (`analisisImagenes/curva_dosis.py`: la `CurvaDeDosis` con sus piezas); ninguna calcula una densidad óptica, una dosis, un residuo ni un parámetro de la curva. La curva de cada capa se
evalúa con `CurvaDeDosis.dosis`, la ÚNICA definición del modelo (CD.9). La única cuenta propia es `residuo_maximo`, que ELIGE entre los residuos que dio el motor el de mayor valor absoluto.

El gráfico (DA-92, «todo eso en un mismo gráfico en esa ventana con grid y leyenda»): los pares (densidad óptica neta, dosis) de cada pieza con su ±u en netOD y la curva de Devic de cada capa, en su color
(los de la ventana mensual, `COLOR_CAPA`), con rejilla y leyenda. La curva llega hasta la netOD de la última pieza de esa capa, sin extrapolar; el tramo fuera de su rango útil va punteado y sus piezas,
huecas. Debajo, en un gráfico pequeño, los residuos de las cuatro capas en %. La dosis de cada par es la que entró al ajuste (`dosis_cgy`: la medida, contada desde el cero de la curva), la misma con la que
el motor calculó el residuo.

Sin Qt ni `pyplot`. Sin símbolos de correcto o incorrecto (DA-18) y con las unidades entre corchetes. Lo que viene del usuario (las condiciones, los textos libres) se escribe con `texto_seguro`, que no
lanza por un valor raro (la regla de CD.4 para quien lo muestre: `OverflowError`, `ValueError` y `TypeError` dan «no legible»)."""
import math
import numbers

import numpy as np

from analisisImagenes import curva_dosis as motor
from analisisImagenes.dibujo_placa_mensual import COLOR_CAPA, COLOR_REJILLA, NO_MEDIBLE, TINTA, TINTA_SUAVE
from analisisImagenes.pelicula import ADJETIVO_DE_LA_CAPA, CAPAS_DEL_PISO

CAPAS = CAPAS_DEL_PISO                                   # R, G, B y el gris: las cuatro que calibra la curva (DC1)
PLANTILLA_DE_DOSIS = (0.0, 50.0, 100.0, 150.0, 200.0, 300.0, 400.0, 500.0, 600.0, 800.0, 1000.0)     # P12 de la curva: la plantilla con que arranca la tabla (0 = la película virgen)
TIPOS_DE_PELICULA = ("EBT3", "EBT4", "EBT-XD")          # el menú es editable: «u otro»
ENERGIAS = ("6 MV", "10 MV", "15 MV", "6 MV FFF", "10 MV FFF")
ACELERADORES = ("Clinac 600", "Clinac iX", "Halcyon")
MB_DE_AVISO = 20.0                                       # DC14: un escaneo de más de 20 MB se avisa (se recomienda escanear solo el área de la pieza)
DECIMALES_NETOD = 4
PUNTOS_DE_LA_CURVA = 200
ESTILO_EN_EL_RANGO = "-"
ESTILO_FUERA_DEL_RANGO = ":"
ETIQUETA_NETOD = "densidad óptica neta [1]"
ETIQUETA_DOSIS = "dosis [cGy]"
ETIQUETA_RESIDUO = "residuo [%]"
NO_LEGIBLE = "no legible"
SIN_CERO = "sin cero"                                    # CD5-PROD-R1-05: lo que dice la celda de una pieza bien medida mientras la curva no tiene cero
RECORTADA = "recortada por el escáner"
SIN_IMAGEN = "sin imagen"
SIN_IMAGEN_VIRGEN = "sin imagen (película virgen)"
TEXTO_FUERA_DEL_RANGO = "fuera del rango útil: punteado, piezas huecas"
NOMBRE_EN_EL_GRAFICO = {c: (f"capa {ADJETIVO_DE_LA_CAPA[c]}" if c != "gris" else "gris") for c in CAPAS}

COLUMNAS_DE_LAS_PIEZAS = ("Dosis nominal [cGy]", "Imagen", "Archivo", "Dosis medida [cGy]", "netOD roja [1]", "netOD verde [1]", "netOD azul [1]", "netOD gris [1]", "Quitar")
COLUMNA_NOMINAL, COLUMNA_CARGAR, COLUMNA_ARCHIVO, COLUMNA_MEDIDA = 0, 1, 2, 3
COLUMNA_DE_LA_CAPA = {"R": 4, "G": 5, "B": 6, "gris": 7}
COLUMNA_QUITAR = 8
COLUMNAS_DE_LA_CURVA = ("Capa", "a [cGy]", "b [cGy]", "n [1]", "Rango útil [cGy]", "Residuo máximo [%]", "RMS [%]", "Estado")          # el estado (un texto largo) al final: los números se ven sin desplazar


# ----------------------------------------------------------------------------------------------------- textos

def texto_seguro(valor):
    """Un valor que viene del usuario (de las condiciones de irradiación o de un texto libre) como texto, sin lanzar nunca: un entero de más de 4300 cifras (`str` lanza `ValueError`), uno que no cabe en un
    real (`format` lanza `OverflowError`) o un objeto raro dan «no legible», y nunca se omite el campo (regla del 08-09)."""
    if valor is None:
        return ""
    try:
        if isinstance(valor, bool):
            return "sí" if valor else "no"
        if isinstance(valor, float):
            return f"{valor:g}"
        return str(valor)
    except (OverflowError, ValueError, TypeError):
        return NO_LEGIBLE


def leer_numero(texto):
    """(valor, problema) de lo que el físico escribió en un campo numérico: vacío da (None, None); la coma decimal vale como punto; un texto que no es un número finito da (None, «no es un número: '...'»).
    La ventana pasa al servicio NÚMEROS, nunca el texto del formulario (lo pide CD.4)."""
    limpio = (texto or "").strip()
    if not limpio:
        return None, None
    try:
        valor = float(limpio.replace(",", "."))
    except ValueError:
        return None, f"no es un número: {limpio!r}"
    if not math.isfinite(valor):
        return None, f"no es un número finito: {limpio!r}"
    return valor, None


def numero_del_catalogo(valor):
    """El número que el catálogo de equipos guarda en un campo (el factor de una cámara o de un electrómetro), como `float`, o None. CD5-PR-7: un número real se toma TAL CUAL (la copia guardada, DA-13, es el
    número del catálogo y no su texto de seis cifras de `texto_seguro`); un texto, con `leer_numero` (la coma decimal vale); y lo que no es un número finito (nada, un texto como «No Aplica», un booleano,
    un entero que no cabe en un real) no es nada. Nunca lanza."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, numbers.Real):
        try:
            numero = float(valor)
        except (OverflowError, ValueError, TypeError):
            return None
        return numero if math.isfinite(numero) else None
    if isinstance(valor, str):
        return leer_numero(valor)[0]
    return None


def texto_de_la_dosis(valor):
    """Una dosis de la tabla de piezas: el número tal como lo escribiría el físico («50», «100.5»), o vacío."""
    return "" if valor is None else f"{float(valor):g}"


def _cifra(valor, decimales):
    return "" if valor is None else f"{float(valor):.{decimales}f}"


def texto_de_la_capa_de_la_pieza(pieza, capa, curva=None):
    """Lo que dice la celda de una capa de una pieza: su netOD contra el cero de la curva con su u, o el MOTIVO por el que no la tiene: el estado de la medición de la pieza («no medible: …» de CD.2: dos
    piezas, no es película, una resolución de editor...), «recortada por el escáner», «sin cero» o «no medible». Vacío si la pieza todavía no tiene imagen (`pieza` None). CD5-PROD-R1-05: una pieza
    «ok» sin netOD en una curva SIN cero (`curva` es la que dio la pieza) dice `SIN_CERO`, porque el motivo es la curva y no la pieza (sin cero no hay densidad óptica neta de nadie); sin `curva`, o con
    una curva que sí tiene cero, dice `NO_MEDIBLE` como siempre."""
    if pieza is None:
        return ""
    if pieza.estado != "ok":
        return pieza.estado
    datos = pieza.capas[capa]
    if datos.get("recortada") is not None:
        return RECORTADA
    if datos.get("netod") is None:
        return SIN_CERO if curva is not None and curva.cero is None else NO_MEDIBLE
    texto = _cifra(datos["netod"], DECIMALES_NETOD)
    if datos.get("u_netod") is not None:
        texto += f" ± {_cifra(datos['u_netod'], DECIMALES_NETOD)}"
    return texto


def texto_del_archivo(nombre, datos, nominal):
    """La celda «Archivo»: el nombre, con el aviso de DC14 si el escaneo pasa de `MB_DE_AVISO`; sin imagen, «sin imagen» (o «sin imagen (película virgen)» en la fila de 0 cGy)."""
    if not nombre:
        return SIN_IMAGEN_VIRGEN if nominal == 0 else SIN_IMAGEN
    megas = len(datos or b"") / 1e6
    if megas > MB_DE_AVISO:
        return f"{nombre}: el archivo pesa {megas:.1f} [MB], conviene escanear solo el área de la pieza"
    return nombre


def residuo_maximo(curva, capa):
    """El residuo de mayor valor absoluto, con su signo, entre los que el MOTOR dio a las piezas del rango útil de esa capa (en %), o None. Es una elección, no una cuenta."""
    residuos = [p.capas[capa]["residuo_pct"] for p in curva.piezas if p.capas[capa].get("en_el_rango") and p.capas[capa].get("residuo_pct") is not None]
    return max(residuos, key=abs) if residuos else None


def filas_de_la_curva(curva):
    """La tabla de la curva, una fila por capa: el estado, a, b y n, el rango útil, el residuo máximo y el RMS, tal como los dio el motor (`CurvaDeDosis.capas`). Vacío lo que la capa no tiene."""
    filas = []
    for c in CAPAS:
        datos = curva.capas[c]
        p = datos.get("parametros")
        filas.append((NOMBRE_EN_EL_GRAFICO[c], "" if p is None else f"{p['a']:.4g}", "" if p is None else f"{p['b']:.4g}", "" if p is None else f"{p['n']:.4f}",
                      "" if datos.get("rango_cgy") is None else f"de 0 a {datos['rango_cgy']:g}", _cifra(residuo_maximo(curva, c), 2), _cifra(datos.get("rms_pct"), 2), datos["estado"]))
    return filas


def texto_del_cero(curva):
    """De dónde sale el cero de la curva (DC3): el detalle que da el motor, o que no hay cero."""
    if curva is None or curva.cero is None:
        return f"Sin cero: {motor.MOTIVO_SIN_CERO}."
    return f"Cero de la curva: {curva.cero['detalle']}."


def texto_de_la_virgen(referencia, aviso, curva):
    """DC3 (el formulario muestra la película virgen montada y si sirve de cero): una línea con la virgen montada junto a la base y lo que hizo la curva con ella."""
    if aviso:
        return f"Película virgen montada: no se pudo leer ({aviso}); la curva se ajusta sin ella."
    if referencia is None:
        return "Película virgen montada: no hay ninguna junto a la base; el cero sale de las piezas."
    pr = referencia.procedencia or {}
    cabeza = f"Película virgen montada: «{pr.get('archivo') or 'sin nombre'}» ({pr.get('fecha_escaneo') or pr.get('fecha_calculo') or 'sin fecha'})"
    if referencia.estado != "ok":
        return f"{cabeza}: no es válida ({referencia.estado}) y no se usa."
    if curva is None or curva.cero is None:
        return f"{cabeza}: se usará como cero si no hay piezas de 0 cGy y su cadena de captura es la de las piezas."
    if curva.cero["fuente"] == "pelicula_virgen":
        return f"{cabeza}: hace de cero de esta curva."
    no_sirve = [a for a in curva.avisos if a.startswith(motor.AVISO_VIRGEN_NO_SIRVE.split("{")[0])]
    if no_sirve:
        return f"{cabeza}: {no_sirve[0]}."
    if curva.cero["fuente"] == "piezas_de_0_cgy":
        return f"{cabeza}: no hace de cero, porque hay piezas de 0 cGy; se guarda su copia con la calibración."
    return f"{cabeza}: no hace de cero; se guarda su copia con la calibración."


def texto_de_la_carpeta(recalculo):
    """Las líneas del estado de la carpeta de los escaneos de una calibración abierta (CD.4, para CD.5): los que FALTAN y las copias que están pero ya NO COINCIDEN con su huella, cada uno aparte."""
    lineas = []
    if recalculo is None:
        return lineas
    if recalculo.escaneos_que_faltan:
        lineas.append(f"Faltan junto a la base los escaneos de {len(recalculo.escaneos_que_faltan)} piezas (lo medido guardado se recalcula igual; volver a medirlas los necesita): "
                      + ", ".join(recalculo.escaneos_que_faltan) + ".")
    if recalculo.escaneos_que_no_coinciden:
        lineas.append(f"Estas copias de los escaneos ya no coinciden con su huella (no son los escaneos que se midieron): " + ", ".join(recalculo.escaneos_que_no_coinciden) + ".")
    return lineas


def la_calibracion_que_reemplaza(vigentes, encabezado):
    """CD5-PROD-R1-02: la calibración vigente que `guardar` del servicio ANULARÁ al guardar `encabezado`, o None: la de su misma clave de bloque, que el servicio compara tal cual (`lote = ? AND
    DATE(fecha_irradiacion) = DATE(?) AND energia = ?`); si hubiera más de una, la más reciente. `vigentes`: lo que da `services.curva_dosis.listar` (la más reciente primero). Solo ANTICIPA lo que el servicio
    hace, para preguntar antes: una prueba compara las dos (la convergencia de dos caminos no se confía). `encabezado` es el que la ventana arma (lote y energía sin los espacios de los lados)."""
    for fila in vigentes:
        if fila.get("lote") == encabezado["lote"] and fila.get("fecha_irradiacion") == encabezado["fecha_irradiacion"] and fila.get("energia") == encabezado["energia"]:
            return fila
    return None


def texto_de_la_que_reemplaza(anterior):
    """La línea que se agrega a la confirmación de «Guardar» cuando ya hay una calibración vigente con el mismo lote, fecha y energía (CD5-PROD-R1-02)."""
    return f"Ya hay una calibración vigente con este lote, fecha y energía (id {anterior['id']}). Guardar esta la REEMPLAZA: la anterior queda anulada, con su rastro."


def texto_de_una_calibracion(fila):
    """Un renglón de la lista de «Abrir...» (una fila de `services.curva_dosis.listar`)."""
    estados = fila.get("estado") or {}
    capas = "; ".join(f"{NOMBRE_EN_EL_GRAFICO[c]}: {estados.get(c, '')}" for c in CAPAS)
    return (f"{fila['id']}: lote {texto_seguro(fila.get('lote'))}, irradiada el {texto_seguro(fila.get('fecha_irradiacion'))}, {texto_seguro(fila.get('energia'))}, "
            f"guardada por {texto_seguro(fila.get('usuario'))} el {texto_seguro(fila.get('fecha_registro'))} ({capas})")


# ----------------------------------------------------------------------------------------------------- dibujos

def dibujar_vacio(eje_curva, eje_residuos, texto):
    """Sin curva todavía: los dos ejes con sus rótulos y el texto que dice por qué."""
    for eje in (eje_curva, eje_residuos):
        eje.clear()
        eje.grid(True, color=COLOR_REJILLA)
    eje_curva.set_xlabel(ETIQUETA_NETOD)
    eje_curva.set_ylabel(ETIQUETA_DOSIS)
    eje_residuos.set_xlabel(ETIQUETA_DOSIS)
    eje_residuos.set_ylabel(ETIQUETA_RESIDUO)
    eje_curva.text(0.5, 0.5, texto, transform=eje_curva.transAxes, ha="center", va="center", color=TINTA_SUAVE, wrap=True)


def _piezas_de_la_capa(curva, capa):
    return [p for p in curva.piezas if p.capas[capa].get("netod") is not None and p.capas[capa].get("dosis_cgy") is not None]


def dibujar_curva(eje, curva):
    """El gráfico único de la calibración (DA-92): por capa, los pares (netOD, dosis) con su ±u en netOD (rellenos en el rango útil, huecos fuera) y la curva de Devic (`curva.dosis`), que llega hasta la
    netOD de la última pieza de esa capa: entera en el rango útil y punteada después. Con rejilla y leyenda."""
    eje.clear()
    eje.grid(True, color=COLOR_REJILLA)
    eje.set_xlabel(ETIQUETA_NETOD)
    eje.set_ylabel(ETIQUETA_DOSIS)
    hay_fuera = False
    for c in CAPAS:
        color = COLOR_CAPA[c]
        piezas = _piezas_de_la_capa(curva, c)
        rotulo = NOMBRE_EN_EL_GRAFICO[c]                    # cada capa una vez en la leyenda: con el primer grupo que se dibuja (una capa sin rango útil solo tiene piezas huecas)
        for en_el_rango in (True, False):
            grupo = [p for p in piezas if bool(p.capas[c].get("en_el_rango")) == en_el_rango]
            if not grupo:
                continue
            hay_fuera = hay_fuera or not en_el_rango
            eje.errorbar([p.capas[c]["netod"] for p in grupo], [p.capas[c]["dosis_cgy"] for p in grupo], xerr=[p.capas[c]["u_netod"] or 0.0 for p in grupo], fmt="o", color=color,
                         mfc=color if en_el_rango else "none", mec=color, ms=5, capsize=2, label=rotulo, gid=f"piezas_{c}_{'dentro' if en_el_rango else 'fuera'}")
            rotulo = "_nolegend_"
        if curva.capas[c].get("parametros") is None or not piezas:
            continue
        ultima = max(p.capas[c]["netod"] for p in piezas)
        tope = curva.capas[c].get("netod_maxima")
        tope = 0.0 if tope is None else min(float(tope), ultima)
        if tope > 0.0:
            x = np.linspace(0.0, tope, PUNTOS_DE_LA_CURVA)
            eje.plot(x, curva.dosis(c, x), ESTILO_EN_EL_RANGO, color=color, lw=1.5, label=f"{NOMBRE_EN_EL_GRAFICO[c]}: Devic", gid=f"curva_{c}_dentro")
        if ultima > tope:
            hay_fuera = True
            x = np.linspace(tope, ultima, PUNTOS_DE_LA_CURVA)
            eje.plot(x, curva.dosis(c, x), ESTILO_FUERA_DEL_RANGO, color=color, lw=1.2, label="_nolegend_" if tope > 0.0 else f"{NOMBRE_EN_EL_GRAFICO[c]}: Devic", gid=f"curva_{c}_fuera")
    if hay_fuera:
        eje.plot([], [], ESTILO_FUERA_DEL_RANGO, color=TINTA_SUAVE, marker="o", mfc="none", label=TEXTO_FUERA_DEL_RANGO)
    titulo = "Curva de dosis de cada capa: D = a·x + b·xⁿ (Devic)"
    if curva.cero is not None and curva.cero.get("fuente") == "pieza_de_menor_dosis":
        titulo += f"\n{curva.cero['detalle']}: las dosis se cuentan desde ella"
    eje.set_title(titulo, color=TINTA, fontsize=10)
    if eje.get_legend_handles_labels()[0]:
        eje.legend(fontsize=8, loc="upper left")


def dibujar_residuos(eje, curva):
    """Los residuos de las piezas, en %, de las cuatro capas en un mismo gráfico pequeño (DA-92), contra la dosis con que entraron al ajuste; las bandas de la tolerancia del motor (±`residuo_maximo_pct` y,
    por debajo de `dosis_baja_cgy`, ±`residuo_maximo_bajas_pct`). Rellenos en el rango útil, huecos fuera."""
    eje.clear()
    eje.grid(True, color=COLOR_REJILLA)
    eje.set_xlabel(ETIQUETA_DOSIS)
    eje.set_ylabel(ETIQUETA_RESIDUO)
    eje.axhline(0.0, color=TINTA_SUAVE, lw=0.8)
    maxima = 0.0
    for c in CAPAS:
        color = COLOR_CAPA[c]
        piezas = [p for p in curva.piezas if p.capas[c].get("residuo_pct") is not None and p.capas[c].get("dosis_cgy") is not None]
        for en_el_rango in (True, False):
            grupo = [p for p in piezas if bool(p.capas[c].get("en_el_rango")) == en_el_rango]
            if grupo:
                maxima = max(maxima, max(p.capas[c]["dosis_cgy"] for p in grupo))
                eje.plot([p.capas[c]["dosis_cgy"] for p in grupo], [p.capas[c]["residuo_pct"] for p in grupo], "o", color=color, mfc=color if en_el_rango else "none", mec=color, ms=4,
                         gid=f"residuos_{c}_{'dentro' if en_el_rango else 'fuera'}")
    P = curva.parametros
    baja, tolerancia, tolerancia_baja = P["dosis_baja_cgy"], P["residuo_maximo_pct"], P["residuo_maximo_bajas_pct"]
    alto = max(maxima, baja) * 1.05
    eje.hlines([tolerancia, -tolerancia], baja, alto, colors=TINTA_SUAVE, linestyles="--", lw=0.8)
    eje.hlines([tolerancia_baja, -tolerancia_baja], 0.0, baja, colors=TINTA_SUAVE, linestyles="--", lw=0.8)
