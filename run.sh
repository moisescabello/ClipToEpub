#!/bin/bash
# Launcher script for Clipboard to ePub

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Starting Clipboard to ePub...${NC}"

# Activate virtual environment
source venv/bin/activate

# Run the application (menu bar)
python -m cliptoepub.menubar_app "$@"

# Deactivate virtual environment on exit
deactivate
