import data.ManejoDatos.conection as con
from data.ManejoDatos.user import Usuario
from data.ManejoDatos.encriptarInfo import encrypt_data, decrypt_data
from services.audit_minimo import registrar as _registrar_auditoria
from services.audit_minimo import ACCION_LOGIN, ACCION_LOGOUT, ACCION_AUTORIZACION
from services.audit_minimo import ACCION_GUARDAR, ACCION_ACTUALIZAR

class UsuarioData():

    def login(self, username: Usuario, accion=ACCION_LOGIN):
        """Valida credenciales y deja rastro en `audit_log`.

        `accion` (A8, §8.1 H3 del PLAN_AUDITORIA_DOS_EJES_21-07): qué se está
        registrando. Por defecto `ACCION_LOGIN` (inicio de sesión real, desde
        Login.py). Los diálogos `DialogAdminPermiso*` pasan
        `ACCION_AUTORIZACION` porque NO están abriendo sesión: están
        confirmando permiso para una operación puntual (editar/eliminar/crear
        usuario). Antes todos escribían "login", y como las rutas diarias no
        auditaban su propia operación (H1/H2), ese login quedaba como ÚNICO
        rastro -- de ahí el reporte "mi borrado aparece como un login".
        """
        try:
            with con.Conexion().conectar() as db:  # Cierra la conexión automáticamente
                cursor = db.cursor()

                cursor.execute("SELECT * FROM users WHERE user=?", (username._usuario,))
                fila = cursor.fetchone()

                if fila:
                    # Desencriptar la contraseña almacenada
                    stored_password = decrypt_data(fila[2])
                    print(stored_password)
                    # Compara la contraseña ingresada con la desencriptada
                    if username._clave == stored_password:
                        #print(stored_password)
                        # A4 (PLAN_AUDITORIA_DOS_EJES_21-07): sesión iniciada
                        # -- se audita con el fullname (fila[3]), la misma
                        # identidad que usuario_actual() lee en el resto de
                        # la app (user_id._nombre).
                        _registrar_auditoria(fila[3], accion, detalle="OK")
                        return Usuario(username=fila[1], password=stored_password, fullname=fila[3])
                    else:
                        #print("Contraseña incorrecta.")
                        #print(stored_password)
                        # Se audita con el usuario INTENTADO (username._usuario)
                        # -- todavía no hay un fullname válido que usar, y
                        # quién intentó (aunque falló) es justo lo relevante.
                        _registrar_auditoria(username._usuario, accion,
                                             detalle="contraseña incorrecta")
                        return None
                else:

                    print("Usuario no encontrado.")
                    _registrar_auditoria(username._usuario, accion,
                                         detalle="usuario no encontrado")
                    return None
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("Error en login:", e)
            return None

    def logout(self, nombre_usuario):
        """Deja rastro de cierre de sesión (A4, PLAN_AUDITORIA_DOS_EJES_21-07.md)."""
        _registrar_auditoria(nombre_usuario, ACCION_LOGOUT)
    
    def add_user(self, username: Usuario):
        # F3 (PLAN_F_CIERRE_ESTANDAR_29-07.md): `fullname` es TEXT UNIQUE,
        # NO NOT NULL -- admite vacío. Es el destino de 6 FK y la identidad
        # que queda en audit_log; un usuario sin él es inatribuible de por
        # vida. La interfaz ya lo exige (register_page.py deshabilita el
        # botón sin texto), esta guarda es la última línea de defensa para
        # cualquier otro llamador. Se rechaza en el servicio, no con
        # NOT NULL en el esquema: eso exigiría recrear `users` (que además
        # lleva un trigger anti-borrado de E8, que una recreación borraría)
        # para cerrar un camino que la UI ya bloquea.
        if not username._nombre or not username._nombre.strip():
            print("No se agrega el usuario: el nombre completo no puede quedar vacío.")
            return None
        try:
            with con.Conexion().conectar() as db:  # Cierra la conexión automáticamente
                cursor = db.cursor()
                # Asegúrate de que el nombre de usuario sea único
                cursor.execute("SELECT COUNT(*) FROM users WHERE user=?", (username._usuario,))
                if cursor.fetchone()[0] > 0:
                    print(f"El usuario {username._usuario} ya existe.")
                    return None  # Usuario ya existe, no lo agrega

                # Si no existe, lo agrega a la base de datos.
                # E6: `rol_sistema` (permisos) nace 'fisico' SIEMPRE -- los
                # roles 'admin'/'jefe' solo se asignan por la migración del
                # arranque o a mano; el registro público jamás debe poder
                # crear una cuenta con permisos administrativos. `role` sigue
                # siendo el cargo mostrado que eligió en el combo (lo
                # imprimen los PDF y lo compara la recuperación).
                encrypted_pass = encrypt_data(username._clave)
                cursor.execute("INSERT INTO users (user, password, fullname, active, idreal, role, firma, rol_sistema) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (username._usuario, encrypted_pass, username._nombre, username._activo, username._ident, username._rol, username._firma, "fisico"))
                # Commit explícito ANTES de auditar: `registrar()` abre su
                # propia conexión (services/audit_minimo.py) y si el INSERT
                # de arriba sigue sin comprometerse, choca con "database is
                # locked" (mismo motivo por el que update_password, abajo,
                # ya hacía su propio db.commit() antes de auditar).
                db.commit()
                print(f"Usuario {username} agregado exitosamente.")
                # A6.2 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): alta de
                # usuario -- este archivo ya audita login/logout (A4), pero
                # crear la cuenta en sí no dejaba rastro. Es alta desde el
                # registro propio (register_page.py, sin sesión activa
                # todavía), así que se audita con la identidad del usuario
                # recién creado, igual que login() hace en su rama "OK".
                _registrar_auditoria(username._nombre, ACCION_GUARDAR, "users",
                                     ref=username._usuario)
                return Usuario(username._usuario, username._clave, username._nombre, username._activo, username._ident, username._rol, username._firma)  # Devuelve el nuevo usuario creado
        except Exception as e:
            print("Error al agregar usuario:", e)
            return None
        
    def get_user(self, usuario, idreal, role):
        """Verifica si existe un usuario con los datos ingresados."""
        try:
            with con.Conexion().conectar() as db:
                cursor = db.cursor()
                cursor.execute("SELECT * FROM users WHERE user=? AND idreal=? AND role=?", (usuario, idreal, role))
                fila = cursor.fetchone()
                if fila:
                    # Desencriptar la contraseña antes de retornarla
                    decrypted_pass = decrypt_data(fila[2])
                    
                    return (fila[0], fila[1], decrypted_pass, fila[3], fila[4], fila[5], fila[6])
                return None
        except Exception as e:
            print("Error al buscar usuario:", e)
            return None

    def update_password(self, usuario, nueva_pass):
        """Actualiza la contraseña del usuario en la base de datos."""
        try:
            with con.Conexion().conectar() as db:
                cursor = db.cursor()
                encrypted_new_pass = encrypt_data(nueva_pass)
                # A6.2-bis: el nombre completo se lee ANTES del UPDATE (la
                # fila existe, `recover_page` ya validó con get_user) para
                # auditar con la MISMA identidad que el resto del audit_log.
                cursor.execute("SELECT fullname FROM users WHERE user=?", (usuario,))
                fila_usuario = cursor.fetchone()
                cursor.execute("UPDATE users SET password=? WHERE user=?", (encrypted_new_pass, usuario))
                db.commit()
                # A6.2 (PLAN_AUDITORIA_DOS_EJES_21-07.md §10.7): cambio de
                # contraseña vía recuperación (recover_page.py) -- mismo
                # archivo que ya audita login/logout, sin rastro hasta
                # ahora pese a ser un cambio de credencial.
                #
                # A6.2-bis: antes se auditaba con `usuario` (el nombre de
                # CUENTA, p.ej. "fparrap"), mientras que el alta y el login
                # usan el nombre COMPLETO ("Felipe Parra Paez"). En la BD del
                # rebuild 27-07-2026 eso dejó dos filas de la misma persona
                # sobre `users` con identidades distintas. Ahora espeja a
                # add_user: nombre completo en `usuario`, cuenta en `ref`.
                _registrar_auditoria(fila_usuario[0] if fila_usuario else usuario,
                                     ACCION_ACTUALIZAR, "users", ref=usuario,
                                     detalle="cambio de contraseña")
                return True
        except Exception as e:
            print("Error al actualizar contraseña:", e)
            return False
