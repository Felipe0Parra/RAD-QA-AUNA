"""J2 (companion de J1, PLAN_HALCYON_SELECCION_CARPETA_21-07): la ingesta de
Halcyon deja rastro en `audit_log`.

Antes de esta tarea, `createDB` -- el único punto real de escritura de la
tabla `halcyon` (confirmado: `addInfo` era la única función que disparaba el
guardado, ligada a `dateChanged` en `ui/paginasControles/PruebasDiarias/
halcyon.py:129`; no existe un botón "Enviar" que vuelva a escribir -- ese
botón solo genera el PDF, ver `button_click`) -- no llamaba a `registrar()`,
a diferencia del guardado manual de `load.py:add_info`. Ahora, tras un
`createDB` exitoso, se registra QUÉ carpeta MPC se usó -- justo lo que J1
cambia (antes se elegía por hora máxima, ahora por completitud).

H3 (PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md §H3) partió `addInfo` en dos:
`previsualizar_halcyon` (dateChanged, cero escrituras) y `agregar_halcyon`
("Agregar", el único que guarda) -- este archivo prueba `agregar_halcyon`,
que es quien conserva el guardado y la auditoría que J2 fijó aquí.

`createDB`/`Conexion` se mockean aquí: el pipeline CSV -> widgets -> columnas
reales de la tabla `halcyon` es una pieza aparte, ya en producción, sin
relación con J1/J2 -- lo único bajo prueba es que, en el camino de éxito,
`_registrar_auditoria` se invoca con los datos correctos (y que NO se invoca
cuando la fecha ya existe, rama que tampoco llama a `createDB`).
"""
import pytest

import data.ManejoDatos.obtenerDatosHalcyon as halcyon_mod

HEADER_Y_FILAS = (
    "Name [Unit], Value, Threshold, Evaluation Result\n"
    "IsoCenterGroup/Iso/MV/Size [mm], 0.67, 0.9, Pass\n"
    "BeamOutputGroup/Beam/Output/Change [%], 0.3, 2.0, Pass\n"
)


def _patch_conexion(monkeypatch, fila_existente):
    """fila_existente simula el fetchone() de `SELECT * FROM halcyon WHERE
    date=?` -- None si nunca se guardó esa fecha (toma la rama createDB)."""
    class _Cursor:
        def execute(self, *a, **k):
            pass

        def fetchone(self):
            return fila_existente

    class _DB:
        def cursor(self):
            return _Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Conexion:
        def conectar(self):
            return _DB()

    monkeypatch.setattr(halcyon_mod.con, "Conexion", _Conexion)


@pytest.fixture
def carpeta_mpc_falsa(tmp_path):
    carpeta = tmp_path / "HAL-TRT-SN1161-2026-07-01-05-19-31-0000-GeometryCheckTemplate6xFFFMVkV"
    carpeta.mkdir()
    (carpeta / "Results.csv").write_text(HEADER_Y_FILAS, encoding="utf-8")
    return str(carpeta)


@pytest.fixture
def preparar_agregar_halcyon(monkeypatch, tmp_path, carpeta_mpc_falsa):
    monkeypatch.chdir(tmp_path)  # aisla el 'infoWidgets.csv' que agregar_halcyon escribe con ruta relativa
    monkeypatch.setattr(halcyon_mod, "seleccionar_carpeta_mpc",
                         lambda ruta_base, fecha: carpeta_mpc_falsa)
    # H1-bis (2026-08-06): createDB ahora devuelve bool (antes no devolvía
    # nada) -- el mock debe imitar el camino de ÉXITO, o agregar_halcyon lo
    # trata como fallo y muestra QMessageBox.critical (sin mockear aquí a
    # propósito: si algo lo dispara sin querer, debe fallar ruidoso).
    monkeypatch.setattr(halcyon_mod, "createDB", lambda *a, **k: True)
    monkeypatch.setattr(halcyon_mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))


class TestAgregarHalcyonAuditaLaIngesta:
    def test_createDB_exitoso_registra_en_audit_log(self, preparar_agregar_halcyon, monkeypatch):
        _patch_conexion(monkeypatch, fila_existente=None)
        llamadas = []
        monkeypatch.setattr(halcyon_mod, "_registrar_auditoria",
                             lambda *a, **k: llamadas.append((a, k)))

        halcyon_mod.agregar_halcyon(None, "2026-07-01", "fisico_prueba")

        assert len(llamadas) == 1
        args, kwargs = llamadas[0]
        assert args == ("fisico_prueba", "guardar", "halcyon")
        assert kwargs["ref"] == "2026-07-01"
        assert "GeometryCheckTemplate6xFFFMVkV" in kwargs["detalle"]

    def test_fecha_ya_existente_no_duplica_ni_audita(self, preparar_agregar_halcyon, monkeypatch):
        _patch_conexion(monkeypatch, fila_existente=(1, "2026-07-01"))
        llamadas = []
        monkeypatch.setattr(halcyon_mod, "_registrar_auditoria",
                             lambda *a, **k: llamadas.append((a, k)))

        halcyon_mod.agregar_halcyon(None, "2026-07-01", "fisico_prueba")

        assert llamadas == []
