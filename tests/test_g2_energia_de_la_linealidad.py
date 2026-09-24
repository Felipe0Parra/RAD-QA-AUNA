"""G.2 (PLAN_HANDOFF_IMAGENES_22-09.md §7bis): la energía de la linealidad sale del protocolo del equipo, y la
tabla de μ sale de UNA fuente y de UNA fórmula.

CAUSA. **[código + medido]** `tac_mensual.py` ofrecía un selector con UNA sola opción, `"0.12 MeV"`, para los tres
equipos: la curva del Halcyon (125 kV) y la del iX (100 kV) se ajustaban contra la tabla de 120 kV. La tabla
(`poder_frenado_materiales.json`) tenía una sola energía, siete filas tecleadas a mano y tres donde
μ ≠ (μ/ρ)·ρ: aire (0.145 × 0.0013 = 0.00019, decía 0.00089), LDPE (0.164 × 0.92 = 0.151, decía 0.136: el valor del
PMP copiado) y Delrin (0.154 × 1.42 = 0.219, decía 0.213). Y la energía nunca se guardaba con la prueba.

Lo que este archivo garantiza:

  1. SIN SELECTOR -- ninguna de las cinco pantallas de imágenes tiene el combo de energía; cada una muestra la de su
     protocolo y llena la tabla de μ sola, con los valores de esa energía.
  2. LA ENERGÍA VIAJA -- el ajuste de linealidad de cada equipo usa su energía, y el resultado la lleva (tres equipos,
     tres energías, tres pendientes distintas con los mismos HU).
  3. UN EQUIPO SIN PROTOCOLO NO RECIBE UNA ENERGÍA INVENTADA.
  4. LA TABLA -- coherente (μ = (μ/ρ)·ρ y μ/ρ decrece con la energía), reproduce la tabla vieja a 0.12 MeV dentro de
     ±3 % en μ/ρ, coincide con NIST (compuestos) y el JSON es EXACTAMENTE lo que produce el script versionado.
  5. SE GUARDA -- `linealidad_ct.energia_mev`: migración aditiva e idempotente, ida y vuelta por la BD, y el PDF la
     imprime (o dice que no se registró en un control anterior).
"""
import ast
import json
import pathlib
import re
import shutil
import sqlite3
import sys

import numpy as np
import pytest

from PyQt5.QtWidgets import QComboBox, QTableWidget

import data.ManejoDatos.conection as conection_mod
from _formularios_imagenes import FORMULARIOS, app, bd_temporal, iniciar, sin_dialogos  # noqa: F401  (fixtures)
from _informe_imagenes import avisos, bd_copia, generar, paginas  # noqa: F401  (fixtures)
from analisisImagenes.catphan import atenuacion
from analisisImagenes.catphan.atenuacion import (
    clave_energia, energia_de_linealidad_mev, materiales_a_energia)
from analisisImagenes.catphan.protocolos import PROTOCOLOS
from data.ManejoDatos.catphan_TAC.catphan_db import (
    guardar_prueba_completa_catphan, mapear_linealidad_ct, reconstruir_resultados_desde_bd,
    tabla_resultados_linealidad_ct)

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
import generar_tabla_mu as script_mu  # noqa: E402

MATERIALES = ["Aire", "PMP", "LDPE", "Poliestireno", "Acrilico", "Delrin", "Teflon"]
NOMBRE_EN_TABLA = {"Acrilico": "Acrílico", "Teflon": "Teflón"}     # la pantalla los escribe con tilde

# La tabla ANTERIOR (energia_0.12MeV), tal como estaba tecleada. Es la referencia de (c).
TABLA_ANTERIOR = {
    "Aire":         {"poder_frenado": 0.145, "densidad": 0.0013, "coeficiente_atenuacion": 0.00089},
    "PMP":          {"poder_frenado": 0.164, "densidad": 0.83,   "coeficiente_atenuacion": 0.136},
    "LDPE":         {"poder_frenado": 0.164, "densidad": 0.92,   "coeficiente_atenuacion": 0.136},
    "Poliestireno": {"poder_frenado": 0.155, "densidad": 1.03,   "coeficiente_atenuacion": 0.160},
    "Acrilico":     {"poder_frenado": 0.156, "densidad": 1.18,   "coeficiente_atenuacion": 0.184},
    "Delrin":       {"poder_frenado": 0.154, "densidad": 1.42,   "coeficiente_atenuacion": 0.213},
    "Teflon":       {"poder_frenado": 0.141, "densidad": 2.16,   "coeficiente_atenuacion": 0.305},
}

# HU reales del tomógrafo (pylinac sobre `QA tomografo Catphan`, orden de la tabla de la pantalla)
HU_TOMOGRAFO = [-1000.0, -185.0, -95.0, -37.0, 121.5, 322.0, 916.0]


def _celda(tabla, fila, columna):
    item = tabla.item(fila, columna)
    return item.text() if item else None


def _formulario(clave):
    """La pantalla YA iniciada: la tabla de linealidad existe desde que se construye el formulario de las
    siete pruebas, no antes."""
    return iniciar(FORMULARIOS[clave][0]()), FORMULARIOS[clave][1]


# ---------------------------------------------------------------------------
# 1. SIN SELECTOR
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clave", sorted(FORMULARIOS))
def test_ninguna_pantalla_de_imagenes_tiene_selector_de_energia(app, bd_temporal, clave):
    obj, _equipo = _formulario(clave)
    assert not hasattr(obj, "energia_select")
    for combo in obj.findChildren(QComboBox):
        opciones = [combo.itemText(i) for i in range(combo.count())]
        assert not any("Energía" in o or "MeV" in o for o in opciones), opciones


@pytest.mark.parametrize("clave", sorted(FORMULARIOS))
def test_cada_pantalla_muestra_la_energia_de_su_protocolo_y_llena_la_tabla_sola(app, bd_temporal, clave):
    obj, equipo = _formulario(clave)
    energia = PROTOCOLOS[equipo].energia_linealidad_mev
    assert obj.energia_linealidad_mev == energia

    texto = obj.energia_linealidad_texto.text()
    assert f"{energia:g}" in texto and equipo in texto

    tabla = obj.tabla_linealidad_ct
    assert isinstance(tabla, QTableWidget)
    esperados = materiales_a_energia(energia)
    for fila, material in enumerate(MATERIALES):
        assert _celda(tabla, fila, 0) == NOMBRE_EN_TABLA.get(material, material)
        assert _celda(tabla, fila, 1) == f"{energia:g}"
        assert _celda(tabla, fila, 2) == f"{esperados[material]['mu_rho']:.4f}"
        assert _celda(tabla, fila, 3) == f"{esperados[material]['densidad']:.4f}"
        assert _celda(tabla, fila, 4) == f"{esperados[material]['mu']:.4f}"


def test_las_tres_energias_son_distintas_y_son_las_del_catalogo(app, bd_temporal):
    energias = {FORMULARIOS[c][1]: _formulario(c)[0].energia_linealidad_mev for c in FORMULARIOS}
    assert energias == {"Tomógrafo": 0.120, "Clinac ix": 0.100, "Halcyon": 0.125}


def test_construir_la_pantalla_no_cambia_de_pestana_ni_intenta_el_ajuste(app, bd_temporal):
    """La tabla se llena al construir, pero el ajuste espera a que lleguen los HU: no cambia la pestaña de
    resultados ni deja un análisis a medias."""
    obj, _ = _formulario("tomografo")
    assert obj.graficar.currentText() != "Linealidad del CT"
    assert getattr(obj, "resultados_linealidad_ct", None) is None


# ---------------------------------------------------------------------------
# 2. LA ENERGÍA VIAJA CON EL AJUSTE
# ---------------------------------------------------------------------------

def _poner_hu(obj, hu):
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    from PyQt5.QtWidgets import QTableWidgetItem
    from PyQt5.QtWidgets import QLabel
    if not hasattr(obj, "canvas_resultados"):
        obj.canvas_resultados = FigureCanvasQTAgg(Figure())     # lo crea la pantalla al cargar una carpeta
    if getattr(obj, "resultados_texto", None) is None:
        obj.resultados_texto = QLabel()                        # ídem: el panel de resultados
    for fila, valor in enumerate(hu):
        obj.tabla_linealidad_ct.setItem(fila, 5, QTableWidgetItem(f"{valor:.1f}"))


def test_el_ajuste_usa_la_energia_de_cada_equipo_y_el_resultado_la_lleva(app, bd_temporal):
    """Los MISMOS HU en los tres equipos: si el ajuste usara una energía única darían la misma pendiente."""
    pendientes = {}
    for clave in ("tomografo", "ix_mensual", "hc_mensual"):
        obj, equipo = _formulario(clave)
        _poner_hu(obj, HU_TOMOGRAFO)
        resultado = obj.try_actualizar_linealidad_ct()
        assert resultado is not None, f"{equipo}: el ajuste no corrió"
        assert resultado["energia_mev"] == PROTOCOLOS[equipo].energia_linealidad_mev
        assert obj.resultados_linealidad_ct["energia_mev"] == resultado["energia_mev"]
        mu = [float(_celda(obj.tabla_linealidad_ct, f, 4)) for f in range(7)]
        pendiente, _ = np.polyfit(mu, HU_TOMOGRAFO, 1)
        assert resultado["pendiente"] == pytest.approx(pendiente)
        pendientes[equipo] = resultado["pendiente"]
    assert len({round(p, 3) for p in pendientes.values()}) == 3, pendientes


# ---------------------------------------------------------------------------
# 3. UN EQUIPO SIN PROTOCOLO NO RECIBE UNA ENERGÍA INVENTADA
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("equipo", ["Clinac 600", "esHC", "", None, "Equipo Inventado"])
def test_un_equipo_sin_protocolo_no_tiene_energia(equipo):
    assert energia_de_linealidad_mev(equipo) is None


def test_una_pantalla_sin_protocolo_deja_la_tabla_vacia_y_no_ajusta(app, bd_temporal):
    obj, _ = _formulario("tomografo")
    obj.equipo_f = "Clinac 600"
    obj._aplicar_energia_de_linealidad()
    assert obj.energia_linealidad_mev is None
    assert "Sin energía definida" in obj._texto_energia_de_linealidad()
    for fila in range(7):
        assert [_celda(obj.tabla_linealidad_ct, fila, c) for c in range(1, 5)] == ["", "", "", ""]
    _poner_hu(obj, HU_TOMOGRAFO)
    assert obj.try_actualizar_linealidad_ct() is None


def test_pedir_una_energia_que_la_tabla_no_trae_falla_y_no_aproxima():
    with pytest.raises(KeyError):
        materiales_a_energia(0.140)


# ---------------------------------------------------------------------------
# 4. LA TABLA DE μ
# ---------------------------------------------------------------------------

def _tabla_json():
    return json.loads((RAIZ / "resources" / "archivos_json" / "poder_frenado_materiales.json")
                      .read_text(encoding="utf-8"))


def _energias_del_json():
    return sorted(float(k[len("energia_"):-len("MeV")]) for k in _tabla_json() if k.startswith("energia_"))


def test_la_tabla_trae_exactamente_las_energias_del_catalogo():
    assert _energias_del_json() == sorted({p.energia_linealidad_mev for p in PROTOCOLOS.values()})


@pytest.mark.parametrize("energia", [0.1, 0.12, 0.125])
def test_mu_es_mu_sobre_rho_por_densidad_en_cada_fila(energia):
    """(b): la incoherencia de la tabla vieja (aire, LDPE, Delrin) no puede volver."""
    filas = materiales_a_energia(energia)
    assert list(filas) == MATERIALES
    for material, f in filas.items():
        assert f["mu"] == pytest.approx(f["mu_rho"] * f["densidad"], abs=6e-6), material
        assert round(f["mu"], 3) == round(f["mu_rho"] * f["densidad"], 3), material


def test_mu_sobre_rho_decrece_con_la_energia_en_los_siete_materiales():
    a, b, c = (materiales_a_energia(e) for e in (0.100, 0.120, 0.125))
    for m in MATERIALES:
        assert a[m]["mu_rho"] > b[m]["mu_rho"] > c[m]["mu_rho"], m


def test_pmp_y_ldpe_comparten_mu_sobre_rho_y_difieren_por_la_densidad():
    """La tabla vieja copió el μ del PMP en el LDPE: misma composición, distinta densidad."""
    for e in (0.100, 0.120, 0.125):
        t = materiales_a_energia(e)
        assert t["PMP"]["mu_rho"] == t["LDPE"]["mu_rho"]
        assert t["LDPE"]["mu"] / t["PMP"]["mu"] == pytest.approx(0.92 / 0.83, rel=1e-3)
        assert t["LDPE"]["mu"] != t["PMP"]["mu"]


def test_la_tabla_vieja_tenia_tres_filas_incoherentes_y_la_nueva_ninguna():
    """El defecto que G.2 corrige, fijado como hecho: en la vieja μ ≠ (μ/ρ)·ρ en aire, LDPE y Delrin."""
    incoherentes = [m for m, f in TABLA_ANTERIOR.items()
                    if abs(f["coeficiente_atenuacion"] / (f["poder_frenado"] * f["densidad"]) - 1) > 0.02]
    assert incoherentes == ["Aire", "LDPE", "Delrin"]
    nuevas = materiales_a_energia(0.120)
    assert all(abs(f["mu"] - f["mu_rho"] * f["densidad"]) < 6e-6 for f in nuevas.values())


def test_reproduce_la_tabla_anterior_a_012_mev_dentro_de_3_por_ciento():
    """(c): la tabla vieja SÍ salió de NIST interpolado a 0.12 MeV; el método nuevo la reproduce. Si no lo
    hiciera, la vieja vendría de otra fuente u otra convención y habría que saberlo antes de mover la curva."""
    nueva = materiales_a_energia(0.120)
    for m, vieja in TABLA_ANTERIOR.items():
        rel = abs(nueva[m]["mu_rho"] - vieja["poder_frenado"]) / vieja["poder_frenado"]
        assert rel < 0.03, (m, rel)
        assert nueva[m]["densidad"] == vieja["densidad"], "las densidades nominales no cambian"


def test_las_filas_coherentes_de_la_tabla_vieja_apenas_se_mueven_en_mu():
    nueva = materiales_a_energia(0.120)
    for m in ("PMP", "Poliestireno", "Acrilico", "Teflon"):
        vieja = TABLA_ANTERIOR[m]["coeficiente_atenuacion"]
        assert abs(nueva[m]["mu"] - vieja) / vieja < 0.01, m


def test_la_regla_de_mezclas_coincide_con_las_tablas_de_compuestos_de_nist():
    assert script_mu.verificar_contra_compuestos(0.005) == []


def test_no_se_extrapola_fuera_del_rango_tabulado():
    with pytest.raises(ValueError, match="fuera del rango tabulado"):
        script_mu.mu_rho_elemento("C", 250)
    with pytest.raises(ValueError, match="fuera del rango tabulado"):
        script_mu.mu_rho_elemento("C", 60)


def test_el_json_es_exactamente_lo_que_produce_el_script():
    """Nadie edita el JSON a mano: si se toca un número, o el catálogo cambia una energía, esto falla."""
    assert _tabla_json() == script_mu.generar()
    assert script_mu.main(["--verificar"]) == 0


def test_el_json_declara_su_fuente():
    fuente = _tabla_json()["_fuente"]
    assert "NIST" in fuente["referencia"] and "Hubbell" in fuente["referencia"]
    assert "generar_tabla_mu.py" in fuente["generado_por"]


def test_la_clave_de_energia_se_define_en_un_solo_sitio():
    assert clave_energia(0.12) == "energia_0.12MeV" and clave_energia(0.1) == "energia_0.1MeV"
    assert script_mu.clave_energia is atenuacion.clave_energia


# ---------------------------------------------------------------------------
# 5. UNA SOLA FUENTE DE LA ENERGÍA EN EL CÓDIGO
# ---------------------------------------------------------------------------

def _cadenas_de_produccion():
    for ruta in RAIZ.rglob("*.py"):
        rel = ruta.relative_to(RAIZ).as_posix()
        if rel.startswith(("tests/", ".venv/", "build/", "dist/")) or "/.venv/" in rel:
            continue
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                yield rel, nodo.lineno, nodo.value


@pytest.mark.parametrize("frase", ["Seleccionar Energía", "0.12 MeV"])
def test_no_quedan_energias_tecleadas_ni_el_selector_en_produccion(frase):
    halladas = [(r, n) for r, n, t in _cadenas_de_produccion() if t == frase]
    assert halladas == [], halladas


def test_el_formulario_toma_la_energia_del_catalogo():
    fuente = (RAIZ / "ui/paginasControles/PruebasMensuales/tac_mensual.py").read_text(encoding="utf-8")
    assert "energia_de_linealidad_mev(" in fuente and "materiales_a_energia(" in fuente
    assert "energia_select" not in fuente and "on_energia_linealidad_cambio" not in fuente


# ---------------------------------------------------------------------------
# 6. SE GUARDA: migración, ida y vuelta, PDF
# ---------------------------------------------------------------------------

def _columnas(ruta, tabla):
    con = sqlite3.connect(ruta)
    try:
        return [r[1] for r in con.execute(f"PRAGMA table_info({tabla})")]
    finally:
        con.close()


def test_una_bd_nueva_trae_la_columna(bd_temporal):
    ruta = conection_mod.ruta_base_datos()
    assert "energia_mev" in _columnas(ruta, "linealidad_ct")


def test_la_migracion_es_aditiva_e_idempotente_sobre_una_copia_de_produccion(monkeypatch, tmp_path):
    from _bd_referencia import BD_REBUILD_21_09
    if not BD_REBUILD_21_09.exists():
        pytest.skip("falta la BD de referencia del 21-09")
    copia = tmp_path / "copia.db"
    shutil.copy2(BD_REBUILD_21_09, copia)
    assert "energia_mev" not in _columnas(str(copia), "linealidad_ct")
    antes = sqlite3.connect(copia).execute("SELECT COUNT(*) FROM linealidad_ct").fetchone()[0]

    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: str(copia))
    for _ in range(2):                                   # la segunda corrida no debe cambiar nada
        conection_mod.Conexion._instance = None
        conection_mod.Conexion().con.close()
        conection_mod.Conexion._instance = None
        cols = _columnas(str(copia), "linealidad_ct")
        assert cols.count("energia_mev") == 1
    con = sqlite3.connect(copia)
    assert con.execute("SELECT COUNT(*) FROM linealidad_ct").fetchone()[0] == antes
    assert con.execute("SELECT COUNT(*) FROM linealidad_ct WHERE energia_mev IS NOT NULL").fetchone()[0] == 0
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.close()


def test_el_mapeo_lleva_la_energia():
    m = mapear_linealidad_ct({"pendiente": 6000.0, "intercepto": -1000.0, "r_squared": 0.999,
                              "referencia": 1.0, "escala_contraste": 0.0002, "energia_mev": 0.125})
    assert m["energia_mev"] == 0.125
    assert mapear_linealidad_ct({"pendiente": 1.0, "r_squared": 0.9})["energia_mev"] is None


LINEALIDAD = {"pendiente": 6146.9, "intercepto": -996.0, "r_squared": 0.99903, "referencia": 0.5,
              "escala_contraste": 1 / 6146.9}


def _crear_control():
    con = sqlite3.connect(conection_mod.ruta_base_datos())
    con.execute("INSERT INTO controles (equipo, control, fecha) VALUES ('Halcyon', 'Mensual', '09/2026')")
    con.commit()
    ref = con.execute("SELECT id FROM controles ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.close()
    return ref


def _guardar_linealidad(**extra):
    sesion = _crear_control()
    guardar_prueba_completa_catphan(
        user_id="Fisico Real", fecha="2026-09-24", equipo="Halcyon", kv=125, ma=80, espesor_corte=2.0,
        resultados_por_categoria={"linealidad_ct": dict(LINEALIDAD, **extra)}, id_sesion=sesion)
    return sesion


def test_la_energia_hace_ida_y_vuelta_por_la_bd(app, bd_temporal):
    sesion = _guardar_linealidad(energia_mev=0.125)
    r = reconstruir_resultados_desde_bd(sesion, categorias=["linealidad_ct"])["linealidad_ct"]
    assert r["energia_mev"] == 0.125
    assert r["pendiente"] == pytest.approx(6146.9)
    assert "Energía [MeV]: 0.125" in tabla_resultados_linealidad_ct(r)


def test_una_linealidad_sin_energia_se_reconstruye_con_none_y_lo_dice(app, bd_temporal):
    sesion = _guardar_linealidad()
    r = reconstruir_resultados_desde_bd(sesion, categorias=["linealidad_ct"])["linealidad_ct"]
    assert r["energia_mev"] is None
    assert "Energía [MeV]: no registrada" in tabla_resultados_linealidad_ct(r)


SESION_42 = (42, "Tomógrafo", "07/2026")      # tiene linealidad (id_tipo 6)


def _texto_pdf(paginas_):
    return re.sub(r"\s+", " ", "\n".join(paginas_))


def test_el_pdf_de_un_control_anterior_dice_que_la_energia_no_se_registro(app, avisos, bd_copia, monkeypatch):
    ok, visor = generar(bd_copia, monkeypatch, *SESION_42)
    assert ok is True and avisos == []
    assert "Energía [MeV] no registrada (control anterior al 24-09-2026)" in _texto_pdf(paginas(visor["pdf"]))


def test_el_pdf_imprime_la_energia_guardada(app, avisos, bd_copia, monkeypatch):
    con = sqlite3.connect(bd_copia)
    n = con.execute("UPDATE linealidad_ct SET energia_mev = 0.12 WHERE id_prueba IN "
                    "(SELECT id_prueba FROM pruebas WHERE id_sesion = 42 AND id_tipo = 6)").rowcount
    con.commit()
    con.close()
    assert n == 1
    ok, visor = generar(bd_copia, monkeypatch, *SESION_42)
    assert ok is True and avisos == []
    plano = _texto_pdf(paginas(visor["pdf"]))
    assert re.search(r"Energía \[MeV\] 0\.12 Pendiente", plano), "la fila de la energía debe ir en la tabla de linealidad"
    assert "no registrada" not in plano
