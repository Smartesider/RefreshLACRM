# LACRM Sync - Quick Start Installation Script
# This script automates the installation process for Ubuntu servers

#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 LACRM Sync Installation Script${NC}"
echo -e "${BLUE}===================================${NC}"

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root for security reasons"
   exit 1
fi

# Step 1: Check prerequisites
echo -e "${BLUE}📋 Checking prerequisites...${NC}"

# Check Python 3
if command -v python3 &> /dev/null; then
    print_status "Python 3 found: $(python3 --version)"
else
    print_error "Python 3 is required but not installed"
    echo "Install with: sudo apt update && sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

# Check Git
if command -v git &> /dev/null; then
    print_status "Git found: $(git --version)"
else
    print_error "Git is required but not installed"
    echo "Install with: sudo apt update && sudo apt install git"
    exit 1
fi

# Step 2: Clone or update repository
echo -e "\n${BLUE}📥 Setting up repository...${NC}"

INSTALL_DIR="$HOME/RefreshLACRM"

if [ -d "$INSTALL_DIR" ]; then
    print_warning "Directory $INSTALL_DIR already exists"
    read -p "Do you want to update existing installation? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd "$INSTALL_DIR"
        git pull origin main
        print_status "Repository updated"
    else
        print_error "Installation cancelled"
        exit 1
    fi
else
    git clone https://github.com/Smartesider/RefreshLACRM.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    print_status "Repository cloned to $INSTALL_DIR"
fi

# Step 3: Set up Python virtual environment
echo -e "\n${BLUE}🐍 Setting up Python environment...${NC}"

if [ -d ".venv" ]; then
    print_warning "Virtual environment already exists"
else
    python3 -m venv .venv
    print_status "Virtual environment created"
fi

source .venv/bin/activate
print_status "Virtual environment activated"

# Install dependencies
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    print_status "Dependencies installed"
else
    print_warning "requirements.txt not found, installing basic dependencies"
    pip install requests beautifulsoup4 tqdm openai python-whois dnspython lxml
fi

# Step 4: Create configuration file
echo -e "\n${BLUE}⚙️  Setting up configuration...${NC}"

if [ -f "config.ini" ]; then
    print_warning "config.ini already exists"
    read -p "Do you want to backup and recreate it? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp config.ini config.ini.backup.$(date +%Y%m%d_%H%M%S)
        print_status "Existing config backed up"
    else
        print_status "Keeping existing configuration"
        CONFIG_EXISTS=true
    fi
fi

if [ "$CONFIG_EXISTS" != "true" ]; then
    cat > config.ini << 'EOF'
[LACRM]
UserCode = 1101F8
APIToken = 1114616-4041135154939083599611185486179-EYWOhssSyM3ZfarQ8a03UHWmB6hq4gsM6pcE7N80SChL5RNWRU

# Organization number field ID (for Pipeline custom fields)
OrgNrFieldId = 4040978325247338748089826771438

[OpenAI]
APIKey = 

[Database]
ConnectionString =

# CUSTOM FIELDS MAPPING - Field IDs discovered via API
[LACRM_CUSTOM_FIELDS]
# Company custom field IDs (found via GetCustomFields API)
orgnr = 4040961118050679815525241665363
brreg_navn = 4040961137375950075745209046981
bransje = 4040961153968796370046951924248
etablert = 4040961183001665699056571314845
antall_ansatte = 4040961209597258967327317863388
firma_epost = 4040961231502767554857411668309
nettsted = 4040961246301667987990897858695
proff_rating = 4040961268769802269769131903705
siste_regnskap = 4040961282378887710148353914819
pipeline_anbefalt = 4040961487236898177720565588689
salgsmotor_notat = 4040961516841616573015183427916
oppdateringslogg = 4040961554387658292041762072618
EOF
    print_status "Configuration file created"
fi

# Step 5: Set up directories and permissions
echo -e "\n${BLUE}📁 Setting up directories...${NC}"

mkdir -p logs cache
chmod 755 logs cache
chmod 600 config.ini
print_status "Directories created and permissions set"

# Step 6: Test installation
echo -e "\n${BLUE}🧪 Testing installation...${NC}"

echo "Testing LACRM connection..."
if python lacrm_sync.py --show-fields > /dev/null 2>&1; then
    print_status "LACRM connection successful"
else
    print_warning "LACRM connection test failed - check your API credentials"
fi

echo "Testing with sample organization number..."
if python lacrm_sync.py --oppdater 918124306 --dry-run > /dev/null 2>&1; then
    print_status "Data enrichment test successful"
else
    print_warning "Data enrichment test failed - check network connectivity"
fi

# Step 7: Set up automation
echo -e "\n${BLUE}⏰ Setting up automation...${NC}"

read -p "Do you want to set up daily automatic sync at 3 AM? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python lacrm_sync.py --cron
    print_status "Daily automation configured"
else
    print_status "Skipping automation setup"
fi

# Step 8: Final instructions
echo -e "\n${GREEN}🎉 Installation Complete!${NC}"
echo -e "${BLUE}=========================${NC}"
echo
echo -e "${YELLOW}Quick Start Commands:${NC}"
echo "cd $INSTALL_DIR"
echo "source .venv/bin/activate"
echo
echo -e "${YELLOW}Test commands:${NC}"
echo "python lacrm_sync.py --show-fields                    # Show custom fields"
echo "python lacrm_sync.py --sync-lacrm --dry-run           # Test sync (no changes)"
echo "python lacrm_sync.py --oppdater 918124306             # Test single company"
echo
echo -e "${YELLOW}Production commands:${NC}"
echo "python lacrm_sync.py --sync-lacrm --update-missing-orgnr  # Full sync"
echo "python lacrm_sync.py --sync-lacrm --debug                 # Debug mode"
echo
echo -e "${YELLOW}Files and directories:${NC}"
echo "Configuration: $INSTALL_DIR/config.ini"
echo "Logs: $INSTALL_DIR/logs/sync.log"
echo "Cache: $INSTALL_DIR/cache/"
echo
echo -e "${GREEN}✅ System ready for production use!${NC}"

# Add convenience alias
echo
read -p "Do you want to add a convenience alias 'lacrm-sync' to your shell? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ALIAS_CMD="alias lacrm-sync='cd $INSTALL_DIR && source .venv/bin/activate && python lacrm_sync.py'"
    echo "$ALIAS_CMD" >> ~/.bashrc
    echo "alias lacrm-sync='cd $INSTALL_DIR && source .venv/bin/activate && python lacrm_sync.py'" >> ~/.bash_aliases 2>/dev/null || true
    print_status "Alias 'lacrm-sync' added to your shell"
    echo "Reload your shell with: source ~/.bashrc"
    echo "Then use: lacrm-sync --sync-lacrm"
fi

echo
print_status "Installation completed successfully!"
print_status "Check logs/sync.log for detailed execution logs"
