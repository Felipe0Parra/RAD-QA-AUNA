"""H2.4 (auditoría 2026-07-14) -- audit trail mínimo (services/audit_minimo.py).

Antes de esta tarea, `services/auditorias.py`/`decoradores_audit.py` existían
pero 100% comentados: la tabla `audit_log` nunca se creaba y no había forma de
reconstruir quién/qué/cuándo en un guardado. `registrar()` es el único punto
de entrada nuevo, deliberadamente simple (sin AuditEngine/señales/excepthook).

Principio central a probar: la inserción es SIEMPRE best-effort -- un fallo
al auditar (BD bloqueada, ruta inválida, lo que sea) nunca debe propagar una
excepción hacia quien llama, porque quien llama es siempre el código que
JUSTO terminó de guardar el dato real (calculadora, mensual, diario, equipos).
Si `registrar()` pudiera lanzar, un audit_log roto podría tumbar guardados
que nada tienen que ver con la auditoría misma.
"""
import os
import sqlite3
import tempfile

import pytest

import data.ManejoDatos.conection as conection_mod
import services.audit_minimo as audit_minimo


@pytest.fixture
def bd_temporal(monkeypatch):
    ruta = tempfile.mktemp(suffix=".db")
    # Parcheado vía el MÓDULO conection (no un `from ... import
    # ruta_base_datos` capturado dentro de audit_minimo) -- es justo lo que
    # hacen add_info/Conexion en sus propios tests (ver test_reporte_diario_
    # h22.py) y lo que un guardado real necesita ver reflejado. Ver
    # test_registrar_ve_el_parche_de_conection_no_uno_propio más abajo: esa
    # es la regresión concreta que este fixture previene silenciosamente.
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    yield ruta
    if os.path.exists(ruta):
        os.remove(ruta)


class TestRegistrarUsaLaRutaVigenteDeConection:
    """Regresión concreta encontrada al implementar H2.4: la primera versión
    de audit_minimo.py hacía `from data.ManejoDatos.conection import
    ruta_base_datos`, que captura el OBJETO función en el momento del
    import. Cuando un test (o `add_info`/`guardar_db` en producción bajo
    otro contexto) parchea `conection_mod.ruta_base_datos` con monkeypatch,
    esa referencia ya capturada no se entera -- `registrar()` seguía
    resolviendo la ruta REAL de desarrollo (Codigo_radqa/BaseDatosQA.db,
    ~20KB, DISTINTA de la BD de producción real de ~32MB en AUNA_2026_2/)
    en vez de la BD temporal del test, y creaba ahí un archivo huérfano con
    audit_log a través de sucesivas corridas de la suite -- confirmado y
    limpiado durante esta misma tarea. Sin este test, la fuga es silenciosa:
    todos los `registrar()` de esta suite "pasan" igual porque nunca lanzan,
    solo escriben en el lugar equivocado."""

    def test_registrar_ve_el_parche_de_conection_no_uno_propio(self, bd_temporal):
        audit_minimo.registrar("fisico_prueba", "guardar", "t", ref="1")

        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        con.close()
        assert n == 1, (
            "registrar() no escribió en la BD temporal parcheada -- "
            "¿volvió a capturar ruta_base_datos por valor en vez de vía el "
            "módulo conection?")

    def test_ruta_db_explicita_tiene_prioridad(self, bd_temporal, tmp_path):
        """La calculadora (dialogs.py:guardar_db) NO usa Conexion().conectar()
        -- guarda vía DosisService, con su propio patrón de conexión (doble
        patrón, H2.5 pendiente). Pasa `ruta_db` explícito para que la
        auditoría caiga en la MISMA base que su guardado, sin depender de
        que `conection_mod.ruta_base_datos` esté parcheado a esa ruta."""
        otra_ruta = str(tmp_path / "otra.db")
        audit_minimo.registrar("x", "guardar", "calculadora_dosimetrica",
                               ruta_db=otra_ruta)

        con = sqlite3.connect(otra_ruta)
        n = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        con.close()
        assert n == 1

        # bd_temporal (la ruta "por defecto" parcheada en conection) NO debe
        # haber recibido nada -- confirma que ruta_db realmente prevalece.
        con = sqlite3.connect(bd_temporal)
        tablas = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        con.close()
        assert ("audit_log",) not in tablas


class TestRegistrarEscribeLaFila:
    def test_crea_la_tabla_e_inserta(self, bd_temporal):
        audit_minimo.registrar("fisico_prueba", "guardar", "calculadora_dosimetrica",
                               ref="15/07/2026|IX", detalle="test")

        con = sqlite3.connect(bd_temporal)
        filas = con.execute(
            "SELECT usuario, accion, tabla, ref, detalle FROM audit_log").fetchall()
        con.close()
        assert filas == [("fisico_prueba", "guardar", "calculadora_dosimetrica",
                          "15/07/2026|IX", "test")]

    def test_timestamp_formato_iso_ordenable(self, bd_temporal):
        """ISO 8601 (no dd/MM/yyyy) -- ordena bien como texto y evita la
        ambigüedad de fechas mixtas ya detectada en el catálogo de equipos
        (H2.6: "5/02/2024" vs "05/02/2024")."""
        audit_minimo.registrar("x", "guardar")
        con = sqlite3.connect(bd_temporal)
        (marca,) = con.execute("SELECT timestamp FROM audit_log").fetchone()
        con.close()
        import datetime
        datetime.datetime.strptime(marca, "%Y-%m-%d %H:%M:%S")  # no debe lanzar

    def test_usuario_none_no_revienta(self, bd_temporal):
        """Contextos sin usuario resuelto (p.ej. tests, o self.main_window sin
        user_id) deben registrar igual -- mejor auditar sin usuario que no
        auditar nada."""
        audit_minimo.registrar(None, "guardar", "equipos", ref="N31010/1822")
        con = sqlite3.connect(bd_temporal)
        (usuario,) = con.execute("SELECT usuario FROM audit_log").fetchone()
        con.close()
        assert usuario is None

    def test_dos_registros_consecutivos_no_chocan(self, bd_temporal):
        """CREATE TABLE IF NOT EXISTS se ejecuta en cada llamada -- confirma
        que no revienta al re-ejecutarse sobre una tabla ya creada."""
        audit_minimo.registrar("a", "guardar", "t1", ref="1")
        audit_minimo.registrar("b", "actualizar", "t2", ref="2")
        con = sqlite3.connect(bd_temporal)
        n = con.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        con.close()
        assert n == 2


class TestFalloDeAuditoriaNoPropaga:
    """El corazón de H2.4: un fallo al auditar NUNCA debe lanzar hacia quien
    llama -- ver docstring del módulo."""

    def test_ruta_invalida_no_lanza(self):
        # No debe lanzar -- si lanzara, tumbaría el guardado principal que
        # llamó a registrar() justo después de guardar su propio dato.
        audit_minimo.registrar("x", "guardar", "cualquier_tabla",
                               ruta_db="/ruta/que/no/existe/ni/puede/crearse.db")

    def test_sqlite_connect_roto_no_lanza(self, monkeypatch):
        def _connect_roto(*a, **k):
            raise sqlite3.OperationalError("simulado: database is locked")
        monkeypatch.setattr(audit_minimo.sqlite3, "connect", _connect_roto)
        audit_minimo.registrar("x", "guardar", "cualquier_tabla")
