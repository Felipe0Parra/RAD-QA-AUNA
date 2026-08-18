"""RT1 (PLAN_LECTURA_VIGENTE_18-08.md §6-RT1): batería propia del frente
DINÁMICO.

El fixture de sesión de `conftest.py` es el tripwire; este archivo prueba
las tres cosas que el tripwire da por supuestas y que, si fallan, lo
convierten en decoración:

1. Que la **profundidad de frame** con la que RT1 decide "esto lo ejecutó
   producción" apunta de verdad al llamador de `.execute()`, en las cuatro
   formas que aparecen en el árbol.
2. Que RT1 **atrapa lo que ES1 no puede ver** -- una consulta armada dentro
   de un bucle, genuinamente irresoluble para el análisis estático. Sin
   esto, RT1 sería un duplicado caro de ES1.
3. Que la lista blanca censal de RT1 **no diverge** de la de ES1.

Cómo se fabrica "código de producción" sin escribir en el árbol de
producción: `compile(fuente, ruta_ficticia, "exec")` produce funciones cuyo
`co_filename` es la ruta que se le dé. RT1 clasifica por `co_filename`, así
que eso basta para que las vea como producción -- y no deja ni un archivo
nuevo bajo `data/`.
"""
import ast
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import _rt1_interceptor_sql as _rt1              # noqa: E402
from services import lectura_vigente as lv       # noqa: E402

# Ruta que NO existe: solo se usa como `co_filename` para que el filtro de
# origen de RT1 clasifique estas funciones como producción.
FICTICIO = "data/ManejoDatos/_sitio_ficticio_rt1.py"
RUTA_FICTICIA = str(ROOT / FICTICIO)

TABLA = "dosimetriaMen"   # la tabla de D2, real y dentro del alcance


def _compilar_como_produccion(fuente):
    ns = {}
    exec(compile(fuente, RUTA_FICTICIA, "exec"), ns)
    return ns


@pytest.fixture
def rt1_aislado():
    """RT1 está activo a nivel de SESIÓN (conftest). Estos tests ejecutan a
    propósito SQL que el tripwire debe marcar, así que todo lo que
    provoquen se retira del estado global al terminar -- si no, la sesión
    entera fallaría por culpa de este archivo, y las cifras de cobertura
    publicadas quedarían contaminadas con un archivo que no existe."""
    n = len(_rt1.hallazgos_sesion)
    yield _rt1
    del _rt1.hallazgos_sesion[n:]
    for clave in list(_rt1.funciones_produccion_ejercitadas):
        if clave[0] == FICTICIO:
            _rt1.funciones_produccion_ejercitadas.discard(clave)


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")   # ya instrumentada por el fixture de sesión
    c.execute(f'CREATE TABLE "{TABLA}" (ref, energia, dosis_ref_cgy_um, activo)')
    c.execute(f'INSERT INTO "{TABLA}" VALUES (1, "6mv", 1.0125, 1)')
    yield c
    c.close()


class TestProfundidadDeFrame:
    """`_origen()` usa `sys._getframe(2)` (0=él mismo, 1=`_rastrear_sql`,
    2=el llamador real). Que `sqlite3` no interponga ningún frame Python
    entre `.execute()` y el callback es una suposición sobre el runtime,
    no algo obvio -- se comprueba, no se razona."""

    FUENTES = {
        "con_connection_execute": f'''
def con_connection_execute(con):
    con.execute('SELECT ref FROM {TABLA} WHERE activo = 1')
''',
        "con_cursor_execute": f'''
def con_cursor_execute(con):
    con.cursor().execute('SELECT ref FROM {TABLA} WHERE activo = 1')
''',
        "con_executemany": f'''
def con_executemany(con):
    con.executemany(
        'UPDATE {TABLA} SET energia = ? WHERE activo = 1', [("6mv",), ("10mv",)])
''',
        "con_llamada_anidada": f'''
def _interno(con):
    con.execute('SELECT ref FROM {TABLA} WHERE activo = 1')

def con_llamada_anidada(con):
    _interno(con)
''',
    }

    @pytest.mark.parametrize("nombre", sorted(FUENTES))
    def test_el_frame_registrado_es_el_llamador_de_execute(
            self, nombre, con, rt1_aislado):
        ns = _compilar_como_produccion(self.FUENTES[nombre])
        ns[nombre](con)

        # En el caso anidado el llamador INMEDIATO de .execute() es
        # `_interno`, no la función externa: eso es exactamente lo que RT1
        # debe registrar (el sitio que ejecuta, no quien lo invocó).
        esperado = "_interno" if nombre == "con_llamada_anidada" else nombre
        assert (FICTICIO, esperado) in rt1_aislado.funciones_produccion_ejercitadas, (
            f"RT1 no atribuyó la sentencia a {esperado}; la profundidad de "
            f"frame de `_origen()` no apunta al llamador de .execute(). "
            f"Registrado: {sorted(rt1_aislado.funciones_produccion_ejercitadas)}")

    def test_un_llamador_de_la_suite_no_cuenta_como_produccion(
            self, con, rt1_aislado):
        """El caso que motivó el filtro de origen: esta misma consulta, sin
        filtro y ejecutada desde `tests/`, no debe vigilarse."""
        antes = len(rt1_aislado.hallazgos_sesion)
        con.execute(f'SELECT ref FROM {TABLA}').fetchall()   # sin filtro, a propósito
        assert len(rt1_aislado.hallazgos_sesion) == antes, (
            "una verificación de test se coló como si fuera producción")
        assert not any(a.startswith("tests/")
                       for a, _ in rt1_aislado.funciones_produccion_ejercitadas)


class TestRT1VeLoQueES1NoPuedeVer:
    """La razón de existir de RT1. Si esto no se cumple, RT1 es un
    duplicado caro del frente estático."""

    # `query` se reasigna DENTRO de un bucle: `resolver_argumento_execute`
    # devuelve None por diseño ("más seguro dejarlo opaco que fingir una
    # resolución incorrecta"), así que ES1 no puede leer este SQL jamás.
    FUENTE_OPACA = f'''
def lector_opaco(con, tablas):
    query = "SELECT 1"
    for t in tablas:
        query = "SELECT ref, dosis_ref_cgy_um FROM " + t + " WHERE ref = 1"
    con.execute(query).fetchall()
'''

    def test_es1_es_ciego_a_esta_consulta(self):
        arbol = ast.parse(self.FUENTE_OPACA)
        func = arbol.body[0]
        llamada = next(n for n in ast.walk(func)
                       if isinstance(n, ast.Call)
                       and isinstance(n.func, ast.Attribute)
                       and n.func.attr == "execute")
        assert lv.resolver_argumento_execute(func, llamada) is None, (
            "si AN1 llegara a resolver esta variable, el caso dejaría de "
            "demostrar nada y habría que construir otro más opaco")

    def test_rt1_la_atrapa_con_el_sql_ya_resuelto(self, con, rt1_aislado):
        ns = _compilar_como_produccion(self.FUENTE_OPACA)
        antes = len(rt1_aislado.hallazgos_sesion)

        ns["lector_opaco"](con, [TABLA])

        nuevos = rt1_aislado.hallazgos_sesion[antes:]
        assert nuevos, (
            "RT1 dejó pasar una lectura de producción sin filtro de activo "
            "que ES1 no puede ver: el frente dinámico no aporta nada")
        sql, origen, hallazgos = nuevos[0]
        assert TABLA in sql and "activo" not in sql.lower()
        assert origen[:2] == (FICTICIO, "lector_opaco")
        assert [h.tabla for h in hallazgos] == [TABLA]
        assert hallazgos[0].motivo == "sin filtro de activo"

    def test_la_misma_consulta_con_filtro_no_se_marca(self, con, rt1_aislado):
        """El contraprueba: un analizador que marca todo no sirve de nada."""
        fuente = self.FUENTE_OPACA.replace(
            'WHERE ref = 1"', 'WHERE ref = 1 AND (activo IS NULL OR activo = 1)"')
        ns = _compilar_como_produccion(fuente)
        antes = len(rt1_aislado.hallazgos_sesion)

        ns["lector_opaco"](con, [TABLA])

        assert len(rt1_aislado.hallazgos_sesion) == antes


class TestListaBlancaCensal:
    """Las 4 excepciones censales de RT1 no son una segunda opinión: son
    las mismas que ES1 ya revisó. Si una de las dos listas se mueve sin la
    otra, este test lo dice (§3: dos copias del mismo criterio que se
    desincronizan es el error que originó todo el plan)."""

    def test_toda_excepcion_de_rt1_esta_tambien_en_es1(self):
        import test_le4_lecturas_filtran_activo as es1
        for sitio, razon in _rt1.SITIOS_CENSALES_PERMITIDOS.items():
            assert sitio in es1.SITIOS_DINAMICOS_PERMITIDOS, (
                f"{sitio} es excepción en RT1 y no en ES1 -- o la línea "
                f"cambió, o alguien ensanchó una lista sin la otra. "
                f"Razón declarada en RT1: {razon}")

    def test_cada_excepcion_declara_su_razon(self):
        for sitio, razon in _rt1.SITIOS_CENSALES_PERMITIDOS.items():
            assert len(razon) > 40, f"{sitio} sin razón documentada"

    def test_rt1_no_hereda_los_sitios_opacos_de_es1(self):
        """Heredarlos anularía el frente dinámico justo donde aporta: un
        sitio opaco al AST sí es legible en tiempo de ejecución."""
        import test_le4_lecturas_filtran_activo as es1
        assert not (set(_rt1.SITIOS_CENSALES_PERMITIDOS)
                    & set(es1.SITIOS_OPACOS_PERMITIDOS))


class TestDenominadorDeCobertura:
    """§9.3 exige publicar "el número de funciones lectoras realmente
    ejercitadas". El numerador lo mide el interceptor; el DENOMINADOR se
    deriva del árbol en cada corrida en vez de congelarse, porque un número
    escrito a mano envejece en silencio -- la forma exacta del defecto que
    este plan persigue."""

    def test_coincide_con_la_medicion_del_plan(self):
        lectoras = _rt1.lectoras_del_bloque_qc()
        assert len(lectoras) == 19, (
            f"§2.5 del plan midió 19 funciones de producción que leen alguna "
            f"de las 22 tablas hijas; ahora salen {len(lectoras)}. Si el "
            f"cambio es deliberado, actualiza el plan y este número a la vez; "
            f"si no, alguien añadió una lectura nueva sin enterarse.\n"
            + "\n".join(f"  {a}::{f}" for a, f in sorted(lectoras)))

    def test_las_lectoras_son_de_produccion_y_ninguna_de_tests(self):
        for archivo, _ in _rt1.lectoras_del_bloque_qc():
            assert Path(archivo).parts[0] in _rt1._DIRS_PRODUCCION

    def test_el_informe_publica_la_fraccion(self):
        informe = _rt1.informe_cobertura()
        assert "FUNCIONES LECTORAS del bloque de QC ejercitadas:" in informe
        assert "deuda nominal" in informe
