from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from bson.objectid import ObjectId
from datetime import datetime
import json
import csv
import io

from . import admin_bp
from ..auth.utils import admin_required
from .. import mongo
from ..models.database import DatabaseCollection, CollectionField

# Constante para la colección de metadatos
METADATA_COLLECTION = 'db_metadata'


@admin_bp.route('/database/collections')
@login_required
@admin_required
def list_collections():
    """Listar todas las colecciones definidas en la base de datos."""
    try:
        # Obtener metadatos de las colecciones desde la colección especial
        metadata = list(mongo.db[METADATA_COLLECTION].find().sort('name', 1))

        # Obtener estadísticas de cada colección (número de documentos)
        for col in metadata:
            if 'name' in col:
                try:
                    col['document_count'] = mongo.db[col['name']].count_documents({})
                except Exception:
                    col['document_count'] = 0

        return render_template('admin/database/collections.html', collections=metadata)
    except Exception as e:
        flash(f'Error al cargar las colecciones: {str(e)}', 'danger')
        return render_template('admin/database/collections.html', collections=[])


@admin_bp.route('/database/collections/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create_collection():
    """Crear una nueva colección en la base de datos."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        # Validar datos
        if not name:
            flash('El nombre de la colección es obligatorio', 'danger')
            return render_template('admin/database/create_collection.html')

        # Validar que el nombre no contenga caracteres especiales
        if not name.isalnum() and '_' not in name:
            flash('El nombre de la colección solo puede contener letras, números y guiones bajos', 'danger')
            return render_template('admin/database/create_collection.html')

        # Verificar si ya existe una colección con ese nombre
        if mongo.db[METADATA_COLLECTION].find_one({'name': name}):
            flash(f'Ya existe una colección con el nombre "{name}"', 'danger')
            return render_template('admin/database/create_collection.html')

        # Crear la colección
        collection = DatabaseCollection(
            name=name,
            description=description
        )

        # Guardar los metadatos de la colección
        mongo.db[METADATA_COLLECTION].insert_one(collection.to_dict())

        flash(f'Colección "{name}" creada correctamente', 'success')
        return redirect(url_for('admin.edit_collection', collection_id=str(collection._id)))

    return render_template('admin/database/create_collection.html')


@admin_bp.route('/database/collections/<collection_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_collection(collection_id):
    """Editar una colección existente."""
    # Obtener metadatos de la colección
    collection_data = mongo.db[METADATA_COLLECTION].find_one({'_id': ObjectId(collection_id)})

    if not collection_data:
        flash('Colección no encontrada', 'danger')
        return redirect(url_for('admin.list_collections'))

    collection = DatabaseCollection.from_dict(collection_data)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_info':
            # Actualizar información básica de la colección
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()

            # Validar datos
            if not name:
                flash('El nombre de la colección es obligatorio', 'danger')
                return render_template('admin/database/edit_collection.html', collection=collection)

            # Si el nombre ha cambiado, verificar que no exista otra colección con ese nombre
            if name != collection.name and mongo.db[METADATA_COLLECTION].find_one({'name': name}):
                flash(f'Ya existe una colección con el nombre "{name}"', 'danger')
                return render_template('admin/database/edit_collection.html', collection=collection)

            # Actualizar la colección
            old_name = collection.name
            collection.name = name
            collection.description = description
            collection.updated_at = datetime.utcnow()

            # Actualizar los metadatos
            mongo.db[METADATA_COLLECTION].update_one(
                {'_id': ObjectId(collection_id)},
                {'$set': collection.to_dict()}
            )

            # Si cambió el nombre, renombrar la colección real en MongoDB
            if old_name != name and old_name in mongo.db.list_collection_names():
                mongo.db[old_name].rename(name)

            flash(f'Colección "{name}" actualizada correctamente', 'success')

        elif action == 'add_field':
            # Redirigir al formulario para añadir un nuevo campo
            return redirect(url_for('admin.add_field', collection_id=collection_id))

    return render_template('admin/database/edit_collection.html', collection=collection)


@admin_bp.route('/database/collections/<collection_id>/fields/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_field(collection_id):
    """Añadir un nuevo campo a una colección."""
    collection_data = mongo.db[METADATA_COLLECTION].find_one({'_id': ObjectId(collection_id)})

    if not collection_data:
        flash('Colección no encontrada', 'danger')
        return redirect(url_for('admin.list_collections'))

    collection = DatabaseCollection.from_dict(collection_data)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        field_type = request.form.get('field_type')
        required = request.form.get('required') == 'on'
        description = request.form.get('description', '').strip()

        # Validar datos
        if not name or not field_type:
            flash('El nombre y tipo del campo son obligatorios', 'danger')
            return render_template('admin/database/add_field.html', collection=collection,
                                   field_types=CollectionField.FIELD_TYPES)

        # Verificar que no exista otro campo con el mismo nombre
        if any(field.name == name for field in collection.fields):
            flash(f'Ya existe un campo con el nombre "{name}" en esta colección', 'danger')
            return render_template('admin/database/add_field.html', collection=collection,
                                   field_types=CollectionField.FIELD_TYPES)

        # Verificar que el nombre no contenga caracteres especiales
        if not name.replace('_', '').isalnum():
            flash('El nombre del campo solo puede contener letras, números y guiones bajos', 'danger')
            return render_template('admin/database/add_field.html', collection=collection,
                                   field_types=CollectionField.FIELD_TYPES)

        # Crear el nuevo campo
        options = {}

        # Manejar opciones específicas según el tipo de campo
        if field_type == 'enum':
            enum_values = request.form.get('enum_values', '').strip().split(',')
            enum_values = [value.strip() for value in enum_values if value.strip()]
            if not enum_values:
                flash('Debe proporcionar al menos un valor para el campo de tipo lista de opciones', 'danger')
                return render_template('admin/database/add_field.html', collection=collection,
                                       field_types=CollectionField.FIELD_TYPES)
            options['values'] = enum_values

        elif field_type == 'reference':
            reference_collection = request.form.get('reference_collection')
            if not reference_collection:
                flash('Debe seleccionar una colección de referencia', 'danger')
                return render_template('admin/database/add_field.html', collection=collection,
                                       field_types=CollectionField.FIELD_TYPES)
            options['reference_collection'] = reference_collection

        # Crear y añadir el campo
        field = CollectionField(
            name=name,
            field_type=field_type,
            required=required,
            description=description,
            options=options
        )

        collection.add_field(field)

        # Actualizar metadatos de la colección
        mongo.db[METADATA_COLLECTION].update_one(
            {'_id': ObjectId(collection_id)},
            {'$set': collection.to_dict()}
        )

        flash(f'Campo "{name}" añadido correctamente a la colección "{collection.name}"', 'success')
        return redirect(url_for('admin.edit_collection', collection_id=collection_id))

    # Obtener todas las colecciones para referencias
    all_collections = list(mongo.db[METADATA_COLLECTION].find().sort('name', 1))

    return render_template(
        'admin/database/add_field.html',
        collection=collection,
        field_types=CollectionField.FIELD_TYPES,
        all_collections=all_collections
    )


@admin_bp.route('/database/collections/<collection_id>/fields/<field_name>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_field(collection_id, field_name):
    """Editar un campo existente en una colección."""
    collection_data = mongo.db[METADATA_COLLECTION].find_one({'_id': ObjectId(collection_id)})

    if not collection_data:
        flash('Colección no encontrada', 'danger')
        return redirect(url_for('admin.list_collections'))

    collection = DatabaseCollection.from_dict(collection_data)

    # Buscar el campo por nombre
    field = next((f for f in collection.fields if f.name == field_name), None)

    if not field:
        flash(f'Campo "{field_name}" no encontrado en la colección', 'danger')
        return redirect(url_for('admin.edit_collection', collection_id=collection_id))

    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        required = request.form.get('required') == 'on'

        # Actualizar el campo
        field.description = description
        field.required = required

        # Actualizar opciones específicas según el tipo
        if field.field_type == 'enum':
            enum_values = request.form.get('enum_values', '').strip().split(',')
            enum_values = [value.strip() for value in enum_values if value.strip()]
            if not enum_values:
                flash('Debe proporcionar al menos un valor para el campo de tipo lista de opciones', 'danger')
                return render_template('admin/database/edit_field.html', collection=collection, field=field)
            field.options['values'] = enum_values

        # Actualizar la colección con el campo modificado
        collection.update_field(field_name, field)

        # Guardar cambios en la base de datos
        mongo.db[METADATA_COLLECTION].update_one(
            {'_id': ObjectId(collection_id)},
            {'$set': collection.to_dict()}
        )

        flash(f'Campo "{field_name}" actualizado correctamente', 'success')
        return redirect(url_for('admin.edit_collection', collection_id=collection_id))

    return render_template(
        'admin/database/edit_field.html',
        collection=collection,
        field=field
    )


@admin_bp.route('/database/collections/<collection_id>/fields/<field_name>/delete', methods=['POST'])
@login_required
@admin_required
def delete_field(collection_id, field_name):
    """Eliminar un campo de una colección."""
    collection_data = mongo.db[METADATA_COLLECTION].find_one({'_id': ObjectId(collection_id)})

    if not collection_data:
        flash('Colección no encontrada', 'danger')
        return redirect(url_for('admin.list_collections'))

    collection = DatabaseCollection.from_dict(collection_data)

    # Verificar si el campo existe
    if not any(f.name == field_name for f in collection.fields):
        flash(f'Campo "{field_name}" no encontrado en la colección', 'danger')
        return redirect(url_for('admin.edit_collection', collection_id=collection_id))

    # Eliminar el campo
    collection.remove_field(field_name)

    # Actualizar metadatos
    mongo.db[METADATA_COLLECTION].update_one(
        {'_id': ObjectId(collection_id)},
        {'$set': collection.to_dict()}
    )

    # Opcional: Actualizar documentos existentes para eliminar el campo
    if collection.name in mongo.db.list_collection_names():
        mongo.db[collection.name].update_many({}, {'$unset': {field_name: ""}})

    flash(f'Campo "{field_name}" eliminado correctamente de la colección "{collection.name}"', 'success')
    return redirect(url_for('admin.edit_collection', collection_id=collection_id))


@admin_bp.route('/database/collections/<collection_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_collection(collection_id):
    """Eliminar una colección de la base de datos."""
    collection_data = mongo.db[METADATA_COLLECTION].find_one({'_id': ObjectId(collection_id)})

    if not collection_data:
        flash('Colección no encontrada', 'danger')
        return redirect(url_for('admin.list_collections'))

    collection_name = collection_data['name']

    # Eliminar la colección de metadatos
    mongo.db[METADATA_COLLECTION].delete_one({'_id': ObjectId(collection_id)})

    # Eliminar la colección real si existe
    if collection_name in mongo.db.list_collection_names():
        mongo.db[collection_name].drop()

    flash(f'Colección "{collection_name}" eliminada correctamente', 'success')
    return redirect(url_for('admin.list_collections'))


@admin_bp.route('/database/export', methods=['GET', 'POST'])
@login_required
@admin_required
def export_database():
    """Exportar la base de datos de iniciativas de inversión."""
    if request.method == 'POST':
        export_format = request.form.get('format', 'json')

        # Obtener metadatos de todas las colecciones
        collections_metadata = list(mongo.db[METADATA_COLLECTION].find())

        if export_format == 'json':
            # Crear estructura para la exportación
            export_data = {
                'metadata': collections_metadata,
                'collections': {}
            }

            # Obtener datos de cada colección
            for col_meta in collections_metadata:
                collection_name = col_meta['name']
                if collection_name in mongo.db.list_collection_names():
                    export_data['collections'][collection_name] = list(mongo.db[collection_name].find())

            # Convertir ObjectId a strings para la serialización JSON
            export_json = json.dumps(export_data, default=str, indent=2)

            # Devolver como archivo de descarga
            return jsonify({
                'success': True,
                'data': export_json,
                'filename': f'database_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            })

        elif export_format == 'csv':
            # Crear un archivo CSV por cada colección
            collection_csvs = {}

            for col_meta in collections_metadata:
                collection_name = col_meta['name']

                if collection_name in mongo.db.list_collection_names():
                    documents = list(mongo.db[collection_name].find())

                    if documents:
                        # Crear un buffer de memoria para el CSV
                        output = io.StringIO()
                        writer = csv.DictWriter(output, fieldnames=documents[0].keys())
                        writer.writeheader()

                        for doc in documents:
                            # Convertir ObjectId a strings para CSV
                            for key, value in doc.items():
                                if isinstance(value, ObjectId):
                                    doc[key] = str(value)

                            writer.writerow(doc)

                        collection_csvs[collection_name] = output.getvalue()
                        output.close()

            return jsonify({
                'success': True,
                'data': collection_csvs,
                'filename_prefix': f'database_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            })

    return render_template('admin/database/export.html')


@admin_bp.route('/database/collections/<collection_id>/view', methods=['GET'])
@login_required
@admin_required
def view_collection_data(collection_id):
    """Ver los datos de una colección en formato de hoja de cálculo."""
    # Obtener metadatos de la colección
    collection_data = mongo.db[METADATA_COLLECTION].find_one({'_id': ObjectId(collection_id)})

    if not collection_data:
        flash('Colección no encontrada', 'danger')
        return redirect(url_for('admin.list_collections'))

    collection = DatabaseCollection.from_dict(collection_data)

    # Preparar parámetros de paginación y ordenación
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', '_id')
    sort_dir = request.args.get('sort_dir', 'asc')

    # Calcular el número de documentos a omitir para la paginación
    skip = (page - 1) * per_page

    # Definir el orden
    sort_direction = 1 if sort_dir == 'asc' else -1

    # Obtener documentos de la colección
    documents = []
    total_docs = 0

    if collection.name in mongo.db.list_collection_names():
        # Obtener el total de documentos
        total_docs = mongo.db[collection.name].count_documents({})

        # Obtener los documentos paginados y ordenados
        cursor = mongo.db[collection.name].find().sort(sort_by, sort_direction).skip(skip).limit(per_page)
        documents = list(cursor)

    # Calcular el número total de páginas
    total_pages = (total_docs + per_page - 1) // per_page if total_docs > 0 else 1

    # Obtener una lista de todas las columnas (campos)
    all_fields = [field.name for field in collection.fields]

    # Si hay documentos, añadir campos que puedan existir en los datos pero no en los metadatos
    if documents:
        for doc in documents:
            for field_name in doc.keys():
                if field_name != '_id' and field_name not in all_fields:
                    all_fields.append(field_name)

    # Insertar _id al principio de la lista
    if '_id' not in all_fields:
        all_fields.insert(0, '_id')

    return render_template(
        'admin/database/view_collection.html',
        collection=collection,
        documents=documents,
        all_fields=all_fields,
        total_docs=total_docs,
        current_page=page,
        total_pages=total_pages,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir
    )