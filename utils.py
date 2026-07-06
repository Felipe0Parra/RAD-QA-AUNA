import os
import sys

def resource_path(relative_path):
    """
    Para empaquetar con PyInstaller, se usa el método sys._MEIPASS
    para ubicar recursos externos (imágenes, etc.).
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

