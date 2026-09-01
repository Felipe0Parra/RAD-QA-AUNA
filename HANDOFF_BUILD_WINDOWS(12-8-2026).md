# Revision Rebuild windows 12 de Agosto de 2026

- La tabla de conos no se guarda apropiadamente ni se restaura al abrir el control mensual, particularmente en el iX, que tan dificil es que se guarden normal, porque a veces se guardan solo unos valores de toda la tabla de seleccion Funciona/No funciona de esa seccion de conos, en la tabla que se abre desde la app se muestran 3 registros o 2 o los que sea, parece que esto depende de si realmente cambia el valor nuevo respecto al anterior y si no no lo guarda.
- Porque luego de recargar un control mensual no me deja desplegar el menu completo de equipos en la seleccion de camara primaria, secundaria, camara principal de electrones y electrometro en la priemra seccion del formulario mensual en la seccion "Equipos". Si sigue dejando elegir cualquier serie, pero no deja escoger un equipo diferente luego de haberlo recargado/reabierto y reactivado. 


- Expulsion de la terminal:

E10: sqlite_sequence normalizada para tabla_factor_campo (duplicados -> seq=168)
E10: sqlite_sequence normalizada para tabla_factores_sobre_eje (duplicados -> seq=207)
E10: sqlite_sequence normalizada para tabla_factores_transmision (duplicados -> seq=140)
E10: sqlite_sequence normalizada para uniformidad_ruido (duplicados -> seq=130)
E10: sqlite_sequence normalizada para users (duplicados -> seq=13)
E10: sqlite_sequence normalizada para valores_ct (duplicados -> seq=189)
F1: 58 tablas con borrado en cascada -- respaldando antes de recrear el esquema en RESTRICT...
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-12\respaldos_bd\pre_migracion\BaseDatosQA_2026-08-12_094909.db
E10: migrando 58 tablas a ON DELETE RESTRICT...
integrity_check después: ok

--- Cambios de esquema ---
  Tablas nuevas creadas: ['angulos_entre_lineas_starshot', 'audit_log']
  HC_desplazamiento_isocentro_mensual: columna(s) nueva(s) ['activo']
  HC_dosimetria_anual: columna(s) nueva(s) ['activo']
  HC_imagen_perfil_mlc_anual: columna(s) nueva(s) ['activo']
  HC_indicadores_brazo: columna(s) nueva(s) ['activo']
  HC_indicadores_camilla: columna(s) nueva(s) ['activo']
  HC_indicadores_colimador: columna(s) nueva(s) ['activo']
  HC_indicadores_laser: columna(s) nueva(s) ['activo']
  HC_linealidad_unidades_monitor_anual: columna(s) nueva(s) ['activo']
  HC_precision_posicion_multilaminas_anual: columna(s) nueva(s) ['activo']
  HC_tamanos_campo_radiacion: columna(s) nueva(s) ['activo']
  HC_velocidad_multilaminas_anual: columna(s) nueva(s) ['activo']
  LinealidadBraquiterapia: columna(s) nueva(s) ['activo']
  TipoCalibracion: columna(s) nueva(s) ['activo']
  aceleradorlineal_600: columna(s) nueva(s) ['activo']
  aceleradorlineal_ix: columna(s) nueva(s) ['activo']
  analisis_placa_franjas: columna(s) nueva(s) ['activo']
  braqui: columna(s) nueva(s) ['activo']
  calculadora_dosimetrica: columna(s) nueva(s) ['energia', 'pdd_zref_electrones', 'protocolo_trs398', 'r50_medido', 'tension_negativa', 'tpr2010', 'vigente']
  control_conos: columna(s) nueva(s) ['activo']
  control_cunas: columna(s) nueva(s) ['activo']
  controles: columna(s) nueva(s) ['activo']
  dosimetriaMen: columna(s) nueva(s) ['activo']
  equipos_medicion: columna(s) nueva(s) ['activo', 'equipo_id']
  halcyon: columna(s) nueva(s) ['activo']
  tabla_control_camaras_monitoras: columna(s) nueva(s) ['activo']
  tabla_factor_campo: columna(s) nueva(s) ['activo']
  tabla_factores_sobre_eje: columna(s) nueva(s) ['activo']
  tabla_factores_transmision: columna(s) nueva(s) ['activo']
  tamano_campo: columna(s) nueva(s) ['activo']
  users: columna(s) nueva(s) ['rol_sistema']

--- Normalización de datos (X1) ---
  Filas con el centinela histórico de 2º físico (' ---- '): 7 encontradas, 7 normalizadas a NULL

--- Catálogos base (prerrequisito de foreign_keys=ON) ---
  (los 4 catálogos ya estaban sembrados -- sin cambios)

--- Saneamiento del catálogo de equipos (certificados H2.6/H2.10) ---
  corregidas en esta corrida: 31 fila(s)
    id=26: Unificar TN34001->N34001 (misma camara fisica que serie 1069, ver certificado ADW43146); queda historico
    id=27: Unificar TN31022->N31022 (misma camara fisica que serie 152342, ver certificado ADW43144); queda historico
    id=13: N30013 vigente: t_cal/p_cal tenian las condiciones AMBIENTALES del certificado (20.9C/98.91kPa) en vez de las de REFERENCIA (22C/101.325kPa, ver Comments del certificado ADW39862) -- error de ~2% en kTP
    id=7: N31014 vigente: mismo error que id13 (certificado ADW39861) -- t_cal/p_cal ambientales en vez de referencia -- error de ~2% en kTP
    id=69: Normalizar formato de fecha (5/02/2024 -> 05/02/2024), fila historica N31010/1825 2024
    id=70: Normalizar formato de fecha, fila historica N34001/2426
    id=16: Pozo A972662 vigente: coeficiente de calibracion tenia 46670 (factor 10 de menos); certificado HDR12115 reporta 4.667e5 = 466700. Solo campo de referencia visual (no se lee en ninguna formula), sin impacto dosimetrico vivo -- corregido por higiene/legibilidad para el fisico
    id=71: Duplicado erroneo de id16 (mismo evento, año transcrito mal como 2025 y escala 4.667 en vez de 466700) -- queda historico
    id=58: Duplicado exacto de id77 (pozo A092535, mismo certificado HDR12899) -- queda historico
    id=57: Duplicado de id77 con escala incorrecta (46470 en vez de 464700) -- queda historico
    id=63: Duplicado de id77 con escala incorrecta (4.647 en vez de 464700) -- queda historico
    id=54: Pozo 'A132690 Somer': equipo prestado, ya devuelto (confirmado por el fisico 2026-07-16) -- retirado del catalogo activo
    id=55: Pozo 'A132690 Somer': idem id54
    id=56: Pozo 'A132690 Somer': idem id54 (esta fila ademas tenia p_cal=760, mezcla mmHg/kPa -- ya no importa al quedar retirada, no se corrige un valor de un equipo que ya no esta en servicio)
    id=64: Duplicado exacto de id81 (N31010/1822) -- queda historico
    id=65: Duplicado exacto de id80 (N34001/1069) -- queda historico
    id=59: Duplicado exacto de id78 (N31022/152342) -- queda historico
    id=60: Duplicado exacto de id78 (N31022/152342) -- queda historico
    id=61: Duplicado exacto de id78 (N31022/152342) -- queda historico
    id=62: Duplicado exacto de id78 (N31022/152342) -- queda historico
    id=75: Duplicado exacto de id79 (electrometro CDX-2000B, recalibracion 2026) -- queda historico
    id=16: (H2.10) Pozo A972662 vigente: t_cal/p_cal tenian las condiciones AMBIENTALES (21.4C/98.52kPa) en vez de las de REFERENCIA (22C/101.325kPa, ver certificado HDR12115) -- mismo bug que id13/id7, hallado al investigar por que A972662 desaparecio del selector de braquiterapia tras H2.6
    id=18: (H2.10) Electrometro CDX-2000B/B091982: fila vieja (05/02/2024) seguia vigente=1 a la vez que la recalibracion id79 (17/03/2026, tambien vigente=1) -- dos vigentes simultaneas para la misma serie; queda historica
    id=13: (G9) N30013 vigente: v1 (voltaje de electrodo colector) sin registrar; certificado ADW39862 declara 'Collecting Electrode Bias: +300 V'
    id=13: (G9) N30013 vigente: h_cal=33 es la humedad AMBIENTAL del dia de calibracion (certificado ADW39862, 'Environmental Conditions') -- se asume 50% como humedad de REFERENCIA. SUPUESTO DE TRABAJO (DA-27): el certificado ADCL no declara humedad de referencia, esto NO es una lectura del documento
    id=7: (G9) N31014 vigente: v1 sin registrar; certificado ADW39861 declara 'Collecting Electrode Bias: +300 V'
    id=7: (G9) N31014 vigente: h_cal=33 es la humedad AMBIENTAL del certificado ADW39861. SUPUESTO DE TRABAJO (DA-27): se asume 50% de referencia, no es una lectura del certificado
    id=16: (G9) Pozo A972662 vigente: v1 sin registrar; certificado HDR12115 declara 'Collecting Electrode Bias: +300 V'
    id=16: (G9) Pozo A972662 vigente: h_cal=38 es la humedad AMBIENTAL del certificado HDR12115. SUPUESTO DE TRABAJO (DA-27): se asume 50% de referencia, no es una lectura del certificado
    id=57: (G7, DA-23) Fecha con mes y dia invertidos ('7/28/2025', QDate invalido) -- certificado HDR12899 confirma 'Calibration Completed: 28/JUL/2025' -> 28 de julio de 2025
    id=58: (G7, DA-23) Fecha con mes y dia invertidos, misma correccion que id57 (certificado HDR12899)

--- Cambios estructurales ---
  Tablas migradas de borrado en cascada a RESTRICT: 58
    CondicionesMedicion
    HC_desplazamiento_isocentro_mensual
    HC_dosimetria_anual
    HC_fantomas
    HC_imagen_perfil_mlc_anual
    HC_indicadores_brazo
    HC_indicadores_camilla
    HC_indicadores_colimador
    HC_indicadores_laser
    HC_linealidad_unidades_monitor_anual
    HC_precision_posicion_multilaminas_anual
    HC_tamanos_campo_radiacion
    HC_velocidad_multilaminas_anual
    LecturasMaximos
    MaximosCamaras
    ResultadosActividad
    SistemaMedicion
    aceleradorlineal_600
    aceleradorlineal_ix
    analisis_placa_correcciones
    analisis_placa_franjas
    analisis_placa_verificaciones
    angulo_starshot
    braqui
    configuracion_picketfence
    configuracion_starshot
    control_conos
    control_cunas
    controles
    dosimetriaMen
    equipos_anual
    equipos_medicion
    error_picket
    espesor_corte
    estadisticas_starshot
    halcyon
    highest_leaf_errors
    indicadores_angulares_colimador
    indicadores_brazo
    leaf_error
    linealidad_ct
    posicionamiento_reposicionamiento
    preguntas
    pruebas
    resolucion_contraste
    resolucion_contraste_rois
    resolucion_espacial
    resolucion_espacial_regiones
    tabla_control_camaras_monitoras
    tabla_factor_campo
    tabla_factores_sobre_eje
    tabla_factores_transmision
    tamano_campo
    tamaño_pixel
    uniformidad_angular_starshot
    uniformidad_global
    uniformidad_ruido
    valores_ct
  Triggers anti-borrado creados: ['trg_no_borrar_LinealidadBraquiterapia', 'trg_no_borrar_TipoCalibracion', 'trg_no_borrar_controles', 'trg_no_borrar_users']
  Roles de sistema asignados: {'admin': 1, 'fisico': 5, 'jefe': 1}
  Filas duplicadas de sqlite_sequence normalizadas: 35 tabla(s)
  Índice único de controles: creado

--- Registros de QC preservados ---
  controles: 27 -> 27
  dosimetriaMen: 43 -> 43
  preguntas: 15 -> 15
  tamano_campo: 72 -> 72
  pruebas: 35 -> 35
  calculadora_dosimetrica: 1 -> 1
  Ningún registro de QC se perdió (la migración nunca borra filas).

--- Censo completo (69 tablas revisadas) ---
  Las 63 tablas restantes conservan sus conteos (ninguna perdió filas).

--- Duplicados de controles (unicidad DP-06) ---
  Ningún duplicado por (equipo, control, mes/año) entre las filas activas.

Listo. Backup de seguridad conservado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-12\BaseDatosQA.db.pre_migracion_20260812_094909.bak
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-12> $env:RADQA_HALCYON_MPC = "C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon"
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-12> python main.py
admin2025
ANTES ADD: btn_2_laseres False
CREADO: btn_2_laseres
ANTES ADD: btn_2_telemetro False
CREADO: btn_2_telemetro
ANTES ADD: btn_2_tamano_campo False
CREADO: btn_2_tamano_campo
ANTES ADD: line_2_centrado_reticulo False
CREADO: line_2_centrado_reticulo
ANTES ADD: line_2_dosis_referencia False
CREADO: line_2_dosis_referencia
ANTES ADD: observaciones False
CREADO: observaciones
Manteniendo columna ID

▥ Columnas detectadas: ['equip_type', 'model', 'serie', 'calibr_fact', 'calibr_fact2', 'fecha_calibr', 'fabricante', 't_cal', 'p_cal', 'h_cal', 'v1', 'activo', 'vigente', 'imagen_certificado'] para equipos

ANTES ADD: modelo False
CREADO: modelo
ANTES ADD: serie False
CREADO: serie
ANTES ADD: calib_factor False
CREADO: calib_factor
ANTES ADD: calib_factor2 False
CREADO: calib_factor2
ANTES ADD: fabricante False
CREADO: fabricante
ANTES ADD: t_cal False
CREADO: t_cal
ANTES ADD: p_cal False
CREADO: p_cal
ANTES ADD: h_cal False
CREADO: h_cal
ANTES ADD: v1_cal False
CREADO: v1_cal
super().__init__: 0.000s
dict_values(['luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla'])
initDATA: 0.001s
ANTES ADD: btn_2_laseres False
CREADO: btn_2_laseres
ANTES ADD: btn_2_telemetro False
CREADO: btn_2_telemetro
ANTES ADD: btn_2_tamano_campo False
CREADO: btn_2_tamano_campo
ANTES ADD: line_2_centrado_reticulo False
CREADO: line_2_centrado_reticulo
ANTES ADD: line_2_fot_6mv False
CREADO: line_2_fot_6mv
ANTES ADD: line_2_fot_15mv False
CREADO: line_2_fot_15mv
ANTES ADD: line_2_ele_6mev False
CREADO: line_2_ele_6mev
ANTES ADD: line_2_ele_9mev False
CREADO: line_2_ele_9mev
ANTES ADD: line_2_ele_12mev False
CREADO: line_2_ele_12mev
ANTES ADD: line_2_ele_15mev False
CREADO: line_2_ele_15mev
ANTES ADD: observaciones False
CREADO: observaciones
iniGUI: 0.024s
load table: 0.092s
asignar_encabezados: 0.095s
button_click: 0.095s
entro a la funcion de ordenacion
Entra a la función add_info en load.py con tabla: aceleradorlineal_ix
Manteniendo columna ID

▥ Columnas detectadas: ['date', 'user_id', 'luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla', 'laseres', 'telemetro', 'tamano_campo', 'centrado_reticulo', 'tol_fot_6mv', 'tol_fot_15mv', 'tol_ele_6mev', 'tol_ele_9mev', 'tol_ele_12mev', 'tol_ele_15mev', 'observaciones'] para aceleradorlineal_ix

entro a la funcion de ordenacion
Entra a la función add_info en load.py con tabla: aceleradorlineal_ix
Manteniendo columna ID

▥ Columnas detectadas: ['date', 'user_id', 'luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla', 'laseres', 'telemetro', 'tamano_campo', 'centrado_reticulo', 'tol_fot_6mv', 'tol_fot_15mv', 'tol_ele_6mev', 'tol_ele_9mev', 'tol_ele_12mev', 'tol_ele_15mev', 'observaciones'] para aceleradorlineal_ix

consultando db
2026-08-04
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado laseres: 1.5 en btn_2_laseres
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado telemetro: 0 en btn_2_telemetro
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado tamano_campo: 0 en btn_2_tamano_campo
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado centrado_reticulo: 0 en line_2_centrado_reticulo
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Datos del 2026-08-04 cargados correctamente.
  - Botones finales: 12
entro a la funcion de ordenacion
Entra a la función add_info en load.py con tabla: aceleradorlineal_ix
Manteniendo columna ID

▥ Columnas detectadas: ['date', 'user_id', 'luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla', 'laseres', 'telemetro', 'tamano_campo', 'centrado_reticulo', 'tol_fot_6mv', 'tol_fot_15mv', 'tol_ele_6mev', 'tol_ele_9mev', 'tol_ele_12mev', 'tol_ele_15mev', 'observaciones'] para aceleradorlineal_ix

Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001E2CC9F5410>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
user_id_f2 antes de create_control: 6
Entrando a crear control
Clinac ix
Cargando widgets desde hoja: preguntas_mensu_ix
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_princi_electrones False
CREADO: ln_fact_cam_princi_electrones
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
ANTES ADD: observaciones_segu False
CREADO: observaciones_segu
ANTES ADD: puntero_telem_diff False
CREADO: puntero_telem_diff
ANTES ADD: lbl_telem_rango False
CREADO: lbl_telem_rango
ANTES ADD: lbl_telem_desp False
CREADO: lbl_telem_desp
ANTES ADD: lbl_camilla_vert_rango False
CREADO: lbl_camilla_vert_rango
ANTES ADD: lbl_camilla_vert_desp False
CREADO: lbl_camilla_vert_desp
ANTES ADD: lbl_camilla_iso_desp False
CREADO: lbl_camilla_iso_desp
ANTES ADD: lbl_reticulo_cent False
CREADO: lbl_reticulo_cent
ANTES ADD: lbl_iso_mec False
CREADO: lbl_iso_mec
ANTES ADD: camp_luz_desp False
CREADO: camp_luz_desp
ANTES ADD: lbl_bordes_coin False
CREADO: lbl_bordes_coin
ANTES ADD: lbl_laser_techo False
CREADO: lbl_laser_techo
ANTES ADD: lbl_laser_lateral27 False
CREADO: lbl_laser_lateral27
ANTES ADD: lbl_laser_lateral9 False
CREADO: lbl_laser_lateral9
ANTES ADD: observaciones False
CREADO: observaciones
ANTES ADD: val_teo_6mv False
CREADO: val_teo_6mv
ANTES ADD: ln_dosis_ref_cgy_um_6mv False
CREADO: ln_dosis_ref_cgy_um_6mv
ANTES ADD: ln_discrepancia_dosis_6mv False
CREADO: ln_discrepancia_dosis_6mv
ANTES ADD: ln_calidad_pdd20_10_6mv False
CREADO: ln_calidad_pdd20_10_6mv
ANTES ADD: ln_discrepancia_calidad_6mv False
CREADO: ln_discrepancia_calidad_6mv
ANTES ADD: ln_simetria_inplane_6mv False
CREADO: ln_simetria_inplane_6mv
ANTES ADD: ln_simetria_crossplane_6mv False
CREADO: ln_simetria_crossplane_6mv
ANTES ADD: ln_planicidad_inplane_6mv False
CREADO: ln_planicidad_inplane_6mv
ANTES ADD: ln_planicidad_crossplane_6mv False
CREADO: ln_planicidad_crossplane_6mv
ANTES ADD: val_teo_15mv False
CREADO: val_teo_15mv
ANTES ADD: ln_dosis_ref_cgy_um_15mv False
CREADO: ln_dosis_ref_cgy_um_15mv
ANTES ADD: ln_discrepancia_dosis_15mv False
CREADO: ln_discrepancia_dosis_15mv
ANTES ADD: ln_calidad_pdd20_10_15mv False
CREADO: ln_calidad_pdd20_10_15mv
ANTES ADD: ln_discrepancia_calidad_15mv False
CREADO: ln_discrepancia_calidad_15mv
ANTES ADD: ln_simetria_inplane_15mv False
CREADO: ln_simetria_inplane_15mv
ANTES ADD: ln_simetria_crossplane_15mv False
CREADO: ln_simetria_crossplane_15mv
ANTES ADD: ln_planicidad_inplane_15mv False
CREADO: ln_planicidad_inplane_15mv
ANTES ADD: ln_planicidad_crossplane_15mv False
CREADO: ln_planicidad_crossplane_15mv
ANTES ADD: val_teo_6mev False
CREADO: val_teo_6mev
ANTES ADD: ln_dosis_ref_cgy_um_6mev False
CREADO: ln_dosis_ref_cgy_um_6mev
ANTES ADD: ln_discrepancia_dosis_6mev False
CREADO: ln_discrepancia_dosis_6mev
ANTES ADD: ln_calidad_j2_j1_6mev False
CREADO: ln_calidad_j2_j1_6mev
ANTES ADD: ln_discrepancia_calidad_6mev False
CREADO: ln_discrepancia_calidad_6mev
ANTES ADD: ln_simetria_inplane_6mev False
CREADO: ln_simetria_inplane_6mev
ANTES ADD: ln_simetria_crossplane_6mev False
CREADO: ln_simetria_crossplane_6mev
ANTES ADD: ln_planicidad_inplane_6mev False
CREADO: ln_planicidad_inplane_6mev
ANTES ADD: ln_planicidad_crossplane_6mev False
CREADO: ln_planicidad_crossplane_6mev
ANTES ADD: val_teo_9mev False
CREADO: val_teo_9mev
ANTES ADD: ln_dosis_ref_cgy_um_9mev False
CREADO: ln_dosis_ref_cgy_um_9mev
ANTES ADD: ln_discrepancia_dosis_9mev False
CREADO: ln_discrepancia_dosis_9mev
ANTES ADD: ln_calidad_j2_j1_9mev False
CREADO: ln_calidad_j2_j1_9mev
ANTES ADD: ln_discrepancia_calidad_9mev False
CREADO: ln_discrepancia_calidad_9mev
ANTES ADD: ln_simetria_inplane_9mev False
CREADO: ln_simetria_inplane_9mev
ANTES ADD: ln_simetria_crossplane_9mev False
CREADO: ln_simetria_crossplane_9mev
ANTES ADD: ln_planicidad_inplane_9mev False
CREADO: ln_planicidad_inplane_9mev
ANTES ADD: ln_planicidad_crossplane_9mev False
CREADO: ln_planicidad_crossplane_9mev
ANTES ADD: val_teo_12mev False
CREADO: val_teo_12mev
ANTES ADD: ln_dosis_ref_cgy_um_12mev False
CREADO: ln_dosis_ref_cgy_um_12mev
ANTES ADD: ln_discrepancia_dosis_12mev False
CREADO: ln_discrepancia_dosis_12mev
ANTES ADD: ln_calidad_j2_j1_12mev False
CREADO: ln_calidad_j2_j1_12mev
ANTES ADD: ln_discrepancia_calidad_12mev False
CREADO: ln_discrepancia_calidad_12mev
ANTES ADD: ln_simetria_inplane_12mev False
CREADO: ln_simetria_inplane_12mev
ANTES ADD: ln_simetria_crossplane_12mev False
CREADO: ln_simetria_crossplane_12mev
ANTES ADD: ln_planicidad_inplane_12mev False
CREADO: ln_planicidad_inplane_12mev
ANTES ADD: ln_planicidad_crossplane_12mev False
CREADO: ln_planicidad_crossplane_12mev
ANTES ADD: val_teo_15mev False
CREADO: val_teo_15mev
ANTES ADD: ln_dosis_ref_cgy_um_15mev False
CREADO: ln_dosis_ref_cgy_um_15mev
ANTES ADD: ln_discrepancia_dosis_15mev False
CREADO: ln_discrepancia_dosis_15mev
ANTES ADD: ln_calidad_j2_j1_15mev False
CREADO: ln_calidad_j2_j1_15mev
ANTES ADD: ln_discrepancia_calidad_15mev False
CREADO: ln_discrepancia_calidad_15mev
ANTES ADD: ln_simetria_inplane_15mev False
CREADO: ln_simetria_inplane_15mev
ANTES ADD: ln_simetria_crossplane_15mev False
CREADO: ln_simetria_crossplane_15mev
ANTES ADD: ln_planicidad_inplane_15mev False
CREADO: ln_planicidad_inplane_15mev
ANTES ADD: ln_planicidad_crossplane_15mev False
CREADO: ln_planicidad_crossplane_15mev
ANTES ADD: ln_observaciones_dosi False
CREADO: ln_observaciones_dosi
ANTES ADD: ln_tolerance_mlc False
CREADO: ln_tolerance_mlc
ANTES ADD: ln_action_tolerance False
CREADO: ln_action_tolerance
ANTES ADD: ln_tolerance_starshot False
CREADO: ln_tolerance_starshot
ANTES ADD: ln_sid_starshot False
CREADO: ln_sid_starshot
  - DataFrame: 289 filas
Layouts disponibles: 5
<PyQt5.QtWidgets.QGridLayout object at 0x000001E354394550>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E3543944C0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E354394670>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E3543945E0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E354394700>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
action tolerance encontrado
Widgets MLC encontrados y configurados
Insertando datos de equipos para IX
Insertados 4 registros de equipos correctamente
Actualizando tabla de controles mensuales para Clinac ix
Actualizando tabla de controles mensuales para Clinac ix

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000001E354397010>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

Se presionó btn_guardar_ix

Entra a subirlineasmensuales_ix de la clase PruebaMensualIX
Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Dialog llamado desde: PruebaMensualIX

Entra a subirlineasmensuales_ix de la clase PruebaMensualIX
Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen


Entra a subirlineasmensuales_ix de la clase PruebaMensualIX
Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Manteniendo columna ID

▥ Columnas detectadas: ['val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-12\respaldos_bd\BaseDatosQA_2026-08-12_095725.db
admin2025
ANTES ADD: btn_2_laseres False
CREADO: btn_2_laseres
ANTES ADD: btn_2_telemetro False
CREADO: btn_2_telemetro
ANTES ADD: btn_2_tamano_campo False
CREADO: btn_2_tamano_campo
ANTES ADD: line_2_centrado_reticulo False
CREADO: line_2_centrado_reticulo
ANTES ADD: line_2_dosis_referencia False
CREADO: line_2_dosis_referencia
ANTES ADD: observaciones False
CREADO: observaciones
Manteniendo columna ID

▥ Columnas detectadas: ['equip_type', 'model', 'serie', 'calibr_fact', 'calibr_fact2', 'fecha_calibr', 'fabricante', 't_cal', 'p_cal', 'h_cal', 'v1', 'activo', 'vigente', 'imagen_certificado'] para equipos

ANTES ADD: modelo False
CREADO: modelo
ANTES ADD: serie False
CREADO: serie
ANTES ADD: calib_factor False
CREADO: calib_factor
ANTES ADD: calib_factor2 False
CREADO: calib_factor2
ANTES ADD: fabricante False
CREADO: fabricante
ANTES ADD: t_cal False
CREADO: t_cal
ANTES ADD: p_cal False
CREADO: p_cal
ANTES ADD: h_cal False
CREADO: h_cal
ANTES ADD: v1_cal False
CREADO: v1_cal
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001E3544BC590>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Equipo seleccionado para reporte 
Tomógrafo
Equipo seleccionado para reporte 
Tomógrafo
Equipo seleccionado para reporte 
Tomógrafo
Equipo seleccionado para reporte 
Tomógrafo
Equipo seleccionado para reporte 
Tomógrafo
Equipo seleccionado para reporte 
Tomógrafo
ANTES ADD: line_1_rep_act_ci False
CREADO: line_1_rep_act_ci
ANTES ADD: line_1_exp_act_ci False
CREADO: line_1_exp_act_ci
ANTES ADD: line_1_cyc_dummy False
CREADO: line_1_cyc_dummy
ANTES ADD: line_1_cyc_rad False
CREADO: line_1_cyc_rad
ANTES ADD: observaciones False
CREADO: observaciones
Botón subir sin datos
13.65
Fecha Inicio CET: 2026-06-05 11:36:24+02:00 (Fecha del certificado)
Fecha Inicio convertido a COT: 2026-06-05 04:36:24-05:00
Fecha Final COT: 2026-08-12 09:57:34-05:00
Horas transcurridas desde 2026-08-12 09:57:34: 1637.3527777777779
Dias transcurridos: 68.22303240740742
 La actividad es:  7.1939
super().__init__: 0.000s
dict_values(['luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla'])
initDATA: 0.001s
ANTES ADD: btn_2_laseres False
CREADO: btn_2_laseres
ANTES ADD: btn_2_telemetro False
CREADO: btn_2_telemetro
ANTES ADD: btn_2_tamano_campo False
CREADO: btn_2_tamano_campo
ANTES ADD: line_2_centrado_reticulo False
CREADO: line_2_centrado_reticulo
ANTES ADD: line_2_fot_6mv False
CREADO: line_2_fot_6mv
ANTES ADD: line_2_fot_15mv False
CREADO: line_2_fot_15mv
ANTES ADD: line_2_ele_6mev False
CREADO: line_2_ele_6mev
ANTES ADD: line_2_ele_9mev False
CREADO: line_2_ele_9mev
ANTES ADD: line_2_ele_12mev False
CREADO: line_2_ele_12mev
ANTES ADD: line_2_ele_15mev False
CREADO: line_2_ele_15mev
ANTES ADD: observaciones False
CREADO: observaciones
iniGUI: 0.020s
load table: 0.088s
asignar_encabezados: 0.091s
button_click: 0.091s
consultando db
2026-08-04
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado laseres: 1.5 en btn_2_laseres
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado telemetro: 0 en btn_2_telemetro
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado tamano_campo: 0 en btn_2_tamano_campo
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado centrado_reticulo: 0 en line_2_centrado_reticulo
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargadas observaciones
✓ Datos del 2026-08-04 cargados correctamente.
  - Botones finales: 12
consultando db
2026-08-12
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado laseres: 1 en btn_2_laseres
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado telemetro: 1 en btn_2_telemetro
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado tamano_campo: 1 en btn_2_tamano_campo
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado centrado_reticulo: 1 en line_2_centrado_reticulo
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargadas observaciones
✓ Datos del 2026-08-12 cargados correctamente.
  - Botones finales: 12
Limpiando data
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001E3544BC590>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
user_id_f2 antes de create_control: 6
Entrando a crear control
Clinac ix
Cargando widgets desde hoja: preguntas_mensu_ix
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_princi_electrones False
CREADO: ln_fact_cam_princi_electrones
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
ANTES ADD: observaciones_segu False
CREADO: observaciones_segu
ANTES ADD: puntero_telem_diff False
CREADO: puntero_telem_diff
ANTES ADD: lbl_telem_rango False
CREADO: lbl_telem_rango
ANTES ADD: lbl_telem_desp False
CREADO: lbl_telem_desp
ANTES ADD: lbl_camilla_vert_rango False
CREADO: lbl_camilla_vert_rango
ANTES ADD: lbl_camilla_vert_desp False
CREADO: lbl_camilla_vert_desp
ANTES ADD: lbl_camilla_iso_desp False
CREADO: lbl_camilla_iso_desp
ANTES ADD: lbl_reticulo_cent False
CREADO: lbl_reticulo_cent
ANTES ADD: lbl_iso_mec False
CREADO: lbl_iso_mec
ANTES ADD: camp_luz_desp False
CREADO: camp_luz_desp
ANTES ADD: lbl_bordes_coin False
CREADO: lbl_bordes_coin
ANTES ADD: lbl_laser_techo False
CREADO: lbl_laser_techo
ANTES ADD: lbl_laser_lateral27 False
CREADO: lbl_laser_lateral27
ANTES ADD: lbl_laser_lateral9 False
CREADO: lbl_laser_lateral9
ANTES ADD: observaciones False
CREADO: observaciones
ANTES ADD: val_teo_6mv False
CREADO: val_teo_6mv
ANTES ADD: ln_dosis_ref_cgy_um_6mv False
CREADO: ln_dosis_ref_cgy_um_6mv
ANTES ADD: ln_discrepancia_dosis_6mv False
CREADO: ln_discrepancia_dosis_6mv
ANTES ADD: ln_calidad_pdd20_10_6mv False
CREADO: ln_calidad_pdd20_10_6mv
ANTES ADD: ln_discrepancia_calidad_6mv False
CREADO: ln_discrepancia_calidad_6mv
ANTES ADD: ln_simetria_inplane_6mv False
CREADO: ln_simetria_inplane_6mv
ANTES ADD: ln_simetria_crossplane_6mv False
CREADO: ln_simetria_crossplane_6mv
ANTES ADD: ln_planicidad_inplane_6mv False
CREADO: ln_planicidad_inplane_6mv
ANTES ADD: ln_planicidad_crossplane_6mv False
CREADO: ln_planicidad_crossplane_6mv
ANTES ADD: val_teo_15mv False
CREADO: val_teo_15mv
ANTES ADD: ln_dosis_ref_cgy_um_15mv False
CREADO: ln_dosis_ref_cgy_um_15mv
ANTES ADD: ln_discrepancia_dosis_15mv False
CREADO: ln_discrepancia_dosis_15mv
ANTES ADD: ln_calidad_pdd20_10_15mv False
CREADO: ln_calidad_pdd20_10_15mv
ANTES ADD: ln_discrepancia_calidad_15mv False
CREADO: ln_discrepancia_calidad_15mv
ANTES ADD: ln_simetria_inplane_15mv False
CREADO: ln_simetria_inplane_15mv
ANTES ADD: ln_simetria_crossplane_15mv False
CREADO: ln_simetria_crossplane_15mv
ANTES ADD: ln_planicidad_inplane_15mv False
CREADO: ln_planicidad_inplane_15mv
ANTES ADD: ln_planicidad_crossplane_15mv False
CREADO: ln_planicidad_crossplane_15mv
ANTES ADD: val_teo_6mev False
CREADO: val_teo_6mev
ANTES ADD: ln_dosis_ref_cgy_um_6mev False
CREADO: ln_dosis_ref_cgy_um_6mev
ANTES ADD: ln_discrepancia_dosis_6mev False
CREADO: ln_discrepancia_dosis_6mev
ANTES ADD: ln_calidad_j2_j1_6mev False
CREADO: ln_calidad_j2_j1_6mev
ANTES ADD: ln_discrepancia_calidad_6mev False
CREADO: ln_discrepancia_calidad_6mev
ANTES ADD: ln_simetria_inplane_6mev False
CREADO: ln_simetria_inplane_6mev
ANTES ADD: ln_simetria_crossplane_6mev False
CREADO: ln_simetria_crossplane_6mev
ANTES ADD: ln_planicidad_inplane_6mev False
CREADO: ln_planicidad_inplane_6mev
ANTES ADD: ln_planicidad_crossplane_6mev False
CREADO: ln_planicidad_crossplane_6mev
ANTES ADD: val_teo_9mev False
CREADO: val_teo_9mev
ANTES ADD: ln_dosis_ref_cgy_um_9mev False
CREADO: ln_dosis_ref_cgy_um_9mev
ANTES ADD: ln_discrepancia_dosis_9mev False
CREADO: ln_discrepancia_dosis_9mev
ANTES ADD: ln_calidad_j2_j1_9mev False
CREADO: ln_calidad_j2_j1_9mev
ANTES ADD: ln_discrepancia_calidad_9mev False
CREADO: ln_discrepancia_calidad_9mev
ANTES ADD: ln_simetria_inplane_9mev False
CREADO: ln_simetria_inplane_9mev
ANTES ADD: ln_simetria_crossplane_9mev False
CREADO: ln_simetria_crossplane_9mev
ANTES ADD: ln_planicidad_inplane_9mev False
CREADO: ln_planicidad_inplane_9mev
ANTES ADD: ln_planicidad_crossplane_9mev False
CREADO: ln_planicidad_crossplane_9mev
ANTES ADD: val_teo_12mev False
CREADO: val_teo_12mev
ANTES ADD: ln_dosis_ref_cgy_um_12mev False
CREADO: ln_dosis_ref_cgy_um_12mev
ANTES ADD: ln_discrepancia_dosis_12mev False
CREADO: ln_discrepancia_dosis_12mev
ANTES ADD: ln_calidad_j2_j1_12mev False
CREADO: ln_calidad_j2_j1_12mev
ANTES ADD: ln_discrepancia_calidad_12mev False
CREADO: ln_discrepancia_calidad_12mev
ANTES ADD: ln_simetria_inplane_12mev False
CREADO: ln_simetria_inplane_12mev
ANTES ADD: ln_simetria_crossplane_12mev False
CREADO: ln_simetria_crossplane_12mev
ANTES ADD: ln_planicidad_inplane_12mev False
CREADO: ln_planicidad_inplane_12mev
ANTES ADD: ln_planicidad_crossplane_12mev False
CREADO: ln_planicidad_crossplane_12mev
ANTES ADD: val_teo_15mev False
CREADO: val_teo_15mev
ANTES ADD: ln_dosis_ref_cgy_um_15mev False
CREADO: ln_dosis_ref_cgy_um_15mev
ANTES ADD: ln_discrepancia_dosis_15mev False
CREADO: ln_discrepancia_dosis_15mev
ANTES ADD: ln_calidad_j2_j1_15mev False
CREADO: ln_calidad_j2_j1_15mev
ANTES ADD: ln_discrepancia_calidad_15mev False
CREADO: ln_discrepancia_calidad_15mev
ANTES ADD: ln_simetria_inplane_15mev False
CREADO: ln_simetria_inplane_15mev
ANTES ADD: ln_simetria_crossplane_15mev False
CREADO: ln_simetria_crossplane_15mev
ANTES ADD: ln_planicidad_inplane_15mev False
CREADO: ln_planicidad_inplane_15mev
ANTES ADD: ln_planicidad_crossplane_15mev False
CREADO: ln_planicidad_crossplane_15mev
ANTES ADD: ln_observaciones_dosi False
CREADO: ln_observaciones_dosi
ANTES ADD: ln_tolerance_mlc False
CREADO: ln_tolerance_mlc
ANTES ADD: ln_action_tolerance False
CREADO: ln_action_tolerance
ANTES ADD: ln_tolerance_starshot False
CREADO: ln_tolerance_starshot
ANTES ADD: ln_sid_starshot False
CREADO: ln_sid_starshot
  - DataFrame: 289 filas
Layouts disponibles: 5
<PyQt5.QtWidgets.QGridLayout object at 0x000001E31918DCF0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E31918CDC0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E31918EC20>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E31918FB50>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E319194AF0>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
action tolerance encontrado
Widgets MLC encontrados y configurados

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000001E3191E3B50>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

Se presionó btn_guardar_ix

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000001E3191E3B50>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

Se presionó btn_guardar_ix

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000001E3191E3B50>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

Se presionó btn_guardar_ix

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000001E3191E3B50>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

Se presionó btn_guardar_ix

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000001E3191E3B50>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

Se presionó btn_guardar_ix
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025
→ Eliminando en tabla controles, WHERE "id" = ?, valores [42]
UPDATE (anular) ejecutado correctamente
Fin de eliminarRegistro

Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-12\respaldos_bd\BaseDatosQA_2026-08-12_100758.db
admin2025
ANTES ADD: btn_2_laseres False
CREADO: btn_2_laseres
ANTES ADD: btn_2_telemetro False
CREADO: btn_2_telemetro
ANTES ADD: btn_2_tamano_campo False
CREADO: btn_2_tamano_campo
ANTES ADD: line_2_centrado_reticulo False
CREADO: line_2_centrado_reticulo
ANTES ADD: line_2_dosis_referencia False
CREADO: line_2_dosis_referencia
ANTES ADD: observaciones False
CREADO: observaciones

CREADO: ln_simetria_crossplane_15mev
ANTES ADD: ln_planicidad_inplane_15mev False
CREADO: ln_planicidad_inplane_15mev
ANTES ADD: ln_planicidad_crossplane_15mev False
CREADO: ln_planicidad_crossplane_15mev
ANTES ADD: ln_observaciones_dosi False
CREADO: ln_observaciones_dosi
ANTES ADD: ln_tolerance_mlc False
CREADO: ln_tolerance_mlc
ANTES ADD: ln_action_tolerance False
CREADO: ln_action_tolerance
ANTES ADD: ln_tolerance_starshot False
CREADO: ln_tolerance_starshot
ANTES ADD: ln_sid_starshot False
CREADO: ln_sid_starshot
  - DataFrame: 289 filas
Layouts disponibles: 5
<PyQt5.QtWidgets.QGridLayout object at 0x000001E3544A8790>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E3544A8820>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E3544A8670>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E3544A85E0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E3544A8550>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
action tolerance encontrado
Widgets MLC encontrados y configurados
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-12\respaldos_bd\BaseDatosQA_2026-08-12_101019.db
admin2025
ANTES ADD: btn_2_laseres False
CREADO: btn_2_laseres
ANTES ADD: btn_2_telemetro False
CREADO: btn_2_telemetro
ANTES ADD: btn_2_tamano_campo False
CREADO: btn_2_tamano_campo
ANTES ADD: line_2_centrado_reticulo False
CREADO: line_2_centrado_reticulo
ANTES ADD: line_2_dosis_referencia False
CREADO: line_2_dosis_referencia
ANTES ADD: observaciones False
CREADO: observaciones
Clinac 600
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001E3188B3C90>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
super().__init__: 0.000s
dict_values(['luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla'])
initDATA: 0.001s
ANTES ADD: btn_2_laseres False
CREADO: btn_2_laseres
ANTES ADD: btn_2_telemetro False
CREADO: btn_2_telemetro
ANTES ADD: btn_2_tamano_campo False
CREADO: btn_2_tamano_campo
ANTES ADD: line_2_centrado_reticulo False
CREADO: line_2_centrado_reticulo
ANTES ADD: line_2_fot_6mv False
CREADO: line_2_fot_6mv
ANTES ADD: line_2_fot_15mv False
CREADO: line_2_fot_15mv
ANTES ADD: line_2_ele_6mev False
CREADO: line_2_ele_6mev
ANTES ADD: line_2_ele_9mev False
CREADO: line_2_ele_9mev
ANTES ADD: line_2_ele_12mev False
CREADO: line_2_ele_12mev
ANTES ADD: line_2_ele_15mev False
CREADO: line_2_ele_15mev
ANTES ADD: observaciones False
CREADO: observaciones
iniGUI: 0.022s
load table: 0.090s
asignar_encabezados: 0.093s
button_click: 0.093s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001E3188B3C90>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
user_id_f2 antes de create_control: 6
Entrando a crear control
Clinac ix
Cargando widgets desde hoja: preguntas_mensu_ix
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_princi_electrones False
CREADO: ln_fact_cam_princi_electrones
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
ANTES ADD: observaciones_segu False
CREADO: observaciones_segu
ANTES ADD: puntero_telem_diff False
CREADO: puntero_telem_diff
ANTES ADD: lbl_telem_rango False
CREADO: lbl_telem_rango
ANTES ADD: lbl_telem_desp False
CREADO: lbl_telem_desp
ANTES ADD: lbl_camilla_vert_rango False
CREADO: lbl_camilla_vert_rango
ANTES ADD: lbl_camilla_vert_desp False
CREADO: lbl_camilla_vert_desp
ANTES ADD: lbl_camilla_iso_desp False
CREADO: lbl_camilla_iso_desp
ANTES ADD: lbl_reticulo_cent False
CREADO: lbl_reticulo_cent
ANTES ADD: lbl_iso_mec False
CREADO: lbl_iso_mec
ANTES ADD: camp_luz_desp False
CREADO: camp_luz_desp
ANTES ADD: lbl_bordes_coin False
CREADO: lbl_bordes_coin
ANTES ADD: lbl_laser_techo False
CREADO: lbl_laser_techo
ANTES ADD: lbl_laser_lateral27 False
CREADO: lbl_laser_lateral27
ANTES ADD: lbl_laser_lateral9 False
CREADO: lbl_laser_lateral9
ANTES ADD: observaciones False
CREADO: observaciones
ANTES ADD: val_teo_6mv False
CREADO: val_teo_6mv
ANTES ADD: ln_dosis_ref_cgy_um_6mv False
CREADO: ln_dosis_ref_cgy_um_6mv
ANTES ADD: ln_discrepancia_dosis_6mv False
CREADO: ln_discrepancia_dosis_6mv
ANTES ADD: ln_calidad_pdd20_10_6mv False
CREADO: ln_calidad_pdd20_10_6mv
ANTES ADD: ln_discrepancia_calidad_6mv False
CREADO: ln_discrepancia_calidad_6mv
ANTES ADD: ln_simetria_inplane_6mv False
CREADO: ln_simetria_inplane_6mv
ANTES ADD: ln_simetria_crossplane_6mv False
CREADO: ln_simetria_crossplane_6mv
ANTES ADD: ln_planicidad_inplane_6mv False
CREADO: ln_planicidad_inplane_6mv
ANTES ADD: ln_planicidad_crossplane_6mv False
CREADO: ln_planicidad_crossplane_6mv
ANTES ADD: val_teo_15mv False
CREADO: val_teo_15mv
ANTES ADD: ln_dosis_ref_cgy_um_15mv False
CREADO: ln_dosis_ref_cgy_um_15mv
ANTES ADD: ln_discrepancia_dosis_15mv False
CREADO: ln_discrepancia_dosis_15mv
ANTES ADD: ln_calidad_pdd20_10_15mv False
CREADO: ln_calidad_pdd20_10_15mv
ANTES ADD: ln_discrepancia_calidad_15mv False
CREADO: ln_discrepancia_calidad_15mv
ANTES ADD: ln_simetria_inplane_15mv False
CREADO: ln_simetria_inplane_15mv
ANTES ADD: ln_simetria_crossplane_15mv False
CREADO: ln_simetria_crossplane_15mv
ANTES ADD: ln_planicidad_inplane_15mv False
CREADO: ln_planicidad_inplane_15mv
ANTES ADD: ln_planicidad_crossplane_15mv False
CREADO: ln_planicidad_crossplane_15mv
ANTES ADD: val_teo_6mev False
CREADO: val_teo_6mev
ANTES ADD: ln_dosis_ref_cgy_um_6mev False
CREADO: ln_dosis_ref_cgy_um_6mev
ANTES ADD: ln_discrepancia_dosis_6mev False
CREADO: ln_discrepancia_dosis_6mev
ANTES ADD: ln_calidad_j2_j1_6mev False
CREADO: ln_calidad_j2_j1_6mev
ANTES ADD: ln_discrepancia_calidad_6mev False
CREADO: ln_discrepancia_calidad_6mev
ANTES ADD: ln_simetria_inplane_6mev False
CREADO: ln_simetria_inplane_6mev
ANTES ADD: ln_simetria_crossplane_6mev False
CREADO: ln_simetria_crossplane_6mev
ANTES ADD: ln_planicidad_inplane_6mev False
CREADO: ln_planicidad_inplane_6mev
ANTES ADD: ln_planicidad_crossplane_6mev False
CREADO: ln_planicidad_crossplane_6mev
ANTES ADD: val_teo_9mev False
CREADO: val_teo_9mev
ANTES ADD: ln_dosis_ref_cgy_um_9mev False
CREADO: ln_dosis_ref_cgy_um_9mev
ANTES ADD: ln_discrepancia_dosis_9mev False
CREADO: ln_discrepancia_dosis_9mev
ANTES ADD: ln_calidad_j2_j1_9mev False
CREADO: ln_calidad_j2_j1_9mev
ANTES ADD: ln_discrepancia_calidad_9mev False
CREADO: ln_discrepancia_calidad_9mev
ANTES ADD: ln_simetria_inplane_9mev False
CREADO: ln_simetria_inplane_9mev
ANTES ADD: ln_simetria_crossplane_9mev False
CREADO: ln_simetria_crossplane_9mev
ANTES ADD: ln_planicidad_inplane_9mev False
CREADO: ln_planicidad_inplane_9mev
ANTES ADD: ln_planicidad_crossplane_9mev False
CREADO: ln_planicidad_crossplane_9mev
ANTES ADD: val_teo_12mev False
CREADO: val_teo_12mev
ANTES ADD: ln_dosis_ref_cgy_um_12mev False
CREADO: ln_dosis_ref_cgy_um_12mev
ANTES ADD: ln_discrepancia_dosis_12mev False
CREADO: ln_discrepancia_dosis_12mev
ANTES ADD: ln_calidad_j2_j1_12mev False
CREADO: ln_calidad_j2_j1_12mev
ANTES ADD: ln_discrepancia_calidad_12mev False
CREADO: ln_discrepancia_calidad_12mev
ANTES ADD: ln_simetria_inplane_12mev False
CREADO: ln_simetria_inplane_12mev
ANTES ADD: ln_simetria_crossplane_12mev False
CREADO: ln_simetria_crossplane_12mev
ANTES ADD: ln_planicidad_inplane_12mev False
CREADO: ln_planicidad_inplane_12mev
ANTES ADD: ln_planicidad_crossplane_12mev False
CREADO: ln_planicidad_crossplane_12mev
ANTES ADD: val_teo_15mev False
CREADO: val_teo_15mev
ANTES ADD: ln_dosis_ref_cgy_um_15mev False
CREADO: ln_dosis_ref_cgy_um_15mev
ANTES ADD: ln_discrepancia_dosis_15mev False
CREADO: ln_discrepancia_dosis_15mev
ANTES ADD: ln_calidad_j2_j1_15mev False
CREADO: ln_calidad_j2_j1_15mev
ANTES ADD: ln_discrepancia_calidad_15mev False
CREADO: ln_discrepancia_calidad_15mev
ANTES ADD: ln_simetria_inplane_15mev False
CREADO: ln_simetria_inplane_15mev
ANTES ADD: ln_simetria_crossplane_15mev False
CREADO: ln_simetria_crossplane_15mev
ANTES ADD: ln_planicidad_inplane_15mev False
CREADO: ln_planicidad_inplane_15mev
ANTES ADD: ln_planicidad_crossplane_15mev False
CREADO: ln_planicidad_crossplane_15mev
ANTES ADD: ln_observaciones_dosi False
CREADO: ln_observaciones_dosi
ANTES ADD: ln_tolerance_mlc False
CREADO: ln_tolerance_mlc
ANTES ADD: ln_action_tolerance False
CREADO: ln_action_tolerance
ANTES ADD: ln_tolerance_starshot False
CREADO: ln_tolerance_starshot
ANTES ADD: ln_sid_starshot False
CREADO: ln_sid_starshot
  - DataFrame: 289 filas
Layouts disponibles: 5
<PyQt5.QtWidgets.QGridLayout object at 0x000001E350CAF6D0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E350CAF760>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E350CAF640>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E350CAF5B0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E350CAF520>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
action tolerance encontrado
Widgets MLC encontrados y configurados

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000001E350CAC9D0>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

Se presionó btn_guardar_ix

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000001E350CAC9D0>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

Se presionó btn_guardar_ix

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000001E350CAC9D0>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

Se presionó btn_guardar_ix
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-12\respaldos_bd\BaseDatosQA_2026-08-12_101410.db
admin2025
ANTES ADD: btn_2_laseres False
CREADO: btn_2_laseres
ANTES ADD: btn_2_telemetro False
CREADO: btn_2_telemetro
ANTES ADD: btn_2_tamano_campo False
CREADO: btn_2_tamano_campo
ANTES ADD: line_2_centrado_reticulo False
CREADO: line_2_centrado_reticulo
ANTES ADD: line_2_dosis_referencia False
CREADO: line_2_dosis_referencia
ANTES ADD: observaciones False
CREADO: observaciones
super().__init__: 0.000s
dict_values(['luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla'])
initDATA: 0.001s
ANTES ADD: btn_2_laseres False
CREADO: btn_2_laseres
ANTES ADD: btn_2_telemetro False
CREADO: btn_2_telemetro
ANTES ADD: btn_2_tamano_campo False
CREADO: btn_2_tamano_campo
ANTES ADD: line_2_centrado_reticulo False
CREADO: line_2_centrado_reticulo
ANTES ADD: line_2_fot_6mv False
CREADO: line_2_fot_6mv
ANTES ADD: line_2_fot_15mv False
CREADO: line_2_fot_15mv
ANTES ADD: line_2_ele_6mev False
CREADO: line_2_ele_6mev
ANTES ADD: line_2_ele_9mev False
CREADO: line_2_ele_9mev
ANTES ADD: line_2_ele_12mev False
CREADO: line_2_ele_12mev
ANTES ADD: line_2_ele_15mev False
CREADO: line_2_ele_15mev
ANTES ADD: observaciones False
CREADO: observaciones
iniGUI: 0.022s
load table: 0.089s
asignar_encabezados: 0.093s
button_click: 0.093s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001E351E87210>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
user_id_f2 antes de create_control: 6
Entrando a crear control
Clinac ix
Cargando widgets desde hoja: preguntas_mensu_ix
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_princi_electrones False
CREADO: ln_fact_cam_princi_electrones
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
ANTES ADD: observaciones_segu False
CREADO: observaciones_segu
ANTES ADD: puntero_telem_diff False
CREADO: puntero_telem_diff
ANTES ADD: lbl_telem_rango False
CREADO: lbl_telem_rango
ANTES ADD: lbl_telem_desp False
CREADO: lbl_telem_desp
ANTES ADD: lbl_camilla_vert_rango False
CREADO: lbl_camilla_vert_rango
ANTES ADD: lbl_camilla_vert_desp False
CREADO: lbl_camilla_vert_desp
ANTES ADD: lbl_camilla_iso_desp False
CREADO: lbl_camilla_iso_desp
ANTES ADD: lbl_reticulo_cent False
CREADO: lbl_reticulo_cent
ANTES ADD: lbl_iso_mec False
CREADO: lbl_iso_mec
ANTES ADD: camp_luz_desp False
CREADO: camp_luz_desp
ANTES ADD: lbl_bordes_coin False
CREADO: lbl_bordes_coin
ANTES ADD: lbl_laser_techo False
CREADO: lbl_laser_techo
ANTES ADD: lbl_laser_lateral27 False
CREADO: lbl_laser_lateral27
ANTES ADD: lbl_laser_lateral9 False
CREADO: lbl_laser_lateral9
ANTES ADD: observaciones False
CREADO: observaciones
ANTES ADD: val_teo_6mv False
CREADO: val_teo_6mv
ANTES ADD: ln_dosis_ref_cgy_um_6mv False
CREADO: ln_dosis_ref_cgy_um_6mv
ANTES ADD: ln_discrepancia_dosis_6mv False
CREADO: ln_discrepancia_dosis_6mv
ANTES ADD: ln_calidad_pdd20_10_6mv False
CREADO: ln_calidad_pdd20_10_6mv
ANTES ADD: ln_discrepancia_calidad_6mv False
CREADO: ln_discrepancia_calidad_6mv
ANTES ADD: ln_simetria_inplane_6mv False
CREADO: ln_simetria_inplane_6mv
ANTES ADD: ln_simetria_crossplane_6mv False
CREADO: ln_simetria_crossplane_6mv
ANTES ADD: ln_planicidad_inplane_6mv False
CREADO: ln_planicidad_inplane_6mv
ANTES ADD: ln_planicidad_crossplane_6mv False
CREADO: ln_planicidad_crossplane_6mv
ANTES ADD: val_teo_15mv False
CREADO: val_teo_15mv
ANTES ADD: ln_dosis_ref_cgy_um_15mv False
CREADO: ln_dosis_ref_cgy_um_15mv
ANTES ADD: ln_discrepancia_dosis_15mv False
CREADO: ln_discrepancia_dosis_15mv
ANTES ADD: ln_calidad_pdd20_10_15mv False
CREADO: ln_calidad_pdd20_10_15mv
ANTES ADD: ln_discrepancia_calidad_15mv False
CREADO: ln_discrepancia_calidad_15mv
ANTES ADD: ln_simetria_inplane_15mv False
CREADO: ln_simetria_inplane_15mv
ANTES ADD: ln_simetria_crossplane_15mv False
CREADO: ln_simetria_crossplane_15mv
ANTES ADD: ln_planicidad_inplane_15mv False
CREADO: ln_planicidad_inplane_15mv
ANTES ADD: ln_planicidad_crossplane_15mv False
CREADO: ln_planicidad_crossplane_15mv
ANTES ADD: val_teo_6mev False
CREADO: val_teo_6mev
ANTES ADD: ln_dosis_ref_cgy_um_6mev False
CREADO: ln_dosis_ref_cgy_um_6mev
ANTES ADD: ln_discrepancia_dosis_6mev False
CREADO: ln_discrepancia_dosis_6mev
ANTES ADD: ln_calidad_j2_j1_6mev False
CREADO: ln_calidad_j2_j1_6mev
ANTES ADD: ln_discrepancia_calidad_6mev False
CREADO: ln_discrepancia_calidad_6mev
ANTES ADD: ln_simetria_inplane_6mev False
CREADO: ln_simetria_inplane_6mev
ANTES ADD: ln_simetria_crossplane_6mev False
CREADO: ln_simetria_crossplane_6mev
ANTES ADD: ln_planicidad_inplane_6mev False
CREADO: ln_planicidad_inplane_6mev
ANTES ADD: ln_planicidad_crossplane_6mev False
CREADO: ln_planicidad_crossplane_6mev
ANTES ADD: val_teo_9mev False
CREADO: val_teo_9mev
ANTES ADD: ln_dosis_ref_cgy_um_9mev False
CREADO: ln_dosis_ref_cgy_um_9mev
ANTES ADD: ln_discrepancia_dosis_9mev False
CREADO: ln_discrepancia_dosis_9mev
ANTES ADD: ln_calidad_j2_j1_9mev False
CREADO: ln_calidad_j2_j1_9mev
ANTES ADD: ln_discrepancia_calidad_9mev False
CREADO: ln_discrepancia_calidad_9mev
ANTES ADD: ln_simetria_inplane_9mev False
CREADO: ln_simetria_inplane_9mev
ANTES ADD: ln_simetria_crossplane_9mev False
CREADO: ln_simetria_crossplane_9mev
ANTES ADD: ln_planicidad_inplane_9mev False
CREADO: ln_planicidad_inplane_9mev
ANTES ADD: ln_planicidad_crossplane_9mev False
CREADO: ln_planicidad_crossplane_9mev
ANTES ADD: val_teo_12mev False
CREADO: val_teo_12mev
ANTES ADD: ln_dosis_ref_cgy_um_12mev False
CREADO: ln_dosis_ref_cgy_um_12mev
ANTES ADD: ln_discrepancia_dosis_12mev False
CREADO: ln_discrepancia_dosis_12mev
ANTES ADD: ln_calidad_j2_j1_12mev False
CREADO: ln_calidad_j2_j1_12mev
ANTES ADD: ln_discrepancia_calidad_12mev False
CREADO: ln_discrepancia_calidad_12mev
ANTES ADD: ln_simetria_inplane_12mev False
CREADO: ln_simetria_inplane_12mev
ANTES ADD: ln_simetria_crossplane_12mev False
CREADO: ln_simetria_crossplane_12mev
ANTES ADD: ln_planicidad_inplane_12mev False
CREADO: ln_planicidad_inplane_12mev
ANTES ADD: ln_planicidad_crossplane_12mev False
CREADO: ln_planicidad_crossplane_12mev
ANTES ADD: val_teo_15mev False
CREADO: val_teo_15mev
ANTES ADD: ln_dosis_ref_cgy_um_15mev False
CREADO: ln_dosis_ref_cgy_um_15mev
ANTES ADD: ln_discrepancia_dosis_15mev False
CREADO: ln_discrepancia_dosis_15mev
ANTES ADD: ln_calidad_j2_j1_15mev False
CREADO: ln_calidad_j2_j1_15mev
ANTES ADD: ln_discrepancia_calidad_15mev False
CREADO: ln_discrepancia_calidad_15mev
ANTES ADD: ln_simetria_inplane_15mev False
CREADO: ln_simetria_inplane_15mev
ANTES ADD: ln_simetria_crossplane_15mev False
CREADO: ln_simetria_crossplane_15mev
ANTES ADD: ln_planicidad_inplane_15mev False
CREADO: ln_planicidad_inplane_15mev
ANTES ADD: ln_planicidad_crossplane_15mev False
CREADO: ln_planicidad_crossplane_15mev
ANTES ADD: ln_observaciones_dosi False
CREADO: ln_observaciones_dosi
ANTES ADD: ln_tolerance_mlc False
CREADO: ln_tolerance_mlc
ANTES ADD: ln_action_tolerance False
CREADO: ln_action_tolerance
ANTES ADD: ln_tolerance_starshot False
CREADO: ln_tolerance_starshot
ANTES ADD: ln_sid_starshot False
CREADO: ln_sid_starshot
  - DataFrame: 289 filas
Layouts disponibles: 5
<PyQt5.QtWidgets.QGridLayout object at 0x000001E318F031C0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E318F00040>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E318F02200>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E318F01240>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E318F00280>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
action tolerance encontrado
Widgets MLC encontrados y configurados
Insertando datos de equipos para IX
Insertados 4 registros de equipos correctamente
Actualizando tabla de controles mensuales para Clinac ix
Actualizando tabla de controles mensuales para Clinac ix
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-12\respaldos_bd\BaseDatosQA_2026-08-12_101536.db
admin2025
ANTES ADD: btn_2_laseres False
CREADO: btn_2_laseres
ANTES ADD: btn_2_telemetro False
CREADO: btn_2_telemetro
ANTES ADD: btn_2_tamano_campo False
CREADO: btn_2_tamano_campo
ANTES ADD: line_2_centrado_reticulo False
CREADO: line_2_centrado_reticulo
ANTES ADD: line_2_dosis_referencia False
CREADO: line_2_dosis_referencia
ANTES ADD: observaciones False
CREADO: observaciones
Clinac 600
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001E355C78790>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
user_id_f2 antes de create_control: 6
Entrando a crear control
Clinac 600
Cargando widgets desde hoja: preguntas_mensu_600
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
ANTES ADD: observaciones_segu False
CREADO: observaciones_segu
ANTES ADD: puntero_telem_diff False
CREADO: puntero_telem_diff
ANTES ADD: lbl_telem_rango False
CREADO: lbl_telem_rango
ANTES ADD: lbl_telem_desp False
CREADO: lbl_telem_desp
ANTES ADD: lbl_camilla_vert_rango False
CREADO: lbl_camilla_vert_rango
ANTES ADD: lbl_camilla_vert_desp False
CREADO: lbl_camilla_vert_desp
ANTES ADD: lbl_camilla_iso_desp False
CREADO: lbl_camilla_iso_desp
ANTES ADD: lbl_reticulo_cent False
CREADO: lbl_reticulo_cent
ANTES ADD: lbl_iso_mec False
CREADO: lbl_iso_mec
ANTES ADD: camp_luz_desp False
CREADO: camp_luz_desp
ANTES ADD: lbl_bordes_coin False
CREADO: lbl_bordes_coin
ANTES ADD: lbl_laser_techo False
CREADO: lbl_laser_techo
ANTES ADD: lbl_laser_lateral27 False
CREADO: lbl_laser_lateral27
ANTES ADD: lbl_laser_lateral9 False
CREADO: lbl_laser_lateral9
ANTES ADD: observaciones False
CREADO: observaciones
ANTES ADD: val_teo_6mv False
CREADO: val_teo_6mv
ANTES ADD: ln_dosis_ref_cgy_um_6mv False
CREADO: ln_dosis_ref_cgy_um_6mv
ANTES ADD: ln_discrepancia_dosis_6mv False
CREADO: ln_discrepancia_dosis_6mv
ANTES ADD: ln_calidad_pdd20_10_6mv False
CREADO: ln_calidad_pdd20_10_6mv
ANTES ADD: ln_discrepancia_calidad_6mv False
CREADO: ln_discrepancia_calidad_6mv
ANTES ADD: ln_simetria_inplane_6mv False
CREADO: ln_simetria_inplane_6mv
ANTES ADD: ln_simetria_crossplane_6mv False
CREADO: ln_simetria_crossplane_6mv
ANTES ADD: ln_planicidad_inplane_6mv False
CREADO: ln_planicidad_inplane_6mv
ANTES ADD: ln_planicidad_crossplane_6mv False
CREADO: ln_planicidad_crossplane_6mv
ANTES ADD: ln_observaciones_dosi False
CREADO: ln_observaciones_dosi
ANTES ADD: ln_tolerance_mlc False
CREADO: ln_tolerance_mlc
ANTES ADD: ln_action_tolerance False
CREADO: ln_action_tolerance
ANTES ADD: ln_tolerance_starshot False
CREADO: ln_tolerance_starshot
ANTES ADD: ln_sid_starshot False
CREADO: ln_sid_starshot
  - DataFrame: 128 filas
Layouts disponibles: 5
<PyQt5.QtWidgets.QGridLayout object at 0x000001E350BF69E0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E350BF6560>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E350BF6680>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E350BF65F0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E350BF6710>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
DF LINES: 
['val_teo_6mv', 'ln_dosis_ref_cgy_um_6mv', 'ln_discrepancia_dosis_6mv', 'ln_tolerancia_dosis', 'ln_calidad_pdd20_10_6mv', 'ln_discrepancia_calidad_6mv', 'ln_tolerancia_calidad', 'ln_simetria_inplane_6mv', 'ln_simetria_crossplane_6mv', 'ln_tolerancia_simetria', 'ln_planicidad_inplane_6mv', 'ln_planicidad_crossplane_6mv', 'ln_tolerancia_planicidad', 'ln_observaciones_dosi']
Widget 'ln_dosis_ref_cgy_um_15mv' no encontrado
Widget 'ln_dosis_ref_cgy_um_6mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_9mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_12mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_15mev' no encontrado
super().__init__: 0.000s
dict_values(['luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla'])
initDATA: 0.001s
ANTES ADD: btn_2_laseres False
CREADO: btn_2_laseres
ANTES ADD: btn_2_telemetro False
CREADO: btn_2_telemetro
ANTES ADD: btn_2_tamano_campo False
CREADO: btn_2_tamano_campo
ANTES ADD: line_2_centrado_reticulo False
CREADO: line_2_centrado_reticulo
ANTES ADD: line_2_fot_6mv False
CREADO: line_2_fot_6mv
ANTES ADD: line_2_fot_15mv False
CREADO: line_2_fot_15mv
ANTES ADD: line_2_ele_6mev False
CREADO: line_2_ele_6mev
ANTES ADD: line_2_ele_9mev False
CREADO: line_2_ele_9mev
ANTES ADD: line_2_ele_12mev False
CREADO: line_2_ele_12mev
ANTES ADD: line_2_ele_15mev False
CREADO: line_2_ele_15mev
ANTES ADD: observaciones False
CREADO: observaciones
iniGUI: 0.024s
load table: 0.093s
asignar_encabezados: 0.097s
button_click: 0.098s
consultando db
2026-08-04
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado laseres: 1.5 en btn_2_laseres
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado telemetro: 0 en btn_2_telemetro
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado tamano_campo: 0 en btn_2_tamano_campo
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado centrado_reticulo: 0 en line_2_centrado_reticulo
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargadas observaciones
✓ Datos del 2026-08-04 cargados correctamente.
  - Botones finales: 12
consultando db
2026-08-12
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado laseres: 1 en btn_2_laseres
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado telemetro: 1 en btn_2_telemetro
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado tamano_campo: 1 en btn_2_tamano_campo
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado centrado_reticulo: 1 en line_2_centrado_reticulo
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargadas observaciones
✓ Datos del 2026-08-12 cargados correctamente.
  - Botones finales: 12
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001E355C78790>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Físico 2 seleccionado: Daniela Mesa Lotero, ID: 9
user_id_f2 antes de create_control: 9
Entrando a crear control
Clinac ix
Cargando widgets desde hoja: preguntas_mensu_ix
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_princi_electrones False
CREADO: ln_fact_cam_princi_electrones
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
ANTES ADD: observaciones_segu False
CREADO: observaciones_segu
ANTES ADD: puntero_telem_diff False
CREADO: puntero_telem_diff
ANTES ADD: lbl_telem_rango False
CREADO: lbl_telem_rango
ANTES ADD: lbl_telem_desp False
CREADO: lbl_telem_desp
ANTES ADD: lbl_camilla_vert_rango False
CREADO: lbl_camilla_vert_rango
ANTES ADD: lbl_camilla_vert_desp False
CREADO: lbl_camilla_vert_desp
ANTES ADD: lbl_camilla_iso_desp False
CREADO: lbl_camilla_iso_desp
ANTES ADD: lbl_reticulo_cent False
CREADO: lbl_reticulo_cent
ANTES ADD: lbl_iso_mec False
CREADO: lbl_iso_mec
ANTES ADD: camp_luz_desp False
CREADO: camp_luz_desp
ANTES ADD: lbl_bordes_coin False
CREADO: lbl_bordes_coin
ANTES ADD: lbl_laser_techo False
CREADO: lbl_laser_techo
ANTES ADD: lbl_laser_lateral27 False
CREADO: lbl_laser_lateral27
ANTES ADD: lbl_laser_lateral9 False
CREADO: lbl_laser_lateral9
ANTES ADD: observaciones False
CREADO: observaciones
ANTES ADD: val_teo_6mv False
CREADO: val_teo_6mv
ANTES ADD: ln_dosis_ref_cgy_um_6mv False
CREADO: ln_dosis_ref_cgy_um_6mv
ANTES ADD: ln_discrepancia_dosis_6mv False
CREADO: ln_discrepancia_dosis_6mv
ANTES ADD: ln_calidad_pdd20_10_6mv False
CREADO: ln_calidad_pdd20_10_6mv
ANTES ADD: ln_discrepancia_calidad_6mv False
CREADO: ln_discrepancia_calidad_6mv
ANTES ADD: ln_simetria_inplane_6mv False
CREADO: ln_simetria_inplane_6mv
ANTES ADD: ln_simetria_crossplane_6mv False
CREADO: ln_simetria_crossplane_6mv
ANTES ADD: ln_planicidad_inplane_6mv False
CREADO: ln_planicidad_inplane_6mv
ANTES ADD: ln_planicidad_crossplane_6mv False
CREADO: ln_planicidad_crossplane_6mv
ANTES ADD: val_teo_15mv False
CREADO: val_teo_15mv
ANTES ADD: ln_dosis_ref_cgy_um_15mv False
CREADO: ln_dosis_ref_cgy_um_15mv
ANTES ADD: ln_discrepancia_dosis_15mv False
CREADO: ln_discrepancia_dosis_15mv
ANTES ADD: ln_calidad_pdd20_10_15mv False
CREADO: ln_calidad_pdd20_10_15mv
ANTES ADD: ln_discrepancia_calidad_15mv False
CREADO: ln_discrepancia_calidad_15mv
ANTES ADD: ln_simetria_inplane_15mv False
CREADO: ln_simetria_inplane_15mv
ANTES ADD: ln_simetria_crossplane_15mv False
CREADO: ln_simetria_crossplane_15mv
ANTES ADD: ln_planicidad_inplane_15mv False
CREADO: ln_planicidad_inplane_15mv
ANTES ADD: ln_planicidad_crossplane_15mv False
CREADO: ln_planicidad_crossplane_15mv
ANTES ADD: val_teo_6mev False
CREADO: val_teo_6mev
ANTES ADD: ln_dosis_ref_cgy_um_6mev False
CREADO: ln_dosis_ref_cgy_um_6mev
ANTES ADD: ln_discrepancia_dosis_6mev False
CREADO: ln_discrepancia_dosis_6mev
ANTES ADD: ln_calidad_j2_j1_6mev False
CREADO: ln_calidad_j2_j1_6mev
ANTES ADD: ln_discrepancia_calidad_6mev False
CREADO: ln_discrepancia_calidad_6mev
ANTES ADD: ln_simetria_inplane_6mev False
CREADO: ln_simetria_inplane_6mev
ANTES ADD: ln_simetria_crossplane_6mev False
CREADO: ln_simetria_crossplane_6mev
ANTES ADD: ln_planicidad_inplane_6mev False
CREADO: ln_planicidad_inplane_6mev
ANTES ADD: ln_planicidad_crossplane_6mev False
CREADO: ln_planicidad_crossplane_6mev
ANTES ADD: val_teo_9mev False
CREADO: val_teo_9mev
ANTES ADD: ln_dosis_ref_cgy_um_9mev False
CREADO: ln_dosis_ref_cgy_um_9mev
ANTES ADD: ln_discrepancia_dosis_9mev False
CREADO: ln_discrepancia_dosis_9mev
ANTES ADD: ln_calidad_j2_j1_9mev False
CREADO: ln_calidad_j2_j1_9mev
ANTES ADD: ln_discrepancia_calidad_9mev False
CREADO: ln_discrepancia_calidad_9mev
ANTES ADD: ln_simetria_inplane_9mev False
CREADO: ln_simetria_inplane_9mev
ANTES ADD: ln_simetria_crossplane_9mev False
CREADO: ln_simetria_crossplane_9mev
ANTES ADD: ln_planicidad_inplane_9mev False
CREADO: ln_planicidad_inplane_9mev
ANTES ADD: ln_planicidad_crossplane_9mev False
CREADO: ln_planicidad_crossplane_9mev
ANTES ADD: val_teo_12mev False
CREADO: val_teo_12mev
ANTES ADD: ln_dosis_ref_cgy_um_12mev False
CREADO: ln_dosis_ref_cgy_um_12mev
ANTES ADD: ln_discrepancia_dosis_12mev False
CREADO: ln_discrepancia_dosis_12mev
ANTES ADD: ln_calidad_j2_j1_12mev False
CREADO: ln_calidad_j2_j1_12mev
ANTES ADD: ln_discrepancia_calidad_12mev False
CREADO: ln_discrepancia_calidad_12mev
ANTES ADD: ln_simetria_inplane_12mev False
CREADO: ln_simetria_inplane_12mev
ANTES ADD: ln_simetria_crossplane_12mev False
CREADO: ln_simetria_crossplane_12mev
ANTES ADD: ln_planicidad_inplane_12mev False
CREADO: ln_planicidad_inplane_12mev
ANTES ADD: ln_planicidad_crossplane_12mev False
CREADO: ln_planicidad_crossplane_12mev
ANTES ADD: val_teo_15mev False
CREADO: val_teo_15mev
ANTES ADD: ln_dosis_ref_cgy_um_15mev False
CREADO: ln_dosis_ref_cgy_um_15mev
ANTES ADD: ln_discrepancia_dosis_15mev False
CREADO: ln_discrepancia_dosis_15mev
ANTES ADD: ln_calidad_j2_j1_15mev False
CREADO: ln_calidad_j2_j1_15mev
ANTES ADD: ln_discrepancia_calidad_15mev False
CREADO: ln_discrepancia_calidad_15mev
ANTES ADD: ln_simetria_inplane_15mev False
CREADO: ln_simetria_inplane_15mev
ANTES ADD: ln_simetria_crossplane_15mev False
CREADO: ln_simetria_crossplane_15mev
ANTES ADD: ln_planicidad_inplane_15mev False
CREADO: ln_planicidad_inplane_15mev
ANTES ADD: ln_planicidad_crossplane_15mev False
CREADO: ln_planicidad_crossplane_15mev
ANTES ADD: ln_observaciones_dosi False
CREADO: ln_observaciones_dosi
ANTES ADD: ln_tolerance_mlc False
CREADO: ln_tolerance_mlc
ANTES ADD: ln_action_tolerance False
CREADO: ln_action_tolerance
ANTES ADD: ln_tolerance_starshot False
CREADO: ln_tolerance_starshot
ANTES ADD: ln_sid_starshot False
CREADO: ln_sid_starshot
  - DataFrame: 289 filas
Layouts disponibles: 5
<PyQt5.QtWidgets.QGridLayout object at 0x000001E3121656C0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E312165750>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E312165630>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E3121655A0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E312165510>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
action tolerance encontrado
Widgets MLC encontrados y configurados
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025
→ Eliminando en tabla controles, WHERE "id" = ?, valores [42]
UPDATE (anular) ejecutado correctamente
Fin de eliminarRegistro


 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000001E31215AC20>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

Se presionó btn_guardar_ix
Subiendo tabla indicadores_brazo sin id_energia
Los argumentos son: nombre_tabla=indicadores_brazo, ref=42, anual=False, id=False

▥ Columnas detectadas: ['ref', 'nivel', 'indicador_luminoso_consola', 'indicador_luminoso_equipo'] para indicadores_brazo

Bloque identificado por ['ref'] para la tabla indicadores_brazo, id = False

▥ Datos a insertar en indicadores_brazo:
  - [42, '0°', '', '']
  - [42, '90°', '', '']
  - [42, '180°', '', '']
  - [42, '270°', '', '']
Actualizando tabla de controles mensuales para Clinac ix
Tabla indicadores_brazo subida correctamente

Subiendo datos para preguntas
    Método open_main_window en la clase: DialogAdminPermisoEditar
admin2025
self.accept() = None
    El usuario presionó Sí (DialogAdminPermisoEditar)

▥ Columnas detectadas: ['ref', 'iso_mec', 'reticulo_cent', 'bordes_coin', 'camilla_vert_rango', 'camilla_vert_desp', 'camilla_iso_desp', 'telem_rango', 'telem_desp', 'camp_luz_desp', 'puntero_telem_diff', 'laser_techo', 'laser_lateral27', 'laser_lateral9', 'observaciones'] para preguntas

Datos guardados correctamente.
Actualizando tabla de controles mensuales para Clinac ix
Datos subidos correctamente
Dialog llamado desde: PruebaMensualIX
Manteniendo columna ID

▥ Columnas detectadas: ['equip_type', 'model', 'serie', 'calibr_fact', 'calibr_fact2', 'fecha_calibr', 'fabricante', 't_cal', 'p_cal', 'h_cal', 'v1', 'activo', 'vigente', 'imagen_certificado'] para equipos

ANTES ADD: modelo False
CREADO: modelo
ANTES ADD: serie False
CREADO: serie
ANTES ADD: calib_factor False
CREADO: calib_factor
ANTES ADD: calib_factor2 False
CREADO: calib_factor2
ANTES ADD: fabricante False
CREADO: fabricante
ANTES ADD: t_cal False
CREADO: t_cal
ANTES ADD: p_cal False
CREADO: p_cal
ANTES ADD: h_cal False
CREADO: h_cal
ANTES ADD: v1_cal False
CREADO: v1_cal

Botón editar equipo clickeado (función habilitar2 en equipos.py)
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025

Función editarEquipo en equipos.py
Datos a editar
----------------------------------------------------------------------
Fila seleccionada: 35
ID del equipo seleccionado: 70
    - Datos del equipo recuperados: 
          ('Cámara de ionización', 'N34001', '2426', 0.08524, None, '05/02/2024', 'PTW', 22, 101.325, 50, 300.0, 0.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 05/02/2024
Guardando cambios en el equipo...
ID del equipo a actualizar: 70
Recursos limpiados correctamente

Botón deshabilitar clickeado
Dialog llamado desde: PruebaMensualIX
300
300
300
Data saved successfully for date: 12/08/2026
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-08-05-05-01-00-0000-GeometryCheckTemplate6xFFFMVkV
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-08-05-05-01-00-0000-GeometryCheckTemplate6xFFFMVkV
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-08-06-05-01-47-0000-GeometryCheckTemplate6xFFFMVkV
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-08-06-05-01-47-0000-GeometryCheckTemplate6xFFFMVkV
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-08-06-05-01-47-0000-GeometryCheckTemplate6xFFFMVkV
Ya existe la fecha

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000001E31215AC20>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

Se presionó btn_guardar_ix

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000001E31215AC20>
Texto actual en observaciones_segu: 'nigger'
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

Se presionó btn_guardar_ix
