from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from bson.objectid import ObjectId
import bcrypt
from datetime import datetime

from wtforms import StringField, SelectField, BooleanField, DateField
from wtforms.validators import Email

from . import admin_bp
from ..auth.utils import admin_required
from .. import mongo
from ..models.user import User
import pandas as pd
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import current_app

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Dashboard de administrador."""
    try:
        # Obtener estadísticas básicas
        total_users = mongo.db.users.count_documents({})
        directors = mongo.db.users.count_documents({"role": "director"})
        colaboradores = mongo.db.users.count_documents({"role": "colaborador"})

        stats = {
            'total_users': total_users,
            'directors': directors,
            'colaboradores': colaboradores
        }

        print(f"Estadísticas obtenidas: {stats}")
        return render_template('admin/dashboard.html', stats=stats)
    except Exception as e:
        print(f"Error en dashboard de admin: {str(e)}")
        flash(f"Error al cargar el dashboard: {str(e)}", "danger")
        return redirect(url_for('index'))


@admin_bp.route('/users')
@login_required
@admin_required
def user_list():
    """Lista de usuarios para administrar."""
    users = list(mongo.db.users.find())
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/<user_id>')
@login_required
@admin_required
def user_detail(user_id):
    """Detalle de un usuario específico."""
    user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not user_data:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('admin.user_list'))

    user = User(**user_data)
    return render_template('admin/user_detail.html', user=user)


@admin_bp.route('/users/<user_id>/toggle_active', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    """Activar o desactivar un usuario."""
    user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not user_data:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('admin.user_list'))

    # No permitir desactivar al propio usuario administrador
    if str(user_data["_id"]) == current_user.get_id():
        flash('No puedes desactivar tu propia cuenta', 'danger')
        return redirect(url_for('admin.user_list'))

    # Cambiar el estado activo
    new_status = not user_data.get('active', True)
    mongo.db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"active": new_status}}
    )

    status_str = 'activado' if new_status else 'desactivado'
    flash(f'Usuario {user_data["email"]} {status_str} correctamente', 'success')
    return redirect(url_for('admin.user_list'))


@admin_bp.route('/users/<user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Eliminar un usuario."""
    user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not user_data:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('admin.user_list'))

    # No permitir eliminar al propio usuario administrador
    if str(user_data["_id"]) == current_user.get_id():
        flash('No puedes eliminar tu propia cuenta', 'danger')
        return redirect(url_for('admin.user_list'))

    # Eliminar el usuario
    mongo.db.users.delete_one({"_id": ObjectId(user_id)})
    flash(f'Usuario {user_data["email"]} eliminado correctamente', 'success')
    return redirect(url_for('admin.user_list'))


@admin_bp.route('/users/<user_id>/reset_password', methods=['POST'])
@login_required
@admin_required
def reset_user_password(user_id):
    """Restablecer la contraseña de un usuario."""
    user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not user_data:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('admin.user_list'))

    # Crear una contraseña temporal
    temp_password = "Temporal123!"
    hashed_password = bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt())

    # Actualizar la contraseña del usuario
    mongo.db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password": hashed_password}}
    )

    flash(f'Contraseña restablecida para {user_data["email"]}. Nueva contraseña: {temp_password}', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<user_id>/change_role', methods=['POST'])
@login_required
@admin_required
def change_user_role(user_id):
    """Cambiar el rol de un usuario."""
    user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not user_data:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('admin.user_list'))

    # No permitir cambiar el rol del propio administrador
    if str(user_data["_id"]) == current_user.get_id():
        flash('No puedes cambiar tu propio rol', 'danger')
        return redirect(url_for('admin.user_list'))

    # Obtener el nuevo rol desde el formulario
    new_role = request.form.get('role')
    if new_role not in ['admin', 'director', 'colaborador']:
        flash('Rol no válido', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))

    # Actualizar el rol del usuario
    mongo.db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": new_role}}
    )

    flash(f'Rol de {user_data["email"]} actualizado a {new_role}', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/export', methods=['GET'])
@login_required
@admin_required
def export_users():
    """Exportar lista de usuarios en formato JSON."""
    users = list(mongo.db.users.find({}, {'password': 0}))  # Excluir contraseñas

    # Convertir ObjectId a string para serialización JSON
    for user in users:
        user['_id'] = str(user['_id'])
        if 'created_at' in user:
            user['created_at'] = user['created_at'].isoformat() if user['created_at'] else None
        if 'last_login' in user:
            user['last_login'] = user['last_login'].isoformat() if user['last_login'] else None

    return jsonify(users)


@admin_bp.route('/user_detail/<user_id>', methods=['GET'])
@login_required
@admin_required
def user_detail_page(user_id):
    """Página de detalle de usuario."""
    try:
        user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        if not user_data:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('admin.user_list'))

        return render_template('admin/user_detail.html', user=user_data)
    except Exception as e:
        flash(f'Error al cargar los detalles del usuario: {str(e)}', 'danger')
        return redirect(url_for('admin.user_list'))


@admin_bp.route('/users/<user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Editar cualquier campo de un usuario de manera dinámica."""
    try:
        user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        if not user_data:
            flash('Usuario no encontrado', 'danger')
            return redirect(url_for('admin.user_list'))

        # Crear un formulario dinámico basado en los campos existentes
        from flask_wtf import FlaskForm
        from wtforms import StringField, SelectField, BooleanField, SubmitField, TextAreaField
        from wtforms.validators import DataRequired, Email, Optional

        class UserEditForm(FlaskForm):
            email = StringField('Correo Electrónico', validators=[DataRequired(), Email()])
            nombre = StringField('Nombre Completo', validators=[DataRequired()])
            rut = StringField('RUT', validators=[DataRequired()])
            telefono = StringField('Teléfono de Contacto', validators=[Optional()])
            role = SelectField('Rol', choices=[
                ('admin', 'Administrador'),
                ('director', 'Director'),
                ('colaborador', 'Colaborador')
            ], validators=[DataRequired()])
            direccion = StringField('Dirección', validators=[Optional()])
            titulos = StringField('Títulos (separados por coma)', validators=[Optional()])
            active = BooleanField('Usuario Activo')
            submit = SubmitField('Guardar Cambios')

        form = UserEditForm()

        # Para el método GET, prellenar el formulario con los datos existentes
        if request.method == 'GET':
            form.email.data = user_data.get('email', '')
            form.nombre.data = user_data.get('nombre', '')
            form.rut.data = user_data.get('rut', '')
            form.telefono.data = user_data.get('telefono', '')
            form.role.data = user_data.get('role', 'colaborador')
            form.direccion.data = user_data.get('direccion', '')
            form.titulos.data = user_data.get('titulos', '')
            form.active.data = user_data.get('active', True)

        # Procesar el envío del formulario
        if form.validate_on_submit():
            # No permitir que un administrador se desactive a sí mismo
            if str(user_data["_id"]) == current_user.get_id() and form.active.data == False:
                flash('No puedes desactivar tu propia cuenta', 'danger')
                return redirect(url_for('admin.edit_user', user_id=user_id))

            # Preparar datos para la actualización
            update_data = {
                'email': form.email.data,
                'nombre': form.nombre.data,
                'rut': form.rut.data,
                'telefono': form.telefono.data,
                'role': form.role.data,
                'direccion': form.direccion.data,
                'titulos': form.titulos.data,
                'active': form.active.data
            }

            # Actualizar en la base de datos
            result = mongo.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                flash('Usuario actualizado correctamente', 'success')
            else:
                flash('No se realizaron cambios', 'info')

            return redirect(url_for('admin.user_detail', user_id=user_id))

        return render_template('admin/edit_user.html', form=form, user=user_data)

    except Exception as e:
        flash(f'Error al editar el usuario: {str(e)}', 'danger')
        return redirect(url_for('admin.user_list'))



@admin_bp.route('/upload-excel', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_excel():
    """Subir archivo Excel y convertirlo a una colección MongoDB."""
    from ..admin.forms import ExcelUploadForm

    form = ExcelUploadForm()

    if form.validate_on_submit():
        try:
            # Guardar el archivo temporalmente
            f = form.excel_file.data
            filename = secure_filename(f.filename)
            temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            f.save(temp_path)

            # Procesar el archivo Excel
            collection_name = form.collection_name.data
            target_db = form.target_db.data

            # Leer el archivo Excel con pandas
            df = pd.read_excel(temp_path, dtype=str)  # Usar dtype=str para manejar todo como texto inicialmente

            # Limpiar nombres de columnas (quitar espacios, caracteres especiales)
            df.columns = [clean_column_name(col) for col in df.columns]

            # Convertir DataFrame a lista de diccionarios (documentos para MongoDB)
            documents = df.to_dict('records')

            # Añadir metadatos
            metadata = {
                'upload_date': datetime.utcnow(),
                'uploaded_by': current_user.get_id(),
                'original_filename': filename,
                'column_count': len(df.columns),
                'row_count': len(df),
                'columns': list(df.columns)
            }

            # Seleccionar la base de datos correcta
            if target_db == 'db_metadata':
                db = mongo.db.db_metadata
            else:
                db = mongo.db

            # Guardar metadatos
            meta_id = db.excel_imports.insert_one(metadata).inserted_id

            # Insertar los documentos en la colección
            result = db[collection_name].insert_many(documents)

            # Actualizar metadatos con el ID de la colección
            db.excel_imports.update_one(
                {'_id': meta_id},
                {'$set': {'collection_id': collection_name}}
            )

            # Eliminar el archivo temporal
            os.remove(temp_path)

            flash(
                f'Archivo Excel procesado correctamente. Se insertaron {len(result.inserted_ids)} documentos en la colección {collection_name}.',
                'success')
            return redirect(url_for('admin.excel_collections'))

        except Exception as e:
            flash(f'Error al procesar el archivo Excel: {str(e)}', 'danger')
            # Si existe el archivo temporal, eliminarlo
            if os.path.exists(temp_path):
                os.remove(temp_path)

    return render_template('admin/upload_excel.html', form=form)


def clean_column_name(column_name):
    """Limpia el nombre de la columna para hacerlo compatible con MongoDB."""
    import re
    # Reemplazar espacios y caracteres especiales por guiones bajos
    cleaned = re.sub(r'[^\w\s]', '_', column_name)
    # Reemplazar espacios por guiones bajos y convertir a minúsculas
    cleaned = re.sub(r'\s+', '_', cleaned).lower()
    # Asegurarse de que no empiece con números
    if cleaned[0].isdigit():
        cleaned = 'col_' + cleaned
    return cleaned


@admin_bp.route('/excel-collections')
@login_required
@admin_required
def excel_collections():
    """Ver las colecciones creadas a partir de archivos Excel."""
    # Obtener todas las importaciones de Excel
    metadata_imports = list(mongo.db.db_metadata.excel_imports.find().sort('upload_date', -1))
    main_imports = list(mongo.db.excel_imports.find().sort('upload_date', -1))

    # Combinar las importaciones
    all_imports = metadata_imports + main_imports
    all_imports.sort(key=lambda x: x.get('upload_date', datetime.min), reverse=True)

    return render_template('admin/excel_collections.html', imports=all_imports)


@admin_bp.route('/excel-collection/<db_name>/<collection_name>')
@login_required
@admin_required
def view_excel_collection(db_name, collection_name):
    """Ver el contenido de una colección creada a partir de un archivo Excel."""
    try:
        # Seleccionar la base de datos correcta
        if db_name == 'db_metadata':
            db = mongo.db.db_metadata
        else:
            db = mongo.db

        # Obtener los documentos de la colección (paginados)
        page = request.args.get('page', 1, type=int)
        per_page = 20
        skip = (page - 1) * per_page

        total = db[collection_name].count_documents({})
        documents = list(db[collection_name].find().skip(skip).limit(per_page))

        # Obtener los nombres de las columnas
        if documents:
            columns = list(documents[0].keys())
        else:
            columns = []

        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page  # Ceiling division
        }

        return render_template(
            'admin/view_excel_collection.html',
            db_name=db_name,
            collection_name=collection_name,
            documents=documents,
            columns=columns,
            pagination=pagination
        )
    except Exception as e:
        flash(f'Error al visualizar la colección: {str(e)}', 'danger')
        return redirect(url_for('admin.excel_collections'))


@admin_bp.route('/excel-collection/<db_name>/<collection_name>/delete', methods=['POST'])
@login_required
@admin_required
def delete_excel_collection(db_name, collection_name):
    """Eliminar una colección creada a partir de un archivo Excel."""
    try:
        # Seleccionar la base de datos correcta
        if db_name == 'db_metadata':
            db = mongo.db.db_metadata
        else:
            db = mongo.db

        # Eliminar la colección
        db[collection_name].drop()

        # Eliminar los metadatos asociados
        db.excel_imports.delete_many({'collection_id': collection_name})

        flash(f'Colección {collection_name} eliminada correctamente.', 'success')
    except Exception as e:
        flash(f'Error al eliminar la colección: {str(e)}', 'danger')

    return redirect(url_for('admin.excel_collections'))