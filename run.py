from app import create_app
import os

application = create_app()  # Mantenemos el nombre "application" por compatibilidad

# Configuración para Render
port = int(os.environ.get("PORT", 5000))

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=port)