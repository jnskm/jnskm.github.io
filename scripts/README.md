# Image Compression Scripts

These scripts automatically compress images using the TinyPNG API, replacing the original files with optimized versions.

## Automatic Compression Options

You have two options for automatic compression on your local machine:

### Option 1: Git Pre-Commit Hook (Recommended)
Automatically compresses images when you commit them to git.

**Setup:**
1. The pre-commit hook is already installed at `.git/hooks/pre-commit`
2. Just set your API key: `export TINYPNG_API_KEY='your-api-key'`
3. That's it! Images will be compressed automatically when you commit.

**How it works:**
- When you run `git commit`, it automatically compresses any staged image files
- The compressed images are automatically added to your commit
- No manual steps needed!

**To disable temporarily:**
```bash
mv .git/hooks/pre-commit .git/hooks/pre-commit.disabled
```

### Option 2: File Watcher (Real-time)
Automatically compresses images as soon as you save them.

**Setup:**
```bash
# Set your API key
export TINYPNG_API_KEY='your-api-key'

# Run the watcher in the background
ruby scripts/watch_images.rb

# Or run it detached (keeps running after closing terminal)
nohup ruby scripts/watch_images.rb > /dev/null 2>&1 &
```

**How it works:**
- Watches the `assets/images/books/` directory
- Automatically compresses images when they're added or modified
- Runs continuously until you stop it (Ctrl+C)

**To stop the watcher:**
```bash
# Find the process
ps aux | grep watch_images

# Kill it
kill <process-id>
```

## Setup

1. **Get a TinyPNG API Key:**
   - Visit https://tinypng.com/developers
   - Sign up for a free account (500 compressions/month free)
   - Get your API key

2. **Set the API Key:**
   ```bash
   export TINYPNG_API_KEY='your-api-key-here'
   ```
   
   Or add it to a `.env` file in the project root:
   ```bash
   echo "TINYPNG_API_KEY=your-api-key-here" > .env
   source .env
   ```

## Manual Usage

If you prefer to compress images manually (or the automatic methods aren't running):

### Ruby Script (Recommended)

```bash
# Compress all images in assets/images/books/
ruby scripts/compress_images.rb

# Compress specific image(s)
ruby scripts/compress_images.rb assets/images/books/book-cover.jpg
ruby scripts/compress_images.rb assets/images/books/*.jpg
```

### Shell Script Alternative

```bash
# Make script executable (first time only)
chmod +x scripts/compress_images.sh

# Compress all images in assets/images/books/
./scripts/compress_images.sh

# Compress specific image(s)
./scripts/compress_images.sh assets/images/books/book-cover.jpg
```

## How It Works

1. Script reads the image file
2. Sends it to TinyPNG API for compression
3. Creates a backup of the original (`.backup` extension)
4. Downloads the compressed version
5. Replaces the original file with the compressed version
6. Shows compression statistics

## Backup Files

The script creates `.backup` files automatically. These are ignored by git (see `.gitignore`). You can:
- Keep them for safety
- Delete them manually if you're satisfied with the compression
- Uncomment the cleanup line in the Ruby script to auto-delete backups

## Notes

- Free TinyPNG accounts: 500 compressions/month
- Works with JPG, PNG, and WebP formats
- Original files are backed up before replacement
- Compression typically reduces file size by 50-70%

