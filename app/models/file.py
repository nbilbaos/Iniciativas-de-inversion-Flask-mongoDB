# app/models/file.py
from datetime import datetime
from bson.objectid import ObjectId


class File:
    """Modelo para representar archivos subidos en el sistema."""

    def __init__(self, filename, original_filename, file_path, file_type, file_size,
                 initiative_id, uploaded_by, is_default=False, description='',
                 _id=None, uploaded_at=None, last_modified=None):
        """
        Inicializa un nuevo registro de archivo.

        Args:
            filename (str): Nombre del archivo en el sistema (único)
            original_filename (str): Nombre original del archivo
            file_path (str): Ruta al archivo en el sistema
            file_type (str): Tipo MIME del archivo
            file_size (int): Tamaño del archivo en bytes
            initiative_id (str): ID de la iniciativa a la que pertenece
            uploaded_by (str): ID del usuario que subió el archivo
            is_default (bool, optional): Si es un archivo predeterminado del sistema
            description (str, optional): Descripción opcional del archivo
            _id (ObjectId, optional): ID del archivo
            uploaded_at (datetime, optional): Fecha de subida
            last_modified (datetime, optional): Fecha de última modificación
        """
        self._id = _id or ObjectId()
        self.filename = filename
        self.original_filename = original_filename
        self.file_path = file_path
        self.file_type = file_type
        self.file_size = file_size
        self.initiative_id = initiative_id
        self.uploaded_by = uploaded_by
        self.is_default = is_default
        self.description = description
        self.uploaded_at = uploaded_at or datetime.utcnow()
        self.last_modified = last_modified or datetime.utcnow()
        self.active = True

    def to_dict(self):
        """Convierte el archivo a un diccionario para almacenamiento."""
        return {
            '_id': self._id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'initiative_id': self.initiative_id,
            'uploaded_by': self.uploaded_by,
            'is_default': self.is_default,
            'description': self.description,
            'uploaded_at': self.uploaded_at,
            'last_modified': self.last_modified,
            'active': self.active
        }

    @classmethod
    def from_dict(cls, data):
        """Crea una instancia de File desde un diccionario."""
        return cls(
            _id=data.get('_id'),
            filename=data.get('filename'),
            original_filename=data.get('original_filename'),
            file_path=data.get('file_path'),
            file_type=data.get('file_type'),
            file_size=data.get('file_size'),
            initiative_id=data.get('initiative_id'),
            uploaded_by=data.get('uploaded_by'),
            is_default=data.get('is_default', False),
            description=data.get('description', ''),
            uploaded_at=data.get('uploaded_at'),
            last_modified=data.get('last_modified')
        )


class FileHistory:
    """Modelo para registrar cambios en los archivos."""

    ACTIONS = {
        'upload': 'Archivo subido',
        'delete': 'Archivo eliminado',
        'update': 'Archivo actualizado',
        'restore': 'Archivo restaurado',
        'enable_files': 'Habilitada gestión de archivos para la iniciativa',
        'disable_files': 'Deshabilitada gestión de archivos para la iniciativa'
    }

    def __init__(self, initiative_id, file_id, user_id, action, details='',
                 _id=None, timestamp=None):
        """
        Inicializa un nuevo registro de historial de archivo.

        Args:
            initiative_id (str): ID de la iniciativa
            file_id (str, optional): ID del archivo (puede ser None para acciones globales)
            user_id (str): ID del usuario que realizó la acción
            action (str): Tipo de acción (de ACTIONS)
            details (str, optional): Detalles adicionales de la acción
            _id (ObjectId, optional): ID del registro
            timestamp (datetime, optional): Fecha y hora de la acción
        """
        self._id = _id or ObjectId()
        self.initiative_id = initiative_id
        self.file_id = file_id
        self.user_id = user_id
        self.action = action
        self.details = details
        self.timestamp = timestamp or datetime.utcnow()

    def to_dict(self):
        """Convierte el registro de historial a un diccionario para almacenamiento."""
        return {
            '_id': self._id,
            'initiative_id': self.initiative_id,
            'file_id': self.file_id,
            'user_id': self.user_id,
            'action': self.action,
            'details': self.details,
            'timestamp': self.timestamp
        }

    @classmethod
    def from_dict(cls, data):
        """Crea una instancia de FileHistory desde un diccionario."""
        return cls(
            _id=data.get('_id'),
            initiative_id=data.get('initiative_id'),
            file_id=data.get('file_id'),
            user_id=data.get('user_id'),
            action=data.get('action'),
            details=data.get('details', ''),
            timestamp=data.get('timestamp')
        )