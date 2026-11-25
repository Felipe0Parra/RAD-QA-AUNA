"""UM.6b (PLAN_CALCULADORA_UM_05-11.md, DC14, DC15, DC16): la subpestaña «Desde JSON» de la pestaña «Calculadora UM» (octavo módulo de la calculadora; la pestaña la importa diferido).

Sin SQL y sin física: el plan lo lee y lo calcula `services.um_plan_json` (la misma `um_motor.calcular` de la parte manual) y los datos de cada haz llegan por `CalculadoraUM.haz_vigente`, la misma
lectura de la parte manual (con su diccionario de haces por el `id` del conjunto vigente, Trampa 10). Dos capas, como la pantalla y el diálogo de la carga:

  - La CAPA PURA (sin Qt, arriba): el estado de cada fila y el resumen, con UNA clasificación (`clase_de_la_fila`) para la tabla y para el conteo, que suma el total; las celdas de la tabla; el texto
    de la cuña; el nombre que se ve (como lo cita un motivo del lector: en una línea, acortado y con lo que no se ve escrito con su código) y el entero de su ayuda; el motivo de un campo sin tablas, que dice quién las carga y con qué botón; la primera línea de lo copiado.
  - La CAPA DE WIDGETS (abajo): `PanelDesdeJSON` y `DialogoFormato` («Ver formato»: el texto de `um_plan_json.EJEMPLO_DE_PLAN`, el mismo que las pruebas calculan con las tablas reales).

Los umbrales son los de la parte manual (una sola fuente: sus dos campos); cambiarlos cambia los estados de la tabla y no las UM ni el error. El equipo y la energía de arriba no mandan sobre el plan:
cada campo usa las tablas de SU equipo y SU energía. Importar otro archivo reemplaza el anterior sin mezclar (y un archivo rechazado deja la tabla vacía, con su motivo). Nada se guarda ni se
imprime (P7): los nombres del plan y de los campos solo se muestran. Ningún slot deja escapar una excepción (llegaría a `error_log.txt` por el `excepthook` de `main.py`)."""
import os
from dataclasses import dataclass

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout,
                             QWidget)

from services import um_motor, um_plan_json
from ui.paginasGuia.calculadora_um import (QUIEN_CARGA, SIN_CUNA, SIN_RESULTADO, SIN_UM_DE_ECLIPSE, _citar, _llenar, _tabla, ayuda_en_texto_plano, cifras_del_error, columnas_quietas,
                                           filas_del_desglose, sin_palabras_enormes, texto_de_d_um, texto_de_las_um, texto_de_los_campos, texto_del_contexto, texto_del_error,
                                           texto_del_estado, texto_para_copiar, texto_sin_perder, umbrales_desde_textos)

# ================================================================================================================================== capa pura (sin Qt)

COLUMNAS = ("Campo", "Estado", "Error [%]", "UM calculadas [UM]", "UM de Eclipse [UM]", "Cuña", "Equipo", "Energía", "Avisos o motivo")      # lo que decide, primero: a 1366 [px] se ve sin desplazar
SIN_CALCULAR = "Sin calcular"
SIN_COMPARAR = "Sin UM de Eclipse"
SIN_EVALUAR = "Sin evaluar"
CLASES = ("Dentro", "Revisar", "Fuera", SIN_EVALUAR, SIN_COMPARAR, SIN_CALCULAR)      # el orden del resumen; Dentro, Revisar y Fuera son los de `um_motor.estado_de`
EN_EL_RESUMEN = {"Dentro": "dentro", "Revisar": "revisar", "Fuera": "fuera", SIN_EVALUAR: "sin evaluar", SIN_COMPARAR: "sin UM de Eclipse", SIN_CALCULAR: "sin calcular"}
SIEMPRE = ("Dentro", "Revisar", "Fuera")                                                # el resumen los dice aunque sean 0; los demás, solo si hay
FACTOR_ESCRITO = "factor escrito"
NADA_IMPORTADO = "Ningún plan importado. Pulse «Importar JSON» y elija el archivo del plan; «Ver formato» muestra cómo es."
NOTA = ("Cada campo se calcula con las tablas de su equipo y su energía, los que dice el archivo: el equipo y la energía de arriba son los de la parte manual, «Cargar tablas» e «Historial». "
        "Los umbrales de Dentro y Revisar son los de la parte manual, para toda la sesión: cambiarlos allí cambia los estados de esta tabla, no las UM ni el error. Nada de esto se guarda. "
        "Si otro puesto carga tablas, vuelva a importar el plan.")
RECALCULADO = "Recalculado con las tablas cargadas hace un momento."
MAXIMO_DEL_NOMBRE, MITAD_DEL_NOMBRE = 200, 99      # [caracteres] de un nombre en su ayuda y en lo copiado: entero hasta 200; uno absurdo, su comienzo, «…» y su final
CODIGO = len("<U+200B>")                            # [caracteres] de un carácter que no se ve, escrito con su código
MAXIMO_EN_LA_CELDA = um_plan_json.MAXIMO_CITADO + CODIGO      # [caracteres] de lo que se ve de un nombre en su celda: lo de 30 y un código
COMIENZO_EN_LA_CELDA, FINAL_EN_LA_CELDA = um_plan_json.CITA_COMIENZO + CODIGO, um_plan_json.CITA_FINAL + CODIGO      # el corte de la cita, con lugar para un código
ELIJA_UNA_FILA = "Elija una fila de la tabla para ver su desglose."
TITULO_DEL_FORMATO = "Calculadora UM: el formato del JSON de un plan"
EXPLICACION_DEL_FORMATO = ("Un objeto con «equipo», «energia» y la lista «campos», uno por campo del plan; el equipo y la energía de un campo mandan sobre los del plan. Lo que la calculadora no "
                           "entiende no lo ignora: una clave desconocida o un valor raro dejan ese campo sin calcular, con su motivo. Este es el ejemplo que las pruebas calculan con las tablas "
                           "reales del Clinac 600, 6 MV:")
TAMANO_DEL_FORMATO = (760, 620)
FILTRO = "Planes JSON (*.json);;Todos los archivos (*)"
PESOS_DEL_DIVISOR = (3, 2)      # a la izquierda la tabla (con el rechazo, el resumen y la nota encima), a la derecha el desglose de la fila elegida
PESOS_DEL_DESGLOSE = (3, 1)     # el desglose y los avisos, como en la parte manual


@dataclass(frozen=True)
class Fila:
    """Una fila de la tabla: el campo importado (`um_plan_json.CampoImportado`), su resultado (`um_motor.Resultado` o None) y su motivo (o None)."""
    campo: object
    resultado: object
    motivo: object


def _caben(caracteres, largo):
    """Cuántos de `caracteres`, en su orden, caben en `largo` caracteres con lo que no se ve escrito con su código."""
    usado = 0
    for cuantos, caracter in enumerate(caracteres):
        usado += len(um_plan_json._a_la_vista(caracter))
        if usado > largo:
            return cuantos
    return len(caracteres)


def nombre_para_mostrar(texto):
    """Un nombre del archivo (del plan o de un campo), como lo cita un motivo (`um_plan_json._cita`): en una línea, acortado y con lo que no se ve escrito con su código; si con los
    códigos pasa de `MAXIMO_EN_LA_CELDA`, su comienzo y su final sin partir un código."""
    visto = um_plan_json._cita(texto)
    if len(visto) <= MAXIMO_EN_LA_CELDA:
        return visto
    texto = " ".join(str(texto).split())
    comienzo, final = _caben(texto, COMIENZO_EN_LA_CELDA), _caben(texto[::-1], FINAL_EN_LA_CELDA)
    return um_plan_json._a_la_vista(texto[:comienzo]) + "…" + um_plan_json._a_la_vista(texto[len(texto) - final:])


def nombre_completo(texto):
    """El nombre entero, para la ayuda de su celda y lo copiado: en una línea y con lo que no se ve escrito con su código; solo uno absurdo (más de `MAXIMO_DEL_NOMBRE`) se acorta."""
    texto = " ".join(str(texto).split())
    if len(texto) > MAXIMO_DEL_NOMBRE:
        texto = texto[:MITAD_DEL_NOMBRE] + "…" + texto[-MITAD_DEL_NOMBRE:]
    return um_plan_json._a_la_vista(texto)


def motivo_sin_tablas(equipo, energia):
    """El motivo de un campo cuyo haz no tiene tablas cargadas: qué falta y quién las carga, con qué botón (el mismo `QUIEN_CARGA` del aviso de la parte manual)."""
    return f"No hay tablas cargadas del {equipo}, {energia}: sin ellas este campo no se calcula. {QUIEN_CARGA}"


def clase_de_la_fila(fila, umbrales):
    """La clase de una fila, UNA sola definición para la tabla y para el resumen: «Sin calcular» (sin resultado), «Sin UM de Eclipse» (sin con qué comparar), «Sin evaluar» (los umbrales escritos
    no sirven: `umbrales` es None) o el estado del motor con el error SIN redondear (`um_motor.estado_de`)."""
    if fila.resultado is None:
        return SIN_CALCULAR
    if fila.resultado.error_pct is None:
        return SIN_COMPARAR
    if umbrales is None:
        return SIN_EVALUAR
    return um_motor.estado_de(fila.resultado.error_pct, *umbrales)


def texto_del_resumen(filas, umbrales):
    """«N campos: a dentro, b revisar, c fuera y d sin calcular.»: cuenta las clases de `clase_de_la_fila` (la misma de la tabla), y siempre suma el total."""
    cuenta = {clase: 0 for clase in CLASES}
    for fila in filas:
        cuenta[clase_de_la_fila(fila, umbrales)] += 1
    partes = [f"{cuenta[clase]} {EN_EL_RESUMEN[clase]}" for clase in CLASES if clase in SIEMPRE or cuenta[clase]]
    return f"{len(filas)} {'campo' if len(filas) == 1 else 'campos'}: {', '.join(partes[:-1])} y {partes[-1]}."


def texto_de_la_cuna(entrada):
    """La cuña de una entrada: «Sin cuña», «15° IN», o «30° (factor escrito)» (con el factor escrito el motor no usa la orientación y el lector no la pasa, UM2-D18)."""
    if entrada.cuna is None:
        return SIN_CUNA
    return f"{entrada.cuna}° ({FACTOR_ESCRITO})" if entrada.wf_manual is not None else f"{entrada.cuna}° {entrada.cuna_orientacion}"


def celdas_de_la_fila(fila, umbrales):
    """Los textos de las columnas de `COLUMNAS`, en su orden, para una fila. Las UM de Eclipse, tal como se escribieron (`texto_sin_perder`); el error, con las cifras que piden los umbrales (`cifras_del_error`)."""
    campo, entrada, resultado = fila.campo, fila.campo.entrada, fila.resultado
    eclipse = "" if entrada is None or entrada.um_planeador is None else _citar(texto_sin_perder(entrada.um_planeador))      # uno absurdo no ensancha la columna: su motivo lo cita
    cuna = "" if entrada is None else texto_de_la_cuna(entrada)
    if resultado is None:
        um = error = ""
        avisos = sin_palabras_enormes(" ".join(str(fila.motivo).split()))
    else:
        um = f"{resultado.um:.1f}"
        error = "" if resultado.error_pct is None else cifras_del_error(resultado.error_pct, umbrales or ())
        avisos = {0: "Sin avisos", 1: "1 aviso"}.get(len(resultado.avisos), f"{len(resultado.avisos)} avisos")
    return (nombre_para_mostrar(campo.nombre), clase_de_la_fila(fila, umbrales), error, um, eclipse, cuna, campo.equipo or "", campo.energia or "", avisos)


def texto_del_contexto_del_campo(fila, texto_error, texto_estado):
    """La primera línea de lo que se copia: el campo (su nombre entero) y el contexto de la parte manual (`texto_del_contexto`), con la cuña como se ve en la tabla."""
    entrada = fila.campo.entrada
    orientacion = FACTOR_ESCRITO if entrada.wf_manual is not None else entrada.cuna_orientacion
    return f"Campo: {nombre_completo(fila.campo.nombre)} | " + texto_del_contexto(fila.campo.equipo, fila.campo.energia, entrada.cuna, orientacion, entrada.um_planeador, texto_error,
                                                                                        texto_estado)


def texto_del_archivo(nombre_del_plan, ruta):
    """Qué se importó: el nombre del plan (si lo dice) y el del archivo, acortados."""
    archivo = nombre_para_mostrar(os.path.basename(ruta))
    return f"Plan: {nombre_para_mostrar(nombre_del_plan)} (archivo {archivo})" if nombre_del_plan.strip() else f"Archivo: {archivo}"


# ================================================================================================================================== capa de widgets

class DialogoFormato(QDialog):
    """«Ver formato»: la explicación y `um_plan_json.EJEMPLO_DE_PLAN`, de solo lectura y en letra de ancho fijo. No es modal (`show`), es hijo del panel y se cierra con la cruz o con Esc."""

    def __init__(self, padre):
        super().__init__(padre)
        self.setWindowTitle(TITULO_DEL_FORMATO)
        self.setModal(False)
        capa = QVBoxLayout(self)
        self.explicacion = QLabel(EXPLICACION_DEL_FORMATO)
        self.explicacion.setWordWrap(True)
        self.ejemplo = QPlainTextEdit(um_plan_json.EJEMPLO_DE_PLAN)
        self.ejemplo.setReadOnly(True)
        self.ejemplo.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.boton_copiar = QPushButton("Copiar el ejemplo")
        self.boton_copiar.clicked.connect(lambda: QApplication.clipboard().setText(self.ejemplo.toPlainText()))
        for widget in (self.explicacion, self.ejemplo, self.boton_copiar):
            capa.addWidget(widget)
        self.resize(*TAMANO_DEL_FORMATO)


class PanelDesdeJSON(QWidget):
    """La subpestaña. `pagina` es la `CalculadoraUM`: de ella salen los umbrales (sus dos campos) y los datos de cada haz (`haz_vigente`)."""

    def __init__(self, pagina):
        super().__init__(pagina)
        self.pagina = pagina
        self.campos, self.filas, self.dialogo_formato, self.archivo = None, [], None, ""
        capa = QVBoxLayout(self)
        arriba = QHBoxLayout()
        self.boton_importar, self.boton_formato = QPushButton("Importar JSON"), QPushButton("Ver formato")
        self.etiqueta_archivo = QLabel(NADA_IMPORTADO)
        for widget in (self.boton_importar, self.boton_formato):
            arriba.addWidget(widget)
        arriba.addWidget(self.etiqueta_archivo, 1)
        capa.addLayout(arriba)
        izquierda = QWidget()
        lista = QVBoxLayout(izquierda)
        lista.setContentsMargins(0, 0, 0, 0)
        self.etiqueta_rechazo, self.etiqueta_resumen, self.nota = QLabel(), QLabel(), QLabel(NOTA)
        for etiqueta in (self.etiqueta_rechazo, self.etiqueta_resumen, self.nota):
            lista.addWidget(etiqueta)
        self.tabla_campos = _tabla(COLUMNAS)
        self.tabla_campos.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla_campos.setSelectionMode(QAbstractItemView.SingleSelection)
        lista.addWidget(self.tabla_campos, 1)
        derecha = QWidget()
        detalle = QVBoxLayout(derecha)
        detalle.setContentsMargins(0, 0, 0, 0)
        self.etiqueta_um, self.etiqueta_d_um, self.etiqueta_error, self.etiqueta_estado = QLabel(), QLabel(), QLabel(), QLabel()
        self.etiqueta_motivo, self.etiqueta_campos, self.titulo_avisos = QLabel(), QLabel(), QLabel()
        for etiqueta in (self.etiqueta_um, self.etiqueta_d_um, self.etiqueta_error, self.etiqueta_estado, self.etiqueta_motivo, self.etiqueta_campos):
            etiqueta.setTextInteractionFlags(Qt.TextSelectableByMouse)
            detalle.addWidget(etiqueta)
        self.etiqueta_um.setStyleSheet("font-size: 14pt; font-weight: bold;")
        self.tabla_desglose = _tabla(("Factor", "Valor", "Origen", "Detalle"))
        self.lista_avisos = QListWidget()
        self.lista_avisos.setWordWrap(True)
        self.lista_avisos.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        avisos = QWidget()
        capa_avisos = QVBoxLayout(avisos)
        capa_avisos.setContentsMargins(0, 0, 0, 0)
        capa_avisos.addWidget(self.titulo_avisos)
        capa_avisos.addWidget(self.lista_avisos)
        self.divisor_del_desglose = QSplitter(Qt.Vertical)
        self.divisor_del_desglose.setChildrenCollapsible(False)
        for parte, peso in zip((self.tabla_desglose, avisos), PESOS_DEL_DESGLOSE):
            self.divisor_del_desglose.addWidget(parte)
            self.divisor_del_desglose.setStretchFactor(self.divisor_del_desglose.count() - 1, peso)
        detalle.addWidget(self.divisor_del_desglose, 1)
        self.boton_copiar = QPushButton("Copiar el desglose")
        detalle.addWidget(self.boton_copiar)
        self.divisor = QSplitter(Qt.Horizontal)
        self.divisor.setChildrenCollapsible(False)
        for parte, peso in zip((izquierda, derecha), PESOS_DEL_DIVISOR):
            self.divisor.addWidget(parte)
            self.divisor.setStretchFactor(self.divisor.count() - 1, peso)
        self.divisor.setSizes([1000 * peso for peso in PESOS_DEL_DIVISOR])      # el reparto inicial es el de los pesos, no el del texto de la nota
        capa.addWidget(self.divisor, 1)
        # E2 y UM5-S1: las etiquetas cuyo texto cambia; la pestaña las suma a SU lista (`CalculadoraUM.etiquetas_que_cambian`, una sola) y les pone la regla común
        self.etiquetas_que_cambian = (self.etiqueta_archivo, self.etiqueta_rechazo, self.etiqueta_resumen, self.nota, self.etiqueta_um, self.etiqueta_d_um, self.etiqueta_error,
                                      self.etiqueta_estado, self.etiqueta_motivo, self.etiqueta_campos, self.titulo_avisos)
        self.boton_importar.clicked.connect(self.importar)
        self.boton_formato.clicked.connect(self.ver_formato)
        self.tabla_campos.itemSelectionChanged.connect(self._mostrar_la_fila)
        self.boton_copiar.clicked.connect(self.copiar)
        self._vaciar()

    # ------------------------------------------------------------------ importar
    def _umbrales(self):
        """(dentro, fuera) de los dos campos de la parte manual, o None si no sirven (el motivo lo dice el estado de la fila elegida)."""
        try:
            return umbrales_desde_textos(*self.pagina._textos_de_umbrales())
        except um_motor.FaltaDato:
            return None

    def _vaciar(self, rechazo=""):
        self.campos, self.filas, self.archivo = None, [], ""
        self.tabla_campos.setRowCount(0)
        self.etiqueta_archivo.setText(NADA_IMPORTADO)
        self.etiqueta_rechazo.setText(sin_palabras_enormes(rechazo))
        self.etiqueta_rechazo.setVisible(bool(rechazo))
        self.etiqueta_resumen.setText("")
        self.etiqueta_resumen.setVisible(False)
        self._mostrar_la_fila()

    def importar(self):
        """«Importar JSON»: elige el archivo (`QFileDialog.getOpenFileName`; cancelar no cambia nada) y lo carga."""
        ruta, _ = QFileDialog.getOpenFileName(self, "Importar JSON", "", FILTRO)
        if ruta:
            self.cargar(ruta)

    def cargar(self, ruta):
        """Lee y calcula el plan de `ruta`, reemplazando el anterior. Un archivo que no es un plan deja la tabla vacía y dice por qué; un error inesperado, igual (nunca escapa del slot)."""
        self._vaciar()
        try:
            nombre, campos = um_plan_json.leer_plan(um_plan_json.leer_archivo(ruta))
        except um_plan_json.PlanInvalido as fallo:
            self._vaciar(f"No se importó el archivo «{nombre_para_mostrar(os.path.basename(ruta))}»: {fallo}")
            return
        except Exception as fallo:   # noqa: BLE001 -- un error que no es un motivo se dice como tal y no deja tabla
            self._vaciar(f"No se importó el archivo: la lectura falló por un error inesperado ({type(fallo).__name__}). Avise a quien mantiene la app.")
            return
        self.campos, self.archivo = campos, sin_palabras_enormes(texto_del_archivo(nombre, ruta))
        self.etiqueta_archivo.setText(self.archivo)
        self.recalcular()

    def _datos_de(self, equipo, energia):
        """Los datos del haz para `um_plan_json.calcular_plan`: los de la parte manual (`haz_vigente`); sin tablas, un motivo que dice quién las carga."""
        haz = self.pagina.haz_vigente(equipo, energia)
        if haz is None:
            raise um_motor.FaltaDato(motivo_sin_tablas(equipo, energia))
        return haz[1]

    def recalcular(self, tras_cargar=False):
        """Vuelve a calcular el plan importado (al importarlo, y tras «Cargar tablas» en esta sesión, `tras_cargar`, que lo dice): nunca queda una UM de un conjunto que esta sesión reemplazó.
        Si otro puesto carga tablas, la tabla sigue siendo lo que se calculó al importar (la nota lo dice)."""
        if self.campos is None:
            return
        try:
            self.filas = [Fila(*f) for f in um_plan_json.calcular_plan(self.campos, self._datos_de)]
        except Exception as fallo:   # noqa: BLE001 -- calcular_plan no deja escapar nada de un campo; esto es un defecto propio y se dice
            self._vaciar(f"El cálculo del plan falló por un error inesperado ({type(fallo).__name__}). Avise a quien mantiene la app.")
            return
        _llenar(self.tabla_campos, [celdas_de_la_fila(f, self._umbrales()) for f in self.filas])
        for i, fila in enumerate(self.filas):
            self.tabla_campos.item(i, 0).setToolTip(ayuda_en_texto_plano(nombre_completo(fila.campo.nombre)))
        self.etiqueta_archivo.setText(f"{self.archivo} {RECALCULADO}" if tras_cargar else self.archivo)
        self.refrescar_estados()

    def refrescar_estados(self, *_):
        """Los estados, el error y el resumen con los umbrales escritos AHORA en la parte manual: cambiarlos no cambia las UM ni el error."""
        if not self.filas:
            return
        umbrales = self._umbrales()
        with columnas_quietas(self.tabla_campos):
            for i, fila in enumerate(self.filas):
                for j in (COLUMNAS.index("Error [%]"), COLUMNAS.index("Estado")):
                    texto = celdas_de_la_fila(fila, umbrales)[j]
                    self.tabla_campos.item(i, j).setText(texto)
                    self.tabla_campos.item(i, j).setToolTip(ayuda_en_texto_plano(texto))
        self.etiqueta_resumen.setText(texto_del_resumen(self.filas, umbrales))
        self.etiqueta_resumen.setVisible(True)
        self._mostrar_la_fila()

    # ------------------------------------------------------------------ la fila elegida
    def _elegida(self):
        filas = {i.row() for i in self.tabla_campos.selectedItems()}
        return self.filas[filas.pop()] if len(filas) == 1 and self.filas else None

    def _mostrar_la_fila(self):
        """El MISMO desglose de la parte manual para la fila elegida (`filas_del_desglose`, `texto_de_los_campos`, el error y el estado), o su motivo y ningún número."""
        fila = self._elegida()
        self.etiqueta_um.setText(ELIJA_UNA_FILA if fila is None else SIN_RESULTADO)
        for etiqueta in (self.etiqueta_d_um, self.etiqueta_error, self.etiqueta_estado, self.etiqueta_motivo, self.etiqueta_campos):
            etiqueta.setText("")
        self.tabla_desglose.setRowCount(0)
        self.lista_avisos.clear()
        self.titulo_avisos.setText("Avisos")
        self.boton_copiar.setEnabled(False)
        self.etiqueta_motivo.setVisible(False)
        self.etiqueta_campos.setVisible(False)
        if fila is None:
            return
        if fila.resultado is None:
            self.etiqueta_motivo.setText(sin_palabras_enormes(fila.motivo))
            self.etiqueta_motivo.setVisible(True)
            return
        r = fila.resultado
        self.etiqueta_um.setText(texto_de_las_um(r))
        self.etiqueta_d_um.setText(texto_de_d_um(r))
        textos = self.pagina._textos_de_umbrales()
        if r.error_pct is None:
            self.etiqueta_error.setText(SIN_UM_DE_ECLIPSE)
        else:
            umbrales = self._umbrales()
            self.etiqueta_error.setText(texto_del_error(r.error_pct, umbrales or ()))
            self.etiqueta_estado.setText(sin_palabras_enormes(texto_del_estado(r.error_pct, textos)))
        _llenar(self.tabla_desglose, filas_del_desglose(r))
        self.etiqueta_campos.setText(texto_de_los_campos(r))
        self.etiqueta_campos.setVisible(True)
        for aviso in r.avisos:
            self.lista_avisos.addItem(QListWidgetItem(aviso))
        self.titulo_avisos.setText(f"Avisos ({len(r.avisos)})")
        self.boton_copiar.setEnabled(True)

    def copiar(self):
        fila = self._elegida()
        if fila is not None and fila.resultado is not None:
            contexto = texto_del_contexto_del_campo(fila, self.etiqueta_error.text(), self.etiqueta_estado.text())
            QApplication.clipboard().setText(texto_para_copiar(fila.resultado, contexto))

    def ver_formato(self):
        if self.dialogo_formato is None:
            self.dialogo_formato = DialogoFormato(self)
        self.dialogo_formato.show()
        self.dialogo_formato.raise_()
