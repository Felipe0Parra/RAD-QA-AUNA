# Rebuild Windows 25 de Agosto de 2026

Anotaciones:
- importante tener en cuenta que no hemos hecho realmente pruebas en TAC ni cosas de picketfence al menos con consciencia de lo que debe dar, por lo cual esos errores no se habian notado antes, igual en el futuro habra que repararlos.

md5 inicial: 7DEB6C7CD4B01AB6912D56E8DEB50164
md5 final, luego de la migracion: 7EC6F5529108669773B49ABAF686EB0C. Cambia un poco.

- La terminal no emite los mensajes de MI1 luego de iniciar la app, ni la segunda vez al iniciar la app, o no se si yo no veo los mensajes en particular, revisa tu la expulsion de la terminal que se presenta mas adelante en este documento.

- No se que tan conveniente es que al anular un control los valores de algunas de sus tablas hijas no se anulen inmediatamente tambien, creo que no es coherente, por ejemplo para el control anulado del 25/08/2026 si se pone en cero el activo de la tabla controles pero no se ponen en cero los valores del ultimo bloque creado en este control de la tabla control_cunas o control_conos, ni en la tabla equipos, seguro entre otras. Esto parece funcionar bien puesto que la columna activo del control es parte del identificador, hay que asegurarnos de que esta discriminacion se este aplicando para todos los guardados que sea necesario en al BD, funciona por la misma razon que funciona guardar bloques en activo/no activo, porque para crear uno nuevo siempre se necesita anular al anterior si se trabaja en la misma fecha por lo cual nunca van a existir duplicados, si siempre existe el identificador de activo cuando sea necesario, como en el caso de controles para los bloques en diferentes tablas. Funciona bien, pero esto es supremamente sensible si no se tiene en al ref el valor de activo de la tabla padre o raiz de ese registro. Hay que verificarlo con maxima atencion luego. (Esto no es necesariamente una correccion es una reflexion y estoy creo contento con el resultado, se puede revisar igual)

- Esta funcionando bastante bien el guardado del analisis de placa en la tabla preguntas segun veo, se guarda lo que haya en texto cuando se sube la imagen, si no hay nada en texto pues rellena con null y si luego se rellena y se sube ambos convergen en un nuevo registro con ambas cosas, un poco cargado pero funciona bien y coherente con todo lo demas.

- Aun no se bloquean los botones de seleccion de energia por tipo de radiacion de la calculadora al cargar un calculo anterior.

- En tablas como la calculadora_dosimetrica se deberia rellenar con null los campos intencionalmente vacios debido a la naturaleza del calculo???

- Cuando se sube una imagen con 96 DPI sale una ventana emergente que dice que el analisis no se completo por lo que no hay datos por guardar. Y el boton queda desahabilitado.

- La imagen guardada del analisis de la placa para el control mensual aparece luego de volver a abrir el registro, sin embargo, sigue apareciendo lo de subir imangen, y no se carga el analisis junto con ella, es decir, no se cargan los graficos del perfil, preferiria que aparecieran ya que la intencion de cargar nuevamente todo es para verificar que todo haya quedado como se espera(importante). Debemos tener en cuenta este funcionamiento en caso de que haya que reparar el analisis de placa de braquiterapia usando las mismas herramientas. Deberian volverse a ver los graficos tal cual.

- El guardado de las tablas de analisis de placa esta funcionando bastante bien segun veo.

- Hay un error al momento de crear un control mensual que no habia notado, puesto que si no selecciono ningun fisico salta la ventana emergente con el error de que el Fisico 1 no existe en la base de datos, le doy Okay o lo que sea que muestra de opcion e igual se crea el registro, se debe bloquear el acceso si no se ha seleccionado al fisico 1 y al 2, y no crear el registro hasta que se hayan seleccionado, es importante, pero no es un error que destruya todo el proceso, se puede jugar con su prioridad dentro del plan.

- La fecha dentro del control mensual se sigue pudiendo modificar, aqui tenemos dos opciones, o la bloqueamos, la mas facil o hacemos que al cambiarla se construya un nuevo registro si es una fecha de un mes en el que no hay control (Esto deberia tener barreras para prohibir crear control mas de un control dentro del mismo mes) y abrir el control correspondiente al mes seleccionado sin importar el dia si existe un control para ese mes.

- En una de las muchas selecciones de imagen que hice para la parte de analisis mecanico imagen de campo, el ultimo que hice o el de las 9:56 no mostro el icono de carga al lado del cursor, pues al principio si pero desaparecio rapidamente justo despues de haberle dado enter luego de haber acomodado manualmente los puntos dejo de aparecer el icono de carga, aun aparecia el texto de analizando imagen y seguia bloqueado el boton de guardar pero pues si. Un comportamiento anormal comparado con los anteriores casos.

- Si se deja un cono sin marcar en el formulario mensual y se le da guardar sale una alerta de que falta por marcar uno de los conos, luego inmediatamente sale el mensaje de que fueron cargados exitosamente los datos en la BD. Si se cargan como No funciona los valores no marcados de las cunas, osea, hay un error aqui, no deberia guardarse nada, de los conos parece que no hay nada en la fecha 20/01/2027. Pero para las cunas si, depronto por esto fue el doble mensaje contradictorio, hay que unificar el guardado.

- Para el cambio de fuente en Braquiterapia se puede cargar el dia que se hizo el cambio de fuente poniendo la fecha correspondiente al que ya existe, se cargan los datos de las tablas de maximos de camara y lecturas, se cargan condiciones de medicion, se cargan los equipos sin serie, pero creo que los valores mostrados no coinciden con los guardados, creo que se estan mezclando los datos que se cargan porque para el 26/06/2026 hay una calibracion redundante y un cambio de fuente y pareciera que ambos llenan esa tabla, no se como esta distinguiendo entre calibracion redundante y cambio de fuente, siento que se estan cruzando los cables porque con el boton de cambio de fuente seleccionado le doy reporte y genera un documento que dice calibracion redundante. Ahora,el control carga para lo que hay guardado en el cambio de fuente para la tabla de lecturas del maximo y condiciones de medicion, aqui hay un enredo, ese boton puede ser nuestro camino para decidir. El boton de limpiar si limpia todo pero el no se puede ni siquiera guardar con todos los campos llenos el control el boton aparece inhabilitado. 

- En braquiterapia aun hace falta que se limpie automaticamente cuando escojo un dia nuevo en la parte diaria.

- Con lo de revisar que aparezca el valor de dosis de referencia te refieres a la parte de dosimetria del control mensual? Pues si, la calculada.









Expulsion de la terminal para la construccion del ejecutable:

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2> .\.venv\Scripts\python.exe build_exe.py
98 INFO: PyInstaller: 6.21.0, contrib hooks: 2026.7
98 INFO: Python: 3.11.0
115 INFO: Platform: Windows-10-10.0.26200-SP0
115 INFO: Python environment: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\.venv
116 INFO: wrote C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\RAD-QA.spec
118 INFO: Removing temporary files and cleaning cache in C:\Users\parra\AppData\Local\pyinstaller
6963 INFO: Module search paths (PYTHONPATH):
['C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311\\python311.zip',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311\\DLLs',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311\\Lib',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\win32',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\win32\\lib',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\pythonwin',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2']
7240 INFO: Appending 'datas' from .spec
7247 INFO: checking Analysis
7248 INFO: Building Analysis because Analysis-00.toc is non existent
7248 INFO: Looking for Python shared library...
7248 INFO: Using Python shared library: C:\Users\parra\AppData\Local\Programs\Python\Python311\python311.dll
7248 INFO: Running Analysis Analysis-00.toc
7248 INFO: Target bytecode optimization level: 0
7248 INFO: Initializing module dependency graph...
7249 INFO: Initializing module graph hook caches...
7276 INFO: Analyzing modules for base_library.zip ...
8115 INFO: Processing standard module hook 'hook-heapq.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
8231 INFO: Processing standard module hook 'hook-encodings.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
9636 INFO: Processing standard module hook 'hook-math.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
9796 INFO: Processing standard module hook 'hook-pickle.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
12751 INFO: Caching module dependency graph...
12771 INFO: Analyzing C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\main.py
12791 INFO: Processing standard module hook 'hook-PyQt5.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
13311 INFO: Processing standard module hook 'hook-PyQt5.QtWidgets.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
14643 INFO: Processing standard module hook 'hook-PyQt5.QtCore.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
16295 INFO: Processing standard module hook 'hook-PyQt5.QtGui.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
23889 INFO: Processing standard module hook 'hook-sqlite3.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
24158 INFO: Processing standard module hook 'hook-cryptography.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
25093 INFO: hook-cryptography: cryptography does not seem to be using dynamically linked OpenSSL.
25212 INFO: Processing standard module hook 'hook-numpy.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
25550 INFO: Processing standard module hook 'hook-difflib.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
25861 INFO: Processing standard module hook 'hook-multiprocessing.util.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
26055 INFO: Processing standard module hook 'hook-xml.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
26417 INFO: Processing standard module hook 'hook-_ctypes.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
27134 INFO: Processing standard module hook 'hook-sysconfig.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
27217 INFO: Processing standard module hook 'hook-platform.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
27746 INFO: Processing standard module hook 'hook-webbrowser.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
28285 INFO: Processing pre-safe-import-module hook 'hook-typing_extensions.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
28286 INFO: SetuptoolsInfo: initializing cached setuptools info...
29070 INFO: Processing standard module hook 'hook-charset_normalizer.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
29330 INFO: Processing standard module hook 'hook-PyQt5.QtSql.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
29818 INFO: Processing standard module hook 'hook-pandas.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
31449 INFO: Processing standard module hook 'hook-pytz.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
31701 INFO: Processing standard module hook 'hook-scipy.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
32188 INFO: Processing standard module hook 'hook-pycparser.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
32273 INFO: Processing standard module hook 'hook-setuptools.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
32277 INFO: Processing pre-safe-import-module hook 'hook-distutils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
32277 INFO: Processing pre-find-module-path hook 'hook-distutils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_find_module_path'
32718 INFO: Processing standard module hook 'hook-distutils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
32796 INFO: Processing standard module hook 'hook-distutils.util.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
32854 INFO: Processing standard module hook 'hook-_osx_support.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
33082 INFO: Processing standard module hook 'hook-pkg_resources.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
33860 INFO: Processing pre-safe-import-module hook 'hook-importlib_metadata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
33918 INFO: Processing pre-safe-import-module hook 'hook-packaging.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
34756 INFO: Processing standard module hook 'hook-scipy.linalg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
34871 INFO: Processing standard module hook 'hook-scipy.special._ufuncs.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
35468 INFO: Processing standard module hook 'hook-scipy.spatial._ckdtree.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
35517 INFO: Processing standard module hook 'hook-matplotlib.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
35815 INFO: Processing pre-safe-import-module hook 'hook-gi.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
35970 INFO: Processing standard module hook 'hook-matplotlib.backend_bases.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
36037 INFO: Processing standard module hook 'hook-PIL.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
36149 INFO: Processing standard module hook 'hook-PIL.Image.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
36438 INFO: Processing standard module hook 'hook-xml.etree.cElementTree.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
36601 INFO: Processing standard module hook 'hook-PIL.ImageFilter.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
37014 INFO: Processing standard module hook 'hook-matplotlib.backends.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
37051 INFO: Processing standard module hook 'hook-matplotlib.pyplot.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
37727 INFO: Processing standard module hook 'hook-dateutil.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
37765 INFO: Processing pre-safe-import-module hook 'hook-six.moves.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
38773 INFO: Processing standard module hook 'hook-scipy.spatial.transform.rotation.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
39522 INFO: Processing standard module hook 'hook-scipy.stats._stats.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
39828 INFO: Processing standard module hook 'hook-scipy.sparse.csgraph.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
40412 INFO: Processing standard module hook 'hook-scipy.special._ellip_harm_2.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
41896 INFO: Processing standard module hook 'hook-pandas.io.formats.style.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
43166 INFO: Processing standard module hook 'hook-pandas.plotting.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
43555 INFO: Processing standard module hook 'hook-openpyxl.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
44498 INFO: Processing standard module hook 'hook-pandas.io.clipboard.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
44814 INFO: Processing standard module hook 'hook-xml.dom.domreg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
45348 INFO: Processing standard module hook 'hook-reportlab.lib.utils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
45447 INFO: Processing standard module hook 'hook-reportlab.pdfbase._fontdata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
46734 INFO: Processing standard module hook 'hook-pydicom.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
47406 INFO: Processing pre-safe-import-module hook 'hook-importlib_resources.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
51283 INFO: Processing standard module hook 'hook-pyqtgraph.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
265 WARNING: Failed to collect submodules for 'pyqtgraph.opengl' because importing 'pyqtgraph.opengl' raised: ModuleNotFoundError: No module named 'OpenGL'
51925 INFO: hook-pyqtgraph: selected 'PyQt5' as Qt bindings because hook for 'PyQt5' has been run before.
51941 INFO: Processing standard module hook 'hook-PyQt5.uic.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
52091 INFO: Processing pre-find-module-path hook 'hook-PyQt5.uic.port_v2.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_find_module_path'
52137 INFO: Processing standard module hook 'hook-PyQt5.QtSvg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
53050 INFO: Processing standard module hook 'hook-PyQt5.QtTest.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
54391 INFO: Processing standard module hook 'hook-matplotlib.backends.backend_qtagg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
54395 INFO: Processing standard module hook 'hook-matplotlib.backends.qt_compat.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
54395 INFO: hook-matplotlib.backends.qt_compat: selected 'PyQt5' as Qt bindings because hook for 'PyQt5' has been run before.
55022 INFO: Processing standard module hook 'hook-plotly.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
55946 INFO: Processing standard module hook 'hook-narwhals.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
59268 INFO: Processing standard module hook 'hook-skimage.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
59325 INFO: Processing standard module hook 'hook-skimage.measure.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
60172 INFO: Processing standard module hook 'hook-pydantic.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
60878 INFO: Processing standard module hook 'hook-zoneinfo.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
61378 INFO: Processing standard module hook 'hook-dns.rdata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
61804 INFO: Processing standard module hook 'hook-pythoncom.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
61882 INFO: Processing standard module hook 'hook-pywintypes.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
62315 INFO: Processing standard module hook 'hook-skimage.filters.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
63433 INFO: Processing standard module hook 'hook-skimage.draw.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
63850 INFO: Processing standard module hook 'hook-skimage.transform.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
64404 INFO: Processing standard module hook 'hook-skimage.segmentation.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
64844 INFO: Processing standard module hook 'hook-skimage.exposure.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
65302 INFO: Processing standard module hook 'hook-skimage.morphology.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
65825 INFO: Processing standard module hook 'hook-skimage.feature.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
66491 INFO: Processing standard module hook 'hook-cv2.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
67040 INFO: Processing standard module hook 'hook-msoffcrypto.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
67160 INFO: Processing pre-safe-import-module hook 'hook-win32com.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\pre_safe_import_module'
67233 INFO: Processing standard module hook 'hook-win32com.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
68015 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.IX'
68039 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.halcyon'
68074 INFO: Analyzing hidden import 'ui.paginasControles.PruebasMensuales.ix_mensual'
68089 INFO: Analyzing hidden import 'ui.paginasControles.PruebasMensuales.tac_mensual'
68248 INFO: Analyzing hidden import 'ui.paginasControles.PruebasAnuales.ix_anual'
68299 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.seiscientos'
68313 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.braquiterapia'
68504 INFO: Analyzing hidden import 'pylinac.contrib'
68504 INFO: Analyzing hidden import 'pylinac.contrib.orthogonality'
68507 INFO: Analyzing hidden import 'pylinac.contrib.quasar'
68508 INFO: Analyzing hidden import 'pylinac.core.metrics'
68508 INFO: Analyzing hidden import 'pylinac.dlg'
68510 INFO: Analyzing hidden import 'pylinac.nuclear'
68536 INFO: Analyzing hidden import 'pylinac.plan_generator'
68537 INFO: Analyzing hidden import 'pylinac.plan_generator.dicom'
68559 INFO: Processing module hooks (post-graph stage)...
68641 WARNING: Hidden import "pycparser.lextab" not found!
68641 WARNING: Hidden import "pycparser.yacctab" not found!
68788 INFO: Processing pre-safe-import-module hook 'hook-tomli.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
68994 INFO: Processing standard module hook 'hook-skimage.color.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
69485 INFO: Processing standard module hook 'hook-skimage.restoration.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
69951 INFO: Processing standard module hook 'hook-skimage.metrics.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
70549 INFO: Processing standard module hook 'hook-matplotlib.backends.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
70550 INFO: Matplotlib backend selection method: automatic discovery of used backends
70581 INFO: Discovered Matplotlib backend(s) via `matplotlib.use()` call in module 'models.PDF.Mensuales.reportes_mensuales': ['Agg', 'Agg', 'Agg']
70616 INFO: The following Matplotlib backends were discovered by scanning for `matplotlib.use()` calls: ['Agg']. If your backend of choice is not in this list, either add a `matplotlib.use()` call to your code, or configure the backend collection via hook options (see: https://pyinstaller.org/en/stable/hooks-config.html#matplotlib-hooks).
70617 INFO: Selected matplotlib backends: ['Agg']
70872 INFO: Processing standard module hook 'hook-PIL.SpiderImagePlugin.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
71293 WARNING: Hidden import "scipy.special._cdflib" not found!
71326 INFO: Processing standard module hook 'hook-setuptools._vendor.importlib_metadata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
71385 INFO: Processing standard module hook 'hook-setuptools._vendor.jaraco.text.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
71907 INFO: Processing standard module hook 'hook-tzdata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
72317 INFO: Performing binary vs. data reclassification (1844 entries)
80770 INFO: Looking for ctypes DLLs
80918 INFO: Analyzing run-time hooks ...
80933 INFO: Including run-time hook 'pyi_rth_mplconfig.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
80934 INFO: Processing pre-find-module-path hook 'hook-_pyi_rth_utils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_find_module_path'
80936 INFO: Processing standard module hook 'hook-_pyi_rth_utils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
80940 INFO: Including run-time hook 'pyi_rth_pkgutil.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
80942 INFO: Including run-time hook 'pyi_rth_multiprocessing.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
80943 INFO: Including run-time hook 'pyi_rth_setuptools.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
80944 INFO: Including run-time hook 'pyi_rth_pkgres.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
80947 INFO: Including run-time hook 'pyi_rth_pywintypes.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
80947 INFO: Including run-time hook 'pyi_rth_pythoncom.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
80948 INFO: Including run-time hook 'pyi_rth_inspect.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
80950 INFO: Including run-time hook 'pyi_rth_pyqt5.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
80952 INFO: Including run-time hook 'pyi_rth_pyqtgraph_multiprocess.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
80953 INFO: Including run-time hook 'pyi_rth_cryptography_openssl.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
81017 INFO: Creating base_library.zip...
81030 INFO: Looking for dynamic libraries
83870 INFO: Extra DLL search directories (AddDllDirectory): ['C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyQt5\\Qt5\\bin', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\numpy.libs', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\scipy.libs', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\pandas.libs', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\cv2\\../../x64/vc14/bin']
83870 INFO: Extra DLL search directories (PATH): ['C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\cv2\\../../x64/vc14/bin', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyQt5\\Qt5\\bin']
86350 WARNING: Library not found: could not resolve 'LIBPQ.dll', dependency of 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-25-2\\.venv\\Lib\\site-packages\\PyQt5\\Qt5\\plugins\\sqldrivers\\qsqlpsql.dll'.
86687 INFO: Warnings written to C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\build\RAD-QA\warn-RAD-QA.txt
86921 INFO: Graph cross-reference written to C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\build\RAD-QA\xref-RAD-QA.html
87003 INFO: checking PYZ
87003 INFO: Building PYZ because PYZ-00.toc is non existent
87003 INFO: Building PYZ (ZlibArchive) C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\build\RAD-QA\PYZ-00.pyz
89242 INFO: Building PYZ (ZlibArchive) C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\build\RAD-QA\PYZ-00.pyz completed successfully.
89290 INFO: checking PKG
89291 INFO: Building PKG because PKG-00.toc is non existent
89291 INFO: Building PKG (CArchive) RAD-QA.pkg
89331 INFO: Building PKG (CArchive) RAD-QA.pkg completed successfully.
89332 INFO: Bootloader C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\.venv\Lib\site-packages\PyInstaller\bootloader\Windows-64bit-intel\runw.exe
89332 INFO: checking EXE
89332 INFO: Building EXE because EXE-00.toc is non existent
89332 INFO: Building EXE from EXE-00.toc
89332 INFO: Copying bootloader EXE to C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\build\RAD-QA\RAD-QA.exe
89403 INFO: Copying icon to EXE
89437 INFO: Copying 0 resources to EXE
89437 INFO: Embedding manifest in EXE
89484 INFO: Appending PKG archive to EXE
89557 INFO: Fixing EXE headers
89863 INFO: Building EXE from EXE-00.toc completed successfully.
89873 INFO: checking COLLECT
89873 INFO: Building COLLECT because COLLECT-00.toc is non existent
89874 INFO: Building COLLECT COLLECT-00.toc
91755 INFO: Building COLLECT COLLECT-00.toc completed successfully.
91775 INFO: Build complete! The results are available in: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\dist
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2>

- Expulsion de la terminal para la previsualizacion del resultado de la herramienta de migracion:

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2> .venv\Scripts\python scripts\migrar_bd_a_estandar.py "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\BaseDatosQA.db"
Base de datos: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\BaseDatosQA.db
integrity_check antes: ok

[MODO DRY-RUN] No se modifica el archivo original. Use --aplicar para aplicar los cambios de verdad.

E10: sqlite_sequence normalizada para HC_desplazamiento_isocentro_mensual (duplicados -> seq=15)
E10: sqlite_sequence normalizada para HC_dosimetria_anual (duplicados -> seq=3)
E10: sqlite_sequence normalizada para HC_fantomas (duplicados -> seq=3)
E10: sqlite_sequence normalizada para HC_imagen_perfil_mlc_anual (duplicados -> seq=4)
E10: sqlite_sequence normalizada para HC_indicadores_brazo (duplicados -> seq=36)
E10: sqlite_sequence normalizada para HC_indicadores_camilla (duplicados -> seq=81)
E10: sqlite_sequence normalizada para HC_indicadores_colimador (duplicados -> seq=27)
E10: sqlite_sequence normalizada para HC_indicadores_laser (duplicados -> seq=27)
E10: sqlite_sequence normalizada para HC_linealidad_unidades_monitor_anual (duplicados -> seq=32)
E10: sqlite_sequence normalizada para HC_precision_posicion_multilaminas_anual (duplicados -> seq=20)
E10: sqlite_sequence normalizada para HC_tamanos_campo_radiacion (duplicados -> seq=37)
E10: sqlite_sequence normalizada para HC_velocidad_multilaminas_anual (duplicados -> seq=16)
E10: sqlite_sequence normalizada para LinealidadBraquiterapia (duplicados -> seq=10)
E10: sqlite_sequence normalizada para TipoCalibracion (duplicados -> seq=35)
E10: sqlite_sequence normalizada para aceleradorlineal_600 (duplicados -> seq=368)
E10: sqlite_sequence normalizada para aceleradorlineal_ix (duplicados -> seq=376)
E10: sqlite_sequence normalizada para braqui (duplicados -> seq=433)
E10: sqlite_sequence normalizada para control_conos (duplicados -> seq=89)
E10: sqlite_sequence normalizada para control_cunas (duplicados -> seq=180)
E10: sqlite_sequence normalizada para controles_mensuales (duplicados -> seq=109)
E10: sqlite_sequence normalizada para energias (duplicados -> seq=5)
E10: sqlite_sequence normalizada para equipos (duplicados -> seq=81)
E10: sqlite_sequence normalizada para equipos_medicion (duplicados -> seq=273)
E10: sqlite_sequence normalizada para equipos_mensual (duplicados -> seq=87)
E10: sqlite_sequence normalizada para halcyon (duplicados -> seq=326)
E10: sqlite_sequence normalizada para pruebas (duplicados -> seq=187)
E10: sqlite_sequence normalizada para resolucion_contraste_rois (duplicados -> seq=216)
E10: sqlite_sequence normalizada para resolucion_espacial_regiones (duplicados -> seq=240)
E10: sqlite_sequence normalizada para tabla_control_camaras_monitoras (duplicados -> seq=126)
E10: sqlite_sequence normalizada para tabla_factor_campo (duplicados -> seq=168)
E10: sqlite_sequence normalizada para tabla_factores_sobre_eje (duplicados -> seq=207)
E10: sqlite_sequence normalizada para tabla_factores_transmision (duplicados -> seq=140)
E10: sqlite_sequence normalizada para uniformidad_ruido (duplicados -> seq=135)
E10: sqlite_sequence normalizada para users (duplicados -> seq=13)
E10: sqlite_sequence normalizada para valores_ct (duplicados -> seq=196)
F1: 58 tablas con borrado en cascada -- respaldando antes de recrear el esquema en RESTRICT...
Respaldo de la base de datos creado en: C:\Users\parra\AppData\Local\Temp\tmpt2rx2wqg\respaldos_bd\pre_migracion\BaseDatosQA_2026-08-25_154210.db
E10: migrando 58 tablas a ON DELETE RESTRICT...
EB2d: angulo_starshot migrada -- UNIQUE(ref, spoke_index) de tabla retirado (el índice parcial de CL1 ya cubre lo mismo, respetando 'activo').

--- Cambios de esquema ---
  Tablas nuevas creadas: ['angulos_entre_lineas_starshot', 'audit_log']
  CondicionesMedicion: columna(s) nueva(s) ['activo']
  HC_desplazamiento_isocentro_mensual: columna(s) nueva(s) ['activo']
  HC_dosimetria_anual: columna(s) nueva(s) ['activo']
  HC_fantomas: columna(s) nueva(s) ['activo']
  HC_imagen_perfil_mlc_anual: columna(s) nueva(s) ['activo']
  HC_indicadores_brazo: columna(s) nueva(s) ['activo']
  HC_indicadores_camilla: columna(s) nueva(s) ['activo']
  HC_indicadores_colimador: columna(s) nueva(s) ['activo']
  HC_indicadores_laser: columna(s) nueva(s) ['activo']
  HC_linealidad_unidades_monitor_anual: columna(s) nueva(s) ['activo']
  HC_precision_posicion_multilaminas_anual: columna(s) nueva(s) ['activo']
  HC_tamanos_campo_radiacion: columna(s) nueva(s) ['activo']
  HC_velocidad_multilaminas_anual: columna(s) nueva(s) ['activo']
  LecturasMaximos: columna(s) nueva(s) ['activo']
  LinealidadBraquiterapia: columna(s) nueva(s) ['activo']
  MaximosCamaras: columna(s) nueva(s) ['activo']
  ResultadosActividad: columna(s) nueva(s) ['activo']
  SistemaMedicion: columna(s) nueva(s) ['activo']
  TipoCalibracion: columna(s) nueva(s) ['activo']
  aceleradorlineal_600: columna(s) nueva(s) ['activo']
  aceleradorlineal_ix: columna(s) nueva(s) ['activo']
  analisis_placa_correcciones: columna(s) nueva(s) ['activo']
  analisis_placa_franjas: columna(s) nueva(s) ['activo']
  analisis_placa_verificaciones: columna(s) nueva(s) ['activo']
  angulo_starshot: columna(s) nueva(s) ['activo']
  braqui: columna(s) nueva(s) ['activo']
  calculadora_dosimetrica: columna(s) nueva(s) ['energia', 'pdd_zref_electrones', 'protocolo_trs398', 'r50_medido', 'tension_negativa', 'tpr2010', 'vigente']
  configuracion_picketfence: columna(s) nueva(s) ['activo']
  configuracion_starshot: columna(s) nueva(s) ['activo']
  control_conos: columna(s) nueva(s) ['activo']
  control_cunas: columna(s) nueva(s) ['activo']
  controles: columna(s) nueva(s) ['activo']
  dosimetriaMen: columna(s) nueva(s) ['activo']
  equipos_medicion: columna(s) nueva(s) ['activo', 'equipo_id']
  error_picket: columna(s) nueva(s) ['activo']
  espesor_corte: columna(s) nueva(s) ['activo']
  estadisticas_starshot: columna(s) nueva(s) ['activo']
  halcyon: columna(s) nueva(s) ['activo']
  highest_leaf_errors: columna(s) nueva(s) ['activo']
  indicadores_angulares_colimador: columna(s) nueva(s) ['activo']
  indicadores_brazo: columna(s) nueva(s) ['activo']
  leaf_error: columna(s) nueva(s) ['activo']
  linealidad_ct: columna(s) nueva(s) ['activo']
  preguntas: columna(s) nueva(s) ['activo']
  pruebas: columna(s) nueva(s) ['activo']
  resolucion_contraste: columna(s) nueva(s) ['activo']
  resolucion_contraste_rois: columna(s) nueva(s) ['activo']
  resolucion_espacial: columna(s) nueva(s) ['activo']
  resolucion_espacial_regiones: columna(s) nueva(s) ['activo']
  tabla_control_camaras_monitoras: columna(s) nueva(s) ['activo']
  tabla_factor_campo: columna(s) nueva(s) ['activo']
  tabla_factores_sobre_eje: columna(s) nueva(s) ['activo']
  tabla_factores_transmision: columna(s) nueva(s) ['activo']
  tamano_campo: columna(s) nueva(s) ['activo']
  tamaño_pixel: columna(s) nueva(s) ['activo']
  uniformidad_angular_starshot: columna(s) nueva(s) ['activo']
  uniformidad_global: columna(s) nueva(s) ['activo']
  uniformidad_ruido: columna(s) nueva(s) ['activo']
  users: columna(s) nueva(s) ['rol_sistema']
  valores_ct: columna(s) nueva(s) ['activo']

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

--- Saneamiento de claves duplicadas del bloque de QC (SA1, DA-38) ---
  121 fila(s) pasadas a histórica (activo=0), cero borradas:
    HC_indicadores_camilla: 9 fila(s)
      rowid=55 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Longitudinal', 'desplazamiento': 1.0} -- gana rowid=64
      rowid=56 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Longitudinal', 'desplazamiento': 5.0} -- gana rowid=65
      rowid=57 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Longitudinal', 'desplazamiento': 20.0} -- gana rowid=66
      rowid=58 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Lateral', 'desplazamiento': 1.0} -- gana rowid=67
      rowid=59 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Lateral', 'desplazamiento': 5.0} -- gana rowid=68
      rowid=60 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Lateral', 'desplazamiento': 20.0} -- gana rowid=69
      rowid=61 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Vertical', 'desplazamiento': 1.0} -- gana rowid=70
      rowid=62 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Vertical', 'desplazamiento': 5.0} -- gana rowid=71
      rowid=63 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Vertical', 'desplazamiento': 20.0} -- gana rowid=72
    HC_indicadores_colimador: 3 fila(s)
      rowid=19 clave={'ref': 33, 'id_energia': 0, 'nivel': 0.0} -- gana rowid=22
      rowid=20 clave={'ref': 33, 'id_energia': 0, 'nivel': 90.0} -- gana rowid=23
      rowid=21 clave={'ref': 33, 'id_energia': 0, 'nivel': 270.0} -- gana rowid=24
    HC_indicadores_laser: 3 fila(s)
      rowid=19 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Longitudinal'} -- gana rowid=22
      rowid=20 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Vertical'} -- gana rowid=23
      rowid=21 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Lateral'} -- gana rowid=24
    aceleradorlineal_600: 2 fila(s)
      rowid=121 clave={'DATE(date)': '2025-07-24'} -- gana rowid=122
      rowid=212 clave={'DATE(date)': '2025-12-16'} -- gana rowid=213
    aceleradorlineal_ix: 30 fila(s)
      rowid=2 clave={'DATE(date)': '2025-03-04'} -- gana rowid=40
      rowid=3 clave={'DATE(date)': '2025-03-05'} -- gana rowid=41
      rowid=4 clave={'DATE(date)': '2025-03-10'} -- gana rowid=42
      rowid=5 clave={'DATE(date)': '2025-03-25'} -- gana rowid=43
      rowid=6 clave={'DATE(date)': '2025-03-26'} -- gana rowid=44
      rowid=7 clave={'DATE(date)': '2025-03-27'} -- gana rowid=45
      rowid=8 clave={'DATE(date)': '2025-03-28'} -- gana rowid=46
      rowid=9 clave={'DATE(date)': '2025-04-01'} -- gana rowid=47
      rowid=10 clave={'DATE(date)': '2025-04-02'} -- gana rowid=48
      rowid=11 clave={'DATE(date)': '2025-04-03'} -- gana rowid=49
      rowid=12 clave={'DATE(date)': '2025-04-04'} -- gana rowid=50
      rowid=13 clave={'DATE(date)': '2025-04-07'} -- gana rowid=51
      rowid=14 clave={'DATE(date)': '2025-04-08'} -- gana rowid=52
      rowid=15 clave={'DATE(date)': '2025-04-09'} -- gana rowid=53
      rowid=16 clave={'DATE(date)': '2025-04-10'} -- gana rowid=54
      rowid=17 clave={'DATE(date)': '2025-04-11'} -- gana rowid=55
      rowid=18 clave={'DATE(date)': '2025-04-14'} -- gana rowid=56
      rowid=19 clave={'DATE(date)': '2025-04-15'} -- gana rowid=57
      rowid=20 clave={'DATE(date)': '2025-04-16'} -- gana rowid=58
      rowid=21 clave={'DATE(date)': '2025-04-21'} -- gana rowid=59
      rowid=22 clave={'DATE(date)': '2025-04-24'} -- gana rowid=60
      rowid=23 clave={'DATE(date)': '2025-04-25'} -- gana rowid=61
      rowid=24 clave={'DATE(date)': '2025-04-28'} -- gana rowid=62
      rowid=25 clave={'DATE(date)': '2025-04-22'} -- gana rowid=63
      rowid=26 clave={'DATE(date)': '2025-04-23'} -- gana rowid=64
      rowid=27 clave={'DATE(date)': '2025-04-29'} -- gana rowid=65
      rowid=28 clave={'DATE(date)': '2025-04-30'} -- gana rowid=66
      rowid=29 clave={'DATE(date)': '2025-05-02'} -- gana rowid=67
      rowid=127 clave={'DATE(date)': '2025-07-31'} -- gana rowid=128
      rowid=187 clave={'DATE(date)': '2025-10-27'} -- gana rowid=188
    analisis_placa_correcciones: 8 fila(s)
      rowid=1 clave={'ref': 16, 'vertice': 'arriba_izq'} -- gana rowid=5
      rowid=2 clave={'ref': 16, 'vertice': 'arriba_der'} -- gana rowid=6
      rowid=3 clave={'ref': 16, 'vertice': 'abajo_izq'} -- gana rowid=7
      rowid=4 clave={'ref': 16, 'vertice': 'abajo_der'} -- gana rowid=8
      rowid=13 clave={'ref': 15, 'vertice': 'arriba_izq'} -- gana rowid=17
      rowid=14 clave={'ref': 15, 'vertice': 'arriba_der'} -- gana rowid=18
      rowid=15 clave={'ref': 15, 'vertice': 'abajo_izq'} -- gana rowid=19
      rowid=16 clave={'ref': 15, 'vertice': 'abajo_der'} -- gana rowid=20
    analisis_placa_franjas: 6 fila(s)
      rowid=1 clave={'ref': 16, 'franja': 'Franja 1'} -- gana rowid=4
      rowid=2 clave={'ref': 16, 'franja': 'Franja 2'} -- gana rowid=5
      rowid=3 clave={'ref': 16, 'franja': 'Franja 3'} -- gana rowid=6
      rowid=10 clave={'ref': 15, 'franja': 'Franja 1'} -- gana rowid=13
      rowid=11 clave={'ref': 15, 'franja': 'Franja 2'} -- gana rowid=14
      rowid=12 clave={'ref': 15, 'franja': 'Franja 3'} -- gana rowid=15
    analisis_placa_verificaciones: 4 fila(s)
      rowid=1 clave={'ref': 16, 'tipo': 'verificacion_inicial'} -- gana rowid=3
      rowid=2 clave={'ref': 16, 'tipo': 'verificacion_ideal'} -- gana rowid=4
      rowid=7 clave={'ref': 15, 'tipo': 'verificacion_inicial'} -- gana rowid=9
      rowid=8 clave={'ref': 15, 'tipo': 'verificacion_ideal'} -- gana rowid=10
    braqui: 2 fila(s)
      rowid=190 clave={'DATE(date)': '2025-10-24'} -- gana rowid=193
      rowid=191 clave={'DATE(date)': '2025-10-24'} -- gana rowid=193
    control_conos: 4 fila(s)
      rowid=72 clave={'ref': 30, 'medida': '10x10'} -- gana rowid=76
      rowid=73 clave={'ref': 30, 'medida': '15x15'} -- gana rowid=77
      rowid=74 clave={'ref': 30, 'medida': '20x20'} -- gana rowid=78
      rowid=75 clave={'ref': 30, 'medida': '25x25'} -- gana rowid=79
    control_cunas: 8 fila(s)
      rowid=145 clave={'ref': 31, 'angulo': 15} -- gana rowid=149
      rowid=146 clave={'ref': 31, 'angulo': 30} -- gana rowid=150
      rowid=147 clave={'ref': 31, 'angulo': 45} -- gana rowid=151
      rowid=148 clave={'ref': 31, 'angulo': 60} -- gana rowid=152
      rowid=153 clave={'ref': 30, 'angulo': 15} -- gana rowid=157
      rowid=154 clave={'ref': 30, 'angulo': 30} -- gana rowid=158
      rowid=155 clave={'ref': 30, 'angulo': 45} -- gana rowid=159
      rowid=156 clave={'ref': 30, 'angulo': 60} -- gana rowid=160
    equipos_medicion: 8 fila(s)
      rowid=246 clave={'ref': 30, 'tipo_camara': 'Principal Fotones'} -- gana rowid=254
      rowid=250 clave={'ref': 30, 'tipo_camara': 'Principal Fotones'} -- gana rowid=254
      rowid=247 clave={'ref': 30, 'tipo_camara': 'Principal Electrones'} -- gana rowid=255
      rowid=251 clave={'ref': 30, 'tipo_camara': 'Principal Electrones'} -- gana rowid=255
      rowid=248 clave={'ref': 30, 'tipo_camara': 'Secundaria'} -- gana rowid=256
      rowid=252 clave={'ref': 30, 'tipo_camara': 'Secundaria'} -- gana rowid=256
      rowid=249 clave={'ref': 30, 'tipo_camara': 'Electrómetro'} -- gana rowid=257
      rowid=253 clave={'ref': 30, 'tipo_camara': 'Electrómetro'} -- gana rowid=257
    indicadores_angulares_colimador: 6 fila(s)
      rowid=22 clave={'ref': 22, 'nivel': '0°'} -- gana rowid=25
      rowid=23 clave={'ref': 22, 'nivel': '90°'} -- gana rowid=26
      rowid=24 clave={'ref': 22, 'nivel': '270°'} -- gana rowid=27
      rowid=31 clave={'ref': 30, 'nivel': '0°'} -- gana rowid=34
      rowid=32 clave={'ref': 30, 'nivel': '90°'} -- gana rowid=35
      rowid=33 clave={'ref': 30, 'nivel': '270°'} -- gana rowid=36
    indicadores_brazo: 12 fila(s)
      rowid=33 clave={'ref': 31, 'nivel': '0°'} -- gana rowid=37
      rowid=34 clave={'ref': 31, 'nivel': '90°'} -- gana rowid=38
      rowid=35 clave={'ref': 31, 'nivel': '180°'} -- gana rowid=39
      rowid=36 clave={'ref': 31, 'nivel': '270°'} -- gana rowid=40
      rowid=41 clave={'ref': 30, 'nivel': '0°'} -- gana rowid=49
      rowid=45 clave={'ref': 30, 'nivel': '0°'} -- gana rowid=49
      rowid=42 clave={'ref': 30, 'nivel': '90°'} -- gana rowid=50
      rowid=46 clave={'ref': 30, 'nivel': '90°'} -- gana rowid=50
      rowid=43 clave={'ref': 30, 'nivel': '180°'} -- gana rowid=51
      rowid=47 clave={'ref': 30, 'nivel': '180°'} -- gana rowid=51
      rowid=44 clave={'ref': 30, 'nivel': '270°'} -- gana rowid=52
      rowid=48 clave={'ref': 30, 'nivel': '270°'} -- gana rowid=52
    tamano_campo: 16 fila(s)
      rowid=41 clave={'ref': 30, 'campo_nominal': '5 x 5'} -- gana rowid=57
      rowid=45 clave={'ref': 30, 'campo_nominal': '5 x 5'} -- gana rowid=57
      rowid=49 clave={'ref': 30, 'campo_nominal': '5 x 5'} -- gana rowid=57
      rowid=53 clave={'ref': 30, 'campo_nominal': '5 x 5'} -- gana rowid=57
      rowid=42 clave={'ref': 30, 'campo_nominal': '10 x 10'} -- gana rowid=58
      rowid=46 clave={'ref': 30, 'campo_nominal': '10 x 10'} -- gana rowid=58
      rowid=50 clave={'ref': 30, 'campo_nominal': '10 x 10'} -- gana rowid=58
      rowid=54 clave={'ref': 30, 'campo_nominal': '10 x 10'} -- gana rowid=58
      rowid=43 clave={'ref': 30, 'campo_nominal': '15 x 15'} -- gana rowid=59
      rowid=47 clave={'ref': 30, 'campo_nominal': '15 x 15'} -- gana rowid=59
      rowid=51 clave={'ref': 30, 'campo_nominal': '15 x 15'} -- gana rowid=59
      rowid=55 clave={'ref': 30, 'campo_nominal': '15 x 15'} -- gana rowid=59
      rowid=44 clave={'ref': 30, 'campo_nominal': '20 x 20'} -- gana rowid=60
      rowid=48 clave={'ref': 30, 'campo_nominal': '20 x 20'} -- gana rowid=60
      rowid=52 clave={'ref': 30, 'campo_nominal': '20 x 20'} -- gana rowid=60
      rowid=56 clave={'ref': 30, 'campo_nominal': '20 x 20'} -- gana rowid=60

--- Índices UNIQUE parciales del bloque de QC (CL1) ---
  creados en esta corrida: 57 -- ['CondicionesMedicion', 'HC_desplazamiento_isocentro_mensual', 'HC_dosimetria_anual', 'HC_fantomas', 'HC_imagen_perfil_mlc_anual', 'HC_indicadores_brazo', 'HC_indicadores_camilla', 'HC_indicadores_colimador', 'HC_indicadores_laser', 'HC_linealidad_unidades_monitor_anual', 'HC_precision_posicion_multilaminas_anual', 'HC_tamanos_campo_radiacion','HC_velocidad_multilaminas_anual', 'LecturasMaximos', 'MaximosCamaras', 'ResultadosActividad', 'SistemaMedicion', 'TipoCalibracion', 'aceleradorlineal_600', 'aceleradorlineal_ix', 'analisis_placa_correcciones', 'analisis_placa_franjas', 'analisis_placa_verificaciones', 'angulo_starshot', 'angulos_entre_lineas_starshot', 'braqui', 'configuracion_picketfence', 'configuracion_starshot', 'control_conos', 'control_cunas', 'dosimetriaMen', 'equipos_medicion', 'error_picket', 'espesor_corte', 'estadisticas_starshot', 'halcyon', 'highest_leaf_errors', 'indicadores_angulares_colimador', 'indicadores_brazo', 'leaf_error', 'linealidad_ct', 'preguntas', 'pruebas', 'resolucion_contraste', 'resolucion_contraste_rois', 'resolucion_espacial', 'resolucion_espacial_regiones', 'tabla_control_camaras_monitoras', 'tabla_factor_campo', 'tabla_factores_sobre_eje', 'tabla_factores_transmision', 'tamano_campo', 'tamaño_pixel', 'uniformidad_angular_starshot', 'uniformidad_global', 'uniformidad_ruido', 'valores_ct']

--- angulo_starshot: retiro del UNIQUE de tabla (EB2d, DA-57) ---
  migrada -- UNIQUE(ref, spoke_index) de tabla retirado
  Sin esto, el SEGUNDO análisis starshot de un mismo control fallaría al guardar:
  una fila anulada y una vigente con el mismo (ref, spoke_index) violan el UNIQUE
  aunque `activo` sea distinto. El índice parcial de CL1 cubre lo mismo respetando
  la vigencia.

--- Retiro de equipos_anual (MI5, DA-44) ---
  retirada: estaba vacía, DROP TABLE aplicado

--- Retiro de posicionamiento_reposicionamiento (EB7, DA-50) ---
  retirada: estaba vacía, DROP TABLE aplicado

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
  dosimetriaMen: 44 -> 44
  preguntas: 16 -> 16
  tamano_campo: 76 -> 76
  pruebas: 42 -> 42
  calculadora_dosimetrica: 2 -> 2
  Ningún registro de QC se perdió (la migración nunca borra filas).

--- Censo completo (67 tablas revisadas) ---
  Las 61 tablas restantes conservan sus conteos (ninguna perdió filas).

--- Duplicados de controles (unicidad DP-06) ---
  Ningún duplicado por (equipo, control, mes/año) entre las filas activas.

  - La ejecucion real se da de la misma forma:

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2> .venv\Scripts\python scripts\migrar_bd_a_estandar.py "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\BaseDatosQA.db" --aplicar --usuario FelipePP12
Base de datos: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\BaseDatosQA.db
integrity_check antes: ok
Backup creado: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\BaseDatosQA.db.pre_migracion_20260825_161100.bak
E10: sqlite_sequence normalizada para HC_desplazamiento_isocentro_mensual (duplicados -> seq=15)
E10: sqlite_sequence normalizada para HC_dosimetria_anual (duplicados -> seq=3)
E10: sqlite_sequence normalizada para HC_fantomas (duplicados -> seq=3)
E10: sqlite_sequence normalizada para HC_imagen_perfil_mlc_anual (duplicados -> seq=4)
E10: sqlite_sequence normalizada para HC_indicadores_brazo (duplicados -> seq=36)
E10: sqlite_sequence normalizada para HC_indicadores_camilla (duplicados -> seq=81)
E10: sqlite_sequence normalizada para HC_indicadores_colimador (duplicados -> seq=27)
E10: sqlite_sequence normalizada para HC_indicadores_laser (duplicados -> seq=27)
E10: sqlite_sequence normalizada para HC_linealidad_unidades_monitor_anual (duplicados -> seq=32)
E10: sqlite_sequence normalizada para HC_precision_posicion_multilaminas_anual (duplicados -> seq=20)
E10: sqlite_sequence normalizada para HC_tamanos_campo_radiacion (duplicados -> seq=37)
E10: sqlite_sequence normalizada para HC_velocidad_multilaminas_anual (duplicados -> seq=16)
E10: sqlite_sequence normalizada para LinealidadBraquiterapia (duplicados -> seq=10)
E10: sqlite_sequence normalizada para TipoCalibracion (duplicados -> seq=35)
E10: sqlite_sequence normalizada para aceleradorlineal_600 (duplicados -> seq=368)
E10: sqlite_sequence normalizada para aceleradorlineal_ix (duplicados -> seq=376)
E10: sqlite_sequence normalizada para braqui (duplicados -> seq=433)
E10: sqlite_sequence normalizada para control_conos (duplicados -> seq=89)
E10: sqlite_sequence normalizada para control_cunas (duplicados -> seq=180)
E10: sqlite_sequence normalizada para controles_mensuales (duplicados -> seq=109)
E10: sqlite_sequence normalizada para energias (duplicados -> seq=5)
E10: sqlite_sequence normalizada para equipos (duplicados -> seq=81)
E10: sqlite_sequence normalizada para equipos_medicion (duplicados -> seq=273)
E10: sqlite_sequence normalizada para equipos_mensual (duplicados -> seq=87)
E10: sqlite_sequence normalizada para halcyon (duplicados -> seq=326)
E10: sqlite_sequence normalizada para pruebas (duplicados -> seq=187)
E10: sqlite_sequence normalizada para resolucion_contraste_rois (duplicados -> seq=216)
E10: sqlite_sequence normalizada para resolucion_espacial_regiones (duplicados -> seq=240)
E10: sqlite_sequence normalizada para tabla_control_camaras_monitoras (duplicados -> seq=126)
E10: sqlite_sequence normalizada para tabla_factor_campo (duplicados -> seq=168)
E10: sqlite_sequence normalizada para tabla_factores_sobre_eje (duplicados -> seq=207)
E10: sqlite_sequence normalizada para tabla_factores_transmision (duplicados -> seq=140)
E10: sqlite_sequence normalizada para uniformidad_ruido (duplicados -> seq=135)
E10: sqlite_sequence normalizada para users (duplicados -> seq=13)
E10: sqlite_sequence normalizada para valores_ct (duplicados -> seq=196)
F1: 58 tablas con borrado en cascada -- respaldando antes de recrear el esquema en RESTRICT...
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\respaldos_bd\pre_migracion\BaseDatosQA_2026-08-25_161101.db
E10: migrando 58 tablas a ON DELETE RESTRICT...
EB2d: angulo_starshot migrada -- UNIQUE(ref, spoke_index) de tabla retirado (el índice parcial de CL1 ya cubre lo mismo, respetando 'activo').
integrity_check después: ok

--- Cambios de esquema ---
  Tablas nuevas creadas: ['angulos_entre_lineas_starshot', 'audit_log']
  CondicionesMedicion: columna(s) nueva(s) ['activo']
  HC_desplazamiento_isocentro_mensual: columna(s) nueva(s) ['activo']
  HC_dosimetria_anual: columna(s) nueva(s) ['activo']
  HC_fantomas: columna(s) nueva(s) ['activo']
  HC_imagen_perfil_mlc_anual: columna(s) nueva(s) ['activo']
  HC_indicadores_brazo: columna(s) nueva(s) ['activo']
  HC_indicadores_camilla: columna(s) nueva(s) ['activo']
  HC_indicadores_colimador: columna(s) nueva(s) ['activo']
  HC_indicadores_laser: columna(s) nueva(s) ['activo']
  HC_linealidad_unidades_monitor_anual: columna(s) nueva(s) ['activo']
  HC_precision_posicion_multilaminas_anual: columna(s) nueva(s) ['activo']
  HC_tamanos_campo_radiacion: columna(s) nueva(s) ['activo']
  HC_velocidad_multilaminas_anual: columna(s) nueva(s) ['activo']
  LecturasMaximos: columna(s) nueva(s) ['activo']
  LinealidadBraquiterapia: columna(s) nueva(s) ['activo']
  MaximosCamaras: columna(s) nueva(s) ['activo']
  ResultadosActividad: columna(s) nueva(s) ['activo']
  SistemaMedicion: columna(s) nueva(s) ['activo']
  TipoCalibracion: columna(s) nueva(s) ['activo']
  aceleradorlineal_600: columna(s) nueva(s) ['activo']
  aceleradorlineal_ix: columna(s) nueva(s) ['activo']
  analisis_placa_correcciones: columna(s) nueva(s) ['activo']
  analisis_placa_franjas: columna(s) nueva(s) ['activo']
  analisis_placa_verificaciones: columna(s) nueva(s) ['activo']
  angulo_starshot: columna(s) nueva(s) ['activo']
  braqui: columna(s) nueva(s) ['activo']
  calculadora_dosimetrica: columna(s) nueva(s) ['energia', 'pdd_zref_electrones', 'protocolo_trs398', 'r50_medido', 'tension_negativa', 'tpr2010', 'vigente']
  configuracion_picketfence: columna(s) nueva(s) ['activo']
  configuracion_starshot: columna(s) nueva(s) ['activo']
  control_conos: columna(s) nueva(s) ['activo']
  control_cunas: columna(s) nueva(s) ['activo']
  controles: columna(s) nueva(s) ['activo']
  dosimetriaMen: columna(s) nueva(s) ['activo']
  equipos_medicion: columna(s) nueva(s) ['activo', 'equipo_id']
  error_picket: columna(s) nueva(s) ['activo']
  espesor_corte: columna(s) nueva(s) ['activo']
  estadisticas_starshot: columna(s) nueva(s) ['activo']
  halcyon: columna(s) nueva(s) ['activo']
  highest_leaf_errors: columna(s) nueva(s) ['activo']
  indicadores_angulares_colimador: columna(s) nueva(s) ['activo']
  indicadores_brazo: columna(s) nueva(s) ['activo']
  leaf_error: columna(s) nueva(s) ['activo']
  linealidad_ct: columna(s) nueva(s) ['activo']
  preguntas: columna(s) nueva(s) ['activo']
  pruebas: columna(s) nueva(s) ['activo']
  resolucion_contraste: columna(s) nueva(s) ['activo']
  resolucion_contraste_rois: columna(s) nueva(s) ['activo']
  resolucion_espacial: columna(s) nueva(s) ['activo']
  resolucion_espacial_regiones: columna(s) nueva(s) ['activo']
  tabla_control_camaras_monitoras: columna(s) nueva(s) ['activo']
  tabla_factor_campo: columna(s) nueva(s) ['activo']
  tabla_factores_sobre_eje: columna(s) nueva(s) ['activo']
  tabla_factores_transmision: columna(s) nueva(s) ['activo']
  tamano_campo: columna(s) nueva(s) ['activo']
  tamaño_pixel: columna(s) nueva(s) ['activo']
  uniformidad_angular_starshot: columna(s) nueva(s) ['activo']
  uniformidad_global: columna(s) nueva(s) ['activo']
  uniformidad_ruido: columna(s) nueva(s) ['activo']
  users: columna(s) nueva(s) ['rol_sistema']
  valores_ct: columna(s) nueva(s) ['activo']

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

--- Saneamiento de claves duplicadas del bloque de QC (SA1, DA-38) ---
  121 fila(s) pasadas a histórica (activo=0), cero borradas:
    HC_indicadores_camilla: 9 fila(s)
      rowid=55 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Longitudinal', 'desplazamiento': 1.0} -- gana rowid=64
      rowid=56 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Longitudinal', 'desplazamiento': 5.0} -- gana rowid=65
      rowid=57 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Longitudinal', 'desplazamiento': 20.0} -- gana rowid=66
      rowid=58 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Lateral', 'desplazamiento': 1.0} -- gana rowid=67
      rowid=59 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Lateral', 'desplazamiento': 5.0} -- gana rowid=68
      rowid=60 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Lateral', 'desplazamiento': 20.0} -- gana rowid=69
      rowid=61 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Vertical', 'desplazamiento': 1.0} -- gana rowid=70
      rowid=62 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Vertical', 'desplazamiento': 5.0} -- gana rowid=71
      rowid=63 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Vertical', 'desplazamiento': 20.0} -- gana rowid=72
    HC_indicadores_colimador: 3 fila(s)
      rowid=19 clave={'ref': 33, 'id_energia': 0, 'nivel': 0.0} -- gana rowid=22
      rowid=20 clave={'ref': 33, 'id_energia': 0, 'nivel': 90.0} -- gana rowid=23
      rowid=21 clave={'ref': 33, 'id_energia': 0, 'nivel': 270.0} -- gana rowid=24
    HC_indicadores_laser: 3 fila(s)
      rowid=19 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Longitudinal'} -- gana rowid=22
      rowid=20 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Vertical'} -- gana rowid=23
      rowid=21 clave={'ref': 33, 'id_energia': 0, 'ubicacion': 'Lateral'} -- gana rowid=24
    aceleradorlineal_600: 2 fila(s)
      rowid=121 clave={'DATE(date)': '2025-07-24'} -- gana rowid=122
      rowid=212 clave={'DATE(date)': '2025-12-16'} -- gana rowid=213
    aceleradorlineal_ix: 30 fila(s)
      rowid=2 clave={'DATE(date)': '2025-03-04'} -- gana rowid=40
      rowid=3 clave={'DATE(date)': '2025-03-05'} -- gana rowid=41
      rowid=4 clave={'DATE(date)': '2025-03-10'} -- gana rowid=42
      rowid=5 clave={'DATE(date)': '2025-03-25'} -- gana rowid=43
      rowid=6 clave={'DATE(date)': '2025-03-26'} -- gana rowid=44
      rowid=7 clave={'DATE(date)': '2025-03-27'} -- gana rowid=45
      rowid=8 clave={'DATE(date)': '2025-03-28'} -- gana rowid=46
      rowid=9 clave={'DATE(date)': '2025-04-01'} -- gana rowid=47
      rowid=10 clave={'DATE(date)': '2025-04-02'} -- gana rowid=48
      rowid=11 clave={'DATE(date)': '2025-04-03'} -- gana rowid=49
      rowid=12 clave={'DATE(date)': '2025-04-04'} -- gana rowid=50
      rowid=13 clave={'DATE(date)': '2025-04-07'} -- gana rowid=51
      rowid=14 clave={'DATE(date)': '2025-04-08'} -- gana rowid=52
      rowid=15 clave={'DATE(date)': '2025-04-09'} -- gana rowid=53
      rowid=16 clave={'DATE(date)': '2025-04-10'} -- gana rowid=54
      rowid=17 clave={'DATE(date)': '2025-04-11'} -- gana rowid=55
      rowid=18 clave={'DATE(date)': '2025-04-14'} -- gana rowid=56
      rowid=19 clave={'DATE(date)': '2025-04-15'} -- gana rowid=57
      rowid=20 clave={'DATE(date)': '2025-04-16'} -- gana rowid=58
      rowid=21 clave={'DATE(date)': '2025-04-21'} -- gana rowid=59
      rowid=22 clave={'DATE(date)': '2025-04-24'} -- gana rowid=60
      rowid=23 clave={'DATE(date)': '2025-04-25'} -- gana rowid=61
      rowid=24 clave={'DATE(date)': '2025-04-28'} -- gana rowid=62
      rowid=25 clave={'DATE(date)': '2025-04-22'} -- gana rowid=63
      rowid=26 clave={'DATE(date)': '2025-04-23'} -- gana rowid=64
      rowid=27 clave={'DATE(date)': '2025-04-29'} -- gana rowid=65
      rowid=28 clave={'DATE(date)': '2025-04-30'} -- gana rowid=66
      rowid=29 clave={'DATE(date)': '2025-05-02'} -- gana rowid=67
      rowid=127 clave={'DATE(date)': '2025-07-31'} -- gana rowid=128
      rowid=187 clave={'DATE(date)': '2025-10-27'} -- gana rowid=188
    analisis_placa_correcciones: 8 fila(s)
      rowid=1 clave={'ref': 16, 'vertice': 'arriba_izq'} -- gana rowid=5
      rowid=2 clave={'ref': 16, 'vertice': 'arriba_der'} -- gana rowid=6
      rowid=3 clave={'ref': 16, 'vertice': 'abajo_izq'} -- gana rowid=7
      rowid=4 clave={'ref': 16, 'vertice': 'abajo_der'} -- gana rowid=8
      rowid=13 clave={'ref': 15, 'vertice': 'arriba_izq'} -- gana rowid=17
      rowid=14 clave={'ref': 15, 'vertice': 'arriba_der'} -- gana rowid=18
      rowid=15 clave={'ref': 15, 'vertice': 'abajo_izq'} -- gana rowid=19
      rowid=16 clave={'ref': 15, 'vertice': 'abajo_der'} -- gana rowid=20
    analisis_placa_franjas: 6 fila(s)
      rowid=1 clave={'ref': 16, 'franja': 'Franja 1'} -- gana rowid=4
      rowid=2 clave={'ref': 16, 'franja': 'Franja 2'} -- gana rowid=5
      rowid=3 clave={'ref': 16, 'franja': 'Franja 3'} -- gana rowid=6
      rowid=10 clave={'ref': 15, 'franja': 'Franja 1'} -- gana rowid=13
      rowid=11 clave={'ref': 15, 'franja': 'Franja 2'} -- gana rowid=14
      rowid=12 clave={'ref': 15, 'franja': 'Franja 3'} -- gana rowid=15
    analisis_placa_verificaciones: 4 fila(s)
      rowid=1 clave={'ref': 16, 'tipo': 'verificacion_inicial'} -- gana rowid=3
      rowid=2 clave={'ref': 16, 'tipo': 'verificacion_ideal'} -- gana rowid=4
      rowid=7 clave={'ref': 15, 'tipo': 'verificacion_inicial'} -- gana rowid=9
      rowid=8 clave={'ref': 15, 'tipo': 'verificacion_ideal'} -- gana rowid=10
    braqui: 2 fila(s)
      rowid=190 clave={'DATE(date)': '2025-10-24'} -- gana rowid=193
      rowid=191 clave={'DATE(date)': '2025-10-24'} -- gana rowid=193
    control_conos: 4 fila(s)
      rowid=72 clave={'ref': 30, 'medida': '10x10'} -- gana rowid=76
      rowid=73 clave={'ref': 30, 'medida': '15x15'} -- gana rowid=77
      rowid=74 clave={'ref': 30, 'medida': '20x20'} -- gana rowid=78
      rowid=75 clave={'ref': 30, 'medida': '25x25'} -- gana rowid=79
    control_cunas: 8 fila(s)
      rowid=145 clave={'ref': 31, 'angulo': 15} -- gana rowid=149
      rowid=146 clave={'ref': 31, 'angulo': 30} -- gana rowid=150
      rowid=147 clave={'ref': 31, 'angulo': 45} -- gana rowid=151
      rowid=148 clave={'ref': 31, 'angulo': 60} -- gana rowid=152
      rowid=153 clave={'ref': 30, 'angulo': 15} -- gana rowid=157
      rowid=154 clave={'ref': 30, 'angulo': 30} -- gana rowid=158
      rowid=155 clave={'ref': 30, 'angulo': 45} -- gana rowid=159
      rowid=156 clave={'ref': 30, 'angulo': 60} -- gana rowid=160
    equipos_medicion: 8 fila(s)
      rowid=246 clave={'ref': 30, 'tipo_camara': 'Principal Fotones'} -- gana rowid=254
      rowid=250 clave={'ref': 30, 'tipo_camara': 'Principal Fotones'} -- gana rowid=254
      rowid=247 clave={'ref': 30, 'tipo_camara': 'Principal Electrones'} -- gana rowid=255
      rowid=251 clave={'ref': 30, 'tipo_camara': 'Principal Electrones'} -- gana rowid=255
      rowid=248 clave={'ref': 30, 'tipo_camara': 'Secundaria'} -- gana rowid=256
      rowid=252 clave={'ref': 30, 'tipo_camara': 'Secundaria'} -- gana rowid=256
      rowid=249 clave={'ref': 30, 'tipo_camara': 'Electrómetro'} -- gana rowid=257
      rowid=253 clave={'ref': 30, 'tipo_camara': 'Electrómetro'} -- gana rowid=257
    indicadores_angulares_colimador: 6 fila(s)
      rowid=22 clave={'ref': 22, 'nivel': '0°'} -- gana rowid=25
      rowid=23 clave={'ref': 22, 'nivel': '90°'} -- gana rowid=26
      rowid=24 clave={'ref': 22, 'nivel': '270°'} -- gana rowid=27
      rowid=31 clave={'ref': 30, 'nivel': '0°'} -- gana rowid=34
      rowid=32 clave={'ref': 30, 'nivel': '90°'} -- gana rowid=35
      rowid=33 clave={'ref': 30, 'nivel': '270°'} -- gana rowid=36
    indicadores_brazo: 12 fila(s)
      rowid=33 clave={'ref': 31, 'nivel': '0°'} -- gana rowid=37
      rowid=34 clave={'ref': 31, 'nivel': '90°'} -- gana rowid=38
      rowid=35 clave={'ref': 31, 'nivel': '180°'} -- gana rowid=39
      rowid=36 clave={'ref': 31, 'nivel': '270°'} -- gana rowid=40
      rowid=41 clave={'ref': 30, 'nivel': '0°'} -- gana rowid=49
      rowid=45 clave={'ref': 30, 'nivel': '0°'} -- gana rowid=49
      rowid=42 clave={'ref': 30, 'nivel': '90°'} -- gana rowid=50
      rowid=46 clave={'ref': 30, 'nivel': '90°'} -- gana rowid=50
      rowid=43 clave={'ref': 30, 'nivel': '180°'} -- gana rowid=51
      rowid=47 clave={'ref': 30, 'nivel': '180°'} -- gana rowid=51
      rowid=44 clave={'ref': 30, 'nivel': '270°'} -- gana rowid=52
      rowid=48 clave={'ref': 30, 'nivel': '270°'} -- gana rowid=52
    tamano_campo: 16 fila(s)
      rowid=41 clave={'ref': 30, 'campo_nominal': '5 x 5'} -- gana rowid=57
      rowid=45 clave={'ref': 30, 'campo_nominal': '5 x 5'} -- gana rowid=57
      rowid=49 clave={'ref': 30, 'campo_nominal': '5 x 5'} -- gana rowid=57
      rowid=53 clave={'ref': 30, 'campo_nominal': '5 x 5'} -- gana rowid=57
      rowid=42 clave={'ref': 30, 'campo_nominal': '10 x 10'} -- gana rowid=58
      rowid=46 clave={'ref': 30, 'campo_nominal': '10 x 10'} -- gana rowid=58
      rowid=50 clave={'ref': 30, 'campo_nominal': '10 x 10'} -- gana rowid=58
      rowid=54 clave={'ref': 30, 'campo_nominal': '10 x 10'} -- gana rowid=58
      rowid=43 clave={'ref': 30, 'campo_nominal': '15 x 15'} -- gana rowid=59
      rowid=47 clave={'ref': 30, 'campo_nominal': '15 x 15'} -- gana rowid=59
      rowid=51 clave={'ref': 30, 'campo_nominal': '15 x 15'} -- gana rowid=59
      rowid=55 clave={'ref': 30, 'campo_nominal': '15 x 15'} -- gana rowid=59
      rowid=44 clave={'ref': 30, 'campo_nominal': '20 x 20'} -- gana rowid=60
      rowid=48 clave={'ref': 30, 'campo_nominal': '20 x 20'} -- gana rowid=60
      rowid=52 clave={'ref': 30, 'campo_nominal': '20 x 20'} -- gana rowid=60
      rowid=56 clave={'ref': 30, 'campo_nominal': '20 x 20'} -- gana rowid=60

--- Índices UNIQUE parciales del bloque de QC (CL1) ---
  creados en esta corrida: 57 -- ['CondicionesMedicion', 'HC_desplazamiento_isocentro_mensual', 'HC_dosimetria_anual', 'HC_fantomas', 'HC_imagen_perfil_mlc_anual', 'HC_indicadores_brazo', 'HC_indicadores_camilla', 'HC_indicadores_colimador', 'HC_indicadores_laser', 'HC_linealidad_unidades_monitor_anual', 'HC_precision_posicion_multilaminas_anual', 'HC_tamanos_campo_radiacion', 'HC_velocidad_multilaminas_anual', 'LecturasMaximos', 'MaximosCamaras', 'ResultadosActividad', 'SistemaMedicion', 'TipoCalibracion', 'aceleradorlineal_600', 'aceleradorlineal_ix', 'analisis_placa_correcciones', 'analisis_placa_franjas', 'analisis_placa_verificaciones', 'angulo_starshot', 'angulos_entre_lineas_starshot', 'braqui', 'configuracion_picketfence', 'configuracion_starshot', 'control_conos', 'control_cunas', 'dosimetriaMen', 'equipos_medicion', 'error_picket', 'espesor_corte', 'estadisticas_starshot', 'halcyon', 'highest_leaf_errors', 'indicadores_angulares_colimador', 'indicadores_brazo', 'leaf_error', 'linealidad_ct', 'preguntas', 'pruebas', 'resolucion_contraste', 'resolucion_contraste_rois', 'resolucion_espacial', 'resolucion_espacial_regiones', 'tabla_control_camaras_monitoras', 'tabla_factor_campo', 'tabla_factores_sobre_eje', 'tabla_factores_transmision', 'tamano_campo', 'tamaño_pixel', 'uniformidad_angular_starshot', 'uniformidad_global', 'uniformidad_ruido', 'valores_ct']

--- angulo_starshot: retiro del UNIQUE de tabla (EB2d, DA-57) ---
  migrada -- UNIQUE(ref, spoke_index) de tabla retirado
  Sin esto, el SEGUNDO análisis starshot de un mismo control fallaría al guardar:
  una fila anulada y una vigente con el mismo (ref, spoke_index) violan el UNIQUE
  aunque `activo` sea distinto. El índice parcial de CL1 cubre lo mismo respetando
  la vigencia.

--- Retiro de equipos_anual (MI5, DA-44) ---
  retirada: estaba vacía, DROP TABLE aplicado

--- Retiro de posicionamiento_reposicionamiento (EB7, DA-50) ---
  retirada: estaba vacía, DROP TABLE aplicado

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
  dosimetriaMen: 44 -> 44
  preguntas: 16 -> 16
  tamano_campo: 76 -> 76
  pruebas: 42 -> 42
  calculadora_dosimetrica: 2 -> 2
  Ningún registro de QC se perdió (la migración nunca borra filas).

--- Censo completo (67 tablas revisadas) ---
  Las 61 tablas restantes conservan sus conteos (ninguna perdió filas).

--- Duplicados de controles (unicidad DP-06) ---
  Ningún duplicado por (equipo, control, mes/año) entre las filas activas.

Listo. Backup de seguridad conservado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\BaseDatosQA.db.pre_migracion_20260825_161100.bak

- Expulsion de la terminal al abrir la app con >python main.py:

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2> python main.py
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x0000025BF346F510>, id_f1_num usado: Administrador
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
Fecha Final COT: 2026-08-25 16:21:05-05:00
Horas transcurridas desde 2026-08-25 16:21:05: 1955.7447222222222
Dias transcurridos: 81.48936342592593
 La actividad es:  6.3514
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
load table: 0.089s
asignar_encabezados: 0.089s
button_click: 0.090s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x0000025BF346F510>, id_f1_num usado: Administrador
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
<PyQt5.QtWidgets.QGridLayout object at 0x0000025C3B59C5E0>
<PyQt5.QtWidgets.QGridLayout object at 0x0000025C3B5C2200>
<PyQt5.QtWidgets.QGridLayout object at 0x0000025C3B5C20E0>
<PyQt5.QtWidgets.QGridLayout object at 0x0000025C3B5C2170>
<PyQt5.QtWidgets.QGridLayout object at 0x0000025C3B5C1870>
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
Insertando datos de equipos para IX
Insertados 4 registros de equipos correctamente
Actualizando tabla de controles mensuales para Clinac ix
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x0000025C3B5BAD40>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

Se presionó btn_guardar_ix

 Función guardar_control_conos en IX

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x0000025C3B5BAD40>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

Se presionó btn_guardar_ix
Subiendo tabla indicadores_brazo sin id_energia
Los argumentos son: nombre_tabla=indicadores_brazo, ref=43, anual=False, id=False

▥ Columnas detectadas: ['ref', 'nivel', 'indicador_luminoso_consola', 'indicador_luminoso_equipo'] para indicadores_brazo

Bloque identificado por ['ref'] para la tabla indicadores_brazo, id = False

▥ Datos a insertar en indicadores_brazo:
  - [43, '0°', '1', '1']
  - [43, '90°', '1', '1']
  - [43, '180°', '1', '1']
  - [43, '270°', '1', '1']
Actualizando tabla de controles mensuales para Clinac ix
Tabla indicadores_brazo subida correctamente
Subiendo tabla indicadores_angulares_colimador sin id_energia
Los argumentos son: nombre_tabla=indicadores_angulares_colimador, ref=43, anual=False, id=False

▥ Columnas detectadas: ['ref', 'nivel', 'indicador_luminoso_consola', 'indicador_luminoso_equipo'] para indicadores_angulares_colimador

Bloque identificado por ['ref'] para la tabla indicadores_angulares_colimador, id = False

▥ Datos a insertar en indicadores_angulares_colimador:
  - [43, '0°', '1', '1']
  - [43, '90°', '1', '1']
  - [43, '180°', '1', '1']
  - [43, '270°', '1', '1']
Actualizando tabla de controles mensuales para Clinac ix
Tabla indicadores_angulares_colimador subida correctamente

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2> python main.py
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
iniGUI: 0.021s
load table: 0.086s
asignar_encabezados: 0.086s
button_click: 0.087s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001DF7EE45550>, id_f1_num usado: Administrador
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
<PyQt5.QtWidgets.QGridLayout object at 0x000001DFBC55E710>
<PyQt5.QtWidgets.QGridLayout object at 0x000001DFBC55E680>
<PyQt5.QtWidgets.QGridLayout object at 0x000001DFBC55E830>
<PyQt5.QtWidgets.QGridLayout object at 0x000001DFBC55E7A0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001DFBC55E8C0>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
action tolerance encontrado
Widgets MLC encontrados y configurados
Entra a subir tabla en fieldSize

▥ Columnas detectadas: ['ref', 'campo_nominal', 'ie_largoy1', 'ie_largoy2', 'ie_anchox1', 'ie_anchox2', 'ic_largoy1', 'ic_largoy2', 'ic_anchox1', 'ic_anchox2'] para tamano_campo

Bloque identificado por ['ref'] para la tabla tamano_campo, id = False

▥ Datos a insertar en tamano_campo:
  - [44, '5 x 5', '5', '5', '5', '5', '5', '5', '5', '5']
  - [44, '10 x 10', '10', '01', '10', '10', '10', '10', '10', '10']
  - [44, '15 x 15', '15', '15', '15', '15', '15', '15', '15', '15']
  - [44, '20 x 20', '20', '20', '20', '20', '20', '20', '20', '20']
Actualizando tabla de controles mensuales para Clinac ix

La variable equipo_f en la función fieldSize es: Clinac ix
Entra a subir tabla en fieldSize

▥ Columnas detectadas: ['ref', 'campo_nominal', 'ie_largoy1', 'ie_largoy2', 'ie_anchox1', 'ie_anchox2', 'ic_largoy1', 'ic_largoy2', 'ic_anchox1', 'ic_anchox2'] para tamano_campo

Bloque identificado por ['ref'] para la tabla tamano_campo, id = False

▥ Datos a insertar en tamano_campo:
  - [44, '5 x 5', '5', '5', '5', '5', '5', '5', '5', '5']
  - [44, '10 x 10', '10', '01', '10', '10', '10', '10', '10', '10']
  - [44, '15 x 15', '15', '15', '15', '15', '15', '15', '15', '15']
  - [44, '20 x 20', '20', '20', '20', '20', '20', '20', '20', '20']
Actualizando tabla de controles mensuales para Clinac ix

La variable equipo_f en la función fieldSize es: Clinac ix
Subir imagen activado en imagenUpLoader en PruebasDiarias.py
Analisis de imagen activado en subir_imagen en PruebasDiarias.py
analizando imagen
Subir imagen activado en imagenUpLoader en PruebasDiarias.py
Analizando imagen...
DPI:  300
Lado arriba: 99.74 mm
Lado abajo: 99.40 mm
Lado izquierda: 99.65 mm
Lado derecha: 99.65 mm
Centro: (655, 639)
Tamaño de Campo: 103.24 (mm)
Tamaño de Campo: 101.61 (mm)
Cruz vs centro geométrico: Δx=0.00mm, Δy=-0.08mm
Tamaño de Campo: 105.53 (mm)
Tamaño de Campo: 103.27 (mm)
Cruz vs centro geométrico: Δx=0.00mm, Δy=-0.08mm
Tamaño de Campo: 103.16 (mm)
Tamaño de Campo: 101.63 (mm)
Cruz vs centro geométrico: Δx=0.00mm, Δy=-0.08mm
Aceptar imagen activado en PruebasDiarias.py

Entra a la función crear_algo en load.py con ref: 44 y imagen: C:/Users/parra/Documents/Archivos_UseApp/PlacasHistoricas/placa_ref30.jpeg

Subiendo datos para preguntas

▥ Columnas detectadas: ['ref', 'iso_mec', 'reticulo_cent', 'bordes_coin', 'camilla_vert_rango', 'camilla_vert_desp', 'camilla_iso_desp', 'telem_rango', 'telem_desp', 'camp_luz_desp', 'puntero_telem_diff', 'laser_techo', 'laser_lateral27', 'laser_lateral9', 'observaciones'] para preguntas

Datos guardados correctamente.
Actualizando tabla de controles mensuales para Clinac ix
Datos subidos correctamente

Subiendo datos para preguntas

▥ Columnas detectadas: ['ref', 'iso_mec', 'reticulo_cent', 'bordes_coin', 'camilla_vert_rango', 'camilla_vert_desp', 'camilla_iso_desp', 'telem_rango', 'telem_desp', 'camp_luz_desp', 'puntero_telem_diff', 'laser_techo', 'laser_lateral27', 'laser_lateral9', 'observaciones'] para preguntas

Datos guardados correctamente.
Actualizando tabla de controles mensuales para Clinac ix
Datos subidos correctamente

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
300
300
300
Data saved successfully for date: 25/08/2026

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
300

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

Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\respaldos_bd\BaseDatosQA_2026-08-25_171029.db

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2> python main.py
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x0000013D96756B10>, id_f1_num usado: Administrador
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
Fecha Final COT: 2026-08-26 08:03:51-05:00
Horas transcurridas desde 2026-08-26 08:03:51: 1971.4575
Dias transcurridos: 82.1440625
 La actividad es:  6.3125
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
iniGUI: 0.026s
load table: 0.093s
asignar_encabezados: 0.093s
button_click: 0.093s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x0000013D96756B10>, id_f1_num usado: Administrador
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
<PyQt5.QtWidgets.QGridLayout object at 0x0000013E01571AB0>
<PyQt5.QtWidgets.QGridLayout object at 0x0000013E01571360>
<PyQt5.QtWidgets.QGridLayout object at 0x0000013E01571BD0>
<PyQt5.QtWidgets.QGridLayout object at 0x0000013E01571B40>
<PyQt5.QtWidgets.QGridLayout object at 0x0000013E01571C60>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
action tolerance encontrado
Widgets MLC encontrados y configurados
Subir imagen activado en imagenUpLoader en PruebasDiarias.py
Analisis de imagen activado en subir_imagen en PruebasDiarias.py
analizando imagen
Subir imagen activado en imagenUpLoader en PruebasDiarias.py
Analizando imagen...
DPI:  300
Lado arriba: 99.74 mm
Lado abajo: 99.65 mm
Lado izquierda: 99.99 mm
Lado derecha: 99.40 mm
Centro: (657, 640)
Tamaño de Campo: 103.24 (mm)
Tamaño de Campo: 101.62 (mm)
Cruz vs centro geométrico: Δx=-0.17mm, Δy=-0.17mm
Tamaño de Campo: 105.53 (mm)
Tamaño de Campo: 103.27 (mm)
Cruz vs centro geométrico: Δx=-0.17mm, Δy=-0.17mm
Tamaño de Campo: 103.15 (mm)
Tamaño de Campo: 101.64 (mm)
Cruz vs centro geométrico: Δx=-0.17mm, Δy=-0.17mm
Aceptar imagen activado en PruebasDiarias.py

Entra a la función crear_algo en load.py con ref: 44 y imagen: C:/Users/parra/Documents/Archivos_UseApp/PlacasHistoricas/placa_ref30.jpeg
Analizando imagen...
DPI:  96
Lado arriba: 141.02 mm
Lado abajo: 140.50 mm
Lado izquierda: 142.35 mm
Lado derecha: 142.08 mm
Centro: (296, 277)
Tamaño de Campo: 145.45 (mm)
Tamaño de Campo: 144.43 (mm)
Imagen no subida o inadecuada:  'NoneType' object is not subscriptable
Error al subir o al analizar imagen:  'NoneType' object is not subscriptable
Aceptar imagen activado en PruebasDiarias.py
Archivo:  C:/Users/parra/Documents/Archivos_UseApp/PlacasHistoricas/placa_ANOMALA_96dpi_ref10.jpeg

ele_15mev']
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
✓ Datos del 2026-08-06 cargados correctamente.
  - Botones finales: 12
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\respaldos_bd\BaseDatosQA_2026-08-26_130114.db
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2> python main.py
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
Listando carpetas...
Error al listar carpetas: [WinError 53] The network path was not found: '\\\\VARIANDB\\Va_Transfer\\TDS\\HAL1161\\MPCChecks'
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\respaldos_bd\BaseDatosQA_2026-08-26_130222.db
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2> $env:RADQA_HALCYON_MPC = "C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon"
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2> python main.py
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
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-07-14-05-22-57-0001-GeometryCheckTemplate6xFFFMVkV
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-07-14-05-22-57-0001-GeometryCheckTemplate6xFFFMVkV
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\models\PDF\reportes.py:154: FutureWarning: Setting an item of incompatible dtype is deprecated and will raise an error in a future version of pandas. Value '' has dtype incompatible with float64, please explicitly cast to a compatible dtype first.
  df.loc[df[df.columns[0]] == values[0], 'Umbrales'] = values[1]
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-07-15-05-31-03-0007-GeometryCheckTemplate6xFFFMVkV
Ya existe la fecha
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-07-15-05-31-03-0007-GeometryCheckTemplate6xFFFMVkV
Ya existe la fecha
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-07-16-05-37-30-0001-GeometryCheckTemplate6xFFFMVkV
Ya existe la fecha
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-07-13-15-46-18-0000-GeometryCheckTemplate6xFFFMVkV
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-07-13-15-46-18-0000-GeometryCheckTemplate6xFFFMVkV
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-07-13-15-46-18-0000-GeometryCheckTemplate6xFFFMVkV
Ya existe la fecha
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-07-14-05-22-57-0001-GeometryCheckTemplate6xFFFMVkV
Ya existe la fecha
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-07-13-15-46-18-0000-GeometryCheckTemplate6xFFFMVkV
Ya existe la fecha
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-07-06-05-48-06-0000-GeometryCheckTemplate6xFFFMVkV
Ya existe la fecha
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-07-10-05-14-44-0002-GeometryCheckTemplate6xFFFMVkV
Ya existe la fecha
Listando carpetas...
No se encontró carpeta para esa fecha.
Listando carpetas...
No se encontró carpeta para esa fecha.
Listando carpetas...
Carpeta encontrada: C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon\HAL-TRT-SN1161-2026-08-06-05-01-47-0000-GeometryCheckTemplate6xFFFMVkV
Ya existe la fecha

 *  History restored 

PS C:\Users\parra\Documents\AUNA_Codigos_2026> (Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& c:\Users\parra\Documents\AUNA_Codigos_2026\Python_Personal\.venv\Scripts\Activate.ps1)
(Python_Personal) PS C:\Users\parra\Documents\AUNA_Codigos_2026> cd "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2"
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2> 
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2> python main.py
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
initDATA: 0.013s
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
iniGUI: 0.094s
load table: 0.273s
asignar_encabezados: 0.274s
button_click: 0.275s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x0000018E7A067DD0>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x0000018E7A067DD0>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
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
Insertando datos de equipos para IX
Insertados 4 registros de equipos correctamente
Actualizando tabla de controles anuales para Clinac ix
Actualizando tabla de controles anuales para Clinac ix
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tamano_campo', 'factor_campo', 'factor_campo_esperado', 'discrepancia'] para tabla_factor_campo

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factor_campo, id = True

▥ Datos a insertar en tabla_factor_campo:
  - [19, 0, '3x3', '3', '3', '0.00']
  - [19, 0, '10x10', '10', '10', '0.00']
  - [19, 0, '15x15', '15', '15', '0.00']
  - [19, 0, '20x20', '20', '20', '0.00']
  - [19, 0, '25x25', '25', '25', '0.00']
  - [19, 0, '30x30', '30', '30', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factor_campo subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tamano_campo', 'factor_campo', 'factor_campo_esperado', 'discrepancia'] para tabla_factor_campo

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factor_campo, id = True

▥ Datos a insertar en tabla_factor_campo:
  - [19, 0, '3x3', '3', '3', '0.00']
  - [19, 0, '10x10', '10', '10', '0.00']
  - [19, 0, '15x15', '15', '15', '0.00']
  - [19, 0, '20x20', '20', '20', '0.00']
  - [19, 0, '25x25', '25', '25', '0.00']
  - [19, 0, '30x30', '30', '30', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factor_campo subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tamano_campo', 'factor_campo', 'factor_campo_esperado', 'discrepancia'] para tabla_factor_campo

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factor_campo, id = True

▥ Datos a insertar en tabla_factor_campo:
  - [19, 1, '3x3', '1', '1', '0.00']
  - [19, 1, '1', '1', '1', '0.00']
  - [19, 1, '1', '1', '1', '0.00']
  - [19, 1, '1', '1', '1', '0.00']
  - [19, 1, '1', '1', '1', '0.00']
  - [19, 1, '1', '1', '1', '0.00']
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\data\ManejoDatos\load.py", line 614, in loadtablacomplex
    cursor.executemany(sql, datos)
sqlite3.IntegrityError: UNIQUE constraint failed: tabla_factor_campo.ref, tabla_factor_campo.id_energia, tabla_factor_campo.tamano_campo
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factor_campo subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tamano_campo', 'factor_campo', 'factor_campo_esperado', 'discrepancia'] para tabla_factor_campo

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factor_campo, id = True

▥ Datos a insertar en tabla_factor_campo:
  - [19, 2, '3x3', '1', '1', '0.00']
  - [19, 2, '10x10', '1', '1', '0.00']
  - [19, 2, '15x15', '1', '1', '0.00']
  - [19, 2, '20x20', '1', '1', '0.00']
  - [19, 2, '25x25', '1', '1', '0.00']
  - [19, 2, '30x30', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factor_campo subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tamano_campo', 'factor_campo', 'factor_campo_esperado', 'discrepancia'] para tabla_factor_campo

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factor_campo, id = True

▥ Datos a insertar en tabla_factor_campo:
  - [19, 2, '3x3', '1', '1', '0.00']
  - [19, 2, '10x10', '1', '1', '0.00']
  - [19, 2, '15x15', '1', '1', '0.00']
  - [19, 2, '20x20', '1', '1', '0.00']
  - [19, 2, '25x25', '1', '1', '0.00']
  - [19, 2, '30x30', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factor_campo subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tamano_campo', 'factor_campo', 'factor_campo_esperado', 'discrepancia'] para tabla_factor_campo

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factor_campo, id = True

▥ Datos a insertar en tabla_factor_campo:
  - [19, 3, '3x3', '1', '1', '0.00']
  - [19, 3, '10x10', '1', '1', '0.00']
  - [19, 3, '15x15', '1', '1', '0.00']
  - [19, 3, '20x20', '1', '1', '0.00']
  - [19, 3, '25x25', '1', '1', '0.00']
  - [19, 3, '30x30', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factor_campo subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tamano_campo', 'factor_campo', 'factor_campo_esperado', 'discrepancia'] para tabla_factor_campo

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factor_campo, id = True

▥ Datos a insertar en tabla_factor_campo:
  - [19, 4, '3x3', '1', '1', '0.00']
  - [19, 4, '10x10', '1', '1', '0.00']
  - [19, 4, '15x15', '1', '1', '0.00']
  - [19, 4, '20x20', '1', '1', '0.00']
  - [19, 4, '25x25', '1', '1', '0.00']
  - [19, 4, '30x30', '1', '1', '100.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factor_campo subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tamano_campo', 'factor_campo', 'factor_campo_esperado', 'discrepancia'] para tabla_factor_campo

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factor_campo, id = True

▥ Datos a insertar en tabla_factor_campo:
  - [19, 5, '3x3', '1', '1', '0.00']
  - [19, 5, '10x10', '1', '1', '0.00']
  - [19, 5, '15x15', '1', '1', '0.00']
  - [19, 5, '20x20', '1', '1', '0.00']
  - [19, 5, '25x25', '1', '1', '0.00']
  - [19, 5, '30x30', '1', '1', '100.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factor_campo subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tamano_campo', 'factor_campo', 'factor_campo_esperado', 'discrepancia'] para tabla_factor_campo

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factor_campo, id = True

▥ Datos a insertar en tabla_factor_campo:
  - [19, 5, '3x3', '1', '1', '0.00']
  - [19, 5, '10x10', '1', '1', '0.00']
  - [19, 5, '15x15', '1', '1', '0.00']
  - [19, 5, '20x20', '1', '1', '0.00']
  - [19, 5, '25x25', '1', '1', '0.00']
  - [19, 5, '30x30', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factor_campo subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'angulo', 'factor_transmision', 'factor_transmision_esperado', 'discrepancia'] para tabla_factores_transmision

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factores_transmision, id = True

▥ Datos a insertar en tabla_factores_transmision:
  - [19, 0, '15°', '1', '1', '0.00']
  - [19, 0, '30°', '1', '1', '0.00']
  - [19, 0, '45°', '1', '1', '0.00']
  - [19, 0, '60°', '1', '1', '0.00']
  - [19, 0, 'MLC', '1', '1', '100.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_transmision subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'angulo', 'factor_transmision', 'factor_transmision_esperado', 'discrepancia'] para tabla_factores_transmision

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factores_transmision, id = True

▥ Datos a insertar en tabla_factores_transmision:
  - [19, 1, '15°', '1', '1', '0.00']
  - [19, 1, '30°', '1', '1', '0.00']
  - [19, 1, '45°', '1', '1', '0.00']
  - [19, 1, '60°', '1', '1', '0.00']
  - [19, 1, 'MLC', '1', '1', '100.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_transmision subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'angulo', 'factor_transmision', 'factor_transmision_esperado', 'discrepancia'] para tabla_factores_transmision

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factores_transmision, id = True

▥ Datos a insertar en tabla_factores_transmision:
  - [19, 2, '15°', '1', '1', '0.00']
  - [19, 2, '30°', '1', '1', '0.00']
  - [19, 2, '45°', '1', '1', '0.00']
  - [19, 2, '60°', '1', '1', '0.00']
  - [19, 2, 'MLC', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_transmision subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'angulo', 'factor_transmision', 'factor_transmision_esperado', 'discrepancia'] para tabla_factores_transmision

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factores_transmision, id = True

▥ Datos a insertar en tabla_factores_transmision:
  - [19, 3, '15°', '1', '1', '0.00']
  - [19, 3, '30°', '1', '1', '0.00']
  - [19, 3, '45°', '1', '1', '0.00']
  - [19, 3, '60°', '1', '1', '0.00']
  - [19, 3, 'MLC', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_transmision subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'angulo', 'factor_transmision', 'factor_transmision_esperado', 'discrepancia'] para tabla_factores_transmision

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factores_transmision, id = True

▥ Datos a insertar en tabla_factores_transmision:
  - [19, 4, '15°', '1', '1', '0.00']
  - [19, 4, '30°', '1', '1', '0.00']
  - [19, 4, '45°', '1', '1', '0.00']
  - [19, 4, '60°', '1', '1', '0.00']
  - [19, 4, 'MLC', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_transmision subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'angulo', 'factor_transmision', 'factor_transmision_esperado', 'discrepancia'] para tabla_factores_transmision

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factores_transmision, id = True

▥ Datos a insertar en tabla_factores_transmision:
  - [19, 5, '15°', '1', '1', '0.00']
  - [19, 5, '30°', '1', '1', '0.00']
  - [19, 5, '45°', '1', '1', '0.00']
  - [19, 5, '60°', '1', '1', '0.00']
  - [19, 5, 'MLC', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_transmision subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 0, 'PDD (10 x 10)', '5', '1', '1', '0.00']
  - [19, 0, 'PDD (10 x 10)', '10', '1', '1', '0.00']
  - [19, 0, 'PDD (10 x 10)', '15', '1', '1', '0.00']
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 0, 'PPD (15 x 15)', '5', '1', '1', '0.00']
  - [19, 0, 'PPD (15 x 15)', '10', '1', '1', '0.00']
  - [19, 0, 'PPD (15 x 15)', '15', '1', '1', '0.00']
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 0, 'PPD (20 x 20)', '5', '1', '1', '0.00']
  - [19, 0, 'PPD (20 x 20)', '10', '1', '1', '0.00']
  - [19, 0, 'PPD (20 x 20)', '15', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_sobre_eje subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 1, 'PDD (10 x 10)', '5', '1', '1', '0.00']
  - [19, 1, 'PDD (10 x 10)', '10', '1', '1', '0.00']
  - [19, 1, 'PDD (10 x 10)', '15', '1', '1', '0.00']
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 1, 'PPD (15 x 15)', '5', '1', '1', '0.00']
  - [19, 1, 'PPD (15 x 15)', '10', '1', '1', '0.00']
  - [19, 1, 'PPD (15 x 15)', '15', '1', '1', '0.00']
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 1, 'PPD (20 x 20)', '5', '1', '1', '0.00']
  - [19, 1, 'PPD (20 x 20)', '10', '1', '1', '0.00']
  - [19, 1, 'PPD (20 x 20)', '15', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_sobre_eje subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 2, 'PDD (10 x 10)', '5', '1', '1', '0.00']
  - [19, 2, 'PDD (10 x 10)', '10', '1', '1', '0.00']
  - [19, 2, 'PDD (10 x 10)', '15', '1', '1', '0.00']
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 2, 'PPD (15 x 15)', '5', '1', '1', '0.00']
  - [19, 2, 'PPD (15 x 15)', '10', '1', '1', '0.00']
  - [19, 2, 'PPD (15 x 15)', '15', '1', '1', '0.00']
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 2, 'PPD (20 x 20)', '5', '1', '1', '0.00']
  - [19, 2, 'PPD (20 x 20)', '10', '1', '1', '0.00']
  - [19, 2, 'PPD (20 x 20)', '15', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_sobre_eje subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 3, 'PDD (10 x 10)', '5', '1', '1', '0.00']
  - [19, 3, 'PDD (10 x 10)', '10', '1', '1', '0.00']
  - [19, 3, 'PDD (10 x 10)', '15', '1', '1', '0.00']
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 3, 'PPD (15 x 15)', '5', '1', '1', '0.00']
  - [19, 3, 'PPD (15 x 15)', '10', '1', '1', '0.00']
  - [19, 3, 'PPD (15 x 15)', '15', '1', '1', '0.00']
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 3, 'PPD (20 x 20)', '5', '1', '1', '0.00']
  - [19, 3, 'PPD (20 x 20)', '10', '1', '1', '0.00']
  - [19, 3, 'PPD (20 x 20)', '15', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_sobre_eje subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 4, 'PDD (10 x 10)', '5', '1', '1', '0.00']
  - [19, 4, 'PDD (10 x 10)', '10', '1', '1', '0.00']
  - [19, 4, 'PDD (10 x 10)', '15', '1', '1', '0.00']
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 4, 'PPD (15 x 15)', '5', '1', '1', '0.00']
  - [19, 4, 'PPD (15 x 15)', '10', '1', '1', '0.00']
  - [19, 4, 'PPD (15 x 15)', '15', '1', '1', '0.00']
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 4, 'PPD (20 x 20)', '5', '1', '1', '0.00']
  - [19, 4, 'PPD (20 x 20)', '10', '1', '1', '0.00']
  - [19, 4, 'PPD (20 x 20)', '15', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_sobre_eje subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 5, 'PDD (10 x 10)', '5', '1', '1', '0.00']
  - [19, 5, 'PDD (10 x 10)', '10', '1', '1', '0.00']
  - [19, 5, 'PDD (10 x 10)', '15', '1', '1', '0.00']
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 5, 'PPD (15 x 15)', '5', '1', '1', '0.00']
  - [19, 5, 'PPD (15 x 15)', '10', '1', '1', '0.00']
  - [19, 5, 'PPD (15 x 15)', '15', '1', '1', '0.00']
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tam_pdd', 'profundidad', 'ppd', 'ppd_esperado', 'discrepancia'] para tabla_factores_sobre_eje

Bloque identificado por ['ref', 'id_energia', 'tam_pdd'] para la tabla tabla_factores_sobre_eje, id = True

▥ Datos a insertar en tabla_factores_sobre_eje:
  - [19, 5, 'PPD (20 x 20)', '5', '1', '1', '0.00']
  - [19, 5, 'PPD (20 x 20)', '10', '1', '1', '0.00']
  - [19, 5, 'PPD (20 x 20)', '15', '1', '1', '0.00']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_factores_sobre_eje subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicador_medir', 'valor_medido'] para tabla_control_camaras_monitoras

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_control_camaras_monitoras, id = True

▥ Datos a insertar en tabla_control_camaras_monitoras:
  - [19, 0, 'Fac. Calibración', '1']
  - [19, 0, 'Reproducibilidad', '1']
  - [19, 0, 'Linealidad R2', '1']
  - [19, 0, 'Tasa mínima 80 cGy/min', '1']
  - [19, 0, 'Tasa intermedia 160 cGy/min', '1']
  - [19, 0, 'Tasa máxima 400 cGy/min', '1']
  - [19, 0, 'Desviación estándar', '1']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_control_camaras_monitoras subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicador_medir', 'valor_medido'] para tabla_control_camaras_monitoras

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_control_camaras_monitoras, id = True

▥ Datos a insertar en tabla_control_camaras_monitoras:
  - [19, 1, 'Fac. Calibración', '1']
  - [19, 1, 'Reproducibilidad', '1']
  - [19, 1, 'Linealidad R2', '1']
  - [19, 1, 'Tasa mínima 80 cGy/min', '1']
  - [19, 1, 'Tasa intermedia 160 cGy/min', '1']
  - [19, 1, 'Tasa máxima 400 cGy/min', '1']
  - [19, 1, 'Desviación estándar', '1']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_control_camaras_monitoras subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicador_medir', 'valor_medido'] para tabla_control_camaras_monitoras

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_control_camaras_monitoras, id = True

▥ Datos a insertar en tabla_control_camaras_monitoras:
  - [19, 2, 'Fac. Calibración', '1']
  - [19, 2, 'Reproducibilidad', '1']
  - [19, 2, 'Linealidad R2', '1']
  - [19, 2, 'Tasa mínima 80 cGy/min', '1']
  - [19, 2, 'Tasa intermedia 160 cGy/min', '1']
  - [19, 2, 'Tasa máxima 400 cGy/min', '1']
  - [19, 2, 'Desviación estándar', '1']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_control_camaras_monitoras subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicador_medir', 'valor_medido'] para tabla_control_camaras_monitoras

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_control_camaras_monitoras, id = True

▥ Datos a insertar en tabla_control_camaras_monitoras:
  - [19, 3, 'Fac. Calibración', '1']
  - [19, 3, '1', '1']
  - [19, 3, 'Linealidad R2', '1']
  - [19, 3, 'Tasa mínima 80 cGy/min', '1']
  - [19, 3, 'Tasa intermedia 160 cGy/min', '1']
  - [19, 3, 'Tasa máxima 400 cGy/min', '1']
  - [19, 3, 'Desviación estándar', '']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_control_camaras_monitoras subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicador_medir', 'valor_medido'] para tabla_control_camaras_monitoras

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_control_camaras_monitoras, id = True

▥ Datos a insertar en tabla_control_camaras_monitoras:
  - [19, 4, 'Fac. Calibración', '1']
  - [19, 4, 'Reproducibilidad', '1']
  - [19, 4, 'Linealidad R2', '1']
  - [19, 4, 'Tasa mínima 80 cGy/min', '1']
  - [19, 4, 'Tasa intermedia 160 cGy/min', '1']
  - [19, 4, 'Tasa máxima 400 cGy/min', '1']
  - [19, 4, 'Desviación estándar', '']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_control_camaras_monitoras subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicador_medir', 'valor_medido'] para tabla_control_camaras_monitoras

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_control_camaras_monitoras, id = True

▥ Datos a insertar en tabla_control_camaras_monitoras:
  - [19, 5, 'Fac. Calibración', '1']
  - [19, 5, 'Reproducibilidad', '1']
  - [19, 5, 'Linealidad R2', '1']
  - [19, 5, 'Tasa mínima 80 cGy/min', '1']
  - [19, 5, 'Tasa intermedia 160 cGy/min', '1']
  - [19, 5, 'Tasa máxima 400 cGy/min', '1']
  - [19, 5, 'Desviación estándar', '1']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_control_camaras_monitoras subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicador_medir', 'valor_medido'] para tabla_control_camaras_monitoras

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_control_camaras_monitoras, id = True

▥ Datos a insertar en tabla_control_camaras_monitoras:
  - [19, 4, 'Fac. Calibración', '1']
  - [19, 4, 'Reproducibilidad', '1']
  - [19, 4, 'Linealidad R2', '1']
  - [19, 4, 'Tasa mínima 80 cGy/min', '1']
  - [19, 4, 'Tasa intermedia 160 cGy/min', '1']
  - [19, 4, 'Tasa máxima 400 cGy/min', '1']
  - [19, 4, 'Desviación estándar', '1']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_control_camaras_monitoras subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicador_medir', 'valor_medido'] para tabla_control_camaras_monitoras

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_control_camaras_monitoras, id = True

▥ Datos a insertar en tabla_control_camaras_monitoras:
  - [19, 3, 'Fac. Calibración', '1']
  - [19, 3, '1', '1']
  - [19, 3, 'Linealidad R2', '1']
  - [19, 3, 'Tasa mínima 80 cGy/min', '1']
  - [19, 3, 'Tasa intermedia 160 cGy/min', '1']
  - [19, 3, 'Tasa máxima 400 cGy/min', '1']
  - [19, 3, 'Desviación estándar', '1']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_control_camaras_monitoras subida(s) correctamente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicador_medir', 'valor_medido'] para tabla_control_camaras_monitoras

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_control_camaras_monitoras, id = True

▥ Datos a insertar en tabla_control_camaras_monitoras:
  - [19, 2, 'Fac. Calibración', '1']
  - [19, 2, 'Reproducibilidad', '1']
  - [19, 2, 'Linealidad R2', '1']
  - [19, 2, 'Tasa mínima 80 cGy/min', '1']
  - [19, 2, 'Tasa intermedia 160 cGy/min', '1']
  - [19, 2, 'Tasa máxima 400 cGy/min', '1']
  - [19, 2, 'Desviación estándar', '1']
Actualizando tabla de controles anuales para Clinac ix
Tabla(s) tabla_control_camaras_monitoras subida(s) correctamente
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\respaldos_bd\BaseDatosQA_2026-08-26_152919.db
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
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\respaldos_bd\BaseDatosQA_2026-08-26_153005.db
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x0000018E7B0B8C50>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
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
iniGUI: 0.054s
load table: 0.183s
asignar_encabezados: 0.184s
button_click: 0.185s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x0000018E7B0B8C50>, id_f1_num usado: Administrador
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
Recursos limpiados correctamente
Insertando datos de equipos para IX
Insertados 4 registros de equipos correctamente
Actualizando tabla de controles anuales para Clinac ix
Actualizando tabla de controles anuales para Clinac ix
Insertando datos de equipos para IX
Insertados 4 registros de equipos correctamente
Actualizando tabla de controles anuales para Clinac ix
Actualizando tabla de controles anuales para Clinac ix
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-25-2\respaldos_bd\BaseDatosQA_2026-08-26_153115.db