# AlumniHuddle AI Chat - Deployment Guide

This guide covers deploying the AlumniHuddle AI Chat service to Railway.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Railway                                  │
│  ┌─────────────────────┐    ┌─────────────────────────┐        │
│  │   open-webui        │    │   pipelines             │        │
│  │   (public)          │───▶│   (internal)            │        │
│  │   chat.alumnihuddle │    │   Anthropic Claude      │        │
│  └─────────────────────┘    └─────────────────────────┘        │
│            │                                                     │
└────────────┼─────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Supabase (shared)                             │
│  - PostgreSQL database (huddles, mentors, users, chats)         │
│  - Auth (shared with main Vercel app for SSO)                   │
└─────────────────────────────────────────────────────────────────┘
             ▲
             │
┌─────────────────────────────────────────────────────────────────┐
│                    Vercel (main app)                             │
│  - alumnihuddle.vercel.app                                      │
│  - Links to chat.alumnihuddle.com/{huddle-slug}                │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. Railway account (https://railway.app)
2. Your Supabase credentials (already configured)
3. Anthropic API key
4. This repository pushed to GitHub

## Step 1: Prepare the Repository

Make sure your repository includes:
- `docker-compose.prod.yaml` (production Docker configuration)
- `.env.example` (template for environment variables)
- All custom backend files in `backend/open_webui/`
- Custom static files in `custom-static/`

## Step 2: Create Railway Project

1. Go to https://railway.app and sign in
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Connect your GitHub account and select this repository

## Step 3: Configure Services

Railway will detect the `docker-compose.prod.yaml`. You need two services:

### Service 1: Pipelines (Internal)
- This runs the Anthropic Claude pipeline
- Should NOT be publicly accessible
- Environment variables:
  - `ANTHROPIC_API_KEY`: Your Anthropic API key
  - `PIPELINES_API_KEY`: Internal API key (generate a secure random string)

### Service 2: Open-WebUI (Public)
- This is the main web application
- Should be publicly accessible
- Environment variables (copy from `.env.example` and fill in):
  ```
  DATABASE_URL=postgresql://...
  SUPABASE_URL=https://...
  SUPABASE_ANON_KEY=...
  SUPABASE_SERVICE_KEY=...
  WEBUI_SECRET_KEY=<generate with: openssl rand -hex 32>
  ANTHROPIC_API_KEY=...
  PIPELINES_API_KEY=<same as pipelines service>
  BASE_DOMAIN=alumnihuddle.com
  CORS_ALLOW_ORIGIN=https://alumnihuddle.vercel.app
  ```

## Step 4: Set Up Networking

1. In Railway, go to the open-webui service settings
2. Under "Networking", generate a domain or add custom domain
3. For custom domain `chat.alumnihuddle.com`:
   - Add the domain in Railway
   - Configure DNS CNAME record pointing to Railway's provided target

## Step 5: Configure Environment Variables in Railway

For each service, go to "Variables" and add the required environment variables.

### Pipelines Service Variables:
```
ANTHROPIC_API_KEY=sk-ant-api03-...
PIPELINES_URLS=https://raw.githubusercontent.com/open-webui/pipelines/main/examples/pipelines/providers/anthropic_manifold_pipeline.py
PIPELINES_API_KEY=<your-secure-key>
```

### Open-WebUI Service Variables:
```
DATABASE_URL=postgresql://postgres.aftfwjizbyswzkainwqm:...@aws-1-us-east-1.pooler.supabase.com:5432/postgres
SUPABASE_URL=https://aftfwjizbyswzkainwqm.supabase.co
SUPABASE_ANON_KEY=<your-anon-key>
SUPABASE_SERVICE_KEY=<your-service-key>
WEBUI_SECRET_KEY=<generate-secure-key>
ANTHROPIC_API_KEY=sk-ant-api03-...
PIPELINES_API_KEY=<same-as-pipelines>
BASE_DOMAIN=alumnihuddle.com
CORS_ALLOW_ORIGIN=https://alumnihuddle.vercel.app
PORT=8080
```

## Step 6: Deploy

1. Railway will automatically deploy when you push to GitHub
2. Monitor the deployment logs for any errors
3. Once deployed, test the health endpoint: `https://your-domain/health`

## Step 7: Verify Deployment

1. Visit your Railway URL
2. Test login functionality
3. Test chat with a huddle subdomain header or path
4. Verify mentor context is being injected

## DNS Configuration (when custom domain is ready)

Add these DNS records to your domain provider:

```
Type: CNAME
Name: chat
Value: <railway-provided-target>
TTL: 3600
```

## Troubleshooting

### Database Connection Issues
- Ensure you're using the Session Pooler URL (IPv4 compatible)
- Check that DATABASE_URL is properly URL-encoded (special characters)

### CORS Errors
- Add your Vercel domain to CORS_ALLOW_ORIGIN
- Include both http and https if testing locally

### Model Not Found
- Ensure huddle models are created in the database
- Check that the pipelines service is healthy

### Authentication Issues
- Verify WEBUI_SECRET_KEY is the same across deployments
- Check Supabase JWT settings match

## SSO Integration with Main App

See `SSO_INTEGRATION.md` for details on sharing authentication between the main Vercel app and this chat service.
