"""A.1 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md SS0.1): `seiscientos_mensual.py`
crea un boton 'Volver' conectado a `self._volver_a_preINIGI(...)`, un metodo
que no existe en ningun archivo del proyecto. Hoy es inerte solo porque la
linea que lo agregaria al layout esta comentada -- descomentarla produciria
un `AttributeError` que PyQt se traga (el fisico pulsa y no pasa nada).

Este test censa, por AST, TODAS las llamadas `self.<algo>(...)` del cuerpo
de `PruebaMensual600` y exige que cada nombre resuelva en la clase o su MRO.
Dos excepciones legitimas, ambas de despacho dinamico hacia subclases
(PruebaMensual600 es la base de PruebaMensualIX), y las dos guardadas por
`hasattr` antes de la llamada -- nunca se alcanzan sobre la clase base:
`addsomething_ix` (:892, tras `hasattr(self, 'esIX') and self.esIX`) y
`Traerinfo_conos` (:3292, tras `hasattr(self, 'Traerinfo_conos')` explicito).
"""
import ast
from pathlib import Path

import pytest

ARCHIVO = (
    Path(__file__).resolve().parent.parent
    / "ui" / "paginasControles" / "PruebasMensuales" / "seiscientos_mensual.py"
)

# Despacho dinamico legitimo hacia metodos que solo existen en subclases,
# guardado por `hasattr` en el propio sitio de la llamada -- no una fuga.
NOMBRES_DESPACHO_DINAMICO_PERMITIDOS = {
    "addsomething_ix",
    "Traerinfo_conos",
}


def _clase_pruebamensual600():
    tree = ast.parse(ARCHIVO.read_text(encoding="utf-8"), filename=str(ARCHIVO))
    for nodo in ast.walk(tree):
        if isinstance(nodo, ast.ClassDef) and nodo.name == "PruebaMensual600":
            return nodo
    raise AssertionError("No se encontro la clase PruebaMensual600")


def _nombres_llamados_sobre_self(clase_nodo):
    nombres = set()
    for nodo in ast.walk(clase_nodo):
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute):
            valor = nodo.func.value
            if isinstance(valor, ast.Name) and valor.id == "self":
                nombres.add(nodo.func.attr)
    return nombres


def _cargar_clase_real():
    from ui.paginasControles.PruebasMensuales.seiscientos_mensual import (
        PruebaMensual600,
    )
    return PruebaMensual600


class TestNingunMetodoInexistenteEnPruebaMensual600:
    def test_todo_self_punto_algo_resuelve_en_la_clase_o_su_mro(self):
        clase_nodo = _clase_pruebamensual600()
        nombres = _nombres_llamados_sobre_self(clase_nodo)
        clase_real = _cargar_clase_real()
        disponibles = set(dir(clase_real))

        faltantes = sorted(
            nombre for nombre in nombres
            if nombre not in disponibles
            and nombre not in NOMBRES_DESPACHO_DINAMICO_PERMITIDOS
        )
        assert faltantes == [], (
            f"self.<algo>(...) sin resolver en PruebaMensual600 o su MRO: "
            f"{faltantes} -- si es despacho dinamico hacia una subclase, "
            f"guardar con hasattr() y anadir a NOMBRES_DESPACHO_DINAMICO_PERMITIDOS "
            f"con su razon"
        )

    def test_los_dos_permitidos_siguen_guardados_por_hasattr(self):
        """Si algun dia dejan de estar guardados, este test debe fallar --
        la lista blanca no debe volverse una forma de ocultar una fuga real."""
        codigo = ARCHIVO.read_text(encoding="utf-8")
        assert "hasattr(self, 'esIX') and self.esIX" in codigo
        assert 'hasattr(self, "Traerinfo_conos")' in codigo
