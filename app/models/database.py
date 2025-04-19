from datetime import datetime
from bson.objectid import ObjectId


class CollectionField:
    """Representa un campo en una colección."""

    # Tipos de campos disponibles
    FIELD_TYPES = {
        'text': 'Texto',
        'number': 'Número',
        'integer': 'Entero',
        'decimal': 'Decimal',
        'date': 'Fecha',
        'datetime': 'Fecha y Hora',
        'boolean': 'Booleano (Sí/No)',
        'array': 'Lista',
        'object': 'Objeto',
        'reference': 'Referencia a otra colección',
        'file': 'Archivo',
        'email': 'Correo electrónico',
        'url': 'URL',
        'enum': 'Lista de opciones',
    }

    def __init__(self, name, field_type, required=False, description='', options=None):
        self.name = name  # Nombre del campo
        self.field_type = field_type  # Tipo de campo (de FIELD_TYPES)
        self.required = required  # ¿Es obligatorio?
        self.description = description  # Descripción del campo
        self.options = options or {}  # Opciones adicionales (por ejemplo, valores enum)

    def to_dict(self):
        """Convierte el campo a un diccionario para almacenamiento."""
        return {
            'name': self.name,
            'field_type': self.field_type,
            'required': self.required,
            'description': self.description,
            'options': self.options
        }

    @classmethod
    def from_dict(cls, data):
        """Crea una instancia de CollectionField desde un diccionario."""
        return cls(
            name=data.get('name'),
            field_type=data.get('field_type'),
            required=data.get('required', False),
            description=data.get('description', ''),
            options=data.get('options', {})
        )


class DatabaseCollection:
    """Representa una colección en la base de datos de iniciativas de inversión."""

    def __init__(self, name, description='', fields=None, created_at=None, updated_at=None, _id=None):
        self._id = _id or ObjectId()
        self.name = name  # Nombre de la colección
        self.description = description  # Descripción de la colección
        self.fields = fields or []  # Lista de campos (CollectionField)
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def add_field(self, field):
        """Añade un campo a la colección."""
        if isinstance(field, dict):
            field = CollectionField.from_dict(field)
        self.fields.append(field)
        self.updated_at = datetime.utcnow()

    def remove_field(self, field_name):
        """Elimina un campo de la colección por su nombre."""
        self.fields = [f for f in self.fields if f.name != field_name]
        self.updated_at = datetime.utcnow()

    def update_field(self, field_name, updated_field):
        """Actualiza un campo existente."""
        for i, field in enumerate(self.fields):
            if field.name == field_name:
                self.fields[i] = updated_field
                break
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        """Convierte la colección a un diccionario para almacenamiento."""
        return {
            '_id': self._id,
            'name': self.name,
            'description': self.description,
            'fields': [field.to_dict() for field in self.fields],
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

    @classmethod
    def from_dict(cls, data):
        """Crea una instancia de DatabaseCollection desde un diccionario."""
        fields = [CollectionField.from_dict(field_data) for field_data in data.get('fields', [])]
        return cls(
            _id=data.get('_id'),
            name=data.get('name'),
            description=data.get('description', ''),
            fields=fields,
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )