// Funcionalidad para confirmación de eliminación
document.addEventListener('DOMContentLoaded', function() {
    // Manejo de confirmaciones para eliminar elementos
    const deleteButtons = document.querySelectorAll('.delete-confirm');

    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('¿Estás seguro de que deseas eliminar este elemento? Esta acción no se puede deshacer.')) {
                e.preventDefault();
            }
        });
    });

    // Auto-cerrar mensajes flash después de 5 segundos
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Manejo del cierre de sesión
    const logoutForm = document.getElementById('logout-form');
    if (logoutForm) {
        logoutForm.addEventListener('submit', function() {
            // Limpiar datos de almacenamiento local
            localStorage.removeItem('loginAttempts');
            localStorage.removeItem('lastAttemptTime');
            sessionStorage.clear();
        });
    }

    // Inicianlizar tooltips de Bootstrap
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });


    // Detectar inactividad y cerrar sesión automáticamente después de cierto tiempo
    let inactivityTimeout;
    const inactivityTime = 30 * 60 * 1000; // 30 minutos en milisegundos

    function resetInactivityTimer() {
        clearTimeout(inactivityTimeout);
        inactivityTimeout = setTimeout(logout, inactivityTime);
    }

    function logout() {
        // Redirigir a la página de cierre de sesión
        window.location.href = '/auth/logout';
    }

    // Eventos que reinician el temporizador de inactividad
    document.addEventListener('mousemove', resetInactivityTimer);
    document.addEventListener('keypress', resetInactivityTimer);
    document.addEventListener('click', resetInactivityTimer);
    document.addEventListener('scroll', resetInactivityTimer);

    // Iniciar el temporizador al cargar la página
    resetInactivityTimer();
});

// Función para validar formularios del lado del cliente
function validateForm(formId, rules) {
    const form = document.getElementById(formId);

    if (!form) return;

    form.addEventListener('submit', function(e) {
        let isValid = true;

        // Recorrer cada regla de validación
        for (const fieldId in rules) {
            const field = document.getElementById(fieldId);
            const fieldRules = rules[fieldId];
            const errorElement = document.getElementById(`${fieldId}-error`);

            if (!field || !errorElement) continue;

            // Limpiar mensajes de error anteriores
            errorElement.textContent = '';
            errorElement.classList.add('d-none');
            field.classList.remove('is-invalid');

            // Validar campo requerido
            if (fieldRules.required && field.value.trim() === '') {
                errorElement.textContent = fieldRules.requiredMessage || 'Este campo es obligatorio';
                errorElement.classList.remove('d-none');
                field.classList.add('is-invalid');
                isValid = false;
                continue;
            }

            // Validar longitud mínima
            if (fieldRules.minLength && field.value.length < fieldRules.minLength) {
                errorElement.textContent = fieldRules.minLengthMessage || `Este campo debe tener al menos ${fieldRules.minLength} caracteres`;
                errorElement.classList.remove('d-none');
                field.classList.add('is-invalid');
                isValid = false;
                continue;
            }

            // Validar expresiones regulares
            if (fieldRules.pattern && !new RegExp(fieldRules.pattern).test(field.value)) {
                errorElement.textContent = fieldRules.patternMessage || 'El formato no es válido';
                errorElement.classList.remove('d-none');
                field.classList.add('is-invalid');
                isValid = false;
                continue;
            }

            // Validar coincidencia con otro campo (ej: confirmar contraseña)
            if (fieldRules.match) {
                const matchField = document.getElementById(fieldRules.match);
                if (matchField && field.value !== matchField.value) {
                    errorElement.textContent = fieldRules.matchMessage || 'Los campos no coinciden';
                    errorElement.classList.remove('d-none');
                    field.classList.add('is-invalid');
                    isValid = false;
                    continue;
                }
            }

            // Validar email
            if (fieldRules.email && field.value.trim() !== '') {
                const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailPattern.test(field.value)) {
                    errorElement.textContent = fieldRules.emailMessage || 'Ingrese un correo electrónico válido';
                    errorElement.classList.remove('d-none');
                    field.classList.add('is-invalid');
                    isValid = false;
                    continue;
                }
            }

            // Función de validación personalizada
            if (fieldRules.customValidator && typeof fieldRules.customValidator === 'function') {
                const validationResult = fieldRules.customValidator(field.value);
                if (validationResult !== true) {
                    errorElement.textContent = validationResult || 'Campo inválido';
                    errorElement.classList.remove('d-none');
                    field.classList.add('is-invalid');
                    isValid = false;
                    continue;
                }
            }
        }

        if (!isValid) {
            e.preventDefault();
        }
    });
}

// Función para validar fortaleza de contraseñas
function validatePasswordStrength(password) {
    // Verificar longitud mínima
    if (password.length < 8) {
        return 'La contraseña debe tener al menos 8 caracteres';
    }

    // Verificar que contenga al menos una letra mayúscula
    if (!/[A-Z]/.test(password)) {
        return 'La contraseña debe contener al menos una letra mayúscula';
    }

    // Verificar que contenga al menos una letra minúscula
    if (!/[a-z]/.test(password)) {
        return 'La contraseña debe contener al menos una letra minúscula';
    }

    // Verificar que contenga al menos un número
    if (!/\d/.test(password)) {
        return 'La contraseña debe contener al menos un número';
    }

    // Verificar que contenga al menos un carácter especial
    if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
        return 'La contraseña debe contener al menos un carácter especial';
    }

    return true;
}