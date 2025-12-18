#!/usr/bin/env ruby
# Script to compress images using TinyPNG API
# Usage: ruby scripts/compress_images.rb [path/to/image.jpg]

require 'net/http'
require 'json'
require 'fileutils'

# Get API key from environment variable
TINYPNG_API_KEY = ENV['TINYPNG_API_KEY']

if TINYPNG_API_KEY.nil? || TINYPNG_API_KEY.empty?
  puts "Error: TINYPNG_API_KEY environment variable is not set."
  puts "Please set it with: export TINYPNG_API_KEY='your-api-key'"
  exit 1
end

def compress_image(image_path, resize_width: nil, resize_height: nil)
  unless File.exist?(image_path)
    puts "Error: File not found: #{image_path}"
    return false
  end

  # Check if file is an image
  unless image_path.match?(/\.(jpg|jpeg|png|webp)$/i)
    puts "Skipping non-image file: #{image_path}"
    return false
  end

  puts "Compressing: #{image_path}"
  if resize_width && resize_height
    puts "  Resizing to: #{resize_width}x#{resize_height}px"
  end

  # Read the image file
  image_data = File.binread(image_path)
  
  # Create HTTP request to TinyPNG API
  uri = URI('https://api.tinify.com/shrink')
  http = Net::HTTP.new(uri.host, uri.port)
  http.use_ssl = true
  
  request = Net::HTTP::Post.new(uri.path)
  request.basic_auth('api', TINYPNG_API_KEY)
  request.body = image_data
  request['Content-Type'] = 'application/octet-stream'
  
  # Make the request
  response = http.request(request)
  
  if response.code == '201'
    # Get the compressed image URL from response
    result = JSON.parse(response.body)
    output_url = result['output']['url']
    
    # Apply resize if requested (for book/album covers)
    if resize_width && resize_height
      # For resizing, we need to make a POST request to the output URL
      resize_uri = URI(output_url)
      resize_http = Net::HTTP.new(resize_uri.host, resize_uri.port)
      resize_http.use_ssl = true
      
      resize_request = Net::HTTP::Post.new(resize_uri.path)
      resize_request.basic_auth('api', TINYPNG_API_KEY)
      resize_request['Content-Type'] = 'application/json'
      resize_request.body = {
        'resize' => {
          'method' => 'cover',  # Use 'cover' for exact dimensions (may crop), or 'fit' to fit within dimensions
          'width' => resize_width,
          'height' => resize_height
        }
      }.to_json
      
      resize_response = resize_http.request(resize_request)
      if resize_response.code == '200'
        output_url = JSON.parse(resize_response.body)['output']['url']
      else
        puts "  ⚠ Warning: Resize failed (#{resize_response.code}): #{resize_response.body}"
        puts "  Using compressed image without resize"
      end
    end
    
    # Download the compressed (and optionally resized) image
    download_uri = URI(output_url)
    download_request = Net::HTTP::Get.new(download_uri.path)
    download_request.basic_auth('api', TINYPNG_API_KEY)
    
    download_response = http.request(download_request)
    
    if download_response.code == '200'
      # Create backup of original
      backup_path = "#{image_path}.backup"
      FileUtils.cp(image_path, backup_path)
      
      # Replace original with compressed version
      File.binwrite(image_path, download_response.body)
      
      # Get file sizes
      original_size = File.size(backup_path)
      compressed_size = File.size(image_path)
      savings = ((1 - compressed_size.to_f / original_size) * 100).round(1)
      
      puts "  ✓ Compressed: #{original_size} bytes → #{compressed_size} bytes (#{savings}% reduction)"
      puts "  Backup saved to: #{backup_path}"
      
      # Optionally remove backup (uncomment if you want)
      # FileUtils.rm(backup_path)
      
      return true
    else
      puts "  ✗ Error downloading compressed image: #{download_response.code}"
      return false
    end
  else
    puts "  ✗ Error compressing image: #{response.code} - #{response.body}"
    return false
  end
rescue => e
  puts "  ✗ Error: #{e.message}"
  return false
end

# Main execution
if ARGV.length > 0
  # Compress specific file(s) provided as arguments
  ARGV.each do |file_path|
    # Determine if this is a book or album cover based on path
    if file_path.include?('/books/')
      compress_image(file_path, resize_width: 300, resize_height: 450)
    elsif file_path.include?('/music/')
      compress_image(file_path, resize_width: 300, resize_height: 300)  # Square 1:1 aspect ratio
    else
      # No resize for other images
      compress_image(file_path)
    end
  end
else
  # Compress all images in assets/images/books/ and assets/images/music/
  books_dir = File.join(__dir__, '..', 'assets', 'images', 'books')
  music_dir = File.join(__dir__, '..', 'assets', 'images', 'music')
  
  total_compressed = 0
  total_images = 0
  
  # Process book covers
  if Dir.exist?(books_dir)
    image_files = Dir.glob(File.join(books_dir, '*.{jpg,jpeg,png,webp}'))
    unless image_files.empty?
      puts "Found #{image_files.length} book cover image(s) to compress..."
      puts ""
      
      image_files.each do |image_path|
        if compress_image(image_path, resize_width: 300, resize_height: 450)
          total_compressed += 1
        end
        total_images += 1
        puts ""
      end
    end
  end
  
  # Process album covers
  if Dir.exist?(music_dir)
    image_files = Dir.glob(File.join(music_dir, '*.{jpg,jpeg,png,webp}'))
    unless image_files.empty?
      puts "Found #{image_files.length} album cover image(s) to compress..."
      puts ""
      
      image_files.each do |image_path|
        if compress_image(image_path, resize_width: 300, resize_height: 300)  # Square 1:1 aspect ratio
          total_compressed += 1
        end
        total_images += 1
        puts ""
      end
    end
  end
  
  if total_images == 0
    puts "No images found in #{books_dir} or #{music_dir}"
    exit 0
  end
  
  puts "Compression complete: #{total_compressed}/#{total_images} images compressed"
end

