# # audit/engine.py
# import logging
# import sys
# import traceback
# import functools
# from datetime import datetime
# from PyQt5.QtCore import QObject, pyqtSignal
# import data.ManejoDatos.conection as con

# class AuditEngine(QObject):
#     new_entry = pyqtSignal(dict)
#     _instance = None

#     def __new__(cls):
#         if cls._instance is None:
#             instance = super().__new__(cls)
#             QObject.__init__(instance)
#             instance._initialized = False
#             cls._instance = instance
#         return cls._instance

#     def __init__(self):
#         if self._initialized:
#             return
#         # QObject.__init__ ya se llamó en __new__, NO repetir aquí
#         self._initialized  = True
#         self._current_user = "sistema"
#         self._current_role = "user"
#         self._ensure_table()
#         self._setup_excepthook()

#     def set_user(self, username: str, role: str = 'user'):
#         """Llamar esto inmediatamente después del login exitoso."""
#         self._current_user = username
#         self._current_role = role

#     def clear_user(self):
#         """Llamar esto en logout."""
#         self._current_user = "sistema"

#     def _ensure_table(self):
#         """Crea la tabla si no existe."""
#         try:
#             with con.Conexion().conectar() as db:
#                 db.execute("""
#                     CREATE TABLE IF NOT EXISTS audit_log (
#                         id        INTEGER PRIMARY KEY AUTOINCREMENT,
#                         timestamp TEXT NOT NULL,
#                         username  TEXT NOT NULL,
#                         action    TEXT NOT NULL,
#                         module    TEXT NOT NULL,
#                         status    TEXT NOT NULL,
#                         detail    TEXT
#                     )
#                 """)
#                 db.commit()
#         except Exception as e:
#             print(f"[AUDIT FATAL] No se pudo crear tabla de auditoría: {e}", file=sys.stderr)

#     def record(self, action: str, module: str, status: str = 'OK', detail: str = None):
#         """
#         Punto central de registro. Primero persiste, luego emite a UI.
#         """
#         entry = {
#             'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
#             'username':  self._current_user,
#             'action':    action,
#             'module':    module,
#             'status':    status,
#             'detail':    detail,
#         }
#         self._persist(entry)   # Primero
#         self._emit_ui(entry)   # Después

#     def _persist(self, entry: dict):
#         try:
#             with con.Conexion().conectar() as db:
#                 db.execute("""
#                     INSERT INTO audit_log
#                         (timestamp, username, action, module, status, detail)
#                     VALUES (?, ?, ?, ?, ?, ?)
#                 """, (
#                     entry['timestamp'],
#                     entry['username'],
#                     entry['action'],
#                     entry['module'],
#                     entry['status'],
#                     entry['detail'],
#                 ))
#                 db.commit()
#         except Exception as e:
#             # Si la persistencia falla, al menos queda en stderr
#             print(f"[AUDIT FATAL] No se pudo persistir entrada: {e}\n{entry}", file=sys.stderr)

#     def _emit_ui(self, entry: dict):
#         try:
#             self.new_entry.emit(entry)
#         except Exception as e:
#             print(f"[AUDIT UI] Fallo al emitir señal: {e}", file=sys.stderr)

#     def _setup_excepthook(self):
#         original = sys.excepthook
#         def hook(exc_type, exc_value, exc_tb):
#             self.record(
#                 action=f'{exc_type.__name__}: {exc_value}',
#                 module='sys.excepthook',
#                 status='CRITICAL',
#                 detail=''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
#             )
#             original(exc_type, exc_value, exc_tb)
#         sys.excepthook = hook