#app/director/routes.py
from flask import (
    render_template, redirect, url_for,
    flash, request, current_app
)
from flask_login import login_required, current_user
from bson.objectid import ObjectId
import bcrypt
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer, ListFlowable, ListItem
from reportlab.lib.units import inch
import base64
import os
from . import director_bp
from ..auth.utils import director_required
from .. import mongo, csrf
from ..models.user import User
from app.utils.timezone_utils import now_chile, format_chile_datetime, chile_to_utc
from flask import jsonify
from ..models.task import Task
from unidecode import unidecode  # Asegúrate de tener `unidecode` instalado

# Agregado al inicio de la función view_stats()
from collections import defaultdict

@director_bp.route('/dashboard')
@login_required
@director_required
def dashboard():
    """Dashboard para el rol de director."""
    try:
        # Obtener estadísticas de colaboradores
        colaboradores = mongo.db.users.count_documents({"role": "colaborador"})

        # Obtener iniciativas en progreso (estado distinto a "No Iniciado")
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            coll = mongo.db[parts[0]][parts[1]]
        else:
            coll = mongo.db[collection_name]

        iniciativas_activas = list(coll.find({
            "estado": {"$ne": "No Iniciado"}
        }).sort("ultimo_cambio_estado", -1).limit(5))

        # Contar total de iniciativas por estado
        pipeline = [
            {"$match": {"estado": {"$exists": True}}},
            {"$group": {"_id": "$estado", "count": {"$sum": 1}}}
        ]
        estados_count = list(coll.aggregate(pipeline))

        # Crear diccionario de conteo por estado
        conteo_estados = {}
        for estado in estados_count:
            conteo_estados[estado["_id"]] = estado["count"]

        stats = {
            'colaboradores': colaboradores,
            'total_iniciativas': coll.count_documents({}),
            'iniciativas_activas': len(iniciativas_activas),
            'conteo_estados': conteo_estados
        }
        now = now_chile()

        return render_template(
            'director/dashboard.html',
            stats=stats,
            iniciativas_activas=iniciativas_activas
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error en dashboard: {error_details}")
        flash(f'Error al cargar el dashboard: {e}', 'danger')
        return render_template('director/dashboard.html', stats={})


@director_bp.route('/profile')
@login_required
@director_required
def profile():
    """Perfil del director."""
    return render_template('director/profile.html')


@director_bp.route('/colaboradores')
@login_required
@director_required
def colaborador_list():
    colaboradores = list(mongo.db.users.find({"role": "colaborador"}))
    return render_template('director/colaboradores.html', colaboradores=colaboradores)


@director_bp.route('/colaboradores/<colaborador_id>')
@login_required
@director_required
def colaborador_detail(colaborador_id):
    colaborador_data = mongo.db.users.find_one({
        "_id": ObjectId(colaborador_id),
        "role": "colaborador"
    })
    if not colaborador_data:
        flash('Colaborador no encontrado', 'danger')
        return redirect(url_for('director.colaborador_list'))

    colaborador = User(**colaborador_data)
    return render_template('director/colaborador_detail.html', colaborador=colaborador)


@director_bp.route('/colaboradores/nuevo', methods=['GET', 'POST'])
@login_required
@director_required
def crear_colaborador():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        nombre = request.form.get('nombre')
        rut = request.form.get('rut')
        direccion = request.form.get('direccion')
        telefono = request.form.get('telefono')
        titulos_raw = request.form.get('titulos')

        # Validación
        if not all([email, password, confirm, nombre, rut]):
            flash('Complete todos los campos obligatorios', 'danger')
            return render_template('director/crear_colaborador.html')
        if mongo.db.users.find_one({"email": email}):
            flash('Correo ya registrado', 'danger')
            return render_template('director/crear_colaborador.html')
        if password != confirm:
            flash('Las contraseñas no coinciden', 'danger')
            return render_template('director/crear_colaborador.html')

        # Validar fuerza de contraseña
        from ..auth.utils import validate_password_strength
        valid, errors = validate_password_strength(password)
        if not valid:
            for err in errors:
                flash(err, 'danger')
            return render_template('director/crear_colaborador.html')

        titulos = [
            t.strip() for t in titulos_raw.split(',')
            if t.strip()
        ] if titulos_raw else []

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        new_user = {
            "email": email,
            "password": hashed,
            "role": "colaborador",
            "active": True,
            "created_at": chile_to_utc(now_chile()),
            "last_login": None,
            "nombre": nombre,
            "rut": rut,
            "direccion": direccion,
            "telefono": telefono,
            "titulos": titulos,
            "iniciativas": []
        }

        mongo.db.users.insert_one(new_user)
        flash(f'Colaborador {nombre} creado', 'success')
        return redirect(url_for('director.colaborador_list'))

    return render_template('director/crear_colaborador.html')


@director_bp.route('/colaboradores/<colaborador_id>/toggle_active', methods=['POST'])
@login_required
@director_required
def toggle_colaborador_active(colaborador_id):
    colabor = mongo.db.users.find_one({
        "_id": ObjectId(colaborador_id),
        "role": "colaborador"
    })
    if not colabor:
        flash('No encontrado', 'danger')
        return redirect(url_for('director.colaborador_list'))

    nuevo = not colabor.get('active', True)
    mongo.db.users.update_one(
        {"_id": ObjectId(colaborador_id)},
        {"$set": {"active": nuevo}}
    )
    estado = 'activado' if nuevo else 'desactivado'
    flash(f'Colaborador {colabor["email"]} {estado}', 'success')
    return redirect(url_for('director.colaborador_detail', colaborador_id=colaborador_id))


@director_bp.route('/colaboradores/<colaborador_id>/reset_password', methods=['POST'])
@login_required
@director_required
def reset_colaborador_password(colaborador_id):
    colabor = mongo.db.users.find_one({
        "_id": ObjectId(colaborador_id),
        "role": "colaborador"
    })
    if not colabor:
        flash('No encontrado', 'danger')
        return redirect(url_for('director.colaborador_list'))

    temp = "Temporal123!"
    hashed = bcrypt.hashpw(temp.encode(), bcrypt.gensalt())
    mongo.db.users.update_one(
        {"_id": ObjectId(colaborador_id)},
        {"$set": {"password": hashed}}
    )
    flash(f'Nueva contraseña para {colabor.get("nombre") or colabor["email"]}: {temp}', 'success')
    return redirect(url_for('director.colaborador_detail', colaborador_id=colaborador_id))


@director_bp.route('/colaboradores/<colaborador_id>/edit', methods=['GET', 'POST'])
@login_required
@director_required
def edit_colaborador(colaborador_id):
    try:
        colabor = mongo.db.users.find_one({"_id": ObjectId(colaborador_id)})
        if not colabor or colabor.get('role') != 'colaborador':
            flash('Solo colaboradores', 'danger')
            return redirect(url_for('director.colaborador_list'))

        # Formulario inline
        from flask_wtf import FlaskForm
        from wtforms import StringField, SubmitField
        from wtforms.validators import DataRequired, Email, Optional

        class EditForm(FlaskForm):
            email = StringField('Correo', validators=[DataRequired(), Email()])
            nombre = StringField('Nombre', validators=[DataRequired()])
            rut = StringField('RUT', validators=[DataRequired()])
            telefono = StringField('Teléfono', validators=[Optional()])
            direccion = StringField('Dirección', validators=[Optional()])
            titulos = StringField('Títulos', validators=[Optional()])
            submit = SubmitField('Guardar')

        form = EditForm()

        # Para el método GET, prellenar el formulario
        if request.method == 'GET':
            form.email.data = colabor.get('email', '')
            form.nombre.data = colabor.get('nombre', '')
            form.rut.data = colabor.get('rut', '')
            form.telefono.data = colabor.get('telefono', '')
            form.direccion.data = colabor.get('direccion', '')

            # Convertir lista a string para el formulario
            if isinstance(colabor.get('titulos', []), list):
                form.titulos.data = ', '.join(colabor.get('titulos', []))
            else:
                form.titulos.data = colabor.get('titulos', '')

        if form.validate_on_submit():
            titulos = [t.strip() for t in form.titulos.data.split(',') if t.strip()]
            update_data = {
                'email': form.email.data,
                'nombre': form.nombre.data,
                'rut': form.rut.data,
                'telefono': form.telefono.data,
                'direccion': form.direccion.data,
                'titulos': titulos
            }
            res = mongo.db.users.update_one(
                {"_id": ObjectId(colaborador_id)},
                {"$set": update_data}
            )
            msg = 'Colaborador actualizado' if res.modified_count else 'Sin cambios'
            flash(msg, 'success' if res.modified_count else 'info')
            return redirect(url_for('director.colaborador_detail', colaborador_id=colaborador_id))

        return render_template('director/edit_colaborador.html', form=form, colaborador=colabor)

    except Exception as e:
        flash(f'Error: {e}', 'danger')
        return redirect(url_for('director.colaborador_list'))



@director_bp.route('/iniciativas')
@login_required
@director_required
def list_initiatives():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        skip = (page - 1) * per_page

        search = request.args.get('search', '')
        status = request.args.get('status', '')

        # Inicio de depuración
        print(f"DEBUG - Búsqueda: '{search}', Estado: '{status}'")

        filt = {}
        if search:
            filt['$or'] = [
                {'nombre_iniciativa': {'$regex': search, '$options': 'i'}},
                {'nombre': {'$regex': search, '$options': 'i'}},
                {'cod': {'$regex': search, '$options': 'i'}},
                {'codigo': {'$regex': search, '$options': 'i'}}
            ]
        if status:
            filt['estado'] = status
        elif status == 'active':
            filt['estado'] = 'activo'
        elif status == 'inactive':
            filt['estado'] = 'inactivo'

        print(f"DEBUG - Filtro de búsqueda: {filt}")

        # Obtener el nombre de la colección donde están las iniciativas
        collection_name = current_app.config['INITIATIVES_COLLECTION']


        # Verificar si collection_name contiene un punto (subcollection)
        if '.' in collection_name:
            parts = collection_name.split('.')
            if len(parts) > 1:
                coll = mongo.db[parts[0]][parts[1]]
            else:
                coll = mongo.db[collection_name]
        else:
            coll = mongo.db[collection_name]

        # Ejecutar la consulta con el filtro
        total = coll.count_documents(filt)
        #iniciativas = list(coll.find(filt).skip(skip).limit(per_page))
        iniciativas = list(coll.find(filt).sort("fecha_creacion", -1).skip(skip).limit(per_page))

        colaboradores = list(mongo.db.users.find({
            "role": {"$in": ["colaborador", "director"]}
        }))

        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page
        }


        return render_template(
            'director/iniciativas.html',
            iniciativas=iniciativas,
            colaboradores=colaboradores,
            pagination=pagination,
            collection_name=collection_name,
            search=search,
            status=status
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"DEBUG - Error: {error_details}")
        flash(f'Error al cargar iniciativas: {e}', 'danger')
        return redirect(url_for('director.dashboard'))

@director_bp.route('/iniciativas/<iniciativa_id>')
@login_required
@director_required
def view_initiative(iniciativa_id):
    try:
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            coll = mongo.db[parts[0]][parts[1]]
        else:
            coll = mongo.db[collection_name]

        iniciativa = coll.find_one({"_id": ObjectId(iniciativa_id)})
        if not iniciativa:
            flash('No encontrada', 'danger')
            return redirect(url_for('director.list_initiatives'))

        colaboradores = list(mongo.db.users.find({
            "role": {"$in": ["colaborador", "director"]},
            "active": True,
            "_id": {"$ne": ObjectId(current_user.get_id())}  # Excluir usuario actual si es necesario
        }))
        # Al obtener usuarios asignados, también obtener información de roles
        assigned = iniciativa.get('assigned_users') or []

        # Obtener información completa de los usuarios asignados
        assigned_users = []
        if assigned:
            for u in mongo.db.users.find({"_id": {"$in": [ObjectId(u) for u in assigned if u]}}):
                # Buscar el rol del usuario en esta iniciativa
                role = 'collaborator'  # Valor predeterminado
                for asig in mongo.db.assignment_history.find({
                    "initiative_id": iniciativa_id,
                    "user_id": str(u["_id"])
                }).sort("timestamp", -1).limit(1):
                    if "role" in asig:
                        role = asig["role"]
                        break

                # Añadir el rol al objeto usuario
                u["role"] = role
                assigned_users.append(u)

        history = list(mongo.db.assignment_history.find(
            {"initiative_id": iniciativa_id}
        ).sort("timestamp", -1))

        # Obtener historial de estados
        try:
            estados_historial = list(mongo.db.estado_iniciativa_historial.find(
                {"initiative_id": str(iniciativa_id)}
            ).sort("timestamp", -1))
        except Exception as e:
            print(f"Error al obtener historial de estados: {e}")
            estados_historial = []

        # Obtener tareas de la iniciativa
        tasks = list(mongo.db.tasks.find(
            {"initiative_id": iniciativa_id}
        ).sort("created_at", -1))

        # Obtener información de usuarios para las tareas
        user_ids = set()
        for task in tasks:
            if task.get('created_by'):
                user_ids.add(task.get('created_by'))
            if task.get('completed_by'):
                user_ids.add(task.get('completed_by'))
            if task.get('assigned_to'):
                user_ids.update(task.get('assigned_to'))

        users = {str(u['_id']): u for u in
                mongo.db.users.find({
                    "_id": {"$in": [ObjectId(uid) for uid in user_ids if uid]},
                    "role": {"$ne": "admin"}  # Excluir administradores
                })}

        # Lista de estados válidos para el selector
        estados_validos = [
            'No Iniciado', 'Formulación', 'Revisión', 'Corrección',
            'Elegible', 'Financiado', 'Firma Convenio', 'Preparación Bases',
            'Licitación', 'Adjudicación', 'Firma Contrato', 'Entregado',
            'En Ejecución', 'Finalizado'
        ]

        return render_template(
            'director/view_initiative.html',
            iniciativa=iniciativa,
            colaboradores=colaboradores,
            assigned_users=assigned_users,
            assignments_history=history,
            collection_name=collection_name,
            iniciativa_id=str(iniciativa_id),
            estados_historial=estados_historial,
            estados_validos=estados_validos,
            tasks=tasks,  # Añadimos las tareas
            users=users    # Añadimos la información de usuarios
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error detallado: {error_details}")
        flash(f'Error al ver iniciativa: {e}', 'danger')
        return redirect(url_for('director.list_initiatives'))

@director_bp.route('/iniciativas/<iniciativa_id>/edit', methods=['GET', 'POST'])
@login_required
@director_required
def edit_initiative(iniciativa_id):
    """Editar una iniciativa."""
    try:
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        coll = mongo.db[collection_name]

        iniciativa = coll.find_one({"_id": ObjectId(iniciativa_id)})
        if not iniciativa:
            flash('Iniciativa no encontrada', 'danger')
            return redirect(url_for('director.list_initiatives'))

        if request.method == 'POST':
            # Obtener todos los campos del formulario
            update_data = {}
            for key in request.form:
                if key != 'csrf_token' and key != 'submit':
                    update_data[key] = request.form[key]

            # Registrar la modificación
            history_entry = {
                "initiative_id": iniciativa_id,
                "type": "update",
                "user_id": current_user.get_id(),
                "user_email": current_user.email,
                "timestamp": chile_to_utc(now_chile()),
                "fields_modified": list(update_data.keys())
            }
            mongo.db.modification_history.insert_one(history_entry)

            # Actualizar la iniciativa
            result = coll.update_one(
                {"_id": ObjectId(iniciativa_id)},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                flash('Iniciativa actualizada correctamente', 'success')
            else:
                flash('No se realizaron cambios', 'info')

            return redirect(url_for('director.view_initiative', iniciativa_id=iniciativa_id))

        # Obtener todos los campos de la iniciativa para el formulario dinámico
        fields = []
        for key, value in iniciativa.items():
            if key != '_id' and key != 'assigned_users':
                fields.append({
                    'name': key,
                    'value': value,
                    'type': 'text'
                })

        return render_template(
            'director/edit_initiative.html',
            iniciativa=iniciativa,
            fields=fields,
            iniciativa_id=iniciativa_id
        )
    except Exception as e:
        flash(f'Error al editar la iniciativa: {str(e)}', 'danger')
        return redirect(url_for('director.view_initiative', iniciativa_id=iniciativa_id))


@director_bp.route('/iniciativas/<iniciativa_id>/assign', methods=['POST'])
@login_required
@director_required
def assign_users(iniciativa_id):
    """Asignar usuarios a una iniciativa."""
    try:
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        coll = mongo.db[collection_name]

        # Obtener IDs de usuarios seleccionados
        selected_users = request.form.getlist('user_ids')
        # Obtener IDs de coordinadores seleccionados (nuevo)
        coordinator_ids = request.form.getlist('coordinator_ids')

        if not selected_users:
            flash('No se seleccionó ningún usuario para asignar', 'warning')
            return redirect(url_for('director.view_initiative', iniciativa_id=iniciativa_id))

        # Convertir el ID a ObjectId
        iniciativa = coll.find_one({"_id": ObjectId(iniciativa_id)})

        if not iniciativa:
            flash('Iniciativa no encontrada', 'danger')
            return redirect(url_for('director.list_initiatives'))

        # Actualizar la iniciativa con los usuarios asignados
        result = coll.update_one(
            {"_id": ObjectId(iniciativa_id)},
            {"$set": {"assigned_users": selected_users}}
        )

        # Registrar la asignación en el historial
        for user_id in selected_users:
            user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
            if user:
                # Determinar si el usuario es coordinador o colaborador regular
                role = "coordinator" if user_id in coordinator_ids else "collaborator"

                history_entry = {
                    "initiative_id": iniciativa_id,
                    "initiative_name": iniciativa.get('nombre', 'Sin nombre'),
                    "type": "assignment",
                    "user_id": user_id,
                    "user_email": user.get('email', 'Desconocido'),
                    "assigned_by": current_user.get_id(),
                    "assigned_by_email": current_user.email,
                    "timestamp": chile_to_utc(now_chile()),
                    "role": role  # Añadir el rol de asignación
                }
                mongo.db.assignment_history.insert_one(history_entry)

                # Actualizar también el registro del usuario
                mongo.db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$push": {
                        "iniciativas": {
                            "initiative_id": iniciativa_id,
                            "nombre": iniciativa.get('nombre', 'Sin nombre'),
                            "assigned_by": current_user.get_id(),
                            "assigned_at": chile_to_utc(now_chile()),
                            "active": True,
                            "role": role  # Añadir el rol de asignación
                        }
                    }}
                )

        if result.modified_count > 0:
            flash('Usuarios asignados correctamente a la iniciativa', 'success')
        else:
            flash('No se realizaron cambios en las asignaciones', 'info')

        return redirect(url_for('director.view_initiative', iniciativa_id=iniciativa_id))
    except Exception as e:
        flash(f'Error al asignar usuarios: {str(e)}', 'danger')
        return redirect(url_for('director.view_initiative', iniciativa_id=iniciativa_id))

@director_bp.route('/iniciativas/<iniciativa_id>/unassign/<user_id>', methods=['POST'])
@login_required
@director_required
def unassign_user(iniciativa_id, user_id):
    """Desasignar un usuario de una iniciativa."""
    try:
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        coll = mongo.db[collection_name]

        # Convertir el ID a ObjectId
        iniciativa = coll.find_one({"_id": ObjectId(iniciativa_id)})

        if not iniciativa or 'assigned_users' not in iniciativa:
            flash('Iniciativa no encontrada o no tiene usuarios asignados', 'danger')
            return redirect(url_for('director.list_initiatives'))

        # Eliminar el usuario de la lista de asignados
        assigned_users = iniciativa.get('assigned_users', [])
        if user_id in assigned_users:
            assigned_users.remove(user_id)

            # Actualizar la iniciativa
            result = coll.update_one(
                {"_id": ObjectId(iniciativa_id)},
                {"$set": {"assigned_users": assigned_users}}
            )

            # Registrar la desasignación en el historial
            user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
            if user:
                history_entry = {
                    "initiative_id": iniciativa_id,
                    "initiative_name": iniciativa.get('nombre', 'Sin nombre'),
                    "type": "unassignment",
                    "user_id": user_id,
                    "user_email": user.get('email', 'Desconocido'),
                    "removed_by": current_user.get_id(),
                    "removed_by_email": current_user.email,
                    "timestamp": chile_to_utc(now_chile())
                }
                mongo.db.assignment_history.insert_one(history_entry)

                # Actualizar el registro del usuario
                mongo.db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {
                        "iniciativas.$[elem].active": False,
                        "iniciativas.$[elem].removed_by": current_user.get_id(),
                        "iniciativas.$[elem].removed_at": chile_to_utc(now_chile())
                    }},
                    array_filters=[{"elem.initiative_id": iniciativa_id}]
                )

            flash('Usuario desasignado correctamente de la iniciativa', 'success')
        else:
            flash('El usuario no estaba asignado a esta iniciativa', 'warning')

        return redirect(url_for('director.view_initiative', iniciativa_id=iniciativa_id))
    except Exception as e:
        flash(f'Error al desasignar usuario: {str(e)}', 'danger')
        return redirect(url_for('director.view_initiative', iniciativa_id=iniciativa_id))


# Agregar estas rutas al archivo app/director/routes.py

@director_bp.route('/iniciativas/nueva', methods=['GET', 'POST'])
@login_required
@director_required
def crear_iniciativa():
    """Crear una nueva iniciativa."""
    print("DEBUG: Iniciando función crear_iniciativa")
    try:
        print("DEBUG: Obteniendo collection_name")
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        print(f"DEBUG: collection_name = {collection_name}")

        print("DEBUG: Accediendo a la colección")
        coll = mongo.db[collection_name]

        print("DEBUG: Buscando documentos de muestra")
        # Obtener muestra de documentos para detectar estructura
        sample_docs = list(coll.find().limit(1))
        print(f"DEBUG: Encontrados {len(sample_docs)} documentos de muestra")

        # Si hay iniciativas existentes, usamos sus campos como plantilla
        fields = []
        if sample_docs:
            print("DEBUG: Usando estructura de documentos existentes")
            # Excluimos campos internos y técnicos
            excluded_fields = ['_id', 'estado', 'assigned_users', 'descripcion']

            # Recorrer los campos del primer documento
            for key in sample_docs[0].keys():
                print(f"DEBUG: Procesando campo {key}")
                if key not in excluded_fields:
                    fields.append({
                        'name': key,
                        'label': key.replace('_', ' ').capitalize(),
                        'type': 'text',
                        'required': True
                    })
        else:
            print("DEBUG: Usando estructura predeterminada")
            # Si no hay iniciativas, definimos campos mínimos predeterminados
            fields = [
                {'name': 'nombre', 'label': 'Nombre de la iniciativa', 'type': 'text', 'required': True},
                {'name': 'codigo', 'label': 'Código', 'type': 'text', 'required': True},
                {'name': 'monto', 'label': 'Monto (CLP)', 'type': 'number', 'required': True},
                {'name': 'fecha_inicio', 'label': 'Fecha de inicio', 'type': 'date', 'required': False}
            ]

        print(f"DEBUG: Campos definidos: {fields}")

        if request.method == 'POST':
            print("DEBUG: Procesando solicitud POST")
            # Recopilar todos los campos del formulario
            iniciativa_data = {}

            print("DEBUG: Recorriendo campos del formulario")
            for key in request.form:
                print(f"DEBUG: Campo del formulario: {key}")
                if key != 'csrf_token' and key != 'submit' and key != 'descripcion':
                    value = request.form.get(key)
                    print(f"DEBUG: Asignando {key} = {value}")
                    iniciativa_data[key] = value

            print("DEBUG: Procesando campo de descripción")
            # Agregar descripción (tratada por separado para limitar palabras)
            descripcion = request.form.get('descripcion', '')
            palabras = descripcion.split()
            if len(palabras) > 200:
                descripcion = ' '.join(palabras[:200])
                flash('La descripción se ha limitado a 200 palabras', 'warning')

            iniciativa_data['descripcion'] = descripcion

            print("DEBUG: Estableciendo campos adicionales")
            # Establecer estado inicial
            iniciativa_data['estado'] = 'No Iniciado'
            iniciativa_data['fecha_creacion'] = chile_to_utc(now_chile())
            iniciativa_data['creado_por'] = current_user.get_id()
            iniciativa_data['creado_por_email'] = current_user.email

            print("DEBUG: Insertando en la base de datos")
            # Insertar la iniciativa en la base de datos
            result = coll.insert_one(iniciativa_data)

            if result.inserted_id:
                print(f"DEBUG: Iniciativa creada con ID: {result.inserted_id}")
                # Registrar en el historial de estados
                history_entry = {
                    "initiative_id": f"{result.inserted_id}",  # Convertir explícitamente a string
                    "estado_anterior": None,
                    "estado_nuevo": "No Iniciado",
                    "cambiado_por": current_user.get_id(),
                    "cambiado_por_email": current_user.email,
                    "timestamp": chile_to_utc(now_chile()),
                    "comentario": "Iniciativa creada"
                }

                print("DEBUG: Registrando en historial de estados")
                mongo.db.estado_iniciativa_historial.insert_one(history_entry)

                print("DEBUG: Redirección a view_initiative")
                flash('Iniciativa creada exitosamente', 'success')
                return redirect(url_for('director.view_initiative', iniciativa_id=f"{result.inserted_id}"))
            else:
                print("DEBUG: Error al insertar en la base de datos")
                flash('Error al crear la iniciativa', 'danger')
        else:
            print("DEBUG: Método GET, mostrando formulario")

        print("DEBUG: Renderizando plantilla crear_iniciativa.html")
        return render_template(
            'director/crear_iniciativa.html',
            fields=fields
        )

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"DEBUG: Error detallado: {error_details}")
        flash(f'Error al crear iniciativa: {str(e)}', 'danger')
        return redirect(url_for('director.list_initiatives'))


@director_bp.route('/iniciativas/<iniciativa_id>/cambiar-estado', methods=['POST'])
@login_required
@director_required
def cambiar_estado_iniciativa(iniciativa_id):
    """Cambiar el estado de una iniciativa."""
    try:
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        coll = mongo.db[collection_name]

        iniciativa = coll.find_one({"_id": ObjectId(iniciativa_id)})
        if not iniciativa:
            flash('Iniciativa no encontrada', 'danger')
            return redirect(url_for('director.list_initiatives'))

        nuevo_estado = request.form.get('nuevo_estado')
        comentario = request.form.get('comentario', '')

        # Lista de estados válidos
        estados_validos = [
            'No Iniciado', 'Formulación', 'Revisión', 'Corrección',
            'Elegible', 'Financiado', 'Firma Convenio', 'Preparación Bases',
            'Licitación', 'Adjudicación', 'Firma Contrato', 'Entregado',
            'En Ejecución', 'Finalizado'
        ]

        # Validar que el estado sea válido
        if nuevo_estado not in estados_validos:
            flash('Estado no válido', 'danger')
            return redirect(url_for('director.view_initiative', iniciativa_id=iniciativa_id))

        estado_anterior = iniciativa.get('estado', 'No Iniciado')

        # Verificar si el estado realmente cambió
        if estado_anterior == nuevo_estado:
            flash('El estado no ha cambiado', 'info')
            return redirect(url_for('director.view_initiative', iniciativa_id=iniciativa_id))

        # Actualizar el estado de la iniciativa
        result = coll.update_one(
            {"_id": ObjectId(iniciativa_id)},
            {"$set": {
                "estado": nuevo_estado,
                "ultimo_cambio_estado": chile_to_utc(now_chile()),
                "estado_cambiado_por": current_user.get_id()
            }}
        )

        # Registrar en el historial de estados
        history_entry = {
            "initiative_id": iniciativa_id,
            "estado_anterior": estado_anterior,
            "estado_nuevo": nuevo_estado,
            "cambiado_por": current_user.get_id(),
            "cambiado_por_email": current_user.email,
            "timestamp": chile_to_utc(now_chile()),
            "comentario": comentario
        }

        mongo.db.estado_iniciativa_historial.insert_one(history_entry)

        if result.modified_count > 0:
            flash(f'Estado cambiado de "{estado_anterior}" a "{nuevo_estado}"', 'success')
        else:
            flash('No se pudo actualizar el estado', 'warning')

        return redirect(url_for('director.view_initiative', iniciativa_id=iniciativa_id))

    except Exception as e:
        flash(f'Error al cambiar estado: {str(e)}', 'danger')
        return redirect(url_for('director.view_initiative', iniciativa_id=iniciativa_id))


@director_bp.route('/iniciativas/actualizar-masivo', methods=['POST'])
@login_required
@director_required
def actualizar_iniciativas_masivo():
    """Actualizar masivamente el estado de las iniciativas."""
    try:
        nuevo_estado = request.form.get('nuevo_estado')
        filtro = request.form.get('filtro', '{}')  # JSON con filtros

        # Validar estado
        estados_validos = [
            'No Iniciado', 'Formulación', 'Revisión', 'Corrección',
            'Elegible', 'Financiado', 'Firma Convenio', 'Preparación Bases',
            'Licitación', 'Adjudicación', 'Firma Contrato', 'Entregado',
            'En Ejecución', 'Finalizado'
        ]

        if nuevo_estado not in estados_validos:
            flash('Estado no válido', 'danger')
            return redirect(url_for('director.list_initiatives'))

        # Convertir filtro de JSON
        import json
        try:
            filtro_dict = json.loads(filtro)
        except:
            filtro_dict = {}  # Filtro vacío = todas las iniciativas

        # Obtener colección
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        if '.' in collection_name:
            parts = collection_name.split('.')
            if len(parts) > 1:
                coll = mongo.db[parts[0]][parts[1]]
            else:
                coll = mongo.db[collection_name]
        else:
            coll = mongo.db[collection_name]

        # Obtener IDs de iniciativas a actualizar para historial
        iniciativas = list(coll.find(filtro_dict, {"_id": 1, "estado": 1}))

        # Actualizar todas las iniciativas que cumplan el filtro
        resultado = coll.update_many(
            filtro_dict,
            {
                "$set": {
                    "estado": nuevo_estado,
                    "ultimo_cambio_estado": chile_to_utc(now_chile()),
                    "estado_cambiado_por": current_user.get_id()
                }
            }
        )

        # Registrar en historial de cambios
        for iniciativa in iniciativas:
            iniciativa_id = str(iniciativa["_id"])
            estado_anterior = iniciativa.get("estado", "No Iniciado")

            if estado_anterior != nuevo_estado:
                historial = {
                    "initiative_id": iniciativa_id,
                    "estado_anterior": estado_anterior,
                    "estado_nuevo": nuevo_estado,
                    "cambiado_por": current_user.get_id(),
                    "cambiado_por_email": current_user.email,
                    "timestamp": chile_to_utc(now_chile()),
                    "comentario": "Actualización masiva de estado"
                }
                mongo.db.estado_iniciativa_historial.insert_one(historial)

        flash(f'Se actualizaron {resultado.modified_count} iniciativas al estado "{nuevo_estado}"', 'success')
        return redirect(url_for('director.list_initiatives'))

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error en actualización masiva: {error_details}")
        flash(f'Error al actualizar iniciativas: {e}', 'danger')
        return redirect(url_for('director.list_initiatives'))


# Ruta para ver todas las tareas de una iniciativa
@director_bp.route('/iniciativas/<iniciativa_id>/tareas')
@login_required
@director_required
def view_initiative_tasks(iniciativa_id):
    """Ver las tareas de una iniciativa específica."""
    try:
        # Verificar que la iniciativa existe
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            initiatives_coll = mongo.db[parts[0]][parts[1]]
        else:
            initiatives_coll = mongo.db[collection_name]

        iniciativa = initiatives_coll.find_one({"_id": ObjectId(iniciativa_id)})

        if not iniciativa:
            flash('Iniciativa no encontrada', 'danger')
            return redirect(url_for('director.list_initiatives'))

        # Obtener todas las tareas relacionadas con esta iniciativa
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
                 mongo.db.users.find({
                     "_id": {"$in": [ObjectId(uid) for uid in user_ids if uid]},
                     "role": {"$ne": "admin"}  # Excluir a los administradores
                 })}

        return render_template(
            'director/initiative_tasks.html',
            iniciativa=iniciativa,
            tasks=tasks,
            users=users,
            iniciativa_id=iniciativa_id
        )
    except Exception as e:
        import traceback
        print(f"Error al ver tareas: {traceback.format_exc()}")
        flash(f'Error al cargar las tareas: {str(e)}', 'danger')
        return redirect(url_for('director.view_initiative', iniciativa_id=iniciativa_id))


# Ruta para añadir una nueva tarea
@director_bp.route('/iniciativas/<iniciativa_id>/tareas/crear', methods=['POST'])
@login_required
@director_required
def create_task(iniciativa_id):
    """Crear una nueva tarea para una iniciativa."""
    try:
        # Obtener datos del formulario
        content = request.form.get('content', '').strip()
        assigned_users = request.form.getlist('assigned_users')

        # Verificar que los usuarios asignados no sean administradores
        if assigned_users:
            valid_users = []
            for user_id in assigned_users:
                user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
                if user and user.get('role') != 'admin':
                    valid_users.append(user_id)
            assigned_users = valid_users

        # Validar contenido
        if not content:
            flash('El contenido de la tarea es obligatorio', 'danger')
            return redirect(url_for('director.view_initiative_tasks', iniciativa_id=iniciativa_id))

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
        return redirect(url_for('director.view_initiative_tasks', iniciativa_id=iniciativa_id))
    except Exception as e:
        flash(f'Error al crear la tarea: {str(e)}', 'danger')
        return redirect(url_for('director.view_initiative_tasks', iniciativa_id=iniciativa_id))


# Ruta para marcar una tarea como completada
@director_bp.route('/tareas/<task_id>/completar', methods=['POST'])
@login_required
@director_required
def complete_task(task_id):
    """Marcar una tarea como completada."""
    try:
        # Buscar la tarea
        task_data = mongo.db.tasks.find_one({"_id": ObjectId(task_id)})

        if not task_data:
            flash('Tarea no encontrada', 'danger')
            return redirect(request.referrer or url_for('director.all_collaborator_tasks'))

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

        flash('Tarea completada correctamente', 'success')

        # Redireccionar a la página anterior o a la lista de tareas
        return redirect(request.referrer or url_for('director.all_collaborator_tasks'))
    except Exception as e:
        flash(f'Error al completar la tarea: {str(e)}', 'danger')
        return redirect(request.referrer or url_for('director.all_collaborator_tasks'))


@director_bp.route('/tareas/<task_id>/reabrir', methods=['POST'])
@login_required
@director_required
def reopen_task(task_id):
    """Reabrir una tarea que estaba completada."""
    try:
        # Buscar la tarea
        task_data = mongo.db.tasks.find_one({"_id": ObjectId(task_id)})

        if not task_data:
            flash('Tarea no encontrada', 'danger')
            return redirect(request.referrer or url_for('director.all_collaborator_tasks'))

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

        flash('Tarea reabierta correctamente', 'success')
        return redirect(request.referrer or url_for('director.all_collaborator_tasks'))
    except Exception as e:
        flash(f'Error al reabrir la tarea: {str(e)}', 'danger')
        return redirect(request.referrer or url_for('director.all_collaborator_tasks'))


@director_bp.route('/tareas/<task_id>/eliminar', methods=['POST'])
@login_required
@director_required
def delete_task(task_id):
    """Eliminar una tarea."""
    try:
        # Buscar la tarea
        task_data = mongo.db.tasks.find_one({"_id": ObjectId(task_id)})

        if not task_data:
            flash('Tarea no encontrada', 'danger')
            return redirect(request.referrer or url_for('director.all_collaborator_tasks'))

        # Eliminar la tarea
        mongo.db.tasks.delete_one({"_id": ObjectId(task_id)})

        flash('Tarea eliminada correctamente', 'success')
        return redirect(request.referrer or url_for('director.all_collaborator_tasks'))
    except Exception as e:
        flash(f'Error al eliminar la tarea: {str(e)}', 'danger')
        return redirect(request.referrer or url_for('director.all_collaborator_tasks'))

@director_bp.route('/all-tasks')
@login_required
@director_required
def all_collaborator_tasks():
    """Ver todas las tareas de los colaboradores."""
    try:
        # Obtener todas las tareas
        tasks = list(mongo.db.tasks.find().sort("created_at", -1))

        # Obtener las iniciativas relacionadas con las tareas
        initiative_ids = set(task.get('initiative_id') for task in tasks if task.get('initiative_id'))

        # Obtener información de las iniciativas
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

        # Obtener información de los usuarios
        user_ids = set()
        for task in tasks:
            if task.get('created_by'):
                user_ids.add(task.get('created_by'))
            if task.get('completed_by'):
                user_ids.add(task.get('completed_by'))
            if task.get('assigned_to'):
                user_ids.update(task.get('assigned_to'))

        users = {
            str(u['_id']): u for u in mongo.db.users.find({
                "_id": {"$in": [ObjectId(uid) for uid in user_ids if uid]},
                "role": {"$ne": "admin"}  # Excluir a los administradores
            })
        }

        # Agrupar tareas por iniciativa
        tasks_by_initiative = {}
        for task in tasks:
            initiative_id = task.get('initiative_id')
            if initiative_id not in tasks_by_initiative:
                tasks_by_initiative[initiative_id] = []
            tasks_by_initiative[initiative_id].append(task)

        # Calcular estadísticas
        total_tasks = len(tasks)
        completed_tasks = sum(1 for task in tasks if task.get('is_completed'))
        pending_tasks = total_tasks - completed_tasks

        stats = {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'pending_tasks': pending_tasks,
            'completion_rate': round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
        }

        return render_template(
            'director/all_tasks.html',
            tasks=tasks,
            tasks_by_initiative=tasks_by_initiative,
            initiatives=initiatives,
            users=users,
            stats=stats
        )
    except Exception as e:
        import traceback
        print(f"Error al cargar todas las tareas: {traceback.format_exc()}")
        flash(f'Error al cargar las tareas: {str(e)}', 'danger')
        return redirect(url_for('director.dashboard'))


@director_bp.route('/stats')
@login_required
@director_required
def view_stats():
    """Mostrar estadísticas sobre las iniciativas."""
    try:

        collection_name = current_app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        coll = mongo.db[parts[0]][parts[1]] if len(parts) > 1 else mongo.db[collection_name]

        total_iniciativas = coll.count_documents({})

        pipeline_estado = [
            {"$group": {"_id": "$estado", "count": {"$sum": 1}}}
        ]
        estados_count = list(coll.aggregate(pipeline_estado))
        estados_data = {estado["_id"] or "No definido": estado["count"] for estado in estados_count}


        with_collaborators = coll.count_documents({"assigned_users": {"$exists": True, "$not": {"$size": 0}}})
        collaborators_percent = round((with_collaborators / total_iniciativas * 100) if total_iniciativas else 0)

        # Corregido: uso del campo "Participación" (con tilde y mayúscula)
        # Obtener y procesar valores únicos del campo "Participación"
        participacion_contador = defaultdict(int)

        for doc in coll.find({}, {"participación": 1}):
            valor = doc.get("participación", "no especificado")

            # Normalizar texto: quitar tildes, pasar a minúsculas, eliminar espacios extra
            if isinstance(valor, str):
                normalizado = unidecode(valor.strip().lower())
            else:
                normalizado = "no especificado"

            participacion_contador[normalizado] += 1

        # Preparar datos para gráfico de torta
        color_map = {
            "si": "#28a745",
            "no": "#dc3545",
            "en avance": "#ffc107",
            "no especificado": "#6c757d"
        }

        participacion_labels = []
        participacion_values = []
        participacion_colors = []

        for key, value in participacion_contador.items():
            participacion_labels.append(key.capitalize())
            participacion_values.append(value)
            participacion_colors.append(color_map.get(key, "#007bff"))

        # Calcular % de participación positiva



        with_participation = sum(
            participacion_contador[k] for k in participacion_contador
            if "si" in k or "avance" in k
        )
        participation_percent = round((with_participation / total_iniciativas * 100) if total_iniciativas > 0 else 0)

        pipeline_meses = [
            {
                "$match": {
                    "fecha_creacion": {"$type": "date"}
                }
            },
            {
                "$group": {
                    "_id": {
                        "month": {"$month": "$fecha_creacion"},
                        "year": {"$year": "$fecha_creacion"}
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id.year": 1, "_id.month": 1}}
        ]

        try:
            meses_data = list(coll.aggregate(pipeline_meses))
            meses_labels = [f"{item['_id']['month']}/{item['_id']['year']}" for item in meses_data]
            meses_values = [item["count"] for item in meses_data]
        except Exception as e:
            print(f"Error al procesar estadísticas por mes: {e}")
            meses_labels = []
            meses_values = []

        campos_stats = {}
        campos_a_verificar = ["descripcion", "monto", "codigo", "ubicacion", "Participación", "observaciones", "num_participantes"]

        for campo in campos_a_verificar:
            if campo == "Participación":
                count = coll.count_documents({
                    "$or": [{"Participación": True}, {"Participación": "true"}]
                })
            elif campo == "num_participantes":
                count = coll.count_documents({"num_participantes": {"$exists": True, "$gt": 0}})
            else:
                count = coll.count_documents({
                    "$or": [
                        {campo: {"$exists": True, "$ne": ""}},
                        {campo: {"$exists": True, "$gt": 0}},
                        {campo: {"$exists": True, "$eq": True}}
                    ]
                })


            campos_stats[campo] = {
                "count": count,
                "percent": float(round((count / total_iniciativas * 100), 2)) if total_iniciativas else 0.0

            }

        # al final de view_stats, antes del render_template
        total_iniciativas = int(total_iniciativas)
        collaborators_percent = float(collaborators_percent)
        participation_percent = float(participation_percent)
        # Fuerza todos los estados a enteros
        estados_data = {str(k): int(v) for k, v in estados_data.items()}
        # Y ya en tu campos_stats tú ya lo haces con int y float

        return render_template(
            'director/stats.html',
            total_iniciativas=total_iniciativas,
            estados_data=estados_data,
            with_collaborators=with_collaborators,
            collaborators_percent=collaborators_percent,
            with_participation=with_participation,
            participation_percent=participation_percent,
            participacion_labels=participacion_labels,
            participacion_values=participacion_values,
            participacion_colors=participacion_colors,
            meses_labels=meses_labels,
            meses_values=meses_values,
            campos_stats=campos_stats
        )

    except Exception as e:
        import traceback
        print(f"Error al generar estadísticas: {traceback.format_exc()}")
        flash(f'Error al cargar estadísticas: {str(e)}', 'danger')
        return redirect(url_for('director.dashboard'))


# En app/director/routes.py

# En app/director/routes.py y app/colaborador/routes.py

@director_bp.route('/iniciativas/<iniciativa_id>/minuta', methods=['GET', 'POST'])
@login_required
@director_required
def generate_minuta(iniciativa_id):
    """Generar minuta de la iniciativa."""
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
            return redirect(url_for('director.list_initiatives'))

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
                "updated_at": chile_to_utc(now_chile()),
                "updated_by": current_user.get_id()
            }

            # Actualizar la iniciativa con la configuración de minuta
            coll.update_one(
                {"_id": ObjectId(iniciativa_id)},
                {"$set": {"minuta_config": minuta_config}}
            )

            # Si el botón presionado fue "preview", redirigir a la vista previa
            if 'preview' in request.form:
                return redirect(url_for('director.preview_minuta', iniciativa_id=iniciativa_id))

            # Si fue "download", generar el PDF
            if 'download' in request.form:
                return redirect(url_for('director.download_minuta', iniciativa_id=iniciativa_id))

            flash('Configuración de minuta guardada correctamente', 'success')
            return redirect(url_for('director.generate_minuta', iniciativa_id=iniciativa_id))

        # Para GET, cargar la configuración guardada (si existe)
        minuta_config = iniciativa.get('minuta_config', {})

        return render_template(
            'director/minuta_generator.html',
            iniciativa=iniciativa_json,
            files=files_json,
            minuta_config=minuta_config,
            iniciativa_id=iniciativa_id
        )
    except Exception as e:
        import traceback
        print(f"Error en generate_minuta: {traceback.format_exc()}")
        flash(f'Error al generar minuta: {str(e)}', 'danger')
        return redirect(url_for('director.view_initiative', iniciativa_id=iniciativa_id))


@director_bp.route('/iniciativas/<iniciativa_id>/minuta/preview')
@login_required
@director_required
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
            return redirect(url_for('director.list_initiatives'))

        # Obtener configuración de minuta
        minuta_config = iniciativa.get('minuta_config', {})
        if not minuta_config:
            flash('No hay configuración de minuta guardada', 'warning')
            return redirect(url_for('director.generate_minuta', iniciativa_id=iniciativa_id))

        # Obtener imágenes seleccionadas
        selected_image_ids = minuta_config.get('selected_images', [])
        images = list(mongo.db.files.find({
            "_id": {"$in": [ObjectId(img_id) for img_id in selected_image_ids if img_id]},
            "active": True
        }))

        return render_template(
            'director/minuta_preview.html',
            iniciativa=iniciativa,
            minuta_config=minuta_config,
            images=images,
            iniciativa_id=iniciativa_id
        )
    except Exception as e:
        flash(f'Error al previsualizar minuta: {str(e)}', 'danger')
        return redirect(url_for('director.generate_minuta', iniciativa_id=iniciativa_id))


@director_bp.route('/iniciativas/<iniciativa_id>/minuta/download')
@login_required
@director_required
def download_minuta(iniciativa_id):
    """Descargar minuta como PDF usando ReportLab."""
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
            return redirect(url_for('director.list_initiatives'))

        # Obtener configuración de minuta
        minuta_config = iniciativa.get('minuta_config', {})
        if not minuta_config:
            flash('No hay configuración de minuta guardada', 'warning')
            return redirect(url_for('director.generate_minuta', iniciativa_id=iniciativa_id))

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
                bullet_items.append(ListItem(Paragraph("✅ Construcción y habilitación de infraestructura", normal_style)))

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
        fecha_chile = now_chile().strftime('%Y%m%d')
        filename = f"MINUTA_{safe_name}_{fecha_chile}.pdf"

        # Crear respuesta con el PDF
        response = current_app.response_class(
            pdf_data,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment;filename={filename}'}
        )

        return response
    except Exception as e:
        import traceback
        print(f"Error al descargar minuta: {traceback.format_exc()}")
        flash(f'Error al descargar minuta: {str(e)}', 'danger')
        return redirect(url_for('director.generate_minuta', iniciativa_id=iniciativa_id))