# Deployment Plan for Eco Site Analytics (Streamlit App)

## Overview

This deployment plan outlines the steps to deploy the Eco Site Analytics Streamlit application to a DigitalOcean droplet as a companion app to the existing EndToEndQualificationV3 FastHTML application. The apps will share the same database but run independently.

## Architecture

```
DigitalOcean Droplet (162.243.186.65)
├── /app/
│   ├── restorical/           # Existing FastHTML app (Port 5001)
│   │   ├── data/
│   │   │   └── database/
│   │   │       └── ecology_sites.db  # Shared database
│   │   └── ...
│   └── eco-analytics/        # New Streamlit app (Port 8501)
│       ├── .venv/            # Separate virtual environment
│       ├── streamlit_app.py
│       ├── app_lib/
│       ├── pages/
│       └── requirements.txt
```

## Pre-Deployment Checklist

- [ ] Create GitHub repository for Eco Site Analytics
- [ ] Push current code to GitHub repository
- [ ] Ensure database path configuration uses environment variable
- [ ] Test locally with shared database path
- [ ] Document any environment-specific configurations

## Deployment Stages

### Stage 1: Repository Setup (Local)

1. **Initialize Git Repository**
```bash
cd /Users/darrensilver/python_projects/Restorical/Eco_Site_Analytics
git init
git add .
git commit -m "Initial commit: Eco Site Analytics Streamlit app"
```

2. **Create GitHub Repository**
```bash
# Create a new repository on GitHub named 'eco-site-analytics'
# Then add remote:
git remote add origin https://github.com/YOUR_USERNAME/eco-site-analytics.git
git branch -M main
git push -u origin main
```

3. **Update Configuration for Deployment**

Create a `.env.example` file:
```bash
# Database Configuration
ECO_DB_PATH=/app/restorical/data/database/ecology_sites.db

# API Configuration  
PROCESS_API_BASE=http://localhost:5001
PROCESS_API_TOKEN=secret123

# Streamlit Configuration
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
```

### Stage 2: Server Deployment

#### 2.1 Connect to Server
```bash
ssh root@162.243.186.65
```

#### 2.2 Create Application Directory
```bash
# Create directory for Streamlit app
mkdir -p /app/eco-analytics
cd /app/eco-analytics

# Clone repository
git clone https://github.com/YOUR_USERNAME/eco-site-analytics.git .
```

#### 2.3 Set Up Python Environment
```bash
# Create virtual environment (separate from FastHTML app)
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

#### 2.4 Configure Environment
```bash
# Create .env file with production settings
cat > .env << 'EOF'
# Database Configuration (shared with FastHTML app)
ECO_DB_PATH=/app/restorical/data/database/ecology_sites.db

# API Configuration (FastHTML app endpoints)
PROCESS_API_BASE=http://localhost:5001
PROCESS_API_TOKEN=secret123

# Streamlit Configuration
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
EOF

# Create Streamlit config
mkdir -p .streamlit
cat > .streamlit/config.toml << 'EOF'
[server]
port = 8501
address = "0.0.0.0"
headless = true

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#059669"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
EOF
```

#### 2.5 Configure Firewall
```bash
# Open port for Streamlit
ufw allow 8501/tcp
ufw reload
```

#### 2.6 Test Application
```bash
# Activate virtual environment
source /app/eco-analytics/.venv/bin/activate

# Set environment variables
export $(cat .env | xargs)

# Run Streamlit app
streamlit run streamlit_app.py

# Test in browser: http://162.243.186.65:8501
```

### Stage 3: Persistent Running with Screen

#### 3.1 Create Start Script
```bash
cat > /app/eco-analytics/start_app.sh << 'EOF'
#!/bin/bash
cd /app/eco-analytics
source .venv/bin/activate
export $(cat .env | xargs)
streamlit run streamlit_app.py
EOF

chmod +x /app/eco-analytics/start_app.sh
```

#### 3.2 Run with Screen
```bash
# Start new screen session
screen -S eco-analytics

# Run the app
/app/eco-analytics/start_app.sh

# Detach from screen: Ctrl+A, then D
# Reattach later: screen -r eco-analytics
```

### Stage 4: Systemd Service (Production)

#### 4.1 Create Service File
```bash
cat > /etc/systemd/system/eco-analytics.service << 'EOF'
[Unit]
Description=Eco Site Analytics Streamlit App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/app/eco-analytics
Environment="PATH=/app/eco-analytics/.venv/bin"
EnvironmentFile=/app/eco-analytics/.env
ExecStart=/app/eco-analytics/.venv/bin/streamlit run streamlit_app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

#### 4.2 Enable and Start Service
```bash
# Reload systemd
systemctl daemon-reload

# Enable service to start on boot
systemctl enable eco-analytics

# Start service
systemctl start eco-analytics

# Check status
systemctl status eco-analytics

# View logs
journalctl -u eco-analytics -f
```

### Stage 5: Update Automation

#### 5.1 Create Update Script
```bash
cat > /app/eco-analytics/update_app.sh << 'EOF'
#!/bin/bash
set -e

echo "==================================="
echo "Updating Eco Site Analytics"
echo "==================================="

cd /app/eco-analytics

# Pull latest changes
echo "Pulling latest changes from GitHub..."
git pull origin main

# Activate virtual environment
source .venv/bin/activate

# Update dependencies if requirements.txt changed
if git diff HEAD@{1} --name-only | grep -q "requirements.txt"; then
    echo "Updating Python dependencies..."
    pip install -r requirements.txt
fi

# Restart service
echo "Restarting application..."
if systemctl is-active --quiet eco-analytics; then
    systemctl restart eco-analytics
    echo "Service restarted successfully"
else
    echo "Starting in screen session..."
    screen -dmS eco-analytics ./start_app.sh
    echo "Application started in screen"
fi

echo "Update complete!"
echo "Check application at: http://162.243.186.65:8501"
EOF

chmod +x /app/eco-analytics/update_app.sh
```

## Monitoring and Maintenance

### Health Checks

Create a health check endpoint in Streamlit:
```python
# Add to streamlit_app.py
import streamlit as st

# Health check endpoint (accessible via /_stcore/health)
if st.query_params.get("health") == "check":
    st.success("Healthy")
    st.stop()
```

### Log Monitoring
```bash
# View Streamlit logs (if using systemd)
journalctl -u eco-analytics -f

# View Streamlit logs (if using screen)
screen -r eco-analytics

# Check application logs
tail -f /app/eco-analytics/logs/*.log
```

### Database Monitoring
```bash
# Check database size
du -sh /app/restorical/data/database/ecology_sites.db

# Verify database accessibility
sqlite3 /app/restorical/data/database/ecology_sites.db "SELECT COUNT(*) FROM sites;"
```

## Nginx Reverse Proxy Setup (Optional)

For production with domain name and SSL:

```nginx
# /etc/nginx/sites-available/eco-analytics
server {
    listen 80;
    server_name analytics.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    location /_stcore/stream {
        proxy_pass http://127.0.0.1:8501/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }
}
```

## Troubleshooting

### Common Issues and Solutions

1. **Database Connection Issues**
```bash
# Check database file permissions
ls -la /app/restorical/data/database/ecology_sites.db

# Test database connection
python3 -c "import sqlite3; conn = sqlite3.connect('/app/restorical/data/database/ecology_sites.db'); print('Connected successfully')"
```

2. **Port Already in Use**
```bash
# Check what's using port 8501
lsof -i :8501

# Kill process if needed
kill -9 <PID>
```

3. **Streamlit Not Loading**
```bash
# Check if Streamlit is running
ps aux | grep streamlit

# Check network connectivity
netstat -tlnp | grep 8501

# Restart service
systemctl restart eco-analytics
```

4. **Memory Issues**
```bash
# Check memory usage
free -h

# Monitor with htop
htop

# If needed, restart to free memory
systemctl restart eco-analytics
```

## Security Considerations

1. **Database Access**: Read-only access to shared database
2. **Network Security**: Firewall configured to only allow necessary ports
3. **API Authentication**: Process API uses token-based auth
4. **Environment Variables**: Sensitive data stored in .env file
5. **Updates**: Regular security updates via `apt update && apt upgrade`

## Backup Strategy

Since this app only reads from the database (no writes), backups are handled by the main FastHTML application. However, code backups are maintained via Git.

## Quick Reference Commands

```bash
# SSH to server
ssh root@162.243.186.65

# Navigate to app
cd /app/eco-analytics

# Update application
./update_app.sh

# View logs (systemd)
journalctl -u eco-analytics -f

# View logs (screen)
screen -r eco-analytics

# Restart application (systemd)
systemctl restart eco-analytics

# Restart application (screen)
screen -X -S eco-analytics quit
screen -dmS eco-analytics ./start_app.sh

# Check status
systemctl status eco-analytics

# Test locally
curl http://localhost:8501

# Test from internet
curl http://162.243.186.65:8501
```

## Next Steps

1. [ ] Create GitHub repository
2. [ ] Push code to repository
3. [ ] Deploy to server following Stage 2
4. [ ] Test with shared database
5. [ ] Configure persistent running (Stage 3 or 4)
6. [ ] Set up monitoring
7. [ ] Document API endpoints for team
8. [ ] Consider adding domain/SSL with Nginx

## Support Contact

For deployment issues:
- Check logs first: `journalctl -u eco-analytics -f`
- Verify database path: `ls -la /app/restorical/data/database/`
- Test network: `netstat -tlnp | grep 8501`
- Review this document for troubleshooting steps