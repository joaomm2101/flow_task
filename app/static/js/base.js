    // ---------------------------------------------------------------------------
    // Form helpers. Messages are shown inline in the form's .form-feedback element
    // (always via textContent, never innerHTML).
    // ---------------------------------------------------------------------------
    function showFeedback(form, message) {
        const feedback = form.querySelector('.form-feedback');
        if (feedback) {
            feedback.textContent = message;
            feedback.hidden = !message;
        }
    }

    function setBusy(form, busy) {
        form.querySelectorAll('button[type="submit"], button[data-busy-lock]').forEach((button) => {
            button.disabled = busy;
        });
        form.setAttribute('aria-busy', busy ? 'true' : 'false');
    }

    // FastAPI returns `detail` as a string, or as a list of objects on 422 validation errors.
    async function describeError(response, overrides = {}) {
        let data = null;
        try {
            data = await response.json();
        } catch (error) {
            // non-JSON body (e.g. a proxy error page): fall through to the generic messages
        }
        if (overrides[response.status]) return overrides[response.status];

        const detail = data && data.detail;
        switch (response.status) {
            case 403: return 'Ação não permitida.';
            case 404: return 'Tarefa não encontrada.';
            case 409: return 'Usuário ou e-mail já cadastrado.';
            case 429: return 'Muitas tentativas. Aguarde alguns minutos e tente novamente.';
            case 422:
                if (Array.isArray(detail)) {
                    if (detail.some((item) => (item.loc || []).includes('password') || (item.loc || []).includes('new_password'))) {
                        return 'A senha deve ter de 8 a 72 caracteres, com pelo menos uma letra e um número.';
                    }
                    return detail.map((item) => `${(item.loc || []).slice(1).join('.')}: ${item.msg}`).join(' · ');
                }
                break;
            default:
        }
        if (response.status >= 500) {
            const code = data && data.request_id ? ` (código: ${data.request_id})` : '';
            return `Erro no servidor. Tente novamente em instantes.${code}`;
        }
        return typeof detail === 'string' ? detail : 'Não foi possível concluir a ação.';
    }

    // Runs `action` (returns a fetch Response or null) for a form: clears old feedback, locks the
    // submit button against double clicks, shows errors inline. Resolves to the Response when it
    // was ok. On success the button stays locked: the caller navigates away.
    async function runForm(form, action, errorOverrides = {}) {
        showFeedback(form, '');
        setBusy(form, true);
        try {
            const response = await action();
            if (!response) return null; // session ended: authFetch is already redirecting
            if (response.ok) return response;
            showFeedback(form, await describeError(response, errorOverrides));
        } catch (error) {
            console.error('Error:', error);
            showFeedback(form, 'Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.');
        }
        setBusy(form, false);
        return null;
    }

    // ---------------------------------------------------------------------------
    // Add todo
    // ---------------------------------------------------------------------------
    const todoForm = document.getElementById('todoForm');
    if (todoForm) {
        todoForm.addEventListener('submit', async function (event) {
            event.preventDefault();

            const form = event.target;
            const data = Object.fromEntries(new FormData(form).entries());
            const payload = {
                title: data.title,
                description: data.description,
                priority: parseInt(data.priority),
                complete: false
            };

            const response = await runForm(form, () => authFetch('/todos/todo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }));
            if (response) window.location.href = '/todos/todo-page';
        });
    }

    // ---------------------------------------------------------------------------
    // Edit / delete todo
    // ---------------------------------------------------------------------------
    const editTodoForm = document.getElementById('editTodoForm');
    if (editTodoForm) {
        const todoId = window.location.pathname.substring(window.location.pathname.lastIndexOf('/') + 1);

        editTodoForm.addEventListener('submit', async function (event) {
            event.preventDefault();

            const form = event.target;
            const data = Object.fromEntries(new FormData(form).entries());
            const payload = {
                title: data.title,
                description: data.description,
                priority: parseInt(data.priority),
                complete: data.complete === 'on'
            };

            const response = await runForm(form, () => authFetch(`/todos/todo/${todoId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }));
            if (response) window.location.href = '/todos/todo-page';
        });

        const deleteButton = document.getElementById('deleteButton');
        if (deleteButton) {
            deleteButton.addEventListener('click', async function () {
                if (!window.confirm('Excluir esta tarefa? Essa ação não pode ser desfeita.')) return;

                const response = await runForm(editTodoForm, () => authFetch(`/todos/todo/${todoId}`, {
                    method: 'DELETE'
                }));
                if (response) window.location.href = '/todos/todo-page';
            });
        }
    }

    // ---------------------------------------------------------------------------
    // Login
    // ---------------------------------------------------------------------------
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async function (event) {
            event.preventDefault();

            const form = event.target;
            const payload = new URLSearchParams();
            for (const [key, value] of new FormData(form).entries()) {
                payload.append(key, value);
            }

            const response = await runForm(form, () => fetch('/auth/token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: payload.toString()
            }), { 401: 'Usuário ou senha inválidos.' });
            // The server set the HttpOnly access_token cookie; scripts never see the JWT
            if (response) window.location.href = '/todos/todo-page';
        });
    }

    // ---------------------------------------------------------------------------
    // Register
    // ---------------------------------------------------------------------------
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async function (event) {
            event.preventDefault();

            const form = event.target;
            const data = Object.fromEntries(new FormData(form).entries());

            if (data.password !== data.password2) {
                showFeedback(form, 'As senhas não conferem.');
                return;
            }

            const payload = {
                email: data.email,
                username: data.username,
                first_name: data.first_name,
                last_name: data.last_name,
                phone_number: data.phone_number,
                password: data.password
            };

            const response = await runForm(form, () => fetch('/auth/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }));
            if (response) window.location.href = '/auth/login-page';
        });
    }

    // ---------------------------------------------------------------------------
    // Session
    // ---------------------------------------------------------------------------
    function logout() {
        // The server expires the HttpOnly access_token cookie and redirects to the login page
        window.location.href = '/auth/logout';
    };

    // fetch() for authenticated calls: the browser sends the HttpOnly session cookie by itself.
    // A 401 (missing/expired session) ends the session and resolves to null.
    async function authFetch(url, options = {}) {
        const response = await fetch(url, { ...options, credentials: 'same-origin' });
        if (response.status === 401) {
            logout();
            return null;
        }
        return response;
    }

    // Logout buttons (no inline onclick: the Content-Security-Policy forbids inline handlers)
    document.querySelectorAll('[data-logout]').forEach((button) => {
        button.addEventListener('click', logout);
    });

    const taskSearch = document.getElementById('taskSearch');
    if (taskSearch) {
        taskSearch.addEventListener('input', function () {
            const term = this.value.trim().toLowerCase();
            document.querySelectorAll('.tasks-table tbody tr[data-task]').forEach((row) => {
                row.hidden = !row.dataset.task.includes(term);
            });
        });
    }
