from flask import Blueprint

director_bp = Blueprint('director', __name__, url_prefix='/director')

from . import routes
