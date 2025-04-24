# app/director/__init__.py
from bson import ObjectId
from flask import Blueprint, current_app
from .. import mongo

director_bp = Blueprint('director', __name__, url_prefix='/director')

# Quitamos la llamada a current_app que podría estar causando problemas
# En app/director/__init__.py

# En app/director/__init__.py

def init_app(app):
    @app.context_processor
    def utility_processor():
        def get_estado_historial(iniciativa_id):
            """Obtiene el historial de cambios de estado de una iniciativa."""
            historial = list(mongo.db.estado_iniciativa_historial.find(
                {"initiative_id": iniciativa_id}
            ).sort("timestamp", -1))
            return historial

        def get_user_by_id(user_id):
            """Obtiene la información de un usuario por su ID."""
            user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
            return user

        def get_iniciativa_info(iniciativa_id):
            """Obtiene información de una iniciativa (estado y nombre)."""
            collection_name = app.config['INITIATIVES_COLLECTION']
            if '.' in collection_name:
                parts = collection_name.split('.')
                if len(parts) > 1:
                    coll = mongo.db[parts[0]][parts[1]]
                else:
                    coll = mongo.db[collection_name]
            else:
                coll = mongo.db[collection_name]

            iniciativa = coll.find_one({"_id": ObjectId(iniciativa_id)})
            if iniciativa:
                return {
                    'estado': iniciativa.get('estado', 'No disponible'),
                    'nombre': iniciativa.get('nombre_iniciativa',
                                             iniciativa.get('nombre', 'Iniciativa sin nombre'))
                }
            return {
                'estado': 'No disponible',
                'nombre': 'Iniciativa no encontrada'
            }

        # En el return del context_processor, cambia get_iniciativa_estado por:
        return dict(
            get_estado_historial=get_estado_historial,
            get_user_by_id=get_user_by_id,
            get_iniciativa_info=get_iniciativa_info
        )

from . import routes
# Importar las rutas de archivos
from . import file_routes