#app/colaborador/routes.py
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from datetime import datetime
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
from . import colaborador_bp
from ..auth.utils import role_required
from .. import mongo
from flask import jsonify
from ..models.task import Task
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer, ListFlowable, ListItem
from reportlab.lib.units import inch
import base64
import os

# Constante para la colección de metadatos de la base de datos
METADATA_COLLECTION = 'db_metadata'

@colaborador_bp.route('/dashboard')
@login_required
@role_required(['colaborador'])
def dashboard():
    """Dashboard unificado para el rol de colaborador."""
    try:
        # Obtener datos del usuario actual
        user_data = mongo.db.users.find_one({"_id": ObjectId(current_user.get_id())})
        if not user_data:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('auth.login'))

        # Obtener iniciativas asignadas activas
        assigned_initiatives = user_data.get('iniciativas', [])
        active_initiatives = [i for i in assigned_initiatives if i.get('active', True)]

        # Obtener detalles de las iniciativas activas
        initiative_details = []
        initiative_ids = []

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

                    # Calcular progreso basado en el estado
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

                    # Añadir el ID de la iniciativa para poder usar en los enlaces
                    initiative_details.append({
                        'id': str(initiative['_id']),
                        'nombre': initiative.get('nombre_iniciativa', initiative.get('nombre', 'Sin nombre')),
                        'codigo': initiative.get('cod', initiative.get('codigo')),
                        'descripcion': initiative.get('descripcion', ''),
                        'fecha_asignacion': assignment_info.get('assigned_at'),
                        'estado': estado_actual,
                        'progreso': progreso,
                        'asignado_por': assigner.get('nombre', assigner.get('email',
                                                                            'No especificado')) if assigner else 'No especificado'
                    })

        # Ordenar las iniciativas por fecha de asignación (más recientes primero)
        initiative_details.sort(key=lambda x: x.get('fecha_asignacion', datetime(1900, 1, 1)), reverse=True)

        # Obtener tareas del usuario
        tasks = list(mongo.db.tasks.find({
            "$or": [
                {"assigned_to": current_user.get_id()},
                {"created_by": current_user.get_id()}
            ]
        }).sort("created_at", -1))

        # Contar tareas pendientes por iniciativa
        pending_tasks_by_initiative = {}
        for task in tasks:
            if not task.get('is_completed', False):
                initiative_id = task.get('initiative_id')
                if initiative_id not in pending_tasks_by_initiative:
                    pending_tasks_by_initiative[initiative_id] = 0
                pending_tasks_by_initiative[initiative_id] += 1

        # Añadir contador de tareas pendientes a cada iniciativa
        for initiative in initiative_details:
            initiative['pending_tasks_count'] = pending_tasks_by_initiative.get(initiative['id'], 0)

        # Separar tareas pendientes y completadas
        pending_tasks = []
        completed_tasks = []

        # Obtener nombres de iniciativas para las tareas
        task_initiative_ids = {task['initiative_id'] for task in tasks}
        task_initiatives = {}

        if task_initiative_ids:
            collection_name = current_app.config['INITIATIVES_COLLECTION']
            parts = collection_name.split('.')
            if len(parts) > 1:
                initiatives_coll = mongo.db[parts[0]][parts[1]]
            else:
                initiatives_coll = mongo.db[collection_name]

            for init in initiatives_coll.find({"_id": {"$in": [ObjectId(id) for id in task_initiative_ids]}}):
                task_initiatives[str(init['_id'])] = init.get('nombre_iniciativa', init.get('nombre', 'Sin nombre'))

        # Procesar tareas
        for task in tasks:
            # Añadir nombre de la iniciativa a la tarea
            task['initiative_name'] = task_initiatives.get(task['initiative_id'], 'Iniciativa desconocida')

            if task.get('is_completed', False):
                completed_tasks.append(task)
            else:
                pending_tasks.append(task)

        # Limitar a las 5 tareas más recientes para el dashboard
        pending_tasks = pending_tasks[:5]
        completed_tasks = completed_tasks[:5]

        # Estadísticas
        stats = {
            'total_tasks': len(tasks),
            'completed_tasks': len([t for t in tasks if t.get('is_completed', False)]),
            'pending_tasks': len([t for t in tasks if not t.get('is_completed', False)]),
            'total_iniciativas': len(initiative_details)
        }

        # Obtener actividad reciente (del historial de modificaciones y tareas)
        activity_log = []

        # Añadir historial de cambios de estado de iniciativas
        estado_logs = list(mongo.db.estado_iniciativa_historial.find({
            "initiative_id": {"$in": [str(id) for id in initiative_ids]}
        }).sort("timestamp", -1).limit(5))

        for log in estado_logs:
            activity_log.append({
                'timestamp': log.get('timestamp'),
                'description': f"Cambio de estado en {task_initiatives.get(log.get('initiative_id'), 'Iniciativa')} a {log.get('new_state')}",
                'icon': 'fas fa-exchange-alt'
            })

        # Añadir tareas completadas como actividad
        for task in completed_tasks[:3]:  # Limitamos a las 3 más recientes
            # Obtener nombre del usuario que completó
            completer = None
            if task.get('completed_by'):
                completer = mongo.db.users.find_one(
                    {"_id": ObjectId(task.get('completed_by'))},
                    {"nombre": 1, "email": 1}
                )

            activity_log.append({
                'timestamp': task.get('completed_at'),
                'description': f"Tarea completada en {task.get('initiative_name')}: {task.get('content')[:50]}...",
                'icon': 'fas fa-check-circle'
            })

        # Ordenar actividad por fecha (más reciente primero)
        activity_log.sort(key=lambda x: x['timestamp'], reverse=True)
        activity_log = activity_log[:5]  # Limitar a 5 actividades

        # Obtener fecha actual para el dashboard
        now = datetime.now()

        return render_template(
            'colaborador/dashboard.html',
            user_data=user_data,
            stats=stats,
            iniciativas=initiative_details,
            pending_tasks=pending_tasks,
            completed_tasks=completed_tasks,
            activity_log=activity_log,
            now=now
        )
    except Exception as e:
        import traceback
        print(f"Error en dashboard: {traceback.format_exc()}")
        flash(f'Error al cargar el dashboard: {str(e)}', 'danger')
        return redirect(url_for('auth.login'))


@colaborador_bp.route('/profile')
@login_required
@role_required(['colaborador'])
def profile():
    """Perfil mejorado del colaborador."""
    try:
        # Obtener datos completos del usuario
        user_data = mongo.db.users.find_one({"_id": ObjectId(current_user.get_id())})

        if not user_data:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('colaborador.dashboard'))

        # Obtener estadísticas para mostrar en el perfil
        # 1. Contar iniciativas asignadas
        assigned_initiatives = user_data.get('iniciativas', [])
        active_initiatives = [i for i in assigned_initiatives if i.get('active', True)]

        # 2. Contar tareas totales, completadas y calcular tasa de finalización
        tasks = list(mongo.db.tasks.find({
            "$or": [
                {"assigned_to": current_user.get_id()},
                {"created_by": current_user.get_id()}
            ]
        }))

        completed_tasks = [t for t in tasks if t.get('is_completed', False)]

        completion_rate = 0
        if tasks:
            completion_rate = round((len(completed_tasks) / len(tasks)) * 100)

        stats = {
            'total_iniciativas': len(active_initiatives),
            'total_tasks': len(tasks),
            'completed_tasks': len(completed_tasks),
            'completion_rate': completion_rate
        }

        return render_template(
            'colaborador/profile.html',
            current_user=user_data,
            stats=stats
        )

    except Exception as e:
        import traceback
        print(f"Error en profile: {traceback.format_exc()}")
        flash(f'Error al cargar el perfil: {str(e)}', 'danger')
        return redirect(url_for('colaborador.dashboard'))


@colaborador_bp.route('/profile/update', methods=['POST'])
@login_required
@role_required(['colaborador'])
def update_profile():
    """Actualizar datos del perfil del colaborador."""
    try:
        # Obtener campos del formulario
        nombre = request.form.get('nombre')
        rut = request.form.get('rut')
        telefono = request.form.get('telefono')
        direccion = request.form.get('direccion')
        cargo = request.form.get('cargo')
        area_especializacion = request.form.get('area_especializacion')

        # Procesar listas (separadas por coma)
        titulos_raw = request.form.get('titulos', '')
        titulos = [t.strip() for t in titulos_raw.split(',') if t.strip()] if titulos_raw else []

        certificaciones_raw = request.form.get('certificaciones', '')
        certificaciones = [c.strip() for c in certificaciones_raw.split(',') if
                           c.strip()] if certificaciones_raw else []

        idiomas_raw = request.form.get('idiomas', '')
        idiomas = [i.strip() for i in idiomas_raw.split(',') if i.strip()] if idiomas_raw else []

        # Procesar imagen de perfil si se ha subido
        profile_image = request.files.get('profile_image')
        profile_image_filename = None

        if profile_image and profile_image.filename:
            # Validar tipo de archivo
            if profile_image.content_type.startswith('image/'):
                # Generar nombre de archivo único
                filename = secure_filename(profile_image.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"

                # Preparar ruta para guardar
                uploads_folder = os.path.join(
                    current_app.static_folder, 'uploads', 'profile'
                )
                os.makedirs(uploads_folder, exist_ok=True)

                # Guardar imagen original
                file_path = os.path.join(uploads_folder, unique_filename)
                profile_image.save(file_path)

                # Procesar imagen para estandarizar tamaño
                try:
                    from PIL import Image

                    # Abrir imagen
                    img = Image.open(file_path)

                    # Recortar a cuadrado si no lo es
                    width, height = img.size
                    size = min(width, height)
                    left = (width - size) // 2
                    top = (height - size) // 2
                    right = left + size
                    bottom = top + size
                    img = img.crop((left, top, right, bottom))

                    # Redimensionar a 300x300
                    img = img.resize((300, 300), Image.LANCZOS)

                    # Guardar imagen procesada
                    img.save(file_path)

                    # Guardar nombre de archivo para la BD
                    profile_image_filename = unique_filename

                except Exception as img_error:
                    # Si hay error al procesar, mantener la imagen original
                    print(f"Error al procesar imagen: {str(img_error)}")
                    profile_image_filename = unique_filename
            else:
                flash('El archivo seleccionado no es una imagen válida', 'warning')

        # Preparar datos para actualizar
        update_data = {
            "nombre": nombre,
            "rut": rut,
            "telefono": telefono,
            "direccion": direccion,
            "cargo": cargo,
            "area_especializacion": area_especializacion,
            "titulos": titulos,
            "certificaciones": certificaciones,
            "idiomas": idiomas,
        }

        # Añadir imagen de perfil si se ha procesado
        if profile_image_filename:
            update_data["profile_image"] = profile_image_filename

        # Actualizar en la base de datos
        result = mongo.db.users.update_one(
            {"_id": ObjectId(current_user.get_id())},
            {"$set": update_data}
        )

        if result.modified_count > 0:
            flash('Perfil actualizado correctamente', 'success')
        else:
            flash('No se realizaron cambios en el perfil', 'info')

        return redirect(url_for('colaborador.profile'))

    except Exception as e:
        import traceback
        print(f"Error al actualizar perfil: {traceback.format_exc()}")
        flash(f'Error al actualizar el perfil: {str(e)}', 'danger')
        return redirect(url_for('colaborador.profile'))


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
    """Permitir al colaborador editar todos los campos de una iniciativa."""
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

        # Obtener la colección correcta
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            initiatives_coll = mongo.db[parts[0]][parts[1]]
        else:
            initiatives_coll = mongo.db[collection_name]

        # Obtener la iniciativa
        initiative = initiatives_coll.find_one({"_id": ObjectId(iniciativa_id)})

        if not initiative:
            flash('Iniciativa no encontrada', 'danger')
            return redirect(url_for('colaborador.my_initiatives'))

        if request.method == 'POST':
            # Recopilar todos los campos del formulario
            update_data = {}
            modified_fields = []

            # Lista completa de campos a verificar
            form_fields = [
                'nombre_iniciativa', 'cod', 'descripcion', 'tipo', 'categoria',
                'estado', 'avance', 'comentarios', 'comuna', 'region', 'direccion',
                'contacto_nombre', 'contacto_telefono', 'contacto_email',
                'fuente_financiamiento', 'monto', 'etapa_financiera'
            ]

            for field in form_fields:
                if field in request.form:
                    new_value = request.form.get(field)

                    # Formatear valores especiales
                    if field == 'avance':
                        try:
                            new_value = int(new_value)
                        except (ValueError, TypeError):
                            new_value = 0
                    elif field == 'monto':
                        # Eliminar separadores de miles antes de guardar
                        new_value = new_value.replace('.', '')
                        if new_value:
                            try:
                                new_value = int(new_value)
                            except ValueError:
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

            # Verificar si debemos redirigir al workbench
            if 'redirect_to_workbench' in request.form:
                return redirect(url_for('colaborador.workbench', iniciativa_id=iniciativa_id))
            else:
                return redirect(url_for('colaborador.view_initiative_detail', iniciativa_id=iniciativa_id))

        # Para GET, renderizar el formulario con todos los campos de la iniciativa
        return render_template(
            'colaborador/edit_initiative.html',
            initiative=initiative,
            iniciativa_id=iniciativa_id
        )
    except Exception as e:
        import traceback
        traceback.print_exc()  # Para debugging
        flash(f'Error al editar la iniciativa: {e}', 'danger')
        return redirect(url_for('colaborador.my_initiatives'))

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

        # Obtener archivos relacionados con esta iniciativa - NUEVO
        files = list(mongo.db.files.find({
            "initiative_id": iniciativa_id,
            "active": True
        }).sort("uploaded_at", -1))

        # Obtener información de los usuarios para mostrar nombres
        user_ids = set()
        for task in tasks:
            user_ids.add(task.get('created_by'))
            if task.get('completed_by'):
                user_ids.add(task.get('completed_by'))
            if task.get('assigned_to'):
                user_ids.update(task.get('assigned_to'))

        # Añadir los usuarios que han subido archivos - NUEVO
        for file in files:
            user_ids.add(file.get('uploaded_by'))

        users = {str(u['_id']): u for u in
                 mongo.db.users.find({"_id": {"$in": [ObjectId(uid) for uid in user_ids if uid]}})}

        # Obtener colaboradores asignados a la iniciativa
        assigned_user_ids = initiative.get('assigned_users', [])
        other_collaborators = list(mongo.db.users.find({
            "_id": {"$in": [ObjectId(uid) for uid in assigned_user_ids if uid]},
            "_id": {"$ne": ObjectId(current_user.get_id())},
            "role": "colaborador"  # Solo mostrar usuarios con rol de colaborador
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
            users=users,
            files=files,  # NUEVO
            files_enabled=initiative.get('files_enabled', False)  # NUEVO
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

        # Procesar tareas para añadir información adicional
        for task in assigned_tasks:
            # Añadir nombre de la iniciativa
            initiative = initiatives.get(task['initiative_id'])
            if initiative:
                task['initiative_name'] = initiative.get('nombre_iniciativa',
                                                      initiative.get('nombre', 'Sin nombre'))
            else:
                task['initiative_name'] = 'Iniciativa desconocida'

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

        # Separar tareas en pendientes y completadas
        pending_tasks = [t for t in assigned_tasks if not t.get('is_completed', False)]
        completed_tasks = [t for t in assigned_tasks if t.get('is_completed', False)]

        # Agrupar tareas por iniciativa
        tasks_by_initiative = {}
        for task in assigned_tasks:
            initiative_id = task['initiative_id']
            if initiative_id not in tasks_by_initiative:
                tasks_by_initiative[initiative_id] = []
            tasks_by_initiative[initiative_id].append(task)

        # Estadísticas para la página
        stats = {
            'total_tasks': len(assigned_tasks),
            'completed_tasks': len(completed_tasks),
            'pending_tasks': len(pending_tasks)
        }

        return render_template(
            'colaborador/initiative_tasks.html',
            tasks=assigned_tasks,
            pending_tasks=pending_tasks,
            completed_tasks=completed_tasks,
            tasks_by_initiative=tasks_by_initiative,
            initiatives=initiatives,
            users=users,
            stats=stats
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
            "role": "colaborador",  # Solo mostrar usuarios con rol de colaborador
            "_id": {"$ne": ObjectId(current_user.get_id())}  # Excluir al usuario actual
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


# En app/colaborador/routes.py

@colaborador_bp.route('/iniciativas/<iniciativa_id>/minuta', methods=['GET', 'POST'])
@login_required
@role_required(['colaborador'])
def generate_minuta(iniciativa_id):
    """Generar minuta de la iniciativa."""
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

        # Obtener la iniciativa
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            coll = mongo.db[parts[0]][parts[1]]
        else:
            coll = mongo.db[collection_name]

        iniciativa = coll.find_one({"_id": ObjectId(iniciativa_id)})
        if not iniciativa:
            flash('Iniciativa no encontrada', 'danger')
            return redirect(url_for('colaborador.list_initiatives'))

        # Convertir ObjectId a string
        iniciativa_json = {}
        for key, value in iniciativa.items():
            if key == '_id':
                iniciativa_json[key] = str(value)
            elif isinstance(value, ObjectId):
                iniciativa_json[key] = str(value)
            else:
                iniciativa_json[key] = value

        # Obtener archivos asociados a la iniciativa (para imágenes)
        files = list(mongo.db.files.find({
            "initiative_id": iniciativa_id,
            "active": True,
            "file_type": "image"  # Filtrar solo imágenes
        }))

        # Convertir ObjectId a string en los archivos
        files_json = []
        for file in files:
            file_json = {}
            for key, value in file.items():
                if key == '_id' or isinstance(value, ObjectId):
                    file_json[key] = str(value)
                else:
                    file_json[key] = value
            files_json.append(file_json)

        # Si se envió el formulario para generar la minuta
        if request.method == 'POST':
            selected_fields = request.form.getlist('fields')
            field_labels = {}

            # Obtener las etiquetas personalizadas para cada campo
            for field in selected_fields:
                field_labels[field] = request.form.get(f"label_{field}", field.replace('_', ' ').capitalize())

            # Obtener imágenes seleccionadas
            selected_images = request.form.getlist('images')

            # Obtener configuración de la sección "El proyecto contempla"
            show_project_section = 'show_project_section' in request.form
            project_section_title = request.form.get('project_section_title', 'El proyecto contempla:')
            project_features = request.form.get('project_features', '')

            # Actualizar la configuración de minuta
            minuta_config = {
                "selected_fields": selected_fields,
                "field_labels": field_labels,
                "selected_images": selected_images,
                "title": request.form.get('minuta_title', 'MINUTA PROYECTO'),
                "show_project_section": show_project_section,
                "project_section_title": project_section_title,
                "project_features": project_features,
                "updated_at": datetime.utcnow(),
                "updated_by": current_user.get_id()
            }

            # Actualizar la iniciativa con la configuración de minuta
            coll.update_one(
                {"_id": ObjectId(iniciativa_id)},
                {"$set": {"minuta_config": minuta_config}}
            )

            # Si el botón presionado fue "preview", redirigir a la vista previa
            if 'preview' in request.form:
                return redirect(url_for('colaborador.preview_minuta', iniciativa_id=iniciativa_id))

            # Si fue "download", generar el PDF
            if 'download' in request.form:
                return redirect(url_for('colaborador.download_minuta', iniciativa_id=iniciativa_id))

            flash('Configuración de minuta guardada correctamente', 'success')
            return redirect(url_for('colaborador.generate_minuta', iniciativa_id=iniciativa_id))

        # Para GET, cargar la configuración guardada (si existe)
        minuta_config = iniciativa.get('minuta_config', {})

        return render_template(
            'colaborador/minuta_generator.html',
            iniciativa=iniciativa_json,
            files=files_json,
            minuta_config=minuta_config,
            iniciativa_id=iniciativa_id
        )
    except Exception as e:
        import traceback
        print(f"Error en generate_minuta: {traceback.format_exc()}")
        flash(f'Error al generar minuta: {str(e)}', 'danger')
        return redirect(url_for('colaborador.view_initiative_detail', iniciativa_id=iniciativa_id))


@colaborador_bp.route('/iniciativas/<iniciativa_id>/minuta/preview')
@login_required
@role_required(['colaborador'])
def preview_minuta(iniciativa_id):
    """Vista previa de la minuta."""
    try:
        # Obtener la iniciativa
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            coll = mongo.db[parts[0]][parts[1]]
        else:
            coll = mongo.db[collection_name]

        iniciativa = coll.find_one({"_id": ObjectId(iniciativa_id)})
        if not iniciativa:
            flash('Iniciativa no encontrada', 'danger')
            return redirect(url_for('colaborador.list_initiatives'))

        # Obtener configuración de minuta
        minuta_config = iniciativa.get('minuta_config', {})
        if not minuta_config:
            flash('No hay configuración de minuta guardada', 'warning')
            return redirect(url_for('colaborador.generate_minuta', iniciativa_id=iniciativa_id))

        # Obtener imágenes seleccionadas
        selected_image_ids = minuta_config.get('selected_images', [])
        images = list(mongo.db.files.find({
            "_id": {"$in": [ObjectId(img_id) for img_id in selected_image_ids if img_id]},
            "active": True
        }))

        return render_template(
            'colaborador/minuta_preview.html',
            iniciativa=iniciativa,
            minuta_config=minuta_config,
            images=images,
            iniciativa_id=iniciativa_id
        )
    except Exception as e:
        flash(f'Error al previsualizar minuta: {str(e)}', 'danger')
        return redirect(url_for('colaborador.generate_minuta', iniciativa_id=iniciativa_id))


@colaborador_bp.route('/iniciativas/<iniciativa_id>/minuta/download')
@login_required
@role_required(['colaborador'])
def download_minuta(iniciativa_id):
    """Descargar minuta como PDF."""
    try:

        # Verificar acceso
        user = mongo.db.users.find_one({"_id": ObjectId(current_user.get_id())})
        if not user:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('colaborador.dashboard'))

        has_access = False
        for iniciativa in user.get('iniciativas', []):
            if iniciativa.get('initiative_id') == iniciativa_id and iniciativa.get('active', True):
                has_access = True
                break

        if not has_access:
            flash('No tienes acceso a esta iniciativa', 'danger')
            return redirect(url_for('colaborador.my_initiatives'))




        # Obtener la iniciativa
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            coll = mongo.db[parts[0]][parts[1]]
        else:
            coll = mongo.db[collection_name]

        iniciativa = coll.find_one({"_id": ObjectId(iniciativa_id)})
        if not iniciativa:
            flash('Iniciativa no encontrada', 'danger')
            return redirect(url_for('colaborador.list_initiatives'))

        # Obtener configuración de minuta
        minuta_config = iniciativa.get('minuta_config', {})
        if not minuta_config:
            flash('No hay configuración de minuta guardada', 'warning')
            return redirect(url_for('colaborador.generate_minuta', iniciativa_id=iniciativa_id))

        # Obtener imágenes seleccionadas
        selected_image_ids = minuta_config.get('selected_images', [])
        images = list(mongo.db.files.find({
            "_id": {"$in": [ObjectId(img_id) for img_id in selected_image_ids if img_id]},
            "active": True
        }))

        # Generar PDF con ReportLab
        buffer = BytesIO()

        # Configuración del documento
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Estilos
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        normal_style = styles['Normal']

        # Lista de elementos para el PDF
        elements = []

        # Título
        elements.append(Paragraph(minuta_config.get('title', 'MINUTA PROYECTO'), title_style))
        elements.append(Spacer(1, 0.25 * inch))

        # Tabla de información
        data = []
        selected_fields = minuta_config.get('selected_fields', [])
        field_labels = minuta_config.get('field_labels', {})

        for field in selected_fields:
            label = field_labels.get(field, field.replace('_', ' ').capitalize())
            value = str(iniciativa.get(field, ''))
            data.append([label, value])

        if data:
            table = Table(data, colWidths=[2 * inch, 4 * inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.25 * inch))


        # Sección "El proyecto contempla" (configurable)
        if minuta_config.get('show_project_section', True):
            section_title = minuta_config.get('project_section_title', 'El proyecto contempla:')
            elements.append(Paragraph(f"<b>{section_title}</b>", normal_style))
            elements.append(Spacer(1, 0.1 * inch))

            # Lista de elementos con viñetas
            bullet_items = []

            project_features = minuta_config.get('project_features', '')
            if project_features:
                feature_lines = project_features.split('\n')
                for line in feature_lines:
                    line = line.strip()
                    if line:
                        # Eliminar el emoji de verificación si ya está presente
                        if line.startswith('✅'):
                            line = line[1:].strip()
                        bullet_items.append(ListItem(Paragraph("✅ " + line, normal_style)))
            elif iniciativa.get('descripcion'):
                desc_lines = iniciativa.get('descripcion').split('\n')
                for line in desc_lines:
                    if line.strip():
                        # Eliminar el emoji de verificación si ya está presente
                        if line.strip().startswith('✅'):
                            line = line[1:].strip()
                        bullet_items.append(ListItem(Paragraph("✅ " + line.strip(), normal_style)))
            else:
                bullet_items.append(
                    ListItem(Paragraph("✅ Construcción y habilitación de infraestructura", normal_style)))

            if bullet_items:
                bullets = ListFlowable(
                    bullet_items,
                    bulletType='bullet',
                    start='',
                    bulletFontName='Helvetica',
                    bulletFontSize=10
                )
                elements.append(bullets)

            elements.append(Spacer(1, 0.25 * inch))

        # Imágenes
        if images:
            for image_doc in images:
                try:
                    img_path = image_doc.get('file_path')
                    if img_path and os.path.exists(img_path):
                        img = Image(img_path)
                        # Ajustar tamaño máximo
                        max_width = 6 * inch
                        max_height = 4 * inch
                        if img.drawWidth > max_width:
                            ratio = max_height / img.drawHeight
                            img.drawWidth = max_width
                            img.drawHeight = img.drawHeight * ratio
                        elements.append(img)
                        elements.append(Spacer(1, 0.1 * inch))
                except Exception as img_error:
                    print(f"Error al procesar imagen {image_doc.get('_id')}: {str(img_error)}")

        # Construir el documento
        doc.build(elements)

        # Obtener el PDF del buffer
        pdf_data = buffer.getvalue()
        buffer.close()

        # Nombre del archivo
        proyecto_nombre = iniciativa.get('nombre_iniciativa', iniciativa.get('nombre', 'proyecto'))
        safe_name = "".join([c for c in proyecto_nombre if c.isalpha() or c.isdigit() or c == ' ']).rstrip()
        filename = f"MINUTA_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"

        # Crear respuesta con el PDF
        response = current_app.response_class(
            pdf_data,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment;filename={filename}'}
        )

        return response
    except Exception as e:
        flash(f'Error al descargar minuta: {str(e)}', 'danger')
        return redirect(url_for('colaborador.generate_minuta', iniciativa_id=iniciativa_id))