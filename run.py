from app import create_app


application = create_app()  # This MUST be named "application" for Elastic Beanstalk

# Set SERVER_NAME to None to accept any host header
application.config["SERVER_NAME"] = None  # Must be named "application" for Elastic Beanstalk

# Allow requests from any host
application.config["SERVER_NAME"] = None  # OJO: debe ser 'application', NO 'app'

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=5001)
