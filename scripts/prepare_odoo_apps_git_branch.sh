#!/bin/bash
# Crée/met à jour la branche Git 17.0 pour Odoo Apps :
#   bi_realtime/ à la RACINE du dépôt (exigence store)
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BRANCH="${ODOO_APPS_BRANCH:-17.0}"
if [ -d "${PROJECT_DIR}/bi_realtime" ]; then
    MODULE_SRC="${PROJECT_DIR}/bi_realtime"
elif [ -d "${PROJECT_DIR}/odoo-module/bi_realtime" ]; then
    MODULE_SRC="${PROJECT_DIR}/odoo-module/bi_realtime"
fi
TMP_COPY=$(mktemp -d)

cd "$PROJECT_DIR"

# Toujours partir de main (projet complet)
if git show-ref --verify --quiet refs/heads/main; then
    git checkout main
elif git show-ref --verify --quiet refs/heads/master; then
    git checkout master
fi

[ -d "$MODULE_SRC" ] || { echo "❌ Module introuvable : $MODULE_SRC"; exit 1; }

echo "📦 Branche Odoo Apps : $BRANCH"
echo "   Copie sécurisée du module vers $TMP_COPY"
rsync -rlpt \
    --no-owner --no-group \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    "$MODULE_SRC/" "$TMP_COPY/"

CURRENT=$(git branch --show-current)
FILE_COUNT=$(find "$TMP_COPY" -type f | wc -l)
echo "   Fichiers copiés : $FILE_COUNT"
[ "$FILE_COUNT" -gt 20 ] || { echo "❌ Copie incomplète (< 20 fichiers)"; exit 1; }

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git branch -D "$BRANCH"
fi

git checkout --orphan "$BRANCH"
git rm -rf . 2>/dev/null || true

mkdir -p bi_realtime
rsync -rlpt --no-owner --no-group "$TMP_COPY/" bi_realtime/
rm -rf "$TMP_COPY"

cat > README.md <<'EOF'
# BI en temps réel — Odoo 17

Odoo module `bi_realtime` for [Odoo Apps](https://apps.odoo.com).

Author: **AKREM.KHELIFI**
https://github.com/Akremjs/BI-Realtime
EOF

git add bi_realtime README.md
ADDED=$(git diff --cached --name-only | wc -l)
echo "   Fichiers indexés pour commit : $ADDED"
[ "$ADDED" -gt 20 ] || { echo "❌ Trop peu de fichiers stagés"; git status; exit 1; }

git commit -m "Odoo Apps branch $BRANCH: full bi_realtime module at repository root"

echo ""
echo "✅ Branche $BRANCH prête ($(git ls-tree -r --name-only HEAD | wc -l) fichiers)."
echo ""
echo "Pousser (remplace la branche cassée sur GitHub) :"
echo "  git push --force -u apps $BRANCH"
echo ""
echo "URL Odoo Apps :"
echo "  ssh://git@github.com/Akremjs/BI-Realtime.git#$BRANCH"
echo ""
echo "Revenir au projet complet :"
echo "  git checkout main"
