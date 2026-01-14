# Music Automation System

This document explains how the automatic music detection and website update system works.

## Overview

When you add a new song to your **"Christian Songs" YouTube playlist**, a GitHub Action automatically:

1. Checks the playlist RSS feed daily
2. Detects any new videos added to the playlist
3. Creates a new music entry page on your website
4. Commits and pushes the change, triggering a site rebuild

**Why a playlist?** This gives you full control—only songs you intentionally add to the playlist will appear on your website. Other channel videos (tutorials, vlogs, etc.) are ignored.

## How It Works

### Components

```
.github/workflows/check-new-music.yml  - GitHub Action workflow
scripts/check_new_music.py             - Python script that does the work
_music/                                - Directory for music entries
.music-tracker.json                    - Tracks which videos have been processed
```

### Workflow

```
Add song to "Christian Songs" playlist
                ↓
GitHub Action runs (daily at 9 AM UTC)
                ↓
Fetches playlist RSS feed
                ↓
Compares to tracked videos & existing _music/ files
                ↓
New video found? → Creates _music/song-name.md
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

### Videos not being detected

1. Check the Actions tab for error logs
2. Verify your YouTube handle is correct in the workflow file
3. Try running the workflow manually

### Wrong channel ID

If the script can't find your channel ID automatically, you can hardcode it:

1. Find your channel ID (format: UC...)
2. Edit `scripts/check_new_music.py`
3. Replace the `get_channel_id_from_handle()` call with your ID

### Re-processing videos

To re-process all videos (e.g., after fixing a bug):

1. Delete `.music-tracker.json`
2. Run the workflow manually

This will create entries for all videos currently in the RSS feed (typically the 15 most recent).

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
