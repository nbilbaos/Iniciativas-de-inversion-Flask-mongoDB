from flask import Blueprint

colaborador_bp = Blueprint('colaborador', __name__, url_prefix='/colaborador')

from . import routes