# Aplicación Flask con MongoDB y Sistema de Autenticación

Esta es una aplicación web desarrollada con Flask y MongoDB que incluye un sistema de autenticación robusto con múltiples roles de usuario (admin, director, colaborador).

## Características

* Estructura basada en Blueprints para una organización modular.
* Sistema de autenticación seguro con Flask-Login.
* Tres niveles de acceso: admin, director y colaborador.
* Integración con MongoDB para almacenamiento de datos.
* Medidas de seguridad: protección CSRF, bloqueo por intentos fallidos y captcha.
* Interfaz responsive utilizando Bootstrap 5.

## Requisitos previos

* Python 3.8+
* MongoDB instalado y en ejecución
* pip (administrador de paquetes de Python)

## Instalación

1. Clona este repositorio:
   ```bash
   git clone [https://github.com/tu-usuario/flask-mongodb-app.git](https://github.com/tu-usuario/flask-mongodb-app.git)
   cd flask-mongodb-app

## Crear entorno virtual para las dependecias (requiere instalar venv con pip)
python -m venv venv

## En Windows:
venv\Scripts\activate

## En macOS/Linux:
source venv/bin/activate

## Instalar dependencias:
pip install -r requirements.txt

## Iniciar MongoDB (puede variar según tu sistema)
* sudo systemctl start mongod    # En Linux
* brew services start mongodb    # En macOS con Homebrew

## Ejecucion
python run.py

└── run.py                    # Script para ejecutar la aplicación


