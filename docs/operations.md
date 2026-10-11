# Guia de operação

Como publicar, operar e proteger o Flowtask. Todos os comandos partem da raiz do repositório.

## 1. Publicar (primeira vez)

Requisitos no servidor: Docker com Compose, as portas **80 e 443** liberadas e um domínio apontando para o servidor (para o certificado Let's Encrypt).

```bash
cp .env.compose.example .env
```

Edite `.env`:

| Variável | O que colocar |
| --- | --- |
| `POSTGRES_ADMIN_PASSWORD` | `openssl rand -hex 32` (superusuário do PostgreSQL, só para administração e backups) |
| `APP_DB_PASSWORD` | `openssl rand -hex 32` (papel `flowtask`, usado pela aplicação) |
| `SECRET_KEY` | `openssl rand -hex 32` (assinatura dos JWT) |
| `DOMAIN` | `app.seudominio.com` (sem `https://`) |

Use valores **hexadecimais**: eles entram numa URL de conexão e não precisam de escape. Depois:

```bash
docker compose up -d --build
docker compose ps                       # db, app e caddy devem ficar "healthy"/"running"
docker compose logs -f app              # logs em JSON; as migrações rodam antes do servidor subir
```

O `.env` é ignorado pelo git. **Nunca o versione**, e restrinja o acesso: `chmod 600 .env`.

Verifique de fora:

```bash
curl -sI https://app.seudominio.com/auth/login-page | grep -i -E "strict-transport|content-security|x-frame"
curl -s https://app.seudominio.com/ready      # {"status":"ready"}
```

> O volume do PostgreSQL só roda os scripts de `docker/initdb` na **primeira** criação. Se você mudar `APP_DB_PASSWORD` depois, altere também o papel no banco: `docker compose exec db psql -U postgres -c "ALTER ROLE flowtask PASSWORD '...'"`.

## 2. Atualizar a aplicação

```bash
git pull
docker compose up -d --build app
```

O container aplica `alembic upgrade head` ao iniciar. Com várias réplicas, defina `RUN_MIGRATIONS=false` nelas e rode as migrações num passo separado (`docker compose run --rm app sh -c "cd /srv/app && alembic upgrade head"`), para não migrar em paralelo.

**Migração de unicidade.** Se a migração `a3c1d7e9b2f4` abortar com "duplicate values exist", há contas repetidas. Ela não altera nada nesse caso. Resolva (renomeie ou una as contas) e rode de novo:

```bash
docker compose exec db psql -U postgres -d flowtask -c \
  "SELECT username, count(*) FROM users GROUP BY username HAVING count(*) > 1"
```

## 3. Criar um administrador

O cadastro público só cria usuários comuns. Cadastre-se normalmente e promova a conta:

```bash
docker compose exec db psql -U postgres -d flowtask -c \
  "UPDATE users SET role = 'admin' WHERE username = 'seu_usuario'"
```

O papel vai no JWT: a pessoa precisa **sair e entrar de novo** para o novo papel valer.

## 4. Backup e restauração

```bash
scripts/backup.sh                 # gera backups/flowtask-<data>.sql.gz e mantém os 14 mais recentes
KEEP=30 scripts/backup.sh         # outra retenção
```

Agende no `cron` do servidor (diário às 03:00):

```cron
0 3 * * * cd /caminho/do/projeto && scripts/backup.sh >> backups/backup.log 2>&1
```

Boas práticas: copie `backups/` para **fora do servidor** (outro provedor ou bucket com versionamento), pois um backup no mesmo disco não protege contra a perda do disco, e **teste a restauração** periodicamente.

Restaurar (**destrutivo**: substitui o banco atual, e o script pede confirmação):

```bash
scripts/restore.sh backups/flowtask-20261011T030000Z.sql.gz
```

## 5. Rotação de segredos

| Segredo | Quando | Como | Efeito |
| --- | --- | --- | --- |
| `SECRET_KEY` | Suspeita de vazamento, ou periodicamente | Novo valor no `.env`, depois `docker compose up -d app` | **Todas as sessões são encerradas** (todos precisam entrar de novo) |
| `APP_DB_PASSWORD` | Suspeita de vazamento | `ALTER ROLE flowtask PASSWORD '...'` no banco, atualizar `.env`, `docker compose up -d app` | Breve reinício do app |
| `POSTGRES_ADMIN_PASSWORD` | Idem | `ALTER ROLE postgres PASSWORD '...'`, atualizar `.env` | Só afeta administração e backups |

**Histórico do git.** Se uma chave ou senha já foi commitada, trocar o valor resolve o risco prático, mas o valor antigo continua visível no histórico. Reescrever o histórico (`git filter-repo`) é destrutivo e invalida clones e PRs; só faça se for realmente necessário e depois de rotacionar.

## 6. Monitoramento

- **Liveness:** `GET /healthy` (o processo está vivo). **Readiness:** `GET /ready` (o banco responde, devolve 503 se não). Use `/ready` no balanceador ou monitor externo (UptimeRobot, Better Stack...).
- **Logs:** uma linha JSON por requisição e erro em `docker compose logs app`, com `request_id`. Quando um usuário vir "Erro no servidor (código: ...)", procure o código nos logs: `docker compose logs app | grep <código>`.
- **Alertas de segurança** nos logs: `"cross-origin write refused"` (tentativa de CSRF) e picos de status 401/429 em `/auth/token` (força bruta).
- Não há Sentry nem métricas embutidos. Para erros em tempo real, adicione o SDK do Sentry no `create_app()`.

## 7. Checklist de endurecimento

Antes de abrir ao público:

- [ ] HTTPS ativo e `curl -I` mostra `Strict-Transport-Security`
- [ ] `ENABLE_DOCS` **não** está ligado (`/docs` responde 404)
- [ ] `COOKIE_SECURE` não foi definido como `false`
- [ ] `.env` com permissão `600` e fora do git
- [ ] Firewall: só 80 e 443 abertas (a porta 5432 do PostgreSQL **não** é publicada pelo compose; mantenha assim)
- [ ] Backup agendado, cópia externa feita e **restauração testada**
- [ ] Segredos rotacionados se já passaram pelo git
- [ ] `docker compose logs app` sem erros após o primeiro login e cadastro
- [ ] Imagens atualizadas periodicamente (`docker compose pull && docker compose up -d --build`) e PRs do Dependabot revisados

**PostgreSQL fora do Docker (desenvolvimento local).** Verifique o `pg_hba.conf`: se as linhas `host`/`local` usam `trust`, qualquer processo local conecta **sem senha**, e a senha do `DATABASE_URL` não protege nada. Em servidores, use `scram-sha-256`. Na stack do compose isso já vem configurado pela imagem oficial, que usa `scram-sha-256` para conexões de rede.

## 8. Limites conhecidos de escala

- O limitador de tentativas de login guarda o estado na memória de cada processo. Com `WEB_CONCURRENCY=2` o limite efetivo é cerca do dobro, e vários containers somam. Para um limite exato, use um único worker (`WEB_CONCURRENCY=1`) ou mova o limitador para o Redis.
- Sessões são JWT sem estado: não há como derrubar uma sessão específica antes de expirar (20 min). Em caso de incidente, rotacione a `SECRET_KEY`.
