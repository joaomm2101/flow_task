    // Add Todo JS
    const todoForm = document.getElementById('todoForm');
    if (todoForm) {
        todoForm.addEventListener('submit', async function (event) {
            event.preventDefault();

            const form = event.target;
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());

            const payload = {
                title: data.title,
                description: data.description,
                priority: parseInt(data.priority),
                complete: false
            };

            try {
                const response = await authFetch('/todos/todo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (!response) return;

                if (response.ok) {
                    window.location.href = '/todos/todo-page';
                } else {
                    // Handle error
                    const errorData = await response.json();
                    alert(`Error: ${formatApiError(errorData)}`);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            }
        });
    }

    // Edit Todo JS
    const editTodoForm = document.getElementById('editTodoForm');
    if (editTodoForm) {
        editTodoForm.addEventListener('submit', async function (event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        var url = window.location.pathname;
        const todoId = url.substring(url.lastIndexOf('/') + 1);

        const payload = {
            title: data.title,
            description: data.description,
            priority: parseInt(data.priority),
            complete: data.complete === "on"
        };

        try {
            const response = await authFetch(`/todos/todo/${todoId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!response) return;

            if (response.ok) {
                window.location.href = '/todos/todo-page'; // Redirect to the todo page
            } else {
                // Handle error
                const errorData = await response.json();
                alert(`Error: ${formatApiError(errorData)}`);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred. Please try again.');
        }
    });

        document.getElementById('deleteButton').addEventListener('click', async function () {
            var url = window.location.pathname;
            const todoId = url.substring(url.lastIndexOf('/') + 1);

            try {
                const response = await authFetch(`/todos/todo/${todoId}`, {
                    method: 'DELETE'
                });
                if (!response) return;

                if (response.ok) {
                    // Handle success
                    window.location.href = '/todos/todo-page'; // Redirect to the todo page
                } else {
                    // Handle error
                    const errorData = await response.json();
                    alert(`Error: ${formatApiError(errorData)}`);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            }
        });

        
    }

    // Login JS
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async function (event) {
            event.preventDefault();

            const form = event.target;
            const formData = new FormData(form);

            const payload = new URLSearchParams();
            for (const [key, value] of formData.entries()) {
                payload.append(key, value);
            }

            try {
                const response = await fetch('/auth/token', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: payload.toString()
                });

                if (response.ok) {
                    // Handle success (e.g., redirect to dashboard)
                    const data = await response.json();
                    // Save the JWT in the access_token cookie (same lifetime as the token: 20 min)
                    document.cookie = `access_token=${encodeURIComponent(data.access_token)}; path=/; max-age=1200; SameSite=Lax`;
                    window.location.href = '/todos/todo-page';
                } else {
                    // Handle error
                    const errorData = await response.json();
                    alert(`Error: ${formatApiError(errorData)}`);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            }
        });
    }

    // Register JS
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async function (event) {
            event.preventDefault();

            const form = event.target;
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());

            if (data.password !== data.password2) {
                alert("Passwords do not match");
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

            try {
                const response = await fetch('/auth/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    window.location.href = '/auth/login-page';
                } else {
                    // Handle error
                    const errorData = await response.json();
                    alert(`Error: ${formatApiError(errorData)}`);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            }
        });
    }

    // FastAPI returns `detail` as a string, or as a list of objects on 422 validation errors
    function formatApiError(errorData) {
        const detail = errorData && errorData.detail;
        if (Array.isArray(detail)) {
            return detail.map((item) => `${(item.loc || []).slice(1).join('.')}: ${item.msg}`).join('\n');
        }
        return detail || 'Unexpected error';
    }





    // Helper function to get a cookie by name
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    };

    function clearAccessToken() {
        document.cookie = 'access_token=; path=/; max-age=0; SameSite=Lax';
    }

    function logout() {
        clearAccessToken();
        // The server also expires the cookie and redirects to the login page
        window.location.href = '/auth/logout';
    };

    // fetch() with the JWT from the cookie. A missing/expired token ends the session
    // and sends the user to the login page; in that case it resolves to null.
    async function authFetch(url, options = {}) {
        const token = getCookie('access_token');
        if (!token) {
            logout();
            return null;
        }
        const response = await fetch(url, {
            ...options,
            headers: { ...options.headers, 'Authorization': `Bearer ${token}` }
        });
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
