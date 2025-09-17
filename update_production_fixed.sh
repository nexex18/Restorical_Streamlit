#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Streamlit Production Update Script ===${NC}"

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

# Step 2: Pull latest changes from GitHub
echo -e "\n${YELLOW}Pulling latest changes from GitHub...${NC}"
git pull origin main
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Successfully pulled latest changes${NC}"
else
    echo -e "${RED}✗ Failed to pull from GitHub${NC}"
    echo -e "${YELLOW}Please check your git status and resolve any conflicts${NC}"
    exit 1
fi

# Step 3: Install/update dependencies if requirements.txt changed
if git diff HEAD@{1} --name-only | grep -q "requirements.txt"; then
    echo -e "\n${YELLOW}requirements.txt changed, updating dependencies...${NC}"
    pip install -r requirements.txt
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Dependencies updated${NC}"
    else
        echo -e "${RED}✗ Failed to update dependencies${NC}"
        exit 1
    fi
else
    echo -e "\n${GREEN}✓ No dependency changes detected${NC}"
fi

# Step 4: Fix and verify .env file
echo -e "\n${YELLOW}Checking and fixing .env file...${NC}"

# Create a clean .env file if it doesn't exist or fix it if it has issues
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file with production settings...${NC}"
    cat > .env << 'EOL'
ECO_DB_PATH=/app/restorical/data/database/ecology_sites.db
PROCESS_API_BASE=http://localhost:5001
PROCESS_API_TOKEN=restorical
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=127.0.0.1
AUTH_TOKEN=restorical
EOL
    echo -e "${GREEN}✓ Created .env file${NC}"
else
    # Clean up the existing .env file (remove EOF lines, leading spaces)
    echo -e "${YELLOW}Cleaning up .env file...${NC}"
    # Remove EOF lines and leading/trailing spaces
    sed -i '/^[[:space:]]*EOF$/d; s/^[[:space:]]*//; s/[[:space:]]*$//' .env
    # Remove empty lines
    sed -i '/^$/d' .env
    echo -e "${GREEN}✓ Cleaned .env file${NC}"
fi

# Display the .env file for verification
echo -e "\n${YELLOW}Current .env configuration:${NC}"
cat .env

# Step 5: Load environment variables for the script
echo -e "\n${YELLOW}Loading environment variables...${NC}"
set -a  # automatically export all variables
source .env
set +a  # turn off automatic export
echo -e "${GREEN}✓ Environment variables loaded${NC}"

# Step 6: Start Streamlit with explicit configuration
echo -e "\n${YELLOW}Starting Streamlit application...${NC}"

# Get configuration from environment or use defaults
SERVER_ADDRESS="${STREAMLIT_SERVER_ADDRESS:-127.0.0.1}"
SERVER_PORT="${STREAMLIT_SERVER_PORT:-8501}"

# Start Streamlit with explicit server configuration
# This ensures it uses the right address and port even if .env loading fails
nohup streamlit run streamlit_app.py \
    --server.address=$SERVER_ADDRESS \
    --server.port=$SERVER_PORT \
    --server.headless=true \
    > streamlit.log 2>&1 &

STREAMLIT_PID=$!
sleep 3

# Step 7: Verify Streamlit started successfully
if ps -p $STREAMLIT_PID > /dev/null; then
    echo -e "${GREEN}✓ Streamlit started successfully (PID: $STREAMLIT_PID)${NC}"
    
    # Check what address it's actually listening on
    echo -e "\n${YELLOW}Checking listening ports...${NC}"
    lsof -i :$SERVER_PORT 2>/dev/null | grep LISTEN || netstat -tlnp 2>/dev/null | grep :$SERVER_PORT
    
    echo -e "\n${GREEN}=== Deployment Successful ===${NC}"
    
    # Determine how to access the application
    if [ "$SERVER_ADDRESS" = "127.0.0.1" ] || [ "$SERVER_ADDRESS" = "localhost" ]; then
        echo -e "Application is running locally only (secured mode)."
        echo -e "Access through Nginx proxy at:"
        echo -e "  ${GREEN}http://your-domain/streamlit/${NC}"
    else
        PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "your-server-ip")
        echo -e "Application is running at:"
        echo -e "  ${GREEN}http://${PUBLIC_IP}:${SERVER_PORT}${NC}"
    fi
    
    echo -e "\nUseful commands:"
    echo -e "  View logs:        ${YELLOW}tail -f streamlit.log${NC}"
    echo -e "  Check status:     ${YELLOW}ps aux | grep streamlit${NC}"
    echo -e "  Stop application: ${YELLOW}pkill -f streamlit${NC}"
    echo -e "  View connections: ${YELLOW}lsof -i :${SERVER_PORT}${NC}"
    echo -e "  Check .env:       ${YELLOW}cat .env${NC}"
else
    echo -e "${RED}✗ Failed to start Streamlit${NC}"
    echo -e "${YELLOW}Check streamlit.log for errors:${NC}"
    tail -n 20 streamlit.log
    exit 1
fi

echo -e "\n${GREEN}Update complete!${NC}"