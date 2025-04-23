# app/models/task.py
from datetime import datetime
from bson.objectid import ObjectId


class Task:
    """Representa una tarea en el sistema."""

    def __init__(self, content, initiative_id, created_by, assigned_to=None,
                 is_completed=False, completed_by=None, completed_at=None,
                 _id=None, created_at=None):
        self._id = _id or ObjectId()
        self.content = content  # Contenido de la tarea (máximo 200 palabras)
        self.initiative_id = initiative_id  # ID de la iniciativa relacionada
        self.created_by = created_by  # ID del usuario que creó la tarea
        self.created_at = created_at or datetime.utcnow()
        self.assigned_to = assigned_to or []  # Lista de IDs de usuarios asignados (opcional)
        self.is_completed = is_completed  # Si la tarea está completada o no
        self.completed_by = completed_by  # ID del usuario que completó la tarea
        self.completed_at = completed_at  # Fecha de finalización

    def complete(self, user_id):
        """Marca la tarea como completada."""
        if self.is_completed:
            return False

        self.is_completed = True
        self.completed_by = user_id
        self.completed_at = datetime.utcnow()
        return True

    def reopen(self):
        """Reabre una tarea que estaba completada."""
        if not self.is_completed:
            return False

        self.is_completed = False
        self.completed_by = None
        self.completed_at = None
        return True

    def to_dict(self):
        """Convierte la tarea a un diccionario para almacenamiento."""
        return {
            '_id': self._id,
            'content': self.content,
            'initiative_id': self.initiative_id,
            'created_by': self.created_by,
            'created_at': self.created_at,
            'assigned_to': self.assigned_to,
            'is_completed': self.is_completed,
            'completed_by': self.completed_by,
            'completed_at': self.completed_at
        }

    @classmethod
    def from_dict(cls, data):
        """Crea una instancia de Task desde un diccionario."""
        return cls(
            _id=data.get('_id'),
            content=data.get('content'),
            initiative_id=data.get('initiative_id'),
            created_by=data.get('created_by'),
            created_at=data.get('created_at'),
            assigned_to=data.get('assigned_to', []),
            is_completed=data.get('is_completed', False),
            completed_by=data.get('completed_by'),
            completed_at=data.get('completed_at')
        )