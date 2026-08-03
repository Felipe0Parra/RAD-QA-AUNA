"""I4 (PLAN §10): ensayo integral de la incorporación de una BD de formato
viejo del MISMO LINAJE que producción -- el escenario exacto que describió el
físico ("como la BD de producción original, antes de tocarla, pero con más
registros de QC").

El artefacto de prueba es el que el propio físico incorporó para esto
(2026-07-24): `AUNA_2026_2/BaseDatosQA(A_Ajustar).db` -- la producción
genuina en su formato pre-TODO, verificado por inspección directa: 68 tablas
(sin `angulos_entre_lineas_starshot` NI `audit_log`), sin `controles.activo`,
sin las 5 columnas nuevas de `calculadora_dosimetrica`, con los 7 centinelas
`' ---- '`, con el catálogo de equipos en el estado PRE-saneamiento
(id13 con las condiciones ambientales 20.9/98.91, id16 con la escala 46670,
los duplicados vivos, etc.) y con MÁS registros de QC que la producción
actual (27 controles vs 24).

Si el archivo no está en esta máquina, los tests se saltan honestamente
(skipif granular, lección HI-0). SIEMPRE se trabaja sobre una COPIA en tmp --
el archivo del físico jamás se toca (verificado con md5 en el propio test).
"""
import hashlib
import os
import shutil
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scripts.migrar_bd_a_estandar import migrar

RUTA_BD_A_AJUSTAR = os.path.join(
    os.path.dirname(__file__), "..", "..", "BaseDatosQA(A_Ajustar).db")

# Verdad terreno del artefacto, medida por inspección directa el 2026-07-24
# (no asumida): si el físico algún día reemplaza el archivo por otra copia
# con más QC, estos números cambian y los asserts que dependen de ellos se
# ajustan -- por eso el fixture guarda el md5 del archivo tal como se validó.
QC_ESPERADO = {"controles": 27, "dosimetriaMen": 37, "preguntas": 14,
               "tamano_campo": 68, "pruebas": 35, "calculadora_dosimetrica": 1}
CENTINELAS_ESPERADOS = 7
CORRECCIONES_EQUIPOS_ESPERADAS = 31  # 23 de H2.6/H2.10 + 8 de G9/G7 (2026-07-31), todos aplican


def _md5(ruta):
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


@pytest.fixture
def copia_bd_formato_viejo(tmp_path):
    if not os.path.isfile(RUTA_BD_A_AJUSTAR):
        pytest.skip("BaseDatosQA(A_Ajustar).db no está en esta máquina")
    md5_antes = _md5(RUTA_BD_A_AJUSTAR)
    ruta = str(tmp_path / "bd_formato_viejo.db")
    shutil.copy(RUTA_BD_A_AJUSTAR, ruta)
    yield ruta
    # el archivo de referencia del físico permanece intacto, byte a byte
    assert _md5(RUTA_BD_A_AJUSTAR) == md5_antes


class TestIncorporacionDeLaBdRealFormatoViejo:

    def test_end_to_end_queda_al_estandar_sin_perder_nada(self, copia_bd_formato_viejo):
        ruta = copia_bd_formato_viejo

        # estado "viejo" confirmado antes de migrar (no asumido)
        con = sqlite3.connect(ruta)
        cols_controles = [c[1] for c in con.execute("PRAGMA table_info(controles)").fetchall()]
        tablas_antes = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        t_cal_13 = con.execute("SELECT t_cal FROM equipos WHERE id = 13").fetchone()[0]
        con.close()
        assert "activo" not in cols_controles
        assert "angulos_entre_lineas_starshot" not in tablas_antes
        assert "audit_log" not in tablas_antes  # anterior incluso a H2.4
        assert t_cal_13 == 20.9  # equipos aún con las condiciones ambientales

        resultado = migrar(ruta, aplicar=True, usuario="ensayo_i4")

        # 1) esquema al estándar
        con = sqlite3.connect(ruta)
        cols_controles = [c[1] for c in con.execute("PRAGMA table_info(controles)").fetchall()]
        cols_calc = [c[1] for c in con.execute(
            "PRAGMA table_info(calculadora_dosimetrica)").fetchall()]
        tablas = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        sentinelas = con.execute(
            "SELECT COUNT(*) FROM controles WHERE user_id_f2 = ' ---- '").fetchone()[0]
        t_cal_13, p_cal_13 = con.execute(
            "SELECT t_cal, p_cal FROM equipos WHERE id = 13").fetchone()
        n_equipos = con.execute("SELECT COUNT(*) FROM equipos").fetchone()[0]
        auditadas = con.execute(
            "SELECT COUNT(*) FROM audit_log WHERE accion = 'saneamiento_h26'").fetchone()[0]
        con.close()
        assert "activo" in cols_controles
        assert {"protocolo_trs398", "r50_medido", "pdd_zref_electrones",
                "energia", "vigente"} <= set(cols_calc)
        assert {"angulos_entre_lineas_starshot", "audit_log"} <= tablas

        # 2) los 7 centinelas reales normalizados
        assert resultado["sentinelas_normalizadas"] == CENTINELAS_ESPERADOS
        assert sentinelas == 0

        # 3) ni una fila de QC perdida (los conteos reales del artefacto,
        #    incluidos los 3 controles que producción actual NO tiene)
        assert resultado["qc_antes"] == QC_ESPERADO
        assert resultado["qc_despues"] == QC_ESPERADO

        # 4) equipos: los 23 cambios de certificados aplican TODOS, cero
        #    deriva (prueba de linaje), ninguna fila borrada, la corrección
        #    dosimétrica clave verificada en el dato (id13 → referencia),
        #    y cada corrección auditada en el audit_log recién creado
        assert len(resultado["equipos"]["aplicados"]) == CORRECCIONES_EQUIPOS_ESPERADAS
        assert resultado["equipos"]["con_deriva"] == []
        assert (t_cal_13, p_cal_13) == (22.0, 101.325)
        assert n_equipos == 39  # nunca se borra una fila del catálogo
        assert auditadas == CORRECCIONES_EQUIPOS_ESPERADAS

        # 5) integridad
        assert resultado["integridad_antes"] == "ok"
        assert resultado["integridad_despues"] == "ok"

    def test_el_esquema_resultante_contiene_todo_lo_de_una_bd_nueva(
            self, copia_bd_formato_viejo, tmp_path, monkeypatch):
        """"Quedar al estándar" == ninguna tabla/columna de una BD creada HOY
        por la app le falta a la BD migrada (la migrada puede traer MÁS --
        tablas legacy propias -- pero nunca menos)."""
        import data.ManejoDatos.conection as conection_mod
        from data.ManejoDatos.conection import Conexion

        migrar(copia_bd_formato_viejo, aplicar=True)

        ruta_nueva = str(tmp_path / "bd_nueva_de_hoy.db")
        monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta_nueva)
        Conexion._instance = None
        Conexion().con.close()
        Conexion._instance = None

        def inventario(ruta):
            con = sqlite3.connect(ruta)
            inv = {}
            for (tabla,) in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                inv[tabla] = {c[1] for c in con.execute(
                    f"PRAGMA table_info('{tabla}')").fetchall()}
            con.close()
            return inv

        inv_nueva = inventario(ruta_nueva)
        inv_migrada = inventario(copia_bd_formato_viejo)

        for tabla, columnas in inv_nueva.items():
            assert tabla in inv_migrada, f"falta la tabla {tabla}"
            faltantes = columnas - inv_migrada[tabla]
            assert not faltantes, f"a {tabla} le faltan columnas: {faltantes}"

    def test_segunda_corrida_es_un_no_op_total(self, copia_bd_formato_viejo, capsys):
        migrar(copia_bd_formato_viejo, aplicar=True)
        capsys.readouterr()

        resultado2 = migrar(copia_bd_formato_viejo, aplicar=True)

        salida = capsys.readouterr().out
        assert "sin cambios de esquema" in salida
        assert resultado2["sentinelas_normalizadas"] == 0
        assert resultado2["equipos"]["aplicados"] == []
        assert len(resultado2["equipos"]["ya_aplicados"]) == CORRECCIONES_EQUIPOS_ESPERADAS
        assert resultado2["qc_antes"] == resultado2["qc_despues"] == QC_ESPERADO

    def test_dry_run_no_modifica_la_copia(self, copia_bd_formato_viejo):
        md5_copia_antes = _md5(copia_bd_formato_viejo)

        resultado = migrar(copia_bd_formato_viejo, aplicar=False)

        assert _md5(copia_bd_formato_viejo) == md5_copia_antes
        # pero el reporte YA muestra todo lo que haría
        assert resultado["sentinelas_antes"] == CENTINELAS_ESPERADOS
        assert len(resultado["equipos"]["aplicados"]) == CORRECCIONES_EQUIPOS_ESPERADAS
