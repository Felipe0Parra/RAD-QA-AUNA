"""C3 (PLAN_REPARACION_ANUAL_27-08.md §Fase 1): tripwire censal --
ninguna tabla puede recibir dos registros de `_configurar_eventos` con
callback `_calcular_discrepancias_tablas`, ni una `columna_discrepancia`
puede coincidir con una columna que la misma llamada usa como dato de
entrada (`columna_real`/`columna_esperada`).

`AN-5` vivió sin manifestarse solo porque dos registros para `tabla_icam`
compartían `timer_key` y el segundo cancelaba el temporizador del primero
-- un accidente de temporización, no una garantía. Sin este tripwire, el
próximo caso sería igual de invisible.

Deriva el censo por AST directamente del código fuente vigente (no por
número de línea) -- resuelve las tablas de un bucle `for x in LISTA:`
contra la lista real que se le asigna, así que sigue funcionando aunque
`E1`/`R1` reescriban estos mismos métodos más adelante.
"""
import ast
import inspect
import os
import textwrap
from collections import Counter

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.paginasControles.PruebasAnuales.seiscientos_anual import PruebaAnual600
from ui.paginasControles.PruebasAnuales.ix_anual import PruebaAnualIX
from ui.paginasControles.PruebasAnuales.halcyon_anual import PruebaAnualHalcyon
from ui.paginasControles.PruebasMensuales.halcyon_mensual import PruebaMensualHc


def _valor_constante(nodo):
    return nodo.value if isinstance(nodo, ast.Constant) else None


def registros_de_discrepancia(fuente_func):
    """Devuelve una lista de (nombre_tabla_resuelto, columna_real,
    columna_esperada, columna_discrepancia) por cada registro de
    `_calcular_discrepancias_tablas` encontrado en `fuente_func` (código
    fuente ya dedentado de una función/método)."""
    arbol = ast.parse(fuente_func)

    listas = {}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Assign) and isinstance(nodo.value, ast.List):
            for objetivo in nodo.targets:
                if isinstance(objetivo, ast.Name):
                    listas[objetivo.id] = [
                        e.id for e in nodo.value.elts if isinstance(e, ast.Name)
                    ]

    registros = []

    def _posicionales_normalizados(nodo_llamada):
        """Admite las dos formas de llamada presentes en el código real:
        `self._calcular_discrepancias_tablas(tabla, ...)` (ligada) y
        `Clase._calcular_discrepancias_tablas(self, tabla, ...)` (no
        ligada, usada en halcyon_mensual.py para reusar el método de
        PruebaAnual600 sin heredarlo) -- en la segunda, el primer
        posicional es `self`, no la tabla."""
        posicionales = list(nodo_llamada.args)
        if posicionales and isinstance(posicionales[0], ast.Name) and posicionales[0].id == "self":
            posicionales = posicionales[1:]
        return posicionales

    def _columnas(nodo_llamada, posicionales):
        columna_real = _valor_constante(posicionales[1]) if len(posicionales) > 1 else None
        columna_esperada = _valor_constante(posicionales[2]) if len(posicionales) > 2 else None
        columna_discrepancia = _valor_constante(posicionales[3]) if len(posicionales) > 3 else 3
        for kw in nodo_llamada.keywords:
            if kw.arg == "columna_discrepancia":
                columna_discrepancia = _valor_constante(kw.value)
        return columna_real, columna_esperada, columna_discrepancia

    def visitar(nodo, pila_bucles):
        if isinstance(nodo, ast.For) and isinstance(nodo.target, ast.Name):
            pila_bucles = pila_bucles + [(nodo.target.id, nodo.iter, nodo)]

        if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "_calcular_discrepancias_tablas"):
            posicionales = _posicionales_normalizados(nodo)
            if posicionales and isinstance(posicionales[0], ast.Name):
                nombre_arg = posicionales[0].id
                columna_real, columna_esperada, columna_discrepancia = _columnas(nodo, posicionales)

                resuelto = False
                for var_bucle, iterable, nodo_for in reversed(pila_bucles):
                    if var_bucle == nombre_arg:
                        if isinstance(iterable, ast.Name) and iterable.id in listas:
                            # La lista se define UNA vez, fuera de cualquier
                            # bucle -- sus elementos son bindings estables
                            # de método (clave "de nivel de método", sin
                            # bucle asociado): así, un registro individual
                            # posterior para el mismo nombre SÍ colisiona.
                            for tabla in listas[iterable.id]:
                                registros.append(((tabla, None), columna_real, columna_esperada, columna_discrepancia))
                        else:
                            registros.append(((f"<bucle:{nombre_arg}>", id(nodo_for)), columna_real, columna_esperada, columna_discrepancia))
                        resuelto = True
                        break
                if not resuelto:
                    # El nombre no es el target de ningún bucle en curso.
                    # Si aun así vive DENTRO de un cuerpo de bucle (p.ej.
                    # `tabla_obj = tabla['tabla']` reasignado en cada
                    # iteración), cada bucle produce objetos distintos
                    # aunque el nombre temporal coincida entre bucles
                    # hermanos -- se distingue por el nodo del bucle más
                    # interno que contiene la llamada. Fuera de todo bucle,
                    # el nombre es un binding estable de método.
                    contexto = id(pila_bucles[-1][2]) if pila_bucles else None
                    registros.append(((nombre_arg, contexto), columna_real, columna_esperada, columna_discrepancia))

        for hijo in ast.iter_child_nodes(nodo):
            visitar(hijo, pila_bucles)

    visitar(arbol, [])
    return registros


def registros_de_metodo(metodo):
    return registros_de_discrepancia(textwrap.dedent(inspect.getsource(metodo)))


def _tablas_duplicadas(registros):
    # registros[i][0] es (nombre, contexto) -- ver registros_de_discrepancia.
    conteo = Counter(clave for clave, *_ in registros)
    return {clave[0]: n for clave, n in conteo.items() if n > 1}


def _colisiones_columna_entrada(registros):
    return [
        r for r in registros
        if r[3] is not None and r[3] in (r[1], r[2])
    ]


class TestLaTrampaSintéticaSeDetecta:
    """Rojo antes que verde: reproduce, en una función de mentira, el
    patrón exacto de AN-5 (una tabla en un grupo genérico Y con un
    registro individual aparte) y confirma que el censo lo marca."""

    def test_tabla_en_bucle_y_ademas_individual_se_marca_como_duplicada(self):
        fuente = '''
def _configurar_subtoolbox(self):
    grupo_tablas_mecanicos = [tabla_ig, tabla_ic, tabla_icam]
    for tabla in grupo_tablas_mecanicos:
        self._configurar_eventos(tabla, callback=self._calcular_discrepancias_tablas(tabla, 0, 1, 2, diferencia_tipo="absoluta"))
    self._configurar_eventos(tabla_icam, callback=self._calcular_discrepancias_tablas(tabla_icam, 1, 2, 3, diferencia_tipo="porcentaje"))
'''
        registros = registros_de_discrepancia(fuente)
        duplicadas = _tablas_duplicadas(registros)
        assert "tabla_icam" in duplicadas
        assert duplicadas["tabla_icam"] == 2

    def test_columna_discrepancia_igual_a_columna_de_entrada_se_marca(self):
        fuente = '''
def _configurar_subtoolbox(self):
    self._configurar_eventos(tabla_x, callback=self._calcular_discrepancias_tablas(tabla_x, 1, 2, 1, diferencia_tipo="absoluta"))
'''
        registros = registros_de_discrepancia(fuente)
        colisiones = _colisiones_columna_entrada(registros)
        assert len(colisiones) == 1

    def test_caso_sano_no_marca_nada(self):
        fuente = '''
def _configurar_subtoolbox(self):
    grupo = [tabla_a, tabla_b]
    for tabla in grupo:
        self._configurar_eventos(tabla, callback=self._calcular_discrepancias_tablas(tabla, 0, 1, 2, diferencia_tipo="absoluta"))
    self._configurar_eventos(tabla_c, callback=self._calcular_discrepancias_tablas(tabla_c, 1, 2, 3, diferencia_tipo="porcentaje"))
'''
        registros = registros_de_discrepancia(fuente)
        assert not _tablas_duplicadas(registros)
        assert not _colisiones_columna_entrada(registros)


# Censo real: cada método que registra callbacks de discrepancia, en los
# tres anuales y en el mensual de Halcyon (única excepción documentada en
# C1 -- comparte la misma función raíz).
METODOS_CENSADOS = [
    ("seiscientos_anual.py", PruebaAnual600._configurar_subtoolbox),
    ("ix_anual.py", PruebaAnualIX._configurar_subtoolbox),
    ("halcyon_anual.py", PruebaAnualHalcyon._configurar_subtoolbox),
    ("halcyon_mensual.py", PruebaMensualHc.controlTestWindow),
]


class TestCensoRealSinColisiones:
    @pytest.mark.parametrize("archivo, metodo", METODOS_CENSADOS, ids=[m[0] for m in METODOS_CENSADOS])
    def test_ninguna_tabla_recibe_dos_registros(self, archivo, metodo):
        registros = registros_de_metodo(metodo)
        duplicadas = _tablas_duplicadas(registros)
        assert not duplicadas, (
            f"{archivo}.{metodo.__name__}: tabla(s) con más de un registro "
            f"de _calcular_discrepancias_tablas: {duplicadas}")

    @pytest.mark.parametrize("archivo, metodo", METODOS_CENSADOS, ids=[m[0] for m in METODOS_CENSADOS])
    def test_ninguna_columna_discrepancia_coincide_con_columna_de_entrada(self, archivo, metodo):
        registros = registros_de_metodo(metodo)
        colisiones = _colisiones_columna_entrada(registros)
        assert not colisiones, (
            f"{archivo}.{metodo.__name__}: registro(s) cuya columna_discrepancia "
            f"coincide con columna_real/columna_esperada: {colisiones}")

    def test_el_censo_encuentra_al_menos_una_tabla_por_archivo(self):
        # Guarda contra que un refactor rompa el parseo por AST y el censo
        # quede vacío en silencio (falso verde).
        for archivo, metodo in METODOS_CENSADOS:
            registros = registros_de_metodo(metodo)
            assert registros, f"{archivo}.{metodo.__name__}: el censo no encontró ningún registro"
