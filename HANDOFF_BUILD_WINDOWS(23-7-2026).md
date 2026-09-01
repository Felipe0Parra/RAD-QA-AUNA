# Revision en Windows del 23-07-2026

- Hacen falta subtitulos para separar e identificar la ubicacion correspondiente de cada energia en el formulario mensual, especialmente para el iX claramente que es el que mas energias tiene.
- Por que aparecen unas flechitas al lado de la fecha en la calculadora dosimetrica, dado que esta bloqueada deberiamos eleminar cualquier simbolo o boton que haga parecer que es posible seleccionar una opcion.
- Si los valores que voy a cargar en la calculadora son para electrones y lo del kQ si funciona automatico para esta opcion que no salte la advertencia.
- Debemos habilitar una opcion de limpiar tambien, y depronto implementar una funcion que no deje editar los valores directamente desde la calculadora, bueno es que hay que pensar en una forma que evite que se sigan quedando datos pegados, hay que meditar un poco mas cual opcion es mejor, y comoda para trabajar pero confiable en terminos de mantener un control seguro desde la app, que la estrcutura de la app por si sola evite ese tipo de errores. Debemos verificar si el registro de cada calculo de la calculadora se puede visualizar desde alguna otra pestana dentro de la app.
- Definitivamente tiene que existir la opcion de limpiar.
- La ventana emergente al seleccionar la N34001 para electrones habla de fotones, y el calculo del kQ sucede normal, hay que aclarar como sucede esto, es decir, como funciona el kQ para cada camara, que datos hacen falta y de que depende para que se calcule automaticamente.
- Dejar datos pegados es un error medianamente comun en los formatos de excel y es un error que debemos garantizar que la app no permite que suceda.
- Dado que a veces a pesar de coincidir en todos los resultados, el motor de la app contra el excel, algunos valores resultantes difieren segun los datos que se meten en la calculadora, esto es resultado de dejar valores de M1 por ejemplo pegados, y como hay varias casillas donde debe aparecer, de forma erronea, se cambia uno, pero no se cambian los demas valores donde aparece, la app escoje entonces el particular para cada calculo que hace el excel, por lo que finalmente coinciden los valores, pero como en la app yo solo pongo 1 valor de M1 por ejemplo que se propaga/rellena automaticamente, no hay riesgo de que las otros calculos que lo usan reciban un valor pegado del anterior si yo solo cambie el primero por que ese cambia automaticamente, mas si estoy forzado a rellenarlo cada vez. La pregunta en este punto es, es lo mas adecuado hacer la comparacion asi? Porque el comparador me ayuda a verificar si en el excel pusieron datos a fuerza bruta y no calculados, pero no me permite identificar si quedaron datos pegados en el formato de excel, lo cual puede ser no relevante, porque lo que al final del dia importa no es el calculo particular que genera la hoja de excel sino el motor de calculo y que su precision y funcionamiento se repliquen en la app, el llenado y los errores son ajenos en este sentido entre los dos motores. (Esto es como una reflexion para tener en cuenta)
- Parece que no funciona bien aun lo de abrir un registro con fecha especifica. Y depronto debamos habilitar una funcion que permita cerrar el formulario mensual para abrir uno nuevo sin necesidad de tener que cerrar sesion. Y bloquear la fecha interna del formulario, que se deba fijar al inicio siempre donde uno asigna los fisicos. Bueno si carga cuando se pone una de las fechas que solo estan en este momento por mes y ano. La fecha ya dentro del formulario no se puede modificar, por lo tanto que sea texto bloqueado sin simbolos y eso.
- Verificar que solo el administrador puede eliminar un registro, o fisico medico jefe.
- No veo senales de soft-delete, el registro borrado donde queda en caso de querer reponerlo.
- El proceso de auditoria esta funcionando bastante bien, el llenado de la columna detalles es bastante informativo.
- Hay un registro mensual de iX que aparece en la tabla de la app en la parte mensual logicamente, que parece estar vacio, pero lo raro es que no aparece en la BD.
- Esta actualizado el selector de camaras y las series en la parte inicial de los formularios mensuales? Es decir, estan sus factores de calibracion actualizados? Parece que si.
- Veo que e registro de subir datos desde el formulario mensual crea un registro en controles, pero porque no hay nada en dosiemtriaMen? Se supone que controles, dosiemtriaMen y calculadora_dosimetrica son dependientes, no? Rompimos algo en este paso seguramente, porque como se estaban guardando entonces los registros que ya existen en esa tabla de dosimetriaMen, por que no se estan guardando ahora? ya entiendo, dosimetriaMen es unicamente para le seccion de aspectos dosimetricos. Pero cual es la tabla que se muestra en la app en el formulario mensual??

Es que hay una situacion particular que no entiendo, parece que la tabla que se muestra dentro de la app en el formulario mensual es la de controles por que, porque por ejemplo esta muestra para el iX un registro de cristian el 07/2026. Pero en dosimetriaMen no hay ningun registro con esa fecha. Sin olvidar que hicimos borrados y ediciones y aparecieron registros sin informacion de fecha y usario, etc. Y como dije anteriormente entiendo porque puede que no aparezca nada en dosimetria mensual, pero que tabla contiene entonces todas esas columnas que se muestran en la tabla de la app que parece ser controles, pero controles solo contiene unas poquitas columnas.
- Hay tambien que verificar la tabla de equipos_medicion para ver si esta actualizada, la tocamos, de que se alimenta.
- Hay que verificar las rutas, conexiones entre tablas y la creacion y carga de registros y su contraste entre lo que se muestra en la app y lo que contiene la BD.
- Despues de eliminar el registro, escribo nuevos datos en aspectos dosimetricos, y se cargan registros en la dosimetriaMen, pero sin informacion de equipo, fecha o usuario.
- Hay que ajustar los tamanos de texto de la seccion de aspectos mecanimos/resultados de aspectos mecanimos, el texto indicativo se mete dentro de la casilla donde se escribe el valor y se ubica sobre el texto de ejemplo.
- Pego lo extraido de la terminal para la prueba de llenado, guardado y carga y eliminacion del registro de la calculadora dosimetrica y subiendo el registro:

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-23> python main.py
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
iniGUI: 0.025s
load table: 0.098s
asignar_encabezados: 0.099s
button_click: 0.099s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001C11487D650>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
Físico 2 seleccionado: Cristian Castellanos, ID: 3
user_id_f2 antes de create_control: 3
Entrando a crear control
Clinac ix
Error al obtener conexión: Cannot operate on a closed database.
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
<PyQt5.QtWidgets.QGridLayout object at 0x000001C18062C040>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C18062C0D0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C18062C160>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C18062C1F0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C18062C280>
Error al obtener conexión: Cannot operate on a closed database.
Error al obtener conexión: Cannot operate on a closed database.
Error al obtener conexión: Cannot operate on a closed database.
Error al obtener conexión: Cannot operate on a closed database.
Error al obtener conexión: Cannot operate on a closed database.
Error al obtener conexión: Cannot operate on a closed database.
Error al obtener conexión: Cannot operate on a closed database.
Error al obtener conexión: Cannot operate on a closed database.
Error al obtener conexión: Cannot operate on a closed database.
Error al obtener conexión: Cannot operate on a closed database.
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Error al obtener conexión: Cannot operate on a closed database.
Error al obtener conexión: Cannot operate on a closed database.
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
Error al obtener conexión: Cannot operate on a closed database.
Error al obtener conexión: Cannot operate on a closed database.
Error al obtener conexión: Cannot operate on a closed database.
ln tolerance encontrado
⚠️ Widgets MLC no encontrados - revisar creación desde Excel
No hay datos para esta referencia.
No hay datos para esta referencia.
No hay datos para esta referencia.
Dialog llamado desde: PruebaMensualIX
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
Cociente fuera de rango (2.0 – 5.0)
300
Cociente fuera de rango (2.0 – 5.0)
300
could not convert string to float: ''
300
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
Error searching database: no such column: energia
Data saved successfully for date: 29/09/2024
Dialog llamado desde: PruebaMensualIX
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
Cociente fuera de rango (2.0 – 5.0)
300
Cociente fuera de rango (2.0 – 5.0)
300
could not convert string to float: ''
300
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
Data saved successfully for date: 29/09/2024
Dialog llamado desde: PruebaMensualIX
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
Dialog llamado desde: PruebaMensualIX
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
300
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
Dialog llamado desde: PruebaMensualIX
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
Cociente fuera de rango (2.0 – 5.0)
300
Cociente fuera de rango (2.0 – 5.0)
300
could not convert string to float: ''
300
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
Data saved successfully for date: 29/09/2024

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

Error al obtener conexión: Cannot operate on a closed database.
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025
→ Eliminando en tabla controles, WHERE "id" = ?, valores [41]
DELETE ejecutado correctamente
Fin de eliminarRegistro


- Otra entrada tratando de abrir un archivo mensual en el 600:

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-23> python main.py
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
iniGUI: 0.055s
load table: 0.193s
asignar_encabezados: 0.194s
button_click: 0.194s
Clinac 600
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x00000108400E8C90>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
Error: 'QComboBox' object has no attribute 'setText'
Error: 'QComboBox' object has no attribute 'setText'
Físico 2 seleccionado: Cristian Castellanos, ID: 3
user_id_f2 antes de create_control: 3
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
<PyQt5.QtWidgets.QGridLayout object at 0x00000108C56D55A0>
<PyQt5.QtWidgets.QGridLayout object at 0x00000108C56D5510>
<PyQt5.QtWidgets.QGridLayout object at 0x00000108C56D56C0>
<PyQt5.QtWidgets.QGridLayout object at 0x00000108C56D5630>
<PyQt5.QtWidgets.QGridLayout object at 0x00000108C56D5750>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
DF LINES: 
['val_teo_6mv', 'ln_dosis_ref_cgy_um_6mv', 'ln_discrepancia_dosis_6mv', 'ln_tolerancia_dosis', 'ln_calidad_pdd20_10_6mv', 'ln_discrepancia_calidad_6mv', 'ln_tolerancia_calidad', 'ln_simetria_inplane_6mv', 'ln_simetria_crossplane_6mv', 'ln_tolerancia_simetria', 'ln_planicidad_inplane_6mv', 'ln_planicidad_crossplane_6mv', 'ln_tolerancia_planicidad', 'ln_observaciones_dosi']
Widget 'ln_dosis_ref_cgy_um_15mv' no encontrado
Widget 'ln_dosis_ref_cgy_um_6mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_9mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_12mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_15mev' no encontrado