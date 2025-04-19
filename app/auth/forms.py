from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
import re

class LoginForm(FlaskForm):
    """Formulario de inicio de sesión."""
    email = StringField('Correo Electrónico', validators=[
        DataRequired(message="El correo electrónico es obligatorio"),
        Email(message="Ingrese un correo electrónico válido"),
        Length(max=100, message="El correo electrónico no puede tener más de 100 caracteres")
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message="La contraseña es obligatoria"),
        Length(min=8, message="La contraseña debe tener al menos 8 caracteres")
    ])
    remember_me = BooleanField('Recordarme')
    submit = SubmitField('Iniciar Sesión')


class RegisterForm(FlaskForm):
    """Formulario de registro de usuario."""
    email = StringField('Correo Electrónico', validators=[
        DataRequired(message="El correo electrónico es obligatorio"),
        Email(message="Ingrese un correo electrónico válido"),
        Length(max=100, message="El correo electrónico no puede tener más de 100 caracteres")
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message="La contraseña es obligatoria"),
        Length(min=8, message="La contraseña debe tener al menos 8 caracteres")
    ])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[
        DataRequired(message="Confirme su contraseña"),
        EqualTo('password', message="Las contraseñas no coinciden")
    ])

    nombre = StringField('Nombre Completo', validators=[
        DataRequired(message="El nombre es obligatorio"),
        Length(max=100, message="El nombre no puede tener más de 100 caracteres")
    ])

    rut = StringField('RUT', validators=[
        DataRequired(message="El RUT es obligatorio"),
        Length(max=12, message="El RUT no puede tener más de 12 caracteres")
    ])

    direccion = StringField('Dirección', validators=[
        Length(max=200, message="La dirección no puede tener más de 200 caracteres")
    ])

    telefono = StringField('Teléfono de Contacto', validators=[
        Length(max=20, message="El teléfono no puede tener más de 20 caracteres")
    ])

    titulos = StringField('Títulos (separados por coma)', validators=[
        Length(max=300, message="Los títulos no pueden tener más de 300 caracteres en total")
    ])

    role = SelectField('Rol', choices=[
        ('director', 'Director'),
        ('colaborador', 'Colaborador')
    ])

    submit = SubmitField('Registrar')

    def validate_password(self, password):
        """Validar que la contraseña cumpla con requisitos de seguridad."""
        if not re.search(r"[A-Z]", password.data):
            raise ValidationError("La contraseña debe contener al menos una letra mayúscula.")
        if not re.search(r"[a-z]", password.data):
            raise ValidationError("La contraseña debe contener al menos una letra minúscula.")
        if not re.search(r"[0-9]", password.data):
            raise ValidationError("La contraseña debe contener al menos un número.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password.data):
            raise ValidationError("La contraseña debe contener al menos un carácter especial.")

class ChangePasswordForm(FlaskForm):
    """Formulario para cambiar contraseña."""
    current_password = PasswordField('Contraseña Actual', validators=[
        DataRequired(message="La contraseña actual es obligatoria")
    ])
    new_password = PasswordField('Nueva Contraseña', validators=[
        DataRequired(message="La nueva contraseña es obligatoria"),
        Length(min=8, message="La contraseña debe tener al menos 8 caracteres")
    ])
    confirm_password = PasswordField('Confirmar Nueva Contraseña', validators=[
        DataRequired(message="Confirme su nueva contraseña"),
        EqualTo('new_password', message="Las contraseñas no coinciden")
    ])
    submit = SubmitField('Cambiar Contraseña')

    def validate_new_password(self, new_password):
        """Validar que la contraseña cumpla con requisitos de seguridad."""
        if not re.search(r"[A-Z]", new_password.data):
            raise ValidationError("La contraseña debe contener al menos una letra mayúscula.")
        if not re.search(r"[a-z]", new_password.data):
            raise ValidationError("La contraseña debe contener al menos una letra minúscula.")
        if not re.search(r"[0-9]", new_password.data):
            raise ValidationError("La contraseña debe contener al menos un número.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_password.data):
            raise ValidationError("La contraseña debe contener al menos un carácter especial.")