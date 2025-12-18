#!/usr/bin/env ruby
# File watcher that automatically compresses images when they're added/modified
# Run this in the background: ruby scripts/watch_images.rb
# Or use: nohup ruby scripts/watch_images.rb &

require 'fileutils'
require 'time'

# Directories to watch
WATCH_DIRS = [
  File.join(__dir__, '..', 'assets', 'images', 'books'),
  File.join(__dir__, '..', 'assets', 'images', 'music')
]
COMPRESS_SCRIPT = File.join(__dir__, 'compress_images.rb')

# Track processed files to avoid re-processing
processed_files = {}

puts "Watching for new/modified images in:"
WATCH_DIRS.each { |dir| puts "  - #{dir}" }
puts "Press Ctrl+C to stop"
puts ""

# Check if directories exist
WATCH_DIRS.each do |watch_dir|
  unless Dir.exist?(watch_dir)
    puts "Warning: Directory not found: #{watch_dir}"
    puts "  Creating directory..."
    FileUtils.mkdir_p(watch_dir)
  end
end

# Check if compression script exists
unless File.exist?(COMPRESS_SCRIPT)
  puts "Error: Compression script not found: #{COMPRESS_SCRIPT}"
  exit 1
end

# Function to compress a single image using the script
def compress_single_image(image_path, compress_script)
  return false unless File.exist?(image_path)
  return false unless image_path.match?(/\.(jpg|jpeg|png|webp)$/i)
  
  # Skip backup files
  return false if image_path.end_with?('.backup')
  
  # Call the compression script
  system("ruby", compress_script, image_path)
  $?.success?
end

loop do
  begin
    # Check for new or modified image files in all watch directories
    WATCH_DIRS.each do |watch_dir|
      Dir.glob(File.join(watch_dir, '*.{jpg,jpeg,png,webp}')).each do |image_path|
        # Skip backup files
        next if image_path.end_with?('.backup')
        
        mtime = File.mtime(image_path)
        file_key = image_path
        
        # Process if new file or modified since last check
        if !processed_files[file_key] || processed_files[file_key] < mtime
          # Only process if modified in the last 5 seconds (to catch new saves)
          if (Time.now - mtime) < 5
            puts "[#{Time.now.strftime('%H:%M:%S')}] Detected: #{File.basename(image_path)}"
            compress_single_image(image_path, COMPRESS_SCRIPT)
            processed_files[file_key] = mtime
            puts ""
          end
        end
      end
    end
    
    sleep 2  # Check every 2 seconds
  rescue Interrupt
    puts "\nStopping file watcher..."
    exit 0
  rescue => e
    puts "Error: #{e.message}"
    sleep 5  # Wait longer on error
  end
end

