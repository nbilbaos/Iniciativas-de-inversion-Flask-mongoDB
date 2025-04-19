from flask_login import UserMixin
from bson.objectid import ObjectId
from datetime import datetime


class User(UserMixin):
    """Modelo de usuario para la autenticación con Flask-Login."""

    def __init__(self, _id=None, email=None, password=None, role=None,
                 active=True, created_at=None, last_login=None,
                 nombre=None, rut=None, direccion=None, telefono=None,
                 titulos=None, iniciativas=None, **kwargs):
        self._id = _id if _id else ObjectId()
        self.email = email
        self.password = password
        self.role = role  # admin, director, colaborador
        self.active = active
        self.created_at = created_at if created_at else datetime.utcnow()
        self.last_login = last_login

        # Nuevos campos
        self.nombre = nombre or ""
        self.rut = rut or ""
        self.direccion = direccion or ""
        self.telefono = telefono or ""
        self.titulos = titulos or []

        # Iniciativas asignadas (solo para colaboradores)
        # Lista de diccionarios con formato:
        # {
        #   'iniciativa_id': ObjectId,  # ID de la iniciativa
        #   'collection_name': str,     # Nombre de la colección
        #   'assigned_at': datetime,    # Fecha de asignación
        #   'assigned_by': str,         # ID del director que asignó
        #   'active': bool              # Si la asignación está activa
        # }
        self.iniciativas = iniciativas or []

    def get_id(self):
        """Método requerido por Flask-Login para obtener el ID del usuario."""
        return str(self._id)

    def is_active(self):
        """Método requerido por Flask-Login para verificar si el usuario está activo."""
        return self.active

    def is_admin(self):
        """Verifica si el usuario tiene el rol de administrador."""
        return self.role == 'admin'

    def is_director(self):
        """Verifica si el usuario tiene el rol de director."""
        return self.role == 'director'

    def is_colaborador(self):
        """Verifica si el usuario tiene el rol de colaborador."""
        return self.role == 'colaborador'

    def to_dict(self):
        """Convierte la instancia en un diccionario."""
        return {
            '_id': self._id,
            'email': self.email,
            'password': self.password,
            'role': self.role,
            'active': self.active,
            'created_at': self.created_at,
            'last_login': self.last_login,
            'nombre': self.nombre,
            'rut': self.rut,
            'direccion': self.direccion,
            'telefono': self.telefono,
            'titulos': self.titulos,
            'iniciativas': self.iniciativas
        }

    def add_iniciativa(self, iniciativa_id, collection_name, assigned_by):
        """
        Añade una iniciativa al usuario (solo para colaboradores)

        Args:
            iniciativa_id: ObjectId de la iniciativa
            collection_name: Nombre de la colección
            assigned_by: ID del director que asigna la iniciativa
        """
        if self.role != 'colaborador':
            return False

        # Verificar si ya está asignada
        for init in self.iniciativas:
            if (str(init.get('iniciativa_id')) == str(iniciativa_id) and
                    init.get('collection_name') == collection_name and
                    init.get('active')):
                return False  # Ya está asignada y activa

        # Añadir la iniciativa
        self.iniciativas.append({
            'iniciativa_id': ObjectId(iniciativa_id),
            'collection_name': collection_name,
            'assigned_at': datetime.utcnow(),
            'assigned_by': assigned_by,
            'active': True
        })
        return True

    def remove_iniciativa(self, iniciativa_id, collection_name, removed_by):
        """
        Marca una iniciativa como inactiva (no la elimina físicamente)

        Args:
            iniciativa_id: ObjectId de la iniciativa
            collection_name: Nombre de la colección
            removed_by: ID del director que desasigna la iniciativa
        """
        if self.role != 'colaborador':
            return False

        for i, init in enumerate(self.iniciativas):
            if (str(init.get('iniciativa_id')) == str(iniciativa_id) and
                    init.get('collection_name') == collection_name and
                    init.get('active')):
                # Marcar como inactiva
                self.iniciativas[i]['active'] = False
                self.iniciativas[i]['removed_at'] = datetime.utcnow()
                self.iniciativas[i]['removed_by'] = removed_by
                return True

        return False  # No se encontró la iniciativa activa

    def get_active_iniciativas(self):
        """Retorna solo las iniciativas activas del usuario."""
        return [init for init in self.iniciativas if init.get('active', False)]