"""DP147.1 (PLAN_DP147_PDF_MENSUAL_POR_TIPO_17-10.md, DP-147): el PDF mensual de braquiterapia se lee de la tabla del tipo PEDIDO, nunca de la que
tenga el mismo id.

CAUSA medida (§0 del plan). `_recopilar_datos_completos` preguntaba PRIMERO por `LinealidadBraquiterapia WHERE id = ref_id`, sin mirar que reporte
se pidio: si existia una linealidad (vigente o anulada: no filtraba) con el mismo id que la calibracion, imprimia ESA fila. Los ids de las dos
tablas son contadores independientes; en la copia de la produccion del 06-10 el PDF del cambio de fuente del 27-09-2025 (`TipoCalibracion` 14) salia
como el de la linealidad del 26-12-2025 (`LinealidadBraquiterapia` 14), con el encabezado, la fecha y la firma de la calibracion y el cuerpo de otro
control. La pregunta «¿es el reporte de linealidad?» se contestaba tres veces con tres reglas; la segunda la contestaba el DATO y no lo pedido.

LO QUE SE GARANTIZA, cada cosa con su prueba:
  1. BASE NUEVA con la colision POR CONSTRUCCION (la plantilla de `Conexion()`: los dos contadores empiezan en 1; calibraciones 1, 2 y 3 de los tres
     tipos del boton, linealidades 1 VIGENTE, 2 ANULADA y 3 VIGENTE), con `reporte_mensual` REAL y el visor falso:
       1a. cada calibracion, por su (fecha, tipo), imprime SU cuerpo (serie, las CINCO hijas con valores propios -CondicionesMedicion incluida-, firmante, las 7 tablas) y
           ninguna marca de linealidad ni de otra calibracion (la 2 prueba que lo anulado tampoco secuestra);
       1b. en un pedido de calibracion se llama SOLO al lector de identidad de `TipoCalibracion`, con el `ref` resuelto;
       1c. los pedidos de linealidad imprimen su linealidad y llaman SOLO al lector de linealidad;
       1d. metamorfica: el PDF de una calibracion es IGUAL con y sin las linealidades en la base (tablas que recibe el generador y texto con posicion), y el
           de una linealidad es IGUAL con y sin las calibraciones;
       1e. lo que ya estaba bien (base sin colisiones): el respaldo por dia y el aviso «No se encontro control mensual...».
  2. COPIA REAL (`BD_REBUILD_08_10`, copiada a un temporal; salta si falta, HI-0): el 27-09-2025 en los tres tipos imprime la calibracion 14 (4 paginas)
     y el 26-12-2025 'Linealidad' imprime la linealidad 14.
  3. TRIPWIRES por AST: T1 una sola definicion (`_es_reporte_de_linealidad`) de la pregunta, que usan las tres decisiones: el texto «linealidad» no se pregunta en NINGUNA
     otra forma (igualdad, tupla/lista/set/diccionario literal, constante de modulo, match, f-string...); T2 la CLASE: un id nunca elige su tabla (toda funcion que lee por id
     de dos raices -con su SQL, con lectores o a traves de envoltorios del mismo archivo- esta declarada con su motivo y en ella cada par vive en ramas EXCLUYENTES de un `if`
     cuyo test es SOLO lo pedido; ningun `if` pregunta por un lector ni por su resultado), con pruebas de que discrimina; T3 la firma: `tipo_reporte` SIN valor por omision en la
     recopilacion y toda llamada del repo lo pasa (decision D2 del plan: quien llame sin decir que reporte quiere falla en voz alta en vez de adivinar), y en
     `_procesar_datos_para_reporte` (que sirve a todas las maquinas) solo `None`, que braquiterapia rechaza en voz alta (H1 de la revision de la ronda 1).

Trampas: T2 de CLAUDE.md (`reporte_mensual` se traga los errores en un `QMessageBox.critical`: se captura y la prueba falla si avisa; ningun dialogo real
bajo offscreen); T4 (la conexion `qt_sql_default_connection` se suelta entre pedidos); «disk I/O error» de dos SQLite en un proceso (TODO se siembra con
`sqlite3` ANTES de abrir ninguna conexion Qt sobre esa base, y despues solo se lee); T5 (el parche conserva el numero de cada linea de HEAD y la funcion nueva va al
final: no lo comprueba esta prueba sino la compuerta diferencial del anexo, y los censores por linea siguen verdes sin tocarlos); T9/T10 (ningun contenedor ni
`lru_cache` de modulo: el unico estado compartido vive en fixtures de modulo).
Nunca se abre una BD de referencia: la copia real se copia a un temporal y la base nueva se crea en otro."""
import ast
import hashlib
import os
import re
import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from _bd_referencia import BD_REBUILD_08_10

RAIZ = Path(__file__).resolve().parent.parent
REPORTE = "models/PDF/Mensuales/reportes_mensuales.py"
REPORTE_ANUAL = "models/PDF/Anual/reportes_anuales.py"
CAMBIO, MENSUAL, REDUNDANTE = "Cambio de fuente", "Control Mensual", "Calibración Redundante"

# El cuerpo de una calibracion y el de una linealidad: las tablas que recibe el generador del PDF y las marcas del texto
CLAVES_DE_CALIBRACION = {"tipo_calibracion", "sistema_medicion", "condiciones_medicion", "maximos_camaras", "lecturas_maximos",
                         "resultados_actividad", "grafico_maximos"}
CLAVES_DE_LINEALIDAD = {"sistema_medicion_linealidad", "carga_colectada", "medidas_linealidad", "resultados_linealidad", "grafico_linealidad"}
MARCAS_DE_LINEALIDAD = ("Carga colectada en 60s", "Medidas de linealidad", "Gráfico de linealidad", "LIN-UNO", "LIN-DOS-ANULADA", "LIN-TRES", "Fisica Linealidad")
LECTORES = (("_obtener_datos_linealidad_braquiterapia", "LinealidadBraquiterapia"),
            ("_obtener_datos_tabla_principal_braquiterapia", "TipoCalibracion"))

# Las tres calibraciones de la base nueva: cada una con su serie, certificado, firmante e hijas PROPIAS (nada se repite entre ellas, tampoco las condiciones de
# medicion: t, p, h y desplazamiento de CondicionesMedicion. Antes valian lo mismo en las tres y una hija leida con el `ref` de OTRA calibracion no se notaba)
CALIBRACIONES = {
    "cf": SimpleNamespace(id=1, fecha="2026-01-10 15:03:03", tipo=CAMBIO, serie="SERIE-CF", certificado="CERT-CF", usuario="Fisico CF", cp="CP-CF",
                          ele="EL-CF", maximos=("70.11", "71.22", "70.93"), actividad=(9.101, 9.202, 9.303), lectura="7.11e-08",
                          t=21.51, p=641.11, h=41.41, desplazamiento=0.131),
    "cm": SimpleNamespace(id=2, fecha="2026-02-20 10:00:00", tipo=MENSUAL, serie="SERIE-CM", certificado="CERT-CM", usuario="Fisico CM", cp="CP-CM",
                          ele="EL-CM", maximos=("60.11", "61.22", "60.93"), actividad=(8.101, 8.202, 8.303), lectura="6.11e-08",
                          t=22.62, p=642.22, h=42.52, desplazamiento=0.232),
    "cr": SimpleNamespace(id=3, fecha="2026-01-10 15:20:00", tipo=REDUNDANTE, serie="SERIE-CR", certificado="CERT-CR", usuario="Fisico CR", cp="CP-CR",
                          ele="EL-CR", maximos=("50.11", "51.22", "50.93"), actividad=(7.101, 7.202, 7.303), lectura="5.11e-08",
                          t=23.73, p=643.33, h=43.63, desplazamiento=0.333),
}
# Las tres linealidades (los ids 1, 2 y 3 son los de las tres calibraciones): vigente, ANULADA, vigente
LINEALIDADES = {
    "uno": SimpleNamespace(id=1, fecha="2026-03-03", activo=1, marca="LIN-UNO"),
    "dos": SimpleNamespace(id=2, fecha="2026-03-04", activo=0, marca="LIN-DOS-ANULADA"),
    "tres": SimpleNamespace(id=3, fecha="2026-03-05", activo=1, marca="LIN-TRES"),
}
SUFIJO_DE_ID_SIN_COLISION = 1000       # las linealidades de la base sin colisiones llevan los ids 1001, 1002 y 1003


def _dia(fecha):
    return fecha.split(" ")[0]


# --------------------------------------------------------------------------------------------------------------------------- siembra (solo sqlite3)

def _sembrar_calibracion(con, c):
    con.execute("INSERT INTO TipoCalibracion (id, user, fecha, tipo, serie, certificado, fecha_cer, intensidad, conversion, activo) VALUES (?,?,?,?,?,?,?,?,?,1)",
                (c.id, c.usuario, c.fecha, c.tipo, c.serie, c.certificado, "2025-12-01 10:00:00", 10.5, 0.11))
    con.execute("INSERT INTO SistemaMedicion (ref, user, fecha, modelo, serie_cp, calibracion, modelo_elec, serie_ele, electrometro, t0, p0, h0, activo) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)", (c.id, c.usuario, c.fecha, "HDR1000 Plus", c.cp, 466700.0, "CDX-2000B", c.ele, 1.0, 22.0, 760.0, 50.0))
    con.execute("INSERT INTO CondicionesMedicion (ref, user, fecha, t, p, h, desplazamiento_ini, activo) VALUES (?,?,?,?,?,?,?,1)",
                (c.id, c.usuario, c.fecha, c.t, c.p, c.h, c.desplazamiento))
    for posicion, medida in zip(("127.5", "127.0", "126.5"), c.maximos):
        con.execute("INSERT INTO MaximosCamaras (ref, user, fecha, posicion, medida1, medida2, promedio, activo) VALUES (?,?,?,?,?,?,?,1)",
                    (c.id, c.usuario, c.fecha, posicion, medida, medida, medida))
    for voltaje in ("300.0", "150.0", "-300.0"):
        con.execute("INSERT INTO LecturasMaximos (ref, user, fecha, voltaje, V_300, V_150, Vn_300, promediosV, activo) VALUES (?,?,?,?,?,?,?,?,1)",
                    (c.id, c.usuario, c.fecha, voltaje, c.lectura, c.lectura, c.lectura, c.lectura))
    monitor, calculada, decaimiento = c.actividad
    con.execute("INSERT INTO ResultadosActividad (ref, user, fecha, Ks, Kp, Ktp, actividad_monitor, actividad_calculada, actividad_decaimiento, activo) "
                "VALUES (?,?,?,1.0,1.0,1.182,?,?,?,1)", (c.id, c.usuario, c.fecha, monitor, calculada, decaimiento))


def _sembrar_linealidad(con, identificador, fecha, activo, marca):
    """Una linealidad COMPLETA (los 10 puntos y las 5 medidas de reproducibilidad): sin ellos el PDF de linealidad no se genera."""
    valores = {"id": identificador, "user": "Fisica Linealidad", "fecha": fecha, "modelo": "MODELO-LIN", "serie_cp": marca, "calibracion": 467900.0,
               "modelo_elec": "CDX-2000B", "serie_ele": "EL-LIN", "electrometro": 1.0, "q_est": 2134.7, "t_integrado": 30.0, "i_est": 71.16,
               "reproducibilidad": 99.8, "exactitud": 0.99999, "tiempo_transito": 1.59, "repro_prom": 4379.16, "activo": activo}
    for m in range(1, 6):
        valores[f"repro_m{m}"] = 4379.0 + m / 10
    for i in range(10):
        tp = 0.1 * 2 ** i
        valores.update({f"lin_tp_{i}": tp, f"lin_q1_{i}": 120 + 70 * tp, f"lin_q2_{i}": 120.5 + 70 * tp, f"lin_qprom_{i}": 120.25 + 70 * tp, f"lin_te_{i}": 1.7 + tp})
    con.execute(f"INSERT INTO LinealidadBraquiterapia ({', '.join(valores)}) VALUES ({', '.join('?' * len(valores))})", tuple(valores.values()))


def _sembrar(ruta, calibraciones=True, linealidades=True, desplazamiento_de_ids=0):
    con = sqlite3.connect(ruta)
    try:
        if calibraciones:
            for c in CALIBRACIONES.values():
                _sembrar_calibracion(con, c)
        if linealidades:
            for lin in LINEALIDADES.values():
                _sembrar_linealidad(con, lin.id + desplazamiento_de_ids, lin.fecha, lin.activo, lin.marca)
        con.commit()
    finally:
        con.close()


# ------------------------------------------------------------------------------------------------------------------------- fixtures y el pedido real

@pytest.fixture(scope="module")
def app():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def rm(app):
    import data.ManejoDatos.load  # noqa: F401  (antes que models.PDF: el ciclo de importaciones, como test_pi7)
    from models.PDF.Mensuales import reportes_mensuales
    return reportes_mensuales


@pytest.fixture(autouse=True, scope="module")
def sin_dialogos_reales():
    """Trampa 2: ningun QMessageBox real bajo offscreen (un modal esperando un clic cuelga el proceso). De alcance de MODULO a proposito: la fixture `oficina`
    (tambien de modulo) captura los `critical` por encima de este parche, y una autouse de alcance de funcion los pisaria otra vez en cada prueba."""
    from PyQt5.QtWidgets import QMessageBox
    with pytest.MonkeyPatch.context() as mp:
        for tipo in ("information", "warning", "critical", "question"):
            mp.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: QMessageBox.Ok))
        yield


@pytest.fixture(scope="module")
def plantilla(tmp_path_factory):
    """La BD NUEVA con el esquema completo de `Conexion()`, hecha UNA vez; cada base trabaja sobre su copia."""
    ruta = str(tmp_path_factory.mktemp("dp147") / "plantilla.db")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
        previo = Conexion._instance
        Conexion._instance = None
        try:
            Conexion().con.close()
            Conexion._instance = None
        finally:
            Conexion._instance = previo
    return ruta


@pytest.fixture(scope="module")
def bases(plantilla, tmp_path_factory):
    """Cuatro bases NUEVAS sembradas con `sqlite3` antes de que NADIE abra una conexion Qt sobre ellas: completa (calibraciones 1-3 y linealidades 1-3: los ids
    colisionan), solo calibraciones, solo linealidades y sin colision (linealidades 1001-1003). Despues solo se leen."""
    carpeta = tmp_path_factory.mktemp("dp147_bases")
    rutas = {}
    for nombre, kw in (("completa", dict()), ("solo_calibraciones", dict(linealidades=False)), ("solo_linealidades", dict(calibraciones=False)),
                       ("sin_colision", dict(desplazamiento_de_ids=SUFIJO_DE_ID_SIN_COLISION))):
        destino = str(carpeta / f"{nombre}.db")
        shutil.copy(plantilla, destino)
        _sembrar(destino, **kw)
        rutas[nombre] = destino
    return rutas


def _celda(v):
    if hasattr(v, "drawWidth"):
        return f"IMAGEN {round(float(v.drawWidth))}x{round(float(v.drawHeight))}"
    if isinstance(v, (bytes, bytearray)):
        return "BYTES " + hashlib.sha256(bytes(v)).hexdigest()[:16]
    s = str(v)
    return s if len(s) < 200 else "TEXTO " + hashlib.sha256(s.encode()).hexdigest()[:16]


def _serializar(valor):
    import pandas as pd
    if isinstance(valor, pd.DataFrame):
        return {"columnas": [str(c) for c in valor.columns], "filas": [[_celda(v) for v in fila] for fila in valor.values.tolist()]}
    return {"columnas": ["?"], "filas": [[_celda(valor)]]}


@pytest.fixture(scope="module")
def oficina(rm):
    """El pedido REAL de un PDF mensual de braquiterapia: `reporte_mensual` con el visor falso, un generador que deja constancia de las tablas que recibe, el
    espia de los dos lectores de identidad y los dialogos capturados. Cada pedido se hace UNA vez por (base, fecha, tipo) y se recuerda (el estado vive aqui, no
    en el modulo); `fresco=True` fuerza otro pedido (el control de ruido de 1d)."""
    import fitz
    from PyQt5.QtSql import QSqlDatabase
    from PyQt5.QtWidgets import QMessageBox

    estado = SimpleNamespace(errores=[], leido=[], capt={}, visor={}, recuerdo={})

    def quitar_la_conexion_por_omision():                       # Trampa 4: la conexion por omision de QtSql se cachea por PROCESO
        if QSqlDatabase.contains("qt_sql_default_connection"):
            QSqlDatabase.database("qt_sql_default_connection").close()
            QSqlDatabase.removeDatabase("qt_sql_default_connection")

    class FalsoVisor:
        def __init__(self, pdf_data=None, **k):
            estado.visor["pdf"] = pdf_data

        def show(self):
            pass

    real = rm.generar_reporte_pdf_multitabla_mensual

    def generador(*a, **k):
        tablas = k.get("tablas", a[0] if a else None)
        estado.capt["tablas"] = {str(c): _serializar(v) for c, v in tablas.items()}
        estado.capt["user"] = k.get("user")
        estado.capt["tipo_reporte"] = k.get("tipo_reporte")
        return real(*a, **k)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: estado.errores.append(str(a[2]) if len(a) > 2 else str(a))))
        for tipo in ("information", "warning", "question"):
            mp.setattr(QMessageBox, tipo, staticmethod(lambda *a, **k: QMessageBox.Ok))
        mp.setattr(rm, "PdfViewer", FalsoVisor)
        mp.setattr(rm, "generar_reporte_pdf_multitabla_mensual", generador)
        for nombre, tabla in LECTORES:
            original = getattr(rm, nombre)

            def espia(db, ref_id, _o=original, _t=tabla):
                r = _o(db, ref_id)
                estado.leido.append([_t, ref_id, bool(r)])
                return r
            mp.setattr(rm, nombre, espia)

        def pedir(ruta, fecha, tipo, fresco=False):
            clave = (str(ruta), fecha, tipo)
            if not fresco and clave in estado.recuerdo:
                return estado.recuerdo[clave]
            # la MISMA base para el reporte (QtSql) y para los servicios que abren sqlite3 con Conexion() (la posicion inicial)
            mp.setattr(conection_mod, "ruta_base_datos", lambda: str(ruta))
            mp.setattr(Conexion, "_instance", object.__new__(Conexion))
            quitar_la_conexion_por_omision()

            class Pantalla:
                def opeenDatabase(self):
                    quitar_la_conexion_por_omision()
                    db = QSqlDatabase.addDatabase("QSQLITE")
                    db.setDatabaseName(str(ruta))
                    db.open()
                    return db

            estado.errores.clear(); estado.leido.clear(); estado.capt.clear(); estado.visor.clear()
            rm.reporte_mensual(Pantalla(), fecha, "Braquiterapia", "IDC", tipo, None, None, "")
            r = SimpleNamespace(base=os.path.basename(str(ruta)), fecha=fecha, tipo=tipo, errores=list(estado.errores), leido=[list(x) for x in estado.leido],
                                pdf="pdf" in estado.visor, texto="", palabras=[], paginas=0, tablas=dict(estado.capt.get("tablas") or {}),
                                claves=set((estado.capt.get("tablas") or {}).keys()), user=estado.capt.get("user"),
                                tipo_reporte=estado.capt.get("tipo_reporte"))
            if r.pdf:
                doc = fitz.open(stream=bytes(estado.visor["pdf"]), filetype="pdf")
                try:
                    r.paginas = doc.page_count
                    r.texto = " ".join(" ".join(p.get_text() for p in doc).split())
                    r.palabras = [[[round(c, 1) for c in w[:4]] + [w[4]] for w in p.get_text("words")] for p in doc]
                finally:
                    doc.close()
            estado.recuerdo[clave] = r
            return r

        try:
            yield SimpleNamespace(pedir=pedir)
        finally:
            quitar_la_conexion_por_omision()
            estado.recuerdo.clear()


def _instantanea(r):
    """Todo lo que un fisico veria de un PDF y lo que el generador recibio: para comparar dos pedidos."""
    return {"claves": sorted(r.claves), "tablas": r.tablas, "user": r.user, "tipo_reporte": r.tipo_reporte, "paginas": r.paginas, "texto": r.texto,
            "palabras": r.palabras}


def _en_que_difieren(a, b):
    ia, ib = _instantanea(a), _instantanea(b)
    return [campo for campo in ia if ia[campo] != ib[campo]]


def _marcas_de_linealidad(r):
    return [m for m in MARCAS_DE_LINEALIDAD if m in r.texto] + [f"tabla {k}" for k in sorted(r.claves & CLAVES_DE_LINEALIDAD)]


HIJAS = ("SistemaMedicion", "CondicionesMedicion", "MaximosCamaras", "LecturasMaximos", "ResultadosActividad")


def _marcas_de_hijas(c):
    """{hija -> textos que SOLO trae el PDF de la calibracion `c`}: las cinco tablas que cuelgan de su `ref`, cada una con valores propios sembrados. Una hija leida con el `ref`
    de otra calibracion (el mismo error de «cuerpo de otro control» que DP-147 cierra, en una hija) hace faltar estas marcas y trae las de la otra."""
    return {"SistemaMedicion": [c.cp, c.ele],
            "CondicionesMedicion": [str(c.t), str(c.p), str(c.h), str(c.desplazamiento)],
            "MaximosCamaras": list(c.maximos),
            "LecturasMaximos": [c.lectura],
            "ResultadosActividad": [f"{valor}" for valor in c.actividad]}


def _pedido_ok(r):
    assert not r.errores, f"el reporte avisó de un error ({r.base}, {r.fecha}, {r.tipo}): {r.errores}"
    assert r.pdf, f"no se generó ningún PDF ({r.base}, {r.fecha}, {r.tipo})"
    return r


# ========================================================================================================================================== premisa

class TestPremisa:
    def test_los_contadores_de_una_base_nueva_colisionan_por_construccion(self, plantilla, tmp_path):
        """Sin esto la prueba no probaria nada: si la plantilla dejara de empezar en 1, la primera calibracion y la primera linealidad dejarian de compartir id."""
        ruta = str(tmp_path / "premisa.db")
        shutil.copy(plantilla, ruta)
        con = sqlite3.connect(ruta)
        try:
            id_calibracion = con.execute("INSERT INTO TipoCalibracion (user, fecha, tipo, serie, activo) VALUES ('p', '2026-01-01', 'Cambio de fuente', 'S', 1)").lastrowid
            id_linealidad = con.execute("INSERT INTO LinealidadBraquiterapia (user, fecha, activo) VALUES ('p', '2026-01-02', 1)").lastrowid
        finally:
            con.close()
        assert id_calibracion == 1 and id_linealidad == 1, "los dos contadores ya no empiezan en 1: la colision por construccion desaparecio"

    def test_la_base_completa_tiene_tres_ids_compartidos_y_la_otra_ninguno(self, bases):
        def compartidos(ruta):
            con = sqlite3.connect(ruta)
            try:
                return [i for (i,) in con.execute("SELECT t.id FROM TipoCalibracion t JOIN LinealidadBraquiterapia l ON l.id = t.id ORDER BY t.id")]
            finally:
                con.close()
        assert compartidos(bases["completa"]) == [1, 2, 3]
        assert compartidos(bases["sin_colision"]) == []
        con = sqlite3.connect(bases["completa"])
        try:
            assert [r for r in con.execute("SELECT id, activo FROM LinealidadBraquiterapia ORDER BY id")] == [(1, 1), (2, 0), (3, 1)]
        finally:
            con.close()

    def test_las_cinco_hijas_de_cada_calibracion_tienen_valores_propios_en_la_base_y_en_la_siembra(self, bases):
        """Sin esto la prueba de las hijas no probaria nada: si dos calibraciones sembraran el MISMO valor en una hija (como CondicionesMedicion antes: t, p, h y
        desplazamiento iguales en las tres), leer esa hija con el `ref` de la otra calibracion daria un PDF identico y nadie lo notaria. Se comprueba en la propia
        base sembrada, hija por hija y calibracion por calibracion, ademas de en las marcas que las pruebas buscan en el PDF."""
        for nombre in ("t", "p", "h", "desplazamiento"):
            valores = [getattr(c, nombre) for c in CALIBRACIONES.values()]
            assert len(set(valores)) == len(valores), f"CondicionesMedicion: el valor sembrado de {nombre} se repite entre calibraciones: {valores}"
        for hija in HIJAS:
            marcas = [set(_marcas_de_hijas(c)[hija]) for c in CALIBRACIONES.values()]
            repetidas = {m for i, a in enumerate(marcas) for b in marcas[i + 1:] for m in a & b}
            assert not repetidas, f"{hija}: marcas que se repiten entre calibraciones {sorted(repetidas)}"
        con = sqlite3.connect(bases["completa"])
        try:
            filas = con.execute("SELECT ref, t, p, h, desplazamiento_ini FROM CondicionesMedicion WHERE activo = 1 ORDER BY ref").fetchall()
        finally:
            con.close()
        assert filas == [(c.id, c.t, c.p, c.h, c.desplazamiento) for c in CALIBRACIONES.values()], filas
        assert len({fila[1:] for fila in filas}) == len(CALIBRACIONES), "CondicionesMedicion: dos calibraciones tienen las mismas condiciones sembradas"


# ============================================================================================================================================== 1a

# ids legibles, ASCII y unicos (nada que coincida con el nombre del archivo: `-k` de las baterias de mutaciones filtra por ellos)
_NOMBRE_DEL_ID = {"cf": "cambio_de_fuente", "cm": "control_mensual", "cr": "calibracion_redundante"}
CALIBRACION_PARAMETROS = [pytest.param(k, id=f"id{CALIBRACIONES[k].id}_{_NOMBRE_DEL_ID[k]}") for k in CALIBRACIONES]


class Test1aCadaCalibracionImprimeSuCuerpo:
    @pytest.mark.parametrize("clave", CALIBRACION_PARAMETROS)
    def test_1a_cada_calibracion_imprime_su_propio_cuerpo_y_ninguna_marca_de_linealidad(self, oficina, bases, clave):
        c = CALIBRACIONES[clave]
        r = _pedido_ok(oficina.pedir(bases["completa"], _dia(c.fecha), c.tipo))
        assert not _marcas_de_linealidad(r), (f"la calibración {c.id} ({c.tipo}) salió con el cuerpo de una LINEALIDAD (DP-147): {_marcas_de_linealidad(r)}; "
                                              f"tablas del generador: {sorted(r.claves)}")
        assert r.claves == CLAVES_DE_CALIBRACION, f"las 7 tablas de calibración, no {sorted(r.claves)}"
        assert r.user == c.usuario, f"el generador recibió el firmante {r.user!r} y no el de la calibración ({c.usuario!r})"
        propias = [marca for marcas in _marcas_de_hijas(c).values() for marca in marcas]
        for esperado in ("Tipo de calibración", "Condiciones de medición", c.serie, c.certificado, c.usuario, *propias):
            assert esperado in r.texto, f"el PDF de la calibración {c.id} no trae {esperado!r}"
        for ajena in (k for k in CALIBRACIONES if k != clave):
            o = CALIBRACIONES[ajena]
            de_otra = [marca for marcas in _marcas_de_hijas(o).values() for marca in marcas] + [o.serie, o.certificado]
            presentes = [marca for marca in de_otra if marca in r.texto]
            assert not presentes, f"el PDF de la calibración {c.id} trae datos de la {o.id}: {presentes}"

    def test_1a_el_cuerpo_de_una_calibracion_trae_las_cinco_hijas_propias(self, oficina, bases):
        """Las CINCO hijas de `TipoCalibracion` (SistemaMedicion, CondicionesMedicion, MaximosCamaras, LecturasMaximos, ResultadosActividad), cada una por su contenido y no por
        un titulo: en el PDF de cada calibracion estan las marcas de SU hija y ninguna de la misma hija de las otras dos (si una hija se leyera con el `ref` de otra calibracion,
        faltarian las propias y sobrarian las ajenas)."""
        assert set(_marcas_de_hijas(CALIBRACIONES["cm"])) == set(HIJAS) and len(HIJAS) == 5
        for clave, c in CALIBRACIONES.items():
            r = _pedido_ok(oficina.pedir(bases["completa"], _dia(c.fecha), c.tipo))
            assert not _marcas_de_linealidad(r), f"la calibración {c.id} ({c.tipo}) salió con el cuerpo de una linealidad: {_marcas_de_linealidad(r)}"
            faltan = {hija: [m for m in marcas if m not in r.texto] for hija, marcas in _marcas_de_hijas(c).items()}
            faltan = {hija: m for hija, m in faltan.items() if m}
            assert not faltan, f"hijas de la calibración {c.id} que no aparecen (o no completas) en su PDF: {faltan}"
            for otra in (k for k in CALIBRACIONES if k != clave):
                ajenas = {hija: [m for m in marcas if m in r.texto] for hija, marcas in _marcas_de_hijas(CALIBRACIONES[otra]).items()}
                ajenas = {hija: m for hija, m in ajenas.items() if m}
                assert not ajenas, f"el PDF de la calibración {c.id} trae hijas de la calibración {CALIBRACIONES[otra].id}: {ajenas}"

    def test_1a_lo_anulado_tampoco_secuestra(self, oficina, bases):
        """La linealidad 2 esta ANULADA y comparte id con el Control Mensual: la sonda de antes no filtraba `activo` y tambien lo secuestraba."""
        con = sqlite3.connect(bases["completa"])
        try:
            assert con.execute("SELECT activo FROM LinealidadBraquiterapia WHERE id = 2").fetchone() == (0,)
        finally:
            con.close()
        c = CALIBRACIONES["cm"]
        r = _pedido_ok(oficina.pedir(bases["completa"], _dia(c.fecha), c.tipo))
        assert "LIN-DOS-ANULADA" not in r.texto and not (r.claves & CLAVES_DE_LINEALIDAD), \
            f"el Control Mensual (id 2) salió como la linealidad ANULADA con su mismo id: {_marcas_de_linealidad(r)}"
        assert c.serie in r.texto


# ============================================================================================================================================== 1b

class Test1bLosLectoresDeIdentidad:
    @pytest.mark.parametrize("clave", CALIBRACION_PARAMETROS)
    def test_1b_un_pedido_de_calibracion_llama_solo_al_lector_de_TipoCalibracion_con_su_ref(self, oficina, bases, clave):
        c = CALIBRACIONES[clave]
        r = _pedido_ok(oficina.pedir(bases["completa"], _dia(c.fecha), c.tipo))
        assert r.leido == [["TipoCalibracion", c.id, True]], (f"un pedido de calibración ({c.tipo}, id {c.id}) debe leer SOLO TipoCalibracion con su ref y leyó "
                                                              f"{r.leido} (la sonda de DP-147 pregunta primero a LinealidadBraquiterapia)")

    @pytest.mark.parametrize("clave", CALIBRACION_PARAMETROS)
    def test_1b_ni_siquiera_sin_colision_un_pedido_de_calibracion_pregunta_a_la_tabla_de_linealidad(self, oficina, bases, clave):
        """HEAD sondeaba LinealidadBraquiterapia en TODO pedido de calibracion (258 de 258 en las ocho bases, c05 del plan), haya o no colision: el PDF salia bien por
        casualidad. Ahora la tabla la decide lo pedido y la otra no se consulta."""
        c = CALIBRACIONES[clave]
        r = _pedido_ok(oficina.pedir(bases["sin_colision"], _dia(c.fecha), c.tipo))
        assert r.leido == [["TipoCalibracion", c.id, True]], f"sin colisión, un pedido de calibración leyó {r.leido}"


# ============================================================================================================================================== 1c

PEDIDOS_DE_LINEALIDAD = [pytest.param("uno", "Linealidad", id="uno-Linealidad"), pytest.param("tres", "Linealidad", id="tres-Linealidad"),
                         pytest.param("uno", "Linealidad Braquiterapia", id="uno-Linealidad_Braquiterapia")]


class Test1cLosPedidosDeLinealidad:
    @pytest.mark.parametrize("clave,tipo", PEDIDOS_DE_LINEALIDAD)
    def test_1c_un_pedido_de_linealidad_imprime_su_linealidad_y_llama_solo_al_lector_de_linealidad(self, oficina, bases, clave, tipo):
        lin = LINEALIDADES[clave]
        r = _pedido_ok(oficina.pedir(bases["completa"], lin.fecha, tipo))
        assert r.leido == [["LinealidadBraquiterapia", lin.id, True]], f"un pedido de linealidad debe leer SOLO LinealidadBraquiterapia y leyó {r.leido}"
        assert r.claves == CLAVES_DE_LINEALIDAD, f"las 5 tablas de linealidad, no {sorted(r.claves)}"
        assert "Carga colectada en 60s" in r.texto and lin.marca in r.texto and r.user == "Fisica Linealidad"
        ajenas = [x for x in ("SERIE-CF", "SERIE-CM", "SERIE-CR", "Tipo de calibración", "Condiciones de medición") if x in r.texto]
        assert not ajenas, f"el PDF de la linealidad trae datos de una calibración (el secuestro al revés): {ajenas}"

    def test_1c_el_predicado_acepta_el_tipo_de_la_pagina_de_linealidad_y_el_largo(self, rm):
        """La pagina de Linealidad pide 'Linealidad' y los guiones de verificacion 'Linealidad Braquiterapia': las dos son linealidad, ningun tipo de calibracion lo es."""
        assert rm._es_reporte_de_linealidad("Linealidad") is True
        assert rm._es_reporte_de_linealidad("Linealidad Braquiterapia") is True
        for tipo in (CAMBIO, MENSUAL, REDUNDANTE, "Control Mensual", ""):
            assert rm._es_reporte_de_linealidad(tipo) is False, tipo


# ============================================================================================================================================== 1d

class Test1dMetamorfica:
    def test_1d_control_de_ruido_dos_pedidos_iguales_dan_el_mismo_pdf(self, oficina, bases):
        """Sin este piso, comparar dos bases no distingue una diferencia de contenido de una de generacion: el mismo pedido dos veces debe dar lo mismo."""
        c = CALIBRACIONES["cm"]
        a = _pedido_ok(oficina.pedir(bases["solo_calibraciones"], _dia(c.fecha), c.tipo))
        b = _pedido_ok(oficina.pedir(bases["solo_calibraciones"], _dia(c.fecha), c.tipo, fresco=True))
        assert a is not b and not _en_que_difieren(a, b), f"dos pedidos idénticos difieren en {_en_que_difieren(a, b)}"
        assert a.texto and a.palabras and a.tablas, "la comparación estaría vacía"

    @pytest.mark.parametrize("clave", CALIBRACION_PARAMETROS)
    def test_1d_un_pdf_de_calibracion_es_igual_con_y_sin_linealidades_en_la_base(self, oficina, bases, clave):
        c = CALIBRACIONES[clave]
        con = _pedido_ok(oficina.pedir(bases["completa"], _dia(c.fecha), c.tipo))
        sin = _pedido_ok(oficina.pedir(bases["solo_calibraciones"], _dia(c.fecha), c.tipo))
        assert sin.claves == CLAVES_DE_CALIBRACION and not _marcas_de_linealidad(sin), "la referencia sin linealidades no es el PDF de la calibración"
        diferencias = _en_que_difieren(con, sin)
        assert not diferencias, (f"el PDF de la calibración {c.id} CAMBIA según lo que haya en LinealidadBraquiterapia (difiere en {diferencias}); "
                                 f"con linealidades trae {_marcas_de_linealidad(con)}")

    @pytest.mark.parametrize("clave,tipo", PEDIDOS_DE_LINEALIDAD[:2])
    def test_1d_un_pdf_de_linealidad_es_igual_con_y_sin_calibraciones_en_la_base(self, oficina, bases, clave, tipo):
        lin = LINEALIDADES[clave]
        con = _pedido_ok(oficina.pedir(bases["completa"], lin.fecha, tipo))
        sin = _pedido_ok(oficina.pedir(bases["solo_linealidades"], lin.fecha, tipo))
        assert sin.claves == CLAVES_DE_LINEALIDAD, "la referencia sin calibraciones no es el PDF de la linealidad"
        diferencias = _en_que_difieren(con, sin)
        assert not diferencias, f"el PDF de la linealidad {lin.id} CAMBIA según lo que haya en TipoCalibracion (difiere en {diferencias})"


# ============================================================================================================================================== 1e

class Test1eLoQueYaEstabaBien:
    """Sobre la base SIN colisiones (linealidades 1001-1003): lo que ya funcionaba y el arreglo no puede mover."""

    @pytest.mark.parametrize("clave", CALIBRACION_PARAMETROS)
    def test_1e_sin_colision_cada_calibracion_imprime_su_cuerpo(self, oficina, bases, clave):
        c = CALIBRACIONES[clave]
        r = _pedido_ok(oficina.pedir(bases["sin_colision"], _dia(c.fecha), c.tipo))
        # (el espia de los lectores es asunto de 1b: HEAD pregunta a la tabla de linealidad aun sin colision, y el PDF que sale es el correcto)
        assert r.claves == CLAVES_DE_CALIBRACION and c.serie in r.texto and c.usuario == r.user and not _marcas_de_linealidad(r)

    def test_1e_el_respaldo_por_dia_una_redundante_en_un_dia_que_solo_tiene_un_control_mensual_imprime_el_control_mensual(self, oficina, bases):
        """P2 del plan: el respaldo «cualquier tipo del dia» de `_obtener_referencia_braquiterapia` es deliberado (test_le4) y no se toca."""
        cm = CALIBRACIONES["cm"]
        r = _pedido_ok(oficina.pedir(bases["sin_colision"], _dia(cm.fecha), REDUNDANTE))
        assert cm.serie in r.texto and r.user == cm.usuario and r.claves == CLAVES_DE_CALIBRACION
        assert not _marcas_de_linealidad(r)
        assert "Control de calidad Calibración Redundante" in r.texto, "el encabezado conserva el tipo PEDIDO (el cuerpo es el del día)"

    def test_1e_un_dia_sin_calibracion_avisa_que_no_se_encontro_control_mensual(self, oficina, bases):
        r = oficina.pedir(bases["sin_colision"], "2026-05-05", MENSUAL)
        assert not r.pdf and r.leido == []
        assert r.errores == ["No se encontró control mensual para Braquiterapia en 2026-05-05"], r.errores

    def test_1e_una_linealidad_anulada_no_se_resuelve_por_fecha(self, oficina, bases):
        """La resolucion por fecha de una linealidad ya filtraba `activo` (DA-47): pedir el dia de la ANULADA no encuentra nada."""
        r = oficina.pedir(bases["completa"], LINEALIDADES["dos"].fecha, "Linealidad")
        assert not r.pdf and r.leido == []
        assert r.errores == ["No se encontró control mensual para Braquiterapia en 2026-03-04"], r.errores


# =============================================================================================================================================== 2

@pytest.fixture(scope="module")
def copia_real(tmp_path_factory):
    """Copia de `BD_REBUILD_08_10` (con su -wal/-shm si los tiene) a un temporal. Salta si falta (HI-0); la original nunca se abre."""
    if not BD_REBUILD_08_10.exists():
        pytest.skip(f"falta la BD de referencia {BD_REBUILD_08_10.name}")
    destino = tmp_path_factory.mktemp("dp147_real") / "copia.db"
    shutil.copyfile(BD_REBUILD_08_10, destino)
    for sufijo in ("-wal", "-shm"):
        origen = Path(str(BD_REBUILD_08_10) + sufijo)
        if origen.exists():
            shutil.copyfile(origen, str(destino) + sufijo)
    # La copia se abre con el codigo de HOY, como lo hace el arranque de la app (la migracion de esquema agrega, p. ej., las columnas de B.5 a la tabla de la posicion
    # inicial, que la base del 08-10 todavia no tiene). Es sqlite3 sobre la COPIA y antes de que Qt la abra: nunca sobre la de referencia.
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(conection_mod, "ruta_base_datos", lambda: str(destino))
        previo = Conexion._instance
        Conexion._instance = None
        try:
            Conexion().con.close()
        finally:
            Conexion._instance = previo
    con = sqlite3.connect(destino)
    try:
        calibracion = con.execute("SELECT fecha, tipo, serie, activo FROM TipoCalibracion WHERE id = 14").fetchone()
        linealidad = con.execute("SELECT fecha, serie_cp, activo FROM LinealidadBraquiterapia WHERE id = 14").fetchone()
    finally:
        con.close()
    # la PREMISA de la copia real: el id 14 existe en las dos tablas (si la copia cambiara, esta prueba dejaria de probar algo)
    assert calibracion is not None and linealidad is not None, "la copia real ya no tiene el id 14 en las dos tablas"
    assert calibracion[0].startswith("2025-09-27") and calibracion[1] == CAMBIO and calibracion[3] == 1, calibracion
    assert linealidad[0].startswith("2025-12-26") and linealidad[2] == 1, linealidad
    return str(destino)


SERIE_14 = "24-05-8398-003-090425-11843-84"


class Test2CopiaRealDeLaProduccion:
    @pytest.mark.parametrize("tipo", [CAMBIO, MENSUAL, REDUNDANTE], ids=["id14_cambio_de_fuente", "id14_control_mensual", "id14_calibracion_redundante"])
    def test_2_el_27_09_2025_imprime_la_calibracion_14_en_los_tres_tipos(self, oficina, copia_real, tipo):
        r = _pedido_ok(oficina.pedir(copia_real, "2025-09-27", tipo))
        assert not _marcas_de_linealidad(r), (f"el PDF del 27-09-2025 ({tipo}) salió como el de la LINEALIDAD 14 (DP-147): {_marcas_de_linealidad(r)}; "
                                              f"tablas {sorted(r.claves)}")
        assert r.leido == [["TipoCalibracion", 14, True]], r.leido
        assert r.claves == CLAVES_DE_CALIBRACION and r.paginas == 4, (sorted(r.claves), r.paginas)
        for esperado in ("Tipo de calibración", CAMBIO, SERIE_14, "Condiciones de medición"):
            assert esperado in r.texto, esperado
        assert f"Control de calidad {tipo}" in r.texto, "el encabezado conserva el tipo pedido (P2 del plan)"

    def test_2_el_26_12_2025_la_linealidad_imprime_la_linealidad_14(self, oficina, copia_real):
        r = _pedido_ok(oficina.pedir(copia_real, "2025-12-26", "Linealidad"))
        assert r.leido == [["LinealidadBraquiterapia", 14, True]], r.leido
        assert r.claves == CLAVES_DE_LINEALIDAD and "Carga colectada en 60s" in r.texto and "A132690" in r.texto
        assert SERIE_14 not in r.texto and "Tipo de calibración" not in r.texto


# ======================================================================================================================================= tripwires

SALTAR = {".venv", ".git", "build", "dist", "__pycache__", ".pytest_cache", "node_modules"}


@pytest.fixture(scope="module")
def arboles():
    """{ruta relativa -> AST} de TODOS los .py del repo (produccion y pruebas), analizados una sola vez para los tripwires."""
    salida = {}
    for raiz, dirs, nombres in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in SALTAR]
        for nombre in nombres:
            if nombre.endswith(".py"):
                ruta = Path(raiz) / nombre
                try:
                    salida[ruta.relative_to(RAIZ).as_posix()] = ast.parse(ruta.read_text(encoding="utf-8"))
                except (SyntaxError, UnicodeDecodeError):
                    continue
    return salida


def _de_produccion(arboles):
    return [(rel, arbol) for rel, arbol in arboles.items() if not rel.startswith("tests/")]


def _funcion(arbol, nombre):
    return [f for f in ast.walk(arbol) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name == nombre]


def _nombre_llamado(n):
    return n.func.attr if isinstance(n.func, ast.Attribute) else (n.func.id if isinstance(n.func, ast.Name) else None)


# ------------------------------------------------------------------------------------------------------------------------------------------ T1

PREDICADO = "_es_reporte_de_linealidad"
LAS_TRES_DECISIONES = ("_obtener_referencia_braquiterapia", "_recopilar_datos_completos", "_procesar_datos_para_reporte")
METODOS_DE_TEXTO = {"startswith", "endswith", "find", "rfind", "index", "rindex", "count", "__contains__", "search", "match", "fullmatch", "fnmatch", "fnmatchcase"}
# Metodos con los que se CONSULTA una coleccion o un diccionario: cuenta cuando el receptor es el que trae el literal ({'Linealidad': 1}.get(tipo), TIPOS.index(tipo))
METODOS_DE_CONSULTA = {"get", "setdefault", "pop", "index", "count", "__getitem__", "__contains__"}
RAIZ_DE_LINEALIDAD = "lineal"       # la raiz de «linealidad»: tambien atrapa 'lineal' in tipo.lower(), que ninguna comparacion con la palabra entera veria


def _plegar(nodo):
    """El texto literal de un nodo con las concatenaciones y los f-strings plegados ('Lineal' + 'idad' -> 'Linealidad'; f'Linealidad {x}' -> 'Linealidad {}'); None si no es texto literal."""
    if isinstance(nodo, ast.Constant):
        return nodo.value if isinstance(nodo.value, str) else None
    if isinstance(nodo, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in nodo.values)
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Add):
        izquierda, derecha = _plegar(nodo.left), _plegar(nodo.right)
        return izquierda + derecha if izquierda is not None and derecha is not None else None
    return None


def _menciona_linealidad(nodo, constantes=frozenset()):
    """¿El nodo trae, en cualquier parte de su subarbol, texto literal con la raiz de «linealidad» (suelto, dentro de una tupla, lista, set o diccionario, en un f-string o
    partido en una concatenacion) o el nombre de una constante de modulo que lo trae? Mirar el subarbol y no solo el literal directo es lo que cierra la CLASE: la pregunta
    «¿es el reporte de linealidad?» se puede escribir de muchas formas y todas llevan el texto."""
    for n in ast.walk(nodo):
        texto = _plegar(n) if isinstance(n, (ast.Constant, ast.JoinedStr, ast.BinOp)) else None
        if texto is not None and RAIZ_DE_LINEALIDAD in texto.lower():
            return True
        if (isinstance(n, ast.Name) and n.id in constantes) or (isinstance(n, ast.Attribute) and n.attr in constantes):
            return True
    return False


def _constantes_con_el_literal(arbol):
    """Los nombres de las constantes de MODULO y de CLASE (las asignaciones directas del cuerpo del modulo o de una clase) cuyo valor trae el literal (`TIPO = 'Linealidad'`,
    `TIPOS = ('Linealidad', ...)`, una constante de clase usada como `self.TIPO`), tambien las definidas a partir de otras. No se siguen los nombres locales de una funcion
    (`datos`, `tabla`...): por ser genericos darian falsos positivos en el modulo real."""
    cuerpos = [arbol.body] + [c.body for c in ast.walk(arbol) if isinstance(c, ast.ClassDef)]
    constantes, cambio = set(), True
    while cambio:
        cambio = False
        for cuerpo in cuerpos:
            for n in cuerpo:
                if isinstance(n, ast.Assign):
                    destinos, valor = n.targets, n.value
                elif isinstance(n, ast.AnnAssign) and n.value is not None:
                    destinos, valor = [n.target], n.value
                else:
                    continue
                nombres = {d.id for d in destinos if isinstance(d, ast.Name)}
                if nombres and not nombres <= constantes and _menciona_linealidad(valor, constantes):
                    constantes |= nombres
                    cambio = True
    return constantes


def _comparaciones_con_linealidad(arbol):
    """[(funcion, linea, texto)] de cada lugar donde se PREGUNTA por el texto «linealidad»: la pregunta «¿es el reporte de linealidad?», escrita como sea. Se ven la comparacion
    (==, !=, in, not in, is...), el metodo de texto (startswith, re.search...), la consulta de un diccionario o coleccion literal (`{'Linealidad': 1}.get(t)`, `TIPOS.index(t)`,
    `{...}[t]`), el `match`/`case` y el recorrido de una coleccion literal; y en todas, el texto puede venir suelto, dentro de una tupla/lista/set/diccionario, en un f-string,
    partido en una concatenacion o a traves de una constante de modulo o de clase. NO se ven (limite declarado) los textos armados en ejecucion, las constantes importadas de otro
    archivo ni los nombres locales de una funcion.
    Tampoco son una pregunta, y no se marcan: el nombre de la tabla en un SQL, el titulo de un grafico, el valor de un diccionario ({'tipo': 'Linealidad'}) ni la CLAVE de una
    tabla del reporte (`tablas['grafico_linealidad']`)."""
    constantes = _constantes_con_el_literal(arbol)
    hallazgos = []

    def menciona(nodo):
        return _menciona_linealidad(nodo, constantes)

    class V(ast.NodeVisitor):
        def __init__(self):
            self.pila = []

        def anotar(self, n, donde=None):
            donde = n if donde is None else donde
            hallazgos.append((self.pila[-1] if self.pila else "<modulo>", donde.lineno, ast.unparse(donde)))

        def visit_FunctionDef(self, n):
            self.pila.append(n.name)
            self.generic_visit(n)
            self.pila.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Compare(self, n):
            if any(menciona(o) for o in [n.left, *n.comparators]):
                self.anotar(n)
            self.generic_visit(n)

        def visit_Call(self, n):
            if isinstance(n.func, ast.Attribute):
                if n.func.attr in METODOS_DE_TEXTO and (any(menciona(a) for a in [*n.args, *[k.value for k in n.keywords]]) or menciona(n.func.value)):
                    self.anotar(n)
                elif n.func.attr in METODOS_DE_CONSULTA and menciona(n.func.value):
                    self.anotar(n)
            self.generic_visit(n)

        def visit_Subscript(self, n):
            if menciona(n.value):               # {'Linealidad': 1}[tipo]; el indice NO cuenta: tablas['grafico_linealidad'] es una clave, no una pregunta
                self.anotar(n)
            self.generic_visit(n)

        def visit_Match(self, n):
            if any(menciona(caso.pattern) for caso in n.cases):
                self.anotar(n)
            self.generic_visit(n)

        def visit_comprehension(self, n):
            if menciona(n.iter):                # any(tipo == x for x in ('Linealidad',))
                self.anotar(n, n.iter)
            self.generic_visit(n)
    V().visit(arbol)
    return hallazgos


def _llamadas_al_predicado_con_el_tipo(funcion):
    return [n for n in ast.walk(funcion) if isinstance(n, ast.Call) and _nombre_llamado(n) == PREDICADO and len(n.args) == 1 and not n.keywords
            and isinstance(n.args[0], ast.Name) and n.args[0].id == "tipo_reporte"]


def _fallos_t1(arbol):
    """Lo que viola «una sola definicion»: comparaciones con el literal fuera del predicado, predicado repetido o ausente, y las tres decisiones que no lo llaman."""
    fallos = []
    definiciones = [f for f in arbol.body if isinstance(f, ast.FunctionDef) and f.name == PREDICADO]
    if len(definiciones) != 1:
        fallos.append(f"{PREDICADO} debe definirse exactamente una vez a nivel de módulo (hay {len(definiciones)})")
    elif [a.arg for a in definiciones[0].args.args] != ["tipo_reporte"]:
        fallos.append(f"{PREDICADO} debe recibir solo `tipo_reporte`")
    dentro = [h for h in _comparaciones_con_linealidad(arbol) if h[0] == PREDICADO]
    fuera = [h for h in _comparaciones_con_linealidad(arbol) if h[0] != PREDICADO]
    if definiciones and not dentro:
        fallos.append(f"{PREDICADO} no compara el literal de linealidad con el tipo pedido")
    for funcion, linea, texto in fuera:
        fallos.append(f"l.{linea} {funcion}: segunda definición de «es linealidad» ({texto})")
    for nombre in LAS_TRES_DECISIONES:
        encontradas = _funcion(arbol, nombre)
        if len(encontradas) != 1:
            fallos.append(f"{nombre} debe existir una vez (hay {len(encontradas)})")
        elif not _llamadas_al_predicado_con_el_tipo(encontradas[0]):
            fallos.append(f"{nombre} no llama a {PREDICADO}(tipo_reporte)")
    return fallos


def _modulo_con_las_tres_decisiones(condiciones):
    """Un modulo SINTETICO con el predicado unico y las tres decisiones; `condiciones` = {decision: condicion distinta de la llamada al predicado}."""
    def condicion(nombre):
        return condiciones.get(nombre, f"{PREDICADO}(tipo_reporte)")
    return (f"def {PREDICADO}(tipo_reporte):\n    return 'Linealidad' in tipo_reporte\n"
            "def _obtener_referencia_braquiterapia(db, fecha, tipo_reporte):\n"
            f"    if {condicion('_obtener_referencia_braquiterapia')}:\n        return 1\n    return 2\n"
            "def _recopilar_datos_completos(db, ref_id, config_tablas, maquina, tipo_reporte):\n    datos_completos = {}\n"
            f"    if {condicion('_recopilar_datos_completos')}:\n        return 1\n    return datos_completos\n"
            "def _procesar_datos_para_reporte(datos_completos, diccionario, umbrales, maquina, tipo_reporte=None):\n"
            f"    if {condicion('_procesar_datos_para_reporte')}:\n        return 1\n    return 2\n")


# Las formas en que alguien podria escribir una SEGUNDA definicion de «¿es el reporte de linealidad?» fuera del predicado (cada una, una fuente autocontenida). Las cinco primeras
# eran las que el detector ya veia; las demas, las que la revision (RP1) demostro que pasaban sin ser vistas.
SEGUNDAS_DEFINICIONES = [
    pytest.param("def f(tipo_reporte):\n    return tipo_reporte == 'Linealidad Braquiterapia'\n", id="igualdad_exacta"),
    pytest.param("def f(tipo_reporte):\n    return 'Linealidad' in tipo_reporte\n", id="pertenencia"),
    pytest.param("def f(tipo_reporte):\n    return tipo_reporte.startswith('Linealidad')\n", id="startswith"),
    pytest.param("def f(datos_completos):\n    return datos_completos.get('tipo') == 'Linealidad'\n", id="por_el_dato_leido"),
    pytest.param("def f(t):\n    return 'linealidad' not in t.lower() and t != 'LINEALIDAD'\n", id="otra_forma_de_comparar"),
    pytest.param("def f(t):\n    return t in ('Linealidad', 'Linealidad Braquiterapia')\n", id="pertenencia_a_tupla_literal"),
    pytest.param("def f(t):\n    return t not in ['Linealidad']\n", id="pertenencia_a_lista_literal"),
    pytest.param("def f(t):\n    return t in {'Linealidad'}\n", id="pertenencia_a_set_literal"),
    pytest.param("TIPO = 'Linealidad'\n\n\ndef f(t):\n    return t == TIPO\n", id="constante_de_modulo"),
    pytest.param("TIPOS = ('Linealidad', 'Linealidad Braquiterapia')\n\n\ndef f(t):\n    return t in TIPOS\n", id="tupla_de_modulo"),
    pytest.param("BASE = 'Linealidad'\nTIPOS = (BASE, 'otro')\n\n\ndef f(t):\n    return t in TIPOS\n", id="constante_definida_a_partir_de_otra"),
    pytest.param("class K:\n    TIPO = 'Linealidad'\n\n    def f(self, t):\n        return t == self.TIPO\n", id="constante_de_clase"),
    pytest.param("def f(t):\n    return t.startswith(('Linealidad',))\n", id="startswith_con_tupla"),
    pytest.param("def f(t):\n    return {'Linealidad': True}.get(t, False)\n", id="diccionario_de_despacho_con_get"),
    pytest.param("def f(t):\n    return {'Linealidad': True}[t]\n", id="diccionario_de_despacho_con_indice"),
    pytest.param("TABLA = {'Linealidad': True}\n\n\ndef f(t):\n    return TABLA.get(t, False)\n", id="diccionario_de_modulo"),
    pytest.param("TIPOS = ('Linealidad',)\n\n\ndef f(t):\n    return TIPOS.index(t)\n", id="index_sobre_tupla_de_modulo"),
    pytest.param("def f(t):\n    match t:\n        case 'Linealidad':\n            return True\n    return False\n", id="match_case"),
    pytest.param("def f(t):\n    return any(t == x for x in ('Linealidad', 'otro'))\n", id="recorrido_de_coleccion_literal"),
    pytest.param("def f(t, x):\n    return t == f'Linealidad {x}'\n", id="f_string"),
    pytest.param("def f(t):\n    return t == 'Lineal' + 'idad'\n", id="literal_partido"),
    pytest.param("def f(t):\n    return 'lineal' in t.lower()\n", id="raiz_en_minusculas"),
    pytest.param("import re\n\n\ndef f(t):\n    return bool(re.search('Linealidad', t))\n", id="expresion_regular"),
    pytest.param("def f(t):\n    return t != 'Linealidad'\n", id="desigualdad"),
]
# Lo que NO es la pregunta y el detector no puede marcar (sino inundaria de falsos positivos el modulo real, que tiene decenas de textos asi)
USOS_QUE_NO_SON_LA_PREGUNTA = [
    pytest.param("def f(query):\n    query.prepare('SELECT * FROM LinealidadBraquiterapia WHERE id = ?')\n", id="el_nombre_de_la_tabla_en_un_sql"),
    pytest.param("def f(ax):\n    ax.set_title('Linealidad de la Fuente')\n", id="el_titulo_de_un_grafico"),
    pytest.param("def f():\n    return {'tipo': 'Linealidad'}\n", id="el_valor_de_un_diccionario"),
    pytest.param("def f(tablas, valor):\n    tablas['grafico_linealidad'] = valor\n", id="la_clave_de_una_tabla_al_asignar"),
    pytest.param("def f(tablas):\n    return tablas['sistema_medicion_linealidad']\n", id="la_clave_de_una_tabla_al_leer"),
    pytest.param("def f(datos):\n    return datos.get('sistema_medicion_linealidad')\n", id="la_clave_de_una_tabla_con_get"),
    pytest.param("def f(t):\n    return t == 'Cambio de fuente' or t in ('Control Mensual', 'Calibración Redundante')\n", id="la_comparacion_con_otros_tipos"),
    pytest.param("TABLAS = ('sistema_medicion', 'condiciones_medicion')\n\n\ndef f(t):\n    return t in TABLAS\n", id="una_constante_de_modulo_sin_el_texto"),
]
# Otra regla que una de las tres decisiones podria sumar JUNTO a la llamada al predicado (lo que sobrevivia): (lo que va antes en el modulo, la regla)
OTRAS_REGLAS_JUNTO_AL_PREDICADO = [
    pytest.param("", "tipo_reporte in ('Linealidad', 'Linealidad Braquiterapia')", id="tupla"),
    pytest.param("", "tipo_reporte in ['Linealidad']", id="lista"),
    pytest.param("", "tipo_reporte in {'Linealidad'}", id="set"),
    pytest.param("TIPOS_DE_LINEALIDAD = ('Linealidad', 'Linealidad Braquiterapia')\n", "tipo_reporte in TIPOS_DE_LINEALIDAD", id="constante_de_modulo"),
    pytest.param("", "tipo_reporte.startswith(('Linealidad',))", id="startswith_con_tupla"),
    pytest.param("TABLA = {'Linealidad': True}\n", "TABLA.get(tipo_reporte, False)", id="diccionario_de_modulo"),
    pytest.param("", "{'Linealidad': True}.get(tipo_reporte, False)", id="diccionario_literal"),
    pytest.param("", "f'Linealidad {maquina}' == tipo_reporte", id="f_string"),
]


class TestT1UnaSolaDefinicion:
    def test_t1_el_literal_de_linealidad_solo_se_compara_en_la_definicion_unica_y_las_tres_decisiones_la_usan(self, arboles):
        fallos = _fallos_t1(arboles[REPORTE])
        assert not fallos, "DP-147: la pregunta «¿es el reporte de linealidad?» tiene más de una respuesta posible:\n  " + "\n  ".join(fallos)

    def test_t1_el_detector_ve_la_definicion_y_su_unica_comparacion(self, arboles):
        """No vacuidad: el detector encuentra de verdad la comparacion dentro del predicado (un detector que no ve nada pasaria siempre)."""
        dentro = [h for h in _comparaciones_con_linealidad(arboles[REPORTE]) if h[0] == PREDICADO]
        assert len(dentro) == 1 and "Linealidad" in dentro[0][2], dentro

    @pytest.mark.parametrize("fuente", SEGUNDAS_DEFINICIONES)
    def test_t1_el_detector_discrimina_una_segunda_definicion(self, fuente):
        """Cada forma de escribir la pregunta «¿es el reporte de linealidad?» fuera del predicado debe ser vista: no solo la igualdad con el literal directo (RP1 de la
        revision: una tupla, una lista, un set, una constante de modulo, un diccionario de despacho, un match, un f-string o un literal partido pasaban sin ser vistos)."""
        assert _comparaciones_con_linealidad(ast.parse(fuente)), "no vio la segunda definición"

    @pytest.mark.parametrize("fuente", USOS_QUE_NO_SON_LA_PREGUNTA)
    def test_t1_el_detector_no_marca_lo_que_no_es_la_pregunta(self, fuente):
        """El nombre de la tabla en SQL, el titulo de un grafico, el valor de un diccionario, la clave de una tabla del reporte y la comparacion con otro tipo no son una pregunta
        sobre el tipo pedido: un detector que ve todas las formas tambien tiene que callar ante estas, o inundaria de falsos positivos el modulo de produccion."""
        assert _comparaciones_con_linealidad(ast.parse(fuente)) == []

    def test_t1_las_constantes_de_modulo_y_de_clase_se_siguen_por_nombre_y_encadenadas(self):
        arbol = ast.parse("A = ('Linealidad',)\nB = A + ('x',)\nC = 5\nD: tuple = ('otro',)\nE = 'solo texto'\n"
                          "class K:\n    F = 'Linealidad'\n    G = (F, 'x')\n    H = 3\n    def m(self):\n        local = 'Linealidad'\n")
        assert _constantes_con_el_literal(arbol) == {"A", "B", "F", "G"}       # `local` (un nombre de funcion) no se sigue

    @pytest.mark.parametrize("fuente", SEGUNDAS_DEFINICIONES)
    def test_t1_una_cuarta_funcion_con_la_pregunta_escrita_de_otra_forma_hace_caer_el_tripwire(self, fuente):
        """El tripwire completo (no solo el detector): un modulo bien hecho al que se le suma, en una cuarta funcion, la pregunta escrita de cualquiera de esas formas."""
        fallos = _fallos_t1(ast.parse(_modulo_con_las_tres_decisiones({}) + "\n" + fuente))
        assert any("segunda definición" in x for x in fallos), fallos

    @pytest.mark.parametrize("decision", LAS_TRES_DECISIONES)
    @pytest.mark.parametrize("antes,regla", OTRAS_REGLAS_JUNTO_AL_PREDICADO)
    def test_t1_una_decision_que_conserva_el_predicado_y_le_suma_otra_regla_hace_caer_el_tripwire(self, decision, antes, regla):
        """La mutacion que sobrevivia (MUT1 de la revision): la decision SIGUE llamando al predicado y ademas pregunta por una tupla. Es equivalente en conducta, asi que solo este
        tripwire puede verla; lo que garantiza es que la pregunta tiene UNA definicion, no solo que las tres decisiones llamen a esa."""
        fallos = _fallos_t1(ast.parse(antes + _modulo_con_las_tres_decisiones({decision: f"{PREDICADO}(tipo_reporte) or {regla}"})))
        assert any("segunda definición" in x for x in fallos), fallos

    def test_t1_el_modulo_sintetico_bien_hecho_pasa(self):
        assert _fallos_t1(ast.parse(_modulo_con_las_tres_decisiones({}))) == []

    @pytest.mark.parametrize("decision", LAS_TRES_DECISIONES)
    def test_t1_una_decision_que_vuelve_a_su_propia_regla_hace_caer_el_tripwire(self, decision):
        """Cada una de las tres decisiones, reescrita con la regla suelta de antes, debe ser vista (en un modulo sintetico: no depende del texto de produccion)."""
        suelta = "tipo_reporte == 'Linealidad Braquiterapia' or 'Linealidad' in tipo_reporte"
        fallos = _fallos_t1(ast.parse(_modulo_con_las_tres_decisiones({decision: suelta})))
        assert any("segunda definición" in x for x in fallos) and any(f"{decision} no llama" in x for x in fallos), fallos

    @pytest.mark.parametrize("decision", LAS_TRES_DECISIONES)
    def test_t1_una_decision_que_pregunta_por_el_dato_en_vez_del_tipo_hace_caer_el_tripwire(self, decision):
        fallos = _fallos_t1(ast.parse(_modulo_con_las_tres_decisiones({decision: "datos_completos.get('tipo') == 'Linealidad'"})))
        assert any(f"{decision} no llama" in x for x in fallos), fallos

    def test_t1_el_predicado_repetido_o_con_otra_firma_hace_caer_el_tripwire(self):
        repetido = _modulo_con_las_tres_decisiones({}) + "\ndef _es_reporte_de_linealidad(tipo_reporte):\n    return 'Linealidad' in tipo_reporte\n"
        assert any("exactamente una vez" in x for x in _fallos_t1(ast.parse(repetido)))
        otra_firma = _modulo_con_las_tres_decisiones({}).replace("def _es_reporte_de_linealidad(tipo_reporte):", "def _es_reporte_de_linealidad(tipo_reporte, y=None):")
        assert any("solo `tipo_reporte`" in x for x in _fallos_t1(ast.parse(otra_firma)))
        sin_predicado = _modulo_con_las_tres_decisiones({}).replace("def _es_reporte_de_linealidad(tipo_reporte):\n    return 'Linealidad' in tipo_reporte\n", "")
        assert any("exactamente una vez" in x for x in _fallos_t1(ast.parse(sin_predicado)))


# ------------------------------------------------------------------------------------------------------------------------------------------ T2

RAICES = {"controles", "TipoCalibracion", "LinealidadBraquiterapia", "aceleradorlineal_600", "aceleradorlineal_ix", "halcyon", "braqui", "pruebas"}
RE_TABLA = re.compile(r'\b(?:FROM|JOIN|UPDATE|INTO)\s+["`\[]?([A-Za-z_ñ][\wñ]*|\{[^}]+\})', re.I)
RE_ID = re.compile(r'\b(?:\w+\.)?"?(id|ref|id_sesion|id_prueba)"?\s*=\s*(\?|:\w+|\{)', re.I)
LLAMADAS_SQL = {"execute", "prepare", "exec_", "exec", "read_sql", "read_sql_query", "executemany"}
# Las funciones de PRODUCCION que pueden llamar a lectores de identidad de DOS o mas raices, con su motivo. Una funcion nueva que lo haga tiene que declararse
# aqui, y en ella cada par de lectores vive en ramas excluyentes de un `if` sobre lo PEDIDO (la maquina o el tipo de reporte), nunca sobre el dato leido.
PERMITIDAS = {(REPORTE, "_recopilar_datos_completos"): "elige la raíz por `maquina` (controles o braquiterapia) y, en braquiterapia, por el tipo PEDIDO "
                                                       "(`_es_reporte_de_linealidad`), nunca por el id"}
GUARDAS = {PREDICADO}
LO_PEDIDO = {"maquina", "tipo_reporte"}      # los nombres que traen lo que se PIDIO (no un dato leido de la BD)


def _texto_sql(nodo):
    """El texto de un literal o f-string (las partes interpoladas como {expr})."""
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value
    if isinstance(nodo, ast.JoinedStr):
        return "".join(str(v.value) if isinstance(v, ast.Constant) else "{" + ast.unparse(v.value) + "}" for v in nodo.values)
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Add):
        a, b = _texto_sql(nodo.left), _texto_sql(nodo.right)
        if a is not None or b is not None:
            return (a or "{?}") + (b or "{?}")
    return None


class _LectoresSql(ast.NodeVisitor):
    """Las lecturas SQL por id/ref con parametro de una funcion: [(tablas, columnas de id)]."""

    def __init__(self):
        self.hallazgos = []

    def _registrar(self, sql):
        if not sql or not re.search(r"\b(SELECT|UPDATE|DELETE)\b", sql, re.I):
            return
        ids = RE_ID.findall(sql)
        if ids:
            self.hallazgos.append((RE_TABLA.findall(sql), sorted({i[0].lower() for i in ids})))

    def visit_Call(self, n):
        if _nombre_llamado(n) in LLAMADAS_SQL and n.args:
            self._registrar(_texto_sql(n.args[0]))
        self.generic_visit(n)

    def visit_Assign(self, n):
        sql = _texto_sql(n.value)
        if sql and re.search(r"\bSELECT\b", sql, re.I):
            self._registrar(sql)
        self.generic_visit(n)


def _funciones_de(arbol):
    """[(clase o None, funcion)]: todas las funciones y metodos de un archivo, cada una con la clase en la que esta definida."""
    salida = []

    def recorrer(nodo, clase):
        for hijo in ast.iter_child_nodes(nodo):
            if isinstance(hijo, ast.ClassDef):
                recorrer(hijo, hijo.name)
                continue
            if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                salida.append((clase, hijo))
            recorrer(hijo, clase)
    recorrer(arbol, None)
    return salida


def _raices_propias(funcion):
    """Las raices de QC que una funcion lee por `id = ?` con SQL escrito en ella misma."""
    v = _LectoresSql()
    v.visit(funcion)
    return {t for tablas, columnas in v.hallazgos for t in tablas if t in RAICES and "id" in columnas}


def _lectores_de_identidad(arboles_de_produccion):
    """{nombre de funcion -> raices de QC que lee por `id = ?`}: el «lector de identidad» de una raiz, el que tiene el SQL (sus envoltorios se siguen en `_censo_de_lectores`)."""
    lectores = {}
    for _, arbol in arboles_de_produccion:
        for f in ast.walk(arbol):
            if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                raices = _raices_propias(f)
                if raices:
                    lectores.setdefault(f.name, set()).update(raices)
    return lectores


def _destino_en_el_mismo_archivo(llamada, rel, clase):
    """La clave (archivo, clase, funcion) a la que apunta una llamada del MISMO archivo: `f(...)` -> la funcion de modulo `f`; `self.f(...)` -> el metodo `f` de la misma clase."""
    if isinstance(llamada.func, ast.Name):
        return (rel, None, llamada.func.id)
    if isinstance(llamada.func, ast.Attribute) and isinstance(llamada.func.value, ast.Name) and llamada.func.value.id in ("self", "cls"):
        return (rel, clase, llamada.func.attr)
    return None


def _censo_de_lectores(arboles_de_produccion):
    """(lectores, total, llamadas_a_lectores, propias). `lectores` = {nombre -> raices por SQL propio}, de cualquier archivo. `total` = {(archivo, clase, funcion) -> raices que la
    funcion lee por id}: su SQL propio, los lectores a los que llama por nombre y las raices de las funciones del MISMO archivo a las que llama (una funcion de modulo por su
    nombre, un metodo por `self.`), siguiendo los envoltorios hasta el punto fijo: una sonda con uno o varios niveles de indireccion lee las mismas raices que sin ella (RP2).
    Las funciones declaradas en PERMITIDAS no pasan sus raices a quien las llama (deciden por lo PEDIDO y esta prueba vigila que lo hagan): sin ese corte, cada funcion que las
    llame, hasta `reporte_mensual`, pareceria una sonda. LIMITE declarado: un envoltorio que vive en OTRO archivo no se sigue (seguir las llamadas entre archivos por nombre
    marca como sondas, medido, decenas de funciones de la interfaz que se llaman igual). `llamadas_a_lectores` = {clave -> [(llamada, raices que lee esa llamada)]}; `propias` =
    {clave -> raices por su SQL propio}."""
    arboles_de_produccion = list(arboles_de_produccion)
    lectores = _lectores_de_identidad(arboles_de_produccion)
    llamadas_de, propias = {}, {}
    for rel, arbol in arboles_de_produccion:
        for clase, f in _funciones_de(arbol):
            clave = (rel, clase, f.name)             # dos definiciones con la misma clave (un getter y un setter, un `if/else` de definiciones) se funden en una
            llamadas_de.setdefault(clave, []).extend((n, _destino_en_el_mismo_archivo(n, rel, clase)) for n in ast.walk(f) if isinstance(n, ast.Call))
            propias.setdefault(clave, set()).update(_raices_propias(f))
    total = {clave: set(raices) for clave, raices in propias.items()}

    def raices_de(llamada, destino):
        raices = set(lectores.get(_nombre_llamado(llamada), ()))
        if destino in total and (destino[0], destino[2]) not in PERMITIDAS:
            raices |= total[destino]
        return raices

    cambio = True
    while cambio:
        cambio = False
        for clave, llamadas in llamadas_de.items():
            nuevas = set(propias[clave])
            for llamada, destino in llamadas:
                if destino != clave:
                    nuevas |= raices_de(llamada, destino)
            if nuevas != total[clave]:
                total[clave] = nuevas
                cambio = True
    llamadas_a_lectores = {clave: [(n, r) for n, destino in llamadas if (r := raices_de(n, destino))] for clave, llamadas in llamadas_de.items()}
    return lectores, total, llamadas_a_lectores, propias


def _es_literal(nodo):
    return isinstance(nodo, ast.Constant) or (isinstance(nodo, (ast.Tuple, ast.List, ast.Set)) and all(isinstance(e, ast.Constant) for e in nodo.elts))


def _es_guarda(test):
    """El test de un `if` es una GUARDA solo si TODAS sus hojas preguntan por lo PEDIDO -la maquina o el tipo de reporte, contra literales o a traves del predicado- y ninguna por un
    dato leido o por un lector: `predicado(tipo) or lector(id)` NO es una guarda aunque contenga la llamada al predicado (RP2b: la sonda reintroducida dentro de la guarda). Que
    la pregunta por el tipo tenga UNA sola definicion no lo vigila esta prueba sino T1: aqui basta con que la eleccion sea por lo pedido y no por el dato."""
    if isinstance(test, ast.BoolOp):
        return all(_es_guarda(v) for v in test.values)
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return _es_guarda(test.operand)
    if isinstance(test, ast.Call):
        if _nombre_llamado(test) in GUARDAS:
            return not test.keywords and all(isinstance(a, ast.Name) and a.id in LO_PEDIDO for a in test.args)
        f = test.func           # un metodo de texto sobre lo pedido, con literales: `tipo_reporte.startswith(('x',))`
        return isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in LO_PEDIDO and not test.keywords and all(_es_literal(a) for a in test.args)
    if isinstance(test, ast.Compare):
        return isinstance(test.left, ast.Name) and test.left.id in LO_PEDIDO and all(_es_literal(c) for c in test.comparators)
    return False


def _revisar_la_clase(arboles_de_produccion):
    """(lectores, fallos, multiraiz). Falla toda funcion que lee por id de dos o mas raices (con su SQL, con los lectores a los que llama o a traves de sus envoltorios) y no esta
    declarada, y en la declarada: todo `if` (o ternario, o `while`) que pregunta por un lector o por su RESULTADO (la sonda) y todo par de lectores de raices distintas que no
    vive en ramas excluyentes de un `if` cuyo test es SOLO lo pedido (`_es_guarda`)."""
    arboles_de_produccion = list(arboles_de_produccion)
    lectores, total, llamadas_a_lectores, _ = _censo_de_lectores(arboles_de_produccion)
    fallos, multiraiz = [], set()
    for rel, arbol in arboles_de_produccion:
        for clase, f in _funciones_de(arbol):
            clave = (rel, clase, f.name)
            raices = total[clave]
            if len(raices) < 2:
                continue
            multiraiz.add((rel, f.name))
            if (rel, f.name) not in PERMITIDAS:
                fallos.append(f"{rel}::{f.name} lee por id de {sorted(raices)} (con su SQL, con lectores o a través de envoltorios) y no está declarada con su motivo")
                continue
            dentro = set(ast.walk(f))
            llamadas = [(n, r) for n, r in llamadas_a_lectores[clave] if n in dentro]       # solo las de ESTA definicion
            lecturas = {n for n, _ in llamadas}
            # (a) ningun `if` pregunta por un lector ni por su RESULTADO (el patron sonda: `datos = lector(id); if datos:` o `if predicado or lector(id):`)
            resultado_de_lector = {t.id for n in ast.walk(f) if isinstance(n, ast.Assign) and any(x in lecturas for x in ast.walk(n.value))
                                   for t in n.targets if isinstance(t, ast.Name)}
            for n in ast.walk(f):
                if isinstance(n, (ast.If, ast.IfExp, ast.While)) and any((isinstance(x, ast.Name) and x.id in resultado_de_lector) or x in lecturas for x in ast.walk(n.test)):
                    fallos.append(f"{rel}::{f.name} l.{n.lineno}: el `if` pregunta por el RESULTADO de un lector (sonda): {ast.unparse(n.test)}")
            # (b) cada PAR de lectores de raices distintas vive en ramas EXCLUYENTES de un `if` sobre lo PEDIDO, nunca sobre un dato
            padres = {}
            for p in ast.walk(f):
                for h in ast.iter_child_nodes(p):
                    padres[h] = p

            def camino(nodo):
                salida, x = [], nodo
                while x in padres:
                    p = padres[x]
                    if isinstance(p, ast.If):
                        salida.append((p, "body" if x in p.body else ("orelse" if x in p.orelse else "test")))
                    x = p
                return list(reversed(salida))

            for i, (c1, r1) in enumerate(llamadas):
                for c2, r2 in llamadas[i + 1:]:
                    if r1 == r2:
                        continue
                    k1, k2 = camino(c1), camino(c2)
                    if not any(a[0] is b[0] and a[1] != b[1] and _es_guarda(a[0].test) for a, b in zip(k1, k2)):
                        fallos.append(f"{rel}::{f.name}: {_nombre_llamado(c1)} (l.{c1.lineno}) y {_nombre_llamado(c2)} (l.{c2.lineno}) leen raíces distintas y no están en "
                                      "ramas excluyentes de un `if` sobre la máquina o el tipo pedido")
    return lectores, fallos, multiraiz


# Modulos SINTETICOS (autocontenidos: no dependen del texto de produccion) para probar que el tripwire de la clase discrimina
_LECTORES_SINTETICOS = '''
def _obtener_datos_linealidad_braquiterapia(db, ref_id):
    query = QSqlQuery(db)
    query.prepare("SELECT * FROM LinealidadBraquiterapia WHERE id = ?")
    return query
def _obtener_datos_tabla_principal_braquiterapia(db, ref_id):
    query = QSqlQuery(db)
    query.prepare("SELECT * FROM TipoCalibracion WHERE id = ?")
    return query
def _obtener_datos_tabla_principal(db, ref_id):
    query = QSqlQuery(db)
    query.prepare("SELECT * FROM controles WHERE id = ?")
    return query
'''
_SONDA_DE_HEAD = '''
def _recopilar_datos_completos(db, ref_id, config_tablas, maquina):
    datos_completos = {}
    if maquina == 'Braquiterapia':
        datos_linealidad = _obtener_datos_linealidad_braquiterapia(db, ref_id)
        if datos_linealidad:
            datos_completos.update(datos_linealidad)
            return datos_completos
        else:
            datos_principal = _obtener_datos_tabla_principal_braquiterapia(db, ref_id)
    else:
        datos_principal = _obtener_datos_tabla_principal(db, ref_id)
    datos_completos.update(datos_principal)
    return datos_completos
'''
_POR_EL_TIPO_PEDIDO = '''
def _recopilar_datos_completos(db, ref_id, config_tablas, maquina, tipo_reporte):
    datos_completos = {}
    if maquina == 'Braquiterapia':
        if _es_reporte_de_linealidad(tipo_reporte):
            datos_linealidad = _obtener_datos_linealidad_braquiterapia(db, ref_id)
            datos_completos.update(datos_linealidad)
            return datos_completos
        else:
            datos_principal = _obtener_datos_tabla_principal_braquiterapia(db, ref_id)
    else:
        datos_principal = _obtener_datos_tabla_principal(db, ref_id)
    datos_completos.update(datos_principal)
    return datos_completos
'''
_SONDA_CON_OR = _POR_EL_TIPO_PEDIDO.replace(
    "        if _es_reporte_de_linealidad(tipo_reporte):\n            datos_linealidad = _obtener_datos_linealidad_braquiterapia(db, ref_id)",
    "        if True:\n            datos_linealidad = _obtener_datos_linealidad_braquiterapia(db, ref_id) or _obtener_datos_tabla_principal_braquiterapia(db, ref_id)")
_SONDA_EN_OTRA_FUNCION = _POR_EL_TIPO_PEDIDO + '''
def _datos_de_un_ref_cualquiera(db, ref_id):
    return _obtener_datos_linealidad_braquiterapia(db, ref_id) or _obtener_datos_tabla_principal_braquiterapia(db, ref_id)
'''
_SONDA_SOBRE_LA_MAQUINA_Y_EL_DATO = _POR_EL_TIPO_PEDIDO.replace(
    "        if _es_reporte_de_linealidad(tipo_reporte):", "        if _obtener_datos_linealidad_braquiterapia(db, ref_id) is not None:")
# RP2b: la sonda reintroducida DENTRO de la guarda, con la llamada al predicado presente (con `or` y con `and not`)
_SONDA_DENTRO_DE_LA_GUARDA_CON_OR = _POR_EL_TIPO_PEDIDO.replace(
    "        if _es_reporte_de_linealidad(tipo_reporte):", "        if _es_reporte_de_linealidad(tipo_reporte) or _obtener_datos_linealidad_braquiterapia(db, ref_id):")
_SONDA_DENTRO_DE_LA_GUARDA_CON_AND_NOT = _POR_EL_TIPO_PEDIDO.replace(
    "        if _es_reporte_de_linealidad(tipo_reporte):", "        if _es_reporte_de_linealidad(tipo_reporte) and not _obtener_datos_tabla_principal_braquiterapia(db, ref_id):")
# RP2a: la sonda detras de envoltorios que no contienen SQL (uno y dos niveles, metodos de una clase) o con el SQL de dos raices escrito en una sola funcion
_ENVOLTORIOS = '''
def _lin_por_id(db, ref_id):
    return _obtener_datos_linealidad_braquiterapia(db, ref_id)
def _cal_por_id(db, ref_id):
    return _obtener_datos_tabla_principal_braquiterapia(db, ref_id)
'''
_SONDA_CON_ENVOLTORIOS = _POR_EL_TIPO_PEDIDO + _ENVOLTORIOS + '''
def _datos_de_un_ref_cualquiera(db, ref_id):
    return _lin_por_id(db, ref_id) or _cal_por_id(db, ref_id)
'''
_SONDA_CON_ENVOLTORIOS_DE_DOS_NIVELES = _POR_EL_TIPO_PEDIDO + '''
def _lin_0(db, ref_id):
    return _obtener_datos_linealidad_braquiterapia(db, ref_id)
def _lin(db, ref_id):
    return _lin_0(db, ref_id)
def _cal_0(db, ref_id):
    return _obtener_datos_tabla_principal_braquiterapia(db, ref_id)
def _cal(db, ref_id):
    return _cal_0(db, ref_id)
def _datos_de_un_ref_cualquiera(db, ref_id):
    return _lin(db, ref_id) or _cal(db, ref_id)
'''
_SONDA_CON_METODOS_DE_UNA_CLASE = _POR_EL_TIPO_PEDIDO + '''
class Lector:
    def _lin(self, db, ref_id):
        return _obtener_datos_linealidad_braquiterapia(db, ref_id)
    def _cal(self, db, ref_id):
        return _obtener_datos_tabla_principal_braquiterapia(db, ref_id)
    def datos(self, db, ref_id):
        return self._lin(db, ref_id) or self._cal(db, ref_id)
'''
_SONDA_CON_EL_SQL_DE_DOS_RAICES_EN_UNA_FUNCION = _POR_EL_TIPO_PEDIDO + '''
def _sonda_en_linea(db, ref_id):
    query = QSqlQuery(db)
    query.prepare("SELECT * FROM LinealidadBraquiterapia WHERE id = ?")
    if query.exec():
        return query
    query.prepare("SELECT * FROM TipoCalibracion WHERE id = ?")
    return query
'''
# La forma CORRECTA escrita con envoltorios (la tabla la sigue decidiendo lo pedido): el detector no puede castigarla; y la misma con los dos envoltorios en la MISMA rama, que si
_POR_EL_TIPO_PEDIDO_CON_ENVOLTORIOS = _ENVOLTORIOS + '''
def _recopilar_datos_completos(db, ref_id, config_tablas, maquina, tipo_reporte):
    datos_completos = {}
    if maquina == 'Braquiterapia':
        if _es_reporte_de_linealidad(tipo_reporte):
            datos_principal = _lin_por_id(db, ref_id)
        else:
            datos_principal = _cal_por_id(db, ref_id)
    else:
        datos_principal = _obtener_datos_tabla_principal(db, ref_id)
    datos_completos.update(datos_principal)
    return datos_completos
'''
_CON_ENVOLTORIOS_EN_LA_MISMA_RAMA = _POR_EL_TIPO_PEDIDO_CON_ENVOLTORIOS.replace(
    "        else:\n            datos_principal = _cal_por_id(db, ref_id)", "        else:\n            datos_principal = _lin_por_id(db, ref_id) or _cal_por_id(db, ref_id)")
_QUIEN_LLAMA_A_LA_DECLARADA = '''
def reporte_mensual(self, fecha, maquina, tipo_reporte):
    datos_completos = _recopilar_datos_completos(None, 1, {}, maquina, tipo_reporte)
    return _obtener_datos_tabla_principal(None, 1), datos_completos
'''


def _sintetico(fuente):
    return [(REPORTE, ast.parse(_LECTORES_SINTETICOS + fuente))]


class TestT2LaClase:
    def test_t2_en_produccion_ninguna_funcion_adivina_la_tabla_por_el_dato(self, arboles):
        """Un id nunca elige su tabla: la unica funcion que llama a lectores de identidad de dos raices elige entre ellos por lo PEDIDO."""
        _, fallos, _ = _revisar_la_clase(_de_produccion(arboles))
        assert not fallos, "DP-147 (la clase): una función elige la tabla por el dato y no por lo pedido:\n  " + "\n  ".join(fallos)

    def test_t2_el_detector_ve_los_lectores_y_la_declaracion_sigue_siendo_necesaria(self, arboles):
        """No vacuidad: encuentra los tres lectores de la recopilacion y la unica funcion declarada llama de verdad a dos o mas raices (si no, la declaracion sobra)."""
        lectores, _, multiraiz = _revisar_la_clase(_de_produccion(arboles))
        assert lectores.get("_obtener_datos_linealidad_braquiterapia") == {"LinealidadBraquiterapia"}
        assert lectores.get("_obtener_datos_tabla_principal_braquiterapia") == {"TipoCalibracion"}
        assert lectores.get("_obtener_datos_tabla_principal") == {"controles"}
        assert multiraiz == set(PERMITIDAS), f"funciones que llaman a lectores de dos raíces: {sorted(multiraiz)}; declaradas: {sorted(PERMITIDAS)}"

    def test_t2_el_detector_acepta_la_forma_por_el_tipo_pedido(self):
        _, fallos, multiraiz = _revisar_la_clase(_sintetico(_POR_EL_TIPO_PEDIDO))
        assert fallos == [] and multiraiz == set(PERMITIDAS)

    def test_t2_el_detector_discrimina_la_sonda_de_head(self):
        """La forma de antes (`datos = lector(id); if datos:`) cae por las dos razones: pregunta por el resultado y los lectores no estan en ramas excluyentes."""
        _, fallos, _ = _revisar_la_clase(_sintetico(_SONDA_DE_HEAD))
        assert any("RESULTADO de un lector" in x for x in fallos), fallos
        assert any("no están en ramas excluyentes" in x for x in fallos), fallos

    def test_t2_el_detector_discrimina_una_sonda_en_otra_funcion(self):
        _, fallos, _ = _revisar_la_clase(_sintetico(_SONDA_EN_OTRA_FUNCION))
        assert any("_datos_de_un_ref_cualquiera" in x and "no está declarada" in x for x in fallos), fallos

    def test_t2_el_detector_discrimina_una_sonda_escrita_con_or(self):
        _, fallos, _ = _revisar_la_clase(_sintetico(_SONDA_CON_OR))
        assert any("no están en ramas excluyentes" in x for x in fallos), fallos

    def test_t2_el_detector_discrimina_un_if_sobre_el_dato_aunque_los_lectores_esten_en_ramas_distintas(self):
        """Ramas distintas de un `if` que pregunta por un DATO (no por lo pedido) tampoco cuentan como excluyentes."""
        _, fallos, _ = _revisar_la_clase(_sintetico(_SONDA_SOBRE_LA_MAQUINA_Y_EL_DATO))
        assert any("no están en ramas excluyentes" in x for x in fallos), fallos

    def test_t2_una_funcion_declarada_en_otro_archivo_no_hereda_el_permiso(self):
        """La declaracion es por (archivo, funcion): la misma forma correcta en otro archivo, sin declarar, cae."""
        arboles_ = [("models/PDF/Otro/otro.py", ast.parse(_LECTORES_SINTETICOS + _POR_EL_TIPO_PEDIDO))]
        _, fallos, _ = _revisar_la_clase(arboles_)
        assert any("no está declarada" in x for x in fallos), fallos

    @pytest.mark.parametrize("fuente,llamada", [
        pytest.param(_SONDA_DENTRO_DE_LA_GUARDA_CON_OR, "or", id="con_or"),
        pytest.param(_SONDA_DENTRO_DE_LA_GUARDA_CON_AND_NOT, "and not", id="con_and_not"),
    ])
    def test_t2_el_detector_discrimina_una_sonda_dentro_de_la_guarda_con_el_predicado_presente(self, fuente, llamada):
        """RP2b: `if predicado(tipo) or lector(id):` conserva la llamada al predicado en el test del `if` y antes pasaba por guarda. Una guarda es SOLO lo pedido: si el test
        trae ademas un lector, el `if` pregunta por el dato y los dos lectores ya no estan en ramas excluyentes de una guarda."""
        _, fallos, _ = _revisar_la_clase(_sintetico(fuente))
        assert any("RESULTADO de un lector" in x for x in fallos), (llamada, fallos)
        assert any("no están en ramas excluyentes" in x for x in fallos), (llamada, fallos)

    def test_t2_el_detector_acepta_una_guarda_que_solo_pregunta_por_lo_pedido_aunque_no_use_el_predicado(self):
        """Reparto de tareas: T2 vigila que la tabla se elija por lo PEDIDO y no por el dato; que la pregunta por el tipo tenga una sola definicion es de T1. Una guarda sobre el tipo
        pedido escrita de otra forma (`tipo_reporte.startswith(...)`, una igualdad con `tipo_reporte`) es por lo pedido: T2 la acepta y T1 la ve."""
        for condicion in ("tipo_reporte.startswith(('Linealidad',))", "tipo_reporte == 'Linealidad'", "_es_reporte_de_linealidad(tipo_reporte) or tipo_reporte.startswith('Lin')"):
            fuente = _POR_EL_TIPO_PEDIDO.replace("        if _es_reporte_de_linealidad(tipo_reporte):", f"        if {condicion}:")
            assert fuente != _POR_EL_TIPO_PEDIDO
            _, fallos, multiraiz = _revisar_la_clase(_sintetico(fuente))
            assert fallos == [] and multiraiz == set(PERMITIDAS), (condicion, fallos)

    def test_t2_el_detector_discrimina_una_guarda_que_mezcla_lo_pedido_con_un_dato_leido(self):
        """La misma guarda por lo pedido, pero con una hoja que pregunta por un DATO (`datos_completos.get('tipo')`, como la regla de HEAD): ya no es una guarda."""
        fuente = _POR_EL_TIPO_PEDIDO.replace("        if _es_reporte_de_linealidad(tipo_reporte):",
                                             "        if tipo_reporte == 'Linealidad Braquiterapia' or datos_completos.get('tipo') == 'Linealidad':")
        _, fallos, _ = _revisar_la_clase(_sintetico(fuente))
        assert any("no están en ramas excluyentes" in x for x in fallos), fallos

    @pytest.mark.parametrize("fuente", [
        pytest.param(_SONDA_CON_ENVOLTORIOS, id="envoltorios_de_un_nivel"),
        pytest.param(_SONDA_CON_ENVOLTORIOS_DE_DOS_NIVELES, id="envoltorios_de_dos_niveles"),
        pytest.param(_SONDA_CON_METODOS_DE_UNA_CLASE, id="metodos_de_una_clase"),
        pytest.param(_SONDA_CON_EL_SQL_DE_DOS_RAICES_EN_UNA_FUNCION, id="sql_de_dos_raices_en_una_funcion"),
    ])
    def test_t2_el_detector_discrimina_una_sonda_detras_de_envoltorios_o_con_el_sql_en_linea(self, fuente):
        """RP2a: una sonda con envoltorios que no contienen SQL (los lectores se llaman a traves de otras funciones del mismo archivo, uno o dos niveles, o metodos de una clase) o
        con el SQL de dos raices escrito en una sola funcion lee las mismas raices que la directa y tiene que caer igual: una funcion NO declarada que lee de dos raices."""
        _, fallos, multiraiz = _revisar_la_clase(_sintetico(fuente))
        assert any("no está declarada" in x for x in fallos), fallos
        assert len(multiraiz) == 2 and (REPORTE, "_recopilar_datos_completos") in multiraiz, multiraiz

    def test_t2_el_detector_acepta_la_forma_por_el_tipo_pedido_escrita_con_envoltorios(self):
        """No castiga la forma correcta por usar envoltorios: la funcion declarada que llega a los lectores a traves de ellos, uno por rama de un `if` sobre lo pedido, pasa."""
        _, fallos, multiraiz = _revisar_la_clase(_sintetico(_POR_EL_TIPO_PEDIDO_CON_ENVOLTORIOS))
        assert fallos == [] and multiraiz == set(PERMITIDAS), (fallos, multiraiz)

    def test_t2_el_detector_discrimina_los_envoltorios_de_la_funcion_declarada_en_la_misma_rama(self):
        _, fallos, _ = _revisar_la_clase(_sintetico(_CON_ENVOLTORIOS_EN_LA_MISMA_RAMA))
        assert any("no están en ramas excluyentes" in x for x in fallos), fallos

    def test_t2_quien_llama_a_la_funcion_declarada_no_hereda_sus_raices(self):
        """Sin el corte en las funciones declaradas cada funcion que las llame (hasta `reporte_mensual`) leeria de tres raices y pareceria una sonda."""
        _, fallos, multiraiz = _revisar_la_clase(_sintetico(_POR_EL_TIPO_PEDIDO + _QUIEN_LLAMA_A_LA_DECLARADA))
        assert fallos == [] and multiraiz == set(PERMITIDAS), (fallos, multiraiz)

    def test_t2_el_censo_sigue_los_envoltorios_de_verdad_tambien_en_produccion(self, arboles):
        """No vacuidad de la propagacion: en el arbol real hay funciones que llegan a un lector solo a traves de otras (sin SQL propio). Si el censo no siguiera ninguna, la
        deteccion de envoltorios estaria rota y la prueba de arriba pasaria en vacio."""
        _, total, _, propias = _censo_de_lectores(_de_produccion(arboles))
        seguidas = [clave for clave, raices in total.items() if raices and not propias[clave]]
        assert seguidas, "el censo no siguió ningún envoltorio en producción"


# ------------------------------------------------------------------------------------------------------------------------------------------ T3

def _recibe_el_tipo(llamada):
    return len(llamada.args) >= 5 or any(k.arg == "tipo_reporte" for k in llamada.keywords)


def _fallos_de_firma(arbol_del_reporte):
    fallos = []
    definiciones = _funcion(arbol_del_reporte, "_recopilar_datos_completos")
    if len(definiciones) != 1:
        return [f"_recopilar_datos_completos debe definirse una vez (hay {len(definiciones)})"]
    a = definiciones[0].args
    posicionales = [x.arg for x in [*a.posonlyargs, *a.args]]
    if "tipo_reporte" in posicionales:
        indice = posicionales.index("tipo_reporte")
        if indice >= len(posicionales) - len(a.defaults):
            fallos.append("`tipo_reporte` tiene valor por omisión: quien llame sin decir qué reporte quiere recibiría uno adivinado (D2)")
    elif "tipo_reporte" in [x.arg for x in a.kwonlyargs]:
        if a.kw_defaults[[x.arg for x in a.kwonlyargs].index("tipo_reporte")] is not None:
            fallos.append("`tipo_reporte` (solo por nombre) tiene valor por omisión")
    else:
        fallos.append("`_recopilar_datos_completos` no recibe `tipo_reporte`: la tabla la decide el dato y no lo pedido (DP-147)")
    return fallos


def _importa_el_mensual(arbol):
    """El archivo importa `reportes_mensuales` (el modulo cuya `_recopilar_datos_completos` se censa): fuera de ese modulo, es la unica forma de llamarla."""
    for n in ast.walk(arbol):
        if isinstance(n, ast.ImportFrom) and ("reportes_mensuales" in (n.module or "") or any("reportes_mensuales" in a.name for a in n.names)):
            return True
        if isinstance(n, ast.Import) and any("reportes_mensuales" in a.name for a in n.names):
            return True
    return False


def _llamadas_sin_el_tipo(arboles_, excluir):
    """[(archivo, linea)] y el total de las llamadas a la `_recopilar_datos_completos` del MENSUAL (las del propio modulo y las de quien lo importa) que no pasan el tipo.
    El anual tiene su propia homonima de cuatro parametros: sus llamadas (y las de quien solo importa el anual) no entran."""
    sin, total = [], 0
    for rel, arbol in arboles_.items():
        if rel in excluir or not (rel == REPORTE or _importa_el_mensual(arbol)):
            continue
        for n in ast.walk(arbol):
            if isinstance(n, ast.Call) and _nombre_llamado(n) == "_recopilar_datos_completos":
                total += 1
                if not _recibe_el_tipo(n):
                    sin.append((rel, n.lineno))
    return sin, total


SIN_VALOR = object()


def _valor_por_omision(arbol, nombre_funcion, parametro):
    """El nodo del valor por omision de `parametro` en `nombre_funcion`, o SIN_VALOR si es obligatorio."""
    definiciones = _funcion(arbol, nombre_funcion)
    assert len(definiciones) == 1, f"{nombre_funcion} debe definirse una vez (hay {len(definiciones)})"
    a = definiciones[0].args
    posicionales = [x.arg for x in [*a.posonlyargs, *a.args]]
    if parametro in posicionales:
        indice, desde = posicionales.index(parametro), len(posicionales) - len(a.defaults)
        return a.defaults[indice - desde] if indice >= desde else SIN_VALOR
    solo_nombre = [x.arg for x in a.kwonlyargs]
    assert parametro in solo_nombre, f"{nombre_funcion} no recibe {parametro}"
    valor = a.kw_defaults[solo_nombre.index(parametro)]
    return SIN_VALOR if valor is None else valor


def _fallos_del_tipo_por_omision(arbol, nombre_funcion):
    """El `tipo_reporte` de una funcion que sirve a TODAS las maquinas (y donde solo braquiterapia mira el tipo) no puede traer por omision un TIPO de reporte: la rama de
    braquiterapia se elegiria por defecto y en silencio (H1 de la revision; el mismo trato de D2). Solo se admite obligatorio o `None`, que braquiterapia rechaza en voz alta."""
    valor = _valor_por_omision(arbol, nombre_funcion, "tipo_reporte")
    if valor is SIN_VALOR or (isinstance(valor, ast.Constant) and valor.value is None):
        return []
    return [f"`{nombre_funcion}` tiene `tipo_reporte={ast.unparse(valor)}` por omisión: quien la llame para braquiterapia sin decir qué reporte quiere recibiría una rama adivinada"]


def _datos_de_una_linealidad():
    """Los datos de una linealidad con la forma (claves y tipos) que entrega `_obtener_datos_linealidad_braquiterapia`, sin BD."""
    datos = {"equipo": "Braquiterapia", "fecha": "2026-03-03", "user_id": "Fisica Linealidad", "user_id_f2": None, "tipo": "Linealidad", "modelo": "MODELO-LIN",
             "serie_cp": "LIN-UNO", "calibracion": 467900.0, "modelo_elec": "CDX-2000B", "serie_ele": "EL-LIN", "electrometro": 1.0, "q_est": 2134.7, "t_integrado": 30.0,
             "i_est": 71.16, "repro_prom": 4379.16, "reproducibilidad": 99.8, "exactitud": 0.99999, "tiempo_transito": 1.59, "datos_linealidad": []}
    for m in range(1, 6):
        datos[f"repro_m{m}"] = 4379.0 + m / 10
    for i in range(10):
        tp = 0.1 * 2 ** i
        datos["datos_linealidad"].append({"tp": tp, "q1": 120 + 70 * tp, "q2": 120.5 + 70 * tp, "qprom": 120.25 + 70 * tp, "te": 1.7 + tp})
    return datos


class TestT3LaFirma:
    def test_t3_tipo_reporte_va_sin_valor_por_omision(self, arboles):
        fallos = _fallos_de_firma(arboles[REPORTE])
        assert not fallos, "\n".join(fallos)

    def test_t3_toda_llamada_del_repo_pasa_el_tipo_y_reporte_mensual_pasa_el_pedido(self, arboles):
        sin, total = _llamadas_sin_el_tipo(arboles, excluir={REPORTE_ANUAL, "tests/test_dp147_pdf_mensual_por_tipo.py"})
        assert total >= 1, "el censo no encontró ni una llamada: estaría vacío"
        assert not sin, f"llamadas a `_recopilar_datos_completos` que no pasan el tipo de reporte: {sin}"
        llamadas = [n for f in _funcion(arboles[REPORTE], "reporte_mensual") for n in ast.walk(f)
                    if isinstance(n, ast.Call) and _nombre_llamado(n) == "_recopilar_datos_completos"]
        assert len(llamadas) == 1, llamadas
        ultimo = llamadas[0].args[4] if len(llamadas[0].args) >= 5 else next(k.value for k in llamadas[0].keywords if k.arg == "tipo_reporte")
        assert isinstance(ultimo, ast.Name) and ultimo.id == "tipo_reporte", "reporte_mensual debe pasar el tipo PEDIDO (la variable `tipo_reporte`), no un literal"

    def test_t3_el_censo_discrimina_una_llamada_sin_el_tipo_y_una_firma_con_omision(self):
        llamadas = ("_recopilar_datos_completos(db, 1, cfg, m)\n_recopilar_datos_completos(db, 1, cfg, m, tipo_reporte)\n"
                    "rm._recopilar_datos_completos(db, 1, cfg, m, tipo_reporte=t)\n")
        sin, total = _llamadas_sin_el_tipo({"x.py": ast.parse("from models.PDF.Mensuales import reportes_mensuales as rm\n" + llamadas)}, excluir=set())
        assert (sin, total) == ([("x.py", 2)], 3)
        # quien solo importa el ANUAL (que tiene su propia homonima de cuatro parametros) no entra al censo del mensual
        sin, total = _llamadas_sin_el_tipo({"y.py": ast.parse("from models.PDF.Anual import reportes_anuales as ra\n" + llamadas)}, excluir=set())
        assert (sin, total) == ([], 0)
        assert _fallos_de_firma(ast.parse("def _recopilar_datos_completos(db, ref_id, config_tablas, maquina, tipo_reporte='Control Mensual'):\n    pass\n"))
        assert _fallos_de_firma(ast.parse("def _recopilar_datos_completos(db, ref_id, config_tablas, maquina):\n    pass\n"))
        assert _fallos_de_firma(ast.parse("def _recopilar_datos_completos(db, ref_id, config_tablas, maquina, *, tipo_reporte='x'):\n    pass\n"))
        assert not _fallos_de_firma(ast.parse("def _recopilar_datos_completos(db, ref_id, config_tablas, maquina, tipo_reporte):\n    pass\n"))
        assert not _fallos_de_firma(ast.parse("def _recopilar_datos_completos(db, ref_id, config_tablas, maquina, *, tipo_reporte):\n    pass\n"))

    def test_t3_el_anual_conserva_su_propia_firma(self, arboles):
        """`reportes_anuales.py` tiene SU homonima de cuatro parametros: este arreglo no la toca."""
        anual = _funcion(arboles[REPORTE_ANUAL], "_recopilar_datos_completos")
        assert len(anual) == 1 and [a.arg for a in anual[0].args.args] == ["db", "ref_id", "config_tablas", "maquina"]

    def test_t3_procesar_datos_para_reporte_no_adivina_el_tipo_por_omision(self, arboles):
        """H1 de la revision: `_procesar_datos_para_reporte` (la tercera decision) decide la rama de braquiterapia SOLO por el tipo pedido; si su `tipo_reporte` trajera por omision
        'Control Mensual', quien la llamara con datos de una linealidad y sin tipo imprimiria tablas de calibracion armadas con datos de linealidad, sin aviso."""
        fallos = _fallos_del_tipo_por_omision(arboles[REPORTE], "_procesar_datos_para_reporte")
        assert not fallos, "\n".join(fallos)

    def test_t3_el_censo_del_tipo_por_omision_discrimina(self):
        def fallos(firma):
            return _fallos_del_tipo_por_omision(ast.parse(f"def _p({firma}):\n    pass\n"), "_p")
        assert fallos("a, b, c, maquina, tipo_reporte='Control Mensual'")
        assert fallos("a, tipo_reporte='Linealidad'")
        assert fallos("a, *, tipo_reporte='x'")
        assert not fallos("a, b, c, maquina, tipo_reporte=None")
        assert not fallos("a, tipo_reporte")
        assert not fallos("a, *, tipo_reporte=None")
        assert not fallos("a, *, tipo_reporte")

    def test_t3_procesar_datos_para_braquiterapia_sin_decir_el_tipo_falla_en_voz_alta_y_con_el_tipo_decide_el_tipo(self, rm, monkeypatch):
        """Los mismos datos de una linealidad: SIN tipo falla con un mensaje que nombra `tipo_reporte` (antes imprimia calibracion en silencio: probado con la linealidad 14 de la
        copia real del 08-10); CON el tipo pedido, el tipo decide la rama y no el dato (linealidad con 'Linealidad', calibracion con 'Control Mensual'). Las demas maquinas
        siguen sin necesitar el tipo (test_t5 llama a la funcion con cuatro argumentos)."""
        monkeypatch.setattr(rm, "_con_posicion_inicial", lambda tablas, datos: tablas)      # ni BD ni servicios: solo importa QUE rama se elige
        datos = _datos_de_una_linealidad()
        with pytest.raises(ValueError, match="tipo_reporte"):
            rm._procesar_datos_para_reporte(datos, {}, None, "Braquiterapia")
        assert set(rm._procesar_datos_para_reporte(datos, {}, None, "Braquiterapia", "Linealidad")) == CLAVES_DE_LINEALIDAD
        assert set(rm._procesar_datos_para_reporte(datos, {}, None, "Braquiterapia", "Control Mensual")) == CLAVES_DE_CALIBRACION

    def test_t3_el_predicado_rechaza_en_voz_alta_un_tipo_ausente(self, rm):
        """La pregunta «¿es el reporte de linealidad?» no se contesta sin un reporte pedido: `None` no es «no» (seria adivinar calibracion)."""
        with pytest.raises(ValueError, match="tipo_reporte"):
            rm._es_reporte_de_linealidad(None)

