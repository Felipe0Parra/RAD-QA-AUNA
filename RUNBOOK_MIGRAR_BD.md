# Cómo ajustar una base de datos vieja al estándar actual de RAD-QA

Guía operativa de `scripts/migrar_bd_a_estandar.py`. Sirve para incorporar
cualquier copia de `BaseDatosQA.db` que se haya quedado en un formato
anterior (por ejemplo, una copia que se siguió llenando en otro computador)
y dejarla lista para usarse con la versión actual de la aplicación, **sin
perder ni un registro de QC**.

---

## Qué hace la herramienta (todo en una sola corrida)

1. **Esquema al día**: crea las tablas y columnas que se han agregado al
   proyecto y que la BD vieja no tiene (por ejemplo `audit_log`,
   `controles.activo`, las columnas nuevas de la calculadora). Nunca borra
   ni renombra nada.
2. **Catálogos base**: siembra los catálogos internos (tipos de prueba,
   materiales, regiones, energías) solo si están vacíos.
3. **Corrección del catálogo de equipos** (certificados H2.6/H2.10): las
   mismas correcciones que ya se aplicaron a producción (condiciones de
   referencia en vez de ambientales, duplicados marcados históricos, escalas
   de calibración). Solo toca una fila si coincide EXACTAMENTE con el estado
   conocido de los certificados; cualquier fila distinta se deja intacta y
   se reporta para revisión. Nunca borra una fila.
4. **Limpieza del dato histórico** `' ---- '` en el segundo físico de los
   controles (pasa a vacío/NULL, que es lo correcto).
5. **Blindaje estructural** (si la BD viene de antes de esto): migra toda
   FK con borrado en cascada a `RESTRICT`, crea los triggers que impiden
   borrar físicamente `controles`/`TipoCalibracion`/`LinealidadBraquiterapia`/
   `users`, asigna los roles de sistema (admin/jefe/físico) y normaliza
   cualquier fila duplicada de `sqlite_sequence`. El reporte lo cuenta
   explícitamente en **"Cambios estructurales"** — antes esto ocurría en
   silencio.
6. **Verificación y reporte**: integridad antes/después, conteo de cada
   tabla de QC antes/después (deben ser idénticos), **censo de las 69
   tablas** (no solo las de QC) para confirmar que ninguna perdió filas, y
   detalle de todo lo que cambió. Todo queda además registrado en el
   `audit_log` de la propia BD.

## Qué NO hace

- No borra ni modifica ningún registro de QC (controles, dosimetría,
  preguntas, tamaños de campo, pruebas, calculadora).
- No fusiona dos bases de datos (eso es un procedimiento aparte).
- No crea archivos nuevos: si la ruta está mal escrita, avisa y se detiene.

---

## Pasos

Desde la carpeta `Codigo_radqa` (en Windows use `.venv\Scripts\python`; en
Linux `.venv/bin/python`):

### Paso 1 — Previsualizar (no cambia nada)

```
.venv\Scripts\python scripts\migrar_bd_a_estandar.py "C:\ruta\a\MiCopia.db"
```

Sin `--aplicar`, la herramienta trabaja sobre una copia temporal interna y
solo MUESTRA lo que haría. Revise el reporte:

- **"Cambios de esquema"**: tablas/columnas que va a agregar (normal en una
  BD vieja).
- **"Saneamiento del catálogo de equipos"**: cuántas filas va a corregir.
  En una copia del linaje de producción lo normal es ver las correcciones de
  los certificados. Si aparece **"saltadas por deriva"**, esas filas NO se
  tocarán — anote los id y consúltelo antes de continuar.
- **"Cambios estructurales"**: si la BD venía en el formato viejo (borrado
  en cascada), aquí se listan las tablas que pasan a RESTRICT, los triggers
  anti-borrado creados y los roles asignados. Es esperado que aparezca en
  la primera corrida de una BD vieja; en corridas siguientes debe decir
  "sin cambios estructurales".
- **"Registros de QC preservados"** y **"Censo completo"**: los conteos
  deben ser IDÉNTICOS a ambos lados de la flecha, en las 69 tablas, no solo
  las destacadas.

### Paso 2 — Aplicar

```
.venv\Scripts\python scripts\migrar_bd_a_estandar.py "C:\ruta\a\MiCopia.db" --aplicar --usuario sunombre
```

- Antes de tocar el archivo crea un backup con fecha al lado
  (`MiCopia.db.pre_migracion_AAAAMMDD_HHMMSS.bak`). Consérvelo.
- Si la BD viniera dañada (`integrity_check` distinto de "ok"), se detiene
  sin hacer nada.
- `--usuario` deja su nombre en el registro de auditoría de la BD (opcional
  pero recomendado).

### Paso 3 — Usar

Copie el archivo ya migrado como `BaseDatosQA.db` junto al ejecutable
`RAD-QA.exe` (reemplazando el que esté, previa copia de seguridad de ese
también). Abra la aplicación y verifique un par de controles conocidos.

---

## Preguntas frecuentes

**¿Puedo correrla dos veces?** Sí — es idempotente: la segunda corrida
reporta "sin cambios" y no modifica nada.

**¿Y si me equivoco de archivo?** Si la ruta no existe o el archivo no es
una BD SQLite, la herramienta avisa y se detiene sin crear ni tocar nada.

**¿Qué pasa con los archivos `-wal`/`-shm` que a veces acompañan a la BD?**
La herramienta los entiende y los consolida automáticamente al `.db`
principal antes de hacer el backup, así no se pierde ningún registro
reciente. Al transportar una BD entre computadores, lo más seguro sigue
siendo copiar los tres archivos juntos si existen (o cerrar la aplicación
antes de copiar — al cerrar, la app deja el `.db` completo).

**¿Cómo deshago una migración?** Restaure el `.bak` que quedó al lado del
archivo (renombrarlo de vuelta). Nada más hace falta.

**¿Dónde queda constancia de lo que se hizo?** En la salida de la terminal
(puede copiarla/pegarla) y en la tabla `audit_log` de la propia BD migrada
(acciones `migracion` y `saneamiento_h26`, con fecha, usuario y detalle).
