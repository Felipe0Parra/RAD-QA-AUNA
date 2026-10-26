"""F.1 (PLAN_ANALISIS_PELICULAS_08-10.md, DP-157, DA-83 a DA-89): el PDF mensual del Clinac 600 y del Clinac iX imprime el analisis nuevo de la capa que GUARDO el registro (`analisis_placa_mensual`, D.1).

Lo que se garantiza, cada cosa con su prueba (el rojo contra HEAD esta en el anexo: logs/F1/rojo.log):
  - LA REGLA (V = franjas vigentes del analisis viejo, I = imagen en la fila vigente de `preguntas`, N = el analisis nuevo vigente), sin base y sin PDF (`TestLaReglaDeVIN`): con N, la seccion nueva y, solo
    si I, la imagen vieja; NUNCA la tabla vieja ni «No hay datos de analisis de imagen» ni un recuadro vacio (DA-89, 23-10). Sin N: la imagen como hoy y, en lugar de la tabla vieja, UNA linea si V («Analisis de la
    pelicula: pendiente con la herramienta actual...») o «No hay datos...» como hoy si no. La lectura de N va en la fase que ya lee la base (`_recopilar_datos_completos`) y nunca en
    `_procesar_datos_para_reporte`, una funcion pura para 600/iX (T5 la llama sin base); un control sin fila de `preguntas` se trata como una fila sin imagen (hoy no genera PDF: 14, 20 y 23);
  - DE PUNTA A PUNTA (R, G y B: las anclas «capa roja», «capa verde» y «capa azul» estan escritas aqui a mano): el PDF del `reporte_mensual` real, sobre un analisis sembrado con el ESCRITOR REAL del servicio,
    dice el nombre, los numeros guardados, las medidas estadisticas del barrido y los perfiles de ESA capa y ninguno de otra; cambiar `CAPA_POR_OMISION` no cambia ningun PDF;
  - LO GUARDADO MANDA (F1R-2): lo impreso son los valores GUARDADOS, nunca los recalculados; con otra version del algoritmo, con un valor guardado alterado o con la imagen alterada, el PDF sale con lo
    guardado y una frase, sin barrido, perfiles ni parametros, y el detalle va a `error_log.txt`; la pelicula y su recuadro salen igual (del propio registro);
  - F1R-9: una parte que falla (volver a medir, la figura, la pelicula que reportlab no abre) no tumba el PDF; si falla la lectura de la base, el reporte no sale (regla de PI.8).
Se siembra TODO antes de abrir QtSql (DP-147). La pelicula con su recuadro, la paginacion y los guardias por AST estan en `test_f1_pelicula_y_guardias.py`."""
import gc
import html
import io
import json
import re
import sqlite3

import fitz
import pandas as pd
import pytest
from PIL import Image as PILImage

import _placa_mensual_sintetica as gen
from _f1_ayudas import (CAPA_EN_UNA_FRASE, CAPAS, CLAVES_DE_LA_SECCION, ENCABEZADO_DE_LA_TABLA_VIEJA, LEYENDA_DEL_RECUADRO, LINEA_SIN_ANALISIS_NUEVO, NO_MEDIBLE, REFERENCIA_TG142,  # noqa: F401
                        ROTULOS_ESPERADOS, SIMBOLOS_DA18, SIN_DATOS_DEL_ANALISIS_VIEJO, TITULO_DE_LA_PELICULA, TITULO_DE_LA_SECCION, TITULO_DE_LOS_PARAMETROS, aparece, cerrar_mundo, dibujo,
                        app, generar_pdf, imagenes_de, lineas_de, mundo_nuevo, n3, normal, oraculo, parametros, paginas_de, pdf_mod, pel, plantilla, pm, recuadro, rm, seccion, svc, texto_de)  # noqa: F401
from reportlab.platypus import Paragraph

pytestmark = [pytest.mark.usefixtures("app"), pytest.mark.filterwarnings("ignore::DeprecationWarning")]


# ------------------------------------------------------------------------------------------------------------------------------------------------------ la pelicula y los clics

@pytest.fixture(scope="module")
def placa():
    """La pelicula sintetica de PF.0 (independiente del motor) en JPEG: 0.9 MB, mide las tres capas en valor de pixel. Una vez por modulo."""
    return gen.generar("jpeg", variante="A", seed=1)


@pytest.fixture(scope="module")
def otra_placa():
    return gen.generar("jpeg", variante="A", seed=2)


@pytest.fixture(scope="module")
def clics(placa):
    return placa.verdad.clics_del_cuaderno()


@pytest.fixture(scope="module")
def verdad(placa, clics):
    """El oraculo: lo que el motor da sobre esos bytes y esos clics, por capa: `valores_medidos`, y el barrido de cada eje."""
    resultado, barrido, marcas = oraculo(placa.datos, clics, parametros())
    return {"resultado": resultado, "barrido": barrido, "marcas": marcas,
            "valores": {c: pm().valores_medidos(resultado, c) for c in CAPAS}}


ESCENARIOS_SIN_N = {                       # nombre -> (fila_preguntas, imagen_vieja, franjas)
    "nada": (True, False, False), "solo_V": (True, False, True), "solo_I": (True, True, False), "V_e_I": (True, True, True), "sin_fila": (False, False, False)}
ESCENARIOS_CON_N = {                       # nombre -> (fila_preguntas, imagen_vieja, franjas)
    "N_sola": (True, False, False), "N_e_I": (True, True, False), "N_y_V": (True, False, True), "N_V_I": (True, True, True), "N_sin_fila": (False, False, False)}


def _imagenes_truncadas(datos):
    """F1-R2-PROD-01: `{nombre del control: bytes}` de la pelicula guardada de un registro cuyo BLOB quedo CORTADO (una base danada o editada a mano), en PNG (al 70 %) y en JPEG (al 60 %). Pillow lee la
    cabecera (el tamano) y no puede decodificar el resto: pasan por una guarda que solo abre la imagen y revientan al dibujarla, dentro de `doc.build`."""
    png = io.BytesIO()
    PILImage.open(io.BytesIO(datos)).save(png, format="PNG")
    png = png.getvalue()
    return {"imagen_truncada_png": png[: len(png) * 7 // 10], "imagen_truncada_jpeg": datos[: len(datos) * 6 // 10]}


@pytest.fixture(scope="module")
def mundo(plantilla, tmp_path_factory, placa, otra_placa, clics):
    """Una BD con TODOS los escenarios sembrados (un control mensual de cada uno) con el escritor real del servicio. Los analisis alterados lo estan por SQL, al sembrar."""
    m, mp, previo = mundo_nuevo(plantilla, tmp_path_factory)
    try:
        for nombre, (fila, con_imagen, franjas) in {**ESCENARIOS_SIN_N, **ESCENARIOS_CON_N}.items():
            m.control(nombre, fila_preguntas=fila, imagen=placa.datos if con_imagen else None, franjas=franjas)
            if nombre in ESCENARIOS_CON_N:
                m.guardar(nombre, placa.datos, clics, "G")
        for capa in CAPAS:
            m.control(f"capa_{capa}")
            m.guardar(f"capa_{capa}", placa.datos, clics, capa)
        for nombre in ("otra_version", "valor_alterado", "imagen_invalida", "imagen_distinta", "puntos_malos"):
            m.control(nombre)
            m.guardar(nombre, placa.datos, clics, "G")
        m.sql("UPDATE analisis_placa_mensual SET version = 'PM-0' WHERE ref = ?", (m.refs["otra_version"],))
        m.sql("UPDATE analisis_placa_mensual SET fwhm_crossplane_mm = fwhm_crossplane_mm + 0.5 WHERE ref = ?", (m.refs["valor_alterado"],))
        m.sql("UPDATE analisis_placa_mensual SET imagen = ? WHERE ref = ?", (b"esto no es una imagen", m.refs["imagen_invalida"]))
        m.sql("UPDATE analisis_placa_mensual SET imagen = ? WHERE ref = ?", (otra_placa.datos, m.refs["imagen_distinta"]))
        malos = [{"estado": "sin refinar", "clic": [100.0, 100.0], "punto": [100.0, 100.0], "radio_px": None, "motivo": None}] * 5
        m.sql("UPDATE analisis_placa_mensual SET puntos = ? WHERE ref = ?", (json.dumps(malos), m.refs["puntos_malos"]))
        m.control("ix", maquina="Clinac ix")
        m.guardar("ix", placa.datos, clics, "G")
        for nombre, imagen in _imagenes_truncadas(placa.datos).items():          # al final: los demas controles conservan su fecha
            m.control(nombre)
            m.guardar(nombre, placa.datos, clics, "G")
            m.sql("UPDATE analisis_placa_mensual SET imagen = ? WHERE ref = ?", (imagen, m.refs[nombre]))
        yield m
    finally:
        cerrar_mundo(mp, previo)
        gc.collect()


def _valores_guardados(m, nombre):
    """{columna: valor} de la fila vigente del analisis nuevo, leida con sqlite3 a pelo: lo GUARDADO, la verdad contra la que se mira el PDF."""
    con = sqlite3.connect(m.ruta)
    con.row_factory = sqlite3.Row
    try:
        fila = con.execute("SELECT * FROM analisis_placa_mensual WHERE ref = ? AND activo = 1", (m.refs[nombre],)).fetchone()
        return {k: fila[k] for k in fila.keys()}
    finally:
        con.close()


def _la_seccion(texto):
    """El texto de la seccion nueva, normalizado: desde la linea de su titulo hasta la primera linea «Imagen» (el recuadro de la imagen vieja) o «Dosimetría» (la tabla que le sigue en el PDF)."""
    lineas = [normal(l) for l in texto.splitlines() if normal(l)]
    inicio = next((i for i, l in enumerate(lineas) if l.startswith(TITULO_DE_LA_SECCION)), None)
    assert inicio is not None, f"el PDF no trae la seccion «{TITULO_DE_LA_SECCION}»"
    fin = next((i for i in range(inicio, len(lineas)) if lineas[i] in ("Imagen", "Dosimetría")), len(lineas))
    return " ".join(lineas[inicio:fin])


def _celda(c):
    return html.unescape(c.text) if isinstance(c, Paragraph) else ("" if c is None else str(c))


def _filas(df):
    """Las filas de un DataFrame de la seccion como listas de texto (la cabecera es la primera)."""
    return [[_celda(c) for c in fila] for fila in [list(df.columns)] + df.values.tolist()]


# ======================================================================================================================================================== la regla de V, I y N

PNG_MINIMO = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cf00000301010018dd8db40000000049454e44ae426082")
FRANJA = {"franja": "Franja 1", "ancho_media_h": 77.7771, "ancho_media_v": 77.8882, "penumbra_izq_h": 77.1113}


def _datos(n=False, v=False, i=False, con_fila=True, extra=None):
    datos = {"preguntas": ([{"isocentro": "Funciona", "imagen": PNG_MINIMO if i else None}] if con_fila else [])}
    if v:
        datos["analisis_placa_franjas"] = [dict(FRANJA)]
    if n:
        datos[rm().CLAVE_DEL_ANALISIS_NUEVO] = {"capa": "G"}                     # un registro de mentira: la seccion se sustituye por un espia
    datos.update(extra or {})
    return datos


def _procesar(monkeypatch, maquina="Clinac 600", **kw):
    sec = seccion()
    llamadas = []
    monkeypatch.setattr(sec, "tablas_de_la_seccion", lambda registro: (llamadas.append(registro), {c: pd.DataFrame([["Campo", "Valor"]], columns=[c, ""]) for c in sec.CLAVES})[1])
    monkeypatch.setattr(svc(), "leer", lambda *a, **k: pytest.fail("`_procesar_datos_para_reporte` no lee la base (T5 la llama sin base y sin ref_id): el analisis nuevo se lee en la fase de datos"))
    tablas = rm()._procesar_datos_para_reporte(_datos(**kw), {}, {}, maquina)
    return tablas, llamadas


class TestLaReglaDeVIN:
    """La tabla de verdad de DA-89 (23-10) sobre `_procesar_datos_para_reporte`, con datos armados a mano (sin base) y la seccion sustituida por un espia."""

    @pytest.mark.parametrize("maquina", ["Clinac 600", "Clinac ix"])
    @pytest.mark.parametrize("v", [False, True])
    @pytest.mark.parametrize("i", [False, True])
    def test_con_n_la_seccion_nueva_y_solo_si_i_la_imagen_vieja_nunca_la_tabla_vieja(self, monkeypatch, maquina, v, i):
        tablas, llamadas = _procesar(monkeypatch, maquina, n=True, v=v, i=i)
        assert len(llamadas) == 1 and llamadas[0] == {"capa": "G"}, "la seccion se arma una vez, con el registro leido"
        assert all(c in tablas for c in CLAVES_DE_LA_SECCION), sorted(tablas)
        assert "analisis_imagen" not in tablas, "con N no sale ni la tabla vieja ni «No hay datos de analisis de imagen» (DA-89)"
        assert ("imagen" in tablas) == i, "la imagen vieja solo si la fila de preguntas trae imagen (I), nunca el recuadro vacio"

    @pytest.mark.parametrize("v", [False, True])
    def test_con_n_y_sin_fila_de_preguntas_solo_la_seccion(self, monkeypatch, v):
        tablas, _ = _procesar(monkeypatch, n=True, v=v, con_fila=False)
        assert all(c in tablas for c in CLAVES_DE_LA_SECCION) and "imagen" not in tablas and "analisis_imagen" not in tablas

    @pytest.mark.parametrize("con_fila", [True, False])
    def test_la_imagen_vieja_se_decide_por_la_imagen_y_no_por_la_fila(self, monkeypatch, con_fila):
        """F1-M05: I es «la imagen de la primera fila de preguntas no esta vacia», el MISMO predicado con que `_crear_espacio_imagen` decide si hay algo que imprimir; una fila sin imagen no la imprime."""
        tablas, _ = _procesar(monkeypatch, n=True, i=False, con_fila=con_fila)
        assert "imagen" not in tablas

    @pytest.mark.parametrize("maquina", ["Clinac 600", "Clinac ix"])
    @pytest.mark.parametrize("i", [False, True])
    def test_sin_n_ni_v_las_dos_tablas_de_siempre(self, monkeypatch, maquina, i):
        tablas, llamadas = _procesar(monkeypatch, maquina, n=False, v=False, i=i)
        assert llamadas == [] and not any(c in tablas for c in CLAVES_DE_LA_SECCION), "sin N la seccion nueva no sale"
        assert tablas["analisis_imagen"].equals(pd.DataFrame([[SIN_DATOS_DEL_ANALISIS_VIEJO]], columns=["Información"]))
        assert list(tablas["imagen"].columns) == ["Imagen"] and len(tablas["imagen"]) == 1
        if not i:
            assert tablas["imagen"].equals(pd.DataFrame([[None]], columns=["Imagen"])), "el recuadro «Imagen» vacio de siempre"
        else:
            assert str(tablas["imagen"].iloc[0, 0]).endswith(".png"), "la imagen vieja, re-codificada a PNG en un temporal, como hoy"

    @pytest.mark.parametrize("maquina", ["Clinac 600", "Clinac ix"])
    @pytest.mark.parametrize("i", [False, True])
    def test_sin_n_y_con_v_la_imagen_como_hoy_y_una_linea_en_lugar_de_la_tabla_vieja(self, monkeypatch, maquina, i):
        tablas, _ = _procesar(monkeypatch, maquina, n=False, v=True, i=i)
        assert tablas["analisis_imagen"].equals(pd.DataFrame([[LINEA_SIN_ANALISIS_NUEVO]], columns=["Información"])), "UNA fila con la linea de DA-89"
        assert "imagen" in tablas and list(tablas["imagen"].columns) == ["Imagen"]
        valores = " ".join(str(x) for x in tablas["analisis_imagen"].values.ravel()) + " ".join(tablas["analisis_imagen"].columns)
        assert "77.777" not in valores and "Franja" not in valores, "ningun valor de `analisis_placa_*` llega al PDF"

    def test_sin_fila_de_preguntas_se_trata_como_una_fila_sin_imagen(self, monkeypatch):
        """F1-M11 (la guarda de la linea 917): hoy `_crear_espacio_imagen([])` revienta con IndexError y el control no genera PDF (14, 20 y 23)."""
        tablas, _ = _procesar(monkeypatch, n=False, v=False, con_fila=False)
        assert tablas["imagen"].equals(pd.DataFrame([[None]], columns=["Imagen"]))
        assert tablas["analisis_imagen"].equals(pd.DataFrame([[SIN_DATOS_DEL_ANALISIS_VIEJO]], columns=["Información"]))

    @pytest.mark.parametrize("tabla", ["analisis_placa_verificaciones", "analisis_placa_correcciones"])
    def test_v_son_solo_las_franjas_vigentes(self, monkeypatch, tabla):
        """F1-M19: V sale de `analisis_placa_franjas` y de ninguna de sus dos tablas hermanas."""
        tablas, _ = _procesar(monkeypatch, n=False, v=False, extra={tabla: [{"tipo": "x", "angulo1": 1.0}]})
        assert tablas["analisis_imagen"].equals(pd.DataFrame([[SIN_DATOS_DEL_ANALISIS_VIEJO]], columns=["Información"]))

    def test_v_no_sale_de_n(self, monkeypatch):
        """F1-M06: con N pero sin franjas, y con franjas pero sin N, cada una cuenta por separado."""
        con_n_sin_v, _ = _procesar(monkeypatch, n=True, v=False)
        sin_n_con_v, _ = _procesar(monkeypatch, n=False, v=True)
        assert "analisis_imagen" not in con_n_sin_v
        assert sin_n_con_v["analisis_imagen"].iloc[0, 0] == LINEA_SIN_ANALISIS_NUEVO

    def test_halcyon_y_tomografo_no_reciben_la_seccion_ni_la_linea(self, monkeypatch):
        """Solo 600 e iX: las otras maquinas no ganan ninguna clave (y no hay lectura del analisis nuevo)."""
        monkeypatch.setattr(svc(), "leer", lambda *a, **k: pytest.fail("solo el 600 y el iX leen el analisis nuevo"))
        for maquina in ("Halcyon", "Tomógrafo", "Braquiterapia"):
            datos = {"ref_id": 1, "maquina": maquina}
            assert rm()._con_el_analisis_nuevo(datos) is datos and rm().CLAVE_DEL_ANALISIS_NUEVO not in datos

    @pytest.mark.parametrize("maquina", ["Clinac 600", "Clinac ix"])
    def test_el_analisis_nuevo_se_lee_con_el_ref_del_control_en_la_fase_de_datos(self, monkeypatch, maquina):
        """La lectura va en `_con_el_analisis_nuevo` (el `return` de `_recopilar_datos_completos`), por la UNICA puerta (`svc.leer`) y con el `ref_id`."""
        pedidos = []
        monkeypatch.setattr(svc(), "leer", lambda ref: (pedidos.append(ref), {"capa": "G"})[1])
        datos = rm()._con_el_analisis_nuevo({"ref_id": 41, "maquina": maquina})
        assert pedidos == [41] and datos[rm().CLAVE_DEL_ANALISIS_NUEVO] == {"capa": "G"}

    def test_si_la_lectura_falla_la_excepcion_sube(self, monkeypatch):
        """Regla de PI.8: si falla la lectura de la base, el reporte no sale (no se imprime «sin analisis» como si no lo hubiera)."""
        def falla(ref):
            raise RuntimeError("la base no responde")

        monkeypatch.setattr(svc(), "leer", falla)
        with pytest.raises(RuntimeError, match="la base no responde"):
            rm()._con_el_analisis_nuevo({"ref_id": 1, "maquina": "Clinac 600"})

    def test_el_registro_se_pasa_tal_cual_a_la_seccion(self, monkeypatch):
        registro = {"capa": "B", "marca": object()}
        _datos_con = _datos(n=True)
        _datos_con[rm().CLAVE_DEL_ANALISIS_NUEVO] = registro
        sec = seccion()
        recibidos = []
        monkeypatch.setattr(sec, "tablas_de_la_seccion", lambda r: (recibidos.append(r), {c: pd.DataFrame([["a", "b"]], columns=[c, ""]) for c in sec.CLAVES})[1])
        rm()._procesar_datos_para_reporte(_datos_con, {}, {}, "Clinac 600")
        assert recibidos == [registro] and recibidos[0] is registro


# ======================================================================================================================================================== el PDF de punta a punta

def _peliculas_nuevas(pdf, placa):
    """F1R1-P02: los rectangulos de la pagina de las imagenes del PDF con el tamano en pixeles de la pelicula guardada que NO son el cuadrado viejo de 180 x 180 pt: la pelicula NUEVA. Se identifica por su
    tamano en pixeles y no por condiciones sobre su ancho y su alto en puntos (la figura de los perfiles tambien mide 384 pt de ancho y pasaba por «la pelicula»)."""
    ancho_px, alto_px = PILImage.open(io.BytesIO(placa.datos)).size
    return [r for _, r, _, w, h in imagenes_de(pdf) if (w, h) == (ancho_px, alto_px) and abs(r.width - 180) > 1]


@pytest.mark.parametrize("capa", CAPAS)
class TestLaSeccionDiceLaCapaQueGuardoElRegistro:
    """Parametrizada sobre la capa GUARDADA (R, G y B): el PDF del reporte real dice el nombre, los numeros, las medidas estadisticas y los perfiles de ESA capa y ninguno de otra."""

    def test_el_titulo_dice_la_capa_con_su_adjetivo(self, mundo, capa):
        crudo = texto_de(mundo.pdf(f"capa_{capa}"))
        texto = normal(crudo)
        titulo = f"{TITULO_DE_LA_SECCION}, {CAPA_EN_UNA_FRASE[capa]}"
        assert titulo in texto, titulo
        otras = [c for c in CAPAS if c != capa]
        assert not any(f"{TITULO_DE_LA_SECCION}, {CAPA_EN_UNA_FRASE[o]}" in texto for o in otras)
        assert f"{TITULO_DE_LA_SECCION}, capa:" not in texto and f"capa {capa}" not in _la_seccion(crudo), "ni «capa: verde» ni la letra suelta"

    def test_los_valores_impresos_son_los_guardados_de_esa_capa(self, mundo, capa, verdad):
        guardado = _valores_guardados(mundo, f"capa_{capa}")
        assert guardado["capa"] == capa
        seccion_ = _la_seccion(texto_de(mundo.pdf(f"capa_{capa}")))
        for nombre, rotulo in ROTULOS_ESPERADOS.items():
            esperado = n3(guardado[nombre], con_signo=nombre.startswith("desfase"))
            assert re.search(rf"{re.escape(rotulo)}\s+{re.escape(esperado)}(?![\d])", seccion_), f"{rotulo}: se esperaba {esperado}"
        assert "Estado" not in seccion_.replace("Estado de", ""), "el estado solo sale si la capa no se midio (F1R-7)"

    def test_los_valores_del_motor_coinciden_con_los_guardados(self, mundo, capa, verdad):
        """Convergencia de dos caminos afirmada con una prueba: lo guardado por `svc.guardar` es lo que el motor da sobre esos mismos bytes (el oraculo no sale de F.1)."""
        guardado = _valores_guardados(mundo, f"capa_{capa}")
        for nombre in ROTULOS_ESPERADOS:
            assert abs(guardado[nombre] - verdad["valores"][capa][nombre]) < 1e-9, nombre

    def test_ningun_numero_de_otra_capa_aparece(self, mundo, capa, verdad):
        texto = _la_seccion(texto_de(mundo.pdf(f"capa_{capa}")))
        propios = {n3(verdad["valores"][capa][n], con_signo=n.startswith("desfase")) for n in ROTULOS_ESPERADOS}
        for otra in (c for c in CAPAS if c != capa):
            for nombre in ROTULOS_ESPERADOS:
                ajeno = n3(verdad["valores"][otra][nombre], con_signo=nombre.startswith("desfase"))
                if ajeno not in propios:
                    assert not aparece(ajeno, texto), f"el {nombre} de la capa {otra} ({ajeno}) aparece en el PDF de la capa {capa}"

    def test_las_medidas_estadisticas_del_barrido_son_las_de_esa_capa(self, mundo, capa, verdad):
        seccion_ = _la_seccion(texto_de(mundo.pdf(f"capa_{capa}")))
        assert f"Medidas estadísticas del barrido, {CAPA_EN_UNA_FRASE[capa]}" in seccion_
        for eje in pm().EJES:
            b = verdad["barrido"].ejes[eje].capas[capa]
            e = b.estadistica
            fila = " ".join([eje, n3(b.central.fwhm_mm), n3(e.media_mm), n3(e.mediana_mm), n3(e.desviacion_mm), f"{e.n_medibles} de {e.n_bandas}"])
            assert fila in seccion_, fila

    def test_los_perfiles_van_en_una_figura_de_384_x_340_pt_y_la_pelicula_en_otra(self, mundo, capa, placa):
        pdf = mundo.pdf(f"capa_{capa}")
        medidas = [(r.width, r.height) for _, r, _, _, _ in imagenes_de(pdf)]
        assert len([1 for w, h in medidas if abs(w - 384) < 1 and abs(h - 340) < 1]) == 1, medidas
        peliculas = _peliculas_nuevas(pdf, placa)
        assert len(peliculas) == 1, (peliculas, medidas)
        r = peliculas[0]
        assert r.width <= 384.5 and r.height <= 360.5 and (abs(r.width - 384) < 0.5 or abs(r.height - 360) < 0.5), (r, "la pelicula, encajada en 384 x 360 pt lo mas grande que cabe, y no la figura de los perfiles")

    def test_la_linea_del_piso_la_base_y_la_referencia_estan(self, mundo, capa):
        guardado = _valores_guardados(mundo, f"capa_{capa}")
        seccion_ = _la_seccion(texto_de(mundo.pdf(f"capa_{capa}")))
        piso = pel().texto_breve_del_piso(json.loads(guardado["piso"]), capa)
        assert normal(piso) in seccion_, piso
        assert piso.startswith(f"Piso ({CAPA_EN_UNA_FRASE[capa]}):"), piso
        assert normal(REFERENCIA_TG142) in seccion_
        assert f"Base de la medida {pm().BASE_VALOR_DE_PIXEL}" in seccion_, "la fila de la base: la del registro (valor de pixel en esta siembra), no la de hoy; el pie de parametros tambien la dice y no cuenta"

    def test_sin_veredicto_ni_simbolos(self, mundo, capa):
        seccion_ = _la_seccion(texto_de(mundo.pdf(f"capa_{capa}")))
        assert "Cumple" not in seccion_ and "cumple" not in seccion_.replace("lo evalúa", "")
        assert not any(s in seccion_ for s in SIMBOLOS_DA18)


class TestCambiarLaCapaPorOmisionNoCambiaNingunPdf:
    @pytest.mark.parametrize("capa", ["R", "B"])
    def test_con_la_constante_en_otra_capa_el_texto_del_pdf_es_el_mismo(self, mundo, monkeypatch, capa):
        """Ningun PDF lee `CAPA_POR_OMISION`: la elegida en el menu al guardar es la que manda."""
        antes = normal(texto_de(mundo.pdf(f"capa_{capa}")))
        assert f"{TITULO_DE_LA_SECCION}, {CAPA_EN_UNA_FRASE[capa]}" in antes, "no vacuidad: el PDF trae la seccion de la capa guardada"
        monkeypatch.setattr(pel(), "CAPA_POR_OMISION", "G" if capa == "R" else "R")
        pdf, errores = generar_pdf(mundo.ruta, mundo.fechas[f"capa_{capa}"], "Clinac 600", monkeypatch)
        assert not errores and normal(texto_de(pdf)) == antes


class TestSinAnalisisNuevoElPdfDeSiempre:
    """Los controles viejos: las dos tablas de siempre (la tabla vieja ya no, DA-89), con el PDF real."""

    def test_sin_n_ni_v_dice_no_hay_datos_y_trae_el_recuadro_imagen_vacio(self, mundo):
        pdf = mundo.pdf("nada")
        texto = normal(texto_de(pdf))
        assert SIN_DATOS_DEL_ANALISIS_VIEJO in texto and TITULO_DE_LA_SECCION not in texto and LINEA_SIN_ANALISIS_NUEVO not in texto
        assert "Imagen" in lineas_de(pdf), "el recuadro «Imagen» (vacio) de siempre"
        assert not [i for i in imagenes_de(pdf) if abs(i[1].width - 180) < 1], "sin imagen, ningun cuadrado de 2.5 pulgadas"

    @pytest.mark.parametrize("nombre", ["solo_V", "V_e_I"])
    def test_con_v_y_sin_n_una_linea_en_lugar_de_la_tabla_vieja(self, mundo, nombre):
        """DA-89: los valores de `analisis_placa_*` ya no llegan al PDF; sale la linea, y la imagen vieja como hoy."""
        pdf = mundo.pdf(nombre)
        texto = normal(texto_de(pdf))
        assert LINEA_SIN_ANALISIS_NUEVO in texto
        assert SIN_DATOS_DEL_ANALISIS_VIEJO not in texto and TITULO_DE_LA_SECCION not in texto
        assert ENCABEZADO_DE_LA_TABLA_VIEJA not in texto and "Tam. Campo H" not in texto
        for franja in (77.0, 88.0):
            for desplazamiento in (0.7771, 0.8882, 0.1113, 0.2224, 0.3335, 0.4446, 0.5557, 0.6668, 0.7779, 0.9991):
                assert not aparece(f"{franja + desplazamiento:.3f}", texto), "ningun valor de las tablas viejas llega al PDF"
        assert "Imagen" in lineas_de(pdf)

    def test_con_i_y_sin_n_la_imagen_vieja_sigue_saliendo_como_hoy(self, mundo):
        cuadrados = [i for i in imagenes_de(mundo.pdf("solo_I")) if abs(i[1].width - 180) < 1 and abs(i[1].height - 180) < 1]
        assert len(cuadrados) == 1, "la imagen vieja en su cuadrado de 2.5 x 2.5 pulgadas (180 x 180 pt), re-codificada como hoy"

    def test_sin_fila_de_preguntas_el_pdf_sale_con_el_recuadro_vacio_y_no_hay_datos(self, mundo):
        """Rojo contra HEAD: los controles 14, 20 y 23 no generan PDF (`IndexError`, tragado en «Error generando reporte»). Es el unico cambio en un control sin N y se declara."""
        pdf = mundo.pdf("sin_fila")
        texto = normal(texto_de(pdf))
        assert SIN_DATOS_DEL_ANALISIS_VIEJO in texto and "Imagen" in lineas_de(pdf) and TITULO_DE_LA_SECCION not in texto


class TestConElAnalisisNuevoLaSeccionOcupaElLugarDeLasDosTablas:
    def test_n_sola_no_trae_ni_la_tabla_vieja_ni_no_hay_datos_ni_el_recuadro_vacio(self, mundo):
        pdf = mundo.pdf("N_sola")
        texto = normal(texto_de(pdf))
        assert TITULO_DE_LA_SECCION in texto
        assert SIN_DATOS_DEL_ANALISIS_VIEJO not in texto and LINEA_SIN_ANALISIS_NUEVO not in texto and ENCABEZADO_DE_LA_TABLA_VIEJA not in texto
        assert "Imagen" not in lineas_de(pdf), "ni el recuadro vacio de la imagen vieja"

    def test_n_con_i_la_imagen_vieja_va_despues_de_la_seccion_nueva(self, mundo):
        """F1R-1: primero la sección nueva, detrás la imagen vieja, tal como salía."""
        pdf = mundo.pdf("N_e_I")
        doc = fitz.open(stream=pdf, filetype="pdf")
        try:
            def posicion(texto, exacto=False):
                for p in doc:
                    for r in p.search_for(texto):
                        return (p.number, r.y0)
                return None
            titulo = posicion(TITULO_DE_LA_SECCION)
            imagen_vieja = next(((i[0] - 1, i[1].y0) for i in imagenes_de(pdf) if abs(i[1].width - 180) < 1), None)
        finally:
            doc.close()
        assert titulo is not None and imagen_vieja is not None
        assert titulo < imagen_vieja, "la seccion nueva antes que la imagen vieja"

    def test_n_con_v_e_i_sale_la_seccion_y_la_imagen_vieja_pero_no_la_tabla_vieja(self, mundo):
        """DA-89: con N, la tabla vieja desaparece aunque haya franjas; los valores de las franjas no llegan al PDF."""
        pdf = mundo.pdf("N_V_I")
        texto = normal(texto_de(pdf))
        assert TITULO_DE_LA_SECCION in texto and "Imagen" in lineas_de(pdf)
        assert ENCABEZADO_DE_LA_TABLA_VIEJA not in texto and "Tam. Campo H" not in texto and LINEA_SIN_ANALISIS_NUEVO not in texto and SIN_DATOS_DEL_ANALISIS_VIEJO not in texto
        assert not aparece("77.777", texto) and not aparece("88.888", texto)
        assert len([i for i in imagenes_de(pdf) if abs(i[1].width - 180) < 1]) == 1, "la imagen vieja, una vez"

    def test_n_y_v_sin_i_no_trae_ni_tabla_vieja_ni_recuadro_vacio(self, mundo):
        pdf = mundo.pdf("N_y_V")
        texto = normal(texto_de(pdf))
        assert TITULO_DE_LA_SECCION in texto and ENCABEZADO_DE_LA_TABLA_VIEJA not in texto and "Imagen" not in lineas_de(pdf)

    def test_n_sin_fila_de_preguntas_el_pdf_sale_con_solo_la_seccion(self, mundo):
        pdf = mundo.pdf("N_sin_fila")
        texto = normal(texto_de(pdf))
        assert TITULO_DE_LA_SECCION in texto and SIN_DATOS_DEL_ANALISIS_VIEJO not in texto and "Imagen" not in lineas_de(pdf)

    def test_el_ix_recibe_la_misma_seccion(self, mundo):
        texto = normal(texto_de(mundo.pdf("ix")))
        assert f"{TITULO_DE_LA_SECCION}, capa verde" in texto and SIN_DATOS_DEL_ANALISIS_VIEJO not in texto


# ======================================================================================================================================================== lo guardado manda

def _registro(mundo, nombre):
    return svc().leer(mundo.refs[nombre])


def _espiar_recalcular(monkeypatch):
    llamadas = []
    real = svc().recalcular
    monkeypatch.setattr(svc(), "recalcular", lambda r: (llamadas.append(1), real(r))[1])
    return llamadas


class TestLoGuardadoMandaYSoloSeReconstruyeConLaVersionDeHoyYLoGuardadoReproducido:
    def test_un_analisis_reproducible_se_vuelve_a_medir_una_vez_y_trae_el_barrido_los_perfiles_y_los_parametros(self, mundo, monkeypatch):
        llamadas = _espiar_recalcular(monkeypatch)
        tablas = seccion().tablas_de_la_seccion(_registro(mundo, "capa_G"))
        assert llamadas == [1]
        assert list(tablas) == list(CLAVES_DE_LA_SECCION), "las cinco tablas, en el orden de las claves"

    def test_con_otra_version_no_se_vuelve_a_medir_y_se_imprime_lo_guardado_y_una_frase(self, mundo, monkeypatch):
        """F1R-2 / F1-M08: `svc.recalcular` NO compara la version (mide con el motor de hoy): la compara F.1 antes de reconstruir."""
        llamadas = _espiar_recalcular(monkeypatch)
        registro = _registro(mundo, "otra_version")
        tablas = seccion().tablas_de_la_seccion(registro)
        assert llamadas == [], "con otra version ni se mide"
        assert set(tablas) == {"placa_mensual_valores", "placa_mensual_pelicula"}, sorted(tablas)
        texto = " ".join(" ".join(f) for f in _filas(tablas["placa_mensual_valores"]))
        assert "PM-0" in texto and pm().VERSION_ALGORITMO in texto and "no se imprimen" in texto, texto
        for rotulo in ROTULOS_ESPERADOS.values():
            assert rotulo in texto

    def test_en_el_pdf_con_otra_version_los_valores_son_los_guardados_y_no_hay_barrido_perfiles_ni_parametros(self, mundo, placa):
        pdf = mundo.pdf("otra_version")
        seccion_ = _la_seccion(texto_de(pdf))
        guardado = _valores_guardados(mundo, "otra_version")
        assert aparece(n3(guardado["fwhm_crossplane_mm"]), seccion_) and "PM-0" in seccion_
        assert "Medidas estadísticas del barrido" not in seccion_ and "Perfiles de la capa" not in seccion_ and "Parámetros fijos" not in seccion_
        assert not [i for i in imagenes_de(pdf) if abs(i[1].width - 384) < 1 and abs(i[1].height - 340) < 1], "ninguna figura de perfiles"
        assert len(_peliculas_nuevas(pdf, placa)) == 1, "la pelicula sale igual: es de lo guardado"

    def test_con_un_valor_guardado_alterado_se_imprime_el_alterado_y_no_se_reconstruye(self, mundo, monkeypatch, verdad):
        """F1-M07 / F1-M08: lo impreso es lo GUARDADO (aunque el motor de hoy diga otra cosa) y, como `diferencias` no esta vacia, el PDF lo dice y no dibuja lo demas."""
        guardado = _valores_guardados(mundo, "valor_alterado")
        original = verdad["valores"]["G"]["fwhm_crossplane_mm"]
        assert abs(guardado["fwhm_crossplane_mm"] - (original + 0.5)) < 1e-9
        registro = _registro(mundo, "valor_alterado")
        assert svc().diferencias(registro, svc().recalcular(registro)), "no esta vacia: el valor guardado ya no es el que se mide"
        pdf = mundo.pdf("valor_alterado")
        seccion_ = _la_seccion(texto_de(pdf))
        assert aparece(n3(guardado["fwhm_crossplane_mm"]), seccion_), "se imprime el ALTERADO (lo guardado)"
        assert not aparece(n3(original), seccion_), "no el recalculado"
        assert "Medidas estadísticas del barrido" not in seccion_ and "Perfiles de la capa" not in seccion_ and "Parámetros fijos" not in seccion_
        assert "no se imprimen" in seccion_ and "no salen los valores guardados" in seccion_

    def test_el_detalle_de_lo_que_no_coincide_queda_en_el_registro_de_errores(self, mundo, monkeypatch, tmp_path):
        ruta = tmp_path / "error_log.txt"
        monkeypatch.setenv("RADQA_ERROR_LOG", str(ruta))
        seccion().tablas_de_la_seccion(_registro(mundo, "valor_alterado"))
        log = ruta.read_text(encoding="utf-8")
        assert "F.1" in log and "fwhm_crossplane_mm" in log, log

    def test_con_la_imagen_alterada_volver_a_medir_falla_el_pdf_sale_y_el_detalle_va_al_registro(self, mundo, monkeypatch, tmp_path):
        ruta = tmp_path / "error_log.txt"
        monkeypatch.setenv("RADQA_ERROR_LOG", str(ruta))
        pdf, errores = generar_pdf(mundo.ruta, mundo.fechas["imagen_invalida"], "Clinac 600", monkeypatch)
        assert not errores and pdf is not None, "el reporte no avisa de ningun error: la seccion sale con lo guardado"
        seccion_ = _la_seccion(texto_de(pdf))
        guardado = _valores_guardados(mundo, "imagen_invalida")
        assert aparece(n3(guardado["fwhm_crossplane_mm"]), seccion_) and "no se imprimen" in seccion_ and "Perfiles de la capa" not in seccion_
        assert ruta.exists() and "F.1" in ruta.read_text(encoding="utf-8"), "el detalle tecnico va a error_log.txt"

    def test_con_una_imagen_valida_pero_distinta_el_pdf_trae_lo_guardado_y_la_frase(self, mundo):
        seccion_ = _la_seccion(texto_de(mundo.pdf("imagen_distinta")))
        guardado = _valores_guardados(mundo, "imagen_distinta")
        assert aparece(n3(guardado["fwhm_crossplane_mm"]), seccion_) and "no salen los valores guardados" in seccion_
        assert "Medidas estadísticas del barrido" not in seccion_

    def test_con_puntos_que_no_forman_el_campo_la_pelicula_sale_sin_recuadro_y_lo_dice(self, mundo):
        registro = _registro(mundo, "puntos_malos")
        tablas = seccion().tablas_de_la_seccion(registro)
        assert "placa_mensual_pelicula" in tablas
        filas = _filas(tablas["placa_mensual_pelicula"])
        # F1-R2-P03: la linea dice POR QUE, y por lo que dice el motor (`recuadro_luminoso(...).estado`): una leyenda sin motivo o con otro motivo no pasa
        motivo = pm().recuadro_luminoso(registro["puntos"])
        assert not motivo.ok and isinstance(motivo.estado, str) and motivo.estado.strip(), "el motor dice por que los puntos no forman el campo"
        assert [f[0] for f in filas if f[0].startswith("Sin recuadro")] == [f"Sin recuadro: {motivo.estado}"], filas
        assert not any(f[0] == LEYENDA_DEL_RECUADRO for f in filas)
        flujo = tablas["placa_mensual_pelicula"].iloc[0, 0]
        assert isinstance(flujo, recuadro().PeliculaConRecuadro) and tuple(flujo.esquinas) == ()


# ======================================================================================================================================================== las tablas de la seccion

class TestLasTablasDeLaSeccion:
    def test_la_tabla_de_valores_trae_un_rotulo_por_medida_guardada_con_su_unidad_entre_corchetes(self):
        from services.medidas_placa_mensual import MEDIDAS_GUARDADAS
        rotulos = seccion().ROTULOS
        for medida in MEDIDAS_GUARDADAS:
            if medida.nombre == "estado":
                continue
            assert medida.nombre in rotulos, f"falta el rotulo de {medida.nombre}: una medida nueva sin rotulo cae aqui"
            assert rotulos[medida.nombre].endswith(f"[{medida.unidad}]"), rotulos[medida.nombre]
        assert {k: rotulos[k] for k in ROTULOS_ESPERADOS} == ROTULOS_ESPERADOS

    def test_una_medida_guardada_sin_rotulo_no_se_imprime_en_silencio(self, mundo, monkeypatch):
        from services import medidas_placa_mensual as med
        extra = med.MedidaGuardada("fwhm_diagonal_mm", "mm", "REAL")
        monkeypatch.setattr(seccion(), "MEDIDAS_GUARDADAS", med.MEDIDAS_GUARDADAS + (extra,))
        registro = dict(_registro(mundo, "capa_G"), fwhm_diagonal_mm=1.0)
        with pytest.raises(KeyError):
            seccion().tablas_de_la_seccion(registro)

    def test_la_tabla_de_valores_y_el_resto_son_texto_o_imagen_y_nada_anidado(self, mundo):
        from reportlab.platypus import Image, Table
        for clave, df in seccion().tablas_de_la_seccion(_registro(mundo, "capa_G")).items():
            for fila in df.values.tolist():
                for celda in fila:
                    assert celda is None or isinstance(celda, (str, Paragraph, Image)), (clave, type(celda))
                    assert not isinstance(celda, Table)

    def test_lo_que_no_se_midio_se_imprime_no_medible_y_el_estado_solo_si_no_es_ok(self, mundo, monkeypatch):
        """Adenda 3 y F1R-7: una medida vacia dice «no medible» (nunca «sin dato», cero o vacio) y la fila «Estado» sale solo si la capa no es «ok»."""
        registro = dict(_registro(mundo, "capa_G"), desfase_superior_mm=None, fwhm_inplane_mm=None, estado="no medible: la meseta esta recortada")
        filas = dict((f[0], f[1]) for f in _filas(seccion().tablas_de_la_seccion(registro)["placa_mensual_valores"])[1:] if len(f) == 2)
        assert filas[ROTULOS_ESPERADOS["desfase_superior_mm"]] == NO_MEDIBLE and filas[ROTULOS_ESPERADOS["fwhm_inplane_mm"]] == NO_MEDIBLE
        assert filas["Estado"] == "no medible: la meseta esta recortada"
        assert "sin dato" not in " ".join(" ".join(f) for f in _filas(seccion().tablas_de_la_seccion(registro)["placa_mensual_valores"]))
        ok = [f[0] for f in _filas(seccion().tablas_de_la_seccion(_registro(mundo, "capa_G"))["placa_mensual_valores"])]
        assert "Estado" not in ok

    def test_la_tabla_de_valores_trae_el_titulo_la_cabecera_campo_valor_y_la_referencia(self, mundo):
        filas = _filas(seccion().tablas_de_la_seccion(_registro(mundo, "capa_B"))["placa_mensual_valores"])
        assert filas[0][0] == f"{TITULO_DE_LA_SECCION}, capa azul" and filas[1] == ["Campo", "Valor"]
        assert ["Referencia", REFERENCIA_TG142] in filas
        assert ["Capa reportada", "capa azul"] in filas
        assert any(f[0] == "Piso" and f[1].startswith("Piso (capa azul):") for f in filas)

    @pytest.mark.parametrize("capa", CAPAS)
    def test_la_figura_dibuja_los_dos_perfiles_de_esa_capa_apilados(self, mundo, verdad, capa):
        """F1-M09: la figura de los perfiles se compone con `dibujar_perfil` de E.1 por eje y es de la capa del registro (no del gris ni de otra)."""
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        sec = seccion()
        figura = Figure(figsize=(384 / 72.0, 340 / 72.0), layout="constrained")
        FigureCanvasAgg(figura)
        sec.componer_figura(figura, verdad["resultado"], capa)
        ejes = [a for a in figura.axes if a.get_gid() != "leyenda"]
        assert len(ejes) == 2, "dos ejes apilados: crossplane arriba e inplane abajo"
        assert ejes[0].get_position().y0 > ejes[1].get_position().y0 and abs(ejes[0].get_position().x0 - ejes[1].get_position().x0) < 1e-6, "apilados"
        for eje_, nombre in zip(ejes, pm().EJES):
            medida = getattr(verdad["resultado"].capas[capa], nombre)
            titulo = eje_.get_title()
            assert titulo.startswith(f"{CAPA_EN_UNA_FRASE[capa].capitalize()} (reportada), {nombre}: FWHM {n3(medida.fwhm_mm)} mm"), titulo
            suavizado = [l for l in eje_.get_lines() if l.get_gid() == "perfil:suavizado"]
            assert len(suavizado) == 1 and suavizado[0].get_color().lower() == dibujo().COLOR_CAPA[capa].lower(), "el trazo del color de ESA capa"

    def test_tablas_de_la_seccion_pide_la_figura_de_la_capa_del_registro(self, mundo, monkeypatch):
        sec = seccion()
        pedidas = []
        real = sec.componer_figura
        monkeypatch.setattr(sec, "componer_figura", lambda figura, resultado, capa: (pedidas.append(capa), real(figura, resultado, capa))[1])
        for capa in CAPAS:
            sec.tablas_de_la_seccion(_registro(mundo, f"capa_{capa}"))
        assert pedidas == list(CAPAS)

    def test_la_figura_de_los_perfiles_es_la_del_pdf_de_384_x_340_pt_a_200_dpi(self, mundo):
        from PIL import Image as PILImage
        import io
        tablas = seccion().tablas_de_la_seccion(_registro(mundo, "capa_G"))
        figura = tablas["placa_mensual_perfiles"].iloc[0, 0]
        assert abs(figura.drawWidth - 384) < 1e-6 and abs(figura.drawHeight - 340) < 1e-6
        png = PILImage.open(io.BytesIO(seccion().png_de_los_perfiles(_resultado_de(mundo, "capa_G"), "G")))
        assert all(abs(a - b) <= 1 for a, b in zip(png.size, (384 / 72 * 200, 340 / 72 * 200))), png.size

    def test_el_pie_de_parametros_es_texto_de_los_parametros_guardados(self, mundo):
        registro = _registro(mundo, "capa_G")
        filas = _filas(seccion().tablas_de_la_seccion(registro)["placa_mensual_parametros"])
        assert filas[0][0] == TITULO_DE_LOS_PARAMETROS
        texto = " ".join(filas[1]).replace("<br/>", " ")
        assert normal(dibujo().texto_de_parametros(registro["parametros"]).replace("\n", " ")) in normal(texto), "el pie de la ventana, con los parametros GUARDADOS del registro"
        assert len(texto) > 1000

    def test_el_barrido_se_arma_con_las_filas_de_la_ventana_de_esa_capa(self, mundo, verdad):
        """Una sola manera de escribir un numero: las cifras son las de `filas_de_los_barridos` (E.1)."""
        filas = _filas(seccion().tablas_de_la_seccion(_registro(mundo, "capa_B"))["placa_mensual_barrido"])
        assert filas[0][0] == "Medidas estadísticas del barrido, capa azul" and filas[1][0] == "Eje"
        esperadas = [f for f in dibujo().filas_de_los_barridos(verdad["barrido"]) if f[0] == "Capa azul"]
        assert [f[0] for f in filas[2:]] == [e[1] for e in esperadas] == list(pm().EJES)
        for fila, e in zip(filas[2:], esperadas):
            assert fila[1:] == [e[8], e[5], e[6], e[7], f"{e[4]} de {e[3]}"], (fila, e)


def _resultado_de(mundo, nombre):
    return svc().recalcular(svc().leer(mundo.refs[nombre]))


# ======================================================================================================================================================== el texto que viene de afuera no rompe el PDF

class TestUnTextoConMarcadoNoRompeElPdf:
    def test_el_nombre_de_la_pelicula_virgen_con_ampersand_y_menor_que_sale_tal_cual_en_la_linea_del_piso(self, mundo):
        """Las celdas de texto son `Paragraph` (marcado): un `&` o un `<` del nombre de un archivo (el piso en modo virgen lo nombra) sin escapar tumba el PDF entero con un error de marcado."""
        import contextlib
        import io
        registro = _registro(mundo, "capa_G")
        piso = json.loads(json.dumps(registro["piso"]))
        piso["modo"] = "virgen"
        piso["referencia_virgen"] = {"procedencia": {"archivo": "virgen a&b <c>.tif", "fecha_escaneo": "2026-03-15", "fecha_calculo": "2026-03-16", "sha256": "0123456789abcdef" * 4}}
        tablas = seccion().tablas_de_la_seccion(dict(registro, piso=piso))
        with contextlib.redirect_stdout(io.StringIO()):
            pdf = bytes(pdf_mod().generar_reporte_pdf_multitabla_mensual(tablas, "07/2026", "Fisico de prueba", maquina="Clinac 600", logo_path=None, temp=True))
        assert "virgen a&b <c>.tif" in normal(texto_de(pdf))


# ======================================================================================================================================================== una parte que falla no tumba el PDF

class TestUnaParteQueFallaNoTumbaElPdf:
    """F1R-9 (el patron de B.6): el PDF sale con lo guardado y una frase sin texto tecnico, y el detalle va a `error_log.txt`. En cambio, si falla la lectura de la base, el reporte no sale."""

    def test_si_volver_a_medir_lanza_cualquier_cosa_el_pdf_sale_con_lo_guardado(self, mundo, monkeypatch, tmp_path):
        monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
        monkeypatch.setattr(svc(), "recalcular", lambda r: (_ for _ in ()).throw(RuntimeError("falla del motor")))
        pdf, errores = generar_pdf(mundo.ruta, mundo.fechas["capa_G"], "Clinac 600", monkeypatch)
        assert not errores and pdf is not None
        seccion_ = _la_seccion(texto_de(pdf))
        assert "no se pudo volver a medir" in seccion_ and "falla del motor" not in seccion_, "una frase sin texto tecnico"
        assert "falla del motor" in (tmp_path / "error_log.txt").read_text(encoding="utf-8")
        assert "Perfiles de la capa" not in seccion_

    def test_si_la_figura_falla_salen_el_barrido_y_los_parametros_y_la_frase(self, mundo, monkeypatch, tmp_path):
        monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
        monkeypatch.setattr(seccion(), "png_de_los_perfiles", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no hay figura")))
        pdf, errores = generar_pdf(mundo.ruta, mundo.fechas["capa_G"], "Clinac 600", monkeypatch)
        assert not errores and pdf is not None
        seccion_ = _la_seccion(texto_de(pdf))
        assert "Medidas estadísticas del barrido" in seccion_ and "Parámetros fijos" in seccion_ and "no se pudieron dibujar" in seccion_ and "no hay figura" not in seccion_
        assert "Perfiles de la capa" not in seccion_
        assert "no hay figura" in (tmp_path / "error_log.txt").read_text(encoding="utf-8")

    def test_si_reportlab_no_abre_la_pelicula_el_pdf_sale_sin_ella_con_una_frase(self, mundo, monkeypatch, tmp_path):
        monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
        pdf, errores = generar_pdf(mundo.ruta, mundo.fechas["imagen_invalida"], "Clinac 600", monkeypatch)
        assert not errores and pdf is not None
        seccion_ = _la_seccion(texto_de(pdf))
        assert "no se pudo incluir" in seccion_ and TITULO_DE_LA_PELICULA not in seccion_, "sin la pelicula no hay tabla de la pelicula: solo la frase"
        assert not [i for i in imagenes_de(pdf) if abs(i[1].width - 384) < 1 or abs(i[1].height - 360) < 1]

    @pytest.mark.parametrize("nombre", ["imagen_truncada_png", "imagen_truncada_jpeg"])
    def test_si_la_pelicula_guardada_esta_truncada_el_pdf_sale_sin_ella_con_una_frase(self, mundo, nombre, monkeypatch, tmp_path):
        """F1-R2-PROD-01 / F1R-9: una imagen CORTADA (PNG o JPEG) se abre (Pillow y reportlab leen la cabecera) y no se decodifica: reventaba despues, en `canvas.drawImage` dentro de `doc.build`, y el reporte
        entero terminaba en «Error generando reporte» -- sin PDF, ni siquiera con los valores guardados. La guarda tiene que hacer lo que hace el dibujo, decodificar, para que la pelicula que no se puede dibujar
        no tumbe el PDF: sale la seccion con lo guardado, sin la pelicula y con la frase."""
        imagen = mundo.consulta("SELECT imagen FROM analisis_placa_mensual WHERE ref = ? AND activo = 1", (mundo.refs[nombre],))[0][0]
        with PILImage.open(io.BytesIO(imagen)) as abierta:
            assert abierta.size[0] > 0 and abierta.size[1] > 0, "la cabecera se lee: una guarda que solo abre la imagen no ve nada"
            with pytest.raises(OSError):
                abierta.load()
        monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
        pdf, errores = generar_pdf(mundo.ruta, mundo.fechas[nombre], "Clinac 600", monkeypatch)
        assert not errores and pdf is not None, f"el reporte no avisa de ningun error: la seccion sale con lo guardado ({errores})"
        seccion_ = _la_seccion(texto_de(pdf))
        assert aparece(n3(_valores_guardados(mundo, nombre)["fwhm_crossplane_mm"]), seccion_), "los valores guardados salen"
        assert "no se pudo incluir" in seccion_ and TITULO_DE_LA_PELICULA not in seccion_, "sin la pelicula no hay tabla de la pelicula: solo la frase"
        assert not [i for i in imagenes_de(pdf) if abs(i[1].width - 384) < 1 or abs(i[1].height - 360) < 1]
        registro = (tmp_path / "error_log.txt").read_text(encoding="utf-8")
        assert "F.1" in registro and "la película" in registro, "el detalle tecnico va a error_log.txt"

    def test_si_la_lectura_de_la_base_falla_el_reporte_no_sale(self, mundo, monkeypatch):
        """PI.8: no se imprime «sin analisis» como si no lo hubiera. El aviso es el de siempre, «Error generando reporte»."""
        monkeypatch.setattr(svc(), "leer", lambda ref: (_ for _ in ()).throw(RuntimeError("la base no responde")))
        pdf, errores = generar_pdf(mundo.ruta, mundo.fechas["capa_G"], "Clinac 600", monkeypatch)
        assert pdf is None and len(errores) == 1 and "Error generando reporte" in str(errores[0]) and "la base no responde" in str(errores[0])


# ======================================================================================================================================================== lo que no cambia

class TestSoloLaSeccionNuevaCambiaEnElPdfDeUnControlConAnalisisNuevo:
    def test_el_resto_del_pdf_de_un_control_sin_n_no_nombra_nada_de_la_seccion(self, mundo):
        for nombre in ESCENARIOS_SIN_N:
            texto = normal(texto_de(mundo.pdf(nombre)))
            assert TITULO_DE_LA_SECCION not in texto and "Perfiles de la capa" not in texto and "Medidas estadísticas del barrido" not in texto, nombre

    def test_la_regla_de_siempre_no_pierde_las_demas_tablas(self, mundo):
        for nombre in ("N_sola", "capa_G", "ix"):
            texto = normal(texto_de(mundo.pdf(nombre)))
            for esperado in ("Equipos de medición", "Indicadores angulares gantry", "Resultados aspectos mecánicos", "Tamaño de campo", "Dosimetría"):
                assert esperado in texto, (nombre, esperado)
