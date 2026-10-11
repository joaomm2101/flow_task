# Flowtask

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)

Aplicação web de lista de tarefas (To-Do) construída com **FastAPI**: cadastro e login, tarefas por usuário, painel administrativo, interface renderizada no servidor (Jinja2 + Bootstrap) e API JSON. Nasceu do curso **FastAPI – The Complete Course** (Eric Roby) e foi endurecida para produção: autenticação por cookie `HttpOnly`, proteção contra CSRF e força bruta, migrações versionadas, logs estruturados, imagem Docker e CI com testes, lint, auditoria de dependências e varredura de segredos.

## Sumário

- [Funcionalidades](#funcionalidades)
- [Como executar](#como-executar)
- [Configuração](#configuração)
- [Rotas](#rotas)
- [Testes e CI](#testes-e-ci)
- [Banco de dados e migrações](#banco-de-dados-e-migrações)
- [Segurança](#segurança)
- [Produção](#produção)
- [Limitações conhecidas](#limitações-conhecidas)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Créditos](#créditos)

## Funcionalidades

- Cadastro e login com **JWT** guardado em cookie `HttpOnly` (a API também aceita `Authorization: Bearer`)
- Senhas com hash **bcrypt** e política mínima (8 a 72 caracteres, com letra e número)
- CRUD de tarefas, sempre restrito ao usuário dono
- Rotas de administração restritas ao papel `admin`
- Troca de senha (exige a senha atual) e atualização de telefone
- Interface em português: mensagens de erro no próprio formulário, páginas de erro amigáveis, confirmação antes de excluir
- `GET /healthy` (liveness) e `GET /ready` (readiness, consulta o banco)
- Logs em JSON com `X-Request-ID` por requisição

## Como executar

Pré-requisitos: **Docker** com Compose (caminho mais simples) ou **Python 3.13 + [uv](https://docs.astral.sh/uv/)** e um PostgreSQL.

### Com Docker (HTTP local)

```bash
cp .env.compose.example .env
# preencha os três segredos com valores aleatórios:
#   POSTGRES_ADMIN_PASSWORD, APP_DB_PASSWORD, SECRET_KEY   ->   openssl rand -hex 32
docker compose -f docker-compose.yml -f docker-compose.ci.yml up -d --build db app
```

A aplicação sobe em <http://127.0.0.1:8000>. As migrações são aplicadas automaticamente na inicialização. Para conferir o ambiente, rode `scripts/smoke_test.sh`.

### Sem Docker

```bash
uv sync
cp app/.env.example app/.env        # preencha SECRET_KEY e DATABASE_URL
set -a; source app/.env; set +a
(cd app && uv run alembic upgrade head)   # cria o schema (obrigatório na primeira vez e a cada deploy)
uv run uvicorn app.main:app --reload
```

`COOKIE_SECURE=false` é necessário em desenvolvimento por HTTP: o cookie de sessão é `Secure` por padrão. Para ver o Swagger local, defina `ENABLE_DOCS=true` (em <http://127.0.0.1:8000/docs>).

## Configuração

Tudo vem de variáveis de ambiente. A aplicação **não inicia** sem `SECRET_KEY` e `DATABASE_URL`.

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `SECRET_KEY` | — (obrigatória) | Chave de assinatura do JWT. Gere com `openssl rand -hex 32` |
| `DATABASE_URL` | — (obrigatória) | URL SQLAlchemy, por exemplo `postgresql://user:pass@host/db` |
| `COOKIE_SECURE` | `true` | `false` apenas em desenvolvimento por HTTP |
| `ENABLE_DOCS` | `false` | Liga `/docs`, `/redoc` e `/openapi.json` |
| `ALLOWED_ORIGIN_HOSTS` | vazio | Hosts extras (`host[:porta]`, separados por vírgula) autorizados a fazer escritas cross-origin |
| `LOG_LEVEL` | `INFO` | Nível dos logs |

Apenas no Docker: `WEB_CONCURRENCY` (workers, padrão 2), `FORWARDED_ALLOW_IPS` (proxies confiáveis), `RUN_MIGRATIONS` (`false` para não migrar ao iniciar), `DOMAIN` (host público atendido pelo Caddy), `POSTGRES_ADMIN_PASSWORD` e `APP_DB_PASSWORD`. Veja `.env.compose.example`.

## Rotas

Páginas (HTML): `/` (redireciona), `/auth/login-page`, `/auth/register-page`, `/todos/todo-page`, `/todos/add-todo-page`, `/todos/edit-todo-page/{id}`.

| Método | Rota | Descrição | Acesso |
| --- | --- | --- | --- |
| `POST` | `/auth/` | Cria usuário (sempre com papel `user`) | público |
| `POST` | `/auth/token` | Login: define o cookie `access_token` e devolve o JWT | público, com limite de tentativas |
| `GET` | `/auth/logout` | Encerra a sessão (apaga o cookie) | qualquer |
| `GET` | `/todos/` | Lista as tarefas do usuário | login |
| `GET` | `/todos/todo/{id}` | Busca uma tarefa | login |
| `POST` | `/todos/todo` | Cria uma tarefa | login |
| `PUT` | `/todos/todo/{id}` | Atualiza uma tarefa | login |
| `DELETE` | `/todos/todo/{id}` | Remove uma tarefa | login |
| `GET` | `/user/` | Dados do usuário logado | login |
| `PUT` | `/user/user/password` | Troca a senha (`{"password", "new_password"}` no corpo) | login |
| `PUT` | `/user/phone_number/{phone_number}` | Atualiza o telefone | login |
| `GET` | `/admin/todos` | Lista todas as tarefas | `admin` |
| `DELETE` | `/admin/todos/{id}` | Remove qualquer tarefa | `admin` |
| `GET` | `/healthy` · `/ready` | Liveness · readiness (consulta o banco) | público |

Clientes de API recebem JSON nos erros. Navegadores recebem páginas de erro em HTML, e um acesso direto a uma URL de API sem sessão é redirecionado para `/`.

Para criar um administrador, promova um usuário já cadastrado: `UPDATE users SET role = 'admin' WHERE username = '...';`. Isso nunca é possível pelo cadastro público.

## Testes e CI

```bash
uv run pytest app/test        # 100+ testes; usam SQLite temporário, sem tocar no seu banco
uvx ruff check app            # lint (pyflakes, bugbear, bandit)
```

Os testes de interface executam o `base.js` num DOM simulado e exigem `node` (são ignorados se ele não existir).

O GitHub Actions (`.github/workflows/ci.yml`) roda em todo PR e push na `main`: testes, `ruff`, `pip-audit`, `gitleaks` e um **smoke test do Docker** (build da imagem, PostgreSQL real, migrações do zero, cadastro, login, CRUD, cabeçalhos e CSRF). O check **CI passed** é obrigatório na `main`. O Dependabot propõe atualizações semanais; as que quebram o CI ficam bloqueadas.

## Banco de dados e migrações

O schema é definido **apenas** pelas migrações do Alembic (`app/alembic/versions`), e a aplicação não cria tabelas sozinha.

```bash
cd app
alembic upgrade head                       # aplica
alembic revision -m "descrição" --autogenerate   # nova migração a partir dos modelos
alembic downgrade -1                       # desfaz a última
```

Um teste garante que o schema migrado coincide com os modelos (`compare_metadata`) e que um banco vazio é construído só com migrações. A migração de unicidade (`username`/`email`) se recusa a rodar, sem alterar dados, se houver duplicatas.

## Segurança

| Ameaça | Defesa |
| --- | --- |
| Roubo do token por XSS | JWT em cookie `HttpOnly` + `SameSite=Lax` + `Secure`; CSP sem `unsafe-inline`; textos do servidor inseridos com `textContent` |
| CSRF | `SameSite=Lax` e recusa (403) de escritas cujo `Origin` não é do próprio host |
| Força bruta no login | 5 falhas por usuário+IP e 20 por IP em 15 min → 429 com `Retry-After`; memória do limitador limitada |
| Escalação de privilégio | O cadastro público ignora `role`; rotas admin checam o papel |
| Acesso a dados de outros usuários | Todas as consultas e a página de edição filtram por `owner_id` |
| Contas duplicadas | `UNIQUE` em `username` e `email` + resposta 409 |
| Senhas fracas / vazamento de hash | Política de senha; `GET /user/` nunca devolve o hash; troca de senha exige a senha atual |
| Vazamento de erros | 500 genérico com `request_id`; o traceback fica só no log |
| Dependências vulneráveis | `python-jose` trocado por PyJWT; `pip-audit` e Dependabot no CI |
| Segredos no código | Apenas variáveis de ambiente; `gitleaks` no CI |

Também há `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS (sob HTTPS) e `Cache-Control: no-store` nas respostas dinâmicas. **Se este repositório já esteve público com a chave JWT ou a senha do banco antigas no histórico, considere-as vazadas e rotacione-as** (veja [docs/operations.md](docs/operations.md)).

## Produção

A stack de produção está em `docker-compose.yml`: **Caddy** (HTTPS automático) → **app** (sem porta publicada, sistema de arquivos somente leitura, sem capabilities) → **PostgreSQL** (a aplicação usa um papel sem privilégios de superusuário). O passo a passo, backups, restauração, rotação de segredos e checklist de endurecimento estão em **[docs/operations.md](docs/operations.md)**.

```bash
cp .env.compose.example .env     # preencha os segredos e DOMAIN=seu.dominio.com
docker compose up -d --build
```

## Limitações conhecidas

- **Recuperação de senha** ainda não existe (exige envio de e-mail); também não há confirmação de e-mail.
- O **limitador de login é por processo**: com `WEB_CONCURRENCY=2` o limite efetivo é cerca do dobro, e um reinício o zera. Para várias réplicas, mova-o para o Redis.
- O JWT dura 20 minutos e **não pode ser revogado** antes disso (não há refresh token nem lista de revogação).
- `bcrypt` está fixado em `4.0.1` por incompatibilidade do `passlib` com versões novas; o ideal é usar o `bcrypt` diretamente.
- Não há monitoramento de erros nem métricas (Sentry/Prometheus); apenas logs JSON.
- A fonte vem do Google Fonts (único recurso externo). Para zero requisições externas, hospede as fontes e ajuste a CSP em `app/main.py`.

## Estrutura do projeto

```text
.
├── app/
│   ├── main.py            # create_app(): middlewares, handlers de erro, rotas
│   ├── security.py        # política de senha e limitador de login
│   ├── observability.py   # logs JSON e request id
│   ├── database.py · models.py
│   ├── routers/           # auth, todos, user, admin
│   ├── templates/ · static/   # Jinja2, CSS, JS, favicon
│   ├── alembic/           # migrações
│   └── test/              # testes (pytest)
├── docker/                # entrypoint, Caddyfile, init do banco
├── scripts/               # smoke_test.sh, backup.sh, restore.sh
├── docs/operations.md     # guia de operação
├── Dockerfile · docker-compose.yml
└── .github/workflows/ci.yml
```

## Créditos

Baseado no curso **FastAPI – The Complete Course**, de [Eric Roby](https://github.com/codingwithroby).
