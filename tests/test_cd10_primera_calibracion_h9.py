"""CD.10 (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, bloque CD.10, DA-90: «por ahora, con lo que tenemos»): LA PRIMERA CALIBRACION REAL, con las 21 piezas de H9 (Epson 12000XL declarada, 16 bits a
150 ppp, la dosis medida es la nominal, el cero es la pieza de 5 cGy: P14), hecha por el CAMINO REAL DE LA APP -- el servicio de CD.4 sobre una base NUEVA en un temporal -- y fijada aqui tal cual salio.
CAUSA: todo lo anterior estaba probado con piezas sinteticas; esto fija lo que da la app con piezas irradiadas de verdad, para que un cambio de la medicion, del cero, del modelo, de un umbral o de una
pieza se vea.
LO QUE SE GARANTIZA, cada cosa contra una verdad que no sale de lo que se prueba (las piezas leidas aqui, CD.2 llamado aqui, la copia guardada leida de vuelta):
  (1) El docstring de `ajustar` ya no promete lo falso (decision de Opus de la ronda 1 de CD.4, vetable): `P` no se valida en el motor -- lo pasa y lo valida solo `services/curva_dosis.py`, la ventana
      llama sin `P` (el censo por AST es el de la prueba de CD.9: aqui no se repite) -- y con un `P` de otro tipo `ajustar` lanza `TypeError`, mientras que el servicio lo rechaza con
      `CurvaDosisError` sin escribir nada. Y `texto_de_la_cadena` es publica (CD10-D12, cierra CD9-D3).
  (2) Las 21 por el servicio: los estados, los rangos y el cero de CD3-D17; la u de la netOD guardada es la ecuacion 2 de Vargas-Segura (DC3); lo guardado se rehace igual desde los escaneos; ninguna es
      vigente valida; una pelicula de la WF-6590 (8 bits a 600 ppp) sigue
      en netOD con el motivo de cada capa (condiciones 1 y 5 de DC8) y `curva_efectiva` no le da curva.
  (3) La pieza de verificacion: con la calibracion SIN la de 350 cGy, el verde y la roja son «guía» (la de 350 era lo unico que hacia «no válida» al verde) y la de 350 se lee con la copia guardada
      a +3.30 (roja), +3.68 (verde) y +6.09 % (azul, sin rango util) de 345 cGy: NINGUNA capa la lee a ±3 % (punto 8 de §8 del plan); su U (k = 2) de DC10 y la inversa de la curva.
  (4) La plantilla de P12 (la de 5 como cero, 50, 100, 150, 200, 300, 400, 500, 600, 800 y 1000) contra las diez restantes: los estados, el rango (995 cGy en roja y verde: con dosis espaciadas el
      criterio (b) de DC5 no corta) y el error medio, el RMS y el maximo por capa; y la pieza de 100 cGy, a 95 cGy del cero, se juzga con ±5 % (por eso el verde de la plantilla no es «no válida»).
REGLA DE PR.0 DE LAS PIEZAS (CD10-REV-AMB-2: UNA sola definicion, `_exigir_las_piezas`, que llaman `_bytes` -- por donde se lee TODA pieza, tambien la de `_piezas` -- y las dos fixtures): si la carpeta existe y falta una pieza,
falla nombrandola; si la carpeta no existe, TODA prueba que lee una pieza se salta con su motivo (las de CD.3 y CD.4 hacen lo mismo: la suite sigue con 4 skipped en esta maquina, donde la carpeta existe) y las que no leen
ninguna (el docstring, las 730 lineas, el ValueError de una virgen, el texto de la cadena de captura) corren siempre.
Las cifras se fijan a media unidad de la ultima cifra que muestra la app (0.005 puntos en los porcentajes); los textos se ESCRIBEN aqui, no se importan (CD2-M1).
Rojo contra la base (2ea9248, el commit de CD.9 sin CD.10): caen 4 de 23 -- el docstring de `ajustar`, `texto_de_la_cadena` publica y las dos del texto de la cadena (1-bis), que la nombran publica --; lo demas
pasa, porque fija lo que la base ya hace (es la verificacion real de CD.10, no una conducta nueva).
Ronda 1 de la revision (CD10-REV-AMB-1 y AMB-2): sus cinco casos (1-bis y la regla de PR.0) los guardan las mutaciones MA05 a MA07 y MC01 a MC03 de `cd10_mutaciones.py`. Sin ellos, la mutacion del revisor (el motor
de la placa escribe su propia copia del texto) pasaba las 428 pruebas de CD.10, CD.9 y CD.6, y sin la carpeta de las piezas una prueba FALLABA en lugar de saltarse."""
import ast
import copy
import importlib
import inspect
import json
import math
import os
import re
import sqlite3
from pathlib import Path

import pytest

import _corpus
import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from scripts.indices_bloque_qc import crear_indices

RAIZ = Path(__file__).resolve().parent.parent
CAPAS = ("R", "G", "B")      # CD.5b (DA-94): la curva cubre solo las capas de color; sin el gris
ESCANER = "Epson 12000XL (declarado por el físico)"
ENCABEZADO = {"lote": "H9", "tipo_pelicula": "EBT3", "fecha_irradiacion": "2024-08-28", "energia": "6 MV", "escaner_declarado": ESCANER, "modo_de_escaneo": "transmisión"}
PLANTILLA = (5, 50, 100, 150, 200, 300, 400, 500, 600, 800, 1000)
CONTROLES = (250, 350, 450, 550, 650, 700, 750, 850, 900, 950)
VERIFICACION = 350
MEDIA_UNIDAD = 0.005                                                   # la app muestra los porcentajes con 2 decimales

GUIA = "guía: el cero es la pieza de 5 cGy"
AZUL_INCOMPLETA = "incompleta: quedan 0 dosis en el rango útil (hacen falta 6)"
ESTADOS_DE_LAS_21 = {"R": GUIA, "G": "no válida: el residuo de la pieza de 350 cGy es +3.19 % (la tolerancia es ±3 %)", "B": AZUL_INCOMPLETA}
                     # CD.5b (DA-94): sin el gris
RANGOS_DE_LAS_21 = {"R": 445.0, "G": 645.0, "B": None}          # CD.5b (DA-94): sin el gris
BASE_DE_LA_MENSUAL = {"R": "la curva de la capa roja es una guía: el cero es la pieza de 5 cGy",
                      "G": "la curva de la capa verde no es válida: no válida: el residuo de la pieza de 350 cGy es +3.19 % (la tolerancia es ±3 %)",
                      "B": "la curva de la capa azul no es válida: incompleta: quedan 0 dosis en el rango útil (hacen falta 6)"}
                      # CD.5b (DA-94): sin el gris
SIN_CURVA_PARA_LA_MENSUAL = ("no hay curva de dosis: no hay ninguna calibración vigente con una capa válida (se hace con «Curva de dosis...») (la curva de un análisis es la de la calibración vigente más "
                             "reciente con al menos una capa «válida» escaneada con la misma cadena de captura que la película)")
# (3) la de 350 leida con la curva de las otras 20: error contra 345 cGy (la dosis contada desde el cero) [%] y si cae en el rango util
LECTURA_DE_LA_350 = {"R": (3.2957, True), "G": (3.6759, True), "B": (6.0854, False)}          # CD.5b (DA-94): sin el gris
RANGOS_SIN_LA_350 = {"R": 445.0, "G": 645.0, "B": None}          # CD.5b (DA-94): sin el gris
U_DE_LA_350 = {"R": 21.754, "G": 25.833, "B": 40.318}          # CD.5b (DA-94): sin el gris. DC10: la U (k = 2) de esa lectura [cGy]; la app la muestra con 1 decimal
# (4) la plantilla contra las diez: (medio, RMS, maximo) del error contra la dosis contada desde el cero [%]
PLANTILLA_CONTRA_LAS_DIEZ = {"R": (1.4523, 2.3533, 5.0633), "G": (1.0519, 1.8021, 4.1078), "B": (1.8099, 3.6855, 9.0280)}          # CD.5b (DA-94): sin el gris
RANGOS_DE_LA_PLANTILLA = {"R": 995.0, "G": 995.0, "B": None}          # CD.5b (DA-94): sin el gris
RESIDUO_DE_LA_100_EN_LA_PLANTILLA = {"R": -2.0921, "G": -4.6835}


def _cd():
    return importlib.import_module("analisisImagenes.curva_dosis")


def _svc():
    return importlib.import_module("services.curva_dosis")


def _pm():
    return importlib.import_module("analisisImagenes.placa_mensual")


def _pel():
    return importlib.import_module("analisisImagenes.pelicula")


# ===================================================================================================== (1) el docstring de `ajustar`

ANTES = "NUNCA lanza por el contenido; `ValueError` si `piezas` no son `PiezaDeCalibracion`."


class TestElDocstringDeAjustar:
    def test_ya_no_promete_lo_falso_y_dice_quien_valida_P(self):
        doc = " ".join(_cd().ajustar.__doc__.split())
        assert ANTES not in doc, "el docstring de `ajustar` sigue prometiendo que NUNCA lanza (con un `P` de otro tipo lanza `TypeError`)"
        for frase in ("NUNCA lanza por el contenido de las piezas;", "`ValueError` si `piezas` no son `PiezaDeCalibracion` o `virgen` no es una `ReferenciaVirgen`.",
                      "`P` NO se valida aquí: lo pasa y lo valida solo `services/curva_dosis.py` (`_parametros_de_la_curva`; la ventana de calibración llama sin `P`),",
                      "con un `P` de otro tipo puede lanzar `TypeError`"):
            assert frase in doc, frase

    def test_el_cambio_no_mueve_ninguna_linea_del_motor(self):
        """Trampa 5: el docstring se corrige DENTRO de su linea; el motor sigue con 730 lineas (715 en b5abfa8; CD.5b sumo 15) y `ajustar` empieza donde empezaba (linea 482) (nadie cita lineas de este archivo hoy, y asi no hay que censar)."""
        texto = (RAIZ / "analisisImagenes" / "curva_dosis.py").read_text(encoding="utf-8")
        assert texto.count("\n") == 730
        assert texto.splitlines().index("def ajustar(piezas, P=None, virgen=None, u_dosis_medida_pct=None):") == 481

    def test_quien_pasa_P_lo_guarda_la_prueba_de_cd9_y_el_texto_de_la_cadena_es_publico(self):
        """CD10-D8: el censo por AST de los llamadores de `ajustar` (solo el servicio pasa `P`; la vista previa de la ventana, sin `P`) es UNO y vive en la prueba de CD.9
        (`test_ajustar_solo_lo_llaman_los_declarados_y_como_se_declaro`): aqui no se repite. CD10-D12 (cierra la deuda CD9-D3): CD.10 es la primera tarea que edita el motor de la curva, y
        `texto_de_la_cadena` pasa a ser publica (el motor de la placa la usaba privada desde CD.6, H-CD9-2)."""
        assert "def test_ajustar_solo_lo_llaman_los_declarados_y_como_se_declaro(" in (RAIZ / "tests" / "test_cd9_tripwires_curva_dosis.py").read_text(encoding="utf-8")
        assert callable(getattr(_cd(), "texto_de_la_cadena", None)) and not hasattr(_cd(), "_texto_de_la_cadena")
        assert "_texto_de_la_cadena" not in (RAIZ / "analisisImagenes" / "placa_mensual.py").read_text(encoding="utf-8")

    @pytest.mark.parametrize("P", [[("residuo_maximo_pct", 3.0)], {"residuo_maximo_pct": "3"}], ids=["una_lista", "un_texto_por_numero"])
    def test_con_un_P_de_otro_tipo_ajustar_lanza_TypeError(self, h9_medidas, P):
        with pytest.raises(TypeError):
            _cd().ajustar([p for p, _ in h9_medidas.values()], P=P)

    def test_con_una_virgen_de_otro_tipo_ValueError(self):
        with pytest.raises(ValueError, match="ReferenciaVirgen"):
            _cd().ajustar([], virgen="no es una referencia")

    def test_el_servicio_rechaza_ese_P_con_su_error_y_sin_escribir_nada(self, base_nueva):
        with pytest.raises(_svc().CurvaDosisError, match="'residuo_maximo_pct' debe ser un número finito de 0 o más, no '3'"):
            _svc().guardar("fisico", {**ENCABEZADO, "parametros_de_la_curva": {"residuo_maximo_pct": "3"}}, _piezas((5, 50, 100)))
        assert _sql(base_nueva, "SELECT COUNT(*) FROM calibracion_pelicula")[0][0] == 0
        assert not os.path.exists(os.path.join(os.path.dirname(base_nueva), "calibraciones_pelicula_escaneos"))


# ===================================================================================================== (1-bis) el texto de la cadena de captura: UNA definicion (CD10-REV-AMB-1)
# Al hacerla publica (CD10-D12) se retiro de la prueba de CD.9 la excepcion `(MOTOR_PLACA, "_texto_de_la_cadena")` y, con ella, el UNICO chequeo que exigia que el motor de la placa escribiera la cadena de
# captura de sus motivos (condicion 3 de DC8 y `curva_efectiva`) con la definicion del motor de la curva: su antipodredumbre obligaba a que ese uso existiera. Una copia del texto en la placa, con la misma salida,
# no la veia ninguna prueba (la mutacion MA05 de la bateria de CD.10; con la prueba de CD.9 de HEAD caia). Aqui se vigila lo que la excepcion vigilaba, por las dos maneras de romperlo: el NOMBRE (la placa ata
# `texto_de_la_cadena` a otro objeto) y el TEXTO (un archivo de produccion que escribe lo que esa funcion escribe cuando falta el escaner, con la misma salida o con otro nombre; MA06).

MOTOR_DE_LA_CURVA = "analisisImagenes/curva_dosis.py"
EXCLUIDOS = {".venv", "build", "dist", "tests", "__pycache__", ".git", "node_modules", ".pytest_cache"}          # los de la prueba de CD.9: el arbol de PRODUCCION
SIN_ESCANER = "escáner sin declarar"          # lo que `texto_de_la_cadena` escribe cuando la cadena no trae el escaner; en produccion solo el motor de la curva lo escribe


def _fuentes_de_produccion():
    """{ruta relativa a la raiz del repo: codigo fuente} de todo archivo .py de produccion (sin `tests/`, `build/`, `.venv`...)."""
    fuentes = {}
    for carpeta, subcarpetas, archivos in os.walk(RAIZ):
        subcarpetas[:] = [s for s in subcarpetas if s not in EXCLUIDOS]
        for nombre in archivos:
            if nombre.endswith(".py"):
                ruta = Path(carpeta) / nombre
                fuentes[ruta.relative_to(RAIZ).as_posix()] = ruta.read_text(encoding="utf-8")
    return fuentes


def _sitios_que_escriben_el_escaner_sin_declarar(fuentes):
    """[(ruta, linea)], ordenado, de cada constante de texto que lleva `SIN_ESCANER` en `{ruta: codigo fuente}`: los pedazos de un f-string cuentan, los docstrings NO (los que explican no escriben)."""
    sitios = []
    for ruta, codigo in fuentes.items():
        arbol = ast.parse(codigo)
        docstrings = {id(n.body[0].value) for n in ast.walk(arbol) if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body
                      and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant) and isinstance(n.body[0].value.value, str)}
        sitios += [(ruta, n.lineno) for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str) and SIN_ESCANER in n.value and id(n) not in docstrings]
    return sorted(sitios)


class TestElTextoDeLaCadenaEsUnoSolo:
    def test_el_motor_de_la_placa_escribe_la_cadena_con_la_funcion_del_motor_y_no_con_una_copia(self):
        assert _pm().texto_de_la_cadena is _cd().texto_de_la_cadena, "el motor de la placa ata `texto_de_la_cadena` a otro objeto que el del motor de la curva: es una copia (una operacion, una definicion)"

    def test_en_toda_la_produccion_solo_el_motor_de_la_curva_escribe_el_escaner_sin_declarar(self):
        sitios = _sitios_que_escriben_el_escaner_sin_declarar(_fuentes_de_produccion())
        assert [ruta for ruta, _ in sitios] == [MOTOR_DE_LA_CURVA], (f"el texto «{SIN_ESCANER}» debe escribirlo UN solo sitio de produccion, el motor de la curva (si el motor cambio esas palabras, se cambian aqui y en "
                                                                     f"el ayudante `texto_de_la_cadena` de la prueba de CD.6; si hay otro sitio, es una copia de `texto_de_la_cadena`): {sitios}")
        lineas, inicio = inspect.getsourcelines(_cd().texto_de_la_cadena)
        assert inicio <= sitios[0][1] < inicio + len(lineas), "ese unico sitio no es el cuerpo de `texto_de_la_cadena`"

    def test_la_guarda_senala_una_copia_con_otro_nombre_o_en_un_f_string_y_no_un_docstring(self):
        copia = 'def _mi_texto(cadena):\n    return cadena["equipo"] or "escáner sin declarar"\n'
        en_un_f_string = "def t(c):\n    return f\"{c['equipo'] or 'escáner sin declarar'}, {c['bits']} bits\"\n"
        solo_explica = '"""Escribe «escáner sin declarar» cuando falta el escáner."""\n\n\nclass A:\n    """Y aquí: escáner sin declarar."""\n\n    def f(self):\n        """Y aquí también: escáner sin declarar."""\n'
        otro_texto = 'def t():\n    return "escáner declarado"\n'
        sitios = _sitios_que_escriben_el_escaner_sin_declarar({"a.py": copia, "b.py": en_un_f_string, "c.py": solo_explica, "d.py": otro_texto})
        assert [ruta for ruta, _ in sitios] == ["a.py", "b.py"] and sitios[0] == ("a.py", 2), sitios


# ===================================================================================================== las piezas, la regla de PR.0 y una base NUEVA

def _exigir_las_piezas():
    """LA regla de PR.0 de las piezas de H9, UNA vez (CD10-REV-AMB-2): sin la carpeta, la prueba que las lee SALTA con su motivo (no hay corpus en esta maquina); con la carpeta, si falta una pieza (o esta vacia)
    FALLA nombrandola. La llaman `_bytes` -- por donde se lee TODA pieza, tambien la de `_piezas` -- y las dos fixtures: ningun camino a una pieza se la salta."""
    faltan = _corpus.piezas_de_calibracion_que_faltan()
    if faltan is None:
        pytest.skip("la carpeta de las piezas de H9 no existe en esta máquina")
    assert faltan == [], f"faltan piezas de H9: {faltan}"


def _bytes(dosis):
    _exigir_las_piezas()
    with open(_corpus.ruta_de_pieza_de_calibracion(dosis), "rb") as f:
        return f.read()


def _piezas(dosis):
    return [{"orden": k, "dosis_nominal_cgy": float(d), "dosis_medida_cgy": float(d), "datos": _bytes(d), "nombre_archivo": _corpus.PIEZAS_DE_CALIBRACION[d]}
            for k, d in enumerate(sorted(dosis), 1)]


def _sql(ruta, consulta):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(consulta).fetchall()
    finally:
        con.close()


@pytest.fixture(scope="module")
def h9_medidas():
    """CD.2 llamado AQUI sobre cada pieza (escala declarada, como el servicio): {dosis: (PiezaDeCalibracion, MedidaDePieza)}. Antes, la regla de PR.0."""
    _exigir_las_piezas()
    P = copy.deepcopy(_pm().VALORES_DE_LA_GEOMETRIA)
    salida = {}
    for k, d in enumerate(sorted(_corpus.PIEZAS_DE_CALIBRACION), 1):
        medida = _pel().medir_pieza_uniforme(_bytes(d), copy.deepcopy(P), _corpus.PIEZAS_DE_CALIBRACION[d], "2026-11-01", escala="declarada")
        salida[d] = (_cd().pieza_de_calibracion(k, float(d), float(d), medida), medida)
    return salida


@pytest.fixture
def base_nueva(monkeypatch, tmp_path):
    """Una base NUEVA en su propia carpeta (los escaneos van junto a ella), creada por el arranque real; nunca una de BasesDeDatos/."""
    carpeta = tmp_path / "base"
    carpeta.mkdir()
    ruta = str(carpeta / "cd10.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    previo = Conexion._instance
    Conexion._instance = None
    conexion = Conexion()
    crear_indices(ruta)
    yield ruta
    conexion.con.close()
    Conexion._instance = previo


@pytest.fixture(scope="module")
def calibraciones(tmp_path_factory):
    """Las tres calibraciones de CD.10, guardadas UNA vez por el servicio en una base nueva y leidas de vuelta: las 21, sin la de 350 y la plantilla de P12."""
    _exigir_las_piezas()
    ruta = str(tmp_path_factory.mktemp("cd10") / "cd10.db")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = None
        conexion = Conexion()
        try:
            crear_indices(ruta)
            svc = _svc()
            todas = sorted(_corpus.PIEZAS_DE_CALIBRACION)
            ids = {"21": svc.guardar("fisico", ENCABEZADO, _piezas(todas)),
                   "sin_350": svc.guardar("fisico", {**ENCABEZADO, "lote": "H9 sin la de 350"}, _piezas([d for d in todas if d != VERIFICACION])),
                   "plantilla": svc.guardar("fisico", {**ENCABEZADO, "lote": "H9 plantilla P12"}, _piezas(PLANTILLA))}
            registros = {k: svc.leer(i) for k, i in ids.items()}
            recalculo = svc.recalcular(registros["21"])
            vigentes = svc.vigentes_validas()
            anulada = svc.anular(ids["21"], "fisico")
            tras = svc.leer(ids["21"])
            yield {"registros": registros, "recalculo": recalculo, "vigentes": vigentes, "anulada": anulada, "tras_anular": tras, "ruta": ruta}
        finally:
            conexion.con.close()
            Conexion._instance = previo


def _curva(calibraciones, cual):
    return _cd().curva_desde_dict(calibraciones["registros"][cual]["ajuste"])


def _error_de_la_lectura(curva, pieza, dosis):
    """La dosis que lee la COPIA guardada de una curva para una pieza (su valor de CD.2 contra el I0 guardado: netOD = log10(I0 / I)), como (error [%] contra su dosis contada desde el cero, si cae en
    el rango util, su U (k = 2) [cGy] con la u de la netOD de la ecuacion 2 de Vargas-Segura (DC3) y `CurvaDeDosis.incertidumbre` (DC10), y la netOD), por capa."""
    cero = curva.cero["dosis_cgy"]
    salida = {}
    for c in CAPAS:
        i0, u0 = curva.cero["capas"][c]["i0"], curva.cero["capas"][c]["u_i0"]
        valor, u = pieza.capas[c]["valor"], pieza.capas[c]["u"]
        netod = math.log10(i0 / valor)
        u_netod = math.sqrt((u0 / i0) ** 2 + (u / valor) ** 2) / math.log(10.0)
        verdad = dosis - cero
        salida[c] = (100.0 * (curva.dosis(c, netod) - verdad) / verdad, curva.rango(c) is not None and verdad <= curva.rango(c), curva.incertidumbre(c, netod, u_netod), netod)
    return salida


# ===================================================================================================== la regla de PR.0 de ESTA prueba (CD10-REV-AMB-2)

class TestLaReglaDePR0DeEstaPrueba:
    """Antes, `test_el_servicio_rechaza_ese_P_...` leia las piezas por `_piezas` sin pasar por la regla (las fixtures la aplicaban cada una por su cuenta) y, sin la carpeta, FALLABA con un TypeError
    (`open(None)`) en lugar de saltarse: la unica de CD.3, CD.4 y CD.10 que lo hacia. Se prueba la regla donde vive, con la raiz de las piezas apuntada a otra carpeta (como la de CD.3): no depende de
    que esta maquina tenga las piezas."""

    def test_sin_la_carpeta_leer_una_pieza_salta_con_su_motivo_y_no_falla(self, monkeypatch, tmp_path):
        monkeypatch.setattr(_corpus, "PIEZAS_DE_CALIBRACION_RAIZ", str(tmp_path / "no_existe"))
        for leer in (lambda: _bytes(5), lambda: _piezas((5, 50, 100))):
            with pytest.raises(pytest.skip.Exception, match="la carpeta de las piezas de H9 no existe"):
                leer()

    def test_con_la_carpeta_y_una_pieza_de_menos_leer_cualquier_otra_falla_nombrando_la_que_falta(self, monkeypatch, tmp_path):
        for dosis, archivo in _corpus.PIEZAS_DE_CALIBRACION.items():
            if dosis != 700:
                (tmp_path / archivo).write_bytes(b"x")
        monkeypatch.setattr(_corpus, "PIEZAS_DE_CALIBRACION_RAIZ", str(tmp_path))
        with pytest.raises(AssertionError, match=re.escape("faltan piezas de H9: [700]")):
            _bytes(5)
        (tmp_path / _corpus.PIEZAS_DE_CALIBRACION[700]).write_bytes(b"x")
        assert _bytes(5) == b"x", "con las 21 presentes la regla no niega leer una pieza"


# ===================================================================================================== (2) las 21 por el servicio

class TestLas21PorElServicio:
    def test_sus_estados_rangos_y_cero_son_los_de_cd3_d17(self, calibraciones):
        r = calibraciones["registros"]["21"]
        assert r["estado"] == ESTADOS_DE_LAS_21
        assert "gris" not in r["estado"] and "gris" not in json.dumps(r["ajuste"]), "CD.5b (DA-94): la calibración de las 21 no tiene curva del gris"
        assert {c: _curva(calibraciones, "21").rango(c) for c in CAPAS} == RANGOS_DE_LAS_21
        assert (r["cero"]["fuente"], r["cero"]["dosis_cgy"]) == ("pieza_de_menor_dosis", 5.0)
        assert r["cadena_de_captura"] == {"piezas": {"bits": 16, "dpi": 150.0, "equipo": None, "formato": "TIFF"}, "escaner_declarado": ESCANER, "modo_de_escaneo": "transmisión"}

    def test_lo_guardado_es_lo_del_motor_y_se_rehace_igual_desde_los_escaneos(self, calibraciones, h9_medidas):
        r = calibraciones["registros"]["21"]
        directo = _cd().ajustar([p for p, _ in h9_medidas.values()])
        assert r["ajuste"] == _pel()._json_normal(directo.como_dict())
        rec = calibraciones["recalculo"]
        assert rec.desde_los_escaneos is not None and rec.escaneos_que_faltan == () and rec.escaneos_que_no_coinciden == ()
        assert _svc().diferencias(r, rec) == []

    def test_la_u_de_la_netod_guardada_es_la_ecuacion_2_de_vargas_segura(self, calibraciones):
        """DC3: u(netOD) = (1 / ln 10) · √((u_I0 / I0)² + (u_I / I)²), con el I0 y su u del cero GUARDADO y el valor y su u de cada pieza guardada, en las 20 irradiadas y las tres capas de la curva (CD.5b, DA-94: sin el gris; 80 valores antes). Fija la u
        que deciden el rango util (criterio (c) de DC5) y la U de la dosis (DC10) con las piezas reales (la mutacion MB12 quita el termino del cero y ningun estado ni rango de H9 lo ve)."""
        ajuste = calibraciones["registros"]["21"]["ajuste"]
        vistas = 0
        for p in ajuste["piezas"]:
            if p["dosis_nominal_cgy"] == 5.0:
                continue
            for c in CAPAS:
                i0, u0 = ajuste["cero"]["capas"][c]["i0"], ajuste["cero"]["capas"][c]["u_i0"]
                k = p["capas"][c]
                esperada = math.sqrt((u0 / i0) ** 2 + (k["u"] / k["valor"]) ** 2) / math.log(10.0)
                assert math.isclose(k["u_netod"], esperada, rel_tol=1e-12), (p["dosis_nominal_cgy"], c, k["u_netod"], esperada)
                vistas += 1
        assert vistas == 60

    def test_ninguna_es_vigente_valida_y_se_anula_con_sus_piezas(self, calibraciones):
        assert calibraciones["vigentes"] == []
        assert calibraciones["anulada"] is True
        tras = calibraciones["tras_anular"]
        assert tras["activo"] == 0 and len(tras["piezas"]) == 21 and not any(p["activo"] for p in tras["piezas"])
        assert [f[0] for f in _sql(calibraciones["ruta"], "SELECT accion FROM audit_log WHERE tabla = 'calibracion_pelicula' ORDER BY id")] == ["guardar", "guardar", "guardar", "anular"]

    def test_una_pelicula_de_la_wf_6590_sigue_en_netod_con_el_motivo_de_cada_capa(self, calibraciones):
        ruta = os.path.join(_corpus.PELICULAS_RAIZ, "EPSON001.TIF")
        if not os.path.isfile(ruta):
            pytest.skip("EPSON001.TIF no está en esta máquina")
        with open(ruta, "rb") as f:
            cadena = _pm().cadena_de_la_pelicula(f.read())
        assert cadena == {"bits": 8, "dpi": 599.999, "equipo": "SEIKO EPSON CORP. WF-6590 Series", "formato": "TIFF"}
        piso = type("PisoDeLaVirgen", (), {"estado": "ok", "origen": "virgen"})()
        curva = _curva(calibraciones, "21")
        assert {c: _pm().base_de_la_capa(curva, c, piso, cadena) for c in CAPAS} == {c: (_pm().BASE_DENSIDAD_OPTICA, m) for c, m in BASE_DE_LA_MENSUAL.items()}
        assert _pm().curva_efectiva(calibraciones["vigentes"], cadena).motivo == SIN_CURVA_PARA_LA_MENSUAL


# ===================================================================================================== (3) la pieza de verificacion

class TestLaPiezaDeVerificacion:
    def test_sin_la_de_350_el_verde_y_la_roja_son_guia(self, calibraciones):
        r = calibraciones["registros"]["sin_350"]
        assert r["estado"] == {"R": GUIA, "G": GUIA, "B": AZUL_INCOMPLETA}, "la de 350 era lo único que dejaba el verde «no válida»"
        assert {c: _curva(calibraciones, "sin_350").rango(c) for c in CAPAS} == RANGOS_SIN_LA_350
        assert len(r["piezas"]) == 20 and VERIFICACION not in {p["dosis_nominal_cgy"] for p in r["piezas"]}

    def test_la_copia_guardada_lee_la_de_350_y_ninguna_capa_la_lee_a_3_por_ciento(self, calibraciones, h9_medidas):
        curva = _curva(calibraciones, "sin_350")
        leida = _error_de_la_lectura(curva, h9_medidas[VERIFICACION][0], VERIFICACION)
        for c, (error, en_el_rango) in LECTURA_DE_LA_350.items():
            assert abs(leida[c][0] - error) <= MEDIA_UNIDAD, (c, leida[c][0], error)
            assert leida[c][1] is en_el_rango, c
        assert all(abs(e[0]) > 3.0 for e in leida.values()), "punto 8 de §8: ninguna capa lee la de 350 cGy a ±3 % con este juego guía"

    def test_la_U_de_esa_lectura_y_la_inversa_de_la_curva(self, calibraciones, h9_medidas):
        """DC10 con piezas reales: la U (k = 2) de la dosis leida (el RMS de los residuos del rango, la incertidumbre declarada -no hay: P13- y la de la pelicula); y `netod`, la inversa, devuelve la
        netOD de la que salio la dosis (es la que usa la ventana mensual para la U de la meseta, CD.6)."""
        curva = _curva(calibraciones, "sin_350")
        assert curva.u_dosis_medida_pct is None
        for c, (_, _, U, netod) in _error_de_la_lectura(curva, h9_medidas[VERIFICACION][0], VERIFICACION).items():
            assert abs(U - U_DE_LA_350[c]) <= 0.05, (c, U)
            assert math.isclose(curva.netod(c, curva.dosis(c, netod)), netod, rel_tol=1e-9), c


# ===================================================================================================== (4) la plantilla de P12

class TestLaPlantillaDeP12:
    def test_sus_estados_y_su_rango(self, calibraciones):
        r = calibraciones["registros"]["plantilla"]
        assert r["estado"] == {"R": GUIA, "G": GUIA, "B": AZUL_INCOMPLETA}
        assert {c: _curva(calibraciones, "plantilla").rango(c) for c in CAPAS} == RANGOS_DE_LA_PLANTILLA
        assert sorted(p["dosis_nominal_cgy"] for p in r["piezas"]) == [float(d) for d in PLANTILLA]

    def test_contra_las_diez_restantes(self, calibraciones, h9_medidas):
        curva = _curva(calibraciones, "plantilla")
        errores = {c: [] for c in CAPAS}
        for d in CONTROLES:
            for c, leida in _error_de_la_lectura(curva, h9_medidas[d][0], d).items():
                errores[c].append(leida[0])
        for c, (medio, rms, maximo) in PLANTILLA_CONTRA_LAS_DIEZ.items():
            medido = (sum(errores[c]) / 10, math.sqrt(sum(e * e for e in errores[c]) / 10), max(abs(e) for e in errores[c]))
            assert all(abs(m - e) <= MEDIA_UNIDAD for m, e in zip(medido, (medio, rms, maximo))), (c, medido)

    def test_la_de_100_esta_a_95_cgy_del_cero_y_se_juzga_con_5_por_ciento(self, calibraciones):
        curva = _curva(calibraciones, "plantilla")
        cien = next(p for p in curva.piezas if p.dosis_nominal_cgy == 100.0)
        assert cien.capas["G"]["dosis_cgy"] == 95.0 < curva.parametros["dosis_baja_cgy"]
        for c, residuo in RESIDUO_DE_LA_100_EN_LA_PLANTILLA.items():
            assert abs(cien.capas[c]["residuo_pct"] - residuo) <= MEDIA_UNIDAD, (c, cien.capas[c]["residuo_pct"])
        assert 3.0 < abs(cien.capas["G"]["residuo_pct"]) <= curva.parametros["residuo_maximo_bajas_pct"]
