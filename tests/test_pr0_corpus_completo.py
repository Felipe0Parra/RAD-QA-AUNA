"""PR.0 (PLAN_GUARDADO_SIN_ESPESOR_Y_RESPALDOS_05-10.md, DP-151): si el corpus de imagenes esta, TODAS las series que
`tests/_corpus.py` declara tienen que estar.

Por que existe: las pruebas de Catphan SALTAN (HI-0) cuando una serie no esta, para que un clon sin los datos externos no
falle. Pero ese mismo salto hace que un RENOMBRE de carpeta apague decenas de pruebas sin un solo rojo: el 05-10-2026
`DICOM/CATPHANKV` y `DICOM/Catphandiciembre` pasaron a `...-Halcyon` y `...-iX` y al menos 79 pruebas dejaron de correr en
silencio (la misma clase de `DP-104`, con las BD de referencia). Aqui se cierra esa puerta sin tocar HI-0:

  - sin corpus en absoluto (ninguna serie declarada existe) -> se SALTA, como siempre;
  - con corpus (alguna serie existe) y alguna otra FALTA -> FALLA, nombrando la clave y la ruta que se esperaba.

La regla es una funcion pura (`series_que_faltan`) que se prueba con carpetas sinteticas, ademas de aplicarse al corpus real.

PF.0 (12-10-2026, PLAN_ANALISIS_PELICULAS_08-10.md) la extiende a la raiz de las PELICULAS reales (`_corpus.PELICULAS_RAIZ`, fuera de las dos raices
anteriores): `verificar_peliculas` es la misma regla con archivos en vez de carpetas y con la raiz como criterio de "hay corpus": si la carpeta existe
y falta una pelicula declarada, FALLA nombrandola; si la carpeta no existe, SALTA. Las dos reglas no se tocan entre si.
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


def peliculas_que_faltan(raiz, declaradas):
    """None si la RAIZ de peliculas no existe (no hay corpus de peliculas en esta maquina); si existe, la lista ORDENADA de las claves cuyo archivo
    falta (vacia si estan todas). Un archivo de 0 bytes y una carpeta con el nombre de la pelicula no cuentan como la pelicula."""
    if not os.path.isdir(raiz):
        return None

    def presente(relativa):
        ruta = os.path.join(raiz, relativa)
        return os.path.isfile(ruta) and os.path.getsize(ruta) > 0

    return sorted(clave for clave, relativa in declaradas.items() if not presente(relativa))


def verificar_peliculas(raiz, declaradas):
    """Salta si la carpeta de peliculas no existe; falla nombrando cada pelicula declarada que no esta cuando la carpeta si existe."""
    faltan = peliculas_que_faltan(raiz, declaradas)
    if faltan is None:
        pytest.skip(f"no hay carpeta de peliculas reales en esta maquina ({raiz}): HI-0, salto honesto")
    detalle = "; ".join(f"{clave} -> {os.path.join(raiz, declaradas[clave])}" for clave in faltan)
    assert not faltan, (
        f"La carpeta de peliculas existe ({raiz}), pero faltan peliculas declaradas en tests/_corpus.py: {detalle}. "
        "Las pruebas que usan esas claves SE SALTARIAN EN SILENCIO (DP-151). Si el archivo se renombro, edite SOLO la "
        "entrada de PELICULAS_MENSUALES o PELICULAS_BRAQUI en tests/_corpus.py."
    )


def texto_del_fallo_de_peliculas(raiz, declaradas):
    """Corre `verificar_peliculas` y devuelve el texto de su fallo. Si la regla SALTA donde tenia que FALLAR (o no hace nada) la prueba cae: pytest da una
    prueba saltada por buena, y esta regla existe justo para que una pelicula que falta no pase en silencio."""
    try:
        verificar_peliculas(raiz, declaradas)
    except pytest.skip.Exception:
        pytest.fail("la regla SALTO donde tenia que FALLAR", pytrace=False)
    except AssertionError as e:
        return str(e)
    pytest.fail("la regla no fallo", pytrace=False)


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

    def test_el_registro_del_hospital_entra_en_la_regla(self):
        """SE.0 (05-10-2026): la carpeta real que llego del hospital (`TOMOGRAFO_SEP26`) vive en un registro aparte de CATPHAN (de CATPHAN iteran pruebas
        que exigen un valor esperado por clave) y la regla tiene que mirarla igual: si el corpus esta y falta, FALLA."""
        todas = _corpus.todas_las_series_declaradas()
        assert "TOMOGRAFO_SEP26" in todas
        assert set(_corpus.CATPHAN) < set(todas)

    def test_si_el_corpus_real_esta_estan_todas_las_series_declaradas(self):
        verificar_corpus(_corpus.CATPHAN_RAIZ, _corpus.todas_las_series_declaradas())


def _crear_peliculas(raiz, relativas):
    os.makedirs(raiz, exist_ok=True)
    for relativa in relativas:
        with open(os.path.join(raiz, relativa), "wb") as f:
            f.write(b"no soy una imagen pero tengo bytes")


PELICULAS = {"M1": "uno.JPG", "M2": "dos.TIF", "B1": "tres.jpeg"}


class TestLaReglaDeLasPeliculasConArchivosSinteticos:
    """PF.0: la regla de PR.0 aplicada a la raiz de las peliculas (archivos, y la raiz decide si hay corpus)."""

    def test_con_todas_las_peliculas_no_falta_ninguna(self, tmp_path):
        _crear_peliculas(str(tmp_path), PELICULAS.values())
        assert peliculas_que_faltan(str(tmp_path), PELICULAS) == []
        verificar_peliculas(str(tmp_path), PELICULAS)       # no salta ni falla

    def test_con_una_pelicula_menos_la_nombra(self, tmp_path):
        _crear_peliculas(str(tmp_path), [PELICULAS["M1"], PELICULAS["B1"]])
        assert peliculas_que_faltan(str(tmp_path), PELICULAS) == ["M2"]

    def test_con_dos_peliculas_menos_las_nombra_ordenadas(self, tmp_path):
        _crear_peliculas(str(tmp_path), [PELICULAS["M2"]])
        assert peliculas_que_faltan(str(tmp_path), PELICULAS) == ["B1", "M1"]

    def test_sin_la_carpeta_no_hay_corpus_y_se_salta(self, tmp_path):
        raiz = str(tmp_path / "no_existe_nunca")
        assert peliculas_que_faltan(raiz, PELICULAS) is None
        with pytest.raises(pytest.skip.Exception):
            verificar_peliculas(raiz, PELICULAS)

    def test_con_la_carpeta_vacia_FALLA_nombrandolas_todas(self, tmp_path):
        """La raiz decide si hay corpus: una carpeta que existe y no tiene ninguna pelicula NO es 'no hay corpus' (a diferencia de las series)."""
        assert peliculas_que_faltan(str(tmp_path), PELICULAS) == ["B1", "M1", "M2"]
        texto = texto_del_fallo_de_peliculas(str(tmp_path), PELICULAS)
        assert all(f"{clave} ->" in texto for clave in PELICULAS)

    def test_el_fallo_nombra_la_clave_y_la_ruta_esperada(self, tmp_path):
        _crear_peliculas(str(tmp_path), [PELICULAS["M1"]])
        texto = texto_del_fallo_de_peliculas(str(tmp_path), PELICULAS)
        assert "M2 ->" in texto and os.path.join(str(tmp_path), "dos.TIF") in texto
        assert "B1 ->" in texto
        assert "M1 ->" not in texto
        assert "DP-151" in texto

    def test_una_carpeta_con_el_nombre_de_la_pelicula_no_cuenta(self, tmp_path):
        _crear_peliculas(str(tmp_path), [PELICULAS["M1"], PELICULAS["B1"]])
        os.makedirs(os.path.join(str(tmp_path), PELICULAS["M2"]))                    # una CARPETA, no un archivo
        assert peliculas_que_faltan(str(tmp_path), PELICULAS) == ["M2"]

    def test_un_archivo_de_cero_bytes_no_cuenta(self, tmp_path):
        _crear_peliculas(str(tmp_path), [PELICULAS["M1"], PELICULAS["B1"]])
        open(os.path.join(str(tmp_path), PELICULAS["M2"]), "wb").close()
        assert peliculas_que_faltan(str(tmp_path), PELICULAS) == ["M2"]

    def test_la_regla_de_las_series_no_cambia_con_esta_extension(self, tmp_path):
        """Las dos reglas son independientes: la de series sigue saltando con la raiz inexistente y por 'ninguna presente'."""
        assert series_que_faltan(str(tmp_path / "no_existe_nunca"), DECLARADAS) is None
        _crear(str(tmp_path), [])
        assert series_que_faltan(str(tmp_path), DECLARADAS) is None            # carpeta que existe pero sin ninguna serie: aqui SI es 'no hay corpus'


class TestLasPeliculasReales:
    def test_las_peliculas_declaradas_no_son_un_conjunto_vacio(self):
        """No vacuidad: si alguien vaciara los registros, la regla de abajo pasaria sin mirar nada."""
        assert len(_corpus.PELICULAS_MENSUALES) >= 10 and len(_corpus.PELICULAS_BRAQUI) >= 4

    def test_si_la_carpeta_de_peliculas_esta_estan_todas_las_declaradas(self):
        verificar_peliculas(_corpus.PELICULAS_RAIZ, _corpus.todas_las_peliculas_declaradas())
