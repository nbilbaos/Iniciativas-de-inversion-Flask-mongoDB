# app/director/__init__.py
from flask import Blueprint, current_app
from .. import mongo

director_bp = Blueprint('director', __name__, url_prefix='/director')

# Quitamos la llamada a current_app que podría estar causando problemas
def init_app(app):
    @app.context_processor
    def utility_processor():
        def get_estado_historial(iniciativa_id):
            """Obtiene el historial de cambios de estado de una iniciativa."""
            historial = list(mongo.db.estado_iniciativa_historial.find(
                {"initiative_id": iniciativa_id}
            ).sort("timestamp", -1))
            return historial

        return dict(get_estado_historial=get_estado_historial)

from . import routes