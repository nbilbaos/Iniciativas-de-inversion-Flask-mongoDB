from functools import wraps
from flask import abort, redirect, url_for
from flask_login import current_user


def admin_required(f):
    """Decorador para restringir el acceso solo a administradores."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)  # Forbidden
        return f(*args, **kwargs)

    return decorated_function


def director_required(f):
    """Decorador para restringir el acceso a directores y administradores."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or (not current_user.is_director() and not current_user.is_admin()):
            abort(403)  # Forbidden
        return f(*args, **kwargs)

    return decorated_function


def role_required(roles):
    """
    Decorador para restringir el acceso basado en roles.

    Args:
        roles (list): Lista de roles permitidos
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)  # Forbidden
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def validate_password_strength(password):
    """
    Valida la fortaleza de una contraseña.

    Args:
        password (str): La contraseña a validar

    Returns:
        tuple: (bool, str) - (es_valida, mensaje_error)
    """
    errors = []

    # Verificar longitud
    if len(password) < 8:
        errors.append("La contraseña debe tener al menos 8 caracteres")

    # Verificar mayúsculas
    if not any(c.isupper() for c in password):
        errors.append("La contraseña debe contener al menos una letra mayúscula")

    # Verificar minúsculas
    if not any(c.islower() for c in password):
        errors.append("La contraseña debe contener al menos una letra minúscula")

    # Verificar números
    if not any(c.isdigit() for c in password):
        errors.append("La contraseña debe contener al menos un número")

    # Verificar caracteres especiales
    special_chars = "!@#$%^&*(),.?\":{}|<>"
    if not any(c in special_chars for c in password):
        errors.append("La contraseña debe contener al menos un carácter especial")

    # Retornar resultado
    if errors:
        return False, errors

    return True, []