"""E.3 (PLAN_HANDOFF_IMAGENES_22-09.md §6): el segundo físico llega al informe PDF de imágenes.

CAUSA. **[código]** `_obtener_info_sesion` consultaba `SELECT c.equipo, c.fecha, c.user_id` y no pedía
`user_id_f2`, que existe en `controles`. **[medido]** el dato está: 9 de las 10 sesiones de imágenes de la
copia del 21-09 lo traen (las dos de ayer, 47 y 48: *Cristian Castellanos* y *Luz Adriana Maya*). El
informe nunca lo leyó: salía una sola firma, aunque el control lo hicieron dos personas. El generador
compartido (`pdf.py`) YA sabía dibujar dos firmas (lo usan el mensual y el anual); faltaba pasárselo.

Lo que este archivo garantiza:

  1. DOS FÍSICOS -- la sesión 47 lleva a los dos: sus nombres en "Información general" y al pie, y
     **dos** firmas (imágenes en la franja de firmas), cada una con su rol.
  2. SIN SEGUNDO FÍSICO -- la sesión 30 (sin `user_id_f2`) sale igual, con **una** firma, sin hueco,
     sin línea "Físico Médico 2" y sin error.
  3. NOMBRES CON ESPACIOS -- `users.fullname = ' Andres David Loaiza Baena'` existe con espacio inicial
     (real). El informe lo resuelve comparando con TRIM **de los dos lados** y no toca el dato.
  4. EL CENTINELA HISTÓRICO `' ---- '` no se imprime si reaparece en una BD vieja.
  5. UN NOMBRE SIN CUENTA se imprime y sale sin firma; una misma persona como Físico 1 y 2 sale
     con las dos firmas (el dato es el dato).
"""
import sqlite3

import pytest

from _informe_imagenes import app, avisos, bd_copia, generar, paginas  # noqa: F401  (fixtures)

# Las firmas se dibujan en la franja inferior de la página (de y=55 a y=105 medido desde abajo;
# de arriba, en una página de 792 pt, empieza cerca de 687).
FRANJA_FIRMAS_DESDE_ARRIBA = 680


def _firmas_de_la_pagina(pdf_bytes, n_pagina=0):
    import fitz
    pagina = fitz.open(stream=pdf_bytes, filetype="pdf")[n_pagina]
    return [i for i in pagina.get_image_info() if i["bbox"][1] >= FRANJA_FIRMAS_DESDE_ARRIBA]


def _cambiar(bd, sql, *args):
    con = sqlite3.connect(bd)
    con.execute(sql, args)
    con.commit()
    con.close()


def _generar_ok(app, avisos, bd_copia, monkeypatch, ref, equipo, fecha):
    ok, visor = generar(bd_copia, monkeypatch, ref, equipo, fecha)
    assert ok is True and avisos == [], f"la generación falló: {avisos}"
    return visor["pdf"], paginas(visor["pdf"])


# ---------------------------------------------------------------------------
# 1. DOS FÍSICOS
# ---------------------------------------------------------------------------

def test_la_sesion_47_lleva_a_los_dos_fisicos_y_las_dos_firmas(app, avisos, bd_copia, monkeypatch):
    pdf, textos = _generar_ok(app, avisos, bd_copia, monkeypatch, 47, "Halcyon", "22/09/2026")
    for n, texto in enumerate(textos, 1):
        assert "Físico Médico: Cristian Castellanos" in texto, f"página {n}: falta el Físico 1"
        assert "Físico Médico 2: Luz Adriana Maya" in texto, f"página {n}: falta el Físico 2"
        # nombre + rol al pie: cada nombre aparece dos veces por página (encabezado y firma)
        assert texto.count("Cristian Castellanos") == 2
        assert texto.count("Luz Adriana Maya") == 2
        assert len(_firmas_de_la_pagina(pdf, n - 1)) == 2, f"página {n}: se esperaban 2 firmas"


def test_los_roles_de_los_dos_salen_al_pie(app, avisos, bd_copia, monkeypatch):
    _pdf, textos = _generar_ok(app, avisos, bd_copia, monkeypatch, 47, "Halcyon", "22/09/2026")
    # "Físico Médico" como rol al pie, uno por firmante (además de las etiquetas del encabezado)
    lineas = [l.strip() for l in textos[0].splitlines()]
    assert lineas.count("Físico Médico") == 2


def test_la_sesion_48_del_tomografo_tambien(app, avisos, bd_copia, monkeypatch):
    pdf, textos = _generar_ok(app, avisos, bd_copia, monkeypatch, 48, "Tomógrafo", "22/09/2026")
    assert "Físico Médico 2: Luz Adriana Maya" in textos[0]
    assert len(_firmas_de_la_pagina(pdf)) == 2


# ---------------------------------------------------------------------------
# 2. SIN SEGUNDO FÍSICO
# ---------------------------------------------------------------------------

def test_una_sesion_sin_segundo_fisico_sale_con_una_sola_firma_y_sin_error(
        app, avisos, bd_copia, monkeypatch):
    pdf, textos = _generar_ok(app, avisos, bd_copia, monkeypatch, 30, "Clinac ix", "05/2026")
    for n, texto in enumerate(textos, 1):
        assert "Físico Médico: Luz Adriana Maya" in texto
        assert "Físico Médico 2" not in texto, f"página {n}: aparece un Físico 2 que no existe"
        assert len(_firmas_de_la_pagina(pdf, n - 1)) == 1


# ---------------------------------------------------------------------------
# 3. NOMBRES CON ESPACIOS
# ---------------------------------------------------------------------------

def test_la_sesion_42_resuelve_el_nombre_con_espacio_inicial(app, avisos, bd_copia, monkeypatch):
    """Caso REAL: `' Andres David Loaiza Baena'` tal cual está en `users` y en `controles`."""
    pdf, textos = _generar_ok(app, avisos, bd_copia, monkeypatch, 42, "Tomógrafo", "07/2026")
    assert "Físico Médico 2: Andres David Loaiza Baena" in textos[0]       # sin el espacio que sobra
    assert len(_firmas_de_la_pagina(pdf)) == 2                              # su firma se encontró


def test_el_control_con_el_nombre_recortado_encuentra_al_usuario_con_espacio(
        app, avisos, bd_copia, monkeypatch):
    _cambiar(bd_copia, "UPDATE controles SET user_id_f2 = ? WHERE id = 42", "Andres David Loaiza Baena")
    pdf, textos = _generar_ok(app, avisos, bd_copia, monkeypatch, 42, "Tomógrafo", "07/2026")
    assert "Físico Médico 2: Andres David Loaiza Baena" in textos[0]
    assert len(_firmas_de_la_pagina(pdf)) == 2, "TRIM en el control: no encontró la firma del usuario"


def test_el_usuario_recortado_es_encontrado_desde_un_control_con_espacio(
        app, avisos, bd_copia, monkeypatch):
    # (sqlite3 abre con las claves foráneas apagadas: el control conserva su nombre con espacio)
    _cambiar(bd_copia, "UPDATE users SET fullname = ? WHERE id = 6", "Andres David Loaiza Baena")
    pdf, textos = _generar_ok(app, avisos, bd_copia, monkeypatch, 42, "Tomógrafo", "07/2026")
    assert "Físico Médico 2: Andres David Loaiza Baena" in textos[0]
    assert len(_firmas_de_la_pagina(pdf)) == 2, "TRIM en users: no encontró la firma del usuario"


# ---------------------------------------------------------------------------
# 4. EL CENTINELA HISTÓRICO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("centinela", [" ---- ", "----", "", "   "])
def test_el_centinela_historico_no_se_imprime(app, avisos, bd_copia, monkeypatch, centinela):
    _cambiar(bd_copia, "UPDATE controles SET user_id_f2 = ? WHERE id = 47", centinela)
    pdf, textos = _generar_ok(app, avisos, bd_copia, monkeypatch, 47, "Halcyon", "22/09/2026")
    for texto in textos:
        assert "----" not in texto
        assert "Físico Médico 2" not in texto
    assert len(_firmas_de_la_pagina(pdf)) == 1


# ---------------------------------------------------------------------------
# 5. LO QUE EL DATO DICE, TAL CUAL
# ---------------------------------------------------------------------------

def test_un_nombre_sin_cuenta_se_imprime_y_sale_sin_firma(app, avisos, bd_copia, monkeypatch):
    _cambiar(bd_copia, "UPDATE controles SET user_id_f2 = ? WHERE id = 47", "Persona Sin Cuenta")
    pdf, textos = _generar_ok(app, avisos, bd_copia, monkeypatch, 47, "Halcyon", "22/09/2026")
    assert "Físico Médico 2: Persona Sin Cuenta" in textos[0]
    assert len(_firmas_de_la_pagina(pdf)) == 1          # solo la del Físico 1


def test_la_misma_persona_como_fisico_1_y_2_sale_con_las_dos_firmas(app, avisos, bd_copia, monkeypatch):
    """Sesión 25 (real): Luz Adriana Maya en los dos puestos. El informe muestra el dato tal cual."""
    pdf, textos = _generar_ok(app, avisos, bd_copia, monkeypatch, 25, "Tomógrafo", "04/2026")
    assert "Físico Médico: Luz Adriana Maya" in textos[0]
    assert "Físico Médico 2: Luz Adriana Maya" in textos[0]
    assert len(_firmas_de_la_pagina(pdf)) == 2
