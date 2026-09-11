"""R7-R10, R13-R15 (PLAN_REPORTES_LEGIBLES_08-09.md, Fase C): los
mensuales dejan de terminar con la tabla "Definiciones de métricas"
(Starshot, ajena a estos reportes) y el mensual de braqui deja de
graficar 3 puntos de voltaje-vs-corriente; las medidas mecánicas y
dosimétricas llevan su unidad entre corchetes, copiada del formato
oficial `IDC-F-RT-119`; las cuatro tolerancias del mensual de
aceleradores salen de `dosimetriaMen.tolerancia_*` (no de un literal);
la tabla de aspectos mecánicos incluye los 2 campos que el cotejo pedido
por el físico encontró ausentes de todo generador de PDF; y la tabla de
actividad de braqui dice "Actividad medida" (no "calculada"), las tres
actividades en `[Ci]` (no `(U)`/`(GBq)`), y dos discrepancias CON signo,
cada una diciendo contra quién se calcula.

R11 dice la convención del eje en el ENCABEZADO de la tabla de análisis,
en vez de dibujarla sobre la placa -- decisión del físico (09-09): la
película es evidencia y superponerle cualquier cosa la vuelve un poco
menos evidencia. R12 (publicar el desfase con signo) queda DIFERIDA: al
preparar la nota se midió que `analisis_placa_correcciones.delta_x/
delta_y` NO es el desfase del campo sino la corrección de FORMA por
vértice (suman cero en los 10 controles reales), y el desfase de verdad
(`delta_cruz`) no se persiste en ninguna tabla. Ver `DP-92`."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import data.ManejoDatos.load  # noqa: F401 -- rompe el mismo ciclo de siempre
from models.PDF.pdf import generar_reporte_pdf_multitabla_mensual
from models.PDF.Mensuales.reportes_mensuales import (
    _crear_tabla_preguntas, _crear_tabla_dosimetria, _crear_tabla_dosimetria_ix,
    _crear_tabla_resultados_actividad, _no_aplica_si_vacio,
    _crear_tabla_analisis_imagen, ENCABEZADO_ANALISIS_IMAGEN)


def _codigo_sin_comentarios(ruta):
    """Descarta las líneas de comentario -- los tests de "esta cadena ya
    no está en el código" no deben confundirse con que la propia tarea
    la MENCIONE en un comentario explicando qué se retiró."""
    return "\n".join(
        linea for linea in open(ruta, encoding="utf-8").read().splitlines()
        if not linea.strip().startswith("#"))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------
# R7 -- retirar "Definiciones de métricas" de todo mensual.
# ---------------------------------------------------------------------
class TestR7SinDefinicionesDeMetricas:
    def test_la_tabla_ya_no_esta_en_el_codigo_fuente(self):
        """"Radio de convergencia" SÍ existe en `pdf.py` -- es una métrica
        real del reporte de Starshot (otra función, más abajo en el
        archivo). Lo que se retiró es la tabla dentro de
        `generar_reporte_pdf_multitabla_mensual`; se acota la búsqueda a
        esa función."""
        import inspect
        from models.PDF.pdf import generar_reporte_pdf_multitabla_mensual
        fuente = inspect.getsource(generar_reporte_pdf_multitabla_mensual)
        assert "Radio de convergencia" not in fuente
        assert "metricas_table" not in fuente
        assert "RMS residuos" not in fuente

    def test_leyenda_de_criterios_de_starshot_y_mlc_se_conserva(self):
        """La tabla retirada es distinta de la "Leyenda de criterios" de
        los reportes de MLC/Starshot -- ésa el físico no la mencionó.
        Las dos apariciones son los encabezados de sección de esas dos
        funciones (Starshot y MLC); no se cuenta comparando contra un
        número fijo para no chocar con el propio comentario de R7."""
        fuente = open("models/PDF/pdf.py", encoding="utf-8").read()
        assert "SECCIÓN 6 — Leyenda de criterios" in fuente
        assert "SECCIÓN 7 — Leyenda de criterios" in fuente


# ---------------------------------------------------------------------
# R8 -- retirar el gráfico V-vs-carga del mensual de braqui.
# ---------------------------------------------------------------------
class TestR8SinGraficoVvsCarga:
    def test_grafico_lecturas_no_esta_en_orden_tablas(self):
        """Se busca la lista viva (los 3 nombres consecutivos), no la sola
        palabra -- que sí aparece en el comentario que documenta el retiro."""
        fuente = open("models/PDF/pdf.py", encoding="utf-8").read()
        assert "'grafico_maximos', 'grafico_lecturas', 'grafico_linealidad'" not in fuente

    def test_la_funcion_se_retiro_no_quedo_huerfana(self):
        """Mismo criterio que DA-68: lo que no existe no se reconecta por
        descuido -- se retira la función, no solo la llamada."""
        fuente = _codigo_sin_comentarios("models/PDF/Mensuales/reportes_mensuales.py")
        assert "def _crear_grafico_lecturas_maximos" not in fuente
        assert "_crear_grafico_lecturas_maximos(" not in fuente

    def test_grafico_de_maximos_camaras_se_conserva(self):
        """El gráfico posición-vs-promedio (distinto del retirado) sigue."""
        fuente = open("models/PDF/Mensuales/reportes_mensuales.py",
                       encoding="utf-8").read()
        assert "_crear_grafico_maximos_camaras" in fuente

    def test_tabla_lecturas_maximos_conserva_los_datos(self):
        """El dato no se pierde, se deja de graficar."""
        fuente = open("models/PDF/Mensuales/reportes_mensuales.py",
                       encoding="utf-8").read()
        assert "_crear_tabla_lecturas_maximos" in fuente


# ---------------------------------------------------------------------
# R9/R10 -- unidades entre corchetes + los 2 campos que faltaban.
# ---------------------------------------------------------------------
class TestR9R10TablaPreguntas:
    PREGUNTA_COMPLETA = {
        'iso_mec': 1.2, 'reticulo_cent': 0.8, 'bordes_coin': 1.0,
        'camilla_vert_rango': 200.0, 'camilla_vert_desp': 1.0,
        'camilla_iso_desp': 2.0, 'telem_rango': 200.0, 'telem_desp': 0.0,
        'camp_luz_desp': 2.5, 'puntero_telem_diff': 0.0,
        'laser_techo': 0.0, 'laser_lateral27': 1.0, 'laser_lateral9': 1.0,
        'observaciones': '',
    }

    def test_bordes_coin_y_camp_luz_desp_aparecen_con_su_valor_real(self, app):
        df = _crear_tabla_preguntas([self.PREGUNTA_COMPLETA])
        texto = df.to_string()
        assert "Coincidencia de bordes de campo [mm]" in texto
        assert "Coincidencia del campo luz-radiación [mm]" in texto
        # Rojo-antes-que-verde: hasta R10 estos dos campos NUNCA
        # aparecían en ningún generador de PDF -- ahora, con dato real,
        # el valor SALE (no solo la etiqueta).
        fila_bordes = [l for l in texto.splitlines() if 'bordes de campo' in l][0]
        assert '1.0' in fila_bordes.split('bordes de campo')[1]

    def test_las_catorce_filas_de_preguntas_estan_todas(self, app):
        """Censo: de los 14 campos de `preguntas`, 11 son [mm] (bordes_coin
        y camp_luz_desp de R10 incluidos), 2 son [cm] (los rangos de
        camilla/telémetro) y 1 (observaciones) no lleva unidad."""
        df = _crear_tabla_preguntas([self.PREGUNTA_COMPLETA])
        texto = df.to_string()
        assert texto.count("[mm]") == 11
        assert texto.count("[cm]") == 2
        assert "Observaciones [" not in texto

    def test_todas_las_unidades_de_mecanicos_son_mm(self, app):
        df = _crear_tabla_preguntas([self.PREGUNTA_COMPLETA])
        texto = df.to_string()
        assert "Observaciones" in texto
        assert "Observaciones [" not in texto  # sin unidad, no es magnitud


class TestR9DosimetriaUnidadesYR14Tolerancias:
    FILA_600 = {
        'energia': '6mv', 'dosis_ref_cgy_um': 1.01, 'discrepancia_dosis': 0.5,
        'tolerancia_dosis': 2.5, 'calidad_pdd20_10': 0.665,
        'discrepancia_calidad': 0.1, 'tolerancia_calidad': 2,
        'simetria_inplane': 1.0, 'simetria_crossplane': 1.1,
        'tolerancia_simetria': 2, 'planicidad_inplane': 2.0,
        'planicidad_crossplane': 2.1, 'tolerancia_planicidad': 3,
    }

    def test_dosis_de_referencia_dice_cgy_um_no_gy_um(self, app):
        """CORRECCIÓN 10-09 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md §3-B.1,
        DP-90(b)): R9 (08-09) se apoyó en el formato en papel
        (`IDC-F-RT-119`, que dice "(Gy/UM)") por encima del dato medido --
        el valor guardado está en cGy/UM (la calculadora computa en Gy/MU
        y `emitir_dosis` hace ×100 antes de guardar). Esta aserción se
        invierte a propósito: el "[Gy/UM]" que este test exigía ANTES de
        hoy era el propio error que B.1 corrige."""
        df = _crear_tabla_dosimetria([self.FILA_600], 'si')
        texto = df.to_string()
        assert "[cGy/UM]" in texto
        assert "[Gy/UM]" not in texto

    def test_calidad_es_adimensional(self, app):
        df = _crear_tabla_dosimetria([self.FILA_600], 'si')
        assert "Calidad (PDD20/10) [1]" in df.to_string()

    def test_simetria_y_planicidad_llevan_porcentaje(self, app):
        df = _crear_tabla_dosimetria([self.FILA_600], 'si')
        texto = df.to_string()
        for etiqueta in ("Simetría Inplane [%]", "Simetría Crossplane [%]",
                          "Planicidad Inplane [%]", "Planicidad Crossplane [%]"):
            assert etiqueta in texto

    def test_tolerancia_sale_de_la_bd_no_de_un_literal(self, app):
        """R14, rojo-antes-que-verde: antes SIEMPRE decía 2/2/2/3 sin
        importar lo que hubiera en la BD."""
        df = _crear_tabla_dosimetria([self.FILA_600], 'si')
        assert "Tolerancia [%]: 2.5" in df.to_string()  # NO "2" (el literal viejo)

    def test_cambiar_la_tolerancia_en_la_fila_cambia_el_pdf(self, app):
        fila_a = dict(self.FILA_600, tolerancia_dosis=2.5)
        fila_b = dict(self.FILA_600, tolerancia_dosis=4.0)
        texto_a = _crear_tabla_dosimetria([fila_a], 'si').to_string()
        texto_b = _crear_tabla_dosimetria([fila_b], 'si').to_string()
        assert "Tolerancia [%]: 2.5" in texto_a
        assert "Tolerancia [%]: 4.0" in texto_b
        assert texto_a != texto_b

    def test_tolerancia_nula_es_no_aplica_nunca_un_valor_por_defecto(self, app):
        fila = dict(self.FILA_600, tolerancia_planicidad=None)
        texto = _crear_tabla_dosimetria([fila], 'si').to_string()
        assert "No aplica" in texto
        assert "Tolerancia [%]: 3" not in texto  # no reintroduce el literal viejo

    def test_no_aplica_si_vacio_trata_none_y_cadena_vacia_igual(self):
        assert _no_aplica_si_vacio(None) == 'No aplica'
        assert _no_aplica_si_vacio('') == 'No aplica'
        assert _no_aplica_si_vacio(2.5) == 2.5
        assert _no_aplica_si_vacio(0) == 0  # 0 es un valor real, no "vacío"

    def test_ix_electrones_calidad_j2_j1_adimensional(self, app):
        fila_e = {
            'energia': '6mev', 'dosis_ref_cgy_um': 1.0, 'discrepancia_dosis': 0.3,
            'tolerancia_dosis': 3, 'calidad_j2_j1': 0.8, 'discrepancia_calidad': 0.1,
            'tolerancia_calidad': 3, 'simetria_inplane': 1.0,
            'simetria_crossplane': 1.0, 'tolerancia_simetria': 3,
            'planicidad_inplane': 2.0, 'planicidad_crossplane': 2.0,
            'tolerancia_planicidad': 4.5,
        }
        df = _crear_tabla_dosimetria_ix([self.FILA_600, fila_e], 'si')
        texto = df.to_string()
        assert "Calidad (J2/J1) [1]" in texto
        assert "Tolerancia [%]: 4.5" in texto

    def test_las_dos_funciones_duplicadas_reciben_el_mismo_arreglo(self, app):
        """§2.4 del plan: `_crear_tabla_dosimetria` y su gemela `_ix`
        están duplicadas a propósito -- arreglar una sola dejaría iX
        mintiendo. Las dos usan `_no_aplica_si_vacio` y los mismos
        corchetes."""
        import inspect
        fuente_600 = inspect.getsource(_crear_tabla_dosimetria)
        fuente_ix = inspect.getsource(_crear_tabla_dosimetria_ix)
        for f in (fuente_600, fuente_ix):
            assert "_no_aplica_si_vacio" in f
            assert "[cGy/UM]" in f  # B.1 (10-09): revierte R9, ver más arriba
            assert "[1]" in f


# ---------------------------------------------------------------------
# R11 -- la convención del eje, DICHA en el encabezado (no dibujada).
# ---------------------------------------------------------------------
class TestR11NotaDeConvencionDeEjes:
    FRANJAS = {'analisis_placa_franjas': [
        {'franja': 'Franja 1', 'ancho_media_h': 101.544, 'ancho_media_v': 101.262,
         'penumbra_izq_h': 5.894, 'penumbra_izq_v': 4.364,
         'penumbra_der_h': 5.494, 'penumbra_der_v': 4.311,
         'diferencia_arriba_izq': 0.066, 'diferencia_arriba_der': 0.127,
         'diferencia_abajo_izq': 0.310, 'diferencia_abajo_der': 0.274},
    ]}

    def test_el_encabezado_dice_hacia_donde_crece_el_eje_y(self, app):
        df = _crear_tabla_analisis_imagen(self.FRANJAS)
        assert df.columns[0] == ENCABEZADO_ANALISIS_IMAGEN
        assert "ABAJO" in df.columns[0]
        assert "eje Y" in df.columns[0]

    def test_la_nota_NO_afirma_un_origen(self, app):
        """El origen (`centro_teorico`) no se persiste, y los `delta_*` que
        el PDF podría publicar se miden cada uno contra su propio vértice
        ideal -- afirmar un origen común sería falso (§0.8, corrección)."""
        encabezado = ENCABEZADO_ANALISIS_IMAGEN.lower()
        assert "origen" not in encabezado
        assert "centro" not in encabezado

    def test_no_anade_ninguna_fila(self, app):
        """La nota va en una fila que YA existe: el conteo de filas de la
        tabla no cambia, así que no puede empujar una página."""
        df = _crear_tabla_analisis_imagen(self.FRANJAS)
        # 1 encabezado de columnas + 10 características (los 10 `getter`).
        assert len(df) == 11

    def test_la_convencion_que_la_nota_declara_es_la_que_el_codigo_calcula(self):
        """El test que hace VERDADERA a la nota, no solo presente.

        Si alguien invierte la resta de `delta_cruz_y` (pasa a
        `centro_teorico[1] - cruz[1]`), el eje Y deja de crecer hacia
        abajo y la nota queda mintiendo. Este test se pone rojo ANTES de
        que eso llegue a un documento firmado. Se lee por AST el archivo
        de análisis -- que este plan NO edita (zona roja): solo lo
        observa."""
        import ast
        arbol = ast.parse(
            open("analisisImagenes/Analisis_PlacaRC.py", encoding="utf-8").read())

        def _es_indice_1_de(nodo, nombre):
            return (isinstance(nodo, ast.Subscript)
                    and isinstance(nodo.value, ast.Name) and nodo.value.id == nombre
                    and isinstance(nodo.slice, ast.Constant) and nodo.slice.value == 1)

        restas = []
        for nodo in ast.walk(arbol):
            if not (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1):
                continue
            destino = nodo.targets[0]
            if not (isinstance(destino, ast.Name) and destino.id == "delta_cruz_y"):
                continue
            # delta_cruz_y = (cruz[1] - centro_teorico[1]) * ... * ...
            expr = nodo.value
            while isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Mult):
                expr = expr.left
            assert isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Sub), (
                "delta_cruz_y ya no es una resta -- la nota del encabezado "
                "afirma un sentido de eje que quizá ya no sea cierto")
            restas.append((expr.left, expr.right))

        assert restas, (
            "no se encontró `delta_cruz_y` en Analisis_PlacaRC.py -- si se "
            "renombró o se movió, hay que revisar si la nota del encabezado "
            "sigue siendo verdad antes de dejarla en el PDF")
        for izquierda, derecha in restas:
            assert _es_indice_1_de(izquierda, "cruz"), (
                "la resta de delta_cruz_y cambió de orden: la nota dice que "
                "el eje Y crece hacia ABAJO porque se calcula "
                "`cruz[1] - centro_teorico[1]` (coordenadas de imagen). Si "
                "ahora es al revés, la nota del PDF quedó FALSA")
            assert _es_indice_1_de(derecha, "centro_teorico")

    def test_la_nota_no_alcanza_a_braqui_ni_a_halcyon(self):
        """`analisis_imagen` solo está en el `orden_tablas` de 600/iX --
        el diario de braqui (R6) no publica ninguna cifra con signo, y el
        mensual de Halcyon no lleva esta tabla."""
        fuente = open("models/PDF/pdf.py", encoding="utf-8").read()
        rama_halcyon = fuente[fuente.index("if maquina == 'Halcyon' and not sistema_imagenes"):]
        rama_halcyon = rama_halcyon[:rama_halcyon.index("elif")]
        assert "analisis_imagen" not in rama_halcyon

    def test_la_imagen_no_se_toca_en_ningun_punto(self):
        """La decisión del físico: la película es evidencia. R11 no dibuja
        sobre el BLOB, ni sobre una copia, ni al componer."""
        import inspect
        from models.PDF.Mensuales import reportes_mensuales as rm
        fuente = inspect.getsource(rm._crear_tabla_analisis_imagen)
        for prohibido in ("QPixmap", "QPainter", "drawImage", "drawLine", "ImageDraw"):
            assert prohibido not in fuente


# ---------------------------------------------------------------------
# R13/R15 -- "Actividad medida", [Ci], y dos discrepancias con signo.
# ---------------------------------------------------------------------
class TestR13R15ResultadosActividad:
    RESULTADO = {'Ks': 1.0, 'Kp': 1.0, 'Ktp': 1.184, 'actividad_monitor': 9.541,
                 'actividad_calculada': 9.65, 'actividad_decaimiento': 9.509}

    def test_actividad_calculada_ahora_dice_medida(self, app):
        texto = _crear_tabla_resultados_actividad([self.RESULTADO]).to_string()
        assert "Actividad medida [Ci]" in texto
        assert "Actividad calculada" not in texto

    def test_las_tres_actividades_estan_en_ci_no_u_ni_gbq(self, app):
        texto = _crear_tabla_resultados_actividad([self.RESULTADO]).to_string()
        assert "Actividad en el monitor [Ci]" in texto
        assert "Actividad por decaimiento [Ci]" in texto
        assert "(U)" not in texto
        assert "(GBq)" not in texto

    def test_factores_de_correccion_son_adimensionales(self, app):
        texto = _crear_tabla_resultados_actividad([self.RESULTADO]).to_string()
        assert "(Ks) [1]" in texto
        assert "(Kp) [1]" in texto
        assert "(Ktp) [1]" in texto

    def test_dos_discrepancias_cada_una_dice_contra_quien(self, app):
        texto = _crear_tabla_resultados_actividad([self.RESULTADO]).to_string()
        assert "Discrepancia (medida - monitor) / monitor [%]" in texto
        assert "Discrepancia (medida - decaimiento) / decaimiento [%]" in texto

    def test_discrepancia_lleva_signo_no_abs(self, app):
        """Rojo-antes-que-verde: `medida < monitor` debe dar NEGATIVO --
        antes `abs()` lo hacía siempre positivo."""
        resultado = dict(self.RESULTADO, actividad_calculada=8.0,
                          actividad_monitor=9.541)
        texto = _crear_tabla_resultados_actividad([resultado]).to_string()
        linea = [l for l in texto.splitlines() if "medida - monitor" in l][0]
        valor = float(linea.rsplit(None, 1)[-1])
        assert valor < 0

    def test_rojo_dirigido_sobre_los_dos_casos_reales_de_la_bd(self, app):
        """§0.9 del plan: `ref=25` y `ref=35` de `ResultadosActividad`
        (BD real del físico) -- la discrepancia contra el monitor las
        deja pasar (0.88 %, 1.03 %); la NUEVA, contra el decaimiento, las
        delata (-77.6 %, +152.4 %)."""
        ref25 = {'Ks': 1.0, 'Kp': 1.0, 'Ktp': 1.184, 'actividad_monitor': 5.088,
                  'actividad_calculada': 5.133, 'actividad_decaimiento': 22.907}
        texto = _crear_tabla_resultados_actividad([ref25]).to_string()
        linea = texto.splitlines()[-1]  # la fila "medida - decaimiento" es la última
        valor = float(linea.rsplit(None, 1)[-1])
        assert valor < -70  # el plan predijo -77.6 %

        ref35 = {'Ks': 1.0, 'Kp': 1.0, 'Ktp': 1.191, 'actividad_monitor': 8.227,
                  'actividad_calculada': 8.312, 'actividad_decaimiento': 3.293}
        texto35 = _crear_tabla_resultados_actividad([ref35]).to_string()
        linea35 = texto35.splitlines()[-1]
        valor35 = float(linea35.rsplit(None, 1)[-1])
        assert valor35 > 140  # el plan predijo +152.4 %

    def test_monitor_cero_da_na_sin_excepcion(self, app):
        resultado = dict(self.RESULTADO, actividad_monitor=0)
        # No debe lanzar excepción -- ZeroDivisionError cubierto.
        texto = _crear_tabla_resultados_actividad([resultado]).to_string()
        assert "N/A" in texto

    def test_la_base_no_se_toca_solo_es_una_vista(self, app):
        """R15: 'por ahora solo en el pdf... no incluir este valor
        directamente almacenado en la BD'. La función es pura: recibe un
        dict y devuelve un DataFrame, no escribe nada."""
        entrada = dict(self.RESULTADO)
        _crear_tabla_resultados_actividad([entrada])
        assert entrada == self.RESULTADO  # el dict de entrada no se mutó


# ---------------------------------------------------------------------
# C4 -- reportes fuera de alcance de la Fase C: el anual usa una función
# de dosimetría DISTINTA (misma nombre, módulo distinto) y no debe verse
# afectado (§2.4 del plan).
# ---------------------------------------------------------------------
class TestC4NoAlcanzaElReporteAnual:
    def test_dosimetria_anual_es_una_funcion_distinta_sin_tolerancia(self):
        import models.PDF.Anual.reportes_anuales as anual_mod
        import inspect
        fuente_anual = inspect.getsource(anual_mod._crear_tabla_dosimetria)
        # La del anual toma un solo argumento (no `umbrales`) -- prueba de
        # que R14 (que exige el parámetro `umbrales`) no la tocó.
        firma = inspect.signature(anual_mod._crear_tabla_dosimetria)
        assert list(firma.parameters) == ['dosimetria_data']
        assert "_no_aplica_si_vacio" not in fuente_anual
