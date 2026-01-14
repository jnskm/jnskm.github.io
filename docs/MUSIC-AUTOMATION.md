# Music Automation System

This document explains how the automatic music detection and website update system works.

## Overview

When you add a new song to your **"Christian Songs" YouTube playlist**, a GitHub Action automatically:

1. Uses the YouTube Data API to check ALL videos in your playlist daily
2. Detects any new videos added to the playlist
3. Downloads the thumbnail and creates a new music entry page on your website
4. Commits and pushes the change, triggering a site rebuild

**Why a playlist?** This gives you full control—only songs you intentionally add to the playlist will appear on your website. Other channel videos (tutorials, vlogs, etc.) are ignored.

## Setup (One-Time)

Before the automation will work, you need to set up a YouTube Data API key:

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** at the top, then **New Project**
3. Name it something like "JNSKM Music Automation"
4. Click **Create**

### Step 2: Enable YouTube Data API

1. In your new project, go to **APIs & Services** > **Library**
2. Search for "YouTube Data API v3"
3. Click on it, then click **Enable**

### Step 3: Create an API Key

1. Go to **APIs & Services** > **Credentials**
2. Click **+ CREATE CREDENTIALS** > **API key**
3. Copy the API key that appears
4. (Optional but recommended) Click **Edit API key** to restrict it:
   - Under "API restrictions", select "Restrict key"
   - Choose "YouTube Data API v3" only
   - Click **Save**

### Step 4: Add API Key to GitHub

1. Go to your GitHub repository: https://github.com/jnskm/jnskm.github.io
2. Click **Settings** > **Secrets and variables** > **Actions**
3. Click **New repository secret**
4. Name: `YOUTUBE_API_KEY`
5. Value: Paste your API key
6. Click **Add secret**

That's it! The automation will now work.

## How It Works

### Components

```
.github/workflows/check-new-music.yml  - GitHub Action workflow
scripts/check_new_music.py             - Python script that does the work
_music/                                - Directory for music entries
assets/images/music/                   - Cover images (auto-downloaded)
.music-tracker.json                    - Tracks which videos have been processed
```

### Workflow

```
Add song to "Christian Songs" playlist
                ↓
GitHub Action runs (daily at 9 AM UTC)
                ↓
Fetches ALL playlist videos via YouTube Data API
                ↓
Compares to tracked videos & existing _music/ files
                ↓
New video found? → Downloads thumbnail as cover image
                → Creates _music/song-name.md
                ↓
Commits & pushes → Site rebuilds automatically
```

### Playlist

The system monitors this playlist:
- **Name:** Christian Songs
- **URL:** https://youtube.com/playlist?list=PLyxPXRjXeZFtRQQdEXH_pMndVzNPRDqkO

## Usage

### Automatic Detection

The system runs automatically every day at 9 AM UTC. No action needed from you.

### Manual Trigger

To check for new music immediately:

1. Go to your GitHub repository
2. Click **Actions** tab
3. Select **Check for New Music Releases**
4. Click **Run workflow** button

### After a New Release

When a new music entry is created automatically, it will have:

- ✅ Title (from YouTube)
- ✅ Date (from YouTube publish date)
- ✅ YouTube link
- ✅ Cover image (auto-downloaded from YouTube, cropped to square, resized to 1080x1080)
- ❌ Spotify link (needs manual update)
- ❌ Apple Music link (needs manual update)
- ❌ Amazon Music link (needs manual update)
- ❌ Lyrics (needs manual update)

**Note:** The cover image is automatically downloaded from the YouTube thumbnail, cropped from 16:9 to square (centered), and resized to 1080x1080 pixels to match your existing album art.

### Adding Streaming Links

After DistroKid distributes your music to other platforms (usually 1-3 days), edit the created file to add links:

1. Go to `_music/your-song-name.md`
2. Add the streaming links:

```yaml
spotify: "https://open.spotify.com/track/..."
apple_music: "https://music.apple.com/..."
amazon_music: "https://music.amazon.com/..."
```

### Adding Lyrics

To add lyrics to a track:

```yaml
show_lyrics: true
lyrics: |
  Verse 1:
  Your lyrics here...

  Chorus:
  More lyrics here...
```

## Customization

### Filtering Videos

The script tries to detect music videos vs. other content. Edit `scripts/check_new_music.py` to customize:

```python
# Keywords that indicate a video IS music
MUSIC_KEYWORDS = ['official', 'audio', 'music', ...]

# Keywords that indicate a video is NOT music
NON_MUSIC_KEYWORDS = ['vlog', 'tutorial', ...]
```

If your channel is music-only, you can simplify by changing `is_music_video()` to always return `True`.

### Schedule

To change when the check runs, edit `.github/workflows/check-new-music.yml`:

```yaml
schedule:
  - cron: '0 9 * * *'  # Currently: 9 AM UTC daily
```

Common schedules:
- `'0 */6 * * *'` - Every 6 hours
- `'0 9,21 * * *'` - Twice daily (9 AM and 9 PM UTC)
- `'0 9 * * 1'` - Weekly on Mondays

## Troubleshooting

### "YouTube API key not configured" error

Make sure you've completed the setup steps above. The API key must be added as a GitHub Secret named `YOUTUBE_API_KEY`.

### Videos not being detected

1. Check the Actions tab for error logs
2. Verify the playlist ID is correct in the workflow file
3. Make sure your API key has YouTube Data API v3 enabled
4. Try running the workflow manually

### API quota exceeded

The YouTube Data API has a daily quota (10,000 units). Each playlist fetch uses about 1-2 units per 50 videos. Normal usage (once daily) won't hit this limit, but if you run it many times manually, you might temporarily hit the quota.

### Re-processing videos

To re-process all videos (e.g., after fixing a bug):

1. Delete `.music-tracker.json`
2. Run the workflow manually

This will create entries for ALL videos in the playlist (not limited to 15 like RSS feeds).

## Technical Notes

### Why YouTube Data API?

The system uses the YouTube Data API instead of RSS feeds because:

- RSS feeds only return the 15 most recent videos (not sorted by date)
- The API returns ALL videos in the playlist with pagination
- Better reliability and metadata access

### Cover Image Processing

Thumbnails are automatically:

- Downloaded from the highest quality available (maxres > standard > high)
- Cropped from 16:9 to square (center crop)
- Downscaled to max 1080x1080 if larger
- **Never upscaled** (to avoid blurry images)
- Skipped if source is smaller than 480x480 (too small to be useful)

## Future Enhancements

Potential improvements you could add:

- **Spotify API integration**: Automatically fetch Spotify links when available
- **Lyrics API**: Auto-fetch lyrics from services like Genius
- **DistroKid webhook**: Trigger updates when DistroKid confirms distribution

## File Locations

| File | Purpose |
|------|---------|
| `_music/*.md` | Individual music entry pages |
| `assets/images/music/*.png` | Cover images (1080x1080) |
| `_layouts/music.html` | Template for music pages |
| `music.md` | Music listing page |
| `scripts/check_new_music.py` | Automation script |
| `.music-tracker.json` | Processed video tracker |
