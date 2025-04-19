from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from bson.objectid import ObjectId
from datetime import datetime
import json

from . import director_bp
from ..auth.utils import director_required
from .. import mongo
from ..models.user import User

# Constante para la colección de metadatos de la base de datos
METADATA_COLLECTION = 'db_metadata'


@director_bp.route('/initiatives')
@login_required
@director_required
def manage_initiatives():
    """Vista principal para gestionar iniciativas y asignaciones."""
    # Obtener todas las colecciones (iniciativas)
    collections = list(mongo.db[METADATA_COLLECTION].find().sort('name', 1))

    # Obtener todos los colaboradores
    colaboradores = list(mongo.db.users.find({"role": "colaborador", "active": True}).sort("nombre", 1))

    return render_template(
        'director/initiatives/manage.html',
        collections=collections,
        colaboradores=colaboradores
    )


@director_bp.route('/initiatives/collaborators/<collection_id>')
@login_required
@director_required
def get_collection_collaborators(collection_id):
    """Obtener colaboradores asignados a una colección específica."""
    # Obtener datos de la colección
    collection_data = mongo.db[METADATA_COLLECTION].find_one({"_id": ObjectId(collection_id)})

    if not collection_data:
        return jsonify({"success": False, "message": "Colección no encontrada"}), 404

    collection_name = collection_data.get('name')

    # Buscar colaboradores que tienen asignada esta colección
    assigned_collaborators = list(mongo.db.users.find({
        "role": "colaborador",
        "iniciativas": {
            "$elemMatch": {
                "collection_name": collection_name,
                "active": True
            }
        }
    }, {
        "_id": 1,
        "nombre": 1,
        "email": 1,
        "rut": 1,
        "iniciativas": 1
    }))

    # Formatear datos para la respuesta
    result = []
    for collab in assigned_collaborators:
        # Encontrar la iniciativa específica
        iniciativa_info = next(
            (i for i in collab.get('iniciativas', [])
             if i.get('collection_name') == collection_name and i.get('active')),
            None
        )

        if iniciativa_info:
            result.append({
                "_id": str(collab.get('_id')),
                "nombre": collab.get('nombre', ''),
                "email": collab.get('email', ''),
                "rut": collab.get('rut', ''),
                "assigned_at": iniciativa_info.get('assigned_at').strftime('%d/%m/%Y %H:%M') if iniciativa_info.get(
                    'assigned_at') else '-'
            })

    return jsonify({
        "success": True,
        "collection": collection_data,
        "collaborators": result
    })


@director_bp.route('/initiatives/assign', methods=['POST'])
@login_required
@director_required
def assign_initiative():
    """Asignar una iniciativa a un colaborador."""
    # Obtener datos del formulario
    collaborator_id = request.form.get('collaborator_id')
    collection_id = request.form.get('collection_id')

    if not collaborator_id or not collection_id:
        return jsonify({"success": False, "message": "Datos incompletos"}), 400

    # Obtener datos de la colección
    collection_data = mongo.db[METADATA_COLLECTION].find_one({"_id": ObjectId(collection_id)})
    if not collection_data:
        return jsonify({"success": False, "message": "Colección no encontrada"}), 404

    collection_name = collection_data.get('name')

    # Obtener datos del colaborador
    collaborator_data = mongo.db.users.find_one({"_id": ObjectId(collaborator_id), "role": "colaborador"})
    if not collaborator_data:
        return jsonify({"success": False, "message": "Colaborador no encontrado"}), 404

    # Crear instancia del modelo de usuario
    collaborator = User(**collaborator_data)

    # Asignar la iniciativa
    if collaborator.add_iniciativa(collection_id, collection_name, str(current_user._id)):
        # Actualizar en la base de datos
        mongo.db.users.update_one(
            {"_id": ObjectId(collaborator_id)},
            {"$set": {"iniciativas": collaborator.iniciativas}}
        )

        return jsonify({
            "success": True,
            "message": f"Iniciativa asignada correctamente a {collaborator.nombre or collaborator.email}"
        })
    else:
        return jsonify({
            "success": False,
            "message": "El colaborador ya tiene asignada esta iniciativa o no es un colaborador válido"
        }), 400


@director_bp.route('/initiatives/unassign', methods=['POST'])
@login_required
@director_required
def unassign_initiative():
    """Quitar una iniciativa de un colaborador."""
    # Obtener datos del formulario
    collaborator_id = request.form.get('collaborator_id')
    collection_id = request.form.get('collection_id')

    if not collaborator_id or not collection_id:
        return jsonify({"success": False, "message": "Datos incompletos"}), 400

    # Obtener datos de la colección
    collection_data = mongo.db[METADATA_COLLECTION].find_one({"_id": ObjectId(collection_id)})
    if not collection_data:
        return jsonify({"success": False, "message": "Colección no encontrada"}), 404

    collection_name = collection_data.get('name')

    # Obtener datos del colaborador
    collaborator_data = mongo.db.users.find_one({"_id": ObjectId(collaborator_id), "role": "colaborador"})
    if not collaborator_data:
        return jsonify({"success": False, "message": "Colaborador no encontrado"}), 404

    # Crear instancia del modelo de usuario
    collaborator = User(**collaborator_data)

    # Quitar la iniciativa
    if collaborator.remove_iniciativa(collection_id, collection_name, str(current_user._id)):
        # Actualizar en la base de datos
        mongo.db.users.update_one(
            {"_id": ObjectId(collaborator_id)},
            {"$set": {"iniciativas": collaborator.iniciativas}}
        )

        return jsonify({
            "success": True,
            "message": f"Iniciativa desasignada correctamente de {collaborator.nombre or collaborator.email}"
        })
    else:
        return jsonify({
            "success": False,
            "message": "El colaborador no tiene asignada esta iniciativa o no es un colaborador válido"
        }), 400


@director_bp.route('/initiatives/history/<collaborator_id>')
@login_required
@director_required
def get_collaborator_history(collaborator_id):
    """Obtener historial de asignaciones de un colaborador."""
    # Obtener datos del colaborador
    collaborator_data = mongo.db.users.find_one({"_id": ObjectId(collaborator_id), "role": "colaborador"})

    if not collaborator_data:
        return jsonify({"success": False, "message": "Colaborador no encontrado"}), 404

    # Obtener todas las iniciativas (activas e inactivas)
    iniciativas = collaborator_data.get('iniciativas', [])

    # Para cada iniciativa, obtener datos adicionales
    history = []
    for iniciativa in iniciativas:
        collection_id = iniciativa.get('iniciativa_id')
        collection_name = iniciativa.get('collection_name')

        # Datos de la iniciativa
        collection_data = mongo.db[METADATA_COLLECTION].find_one({"name": collection_name})

        # Datos del director que asignó
        assigned_by_data = None
        if 'assigned_by' in iniciativa:
            try:
                assigned_by_data = mongo.db.users.find_one({"_id": ObjectId(iniciativa.get('assigned_by'))})
            except:
                pass

        # Datos del director que desasignó
        removed_by_data = None
        if 'removed_by' in iniciativa:
            try:
                removed_by_data = mongo.db.users.find_one({"_id": ObjectId(iniciativa.get('removed_by'))})
            except:
                pass

        history.append({
            "collection_name": collection_name,
            "collection_description": collection_data.get('description', '') if collection_data else '',
            "active": iniciativa.get('active', False),
            "assigned_at": iniciativa.get('assigned_at').strftime('%d/%m/%Y %H:%M:%S') if iniciativa.get(
                'assigned_at') else None,
            "assigned_by": assigned_by_data.get('nombre', '') if assigned_by_data else '',
            "assigned_by_email": assigned_by_data.get('email', '') if assigned_by_data else '',
            "removed_at": iniciativa.get('removed_at').strftime('%d/%m/%Y %H:%M:%S') if iniciativa.get(
                'removed_at') else None,
            "removed_by": removed_by_data.get('nombre', '') if removed_by_data else '',
            "removed_by_email": removed_by_data.get('email', '') if removed_by_data else '',
        })

    # Ordenar por fecha de asignación (más reciente primero)
    history.sort(key=lambda x: x.get('assigned_at') or '', reverse=True)

    return jsonify({
        "success": True,
        "collaborator": {
            "_id": str(collaborator_data.get('_id')),
            "nombre": collaborator_data.get('nombre', ''),
            "email": collaborator_data.get('email', ''),
            "rut": collaborator_data.get('rut', '')
        },
        "history": history
    })