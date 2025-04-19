from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
import bcrypt
from datetime import datetime
import re
import os
from bson.objectid import ObjectId
from flask import render_template, redirect, url_for, flash, request, session, abort, make_response
from . import auth_bp
from .forms import LoginForm, RegisterForm, ChangePasswordForm
from .utils import validate_password_strength
from .. import mongo
from ..models.user import User

# Variables para limitar intentos de inicio de sesión
LOGIN_ATTEMPTS = {}
MAX_ATTEMPTS = 5
LOCKOUT_TIME = 300  # 5 minutos en segundos


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Vista para el inicio de sesión."""
    # Si el usuario ya está autenticado, redirigir a la página principal
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    # Verificar si hay parámetro de cierre de sesión (ignoramos bloqueos en este caso)
    logout_param = request.args.get('logout')

    form = None
    if request.method == 'POST':
        # Obtener datos del formulario
        email = request.form.get('email')
        password = request.form.get('password')
        remember_me = 'remember_me' in request.form

        # Validar formulario
        if not email or not password:
            flash('Por favor, complete todos los campos', 'danger')
            return render_template('auth/login.html', form=form)

        # Buscar el usuario por correo electrónico
        user_data = mongo.db.users.find_one({"email": email})

        # Verificar si existe el usuario y la contraseña es correcta
        if user_data and bcrypt.checkpw(password.encode('utf-8'), user_data['password']):
            # Crear instancia de usuario y iniciar sesión
            user = User(**user_data)
            login_user(user, remember=remember_me)

            # Actualizar última fecha de inicio de sesión
            mongo.db.users.update_one(
                {"_id": user_data["_id"]},
                {"$set": {"last_login": datetime.utcnow()}}
            )

            # Limpiar los intentos fallidos (éxito)
            if 'HTTP_X_REAL_IP' in request.environ:
                ip_address = request.environ['HTTP_X_REAL_IP']
            else:
                ip_address = request.remote_addr

            if ip_address in LOGIN_ATTEMPTS:
                LOGIN_ATTEMPTS.pop(ip_address)

            # Redirigir a la página solicitada o a la página principal según el rol
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                if user.is_admin():
                    next_page = url_for('admin.dashboard')
                elif user.is_director():
                    next_page = url_for('director.dashboard')
                else:
                    next_page = url_for('colaborador.dashboard')

            return redirect(next_page)
        else:
            # Gestionar intentos fallidos de inicio de sesión
            if 'HTTP_X_REAL_IP' in request.environ:
                ip_address = request.environ['HTTP_X_REAL_IP']
            else:
                ip_address = request.remote_addr

            if ip_address not in LOGIN_ATTEMPTS:
                LOGIN_ATTEMPTS[ip_address] = {'attempts': 1, 'last_attempt': datetime.utcnow()}
            else:
                LOGIN_ATTEMPTS[ip_address]['attempts'] += 1
                LOGIN_ATTEMPTS[ip_address]['last_attempt'] = datetime.utcnow()

            flash('Correo electrónico o contraseña incorrectos', 'danger')

            # Incluir contador para JavaScript
            response = make_response(render_template('auth/login.html', form=form))
            response.headers['X-Login-Attempts'] = str(LOGIN_ATTEMPTS[ip_address]['attempts'])
            return response

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Vista para cerrar sesión."""
    # Obtener el usuario actual antes de cerrar la sesión para el mensaje
    email = current_user.email if hasattr(current_user, 'email') else ''

    # Cerrar la sesión del usuario
    logout_user()

    # Limpiar la sesión completamente
    session.clear()

    # Mensaje de confirmación
    flash(f'Sesión cerrada correctamente para {email}', 'success')

    # Forzar actualización de cookies
    response = redirect(url_for('auth.login', logout=1))
    response.delete_cookie('session')  # Eliminar cookie de sesión
    response.delete_cookie('remember_token')  # Eliminar cookie de remember_token

    return response


@auth_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    """Vista para registrar un nuevo usuario (solo accesible por admin)."""
    # Solo los administradores pueden registrar nuevos usuarios
    if not current_user.is_admin():
        abort(403)  # Forbidden

    form = RegisterForm()
    if form.validate_on_submit():
        # Verificar si el correo ya está registrado
        if mongo.db.users.find_one({"email": form.email.data}):
            flash('El correo electrónico ya está registrado', 'danger')
        else:
            # Crear hash de contraseña
            hashed_password = bcrypt.hashpw(
                form.password.data.encode('utf-8'),
                bcrypt.gensalt()
            )

            # Procesar títulos si se proporcionan
            titulos = []
            if form.titulos.data:
                titulos = [titulo.strip() for titulo in form.titulos.data.split(",") if titulo.strip()]

            # Crear nuevo usuario
            new_user = {
                "email": form.email.data,
                "password": hashed_password,
                "role": form.role.data,
                "active": True,
                "created_at": datetime.utcnow(),
                "last_login": None,
                "nombre": form.nombre.data,
                "rut": form.rut.data,
                "direccion": form.direccion.data,
                "telefono": form.telefono.data,
                "titulos": titulos,
                "iniciativas": []
            }

            # Insertar usuario en la base de datos
            mongo.db.users.insert_one(new_user)
            flash(f'Usuario {form.email.data} registrado correctamente', 'success')
            return redirect(url_for('admin.user_list'))

    return render_template('auth/register.html', form=form)


# Utilidades para el manejo de contraseñas
@auth_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Vista para cambiar la contraseña del usuario actual."""
    form = ChangePasswordForm()

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Validar que todos los campos están completos
        if not current_password or not new_password or not confirm_password:
            flash('Por favor, complete todos los campos', 'danger')
            return render_template('auth/change_password.html', form=form)

        # Validar que la nueva contraseña y la confirmación coinciden
        if new_password != confirm_password:
            flash('Las contraseñas no coinciden', 'danger')
            return render_template('auth/change_password.html', form=form)

        # Validar requisitos de seguridad de la contraseña
        validation_result = validate_password_strength(new_password)
        if validation_result[0] == False:
            for error in validation_result[1]:
                flash(error, 'danger')
            return render_template('auth/change_password.html', form=form)

        # Obtener el usuario actual de la base de datos
        user_data = mongo.db.users.find_one({"_id": ObjectId(current_user.get_id())})

        if not user_data:
            flash('Error al obtener los datos del usuario', 'danger')
            return render_template('auth/change_password.html', form=form)

        # Verificar que la contraseña actual sea correcta
        if not bcrypt.checkpw(current_password.encode('utf-8'), user_data['password']):
            flash('La contraseña actual es incorrecta', 'danger')
            return render_template('auth/change_password.html', form=form)

        # Hashear la nueva contraseña
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

        # Actualizar la contraseña en la base de datos
        result = mongo.db.users.update_one(
            {"_id": ObjectId(current_user.get_id())},
            {"$set": {"password": hashed_password}}
        )

        if result.modified_count > 0:
            flash('Contraseña actualizada correctamente', 'success')
            return redirect(url_for('index'))
        else:
            flash('Error al actualizar la contraseña', 'danger')

    return render_template('auth/change_password.html', form=form)