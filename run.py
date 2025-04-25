from app import create_app
import traceback

try:
    app = create_app()

    if __name__ == '__main__':
        print("Iniciando la aplicación Flask...")
        app.run(host='0.0.0.0', port=5001)
except Exception as e:
    print("Error al iniciar la aplicación:")
    print(traceback.format_exc())