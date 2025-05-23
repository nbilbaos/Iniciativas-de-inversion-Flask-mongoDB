# app/utils/template_filters.py
from flask import current_app
from .timezone_utils import format_chile_datetime, utc_to_chile


def register_template_filters(app):
    """Registrar filtros personalizados para templates."""

    @app.template_filter('chile_datetime')
    def chile_datetime_filter(dt, format_str='%d/%m/%Y %H:%M'):
        """Filtro para formatear fechas en zona horaria de Chile."""
        return format_chile_datetime(dt, format_str)

    @app.template_filter('chile_date')
    def chile_date_filter(dt):
        """Filtro para formatear solo la fecha en zona horaria de Chile."""
        return format_chile_datetime(dt, '%d/%m/%Y')

    @app.template_filter('chile_time')
    def chile_time_filter(dt):
        """Filtro para formatear solo la hora en zona horaria de Chile."""
        return format_chile_datetime(dt, '%H:%M')

    @app.template_filter('relative_time')
    def relative_time_filter(dt):
        """Filtro para mostrar tiempo relativo (hace X tiempo)."""
        if not dt:
            return 'Nunca'

        from datetime import datetime
        import pytz
        from .timezone_utils import now_chile

        # Convertir a zona horaria de Chile si es necesario
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)

        chile_dt = dt.astimezone(pytz.timezone('America/Santiago'))
        now = now_chile()

        diff = now - chile_dt

        if diff.days > 0:
            if diff.days == 1:
                return 'Hace 1 día'
            elif diff.days < 7:
                return f'Hace {diff.days} días'
            elif diff.days < 30:
                weeks = diff.days // 7
                return f'Hace {weeks} semana{"s" if weeks > 1 else ""}'
            elif diff.days < 365:
                months = diff.days // 30
                return f'Hace {months} mes{"es" if months > 1 else ""}'
            else:
                years = diff.days // 365
                return f'Hace {years} año{"s" if years > 1 else ""}'

        seconds = diff.seconds
        if seconds < 60:
            return 'Hace menos de un minuto'
        elif seconds < 3600:
            minutes = seconds // 60
            return f'Hace {minutes} minuto{"s" if minutes > 1 else ""}'
        else:
            hours = seconds // 3600
            return f'Hace {hours} hora{"s" if hours > 1 else ""}'