// JavaScript for sites management page

// Search functionality
document.getElementById('searchInput')?.addEventListener('input', function(e) {
    const searchTerm = e.target.value.toLowerCase();
    const rows = document.querySelectorAll('.site-row');

    rows.forEach(row => {
        const name = row.dataset.name.toLowerCase();
        const url = row.dataset.url.toLowerCase();

        if (name.includes(searchTerm) || url.includes(searchTerm)) {
            row.style.display = '';
            if (searchTerm.length > 0) {
                row.classList.add('highlight');
            } else {
                row.classList.remove('highlight');
            }
        } else {
            row.style.display = 'none';
            row.classList.remove('highlight');
        }
    });
});

// Delete modal
const deleteModal = document.getElementById('deleteModal');
if (deleteModal) {
    deleteModal.addEventListener('show.bs.modal', function(event) {
        const button = event.relatedTarget;
        const siteName = button.getAttribute('data-site-name');

        // Update modal content
        document.getElementById('deleteSiteName').textContent = siteName;

        // Update form action
        const form = document.getElementById('deleteForm');
        form.action = `/sites/${siteName}/delete`;
    });
}

// SSH connection test
document.querySelectorAll('.test-ssh-btn').forEach(button => {
    button.addEventListener('click', async function() {
        const siteName = this.getAttribute('data-site-name');
        const originalHTML = this.innerHTML;

        // Show loading spinner
        this.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
        this.disabled = true;

        try {
            const response = await fetch(`/api/sites/${siteName}/test`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            // Show toast notification
            showToast(data.message, data.success ? 'success' : 'danger');

        } catch (error) {
            showToast('Error testing connection: ' + error.message, 'danger');
        } finally {
            // Restore button
            this.innerHTML = originalHTML;
            this.disabled = false;
        }
    });
});

// Show toast notification
function showToast(message, type = 'info') {
    const toastEl = document.getElementById('sshTestToast');
    const toastBody = document.getElementById('sshTestMessage');

    // Set message and styling
    toastBody.textContent = message;
    toastBody.className = `toast-body text-${type === 'success' ? 'success' : type === 'danger' ? 'danger' : 'info'}`;

    // Show toast
    const toast = new bootstrap.Toast(toastEl, {
        autohide: true,
        delay: 5000
    });
    toast.show();
}
