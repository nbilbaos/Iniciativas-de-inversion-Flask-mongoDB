# app/director/file_routes.py
import os
import uuid
from flask import render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from datetime import datetime

from . import director_bp
from ..auth.utils import director_required
from .. import mongo
from ..models.file import File, FileHistory
from ..forms.file_forms import UploadFileForm, UpdateFileForm, EnableFilesForm, AddDefaultFileForm


def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def get_file_type(filename):
    """Determina el tipo de archivo basado en su extensión."""
    ext = filename.rsplit('.', 1)[1].lower()

    # Mapeo de extensiones a tipos generales
    if ext in ['dwg', 'dxf', 'dwt', 'dwf', 'dws']:
        return 'autocad'
    elif ext in ['blend', '3ds', 'obj', 'fbx', 'stl']:
        return '3d'
    elif ext in ['doc', 'docx', 'odt']:
        return 'word'
    elif ext in ['xls', 'xlsx', 'ods']:
        return 'excel'
    elif ext in ['ppt', 'pptx', 'odp']:
        return 'powerpoint'
    elif ext == 'pdf':
        return 'pdf'
    elif ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tif', 'tiff', 'svg']:
        return 'image'
    elif ext in ['zip', 'rar', '7z', 'tar', 'gz']:
        return 'compressed'
    else:
        return 'other'


@director_bp.route('/iniciativas/<iniciativa_id>/archivos')
@login_required
@director_required
def manage_files(iniciativa_id):
    """Vista para gestionar archivos de una iniciativa."""
    try:
        # Obtener la iniciativa
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

        # Verificar si la gestión de archivos está habilitada
        files_enabled = iniciativa.get('files_enabled', False)

        # Formulario para habilitar/deshabilitar gestión de archivos
        enable_form = EnableFilesForm()
        enable_form.enable_files.data = files_enabled

        # Formulario para subir archivos
        upload_form = UploadFileForm()

        # Obtener archivos de la iniciativa
        files = list(mongo.db.files.find({
            "initiative_id": iniciativa_id,
            "active": True
        }).sort("uploaded_at", -1))

        # Obtener archivos predeterminados del sistema
        default_files = list(mongo.db.default_files.find({
            "active": True
        }).sort("uploaded_at", -1))

        # Obtener historial de archivos
        file_history = list(mongo.db.file_history.find({
            "initiative_id": iniciativa_id
        }).sort("timestamp", -1).limit(20))

        # Obtener información de usuarios para el historial
        user_ids = set()
        for entry in file_history:
            user_ids.add(entry.get('user_id'))

        users = {str(u['_id']): u for u in
                 mongo.db.users.find({
                     "_id": {"$in": [ObjectId(uid) for uid in user_ids if uid]}
                 })}

        # Formulario para agregar archivos predeterminados
        add_default_form = AddDefaultFileForm()

        return render_template(
            'director/manage_files.html',
            iniciativa=iniciativa,
            files=files,
            default_files=default_files,
            file_history=file_history,
            users=users,
            files_enabled=files_enabled,
            enable_form=enable_form,
            upload_form=upload_form,
            add_default_form=add_default_form,
            iniciativa_id=iniciativa_id
        )
    except Exception as e:
        import traceback
        print(f"Error al gestionar archivos: {traceback.format_exc()}")
        flash(f'Error al cargar la página de gestión de archivos: {str(e)}', 'danger')
        return redirect(url_for('director.view_initiative', iniciativa_id=iniciativa_id))


@director_bp.route('/iniciativas/<iniciativa_id>/archivos/enable', methods=['POST'])
@login_required
@director_required
def enable_files(iniciativa_id):
    """Habilitar o deshabilitar la gestión de archivos para una iniciativa."""
    try:
        form = EnableFilesForm()

        if form.validate_on_submit():
            enable = form.enable_files.data

            # Actualizar la iniciativa
            collection_name = current_app.config['INITIATIVES_COLLECTION']
            parts = collection_name.split('.')
            if len(parts) > 1:
                initiatives_coll = mongo.db[parts[0]][parts[1]]
            else:
                initiatives_coll = mongo.db[collection_name]

            initiatives_coll.update_one(
                {"_id": ObjectId(iniciativa_id)},
                {"$set": {"files_enabled": enable}}
            )

            # Registrar la acción en el historial
            action = 'enable_files' if enable else 'disable_files'
            history_entry = FileHistory(
                initiative_id=iniciativa_id,
                file_id=None,  # No hay archivo específico
                user_id=current_user.get_id(),
                action=action
            )

            mongo.db.file_history.insert_one(history_entry.to_dict())

            status = "habilitada" if enable else "deshabilitada"
            flash(f'Gestión de archivos {status} correctamente', 'success')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'Error en el campo {field}: {error}', 'danger')

        return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))
    except Exception as e:
        flash(f'Error al cambiar la configuración de archivos: {str(e)}', 'danger')
        return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))


@director_bp.route('/iniciativas/<iniciativa_id>/archivos/upload', methods=['POST'])
@login_required
@director_required
def upload_file(iniciativa_id):
    """Subir un archivo a una iniciativa."""
    try:
        # Verificar que la gestión de archivos esté habilitada
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

        if not iniciativa.get('files_enabled', False):
            flash('La gestión de archivos no está habilitada para esta iniciativa', 'danger')
            return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))

        form = UploadFileForm()

        if form.validate_on_submit():
            file = form.file.data
            description = form.description.data

            if file and allowed_file(file.filename):
                # Crear nombre de archivo seguro y único
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"

                # Asegurar que exista la carpeta de destino
                uploads_folder = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    iniciativa_id
                )
                os.makedirs(uploads_folder, exist_ok=True)

                # Guardar el archivo
                file_path = os.path.join(uploads_folder, unique_filename)
                file.save(file_path)

                # Crear entrada en la base de datos
                file_entry = File(
                    filename=unique_filename,
                    original_filename=filename,
                    file_path=file_path,
                    file_type=get_file_type(filename),
                    file_size=os.path.getsize(file_path),
                    initiative_id=iniciativa_id,
                    uploaded_by=current_user.get_id(),
                    description=description
                )

                file_id = mongo.db.files.insert_one(file_entry.to_dict()).inserted_id

                # Registrar en el historial
                history_entry = FileHistory(
                    initiative_id=iniciativa_id,
                    file_id=str(file_id),
                    user_id=current_user.get_id(),
                    action='upload',
                    details=f"Archivo: {filename}"
                )

                mongo.db.file_history.insert_one(history_entry.to_dict())

                flash(f'Archivo "{filename}" subido correctamente', 'success')
            else:
                flash('Tipo de archivo no permitido', 'danger')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'Error en el campo {field}: {error}', 'danger')

        return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))
    except Exception as e:
        import traceback
        print(f"Error al subir archivo: {traceback.format_exc()}")
        flash(f'Error al subir el archivo: {str(e)}', 'danger')
        return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))


@director_bp.route('/iniciativas/<iniciativa_id>/archivos/<file_id>/delete', methods=['POST'])
@login_required
@director_required
def delete_file(iniciativa_id, file_id):
    """Eliminar un archivo de una iniciativa."""
    try:
        # Verificar que el archivo existe
        file_data = mongo.db.files.find_one({"_id": ObjectId(file_id), "initiative_id": iniciativa_id})

        if not file_data:
            flash('Archivo no encontrado', 'danger')
            return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))

        # Marcar como inactivo en la base de datos (borrado lógico)
        mongo.db.files.update_one(
            {"_id": ObjectId(file_id)},
            {"$set": {"active": False}}
        )

        # Registrar en el historial
        history_entry = FileHistory(
            initiative_id=iniciativa_id,
            file_id=file_id,
            user_id=current_user.get_id(),
            action='delete',
            details=f"Archivo: {file_data.get('original_filename')}"
        )

        mongo.db.file_history.insert_one(history_entry.to_dict())

        flash(f'Archivo "{file_data.get("original_filename")}" eliminado correctamente', 'success')
        return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))
    except Exception as e:
        flash(f'Error al eliminar el archivo: {str(e)}', 'danger')
        return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))


@director_bp.route('/iniciativas/<iniciativa_id>/archivos/<file_id>/update', methods=['POST'])
@login_required
@director_required
def update_file_info(iniciativa_id, file_id):
    """Actualizar información de un archivo."""
    try:
        # Verificar que el archivo existe
        file_data = mongo.db.files.find_one({"_id": ObjectId(file_id), "initiative_id": iniciativa_id})

        if not file_data:
            flash('Archivo no encontrado', 'danger')
            return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))

        form = UpdateFileForm()

        if form.validate_on_submit():
            description = form.description.data

            # Actualizar la descripción
            mongo.db.files.update_one(
                {"_id": ObjectId(file_id)},
                {"$set": {
                    "description": description,
                    "last_modified": datetime.utcnow()
                }}
            )

            # Registrar en el historial
            history_entry = FileHistory(
                initiative_id=iniciativa_id,
                file_id=file_id,
                user_id=current_user.get_id(),
                action='update',
                details=f"Actualizada descripción del archivo: {file_data.get('original_filename')}"
            )

            mongo.db.file_history.insert_one(history_entry.to_dict())

            flash(f'Información del archivo actualizada correctamente', 'success')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'Error en el campo {field}: {error}', 'danger')

        return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))
    except Exception as e:
        flash(f'Error al actualizar la información del archivo: {str(e)}', 'danger')
        return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))


@director_bp.route('/iniciativas/<iniciativa_id>/archivos/<file_id>/download')
@login_required
def download_file(iniciativa_id, file_id):
    """Descargar un archivo."""
    try:
        # Verificar que el archivo existe y está activo
        file_data = mongo.db.files.find_one({
            "_id": ObjectId(file_id),
            "initiative_id": iniciativa_id,
            "active": True
        })

        if not file_data:
            flash('Archivo no encontrado o no disponible', 'danger')
            return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))

        # Obtener la ruta del archivo
        file_path = file_data.get('file_path')
        original_filename = file_data.get('original_filename')

        # Verificar que el archivo existe físicamente
        if not os.path.exists(file_path):
            flash('El archivo no se encuentra en el sistema', 'danger')
            return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))

        # Enviar el archivo para descarga
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)

        return send_from_directory(
            directory, filename, download_name=original_filename, as_attachment=True)
    except Exception as e:
        flash(f'Error al descargar el archivo: {str(e)}', 'danger')
        return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))


@director_bp.route('/default-files/add', methods=['POST'])
@login_required
@director_required
def add_default_file():
    """Agregar un archivo predeterminado del sistema."""
    try:
        form = AddDefaultFileForm()

        if form.validate_on_submit():
            file = form.file.data
            description = form.description.data
            category = form.file_category.data

            if file and allowed_file(file.filename):
                # Crear nombre de archivo seguro y único
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"

                # Asegurar que exista la carpeta de destino
                default_files_folder = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    'default_files'
                )
                os.makedirs(default_files_folder, exist_ok=True)

                # Guardar el archivo
                file_path = os.path.join(default_files_folder, unique_filename)
                file.save(file_path)

                # Crear entrada en la base de datos
                file_entry = {
                    'filename': unique_filename,
                    'original_filename': filename,
                    'file_path': file_path,
                    'file_type': get_file_type(filename),
                    'file_size': os.path.getsize(file_path),
                    'uploaded_by': current_user.get_id(),
                    'is_default': True,
                    'category': category,
                    'description': description,
                    'uploaded_at': datetime.utcnow(),
                    'last_modified': datetime.utcnow(),
                    'active': True
                }

                mongo.db.default_files.insert_one(file_entry)

                flash(f'Archivo predeterminado "{filename}" agregado correctamente', 'success')
            else:
                flash('Tipo de archivo no permitido', 'danger')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'Error en el campo {field}: {error}', 'danger')

        # Redirigir a la página anterior
        return redirect(request.referrer or url_for('director.dashboard'))
    except Exception as e:
        flash(f'Error al agregar el archivo predeterminado: {str(e)}', 'danger')
        return redirect(request.referrer or url_for('director.dashboard'))


@director_bp.route('/default-files/<file_id>/delete', methods=['POST'])
@login_required
@director_required
def delete_default_file(file_id):
    """Eliminar un archivo predeterminado del sistema."""
    try:
        # Verificar que el archivo existe
        file_data = mongo.db.default_files.find_one({"_id": ObjectId(file_id)})

        if not file_data:
            flash('Archivo predeterminado no encontrado', 'danger')
            return redirect(request.referrer or url_for('director.dashboard'))

        # Marcar como inactivo en la base de datos (borrado lógico)
        mongo.db.default_files.update_one(
            {"_id": ObjectId(file_id)},
            {"$set": {"active": False}}
        )

        flash(f'Archivo predeterminado "{file_data.get("original_filename")}" eliminado correctamente', 'success')
        return redirect(request.referrer or url_for('director.dashboard'))
    except Exception as e:
        flash(f'Error al eliminar el archivo predeterminado: {str(e)}', 'danger')
        return redirect(request.referrer or url_for('director.dashboard'))


@director_bp.route('/default-files/<file_id>/download')
@login_required
def download_default_file(file_id):
    """Descargar un archivo predeterminado."""
    try:
        # Verificar que el archivo existe y está activo
        file_data = mongo.db.default_files.find_one({
            "_id": ObjectId(file_id),
            "active": True
        })

        if not file_data:
            flash('Archivo predeterminado no encontrado o no disponible', 'danger')
            return redirect(request.referrer or url_for('director.dashboard'))

        # Obtener la ruta del archivo
        file_path = file_data.get('file_path')
        original_filename = file_data.get('original_filename')

        # Verificar que el archivo existe físicamente
        if not os.path.exists(file_path):
            flash('El archivo no se encuentra en el sistema', 'danger')
            return redirect(request.referrer or url_for('director.dashboard'))

        # Enviar el archivo para descarga
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)

        return send_from_directory(
            directory, filename, download_name=original_filename, as_attachment=True)
    except Exception as e:
        flash(f'Error al descargar el archivo predeterminado: {str(e)}', 'danger')
        return redirect(request.referrer or url_for('director.dashboard'))


@director_bp.route('/iniciativas/<iniciativa_id>/archivos/add-default/<file_id>', methods=['POST'])
@login_required
@director_required
def add_default_file_to_initiative(iniciativa_id, file_id):
    """Agregar un archivo predeterminado a una iniciativa."""
    try:
        # Verificar que la iniciativa existe y tiene habilitada la gestión de archivos
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

        if not iniciativa.get('files_enabled', False):
            flash('La gestión de archivos no está habilitada para esta iniciativa', 'danger')
            return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))

        # Verificar que el archivo predeterminado existe
        default_file = mongo.db.default_files.find_one({"_id": ObjectId(file_id), "active": True})

        if not default_file:
            flash('Archivo predeterminado no encontrado', 'danger')
            return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))

        # Verificar si el archivo ya está asociado a la iniciativa
        existing_file = mongo.db.files.find_one({
            "initiative_id": iniciativa_id,
            "original_filename": default_file.get("original_filename"),
            "is_default": True,
            "active": True
        })

        if existing_file:
            flash('Este archivo predeterminado ya está asociado a la iniciativa', 'warning')
            return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))

        # Copiar el archivo predeterminado a la iniciativa
        file_entry = File(
            filename=default_file.get('filename'),
            original_filename=default_file.get('original_filename'),
            file_path=default_file.get('file_path'),
            file_type=default_file.get('file_type'),
            file_size=default_file.get('file_size'),
            initiative_id=iniciativa_id,
            uploaded_by=current_user.get_id(),
            is_default=True,
            description=default_file.get('description', '')
        )

        file_id = mongo.db.files.insert_one(file_entry.to_dict()).inserted_id

        # Registrar en el historial
        history_entry = FileHistory(
            initiative_id=iniciativa_id,
            file_id=str(file_id),
            user_id=current_user.get_id(),
            action='upload',
            details=f"Archivo predeterminado añadido: {default_file.get('original_filename')}"
        )

        mongo.db.file_history.insert_one(history_entry.to_dict())

        flash(f'Archivo predeterminado "{default_file.get("original_filename")}" agregado a la iniciativa', 'success')
        return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))
    except Exception as e:
        flash(f'Error al agregar el archivo predeterminado a la iniciativa: {str(e)}', 'danger')
        return redirect(url_for('director.manage_files', iniciativa_id=iniciativa_id))