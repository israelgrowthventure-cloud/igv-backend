#!/bin/bash
# Download Hebrew font for PDF generation (Noto Sans Hebrew - OFL license)
# This script is called during Render build process

set -e  # Exit on error

echo "🔤 Downloading Hebrew font for PDF generation..."

# Create fonts directory if not exists
mkdir -p backend/fonts

# Download Noto Sans Hebrew Regular from Google Fonts GitHub
FONT_URL="https://github.com/notofonts/noto-fonts/raw/main/hinted/ttf/NotoSansHebrew/NotoSansHebrew-Regular.ttf"
FONT_PATH="backend/fonts/NotoSansHebrew-Regular.ttf"

# Download font
if [ ! -f "$FONT_PATH" ]; then
    echo "⬇️  Downloading from: $FONT_URL"
    curl -L -o "$FONT_PATH" "$FONT_URL"
    
    if [ -f "$FONT_PATH" ]; then
        FILE_SIZE=$(stat -f%z "$FONT_PATH" 2>/dev/null || stat -c%s "$FONT_PATH" 2>/dev/null || echo "unknown")
        echo "✅ Hebrew font downloaded successfully ($FILE_SIZE bytes)"
        echo "   Location: $FONT_PATH"
    else
        echo "❌ Failed to download Hebrew font"
        exit 1
    fi
else
    echo "✅ Hebrew font already exists"
fi

# Set permissions
chmod 644 "$FONT_PATH"

echo "🎉 Font installation complete!"
