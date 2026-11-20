# Stokivo — inventory and sales management

Stokivo is a small store management app built with Python, FastAPI, and a vanilla HTML/CSS/JavaScript frontend. It covers product management, stock tracking, low-stock alerts, sales recording, revenue and profit summaries, and daily/monthly reports.

## Run locally

1. Use Python 3.11 or newer.
2. Create and activate a virtual environment.
3. Install dependencies:

   pip install -r requirements.txt

4. Start the app:

   uvicorn index:app --reload

5. Open http://127.0.0.1:8000.

Local development creates stokivo.db beside the project. The database is initialized automatically on the first run.

## Deploy to Vercel

1. Push this folder to a Git repository and import it in Vercel.
2. Add a Postgres database through the Vercel Marketplace (for example, Neon or Supabase).
3. Set DATABASE_URL in Vercel to the provider's pooled connection URL, then redeploy.
4. Vercel detects the FastAPI app exported by index.py and serves the frontend from public/.

See Vercel's [FastAPI deployment guide](https://vercel.com/docs/frameworks/backend/fastapi) and [Marketplace storage guide](https://vercel.com/docs/marketplace-storage) for current setup details.

SQLite is intended for local development. Vercel functions do not provide durable local file storage, so deployments require DATABASE_URL backed by Postgres.

## Main API routes

- GET /api/dashboard — overview cards, weekly trend, stock alerts, and recent sales.
- GET /api/products?search= — product catalogue with optional search.
- POST /api/products — add a product.
- PUT /api/products/{id} — update a product.
- DELETE /api/products/{id} — archive a product while retaining its sales history.
- POST /api/sales — record a sale and decrement stock in one transaction.
- GET /api/sales?limit=50 — recent sales.
- GET /api/reports?period=today|week|month|year — totals, trend, and top products.

FastAPI's interactive API reference is available at /docs.

## Project layout

- backend/domain.py — Product, Inventory, Sale, Store, and SalesAnalytics.
- backend/database.py — SQLite and Postgres connection/schema support.
- backend/app.py — FastAPI routes and input validation.
- index.py — Vercel ASGI entry point.
- public/ — responsive single-page frontend.
