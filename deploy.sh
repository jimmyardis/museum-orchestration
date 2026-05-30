#!/usr/bin/env bash
# Museum Orchestration — Railway deploy script
# Run once after: railway login
set -e

PROJECT_ID="2bf7b805-0f0e-47fd-bb4d-d9b0d8cba403"
ENV_ID="4af3086a-953d-4ffb-ab0a-6c67b149a2f5"
SERVICE="museum-orchestration"
REPO="jimmyardis/museum-orchestration"

echo "🚂 Linking to giving-expression project..."
railway link --project "$PROJECT_ID" --environment "$ENV_ID"

echo "📦 Creating service and connecting repo..."
railway add --service "$SERVICE" --repo "$REPO"

echo "🔐 Setting environment variables..."
railway variables --service "$SERVICE" set \
  MUSEUM_ROOT=/app \
  PINECONE_API_KEY="$(grep PINECONE_API_KEY .env | cut -d= -f2)" \
  PINECONE_HOST="$(grep ^PINECONE_HOST .env | cut -d= -f2)" \
  PINECONE_INDEX=museum-of-minds \
  VOYAGE_API_KEY="$(grep VOYAGE_API_KEY .env | cut -d= -f2)" \
  ANTHROPIC_API_KEY="$(grep ANTHROPIC_API_KEY .env | cut -d= -f2)" \
  ELEVENLABS_API_KEY="$(grep ELEVENLABS_API_KEY .env | cut -d= -f2)" \
  GITHUB_TOKEN="$(grep GITHUB_TOKEN .env | cut -d= -f2)" \
  GITHUB_USERNAME=jimmyardis \
  MUSEUM_REPO=jimmyardis/museum-of-minds \
  RAILWAY_TOKEN=95cc9720-b8f8-4783-ae5a-e0d37bcb0917 \
  RAILWAY_PROJECT_ID="$PROJECT_ID" \
  RAILWAY_ENVIRONMENT_ID="$ENV_ID" \
  RAILWAY_SOURCE_REPO=jimmyardis/jane-jacobs-bot \
  PORT=8080

echo "🚀 Deploying..."
railway up --service "$SERVICE" --detach

echo "✅ Done. Dashboard will be live at:"
railway service status --service "$SERVICE" 2>/dev/null | grep url || echo "  check Railway dashboard for URL"
