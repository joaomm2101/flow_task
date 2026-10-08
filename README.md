# ⚡ FastAPI — The Complete Course

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?logo=sqlalchemy&logoColor=white)
![Alembic](https://img.shields.io/badge/Alembic-migrations-6BA81E)
![Pytest](https://img.shields.io/badge/Pytest-0A9EDC?logo=pytest&logoColor=white)
![Status](https://img.shields.io/badge/status-study%20project-blue)

Repositório com o código que escrevi acompanhando o curso **FastAPI – The Complete Course**, de **Eric Roby**. O curso evolui de uma API simples em memória até uma aplicação **full-stack de lista de tarefas (To-Do)** com autenticação JWT, banco de dados, migrações, testes automatizados e páginas HTML renderizadas no servidor.

> 📚 Projeto de estudo: o código reflete o conteúdo do curso, com pequenas adaptações minhas.

## 📑 Sumário

- [Funcionalidades](#-funcionalidades)
- [Stack](#-stack)
- [Estrutura do repositório](#-estrutura-do-repositório)
- [Como executar](#-como-executar)
- [Endpoints principais](#-endpoints-principais)
- [Testes](#-testes)
- [Migrações com Alembic](#-migrações-com-alembic)
- [Aviso de segurança](#-aviso-de-segurança)
- [Créditos](#-créditos)

## ✨ Funcionalidades

- ✅ Cadastro e login de usuários com **OAuth2 (password flow) + tokens JWT**
- ✅ Senhas armazenadas com hash **bcrypt**
- ✅ CRUD completo de tarefas, vinculadas ao usuário dono
- ✅ Controle de acesso por papel (**role**): rotas de admin restritas a `admin`
- ✅ Troca de senha e atualização de telefone do usuário
- ✅ Interface web com templates **Jinja2** e **Bootstrap**
- ✅ Migrações de banco com **Alembic**
- ✅ Testes automatizados com **pytest**, usando banco SQLite isolado
- ✅ Documentação interativa automática (Swagger UI e ReDoc)

## 🛠 Stack

| Camada | Tecnologias |
| --- | --- |
| **Linguagem** | Python |
| **Framework web** | [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/) |
| **Validação** | [Pydantic](https://docs.pydantic.dev/) |
| **Banco de dados / ORM** | [SQLAlchemy](https://www.sqlalchemy.org/) · SQLite (padrão), com scripts SQL para PostgreSQL e MySQL |
| **Drivers** | `psycopg2-binary` (PostgreSQL), `PyMySQL` (MySQL) |
| **Migrações** | [Alembic](https://alembic.sqlalchemy.org/) |
| **Autenticação** | `python-jose` (JWT), `passlib` + `bcrypt` (hash de senha), `python-multipart` (formulários) |
| **Front-end** | Jinja2, Bootstrap, JavaScript, arquivos estáticos via `aiofiles` |
| **Testes** | `pytest`, `httpx` / `TestClient`, `pytest-asyncio` |

## 📂 Estrutura do repositório

Cada pasta é uma etapa do curso, e o código evolui de uma para a outra:

```text
.
├── Database Scripts/        # Scripts SQL para PostgreSQL e MySQL
├── PythonRefresher/         # Revisão de Python (variáveis, listas, OOP, ...)
├── Project 1/               # API de livros: rotas GET básicas
├── Project 2/               # API de livros: CRUD, validação com Pydantic
├── Project 3/               # TodoApp: SQLAlchemy, JWT, routers, roles
├── Project 3.5/             # TodoApp + migrações com Alembic
├── Project 4/               # TodoApp + testes automatizados (pytest)
├── Project 5/               # TodoApp completo: front-end com Jinja2/Bootstrap
│   └── TodoApp/
│       ├── main.py          # Entrada da aplicação
│       ├── database.py      # Engine e sessão do SQLAlchemy
│       ├── models.py        # Modelos Users e Todos
│       ├── routers/         # auth, todos, admin, users
│       ├── templates/       # Páginas HTML (Jinja2)
│       ├── static/          # CSS e JS
│       ├── alembic/         # Migrações
│       └── test/            # Testes
└── requirements.txt
```

## 🚀 Como executar

Pré-requisito: **Python 3.10+**.

### 1️⃣ Clonar o repositório

```bash
git clone https://github.com/<seu-usuario>/<nome-do-repositorio>.git
cd <nome-do-repositorio>
```

### 2️⃣ Criar o ambiente virtual e instalar as dependências

```bash
python -m venv env
source env/bin/activate      # Windows: env\Scripts\activate
pip install -r requirements.txt
```

### 3️⃣ Iniciar a aplicação (Project 5)

Execute a partir da pasta do projeto, pois os caminhos de `static/` e `templates/` são relativos a ela:

```bash
cd "Project 5"
uvicorn TodoApp.main:app --reload
```

O banco SQLite (`todosapp.db`) é criado automaticamente na primeira execução.

### 4️⃣ Acessar

| Recurso | URL |
| --- | --- |
| Aplicação web | http://127.0.0.1:8000 |
| Swagger UI | http://127.0.0.1:8000/docs |
| ReDoc | http://127.0.0.1:8000/redoc |
| Health check | http://127.0.0.1:8000/healthy |

> Para rodar os projetos 1 e 2: `cd "Project 1" && uvicorn books:app --reload`.

## 🔌 Endpoints principais

| Método | Rota | Descrição | Auth |
| --- | --- | --- | --- |
| `POST` | `/auth/` | Cria um usuário | — |
| `POST` | `/auth/token` | Gera o token JWT | — |
| `GET` | `/todos/` | Lista as tarefas do usuário | ✅ |
| `GET` | `/todos/todo/{id}` | Busca uma tarefa | ✅ |
| `POST` | `/todos/todo` | Cria uma tarefa | ✅ |
| `PUT` | `/todos/todo/{id}` | Atualiza uma tarefa | ✅ |
| `DELETE` | `/todos/todo/{id}` | Remove uma tarefa | ✅ |
| `GET` | `/users/` | Dados do usuário logado | ✅ |
| `PUT` | `/users/password` | Altera a senha | ✅ |
| `PUT` | `/users/phonenumber/{phone_number}` | Atualiza o telefone | ✅ |
| `GET` | `/admin/todo` | Lista todas as tarefas | 🔒 admin |
| `DELETE` | `/admin/todo/{id}` | Remove qualquer tarefa | 🔒 admin |

As páginas HTML ficam em `/auth/login-page`, `/auth/register-page` e `/todos/todo-page`.

## 🧪 Testes

A partir da pasta `Project 5`:

```bash
pytest
```

Os testes sobrescrevem as dependências `get_db` e `get_current_user` para usar um SQLite separado (`testdb.db`), sem tocar nos dados reais.

## 🗄 Migrações com Alembic

```bash
cd "Project 5/TodoApp"
alembic revision -m "descrição da mudança"   # cria uma migração
alembic upgrade head                          # aplica as migrações
alembic downgrade -1                          # desfaz a última
```

Para usar PostgreSQL ou MySQL, defina `DATABASE_URL` (veja `.env.example`; remova o `connect_args` específico do SQLite, se houver) e use os scripts em `Database Scripts/` para criar as tabelas.

## 🔐 Aviso de segurança

A `SECRET_KEY` do JWT e a `DATABASE_URL` vêm de variáveis de ambiente (veja `app/.env.example`); a aplicação não inicia sem elas. Nunca versione valores reais.

```bash
openssl rand -hex 32
```

## 🙏 Créditos

- Curso e código-base por **Eric Roby**.
- Estrutura deste README inspirada em guias de boas práticas, como o [How to write a 4000 stars GitHub README](https://dev.to/daytona/how-to-write-a-4000-stars-github-readme-for-your-project-3167), e em READMEs de projetos similares, como [CodeV23/ToDoApp](https://github.com/CodeV23/ToDoApp).

## 📄 Licença

Projeto educacional, sem licença definida. Adicione um arquivo `LICENSE` (por exemplo, MIT) se quiser permitir reuso.
