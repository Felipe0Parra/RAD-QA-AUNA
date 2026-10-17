"""B.6 (PLAN_ANALISIS_PELICULAS_08-10.md, DP-157, decision de Opus del 16-10 `borradores/B6/decision_figura_pdf_Opus.md`): los DIBUJOS de la posicion inicial de la fuente de braquiterapia que la
pagina y los dos PDF comparten. Antes vivian en la pagina (`ui/paginasControles/PruebasMensuales/posicion_inicial_braqui.py`, B.1 y B.4); como el PDF diario y el mensual imprimen el perfil de la
capa reportada, que es la misma figura que dibuja la pestana de esa capa, la definicion de que muestra un perfil se MUDO aqui con su cuerpo sin cambiar (una operacion, una definicion: una segunda
copia del dibujo para el PDF habria que mantenerla dos veces) y la pagina las importa de vuelta con el MISMO nombre (`pagina_mod.X` sigue siendo el mismo objeto).

Es DIBUJO y texto sobre un eje que recibe quien llama: ni Qt ni matplotlib (se prueban sobre una `Figure` sin lienzo, y el PDF las compone con su propia disposicion). Del motor solo usa
`motivos_de_las_filas` y los dos `MOTIVO_*` de las filas puenteadas: dibuja el resultado del motor, no lo corre (un tripwire de PI.10 lo fija por AST). Ningun numero cambia: lo que cada
funcion dibuja es lo que dibujaba en la pagina, linea por linea."""
import textwrap

import numpy as np

from analisisImagenes import posicion_inicial_braqui as motor

# ----------------------------------------------------------------------------------------------------- constantes (mudadas de la pagina)

# La línea que el motor dice cuando la refinó por su perfil: lo único que deja guardar. Una prueba la ata al motor real.
LINEA_REFINADA = "linea refinada por su perfil"
COLOR_MEDIDO = "#2a78d6"
COLOR_REFERENCIA = "#eb6834"
TINTA = "#0b0b0b"
TINTA_SUAVE = "#898781"
COLOR_CAPA = {"R": "#e34948", "G": "#008300", "B": "#2a78d6"}
COLOR_LINEA_DESCARTADA = "#00a6b8"
COLOR_REJILLA = "#e1e0d9"
NOMBRE_DE_PERFIL = {"gris": "Perfil de grises", "R": "Capa roja", "G": "Capa verde", "B": "Capa azul"}
NIVEL_DE_PERFIL = {"gris": "gris", "R": "rojo", "G": "verde", "B": "azul"}
COLOR_TRANSITO = "#9a3fb0"
# B.1 (PD1, nada escondido que cambie el número): qué trazo o qué rótulo muestra CADA parámetro de `motor.PARAMETROS` que entra en la medida. `{clave: (dónde, texto)}`. Una prueba
# deriva por AST qué claves leen `analizar`, `medir_perfil`, `resumen` y todo lo que llaman, exige que cada una tenga su entrada (un parámetro nuevo sin trazo hace caer la prueba y lo nombra) y
# comprueba que cada entrada está de verdad en la figura de la página. Dónde:
#   "perfil"   un trazo de cada perfil (el gris y las tres capas) cuya etiqueta empieza por `texto`;
#   "ventana"  un trazo de la ventana rotada cuya etiqueta empieza por `texto`;
#   "eje"      el eje secundario de arriba de cada perfil, en mm desde la línea (su rótulo empieza por `texto`; la ventana de ±`ventana_mm` es su extensión);
#   "recuadro" una frase del recuadro de resultado (`texto` + el valor + mm);
#   "pagina"   la etiqueta de la página con ese nombre, que DICE el valor con que se midió (la resolución del escaneo); no basta con que tenga algún texto (R1-E);
#   "pie"      una frase del pie de cada figura (los parámetros fijos que no tienen una geometría que dibujar); `texto` es su plantilla y se llena con el valor con que se midió
#              (una lista, como las resoluciones de editor, se dice con comas).
TRAZO_DE_PARAMETRO = {
    "delta": ("perfil", "tope"),
    "ventana_mm": ("eje", "distancia a la línea de referencia"),
    "refinar_linea": ("ventana", "línea de referencia"),
    "contraste_transito": ("ventana", "banda de tránsito"),
    "transito_desde_mm": ("ventana", "banda de tránsito"),
    "transito_hasta_mm": ("ventana", "banda de tránsito"),
    "umbral_pelicula": ("ventana", "banda de tránsito"),
    "tolerancia_mm": ("recuadro", "Tolerancia"),
    "resolucion_escaneo_dpi": ("pagina", "etiqueta_escaneo"),
    "resoluciones_de_editor_dpi": ("pie", "dpi de editor ({}): se usa la resolución del escaneo"),
    "tolerancia_dpi_relativa": ("pie", "tolerancia del dpi declarado ±{:.0%}"),
    "grosor_marco": ("pie", "marco del escaneo {} px"),
    "ancho_linea": ("pie", "franja de la línea ±{} px"),
    "hueco_max": ("pie", "huecos de hasta {} px se puentean"),
    "filtro": ("pie", "filtro de mediana {0} × {0}"),
    "fraccion_central": ("pie", "cuerdas útiles con al menos el {:.0%} del ancho máximo"),
    "fraccion_minima": ("pie", "o el {:.0%} si faltan"),
    "minimo_filas": ("pie", "mínimo {} cuerdas"),
    "delta_cruces": ("pie", "comprobación independiente de los bordes a tope − {:g}"),
    "caida_borde": ("pie", "borde de la película si cae más de {} niveles junto a la meseta"),
    "fraccion_filas_cortadas": ("pie", "mancha cortada si lo están más del {:.0%} de las cuerdas"),
    "margen_filas_mm": ("pie", "margen de {:g} mm sobre y bajo los puntos"),
}
LARGO_DEL_PIE = 200                    # caracteres por línea del pie de parámetros fijos
COLOR_FILA_QUE_NO_ENTRA = "#c4c2ba"    # B.4: las filas con meseta que el barrido no usa (gris claro)
ANCHO_DE_LA_LEYENDA = 64               # caracteres por línea de las etiquetas de la leyenda de la ventana (la banda lleva una etiqueta larga)


# ------------------------------------------------------------------------------------------------- textos y dibujos (mudados de la pagina)


def _numero(valor, decimales):
    """El número con sus decimales y nunca '-0.00' (un desfase que redondea a cero no tiene signo)."""
    texto = f"{valor:.{decimales}f}"
    return texto[1:] if texto.startswith("-") and float(texto) == 0 else texto


def motivo_para_no_guardar(resultado):
    """None si el resultado se puede guardar; si no, el texto de por qué no (P10, DP-145): el motor descarta la línea que
    encontró cuando queda a 5 px o más de los clics, mide contra los clics y da un veredicto sin ningún aviso. Es también
    la primera línea del recuadro: una sola definición del mensaje."""
    mensaje = resultado["mensaje_linea"]
    if mensaje == LINEA_REFINADA:
        return None
    return (f"No se encontró la línea marcada cerca de los dos puntos ({mensaje}): el resultado se midió contra los "
            "puntos, no contra la línea. Vuelva a marcarlos con la lupa (Recalcular)")


def fila_representativa(resultado, perfil="gris"):
    """La cuerda que se dibuja: la central de las cuerdas útiles (`filas[len(filas) // 2]`; no `argmax(ancho)`, que da
    empates porque los anchos son enteros). Sin cuerdas útiles, la fila media de los dos clics en la ventana. R, G y B se
    dibujan sobre la fila que da el gris, como el notebook."""
    filas = resultado["perfiles"][perfil]["filas"]
    if len(filas):
        return int(filas[len(filas) // 2])
    alto = resultado["imagenes"]["gris"].shape[0]
    return int(min(max(round(float(np.mean(resultado["clics_ventana"][:, 1]))), 0), alto - 1))


def _poligono(ax, x0, x1, y0, y1, **estilo):
    """Un rectángulo en las coordenadas de datos de la imagen (la columna c ocupa [c - 0.5, c + 0.5]). Es un polígono y no cuatro líneas: así no suma líneas de más de dos puntos."""
    return ax.fill([x0, x1, x1, x0], [y0, y0, y1, y1], **estilo)[0]


def _dibujar_bandas(ax, resultado):
    """B.1: las bandas donde se decide el lado del tránsito, con los LÍMITES que devuelve el motor (la página no repite la regla): la banda (las filas de la mancha, solo las columnas de la
    ventana que caen dentro: la banda va de ~12 a 50 mm del centro y la ventana solo ve ±`ventana_mm`) y, con trazo discontinuo, las dos zonas de película con que se compara (arriba y abajo
    de la mancha). Cada banda se rotula con su extensión completa, su contraste y el mínimo que se exige; el lado sin banda medible se rotula «no medible» y no se dibuja (el motor no devolvió
    ninguna geometría para él)."""
    detalles = resultado.get("contrastes_transito") or {}
    P = resultado["parametros"]
    ancho = resultado["imagenes"]["gris"].shape[1]
    sin_etiquetar = True
    for lado in ("izquierda", "derecha"):
        if lado not in detalles:
            continue
        d = detalles[lado]
        if d is None:
            ax.plot([], [], ls=":", color=COLOR_TRANSITO, label=f"banda de tránsito a la {lado}: no medible (no hay película suficiente donde se mide)")
            continue
        if d["desde_mm"] is not None:
            extension = f"de {d['desde_mm']:.1f} a {d['hasta_mm']:.1f} mm del centro"
        else:           # sin escala (resolución 'otra') no hay milímetros que dar: como el recuadro, la banda se rotula en píxeles desde el centro de la mancha
            extension = f"de {d['desde_px']} a {d['hasta_px']} px del centro (sin escala: sin milímetros)"
        etiqueta = (f"banda de tránsito a la {lado}: {extension}; contraste {d['contraste']:.1f} niveles "
                    f"(mínimo {P['contraste_transito']:g}); solo película (nivel > {P['umbral_pelicula']:g})")
        x0, x1 = max(d["columnas"][0], 0) - 0.5, min(d["columnas"][1], ancho) - 0.5
        if x1 <= x0:
            ax.plot([], [], ls="-", color=COLOR_TRANSITO, label=etiqueta + " (fuera de la ventana)")
            continue
        f0, f1 = d["filas_banda"]
        _poligono(ax, x0, x1, f0 - 0.5, f1 - 0.5, facecolor=COLOR_TRANSITO, alpha=0.30, edgecolor=COLOR_TRANSITO, lw=1.0, label=etiqueta)
        for clave in ("filas_arriba", "filas_abajo"):
            if d[clave] is not None:
                g0, g1 = d[clave]
                _poligono(ax, x0, x1, g0 - 0.5, g1 - 0.5, fill=False, edgecolor=COLOR_TRANSITO, ls="--", lw=0.9,
                          label="película de comparación (arriba y abajo de la mancha)" if sin_etiquetar else "_película de comparación")
                sin_etiquetar = False


def dibujar_ventana(ax, resultado, perfil, fila, leyenda=False):
    """La ventana rotada alrededor de la línea: la línea de referencia (naranja discontinua), los bordes de la meseta por
    cuerda y el centro de cada cuerda (azul, solo si el perfil se mide) y, desde B.1, las bandas del tránsito. `leyenda`
    (por omisión False: la conducta de siempre) dice qué es cada trazo, fuera del dibujo y a su derecha."""
    r = resultado["perfiles"][perfil]
    m = r["m"]
    ax.imshow(m["suave"], cmap="gray", vmin=m["tope"] - 60, vmax=m["tope"], interpolation="nearest")
    ax.plot(resultado["x_ref"], np.arange(len(resultado["x_ref"])), "--", color=COLOR_REFERENCIA, lw=1.5,
            label="línea de referencia")
    linea = resultado.get("linea")
    if linea is not None and resultado["mensaje_linea"] != LINEA_REFINADA:
        # La línea que el motor encontró y NO usó: sin verla, el físico no sabe por qué se le pide marcar de nuevo.
        todas = np.arange(len(resultado["x_ref"]))
        ax.plot(linea["pendiente"] * todas + linea["corte"], todas, "--", color=COLOR_LINEA_DESCARTADA, lw=1.2,
                label="línea que se encontró (no se usa)")
    if r["estado"] == "ok":
        filas = r["filas"]
        ax.plot(m["x_izq"][filas], filas, "o", ms=2, mfc="white", mec=TINTA, mew=0.3, label="bordes de la meseta")
        ax.plot(m["x_der"][filas], filas, "o", ms=2, mfc="white", mec=TINTA, mew=0.3)
        ax.plot(r["centros"], filas, "-", color=COLOR_MEDIDO, lw=1.5, label="centro de cada cuerda")
    _dibujar_bandas(ax, resultado)
    ax.axhline(fila, color=TINTA_SUAVE, ls=":", lw=1)
    ax.set_xlabel("columna de la ventana [px]")
    ax.set_ylabel("fila de la ventana [px]")
    if leyenda:
        manejadores, etiquetas = ax.get_legend_handles_labels()
        caja = ax.legend(manejadores, [textwrap.fill(e, ANCHO_DE_LA_LEYENDA) for e in etiquetas], loc="upper left", bbox_to_anchor=(1.02, 1.0),
                         fontsize=7, borderaxespad=0.0)
        caja.set_in_layout(False)      # la leyenda va en el hueco de al lado; si la ventana es baja se recorta, pero no hace colapsar los ejes (constrained_layout)


def dibujar_perfil(ax, resultado, perfil, fila, color=TINTA, leyenda=False, columnas_de_la_leyenda=3, eje_en_mm=True, rotulo_en_px=True):
    """El perfil de una cuerda, COMPLETO (B.1): el eje x cubre la ventana entera (±`ventana_mm` alrededor de la línea) y el y va de 0 al tope + 5 %. Dibuja el crudo y el filtrado, el TOPE
    (con la regla del umbral, con el delta con que se midió), el umbral de la meseta, la meseta sombreada entre sus bordes subpíxel con los dos bordes marcados donde cruzan el umbral, la línea
    de referencia y el centro de la meseta de ESA cuerda (azul; no se dibuja en un perfil que no se mide). Arriba, un eje secundario en mm desde la línea (0 = línea) con la escala del resultado
    (sin escala, sin eje). Los dos centros que se comparan son la línea y la meseta: los cruces solo entran en la incertidumbre. `leyenda` (por omisión False: la conducta de siempre) dibuja la
    leyenda dentro, abajo, en `columnas_de_la_leyenda` columnas (la zona de abajo está vacía: el perfil vive cerca del tope). `eje_en_mm` y `rotulo_en_px` (por omisión True: el perfil completo) dejan a la
    página quitar, en una pila de perfiles que comparten el eje x, lo que se repetiría en cada uno."""
    r = resultado["perfiles"][perfil]
    m = r["m"]
    ancho = m["suave"].shape[1]
    x = np.arange(ancho)
    crudo, filtrado = resultado["imagenes"][perfil][fila], m["suave"][fila]
    ax.plot(x, crudo, color=TINTA_SUAVE, lw=0.7, label="perfil crudo")
    ax.plot(x, filtrado, color=color, lw=1.2, label="perfil con filtro de mediana")
    ax.axhline(m["tope"], color=TINTA, ls=":", lw=1, label=f"tope (umbral = tope − {resultado['parametros']['delta']:g} niveles)")
    ax.axhline(m["umbral"], color=TINTA_SUAVE, ls="--", lw=1, label="umbral de la meseta")
    if m["inicio"][fila] >= 0:
        ax.axvspan(m["x_izq"][fila], m["x_der"][fila], color=COLOR_MEDIDO, alpha=0.15, label="meseta")
        ax.plot([m["x_izq"][fila], m["x_der"][fila]], [m["umbral"]] * 2, ls="none", marker="|", ms=14, mew=1.6, color=COLOR_MEDIDO,
                label="bordes de la meseta (subpíxel)")
    if r["estado"] == "ok":
        ax.axvline((m["x_izq"][fila] + m["x_der"][fila]) / 2, color=COLOR_MEDIDO, lw=1.5, label="centro de la meseta")
    ax.axvline(resultado["x_ref"][fila], color=COLOR_REFERENCIA, ls="--", lw=1.5, label="línea de referencia")
    ax.set_xlim(-0.5, ancho - 0.5)
    ax.set_ylim(min(0.0, float(crudo.min()), float(filtrado.min())), max(m["tope"] * 1.05, 1.0))   # el 1.0: una ventana sin nada de pelicula (tope 0) no da limites identicos
    if rotulo_en_px:
        ax.set_xlabel("columna de la ventana [px]")
    ax.set_ylabel(f"{NIVEL_DE_PERFIL[perfil]} invertido")
    tam = resultado["tamano_pixel_mm"]
    if tam is not None and eje_en_mm:
        x_linea = float(resultado["x_ref"][fila])
        arriba = ax.secondary_xaxis("top", functions=(lambda v: (v - x_linea) * tam, lambda mm: mm / tam + x_linea))
        arriba.set_xlabel("distancia a la línea de referencia [mm]")
    nombre = NOMBRE_DE_PERFIL[perfil]
    if motivo_para_no_guardar(resultado):
        ax.set_title(f"{nombre}: medido contra los puntos, no contra la línea", fontsize=8)
    elif r["estado"] == "ok" and m["inicio"][fila] >= 0:
        en_cuerda = resultado["x_ref"][fila] - (m["x_izq"][fila] + m["x_der"][fila]) / 2
        ax.set_title(f"{nombre}: en esta cuerda {_numero(en_cuerda, 2)} px; mediana de {len(r['filas'])} cuerdas "
                     f"{_numero(r['desfase_px'], 2)} px", fontsize=8)
    else:
        ax.set_title(f"{nombre}: no medible", fontsize=8)
    if leyenda:
        ax.legend(loc="lower center", fontsize=7, ncol=columnas_de_la_leyenda)


def texto_de_parametros(resultado):
    """El pie de cada figura (B.1, PD1): los parámetros fijos de la medida que no tienen una geometría que dibujar (las entradas "pie" de `TRAZO_DE_PARAMETRO`), con el valor con que se midió
    (`resultado["parametros"]`, que se guarda con el análisis; una lista, como las resoluciones de editor, se dice con comas), en líneas de `LARGO_DEL_PIE` caracteres sin partir una frase."""
    P = resultado["parametros"]
    titulo = "Parámetros fijos del método (se guardan con cada análisis; no se ajustan en pantalla):"
    lineas, linea = [], titulo
    for clave, (donde, plantilla) in TRAZO_DE_PARAMETRO.items():
        if donde != "pie":
            continue
        valor = P[clave]
        if isinstance(valor, (list, tuple)):               # las resoluciones de editor: «72, 96»
            valor = ", ".join(f"{v:g}" for v in valor)
        frase = plantilla.format(valor)
        union = " " if linea == titulo else " · "
        if linea != titulo and len(linea) + len(union) + len(frase) > LARGO_DEL_PIE:
            lineas.append(linea)
            linea = frase
        else:
            linea += union + frase
    lineas.append(linea)
    return "\n".join(lineas)


def rotular_parametros(figura, resultado):
    """Escribe el pie de parámetros fijos al pie de la figura (para la distribución `constrained`, que le deja su sitio)."""
    figura.supxlabel(texto_de_parametros(resultado), fontsize=7, color=TINTA_SUAVE, wrap=True)


def datos_del_barrido(resultado, perfil, fila_de_referencia=None):
    """B.4: lo que dibuja la grafica «Barrido» de un perfil, SIN dibujar: el desfase de cada fila con meseta (usada o no) contra su posicion respecto de la fila de la cuerda mas ancha. Todo sale de
    `motor.motivos_de_las_filas` (la regla es del motor: la pagina no la copia) y la mediana es la que se reporta (`desfase_px` del perfil). En milimetros si el resultado tiene escala; sin escala
    (resolucion «otra») los milimetros no existen y todo va en pixeles. `media` es la de las filas usadas (la que NO se reporta). La referencia de la posicion es la fila de la cuerda mas ancha DEL PERFIL
    (`np.argmax(ancho)`, la misma con que el motor elige su bloque central); `fila_de_referencia` (por omision None: la del perfil) deja que las cuatro capas juntas usen UNA sola, la del gris, para que las
    filas de una capa y otra sean las mismas filas de la pelicula."""
    r = resultado["perfiles"][perfil]
    d = motor.motivos_de_las_filas(r["m"], resultado["parametros"], resultado["x_ref"])
    tam = resultado["tamano_pixel_mm"]
    escala = tam if tam is not None else 1.0
    referencia = d["fila_de_referencia"] if fila_de_referencia is None else int(fila_de_referencia)
    filas = np.where(d["con_meseta"])[0]
    usada = d["usada"][filas]
    desfase = d["desfase"][filas] * escala
    datos = {"unidad": "mm" if tam is not None else "px", "estado": r["estado"], "filas": filas, "posicion": (filas - referencia) * escala, "desfase": desfase,
             "usada": usada, "motivos": [d["motivos"][y] for y in filas], "fila_de_referencia": referencia, "repliegue": d["repliegue"]}
    if r["estado"] == "ok":
        datos["mediana"] = float(r["desfase_px"]) * escala
        datos["media"] = float(np.mean(desfase[usada]))
    return datos


def _cuantas(n, uno, varias):
    return f"{n} {uno if n == 1 else varias}"


def texto_de_la_regla(resultado, perfil="gris"):
    """B.4: la frase que dice cuando la regla del barrido se RELAJO en un perfil; vacia si no se relajo. Tres casos, ninguno con simbolos de correcto o incorrecto: quedaban menos de `minimo_filas` filas y
    la fraccion bajo (se cuentan las filas usadas con menos de la fraccion central); quedaban menos de `minimo_filas` y el repliegue sumo SOLO filas de otro bloque con cuerdas de la fraccion central o mas
    (R1-05, B4-D7: el conjunto candidato paso del bloque central a toda la imagen; se cuentan las filas usadas de fuera del bloque central; sale solo si la frase de arriba no sale: esa ya dice que la
    regla se relajo); y filas que entraron por un hueco puenteado (con cualquier cuerda). Los numeros salen de los motivos y de las filas del motor y de los parametros con que se midio."""
    r = resultado["perfiles"][perfil]
    P = resultado["parametros"]
    d = motor.motivos_de_las_filas(r["m"], P)
    motivos = d["motivos"]
    frases = []
    por_repliegue = motivos.count(motor.MOTIVO_USADA_POR_REPLIEGUE)
    por_hueco = motivos.count(motor.MOTIVO_USADA_POR_HUECO)
    de_otro_bloque = int(np.sum(d["usada"] & ~d["en_bloque"]))
    if por_repliegue:
        frases.append(f"se {'usó' if por_repliegue == 1 else 'usaron'} {_cuantas(por_repliegue, 'fila', 'filas')} con menos del {round(100 * P['fraccion_central'])} % "
                      f"porque quedaban menos de {P['minimo_filas']}")
    elif d["repliegue"] and de_otro_bloque:
        frases.append(f"el barrido tomó {_cuantas(de_otro_bloque, 'fila', 'filas')} de fuera del bloque central porque en él quedaban menos de {P['minimo_filas']}")
    if por_hueco:
        frases.append(f"{_cuantas(por_hueco, 'fila entró', 'filas entraron')} por un hueco puenteado")
    return "; ".join(frases)


def dibujar_barrido_de_filas(ax, resultado, perfiles=("gris",)):
    """B.4: la grafica «Barrido». Con UN perfil: el desfase de cada fila usada contra su posicion respecto de la fila de la cuerda mas ancha, la MEDIANA (la que se reporta, punteada), la media
    (discontinua) y, en gris claro, las filas con meseta que no entran. Con VARIOS perfiles (las cuatro capas juntas): solo las filas usadas de cada uno y su mediana, cada uno con su color. La frase
    de `texto_de_la_regla` va en el titulo cuando la regla se relajo. La leyenda va FUERA de los ejes, a su derecha (R1-08: dentro, los datos llenan el eje y tapaba filas usadas): con un perfil
    dice lo que dibuja; con varios, una entrada por capa dibujada (su color dice cual es) y una para la mediana punteada. Funcion pura sobre un eje: la regla es del motor, aqui solo se dibuja."""
    unidad = "mm" if resultado["tamano_pixel_mm"] is not None else "px"
    solo = len(perfiles) == 1
    referencia = None
    if not solo:                                   # las cuatro capas juntas comparten UNA referencia (la del gris): una misma fila de la pelicula cae en la misma posicion en todas
        referencia = motor.motivos_de_las_filas(resultado["perfiles"][perfiles[0]]["m"], resultado["parametros"])["fila_de_referencia"]
        referencia = None if referencia < 0 else referencia
    frases = []
    en_la_leyenda = []                             # las capas dibujadas: (la linea de sus filas usadas, su nombre), para la leyenda de las cuatro capas
    for perfil in perfiles:
        d = datos_del_barrido(resultado, perfil, referencia)
        color = TINTA if perfil == "gris" else COLOR_CAPA[perfil]
        nombre = NOMBRE_DE_PERFIL[perfil]
        if d["estado"] != "ok":
            if solo:
                ax.plot(d["posicion"], d["desfase"], "o", ms=3, color=COLOR_FILA_QUE_NO_ENTRA, label="filas con meseta (no se mide)")
            else:
                frases.append(f"{nombre}: no medible, no se dibuja")
            continue
        if solo and (~d["usada"]).any():
            ax.plot(d["posicion"][~d["usada"]], d["desfase"][~d["usada"]], "o", ms=3, color=COLOR_FILA_QUE_NO_ENTRA, label="filas con meseta que no entran")
        usadas, = ax.plot(d["posicion"][d["usada"]], d["desfase"][d["usada"]], "o-" if not solo else "o", ms=3, lw=0.8, color=color, label=f"{nombre}: filas usadas" if not solo else "filas usadas")
        en_la_leyenda.append((usadas, nombre))
        ax.axhline(d["mediana"], ls=":", lw=1.5, color=color, label=f"{nombre}: mediana (la que se reporta)" if not solo else "mediana (la que se reporta)")
        if solo:
            ax.axhline(d["media"], ls="--", lw=1.2, color=COLOR_REFERENCIA, label="media")
        frase = texto_de_la_regla(resultado, perfil)
        if frase:
            frases.append(frase if solo else f"{nombre}: {frase}")
    ax.set_xlabel(f"posición de la fila respecto de la cuerda más ancha{'' if solo else ' del gris'} [{unidad}]")
    ax.set_ylabel(f"desfase [{unidad}]")
    titulo = "Barrido: el desfase de cada fila" if solo else "Barrido de las cuatro capas"
    ax.set_title("\n".join([titulo] + [textwrap.fill(f, 110) for f in frases]), fontsize=8)
    ax.grid(color=COLOR_REJILLA)
    if solo:
        manejadores, etiquetas = ax.get_legend_handles_labels()
    else:                                          # una entrada por capa dibujada (su color dice cual es) y una para la linea punteada: la leyenda completa (ocho entradas) llenaba medio eje
        # la entrada de la mediana es una linea punteada sin datos, de la clase de las que ya hay en el eje (la pagina no importa matplotlib: tripwire 26e de PI.4, solo la carga diferida)
        manejadores = [linea for linea, _ in en_la_leyenda] + ([type(en_la_leyenda[0][0])([], [], color=TINTA, ls=":", lw=1.5)] if en_la_leyenda else [])
        etiquetas = [nombre for _, nombre in en_la_leyenda] + (["mediana (la que se reporta)"] if en_la_leyenda else [])
    if manejadores:
        # R1-08: FUERA de los ejes, a su derecha (la disposicion le deja el sitio y no le quita alto a ningun eje): los datos llenan el eje y ningun rincon de adentro esta libre (16 de 215 puntos usados
        # tapados en braqui_00 y 28 de 161 en EPSON009 con la leyenda arriba a la izquierda).
        ax.legend(manejadores, etiquetas, fontsize=6, loc="upper left", bbox_to_anchor=(1.01, 1.0), borderaxespad=0.0, framealpha=0.75)
