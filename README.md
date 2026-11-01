# tour-ceylon-server

FastAPI backend for Travel Ready Tours: listings, bookings, transfers, drivers, vendor and admin APIs, and online payments (PayHere). It talks to Postgres (Supabase), Clerk, Cloudinary, SMTP, and Geoapify/Google Maps. The traveler site (`tour-ceylon-client`) and the admin/vendor portal call this API.

## Run locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill it in; see "Configuration"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000/docs> for the API docs and <http://localhost:8000/health> for a health check. Python 3.12 is the tested version; the pinned packages have no wheels for 3.14.

Tests: `pip install pytest`, then `DATABASE_URL=sqlite:///:memory: pytest app/tests/test_payment.py app/tests/test_payment_flow.py app/tests/test_payment_pricing.py`.

## Configuration

All settings are environment variables, listed in `.env.example`. The server will not start without `DATABASE_URL`, `CLERK_JWT_PUBLIC_KEY` and `CLERK_ISSUER`. With `PAYMENT_PROVIDER=payhere` it also needs `PAYHERE_MERCHANT_ID` and `PAYHERE_MERCHANT_SECRET`. Online payments are described in [docs/PAYMENTS.md](docs/PAYMENTS.md).

Notes for `.env`:
- Put no `# comment` after a value on the same line.
- `CLERK_JWT_PUBLIC_KEY` is a PEM key written on one line with `\n` for line breaks.
- The Google Maps key is the variable `google-api` (with a hyphen).
- `ADDITIONAL_CORS_ORIGINS` is a JSON list, for example `["https://www.example.com","https://admin.example.com"]`.

## Deploy on a VPS with Docker Compose

`docker-compose.yml` runs only this API. The database stays on Supabase and the web apps are hosted separately. The container listens on `127.0.0.1:8000`, and a reverse proxy in front of it provides HTTPS.

### 1. Prepare the server

Use a recent Ubuntu or Debian VPS and a domain name (for example `api.example.com`) with an **A record** pointing at the server's IP.

```bash
# Docker Engine + Compose plugin (official convenience script)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER      # log out and back in afterwards

# Firewall: SSH and web traffic only (port 8000 stays closed)
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable
```

### 2. Get the code and configure it

```bash
git clone <repository-url> tour-ceylon-server
cd tour-ceylon-server
cp .env.example .env
nano .env
```

Fill in `.env`. For a production server set at least:
- `DATABASE_URL`, the Clerk and Supabase keys, SMTP, Cloudinary and map keys.
- `SECRET_KEY`: a long random value (`openssl rand -hex 32`). The server refuses to start with online payments in production while it is left at the default, because it signs the emailed payment links.
- `CLIENT_APP_URL`: the address of the **customer** site. Payment links in emails open `<CLIENT_APP_URL>/pay/<code>`.
- `PUBLIC_API_URL=https://api.example.com`, the public address from step 3.
- `PAYHERE_MODE=live` and live PayHere credentials only after going live (see [docs/PAYMENTS.md](docs/PAYMENTS.md)). Use `sandbox` until then.
- `CLIENT_RETURN_URL` and `CLIENT_CANCEL_URL`: the live customer-site pages (`/payment/return` and `/payment/cancel`).
- `ADDITIONAL_CORS_ORIGINS`: the domains of your live web apps.

### 3. Put HTTPS in front

Caddy gets and renews the certificate automatically:

```bash
sudo apt install -y caddy
echo 'api.example.com {
    reverse_proxy 127.0.0.1:8000
}' | sudo tee /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

nginx with certbot works too:

```nginx
server {
    server_name api.example.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

then `sudo certbot --nginx -d api.example.com`. The proxy must pass `X-Forwarded-For`; the payment notification rate limit uses it.

### 4. Start it

```bash
docker compose up -d --build
docker compose ps                         # api should become "healthy"
curl -s http://127.0.0.1:8000/health      # {"status":"healthy","database":"connected",...}
curl -s https://api.example.com/health    # the same, through HTTPS
```

### 5. Database tables for online payments (once)

The payment tables must exist before the first online payment. On a database that already has the other tables, create just these two (it skips tables that exist):

```bash
docker compose run --rm api python -c "import app.models; from app.config.database import engine; from app.models.base import Base; Base.metadata.create_all(engine, tables=[Base.metadata.tables['payments'], Base.metadata.tables['payment_events']], checkfirst=True); print('done')"
```

The Alembic history in `alembic/` is incomplete for existing databases (they record a revision that is not in this repository), so do not run `alembic upgrade head` on a live database without checking `alembic current` first.

### 6. Check online payments

If `PAYMENT_PROVIDER=payhere`, confirm PayHere can reach the server: `https://api.example.com/api/v1/payments/payhere/notify` must answer (a `GET` returns `405 Method Not Allowed`, which means it is reachable). Then make one sandbox payment from the customer site and check the `payments` table.

### Update to a new version

```bash
cd tour-ceylon-server
git pull
docker compose up -d --build
docker compose ps
```

### Roll back

```bash
git log --oneline -5                      # find the last good commit
git checkout <good-commit>
docker compose up -d --build
```

### Operate

```bash
docker compose logs -f api                # live logs
docker compose restart api
docker compose down                       # stop (the .env and logs volume are kept)
```

Changing `.env` needs `docker compose up -d` (it recreates the container with the new values). The `.env` file is never copied into the image.

## Layout

- `app/main.py`: app, CORS and middleware. `app/api/v1/`: routes. `app/services/`, `app/repositories/`, `app/models/`: business rules, data access, tables.
- `app/payments/`: provider-agnostic online payments with the PayHere adapter.
- `docker/Dockerfile`, `docker-compose.yml`, `.dockerignore`: container build and run.
- `alembic/`: migrations (see the note in step 5).
