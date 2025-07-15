# LACRM Sync - Komplett Installasjonsveiledning

## 📋 Oversikt
Dette systemet automatiserer synkronisering av bedriftsdata mellom norske registre (Brønnøysund, Proff.no) og Less Annoying CRM (LACRM).

## 🚀 Installasjon på Ubuntu Server

### Trinn 1: Last ned prosjektet
```bash
# Klon repositoriet
git clone https://github.com/Smartesider/RefreshLACRM.git
cd RefreshLACRM

# Eller oppdater eksisterende installasjon
git pull origin main
```

### Trinn 2: Sett opp Python-miljø
```bash
# Opprett virtuelt miljø
python3 -m venv .venv

# Aktiver miljøet
source .venv/bin/activate

# Installer avhengigheter
pip install -r requirements.txt
```

### Trinn 3: Konfigurer systemet
```bash
# Kopier og rediger konfigurasjonsfilen
cp config.ini.example config.ini
nano config.ini
```

**Sett inn denne konfigurasjonen i config.ini:**
```ini
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
```

### Trinn 4: Sikre tilganger
```bash
# Sikre konfigurasjonsfilen
chmod 600 config.ini

# Opprett nødvendige mapper
mkdir -p logs cache
chmod 755 logs cache
```

### Trinn 5: Test installasjonen
```bash
# Test at systemet kan koble til LACRM
python lacrm_sync.py --show-fields

# Test synkronisering med én bedrift
python lacrm_sync.py --oppdater 918124306 --debug

# Test full synkronisering (uten endringer)
python lacrm_sync.py --sync-lacrm --update-missing-orgnr --dry-run
```

### Trinn 6: Sett opp automatisering
```bash
# Automatisk daglig kjøring kl 03:00
python lacrm_sync.py --cron

# Eller manuell crontab-redigering
crontab -e
# Legg til:
# 0 3 * * * /path/to/RefreshLACRM/.venv/bin/python /path/to/RefreshLACRM/lacrm_sync.py --sync-lacrm --update-missing-orgnr
```

## 🔧 Hovedkommandoer

### Grunnleggende operasjoner
```bash
# Vis alle tilgjengelige custom fields
python lacrm_sync.py --show-fields

# Synkroniser alle bedrifter i LACRM
python lacrm_sync.py --sync-lacrm

# Finn og legg til manglende organisasjonsnummer
python lacrm_sync.py --sync-lacrm --update-missing-orgnr

# Kjør uten å gjøre endringer (test)
python lacrm_sync.py --sync-lacrm --dry-run

# Debug-modus med detaljert logging
python lacrm_sync.py --sync-lacrm --update-missing-orgnr --debug
```

### Enkeltstående bedrift
```bash
# Oppdater én bedrift med organisasjonsnummer
python lacrm_sync.py --oppdater 918124306

# Med anbefalinger og tvungen oppdatering
python lacrm_sync.py --oppdater 918124306 --anbefalinger --tving
```

## 📊 Hva systemet gjør

### 1. Identifiserer bedrifter
- Finner bedrifter med `IsCompany="1"`
- Finner kontakter med `CompanyName` satt
- Totalt identifisert: **5 bedrifter** i ditt LACRM

### 2. Organisasjonsnummer-behandling
- Søker automatisk etter manglende org.nr via Brønnøysund
- Oppdaterer LACRM med funnet org.nr
- Validerer eksisterende org.nr

### 3. Databerikelse
- **Brønnøysund Register**: Grunndata, bransje, ansatte, stiftelsesdato
- **Proff.no**: Finansielle nøkkeltall, kontaktinfo, kredittrating
- **Domenehelse**: SSL, DNS, teknisk stack
- **Sosiale medier**: LinkedIn, Facebook, Instagram

### 4. LACRM-synkronisering
Oppdaterer disse custom fields automatisk:
- `orgnr`: Organisasjonsnummer (lenke til Brønnøysund)
- `brreg_navn`: Offisielt firmanavn
- `bransje`: NACE-kode beskrivelse
- `etablert`: Stiftelsesdato
- `antall_ansatte`: Antall registrerte ansatte
- `firma_epost`: Bedriftens e-post
- `nettsted`: Hjemmeside URL
- `proff_rating`: Finansiell vurdering (Stabil/Risiko/Ukjent)
- `siste_regnskap`: Siste regnskapsdata
- `pipeline_anbefalt`: AI-generert salgsanbefaling
- `salgsmotor_notat`: Detaljerte AI-analyser og anbefalinger
- `oppdateringslogg`: Tidsstempel for siste oppdatering

### 5. Salgsanbefalinger (Pipeline)
Systemet genererer automatisk pipeline-elementer basert på:
- Bedriftens alder (Startup-pakke for <2 år)
- Manglende/dårlig nettside (Webdesign)
- Sikkerhetsproblemer (SSL-oppgradering)
- Uprofesjonell e-post (Gmail/Hotmail → Profesjonell e-post)
- Bransjeanalyse og konkurransesituasjon
- Finansiell helse og vekstpotensial

## 🔍 Monitorering

### Loggfiler
```bash
# Se systemlogger
tail -f logs/sync.log

# Søk etter feil
grep -i error logs/sync.log

# Se kun today's aktivitet
grep "$(date +%Y-%m-%d)" logs/sync.log
```

### Cache-system
```bash
# Se cached data for en bedrift
cat cache/918124306.json | python -m json.tool

# Rens cache (tvinger ny data-henting)
rm cache/*.json
```

### Status-sjekk
```bash
# Test LACRM-tilkobling
python lacrm_sync.py --show-fields | head -10

# Verifier custom fields mapping
python -c "import configparser; c=configparser.ConfigParser(); c.read('config.ini'); print('Custom fields configured:', len(c['LACRM_CUSTOM_FIELDS']))"
```

## 🚨 Feilsøking

### Vanlige problemer

**1. API-tilkoblingsfeil**
```bash
# Test nettverkstilkobling
curl -I https://api.lessannoyingcrm.com
curl -I https://data.brreg.no

# Sjekk API-legitimasjon
python -c "import requests; print(requests.post('https://api.lessannoyingcrm.com', data={'UserCode':'1101F8','APIToken':'[DIN_TOKEN]','Function':'GetCustomFields'}).status_code)"
```

**2. Custom fields ikke funnet**
```bash
# Refresh custom fields mapping
python lacrm_sync.py --show-fields > custom_fields_backup.txt
```

**3. Ingen bedrifter funnet**
```bash
# Debug bedriftidentifikasjon
python lacrm_sync.py --sync-lacrm --debug 2>&1 | grep -A5 -B5 "Found.*company"
```

### Gjenopprett fra backup
```bash
# Hvis noe går galt, gjenopprett fra Git
git reset --hard HEAD
git pull origin main
```

## 🔐 Sikkerhet

### Systemherdening
```bash
# Opprett dedikert bruker
sudo useradd -m -s /bin/bash lacrmsync
sudo chown -R lacrmsync:lacrmsync /path/to/RefreshLACRM

# Begrens tilganger
chmod 700 /path/to/RefreshLACRM
chmod 600 config.ini
```

### Miljøvariabler (alternativ til config.ini)
```bash
# Eksporter sensitive data som miljøvariabler
export LACRM_API_TOKEN="1114616-4041135154939083599611185486179-EYWOhssSyM3ZfarQ8a03UHWmB6hq4gsM6pcE7N80SChL5RNWRU"
export LACRM_USER_CODE="1101F8"
```

## 📈 Optimalisering

### Performance-tuning
```bash
# Kjør med redusert verbose logging i produksjon
python lacrm_sync.py --sync-lacrm --update-missing-orgnr 2>/dev/null

# Bruk cache for raskere kjøring
# (Data blir automatisk cached i 7 dager)
```

### Overvåking
```bash
# Sett opp systemd service for automatisk restart
sudo systemctl enable lacrm-sync.timer
sudo systemctl start lacrm-sync.timer
```

## ✅ Suksesskriterier

Etter vellykket installasjon skal du se:
```
✅ 5 bedrifter identifisert i LACRM
✅ Organisasjonsnummer funnet og lagt til
✅ Databerikelse fra Brønnøysund og Proff.no
✅ Custom fields oppdatert automatisk
✅ Salgsanbefalinger generert
✅ Pipeline-elementer opprettet
✅ Automatisk daglig synkronisering aktivert
```

## 🆘 Support

Ved problemer:
1. Sjekk `logs/sync.log` for feilmeldinger
2. Kjør med `--debug` for detaljert informasjon
3. Verifiser nettverkstilkobling til LACRM og Brønnøysund
4. Kontroller at alle custom fields eksisterer i LACRM

**Systemet er nå klart for produksjon! 🚀**
