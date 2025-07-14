#!/bin/bash

# LACRM Uninstallation Script for Ubuntu
# Usage: ./uninstall.sh

set -e  # Exit on any error

echo "🗑️ LACRM System Uninstallation Script"
echo "====================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Confirmation
print_warning "This will completely remove the LACRM system from your server."
print_warning "This includes:"
print_warning "- All application files and logs"
print_warning "- Virtual environment and dependencies" 
print_warning "- Scheduled tasks (cron jobs and systemd services)"
print_warning "- Cache and database files"
echo ""
read -p "Are you sure you want to continue? [y/N]: " CONFIRM

if [[ ! $CONFIRM =~ ^[Yy]$ ]]; then
    print_status "Uninstallation cancelled."
    exit 0
fi

print_status "Starting LACRM system uninstallation..."

# Step 1: Stop all running processes
print_status "Step 1: Stopping all LACRM processes..."
sudo pkill -f lacrm_sync.py || true
sleep 2

# Check if any processes are still running
if pgrep -f lacrm_sync.py > /dev/null; then
    print_warning "Force killing remaining processes..."
    sudo pkill -9 -f lacrm_sync.py || true
fi

# Step 2: Remove systemd services and timers
print_status "Step 2: Removing systemd services..."
sudo systemctl stop lacrm-sync.service 2>/dev/null || true
sudo systemctl stop lacrm-sync.timer 2>/dev/null || true
sudo systemctl disable lacrm-sync.service 2>/dev/null || true
sudo systemctl disable lacrm-sync.timer 2>/dev/null || true

sudo rm -f /etc/systemd/system/lacrm-sync.service
sudo rm -f /etc/systemd/system/lacrm-sync.timer
sudo systemctl daemon-reload || true

# Step 3: Remove cron jobs
print_status "Step 3: Removing cron jobs..."
# Remove from current user
(crontab -l 2>/dev/null | grep -v lacrm_sync || true) | crontab - 2>/dev/null || true

# Remove from root user  
sudo bash -c '(crontab -l 2>/dev/null | grep -v lacrm_sync || true) | crontab -' 2>/dev/null || true

# Step 4: Remove installation directories
print_status "Step 4: Removing installation directories..."
INSTALL_DIRS=("/opt/RefreshLACRM" "$HOME/RefreshLACRM" "/var/www/RefreshLACRM")

for dir in "${INSTALL_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        print_status "Removing $dir..."
        sudo rm -rf "$dir"
    fi
done

# Step 5: Remove logs
print_status "Step 5: Removing system logs..."
sudo rm -f /var/log/lacrm-sync*
rm -rf ~/.cache/lacrm_sync* 2>/dev/null || true

# Step 6: Remove temporary files
print_status "Step 6: Cleaning up temporary files..."
sudo rm -rf /tmp/lacrm_* 2>/dev/null || true

# Step 7: Optional - Remove Python packages
read -p "Remove Python packages used by LACRM? [y/N]: " REMOVE_PACKAGES
if [[ $REMOVE_PACKAGES =~ ^[Yy]$ ]]; then
    print_status "Removing Python packages..."
    pip3 uninstall -y requests beautifulsoup4 lxml dnspython python-whois python-Wappalyzer openai psycopg2-binary tqdm 2>/dev/null || true
fi

# Step 8: Optional - Remove database
read -p "Remove LACRM database files? [y/N]: " REMOVE_DB
if [[ $REMOVE_DB =~ ^[Yy]$ ]]; then
    print_status "Removing database files..."
    
    # Remove SQLite databases
    rm -f ~/cache.db ~/.lacrm_cache.db /tmp/lacrm_cache.db 2>/dev/null || true
    
    # Optional PostgreSQL cleanup
    read -p "Remove PostgreSQL database 'lacrm_cache'? [y/N]: " REMOVE_POSTGRES
    if [[ $REMOVE_POSTGRES =~ ^[Yy]$ ]]; then
        sudo -u postgres dropdb lacrm_cache 2>/dev/null || true
    fi
fi

# Final verification
print_status "Step 7: Verifying uninstallation..."

REMAINING_FILES=()
for dir in "${INSTALL_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        REMAINING_FILES+=("$dir")
    fi
done

if [ ${#REMAINING_FILES[@]} -eq 0 ]; then
    print_status "✅ Uninstallation completed successfully!"
    print_status "All LACRM files and services have been removed."
else
    print_warning "⚠️ Some files may still remain:"
    for file in "${REMAINING_FILES[@]}"; do
        echo "   - $file"
    done
    print_warning "You may need to remove these manually with: sudo rm -rf [path]"
fi

# Check for running processes
if pgrep -f lacrm_sync > /dev/null; then
    print_warning "⚠️ Some LACRM processes are still running:"
    pgrep -f lacrm_sync
    print_warning "Kill them manually with: sudo pkill -9 -f lacrm_sync"
else
    print_status "✅ No LACRM processes are running."
fi

# Check for cron jobs
if crontab -l 2>/dev/null | grep -q lacrm_sync; then
    print_warning "⚠️ Some cron jobs may still exist. Check with: crontab -l"
else
    print_status "✅ No LACRM cron jobs found."
fi

echo ""
print_status "🎉 LACRM system has been uninstalled!"
print_status "Your server is now clean of LACRM components."
echo ""

exit 0
