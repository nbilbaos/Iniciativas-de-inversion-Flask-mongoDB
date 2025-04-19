from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime
from bson.objectid import ObjectId

from . import colaborador_bp
from ..auth.utils import role_required
from .. import mongo

# Constante para la colección de metadatos de la base de datos
METADATA_COLLECTION = 'db_metadata'


@colaborador_bp.route('/dashboard')
@login_required
@role_required(['colaborador'])
def dashboard():
    """Dashboard para el rol de colaborador."""
    # Obtener información del usuario actual
    user_data = {
        'email': current_user.email,
        'role': current_user.role,
        'last_login': current_user.last_login
    }

    """Dashboard para el rol de colaborador."""
    # Obtener las iniciativas activas asignadas al colaborador
    iniciativas_activas = []

    if hasattr(current_user, 'iniciativas'):
        for iniciativa in current_user.get_active_iniciativas():
            # Obtener información de la colección
            collection_name = iniciativa.get('collection_name')
            collection_data = mongo.db[METADATA_COLLECTION].find_one({"name": collection_name})

            if collection_data:
                # Obtener el nombre del director que asignó la iniciativa
                director_name = ""
                if 'assigned_by' in iniciativa:
                    try:
                        director = mongo.db.users.find_one({"_id": ObjectId(iniciativa['assigned_by'])})
                        if director:
                            director_name = director.get('nombre', '') or director.get('email', '')
                    except:
                        pass

                iniciativas_activas.append({
                    'nombre': collection_data.get('name', ''),
                    'descripcion': collection_data.get('description', ''),
                    'fecha_asignacion': iniciativa.get('assigned_at'),
                    'asignado_por': director_name
                })

    # Estadísticas básicas
    stats = {
        'total_iniciativas': len(iniciativas_activas),
        'completed_tasks': 0,
        'pending_tasks': 0
    }

    return render_template('colaborador/dashboard.html',
                           user_data=current_user,
                           stats=stats,
                           iniciativas=iniciativas_activas)

@colaborador_bp.route('/profile')
@login_required
@role_required(['colaborador'])
def profile():
    """Perfil del colaborador."""
    return render_template('colaborador/profile.html')


@colaborador_bp.route('/tasks')
@login_required
@role_required(['colaborador'])
def tasks():
    """Vista de tareas del colaborador (placeholder para futuras funcionalidades)."""
    return render_template('colaborador/tasks.html')


@colaborador_bp.route('/iniciativas')
@login_required
@role_required(['colaborador'])
def my_initiatives():
    """Ver todas las iniciativas asignadas (actuales e históricas)."""
    # Obtener todas las iniciativas (activas e inactivas)
    iniciativas = []

    if hasattr(current_user, 'iniciativas'):
        for iniciativa in current_user.iniciativas:
            # Obtener información de la colección
            collection_name = iniciativa.get('collection_name')
            collection_data = mongo.db[METADATA_COLLECTION].find_one({"name": collection_name})

            if collection_data:
                # Obtener el nombre del director que asignó la iniciativa
                director_asignado = ""
                if 'assigned_by' in iniciativa:
                    try:
                        director = mongo.db.users.find_one({"_id": ObjectId(iniciativa['assigned_by'])})
                        if director:
                            director_asignado = director.get('nombre', '') or director.get('email', '')
                    except:
                        pass

                # Obtener el nombre del director que desasignó la iniciativa (si aplica)
                director_desasignado = ""
                if 'removed_by' in iniciativa:
                    try:
                        director = mongo.db.users.find_one({"_id": ObjectId(iniciativa['removed_by'])})
                        if director:
                            director_desasignado = director.get('nombre', '') or director.get('email', '')
                    except:
                        pass

                iniciativas.append({
                    'nombre': collection_data.get('name', ''),
                    'descripcion': collection_data.get('description', ''),
                    'activa': iniciativa.get('active', False),
                    'fecha_asignacion': iniciativa.get('assigned_at'),
                    'asignado_por': director_asignado,
                    'fecha_desasignacion': iniciativa.get('removed_at'),
                    'desasignado_por': director_desasignado
                })

    # Ordenar iniciativas: primero las activas, luego por fecha de asignación (más reciente primero)
    iniciativas.sort(key=lambda x: (not x['activa'], x['fecha_asignacion'] or datetime.min), reverse=True)

    return render_template('colaborador/initiatives.html', iniciativas=iniciativas)