# app/colaborador/file_routes.py
import os
import uuid
from flask import render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from datetime import datetime

from . import colaborador_bp
from ..auth.utils import role_required
from .. import mongo
from ..models.file import File, FileHistory
from ..forms.file_forms import UploadFileForm, UpdateFileForm


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


@colaborador_bp.route('/iniciativas/<iniciativa_id>/archivos')
@login_required
@role_required(['colaborador'])
def view_files(iniciativa_id):
    """Vista para ver los archivos de una iniciativa."""
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
            return redirect(url_for('colaborador.my_initiatives'))

        # Verificar si la gestión de archivos está habilitada
        files_enabled = iniciativa.get('files_enabled', False)

        if not files_enabled:
            flash('La gestión de archivos no está habilitada para esta iniciativa', 'warning')
            return redirect(url_for('colaborador.view_initiative_detail', iniciativa_id=iniciativa_id))

        # Formulario para subir archivos
        upload_form = UploadFileForm()

        # Obtener archivos de la iniciativa
        files = list(mongo.db.files.find({
            "initiative_id": iniciativa_id,
            "active": True
        }).sort("uploaded_at", -1))

        # Obtener información de usuarios para los archivos
        user_ids = set()
        for file in files:
            user_ids.add(file.get('uploaded_by'))

        users = {str(u['_id']): u for u in
                 mongo.db.users.find({
                     "_id": {"$in": [ObjectId(uid) for uid in user_ids if uid]}
                 })}

        return render_template(
            'colaborador/view_files.html',
            iniciativa=iniciativa,
            files=files,
            users=users,
            files_enabled=files_enabled,
            upload_form=upload_form,
            iniciativa_id=iniciativa_id
        )
    except Exception as e:
        import traceback
        print(f"Error al ver archivos: {traceback.format_exc()}")
        flash(f'Error al cargar la página de archivos: {str(e)}', 'danger')
        return redirect(url_for('colaborador.view_initiative_detail', iniciativa_id=iniciativa_id))


@colaborador_bp.route('/iniciativas/<iniciativa_id>/archivos/upload', methods=['POST'])
@login_required
@role_required(['colaborador'])
def upload_file(iniciativa_id):
    """Subir un archivo a una iniciativa."""
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
            return redirect(url_for('colaborador.my_initiatives'))

        if not iniciativa.get('files_enabled', False):
            flash('La gestión de archivos no está habilitada para esta iniciativa', 'danger')
            return redirect(url_for('colaborador.view_initiative_detail', iniciativa_id=iniciativa_id))

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

        return redirect(url_for('colaborador.view_files', iniciativa_id=iniciativa_id))
    except Exception as e:
        import traceback
        print(f"Error al subir archivo: {traceback.format_exc()}")
        flash(f'Error al subir el archivo: {str(e)}', 'danger')
        return redirect(url_for('colaborador.view_files', iniciativa_id=iniciativa_id))


@colaborador_bp.route('/iniciativas/<iniciativa_id>/archivos/<file_id>/update', methods=['POST'])
@login_required
@role_required(['colaborador'])
def update_file_info(iniciativa_id, file_id):
    """Actualizar información de un archivo."""
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

        # Verificar que el archivo existe y pertenece al usuario
        file_data = mongo.db.files.find_one({
            "_id": ObjectId(file_id),
            "initiative_id": iniciativa_id,
            "uploaded_by": current_user.get_id()  # Solo puede actualizar sus propios archivos
        })

        if not file_data:
            flash('Archivo no encontrado o no tienes permisos para modificarlo', 'danger')
            return redirect(url_for('colaborador.view_files', iniciativa_id=iniciativa_id))

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

        return redirect(url_for('colaborador.view_files', iniciativa_id=iniciativa_id))
    except Exception as e:
        flash(f'Error al actualizar la información del archivo: {str(e)}', 'danger')
        return redirect(url_for('colaborador.view_files', iniciativa_id=iniciativa_id))


@colaborador_bp.route('/iniciativas/<iniciativa_id>/archivos/<file_id>/download')
@login_required
@role_required(['colaborador'])
def download_file(iniciativa_id, file_id):
    """Descargar un archivo."""
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

        # Verificar que el archivo existe y está activo
        file_data = mongo.db.files.find_one({
            "_id": ObjectId(file_id),
            "initiative_id": iniciativa_id,
            "active": True
        })

        if not file_data:
            flash('Archivo no encontrado o no disponible', 'danger')
            return redirect(url_for('colaborador.view_files', iniciativa_id=iniciativa_id))

        # Obtener la ruta del archivo
        file_path = file_data.get('file_path')
        original_filename = file_data.get('original_filename')

        # Verificar que el archivo existe físicamente
        if not os.path.exists(file_path):
            flash('El archivo no se encuentra en el sistema', 'danger')
            return redirect(url_for('colaborador.view_files', iniciativa_id=iniciativa_id))

        # Enviar el archivo para descarga
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)

        return send_from_directory(
            directory, filename, download_name=original_filename, as_attachment=True)
    except Exception as e:
        flash(f'Error al descargar el archivo: {str(e)}', 'danger')
        return redirect(url_for('colaborador.view_files', iniciativa_id=iniciativa_id))