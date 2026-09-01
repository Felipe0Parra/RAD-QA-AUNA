# Rebuild de Windows 19 de Agosot de 2026

- Expulsion de la terminal instalacion de paquetes:

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19> .\.venv\Scripts\python.exe -m pip install --upgrade pip
Requirement already satisfied: pip in c:\users\parra\documents\auna_codigos_2026\codigo_radqa_2026-08-19\.venv\lib\site-packages (22.3)
Collecting pip
  Using cached pip-26.2.1-py3-none-any.whl (1.8 MB)
Installing collected packages: pip
  Attempting uninstall: pip
    Found existing installation: pip 22.3
    Uninstalling pip-22.3:
      Successfully uninstalled pip-22.3
Successfully installed pip-26.2.1
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19> .\.venv\Scripts\python.exe -m pip install -r requirements.txt
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
  Using cached charset_normalizer-3.5.1-cp311-cp311-win_amd64.whl.metadata (46 kB)
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
  Using cached typing_inspection-0.4.4-py3-none-any.whl.metadata (2.6 kB)
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
  Using cached idna-3.19-py3-none-any.whl.metadata (9.2 kB)
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
Using cached typing_inspection-0.4.4-py3-none-any.whl (14 kB)
Using cached tzdata-2026.3-py2.py3-none-any.whl (348 kB)
Using cached charset_normalizer-3.5.1-cp311-cp311-win_amd64.whl (206 kB)
Using cached colorama-0.4.6-py2.py3-none-any.whl (25 kB)
Using cached et_xmlfile-2.0.0-py3-none-any.whl (18 kB)
Using cached pycparser-3.0-py3-none-any.whl (48 kB)
Using cached quaac-1.0.2-py3-none-any.whl (9.3 kB)
Using cached email_validator-2.3.0-py3-none-any.whl (35 kB)
Using cached dnspython-2.8.0-py3-none-any.whl (331 kB)
Using cached idna-3.19-py3-none-any.whl (68 kB)
Using cached pyyaml-6.0.3-cp311-cp311-win_amd64.whl (158 kB)
Installing collected packages: pytz, PyQt5-Qt5, keyboard, argue, xlrd, tzdata, typing-extensions, tabulate, six, pyyaml, pywin32, PyQt5_sip, pyparsing, PyMuPDF, pydicom, pycparser, Pillow, packaging, olefile, numpy, networkx, narwhals, kiwisolver, idna, future, fonttools, et-xmlfile, dnspython, cycler, colorama, charset-normalizer, annotated-types, typing-inspection, tqdm, tifffile, scipy, reportlab, python-dateutil, pyqtgraph, PyQt5, pydantic-core, py-linq, plotly, openpyxl, opencv_python, lazy-loader, imageio, email-validator, contourpy, cffi, scikit-image, pydantic, pandas, matplotlib, cryptography, pyAesCrypt, msoffcrypto-tool, quaac, pylinac
Successfully installed Pillow-12.0.0 PyMuPDF-1.28.0 PyQt5-5.15.11 PyQt5-Qt5-5.15.2 PyQt5_sip-12.17.0 annotated-types-0.8.0 argue-0.3.1 cffi-2.1.1 charset-normalizer-3.5.1 colorama-0.4.6 contourpy-1.3.3 cryptography-50.0.0 cycler-0.12.1 dnspython-2.8.0 email-validator-2.3.0 et-xmlfile-2.0.0 fonttools-4.63.0 future-0.18.3 idna-3.19 imageio-2.37.4 keyboard-0.13.5 kiwisolver-1.5.0 lazy-loader-0.5 matplotlib-3.10.7 msoffcrypto-tool-6.0.0 narwhals-2.24.0 networkx-3.6.1 numpy-2.3.4 olefile-0.47 opencv_python-4.11.0.86 openpyxl-3.1.5 packaging-26.3 pandas-2.3.3 plotly-6.9.0 py-linq-1.4.0 pyAesCrypt-6.1.1 pycparser-3.0 pydantic-2.13.4 pydantic-core-2.46.4 pydicom-2.4.4 pylinac-3.45.0 pyparsing-3.3.2 pyqtgraph-0.13.7 python-dateutil-2.9.0.post0 pytz-2026.3.post1 pywin32-312 pyyaml-6.0.3 quaac-1.0.2 reportlab-4.4.2 scikit-image-0.26.0 scipy-1.16.3 six-1.17.0 tabulate-0.9.0 tifffile-2026.3.3 tqdm-4.70.0 typing-extensions-4.16.0 typing-inspection-0.4.4 tzdata-2026.3 xlrd-2.0.2

- Expulsion de la terminal para la construccion del .exe:

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19> .\.venv\Scripts\python.exe build_exe.py
92 INFO: PyInstaller: 6.21.0, contrib hooks: 2026.6
92 INFO: Python: 3.11.0
105 INFO: Platform: Windows-10-10.0.26200-SP0
105 INFO: Python environment: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\.venv
105 INFO: wrote C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\RAD-QA.spec
107 INFO: Removing temporary files and cleaning cache in C:\Users\parra\AppData\Local\pyinstaller
6424 INFO: Module search paths (PYTHONPATH):
['C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311\\python311.zip',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311\\DLLs',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311\\Lib',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\win32',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\win32\\lib',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\pythonwin',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19']
6687 INFO: Appending 'datas' from .spec
6695 INFO: checking Analysis
6695 INFO: Building Analysis because Analysis-00.toc is non existent
6695 INFO: Looking for Python shared library...
6695 INFO: Using Python shared library: C:\Users\parra\AppData\Local\Programs\Python\Python311\python311.dll
6695 INFO: Running Analysis Analysis-00.toc
6695 INFO: Target bytecode optimization level: 0
6695 INFO: Initializing module dependency graph...
6697 INFO: Initializing module graph hook caches...
6721 INFO: Analyzing modules for base_library.zip ...
7446 INFO: Processing standard module hook 'hook-heapq.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
7568 INFO: Processing standard module hook 'hook-encodings.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
8945 INFO: Processing standard module hook 'hook-math.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
9109 INFO: Processing standard module hook 'hook-pickle.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
11364 INFO: Caching module dependency graph...
11389 INFO: Analyzing C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\main.py
11404 INFO: Processing standard module hook 'hook-PyQt5.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
11871 INFO: Processing standard module hook 'hook-PyQt5.QtWidgets.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
13133 INFO: Processing standard module hook 'hook-PyQt5.QtCore.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
14716 INFO: Processing standard module hook 'hook-PyQt5.QtGui.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
21649 INFO: Processing standard module hook 'hook-sqlite3.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
21873 INFO: Processing standard module hook 'hook-cryptography.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
22531 INFO: hook-cryptography: cryptography does not seem to be using dynamically linked OpenSSL.
22651 INFO: Processing standard module hook 'hook-numpy.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
22956 INFO: Processing standard module hook 'hook-difflib.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
23209 INFO: Processing standard module hook 'hook-multiprocessing.util.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
23395 INFO: Processing standard module hook 'hook-xml.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
23689 INFO: Processing standard module hook 'hook-_ctypes.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
24353 INFO: Processing standard module hook 'hook-sysconfig.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
24433 INFO: Processing standard module hook 'hook-platform.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
24904 INFO: Processing standard module hook 'hook-webbrowser.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
25413 INFO: Processing pre-safe-import-module hook 'hook-typing_extensions.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
25415 INFO: SetuptoolsInfo: initializing cached setuptools info...
26119 INFO: Processing standard module hook 'hook-charset_normalizer.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
26354 INFO: Processing standard module hook 'hook-PyQt5.QtSql.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
26783 INFO: Processing standard module hook 'hook-pandas.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
28352 INFO: Processing standard module hook 'hook-pytz.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
28595 INFO: Processing standard module hook 'hook-scipy.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
29026 INFO: Processing standard module hook 'hook-pycparser.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
29108 INFO: Processing standard module hook 'hook-setuptools.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
29113 INFO: Processing pre-safe-import-module hook 'hook-distutils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
29113 INFO: Processing pre-find-module-path hook 'hook-distutils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_find_module_path'
29526 INFO: Processing standard module hook 'hook-distutils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
29594 INFO: Processing standard module hook 'hook-distutils.util.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
29677 INFO: Processing standard module hook 'hook-_osx_support.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
29887 INFO: Processing standard module hook 'hook-pkg_resources.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
30590 INFO: Processing pre-safe-import-module hook 'hook-importlib_metadata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
30644 INFO: Processing pre-safe-import-module hook 'hook-packaging.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
31497 INFO: Processing standard module hook 'hook-scipy.linalg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
31609 INFO: Processing standard module hook 'hook-scipy.special._ufuncs.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
32179 INFO: Processing standard module hook 'hook-scipy.spatial._ckdtree.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
32233 INFO: Processing standard module hook 'hook-matplotlib.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
32520 INFO: Processing pre-safe-import-module hook 'hook-gi.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
32683 INFO: Processing standard module hook 'hook-matplotlib.backend_bases.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
32753 INFO: Processing standard module hook 'hook-PIL.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
32861 INFO: Processing standard module hook 'hook-PIL.Image.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
33128 INFO: Processing standard module hook 'hook-xml.etree.cElementTree.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
33278 INFO: Processing standard module hook 'hook-PIL.ImageFilter.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
33677 INFO: Processing standard module hook 'hook-matplotlib.backends.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
33714 INFO: Processing standard module hook 'hook-matplotlib.pyplot.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
34335 INFO: Processing standard module hook 'hook-dateutil.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
34372 INFO: Processing pre-safe-import-module hook 'hook-six.moves.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
35346 INFO: Processing standard module hook 'hook-scipy.spatial.transform.rotation.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
36061 INFO: Processing standard module hook 'hook-scipy.stats._stats.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
36352 INFO: Processing standard module hook 'hook-scipy.sparse.csgraph.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
36910 INFO: Processing standard module hook 'hook-scipy.special._ellip_harm_2.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
38371 INFO: Processing standard module hook 'hook-pandas.io.formats.style.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
39621 INFO: Processing standard module hook 'hook-pandas.plotting.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
39986 INFO: Processing standard module hook 'hook-openpyxl.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
40900 INFO: Processing standard module hook 'hook-pandas.io.clipboard.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
41227 INFO: Processing standard module hook 'hook-xml.dom.domreg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
41750 INFO: Processing standard module hook 'hook-reportlab.lib.utils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
41843 INFO: Processing standard module hook 'hook-reportlab.pdfbase._fontdata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
43086 INFO: Processing standard module hook 'hook-pydicom.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
43677 INFO: Processing pre-safe-import-module hook 'hook-importlib_resources.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
47362 INFO: Processing standard module hook 'hook-pyqtgraph.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
269 WARNING: Failed to collect submodules for 'pyqtgraph.opengl' because importing 'pyqtgraph.opengl' raised: ModuleNotFoundError: No module named 'OpenGL'
47984 INFO: hook-pyqtgraph: selected 'PyQt5' as Qt bindings because hook for 'PyQt5' has been run before.
48002 INFO: Processing standard module hook 'hook-PyQt5.uic.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
48129 INFO: Processing pre-find-module-path hook 'hook-PyQt5.uic.port_v2.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_find_module_path'
48176 INFO: Processing standard module hook 'hook-PyQt5.QtSvg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
49009 INFO: Processing standard module hook 'hook-PyQt5.QtTest.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
50292 INFO: Processing standard module hook 'hook-matplotlib.backends.backend_qtagg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
50295 INFO: Processing standard module hook 'hook-matplotlib.backends.qt_compat.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
50295 INFO: hook-matplotlib.backends.qt_compat: selected 'PyQt5' as Qt bindings because hook for 'PyQt5' has been run before.
50907 INFO: Processing standard module hook 'hook-plotly.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
51769 INFO: Processing standard module hook 'hook-narwhals.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
55316 INFO: Processing standard module hook 'hook-skimage.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
55367 INFO: Processing standard module hook 'hook-skimage.measure.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
56209 INFO: Processing standard module hook 'hook-pydantic.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
56767 INFO: Processing standard module hook 'hook-zoneinfo.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
57357 INFO: Processing standard module hook 'hook-dns.rdata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
57746 INFO: Processing standard module hook 'hook-pythoncom.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
57819 INFO: Processing standard module hook 'hook-pywintypes.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
58219 INFO: Processing standard module hook 'hook-skimage.filters.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
59264 INFO: Processing standard module hook 'hook-skimage.draw.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
59617 INFO: Processing standard module hook 'hook-skimage.transform.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
60015 INFO: Processing standard module hook 'hook-skimage.segmentation.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
60396 INFO: Processing standard module hook 'hook-skimage.exposure.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
60877 INFO: Processing standard module hook 'hook-skimage.morphology.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
61355 INFO: Processing standard module hook 'hook-skimage.feature.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
61847 INFO: Processing standard module hook 'hook-cv2.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
62482 INFO: Processing standard module hook 'hook-msoffcrypto.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
62680 INFO: Processing pre-safe-import-module hook 'hook-win32com.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\pre_safe_import_module'
62750 INFO: Processing standard module hook 'hook-win32com.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
63543 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.IX'
63579 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.halcyon'
63616 INFO: Analyzing hidden import 'ui.paginasControles.PruebasMensuales.ix_mensual'
63634 INFO: Analyzing hidden import 'ui.paginasControles.PruebasMensuales.tac_mensual'
63824 INFO: Analyzing hidden import 'ui.paginasControles.PruebasAnuales.ix_anual'
63902 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.seiscientos'
63923 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.braquiterapia'
64155 INFO: Analyzing hidden import 'pylinac.contrib'
64156 INFO: Analyzing hidden import 'pylinac.contrib.orthogonality'
64159 INFO: Analyzing hidden import 'pylinac.contrib.quasar'
64161 INFO: Analyzing hidden import 'pylinac.core.metrics'
64162 INFO: Analyzing hidden import 'pylinac.dlg'
64165 INFO: Analyzing hidden import 'pylinac.nuclear'
64191 INFO: Analyzing hidden import 'pylinac.plan_generator'
64191 INFO: Analyzing hidden import 'pylinac.plan_generator.dicom'
64213 INFO: Processing module hooks (post-graph stage)...
64294 WARNING: Hidden import "pycparser.lextab" not found!
64294 WARNING: Hidden import "pycparser.yacctab" not found!
64468 INFO: Processing pre-safe-import-module hook 'hook-tomli.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
64613 INFO: Processing standard module hook 'hook-skimage.color.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
65097 INFO: Processing standard module hook 'hook-skimage.restoration.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
65511 INFO: Processing standard module hook 'hook-skimage.metrics.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
66039 INFO: Processing standard module hook 'hook-matplotlib.backends.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
66040 INFO: Matplotlib backend selection method: automatic discovery of used backends
66072 INFO: Discovered Matplotlib backend(s) via `matplotlib.use()` call in module 'models.PDF.Mensuales.reportes_mensuales': ['Agg', 'Agg', 'Agg']
66107 INFO: The following Matplotlib backends were discovered by scanning for `matplotlib.use()` calls: ['Agg']. If your backend of choice is not in this list, either add a `matplotlib.use()` call to your code, or configure the backend collection via hook options (see: https://pyinstaller.org/en/stable/hooks-config.html#matplotlib-hooks).
66107 INFO: Selected matplotlib backends: ['Agg']
66351 INFO: Processing standard module hook 'hook-PIL.SpiderImagePlugin.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
66760 WARNING: Hidden import "scipy.special._cdflib" not found!
66803 INFO: Processing standard module hook 'hook-setuptools._vendor.importlib_metadata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
66861 INFO: Processing standard module hook 'hook-setuptools._vendor.jaraco.text.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
67393 INFO: Processing standard module hook 'hook-tzdata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
67765 INFO: Performing binary vs. data reclassification (1842 entries)
76743 INFO: Looking for ctypes DLLs
76887 INFO: Analyzing run-time hooks ...
76902 INFO: Including run-time hook 'pyi_rth_mplconfig.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
76904 INFO: Processing pre-find-module-path hook 'hook-_pyi_rth_utils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_find_module_path'
76906 INFO: Processing standard module hook 'hook-_pyi_rth_utils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
76910 INFO: Including run-time hook 'pyi_rth_pkgutil.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
76912 INFO: Including run-time hook 'pyi_rth_multiprocessing.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
76914 INFO: Including run-time hook 'pyi_rth_setuptools.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
76915 INFO: Including run-time hook 'pyi_rth_pkgres.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
76917 INFO: Including run-time hook 'pyi_rth_pywintypes.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
76917 INFO: Including run-time hook 'pyi_rth_pythoncom.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
76919 INFO: Including run-time hook 'pyi_rth_inspect.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
76921 INFO: Including run-time hook 'pyi_rth_pyqt5.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
76923 INFO: Including run-time hook 'pyi_rth_pyqtgraph_multiprocess.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
76924 INFO: Including run-time hook 'pyi_rth_cryptography_openssl.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
76988 INFO: Creating base_library.zip...
77001 INFO: Looking for dynamic libraries
79627 INFO: Extra DLL search directories (AddDllDirectory): ['C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyQt5\\Qt5\\bin', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\numpy.libs', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\scipy.libs', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\pandas.libs', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\cv2\\../../x64/vc14/bin']
79627 INFO: Extra DLL search directories (PATH): ['C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\cv2\\../../x64/vc14/bin', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyQt5\\Qt5\\bin']
82019 WARNING: Library not found: could not resolve 'LIBPQ.dll', dependency of 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-08-19\\.venv\\Lib\\site-packages\\PyQt5\\Qt5\\plugins\\sqldrivers\\qsqlpsql.dll'.
82265 INFO: Warnings written to C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\build\RAD-QA\warn-RAD-QA.txt
82497 INFO: Graph cross-reference written to C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\build\RAD-QA\xref-RAD-QA.html
82581 INFO: checking PYZ
82581 INFO: Building PYZ because PYZ-00.toc is non existent
82581 INFO: Building PYZ (ZlibArchive) C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\build\RAD-QA\PYZ-00.pyz
84768 INFO: Building PYZ (ZlibArchive) C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\build\RAD-QA\PYZ-00.pyz completed successfully.
84819 INFO: checking PKG
84819 INFO: Building PKG because PKG-00.toc is non existent
84819 INFO: Building PKG (CArchive) RAD-QA.pkg
84856 INFO: Building PKG (CArchive) RAD-QA.pkg completed successfully.
84857 INFO: Bootloader C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\.venv\Lib\site-packages\PyInstaller\bootloader\Windows-64bit-intel\runw.exe
84858 INFO: checking EXE
84858 INFO: Building EXE because EXE-00.toc is non existent
84858 INFO: Building EXE from EXE-00.toc
84858 INFO: Copying bootloader EXE to C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\build\RAD-QA\RAD-QA.exe
84937 INFO: Copying icon to EXE
84985 INFO: Copying 0 resources to EXE
84985 INFO: Embedding manifest in EXE
85030 INFO: Appending PKG archive to EXE
85110 INFO: Fixing EXE headers
86393 INFO: Building EXE from EXE-00.toc completed successfully.
86494 INFO: checking COLLECT
86495 INFO: Building COLLECT because COLLECT-00.toc is non existent
86495 INFO: Building COLLECT COLLECT-00.toc
88813 INFO: Building COLLECT COLLECT-00.toc completed successfully.
88833 INFO: Build complete! The results are available in: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\dist

- Expulsion de la terminal para la previsualizacion de la herramienta de migracion:

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19> .venv\Scripts\python scripts\migrar_bd_a_estandar.py "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\BaseDatosQA.db"
Base de datos: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\BaseDatosQA.db
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
Respaldo de la base de datos creado en: C:\Users\parra\AppData\Local\Temp\tmprv6tmsqh\respaldos_bd\pre_migracion\BaseDatosQA_2026-08-19_084907.db
E10: migrando 58 tablas a ON DELETE RESTRICT...

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
  preguntas: columna(s) nueva(s) ['activo']
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
    id=7: (G9) N31014 vigente: h_cal=33 es la humedad AMBIENTAL del certificado ADW39861. SUPUESTO DE TRABAJO (DA-27): se asume 50% de referencia, no esuna lectura del certificado
    id=16: (G9) Pozo A972662 vigente: v1 sin registrar; certificado HDR12115 declara 'Collecting Electrode Bias: +300 V'
    id=16: (G9) Pozo A972662 vigente: h_cal=38 es la humedad AMBIENTAL del certificado HDR12115. SUPUESTO DE TRABAJO (DA-27): se asume 50% de referencia, no es una lectura del certificado
    id=57: (G7, DA-23) Fecha con mes y dia invertidos ('7/28/2025', QDate invalido) -- certificado HDR12899 confirma 'Calibration Completed: 28/JUL/2025' -> 28 de julio de 2025
    id=58: (G7, DA-23) Fecha con mes y dia invertidos, misma correccion que id57 (certificado HDR12899)

--- Saneamiento de claves duplicadas del bloque de QC (SA1, DA-38) ---
  57 fila(s) pasadas a histórica (activo=0), cero borradas:
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
    analisis_placa_franjas: 6 fila(s)
      rowid=1 clave={'ref': 16, 'franja': 'Franja 1'} -- gana rowid=4
      rowid=2 clave={'ref': 16, 'franja': 'Franja 2'} -- gana rowid=5
      rowid=3 clave={'ref': 16, 'franja': 'Franja 3'} -- gana rowid=6
      rowid=10 clave={'ref': 15, 'franja': 'Franja 1'} -- gana rowid=13
      rowid=11 clave={'ref': 15, 'franja': 'Franja 2'} -- gana rowid=14
      rowid=12 clave={'ref': 15, 'franja': 'Franja 3'} -- gana rowid=15
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
  creados en esta corrida: 22 -- ['HC_desplazamiento_isocentro_mensual', 'HC_dosimetria_anual', 'HC_imagen_perfil_mlc_anual', 'HC_indicadores_brazo', 'HC_indicadores_camilla', 'HC_indicadores_colimador', 'HC_indicadores_laser', 'HC_linealidad_unidades_monitor_anual', 'HC_precision_posicion_multilaminas_anual', 'HC_tamanos_campo_radiacion', 'HC_velocidad_multilaminas_anual', 'analisis_placa_franjas', 'control_conos', 'control_cunas', 'dosimetriaMen', 'equipos_medicion', 'preguntas', 'tabla_control_camaras_monitoras', 'tabla_factor_campo', 'tabla_factores_sobre_eje', 'tabla_factores_transmision', 'tamano_campo']

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

--- Censo completo (69 tablas revisadas) ---
  Las 63 tablas restantes conservan sus conteos (ninguna perdió filas).

--- Duplicados de controles (unicidad DP-06) ---
  Ningún duplicado por (equipo, control, mes/año) entre las filas activas.

- Expulsion de la terminal para la ejecucion de la herramienta de migracion:

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19> .venv\Scripts\python scripts\migrar_bd_a_estandar.py "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\BaseDatosQA.db" --aplicar --usuario FelipePP12
Base de datos: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\BaseDatosQA.db
integrity_check antes: ok
Backup creado: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\BaseDatosQA.db.pre_migracion_20260819_085116.bak
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
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\respaldos_bd\pre_migracion\BaseDatosQA_2026-08-19_085117.db
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
  preguntas: columna(s) nueva(s) ['activo']
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

--- Saneamiento de claves duplicadas del bloque de QC (SA1, DA-38) ---
  57 fila(s) pasadas a histórica (activo=0), cero borradas:
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
    analisis_placa_franjas: 6 fila(s)
      rowid=1 clave={'ref': 16, 'franja': 'Franja 1'} -- gana rowid=4
      rowid=2 clave={'ref': 16, 'franja': 'Franja 2'} -- gana rowid=5
      rowid=3 clave={'ref': 16, 'franja': 'Franja 3'} -- gana rowid=6
      rowid=10 clave={'ref': 15, 'franja': 'Franja 1'} -- gana rowid=13
      rowid=11 clave={'ref': 15, 'franja': 'Franja 2'} -- gana rowid=14
      rowid=12 clave={'ref': 15, 'franja': 'Franja 3'} -- gana rowid=15
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
  creados en esta corrida: 22 -- ['HC_desplazamiento_isocentro_mensual', 'HC_dosimetria_anual', 'HC_imagen_perfil_mlc_anual', 'HC_indicadores_brazo', 'HC_indicadores_camilla', 'HC_indicadores_colimador', 'HC_indicadores_laser', 'HC_linealidad_unidades_monitor_anual', 'HC_precision_posicion_multilaminas_anual', 'HC_tamanos_campo_radiacion', 'HC_velocidad_multilaminas_anual', 'analisis_placa_franjas', 'control_conos', 'control_cunas', 'dosimetriaMen', 'equipos_medicion', 'preguntas', 'tabla_control_camaras_monitoras', 'tabla_factor_campo', 'tabla_factores_sobre_eje', 'tabla_factores_transmision', 'tamano_campo']

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

--- Censo completo (69 tablas revisadas) ---
  Las 63 tablas restantes conservan sus conteos (ninguna perdió filas).

--- Duplicados de controles (unicidad DP-06) ---
  Ningún duplicado por (equipo, control, mes/año) entre las filas activas.

Listo. Backup de seguridad conservado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\BaseDatosQA.db.pre_migracion_20260819_085116.bak                                                                                                                                                     
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19> 
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19> $env:RADQA_HALCYON_MPC = "C:\Users\parra\Documents\Archivos_UseApp\Archivos QA\ReportesDiariosQA001\ReportesDiarioHalcyon"

- Expulsion de la terminal durante las pruebas:

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19> python main.py
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
load table: 0.091s
asignar_encabezados: 0.094s
button_click: 0.095s
entro a la funcion de ordenacion
Entra a la función add_info en load.py con tabla: aceleradorlineal_ix
Manteniendo columna ID

▥ Columnas detectadas: ['date', 'user_id', 'luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla', 'laseres', 'telemetro', 'tamano_campo', 'centrado_reticulo', 'tol_fot_6mv', 'tol_fot_15mv', 'tol_ele_6mev', 'tol_ele_9mev', 'tol_ele_12mev', 'tol_ele_15mev', 'observaciones'] para aceleradorlineal_ix

Limpiando data
Limpiando data
consultando db
2026-08-20
ℹ No hay datos registrados para la fecha 2026-08-20.
consultando db
2026-08-06
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado laseres: 2 en btn_2_laseres
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
✓ Datos del 2026-08-06 cargados correctamente.
  - Botones finales: 12
entro a la funcion de ordenacion
Entra a la función add_info en load.py con tabla: aceleradorlineal_ix
Manteniendo columna ID

▥ Columnas detectadas: ['date', 'user_id', 'luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla', 'laseres', 'telemetro', 'tamano_campo', 'centrado_reticulo', 'tol_fot_6mv', 'tol_fot_15mv', 'tol_ele_6mev', 'tol_ele_9mev', 'tol_ele_12mev', 'tol_ele_15mev', 'observaciones'] para aceleradorlineal_ix

consultando db
2026-08-20
ℹ No hay datos registrados para la fecha 2026-08-20.
Limpiando data
consultando db
2026-08-19
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado laseres: 2 en btn_2_laseres
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado telemetro: 2 en btn_2_telemetro
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado tamano_campo: 2 en btn_2_tamano_campo
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado centrado_reticulo: 2 en line_2_centrado_reticulo
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargadas observaciones
✓ Datos del 2026-08-19 cargados correctamente.
  - Botones finales: 12
entro a la funcion de ordenacion
Entra a la función add_info en load.py con tabla: aceleradorlineal_ix
Manteniendo columna ID

▥ Columnas detectadas: ['date', 'user_id', 'luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla', 'laseres', 'telemetro', 'tamano_campo', 'centrado_reticulo', 'tol_fot_6mv', 'tol_fot_15mv', 'tol_ele_6mev', 'tol_ele_9mev', 'tol_ele_12mev', 'tol_ele_15mev', 'observaciones'] para aceleradorlineal_ix

Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x0000023354BCDDD0>, id_f1_num usado: Administrador
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
<PyQt5.QtWidgets.QGridLayout object at 0x000002339D1A9AB0>
<PyQt5.QtWidgets.QGridLayout object at 0x000002339D1A9A20>
<PyQt5.QtWidgets.QGridLayout object at 0x000002339D1A9BD0>
<PyQt5.QtWidgets.QGridLayout object at 0x000002339D1A9B40>
<PyQt5.QtWidgets.QGridLayout object at 0x000002339D1A9C60>
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
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025
→ Eliminando en tabla equipos_medicion, WHERE "id" = ?, valores [278]
UPDATE (anular) ejecutado correctamente
Fin de eliminarRegistro

Insertando datos de equipos para IX
Insertados 4 registros de equipos correctamente
Actualizando tabla de controles mensuales para Clinac ix
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000002339D0E85E0>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

Se presionó btn_guardar_ix

 Función guardar_control_conos en IX

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000002339D0E85E0>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

Se presionó btn_guardar_ix
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\respaldos_bd\BaseDatosQA_2026-08-19_085831.db

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19> python main.py
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
load table: 0.091s
asignar_encabezados: 0.094s
button_click: 0.095s
entro a la funcion de ordenacion
Entra a la función add_info en load.py con tabla: aceleradorlineal_ix
Manteniendo columna ID

▥ Columnas detectadas: ['date', 'user_id', 'luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla', 'laseres', 'telemetro', 'tamano_campo', 'centrado_reticulo', 'tol_fot_6mv', 'tol_fot_15mv', 'tol_ele_6mev', 'tol_ele_9mev', 'tol_ele_12mev', 'tol_ele_15mev', 'observaciones'] para aceleradorlineal_ix

Limpiando data
Limpiando data
consultando db
2026-08-20
ℹ No hay datos registrados para la fecha 2026-08-20.
consultando db
2026-08-06
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado laseres: 2 en btn_2_laseres
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
✓ Datos del 2026-08-06 cargados correctamente.
  - Botones finales: 12
entro a la funcion de ordenacion
Entra a la función add_info en load.py con tabla: aceleradorlineal_ix
Manteniendo columna ID

▥ Columnas detectadas: ['date', 'user_id', 'luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla', 'laseres', 'telemetro', 'tamano_campo', 'centrado_reticulo', 'tol_fot_6mv', 'tol_fot_15mv', 'tol_ele_6mev', 'tol_ele_9mev', 'tol_ele_12mev', 'tol_ele_15mev', 'observaciones'] para aceleradorlineal_ix

consultando db
2026-08-20
ℹ No hay datos registrados para la fecha 2026-08-20.
Limpiando data
consultando db
2026-08-19
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado laseres: 2 en btn_2_laseres
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado telemetro: 2 en btn_2_telemetro
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado tamano_campo: 2 en btn_2_tamano_campo
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargado centrado_reticulo: 2 en line_2_centrado_reticulo
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
['btn_2_laseres', 'btn_2_telemetro', 'btn_2_tamano_campo', 'line_2_centrado_reticulo', 'line_2_fot_6mv', 'line_2_fot_15mv', 'line_2_ele_6mev', 'line_2_ele_9mev', 'line_2_ele_12mev', 'line_2_ele_15mev']
✓ Cargadas observaciones
✓ Datos del 2026-08-19 cargados correctamente.
  - Botones finales: 12
entro a la funcion de ordenacion
Entra a la función add_info en load.py con tabla: aceleradorlineal_ix
Manteniendo columna ID

▥ Columnas detectadas: ['date', 'user_id', 'luces_consola', 'luces_puerta', 'luces_irradiacion', 'sistema_visualizacion', 'sistema_anticolision', 'interruptor_radiacion_puerta', 'interruptor_radiacion_panel', 'interrupcion_um', 'verificacion_monitoras', 'movimiento_brazo', 'movimiento_colimador', 'movimientos_camilla', 'laseres', 'telemetro', 'tamano_campo', 'centrado_reticulo', 'tol_fot_6mv', 'tol_fot_15mv', 'tol_ele_6mev', 'tol_ele_9mev', 'tol_ele_12mev', 'tol_ele_15mev', 'observaciones'] para aceleradorlineal_ix

Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x0000023354BCDDD0>, id_f1_num usado: Administrador
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
<PyQt5.QtWidgets.QGridLayout object at 0x000002339D1A9AB0>
<PyQt5.QtWidgets.QGridLayout object at 0x000002339D1A9A20>
<PyQt5.QtWidgets.QGridLayout object at 0x000002339D1A9BD0>
<PyQt5.QtWidgets.QGridLayout object at 0x000002339D1A9B40>
<PyQt5.QtWidgets.QGridLayout object at 0x000002339D1A9C60>
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
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025
→ Eliminando en tabla equipos_medicion, WHERE "id" = ?, valores [278]
UPDATE (anular) ejecutado correctamente
Fin de eliminarRegistro

Insertando datos de equipos para IX
Insertados 4 registros de equipos correctamente
Actualizando tabla de controles mensuales para Clinac ix
Actualizando tabla de controles mensuales para Clinac ix

 Función guardar_control_conos en IX

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000002339D0E85E0>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

Se presionó btn_guardar_ix

 Función guardar_control_conos en IX

 -> Entra en subir_control_cunas en 600
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000002339D0E85E0>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

Se presionó btn_guardar_ix
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\respaldos_bd\BaseDatosQA_2026-08-19_085831.db
(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19> python main.py
    Método open_main_window en la clase: DialogAdminPermiso
admin2025
    Método seleccionar_firma en la clase: VentanaFirma
    Método subir_firma en la clase: VentanaFirma
Usuario <data.ManejoDatos.user.Usuario object at 0x000001E5AD54FC10> agregado exitosamente.
Fparrap
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
iniGUI: 0.023s
load table: 0.090s
asignar_encabezados: 0.093s
button_click: 0.093s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001E5AD558150>, id_f1_num usado: Felipe Parra Paez
Consulta de físicos: usuario actual identificado como físico -- Felipe Parra Paez
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
<PyQt5.QtWidgets.QGridLayout object at 0x000001E646102200>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E646102170>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E646102320>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E646102290>
<PyQt5.QtWidgets.QGridLayout object at 0x000001E6461023B0>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
action tolerance encontrado
Widgets MLC encontrados y configurados
    Método open_main_window en la clase: DialogAdminPermisoEliminar
admin2025
→ Eliminando en tabla equipos_medicion, WHERE "id" = ?, valores [282]
UPDATE (anular) ejecutado correctamente
Fin de eliminarRegistro

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
line: observaciones_segu, widget: <PyQt5.QtWidgets.QLineEdit object at 0x000001E646110D30>
Texto actual en observaciones_segu: ''
Datos de control de cuñas insertados correctamente
Actualizando tabla de controles mensuales para Clinac ix

Se presionó btn_guardar_ix
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001E5AD558150>, id_f1_num usado: Felipe Parra Paez
Consulta de físicos: usuario actual identificado como físico -- Felipe Parra Paez
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
Fecha Final COT: 2026-08-19 09:08:45-05:00
Horas transcurridas desde 2026-08-19 09:08:45: 1804.5391666666667
Dias transcurridos: 75.18913194444444
 La actividad es:  6.7385
Subiendo tabla indicadores_brazo sin id_energia
Los argumentos son: nombre_tabla=indicadores_brazo, ref=43, anual=False, id=False

▥ Columnas detectadas: ['ref', 'nivel', 'indicador_luminoso_consola', 'indicador_luminoso_equipo'] para indicadores_brazo

Bloque identificado por ['ref'] para la tabla indicadores_brazo, id = False

▥ Datos a insertar en indicadores_brazo:
  - [43, '0°', '0', '0']
  - [43, '90°', '90', '91']
  - [43, '180°', '180', '180']
  - [43, '270°', '270', '273']
Actualizando tabla de controles mensuales para Clinac ix
Tabla indicadores_brazo subida correctamente
Subiendo tabla indicadores_angulares_colimador sin id_energia
Los argumentos son: nombre_tabla=indicadores_angulares_colimador, ref=43, anual=False, id=False

▥ Columnas detectadas: ['ref', 'nivel', 'indicador_luminoso_consola', 'indicador_luminoso_equipo'] para indicadores_angulares_colimador

Bloque identificado por ['ref'] para la tabla indicadores_angulares_colimador, id = False

▥ Datos a insertar en indicadores_angulares_colimador:
  - [43, '0°', '0', '0']
  - [43, '90°', '90', '09']
  - [43, '180°', '2', '2']
  - [43, '270°', '2', '2']
Actualizando tabla de controles mensuales para Clinac ix
Tabla indicadores_angulares_colimador subida correctamente

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
Entra a subir tabla en fieldSize

▥ Columnas detectadas: ['ref', 'campo_nominal', 'ie_largoy1', 'ie_largoy2', 'ie_anchox1', 'ie_anchox2', 'ic_largoy1', 'ic_largoy2', 'ic_anchox1', 'ic_anchox2'] para tamano_campo

Bloque identificado por ['ref'] para la tabla tamano_campo, id = False

▥ Datos a insertar en tamano_campo:
  - [43, '5 x 5', '5', '5', '5', '5', '5', '5', '5', '5']
  - [43, '10 x 10', '10', '01', '10', '10', '10', '10', '10', '10']
  - [43, '15 x 15', '155', '15', '15', '15', '15', '15', '15', '15']
  - [43, '20 x 20', '20', '20', '02', '02', '20', '20', '20', '20']
Actualizando tabla de controles mensuales para Clinac ix

La variable equipo_f en la función fieldSize es: Clinac ix
Entra a subir tabla en fieldSize

▥ Columnas detectadas: ['ref', 'campo_nominal', 'ie_largoy1', 'ie_largoy2', 'ie_anchox1', 'ie_anchox2', 'ic_largoy1', 'ic_largoy2', 'ic_anchox1', 'ic_anchox2'] para tamano_campo

Bloque identificado por ['ref'] para la tabla tamano_campo, id = False

▥ Datos a insertar en tamano_campo:
  - [43, '5 x 5', '5', '5', '5', '5', '5', '5', '5', '5']
  - [43, '10 x 10', '10', '01', '10', '10', '10', '10', '10', '10']
  - [43, '15 x 15', '155', '15', '15', '15', '15', '15', '15', '15']
  - [43, '20 x 20', '20', '20', '02', '02', '20', '20', '20', '20']
Actualizando tabla de controles mensuales para Clinac ix

La variable equipo_f en la función fieldSize es: Clinac ix
Analisis de imagen activado en subir_imagen en PruebasDiarias.py
analizando imagen
Subir imagen activado en imagenUpLoader en PruebasDiarias.py
Analizando imagen...
DPI:  599
Lado arriba: 100.67 mm
Lado abajo: 99.74 mm
Lado izquierda: 99.75 mm
Lado derecha: 99.14 mm
Centro: (1367, 1424)
Tamaño de Campo: 114.52 (mm)
Tamaño de Campo: 114.55 (mm)
Cruz vs centro geométrico: Δx=0.00mm, Δy=0.42mm
Tamaño de Campo: No disponible
Tamaño de Campo: No disponible
Cruz vs centro geométrico: Δx=0.00mm, Δy=0.42mm
Tamaño de Campo: 111.01 (mm)
Tamaño de Campo: 110.07 (mm)
Cruz vs centro geométrico: Δx=0.00mm, Δy=0.42mm
Aceptar imagen activado en PruebasDiarias.py

Entra a la función crear_algo en load.py con ref: 43 y imagen: C:/Users/parra/Documents/Archivos_UseApp/PlacasHistoricas/placa_ref6.jpeg

Entra a la función crear_algo en load.py con ref: 43 y imagen: C:/Users/parra/Documents/Archivos_UseApp/PlacasHistoricas/placa_ref6.jpeg

Entra a la función crear_algo en load.py con ref: 43 y imagen: C:/Users/parra/Documents/Archivos_UseApp/PlacasHistoricas/placa_ref6.jpeg
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

Dialog llamado desde: PruebaMensualIX
300
300
300
Data saved successfully for date: 19/08/2026

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

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19> python main.py
Fparrap
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
iniGUI: 0.020s
load table: 0.086s
asignar_encabezados: 0.089s
button_click: 0.090s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x0000017782C50610>, id_f1_num usado: Felipe Parra Paez
Consulta de físicos: usuario actual identificado como físico -- Felipe Parra Paez
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
<PyQt5.QtWidgets.QGridLayout object at 0x000001783DC74F70>
<PyQt5.QtWidgets.QGridLayout object at 0x000001783DC74EE0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001783DC75090>
<PyQt5.QtWidgets.QGridLayout object at 0x000001783DC75000>
<PyQt5.QtWidgets.QGridLayout object at 0x000001783DC75120>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
action tolerance encontrado
Widgets MLC encontrados y configurados
Dialog llamado desde: PruebaMensualIX
300
Analisis de imagen activado en subir_imagen en PruebasDiarias.py
analizando imagen
Subir imagen activado en imagenUpLoader en PruebasDiarias.py
Analizando imagen...
DPI:  200
Lado arriba: 100.08 mm
Lado abajo: 99.57 mm
Lado izquierda: 98.69 mm
Lado derecha: 98.94 mm
Centro: (441, 437)
Tamaño de Campo: 103.26 (mm)
Tamaño de Campo: 102.85 (mm)
Cruz vs centro geométrico: Δx=0.00mm, Δy=-0.13mm
Tamaño de Campo: 103.08 (mm)
Tamaño de Campo: 103.14 (mm)
Cruz vs centro geométrico: Δx=0.00mm, Δy=-0.13mm
Tamaño de Campo: 102.93 (mm)
Tamaño de Campo: 102.93 (mm)
Cruz vs centro geométrico: Δx=0.00mm, Δy=-0.13mm
Aceptar imagen activado en PruebasDiarias.py

Entra a la función crear_algo en load.py con ref: 43 y imagen: C:/Users/parra/Documents/Archivos_UseApp/PlacasHistoricas/placa_ref35.jpeg
Tamaño de Campo: 103.26 (mm)
Tamaño de Campo: 102.85 (mm)
Cruz vs centro geométrico: Δx=0.00mm, Δy=-0.13mm
Tamaño de Campo: 103.08 (mm)
Tamaño de Campo: 103.14 (mm)
Cruz vs centro geométrico: Δx=0.00mm, Δy=-0.13mm
Tamaño de Campo: 102.93 (mm)
Tamaño de Campo: 102.93 (mm)
Cruz vs centro geométrico: Δx=0.00mm, Δy=-0.13mm
Tamaño de Campo: 102.93 (mm)
Tamaño de Campo: 102.93 (mm)
Cruz vs centro geométrico: Δx=0.00mm, Δy=-0.13mm
Tamaño de Campo: 103.08 (mm)
Tamaño de Campo: 103.14 (mm)
Cruz vs centro geométrico: Δx=0.00mm, Δy=-0.13mm
Tamaño de Campo: 103.26 (mm)
Tamaño de Campo: 102.85 (mm)
Cruz vs centro geométrico: Δx=0.00mm, Δy=-0.13mm
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
Fecha Final COT: 2026-08-19 10:00:24-05:00
Horas transcurridas desde 2026-08-19 10:00:24: 1805.4
Dias transcurridos: 75.22500000000001
 La actividad es:  6.7362

Anotaciones de la revision:

- Cuando en el diario se le da al boton limpiar no se limpia el widget de anotaciones.
- El guardado de datos parece estar bien, con anulacion y agregacion de los bloques nuevos activos, como el control de conos.
- Se guardan y se pueden editar normalmente al reabrir.
- En el formulario mensual del iX en la parte de aspectos mecanicos en el analisis de imagen parece que despues de darle aceptar se debe esperar un tiempo antes de poder guardar los datos obtenidos, sin embargo, mientras se ejecuta ese proceso, no hay nada que avise que debemos esperar, por lo cual se presiona el boton de guardar con la intencion de saber si esta funcionando pero no funciona seguro porque se debe esperar que salgan los resultados del analisis de imagen, una vez salen si genera un mensaje el boton de guardar de que los datos fueron guardados adecuadamente, ahora, donde se guradan esos datos del analisis de imagen? Parece que no estan completamente esos datos en analisis_placa_franjas, que ocasiona que algunos de estos campos queden vacios? Es porque no cumplen? Se debe generar alguna barrera para este proceso para garantizar que se colecten todos los datos? (Esto lo dejamos para un plan posterior de analisis de imagenes) por ahora hay que terminar de garantizar que lo basico, el guardado, las rutas de la BD, la auditoria funcionen perfectamente, entiendo que no todas las tablas deben funcionar de esta manera, pero solo necesito quedar con claridad de que fue lo que se quiso disenar y si el resultado es coherente con esto y con las buenas practicas, con respecto a este punto no se esta guardando la imagen, y propongo que si hay un proceso corriendo se genere una pestana o algun indicador de que hay un proceso corriendo, para que uno sepa y espere.
- No se esta guardando la imagen de la parte de aspectos mecanicos del formulario mensual, en el iX no se si es una funcion que se comparte entre los 3 aceleradores, se deberia verificar igual, lo raro es que sale una ventana emergente que habla sobre que si se guardo la imagen, donde estan ademas guardadas las demas imagenes???Bueno, ya vi donde se guardan, en preguntas, pero igual no se carga en la app para visualizarla(Grave)
- Hay algunos registros en la tabla de auditorias sobre eliminar sin un usuario registrado, se elimino una de las camaras seleccionadas para la seccion de equipos en el formulario mensual desde Ver tabla en la app.(Grave).
- Porque sale un calculo de actividad en la terminal asi de un momento a otro?
- analisis_placa_verificaciones ni analisis_placa_correcciones no genera nuevos guardados con cada pulsado del boton, hay que garantizar que toda la BD quedo con la estructura y conexiones funcionales, solo analisis_placa_franjas.
- En la calculadora dosimetrica deberian bloquearse tambien los botones de las energias por tipo de radiacion luego de cargar un calculo guardado(no urgente, despues se hace, hay que anotarla en una lista de deudas)

Pruebas de la guia del rebuild:
- Se hizo la migracion, copie todo lo expulsado por la terminal y llevo las bases de datos para que tu me ayudes a comprobar que todas las opereciones quedaron completas.
- El ciclo del reemplazo salio bien con el formulari anual del 600.
- Simule el llenado casi completo del formulario mensual del iX, hice varios guardados y todo parece funcionar bien excepto por la parte de recargar la imagen al abrir, no se si en general su guardado se esta dando correctamente y es lo que tu tienes que revisar con lo que te llevo.
- Lo que dije en el item anterior de que parece guardarse aleatoriamente una imagen en preguntas, digo aleatoriamente porque le he dado varias veces guardar, hay una cantidad inconsistente segun yo de guardados, porque nada mas hay dos, y uno esta activo y el otro no, el activo si contiene la imagen pero igual no se recarga nada al reabrir el formulario en la app.
- Todo el bloque de guardado de aspectos dosimetricos del formulario mensual del iX que es el mas extenso parece funcionar bien, creo que todos los valores importados por mcc se cargaron en la BD y se conservan los valores exportados de la calculadora y dentro de la calculadora para visualizar parametros historicos.

Expulsion de la terminal:

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19> python main.py
Fparrap
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
iniGUI: 0.020s
load table: 0.086s
asignar_encabezados: 0.092s
button_click: 0.092s
Clinac 600
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x00000265EA1BB010>, id_f1_num usado: Felipe Parra Paez
Consulta de físicos: usuario actual identificado como físico -- Felipe Parra Paez
Físico 2 seleccionado: Cristian Castellanos, ID: 3
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x00000265EA1BB010>, id_f1_num usado: Felipe Parra Paez
Consulta de físicos: usuario actual identificado como físico -- Felipe Parra Paez
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
Fecha Final COT: 2026-08-19 10:35:58-05:00
Horas transcurridas desde 2026-08-19 10:35:58: 1805.9927777777777
Dias transcurridos: 75.24969907407407
 La actividad es:  6.7346
Subiendo tabla tabla_factor_campo normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tamano_campo', 'factor_campo', 'factor_campo_esperado', 'discrepancia'] para tabla_factor_campo

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factor_campo, id = True

▥ Datos a insertar en tabla_factor_campo:
  - [44, 0, '3x3', '3', '3', '0.00']
  - [44, 0, '10x10', '10', '10', '0.00']
  - [44, 0, '15x15', '1', '1', '0.00']
  - [44, 0, '20x20', '1', '1', '0.00']
  - [44, 0, '25x25', '1', '1', '0.00']
  - [44, 0, '30x30', '11', '1', '1000.00']
Actualizando tabla de controles anuales para Clinac 600
Tabla(s) tabla_factor_campo subida(s) correctamente
Subiendo tabla tabla_factor_campo normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tamano_campo', 'factor_campo', 'factor_campo_esperado', 'discrepancia'] para tabla_factor_campo

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factor_campo, id = True

▥ Datos a insertar en tabla_factor_campo:
  - [44, 0, '3x3', '3', '3', '0.00']
  - [44, 0, '10x10', '10', '10', '0.00']
  - [44, 0, '15x15', '1', '1', '0.00']
  - [44, 0, '20x20', '1', '1', '0.00']
  - [44, 0, '25x25', '1', '1', '0.00']
  - [44, 0, '30x30', '100', '1', '9900.00']
Actualizando tabla de controles anuales para Clinac 600
Tabla(s) tabla_factor_campo subida(s) correctamente
Subiendo tabla tabla_factor_campo normalmente
Manteniendo columna ID

▥ Columnas detectadas: ['ref', 'id_energia', 'tamano_campo', 'factor_campo', 'factor_campo_esperado', 'discrepancia'] para tabla_factor_campo

Bloque identificado por ['ref', 'id_energia'] para la tabla tabla_factor_campo, id = True

▥ Datos a insertar en tabla_factor_campo:
  - [44, 0, '3x3', '3', '3', '0.00']
  - [44, 0, '10x10', '50', '10', '400.00']
  - [44, 0, '15x15', '1', '1', '0.00']
  - [44, 0, '20x20', '1', '1', '0.00']
  - [44, 0, '25x25', '1', '1', '0.00']
  - [44, 0, '30x30', '100', '1', '9900.00']
Actualizando tabla de controles anuales para Clinac 600
Tabla(s) tabla_factor_campo subida(s) correctamente
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\respaldos_bd\BaseDatosQA_2026-08-19_103731.db
Fparrap
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
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000002666F32AD50>, id_f1_num usado: Felipe Parra Paez
Consulta de físicos: usuario actual identificado como físico -- Felipe Parra Paez
Físico 2 seleccionado: Cristian Castellanos, ID: 3
Cargando widgets desde hoja: preguntas_anual_600
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
  - DataFrame: 22 filas
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
asignar_encabezados: 0.097s
button_click: 0.097s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000002666F32AD50>, id_f1_num usado: Felipe Parra Paez
Consulta de físicos: usuario actual identificado como físico -- Felipe Parra Paez
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
<PyQt5.QtWidgets.QGridLayout object at 0x0000026636A54790>
<PyQt5.QtWidgets.QGridLayout object at 0x0000026636A54C10>
<PyQt5.QtWidgets.QGridLayout object at 0x0000026636A54AF0>
<PyQt5.QtWidgets.QGridLayout object at 0x0000026636A54B80>
<PyQt5.QtWidgets.QGridLayout object at 0x0000026636A54A60>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
action tolerance encontrado
Widgets MLC encontrados y configurados
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\respaldos_bd\BaseDatosQA_2026-08-19_104534.db
Fparrap
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
iniGUI: 0.023s
load table: 0.093s
asignar_encabezados: 0.097s
button_click: 0.097s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000002663082AD90>, id_f1_num usado: Felipe Parra Paez
Consulta de físicos: usuario actual identificado como físico -- Felipe Parra Paez
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
<PyQt5.QtWidgets.QGridLayout object at 0x0000026674F98D30>
<PyQt5.QtWidgets.QGridLayout object at 0x0000026674F98CA0>
<PyQt5.QtWidgets.QGridLayout object at 0x0000026674F98DC0>
<PyQt5.QtWidgets.QGridLayout object at 0x0000026674F98E50>
<PyQt5.QtWidgets.QGridLayout object at 0x0000026674F98EE0>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
action tolerance encontrado
Widgets MLC encontrados y configurados
Analisis de imagen activado en subir_imagen en PruebasDiarias.py
analizando imagen
Subir imagen activado en imagenUpLoader en PruebasDiarias.py
Analizando imagen...
DPI:  300
Lado arriba: 99.74 mm
Lado abajo: 99.65 mm
Lado izquierda: 99.40 mm
Lado derecha: 99.40 mm
Centro: (656, 638)
Tamaño de Campo: 103.24 (mm)
Tamaño de Campo: 101.61 (mm)
Cruz vs centro geométrico: Δx=-0.08mm, Δy=0.00mm
Tamaño de Campo: 105.53 (mm)
Tamaño de Campo: 103.28 (mm)
Cruz vs centro geométrico: Δx=-0.08mm, Δy=0.00mm
Tamaño de Campo: 103.17 (mm)
Tamaño de Campo: 101.64 (mm)
Cruz vs centro geométrico: Δx=-0.08mm, Δy=0.00mm
Recursos limpiados correctamente
Aceptar imagen activado en PruebasDiarias.py

Entra a la función crear_algo en load.py con ref: 45 y imagen: C:/Users/parra/Documents/Archivos_UseApp/PlacasHistoricas/placa_ref30.jpeg

Entra a la función crear_algo en load.py con ref: 45 y imagen: C:/Users/parra/Documents/Archivos_UseApp/PlacasHistoricas/placa_ref30.jpeg
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
Fecha Final COT: 2026-08-19 10:47:48-05:00
Horas transcurridas desde 2026-08-19 10:47:48: 1806.19
Dias transcurridos: 75.25791666666667
 La actividad es:  6.7341
Analisis de imagen activado en subir_imagen en PruebasDiarias.py
analizando imagen
Subir imagen activado en imagenUpLoader en PruebasDiarias.py
DPI:  599
Aceptar imagen activado en PruebasDiarias.py
DPI:  599
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\respaldos_bd\BaseDatosQA_2026-08-19_104835.db

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19> python main.py
Fparrap
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
load table: 0.088s
asignar_encabezados: 0.092s
button_click: 0.092s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x0000022E6F74F950>, id_f1_num usado: Felipe Parra Paez
Consulta de físicos: usuario actual identificado como físico -- Felipe Parra Paez
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
<PyQt5.QtWidgets.QGridLayout object at 0x0000022EF8C864D0>
<PyQt5.QtWidgets.QGridLayout object at 0x0000022EF8C86440>
<PyQt5.QtWidgets.QGridLayout object at 0x0000022EF8C865F0>
<PyQt5.QtWidgets.QGridLayout object at 0x0000022EF8C86560>
<PyQt5.QtWidgets.QGridLayout object at 0x0000022EF8C86680>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
action tolerance encontrado
Widgets MLC encontrados y configurados

Subiendo datos para preguntas

▥ Columnas detectadas: ['ref', 'iso_mec', 'reticulo_cent', 'bordes_coin', 'camilla_vert_rango', 'camilla_vert_desp', 'camilla_iso_desp', 'telem_rango', 'telem_desp', 'camp_luz_desp', 'puntero_telem_diff', 'laser_techo', 'laser_lateral27', 'laser_lateral9', 'observaciones'] para preguntas

Datos guardados correctamente.
Actualizando tabla de controles mensuales para Clinac ix
Datos subidos correctamente
Respaldo de la base de datos creado en: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-08-19\respaldos_bd\BaseDatosQA_2026-08-19_105217.db
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
load table: 0.089s
asignar_encabezados: 0.092s
button_click: 0.093s
Clinac ix
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x0000022EF43E96D0>, id_f1_num usado: Administrador
Consulta de físicos: el usuario actual no aparece en la lista de físicos (role='Físico Médico') -- normal si quien inició sesión no tiene ese rol
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
<PyQt5.QtWidgets.QGridLayout object at 0x0000022EB5AFD900>
<PyQt5.QtWidgets.QGridLayout object at 0x0000022EB5AFD870>
<PyQt5.QtWidgets.QGridLayout object at 0x0000022EB5AFD990>
<PyQt5.QtWidgets.QGridLayout object at 0x0000022EB5AFDA20>
<PyQt5.QtWidgets.QGridLayout object at 0x0000022EB5AFDAB0>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
ln tolerance encontrado
action tolerance encontrado
Widgets MLC encontrados y configurados
Dialog llamado desde: PruebaMensualIX
300
300
300
Data saved successfully for date: 19/08/2026

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