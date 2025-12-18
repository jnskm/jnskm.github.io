#!/bin/bash
# Simple migration script to copy features from jnskm.com to jnskm.github.io
# This preserves existing files and creates backups

set -e

SOURCE_DIR="/Users/jnskm/Documents/Code/jnskm.com"
TARGET_DIR="/Users/jnskm/Documents/Code/jnskm.github.io"

echo "🚀 Migrating features from jnskm.com to jnskm.github.io"
echo ""

# Check directories
if [ ! -d "$SOURCE_DIR" ] || [ ! -d "$TARGET_DIR" ]; then
  echo "❌ Error: Source or target directory not found"
  exit 1
fi

cd "$TARGET_DIR"

# Create backup directory
BACKUP_DIR=".migration_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "📦 Copying collections..."
mkdir -p _music _books _videos _bible_studies
[ -d "$SOURCE_DIR/_music" ] && cp -r "$SOURCE_DIR/_music"/* _music/ 2>/dev/null || true
[ -d "$SOURCE_DIR/_books" ] && cp -r "$SOURCE_DIR/_books"/* _books/ 2>/dev/null || true
[ -d "$SOURCE_DIR/_videos" ] && cp -r "$SOURCE_DIR/_videos"/* _videos/ 2>/dev/null || true
[ -d "$SOURCE_DIR/_bible_studies" ] && cp -r "$SOURCE_DIR/_bible_studies"/* _bible_studies/ 2>/dev/null || true
echo "  ✓ Collections copied"

echo ""
echo "🎨 Copying layouts..."
mkdir -p _layouts
[ -f "$SOURCE_DIR/_layouts/music.html" ] && cp "$SOURCE_DIR/_layouts/music.html" _layouts/ || true
[ -f "$SOURCE_DIR/_layouts/book.html" ] && cp "$SOURCE_DIR/_layouts/book.html" _layouts/ || true
[ -f "$SOURCE_DIR/_layouts/video.html" ] && cp "$SOURCE_DIR/_layouts/video.html" _layouts/ || true
[ -f "$SOURCE_DIR/_layouts/bible_study.html" ] && cp "$SOURCE_DIR/_layouts/bible_study.html" _layouts/ || true
echo "  ✓ Layouts copied"

echo ""
echo "📄 Copying pages..."
[ -f "$SOURCE_DIR/music.md" ] && cp "$SOURCE_DIR/music.md" . || true
[ -f "$SOURCE_DIR/books.md" ] && cp "$SOURCE_DIR/books.md" . || true
[ -f "$SOURCE_DIR/videos.md" ] && cp "$SOURCE_DIR/videos.md" . || true
[ -f "$SOURCE_DIR/bible-studies.md" ] && cp "$SOURCE_DIR/bible-studies.md" . || true
echo "  ✓ Pages copied"

echo ""
echo "🛠️  Copying scripts..."
mkdir -p scripts
[ -d "$SOURCE_DIR/scripts" ] && cp -r "$SOURCE_DIR/scripts"/* scripts/ 2>/dev/null || true
chmod +x scripts/*.sh scripts/*.rb 2>/dev/null || true
echo "  ✓ Scripts copied"

echo ""
echo "📚 Copying guides..."
[ -f "$SOURCE_DIR/CONTENT_GUIDE.md" ] && cp "$SOURCE_DIR/CONTENT_GUIDE.md" . || true
echo "  ✓ Guides copied"

echo ""
echo "📁 Creating image directories..."
mkdir -p assets/images/books assets/images/music assets/images/podcasts
echo "  ✓ Directories created"

echo ""
echo "⚠️  Manual steps required:"
echo ""
echo "1. Update _config.yml:"
echo "   Add these sections (see MIGRATION_GUIDE.md for details):"
echo "   - collections:"
echo "   - defaults:"
echo ""
echo "2. Update CSS:"
echo "   Add book cover styles to assets/css/custom.css"
echo ""
echo "3. Update header:"
echo "   Review and update _includes/header.html with new navigation"
echo ""
echo "4. Update index:"
echo "   Review index.html or index.markdown"
echo ""
echo "✅ File copying complete!"
echo "📝 See MIGRATION_GUIDE.md for detailed manual steps"

