#!/bin/bash
# Shell script alternative to compress images using TinyPNG API
# Usage: ./scripts/compress_images.sh [path/to/image.jpg]

if [ -z "$TINYPNG_API_KEY" ]; then
  echo "Error: TINYPNG_API_KEY environment variable is not set."
  echo "Please set it with: export TINYPNG_API_KEY='your-api-key'"
  exit 1
fi

compress_image() {
  local image_path="$1"
  
  if [ ! -f "$image_path" ]; then
    echo "Error: File not found: $image_path"
    return 1
  fi
  
  # Check if file is an image
  if [[ ! "$image_path" =~ \.(jpg|jpeg|png|webp)$ ]]; then
    echo "Skipping non-image file: $image_path"
    return 1
  fi
  
  echo "Compressing: $image_path"
  
  # Create backup
  backup_path="${image_path}.backup"
  cp "$image_path" "$backup_path"
  
  # Compress using TinyPNG API
  response=$(curl -s -w "\n%{http_code}" \
    --user "api:$TINYPNG_API_KEY" \
    --data-binary @"$image_path" \
    https://api.tinify.com/shrink)
  
  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | sed '$d')
  
  if [ "$http_code" = "201" ]; then
    # Extract output URL
    output_url=$(echo "$body" | grep -o '"url":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$output_url" ]; then
      # Download compressed image
      curl -s --user "api:$TINYPNG_API_KEY" "$output_url" -o "$image_path"
      
      # Calculate savings
      original_size=$(stat -f%z "$backup_path" 2>/dev/null || stat -c%s "$backup_path" 2>/dev/null)
      compressed_size=$(stat -f%z "$image_path" 2>/dev/null || stat -c%s "$image_path" 2>/dev/null)
      savings=$(awk "BEGIN {printf \"%.1f\", (1 - $compressed_size/$original_size) * 100}")
      
      echo "  ✓ Compressed: $original_size bytes → $compressed_size bytes ($savings% reduction)"
      echo "  Backup saved to: $backup_path"
      
      return 0
    else
      echo "  ✗ Error: Could not extract output URL from response"
      mv "$backup_path" "$image_path"
      return 1
    fi
  else
    echo "  ✗ Error compressing image: HTTP $http_code"
    echo "  Response: $body"
    mv "$backup_path" "$image_path"
    return 1
  fi
}

# Main execution
if [ $# -gt 0 ]; then
  # Compress specific file(s) provided as arguments
  for file_path in "$@"; do
    compress_image "$file_path"
  done
else
  # Compress all images in assets/images/books/
  script_dir="$(cd "$(dirname "$0")" && pwd)"
  books_dir="$script_dir/../assets/images/books"
  
  if [ ! -d "$books_dir" ]; then
    echo "Error: Directory not found: $books_dir"
    exit 1
  fi
  
  image_files=("$books_dir"/*.{jpg,jpeg,png,webp} 2>/dev/null)
  
  if [ ${#image_files[@]} -eq 0 ] || [ ! -f "${image_files[0]}" ]; then
    echo "No images found in $books_dir"
    exit 0
  fi
  
  echo "Found ${#image_files[@]} image(s) to compress..."
  echo ""
  
  compressed_count=0
  for image_path in "${image_files[@]}"; do
    if compress_image "$image_path"; then
      ((compressed_count++))
    fi
    echo ""
  done
  
  echo "Compression complete: $compressed_count/${#image_files[@]} images compressed"
fi

