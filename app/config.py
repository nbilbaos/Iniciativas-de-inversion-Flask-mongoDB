import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


class Config:
    """Configuración base de la aplicación."""
    SECRET_KEY = os.getenv('SECRET_KEY')
    MONGO_URI = os.getenv('MONGO_URI')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')


    # In config.py
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'uploads')


    ALLOWED_EXTENSIONS = {
        # Archivos CAD y 3D
        'dwg', 'dxf', 'dwt', 'dwf', 'dws',  # AutoCAD
        'blend', '3ds', 'obj', 'fbx', 'stl',  # Blender y formatos 3D
        # Documentos ofimáticos
        'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'odp',
        # PDF y otros documentos
        'pdf', 'txt', 'csv', 'json', 'xml',
        # Imágenes
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tif', 'tiff', 'svg',
        # Archivos comprimidos
        'zip', 'rar', '7z', 'tar', 'gz'
    }

    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB in bytes


    # Añadir esto a la clase Config
    # Cambiado a TEMP_UPLOADS para no sobrescribir la configuración existente
    TEMP_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_uploads')

    # Configuraciones para seguridad
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 1800  # 30 minutos en segundos

    # Configuración CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_CHECK_DEFAULT = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hora en segundos

    # Usuario admin por defecto
    DEFAULT_ADMIN_EMAIL = "admin@example.com"
    DEFAULT_ADMIN_PASSWORD = "Admin123!"  # En producción, usar algo más seguro

    # Nombre de la colección de iniciativas
    INITIATIVES_COLLECTION = 'db_metadata.iniciativas_2025'


class DevelopmentConfig(Config):
    """Configuración para desarrollo."""
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_SSL_STRICT = False  # No requerir HTTPS en desarrollo


class ProductionConfig(Config):
    """Configuración para producción."""
    DEBUG = False
    # Configuración HTTPS
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PREFERRED_URL_SCHEME = 'https'

    # Override MongoDB URI with environment variable if provided
    MONGO_URI = os.environ.get('MONGO_URI', Config.MONGO_URI)

    # Set a longer request timeout for production
    MONGO_CONNECT_TIMEOUT_MS = 30000
    MONGO_SERVER_SELECTION_TIMEOUT_MS = 30000

    ALLOWED_HOSTS = ['iniciativas.cl',
                     'www.iniciativas.cl',
                     'flask-mongodb-env3.eba-2xc3jqqa.us-east-1.elasticbeanstalk.com',
                     '172.31.84.40']  # IPs internas de EB


# Configuración según el entorno
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig
}


# Obtener la configuración según el entorno
def get_config():
    env = os.getenv('FLASK_ENV', 'development')
    return config_by_name[env]