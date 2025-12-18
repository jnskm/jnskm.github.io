#!/bin/bash
# Setup script for automatic local image compression
# Run this once to set up automatic compression

echo "Setting up automatic image compression..."
echo ""

# Check if API key is already set
if [ -z "$TINYPNG_API_KEY" ]; then
  echo "Please enter your TinyPNG API key:"
  echo "  (Get it from: https://tinypng.com/developers)"
  read -r api_key
  
  if [ -z "$api_key" ]; then
    echo "Error: API key is required"
    exit 1
  fi
  
  # Add to .env file
  echo "TINYPNG_API_KEY=$api_key" > .env
  echo ""
  echo "✅ API key saved to .env file"
  echo ""
  echo "To use it, run: source .env"
  echo "Or add this to your ~/.zshrc or ~/.bashrc:"
  echo "  export TINYPNG_API_KEY='$api_key'"
  echo ""
else
  echo "✅ API key is already set"
  echo ""
fi

# Check if pre-commit hook is installed
if [ -f .git/hooks/pre-commit ]; then
  echo "✅ Git pre-commit hook is installed"
  echo "   Images will be automatically compressed when you commit"
else
  echo "⚠️  Git pre-commit hook not found"
  echo "   Run: cp scripts/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit"
fi

echo ""
echo "Setup complete!"
echo ""
echo "Automatic compression is now enabled:"
echo "  - Images will be compressed automatically when you commit them"
echo "  - No manual steps needed!"
echo ""
echo "To test, add an image to assets/images/books/ and commit it."

