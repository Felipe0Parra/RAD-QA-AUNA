import data.ManejoDatos.conection as con
from data.ManejoDatos.user import Usuario
from data.ManejoDatos.encriptarInfo import encrypt_data, decrypt_data
from services.audit_minimo import registrar as _registrar_auditoria

class UsuarioData():

    def login(self, username: Usuario):
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
                        _registrar_auditoria(fila[3], "login", detalle="OK")
                        return Usuario(username=fila[1], password=stored_password, fullname=fila[3])
                    else:
                        #print("Contraseña incorrecta.")
                        #print(stored_password)
                        # Se audita con el usuario INTENTADO (username._usuario)
                        # -- todavía no hay un fullname válido que usar, y
                        # quién intentó (aunque falló) es justo lo relevante.
                        _registrar_auditoria(username._usuario, "login",
                                             detalle="contraseña incorrecta")
                        return None
                else:

                    print("Usuario no encontrado.")
                    _registrar_auditoria(username._usuario, "login",
                                         detalle="usuario no encontrado")
                    return None
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("Error en login:", e)
            return None

    def logout(self, nombre_usuario):
        """Deja rastro de cierre de sesión (A4, PLAN_AUDITORIA_DOS_EJES_21-07.md)."""
        _registrar_auditoria(nombre_usuario, "logout")
    
    def add_user(self, username: Usuario):
        try:
            with con.Conexion().conectar() as db:  # Cierra la conexión automáticamente
                cursor = db.cursor()
                # Asegúrate de que el nombre de usuario sea único
                cursor.execute("SELECT COUNT(*) FROM users WHERE user=?", (username._usuario,))
                if cursor.fetchone()[0] > 0:
                    print(f"El usuario {username._usuario} ya existe.")
                    return None  # Usuario ya existe, no lo agrega

                # Si no existe, lo agrega a la base de datos
                encrypted_pass = encrypt_data(username._clave)
                cursor.execute("INSERT INTO users (user, password, fullname, active, idreal, role, firma ) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (username._usuario, encrypted_pass, username._nombre, username._activo, username._ident, username._rol, username._firma))
                print(f"Usuario {username} agregado exitosamente.")
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
                cursor.execute("UPDATE users SET password=? WHERE user=?", (encrypted_new_pass, usuario))
                db.commit()
                return True
        except Exception as e:
            print("Error al actualizar contraseña:", e)
            return False
