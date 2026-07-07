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
