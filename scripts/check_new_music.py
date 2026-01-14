#!/usr/bin/env python3
"""
Check for new music releases on YouTube and create Jekyll music entries.

This script:
1. Fetches the YouTube RSS feed for the configured channel
2. Compares against previously tracked videos AND existing _music/ files
3. Creates new _music/ entries for any new videos
4. Matches the existing simple format used in the site
"""

import os
import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from io import BytesIO
from slugify import slugify

# PIL is optional - if not available, thumbnails won't be downloaded
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL/Pillow not installed. Thumbnails will not be downloaded.")

# Configuration
YOUTUBE_HANDLE = os.environ.get('YOUTUBE_HANDLE', '@jnskm')
REPO_ROOT = Path(__file__).parent.parent
MUSIC_DIR = REPO_ROOT / '_music'
IMAGES_DIR = REPO_ROOT / 'assets' / 'images' / 'music'
TRACKER_FILE = REPO_ROOT / '.music-tracker.json'

# Cover image settings
# YouTube maxresdefault is 1280x720, which crops to 720x720 square
# We don't upscale to avoid blurry images - output matches input size (up to max)
COVER_IMAGE_MAX_SIZE = 1080  # Maximum output size (won't upscale beyond source)
COVER_IMAGE_MIN_SIZE = 480   # Minimum acceptable size (below this, skip download)

# YouTube playlist ID - only videos in this playlist will be added to the site
# This is from the "Christian Songs" playlist
YOUTUBE_PLAYLIST_ID = os.environ.get('YOUTUBE_PLAYLIST_ID', 'PLyxPXRjXeZFtRQQdEXH_pMndVzNPRDqkO')

# YouTube RSS feed URL patterns
YOUTUBE_RSS_BY_PLAYLIST_ID = 'https://www.youtube.com/feeds/videos.xml?playlist_id={}'
YOUTUBE_RSS_BY_CHANNEL_ID = 'https://www.youtube.com/feeds/videos.xml?channel_id={}'
YOUTUBE_CHANNEL_PAGE = 'https://www.youtube.com/{}'

# Since we're using a curated playlist, assume ALL videos in it are music
ASSUME_ALL_MUSIC = True

# Keywords that indicate a video is music (only used if ASSUME_ALL_MUSIC = False)
MUSIC_KEYWORDS = [
    'official', 'audio', 'music', 'song', 'single', 'album', 'ep',
    'lyric', 'video', 'mv', 'track', 'release'
]

# Keywords that indicate a video is NOT music
NON_MUSIC_KEYWORDS = [
    'vlog', 'tutorial', 'review', 'unboxing', 'gameplay', 'stream',
    'podcast', 'interview', 'behind the scenes', 'reaction'
]


def fetch_playlist_rss(playlist_id: str) -> list[dict]:
    """
    Fetch and parse the YouTube RSS feed for a playlist.
    Returns a list of video entries with metadata.
    """
    url = YOUTUBE_RSS_BY_PLAYLIST_ID.format(playlist_id)
    return _parse_youtube_rss(url)


def fetch_channel_rss(channel_id: str) -> list[dict]:
    """
    Fetch and parse the YouTube RSS feed for a channel.
    Returns a list of video entries with metadata.
    """
    url = YOUTUBE_RSS_BY_CHANNEL_ID.format(channel_id)
    return _parse_youtube_rss(url)


def get_channel_id_from_handle(handle: str) -> str | None:
    """
    Fetch the YouTube channel page and extract the channel ID.
    The channel ID is needed for the RSS feed.
    """
    url = YOUTUBE_CHANNEL_PAGE.format(handle)
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8')

            # Look for channel ID in various places
            patterns = [
                r'"channelId":"(UC[a-zA-Z0-9_-]{22})"',
                r'channel_id=(UC[a-zA-Z0-9_-]{22})',
                r'"externalId":"(UC[a-zA-Z0-9_-]{22})"',
                r'<meta itemprop="channelId" content="(UC[a-zA-Z0-9_-]{22})"',
            ]

            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    return match.group(1)

    except (URLError, HTTPError) as e:
        print(f"Error fetching channel page: {e}")

    return None


def _parse_youtube_rss(url: str) -> list[dict]:
    """
    Fetch and parse a YouTube RSS feed (channel or playlist).
    Returns a list of video entries with metadata.
    """
    videos = []

    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=30) as response:
            xml_content = response.read()

        # Parse XML
        root = ET.fromstring(xml_content)

        # Define namespaces used in YouTube RSS
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'yt': 'http://www.youtube.com/xml/schemas/2015',
            'media': 'http://search.yahoo.com/mrss/',
        }

        # Extract video entries
        for entry in root.findall('atom:entry', namespaces):
            video_id = entry.find('yt:videoId', namespaces)
            title = entry.find('atom:title', namespaces)
            published = entry.find('atom:published', namespaces)

            # Get media group for additional info
            media_group = entry.find('media:group', namespaces)
            description = ''
            thumbnail = ''

            if media_group is not None:
                desc_elem = media_group.find('media:description', namespaces)
                if desc_elem is not None and desc_elem.text:
                    description = desc_elem.text

                thumb_elem = media_group.find('media:thumbnail', namespaces)
                if thumb_elem is not None:
                    thumbnail = thumb_elem.get('url', '')

            if video_id is not None and title is not None:
                videos.append({
                    'video_id': video_id.text,
                    'title': title.text,
                    'published': published.text if published is not None else '',
                    'description': description,
                    'thumbnail': thumbnail,
                    'youtube_url': f'https://www.youtube.com/watch?v={video_id.text}',
                    'youtube_music_url': f'https://music.youtube.com/watch?v={video_id.text}',
                })

    except (URLError, HTTPError) as e:
        print(f"Error fetching RSS feed: {e}")
    except ET.ParseError as e:
        print(f"Error parsing RSS XML: {e}")

    return videos


def is_music_video(video: dict) -> bool:
    """
    Determine if a video is likely a music release based on title and description.
    This helps filter out vlogs, tutorials, etc.

    Customize ASSUME_ALL_MUSIC and keywords at the top of this file.
    """
    # For music-focused channels, assume everything is music
    if ASSUME_ALL_MUSIC:
        return True

    text = (video['title'] + ' ' + video['description']).lower()

    # Check for non-music keywords first
    for keyword in NON_MUSIC_KEYWORDS:
        if keyword in text:
            return False

    # Check for music keywords
    for keyword in MUSIC_KEYWORDS:
        if keyword in text:
            return True

    # Default: include the video
    return True


def get_existing_video_ids() -> set[str]:
    """
    Scan existing _music/ files to extract video IDs already on the site.
    This prevents duplicates even if the tracker file is missing.
    """
    video_ids = set()

    if not MUSIC_DIR.exists():
        return video_ids

    # Patterns to match YouTube video IDs in various URL formats
    patterns = [
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
    ]

    for filepath in MUSIC_DIR.glob('*.md'):
        if filepath.name.startswith('_'):  # Skip templates
            continue
        try:
            content = filepath.read_text()
            for pattern in patterns:
                matches = re.findall(pattern, content)
                video_ids.update(matches)
        except Exception as e:
            print(f"Warning: Could not read {filepath}: {e}")

    return video_ids


def download_and_resize_thumbnail(video_id: str, slug: str) -> bool:
    """
    Download YouTube thumbnail and save as square album art.

    NEVER upscales to avoid blurry images:
    - If source >= max size: downscale to max size
    - If source >= min size: keep original size (no scaling)
    - If source < min size: skip (too small, would be blurry)

    YouTube provides thumbnails at various resolutions:
    - maxresdefault.jpg (1280x720) -> 720x720 after crop
    - sddefault.jpg (640x480) -> 480x480 after crop
    - hqdefault.jpg (480x360) -> 360x360 after crop

    Returns True if successful, False otherwise.
    """
    if not PIL_AVAILABLE:
        print(f"  Skipping thumbnail download (PIL not available)")
        return False

    # Ensure images directory exists
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    output_path = IMAGES_DIR / f'{slug}.png'

    # Skip if image already exists
    if output_path.exists():
        print(f"  Cover image already exists: {output_path.name}")
        return True

    # Try different thumbnail qualities (highest first)
    thumbnail_urls = [
        f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg',
        f'https://img.youtube.com/vi/{video_id}/sddefault.jpg',
        f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg',
    ]

    best_image = None
    best_size = 0

    for url in thumbnail_urls:
        try:
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=30) as response:
                # Check if we got a valid image (YouTube returns a placeholder for missing thumbnails)
                if response.status != 200:
                    continue

                image_data = response.read()

                # Check if image is too small (placeholder detection)
                if len(image_data) < 5000:
                    continue

                # Open and process the image
                img = Image.open(BytesIO(image_data))

                # Convert to RGB if necessary (in case of RGBA or palette images)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')

                width, height = img.size

                # The square crop size will be min(width, height)
                crop_size = min(width, height)

                # Use the first (largest) image that's at least minimum size
                if crop_size >= COVER_IMAGE_MIN_SIZE:
                    best_image = img
                    best_size = crop_size
                    break  # Use the highest quality available

        except (URLError, HTTPError) as e:
            continue
        except Exception as e:
            print(f"  Error processing thumbnail from {url}: {e}")
            continue

    # Check if we found a usable image
    if best_image is None or best_size < COVER_IMAGE_MIN_SIZE:
        size_info = f"{best_size}x{best_size}" if best_size > 0 else "none found"
        print(f"  Skipping thumbnail: too small ({size_info}, need at least {COVER_IMAGE_MIN_SIZE}x{COVER_IMAGE_MIN_SIZE})")
        print(f"  You'll need to manually add a cover image for this track.")
        return False

    # Crop to center square
    width, height = best_image.size
    if width > height:
        # Landscape: crop sides
        left = (width - height) // 2
        best_image = best_image.crop((left, 0, left + height, height))
    elif height > width:
        # Portrait: crop top/bottom
        top = (height - width) // 2
        best_image = best_image.crop((0, top, width, top + width))

    # Determine output size: downscale if larger than max, otherwise keep original
    current_size = best_image.size[0]  # It's square now
    if current_size > COVER_IMAGE_MAX_SIZE:
        output_size = COVER_IMAGE_MAX_SIZE
        best_image = best_image.resize((output_size, output_size), Image.Resampling.LANCZOS)
        print(f"  Downloaded cover image: {output_path.name} ({output_size}x{output_size}, downscaled from {current_size})")
    else:
        output_size = current_size
        print(f"  Downloaded cover image: {output_path.name} ({output_size}x{output_size})")

    # Save as PNG
    best_image.save(output_path, 'PNG', optimize=True)

    return True


def load_tracked_videos() -> set[str]:
    """Load the set of video IDs we've already processed."""
    if TRACKER_FILE.exists():
        with open(TRACKER_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get('processed_videos', []))
    return set()


def save_tracked_videos(video_ids: set[str]):
    """Save the set of processed video IDs."""
    with open(TRACKER_FILE, 'w') as f:
        json.dump({
            'processed_videos': list(video_ids),
            'last_updated': datetime.utcnow().isoformat(),
        }, f, indent=2)


def create_music_entry(video: dict) -> Path:
    """
    Create a Jekyll music entry file for a video.
    Also downloads and resizes the YouTube thumbnail as cover art.
    Matches the simple format used in existing entries.
    Returns the path to the created file.
    """
    # Generate a slug for the filename
    slug = slugify(video['title'], max_length=50)

    # Parse the published date
    pub_date = datetime.now()
    if video['published']:
        try:
            pub_date = datetime.fromisoformat(video['published'].replace('Z', '+00:00'))
        except ValueError:
            pass

    # Format the date for Jekyll
    date_str = pub_date.strftime('%Y-%m-%d')

    # Use short youtu.be URL format (matching existing entries)
    youtube_short_url = f'https://youtu.be/{video["video_id"]}'

    # Download and resize the thumbnail
    download_and_resize_thumbnail(video['video_id'], slug)

    # Build the file content in the simple format matching existing entries
    # Example from be-still.md:
    # ---
    # title: "Be Still"
    # date: 2025-02-27
    # cover_image: "/assets/images/music/be-still.png"
    # youtube: "https://youtu.be/RoFy80UpDV4"
    # show_lyrics: false
    # ---
    #
    # Inspired by Psalm 46.

    content_lines = [
        '---',
        f'title: "{video["title"]}"',
        f'date: {date_str}',
        f'cover_image: "/assets/images/music/{slug}.png"',
        f'youtube: "{youtube_short_url}"',
        'show_lyrics: false',
        '---',
        '',
    ]

    # Add description as content if available
    if video['description']:
        # Take first line of description (often the song inspiration/note)
        first_line = video['description'].split('\n')[0].strip()
        if first_line and len(first_line) < 300:
            content_lines.append(first_line)
            content_lines.append('')

    # Write the file
    filename = f'{slug}.md'
    filepath = MUSIC_DIR / filename

    # Handle duplicate filenames
    counter = 1
    while filepath.exists():
        filename = f'{slug}-{counter}.md'
        filepath = MUSIC_DIR / filename
        counter += 1

    with open(filepath, 'w') as f:
        f.write('\n'.join(content_lines))

    print(f"Created: {filepath}")
    return filepath


def set_github_output(name: str, value: str):
    """Set a GitHub Actions output variable."""
    output_file = os.environ.get('GITHUB_OUTPUT')
    if output_file:
        with open(output_file, 'a') as f:
            f.write(f'{name}={value}\n')
    else:
        print(f"Output: {name}={value}")


def main():
    print(f"Checking for new music from YouTube playlist: {YOUTUBE_PLAYLIST_ID}")

    # Ensure music directory exists
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)

    # Fetch RSS feed from playlist
    print("Fetching YouTube playlist RSS feed...")
    videos = fetch_playlist_rss(YOUTUBE_PLAYLIST_ID)
    print(f"Found {len(videos)} videos in playlist")

    # Load previously tracked videos from tracker file
    tracked = load_tracked_videos()
    print(f"Previously tracked in tracker file: {len(tracked)} videos")

    # Also check existing _music/ files to avoid duplicates
    existing = get_existing_video_ids()
    print(f"Found in existing _music/ files: {len(existing)} videos")

    # Combine both sets
    already_processed = tracked | existing

    # Find new videos
    new_videos = []
    for video in videos:
        if video['video_id'] not in already_processed:
            if is_music_video(video):
                new_videos.append(video)
                tracked.add(video['video_id'])
            else:
                print(f"Skipping non-music video: {video['title']}")
                tracked.add(video['video_id'])  # Still track it to avoid reprocessing
        else:
            # Make sure tracker has all existing video IDs
            tracked.add(video['video_id'])

    print(f"New music videos to add: {len(new_videos)}")

    # Create entries for new videos
    created_titles = []
    for video in new_videos:
        try:
            create_music_entry(video)
            created_titles.append(video['title'])
        except Exception as e:
            print(f"Error creating entry for '{video['title']}': {e}")

    # Save updated tracker
    save_tracked_videos(tracked)

    # Set outputs for GitHub Actions
    if created_titles:
        set_github_output('new_music', 'true')
        # Truncate titles if too long for commit message
        titles_str = ', '.join(created_titles)
        if len(titles_str) > 100:
            titles_str = titles_str[:97] + '...'
        set_github_output('titles', titles_str)
        print(f"\nSuccessfully created {len(created_titles)} new music entries!")
    else:
        set_github_output('new_music', 'false')
        print("\nNo new music found.")


if __name__ == '__main__':
    main()
