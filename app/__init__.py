from flask import Flask, redirect, url_for
from flask_pymongo import PyMongo
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf
import bcrypt
import os
from bson.objectid import ObjectId

# Instancias globales
mongo = PyMongo()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app():
    """Función de fábrica para crear la aplicación Flask."""
    # Inicializar la aplicación Flask
    app = Flask(__name__)

    # Cargar configuración
    from .config import get_config
    app.config.from_object(get_config())

    # Configuración adicional para sesiones y CSRF
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_COOKIE_SECURE'] = False  # Cambiar a True en producción
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutos
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hora
    app.config['WTF_CSRF_SSL_STRICT'] = False  # Cambiar a True en producción

    # Inicializar extensiones
    mongo.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'

    # Configurar el cargador de usuarios para Flask-Login
    from .models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            print(f"Intentando cargar usuario con id: {user_id}")
            user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
            if user_data:
                print(f"Usuario encontrado: {user_data.get('email')}")
                return User(**user_data)
            else:
                print(f"Usuario no encontrado con id: {user_id}")
                return None
        except Exception as e:
            print(f"Error al cargar usuario: {str(e)}")
            return None

    # Registrar blueprints
    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    from .admin import admin_bp
    app.register_blueprint(admin_bp)

    from .director import director_bp
    app.register_blueprint(director_bp)

    from .colaborador import colaborador_bp
    app.register_blueprint(colaborador_bp)

    # Crear usuario admin por defecto si no existe
    with app.app_context():
        try:
            if mongo.db.users.count_documents({"email": app.config['DEFAULT_ADMIN_EMAIL']}) == 0:
                # Crear hash de contraseña
                hashed_password = bcrypt.hashpw(
                    app.config['DEFAULT_ADMIN_PASSWORD'].encode('utf-8'),
                    bcrypt.gensalt()
                )

                # Insertar usuario admin
                mongo.db.users.insert_one({
                    "email": app.config['DEFAULT_ADMIN_EMAIL'],
                    "password": hashed_password,
                    "role": "admin",
                    "active": True
                })
                print(f"Usuario admin creado: {app.config['DEFAULT_ADMIN_EMAIL']}")
        except Exception as e:
            print(f"Error al crear usuario admin: {str(e)}")
            print("¿Está MongoDB en ejecución y configurado correctamente?")


    # Registrar procesador de contexto para CSRF
    @app.context_processor
    def inject_csrf_token():
        return {'csrf_token': generate_csrf()}

    # Añade este procesador de contexto justo después del procesador inject_csrf_token
    @app.context_processor
    def utility_processor():
        def get_assigner_name(assigned_by_id):
            if assigned_by_id:
                try:
                    from bson.objectid import ObjectId
                    assigner = mongo.db.users.find_one({"_id": ObjectId(assigned_by_id)})
                    return assigner.get('nombre', assigner.get('email', 'Desconocido')) if assigner else 'Desconocido'
                except Exception as e:
                    print(f"Error al obtener nombre de asignador: {str(e)}")
                    return 'Desconocido'
            return 'No asignado'

        return dict(get_assigner_name=get_assigner_name)



    # Ruta principal
    @app.route('/')
    def index():
        # Si el usuario ya está autenticado, redirigir al dashboard según su rol
        from flask_login import current_user
        if current_user.is_authenticated:
            if current_user.is_admin():
                return redirect(url_for('admin.dashboard'))
            elif current_user.is_director():
                return redirect(url_for('director.dashboard'))
            else:
                return redirect(url_for('colaborador.dashboard'))
        # Si no está autenticado, redirigir a la página de login
        return redirect(url_for('auth.login'))

    return app




