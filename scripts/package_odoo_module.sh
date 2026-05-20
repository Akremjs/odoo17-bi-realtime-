#!/usr/bin/env bash
# Build dist/bi_realtime.zip for Odoo Apps upload.
# Usage: bash scripts/package_odoo_module.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="${PROJECT_DIR}/dist"
ZIP_PATH="${DIST_DIR}/bi_realtime.zip"
REGENERATE_ASSETS="${REGENERATE_ASSETS:-1}"

# Prefer module at project root (latest); fallback to odoo-module/
if [ -d "${PROJECT_DIR}/bi_realtime" ]; then
    MODULE_SRC="${PROJECT_DIR}/bi_realtime"
elif [ -d "${PROJECT_DIR}/odoo-module/bi_realtime" ]; then
    MODULE_SRC="${PROJECT_DIR}/odoo-module/bi_realtime"
else
    echo "❌ Module introuvable (bi_realtime/ ou odoo-module/bi_realtime/)"
    exit 1
fi

echo "📦 Packaging BI Realtime"
echo "   Source : $MODULE_SRC"

if [ "$REGENERATE_ASSETS" = "1" ] && [ -f "${MODULE_SRC}/static/description/render_icon.py" ]; then
    echo "🎨 Regénération icon.png"
    (cd "${MODULE_SRC}/static/description" && python3 render_icon.py)
    if [ "${REGENERATE_BANNER:-0}" = "1" ]; then
        echo "🎨 Regénération banner.png (script)"
        (cd "${MODULE_SRC}/static/description" && python3 render_banner.py)
    fi
fi

MANIFEST="${MODULE_SRC}/__manifest__.py"
[ -f "$MANIFEST" ] || { echo "❌ __manifest__.py manquant"; exit 1; }
VERSION=$(grep -E "^[[:space:]]*'version'" "$MANIFEST" | head -1 | sed -E "s/.*'([^']+)'.*/\1/")
echo "   Version : ${VERSION:-?}"

for req in icon.png banner.png index.html screenshot_dashboard.png; do
    [ -f "${MODULE_SRC}/static/description/${req}" ] || {
        echo "❌ Fichier requis manquant : static/description/${req}"
        exit 1
    }
done

mkdir -p "$DIST_DIR"
STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT

rsync -a \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '*.pyo' \
    --exclude '.DS_Store' \
    --exclude '.env' \
    --exclude '.env.*' \
    --exclude '*.pem' \
    --exclude '*.key' \
    --exclude 'render_icon.py' \
    --exclude 'render_banner.py' \
    "${MODULE_SRC}/" "${STAGING}/bi_realtime/"

FILE_COUNT=$(find "${STAGING}/bi_realtime" -type f | wc -l)
echo "   Fichiers : $FILE_COUNT"
[ "$FILE_COUNT" -gt 30 ] || { echo "❌ Archive trop petite"; exit 1; }

rm -f "$ZIP_PATH"
(
    cd "$STAGING"
    zip -qr "$ZIP_PATH" bi_realtime
)

echo ""
echo "✅ ZIP créé : $ZIP_PATH ($(du -h "$ZIP_PATH" | cut -f1))"
echo ""
echo "Prochaine étape :"
echo "  https://apps.odoo.com/apps/upload"
echo "  → téléverser dist/bi_realtime.zip (version ${VERSION})"
