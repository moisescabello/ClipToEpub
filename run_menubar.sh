#!/bin/bash

# Clipboard to ePub - Phase 3 Menu Bar Launcher
# This script launches the menu bar application

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}📋 Clipboard to ePub - Menu Bar Application${NC}"
echo -e "${BLUE}=================================================${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo "Please run ./setup.sh first to set up the environment"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if required packages are installed
python -c "import rumps, pync" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${BLUE}ℹ️  Installing Phase 3 dependencies...${NC}"
    pip install rumps pync
fi

# Create default configuration if it doesn't exist
CONFIG_FILE="$HOME/Library/Preferences/clipboard-to-epub.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${BLUE}ℹ️  Creating default configuration...${NC}"
    mkdir -p "$HOME/Library/Preferences"
    cat > "$CONFIG_FILE" << EOL
{
  "output_directory": "$HOME/Documents/ClipboardEpubs",
  "hotkey": "cmd+shift+e",
  "author": "Unknown Author",
  "language": "en",
  "style": "default",
  "auto_open": false,
  "show_notifications": true,
  "chapter_words": 5000
}
EOL
    echo -e "${GREEN}✅ Configuration created at: $CONFIG_FILE${NC}"
fi

# Check accessibility permissions reminder
echo ""
echo -e "${BLUE}⚠️  IMPORTANT: Accessibility Permissions${NC}"
echo "The app needs accessibility permissions for global hotkeys to work."
echo ""
echo "To grant permissions:"
echo "1. Open System Settings > Privacy & Security > Accessibility"
echo "2. Click the '+' button and add Terminal (or your terminal app)"
echo "3. Make sure the checkbox is enabled"
echo ""
echo "Press Enter to continue..."
read

# Launch the menu bar application
echo -e "${GREEN}🚀 Launching menu bar application...${NC}"
echo -e "${BLUE}The app will appear in your menu bar as a 📋 icon${NC}"
echo ""
echo "Features:"
echo "  • Click the icon to access the menu"
echo "  • Use Cmd+Shift+E to convert clipboard content"
echo "  • Recent conversions are available in the menu"
echo "  • Settings can be configured from the menu"
echo ""
echo "Press Ctrl+C to stop the application"
echo -e "${BLUE}=================================================${NC}"

# Run the menu bar app
python src/menubar_app.py

# Deactivate virtual environment when done
deactivate

echo -e "${GREEN}✅ Application stopped${NC}"