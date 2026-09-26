# PostPilot - AI-Powered Instagram Content Automation

PostPilot is a full-stack content studio that turns a creator's niche and topic into branded Instagram posts, captions, hashtags, and Reels. Users can review and edit generated media before publishing it through the official Instagram API.

> For an interview-ready technical walkthrough and CV wording, open [PROJECT_INTERVIEW_GUIDE.html](PROJECT_INTERVIEW_GUIDE.html).

## What it does

- Generates post copy, hashtags, visual prompts, structured carousels, comparison posts, quote cards, and short-form Reels.
- Supports configurable text and image providers: Gemini, Anthropic, OpenAI, Cloudflare Workers AI, Pexels, and local/template fallbacks.
- Applies user-specific niche, content pillars, brand handle, accent color, visual style, and templates.
- Gives creators a React dashboard to generate, review, edit, approve, reject, regenerate, download, and organize content.
- Renders branded images with Pillow and Reels with ffmpeg, Edge TTS narration, word-timed captions, and generated music beds.
- Uses Google sign-in, JWT-authenticated APIs, user-scoped data, encrypted Instagram credentials, and OAuth state validation.
- Uploads media to Cloudinary when configured, enabling durable delivery and Instagram publishing from a public URL.
- Supports manual, semi-automatic, and automatic publishing modes for connected professional Instagram accounts.

## Architecture

```text
React + Vite dashboard
        |
        v
FastAPI REST API (auth, validation, jobs, orchestration)
        |
        +--> AI providers --> structured copy / visual prompts
        +--> Pillow + ffmpeg --> branded images / Reels
        +--> SQLite (local) or PostgreSQL (production)
        +--> Cloudinary --> public media URLs
        +--> Instagram API --> publish approved media
```

## Tech stack

| Area | Technology |
| --- | --- |
| Frontend | React 18, Vite, React Router, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic, httpx |
| AI | Gemini, Claude, OpenAI, Cloudflare Workers AI, structured JSON output |
| Media | Pillow, NumPy, ffmpeg, Edge TTS, Cloudinary |
| Data & auth | PostgreSQL, SQLite, Google OAuth, JWT, cryptography |
| Deployment | Docker, Vercel-ready frontend, Render-ready backend |

## Local setup

### 1. Start the API

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`. With no AI credentials configured, the project can still use its local/template fallback paths.

### 2. Start the dashboard

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (usually `http://localhost:5173`). For local development, use the development login or set matching Google OAuth configuration in `backend/.env` and `frontend/.env.local`.

## Configuration

The environment templates list the available settings:

- [`backend/.env.example`](backend/.env.example) - database, authentication, providers, Cloudinary, Instagram, scheduler, and rate-limit settings.
- [`frontend/.env.example`](frontend/.env.example) - API base URL and Google OAuth client ID.

Never commit real `.env` files or generated runtime data. The `.gitignore` already excludes them.

## Production notes

- The backend Docker image installs ffmpeg because the Reel renderer depends on it.
- Set `DATABASE_URL`, a strong `JWT_SECRET`, `GOOGLE_CLIENT_ID`, and `FRONTEND_ORIGINS` before running in production; the API refuses unsafe production configuration at startup.
- Configure Cloudinary before using Instagram publishing because Meta must fetch media from a public URL.
- Use an external scheduler to call the secured `/api/cron/run` endpoint periodically on hosts that may sleep.

## Scope for future work

- Move in-process render jobs to a durable queue such as Celery/RQ with Redis.
- Add automated test coverage and provider observability.
- Add a content calendar, analytics feedback loop, and additional moderation safeguards.
