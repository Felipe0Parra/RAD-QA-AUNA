"""CD.5b (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, DA-94): la parte de dosis no tiene ninguna curva de la capa gris.

El pedido del físico (01-11): «En esta parte de dosis tampoco incluyas curvas para la capa gris de ningun tipo». La curva de una calibración cubre SOLO las capas de color, `curva_dosis.CAPAS_DE_LA_CURVA`
(R, G y B), UNA definición de la que salen el cero, el ajuste, los estados, la copia guardada y su lectura, el servicio, la ventana de calibración (la tabla de piezas, la de la curva, el gráfico y los
residuos), la regla de la base, `curva_efectiva`, los avisos de la virgen y el eje de la dosis. El piso de la película y la medida de una pieza (CD.2) siguen con las cuatro capas: no son una curva.

Lo que fija:
  (1) la definición es UNA, vive en el motor de la curva y es la de las capas de color; nadie más la escribe y los módulos de la curva no nombran la lista con el gris ni el literal «gris»;
  (2) el motor: la curva, su cero, sus piezas y su copia no tienen el gris; pedirle el gris es un `ValueError` con la regla entera; una pieza de 0 cGy sirve de cero por las capas de la curva; una
      copia de cuatro capas se rechaza al leerla, con su motivo;
  (3) el servicio: el estado guardado, el detalle de la auditoría y lo medido de cada pieza (la parte que entra a la curva) sin el gris, con la medición de CD.2 entera; una calibración guardada que
      solo fuera «válida» en el gris no es una vigente válida;
  (4) la ventana de calibración: ninguna columna, fila, curva, par, residuo, rótulo ni texto del gris;
  (5) el motor mensual: el gris nunca pasa a dosis (la regla de la base lo dice con su motivo, en su lugar del orden), `curva_de_la_capa` no lo da, `curva_efectiva` no cuenta una copia con él, los
      avisos de la virgen no lo miran y el eje de la dosis no lo cuenta; en un análisis en dosis el gris queda «no medible en dosis» y en netOD se sigue midiendo (los clics se refinan sobre él, DA-93).
  RONDA 1 DE LA REVISIÓN (01-11, CD5b-REV1-*; cada una con su mutación de `cd5b_mutaciones.py`, M18 en adelante): la guarda por AST de «cada sitio deriva de la definición» tenía su lista de sitios escrita a
      mano y le faltaban dos del servicio y el texto de las capas del motor mensual, y la guarda de la propia curva no estaba amarrada a la definición (P1, P2): ahora la lista es el censo de las funciones que
      nombran la definición en esos tres archivos, una prueba exige que esté completo, y la guarda de la capa y el ajuste entero del motor se prueban CAMBIANDO la definición; la regla de la base y los avisos
      de la virgen se prueban sin la fixture `escena` (P3): si el análisis en dosis revienta por otra razón esas pruebas no caen por eso, y la regla se ve también con una curva que daría el gris por válido.
Las pruebas importan la producción POR PRUEBA: contra la base (la curva de cuatro capas) cada una cae con su error. Sin símbolos de correcto o incorrecto (DA-18).
"""
import ast
import copy
import dataclasses
import importlib
import json
import math
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_cd5_ventana_de_calibracion import (_virgen_a_600, _cursor_limpio, app, bd, cargar_todas, catalogo, celdas, dialogos,  # noqa: F401 (fixtures)
                                              escaneos, escaneos_a_600_ppp, escaneos_con_el_rojo_recortado, fabrica, plantilla)
from test_cd6_base_dosis_del_motor import escena  # noqa: F401 (fixture: la placa de la verdad, su curva y sus dos análisis)

RAIZ = Path(__file__).resolve().parent.parent
MOTOR_PY = RAIZ / "analisisImagenes" / "curva_dosis.py"
SERVICIO_PY = RAIZ / "services" / "curva_dosis.py"
DIBUJO_PY = RAIZ / "analisisImagenes" / "dibujo_curva_dosis.py"
VENTANA_PY = RAIZ / "ui" / "paginasControles" / "PruebasMensuales" / "curva_dosis.py"
MENSUAL_PY = RAIZ / "analisisImagenes" / "placa_mensual.py"
DIBUJO_MENSUAL_PY = RAIZ / "analisisImagenes" / "dibujo_placa_mensual.py"
CAPAS_DE_LA_CURVA = ("R", "G", "B")                    # escritas AQUÍ a propósito: la prueba fija la regla, no la importa
SIN_CURVA_EN_LA_CURVA = "la curva de dosis calibra solo las capas R, G, B; 'gris' no tiene curva"
FUERA_DE_LA_CURVA = "la curva de dosis no calibra la capa gris: solo calibra las capas roja, verde y azul"
NO_MEDIBLE_EN_DOSIS = "no medible en dosis: "
BASE_OD = "densidad óptica neta"
VALIDA = "válida"
ENCABEZADO = {"lote": "L-5b", "tipo_pelicula": "EBT3", "fecha_irradiacion": "2026-11-01", "energia": "6 MV"}
# El censo de los sitios del servicio, del motor mensual y de su dibujo que se derivan de la definición (CD5b-REV1-P1 y P2): TODA función de esos tres archivos que nombre `CAPAS_DE_LA_CURVA` está aquí
# (lo exige `test_ningun_sitio_nombra_la_definicion_sin_estar_en_la_guarda`). Los siete primeros, en su orden de siempre; los tres últimos, los que la lista a mano había dejado fuera.
SITIOS_QUE_DERIVAN_DE_LA_DEFINICION = [(MENSUAL_PY, "base_de_la_capa"), (MENSUAL_PY, "curva_de_la_capa"), (MENSUAL_PY, "avisos_de_la_virgen"), (MENSUAL_PY, "curva_efectiva"),
                                       (DIBUJO_MENSUAL_PY, "eje_de_la_dosis"), (SERVICIO_PY, "vigentes_validas"), (SERVICIO_PY, "_estado_por_capa"),
                                       (SERVICIO_PY, "_detalle"), (SERVICIO_PY, "_pieza_desde_la_fila"), (MENSUAL_PY, "_texto_de_las_capas_de_la_curva")]


def cd():
    return importlib.import_module("analisisImagenes.curva_dosis")


def svc():
    return importlib.import_module("services.curva_dosis")


def dib():
    return importlib.import_module("analisisImagenes.dibujo_curva_dosis")


def pm():
    return importlib.import_module("analisisImagenes.placa_mensual")


def dpm():
    return importlib.import_module("analisisImagenes.dibujo_placa_mensual")


def pel():
    return importlib.import_module("analisisImagenes.pelicula")


def _P():
    return copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA)


def _arbol(ruta):
    return ast.parse(ruta.read_text(encoding="utf-8"))


def _funcion(arbol, nombre):
    return next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == nombre)


def _nombres(nodo):
    return {n.id for n in ast.walk(nodo) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(nodo) if isinstance(n, ast.Attribute)}


def _medidas(juego):
    return [cd().pieza_de_calibracion(o, float(d), float(d), pel().medir_pieza_uniforme(datos, _P(), nombre, "2026-11-01", escala="declarada")) for o, (d, nombre, datos) in sorted(juego.items())]


@pytest.fixture(scope="module")
def medidas(escaneos):
    return _medidas(escaneos)


@pytest.fixture(scope="module")
def curva(medidas):
    return cd().ajustar(medidas, u_dosis_medida_pct=1.5)


def _claves(objeto):
    """Todas las claves de diccionario de un JSON (a cualquier profundidad)."""
    if isinstance(objeto, dict):
        return set(objeto) | set().union(*(_claves(v) for v in objeto.values()))
    if isinstance(objeto, list):
        return set().union(*(_claves(v) for v in objeto)) if objeto else set()
    return set()


# ===================================================================================================== (1) UNA definición

class TestUnaSolaDefinicion:
    def test_las_capas_de_la_curva_son_las_de_color(self):
        assert cd().CAPAS_DE_LA_CURVA == CAPAS_DE_LA_CURVA and cd().CAPAS_DE_LA_CURVA is pel().CAPAS, "las capas de la curva son las de color, la misma tupla que ofrece el menú (DA-85)"
        assert pel().CAPAS_DEL_PISO == ("R", "G", "B", "gris"), "el piso sigue con las cuatro: no es una curva"

    def test_nadie_mas_la_define(self):
        definiciones = []
        for carpeta in ("analisisImagenes", "services", "ui", "models", "data"):
            for ruta in sorted((RAIZ / carpeta).rglob("*.py")):
                for n in ast.walk(_arbol(ruta)):
                    if isinstance(n, (ast.Assign, ast.AnnAssign)):
                        destinos = n.targets if isinstance(n, ast.Assign) else [n.target]
                        if any(isinstance(t, ast.Name) and t.id == "CAPAS_DE_LA_CURVA" for t in destinos):
                            definiciones.append(str(ruta.relative_to(RAIZ)))
        assert definiciones == ["analisisImagenes/curva_dosis.py"], definiciones

    @pytest.mark.parametrize("ruta", [MOTOR_PY, SERVICIO_PY, DIBUJO_PY, VENTANA_PY], ids=lambda r: r.name if r.parent.name != "PruebasMensuales" else "ventana")
    def test_los_modulos_de_la_curva_no_nombran_el_gris(self, ruta):
        arbol = _arbol(ruta)
        assert "CAPAS_DEL_PISO" not in _nombres(arbol) and not any(isinstance(a, ast.alias) and a.name == "CAPAS_DEL_PISO" for a in ast.walk(arbol)), "la lista de capas con el gris"
        docstrings = {id(n.body[0].value) for n in ast.walk(arbol) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body and isinstance(n.body[0], ast.Expr)}
        de_codigo = [n.lineno for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, str) and "gris" in n.value.lower() and id(n) not in docstrings]
        assert not de_codigo, f"un texto o una clave del gris en {ruta.name}, líneas {de_codigo}"

    def test_el_dibujo_de_la_calibracion_toma_sus_capas_de_la_definicion(self):
        assert dib().CAPAS is cd().CAPAS_DE_LA_CURVA
        assert list(dib().COLUMNA_DE_LA_CAPA) == list(CAPAS_DE_LA_CURVA) and dib().COLUMNA_QUITAR == len(dib().COLUMNAS_DE_LAS_PIEZAS) - 1
        assert [dib().COLUMNAS_DE_LAS_PIEZAS[dib().COLUMNA_DE_LA_CAPA[c]] for c in CAPAS_DE_LA_CURVA] == ["netOD roja [1]", "netOD verde [1]", "netOD azul [1]"]
        valores = {t.id: n.value for n in _arbol(DIBUJO_PY).body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
        assert isinstance(valores["COLUMNA_DE_LA_CAPA"], ast.DictComp) and not isinstance(valores["COLUMNA_QUITAR"], ast.Constant), "las columnas salen de las capas, no se escriben a mano"
        assert not any(isinstance(e, ast.Constant) and str(e.value).startswith("netOD ") for e in valores["COLUMNAS_DE_LAS_PIEZAS"].elts), "ninguna columna de una capa escrita a mano"

    @pytest.mark.parametrize("ruta,funcion", SITIOS_QUE_DERIVAN_DE_LA_DEFINICION)
    def test_cada_sitio_del_motor_mensual_y_del_servicio_deriva_de_la_definicion(self, ruta, funcion):
        nombres = _nombres(_funcion(_arbol(ruta), funcion))
        assert "CAPAS_DE_LA_CURVA" in nombres and "CAPAS_DEL_PISO" not in nombres, (funcion, sorted(n for n in nombres if n.isupper()))

    @pytest.mark.parametrize("ruta", [SERVICIO_PY, MENSUAL_PY, DIBUJO_MENSUAL_PY], ids=lambda r: r.name)
    def test_ningun_sitio_nombra_la_definicion_sin_estar_en_la_guarda(self, ruta):
        """CD5b-REV1-P1: la lista de arriba es el censo COMPLETO de esos tres archivos, no una selección: las funciones (de módulo o métodos) que nombran `CAPAS_DE_LA_CURVA` son exactamente las de la lista.
        Una función nueva que la nombre se agrega a la lista a propósito; sin esto, un sitio fuera de la lista puede dejar de derivar de la definición sin que nada lo vea."""
        arbol = _arbol(ruta)
        funciones = [n for padre in ast.walk(arbol) if isinstance(padre, (ast.Module, ast.ClassDef)) for n in padre.body if isinstance(n, ast.FunctionDef)]
        nombran = sorted(f.name for f in funciones if "CAPAS_DE_LA_CURVA" in _nombres(f))
        assert nombran == sorted(funcion for r, funcion in SITIOS_QUE_DERIVAN_DE_LA_DEFINICION if r == ruta), nombran


# ===================================================================================================== (2) el motor de la curva

class TestElMotorNoTieneGris:
    def test_la_curva_su_cero_y_sus_piezas_son_de_las_capas_de_color(self, curva, medidas):
        assert set(curva.capas) == set(CAPAS_DE_LA_CURVA) and set(curva.cero["capas"]) == set(CAPAS_DE_LA_CURVA)
        assert all(set(p.capas) == set(CAPAS_DE_LA_CURVA) for p in curva.piezas)
        assert all(curva.estado(c) == VALIDA for c in CAPAS_DE_LA_CURVA), {c: curva.estado(c) for c in CAPAS_DE_LA_CURVA}
        assert all(set(m.capas) == set(CAPAS_DE_LA_CURVA) for m in medidas), "`pieza_de_calibracion` arma solo las capas de la curva"
        assert all("gris" in m.medida.centro for m in medidas), "la medida de CD.2 sigue con las cuatro capas"

    def test_la_copia_no_tiene_el_gris(self, curva):
        copia = json.loads(json.dumps(curva.como_dict()))
        assert "gris" not in _claves(copia) and "gris" not in json.dumps(copia, ensure_ascii=False)
        assert cd().curva_desde_dict(copia).como_dict() == copia

    def test_con_la_virgen_de_cero_tampoco_hay_gris(self, escaneos_a_600_ppp):
        """El cero de la película virgen montada (DC3, el segundo de la regla) se toma solo de las capas de la curva."""
        c = cd().ajustar(_medidas(escaneos_a_600_ppp), virgen=_virgen_a_600()[1])
        assert c.cero["fuente"] == "pelicula_virgen" and set(c.cero["capas"]) == set(CAPAS_DE_LA_CURVA), c.cero
        assert set(c.capas) == set(CAPAS_DE_LA_CURVA) and "gris" not in _claves(json.loads(json.dumps(c.como_dict())))

    def test_sin_cero_tampoco_hay_gris(self, medidas):
        """Sin con qué hacer el cero (ninguna pieza de 0 cGy, ninguna virgen, ninguna dosis medida) cada capa de la curva es «incompleta» y el gris no aparece."""
        sin_dosis = [dataclasses.replace(p, dosis_medida_cgy=None) for p in medidas[1:]]
        c = cd().ajustar(sin_dosis)
        assert c.cero is None and set(c.capas) == set(CAPAS_DE_LA_CURVA) and all(c.estado(k).startswith("incompleta: ") for k in CAPAS_DE_LA_CURVA)
        assert cd().curva_desde_dict(json.loads(json.dumps(c.como_dict()))).como_dict() == json.loads(json.dumps(c.como_dict()))

    @pytest.mark.parametrize("pedido", ["estado", "rango", "dosis", "netod", "incertidumbre"])
    def test_pedirle_el_gris_dice_la_regla_entera(self, curva, pedido):
        llamada = {"estado": lambda: curva.estado("gris"), "rango": lambda: curva.rango("gris"), "dosis": lambda: curva.dosis("gris", 0.2), "netod": lambda: curva.netod("gris", 100.0),
                   "incertidumbre": lambda: curva.incertidumbre("gris", 0.2, 0.001)}[pedido]
        with pytest.raises(ValueError) as error:
            llamada()
        assert str(error.value) == SIN_CURVA_EN_LA_CURVA

    def test_la_guarda_de_la_capa_sigue_a_la_definicion(self, curva, monkeypatch):
        """CD5b-REV1-P2: la guarda de la curva (`CurvaDeDosis._exige_la_capa`) y su regla entera salen de la DEFINICIÓN, no de las capas que la curva traiga (hoy dan lo mismo, y por eso solo se ve cambiando la
        definición): con ella reducida a R y G, el azul, que esta curva SÍ trae, tampoco tiene curva y la regla nombra las dos que quedan."""
        monkeypatch.setattr(cd(), "CAPAS_DE_LA_CURVA", ("R", "G"))
        assert curva.estado("R") == VALIDA and curva.rango("G") == curva.capas["G"]["rango_cgy"], "las capas de la definición siguen respondiendo"
        with pytest.raises(ValueError) as error:
            curva.estado("B")
        assert str(error.value) == "la curva de dosis calibra solo las capas R, G; 'B' no tiene curva"

    def test_con_la_definicion_reducida_el_ajuste_entero_y_su_copia_son_de_esas_capas(self, medidas, monkeypatch):
        """CD5b-REV1-P2 (la clase, en el motor): el cero, las piezas, los estados y la copia (su lectura exige exactamente esas capas) salen de la DEFINICIÓN y no de las capas que traigan las piezas medidas (hoy dan
        lo mismo, y por eso solo se ve cambiando la definición): con ella reducida a R y G, el ajuste de las MISMAS piezas medidas (que traen R, G y B) es de R y G, y una copia con el azul se rechaza."""
        monkeypatch.setattr(cd(), "CAPAS_DE_LA_CURVA", ("R", "G"))
        c = cd().ajustar(medidas, u_dosis_medida_pct=1.5)
        assert set(c.capas) == {"R", "G"} and set(c.cero["capas"]) == {"R", "G"} and all(set(p.capas) == {"R", "G"} for p in c.piezas), "el ajuste entero es de las capas de la definición"
        copia = json.loads(json.dumps(c.como_dict()))
        assert cd().curva_desde_dict(copia).como_dict() == copia
        copia["capas"]["B"] = copy.deepcopy(copia["capas"]["G"])
        with pytest.raises(ValueError) as error:
            cd().curva_desde_dict(copia)
        assert str(error.value) == "La curva de dosis está dañada: las capas no trae exactamente sus claves: R, G."

    def test_una_pieza_de_0_cgy_sirve_de_cero_por_las_capas_de_la_curva(self, medidas):
        """Una pieza que trajera un gris sin valor (fuera de contrato: `pieza_de_calibracion` ya no lo pone) sirve de cero igual: el cero mira solo las capas de la curva."""
        cero = medidas[0]
        assert cero.dosis_nominal_cgy == 0
        con_gris = dataclasses.replace(cero, capas={**cero.capas, "gris": {**cero.capas["R"], "valor": 0.0}})
        c = cd().ajustar([con_gris, *medidas[1:]])
        assert c.cero["fuente"] == "piezas_de_0_cgy" and not any("no sirve de cero" in a for a in c.avisos), c.avisos
        assert set(c.capas) == set(CAPAS_DE_LA_CURVA) and all(set(p.capas) == set(CAPAS_DE_LA_CURVA) for p in c.piezas)

    def test_el_aviso_de_una_pieza_negra_nombra_las_capas_de_la_curva(self, medidas):
        cero = medidas[0]
        negra = dataclasses.replace(cero, capas={c: {**f, "valor": 0.0} for c, f in cero.capas.items()})
        c = cd().ajustar([negra, *medidas[1:]])
        assert "la pieza 1 (0 cGy) no sirve de cero: su valor no es positivo en R, G, B y sin un valor positivo no hay densidad óptica neta" in c.avisos, c.avisos

    @pytest.mark.parametrize("donde", ["capas", "cero", "pieza"])
    def test_una_copia_de_cuatro_capas_se_rechaza_con_su_motivo(self, curva, donde):
        copia = json.loads(json.dumps(curva.como_dict()))
        if donde == "capas":
            copia["capas"]["gris"] = copy.deepcopy(copia["capas"]["G"])
            motivo = "La curva de dosis está dañada: las capas no trae exactamente sus claves: R, G, B"
        elif donde == "cero":
            copia["cero"]["capas"]["gris"] = copy.deepcopy(copia["cero"]["capas"]["G"])
            motivo = "La curva de dosis está dañada: las capas del cero no trae exactamente sus claves: R, G, B"
        else:
            copia["piezas"][2]["capas"]["gris"] = copy.deepcopy(copia["piezas"][2]["capas"]["G"])
            motivo = "La curva de dosis está dañada: las capas de la pieza 3 de la lista no trae exactamente sus claves: R, G, B"
        with pytest.raises(ValueError) as error:
            cd().curva_desde_dict(copia)
        assert str(error.value) == motivo + "."


# ===================================================================================================== (3) el servicio

class TestElServicio:
    def _guardar(self, escaneos):
        piezas = [{"orden": o, "dosis_nominal_cgy": float(d), "dosis_medida_cgy": float(d), "datos": datos, "nombre_archivo": nombre} for o, (d, nombre, datos) in sorted(escaneos.items())]
        return svc().guardar("fisico", dict(ENCABEZADO), piezas)

    def test_lo_guardado_no_tiene_curva_del_gris_y_la_medicion_de_cd2_sigue_entera(self, bd, escaneos):
        r = svc().leer(self._guardar(escaneos))
        assert r["estado"] == {c: VALIDA for c in CAPAS_DE_LA_CURVA}
        assert "gris" not in _claves(r["ajuste"])
        for p in r["piezas"]:
            assert set(p["medida"]["pieza"]["capas"]) == set(CAPAS_DE_LA_CURVA), "lo que entra a la curva: sin el gris"
            assert "gris" in p["medida"]["medicion"]["centro"], "la medición de CD.2 se guarda entera (las cuatro capas)"
        detalle = sqlite3.connect(bd).execute("SELECT detalle FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()[0]
        assert detalle.endswith("; R: válida; G: válida; B: válida") and "gris" not in detalle, detalle
        assert svc().diferencias(r, svc().recalcular(r)) == []

    def test_una_calibracion_que_solo_seria_valida_en_el_gris_no_es_una_vigente_valida(self, bd, escaneos):
        """Una fila cuyo estado guardado tuviera el gris «válida» y las capas de color no (fuera de contrato: CD.5b ya no lo escribe; así quedaría una fila de antes) no es una vigente válida."""
        nueva = self._guardar(escaneos)
        assert [r["id"] for r in svc().vigentes_validas()] == [nueva]
        estado = {"R": "incompleta: de prueba", "G": "no válida: de prueba", "B": "incompleta: de prueba", "gris": VALIDA}
        con = sqlite3.connect(bd)
        con.execute("UPDATE calibracion_pelicula SET estado = ? WHERE id = ?", (json.dumps(estado, ensure_ascii=False), nueva))
        con.commit()
        con.close()
        assert svc().vigentes_validas() == []


# ===================================================================================================== (4) la ventana de calibración

def _textos(v):
    from PyQt5.QtWidgets import QLabel, QPushButton, QTableWidget
    textos = [w.text() for w in v.findChildren((QLabel, QPushButton))] + [w.toolTip() for w in v.findChildren(QPushButton)]
    for t in v.findChildren(QTableWidget):
        textos += [t.horizontalHeaderItem(c).text() for c in range(t.columnCount()) if t.horizontalHeaderItem(c)]
        textos += [x for fila in celdas(t) for x in fila if x]
    return textos


class TestLaVentana:
    def test_ninguna_columna_fila_curva_par_residuo_ni_rotulo_del_gris(self, fabrica, dialogos, tmp_path, escaneos):
        v = fabrica()
        cargar_todas(v, dialogos, tmp_path, escaneos)
        encabezados = [v.tabla_piezas.horizontalHeaderItem(c).text() for c in range(v.tabla_piezas.columnCount())]
        assert encabezados == ["Dosis nominal [cGy]", "Imagen", "Archivo", "Dosis medida [cGy]", "netOD roja [1]", "netOD verde [1]", "netOD azul [1]", "Quitar"]
        assert [f[0] for f in celdas(v.tabla_curva)] == ["capa roja", "capa verde", "capa azul"]
        for eje in (v.eje_curva, v.eje_residuos):
            gids = [l.get_gid() or "" for l in eje.lines] + [c.get_gid() or "" for c in eje.collections]
            assert gids and not any("gris" in g for g in gids), gids
            assert not any("gris" in r for r in eje.get_legend_handles_labels()[1])
        assert {g.split("_")[1] for g in (l.get_gid() or "" for l in v.eje_curva.lines) if g.startswith("curva_")} == set(CAPAS_DE_LA_CURVA)
        assert not [t for t in _textos(v) if "gris" in t.lower()], [t for t in _textos(v) if "gris" in t.lower()]

    def test_guardar_una_curva_con_capas_no_validas_las_nombra_sin_el_gris(self, fabrica, dialogos, tmp_path, escaneos_con_el_rojo_recortado):
        from test_cd5_ventana_de_calibracion import llenar_el_encabezado
        v = fabrica()
        cargar_todas(v, dialogos, tmp_path, escaneos_con_el_rojo_recortado)
        llenar_el_encabezado(v)
        v.boton_guardar.click()
        preguntas = [c["texto"] for c in dialogos.de("question")]
        assert preguntas and "capa roja: " in preguntas[0] and "gris" not in preguntas[0], preguntas


# ===================================================================================================== (5) el motor mensual

def _con_una_capa_de_mas(curva, capa, **fila):
    """La curva con una capa que no es de la curva (fuera de contrato: nadie la escribe así desde CD.5b), para ver que ningún sitio la cuenta."""
    capas = copy.deepcopy(curva.capas)
    capas[capa] = {**copy.deepcopy(capas["G"]), **fila}
    return dataclasses.replace(curva, capas=capas)


class TestElMotorMensual:
    def test_la_regla_de_la_base_no_pasa_el_gris_a_dosis_y_dice_por_que(self, curva):
        """CD5b-REV1-P3: SIN la fixture `escena` (el análisis en dosis entero): la regla se prueba con la curva de este archivo, un piso de película virgen y la cadena de la propia curva. Si el análisis en dosis
        revienta por otra razón, esta prueba no cae por eso; cae por lo que dice la regla."""
        piso, cadena = SimpleNamespace(estado="ok", origen="virgen"), curva.cadena
        assert pm().base_de_la_capa(curva, "gris", piso, cadena) == (BASE_OD, FUERA_DE_LA_CURVA)
        assert pm().base_de_la_capa(None, "gris", piso, cadena) == (BASE_OD, pm().MOTIVO_SIN_CURVA), "la primera condición sigue siendo que haya curva"
        assert all(pm().base_de_la_capa(curva, c, piso, cadena) == (pm().BASE_DOSIS, None) for c in CAPAS_DE_LA_CURVA)

    def test_la_regla_de_la_base_no_pasa_el_gris_aunque_la_curva_lo_diera_por_valido(self, curva):
        """CD5b-REV1-P3: que la regla rechace el gris no es solo un efecto de que la curva lo rechace (CD5b-D8, defensa en profundidad): una curva que diera el gris por válido, con su cero de 0 cGy, su cadena
        y un piso de película virgen, tampoco lo pasa a dosis. Es la aserción de la regla, sin que el `ValueError` de la curva la tape."""
        piso, cadena = SimpleNamespace(estado="ok", origen="virgen"), curva.cadena
        permisiva = SimpleNamespace(estado=lambda capa: VALIDA, cero=curva.cero, cadena=cadena)
        assert all(pm().base_de_la_capa(permisiva, c, piso, cadena) == (pm().BASE_DOSIS, None) for c in CAPAS_DE_LA_CURVA), "el control: esa curva deja pasar todo lo demás"
        assert pm().base_de_la_capa(permisiva, "gris", piso, cadena) == (BASE_OD, FUERA_DE_LA_CURVA)

    def test_curva_de_la_capa_no_da_el_gris(self, escena):
        with pytest.raises(ValueError) as error:
            pm().curva_de_la_capa(escena.curva, "gris")
        assert str(error.value) == FUERA_DE_LA_CURVA + "."

    def test_en_un_analisis_en_dosis_el_gris_es_no_medible_en_dosis_y_en_netod_se_sigue_midiendo(self, escena):
        gris = escena.do.capas["gris"]
        assert gris.estado == NO_MEDIBLE_EN_DOSIS + FUERA_DE_LA_CURVA and gris.base == BASE_OD and gris.motivo_de_la_base == FUERA_DE_LA_CURVA
        assert all(escena.do.capas[c].ok and escena.do.capas[c].base == pm().BASE_DOSIS for c in CAPAS_DE_LA_CURVA)
        assert escena.od.capas["gris"].ok, "en netOD el motor sigue midiendo el gris (DA-93: no se muestra)"
        assert not any("gris" in a for a in escena.do.avisos_de_la_dosis)

    def test_curva_efectiva_no_cuenta_una_copia_con_el_gris(self, escena):
        copia = json.loads(json.dumps(escena.curva.como_dict()))
        for c in CAPAS_DE_LA_CURVA:
            copia["capas"][c]["estado"] = "no válida: de prueba"
        sin_validas = {"id": 3, "lote": "L-3", "fecha_irradiacion": "2026-10-30", "ajuste": copy.deepcopy(copia)}
        copia["capas"]["gris"] = {**copy.deepcopy(copia["capas"]["G"]), "estado": VALIDA}
        solo_el_gris = {"id": 4, "lote": "L-4", "fecha_irradiacion": "2026-10-31", "ajuste": copia}
        e = pm().curva_efectiva([solo_el_gris, sin_validas], escena.cadena)
        assert e.curva is None and e.motivo.startswith(pm().MOTIVO_SIN_CURVA + ": no hay ninguna calibración vigente con una capa válida") and "1 con la copia de la curva dañada" in e.motivo, e.motivo

    def test_los_avisos_de_la_virgen_no_miran_el_gris(self, curva):
        """CD5b-REV1-P3: SIN la fixture `escena` (si el análisis en dosis revienta por mirar el gris, esta prueba cae por sus avisos y no por la preparación de la fixture)."""
        i0 = {c: curva.cero["capas"][c]["i0"] for c in CAPAS_DE_LA_CURVA}
        piso = SimpleNamespace(estado="ok", origen="virgen", capas={**{c: SimpleNamespace(mediana=i0[c]) for c in CAPAS_DE_LA_CURVA}, "gris": SimpleNamespace(mediana=1.0)})
        assert pm().avisos_de_la_virgen(curva, piso, 2.0) == ()
        piso.capas["B"] = SimpleNamespace(mediana=i0["B"] * 1.05)
        avisos = pm().avisos_de_la_virgen(curva, piso, 2.0)
        assert len(avisos) == 1 and "en la capa azul" in avisos[0], avisos

    def test_los_avisos_de_la_virgen_no_miran_el_gris_aunque_el_cero_lo_traiga(self, curva):
        """CD5b-REV1-P3: la aserción de los avisos, sin que el `KeyError` de un cero sin gris la tape: con un gris en el cero de la curva (fuera de contrato) y un piso que lo contradice al 100 %, el gris no se mira."""
        i0 = {c: curva.cero["capas"][c]["i0"] for c in CAPAS_DE_LA_CURVA}
        con_gris_en_el_cero = dataclasses.replace(curva, cero={**curva.cero, "capas": {**curva.cero["capas"], "gris": {"i0": 1.0, "u_i0": 0.0}}})
        piso = SimpleNamespace(estado="ok", origen="virgen", capas={**{c: SimpleNamespace(mediana=i0[c]) for c in CAPAS_DE_LA_CURVA}, "gris": SimpleNamespace(mediana=2.0)})
        assert pm().avisos_de_la_virgen(con_gris_en_el_cero, piso, 2.0) == ()
        piso.capas["B"] = SimpleNamespace(mediana=i0["B"] * 1.05)
        avisos = pm().avisos_de_la_virgen(con_gris_en_el_cero, piso, 2.0)
        assert len(avisos) == 1 and "en la capa azul" in avisos[0], avisos

    def test_el_eje_de_la_dosis_cuenta_solo_las_capas_de_la_curva(self, escena):
        tope = dpm().eje_de_la_dosis(escena.curva)
        mayor = max(escena.curva.rango(c) for c in CAPAS_DE_LA_CURVA)
        assert tope == dpm().PASO_DEL_EJE_DE_LA_DOSIS_CGY * math.ceil(mayor / dpm().PASO_DEL_EJE_DE_LA_DOSIS_CGY)
        con_otra = _con_una_capa_de_mas(escena.curva, "gris", rango_cgy=mayor + 500.0, estado=VALIDA)
        assert dpm().eje_de_la_dosis(con_otra) == tope, "una capa que no es de la curva no cuenta para el eje"
        rota = dataclasses.replace(escena.curva, capas={**copy.deepcopy(escena.curva.capas), "B": {**copy.deepcopy(escena.curva.capas["B"]), "rango_cgy": mayor + 200.0}})
        assert dpm().eje_de_la_dosis(rota) == dpm().PASO_DEL_EJE_DE_LA_DOSIS_CGY * math.ceil((mayor + 200.0) / dpm().PASO_DEL_EJE_DE_LA_DOSIS_CGY), "el azul sí cuenta"
