# Guardar como scripts/setup_collections.py

#Script de migración para verificar y crear las colecciones necesarias. Este script
#es útil para correrlo manualmente cuando sea necesario, especialmente durante
#la configuración inicial o al actualizar la aplicación

from flask import Flask
from pymongo import MongoClient
import os
import sys

# Añadir el directorio principal al path para poder importar los módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar configuración
from app.config import get_config


def setup_collections():
    """Script para verificar y crear todas las colecciones necesarias en la base de datos."""
    # Obtener configuración
    config = get_config()

    # Conectar a MongoDB
    try:
        client = MongoClient(config.MONGO_URI)
        db = client.get_default_database()
        print(f"Conectado a la base de datos: {db.name}")
    except Exception as e:
        print(f"Error al conectar a MongoDB: {e}")
        return

    # Lista de colecciones a verificar
    required_collections = [
        {
            'name': 'tasks',
            'indexes': [
                [("initiative_id", 1)],
                [("created_by", 1)],
                [("assigned_to", 1)],
                [("is_completed", 1)],
                [("created_at", -1)]
            ]
        },
        {
            'name': 'users',
            'indexes': [
                [("email", 1)],
                [("role", 1)]
            ]
        },
        {
            'name': 'assignment_history',
            'indexes': [
                [("initiative_id", 1)],
                [("timestamp", -1)]
            ]
        },
        {
            'name': 'estado_iniciativa_historial',
            'indexes': [
                [("initiative_id", 1)],
                [("timestamp", -1)]
            ]
        },
        {
            'name': 'modification_history',
            'indexes': [
                [("initiative_id", 1)],
                [("timestamp", -1)]
            ]
        }
    ]

    # Verificar y crear cada colección
    existing_collections = db.list_collection_names()

    for collection_info in required_collections:
        collection_name = collection_info['name']

        if collection_name not in existing_collections:
            print(f"Creando colección: {collection_name}")
            db.create_collection(collection_name)

            # Crear índices
            for index in collection_info['indexes']:
                db[collection_name].create_index(index)
                print(f"  Índice creado: {index}")
        else:
            print(f"La colección '{collection_name}' ya existe")

            # Verificar y crear índices que falten
            existing_indices = [idx['key'] for idx in db[collection_name].list_indexes()]
            for index in collection_info['indexes']:
                index_tuple = tuple(index)
                if index_tuple not in existing_indices:
                    db[collection_name].create_index(index)
                    print(f"  Índice creado: {index}")

    print("Todas las colecciones han sido verificadas y configuradas correctamente.")


if __name__ == "__main__":
    setup_collections()