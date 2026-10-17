#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/show_tell"
S6="/package/admin/s6/command"
BRANCH="main"

echo "===== HAT CONVERSE DEPLOYMENT ====="

cd "$APP_DIR"

# 1. Ensure we're on the correct branch
if [ "$(git branch --show-current)" != "$BRANCH" ]; then
    echo "ERROR: Switch to the main branch first"
    exit 1
fi

# 2. Protect local modifications
if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: Uncommitted changes found"
    git status --short
    exit 1
fi

# 3. Fetch the latest code
echo "Fetching code..."
git fetch origin "$BRANCH"
git merge --ff-only "origin/$BRANCH"

# 4. Backend dependencies and tests
echo "Testing FastAPI..."
cd "$APP_DIR/api"

./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pytest tests/

# 5. Build frontend
echo "Building React..."
cd "$APP_DIR/web_app"

npm ci
npm run build

# 6. Check supervisor
echo "Checking s6..."
"$S6/s6-svok" \
    "$APP_DIR/s6-scandir/show-tell-api"

# 7. Restart backend
echo "Restarting FastAPI..."
"$S6/s6-svc" -t \
    "$APP_DIR/s6-scandir/show-tell-api"

# 8. Verify backend is ready
echo "Checking backend health..."

healthy=0

for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS \
        http://127.0.0.1:8000/health > /dev/null; then
        healthy=1
        break
    fi
    sleep 2
done

if [ "$healthy" -ne 1 ]; then
    echo "ERROR: Backend health check failed"
    exit 1
fi

# 9. Verify Apache
curl -fsS \
    http://127.0.0.1:8080/ > /dev/null

echo "===== DEPLOYMENT SUCCESSFUL ====="
git -C "$APP_DIR" rev-parse --short HEAD
