from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

from . import routes
from . import database  # Importar el módulo de gestión de base de datos