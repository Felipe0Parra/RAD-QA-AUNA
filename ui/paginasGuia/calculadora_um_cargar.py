"""UM.5 (PLAN_CALCULADORA_UM_05-11.md, DC13): el botón «Cargar tablas» de la pestaña «Calculadora UM» y el historial de las tablas guardadas.

Sin SQL y sin física: lo que entendió una carga lo dice el servicio de UM.3 (`um_datos_haz.revisar`, la MISMA comprobación que repite `guardar`, UM3-D2), y aquí solo se lee lo escrito con la
regla de la pestaña (`calculadora_um.leer_numero`, UM4-D4), se ordena lo que se ve y se llama al servicio con ARGUMENTOS CON NOMBRE. Dos capas, como la pestaña (UM4-D2):

  - La CAPA PURA (sin Qt, arriba): quién es la sesión y si puede cargar (`login_de_la_sesion`, `puede_cargar`: solo para pintar el botón; el permiso lo decide el servicio, DA-81), leer los
    archivos elegidos (`leer_archivos`), lo que cada uno dice de sí mismo (`lo_que_dice`), los nombres cortos con que se ven (`nombres_para_mostrar`, `legible`), de lo escrito a los argumentos
    del servicio o a un motivo (`carga_desde_textos`), y del resumen del servicio a lo que se ve (`estado_de_cada_archivo`, de la que salen `filas_de_los_archivos` y `texto_del_conteo`,
    `texto_de_lo_vigente`, `texto_del_rechazo`, `texto_de_lo_guardado`, `filas_del_historial`, `filas_de_los_archivos_guardados`). Se prueba sin crear ningún widget.
  - La CAPA DE WIDGETS (abajo): `DialogoCargarTablas` y `DialogoHistorial`, que solo arman la ventana y llaman a la capa pura y al servicio.

Nada se guarda sin pasar por el resumen: «Guardar estas tablas» solo se habilita tras una revisión SIN problemas, y guarda EXACTAMENTE lo revisado (los mismos argumentos); cualquier cambio en lo
escrito o en los archivos lo vuelve a apagar hasta revisar otra vez (como UM4-D6: nunca se ve un resumen que no corresponde a lo escrito). Sin hilo (H14): revisar los 22 archivos reales tarda
décimas de segundo; mientras tanto se ve el cursor de espera (DA-71). Lo que no se puede leer no se esconde: un archivo que no se abre o que no se entiende impide guardar y se ve con su
motivo, y los demás siguen en el resumen."""
import os
import re

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog, QFileDialog, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QPushButton, QSizePolicy, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from services import um_datos_haz, um_motor
from services import um_lector_eclipse as lector
from services.permisos import es_fisico_jefe
from ui.paginasGuia.calculadora_um import EQUIPOS, Campo, leer_numero, que_no_fije_el_ancho, sin_palabras_enormes, texto_sin_perder

# ================================================================================================================================== capa pura (sin Qt)

TITULO_DE_LA_CARGA = "Cargar las tablas de una energía"
TITULO_DEL_HISTORIAL = "Historial de las tablas guardadas"
TAMANO_DE_LA_CARGA = (1280, 700)         # cabe en una pantalla de 1366 x 768 con la barra de tareas
TAMANO_DEL_HISTORIAL = (1100, 560)
ALTO_DE_UNA_FILA = 24                     # [px], como el desglose de la pestaña
ANCHOS_DE_LOS_ARCHIVOS = (380, 520)
ANCHOS_DEL_HISTORIAL = (150, 140, 115, 330, 90, 280)
ANCHOS_DE_LOS_GUARDADOS = (150, 200, 360, 120, 160)
ANCHO_DEL_CONTEO = 320                    # [px], R1-S8b: cabe «22 archivos: 12 se usan y 10 se ignoran.» en una línea; un conteo más largo se parte en líneas dentro de su celda en lugar de ensanchar el diálogo
FILTRO_DE_ARCHIVOS = "Archivos de Eclipse (*.txt *.data *.asc);;Todos los archivos (*)"
TAMANO_MAXIMO_BYTES = 20 * 1024 * 1024      # UM5-D7: el mayor archivo real mide 188 [kB]; uno de más de 20 [MB] no es una exportación de Eclipse y no se lee (no se congela la pantalla)
D0_EN_DMAX, D0_EN_LA_TABLA = "en dmax", "en las condiciones de la tabla"
ORIGEN_INICIAL = "Eclipse: 1 cGy/UM en dmax"         # DC2 y DA-95: el valor de Eclipse, escrito con su origen
CAMPO_D0 = Campo("d0", "D'0 [cGy/UM]", "D'0 [cGy/UM]", True, inicial="1.000",
                 explicacion="La tasa de referencia de Eclipse: 1 [cGy/UM] en dmax. Si la tabla de factores no está a la SSD de los PDD, se escribe en las condiciones de la tabla.")
AYUDA_DE_CARGAR = "Elija los archivos que exporta Eclipse para una energía: antes de guardar se ve qué entendió la app, y nada se guarda sin pulsar «Guardar estas tablas»."
AYUDA_SIN_PERMISO = ("Las tablas las cargan el físico jefe o el administrador. Con esta cuenta se pueden ver las tablas cargadas y su historial, pero no cargarlas.")
AYUDA_DEL_HISTORIAL = "Las cargas del equipo y la energía elegidos: la vigente y las que reemplazó, con quién y cuándo las cargó."
SIN_ARCHIVOS = "Pulse «Elegir archivos» y elija todos los que exporta Eclipse para una energía (los que el cálculo no lee se ignoran)."
LO_ESCRITO_CAMBIO = "Lo escrito o los archivos cambiaron desde la última revisión: pulse «Revisar» para ver el resumen de nuevo antes de guardar."
SE_PUEDE_GUARDAR = "Nada impide guardar. Revise el resumen y, si es lo que quiere, pulse «Guardar estas tablas»."
NADA_IMPIDE = "Nada impide guardar."
SIN_REVISAR = "Sin revisar: corrija lo escrito"
# UM5-S8: qué es cada archivo elegido para la carga, y cómo lo dice la tabla. De esta única clasificación salen las filas y el conteo (cada archivo se cuenta una vez y los números suman el total).
USA, IGNORA, IMPIDE, SIN_CLASIFICAR = range(4)           # cuatro etiquetas: solo importa que sean distintas
ESTADO_EN_LA_TABLA = {USA: "Se usa", IGNORA: "Se ignora: el cálculo no lo lee", IMPIDE: "Impide guardar: vea el motivo", SIN_CLASIFICAR: "Sin revisar: lo impide otro problema"}
FILAS_Y_COLUMNAS = ("Filas y columnas: en las tablas de factores de Eclipse las filas son Y y las columnas X. En cada cuña el lado corto de su tabla es el del gradiente y, si está su "
                    "name.data, su orientación debe decir lo mismo; si no lo dice, no se puede guardar.")
COLUMNAS_DE_LOS_ARCHIVOS = ("Archivo", "Lo que dice ser", "En la carga")
COLUMNAS_DEL_HISTORIAL = ("Cargadas el", "Por", "Estado", "D'0", "Archivos", "Reemplazó a", "Observaciones")
COLUMNAS_DE_LOS_GUARDADOS = ("Accesorio", "Dato", "Archivo", "Huella", "Tamaño [bytes]", "Estado")
# Lo que dice cada tipo de dato de Eclipse, para el físico (el código es el de la cabecera, «# data:»).
QUE_ES = {"OPD": "PDD medido", "OPD_calculated": "PDD calculado por Eclipse", "OPP_processed": "perfiles medidos y procesados", "OPP_calculated": "perfiles calculados por Eclipse",
          "OutputFactorTable": "tabla de factores", "WDD": "PDD medido con cuña", "WDP": "perfiles medidos con cuña", "WedgeTransmission": "transmisión de la cuña",
          "WedgeParameters": "parámetros de la cuña (name.data)"}


def login_de_la_sesion(usuario):
    """El login de la sesión: el `_usuario` del objeto de la sesión (como lo leen Referencias y Usuarios), o el texto mismo si la sesión es un texto (la ventana de prueba de `mainpages.py`);
    None si no hay ninguno. Es el que llega al servicio, que con él decide el permiso y escribe el nombre de quien carga."""
    login = getattr(usuario, "_usuario", usuario)
    return login.strip() if isinstance(login, str) and login.strip() else None


def puede_cargar(login):
    """Solo para PINTAR el botón (DA-81): el servicio lo vuelve a comprobar al guardar con la misma regla, `es_fisico_jefe` (hoy el jefe y el administrador; el rol «físico» no, PC-12)."""
    return bool(login) and es_fisico_jefe(login)


def leer_archivos(rutas, abrir=open):
    """([(ruta, bytes)], [(ruta, motivo)]): los archivos elegidos, tal como están en el disco, y los que no se pudieron leer (que impiden guardar y se ven con su motivo). Uno de más de
    `TAMANO_MAXIMO_BYTES` no se lee."""
    leidos, no_leidos = [], []
    for ruta in rutas:
        try:
            if os.path.getsize(ruta) > TAMANO_MAXIMO_BYTES:
                no_leidos.append((ruta, f"mide más de {TAMANO_MAXIMO_BYTES // (1024 * 1024)} [MB]: no es un archivo de los que exporta Eclipse y no se lee"))
                continue
            with abrir(ruta, "rb") as archivo:
                leidos.append((ruta, archivo.read()))
        except OSError as fallo:
            no_leidos.append((ruta, f"no se pudo leer ({fallo.strerror or type(fallo).__name__})"))
    return leidos, no_leidos


def lo_que_dice(contenido):
    """(Identidad o None, texto): lo que el archivo dice de sí mismo en su cabecera («máquina 600C, haz 6X; Open Field - 00: PDD medido»), o por qué no se entiende."""
    try:
        i = lector.identidad(lector.decodificar(contenido))
    except lector.ArchivoNoReconocido as fallo:
        return None, f"No se entiende su cabecera: {fallo}"
    return i, f"máquina {i.maquina}, haz {i.haz}; {i.accesorio}: {QUE_ES.get(i.dato, i.dato)}"


def _partes(ruta):
    return [parte for parte in re.split(r"[\\/]+", ruta) if parte] or [ruta]


def nombres_para_mostrar(rutas):
    """{ruta: cómo se ve}: el nombre del archivo y, solo si otro se llama igual (un name.data por cuña en carpetas distintas), las carpetas que hacen falta para distinguirlos."""
    partes = {ruta: _partes(ruta) for ruta in rutas}
    cortos = {}
    for ruta, suyas in partes.items():
        n = 1
        while n < len(suyas) and any(otras[-n:] == suyas[-n:] for otra, otras in partes.items() if otra != ruta):
            n += 1
        cortos[ruta] = "/".join(suyas[-n:])
    return cortos


def legible(texto, cortos):
    """El texto del servicio con cada ruta completa cambiada por su nombre corto (el servicio nombra cada archivo por la ruta que recibió, UM3-D3). En UNA pasada y de la más larga a la más corta:
    un nombre ya puesto no se vuelve a cambiar (el corto de una ruta puede contener otra ruta) y una ruta que empieza como otra se cambia entera."""
    if not cortos:
        return texto
    rutas = re.compile("|".join(re.escape(ruta) for ruta in sorted(cortos, key=len, reverse=True)))
    return rutas.sub(lambda hallada: cortos[hallada.group(0)], texto)


def cunas_de(identidades):
    """Los ángulos de las cuñas que traen los archivos, de menor a mayor: una casilla de factor escrito por cada una."""
    return sorted({i.angulo_cuna for i in identidades if i is not None and i.angulo_cuna is not None})


def energia_de(identidades):
    """La energía que dicen TODOS los archivos que se entienden, en la forma del lector («6 MV»), o None si no dicen la misma o no se reconoce."""
    haces = {lector.clave_energia(i.haz) for i in identidades if i is not None}
    return haces.pop() if len(haces) == 1 and None not in haces else None


def campo_de_la_cuna(angulo):
    return Campo(f"wf_{angulo}", f"Factor de la cuña de {angulo}° en 10 × 10", f"el factor de la cuña de {angulo}° en 10 × 10", False, ayuda="opcional",
                 explicacion=f"Opcional. El factor de la cuña de {angulo}° en 10 × 10 a la profundidad de la tabla. Vacío, se deduce de su name.data si está; si no, se escribe por campo.")


def carga_desde_textos(equipo, energia, d0, donde, origen, wf, observaciones, archivos):
    """Los argumentos, CON NOMBRE, de `um_datos_haz.revisar` y `um_datos_haz.guardar` (sin el usuario), o `um_motor.FaltaDato` con todos los motivos de lectura, uno por línea. Los números se
    leen con la regla de la pestaña (`leer_numero`); los rangos NO se repiten aquí: los decide el servicio. `wf`: {ángulo: texto}; vacío, no se escribe."""
    motivos, escritos = [], {}
    clave = lector.clave_energia(energia)
    if not energia.strip():
        motivos.append("Falta escribir la energía, por ejemplo «6 MV».")
    elif clave is None:
        motivos.append(f"No se entiende la energía «{energia.strip()}»: se escribe como «6 MV» o «6X» (solo fotones).")
    try:
        valor_d0 = leer_numero(d0, CAMPO_D0)
    except um_motor.FaltaDato as fallo:
        motivos.append(str(fallo))
        valor_d0 = None
    for angulo, texto in sorted(wf.items()):
        try:
            valor = leer_numero(texto, campo_de_la_cuna(angulo))
        except um_motor.FaltaDato as fallo:
            motivos.append(str(fallo))
            continue
        if valor is not None:
            escritos[angulo] = valor
    if not origen.strip():
        motivos.append("Falta escribir de dónde sale D'0, por ejemplo «Eclipse: 1 cGy/UM en dmax».")
    if motivos:
        raise um_motor.FaltaDato("\n".join(motivos))
    return {"equipo": equipo, "energia": clave, "archivos": archivos, "d0_dmax": valor_d0 if donde == D0_EN_DMAX else None,
            "d0_tabla": valor_d0 if donde == D0_EN_LA_TABLA else None, "d0_origen": origen.strip(), "wf_escritos": escritos, "curva_sc": None, "sc_origen": None,
            "observaciones": observaciones.strip() or None}


def estado_de_cada_archivo(archivos, revision):
    """UM5-S8: qué es cada archivo elegido para la carga, en el orden en que llegaron: `USA`, `IGNORA`, `IMPIDE` (nombrado en un problema, aunque el servicio lo haya clasificado como usado o
    ignorado: se usaría, pero no se puede guardar) o `SIN_CLASIFICAR` (el servicio no lo clasificó en ninguna lista: lo impide otro problema); None si no hay revisión (lo escrito no se
    entendió y no se revisó). Es la ÚNICA clasificación: de ella salen las filas de la tabla y el conteo. `revision`: la `um_armar.Revision` del servicio."""
    if revision is None:
        return None
    usados, ignorados = set(revision.usados), set(revision.ignorados)
    estados = []
    for ruta, _ in archivos:
        nombrado = re.compile(re.escape(ruta) + r"(?=[: ]|$)")       # el servicio nombra el archivo seguido de «:», de un espacio o al final
        if any(nombrado.search(problema) for problema in revision.problemas):
            estados.append(IMPIDE)                     # primero: uno que se usaría pero da un problema (otra máquina) no «se usa»
        elif ruta in usados:
            estados.append(USA)
        elif ruta in ignorados:
            estados.append(IGNORA)
        else:
            estados.append(SIN_CLASIFICAR)
    return estados


def filas_de_los_archivos(archivos, no_leidos, dichos, revision, cortos):
    """Una fila por archivo elegido, en el orden en que llegaron: (cómo se ve, lo que dice ser, qué pasa con él en la carga, según `estado_de_cada_archivo`). `dichos`: {ruta: texto de
    `lo_que_dice`}; `revision`: la `um_armar.Revision` del servicio, o None si lo escrito no se entendió y no se revisó."""
    estados = estado_de_cada_archivo(archivos, revision)
    filas = [(cortos[ruta], dichos[ruta], SIN_REVISAR if estados is None else ESTADO_EN_LA_TABLA[estados[i]]) for i, (ruta, _) in enumerate(archivos)]
    filas += [(cortos[ruta], motivo, "Impide guardar: no se leyó") for ruta, motivo in no_leidos]
    return filas


def texto_del_conteo(archivos, no_leidos, revision):
    """Cuántos archivos se eligieron y qué es cada uno (`estado_de_cada_archivo`): cada archivo se cuenta UNA vez y los números suman el total (UM5-S8). Sin nada que impida guardar dice
    cuántos se usan y cuántos se ignoran; con algo (un archivo nombrado en un problema, o uno que el servicio no clasificó) dice además cuántos impiden guardar; los que no se pudieron leer
    van al final. Sin revisión (lo escrito no se entendió, o un archivo que no se puede decodificar cortó la revisión: el servicio no clasificó ninguno y dejó algún archivo sin veredicto), lo
    dice en lugar de contar ceros. Si el servicio no clasificó ninguno pero NOMBRÓ a cada archivo en un problema, no cortó nada: los revisó uno por uno y cada uno impide guardar, como dice su fila
    (R1-S8a)."""
    total = len(archivos) + len(no_leidos)
    estados = estado_de_cada_archivo(archivos, revision)
    texto = f"{total} {'archivo' if total == 1 else 'archivos'}: "
    if estados is None or (revision.problemas and not revision.usados and not revision.ignorados and SIN_CLASIFICAR in estados):
        texto += "sin revisar"
    else:
        usan, ignoran, impiden = estados.count(USA), estados.count(IGNORA), estados.count(IMPIDE) + estados.count(SIN_CLASIFICAR)
        se_usan, se_ignoran = f"{usan} se {'usa' if usan == 1 else 'usan'}", f"{ignoran} se {'ignora' if ignoran == 1 else 'ignoran'}"
        texto += f"{se_usan} y {se_ignoran}" if not impiden else f"{se_usan}, {se_ignoran} y {impiden} {'impide' if impiden == 1 else 'impiden'} guardar"
    return texto + (f"; {len(no_leidos)} no se {'pudo' if len(no_leidos) == 1 else 'pudieron'} leer." if no_leidos else ".")


def texto_de_lo_vigente(equipo, energia, registro):
    """Qué pasa con lo guardado si se guarda esta carga: el servicio anula el conjunto vigente de la misma clave y lo deja en el historial (DA-49, DA-52)."""
    if registro is None:
        return f"No hay tablas guardadas del {equipo}, {energia}: estas serán las primeras."
    return (f"Ya hay tablas vigentes del {equipo}, {energia}, cargadas el {registro['fecha_registro']} por {registro['usuario']}: al guardar, estas pasan a ser las vigentes y "
            "aquellas quedan en el historial.")


def texto_del_rechazo(motivo, cortos):
    """Por qué el servicio no guardó, en una frase que empieza por «No se guardó nada» y sin la palabra técnica de la denegación."""
    if motivo == um_datos_haz.DENEGADO:
        motivo = um_datos_haz.DENEGADO.partition(": ")[2]
    if not motivo.startswith(um_datos_haz.NO_SE_GUARDA):
        motivo = um_datos_haz.NO_SE_GUARDA + motivo
    return legible(motivo, cortos)


def texto_de_lo_guardado(equipo, energia, habia):
    return (f"Guardadas las tablas del {equipo}, {energia}: la pestaña ya calcula con ellas. "
            + ("Las anteriores quedan en el historial." if habia else "Son las primeras de esta energía."))


def _vigente(registro):
    return registro.get("activo") in (None, 1)


def filas_del_historial(registros):
    """Una fila por carga, de la más reciente a la más antigua (`um_datos_haz.historial`): (cargadas el, por, estado, D'0, archivos, a cuál reemplazó, observaciones). Una carga cuyo
    contenido guardado no se puede leer dice por qué en la columna de D'0 (no esconde las demás)."""
    filas = []
    for i, r in enumerate(registros):
        anterior = registros[i + 1] if i + 1 < len(registros) else None
        if r.get("problema"):
            d0 = f"No se puede leer: {r['problema']}"
        else:
            valor, donde = (r["d0_dmax"], D0_EN_DMAX) if r["d0_tabla"] is None else (r["d0_tabla"], D0_EN_LA_TABLA)
            d0 = f"{texto_sin_perder(valor)} [cGy/UM] {donde} ({r['d0_origen']})"           # R1-H1: el D'0 guardado con todas sus cifras (el historial es el registro de qué se cargó)
        reemplazo = f"La carga del {anterior['fecha_registro']}, de {anterior['usuario']}" if anterior else "Ninguna: fue la primera"
        filas.append((r["fecha_registro"], r["usuario"], "Vigente" if _vigente(r) else "Reemplazada", d0, str(len(r["archivos"])), reemplazo, r["observaciones"] or ""))
    return filas


def filas_de_los_archivos_guardados(registro):
    """Los archivos de una carga del historial: (accesorio, qué dato es, cómo se ve, las 12 primeras cifras de su huella sha256, tamaño en bytes, estado)."""
    cortos = nombres_para_mostrar([a["nombre_archivo"] for a in registro["archivos"]])
    return [(a["accesorio"], QUE_ES.get(a["dato"], a["dato"]), cortos[a["nombre_archivo"]], a["sha256"][:12], str(a["bytes"]), "Vigente" if _vigente(a) else "Anulado")
            for a in registro["archivos"]]


# ================================================================================================================================== capa de widgets

def _tabla(columnas):
    tabla = QTableWidget(0, len(columnas))
    tabla.setHorizontalHeaderLabels(list(columnas))
    tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
    tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
    tabla.verticalHeader().setVisible(False)
    tabla.verticalHeader().setDefaultSectionSize(ALTO_DE_UNA_FILA)
    cabecera = tabla.horizontalHeader()
    cabecera.setSectionResizeMode(QHeaderView.Interactive)
    cabecera.setStretchLastSection(True)
    return tabla


def _llenar(tabla, filas, anchos=()):
    tabla.setRowCount(len(filas))
    for i, fila in enumerate(filas):
        for j, texto in enumerate(fila):
            celda = QTableWidgetItem(texto)
            celda.setToolTip(texto)
            tabla.setItem(i, j, celda)
    for j, ancho in enumerate(anchos):
        tabla.setColumnWidth(j, ancho)


def _lista():
    lista = QListWidget()
    lista.setWordWrap(True)
    lista.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)     # un texto más alto que la lista se lee entero (TP-1 de la auditoría de UM.4)
    return lista


def _con_espera(funcion):
    """Lo que tarda (leer y revisar archivos, guardar) con el cursor de espera, que vuelve siempre (DA-71)."""
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        return funcion()
    finally:
        QApplication.restoreOverrideCursor()


class DialogoCargarTablas(QDialog):
    """La carga de las tablas de UNA energía (DC13). Se abre con `show()` (nunca `exec_`, Trampa 2), es hijo de la pestaña y modal para la ventana: mientras está abierto la pestaña no cambia
    de equipo ni de energía. `pagina`: la `CalculadoraUM`, de la que toma el equipo, la energía elegida y el login, y a la que avisa al guardar (`tablas_guardadas`)."""

    def __init__(self, pagina):
        super().__init__(pagina)
        self.pagina = pagina
        self.setWindowTitle(TITULO_DE_LA_CARGA)
        self.setModal(True)
        self.archivos, self.no_leidos, self.dichos, self.identidades, self.cortos = [], [], {}, {}, {}
        self.campos_wf = {}
        self.revision = None
        self._revisada = None        # los argumentos de la última revisión SIN problemas: lo único que «Guardar» guarda
        self._habia_vigente = None   # si al revisar ya había tablas vigentes de esa clave (None: no se supo)
        self._carpeta = ""
        self._armar()
        self._invalidar()
        self.estado.setText(SIN_ARCHIVOS)

    # ------------------------------------------------------------------ armado
    def _armar(self):
        capa = QVBoxLayout(self)
        arriba = QGridLayout()
        self.combo_equipo = QComboBox()
        self.combo_equipo.addItems(EQUIPOS)
        self.combo_equipo.setCurrentIndex(max(self.combo_equipo.findText(self.pagina.combo_equipo.currentText()), 0))
        self.linea_energia = QLineEdit(self.pagina.combo_energia.currentData() or "")
        self.linea_energia.setPlaceholderText("por ejemplo, 6 MV")
        self.linea_energia.setToolTip("La energía de los archivos; vacía, se toma de lo que dicen los archivos. Si los archivos dicen otra, no se puede guardar.")
        self.boton_elegir = QPushButton("Elegir archivos")
        self.etiqueta_conteo = QLabel()
        self.linea_d0 = QLineEdit(CAMPO_D0.inicial)
        self.linea_d0.setToolTip(CAMPO_D0.explicacion)
        self.combo_d0 = QComboBox()
        self.combo_d0.addItems((D0_EN_DMAX, D0_EN_LA_TABLA))
        self.linea_origen = QLineEdit(ORIGEN_INICIAL)
        self.linea_origen.setToolTip("De dónde sale D'0: queda guardado con las tablas.")
        self.linea_observaciones = QLineEdit()
        self.linea_observaciones.setPlaceholderText("opcional")
        for fila, (etiqueta, widget, otra, otro) in enumerate((("Equipo", self.combo_equipo, "Energía", self.linea_energia),
                                                              (CAMPO_D0.etiqueta, self.linea_d0, "D'0 escrito", self.combo_d0),
                                                              ("Origen de D'0", self.linea_origen, "Observaciones", self.linea_observaciones))):
            arriba.addWidget(QLabel(etiqueta), fila, 0)
            arriba.addWidget(widget, fila, 1)
            arriba.addWidget(QLabel(otra), fila, 2)
            arriba.addWidget(otro, fila, 3)
        arriba.addWidget(self.boton_elegir, 0, 4)
        arriba.addWidget(self.etiqueta_conteo, 1, 4, 2, 1)
        arriba.setColumnStretch(1, 1)
        arriba.setColumnStretch(3, 1)
        capa.addLayout(arriba)
        self.titulo_cunas = QLabel("Factores de cuña escritos")
        self.rejilla_cunas = QGridLayout()
        capa.addWidget(self.titulo_cunas)
        capa.addLayout(self.rejilla_cunas)

        self.tabla_archivos = _tabla(COLUMNAS_DE_LOS_ARCHIVOS)
        self.lista_problemas, self.lista_avisos = _lista(), _lista()
        self.titulo_problemas, self.titulo_avisos = QLabel(), QLabel()
        partes = QSplitter(Qt.Vertical)
        partes.setChildrenCollapsible(False)       # UM5-S2: ningún panel del resumen se esconde con un arrastre
        self.titulo_problemas.setText("Lo que impide guardar")
        self.titulo_avisos.setText("Lo que entendió la app y conviene mirar")
        _llenar(self.tabla_archivos, [], ANCHOS_DE_LOS_ARCHIVOS)
        self.nota_filas_y_columnas = QLabel(FILAS_Y_COLUMNAS)
        for titulo, widget in ((None, self.tabla_archivos), (self.titulo_problemas, self.lista_problemas), (self.titulo_avisos, self.lista_avisos)):
            caja = QWidget()
            interior = QVBoxLayout(caja)
            interior.setContentsMargins(0, 0, 0, 0)
            if titulo is not None:
                interior.addWidget(titulo)
            interior.addWidget(widget)
            partes.addWidget(caja)
        for i, peso in enumerate((3, 2, 2)):          # la tabla de los archivos, lo que impide guardar y lo que conviene mirar
            partes.setStretchFactor(i, peso)
        self.lista_problemas.setMinimumHeight(3 * ALTO_DE_UNA_FILA)        # lo que impide guardar se ve de a tres líneas por lo menos (con doce, con su barra)
        capa.addWidget(partes, 1)
        capa.addWidget(self.nota_filas_y_columnas)
        self.etiqueta_vigente = QLabel()
        self.estado = QLabel()
        for etiqueta in (self.etiqueta_vigente, self.estado):
            etiqueta.setTextInteractionFlags(Qt.TextSelectableByMouse)
            capa.addWidget(etiqueta)
        # UM5-S1: toda etiqueta del diálogo cuyo texto puede traer algo escrito o cargado (un nombre, un motivo del servicio, el texto de un fallo, el conteo de los archivos), una sola lista: ninguna
        # fija el ancho mínimo del diálogo según su texto. Los títulos de las listas solo llevan una cifra propia, corta: no ajustan la línea. R1-S8b: el conteo, con el texto de UM5-S8, ya no es corto
        # (hasta 1320 [px] de mínimo con 122 archivos): ajusta la línea y su celda tiene un ancho propio, `ANCHO_DEL_CONTEO` (sin él la celda toma el del botón y hasta el conteo de siempre se parte en
        # dos líneas), así que uno más largo se parte dentro de las dos filas que ocupa en lugar de ensanchar el diálogo o hacerlo crecer.
        self.etiquetas_que_cambian = (self.nota_filas_y_columnas, self.etiqueta_vigente, self.estado, self.etiqueta_conteo)
        que_no_fije_el_ancho(*self.etiquetas_que_cambian, vertical=QSizePolicy.Preferred)
        self.etiqueta_conteo.setMinimumWidth(ANCHO_DEL_CONTEO)
        botones = QHBoxLayout()
        self.boton_revisar, self.boton_guardar, self.boton_cerrar = QPushButton("Revisar"), QPushButton("Guardar estas tablas"), QPushButton("Cerrar")
        botones.addStretch(1)
        for boton in (self.boton_revisar, self.boton_guardar, self.boton_cerrar):
            boton.setAutoDefault(False)
            botones.addWidget(boton)
        capa.addLayout(botones)
        self.resize(*TAMANO_DE_LA_CARGA)
        self.titulo_cunas.setVisible(False)

        self.boton_elegir.clicked.connect(self.elegir_archivos)
        self.boton_revisar.clicked.connect(self.revisar)
        self.boton_guardar.clicked.connect(self.guardar)
        self.boton_cerrar.clicked.connect(self.close)
        self.combo_equipo.currentIndexChanged.connect(self._invalidar)
        self.combo_d0.currentIndexChanged.connect(self._invalidar)
        for linea in (self.linea_energia, self.linea_d0, self.linea_origen, self.linea_observaciones):
            linea.textEdited.connect(self._invalidar)

    def _armar_cunas(self, angulos):
        """Una casilla de factor escrito por cada cuña de los archivos (las de antes se quitan; lo que se escribió en una que sigue se conserva)."""
        antes = {angulo: linea.text() for angulo, linea in self.campos_wf.items()}
        while self.rejilla_cunas.count():
            widget = self.rejilla_cunas.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        self.campos_wf = {}
        for i, angulo in enumerate(angulos):
            campo = campo_de_la_cuna(angulo)
            linea = QLineEdit(antes.get(angulo, ""))
            linea.setPlaceholderText(campo.ayuda)
            linea.setToolTip(campo.explicacion)
            linea.textEdited.connect(self._invalidar)
            self.rejilla_cunas.addWidget(QLabel(campo.etiqueta), i // 2, 2 * (i % 2))
            self.rejilla_cunas.addWidget(linea, i // 2, 2 * (i % 2) + 1)
            self.campos_wf[angulo] = linea
        self.titulo_cunas.setVisible(bool(angulos))

    # ------------------------------------------------------------------ los archivos
    def elegir_archivos(self):
        rutas, _ = QFileDialog.getOpenFileNames(self, "Elija los archivos de una energía", self._carpeta, FILTRO_DE_ARCHIVOS)
        if rutas:
            self._carpeta = os.path.dirname(rutas[0])
            self.usar_archivos(rutas)

    def usar_archivos(self, rutas):
        """Lee los archivos elegidos (la lista reemplaza a la anterior), lo que dice cada uno de sí mismo y revisa la carga."""
        self.archivos, self.no_leidos = _con_espera(lambda: leer_archivos(rutas))
        self.cortos = nombres_para_mostrar([ruta for ruta, _ in self.archivos] + [ruta for ruta, _ in self.no_leidos])
        self.identidades, self.dichos = {}, {}
        for ruta, contenido in self.archivos:
            self.identidades[ruta], self.dichos[ruta] = lo_que_dice(contenido)
        if not self.linea_energia.text().strip():
            self.linea_energia.setText(energia_de(self.identidades.values()) or "")
        self._armar_cunas(cunas_de(self.identidades.values()))
        self.revisar()

    # ------------------------------------------------------------------ revisar y guardar
    def _invalidar(self, *_):
        self._revisada = None
        self.boton_guardar.setEnabled(False)
        if self.archivos or self.no_leidos:
            self.estado.setText(LO_ESCRITO_CAMBIO)

    def _argumentos(self):
        return carga_desde_textos(self.combo_equipo.currentText(), self.linea_energia.text(), self.linea_d0.text(), self.combo_d0.currentText(), self.linea_origen.text(),
                                  {angulo: linea.text() for angulo, linea in self.campos_wf.items()}, self.linea_observaciones.text(), list(self.archivos))

    def revisar(self):
        """Pide al servicio el resumen de lo que se va a guardar y lo muestra; «Guardar» se habilita solo si nada lo impide."""
        self._invalidar()
        if not (self.archivos or self.no_leidos):
            self.estado.setText(SIN_ARCHIVOS)
            return
        self.revision, problemas, avisos, vigente = None, [], [], ""
        try:
            argumentos = self._argumentos()
        except um_motor.FaltaDato as fallo:
            argumentos, problemas = None, str(fallo).split("\n")
        if argumentos is not None:
            try:
                self.revision = _con_espera(lambda: um_datos_haz.revisar(equipo=argumentos["equipo"], energia=argumentos["energia"], archivos=argumentos["archivos"],
                                                                        d0_dmax=argumentos["d0_dmax"], d0_tabla=argumentos["d0_tabla"], wf_escritos=argumentos["wf_escritos"],
                                                                        curva_sc=argumentos["curva_sc"], sc_origen=argumentos["sc_origen"], d0_origen=argumentos["d0_origen"],
                                                                        observaciones=argumentos["observaciones"]))
                problemas, avisos = [legible(p, self.cortos) for p in self.revision.problemas], [legible(a, self.cortos) for a in self.revision.avisos]
            except Exception as fallo:   # noqa: BLE001 -- la frontera de la ventana: lo que no se esperaba se dice y no deja guardar
                problemas = [f"La revisión falló por un error inesperado ({type(fallo).__name__}: {fallo}). Avise a quien mantiene la app."]
            vigente = self._lo_vigente(argumentos["equipo"], argumentos["energia"])
        problemas += [f"{self.cortos[ruta]}: {motivo}" for ruta, motivo in self.no_leidos]
        _llenar(self.tabla_archivos, filas_de_los_archivos(self.archivos, self.no_leidos, self.dichos, self.revision, self.cortos), ANCHOS_DE_LOS_ARCHIVOS)
        self.etiqueta_conteo.setText(texto_del_conteo(self.archivos, self.no_leidos, self.revision))
        self.lista_problemas.clear()
        self.lista_problemas.addItems(problemas or [NADA_IMPIDE])
        self.titulo_problemas.setText(f"Lo que impide guardar ({len(problemas)})")
        self.lista_avisos.clear()
        self.lista_avisos.addItems(avisos)
        self.titulo_avisos.setText(f"Lo que entendió la app y conviene mirar ({len(avisos)})")
        self.etiqueta_vigente.setText(sin_palabras_enormes(vigente))         # R1-S1: el fallo de la base o un nombre sin espacios tampoco ensanchan el diálogo
        if problemas:
            self.estado.setText(f"No se puede guardar: {len(problemas)} {'problema' if len(problemas) == 1 else 'problemas'} (arriba, con su motivo).")
            return
        self._revisada = argumentos
        self.boton_guardar.setEnabled(True)
        self.estado.setText(SE_PUEDE_GUARDAR)

    def _lo_vigente(self, equipo, energia):
        """El texto de lo que pasa con las tablas vigentes al guardar; anota si las hay (lo dice el aviso de lo guardado)."""
        try:
            registro = um_datos_haz.vigente(equipo, energia)
        except Exception as fallo:   # noqa: BLE001 -- no saber si hay tablas vigentes no impide revisar; se dice
            self._habia_vigente = None
            return f"No se pudo saber si ya hay tablas vigentes del {equipo}, {energia}: {fallo}"
        self._habia_vigente = registro is not None
        return texto_de_lo_vigente(equipo, energia, registro)

    def guardar(self):
        """Guarda EXACTAMENTE lo revisado, con el login de la sesión, y avisa a la pestaña. El servicio vuelve a comprobar todo y el permiso."""
        argumentos = self._revisada
        if argumentos is None:
            return
        habia = self._habia_vigente
        try:
            ok, motivo, _ = _con_espera(lambda: um_datos_haz.guardar(equipo=argumentos["equipo"], energia=argumentos["energia"], archivos=argumentos["archivos"],
                                                                    d0_dmax=argumentos["d0_dmax"], d0_tabla=argumentos["d0_tabla"], d0_origen=argumentos["d0_origen"],
                                                                    wf_escritos=argumentos["wf_escritos"], curva_sc=argumentos["curva_sc"], sc_origen=argumentos["sc_origen"],
                                                                    observaciones=argumentos["observaciones"], usuario=self.pagina.login))
        except Exception as fallo:   # noqa: BLE001 -- se dice, no se traga
            ok, motivo = False, f"el guardado falló por un error inesperado ({type(fallo).__name__}: {fallo}); mire el historial antes de volver a intentarlo y avise a quien mantiene la app"
        self._invalidar()
        if not ok:
            self.estado.setText(sin_palabras_enormes(texto_del_rechazo(motivo, self.cortos)))
            return
        self.etiqueta_vigente.setText("")         # lo que decía de las tablas vigentes ya no es cierto: ahora las vigentes son éstas
        self.estado.setText(texto_de_lo_guardado(argumentos["equipo"], argumentos["energia"], habia))
        self.pagina.tablas_guardadas(argumentos["equipo"], argumentos["energia"])


class DialogoHistorial(QDialog):
    """El historial de las tablas del equipo y la energía elegidos en la pestaña (`um_datos_haz.historial`): todas las cargas, la vigente y las reemplazadas, con quién y cuándo, y los archivos
    de la carga elegida. No es modal (`show`) y es hijo de la pestaña."""

    def __init__(self, pagina, equipo, energia):
        super().__init__(pagina)
        self.setWindowTitle(f"{TITULO_DEL_HISTORIAL}: {equipo}, {energia}" if energia else TITULO_DEL_HISTORIAL)
        self.setModal(False)
        capa = QVBoxLayout(self)
        self.aviso = QLabel()
        que_no_fije_el_ancho(self.aviso, vertical=QSizePolicy.Preferred)        # UM5-S1
        self.tabla = _tabla(COLUMNAS_DEL_HISTORIAL)
        self.tabla_archivos = _tabla(COLUMNAS_DE_LOS_GUARDADOS)
        capa.addWidget(self.aviso)
        capa.addWidget(self.tabla, 2)
        capa.addWidget(QLabel("Archivos de la carga elegida"))
        capa.addWidget(self.tabla_archivos, 1)
        self.resize(*TAMANO_DEL_HISTORIAL)
        self.registros = []
        if energia is None:
            self.aviso.setText(f"No hay tablas cargadas del {equipo}: no hay historial.")
        else:
            try:
                self.registros = um_datos_haz.historial(equipo, energia)
            except Exception as fallo:   # noqa: BLE001 -- se dice
                self.aviso.setText(sin_palabras_enormes(f"No se pudo leer el historial del {equipo}, {energia}: {fallo}"))
            else:
                self.aviso.setText(f"{len(self.registros)} {'carga' if len(self.registros) == 1 else 'cargas'} del {equipo}, {energia}, de la más reciente a la más antigua.")
        _llenar(self.tabla, filas_del_historial(self.registros), ANCHOS_DEL_HISTORIAL)
        self.tabla.currentCellChanged.connect(self._mostrar_archivos)
        if self.registros:
            self.tabla.setCurrentCell(0, 0)

    def _mostrar_archivos(self, fila, *_):
        _llenar(self.tabla_archivos, filas_de_los_archivos_guardados(self.registros[fila]) if 0 <= fila < len(self.registros) else [], ANCHOS_DE_LOS_GUARDADOS)
