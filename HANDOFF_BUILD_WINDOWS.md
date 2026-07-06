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
