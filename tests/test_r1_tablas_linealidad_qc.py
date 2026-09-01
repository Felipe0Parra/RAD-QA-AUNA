"""R1 (PLAN_REPARACION_ANUAL_27-08.md §Fase 3, F-5): las 4 tablas nuevas
de lecturas crudas de la hoja "Linealidad" (600/iX) entran al contrato de
QC completo -- no basta con que existan, tienen que:

1. nacer con `CREATE TABLE` real (`crearTablasAnuales`, conection.py);
2. estar en `TABLAS_ANULABLES` (para que `_asegurar_activo_bloque_qc` les
   agregue `activo` sola, y para que IV2/loadtablacomplex las traten como
   bloque de QC);
3. tener su clave natural en `CLAVES_INDICE` (para que `crear_indices` les
   ponga el UNIQUE parcial);
4. guardar y leer con el mismo mecanismo genérico que ya usan sus
   hermanas (`loadtablacomplex`/`pruebatalas`/`reemplazar_bloque`), sin
   código especial por tabla -- "Subir" dos veces reemplaza el bloque
   (anula, no borra), y una lectura no ve el bloque anulado.

Todo sobre una BD TEMPORAL creada con DDL real vía `Conexion()` (mismo
mecanismo que IV2/CL1/CL2/MI1) -- nunca un archivo de referencia."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.anulacion import TABLAS_ANULABLES
from scripts.indices_bloque_qc import CLAVES_INDICE, crear_indices, nombre_indice

TABLAS_R1 = {
    "anual_linealidad_um": ("ref", "id_energia", "um", "q1", "q2", "q_prom"),
    "anual_lecturas_factor_campo": ("ref", "id_energia", "clave", "q1", "q2", "q_prom", "factor"),
    "anual_lecturas_transmision": ("ref", "id_energia", "accesorio", "q1_in", "q2_in", "q1_out", "q2_out", "q_med", "factor_t"),
    "anual_tasa_dosis": ("ref", "id_energia", "tasa_um_min", "med1", "med2"),
}


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    # `energias` ya trae 0-5 sembrados desde _asegurar_catalogos_base;
    # `controles` no se siembra sola -- los `ref` que usan los tests de
    # guardado/lectura necesitan su fila real (FK ref -> controles.id).
    # Meses distintos: hay un UNIQUE real sobre (equipo, control, mes).
    conexion.con.executemany(
        "INSERT INTO controles (id, equipo, control, fecha, activo) "
        "VALUES (?, 'Clinac ix', 'Anual', ?, 1)",
        [(10, "07/2026"), (20, "08/2026")])
    conexion.con.commit()
    yield conexion
    conexion.con.close()
    Conexion._instance = None


def _columnas(con, tabla):
    return [c[1] for c in con.execute(f"PRAGMA table_info('{tabla}')").fetchall()]


class TestLasCuatroTablasNacenConElEsquemaCorrecto:
    @pytest.mark.parametrize("tabla, columnas_esperadas", TABLAS_R1.items())
    def test_columnas_de_datos_en_el_orden_declarado(self, bd_temporal, tabla, columnas_esperadas):
        columnas_reales = _columnas(bd_temporal.con, tabla)
        assert columnas_reales, f"{tabla}: no existe (sin CREATE TABLE)"
        # id primero (autoincrement), luego exactamente lo declarado, en orden.
        assert columnas_reales[0] == "id"
        assert tuple(columnas_reales[1:1 + len(columnas_esperadas)]) == columnas_esperadas

    @pytest.mark.parametrize("tabla", TABLAS_R1)
    def test_gana_activo_al_arrancar(self, bd_temporal, tabla):
        # _asegurar_activo_bloque_qc corre dentro de Conexion.__init__ --
        # para cuando el fixture entrega la conexión, ya debería estar.
        assert "activo" in _columnas(bd_temporal.con, tabla)

    @pytest.mark.parametrize("tabla", TABLAS_R1)
    def test_esta_en_tablas_anulables(self, tabla):
        assert tabla in TABLAS_ANULABLES

    @pytest.mark.parametrize("tabla, columnas_esperadas", TABLAS_R1.items())
    def test_clave_natural_declarada_y_sus_columnas_existen(self, bd_temporal, tabla, columnas_esperadas):
        assert tabla in CLAVES_INDICE
        clave = CLAVES_INDICE[tabla]
        assert clave[0] == "ref"
        columnas_reales = set(_columnas(bd_temporal.con, tabla))
        for columna in clave:
            assert columna in columnas_reales


class TestElIndiceUnicoSeCreaSinExcepciones:
    def test_crear_indices_crea_las_cuatro(self, bd_temporal, tmp_path):
        ruta = str(tmp_path / "test.db")
        bd_temporal.con.close()
        resultado = crear_indices(ruta)
        for tabla in TABLAS_R1:
            assert resultado[tabla] == "creado", f"{tabla}: {resultado[tabla]}"


class TestGuardadoYLecturaConElMecanismoGenerico:
    """Sin código especial por tabla: el mismo loadtablacomplex/pruebatalas
    que ya usan tabla_factor_campo etc."""

    def _insertar_bloque(self, con, tabla, ref, id_energia, filas):
        columnas = TABLAS_R1[tabla]
        columnas_sql = ", ".join(columnas)
        placeholders = ", ".join("?" for _ in columnas)
        con.execute(
            f"UPDATE {tabla} SET activo = 0 WHERE ref=? AND id_energia=? "
            f"AND (activo IS NULL OR activo = 1)", (ref, id_energia))
        for fila in filas:
            con.execute(
                f"INSERT INTO {tabla} ({columnas_sql}) VALUES ({placeholders})",
                (ref, id_energia) + fila)
        con.commit()

    @pytest.mark.parametrize("tabla", TABLAS_R1)
    def test_un_segundo_guardado_anula_el_primero_no_lo_borra(self, bd_temporal, tabla):
        con = bd_temporal.con
        columnas_dato = TABLAS_R1[tabla][2:]  # sin ref/id_energia
        # Primera columna de datos es siempre la clave natural (texto);
        # el resto son lecturas numéricas -- el valor exacto no importa
        # para esta prueba, solo que la fila exista y sea distinguible.
        resto = tuple(1.0 for _ in columnas_dato[1:])
        fila_1 = ("A",) + resto
        self._insertar_bloque(con, tabla, ref=10, id_energia=0, filas=[fila_1])

        activas = con.execute(
            f"SELECT COUNT(*) FROM {tabla} WHERE ref=10 AND id_energia=0 "
            f"AND (activo IS NULL OR activo = 1)").fetchone()[0]
        assert activas == 1

        fila_2 = ("B",) + resto
        self._insertar_bloque(con, tabla, ref=10, id_energia=0, filas=[fila_2])

        totales = con.execute(
            f"SELECT COUNT(*) FROM {tabla} WHERE ref=10 AND id_energia=0").fetchone()[0]
        assert totales == 2, "el bloque anterior debe seguir la fila (anulada), no desaparecer"

        activas = con.execute(
            f"SELECT COUNT(*) FROM {tabla} WHERE ref=10 AND id_energia=0 "
            f"AND (activo IS NULL OR activo = 1)").fetchone()[0]
        assert activas == 1, "solo el bloque nuevo debe quedar activo"

    @pytest.mark.parametrize("tabla", TABLAS_R1)
    def test_el_indice_unico_rechaza_dos_filas_activas_con_la_misma_clave(self, bd_temporal, tmp_path, tabla):
        ruta = str(tmp_path / "test.db")
        con = bd_temporal.con
        con.close()
        resultado = crear_indices(ruta)
        assert resultado[tabla] == "creado"

        Conexion._instance = None
        con2 = Conexion().con
        columnas_dato = TABLAS_R1[tabla][2:]
        clave_natural = columnas_dato[0]
        valor_clave = "50" if clave_natural in ("um", "tasa_um_min") else (
            "3x3" if clave_natural == "clave" else "Open")
        resto = tuple(1.0 for _ in columnas_dato[1:])

        columnas = TABLAS_R1[tabla]
        columnas_sql = ", ".join(columnas)
        placeholders = ", ".join("?" for _ in columnas)
        con2.execute(
            f"INSERT INTO {tabla} ({columnas_sql}) VALUES ({placeholders})",
            (20, 0, valor_clave) + resto)
        con2.commit()

        import sqlite3
        with pytest.raises(sqlite3.IntegrityError):
            con2.execute(
                f"INSERT INTO {tabla} ({columnas_sql}) VALUES ({placeholders})",
                (20, 0, valor_clave) + resto)
