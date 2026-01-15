#!/usr/bin/env python3
"""
Check for new music releases on YouTube and create Jekyll music entries.

This script:
1. Uses the YouTube Data API to fetch ALL videos from a playlist
2. Compares against previously tracked videos AND existing _music/ files
3. Creates new _music/ entries for any new videos
4. Matches the existing simple format used in the site
"""

import os
import re
import json
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
REPO_ROOT = Path(__file__).parent.parent
MUSIC_DIR = REPO_ROOT / '_music'
IMAGES_DIR = REPO_ROOT / 'assets' / 'images' / 'music'
TRACKER_FILE = REPO_ROOT / '.music-tracker.json'

# Cover image settings
COVER_IMAGE_MAX_SIZE = 1080  # Maximum output size (won't upscale beyond source)
COVER_IMAGE_MIN_SIZE = 480   # Minimum acceptable size (below this, skip download)

# YouTube playlist ID - only videos in this playlist will be added to the site
YOUTUBE_PLAYLIST_ID = os.environ.get('YOUTUBE_PLAYLIST_ID', 'PLyxPXRjXeZFtRQQdEXH_pMndVzNPRDqkO')

# YouTube Data API key (required for full playlist access)
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')

# YouTube Data API endpoints
YOUTUBE_API_PLAYLIST_ITEMS = 'https://www.googleapis.com/youtube/v3/playlistItems'
YOUTUBE_API_VIDEOS = 'https://www.googleapis.com/youtube/v3/videos'

# Songlink/Odesli API for finding streaming links
SONGLINK_API = 'https://api.song.link/v1-alpha.1/links'


def fetch_streaming_links(youtube_url: str) -> dict:
    """
    Use Songlink/Odesli API to find streaming links for a song.
    Given a YouTube URL, returns links to Spotify, Apple Music, Amazon Music, etc.

    Returns a dict with keys: spotify, apple_music, amazon_music, youtube_music
    Values are URLs or empty strings if not found.
    """
    links = {
        'spotify': '',
        'apple_music': '',
        'amazon_music': '',
        'youtube_music': '',
    }

    try:
        # URL encode the YouTube URL
        from urllib.parse import quote
        encoded_url = quote(youtube_url, safe='')
        api_url = f"{SONGLINK_API}?url={encoded_url}"

        req = Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))

        # Extract links from the response
        links_by_platform = data.get('linksByPlatform', {})

        if 'spotify' in links_by_platform:
            links['spotify'] = links_by_platform['spotify'].get('url', '')

        if 'appleMusic' in links_by_platform:
            links['apple_music'] = links_by_platform['appleMusic'].get('url', '')

        if 'amazonMusic' in links_by_platform:
            links['amazon_music'] = links_by_platform['amazonMusic'].get('url', '')

        if 'youtubeMusic' in links_by_platform:
            links['youtube_music'] = links_by_platform['youtubeMusic'].get('url', '')

        # Log what we found
        found = [k for k, v in links.items() if v]
        if found:
            print(f"  Found streaming links: {', '.join(found)}")
        else:
            print(f"  No streaming links found (song may not be on other platforms yet)")

    except (URLError, HTTPError) as e:
        print(f"  Could not fetch streaming links: {e}")
    except json.JSONDecodeError as e:
        print(f"  Error parsing Songlink response: {e}")
    except Exception as e:
        print(f"  Unexpected error fetching streaming links: {e}")

    return links


def clean_title(title: str) -> str:
    """
    Clean up YouTube video title for display on the website.

    Removes:
    - "Christian Songs - " prefix
    - " (inspired by ...)" suffix
    """
    # Remove "Christian Songs - " prefix (case insensitive)
    cleaned = re.sub(r'^Christian Songs\s*[-–—]\s*', '', title, flags=re.IGNORECASE)

    # Remove " (inspired by ...)" suffix
    cleaned = re.sub(r'\s*\(inspired by [^)]+\)\s*$', '', cleaned, flags=re.IGNORECASE)

    return cleaned.strip()


def get_video_durations(video_ids: list[str], api_key: str) -> dict[str, int]:
    """
    Fetch video durations for a list of video IDs.
    Returns a dict mapping video_id -> duration in seconds.
    """
    durations = {}

    # Process in batches of 50 (API limit)
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        ids_param = ','.join(batch)

        url = (
            f"{YOUTUBE_API_VIDEOS}"
            f"?part=contentDetails"
            f"&id={ids_param}"
            f"&key={api_key}"
        )

        try:
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))

            for item in data.get('items', []):
                video_id = item.get('id')
                duration_str = item.get('contentDetails', {}).get('duration', 'PT0S')

                # Parse ISO 8601 duration (e.g., "PT4M13S" -> 253 seconds)
                duration_seconds = parse_iso_duration(duration_str)
                durations[video_id] = duration_seconds

        except (URLError, HTTPError) as e:
            print(f"Error fetching video durations: {e}")
        except json.JSONDecodeError as e:
            print(f"Error parsing duration response: {e}")

    return durations


def parse_iso_duration(duration: str) -> int:
    """
    Parse ISO 8601 duration format (e.g., "PT4M13S") to seconds.
    """
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return hours * 3600 + minutes * 60 + seconds


def filter_duplicates_keep_longest(videos: list[dict], durations: dict[str, int]) -> list[dict]:
    """
    When multiple videos have the same cleaned title, keep only the longest one.
    This filters out YouTube Shorts in favor of full songs.
    """
    # Group videos by cleaned title
    by_title = {}
    for video in videos:
        cleaned = clean_title(video['title'])
        if cleaned not in by_title:
            by_title[cleaned] = []
        by_title[cleaned].append(video)

    # For each title, keep only the longest video
    filtered = []
    for cleaned_title, title_videos in by_title.items():
        if len(title_videos) == 1:
            filtered.append(title_videos[0])
        else:
            # Find the longest video
            longest = max(title_videos, key=lambda v: durations.get(v['video_id'], 0))
            duration = durations.get(longest['video_id'], 0)

            # Log what we're doing
            other_ids = [v['video_id'] for v in title_videos if v['video_id'] != longest['video_id']]
            print(f"  Duplicate title '{cleaned_title}': keeping {longest['video_id']} ({duration}s), skipping {other_ids}")

            filtered.append(longest)

    return filtered


def fetch_playlist_videos_api(playlist_id: str, api_key: str) -> list[dict]:
    """
    Fetch ALL videos from a YouTube playlist using the Data API.
    This overcomes the 15-video limit of RSS feeds.

    Returns a list of video entries with metadata.
    """
    if not api_key:
        print("Error: YOUTUBE_API_KEY environment variable not set")
        print("Please add your YouTube Data API key to GitHub Secrets")
        return []

    videos = []
    next_page_token = None

    while True:
        # Build API URL
        url = (
            f"{YOUTUBE_API_PLAYLIST_ITEMS}"
            f"?part=snippet,contentDetails"
            f"&playlistId={playlist_id}"
            f"&maxResults=50"  # Maximum allowed per request
            f"&key={api_key}"
        )

        if next_page_token:
            url += f"&pageToken={next_page_token}"

        try:
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))

            # Process each item in the response
            for item in data.get('items', []):
                snippet = item.get('snippet', {})
                content_details = item.get('contentDetails', {})

                video_id = content_details.get('videoId') or snippet.get('resourceId', {}).get('videoId')

                if not video_id:
                    continue

                # Get the best available thumbnail
                thumbnails = snippet.get('thumbnails', {})
                thumbnail = ''
                for quality in ['maxres', 'standard', 'high', 'medium', 'default']:
                    if quality in thumbnails:
                        thumbnail = thumbnails[quality].get('url', '')
                        break

                videos.append({
                    'video_id': video_id,
                    'title': snippet.get('title', ''),
                    'published': snippet.get('publishedAt', ''),
                    'description': snippet.get('description', ''),
                    'thumbnail': thumbnail,
                    'youtube_url': f'https://www.youtube.com/watch?v={video_id}',
                    'youtube_music_url': f'https://music.youtube.com/watch?v={video_id}',
                })

            # Check for more pages
            next_page_token = data.get('nextPageToken')
            if not next_page_token:
                break

        except (URLError, HTTPError) as e:
            print(f"Error fetching playlist from API: {e}")
            break
        except json.JSONDecodeError as e:
            print(f"Error parsing API response: {e}")
            break

    return videos


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
                if response.status != 200:
                    continue

                image_data = response.read()

                # Check if image is too small (placeholder detection)
                if len(image_data) < 5000:
                    continue

                img = Image.open(BytesIO(image_data))

                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')

                width, height = img.size
                crop_size = min(width, height)

                if crop_size >= COVER_IMAGE_MIN_SIZE:
                    best_image = img
                    best_size = crop_size
                    break

        except (URLError, HTTPError):
            continue
        except Exception as e:
            print(f"  Error processing thumbnail from {url}: {e}")
            continue

    if best_image is None or best_size < COVER_IMAGE_MIN_SIZE:
        size_info = f"{best_size}x{best_size}" if best_size > 0 else "none found"
        print(f"  Skipping thumbnail: too small ({size_info}, need at least {COVER_IMAGE_MIN_SIZE}x{COVER_IMAGE_MIN_SIZE})")
        print(f"  You'll need to manually add a cover image for this track.")
        return False

    # Crop to center square
    width, height = best_image.size
    if width > height:
        left = (width - height) // 2
        best_image = best_image.crop((left, 0, left + height, height))
    elif height > width:
        top = (height - width) // 2
        best_image = best_image.crop((0, top, width, top + width))

    # Determine output size
    current_size = best_image.size[0]
    if current_size > COVER_IMAGE_MAX_SIZE:
        output_size = COVER_IMAGE_MAX_SIZE
        best_image = best_image.resize((output_size, output_size), Image.Resampling.LANCZOS)
        print(f"  Downloaded cover image: {output_path.name} ({output_size}x{output_size}, downscaled from {current_size})")
    else:
        output_size = current_size
        print(f"  Downloaded cover image: {output_path.name} ({output_size}x{output_size})")

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


def extract_bible_verse(description: str) -> str:
    """
    Extract Bible verse from YouTube video description.
    Looks for content after "## Bible Verse" marker.
    Returns the Bible verse text, or empty string if not found.
    """
    if not description:
        return ""

    # Look for ## Bible Verse section
    match = re.search(r'##\s*Bible Verse\s*\n(.*?)(?=\n##|\Z)', description, re.DOTALL | re.IGNORECASE)
    if match:
        verse_text = match.group(1).strip()
        # Clean up: remove links and timestamps
        lines = []
        for line in verse_text.split('\n'):
            line = line.strip()
            if line.startswith('http://') or line.startswith('https://'):
                continue
            if re.match(r'^\d+:\d+', line):
                continue
            lines.append(line)
        return '\n'.join(lines).strip()

    return ""


def create_music_entry(video: dict) -> Path:
    """
    Create a Jekyll music entry file for a video.
    Also downloads and resizes the YouTube thumbnail as cover art.
    Returns the path to the created file.

    Generated files match the template structure with:
    - Full front matter (all streaming platform fields)
    - ## Bible Verse section (from YouTube description)
    - ## Inspiration section (placeholder)
    - ## Lyrics section (placeholder)
    - ## Listen On section (placeholder)
    """
    # Clean the title for display
    display_title = clean_title(video['title'])

    # Generate a slug for the filename (use cleaned title)
    slug = slugify(display_title, max_length=50)

    # Parse the published date
    pub_date = datetime.now()
    if video['published']:
        try:
            # Handle ISO format with timezone
            published = video['published'].replace('Z', '+00:00')
            pub_date = datetime.fromisoformat(published)
        except ValueError:
            pass

    date_str = pub_date.strftime('%Y-%m-%d')
    youtube_short_url = f'https://youtu.be/{video["video_id"]}'
    youtube_music_url = f'https://music.youtube.com/watch?v={video["video_id"]}'

    # Download and resize the thumbnail
    download_and_resize_thumbnail(video['video_id'], slug)

    # Fetch streaming links from Songlink/Odesli
    print(f"  Fetching streaming links for {display_title}...")
    streaming_links = fetch_streaming_links(youtube_short_url)

    # Use fetched links or fallback to defaults
    spotify_url = streaming_links.get('spotify', '')
    apple_music_url = streaming_links.get('apple_music', '')
    amazon_music_url = streaming_links.get('amazon_music', '')
    if streaming_links.get('youtube_music'):
        youtube_music_url = streaming_links['youtube_music']

    # Extract Bible verse from YouTube description
    bible_verse = extract_bible_verse(video.get('description', ''))

    # Build the file content matching the template structure
    content_lines = [
        '---',
        f'title: "{display_title}"',
        f'date: {date_str}',
        f'cover_image: "/assets/images/music/{slug}.png"',
        '# Recommended image dimensions: 300x300px (1:1 aspect ratio, square)',
        '# This ensures optimal display and fast loading on all devices',
        '# File size should be under 100KB for best performance',
        f'youtube: "{youtube_short_url}"',
        f'youtube_music: "{youtube_music_url}"',
        f'spotify: "{spotify_url}"',
        f'apple_music: "{apple_music_url}"',
        f'amazon_music: "{amazon_music_url}"',
        '---',
    ]

    # Add Bible Verse section
    content_lines.append('## Bible Verse')
    if bible_verse:
        content_lines.append(bible_verse)
    else:
        content_lines.append('(Add Bible verse here)')
    content_lines.append('')

    # Add Inspiration section (placeholder - to be filled manually)
    content_lines.append('## Inspiration')
    content_lines.append('')
    content_lines.append('(Add inspiration and background for this song)')
    content_lines.append('')

    # Add Lyrics section (placeholder - to be filled manually)
    content_lines.append('## Lyrics')
    content_lines.append('[Verse 1]')
    content_lines.append('(Add lyrics here)')
    content_lines.append('')
    content_lines.append('[Chorus]')
    content_lines.append('(Add lyrics here)')
    content_lines.append('')

    # Add Listen On section with streaming links
    content_lines.append('## Listen On')
    listen_on_links = []
    if youtube_short_url:
        listen_on_links.append(f'- [YouTube]({youtube_short_url})')
    if youtube_music_url:
        listen_on_links.append(f'- [YouTube Music]({youtube_music_url})')
    if spotify_url:
        listen_on_links.append(f'- [Spotify]({spotify_url})')
    if apple_music_url:
        listen_on_links.append(f'- [Apple Music]({apple_music_url})')
    if amazon_music_url:
        listen_on_links.append(f'- [Amazon Music]({amazon_music_url})')

    if listen_on_links:
        content_lines.extend(listen_on_links)
    else:
        content_lines.append('(Add streaming links here)')
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


def build_listen_on_content(streaming_links: dict, youtube_url: str = "", youtube_music_url: str = "") -> str:
    """
    Build the Listen On section content with streaming links.
    Returns markdown formatted links.
    """
    links = []

    # Get URLs from streaming_links dict or use provided defaults
    yt_url = youtube_url or streaming_links.get('youtube', '')
    ytm_url = youtube_music_url or streaming_links.get('youtube_music', '')
    spotify_url = streaming_links.get('spotify', '')
    apple_music_url = streaming_links.get('apple_music', '')
    amazon_music_url = streaming_links.get('amazon_music', '')

    if yt_url:
        links.append(f'- [YouTube]({yt_url})')
    if ytm_url:
        links.append(f'- [YouTube Music]({ytm_url})')
    if spotify_url:
        links.append(f'- [Spotify]({spotify_url})')
    if apple_music_url:
        links.append(f'- [Apple Music]({apple_music_url})')
    if amazon_music_url:
        links.append(f'- [Amazon Music]({amazon_music_url})')

    return '\n'.join(links) if links else ''


def update_existing_music_entry(filepath: Path, bible_verse: str = "", streaming_links: dict = None) -> bool:
    """
    Update an existing music entry file to add missing sections.
    Preserves all existing content - only adds sections that don't exist.
    Can also populate Listen On section with streaming links if empty.

    Returns True if the file was modified, False otherwise.
    """
    if streaming_links is None:
        streaming_links = {}

    try:
        content = filepath.read_text()
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
        return False

    modified = False
    sections_to_check = ['## Bible Verse', '## Inspiration', '## Lyrics', '## Listen On']

    # Check which sections are missing
    missing_sections = []
    for section in sections_to_check:
        if section not in content:
            missing_sections.append(section)

    # Check if Listen On section exists but is empty (only has the header)
    listen_on_empty = False
    if '## Listen On' in content and '## Listen On' not in missing_sections:
        # Find the Listen On section and check if it has any links
        listen_match = re.search(r'## Listen On\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
        if listen_match:
            listen_content = listen_match.group(1).strip()
            # Consider empty if no markdown links or just placeholder text
            if not listen_content or listen_content == '(Add streaming links here)' or '](http' not in listen_content:
                listen_on_empty = True

    if not missing_sections and not listen_on_empty:
        return False  # All sections present and Listen On has content

    # Find the end of front matter (after second ---)
    front_matter_end = content.find('---', content.find('---') + 3)
    if front_matter_end == -1:
        print(f"  Warning: Could not find front matter in {filepath}")
        return False

    # Position after the closing ---
    insert_pos = front_matter_end + 3

    # Find where the body content starts (skip newlines after front matter)
    body_start = insert_pos
    while body_start < len(content) and content[body_start] in '\n\r':
        body_start += 1

    # Get existing body content
    body_content = content[body_start:] if body_start < len(content) else ""

    # Build new content by adding missing sections in order
    new_body_parts = []

    # Bible Verse section
    if '## Bible Verse' in missing_sections:
        new_body_parts.append('## Bible Verse')
        if bible_verse:
            new_body_parts.append(bible_verse)
        else:
            new_body_parts.append('(Add Bible verse here)')
        new_body_parts.append('')
        modified = True

    # Check if we need to add other sections at the end
    sections_to_add_at_end = []

    if '## Inspiration' in missing_sections:
        sections_to_add_at_end.append(('## Inspiration', '\n(Add inspiration and background for this song)\n'))
        modified = True

    if '## Lyrics' in missing_sections:
        sections_to_add_at_end.append(('## Lyrics', '[Verse 1]\n(Add lyrics here)\n\n[Chorus]\n(Add lyrics here)\n'))
        modified = True

    if '## Listen On' in missing_sections:
        # Build Listen On content with streaming links
        listen_content = build_listen_on_content(streaming_links)
        sections_to_add_at_end.append(('## Listen On', listen_content))
        modified = True

    # Handle empty Listen On section - populate with streaming links
    if listen_on_empty and streaming_links:
        listen_content = build_listen_on_content(streaming_links)
        if listen_content:
            # Replace the empty Listen On section with populated one
            content = re.sub(
                r'## Listen On\s*\n.*?(?=\n## |\Z)',
                f'## Listen On\n{listen_content}\n',
                content,
                flags=re.DOTALL
            )
            modified = True
            print(f"  Populated Listen On section with streaming links")

    if not modified:
        return False

    # Reconstruct the file
    new_content = content[:insert_pos] + '\n'

    # Add Bible Verse at the beginning if missing
    if new_body_parts:
        new_content += '\n'.join(new_body_parts) + '\n'

    # Add existing body content
    new_content += body_content

    # Add missing sections at the end
    for section_header, section_content in sections_to_add_at_end:
        if not new_content.endswith('\n'):
            new_content += '\n'
        new_content += f'\n{section_header}\n{section_content}'

    # Ensure file ends with newline
    if not new_content.endswith('\n'):
        new_content += '\n'

    # Write the updated content
    try:
        filepath.write_text(new_content)
        print(f"  Updated: {filepath.name} (added: {', '.join(missing_sections)})")
        return True
    except Exception as e:
        print(f"  Error writing {filepath}: {e}")
        return False


def set_github_output(name: str, value: str):
    """Set a GitHub Actions output variable."""
    output_file = os.environ.get('GITHUB_OUTPUT')
    if output_file:
        with open(output_file, 'a') as f:
            f.write(f'{name}={value}\n')
    else:
        print(f"Output: {name}={value}")


def update_all_existing_files(videos: list[dict]) -> int:
    """
    Update all existing music files to add any missing sections.
    Uses video data to populate Bible verses from YouTube descriptions.
    Fetches streaming links via Songlink API for files with empty Listen On sections.

    Returns the number of files updated.
    """
    updated_count = 0

    # Build a mapping of video_id -> video data for Bible verse lookup
    video_by_id = {v['video_id']: v for v in videos}

    # Patterns to extract video ID from file content
    video_id_patterns = [
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
    ]

    for filepath in MUSIC_DIR.glob('*.md'):
        if filepath.name.startswith('_'):  # Skip templates
            continue

        try:
            content = filepath.read_text()

            # Find the video ID in this file
            video_id = None
            for pattern in video_id_patterns:
                match = re.search(pattern, content)
                if match:
                    video_id = match.group(1)
                    break

            # Get Bible verse from YouTube if we have the video data
            bible_verse = ""
            if video_id and video_id in video_by_id:
                bible_verse = extract_bible_verse(video_by_id[video_id].get('description', ''))

            # Check if Listen On section needs streaming links
            streaming_links = {}
            listen_on_empty = False
            if '## Listen On' in content:
                listen_match = re.search(r'## Listen On\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
                if listen_match:
                    listen_content = listen_match.group(1).strip()
                    if not listen_content or listen_content == '(Add streaming links here)' or '](http' not in listen_content:
                        listen_on_empty = True

            # Fetch streaming links if Listen On is empty and we have a video ID
            if listen_on_empty and video_id:
                youtube_url = f"https://youtu.be/{video_id}"
                print(f"  Fetching streaming links for {filepath.name}...")
                streaming_links = fetch_streaming_links(youtube_url)

            # Update the file if needed
            if update_existing_music_entry(filepath, bible_verse, streaming_links):
                updated_count += 1

        except Exception as e:
            print(f"  Error processing {filepath}: {e}")

    return updated_count


def main():
    print(f"Checking for new music from YouTube playlist: {YOUTUBE_PLAYLIST_ID}")

    # Check for API key
    if not YOUTUBE_API_KEY:
        print("\n" + "="*60)
        print("ERROR: YouTube API key not configured!")
        print("="*60)
        print("\nTo fix this:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project and enable YouTube Data API v3")
        print("3. Create an API key")
        print("4. Add it as a GitHub Secret named YOUTUBE_API_KEY")
        print("\nSee docs/MUSIC-AUTOMATION.md for detailed instructions.")
        print("="*60 + "\n")
        set_github_output('new_music', 'false')
        return

    # Ensure music directory exists
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)

    # Fetch ALL videos from playlist using the API
    print("Fetching YouTube playlist via Data API...")
    videos = fetch_playlist_videos_api(YOUTUBE_PLAYLIST_ID, YOUTUBE_API_KEY)
    print(f"Found {len(videos)} videos in playlist")

    if not videos:
        print("No videos found or API error occurred.")
        set_github_output('new_music', 'false')
        return

    # Fetch video durations to filter out shorts
    print("Fetching video durations...")
    video_ids = [v['video_id'] for v in videos]
    durations = get_video_durations(video_ids, YOUTUBE_API_KEY)

    # Filter duplicates (keep longest version of each song)
    print("Filtering duplicates (keeping full songs over shorts)...")
    videos = filter_duplicates_keep_longest(videos, durations)
    print(f"After filtering: {len(videos)} unique songs")

    # Update existing files with missing sections
    print("\nChecking existing files for missing sections...")
    updated_count = update_all_existing_files(videos)
    if updated_count > 0:
        print(f"Updated {updated_count} existing files with missing sections.")
    else:
        print("All existing files have complete sections.")

    # Load previously tracked videos
    tracked = load_tracked_videos()
    print(f"\nPreviously tracked in tracker file: {len(tracked)} videos")

    # Also check existing _music/ files to avoid duplicates
    existing = get_existing_video_ids()
    print(f"Found in existing _music/ files: {len(existing)} videos")

    # Combine both sets
    already_processed = tracked | existing

    # Find new videos
    new_videos = []
    for video in videos:
        if video['video_id'] not in already_processed:
            new_videos.append(video)
            tracked.add(video['video_id'])
        else:
            tracked.add(video['video_id'])

    print(f"New music videos to add: {len(new_videos)}")

    # Create entries for new videos
    created_titles = []
    for video in new_videos:
        try:
            create_music_entry(video)
            created_titles.append(clean_title(video['title']))
        except Exception as e:
            print(f"Error creating entry for '{video['title']}': {e}")

    # Save updated tracker
    save_tracked_videos(tracked)

    # Set outputs for GitHub Actions
    if created_titles or updated_count > 0:
        set_github_output('new_music', 'true')
        if created_titles:
            titles_str = ', '.join(created_titles)
            if len(titles_str) > 100:
                titles_str = titles_str[:97] + '...'
            set_github_output('titles', titles_str)
            print(f"\nSuccessfully created {len(created_titles)} new music entries!")
        if updated_count > 0:
            print(f"Updated {updated_count} existing files.")
    else:
        set_github_output('new_music', 'false')
        print("\nNo new music found and no files needed updating.")


if __name__ == '__main__':
    main()
