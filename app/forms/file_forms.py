# app/forms/file_forms.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, BooleanField, SubmitField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length, Optional

class UploadFileForm(FlaskForm):
    """Formulario para subir archivos."""
    file = FileField('Archivo', validators=[
        FileRequired(message="Debe seleccionar un archivo"),
        FileAllowed(['dwg', 'dxf', 'dwt', 'dwf', 'dws',  # AutoCAD
                     'blend', '3ds', 'obj', 'fbx', 'stl',  # Blender y formatos 3D
                     'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'odp',  # Ofimática
                     'pdf', 'txt', 'csv', 'json', 'xml',  # Documentos
                     'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tif', 'tiff', 'svg',  # Imágenes
                     'zip', 'rar', '7z', 'tar', 'gz'],  # Comprimidos
                    message="Formato de archivo no permitido")
    ])
    description = TextAreaField('Descripción', validators=[Optional(), Length(max=200, message="La descripción no puede exceder los 200 caracteres")])
    submit = SubmitField('Subir Archivo')

class UpdateFileForm(FlaskForm):
    """Formulario para actualizar información de archivos."""
    description = TextAreaField('Descripción', validators=[
        Optional(),
        Length(max=200, message="La descripción no puede exceder los 200 caracteres")
    ])
    submit = SubmitField('Actualizar Información')

class EnableFilesForm(FlaskForm):
    """Formulario para habilitar/deshabilitar gestión de archivos en una iniciativa."""
    enable_files = BooleanField('Habilitar gestión de archivos para esta iniciativa')
    submit = SubmitField('Guardar Configuración')

class AddDefaultFileForm(FlaskForm):
    """Formulario para agregar un archivo predeterminado del sistema."""
    file = FileField('Archivo', validators=[
        FileRequired(message="Debe seleccionar un archivo"),
        FileAllowed(['pdf', 'doc', 'docx', 'txt', 'xlsx', 'pptx'],
                    message="Solo se permiten documentos (PDF, Word, Excel, PowerPoint, Texto)")
    ])
    description = TextAreaField('Descripción', validators=[
        DataRequired(message="La descripción es obligatoria"),
        Length(max=200, message="La descripción no puede exceder los 200 caracteres")
    ])
    file_category = SelectField('Categoría', choices=[
        ('manual', 'Manual de Usuario'),
        ('template', 'Plantilla'),
        ('guide', 'Guía'),
        ('regulation', 'Normativa'),
        ('other', 'Otro')
    ])
    submit = SubmitField('Agregar Archivo Predeterminado')