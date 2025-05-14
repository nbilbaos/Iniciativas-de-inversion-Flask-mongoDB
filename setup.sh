#!/bin/bash
# Crea todas las carpetas necesarias para la aplicación
# Ejecutar en el proceso de construcción de Render

# Crear directorios de carga
mkdir -p app/uploads
mkdir -p app/uploads/default_files
mkdir -p app/temp_uploads

echo "Directorios de carga creados correctamente."

# Ejecutar scripts de Python para inicialización
python -m app.create_initial_folders
python -m app.setup_file_collections

echo "Configuración inicial completada."