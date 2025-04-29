from app import create_app
import traceback

try:
    app = create_app()  # Este objeto estará disponible para gunicorn
except Exception as e:
    print("Error al iniciar la aplicación:")
    print(traceback.format_exc())

# Nota: no uses app.run() aquí, Render + gunicorn se encargan
