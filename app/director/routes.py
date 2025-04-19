from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from bson.objectid import ObjectId
import bcrypt
from datetime import datetime
from flask_wtf.csrf import generate_csrf

from . import director_bp
from ..auth.utils import director_required
from .. import mongo, csrf
from ..models.user import User

@director_bp.route('/dashboard')
@login_required
@director_required
def dashboard():
    """Dashboard para el rol de director."""
    # Obtener estadísticas relevantes para el director
    colaboradores = mongo.db.users.count_documents({"role": "colaborador"})

    stats = {
        'colaboradores': colaboradores,
        # Aquí puedes agregar más estadísticas relevantes para el director
    }

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
    """Lista de colaboradores para el director."""
    colaboradores = list(mongo.db.users.find({"role": "colaborador"}))
    return render_template('director/colaboradores.html', colaboradores=colaboradores)


@director_bp.route('/colaboradores/<colaborador_id>')
@login_required
@director_required
def colaborador_detail(colaborador_id):
    """Ver detalles de un colaborador."""
    colaborador_data = mongo.db.users.find_one({"_id": ObjectId(colaborador_id), "role": "colaborador"})

    if not colaborador_data:
        flash('Colaborador no encontrado', 'danger')
        return redirect(url_for('director.colaborador_list'))

    # Convertir el diccionario a un objeto User
    from ..models.user import User
    colaborador = User(**colaborador_data)

    return render_template('director/colaborador_detail.html', colaborador=colaborador)

@director_bp.route('/colaboradores/nuevo', methods=['GET', 'POST'])
@login_required
@director_required
def crear_colaborador():
    """Vista para que el director cree un nuevo colaborador."""
    if request.method == 'POST':
        # Obtener datos del formulario
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        nombre = request.form.get('nombre')
        rut = request.form.get('rut')
        direccion = request.form.get('direccion')
        telefono = request.form.get('telefono')
        titulos_raw = request.form.get('titulos')

        # Validación básica
        if not email or not password or not confirm_password or not nombre or not rut:
            flash('Por favor, complete todos los campos obligatorios', 'danger')
            return render_template('director/crear_colaborador.html')

        # Verificar si el correo ya está registrado
        if mongo.db.users.find_one({"email": email}):
            flash('El correo electrónico ya está registrado', 'danger')
            return render_template('director/crear_colaborador.html')

        # Verificar que las contraseñas coincidan
        if password != confirm_password:
            flash('Las contraseñas no coinciden', 'danger')
            return render_template('director/crear_colaborador.html')

        # Validar la contraseña (seguridad)
        from ..auth.utils import validate_password_strength
        password_valid, errors = validate_password_strength(password)
        if not password_valid:
            for error in errors:
                flash(error, 'danger')
            return render_template('director/crear_colaborador.html')

        # Procesar títulos
        titulos = []
        if titulos_raw:
            titulos = [titulo.strip() for titulo in titulos_raw.split(',') if titulo.strip()]

        # Crear hash de contraseña
        import bcrypt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Crear nuevo usuario con rol colaborador
        new_user = {
            "email": email,
            "password": hashed_password,
            "role": "colaborador",  # Director sólo puede crear colaboradores
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

        # Insertar usuario en la base de datos
        mongo.db.users.insert_one(new_user)
        flash(f'Colaborador {nombre} ({email}) creado correctamente', 'success')
        return redirect(url_for('director.colaborador_list'))

    return render_template('director/crear_colaborador.html')


@director_bp.route('/colaboradores/<colaborador_id>/toggle_active', methods=['POST'])
@login_required
@director_required
def toggle_colaborador_active(colaborador_id):
    """Activar o desactivar un colaborador."""
    colaborador = mongo.db.users.find_one({"_id": ObjectId(colaborador_id), "role": "colaborador"})

    if not colaborador:
        flash('Colaborador no encontrado', 'danger')
        return redirect(url_for('director.colaborador_list'))

    # Cambiar el estado activo
    new_status = not colaborador.get('active', True)
    mongo.db.users.update_one(
        {"_id": ObjectId(colaborador_id)},
        {"$set": {"active": new_status}}
    )

    status_str = 'activado' if new_status else 'desactivado'
    flash(f'Colaborador {colaborador["email"]} {status_str} correctamente', 'success')
    return redirect(url_for('director.colaborador_detail', colaborador_id=colaborador_id))


@director_bp.route('/colaboradores/<colaborador_id>/reset_password', methods=['POST'])
@login_required
@director_required
def reset_colaborador_password(colaborador_id):
    """Restablecer la contraseña de un colaborador."""
    colaborador = mongo.db.users.find_one({"_id": ObjectId(colaborador_id), "role": "colaborador"})

    if not colaborador:
        flash('Colaborador no encontrado', 'danger')
        return redirect(url_for('director.colaborador_list'))

    # Crear una contraseña temporal
    import bcrypt
    temp_password = "Temporal123!"
    hashed_password = bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt())

    # Actualizar la contraseña del colaborador
    mongo.db.users.update_one(
        {"_id": ObjectId(colaborador_id)},
        {"$set": {"password": hashed_password}}
    )

    flash(
        f'Contraseña restablecida para {colaborador.get("nombre") or colaborador["email"]}. Nueva contraseña: {temp_password}',
        'success')
    return redirect(url_for('director.colaborador_detail', colaborador_id=colaborador_id))


@director_bp.route('/colaboradores/<colaborador_id>/edit', methods=['GET', 'POST'])
@login_required
@director_required
def edit_colaborador(colaborador_id):
    """Editar un usuario colaborador."""
    try:
        colaborador = mongo.db.users.find_one({"_id": ObjectId(colaborador_id)})
        if not colaborador:
            flash('Colaborador no encontrado', 'danger')
            return redirect(url_for('director.colaborador_list'))

        # Verificar que sea un colaborador
        if colaborador.get('role') != 'colaborador':
            flash('Solo puedes editar usuarios colaboradores', 'danger')
            return redirect(url_for('director.colaborador_list'))

        # Crear formulario
        from flask_wtf import FlaskForm
        from wtforms import StringField, SubmitField, TextAreaField
        from wtforms.validators import DataRequired, Email, Optional

        class ColaboradorEditForm(FlaskForm):
            email = StringField('Correo Electrónico', validators=[DataRequired(), Email()])
            nombre = StringField('Nombre Completo', validators=[DataRequired()])
            rut = StringField('RUT', validators=[DataRequired()])
            telefono = StringField('Teléfono de Contacto', validators=[Optional()])
            direccion = StringField('Dirección', validators=[Optional()])
            titulos = StringField('Títulos (separados por coma)', validators=[Optional()])
            submit = SubmitField('Guardar Cambios')

        form = ColaboradorEditForm()

        # Para el método GET, prellenar el formulario
        if request.method == 'GET':
            form.email.data = colaborador.get('email', '')
            form.nombre.data = colaborador.get('nombre', '')
            form.rut.data = colaborador.get('rut', '')
            form.telefono.data = colaborador.get('telefono', '')
            form.direccion.data = colaborador.get('direccion', '')
            # Si titulos es una lista, la convertimos a string separada por comas
            if isinstance(colaborador.get('titulos', ''), list):
                form.titulos.data = ', '.join(colaborador.get('titulos', []))
            else:
                form.titulos.data = colaborador.get('titulos', '')

        # Procesar el envío del formulario
        if form.validate_on_submit():
            # Procesar títulos como lista
            titulos = []
            if form.titulos.data:
                titulos = [titulo.strip() for titulo in form.titulos.data.split(',') if titulo.strip()]

            # Preparar datos para la actualización
            update_data = {
                'email': form.email.data,
                'nombre': form.nombre.data,
                'rut': form.rut.data,
                'telefono': form.telefono.data,
                'direccion': form.direccion.data,
                'titulos': titulos  # Guardamos como lista
            }

            # Actualizar en la base de datos
            result = mongo.db.users.update_one(
                {"_id": ObjectId(colaborador_id)},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                flash('Colaborador actualizado correctamente', 'success')
            else:
                flash('No se realizaron cambios', 'info')

            return redirect(url_for('director.colaborador_detail', colaborador_id=colaborador_id))

        return render_template('director/edit_colaborador.html', form=form, colaborador=colaborador)

    except Exception as e:
        flash(f'Error al editar el colaborador: {str(e)}', 'danger')
        return redirect(url_for('director.colaborador_list'))