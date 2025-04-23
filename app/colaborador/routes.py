#app/colaborador/routes.py
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from datetime import datetime
from bson.objectid import ObjectId

from . import colaborador_bp
from ..auth.utils import role_required
from .. import mongo

from flask import jsonify
from ..models.task import Task

# Constante para la colección de metadatos de la base de datos
METADATA_COLLECTION = 'db_metadata'

@colaborador_bp.route('/dashboard')
@login_required
@role_required(['colaborador'])
def dashboard():
    """Dashboard para el rol de colaborador."""
    user_data = mongo.db.users.find_one({"_id": ObjectId(current_user.get_id())})

    if not user_data:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('auth.login'))

    # Obtener iniciativas asignadas activas
    assigned_initiatives = user_data.get('iniciativas', [])
    active_initiatives = [i for i in assigned_initiatives if i.get('active', True)]

    stats = {
        'total_tasks': 0,  # Puedes implementar la lógica de tareas más adelante
        'completed_tasks': 0,
        'pending_tasks': 0,
        'total_iniciativas': len(active_initiatives)
    }

    # Obtener detalles de las iniciativas activas
    initiative_details = []
    if active_initiatives:
        initiative_ids = [ObjectId(i.get('initiative_id')) for i in active_initiatives]

        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            initiatives_coll = mongo.db[parts[0]][parts[1]]
        else:
            initiatives_coll = mongo.db[collection_name]

        initiatives = list(initiatives_coll.find({
            "_id": {"$in": initiative_ids}
        }))

        # Mapear la información de asignación a cada iniciativa
        for initiative in initiatives:
            # Buscar la información de asignación correspondiente
            assignment_info = next(
                (ai for ai in active_initiatives if ai.get('initiative_id') == str(initiative['_id'])),
                None
            )

            if assignment_info:
                # Obtener el nombre del usuario que asignó
                assigner = None
                if assignment_info.get('assigned_by'):
                    assigner = mongo.db.users.find_one(
                        {"_id": ObjectId(assignment_info.get('assigned_by'))},
                        {"nombre": 1, "email": 1}
                    )

                # Añadir el ID de la iniciativa para poder usar en los enlaces al workbench
                initiative_details.append({
                    'id': str(initiative['_id']),
                    'nombre': initiative.get('nombre_iniciativa', initiative.get('nombre', 'Sin nombre')),
                    'descripcion': initiative.get('descripcion', ''),
                    'fecha_asignacion': assignment_info.get('assigned_at'),
                    'asignado_por': assigner.get('nombre', assigner.get('email',
                                                                      'No especificado')) if assigner else 'No especificado',
                    'estado': initiative.get('estado', 'No Iniciado')
                })

    return render_template(
        'colaborador/dashboard.html',
        stats=stats,
        user_data=user_data,
        iniciativas=initiative_details
    )

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


# Agregar esta ruta en tu archivo colaborador/routes.py

@colaborador_bp.route('/mis-iniciativas')
@login_required
@role_required(['colaborador'])
def my_initiatives():
    """Mostrar las iniciativas asignadas al colaborador."""
    try:
        # Obtener datos del usuario actual
        user = mongo.db.users.find_one({"_id": ObjectId(current_user.get_id())})

        if not user:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('colaborador.dashboard'))

        # Obtener IDs de iniciativas asignadas
        assigned_initiatives = user.get('iniciativas', [])
        active_initiative_ids = []

        for iniciativa in assigned_initiatives:
            if iniciativa.get('active', True):
                active_initiative_ids.append(ObjectId(iniciativa.get('initiative_id')))

        # Obtener detalles de las iniciativas desde la colección
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            initiatives_coll = mongo.db[parts[0]][parts[1]]
        else:
            initiatives_coll = mongo.db[collection_name]

        initiatives = list(initiatives_coll.find({
            "_id": {"$in": active_initiative_ids}
        }))

        # Para cada iniciativa, obtener los otros colaboradores asignados
        initiatives_with_collaborators = []
        for initiative in initiatives:
            # Buscar todos los usuarios asignados a esta iniciativa
            assigned_user_ids = initiative.get('assigned_users', [])
            other_collaborators = []

            if assigned_user_ids:
                # Obtener detalles de otros colaboradores (excluyendo al usuario actual)
                other_collaborators = list(mongo.db.users.find({
                    "_id": {"$in": [ObjectId(uid) for uid in assigned_user_ids if uid != str(current_user.get_id())]},
                    "role": {"$in": ["colaborador", "director"]}
                }))

            # Encontrar la información de asignación para esta iniciativa
            assignment_info = None
            for asig in assigned_initiatives:
                if asig.get('initiative_id') == str(initiative['_id']):
                    assignment_info = asig
                    break

            initiatives_with_collaborators.append({
                'iniciativa': initiative,
                'otros_colaboradores': other_collaborators,
                'fecha_asignacion': assignment_info.get('assigned_at') if assignment_info else None,
                'asignado_por': assignment_info.get('assigned_by') if assignment_info else None
            })

        return render_template(
            'colaborador/initiatives.html',
            initiatives=initiatives_with_collaborators
        )
    except Exception as e:
        flash(f'Error al cargar iniciativas: {e}', 'danger')
        return redirect(url_for('colaborador.dashboard'))


@colaborador_bp.route('/iniciativas/<iniciativa_id>')
@login_required
@role_required(['colaborador'])
def view_initiative_detail(iniciativa_id):
    """Ver detalles de una iniciativa específica asignada al colaborador."""
    try:
        # Verificar que el usuario tiene acceso a esta iniciativa
        user = mongo.db.users.find_one({"_id": ObjectId(current_user.get_id())})

        if not user:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('colaborador.my_initiatives'))

        # Verificar si la iniciativa está asignada al usuario
        has_access = False
        for iniciativa in user.get('iniciativas', []):
            if (iniciativa.get('initiative_id') == iniciativa_id and
                    iniciativa.get('active', True)):
                has_access = True
                break

        if not has_access:
            flash('No tienes acceso a esta iniciativa', 'danger')
            return redirect(url_for('colaborador.my_initiatives'))

        # Obtener detalles de la iniciativa
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            initiatives_coll = mongo.db[parts[0]][parts[1]]
        else:
            initiatives_coll = mongo.db[collection_name]

        initiative = initiatives_coll.find_one({"_id": ObjectId(iniciativa_id)})

        if not initiative:
            flash('Iniciativa no encontrada', 'danger')
            return redirect(url_for('colaborador.my_initiatives'))

        # Obtener otros colaboradores asignados
        assigned_user_ids = initiative.get('assigned_users', [])
        other_collaborators = []

        if assigned_user_ids:
            other_collaborators = list(mongo.db.users.find({
                "_id": {"$in": [ObjectId(uid) for uid in assigned_user_ids if uid != str(current_user.get_id())]},
                "role": {"$in": ["colaborador", "director"]}
            }))

        # Obtener historial de cambios (solo los más recientes)
        change_history = list(mongo.db.modification_history.find({
            "initiative_id": iniciativa_id
        }).sort("timestamp", -1).limit(10))

        return render_template(
            'colaborador/initiative_detail.html',
            initiative=initiative,
            other_collaborators=other_collaborators,
            change_history=change_history
        )
    except Exception as e:
        #print(f"Error en view_initiative_detail: {str(e)}")  # Para debugging
        import traceback
        traceback.print_exc()  # Para debugging
        flash(f'Error al cargar detalles de la iniciativa: {e}', 'danger')
        return redirect(url_for('colaborador.my_initiatives'))


@colaborador_bp.route('/iniciativas/<iniciativa_id>/editar', methods=['GET', 'POST'])
@login_required
@role_required(['colaborador'])
def edit_initiative(iniciativa_id):
    """Permitir al colaborador editar campos específicos de una iniciativa."""
    try:
        # Verificar que el usuario tiene acceso a esta iniciativa
        user = mongo.db.users.find_one({"_id": ObjectId(current_user.get_id())})

        if not user:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('colaborador.my_initiatives'))

        # Verificar si la iniciativa está asignada al usuario
        has_access = False
        for iniciativa in user.get('iniciativas', []):
            if (iniciativa.get('initiative_id') == iniciativa_id and
                    iniciativa.get('active', True)):
                has_access = True
                break

        if not has_access:
            flash('No tienes acceso a esta iniciativa', 'danger')
            return redirect(url_for('colaborador.my_initiatives'))

        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            initiatives_coll = mongo.db[parts[0]][parts[1]]
        else:
            initiatives_coll = mongo.db[collection_name]

        initiative = initiatives_coll.find_one({"_id": ObjectId(iniciativa_id)})

        if not initiative:
            flash('Iniciativa no encontrada', 'danger')
            return redirect(url_for('colaborador.my_initiatives'))

        # Definir campos editables por colaboradores
        editable_fields = ['estado', 'avance', 'comentarios', 'ultima_actualizacion']

        if request.method == 'POST':
            # Obtener solo los campos permitidos para edición
            update_data = {}
            modified_fields = []

            for field in editable_fields:
                if field in request.form:
                    new_value = request.form.get(field)
                    # Convertir a número si es el campo de avance
                    if field == 'avance':
                        try:
                            new_value = int(new_value)
                        except (ValueError, TypeError):
                            new_value = 0

                    # Solo actualizar si el valor ha cambiado
                    if field in initiative:
                        if str(initiative[field]) != str(new_value):
                            update_data[field] = new_value
                            modified_fields.append(field)
                    elif new_value:  # Si el campo no existe pero tiene un valor nuevo
                        update_data[field] = new_value
                        modified_fields.append(field)

            if update_data:
                # Agregar fecha de actualización
                update_data['ultima_actualizacion'] = datetime.utcnow()

                # Actualizar la iniciativa
                result = initiatives_coll.update_one(
                    {"_id": ObjectId(iniciativa_id)},
                    {"$set": update_data}
                )

                if result.modified_count > 0:
                    # Registrar la modificación en el historial
                    history_entry = {
                        "initiative_id": iniciativa_id,
                        "type": "update",
                        "user_id": current_user.get_id(),
                        "user_email": current_user.email,
                        "timestamp": datetime.utcnow(),
                        "fields_modified": modified_fields,
                        "changes": update_data
                    }
                    mongo.db.modification_history.insert_one(history_entry)

                    flash('Cambios guardados correctamente', 'success')
                else:
                    flash('No se realizaron cambios', 'info')
            else:
                flash('No hay cambios para guardar', 'info')

            return redirect(url_for('colaborador.view_initiative_detail', iniciativa_id=iniciativa_id))

        # Para GET, preparar los campos editables para mostrar en el formulario
        fields_to_show = {}
        for field in editable_fields:
            if field in initiative:
                fields_to_show[field] = initiative[field]
            else:
                # Valores por defecto para campos que no existen
                if field == 'estado':
                    fields_to_show[field] = 'activo'
                elif field == 'avance':
                    fields_to_show[field] = 0
                else:
                    fields_to_show[field] = ''

        return render_template(
            'colaborador/edit_initiative.html',
            initiative=initiative,
            editable_fields=fields_to_show,
            iniciativa_id=iniciativa_id
        )
    except Exception as e:
        #print(f"Error en edit_initiative: {str(e)}")  # Para debugging
        import traceback
        traceback.print_exc()  # Para debugging
        flash(f'Error al editar la iniciativa: {e}', 'danger')
        return redirect(url_for('colaborador.my_initiatives'))


# Añadir esta nueva ruta a app/colaborador/routes.py

# Añadir a app/colaborador/routes.py

@colaborador_bp.route('/iniciativas/<iniciativa_id>/workbench')
@login_required
@role_required(['colaborador'])
def workbench(iniciativa_id):
    """Vista del área de trabajo para una iniciativa específica."""
    try:
        # Verificar que el colaborador tiene acceso a esta iniciativa
        user = mongo.db.users.find_one({"_id": ObjectId(current_user.get_id())})
        if not user:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('colaborador.dashboard'))

        # Verificar si la iniciativa está asignada al usuario
        has_access = False
        for iniciativa in user.get('iniciativas', []):
            if iniciativa.get('initiative_id') == iniciativa_id and iniciativa.get('active', True):
                has_access = True
                break

        if not has_access:
            flash('No tienes acceso a esta iniciativa', 'danger')
            return redirect(url_for('colaborador.my_initiatives'))

        # Obtener detalles de la iniciativa
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            initiatives_coll = mongo.db[parts[0]][parts[1]]
        else:
            initiatives_coll = mongo.db[collection_name]

        initiative = initiatives_coll.find_one({"_id": ObjectId(iniciativa_id)})

        if not initiative:
            flash('Iniciativa no encontrada', 'danger')
            return redirect(url_for('colaborador.my_initiatives'))

        # Obtener tareas relacionadas con esta iniciativa
        tasks = list(mongo.db.tasks.find({"initiative_id": iniciativa_id}).sort("created_at", -1))

        # Obtener información de los usuarios para mostrar nombres
        user_ids = set()
        for task in tasks:
            user_ids.add(task.get('created_by'))
            if task.get('completed_by'):
                user_ids.add(task.get('completed_by'))
            if task.get('assigned_to'):
                user_ids.update(task.get('assigned_to'))

        users = {str(u['_id']): u for u in
                 mongo.db.users.find({"_id": {"$in": [ObjectId(uid) for uid in user_ids if uid]}})}

        # Obtener colaboradores asignados a la iniciativa
        assigned_user_ids = initiative.get('assigned_users', [])
        other_collaborators = list(mongo.db.users.find({
            "_id": {"$in": [ObjectId(uid) for uid in assigned_user_ids if uid]},
            "_id": {"$ne": ObjectId(current_user.get_id())}
        }))

        # Definir estados y calcular progreso
        estados = [
            'No Iniciado', 'Formulación', 'Revisión', 'Corrección', 'Elegible',
            'Financiado', 'Firma Convenio', 'Preparación Bases', 'Licitación',
            'Adjudicación', 'Firma Contrato', 'Entregado', 'En Ejecución', 'Finalizado'
        ]

        estado_actual = initiative.get('estado', 'No Iniciado')
        progreso = 0

        if estado_actual in estados:
            indice_estado = estados.index(estado_actual)
            progreso = (indice_estado / (len(estados) - 1)) * 100

        return render_template(
            'colaborador/workbench.html',
            initiative=initiative,
            iniciativa_id=iniciativa_id,
            other_collaborators=other_collaborators,
            estados=estados,
            estado_actual=estado_actual,
            progreso=progreso,
            tasks=tasks,
            users=users
        )
    except Exception as e:
        import traceback
        print(f"Error en workbench: {traceback.format_exc()}")
        flash(f'Error al cargar el área de trabajo: {str(e)}', 'danger')
        return redirect(url_for('colaborador.my_initiatives'))


# Ruta para ver todas las tareas asignadas al colaborador
@colaborador_bp.route('/mis-tareas')
@login_required
@role_required(['colaborador'])
def my_tasks():
    """Ver todas las tareas asignadas al colaborador actual."""
    try:
        # Obtener las tareas donde el colaborador está asignado
        assigned_tasks = list(mongo.db.tasks.find({
            "$or": [
                {"assigned_to": current_user.get_id()},
                {"created_by": current_user.get_id()}
            ]
        }).sort("created_at", -1))

        # Obtener las iniciativas relacionadas con las tareas
        initiative_ids = {task['initiative_id'] for task in assigned_tasks}

        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            initiatives_coll = mongo.db[parts[0]][parts[1]]
        else:
            initiatives_coll = mongo.db[collection_name]

        initiatives = {
            str(init['_id']): init for init in initiatives_coll.find({
                "_id": {"$in": [ObjectId(i_id) for i_id in initiative_ids if i_id]}
            })
        }

        # Obtener información de los usuarios para mostrar nombres
        user_ids = set()
        for task in assigned_tasks:
            user_ids.add(task.get('created_by'))
            if task.get('completed_by'):
                user_ids.add(task.get('completed_by'))
            if task.get('assigned_to'):
                user_ids.update(task.get('assigned_to'))

        users = {str(u['_id']): u for u in
                 mongo.db.users.find({"_id": {"$in": [ObjectId(uid) for uid in user_ids if uid]}})}

        # Agrupar tareas por iniciativa
        tasks_by_initiative = {}
        for task in assigned_tasks:
            initiative_id = task['initiative_id']
            if initiative_id not in tasks_by_initiative:
                tasks_by_initiative[initiative_id] = []
            tasks_by_initiative[initiative_id].append(task)

        return render_template(
            'colaborador/tasks.html',
            tasks=assigned_tasks,
            tasks_by_initiative=tasks_by_initiative,
            initiatives=initiatives,
            users=users
        )
    except Exception as e:
        import traceback
        print(f"Error al cargar tareas: {traceback.format_exc()}")
        flash(f'Error al cargar las tareas: {str(e)}', 'danger')
        return redirect(url_for('colaborador.dashboard'))


# Ruta para ver tareas de una iniciativa específica
@colaborador_bp.route('/iniciativas/<iniciativa_id>/tareas')
@login_required
@role_required(['colaborador'])
def view_initiative_tasks(iniciativa_id):
    """Ver tareas de una iniciativa específica."""
    try:
        # Verificar que el colaborador tiene acceso a esta iniciativa
        user = mongo.db.users.find_one({"_id": ObjectId(current_user.get_id())})
        if not user:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('colaborador.dashboard'))

        # Verificar si la iniciativa está asignada al usuario
        has_access = False
        for iniciativa in user.get('iniciativas', []):
            if iniciativa.get('initiative_id') == iniciativa_id and iniciativa.get('active', True):
                has_access = True
                break

        if not has_access:
            flash('No tienes acceso a esta iniciativa', 'danger')
            return redirect(url_for('colaborador.my_initiatives'))

        # Obtener detalles de la iniciativa
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            initiatives_coll = mongo.db[parts[0]][parts[1]]
        else:
            initiatives_coll = mongo.db[collection_name]

        iniciativa = initiatives_coll.find_one({"_id": ObjectId(iniciativa_id)})

        if not iniciativa:
            flash('Iniciativa no encontrada', 'danger')
            return redirect(url_for('colaborador.my_initiatives'))

        # Obtener tareas relacionadas con esta iniciativa
        tasks = list(mongo.db.tasks.find({"initiative_id": iniciativa_id}).sort("created_at", -1))
        tasks_by_initiative = {iniciativa_id: tasks}
        initiatives = {iniciativa_id: iniciativa}

        # Obtener información de los usuarios para mostrar nombres
        user_ids = set()
        for task in tasks:
            user_ids.add(task.get('created_by'))
            if task.get('completed_by'):
                user_ids.add(task.get('completed_by'))
            if task.get('assigned_to'):
                user_ids.update(task.get('assigned_to'))

        users = {str(u['_id']): u for u in
                 mongo.db.users.find({"_id": {"$in": [ObjectId(uid) for uid in user_ids if uid]}})}

        # Obtener colaboradores asignados a la iniciativa para el formulario de creación
        assigned_user_ids = iniciativa.get('assigned_users', [])
        other_collaborators = list(mongo.db.users.find({
            "_id": {"$in": [ObjectId(uid) for uid in assigned_user_ids if uid]},
            "role": {"$in": ["colaborador", "director"]}
        }))

        return render_template(
            'colaborador/initiative_tasks.html',
            initiative=iniciativa,
            initiatives=initiatives,
            tasks=tasks,
            tasks_by_initiative=tasks_by_initiative,
            users=users,
            iniciativa_id=iniciativa_id,
            other_collaborators=other_collaborators
        )
    except Exception as e:
        import traceback
        print(f"Error al ver tareas de iniciativa: {traceback.format_exc()}")
        flash(f'Error al cargar las tareas: {str(e)}', 'danger')
        return redirect(url_for('colaborador.my_initiatives'))


# Ruta para añadir una nueva tarea
@colaborador_bp.route('/iniciativas/<iniciativa_id>/tareas/crear', methods=['POST'])
@login_required
@role_required(['colaborador'])
def create_task(iniciativa_id):
    """Crear una nueva tarea para una iniciativa."""
    try:
        # Verificar que el colaborador tiene acceso a esta iniciativa
        user = mongo.db.users.find_one({"_id": ObjectId(current_user.get_id())})
        if not user:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('colaborador.dashboard'))

        # Verificar si la iniciativa está asignada al usuario
        has_access = False
        for iniciativa in user.get('iniciativas', []):
            if iniciativa.get('initiative_id') == iniciativa_id and iniciativa.get('active', True):
                has_access = True
                break

        if not has_access:
            flash('No tienes acceso a esta iniciativa', 'danger')
            return redirect(url_for('colaborador.my_initiatives'))

        # Obtener datos del formulario
        content = request.form.get('content', '').strip()
        assigned_users = request.form.getlist('assigned_users')

        # Validar contenido
        if not content:
            flash('El contenido de la tarea es obligatorio', 'danger')
            return redirect(url_for('colaborador.view_initiative_tasks', iniciativa_id=iniciativa_id))

        # Validar longitud (máximo 200 palabras)
        words = content.split()
        if len(words) > 200:
            content = ' '.join(words[:200])
            flash('El contenido ha sido truncado a 200 palabras', 'warning')

        # Crear la tarea
        task = Task(
            content=content,
            initiative_id=iniciativa_id,
            created_by=current_user.get_id(),
            assigned_to=assigned_users
        )

        # Guardar en la base de datos
        mongo.db.tasks.insert_one(task.to_dict())

        flash('Tarea creada correctamente', 'success')
        return redirect(url_for('colaborador.view_initiative_tasks', iniciativa_id=iniciativa_id))
    except Exception as e:
        import traceback
        print(f"Error al crear tarea: {traceback.format_exc()}")
        flash(f'Error al crear la tarea: {str(e)}', 'danger')
        return redirect(url_for('colaborador.view_initiative_tasks', iniciativa_id=iniciativa_id))


# Ruta para marcar una tarea como completada
@colaborador_bp.route('/tareas/<task_id>/completar', methods=['POST'])
@login_required
@role_required(['colaborador'])
def complete_task(task_id):
    """Marcar una tarea como completada."""
    try:
        # Buscar la tarea
        task_data = mongo.db.tasks.find_one({"_id": ObjectId(task_id)})

        if not task_data:
            return jsonify({"success": False, "message": "Tarea no encontrada"})

        # Verificar que el usuario tiene permiso para completar esta tarea
        if (current_user.get_id() not in task_data.get('assigned_to', []) and
                current_user.get_id() != task_data.get('created_by')):
            return jsonify({
                "success": False,
                "message": "No tienes permiso para completar esta tarea"
            })

        # Crear objeto Task y marcar como completada
        task = Task.from_dict(task_data)
        task.complete(current_user.get_id())

        # Actualizar en la base de datos
        mongo.db.tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {
                "is_completed": task.is_completed,
                "completed_by": task.completed_by,
                "completed_at": task.completed_at
            }}
        )

        return jsonify({
            "success": True,
            "message": "Tarea completada",
            "completed_by": current_user.email,
            "completed_at": task.completed_at.strftime('%d/%m/%Y %H:%M')
        })
    except Exception as e:
        import traceback
        print(f"Error al completar tarea: {traceback.format_exc()}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"})


# Ruta para reabrir una tarea
@colaborador_bp.route('/tareas/<task_id>/reabrir', methods=['POST'])
@login_required
@role_required(['colaborador'])
def reopen_task(task_id):
    """Reabrir una tarea que estaba completada."""
    try:
        # Buscar la tarea
        task_data = mongo.db.tasks.find_one({"_id": ObjectId(task_id)})

        if not task_data:
            return jsonify({"success": False, "message": "Tarea no encontrada"})

        # Verificar que el usuario tiene permiso para reabrir esta tarea
        if (current_user.get_id() not in task_data.get('assigned_to', []) and
                current_user.get_id() != task_data.get('created_by')):
            return jsonify({
                "success": False,
                "message": "No tienes permiso para reabrir esta tarea"
            })

        # Crear objeto Task y reabrir
        task = Task.from_dict(task_data)
        task.reopen()

        # Actualizar en la base de datos
        mongo.db.tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {
                "is_completed": task.is_completed,
                "completed_by": task.completed_by,
                "completed_at": task.completed_at
            }}
        )

        return jsonify({
            "success": True,
            "message": "Tarea reabierta"
        })
    except Exception as e:
        import traceback
        print(f"Error al reabrir tarea: {traceback.format_exc()}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"})