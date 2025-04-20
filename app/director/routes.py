from flask import (
    render_template, redirect, url_for,
    flash, request, current_app
)
from flask_login import login_required, current_user
from bson.objectid import ObjectId
import bcrypt
from datetime import datetime

from . import director_bp
from ..auth.utils import director_required
from .. import mongo, csrf
from ..models.user import User


@director_bp.route('/dashboard')
@login_required
@director_required
def dashboard():
    """Dashboard para el rol de director."""
    colaboradores = mongo.db.users.count_documents({"role": "colaborador"})
    stats = {'colaboradores': colaboradores}
    return render_template('director/dashboard.html', stats=stats)


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
            "created_at": datetime.utcnow(),
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
                {'cod': {'$regex': search, '$options': 'i'}}
            ]
        if status == 'active':
            filt['estado'] = 'activo'
        elif status == 'inactive':
            filt['estado'] = 'inactivo'

        print(f"DEBUG - Filtro de búsqueda: {filt}")

        # Obtener el nombre de la colección donde están las iniciativas
        collection_name = current_app.config['INITIATIVES_COLLECTION']
        print(f"DEBUG - Nombre de colección: {collection_name}")

        coll = mongo.db[collection_name]

        # Verificar que la colección existe y contiene documentos
        all_documents = list(coll.find().limit(3))
        print(f"DEBUG - Muestra de documentos en la colección: {all_documents}")

        # Verificar estructura de los documentos
        if all_documents:
            sample_doc = all_documents[0]
            print(f"DEBUG - Estructura del primer documento: {sample_doc.keys()}")
            if 'nombre' in sample_doc:
                print(f"DEBUG - Campo 'nombre' ejemplo: {sample_doc['nombre']}")
            if 'codigo' in sample_doc:
                print(f"DEBUG - Campo 'codigo' ejemplo: {sample_doc['codigo']}")
            if 'estado' in sample_doc:
                print(f"DEBUG - Campo 'estado' ejemplo: {sample_doc['estado']}")

        # Ejecutar la consulta con el filtro
        total = coll.count_documents(filt)
        print(f"DEBUG - Total de documentos encontrados con filtro: {total}")

        iniciativas = list(coll.find(filt).skip(skip).limit(per_page))
        print(f"DEBUG - Iniciativas encontradas: {len(iniciativas)}")
        # Fin de depuración

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
            collection_name=collection_name
        )
    except Exception as e:
        print(f"DEBUG - Error: {str(e)}")
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
            "role": {"$in": ["colaborador", "director"]}
        }))

        assigned = iniciativa.get('assigned_users') or []
        assigned_users = list(mongo.db.users.find({
            "_id": {"$in": [ObjectId(u) for u in assigned]}
        })) if assigned else []

        history = list(mongo.db.assignment_history.find(
            {"initiative_id": iniciativa_id}
        ).sort("timestamp", -1))

        return render_template(
            'director/view_initiative.html',
            iniciativa=iniciativa,
            colaboradores=colaboradores,
            assigned_users=assigned_users,
            assignments_history=history,
            collection_name=collection_name
        )
    except Exception as e:
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
                "timestamp": datetime.utcnow(),
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
                history_entry = {
                    "initiative_id": iniciativa_id,
                    "initiative_name": iniciativa.get('nombre', 'Sin nombre'),
                    "type": "assignment",
                    "user_id": user_id,
                    "user_email": user.get('email', 'Desconocido'),
                    "assigned_by": current_user.get_id(),
                    "assigned_by_email": current_user.email,
                    "timestamp": datetime.utcnow()
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
                            "assigned_at": datetime.utcnow(),
                            "active": True
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
                    "timestamp": datetime.utcnow()
                }
                mongo.db.assignment_history.insert_one(history_entry)

                # Actualizar el registro del usuario
                mongo.db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {
                        "iniciativas.$[elem].active": False,
                        "iniciativas.$[elem].removed_by": current_user.get_id(),
                        "iniciativas.$[elem].removed_at": datetime.utcnow()
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