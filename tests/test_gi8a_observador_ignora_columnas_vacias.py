"""GI.8a (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, DP-86): el observador de contrato no cambia de huella cuando solo se anadio una columna vacia.

Por que: `observador_contrato._censo_y_vigente` calculaba la huella de cada fila con TODAS las columnas, tambien las que valen NULL. Anadir una columna -aunque llegara vacia a todas las filas- cambiaba la
huella de TODOS los bloques de esa tabla: 292 falsos «cambia (NO declarado)» en `braqui` (03-09), 55 / 66 bloques al abrir la copia desplegada con las columnas de los planes del 21 al 25-09 (GI.0b). La receta
de dos pasos de DP-86 lo esquiva declarando cientos de `ref` a mano, y declararlos apaga la vigilancia de lo que SI cambio.

Lo que fija esta prueba (version 3 de la foto):
  1. una columna anadida y vacia no mueve la huella de ningun bloque de ninguna tabla (la comparacion no da fallos y el censo `vigente` entero es igual);
  2. un valor que APARECE en esa columna cambia la huella de EXACTAMENTE su bloque, y volver a NULL la devuelve a la de antes;
  3. un valor alterado en una columna ya poblada, o que pasa a NULL, cambia la huella de su bloque (la vigilancia de lo que si cambia sigue intacta);
  4. `0` y la cadena vacia NO son NULL: aparecer con ellos cambia la huella;
  5. la version de la foto es la 3 y una foto de la version 2 no se compara con una de la 3, y el mensaje NOMBRA las dos versiones y la de la herramienta;
  6. la receta de la huella va atada a la version: una tabla fija en memoria da huellas literales POR VERSION, asi que cambiar como se calcula (separadores, orden de claves, que se omite,
     como se serializa un BLOB) sin subir la version -o subirla sin fijar las huellas de la nueva- hace caer la prueba (revision de GI.8a, hallazgo F1).
Sobre el rojo contra el codigo anterior: la version (`VERSION_OBSERVADOR`) y la huella cambian; las pruebas de «lo que si cambia» usan API que ya existia y pasan en los dos lados (son los controles).
"""
import hashlib
import json
import shutil
import sqlite3

import pytest

import scripts.observador_contrato as obs
from _bd_referencia import BD_REBUILD_14_09, BD_REBUILD_21_09

TABLAS = ("resolucion_contraste_rois", "valores_ct", "pruebas")
NUEVA = "gi8a_columna_nueva"


def _copia(origen, tmp_path):
    if not origen.exists():
        pytest.skip(f"BD de referencia ausente: {origen}")
    ruta = str(tmp_path / "copia.db")
    shutil.copy(origen, ruta)
    return ruta


def _foto(ruta):
    """Las BD de referencia son copias crudas: las tablas que la app crea al abrir todavia no existen (`tolerar_tablas_ausentes`, GI.0b)."""
    return obs.capturar(ruta, tolerar_tablas_ausentes=True)


def _anadir_columnas(ruta, tablas=TABLAS, tipo="TEXT"):
    con = sqlite3.connect(ruta)
    try:
        for t in tablas:
            con.execute(f'ALTER TABLE "{t}" ADD COLUMN {NUEVA} {tipo}')
        con.commit()
    finally:
        con.close()


def _ejecutar(ruta, sql, params=()):
    con = sqlite3.connect(ruta)
    try:
        con.execute(sql, params)
        con.commit()
    finally:
        con.close()


def _una_fila_vigente(ruta, tabla, donde=""):
    """El `id` de una fila vigente de `tabla` (o `None` si la copia no trae ninguna)."""
    con = sqlite3.connect(ruta)
    try:
        con.row_factory = None
        columnas = [c[1] for c in con.execute(f'PRAGMA table_info("{tabla}")')]
        vigente = " AND (activo IS NULL OR activo = 1)" if "activo" in columnas else ""
        fila = con.execute(f'SELECT id FROM "{tabla}" WHERE 1=1{vigente}{donde} ORDER BY id LIMIT 1').fetchone()
        return fila[0] if fila else None
    finally:
        con.close()


def hashlib_sha256(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _bloques_que_cambian(antes, despues, tabla):
    a, b = antes["vigente"][tabla], despues["vigente"][tabla]
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


# Solo copias que YA pasaron por la app (todas las tablas del contrato con `activo`): una copia cruda mas vieja (`BD_QA`, 21-08) trae ~30 tablas sin la columna y el interceptor de RT1
# (`tests/conftest.py`) veria el SELECT del observador como una lectura sin filtro de vigencia; no es lo que esta prueba mide.
@pytest.fixture(params=[("rebuild_14_09", BD_REBUILD_14_09), ("rebuild_21_09", BD_REBUILD_21_09)], ids=lambda p: p[0])
def copia(request, tmp_path):
    ruta = _copia(request.param[1], tmp_path)
    if _una_fila_vigente(ruta, "valores_ct") is None:
        pytest.skip("la copia no trae Valores CT vigentes")
    return ruta


class TestUnaColumnaVaciaNoMueveNingunaHuella:

    def test_las_tablas_de_la_prueba_estan_en_el_contrato(self):
        assert set(TABLAS) <= set(obs._tablas_en_alcance())

    def test_la_comparacion_no_da_fallos_y_el_censo_vigente_es_identico(self, copia):
        antes = _foto(copia)
        _anadir_columnas(copia)
        despues = _foto(copia)
        fallos, info = obs.comparar(antes, despues)
        assert fallos == [], fallos
        for t in TABLAS:
            assert f"[esquema] columna nueva {t}.{NUEVA}" in info, (t, info[:5])
        assert antes["vigente"] == despues["vigente"], "ninguna huella de ninguna tabla se mueve"


class TestLoQueSiCambiaSigueViendose:

    def test_un_valor_que_aparece_en_la_columna_nueva_cambia_exactamente_su_bloque(self, copia):
        antes = _foto(copia)
        _anadir_columnas(copia)
        fila = _una_fila_vigente(copia, "valores_ct")
        _ejecutar(copia, f'UPDATE valores_ct SET {NUEVA} = ? WHERE id = ?', ("x", fila))
        despues = _foto(copia)
        assert len(_bloques_que_cambian(antes, despues, "valores_ct")) == 1
        assert _bloques_que_cambian(antes, despues, "pruebas") == [] and _bloques_que_cambian(antes, despues, "resolucion_contraste_rois") == []
        fallos, _ = obs.comparar(antes, despues)
        assert len([f for f in fallos if f.startswith("[vigente] valores_ct")]) == 1, fallos

    def test_volver_a_null_devuelve_la_huella_de_antes(self, copia):
        antes = _foto(copia)
        _anadir_columnas(copia)
        fila = _una_fila_vigente(copia, "valores_ct")
        _ejecutar(copia, f'UPDATE valores_ct SET {NUEVA} = ? WHERE id = ?', ("x", fila))
        _ejecutar(copia, f'UPDATE valores_ct SET {NUEVA} = NULL WHERE id = ?', (fila,))
        assert _foto(copia)["vigente"] == antes["vigente"]

    def test_un_valor_alterado_en_una_columna_ya_poblada_cambia_su_bloque(self, copia):
        antes = _foto(copia)
        _anadir_columnas(copia)
        fila = _una_fila_vigente(copia, "valores_ct")
        _ejecutar(copia, "UPDATE valores_ct SET promedio_hu = promedio_hu + 1 WHERE id = ?", (fila,))
        despues = _foto(copia)
        assert len(_bloques_que_cambian(antes, despues, "valores_ct")) == 1
        fallos, _ = obs.comparar(antes, despues)
        assert len([f for f in fallos if f.startswith("[vigente] valores_ct")]) == 1, fallos

    def test_un_valor_que_pasa_a_null_cambia_su_bloque(self, copia):
        """El valor que DESAPARECE tambien se ve (una columna poblada que pasa a NULL no es «una columna vacia anadida»)."""
        fila = _una_fila_vigente(copia, "resolucion_contraste_rois", " AND snr IS NOT NULL")
        if fila is None:
            pytest.skip("la copia no trae un ROI de contraste con SNR")
        antes = _foto(copia)
        _ejecutar(copia, "UPDATE resolucion_contraste_rois SET snr = NULL WHERE id = ?", (fila,))
        despues = _foto(copia)
        assert len(_bloques_que_cambian(antes, despues, "resolucion_contraste_rois")) == 1

    @pytest.mark.parametrize("valor, tipo_almacenado", [(0, "integer"), (0.0, "real"), ("", "text")])
    def test_cero_y_cadena_vacia_no_son_null(self, copia, valor, tipo_almacenado):
        """Columna SIN tipo declarado (afinidad BLOB): guarda cada valor tal cual. Con `TEXT` SQLite convertiria el 0 en la cadena '0' y la prueba no distinguiria
        un cero numerico de un texto (la mutacion MA4, que omite los ceros, sobrevivia por eso); se comprueba el tipo almacenado para que la prueba mida lo que dice."""
        antes = _foto(copia)
        _anadir_columnas(copia, tipo="")
        fila = _una_fila_vigente(copia, "valores_ct")
        _ejecutar(copia, f'UPDATE valores_ct SET {NUEVA} = ? WHERE id = ?', (valor, fila))
        con = sqlite3.connect(copia)
        try:
            assert con.execute(f'SELECT typeof({NUEVA}) FROM valores_ct WHERE id = ?', (fila,)).fetchone()[0] == tipo_almacenado
        finally:
            con.close()
        despues = _foto(copia)
        assert len(_bloques_que_cambian(antes, despues, "valores_ct")) == 1, repr(valor)


class TestLaVersionDeLaFoto:

    def test_la_version_es_la_3(self):
        """1 = huellas con el nombre real de cada columna; 2 (GI.0b) = con el nombre canonico de los renombrados declarados; 3 (GI.8a) = sin las columnas en NULL. Quien cambie como se hashea la sube."""
        assert obs.VERSION_OBSERVADOR == 3

    def test_una_foto_de_la_version_2_no_se_compara_con_una_de_la_3(self, copia):
        foto = _foto(copia)
        vieja = json.loads(json.dumps(foto))
        vieja["observador"]["version"] = 2
        fallos, _ = obs.comparar(vieja, foto)
        assert len(fallos) == 1 and "no las tomó la misma versión" in fallos[0], fallos
        # revision de GI.8a (P-02): el mensaje dice CUAL version es cada foto y cual es la de la herramienta, no vuelca dos diccionarios
        assert "la primera: versión 2" in fallos[0] and "la segunda: versión 3" in fallos[0] and "esta herramienta es la versión 3" in fallos[0], fallos
        assert "{" not in fallos[0], fallos[0]
        assert obs.comparar(foto, json.loads(json.dumps(foto)))[0] == []

    def test_una_foto_sin_registro_de_version_se_dice_asi(self, copia):
        foto = _foto(copia)
        sin_registro = json.loads(json.dumps(foto))
        sin_registro.pop("observador")
        fallos, _ = obs.comparar(sin_registro, foto)
        assert len(fallos) == 1 and "la primera: sin registro de versión" in fallos[0] and "la segunda: versión 3" in fallos[0], fallos

    def test_misma_version_y_otra_lista_de_renombrados_tambien_se_dice(self, copia):
        foto = _foto(copia)
        otra = json.loads(json.dumps(foto))
        otra["observador"]["renombres_declarados"].append(["x", "a", "b"])
        fallos, _ = obs.comparar(foto, otra)
        assert len(fallos) == 1 and "versión 3, con 2 renombrados declarados" in fallos[0] and "versión 3, con 3 renombrados declarados" in fallos[0], fallos


# Huellas de referencia POR VERSION de una tabla fija en memoria (todos los tipos que guarda la base: entero, real, texto, BLOB, vacio, 0, 0.0, '', todo NULL, una fila anulada).
# Quien cambie como se calcula la huella tiene que subir `VERSION_OBSERVADOR` y escribir AQUI las de la version nueva; la prueba cae si cambia la receta sin la version o la version sin las huellas.
HUELLAS_DE_REFERENCIA_POR_VERSION = {
    3: {"1": "4ed7c10c53f57aff9a27d24ddad569a54666f19ca60520a5ea6317dc8cc805fa",
        "2": "3c41a9a6cd97128f32869414577ea51b6b59c56cac44ff97294d0a3b62144621",
        "3": "c42b18ffaefaacd23fa2bac276b9c5330c03dc86668d8420514ab4e3476afab2"},
}


def _huellas_de_la_tabla_fija():
    con = sqlite3.connect(":memory:")
    try:
        con.execute("CREATE TABLE tabla_fija (id INTEGER PRIMARY KEY, ref INTEGER, entero INTEGER, real REAL, texto TEXT, binario BLOB, vacio TEXT, activo INTEGER)")
        con.executemany("INSERT INTO tabla_fija VALUES (?,?,?,?,?,?,?,?)", [
            (1, 1, 10, 1.5, "a", b"\x00\x01", None, 1),
            (2, 1, 0, 0.0, "", None, None, None),           # 0, 0.0 y '' NO son NULL; activo NULL cuenta como vigente
            (3, 2, None, None, None, None, None, 1),        # todo NULL: queda solo la clave del bloque
            (4, 3, 7, 2.25, "ñ", b"", "x", 1),
            (5, 3, 99, 9.9, "anulada", None, None, 0),      # anulada: no entra a la huella
        ])
        columnas = [c[1] for c in con.execute("PRAGMA table_info('tabla_fija')")]
        censo, vigente = obs._censo_y_vigente(con.cursor(), "tabla_fija", columnas)
        assert censo == {"total": 5, "activas": 4, "anuladas": 1}
        return vigente
    finally:
        con.close()


class TestLaRecetaDeLaHuellaVaConLaVersion:

    def test_cada_version_tiene_sus_huellas_de_referencia(self):
        assert obs.VERSION_OBSERVADOR in HUELLAS_DE_REFERENCIA_POR_VERSION, "se subió la versión del observador sin fijar las huellas de referencia de la nueva"

    def test_la_huella_de_la_tabla_fija_es_la_de_su_version(self):
        assert _huellas_de_la_tabla_fija() == HUELLAS_DE_REFERENCIA_POR_VERSION[obs.VERSION_OBSERVADOR], \
            "cambió como se calcula la huella: suba VERSION_OBSERVADOR y fije las huellas de la versión nueva (dos fotos de recetas distintas no son comparables)"

    def test_cero_vacio_y_blob_vacio_entran_a_la_huella_y_null_no(self):
        """Los tres bloques son distintos entre si y el de «todo NULL» no es el de «{}»: la clave del bloque entra siempre, el NULL nunca."""
        h = _huellas_de_la_tabla_fija()
        assert len(set(h.values())) == 3
        assert h["2"] != hashlib_sha256("{}")
