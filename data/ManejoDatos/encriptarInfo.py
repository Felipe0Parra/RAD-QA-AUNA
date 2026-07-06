import pyAesCrypt
import tempfile
import os
import base64
import traceback

# Define una contraseña segura para la encriptación (guárdala en un lugar seguro)
ENCRYPTION_PASSWORD = "Stark_3012"  
BUFFER_SIZE = 64 * 1024

def encrypt_data(data: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as temp_in:
        temp_in.write(data.encode())
        temp_in.flush()
        temp_in_path = temp_in.name
    temp_out_path = temp_in_path + ".aes"
    try:
        pyAesCrypt.encryptFile(temp_in_path, temp_out_path, ENCRYPTION_PASSWORD, BUFFER_SIZE)
        with open(temp_out_path, "rb") as f:
            encrypted_bytes = f.read()
        # Convertir a Base64 para almacenarlo como texto
        encrypted_b64 = base64.b64encode(encrypted_bytes).decode('utf-8')
    finally:
        os.remove(temp_in_path)
        if os.path.exists(temp_out_path):
            os.remove(temp_out_path)
    return encrypted_b64

def decrypt_data(encrypted_b64: str) -> str:
    encrypted_bytes = base64.b64decode(encrypted_b64.encode('utf-8'))
    with tempfile.NamedTemporaryFile(delete=False) as temp_in:
        temp_in.write(encrypted_bytes)
        temp_in.flush()
        temp_in_path = temp_in.name
    temp_out_path = temp_in_path + ".dec"
    try:
        pyAesCrypt.decryptFile(temp_in_path, temp_out_path, ENCRYPTION_PASSWORD, BUFFER_SIZE)
        with open(temp_out_path, "rb") as f:
            decrypted_data = f.read().decode()
    except Exception as e:
        traceback.print_exc()
        print("Error al desencriptar:", e)
        decrypted_data = None
    finally:
        os.remove(temp_in_path)
        if os.path.exists(temp_out_path):
            os.remove(temp_out_path)
    return decrypted_data