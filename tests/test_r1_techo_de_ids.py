"""R.1 (PLAN_PUNTEROS_A_EQUIPOS_11-09.md §2): `_asegurar_secuencias_sin_
duplicados` (E10) solo miraba `sqlite_sequence` DUPLICADA -- una tabla a la
que le FALTA la fila (medido en producción: `equipos`, desde el rebuild del
28-08-2026) no se tocaba nunca, y `AUTOINCREMENT` caía a `MAX(id)+1`,
reciclando ids que punteros vivos en `equipos_medicion`/
`calculadora_dosimetrica` todavía apuntaban (control real: iX 12/08/2026 y
600 31/08/2026, `equipo_id` 78/19/80/81 sin resolver).

Además la propia rutina perdía una fila basura por arranque: `DELETE FROM
sqlite_sequence WHERE name = ?` con `name = NULL` nunca acierta (en SQL,
`= NULL` no es verdad jamás), así que el `INSERT` de más abajo sí corría
cada vez (53 filas `name IS NULL` acumuladas, medido).

Exigencia explícita del físico (11-09): la protección tiene que servir para
CUALQUIER BD, con cualquier cantidad de equipos borrados y cualesquiera que
sean -- no un umbral escrito a mano. El techo se reconstruye de tres
evidencias que la propia base ya contiene (§0.8 del plan): la fila de
`sqlite_sequence` si sobrevive, `MAX(id)` de la tabla, y `MAX(columna)` de
cada puntero VIVO hacia ella -- un puntero que existe es la prueba de que
ese id se entregó alguna vez, y es TODA la evidencia que hace falta: un id
que nadie apunta no puede adoptar a nadie si se recicla (demostrado en el
plan con una prueba de estrés de 15 semillas x 4 rondas de borrados
aleatorios, §0.11).
"""
import random
import sqlite3

import pytest

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    """Esquema COMPLETO (equipos, equipos_medicion, calculadora_dosimetrica,
    controles, sqlite_sequence...) via el arranque real de `Conexion()`,
    igual que `tests/test_e10_restrict.py`."""
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    conexion.con.close()
    Conexion._instance = None
    return ruta


def _reabrir(ruta):
    """Crea una Conexion() NUEVA sobre `ruta` -- dispara el arranque
    (incluida _asegurar_secuencias_sin_duplicados) otra vez, mismo patrón
    que test_e10_restrict.py::test_preserva_el_contador_autoincrement."""
    Conexion._instance = None
    return Conexion()


def _cerrar(conexion):
    conexion.con.close()
    Conexion._instance = None


def _crudo(ruta):
    return sqlite3.connect(ruta)


class TestCasoRealMedido:
    """Réplica exacta del control 43 (iX 12/08/2026): equipos con MAX(id)=79
    y un equipo_id=81 huérfano en equipos_medicion (ese id existió, se borró,
    y sqlite_sequence perdió su fila para 'equipos' en la reconstrucción)."""

    def test_el_proximo_alta_no_reutiliza_un_id_apuntado(self, bd_temporal):
        ruta = bd_temporal
        con = _crudo(ruta)
        con.execute(
            "INSERT INTO equipos (id, equip_type, model, serie, activo) "
            "VALUES (79, 'Cámara de ionización', 'N31010', '1825', 1)")
        con.execute(
            "INSERT INTO equipos (id, equip_type, model, serie, activo) "
            "VALUES (81, 'Cámara de ionización', 'N31010', '1822', 1)")
        con.execute("DELETE FROM equipos WHERE id = 81")
        # el rebuild real perdió la fila de 'equipos' en sqlite_sequence
        con.execute("DELETE FROM sqlite_sequence WHERE name = 'equipos'")
        con.execute(
            "INSERT INTO controles (id, equipo, control, fecha, activo) "
            "VALUES (1, 'Clinac ix', 'Mensual', '05/2026', 1)")
        con.execute(
            "INSERT INTO equipos_medicion (ref, tipo_camara, equip_type, "
            "model, serie, calibr_fact, fecha_calibr, equipo_id, activo) "
            "VALUES (1, 'Principal', 'Cámara de ionización', 'N31010', "
            "'1822', 0.3036, '21/07/2025', 81, 1)")
        con.commit()
        con.close()

        conexion = _reabrir(ruta)
        try:
            cur = conexion.con.cursor()
            cur.execute(
                "INSERT INTO equipos (equip_type, model, serie, activo) "
                "VALUES ('Cámara de ionización', 'NUEVA', 'X', 1)")
            nuevo_id = cur.lastrowid
        finally:
            _cerrar(conexion)

        assert nuevo_id == 82  # max(79, 81) + 1 -- hoy da 80


class TestGeneralidadBorradosAleatorios:
    """El físico exigió (11-09): la protección debe servir para CUALQUIER
    BD, con cualquier cantidad de equipos borrados y cualesquiera que sean
    -- no un umbral escrito a mano. Escenarios sintéticos con semilla fija
    (reproducibles): se verifica la PROPIEDAD, no un número concreto."""

    @pytest.mark.parametrize("semilla", range(8))
    def test_ningun_id_nuevo_coincide_con_un_puntero_existente(
            self, bd_temporal, semilla):
        ruta = bd_temporal
        rnd = random.Random(semilla)
        con = _crudo(ruta)
        con.execute(
            "INSERT INTO controles (id, equipo, control, fecha, activo) "
            "VALUES (1, 'Clinac ix', 'Mensual', '01/2026', 1)")

        n_equipos = rnd.randint(5, 40)
        ids = []
        for i in range(n_equipos):
            cur = con.execute(
                "INSERT INTO equipos (equip_type, model, serie, activo) "
                "VALUES ('Cámara de ionización', ?, ?, 1)",
                (f"M{i}", f"S{i}"))
            ids.append(cur.lastrowid)

        # borrado variado: entre 30% y 70% al azar, como pidió el físico
        k = max(1, int(n_equipos * rnd.uniform(0.3, 0.7)))
        borrados = rnd.sample(ids, k)
        for eid in borrados:
            con.execute("DELETE FROM equipos WHERE id = ?", (eid,))

        # punteros hacia equipos borrados (huérfanos) Y hacia equipos vivos
        # (el caso normal, A092535) -- ambos deben quedar protegidos
        vivos = [i for i in ids if i not in borrados]
        candidatos_puntero = list(borrados) + list(vivos)
        rnd.shuffle(candidatos_puntero)
        n_punteros = rnd.randint(0, len(candidatos_puntero))
        punteros = candidatos_puntero[:n_punteros]
        for j, eid in enumerate(punteros):
            con.execute(
                "INSERT INTO equipos_medicion (ref, tipo_camara, equip_type, "
                "model, serie, calibr_fact, fecha_calibr, equipo_id, activo) "
                "VALUES (1, ?, 'Cámara de ionización', 'M', 'S', 1, "
                "'01/01/2025', ?, 1)", (f"T{j}", eid))

        # a veces el contador se pierde del todo (rebuild real), a veces no
        if rnd.random() < 0.5:
            con.execute("DELETE FROM sqlite_sequence WHERE name = 'equipos'")
        con.commit()
        con.close()

        protegidos = set(punteros)  # cualquier id alguna vez apuntado

        conexion = _reabrir(ruta)
        try:
            cur = conexion.con.cursor()
            nuevos = []
            for i in range(3):
                cur.execute(
                    "INSERT INTO equipos (equip_type, model, serie, activo) "
                    "VALUES ('Cámara de ionización', ?, ?, 1)",
                    (f"NUEVO{i}", f"NS{i}"))
                nuevos.append(cur.lastrowid)
        finally:
            _cerrar(conexion)

        choques = protegidos & set(nuevos)
        assert not choques, (
            f"semilla={semilla}: ids nuevos {nuevos} chocan con punteros "
            f"ya existentes {choques} (protegidos={sorted(protegidos)})")


class TestFugaDeFilasNulasSeCierra:
    def test_filas_basura_no_se_acumulan_entre_arranques(self, bd_temporal):
        ruta = bd_temporal
        con = _crudo(ruta)
        con.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (NULL, 5)")
        con.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (NULL, 9)")
        con.commit()
        con.close()

        for vuelta in range(3):
            conexion = _reabrir(ruta)
            _cerrar(conexion)
            con = _crudo(ruta)
            n_nulas = con.execute(
                "SELECT COUNT(*) FROM sqlite_sequence "
                "WHERE name IS NULL").fetchone()[0]
            con.close()
            assert n_nulas == 0, f"arranque #{vuelta + 1}: quedaron filas NULL"


class TestIdempotencia:
    def test_dos_pasadas_seguidas_no_cambian_nada(self, bd_temporal):
        ruta = bd_temporal
        _cerrar(_reabrir(ruta))
        con = _crudo(ruta)
        antes = con.execute(
            "SELECT name, seq FROM sqlite_sequence ORDER BY name").fetchall()
        con.close()

        _cerrar(_reabrir(ruta))
        con = _crudo(ruta)
        despues = con.execute(
            "SELECT name, seq FROM sqlite_sequence ORDER BY name").fetchall()
        con.close()

        assert antes == despues


class TestNuncaBaja:
    def test_contador_ya_adelantado_no_se_retrocede(self, bd_temporal):
        """Un salto de ids es inocuo; una reutilización no -- mismo
        criterio que E10 ya aplicaba a los duplicados."""
        ruta = bd_temporal
        con = _crudo(ruta)
        con.execute("DELETE FROM sqlite_sequence WHERE name = 'equipos'")
        con.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('equipos', 200)")
        con.execute(
            "INSERT INTO controles (id, equipo, control, fecha, activo) "
            "VALUES (1, 'Clinac ix', 'Mensual', '01/2026', 1)")
        con.execute(
            "INSERT INTO equipos_medicion (ref, tipo_camara, equip_type, "
            "model, serie, calibr_fact, fecha_calibr, equipo_id, activo) "
            "VALUES (1, 'Principal', 'Cámara de ionización', 'M', 'S', 1, "
            "'01/01/2025', 81, 1)")
        con.commit()
        con.close()

        conexion = _reabrir(ruta)
        try:
            seq = conexion.con.execute(
                "SELECT seq FROM sqlite_sequence "
                "WHERE name='equipos'").fetchone()[0]
        finally:
            _cerrar(conexion)

        assert seq == 200  # el techo reconstruido (81) es MENOR: no baja


class TestDuplicadosSiguenColapsando:
    """No romper lo que E10 arreglaba (test_e10_restrict.py cubre esto para
    'controles'; aquí se repite sobre 'equipos' para no dejarlo implícito)."""

    def test_no_se_rompe_lo_que_e10_arreglaba(self, bd_temporal):
        ruta = bd_temporal
        con = _crudo(ruta)
        con.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('equipos', 50)")
        con.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('equipos', 999)")
        con.commit()
        con.close()

        conexion = _reabrir(ruta)
        try:
            filas = conexion.con.execute(
                "SELECT seq FROM sqlite_sequence "
                "WHERE name='equipos'").fetchall()
        finally:
            _cerrar(conexion)

        assert filas == [(999,)]  # una sola fila, con el máximo


class TestRobustezAnteEsquemasIncompletos:
    """BD sin `calculadora_dosimetrica`, sin la columna `equipo_id`, o sin
    `sqlite_sequence` en absoluto -- ninguna debe tronar. Se prueba contra
    un `Conexion` "desnudo" (sin pasar por __init__, que crea el esquema
    completo) para poder declarar esquemas mínimos y a propósito
    incompletos, como las BD de julio que el físico sigue abriendo."""

    @staticmethod
    def _instancia_desnuda(con):
        obj = Conexion.__new__(Conexion)
        obj.con = con
        return obj

    def test_sin_calculadora_dosimetrica_no_truena(self, tmp_path):
        con = sqlite3.connect(str(tmp_path / "bare1.db"))
        con.executescript("""
            CREATE TABLE equipos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, model TEXT, activo INTEGER);
            CREATE TABLE equipos_medicion (
                ref INTEGER, id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipo_id INTEGER);
            INSERT INTO equipos_medicion (ref, equipo_id) VALUES (1, 50);
        """)
        con.commit()
        obj = self._instancia_desnuda(con)
        obj._asegurar_secuencias_sin_duplicados()  # no debe tronar
        fila = con.execute(
            "SELECT seq FROM sqlite_sequence WHERE name='equipos'").fetchone()
        assert fila == (50,)
        con.close()

    def test_sin_columna_equipo_id_no_truena(self, tmp_path):
        con = sqlite3.connect(str(tmp_path / "bare2.db"))
        con.executescript("""
            CREATE TABLE equipos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, model TEXT, activo INTEGER);
            CREATE TABLE equipos_medicion (
                ref INTEGER, id INTEGER PRIMARY KEY AUTOINCREMENT);
        """)
        con.commit()
        obj = self._instancia_desnuda(con)
        obj._asegurar_secuencias_sin_duplicados()  # no debe tronar
        con.close()

    def test_sin_sqlite_sequence_en_absoluto_no_truena(self, tmp_path):
        con = sqlite3.connect(str(tmp_path / "bare3.db"))
        con.executescript(
            "CREATE TABLE equipos (id INTEGER PRIMARY KEY, model TEXT);")
        con.commit()
        obj = self._instancia_desnuda(con)
        obj._asegurar_secuencias_sin_duplicados()  # no debe tronar
        con.close()
