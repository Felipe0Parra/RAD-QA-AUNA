"""CD.9 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, DA-92, DA-93): que no vuelva a haber DOS. La curva de dosis de las películas tiene sus «una sola» (el bloque CD.9 del plan); cada una se puede
romper en silencio en una tarea futura (alguien convierte a dosis «para probar» en otro módulo, una ventana pasa a leer la curva vigente al reabrir, el PDF arma su propia tabla, alguien escribe
«100 mm» a mano...). Aquí cada una es un TRIPWIRE derivado del ÁRBOL de producción (AST), como PI.10 (`test_pi10_tripwires_posicion_inicial.py`): cada guarda es una función pura sobre
`{ruta: (texto, árbol)}` que se corre sobre el árbol real (debe salir limpia) y sobre fuentes fabricadas (debe señalar el sitio).

  1. UNA SOLA CONVERSIÓN entre netOD y dosis. (a) Fuera de `analisisImagenes/curva_dosis.py` nadie importa ni usa un nombre PRIVADO del motor de la curva (los privados se leen del propio motor:
     sus definiciones de módulo con «_» y los métodos con «_» de sus clases); (b) nadie fuera del motor eleva a la potencia del modelo (`x ** n`, `x **= n`, `pow(x, n)`, `np.power(x, n)`...: el exponente
     se reconoce escrito como sea) ni hace cuentas con sus parámetros `a`, `b`, `n` (en los módulos del plan solo se pueden ESCRIBIR, dentro de un f-string: la tabla de la curva de la ventana de calibración).
  2. UNA SOLA REGLA de la base por capa, de la curva efectiva, del botón y de lo guardado en dosis: `base_de_la_capa`, `curva_de_la_capa`, `curva_efectiva`, `se_puede_pasar_a_dosis` y
     `valores_medidos_en_dosis` (el motor de la placa), `filas_de_la_capa_reportada` (su dibujo) y `curva_guardada`, `recalcular_en_dosis` y `diferencias_en_dosis` (su servicio) se definen UNA vez,
     en su módulo, y solo las llaman los sitios declarados (también si se importan con otro nombre: `from m import regla as _otra`); una `CurvaEfectiva` solo se construye en el motor, desde la copia
     guardada (el servicio) o como el motivo de un fallo de lectura (la ventana).
  3. LAS DOS VENTANAS (la de calibración y la mensual) SIN SQL.
  4. AL REABRIR, la curva es la COPIA guardada: (a) el servicio de la curva (`services/curva_dosis.py`) solo lo usan la ventana de calibración y, para la curva VIGENTE de una película nueva,
     `_leer_la_curva` de la ventana mensual; (b) `_leer_la_curva` empieza por la guarda «con un registro a la vista no se busca»; (c) `abrir_guardado` toma la curva de `svc.curva_guardada` y no
     busca la vigente; (d) el servicio de la placa y la sección del PDF no importan el servicio de la curva; (e) solo el servicio de la curva y el esquema escriben SQL sobre las tablas de las
     calibraciones, y nadie más usa sus nombres de tabla.
  5. NINGÚN TEXTO de la ventana mensual, su dibujo ni su PDF escribe una base a mano (el nombre de la base sale de `motor.BASE_*`), ni compara una base con un literal, ni escribe «cGy» fuera de «[cGy]».
  6. DA-93: (a) los rótulos de `filas_de_la_capa_reportada` no se copian en otro módulo (la tabla es UNA); (b) el cuadrado perfecto es `LADO_DEL_CUADRADO_PERFECTO_MM` (una definición; las
     funciones del cuadrado la usan y no escriben 100 ni 50; ningún texto dice «100 mm»); (c) el cuadro «Info» no crea textos: recibe los widgets de `EXPLICACIONES_EN_LA_INFO`, cada uno de la
     ventana; (d) ningún perfil del gris: el gris solo aparece en los sitios declarados (la película virgen, las bandas y el marco de la imagen, el refinado de los clics, el color de cada capa), y ni
     una estructura de capas que lo lleve ni el dict `.capas` de un resultado se RECORREN (se indexan: `COLOR_CAPA[capa]`, `resultado.capas[capa]`); las estructuras se LEEN del árbol.
     (e) DA-94: ninguna curva de la capa gris en la parte de dosis: el motor y el servicio de la curva, su dibujo, su ventana y la sección del PDF no nombran el gris ni una estructura de capas que lo
     lleve (`CAPAS_DEL_PISO`, `CAPAS_QUE_LA_VIRGEN_NO_PUEDE_TENER_MAS_OSCURAS`... leídas del árbol), y el motor mensual y su dibujo no piden a una curva el estado, el rango, la dosis, la netOD, la
     incertidumbre ni la capa del gris, ni recorriendo algo que lo traiga (tampoco por un alias local) (sin excepciones).
  7. EL EMPAQUETADO: los cuatro módulos nuevos del plan están UNA vez en `hidden_imports` de `build_exe.py` (leído por AST), los módulos del plan no usan `importlib` ni `__import__`, y nadie nombra
     un módulo nuevo en un texto (una importación por nombre que PyInstaller no ve).
  8. UNA SOLA CONVERSIÓN DE PPP A MM: en los módulos del plan solo `pelicula.escala_mm` divide entre 25.4 (como vigila PI.10 para los suyos).
  9. UN SOLO LLAMADOR DEL AJUSTE CON PARÁMETROS: `ajustar` del motor de la curva lo llaman `guardar` y `_ajustar_como_al_guardar` del servicio, con `P=` (ya validado por
     `_parametros_de_la_curva`), y la vista previa de la ventana de calibración (`_ajustar`), SIN `P` (los de fábrica): con un `P` de otro tipo `ajustar` lanza `TypeError` (su docstring dice «NUNCA
     lanza por el contenido»), y ese contrato solo es cierto mientras nadie más le pase `P`.

Cada guarda tiene (i) su COMPUERTA DE NO VACUIDAD por archivo (Trampa 8: sin ella pasaría en vacío si el árbol cambiara de forma), (ii) su CASO SINTÉTICO que la hace caer y que nombra el sitio y
(iii) sus EXCEPCIONES declaradas con su motivo, con una prueba que exige que cada excepción siga existiendo en el árbol (una excepción que ya no hace falta se retira: la lista no se pudre).
Dos reglas de forma (ronda 1 de revisión, hallazgos CD9-REV-AMB-1 a 6): (1) un nombre se reconoce COMO SEA que se escriba (`from m import f as g`, `import a.b.c`, `from . import m`, `_otra = m.f`):
todas las guardas por módulo o por función resuelven por `_enlaces`/`_destinos`; (2) una excepción se declara por SITIO, nunca por «todo el nivel de módulo»: lo que está fuera de toda función nombra su
enunciado (`=COLOR_CAPA`, `(import)`, `class X`, `(módulo)`).
Las guardas por archivo que ya viven en las pruebas de CD.3, CD.5, CD.7 y CD.8 (sin SQL, sin Qt, el empaquetado de sus módulos, la sección sin la curva vigente) se quedan donde están: estas son
las del ÁRBOL entero. Solo lee fuentes: no importa la producción, no abre la base ni Qt."""
import ast
import os
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
EXCLUIDOS = {".venv", "build", "dist", "tests", "__pycache__", ".git", "node_modules", ".pytest_cache"}

MOTOR_CURVA = "analisisImagenes/curva_dosis.py"                         # CD.3: el motor de la curva (el modelo de Devic)
DIBUJO_CURVA = "analisisImagenes/dibujo_curva_dosis.py"                  # CD.5: el dibujo de la ventana de calibración
SERVICIO_CURVA = "services/curva_dosis.py"                              # CD.4: la única puerta a las tablas de las calibraciones
VENTANA_CURVA = "ui/paginasControles/PruebasMensuales/curva_dosis.py"    # CD.5: la ventana de calibración
MOTOR_PLACA = "analisisImagenes/placa_mensual.py"                        # CD.6: la base dosis en el motor mensual
DIBUJO_PLACA = "analisisImagenes/dibujo_placa_mensual.py"                # CD.7: el dibujo de la ventana mensual
SERVICIO_PLACA = "services/placa_mensual.py"                             # CD.6b: la dosis guardada y la copia de la curva
MEDIDAS = "services/medidas_placa_mensual.py"                           # CD.6b: lo que se guarda
VENTANA_PLACA = "ui/paginasControles/PruebasMensuales/placa_mensual.py"  # CD.7: la ventana mensual
SECCION_PDF = "models/PDF/Mensuales/seccion_placa_mensual.py"            # CD.8: la sección del PDF mensual
PELICULA = "analisisImagenes/pelicula.py"                               # CD.2: la pieza y `escala_mm`
ESQUEMA = "data/ManejoDatos/conection.py"                               # CD.4: las dos tablas
BUILD = "build_exe.py"

MODULO_MOTOR_CURVA = "analisisImagenes.curva_dosis"
MODULO_SERVICIO_CURVA = "services.curva_dosis"
MODULO_SERVICIO_PLACA = "services.placa_mensual"
MODULOS_NUEVOS = (MOTOR_CURVA, DIBUJO_CURVA, SERVICIO_CURVA, VENTANA_CURVA)          # la zona verde del §4 del plan
MODULOS_DEL_PLAN = MODULOS_NUEVOS + (PELICULA, MOTOR_PLACA, DIBUJO_PLACA, SERVICIO_PLACA, MEDIDAS, VENTANA_PLACA, SECCION_PDF)
VISTA_MENSUAL = (DIBUJO_PLACA, VENTANA_PLACA, SECCION_PDF)                          # lo que se ve de un análisis mensual: la ventana, su dibujo y su PDF
VENTANAS = (VENTANA_CURVA, VENTANA_PLACA)
EMPAQUETADOS_POR_CD7 = ("ui.paginasControles.PruebasMensuales.placa_mensual", "analisisImagenes.dibujo_placa_mensual")


def _punteado(ruta):
    return ruta[:-3].replace("/", ".")


# --- las EXCEPCIONES declaradas, cada una con su motivo (una excepción sin motivo es una puerta abierta) ---------------------------------------------------------------------------------------
PRIVADOS_PERMITIDOS = {
    (MOTOR_PLACA, "_texto_de_la_cadena"): "H-CD9-2 (deuda de CD.6): el motor de la placa escribe con él la cadena de captura en el motivo de la condición 3 («la película se escaneó con otra "
                                          "cadena: ...»); es TEXTO, no evalúa el modelo. Se retira cuando la primera tarea que edite el motor de la curva la haga pública (CD9-D3)",
}
LLAMADORES_PERMITIDOS = {
    "base_de_la_capa": {},
    "curva_de_la_capa": {
        (DIBUJO_PLACA, "dibujar_perfil"): "CD.7 (DC9): el perfil en dosis dibuja los niveles con la curva de SU capa",
        (DIBUJO_PLACA, "_capa_en_dosis"): "CD.7 (DC9): la capa de la pestaña 2 en dosis, píxel a píxel, con la curva de SU capa"},
    "curva_efectiva": {
        (VENTANA_PLACA, "_leer_la_curva"): "CD.7 (DC7): la curva vigente de una película NUEVA (con un registro a la vista no se llama: guarda 4b)"},
    "se_puede_pasar_a_dosis": {
        (VENTANA_PLACA, "_regla_de_la_dosis"): "CD.7 (DA-92): el botón «Ver en dosis»",
        (SERVICIO_PLACA, "_la_dosis"): "CD.6b (DC16): al guardar, la MISMA regla del botón decide si también se guarda la dosis"},
    "valores_medidos_en_dosis": {
        (SERVICIO_PLACA, "_la_dosis"): "CD.6b (DC16): lo que se guarda en dosis",
        (SERVICIO_PLACA, "diferencias_en_dosis"): "CD.6b: al reabrir, lo recalculado en dosis contra lo guardado"},
    "filas_de_la_capa_reportada": {
        (VENTANA_PLACA, "_aplicar_la_regla"): "CD.7 (DA-93): la tabla de la pestaña 1",
        (SECCION_PDF, "_filas_nuevas"): "CD.8 (DA-93): la tabla de valores del PDF, la MISMA"},
    "curva_guardada": {
        (VENTANA_PLACA, "abrir_guardado"): "CD.6b (DA-81): al reabrir, la copia guardada",
        (VENTANA_PLACA, "_al_guardar"): "CD.6b (DA-81): tras guardar, la ventana pasa a ser el registro y usa su copia",
        (SECCION_PDF, "texto_de_la_curva"): "CD.8 (DC12): la línea de la curva del PDF, de la copia"},
    "recalcular_en_dosis": {
        (VENTANA_PLACA, "_medir_en_dosis"): "CD.6b: un registro a la vista se mide en dosis con su copia",
        (SECCION_PDF, "reconstruir_en_dosis"): "CD.8: el PDF en dosis, con la copia"},
    "diferencias_en_dosis": {
        (VENTANA_PLACA, "_al_ver_en_dosis"): "CD.6b: avisa si lo recalculado en dosis no da lo guardado",
        (SECCION_PDF, "reconstruir_en_dosis"): "CD.8: el PDF no imprime en dosis lo que no da lo guardado"},
}
REGLAS = {"base_de_la_capa": MOTOR_PLACA, "curva_de_la_capa": MOTOR_PLACA, "curva_efectiva": MOTOR_PLACA, "se_puede_pasar_a_dosis": MOTOR_PLACA, "valores_medidos_en_dosis": MOTOR_PLACA,
          "filas_de_la_capa_reportada": DIBUJO_PLACA, "curva_guardada": SERVICIO_PLACA, "recalcular_en_dosis": SERVICIO_PLACA, "diferencias_en_dosis": SERVICIO_PLACA}
CONSTRUCTORES_DE_LA_CURVA_EFECTIVA = {
    (SERVICIO_PLACA, "_leer_la_copia"): "CD.6b (revision): la UNICA lectura de la copia guardada (la llama curva_guardada)",
    (VENTANA_PLACA, "_leer_la_curva"): "CD.7: si no se pudieron leer las calibraciones, una curva vacía con el motivo (sin curva)",
}
USOS_DEL_SERVICIO_DE_LA_CURVA = {
    (VENTANA_CURVA, "*"): "CD.5: la ventana de calibración ES la interfaz de las calibraciones (guardar, listar, leer, recalcular, anular): el archivo entero",
    (VENTANA_PLACA, "(import)"): "CD.7: la ventana mensual importa el servicio de la curva, en una sentencia de nivel de módulo (solo lo llama `_leer_la_curva`; lo demás de nivel de módulo o del cuerpo de una clase NO está declarado: CD9-REV-AMB-4)",
    (VENTANA_PLACA, "_leer_la_curva"): "CD.7 (DC7): la lista de las calibraciones vigentes y válidas para la curva de una película NUEVA",
}
SQL_DE_LAS_CALIBRACIONES = {
    SERVICIO_CURVA: "CD.4: la única puerta a las dos tablas",
    ESQUEMA: "CD.4: el CREATE TABLE de las dos tablas",
}
BASES_ESCRITAS_PERMITIDAS = {
    (DIBUJO_PLACA, "texto_de_la_base"): "OD.1: la ÚNICA frase que explica cada base; elige la frase con `motor.BASE_*` y la fórmula nombra la base que explica",
    # CD.8 (01-11, H-CD9-4): `_meseta_de_la_capa` ya no esta: arma el rotulo con `motor.BASE_DENSIDAD_OPTICA` (CD9-D4 superada)
}
GRIS_PERMITIDO = {
    (DIBUJO_PLACA, "=COLOR_CAPA"): "el color de cada capa (`COLOR_CAPA`, un dict que se INDEXA: `COLOR_CAPA[capa]`), que usan las tablas y la zona de la película virgen (sus cuatro capas). Es lo ÚNICO de nivel de módulo "
                                   "que puede llevar el gris (CD9-REV-AMB-1: antes la excepción era «todo el nivel de módulo del dibujo»)",
    (DIBUJO_PLACA, "nombre_de_la_capa"): "el nombre «Gris» de una capa, para las tablas de la película virgen",
    (DIBUJO_PLACA, "filas_de_la_virgen"): "la tabla de la película virgen: su piso tiene las cuatro capas (A.3, OD.1)",
    (DIBUJO_PLACA, "filas_de_la_uniformidad"): "la tabla de uniformidad y ruido de la película virgen (las cuatro capas)",
    (DIBUJO_PLACA, "_bandas_de_los_perfiles"): "las filas de la banda de 1 mm de los perfiles, para dibujarla SOBRE LA IMAGEN (DC9: la imagen con lo dibujado no sigue a la base); toma las filas del "
                                               "primer perfil que haya, empezando por el del gris, que el motor sigue midiendo",
    # CD.5b (01-11, DA-94): `eje_de_la_dosis` ya no esta: cuenta solo las capas de la curva (`CAPAS_DE_LA_CURVA`), H-CD9-9 y PC-1 cerradas
    (DIBUJO_PLACA, "dibujar_geometria"): "el tamaño del marco girado (`girada.capas[\"gris\"].shape`), para dibujar las bandas sobre la imagen; no es un perfil",
    (VENTANA_PLACA, "_refinar"): "los clics se refinan sobre la imagen gris (`motor.refinar_marca(pelicula.gris, ...)`): el motor la sigue midiendo (DA-93)",
}
LLAMADORES_DE_AJUSTAR = {
    (SERVICIO_CURVA, "guardar"): ("con P", "CD.4: el ajuste que se guarda, con los parámetros del encabezado ya validados"),
    (SERVICIO_CURVA, "_ajustar_como_al_guardar"): ("con P", "CD.4: el reajuste desde lo guardado, con `_parametros_de_la_curva` de la copia"),
    (VENTANA_CURVA, "_ajustar"): ("sin P", "H-CD9-1: CD.5, la vista previa del formulario antes de guardar: ajusta con los parámetros de FÁBRICA (sin `P`), el mismo camino que mide `guardar`; "
                                          "sin `P` no puede lanzar `TypeError`"),
}
DIVISIONES_DE_25_4_PERMITIDAS = {
    (PELICULA, "escala_mm"): "la ÚNICA función que vuelve una resolución en escala (PI.10, CD.2)",
}
FUNCIONES_DE_POTENCIA = ("pow", "power", "float_power", "__pow__")          # `pow(x, n)`, `math.pow`, `np.power`, `np.float_power`, `x.__pow__(n)`: la potencia escrita como una llamada
PALABRAS_DEL_EXPONENTE = ("exp", "x2", "exponent", "other")                  # el exponente dado por nombre: `pow(x, exp=n)`, `np.power(x, x2=n)`
TEXTOS_DEL_CUADRADO = re.compile(r"\b100(?:\.0)?\s*mm\b")
FUNCIONES_DEL_CUADRADO = re.compile(r"cuadra(?:do|tura)")          # filas_de_la_cuadratura, cuadrado_perfecto, dibujar_cuadratura: las que dicen o dibujan el cuadrado perfecto
NUMEROS_DEL_CUADRADO = (100, 50)                         # el lado y su mitad, escritos a mano


# ------------------------------------------------------------------------------------------------------------------ el árbol de producción

def _cargar_produccion():
    fuentes = {}
    for carpeta, subcarpetas, archivos in os.walk(RAIZ):
        subcarpetas[:] = [s for s in subcarpetas if s not in EXCLUIDOS]
        for nombre in archivos:
            if nombre.endswith(".py"):
                ruta = Path(carpeta) / nombre
                texto = ruta.read_text(encoding="utf-8", errors="replace")
                try:
                    fuentes[str(ruta.relative_to(RAIZ)).replace(os.sep, "/")] = (texto, ast.parse(texto, str(ruta)))
                except SyntaxError:
                    pass
    return fuentes


# Trampa 8, POR ARCHIVO: cada archivo que una guarda vigila existe y tiene cuerpo. {ruta: (motivo, mínimo de funciones)}: el mínimo es la MITAD de las que tenía el 01-11 (b5abfa8 con CD.6b y CD.8).
ARCHIVOS_VIGILADOS = {
    MOTOR_CURVA: ("el motor de la curva: sus privados (guarda 1) y `ajustar` (guarda 9)", 15),
    DIBUJO_CURVA: ("el dibujo de la calibración: escribe los parámetros de la curva (guarda 1b)", 9),
    SERVICIO_CURVA: ("la única puerta a las calibraciones (guardas 4 y 9)", 18),
    VENTANA_CURVA: ("la ventana de calibración: sin SQL, la vista previa del ajuste (guardas 3 y 9)", 18),
    MOTOR_PLACA: ("el motor de la placa: las reglas de la base, del botón y de lo guardado en dosis (guarda 2)", 50),
    DIBUJO_PLACA: ("el dibujo de la ventana mensual: la tabla de la capa reportada, el cuadrado, los textos y el gris (guardas 2, 5 y 6)", 37),
    SERVICIO_PLACA: ("el servicio de la placa: la copia guardada de la curva (guardas 2 y 4)", 10),
    VENTANA_PLACA: ("la ventana mensual: sin SQL, la curva al reabrir, el cuadro «Info» (guardas 3, 4 y 6)", 43),
    SECCION_PDF: ("la sección del PDF mensual: la misma tabla y la copia de la curva (guardas 2, 4, 5 y 6)", 7),
    PELICULA: ("la pieza y la única conversión de ppp a mm (guarda 8)", 58),
    ESQUEMA: ("el CREATE TABLE de las calibraciones (guarda 4e)", 25),
}
ARCHIVOS_SIN_FUNCIONES = {MEDIDAS: "la lista de lo que se guarda (constantes)", BUILD: "`hidden_imports` (guarda 7)"}


@pytest.fixture(scope="module")
def produccion():
    fuentes = _cargar_produccion()
    assert len(fuentes) >= 100, f"el árbol de producción leyó {len(fuentes)} archivos: no está leyendo el árbol"
    return fuentes


class TestNoVacuidadPorArchivo:
    @pytest.mark.parametrize("ruta", sorted(ARCHIVOS_VIGILADOS))
    def test_el_archivo_vigilado_existe_y_tiene_cuerpo(self, produccion, ruta):
        motivo, minimo = ARCHIVOS_VIGILADOS[ruta]
        assert ruta in produccion, f"{ruta} ya no está en el árbol de producción ({motivo}): la guarda vigilaría nada"
        funciones = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(produccion[ruta][1]))
        assert funciones >= minimo, f"{ruta} tiene {funciones} funciones (mínimo {minimo}; {motivo})"

    @pytest.mark.parametrize("ruta", sorted(ARCHIVOS_SIN_FUNCIONES))
    def test_los_archivos_de_constantes_existen_y_no_estan_vacios(self, produccion, ruta):
        assert ruta in produccion and len(produccion[ruta][1].body) >= 2, f"{ruta}: {ARCHIVOS_SIN_FUNCIONES[ruta]}"


# ------------------------------------------------------------------------------------------------------------------ ayudas (puras)

def _con(produccion, ruta, agregado):
    """El árbol real con `agregado` al FINAL de `ruta` (un archivo nuevo si no existe): así un caso sintético usa los mismos alias del módulo real."""
    texto = (produccion[ruta][0] + "\n\n" if ruta in produccion else "") + agregado
    return {**produccion, ruta: (texto, ast.parse(texto))}


def _con_reemplazo(produccion, ruta, viejo, nuevo):
    texto = produccion[ruta][0]
    assert texto.count(viejo) == 1, f"el caso sintético no encuentra UNA vez su ancla en {ruta}: {viejo!r}"
    texto = texto.replace(viejo, nuevo)
    return {**produccion, ruta: (texto, ast.parse(texto))}


def _recordado(que, nodo, calcular):
    """Cada árbol se recorre UNA vez (los casos sintéticos solo cambian UN archivo; el resto del árbol se reusa). La memoria vive EN el nodo (`nodo.__dict__`) y se suelta con el árbol, al terminar el
    módulo: un contenedor de módulo (`_MEMORIA = {}`) retenía los 152 árboles mientras viviera el proceso (356 MB medidos con `b4_medir_caches3.py`) y B.4 exige cerrar o declarar cada cache de módulo
    de las pruebas (Trampa 10: nada que sobreviva al módulo ni dependa del orden)."""
    memoria = nodo.__dict__.setdefault("_memoria_cd9", {})
    if que not in memoria:
        memoria[que] = calcular(nodo)
    return memoria[que]


def _nodos(arbol):
    return _recordado("nodos", arbol, lambda a: list(ast.walk(a)))


def _funcion_contenedora(arbol):
    return _recordado("contenedora", arbol, _calcular_contenedora)


def _sitio_del_enunciado(enunciado):
    """El sitio de lo que hay en un enunciado de NIVEL DE MÓDULO fuera de toda función: el nombre que asigna («=COLOR_CAPA»), «(import)», «class X» o «(módulo)» (cualquier otro enunciado)."""
    if isinstance(enunciado, (ast.Import, ast.ImportFrom)):
        return "(import)"
    if isinstance(enunciado, ast.ClassDef):
        return f"class {enunciado.name}"
    destinos = enunciado.targets if isinstance(enunciado, ast.Assign) else [enunciado.target] if isinstance(enunciado, (ast.AnnAssign, ast.AugAssign)) else []
    nombres = [t.id for t in destinos if isinstance(t, ast.Name)]
    return "=" + ",".join(nombres) if nombres else "(módulo)"


def _calcular_contenedora(arbol):
    """{id(nodo): el sitio del nodo}: la función más interna que lo contiene o, FUERA de toda función, el enunciado de módulo donde está (`_sitio_del_enunciado`). Así cada hallazgo nombra su sitio y una
    excepción se declara por función o por el nombre que se asigna, nunca por «todo el nivel de módulo» (la clave `None` dejaba pasar cualquier cosa de módulo o del cuerpo de una clase: CD9-REV-AMB-1 y 4)."""
    contenedora = {id(arbol): None}

    def visitar(nodo, sitio):
        for hijo in ast.iter_child_nodes(nodo):
            if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                propio = hijo.name
            elif nodo is arbol:
                propio = _sitio_del_enunciado(hijo)
            else:
                propio = sitio
            contenedora[id(hijo)] = propio
            visitar(hijo, propio)

    visitar(arbol, None)
    return contenedora


def _literales(arbol):
    return _recordado("literales", arbol, _calcular_literales)


def _calcular_literales(arbol):
    """[(nodo, texto)] de cada texto que se USA: las constantes y la plantilla de cada f-string (sus partes literales con «{}» en cada hueco). Se saltan las cadenas sueltas (los docstrings)."""
    sueltas = {id(n.value) for n in _nodos(arbol) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
    dentro = {id(x) for f in _nodos(arbol) if isinstance(f, ast.FormattedValue) and f.format_spec is not None for x in ast.walk(f.format_spec)}
    salida = []
    for nodo in _nodos(arbol):
        if isinstance(nodo, ast.JoinedStr) and id(nodo) not in dentro:
            partes = []
            for p in nodo.values:
                if isinstance(p, ast.Constant) and isinstance(p.value, str):
                    partes.append(p.value)
                    dentro.add(id(p))
                else:
                    partes.append("{}")
            salida.append((nodo, "".join(partes)))
    for nodo in _nodos(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and id(nodo) not in sueltas and id(nodo) not in dentro:
            salida.append((nodo, nodo.value))
    return salida


def _paquete_de(ruta):
    """El paquete de un archivo («services/placa_mensual.py» -> «services»), para resolver sus importaciones relativas."""
    return ".".join(ruta[:-3].split("/")[:-1])


def _modulo_importado(n, ruta):
    """El nombre punteado del módulo de un `from ... import`, también si es relativo: `from . import x` en «services/placa_mensual.py» -> «services»; `from .x import y` -> «services.x»; `from .. import z` en
    «ui/paginas/p.py» -> «ui»."""
    if not n.level:
        return n.module or ""
    base = [p for p in _paquete_de(ruta).split(".") if p]
    base = base[:max(len(base) - (n.level - 1), 0)]
    return ".".join(base + ([n.module] if n.module else []))


def _destinos(expresion, enlaces):
    """Los nombres punteados a los que puede apuntar `a.b.c` según las importaciones del archivo: `motor.ajustar` -> {«analisisImagenes.curva_dosis.ajustar»}; vacío si no sale de una importación."""
    if isinstance(expresion, ast.Name):
        return set(enlaces.get(expresion.id, ()))
    if isinstance(expresion, ast.Attribute):
        return {f"{base}.{expresion.attr}" for base in _destinos(expresion.value, enlaces)}
    return set()


def _calcular_enlaces(ruta, arbol):
    enlaces = {}

    def ligar(nombre, destino):
        enlaces.setdefault(nombre, set()).add(destino)

    for n in _nodos(arbol):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.asname:
                    ligar(a.asname, a.name)
                else:
                    ligar(a.name.split(".")[0], a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            modulo = _modulo_importado(n, ruta)
            for a in n.names:
                if a.name != "*":
                    ligar(a.asname or a.name, f"{modulo}.{a.name}" if modulo else a.name)
    alias = [(t.id, n.value) for n in _nodos(arbol) if isinstance(n, ast.Assign) and isinstance(n.value, (ast.Name, ast.Attribute)) for t in n.targets if isinstance(t, ast.Name)]
    for _ in range(3):                  # un alias de un alias (`_otra = motor.regla`, `_mas = _otra`)
        for nombre, valor in alias:
            for destino in _destinos(valor, enlaces):
                ligar(nombre, destino)
    return enlaces


def _enlaces(ruta, arbol):
    """{nombre local: {los nombres punteados a los que apunta}} por TODAS las importaciones del archivo (también las diferidas, dentro de una función) y por los alias de una asignación (`_otra = motor.regla`):
    `import a.b.c` liga «a»; `import a.b as x` liga «x» a «a.b»; `from a import b as y` liga «y» a «a.b» (b es un módulo o un nombre suyo); las relativas se resuelven con el paquete del archivo. Una guarda que
    reconoce un nombre por COMO se escribe en un archivo deja pasar el mismo nombre escrito de otra forma (CD9-REV-AMB-5 y 6): todas las que miran módulos o funciones resuelven por aquí."""
    return _recordado(("enlaces", ruta), arbol, lambda a: _calcular_enlaces(ruta, a))


def _importaciones_de(ruta, arbol, modulo):
    """Las sentencias `import` de `ruta` que traen el módulo `modulo` o un nombre suyo, escritas como sea: `from p import m [as x]`, `from p.m import f`, `import p.m [as x]` y las relativas."""
    salida = []
    for n in _nodos(arbol):
        if isinstance(n, ast.Import):
            if any(a.name == modulo or a.name.startswith(modulo + ".") for a in n.names):
                salida.append(n)
        elif isinstance(n, ast.ImportFrom):
            origen = _modulo_importado(n, ruta)
            if origen == modulo or origen.startswith(modulo + ".") or any(f"{origen}.{a.name}" == modulo for a in n.names):
                salida.append(n)
    return salida


def _importa(ruta, arbol, modulo):
    return bool(_importaciones_de(ruta, arbol, modulo))


def _nombres_llamados(funcion, enlaces):
    """Los nombres con que una llamada puede estar llamando a una función: el que se ve (`regla` en `motor.regla(...)`, `_otra` en `_otra(...)`) y, si ese nombre sale de una importación o de un alias, el de origen."""
    if isinstance(funcion, ast.Attribute):
        return {funcion.attr}
    if isinstance(funcion, ast.Name):
        return {funcion.id} | {destino.rpartition(".")[2] for destino in enlaces.get(funcion.id, ())}
    return set()


def _llamadas_al_modulo(fuentes, ruta, modulo):
    """[(función contenedora, nombre llamado, línea, nodo)] de las llamadas de `ruta` a funciones de `modulo`, escritas como sea: por su alias, por la ruta entera, importadas por nombre o con otro nombre."""
    _, arbol = fuentes[ruta]
    enlaces = _enlaces(ruta, arbol)
    contenedora = _funcion_contenedora(arbol)
    salida = []
    for n in _nodos(arbol):
        if isinstance(n, ast.Call):
            for destino in sorted(_destinos(n.func, enlaces)):
                paquete, _, hoja = destino.rpartition(".")
                if paquete == modulo:
                    salida.append((contenedora.get(id(n)), hoja, n.lineno, n))
    return salida


def _definiciones_de_modulo(arbol):
    nombres = []
    for n in arbol.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nombres.append(n.name)
        elif isinstance(n, ast.Assign):
            nombres += [t.id for t in n.targets if isinstance(t, ast.Name)]
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            nombres.append(n.target.id)
    return nombres


def _texto_de_constante(arbol, nombre):
    for n in arbol.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == nombre for t in n.targets) and isinstance(n.value, ast.Constant):
            return n.value.value
    return None


def _funcion(arbol, nombre):
    encontradas = [n for n in _nodos(arbol) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nombre]
    return encontradas[0] if len(encontradas) == 1 else None


def _orden(hallazgo):
    return tuple("" if x is None else str(x) for x in hallazgo)


def _sin_permitidos(hallados, permitidos):
    """Los hallazgos (ruta, función, línea, ...) que no están declarados, por (ruta, función) (función None: lo de módulo) o por (ruta, "*") para el archivo entero."""
    return sorted((h for h in hallados if (h[0], h[1]) not in permitidos and (h[0], "*") not in permitidos), key=_orden)


def _usados(hallados, permitidos):
    """Las excepciones declaradas que el árbol de hoy SÍ usa: una que ya no aparece se retira (antipodredumbre)."""
    return {k for k in permitidos if any((h[0], h[1]) == k or (k[1] == "*" and h[0] == k[0]) for h in hallados)}


# ======================================================================================================== 0b. las ayudas que resuelven nombres (CD9-REV-AMB-3, 5 y 6)

class TestElResolvedorDeNombres:
    """Las guardas por módulo o por función dependían de COMO se escribía el nombre en cada archivo (el alias de `from m import f as g`, la ruta entera de `import a.b`, la importación relativa): todas
    resuelven ahora por `_enlaces`/`_destinos`, que se prueban aquí por separado y contra los alias reales del árbol (si el estilo de las importaciones cambia y el resolvedor no lo entiende, esto lo dice)."""

    @pytest.mark.parametrize("fuente, ruta, esperado", [
        ("import a.b.c\n", "x/y.py", {"a": {"a"}}),
        ("import a.b.c as m\n", "x/y.py", {"m": {"a.b.c"}}),
        ("from a import b as m\nfrom a.b import f, g as h\n", "x/y.py", {"m": {"a.b"}, "f": {"a.b.f"}, "h": {"a.b.g"}}),
        ("from . import m\nfrom .n import f as g\n", "services/placa_mensual.py", {"m": {"services.m"}, "g": {"services.n.f"}}),
        ("from .. import m\nfrom ..n import f\n", "ui/paginas/p.py", {"m": {"ui.m"}, "f": {"ui.n.f"}}),
        ("from . import m\n", "raiz.py", {"m": {"m"}}),
        ("from a import b\n_c = b.f\n_d = _c\ndef g():\n    _e = _d.h\n", "x/y.py", {"b": {"a.b"}, "_c": {"a.b.f"}, "_d": {"a.b.f"}, "_e": {"a.b.f.h"}}),
        ("def f():\n    import a.b as m\n    from c import d\n", "x/y.py", {"m": {"a.b"}, "d": {"c.d"}}),
    ], ids=["ruta_entera", "con_alias", "desde_un_paquete", "relativa_de_un_paquete", "relativa_de_dos_niveles", "relativa_sin_paquete", "alias_de_asignacion", "importacion_diferida"])
    def test_resuelve_cada_forma_de_importar(self, fuente, ruta, esperado):
        enlaces = _enlaces(ruta, ast.parse(fuente))
        assert {k: v for k, v in enlaces.items() if k in esperado} == esperado, enlaces

    @pytest.mark.parametrize("expresion, esperado", [("motor.ajustar", {"analisisImagenes.curva_dosis.ajustar"}), ("analisisImagenes.curva_dosis.ajustar", {"analisisImagenes.curva_dosis.ajustar"}),
                                                     ("_a", {"analisisImagenes.curva_dosis.ajustar"}), ("otro.nada", set()), ("f().x", set())])
    def test_destinos(self, expresion, esperado):
        enlaces = _enlaces("x/y.py", ast.parse("import analisisImagenes.curva_dosis\nfrom analisisImagenes import curva_dosis as motor\nfrom analisisImagenes.curva_dosis import ajustar as _a\n"))
        assert _destinos(ast.parse(expresion, mode="eval").body, enlaces) == esperado

    def test_los_alias_reales_del_arbol_se_resuelven(self, produccion):
        """No vacuidad: las guardas del árbol real cuentan con estas resoluciones (la ventana mensual importa `motor`, `svc`, `svc_curva`...)."""
        enlaces = _enlaces(VENTANA_PLACA, produccion[VENTANA_PLACA][1])
        assert enlaces["motor"] == {"analisisImagenes.placa_mensual"} and enlaces["svc"] == {MODULO_SERVICIO_PLACA} and enlaces["svc_curva"] == {MODULO_SERVICIO_CURVA}, enlaces
        assert _enlaces(SECCION_PDF, produccion[SECCION_PDF][1])["motor"] == {"analisisImagenes.placa_mensual"}
        assert _enlaces(VENTANA_CURVA, produccion[VENTANA_CURVA][1])["motor"] == {MODULO_MOTOR_CURVA}

    def test_las_estructuras_con_el_gris_se_leen_del_arbol(self, produccion):
        """No vacuidad de la guarda 6d/6e: lo que lleva el gris se deriva del árbol (hoy son al menos estas) y NO incluye las listas de las tres capas de color."""
        estructuras = estructuras_con_el_gris(produccion)
        assert {"CAPAS_DEL_PISO", "CAPAS_QUE_LA_VIRGEN_NO_PUEDE_TENER_MAS_OSCURAS", "COLOR_CAPA", "ADJETIVO_DE_LA_CAPA"} <= estructuras, estructuras
        assert not {"CAPAS", "CAPAS_DE_LA_CURVA", "NOMBRE_DE_CAPA"} & estructuras, estructuras

    @pytest.mark.parametrize("fuente, esperado", [
        ("X = ('R', 'G', 'gris')\n", True), ("X = ['R', 'G', 'B']\n", False), ("X = CAPAS + ('gris',)\n", True), ("X = {'R': 1, 'gris': 2}\n", True), ("X = {'piso': {'gris': 2}}\n", False),
        ("X = dict(NOMBRE, gris='gris')\n", True), ("X = tuple(Y)\n", True), ("X = tuple(Z)\n", False), ("X = Y[:3]\n", False), ("X = {**Y}\n", True), ("X = (*Y, 'B')\n", True),
        ("X = 'gris'\n", True),
    ], ids=["tupla", "tupla_sin_el_gris", "suma", "dict_por_capa", "gris_anidado_en_los_valores", "dict_con_palabra_clave", "tuple_de_una_conocida", "tuple_de_otra", "rebanada", "dict_expandido",
            "tupla_con_estrella", "texto_suelto"])
    def test_que_es_una_estructura_con_el_gris(self, fuente, esperado):
        asignacion = ast.parse(fuente).body[0]
        assert _capas_con_el_gris(asignacion.value, {"Y"}) is esperado


# ======================================================================================================== 1. una sola conversión

def privados_del_motor(fuentes):
    """Los nombres PRIVADOS del motor de la curva, leídos de él: sus definiciones de módulo con «_» y los métodos con «_» de sus clases (sin los dunder)."""
    _, arbol = fuentes[MOTOR_CURVA]
    de_modulo = {n for n in _definiciones_de_modulo(arbol) if n.startswith("_") and not n.startswith("__")}
    metodos = {m.name for c in arbol.body if isinstance(c, ast.ClassDef) for m in c.body
               if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("_") and not m.name.startswith("__")}
    return de_modulo, metodos


def usos_de_privados_del_motor(fuentes):
    """[(ruta, nombre privado, línea, cómo)] fuera del motor: `from analisisImagenes.curva_dosis import _x` (también relativo), `motor._x` (por su alias, por la ruta entera o relativo) o `algo._metodo_privado`."""
    de_modulo, metodos = privados_del_motor(fuentes)
    hallados = []
    for ruta, (_, arbol) in fuentes.items():
        if ruta == MOTOR_CURVA:
            continue
        enlaces = _enlaces(ruta, arbol)
        for n in _nodos(arbol):
            if isinstance(n, ast.ImportFrom) and _modulo_importado(n, ruta) == MODULO_MOTOR_CURVA:
                hallados += [(ruta, a.name, n.lineno, "lo importa") for a in n.names if a.name.startswith("_")]
            elif isinstance(n, ast.Attribute) and n.attr.startswith("_") and MODULO_MOTOR_CURVA in _destinos(n.value, enlaces):
                hallados.append((ruta, n.attr, n.lineno, "lo usa por el módulo"))
            elif isinstance(n, ast.Attribute) and n.attr in metodos:
                hallados.append((ruta, n.attr, n.lineno, "usa un método privado de la curva"))
    return sorted(hallados, key=_orden)


def _es_exponente_del_modelo(e, nombres=("n",)):
    """`n`, `curva.n`, `p["n"]`, uno de ellos convertido (`float(p["n"])`) o un nombre al que se asignó uno de ellos (`expo = p["n"]`; los `nombres` salen de `_calcular_exponentes`)."""
    if isinstance(e, ast.Call) and len(e.args) == 1 and not e.keywords and (e.func.id if isinstance(e.func, ast.Name) else getattr(e.func, "attr", None)) in ("float", "float64", "float32", "abs"):
        return _es_exponente_del_modelo(e.args[0], nombres)
    return ((isinstance(e, ast.Name) and e.id in nombres) or (isinstance(e, ast.Attribute) and e.attr == "n")
            or (isinstance(e, ast.Subscript) and isinstance(e.slice, ast.Constant) and e.slice.value == "n"))


def _calcular_exponentes(arbol):
    nombres = {"n"}
    asignaciones = [(t.id, a.value) for a in _nodos(arbol) if isinstance(a, ast.Assign) for t in a.targets if isinstance(t, ast.Name)]
    for _ in range(3):
        nombres |= {nombre for nombre, valor in asignaciones if _es_exponente_del_modelo(valor, nombres)}
    return nombres


def potencias_del_modelo(arbol):
    """[(nodo, qué)] de cada potencia con el exponente del modelo, escrita como sea: `x ** n`, `x **= n`, `pow(x, n)`, `math.pow(x, n)`, `np.power(x, n)`, `np.float_power(x, n)`, `x.__pow__(n)`, con el exponente
    dado por posición o por nombre (`exponent=`) y también si se le puso otro nombre (`expo = curva.n`). La base no cuenta: `np.power(n, 2)` es otra cosa (CD9-REV-AMB-2)."""
    nombres = _recordado("exponentes", arbol, _calcular_exponentes)
    hallados = []
    for n in _nodos(arbol):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow) and _es_exponente_del_modelo(n.right, nombres):
            hallados.append((n, "eleva a la potencia del modelo"))
        elif isinstance(n, ast.AugAssign) and isinstance(n.op, ast.Pow) and _es_exponente_del_modelo(n.value, nombres):
            hallados.append((n, "eleva a la potencia del modelo (**=)"))
        elif isinstance(n, ast.Call) and (n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", None)) in FUNCIONES_DE_POTENCIA:
            exponentes = [*n.args[1:2], *(n.args if len(n.args) == 1 else []), *(k.value for k in n.keywords if k.arg in PALABRAS_DEL_EXPONENTE)]
            if any(_es_exponente_del_modelo(e, nombres) for e in exponentes):
                hallados.append((n, "eleva a la potencia del modelo (con una función)"))
    return hallados


def formula_fuera_del_motor(fuentes, modulos=MODULOS_DEL_PLAN):
    """[(ruta, función, línea, qué)]: (i) en TODO el árbol, fuera del motor de la curva, una potencia con el exponente del modelo (`potencias_del_modelo`: `x ** n`, `x ** p["n"]`, `x **= n`, `pow(x, n)`,
    `np.power(x, n)`...); (ii) en los módulos del plan (salvo el motor y `pelicula.py`, que no conoce la curva), una lectura de `["a"]`, `["b"]` o `["n"]` que no sea para escribirla en un f-string."""
    hallados = []
    for ruta, (_, arbol) in fuentes.items():
        if ruta == MOTOR_CURVA:
            continue
        contenedora = _funcion_contenedora(arbol)
        hallados += [(ruta, contenedora.get(id(n)), n.lineno, como) for n, como in potencias_del_modelo(arbol)]
        if ruta in modulos and ruta != PELICULA:
            escritos = {id(f.value) for f in _nodos(arbol) if isinstance(f, ast.FormattedValue)}
            hallados += [(ruta, contenedora.get(id(n)), n.lineno, f"usa el parámetro {n.slice.value!r} del modelo") for n in _nodos(arbol)
                         if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and n.slice.value in ("a", "b", "n") and id(n) not in escritos]
    return sorted(hallados, key=_orden)


class TestUnaSolaConversion:
    def test_nadie_fuera_del_motor_usa_sus_privados(self, produccion):
        hallados = [(r, nombre, l, como) for r, nombre, l, como in usos_de_privados_del_motor(produccion) if (r, nombre) not in PRIVADOS_PERMITIDOS]
        assert not hallados, f"un nombre privado del motor de la curva fuera de él (la conversión es UNA: usa su API pública): {hallados}"

    def test_no_vacuidad_los_privados_se_leen_del_motor(self, produccion):
        de_modulo, metodos = privados_del_motor(produccion)
        assert {"_devic", "_derivada_de_devic", "_ajustar_devic", "_texto_de_la_cadena"} <= de_modulo and "_parametros_de" in metodos, (de_modulo, metodos)

    def test_cada_privado_permitido_sigue_existiendo(self, produccion):
        usados = {(r, nombre) for r, nombre, _, _ in usos_de_privados_del_motor(produccion)}
        assert set(PRIVADOS_PERMITIDOS) <= usados, f"excepción que ya no hace falta (retírala): {set(PRIVADOS_PERMITIDOS) - usados}"

    @pytest.mark.parametrize("ruta, agregado, nombre", [
        (DIBUJO_CURVA, "def _intruso(x, a, b, n):\n    return motor._devic(x, a, b, n)\n", "_devic"),
        (SECCION_PDF, "from analisisImagenes.curva_dosis import _derivada_de_devic\n", "_derivada_de_devic"),
        (VENTANA_PLACA, "def _intruso(curva):\n    return curva._parametros_de('G')\n", "_parametros_de"),
        # CD9-REV-AMB-6: las otras formas de escribir el mismo uso (la ruta calificada sin alias y las importaciones relativas)
        (SECCION_PDF, "import analisisImagenes.curva_dosis\ndef _intruso(x, a, b, n):\n    return analisisImagenes.curva_dosis._devic(x, a, b, n)\n", "_devic"),
        (SECCION_PDF, "import analisisImagenes.curva_dosis as _c\ndef _intruso(x, a, b, n):\n    return _c._devic(x, a, b, n)\n", "_devic"),
        (DIBUJO_PLACA, "from .curva_dosis import _derivada_de_devic\n", "_derivada_de_devic"),
        (DIBUJO_PLACA, "from . import curva_dosis as _c\ndef _intruso(x, a, b, n):\n    return _c._devic(x, a, b, n)\n", "_devic"),
    ], ids=["por_el_modulo", "importado", "metodo_de_la_curva", "ruta_calificada_sin_alias", "ruta_calificada_con_alias", "importado_con_ruta_relativa", "modulo_relativo"])
    def test_discrimina_un_privado_usado_fuera(self, produccion, ruta, agregado, nombre):
        hallados = usos_de_privados_del_motor(_con(produccion, ruta, agregado))
        assert any(r == ruta and n == nombre for r, n, _, _ in hallados), hallados

    def test_nadie_fuera_del_motor_reescribe_la_formula(self, produccion):
        assert not formula_fuera_del_motor(produccion), formula_fuera_del_motor(produccion)

    def test_no_vacuidad_el_motor_tiene_la_formula_y_el_dibujo_escribe_sus_parametros(self, produccion):
        _, motor = produccion[MOTOR_CURVA]
        assert potencias_del_modelo(motor), "el motor eleva a n: la guarda mira lo correcto"
        _, dibujo = produccion[DIBUJO_CURVA]
        escritos = [n for f in ast.walk(dibujo) if isinstance(f, ast.FormattedValue) for n in [f.value]
                    if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and n.slice.value in ("a", "b", "n")]
        assert len(escritos) >= 3, "la tabla de la curva escribe a, b y n en un f-string: es la lectura que se permite"

    @pytest.mark.parametrize("ruta, agregado", [
        (DIBUJO_CURVA, "def _intrusa(p, x):\n    return p['a'] * x + p['b'] * x ** p['n']\n"),
        (VENTANA_PLACA, "def _intrusa(a, b, n, x):\n    return a * x + b * x ** n\n"),
        ("analisisImagenes/otro_modulo.py", "def dosis(x, curva):\n    return curva.a * x + curva.b * x ** curva.n\n"),
        # CD9-REV-AMB-2: la potencia del modelo escrita de otra manera, en un modulo FUERA de los once del plan (donde solo vigila la potencia)
        ("analisisImagenes/otro_modulo.py", "import numpy as np\ndef dosis(x, curva):\n    return curva.a * x + curva.b * np.power(x, curva.n)\n"),
        ("analisisImagenes/otro_modulo.py", "def dosis(x, curva):\n    return curva.a * x + curva.b * pow(x, curva.n)\n"),
        ("analisisImagenes/otro_modulo.py", "import math\ndef dosis(x, curva):\n    return curva.a * x + curva.b * math.pow(x, curva.n)\n"),
        ("analisisImagenes/otro_modulo.py", "import numpy\ndef dosis(x, p):\n    return p['a'] * x + p['b'] * numpy.float_power(x, p['n'])\n"),
        ("analisisImagenes/otro_modulo.py", "def dosis(x, curva):\n    x **= curva.n\n    return curva.a * x\n"),
        ("analisisImagenes/otro_modulo.py", "def dosis(x, curva):\n    expo = curva.n\n    return curva.a * x + curva.b * x ** expo\n"),
        ("analisisImagenes/otro_modulo.py", "import numpy as np\ndef dosis(x, curva):\n    return np.power(x, exponent=curva.n)\n"),
        (VENTANA_PLACA, "import numpy as np\ndef _intrusa(a, b, n, x):\n    return a * x + b * np.power(x, n)\n"),
        ("analisisImagenes/otro_modulo.py", "def dosis(x, p):\n    expo = float(p['n'])\n    return x ** expo\n"),
    ], ids=["dibujo_con_los_parametros", "ventana", "modulo_nuevo", "np_power", "pow", "math_pow", "float_power", "operador_aumentado", "exponente_con_otro_nombre", "exponente_por_palabra_clave",
            "ventana_con_np_power", "exponente_convertido_con_float"])
    def test_discrimina_la_formula_reescrita(self, produccion, ruta, agregado):
        hallados = formula_fuera_del_motor(_con(produccion, ruta, agregado))
        assert any(r == ruta and f in ("_intrusa", "dosis") for r, f, _, _ in hallados), hallados

    @pytest.mark.parametrize("agregado", [
        "def dosis(x):\n    return x ** 2 + 10 ** 3\n",
        "import numpy as np\ndef dosis(x, n):\n    return np.power(n, 2) + np.power(x, 2)\n",
        "def dosis(base, expo):\n    return pow(base, 0.5) + pow(base, expo)\n",
    ], ids=["potencias_fijas", "n_como_base", "otro_exponente"])
    def test_no_marca_una_potencia_que_no_es_la_del_modelo(self, produccion, agregado):
        """El control de las spellings nuevas: elevar con `pow`/`np.power` sigue siendo legitimo si el exponente no es el `n` del modelo (la base no cuenta)."""
        assert not [h for h in formula_fuera_del_motor(_con(produccion, "analisisImagenes/otro_modulo.py", agregado)) if h[0] == "analisisImagenes/otro_modulo.py"]


# ======================================================================================================== 2. una sola regla

def definiciones_de_las_reglas(fuentes):
    """{regla: [(ruta, línea)]} de cada función que se llama como una regla, en todo el árbol."""
    salida = {regla: [] for regla in REGLAS}
    for ruta, (_, arbol) in fuentes.items():
        for n in _nodos(arbol):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in salida:
                salida[n.name].append((ruta, n.lineno))
    return salida


def llamadores_de_las_reglas(fuentes):
    """{regla: [(ruta, función, línea)]} de las llamadas a cada regla FUERA de su módulo, por su nombre (no hay homónimos en el árbol): el que se ve en la llamada (`motor.regla(...)`) y, si ese nombre sale
    de una importación o de una asignación, el de origen (`from m import regla as _otra` + `_otra(...)`; `_otra = m.regla`: CD9-REV-AMB-5, decisión CD9-D7 ampliada)."""
    salida = {regla: [] for regla in REGLAS}
    for ruta, (_, arbol) in fuentes.items():
        contenedora = _funcion_contenedora(arbol)
        enlaces = _enlaces(ruta, arbol)
        for n in _nodos(arbol):
            if isinstance(n, ast.Call):
                for nombre in sorted(_nombres_llamados(n.func, enlaces)):
                    if nombre in salida and ruta != REGLAS[nombre]:
                        salida[nombre].append((ruta, contenedora.get(id(n)), n.lineno))
    return salida


def constructores_de_la_curva_efectiva(fuentes):
    hallados = []
    for ruta, (_, arbol) in fuentes.items():
        if ruta == MOTOR_PLACA:
            continue
        contenedora = _funcion_contenedora(arbol)
        enlaces = _enlaces(ruta, arbol)
        hallados += [(ruta, contenedora.get(id(n)), n.lineno) for n in _nodos(arbol) if isinstance(n, ast.Call) and "CurvaEfectiva" in _nombres_llamados(n.func, enlaces)]
    return sorted(hallados, key=_orden)


class TestUnaSolaRegla:
    def test_cada_regla_se_define_una_vez_en_su_modulo(self, produccion):
        for regla, sitios in definiciones_de_las_reglas(produccion).items():
            assert [r for r, _ in sitios] == [REGLAS[regla]], f"`{regla}` se define en {sitios}: es UNA regla, en {REGLAS[regla]}"

    def test_no_vacuidad_cada_regla_es_una_funcion_de_modulo(self, produccion):
        for regla, ruta in REGLAS.items():
            assert regla in _definiciones_de_modulo(produccion[ruta][1]), f"`{regla}` ya no es una función de módulo de {ruta}"

    def test_solo_los_llamadores_declarados_usan_cada_regla(self, produccion):
        for regla, sitios in llamadores_de_las_reglas(produccion).items():
            fuera = _sin_permitidos(sitios, LLAMADORES_PERMITIDOS[regla])
            assert not fuera, f"`{regla}` la llama un sitio no declarado (¿una segunda regla?): {fuera}"

    def test_cada_llamador_declarado_sigue_llamando(self, produccion):
        for regla, sitios in llamadores_de_las_reglas(produccion).items():
            assert _usados(sitios, LLAMADORES_PERMITIDOS[regla]) == set(LLAMADORES_PERMITIDOS[regla]), f"`{regla}`: llamador declarado que ya no llama (retíralo): {set(LLAMADORES_PERMITIDOS[regla]) - _usados(sitios, LLAMADORES_PERMITIDOS[regla])}"

    def test_la_curva_efectiva_solo_se_construye_en_los_sitios_declarados(self, produccion):
        hallados = constructores_de_la_curva_efectiva(produccion)
        assert not _sin_permitidos(hallados, CONSTRUCTORES_DE_LA_CURVA_EFECTIVA), hallados
        assert _usados(hallados, CONSTRUCTORES_DE_LA_CURVA_EFECTIVA) == set(CONSTRUCTORES_DE_LA_CURVA_EFECTIVA)

    @pytest.mark.parametrize("regla", sorted(REGLAS))
    def test_discrimina_una_segunda_definicion(self, produccion, regla):
        ruta = VENTANA_PLACA if REGLAS[regla] != VENTANA_PLACA else DIBUJO_PLACA
        sitios = definiciones_de_las_reglas(_con(produccion, ruta, f"def {regla}(*args, **kwargs):\n    return None\n"))[regla]
        assert sorted(r for r, _ in sitios) == sorted([REGLAS[regla], ruta]), sitios

    @pytest.mark.parametrize("regla", sorted(REGLAS))
    def test_discrimina_un_llamador_nuevo(self, produccion, regla):
        sitios = llamadores_de_las_reglas(_con(produccion, SECCION_PDF if REGLAS[regla] != SECCION_PDF else VENTANA_PLACA,
                                               f"def _intruso(x):\n    return x.{regla}(x)\n"))[regla]
        assert [s for s in _sin_permitidos(sitios, LLAMADORES_PERMITIDOS[regla]) if s[1] == "_intruso"], sitios

    def test_discrimina_una_curva_efectiva_armada_a_mano(self, produccion):
        hallados = constructores_de_la_curva_efectiva(_con(produccion, SECCION_PDF, "def _intruso(c):\n    return motor.CurvaEfectiva(c)\n"))
        assert (SECCION_PDF, "_intruso") in {(r, f) for r, f, _ in _sin_permitidos(hallados, CONSTRUCTORES_DE_LA_CURVA_EFECTIVA)}

    @pytest.mark.parametrize("agregado", ["from analisisImagenes.placa_mensual import CurvaEfectiva as _CE\ndef _intruso(c):\n    return _CE(c)\n",
                                          "from analisisImagenes import placa_mensual as _m\n_CE = _m.CurvaEfectiva\ndef _intruso(c):\n    return _CE(c)\n"], ids=["importada_con_otro_nombre", "alias_por_asignacion"])
    def test_discrimina_una_curva_efectiva_armada_con_otro_nombre(self, produccion, agregado):
        """CD9-REV-AMB-5: la clase importada con otro nombre (`import f as g`) tampoco se construye fuera de los sitios declarados."""
        hallados = constructores_de_la_curva_efectiva(_con(produccion, SECCION_PDF, agregado))
        assert (SECCION_PDF, "_intruso") in {(r, f) for r, f, _ in _sin_permitidos(hallados, CONSTRUCTORES_DE_LA_CURVA_EFECTIVA)}

    @pytest.mark.parametrize("forma", ["importada_con_otro_nombre", "alias_por_asignacion"])
    @pytest.mark.parametrize("regla", sorted(REGLAS))
    def test_discrimina_un_llamador_con_otro_nombre(self, produccion, regla, forma):
        """CD9-REV-AMB-5: reconocer al llamador por el NOMBRE llamado no ve `from <modulo> import <regla> as _otra` ni `_otra = <modulo>.<regla>`: la premisa «un alias nuevo también se llama así»
        vale para el atributo (`motor.regla`) y no para `import f as g`. Aquí, cada una de las nueve reglas, llamada con otro nombre desde un sitio no declarado."""
        modulo = _punteado(REGLAS[regla])
        paquete, _, hoja = modulo.rpartition(".")
        agregado = {"importada_con_otro_nombre": f"from {modulo} import {regla} as _otra\n",
                    "alias_por_asignacion": f"from {paquete} import {hoja} as _m\n_otra = _m.{regla}\n"}[forma] + "def _intruso(x):\n    return _otra(x)\n"
        sitios = llamadores_de_las_reglas(_con(produccion, SECCION_PDF if REGLAS[regla] != SECCION_PDF else VENTANA_PLACA, agregado))[regla]
        assert [s for s in _sin_permitidos(sitios, LLAMADORES_PERMITIDOS[regla]) if s[1] == "_intruso"], sitios


# ======================================================================================================== 3. las dos ventanas sin SQL

LLAMADAS_DE_SQL = {"execute", "executemany", "executescript", "cursor", "commit", "rollback", "conectar"}
MODULOS_DE_SQL = ("sqlite3", "PyQt5.QtSql", "sqlalchemy")
NOMBRES_DE_SQL = {"Conexion", "QSqlQuery", "QSqlDatabase"}
TEXTO_SQL = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|REPLACE)\b.*\b(FROM|INTO|SET|TABLE|WHERE)\b|\bPRAGMA\b", re.IGNORECASE | re.DOTALL)


def sql_en(fuentes, ruta):
    texto, arbol = fuentes[ruta]
    contenedora = _funcion_contenedora(arbol)
    hallados = []
    for n in _nodos(arbol):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in LLAMADAS_DE_SQL:
            hallados.append((ruta, contenedora.get(id(n)), n.lineno, f"llama .{n.func.attr}("))
        elif isinstance(n, ast.Import) and any(a.name.startswith(MODULOS_DE_SQL) for a in n.names):
            hallados.append((ruta, contenedora.get(id(n)), n.lineno, "importa SQL"))
        elif isinstance(n, ast.ImportFrom) and (n.module or "").startswith(MODULOS_DE_SQL):
            hallados.append((ruta, contenedora.get(id(n)), n.lineno, "importa SQL"))
        elif isinstance(n, ast.Name) and n.id in NOMBRES_DE_SQL:
            hallados.append((ruta, contenedora.get(id(n)), n.lineno, f"usa {n.id}"))
    hallados += [(ruta, contenedora.get(id(n)), n.lineno, "un texto SQL") for n, t in _literales(arbol) if TEXTO_SQL.search(t)]
    return sorted(hallados, key=_orden)


class TestLasVentanasSinSql:
    @pytest.mark.parametrize("ruta", VENTANAS, ids=["calibracion", "mensual"])
    def test_la_ventana_no_toca_la_base(self, produccion, ruta):
        assert not sql_en(produccion, ruta), sql_en(produccion, ruta)

    @pytest.mark.parametrize("ruta", VENTANAS, ids=["calibracion", "mensual"])
    def test_no_vacuidad_es_la_ventana_y_usa_su_servicio(self, produccion, ruta):
        _, arbol = produccion[ruta]
        assert any(isinstance(n, ast.ClassDef) and n.name.startswith("Ventana") for n in arbol.body), f"{ruta} ya no define su ventana"
        assert _importa(ruta, arbol, MODULO_SERVICIO_CURVA if ruta == VENTANA_CURVA else MODULO_SERVICIO_PLACA)

    @pytest.mark.parametrize("linea", ["import sqlite3", "from PyQt5.QtSql import QSqlQuery", "def _x(c):\n    c.execute('SELECT 1')", "def _x():\n    return Conexion().conectar()",
                                       "CONSULTA = 'SELECT id FROM controles WHERE ref = ?'", "def _x(c):\n    c.commit()"])
    @pytest.mark.parametrize("ruta", VENTANAS, ids=["calibracion", "mensual"])
    def test_discrimina_cada_forma_de_tocar_la_bd(self, produccion, ruta, linea):
        assert sql_en(_con(produccion, ruta, linea + "\n"), ruta), linea


# ======================================================================================================== 4. al reabrir, la copia guardada

def usos_del_servicio_de_la_curva(fuentes):
    """[(ruta, función, línea, qué)]: cada importación del servicio de la curva y cada llamada a él, fuera de él, escritas como sea (relativas, por nombre, con la ruta entera, con otro nombre)."""
    hallados = []
    for ruta, (_, arbol) in fuentes.items():
        if ruta == SERVICIO_CURVA:
            continue
        contenedora = _funcion_contenedora(arbol)
        hallados += [(ruta, contenedora.get(id(n)), n.lineno, "lo importa") for n in _importaciones_de(ruta, arbol, MODULO_SERVICIO_CURVA)]
        hallados += [(ruta, f, l, f"llama {nombre}") for f, nombre, l, _ in _llamadas_al_modulo(fuentes, ruta, MODULO_SERVICIO_CURVA)]
    return sorted(hallados, key=_orden)


def problemas_de_la_guarda_del_registro(fuentes):
    """`_leer_la_curva` de la ventana mensual EMPIEZA (tras su docstring) por un `if` que mira `self._registro` y solo hace `return`: con un registro a la vista no se busca la curva vigente."""
    funcion = _funcion(fuentes[VENTANA_PLACA][1], "_leer_la_curva")
    if funcion is None:
        return ["la ventana mensual ya no define `_leer_la_curva` (una vez)"]
    cuerpo = [s for s in funcion.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
    primera = cuerpo[0] if cuerpo else None
    if not (isinstance(primera, ast.If) and any(isinstance(n, ast.Attribute) and n.attr == "_registro" for n in ast.walk(primera.test))
            and len(primera.body) == 1 and isinstance(primera.body[0], ast.Return) and primera.body[0].value is None and not primera.orelse):
        return [f"`_leer_la_curva` (línea {funcion.lineno}) no empieza por «con un registro a la vista, return»: al reabrir buscaría la curva vigente (DA-81)"]
    return []


def problemas_al_reabrir(fuentes):
    """`abrir_guardado` de la ventana mensual toma la curva de `svc.curva_guardada` y no llama `_leer_la_curva`, `curva_efectiva` ni el servicio de la curva."""
    texto, arbol = fuentes[VENTANA_PLACA]
    funcion = _funcion(arbol, "abrir_guardado")
    if funcion is None:
        return ["la ventana mensual ya no define `abrir_guardado` (una vez)"]
    enlaces = _enlaces(VENTANA_PLACA, arbol)
    llamadas = [n for n in ast.walk(funcion) if isinstance(n, ast.Call)]
    problemas = [f"`abrir_guardado` llama `{ast.unparse(n.func)}` (línea {n.lineno}): al reabrir buscaría la curva vigente" for n in llamadas
                 if _nombres_llamados(n.func, enlaces) & {"_leer_la_curva", "curva_efectiva", "vigentes_validas"} or any(d.startswith(MODULO_SERVICIO_CURVA + ".") for d in _destinos(n.func, enlaces))]
    if not any(f"{MODULO_SERVICIO_PLACA}.curva_guardada" in _destinos(n.func, enlaces) for n in llamadas):
        problemas.append("`abrir_guardado` ya no toma la curva de `svc.curva_guardada` (la copia guardada, DA-81)")
    return problemas


def tablas_de_las_calibraciones(fuentes):
    _, arbol = fuentes[SERVICIO_CURVA]
    return tuple(t for t in (_texto_de_constante(arbol, "TABLA"), _texto_de_constante(arbol, "TABLA_PIEZAS")) if t)


def sql_de_las_calibraciones(fuentes):
    """[(ruta, función, línea, qué)]: un texto SQL que nombra una tabla de las calibraciones, o el uso de los nombres de tabla o de las sentencias del servicio (`TABLA`, `TABLA_PIEZAS`, `SQL_*`),
    fuera de los archivos declarados."""
    tablas = tablas_de_las_calibraciones(fuentes)
    patron = re.compile(r"\b(" + "|".join(re.escape(t) for t in tablas) + r")\b")
    hallados = []
    for ruta, (_, arbol) in fuentes.items():
        contenedora = _funcion_contenedora(arbol)
        hallados += [(ruta, contenedora.get(id(n)), n.lineno, "un texto SQL con una tabla de las calibraciones") for n, t in _literales(arbol) if patron.search(t) and TEXTO_SQL.search(t)]
        if ruta != SERVICIO_CURVA:
            enlaces = _enlaces(ruta, arbol)
            hallados += [(ruta, contenedora.get(id(n)), n.lineno, f"usa {n.attr} del servicio") for n in _nodos(arbol) if isinstance(n, ast.Attribute)
                         and MODULO_SERVICIO_CURVA in _destinos(n.value, enlaces) and (n.attr in ("TABLA", "TABLA_PIEZAS") or n.attr.startswith("SQL_"))]
            hallados += [(ruta, contenedora.get(id(n)), n.lineno, f"importa {a.name} del servicio") for n in _nodos(arbol) if isinstance(n, ast.ImportFrom)
                         and _modulo_importado(n, ruta) == MODULO_SERVICIO_CURVA for a in n.names if a.name in ("TABLA", "TABLA_PIEZAS") or a.name.startswith("SQL_")]
    return sorted(hallados, key=_orden)


class TestAlReabrirLaCopiaGuardada:
    def test_el_servicio_de_la_curva_solo_lo_usan_los_sitios_declarados(self, produccion):
        hallados = usos_del_servicio_de_la_curva(produccion)
        assert not _sin_permitidos(hallados, USOS_DEL_SERVICIO_DE_LA_CURVA), _sin_permitidos(hallados, USOS_DEL_SERVICIO_DE_LA_CURVA)

    def test_no_vacuidad_la_ventana_mensual_lee_las_vigentes_solo_para_una_pelicula_nueva(self, produccion):
        hallados = usos_del_servicio_de_la_curva(produccion)
        assert (VENTANA_PLACA, "_leer_la_curva", "llama vigentes_validas") in {(r, f, q) for r, f, _, q in hallados}
        assert _usados(hallados, USOS_DEL_SERVICIO_DE_LA_CURVA) == set(USOS_DEL_SERVICIO_DE_LA_CURVA)

    def test_leer_la_curva_empieza_por_la_guarda_del_registro(self, produccion):
        assert not problemas_de_la_guarda_del_registro(produccion)

    def test_abrir_guardado_usa_la_copia(self, produccion):
        assert not problemas_al_reabrir(produccion)

    @pytest.mark.parametrize("ruta", [SERVICIO_PLACA, SECCION_PDF])
    def test_el_servicio_de_la_placa_y_el_pdf_no_importan_el_servicio_de_la_curva(self, produccion, ruta):
        assert not _importa(ruta, produccion[ruta][1], MODULO_SERVICIO_CURVA), f"{ruta} importa el servicio de la curva: leería las calibraciones vigentes (DA-81)"

    def test_solo_el_servicio_y_el_esquema_escriben_sql_de_las_calibraciones(self, produccion):
        hallados = sql_de_las_calibraciones(produccion)
        assert not [h for h in hallados if h[0] not in SQL_DE_LAS_CALIBRACIONES], hallados
        assert {h[0] for h in hallados} == set(SQL_DE_LAS_CALIBRACIONES), "no vacuidad: el servicio y el esquema escriben ese SQL"

    @pytest.mark.parametrize("ruta, agregado", [
        (SECCION_PDF, "from services import curva_dosis as svc_curva\n"),
        (VENTANA_PLACA, "def _intruso(self):\n    return svc_curva.listar()\n"),
        (DIBUJO_PLACA, "from services.curva_dosis import vigentes_validas\n"),
        # CD9-REV-AMB-4: lo que hay FUERA de toda funcion de la ventana no es «la importacion declarada» (el cuerpo de una clase, una asignacion de modulo)
        (VENTANA_PLACA, "class _Cache:\n    VIGENTES = svc_curva.vigentes_validas()\n"),
        (VENTANA_PLACA, "CALIBRACIONES = svc_curva.vigentes_validas()\n"),
        (VENTANA_PLACA, "def _intruso():\n    from services import curva_dosis as otro\n    return otro.listar()\n"),
        # CD9-REV-AMB-6: las otras formas de importar o llamar al servicio (relativa, por nombre, ruta entera)
        (SERVICIO_PLACA, "from . import curva_dosis as svc_curva\n"),
        (SERVICIO_PLACA, "from .curva_dosis import vigentes_validas as _vigentes\n"),
        (SECCION_PDF, "import services.curva_dosis\ndef _intruso():\n    return services.curva_dosis.vigentes_validas()\n"),
    ], ids=["el_pdf_lo_importa", "otra_funcion_de_la_ventana", "el_dibujo_importa_una_funcion", "en_el_cuerpo_de_una_clase", "a_nivel_de_modulo", "importacion_diferida_en_otra_funcion",
            "el_servicio_de_la_placa_lo_importa_relativo", "importado_relativo_por_nombre", "ruta_entera"])
    def test_discrimina_un_uso_nuevo_del_servicio_de_la_curva(self, produccion, ruta, agregado):
        assert _sin_permitidos(usos_del_servicio_de_la_curva(_con(produccion, ruta, agregado)), USOS_DEL_SERVICIO_DE_LA_CURVA)

    def test_discrimina_leer_la_curva_sin_la_guarda(self, produccion):
        texto = produccion[VENTANA_PLACA][0]
        funcion = _funcion(produccion[VENTANA_PLACA][1], "_leer_la_curva")
        guarda = [s for s in funcion.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))][0]
        lineas = texto.splitlines(keepends=True)
        sin = "".join(lineas[:guarda.lineno - 1] + lineas[guarda.end_lineno:])
        assert problemas_de_la_guarda_del_registro({**produccion, VENTANA_PLACA: (sin, ast.parse(sin))})

    def test_discrimina_abrir_guardado_con_la_curva_vigente(self, produccion):
        texto = produccion[VENTANA_PLACA][0]
        funcion = _funcion(produccion[VENTANA_PLACA][1], "abrir_guardado")
        llamada = next(n for n in ast.walk(funcion) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "curva_guardada")
        viejo = ast.get_source_segment(texto, llamada)
        assert problemas_al_reabrir(_con_reemplazo(produccion, VENTANA_PLACA, viejo, "motor.curva_efectiva(svc_curva.vigentes_validas(), None)"))

    @pytest.mark.parametrize("llamada, importacion", [
        ("svc_curva.vigentes_validas()", ""),
        ("_vigentes()", "from services.curva_dosis import vigentes_validas as _vigentes\n"),
        ("motor.curva_efectiva([], None)", ""),
        ("self._leer_la_curva()", ""),
    ], ids=["el_servicio", "el_servicio_importado_por_nombre", "la_regla_de_la_curva_efectiva", "buscar_la_curva_de_una_pelicula_nueva"])
    def test_discrimina_abrir_guardado_que_ademas_busca_la_vigente(self, produccion, llamada, importacion):
        """CD9-REV-AMB-6: `abrir_guardado` CONSERVA la lectura de la copia guardada y suma una busqueda de la curva vigente: lo unico que puede hacer caer la guarda es esa llamada (no la falta de la copia),
        escrita como atributo o como nombre importado."""
        texto = produccion[VENTANA_PLACA][0]
        funcion = _funcion(produccion[VENTANA_PLACA][1], "abrir_guardado")
        viejo = ast.get_source_segment(texto, next(n for n in ast.walk(funcion) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "curva_guardada"))
        fuentes = _con_reemplazo(_con(produccion, VENTANA_PLACA, importacion) if importacion else produccion, VENTANA_PLACA, viejo, f"({llamada}, {viejo})[1]")
        problemas = problemas_al_reabrir(fuentes)
        assert problemas and not any("ya no toma la curva" in p for p in problemas), problemas

    @pytest.mark.parametrize("agregado", ["CONSULTA = 'SELECT * FROM calibracion_pelicula WHERE activo = 1'\n",
                                          "def _x(svc):\n    return f'UPDATE {svc_curva.TABLA} SET activo = 0'\n"], ids=["texto", "nombre_del_servicio"])
    def test_discrimina_sql_de_las_calibraciones_fuera_del_servicio(self, produccion, agregado):
        hallados = sql_de_las_calibraciones(_con(produccion, VENTANA_PLACA, agregado))
        assert [h for h in hallados if h[0] == VENTANA_PLACA], hallados

    @pytest.mark.parametrize("ruta, agregado", [
        (VENTANA_PLACA, "from services.curva_dosis import TABLA_PIEZAS\n"),
        (VENTANA_PLACA, "from services.curva_dosis import SQL_VIGENTES_VALIDAS as _consulta\n"),
        (SERVICIO_PLACA, "from . import curva_dosis as _s\ndef _x():\n    return f'DELETE FROM {_s.TABLA}'\n"),
        (SECCION_PDF, "import services.curva_dosis\ndef _x():\n    return f'DELETE FROM {services.curva_dosis.TABLA}'\n"),
    ], ids=["la_tabla_importada_por_nombre", "la_sentencia_importada_con_otro_nombre", "el_nombre_por_la_ruta_relativa", "el_nombre_por_la_ruta_entera"])
    def test_discrimina_los_nombres_del_servicio_usados_por_otro_camino(self, produccion, ruta, agregado):
        """CD9-REV-AMB-6: los nombres de tabla y las sentencias del servicio (`TABLA`, `TABLA_PIEZAS`, `SQL_*`) se usan tambien importados por nombre, con la ruta relativa o con la ruta entera."""
        hallados = sql_de_las_calibraciones(_con(produccion, ruta, agregado))
        assert [h for h in hallados if h[0] == ruta], hallados


# ======================================================================================================== 5. ningún texto escribe una base o una dosis a mano

def nombres_de_las_bases(fuentes):
    _, arbol = fuentes[MOTOR_PLACA]
    return {nombre: _texto_de_constante(arbol, nombre) for nombre in _definiciones_de_modulo(arbol) if nombre.startswith("BASE_") and isinstance(_texto_de_constante(arbol, nombre), str)}


def bases_escritas_a_mano(fuentes, modulos=VISTA_MENSUAL):
    """[(ruta, función, línea, qué)]: (a) un texto que lleva el nombre de una base de varias palabras (`BASE_DENSIDAD_OPTICA`, `BASE_VALOR_DE_PIXEL`; sin distinguir mayúsculas); (b) una comparación de
    algo que dice «base» con un literal que es el nombre de una base (también «dosis»); (c) «cGy» fuera de «[cGy]»."""
    bases = nombres_de_las_bases(fuentes)
    largas = [v.lower() for v in bases.values() if " " in v]
    hallados = []
    for ruta in modulos:
        _, arbol = fuentes[ruta]
        contenedora = _funcion_contenedora(arbol)
        for n, t in _literales(arbol):
            if any(b in t.lower() for b in largas):
                hallados.append((ruta, contenedora.get(id(n)), n.lineno, f"escribe una base: {t[:60]!r}"))
            if "cGy" in t.replace("[cGy]", ""):
                hallados.append((ruta, contenedora.get(id(n)), n.lineno, f"«cGy» fuera de «[cGy]»: {t[:60]!r}"))
        for n in _nodos(arbol):
            if isinstance(n, ast.Compare):
                lados = [n.left, *n.comparators]
                if any(isinstance(c, ast.Constant) and c.value in bases.values() for c in lados) and any("base" in ast.unparse(c).lower() for c in lados if not isinstance(c, ast.Constant)):
                    hallados.append((ruta, contenedora.get(id(n)), n.lineno, f"compara una base con un literal: {ast.unparse(n)[:60]}"))
    return sorted(hallados, key=_orden)


class TestNingunTextoEscribeUnaBase:
    def test_la_vista_mensual_no_escribe_una_base_a_mano(self, produccion):
        fuera = _sin_permitidos(bases_escritas_a_mano(produccion), BASES_ESCRITAS_PERMITIDAS)
        assert not fuera, f"un texto de la ventana mensual, su dibujo o su PDF escribe una base o una unidad a mano (usa `motor.BASE_*` y «[cGy]»): {fuera}"

    def test_no_vacuidad_las_bases_se_leen_del_motor_y_las_excepciones_siguen(self, produccion):
        bases = nombres_de_las_bases(produccion)
        assert {"BASE_DENSIDAD_OPTICA", "BASE_VALOR_DE_PIXEL", "BASE_DOSIS"} <= set(bases), bases
        assert _usados(bases_escritas_a_mano(produccion), BASES_ESCRITAS_PERMITIDAS) == set(BASES_ESCRITAS_PERMITIDAS), "excepción que ya no hace falta: retírala"

    @pytest.mark.parametrize("ruta, agregado", [
        (SECCION_PDF, "def _intruso():\n    return 'Base de la medida: densidad óptica neta'\n"),
        (VENTANA_PLACA, "def _intruso(v):\n    return f'Dosis de la meseta: {v:.1f} cGy'\n"),
        (DIBUJO_PLACA, "def _intruso(resultado):\n    return resultado.base == 'dosis'\n"),
        (DIBUJO_PLACA, "def _intruso():\n    return 'Valor de píxel normalizado medio'\n"),
    ], ids=["base_en_el_pdf", "cgy_sin_corchetes", "comparacion_con_literal", "valor_de_pixel"])
    def test_discrimina_un_texto_a_mano(self, produccion, ruta, agregado):
        fuera = _sin_permitidos(bases_escritas_a_mano(_con(produccion, ruta, agregado)), BASES_ESCRITAS_PERMITIDAS)
        assert [h for h in fuera if h[0] == ruta and h[1] == "_intruso"], fuera


# ======================================================================================================== 6. DA-93: una tabla, un cuadrado, una lista de «Info», ningún perfil gris

def rotulos_de_la_tabla(fuentes):
    """Las plantillas de los rótulos de `filas_de_la_capa_reportada` (y de las funciones del dibujo que llama y de las constantes de texto que usa) que llevan una unidad entre corchetes y al menos
    15 caracteres propios: «Lado {} (radiación − luz) [mm]», «Radiación − retículo (x; y) [mm]»... Las cortas («FWHM {} [mm]», «Estado») se repiten con razón en otras tablas."""
    _, arbol = fuentes[DIBUJO_PLACA]
    raiz = _funcion(arbol, "filas_de_la_capa_reportada")
    if raiz is None:
        return []
    del_modulo = {n.name: n for n in arbol.body if isinstance(n, ast.FunctionDef)}
    funciones = [raiz] + [del_modulo[n.func.id] for n in ast.walk(raiz) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in del_modulo]
    plantillas = set()
    for f in funciones:
        plantillas |= {t for _, t in _literales(f)}
        plantillas |= {_texto_de_constante(arbol, n.id) for n in ast.walk(f) if isinstance(n, ast.Name) and isinstance(_texto_de_constante(arbol, n.id), str)}
    plantillas = {re.sub(r"\{[^{}]*\}", "{}", p) for p in plantillas}
    return sorted(p for p in plantillas if "[" in p and len(p.replace("{}", "")) >= 15)


def _patron(plantilla):
    return re.compile(".+?".join(re.escape(trozo) for trozo in plantilla.split("{}")))


def rotulos_copiados(fuentes, modulos=(VENTANA_PLACA, SECCION_PDF)):
    patrones = [(_patron(p), p) for p in rotulos_de_la_tabla(fuentes)]
    hallados = []
    for ruta in modulos:
        _, arbol = fuentes[ruta]
        contenedora = _funcion_contenedora(arbol)
        hallados += [(ruta, contenedora.get(id(n)), n.lineno, f"copia el rótulo «{p}»: {t[:50]!r}") for n, t in _literales(arbol) for patron, p in patrones if patron.search(t)]
    return sorted(hallados, key=_orden)


def problemas_del_cuadrado(fuentes):
    problemas = []
    definiciones = [(r, n.lineno) for r, (_, a) in fuentes.items() for n in a.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "LADO_DEL_CUADRADO_PERFECTO_MM" for t in n.targets)]
    if [r for r, _ in definiciones] != [DIBUJO_PLACA]:
        problemas.append(f"`LADO_DEL_CUADRADO_PERFECTO_MM` se define en {definiciones}: es UNA, en el dibujo")
    _, arbol = fuentes[DIBUJO_PLACA]
    del_cuadrado = [n for n in arbol.body if isinstance(n, ast.FunctionDef) and FUNCIONES_DEL_CUADRADO.search(n.name)]
    if len(del_cuadrado) < 3:
        problemas.append(f"el dibujo tiene {len(del_cuadrado)} funciones del cuadrado (filas_de_la_cuadratura, cuadrado_perfecto, dibujar_cuadratura)")
    for f in del_cuadrado:
        nombres = {n.id for n in ast.walk(f) if isinstance(n, ast.Name)}
        if not ({"LADO_DEL_CUADRADO_PERFECTO_MM", "cuadrado_perfecto"} & nombres):
            problemas.append(f"`{f.name}` (línea {f.lineno}) no usa `LADO_DEL_CUADRADO_PERFECTO_MM` ni `cuadrado_perfecto`")
        numeros = [n.lineno for n in ast.walk(f) if isinstance(n, ast.Constant) and not isinstance(n.value, bool) and isinstance(n.value, (int, float)) and n.value in NUMEROS_DEL_CUADRADO]
        if numeros:
            problemas.append(f"`{f.name}` escribe 100 o 50 a mano (líneas {numeros}): el lado es `LADO_DEL_CUADRADO_PERFECTO_MM`")
    for ruta in VISTA_MENSUAL:
        _, a = fuentes[ruta]
        contenedora = _funcion_contenedora(a)
        problemas += [f"{ruta}:{n.lineno} ({contenedora.get(id(n))}) dice «100 mm» a mano: {t[:50]!r}" for n, t in _literales(a) if TEXTOS_DEL_CUADRADO.search(t)]
    return problemas


def problemas_de_la_info(fuentes):
    _, arbol = fuentes[VENTANA_PLACA]
    problemas = []
    lista = [n for n in arbol.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "EXPLICACIONES_EN_LA_INFO" for t in n.targets)]
    otras = [r for r, (_, a) in fuentes.items() if r != VENTANA_PLACA and "EXPLICACIONES_EN_LA_INFO" in _definiciones_de_modulo(a)]
    if len(lista) != 1 or otras or not isinstance(lista[0].value, ast.Tuple):
        return [f"`EXPLICACIONES_EN_LA_INFO` no es UNA tupla de la ventana mensual ({len(lista)} en la ventana, otras en {otras})"]
    nombres = [e.value for e in lista[0].value.elts if isinstance(e, ast.Constant)]
    asignados = {t.attr for n in _nodos(arbol) if isinstance(n, ast.Assign) for t in n.targets
                 if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self"}
    problemas += [f"`{n}` de `EXPLICACIONES_EN_LA_INFO` no es un widget de la ventana (`self.{n} = ...`)" for n in nombres if n not in asignados]
    clase = [n for n in arbol.body if isinstance(n, ast.ClassDef) and n.name == "_DialogoInfo"]
    if len(clase) != 1:
        return problemas + ["la ventana ya no define `_DialogoInfo` (una vez)"]
    textos = [t for n, t in _literales(clase[0])]
    creados = [ast.unparse(n.func) for n in ast.walk(clase[0]) if isinstance(n, ast.Call) and (getattr(n.func, "id", "") in ("QLabel", "QTextEdit", "QTextBrowser", "QPlainTextEdit")
                                                                                            or getattr(n.func, "attr", "") in ("setText", "setPlainText", "setHtml", "setMarkdown"))]
    if textos or creados:
        problemas.append(f"el cuadro «Info» escribe sus propios textos (copia, no los widgets de la ventana): {textos} {creados}")
    llamadas = [n for n in _nodos(arbol) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_DialogoInfo"]
    if len(llamadas) != 1 or not any(isinstance(x, ast.Name) and x.id == "EXPLICACIONES_EN_LA_INFO" for x in ast.walk(llamadas[0])):
        problemas.append("`_DialogoInfo` no se construye UNA vez con los widgets de `EXPLICACIONES_EN_LA_INFO`")
    return problemas


def _asignaciones_de_modulo(arbol):
    """[(nombre, valor)] de las asignaciones de NIVEL DE MÓDULO a un nombre (`X = ...`, `X: T = ...`) de un archivo."""
    return _recordado("asignaciones_de_modulo", arbol, lambda a: [(t.id, n.value) for n in a.body if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None
                                                                   for t in (n.targets if isinstance(n, ast.Assign) else [n.target]) if isinstance(t, ast.Name)])


def _capas_con_el_gris(valor, conocidas):
    """¿Esta expresión de módulo construye una lista, un conjunto o un dict de capas que lleva el gris? El literal «gris» como elemento o como clave, `dict(..., gris=...)`, una suma de tuplas
    (`CAPAS + ("gris",)`), `tuple(...)` de una de ellas o una referencia a una ya conocida. (No mira dentro de los VALORES de un dict: un dict de parámetros con un «gris» anidado no es una lista de capas.)"""
    if isinstance(valor, ast.Starred):
        return _capas_con_el_gris(valor.value, conocidas)
    if isinstance(valor, (ast.Tuple, ast.List, ast.Set)):
        return any(_capas_con_el_gris(e, conocidas) for e in valor.elts)
    if isinstance(valor, ast.Dict):
        return any(_capas_con_el_gris(k if k is not None else v, conocidas) for k, v in zip(valor.keys, valor.values))
    if isinstance(valor, ast.Constant):
        return valor.value == "gris"
    if isinstance(valor, ast.BinOp) and isinstance(valor.op, (ast.Add, ast.BitOr)):
        return _capas_con_el_gris(valor.left, conocidas) or _capas_con_el_gris(valor.right, conocidas)
    if isinstance(valor, ast.Call) and (valor.func.id if isinstance(valor.func, ast.Name) else getattr(valor.func, "attr", None)) in ("tuple", "list", "set", "frozenset", "sorted", "dict"):
        return any(_capas_con_el_gris(a, conocidas) for a in valor.args) or any(k.arg == "gris" or _capas_con_el_gris(k.value, conocidas) for k in valor.keywords)
    if isinstance(valor, ast.Name):
        return valor.id in conocidas
    if isinstance(valor, ast.Attribute):
        return valor.attr in conocidas
    return False


def estructuras_con_el_gris(fuentes):
    """Los nombres de nivel de módulo, en TODO el árbol, que son una lista, un conjunto o un dict de capas con el gris. Se LEEN del árbol (no son una lista escrita a mano: CD9-REV-AMB-3): hoy
    `CAPAS_DEL_PISO` y `CAPAS_QUE_LA_VIRGEN_NO_PUEDE_TENER_MAS_OSCURAS` (pelicula.py), `ADJETIVO_DE_LA_CAPA`, `COLOR_CAPA`... Recorrerlas recorre el gris; INDEXARLAS (`COLOR_CAPA[capa]`) no."""
    asignaciones = [(nombre, valor) for _, arbol in fuentes.values() for nombre, valor in _asignaciones_de_modulo(arbol)]
    conocidas = set()
    cambio = True
    while cambio:
        cambio = False
        for nombre, valor in asignaciones:
            if nombre not in conocidas and _capas_con_el_gris(valor, conocidas):
                conocidas.add(nombre)
                cambio = True
    return conocidas


def _indexados(arbol):
    """Los ids de los nodos que son el `value` de un `x[...]`: usar `COLOR_CAPA[capa]` o `resultado.capas[capa]` no recorre nada."""
    return _recordado("indexados", arbol, lambda a: {id(s.value) for s in _nodos(a) if isinstance(s, ast.Subscript)})


def _es_referencia_a(nodo, estructuras, enlaces):
    """¿Este nodo nombra una de las `estructuras` (`CAPAS_DEL_PISO`, `pel.CAPAS_DEL_PISO` o un nombre importado como alias suyo)?"""
    if isinstance(nodo, ast.Name):
        return isinstance(nodo.ctx, ast.Load) and (nodo.id in estructuras or any(d.rpartition(".")[2] in estructuras for d in enlaces.get(nodo.id, ())))
    return isinstance(nodo, ast.Attribute) and nodo.attr in estructuras


def _de_una_curva(nodo):
    """El objeto es «una curva» si su expresión dice «curva» (CD9-D13, vetable): `curva`, `self._curva`, `resultado.curva`."""
    return "curva" in ast.unparse(nodo).lower()


def _recorre_las_capas(nodo, indexados):
    """¿Es el dict `.capas` de un resultado SIN indexar? Lleva las cuatro capas (el motor lo arma con `CAPAS_DEL_PISO`): recorrerlo recorre el gris sin escribir nunca «gris». El de una curva solo trae R, G y B."""
    return isinstance(nodo, ast.Attribute) and nodo.attr == "capas" and id(nodo) not in indexados and not _de_una_curva(nodo.value)


def usos_del_gris(fuentes, modulos=VISTA_MENSUAL):
    """[(ruta, función, línea, qué)] en la ventana mensual, su dibujo y su PDF: (a) el literal «gris» o `.gris`; (b) una estructura de capas que lo lleva (`estructuras_con_el_gris`, leídas del árbol) que no se
    INDEXE; (c) el dict `.capas` de un resultado que no se indexe. Dibujar el perfil del gris exige alguna de las tres, escrita como sea."""
    estructuras = estructuras_con_el_gris(fuentes)
    hallados = []
    for ruta in modulos:
        _, arbol = fuentes[ruta]
        contenedora = _funcion_contenedora(arbol)
        enlaces, indexados = _enlaces(ruta, arbol), _indexados(arbol)
        for n in _nodos(arbol):
            if isinstance(n, ast.Constant) and n.value == "gris":
                hallados.append((ruta, contenedora.get(id(n)), n.lineno, "«gris»"))
            elif isinstance(n, ast.Attribute) and n.attr == "gris":
                hallados.append((ruta, contenedora.get(id(n)), n.lineno, ".gris"))
            elif _es_referencia_a(n, estructuras, enlaces) and id(n) not in indexados:
                hallados.append((ruta, contenedora.get(id(n)), n.lineno, "una lista de capas con el gris"))
            elif _recorre_las_capas(n, indexados):
                hallados.append((ruta, contenedora.get(id(n)), n.lineno, "recorre el dict de capas del resultado (lleva el gris)"))
    return sorted(hallados, key=_orden)


class TestDA93:
    def test_los_rotulos_de_la_tabla_no_se_copian(self, produccion):
        assert not rotulos_copiados(produccion), f"la tabla de la capa reportada es UNA (`filas_de_la_capa_reportada`): {rotulos_copiados(produccion)}"

    def test_no_vacuidad_los_rotulos_se_leen_de_la_tabla(self, produccion):
        rotulos = rotulos_de_la_tabla(produccion)
        assert {"Lado {} (radiación − luz) [mm]", "Radiación − cruce de diagonales (x; y) [mm]", "Radiación − retículo (x; y) [mm]"} <= set(rotulos), rotulos

    @pytest.mark.parametrize("ruta", [VENTANA_PLACA, SECCION_PDF])
    def test_discrimina_un_rotulo_copiado(self, produccion, ruta):
        hallados = rotulos_copiados(_con(produccion, ruta, "def _intrusa():\n    return [('Radiación − retículo (x; y) [mm]', '0.1'), ('Lado izquierdo (radiación − luz) [mm]', '0.2')]\n"))
        assert len([h for h in hallados if h[1] == "_intrusa"]) == 2, hallados

    def test_un_solo_cuadrado_perfecto(self, produccion):
        assert not problemas_del_cuadrado(produccion), problemas_del_cuadrado(produccion)

    @pytest.mark.parametrize("viejo, nuevo", [("    lado = LADO_DEL_CUADRADO_PERFECTO_MM\n", "    lado = 100.0\n"),
                                              ("    mitad = LADO_DEL_CUADRADO_PERFECTO_MM / 2.0\n", "    mitad = 50.0\n")], ids=["las_filas", "las_esquinas"])
    def test_discrimina_el_lado_escrito_a_mano(self, produccion, viejo, nuevo):
        assert problemas_del_cuadrado(_con_reemplazo(produccion, DIBUJO_PLACA, viejo, nuevo))

    def test_discrimina_un_texto_de_100_mm_y_una_segunda_definicion(self, produccion):
        assert problemas_del_cuadrado(_con(produccion, SECCION_PDF, "TEXTO = 'contra un cuadrado de 100 mm'\n"))
        assert problemas_del_cuadrado(_con(produccion, VENTANA_PLACA, "LADO_DEL_CUADRADO_PERFECTO_MM = 100.0\n"))

    def test_la_info_no_copia_textos(self, produccion):
        assert not problemas_de_la_info(produccion), problemas_de_la_info(produccion)

    @pytest.mark.parametrize("viejo, nuevo", [
        ("        for etiqueta in etiquetas:\n            capa.addWidget(etiqueta)\n", "        for etiqueta in etiquetas:\n            capa.addWidget(QLabel(etiqueta.text()))\n"),
        ('EXPLICACIONES_EN_LA_INFO = ("etiqueta_marcas",', 'EXPLICACIONES_EN_LA_INFO = ("etiqueta_que_no_existe",'),
        ("tuple(getattr(self, nombre) for nombre in EXPLICACIONES_EN_LA_INFO)", "(self.etiqueta_marcas, self.etiqueta_piso)"),
    ], ids=["el_cuadro_crea_su_texto", "un_nombre_que_no_es_widget", "la_lista_escrita_a_mano"])
    def test_discrimina_una_info_que_copia(self, produccion, viejo, nuevo):
        assert problemas_de_la_info(_con_reemplazo(produccion, VENTANA_PLACA, viejo, nuevo))

    def test_ningun_perfil_del_gris(self, produccion):
        fuera = _sin_permitidos(usos_del_gris(produccion), GRIS_PERMITIDO)
        assert not fuera, f"el gris en la ventana mensual, su dibujo o su PDF fuera de los sitios declarados (DA-93: ningún perfil gris): {fuera}"

    def test_cada_sitio_del_gris_declarado_sigue_existiendo(self, produccion):
        assert _usados(usos_del_gris(produccion), GRIS_PERMITIDO) == set(GRIS_PERMITIDO), set(GRIS_PERMITIDO) - _usados(usos_del_gris(produccion), GRIS_PERMITIDO)

    @pytest.mark.parametrize("ruta, agregado", [
        (DIBUJO_PLACA, "def _intruso(ax, resultado):\n    dibujar_perfil(ax, resultado.capas['gris'].crossplane, 'gris')\n"),
        (SECCION_PDF, "def _intruso(ax, resultado):\n    for capa in pel.CAPAS_DEL_PISO:\n        dibujar_perfil(ax, resultado.capas[capa].crossplane, capa)\n"),
        (VENTANA_PLACA, "def _intruso(self):\n    return self._resultado.capas['gris']\n"),
    ], ids=["el_dibujo", "el_pdf_recorre_las_cuatro", "la_ventana"])
    def test_discrimina_un_perfil_gris(self, produccion, ruta, agregado):
        assert [h for h in _sin_permitidos(usos_del_gris(_con(produccion, ruta, agregado)), GRIS_PERMITIDO) if h[1] == "_intruso"]

    @pytest.mark.parametrize("ruta", list(VISTA_MENSUAL), ids=["el_dibujo", "la_ventana", "el_pdf"])
    @pytest.mark.parametrize("cuerpo", [
        "    for capa, medida in resultado.capas.items():\n        dibujar_perfil(ax, medida.crossplane, capa)\n",
        "    for capa in resultado.capas:\n        dibujar_perfil(ax, resultado.capas[capa].crossplane, capa)\n",
        "    return [m.crossplane for m in resultado.capas.values()]\n",
        "    todas = resultado.capas\n    return [todas[c] for c in sorted(todas)]\n",
    ], ids=["items", "claves", "valores", "alias_del_dict"])
    def test_discrimina_recorrer_el_dict_de_capas_del_resultado(self, produccion, ruta, cuerpo):
        """CD9-REV-AMB-1 (b): el dict `.capas` de un resultado lleva las CUATRO capas (el motor lo arma con `CAPAS_DEL_PISO`): recorrerlo dibuja el perfil gris sin escribir nunca «gris». En la vista
        mensual `.capas` solo se usa con un indice (`resultado.capas[capa]`)."""
        agregado = "def _intruso(ax, resultado):\n" + cuerpo
        assert [h for h in _sin_permitidos(usos_del_gris(_con(produccion, ruta, agregado)), GRIS_PERMITIDO) if h[1] == "_intruso"]

    @pytest.mark.parametrize("ruta, agregado", [
        (DIBUJO_PLACA, "CAPAS_DE_LOS_PERFILES = ('R', 'G', 'B', 'gris')\n"),
        (DIBUJO_PLACA, "ORDEN = ('R', 'G', 'B', 'gris')\ndef _intruso(ax, resultado):\n    for capa in ORDEN:\n        dibujar_perfil(ax, resultado.capas[capa].crossplane, capa)\n"),
        (DIBUJO_PLACA, "COLOR_CAPA['gris'] = '#000000'\n"),
        (VENTANA_PLACA, "CAPAS_DE_LA_PESTANA = ('R', 'G', 'B', 'gris')\n"),
        (SECCION_PDF, "class _Perfiles:\n    CAPAS = ('R', 'G', 'B', 'gris')\n"),
    ], ids=["tupla_de_modulo_en_el_dibujo", "tupla_de_modulo_recorrida", "otro_enunciado_de_modulo_en_el_dibujo", "tupla_de_modulo_en_la_ventana", "atributo_de_clase_en_el_pdf"])
    def test_discrimina_una_estructura_con_el_gris_fuera_de_su_sitio(self, produccion, ruta, agregado):
        """CD9-REV-AMB-1 (a): lo unico de NIVEL DE MODULO que puede llevar el gris es el dict `COLOR_CAPA` del dibujo (el color de cada capa); la excepcion ya no es «todo el modulo del dibujo»."""
        fuera = [h for h in _sin_permitidos(usos_del_gris(_con(produccion, ruta, agregado)), GRIS_PERMITIDO) if h[0] == ruta]
        assert fuera, usos_del_gris(_con(produccion, ruta, agregado))

    @pytest.mark.parametrize("ruta, agregado", [
        (SECCION_PDF, "def _intruso(ax, resultado):\n    for capa in pel.CAPAS_QUE_LA_VIRGEN_NO_PUEDE_TENER_MAS_OSCURAS:\n        dibujar_perfil(ax, resultado.capas[capa].crossplane, capa)\n"),
        (DIBUJO_PLACA, "def _intruso(ax, resultado):\n    for capa in COLOR_CAPA:\n        dibujar_perfil(ax, resultado.capas[capa].crossplane, capa)\n"),
        (VENTANA_PLACA, "def _intruso(self):\n    return list(pel.ADJETIVO_DE_LA_CAPA)\n"),
        (DIBUJO_PLACA, "from analisisImagenes.pelicula import CAPAS_DEL_PISO as TODAS\ndef _intruso(ax, resultado):\n    for capa in TODAS:\n        dibujar_perfil(ax, resultado.capas[capa].crossplane, capa)\n"),
    ], ids=["la_otra_lista_del_arbol_con_el_gris", "un_dict_por_capa_recorrido", "las_claves_de_un_dict_por_capa", "la_lista_del_piso_con_otro_nombre"])
    def test_discrimina_una_estructura_del_arbol_que_lleva_el_gris(self, produccion, ruta, agregado):
        """CD9-REV-AMB-3 (y 1): las listas y los dicts de capas que llevan el gris se LEEN del arbol (no son una lista escrita a mano): hoy `CAPAS_DEL_PISO` y
        `CAPAS_QUE_LA_VIRGEN_NO_PUEDE_TENER_MAS_OSCURAS` (pelicula.py), `COLOR_CAPA` (el dibujo), `ADJETIVO_DE_LA_CAPA`... Se pueden INDEXAR (`COLOR_CAPA[capa]`), no recorrer."""
        assert [h for h in _sin_permitidos(usos_del_gris(_con(produccion, ruta, agregado)), GRIS_PERMITIDO) if h[1] == "_intruso"]

    @pytest.mark.parametrize("ruta", list(VISTA_MENSUAL), ids=["el_dibujo", "la_ventana", "el_pdf"])
    def test_no_marca_el_codigo_que_solo_recorre_las_capas_de_color(self, produccion, ruta):
        """El control de las guardas anchas: recorrer `CAPAS` (R, G y B), indexar `resultado.capas[capa]`, `COLOR_CAPA[capa]` y `ADJETIVO_DE_LA_CAPA[capa]` es lo que hace el codigo de hoy."""
        agregado = ("def _legitima(ax, resultado, capa):\n    for c in pel.CAPAS:\n        m = resultado.capas[c]\n        ax.plot([0], [0], color=COLOR_CAPA[c], label=pel.ADJETIVO_DE_LA_CAPA[c])\n"
                    "    return resultado.capas[capa], len(resultado.parametros), resultado.capas['G']\n")
        assert not [h for h in _sin_permitidos(usos_del_gris(_con(produccion, ruta, agregado)), GRIS_PERMITIDO) if h[1] == "_legitima"]


# ======================================================================================================== 6e. DA-94: ninguna curva de la capa gris en la parte de dosis

PARTE_DE_DOSIS = (MOTOR_CURVA, SERVICIO_CURVA, DIBUJO_CURVA, VENTANA_CURVA, SECCION_PDF)      # la curva (CD.3 a CD.5) y el PDF en dosis (CD.8): ni el gris ni la lista con el gris
MOTOR_MENSUAL_Y_SU_DIBUJO = (MOTOR_PLACA, DIBUJO_PLACA)        # miden y dibujan las cuatro capas (el piso, DA-93), pero a una curva solo le piden las capas de la curva
METODOS_DE_LA_CURVA = ("estado", "rango", "dosis", "netod", "incertidumbre")
CURVA_DEL_GRIS_PERMITIDA = {}                              # VACÍA a propósito: lo pidió el físico («de ningún tipo», DA-94); CD.5b cerró el último sitio (`eje_de_la_dosis`, H-CD9-9)
PALABRA_GRIS = re.compile(r"\bgris\b", re.IGNORECASE)


def pedidos_a_la_curva(fuentes, ruta):
    """[(función, línea, qué pide, recorre)] de cada `curva.<estado|rango|dosis|netod|incertidumbre>(...)` y cada `curva.capas[...]` de `ruta` (el objeto se llama «curva»), con «recorre» = la LISTA de
    los iterables de TODOS los `for` y comprensiones que lo contienen (cada generador de una comprensión), del más exterior al más interior: lo que alimenta el pedido puede venir de cualquiera de ellos."""
    _, arbol = fuentes[ruta]
    contenedora = _funcion_contenedora(arbol)
    recorre = {}
    for n in _nodos(arbol):
        if isinstance(n, ast.For):
            dentro, iterables = [x for s in n.body + n.orelse for x in ast.walk(s)], [n.iter]
        elif isinstance(n, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            dentro, iterables = list(ast.walk(n)), [g.iter for g in n.generators]
        else:
            continue
        for x in dentro:
            recorre.setdefault(id(x), []).extend(iterables)          # _nodos va de afuera hacia adentro: el bucle más exterior queda el primero
    salida = []
    for n in _nodos(arbol):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in METODOS_DE_LA_CURVA and _de_una_curva(n.func.value):
            pide = (n.func.attr, [*n.args, *(k.value for k in n.keywords)])
        elif isinstance(n, ast.Subscript) and isinstance(n.value, ast.Attribute) and n.value.attr == "capas" and _de_una_curva(n.value.value):
            pide = ("capas", [n.slice])
        else:
            continue
        salida.append((contenedora.get(id(n)), n.lineno, pide, recorre.get(id(n), [])))
    return salida


def _calcular_ambitos(arbol):
    ambitos = {id(arbol): None}

    def visitar(nodo, ambito):
        for hijo in ast.iter_child_nodes(nodo):
            propio = id(hijo) if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef)) else ambito
            ambitos[id(hijo)] = propio
            visitar(hijo, propio)

    visitar(arbol, None)
    return ambitos


def _lo_que_trae_el_gris(fuentes, ruta, estructuras):
    """`trae(nodo)`: ¿este trozo de `ruta` trae el gris? El literal «gris», `.gris`, una estructura de capas con el gris o el dict `.capas` de un resultado SIN indexar, o un nombre al que se le asignó algo así
    en su función (o a nivel de módulo, que vale para todo el archivo), por asignación o por omisión de un parámetro (`_todas = resultado.capas`, `capas = CAPAS_DEL_PISO`, `def f(curva, capas=CAPAS_DEL_PISO)`):
    un alias local no lo esconde (CD9-REV-AMB-3) y el alias de una función no contamina a otra que usa el mismo nombre para otra cosa."""
    _, arbol = fuentes[ruta]
    enlaces, indexados = _enlaces(ruta, arbol), _indexados(arbol)
    ambitos = _recordado("ambitos", arbol, _calcular_ambitos)
    portadores = {}                                              # {ámbito: nombres que traen el gris}; ámbito = id de la función (None: el nivel de módulo)

    def trae(nodo):
        propios = portadores.get(ambitos.get(id(nodo)), set()) | portadores.get(None, set())
        for x in ast.walk(nodo):
            if (isinstance(x, ast.Constant) and x.value == "gris") or (isinstance(x, ast.Attribute) and x.attr == "gris"):
                return True
            if id(x) not in indexados and (_es_referencia_a(x, estructuras, enlaces) or _recorre_las_capas(x, indexados)
                                           or (isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load) and x.id in propios)):
                return True
        return False

    asignaciones = [(ambitos[id(a)], t.id, a.value) for a in _nodos(arbol) if isinstance(a, ast.Assign) for t in a.targets if isinstance(t, ast.Name)]
    for f in _nodos(arbol):
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):          # el valor por omisión de un parámetro es una asignación dentro de su función
            posicionales = [*f.args.posonlyargs, *f.args.args]
            asignaciones += [(id(f), a.arg, d) for a, d in zip(posicionales[len(posicionales) - len(f.args.defaults):], f.args.defaults)]
            asignaciones += [(id(f), a.arg, d) for a, d in zip(f.args.kwonlyargs, f.args.kw_defaults) if d is not None]
    for _ in range(3):
        for ambito, nombre, valor in asignaciones:
            if trae(valor):
                portadores.setdefault(ambito, set()).add(nombre)
    return trae


def curvas_del_gris(fuentes):
    """[(ruta, función, línea, qué)]: (a) en la parte de dosis, el literal «gris» (fuera de los docstrings), `.gris` o una estructura de capas con el gris (`estructuras_con_el_gris`, leídas del árbol) sin indexar;
    (b) en el motor mensual y su dibujo, un pedido a una curva con el literal «gris» o dentro de un `for`/comprensión que recorre algo que trae el gris (`_lo_que_trae_el_gris`)."""
    estructuras = estructuras_con_el_gris(fuentes)
    hallados = []
    for ruta in PARTE_DE_DOSIS:
        _, arbol = fuentes[ruta]
        contenedora = _funcion_contenedora(arbol)
        enlaces, indexados = _enlaces(ruta, arbol), _indexados(arbol)
        for n in _nodos(arbol):
            if _es_referencia_a(n, estructuras, enlaces) and id(n) not in indexados:
                hallados.append((ruta, contenedora.get(id(n)), n.lineno, "una lista de capas con el gris"))
            elif isinstance(n, ast.Attribute) and n.attr == "gris":
                hallados.append((ruta, contenedora.get(id(n)), n.lineno, ".gris"))
        hallados += [(ruta, contenedora.get(id(n)), n.lineno, f"«gris» en un texto: {t[:50]!r}") for n, t in _literales(arbol) if PALABRA_GRIS.search(t)]
    for ruta in MOTOR_MENSUAL_Y_SU_DIBUJO:
        trae = _lo_que_trae_el_gris(fuentes, ruta, estructuras)
        for funcion, linea, (metodo, argumentos), iterables in pedidos_a_la_curva(fuentes, ruta):
            if any(trae(a) for a in argumentos):
                hallados.append((ruta, funcion, linea, f"pide a una curva {metodo} del gris"))
            else:
                hallados += [(ruta, funcion, linea, f"pide a una curva {metodo} recorriendo {ast.unparse(it)[:40]}") for it in iterables if trae(it)]
    return sorted(hallados, key=_orden)


class TestNingunaCurvaDelGris:
    def test_ninguna_curva_del_gris_en_la_parte_de_dosis(self, produccion):
        hallados = curvas_del_gris(produccion)
        fuera = _sin_permitidos(hallados, CURVA_DEL_GRIS_PERMITIDA)
        assert not fuera, f"la parte de dosis tiene una curva de la capa gris (DA-94: «de ningún tipo»; la curva es de `CAPAS_DE_LA_CURVA`, R, G y B): {fuera}"
        assert _usados(hallados, CURVA_DEL_GRIS_PERMITIDA) == set(CURVA_DEL_GRIS_PERMITIDA)

    def test_no_vacuidad_la_curva_tiene_sus_capas_y_la_guarda_ve_los_bucles(self, produccion):
        assert "CAPAS_DE_LA_CURVA" in _definiciones_de_modulo(produccion[MOTOR_CURVA][1]), "el motor de la curva ya no define `CAPAS_DE_LA_CURVA` (DA-94)"
        recorridos = {(funcion, ast.unparse(iterable)) for funcion, _, _, iterables in pedidos_a_la_curva(produccion, DIBUJO_PLACA) for iterable in iterables}
        assert ("eje_de_la_dosis", "motor.CAPAS_DE_LA_CURVA") in recorridos, f"la guarda ya no ve el bucle del eje de la dosis sobre las capas de la curva: {recorridos}"

    @pytest.mark.parametrize("agregados, esperados", [
        ([(DIBUJO_PLACA, "def _intruso(curva):\n    return [curva.rango(c) for c in motor.CAPAS_DEL_PISO]\n")], {(DIBUJO_PLACA, "pide a una curva rango recorriendo motor.CAPAS_DEL_PISO")}),
        ([(MOTOR_PLACA, "def _intruso(curva):\n    return curva.estado('gris'), curva.capas['gris']\n"),
          (SECCION_PDF, "def _intruso(resultado):\n    return [resultado.capas[c] for c in pel.CAPAS_DEL_PISO], resultado.gris, 'la capa gris'\n")],
         {(MOTOR_PLACA, "pide a una curva estado del gris"), (MOTOR_PLACA, "pide a una curva capas del gris"), (SECCION_PDF, "una lista de capas con el gris"),
          (SECCION_PDF, ".gris"), (SECCION_PDF, "«gris» en un texto: 'la capa gris'")}),
        # CD9-REV-AMB-3: la lista con el gris se LEE del arbol (hay mas de una: pelicula.py tiene `CAPAS_QUE_LA_VIRGEN_NO_PUEDE_TENER_MAS_OSCURAS`) y un alias local no la esconde
        ([(DIBUJO_CURVA, "def _intruso(curva):\n    return [curva.rango(c) for c in pel.CAPAS_QUE_LA_VIRGEN_NO_PUEDE_TENER_MAS_OSCURAS]\n")], {(DIBUJO_CURVA, "una lista de capas con el gris")}),
        ([(MOTOR_PLACA, "def _intruso(curva):\n    _las_cuatro = CAPAS_DEL_PISO\n    return [curva.estado(c) for c in _las_cuatro]\n")], {(MOTOR_PLACA, "pide a una curva estado recorriendo _las_cuatro")}),
        ([(MOTOR_PLACA, "def _intruso(curva, resultado):\n    return [curva.rango(c) for c in resultado.capas]\n")], {(MOTOR_PLACA, "pide a una curva rango recorriendo resultado.capas")}),
        ([(DIBUJO_PLACA, "def _intruso(curva, resultado):\n    for c, m in resultado.capas.items():\n        curva.estado(c)\n")], {(DIBUJO_PLACA, "pide a una curva estado recorriendo resultado.capas.items()")}),
        ([(MOTOR_PLACA, "def _intruso(curva, resultado):\n    _todas = resultado.capas\n    return [curva.estado(c) for c in _todas]\n")], {(MOTOR_PLACA, "pide a una curva estado recorriendo _todas")}),
        ([(MOTOR_PLACA, "def _intruso(curva, _capas=CAPAS_DEL_PISO):\n    return [curva.estado(c) for c in _capas]\n")], {(MOTOR_PLACA, "pide a una curva estado recorriendo _capas")}),
        # el pedido puede estar en un bucle INTERIOR: lo que lo alimenta es el iterable de cualquiera de los bucles que lo contienen (y de cualquier generador de una comprension)
        ([(MOTOR_PLACA, "def _intruso(curva):\n    for c in CAPAS_DEL_PISO:\n        for eje in EJES:\n            curva.rango(c)\n")], {(MOTOR_PLACA, "pide a una curva rango recorriendo CAPAS_DEL_PISO")}),
        ([(MOTOR_PLACA, "def _intruso(curva):\n    return [curva.estado(c) for eje in EJES for c in CAPAS_DEL_PISO]\n")], {(MOTOR_PLACA, "pide a una curva estado recorriendo CAPAS_DEL_PISO")}),
    ], ids=["el_dibujo_recorre_el_gris", "el_motor_pide_el_gris_y_el_pdf_lo_nombra", "otra_lista_del_arbol_con_el_gris", "alias_local_de_la_lista_del_piso", "recorre_el_dict_de_capas",
            "recorre_el_dict_de_capas_en_el_dibujo", "alias_local_del_dict_de_capas", "capas_por_omision_de_un_parametro", "bucle_exterior_con_otro_bucle_dentro", "segundo_generador_de_una_comprension"])
    def test_discrimina_una_curva_del_gris(self, produccion, agregados, esperados):
        fuentes = produccion
        for ruta, agregado in agregados:
            fuentes = _con(fuentes, ruta, agregado)
        hallados = {(r, q) for r, f, _, q in _sin_permitidos(curvas_del_gris(fuentes), CURVA_DEL_GRIS_PERMITIDA) if f == "_intruso"}
        assert hallados == esperados, hallados

    @pytest.mark.parametrize("ruta, agregado", [
        (MOTOR_PLACA, "def _legitima(curva, capas):\n    return [curva.estado(c) for c in capas]\n"),
        (MOTOR_PLACA, "def _legitima(curva):\n    capas = CAPAS_DE_LA_CURVA\n    return [curva.rango(c) for c in capas]\n"),
        (DIBUJO_PLACA, "def _legitima(curva, resultado):\n    todas = list(motor.CAPAS_DE_LA_CURVA)\n    return [curva.rango(c) for c in todas if resultado.capas[c].ok]\n"),
    ], ids=["un_parametro_que_se_llama_como_un_alias_de_otra_funcion", "un_alias_de_las_capas_de_la_curva", "las_capas_de_la_curva_con_el_resultado_indexado"])
    def test_no_marca_el_pedido_a_la_curva_de_las_capas_de_color(self, produccion, ruta, agregado):
        """El control: un nombre que es alias de la lista con el gris en OTRA función del archivo (el motor mensual tiene `capas = {... for nombre in CAPAS_DEL_PISO}`) no contamina a una función que
        pide a la curva solo sus capas (R, G y B): el alias vale dentro de su función (y de módulo para todo el archivo)."""
        assert not [h for h in curvas_del_gris(_con(produccion, ruta, agregado)) if h[1] == "_legitima"]


# ======================================================================================================== 7. el empaquetado

def lista_de_hidden_imports(fuentes):
    _, arbol = fuentes[BUILD]
    listas = [n.value for n in arbol.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "hidden_imports" for t in n.targets)]
    if len(listas) != 1 or not isinstance(listas[0], ast.List):
        return None
    return [e.value for e in listas[0].elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]


def importaciones_dinamicas(fuentes, modulos=MODULOS_DEL_PLAN):
    hallados = []
    for ruta in modulos:
        _, arbol = fuentes[ruta]
        contenedora = _funcion_contenedora(arbol)
        for n in _nodos(arbol):
            if (isinstance(n, ast.Name) and n.id in ("importlib", "__import__")) or (isinstance(n, ast.Import) and any(a.name.startswith("importlib") for a in n.names)) \
                    or (isinstance(n, ast.ImportFrom) and (n.module or "").startswith("importlib")):
                hallados.append((ruta, contenedora.get(id(n)), n.lineno, "importación dinámica"))
    nuevos = tuple(_punteado(r) for r in MODULOS_NUEVOS)
    for ruta, (_, arbol) in fuentes.items():
        if ruta == BUILD:
            continue
        contenedora = _funcion_contenedora(arbol)
        hallados += [(ruta, contenedora.get(id(n)), n.lineno, f"nombra un módulo nuevo en un texto: {t!r}") for n, t in _literales(arbol) if t.startswith(nuevos)]
    return sorted(hallados, key=_orden)


class TestElEmpaquetado:
    def test_los_modulos_nuevos_estan_una_vez_en_hidden_imports(self, produccion):
        nombres = lista_de_hidden_imports(produccion)
        assert nombres is not None and len(nombres) >= 20, "build_exe.py ya no tiene UNA lista `hidden_imports` de módulo"
        for modulo in tuple(_punteado(r) for r in MODULOS_NUEVOS) + EMPAQUETADOS_POR_CD7:
            assert nombres.count(modulo) == 1, f"{modulo} está {nombres.count(modulo)} veces en hidden_imports"

    def test_ninguna_importacion_dinamica(self, produccion):
        assert not importaciones_dinamicas(produccion), importaciones_dinamicas(produccion)

    def test_discrimina_un_modulo_que_falta_o_esta_dos_veces(self, produccion):
        texto = produccion[BUILD][0]
        for viejo, nuevo in (('"services.curva_dosis",', ""), ('"services.curva_dosis",', '"services.curva_dosis", "services.curva_dosis",')):
            assert texto.count(viejo) == 1
            otro = texto.replace(viejo, nuevo)
            nombres = lista_de_hidden_imports({**produccion, BUILD: (otro, ast.parse(otro))})
            assert nombres.count("services.curva_dosis") != 1

    @pytest.mark.parametrize("ruta, agregado", [
        (VENTANA_PLACA, "import importlib\n"),
        (SERVICIO_PLACA, "def _x():\n    return __import__('analisisImagenes.curva_dosis')\n"),
        ("ui/paginasControles/otra.py", "PAGINA = 'ui.paginasControles.PruebasMensuales.curva_dosis'\n"),
    ], ids=["importlib", "dunder_import", "por_nombre_en_otro_modulo"])
    def test_discrimina_una_importacion_dinamica(self, produccion, ruta, agregado):
        fuentes = _con(produccion, ruta, agregado)
        assert [h for h in importaciones_dinamicas(fuentes, MODULOS_DEL_PLAN + ((ruta,) if ruta not in MODULOS_DEL_PLAN else ())) if h[0] == ruta]


# ======================================================================================================== 8. una sola conversión de ppp a mm

def _es_25_4_entre_algo(n):
    return isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div) and (
        any(isinstance(x, ast.Constant) and x.value == 25.4 for x in ast.walk(n.left)) or (isinstance(n.right, ast.Constant) and n.right.value == 25.4))


def divisiones_de_25_4(fuentes, modulos=MODULOS_DEL_PLAN):
    hallados = []
    for ruta in modulos:
        _, arbol = fuentes[ruta]
        contenedora = _funcion_contenedora(arbol)
        hallados += [(ruta, contenedora.get(id(n)), n.lineno) for n in _nodos(arbol) if _es_25_4_entre_algo(n)]
    return sorted(hallados, key=_orden)


class TestUnaSolaEscala:
    def test_solo_escala_mm_divide_25_4(self, produccion):
        hallados = divisiones_de_25_4(produccion)
        assert not _sin_permitidos(hallados, DIVISIONES_DE_25_4_PERMITIDAS), _sin_permitidos(hallados, DIVISIONES_DE_25_4_PERMITIDAS)
        assert _usados(hallados, DIVISIONES_DE_25_4_PERMITIDAS) == set(DIVISIONES_DE_25_4_PERMITIDAS), "no vacuidad: `escala_mm` divide 25.4"

    @pytest.mark.parametrize("ruta", [r for r in MODULOS_DEL_PLAN if r != PELICULA])
    @pytest.mark.parametrize("expresion", ["25.4 / dpi", "dpi / 25.4", "(25.4 * k) / dpi"])
    def test_discrimina_una_division_nueva(self, produccion, ruta, expresion):
        hallados = divisiones_de_25_4(_con(produccion, ruta, f"def _intrusa(dpi, k=1):\n    return {expresion}\n"))
        assert (ruta, "_intrusa") in {(r, f) for r, f, _ in _sin_permitidos(hallados, DIVISIONES_DE_25_4_PERMITIDAS)}


# ======================================================================================================== 9. un solo llamador del ajuste con parámetros

def llamadas_a_ajustar(fuentes):
    """[(ruta, función, línea, «con P» o «sin P»)] de cada llamada a `ajustar` del motor de la curva fuera de él (por su alias o importada)."""
    hallados = []
    for ruta in fuentes:
        if ruta == MOTOR_CURVA:
            continue
        for f, nombre, l, n in _llamadas_al_modulo(fuentes, ruta, MODULO_MOTOR_CURVA):
            if nombre == "ajustar":
                con_p = len(n.args) >= 2 or any(k.arg in ("P", None) for k in n.keywords)
                hallados.append((ruta, f, l, "con P" if con_p else "sin P"))
    return sorted(hallados, key=_orden)


class TestUnSoloLlamadorDelAjuste:
    def test_ajustar_solo_lo_llaman_los_declarados_y_como_se_declaro(self, produccion):
        hallados = llamadas_a_ajustar(produccion)
        mal = [h for h in hallados if (h[0], h[1]) not in LLAMADORES_DE_AJUSTAR or LLAMADORES_DE_AJUSTAR[(h[0], h[1])][0] != h[3]]
        assert not mal, f"`ajustar` del motor de la curva: un llamador no declarado, o que pasa `P` sin ser el servicio: {mal}"

    def test_cada_llamador_declarado_sigue_llamando(self, produccion):
        assert {(r, f) for r, f, _, _ in llamadas_a_ajustar(produccion)} == set(LLAMADORES_DE_AJUSTAR)

    @pytest.mark.parametrize("ruta, agregado", [
        (VENTANA_PLACA, "def _intruso(piezas):\n    return motor_curva.ajustar(piezas)\n"),
        (SECCION_PDF, "from analisisImagenes.curva_dosis import ajustar as _a\ndef _intruso(piezas):\n    return _a(piezas, P={'x': 1})\n"),
        # CD9-REV-AMB-6: la ruta calificada sin alias, la importacion relativa y el alias por asignacion
        (VENTANA_PLACA, "import analisisImagenes.curva_dosis\ndef _intruso(piezas):\n    return analisisImagenes.curva_dosis.ajustar(piezas, P={'x': 1})\n"),
        (VENTANA_PLACA, "import analisisImagenes.curva_dosis as _c\ndef _intruso(piezas):\n    return _c.ajustar(piezas)\n"),
        (DIBUJO_PLACA, "from .curva_dosis import ajustar as _a\ndef _intruso(piezas):\n    return _a(piezas, P={'x': 1})\n"),
        (DIBUJO_PLACA, "from . import curva_dosis as _c\ndef _intruso(piezas):\n    return _c.ajustar(piezas, {'x': 1})\n"),
        (SECCION_PDF, "from analisisImagenes import curva_dosis as _m\n_ajusta = _m.ajustar\ndef _intruso(piezas):\n    return _ajusta(piezas, P={'x': 1})\n"),
    ], ids=["otro_modulo", "importada_con_P", "ruta_calificada_sin_alias", "ruta_calificada_con_alias", "importada_con_ruta_relativa", "modulo_relativo", "alias_por_asignacion"])
    def test_discrimina_un_llamador_nuevo(self, produccion, ruta, agregado):
        fuentes = _con(produccion, ruta, ("from analisisImagenes import curva_dosis as motor_curva\n" if "motor_curva" in agregado else "") + agregado)
        assert [h for h in llamadas_a_ajustar(fuentes) if h[0] == ruta and h[1] == "_intruso"]

    def test_discrimina_la_vista_previa_que_pasa_P(self, produccion):
        texto = produccion[VENTANA_CURVA][0]
        llamada = next(n for f, nombre, l, n in _llamadas_al_modulo(produccion, VENTANA_CURVA, MODULO_MOTOR_CURVA) if nombre == "ajustar")
        viejo = ast.get_source_segment(texto, llamada)
        fuentes = _con_reemplazo(produccion, VENTANA_CURVA, viejo, viejo[:-1] + ", P={'piezas_minimas': 2})")
        assert (VENTANA_CURVA, "_ajustar", "con P") in {(r, f, c) for r, f, _, c in llamadas_a_ajustar(fuentes)}


# ======================================================================================================== 9b. las excepciones se declaran por SITIO, nunca por «todo el módulo»

class TestLasExcepcionesSonPorSitio:
    """CD9-REV-AMB-1 y 4: una excepcion declarada con la funcion `None` dejaba pasar TODO lo que hubiera fuera de las funciones del archivo (una tupla de capas con el gris, una llamada al servicio en el
    cuerpo de una clase). Ahora lo que no esta dentro de una funcion nombra su enunciado (`=COLOR_CAPA`, `(import)`, `class X`, `(módulo)`) y cada excepcion se declara por funcion o por ese nombre."""

    @pytest.mark.parametrize("excepciones", [CONSTRUCTORES_DE_LA_CURVA_EFECTIVA, USOS_DEL_SERVICIO_DE_LA_CURVA, BASES_ESCRITAS_PERMITIDAS, GRIS_PERMITIDO, CURVA_DEL_GRIS_PERMITIDA,
                                              LLAMADORES_DE_AJUSTAR, DIVISIONES_DE_25_4_PERMITIDAS, *LLAMADORES_PERMITIDOS.values()],
                             ids=["constructores", "servicio_de_la_curva", "bases", "gris", "curva_del_gris", "ajustar", "25_4", *(f"llamadores_{r}" for r in LLAMADORES_PERMITIDOS)])
    def test_ninguna_excepcion_es_de_todo_el_modulo(self, excepciones):
        assert not [k for k in excepciones if k[1] is None], f"una excepcion con la funcion `None` deja pasar todo lo de modulo del archivo: {[k for k in excepciones if k[1] is None]}"

    def test_lo_que_esta_fuera_de_una_funcion_nombra_su_enunciado(self):
        fuente = ("import os\nfrom . import x\nCOLOR = {'gris': 1}\nA, B = 1, 2\nX: int = f()\nclass K:\n    V = g()\n    def metodo(self):\n        return h()\nif True:\n    y = 2\ndef libre():\n    return z()\n")
        arbol = ast.parse(fuente)
        sitios = _funcion_contenedora(arbol)
        por_linea = {}
        for n in ast.walk(arbol):
            if isinstance(n, (ast.Name, ast.Constant)) and hasattr(n, "lineno"):
                por_linea.setdefault(n.lineno, set()).add(sitios.get(id(n)))
        assert por_linea[3] == {"=COLOR"} and por_linea[5] == {"=X"} and por_linea[7] == {"class K"} and por_linea[9] == {"metodo"} and por_linea[11] == {"(módulo)"} and por_linea[13] == {"libre"}
        assert {sitios.get(id(n)) for n in arbol.body[:2]} == {"(import)"} and sitios.get(id(arbol.body[3])) == "(módulo)", "una asignacion a una tupla no nombra un unico destino"


# ======================================================================================================== 10. cada guarda dice si el árbol cambió de forma (Trampa 8)

class TestCadaGuardaDiceSiElArbolCambioDeForma:
    """Si el árbol deja de tener lo que una guarda vigila (una función renombrada, la lista movida), la guarda lo DICE en lugar de pasar en vacío."""

    @pytest.mark.parametrize("guarda, ruta, viejo, nuevo", [
        ("registro", VENTANA_PLACA, "    def _leer_la_curva(self):\n", "    def _leer_la_curva_otra(self):\n"),
        ("reabrir", VENTANA_PLACA, "    def abrir_guardado(self):\n", "    def abrir_guardado_otro(self):\n"),
        ("cuadrado", DIBUJO_PLACA, "def cuadrado_perfecto():\n", "def esquinas_ideales():\n"),
        ("info", VENTANA_PLACA, "class _DialogoInfo(QDialog):\n", "class _CuadroInfo(QDialog):\n"),
    ], ids=["leer_la_curva", "abrir_guardado", "cuadrado_perfecto", "dialogo_info"])
    def test_una_funcion_renombrada_se_dice(self, produccion, guarda, ruta, viejo, nuevo):
        fuentes = _con_reemplazo(produccion, ruta, viejo, nuevo)
        problemas = {"registro": problemas_de_la_guarda_del_registro, "reabrir": problemas_al_reabrir, "cuadrado": problemas_del_cuadrado, "info": problemas_de_la_info}[guarda](fuentes)
        assert problemas, guarda

    @pytest.mark.parametrize("agregado", ['EXPLICACIONES_EN_LA_INFO = ("etiqueta_marcas",)\n', 'EXPLICACIONES_EN_LA_INFO: tuple = ("etiqueta_marcas",)\n'], ids=["asignada", "anotada"])
    def test_una_segunda_lista_de_la_info_se_dice(self, produccion, agregado):
        assert problemas_de_la_info(_con(produccion, DIBUJO_PLACA, agregado))

    def test_build_exe_sin_su_lista_se_dice(self, produccion):
        texto = produccion[BUILD][0].replace("hidden_imports = [", "otros_imports = [", 1)
        assert lista_de_hidden_imports({**produccion, BUILD: (texto, ast.parse(texto))}) is None

    def test_sin_la_tabla_de_la_capa_reportada_no_hay_rotulos_y_la_no_vacuidad_lo_ve(self, produccion):
        fuentes = _con_reemplazo(produccion, DIBUJO_PLACA, "def filas_de_la_capa_reportada(", "def filas_de_otra_tabla(")
        assert rotulos_de_la_tabla(fuentes) == [] and "filas_de_la_capa_reportada" not in _definiciones_de_modulo(fuentes[DIBUJO_PLACA][1])
