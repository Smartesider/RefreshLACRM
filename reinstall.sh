#!/bin/bash

# LACRM Reinstallation Script for Ubuntu
# Usage: ./reinstall.sh

set -e  # Exit on any error

echo "🚀 LACRM System Reinstallation Script"
echo "===================================="

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

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root. Run as regular user with sudo access."
   exit 1
fi

print_status "Starting LACRM system reinstallation..."

# Step 1: Remove existing installation
print_status "Step 1: Cleaning up existing installation..."

# Stop any running processes
print_status "Stopping any running LACRM processes..."
sudo pkill -f lacrm_sync.py || true

# Remove cron jobs
print_status "Removing cron jobs..."
(crontab -l 2>/dev/null | grep -v lacrm_sync || true) | crontab - || true

# Remove old installation directories
INSTALL_DIRS=("/opt/RefreshLACRM" "$HOME/RefreshLACRM" "/var/www/RefreshLACRM")
for dir in "${INSTALL_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        print_status "Removing old installation at $dir..."
        sudo rm -rf "$dir"
    fi
done

# Step 2: Update system
print_status "Step 2: Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Step 3: Install dependencies
print_status "Step 3: Installing system dependencies..."
sudo apt install -y python3 python3-pip python3-venv git curl htop nano vim tree

# Step 4: Choose installation directory
read -p "Install location [/opt/RefreshLACRM]: " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-/opt/RefreshLACRM}

print_status "Installing to: $INSTALL_DIR"

# Step 5: Clone repository
print_status "Step 4: Cloning repository..."
sudo git clone https://github.com/Smartesider/RefreshLACRM.git "$INSTALL_DIR"
sudo chown -R $USER:$USER "$INSTALL_DIR"

# Step 6: Setup virtual environment
print_status "Step 5: Setting up Python virtual environment..."
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate

# Step 7: Install Python packages
print_status "Step 6: Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Step 8: Setup configuration
print_status "Step 7: Setting up configuration..."
if [ ! -f config.ini ]; then
    cp config.ini.example config.ini
    print_warning "Please edit config.ini with your API credentials:"
    print_warning "nano $INSTALL_DIR/config.ini"
fi

# Step 9: Create logs directory
print_status "Step 8: Creating logs directory..."
mkdir -p logs
chmod 755 logs

# Step 10: Test installation
print_status "Step 9: Testing installation..."
if python3 lacrm_sync.py --help > /dev/null 2>&1; then
    print_status "✅ Installation successful!"
else
    print_error "❌ Installation test failed"
    exit 1
fi

# Step 11: Setup systemd service (optional)
read -p "Setup systemd service for automated runs? [y/N]: " SETUP_SERVICE
if [[ $SETUP_SERVICE =~ ^[Yy]$ ]]; then
    print_status "Setting up systemd service..."
    
    sudo tee /etc/systemd/system/lacrm-sync.service > /dev/null <<EOF
[Unit]
Description=LACRM Sync Service
After=network.target

[Service]
Type=oneshot
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/lacrm_sync.py --sync-lacrm --update-missing-orgnr
StandardOutput=append:$INSTALL_DIR/logs/sync.log
StandardError=append:$INSTALL_DIR/logs/sync.log

[Install]
WantedBy=multi-user.target
EOF

    sudo tee /etc/systemd/system/lacrm-sync.timer > /dev/null <<EOF
[Unit]
Description=Run LACRM Sync Daily
Requires=lacrm-sync.service

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable lacrm-sync.timer
    sudo systemctl start lacrm-sync.timer
    
    print_status "✅ Systemd service and timer configured"
    print_status "Check status with: sudo systemctl status lacrm-sync.timer"
fi

# Final instructions
echo ""
print_status "🎉 Installation Complete!"
echo ""
print_status "Next steps:"
echo "1. Edit configuration: nano $INSTALL_DIR/config.ini"
echo "2. Find Custom Field IDs: cd $INSTALL_DIR && source venv/bin/activate && python3 lacrm_sync.py --show-fields"
echo "3. Test with dry run: python3 lacrm_sync.py --sync-lacrm --dry-run"
echo "4. View logs: tail -f $INSTALL_DIR/logs/sync.log"
echo ""
print_status "Installation directory: $INSTALL_DIR"
print_status "Activate virtual environment: source $INSTALL_DIR/venv/bin/activate"
echo ""

exit 0
