"""PR.0 (PLAN_GUARDADO_SIN_ESPESOR_Y_RESPALDOS_05-10.md, DP-151): si el corpus de imagenes esta, TODAS las series que
`tests/_corpus.py` declara tienen que estar.

Por que existe: las pruebas de Catphan SALTAN (HI-0) cuando una serie no esta, para que un clon sin los datos externos no
falle. Pero ese mismo salto hace que un RENOMBRE de carpeta apague decenas de pruebas sin un solo rojo: el 05-10-2026
`DICOM/CATPHANKV` y `DICOM/Catphandiciembre` pasaron a `...-Halcyon` y `...-iX` y al menos 79 pruebas dejaron de correr en
silencio (la misma clase de `DP-104`, con las BD de referencia). Aqui se cierra esa puerta sin tocar HI-0:

  - sin corpus en absoluto (ninguna serie declarada existe) -> se SALTA, como siempre;
  - con corpus (alguna serie existe) y alguna otra FALTA -> FALLA, nombrando la clave y la ruta que se esperaba.

La regla es una funcion pura (`series_que_faltan`) que se prueba con carpetas sinteticas, ademas de aplicarse al corpus real.
"""
import os

import pytest

import _corpus


def series_que_faltan(raiz, declaradas):
    """None si NO hay corpus (ninguna serie declarada existe bajo `raiz`); si lo hay, la lista ORDENADA de las claves cuya
    carpeta falta (vacia si estan todas)."""
    rutas = {clave: os.path.join(raiz, relativa) for clave, relativa in declaradas.items()}
    presentes = {clave for clave, ruta in rutas.items() if os.path.isdir(ruta)}
    if not presentes:
        return None
    return sorted(clave for clave in rutas if clave not in presentes)


def verificar_corpus(raiz, declaradas):
    """Salta si no hay corpus; falla nombrando cada serie declarada que no esta cuando el corpus si esta."""
    faltan = series_que_faltan(raiz, declaradas)
    if faltan is None:
        pytest.skip(f"no hay corpus Catphan en esta maquina ({raiz}): HI-0, salto honesto")
    detalle = "; ".join(f"{clave} -> {os.path.join(raiz, declaradas[clave])}" for clave in faltan)
    assert not faltan, (
        f"El corpus Catphan esta (otras series si existen), pero faltan series declaradas en tests/_corpus.py: {detalle}. "
        "Las pruebas que usan esas claves SE SALTARIAN EN SILENCIO (DP-151). Si la carpeta se renombro, edite SOLO la "
        "entrada de CATPHAN en tests/_corpus.py."
    )


def _crear(raiz, relativas):
    for relativa in relativas:
        os.makedirs(os.path.join(raiz, relativa), exist_ok=True)


DECLARADAS = {"A": "serie_a", "B": os.path.join("sub", "serie_b"), "C": "serie_c"}


class TestLaReglaConCarpetasSinteticas:
    def test_con_todas_las_series_no_falta_ninguna(self, tmp_path):
        _crear(str(tmp_path), DECLARADAS.values())
        assert series_que_faltan(str(tmp_path), DECLARADAS) == []
        verificar_corpus(str(tmp_path), DECLARADAS)        # no salta ni falla

    def test_con_una_serie_menos_la_nombra(self, tmp_path):
        _crear(str(tmp_path), [DECLARADAS["A"], DECLARADAS["C"]])
        assert series_que_faltan(str(tmp_path), DECLARADAS) == ["B"]

    def test_con_dos_series_menos_las_nombra_ordenadas(self, tmp_path):
        _crear(str(tmp_path), [DECLARADAS["B"]])
        assert series_que_faltan(str(tmp_path), DECLARADAS) == ["A", "C"]

    def test_sin_ninguna_serie_no_hay_corpus_y_se_salta(self, tmp_path):
        assert series_que_faltan(str(tmp_path), DECLARADAS) is None
        with pytest.raises(pytest.skip.Exception):
            verificar_corpus(str(tmp_path), DECLARADAS)

    def test_con_la_raiz_inexistente_se_salta(self, tmp_path):
        raiz = str(tmp_path / "no_existe_nunca")
        assert series_que_faltan(raiz, DECLARADAS) is None
        with pytest.raises(pytest.skip.Exception):
            verificar_corpus(raiz, DECLARADAS)

    def test_el_fallo_nombra_la_clave_y_la_ruta_esperada(self, tmp_path):
        _crear(str(tmp_path), [DECLARADAS["A"]])
        with pytest.raises(AssertionError) as info:
            verificar_corpus(str(tmp_path), DECLARADAS)
        texto = str(info.value)
        assert "B ->" in texto and os.path.join(str(tmp_path), "sub", "serie_b") in texto
        assert "C ->" in texto
        assert "A ->" not in texto
        assert "DP-151" in texto

    def test_un_archivo_con_el_nombre_de_la_serie_no_cuenta_como_carpeta(self, tmp_path):
        _crear(str(tmp_path), [DECLARADAS["A"], DECLARADAS["C"]])
        os.makedirs(os.path.join(str(tmp_path), "sub"), exist_ok=True)
        with open(os.path.join(str(tmp_path), DECLARADAS["B"]), "w") as f:       # un ARCHIVO, no una carpeta
            f.write("no soy una serie")
        assert series_que_faltan(str(tmp_path), DECLARADAS) == ["B"]


class TestElCorpusReal:
    def test_las_series_declaradas_no_son_un_conjunto_vacio(self):
        """No vacuidad: si alguien vaciara CATPHAN, la regla de abajo pasaria sin mirar nada."""
        assert len(_corpus.CATPHAN) >= 6

    def test_si_el_corpus_real_esta_estan_todas_las_series_declaradas(self):
        verificar_corpus(_corpus.CATPHAN_RAIZ, _corpus.CATPHAN)
