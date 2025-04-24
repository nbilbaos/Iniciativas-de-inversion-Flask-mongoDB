# app/create_initial_folders.py
import os
import sys

# Obtener la ruta de la aplicación
app_path = os.path.dirname(os.path.abspath(__file__))

# Definir las carpetas a crear
folders = [
    os.path.join(app_path, 'uploads'),
    os.path.join(app_path, 'uploads', 'default_files'),
    os.path.join(app_path, 'temp_uploads')
]

# Crear las carpetas
for folder in folders:
    try:
        os.makedirs(folder, exist_ok=True)
        print(f"Carpeta creada o verificada: {folder}")
    except Exception as e:
        print(f"Error al crear la carpeta {folder}: {e}")
        sys.exit(1)

print("Todas las carpetas de archivos se han creado correctamente.")