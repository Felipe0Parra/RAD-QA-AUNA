# Handoff técnico — Empaquetado Windows (PyInstaller) — RAD-QA

**Fecha de la sesión:** 2026-07-06
**Entorno de esta sesión:** Windows 11, Python 3.11.0 (64-bit), venv en `.venv/`, PyInstaller 6.21.0
**Autor:** Sesión de Claude Code (Windows) — este documento es para dar contexto a otra sesión de Claude Code (Linux) sobre el mismo repositorio
**Estado general:** Empaquetado Windows funcional y verificado parcialmente. Ver sección "Pendientes" antes de dar por cerrado el ticket.

---

## 1. Objetivo de la sesión

Diagnosticar por qué no se lograba generar ni ejecutar un `.exe` de la aplicación (PyQt5, control de calidad en radioterapia) usando PyInstaller, dejar la máquina Windows lista, y documentar el procedimiento repetible de build.

---

## 2. Causa raíz encontrada (bloqueante, ya resuelta)

**El proyecto vivía dentro de una carpeta sincronizada activamente por OneDrive** (`C:\Users\<user>\Documents\...`, con "Backup" del Documents habilitado). Evidencia encontrada:

- Los archivos del repo tenían el atributo `ReparsePoint` (placeholders del Cloud Files API de OneDrive).
- Había un build previo (16/jun) que llegó hasta generar `build\RAD-QA\RAD-QA.exe` pero **nunca completó `dist\`** — el paso `COLLECT` de PyInstaller (que copia miles de archivos pequeños muy rápido) es exactamente el patrón que el motor de sincronización de OneDrive bloquea/compite por locks de archivo.
- Un segundo intento el mismo día de esta sesión murió al arrancar, sin poder limpiar los artefactos del intento anterior (`PermissionError` típico de archivo bloqueado por el proceso de OneDrive).

**Resolución:** el usuario removió la carpeta de Documents del backup activo de OneDrive (sin cambiar la ruta física — sigue siendo `C:\Users\...\Documents\...`, solo dejó de estar bajo sincronización activa). Verificado empíricamente:
- Atributo `Offline` = `False` en los archivos (ya no son placeholders de nube, están completamente hidratados en disco).
- `attrib.exe` ya no muestra marcadores de cloud (`P`/`U`).
- Se pudo borrar `build\` sin ningún error de permisos (antes fallaba).

**Nota para Linux:** este problema es específico de Windows + OneDrive. No debería replicarse en la sesión Linux, pero si el repo se sincroniza vía algún servicio de nube equivalente (Dropbox, Nextcloud client, etc.) montado sobre el path de trabajo, aplica la misma precaución: compilar fuera de cualquier carpeta con sincronización activa en tiempo real.

---

## 3. Dependencia faltante encontrada y corregida

`ui/paginasGuia/dialogs.py:967` y `:1009` usan `import pywintypes` e `import win32com.client` (automatización COM de Excel, función "Importar desde Excel/MCC"). **No estaba en `requirements.txt`.**

**Acción tomada:**
- Instalado `pywin32==312` en el venv Windows.
- Agregado `pywin32` a `requirements.txt` (línea nueva junto a `pyAesCrypt`/`keyboard`).
- Verificado que `import win32com.client, pywintypes` funciona en el venv.
- Verificado que la automatización COM real funciona en esta máquina: `win32com.client.Dispatch('Excel.Application')` conecta exitosamente a Excel 16.0 instalado localmente.

**Nota para Linux:** `win32com`/`pywintypes` son librerías **exclusivas de Windows** (dependen de COM/OLE de Win32). Los imports están hechos *dentro de los métodos* (`lista_a_diccionario`, `import_mcc`), no a nivel de módulo — esto significa que el archivo `dialogs.py` se puede importar sin problema en Linux (no rompe el arranque de la app), pero **la función de importar desde Excel nunca podrá funcionar en Linux** tal como está escrita (no hay Excel COM en Linux). Si se necesita esa función en Linux, hay que reescribirla con otra librería (p. ej. `openpyxl`, que ya está en `requirements.txt` y es multiplataforma) en vez de depender de Excel real vía COM. **No se tocó ese código esta sesión** — solo se diagnosticó.

---

## 4. Procedimiento de build verificado (Windows)

Fuente de verdad: **`RAD-QA.spec`** (no usar `build_exe.py` — quedó desincronizado; además invoca `pyinstaller` a secas desde el PATH sin garantizar que sea el del venv correcto).

```powershell
cd <repo>
.\.venv\Scripts\Activate.ps1
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
python -m PyInstaller RAD-QA.spec --noconfirm --clean
```

Resultado: `dist\RAD-QA\RAD-QA.exe` (modo `onedir`, ~36 MB el exe, ~457 MB la carpeta completa con `_internal\`).

**Advertencia inofensiva del build** (no requiere acción): `Library not found: could not resolve 'LIBPQ.dll', dependency of ...qsqlpsql.dll` — es el driver Qt SQL de PostgreSQL que PyQt5 empaqueta por defecto; la app usa `sqlite3` puro (stdlib), no `QtSql`, así que es ignorable.

**Regla de despliegue:** hay que distribuir la carpeta `dist\RAD-QA\` **completa**, no solo el `.exe` suelto. Debe copiarse a una ruta con permisos de escritura (no `Program Files`), porque la base de datos se crea/escribe junto al ejecutable.

---

## 5. Manejo de la base de datos (SQLite)

`data/ManejoDatos/conection.py:8-21` (función `ruta_base_datos()`) ya está corregido para resolver la ruta de forma robusta:
- **Empaquetado** (`sys.frozen == True`): `os.path.dirname(sys.executable)` → junto al `.exe`.
- **Desarrollo**: raíz del repo.

Esto es correcto y ya estaba resuelto antes de esta sesión (hay un comentario en el propio código explicando que antes usaba una ruta relativa que causaba bifurcación de datos según el cwd — bug ya corregido previamente, dejar así).

**No hay sistema de migraciones de esquema.** `createTable()` en `conection.py:80` usa `CREATE TABLE IF NOT EXISTS` únicamente; hay `ALTER TABLE` comentados en el código (líneas ~238-243, ~354) que evidencian que los cambios de esquema históricamente se aplicaron **a mano, una sola vez**, y no quedó automatizado. **Riesgo:** si el esquema de la base de Linux y el esquema que genera el código actual en Windows difieren, migrar el `.db` de un lado a otro puede producir errores `no such column`. Antes de mover datos entre entornos, comparar `sqlite3 BaseDatosQA.db ".schema"` en ambos lados.

**Portabilidad del archivo `.db` entre SO:** confirmada. Es un archivo binario SQLite estándar, sin nada específico de plataforma. El cifrado de campos sensibles (`data/ManejoDatos/encriptarInfo.py`) usa `pyAesCrypt` con una contraseña **estática hardcodeada en el código fuente** (`ENCRYPTION_PASSWORD = "Stark_3012"`, línea 8) — no depende de la máquina, así que los campos cifrados se descifran igual en cualquier SO donde corra el mismo código fuente. (Ver hallazgo de seguridad en sección 7.)

Para migrar datos reales de Linux → paquete Windows: copiar el archivo `.db` (binario, sin pasar por Git con conversión de texto) directamente a `dist\RAD-QA\BaseDatosQA.db`, con la app cerrada en ambos extremos y tras respaldar el `.db` destino existente.

---

## 6. Estado de las pruebas funcionales (checklist)

Probado y **confirmado funcionando** en el `.exe` empaquetado (Windows):
- [x] La app abre sin crashear (smoke test).
- [x] Login / flujo de autenticación.
- [x] Generación de reporte PDF.
- [x] **Exportar a Excel** (funciona).

**Pendiente de probar** (no confirmado, ni positivo ni negativo):
- [ ] Carga de carpeta DICOM (prueba mensual de TAC / CatPhan) — no se llegó a probar.
- [ ] **Importar desde Excel/MCC** (`import_mcc` en `dialogs.py`) — el usuario aclaró explícitamente que **no lo probó**, no hay evidencia de falla real todavía. Ver hallazgo de revisión de código en la sección 7 — es sospecha basada en lectura del código, no en un fallo observado.

---

## 7. Hallazgos de revisión de código (no confirmados en runtime, pendientes de investigar)

Estos se detectaron leyendo el código durante el diagnóstico de la dependencia `pywin32`, **no fueron reproducidos ejecutando la app** — quien retome esto debe validarlos antes de asumir que son bugs reales:

1. **`ui/paginasGuia/dialogs.py:1007-1074` (`import_mcc`) — implementación aparentemente incompleta.** El método abre 4 hojas de Excel (`ws`, `ws2`, `ws3`, `ws4`, líneas 1024-1027) pero solo tiene un bucle de lectura para la primera (`ws` → `df1`, líneas 1042-1047). Las líneas 1049-1058 están en blanco donde se esperarían los bucles equivalentes para `ws2/ws3/ws4` → `df2/df3/df4`. Como consecuencia, `dict2`, `dict3`, `dict4` (línea 1063-1065) siempre quedan vacíos, y solo se llama `self.mapear_excel_a_ui(dict1)` (línea 1074) — los datos de las hojas 5, 6 y 7 nunca llegan a la interfaz. **Si al probar la importación faltan datos de esas hojas, esta es la causa.**
2. **Mismo método, línea 1016:** si el usuario cancela el diálogo de selección de archivo (`QFileDialog.getOpenFileName` retorna cadena vacía), la variable `ruta` nunca se asigna (solo se asigna dentro del `if archivo:` de la línea 1012) y `self.ruta = ruta` en la línea 1016 lanzaría `UnboundLocalError`. El `try/except` de las líneas 1010-1015 no lo cubre (el except solo captura errores del propio diálogo, no de la falta de asignación posterior).
3. **Sin manejo de errores alrededor de la apertura del Excel** (línea 1022 en adelante): si el archivo seleccionado no es un `.xlsx` real con al menos 7 hojas (por ejemplo, si el usuario selecciona un `.mcc` de texto plano en lugar de un Excel — el propio mensaje de error de la línea 1015 dice "formato MCC", lo cual es confuso porque el diálogo filtra por Excel), `wb.Sheets(7)` u otras líneas lanzarán una excepción COM sin captura, sin mensaje amigable para el usuario.

**No se corrigió nada de esto todavía** — se dejó pendiente a solicitud del usuario, quien primero quiere probarlo antes de decidir si se arregla.

---

## 8. Hallazgo de seguridad (no bloqueante, informativo)

`data/ManejoDatos/encriptarInfo.py:8`: `ENCRYPTION_PASSWORD = "Stark_3012"` — contraseña de cifrado AES hardcodeada en texto plano en el código fuente. Quedará embebida tal cual dentro del `.exe` compilado (y visible para cualquiera con el código fuente, como esta sesión Linux). Si los datos cifrados en la base de datos son sensibles (parece que sí, dado que existe cifrado deliberado), vale la pena evaluar mover esta clave a una variable de entorno o a un mecanismo de gestión de secretos. **No se tocó esta sesión**, solo se deja registrado.

---

## 9. Resumen ejecutable de lo que falta / próximos pasos sugeridos

1. Probar la carga de DICOM en el `.exe` empaquetado (checklist pendiente, sección 6).
2. Probar `import_mcc` con un archivo real y contrastar contra los 3 hallazgos de la sección 7 antes de tocar código.
3. Si se confirma el hallazgo #1 de la sección 7, completar los bucles faltantes para `df2/df3/df4` y extender `mapear_excel_a_ui` (o el mapeo equivalente) para usarlos.
4. Si se van a migrar datos reales desde el entorno Linux, comparar esquemas de BD antes de copiar el `.db` (sección 5).
5. Evaluar si la función de importar Excel necesita una reescritura multiplataforma (openpyxl en vez de `win32com`) si el plan es que la app corra también en Linux más allá del build de Windows.
6. Opcional: revisar el hallazgo de seguridad de la clave hardcodeada (sección 8).

---

## 10. Auditoría funcional (Windows) — sesión 2026-07-07

**Método:** aplicación ejecutada desde código fuente (`python main.py`, venv `.venv`, consola visible) sobre una **copia real de la base de datos de producción** colocada en la raíz del workspace padre (ver nota 10.6.1). Cada síntoma de consola se verificó contra el código fuente antes de concluir; hubo dos rondas (exploración libre + recolección dirigida de evidencia, incluida inspección manual de la BD en VS Code por parte del evaluador). **No se modificó ningún archivo del repo durante la auditoría.** Esta sección actualiza el estado de las secciones 6 y 7.

### 10.1 Resumen ejecutivo

| # | Hallazgo | Estado | Gravedad |
|---|----------|--------|----------|
| F1 | Typo SQL `FOREING KEY` impide crear `angulos_entre_lineas_starshot`; error en cada arranque, tragado por un `except` genérico | Confirmado (runtime + código + BD) | **Alta** |
| F2 | Reporte PDF de sistema de imágenes 100% inoperante: `NameError: name 'P'` determinista | Confirmado (runtime + código) | **Alta** |
| F3 | El historial diario iX renderiza solo 2 de N registros; la BD sí los contiene todos | Confirmado (runtime + BD + código) | **Alta** |
| F4 | Análisis PicketFence muere: `'PicketFence' object has no attribute 'image'`; pylinac sin fijar en requirements | Confirmado (runtime); causa = hipótesis | **Alta** |
| F5 | `import_mcc` inviable en su forma actual: 3 defectos + fuga de procesos Excel huérfanos | Confirmado (runtime, 3 casos) | Media |
| F6 | `resultados_texto` cambia de QLabel a QTableWidget en runtime; rompe flujos del TAC según el orden de uso | Confirmado (runtime + código) | Media |
| F7 | Halcyon: ingesta automática desde ruta de red del hospital; reimportar una fecha existente se descarta en silencio | Confirmado (código) | Media |
| F8 | La escritura diaria (`add_info`) SÍ funciona — la percepción de "no guarda" la causa F3 | Confirmado (runtime + BD) | — (aclaración) |
| F9 | Menores: rutas relativas al cwd, validaciones ruidosas, consulta F1 vacía, widgets MLC ausentes, encoding | Parcial | Baja-Media |

### 10.2 Hallazgos detallados

**F1 — `FOREING KEY` (typo) en `crearTablasMLCs`.**
- Evidencia runtime (cada arranque): `sqlite3.OperationalError: near "ref": syntax error` en `conection.py:1197`.
- Causa localizada: `data/ManejoDatos/conection.py:1174` — `FOREING KEY (ref) REFERENCES ...` en el `CREATE TABLE` de `angulos_entre_lineas_starshot`. SQLite interpreta `FOREING` como nombre de columna y revienta en `(ref)`.
- Alcance verificado contra la BD: esa tabla es la **última** de la lista del bucle (línea 1194); las otras 8 tablas MLC/Starshot sí se crean. En la BD inspeccionada existen todas **menos** `angulos_entre_lineas_starshot`.
- Agravante: el `try/except` de `__init_connection` (líneas 49-51) imprime y continúa → en el exe `--noconsole` el error es invisible. Cualquier INSERT futuro a esa tabla fallará con `no such table`.

**F2 — `NameError: name 'P'` en el reporte PDF de sistema de imágenes.**
- Evidencia runtime: reproducido en cada intento de generar el reporte (2 sesiones).
- Causa localizada: `models/PDF/pdf.py:557` usa los helpers `P()`/`Pl()`, que solo existen como **funciones anidadas locales** dentro de otras dos funciones del mismo archivo (líneas 1262/1271 y 1784/1792) — fuera de alcance en la línea 557.
- Hipótesis de origen: copy-paste de la sección "Interpretación de métricas" desde el generador del reporte **Starshot** hacia `generar_reporte_pdf_multitabla_mensual` sin trasladar los helpers. Doble evidencia: el texto pegado describe "Radio de convergencia… criterio de aceptación del ensayo Starshot" (líneas 563-577), contenido que no corresponde al reporte de imágenes de TAC donde quedó insertado.
- Impacto: el fallo es **determinista** — no depende de los datos; el reporte de imágenes no puede generarse bajo ninguna condición.

**F3 — Historial diario iX: la vista pierde registros (la BD no).**
- Evidencia empírica (evaluador): la tabla de historial en la app muestra únicamente los registros id **363 y 358**, mientras la BD abierta en VS Code contiene el historial completo **más ~8 registros nuevos** creados por el administrador durante las pruebas. Las tablas del 600 y de equipos se ven completas y su columna 0 (ID) coincide con la BD.
- Causa localizada: `data/GraficasyTablas/tablas.py:47-50` — dentro del bucle **de columnas**, cuando una columna de dosis viene vacía/`None`, hace `row += 1; continue`. Eso desplaza las celdas restantes del registro a la fila visual siguiente (que no fue insertada) y desalinea el render de todos los registros posteriores. Con `ORDER BY date DESC` (línea 11), los registros nuevos de prueba —que suelen traer dosis vacías— van primero y rompen el render del resto del historial.
- Riesgo derivado (edición): `cargarDatosEditados` (`ui/paginasControles/PruebasDiarias/PruebasDiarias.py:709` y `:720`) toma el id de la **columna 0 de la fila visual** y ejecuta `UPDATE ... WHERE id = ?`. Un UPDATE cuyo WHERE no coincide con ninguna fila **no es error en SQL**: reporta "Registro actualizado correctamente" habiendo cambiado 0 filas. Combinado con la desalineación, una edición puede aplicarse al registro equivocado o a ninguno, con mensaje de éxito.

**F4 — PicketFence roto: incompatibilidad de versión de pylinac (hipótesis principal).**
- Evidencia runtime: `[Starshot] Ejecutando análisis...` → `Boton Ejecutar analisis activado` → `'PicketFence' object has no attribute 'image'`.
- Hecho verificado: `requirements.txt` declara `pylinac>=3.0.0` (**sin fijar**); ambos venvs Windows (copia vieja y LW) tienen instalado **pylinac 3.45.0**.
- Hipótesis: el código MLC/PicketFence fue escrito contra una versión anterior de la API de pylinac (probablemente la del entorno de desarrollo Linux) o accede al atributo antes del análisis. **La sesión Linux debe comparar su `pip show pylinac` contra 3.45.0** antes de tocar ese código.
- Consecuencia colateral: la evidencia pendiente de F1 (forzar el `no such table` de Starshot) no pudo recolectarse porque el análisis muere antes.
- Nota UI: el evaluador no encontró un botón visible para lanzar el análisis Starshot en su recorrido, aunque la consola registró "Boton Ejecutar analisis activado" — revisar visibilidad/ubicación del control en la página mensual iX.

**F5 — `import_mcc`: prototipo inviable en su forma actual.** (Actualiza los hallazgos 7.2 y 7.3: **ambos confirmados en runtime**.)
- Caso A (cancelar el diálogo): `UnboundLocalError` en `dialogs.py:1016` — confirmado 3 veces. La app no crashea porque PyQt5 imprime las excepciones de slots y continúa (en el exe sin consola: invisible).
- Caso B (PDF cualquiera): `com_error` DISP_E_BADINDEX en `wb.Sheets(4)` (`dialogs.py:1024`).
- Caso C (**archivo .mcc real**): mismo BADINDEX — Excel abre el .mcc (texto plano) como libro de **una sola hoja**, así que el diseño actual (`Sheets(4..7)`) **no puede funcionar jamás con archivos .mcc reales**; requiere un .xlsx de ≥7 hojas. El nombre de la función es un misnomer.
- Contribuye: filtro del diálogo malformado (`"Archivos Excel ; Todos los archivos (*)"` — sin patrón `*.xlsx` ni separador `;;`) → no filtra nada.
- Colateral: cada fallo posterior a `Workbooks.Open` deja un proceso `EXCEL.EXE` huérfano con el archivo bloqueado (`wb.Close()`/`excel.Quit()` inalcanzables tras la excepción). Tras la sesión de pruebas puede haber varios acumulados.
- El camino feliz (leer hojas 4-7 de un xlsx válido) sigue **sin probarse**; por código, solo la hoja 4 está implementada (hallazgo 7.1 vigente: bucles de `ws2-ws4` ausentes en `dialogs.py:1049-1058`).

**F6 — Widget con identidad cambiante en TAC mensual.**
- Evidencia runtime: `AttributeError: 'QTableWidget' object has no attribute 'setText'` en `tac_mensual.py:1438` y `:2096`.
- Causa localizada: `resultados_texto` nace como `QLabel` (`tac_mensual.py:2305`) y `reemplazar_resultados_texto_con_tabla` lo **reasigna** a un `QTableWidget` (`:1490`). Tras el primer análisis que hace el reemplazo, toda ruta que aún asuma QLabel (`setText` en 1438/2064/2096) revienta. Bug dependiente del **orden de acciones** — por eso parece intermitente.
- Hipótesis de origen: refactor incompleto (migración de resultados de texto plano a tablas).
- Nota: el guardado CatPhan en sí **funciona** (sesión 39 guardada repetidamente, una vez por corte procesado).

**F7 — Halcyon: dependencia de red y descarte silencioso.**
- `data/ManejoDatos/obtenerDatosHalcyon.py:58-78` (`addInfo`): busca **automáticamente** la carpeta MPC del día en la ruta fija `\\VARIANDB\Va_Transfer\TDS\HAL1161\MPCChecks`, elige la más reciente por hora y lee `Results.csv`. Fuera de la red del hospital esto siempre falla ("Error al listar carpetas") — las pruebas de Halcyon **no pueden ejecutarse en una máquina doméstica**; no es un bug del build sino una dependencia de entorno no documentada (hasta ahora).
- `obtenerDatosHalcyon.py:47-48` (`addInfo2`, variante manual): el comentario dice "Si ya existe, actualizar" pero el código **solo imprime** `"Ya existe la fecha"` — reimportar un día ya registrado se descarta silenciosamente, sin aviso en UI.
- Extras del mismo archivo: escribe `infoWidgets.csv` con ruta relativa al cwd (línea 36) y extrae la fecha del **nombre de la carpeta** sin validar el match (líneas 21-23 → `AttributeError` si la ruta no contiene `yyyy-mm-dd`).

**F8 — La escritura diaria funciona (corrección a la conclusión preliminar de la sesión).**
- Evidencia runtime (2ª ronda): al presionar guardar aparecen `entro a la funcion de ordenacion` → `Entra a la función add_info en load.py con tabla: aceleradorlineal_ix` → `Columnas detectadas [...]` sin errores.
- Código: `add_info` usa la fecha del `date_box` y hace `DELETE` + `INSERT` **por esa fecha** (`data/ManejoDatos/load.py:54` y `:110-114`) → guardar en días pasados sí escribe.
- Evidencia BD: los ~8 registros nuevos del administrador **están** en `aceleradorlineal_ix` (verificado por el evaluador en VS Code).
- Conclusión corregida: la impresión de "cargar días pasados no modifica la BD / las tendencias no cambian" era una **ilusión creada por F3** (la vista oculta lo escrito). Pendiente: re-verificar la gráfica de tendencia contra los datos nuevos — lee la BD por SQL directo (`graficarvstiempo`), debería reflejarlos.
- Puntos de aborto legítimos que sí existen antes de escribir (con popup, no silenciosos): usuario logueado inexistente en `users` (`load.py:57-60`) y campos no numéricos/vacíos (`load.py:76-87`).

**F9 — Hallazgos menores / deuda de higiene.**
- `dosimetria.json` se lee/escribe con **ruta relativa al cwd** (`Error al cargar datos: No such file...` en cada apertura de la mensual iX) — misma familia del bug histórico de `BaseDatosQA.db`; en el exe congelado el cwd puede variar → riesgo de datos bifurcados.
- Calculadora de dosis: el cálculo de kQ0 se dispara al abrir con campos vacíos → `could not convert string to float: ''` (ruido en cada apertura; falta validación/lazy trigger).
- Consulta de físicos F1 devuelve **siempre** `[]` mientras F2 sí se llena (IDs 3/6/9/10 según pantalla) — hipótesis: filtro de rol/flag en la query de F1 que no coincide con los datos actuales de `users`.
- `⚠️ Widgets MLC no encontrados` y `Widget 'ln_dosis_ref_...' no encontrado`: la UI se genera desde hojas Excel (`preguntas_mensu_*`); hay desfase entre esas hojas y los widgets que el código espera (en el 600 parte es esperable: máquina de 1 energía vs código genérico de 6 energías).
- Print de depuración a nivel de módulo `0.30000000000000004` en cada arranque; tabla `tamaño_pixel` con `ñ` en el nombre (la consola la muestra corrupta — riesgo de encoding entre entornos/herramientas).
- `Advertencia: El archivo RS...dcm no contiene datos de píxeles`: es un RTSTRUCT (por estándar DICOM no trae imagen); el cargador no filtra por Modality/SOPClass antes de intentar leer `pixel_array`. Inofensivo pero ruidoso.

### 10.3 Estado de las conclusiones del evaluador

1. "El import MCC no está terminado" → **Confirmada y ampliada** (F5: además, inviable por diseño para archivos .mcc reales).
2. "Con una BD con físicos sí se guarda el análisis DICOM del TAC; el reporte falla con `name 'P'`" → **Confirmada**; el fallo del reporte es determinista (F2), no depende de los datos.
3. "Hay un error interno silencioso al cancelar la carga; la app no crashea" → **Confirmada**, con explicación: PyQt5 imprime las excepciones de slots y continúa; en el exe sin consola todo el catálogo de errores de esta auditoría es invisible para el usuario final.
4. "La aplicación busca automáticamente el archivo para el reporte de Halcyon" → **Confirmada** (F7: ruta de red fija del hospital).
5. "No se pueden modificar las gráficas de tendencia / cargar días pasados no modifica la BD" → **Corregida por la evidencia**: la escritura SÍ llega a la BD (F8); lo defectuoso es la vista del historial (F3) y potencialmente la edición por id visual. La gráfica queda pendiente de re-verificación con los datos nuevos.

### 10.4 Actualización del checklist de la sección 6

- [x] **Importar desde Excel/MCC** — PROBADO: falla en los 3 casos (F5). Hallazgos 7.2 y 7.3 confirmados en runtime; 7.1 sigue pendiente de camino feliz.
- [x] **Carga DICOM TAC (CatPhan)** — funciona y guarda (sesión 39); el reporte PDF está bloqueado por F2; dos `AttributeError` de F6 en flujos colaterales.
- [ ] **Starshot / PicketFence** — bloqueado por F4; la prueba del `no such table` de F1 sigue pendiente.

### 10.5 Evidencia aún pendiente de recolectar

1. Camino feliz de `import_mcc` con un `.xlsx` de ≥7 hojas (validar hallazgo 7.1: solo la hoja 4 llega a la UI).
2. Gráfica de tendencia contra los ~8 registros nuevos (verificar directamente sobre la gráfica, que lee por SQL y no pasa por la vista rota de F3).
3. Con F4 resuelto, confirmar el `no such table: angulos_entre_lineas_starshot` al guardar un Starshot (cierra F1).
4. Procesos `EXCEL.EXE` huérfanos tras los fallos de import_mcc (Administrador de tareas).

### 10.6 Notas de entorno para la sesión Linux

1. **Ubicación de la BD en desarrollo:** `ruta_base_datos()` ancla el `.db` **tres niveles arriba** de `data/ManejoDatos/` → cuando se corre desde fuente dentro de este workspace, eso es la **raíz del workspace padre** (`AUNA_Codigos_2026/BaseDatosQA.db`), no la raíz del repo. En el exe congelado: junto al ejecutable.
2. **pylinac no está fijado** (`>=3.0.0`); ambos venvs Windows resolvieron a 3.45.0. Comparar con la versión del entorno Linux antes de tocar el código MLC/PicketFence (F4).
3. `win32com`/Excel COM (import_mcc) es Windows-only (ya advertido en sección 3); cualquier rediseño multiplataforma implicaría otra librería (p. ej. `openpyxl`, ya presente en requirements).
4. Las rutas de red `\\VARIANDB\...` (ingesta Halcyon en `obtenerDatosHalcyon.py`, respaldo en `mainpages.hacer_respaldo`) solo existen en la red del hospital.

---

## 11. Actualización de sesión — 2026-07-08

**Contexto:** la carpeta activa del proyecto cambió de nombre. La copia auditada en la sección 10 (`Codigo_radqa_LW_7-06-2026`) fue renombrada a `Codigo_radqa_LW_7-06-2026(Windows_audited)` y quedó congelada como referencia. El trabajo continúa en una copia nueva, **`Codigo_radqa_2026-07-08`**, que a diferencia de las anteriores **sí tiene `.git`** (checkout real del repo) y ya trae varias correcciones integradas, presumiblemente desde la sesión Linux. Se verificó el entorno (venv Python 3.11.0 aislado correctamente, `pip check` sin conflictos, 18/18 librerías clave importan sin error) antes de continuar.

### 11.1 Correcciones ya integradas en este checkout (confirmadas, no aplicadas por esta sesión Windows)

- **Bug de ruta de la BD (mencionado como hipótesis en 10.6.1) — ya corregido.** `ruta_datos()` en `data/ManejoDatos/conection.py:8-19` ahora resuelve así: congelado → `os.path.dirname(sys.executable)`; desarrollo → `os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))`, es decir **2 niveles arriba** desde `data/ManejoDatos/` = raíz del proyecto. Ya **no** ancla 3 niveles arriba (raíz del workspace padre). El propio docstring de la función lo documenta explícitamente como corrección deliberada de un bug histórico de bifurcación de datos por cwd.
- **`requirements.txt` — `pylinac` ahora fijado a `==3.45.0`** (antes `>=3.0.0`, hallazgo F4 de la sección 10). Esto no corrige el `AttributeError` de PicketFence en sí, pero elimina el riesgo de que una instalación futura resuelva a una versión distinta de la que se está depurando. `pywin32` ahora está condicionado a `sys_platform == "win32"` (ya no se intentará instalar en Linux).
- **Dependencias nuevas: `xlrd==2.0.2` y `msoffcrypto-tool==6.0.0`**, con un comentario en `requirements.txt` que referencia una "Fase D3": leer las hojas TRS-398 del OIEA **sin pasar por Excel/win32com** (los `.xls` oficiales vienen cifrados con la contraseña por defecto de Excel `VelvetSweatshop`, formato BIFF8 → `msoffcrypto` descifra, `xlrd` lee). Esto ataca directamente el problema de fondo del hallazgo **F5** (import_mcc dependía de automatización COM de Excel, inviable con archivos `.mcc` reales). Hay carpetas nuevas en el repo (`mcc_PTW_read/`, `services/`) que sugieren que este rediseño está en curso. **No se validó funcionalmente esta sesión** — solo se confirmó que las dependencias están declaradas e instaladas; queda pendiente para quien continúe revisar si ya reemplaza a `import_mcc` o convive con él.

### 11.2 Incidente operativo: "la BD no carga" — causa real (no es un bug de código)

El usuario reportó que, tras colocar manualmente una copia de la BD de producción (33 402 880 bytes, ~cientos de registros reales) tanto en la carpeta del build (`dist\RAD-QA\`) como "a la altura de la carpeta del proyecto", la aplicación seguía sin mostrar los datos al ejecutar `python main.py`. Diagnóstico:

1. **Dos rutas de resolución completamente independientes.** Con el fix de 11.1 ya aplicado, `python main.py` (modo desarrollo) busca en `Codigo_radqa_2026-07-08\BaseDatosQA.db`, mientras que `RAD-QA.exe` (modo congelado) busca en `dist\RAD-QA\BaseDatosQA.db`. El código no vincula ni sincroniza estas dos rutas entre sí de ninguna forma.
2. **Comportamiento no documentado: auto-creación silenciosa de una BD vacía.** Si `Conexion.__init_connection` (mismo archivo, `try/except` de las líneas ~37-51, ya señalado en la sección 10) no encuentra el archivo en la ruta resuelta, **no lanza error ni avisa al usuario**: crea un `BaseDatosQA.db` nuevo con el esquema completo y un usuario admin por defecto. Esto fue lo que se encontró en `Codigo_radqa_2026-07-08\BaseDatosQA.db` (352 256 bytes, `users → 1 fila`) antes de la intervención — no era el archivo del usuario dañado, era uno generado por la propia app en un arranque previo en el que no había nada ahí.
3. **Causa inmediata verificada empíricamente:** al intentar copiar el archivo real desde su ubicación original (raíz del workspace padre) hacia la raíz del proyecto, ese archivo original **ya no existía** — se confirmó que la operación previa del usuario había sido **mover (cortar/pegar), no copiar**, consistente con el comportamiento por defecto del Explorador de Windows al arrastrar archivos dentro del mismo disco. Resultado: el archivo real terminó existiendo en un solo destino (`dist\RAD-QA\`) en vez de en los dos necesarios.
4. **Resolución:** se copió (`Copy-Item -Force`, sin mover) el archivo real desde `dist\RAD-QA\BaseDatosQA.db` hacia `Codigo_radqa_2026-07-08\BaseDatosQA.db`. Verificado con conteo de filas por tabla (`users → 7`, `aceleradorlineal_ix → 330`, `controles → 29`) que coincide con la BD de producción real. Ambas rutas quedaron sincronizadas manualmente; el código sigue sin vincularlas.

**Hipótesis/observación para quien continúe (no se aplicó ningún cambio de código, solo se documenta):** la auto-creación silenciosa de una BD vacía (punto 2) es la raíz de por qué este tipo de incidente es fácil de malinterpretar como "no se guardan los datos" o "la BD no se vincula" — no hay ningún mensaje, log visible al usuario ni distinción entre "abrí tu base de datos existente" y "no encontré nada, creé una nueva". Vale la pena evaluar agregar un aviso (UI o al menos en el log de consola) cuando esto ocurre.

### 11.3 Nueva evidencia de consola recolectada (arranque limpio, `python main.py`, módulo iX mensual)

Confirma/actualiza hallazgos ya registrados en la sección 10, sección F9, sin hallazgos nuevos de gravedad alta:

- **`dosimetria.json` — el "bug de ruta relativa al cwd" de F9 queda desactualizado/cerrado en este checkout.** El error observado (`Error al cargar datos: [Errno 2] No such file or directory: '...\Codigo_radqa_2026-07-08\dosimetria.json'`) ya **no** es cwd-relativo: `ui/paginasControles/PruebasMensuales/ix_mensual.py:361` hace `filename = ruta_datos(filename)`, con un comentario explícito ("Anclar el JSON de campos junto a la BD (independiente del cwd)") que confirma que esto ya fue corregido usando el mismo helper que ancla `BaseDatosQA.db`. Lo único que ocurre es que el archivo simplemente **no existe todavía** en esa ruta (es un caché/config opcional de primer uso); el `try/except` de la línea 462 lo captura sin romper la app. **No es un bug — es esperado en un entorno nuevo sin ese archivo.**
- **`⚠️ Widgets MLC no encontrados - revisar creación desde Excel`** — se reproduce de nuevo, consistente con el hallazgo ya registrado en F9 sobre desfase entre las hojas Excel `preguntas_mensu_*` y los widgets que el código espera.
- Ruido de depuración masivo confirmado otra vez: decenas de líneas `ANTES ADD: <widget> False` / `CREADO: <widget>` por cada carga de página, más el print de módulo `0.30000000000000004`. Cosmético, ya registrado en F9, sin impacto funcional.


# Carga manual de la revision de windows del 2026-07-09.

Copia manual mia de mis pruebas en la sesion de windows el dia 9-Jul-2026, anotaciones de la terminal y hallazgos:

- Para un mismo modelo de camara hay varias series pero muchas corresponden al mismo valor numerico de serie, por ejemplo 1825 o 1822 pero hay varios de estos y algunos contienen factores de calibracion diferentes que cargan con valores particulares de temperatura, presion y humedad, estos son valores que se van actualizando a medida que se hacen calibraciones? Salen de tablas de la IAEA o similares? Porque no tienen notas que indiquen cual es cual, pues el problema es que unicamente sirve para seleccionar el valor adecuado de factor de calibracion, porque los valores de temperatura, presion y humedad se pueden modificar directamente en la app.

- Falta mucho desarrollo en el pdf que se reporta, como darle un uso real a la columna de evaluacion, muchas veces sale vacio. Faltan unidades en los reportes.

- No parece estarse importando el archivo mcc, ni siquiera para el 600 que tiene una sola energia, no aparecen valores en las casillas por lo cual no se carga ni registra nada, a no ser de que permanezcan invisibles o si se guarden al final luego de rellenar todo lo de informacion mensual pero de primera vista no parece estar cargando y lo de la terminal puede tener evidencia de esto. Para ninguno de los campos, planicidad, simetria o PDD para ninguno de los aceleradores.

- No se aprecia ningun cambio al seleccionar una version diferente del protocolo TRS 398, sugiero eliminar la palabra "provisional".

- Sale el mensaje de llenar manualmente el kq pero no hay ninguna casilla habilitada, claramente cuando se selecciona una camara de la que no hay informacion.

- El documento pdf de la TRS 398 menos reciente de los que tenemos dice 2005 no 2000.

- 



(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-09> python main.py
0.30000000000000004
admin2025
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
PruebaImagenesHC  __init__ called
Halcyon
ENTRANDO A PRUEBA IMAGENES HC
control de Halcyon
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000002285B1885D0>, id_f1_num usado: Administrador
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
Entra a imagenes HC
Equipo seleccionado para reporte 
Halcyon
Equipo seleccionado para reporte 
Halcyon
Equipo seleccionado para reporte 
Halcyon
Equipo seleccionado para reporte 
Halcyon
Equipo seleccionado para reporte 
Halcyon
Equipo seleccionado para reporte 
Halcyon
PruebaImagenesHC received ref: None
PruebaImagenesIX  __init__ called
Halcyon
ENTRANDO A PRUEBA IMAGENES HC
control de Halcyon
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000002285B1885D0>, id_f1_num usado: Administrador
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
Usted está aquí mostrar controles HC anual 
[(42, '07/2026', 'Halcyon', 'Anual', 0)]
Equipo seleccionado para reporte 
Halcyon
PruebaImagenesHC received ref: None
42
Halcyon
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000002285B1885D0>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
Datos tabla principal obtenidos: {'equipo': 'Halcyon', 'fecha': '07/2026', 'user_id': 'Javier Castillo', 'user_id_f2': 'Cristian Castellanos'}
Buscando información del usuario principal: Javier Castillo
Buscando información del usuario 2 con ID: Cristian Castellanos
Información de usuario obtenida: {'usuario1': {'usuario': 'Javier Castillo', 'rol': 'Físico Médico', 'firma_path': 'C:\\Users\\parra\\AppData\\Local\\Temp\\tmpik1snpog.png'}, 'usuario2': {'usuario': 'Cristian Castellanos', 'rol': 'Físico Médico', 'firma_path': 'C:\\Users\\parra\\AppData\\Local\\Temp\\tmpneug2i5a.png'}}
Generando reporte de Halcyon sin sistema de imágenes...
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
user_id_f2 antes de create_control: 6
Entrando a crear control
Halcyon
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
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
ANTES ADD: ln_observaciones_dosi False
CREADO: ln_observaciones_dosi
ANTES ADD: ln_tolerance_mlc False
CREADO: ln_tolerance_mlc
ANTES ADD: ln_action_tolerance False
CREADO: ln_action_tolerance
DF LINES: 
['val_teo_6mv', 'ln_dosis_ref_cgy_um_6mv', 'ln_discrepancia_dosis_6mv', 'ln_tolerancia_dosis', 'ln_calidad_pdd20_10_6mv', 'ln_discrepancia_calidad_6mv', 'ln_tolerancia_calidad', 'ln_simetria_inplane_6mv', 'ln_simetria_crossplane_6mv', 'ln_tolerancia_simetria', 'ln_observaciones_dosi']
DF LINES: 
['ln_action_tolerance']
Widget 'ln_dosis_ref_cgy_um_15mv' no encontrado
Widget 'ln_dosis_ref_cgy_um_6mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_9mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_12mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_15mev' no encontrado
Datos salvados en JSON.
Tabla HC_indicadores_brazo guardada correctamente
Tabla HC_indicadores_colimador guardada correctamente
Dialog llamado desde: PruebaMensualHc
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
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-09\ui\paginasGuia\dialogs.py", line 1034, in import_mcc
    ws = wb.Sheets(4)
         ^^^^^^^^^^^^
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-09\.venv\Lib\site-packages\win32com\client\dynamic.py", line 214, in __call__
    self._oleobj_.Invoke(*allArgs), self._olerepr_.defaultDispatchName, None
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
pywintypes.com_error: (-2147352567, 'Exception occurred.', (0, None, None, None, 0, -2147352565), None)
Data saved successfully for date: 09/07/2026
Datos tabla principal obtenidos: {'equipo': 'Halcyon', 'fecha': '07/2026', 'user_id': 'Cristian Castellanos', 'user_id_f2': ' Andres David Loaiza Baena'}
Buscando información del usuario principal: Cristian Castellanos
Buscando información del usuario 2 con ID:  Andres David Loaiza Baena
Información de usuario obtenida: {'usuario1': {'usuario': 'Cristian Castellanos', 'rol': 'Físico Médico', 'firma_path': 'C:\\Users\\parra\\AppData\\Local\\Temp\\tmp4clpfakc.png'}, 'usuario2': {'usuario': ' Andres David Loaiza Baena', 'rol': 'Físico Médico', 'firma_path': 'C:\\Users\\parra\\AppData\\Local\\Temp\\tmpp9i3z2uz.png'}}
Generando reporte de Halcyon sin sistema de imágenes...
Dialog llamado desde: PruebaMensualHc
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-09\ui\paginasGuia\dialogs.py", line 1034, in import_mcc
    ws = wb.Sheets(4)
         ^^^^^^^^^^^^
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-09\.venv\Lib\site-packages\win32com\client\dynamic.py", line 214, in __call__
    self._oleobj_.Invoke(*allArgs), self._olerepr_.defaultDispatchName, None
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
pywintypes.com_error: (-2147352567, 'Exception occurred.', (0, None, None, None, 0, -2147352565), None)
Data saved successfully for date: 09/07/2026
No hay datos para esta referencia.
No hay datos para esta referencia.
No hay datos para esta referencia.
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
iniGUI: 0.038s
load table: 0.111s
asignar_encabezados: 0.112s
button_click: 0.112s
Clinac 600
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000002285B1885D0>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
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
<PyQt5.QtWidgets.QGridLayout object at 0x000002286BF4E200>
<PyQt5.QtWidgets.QGridLayout object at 0x000002286BF4DB40>
<PyQt5.QtWidgets.QGridLayout object at 0x000002286BF4E320>
<PyQt5.QtWidgets.QGridLayout object at 0x000002286BF4E290>
<PyQt5.QtWidgets.QGridLayout object at 0x000002286BF4E3B0>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
DF LINES: 
['val_teo_6mv', 'ln_dosis_ref_cgy_um_6mv', 'ln_discrepancia_dosis_6mv', 'ln_tolerancia_dosis', 'ln_calidad_pdd20_10_6mv', 'ln_discrepancia_calidad_6mv', 'ln_tolerancia_calidad', 'ln_simetria_inplane_6mv', 'ln_simetria_crossplane_6mv', 'ln_tolerancia_simetria', 'ln_planicidad_inplane_6mv', 'ln_planicidad_crossplane_6mv', 'ln_tolerancia_planicidad', 'ln_observaciones_dosi']
Widget 'ln_dosis_ref_cgy_um_15mv' no encontrado
Widget 'ln_dosis_ref_cgy_um_6mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_9mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_12mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_15mev' no encontrado
Dialog llamado desde: PruebaMensual600
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
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-09\ui\paginasGuia\dialogs.py", line 1034, in import_mcc
    ws = wb.Sheets(4)
         ^^^^^^^^^^^^
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-09\.venv\Lib\site-packages\win32com\client\dynamic.py", line 214, in __call__
    self._oleobj_.Invoke(*allArgs), self._olerepr_.defaultDispatchName, None
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
pywintypes.com_error: (-2147352567, 'Exception occurred.', (0, None, None, None, 0, -2147352565), None)
Traceback (most recent call last):
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-09\ui\paginasGuia\dialogs.py", line 1034, in import_mcc
    ws = wb.Sheets(4)
         ^^^^^^^^^^^^
  File "C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-09\.venv\Lib\site-packages\win32com\client\dynamic.py", line 214, in __call__
    self._oleobj_.Invoke(*allArgs), self._olerepr_.defaultDispatchName, None
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
pywintypes.com_error: (-2147352567, 'Exception occurred.', (0, None, None, None, 0, -2147352565), None)
Data saved successfully for date: 09/07/2026

Subiendo datos para dosimetriaMen

▥ Columnas detectadas: ['ref', 'val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

ADVERTENCIA: columna 'val_teo_dosis' no tiene widget correspondiente → None
ADVERTENCIA: columna 'val_teo_calidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'energia' no tiene widget correspondiente → None
Datos guardados correctamente.
Actualizando tabla de controles mensuales para Clinac 600
Datos subidos correctamente
Datos guardados en C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-09\dosimetria.json

Subiendo datos para dosimetriaMen

▥ Columnas detectadas: ['ref', 'val_teo_dosis', 'val_teo_calidad', 'dosis_ref_cgy_um', 'discrepancia_dosis', 'tolerancia_dosis', 'calidad_pdd20_10', 'discrepancia_calidad', 'tolerancia_calidad', 'simetria_inplane', 'simetria_crossplane', 'tolerancia_simetria', 'planicidad_inplane', 'planicidad_crossplane', 'tolerancia_planicidad', 'observaciones_dosi', 'energia'] para dosimetriaMen

ADVERTENCIA: columna 'val_teo_dosis' no tiene widget correspondiente → None
ADVERTENCIA: columna 'val_teo_calidad' no tiene widget correspondiente → None
ADVERTENCIA: columna 'energia' no tiene widget correspondiente → None
Datos guardados correctamente.
Actualizando tabla de controles mensuales para Clinac 600
Datos subidos correctamente
No hay datos para esta referencia.
No hay datos para esta referencia.
No hay datos para esta referencia.
No hay datos para esta referencia.
No hay datos para esta referencia.
Guardando datos o haciendo respaldo...


# Carga manual de la revision en la mañana del 2026-07-10

Anotaciones:

- Cargar con la serie el valor de la humedad de la calibracion si existe, y ajustar estos valores a 1 unidad decimal.

- Dentro de la calculadora de dosis la opcion de comparar con el excel funcionan bien.

- La parte de analisis->Generar curva no hace nada. Se reporta lo que muestra la terminal:

0.30000000000000004
admin2025
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
Halcyon
id_f1 recibido: <data.ManejoDatos.user.Usuario object at 0x000001A51C3E7950>, id_f1_num usado: Administrador
Consulta de físicos exitosa: Nombre F1: []
Físico 2 seleccionado:  Andres David Loaiza Baena, ID: 6
user_id_f2 antes de create_control: 6
Entrando a crear control
Halcyon
ANTES ADD: ln_fact_cam_princi False
CREADO: ln_fact_cam_princi
ANTES ADD: ln_fact_cam_sec False
CREADO: ln_fact_cam_sec
ANTES ADD: ln_fact_elect False
CREADO: ln_fact_elect
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
ANTES ADD: ln_observaciones_dosi False
CREADO: ln_observaciones_dosi
ANTES ADD: ln_tolerance_mlc False
CREADO: ln_tolerance_mlc
ANTES ADD: ln_action_tolerance False
CREADO: ln_action_tolerance
DF LINES: 
['val_teo_6mv', 'ln_dosis_ref_cgy_um_6mv', 'ln_discrepancia_dosis_6mv', 'ln_tolerancia_dosis', 'ln_calidad_pdd20_10_6mv', 'ln_discrepancia_calidad_6mv', 'ln_tolerancia_calidad', 'ln_simetria_inplane_6mv', 'ln_simetria_crossplane_6mv', 'ln_tolerancia_simetria', 'ln_observaciones_dosi']
DF LINES: 
['ln_action_tolerance']
Widget 'ln_dosis_ref_cgy_um_15mv' no encontrado
Widget 'ln_dosis_ref_cgy_um_6mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_9mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_12mev' no encontrado
Widget 'ln_dosis_ref_cgy_um_15mev' no encontrado
Dialog llamado desde: PruebaMensualHc
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

- La opcion dentro de la calculadora de dosis que ofrece generar un reporte pdf no genera nada porque no hay fechas guardadas en la base de datos. Esto puede ser logico, sabiendo que aun falta generar y guardar el reporte mensual completo. Sin embargo, al "Aceptar y cerrar" se genera un reporte pdf, seguramente porque este boton si crea el registro y asigna una fecha a partir de la cual generar el pdf.

- Error grave, en la calculadora de dosis para electrones del IX no coloque solamente valor a la casilla de TPR, al final pudo calcular dosis absoluta, pero le di al boton de 6MV, luego al de 'Aceptar y cerrar' y dijo que no se podia guardar dado que faltaba un valor ahi en tipo de medida pero nisiquiera se que casilla es esa, lo grave es que se cerró igual, lo cual borró todo el trabajo de llenado de datos, esto no deberia pasar, deberia haber una verificacion luego de presionar el boton de "Aceptar y cerrar" que si falta algun dato permita elegir si descartar los cambios o seguir editando. O que queden en cache mientras la aplicacion este abierta o algo asi, lo que sea mas limpio y simple pero bien estructurado.


Adjunto el mensaje de la terminal para esta parte, no se exactamente donde empieza lo de la calculadora del IX para electrones;

PyQt5.QtWidgets.QGridLayout object at 0x000001A527B5E7A0>
<PyQt5.QtWidgets.QGridLayout object at 0x000001A527B5EC20>
<PyQt5.QtWidgets.QGridLayout object at 0x000001A527B5EB00>
<PyQt5.QtWidgets.QGridLayout object at 0x000001A527B5EB90>
<PyQt5.QtWidgets.QGridLayout object at 0x000001A527B5EA70>
DF LINES: 
['puntero_telem_diff', 'lbl_telem_rango', 'lbl_telem_desp', 'lbl_camilla_vert_rango', 'lbl_camilla_vert_desp', 'lbl_camilla_iso_desp', 'lbl_reticulo_cent', 'lbl_iso_mec', 'camp_luz_desp', 'lbl_bordes_coin', 'lbl_laser_techo', 'lbl_laser_lateral27', 'lbl_laser_lateral9', 'observaciones']
Configurando dosimetría para equipo IX

Entra a addsomething_ix de la clase PruebaMensualIX
Error al cargar datos: [Errno 2] No such file or directory: 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-10\\dosimetria.json'
ln tolerance encontrado
⚠️ Widgets MLC no encontrados - revisar creación desde Excel
Dialog llamado desde: PruebaMensualIX
Dialog llamado desde: PruebaMensual600
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
could not convert string to float: '21.2-'
could not convert string to float: ''
could not convert string to float: ''
could not convert string to float: ''
Dialog llamado desde: PruebaMensualIX

- Para la calculadora de dosis de electrones del IX se necesita el valor de TPR, si es asi no lo logro encontrar en el .xls.

- Si la N31002 presenta diferencias reales con respecto a la N31010, entonces no deberiamos descartar la opcion de que sean camaras separadas si aun se usan?. Bueno, pero ya no se usa, ya no la tienen. El lunes vamos a cargar mas informacion de las tablas.

- Tiene o no filtro aplanador. Se esta teniendo en cuenta esto en alguna parte del proceso de calculo de la dosis? Que parametro lo tiene en cuenta?

- Debemos verificar el calculo del R50, dado que no esta dando exactamente igual que en el excel, pero esa diferencia puede ser indicador de un calculo erroneo o simplemente la cantidad de decimales tenidos en cuenta, o el uso del parametro incorrecto en la formula, etc. Entonces hay que diferenciar.

- Con respecto a importar los archivos .mcc, lo importante es extraer de ellos informacion que pueda rellenar el formulario.

- La formula que aparece en el formato .xls indica que se calcula como R50(asumo que el R50 medido)*0.6 - 0.1. Esta formula en el caso del calculo dosimetrico mensual para el acelerador IX de octubre del 2024 (Carpeta Documents/Archivos_UseApp/Archivos QA/2024/Octubre/iX/Electrones la de 6 MV) con un R50 medido de 2.397 da 1.3382. Si usaramos Q(R50), daría exactamente lo que nos da en la app, pero se supone que el formato de excel es el correcto, no? Te pregunto para verificar si esto fue extraido de la version TRS 398 del 2024 y esta actualizado o si hay un error.

- Ademas el TPR 20/10 no se tiene en cuenta en las pruebas de calculo de dosis para electrones, deberiamos como primera opcion asignar inmediatamente un valor a la casilla del TPR como N/A bloqueado en la casilla, asumo que igual despues de la seleccion de electrones el valor de esta casilla no influye en el calculo de la dosis de ninguna posible manera. Si esta solucion lo complicase podriamos mas bien simplemente ocultar la casilla cuando se seleccionen electrones.

- Me gustaria que por defecto estuviera marcada la casilla de Tipo de escaneo en modo pulse. Debido a que es casi el modo predeterminado en el que se hacen estas pruebas aqui. Claramente que se pueda cambiar en caso tal. 

- Hay un pequeño inconveniente, es muy util que salga el letrero de que hacen falta datos, cuando se selecciona el boton de 'Aceptar y cerrar" pero igualmente se cierra y se limpia la calculadora, lo cual implica que si por error la cierro, tendria que volver a escribir manualmente casi todos los datos, lo cual no es agradable, quisiera que ademas de mostrar los valores que hacen falta mostrara tambien dos botones de "Descartar cambios" o "Quedarse" Acompañados de la pregunta de "Desea salir de la calculadora?".

# Carga manual de la revision en la mañana del 2026-07-14

Esta todo bien en el proceso de construccion?, que son los warnings con hidden import?:

(.venv) PS C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-14> .\.venv\Scripts\python.exe build_exe.py
87 INFO: PyInstaller: 6.21.0, contrib hooks: 2026.6
87 INFO: Python: 3.11.0
98 INFO: Platform: Windows-10-10.0.26200-SP0
98 INFO: Python environment: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-14\.venv
99 INFO: wrote C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-14\RAD-QA.spec
100 INFO: Removing temporary files and cleaning cache in C:\Users\parra\AppData\Local\pyinstaller
6565 INFO: Module search paths (PYTHONPATH):
['C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311\\python311.zip',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311\\DLLs',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311\\Lib',
 'C:\\Users\\parra\\AppData\\Local\\Programs\\Python\\Python311',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\win32',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\win32\\lib',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\pythonwin',
 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14']
6770 INFO: Appending 'datas' from .spec
6777 INFO: checking Analysis
6777 INFO: Building Analysis because Analysis-00.toc is non existent
6777 INFO: Looking for Python shared library...
6777 INFO: Using Python shared library: C:\Users\parra\AppData\Local\Programs\Python\Python311\python311.dll
6777 INFO: Running Analysis Analysis-00.toc
6777 INFO: Target bytecode optimization level: 0
6777 INFO: Initializing module dependency graph...
6779 INFO: Initializing module graph hook caches...
6788 INFO: Analyzing modules for base_library.zip ...
7333 INFO: Processing standard module hook 'hook-heapq.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
7372 INFO: Processing standard module hook 'hook-encodings.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
7885 INFO: Processing standard module hook 'hook-math.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
8078 INFO: Processing standard module hook 'hook-pickle.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
8755 INFO: Caching module dependency graph...
8775 INFO: Analyzing C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-14\main.py
8778 INFO: Processing standard module hook 'hook-PyQt5.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
9266 INFO: Processing standard module hook 'hook-PyQt5.QtWidgets.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
10825 INFO: Processing standard module hook 'hook-PyQt5.QtCore.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
12716 INFO: Processing standard module hook 'hook-PyQt5.QtGui.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
21234 INFO: Processing standard module hook 'hook-sqlite3.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
21465 INFO: Processing standard module hook 'hook-cryptography.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
22068 INFO: hook-cryptography: cryptography does not seem to be using dynamically linked OpenSSL.
22172 INFO: Processing standard module hook 'hook-numpy.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
22411 INFO: Processing standard module hook 'hook-difflib.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
22512 INFO: Processing standard module hook 'hook-multiprocessing.util.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
22578 INFO: Processing standard module hook 'hook-xml.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
22705 INFO: Processing standard module hook 'hook-_ctypes.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
23045 INFO: Processing standard module hook 'hook-sysconfig.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
23085 INFO: Processing standard module hook 'hook-platform.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
23295 INFO: Processing standard module hook 'hook-webbrowser.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
23659 INFO: Processing pre-safe-import-module hook 'hook-typing_extensions.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
23659 INFO: SetuptoolsInfo: initializing cached setuptools info...
24682 INFO: Processing standard module hook 'hook-charset_normalizer.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
24852 INFO: Processing standard module hook 'hook-pandas.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
25911 INFO: Processing standard module hook 'hook-pytz.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
26117 INFO: Processing standard module hook 'hook-scipy.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
26484 INFO: Processing standard module hook 'hook-pycparser.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
26577 INFO: Processing standard module hook 'hook-setuptools.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
26581 INFO: Processing pre-safe-import-module hook 'hook-distutils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
26581 INFO: Processing pre-find-module-path hook 'hook-distutils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_find_module_path'
26926 INFO: Processing standard module hook 'hook-distutils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
26958 INFO: Processing standard module hook 'hook-distutils.util.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
26974 INFO: Processing standard module hook 'hook-_osx_support.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
27094 INFO: Processing standard module hook 'hook-pkg_resources.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
27704 INFO: Processing pre-safe-import-module hook 'hook-importlib_metadata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
27750 INFO: Processing pre-safe-import-module hook 'hook-packaging.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
28483 INFO: Processing standard module hook 'hook-scipy.linalg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
28584 INFO: Processing standard module hook 'hook-scipy.special._ufuncs.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
29196 INFO: Processing standard module hook 'hook-scipy.spatial._ckdtree.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
29227 INFO: Processing standard module hook 'hook-matplotlib.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
29470 INFO: Processing pre-safe-import-module hook 'hook-gi.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
29626 INFO: Processing standard module hook 'hook-matplotlib.backend_bases.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
29685 INFO: Processing standard module hook 'hook-PIL.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
29810 INFO: Processing standard module hook 'hook-PIL.Image.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
30010 INFO: Processing standard module hook 'hook-xml.etree.cElementTree.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
30168 INFO: Processing standard module hook 'hook-PIL.ImageFilter.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
30558 INFO: Processing standard module hook 'hook-matplotlib.backends.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
30593 INFO: Processing standard module hook 'hook-matplotlib.pyplot.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
31169 INFO: Processing standard module hook 'hook-dateutil.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
31323 INFO: Processing pre-safe-import-module hook 'hook-six.moves.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
32297 INFO: Processing standard module hook 'hook-scipy.spatial.transform.rotation.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
33097 INFO: Processing standard module hook 'hook-scipy.stats._stats.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
33370 INFO: Processing standard module hook 'hook-scipy.sparse.csgraph.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
34030 INFO: Processing standard module hook 'hook-scipy.special._ellip_harm_2.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
35461 INFO: Processing standard module hook 'hook-pandas.io.formats.style.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
36769 INFO: Processing standard module hook 'hook-pandas.plotting.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
36993 INFO: Processing standard module hook 'hook-openpyxl.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
38099 INFO: Processing standard module hook 'hook-pandas.io.clipboard.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
38279 INFO: Processing standard module hook 'hook-xml.dom.domreg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
38691 INFO: Processing standard module hook 'hook-reportlab.lib.utils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
38728 INFO: Processing standard module hook 'hook-reportlab.pdfbase._fontdata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
40039 INFO: Processing standard module hook 'hook-PyQt5.QtSql.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
41785 INFO: Processing standard module hook 'hook-pydicom.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
42265 INFO: Processing pre-safe-import-module hook 'hook-importlib_resources.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
46093 INFO: Processing standard module hook 'hook-pyqtgraph.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
364 WARNING: Failed to collect submodules for 'pyqtgraph.opengl' because importing 'pyqtgraph.opengl' raised: ModuleNotFoundError: No module named 'OpenGL'
46786 INFO: hook-pyqtgraph: selected 'PyQt5' as Qt bindings because hook for 'PyQt5' has been run before.
46806 INFO: Processing standard module hook 'hook-PyQt5.uic.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
46920 INFO: Processing pre-find-module-path hook 'hook-PyQt5.uic.port_v2.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_find_module_path'
46953 INFO: Processing standard module hook 'hook-PyQt5.QtSvg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
47801 INFO: Processing standard module hook 'hook-PyQt5.QtTest.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
49072 INFO: Processing standard module hook 'hook-matplotlib.backends.backend_qtagg.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
49075 INFO: Processing standard module hook 'hook-matplotlib.backends.qt_compat.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
49075 INFO: hook-matplotlib.backends.qt_compat: selected 'PyQt5' as Qt bindings because hook for 'PyQt5' has been run before.
49608 INFO: Processing standard module hook 'hook-plotly.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
50484 INFO: Processing standard module hook 'hook-narwhals.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
54124 INFO: Processing standard module hook 'hook-skimage.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
54177 INFO: Processing standard module hook 'hook-skimage.measure.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
54993 INFO: Processing standard module hook 'hook-pydantic.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
55476 INFO: Processing standard module hook 'hook-zoneinfo.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
55906 INFO: Processing standard module hook 'hook-dns.rdata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
56381 INFO: Processing standard module hook 'hook-pythoncom.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
56443 INFO: Processing standard module hook 'hook-pywintypes.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
56725 INFO: Processing standard module hook 'hook-skimage.filters.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
58883 INFO: Processing standard module hook 'hook-skimage.draw.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
59189 INFO: Processing standard module hook 'hook-skimage.transform.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
59531 INFO: Processing standard module hook 'hook-skimage.segmentation.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
59865 INFO: Processing standard module hook 'hook-skimage.exposure.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
60195 INFO: Processing standard module hook 'hook-skimage.morphology.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
60759 INFO: Processing standard module hook 'hook-skimage.feature.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
61301 INFO: Processing standard module hook 'hook-cv2.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
61879 INFO: Processing standard module hook 'hook-msoffcrypto.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
61988 INFO: Processing pre-safe-import-module hook 'hook-win32com.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\pre_safe_import_module'
62049 INFO: Processing standard module hook 'hook-win32com.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
62679 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.IX'
62691 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.halcyon'
62700 INFO: Analyzing hidden import 'ui.paginasControles.PruebasMensuales.ix_mensual'
62707 INFO: Analyzing hidden import 'ui.paginasControles.PruebasMensuales.tac_mensual'
62843 INFO: Analyzing hidden import 'ui.paginasControles.PruebasAnuales.ix_anual'
62870 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.seiscientos'
62877 INFO: Analyzing hidden import 'ui.paginasControles.PruebasDiarias.braquiterapia'
63018 INFO: Analyzing hidden import 'services.auditorias'
63019 INFO: Analyzing hidden import 'services.decoradores_audit'
63020 INFO: Analyzing hidden import 'pylinac.contrib'
63020 INFO: Analyzing hidden import 'pylinac.contrib.orthogonality'
63024 INFO: Analyzing hidden import 'pylinac.contrib.quasar'
63025 INFO: Analyzing hidden import 'pylinac.core.metrics'
63026 INFO: Analyzing hidden import 'pylinac.dlg'
63029 INFO: Analyzing hidden import 'pylinac.nuclear'
63055 INFO: Analyzing hidden import 'pylinac.plan_generator'
63056 INFO: Analyzing hidden import 'pylinac.plan_generator.dicom'
63077 INFO: Processing module hooks (post-graph stage)...
63156 WARNING: Hidden import "pycparser.lextab" not found!
63156 WARNING: Hidden import "pycparser.yacctab" not found!
63272 INFO: Processing pre-safe-import-module hook 'hook-tomli.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
63469 INFO: Processing standard module hook 'hook-skimage.color.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
63848 INFO: Processing standard module hook 'hook-skimage.restoration.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
64204 INFO: Processing standard module hook 'hook-skimage.metrics.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
64678 INFO: Processing standard module hook 'hook-matplotlib.backends.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
64678 INFO: Matplotlib backend selection method: automatic discovery of used backends
64714 INFO: Discovered Matplotlib backend(s) via `matplotlib.use()` call in module 'models.PDF.Mensuales.reportes_mensuales': ['Agg', 'Agg', 'Agg']
64748 INFO: The following Matplotlib backends were discovered by scanning for `matplotlib.use()` calls: ['Agg']. If your backend of choice is not in this list, either add a `matplotlib.use()` call to your code, or configure the backend collection via hook options (see: https://pyinstaller.org/en/stable/hooks-config.html#matplotlib-hooks).
64748 INFO: Selected matplotlib backends: ['Agg']
64999 INFO: Processing standard module hook 'hook-PIL.SpiderImagePlugin.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
65401 WARNING: Hidden import "scipy.special._cdflib" not found!
65425 INFO: Processing standard module hook 'hook-setuptools._vendor.importlib_metadata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
65485 INFO: Processing standard module hook 'hook-setuptools._vendor.jaraco.text.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
65971 INFO: Processing standard module hook 'hook-tzdata.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
66308 INFO: Performing binary vs. data reclassification (1829 entries)
66419 INFO: Looking for ctypes DLLs
66568 INFO: Analyzing run-time hooks ...
66581 INFO: Including run-time hook 'pyi_rth_mplconfig.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
66583 INFO: Processing pre-find-module-path hook 'hook-_pyi_rth_utils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\pre_find_module_path'
66585 INFO: Processing standard module hook 'hook-_pyi_rth_utils.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks'
66591 INFO: Including run-time hook 'pyi_rth_pkgutil.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
66592 INFO: Including run-time hook 'pyi_rth_multiprocessing.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
66594 INFO: Including run-time hook 'pyi_rth_setuptools.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
66595 INFO: Including run-time hook 'pyi_rth_pkgres.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
66597 INFO: Including run-time hook 'pyi_rth_pywintypes.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
66598 INFO: Including run-time hook 'pyi_rth_pythoncom.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
66598 INFO: Including run-time hook 'pyi_rth_inspect.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
66600 INFO: Including run-time hook 'pyi_rth_pyqt5.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
66603 INFO: Including run-time hook 'pyi_rth_pyqtgraph_multiprocess.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
66604 INFO: Including run-time hook 'pyi_rth_cryptography_openssl.py' from 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
66667 INFO: Creating base_library.zip...
66680 INFO: Looking for dynamic libraries
70422 INFO: Extra DLL search directories (AddDllDirectory): ['C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyQt5\\Qt5\\bin', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\numpy.libs', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\scipy.libs', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\pandas.libs', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\cv2\\../../x64/vc14/bin']
70422 INFO: Extra DLL search directories (PATH): ['C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\cv2\\../../x64/vc14/bin', 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyQt5\\Qt5\\bin']
72034 WARNING: Library not found: could not resolve 'LIBPQ.dll', dependency of 'C:\\Users\\parra\\Documents\\AUNA_Codigos_2026\\Codigo_radqa_2026-07-14\\.venv\\Lib\\site-packages\\PyQt5\\Qt5\\plugins\\sqldrivers\\qsqlpsql.dll'.
72291 INFO: Warnings written to C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-14\build\RAD-QA\warn-RAD-QA.txt
72525 INFO: Graph cross-reference written to C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-14\build\RAD-QA\xref-RAD-QA.html
72613 INFO: checking PYZ
72613 INFO: Building PYZ because PYZ-00.toc is non existent
72613 INFO: Building PYZ (ZlibArchive) C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-14\build\RAD-QA\PYZ-00.pyz
74877 INFO: Building PYZ (ZlibArchive) C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-14\build\RAD-QA\PYZ-00.pyz completed successfully.
74926 INFO: checking PKG
74927 INFO: Building PKG because PKG-00.toc is non existent
74927 INFO: Building PKG (CArchive) RAD-QA.pkg
74960 INFO: Building PKG (CArchive) RAD-QA.pkg completed successfully.
74961 INFO: Bootloader C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-14\.venv\Lib\site-packages\PyInstaller\bootloader\Windows-64bit-intel\runw.exe
74962 INFO: checking EXE
74962 INFO: Building EXE because EXE-00.toc is non existent
74962 INFO: Building EXE from EXE-00.toc
74962 INFO: Copying bootloader EXE to C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-14\build\RAD-QA\RAD-QA.exe
74966 INFO: Copying icon to EXE
74968 INFO: Copying 0 resources to EXE
74968 INFO: Embedding manifest in EXE
74971 INFO: Appending PKG archive to EXE
74990 INFO: Fixing EXE headers
75114 INFO: Building EXE from EXE-00.toc completed successfully.
75234 INFO: checking COLLECT
75234 INFO: Building COLLECT because COLLECT-00.toc is non existent
75235 INFO: Building COLLECT COLLECT-00.toc
76772 INFO: Building COLLECT COLLECT-00.toc completed successfully.
76792 INFO: Build complete! The results are available in: C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-07-14\dist

- Revise nuevamente la formula del calculo de Q(R50) y zref(R50), me comenta que el documento de la IAEA ni el de la AAPM no son claros, (y difieren en muchas cosas). con respecto a cual valor se usa para calculara cada uno de estos anteriormente mencionados.Segun yo, el hecho de que en el documento de la IAEA se mencione un R50,ion que se usa para calcular el Beam Quality(R50) y que este ultimo nada mas se represente como R50, me parece suficiente para saber que el calculo de zref entonces es con R50, y no con R50,ion. Por lo cual yo lo doy como valido, y segun la comparacion con el excel ...

- Camaras de ionizacion disponibles aqui:

- Verificar el guardado y la persisntencia de la informacion:

- Si yo cambio la fecha para llenar una prueba en una fecha diferente a la que en que se realizó, obviamente posterior, se estan actualizando las fechas de vigencia de los equipos? No se ajusta, si en la fecha del formulario mensual elijo octubre del 2024, y en la calculadora de dosis cambio la fecha para que coincida con la del formulario a 10/9/2024 (asumiendo que este formato de fecha tiene sentido porque nos importa es el mes), y busco la serie de la camara N34001, que es la unica que tiene la serie 2426, la TN34001 que es segun me cuentan la que se usa normalmente no tiene la serie 2426, solo la 1069. Incluso si selecciono la serie 001069 para la TN34001 no aparece ni vigente ni nada, hay que hacer una revision en esta seccion. Al final hay realmente alguna diferencia entre TN34001 y N34001?.

- No estan apareciendo los archivos .mcc (MCC FILE) al seleccionar el boton y explorar los archivos. El problema puede ser debido a que la carpeta de electrones incluye archivos .xls ademas de los MCC FILES, y por eso no se puede cargar la "carpeta". Verificado, si es por eso. Seria util que en la ventana emergente de informacion al cargar los datos se muestre la formula y/o principio usado para llegar a estos valores de forma breve y clara. Que es lo de calidad (J1/J2), y por que no se llena automaticamente?

- La calculadora se abre con una fecha diferente al del formulario del control mensual. No tiene sentido realmente.

- Hay que agrandar el tamaño del espacio donde se escriben los meses, o desplazarlos hacia la izquierda, para que la flechita del menú desplegable no quede sobre el texto del mes. Queda sobre la ultima letra.

- Muy bien, aparece de una vez seleccionado el Tipo de escaneo en pulse. Se carga el valor del parametro de Humedad de calibracion automaticamente, aparece la ventana despues de "Aceptar y cerrar" para decidir si descartar o seguir editando. Funciona la carga de archivos MCC y parecen estar bien en el sentido de que estan dentro de las tolerancias. 

- Podriamos incluir en la comparacion de la app vs excel el parametro Q(R50) y el zref.

- La calculadora de dosis para electrones no esta dejando cerrar que porque falta llenar le campo de SSD, el problema es que esa casilla no es visible, si se debe incluir o no, no lo se. Pero al menos en el formato de excel .xls en el que nos hemos basado aparece (100 cm)

- Acaso el comparador de app contra excel esta mintiendo sobre el valor real calculaod, si no por que no coincide exactamente el de la app con el de la tabla de comparacion? Por ejemplo, la calculadora dice, 1.1648 y la ventana de comparacion en la columna de app dice 1.164700y pues no entiendo bien porque, se que hay algunos archivos .xls que estan mal llenados, pero para eso tenemos varios y los documentos de referencia pdf.

- Al menos en el IX hay que poner un subtitulo o texto indicador de cuales energias son para electrones y cuales para fotones, ya que solo aparecen 6 botones sin mas 6 MV, 15 MV, 6 MV, 9 MV, ... y es facil cometer errores de seleccion y permite un proceso mas limpio del codigo y al usar la app.

- Si quedan los datos guardados al abrir y cerrar la app al menos luego de cargar un reporte diario. Pero lo que se registran depende de la fecha. Porque si lleno en el mismo dia dos reportes diarios el ultimo reemplaza al primero.

- Se esta cargando automaticamente un dato en calidad cuando abro el formulario mensual del IX en la fecha actual. Pero no es de lo que habia guardado porque no lo guardé y tampoco están los datos de dosis que habia cargado desde la calculadora.

- En el formulario mensual, aspectos mecanicos, indicadores angulares del colimador falta la fila para llenar informacion de los 180 grados.

En el formulario mensual, aspectos mecanicos, tamaño de campo estan llenos predeterminadamente los valores de las tablas, esto no puede ocurrir, todo debe estar limpio si no hay datos cargados previamente para esa fecha.

- Los datos se cargan correctamente a la base de datos, en cada seccion del formulario mensual, cada tabla una a una.

Cambios proximos:
- La ventana emergente que informa lo del kQ al elegir una camara no menciona electrones para habilitar el llenado manual de este parametro, deberia tenerse en cuenta tambien.