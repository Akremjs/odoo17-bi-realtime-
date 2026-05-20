#!/usr/bin/env bash
# Push branch 17.0 to GitHub repo BI-Realtime (Odoo Apps).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REPO_URL="${ODOO_APPS_REPO:-git@github.com:Akremjs/BI-Realtime.git}"
BRANCH="${ODOO_APPS_BRANCH:-17.0}"

cd "$PROJECT_DIR"

if ! git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    echo "❌ Branche locale $BRANCH introuvable."
    exit 1
fi

git checkout "$BRANCH"

if git remote get-url apps &>/dev/null; then
    git remote set-url apps "$REPO_URL"
else
    git remote add apps "$REPO_URL"
fi

echo "📤 Push $BRANCH → $REPO_URL"
git push -u apps "$BRANCH"

echo ""
echo "✅ OK — URL Odoo Apps :"
echo "   ssh://git@github.com/Akremjs/BI-Realtime.git#$BRANCH"
echo ""
echo "Vérifiez : https://github.com/Akremjs/BI-Realtime/tree/$BRANCH"
echo "Structure : bi_realtime/ à la racine"
