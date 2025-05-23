# app/utils/timezone_utils.py
from datetime import datetime
import pytz

# Zona horaria de Chile
CHILE_TZ = pytz.timezone('America/Santiago')


def now_chile():
    """Obtener la hora actual en zona horaria de Chile"""
    return datetime.now(CHILE_TZ)


def utc_to_chile(utc_dt):
    """Convertir datetime UTC a zona horaria de Chile"""
    if utc_dt is None:
        return None

    # Si el datetime no tiene zona horaria, asumimos que es UTC
    if utc_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(utc_dt)

    return utc_dt.astimezone(CHILE_TZ)


def chile_to_utc(chile_dt):
    """Convertir datetime de Chile a UTC para almacenar en base de datos"""
    if chile_dt is None:
        return None

    # Si el datetime no tiene zona horaria, asumimos que es de Chile
    if chile_dt.tzinfo is None:
        chile_dt = CHILE_TZ.localize(chile_dt)

    return chile_dt.astimezone(pytz.utc).replace(tzinfo=None)


def format_chile_datetime(dt, format_str='%d/%m/%Y %H:%M'):
    """Formatear datetime para mostrar en zona horaria de Chile"""
    if dt is None:
        return 'No disponible'

    # Si es UTC, convertir a Chile
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)

    chile_dt = dt.astimezone(CHILE_TZ)
    return chile_dt.strftime(format_str)


def get_chile_date_only():
    """Obtener solo la fecha actual de Chile (sin hora)"""
    return now_chile().date()


def parse_chile_datetime(date_string, format_str='%d/%m/%Y %H:%M'):
    """Parsear string de fecha en zona horaria de Chile"""
    try:
        naive_dt = datetime.strptime(date_string, format_str)
        return CHILE_TZ.localize(naive_dt)
    except ValueError:
        return None