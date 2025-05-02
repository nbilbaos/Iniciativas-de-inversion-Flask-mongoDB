from flask import Flask, redirect, url_for
from flask_pymongo import PyMongo
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf
import bcrypt
import os
from bson.objectid import ObjectId
from .health import health_bp


# Instancias globales
mongo = PyMongo()
login_manager = LoginManager()
csrf = CSRFProtect()


def setup_required_collections(app, mongo):
    """
    Configura todas las colecciones necesarias para la aplicación.
    Verifica si existen y las crea si son necesarias.
    """
    with app.app_context():
        collections = mongo.db.list_collection_names()

        # Configuración de la colección 'tasks'
        if 'tasks' not in collections:
            mongo.db.create_collection('tasks')
            print('Colección "tasks" creada exitosamente')

            # Índices para la colección 'tasks'
            mongo.db.tasks.create_index([("initiative_id", 1)])
            mongo.db.tasks.create_index([("created_by", 1)])
            mongo.db.tasks.create_index([("assigned_to", 1)])
            mongo.db.tasks.create_index([("is_completed", 1)])
            mongo.db.tasks.create_index([("created_at", -1)])
            print('Índices para la colección "tasks" creados exitosamente')

        # Configuración de la colección 'assignment_history' si no existe
        if 'assignment_history' not in collections:
            mongo.db.create_collection('assignment_history')
            print('Colección "assignment_history" creada exitosamente')
            mongo.db.assignment_history.create_index([("initiative_id", 1)])
            mongo.db.assignment_history.create_index([("timestamp", -1)])

        # Configuración de la colección 'estado_iniciativa_historial' si no existe
        if 'estado_iniciativa_historial' not in collections:
            mongo.db.create_collection('estado_iniciativa_historial')
            print('Colección "estado_iniciativa_historial" creada exitosamente')
            mongo.db.estado_iniciativa_historial.create_index([("initiative_id", 1)])
            mongo.db.estado_iniciativa_historial.create_index([("timestamp", -1)])

        # Configuración de la colección 'modification_history' si no existe
        if 'modification_history' not in collections:
            mongo.db.create_collection('modification_history')
            print('Colección "modification_history" creada exitosamente')
            mongo.db.modification_history.create_index([("initiative_id", 1)])
            mongo.db.modification_history.create_index([("timestamp", -1)])

        print("Todas las colecciones necesarias han sido verificadas y configuradas.")


def create_app():
    """Función de fábrica para crear la aplicación Flask."""
    # Inicializar la aplicación Flask
    app = Flask(__name__)
    app.config['INITIATIVES_COLLECTION'] = 'db_metadata.iniciativas_2025'
    # Cargar configuración
    from .config import get_config
    app.config.from_object(get_config())
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['TEMP_UPLOADS'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'default_files'), exist_ok=True)
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

    # Crear índices para mejorar la búsqueda
    with app.app_context():
        collection_name = app.config['INITIATIVES_COLLECTION']
        parts = collection_name.split('.')
        if len(parts) > 1:
            mongo.db[parts[0]][parts[1]].create_index([('nombre_iniciativa', 'text'), ('cod', 'text')])
        else:
            mongo.db[collection_name].create_index([('nombre_iniciativa', 'text'), ('cod', 'text')])

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

    # En app/__init__.py después de registrar el blueprint
    from .director import director_bp, init_app as init_director
    app.register_blueprint(director_bp)
    init_director(app)

    from .colaborador import colaborador_bp
    app.register_blueprint(colaborador_bp)

    app.register_blueprint(health_bp)

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

    # En app/__init__.py o en un archivo de setup
    with app.app_context():
        # Índices para iniciativas
        mongo.db.db_metadata.iniciativas.create_index([("nombre", 1)])
        mongo.db.db_metadata.iniciativas.create_index([("codigo", 1)])

        # Índices para historiales
        mongo.db.assignment_history.create_index([("initiative_id", 1)])
        mongo.db.assignment_history.create_index([("timestamp", -1)])
        mongo.db.modification_history.create_index([("initiative_id", 1)])
        mongo.db.modification_history.create_index([("timestamp", -1)])

    # Verificar si existe la colección tasks y crearla si no existe
    with app.app_context():
        # Obtener una lista de todas las colecciones de la base de datos
        collections = mongo.db.list_collection_names()

        # Verificar si la colección tasks existe
        if 'tasks' not in collections:
            # Crear la colección tasks explícitamente
            mongo.db.create_collection('tasks')
            print('Colección "tasks" creada exitosamente')

            # Crear índices para mejorar el rendimiento de consultas
            mongo.db.tasks.create_index([("initiative_id", 1)])
            mongo.db.tasks.create_index([("created_by", 1)])
            mongo.db.tasks.create_index([("assigned_to", 1)])
            mongo.db.tasks.create_index([("is_completed", 1)])
            mongo.db.tasks.create_index([("created_at", -1)])

            print('Índices para la colección "tasks" creados exitosamente')
        else:
            print('La colección "tasks" ya existe')

    @app.template_filter('format_date')
    def format_date_filter(date_value, format_string='%d/%m/%Y'):
        """
        Filtro Jinja para formatear fechas de manera segura.
        Maneja tanto objetos datetime como strings, y casos nulos.

        Uso en plantillas: {{ iniciativa.fecha_creacion|format_date }}
        O con formato personalizado: {{ iniciativa.fecha_creacion|format_date('%d/%m/%Y %H:%M') }}
        """
        if not date_value:
            return "-"

        # Si ya es string, devolverlo como está
        if isinstance(date_value, str):
            return date_value

        # Si es un objeto datetime, formatearlo
        try:
            return date_value.strftime(format_string)
        except Exception:
            # Si hay un error, devolver el valor como string o un valor por defecto
            return str(date_value) if date_value else "-"



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

    # Añadir en app/__init__.py o en un archivo utils.py

    import base64

    def get_image_as_base64(file_path):
        """Convierte una imagen a base64 para incluirla en el PDF."""
        try:
            with open(file_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            print(f"Error al convertir imagen a base64: {str(e)}")
            return ""

    # Registrar la función en Jinja2
    @app.context_processor
    def utility_processor():
        return dict(get_image_as_base64=get_image_as_base64)


    # Configurar todas las colecciones requeridas
    setup_required_collections(app, mongo)

    return app



