# Content Creation Guide

This guide will help you quickly create new content for your Jekyll site.

## Quick Start

### Creating a Blog Post

1. Create a new file in `_posts/blog/` with the format: `YYYY-MM-DD-post-title.md`
2. Use this template:

```markdown
---
title: "Your Blog Post Title"
date: 2025-01-01
category: blog
---

Your blog post content here.
```

### Creating a Music Track

1. Copy `_music/_template.md` to `_music/track-name.md`
2. Fill in the front matter and content
3. The layout will automatically create links to all your streaming platforms
4. Add lyrics using the `lyrics` field and set `show_lyrics: true`

Example:
```markdown
---
title: "Song Title"
artist: "Your Name"
date: 2025-01-01
youtube: "https://youtube.com/watch?v=..."
spotify: "https://open.spotify.com/track/..."
apple_music: "https://music.apple.com/..."
show_lyrics: true
lyrics: |
  ## Verse 1
  Line one
  Line two
---

Your description here.
```

### Creating a Book Entry

1. Copy `_books/_template.md` to `_books/book-name.md`
2. Prepare your book cover image with these specifications:
   - **Dimensions**: 300x450px (6:9 aspect ratio)
   - **File format**: JPG or WebP (JPG recommended for compatibility)
   - **File size**: Under 100KB for fast loading on older devices
   - **Aspect ratio**: Must be exactly 6:9 (2:3) - width:height
3. Add your book cover image to `assets/images/books/`
4. Fill in the front matter

**Image Optimization Tips:**
- Use image editing software to resize to exactly 300x450px
- **Automatic Compression (Recommended):** Images are automatically compressed when you commit them to git!
  - The git pre-commit hook will compress images automatically
  - Just set your API key: `export TINYPNG_API_KEY='your-api-key'`
  - See `scripts/README.md` for setup and alternative options
- **Manual Compression:** If you prefer to compress manually:
  ```bash
  # Set your TinyPNG API key first
  export TINYPNG_API_KEY='your-api-key'
  
  # Compress all book cover images
  ruby scripts/compress_images.rb
  
  # Or compress a specific image
  ruby scripts/compress_images.rb assets/images/books/book-cover.jpg
  ```
- Manual tools: Use tools like TinyPNG, ImageOptim, or Squoosh (aim for 50-100KB)
- Test on mobile devices to ensure fast loading
- The CSS will automatically maintain the 6:9 aspect ratio

Example:
```markdown
---
title: "Book Title"
author: "Your Name"
date: 2025-01-01
cover_image: "/assets/images/books/book-cover.jpg"
amazon: "https://a.co/d/..."
series: "Tails of Grace"  # Optional
---

Your book description here.
```

### Creating a Video Entry (Music Videos with Lyrics)

1. Copy `_videos/_template.md` to `_videos/video-name.md`
2. Use either `youtube_id` (just the ID) or `youtube_url` (full URL)
3. Videos are embedded by default. Set `embed_video: false` if you only want a link
4. Add lyrics if applicable

Example:
```markdown
---
title: "Video Title"
date: 2025-01-01
youtube_id: "dQw4w9WgXcQ"
embed_video: true  # Set to false for link-only
show_lyrics: true
lyrics: |
  Verse 1
  Line one
  Line two
---

Your video description here.
```

### Creating a Bible Study Video

1. Copy `_bible_studies/_template.md` to `_bible_studies/study-name.md`
2. Use either `youtube_id` (just the ID) or `youtube_url` (full URL)
3. Videos are embedded by default. Set `embed_video: false` if you only want a link
4. Add scripture reference in the `scripture` field

Example:
```markdown
---
title: "Bible Study: John 3:16"
date: 2025-01-01
scripture: "John 3:16"
youtube_id: "dQw4w9WgXcQ"
embed_video: true  # Set to false for link-only
---

Your Bible study description here.
```

## File Naming

- Blog posts: `_posts/blog/YYYY-MM-DD-title.md`
- Music: `_music/track-name.md` (no date needed in filename)
- Books: `_books/book-name.md` (no date needed in filename)
- Videos (music videos with lyrics): `_videos/video-name.md` (no date needed in filename)
- Bible Studies: `_bible_studies/study-name.md` (no date needed in filename)

## Tips

- The `date` field in front matter controls sorting and display
- All fields are optional except `title`
- You can add any custom front matter fields you need
- The templates in each collection folder show all available options

