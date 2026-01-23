#!/bin/bash
# Download Hebrew font for PDF generation (Noto Sans Hebrew - OFL license)
# This script is called during Render build process

set -e  # Exit on error

echo "🔤 Checking Hebrew font for PDF generation..."

# Determine the script location
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create fonts directory if not exists (in the same dir as this script)
mkdir -p "$SCRIPT_DIR/fonts"

FONT_PATH="$SCRIPT_DIR/fonts/NotoSansHebrew-Regular.ttf"

# Check if font already exists in repo (committed)
if [ -f "$FONT_PATH" ]; then
    FILE_SIZE=$(stat -c%s "$FONT_PATH" 2>/dev/null || stat -f%z "$FONT_PATH" 2>/dev/null || echo "unknown")
    echo "✅ Hebrew font already exists in repo ($FILE_SIZE bytes)"
    echo "   Location: $FONT_PATH"
    chmod 644 "$FONT_PATH"
    exit 0
fi

# Download Noto Sans Hebrew Regular from Google Fonts GitHub (updated URL)
echo "⬇️  Downloading Hebrew font..."
FONT_URLS=(
    "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansHebrew/NotoSansHebrew-Regular.ttf"
    "https://github.com/notofonts/noto-fonts/raw/main/hinted/ttf/NotoSansHebrew/NotoSansHebrew-Regular.ttf"
    "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSansHebrew/NotoSansHebrew-Regular.ttf"
)

for FONT_URL in "${FONT_URLS[@]}"; do
    echo "   Trying: $FONT_URL"
    if curl -L -s -o "$FONT_PATH" "$FONT_URL" && [ -f "$FONT_PATH" ] && [ -s "$FONT_PATH" ]; then
        FILE_SIZE=$(stat -c%s "$FONT_PATH" 2>/dev/null || stat -f%z "$FONT_PATH" 2>/dev/null || echo "unknown")
        if [ "$FILE_SIZE" -gt 1000 ]; then
            echo "✅ Hebrew font downloaded successfully ($FILE_SIZE bytes)"
            chmod 644 "$FONT_PATH"
            exit 0
        fi
    fi
    rm -f "$FONT_PATH"  # Remove failed download
done

echo "⚠️  Could not download Hebrew font - will use system fallback"
exit 0  # Don't fail build, fallback fonts may work
