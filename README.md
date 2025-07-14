# RefreshLACRM - Automatisk LACRM Lead-generering 🚀

Et intelligent system som automatisk henter forretningsdata fra Brønnøysund-registeret og oppretter kvalifiserte leads i LACRM med AI-genererte salgsanbefalinger.
Uses various sources to update LACRM data

## ✨ Funksjoner

- **🔍 Automatisk datahenting** fra Brønnøysund-registeret
- **🤖 AI-drevet salgsanalyse** med ChatGPT-integrasjon
- **📊 Intelligent lead-kvalifisering** basert på 15 forretningsregler
- **⚡ LACRM-integrasjon** med automatisk pipeline-opprettelse
- **📈 Company Card-oppdatering** med strukturerte forretningsdata
- **🎯 Salgsmål-matching** mot 15 definerte tjenestekategorier

## 🚀 Rask Start

### 1. Installer systemet
```bash
git clone https://github.com/ditt-brukernavn/RefreshLACRM.git
cd RefreshLACRM
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# eller: venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Konfigurer API-er
```bash
cp config.ini.example config.ini
nano config.ini
```

Fyll inn:
- **LACRM UserCode & APIToken** (fra LACRM Settings → API)
- **OpenAI API Key** (valgfritt, for AI-anbefalinger)

### 3. Finn Custom Field ID-er automatisk
```bash
python3 lacrm_sync.py --show-fields
```

Dette viser alle tilgjengelige Custom Fields i din LACRM med ID-numre.

### 4. Oppdater config.ini med Field ID-er

Se [LACRM_SETUP_GUIDE.md](LACRM_SETUP_GUIDE.md) for detaljert veiledning.

### 5. Test systemet
```bash
# Test med en bedrift (dry-run)
python3 lacrm_sync.py --oppdater 923609016 --dry-run

# Full sync (dry-run)
python3 lacrm_sync.py --sync-lacrm --dry-run
```

## 📖 Detaljert Dokumentasjon

- **[LACRM Setup Guide](LACRM_SETUP_GUIDE.md)** - Komplett konfigurasjonsveiledning
- **[Field Mapping](docs/field-mapping.md)** - Hvordan data mappes mellom systemer
- **[Sales Rules](docs/sales-rules.md)** - De 15 intelligente salgsreglene
- **[API Documentation](docs/api.md)** - Teknisk API-dokumentasjon

## 🎯 Hvordan det fungerer

1. **Henter bedriftsdata** fra Brønnøysund via organisasjonsnummer
2. **Analyserer forretningsmulighetene** med 15 intelligente regler
3. **Genererer AI-salgsnotater** basert på bedriftsprofilen
4. **Oppretter LACRM pipeline-item** i "Potensielle kunder"
5. **Oppdaterer Company Card** med strukturerte forretningsdata

## 🛠️ Kommandoer

```bash
# Finn Custom Field ID-er
python3 lacrm_sync.py --show-fields

# Oppdater en enkelt bedrift
python3 lacrm_sync.py --oppdater 923609016

# Sync alle bedrifter fra liste til LACRM
python3 lacrm_sync.py --sync-lacrm

# Debugging med detaljert logging
python3 lacrm_sync.py --sync-lacrm --debug

# Dry-run (test uten å faktisk oppdatere LACRM)
python3 lacrm_sync.py --sync-lacrm --dry-run
```

## 📊 Salgsintelligens

Systemet analyserer 15 forskjellige forretningsmuligheter:

1. **Startup-pakke** - Nye selskap < 2 år
2. **Webdesign** - Ingen/dårlig nettside
3. **Sikkerhetsoppgradering** - SSL-problemer
4. **Profesjonell e-post** - Gmail/Hotmail som bedrifts-e-post
5. **Automatisering** - Ingen ansatte registrert
6. **SEO + Reviews** - Konkurranseutsatte bransjer
7. **Omprofilering** - Dårlige regnskapstall
8. **Modernisering** - Gamle firma, dårlig digital tilstedeværelse
9. **Booking-system** - Tjenestebedrifter
10. **Hosting-problemer** - Tekniske issues
11. **Kundetilbakemelding** - Ingen reviews
12. **Synlighetspakke** - Svak digital synlighet
13. **CRM-integrasjon** - Kontaktkaos
14. **E-postmarkedsføring** - Ingen kundedialog
15. **Regnskapsintegrasjon** - Fiken-brukere

## 🏗️ Teknisk Arkitektur

- **Python 3.8+** med modulær arkitektur
- **LACRM REST API** for CRM-integrasjon
- **OpenAI GPT-4** for AI-salgsanalyse
- **Brønnøysund API** for bedriftsdata
- **JSON-basert konfigurasjonsystem**
- **Omfattende logging og feilhåndtering**

## 📈 Automatisering

Sett opp automatisk kjøring med cron:

```bash
# Kjør hver dag kl 09:00
0 9 * * * cd /path/to/RefreshLACRM && /path/to/venv/bin/python lacrm_sync.py --sync-lacrm
```

## 🔧 Feilsøking

### Field ID-problemer
```bash
# Se alle tilgjengelige felter
python3 lacrm_sync.py --show-fields

# Sjekk config.ini at Field ID-er er numeriske
```

### API-problemer
```bash
# Test LACRM-tilkobling
python3 lacrm_sync.py --debug --oppdater 923609016 --dry-run
```

### Ingen pipeline-items opprettet
- Sjekk at bedriftene matcher salgsreglene
- Verifiser at pipeline "Potensielle kunder" finnes
- Kjør med `--debug` for detaljert analyse

## 🤝 Bidrag

1. Fork prosjektet
2. Opprett feature branch (`git checkout -b feature/ny-funksjon`)
3. Commit endringer (`git commit -am 'Legg til ny funksjon'`)
4. Push til branch (`git push origin feature/ny-funksjon`)
5. Opprett Pull Request

## 📄 Lisens

Dette prosjektet er lisensiert under MIT License - se [LICENSE](LICENSE) filen for detaljer.

## 🆘 Support

- **Dokumentasjon**: Se [LACRM_SETUP_GUIDE.md](LACRM_SETUP_GUIDE.md)
- **Issues**: Bruk GitHub Issues for bugrapporter
- **Debugging**: Kjør alltid med `--debug` ved problemer
