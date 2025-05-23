from flask import Flask, redirect, url_for, jsonify, request, render_template, flash
from flask_pymongo import PyMongo
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf
import bcrypt
import os
import sys
import importlib
from bson.objectid import ObjectId
from .health import health_bp
from app.utils.template_filters import register_template_filters

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

    # Definir dominios permitidos
    app.config['ALLOWED_DOMAINS'] = [
        'iniciativas.cl',
        'www.iniciativas.cl',
        'flask-mongodb-app.onrender.com',  # Dominio de Render (ajustar según el nombre elegido)
        '127.0.0.1:5000',
        'localhost:5000'
    ]

    # Handler para manejar múltiples dominios
    @app.before_request
    def handle_domains_and_health():
        # Siempre permitir el health check
        if request.path == '/health':
            return 'OK', 200

        # Si está en producción, se podría implementar redirección al dominio principal
        # (comentado por ahora para mantener comportamiento actual)
        # if app.env == 'production' and request.host not in ['iniciativas.cl', 'www.iniciativas.cl']:
        #     if request.host in app.config['ALLOWED_DOMAINS']:
        #         url = request.url.replace(request.host, 'iniciativas.cl')
        #         return redirect(url, code=301)

    # Create upload directories explicitly with proper error handling
    try:
        upload_dir = app.config.get('UPLOAD_FOLDER')
        temp_dir = app.config.get('TEMP_UPLOADS')
        default_files_dir = os.path.join(upload_dir, 'default_files') if upload_dir else None

        # Handle paths more robustly
        if upload_dir and not os.path.isabs(upload_dir):
            app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), upload_dir)
            upload_dir = app.config['UPLOAD_FOLDER']

        if temp_dir and not os.path.isabs(temp_dir):
            app.config['TEMP_UPLOADS'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), temp_dir)
            temp_dir = app.config['TEMP_UPLOADS']

        # Create directories if they don't exist
        for directory in [upload_dir, temp_dir, default_files_dir]:
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                print(f"Created directory: {directory}")

    except Exception as e:
        print(f"Warning: Could not create directories: {str(e)}")
        print("Will rely on .platform/hooks for directory creation")
        # Continue anyway, the .ebextensions will handle this

    # Configuración mejorada para sesiones y CSRF
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = True  # Cambiar a True para usar PERMANENT_SESSION_LIFETIME
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_COOKIE_SECURE'] = False  # Bien para desarrollo local
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    # Accept requests from any host
    app.config['SERVER_NAME'] = None
    app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 horas para producción
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = 86400  # 24 horas para tokens CSRF
    app.config['WTF_CSRF_SSL_STRICT'] = False  # Para entorno sin HTTPS


    # Inicializar extensiones
    mongo.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    register_template_filters(app)
    # Crear índices para mejorar la búsqueda
    with app.app_context():
        try:
            collection_name = app.config['INITIATIVES_COLLECTION']
            parts = collection_name.split('.')
            if len(parts) > 1:
                mongo.db[parts[0]][parts[1]].create_index([('nombre_iniciativa', 'text'), ('cod', 'text')])
            else:
                mongo.db[collection_name].create_index([('nombre_iniciativa', 'text'), ('cod', 'text')])
        except Exception as e:
            print(f"Warning: Could not create text indexes: {str(e)}")

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

    # Add a diagnostic endpoint
    @app.route('/api/status')
    def api_status():
        """Return information about the application status."""
        import sys
        try:
            import pkg_resources
            installed_packages = sorted([f"{pkg.key}=={pkg.version}"
                                         for pkg in pkg_resources.working_set])
        except Exception as e:
            installed_packages = ["Error getting packages: " + str(e)]

        # Check for reportlab
        reportlab_installed = False
        try:
            import reportlab
            reportlab_installed = True
            reportlab_version = reportlab.__version__
        except ImportError:
            reportlab_version = "Not installed"

        status = {
            'status': 'online',
            'python_version': sys.version,
            'reportlab_available': reportlab_installed,
            'reportlab_version': reportlab_version,
            'installed_packages': installed_packages,
            'host': request.host,
            'app_config': {
                'allowed_domains': app.config.get('ALLOWED_DOMAINS', []),
                'env': app.env
            }
        }

        return jsonify(status)

    # Ruta de health check adicional en la raíz de la aplicación
    @app.route('/health', methods=['GET'])
    def health_check():
        """Endpoint para health checks de Elastic Beanstalk."""
        return 'OK', 200

    # Register health blueprint first - most important for EB health checks
    app.register_blueprint(health_bp)

    # Registrar blueprints
    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    from .admin import admin_bp
    app.register_blueprint(admin_bp)

    # Registrar colaborador blueprint primero para asegurar que la ruta colaborador.dashboard existe
    try:
        from .colaborador import colaborador_bp
        app.register_blueprint(colaborador_bp)
        print("Collaborator module loaded successfully")
    except ImportError as e:
        print(f"Warning: Could not import colaborador module: {str(e)}")
        # Create a dummy blueprint if colaborador module fails to load
        from flask import Blueprint
        colaborador_bp = Blueprint('colaborador', __name__, url_prefix='/colaborador')

        @colaborador_bp.route('/dashboard')
        def dashboard():
            return redirect(url_for('index'))

        app.register_blueprint(colaborador_bp)
        print("Created dummy colaborador blueprint for redirection")

    # Luego intentar cargar el blueprint de director
    try:
        print("Attempting to import director module...")
        from .director import director_bp, init_app as init_director
        app.register_blueprint(director_bp)
        init_director(app)
        print("Director module loaded successfully")
    except ImportError as e:
        print(f"Warning: Could not import director module: {str(e)}")
    except Exception as general_e:
        print(f"Unexpected error during director blueprint registration: {str(general_e)}")

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
        try:
            # Índices para iniciativas
            mongo.db.db_metadata.iniciativas.create_index([("nombre", 1)])
            mongo.db.db_metadata.iniciativas.create_index([("codigo", 1)])

            # Índices para historiales
            mongo.db.assignment_history.create_index([("initiative_id", 1)])
            mongo.db.assignment_history.create_index([("timestamp", -1)])
            mongo.db.modification_history.create_index([("initiative_id", 1)])
            mongo.db.modification_history.create_index([("timestamp", -1)])
        except Exception as e:
            print(f"Warning: Could not create some indexes: {str(e)}")

    # Verificar si existe la colección tasks y crearla si no existe
    with app.app_context():
        try:
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
        except Exception as e:
            print(f"Warning: Could not set up tasks collection: {str(e)}")

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

    # Busca la función context_processor y modifícala:
    @app.context_processor
    def inject_csrf_token():
        from flask_wtf.csrf import generate_csrf
        # Importar dentro de la función para evitar errores de contexto
        try:
            from app.utils.timezone_utils import now_chile
            return {
                'csrf_token': generate_csrf(),  # ← Nota los paréntesis ()
                'now_chile': now_chile()
            }
        except Exception as e:
            # Fallback si hay problema
            from datetime import datetime
            return {
                'csrf_token': generate_csrf(),  # ← Nota los paréntesis ()
                'now_chile': datetime.now()
            }


    # Añade este procesador de contexto justo después del procesador inject_csrf_token
    @app.context_processor
    def utility_processor():
        def get_assigner_name(assigned_by_id):
            if assigned_by_id:
                try:
                    assigner = mongo.db.users.find_one({"_id": ObjectId(assigned_by_id)})
                    return assigner.get('nombre', assigner.get('email', 'Desconocido')) if assigner else 'Desconocido'
                except Exception as e:
                    print(f"Error al obtener nombre de asignador: {str(e)}")
                    return 'Desconocido'
            return 'No asignado'

        def get_image_as_base64(file_path):
            """Convierte una imagen a base64 para incluirla en el PDF."""
            try:
                import base64
                with open(file_path, "rb") as image_file:
                    return base64.b64encode(image_file.read()).decode('utf-8')
            except Exception as e:
                print(f"Error al convertir imagen a base64: {str(e)}")
                return ""

        return dict(get_assigner_name=get_assigner_name, get_image_as_base64=get_image_as_base64)

    # Ruta principal
    # Reemplaza la función index en app/__init__.py con esta versión mejorada

    @app.route('/')
    def index():
        """Ruta principal con manejo de errores mejorado."""
        # Si el usuario ya está autenticado, redirigir al dashboard según su rol
        from flask_login import current_user
        if current_user.is_authenticated:
            try:
                if current_user.is_admin():
                    return redirect(url_for('admin.dashboard'))
                elif current_user.is_director():
                    # Verificar si la ruta director.dashboard existe
                    try:
                        return redirect(url_for('director.dashboard'))
                    except Exception as route_error:
                        app.logger.error(f"Error al redirigir a director.dashboard: {str(route_error)}")
                        # Verificar si estamos en mantenimiento
                        maintenance_mode = os.environ.get('MAINTENANCE_MODE', 'false').lower() == 'true'
                        if maintenance_mode:
                            flash('El sistema está en mantenimiento. Algunas funciones podrían no estar disponibles.',
                                  'warning')
                        else:
                            flash('El módulo de director está temporalmente no disponible. Contacte al administrador.',
                                  'warning')
                        # Mostrar una página genérica
                        return render_template('fallback/director_dashboard.html')
                else:
                    # Si es colaborador, intentar redirigir al dashboard de colaborador
                    try:
                        return redirect(url_for('colaborador.dashboard'))
                    except Exception as collab_error:
                        app.logger.error(f"Error al redirigir a colaborador.dashboard: {str(collab_error)}")
                        flash('El módulo de colaborador está temporalmente no disponible. Contacte al administrador.',
                              'warning')
                        return render_template('fallback/colaborador_dashboard.html', user=current_user)
            except Exception as general_error:
                app.logger.error(f"Error general en el enrutamiento: {str(general_error)}")
                flash('Ha ocurrido un error al procesar su solicitud. Por favor, inténtelo nuevamente.', 'danger')
                return render_template('errors/generic_error.html')

        # Si no está autenticado, redirigir a la página de login
        return redirect(url_for('auth.login'))
    try:
        setup_required_collections(app, mongo)
    except Exception as e:
        print(f"Warning: Could not set up all collections: {str(e)}")

    return app