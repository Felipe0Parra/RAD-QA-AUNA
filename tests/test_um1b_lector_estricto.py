"""UM.1b (PLAN_CALCULADORA_UM_05-11.md): el lector de Eclipse (`services/um_lector_eclipse.py`) rechaza, con su motivo, lo que no entiende.

La auditoria independiente de UM.1 (06-11-2026) reprodujo que el lector comiteado (`1ef6e33`) aceptaba numeros mal escritos como otros numeros (`float()` admite
«1.1_7», «0.8e0» y un espacio Unicode: una celda 1.107 se leia 1.17, +5.7 % en las UM), se saltaba lineas que no entendia, daba motivos sin sus unidades o falsos
y no guardaba la `y` de cada punto. Aqui se fija la correccion por CLASES (una funcion por clase, no un parche por caso):
  1. un solo validador para TODO numero del archivo (`_numero`, y la prueba por AST de que no hay otra conversion de texto a numero);
  2. lo que empieza por «%», lo que hay antes de la primera curva, un `$ENOF` entre curvas y una linea de parametros sin la forma nombre[unidad]:valor se rechazan;
  4. los motivos dicen sus unidades entre corchetes; 5. un archivo guardado como UTF-16 lo dice; 6. una curva con puntos fuera de y = 0 se rechaza;
  3. y, al final, los casos que la lente de pruebas de la auditoria escribio para las mutaciones que sobrevivian a los 242 casos de UM.1 (P-01 a P-11).
Los numeros esperados salen de los archivos (leidos a mano) y del plan, nunca del lector. Ningun numero de los 22 archivos reales cambia: medido sobre los 522
archivos reales (los 22 del 600C y los 500 del paquete de Varian), ninguno escribe un numero fuera de la forma de `_numero` ni una curva con y distinta de 0 en
lo que lee el motor (`scripts/um1b_medir_datos_reales.py` del anexo). Sin Qt y sin base de datos.
"""
import ast
import importlib
import math
import os
import re

import numpy as np
import pytest

AQUI = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(AQUI, "datos_um", "600C")
MODULO = os.path.join(AQUI, "..", "services", "um_lector_eclipse.py")
PDD = "CLINAC 600C_Open Field - 00_Measured Depth Doses.txt"
OF = "CLINAC 600C_Open Field - 00_Output Factors.txt"
PERFILES = "CLINAC 600C_Open Field - 00_Processed Measured Profiles.txt"
PUNTO = "<+000.0 +000.0 +000.0 +045.300>"      # el primer punto del PDD de 2.5 x 2.5 (aparece una vez)
EM, NBSP = "\u2003", "\u00a0"                   # un espacio largo y un espacio sin separacion de Unicode: no son blancos para el lector (solo lo son el espacio y el tabulador)
BLANCOS = [" ", "\t", EM, NBSP]
PUNTO_PERFIL = "<+002.5 +000.0 +013.5 +099.521>"   # un punto real de los perfiles abiertos cuya ultima cifra no es 0 (aparece una vez)


@pytest.fixture(scope="module")
def lector():
    return importlib.import_module("services.um_lector_eclipse")


def crudo(nombre):
    with open(os.path.join(DATOS, nombre), "rb") as f:
        return f.read()


def texto(lector, nombre):
    return lector.decodificar(crudo(nombre))


def una_vez(t, viejo, nuevo):
    assert t.count(viejo) == 1, viejo
    return t.replace(viejo, nuevo)


# ---------- Clase 1 (S1): un numero mal escrito no entra como otro numero ----------
@pytest.mark.parametrize("bueno, valor", [("+073.091", 73.091), ("-000.0", 0.0), ("100", 100.0), ("0.662300", 0.6623), ("+0", 0.0), ("007", 7.0)])
def test_numero_lee_lo_que_escribe_eclipse(lector, bueno, valor):
    assert lector._numero(bueno) == valor


@pytest.mark.parametrize("malo", ["1.1_7", "0.8e0", "1e2", "+073.e91", "1_00.0", "inf", "nan", "-inf", "0x10", "1.0 ", " 1.0", " 1.0", "１.0",
                                  "١.5", "1,0", ".5", "1000.", "+", "", "1" * 400,
                                  "1.0 ", "++5", "+-5", "1.5.5", "1.5e"])      # (implementador) los cinco ultimos: un blanco ASCII al final, dos signos, dos puntos y una «e» suelta
def test_numero_no_lee_lo_que_eclipse_no_escribe(lector, malo):
    """float() aceptaba los nueve primeros (y el ultimo da inf): un caracter danado dentro de un numero entraba como otro numero. (Implementador) «1.0 » (un blanco ASCII al final) SI lo acepta
    `float()` y no es un numero de Eclipse; «++5», «+-5», «1.5.5» y «1.5e» los rechaza `float()` con un ValueError y no con None: una expresion que los dejara pasar haria que el lector se
    cayera con una excepcion cruda en vez de rechazar el archivo con su motivo."""
    assert lector._numero(malo) is None


@pytest.mark.parametrize("malo", ["+04_5.300", "+045.3e0", "+045.e30", "+４５.300", "+045,300", "+0_3.091"])
def test_un_punto_con_un_numero_mal_escrito_se_rechaza(lector, malo):
    t = una_vez(texto(lector, PDD), PUNTO, PUNTO.replace("+045.300", malo))
    with pytest.raises(lector.ArchivoNoReconocido, match="hay un punto que no tiene cuatro números válidos"):
        lector.leer_curvas(t)


@pytest.mark.parametrize("viejo, malo, motivo", [
    ("%FLSZ 100*100\n", "%FLSZ 100*1_0\n", "El campo de una curva no se puede leer: «1_0»"),
    ("%FLSZ 100*100\n", "%FLSZ 100*1e2\n", "El campo de una curva no se puede leer: «1e2»"),
    ("%FLSZ 100*100\n", "%FLSZ 100*10 \n", "El campo de una curva no se puede leer: «10 »"),
    ("%SSD 1000\n", "%SSD 1_000\n", "La SSD de una curva no se puede leer: «1_000»"),
    ("%SSD 1000\n", "%SSD 1e3\n", "La SSD de una curva no se puede leer: «1e3»"),
    ("%SSD 1000\n", "%SSD １000\n", "La SSD de una curva no se puede leer: «１000»"),
])
def test_una_cabecera_de_curva_con_un_numero_mal_escrito_se_rechaza(lector, viejo, malo, motivo):
    """«%FLSZ 100*10» con la ultima cifra cambiada por un espacio Unicode daba un campo de 10 x 1 cm: str.strip() lo quitaba y float() leia 10."""
    t = texto(lector, PDD).replace(viejo, malo, 1)
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(motivo)):
        lector.leer_curvas(t)


@pytest.mark.parametrize("viejo, nuevo", [(", 1.107\n", ", 1.1_7\n"), (", 1.107\n", ", 1.107e0\n"), (", 1.107\n", ", 1.10 \n"), ("\n2.5, 0.870", "\n2.5e0, 0.870"),
                                          ("\n20, 0.928", "\n2_0, 0.928")])
def test_una_tabla_con_un_numero_mal_escrito_se_rechaza(lector, viejo, nuevo):
    """La celda Y 40, X 40 (1.107) escrita «1.1_7» se leia 1.17 y las UM de 40 x 40 a 10 cm bajaban de 259.93 a 245.93 (-5.38 %) sin aviso (auditoria, S1)."""
    with pytest.raises(lector.ArchivoNoReconocido, match="la tabla de factores tiene una línea que no son números separados por comas"):
        lector.leer_tabla_of(una_vez(texto(lector, OF), viejo, nuevo))


@pytest.mark.parametrize("viejo, nuevo, motivo", [("%DetectorDepth 50\n", "%DetectorDepth 5_0\n", "La profundidad de la tabla no se puede leer: «5_0»"),
                                                  ("%DetectorDepth 50\n", "%DetectorDepth 5e1\n", "La profundidad de la tabla no se puede leer: «5e1»"),
                                                  ("%SourcePhantomDistance 1000\n", "%SourcePhantomDistance 1_000\n", "La SSD de la tabla no se puede leer: «1_000»")])
def test_la_cabecera_de_una_tabla_con_un_numero_mal_escrito_se_rechaza(lector, viejo, nuevo, motivo):
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(motivo)):
        lector.leer_tabla_of(una_vez(texto(lector, OF), viejo, nuevo))


@pytest.mark.parametrize("viejo, nuevo", [("[Gy]:0.662300", "[Gy]:0.6_2300"), ("[Gy]:0.662300", "[Gy]:0.6623e0"), ("[Gy]:0.662300", "[Gy]:0.662300 "),
                                          ("[MU]:100.000000", "[MU]:1_00.000000"), ("[MU]:100.000000", "[MU]:1e2")])
def test_la_dosis_o_las_mu_de_la_cuna_mal_escritas_se_rechazan(lector, viejo, nuevo):
    """«0.6_2300» se leia 0.623 cGy/UM en vez de 0.6623 y las UM con la cuna de 15 grados subian un 6.31 % (auditoria, S1)."""
    with pytest.raises(lector.ArchivoNoReconocido, match="las dos deben ser números mayores que 0"):
        lector.dosis_de_referencia_cuna(una_vez(texto(lector, "name.data"), viejo, nuevo))


@pytest.mark.parametrize("malo", ["1_5.0", "1.5e1", "15.0 "])
def test_el_angulo_de_la_cuna_mal_escrito_se_rechaza(lector, malo):
    with pytest.raises(lector.ArchivoNoReconocido, match="el ángulo de la cuña no se puede leer"):
        lector.angulo_en_parametros(una_vez(texto(lector, "name.data"), "Wedge angle[deg]:15.0", f"Wedge angle[deg]:{malo}"))


@pytest.mark.parametrize("malo", ["inf", "nan", "1e9", "1_0"])
def test_un_lado_o_una_celda_que_no_es_un_numero_se_rechaza(lector, malo):
    """Antes «inf» y «1e9» llegaban como numeros a la barrera de los lados (y «nan» a la de las celdas): ahora no son numeros del archivo."""
    t = texto(lector, OF)
    for viejo, nuevo in ((", 40\n", f", {malo}\n"), ("\n40, ", f"\n{malo}, "), (", 1.107\n", f", {malo}\n")):
        with pytest.raises(lector.ArchivoNoReconocido, match="no son números separados por comas"):
            lector.leer_tabla_of(una_vez(t, viejo, nuevo))


def test_un_numero_con_punto_final_no_es_un_numero_de_eclipse(lector):
    """Ningun numero de los 522 archivos reales termina en punto. Dos caracteres cambiados de sitio en «<+100.0 ...>» dan «<+1000. ...>»: se leia x = 100 cm
    en vez de 10 (el oraculo de la auditoria lo marcaba invalido; con el lector nuevo era la UNICA variante de las 5610 aceptada con otro valor)."""
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape("La SSD de una curva no se puede leer: «1000.»")):
        lector.leer_curvas(texto(lector, PDD).replace("%SSD 1000\n", "%SSD 1000.\n"))
    with pytest.raises(lector.ArchivoNoReconocido, match="hay un punto que no tiene cuatro números válidos"):
        lector.leer_curvas(una_vez(texto(lector, PDD), PUNTO, "<+0000. +000.0 +000.0 +045.300>"))


def test_todo_numero_del_archivo_pasa_por_un_solo_validador():
    """Por AST: float() e int() solo aparecen en `_numero` (los numeros del archivo), en `clave_energia` y `angulo_cuna` (un nombre que su expresion ya valida con
    digitos ASCII), en `_anunciadas` (los digitos de $NUMS) y en `valores_fuera_de_tendencia` (numpy a float). Cualquier otra conversion de texto a numero es la
    clase S1 otra vez."""
    with open(MODULO, encoding="utf-8") as f:
        arbol = ast.parse(f.read())
    sitios = set()
    for funcion in (n for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef)):
        for llamada in ast.walk(funcion):
            if isinstance(llamada, ast.Call) and isinstance(llamada.func, ast.Name) and llamada.func.id in ("float", "int"):
                sitios.add((funcion.name, llamada.func.id))
    assert sitios == {("_numero", "float"), ("clave_energia", "float"), ("angulo_cuna", "int"), ("_anunciadas", "int"), ("valores_fuera_de_tendencia", "float")}


# ---------- Clase 2 (S2, REAL-2, P-12, P-13): lo que no se entiende no se salta ----------
@pytest.mark.parametrize("fila", ["20", "4", "15", "25", "40"])
def test_una_fila_de_la_tabla_con_porcentaje_delante_no_se_salta(lector, fila):
    """La fila Y 20 escrita «%20, 0.928, ...» desaparecia: la tabla quedaba con 11 filas y el motor interpolaba (+0.19 % a 20 x 20; +0.67 % a 25 x 25). (Implementador) La
    ultima fila, la de 40, tambien cuenta: una lista de lineas «%» que dejara fuera la ultima linea del archivo la perderia sin avisar."""
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(f"la cabecera de la tabla de factores tiene una línea que no se entiende: «%{fila}, 0.")):
        lector.leer_tabla_of(una_vez(texto(lector, OF), f"\n{fila}, 0.", f"\n%{fila}, 0."))


def test_una_linea_con_porcentaje_que_no_se_entiende_en_la_primera_linea_de_la_tabla_no_se_salta(lector):
    """(Implementador) La primera linea del archivo cuenta como cualquier otra: la que empieza por «%» y no es «%CLAVE valor» se rechaza aunque nada la preceda."""
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape("la cabecera de la tabla de factores tiene una línea que no se entiende: «%VERSION03»")):
        lector.leer_tabla_of("%VERSION03\n" + texto(lector, OF))


def test_un_dato_de_la_cabecera_de_la_tabla_dicho_dos_veces_con_otro_valor_se_rechaza_tambien_el_primero(lector):
    """(Implementador) La primera clave de la cabecera («%VERSION») dicha otra vez con otro valor se rechaza como cualquier otra (rx24 lo prueba con la ultima)."""
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape("la cabecera de la tabla de factores dice dos veces «VERSION», con «03» y con «04»")):
        lector.leer_tabla_of(una_vez(texto(lector, OF), "%VERSION 03\n", "%VERSION 03\n%VERSION 04\n"))


@pytest.mark.parametrize("malo", ["%SSD1000", "%SS2D 1000", "% SSD 1000", "%.SSD 1000", "%SSD-1000", "%SS_D 1000", "%SSD\u00a01000", "%" + PUNTO])
def test_una_linea_de_curva_con_porcentaje_que_no_es_una_clave_se_rechaza(lector, malo):
    """«%SSD1000» o «%SS2D 1000» dejaban la curva con ssd_cm = None («no dice su SSD») aunque el archivo dice 1000; un punto con «%» delante se perdia."""
    viejo = PUNTO if malo.endswith(">") else "%SSD 1000"
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(f"hay una línea que no se entiende: «{malo[:40]}»")):
        lector.leer_curvas(texto(lector, PDD).replace(viejo, malo, 1))


def test_la_clave_y_su_valor_se_separan_con_espacios_o_tabuladores(lector):
    """«%SSD<TAB>1000» se tomaba como la clave «SSD\\t1000» sin valor (ssd_cm = None) y «%FLSZ<TAB>100*100» como una curva sin campo (REAL-2): la tabla ya
    admitia el tabulador; ahora las dos cabeceras son la misma regla."""
    curvas = lector.leer_curvas(texto(lector, PDD).replace("%SSD 1000\n", "%SSD\t1000\n").replace("%FLSZ 100*100\n", "%FLSZ\t100*100\n"))
    assert {c.ssd_cm for c in curvas} == {100.0} and (10.0, 10.0) in [c.campo_cm for c in curvas]
    assert lector.leer_tabla_of(una_vez(texto(lector, OF), "%DetectorDepth 50", "%DetectorDepth\t 50")).prof_cm == 5.0
    # (ronda 1, R2) el campo ya NO admite blancos junto al «*»: «10 *100» era 1 x 10 cm y «100*10 » 10 x 1 (ver test_r2_r3_un_blanco_en_un_dato_numerico_de_la_cabecera_de_una_curva_no_se_recorta)
    for separador in ("\t", "  ", " \t "):      # (implementador) «$NUMS» sigue la misma regla de la clave: uno o mas blancos, espacios o tabuladores
        assert len(lector.leer_curvas(una_vez(texto(lector, PDD), "$NUMS 012", f"$NUMS{separador}012"))) == 12


def test_un_espacio_al_final_de_un_dato_de_la_tabla_no_cambia_el_dato(lector):
    """«%TYPE OutputFactorTable » (un espacio al final) se rechazaba como «no es una tabla de factores» (observado en UM.1): el valor se recorta como en las curvas."""
    assert lector.leer_tabla_of(una_vez(texto(lector, OF), "%TYPE OutputFactorTable\n", "%TYPE OutputFactorTable \n")).m[0, 0] == 0.870


@pytest.mark.parametrize("malo", ["$NUMS doce", "$NUMS011", "$NUMS -12", "$NUMS 012 basura", "NUMS 012", "$NUMS ０１２", "basura\n$NUMS 012"])
def test_lo_que_hay_antes_de_la_primera_curva_se_entiende_o_se_rechaza(lector, malo):
    """«$NUMS doce» o «$NUMS011» se aceptaban sin contar las curvas (P-12); lo que no era «$NUMS» antes del primer $STOM se descartaba sin mirarlo."""
    with pytest.raises(lector.ArchivoNoReconocido, match="hay una línea antes de la primera curva que no se entiende"):
        lector.leer_curvas(una_vez(texto(lector, PDD), "$NUMS 012", malo))


def test_nums_dicho_dos_veces(lector):
    t = texto(lector, PDD)
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape("el archivo dice dos veces «$NUMS», con «12» y con «11»")):
        lector.leer_curvas(una_vez(t, "$NUMS 012", "$NUMS 012\n$NUMS 011"))
    assert len(lector.leer_curvas(una_vez(t, "$NUMS 012", "$NUMS 012\n# comentario\n$NUMS 12"))) == 12


def test_el_enof_del_final_es_una_linea_propia(lector):
    """Se buscaba «$ENOF» como subcadena del ultimo bloque: un archivo cortado tras su ultimo $ENOM con «$ENOF» solo dentro de un comentario se aceptaba."""
    t = texto(lector, PDD)
    with pytest.raises(lector.ArchivoNoReconocido, match="el archivo no termina: parece cortado"):
        lector.leer_curvas(t[:t.rindex("$ENOF")] + "# fin $ENOF\n")


def test_una_curva_que_se_acaba_sin_su_enom_se_rechaza_aunque_su_ultima_linea_no_este_vacia(lector):
    """(Implementador) Con el «$STOM» de la curva siguiente pegado a la ultima linea de esta, el bloque no termina en una linea vacia sino en un punto: sin su «$ENOM» la curva
    no termina, sea cual sea esa ultima linea (con un orden de cadenas `<` en lugar de `!=` el punto, que va despues del «$», pasaba)."""
    with pytest.raises(lector.ArchivoNoReconocido, match="una curva no termina: parece cortado"):
        lector.leer_curvas(texto(lector, PDD).replace("\n$ENOM\n$STOM", "$STOM", 1))


@pytest.mark.parametrize("intruso", ["$ENOF basura", "$ENOFX", "$BASURA", "basura"])
def test_lo_que_sigue_al_enof_del_final_no_se_salta(lector, intruso):
    t = texto(lector, PDD)
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(f"después del final de una curva ($ENOM) que no se entiende: «{intruso}»")):
        lector.leer_curvas(t.rstrip("\n") + "\n" + intruso + "\n")


def test_un_enof_suelto_entre_dos_curvas_se_rechaza(lector):
    """UM1-D5 admite tras $ENOM comentarios y el $ENOF DEL FINAL: uno entre dos curvas se aceptaba (P-12)."""
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape("hay una línea después del final de una curva ($ENOM) que no se entiende: «$ENOF»")):
        lector.leer_curvas(texto(lector, PDD).replace("$ENOM\n$STOM", "$ENOM\n$ENOF\n$STOM", 1))


@pytest.mark.parametrize("malo", ["Wedge angle[deg] :15.0", "Wedge angle(deg):15.0", "Wedge angle[deg]>:15.0", "Wedge angle 15.0"])
def test_una_linea_de_parametros_sin_la_forma_nombre_unidad_valor_se_rechaza(lector, malo):
    """Una linea asi se descartaba y el angulo quedaba en None («no lo dice»): el armado se saltaba la comparacion con el accesorio (P-13)."""
    t = una_vez(texto(lector, "name.data"), "Wedge angle[deg]:15.0", malo)
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(f"el name.data tiene una línea de parámetros que no es «nombre[unidad]:valor»: «{malo}»")):
        lector.angulo_en_parametros(t)


# ---------- Clase 4 (REAL-4, S3, P-14): los motivos dicen sus unidades entre corchetes ----------
def test_los_motivos_dicen_sus_unidades_entre_corchetes(lector):
    def motivo(funcion, t):
        with pytest.raises(lector.ArchivoNoReconocido) as e:
            funcion(t)
        return str(e.value)
    assert "no vale 1.000 en 10 × 10 [cm]" in motivo(lector.leer_tabla_of, una_vez(texto(lector, OF), "10, 0.918, 0.930, 0.950, 0.964, 0.973, 1.000, ",
                                                                                     "10, 0.918, 0.930, 0.950, 0.964, 0.973, 1.001, "))
    assert motivo(lector.dosis_de_referencia_cuna, una_vez(texto(lector, "name.data"), "depth[Gy]", "depth[mGy]")).endswith(
        "viene en [mGy] por [MU]: se esperaba [Gy] o [cGy] por [MU]")
    assert motivo(lector.leer_curvas, texto(lector, PDD).replace("%FLSZ 100*100", "%FLSZ 000*100", 1)) == \
        "hay una curva con un campo imposible: 0 × 10 [cm] (la cabecera lo da en [mm]: «000*100»)"
    assert motivo(lector.leer_curvas, texto(lector, PDD).replace("%SSD 1000", "%SSD mil", 1)) == "La SSD de una curva no se puede leer: «mil» (la cabecera la da en [mm])"


# ---------- Clase 5 (REAL-3): una exportacion guardada como «Unicode» (UTF-16) lo dice ----------
@pytest.mark.parametrize("codificacion", ["utf-16", "utf-16-le", "utf-16-be"])
@pytest.mark.parametrize("nombre", [PDD, OF, "name.data"])
def test_un_archivo_guardado_como_utf16_dice_que_lo_es(lector, nombre, codificacion):
    """Se rechazaba con motivos falsos («no tiene curvas W2CAD», «parece cortado»): el fisico buscaria un corte que no existe."""
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape("parece guardado como «Unicode» (UTF-16)")):
        lector.decodificar(crudo(nombre).decode("utf-8-sig").encode(codificacion))


# ---------- Clase 6 (REAL-1, O5): una curva con puntos fuera de y = 0 no se lee como una por el eje ----------
@pytest.mark.parametrize("como, reemplazo", [("en diagonal (x = y)", r"<\1 \1 "), ("a lo largo de y", r"<+000.0 \1 "), ("fuera del eje (y = 5 cm)", r"<\1 +050.0 "),
                                              ("fuera del eje, por el lado negativo (y = -5 cm)", r"<\1 -050.0 ")])
def test_una_curva_con_puntos_fuera_de_y_0_se_rechaza(lector, como, reemplazo):
    """`Curva` no guarda y: un perfil diagonal del 40 x 40 puesto delante del cruzado se elegia para el OAR y lo cambiaba un 10 % (auditoria, REAL-1). (Implementador) El motivo
    dice de que y a que y esta la curva, en cm, leido del TEXTO de la curva y no del lector; y la y negativa se rechaza igual que la positiva."""
    preambulo, primera, *resto = texto(lector, PERFILES).split("$STOM")
    cambiada = re.sub(r"<([+-][0-9.]+) \+000\.0 ", reemplazo, primera)
    assert cambiada != primera
    ys = [float(y) for y in re.findall(r"<[+-][0-9.]+ ([+-][0-9.]+) [+-][0-9.]+ [+-][0-9.]+>", cambiada)]      # la y de cada punto, en mm, tal como dice el archivo
    assert len(ys) == cambiada.count("<") > 0 and (min(ys) != 0 or max(ys) != 0)      # se leyo la y de TODOS los puntos, y alguna no es 0
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(f"hay una curva con puntos fuera de y = 0 (y de {min(ys) / 10:g} a {max(ys) / 10:g} [cm])")):
        lector.leer_curvas("$STOM".join([preambulo, cambiada, *resto]))


def test_y_menos_cero_es_y_0_y_las_curvas_reales_estan_en_y_0(lector):
    assert len(lector.leer_curvas(una_vez(texto(lector, PDD), PUNTO, "<+000.0 -000.0 +000.0 +045.300>"))) == 12
    assert len(lector.leer_curvas(texto(lector, PERFILES))) == 59

# ---------- Clase 3 (P-01 a P-11): los casos de la lente de pruebas de la auditoria independiente de UM.1 (logs/UM1/auditoria_pruebas/test_auditoria_um1_pruebas.py del
# anexo), copiados tal cual salvo IX13. Cada uno nombra el mutante (logs/UM1/auditoria_pruebas/mutantes_literales.py) que sobrevivia a los 242 casos de UM.1 y que caza:
# prueban barreras que el lector ya tenia, asi que su rojo no es contra HEAD sino la mutacion que sobrevivia (um1b_mutaciones.py). ----------
# FL09: las MU de referencia nunca valen otra cosa que 100 en la prueba: un lector que dividiera por 100 fijo pasaba.
@pytest.mark.parametrize("dosis, mu, esperado", [("[Gy]:0.662300", "[MU]:200.000000", 0.33115), ("[Gy]:0.662300", "[MU]:50.000000", 1.3246)])
def test_fl09_las_mu_de_referencia_dividen_de_verdad(lector, dosis, mu, esperado):
    t = texto(lector, "name.data").replace("[Gy]:0.662300", dosis).replace("[MU]:100.000000", mu)
    assert lector.dosis_de_referencia_cuna(t) == pytest.approx(esperado, rel=1e-12)


# FL01, FL02: «decimales» en la prueba eran 50.0 y 1000.0: un lector que truncara o redondeara los mm pasaba.
def test_fl01_fl02_la_cabecera_con_fraccion_de_mm_no_se_trunca(lector):
    t = texto(lector, OF).replace("%DetectorDepth 50", "%DetectorDepth 50.5").replace("%SourcePhantomDistance 1000", "%SourcePhantomDistance 1000.5")
    tabla = lector.leer_tabla_of(t)
    assert (tabla.prof_cm, tabla.ssd_cm) == (50.5 / 10, 1000.5 / 10)
    curva = lector.leer_curvas(texto(lector, PDD).replace("%FLSZ 100*100", "%FLSZ 100.4*100.6"))
    assert next(c.campo_cm for c in curva if c.campo_cm[0] > 10 and c.campo_cm[0] < 10.1) == (100.4 / 10, 100.6 / 10)


# IX06: en las cinco tablas el 10 ocupa la misma posicion en X y en Y: la celda 10 x 10 con los indices cruzados pasaba.
def test_ix06_la_celda_de_10_x_10_con_lados_x_e_y_distintos(lector):
    t = texto(lector, OF)
    sin_la_primera_fila = re.sub(r"(?m)^2\.5, 0\.870.*\n", "", t, count=1)
    assert sin_la_primera_fila != t
    tabla = lector.leer_tabla_of(sin_la_primera_fila)
    assert tabla.y[0] == 3.0 and tabla.x[0] == 2.5
    assert float(tabla.m[list(tabla.y).index(10.0), list(tabla.x).index(10.0)]) == 1.0


# IX17: en todas las tablas reales los lados Y coinciden con los primeros lados X: interpolar la columna con los lados X pasaba.
def test_ix17_la_columna_se_interpola_con_los_lados_y(lector):
    x, y = np.array([5.0, 10.0, 20.0]), np.array([4.0, 10.0, 20.0])
    m = np.array([[1.0, 0.98, 1.0], [0.99, 1.0, 0.99], [1.0, 1.0, 1.0]])
    (yy, xx, v, por_fila, por_columna), = lector.valores_fuera_de_tendencia(lector.TablaOF(x, y, m, 100.0, 5.0))
    assert (yy, xx, v) == (10.0, 10.0, 1.0)
    assert por_columna == pytest.approx(0.98 + 0.02 * math.log(10 / 4) / math.log(20 / 4), abs=1e-12)
    assert por_fila == pytest.approx(0.99, abs=1e-12)


# RX13: una sola curva con «# machine:» vacio entre once que dicen «600C, 6X» se rechaza (con (.+) se ignoraba y pasaba).
def test_rx13_un_dato_vacio_en_una_sola_curva_no_se_ignora(lector):
    partes = texto(lector, PDD).split("# machine: 600C, 6X\n")
    assert len(partes) == 13
    t = "# machine: 600C, 6X\n".join(partes[:6]) + "# machine:\n" + "# machine: 600C, 6X\n".join(partes[6:])
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape("la cabecera dice dos veces «machine», con «600C, 6X» y con «»")):
        lector.identidad(t)


# RX24: en la tabla, un «%DetectorDepth » vacio junto a uno con valor se rechaza (con (.+) se ignoraba y la tabla pasaba).
def test_rx24_un_dato_vacio_repetido_en_la_tabla_no_se_ignora(lector):
    t = texto(lector, OF).replace("%DetectorDepth 50\n", "%DetectorDepth \n%DetectorDepth 50\n", 1)
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape("dice dos veces «DetectorDepth», con «» y con «50»")):
        lector.leer_tabla_of(t)


# RX29: en el name.data, un «Wedge angle[deg]:» vacio junto a uno con valor se rechaza (con (.+) se tomaba el 15 en silencio).
def test_rx29_un_parametro_vacio_repetido_no_se_ignora(lector):
    t = texto(lector, "name.data").replace("Wedge angle[deg]:15.0\n", "Wedge angle[deg]:\nWedge angle[deg]:15.0\n", 1)
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape("dice dos veces «Wedge angle», con « [deg]» y con «15.0 [deg]»")):
        lector.angulo_en_parametros(t)


# RX01 a RX04: angulo_cuna solo se probaba con los cuatro accesorios reales.
@pytest.mark.parametrize("accesorio", ["Standard Wedge - 15 EDW", "Standard Wedge - ", "Standard Wedge -15", "standard wedge - 15", "Standard Wedge -  15"])
def test_rx01_a_rx04_un_accesorio_que_no_es_exactamente_una_cuna_fisica_no_da_angulo(lector, accesorio):
    assert lector.Identidad("600C", "6X", accesorio, "OPD").angulo_cuna is None


# RX05, RX06: «Unique 6000» y «Phoenix» pasaban por su prefijo, no por el fullmatch.
@pytest.mark.parametrize("nombre", ["Clinac 6000", "600C2", "600 C 2", "iX2", "Clinac iX 2"])
def test_rx05_rx06_un_nombre_que_empieza_como_uno_conocido_no_es_ese_equipo(lector, nombre):
    assert lector.clave_equipo(nombre) is None


# RX09, RX11: una unidad sin numero y la unidad en minusculas.
@pytest.mark.parametrize("texto_e, clave", [("X", None), ("MV", None), (".5X", None), ("6x", "6 MV"), ("6 mv", "6 MV")])
def test_rx09_rx11_clave_de_energia_sin_numero_o_en_minusculas(lector, texto_e, clave):
    assert lector.clave_energia(texto_e) == clave


# RX20: un archivo que no empieza por $NUMS (una linea en blanco delante) sigue comprobando cuantas curvas anuncia.
def test_rx20_el_numero_de_curvas_se_comprueba_aunque_nums_no_sea_la_primera_linea(lector):
    with pytest.raises(lector.ArchivoNoReconocido, match="anuncia 11 curvas y trae 12"):
        lector.leer_curvas("\n" + texto(lector, PDD).replace("$NUMS 012", "$NUMS 011", 1))


# RX26: un %DetectorDepth dentro de un comentario no es la cabecera.
def test_rx26_un_dato_comentado_no_es_la_cabecera(lector):
    t = texto(lector, OF).replace("%DetectorDepth 50\n", "# %DetectorDepth 50\n", 1)
    with pytest.raises(lector.ArchivoNoReconocido, match="no es una tabla de factores con SSD y profundidad"):
        lector.leer_tabla_of(t)


# RX30, RX31: el nombre y la unidad se cortan en el PRIMER «[...]:» (un valor con corchetes no cambia el nombre).
def test_rx30_rx31_un_valor_con_corchetes_no_cambia_el_nombre_ni_la_unidad(lector):
    t = texto(lector, "name.data").replace("Wedge material[]:Fe", "Wedge material[]:Fe [x]: y", 1)
    assert lector.leer_parametros(t)["Wedge material"] == ("Fe [x]: y", "")


# IX13: un name.data con dos secciones «Data parameters:» se rechaza (con rsplit se tomaba la ultima en silencio; UM.1b: por la segunda marca).
def test_ix13_dos_secciones_de_parametros_que_se_contradicen(lector):
    t = texto(lector, "name.data") + "Data parameters:\nWedge angle[deg]:30.0\n"
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape("no es «nombre[unidad]:valor»: «Data parameters:»")):      # UM.1b: la segunda marca ya no es un parametro
        lector.angulo_en_parametros(t)


# IX09: un punto con dos espacios entre numeros se lee igual.
def test_ix09_un_punto_con_dos_espacios_se_lee(lector):
    t = texto(lector, PDD).replace("<+000.0 +000.0 +000.0 +045.300>", "<+000.0  +000.0\t+000.0 +045.300>", 1)
    assert lector.leer_curvas(t)[0].valor[0] == 45.3


# LT03, LT04: el tipo de la tabla es exactamente «OutputFactorTable».
@pytest.mark.parametrize("tipo", ["OutputFactorTable_calculated", "outputfactortable", "WedgeOutputFactorTable"])
def test_lt03_lt04_otro_tipo_parecido_no_es_una_tabla_de_factores(lector, tipo):
    with pytest.raises(lector.ArchivoNoReconocido, match="no es una tabla de factores"):
        lector.leer_tabla_of(texto(lector, OF).replace("%TYPE OutputFactorTable", f"%TYPE {tipo}", 1))


# LT06, LT08: las unidades se comparan tal cual (la prueba solo probaba mGy, rad y arcmin).
@pytest.mark.parametrize("unidad", ["GY", "gy", "CGY"])
def test_lt06_otra_grafia_de_gy_se_rechaza(lector, unidad):
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(f"viene en [{unidad}] por [MU]")):
        lector.dosis_de_referencia_cuna(texto(lector, "name.data").replace("calibration depth[Gy]", f"calibration depth[{unidad}]"))


@pytest.mark.parametrize("unidad", ["Deg", "DEG"])
def test_lt08_otra_grafia_de_deg_se_rechaza(lector, unidad):
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(f"viene en [{unidad}]: se esperaba [deg]")):
        lector.angulo_en_parametros(texto(lector, "name.data").replace("angle[deg]", f"angle[{unidad}]"))


# LT10, LT11, LT12: una linea que empieza por «$» dentro de una curva o tras su $ENOM no se salta («!» y «basura» no la cubrian).
def test_lt10_una_linea_con_dolar_dentro_de_una_curva_se_rechaza(lector):
    with pytest.raises(lector.ArchivoNoReconocido, match="hay una línea que no se entiende: «\\$BASURA»"):
        lector.leer_curvas(texto(lector, PDD).replace("%FLSZ 025*025\n", "%FLSZ 025*025\n$BASURA\n", 1))


@pytest.mark.parametrize("intruso", ["$BASURA", "$ENOF basura", "$ENOFX"])
def test_lt11_lt12_una_linea_con_dolar_tras_enom_se_rechaza(lector, intruso):
    with pytest.raises(lector.ArchivoNoReconocido, match="después del final de una curva"):
        lector.leer_curvas(texto(lector, PDD).replace("$ENOM\n$STOM", f"$ENOM\n{intruso}\n$STOM", 1))


# LT14: el $ENOF que cuenta es el del final, no uno suelto entre dos curvas.
def test_lt14_un_enof_entre_curvas_no_reemplaza_al_del_final(lector):
    t = texto(lector, PDD).replace("$ENOM\n$STOM", "$ENOM\n$ENOF\n$STOM", 1)
    t = t[:t.rindex("$ENOF")]
    with pytest.raises(lector.ArchivoNoReconocido, match="el archivo no termina: parece cortado"):
        lector.leer_curvas(t)


# LT16: el campo se escribe X*Y; «100x100» no es un campo.
def test_lt16_un_campo_con_x_no_es_un_campo(lector):
    with pytest.raises(lector.ArchivoNoReconocido, match="hay una curva que no dice su campo"):
        lector.leer_curvas(texto(lector, PDD).replace("%FLSZ 100*100", "%FLSZ 100x100", 1))


# LT17: el parametro se busca por el COMIENZO de su nombre.
def test_lt17_un_parametro_que_contiene_el_nombre_no_es_ese_parametro(lector):
    t = texto(lector, "name.data").replace("Wedge angle[deg]:15.0\n", "Nominal Wedge angle[deg]:30.0\nWedge angle[deg]:15.0\n", 1)
    assert lector.angulo_en_parametros(t) == 15.0


# FL03: una fila con una coma al final (una celda vacia) se rechaza, no se salta la celda.
def test_fl03_una_celda_vacia_se_rechaza(lector):
    t = texto(lector, OF).replace("0.969\n", "0.969,\n", 1)
    with pytest.raises(lector.ArchivoNoReconocido, match="no son números separados por comas"):
        lector.leer_tabla_of(t)


# FL06: una coma decimal no es un numero (no se adivina el separador).
def test_fl06_una_coma_decimal_se_rechaza(lector):
    with pytest.raises(lector.ArchivoNoReconocido, match="las dos deben ser números mayores que 0"):
        lector.dosis_de_referencia_cuna(texto(lector, "name.data").replace("[Gy]:0.662300", "[Gy]:0,662300"))


# CV06: el angulo del name.data solo se probaba con 15.0 (entero): un lector que lo truncara pasaba y la comprobacion del armado contra el accesorio
# («Standard Wedge - 15») dejaba pasar un 15.4.
def test_cv06_el_angulo_con_decimales_no_se_trunca(lector):
    assert lector.angulo_en_parametros(texto(lector, "name.data").replace("Wedge angle[deg]:15.0", "Wedge angle[deg]:15.4")) == 15.4


# CV02: la clave de energia pasa por float (6.0X es 6 MV); solo se probaba con enteros.
@pytest.mark.parametrize("texto_e, clave", [("6.0X", "6 MV"), ("06.50 MV", "6.5 MV")])
def test_cv02_la_energia_con_decimales_se_normaliza(lector, texto_e, clave):
    assert lector.clave_energia(texto_e) == clave


# CV01: el angulo de la cuna del accesorio es un entero (el armado lo escribe «de 15°» en sus motivos).
def test_cv01_el_angulo_del_accesorio_es_entero(lector):
    assert type(lector.Identidad("600C", "6X", "Standard Wedge - 15", "OPD").angulo_cuna) is int


# ---------- Ronda 1 de la revision de UM.1b (08-11-2026, dos revisores de Opus): R1 a R4 ----------
# R1 (la clase 2 seguia abierta con «#»): un «3» que se vuelve «#» es un solo bit y la fila Y 30, Y 35 o Y 3 de la tabla desaparecia sin aviso; un «#» delante de un punto lo perdia.
#    Medido en los 5890 bloques de curva y las 105 tablas reales (scripts/um1b_corr_medir_orden.py del anexo): en una curva TODOS los comentarios van antes de la primera clave (o tras el
#    $ENOM) y en una tabla antes de la linea de lados X (el «# Data» incluido); ninguno entre los datos y ninguno contiene «<» ni «%».
# R2 (la clase 1 seguia abierta con el blanco ASCII): «0» -> « » es un solo bit; un blanco al final de un numero se recortaba y «5 » se leia 0.5 cm (la profundidad de la tabla), «1.10 » 1.10
#    (en vez de 1.107) y «%FLSZ 100*10 » un campo de 10 x 1 cm. Ninguna linea de los 522 archivos reales empieza ni termina en blanco.
# R3 (la prueba era debil): la mutacion que recortaba la cabecera de la tabla con rstrip() (tambien los blancos de Unicode) sobrevivia: aqui cada sitio se prueba con un blanco ASCII, un
#    tabulador y los dos de Unicode.
# R4 (str.split() sin argumentos separaba los numeros de un punto con cualquier blanco de Unicode): solo el espacio y el tabulador separan.
@pytest.mark.parametrize("viejo, nuevo", [("\n30, 0.", "\n#0, 0."), ("\n3, 0.", "\n#, 0."), ("\n35, 0.", "\n#5, 0."), ("\n20, 0.", "\n#20, 0."),
                                          ("\n40, 0.", "\n#40, 0."), ("\n2.5, 0.870", "\n#2.5, 0.870")])
def test_r1_una_fila_de_la_tabla_comentada_no_se_pierde(lector, viejo, nuevo):
    """Las tres primeras son el cambio de un solo bit del «3» (Y 30, Y 3 y Y 35: el motor interpolaba -1.07 % a 25 x 30 cm y +0.67 % a 25 x 35); las otras, un «#» delante (la ultima fila y la primera
    tambien cuentan)."""
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape("la tabla de factores tiene un comentario entre sus datos: «#")):
        lector.leer_tabla_of(una_vez(texto(lector, OF), viejo, nuevo))


def test_r1_un_comentario_justo_despues_de_la_linea_de_lados_x_se_rechaza(lector):
    """La frontera: la linea de lados X es el primer dato de la tabla; un comentario despues de ella ya esta entre los datos."""
    with pytest.raises(lector.ArchivoNoReconocido, match="la tabla de factores tiene un comentario entre sus datos: «# nota»"):
        lector.leer_tabla_of(una_vez(texto(lector, OF), ", 40\n2.5, 0.870", ", 40\n# nota\n2.5, 0.870"))


def test_r1_los_comentarios_de_antes_de_la_linea_de_lados_x_siguen_valiendo(lector):
    """El «# Data» de Eclipse va entre las claves y la linea de lados X; uno mas, o uno entre las claves, no cambia lo que se lee."""
    t = texto(lector, OF)
    antes = una_vez(t, "# Data\n", "# Data\n# otra nota\n").replace("%DetectorDepth 50\n", "%DetectorDepth 50\n# y otra\n")
    assert antes != t and lector.leer_tabla_of(antes).m.tolist() == lector.leer_tabla_of(t).m.tolist()


def test_r1_un_comentario_al_final_de_la_tabla_se_rechaza(lector):
    with pytest.raises(lector.ArchivoNoReconocido, match="la tabla de factores tiene un comentario entre sus datos: «# fin»"):
        lector.leer_tabla_of(texto(lector, OF) + "# fin\n")


@pytest.mark.parametrize("viejo, nuevo", [(PUNTO, "#" + PUNTO), (PUNTO, "# " + PUNTO), ("<+000.0 +000.0 +010.0 +098.200>", "#<+000.0 +000.0 +010.0 +098.200>"),
                                          ("<+000.0 +000.0 +300.0 +017.000>", "#<+000.0 +000.0 +300.0 +017.000>")])
def test_r1_un_punto_de_una_curva_comentado_no_se_pierde(lector, viejo, nuevo):
    """El primero (la curva empezaba en z = 0.1 en vez de 0.0), uno del medio y el ultimo de la primera curva del PDD."""
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape("hay un comentario («#») entre las claves o los puntos de una curva: «#")):
        lector.leer_curvas(una_vez(texto(lector, PDD), viejo, nuevo))


@pytest.mark.parametrize("bloque", ["%FLSZ 100*100\n# nota\n<+0 +0 +0 +1>\n", "<+0 +0 +0 +1>\n# nota\n%FLSZ 100*100\n"])
def test_r1_un_comentario_despues_de_la_primera_clave_o_del_primer_punto_de_una_curva_se_rechaza(lector, bloque):
    """Las dos condiciones: una clave sin puntos todavia, y un punto sin claves todavia."""
    with pytest.raises(lector.ArchivoNoReconocido, match="hay un comentario"):
        lector.leer_curvas("$NUMS 001\n$STOM\n" + bloque + "$ENOM\n$ENOF\n")


def test_r1_los_comentarios_de_antes_de_la_primera_clave_y_de_despues_del_enom_siguen_valiendo(lector):
    curvas = lector.leer_curvas("$NUMS 001\n$STOM\n# nota\n#\n%FLSZ 100*100\n<+0 +0 +0 +1>\n$ENOM\n# despues\n$ENOF\n")
    assert len(curvas) == 1 and curvas[0].campo_cm == (10.0, 10.0)


@pytest.mark.parametrize("blanco", BLANCOS)
@pytest.mark.parametrize("viejo, nuevo, que", [
    ("%DetectorDepth 50\n", "%DetectorDepth 5{b}\n", "La profundidad de la tabla no se puede leer: «5{b}» (la cabecera la da en [mm])"),
    ("%DetectorDepth 50\n", "%DetectorDepth 50{b}\n", "La profundidad de la tabla no se puede leer: «50{b}» (la cabecera la da en [mm])"),
    ("%SourcePhantomDistance 1000\n", "%SourcePhantomDistance 100{b}\n", "La SSD de la tabla no se puede leer: «100{b}» (la cabecera la da en [mm])"),
    ("%SourcePhantomDistance 1000\n", "%SourcePhantomDistance 1000{b}\n", "La SSD de la tabla no se puede leer: «1000{b}» (la cabecera la da en [mm])"),
])
def test_r2_r3_un_blanco_al_final_de_un_dato_numerico_de_la_cabecera_de_la_tabla_no_se_recorta(lector, blanco, viejo, nuevo, que):
    """«%DetectorDepth 50» con su ultima cifra reemplazada por un espacio se leia 0.5 cm (d0 de 0.5 cm en vez de 5): las UM de X 25 x Y 30 a 5 cm subian +5.3 % (revision, R2). El mutante del
    revisor (recortar la cabecera con rstrip(), tambien los blancos de Unicode) sobrevivia a las dos pruebas del lector (R3)."""
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(que.format(b=blanco))):
        lector.leer_tabla_of(una_vez(texto(lector, OF), viejo, nuevo.format(b=blanco)))


@pytest.mark.parametrize("blanco, se_lee", [(" ", True), ("\t", True), (" \t  ", True), (EM, False), (NBSP, False)])
def test_r2_un_blanco_al_final_del_tipo_de_la_tabla_es_un_texto_y_se_recorta_si_es_ascii(lector, blanco, se_lee):
    """UM1b-D5 se acota a los TEXTOS: «%TYPE OutputFactorTable » se lee (se compara entera con el nombre del tipo; un blanco no puede reemplazar una letra sin que deje de coincidir), pero solo si el
    blanco es un espacio o un tabulador."""
    t = una_vez(texto(lector, OF), "%TYPE OutputFactorTable\n", f"%TYPE OutputFactorTable{blanco}\n")
    if se_lee:
        assert lector.leer_tabla_of(t).m[0, 0] == 0.870
    else:
        with pytest.raises(lector.ArchivoNoReconocido, match="no es una tabla de factores"):
            lector.leer_tabla_of(t)


@pytest.mark.parametrize("blanco", BLANCOS)
@pytest.mark.parametrize("viejo, nuevo", [
    (", 1.107\n", ", 1.10{b}\n"),        # la ultima celda de la ultima fila, con su ultima cifra reemplazada (1.107 se leia 1.10)
    (", 1.107\n", ", 1.107{b}\n"),       # ... o con un blanco de mas
    (", 0.874, ", ", 0.87{b}, "),         # una celda del medio: el blanco queda antes de la coma (0.874 se leia 0.87)
    (", 40\n", ", 4{b}\n"),              # la linea de lados X
    ("\n40, ", "\n4{b}, "),              # un lado Y
])
def test_r2_r3_un_blanco_al_final_de_una_celda_de_la_tabla_no_se_recorta(lector, blanco, viejo, nuevo):
    with pytest.raises(lector.ArchivoNoReconocido, match="la tabla de factores tiene una línea que no son números separados por comas"):
        lector.leer_tabla_of(una_vez(texto(lector, OF), viejo, nuevo.format(b=blanco)))


@pytest.mark.parametrize("blanco", BLANCOS)
@pytest.mark.parametrize("viejo, nuevo, que", [
    ("%FLSZ 100*100\n", "%FLSZ 100*10{b}\n", "El campo de una curva no se puede leer: «10{b}»"),
    ("%FLSZ 100*100\n", "%FLSZ 10{b}*100\n", "El campo de una curva no se puede leer: «10{b}»"),
    ("%FLSZ 100*100\n", "%FLSZ 100{b}*100\n", "El campo de una curva no se puede leer: «100{b}»"),
    ("%FLSZ 100*100\n", "%FLSZ 100*{b}100\n", "El campo de una curva no se puede leer: «{b}100»"),
    ("%FLSZ 100*100\n", "%FLSZ 100*100{b}\n", "El campo de una curva no se puede leer: «100{b}»"),
    ("%SSD 1000\n", "%SSD 100{b}\n", "La SSD de una curva no se puede leer: «100{b}»"),
    ("%SSD 1000\n", "%SSD 1000{b}\n", "La SSD de una curva no se puede leer: «1000{b}»"),
])
def test_r2_r3_un_blanco_en_un_dato_numerico_de_la_cabecera_de_una_curva_no_se_recorta(lector, blanco, viejo, nuevo, que):
    """«%FLSZ 100*10 » daba un campo de 10 x 1 cm y «%FLSZ 10 *100» uno de 1 x 10 (ejemplo exacto de H-UM1b-2: se cerro solo para el espacio sin separacion). Los blancos junto al «*» ya no
    se admiten: ningun archivo real los trae (5886 de 5886 son «NNN*NNN»)."""
    t = texto(lector, PDD).replace(viejo, nuevo.format(b=blanco), 1)
    with pytest.raises(lector.ArchivoNoReconocido, match=re.escape(que.format(b=blanco))):
        lector.leer_curvas(t)


@pytest.mark.parametrize("nuevo", [
    "<+002.5 +000.0 +013.5 +099.52 >",
    "<+002.5 +000.0 +013.5 +099.52\t>",
    "<+002.5 +000.0 +013.5 +099.52" + EM + ">",        # R4: se tomaba por separador y el numero quedaba truncado (-0.001 %)
    "<+002.5 +000.0 +013.5 +099.52" + NBSP + ">",
    "< +002.5 +000.0 +013.5 +099.521>",
    "<" + NBSP + "+002.5 +000.0 +013.5 +099.521>",
    "<+002.5" + NBSP + "+000.0 +013.5 +099.521>",       # R4: un espacio sin separacion no separa dos numeros
    "<+002.5 +000.0" + EM + "+013.5 +099.521>",
])
def test_r2_r4_un_blanco_dentro_de_un_punto_no_se_recorta_y_solo_el_espacio_y_el_tabulador_separan(lector, nuevo):
    t = texto(lector, PERFILES)
    assert PUNTO_PERFIL in t
    with pytest.raises(lector.ArchivoNoReconocido, match="hay un punto que no tiene cuatro números válidos"):
        lector.leer_curvas(t.replace(PUNTO_PERFIL, nuevo, 1))


@pytest.mark.parametrize("blanco", BLANCOS)
@pytest.mark.parametrize("viejo, nuevo, motivo", [
    ("[Gy]:0.662300", "[Gy]:0.66230{b}", "las dos deben ser números mayores que 0"),
    ("[Gy]:0.662300", "[Gy]:0.662300{b}", "las dos deben ser números mayores que 0"),
    ("[MU]:100.000000", "[MU]:10{b}", "las dos deben ser números mayores que 0"),      # «100» con su ultima cifra reemplazada: 10 UM en vez de 100
])
def test_r2_r3_un_blanco_al_final_de_la_dosis_o_las_mu_de_la_cuna_no_se_recorta(lector, blanco, viejo, nuevo, motivo):
    with pytest.raises(lector.ArchivoNoReconocido, match=motivo):
        lector.dosis_de_referencia_cuna(una_vez(texto(lector, "name.data"), viejo, nuevo.format(b=blanco)))


@pytest.mark.parametrize("blanco", BLANCOS)
@pytest.mark.parametrize("nuevo", ["Wedge angle[deg]:1{b}", "Wedge angle[deg]:15.0{b}"])
def test_r2_r3_un_blanco_al_final_del_angulo_de_la_cuna_no_se_recorta(lector, blanco, nuevo):
    with pytest.raises(lector.ArchivoNoReconocido, match="el ángulo de la cuña no se puede leer"):
        lector.angulo_en_parametros(una_vez(texto(lector, "name.data"), "Wedge angle[deg]:15.0", nuevo.format(b=blanco)))


def test_r2_la_orientacion_de_la_cuna_es_un_texto_y_se_recorta_a_la_derecha(lector):
    assert lector.orientacion_de_cuna(una_vez(texto(lector, "name.data"), "(IN/OUT/LEFT/RIGHT)[]:IN", "(IN/OUT/LEFT/RIGHT)[]:in \t")) == "IN"


def test_r2_la_sangria_de_una_linea_con_clave_no_cambia_lo_que_se_lee(lector):
    """Lo que se recorta sigue siendo la sangria (a la izquierda); lo que ya no se recorta es el final de una linea con numeros."""
    curvas = lector.leer_curvas(texto(lector, PDD).replace("%SSD 1000\n", "  \t%SSD 1000\n").replace("%FLSZ 100*100\n", " %FLSZ 100*100\n"))
    assert {c.ssd_cm for c in curvas} == {100.0} and (10.0, 10.0) in [c.campo_cm for c in curvas]
    assert lector.leer_tabla_of(texto(lector, OF).replace("\n40, 0.", "\n  40, 0.")).y[-1] == 40.0


@pytest.mark.parametrize("blanco", [EM, NBSP])
def test_r3_un_blanco_de_unicode_no_es_sangria_ni_final_de_linea(lector, blanco):
    """Solo el espacio y el tabulador se recortan (`_BLANCOS`): un blanco de Unicode delante de una clave, un punto, una fila, una celda o el valor de un parametro, o detras de un punto o de un
    marcador, es un caracter que no se entiende y el archivo se rechaza (las mutaciones que recortaban con lstrip() o rstrip() sin argumentos, que tambien quitan los de Unicode, sobrevivian)."""
    pdd, of, nd = texto(lector, PDD), texto(lector, OF), texto(lector, "name.data")
    casos = [
        (lector.leer_curvas, pdd.replace("%SSD 1000\n", f"{blanco}%SSD 1000\n", 1), "hay una línea que no se entiende"),
        (lector.leer_curvas, pdd.replace(PUNTO, f"{blanco}{PUNTO}", 1), "hay una línea que no se entiende"),
        (lector.leer_curvas, pdd.replace(PUNTO, f"{PUNTO}{blanco}", 1), "hay un punto que no se puede leer"),
        (lector.leer_curvas, pdd.replace("$ENOM\n", f"$ENOM{blanco}\n", 1), "hay una línea que no se entiende"),
        (lector.leer_tabla_of, of.replace("\n40, 0.", f"\n{blanco}40, 0.", 1), "no son números separados por comas"),
        (lector.leer_tabla_of, of.replace("0.933, 0.949", f"0.933,{blanco}0.949", 1), "no son números separados por comas"),
        (lector.dosis_de_referencia_cuna, nd.replace("[Gy]:0.662300", f"[Gy]:{blanco}0.662300"), "las dos deben ser números mayores que 0"),
    ]
    for leer, t, motivo in casos:
        with pytest.raises(lector.ArchivoNoReconocido, match=motivo):
            leer(t)


@pytest.mark.parametrize("blanco", [EM, NBSP])
def test_r3_la_orientacion_de_la_cuna_no_pierde_un_blanco_de_unicode_al_final(lector, blanco):
    assert lector.orientacion_de_cuna(una_vez(texto(lector, "name.data"), "(IN/OUT/LEFT/RIGHT)[]:IN", f"(IN/OUT/LEFT/RIGHT)[]:IN{blanco}")) == "IN" + blanco


def test_r2_los_blancos_ascii_detras_de_un_punto_un_marcador_o_un_comentario_no_cambian_lo_que_se_lee(lector):
    """Lo que SI se recorta a la derecha es lo que no lleva un numero hasta el final de la linea: el punto tras su «>», los marcadores y los comentarios (un editor puede dejar blancos ahi y no esconden
    ninguna cifra); delante de cualquier linea se recorta la sangria."""
    t = texto(lector, PDD)
    sucio = "\n".join((" \t" + l + "  \t") if l.startswith(("<", "$", "#")) else l for l in t.split("\n"))
    assert sucio != t
    for a, b in zip(lector.leer_curvas(sucio), lector.leer_curvas(t)):
        assert a.campo_cm == b.campo_cm and a.ssd_cm == b.ssd_cm and np.array_equal(a.z_cm, b.z_cm) and np.array_equal(a.valor, b.valor)
