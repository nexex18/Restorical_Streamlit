# Streamlit Eco Site Analytics Deployment Guide

## Overview
This guide covers deploying the Streamlit Eco Site Analytics application to a production server.

## Prerequisites
- Ubuntu server (tested on Ubuntu 20.04/22.04)
- Python 3.10+ installed
- Git installed
- Access to the shared database at `/app/restorical/data/database/ecology_sites.db`

## Initial Server Setup

### 1. Clone the Repository
```bash
cd /app
git clone https://github.com/nexex18/Restorical_Streamlit.git eco-analytics
cd eco-analytics
```

### 2. Create Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install python-dotenv  # Required for environment variable loading
```

### 4. Configure Environment Variables
Create a `.env` file in the project root (`/app/eco-analytics/.env`):

```bash
cat > .env << 'EOF'
ECO_DB_PATH=/app/restorical/data/database/ecology_sites.db
PROCESS_API_BASE=http://localhost:5001
PROCESS_API_TOKEN=restorical
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
AUTH_TOKEN=restorical
EOF
```

**Important:** The `.env` file is gitignored and should never be committed to the repository. Each deployment should maintain its own `.env` file.

## Running the Application

### Manual Start (for testing)
```bash
cd /app/eco-analytics
source .venv/bin/activate

# Load environment variables and run
export $(grep -v '^#' .env | xargs)
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

### Running in Background (production)

#### Option 1: Using nohup
```bash
cd /app/eco-analytics
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
nohup streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0 > streamlit.log 2>&1 &
```

#### Option 2: Using screen (recommended)
```bash
# Create a new screen session
screen -S streamlit

# Inside the screen session
cd /app/eco-analytics
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0

# Detach from screen with Ctrl+A, then D
# Reattach later with: screen -r streamlit
```

## Updating the Application

### 1. Pull Latest Changes
```bash
cd /app/eco-analytics
git pull origin main
```

### 2. Update Dependencies (if needed)
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Restart the Application
```bash
# Find and stop the current process
pkill -f streamlit

# Start again using your preferred method (see Running the Application above)
```

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `ECO_DB_PATH` | Path to the shared SQLite database | `/app/restorical/data/database/ecology_sites.db` |
| `PROCESS_API_BASE` | Base URL for the FastHTML processing API | `http://localhost:5001` |
| `PROCESS_API_TOKEN` | Authentication token for the processing API | `restorical` |
| `AUTH_TOKEN` | Password for Streamlit app authentication | `restorical` |
| `STREAMLIT_SERVER_PORT` | Port for Streamlit server | `8501` |
| `STREAMLIT_SERVER_ADDRESS` | Address to bind Streamlit server | `0.0.0.0` |

## Troubleshooting

### Application not reading environment variables
Make sure to export the variables before running:
```bash
export $(grep -v '^#' .env | xargs)
```

### Port already in use
Kill any existing Streamlit processes:
```bash
pkill -f streamlit
# or
lsof -i :8501  # Find process using port 8501
kill -9 <PID>  # Kill the specific process
```

### Database not found
Verify the database path exists:
```bash
ls -la /app/restorical/data/database/ecology_sites.db
```

### Authentication not working
1. Verify AUTH_TOKEN is set in `.env`
2. Restart the application to reload environment variables
3. Check that python-dotenv is installed

### Checking logs
If running with nohup:
```bash
tail -f streamlit.log
```

If running in screen:
```bash
screen -r streamlit
```

## Security Considerations

1. **Never commit `.env` files** - Keep them local to each deployment
2. **Use strong passwords** - Change default AUTH_TOKEN value
3. **Firewall configuration** - Ensure port 8501 is only accessible as needed
4. **Regular updates** - Keep dependencies updated for security patches

## Monitoring

### Check if application is running
```bash
ps aux | grep streamlit
```

### Check port binding
```bash
netstat -tlnp | grep 8501
```

### View active screen sessions
```bash
screen -ls
```

## Access
Once running, the application will be available at:
```
http://<server-ip>:8501
```

Default login password is set in the AUTH_TOKEN environment variable.