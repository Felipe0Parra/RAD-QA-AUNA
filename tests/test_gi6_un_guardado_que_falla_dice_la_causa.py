"""GI.6 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, A9): si un guardado de una prueba de imagen NO se hizo, la aplicacion dice POR QUE.

Antes `guardar_prueba_completa_catphan` hacia rollback, `print_exc` (a una consola que el `.exe` no tiene) y devolvia `None`; la pantalla decia siempre
«Error al guardar X en la base de datos» -- una base sin la columna `error_pct`, un bloqueo real de otro proceso (30 s de congelacion) y un `FOREIGN KEY` eran lo mismo --, sus ramas
especificas eran inalcanzables y `error_log.txt` no recibia nada. Ademas el escritor ignoraba lo que devolvia cada `guardar_*`: una prueba cuyas filas hijas no entraron anulaba la
vigente buena y se daba por guardada (anotacion de la revision de GI.1).

Ahora: el escritor revierte TODO y RELANZA; una prueba sin filas hijas no se da por guardada; la auditoria posterior al commit no tumba un guardado bueno; la pantalla traduce los
casos conocidos (`errores_guardado.traducir`, sin texto crudo de SQLite) y deja la causa tecnica completa en `error_log.txt` (`services/registro_errores.py`).
kV, mA y espesor siguen siendo obligatorios (D1): nada de aqui lo relaja.

Los imports de lo NUEVO son perezosos donde conviene, para que contra el codigo anterior cada prueba caiga por su aserción y no por un `ImportError` generico.
"""
import ast
import gc
import os
import sqlite3
import sys
import threading
import time

import pytest
from PyQt5.QtWidgets import QMessageBox, QPushButton

from _formularios_imagenes import FORMULARIOS, app, bd_temporal, iniciar, sin_dialogos  # noqa: F401  (fixtures)
from _serie_sintetica import serie_axial
from data.ManejoDatos.catphan_TAC import catphan_db
from data.ManejoDatos.catphan_TAC.leer_dicom import DicomVolume

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIMBOLOS = ("✅", "❌", "✓", "✗", "⚠", "✔", "✖")
PAYLOAD_ESPESOR = {"espesor_promedio_mm": 1.9, "espesor_teorico_mm": 2.0, "diferencia_mm": 0.1,
                   "espesores_individuales": {"Izquierda": 1.9, "Abajo": 1.9, "Derecha": 1.9, "Arriba": 1.9}, "num_rampas_detectadas": 4}
PAYLOAD_PIXEL = {"X": 1.07, "Y": 1.08, "imagen_analisis": b"png"}
PAYLOAD_LINEALIDAD = {"pendiente": 1.0, "intercepto": 0.0, "r_squared": 0.999}


@pytest.fixture(autouse=True)
def _hay_qapplication(app):
    """Las pruebas de aqui construyen pantallas: la QApplication tiene que existir antes (Trampa 1)."""
    return app


@pytest.fixture
def dialogos(monkeypatch):
    """Todo lo que ve el fisico: [(tipo, titulo, texto)]. Ningun QMessageBox real (Trampa 2)."""
    visto = []
    for tipo in ("warning", "critical", "information"):
        monkeypatch.setattr(QMessageBox, tipo, lambda parent, titulo, texto, *a, _t=tipo, **k: visto.append((_t, titulo, texto)))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    return visto


@pytest.fixture
def log_de_errores(monkeypatch, tmp_path):
    """`error_log.txt` de la prueba: un archivo temporal (nunca el del proyecto)."""
    ruta = tmp_path / "error_log.txt"
    import services.registro_errores as registro
    monkeypatch.setattr(registro, "ruta_error_log", lambda: str(ruta))
    return ruta


def _cerrar_pantalla(obj):
    """Receta de cierre de la Trampa 9 del CLAUDE.md: `deleteLater()` + `gc.collect()` no bastan; sin el bucle de eventos las pantallas con una serie quedan vivas (la revision de GI.6
    midio 15 pantallas y 9076 widgets vivos tras las 14 pruebas de pantalla, contra 0 y 240 con esta receta). Ademas se suelta la vista del volumen."""
    from PyQt5.QtCore import QCoreApplication, QEvent
    visualizador = getattr(obj, "visualizador_principal", None)
    if visualizador is not None:
        visualizador.vol = None
    obj.corte_seleccionado_info = None
    obj.hide()
    obj.close()
    obj.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QCoreApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


@pytest.fixture
def pantallas():
    lista = []
    yield lista
    for obj in lista:
        _cerrar_pantalla(obj)
    lista.clear()
    gc.collect()


def _pantalla(pantallas, tmp_path, clave="tomografo", dialogos=None):
    obj = iniciar(FORMULARIOS[clave][0]())
    pantallas.append(obj)
    obj.user_id = "Fisico Real"
    obj.visualizador_principal.vol = DicomVolume(serie_axial(str(tmp_path / "serie"), n=5))
    obj.asignar_parametros_adquisicion()
    if dialogos is not None:
        del dialogos[:]                  # crear el control ya dijo «Exito»: lo que cuenta es lo que ve el fisico DESPUES, al guardar
    return obj


def _preparar_espesor(obj):
    obj._registrar_adquisicion("espesor", b"PNG-DEL-CORTE")
    obj.resultados_espesor = dict(PAYLOAD_ESPESOR)
    return obj.resultados_espesor


def _crear_control(con, equipo="Tomógrafo", fecha="06/2026"):
    con.execute("INSERT INTO controles (equipo, control, fecha) VALUES (?, 'Mensual', ?)", (equipo, fecha))
    con.commit()
    return con.execute("SELECT id FROM controles ORDER BY id DESC LIMIT 1").fetchone()[0]


def _guardar(ref, categorias, **extra):
    base = dict(user_id="Fisico Real", fecha="2026-06-01", equipo="Tomógrafo", kv=120, ma=100, espesor_corte=2.0,
                resultados_por_categoria=categorias, id_sesion=ref, tam_px_teorico=1.074)
    base.update(extra)
    return catphan_db.guardar_prueba_completa_catphan(**base)


def _filas_vigentes(con, ref):
    return con.execute("SELECT id_prueba, id_tipo FROM pruebas WHERE id_sesion = ? AND activo = 1 ORDER BY id_tipo", (ref,)).fetchall()


def _todas(con, ref):
    return con.execute("SELECT COUNT(*) FROM pruebas WHERE id_sesion = ?", (ref,)).fetchone()[0]


def _hijas(con, tabla, id_prueba):
    return con.execute(f"SELECT COUNT(*) FROM {tabla} WHERE id_prueba = ? AND activo = 1", (id_prueba,)).fetchone()[0]


def _valores_ct(nombres=("Aire", "PMP", "LDPE", "Poliestireno", "Acrilico", "Delrin", "Teflon"), metadatos=True):
    """Lo que entrega `valor_numero_ct`: un dict por material y, al final, un elemento de METADATOS (la imagen del analisis) que no es un material."""
    lista = [{"centro": (10, 10), "material": n, "promedio_hu": 10.0 * i, "std_hu": 1.0, "rango_hu": [0, 1], "error_abs": 1.0, "error_rel": 0.5} for i, n in enumerate(nombres)]
    if metadatos:
        lista.append({"imagen_analisis": b"png"})
    return lista


# --------------------------------------------------------------------------------------------------- el traductor (puro)
CASOS = [
    # (excepcion, titulo, gravedad, fragmentos que SI deben estar, texto crudo que NO debe aparecer)
    (sqlite3.OperationalError("database is locked"), "Base de datos ocupada", "aviso", ["otro proceso", "repita el guardado"], ["database is locked"]),
    (sqlite3.OperationalError("database table is locked"), "Base de datos ocupada", "aviso", ["otro proceso"], ["table is locked"]),
    (sqlite3.OperationalError("table tamaño_pixel has no column named error_pct"), "Falta una columna en la base de datos", "error",
     ["a la tabla «tamaño_pixel» de la base de datos le falta la columna «error_pct»", "migración"], ["has no column named"]),
    (sqlite3.OperationalError("no such column: mes_control"), "Falta una columna en la base de datos", "error", ["a la base de datos le falta la columna «mes_control»", "migración"], ["no such column"]),
    (sqlite3.OperationalError("no such table: catphan_metricas"), "Falta una tabla en la base de datos", "error", ["le falta la tabla «catphan_metricas»", "migración"], ["no such table"]),
    # GI.6 (revision, P4): SQLite no dice CUAL clave foranea fallo (el control, el material, el tipo de prueba...): el mensaje no culpa a un solo padre
    (sqlite3.IntegrityError("FOREIGN KEY constraint failed"), "Falta un dato relacionado", "error", ["falta un dato del que depende", "por ejemplo", "ábralo de nuevo", "avise al responsable"], ["FOREIGN KEY"]),
    (sqlite3.IntegrityError("UNIQUE constraint failed: pruebas.id_sesion, pruebas.id_tipo"), "Registro duplicado", "error", ["la tabla «pruebas» ya tiene un registro vigente igual", "error_log.txt"], ["UNIQUE constraint"]),
    # un UNIQUE de indice con expresion no trae «tabla.columna» sino «index 'nombre'»: no se presenta ese texto como si fuera una tabla
    (sqlite3.IntegrityError("UNIQUE constraint failed: index 'idx_controles_unico_mes'"), "Registro duplicado", "error",
     ["ya tiene un registro vigente igual", "idx_controles_unico_mes", "error_log.txt"], ["UNIQUE constraint", "la tabla «index"]),
    (sqlite3.IntegrityError("NOT NULL constraint failed: pruebas.espesor_corte"), "Falta un dato obligatorio", "error", ["falta el dato obligatorio «espesor_corte» de la tabla «pruebas»"], ["NOT NULL constraint"]),
    (sqlite3.IntegrityError("CHECK constraint failed: tamaño_pixel"), "Dato fuera de lo permitido", "error", ["no cumple"], ["CHECK constraint"]),
    (sqlite3.OperationalError("disk I/O error"), "No se pudo escribir en la base de datos", "error", ["permisos", "disponible"], ["I/O error"]),
    (sqlite3.OperationalError("unable to open database file"), "No se pudo escribir en la base de datos", "error", ["permisos"], ["unable to open"]),
    (sqlite3.OperationalError("attempt to write a readonly database"), "No se pudo escribir en la base de datos", "error", ["permisos"], ["readonly database"]),
    (sqlite3.OperationalError("database or disk is full"), "No se pudo escribir en la base de datos", "error", ["permisos"], ["disk is full"]),
    (sqlite3.DatabaseError("database disk image is malformed"), "Base de datos dañada", "error", ["respaldo", "No siga trabajando"], ["malformed"]),
    (sqlite3.DatabaseError("file is not a database"), "Base de datos dañada", "error", ["respaldo"], ["not a database"]),
    (RuntimeError("detalle secreto de la implementacion"), "Error inesperado", "error", ["RuntimeError", "error_log.txt"], ["detalle secreto"]),
]


class TestTraductor:

    @pytest.mark.parametrize("excepcion, titulo, gravedad, debe, no_debe", CASOS, ids=[str(c[0])[:48] for c in CASOS])
    def test_cada_causa_conocida_tiene_su_mensaje(self, excepcion, titulo, gravedad, debe, no_debe):
        from analisisImagenes.catphan.errores_guardado import traducir
        m = traducir(excepcion, "Espesor de corte")
        assert (m.titulo, m.gravedad) == (titulo, gravedad)
        assert m.texto.startswith("No se pudo guardar «Espesor de corte»")
        assert "No se guardó nada" in m.texto
        for fragmento in debe:
            assert fragmento in m.texto, (fragmento, m.texto)
        for crudo in no_debe:
            assert crudo not in m.texto, f"texto crudo en el mensaje: {crudo!r}"
        assert not any(s in m.titulo + m.texto for s in SIMBOLOS)                                  # DA-18

    def test_solo_lo_inesperado_se_marca_como_no_conocido(self):
        from analisisImagenes.catphan.errores_guardado import traducir
        assert [traducir(c[0]).conocido for c in CASOS] == [True] * (len(CASOS) - 1) + [False]

    def test_sin_prueba_el_sujeto_es_la_prueba(self):
        from analisisImagenes.catphan.errores_guardado import traducir
        assert traducir(sqlite3.OperationalError("database is locked")).texto.startswith("No se pudo guardar la prueba")

    def test_una_prueba_que_no_entrego_datos_y_una_cuyos_datos_no_se_pueden_convertir(self):
        from analisisImagenes.catphan.errores_guardado import (CAUSA_NO_CONVERTIBLES, CAUSA_SIN_DATOS, CategoriaNoGuardada, traducir)
        sin = traducir(CategoriaNoGuardada("linealidad_ct", CAUSA_SIN_DATOS), "Linealidad CT")
        malos = traducir(CategoriaNoGuardada("linealidad_ct", CAUSA_NO_CONVERTIBLES), "Linealidad CT")
        assert sin.titulo == "Prueba sin datos" and "no entregó datos" in sin.texto and "Repita el análisis" in sin.texto
        assert malos.titulo == "Resultados incompletos" and "incompletos" in malos.texto and "error_log.txt" in malos.texto
        assert sin.conocido and malos.conocido and sin.texto != malos.texto

    def test_todo_mensaje_dice_que_no_se_guardo_y_que_hacer(self):
        from analisisImagenes.catphan.errores_guardado import CategoriaNoGuardada, traducir
        for excepcion in [c[0] for c in CASOS] + [CategoriaNoGuardada("espesor")]:
            texto = traducir(excepcion, "Espesor de corte").texto
            assert "No se guardó nada" in texto
            assert any(verbo in texto for verbo in ("Repita", "repita", "Espere", "avise", "Avise", "Compruebe", "Cierre", "migración", "recupere", "No siga"))

    def test_ninguna_excepcion_hace_fallar_al_traductor(self):
        """Revision de GI.6 (P8): `traducir` extraia la columna con `split("no such column:")[1]` y lanzaba `IndexError` ante cualquier excepcion que contuviera la frase sin los dos
        puntos (o con otra capitalizacion): el manejador de errores reventaba y el fisico se quedaba sin dialogo. Venga de donde venga, una excepcion tiene mensaje."""
        from analisisImagenes.catphan.errores_guardado import MensajeDeError, traducir
        for excepcion in (KeyError("no such column"), ValueError("Error: no such column in frame"), RuntimeError("no such column: "),
                          sqlite3.OperationalError("No Such Column"), sqlite3.OperationalError("table  has no column named "),
                          sqlite3.OperationalError("no such table: "), sqlite3.IntegrityError("UNIQUE constraint failed: "),
                          sqlite3.IntegrityError("NOT NULL constraint failed: x"), Exception(), Exception(None), OSError(13, "Permiso denegado")):
            m = traducir(excepcion, "Espesor de corte")
            assert isinstance(m, MensajeDeError) and "No se guardó nada" in m.texto, repr(excepcion)
            assert not any(s in m.titulo + m.texto for s in SIMBOLOS)

    def test_el_mensaje_no_dice_que_dejo_el_detalle_si_no_se_pudo_registrar(self):
        """Revision de GI.6 (P5): los mensajes afirmaban «el detalle quedó en error_log.txt» aunque el registro no se hubiera podido escribir (carpeta sin permiso, disco lleno): el
        `.exe` no tiene consola y no quedaba rastro alguno. `traducir(..., registrado=False)` lo dice."""
        from analisisImagenes.catphan.errores_guardado import CAUSA_NO_CONVERTIBLES, CategoriaNoGuardada, traducir
        prometen = 0
        for excepcion in [c[0] for c in CASOS] + [CategoriaNoGuardada("espesor", CAUSA_NO_CONVERTIBLES)]:
            con = traducir(excepcion, "Espesor de corte").texto
            sin = traducir(excepcion, "Espesor de corte", registrado=False).texto
            assert "No se guardó nada" in sin
            if "quedó en error_log.txt" in con:
                prometen += 1
                assert "quedó en error_log.txt" not in sin and "no se pudo escribir el detalle" in sin.lower(), (con, sin)
            else:
                assert sin == con, "lo que no promete el registro no cambia"
        assert prometen >= 6, "duplicado (2), dato obligatorio, fuera de lo permitido, dato relacionado, resultados incompletos e inesperado prometen el registro"

    def test_una_prueba_que_no_entrego_datos_nombra_la_prueba_de_la_excepcion_aunque_no_se_la_pasen(self):
        """Revision de GI.6 (P6): en «Guardar todos» la pantalla no sabe cual de las siete fallo, pero la excepcion si (`.categoria`): el mensaje la nombra. Si la pantalla SI sabe cual
        es, manda lo que le diga."""
        from analisisImagenes.catphan.errores_guardado import CAUSA_NO_CONVERTIBLES, CAUSA_SIN_DATOS, CategoriaNoGuardada, traducir
        for causa in (CAUSA_SIN_DATOS, CAUSA_NO_CONVERTIBLES):
            texto = traducir(CategoriaNoGuardada("linealidad_ct", causa)).texto
            assert texto.startswith("No se pudo guardar «Linealidad CT»"), texto
        assert traducir(CategoriaNoGuardada("linealidad_ct"), "Espesor de corte").texto.startswith("No se pudo guardar «Espesor de corte»")

    def test_una_prueba_sin_datos_o_incompleta_es_un_error_y_no_un_aviso(self):
        """Revision de GI.6 (GI6-T4): se arregla repitiendo el analisis, no esperando; la gravedad decide el icono del dialogo (advertencia o error)."""
        from analisisImagenes.catphan.errores_guardado import CAUSA_NO_CONVERTIBLES, CAUSA_SIN_DATOS, CategoriaNoGuardada, GRAVEDAD_ERROR, traducir
        for causa in (CAUSA_SIN_DATOS, CAUSA_NO_CONVERTIBLES):
            assert traducir(CategoriaNoGuardada("espesor", causa), "Espesor de corte").gravedad == GRAVEDAD_ERROR


# ------------------------------------------------------------------------------------------------------ el registro de errores
class TestRegistroDeErrores:

    def test_la_ruta_es_la_de_main_en_desarrollo_y_junto_al_ejecutable_congelado(self, monkeypatch, tmp_path):
        import services.registro_errores as registro
        monkeypatch.chdir(tmp_path)                       # la ruta NO depende de desde donde se arranque
        assert registro.ruta_error_log() == os.path.join(RAIZ, "error_log.txt")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", os.path.join("C:\\", "Controles", "RAD-QA.exe"))
        assert registro.ruta_error_log() == os.path.join(os.path.dirname(sys.executable), "error_log.txt")

    def test_deja_la_hora_el_contexto_y_el_rastro_de_la_causa_encadenada(self, log_de_errores):
        import services.registro_errores as registro
        try:
            try:
                raise sqlite3.OperationalError("database is locked")
            except sqlite3.OperationalError as causa:
                raise RuntimeError("no se pudo convertir") from causa
        except RuntimeError as e:
            assert registro.registrar_error("Guardar «Espesor de corte» falló (control 7)", e, detalle="usuario: Fisico Real") is True
        texto = log_de_errores.read_text(encoding="utf-8")
        assert "Guardar «Espesor de corte» falló (control 7)" in texto and "usuario: Fisico Real" in texto
        assert "RuntimeError: no se pudo convertir" in texto and "sqlite3.OperationalError: database is locked" in texto
        assert "direct cause" in texto and "Traceback" in texto
        assert texto.lstrip().startswith("[20")

    def test_cada_registro_se_agrega_al_final_y_no_pisa_los_anteriores(self, log_de_errores):
        import services.registro_errores as registro
        registro.registrar_error("primero")
        registro.registrar_error("segundo")
        texto = log_de_errores.read_text(encoding="utf-8")
        assert texto.index("primero") < texto.index("segundo") and texto.count("[20") == 2

    def test_nunca_lanza_aunque_no_pueda_escribir(self, monkeypatch, tmp_path):
        import services.registro_errores as registro
        monkeypatch.setattr(registro, "ruta_error_log", lambda: str(tmp_path))                   # una CARPETA: abrirla para escribir falla
        assert registro.registrar_error("x", RuntimeError("y")) is False

    def test_avisar_consola_nunca_lanza(self, monkeypatch):
        """Revision de GI.6 (P3): ni un simbolo con una salida ascii, ni una salida cerrada, ni la ausencia de consola (el `.exe` --noconsole deja `sys.stdout` en `None`) la rompen."""
        import io
        import services.registro_errores as registro

        class SalidaRota:
            def write(self, *a):
                raise OSError(9, "Bad file descriptor")

            def flush(self):
                raise OSError(9, "Bad file descriptor")

        for salida, esperado in ((io.TextIOWrapper(io.BytesIO(), encoding="ascii"), False), (SalidaRota(), False), (None, True), (io.StringIO(), True)):
            monkeypatch.setattr(sys, "stdout", salida)
            assert registro.avisar_consola("Guardado ✅ ok") is esperado


# ----------------------------------------------------------------------------------------------------------- el escritor
class TestEscritor:

    def test_una_base_sin_la_columna_error_pct_relanza_la_causa_y_no_deja_nada(self, bd_temporal):
        """El ejemplo de A9: antes `None` y un «Error al guardar» sin causa."""
        bd_temporal.execute("ALTER TABLE tamaño_pixel DROP COLUMN error_pct")
        bd_temporal.commit()
        ref = _crear_control(bd_temporal)
        with pytest.raises(sqlite3.OperationalError, match="error_pct"):
            _guardar(ref, {"tamano_pixel": PAYLOAD_PIXEL})
        assert _todas(bd_temporal, ref) == 0

    def test_un_fallo_en_otra_categoria_revierte_todo_y_relanza(self, bd_temporal, monkeypatch):
        from analisisImagenes.catphan.errores_guardado import CAUSA_NO_CONVERTIBLES, CategoriaNoGuardada
        ref = _crear_control(bd_temporal)
        _guardar(ref, {"espesor": PAYLOAD_ESPESOR})
        antes = _filas_vigentes(bd_temporal, ref)

        def falla(*a, **k):
            raise RuntimeError("fallo simulado")

        monkeypatch.setattr(catphan_db, "guardar_linealidad_ct", falla)
        with pytest.raises(CategoriaNoGuardada) as e:
            _guardar(ref, {"espesor": dict(PAYLOAD_ESPESOR, espesor_promedio_mm=2.1), "linealidad_ct": PAYLOAD_LINEALIDAD})
        assert e.value.categoria == "linealidad_ct" and e.value.causa == CAUSA_NO_CONVERTIBLES and isinstance(e.value.__cause__, RuntimeError)
        assert _filas_vigentes(bd_temporal, ref) == antes, "lo que ya estaba guardado no debe cambiar"

    def test_el_escritor_revierte_antes_de_relanzar_y_nunca_confirma(self, bd_temporal, monkeypatch):
        """El rollback explicito no es decorativo: con un cierre de conexion tardio o un cursor compartido, lo escrito a medias podria confirmarse. Se espia el orden."""
        from types import SimpleNamespace
        llamadas = []

        class Espia:
            def __init__(self, real):
                self._real = real

            def __getattr__(self, nombre):
                atributo = getattr(self._real, nombre)
                if nombre in ("rollback", "commit", "close") and callable(atributo):
                    def registrado(*a, **k):
                        llamadas.append(nombre)
                        return atributo(*a, **k)
                    return registrado
                return atributo

        real = catphan_db.Conexion().conectar()
        monkeypatch.setattr(catphan_db, "Conexion", lambda: SimpleNamespace(conectar=lambda: Espia(real)))
        monkeypatch.setattr(catphan_db, "guardar_espesor_corte", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("falla a mitad")))
        ref = _crear_control(bd_temporal)
        with pytest.raises(Exception):
            _guardar(ref, {"espesor": PAYLOAD_ESPESOR})
        assert "rollback" in llamadas and "commit" not in llamadas
        assert llamadas.index("rollback") < llamadas.index("close")

    def test_un_error_de_la_base_en_una_categoria_se_relanza_tal_cual_y_no_se_disfraza(self, bd_temporal, monkeypatch):
        ref = _crear_control(bd_temporal)

        def ocupada(*a, **k):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(catphan_db, "guardar_espesor_corte", ocupada)
        with pytest.raises(sqlite3.OperationalError, match="database is locked"):
            _guardar(ref, {"espesor": PAYLOAD_ESPESOR})
        assert _todas(bd_temporal, ref) == 0

    def test_la_base_realmente_ocupada_por_otro_se_rinde_y_dice_ocupada(self, bd_temporal, monkeypatch):
        """Un bloqueo REAL (otra conexion con una transaccion de escritura abierta), con la espera bajada de 30 s a 0.3 s."""
        from data.ManejoDatos.conection import ruta_base_datos
        monkeypatch.setattr(catphan_db, "ESPERA_BD_OCUPADA_MS", 300)
        ref = _crear_control(bd_temporal)
        otro = sqlite3.connect(ruta_base_datos(), timeout=1)
        otro.execute("BEGIN IMMEDIATE")
        try:
            t0 = time.time()
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                _guardar(ref, {"espesor": PAYLOAD_ESPESOR})
            assert time.time() - t0 < 10
        finally:
            otro.rollback()
            otro.close()
        assert _todas(bd_temporal, ref) == 0
        assert _guardar(ref, {"espesor": PAYLOAD_ESPESOR}) == ref, "tras soltar la base, el guardado funciona (no quedo ninguna transaccion colgada)"

    def test_una_prueba_cuyas_filas_no_entraron_no_se_da_por_guardada_y_no_anula_la_buena(self, bd_temporal):
        """La anotacion de la revision de GI.1: el segundo guardado de una linealidad sin R² devolvia exito, anulaba la fila vigente buena y no insertaba la nueva."""
        ref = _crear_control(bd_temporal)
        _guardar(ref, {"linealidad_ct": PAYLOAD_LINEALIDAD})
        buena = _filas_vigentes(bd_temporal, ref)
        assert len(buena) == 1
        with pytest.raises(Exception) as e:
            _guardar(ref, {"linealidad_ct": {"pendiente": 1.0, "intercepto": 0.0, "r_squared": None}})
        assert not isinstance(e.value, AssertionError)
        assert _filas_vigentes(bd_temporal, ref) == buena
        hijas = bd_temporal.execute("SELECT COUNT(*) FROM linealidad_ct WHERE id_prueba = ? AND activo = 1", (buena[0][0],)).fetchone()[0]
        assert hijas == 1, "la fila vigente buena perdio su detalle"

    def test_el_mapeo_que_revienta_es_un_dato_incompleto_de_esa_prueba(self, bd_temporal):
        from analisisImagenes.catphan.errores_guardado import CAUSA_NO_CONVERTIBLES, CategoriaNoGuardada
        ref = _crear_control(bd_temporal)
        with pytest.raises(CategoriaNoGuardada) as e:
            _guardar(ref, {"tamano_pixel": {"X": None, "Y": None}})              # `mapear_tamano_pixel`: round(None, 3) (anotacion de GI.1)
        assert (e.value.categoria, e.value.causa) == ("tamano_pixel", CAUSA_NO_CONVERTIBLES)
        assert _todas(bd_temporal, ref) == 0

    def test_una_prueba_sin_nada_que_guardar_tampoco_se_da_por_guardada(self, bd_temporal):
        from analisisImagenes.catphan.errores_guardado import CAUSA_SIN_DATOS, CategoriaNoGuardada
        ref = _crear_control(bd_temporal)
        with pytest.raises(CategoriaNoGuardada) as e:
            _guardar(ref, {"resolucion_contraste": {"resumen": {}, "rois": []}})
        assert (e.value.categoria, e.value.causa) == ("resolucion_contraste", CAUSA_SIN_DATOS)
        assert _todas(bd_temporal, ref) == 0

    def test_si_la_auditoria_posterior_al_commit_falla_el_guardado_sigue_siendo_bueno(self, bd_temporal, monkeypatch, log_de_errores):
        ref = _crear_control(bd_temporal)

        def falla(*a, **k):
            raise RuntimeError("la auditoria no pudo escribir")

        monkeypatch.setattr(catphan_db, "_registrar_auditoria", falla)
        assert _guardar(ref, {"espesor": PAYLOAD_ESPESOR}) == ref
        assert len(_filas_vigentes(bd_temporal, ref)) == 1
        assert "la auditoria no pudo escribir" in log_de_errores.read_text(encoding="utf-8")

    def test_el_escritor_ya_no_devuelve_none_en_ningun_camino(self):
        """Tripwire: todo `return` del escritor devuelve el id de la sesion (el fallo se relanza)."""
        with open(os.path.join(RAIZ, "data/ManejoDatos/catphan_TAC/catphan_db.py"), encoding="utf-8") as f:
            arbol = ast.parse(f.read())
        funcion = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "guardar_prueba_completa_catphan")
        retornos = [n for n in ast.walk(funcion) if isinstance(n, ast.Return)]
        assert retornos and all(isinstance(r.value, ast.Name) and r.value.id == "id_sesion" for r in retornos)

    def test_guardar_linealidad_ct_ya_no_se_traga_lo_que_le_pasa(self):
        with open(os.path.join(RAIZ, "data/ManejoDatos/catphan_TAC/catphan_db.py"), encoding="utf-8") as f:
            arbol = ast.parse(f.read())
        funcion = next(n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name == "guardar_linealidad_ct")
        assert not [n for n in ast.walk(funcion) if isinstance(n, ast.ExceptHandler)]


    # ---- hallazgos de la revision escéptica de GI.6 (workflow wf_1fa65c75-6b9; guiones en logs/GI6/revision/) --------------------------------------------
    def test_un_material_que_la_tabla_no_conoce_no_se_salta_en_silencio(self, bd_temporal):
        """Revision de GI.6 (P1): `guardar_valores_ct` saltaba con `continue` los materiales fuera de su mapa y devolvia `True` aun con CERO filas: la prueba se daba por guardada, anulaba
        la vigente buena y quedaba sin detalle (o con filas de menos). El elemento de METADATOS que `valor_numero_ct` agrega al final no es un material y se sigue ignorando."""
        from analisisImagenes.catphan.errores_guardado import CAUSA_NO_CONVERTIBLES, CAUSA_SIN_DATOS, CategoriaNoGuardada
        ref = _crear_control(bd_temporal)
        assert _guardar(ref, {"valores_ct": _valores_ct()}) == ref
        buena = _filas_vigentes(bd_temporal, ref)
        assert _hijas(bd_temporal, "valores_ct", buena[0][0]) == 7, "el productor real (7 materiales + metadatos) guarda sus 7 filas"
        for malos, causa in ((_valores_ct(("Hueso", "Grasa")), CAUSA_NO_CONVERTIBLES),                      # ninguno se reconoce
                             (_valores_ct(("Aire", "Teflón")), CAUSA_NO_CONVERTIBLES),                         # uno si y uno no (la tilde): guardado parcial silencioso
                             ([{"imagen_analisis": b"png"}], CAUSA_SIN_DATOS)):                               # solo metadatos: nada que guardar
            with pytest.raises(CategoriaNoGuardada) as e:
                _guardar(ref, {"valores_ct": malos})
            assert (e.value.categoria, e.value.causa) == ("valores_ct", causa)
            assert _filas_vigentes(bd_temporal, ref) == buena, "la fila vigente buena no se anula"
            assert _hijas(bd_temporal, "valores_ct", buena[0][0]) == 7, "y conserva su detalle"

    def test_si_la_conexion_no_se_abre_el_escritor_dice_que_no_se_pudo_abrir(self, bd_temporal, monkeypatch):
        """Revision de GI.6 (P2): `Conexion.conectar()` traga su error (lo imprime) y devuelve `None`; el escritor hacia `None.execute` y lanzaba `AttributeError`: el fisico leia «error
        inesperado» y la causa no llegaba a `error_log.txt`."""
        from types import SimpleNamespace
        monkeypatch.setattr(catphan_db, "Conexion", lambda: SimpleNamespace(conectar=lambda: None))
        with pytest.raises(sqlite3.OperationalError, match="unable to open database file"):
            _guardar(1, {"espesor": PAYLOAD_ESPESOR})

    def test_un_guardado_confirmado_no_se_vuelve_fallo_por_la_consola(self, bd_temporal, monkeypatch):
        """Revision de GI.6 (P3 / GI6-T7): el aviso por consola posterior al `commit` llevaba un simbolo; con una salida que no lo admite (stdout redirigido en cp1252 o ascii) lanzaba
        `UnicodeEncodeError` DESPUES de guardar, el escritor lo relanzaba y la pantalla decia «No se guardo nada» con la fila ya en la base."""
        import io
        ref = _crear_control(bd_temporal)
        monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="ascii"))
        assert _guardar(ref, {"espesor": PAYLOAD_ESPESOR}) == ref
        assert len(_filas_vigentes(bd_temporal, ref)) == 1

    def test_una_consola_que_falla_despues_del_commit_tampoco_tumba_el_guardado(self, bd_temporal, monkeypatch):
        """Lo mismo con CUALQUIER fallo de la consola (una salida cerrada), no solo la codificacion: lo posterior al `commit` no puede convertir un guardado bueno en uno fallido."""
        ref = _crear_control(bd_temporal)

        class SalidaRota:
            def write(self, *a):
                raise OSError(9, "Bad file descriptor")

            def flush(self):
                raise OSError(9, "Bad file descriptor")

        monkeypatch.setattr(sys, "stdout", SalidaRota())
        assert _guardar(ref, {"espesor": PAYLOAD_ESPESOR}) == ref
        assert len(_filas_vigentes(bd_temporal, ref)) == 1

    def test_un_error_de_integridad_de_una_categoria_sube_tal_cual(self, bd_temporal, monkeypatch):
        """Revision de GI.6 (GI6-T1): solo `sqlite3.Error` se deja pasar SIN envolver; si el `except` se acotara a `OperationalError`, un FOREIGN KEY / UNIQUE / NOT NULL / una base
        dañada se presentaria como «Resultados incompletos» en vez de su causa (el defecto que GI.6 viene a cerrar)."""
        ref = _crear_control(bd_temporal)
        for excepcion in (sqlite3.IntegrityError("FOREIGN KEY constraint failed"), sqlite3.DatabaseError("database disk image is malformed"),
                          sqlite3.ProgrammingError("Cannot operate on a closed database.")):
            monkeypatch.setattr(catphan_db, "guardar_espesor_corte", lambda *a, _e=excepcion, **k: (_ for _ in ()).throw(_e))
            with pytest.raises(type(excepcion)) as e:
                _guardar(ref, {"espesor": PAYLOAD_ESPESOR})
            assert e.value is excepcion, "se relanza la MISMA excepcion, sin envolverla"
        assert _todas(bd_temporal, ref) == 0

    def test_la_primera_categoria_sin_datos_tampoco_se_da_por_guardada(self, bd_temporal):
        """Revision de GI.6 (GI6-T2): `if not guardado` va DENTRO del bucle de categorias; fuera de el solo se validaria la ULTIMA y una categoria intermedia sin filas hijas anularia la
        vigente buena y se daria por guardada (el defecto de GI.1)."""
        from analisisImagenes.catphan.errores_guardado import CAUSA_SIN_DATOS, CategoriaNoGuardada
        ref = _crear_control(bd_temporal)
        with pytest.raises(CategoriaNoGuardada) as e:
            _guardar(ref, {"resolucion_contraste": {"resumen": {}, "rois": []}, "espesor": PAYLOAD_ESPESOR})
        assert (e.value.categoria, e.value.causa) == ("resolucion_contraste", CAUSA_SIN_DATOS)
        assert _todas(bd_temporal, ref) == 0, "ni siquiera la categoria buena que venia despues se guarda: o entra todo o no entra nada"

    def test_un_rollback_que_falla_no_tapa_la_causa(self, bd_temporal, monkeypatch):
        """Revision de GI.6 (GI6-T3): `un rollback que falla no debe tapar la causa original` es una promesa del escritor; sin su `try/except` el rollback roto lanzaria SU error y la
        pantalla traduciria uno ajeno."""
        from types import SimpleNamespace
        real = catphan_db.Conexion().conectar()

        class Roto:
            def __init__(self, conexion):
                self._real = conexion

            def __getattr__(self, nombre):
                if nombre == "rollback":
                    def falla(*a, **k):
                        raise sqlite3.ProgrammingError("rollback roto")
                    return falla
                return getattr(self._real, nombre)

        monkeypatch.setattr(catphan_db, "Conexion", lambda: SimpleNamespace(conectar=lambda: Roto(real)))
        monkeypatch.setattr(catphan_db, "guardar_espesor_corte", lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
        ref = _crear_control(bd_temporal)
        with pytest.raises(sqlite3.OperationalError, match="database is locked"):
            _guardar(ref, {"espesor": PAYLOAD_ESPESOR})

    def test_la_espera_a_otro_proceso_es_la_de_siempre_en_produccion(self):
        """Revision de GI.6 (GI6-T4 A): la prueba del bloqueo real baja la espera a 0.3 s; 30 s es lo que la aplicacion espera DE VERDAD (V1 midio 30.6 s) y no debe cambiar sin que algo
        falle."""
        assert catphan_db.ESPERA_BD_OCUPADA_MS == 30000


# ----------------------------------------------------------------------------------------------------------- la pantalla
class TestPantalla:

    def _guardar_espesor(self, obj):
        resultados = _preparar_espesor(obj)
        return obj.guardar_resultado_individual("espesor", resultados, output_blob=b"RESULTADO")

    def test_la_base_ocupada_se_dice_ocupada_y_queda_en_el_registro(self, bd_temporal, dialogos, log_de_errores, pantallas, tmp_path, monkeypatch):
        obj = _pantalla(pantallas, tmp_path, dialogos=dialogos)
        monkeypatch.setattr(catphan_db, "guardar_espesor_corte", lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
        assert self._guardar_espesor(obj) is False
        assert [(d[0], d[1]) for d in dialogos] == [("warning", "Base de datos ocupada")]
        assert "otro proceso" in dialogos[0][2] and "database is locked" not in dialogos[0][2]
        registro = log_de_errores.read_text(encoding="utf-8")
        assert "database is locked" in registro and "«Espesor de corte»" in registro and f"control {obj.ref}" in registro and "Fisico Real" in registro
        assert obj.resultados_espesor is not None, "el resultado no se limpia: el fisico puede reintentar"

    def test_una_base_sin_columna_dice_cual_y_que_hacer(self, bd_temporal, dialogos, log_de_errores, pantallas, tmp_path):
        obj = _pantalla(pantallas, tmp_path, dialogos=dialogos)
        bd_temporal.execute("ALTER TABLE tamaño_pixel DROP COLUMN error_pct")
        bd_temporal.commit()
        obj._registrar_adquisicion("tamano_pixel", b"PNG")
        obj.tam_px_teorico = 1.074
        obj.resultados_tamano_pixel = dict(PAYLOAD_PIXEL)
        assert obj.guardar_resultado_individual("tamano_pixel", obj.resultados_tamano_pixel, output_blob=b"R") is False
        assert [(d[0], d[1]) for d in dialogos] == [("critical", "Falta una columna en la base de datos")]
        assert "«error_pct»" in dialogos[0][2] and "migración" in dialogos[0][2] and "has no column" not in dialogos[0][2]
        assert "has no column named error_pct" in log_de_errores.read_text(encoding="utf-8")

    def test_un_error_que_no_se_reconoce_no_enseña_su_texto_pero_lo_guarda_en_el_registro(self, bd_temporal, dialogos, log_de_errores, pantallas, tmp_path, monkeypatch):
        obj = _pantalla(pantallas, tmp_path, dialogos=dialogos)
        monkeypatch.setattr(catphan_db, "reemplazar_bloque", lambda *a, **k: (_ for _ in ()).throw(ValueError("texto interno del programador")))
        assert self._guardar_espesor(obj) is False
        assert dialogos[0][:2] == ("critical", "Error inesperado") and "ValueError" in dialogos[0][2] and "texto interno" not in dialogos[0][2]
        assert "texto interno del programador" in log_de_errores.read_text(encoding="utf-8")

    def test_la_guarda_que_lee_la_base_ocupada_tambien_se_dice_ocupada(self, bd_temporal, dialogos, log_de_errores, pantallas, tmp_path, monkeypatch):
        """Anotado por GI.4: la guarda de la pantalla lee la base antes de guardar; con `database is locked` ahi se veia «Error inesperado»."""
        import ui.paginasControles.PruebasMensuales.tac_mensual as tac
        obj = _pantalla(pantallas, tmp_path, dialogos=dialogos)
        monkeypatch.setattr(tac, "_puede_editarse_control", lambda ref: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
        assert self._guardar_espesor(obj) is False
        assert [(d[0], d[1]) for d in dialogos] == [("warning", "Base de datos ocupada")]
        assert _todas(bd_temporal, obj.ref) == 0

    def test_una_prueba_sin_datos_dice_cual(self, bd_temporal, dialogos, log_de_errores, pantallas, tmp_path):
        obj = _pantalla(pantallas, tmp_path, dialogos=dialogos)
        obj._registrar_adquisicion("tamano_pixel", b"PNG")
        obj.tam_px_teorico = None                                  # sin el tamano teorico del DICOM `mapear_tamano_pixel` hace round(None, 3)
        obj.resultados_tamano_pixel = dict(PAYLOAD_PIXEL)
        assert obj.guardar_resultado_individual("tamano_pixel", obj.resultados_tamano_pixel, output_blob=b"R") is False
        assert [(d[0], d[1]) for d in dialogos if d[0] in ("warning", "critical")] == [("critical", "Resultados incompletos")]
        assert "«Tamaño de píxel»" in dialogos[-1][2]

    def test_si_el_escritor_no_confirma_el_guardado_la_pantalla_lo_dice_sin_texto_crudo(self, bd_temporal, dialogos, log_de_errores, pantallas, tmp_path, monkeypatch):
        """La rama defensiva (el escritor ya no devuelve `None`, pero si alguna vez no devolviera la sesion): se dice QUE prueba no se guardo, sin simbolos."""
        import ui.paginasControles.PruebasMensuales.tac_mensual as tac
        obj = _pantalla(pantallas, tmp_path, dialogos=dialogos)
        monkeypatch.setattr(tac, "guardar_prueba_completa_catphan", lambda **k: None)
        assert self._guardar_espesor(obj) is False
        assert [(d[0], d[1]) for d in dialogos] == [("critical", "Error de guardado")]
        assert "«Espesor de corte»" in dialogos[0][2] and "No se guardó nada" in dialogos[0][2] and not any(s in dialogos[0][2] for s in SIMBOLOS)

    def test_tras_un_fallo_se_puede_reintentar_y_guarda(self, bd_temporal, dialogos, log_de_errores, pantallas, tmp_path, monkeypatch):
        obj = _pantalla(pantallas, tmp_path, dialogos=dialogos)
        original = catphan_db.guardar_espesor_corte
        monkeypatch.setattr(catphan_db, "guardar_espesor_corte", lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
        resultados = _preparar_espesor(obj)
        assert obj.guardar_resultado_individual("espesor", resultados, output_blob=b"R") is False
        monkeypatch.setattr(catphan_db, "guardar_espesor_corte", original)
        assert obj.guardar_resultado_individual("espesor", resultados, output_blob=b"R") is True
        assert len(_filas_vigentes(bd_temporal, obj.ref)) == 1

    def test_los_dialogos_de_guardado_no_llevan_simbolos(self, bd_temporal, dialogos, log_de_errores, pantallas, tmp_path, monkeypatch):
        obj = _pantalla(pantallas, tmp_path, dialogos=dialogos)
        assert self._guardar_espesor(obj) is True                                              # exito
        vistos = list(dialogos)
        obj2 = _pantalla(pantallas, tmp_path / "otra", dialogos=dialogos)
        monkeypatch.setattr(catphan_db, "guardar_espesor_corte", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
        self._guardar_espesor(obj2)                                                            # fallo
        vistos += dialogos
        assert len(vistos) >= 2
        for tipo, titulo, texto in vistos:
            assert not any(s in titulo + texto for s in SIMBOLOS), (titulo, texto)
        exito = [d for d in vistos if d[1] == "Guardado exitoso"][0]
        assert "«Espesor de corte» se guardó correctamente" in exito[2]

    def test_guardar_todos_traduce_igual(self, bd_temporal, dialogos, log_de_errores, pantallas, tmp_path, monkeypatch):
        """"Guardar Todos" es codigo muerto (A13: nadie crea `self.guardar_catphan`); el boton se pone a mano para que no quede con la regla vieja."""
        obj = _pantalla(pantallas, tmp_path, dialogos=dialogos)
        _preparar_espesor(obj)
        obj.guardar_catphan = QPushButton()
        monkeypatch.setattr(catphan_db, "guardar_espesor_corte", lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
        obj.guardar_resultados_catphan()
        assert [(d[0], d[1]) for d in dialogos if d[0] != "information"] == [("warning", "Base de datos ocupada")]
        assert obj.guardar_catphan.isEnabled()
        assert "database is locked" in log_de_errores.read_text(encoding="utf-8")
        assert not any(s in d[1] + d[2] for d in dialogos for s in SIMBOLOS)

    @pytest.mark.parametrize("clave", list(FORMULARIOS))
    def test_las_cinco_pantallas_dicen_la_causa(self, clave, bd_temporal, dialogos, log_de_errores, pantallas, tmp_path, monkeypatch):
        obj = _pantalla(pantallas, tmp_path, clave, dialogos=dialogos)
        monkeypatch.setattr(catphan_db, "guardar_espesor_corte", lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
        assert self._guardar_espesor(obj) is False
        assert [(d[0], d[1]) for d in dialogos] == [("warning", "Base de datos ocupada")]


    # ---- hallazgos de la revision escéptica de GI.6 -------------------------------------------------------------------------------------------------
    def test_si_el_registro_no_se_puede_escribir_el_mensaje_no_lo_promete(self, bd_temporal, dialogos, pantallas, tmp_path, monkeypatch):
        """Revision de GI.6 (P5): con la carpeta del registro sin permiso el dialogo decia igual «el detalle quedo en error_log.txt» y no quedaba rastro alguno (el `.exe` no tiene
        consola)."""
        import services.registro_errores as registro
        monkeypatch.setattr(registro, "ruta_error_log", lambda: str(tmp_path))                   # una CARPETA: abrirla para escribir falla
        obj = _pantalla(pantallas, tmp_path / "s", dialogos=dialogos)
        monkeypatch.setattr(catphan_db, "guardar_espesor_corte",
                            lambda *a, **k: (_ for _ in ()).throw(sqlite3.IntegrityError("UNIQUE constraint failed: pruebas.id_sesion")))
        assert self._guardar_espesor(obj) is False
        assert [(d[0], d[1]) for d in dialogos] == [("critical", "Registro duplicado")]
        assert "quedó en error_log.txt" not in dialogos[0][2] and "no se pudo escribir el detalle" in dialogos[0][2].lower()
        assert "No se guardó nada" in dialogos[0][2]

    def test_el_detalle_que_promete_el_mensaje_llega_al_registro_tambien_en_un_dato_incompleto(self, bd_temporal, dialogos, log_de_errores, pantallas, tmp_path):
        """Revision de GI.6 (GI6-T4 C): «Resultados incompletos» promete el detalle en `error_log.txt`; la causa encadenada (el `TypeError` del mapeo) tiene que estar ahi."""
        obj = _pantalla(pantallas, tmp_path, dialogos=dialogos)
        obj._registrar_adquisicion("tamano_pixel", b"PNG")
        obj.tam_px_teorico = None
        obj.resultados_tamano_pixel = dict(PAYLOAD_PIXEL)
        assert obj.guardar_resultado_individual("tamano_pixel", obj.resultados_tamano_pixel, output_blob=b"R") is False
        assert "quedó en error_log.txt" in dialogos[-1][2]
        registro = log_de_errores.read_text(encoding="utf-8")
        assert "CategoriaNoGuardada" in registro and "TypeError" in registro and "«Tamaño de píxel»" in registro

    def test_guardar_todos_nombra_la_prueba_que_fallo(self, bd_temporal, dialogos, log_de_errores, pantallas, tmp_path):
        """Revision de GI.6 (P6): en «Guardar todos» el mensaje decia «No se pudo guardar la prueba» sin nombrar cual de las hasta siete fallo (la excepcion lo sabia)."""
        obj = _pantalla(pantallas, tmp_path, dialogos=dialogos)
        _preparar_espesor(obj)
        obj._registrar_adquisicion("linealidad_ct", b"PNG")
        obj.resultados_linealidad_ct = {"pendiente": 1.0, "intercepto": 0.0, "r_squared": None}      # `mapear_linealidad_ct`: round(None, ...)
        obj.guardar_catphan = QPushButton()
        obj.guardar_resultados_catphan()
        graves = [d for d in dialogos if d[0] in ("warning", "critical")]
        assert [d[1] for d in graves] == ["Resultados incompletos"]
        assert graves[0][2].startswith("No se pudo guardar «Linealidad CT»") and "la prueba:" not in graves[0][2]
        assert "Guardar todos «Linealidad CT» falló" in log_de_errores.read_text(encoding="utf-8"), "el registro tambien dice cual de las pruebas fue"
        assert _todas(bd_temporal, obj.ref) == 0, "se revierte todo: tampoco se guarda el espesor bueno"
        assert obj.guardar_catphan.isEnabled()

    def test_los_avisos_de_validacion_usan_el_nombre_que_el_fisico_ve(self, bd_temporal, dialogos, log_de_errores, pantallas, tmp_path):
        """Revision de GI.6 (P7): «Falta la categoría requerida: valores_ct» y «Errores de validación para espesor» enseñaban el identificador interno en vez del nombre de la pestaña
        (los demas mensajes de guardado ya usan `etiqueta_de`)."""
        validar = catphan_db.validar_resultados_catphan
        assert validar({}, modo="completo")[1] == ["Falta la prueba requerida: «Espesor de corte»", "Falta la prueba requerida: «Valores CT»",
                                                  "Falta la prueba requerida: «Uniformidad»"]
        assert validar({"espesor": {}, "valores_ct": [], "tamano_pixel": 3, "uniformidad": 5}, modo="individual")[1] == [
            "La prueba «Espesor de corte» no tiene resultados válidos", "La prueba «Valores CT» no tiene resultados válidos",
            "Los resultados de «Tamaño de píxel» no tienen la forma esperada", "Los resultados de «Uniformidad» no tienen la forma esperada"]
        assert validar({"espesor": {"x": 1}}, modo="individual")[1] == ["Faltan datos del espesor promedio en «Espesor de corte»"]
        assert validar({"valores_ct": "texto"}, modo="individual")[1] == ["Los resultados de «Valores CT» no tienen la forma esperada"]
        obj = _pantalla(pantallas, tmp_path, dialogos=dialogos)
        assert obj.guardar_resultado_individual("espesor", {}, output_blob=b"R") is False
        assert [(d[0], d[1]) for d in dialogos] == [("warning", "Validación fallida")]
        assert dialogos[0][2].startswith("Errores de validación para «Espesor de corte»:") and "'espesor'" not in dialogos[0][2]

    def test_con_una_consola_que_no_admite_simbolos_la_pantalla_guarda_y_lo_dice(self, bd_temporal, dialogos, log_de_errores, pantallas, tmp_path, monkeypatch):
        """Revision de GI.6 (P3 / GI6-T7), por la pantalla: un guardado BUENO con una salida ascii dice «se guardó correctamente», no «No se guardó nada»."""
        import io
        obj = _pantalla(pantallas, tmp_path, dialogos=dialogos)
        monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="ascii"))
        assert self._guardar_espesor(obj) is True
        assert [d[1] for d in dialogos if d[0] in ("warning", "critical")] == []
        assert len(_filas_vigentes(bd_temporal, obj.ref)) == 1


# ------------------------------------------------------------------------------------------- tripwires por AST de la pantalla
def _funciones_de_guardado():
    with open(os.path.join(RAIZ, "ui/paginasControles/PruebasMensuales/tac_mensual.py"), encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    return {n.name: n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name in ("guardar_resultado_individual", "guardar_resultados_catphan")}


def test_ningun_dialogo_de_guardado_muestra_el_texto_de_la_excepcion():
    """Ni `str(e)` ni `{e}` ni `{db_error}` dentro de un QMessageBox de las funciones de guardado: el texto crudo (de SQLite o de Python) no llega al fisico."""
    funciones = _funciones_de_guardado()
    assert set(funciones) == {"guardar_resultado_individual", "guardar_resultados_catphan"}
    for nombre, f in funciones.items():
        for llamada in [n for n in ast.walk(f) if isinstance(n, ast.Call) and getattr(n.func, "value", None) is not None
                        and getattr(n.func.value, "id", None) == "QMessageBox"]:
            texto = ast.unparse(llamada)
            assert not any(parte in texto for parte in ("str(e)", "str(db_error)", "{e}", "{db_error}", "format_exc")), (nombre, texto[:120])


def test_ningun_dialogo_de_guardado_lleva_simbolos():
    for nombre, f in _funciones_de_guardado().items():
        for nodo in ast.walk(f):
            if isinstance(nodo, ast.Call) and getattr(getattr(nodo.func, "value", None), "id", None) == "QMessageBox":
                assert not any(s in ast.unparse(nodo) for s in SIMBOLOS), (nombre, ast.unparse(nodo)[:100])


def test_todo_except_exception_de_las_funciones_de_guardado_pasa_por_el_traductor():
    for nombre, f in _funciones_de_guardado().items():
        for h in [n for n in ast.walk(f) if isinstance(n, ast.ExceptHandler) and ast.unparse(n.type) == "Exception"]:
            assert any(isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "_decir_error_de_guardado" for n in ast.walk(h)), (nombre, h.lineno)


def test_ninguna_funcion_de_guardado_llama_a_print():
    """Revision de GI.6 (P3): un `print` dentro de un guardado puede lanzar (un simbolo o un acento con una salida cp1252/ascii: `UnicodeEncodeError`; una salida cerrada: `OSError`) y,
    en el escritor, que corre despues del `commit`, convertia un guardado bueno en uno fallido. Las funciones de guardado avisan con `avisar_consola`, que nunca lanza."""
    for ruta, nombres in (("data/ManejoDatos/catphan_TAC/catphan_db.py", {"guardar_prueba_completa_catphan"}),
                          ("ui/paginasControles/PruebasMensuales/tac_mensual.py", {"guardar_resultado_individual", "guardar_resultados_catphan", "_decir_error_de_guardado"})):
        with open(os.path.join(RAIZ, ruta), encoding="utf-8") as f:
            arbol = ast.parse(f.read())
        funciones = [n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) and n.name in nombres]
        assert {f.name for f in funciones} == nombres
        for f in funciones:
            directos = [n.lineno for n in ast.walk(f) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "print"]
            assert not directos, (f.name, directos)


def test_ningun_guardar_de_una_categoria_salta_filas_en_silencio():
    """Revision de GI.6 (P1): un `continue` dentro de un `guardar_*` es una fila que no se guarda sin que nadie lo sepa. La unica excepcion es el elemento de METADATOS de
    `valor_numero_ct` (sin nombre de material), que no es una fila: lo demas se rechaza (`raise`)."""
    with open(os.path.join(RAIZ, "data/ManejoDatos/catphan_TAC/catphan_db.py"), encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    encontrados = {}
    for f in [n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name.startswith("guardar_") and n.name != "guardar_prueba_completa_catphan"]:
        saltos = [n for n in ast.walk(f) if isinstance(n, ast.Continue)]
        condiciones = [ast.unparse(n.test) for n in ast.walk(f) if isinstance(n, ast.If) and any(isinstance(c, ast.Continue) for c in n.body)]
        if saltos:
            assert len(saltos) == len(condiciones), (f.name, "un `continue` sin condicion salta filas siempre")
            encontrados[f.name] = condiciones
    assert encontrados == {"guardar_valores_ct": ["not material_nombre"]}, encontrados
