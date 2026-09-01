# Revision Rebuild windows 3 de Agosto de 2026

Anotaciones:
- Parece que funciona bastante bien el sistema de seleccion de equipos dentro de la calculadora dosimetrica de los formularios mensuales, aparecen todas las camaras en la seleccion de equipos, pero no todas las series, dependiendo o no de si esta activo el equipo, para ver camaras vencidas y hacer pruebas, manteniendo el entorno limpio y todo eso, se puede rapidamente activar una camara especifica que se quiera analisar e inmediatamente se nota el efecto dentro de la aplicacion, aparece la camara y aparece su vigencia de forma correcta, conclusion, todo esto que se menciona es lo deseado.
-  La activacion de un equipo no debe generar una nueva fila, verificar con Claude que no suceda. Aparentemente cambiar el estado activo no cambia nada, pero cambiar la fecha si genera una nueva fila de 39 a 40.
- En la tabla equipos N30013/2123 simplemente aparecen dos filas de registro practicamente iguales, una activa otra no, no se si esta era la intencion, no haber modificado informacion historica importante, si solo fue algo asi como rellener el voltaje, algunos otros datos entonces todo bien, no pasa nada.
- Para etapas posteriores del plan se puede agregar un filtro para la tabla de equipos, como la de registros.
- Depronto aclarar que tantos colores tiene el codigo de color/semaforo de la tabla de equipos y que indica cada uno.
- Hay algun error al momento de introducir valores en la informacion de un nuevo equipo, que significa esto "could not convert string to float: ''" y porque sale varias veces cuando se hace una edicion en la tabla si no estoy mal.
- Tablas es ON DELETE RESTRICT ON UPDATE CASCADE, algunas de ellas, las que tiene estas caracterisiticas las otras simplemente no indican nada de esto, ni CASCADE ni RESTRICT.
- Creo que hace falta que los widgets de los parametros del equipo donde se introduce la informacion se deshabiliten luego de darle aceptar a los cambios, porque despues de hacer los cambios a quedado activa, esto no me parece un comportamiento adecuado aunque no es urgente. De resto funcionan bien. Ademas, como queda abierto, si vuelvo a modificar un campo y le doy a aceptar nuevamente salta un error que dice "No hay equipo seleccionado" por lo tanto sigue pareciendome la mejor opcion deshabilitar la escritura de texto en los widgets luego de darle aceptar los cambios. (No urgente)
- Creo que la bifuracion de las filas solo se deberia dar al cambiar la fecha, pero incluso eso, todo esto respecto a este tema, mis anotaciones, hay que dejarlas como deudas de diseno.
- De que forma intervienen los valores puestos en los widgets recientemente agregados para el PDD 20 y PDD 10. Si no hacen nada, y en el excel tampoco hay un dato de donde se pueda extraer hay que eliminarlo/ocultarlo. Recordar por que lo agregamos o de donde sale esto. (Esto no es una deuda de diseno, y si es urgente.)
- No se porque esta activa una de las series de la HDR1000 Plus/A092535 con fecha de calibracion del 2022 y no una del 2025.
- En la parte del control mensual de braquiterapia es importante tambien agregar en una futura etapa lo de que abrir un nuevo formulario mensual muestre limpio todos los widgets.



Expulsion de la terminal:
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03> .\.venv\Scripts\python.exe build_exe.py
74 INFO: PyInstaller: 6.21.0, contrib hooks: 2026.6
74 INFO: Python: 3.11.0
84 INFO: Platform: Windows-10-10.0.26200-SP0
84 INFO: Python environment: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\.venv
85 INFO: wrote C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\RAD-QA.spec
86 INFO: Removing temporary files and cleaning cache in C:\Users\parra\AppData\Local\pyinstaller
3691 INFO: Module search paths (PYTHONPATH):
['C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311\\python311.zip',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311\\DLLs',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311\\Lib',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\win32',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\win32\\lib',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\pythonwin',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03']
3901 INFO: Appending 'datas' from .spec
3909 INFO: checking Analysis
3909 INFO: Building Analysis because Analysis-00.toc is non existent
3909 INFO: Looking for Python shared library...
3910 INFO: Using Python shared library: C:\Users\parra\AppData\Local\Programs\Python\Python311\python311.dll
3910 INFO: Running Analysis Analysis-00.toc
3910 INFO: Target bytecode optimization level: 0
3910 INFO: Initializing module dependency graph...
3911 INFO: Initializing module graph hook caches...
3920 INFO: Analyzing modules for base_library.zip ...
4465 INFO: Processing standard module hook 'hook-heapq.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
4504 INFO: Processing standard module hook 'hook-encodings.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
5018 INFO: Processing standard module hook 'hook-math.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
5212 INFO: Processing standard module hook 'hook-pickle.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
5885 INFO: Caching module dependency graph...
5906 INFO: Analyzing C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\main.py
5909 INFO: Processing standard module hook 'hook-PyQt5.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
6383 INFO: Processing standard module hook 'hook-PyQt5.QtWidgets.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
7802 INFO: Processing standard module hook 'hook-PyQt5.QtCore.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
9658 INFO: Processing standard module hook 'hook-PyQt5.QtGui.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
17607 INFO: Processing standard module hook 'hook-sqlite3.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
17783 INFO: Processing standard module hook 'hook-cryptography.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
20147 INFO: hook-cryptography: cryptography does not seem to be using dynamically linked OpenSSL.
20212 INFO: Processing standard module hook 'hook-numpy.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
20455 INFO: Processing standard module hook 'hook-difflib.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
20559 INFO: Processing standard module hook 'hook-multiprocessing.util.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
20629 INFO: Processing standard module hook 'hook-xml.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
20756 INFO: Processing standard module hook 'hook-_ctypes.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
21090 INFO: Processing standard module hook 'hook-sysconfig.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
21129 INFO: Processing standard module hook 'hook-platform.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
21340 INFO: Processing standard module hook 'hook-webbrowser.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
21699 INFO: Processing pre-safe-import-module hook 'hook-typing_extensions.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
21700 INFO: SetuptoolsInfo: initializing cached setuptools info...
23020 INFO: Processing standard module hook 'hook-charset_normalizer.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
23184 INFO: Processing standard module hook 'hook-PyQt5.QtSql.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
23516 INFO: Processing standard module hook 'hook-pandas.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
24691 INFO: Processing standard module hook 'hook-pytz.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
24905 INFO: Processing standard module hook 'hook-scipy.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
25281 INFO: Processing standard module hook 'hook-pycparser.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
25367 INFO: Processing standard module hook 'hook-setuptools.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
25371 INFO: Processing pre-safe-import-module hook 'hook-distutils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
25371 INFO: Processing pre-find-module-path hook 'hook-distutils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_find_module_path'
25720 INFO: Processing standard module hook 'hook-distutils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
25749 INFO: Processing standard module hook 'hook-distutils.util.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
25766 INFO: Processing standard module hook 'hook-_osx_support.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
25895 INFO: Processing standard module hook 'hook-pkg_resources.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
26492 INFO: Processing pre-safe-import-module hook 'hook-importlib_metadata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
26540 INFO: Processing pre-safe-import-module hook 'hook-packaging.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
27299 INFO: Processing standard module hook 'hook-scipy.linalg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
27398 INFO: Processing standard module hook 'hook-scipy.special._ufuncs.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
27995 INFO: Processing standard module hook 'hook-scipy.spatial._ckdtree.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
28025 INFO: Processing standard module hook 'hook-matplotlib.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
28264 INFO: Processing pre-safe-import-module hook 'hook-gi.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
28407 INFO: Processing standard module hook 'hook-matplotlib.backend_bases.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
28526 INFO: Processing standard module hook 'hook-PIL.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
28565 INFO: Processing standard module hook 'hook-PIL.Image.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
28753 INFO: Processing standard module hook 'hook-xml.etree.cElementTree.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
28914 INFO: Processing standard module hook 'hook-PIL.ImageFilter.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
29292 INFO: Processing standard module hook 'hook-matplotlib.backends.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
29329 INFO: Processing standard module hook 'hook-matplotlib.pyplot.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
30001 INFO: Processing standard module hook 'hook-dateutil.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
30038 INFO: Processing pre-safe-import-module hook 'hook-six.moves.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
31001 INFO: Processing standard module hook 'hook-scipy.spatial.transform.rotation.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
31871 INFO: Processing standard module hook 'hook-scipy.stats._stats.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
32125 INFO: Processing standard module hook 'hook-scipy.sparse.csgraph.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
32695 INFO: Processing standard module hook 'hook-scipy.special._ellip_harm_2.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
34210 INFO: Processing standard module hook 'hook-pandas.io.formats.style.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
35337 INFO: Processing standard module hook 'hook-pandas.plotting.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
35558 INFO: Processing standard module hook 'hook-openpyxl.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
36655 INFO: Processing standard module hook 'hook-pandas.io.clipboard.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
36831 INFO: Processing standard module hook 'hook-xml.dom.domreg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
37287 INFO: Processing standard module hook 'hook-reportlab.lib.utils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
37327 INFO: Processing standard module hook 'hook-reportlab.pdfbase._fontdata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
38645 INFO: Processing standard module hook 'hook-pydicom.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
39194 INFO: Processing pre-safe-import-module hook 'hook-importlib_resources.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
43070 INFO: Processing standard module hook 'hook-pyqtgraph.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
312 WARNING: Failed to collect submodules for 'pyqtgraph.opengl' because importing 'pyqtgraph.opengl' raised: ModuleNotFoundError: No module named 'OpenGL'
43722 INFO: hook-pyqtgraph: selected 'PyQt5' as Qt bindings because hook for 'PyQt5' has been run before.
43738 INFO: Processing standard module hook 'hook-PyQt5.uic.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
43847 INFO: Processing pre-find-module-path hook 'hook-PyQt5.uic.port_v2.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_find_module_path'
43881 INFO: Processing standard module hook 'hook-PyQt5.QtSvg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
44885 INFO: Processing standard module hook 'hook-PyQt5.QtTest.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
46386 INFO: Processing standard module hook 'hook-matplotlib.backends.backend_qtagg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
46389 INFO: Processing standard module hook 'hook-matplotlib.backends.qt_compat.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
46390 INFO: hook-matplotlib.backends.qt_compat: selected 'PyQt5' as Qt bindings because hook for 'PyQt5' has been run before.
47064 INFO: Processing standard module hook 'hook-plotly.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
47886 INFO: Processing standard module hook 'hook-narwhals.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
51756 INFO: Processing standard module hook 'hook-skimage.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
51808 INFO: Processing standard module hook 'hook-skimage.measure.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
52658 INFO: Processing standard module hook 'hook-pydantic.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
53167 INFO: Processing standard module hook 'hook-zoneinfo.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
53630 INFO: Processing standard module hook 'hook-dns.rdata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
54125 INFO: Processing standard module hook 'hook-pythoncom.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
54186 INFO: Processing standard module hook 'hook-pywintypes.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
54478 INFO: Processing standard module hook 'hook-skimage.filters.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
57032 INFO: Processing standard module hook 'hook-skimage.draw.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
57337 INFO: Processing standard module hook 'hook-skimage.transform.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
57683 INFO: Processing standard module hook 'hook-skimage.segmentation.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
58014 INFO: Processing standard module hook 'hook-skimage.exposure.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
58346 INFO: Processing standard module hook 'hook-skimage.morphology.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
58970 INFO: Processing standard module hook 'hook-skimage.feature.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
59421 INFO: Processing standard module hook 'hook-cv2.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
59980 INFO: Processing standard module hook 'hook-msoffcrypto.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
60166 INFO: Processing pre-safe-import-module hook 'hook-win32com.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\pre_safe_import_module'
60229 INFO: Processing standard module hook 'hook-win32com.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
60941 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.IX'
60951 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.halcyon'
60960 INFO: Analyzing hidden import 'ui.paginasControles.PruebasMensuales.ix_mensual'
60966 INFO: Analyzing hidden import 'ui.paginasControles.PruebasMensuales.tac_mensual'
61128 INFO: Analyzing hidden import 'ui.paginasControles.PruebasAnuales.ix_anual'
61153 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.seiscientos'
61160 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.braquiterapia'
61324 INFO: Analyzing hidden import 'pylinac.contrib'
61325 INFO: Analyzing hidden import 'pylinac.contrib.orthogonality'
61329 INFO: Analyzing hidden import 'pylinac.contrib.quasar'
61331 INFO: Analyzing hidden import 'pylinac.core.metrics'
61332 INFO: Analyzing hidden import 'pylinac.dlg'
61334 INFO: Analyzing hidden import 'pylinac.nuclear'
61363 INFO: Analyzing hidden import 'pylinac.plan_generator'
61363 INFO: Analyzing hidden import 'pylinac.plan_generator.dicom'
61386 INFO: Processing module hooks (post-graph stage)...
61478 WARNING: Hidden import "pycparser.lextab" not found!
61479 WARNING: Hidden import "pycparser.yacctab" not found!
61604 INFO: Processing pre-safe-import-module hook 'hook-tomli.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
61762 INFO: Processing standard module hook 'hook-skimage.color.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
62222 INFO: Processing standard module hook 'hook-skimage.restoration.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
62580 INFO: Processing standard module hook 'hook-skimage.metrics.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
63073 INFO: Processing standard module hook 'hook-matplotlib.backends.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
63074 INFO: Matplotlib backend selection method: automatic discovery of used backends
63108 INFO: Discovered Matplotlib backend(s) via `matplotlib.use()` call in module 'models.PDF.Mensuales.reportes_mensuales': ['Agg', 'Agg', 'Agg']
63147 INFO: The following Matplotlib backends were discovered by scanning for `matplotlib.use()` calls: ['Agg']. If your backend of choice is not in this list, either add a `matplotlib.use()` call to your code, or configure the backend collection via hook options (see: https://pyinstaller.org/en/stable/hooks-config.html#matplotlib-hooks).
63147 INFO: Selected matplotlib backends: ['Agg']
63407 INFO: Processing standard module hook 'hook-PIL.SpiderImagePlugin.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
63843 WARNING: Hidden import "scipy.special._cdflib" not found!
63871 INFO: Processing standard module hook 'hook-setuptools._vendor.importlib_metadata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
63929 INFO: Processing standard module hook 'hook-setuptools._vendor.jaraco.text.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
64452 INFO: Processing standard module hook 'hook-tzdata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
64810 INFO: Performing binary vs. data reclassification (1839 entries)
64924 INFO: Looking for ctypes DLLs
65074 INFO: Analyzing run-time hooks ...
65089 INFO: Including run-time hook 'pyi_rth_mplconfig.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
65090 INFO: Processing pre-find-module-path hook 'hook-_pyi_rth_utils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_find_module_path'
65092 INFO: Processing standard module hook 'hook-_pyi_rth_utils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
65097 INFO: Including run-time hook 'pyi_rth_pkgutil.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
65099 INFO: Including run-time hook 'pyi_rth_multiprocessing.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
65101 INFO: Including run-time hook 'pyi_rth_setuptools.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
65101 INFO: Including run-time hook 'pyi_rth_pkgres.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
65104 INFO: Including run-time hook 'pyi_rth_pywintypes.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
65104 INFO: Including run-time hook 'pyi_rth_pythoncom.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
65104 INFO: Including run-time hook 'pyi_rth_inspect.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
65108 INFO: Including run-time hook 'pyi_rth_pyqt5.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
65110 INFO: Including run-time hook 'pyi_rth_pyqtgraph_multiprocess.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
65111 INFO: Including run-time hook 'pyi_rth_cryptography_openssl.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
65181 INFO: Creating base_library.zip...
65194 INFO: Looking for dynamic libraries
68464 INFO: Extra DLL search directories (AddDllDirectory): ['C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyQt5\\Qt5\\bin', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\numpy.libs', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\scipy.libs', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\pandas.libs', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\cv2\\../../x64/vc14/bin']
68464 INFO: Extra DLL search directories (PATH): ['C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\cv2\\../../x64/vc14/bin', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyQt5\\Qt5\\bin']
70206 WARNING: Library not found: could not resolve 'LIBPQ.dll', dependency of 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-03\\.venv\\Lib\\site-packages\\PyQt5\\Qt5\\plugins\\sqldrivers\\qsqlpsql.dll'.
70480 INFO: Warnings written to C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\build\RAD-QA\warn-RAD-QA.txt
70713 INFO: Graph cross-reference written to C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\build\RAD-QA\xref-RAD-QA.html
70796 INFO: checking PYZ
70796 INFO: Building PYZ because PYZ-00.toc is non existent
70796 INFO: Building PYZ (ZlibArchive) C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\build\RAD-QA\PYZ-00.pyz
73097 INFO: Building PYZ (ZlibArchive) C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\build\RAD-QA\PYZ-00.pyz completed successfully.
73164 INFO: checking PKG
73164 INFO: Building PKG because PKG-00.toc is non existent
73164 INFO: Building PKG (CArchive) RAD-QA.pkg
73197 INFO: Building PKG (CArchive) RAD-QA.pkg completed successfully.
73197 INFO: Bootloader C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\.venv\Lib\site-packages\PyInstaller\bootloader\Windows-64bit-intel\runw.exe
73197 INFO: checking EXE
73197 INFO: Building EXE because EXE-00.toc is non existent
73197 INFO: Building EXE from EXE-00.toc
73197 INFO: Copying bootloader EXE to C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\build\RAD-QA\RAD-QA.exe
73201 INFO: Copying icon to EXE
73203 INFO: Copying 0 resources to EXE
73203 INFO: Embedding manifest in EXE
73205 INFO: Appending PKG archive to EXE
73225 INFO: Fixing EXE headers
73355 INFO: Building EXE from EXE-00.toc completed successfully.
73464 INFO: checking COLLECT
73464 INFO: Building COLLECT because COLLECT-00.toc is non existent
73465 INFO: Building COLLECT COLLECT-00.toc
75033 INFO: Building COLLECT COLLECT-00.toc completed successfully.
75053 INFO: Build complete! The results are available in: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\dist
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03> .venv\Scripts\python scripts\migrar_bd_a_estandar.py "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\BaseDatosQA.db" --aplicar --usuario FelipePP
Base de datos: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\BaseDatosQA.db
integrity_check antes: ok
Backup creado: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\BaseDatosQA.db.pre_migracion_20260804_134421.bak
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
E10: sqlite_sequence normalizada para TipoCalibracion (duplicados -> seq=34)
E10: sqlite_sequence normalizada para aceleradorlineal_600 (duplicados -> seq=365)
E10: sqlite_sequence normalizada para aceleradorlineal_ix (duplicados -> seq=372)
E10: sqlite_sequence normalizada para braqui (duplicados -> seq=426)
E10: sqlite_sequence normalizada para control_conos (duplicados -> seq=89)
E10: sqlite_sequence normalizada para control_cunas (duplicados -> seq=176)
E10: sqlite_sequence normalizada para controles_mensuales (duplicados -> seq=109)
E10: sqlite_sequence normalizada para energias (duplicados -> seq=5)
E10: sqlite_sequence normalizada para equipos (duplicados -> seq=81)
E10: sqlite_sequence normalizada para equipos_medicion (duplicados -> seq=270)
E10: sqlite_sequence normalizada para equipos_mensual (duplicados -> seq=87)
E10: sqlite_sequence normalizada para halcyon (duplicados -> seq=324)
E10: sqlite_sequence normalizada para pruebas (duplicados -> seq=180)
E10: sqlite_sequence normalizada para resolucion_contraste_rois (duplicados -> seq=210)
E10: sqlite_sequence normalizada para resolucion_espacial_regiones (duplicados -> seq=232)
E10: sqlite_sequence normalizada para tabla_control_camaras_monitoras (duplicados -> seq=126)
E10: sqlite_sequence normalizada para tabla_factor_campo (duplicados -> seq=168)
E10: sqlite_sequence normalizada para tabla_factores_sobre_eje (duplicados -> seq=207)
E10: sqlite_sequence normalizada para tabla_factores_transmision (duplicados -> seq=140)
E10: sqlite_sequence normalizada para uniformidad_ruido (duplicados -> seq=130)
E10: sqlite_sequence normalizada para users (duplicados -> seq=13)
E10: sqlite_sequence normalizada para valores_ct (duplicados -> seq=189)
F1: 58 tablas con borrado en cascada -- respaldando antes de recrear el esquema en RESTRICT...
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\respaldos_bd\pre_migracion\BaseDatosQA_2026-08-04_134421.db
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
  calculadora_dosimetrica: columna(s) nueva(s) ['energia', 'pdd_zref_electrones', 'protocolo_trs398', 'r50_medido', 'vigente']
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

Listo. Backup de seguridad conservado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\BaseDatosQA.db.pre_migracion_20260804_134421.bak

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03> python main.py
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
iniGUI: 0.020s
load table: 0.087s
asignar_encabezados: 0.090s
button_click: 0.091s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001C725CC2AD0>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
Físico 2 seleccionado: Cristian Castellanos, ID: 3
user_id_f2 antes de create_control: 3
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
<PyQt5.QtWidgets.QGridLayout object at 0x000001C76B9717E0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C76B971750>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C76B971900>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C76B971870>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C76B971990>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
⚠️ Widgets MLC no encontrados - revisar creación desde Excel
Dialog llamado desde: PruebaMensualIX
could not convert string to float: ''
could not convert string to float: ''
Dialog llamado desde: PruebaMensualIX

Botón editar equipo clickeado (función habilitar2 en equipos.py)
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025

Función editarEquipo en equipos.py
Datos a editar
----------------------------------------------------------------------
Fila seleccionada: 20
ID del equipo seleccionado: 5
    - Datos del equipo recuperados: 
          ('Cámara de ionización', 'N31010', '1825', 0.3034, None, '05/02/2024', 'PTW', 20.9, 98.97, 33, None, 0.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 05/02/2024
Guardando cambios en el equipo...
ID del equipo a actualizar: 5
Dialog llamado desde: PruebaMensualIX

Botón deshabilitar clickeado

Botón editar equipo clickeado (función habilitar2 en equipos.py)
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025

Función editarEquipo en equipos.py
Datos a editar
----------------------------------------------------------------------
Fila seleccionada: 21
ID del equipo seleccionado: 66
    - Datos del equipo recuperados: 
          ('Cámara de ionización', 'N31010', '1825', 0.3034, None, '5/02/2024', 'PTW', 20.9, 98.97, 33, None, 0.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 05/02/2024
Guardando cambios en el equipo...
ID del equipo a actualizar: 66

Botón editar equipo clickeado (función habilitar2 en equipos.py)
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)

Función editarEquipo en equipos.py
Datos a editar
----------------------------------------------------------------------
Fila seleccionada: 20
ID del equipo seleccionado: 5
    - Datos del equipo recuperados: 
          ('Cámara de ionización', 'N31010', '1825', 0.3034, None, '05/02/2024', 'PTW', 20.9, 98.97, 33, None, 1.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 05/02/2024
Guardando cambios en el equipo...
ID del equipo a actualizar: 5

Botón editar equipo clickeado (función habilitar2 en equipos.py)
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)

Función editarEquipo en equipos.py
Datos a editar
----------------------------------------------------------------------
Fila seleccionada: 20
ID del equipo seleccionado: 5
    - Datos del equipo recuperados: 
          ('Cámara de ionización', 'N31010', '1825', 0.3034, None, '05/02/2024', 'PTW', 20.9, 98.97, 33, None, 0.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 05/02/2024
Guardando cambios en el equipo...
ID del equipo a actualizar: 5

Fila seleccionada: 23
ID del equipo seleccionado: 76
    - Datos del equipo recuperados: 
          ('Cámara de ionización', 'N31010', '1825', 0.3045, None, '16/03/2026', 'PTW', 22, 101.325, 50, 300.0, 1.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 16/03/2026
Guardando cambios en el equipo...
ID del equipo a actualizar: 76

Fila seleccionada: 1
ID del equipo seleccionado: 83
    - Datos del equipo recuperados: 
          ('Cámara de ionización', '9999', '0999', 0.199, None, '16/01/2026', 'DingleIndustries', 22, 101.325, 50, 300.0, 1.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 16/01/2026
Guardando cambios en el equipo...
ID del equipo a actualizar: 83
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


Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 16/01/2026
Guardando cambios en el equipo...
ID del equipo a actualizar: 83
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

Botón editar equipo clickeado (función habilitar2 en equipos.py)

Botón deshabilitar clickeado

Botón editar equipo clickeado (función habilitar2 en equipos.py)
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025

Función editarEquipo en equipos.py
Datos a editar
----------------------------------------------------------------------
Fila seleccionada: 2
ID del equipo seleccionado: 84
    - Datos del equipo recuperados: 
          ('Cámara de ionización', '9999', '0999', 0.199, None, '06/01/2026', 'DingleIndustries', 22, 101.325, 50, 300.0, 1.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 06/01/2026
Guardando cambios en el equipo...
ID del equipo a actualizar: 84
Guardando cambios en el equipo...

Botón deshabilitar clickeado

Función editarEquipo en equipos.py
Datos a editar
----------------------------------------------------------------------
Fila seleccionada: 2
ID del equipo seleccionado: 84
    - Datos del equipo recuperados: 
          ('Cámara de ionización', '9999', '0999', 0.199, None, '06/01/2026', 'DingleIndustries', 22, 101.325, 50, 300.0, 1.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 06/01/2026
Guardando cambios en el equipo...
ID del equipo a actualizar: 84
Guardando cambios en el equipo...

Botón deshabilitar clickeado
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\respaldos_bd\BaseDatosQA_2026-08-04_142502.db
    Método open_main_window en la clase: DialogAdminPermiso
admin2025
    Método seleccionar_firma en la clase: VentanaFirma
    Método subir_firma en la clase: VentanaFirma
Usuario <data.ManejoDatos.user.Usuario object at 0x000001C76B941E10> agregado exitosamente.
    Método open_main_window en la clase: DialogAdminPermiso2
admin2025
Contraseña actualizada con éxito
Fdingle
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001C7BA088ED0>, id_f1_num usado: Felipe Parra Paez
Consulta de físicos exitosa: Nombre F1: ['Felipe Parra Paez']
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
Fecha Final COT: 2026-08-04 14:26:15-05:00
Horas transcurridas desde 2026-08-04 14:26:15: 1449.8308333333334
Dias transcurridos: 60.40961805555556
 La actividad es:  7.7414
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
iniGUI: 0.023s
load table: 0.092s
asignar_encabezados: 0.096s
button_click: 0.096s

Botón editar equipo clickeado (función habilitar2 en equipos.py)
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025

Función editarEquipo en equipos.py
Datos a editar
----------------------------------------------------------------------
Fila seleccionada: 3
ID del equipo seleccionado: 85
    - Datos del equipo recuperados: 
          ('Cámara de ionización', '9999', '0999', 0.199, None, '06/01/2025', 'DingleIndustries', 22, 101.325, 50, 300.0, 1.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 06/01/2025
Guardando cambios en el equipo...
ID del equipo a actualizar: 85

Botón deshabilitar clickeado
ID del equipo a eliminar: 86
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025


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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001C7BA088ED0>, id_f1_num usado: Felipe Parra Paez
Consulta de físicos exitosa: Nombre F1: ['Felipe Parra Paez']
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
Fecha Final COT: 2026-08-04 14:26:15-05:00
Horas transcurridas desde 2026-08-04 14:26:15: 1449.8308333333334
Dias transcurridos: 60.40961805555556
 La actividad es:  7.7414
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
iniGUI: 0.023s
load table: 0.092s
asignar_encabezados: 0.096s
button_click: 0.096s

Botón editar equipo clickeado (función habilitar2 en equipos.py)
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025

Función editarEquipo en equipos.py
Datos a editar
----------------------------------------------------------------------
Fila seleccionada: 3
ID del equipo seleccionado: 85
    - Datos del equipo recuperados: 
          ('Cámara de ionización', '9999', '0999', 0.199, None, '06/01/2025', 'DingleIndustries', 22, 101.325, 50, 300.0, 1.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 06/01/2025
Guardando cambios en el equipo...
ID del equipo a actualizar: 85

Botón deshabilitar clickeado
ID del equipo a eliminar: 86
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025

Botón editar equipo clickeado (función habilitar2 en equipos.py)
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001C7BA088ED0>, id_f1_num usado: Felipe Parra Paez
Consulta de físicos exitosa: Nombre F1: ['Felipe Parra Paez']
Físico 2 seleccionado: Cristian Castellanos, ID: 3
user_id_f2 antes de create_control: 3
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
<PyQt5.QtWidgets.QGridLayout object at 0x000001C7B9F11120>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C7B9F111B0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C7B9F11090>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C7B9F11000>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C7B9F10F70>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
⚠️ Widgets MLC no encontrados - revisar creación desde Excel
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
Cociente fuera de rango (2.0 – 5.0)
300
Cociente fuera de rango (2.0 – 5.0)
300
could not convert string to float: ''
300
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''

Fila seleccionada: 23
ID del equipo seleccionado: 76
    - Datos del equipo recuperados: 
          ('Cámara de ionización', 'N31010', '1825', 0.3045, None, '16/03/2026', 'PTW', 22, 101.325, 50, 300.0, 1.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 16/03/2026
Guardando cambios en el equipo...
ID del equipo a actualizar: 76

Botón deshabilitar clickeado
ID del equipo a eliminar: 82
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025
Botón crear nuevo equipo clickeado (función habilitar1 en equipos.py)
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Función cargarDatos en equipos.py
Botón deshabilitar clickeado

Botón editar equipo clickeado (función habilitar2 en equipos.py)
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025

Función editarEquipo en equipos.py
Datos a editar
----------------------------------------------------------------------
Fila seleccionada: 1
ID del equipo seleccionado: 83
    - Datos del equipo recuperados: 
          ('Cámara de ionización', '9999', '0999', 0.199, None, '16/01/2026', 'DingleIndustries', 22, 101.325, 50, 300.0, 1.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 16/01/2026
Guardando cambios en el equipo...
ID del equipo a actualizar: 83
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

Botón editar equipo clickeado (función habilitar2 en equipos.py)

Botón deshabilitar clickeado

Botón editar equipo clickeado (función habilitar2 en equipos.py)
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025

Función editarEquipo en equipos.py
Datos a editar
----------------------------------------------------------------------
Fila seleccionada: 2
ID del equipo seleccionado: 84
    - Datos del equipo recuperados: 
          ('Cámara de ionización', '9999', '0999', 0.199, None, '06/01/2026', 'DingleIndustries', 22, 101.325, 50, 300.0, 1.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 06/01/2026
Guardando cambios en el equipo...
ID del equipo a actualizar: 84
Guardando cambios en el equipo...

Botón deshabilitar clickeado
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\respaldos_bd\BaseDatosQA_2026-08-04_142502.db
    Método open_main_window en la clase: DialogAdminPermiso
admin2025
    Método seleccionar_firma en la clase: VentanaFirma
    Método subir_firma en la clase: VentanaFirma
Usuario <data.ManejoDatos.user.Usuario object at 0x000001C76B941E10> agregado exitosamente.
    Método open_main_window en la clase: DialogAdminPermiso2
admin2025
Contraseña actualizada con éxito
Fdingle
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001C7BA088ED0>, id_f1_num usado: Felipe Parra Paez
Consulta de físicos exitosa: Nombre F1: ['Felipe Parra Paez']
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
Fecha Final COT: 2026-08-04 14:26:15-05:00
Horas transcurridas desde 2026-08-04 14:26:15: 1449.8308333333334
Dias transcurridos: 60.40961805555556
 La actividad es:  7.7414
super().__init__: 0.000s
dict_values(['luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta','interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla'])
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
iniGUI: 0.023s
load table: 0.092s
asignar_encabezados: 0.096s
button_click: 0.096s

Botón editar equipo clickeado (función habilitar2 en equipos.py)
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025

Función editarEquipo en equipos.py
Datos a editar
----------------------------------------------------------------------
Fila seleccionada: 3
ID del equipo seleccionado: 85
    - Datos del equipo recuperados: 
          ('Cámara de ionización', '9999', '0999', 0.199, None, '06/01/2025', 'DingleIndustries', 22, 101.325, 50, 300.0, 1.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 06/01/2025
Guardando cambios en el equipo...
ID del equipo a actualizar: 85

Botón deshabilitar clickeado
ID del equipo a eliminar: 86
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025

Botón editar equipo clickeado (función habilitar2 en equipos.py)
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001C7BA088ED0>, id_f1_num usado: Felipe Parra Paez
Consulta de físicos exitosa: Nombre F1: ['Felipe Parra Paez']
Físico 2 seleccionado: Cristian Castellanos, ID: 3
user_id_f2 antes de create_control: 3
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
<PyQt5.QtWidgets.QGridLayout object at 0x000001C7B9F11120>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C7B9F111B0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C7B9F11090>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C7B9F11000>
<PyQt5.QtWidgets.QGridLayout object at 0x000001C7B9F10F70>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
⚠️ Widgets MLC no encontrados - revisar creación desde Excel
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
Cociente fuera de rango (2.0 – 5.0)
300
Cociente fuera de rango (2.0 – 5.0)
300
could not convert string to float: ''
300
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
Data saved successfully for date: 04/08/2026
Dialog llamado desde: PruebaMensualIX
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
ANTES ADD: serie False
CREADO: serie
ANTES ADD: certificado False
CREADO: certificado
ANTES ADD: intensidad False
CREADO: intensidad
ANTES ADD: conversion False
CREADO: conversion
ANTES ADD: calibracion False
CREADO: calibracion
ANTES ADD: electrometro False
CREADO: electrometro
ANTES ADD: t0 False
CREADO: t0
ANTES ADD: p0 False
CREADO: p0
ANTES ADD: h0 False
CREADO: h0
ANTES ADD: t False
CREADO: t
ANTES ADD: p False
CREADO: p
ANTES ADD: h False
CREADO: h
ANTES ADD: ref False
CREADO: ref
ANTES ADD: observaciones False
CREADO: observaciones
['24', '05', '9498', '003', '060526', '13659', '19']
['060526']
Fechas normalizadas: 0
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
ANTES ADD: serie False
CREADO: serie
ANTES ADD: certificado False
CREADO: certificado
ANTES ADD: intensidad False
CREADO: intensidad
ANTES ADD: conversion False
CREADO: conversion
ANTES ADD: calibracion False
CREADO: calibracion
ANTES ADD: electrometro False
CREADO: electrometro
ANTES ADD: t0 False
CREADO: t0
ANTES ADD: p0 False
CREADO: p0
ANTES ADD: h0 False
CREADO: h0
ANTES ADD: t False
CREADO: t
ANTES ADD: p False
CREADO: p
ANTES ADD: h False
CREADO: h
ANTES ADD: ref False
CREADO: ref
ANTES ADD: observaciones False
CREADO: observaciones
['24', '05', '9498', '003', '060526', '13659', '19']
['060526']
Fechas normalizadas: 0
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
Linealidad             __init__ called
False
modelo False
serie_cp False
calibracion False
modelo_elec False
serie_ele False
electrometro False
repro_med1 False
repro_med2 False
repro_med3 False
repro_med4 False
repro_med5 False
repro_prom False
q_est False
t_integrado False
i_est False
exactitud False
repro False
tiempo_transito False
ANTES ADD: calibracion False
CREADO: calibracion
ANTES ADD: electrometro False
CREADO: electrometro
ANTES ADD: repro_med1 False
CREADO: repro_med1
ANTES ADD: repro_med2 False
CREADO: repro_med2
ANTES ADD: repro_med3 False
CREADO: repro_med3
ANTES ADD: repro_med4 False
CREADO: repro_med4
ANTES ADD: repro_med5 False
CREADO: repro_med5
ANTES ADD: repro_prom False
CREADO: repro_prom
ANTES ADD: q_est False
CREADO: q_est
ANTES ADD: t_integrado False
CREADO: t_integrado
ANTES ADD: i_est False
CREADO: i_est
ANTES ADD: exactitud False
CREADO: exactitud
ANTES ADD: repro False
CREADO: repro
ANTES ADD: tiempo_transito False
CREADO: tiempo_transito
2026-08-04
    - Entra a la condición de Braqui y Linealidad Braquiterapia, Otro = Linealidad Braquiterapia
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025
→ Eliminando en tabla TipoCalibracion, WHERE "id" = ?, valores [34]
UPDATE (anular) ejecutado correctamente
Fin de eliminarRegistro

Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-03\respaldos_bd\BaseDatosQA_2026-08-04_145033.db