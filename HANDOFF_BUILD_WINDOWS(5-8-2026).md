# Revision Rebuild windows 5 de Agosto de 2026

Anotaciones:
- Acabo de notar que al parecer no se guarda el valor de voltaje negativo, y parece que tampoco se carga/almacena el valor del TPR, ni el de humedad actual(no de referencia de calibracion), esto complica fuertemente las cosas, o no se carga, cuando uno carga un valor guardado para una energia de fotones, particularmente para 6MV en electrones. (No urgente, para despues, bloquear la edicion de estos datos cargados, depronto anadir un boton de limpiar y habilitar la edicion, pero que el boton inmediatamente lo saque a uno de ese registro como si apenas estuviera llenando uno nuevo porque la intencion es no modificar esos valores y mucho menos usar esa carga para llenar mas rapido un nuevo calculo.) La calculadora funciona perfectamente excepto por esas cosas. Esto sucede de la misma forma para electrones, solo que electrones como no muestra TPR pues por esto no carga este valor luego de cargar un guardado.
- En la tabla de calculadora_dosimetrica se esta guardando en el numero de serie el mismo id del equipo.
- No se puede anular un registro, abrir otro del mismo dia/mes/ano y subir cosas, saca una advertencia de que no se puede subir informacion a un registro anulado. Esto se vuelve un problema, querer subir un nuevo archivo sobre la misma fecha es posible? Habria entonces que bifurcarlo y que la diferencia en la tabla controles sea que uno esta activo y el otro no? Como esto afectaria la referenciacion en las tablas hijas o relacionadas, queda entonces un registro anulado bloqueando esa fecha para siempre? Se deben anular todos los resgistros relacionados a esta referencia(dosimetriaMen, calculadora_dosimetrica)? Si se anulan quedan invisibles en la app? Puede ser algo similar a equipos o alguna de las otras tablas en que solo pueden existir dos registros identicos excepto por la columna de activo... En realidad creo que lo mejor es que se pueda activar desde la app, con una pregunta en la misma ventana que da la advertencia de que no se puede cargar informacion sobre registros borrados, que se pregunte si se quiere activar nuevamente el registro de esa fecha y se pida autenticacion personal. Incluso cambiando el dia, mientras este en el mismo mes no se pueden subir registros para ese mes, entiendo porque pero que esperamos que suceda luego, dejar un registro muerto en ese mes por siempre, como si no hubiera pasado, simplemente debe existir la opcion de reactivarlo.
- Parece que el llenado de algunas tablas en los formularios se bloquea despues de la primera vez de darle subir.
- Se puede subir cualquier imagen en la parte de MLC anual del halcyon, esto no es como tal un problema, hay 2 botones uno casi que arriba del otro que ambos cargan la imagen... no urgente, se puede pulir despues.
- Quee pasa con el control diario de iX, nos lo tiramos??? Lo danamos? Que esta pasadno con el control diario, que hicimos, esto si es urgente.
- Limpiar datos en braqui no limpia tooodo, no es urgente, parece igual que todo se guarda bien.

- Expulsion de la terminal:
(Python_Personal) PS C:\Users\parra\Documents\AUNA_Codigos_2026> cd "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05"
(Python_Personal) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05> py -3.11 -m venv .venv
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05> 
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05> 
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05> .\.venv\Scripts\python.exe -m pip install --upgrade pip
Requirement already satisfied: pip in c:\users\parra\documents\auna_codigos_2026\codigo_radqa_2026-08-05\.venv\lib\site-packages (22.3)
Collecting pip
  Downloading pip-26.2.1-py3-none-any.whl (1.8 MB)
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.8/1.8 MB 820.0 kB/s eta 0:00:00
Installing collected packages: pip
  Attempting uninstall: pip
    Found existing installation: pip 22.3
    Uninstalling pip-22.3:
      Successfully uninstalled pip-22.3
Successfully installed pip-26.2.1
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05> .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Collecting PyMuPDF==1.28.0 (from -r requirements.txt (line 1))
  Using cached pymupdf-1.28.0-cp310-abi3-win_amd64.whl.metadata (26 kB)
Collecting matplotlib==3.10.7 (from -r requirements.txt (line 2))
  Using cached matplotlib-3.10.7-cp311-cp311-win_amd64.whl.metadata (11 kB)
Collecting numpy==2.3.4 (from -r requirements.txt (line 3))
  Using cached numpy-2.3.4-cp311-cp311-win_amd64.whl.metadata (60 kB)
Collecting opencv_python==4.11.0.86 (from -r requirements.txt (line 4))
  Using cached opencv_python-4.11.0.86-cp37-abi3-win_amd64.whl.metadata (20 kB)
Collecting pandas==2.3.3 (from -r requirements.txt (line 5))
  Using cached pandas-2.3.3-cp311-cp311-win_amd64.whl.metadata (19 kB)
Collecting Pillow==12.0.0 (from -r requirements.txt (line 6))
  Using cached pillow-12.0.0-cp311-cp311-win_amd64.whl.metadata (9.0 kB)
Collecting pyAesCrypt==6.1.1 (from -r requirements.txt (line 8))
  Using cached pyAesCrypt-6.1.1-py3-none-any.whl.metadata (5.2 kB)
Collecting keyboard==0.13.5 (from -r requirements.txt (line 9))
  Using cached keyboard-0.13.5-py3-none-any.whl.metadata (4.0 kB)
Collecting pywin32==312 (from -r requirements.txt (line 10))
  Using cached pywin32-312-cp311-cp311-win_amd64.whl.metadata (11 kB)
Collecting pydicom==2.4.4 (from -r requirements.txt (line 11))
  Using cached pydicom-2.4.4-py3-none-any.whl.metadata (7.8 kB)
Collecting pylinac==3.45.0 (from -r requirements.txt (line 12))
  Using cached pylinac-3.45.0-py3-none-any.whl.metadata (26 kB)
Collecting PyQt5==5.15.11 (from -r requirements.txt (line 13))
  Using cached PyQt5-5.15.11-cp38-abi3-win_amd64.whl.metadata (2.1 kB)
Collecting PyQt5_sip==12.17.0 (from -r requirements.txt (line 14))
  Using cached PyQt5_sip-12.17.0-cp311-cp311-win_amd64.whl.metadata (492 bytes)
Collecting pyqtgraph==0.13.7 (from -r requirements.txt (line 15))
  Using cached pyqtgraph-0.13.7-py3-none-any.whl.metadata (1.3 kB)
Collecting reportlab==4.4.2 (from -r requirements.txt (line 16))
  Using cached reportlab-4.4.2-py3-none-any.whl.metadata (1.8 kB)
Collecting scipy==1.16.3 (from -r requirements.txt (line 17))
  Using cached scipy-1.16.3-cp311-cp311-win_amd64.whl.metadata (60 kB)
Collecting openpyxl==3.1.5 (from -r requirements.txt (line 19))
  Using cached openpyxl-3.1.5-py2.py3-none-any.whl.metadata (2.5 kB)
Collecting xlrd==2.0.2 (from -r requirements.txt (line 25))
  Using cached xlrd-2.0.2-py2.py3-none-any.whl.metadata (3.5 kB)
Collecting msoffcrypto-tool==6.0.0 (from -r requirements.txt (line 26))
  Using cached msoffcrypto_tool-6.0.0-py3-none-any.whl.metadata (10 kB)
Collecting contourpy>=1.0.1 (from matplotlib==3.10.7->-r requirements.txt (line 2))
  Using cached contourpy-1.3.3-cp311-cp311-win_amd64.whl.metadata (5.5 kB)
Collecting cycler>=0.10 (from matplotlib==3.10.7->-r requirements.txt (line 2))
  Using cached cycler-0.12.1-py3-none-any.whl.metadata (3.8 kB)
Collecting fonttools>=4.22.0 (from matplotlib==3.10.7->-r requirements.txt (line 2))
  Using cached fonttools-4.63.0-cp311-cp311-win_amd64.whl.metadata (121 kB)
Collecting kiwisolver>=1.3.1 (from matplotlib==3.10.7->-r requirements.txt (line 2))
  Using cached kiwisolver-1.5.0-cp311-cp311-win_amd64.whl.metadata (5.2 kB)
Collecting packaging>=20.0 (from matplotlib==3.10.7->-r requirements.txt (line 2))
  Using cached packaging-26.3-py3-none-any.whl.metadata (3.5 kB)
Collecting pyparsing>=3 (from matplotlib==3.10.7->-r requirements.txt (line 2))
  Using cached pyparsing-3.3.2-py3-none-any.whl.metadata (5.8 kB)
Collecting python-dateutil>=2.7 (from matplotlib==3.10.7->-r requirements.txt (line 2))
  Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl.metadata (8.4 kB)
Collecting pytz>=2020.1 (from pandas==2.3.3->-r requirements.txt (line 5))
  Using cached pytz-2026.3.post1-py2.py3-none-any.whl.metadata (22 kB)
Collecting tzdata>=2022.7 (from pandas==2.3.3->-r requirements.txt (line 5))
  Using cached tzdata-2026.3-py2.py3-none-any.whl.metadata (1.4 kB)
Collecting cryptography (from pyAesCrypt==6.1.1->-r requirements.txt (line 8))
  Using cached cryptography-50.0.0-cp311-abi3-win_amd64.whl.metadata (4.3 kB)
Collecting argue~=0.3.1 (from pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached argue-0.3.1-py3-none-any.whl.metadata (452 bytes)
Collecting plotly>=5.0 (from pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached plotly-6.9.0-py3-none-any.whl.metadata (9.0 kB)
Collecting py-linq~=1.4.0 (from pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached py_linq-1.4.0-py3-none-any.whl.metadata (2.6 kB)
Collecting pydantic>=2.0 (from pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached pydantic-2.13.4-py3-none-any.whl.metadata (109 kB)
Collecting quaac (from pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached quaac-1.0.2-py3-none-any.whl.metadata (4.7 kB)
Collecting scikit-image>=0.18 (from pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached scikit_image-0.26.0-cp311-cp311-win_amd64.whl.metadata (15 kB)
Collecting tabulate~=0.9.0 (from pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached tabulate-0.9.0-py3-none-any.whl.metadata (34 kB)
Collecting tqdm>=3.8 (from pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached tqdm-4.70.0-py3-none-any.whl.metadata (57 kB)
Collecting typing-extensions>=4.14.1 (from pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached typing_extensions-4.16.0-py3-none-any.whl.metadata (3.3 kB)
Collecting PyQt5-Qt5<5.16.0,>=5.15.2 (from PyQt5==5.15.11->-r requirements.txt (line 13))
  Using cached PyQt5_Qt5-5.15.2-py3-none-win_amd64.whl.metadata (552 bytes)
Collecting charset-normalizer (from reportlab==4.4.2->-r requirements.txt (line 16))
  Using cached charset_normalizer-3.4.9-cp311-cp311-win_amd64.whl.metadata (42 kB)
Collecting et-xmlfile (from openpyxl==3.1.5->-r requirements.txt (line 19))
  Using cached et_xmlfile-2.0.0-py3-none-any.whl.metadata (2.7 kB)
Collecting olefile>=0.46 (from msoffcrypto-tool==6.0.0->-r requirements.txt (line 26))
  Using cached olefile-0.47-py2.py3-none-any.whl.metadata (9.7 kB)
Collecting future<0.19.0,>=0.18.2 (from py-linq~=1.4.0->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached future-0.18.3-py3-none-any.whl
Collecting six<2.0.0,>=1.16.0 (from py-linq~=1.4.0->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
Collecting cffi>=2.0.0 (from cryptography->pyAesCrypt==6.1.1->-r requirements.txt (line 8))
  Using cached cffi-2.1.1-cp311-cp311-win_amd64.whl.metadata (2.6 kB)
Collecting pycparser (from cffi>=2.0.0->cryptography->pyAesCrypt==6.1.1->-r requirements.txt (line 8))
  Using cached pycparser-3.0-py3-none-any.whl.metadata (8.2 kB)
Collecting narwhals>=1.15.1 (from plotly>=5.0->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached narwhals-2.24.0-py3-none-any.whl.metadata (15 kB)
Collecting annotated-types>=0.6.0 (from pydantic>=2.0->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached annotated_types-0.8.0-py3-none-any.whl.metadata (15 kB)
Collecting pydantic-core==2.46.4 (from pydantic>=2.0->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached pydantic_core-2.46.4-cp311-cp311-win_amd64.whl.metadata (6.7 kB)
Collecting typing-inspection>=0.4.2 (from pydantic>=2.0->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached typing_inspection-0.4.2-py3-none-any.whl.metadata (2.6 kB)
Collecting networkx>=3.0 (from scikit-image>=0.18->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached networkx-3.6.1-py3-none-any.whl.metadata (6.8 kB)
Collecting imageio!=2.35.0,>=2.33 (from scikit-image>=0.18->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached imageio-2.37.4-py3-none-any.whl.metadata (9.6 kB)
Collecting tifffile>=2022.8.12 (from scikit-image>=0.18->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached tifffile-2026.3.3-py3-none-any.whl.metadata (31 kB)
Collecting lazy-loader>=0.4 (from scikit-image>=0.18->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached lazy_loader-0.5-py3-none-any.whl.metadata (5.9 kB)
Collecting colorama (from tqdm>=3.8->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached colorama-0.4.6-py2.py3-none-any.whl.metadata (17 kB)
Collecting email-validator (from quaac->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached email_validator-2.3.0-py3-none-any.whl.metadata (26 kB)
Collecting pyyaml (from quaac->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached pyyaml-6.0.3-cp311-cp311-win_amd64.whl.metadata (2.4 kB)
Collecting dnspython>=2.0.0 (from email-validator->quaac->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached dnspython-2.8.0-py3-none-any.whl.metadata (5.7 kB)
Collecting idna>=2.0.0 (from email-validator->quaac->pylinac==3.45.0->-r requirements.txt (line 12))
  Using cached idna-3.18-py3-none-any.whl.metadata (6.1 kB)
Using cached pymupdf-1.28.0-cp310-abi3-win_amd64.whl (19.8 MB)
Using cached matplotlib-3.10.7-cp311-cp311-win_amd64.whl (8.1 MB)
Using cached numpy-2.3.4-cp311-cp311-win_amd64.whl (13.1 MB)
Using cached opencv_python-4.11.0.86-cp37-abi3-win_amd64.whl (39.5 MB)
Using cached pandas-2.3.3-cp311-cp311-win_amd64.whl (11.3 MB)
Using cached pillow-12.0.0-cp311-cp311-win_amd64.whl (7.0 MB)
Using cached pyAesCrypt-6.1.1-py3-none-any.whl (16 kB)
Using cached keyboard-0.13.5-py3-none-any.whl (58 kB)
Using cached pywin32-312-cp311-cp311-win_amd64.whl (6.9 MB)
Using cached pydicom-2.4.4-py3-none-any.whl (1.8 MB)
Using cached pylinac-3.45.0-py3-none-any.whl (423 kB)
Using cached PyQt5-5.15.11-cp38-abi3-win_amd64.whl (6.9 MB)
Using cached PyQt5_sip-12.17.0-cp311-cp311-win_amd64.whl (59 kB)
Using cached pyqtgraph-0.13.7-py3-none-any.whl (1.9 MB)
Using cached reportlab-4.4.2-py3-none-any.whl (2.0 MB)
Using cached scipy-1.16.3-cp311-cp311-win_amd64.whl (38.7 MB)
Using cached openpyxl-3.1.5-py2.py3-none-any.whl (250 kB)
Using cached xlrd-2.0.2-py2.py3-none-any.whl (96 kB)
Using cached msoffcrypto_tool-6.0.0-py3-none-any.whl (48 kB)
Using cached argue-0.3.1-py3-none-any.whl (3.6 kB)
Using cached py_linq-1.4.0-py3-none-any.whl (10 kB)
Using cached PyQt5_Qt5-5.15.2-py3-none-win_amd64.whl (50.1 MB)
Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
Using cached tabulate-0.9.0-py3-none-any.whl (35 kB)
Using cached contourpy-1.3.3-cp311-cp311-win_amd64.whl (225 kB)
Using cached cryptography-50.0.0-cp311-abi3-win_amd64.whl (3.8 MB)
Using cached cffi-2.1.1-cp311-cp311-win_amd64.whl (185 kB)
Using cached cycler-0.12.1-py3-none-any.whl (8.3 kB)
Using cached fonttools-4.63.0-cp311-cp311-win_amd64.whl (2.4 MB)
Using cached kiwisolver-1.5.0-cp311-cp311-win_amd64.whl (73 kB)
Using cached olefile-0.47-py2.py3-none-any.whl (114 kB)
Using cached packaging-26.3-py3-none-any.whl (129 kB)
Using cached plotly-6.9.0-py3-none-any.whl (9.9 MB)
Using cached narwhals-2.24.0-py3-none-any.whl (461 kB)
Using cached pydantic-2.13.4-py3-none-any.whl (472 kB)
Using cached pydantic_core-2.46.4-cp311-cp311-win_amd64.whl (2.1 MB)
Using cached annotated_types-0.8.0-py3-none-any.whl (13 kB)
Using cached pyparsing-3.3.2-py3-none-any.whl (122 kB)
Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl (229 kB)
Using cached pytz-2026.3.post1-py2.py3-none-any.whl (508 kB)
Using cached scikit_image-0.26.0-cp311-cp311-win_amd64.whl (11.9 MB)
Using cached imageio-2.37.4-py3-none-any.whl (318 kB)
Using cached lazy_loader-0.5-py3-none-any.whl (8.0 kB)
Using cached networkx-3.6.1-py3-none-any.whl (2.1 MB)
Using cached tifffile-2026.3.3-py3-none-any.whl (243 kB)
Using cached tqdm-4.70.0-py3-none-any.whl (80 kB)
Using cached typing_extensions-4.16.0-py3-none-any.whl (45 kB)
Using cached typing_inspection-0.4.2-py3-none-any.whl (14 kB)
Using cached tzdata-2026.3-py2.py3-none-any.whl (348 kB)
Using cached charset_normalizer-3.4.9-cp311-cp311-win_amd64.whl (161 kB)
Using cached colorama-0.4.6-py2.py3-none-any.whl (25 kB)
Using cached et_xmlfile-2.0.0-py3-none-any.whl (18 kB)
Using cached pycparser-3.0-py3-none-any.whl (48 kB)
Using cached quaac-1.0.2-py3-none-any.whl (9.3 kB)
Using cached email_validator-2.3.0-py3-none-any.whl (35 kB)
Using cached dnspython-2.8.0-py3-none-any.whl (331 kB)
Using cached idna-3.18-py3-none-any.whl (65 kB)
Using cached pyyaml-6.0.3-cp311-cp311-win_amd64.whl (158 kB)
Installing collected packages: pytz, PyQt5-Qt5, keyboard, argue, xlrd, tzdata, typing-extensions, tabulate, six, pyyaml, pywin32, PyQt5_sip, pyparsing, PyMuPDF, pydicom, pycparser, Pillow, packaging, olefile, numpy, networkx, narwhals, kiwisolver, idna, future, fonttools, et-xmlfile, dnspython, cycler, colorama, charset-normalizer, annotated-types, typing-inspection, tqdm, tifffile, scipy, reportlab, python-dateutil, pyqtgraph, PyQt5, pydantic-core, py-linq, plotly, openpyxl, opencv_python, lazy-loader, imageio, email-validator, contourpy, cffi, scikit-image, pydantic, pandas, matplotlib, cryptography, pyAesCrypt, msoffcrypto-tool, quaac, pylinac
Successfully installed Pillow-12.0.0 PyMuPDF-1.28.0 PyQt5-5.15.11 PyQt5-Qt5-5.15.2 PyQt5_sip-12.17.0 annotated-types-0.8.0 argue-0.3.1 cffi-2.1.1 charset-normalizer-3.4.9 colorama-0.4.6 contourpy-1.3.3 cryptography-50.0.0 cycler-0.12.1 dnspython-2.8.0 email-validator-2.3.0 et-xmlfile-2.0.0 fonttools-4.63.0 future-0.18.3 idna-3.18 imageio-2.37.4 keyboard-0.13.5 kiwisolver-1.5.0 lazy-loader-0.5 matplotlib-3.10.7 msoffcrypto-tool-6.0.0 narwhals-2.24.0 networkx-3.6.1 numpy-2.3.4 olefile-0.47 opencv_python-4.11.0.86 openpyxl-3.1.5 packaging-26.3 pandas-2.3.3 plotly-6.9.0 py-linq-1.4.0 pyAesCrypt-6.1.1 pycparser-3.0 pydantic-2.13.4 pydantic-core-2.46.4 pydicom-2.4.4 pylinac-3.45.0 pyparsing-3.3.2 pyqtgraph-0.13.7 python-dateutil-2.9.0.post0 pytz-2026.3.post1 pywin32-312 pyyaml-6.0.3 quaac-1.0.2 reportlab-4.4.2 scikit-image-0.26.0 scipy-1.16.3 six-1.17.0 tabulate-0.9.0 tifffile-2026.3.3 tqdm-4.70.0 typing-extensions-4.16.0 typing-inspection-0.4.2 tzdata-2026.3 xlrd-2.0.2
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05> .\.venv\Scripts\python.exe -m pip install pyinstaller==6.21.0
Collecting pyinstaller==6.21.0
  Using cached pyinstaller-6.21.0-py3-none-win_amd64.whl.metadata (8.5 kB)
Collecting altgraph (from pyinstaller==6.21.0)
  Using cached altgraph-0.17.5-py2.py3-none-any.whl.metadata (7.5 kB)
Requirement already satisfied: packaging>=22.0 in .\.venv\Lib\site-packages (from pyinstaller==6.21.0) (26.3)
Collecting pefile>=2022.5.30 (from pyinstaller==6.21.0)
  Using cached pefile-2024.8.26-py3-none-any.whl.metadata (1.4 kB)
Collecting pyinstaller-hooks-contrib>=2026.6 (from pyinstaller==6.21.0)
  Using cached pyinstaller_hooks_contrib-2026.6-py3-none-any.whl.metadata (16 kB)
Collecting pywin32-ctypes>=0.2.1 (from pyinstaller==6.21.0)
  Using cached pywin32_ctypes-0.2.3-py3-none-any.whl.metadata (3.9 kB)
Requirement already satisfied: setuptools>=42.0.0 in .\.venv\Lib\site-packages (from pyinstaller==6.21.0) (65.5.0)
Using cached pyinstaller-6.21.0-py3-none-win_amd64.whl (1.4 MB)
Using cached pefile-2024.8.26-py3-none-any.whl (74 kB)
Using cached pyinstaller_hooks_contrib-2026.6-py3-none-any.whl (457 kB)
Using cached pywin32_ctypes-0.2.3-py3-none-any.whl (30 kB)
Using cached altgraph-0.17.5-py2.py3-none-any.whl (21 kB)
Installing collected packages: altgraph, pywin32-ctypes, pyinstaller-hooks-contrib, pefile, pyinstaller
Successfully installed altgraph-0.17.5 pefile-2024.8.26 pyinstaller-6.21.0 pyinstaller-hooks-contrib-2026.6 pywin32-ctypes-0.2.3
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05> .venv\Scripts\python scripts\migrar_bd_a_estandar.py "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\BaseDatosQA.db" --aplicar --usuario FelipePP
Base de datos: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\BaseDatosQA.db
integrity_check antes: ok
Backup creado: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\BaseDatosQA.db.pre_migracion_20260805_100646.bak
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
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\respaldos_bd\pre_migracion\BaseDatosQA_2026-08-05_100647.db
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

--- Duplicados de controles (unicidad DP-06) ---
  Ningún duplicado por (equipo, control, mes/año) entre las filas activas.

Listo. Backup de seguridad conservado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\BaseDatosQA.db.pre_migracion_20260805_100646.bak

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05> python main.py
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
iniGUI: 0.024s
load table: 0.103s
asignar_encabezados: 0.107s
button_click: 0.107s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F7F83B7A10>, id_f1_num usado: Administrador
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
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8402ED510>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8402ED480>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8402ED630>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8402ED5A0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8402ED6C0>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
⚠️ Widgets MLC no encontrados - revisar creación desde Excel
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
Fila seleccionada: 22
ID del equipo seleccionado: 69
    - Datos del equipo recuperados: 
          ('Cámara de ionización', 'N31010', '1825', 0.3034, None, '05/02/2024', 'PTW', 22, 101.325, 50, 300.0, 0.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 05/02/2024
Guardando cambios en el equipo...
ID del equipo a actualizar: 69

Botón deshabilitar clickeado
Dialog llamado desde: PruebaMensualIX
300
300
300
Data saved successfully for date: 05/08/2026

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
Dialog llamado desde: PruebaMensualIX
300
300
300
Data saved successfully for date: 05/08/2026

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

Dialog llamado desde: PruebaMensualIX
300
Dialog llamado desde: PruebaMensualIX

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

Botón deshabilitar clickeado
Dialog llamado desde: PruebaMensualIX
300
300
300
Data saved successfully for date: 05/08/2026
Dialog llamado desde: PruebaMensualIX
300
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

asignar_encabezados: 0.093s
button_click: 0.093s
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\respaldos_bd\BaseDatosQA_2026-08-05_102330.db
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05> Get-FileHash -Algorithm MD5 .\BaseDatosQA.db

Algorithm       Hash                                                                   Path                                                        
---------       ----                                                                   ----                                                        
MD5             1AD523A2B61A7DD58EF53DA0D2B8A157                                       C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2...


(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05> python main.py
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
load table: 0.090s
asignar_encabezados: 0.093s
button_click: 0.094s
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
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\respaldos_bd\BaseDatosQA_2026-08-05_102706.db
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05> python main.py
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
iniGUI: 0.024s
load table: 0.103s
asignar_encabezados: 0.107s
button_click: 0.107s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F7F83B7A10>, id_f1_num usado: Administrador
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
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8402ED510>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8402ED480>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8402ED630>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8402ED5A0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8402ED6C0>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
⚠️ Widgets MLC no encontrados - revisar creación desde Excel
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
Fila seleccionada: 22
ID del equipo seleccionado: 69
    - Datos del equipo recuperados: 
          ('Cámara de ionización', 'N31010', '1825', 0.3034, None, '05/02/2024', 'PTW', 22, 101.325, 50, 300.0, 0.0, 'Imagen')
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
    - Equipo: Cámara de ionización, Unidades:  1 x 10⁹ Gy/C → (Gy/nC)
Ocultando el segundo factor de calibración.
Fecha de calibración cargada: 05/02/2024
Guardando cambios en el equipo...
ID del equipo a actualizar: 69

Botón deshabilitar clickeado
Dialog llamado desde: PruebaMensualIX
300
300
300
Data saved successfully for date: 05/08/2026

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
Dialog llamado desde: PruebaMensualIX
300
300
300
Data saved successfully for date: 05/08/2026

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

Dialog llamado desde: PruebaMensualIX
300
Dialog llamado desde: PruebaMensualIX

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

Botón deshabilitar clickeado
Dialog llamado desde: PruebaMensualIX
300
300
300
Data saved successfully for date: 05/08/2026
Dialog llamado desde: PruebaMensualIX
300
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

    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025
→ Eliminando en tabla controles, WHERE "id" = ?, valores [42]
UPDATE (anular) ejecutado correctamente
Fin de eliminarRegistro


Entra a subirlineasmensuales_ix de la clase PruebaMensualIX
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\respaldos_bd\BaseDatosQA_2026-08-05_112134.db
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
iniGUI: 0.018s
load table: 0.193s
asignar_encabezados: 0.197s
button_click: 0.197s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F80051D350>, id_f1_num usado: Administrador
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
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8005C9120>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8005C8040>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8005CB2E0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F80052EB90>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F80052FF40>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
⚠️ Widgets MLC no encontrados - revisar creación desde Excel

Entra a subirlineasmensuales_ix de la clase PruebaMensualIX
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F80051D350>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
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
Fecha Final COT: 2026-08-05 11:27:59-05:00
Horas transcurridas desde 2026-08-05 11:27:59: 1470.8597222222222
Dias transcurridos: 61.28582175925926
 La actividad es:  7.678

Entra a subirlineasmensuales_ix de la clase PruebaMensualIX
Entra a la función add_info en load.py con tabla: aceleradorlineal_600
Manteniendo columna ID

▥ Columnas detectadas: ['date', 'user_id', 'luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla', 'laseres', 'telemetro', 'tamano_campo', 'centrado_reticulo', 'dosis_referencia', 'observaciones'] para aceleradorlineal_600

Clinac 600
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F80051D350>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
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
<PyQt5.QtWidgets.QGridLayout object at 0x000001F83BEFBBE0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F83BEFBF40>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F83BEFBD90>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F83BEFBEB0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F83BEFBE20>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
DF LINES: 
['val_teo_6mv', 'ln_dosis_ref_cgy_um_6mv', 'ln_discrepancia_dosis_6mv', 'ln_tolerancia_dosis', 'ln_calidad_pdd20_10_6mv', 'ln_discrepancia_calidad_6mv', 'ln_tolerancia_calidad', 'ln_simetria_inplane_6mv', 'ln_simetria_crossplane_6mv', 'ln_tolerancia_simetria', 'ln_planicidad_inplane_6mv', 'ln_planicidad_crossplane_6mv', 'ln_tolerancia_planicidad', 'ln_observaciones_dosi']
Widget 'ln_dosis_ref_cgy_um_15mv' no encontrado
Widget 'ln_dosis_ref_cgy_um_6mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_9mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_12mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_15mev' no encontrado
Insertados 3 registros de equipos correctamente
Actualizando tabla de controles mensuales para Clinac 600
Actualizando tabla de controles mensuales para Clinac 600

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
<PyQt5.QtWidgets.QGridLayout object at 0x000001F845F62830>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F845F627A0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F845F628C0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F845F62950>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F845F629E0>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
⚠️ Widgets MLC no encontrados - revisar creación desde Excel
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\respaldos_bd\BaseDatosQA_2026-08-05_114025.db
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
iniGUI: 0.023s
Recursos limpiados correctamente
load table: 0.211s
asignar_encabezados: 0.214s
button_click: 0.215s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F7FD3E19D0>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
Error: 'QComboBox' object has no attribute 'setText'
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
<PyQt5.QtWidgets.QGridLayout object at 0x000001F840452B00>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8404528C0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F840452C20>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F8404509D0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F840451D80>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
⚠️ Widgets MLC no encontrados - revisar creación desde Excel

Entra a subirlineasmensuales_ix de la clase PruebaMensualIX
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\respaldos_bd\BaseDatosQA_2026-08-05_114412.db
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
iniGUI: 0.028s
load table: 0.107s
asignar_encabezados: 0.111s
button_click: 0.112s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F7FFC40690>, id_f1_num usado: Administrador
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
<PyQt5.QtWidgets.QGridLayout object at 0x000001F83BE40430>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F83BE404C0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F83BE403A0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F83BE40310>
<PyQt5.QtWidgets.QGridLayout object at 0x000001F83BE40280>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
⚠️ Widgets MLC no encontrados - revisar creación desde Excel

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000001F83BE3DA20>
Texto actual en observaciones_segu: 'SSSSS'
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

Se presionó btn_guardar_ix

 regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]

✓  Módulos detectados: ['CTP404', 'CTP486', 'CTP515', 'CTP528']
   CTP404     → corte   75
   CTP486     → corte   43
   CTP515     → corte   60
   CTP528     → corte   90
mapeoooooooooooooooooooooooo
ln_espesor
ln_contrast_res
ln_resolucion_esp
ln_uni
{'CTP404': 74, 'CTP486': 42, 'CTP515': 59, 'CTP528': 89}
VISUALIZADOR QUE EMITE: 2164725624560
espesor

✓  Módulos detectados: ['CTP404', 'CTP486', 'CTP515', 'CTP528']
   CTP404     → corte   75
   CTP486     → corte   43
   CTP515     → corte   60
   CTP528     → corte   90
mapeoooooooooooooooooooooooo
ln_espesor
ln_contrast_res
ln_resolucion_esp
ln_uni
{'CTP404': 74, 'CTP486': 42, 'CTP515': 59, 'CTP528': 89}
VISUALIZADOR QUE EMITE: 2164725624560
espesor
Clinac 600
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F7FFC40690>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
Cargando widgets desde hoja: preguntas_anual_600
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
  - DataFrame: 22 filas
Insertados 3 registros de equipos correctamente
Actualizando tabla de controles anuales para Clinac 600
Actualizando tabla de controles anuales para Clinac 600

C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]

✓  Módulos detectados: ['CTP404', 'CTP486', 'CTP515', 'CTP528']
   CTP404     → corte   75
   CTP486     → corte   43
   CTP515     → corte   60
   CTP528     → corte   90
mapeoooooooooooooooooooooooo
ln_espesor
ln_contrast_res
ln_resolucion_esp
ln_uni
{'CTP404': 74, 'CTP486': 42, 'CTP515': 59, 'CTP528': 89}
VISUALIZADOR QUE EMITE: 2164725624560
espesor
Clinac 600
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F7FFC40690>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
Cargando widgets desde hoja: preguntas_anual_600
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
  - DataFrame: 22 filas
Insertados 3 registros de equipos correctamente
Actualizando tabla de controles anuales para Clinac 600
Actualizando tabla de controles anuales para Clinac 600
Subiendo tabla tabla_control_camaras_monitoras normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicador_medir', 'valor_medido'] para tabla_control_camaras_monitoras

Anual con energia para la tabla tabla_control_camaras_monitoras, id = True
Anual con energia para la tabla tabla_control_camaras_monitoras, id = True
Anual con energia para la tabla tabla_control_camaras_monitoras, id = True
Anual con energia para la tabla tabla_control_camaras_monitoras, id = True
Anual con energia para la tabla tabla_control_camaras_monitoras, id = True
Anual con energia para la tabla tabla_control_camaras_monitoras, id = True
Anual con energia para la tabla tabla_control_camaras_monitoras, id = True

▥ Datos a insertar en tabla_control_camaras_monitoras:
  - [46, 0, 'Fac. Calibración', '']
  - [46, 0, 'Reproducibilidad', '']
  - [46, 0, 'Linealidad R2', '']
  - [46, 0, 'Tasa mínima 80 cGy/min', '']
  - [46, 0, 'Tasa intermedia 160 cGy/min', '']
  - [46, 0, 'Tasa máxima 400 cGy/min', '']
  - [46, 0, 'Desviación estándar', '']
Actualizando tabla de controles anuales para Clinac 600
Tabla(s) tabla_control_camaras_monitoras subida(s) correctamente
Insertados 3 registros de equipos correctamente
Actualizando tabla de controles anuales para Clinac 600
Actualizando tabla de controles anuales para Clinac 600
Halcyon
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F7FFC40690>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
Físico 2 seleccionado: Cristian Castellanos, ID: 3
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
Analisis de imagen activado en subir_imagen en PruebasDiarias.py
analizando imagen
Subir imagen activado en imagenUpLoader en PruebasDiarias.py
Aceptar imagen activado en PruebasDiarias.py
Aceptar imagen activado en PruebasDiarias.py
Subiendo tabla HC_linealidad_unidades_monitor_anual normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'UM', 'Q1', 'Q2', 'Qprom'] para HC_linealidad_unidades_monitor_anual

Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True
Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True
Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True
Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True
Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True
Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True
Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True
Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True

▥ Datos a insertar en HC_linealidad_unidades_monitor_anual:
  - [47, 0, '50', '', '', '']
  - [47, 0, '100', '', '', '']
  - [47, 0, '150', '', '', '']
  - [47, 0, '200', '', '', '']
  - [47, 0, '250', '', '', '']
  - [47, 0, '300', '', '', '']
  - [47, 0, '350', '', '', '']
  - [47, 0, '400', '', '', '']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_linealidad_unidades_monitor_anual subida(s) correctamente

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
Datos guardados correctamente.
Actualizando tabla de controles anuales para Halcyon
Datos subidos correctamente
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F7FFC40690>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
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
Imagen y perfil del MLC subidos exitosamente a la base de datos.
Imagen y perfil del MLC subidos exitosamente a la base de datos.
Limpiando data
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\respaldos_bd\BaseDatosQA_2026-08-05_121425.db
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
iniGUI: 0.027s
load table: 0.096s
asignar_encabezados: 0.102s
button_click: 0.102s
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F800041090>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
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
Recursos limpiados correctamente
Recursos limpiados correctamente
Botón subir sin datos
13.65
Fecha Inicio CET: 2026-06-05 11:36:24+02:00 (Fecha del certificado)
Fecha Inicio convertido a COT: 2026-06-05 04:36:24-05:00
Fecha Final COT: 2026-08-05 12:15:32-05:00
Horas transcurridas desde 2026-08-05 12:15:32: 1471.6522222222222
Dias transcurridos: 61.318842592592596
 La actividad es:  7.6756
Error calculando discrepancias: wrapped C/C++ object of type QTableWidget has been deleted
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\ui\paginasControles\PruebasAnuales\seiscientos_anual.py", line 366, in calcular
    for fila in range(0, tabla.rowCount()):
                         ^^^^^^^^^^^^^^^^
RuntimeError: wrapped C/C++ object of type QTableWidget has been deleted

C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:419: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  regionprops, key=lambda x: np.abs(x.filled_area - self.catphan_size)
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:421: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_large = self.catphan_size * 1.3 < catphan_region.filled_area
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:422: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  is_too_small = catphan_region.filled_area < self.catphan_size / 1.3
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:2517: FutureWarning: `RegionProperties.filled_area` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.area_filled` instead. 
  return thresh * 2 > region.filled_area > thresh / 2
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\.venv\Lib\site-packages\pylinac\ct.py:831: FutureWarning: `RegionProperties.weighted_centroid` is deprecated starting in version 0.26 and will be removed in version 2.0. Use `RegionProperties.centroid_weighted` instead. 
  r.weighted_centroid[1] + xbounds[0], r.weighted_centroid[0] + ybounds[0]

✓  Módulos detectados: ['CTP404', 'CTP486', 'CTP515', 'CTP528']
   CTP404     → corte   75
   CTP486     → corte   43
   CTP515     → corte   60
   CTP528     → corte   90
mapeoooooooooooooooooooooooo
ln_espesor
ln_contrast_res
ln_resolucion_esp
ln_uni
{'CTP404': 74, 'CTP486': 42, 'CTP515': 59, 'CTP528': 89}
VISUALIZADOR QUE EMITE: 2164725624560
espesor
Clinac 600
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F7FFC40690>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
Cargando widgets desde hoja: preguntas_anual_600
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
  - DataFrame: 22 filas
Insertados 3 registros de equipos correctamente
Actualizando tabla de controles anuales para Clinac 600
Actualizando tabla de controles anuales para Clinac 600
Subiendo tabla tabla_control_camaras_monitoras normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'indicador_medir', 'valor_medido'] para tabla_control_camaras_monitoras

Anual con energia para la tabla tabla_control_camaras_monitoras, id = True
Anual con energia para la tabla tabla_control_camaras_monitoras, id = True
Anual con energia para la tabla tabla_control_camaras_monitoras, id = True
Anual con energia para la tabla tabla_control_camaras_monitoras, id = True
Anual con energia para la tabla tabla_control_camaras_monitoras, id = True
Anual con energia para la tabla tabla_control_camaras_monitoras, id = True
Anual con energia para la tabla tabla_control_camaras_monitoras, id = True

▥ Datos a insertar en tabla_control_camaras_monitoras:
  - [46, 0, 'Fac. Calibración', '']
  - [46, 0, 'Reproducibilidad', '']
  - [46, 0, 'Linealidad R2', '']
  - [46, 0, 'Tasa mínima 80 cGy/min', '']
  - [46, 0, 'Tasa intermedia 160 cGy/min', '']
  - [46, 0, 'Tasa máxima 400 cGy/min', '']
  - [46, 0, 'Desviación estándar', '']
Actualizando tabla de controles anuales para Clinac 600
Tabla(s) tabla_control_camaras_monitoras subida(s) correctamente
Insertados 3 registros de equipos correctamente
Actualizando tabla de controles anuales para Clinac 600
Actualizando tabla de controles anuales para Clinac 600
Halcyon
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F7FFC40690>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
Físico 2 seleccionado: Cristian Castellanos, ID: 3
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
Analisis de imagen activado en subir_imagen en PruebasDiarias.py
analizando imagen
Subir imagen activado en imagenUpLoader en PruebasDiarias.py
Aceptar imagen activado en PruebasDiarias.py
Aceptar imagen activado en PruebasDiarias.py
Subiendo tabla HC_linealidad_unidades_monitor_anual normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'UM', 'Q1', 'Q2', 'Qprom'] para HC_linealidad_unidades_monitor_anual

Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True
Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True
Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True
Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True
Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True
Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True
Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True
Anual con energia para la tabla HC_linealidad_unidades_monitor_anual, id = True

▥ Datos a insertar en HC_linealidad_unidades_monitor_anual:
  - [47, 0, '50', '', '', '']
  - [47, 0, '100', '', '', '']
  - [47, 0, '150', '', '', '']
  - [47, 0, '200', '', '', '']
  - [47, 0, '250', '', '', '']
  - [47, 0, '300', '', '', '']
  - [47, 0, '350', '', '', '']
  - [47, 0, '400', '', '', '']
Actualizando tabla de controles anuales para Halcyon
Tabla(s) HC_linealidad_unidades_monitor_anual subida(s) correctamente

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
Datos guardados correctamente.
Actualizando tabla de controles anuales para Halcyon
Datos subidos correctamente
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F7FFC40690>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
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
Imagen y perfil del MLC subidos exitosamente a la base de datos.
Imagen y perfil del MLC subidos exitosamente a la base de datos.
Limpiando data
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\respaldos_bd\BaseDatosQA_2026-08-05_121425.db
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
iniGUI: 0.027s
load table: 0.096s
asignar_encabezados: 0.102s
button_click: 0.102s
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001F800041090>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
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
Recursos limpiados correctamente
Recursos limpiados correctamente
Botón subir sin datos
13.65
Fecha Inicio CET: 2026-06-05 11:36:24+02:00 (Fecha del certificado)
Fecha Inicio convertido a COT: 2026-06-05 04:36:24-05:00
Fecha Final COT: 2026-08-05 12:15:32-05:00
Horas transcurridas desde 2026-08-05 12:15:32: 1471.6522222222222
Dias transcurridos: 61.318842592592596
 La actividad es:  7.6756
Error calculando discrepancias: wrapped C/C++ object of type QTableWidget has been deleted
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\ui\paginasControles\PruebasAnuales\seiscientos_anual.py", line 366, in calcular
    for fila in range(0, tabla.rowCount()):
                         ^^^^^^^^^^^^^^^^
RuntimeError: wrapped C/C++ object of type QTableWidget has been deleted
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
Voltaje alto, nA prom: 8.0
Voltaje bajo, nA prom: 14.0
Actividad fuente: 63543553.49639677
Ks: 1.1428571428571428 
Ktp: 108.57142857142857 
calibracion camara: 466700.0 
calibracion electrometro: 1.0 
KPol: 0.558252427184466 
Conversion: 0.11
Fecha Inicio CET: 2026-06-05 11:36:24+02:00 (Fecha del certificado)
Fecha Inicio convertido a COT: 2026-06-05 04:36:24-05:00
Fecha Final COT: 2026-08-05 12:18:47-05:00
Horas transcurridas desde 2026-08-05 12:18:47: 1471.7063888888888
Dias transcurridos: 61.321099537037036
    - Entra a la condición de Braqui y Mensual Braquiterapia, Otro = Mensual Braquiterapia
Entra a guardar_DB en PruebaMensualBraq
Cambio de fuente
Actividad fuente: 63522509.36402124
Ks: 1.143 
Ktp: 108.571 
calibracion camara: 466700.0 
calibracion electrometro: 1.0 
KPol: 0.558 
Conversion: 0.11
Fecha Inicio CET: 2026-06-05 11:36:24+02:00 (Fecha del certificado)
Fecha Inicio convertido a COT: 2026-06-05 04:36:24-05:00
Fecha Final COT: 2026-08-05 12:18:47-05:00
Horas transcurridas desde 2026-08-05 12:18:47: 1471.7063888888888
Dias transcurridos: 61.321099537037036
Desplazamiento a guardar: None
2026-08-05 12:18:47
Limpiando data
['']
[]
list index out of range
Limpiando data

ANTES ADD: line_1_exp_act_ci False
CREADO: line_1_exp_act_ci
ANTES ADD: line_1_cyc_dummy False
CREADO: line_1_cyc_dummy
ANTES ADD: line_1_cyc_rad False
CREADO: line_1_cyc_rad
ANTES ADD: observaciones False
CREADO: observaciones
Voltaje alto, nA prom: 8.0
Voltaje bajo, nA prom: 14.0
Actividad fuente: 63543553.49639677
Ks: 1.1428571428571428 
Ktp: 108.57142857142857 
calibracion camara: 466700.0 
calibracion electrometro: 1.0 
KPol: 0.558252427184466 
Conversion: 0.11
Fecha Inicio CET: 2026-06-05 11:36:24+02:00 (Fecha del certificado)
Fecha Inicio convertido a COT: 2026-06-05 04:36:24-05:00
Fecha Final COT: 2026-08-05 12:18:47-05:00
Horas transcurridas desde 2026-08-05 12:18:47: 1471.7063888888888
Dias transcurridos: 61.321099537037036
    - Entra a la condición de Braqui y Mensual Braquiterapia, Otro = Mensual Braquiterapia
Entra a guardar_DB en PruebaMensualBraq
Cambio de fuente
Actividad fuente: 63522509.36402124
Ks: 1.143 
Ktp: 108.571 
calibracion camara: 466700.0 
calibracion electrometro: 1.0 
KPol: 0.558 
Conversion: 0.11
Fecha Inicio CET: 2026-06-05 11:36:24+02:00 (Fecha del certificado)
Fecha Inicio convertido a COT: 2026-06-05 04:36:24-05:00
Fecha Final COT: 2026-08-05 12:18:47-05:00
Horas transcurridas desde 2026-08-05 12:18:47: 1471.7063888888888
Dias transcurridos: 61.321099537037036
Desplazamiento a guardar: None
2026-08-05 12:18:47
Limpiando data
['']
[]
list index out of range
Limpiando data
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
2026-08-05
    - Entra a la condición de Braqui y Linealidad Braquiterapia, Otro = Linealidad Braquiterapia
C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-05\ui\paginasControles\PruebasDiarias\braquiterapia.py:2497: RuntimeWarning: divide by zero encountered in scalar divide
  self.r2 = 1 - (ss_res / ss_tot)