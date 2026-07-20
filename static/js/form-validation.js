(function () {
    'use strict';

    function initFormValidation() {
        // Auto-enable validation on all POST forms
        document.querySelectorAll('form[method="post"], form[method="POST"]').forEach(function (form) {
            form.classList.add('needs-validation');
            form.removeAttribute('novalidate');
        });

        var forms = document.querySelectorAll('.needs-validation');
        Array.prototype.slice.call(forms).forEach(function (form) {
            form.addEventListener('submit', function (event) {
                if (!form.checkValidity()) {
                    event.preventDefault();
                    event.stopPropagation();
                }
                form.classList.add('was-validated');
            }, false);

            // Real-time validation on input/blur
            form.querySelectorAll('input, select, textarea').forEach(function (input) {
                input.addEventListener('blur', function () {
                    if (!this.hasAttribute('required') && this.value.trim() === '') return;
                    this.classList.add('is-touched');
                    if (this.hasAttribute('required') && this.value.trim() === '') {
                        this.setCustomValidity('هذا الحقل مطلوب');
                    } else {
                        this.setCustomValidity('');
                    }
                });
                input.addEventListener('input', function () {
                    if (this.classList.contains('is-touched')) {
                        if (this.hasAttribute('required') && this.value.trim() === '') {
                            this.setCustomValidity('هذا الحقل مطلوب');
                        } else {
                            this.setCustomValidity('');
                        }
                        this.checkValidity();
                    }
                });
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFormValidation);
    } else {
        initFormValidation();
    }

    document.addEventListener('htmx:afterSwap', function () {
        initFormValidation();
    });
})();
