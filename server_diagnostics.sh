#!/bin/bash

# Server Diagnostics Script
# Run this on your DigitalOcean droplet to gather system information
# Usage: bash server_diagnostics.sh

echo "=========================================="
echo "   SERVER DIAGNOSTICS REPORT"
echo "   Generated: $(date)"
echo "=========================================="
echo ""

echo "=========================================="
echo "1. SYSTEM INFORMATION"
echo "=========================================="
echo "Hostname: $(hostname)"
echo "IP Address: $(hostname -I | awk '{print $1}')"
echo "Kernel: $(uname -r)"
echo "OS: $(lsb_release -d 2>/dev/null | cut -f2 || cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
echo "Uptime: $(uptime -p)"
echo ""

echo "=========================================="
echo "2. LISTENING PORTS & SERVICES"
echo "=========================================="
echo "Active network connections (listening):"
sudo netstat -tlnp 2>/dev/null || sudo ss -tlnp
echo ""

echo "=========================================="
echo "3. SPECIFIC APPLICATION PORTS"
echo "=========================================="
echo "=== Port 8501 ==="
sudo lsof -i :8501 2>/dev/null || echo "Nothing found on port 8501"
echo ""
echo "=== Port 5001 ==="
sudo lsof -i :5001 2>/dev/null || echo "Nothing found on port 5001"
echo ""
echo "=== Port 22 (SSH) ==="
sudo lsof -i :22 2>/dev/null || echo "Nothing found on port 22"
echo ""

echo "=========================================="
echo "4. RUNNING PROCESSES (Top 20 by CPU)"
echo "=========================================="
ps aux --sort=-%cpu | head -20
echo ""

echo "=========================================="
echo "5. KEY SERVICES STATUS"
echo "=========================================="
echo "=== Web & Application Servers ==="
for service in nginx apache2 httpd python python3 node docker; do
    if command -v $service &> /dev/null; then
        echo "✓ $service is installed ($(command -v $service))"
        if [[ "$service" == "docker" ]]; then
            docker --version 2>/dev/null
        elif [[ "$service" == "nginx" ]]; then
            nginx -v 2>&1
        elif [[ "$service" == "apache2" ]] || [[ "$service" == "httpd" ]]; then
            apache2 -v 2>/dev/null || httpd -v 2>/dev/null
        elif [[ "$service" == "python" ]] || [[ "$service" == "python3" ]]; then
            $service --version 2>/dev/null
        elif [[ "$service" == "node" ]]; then
            node --version 2>/dev/null
        fi
    else
        echo "✗ $service is not installed"
    fi
done
echo ""

echo "=========================================="
echo "6. SYSTEMD SERVICES (Running)"
echo "=========================================="
systemctl list-units --type=service --state=running --no-pager | grep -E 'loaded active running' | awk '{print $1, $4, $5, $6, $7, $8, $9, $10}'
echo ""

echo "=========================================="
echo "7. DOCKER CONTAINERS (if Docker installed)"
echo "=========================================="
if command -v docker &> /dev/null; then
    echo "=== Running Containers ==="
    sudo docker ps 2>/dev/null || docker ps 2>/dev/null || echo "No running containers or Docker not accessible"
    echo ""
    echo "=== All Containers ==="
    sudo docker ps -a 2>/dev/null || docker ps -a 2>/dev/null || echo "No containers found"
else
    echo "Docker is not installed"
fi
echo ""

echo "=========================================="
echo "8. FIREWALL STATUS"
echo "=========================================="
echo "=== UFW Status ==="
sudo ufw status verbose 2>/dev/null || echo "UFW not configured or not installed"
echo ""
echo "=== IPTables Rules (first 20 lines) ==="
sudo iptables -L -n -v 2>/dev/null | head -20 || echo "Cannot read iptables"
echo ""

echo "=========================================="
echo "9. RESOURCE USAGE"
echo "=========================================="
echo "=== Memory Usage ==="
free -h
echo ""
echo "=== Disk Usage ==="
df -h
echo ""
echo "=== CPU Info ==="
lscpu | grep -E "Model name|CPU\(s\)|Thread|Core|Socket"
echo ""

echo "=========================================="
echo "10. APPLICATION DIRECTORIES"
echo "=========================================="
echo "=== /home directory ==="
ls -la /home/ 2>/dev/null | head -10
echo ""
echo "=== /var/www directory ==="
ls -la /var/www/ 2>/dev/null | head -10 || echo "/var/www not found"
echo ""
echo "=== /opt directory ==="
ls -la /opt/ 2>/dev/null | head -10 || echo "/opt is empty or not accessible"
echo ""
echo "=== /srv directory ==="
ls -la /srv/ 2>/dev/null | head -10 || echo "/srv is empty or not accessible"
echo ""

echo "=========================================="
echo "11. SYSTEMD SERVICE FILES"
echo "=========================================="
ls -la /etc/systemd/system/*.service 2>/dev/null | tail -20 || echo "No custom systemd services found"
echo ""

echo "=========================================="
echo "12. PYTHON/NODE PROCESSES"
echo "=========================================="
echo "=== Python Processes ==="
ps aux | grep -E '[p]ython|[p]ython3' | grep -v grep
echo ""
echo "=== Node Processes ==="
ps aux | grep -E '[n]ode|[n]pm' | grep -v grep
echo ""

echo "=========================================="
echo "13. RECENT LOGINS"
echo "=========================================="
last -10
echo ""

echo "=========================================="
echo "14. CRON JOBS"
echo "=========================================="
echo "=== Root crontab ==="
sudo crontab -l 2>/dev/null || echo "No root cron jobs"
echo ""
echo "=== User crontabs ==="
for user in $(ls /home/); do
    echo "User: $user"
    sudo -u $user crontab -l 2>/dev/null || echo "  No cron jobs for $user"
done
echo ""

echo "=========================================="
echo "15. INSTALLED PACKAGES (Key ones)"
echo "=========================================="
if command -v dpkg &> /dev/null; then
    echo "=== Web/App Related Packages ==="
    dpkg -l 2>/dev/null | grep -E 'nginx|apache|python|node|docker|mysql|postgres|redis|mongodb' | awk '{print $2, $3}'
elif command -v rpm &> /dev/null; then
    echo "=== Web/App Related Packages ==="
    rpm -qa | grep -E 'nginx|apache|python|node|docker|mysql|postgres|redis|mongodb'
else
    echo "Package manager not recognized"
fi
echo ""

echo "=========================================="
echo "   END OF DIAGNOSTICS REPORT"
echo "=========================================="
echo ""
echo "Script completed at: $(date)"
echo "Save this output for analysis"