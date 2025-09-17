#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Streamlit Production Restart Script ===${NC}"

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${RED}ERROR: Virtual environment is not activated!${NC}"
    echo -e "${YELLOW}Please activate your virtual environment first:${NC}"
    echo -e "  source venv/bin/activate"
    exit 1
fi

echo -e "${GREEN}✓ Virtual environment detected: $VIRTUAL_ENV${NC}"

# Step 1: Stop existing Streamlit process
echo -e "\n${YELLOW}Stopping existing Streamlit processes...${NC}"
if pgrep -f streamlit > /dev/null; then
    pkill -f streamlit
    echo -e "${GREEN}✓ Streamlit processes stopped${NC}"
    sleep 2
else
    echo -e "${GREEN}✓ No existing Streamlit processes found${NC}"
fi

# Step 2: Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}✗ .env file not found!${NC}"
    echo -e "${YELLOW}Please create a .env file with your environment variables${NC}"
    exit 1
fi

# Step 3: Load environment variables
echo -e "\n${YELLOW}Loading environment variables...${NC}"
# Source the .env file to load variables into current shell
set -a  # automatically export all variables
source .env
set +a  # turn off automatic export
echo -e "${GREEN}✓ Environment variables loaded${NC}"

# Step 4: Start Streamlit in background
echo -e "\n${YELLOW}Starting Streamlit application...${NC}"
# The environment variables are now in the shell and will be inherited by the child process
nohup streamlit run streamlit_app.py > streamlit.log 2>&1 &
STREAMLIT_PID=$!
sleep 3

# Step 5: Verify Streamlit started successfully
if ps -p $STREAMLIT_PID > /dev/null; then
    echo -e "${GREEN}✓ Streamlit started successfully (PID: $STREAMLIT_PID)${NC}"
    
    # Get the server address from environment or use defaults
    SERVER_ADDRESS="${STREAMLIT_SERVER_ADDRESS:-0.0.0.0}"
    SERVER_PORT="${STREAMLIT_SERVER_PORT:-8501}"
    
    # Get the public IP
    PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "your-server-ip")
    
    echo -e "\n${GREEN}=== Restart Successful ===${NC}"
    echo -e "Application is running at:"
    echo -e "  ${GREEN}http://${PUBLIC_IP}/streamlit/${NC}"
    echo -e "  (Port ${SERVER_PORT} is blocked - access through Nginx proxy only)"
    echo -e "\nUseful commands:"
    echo -e "  View logs:        ${YELLOW}tail -f streamlit.log${NC}"
    echo -e "  Check status:     ${YELLOW}ps aux | grep streamlit${NC}"
    echo -e "  Stop application: ${YELLOW}pkill -f streamlit${NC}"
else
    echo -e "${RED}✗ Failed to start Streamlit${NC}"
    echo -e "${YELLOW}Check streamlit.log for errors:${NC}"
    tail -n 20 streamlit.log
    exit 1
fi

echo -e "\n${GREEN}Restart complete!${NC}"