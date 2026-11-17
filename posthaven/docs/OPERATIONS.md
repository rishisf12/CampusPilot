# Operations

## Start/stop

```bash
docker compose up -d --build   # start
docker compose down            # stop
docker compose down -v         # wipe all data
```

## Ports

| Service | Port |
|---|---|
| Frontend (nginx) | 5173 |
| Backend (FastAPI) | 8000 |
| Postgres | 5432 |
| Redis | 6379 |
| GreenMail API | 8080 |
| GreenMail SMTP | 3025 |
| GreenMail IMAP | 3143 |

## Seed demo data

```bash
make seed   # creates alice@localhost / bob@localhost on GreenMail
```

## Using real IMAP providers

Set `ALLOW_PRIVATE_MAIL_HOSTS=false` and point accounts at real hosts (imap.gmail.com, etc.). App passwords recommended for Gmail/Outlook.

## Key rotation

Re-encrypt credentials by rotating `ENCRYPTION_KEY` and re-encrypting all `encrypted_password` values. (Rotation tooling is a stub; implement before production.)

## Scaling workers

Run multiple `worker` containers. The IdleSupervisor uses Redis leases so exactly one worker owns each account's IMAP IDLE connection.

## Backup/restore

`pg_dump` the Postgres volume; restore with `pg_restore`. Redis data is ephemeral (rebuild on restart).
