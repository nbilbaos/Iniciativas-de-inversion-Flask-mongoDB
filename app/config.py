import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


class Config:
    """Configuración base de la aplicación."""
    SECRET_KEY = os.getenv('SECRET_KEY')
    MONGO_URI = os.getenv('MONGO_URI')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')

    # Configuración para archivos
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    TEMP_UPLOADS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_uploads')
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
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # Límite de 50MB por archivo

    # Añadir esto a la clase Config
    # Cambiado a TEMP_UPLOADS para no sobrescribir la configuración existente
    TEMP_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_uploads')

    # Configuraciones para seguridad
    SESSION_COOKIE_SECURE = True
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
    SESSION_COOKIE_SECURE = True


# Configuración según el entorno
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig
}


# Obtener la configuración según el entorno
def get_config():
    env = os.getenv('FLASK_ENV', 'development')
    return config_by_name[env]