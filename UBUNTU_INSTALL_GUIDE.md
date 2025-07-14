# Ubuntu Server - Avinstallasjon og Reinstallasjon Guide 🐧

## 🗑️ Komplett Avinstallasjon

### Steg 1: Stopp alle kjørende prosesser
```bash
# Stopp eventuelle cron-jobber
sudo crontab -l | grep -v "lacrm_sync.py" | sudo crontab -

# Kill alle Python-prosesser relatert til scriptet
sudo pkill -f lacrm_sync.py

# Sjekk at alt er stoppet
ps aux | grep lacrm_sync
```

### Steg 2: Fjern scheduled tasks
```bash
# Fjern cron-jobber
sudo crontab -r  # Fjerner alle cron-jobber for root
crontab -r       # Fjerner alle cron-jobber for current user

# Eller mer selektivt:
crontab -l | grep -v "lacrm_sync" | crontab -
```

### Steg 3: Fjern prosjektmappen og virtual environment
```bash
# Gå til hjemmemappen
cd ~

# Fjern hele prosjektmappen (FORSIKTIG!)
sudo rm -rf RefreshLACRM/

# Eller hvis du installerte det et annet sted:
sudo rm -rf /opt/RefreshLACRM/
sudo rm -rf /var/www/RefreshLACRM/
```

### Steg 4: Fjern Python-dependencies (valgfritt)
```bash
# Hvis du vil fjerne alle Python-pakker systemet brukte
pip3 uninstall -y requests beautifulsoup4 lxml dnspython python-whois python-Wappalyzer openai psycopg2-binary tqdm

# Eller hvis du brukte system packages:
sudo apt remove python3-requests python3-bs4 python3-lxml python3-dnspython python3-openai
sudo apt autoremove
```

### Steg 5: Rydd opp databaser (hvis brukt)
```bash
# Hvis du brukte PostgreSQL
sudo -u postgres dropdb lacrm_cache

# Hvis du brukte SQLite, slett databasefilen
rm -f ~/RefreshLACRM/cache.db
rm -f /tmp/lacrm_cache.db
```

### Steg 6: Fjern logger og cache
```bash
# Fjern eventuelle logger
sudo rm -rf /var/log/lacrm_sync*
rm -rf ~/.cache/lacrm_sync*

# Fjern temp-filer
sudo rm -rf /tmp/lacrm_*
```

## 🚀 Komplett Reinstallasjon

### Steg 1: Oppdater systemet
```bash
sudo apt update && sudo apt upgrade -y
```

### Steg 2: Installer påkrevde system-pakker
```bash
# Python og pip
sudo apt install python3 python3-pip python3-venv git curl -y

# Nyttige verktøy
sudo apt install htop nano vim tree -y
```

### Steg 3: Clone prosjektet fra GitHub
```bash
# Gå til ønsket mappe (f.eks. /opt for system-wide installasjon)
cd /opt
sudo git clone https://github.com/Smartesider/RefreshLACRM.git
sudo chown -R $USER:$USER RefreshLACRM/

# Eller i hjemmemappen
cd ~
git clone https://github.com/Smartesider/RefreshLACRM.git
```

### Steg 4: Sett opp Python Virtual Environment
```bash
cd RefreshLACRM

# Opprett virtual environment
python3 -m venv venv

# Aktiver virtual environment
source venv/bin/activate

# Oppgrader pip
pip install --upgrade pip
```

### Steg 5: Installer Python-dependencies
```bash
# Installer alle nødvendige pakker
pip install -r requirements.txt

# Eller manuelt hvis requirements.txt mangler:
pip install requests beautifulsoup4 lxml dnspython python-whois python-Wappalyzer openai psycopg2-binary tqdm
```

### Steg 6: Konfigurer systemet
```bash
# Kopier konfigurasjonsfilen
cp config.ini.example config.ini

# Rediger konfigurasjonen med dine API-nøkler
nano config.ini
```

**Fyll inn disse verdiene:**
```ini
[LACRM]
UserCode = DIN_LACRM_USERCODE
APIToken = DIN_LACRM_API_TOKEN
OrgNrFieldId = DITT_ORGNR_FIELD_ID

[OpenAI]
APIKey = DIN_OPENAI_API_KEY

[Database]
ConnectionString = sqlite:///cache.db
```

### Steg 7: Test installasjonen
```bash
# Test grunnleggende funksjonalitet
python3 lacrm_sync.py --show-fields

# Test med en enkelt bedrift (dry-run)
python3 lacrm_sync.py --oppdater 923609016 --dry-run

# Test full sync (dry-run)
python3 lacrm_sync.py --sync-lacrm --dry-run
```

### Steg 8: Sett opp automatisk kjøring (valgfritt)
```bash
# Rediger crontab
crontab -e

# Legg til denne linjen for daglig kjøring kl 03:00:
0 3 * * * cd /opt/RefreshLACRM && source venv/bin/activate && python3 lacrm_sync.py --sync-lacrm --update-missing-orgnr >> logs/cron.log 2>&1

# Eller bruk det innebygde cron-setupet:
python3 lacrm_sync.py --cron
```

### Steg 9: Sett opp logging
```bash
# Opprett log-mappe
mkdir -p logs

# Sett riktige tillatelser
chmod 755 logs
chmod 644 logs/*.log 2>/dev/null || true

# Test logging
python3 lacrm_sync.py --oppdater 923609016 --debug --dry-run
```

### Steg 10: Sett opp systemd service (anbefalt for produksjon)
```bash
# Opprett service-fil
sudo nano /etc/systemd/system/lacrm-sync.service
```

**Innhold av service-filen:**
```ini
[Unit]
Description=LACRM Sync Service
After=network.target

[Service]
Type=oneshot
User=www-data
Group=www-data
WorkingDirectory=/opt/RefreshLACRM
Environment=PATH=/opt/RefreshLACRM/venv/bin
ExecStart=/opt/RefreshLACRM/venv/bin/python /opt/RefreshLACRM/lacrm_sync.py --sync-lacrm --update-missing-orgnr
StandardOutput=append:/var/log/lacrm-sync.log
StandardError=append:/var/log/lacrm-sync.log

[Install]
WantedBy=multi-user.target
```

**Aktiver systemd service:**
```bash
# Reload systemd
sudo systemctl daemon-reload

# Test service
sudo systemctl start lacrm-sync.service
sudo systemctl status lacrm-sync.service

# Se logger
sudo journalctl -u lacrm-sync.service -f

# Sett opp timer for daglig kjøring
sudo nano /etc/systemd/system/lacrm-sync.timer
```

**Timer-konfigurasjon:**
```ini
[Unit]
Description=Run LACRM Sync Daily
Requires=lacrm-sync.service

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

**Aktiver timer:**
```bash
sudo systemctl enable lacrm-sync.timer
sudo systemctl start lacrm-sync.timer
sudo systemctl status lacrm-sync.timer
```

## 🔍 Verifisering av installasjon

### Sjekk at alt fungerer:
```bash
# Sjekk Python-environment
source venv/bin/activate
python3 --version
pip list | grep -E "(requests|openai|beautifulsoup4)"

# Sjekk konfigurasjon
python3 lacrm_sync.py --show-fields

# Sjekk cron/systemd
sudo systemctl list-timers | grep lacrm
crontab -l

# Sjekk logger
tail -f logs/sync.log

# Test full funksjonalitet
python3 lacrm_sync.py --sync-lacrm --dry-run --debug
```

## 🆘 Feilsøking

### Vanlige problemer:

**1. Permission denied:**
```bash
sudo chown -R $USER:$USER /opt/RefreshLACRM/
chmod +x lacrm_sync.py
```

**2. Python module ikke funnet:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

**3. API-feil:**
```bash
# Sjekk config.ini
cat config.ini
python3 lacrm_sync.py --show-fields --debug
```

**4. Cron kjører ikke:**
```bash
sudo systemctl status cron
sudo journalctl -u cron -f
```

**5. Database-problemer:**
```bash
rm -f cache.db
python3 lacrm_sync.py --oppdater 923609016 --debug
```

## 📊 Overvåking

### Sett opp enkel overvåking:
```bash
# Opprett monitoring script
nano monitor_lacrm.sh
```

**Monitor script:**
```bash
#!/bin/bash
LOG_FILE="/opt/RefreshLACRM/logs/sync.log"
LAST_RUN=$(tail -n 100 $LOG_FILE | grep "Successfully" | tail -1)

if [ -z "$LAST_RUN" ]; then
    echo "WARNING: No successful runs found in recent logs"
    exit 1
else
    echo "Last successful run: $LAST_RUN"
    exit 0
fi
```

```bash
chmod +x monitor_lacrm.sh

# Test monitoring
./monitor_lacrm.sh
```

## 🔄 Oppdatering av systemet

### For å oppdatere til nyeste versjon:
```bash
cd /opt/RefreshLACRM
git pull origin main
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

Nå har du en komplett guide for å avinstallere og reinstallere systemet på Ubuntu-serveren din! 🎉
