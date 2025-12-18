# Migration Guide: jnskm.com → jnskm.github.io

This guide will help you migrate all the new features (collections, layouts, scripts) from `jnskm.com` to `jnskm.github.io`.

## Quick Migration

Run the migration script:

```bash
cd /Users/jnskm/Documents/Code/jnskm.com
./scripts/migrate_to_github_io_simple.sh
```

Then follow the manual steps below.

## Manual Steps

### 1. Update `_config.yml`

Add these sections to your `jnskm.github.io/_config.yml`:

```yaml
# Collections for structured content
collections:
  music:
    output: true
    permalink: /music/:name/
  books:
    output: true
    permalink: /books/:name/
  videos:
    output: true
    permalink: /videos/:name/
  bible_studies:
    output: true
    permalink: /bible-studies/:name/

# Front matter defaults for easier content creation
defaults:
  - scope:
      path: "_posts/blog"
      type: "posts"
    values:
      layout: "post"
      category: "blog"
  - scope:
      path: "_music"
      type: "music"
    values:
      layout: "music"
  - scope:
      path: "_books"
      type: "books"
    values:
      layout: "book"
  - scope:
      path: "_videos"
      type: "videos"
    values:
      layout: "video"
  - scope:
      path: "_bible_studies"
      type: "bible_studies"
    values:
      layout: "bible_study"
  - scope:
      path: "_posts"
      type: "posts"
    values:
      layout: "post"
```

**Note:** Since `jnskm.github.io` uses the `minima` theme, you may need to adjust the `layout: "post"` to match your theme's layout names. Check what layouts are available in your `_layouts/` directory.

### 2. Update CSS for Book Covers

Add this to `assets/css/custom.css`:

```css
.book-cover {
  width: 300px;            /* Base width for 6:9 aspect ratio */
  max-width: 100%;         /* Keep responsive on small screens */
  aspect-ratio: 2 / 3;     /* Enforce 6:9 (2:3) aspect ratio */
  height: auto;            /* Fallback for older browsers */
  float: left;             /* Aligns image left */
  margin-right: 20px;      /* Spacing between image and text */
  margin-bottom: 15px;     /* Spacing below image */
  display: block;
  object-fit: contain;     /* Preserve full image without cropping */
}

/* Make images responsive on mobile */
@media screen and (max-width: 600px) {
  .book-cover {
    width: 200px;                 /* Smaller size on mobile (maintains 6:9 ratio) */
    float: none;                  /* Remove floating */
    display: block;
    margin: 0 auto 15px auto;     /* Center the image */
  }
}

/* Extra small mobile devices */
@media screen and (max-width: 400px) {
  .book-cover {
    width: 150px;                 /* Even smaller for very old/small devices */
  }
}
```

### 3. Update Header Navigation

Update `_includes/header.html` to include the new navigation links. The migrated header should include:

- Blog
- Books
- Music
- Videos
- Bible Studies
- Devotionals
- Podcasts
- Contact

**Note:** Since you're using the `minima` theme, the header structure might be different. You may need to adapt the navigation to match your theme's structure.

### 4. Update Index Page

If you want the home page to show all content types (like in `jnskm.com`), update `index.html` or `index.markdown` to match the structure from `jnskm.com/index.html`.

**Note:** The `minima` theme uses `index.markdown` by default. You may need to:
- Keep `index.markdown` for theme compatibility, or
- Override it with `index.html` if you want custom behavior

### 5. Install Git Hook (Optional)

If you want automatic image compression on commit:

```bash
cd /Users/jnskm/Documents/Code/jnskm.github.io
cp scripts/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### 6. Set Up TinyPNG API Key

```bash
export TINYPNG_API_KEY='your-api-key'
# Or add to .env file
echo "TINYPNG_API_KEY=your-api-key" > .env
```

### 7. Test Locally

```bash
cd /Users/jnskm/Documents/Code/jnskm.github.io
bundle install
bundle exec jekyll serve
```

Visit `http://localhost:4000` and check:
- [ ] Collections pages load (`/music`, `/books`, `/videos`, `/bible-studies`)
- [ ] Book covers display correctly with proper aspect ratio
- [ ] Navigation includes all new links
- [ ] Home page shows content (if updated)

## Theme Compatibility Notes

Since `jnskm.github.io` uses the `minima` theme:

1. **Layouts:** The theme may override some layouts. Check if you need to:
   - Create theme-specific versions of layouts
   - Override theme layouts in `_layouts/`

2. **Navigation:** The `minima` theme has its own navigation system. You may need to:
   - Override the theme's header include
   - Or configure navigation through `_config.yml` if the theme supports it

3. **Styling:** The theme's CSS may conflict. You can:
   - Override in `assets/css/custom.css`
   - Or create a custom theme override

## Troubleshooting

### Collections not showing up
- Check that `collections` section is in `_config.yml`
- Verify `output: true` for each collection
- Restart Jekyll server after config changes

### Layouts not working
- Check that layout files exist in `_layouts/`
- Verify front matter defaults are set correctly
- Check for theme layout conflicts

### Images not displaying
- Verify image paths are correct
- Check that `assets/images/books/` directory exists
- Verify CSS is loaded

## Files Copied by Script

The migration script copies:
- ✅ Collections directories (`_music`, `_books`, `_videos`, `_bible_studies`)
- ✅ Layout files (`music.html`, `book.html`, `video.html`, `bible_study.html`)
- ✅ Page files (`music.md`, `books.md`, `videos.md`, `bible-studies.md`)
- ✅ Scripts directory
- ✅ Content guide

## Files You Need to Update Manually

- ⚙️ `_config.yml` - Add collections and defaults
- 🎨 `assets/css/custom.css` - Add book cover styles
- 🔗 `_includes/header.html` - Update navigation
- 🏠 `index.html` or `index.markdown` - Update home page (optional)
- 🔧 `.git/hooks/pre-commit` - Install git hook (optional)

