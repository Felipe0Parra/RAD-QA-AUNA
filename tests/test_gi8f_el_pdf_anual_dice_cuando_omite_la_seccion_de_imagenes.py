"""GI.8f (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, anotada por GI.3): el informe PDF ANUAL de iX y Halcyon dice cuando omite la seccion de imagenes, y el titulo de la seccion sale.

CAUSA: (1) `obtener_tablas_sistema_imagenes_para_pdf` atrapaba toda excepcion con un `print` (la consola que el `.exe` no tiene) y devolvia `{}`: el informe salia SIN la seccion de imagenes y sin
aviso, indistinguible de «este anio no hubo pruebas de imagen»; (2) el titulo «Analisis de CatPhan» que `E.1` asigna a `tablas_reporte['titulo_sistema_imagenes']` solo se dibuja si esa clave esta
en el orden de categorias del generador anual, y ese orden (`TABLAS_INFORME_IMAGENES`) no la contenia: la rama que lo imprime no se ejecutaba y el PDF anual real no decia «Analisis de CatPhan»
(la prueba de `E.1` verifico la asignacion por AST, no el PDF).

(3) el lector REAL (`catphan_db.reconstruir_resultados_desde_bd`) captura TODA excepcion, la imprime a la consola y devuelve `{}` (revision de GI.8f): el aviso de (1) no llegaba nunca con un fallo
real de lectura, solo con un lector parcheado para lanzar; `{}` con pruebas guardadas se trataba como «sin pruebas».

GARANTIAS, una por bloque:

  1. EL TITULO SALE -- en el PDF anual REAL de un Halcyon y de un iX con pruebas de imagen, una vez, antes de la tabla de parametros de adquisicion y despues de todo lo demas del informe, sin ningun aviso.
  2. SI EL LECTOR LANZA, EL INFORME LO DICE -- el PDF lleva el titulo y la linea «La seccion de imagenes no se incluyo: <motivo>.» (la base ocupada se dice como tal; lo demas, que no se pudieron
     leer las pruebas guardadas; nunca texto crudo de SQLite ni nombres de clases ni una indicacion al usuario dentro del documento), el resto del informe sale completo, el fisico ve UN aviso al
     generarlo y la causa tecnica completa queda en `error_log.txt` UNA vez.
  2b. CON EL LECTOR REAL -- lo mismo cuando falla el lector de verdad (una prueba que no se reconstruye, el esquema roto, pruebas de un tipo que ninguna categoria reconoce): `{}` con pruebas
     guardadas ES un fallo; el lector registra su causa en `error_log.txt` (y sigue imprimiendo el rastro a la consola de desarrollo), devuelve un resultado vacio que LLEVA su causa
     (`ResultadosNoLeidos`, sin los marcos del rastro) y el informe anual dice que omitio la seccion y, si la base estaba ocupada, lo dice como tal.
  2c. EL DIALOGO ES VERDAD -- una frase con el motivo, la indicacion de volver a generar solo si la base estaba ocupada, y la mencion de `error_log.txt` SOLO si la causa quedo escrita.
  3. SIN PRUEBAS DE IMAGEN NO CAMBIA NADA -- un anual sin pruebas de imagen no lleva titulo ni aviso (ni siquiera la clave vacia), no muestra ningun dialogo y no escribe nada en `error_log.txt`
     (no es un error); tampoco es un error que la sesion no se encuentre.
  4. EL TITULO VA CON LO QUE PRESENTA -- en cualquier posicion de la pagina (barrido de 0 a 40 filas de equipos antes de la seccion), el titulo queda en la misma pagina que su primera tabla (informe
     sano) o que su aviso (informe sin la seccion); nunca solo al pie de una pagina (revision de GI.8f, ronda 2).
  4b. UNA SOLA DEFINICION -- el orden de la seccion (titulo, tablas, aviso) lo da UNA funcion que usan las dos maquinas y que va AL FINAL del orden; las dos claves de texto son las que el productor
     asigna y el generador conoce; las demas maquinas (el 600) no dibujan ni titulo ni aviso; el aviso se escapa (un `<` no rompe el PDF).

Nunca se conecta a una BD de referencia: se copia a un temporal primero.
"""
import ast
import inspect
import os
import re
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import data.ManejoDatos.catphan_TAC.catphan_db as cdb
import models.PDF.Anual.reportes_anuales as rep_anual
import models.PDF.pdf as pdf_mod
from models.PDF.Imagenes.reportes_control_sistema_imagenes import titulo_del_informe
from _informe_imagenes import FalsoVisor, Padre, app, avisos, bd_copia, paginas  # noqa: F401  (fixtures y ayudas compartidas de las pruebas del informe de imagenes)

CASOS_CON_IMAGENES = [("Halcyon", 34), ("Clinac ix", 30)]            # sesiones reales de la copia del 21-09: Halcyon 06/2026 (7 pruebas) y iX 05/2026 (4 pruebas)
ID_ANUAL_IX_SIN_IMAGENES = 19                                          # el unico anual real de la copia: iX 02/2026, sin pruebas de imagen
BUSY = "la base de datos estaba ocupada por otro programa"
ILEGIBLE = "no se pudieron leer las pruebas de imagen guardadas de esta sesión"
INDICACION_BUSY = "Vuelva a generar el informe en unos segundos."
DONDE_ESTA_EL_DETALLE = "El detalle técnico quedó en el archivo error_log.txt, junto al programa."
ENTRADA_DEL_INFORME = "El informe anual no pudo incluir la sección de imágenes (sesión {sesion})"
ENTRADA_DEL_LECTOR = "No se pudieron reconstruir los resultados de imágenes"


def _plano(paginas_):
    return re.sub(r"\s+", " ", "\n".join(paginas_))


def _anual(bd_copia, monkeypatch, tmp_path, id_control=None, maquina="Halcyon", fecha="2026", log_escribible=True):
    """El informe anual REAL (`reporte_anual`) con el visor sustituido. Si se da `id_control`, esa sesion de imagenes de la copia pasa a ser el control anual del año (en la copia, nunca en la
    base de referencia). Devuelve el texto de las paginas del PDF y la ruta del error_log de la prueba (que con `log_escribible=False` apunta a una carpeta que no existe: no se puede escribir)."""
    ruta_log = (tmp_path / "error_log.txt") if log_escribible else (tmp_path / "carpeta_inexistente" / "error_log.txt")
    monkeypatch.setenv("RADQA_ERROR_LOG", str(ruta_log))
    if id_control is not None:
        con = sqlite3.connect(bd_copia)
        con.execute("UPDATE controles SET control = 'Anual', fecha = ? WHERE id = ?", (fecha, id_control))
        con.commit()
        con.close()
    monkeypatch.setattr(rep_anual, "PdfViewer", FalsoVisor)
    FalsoVisor.ultimo = {}
    rep_anual.reporte_anual(Padre(bd_copia), fecha=fecha, maquina=maquina, id_maquina=maquina, tipo_reporte="Control Anual")
    pdf = FalsoVisor.ultimo.get("pdf")
    return (paginas(pdf) if pdf else None), ruta_log


def _log(ruta):
    return ruta.read_text(encoding="utf-8") if ruta.exists() else ""


def _espiar_el_generador(monkeypatch):
    """Anota el diccionario de tablas que `reporte_anual` entrega al generador (la clave del aviso vacia cambiaria la maquetacion sin cambiar el texto)."""
    recibidos = []
    original = rep_anual.generar_reporte_pdf_multitabla_anual

    def espia(*a, **k):
        recibidos.append(dict(k.get("tablas_dict", a[0] if a else {})))
        return original(*a, **k)
    monkeypatch.setattr(rep_anual, "generar_reporte_pdf_multitabla_anual", espia)
    return recibidos


# ---------------------------------------------------------------------------
# 1. EL TITULO SALE
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("maquina, sesion", CASOS_CON_IMAGENES)
def test_el_titulo_de_la_seccion_sale_una_vez_en_el_pdf_anual_real_antes_de_los_parametros(app, avisos, bd_copia, monkeypatch, tmp_path, maquina, sesion):
    paginas_, ruta_log = _anual(bd_copia, monkeypatch, tmp_path, id_control=sesion, maquina=maquina)
    assert paginas_, "el informe anual no se genero"
    texto = _plano(paginas_)
    titulo = titulo_del_informe()
    assert texto.count(titulo) == 1, f"el titulo «{titulo}» debe salir exactamente una vez; salio {texto.count(titulo)}"
    assert texto.index(titulo) < texto.index("Parámetros de adquisición"), "el titulo va antes de la primera tabla de la seccion"
    assert "La sección de imágenes no se incluyó" not in texto
    assert [a for a in avisos if a[0] in ("warning", "critical")] == [], avisos
    assert _log(ruta_log) == ""


@pytest.mark.parametrize("maquina, sesion", CASOS_CON_IMAGENES)
def test_la_seccion_de_imagenes_va_al_final_del_informe_despues_de_todo_lo_demas(app, avisos, bd_copia, monkeypatch, tmp_path, maquina, sesion):
    """Revision de GI.8f (R-P1): antes de GI.8f las tablas de imagenes iban al final del informe y asi siguen; si la seccion pasara al frente (o al medio) el resto del informe cambiaria de sitio sin
    que ninguna otra prueba lo viera."""
    paginas_, _ = _anual(bd_copia, monkeypatch, tmp_path, id_control=sesion, maquina=maquina)
    texto = _plano(paginas_)
    assert 0 <= texto.index("Equipos de medición") < texto.index(titulo_del_informe()), "los equipos de medicion van antes que la seccion de imagenes"
    assert texto.index(titulo_del_informe()) < texto.index("Parámetros de adquisición")


# ---------------------------------------------------------------------------
# 2. SI EL LECTOR LANZA, EL INFORME LO DICE
# ---------------------------------------------------------------------------

def _lector_que_lanza(monkeypatch, excepcion):
    def falla(*a, **k):
        raise excepcion
    monkeypatch.setattr(rep_anual, "reconstruir_resultados_desde_bd", falla)


@pytest.mark.parametrize("maquina, sesion", CASOS_CON_IMAGENES)
@pytest.mark.parametrize("excepcion, motivo", [
    (sqlite3.OperationalError("database is locked"), BUSY),
    (RuntimeError("fallo inventado: tabla rota"), ILEGIBLE),
], ids=["base_ocupada", "otro_error"])
def test_si_el_lector_lanza_el_pdf_dice_que_omitio_la_seccion_y_por_que(app, avisos, bd_copia, monkeypatch, tmp_path, maquina, sesion, excepcion, motivo):
    _lector_que_lanza(monkeypatch, excepcion)
    paginas_, ruta_log = _anual(bd_copia, monkeypatch, tmp_path, id_control=sesion, maquina=maquina)
    assert paginas_, "el informe anual debe salir aunque la seccion de imagenes no"
    texto = _plano(paginas_)
    aviso = f"La sección de imágenes no se incluyó: {motivo}."
    titulo = titulo_del_informe()
    assert texto.count(aviso) == 1, texto[-900:]
    assert texto.count(titulo) == 1 and texto.index(titulo) < texto.index(aviso), "el titulo de la seccion va antes del aviso"
    # el documento firmado no lleva instrucciones para quien lo genera: eso va en el dialogo
    assert "Vuelva a generar" not in texto and "vuelva a generar" not in texto
    # lo demas del informe sale completo, y de la seccion de imagenes no sale ninguna tabla
    assert "Equipos de medición" in texto
    assert "Parámetros de adquisición" not in texto and "Espesor de corte" not in texto
    # el fisico ve UN aviso al generar, con el motivo, y ningun error
    advertencias = [a for a in avisos if a[0] == "warning"]
    assert len(advertencias) == 1 and advertencias[0][1][0] == "Sección de imágenes"
    assert advertencias[0][1][1] == rep_anual.texto_del_aviso_de_omision(motivo, True), advertencias[0][1][1]
    assert [a for a in avisos if a[0] == "critical"] == []
    # nada de SQLite crudo ni de clases de excepcion en lo que ve el fisico
    for crudo in ("database is locked", "OperationalError", "RuntimeError", "fallo inventado", "Traceback"):
        assert crudo not in texto and crudo not in advertencias[0][1][1], crudo
    # la causa tecnica completa queda en el archivo de errores, UNA vez
    log = _log(ruta_log)
    assert log.count(ENTRADA_DEL_INFORME.format(sesion=sesion)) == 1, log
    assert type(excepcion).__name__ in log and str(excepcion) in log and "Traceback" in log


@pytest.mark.parametrize("maquina, sesion", CASOS_CON_IMAGENES)
def test_dos_informes_seguidos_cada_uno_dice_lo_suyo_y_un_informe_fallido_no_contamina_al_siguiente(app, avisos, bd_copia, monkeypatch, tmp_path, maquina, sesion):
    """Revision de GI.8f (R-P3): el lector se rompe, se repara y se vuelve a generar: el primero lleva SU aviso y SU dialogo; el segundo, sano, no arrastra nada (ni aviso, ni dialogo, ni entrada nueva en
    el registro) y trae la seccion completa. Y con el lector roto dos veces, dos avisos (no se acumulan ni se pierden). Las dos maquinas."""
    original = rep_anual.reconstruir_resultados_desde_bd
    estado = {"roto": True}

    def lector(*a, **k):
        if estado["roto"]:
            raise RuntimeError("x")
        return original(*a, **k)
    monkeypatch.setattr(rep_anual, "reconstruir_resultados_desde_bd", lector)
    paginas_1, ruta_log = _anual(bd_copia, monkeypatch, tmp_path, id_control=sesion, maquina=maquina)
    assert len([a for a in avisos if a[0] == "warning"]) == 1 and _plano(paginas_1).count("La sección de imágenes no se incluyó") == 1
    paginas_2, _ = _anual(bd_copia, monkeypatch, tmp_path, id_control=None, maquina=maquina)
    assert len([a for a in avisos if a[0] == "warning"]) == 2 and _plano(paginas_2).count("La sección de imágenes no se incluyó") == 1
    assert _log(ruta_log).count(ENTRADA_DEL_INFORME.format(sesion=sesion)) == 2
    estado["roto"] = False
    registro_antes = _log(ruta_log)
    paginas_3, _ = _anual(bd_copia, monkeypatch, tmp_path, id_control=None, maquina=maquina)
    texto = _plano(paginas_3)
    assert "La sección de imágenes no se incluyó" not in texto and texto.count(titulo_del_informe()) == 1 and "Parámetros de adquisición" in texto
    assert len([a for a in avisos if a[0] == "warning"]) == 2, "el informe sano no muestra ningun dialogo"
    assert _log(ruta_log) == registro_antes


# ---------------------------------------------------------------------------
# 2b. CON EL LECTOR REAL
# ---------------------------------------------------------------------------

def _romper_el_lector_real(escenario, monkeypatch, bd_copia, sesion):
    """Hace fallar al lector REAL (`reconstruir_resultados_desde_bd`) por dentro, sin sustituirlo: una prueba que no se reconstruye, el esquema roto, o pruebas de un tipo que ninguna categoria
    reconoce. Devuelve el texto de la excepcion esperada en el registro (o None si el lector no lanza)."""
    if escenario == "una_prueba_no_se_reconstruye":
        def falla(*a, **k):
            raise ValueError("fallo al reconstruir UNA prueba (uniformidad)")
        monkeypatch.setattr(cdb, "reconstruir_uniformidad", falla)
        return "fallo al reconstruir UNA prueba (uniformidad)"
    con = sqlite3.connect(bd_copia)
    try:
        if escenario == "esquema_roto":
            con.execute("ALTER TABLE pruebas RENAME COLUMN imagen_resultado TO imagen_resultado_x")
            con.commit()
            return "imagen_resultado"
        if escenario == "tipos_sin_categoria":
            con.execute("UPDATE pruebas SET id_tipo = id_tipo + 100 WHERE id_sesion = ?", (sesion,))        # tipos 101 a 107: ninguna categoria los reconoce (y (sesion, tipo) sigue siendo unico)
            con.commit()
            return None
    finally:
        con.close()
    raise AssertionError(escenario)


@pytest.mark.parametrize("maquina, sesion", CASOS_CON_IMAGENES)
@pytest.mark.parametrize("escenario", ["una_prueba_no_se_reconstruye", "esquema_roto", "tipos_sin_categoria"])
def test_si_el_lector_real_falla_el_informe_anual_dice_que_omitio_la_seccion(app, avisos, bd_copia, monkeypatch, tmp_path, maquina, sesion, escenario):
    """Revision de GI.8f (P1, reproducido): el lector REAL captura toda excepcion, la imprime a la consola y devuelve `{}` -- y un `{}` con pruebas guardadas se trataba como «este año no hubo pruebas
    de imagen»: el informe salia sin la seccion, sin titulo, sin aviso, sin dialogo y sin una linea en `error_log.txt`. Ahora `{}` con pruebas guardadas es un fallo: el informe lo dice y el
    lector deja la causa en el registro."""
    causa = _romper_el_lector_real(escenario, monkeypatch, bd_copia, sesion)
    paginas_, ruta_log = _anual(bd_copia, monkeypatch, tmp_path, id_control=sesion, maquina=maquina)
    assert paginas_, "el informe anual debe salir aunque la seccion de imagenes no"
    texto = _plano(paginas_)
    assert texto.count(f"La sección de imágenes no se incluyó: {ILEGIBLE}.") == 1, texto[-700:]
    assert texto.count(titulo_del_informe()) == 1 and "Equipos de medición" in texto
    assert "Parámetros de adquisición" not in texto and "Espesor de corte" not in texto
    advertencias = [a for a in avisos if a[0] == "warning"]
    assert len(advertencias) == 1 and advertencias[0][1][1] == rep_anual.texto_del_aviso_de_omision(ILEGIBLE, True)
    assert [a for a in avisos if a[0] == "critical"] == []
    log = _log(ruta_log)
    assert log.count(ENTRADA_DEL_INFORME.format(sesion=sesion)) == 1, log                        # la consecuencia, una vez
    if causa is not None:
        assert log.count(ENTRADA_DEL_LECTOR) == 1 and causa in log and "Traceback" in log, log     # la causa del lector, una vez y con su rastro
    else:
        assert ENTRADA_DEL_LECTOR not in log, "sin excepcion no hay causa tecnica que registrar"


@pytest.mark.parametrize("maquina, sesion", CASOS_CON_IMAGENES)
def test_si_el_lector_real_falla_con_la_base_ocupada_el_informe_lo_dice_como_tal(app, avisos, bd_copia, monkeypatch, tmp_path, maquina, sesion):
    """Revision de GI.8f, ronda 2 (R2-P4 / PR2-02): el lector real captura el `database is locked` y devolvia un `{}` mudo, asi que «la base ocupada se dice como tal» solo se cumplia con un
    lector parcheado. Ahora el resultado vacio lleva su causa: el aviso del PDF dice que la base estaba ocupada (sin indicaciones) y el dialogo pide volver a generar el informe."""
    def falla(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(cdb, "reconstruir_uniformidad", falla)
    paginas_, ruta_log = _anual(bd_copia, monkeypatch, tmp_path, id_control=sesion, maquina=maquina)
    texto = _plano(paginas_)
    assert texto.count(f"La sección de imágenes no se incluyó: {BUSY}.") == 1 and "Vuelva a generar" not in texto
    advertencias = [a for a in avisos if a[0] == "warning"]
    assert len(advertencias) == 1 and advertencias[0][1][1] == rep_anual.texto_del_aviso_de_omision(BUSY, True)
    assert INDICACION_BUSY in advertencias[0][1][1]
    log = _log(ruta_log)
    assert log.count(ENTRADA_DEL_LECTOR) == 1 and "database is locked" in log and log.count(ENTRADA_DEL_INFORME.format(sesion=sesion)) == 1


@pytest.mark.parametrize("escenario", ["una_prueba_no_se_reconstruye", "tipos_sin_categoria"])
def test_si_el_lector_real_falla_y_el_registro_no_se_puede_escribir_el_dialogo_no_promete_error_log(app, avisos, bd_copia, monkeypatch, tmp_path, escenario):
    """Revision de GI.8f, ronda 2 (PR2-01): el hueco de cobertura de la rama que la ronda 1 agrego (lectura vacia con pruebas guardadas): `registrado` sale de la entrada de consecuencia y,
    si no se pudo escribir, el dialogo no afirma que el detalle quedo en el archivo. El informe sale igual, con su aviso."""
    _romper_el_lector_real(escenario, monkeypatch, bd_copia, 34)
    paginas_, ruta_log = _anual(bd_copia, monkeypatch, tmp_path, id_control=34, maquina="Halcyon", log_escribible=False)
    assert paginas_ and not ruta_log.exists()
    assert _plano(paginas_).count(f"La sección de imágenes no se incluyó: {ILEGIBLE}.") == 1
    advertencias = [a for a in avisos if a[0] == "warning"]
    assert len(advertencias) == 1 and advertencias[0][1][1] == rep_anual.texto_del_aviso_de_omision(ILEGIBLE, False)
    assert "error_log.txt" not in advertencias[0][1][1]


def test_el_lector_sin_pantalla_devuelve_un_vacio_con_su_causa_sin_marcos_imprime_el_rastro_y_lo_registra(app, bd_copia, monkeypatch, tmp_path, capsys):
    """El contrato del lector cuando falla sin `label` (el informe PDF): sigue siendo un diccionario VACIO (todo llamador que pregunte `if not resultados` o compare con `{}` no cambia), lleva su
    causa en `.causa` SIN los marcos del rastro (retenerlos mantendria vivas las imagenes leidas), el rastro sigue yendo a la consola de desarrollo (revision PR2-03) y la causa queda en el registro."""
    registro = tmp_path / "error_log.txt"
    monkeypatch.setenv("RADQA_ERROR_LOG", str(registro))

    original = cdb.reconstruir_uniformidad

    def falla(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(cdb, "reconstruir_uniformidad", falla)
    capsys.readouterr()
    resultado = cdb.reconstruir_resultados_desde_bd(42)
    assert isinstance(resultado, cdb.ResultadosNoLeidos) and resultado == {} and not resultado and len(resultado) == 0
    assert isinstance(resultado.causa, sqlite3.OperationalError) and str(resultado.causa) == "database is locked" and resultado.causa.__traceback__ is None
    err = capsys.readouterr().err
    assert "Traceback" in err and "database is locked" in err, "el rastro sigue yendo a la consola de desarrollo"
    log = _log(registro)
    assert log.count(ENTRADA_DEL_LECTOR) == 1 and "database is locked" in log and "Traceback" in log
    # un lector sano devuelve un diccionario normal y no escribe nada
    monkeypatch.setattr(cdb, "reconstruir_uniformidad", original)
    sano = cdb.reconstruir_resultados_desde_bd(42)
    assert sano and not isinstance(sano, cdb.ResultadosNoLeidos) and log == _log(registro)


def test_un_resultado_no_leido_se_comporta_como_un_diccionario_vacio_y_acepta_cualquier_causa():
    r = cdb.ResultadosNoLeidos(ValueError("x"))
    assert r == {} and {} == r and not r and dict(r) == {} and r.get("a") is None and list(r) == []
    otro = cdb.ResultadosNoLeidos(None)
    assert otro.causa is None and not otro


# ---------------------------------------------------------------------------
# 2c. EL DIALOGO ES VERDAD
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("motivo, registrado, esperado", [
    (ILEGIBLE, True, f"El informe se generará sin la sección de imágenes: {ILEGIBLE}.\n\n{DONDE_ESTA_EL_DETALLE}"),
    (ILEGIBLE, False, f"El informe se generará sin la sección de imágenes: {ILEGIBLE}."),
    (BUSY, True, f"El informe se generará sin la sección de imágenes: {BUSY}.\n\n{INDICACION_BUSY}\n\n{DONDE_ESTA_EL_DETALLE}"),
    (BUSY, False, f"El informe se generará sin la sección de imágenes: {BUSY}.\n\n{INDICACION_BUSY}"),
])
def test_el_texto_del_dialogo_dice_el_motivo_la_indicacion_solo_si_la_base_estaba_ocupada_y_el_registro_solo_si_se_escribio(motivo, registrado, esperado):
    assert rep_anual.texto_del_aviso_de_omision(motivo, registrado) == esperado
    # una sola frase con mayuscula inicial y punto final (revision P2: el motivo iba en minuscula despues de un punto)
    primera = rep_anual.texto_del_aviso_de_omision(motivo, registrado).split("\n\n")[0]
    assert primera[0].isupper() and primera.endswith(".") and primera.count(". ") == 0


def test_si_el_registro_no_se_puede_escribir_el_dialogo_no_promete_error_log(app, avisos, bd_copia, monkeypatch, tmp_path):
    """Revision de GI.8f (P5): `registrar_error` devuelve False si no puede escribir; el dialogo no afirma entonces que el detalle quedo en el archivo. El informe sale igual con su aviso."""
    _lector_que_lanza(monkeypatch, RuntimeError("x"))
    paginas_, ruta_log = _anual(bd_copia, monkeypatch, tmp_path, id_control=34, maquina="Halcyon", log_escribible=False)
    assert not ruta_log.exists() and paginas_
    assert _plano(paginas_).count(f"La sección de imágenes no se incluyó: {ILEGIBLE}.") == 1
    advertencias = [a for a in avisos if a[0] == "warning"]
    assert len(advertencias) == 1 and advertencias[0][1][1] == rep_anual.texto_del_aviso_de_omision(ILEGIBLE, False)
    assert "error_log.txt" not in advertencias[0][1][1]


# ---------------------------------------------------------------------------
# 3. SIN PRUEBAS DE IMAGEN NO CAMBIA NADA
# ---------------------------------------------------------------------------

def test_un_anual_sin_pruebas_de_imagen_no_lleva_titulo_ni_aviso_ni_dialogo_ni_registro(app, avisos, bd_copia, monkeypatch, tmp_path):
    recibidos = _espiar_el_generador(monkeypatch)
    paginas_, ruta_log = _anual(bd_copia, monkeypatch, tmp_path, id_control=None, maquina="Clinac ix", fecha="02/2026")
    assert paginas_
    texto = _plano(paginas_)
    assert titulo_del_informe() not in texto and "Análisis de CatPhan" not in texto
    assert "La sección de imágenes no se incluyó" not in texto
    assert [a for a in avisos if a[0] in ("warning", "critical")] == [], avisos
    assert _log(ruta_log) == ""
    # revision de GI.8f (R-P4): ni siquiera la clave del aviso vacia (un parrafo vacio y un espaciador cambiarian la maquetacion sin cambiar el texto)
    assert len(recibidos) == 1 and pdf_mod.CLAVE_TITULO_IMAGENES not in recibidos[0] and pdf_mod.CLAVE_AVISO_IMAGENES not in recibidos[0], list(recibidos[0])


def test_con_la_seccion_el_generador_recibe_el_titulo_y_no_el_aviso_y_roto_recibe_las_dos_claves(app, avisos, bd_copia, monkeypatch, tmp_path):
    recibidos = _espiar_el_generador(monkeypatch)
    _anual(bd_copia, monkeypatch, tmp_path, id_control=34, maquina="Halcyon")
    assert pdf_mod.CLAVE_TITULO_IMAGENES in recibidos[0] and pdf_mod.CLAVE_AVISO_IMAGENES not in recibidos[0]
    _lector_que_lanza(monkeypatch, RuntimeError("x"))
    _anual(bd_copia, monkeypatch, tmp_path, id_control=None, maquina="Halcyon")
    assert recibidos[1][pdf_mod.CLAVE_TITULO_IMAGENES] == titulo_del_informe()
    assert recibidos[1][pdf_mod.CLAVE_AVISO_IMAGENES] == rep_anual.AVISO_SECCION_OMITIDA.format(motivo=ILEGIBLE)


def test_la_funcion_publica_de_siempre_sigue_dando_solo_las_tablas(app, bd_copia):
    db = Padre(bd_copia).opeenDatabase()
    tablas, motivo, registrado = rep_anual.obtener_tablas_sistema_imagenes_y_motivo(db, 42)
    assert motivo is None and registrado is None and tablas and "parametros_adquisicion" in tablas
    solo = rep_anual.obtener_tablas_sistema_imagenes_para_pdf(db, 42)
    assert isinstance(solo, dict) and list(solo) == list(tablas)
    # un anual sin pruebas: ni tablas ni motivo (no es un error)
    assert rep_anual.obtener_tablas_sistema_imagenes_y_motivo(db, 19) == rep_anual.SeccionDeImagenes({}, None, None)
    assert rep_anual.obtener_tablas_sistema_imagenes_para_pdf(db, 19) == {}


def test_que_la_sesion_no_se_encuentre_no_es_un_error(app, avisos, bd_copia, monkeypatch, tmp_path):
    """Revision de GI.8f (R-P2): hay pruebas de imagen pero la fila de la sesion no se lee (`_obtener_info_sesion` da None): ni motivo ni registro ni dialogo; el informe no cambia."""
    registro = tmp_path / "error_log.txt"
    monkeypatch.setenv("RADQA_ERROR_LOG", str(registro))
    monkeypatch.setattr(rep_anual.ReporteControlSistemaImagenes, "_obtener_info_sesion", lambda self, db, ref: None)
    db = Padre(bd_copia).opeenDatabase()
    assert rep_anual.obtener_tablas_sistema_imagenes_y_motivo(db, 42) == rep_anual.SeccionDeImagenes({}, None, None)
    assert _log(registro) == "" and [a for a in avisos if a[0] in ("warning", "critical")] == []


def test_pruebas_guardadas_y_lectura_vacia_si_es_un_error_y_sin_pruebas_no(app, bd_copia, monkeypatch, tmp_path):
    """La frontera de la revision (P1): con pruebas guardadas, `{}` del lector es un fallo con motivo y registro; sin pruebas guardadas, `{}` no es nada."""
    monkeypatch.setenv("RADQA_ERROR_LOG", str(tmp_path / "error_log.txt"))
    monkeypatch.setattr(rep_anual, "reconstruir_resultados_desde_bd", lambda *a, **k: {})
    db = Padre(bd_copia).opeenDatabase()
    con_pruebas = rep_anual.obtener_tablas_sistema_imagenes_y_motivo(db, 42)
    assert con_pruebas.tablas == {} and con_pruebas.motivo == ILEGIBLE and con_pruebas.registrado is True
    sin_pruebas = rep_anual.obtener_tablas_sistema_imagenes_y_motivo(db, 19)
    assert sin_pruebas == rep_anual.SeccionDeImagenes({}, None, None)


# ---------------------------------------------------------------------------
# 4. UNA SOLA DEFINICION
# ---------------------------------------------------------------------------

def _generar(tablas, maquina):
    pdf = pdf_mod.generar_reporte_pdf_multitabla_anual(
        tablas_dict=tablas, fecha="2026", user="Físico", tipo_reporte="Anual", maquina=maquina, id_maquina=maquina, temp=True)
    datos = pdf.data() if hasattr(pdf, "data") else pdf
    return paginas(bytes(datos))


def _equipos_con(filas):
    import pandas as pd
    return pd.DataFrame({"Tipo de equipo": [f"Cámara {i}" for i in range(filas)], "Modelo": ["X"] * filas, "Serie": ["1"] * filas, "Factor": ["1.0"] * filas})


@pytest.mark.parametrize("maquina, sesion", CASOS_CON_IMAGENES)
def test_el_titulo_queda_en_la_misma_pagina_que_su_primera_tabla_en_cualquier_posicion(app, bd_copia, maquina, sesion):
    """Revision de GI.8f, ronda 2 (R2-P2, reproducido: 9 de 36 variantes del iX): `Heading2` solo se unia al `Spacer` que le seguia, asi que el titulo podia quedar solo al pie de una pagina con
    su primera tabla en la siguiente. Se barre cuantas filas de equipos hay antes de la seccion (0 a 40): el titulo y «Parámetros de adquisición» van siempre en la misma pagina."""
    db = Padre(bd_copia).opeenDatabase()
    tablas_img = rep_anual.obtener_tablas_sistema_imagenes_y_motivo(db, sesion).tablas
    assert "parametros_adquisicion" in tablas_img
    titulo = titulo_del_informe()
    con_titulo_y_tabla = 0
    for filas in range(0, 41):
        paginas_ = _generar({"equipos": _equipos_con(filas), pdf_mod.CLAVE_TITULO_IMAGENES: titulo, **tablas_img}, maquina)
        donde_titulo = [i for i, pagina in enumerate(paginas_) if titulo in _plano([pagina])]
        donde_tabla = [i for i, pagina in enumerate(paginas_) if "Parámetros de adquisición" in _plano([pagina])]
        assert len(donde_titulo) == 1 and donde_titulo == donde_tabla[:1], (maquina, filas, donde_titulo, donde_tabla)
        con_titulo_y_tabla += 1
    assert con_titulo_y_tabla == 41


@pytest.mark.parametrize("maquina", ["Halcyon", "Clinac ix"])
def test_el_titulo_queda_en_la_misma_pagina_que_su_aviso_en_cualquier_posicion(app, maquina):
    """Lo mismo para el informe sin la seccion (R2-P1, reproducido: 3 de 36 variantes del iX): el aviso no se separa de su titulo."""
    titulo, aviso = titulo_del_informe(), rep_anual.AVISO_SECCION_OMITIDA.format(motivo=ILEGIBLE)
    for filas in range(0, 41):
        paginas_ = _generar({"equipos": _equipos_con(filas), pdf_mod.CLAVE_TITULO_IMAGENES: titulo, pdf_mod.CLAVE_AVISO_IMAGENES: aviso}, maquina)
        donde_titulo = [i for i, pagina in enumerate(paginas_) if titulo in _plano([pagina])]
        donde_aviso = [i for i, pagina in enumerate(paginas_) if aviso in _plano([pagina])]
        assert len(donde_titulo) == 1 and donde_titulo == donde_aviso, (maquina, filas, donde_titulo, donde_aviso)


def test_el_orden_de_la_seccion_es_titulo_tablas_aviso_y_solo_lo_que_hay():
    f = pdf_mod.categorias_de_imagenes_anual
    todo = {"aviso_sistema_imagenes": "a", "uniformidad": 1, "titulo_sistema_imagenes": "t", "parametros_adquisicion": 2, "espesor": 3, "otra_cosa": 4}
    assert f(todo) == ["titulo_sistema_imagenes", "parametros_adquisicion", "espesor", "uniformidad", "aviso_sistema_imagenes"]
    assert f({}) == [] and f({"espesor": 1}) == ["espesor"] and f({"titulo_sistema_imagenes": "t"}) == ["titulo_sistema_imagenes"]


@pytest.mark.parametrize("maquina", ["Halcyon", "Clinac ix"])
def test_el_generador_dibuja_el_titulo_y_el_aviso_en_ese_orden_y_escapa_el_aviso(app, maquina):
    texto = _plano(_generar({"titulo_sistema_imagenes": "Título de prueba", "aviso_sistema_imagenes": "La sección no se incluyó: a <b> & c"}, maquina))
    assert "Título de prueba" in texto and "La sección no se incluyó: a <b> & c" in texto
    assert texto.index("Título de prueba") < texto.index("La sección no se incluyó")


def test_otras_maquinas_no_dibujan_ni_titulo_ni_aviso(app):
    texto = _plano(_generar({"titulo_sistema_imagenes": "Título de prueba", "aviso_sistema_imagenes": "Aviso de prueba"}, "Clinac 600"))
    assert "Título de prueba" not in texto and "Aviso de prueba" not in texto


def test_las_dos_claves_de_texto_son_las_que_el_productor_asigna_y_el_generador_conoce():
    assert pdf_mod.CLAVE_TITULO_IMAGENES == "titulo_sistema_imagenes" and pdf_mod.CLAVE_AVISO_IMAGENES == "aviso_sistema_imagenes"
    fuente = inspect.getsource(rep_anual.reporte_anual)
    claves = {n.slice.value for n in ast.walk(ast.parse(fuente)) if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str)}
    assert {pdf_mod.CLAVE_TITULO_IMAGENES, pdf_mod.CLAVE_AVISO_IMAGENES} <= claves


def test_las_dos_maquinas_usan_la_misma_funcion_y_no_queda_el_bucle_duplicado():
    fuente = inspect.getsource(pdf_mod.generar_reporte_pdf_multitabla_anual)
    assert fuente.count("categorias_de_imagenes_anual(tablas_dict)") == 2, "iX y Halcyon deben usar la misma funcion"
    assert "orden_categorias_img" not in fuente, "no debe quedar el bucle propio de cada maquina"
    assert inspect.getsource(pdf_mod).count("def categorias_de_imagenes_anual") == 1


def test_la_seccion_de_imagenes_se_agrega_al_final_del_orden_en_las_dos_maquinas():
    """Revision de GI.8f (R-P1), a nivel del generador: la seccion se AGREGA (`orden_categorias += ...`) a la lista que cada maquina ya traia; nunca la reemplaza ni va al frente."""
    arbol = ast.parse(inspect.getsource(pdf_mod.generar_reporte_pdf_multitabla_anual))
    aumentos = [n for n in ast.walk(arbol) if isinstance(n, ast.AugAssign) and isinstance(n.op, ast.Add) and isinstance(n.target, ast.Name) and n.target.id == "orden_categorias"
                and isinstance(n.value, ast.Call) and getattr(n.value.func, "id", "") == "categorias_de_imagenes_anual"]
    assert len(aumentos) == 2, "una por maquina (Halcyon e iX)"
    for aumento in aumentos:                     # justo antes, en el mismo bloque, la lista de esa maquina ya esta asignada
        bloque = next(b for n in ast.walk(arbol) for b in [getattr(n, "body", None)] if isinstance(b, list) and aumento in b)
        anteriores = bloque[:bloque.index(aumento)]
        assert any(isinstance(n, ast.Assign) and any(isinstance(o, ast.Name) and o.id == "orden_categorias" for o in n.targets) for n in anteriores)


def test_el_aviso_y_su_dialogo_se_arman_solo_con_el_motivo_del_lector():
    """Ni el PDF ni el dialogo llevan la excepcion cruda: la unica funcion que convierte excepcion en palabras es `_motivo_de_la_omision`."""
    assert rep_anual._motivo_de_la_omision(sqlite3.OperationalError("database is locked")) == BUSY
    assert rep_anual._motivo_de_la_omision(sqlite3.OperationalError("no such column: x")) == ILEGIBLE
    assert rep_anual._motivo_de_la_omision(KeyError("k")) == ILEGIBLE
    assert rep_anual._motivo_de_la_omision(None) == ILEGIBLE
    assert rep_anual.AVISO_SECCION_OMITIDA.format(motivo="m") == "La sección de imágenes no se incluyó: m."
    assert rep_anual.MOTIVO_BASE_OCUPADA == BUSY and rep_anual.MOTIVO_NO_SE_PUDO_LEER == ILEGIBLE and rep_anual.INDICACION_BASE_OCUPADA == INDICACION_BUSY
