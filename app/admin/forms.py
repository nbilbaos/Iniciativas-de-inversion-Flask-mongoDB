from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, BooleanField, SubmitField, TextAreaField, DateField
from wtforms.validators import DataRequired, Email, Optional
from flask_wtf.file import FileField, FileRequired, FileAllowed

class DynamicUserEditForm(FlaskForm):
    """Formulario dinámico para editar usuarios"""
    submit = SubmitField('Guardar Cambios')

class ExcelUploadForm(FlaskForm):
    excel_file = FileField('Archivo Excel (.xlsx)', validators=[
        FileRequired(),
        FileAllowed(['xlsx'], 'Solo se permiten archivos XLSX.')
    ])
    collection_name = StringField('Nombre de la Colección', validators=[DataRequired()])
    target_db = SelectField('Base de Datos Destino', choices=[
        ('db_metadata', 'Metadata'),
        ('main', 'Principal')
    ], default='db_metadata')
    submit = SubmitField('Procesar Archivo')