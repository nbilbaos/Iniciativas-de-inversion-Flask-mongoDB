# app/health.py
from flask import Blueprint
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()
health_bp = Blueprint('health', __name__)

@csrf.exempt
@health_bp.route('/health', methods=['GET'])
def health_check():
    return 'OK', 200
