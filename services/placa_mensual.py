"""D.1 (PLAN_ANALISIS_PELICULAS_08-10.md, DA-83 a DA-86): la ÚNICA puerta a la tabla `analisis_placa_mensual` -- el análisis nuevo del mensual de aceleradores (la imagen y los datos finales de la capa
que el físico reporta).

Sin ella la ventana (E.1) tendría SQL propio y el PDF (F.1) su propia lectura: tres definiciones de lo que es «el análisis guardado de un control». Aquí viven guardar, leer, volver a medir lo guardado
y compararlo con lo guardado. Qué se guarda de la capa lo dice UNA lista (`services/medidas_placa_mensual.py::MEDIDAS_GUARDADAS`): de ella salen el `CREATE TABLE`, el escritor y el lector, así que añadir o
quitar un valor es una línea. Qué se mide lo dice el motor (`analisisImagenes/placa_mensual.py`): este módulo nunca calcula un milímetro, un FWHM ni un piso.

Reglas de este servicio, cada una con su motivo:
  - `guardar` ANALIZA él mismo desde los bytes que guarda (no recibe un `resultado` ajeno: nada garantiza que sea el de esa imagen, la clase de error de IM3/DA-65): lee la película, refina cada clic
    con `refinar_marca` (C.1) y llama a `analizar` (C.2, que NO refina), una sola vez. De ese análisis salen los valores de la capa, la versión del motor, los parámetros con que se midió y el piso.
  - La IMAGEN se guarda tal como se subió (los mismos bytes, P12): el motor lee de ahí, y volver a medir exige la película original, no una copia recomprimida.
  - Se guardan los CINCO CLICS y sus marcas refinadas (`MarcaRefinada.como_dict()`), los PARÁMETROS (al reabrir se recalcula con ESTOS, no con los de hoy), la VERSIÓN y el PISO ENTERO (`Piso.como_dict()`:
    el modo, los valores por capa, las esquinas con sus respaldos, el punto marcado y, en el modo virgen, la COPIA ENTERA de la referencia): es lo necesario para volver a medir, como los puntos y los
    parámetros, no un dato final. La copia guardada manda (DA-81): `recalcular` toma el modo, el punto y la referencia virgen del registro (con `referencia_virgen_desde_dict`), NUNCA del archivo vigente.
  - La CAPA (`R`, `G` o `B`) y el MODO del piso llegan como argumentos SIN valor por omisión: son lo que decide qué número se guarda, y un valor por omisión para un dato que decide lo que se guarda es el
    defecto que el plan existe para evitar. `CAPA_POR_OMISION` es solo el valor con que arranca el menú de la ventana; este módulo no la lee.
  - Una capa que NO es medible no se guarda, por el motivo que sea (decisión del físico del 20-10-2026, que revierte D1-D3): la ÚNICA definición de esa regla y de su texto es `motivo_para_no_guardar`,
    que usan `guardar` (antes de W1 y de la transacción: el rechazo no escribe, no audita ni anula el vigente) y la ventana antes de ofrecer «Guardar». Medible = el estado de esa capa es «ok», sus dos
    perfiles medidos; una penumbra incompleta no la vuelve no medible. Un análisis sin piso (los puntos no forman el campo, otra resolución) se rechaza antes, con el mismo texto: no hay fila que armar.
  - Comprueba W1 (`puede_editarse(ref)`): un control anulado o inexistente no acepta el análisis. Va justo ANTES de abrir la transacción, después del análisis (que tarda un segundo): así la
    ventana entre la comprobación y la escritura es la más corta posible.
  - UNA transacción (`reemplazar_bloque`): anula el análisis vigente de ese control, inserta el nuevo y escribe UNA fila de auditoría (`guardar` si no había análisis, `reemplazo` si lo había, con el `id` de
    la reemplazada en el detalle); si algo falla a mitad no queda nada (DA-52). La fila de auditoría nombra la capa y el piso (`texto_breve_del_piso`, la única definición de esa línea).
  - Lecturas con `{filtro_activo(...)}` dentro del f-string (Trampa 6: AN1/ES1/RT1 solo lo reconocen así), por la clave de bloque `ref` (DA-47: una lectura por clave de bloque filtra la vigencia).

Sin Qt."""
import hashlib
import json
import numbers
from datetime import datetime

from analisisImagenes import placa_mensual as motor
from analisisImagenes.pelicula import (ADJETIVO_DE_LA_CAPA, CAPAS, CAPAS_DEL_PISO, MODOS_DEL_PISO, clase_resolucion, escala_mm, leer_pelicula, referencia_virgen_desde_dict,
                                       texto_breve_del_piso)
from data.ManejoDatos.conection import Conexion
from services import medidas_placa_mensual as medidas
from services.anulacion import filtro_activo, reemplazar_bloque
from services.audit_minimo import ACCION_GUARDAR, ACCION_REEMPLAZO
from services.ventana_edicion import mensaje_bloqueo_edicion, puede_editarse

TABLA = "analisis_placa_mensual"

# Lo que la fila de auditoría de un guardado dice de la capa (la letra R, G o B va al final); es el mismo vocabulario que la posición inicial de braqui («capa reportada G»).
TEXTO_DE_LA_CAPA_EN_LA_AUDITORIA = "capa reportada {}"

# Cuánto se pueden apartar lo guardado y lo recalculado para que `diferencias` los dé por iguales: 1e-6 mm (un nanómetro y medio por mil) para las longitudes y 1e-6 niveles para el piso. El mismo código
# sobre los mismos bytes da el mismo número al bit; esto solo absorbe el ruido de punto flotante de otra máquina (otro orden de las sumas, otra CPU). Una micra ya es una diferencia: cambiar el piso un nivel
# mueve el FWHM del azul 0.14 mm, el decodificador de JPEG puede mover el piso un nivel, y eso es justo lo que el físico tiene que ver.
TOLERANCIA_AL_RECALCULAR = 1e-6

_COLUMNAS_ANTES_DE_LAS_MEDIDAS = ("ref", "imagen", "nombre_archivo", "sha256", "formato", "bits", "transparentes", "dpi_declarado", "clase_resolucion", "tamano_pixel_mm", "version", "parametros", "puntos",
                                  "piso", "capa")
_COLUMNAS_DESPUES_DE_LAS_MEDIDAS = ("usuario", "fecha_registro")
_COLUMNAS_JSON = ("parametros", "puntos", "piso")


class PlacaMensualError(ValueError):
    """Lo que el servicio rechaza ANTES de escribir nada (y todo `ValueError` del motor o del lector de la imagen, con su mensaje): la ventana lo dice tal cual."""


class ControlNoEditable(PlacaMensualError):
    """El control al que pertenece el análisis ya no admite escritura (anulado o inexistente: la puerta W1 de `services/ventana_edicion.py`). El mensaje es el de `mensaje_bloqueo_edicion`."""


def _columnas_de_las_medidas():
    return tuple(m.nombre for m in medidas.MEDIDAS_GUARDADAS)


def _columnas_de_la_fila():
    return _COLUMNAS_ANTES_DE_LAS_MEDIDAS + _columnas_de_las_medidas() + _COLUMNAS_DESPUES_DE_LAS_MEDIDAS


def sql_insert():
    """El INSERT del análisis, con las columnas explícitas (MI0): las fijas y, en medio, las de `MEDIDAS_GUARDADAS` (la lista se lee en cada llamada). Solo COMPONE el texto; lo ejecuta `guardar`."""
    columnas = _columnas_de_la_fila()
    return f"INSERT INTO {TABLA} ({', '.join(columnas)}) VALUES ({', '.join('?' * len(columnas))})"


def _columnas_de_lectura():
    return "id, " + ", ".join(_columnas_de_la_fila()) + ", activo"


def _nombre_de_archivo(nombre):
    """Solo el nombre, sin la carpeta (con '/' o con '\\'): en la base no se guarda la ruta del equipo de quien lo subió."""
    if nombre is None:
        return None
    texto = str(nombre).replace("\\", "/").rsplit("/", 1)[-1].strip()
    return texto or None


def _ref_valido(ref):
    """El id de un control: un entero positivo (no un booleano). `puede_editarse(0)` o `puede_editarse(None)` dan True (W1 no bloquea lo que no puede resolver): el servicio lo exige antes."""
    if isinstance(ref, bool) or not isinstance(ref, numbers.Integral) or ref <= 0:
        raise PlacaMensualError(f"falta el control al que pertenece el análisis: el ref debe ser el id de un control (un entero positivo), no {ref!r}")
    return int(ref)


def _cinco_puntos(puntos):
    try:
        lista = list(puntos)
    except TypeError:
        raise PlacaMensualError("los puntos son una lista de cinco clics (x, y)") from None
    if len(lista) != 5:
        raise PlacaMensualError(f"hacen falta los cinco puntos del campo luminoso (cuatro esquinas y el retículo), no {len(lista)}")
    return lista


def _json_estricto(valor, columna, **opciones):
    """El texto JSON de una columna de la tabla (`parametros`, `puntos` o `piso`), o `PlacaMensualError` -- y no se escribe nada -- si `valor` no cabe en JSON VÁLIDO. `json.dumps` escribe NaN e infinito como
    `NaN` e `Infinity`, que no son JSON (SQLite `json_valid` da 0 y un lector estricto los rechaza), y no serializa un escalar de numpy: sin esto un sexto clic con NaN o un parámetro no finito llegaban a la base
    como una columna que la tabla documenta como JSON y no se puede leer de vuelta (D1-PROD-03). La ÚNICA puerta por la que se escriben las tres."""
    try:
        return json.dumps(valor, allow_nan=False, **opciones)
    except (TypeError, ValueError) as error:
        raise PlacaMensualError(f"lo que se guarda en la columna '{columna}' no es JSON válido ({error}): hay un número no finito (NaN o infinito) o un valor que JSON no admite") from error


def motivo_para_no_guardar(resultado, capa):
    """La ÚNICA definición de cuándo un análisis NO se guarda por lo que midió (decisión del físico del 20-10-2026, que revierte D1-D3): si la capa elegida no es medible, por el motivo que sea,
    devuelve el texto con que se rechaza (nombra la capa y trae el estado del motor tal cual); si se puede guardar, None. Medible = el estado de esa capa es «ok»: sus dos perfiles medidos, con los dos
    FWHM y los cuatro desfases; una penumbra incompleta no la vuelve no medible (la penumbra no se guarda). La usan `guardar` y la ventana, antes de ofrecer «Guardar». `capa`: R, G o B."""
    estado = motor.valores_medidos(resultado, capa)["estado"]
    if estado == "ok":
        return None
    return f"la capa {ADJETIVO_DE_LA_CAPA[capa]} no es medible y no se guarda, sea cual sea el motivo; el análisis dice «{estado}»"


def guardar(ref, usuario, datos, nombre, puntos, parametros, capa, modo_piso, punto_manual=None, referencia_virgen=None):
    """Guarda el análisis de la película de un control y devuelve el `id` nuevo. ANALIZA desde los bytes y los clics (ver el docstring del módulo). Rechaza con `PlacaMensualError` (que es un `ValueError`) y SIN
    escribir nada: ref que no es un control, usuario, capa que no es R, G ni B, modo del piso que no existe, imagen vacía o que no se lee, puntos que no son los cinco, parámetros incompletos, un punto marcado
    con un modo que no es «punto_manual», un análisis que no llegó a tomar el piso, lo que no cabe en JSON válido (un número no finito, NaN o infinito, o un escalar de numpy, en los parámetros o en el punto
    marcado: las columnas `parametros`, `puntos` y `piso` se escriben solo por `_json_estricto`), una capa elegida que no es medible (`motivo_para_no_guardar`); y `ControlNoEditable` si el control
    está anulado o no existe (W1).

    `ref`: el id del control (`controles.id`). `datos`: los bytes de la imagen tal como se subió (bytes o bytearray). `nombre`: el nombre del archivo (se guarda sin la carpeta). `puntos`: los CINCO CLICS (x, y)
    en cualquier orden: aquí se refinan. `parametros`: los `P` con que se mide (TODOS los de `analisisImagenes.placa_mensual.VALORES_DE_LA_GEOMETRIA`, incluida la base de la medida: si falta uno se rechaza, porque el motor lo rellenaria con el valor de hoy y lo guardado dejaria de
    reproducirse si ese valor cambia; se guardan y al reabrir se recalcula con ESTOS).
    `capa`: la que el físico reporta (`R`, `G` o `B`, mayúscula exacta; el gris no se ofrece), SIN valor por omisión. `modo_piso`: «automatico», «punto_manual» o «virgen», SIN valor por omisión;
    `punto_manual` (x, y) es el sexto clic del modo «punto_manual»; `referencia_virgen` es la `ReferenciaVirgen` del modo «virgen». Si la capa elegida no es medible, por el motivo que sea, no se guarda.

    UNA transacción (`reemplazar_bloque`): anula el análisis vigente del control, inserta el nuevo y escribe UNA fila de auditoría (`guardar`, o `reemplazo` si había uno, con el `id` de la reemplazada)."""
    ref = _ref_valido(ref)
    if usuario is None or not str(usuario).strip():
        raise PlacaMensualError("falta el usuario que guarda el análisis")
    if not (isinstance(capa, str) and capa in CAPAS):
        raise PlacaMensualError(f"la capa que se reporta debe ser {', '.join(CAPAS[:-1])} o {CAPAS[-1]} (sin valor por omisión: decide qué se guarda), no {capa!r}")
    if modo_piso not in MODOS_DEL_PISO:
        raise PlacaMensualError(f"el modo del piso debe ser uno de {', '.join(MODOS_DEL_PISO)} (sin valor por omisión: decide el número), no {modo_piso!r}")
    if not isinstance(datos, (bytes, bytearray)) or not datos:
        raise PlacaMensualError("falta la imagen")
    if not isinstance(parametros, dict):
        raise PlacaMensualError("los parámetros del análisis son un diccionario (VALORES_DE_LA_GEOMETRIA)")
    faltan = [k for k in motor.VALORES_DE_LA_GEOMETRIA if k not in parametros]          # el diccionario ENTERO, no solo lo que `analizar` lee por nombre: el motor rellena el resto con el valor de HOY (D1-PROD-02)
    if faltan:
        raise PlacaMensualError(f"a los parámetros les faltan {faltan}")
    clics = _cinco_puntos(puntos)
    imagen = bytes(datos)
    try:
        pelicula = leer_pelicula(imagen)
        tam_mm = escala_mm(pelicula.dpi, parametros)
        marcas = [motor.refinar_marca(pelicula.gris, clic, parametros, tam_mm, pelicula.validos) for clic in clics]
        resultado = motor.analizar(pelicula, marcas, parametros, modo_piso=modo_piso, punto_manual=punto_manual, referencia_virgen=referencia_virgen)
    except ValueError as error:
        raise PlacaMensualError(str(error)) from error
    if resultado.piso is None:
        raise PlacaMensualError(motivo_para_no_guardar(resultado, capa))
    valores = motor.valores_medidos(resultado, capa)
    faltan = [n for n in _columnas_de_las_medidas() if n not in valores]
    if faltan:
        raise PlacaMensualError(f"MEDIDAS_GUARDADAS pide {faltan}, que el motor no entrega en valores_medidos")
    piso = resultado.piso.como_dict()
    nombre_del_archivo = _nombre_de_archivo(nombre)
    fila = {
        "ref": ref, "imagen": imagen, "nombre_archivo": nombre_del_archivo, "sha256": hashlib.sha256(imagen).hexdigest(), "formato": pelicula.formato or None, "bits": pelicula.bits,
        "transparentes": pelicula.transparentes, "dpi_declarado": pelicula.dpi, "clase_resolucion": clase_resolucion(pelicula.dpi, parametros), "tamano_pixel_mm": resultado.tam_mm,
        "version": resultado.version, "parametros": _json_estricto(resultado.parametros, "parametros", sort_keys=True), "puntos": _json_estricto(list(resultado.marcas), "puntos"),
        "piso": _json_estricto(piso, "piso", sort_keys=True),
        "capa": capa, "usuario": usuario, "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    fila.update({n: valores[n] for n in _columnas_de_las_medidas()})
    motivo = motivo_para_no_guardar(resultado, capa)          # después de armar la fila (lo que no cabe en JSON se dice como tal) y ANTES de W1 y de la transacción
    if motivo is not None:
        raise PlacaMensualError(motivo)
    if not puede_editarse(ref):
        raise ControlNoEditable(mensaje_bloqueo_edicion(ref))
    with Conexion().conectar() as db:
        cursor = db.cursor()
        cursor.execute(f"SELECT id FROM analisis_placa_mensual WHERE ref = ?{filtro_activo('analisis_placa_mensual')} ORDER BY id DESC", (ref,))
        previa = cursor.fetchone()
        detalle = f"control {ref}; {nombre_del_archivo or 'sin nombre de archivo'}; {resultado.version}; {TEXTO_DE_LA_CAPA_EN_LA_AUDITORIA.format(capa)}; {texto_breve_del_piso(piso, capa)}"
        if previa is not None:
            detalle += f"; reemplaza id={previa[0]}"
        reemplazar_bloque(cursor, TABLA, [("ref", ref)], sql_insert(), [tuple(fila[c] for c in _columnas_de_la_fila())], usuario, ref=ref, detalle=detalle,
                          accion=ACCION_REEMPLAZO if previa is not None else ACCION_GUARDAR)
        nuevo_id = cursor.lastrowid
        db.commit()
    return nuevo_id


def leer(ref):
    """El análisis VIGENTE del control `ref` como un diccionario con todas las columnas (con los bytes de la imagen, `activo`, y `parametros`, `puntos` y `piso` ya convertidos de JSON), o None si el
    control no tiene ninguno. Por la clave de bloque `ref`: filtra la vigencia (DA-47)."""
    with Conexion().conectar() as db:
        cursor = db.cursor()
        cursor.execute(f"SELECT {_columnas_de_lectura()} FROM analisis_placa_mensual WHERE ref = ?{filtro_activo('analisis_placa_mensual')} ORDER BY id DESC", (ref,))
        fila = cursor.fetchone()
        if fila is None:
            return None
        registro = {descripcion[0]: valor for descripcion, valor in zip(cursor.description, fila)}
    for columna in _COLUMNAS_JSON:
        registro[columna] = json.loads(registro[columna])
    return registro


def recalcular(registro):
    """Vuelve a medir lo guardado (`registro`: lo que devuelve `leer`) -> `ResultadoPlacaMensual`. Con la imagen, los puntos YA refinados (no se vuelve a refinar), los parámetros y el modo del piso
    GUARDADOS, el punto marcado y la copia de la referencia virgen (`referencia_virgen_desde_dict`) del propio registro: NUNCA la referencia vigente del archivo ni los parámetros de hoy (DA-81: la copia
    guardada manda). `PlacaMensualError` si la imagen o la referencia guardadas ya no se pueden leer."""
    piso = registro["piso"]
    try:
        referencia = None if piso.get("referencia_virgen") is None else referencia_virgen_desde_dict(piso["referencia_virgen"])
        punto = None if piso.get("punto") is None else tuple(piso["punto"])
        return motor.analizar(leer_pelicula(registro["imagen"]), registro["puntos"], registro["parametros"], modo_piso=piso["modo"], punto_manual=punto, referencia_virgen=referencia)
    except ValueError as error:
        raise PlacaMensualError(str(error)) from error


def _iguales(guardado, recalculado):
    if guardado is None or recalculado is None:
        return guardado is None and recalculado is None
    if isinstance(guardado, numbers.Real) and isinstance(recalculado, numbers.Real) and not isinstance(guardado, bool) and not isinstance(recalculado, bool):
        return abs(guardado - recalculado) <= TOLERANCIA_AL_RECALCULAR
    return guardado == recalculado


def diferencias(registro, resultado):
    """Lo recalculado (`resultado`, de `recalcular`) contra lo guardado (`registro`): una lista de textos, vacía si no hay ninguna diferencia. Compara la versión del motor, cada valor de
    `MEDIDAS_GUARDADAS` de la capa guardada y TAMBIÉN el piso: el modo y, por capa (R, G, B y el gris), su estado y su valor. Un valor que aparece o desaparece es una diferencia. Lo numérico se
    compara a `TOLERANCIA_AL_RECALCULAR`. Sin símbolos de correcto o incorrecto (DA-18)."""
    encontradas = []
    if registro["version"] != resultado.version:
        encontradas.append(f"versión del motor: guardada {registro['version']}, recalculada {resultado.version}")
    nuevos = motor.valores_medidos(resultado, registro["capa"])
    for nombre in _columnas_de_las_medidas():
        if not _iguales(registro.get(nombre), nuevos.get(nombre)):
            encontradas.append(f"{nombre}: guardado {registro.get(nombre)!r}, recalculado {nuevos.get(nombre)!r}")
    guardado = registro["piso"]
    if resultado.piso is None:
        encontradas.append(f"piso: guardado {guardado.get('estado')!r}, recalculado sin piso")
        return encontradas
    if guardado.get("modo") != resultado.piso.modo:
        encontradas.append(f"modo del piso: guardado {guardado.get('modo')!r}, recalculado {resultado.piso.modo!r}")
    for capa in CAPAS_DEL_PISO:
        viejo, nuevo = guardado["capas"].get(capa, {}), resultado.piso.capas[capa]
        if viejo.get("estado") != nuevo.estado:
            encontradas.append(f"piso (capa {ADJETIVO_DE_LA_CAPA[capa]}), estado: guardado {viejo.get('estado')!r}, recalculado {nuevo.estado!r}")
        if not _iguales(viejo.get("mediana"), nuevo.mediana):
            encontradas.append(f"piso (capa {ADJETIVO_DE_LA_CAPA[capa]}), valor: guardado {viejo.get('mediana')!r}, recalculado {nuevo.mediana!r}")
    return encontradas
