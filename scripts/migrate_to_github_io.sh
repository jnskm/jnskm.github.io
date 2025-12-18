#!/bin/bash
# Script to migrate all new features from jnskm.com to jnskm.github.io
# This will copy collections, layouts, pages, scripts, and configurations

set -e  # Exit on error

SOURCE_DIR="/Users/jnskm/Documents/Code/jnskm.com"
TARGET_DIR="/Users/jnskm/Documents/Code/jnskm.github.io"

echo "🚀 Migrating features from jnskm.com to jnskm.github.io"
echo ""

# Check if directories exist
if [ ! -d "$SOURCE_DIR" ]; then
  echo "❌ Error: Source directory not found: $SOURCE_DIR"
  exit 1
fi

if [ ! -d "$TARGET_DIR" ]; then
  echo "❌ Error: Target directory not found: $TARGET_DIR"
  exit 1
fi

cd "$TARGET_DIR"

echo "📋 Files to be copied:"
echo "  - Collections: _music, _books, _videos, _bible_studies"
echo "  - Layouts: music.html, book.html, video.html, bible_study.html"
echo "  - Pages: music.md, books.md, videos.md, bible-studies.md"
echo "  - Scripts: scripts/ directory"
echo "  - Config: _config.yml updates"
echo "  - CSS: assets/css/custom.css updates"
echo "  - Header: _includes/header.html"
echo "  - Index: index.html"
echo "  - Templates and guides"
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Cancelled."
  exit 0
fi

echo ""
echo "📦 Copying collections..."
mkdir -p _music _books _videos _bible_studies
cp -r "$SOURCE_DIR/_music"/* _music/ 2>/dev/null || true
cp -r "$SOURCE_DIR/_books"/* _books/ 2>/dev/null || true
cp -r "$SOURCE_DIR/_videos"/* _videos/ 2>/dev/null || true
cp -r "$SOURCE_DIR/_bible_studies"/* _bible_studies/ 2>/dev/null || true
echo "  ✓ Collections copied"

echo ""
echo "🎨 Copying layouts..."
mkdir -p _layouts
cp "$SOURCE_DIR/_layouts/music.html" _layouts/ 2>/dev/null || true
cp "$SOURCE_DIR/_layouts/book.html" _layouts/ 2>/dev/null || true
cp "$SOURCE_DIR/_layouts/video.html" _layouts/ 2>/dev/null || true
cp "$SOURCE_DIR/_layouts/bible_study.html" _layouts/ 2>/dev/null || true
echo "  ✓ Layouts copied"

echo ""
echo "📄 Copying pages..."
cp "$SOURCE_DIR/music.md" . 2>/dev/null || true
cp "$SOURCE_DIR/books.md" . 2>/dev/null || true
cp "$SOURCE_DIR/videos.md" . 2>/dev/null || true
cp "$SOURCE_DIR/bible-studies.md" . 2>/dev/null || true
echo "  ✓ Pages copied"

echo ""
echo "🛠️  Copying scripts..."
mkdir -p scripts
cp -r "$SOURCE_DIR/scripts"/* scripts/ 2>/dev/null || true
chmod +x scripts/*.sh scripts/*.rb 2>/dev/null || true
echo "  ✓ Scripts copied"

echo ""
echo "⚙️  Updating _config.yml..."
# Backup existing config
cp _config.yml _config.yml.backup

# Read the source config to extract collections and defaults
python3 << 'PYTHON_SCRIPT'
import yaml
import sys

# Read source config
with open('/Users/jnskm/Documents/Code/jnskm.com/_config.yml', 'r') as f:
    source = yaml.safe_load(f)

# Read target config
with open('/Users/jnskm/Documents/Code/jnskm.github.io/_config.yml', 'r') as f:
    target = yaml.safe_load(f)

# Add collections if not present
if 'collections' not in target:
    target['collections'] = {}
if 'collections' in source:
    target['collections'].update(source['collections'])

# Add defaults if not present
if 'defaults' not in target:
    target['defaults'] = []
if 'defaults' in source:
    # Merge defaults, avoiding duplicates
    existing_paths = {(d.get('scope', {}).get('path'), d.get('scope', {}).get('type')) 
                      for d in target['defaults']}
    for default in source['defaults']:
        scope = default.get('scope', {})
        key = (scope.get('path'), scope.get('type'))
        if key not in existing_paths:
            target['defaults'].append(default)
            existing_paths.add(key)

# Write updated config
with open('/Users/jnskm/Documents/Code/jnskm.github.io/_config.yml', 'w') as f:
    yaml.dump(target, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

print("  ✓ Config updated")
PYTHON_SCRIPT

if [ $? -ne 0 ]; then
  echo "  ⚠️  Python script failed, manually updating config..."
  echo "  Please manually add collections and defaults from jnskm.com/_config.yml"
fi

echo ""
echo "🎨 Updating CSS..."
mkdir -p assets/css
# Merge CSS - append book-cover styles if not present
if ! grep -q "\.book-cover" assets/css/custom.css 2>/dev/null; then
  echo "" >> assets/css/custom.css
  echo "/* Book cover styles */" >> assets/css/custom.css
  grep -A 20 "\.book-cover" "$SOURCE_DIR/assets/css/custom.css" >> assets/css/custom.css 2>/dev/null || true
  echo "  ✓ CSS updated with book cover styles"
else
  echo "  ℹ️  Book cover styles already present"
fi

echo ""
echo "🔗 Updating header navigation..."
# Backup existing header
cp _includes/header.html _includes/header.html.backup
cp "$SOURCE_DIR/_includes/header.html" _includes/header.html
echo "  ✓ Header updated"

echo ""
echo "🏠 Updating index.html..."
# Backup existing index if it exists
if [ -f index.html ]; then
  cp index.html index.html.backup
fi
if [ -f index.markdown ]; then
  cp index.markdown index.markdown.backup
fi
cp "$SOURCE_DIR/index.html" index.html
echo "  ✓ Index updated"

echo ""
echo "📚 Copying templates and guides..."
cp "$SOURCE_DIR/CONTENT_GUIDE.md" . 2>/dev/null || true
echo "  ✓ Guides copied"

echo ""
echo "📁 Creating directories for images..."
mkdir -p assets/images/books
mkdir -p assets/images/music
mkdir -p assets/images/podcasts
echo "  ✓ Image directories created"

echo ""
echo "✅ Migration complete!"
echo ""
echo "📝 Next steps:"
echo "  1. Review _config.yml.backup and merge any custom settings"
echo "  2. Review _includes/header.html.backup if you had custom navigation"
echo "  3. Test locally: bundle exec jekyll serve"
echo "  4. Check that all collections are working"
echo "  5. Set up TinyPNG API key for image compression"
echo ""
echo "⚠️  Note: Backup files created:"
echo "  - _config.yml.backup"
echo "  - _includes/header.html.backup"
echo "  - index.html.backup (if existed)"
echo "  - index.markdown.backup (if existed)"

