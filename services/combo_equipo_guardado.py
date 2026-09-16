"""T.1 (PLAN_COPIA_GUARDADA_Y_REPORTES_16-09.md §2): posicionar un combo de
equipos sobre LO QUE EL CONTROL GUARDÓ, no sobre lo que el catálogo tenga hoy.

PRINCIPIO QUE GOBIERNA ESTE MÓDULO (decisión del físico, 16-09-2026):

  1. Los valores que se muestran y se imprimen salen SIEMPRE de la copia
     guardada. El catálogo no decide ningún valor.
  2. El catálogo solo sirve para POSICIONAR el combo, que es cosmético. Si la
     entrada exacta no se puede identificar, **no se elige una parecida**: se
     añade la guardada como entrada propia. Una calibración NUEVA con la
     misma serie no puede contaminar un control viejo, porque nunca se usa
     como sustituta.
  3. Al guardar se identifica por `id` -- y el `id` queda como trazabilidad,
     no como la fuente de la que se leerá después.

De ahí la regla que hace distinto a este módulo de cualquier "buscar la serie
en el combo": **ante más de una candidata no se elige ninguna**. Desempatar
(por factor, por fecha, por id más alto) es adivinar, y es exactamente la vía
por la que una recalibración de una serie ya usada se colaría en un control
anterior. Una entrada de respaldo honesta vale más que una selección
plausible.

Existe como módulo propio, y no como método de un formulario, porque los
sitios que lo necesitan son TRES y no comparten ancestro: `PruebaMensualBraq`
y `CalRedundanteFuente` (que hereda de ella) en `braq_mensual.py`, y
`Linealidad` en `braquiterapia.py`, que hereda de `PruebaBasico`. Con el
criterio repartido en tres copias volvería a divergir -- que es cómo nació
`DP-105` (corolarios 1 y 4).
"""
from PyQt5.QtCore import Qt

from services.etiqueta_equipo import etiqueta_equipo, serie_de_etiqueta

# Rol propio donde cada entrada del combo guarda su SERIE REAL, aparte del
# texto visible (que lleva fecha y vigencia) y de `currentData()` (que sigue
# siendo el id del equipo, intacto para todos los lectores actuales).
#
# Hace falta porque el texto visible NO es la serie desde G10, y comparar
# textos decorados es frágil por construcción: cambia cada vez que cambia la
# etiqueta. Con la serie en su propio rol, la comparación es exacta y no
# depende del formato.
ROL_SERIE = Qt.UserRole + 1


def agregar_item_calibracion(combo, equipo, fecha_referencia):
    """Añade al combo una calibración del catálogo: texto de
    `etiqueta_equipo`, `id` en `currentData()` (sin cambios para los lectores
    de hoy) y la SERIE REAL en `ROL_SERIE`.

    Un solo punto para que ninguna de las cuatro poblaciones de combo de
    braquiterapia pueda olvidarse del rol -- si una lo olvidara, la recarga
    volvería a fallar solo en esa pantalla y en silencio."""
    texto, eq_id = etiqueta_equipo(equipo, fecha_referencia)
    combo.addItem(texto, eq_id)
    combo.setItemData(combo.count() - 1, equipo["serie"], ROL_SERIE)
    return texto, eq_id


def serie_de_item(combo, indice):
    """Serie real de una entrada. Usa `ROL_SERIE` si está puesto; si no
    (entradas creadas por código que este plan no tocó, o el marcador de
    posición), cae al inverso de la etiqueta sobre el texto visible."""
    guardada = combo.itemData(indice, ROL_SERIE)
    if guardada not in (None, ""):
        return str(guardada).strip()
    return serie_de_etiqueta(combo.itemText(indice))


def _indices_por_serie(combo, serie):
    return [i for i in range(combo.count())
            if serie_de_item(combo, i) == serie and serie != ""]


def agregar_copia_guardada(combo, serie, etiqueta=None):
    """Añade la copia que el control guardó como entrada PROPIA del combo:
    `data = None` (no es una calibración del catálogo) y su serie en el rol.

    `data = None` es deliberado y lo entienden los dos lados: el guardado
    (`T.2`/`T.3`) lo lee como *"no hay id del catálogo que respalde esto"* y
    arrastra la copia en vez de inventar un id por parecido."""
    combo.addItem(etiqueta if etiqueta is not None else f"Serie: {serie}", None)
    indice = combo.count() - 1
    combo.setItemData(indice, serie, ROL_SERIE)
    return indice


def posicionar_en_guardado(combo, serie_guardada, equipo_id=None,
                           model=None, resolver_guardado=None):
    """Deja el combo mostrando el equipo que ESE control guardó.

    Orden, y es el del principio:

      (a) si la fila trae `equipo_id` (columnas de `T.0`, presentes solo en lo
          guardado desde `T.2`), se usa ESE id -- identidad exacta, sin buscar
          nada. Se valida antes con `EquiposService.resolver_guardado`
          (`R.3`): un id que hoy resuelve a OTRO modelo/serie no se adopta.
      (b) si no, se compara SERIE REAL contra serie guardada (normalizando lo
          guardado con `serie_de_etiqueta`, que absorbe las filas decoradas).
          **Con más de una candidata NO se elige ninguna.**
      (c) si no queda una sola candidata -- ni cero ni varias -- se añade la
          copia guardada como entrada propia y se selecciona esa.

    En NINGÚN caso el id o el catálogo aportan un VALOR: solo deciden dónde se
    para el combo. El factor, T0, P0 y H0 los repone el llamador desde la
    copia, DESPUÉS de esto (patrón D2.2/K3).

    Las señales se bloquean durante toda la operación: sin eso,
    `on_serie_pozo_cambio` sobrescribiría factor y condiciones con los del
    catálogo en cuanto el índice cambiara (§0.4 del plan) -- el histórico
    quedaría pisado por el vigente.

    Devuelve el motivo de lo que hizo, para que el llamador pueda avisar o
    registrar: `"por_id"`, `"por_serie"`, `"copia_sin_candidata"`,
    `"copia_por_ambiguedad"` o `"sin_serie"`.
    """
    serie = serie_de_etiqueta(serie_guardada)

    bloqueadas = combo.blockSignals(True)
    try:
        if serie == "":
            return "sin_serie"

        if equipo_id is not None:
            id_confiable = equipo_id
            if resolver_guardado is not None:
                id_confiable = resolver_guardado(equipo_id, model, serie)
            if id_confiable is not None:
                indice = combo.findData(id_confiable)
                if indice >= 0:
                    combo.setCurrentIndex(indice)
                    return "por_id"

        candidatas = _indices_por_serie(combo, serie)
        if len(candidatas) == 1:
            combo.setCurrentIndex(candidatas[0])
            return "por_serie"

        motivo = ("copia_por_ambiguedad" if len(candidatas) > 1
                  else "copia_sin_candidata")
        combo.setCurrentIndex(agregar_copia_guardada(combo, serie))
        return motivo
    finally:
        combo.blockSignals(bloqueadas)


def posicionar_modelo(combo, modelo_guardado):
    """Mismo criterio para el combo de MODELO: si el modelo que el control
    guardó ya no está entre los activos, se añade en vez de dejar el combo
    mostrando otro. Sin ambigüedad posible (el modelo es único en la lista),
    así que aquí no hay caso de "varias candidatas".

    **Aquí NO se bloquean las señales, y es deliberado**: es el
    `currentTextChanged` del combo de modelo el que dispara
    `on_modelo_pozo_cambio`, que es quien PUEBLA el combo de series. Bloquearlo
    dejaría el combo de series vacío y la recarga no tendría dónde posicionarse
    -- se arreglaría un problema creando otro peor. El bloqueo corresponde al
    combo de SERIE (`posicionar_en_guardado`), que es donde la señal
    sobrescribe valores históricos con los del catálogo (§0.4 del plan).

    Con un modelo que ya no está activo, la cascada puebla el combo de series
    con cero calibraciones y `posicionar_en_guardado` añade la copia guardada:
    exactamente lo que debe pasar."""
    if modelo_guardado in (None, ""):
        return "sin_modelo"
    modelo = str(modelo_guardado).strip()

    indice = combo.findText(modelo)
    if indice < 0:
        combo.addItem(modelo, None)
        combo.setCurrentIndex(combo.count() - 1)
        return "copia_sin_candidata"
    combo.setCurrentIndex(indice)
    return "por_texto"
