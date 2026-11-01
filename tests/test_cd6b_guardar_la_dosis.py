"""CD.6b (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, DA-92, DC16, DA-81, DA-88): GUARDAR TAMBIEN LA DOSIS.

CAUSA: con CD.6 y CD.7 la dosis se mide y se ve, pero el registro solo guardaba la netOD. Lo decidio el fisico el 28-10: se guarda SIEMPRE la netOD y, cuando se pueda, tambien la dosis («mas columnas y
mas PDF»), al final del plan («dejemoslo de ultimo»); la copia guardada manda (DA-81).

LO QUE SE GARANTIZA, cada cosa contra una verdad que NO sale del servicio ni de la ventana (la placa sintetica de la verdad en dosis de CD.6, 100 x 99 mm a 300 cGy, la curva de CD.3 hecha con piezas de la
MISMA respuesta, el motor directamente y la base temporal leida con SQL propio):
  LAS COLUMNAS: siete de la dosis de la capa reportada y `curva` (la copia), admitiendo NULL, al FINAL de la tabla, en una base nueva y en una de antes de CD.6b (la migracion, aditiva e idempotente,
    no toca una fila: lo de antes queda en NULL, nunca en cero); la lista y las claves del motor son las mismas (`valores_medidos_en_dosis`, el par de `valores_medidos`).
  SIN DOSIS, COMO ANTES: sin curva, o si la capa reportada no cumple la regla del boton, las ocho quedan en NULL y la auditoria lo dice con el motivo. (Que la fila sea BYTE A BYTE la de antes de CD.6b lo
    prueba la compuerta del anexo, `cd6b_diferencial.py`, contra el commit anterior.)
  CON DOSIS: la dosis de la VERDAD (FWHM a 0.05 mm), la copia JSON estricta (la curva, su calibracion, la cadena de captura de la pelicula y la base de cada capa), la auditoria nombra la curva; la netOD guardada
    no cambia por guardar tambien la dosis; una curva que no es una `CurvaEfectiva` o una copia con NaN se rechazan sin escribir nada.
  REABRIR: `recalcular_en_dosis` mide con la COPIA aunque la calibracion se anule o haya otra vigente (el servicio no lee las calibraciones); una copia danada lo dice.
  LA VENTANA: el boton no cambia lo guardado (apagado y pulsado dan la MISMA fila); «Guardar» pasa la curva que juzga el boton; un registro abre en netOD y el boton pasa a dosis con la copia; tras «Recalcular»
    vuelve la curva vigente; anular la calibracion no cambia lo que muestra un registro.
  LA REVISION DE LA RONDA 1 (01-11; CD6b-REV1-PROD-01 a PROD-04 y REV1-P1 a P5; cada caso cae contra la mutacion de `cd6b_mutaciones.py` que nombra su docstring):
    LA CAPA REPORTADA: la regla y los valores guardados son los de la capa que el fisico reporta (R, G o B: DA-85), no los de la verde (`TestLaCapaReportada`).
    LA CADENA: el servicio juzga con la cadena de LOS BYTES y no se fia de la de la curva que le pasan; reabrir mide con la cadena GUARDADA y nunca con la de los bytes (CD6b-D4), en el servicio y en la ventana.
    LA COPIA DE OTRA FORMA: una copia que es JSON valido pero no tiene la forma que escribe `guardar` (no es un diccionario, le falta o le sobra una clave, la calibracion o la cadena no son lo que deben) es
    una copia DANADA: `curva_guardada` la dice con su motivo (nunca lanza), `recalcular_en_dosis` la rechaza como error del servicio y la ventana abre el registro en netOD con el boton gris y el motivo, sin
    quedar a medias (CD6b-D8).
    LO QUE NO COINCIDE: `diferencias_en_dosis` compara los siete valores guardados, uno por uno, y la ventana los dice todos.
    EL SEGUNDO CASO DE CD6b-D3: la regla se cumple pero al medir en dosis un perfil pasa el rango util (la dosis media de una meseta con cupula pasa la dosis de su nivel medio): se guarda «no medible en dosis: ...»
    con la copia y los numeros vacios, y reabrirlo dice lo mismo.
Rojo contra el commit de CD.7: no existen las columnas, `valores_medidos_en_dosis`, `curva=` de `guardar` ni `recalcular_en_dosis`: las pruebas caen con su error. La produccion se importa POR PRUEBA.
Lo caro (la placa de 600 ppp a 16 bits y la curva) son las fixtures de modulo de la prueba de CD.7 (`escena`); cada guardado es de su prueba.
"""
import ast
import copy
import dataclasses
import json
import math
import sqlite3
import types
from pathlib import Path

import pytest

import _placa_mensual_sintetica as gen
from _e1_ayudas import _cursor_limpio, app, cerrar, clic, dialogos, dibujo_mod, fabrica, pel, pm, sin_simbolos, svc, ventana_mod  # noqa: F401
from test_cd7_ventana_mensual_en_dosis import DOSIS_MESETA, REGISTRO, RESP, Usuario, abierta, calibracion, con_capa, escena, mundo, pulsar  # noqa: F401  (fixtures y ayudas de CD.7)
from test_d1_guardado_placa_mensual import USUARIO, _consulta, _control, _sql, bd, plantilla  # noqa: F401  (fixtures de D.1)

RAIZ = Path(__file__).resolve().parent.parent
TABLA = "analisis_placa_mensual"
DE_LA_DOSIS = ("estado_dosis", "fwhm_crossplane_dosis_mm", "fwhm_inplane_dosis_mm", "desfase_izquierdo_dosis_mm", "desfase_derecho_dosis_mm", "desfase_superior_dosis_mm",
               "desfase_inferior_dosis_mm", "curva")          # escritas AQUI (los nombres que leera CD.8), no leidas de la produccion
DE_LA_NETOD = ("estado", "fwhm_crossplane_mm", "fwhm_inplane_mm", "desfase_izquierdo_mm", "desfase_derecho_mm", "desfase_superior_mm", "desfase_inferior_mm")
LOTE, FECHA_IRR, ID_CAL = "L-31", "2026-10-30", 7
FWHM_X, FWHM_Y = 100.0, 99.0                              # la verdad de la placa de CD.6 (la de CD.7)
NO_SE_COMPARAN = ("id", "ref", "fecha_registro")          # lo que distingue dos guardados de la misma placa en dos controles


def efectiva(curva, id_=ID_CAL, lote=LOTE, fecha=FECHA_IRR):
    return pm().CurvaEfectiva(curva, id_, lote, fecha)


def guardar(escena, ref, curva=None, modo="virgen", capa="G", **extra):
    return svc().guardar(ref, USUARIO, escena.placa.datos, "placa_dosis.tif", escena.clics, copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA), capa, modo,
                         referencia_virgen=escena.ref if modo == "virgen" else None, curva=curva, **extra)


def fila_cruda(ruta, ref):
    """La fila VIGENTE leida con SQL propio (no con `svc.leer`): lo que de verdad quedo en la base, con NULL como None."""
    filas = _consulta(ruta, f"SELECT * FROM {TABLA} WHERE ref = ? AND activo = 1", (ref,))
    nombres = [c[1] for c in _consulta(ruta, f"PRAGMA table_info('{TABLA}')")]
    assert len(filas) == 1
    return dict(zip(nombres, filas[0]))


def auditoria(ruta, ref):
    return [d for (d,) in _consulta(ruta, "SELECT detalle FROM audit_log WHERE tabla = ? AND ref = ? ORDER BY id", (TABLA, str(ref)))]


def nulas(fila):
    return {n: fila[n] for n in DE_LA_DOSIS if fila[n] is not None}


def analizar_directo(escena, datos, clics):
    """La placa `datos` analizada por el MOTOR directamente, en netOD y en dosis (con la curva y la referencia virgen de `escena`), con las marcas refinadas como las refina el servicio."""
    P = copy.deepcopy(pm().VALORES_DE_LA_GEOMETRIA)
    pelicula = pel().leer_pelicula(datos)
    tam = pel().escala_mm(pelicula.dpi, P)
    marcas = [pm().refinar_marca(pelicula.gris, c, P, tam, pelicula.validos) for c in clics]
    cadena = pm().cadena_de_la_pelicula(datos, pelicula)
    od = pm().analizar(pelicula, marcas, P, modo_piso="virgen", referencia_virgen=escena.ref)
    P["base_de_la_medida"] = pm().BASE_DOSIS
    do = pm().analizar(pelicula, marcas, P, modo_piso="virgen", referencia_virgen=escena.ref, curva=escena.curva, cadena=cadena)
    return types.SimpleNamespace(od=od, do=do, cadena=cadena)


@pytest.fixture(scope="module")
def en_dosis(escena):
    """La placa analizada EN DOSIS por el MOTOR directamente, con las marcas refinadas como las refina el servicio (el oraculo de los valores guardados)."""
    return analizar_directo(escena, escena.placa.datos, escena.clics)


def netod_de_la_meseta(medida_de_la_capa):
    """La netOD de la meseta de cada perfil de una capa medida, como la juzga el motor: log10(piso / meseta). En un analisis en netOD la meseta es el nivel medio; en dosis, el nivel de la dosis media."""
    return [math.log10(m.piso / max(m.meseta, pm().VP_MINIMO)) for m in (medida_de_la_capa.crossplane, medida_de_la_capa.inplane)]


@pytest.fixture(scope="module")
def con_cupula(escena):
    """La placa de la verdad en dosis con una CUPULA de -3.5 % a 40 mm (las peliculas reales dan -2 a -5 %; el generador la declara): su meseta no es plana, asi que la dosis MEDIA de la meseta y la dosis de
    su NIVEL medio difieren (la curva es convexa: la media de las dosis pasa a la dosis de la media). Esa diferencia, del orden de 1e-6 de netOD, es lo unico que deja que la regla del boton se cumpla (la juzga
    con el nivel medio de la netOD) y que un perfil pase el rango util al medirlo en dosis (lo juzga con la dosis media): el segundo caso de CD6b-D3. Trae la placa, los clics, la referencia virgen de
    `escena` (para `guardar`) y lo que el MOTOR mide directamente en netOD y en dosis con la curva de `escena`."""
    placa = gen.generar("tiff", bits=16, variante="A", theta_deg=0.4, seed=1, ruido=0.0, respuestas_netod=RESP, dosis_meseta_cgy=DOSIS_MESETA, cupula_pct_40mm=-3.5)
    clics = [tuple(float(v) for v in placa.verdad.marcas_px[k]) for k in ("UL", "UR", "DR", "DL", "C")]
    directo = analizar_directo(escena, placa.datos, clics)
    return types.SimpleNamespace(placa=placa, clics=clics, ref=escena.ref, od=directo.od, do=directo.do)


COPIAS_DANADAS = {          # la copia guardada (el JSON de `curva`) tal como NO la escribe `guardar`: cada una es una forma distinta de estar danada (CD6b-REV1-PROD-01 y PROD-02)
    "es_una_lista": lambda c: [c],
    "es_un_texto": lambda c: "x",
    "le_falta_la_cadena": lambda c: {k: v for k, v in c.items() if k != "cadena"},
    "le_sobra_una_clave": lambda c: dict(c, otra=1),
    "la_calibracion_es_un_texto": lambda c: dict(c, calibracion="x"),
    "a_la_calibracion_le_falta_el_lote": lambda c: dict(c, calibracion={"id": ID_CAL, "fecha_irradiacion": FECHA_IRR}),
    "la_cadena_es_un_texto": lambda c: dict(c, cadena="x"),
    "la_cadena_no_trae_sus_claves": lambda c: dict(c, cadena={}),
    "la_cadena_trae_los_bits_en_texto": lambda c: dict(c, cadena=dict(c["cadena"], bits="16")),
    "la_cadena_es_nula": lambda c: dict(c, cadena=None),
    "la_curva_es_nula": lambda c: dict(c, curva=None),
    "las_bases_son_un_texto": lambda c: dict(c, bases="x"),
}
PRINCIPALES_EN_LA_VENTANA = ("le_falta_la_cadena", "la_cadena_no_trae_sus_claves", "la_calibracion_es_un_texto", "es_una_lista")          # las formas con que la ventana abria el registro mal o a medias


# ===================================================================================================== las columnas

class TestLasColumnas:
    def test_una_base_nueva_las_tiene_al_final_y_admiten_nulo(self, bd):
        info = _consulta(bd, f"PRAGMA table_info('{TABLA}')")
        nombres = [c[1] for c in info if c[1] != "activo"]          # `activo` lo agrega despues `_asegurar_activo_bloque_qc` (al final en una base nueva; antes de las de la dosis en una desplegada)
        assert tuple(nombres[-len(DE_LA_DOSIS):]) == DE_LA_DOSIS and nombres[-len(DE_LA_DOSIS) - 1] == "fecha_registro", nombres
        assert all(c[3] == 0 and c[4] is None for c in info if c[1] in DE_LA_DOSIS), "admiten NULL y no tienen valor por omision (nunca cero)"
        assert {c[1]: c[2] for c in info if c[1] in DE_LA_DOSIS} == {"estado_dosis": "TEXT", "curva": "TEXT", **{n: "REAL" for n in DE_LA_DOSIS[1:-1]}}

    def test_una_base_de_antes_las_gana_al_final_sin_tocar_sus_filas_y_dos_veces_es_igual(self, bd, tmp_path):
        """La migracion de una base ya desplegada (la tabla de D.1 tal como la dejo CD.7, con un registro): `ALTER TABLE ADD COLUMN` las agrega al final, en el orden de la lista; la fila de
        antes queda igual y con las ocho en NULL; una segunda corrida no cambia nada."""
        ddl = _consulta(bd, "SELECT sql FROM sqlite_master WHERE name = ?", (TABLA,))[0][0]
        viejo = ddl
        for n in DE_LA_DOSIS:
            viejo = viejo.replace(f" {n} {'TEXT' if n in ('estado_dosis', 'curva') else 'REAL'},", "", 1)
        assert viejo != ddl and not any(n in viejo for n in DE_LA_DOSIS)
        ruta = str(tmp_path / "antes.db")
        con = sqlite3.connect(ruta)
        con.execute("CREATE TABLE controles (id INTEGER PRIMARY KEY)")
        con.execute("INSERT INTO controles (id) VALUES (1)")
        con.execute(viejo)
        con.execute(f"INSERT INTO {TABLA} (ref, imagen, sha256, version, parametros, puntos, piso, capa, estado, fwhm_crossplane_mm, usuario, fecha_registro) "
                    "VALUES (1, x'00', 'h', 'PM-1', '{}', '[]', '{}', 'G', 'ok', 100.0, 'u', '2026-10-01 10:00:00')")
        con.commit()
        antes = con.execute(f"SELECT * FROM {TABLA}").fetchall()
        columnas_de_antes = [c[1] for c in con.execute(f"PRAGMA table_info('{TABLA}')")]
        from data.ManejoDatos.conection import Conexion
        objeto = object.__new__(Conexion)
        objeto.con = con
        Conexion.crearTablaAnalisisPlacaMensual(objeto)
        nombres = [c[1] for c in con.execute(f"PRAGMA table_info('{TABLA}')")]
        assert nombres == columnas_de_antes + list(DE_LA_DOSIS), "las ocho al FINAL, en el orden de la lista (detras de `activo`, que la base ya tenia)"
        despues = con.execute(f"SELECT * FROM {TABLA}").fetchall()
        assert [f[:len(antes[0])] for f in despues] == antes and despues[0][len(antes[0]):] == (None,) * len(DE_LA_DOSIS), "lo de antes queda en NULL, nunca en cero"
        Conexion.crearTablaAnalisisPlacaMensual(objeto)
        assert con.execute(f"SELECT * FROM {TABLA}").fetchall() == despues and [c[1] for c in con.execute(f"PRAGMA table_info('{TABLA}')")] == nombres, "idempotente"
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        con.close()

    def test_la_lista_unica_y_las_claves_del_motor_son_las_mismas(self):
        import importlib
        medidas = importlib.import_module("services.medidas_placa_mensual")
        assert tuple(m.nombre for m in medidas.COLUMNAS_DE_LA_DOSIS) == DE_LA_DOSIS
        assert tuple(m.nombre for m in medidas.MEDIDAS_GUARDADAS_EN_DOSIS) == pm().CLAVES_DE_VALORES_MEDIDOS_EN_DOSIS == DE_LA_DOSIS[:-1]
        assert all(m.admite_nulo for m in medidas.COLUMNAS_DE_LA_DOSIS)
        assert tuple(m.nombre for m in medidas.MEDIDAS_GUARDADAS) == DE_LA_NETOD, "lo que se guarda de la netOD no cambia"

    def test_valores_medidos_en_dosis_es_el_par_de_valores_medidos(self, en_dosis):
        for capa in ("R", "G", "B"):
            v = pm().valores_medidos(en_dosis.do, capa)
            assert pm().valores_medidos_en_dosis(en_dosis.do, capa) == dict(zip(DE_LA_DOSIS[:-1], (v[n] for n in DE_LA_NETOD)))
        with pytest.raises(ValueError, match="dosis"):
            pm().valores_medidos_en_dosis(en_dosis.od, "G")


# ===================================================================================================== guardar sin dosis

class TestGuardarSinDosis:
    def test_sin_curva_las_columnas_nuevas_quedan_en_null_y_la_auditoria_lo_dice(self, bd, escena):
        ref = _control(bd)
        guardar(escena, ref)
        fila = fila_cruda(bd, ref)
        assert nulas(fila) == {} and fila["estado"] == "ok"
        assert _consulta(bd, f"SELECT COUNT(*) FROM {TABLA} WHERE ref = ? AND estado_dosis IS NULL AND curva IS NULL AND fwhm_crossplane_dosis_mm IS NULL", (ref,))[0][0] == 1, "NULL, no cero"
        assert auditoria(bd, ref)[-1].endswith("; sin dosis (no hay curva de dosis)")

    def test_si_la_capa_reportada_no_cumple_la_regla_no_se_guarda_la_dosis(self, bd, escena):
        """La regla es la del boton sobre la capa REPORTADA: la verde con una curva no valida queda sin dosis aunque el rojo y el azul cumplan."""
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(con_capa(escena.curva, "G", estado="no válida: de prueba")))
        assert nulas(fila_cruda(bd, ref)) == {}
        assert auditoria(bd, ref)[-1].endswith("; sin dosis (la curva de la capa verde no es válida: no válida: de prueba)")

    def test_con_el_piso_de_las_esquinas_no_se_guarda_la_dosis_y_dice_el_motivo(self, bd, escena):
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(escena.curva), modo="automatico")
        assert nulas(fila_cruda(bd, ref)) == {}
        assert "sin dosis (el piso no es el de la película virgen" in auditoria(bd, ref)[-1]

    def test_sin_curva_vigente_la_auditoria_dice_el_motivo_entero(self, bd, escena):
        motivo = pm().curva_efectiva([], escena.curva.cadena).motivo
        ref = _control(bd)
        guardar(escena, ref, curva=pm().CurvaEfectiva(None, motivo=motivo))
        assert nulas(fila_cruda(bd, ref)) == {} and auditoria(bd, ref)[-1].endswith(f"; sin dosis ({motivo})")

    def test_una_curva_que_no_es_una_curva_efectiva_se_rechaza_sin_escribir(self, bd, escena):
        ref = _control(bd)
        with pytest.raises(svc().PlacaMensualError, match="CurvaEfectiva"):
            guardar(escena, ref, curva=escena.curva)
        assert _consulta(bd, f"SELECT COUNT(*) FROM {TABLA} WHERE ref = ?", (ref,))[0][0] == 0 and auditoria(bd, ref) == []

    def test_una_copia_con_nan_se_rechaza_sin_escribir(self, bd, escena):
        """La puerta JSON estricta de D1-PROD-03 tambien para `curva`: un numero no finito en la copia no llega a la base."""
        ref = _control(bd)
        mala = con_capa(escena.curva, "R", costo=float("nan"))
        with pytest.raises(svc().PlacaMensualError, match="curva"):
            guardar(escena, ref, curva=efectiva(mala))
        assert _consulta(bd, f"SELECT COUNT(*) FROM {TABLA} WHERE ref = ?", (ref,))[0][0] == 0 and auditoria(bd, ref) == []


# ===================================================================================================== guardar con dosis

class TestGuardarConDosis:
    def test_guarda_la_dosis_de_la_verdad_de_la_capa_reportada(self, bd, escena, en_dosis):
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(escena.curva))
        fila = fila_cruda(bd, ref)
        assert fila["estado_dosis"] == "ok"
        assert abs(fila["fwhm_crossplane_dosis_mm"] - FWHM_X) <= 0.05 and abs(fila["fwhm_inplane_dosis_mm"] - FWHM_Y) <= 0.05, "la verdad: 100 x 99 mm"
        esperado = pm().valores_medidos_en_dosis(en_dosis.do, "G")
        assert all(fila[n] is not None for n in DE_LA_DOSIS[:-1]), "medida por completo: los dos FWHM y los cuatro desfases"
        assert all(fila[n] == esperado[n] if isinstance(esperado[n], str) else math.isclose(fila[n], esperado[n], abs_tol=1e-9) for n in DE_LA_DOSIS[:-1]), (fila, esperado)
        assert fila["fwhm_crossplane_dosis_mm"] != fila["fwhm_crossplane_mm"], "la dosis no es la netOD con otro nombre"

    def test_la_netod_guardada_no_cambia_por_guardar_tambien_la_dosis(self, bd, escena):
        sin, con = _control(bd), _control(bd)
        guardar(escena, sin)
        guardar(escena, con, curva=efectiva(escena.curva))
        a, b = fila_cruda(bd, sin), fila_cruda(bd, con)
        assert {k: v for k, v in a.items() if k not in NO_SE_COMPARAN + DE_LA_DOSIS} == {k: v for k, v in b.items() if k not in NO_SE_COMPARAN + DE_LA_DOSIS}

    def test_la_copia_es_json_valido_con_la_curva_su_calibracion_la_cadena_y_las_bases(self, bd, escena, en_dosis):
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(escena.curva))
        cruda = fila_cruda(bd, ref)["curva"]
        assert _consulta(bd, f"SELECT json_valid(curva) FROM {TABLA} WHERE ref = ? AND activo = 1", (ref,))[0][0] == 1
        copia = json.loads(cruda)
        assert set(copia) == {"calibracion", "curva", "cadena", "bases"}
        assert copia["calibracion"] == {"id": ID_CAL, "lote": LOTE, "fecha_irradiacion": FECHA_IRR}
        import importlib
        assert importlib.import_module("analisisImagenes.curva_dosis").curva_desde_dict(copia["curva"]).como_dict() == json.loads(json.dumps(escena.curva.como_dict()))
        assert copia["cadena"] == en_dosis.cadena
        assert copia["bases"] == {c: {"base": "dosis", "motivo": None} for c in ("R", "G", "B", "gris")}

    def test_la_auditoria_nombra_la_curva(self, bd, escena):
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(escena.curva))
        detalle = auditoria(bd, ref)[-1]
        assert detalle.endswith(f"; en dosis con la curva del lote «{LOTE}» irradiada el {FECHA_IRR} (calibración {ID_CAL})") and "capa reportada G" in detalle
        assert sin_simbolos(detalle)

    def test_leer_devuelve_la_copia_y_los_valores(self, bd, escena):
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(escena.curva))
        registro = svc().leer(ref)
        assert isinstance(registro["curva"], dict) and registro["curva"]["calibracion"]["lote"] == LOTE and registro["estado_dosis"] == "ok"
        ref2 = _control(bd)
        guardar(escena, ref2)
        assert svc().leer(ref2)["curva"] is None and svc().leer(ref2)["estado_dosis"] is None


class TestLaCapaReportada:
    """CD6b-REV1-P1 y REV1-P2. Lo que se guarda en dosis es de la capa que el fisico REPORTA (DA-85: la verde por omision, pero puede elegir la roja o la azul), y la regla que lo permite se juzga con la
    cadena de captura de LOS BYTES. Las demas pruebas de la tarea guardan siempre la verde con una curva buena para las cuatro capas: no distinguen una capa de otra ni una cadena de otra."""

    @pytest.mark.parametrize("capa", ["R", "B"])
    def test_la_dosis_guardada_es_la_de_la_capa_reportada_aunque_la_verde_no_cumpla(self, bd, escena, en_dosis, capa):
        """Capa reportada R o B con la curva de la VERDE no valida: la regla se juzga sobre la capa reportada, asi que se guarda su dosis (los valores de ESA capa, no de la verde). Cae contra la mutacion
        que fija la capa «G» en `_la_dosis` (R3) y contra la que lee los valores de la verde (R3b)."""
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(con_capa(escena.curva, "G", estado="no válida: de prueba")), capa=capa)
        fila = fila_cruda(bd, ref)
        esperado, de_la_verde = pm().valores_medidos_en_dosis(en_dosis.do, capa), pm().valores_medidos_en_dosis(en_dosis.do, "G")
        assert fila["capa"] == capa and fila["estado_dosis"] == "ok", (fila["estado_dosis"], auditoria(bd, ref)[-1])
        assert all(math.isclose(fila[n], esperado[n], abs_tol=1e-9) for n in DE_LA_DOSIS[1:-1]), "los valores guardados son los de la capa reportada"
        assert any(not math.isclose(esperado[n], de_la_verde[n], abs_tol=1e-9) for n in DE_LA_DOSIS[1:-1]), "premisa: la capa reportada y la verde dan valores distintos, o esta prueba no las distingue"
        assert auditoria(bd, ref)[-1].endswith(f"; en dosis con la curva del lote «{LOTE}» irradiada el {FECHA_IRR} (calibración {ID_CAL})") and f"capa reportada {capa}" in auditoria(bd, ref)[-1]

    @pytest.mark.parametrize("capa", ["R", "B"])
    def test_si_la_capa_reportada_no_cumple_no_se_guarda_la_dosis_aunque_la_verde_cumpla(self, bd, escena, capa):
        """El espejo: capa reportada R o B con SU curva no valida (la verde si): sin dosis, y el motivo nombra la capa reportada. Cae contra la mutacion que fija la capa «G» (R3)."""
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(con_capa(escena.curva, capa, estado="no válida: de prueba")), capa=capa)
        assert nulas(fila_cruda(bd, ref)) == {}
        assert auditoria(bd, ref)[-1].endswith(f"; sin dosis (la curva de la capa {pel().ADJETIVO_DE_LA_CAPA[capa]} no es válida: no válida: de prueba)")

    def test_el_servicio_juzga_con_la_cadena_de_los_bytes_y_no_con_la_de_la_curva_que_le_pasan(self, bd, escena):
        """CD6b-D5 e IM3: el servicio no confia en el llamador. Una `CurvaEfectiva` cuya curva es de OTRA cadena de captura (8 bits) sobre una pelicula de 16 bits no guarda la dosis y dice por que; la ventana
        ya filtra por cadena (`curva_efectiva`), asi que por ella no se nota: es la garantia propia del servicio. Cae contra la mutacion que juzga con la cadena de la curva (R4)."""
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(dataclasses.replace(escena.curva, cadena=dict(escena.curva.cadena, bits=8))))
        assert nulas(fila_cruda(bd, ref)) == {}
        assert "; sin dosis (la película se escaneó con otra cadena de captura que la calibración" in auditoria(bd, ref)[-1]


# ===================================================================================================== reabrir con la copia

class TestReabrirConLaCopia:
    def test_recalcular_en_dosis_usa_la_copia_y_no_lee_las_calibraciones(self, bd, escena, monkeypatch):
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(escena.curva))
        import importlib

        def prohibido():
            raise AssertionError("reabrir no lee las calibraciones vigentes: la copia guardada manda (DA-81)")
        monkeypatch.setattr(importlib.import_module("services.curva_dosis"), "vigentes_validas", prohibido)
        registro = svc().leer(ref)
        resultado = svc().recalcular_en_dosis(registro)
        assert resultado.base == "dosis" and resultado.curva.como_dict() == svc().curva_guardada(registro).curva.como_dict()
        assert json.loads(json.dumps(resultado.curva.como_dict())) == json.loads(json.dumps(escena.curva.como_dict()))
        assert svc().diferencias_en_dosis(registro, resultado) == [], "reabrir dice lo mismo"
        assert svc().diferencias(registro, svc().recalcular(registro)) == [] and svc().recalcular(registro).base == "densidad óptica neta", "la netOD se recalcula como siempre"

    def test_la_curva_guardada_es_una_curva_efectiva_con_su_calibracion(self, bd, escena):
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(escena.curva))
        e = svc().curva_guardada(svc().leer(ref))
        assert isinstance(e, pm().CurvaEfectiva) and (e.id, e.lote, e.fecha_irradiacion, e.motivo) == (ID_CAL, LOTE, FECHA_IRR, None)

    def test_un_registro_sin_dosis_no_tiene_curva_ni_dosis_que_recalcular(self, bd, escena):
        ref = _control(bd)
        guardar(escena, ref)
        registro = svc().leer(ref)
        assert svc().curva_guardada(registro) is None and svc().recalcular_en_dosis(registro) is None and svc().diferencias_en_dosis(registro, None) == []

    def test_una_copia_danada_lo_dice_y_no_pasa_a_dosis(self, bd, escena):
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(escena.curva))
        copia = json.loads(fila_cruda(bd, ref)["curva"])
        copia["curva"]["modelo"] = "otro"
        _sql(bd, f"UPDATE {TABLA} SET curva = ? WHERE ref = ?", (json.dumps(copia), ref))
        registro = svc().leer(ref)
        e = svc().curva_guardada(registro)
        assert e.curva is None and e.motivo.startswith("la copia de la curva guardada con el registro no se puede leer: ") and e.lote == LOTE
        with pytest.raises(svc().PlacaMensualError, match="no se puede leer"):
            svc().recalcular_en_dosis(registro)

    def test_una_imagen_guardada_que_no_se_puede_leer_lo_dice_como_error_del_servicio(self, bd, escena):
        """`recalcular_en_dosis` no deja escapar el `ValueError` del motor o de la lectura: lo convierte en `PlacaMensualError` con su motivo, como `recalcular` (la ventana lo muestra en un cuadro).
        (01-11, pre-vuelo: la cobertura de lineas de la primera forma no corria esa rama; M25.)"""
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(escena.curva))
        registro = dict(svc().leer(ref), imagen=b"no es una imagen")
        with pytest.raises(svc().PlacaMensualError, match="formato de la imagen"):
            svc().recalcular_en_dosis(registro)

    def test_diferencias_en_dosis_ve_un_valor_guardado_distinto(self, bd, escena):
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(escena.curva))
        registro = svc().leer(ref)
        resultado = svc().recalcular_en_dosis(registro)
        registro["fwhm_inplane_dosis_mm"] += 0.01
        diferencias = svc().diferencias_en_dosis(registro, resultado)
        assert len(diferencias) == 1 and diferencias[0].startswith("fwhm_inplane_dosis_mm: guardado ")
        registro["estado_dosis"] = None
        assert svc().diferencias_en_dosis(dict(registro, curva={"x": 1}), None) == ["la dosis: guardada, recalculada sin dosis"]

    def test_diferencias_en_dosis_compara_cada_uno_de_los_siete_valores_guardados(self, bd, escena):
        """CD6b-REV1-PROD-04. Cada columna de la dosis (el estado, los dos FWHM y los cuatro desfases) que no coincide con lo recalculado se dice, con su nombre y ella sola; la prueba de arriba solo alteraba el
        FWHM inplane. Cae contra la mutacion que compara solo los tres primeros (R2)."""
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(escena.curva))
        registro = svc().leer(ref)
        resultado = svc().recalcular_en_dosis(registro)
        assert svc().diferencias_en_dosis(registro, resultado) == []
        for n in DE_LA_DOSIS[:-1]:
            alterado = dict(registro, **{n: "no medible en dosis: otro motivo" if n == "estado_dosis" else registro[n] + 0.01})
            diferencias = svc().diferencias_en_dosis(alterado, resultado)
            assert len(diferencias) == 1 and diferencias[0].startswith(f"{n}: guardado "), (n, diferencias)

    def test_recalcular_en_dosis_usa_la_cadena_guardada_y_no_la_de_los_bytes(self, bd, escena, en_dosis):
        """CD6b-REV1-PROD-03 y REV1-P3 (CD6b-D4: «la cadena guardada es la que usa `recalcular_en_dosis`: nunca se vuelve a leer de los bytes»). En todas las demas pruebas la cadena guardada es igual a la
        de los bytes y no se distinguen. Con la copia diciendo que la pelicula se escaneo a 8 bits (los bytes siguen siendo de 16 y la curva tambien), lo recalculado lo refleja: la capa queda en netOD con el
        motivo de la cadena. Cae contra la mutacion que vuelve a leer la cadena de los bytes (R1)."""
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(escena.curva))
        registro = svc().leer(ref)
        assert svc().cadena_guardada(registro) == en_dosis.cadena and svc().recalcular_en_dosis(registro).capas["G"].base == pm().BASE_DOSIS, "premisa: con la copia intacta se mide en dosis"
        registro["curva"]["cadena"] = dict(registro["curva"]["cadena"], bits=8)
        assert svc().cadena_guardada(registro)["bits"] == 8
        g = svc().recalcular_en_dosis(registro).capas["G"]
        assert g.base == pm().BASE_DENSIDAD_OPTICA and g.estado.startswith("no medible en dosis: la película se escaneó con otra cadena de captura que la calibración"), (g.base, g.estado)
        sin_dosis = _control(bd)
        guardar(escena, sin_dosis)
        assert svc().cadena_guardada(svc().leer(sin_dosis)) is None, "un registro sin dosis no tiene copia ni cadena"

    @pytest.mark.parametrize("como", sorted(COPIAS_DANADAS))
    def test_una_copia_con_otra_forma_es_una_copia_danada_que_se_dice_y_no_lanza(self, bd, escena, como):
        """CD6b-REV1-PROD-02. Una copia que es JSON valido pero no tiene la forma que escribe `guardar` (`COPIAS_DANADAS`) no lanza un AttributeError ni un KeyError: `curva_guardada` da una `CurvaEfectiva`
        SIN curva con el motivo (como la docstring promete), la cadena guardada es None y `recalcular_en_dosis` la rechaza como error del servicio. Cae contra las mutaciones que no revisan la forma (R6, R7)."""
        ref = _control(bd)
        guardar(escena, ref, curva=efectiva(escena.curva))
        registro = svc().leer(ref)
        registro["curva"] = COPIAS_DANADAS[como](copy.deepcopy(registro["curva"]))
        e = svc().curva_guardada(registro)
        assert isinstance(e, pm().CurvaEfectiva) and e.curva is None and e.motivo.startswith("la copia de la curva guardada con el registro no se puede leer: "), (como, e)
        assert svc().cadena_guardada(registro) is None
        with pytest.raises(svc().PlacaMensualError, match="no se puede leer"):
            svc().recalcular_en_dosis(registro)


class TestCuandoUnPerfilPasaElRangoUtilAlMedirEnDosis:
    """CD6b-REV1-P5, el SEGUNDO caso de CD6b-D3: la regla del boton se cumple (juzga la netOD del nivel medio de la meseta) y al medir en dosis un perfil pasa el rango util (juzga la netOD de la dosis media). Se
    guarda «no medible en dosis: ...» con la copia de la curva y SIN numeros (nunca cero); ninguna otra prueba de la tarea lo fija."""

    def test_se_guarda_no_medible_en_dosis_con_la_copia_y_los_numeros_vacios_y_reabrirlo_dice_lo_mismo(self, bd, escena, con_cupula):
        nivel, dosis = max(netod_de_la_meseta(con_cupula.od.capas["G"])), max(netod_de_la_meseta(con_cupula.do.capas["G"]))
        assert dosis - nivel > 1e-7, "premisa: la dosis media de una meseta con cupula pasa la dosis de su nivel medio (la curva es convexa)"
        limite = (nivel + dosis) / 2                       # el tope del rango util de la verde: entre las dos
        curva = con_capa(escena.curva, "G", netod_maxima=limite)
        ref = _control(bd)
        guardar(con_cupula, ref, curva=efectiva(curva))
        fila = fila_cruda(bd, ref)
        assert fila["estado"] == "ok" and fila["estado_dosis"].startswith("no medible en dosis: la meseta (netOD ") and "pasa el rango útil de la curva de la capa verde" in fila["estado_dosis"], fila["estado_dosis"]
        assert [fila[n] for n in DE_LA_DOSIS[1:-1]] == [None] * 6, "sin numeros, y NULL y no cero"
        assert fila["curva"] is not None and _consulta(bd, f"SELECT json_valid(curva) FROM {TABLA} WHERE ref = ? AND activo = 1", (ref,))[0][0] == 1, "la copia se guarda aunque no se haya medido"
        copia = json.loads(fila["curva"])
        assert copia["curva"]["capas"]["G"]["netod_maxima"] == limite and copia["calibracion"] == {"id": ID_CAL, "lote": LOTE, "fecha_irradiacion": FECHA_IRR}
        assert copia["bases"]["G"]["base"] == pm().BASE_DENSIDAD_OPTICA and "pasa el rango útil" in copia["bases"]["G"]["motivo"] and copia["bases"]["R"]["base"] == pm().BASE_DOSIS
        assert auditoria(bd, ref)[-1].endswith(f"; en dosis con la curva del lote «{LOTE}» irradiada el {FECHA_IRR} (calibración {ID_CAL})")
        registro = svc().leer(ref)
        resultado = svc().recalcular_en_dosis(registro)
        assert resultado.capas["G"].estado == fila["estado_dosis"] and svc().diferencias_en_dosis(registro, resultado) == [], "reabrirlo dice lo mismo"


# ===================================================================================================== la ventana

def _guardada(v, bd):
    return fila_cruda(bd, v.ref)


class TestLaVentana:
    def test_el_boton_no_cambia_lo_que_se_guarda(self, fabrica, mundo, escena, dialogos, bd):
        """Guardar con el boton apagado y con el boton pulsado da la MISMA fila (DC16): todas las columnas salvo el id, el control y la hora."""
        filas = []
        for pulsado in (False, True):
            v = fabrica(usuario=Usuario())
            assert v.cargar_imagen(escena.placa.datos, "placa_dosis.tif")
            for x, y in escena.clics:
                clic(v, x, y)
            if pulsado:
                pulsar(v)
                assert v.boton_dosis.isChecked() and v._resultado_en_dosis is not None
            v.boton_guardar.click()
            assert v.estado == "registro"
            filas.append({k: x for k, x in _guardada(v, bd).items() if k not in NO_SE_COMPARAN})
        assert filas[0]["estado_dosis"] == "ok" and filas[0]["curva"] is not None
        assert filas[0] == filas[1]

    def test_guardar_pasa_la_curva_que_juzga_el_boton(self, abierta, monkeypatch):
        v = abierta
        vistos = {}
        original = svc().guardar

        def espia(*a, **k):
            vistos.update(k)
            return original(*a, **k)
        monkeypatch.setattr(svc(), "guardar", espia)
        v.boton_guardar.click()
        assert vistos["curva"] is not None and vistos["curva"].lote == LOTE and vistos["curva"].curva is not None

    def test_sin_curva_vigente_se_guarda_sin_dosis_y_el_registro_queda_gris(self, fabrica, mundo, escena, dialogos, bd):
        mundo.calibraciones = []
        v = fabrica(usuario=Usuario())
        assert v.cargar_imagen(escena.placa.datos, "placa_dosis.tif")
        for x, y in escena.clics:
            clic(v, x, y)
        v.boton_guardar.click()
        assert nulas(_guardada(v, bd)) == {}
        assert not v.boton_dosis.isEnabled() and v.linea_dosis.text() == REGISTRO

    def test_guardar_desde_la_dosis_dice_lo_que_se_guarda_y_deja_el_registro_con_la_copia(self, abierta, bd):
        v = abierta
        pulsar(v)
        filas = [[v.tabla_perfiles.item(i, j).text() if v.tabla_perfiles.item(i, j) else "" for j in range(v.tabla_perfiles.columnCount())] for i in range(v.tabla_perfiles.rowCount())]
        assert [f[-1] for f in filas if f[0] == "Capa verde"][0] == "se guarda (en densidad óptica neta y en dosis)"
        v.boton_guardar.click()
        assert v.estado == "registro" and not v.boton_dosis.isChecked() and v.boton_dosis.isEnabled(), "un registro se ve en netOD y, con la copia, el boton puede pasar a dosis"
        assert _guardada(v, bd)["estado_dosis"] == "ok" and v._resultado_en_dosis is None
        assert f"«{LOTE}»" in v.linea_dosis.text()

    def test_un_registro_abre_en_netod_y_pasa_a_dosis_con_la_copia_aunque_haya_otra_vigente(self, abierta, fabrica, mundo, escena):
        v = abierta
        v.boton_guardar.click()
        mundo.calibraciones = [calibracion(escena.otra, id_=8, lote="L-otra")]
        lecturas = mundo.lecturas
        otra = fabrica(ref=v.ref, usuario=Usuario())
        otra.refrescar()                                  # lo que hace la ventana al mostrarse (`showEvent`): vuelve a buscar la curva vigente... salvo con un registro
        assert otra.estado == "registro" and not otra.boton_dosis.isChecked() and otra.boton_dosis.isEnabled()
        assert f"«{LOTE}»" in otra.linea_dosis.text() and "L-otra" not in otra.linea_dosis.text()
        pulsar(otra)
        assert otra.boton_dosis.isChecked() and otra._resultado_en_dosis is not None
        assert json.loads(json.dumps(otra._resultado_en_dosis.curva.como_dict())) == json.loads(json.dumps(escena.curva.como_dict())), "la COPIA, nunca la vigente"
        assert abs(otra._resultado_en_dosis.capas["G"].crossplane.fwhm_mm - FWHM_X) <= 0.05
        assert mundo.lecturas == lecturas, "un registro nunca busca la curva vigente (DA-81)"
        assert "no coincide" not in otra.etiqueta_registro.text()

    def test_anular_la_calibracion_no_cambia_lo_que_muestra_el_registro(self, abierta, fabrica, mundo, bd):
        v = abierta
        v.boton_guardar.click()
        guardado = _guardada(v, bd)
        mundo.calibraciones = []                          # la calibracion se anulo: ya no esta entre las vigentes
        otra = fabrica(ref=v.ref, usuario=Usuario())
        otra.refrescar()                                  # al mostrarse
        assert otra.boton_dosis.isEnabled()
        pulsar(otra)
        assert pm().valores_medidos_en_dosis(otra._resultado_en_dosis, "G") == {n: guardado[n] for n in DE_LA_DOSIS[:-1]}

    def test_un_registro_en_dosis_se_mide_con_sus_parametros_guardados_y_no_con_los_de_la_ventana(self, abierta, fabrica, bd):
        """En un registro, «Ver en dosis» mide LO GUARDADO (sus parametros, sus puntos, su piso, su copia y su cadena: `svc.recalcular_en_dosis`), no lo que la ventana usaria hoy para un analisis
        nuevo (los parametros de fabrica). Un registro guardado con otra penumbra alta (que no cambia nada de lo guardado en netOD) lo distingue. (01-11, pre-vuelo: M23 sobrevivia sin este caso.)"""
        v = abierta
        v.boton_guardar.click()
        P = json.loads(_guardada(v, bd)["parametros"])
        assert P["penumbra_alta"] == 0.8
        P["penumbra_alta"] = 0.7
        _sql(bd, f"UPDATE {TABLA} SET parametros = ? WHERE ref = ? AND activo = 1", (json.dumps(P, sort_keys=True), v.ref))
        otra = fabrica(ref=v.ref, usuario=Usuario())
        assert otra.estado == "registro" and "no coincide" not in otra.etiqueta_registro.text()
        pulsar(otra)
        assert otra._resultado_en_dosis.parametros["penumbra_alta"] == 0.7, "lo guardado manda, no los parametros de fabrica de la ventana"
        assert otra._resultado_en_dosis.parametros["base_de_la_medida"] == pm().BASE_DOSIS

    def test_tras_recalcular_un_registro_vuelve_la_curva_vigente(self, abierta, fabrica, mundo, escena):
        v = abierta
        v.boton_guardar.click()
        mundo.calibraciones = [calibracion(escena.otra, id_=8, lote="L-otra")]
        otra = fabrica(ref=v.ref, usuario=Usuario())
        lecturas = mundo.lecturas
        puntos = [tuple(m["clic"]) for m in otra._registro["puntos"]]
        otra.boton_recalcular.click()
        for x, y in puntos:
            clic(otra, x, y)
        assert otra.estado == "analizada" and otra._efectiva.lote == "L-otra" and mundo.lecturas > lecturas, "un analisis nuevo usa la curva vigente, no la copia del registro"

    def test_un_registro_con_la_copia_danada_queda_gris_con_el_motivo(self, abierta, fabrica, bd):
        v = abierta
        v.boton_guardar.click()
        copia = json.loads(_guardada(v, bd)["curva"])
        copia["curva"]["modelo"] = "otro"
        _sql(bd, f"UPDATE {TABLA} SET curva = ? WHERE ref = ?", (json.dumps(copia), v.ref))
        otra = fabrica(ref=v.ref, usuario=Usuario())
        assert otra.estado == "registro" and not otra.boton_dosis.isEnabled() and "no se puede leer" in otra.boton_dosis.toolTip()

    def test_lo_guardado_en_dosis_que_no_coincide_se_dice_en_la_linea_del_registro(self, abierta, fabrica, bd, dialogos):
        v = abierta
        v.boton_guardar.click()
        _sql(bd, f"UPDATE {TABLA} SET fwhm_crossplane_dosis_mm = fwhm_crossplane_dosis_mm + 1 WHERE ref = ?", (v.ref,))
        otra = fabrica(ref=v.ref, usuario=Usuario())
        pulsar(otra)
        texto = otra.etiqueta_registro.text()
        assert "En dosis, lo recalculado no coincide con lo guardado:" in texto and "fwhm_crossplane_dosis_mm" in texto

    def test_la_linea_del_registro_dice_cada_uno_de_los_siete_valores_que_no_coinciden(self, abierta, fabrica, bd, dialogos):
        """CD6b-REV1-PROD-04. La prueba de arriba altera solo el FWHM crossplane: la ventana tiene que decir TODOS los que no coinciden. Cae contra la mutacion que compara solo los tres primeros (R2)."""
        v = abierta
        v.boton_guardar.click()
        _sql(bd, f"UPDATE {TABLA} SET estado_dosis = 'no medible en dosis: otro motivo', " + ", ".join(f"{n} = {n} + 1" for n in DE_LA_DOSIS[1:-1]) + " WHERE ref = ?", (v.ref,))
        otra = fabrica(ref=v.ref, usuario=Usuario())
        pulsar(otra)
        texto = otra.etiqueta_registro.text()
        assert "En dosis, lo recalculado no coincide con lo guardado:" in texto and all(f"{n}: guardado " in texto for n in DE_LA_DOSIS[:-1]), texto

    def test_un_registro_con_otra_cadena_guardada_queda_gris_por_la_cadena(self, abierta, fabrica, bd, dialogos):
        """CD6b-REV1-PROD-03 y REV1-P3 en la ventana (CD6b-D4). Al abrir un registro la ventana juzga el boton con la cadena GUARDADA, no con la de los bytes (que sigue siendo la de la curva): con la copia
        diciendo 8 bits, el boton queda gris y dice la cadena. Cae contra la mutacion que toma la cadena de los bytes al abrir (R5)."""
        v = abierta
        v.boton_guardar.click()
        copia = json.loads(_guardada(v, bd)["curva"])
        copia["cadena"]["bits"] = 8
        _sql(bd, f"UPDATE {TABLA} SET curva = ? WHERE ref = ?", (json.dumps(copia), v.ref))
        otra = fabrica(ref=v.ref, usuario=Usuario())
        assert otra.estado == "registro" and not otra.boton_dosis.isEnabled() and "otra cadena de captura que la calibración" in otra.boton_dosis.toolTip(), otra.boton_dosis.toolTip()[-300:]

    def test_un_registro_cuya_copia_no_tiene_la_forma_abre_en_netod_con_el_boton_gris_y_el_motivo(self, abierta, fabrica, bd, dialogos):
        """CD6b-REV1-PROD-01 y REV1-P4. Una copia que es JSON valido pero no tiene la forma que escribe `guardar` (sin la clave «cadena», con la cadena sin sus claves, con la calibracion en texto, una lista)
        no revienta con un KeyError o un AttributeError («Error inesperado») ni deja la ventana a medias: el registro se abre en netOD, con el boton gris y el motivo de la copia, y sin ningun cuadro.
        Cae contra la mutacion que vuelve a leer la clave «cadena» a mano en la ventana (R5b)."""
        v = abierta
        v.boton_guardar.click()
        ref, nombre = v.ref, v._nombre
        copia = json.loads(_guardada(v, bd)["curva"])
        for como in PRINCIPALES_EN_LA_VENTANA:
            _sql(bd, f"UPDATE {TABLA} SET curva = ? WHERE ref = ? AND activo = 1", (json.dumps(COPIAS_DANADAS[como](copy.deepcopy(copia))), ref))
            dialogos.llamadas.clear()
            otra = fabrica(ref=ref, usuario=Usuario())
            assert otra.estado == "registro" and otra._registro is not None and otra._resultado is not None and otra._nombre == nombre, como
            assert not otra.boton_dosis.isEnabled() and "la copia de la curva guardada con el registro no se puede leer: " in otra.boton_dosis.toolTip(), como
            assert not dialogos.llamadas and otra.etiqueta_registro.text().startswith("Análisis guardado: "), (como, dialogos.orden())
            cerrar(otra)

    def test_abrir_un_registro_con_la_copia_sin_la_cadena_en_una_ventana_ocupada_la_deja_en_el_registro(self, abierta, fabrica, bd, dialogos):
        """El escenario de la revision: la ventana tiene un analisis de la sesion (otra imagen, cinco puntos) y se abre el registro cuya copia no trae la clave «cadena». Se abre el registro entero (su imagen, su
        nombre, sus puntos, su resultado), no una mezcla del registro con lo de la sesion."""
        v = abierta
        v.boton_guardar.click()
        ref = v.ref
        copia = json.loads(_guardada(v, bd)["curva"])
        del copia["cadena"]
        _sql(bd, f"UPDATE {TABLA} SET curva = ? WHERE ref = ? AND activo = 1", (json.dumps(copia), ref))
        otra = fabrica(usuario=Usuario())
        assert otra.cargar_imagen(v._bytes, "placa_de_la_sesion.tif")
        for x, y in [m["clic"] for m in v._registro["puntos"]]:
            clic(otra, x, y)
        assert otra.estado == "analizada" and otra._nombre == "placa_de_la_sesion.tif"
        otra.ref = ref
        dialogos.llamadas.clear()
        assert otra.abrir_guardado() is True
        assert otra.estado == "registro" and otra._registro is not None and otra._resultado is not None and otra._nombre == v._registro["nombre_archivo"] and not otra.boton_guardar.isEnabled()
        assert not otra.boton_dosis.isEnabled() and "no se puede leer" in otra.boton_dosis.toolTip() and not dialogos.llamadas


# ===================================================================================================== estructura

class TestEstructura:
    def test_el_servicio_no_lee_las_calibraciones_ni_agrega_sql(self):
        fuente = (RAIZ / "services" / "placa_mensual.py").read_text(encoding="utf-8")
        arbol = ast.parse(fuente)
        importados = {a.name for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) for a in n.names} | {n.module for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)}
        assert "curva_dosis" not in importados - {"analisisImagenes.curva_dosis"} and "services.curva_dosis" not in importados and "vigentes_validas" not in fuente
        assert fuente.count("cursor.execute(") == 2, "la curva llega como argumento: ninguna lectura nueva de la base"
        assert "Qt" not in {n.split(".")[0] for n in importados if n}

    def test_el_motor_no_lee_la_base_ni_usa_qt(self):
        fuente = (RAIZ / "analisisImagenes" / "placa_mensual.py").read_text(encoding="utf-8")
        assert "sqlite3" not in fuente and "PyQt5" not in fuente

    def test_los_textos_nuevos_sin_simbolos(self):
        for texto in (svc().TEXTO_DE_LA_CURVA_EN_LA_AUDITORIA, svc().TEXTO_SIN_DOSIS_EN_LA_AUDITORIA, dibujo_mod().texto_se_guarda("G", "G", None, en_dosis=True),
                      ventana_mod().AYUDA_VER_EN_DOSIS):
            assert sin_simbolos(texto), texto
        assert "también su dosis" in ventana_mod().AYUDA_VER_EN_DOSIS, "la ayuda del boton no dice que se guarda solo la netOD"
