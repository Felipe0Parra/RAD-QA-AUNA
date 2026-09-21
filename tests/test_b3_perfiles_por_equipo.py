"""B.3 (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md): perfiles por
equipo -- qué prueba aplica y con qué umbral.

Censo obligatorio (regla del 08-09, "clasificar cada campo"): las 3
equipos x 8 pruebas de §0.9 deben tener regla y fuente -- si una celda
queda sin definir, esto falla ANTES de que una prueba nueva pueda nacer
sin criterio.
"""
import pytest

from analisisImagenes.catphan.perfiles import PERFILES, PRUEBAS, evaluar


def test_b3_matriz_completa():
    """Rojo antes que verde: este test debía fallar mientras la matriz no
    existía (perfiles.py no existía). Ahora exige que cada equipo tenga
    las 8 pruebas, cada una con `aplica` y una `fuente` no vacía (o un
    `motivo_no_aplica` si `aplica == 'no'`)."""
    faltantes = []
    for nombre_equipo, perfil in PERFILES.items():
        for prueba in PRUEBAS:
            regla = perfil.reglas.get(prueba)
            if regla is None:
                faltantes.append(f"{nombre_equipo}/{prueba}: sin regla")
                continue
            if regla.aplica not in ("si", "no", "informativo"):
                faltantes.append(f"{nombre_equipo}/{prueba}: aplica inválido {regla.aplica!r}")
            if regla.aplica == "no":
                if not regla.motivo_no_aplica:
                    faltantes.append(f"{nombre_equipo}/{prueba}: 'no aplica' sin motivo")
            elif not regla.fuente:
                faltantes.append(f"{nombre_equipo}/{prueba}: sin fuente")
    assert not faltantes, "Celdas sin clasificar:\n" + "\n".join(faltantes)


def test_b3_las_3_claves_de_equipo_son_las_que_usa_la_app():
    """`tac_mensual.py:428-447` usa exactamente estas 3 cadenas -- un
    perfil con otra grafía nunca se encontraría al identificar el equipo."""
    assert set(PERFILES) == {"Tomógrafo", "Clinac ix", "Halcyon"}


# --- Los 8 casos del plan (§4, B.3, PROTOCOLO DE VERIFICACIÓN) ---------


def test_espesor_no_aplica_en_ix_y_halcyon():
    for nombre in ("Clinac ix", "Halcyon"):
        regla = PERFILES[nombre].reglas["espesor"]
        v = evaluar(regla, valor=2.0)
        assert v.estado == "No aplica"
        assert v.referencia is None
        assert "DA-78" in v.fuente or "acelerador" in v.fuente.lower()


def test_espesor_tomografo_1_92_nominal_2_cumple():
    regla = PERFILES["Tomógrafo"].reglas["espesor"]
    v = evaluar(regla, valor=1.92, referencia=2.0)
    assert v.estado == "Cumple"


def test_espesor_tomografo_3_2_nominal_2_no_cumple():
    regla = PERFILES["Tomógrafo"].reglas["espesor"]
    v = evaluar(regla, valor=3.2, referencia=2.0)
    assert v.estado == "No cumple"


def test_geometria_halcyon_50_041_cumple():
    regla = PERFILES["Halcyon"].reglas["geometria"]
    v = evaluar(regla, valor=50.041)
    assert v.estado == "Cumple"
    assert v.referencia == 50.0
    assert v.tolerancia == 0.5


def test_geometria_halcyon_50_6_no_cumple():
    regla = PERFILES["Halcyon"].reglas["geometria"]
    v = evaluar(regla, valor=50.6)
    assert v.estado == "No cumple"


def test_hu_ix_sin_linea_base_da_sin_linea_base():
    regla = PERFILES["Clinac ix"].reglas["numeros_ct"]
    v = evaluar(regla, valor=207.0, metrica="hu_pmp")  # valor real medido, §0.8
    assert v.estado == "Sin línea base"


def test_uniformidad_halcyon_12_hu_cumple():
    regla = PERFILES["Halcyon"].reglas["uniformidad"]
    v = evaluar(regla, valor=12.0)
    assert v.estado == "Cumple"
    assert v.tolerancia == 40.0


def test_uniformidad_tomografo_6_hu_no_cumple():
    regla = PERFILES["Tomógrafo"].reglas["uniformidad"]
    v = evaluar(regla, valor=6.0)
    assert v.estado == "No cumple"
    assert v.tolerancia == 5.0


# --- Casos adicionales: los tipos de tolerancia que el plan no ejemplificó ---


def test_numeros_ct_tolerancia_por_material_tomografo():
    """Tomógrafo: ±20 HU para PMP/LDPE/Poli/Acrílico, ±50 HU para
    Aire/Delrín/Teflón -- misma prueba, dos grupos de umbral."""
    regla = PERFILES["Tomógrafo"].reglas["numeros_ct"]
    v_estrecho = evaluar(regla, valor=121.5, metrica="hu_acrilico", linea_base=100.0)
    assert v_estrecho.tolerancia == 20.0
    v_ancho = evaluar(regla, valor=916.0, metrica="hu_teflon", linea_base=900.0)
    assert v_ancho.tolerancia == 50.0


def test_evaluar_sin_metrica_en_regla_de_tolerancia_por_dict_exige_metrica():
    regla = PERFILES["Halcyon"].reglas["numeros_ct"]
    with pytest.raises(ValueError):
        evaluar(regla, valor=100.0)  # falta `metrica`


def test_resolucion_espacial_ix_umbral_minimo():
    regla = PERFILES["Clinac ix"].reglas["resolucion_espacial"]
    assert evaluar(regla, valor=6.5).estado == "Cumple"
    assert evaluar(regla, valor=5.0).estado == "No cumple"


def test_linealidad_informativo_en_aceleradores():
    for nombre in ("Clinac ix", "Halcyon"):
        regla = PERFILES[nombre].reglas["linealidad"]
        assert evaluar(regla, valor=0.5).estado == "Informativo"
