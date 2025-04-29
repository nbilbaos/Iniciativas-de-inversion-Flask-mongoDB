from app import create_app
import traceback

try:
    application = create_app()  # <<< Cambié 'app' por 'application'

    if __name__ == '__main__':
        print("Iniciando la aplicación Flask...")
        application.run(host='0.0.0.0', port=5001)  # <<< También cambié aquí
except Exception as e:
    print("Error al iniciar la aplicación:")
    print(traceback.format_exc())
