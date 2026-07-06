# import traceback
# import functools
# from services.auditorias import AuditEngine

# def audit_action(action_name: str):
#     """
#     Úsalo SOLO en métodos que representan acciones del usuario.
#     No en helpers, no en getters, no en loops internos.
    
#     Ejemplo:
#         @audit_action("Guardar control de calidad diario - Equipo 1")
#         def guardar_control(self): ...
#     """
#     def decorator(func):
#         @functools.wraps(func)
#         def wrapper(*args, **kwargs):
#             engine = AuditEngine()
#             module = func.__module__
#             try:
#                 result = func(*args, **kwargs)
#                 engine.record(
#                     action=action_name,
#                     module=module,
#                     status='OK'
#                 )
#                 return result
#             except Exception as e:
#                 engine.record(
#                     action=action_name,
#                     module=module,
#                     status='ERROR',
#                     detail=traceback.format_exc()
#                 )
#                 raise
#         return wrapper
#     return decorator