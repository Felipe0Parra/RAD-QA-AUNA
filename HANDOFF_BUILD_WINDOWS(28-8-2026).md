# Rebuild Windows 28 de Agosto de 2026

Anotaciones:
- Bueno, resulta que si se pudieron guardar adecuadamente los reportes diarios de braquiterapia a pesar de que no era visible la actividad esperada.
- La unica forma de que la imagen del reporte diario de braquiterapia es dando el boton de limpiar, es decir, cuando cambio a un nuevo dia se limpia todo, aparece la actividad calculada pero queda la imagen del anterior registro que hubiese guardado. Parece que tambien queda la informacion del analisis anterior, parece que ademas no guarda, es probable que sea porque estoy metienddo una placa que no corresponde a braqui, pero el analisis se ejecuta, aparece el perfil de intensidad para el campo emitido por el acelerador en la placa que monte, pero no deja guardar la imagen, el boton no parece emitir ninguna senal, pero en la BD quedaron los analisis que parecen ser identicos a la ultima placa guardada antes de mi intento. El objetivo aqui es que la imagen y los datos de su analisis desaparezcan de la pantalla y de el cache que puede quedar por ahi cuando yo cambie a un nuevo dia.
- Sigue sucediendo el problema de duplicacion de los botones en analisis de imagen.
- Cuando paso de unos dias a otro de forma hacia el pasado a veces aparece el widget de actividad reportada sombreado en rojo, pero cuando vuelvo y paso por ese mismo dia que marca esa casilla en rojo pero yendo hacia adelante en el tiempo ya no lo marca, a veces queda marcado cuando me paso a un dia nuevo desde un dia que lo marcaba.
- Ademas he notado que no se guarda realmente la hora del control, asi que no tiene ningun sentido tener la hora ahi mostrandose, pero obviamente es fundamental tener en cuenta la hora, pero en el widget de fecha y hora hay algun error porque no se puede ubicar el cursor adecuadamente y escribir una hora diferente, no deja poner ninguna hora nueva.
- Me fui para el dia 28, modifique algunos de los valores de seguridad y le di anadir, logicamente creo un nuevo registro en braqui, anulando los anteriores para esa fecha, pero el nuevo registro no solo tenia los cambios que habia hecho sino que habia desaparecido todo el analisis de imagen. Con los botones duplicados le di analisar, dibujo los perfiles, pero en el momento en el que hize click en uno y ambos de los botones de guardar no parecia suceder nada, luego con la rueda del mouse quise hacer zoom out, ten en cuenta que como estaba editando el registro original del dia 28, en la imagen aun aparecia la imagen de la placa destinada y propia de braqui, pero en el momento en el que hice zoom out desaparecio y aparecio la de tamano de campo que habia tratado de montar para el 31. Aqui hay algo muy importante que revisar, el guardado de estas secciones deberia converger, siempre, solo hay un boton de anadir, no es tan similar al caso del mensual donde hay botones por separado para cada seccion y tienen que converger igual.
- De resto parece funcionar bien.

Todo lo anterior fue ejecutando directamente el .exe por lo que no hay expulsion de terminal, voy a tratar de hacer el mismo proceso pero ejecutando la app desde la terminal:

Listo. Backup de seguridad conservado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\BaseDatosQA.db.pre_migracion_20260828_084249.bak
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28> python main.py
E10: sqlite_sequence normalizada para None (duplicados -> seq=2026-08-27 14:46:53)
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
Fecha Final COT: 2026-08-28 10:04:26-05:00
Horas transcurridas desde 2026-08-28 10:04:26: 2021.4672222222223
Dias transcurridos: 84.22780092592593
 La actividad es:  6.1902
consultando db
2026-08-31
No hay datos registrados para la fecha 2026-08-31.
✓ Canvas limpiado
13.65
Fecha Inicio CET: 2026-06-05 11:36:24+02:00 (Fecha del certificado)
Fecha Inicio convertido a COT: 2026-06-05 04:36:24-05:00
Fecha Final COT: 2026-08-31 10:04:26-05:00
Horas transcurridas desde 2026-08-31 10:04:26: 2093.467222222222
Dias transcurridos: 87.22780092592592
 La actividad es:  6.0183
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001D4081D9710>, id_f1_num usado: Administrador
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
consultando db
2026-08-28
1
1
1
1
✓ Imagen cargada desde BLOB (187462 bytes)
✓ Datos del 2026-08-28 cargados correctamente.
  - Botones finales: 12
DPI:  300
Limpiando data
could not convert string to float: ''
consultando db
2026-08-31
No hay datos registrados para la fecha 2026-08-31.
✓ Canvas limpiado
13.65
Fecha Inicio CET: 2026-06-05 11:36:24+02:00 (Fecha del certificado)
Fecha Inicio convertido a COT: 2026-06-05 04:36:24-05:00
Fecha Final COT: 2026-08-31 10:04:26-05:00
Horas transcurridas desde 2026-08-31 10:04:26: 2093.467222222222
Dias transcurridos: 87.22780092592592
 La actividad es:  6.0183




















 - Hay que hacer al fisico 1 obligatorio para crear el control anual tambien:

 Error grave al tratar de subir los datos de la tabla de indicadores angulares del brazo y en lat tabla de precision de la posicion de las multilaminas en el anual del halcyon:

 (.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28> python main.py
E10: sqlite_sequence normalizada para None (duplicados -> seq=2026-08-27 14:46:53)
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
Fecha Final COT: 2026-08-28 10:04:26-05:00
Horas transcurridas desde 2026-08-28 10:04:26: 2021.4672222222223
Dias transcurridos: 84.22780092592593
 La actividad es:  6.1902
consultando db
2026-08-31
No hay datos registrados para la fecha 2026-08-31.
✓ Canvas limpiado
13.65
Fecha Inicio CET: 2026-06-05 11:36:24+02:00 (Fecha del certificado)
Fecha Inicio convertido a COT: 2026-06-05 04:36:24-05:00
Fecha Final COT: 2026-08-31 10:04:26-05:00
Horas transcurridas desde 2026-08-31 10:04:26: 2093.467222222222
Dias transcurridos: 87.22780092592592
 La actividad es:  6.0183
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001D4081D9710>, id_f1_num usado: Administrador
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
consultando db
2026-08-28
1
1
1
1
✓ Imagen cargada desde BLOB (187462 bytes)
✓ Datos del 2026-08-28 cargados correctamente.
  - Botones finales: 12
DPI:  300
Limpiando data
could not convert string to float: ''
consultando db
2026-08-31
No hay datos registrados para la fecha 2026-08-31.
✓ Canvas limpiado
13.65
Fecha Inicio CET: 2026-06-05 11:36:24+02:00 (Fecha del certificado)
Fecha Inicio convertido a COT: 2026-06-05 04:36:24-05:00
Fecha Final COT: 2026-08-31 10:04:26-05:00
Horas transcurridas desde 2026-08-31 10:04:26: 2093.467222222222
Dias transcurridos: 87.22780092592592
 La actividad es:  6.0183
super().__init__: 0.000s
dict_values(['luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla'])
initDATA: 0.000s
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
load table: 0.159s
asignar_encabezados: 0.160s
button_click: 0.160s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001D4081D9710>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
Cargando widgets desde hoja: preguntas_anual_ix
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_princi_electrones False
CREADO: ln_fact_cam_princi_electrones
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
  - DataFrame: 32 filas
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\respaldos_bd\BaseDatosQA_2026-08-28_100911.db
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
initDATA: 0.000s
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
load table: 0.087s
asignar_encabezados: 0.087s
button_click: 0.088s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001D4B85C5450>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
Cargando widgets desde hoja: preguntas_anual_ix
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_princi_electrones False
CREADO: ln_fact_cam_princi_electrones
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
  - DataFrame: 32 filas
Clinac 600
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001D4B85C5450>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Cargando widgets desde hoja: preguntas_anual_600
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
  - DataFrame: 22 filas
Halcyon
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001D4B85C5450>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Cargando widgets desde hoja: preguntas_anual_Halcyon
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
ANTES ADD: modelo1 False
CREADO: modelo1
ANTES ADD: serie1 False
CREADO: serie1
ANTES ADD: modelo2 False
CREADO: modelo2
ANTES ADD: serie2 False
CREADO: serie2
ANTES ADD: modelo3 False
CREADO: modelo3
ANTES ADD: serie3 False
CREADO: serie3
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
  - DataFrame: 68 filas
DF LINES: 
['val_teo_6mv', 'ln_dosis_ref_cgy_um_6mv', 'ln_discrepancia_dosis_6mv', 'ln_tolerancia_dosis', 'ln_calidad_pdd20_10_6mv', 'ln_discrepancia_calidad_6mv', 'ln_tolerancia_calidad', 'ln_simetria_inplane_6mv', 'ln_simetria_crossplane_6mv', 'ln_tolerancia_simetria', 'ln_planicidad_inplane_6mv', 'ln_planicidad_crossplane_6mv', 'ln_tolerancia_planicidad', 'ln_observaciones_dosi']
Widget 'ln_dosis_ref_cgy_um_15mv' no encontrado
Widget 'ln_dosis_ref_cgy_um_6mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_9mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_12mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_15mev' no encontrado
DF LINES: 
['modelo1', 'serie1', 'modelo2', 'serie2', 'modelo3', 'serie3']

Subiendo datos para HC_fantomas
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'modelo1', 'serie1', 'modelo2', 'serie2', 'modelo3', 'serie3'] para HC_fantomas

Datos guardados correctamente.
Actualizando tabla de controles anuales para Halcyon
Datos subidos correctamente
Insertados 3 registros de equipos correctamente
Actualizando tabla de controles anuales para Halcyon
Actualizando tabla de controles anuales para Halcyon
Subiendo tabla HC_tamanos_campo_radiacion normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicado_inplane', 'indicado_crossplane', 'medido_inplane', 'medido_crossplane'] para HC_tamanos_campo_radiacion

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_tamanos_campo_radiacion, id = True

▥ Datos a insertar en HC_tamanos_campo_radiacion:
  - [47, 0, '6', '6', '1', '1.2']
  - [47, 0, '8', '8', '1', '1']
  - [47, 0, '10', '10', '1', '1']
  - [47, 0, '20', '20', '1', '11']
  - [47, 0, '28', '28', '1', '1']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_tamanos_campo_radiacion subida(s) correctamente

Subiendo datos para HC_dosimetria_anual
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi'] para HC_dosimetria_anual

ADVERTENCIA: columna 'val_teo_dosis' no tiene widget correspondiente → None
ADVERTENCIA: columna 'val_teo_calidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'dosis_ref_cgy_um' no tiene widget correspondiente → None
ADVERTENCIA: columna 'discrepancia_dosis' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_dosis' no tiene widget correspondiente → None
ADVERTENCIA: columna 'calidad_pdd20_10' no tiene widget correspondiente → None
ADVERTENCIA: columna 'discrepancia_calidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_calidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'simetria_inplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'simetria_crossplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_simetria' no tiene widget correspondiente → None
ADVERTENCIA: columna 'planicidad_inplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'planicidad_crossplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_planicidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'observaciones_dosi' no tiene widget correspondiente → None
Nada que guardar en HC_dosimetria_anual para ref=47 (ningún widget de este guardado corresponde a una columna real).
Actualizando tabla de controles anuales para Halcyon
Datos subidos correctamente
Subiendo tabla HC_linealidad_unidades_monitor_anual normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'UM', 'Q1', 'Q2', 'Qprom'] para HC_linealidad_unidades_monitor_anual

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_linealidad_unidades_monitor_anual, id = True

▥ Datos a insertar en HC_linealidad_unidades_monitor_anual:
  - [47, 0, '50', '1', '1', '1.00']
  - [47, 0, '100', '1', '1', '1.00']
  - [47, 0, '150', '1', '1', '1.00']
  - [47, 0, '200', '1', '1', '1.00']
  - [47, 0, '250', '1', '1', '1.00']
  - [47, 0, '300', '11', '1', '6.00']
  - [47, 0, '350', '1', '1', '1.00']
  - [47, 0, '400', '1', '1', '']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_linealidad_unidades_monitor_anual subida(s) correctamente
Insertados 3 registros de equipos correctamente
Actualizando tabla de controles anuales para Halcyon
Actualizando tabla de controles anuales para Halcyon
Insertados 3 registros de equipos correctamente
Actualizando tabla de controles anuales para Halcyon
Actualizando tabla de controles anuales para Halcyon

Subiendo datos para HC_fantomas
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'modelo1', 'serie1', 'modelo2', 'serie2', 'modelo3', 'serie3'] para HC_fantomas

Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\data\ManejoDatos\load.py", line 819, in subirlineasmensuales
    cursor.execute(sql, datos)
sqlite3.IntegrityError: UNIQUE constraint failed: HC_fantomas.id
Error al guardar: UNIQUE constraint failed: HC_fantomas.id
Actualizando tabla de controles anuales para Halcyon
Datos subidos correctamente
Subiendo tabla HC_indicadores_brazo normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'nivel', 'valor_medido', 'discrepancia'] para HC_indicadores_brazo

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_indicadores_brazo, id = True

▥ Datos a insertar en HC_indicadores_brazo:
  - [47, 0, '0', '1', '1.00']
  - [47, 0, '90', '1', '89.00']
  - [47, 0, '180', '1', '179.00']
  - [47, 0, '270', '1', '269.00']
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\data\ManejoDatos\load.py", line 599, in loadtablacomplex
    cursor.execute(
sqlite3.OperationalError: database is locked
Actualizando tabla de controles anuales para Halcyon
Subiendo tabla HC_indicadores_brazo normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'nivel', 'valor_medido', 'discrepancia'] para HC_indicadores_brazo

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_indicadores_brazo, id = True

▥ Datos a insertar en HC_indicadores_brazo:
  - [47, 0, '0', '1', '1.00']
  - [47, 0, '90', '1', '89.00']
  - [47, 0, '180', '1', '179.00']
  - [47, 0, '270', '1', '269.00']
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\data\ManejoDatos\load.py", line 599, in loadtablacomplex
    cursor.execute(
sqlite3.OperationalError: database is locked
Actualizando tabla de controles anuales para Halcyon
Subiendo tabla HC_indicadores_colimador normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'nivel', 'valor_medido', 'discrepancia'] para HC_indicadores_colimador

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_indicadores_colimador, id = True

▥ Datos a insertar en HC_indicadores_colimador:
  - [47, 0, '0', '1', '1.00']
  - [47, 0, '90', '1', '89.00']
  - [47, 0, '270', '1', '269.00']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_indicadores_colimador subida(s) correctamente
Subiendo tabla HC_indicadores_laser normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'ubicacion', 'concordancia', 'dif_isocentro'] para HC_indicadores_laser

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_indicadores_laser, id = True

▥ Datos a insertar en HC_indicadores_laser:
  - [47, 0, 'Longitudinal', '1', '1']
  - [47, 0, 'Vertical', '1', '1']
  - [47, 0, 'Lateral', '1', '1']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_indicadores_laser subida(s) correctamente
Subiendo tabla HC_indicadores_camilla normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'ubicacion', 'desplazamiento', 'medido_cm', 'diferencia'] para HC_indicadores_camilla

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_indicadores_camilla, id = True

▥ Datos a insertar en HC_indicadores_camilla:
  - [47, 0, 'Longitudinal', '1', '1.2', '20.00']
  - [47, 0, 'Longitudinal', '5', '1', '80.00']
  - [47, 0, 'Longitudinal', '20', '1', '95.00']
  - [47, 0, 'Lateral', '1', '1', '0.00']
  - [47, 0, 'Lateral', '5', '11', '120.00']
  - [47, 0, 'Lateral', '20', '1', '95.00']
  - [47, 0, 'Vertical', '1', '1', '0.00']
  - [47, 0, 'Vertical', '5', '1', '80.00']
  - [47, 0, 'Vertical', '20', '1', '95.00']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_indicadores_camilla subida(s) correctamente
Subiendo tabla HC_velocidad_multilaminas_anual normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'banco', 'velocidad_prom', 'desviacion_med'] para HC_velocidad_multilaminas_anual

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_velocidad_multilaminas_anual, id = True

▥ Datos a insertar en HC_velocidad_multilaminas_anual:
  - [47, 0, 'A Proximal', '1', '1']
  - [47, 0, 'A Distal', '1', '1']
  - [47, 0, 'B Proximal', '1', '1']
  - [47, 0, 'B Distal', '1', '1']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_velocidad_multilaminas_anual subida(s) correctamente
Subiendo tabla HC_precision_posicion_multilaminas_anual normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'medida', 'esperada', 'discrepancia'] para HC_precision_posicion_multilaminas_anual

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_precision_posicion_multilaminas_anual, id = True

▥ Datos a insertar en HC_precision_posicion_multilaminas_anual:
  - [47, 0, '1.2', '1', '20.00']
  - [47, 0, '2', '1', '100.00']
  - [47, 0, '2', '1', '100.00']
  - [47, 0, '2', '1', '100.00']
  - [47, 0, '2', '1', '100.00']
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\data\ManejoDatos\load.py", line 614, in loadtablacomplex
    cursor.executemany(sql, datos)
sqlite3.IntegrityError: UNIQUE constraint failed: HC_precision_posicion_multilaminas_anual.ref, HC_precision_posicion_multilaminas_anual.id_energia, HC_precision_posicion_multilaminas_anual.medida
Actualizando tabla de controles anuales para Halcyon
Analisis de imagen activado en subir_imagen en PruebasDiarias.py
analizando imagen
Subir imagen activado en imagenUpLoader en PruebasDiarias.py
Aceptar imagen activado en PruebasDiarias.py
Aceptar imagen activado en PruebasDiarias.py
Subiendo tabla HC_linealidad_unidades_monitor_anual normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'UM', 'Q1', 'Q2', 'Qprom'] para HC_linealidad_unidades_monitor_anual

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_linealidad_unidades_monitor_anual, id = True

▥ Datos a insertar en HC_linealidad_unidades_monitor_anual:
  - [47, 0, '50', '1', '1', '1.00']
  - [47, 0, '100', '1', '1', '1.00']
  - [47, 0, '150', '1', '1', '1.00']
  - [47, 0, '200', '1', '1', '1.00']
  - [47, 0, '250', '1', '1', '1.00']
  - [47, 0, '300', '11', '1', '6.00']
  - [47, 0, '350', '1', '1', '1.00']
  - [47, 0, '400', '1', '1', '1.00']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_linealidad_unidades_monitor_anual subida(s) correctamente
Subiendo tabla HC_tamanos_campo_radiacion normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicado_inplane', 'indicado_crossplane', 'medido_inplane', 'medido_crossplane'] para HC_tamanos_campo_radiacion

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_tamanos_campo_radiacion, id = True

▥ Datos a insertar en HC_tamanos_campo_radiacion:
  - [47, 0, '6', '6', '1', '1.2']
  - [47, 0, '8', '8', '1', '1']
  - [47, 0, '10', '10', '1', '1']
  - [47, 0, '20', '20', '1', '11']
  - [47, 0, '28', '28', '1', '1']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_tamanos_campo_radiacion subida(s) correctamente

Subiendo datos para HC_dosimetria_anual
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi'] para HC_dosimetria_anual

ADVERTENCIA: columna 'val_teo_dosis' no tiene widget correspondiente → None
ADVERTENCIA: columna 'val_teo_calidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'dosis_ref_cgy_um' no tiene widget correspondiente → None
ADVERTENCIA: columna 'discrepancia_dosis' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_dosis' no tiene widget correspondiente → None
ADVERTENCIA: columna 'calidad_pdd20_10' no tiene widget correspondiente → None
ADVERTENCIA: columna 'discrepancia_calidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_calidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'simetria_inplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'simetria_crossplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_simetria' no tiene widget correspondiente → None
ADVERTENCIA: columna 'planicidad_inplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'planicidad_crossplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_planicidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'observaciones_dosi' no tiene widget correspondiente → None
Nada que guardar en HC_dosimetria_anual para ref=47 (ningún widget de este guardado corresponde a una columna real).
Actualizando tabla de controles anuales para Halcyon
Datos subidos correctamente
Subiendo tabla HC_precision_posicion_multilaminas_anual normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'medida', 'esperada', 'discrepancia'] para HC_precision_posicion_multilaminas_anual

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_precision_posicion_multilaminas_anual, id = True

▥ Datos a insertar en HC_precision_posicion_multilaminas_anual:
  - [47, 0, '1.2', '1', '20.00']
  - [47, 0, '2', '1', '100.00']
  - [47, 0, '2', '1', '100.00']
  - [47, 0, '2', '1', '100.00']
  - [47, 0, '2', '1', '100.00']
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\data\ManejoDatos\load.py", line 614, in loadtablacomplex
    cursor.executemany(sql, datos)
sqlite3.IntegrityError: UNIQUE constraint failed: HC_precision_posicion_multilaminas_anual.ref, HC_precision_posicion_multilaminas_anual.id_energia, HC_precision_posicion_multilaminas_anual.medida
Actualizando tabla de controles anuales para Halcyon




Muuy importante toda la seccion del anual del iX de Factor sobre el eje queda demasiado comprimida tanto que no se puede ver nisiquiera la fila por debajo del encabezaod de la tabla, se puede navegar hacia arriba y hacia abajo pero el espacio es tan pequeno que no se logra ver realmente ni una sola de las filas completas, haciendo imposible introducir los datos, talvez haya que hacer cada pestana navegable, y no cada tabla, la tabla completa pero las pestanas que la contienen navegable, porque esta muy incomodo.


(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28> python main.py
E10: sqlite_sequence normalizada para None (duplicados -> seq=2026-08-27 14:46:53)
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
Fecha Final COT: 2026-08-28 10:04:26-05:00
Horas transcurridas desde 2026-08-28 10:04:26: 2021.4672222222223
Dias transcurridos: 84.22780092592593
 La actividad es:  6.1902
consultando db
2026-08-31
No hay datos registrados para la fecha 2026-08-31.
✓ Canvas limpiado
13.65
Fecha Inicio CET: 2026-06-05 11:36:24+02:00 (Fecha del certificado)
Fecha Inicio convertido a COT: 2026-06-05 04:36:24-05:00
Fecha Final COT: 2026-08-31 10:04:26-05:00
Horas transcurridas desde 2026-08-31 10:04:26: 2093.467222222222
Dias transcurridos: 87.22780092592592
 La actividad es:  6.0183
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001D4081D9710>, id_f1_num usado: Administrador
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
consultando db
2026-08-28
1
1
1
1
✓ Imagen cargada desde BLOB (187462 bytes)
✓ Datos del 2026-08-28 cargados correctamente.
  - Botones finales: 12
DPI:  300
Limpiando data
could not convert string to float: ''
consultando db
2026-08-31
No hay datos registrados para la fecha 2026-08-31.
✓ Canvas limpiado
13.65
Fecha Inicio CET: 2026-06-05 11:36:24+02:00 (Fecha del certificado)
Fecha Inicio convertido a COT: 2026-06-05 04:36:24-05:00
Fecha Final COT: 2026-08-31 10:04:26-05:00
Horas transcurridas desde 2026-08-31 10:04:26: 2093.467222222222
Dias transcurridos: 87.22780092592592
 La actividad es:  6.0183
super().__init__: 0.000s
dict_values(['luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla'])
initDATA: 0.000s
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
load table: 0.159s
asignar_encabezados: 0.160s
button_click: 0.160s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001D4081D9710>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
Cargando widgets desde hoja: preguntas_anual_ix
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_princi_electrones False
CREADO: ln_fact_cam_princi_electrones
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
  - DataFrame: 32 filas
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\respaldos_bd\BaseDatosQA_2026-08-28_100911.db
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
initDATA: 0.000s
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
load table: 0.087s
asignar_encabezados: 0.087s
button_click: 0.088s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001D4B85C5450>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
Cargando widgets desde hoja: preguntas_anual_ix
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_princi_electrones False
CREADO: ln_fact_cam_princi_electrones
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
  - DataFrame: 32 filas
Clinac 600
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001D4B85C5450>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Cargando widgets desde hoja: preguntas_anual_600
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
  - DataFrame: 22 filas
Halcyon
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001D4B85C5450>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Cargando widgets desde hoja: preguntas_anual_Halcyon
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
ANTES ADD: modelo1 False
CREADO: modelo1
ANTES ADD: serie1 False
CREADO: serie1
ANTES ADD: modelo2 False
CREADO: modelo2
ANTES ADD: serie2 False
CREADO: serie2
ANTES ADD: modelo3 False
CREADO: modelo3
ANTES ADD: serie3 False
CREADO: serie3
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
  - DataFrame: 68 filas
DF LINES: 
['val_teo_6mv', 'ln_dosis_ref_cgy_um_6mv', 'ln_discrepancia_dosis_6mv', 'ln_tolerancia_dosis', 'ln_calidad_pdd20_10_6mv', 'ln_discrepancia_calidad_6mv', 'ln_tolerancia_calidad', 'ln_simetria_inplane_6mv', 'ln_simetria_crossplane_6mv', 'ln_tolerancia_simetria', 'ln_planicidad_inplane_6mv', 'ln_planicidad_crossplane_6mv', 'ln_tolerancia_planicidad', 'ln_observaciones_dosi']
Widget 'ln_dosis_ref_cgy_um_15mv' no encontrado
Widget 'ln_dosis_ref_cgy_um_6mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_9mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_12mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_15mev' no encontrado
DF LINES: 
['modelo1', 'serie1', 'modelo2', 'serie2', 'modelo3', 'serie3']

Subiendo datos para HC_fantomas
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'modelo1', 'serie1', 'modelo2', 'serie2', 'modelo3', 'serie3'] para HC_fantomas

Datos guardados correctamente.
Actualizando tabla de controles anuales para Halcyon
Datos subidos correctamente
Insertados 3 registros de equipos correctamente
Actualizando tabla de controles anuales para Halcyon
Actualizando tabla de controles anuales para Halcyon
Subiendo tabla HC_tamanos_campo_radiacion normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicado_inplane', 'indicado_crossplane', 'medido_inplane', 'medido_crossplane'] para HC_tamanos_campo_radiacion

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_tamanos_campo_radiacion, id = True

▥ Datos a insertar en HC_tamanos_campo_radiacion:
  - [47, 0, '6', '6', '1', '1.2']
  - [47, 0, '8', '8', '1', '1']
  - [47, 0, '10', '10', '1', '1']
  - [47, 0, '20', '20', '1', '11']
  - [47, 0, '28', '28', '1', '1']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_tamanos_campo_radiacion subida(s) correctamente

Subiendo datos para HC_dosimetria_anual
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi'] para HC_dosimetria_anual

ADVERTENCIA: columna 'val_teo_dosis' no tiene widget correspondiente → None
ADVERTENCIA: columna 'val_teo_calidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'dosis_ref_cgy_um' no tiene widget correspondiente → None
ADVERTENCIA: columna 'discrepancia_dosis' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_dosis' no tiene widget correspondiente → None
ADVERTENCIA: columna 'calidad_pdd20_10' no tiene widget correspondiente → None
ADVERTENCIA: columna 'discrepancia_calidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_calidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'simetria_inplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'simetria_crossplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_simetria' no tiene widget correspondiente → None
ADVERTENCIA: columna 'planicidad_inplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'planicidad_crossplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_planicidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'observaciones_dosi' no tiene widget correspondiente → None
Nada que guardar en HC_dosimetria_anual para ref=47 (ningún widget de este guardado corresponde a una columna real).
Actualizando tabla de controles anuales para Halcyon
Datos subidos correctamente
Subiendo tabla HC_linealidad_unidades_monitor_anual normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'UM', 'Q1', 'Q2', 'Qprom'] para HC_linealidad_unidades_monitor_anual

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_linealidad_unidades_monitor_anual, id = True

▥ Datos a insertar en HC_linealidad_unidades_monitor_anual:
  - [47, 0, '50', '1', '1', '1.00']
  - [47, 0, '100', '1', '1', '1.00']
  - [47, 0, '150', '1', '1', '1.00']
  - [47, 0, '200', '1', '1', '1.00']
  - [47, 0, '250', '1', '1', '1.00']
  - [47, 0, '300', '11', '1', '6.00']
  - [47, 0, '350', '1', '1', '1.00']
  - [47, 0, '400', '1', '1', '']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_linealidad_unidades_monitor_anual subida(s) correctamente
Insertados 3 registros de equipos correctamente
Actualizando tabla de controles anuales para Halcyon
Actualizando tabla de controles anuales para Halcyon
Insertados 3 registros de equipos correctamente
Actualizando tabla de controles anuales para Halcyon
Actualizando tabla de controles anuales para Halcyon

Subiendo datos para HC_fantomas
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'modelo1', 'serie1', 'modelo2', 'serie2', 'modelo3', 'serie3'] para HC_fantomas

Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\data\ManejoDatos\load.py", line 819, in subirlineasmensuales
    cursor.execute(sql, datos)
sqlite3.IntegrityError: UNIQUE constraint failed: HC_fantomas.id
Error al guardar: UNIQUE constraint failed: HC_fantomas.id
Actualizando tabla de controles anuales para Halcyon
Datos subidos correctamente
Subiendo tabla HC_indicadores_brazo normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'nivel', 'valor_medido', 'discrepancia'] para HC_indicadores_brazo

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_indicadores_brazo, id = True

▥ Datos a insertar en HC_indicadores_brazo:
  - [47, 0, '0', '1', '1.00']
  - [47, 0, '90', '1', '89.00']
  - [47, 0, '180', '1', '179.00']
  - [47, 0, '270', '1', '269.00']
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\data\ManejoDatos\load.py", line 599, in loadtablacomplex
    cursor.execute(
sqlite3.OperationalError: database is locked
Actualizando tabla de controles anuales para Halcyon
Subiendo tabla HC_indicadores_brazo normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'nivel', 'valor_medido', 'discrepancia'] para HC_indicadores_brazo

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_indicadores_brazo, id = True

▥ Datos a insertar en HC_indicadores_brazo:
  - [47, 0, '0', '1', '1.00']
  - [47, 0, '90', '1', '89.00']
  - [47, 0, '180', '1', '179.00']
  - [47, 0, '270', '1', '269.00']
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\data\ManejoDatos\load.py", line 599, in loadtablacomplex
    cursor.execute(
sqlite3.OperationalError: database is locked
Actualizando tabla de controles anuales para Halcyon
Subiendo tabla HC_indicadores_colimador normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'nivel', 'valor_medido', 'discrepancia'] para HC_indicadores_colimador

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_indicadores_colimador, id = True

▥ Datos a insertar en HC_indicadores_colimador:
  - [47, 0, '0', '1', '1.00']
  - [47, 0, '90', '1', '89.00']
  - [47, 0, '270', '1', '269.00']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_indicadores_colimador subida(s) correctamente
Subiendo tabla HC_indicadores_laser normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'ubicacion', 'concordancia', 'dif_isocentro'] para HC_indicadores_laser

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_indicadores_laser, id = True

▥ Datos a insertar en HC_indicadores_laser:
  - [47, 0, 'Longitudinal', '1', '1']
  - [47, 0, 'Vertical', '1', '1']
  - [47, 0, 'Lateral', '1', '1']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_indicadores_laser subida(s) correctamente
Subiendo tabla HC_indicadores_camilla normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'ubicacion', 'desplazamiento', 'medido_cm', 'diferencia'] para HC_indicadores_camilla

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_indicadores_camilla, id = True

▥ Datos a insertar en HC_indicadores_camilla:
  - [47, 0, 'Longitudinal', '1', '1.2', '20.00']
  - [47, 0, 'Longitudinal', '5', '1', '80.00']
  - [47, 0, 'Longitudinal', '20', '1', '95.00']
  - [47, 0, 'Lateral', '1', '1', '0.00']
  - [47, 0, 'Lateral', '5', '11', '120.00']
  - [47, 0, 'Lateral', '20', '1', '95.00']
  - [47, 0, 'Vertical', '1', '1', '0.00']
  - [47, 0, 'Vertical', '5', '1', '80.00']
  - [47, 0, 'Vertical', '20', '1', '95.00']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_indicadores_camilla subida(s) correctamente
Subiendo tabla HC_velocidad_multilaminas_anual normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'banco', 'velocidad_prom', 'desviacion_med'] para HC_velocidad_multilaminas_anual

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_velocidad_multilaminas_anual, id = True

▥ Datos a insertar en HC_velocidad_multilaminas_anual:
  - [47, 0, 'A Proximal', '1', '1']
  - [47, 0, 'A Distal', '1', '1']
  - [47, 0, 'B Proximal', '1', '1']
  - [47, 0, 'B Distal', '1', '1']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_velocidad_multilaminas_anual subida(s) correctamente
Subiendo tabla HC_precision_posicion_multilaminas_anual normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'medida', 'esperada', 'discrepancia'] para HC_precision_posicion_multilaminas_anual

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_precision_posicion_multilaminas_anual, id = True

▥ Datos a insertar en HC_precision_posicion_multilaminas_anual:
  - [47, 0, '1.2', '1', '20.00']
  - [47, 0, '2', '1', '100.00']
  - [47, 0, '2', '1', '100.00']
  - [47, 0, '2', '1', '100.00']
  - [47, 0, '2', '1', '100.00']
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\data\ManejoDatos\load.py", line 614, in loadtablacomplex
    cursor.executemany(sql, datos)
sqlite3.IntegrityError: UNIQUE constraint failed: HC_precision_posicion_multilaminas_anual.ref, HC_precision_posicion_multilaminas_anual.id_energia, HC_precision_posicion_multilaminas_anual.medida
Actualizando tabla de controles anuales para Halcyon
Analisis de imagen activado en subir_imagen en PruebasDiarias.py
analizando imagen
Subir imagen activado en imagenUpLoader en PruebasDiarias.py
Aceptar imagen activado en PruebasDiarias.py
Aceptar imagen activado en PruebasDiarias.py
Subiendo tabla HC_linealidad_unidades_monitor_anual normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'UM', 'Q1', 'Q2', 'Qprom'] para HC_linealidad_unidades_monitor_anual

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_linealidad_unidades_monitor_anual, id = True

▥ Datos a insertar en HC_linealidad_unidades_monitor_anual:
  - [47, 0, '50', '1', '1', '1.00']
  - [47, 0, '100', '1', '1', '1.00']
  - [47, 0, '150', '1', '1', '1.00']
  - [47, 0, '200', '1', '1', '1.00']
  - [47, 0, '250', '1', '1', '1.00']
  - [47, 0, '300', '11', '1', '6.00']
  - [47, 0, '350', '1', '1', '1.00']
  - [47, 0, '400', '1', '1', '1.00']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_linealidad_unidades_monitor_anual subida(s) correctamente
Subiendo tabla HC_tamanos_campo_radiacion normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicado_inplane', 'indicado_crossplane', 'medido_inplane', 'medido_crossplane'] para HC_tamanos_campo_radiacion

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_tamanos_campo_radiacion, id = True

▥ Datos a insertar en HC_tamanos_campo_radiacion:
  - [47, 0, '6', '6', '1', '1.2']
  - [47, 0, '8', '8', '1', '1']
  - [47, 0, '10', '10', '1', '1']
  - [47, 0, '20', '20', '1', '11']
  - [47, 0, '28', '28', '1', '1']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_tamanos_campo_radiacion subida(s) correctamente

Subiendo datos para HC_dosimetria_anual
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi'] para HC_dosimetria_anual

ADVERTENCIA: columna 'val_teo_dosis' no tiene widget correspondiente → None
ADVERTENCIA: columna 'val_teo_calidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'dosis_ref_cgy_um' no tiene widget correspondiente → None
ADVERTENCIA: columna 'discrepancia_dosis' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_dosis' no tiene widget correspondiente → None
ADVERTENCIA: columna 'calidad_pdd20_10' no tiene widget correspondiente → None
ADVERTENCIA: columna 'discrepancia_calidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_calidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'simetria_inplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'simetria_crossplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_simetria' no tiene widget correspondiente → None
ADVERTENCIA: columna 'planicidad_inplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'planicidad_crossplane' no tiene widget correspondiente → None
ADVERTENCIA: columna 'tolerancia_planicidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'observaciones_dosi' no tiene widget correspondiente → None
Nada que guardar en HC_dosimetria_anual para ref=47 (ningún widget de este guardado corresponde a una columna real).
Actualizando tabla de controles anuales para Halcyon
Datos subidos correctamente
Subiendo tabla HC_precision_posicion_multilaminas_anual normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'medida', 'esperada', 'discrepancia'] para HC_precision_posicion_multilaminas_anual

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_precision_posicion_multilaminas_anual, id = True

▥ Datos a insertar en HC_precision_posicion_multilaminas_anual:
  - [47, 0, '1.2', '1', '20.00']
  - [47, 0, '2', '1', '100.00']
  - [47, 0, '2', '1', '100.00']
  - [47, 0, '2', '1', '100.00']
  - [47, 0, '2', '1', '100.00']
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\data\ManejoDatos\load.py", line 614, in loadtablacomplex
    cursor.executemany(sql, datos)
sqlite3.IntegrityError: UNIQUE constraint failed: HC_precision_posicion_multilaminas_anual.ref, HC_precision_posicion_multilaminas_anual.id_energia, HC_precision_posicion_multilaminas_anual.medida
Actualizando tabla de controles anuales para Halcyon
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicador_medir', 'valor_medido'] para tabla_control_camaras_monitoras

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_control_camaras_monitoras, id = True

▥ Datos a insertar en tabla_control_camaras_monitoras:
  - [45, 4, 'Fac. Calibración', '1']
  - [45, 4, 'Reproducibilidad', '1']
  - [45, 4, 'Linealidad R2', '1']
  - [45, 4, 'Tasa mínima 100 cGy/min', '1']
  - [45, 4, 'Tasa máxima 400 cGy/min', '1']
  - [45, 4, 'Tasa máxima 600 cGy/min', '1']
  - [45, 4, 'Desviación estándar', '1']
  - [45, 4, 'Observaciones', '1']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_control_camaras_monitoras subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicador_medir', 'valor_medido'] para tabla_control_camaras_monitoras

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_control_camaras_monitoras, id = True

▥ Datos a insertar en tabla_control_camaras_monitoras:
  - [45, 5, 'Fac. Calibración', '1']
  - [45, 5, 'Reproducibilidad', '1']
  - [45, 5, 'Linealidad R2', '1']
  - [45, 5, 'Tasa mínima 100 cGy/min', '1']
  - [45, 5, 'Tasa máxima 400 cGy/min', '1']
  - [45, 5, 'Tasa máxima 600 cGy/min', '1']
  - [45, 5, 'Desviación estándar', '1']
  - [45, 5, 'Observaciones', '1']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_control_camaras_monitoras subida(s) correctamente
Datos tabla principal obtenidos: {'equipo': 'Clinac ix', 'fecha': '08/2027', 'user_id': 'Administrador', 'user_id_f2': ' Andres David Loaiza Baena'}
Buscando información del usuario principal: Administrador
Buscando información del usuario 2 con ID:  Andres David Loaiza Baena
Verificando datos del sistema de imágenes para Clinac ix...
No se encontraron datos del sistema de imágenes para esta sesión
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'angulo', 'factor_transmision', 'factor_transmision_esperado', 'discrepancia'] para tabla_factores_transmision

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factores_transmision, id = True

▥ Datos a insertar en tabla_factores_transmision:
  - [45, 4, '15°', '1', '1', '0.00']
  - [45, 4, '30°', '1', '1', '0.00']
  - [45, 4, '45°', '11', '1', '1000.00']
  - [45, 4, '60°', '1', '1', '0.00']
  - [45, 4, 'MLC', '1', '1', '']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_transmision subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'angulo', 'factor_transmision', 'factor_transmision_esperado', 'discrepancia'] para tabla_factores_transmision

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factores_transmision, id = True

▥ Datos a insertar en tabla_factores_transmision:
  - [45, 5, '15°', '1', '1', '0.00']
  - [45, 5, '30°', '1', '1', '0.00']
  - [45, 5, '45°', '1', '1', '0.00']
  - [45, 5, '60°', '1', '1', '0.00']
  - [45, 5, 'MLC', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_transmision subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'angulo', 'factor_transmision', 'factor_transmision_esperado', 'discrepancia'] para tabla_factores_transmision

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factores_transmision, id = True

▥ Datos a insertar en tabla_factores_transmision:
  - [45, 0, '15°', '1', '1', '0.00']
  - [45, 0, '30°', '1', '1', '0.00']
  - [45, 0, '45°', '1', '1', '0.00']
  - [45, 0, '60°', '1', '1', '0.00']
  - [45, 0, 'MLC', '1', '1', '']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_transmision subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'angulo', 'factor_transmision', 'factor_transmision_esperado', 'discrepancia'] para tabla_factores_transmision

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factores_transmision, id = True

▥ Datos a insertar en tabla_factores_transmision:
  - [45, 0, '15°', '1', '', '']
  - [45, 0, '30°', '1', '', '']
  - [45, 0, '45°', '1', '', '']
  - [45, 0, '60°', '1', '1', '0.00']
  - [45, 0, 'MLC', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_transmision subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'angulo', 'factor_transmision', 'factor_transmision_esperado', 'discrepancia'] para tabla_factores_transmision

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factores_transmision, id = True

▥ Datos a insertar en tabla_factores_transmision:
  - [45, 5, '15°', '1', '1', '0.00']
  - [45, 5, '30°', '1', '', '']
  - [45, 5, '45°', '1', '', '']
  - [45, 5, '60°', '1', '1', '0.00']
  - [45, 5, 'MLC', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_transmision subida(s) correctamente
Subiendo tabla HC_precision_posicion_multilaminas_anual normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'medida', 'esperada', 'discrepancia'] para HC_precision_posicion_multilaminas_anual

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_precision_posicion_multilaminas_anual, id = True

▥ Datos a insertar en HC_precision_posicion_multilaminas_anual:
  - [47, 0, '1.2', '1', '20.00']
  - [47, 0, '2', '', '']
  - [47, 0, '2', '', '']
  - [47, 0, '2', '1', '100.00']
  - [47, 0, '2', '1', '100.00']
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\data\ManejoDatos\load.py", line 614, in loadtablacomplex
    cursor.executemany(sql, datos)
sqlite3.IntegrityError: UNIQUE constraint failed: HC_precision_posicion_multilaminas_anual.ref, HC_precision_posicion_multilaminas_anual.id_energia, HC_precision_posicion_multilaminas_anual.medida
Actualizando tabla de controles anuales para Halcyon
Subiendo tabla HC_indicadores_camilla normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'ubicacion', 'desplazamiento', 'medido_cm', 'diferencia'] para HC_indicadores_camilla

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_indicadores_camilla, id = True

▥ Datos a insertar en HC_indicadores_camilla:
  - [47, 0, 'Longitudinal', '1', '1.2', '20.00']
  - [47, 0, 'Longitudinal', '5', '1', '80.00']
  - [47, 0, 'Longitudinal', '20', '', '']
  - [47, 0, 'Lateral', '1', '1', '0.00']
  - [47, 0, 'Lateral', '5', '11', '120.00']
  - [47, 0, 'Lateral', '20', '1', '95.00']
  - [47, 0, 'Vertical', '1', '1', '0.00']
  - [47, 0, 'Vertical', '5', '1', '80.00']
  - [47, 0, 'Vertical', '20', '1', '95.00']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_indicadores_camilla subida(s) correctamente
Subiendo tabla HC_indicadores_colimador normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'nivel', 'valor_medido', 'discrepancia'] para HC_indicadores_colimador

Bloque identificado por ['ref', 'id_energia'] para la tabla HC_indicadores_colimador, id = True

▥ Datos a insertar en HC_indicadores_colimador:
  - [47, 0, '0', '1', '1.00']
  - [47, 0, '90', '', '']
  - [47, 0, '270', '1', '269.00']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_indicadores_colimador subida(s) correctamente
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-28\respaldos_bd\BaseDatosQA_2026-08-28_104031.db

