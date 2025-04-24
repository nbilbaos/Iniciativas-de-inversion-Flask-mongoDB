# app/setup_file_collections.py
import os
import sys
from flask import Flask
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Obtener la URI de MongoDB
MONGO_URI = os.environ.get('MONGO_URI')

if not MONGO_URI:
    print("Error: La variable de entorno MONGO_URI no está configurada.")
    sys.exit(1)

try:
    # Conectar a MongoDB
    client = MongoClient(MONGO_URI)
    db = client.get_database()

    # Verificar conexión
    client.admin.command('ping')
    print("Conexión a MongoDB establecida con éxito.")

    # Crear colección para archivos si no existe
    if 'files' not in db.list_collection_names():
        db.create_collection('files')
        print("Colección 'files' creada.")
    else:
        print("La colección 'files' ya existe.")

    # Crear índices para la colección de archivos
    db.files.create_index([("initiative_id", ASCENDING)])
    db.files.create_index([("uploaded_by", ASCENDING)])
    db.files.create_index([("uploaded_at", DESCENDING)])
    db.files.create_index([("active", ASCENDING)])
    db.files.create_index([("is_default", ASCENDING)])
    print("Índices creados para la colección 'files'.")

    # Crear colección para archivos predeterminados si no existe
    if 'default_files' not in db.list_collection_names():
        db.create_collection('default_files')
        print("Colección 'default_files' creada.")
    else:
        print("La colección 'default_files' ya existe.")

    # Crear índices para la colección de archivos predeterminados
    db.default_files.create_index([("uploaded_by", ASCENDING)])
    db.default_files.create_index([("category", ASCENDING)])
    db.default_files.create_index([("active", ASCENDING)])
    print("Índices creados para la colección 'default_files'.")

    # Crear colección para historial si no existe
    if 'file_history' not in db.list_collection_names():
        db.create_collection('file_history')
        print("Colección 'file_history' creada.")
    else:
        print("La colección 'file_history' ya existe.")

    # Crear índices para la colección de historial
    db.file_history.create_index([("initiative_id", ASCENDING)])
    db.file_history.create_index([("file_id", ASCENDING)])
    db.file_history.create_index([("user_id", ASCENDING)])
    db.file_history.create_index([("timestamp", DESCENDING)])
    print("Índices creados para la colección 'file_history'.")

    # Actualizar el esquema de iniciativas para incluir el campo files_enabled
    collection_name = os.environ.get('INITIATIVES_COLLECTION', 'db_metadata.iniciativas_2025')

    # Manejar colecciones con punto (subcollections)
    if '.' in collection_name:
        parts = collection_name.split('.')
        if len(parts) > 1:
            initiatives_coll = db[parts[0]][parts[1]]
        else:
            initiatives_coll = db[collection_name]
    else:
        initiatives_coll = db[collection_name]

    # Añadir el campo files_enabled a todas las iniciativas que no lo tengan
    result = initiatives_coll.update_many(
        {"files_enabled": {"$exists": False}},
        {"$set": {"files_enabled": False}}
    )

    print(f"Iniciativas actualizadas con el campo 'files_enabled': {result.modified_count}")

    print("Configuración de colecciones para archivos completada con éxito.")

except Exception as e:
    print(f"Error al configurar las colecciones: {e}")
    sys.exit(1)