# Fly.io hosting guide

This guide deploys the Calendar Matching FastAPI prototype to Fly.io as the first supported hosting target.

Fly deploys from the project source directory with `fly deploy`. The command reads `fly.toml`, builds the Docker image configured there, and updates the app's Fly Machines.

## What is included in this repository

- `Dockerfile` builds the FastAPI app image from `python:3.10-slim` and starts Uvicorn on `0.0.0.0:8080`.
- `fly.toml` defines the Fly app configuration, Dockerfile build, and HTTP service on internal port `8080`.
- `.github/workflows/ci.yml` runs the existing setup verifier on pushes and pull requests.
- `.github/workflows/deploy-fly.yml` optionally deploys to Fly.io from GitHub Actions.
- `requirements.txt` mirrors `pyproject.toml` dependencies for the Docker image build.

## 1. Install and authenticate flyctl

1. Create or sign in to your Fly.io account.
2. Install `flyctl` by following the Fly.io installation instructions for your operating system.
3. Authenticate locally:

```bash
fly auth login
```

## 2. Create the Fly app

From the repository root, create the Fly app without deploying immediately:

```bash
fly launch --no-deploy
```

When prompted:

1. Choose or enter a globally unique app name.
2. Choose a region close to your expected users. The committed `fly.toml` starts with `ams` for Amsterdam.
3. Keep the Dockerfile build path.
4. Decline adding a database unless you already know which durable hosted database you want to use.

After `fly launch --no-deploy`, make sure the `app` value in `fly.toml` matches your actual Fly app name.

## 3. Configure runtime secrets

Set the required secrets in Fly.io. Do not commit real values.

```bash
fly secrets set \
  GOOGLE_CLIENT_ID="your_client_id.apps.googleusercontent.com" \
  GOOGLE_CLIENT_SECRET="your_client_secret" \
  ENCRYPTION_KEY="your_fernet_key" \
  DATABASE_URL="sqlite:///./calendar.db" \
  PUBLIC_BASE_URL="https://<your-fly-app>.fly.dev"
```

Generate a Fernet key locally with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For production-like use, replace the SQLite `DATABASE_URL` with durable managed storage. Keep `ENCRYPTION_KEY` stable across deployments so stored refresh tokens remain decryptable.

## 4. Configure Google OAuth for Fly.io

In Google Cloud Console, open the OAuth 2.0 Web application client and add this authorized redirect URI:

```text
https://<your-fly-app>.fly.dev/oauth/callback
```

If you set `PUBLIC_BASE_URL=https://<your-fly-app>.fly.dev`, the app derives the callback as `${PUBLIC_BASE_URL}/oauth/callback`. If you set `GOOGLE_REDIRECT_URI`, make sure it exactly matches the value registered in Google Cloud.

Keep the local development redirect URI too if you still run the app locally:

```text
http://127.0.0.1:8000/oauth/callback
```

## 5. Deploy manually

Deploy from the repository root:

```bash
fly deploy
```

Fly.io uses `fly.toml` for the app name and service configuration. You can deploy the same source tree to another existing app with:

```bash
fly deploy -a <other-fly-app-name>
```

## 6. Optional GitHub Actions deployment

The workflow in `.github/workflows/deploy-fly.yml` deploys on pushes to `main` and can also be run manually.

Before enabling it:

1. Create a deploy token locally:

```bash
fly tokens create deploy -x 999999h
```

2. Copy the whole token value, including the `FlyV1` prefix.
3. Add it as a GitHub Actions repository secret named `FLY_API_TOKEN`.
4. Confirm `fly.toml` contains the correct Fly app name.

The workflow checks out the repository, installs `flyctl`, and runs:

```bash
flyctl deploy --remote-only
```

## 7. Database guidance

The prototype defaults to local SQLite for development:

```env
DATABASE_URL=sqlite:///./calendar.db
```

Do not rely on the Fly Machine filesystem for data you need to keep. For hosted use, set `DATABASE_URL` to a durable managed database connection string before storing real calendar tokens.

The current app still has a prototype schema and no migrations. Treat Fly.io deployment as a hosting path, not yet a production-hardening milestone.

## 8. Verify the deployment

After deployment completes, open:

```text
https://<your-fly-app>.fly.dev/api/health
```

Expected response:

```json
{"status":"healthy"}
```

Then open the frontend:

```text
https://<your-fly-app>.fly.dev/
```

## 9. Troubleshooting

- **OAuth redirect mismatch**: confirm `PUBLIC_BASE_URL` or `GOOGLE_REDIRECT_URI` matches the Google Cloud authorized redirect URI exactly.
- **No open port or unhealthy service**: confirm the Docker command starts `uvicorn`, binds `0.0.0.0`, and uses Fly.io internal port `8080` (or `$PORT` when provided).
- **Token decryption failures after redeploy**: confirm `ENCRYPTION_KEY` did not change.
- **Lost connected accounts**: confirm `DATABASE_URL` points to durable hosted storage, not the Machine filesystem.
- **Wrong app deployed**: confirm the `app` value in `fly.toml`, or deploy with `fly deploy -a <app-name>`.
