"""UM.6a (PLAN_CALCULADORA_UM_05-11.md, DC15, DC16): el lector del JSON de un plan, `services/um_plan_json.py`.

Lo que fija:
  - el plan de ejemplo (`EJEMPLO_DE_PLAN`, el texto que mostrará «Ver formato») da con las tablas reales del 600C los cinco estados de `logs/h_datos_reales.txt` (Dentro, Revisar, Fuera, sin
    calcular por falta del factor de 30° y sin calcular por VMAT), con los archivos directos y con las tablas guardadas por el servicio de UM.3 en una base TEMPORAL;
  - la CONVERGENCIA (corolario 3 del plan): para los diez casos reales de la parte manual, el JSON da la MISMA `Entrada` que el formulario y por eso el mismo resultado, el mismo desglose y el
    mismo texto para copiar; cambiar los umbrales cambia estados y no UM;
  - cada clave, con cada uno de sus nombres, llega al motor; lo que no se entiende no se ignora (claves desconocidas, dos nombres, lados y mandíbulas a la vez, un solo lado equivalente, la cuña
    sin su ángulo, con decimales o sin tipo físico ni orientación, tipos equivocados, NaN, infinitos, enteros enormes, `null`, el 0 escrito); la orientación nunca se inventa (UM2-D18);
  - el ARCHIVO: tamaño (se mira antes de leer), UTF-8 con y sin BOM, UTF-16 y binario rechazados, vacío, que no existe, una carpeta, la raíz que no es un objeto, sin campos, demasiados
    campos, anidamiento profundo, claves repetidas en cualquier nivel; todos los motivos en español y acotados;
  - un campo malo no tumba a los demás, tampoco un defecto propio ni un fallo al traer las tablas de un haz; los datos de cada haz se piden una vez por plan;
  - la PRIVACIDAD: ningún motivo cita el nombre del plan, el de un campo ni el del paciente; el módulo no importa Qt, sqlite3 ni la base, y no escribe nada;
  - el tiempo con 200 y con 1000 campos, y el tope de campos; `build_exe.py` lista el módulo una vez, después de la puerta de las tablas, y sigue en CRLF.
Sin Qt (salvo la capa pura de la pantalla manual, importada en las pruebas de convergencia). Nunca una base de BasesDeDatos/."""
import ast
import json
import os
import re
import shutil
import sqlite3
import time

import pytest

import services.um_plan_json as pj          # primero: sin UM.6a la colección cae por `ModuleNotFoundError: No module named 'services.um_plan_json'`
import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services import um_armar, um_datos_haz
from services import um_lector_eclipse as lector
from services import um_motor as motor

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "tests", "datos_um", "600C")
EQUIPO, ENERGIA = "Clinac 600", "6 MV"
B = {"dosis_cgy": 100, "x_cm": 10, "y_cm": 10, "ssd_cm": 100, "profundidad_cm": 10}
FISICA = {"cuna_tipo": "fisica", "cuna_orientacion": "IN"}
SIMBOLOS = re.compile("[✓✔✕✖✗✘⚠❌❎✅☑☒]")                                   # DA-18
INGLES = re.compile(r"Expecting|line \d|column|char \d|delimiter|Exceeds|digits|recursion|Unterminated|Invalid|Extra data")


def plan(*campos, **del_plan):
    return json.dumps({"equipo": "600C", "energia": "6X", **del_plan, "campos": list(campos)})


def un_campo(**extra):
    """El campo B con lo de `extra` (un valor None quita la clave)."""
    campo = {k: v for k, v in {**B, **extra}.items() if v is not None}
    return pj.leer_plan(plan(campo))[1][0]


def motivo_de(**extra):
    c = un_campo(**extra)
    assert c.entrada is None, c
    return c.problema


@pytest.fixture(scope="module")
def originales():
    return [(nombre, open(os.path.join(DATOS, nombre), "rb").read()) for nombre in sorted(os.listdir(DATOS))]


@pytest.fixture(scope="module")
def datos(originales):
    """Los datos del haz del 600C, 6 MV, armados con los archivos reales (D'0 = 1 cGy/UM en dmax)."""
    return um_armar.datos_haz([lector.decodificar(b) for _, b in originales], EQUIPO, ENERGIA, 1.0, None)


def de_600(datos):
    return lambda equipo, energia: datos if (equipo, energia) == (EQUIPO, ENERGIA) else None


# ================================================================================================================================== el plan de ejemplo

FILAS_DEL_EJEMPLO = [   # logs/h_datos_reales.txt (05-11) y logs/UM2/h_datos_reales_UM2.txt (UM.2 comiteada): (nombre, UM, error, estado, avisos) o (nombre, motivo)
    ("AP abierto, isocéntrico", "110.7", "-0.26", "Dentro", 0),
    ("PA con láminas", "116.5", "+2.18", "Revisar", 1),
    ("Lateral con cuña de 15", "91.2", "+3.63", "Fuera", 1),
    ("Lateral con cuña de 30, sin factor conocido", "Falta el factor de la cuña de 30° en 10 × 10: escríbalo a mano"),
    ("Arco VMAT", "La técnica «VMAT» no se reconoce como un campo estático: la ecuación 3 de la TG-71 no cubre IMRT ni VMAT, y este campo no se calcula"),
]


def _como_filas(salida):
    filas = []
    for campo, resultado, motivo in salida:
        if resultado is None:
            filas.append((campo.nombre, motivo))
        else:
            filas.append((campo.nombre, f"{resultado.um:.1f}", f"{resultado.error_pct:+.2f}", resultado.estado, len(resultado.avisos)))
    return filas


def test_el_plan_de_ejemplo_da_los_cinco_estados_con_las_tablas_reales(datos):
    nombre, campos = pj.leer_plan(pj.EJEMPLO_DE_PLAN)
    assert nombre == "Ejemplo de prueba (datos inventados, no es un paciente)"
    assert [(c.equipo, c.energia) for c in campos] == [(EQUIPO, ENERGIA)] * 5
    salida = pj.calcular_plan(campos, de_600(datos))
    assert _como_filas(salida) == FILAS_DEL_EJEMPLO
    assert [c.problema for c in campos] == [None, None, None, None, FILAS_DEL_EJEMPLO[4][1]]      # el de 30° se lee bien: lo que falta es su factor, y lo dice el motor
    laminas = salida[1][1]
    assert dict((f.simbolo, f.valor) for f in laminas.factores)["Sc(rc)/Sc(lectura)"] > 1          # el de láminas usa la corrección de Sc


def test_el_ejemplo_es_json_valido_y_sus_claves_son_las_del_formato():
    datos = json.loads(pj.EJEMPLO_DE_PLAN)
    usadas = set(datos) | {k for campo in datos["campos"] for k in campo}
    assert usadas <= pj.CONOCIDAS_DEL_PLAN | pj.CONOCIDAS_DEL_CAMPO
    assert all(k == pj.NOMBRES[c][0] for c, nombres in pj.NOMBRES.items() for k in usadas if k in nombres), "el ejemplo usa el primer nombre de cada concepto"


def _abrir_con_la_app(ruta):
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = None
        try:
            Conexion().con.close()
        finally:
            Conexion._instance = previo


def _sql(ruta, sql, parametros=()):
    con = sqlite3.connect(ruta)
    try:
        filas = con.execute(sql, parametros).fetchall()
        con.commit()
        return filas
    finally:
        con.close()


@pytest.fixture(scope="module")
def plantilla(originales, tmp_path_factory):
    """Una base TEMPORAL nueva, con las tablas reales del 600C, 6 MV, guardadas por el servicio de UM.3 (D'0 = 1 cGy/UM en dmax)."""
    ruta = str(tmp_path_factory.mktemp("um6") / "cargada.db")
    _abrir_con_la_app(ruta)
    _sql(ruta, "INSERT INTO users (user, password, fullname, active, idreal, role, rol_sistema) VALUES ('jefa', 'x', 'Jefa de Física', 1, 901, 'Físico Médico', 'jefe')")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = object.__new__(Conexion)
        try:
            ok, motivo, _ = um_datos_haz.guardar(equipo=EQUIPO, energia=ENERGIA, archivos=originales, d0_dmax=1.0, d0_tabla=None, d0_origen="Eclipse: 1 [cGy/UM] en dmax",
                                                 wf_escritos=None, curva_sc=None, sc_origen=None, observaciones=None, usuario="jefa")
        finally:
            Conexion._instance = previo
    assert ok, motivo
    return ruta


def test_con_las_tablas_guardadas_por_el_servicio_da_lo_mismo_que_con_los_archivos(plantilla, datos, monkeypatch, tmp_path):
    copia = str(tmp_path / "copia.db")
    shutil.copy(plantilla, copia)
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: copia)
    monkeypatch.setattr(Conexion, "_instance", object.__new__(Conexion))
    pedidos = []

    def de_la_base(equipo, energia):
        pedidos.append((equipo, energia))
        return um_datos_haz.datos_del_haz(equipo, energia)
    _, campos = pj.leer_plan(pj.EJEMPLO_DE_PLAN)
    salida = pj.calcular_plan(campos, de_la_base)
    assert _como_filas(salida) == FILAS_DEL_EJEMPLO
    assert [r for _, r, _ in salida] == [r for _, r, _ in pj.calcular_plan(campos, de_600(datos))]      # Resultado por Resultado: los mismos números, factores y avisos
    assert pedidos == [(EQUIPO, ENERGIA)]                                                                # una vez por haz (el VMAT no llega a pedir)
    _, otro = pj.leer_plan(plan(B, {**B, "equipo": "iX"}))
    assert [m for _, _, m in pj.calcular_plan(otro, de_la_base)] == [None, "No hay tablas cargadas del Clinac iX, 6 MV: sin ellas este campo no se calcula"]


# ================================================================================================================================== la convergencia con la parte manual

# Los diez casos reales de la parte manual (tests/test_um4_pantalla_manual.py, CASOS_REALES; D = 200 [cGy]): (lo escrito en el formulario, cuña, UM del log) y su campo en el JSON.
CASOS_REALES = [
    ({"x": "10", "y": "10", "ssd": "100", "prof": "10"}, None, "302.1"),
    ({"x": "10", "y": "10", "ssd": "90", "prof": "10"}, None, "252.8"),
    ({"x": "10", "y": "15", "ssd": "92", "prof": "8"}, None, "228.4"),
    ({"x": "15", "y": "15", "x_ef": "10", "y_ef": "10", "ssd": "90", "prof": "10"}, None, "250.5"),
    ({"x": "20", "y": "20", "ssd": "90", "prof": "10", "punto_x": "5"}, None, "224.9"),
    ({"x": "20", "y": "20", "ssd": "90", "prof": "10", "punto_x": "8"}, None, "223.3"),
    ({"x": "10", "y": "10", "ssd": "90", "prof": "15", "prof_ef": "8"}, None, "256.3"),
    ({"x": "10", "y": "10", "ssd": "90", "prof": "10"}, 15, "326.8"),
    ({"x": "15", "y": "15", "ssd": "90", "prof": "10"}, 15, "306.7"),
    ({"x": "5", "y": "5", "ssd": "90", "prof": "10"}, None, "279.6"),
]
DEL_FORMULARIO_AL_JSON = {"x": "x_cm", "y": "y_cm", "ssd": "ssd_cm", "prof": "profundidad_cm", "x_ef": "x_equivalente_cm", "y_ef": "y_equivalente_cm", "punto_x": "punto_x_cm",
                          "prof_ef": "profundidad_efectiva_cm"}


def _el_mismo_campo_en_json(valores, cuna):
    campo = {"nombre": "caso", "dosis_cgy": 200}
    campo.update({DEL_FORMULARIO_AL_JSON[k]: float(v) for k, v in valores.items()})
    if cuna:
        campo.update(cuna_grados=cuna, **FISICA)
    return campo


@pytest.fixture(scope="module")
def manual():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import ui.paginasGuia.calculadora_um as pantalla      # su capa pura (sin crear widgets)
    return pantalla


@pytest.mark.parametrize("valores, cuna, um_del_log", CASOS_REALES, ids=[c[2] for c in CASOS_REALES])
def test_manual_y_json_dan_el_mismo_numero_en_el_mismo_campo(manual, datos, valores, cuna, um_del_log):
    """La misma `Entrada` y la misma función de cálculo: igualdad EXACTA (no dentro de una tolerancia), y los textos del desglose iguales."""
    del_formulario = manual.entrada_desde_textos(dict({"dosis": "200", "tf": "1.000"}, **valores), cuna, "IN" if cuna else None)
    campo = pj.leer_plan(plan(_el_mismo_campo_en_json(valores, cuna)))[1][0]
    assert campo.problema is None and campo.entrada == del_formulario
    (_, resultado, motivo), = pj.calcular_plan([campo], de_600(datos))
    directo = motor.calcular(datos, del_formulario)
    assert motivo is None and resultado == directo and resultado.um == directo.um
    assert manual.texto_de_las_um(resultado) == f"UM calculadas: {um_del_log} [UM]"
    assert manual.filas_del_desglose(resultado) == manual.filas_del_desglose(directo)
    assert manual.texto_para_copiar(resultado) == manual.texto_para_copiar(directo)


def test_cambiar_los_umbrales_cambia_estados_y_no_um(datos):
    campos = pj.leer_plan(plan({**B, "um_planeador": 150.0}))[1]
    salidas = [pj.calcular_plan(campos, de_600(datos), d, f)[0][1] for d, f in ((2.0, 3.0), (0.1, 0.2), (0.1, 2.0), (1.0, 1.0))]
    assert len({r.um for r in salidas}) == 1 and len({r.error_pct for r in salidas}) == 1
    assert 0.5 < salidas[0].error_pct < 1.0
    assert [r.estado for r in salidas] == ["Dentro", "Fuera", "Revisar", "Dentro"]
    assert [r.estado for r in salidas] == [motor.estado_de(salidas[0].error_pct, d, f) for d, f in ((2.0, 3.0), (0.1, 0.2), (0.1, 2.0), (1.0, 1.0))]


def test_umbrales_que_no_sirven_dejan_cada_campo_con_el_motivo_del_motor(datos):
    salida = pj.calcular_plan(pj.leer_plan(plan(B, B))[1], de_600(datos), 3.0, 2.0)
    assert [r for _, r, _ in salida] == [None, None] and all(m.startswith("Las tolerancias deben ser números mayores que 0") for _, _, m in salida)


# ================================================================================================================================== cada clave llega al motor

def _con(concepto, nombre, valor, **extra):
    """El campo B con `valor` bajo el nombre `nombre` del concepto (sin el nombre base de ese concepto, si B lo trae)."""
    campo = {k: v for k, v in B.items() if k not in pj.NOMBRES[concepto]}
    campo[nombre] = valor
    campo.update(extra)
    return campo


# (concepto, valor, extra, lo que debe salir: f(CampoImportado) -> valor)
CLAVES = [
    ("dosis", 123.5, {}, lambda c: c.entrada.dosis, 123.5),
    ("um_planeador", 150, {}, lambda c: c.entrada.um_planeador, 150.0),
    ("x", 12, {}, lambda c: c.entrada.x, 12.0),
    ("y", 14, {}, lambda c: c.entrada.y, 14.0),
    ("mandibulas", {"x1": 6, "x2": 8, "y1": 9, "y2": 7}, {"x_cm": None, "y_cm": None}, lambda c: (c.entrada.x, c.entrada.y, c.entrada.centro_x, c.entrada.centro_y), (14.0, 16.0, 1.0, -1.0)),
    ("x_ef", 8, {"y_equivalente_cm": 9}, lambda c: (c.entrada.x_ef, c.entrada.y_ef), (8.0, 9.0)),
    ("y_ef", 9, {"x_equivalente_cm": 8}, lambda c: (c.entrada.x_ef, c.entrada.y_ef), (8.0, 9.0)),
    ("lado_ef", 9, {}, lambda c: (c.entrada.x_ef, c.entrada.y_ef), (9.0, 9.0)),
    ("ssd", 95, {}, lambda c: c.entrada.ssd, 95.0),
    ("prof", 8, {}, lambda c: c.entrada.prof, 8.0),
    ("prof_ef", 7.5, {}, lambda c: c.entrada.prof_ef, 7.5),
    ("punto_x", 1.5, {}, lambda c: (c.entrada.punto_x, c.entrada.punto_y), (1.5, 0.0)),
    ("punto_y", -2, {}, lambda c: (c.entrada.punto_x, c.entrada.punto_y), (0.0, -2.0)),
    ("oar", 1.01, {}, lambda c: c.entrada.oar_manual, 1.01),
    ("cuna", 15, FISICA, lambda c: (c.entrada.cuna, c.entrada.cuna_orientacion, c.entrada.wf_manual), (15, "IN", None)),
    ("cuna_tipo", "hard", {"cuna_grados": 15, "cuna_orientacion": "IN"}, lambda c: c.entrada.cuna, 15),
    ("cuna_orientacion", "out", {"cuna_grados": 15, "cuna_tipo": "fisica"}, lambda c: c.entrada.cuna_orientacion, "OUT"),
    ("wf", 0.8, {"cuna_grados": 30}, lambda c: (c.entrada.cuna, c.entrada.wf_manual, c.entrada.cuna_orientacion), (30, 0.8, None)),
    ("tf", 0.97, {}, lambda c: c.entrada.tf, 0.97),
    ("nombre", "A", {}, lambda c: c.nombre, "A"),
    ("equipo", "iX", {}, lambda c: c.equipo, "Clinac iX"),
    ("energia", "15X", {}, lambda c: c.energia, "15 MV"),
    ("tecnica", "3D CRT", {}, lambda c: c.problema, None),
]
# El formato, escrito a mano (DC15): cada nombre que el lector acepta, y nada más. Quitar o agregar un nombre en `NOMBRES` es cambiar el formato, y esta lista lo hace visible.
NOMBRES_DEL_FORMATO = {
    "nombre": ("nombre", "campo", "field_name", "beam_name"), "equipo": ("equipo", "maquina", "machine", "treatment_machine"), "energia": ("energia", "energy"),
    "tecnica": ("tecnica", "technique"), "dosis": ("dosis_cgy", "dosis_campo_cgy", "dose_cgy"), "um_planeador": ("um_planeador", "um_eclipse", "mu_eclipse", "planned_mu"),
    "x": ("x_cm",), "y": ("y_cm",), "mandibulas": ("mandibulas_cm", "jaws_cm"), "x_ef": ("x_equivalente_cm",), "y_ef": ("y_equivalente_cm",),
    "lado_ef": ("lado_equivalente_cm", "equivalent_square_cm"), "ssd": ("ssd_cm",), "prof": ("profundidad_cm", "depth_cm"), "prof_ef": ("profundidad_efectiva_cm", "effective_depth_cm"),
    "punto_x": ("punto_x_cm",), "punto_y": ("punto_y_cm",), "oar": ("oar",), "cuna": ("cuna_grados", "wedge_deg"), "cuna_tipo": ("cuna_tipo", "wedge_type"),
    "cuna_orientacion": ("cuna_orientacion", "wedge_orientation"), "wf": ("factor_cuna", "wedge_factor"), "tf": ("factor_bandeja", "tray_factor"),
}
POR_NOMBRE = [(concepto, nombre, valor, extra, leer, esperado) for concepto, valor, extra, leer, esperado in CLAVES for nombre in NOMBRES_DEL_FORMATO[concepto]]


def test_los_nombres_del_formato_son_exactamente_los_que_acepta_el_lector():
    assert pj.NOMBRES == NOMBRES_DEL_FORMATO
    assert pj.IGNORADOS == {"id", "comentario", "gantry_grados", "colimador_grados", "camilla_grados"}
    assert pj.CLAVES_DEL_PLAN == {"plan", "paciente", "fecha", "formato", "version", "campos"}
    assert pj.TIPOS_DE_CUNA_FISICA == {"FISICA", "PHYSICAL", "HARD", "STANDARD"}


def test_la_tabla_de_claves_cubre_cada_concepto_y_cada_nombre():
    assert sorted(c[0] for c in CLAVES) == sorted(NOMBRES_DEL_FORMATO)
    assert sorted(n for _, n, *_ in POR_NOMBRE) == sorted(n for nombres in NOMBRES_DEL_FORMATO.values() for n in nombres)


@pytest.mark.parametrize("concepto, nombre, valor, extra, leer, esperado", POR_NOMBRE, ids=[f"{c[0]}-{c[1]}" for c in POR_NOMBRE])
def test_cada_clave_con_cada_uno_de_sus_nombres_llega_al_motor(concepto, nombre, valor, extra, leer, esperado):
    campo = {k: v for k, v in _con(concepto, nombre, valor, **extra).items() if v is not None}
    c = pj.leer_plan(plan(campo))[1][0]
    assert leer(c) == esperado, c


def test_el_campo_minimo_y_lo_que_vale_si_el_plan_no_lo_dice():
    e = un_campo().entrada
    assert e == motor.Entrada(dosis=100.0, x=10.0, y=10.0, ssd=100.0, prof=10.0, centro_x=0.0, centro_y=0.0, punto_x=0.0, punto_y=0.0, tf=1.0)
    assert (e.x_ef, e.y_ef, e.prof_ef, e.oar_manual, e.cuna, e.cuna_orientacion, e.wf_manual, e.um_planeador) == (None,) * 8
    assert all(type(v) is float for v in (e.dosis, e.x, e.y, e.ssd, e.prof, e.centro_x, e.centro_y, e.punto_x, e.punto_y, e.tf))    # UM2-D18: número, nunca None


def test_un_null_vale_como_no_dicho_y_un_texto_vacio_tambien():
    assert un_campo(oar=None).entrada.oar_manual is None
    c = pj.leer_plan(plan({**B, "oar": None, "punto_x_cm": None, "factor_bandeja": None, "cuna_grados": None, "cuna_tipo": "", "cuna_orientacion": "  ", "nombre": " "}))[1][0]
    assert c.entrada == un_campo().entrada and c.nombre == "Campo 1"
    assert motivo_de(ssd_cm=None) == "Falta la SSD"
    c = pj.leer_plan(plan({**B, "ssd_cm": None}))[1][0]                      # `null` en un obligatorio: falta
    assert c.problema == "Falta la SSD"


@pytest.mark.parametrize("clave, valor, motivo", [
    ("factor_bandeja", 0, "El factor de bandeja no es un valor posible (de 0.5 a 1.05): 0.0"),
    ("oar", 0, "El OAR no es un valor posible (de 0.7 a 1.2): 0.0"),
    ("um_planeador", 0, "Las UM de Eclipse no son un valor posible (mayor que 0 y hasta 20000 [UM]): 0.0"),
    ("profundidad_efectiva_cm", 0, "La profundidad efectiva no es un valor posible (mayor que 0 y hasta 100 [cm]): 0.0"),
    ("dosis_cgy", 0, "La dosis no es un valor posible (mayor que 0 y hasta 5000 [cGy]): 0.0"),
])
def test_un_cero_escrito_es_cero_y_lo_juzga_el_motor(datos, clave, valor, motivo):
    """Un 0 en un opcional no cae en el valor por omisión: llega al motor, que lo rechaza con su rango."""
    c = un_campo(**{clave: valor})
    assert c.problema is None and getattr(c.entrada, {"factor_bandeja": "tf", "oar": "oar_manual", "um_planeador": "um_planeador", "profundidad_efectiva_cm": "prof_ef",
                                                      "dosis_cgy": "dosis"}[clave]) == 0.0
    assert pj.calcular_plan([c], de_600(datos))[0][2] == motivo


def test_el_punto_en_cero_es_el_eje_y_se_calcula_igual_que_sin_decirlo(datos):
    con_cero = pj.calcular_plan([un_campo(punto_x_cm=0, punto_y_cm=0)], de_600(datos))[0][1]
    assert con_cero == pj.calcular_plan([un_campo()], de_600(datos))[0][1]


# ================================================================================================================================== lo que no se entiende no se ignora

@pytest.mark.parametrize("clave, valor", [("wedge", 15), ("bandeja", 0.95), ("profundidad_efectiva", 6), ("beam_type", "VMAT"), ("mu_planeador", 150), ("x_efectivo_cm", 5),
                                          ("off_axis", 3), ("distancia_eje_cm", 3), ("Dosis_cgy", 100), ("ssd", 100), ("paciente", "x")])
def test_una_clave_desconocida_deja_el_campo_sin_calcular_y_la_nombra(clave, valor):
    assert motivo_de(**{clave: valor}) == f"Trae claves que este lector no conoce: «{clave}»"


def test_las_claves_desconocidas_se_nombran_de_a_cinco_y_acortadas():
    campo = {**B, **{f"clave_{i:04d}": 1 for i in range(10000)}, "x" * 100000: 1}
    t0 = time.perf_counter()
    c = pj.leer_plan(plan(campo))[1][0]
    assert time.perf_counter() - t0 < 2.0
    assert c.problema == "Trae claves que este lector no conoce: «clave_0000», «clave_0001», «clave_0002», «clave_0003», «clave_0004» y 9996 más"
    assert pj.leer_plan(plan({**B, "x" * 100000: 1}))[1][0].problema == "Trae claves que este lector no conoce: «xxxxxxxxxxxx…xxxxxxxx»"


def test_las_claves_que_se_sabe_que_no_usa_se_ignoran():
    assert un_campo(gantry_grados=90, colimador_grados=0, camilla_grados=0, comentario="x", id=3).entrada == un_campo().entrada


def test_una_clave_desconocida_en_el_plan_rechaza_el_archivo_y_las_conocidas_no():
    with pytest.raises(pj.PlanInvalido, match="^El plan trae claves que este lector no conoce: «wedge»\\.$"):
        pj.leer_plan(plan(B, wedge=15))
    assert pj.leer_plan(plan(B, plan="P", paciente={"lo que sea": [1]}, fecha="y", formato="z", version=1))[0] == "P"


@pytest.mark.parametrize("extra, motivo", [
    (dict(dose_cgy=200), "Trae dos nombres para lo mismo: «dose_cgy», «dosis_cgy»"),
    (dict(mandibulas_cm={"x1": 5, "x2": 5, "y1": 5, "y2": 5}), "Trae a la vez las mandíbulas y los lados X e Y"),
    (dict(lado_equivalente_cm=8, x_equivalente_cm=8), "Trae a la vez un lado equivalente y los lados X e Y equivalentes"),
    (dict(x_equivalente_cm=8), "Trae un solo lado equivalente: faltan X o Y"),
    (dict(y_equivalente_cm=8), "Trae un solo lado equivalente: faltan X o Y"),
    (dict(cuna_grados=15.7, **FISICA), "El ángulo de la cuña debe ser un número entero de grados, mayor que 0, y es 15.7"),
    (dict(cuna_grados=-15, **FISICA), "El ángulo de la cuña debe ser un número entero de grados, mayor que 0, y es -15"),
    (dict(cuna_grados=15), "Una cuña sin su factor escrito («factor_cuna») debe ser física: el tipo de cuña («cuna_tipo») debe decir «fisica». Una cuña dinámica no tiene tablas y necesita su factor"),
    (dict(cuna_grados=15, cuna_tipo="SOFT", cuna_orientacion="IN"), "Una cuña sin su factor escrito («factor_cuna») debe ser física: el tipo de cuña («cuna_tipo») debe decir «fisica», y dice «SOFT». Una cuña dinámica no tiene tablas y necesita su factor"),
    (dict(cuna_grados=15, cuna_tipo="fisica"), "La orientación de la cuña (falta) debe ser IN, OUT, LEFT o RIGHT"),
    (dict(cuna_grados=15, cuna_tipo="fisica", cuna_orientacion="DIAGONAL"), "La orientación de la cuña («DIAGONAL» no es una de las cuatro) debe ser IN, OUT, LEFT o RIGHT"),
    (dict(tecnica="VMAT"), "La técnica «VMAT» no se reconoce como un campo estático: la ecuación 3 de la TG-71 no cubre IMRT ni VMAT, y este campo no se calcula"),
])
def test_lo_contradictorio_o_raro_no_se_adivina(extra, motivo):
    assert motivo_de(**extra) == motivo


@pytest.mark.parametrize("tipo", ["DINÁMICA", "Enhanced Dynamic Wedge", "EDW30", "EDW", "virtual", "soft"])
def test_un_tipo_que_no_es_fisico_sin_factor_no_se_calcula(tipo):
    assert "debe decir «fisica»" in motivo_de(cuna_grados=15, cuna_tipo=tipo, cuna_orientacion="IN")


@pytest.mark.parametrize("tipo", ["fisica", "física", "FISICA", "Physical", "standard", "hard", " Física "])
def test_tipos_de_cuna_fisica(tipo):
    assert un_campo(cuna_grados=15, cuna_tipo=tipo, cuna_orientacion="IN").entrada.cuna == 15


@pytest.mark.parametrize("orientacion, leida", [("IN", "IN"), ("out", "OUT"), ("Left", "LEFT"), (" right ", "RIGHT")])
def test_las_cuatro_orientaciones_llegan_tal_cual(orientacion, leida):
    assert un_campo(cuna_grados=15, cuna_tipo="fisica", cuna_orientacion=orientacion).entrada.cuna_orientacion == leida


@pytest.mark.parametrize("extra", [dict(cuna_tipo="fisica"), dict(cuna_orientacion="LEFT"), dict(factor_cuna=0.7), dict(cuna_tipo="fisica", cuna_orientacion="LEFT"),
                                   dict(cuna_grados=0, cuna_tipo="fisica"), dict(cuna_grados=0, factor_cuna=0.7), dict(cuna_grados=0.0, cuna_orientacion="IN"),
                                   dict(cuna_grados=None, cuna_orientacion="IN")])
def test_datos_de_cuna_sin_su_angulo_no_son_un_campo_abierto(extra):
    """Daba WF = 1 en silencio: −22.6 % con una de 15°."""
    assert motivo_de(**extra) == "Trae datos de cuña sin su ángulo («cuna_grados»): un campo así no se calcula como abierto"


def test_sin_cuna_la_orientacion_no_se_inventa():
    """UM2-D18: el lector nunca escribe «IN». Sin cuña (sin decirla o con 0) la orientación queda en None, como en la parte manual."""
    for c in (un_campo(), un_campo(cuna_grados=0), un_campo(cuna_grados=0.0)):
        assert (c.entrada.cuna, c.entrada.cuna_orientacion, c.entrada.wf_manual) == (None, None, None)


@pytest.mark.parametrize("orientacion", [None, "IN", "Y1-IN", "DIAGONAL"])
def test_con_factor_escrito_el_tipo_y_la_orientacion_no_pesan_y_la_orientacion_no_se_pasa(datos, orientacion):
    """Era un rechazo falso: una cuña dinámica con su factor y un rótulo de Eclipse como «Y1-IN». El motor no usa la orientación con el factor escrito: no se pasa."""
    c = un_campo(cuna_grados=30, cuna_tipo="EDW", factor_cuna=0.8, cuna_orientacion=orientacion)
    assert (c.entrada.cuna, c.entrada.wf_manual, c.entrada.cuna_orientacion) == (30, 0.8, None)
    resultado = pj.calcular_plan([c], de_600(datos))[0][1]
    assert dict((f.simbolo, (f.valor, f.origen)) for f in resultado.factores)["WF"] == (0.8, "manual")


def test_con_cuna_de_tablas_la_orientacion_del_plan_es_la_que_cuenta(datos):
    """IN y LEFT dan números distintos (el gradiente va a lo largo de Y o de X): la del plan llega al motor."""
    um = {o: pj.calcular_plan([un_campo(x_cm=8, y_cm=12, cuna_grados=15, cuna_tipo="fisica", cuna_orientacion=o)], de_600(datos))[0][1].um for o in ("IN", "OUT", "LEFT", "RIGHT")}
    assert um["IN"] == um["OUT"] and um["LEFT"] == um["RIGHT"] and um["IN"] != um["LEFT"]
    assert not any("No se dio la orientación" in a for a in pj.calcular_plan([un_campo(cuna_grados=15, **FISICA)], de_600(datos))[0][1].avisos)


def test_una_cuna_de_15_con_decimales_cero_es_15():
    assert un_campo(cuna_grados=15.0, **FISICA).entrada.cuna == 15 and type(un_campo(cuna_grados=15.0, **FISICA).entrada.cuna) is int


@pytest.mark.parametrize("valor, es", [("cien", "el texto «cien»"), (True, "un valor verdadero o falso"), (False, "un valor verdadero o falso"), ([100], "una lista"), ({"v": 100}, "un objeto"),
                                       ("100", "el texto «100»"), ("x" * 200, "el texto «xxxxxxxxxxxx…xxxxxxxx»")])
def test_lo_que_no_es_un_numero_se_dice_y_no_se_convierte(valor, es):
    assert motivo_de(dosis_cgy=valor) == f"La dosis del campo debe ser un número y es {es}"
    assert motivo_de(oar=valor) == f"El OAR debe ser un número y es {es}"
    assert motivo_de(x_cm=None, y_cm=None, mandibulas_cm={"x1": valor, "x2": 5, "y1": 5, "y2": 5}) == f"La mandíbula x1 debe ser un número y es {es}"


@pytest.mark.parametrize("clave, que", [("equipo", "El equipo"), ("energia", "La energía"), ("tecnica", "La técnica"), ("nombre", "El nombre del campo"), ("cuna_tipo", "El tipo de cuña"),
                                        ("cuna_orientacion", "La orientación de la cuña")])
@pytest.mark.parametrize("valor, es", [(600, "un número"), (["600C"], "una lista"), (True, "un valor verdadero o falso")])
def test_lo_que_no_es_un_texto_se_dice_y_no_se_convierte(clave, que, valor, es):
    """`str(["600C"])` pasaría por «Clinac 600» si se convirtiera: no se convierte."""
    extra = {"cuna_grados": 15, **FISICA} if clave.startswith("cuna") else {}
    assert motivo_de(**{**extra, clave: valor}) == f"{que} debe ser un texto y es {es}"


def test_enteros_enormes_e_infinitos_no_tumban_el_plan():
    plano = '{"equipo":"600C","energia":"6X","campos":[{"dosis_cgy":%s,"x_cm":10,"y_cm":10,"ssd_cm":100,"profundidad_cm":10},{"dosis_cgy":100,"x_cm":10,"y_cm":10,"ssd_cm":100,"profundidad_cm":10}]}'
    for valor in ("9" * 400, "1e999", "-1e999"):
        _, c = pj.leer_plan(plano % valor)
        assert (c[0].entrada, c[0].problema, c[1].problema) == (None, "La dosis del campo es un número demasiado grande", None)
    with pytest.raises(pj.PlanInvalido, match="^El archivo no es un plan: debe ser un objeto JSON con la lista «campos»\\. Trae un número de demasiadas cifras\\.$"):
        pj.leer_plan(plano % ("9" * 5000))


@pytest.mark.parametrize("constante", ["NaN", "Infinity", "-Infinity"])
def test_nan_e_infinity_literales_rechazan_el_archivo(constante):
    with pytest.raises(pj.PlanInvalido, match=f"^El archivo trae el valor {constante}, que no es un número: un plan solo lleva números finitos\\.$"):
        pj.leer_plan('{"equipo": "600C", "energia": "6X", "campos": [{"dosis_cgy": %s}]}' % constante)


@pytest.mark.parametrize("texto, clave", [('{"equipo": "600C", "energia": "6X", "campos": [{"dosis_cgy": 1, "dosis_cgy": 2}]}', "dosis_cgy"),
                                          ('{"equipo": "600C", "equipo": "600C", "energia": "6X", "campos": [{}]}', "equipo"),
                                          ('{"campos": [{"mandibulas_cm": {"x1": 1, "x1": 2, "x2": 1, "y1": 1, "y2": 1}}]}', "x1")])
def test_una_clave_repetida_en_cualquier_objeto_rechaza_el_archivo(texto, clave):
    with pytest.raises(pj.PlanInvalido, match=f"^El archivo repite la clave «{clave}» dentro de un mismo objeto: no se sabe cuál vale\\.$"):
        pj.leer_plan(texto)


def test_muchas_claves_en_un_objeto_no_cuelgan_el_lector():
    """Con `claves.count(k)` por cada clave (la referencia) un objeto de 20000 claves tardaba un tiempo cuadrático."""
    campo = {**B, **{f"k{i}": i for i in range(20000)}}
    t0 = time.perf_counter()
    pj.leer_plan(plan(campo))
    assert time.perf_counter() - t0 < 1.0
    texto = '{"campos": [{' + ", ".join(f'"k{i}": 1' for i in range(3)) + ', "k1": 2, "k2": 3}]}'
    with pytest.raises(pj.PlanInvalido, match="^El archivo repite las claves «k1», «k2» dentro"):
        pj.leer_plan(texto)


@pytest.mark.parametrize("del_plan, motivo", [
    (dict(machine="iX"), "Trae dos nombres para lo mismo: «equipo», «machine» (en el plan, fuera de «campos»)."),
    (dict(equipo=600), "El equipo del plan debe ser un texto y es un número (en el plan, fuera de «campos»)."),
    (dict(energia=["6X"]), "La energía del plan debe ser un texto y es una lista (en el plan, fuera de «campos»)."),
    (dict(tecnica=3), "La técnica del plan debe ser un texto y es un número (en el plan, fuera de «campos»)."),
    (dict(plan=7), "El nombre del plan («plan») debe ser un texto y es un número."),
])
def test_lo_que_el_plan_dice_para_todos_sus_campos_tambien_se_exige(del_plan, motivo):
    with pytest.raises(pj.PlanInvalido) as fallo:
        pj.leer_plan(plan(B, **del_plan))
    assert str(fallo.value) == motivo


# ================================================================================================================================== equipo, energía y técnica

@pytest.mark.parametrize("tecnica", ["", "STATIC", "static", "Estático", "Estática", "3D", "3D CRT", "3D-CRT", "3D_CRT", "3DCRT", "Conformal", "Conformada", "conformado"])
def test_lo_que_si_es_un_campo_estatico_se_calcula(tecnica):
    assert un_campo(tecnica=tecnica).problema is None


@pytest.mark.parametrize("tecnica", ["VMAT", "IMRT", "DYNAMIC", "Sliding window", "Field-in-field", "ARC", "Rapidarc", "estatico dinamico"])
def test_lo_que_no_es_un_campo_estatico_no_se_calcula(tecnica):
    assert "no se reconoce como un campo estático" in motivo_de(tecnica=tecnica)


def test_la_tecnica_del_plan_se_hereda_y_la_del_campo_manda():
    _, c = pj.leer_plan(plan(B, {**B, "tecnica": "static"}, tecnica="VMAT"))
    assert "«VMAT»" in c[0].problema and c[1].problema is None


def test_equipo_y_energia_por_campo_mandan_sobre_los_del_plan_y_un_plan_con_dos_equipos_vale(datos):
    _, c = pj.leer_plan(plan(B, {**B, "equipo": "iX", "energia": "15X"}, {**B, "maquina": "Clinac iX"}))
    assert [(x.equipo, x.energia, x.problema) for x in c] == [(EQUIPO, ENERGIA, None), ("Clinac iX", "15 MV", None), ("Clinac iX", "6 MV", None)]
    pedidos = []
    salida = pj.calcular_plan(c, lambda e, f: pedidos.append((e, f)) or (datos if e == EQUIPO else None))
    assert pedidos == [(EQUIPO, ENERGIA), ("Clinac iX", "15 MV"), ("Clinac iX", "6 MV")]
    assert [m for _, _, m in salida] == [None, "No hay tablas cargadas del Clinac iX, 15 MV: sin ellas este campo no se calcula",
                                         "No hay tablas cargadas del Clinac iX, 6 MV: sin ellas este campo no se calcula"]


@pytest.mark.parametrize("del_plan, del_campo, motivo", [
    ({"equipo": "Halcyon"}, {}, "El equipo «Halcyon» no es uno de esta calculadora: el Clinac 600 o el Clinac iX"),
    ({"equipo": "Clinac 2600"}, {}, "El equipo «Clinac 2600» no es uno de esta calculadora: el Clinac 600 o el Clinac iX"),
    ({}, {"equipo": "Synergy 600"}, "El equipo «Synergy 600» no es uno de esta calculadora: el Clinac 600 o el Clinac iX"),
    ({"energia": "6"}, {}, "La energía «6» no se reconoce: debe ser de fotones en MV, como 6X o 6 MV"),
    ({"energia": "6 MeV"}, {}, "La energía «6 MeV» no se reconoce: debe ser de fotones en MV, como 6X o 6 MV"),
    ({}, {"energia": "6XFFF"}, "La energía «6XFFF» no se reconoce: debe ser de fotones en MV, como 6X o 6 MV"),
])
def test_equipo_o_energia_que_no_son_de_la_calculadora_quedan_sin_calcular_con_lo_que_dicen(del_plan, del_campo, motivo):
    c = pj.leer_plan(json.dumps({"equipo": "600C", "energia": "6X", **del_plan, "campos": [{**B, **del_campo}]}))[1][0]
    assert (c.entrada, c.problema) == (None, motivo)


def test_sin_equipo_o_sin_energia_se_dice_cual_falta():
    assert pj.leer_plan(json.dumps({"energia": "6X", "campos": [B]}))[1][0].problema == "Falta el equipo: ni el campo ni el plan lo dicen"
    c = pj.leer_plan(json.dumps({"equipo": "600C", "campos": [B]}))[1][0]
    assert (c.equipo, c.energia, c.problema) == (EQUIPO, None, "Falta la energía: ni el campo ni el plan la dicen")


def test_el_motivo_de_un_campo_dice_primero_la_clave_desconocida():
    """Una clave mal escrita explica lo que falta: «dose» desconocida antes que «falta la dosis»."""
    assert motivo_de(dosis_cgy=None, dose=100) == "Trae claves que este lector no conoce: «dose»"


# ================================================================================================================================== mandíbulas y campo

def test_mandibulas_asimetricas_dan_los_lados_y_el_centro(datos):
    c = un_campo(x_cm=None, y_cm=None, mandibulas_cm={"x1": 1.0, "x2": 9.0, "y1": 7.0, "y2": 3.0})
    assert (c.entrada.x, c.entrada.y, c.entrada.centro_x, c.entrada.centro_y) == (10.0, 10.0, 4.0, -2.0)
    assert "a 1.0 [cm] del borde" in " ".join(pj.calcular_plan([c], de_600(datos))[0][1].avisos)


@pytest.mark.parametrize("mandibulas", [{"x1": 0, "x2": 10, "y1": 5, "y2": 5}, {"x1": -1, "x2": 11, "y1": 5, "y2": 5}, {"x1": -3, "x2": 7, "y1": 5, "y2": 5}])
def test_medio_haz_o_eje_tapado_no_dan_numero(datos, mandibulas):
    motivo = pj.calcular_plan([un_campo(x_cm=None, y_cm=None, mandibulas_cm=mandibulas)], de_600(datos))[0][2]
    assert motivo.startswith("El punto queda en el borde o fuera del campo de las mandíbulas")


@pytest.mark.parametrize("mandibulas, motivo", [
    ({"x1": -5, "x2": 5, "y1": -5, "y2": 5}, "Las mandíbulas no dejan un campo abierto: x1, x2, y1 e y2 van desde el eje, positivos hacia el lado abierto"),
    ({"x1": 5, "x2": 5, "y1": -5, "y2": 5}, "Las mandíbulas no dejan un campo abierto: x1, x2, y1 e y2 van desde el eje, positivos hacia el lado abierto"),
    ({"x1": 5, "x2": 5, "y1": 5}, "Las mandíbulas deben traer exactamente x1, x2, y1 e y2"),
    ({"x1": 5, "x2": 5, "y1": 5, "y2": 5, "x3": 1}, "Las mandíbulas deben traer exactamente x1, x2, y1 e y2"),
    ([5, 5, 5, 5], "Las mandíbulas deben traer exactamente x1, x2, y1 e y2"),
    ("abierto", "Las mandíbulas deben traer exactamente x1, x2, y1 e y2"),
])
def test_mandibulas_que_no_cuadran_se_rechazan(mandibulas, motivo):
    assert motivo_de(x_cm=None, y_cm=None, mandibulas_cm=mandibulas) == motivo


@pytest.mark.parametrize("extra, motivo", [(dict(x_cm=-5), "El lado X debe ser un número mayor que cero"), (dict(dosis_cgy=-5), "La dosis no es un valor posible"),
                                           (dict(punto_x_cm=50), "El punto queda en el borde o fuera del campo"), (dict(ssd_cm=200), "La SSD no es un valor posible"),
                                           (dict(cuna_grados=10**20, **FISICA), "No hay datos de la cuña de 100000000000000000000°")])
def test_una_entrada_imposible_queda_con_el_motivo_del_motor(datos, extra, motivo):
    c = un_campo(**extra)
    assert c.problema is None
    (_, resultado, dicho), = pj.calcular_plan([c], de_600(datos))
    assert resultado is None and dicho.startswith(motivo)


# ================================================================================================================================== un campo malo no tumba a los demás

def test_un_campo_malo_no_tumba_a_los_demas(datos):
    _, campos = pj.leer_plan(plan(
        {"nombre": "bueno", **B},
        {"nombre": "sin SSD", **{k: v for k, v in B.items() if k != "ssd_cm"}},
        {"nombre": "texto", **B, "dosis_cgy": "cien"},
        "esto no es un campo",
        None,
        [1, 2],
        {"nombre": "otro bueno", **B, "um_planeador": 300}))
    assert [(c.nombre, c.problema) for c in campos] == [
        ("bueno", None), ("sin SSD", "Falta la SSD"), ("texto", "La dosis del campo debe ser un número y es el texto «cien»"),
        ("Campo 4", "No es un objeto con los datos de un campo: es el texto «esto no es un campo»"), ("Campo 5", "No es un objeto con los datos de un campo: es nulo"),
        ("Campo 6", "No es un objeto con los datos de un campo: es una lista"), ("otro bueno", None)]
    salida = pj.calcular_plan(campos, de_600(datos))
    assert [r is not None for _, r, _ in salida] == [True, False, False, False, False, False, True]
    assert [m for _, _, m in salida][1:6] == [c.problema for c in campos[1:6]]


def test_un_defecto_propio_tampoco_tumba_a_los_demas(datos):
    _, campos = pj.leer_plan(plan(B, {**B, "equipo": "iX"}, B))
    salida = pj.calcular_plan(campos, lambda e, f: object() if e == "Clinac iX" else datos)       # el iX trae algo que no son datos de un haz
    assert [r is not None for _, r, _ in salida] == [True, False, True]
    assert salida[1][2].startswith("El cálculo falló por un error inesperado (AttributeError: ") and salida[1][2].endswith(". Avise a quien mantiene la app.")


def test_un_fallo_al_traer_las_tablas_queda_en_los_campos_de_ese_haz(datos):
    _, campos = pj.leer_plan(plan(B, {**B, "equipo": "iX"}, {**B, "equipo": "iX"}, B))

    def datos_de(equipo, energia):
        if equipo == "Clinac iX":
            raise motor.FaltaDato("Las tablas guardadas de Clinac iX, 6 MV no se pueden usar: el archivo «a» guardado no coincide con su huella")
        return datos
    salida = pj.calcular_plan(campos, datos_de)
    assert [m for _, _, m in salida] == [None, "Las tablas guardadas de Clinac iX, 6 MV no se pueden usar: el archivo «a» guardado no coincide con su huella"] * 1 + \
        ["Las tablas guardadas de Clinac iX, 6 MV no se pueden usar: el archivo «a» guardado no coincide con su huella", None]
    raro = pj.calcular_plan(campos, lambda e, f: 1 / 0)
    assert all(m == "El cálculo falló por un error inesperado (ZeroDivisionError: division by zero). Avise a quien mantiene la app." for _, _, m in raro)


def test_los_datos_de_cada_haz_se_piden_una_vez_por_plan(datos):
    _, campos = pj.leer_plan(plan(*([B] * 50), {**B, "energia": "15X"}, B))
    pedidos = []
    pj.calcular_plan(campos, lambda e, f: pedidos.append((e, f)) or datos)
    assert pedidos == [(EQUIPO, ENERGIA), (EQUIPO, "15 MV")]


def test_un_campo_sin_calcular_no_pide_tablas():
    pedidos = []
    salida = pj.calcular_plan(pj.leer_plan(plan({**B, "tecnica": "VMAT"}))[1], lambda e, f: pedidos.append(e))
    assert pedidos == [] and "VMAT" in salida[0][2]


# ================================================================================================================================== el archivo

def _escribir(tmp_path, contenido, nombre="plan.json"):
    ruta = tmp_path / nombre
    ruta.write_bytes(contenido)
    return str(ruta)


def test_utf8_con_y_sin_bom_se_lee_igual(tmp_path):
    crudo = pj.EJEMPLO_DE_PLAN.encode("utf-8")
    sin = pj.leer_plan(pj.leer_archivo(_escribir(tmp_path, crudo, "a.json")))
    con = pj.leer_plan(pj.leer_archivo(_escribir(tmp_path, b"\xef\xbb\xbf" + crudo, "b.json")))
    assert sin == con == pj.leer_plan(pj.EJEMPLO_DE_PLAN) and sin[1][0].nombre == "AP abierto, isocéntrico"


@pytest.mark.parametrize("codificacion", ["utf-16", "utf-16-le", "utf-16-be", "utf-32"])
def test_utf16_y_utf32_se_rechazan_con_su_motivo(tmp_path, codificacion):
    with pytest.raises(pj.PlanInvalido, match="^El archivo no está en UTF-8: parece UTF-16 o un archivo binario\\. Guárdelo como UTF-8\\.$"):
        pj.leer_archivo(_escribir(tmp_path, pj.EJEMPLO_DE_PLAN.encode(codificacion)))


def test_un_byte_que_no_es_utf8_se_rechaza_y_dice_cual(tmp_path):
    crudo = pj.EJEMPLO_DE_PLAN.encode("latin-1")
    primero = crudo.index("é".encode("latin-1")) + 1
    with pytest.raises(pj.PlanInvalido, match=f"^El archivo no está en UTF-8: el byte {primero} no se entiende\\. Guárdelo como UTF-8\\.$"):
        pj.leer_archivo(_escribir(tmp_path, crudo))


def test_un_archivo_binario_se_rechaza(tmp_path):
    with pytest.raises(pj.PlanInvalido, match="parece UTF-16 o un archivo binario"):
        pj.leer_archivo(_escribir(tmp_path, bytes(range(256))))


def test_un_archivo_demasiado_grande_no_se_lee(tmp_path, monkeypatch):
    ruta = _escribir(tmp_path, b" " * (pj.TAMANO_MAXIMO_BYTES + 1))
    abiertos = []
    monkeypatch.setattr("builtins.open", lambda *a, **k: abiertos.append(a) or (_ for _ in ()).throw(AssertionError("se abrió el archivo")))
    with pytest.raises(pj.PlanInvalido, match="^El archivo mide 2.000001 \\[MB\\]: un plan no pasa de 2 \\[MB\\], y uno así no se lee\\.$"):
        pj.leer_archivo(ruta)
    assert abiertos == []                                        # se mira su tamaño ANTES de leerlo


def test_un_archivo_justo_en_el_tope_si_se_lee_y_un_texto_de_mas_no(tmp_path):
    relleno = pj.EJEMPLO_DE_PLAN.encode("utf-8")
    justo = relleno + b" " * (pj.TAMANO_MAXIMO_BYTES - len(relleno))
    assert len(pj.leer_plan(pj.leer_archivo(_escribir(tmp_path, justo)))[1]) == 5
    with pytest.raises(pj.PlanInvalido, match="^El archivo mide más de 2 \\[MB\\]: un plan no pasa de eso, y uno así no se lee\\.$"):
        pj.texto_del_archivo(justo + b" ")


def test_500_megas_no_se_leen_ni_agotan_la_memoria(tmp_path):
    ruta = tmp_path / "enorme.json"
    with open(ruta, "wb") as f:
        f.truncate(500 * 1024 ** 2)                               # disperso: no ocupa disco
    t0 = time.perf_counter()
    with pytest.raises(pj.PlanInvalido, match="^El archivo mide 500.0 \\[MB\\]"):
        pj.leer_archivo(str(ruta))
    assert time.perf_counter() - t0 < 0.5


@pytest.mark.parametrize("contenido", [b"", b"   \n\t ", b"\xef\xbb\xbf", b"\xef\xbb\xbf  \r\n"])
def test_un_archivo_vacio_se_dice_vacio(tmp_path, contenido):
    with pytest.raises(pj.PlanInvalido, match="^El archivo está vacío\\.$"):
        pj.leer_plan(pj.leer_archivo(_escribir(tmp_path, contenido)))


def test_un_archivo_que_no_existe_o_una_carpeta_se_dicen(tmp_path):
    with pytest.raises(pj.PlanInvalido, match="^No se pudo leer el archivo: no existe\\.$"):
        pj.leer_archivo(str(tmp_path / "no_esta.json"))
    with pytest.raises(pj.PlanInvalido, match="^No se pudo leer el archivo: es una carpeta\\.$"):
        pj.leer_archivo(str(tmp_path))


def test_un_archivo_sin_permiso_se_dice(tmp_path, monkeypatch):
    ruta = _escribir(tmp_path, pj.EJEMPLO_DE_PLAN.encode("utf-8"))

    def negado(*a, **k):
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr("builtins.open", negado)
    with pytest.raises(pj.PlanInvalido, match="^No se pudo leer el archivo: no hay permiso para leerlo\\.$"):
        pj.leer_archivo(ruta)


@pytest.mark.parametrize("texto, motivo", [
    ("no es json", "El archivo no es un plan: debe ser un objeto JSON con la lista «campos». No es un JSON válido: falla en la línea 1, columna 1."),
    ('{"campos": [\n  {"dosis_cgy": 1,}\n]}', "El archivo no es un plan: debe ser un objeto JSON con la lista «campos». No es un JSON válido: falla en la línea 2, columna 19."),
    ('{"campos": [{}]} y algo más', "El archivo no es un plan: debe ser un objeto JSON con la lista «campos». No es un JSON válido: falla en la línea 1, columna 18."),
    ("[]", "El archivo no es un plan: debe ser un objeto JSON con la lista «campos»."),
    ('[{"campos": []}]', "El archivo no es un plan: debe ser un objeto JSON con la lista «campos»."),
    ('"un texto"', "El archivo no es un plan: debe ser un objeto JSON con la lista «campos»."),
    ("{}", "El archivo no es un plan: debe ser un objeto JSON con la lista «campos»."),
    ('{"campos": "x"}', "La clave «campos» del plan debe ser una lista, con un objeto por campo, y es el texto «x»."),
    ('{"campos": {}}', "La clave «campos» del plan debe ser una lista, con un objeto por campo, y es un objeto."),
    ('{"campos": []}', "El plan no trae ningún campo: la lista «campos» está vacía."),
    ('{"campos": null}', "La clave «campos» del plan debe ser una lista, con un objeto por campo, y es nulo."),
])
def test_un_archivo_que_no_es_un_plan_se_rechaza_entero_con_su_motivo(texto, motivo):
    with pytest.raises(pj.PlanInvalido) as fallo:
        pj.leer_plan(texto)
    assert str(fallo.value) == motivo


def test_el_anidamiento_profundo_se_rechaza_sin_romper(tmp_path):
    for profundo in ('{"campos": [' + "[" * 100000 + "]" * 100000 + "]}", '{"campos": [' + '{"a": ' * 100000 + "1" + "}" * 100000 + "]}"):
        with pytest.raises(pj.PlanInvalido, match="^El archivo no es un plan: debe ser un objeto JSON con la lista «campos»\\. Anida demasiadas listas u objetos, uno dentro de otro\\.$"):
            pj.leer_plan(pj.leer_archivo(_escribir(tmp_path, profundo.encode())))


def test_el_tope_de_campos(datos):
    uno_mas = plan(*([B] * (pj.MAXIMO_DE_CAMPOS + 1)))
    with pytest.raises(pj.PlanInvalido, match=f"^El plan trae {pj.MAXIMO_DE_CAMPOS + 1} campos: esta calculadora lee hasta {pj.MAXIMO_DE_CAMPOS} por archivo\\.$"):
        pj.leer_plan(uno_mas)
    assert len(pj.leer_plan(plan(*([B] * pj.MAXIMO_DE_CAMPOS)))[1]) == pj.MAXIMO_DE_CAMPOS


@pytest.mark.parametrize("n", [200, 1000])
def test_leer_y_calcular_muchos_campos_tarda_poco(datos, n):
    """H14, sin hilo: medido en el pre-vuelo, 200 campos en unos 20 [ms] y 1000 en unos 100 [ms] (leer y calcular). El tope aquí es holgado (una máquina cargada)."""
    ejemplo = json.loads(pj.EJEMPLO_DE_PLAN)
    texto = json.dumps({**ejemplo, "campos": (ejemplo["campos"] * n)[:n]})
    t0 = time.perf_counter()
    salida = pj.calcular_plan(pj.leer_plan(texto)[1], de_600(datos))
    assert time.perf_counter() - t0 < 3.0 and len(salida) == n
    assert [s[1].estado if s[1] else None for s in salida[:10]] == ["Dentro", "Revisar", "Fuera", None, None] * 2


# ================================================================================================================================== los motivos y la privacidad

PRIVADOS = ("Juana Pérez", "HC-0042", "Campo de Juana", "Plan de Juana")


def _todo_lo_que_puede_fallar():
    """Un plan con nombres del paciente en el plan, en «paciente» y en cada campo, y un campo por cada clase de motivo del lector y del motor."""
    nombre = "Campo de Juana Pérez HC-0042"
    raros = [dict(dosis_cgy="cien"), dict(ssd_cm=None), dict(wedge=1), dict(cuna_grados=15), dict(cuna_grados=15, cuna_tipo="fisica"), dict(cuna_orientacion="IN"),
             dict(cuna_grados=15.5, **FISICA), dict(tecnica="VMAT"), dict(equipo="Halcyon"), dict(energia="6"), dict(x_equivalente_cm=8), dict(dose_cgy=1),
             dict(x_cm=None, y_cm=None, mandibulas_cm={"x1": -5, "x2": 5, "y1": 5, "y2": 5}), dict(dosis_cgy=-5), dict(punto_x_cm=50), dict(um_planeador=0), dict(dosis_cgy=10 ** 400),
             dict(equipo="iX"), dict(cuna_grados=30, **FISICA), dict(nombre=5)]
    campos = [{k: v for k, v in {**B, "nombre": nombre, **r}.items() if v is not None} for r in raros]
    return {"plan": "Plan de Juana Pérez HC-0042", "paciente": "Juana Pérez HC-0042", "equipo": "600C", "energia": "6X", "campos": campos}


def test_ningun_motivo_cita_el_nombre_del_plan_el_del_paciente_ni_el_de_un_campo(datos):
    datos_del_plan = _todo_lo_que_puede_fallar()
    nombre, campos = pj.leer_plan(json.dumps(datos_del_plan))
    assert nombre == "Plan de Juana Pérez HC-0042" and all(c.nombre == "Campo de Juana Pérez HC-0042" for c in campos[:-1])
    motivos = [m for _, _, m in pj.calcular_plan(campos, de_600(datos))]
    assert all(motivos) and len(set(motivos)) == len(motivos)                     # cada clase con su propio motivo
    for motivo in motivos:
        assert not any(p in motivo for p in PRIVADOS), motivo
        assert not SIMBOLOS.search(motivo) and not INGLES.search(motivo), motivo


@pytest.mark.parametrize("cambio", [lambda d: d.update(wedge=1), lambda d: d.update(campos=[]), lambda d: d.update(plan=["Juana Pérez"]), lambda d: d.update(machine="iX"),
                                    lambda d: d["campos"].__setitem__(0, '{"a": 1, "a": 2}')])
def test_un_archivo_rechazado_tampoco_cita_esos_nombres(cambio):
    d = _todo_lo_que_puede_fallar()
    cambio(d)
    texto = json.dumps(d).replace('"{\\"a\\": 1, \\"a\\": 2}"', '{"a": 1, "a": 2}')
    with pytest.raises(pj.PlanInvalido) as fallo:
        pj.leer_plan(texto)
    assert not any(p in str(fallo.value) for p in PRIVADOS) and not INGLES.search(str(fallo.value)), fallo.value


def test_lo_que_cita_un_motivo_va_acortado_y_en_una_linea():
    assert motivo_de(tecnica="Arco\ncon\n" + "x" * 500) == "La técnica «Arco con xxx…xxxxxxxx» no se reconoce como un campo estático: la ecuación 3 de la TG-71 no cubre IMRT ni VMAT, y este campo no se calcula"
    assert motivo_de(cuna_grados=15, cuna_tipo="fisica", cuna_orientacion="Y" * 31) == "La orientación de la cuña («YYYYYYYYYYYY…YYYYYYYY» no es una de las cuatro) debe ser IN, OUT, LEFT o RIGHT"
    assert motivo_de(cuna_grados=15, cuna_tipo="fisica", cuna_orientacion="Y" * 30) == f"La orientación de la cuña («{'Y' * 30}» no es una de las cuatro) debe ser IN, OUT, LEFT o RIGHT"


def test_el_modulo_no_importa_qt_ni_la_base_ni_escribe_nada():
    fuente = open(os.path.join(RAIZ, "services", "um_plan_json.py"), encoding="utf-8").read()
    arbol = ast.parse(fuente)
    importados = {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names} | \
                 {f"{n.module}.{a.name}" for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert importados == {"json", "math", "os", "re", "unicodedata", "collections.Counter", "dataclasses.dataclass", "decimal.Decimal", "services.um_lector_eclipse", "services.um_motor"}
    llamadas = [n for n in ast.walk(arbol) if isinstance(n, ast.Call)]
    nombres = [getattr(n.func, "id", getattr(n.func, "attr", None)) for n in llamadas]
    assert "print" not in nombres and "dumps" not in nombres and "write" not in nombres
    abiertos = [n for n in llamadas if getattr(n.func, "id", None) == "open"]
    assert len(abiertos) == 1 and [a.value for a in abiertos[0].args[1:]] == ["rb"]
    assert "calcular(" in fuente and fuente.count("motor.calcular(") == 1          # el cálculo es el del motor, una vez; aquí no hay física


def test_build_exe_lista_el_lector_una_vez_despues_de_la_puerta_y_sigue_en_crlf():
    crudo = open(os.path.join(RAIZ, "build_exe.py"), "rb").read()
    assert b"\r\n" in crudo and b"\n" not in crudo.replace(b"\r\n", b""), "build_exe.py sigue en CRLF"
    arbol = ast.parse(crudo.decode("utf-8"))
    lista = next(n.value for n in arbol.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "hidden_imports" for t in n.targets))
    nombres = [e.value for e in lista.elts]
    assert nombres.count("services.um_plan_json") == 1
    assert nombres.index("services.um_plan_json") == nombres.index("services.um_datos_haz") + 1
    assert nombres.index("ui.paginasGuia.calculadora_um_cargar") == nombres.index("ui.paginasGuia.calculadora_um") + 1       # lo que fija UM.5 sigue
    assert os.path.exists(os.path.join(RAIZ, "services", "um_plan_json.py"))


# ================================================================================================================================== lo que dejó el barrido por AST (pre-vuelo, 12-11, 09:08)
# Cada caso cierra un sobreviviente que no era equivalente (triaje: borradores/UM6/triaje_del_barrido_a.md).

@pytest.mark.parametrize("clave, que", [("dosis_cgy", "La dosis del campo"), ("um_planeador", "Las UM de Eclipse"), ("x_cm", "El lado X"), ("y_cm", "El lado Y"),
                                        ("lado_equivalente_cm", "El lado equivalente"), ("ssd_cm", "La SSD"), ("profundidad_cm", "La profundidad"),
                                        ("profundidad_efectiva_cm", "La profundidad efectiva"), ("punto_x_cm", "La posición X del punto"), ("punto_y_cm", "La posición Y del punto"),
                                        ("oar", "El OAR"), ("factor_bandeja", "El factor de bandeja")])
def test_cada_numero_se_nombra_en_su_motivo(clave, que):
    assert motivo_de(**{clave: "a"}) == f"{que} debe ser un número y es el texto «a»"


@pytest.mark.parametrize("extra, que", [(dict(x_equivalente_cm="a", y_equivalente_cm=9), "El lado X equivalente"), (dict(x_equivalente_cm=8, y_equivalente_cm="a"), "El lado Y equivalente"),
                                        (dict(cuna_grados="a", **FISICA), "El ángulo de la cuña"), (dict(cuna_grados=30, factor_cuna="a"), "El factor de cuña")])
def test_cada_numero_de_la_cuna_y_del_equivalente_se_nombra_en_su_motivo(extra, que):
    assert motivo_de(**extra) == f"{que} debe ser un número y es el texto «a»"


def test_los_topes_son_los_decididos():
    assert (pj.TAMANO_MAXIMO_BYTES, pj.MAXIMO_DE_CAMPOS, pj.CLAVES_NOMBRADAS, pj.MAXIMO_CITADO, pj.CITA_COMIENZO, pj.CITA_FINAL, pj.MAXIMO_RECONOCIDO) == (2 * 1024 * 1024, 1000, 5, 30, 12, 8, 64)


def test_otro_fallo_del_sistema_se_dice_con_su_tipo(tmp_path, monkeypatch):
    ruta = _escribir(tmp_path, pj.EJEMPLO_DE_PLAN.encode("utf-8"))

    def fallo(*a, **k):
        raise OSError(5, "Input/output error")
    monkeypatch.setattr("builtins.open", fallo)
    with pytest.raises(pj.PlanInvalido, match="^No se pudo leer el archivo: el sistema no lo dejó leer \\(OSError\\)\\.$"):
        pj.leer_archivo(ruta)


def test_un_bom_de_utf16_sin_bytes_nulos_tambien_se_dice_utf16():
    with pytest.raises(pj.PlanInvalido, match="parece UTF-16"):
        pj.texto_del_archivo(b"\xff\xfe{}")
    with pytest.raises(pj.PlanInvalido, match="parece UTF-16"):
        pj.texto_del_archivo(b"\xfe\xff{}")


@pytest.mark.parametrize("texto", ['"campos"', '["campos"]', '[{"campos": [1]}]', "1", "null"])
def test_una_raiz_que_no_es_un_objeto_no_es_un_plan_aunque_contenga_campos(texto):
    with pytest.raises(pj.PlanInvalido, match="^El archivo no es un plan: debe ser un objeto JSON con la lista «campos»\\.$"):
        pj.leer_plan(texto)


@pytest.mark.parametrize("lado", [dict(x_cm=10), dict(y_cm=10)])
def test_las_mandibulas_con_un_solo_lado_tambien_son_a_la_vez(lado):
    campo = {**{k: v for k, v in B.items() if k not in ("x_cm", "y_cm")}, "mandibulas_cm": {"x1": 5, "x2": 5, "y1": 5, "y2": 5}, **lado}
    assert pj.leer_plan(plan(campo))[1][0].problema == "Trae a la vez las mandíbulas y los lados X e Y"


def test_las_mandibulas_que_son_una_lista_con_sus_nombres_no_se_leen():
    assert motivo_de(x_cm=None, y_cm=None, mandibulas_cm=["x1", "x2", "y1", "y2"]) == "Las mandíbulas deben traer exactamente x1, x2, y1 e y2"


@pytest.mark.parametrize("mandibulas, abre", [({"x1": -5, "x2": 5, "y1": 5, "y2": 5}, False), ({"x1": -6, "x2": 5, "y1": 5, "y2": 5}, False), ({"x1": 5, "x2": 5, "y1": -6, "y2": 5}, False),
                                               ({"x1": 0.25, "x2": 0.25, "y1": 5, "y2": 5}, True), ({"x1": 5, "x2": 5, "y1": -1, "y2": 2}, True)])
def test_el_campo_abierto_es_el_de_la_suma_de_cada_par(mandibulas, abre):
    """La suma de cada par, no su producto, y de cada eje por separado; un campo de 0.5 [cm] se lee (lo juzga el motor) y uno de 0 o menos no."""
    c = un_campo(x_cm=None, y_cm=None, mandibulas_cm=mandibulas)
    assert (c.problema is None) == abre, c.problema


def test_un_lado_equivalente_y_solo_el_y_tambien_son_a_la_vez():
    assert motivo_de(lado_equivalente_cm=8, y_equivalente_cm=8) == "Trae a la vez un lado equivalente y los lados X e Y equivalentes"


def test_una_cuna_de_menos_un_grado_tampoco_vale():
    assert motivo_de(cuna_grados=-1, **FISICA) == "El ángulo de la cuña debe ser un número entero de grados, mayor que 0, y es -1"


def test_un_plan_sin_nombre_tiene_el_nombre_vacio():
    assert pj.leer_plan(plan(B))[0] == "" and pj.leer_plan(plan(B, plan=None))[0] == ""


def test_cinco_claves_desconocidas_se_nombran_sin_decir_mas():
    assert motivo_de(**{f"k{i}": 1 for i in range(5)}) == "Trae claves que este lector no conoce: «k0», «k1», «k2», «k3», «k4»"


def test_los_otros_nombres_del_plan_tambien_valen():
    _, c = pj.leer_plan(json.dumps({"treatment_machine": "iX", "energy": "15X", "technique": "static", "campos": [B]}))
    assert (c[0].equipo, c[0].energia, c[0].problema) == ("Clinac iX", "15 MV", None)


def test_un_archivo_que_crecio_despues_de_mirar_su_tamano_no_se_lee_cortado(tmp_path, monkeypatch):
    """Se lee hasta pasar el tope por un byte: si creció entre mirar su tamaño y leerlo, se nota; leerlo cortado en el tope daría un JSON que no es el del archivo."""
    ruta = _escribir(tmp_path, b" " * (pj.TAMANO_MAXIMO_BYTES - 2) + b"[]  ")
    monkeypatch.setattr(os.path, "getsize", lambda r: 10)
    with pytest.raises(pj.PlanInvalido, match="^El archivo mide más de 2 \\[MB\\]"):
        pj.leer_archivo(ruta)


def test_un_archivo_justo_en_el_tope_se_lee_entero(tmp_path):
    """El relleno va ANTES del JSON: leerlo con un byte de menos lo cortaría."""
    crudo = pj.EJEMPLO_DE_PLAN.encode("utf-8")
    justo = b" " * (pj.TAMANO_MAXIMO_BYTES - len(crudo)) + crudo
    assert len(justo) == pj.TAMANO_MAXIMO_BYTES and len(pj.leer_plan(pj.leer_archivo(_escribir(tmp_path, justo)))[1]) == 5


# ================================================================================================================================== lo que cerró la ronda 1 de la revisión (12-11)
# Cada prueba de esta sección cierra un hallazgo reproducido de los dos revisores de UM.6 (borradores/UM6/obstaculos.md: UM6-P1 a UM6-P5 y UM6-RP1 a UM6-RP4). Las de P1, P2 y P3 caían contra el
# lector de antes de la ronda. Las demás pasaban, pero las mutaciones R01 a R07 de `um6_mutaciones.py` SOBREVIVÍAN: ninguna prueba fijaba lo que su nombre prometía.

def _eclipse(decimas):
    """Un largo de Eclipse con un decimal, escrito como lo escribe el físico: 52 décimas son «5.2». Sale de un entero, sin coma flotante: la verdad conocida es independiente del lector."""
    return f"{decimas // 10}.{decimas % 10}"


PARES_DE_ECLIPSE = [(i, j) for i in range(20, 101) for j in range(20, 101)]       # x1 y x2 de 2.0 a 10.0 [cm], con un decimal: 6561 pares, en décimas
SIN_LADOS = {k: v for k, v in B.items() if k not in ("x_cm", "y_cm")}


def test_el_lado_y_el_centro_de_las_mandibulas_son_los_que_el_fisico_escribiria_para_todo_par_de_un_decimal():
    """UM6-P1. x1 + x2 en coma flotante no es el lado escrito (0.1 + 5.1 da 5.199999999999999): en 1088 de estos 6561 pares el motor veía láminas donde el formulario no (compara el campo efectivo con las
    mandíbulas por igualdad exacta). Las décimas son enteros: el lado es (i + j)/10 y el centro (j − i)/20, redondeados una sola vez, que son los números que el formulario recibe al escribirlos."""
    malos = []
    for desde in range(0, len(PARES_DE_ECLIPSE), pj.MAXIMO_DE_CAMPOS):
        pares = PARES_DE_ECLIPSE[desde:desde + pj.MAXIMO_DE_CAMPOS]
        campos = [{**SIN_LADOS, "mandibulas_cm": {"x1": i / 10, "x2": j / 10, "y1": j / 10, "y2": i / 10}} for i, j in pares]
        for (i, j), campo in zip(pares, pj.leer_plan(plan(*campos))[1]):
            e = campo.entrada
            leido, escrito = (e.x, e.y, e.centro_x, e.centro_y), ((i + j) / 10, (i + j) / 10, (j - i) / 20, (i - j) / 20)
            if leido != escrito:
                malos.append((i / 10, j / 10, leido, escrito))
    assert not malos, f"{len(malos)} de {len(PARES_DE_ECLIPSE)} pares; x1, x2, (lado X, lado Y, centro X, centro Y) leído y escrito: {malos[:3]}"


@pytest.mark.parametrize("con_equivalente", [True, False], ids=["con el equivalente igual a las mandibulas", "sin equivalente"])
@pytest.mark.parametrize("i, j", [(1, 51), (26, 97), (41, 42), (7, 71), (30, 30), (51, 1), (25, 100)], ids=[f"{i / 10}+{j / 10}" for i, j in [(1, 51), (26, 97), (41, 42), (7, 71), (30, 30), (51, 1), (25, 100)]])
def test_con_mandibulas_el_json_da_lo_mismo_que_el_formulario_aunque_la_suma_no_sea_exacta_en_coma_flotante(manual, datos, i, j, con_equivalente):
    """UM6-P1, la convergencia (corolario 3) con mandíbulas: la `Entrada` del JSON es IGUAL a la del formulario, donde se escribe el lado y el centro; el resultado, el texto para copiar y los avisos son
    los mismos. Con el equivalente escrito igual a las mandíbulas no hay láminas (aviso de «campo efectivo de lado equivalente»): en (2.6, 9.7) el JSON daba 249.279 UM y el formulario 249.704."""
    lado, centro = _eclipse(i + j), f"{(j - i) / 20:g}"
    del_json = {"nombre": "mandíbulas", "dosis_cgy": 200, "um_planeador": 250, "mandibulas_cm": {"x1": i / 10, "x2": j / 10, "y1": 5.0, "y2": 5.0}, "ssd_cm": 90, "profundidad_cm": 10}
    del_formulario = {"dosis": "200", "um_planeador": "250", "x": lado, "y": "10", "centro_x": centro, "ssd": "90", "prof": "10", "tf": "1.000"}
    if con_equivalente:
        del_json.update(x_equivalente_cm=float(lado), y_equivalente_cm=10.0)
        del_formulario.update(x_ef=lado, y_ef="10")
    campo = pj.leer_plan(plan(del_json))[1][0]
    en_el_formulario = manual.entrada_desde_textos(del_formulario, None, None)
    assert campo.problema is None and campo.entrada == en_el_formulario
    (_, resultado, motivo), = pj.calcular_plan([campo], de_600(datos))
    directo = motor.calcular(datos, en_el_formulario)
    assert motivo is None and resultado == directo
    assert manual.texto_para_copiar(resultado) == manual.texto_para_copiar(directo)
    assert not any("campo efectivo de lado equivalente" in aviso for aviso in resultado.avisos)


@pytest.mark.parametrize("donde, n_ceros, n_campos", [("campo", 30000, 1), ("plan", 3000, 100)], ids=["la energia de un campo", "la energia del plan, que se reconoce en cada campo"])
def test_una_energia_de_ceros_sin_unidad_no_congela_la_lectura(donde, n_ceros, n_campos):
    """UM6-P2. `um_lector_eclipse.clave_energia` empieza por `0*([0-9]+...)`: con una tira de ceros y sin unidad los dos se solapan y el retroceso es cuadrático (32000 ceros tardaban 10 [s]; 2000 ceros
    en la energía del plan y 1000 campos, 41 [s], dentro de los topes de 2 [MB] y de 1000 campos). La lectura corre en el hilo de la pantalla (H14): un archivo así la congelaba."""
    ceros = "0" * n_ceros
    campo = {**B, "energia": ceros} if donde == "campo" else B
    texto = plan(*([campo] * n_campos), **({} if donde == "campo" else {"energia": ceros}))
    t0 = time.perf_counter()
    _, campos = pj.leer_plan(texto)
    assert time.perf_counter() - t0 < 1.0
    assert len(campos) == n_campos and all(c.entrada is None and c.problema.startswith("La energía «") and "no se reconoce" in c.problema for c in campos)      # lo que cita, acortado, lo fija la prueba de las citas


def test_el_tope_de_caracteres_de_un_equipo_o_una_energia_es_el_decidido():
    """UM6-D9 (el corrector, ronda 1; vetable): un equipo o una energía de más de 64 caracteres no se pasa al lector de Eclipse y no se reconoce (los reales miden menos de 25). El lector de energías quita los
    espacios y el de equipos todo lo que no es letra ni cifra: con 64 caracteres, el tope, se reconoce; con uno más, no."""
    energia, de_mas = "6" + " " * 61 + "MV", "6" + " " * 62 + "MV"
    equipo, equipo_de_mas = "Clinac" + " " * 54 + "600C", "Clinac" + " " * 55 + "600C"
    assert [len(t) for t in (energia, de_mas, equipo, equipo_de_mas)] == [64, 65, 64, 65]
    assert (un_campo(energia=energia).energia, un_campo(equipo=equipo).equipo) == ("6 MV", "Clinac 600")
    sin_energia, sin_equipo = un_campo(energia=de_mas), un_campo(equipo=equipo_de_mas)
    assert (sin_energia.entrada, sin_energia.energia, sin_equipo.entrada, sin_equipo.equipo) == (None, None, None, None)
    assert "no se reconoce" in sin_energia.problema and "no es uno de esta calculadora" in sin_equipo.problema


def test_el_lector_de_eclipse_solo_recibe_textos_acotados():
    """UM6-D9: todo equipo o energía del archivo pasa por `_reconocer` (el tope de caracteres) antes de llegar a `um_lector_eclipse.clave_equipo` o `clave_energia`: otro uso directo, en un sitio nuevo,
    dejaría pasar el texto entero y con él el retroceso cuadrático de UM6-P2."""
    arbol = ast.parse(open(os.path.join(RAIZ, "services", "um_plan_json.py"), encoding="utf-8").read())
    usos = [n for n in ast.walk(arbol) if isinstance(n, ast.Attribute) and getattr(n.value, "id", None) == "lector" and n.attr.startswith("clave_")]
    acotados = [a for c in ast.walk(arbol) if isinstance(c, ast.Call) and getattr(c.func, "id", None) == "_reconocer" for a in c.args]
    assert sorted(u.attr for u in usos) == ["clave_energia", "clave_equipo"]
    assert all(any(u is a for a in acotados) for u in usos)


def test_un_byte_que_no_es_utf8_se_dice_con_su_lugar_en_el_archivo_con_bom_o_sin_el(tmp_path):
    """UM6-P3. Con BOM, `decode("utf-8-sig")` cuenta el byte del fallo desde DESPUÉS del BOM: el motivo decía de qué byte se trata y señalaba uno tres lugares antes del verdadero."""
    crudo = pj.EJEMPLO_DE_PLAN.encode("latin-1")
    for bom in (b"", b"\xef\xbb\xbf"):
        primero = len(bom) + crudo.index("é".encode("latin-1")) + 1
        with pytest.raises(pj.PlanInvalido, match=f"^El archivo no está en UTF-8: el byte {primero} no se entiende\\. Guárdelo como UTF-8\\.$"):
            pj.leer_archivo(_escribir(tmp_path, bom + crudo, f"con_{len(bom)}_bytes_de_bom.json"))
    with pytest.raises(pj.PlanInvalido, match="^El archivo no está en UTF-8: el byte 6 no se entiende\\. Guárdelo como UTF-8\\.$"):
        pj.texto_del_archivo(b"\xef\xbb\xbfab\xffcd")
    with pytest.raises(pj.PlanInvalido, match="^El archivo no está en UTF-8: el byte 3 no se entiende\\. Guárdelo como UTF-8\\.$"):
        pj.texto_del_archivo(b"ab\xffcd")


@pytest.mark.parametrize("extra, motivo", [
    (dict(equipo="A\n" + "x" * 500), "El equipo «A xxxxxxxxxx…xxxxxxxx» no es uno de esta calculadora: el Clinac 600 o el Clinac iX"),
    (dict(energia="E\n" + "y" * 500), "La energía «E yyyyyyyyyy…yyyyyyyy» no se reconoce: debe ser de fotones en MV, como 6X o 6 MV"),
    (dict(cuna_grados=15, cuna_tipo="T\n" + "z" * 500, cuna_orientacion="IN"),
     "Una cuña sin su factor escrito («factor_cuna») debe ser física: el tipo de cuña («cuna_tipo») debe decir «fisica», y dice «T zzzzzzzzzz…zzzzzzzz». Una cuña dinámica no tiene tablas y necesita su factor"),
], ids=["el equipo", "la energia", "el tipo de cuña"])
def test_lo_que_cita_un_motivo_del_equipo_la_energia_y_el_tipo_de_cuna_va_acortado_y_en_una_linea(extra, motivo):
    """UM6-RP2: de los ocho sitios que citan texto del archivo, estos tres no tenían ninguna prueba con un texto largo o de varias líneas (los equipos, energías y tipos de las pruebas medían 30 o menos)."""
    assert motivo_de(**extra) == motivo


def test_el_error_inesperado_cita_su_mensaje_acortado_y_en_una_linea():
    """UM6-P4 y RP2: el mensaje de un error inesperado (quien trae las tablas, o el motor) puede ser largo y de varias líneas; el motivo lo acorta como todo lo que cita."""
    def datos_de(equipo, energia):
        raise RuntimeError("primera línea\n" + "y" * 500)
    motivos = [m for _, _, m in pj.calcular_plan(pj.leer_plan(plan(B, B))[1], datos_de)]
    assert motivos == ["El cálculo falló por un error inesperado (RuntimeError: primera líne…yyyyyyyy). Avise a quien mantiene la app."] * 2


@pytest.mark.parametrize("como, motivo", [
    ("sin tablas", "No hay tablas cargadas del Clinac 600, 6 MV: sin ellas este campo no se calcula"),
    ("con un motivo", "Las tablas guardadas de Clinac 600, 6 MV no se pueden usar: el archivo «a» guardado no coincide con su huella"),
    ("con un defecto", "El cálculo falló por un error inesperado (ZeroDivisionError: division by zero). Avise a quien mantiene la app."),
], ids=["datos_de da None", "datos_de lanza el motivo del motor", "datos_de lanza un defecto"])
def test_un_haz_sin_tablas_o_que_falla_se_pide_una_vez_por_plan(como, motivo):
    """UM6-D5 y RP1: «los datos de cada haz se piden UNA vez por plan» también cuando el haz no tiene tablas o traerlas falla (con `datos_de` = `um_datos_haz.datos_del_haz`, que lee la base y arma los
    archivos, un plan de N campos de un haz así leería N veces en el hilo de la pantalla)."""
    pedidos = []

    def datos_de(equipo, energia):
        pedidos.append((equipo, energia))
        if como == "con un motivo":
            raise motor.FaltaDato("Las tablas guardadas de Clinac 600, 6 MV no se pueden usar: el archivo «a» guardado no coincide con su huella")
        if como == "con un defecto":
            return 1 / 0
        return None
    salida = pj.calcular_plan(pj.leer_plan(plan(B, B, B, B))[1], datos_de)
    assert pedidos == [(EQUIPO, ENERGIA)]
    assert [m for _, _, m in salida] == [motivo] * 4


def test_un_nombre_con_null_cuenta_como_presente_y_dos_nombres_siguen_siendo_un_error():
    """UM6-RP3: «Dos nombres para lo mismo son un error, aunque digan lo mismo» (`_valor`): también si uno de los dos es `null`, en un campo y en lo que el plan dice para todos."""
    assert pj.leer_plan(plan({**B, "dose_cgy": None}))[1][0].problema == "Trae dos nombres para lo mismo: «dose_cgy», «dosis_cgy»"
    with pytest.raises(pj.PlanInvalido) as fallo:
        pj.leer_plan(plan(B, machine=None))
    assert str(fallo.value) == "Trae dos nombres para lo mismo: «equipo», «machine» (en el plan, fuera de «campos»)."


@pytest.mark.parametrize("texto", ["{} \u0301", "\u0301 {}", " \u0301{} \u0301 "], ids=["tilde suelta despues", "tilde suelta antes", "una a cada lado"])
def test_un_espacio_junto_a_una_tilde_suelta_se_ignora_como_los_de_los_bordes(texto):
    """UM6-RP4: el `.strip()` de `_sin_tildes` no es de más: un espacio pegado a una tilde suelta (U+0301) sobrevive al recorte de `_texto`, porque la tilde no es un espacio, y al quitar la tilde queda en el borde.
    El triaje del barrido lo daba por equivalente («todo lo que llega ya viene recortado»): no lo es."""
    assert un_campo(cuna_grados=15, cuna_tipo=texto.format("fisica"), cuna_orientacion="IN").entrada.cuna == 15
    assert un_campo(cuna_grados=15, cuna_tipo="fisica", cuna_orientacion=texto.format("in")).entrada.cuna_orientacion == "IN"
