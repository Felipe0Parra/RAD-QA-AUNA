"""R4/R9 (PLAN_REPORTES_LEGIBLES_08-09.md): unidades de los reportes PDF,
declaradas en UN SOLO SITIO para que diario y mensual la compartan. Antes
cada generador de PDF mostraba el número crudo de la base de datos sin
decir en qué unidad estaba (`tol_rep_act_ci = 6` y `laseres = 1` se leían
igual siendo Ci y mm).

Tres categorías, todas decisiones del físico (08-09, 09-09) -- ninguna es
un valor "por defecto" que el código eligió:

- **con unidad real** (`UNIDADES`): la etiqueta lleva `[unidad]` junto al
  identificador de la fila. Los valores de aceleradores y braqui copian
  el formato oficial `IDC-F-RT-119` donde existe (mensual) o quedan
  confirmados por el físico (diario, §4.1-bis del plan).
- **adimensional declarado** (`ADIMENSIONALES`): la razón/cociente no
  tiene dimensión y el físico fijó cómo se escribe -- `[1]` (08-09:
  *"si la unidad es adimensional... se pone [1]"*), NUNCA vacío, para
  que no se confunda con "nadie decidió".
- **sin fuente conocida** (`SIN_FUENTE`): Halcyon. *"No inventemos
  nada"* (físico, 09-09) -- no hay ningún documento en el proyecto que
  diga si sus métricas MPC son mm o %. Se declara la falta de fuente;
  no se imprime ningún corchete. Deuda con nombre, no un olvido.

`unidad_de(campo)` es la única función que los generadores de PDF deben
llamar. Devuelve la cadena a anexar (p. ej. `" [mm]"`) o `""` si el campo
no lleva corchete (booleanos, o `SIN_FUENTE`).
"""

CORCHETE_ADIMENSIONAL = "[1]"

# Campo de BD -> unidad, SIN corchetes (unidad_de() los añade).
UNIDADES = {
    # --- Diario 600 ---
    "laseres": "mm",
    "telemetro": "mm",
    "tamano_campo": "mm",
    "centrado_reticulo": "mm",
    "dosis_referencia": "%",  # 600: es discrepancia respecto al valor teórico, no dosis (§4.1-bis)

    # --- Diario iX (mismos 4 mecánicos + consistencia de dosis por energía) ---
    "tol_fot_6mv": "%",
    "tol_fot_15mv": "%",
    "tol_ele_6mev": "%",
    "tol_ele_9mev": "%",
    "tol_ele_12mev": "%",
    "tol_ele_15mev": "%",

    # --- Diario braqui ---
    "tol_rep_act_ci": "Ci",
    "tol_exp_act": "Ci",

    # --- Análisis de placa de braqui, tabla aparte (R6) ---
    "promedio": "mm",
    "desviacion": "mm",

    # --- Mensual: aspectos mecánicos (formato oficial IDC-F-RT-119) ---
    "iso_mec": "mm",              # "Diámetro (mm)"
    "reticulo_cent": "mm",        # "Desplazamiento (mm)"
    "bordes_coin": "mm",          # R10 -- mismo formato, medida de coincidencia
    "camilla_vert_rango": "cm",   # "Rango (cm)"
    "camilla_vert_desp": "mm",    # desplazamiento, mismo patrón que camilla_iso_desp
    "camilla_iso_desp": "mm",
    "telem_rango": "cm",          # "Rango (cm)"
    "telem_desp": "mm",           # desplazamiento, mismo patrón que camp_luz_desp
    "camp_luz_desp": "mm",        # R10
    "puntero_telem_diff": "mm",   # "Diferencia (mm)"
    "laser_techo": "mm",
    "laser_lateral27": "mm",
    "laser_lateral9": "mm",

    # --- Mensual: dosimetría (600/iX) ---
    "dosis_ref_cgy_um": "Gy/UM",  # hoy dice "(cGy/UM)": erra por 100 -- el valor guardado YA está en Gy/UM
    "discrepancia_dosis": "%",
    "simetria_inplane": "%",
    "simetria_crossplane": "%",
    "discrepancia_calidad": "%",
    "planicidad_inplane": "%",
    "planicidad_crossplane": "%",

    # --- Mensual braqui: actividades (R13) ---
    "actividad_monitor": "Ci",
    "actividad_calculada": "Ci",
    "actividad_decaimiento": "Ci",
}

# Campos con unidad adimensional declarada -- SIEMPRE "[1]", nunca vacío.
ADIMENSIONALES = {
    # --- Diario braqui: conteos de ciclos ---
    "tol_cyc_dummy",
    "tol_cyc_rad",

    # --- Mensual: calidad de haz (PDD20/10, J2/J1) ---
    "calidad_pdd20_10",
    "calidad_j2_j1",

    # --- Mensual braqui: factores de corrección (cocientes) ---
    "Ks",
    "Kp",
    "Ktp",
}

# Campos SIN fuente de unidad conocida -- Halcyon. Deuda con nombre
# (DP-90/§4.4-1 de PLAN_REPORTES_LEGIBLES_08-09.md): el día que exista una
# fuente que la declare, se mueven a `UNIDADES` o `ADIMENSIONALES` y el
# test de cobertura de unidades_qc lo exige explícitamente.
SIN_FUENTE = {
    "IsoCenterSize_name2",
    "IsoCenterMVOffset",
    "IsoCenterKVOffset",
    "BeamOutputChange",
    "BeamUniformityChange",
    "BeamMu1GainChange",
    "BeamMu2GainChange",
    "GantryAbsolute",
    "GantryRelative",
    "CouchLat",
    "CouchLng",
    "CouchVrt",
    "CouchLatLong",
    "CouchLngLong",
    "CouchVrtLong",
    "VirtualToIsoLat",
    "VirtualToIsoLng",
    "VirtualToIsoVrt",
    "MVImagerCalibrationGain",
    "MVImagerCalibrationUniformity",
}


def unidad_de(campo):
    """Devuelve `" [unidad]"` (con el espacio inicial, listo para
    concatenar al identificador) o `""` si el campo no lleva corchete --
    booleano, `SIN_FUENTE`, o cualquier campo no declarado (id/fecha/
    usuario, que no son magnitudes)."""
    if campo in UNIDADES:
        return f" [{UNIDADES[campo]}]"
    if campo in ADIMENSIONALES:
        return f" {CORCHETE_ADIMENSIONAL}"
    return ""
