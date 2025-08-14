document.addEventListener('DOMContentLoaded', function() {
    // Inicializar todos los modales de Bootstrap
    var modals = document.querySelectorAll('.modal');
    modals.forEach(function(modal) {
        new bootstrap.Modal(modal);
    });
});

function abrirModalEditar(userId, username) {
    const form = document.getElementById('formEditarUsuario');
    form.action = `/autenticacion/editar/${userId}/`;
    
    // Mostrar indicador de carga
    Swal.fire({
        title: 'Cargando...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
    
    // Obtener los datos actuales del usuario
    fetch(`/autenticacion/usuario/${userId}/`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('editUserId').value = userId;
            document.getElementById('editUsername').value = data.username;
            document.getElementById('editFirstName').value = data.first_name;
            document.getElementById('editLastName').value = data.last_name;
            document.getElementById('editPassword').value = '';
            
            // Cerrar el indicador de carga
            Swal.close();
            
            // Abrir el modal usando Bootstrap 5
            const editModal = new bootstrap.Modal(document.getElementById('editarUsuarioModal'));
            editModal.show();
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({
                title: 'Error',
                text: 'No se pudieron cargar los datos del usuario',
                icon: 'error'
            });
        });
}

// Manejar el envío del formulario de edición
document.addEventListener('DOMContentLoaded', function() {
    const formEditarUsuario = document.getElementById('formEditarUsuario');
    if (formEditarUsuario) {
        formEditarUsuario.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const form = this;
            const submitBtn = form.querySelector('button[type="submit"]');
            const modal = form.closest('.modal');
            const modalInstance = bootstrap.Modal.getInstance(modal);
            
            // Deshabilitar botón
            submitBtn.disabled = true;
            submitBtn.innerHTML = `
                <span class="spinner-border spinner-border-sm" role="status"></span>
                <span class="ms-2">Guardando...</span>
            `;
            
            fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    modalInstance.hide();
                    Swal.fire({
                        title: '¡Éxito!',
                        text: 'Gestor actualizado correctamente',
                        icon: 'success',
                        timer: 1500,
                        showConfirmButton: false
                    }).then(() => {
                        location.reload();
                    });
                } else {
                    throw new Error(data.message || 'Error al actualizar el gestor');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                Swal.fire({
                    title: 'Error',
                    text: error.message || 'Error al procesar la solicitud',
                    icon: 'error'
                });
            })
            .finally(() => {
                // Restaurar botón
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Guardar Cambios';
            });
        });
    }
});