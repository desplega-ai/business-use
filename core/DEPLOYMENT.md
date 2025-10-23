# Deployment Guide

This guide covers deploying Business-Use Core to various platforms.

## Vercel Deployment

### Quick Start

1. **Install Vercel CLI:**
   ```bash
   npm i -g vercel
   ```

2. **Login to Vercel:**
   ```bash
   vercel login
   ```

3. **Deploy:**
   ```bash
   cd core
   vercel
   ```

### Configuration

The `main.py` file exports the FastAPI app for Vercel's automatic deployment.

#### Environment Variables

Set these in Vercel Dashboard (Settings → Environment Variables):

**Required:**
- `BUSINESS_USE_API_KEY` - Your API authentication key

**Optional:**
- `BUSINESS_USE_DATABASE_URL` - PostgreSQL database URL (e.g., Neon: `postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/dbname`)
- `BUSINESS_USE_DATABASE_PATH` - Local file path (default: `/tmp/db.sqlite`)
- `BUSINESS_USE_LOG_LEVEL` - Logging level (default: `info`)
- `BUSINESS_USE_ENV` - Environment name (default: `production`)
- `BUSINESS_USE_DEBUG` - Enable debug mode (default: `false`)

#### Setting Secrets via CLI

```bash
# Add secrets (encrypted environment variables)
vercel secrets add business_use_api_key "your_secret_key_here"
vercel secrets add business_use_database_url "postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/dbname"

# Secrets are referenced in vercel.json with @ prefix
```

### Database Setup (PostgreSQL with Neon)

1. **Create Neon database:**
   - Visit https://neon.tech
   - Create a new project
   - Copy the connection string (postgresql://...)

2. **Initialize database schema:**

   ```bash
   # Set environment variable
   export BUSINESS_USE_DATABASE_URL="postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/dbname"

   # Run migrations
   uv run business-use db migrate
   ```

3. **Set environment variables in Vercel:**
   - Go to Vercel Dashboard → Your Project → Settings → Environment Variables
   - Add `BUSINESS_USE_API_KEY` and `BUSINESS_USE_DATABASE_URL`

**Important Notes:**
- For local development, omit `BUSINESS_USE_DATABASE_URL` to use SQLite
- For production, set `BUSINESS_USE_DATABASE_URL` to your Neon Postgres URL
- Migrations work with both SQLite (local) and Postgres (production)

### Vercel Configuration File

The included `vercel.json` configures:
- Python runtime via `@vercel/python`
- Route all requests to `main.py`
- Environment variable references

### Deployment Flow

```bash
# 1. Make changes
git add .
git commit -m "Update API"

# 2. Deploy to preview (automatic)
git push origin feature-branch

# 3. Deploy to production (automatic)
git push origin main

# Or deploy manually:
vercel --prod
```

### Troubleshooting

**Import errors:**
- Ensure `main.py` is in the root of your deployment
- Check that `src/` directory structure is preserved

**Database connection issues:**
- Verify PostgreSQL connection URL is correct
- For serverless (Vercel), use Neon or other serverless Postgres
- For local dev, SQLite will be used automatically if DATABASE_URL is not set
- Ensure migrations were run before deployment

**API key authentication:**
- Verify `BUSINESS_USE_API_KEY` is set correctly
- Test with: `curl -H "X-Api-Key: your_key" https://your-app.vercel.app/health`

### Limitations

- **Cold starts:** Serverless functions may have cold start latency
- **Execution timeout:** Max 10 seconds on Hobby plan, 60s on Pro
- **Database:** Use Neon or other serverless Postgres for persistence (ephemeral filesystem)
- **Package size:** Must be under 250MB

## Railway Deployment

### Quick Start

1. **Install Railway CLI:**
   ```bash
   npm i -g @railway/cli
   ```

2. **Login:**
   ```bash
   railway login
   ```

3. **Initialize project:**
   ```bash
   cd core
   railway init
   ```

4. **Set environment variables:**
   ```bash
   railway variables set BUSINESS_USE_API_KEY="your_key"
   railway variables set BUSINESS_USE_DATABASE_URL="postgresql://..."
   ```

5. **Deploy:**
   ```bash
   railway up
   ```

### Start Command

Railway will detect Python and use:
```bash
business-use db migrate && business-use prod
```

Or set custom start command in `railway.toml`:
```toml
[deploy]
startCommand = "uv run business-use db migrate && uv run business-use prod"
```

## Render Deployment

### Quick Start

1. **Create `render.yaml`:**
   ```yaml
   services:
     - type: web
       name: business-use-core
       env: python
       buildCommand: "pip install uv && uv sync"
       startCommand: "uv run business-use db migrate && uv run business-use prod"
       envVars:
         - key: BUSINESS_USE_API_KEY
           sync: false
         - key: BUSINESS_USE_DATABASE_URL
           sync: false
   ```

2. **Connect repository in Render Dashboard**

3. **Set environment variables in Render Dashboard**

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.14-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY main.py .

# Install dependencies
RUN uv sync --frozen

# Run migrations and start server
CMD ["sh", "-c", "uv run business-use db migrate && uv run business-use prod"]
```

### Build and run:

```bash
docker build -t business-use-core .

docker run -p 8000:8000 \
  -e BUSINESS_USE_API_KEY="your_key" \
  -e BUSINESS_USE_DATABASE_URL="postgresql://..." \
  business-use-core
```

## Environment Variable Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BUSINESS_USE_API_KEY` | Yes | - | API authentication key |
| `BUSINESS_USE_DATABASE_URL` | For Postgres | - | PostgreSQL database URL (e.g., Neon) |
| `BUSINESS_USE_DATABASE_PATH` | No | Platform-specific | Local SQLite file path (used when DATABASE_URL not set) |
| `BUSINESS_USE_LOG_LEVEL` | No | `info` | Logging level |
| `BUSINESS_USE_ENV` | No | `production` | Environment name |
| `BUSINESS_USE_DEBUG` | No | `false` | Enable debug mode |

## Best Practices

1. **Always use environment variables** for secrets in production
2. **Run migrations before deployment** or as part of startup command
3. **Use Neon or serverless Postgres** for persistent storage in serverless environments
4. **Use SQLite locally** for development (no DATABASE_URL needed)
5. **Set appropriate timeouts** for long-running flow evaluations
6. **Monitor cold starts** and consider keeping functions warm
7. **Use API keys** from environment, never commit to code

## Health Check

Test your deployment:

```bash
# Public health endpoint (no auth)
curl https://your-app.vercel.app/health

# Authenticated status endpoint
curl -H "X-Api-Key: your_key" https://your-app.vercel.app/v1/status
```
