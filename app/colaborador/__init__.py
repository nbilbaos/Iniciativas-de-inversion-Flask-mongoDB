from flask import Blueprint, current_app
from flask_wtf.csrf import generate_csrf

colaborador_bp = Blueprint('colaborador', __name__, url_prefix='/colaborador')
@colaborador_bp.app_context_processor
def inject_csrf_token():
    """Inyectar el token CSRF en todas las plantillas del blueprint."""
    return dict(csrf_token=generate_csrf)
from . import routes
# Importar las rutas de archivos
from . import file_routes