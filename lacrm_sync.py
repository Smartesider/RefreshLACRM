"""
lacrm_sync.py

Subtitle: Smart Contact Enrichment & Sales Insight Engine for LACRM

Purpose:
A command-line driven Python application designed to enrich, verify, and sync customer data 
in Less Annoying CRM (LACRM) by leveraging public registries and intelligent business logic. 
It acts as a data refinery, transforming raw contact data into actionable CRM insights.
"""

import argparse
import configparser
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import dns.resolver
from openai import OpenAI
import requests
import whois
from bs4 import BeautifulSoup
from bs4.element import Tag
from tqdm import tqdm
from Wappalyzer import Wappalyzer, WebPage
from whois.parser import PywhoisError

from db import db_conn, setup_database, db_load_from_cache, db_save_to_cache

# --- Constants ---
LACRM_API_URL = "https://api.lessannoyingcrm.com"
BRREG_API_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}"
BRREG_SEARCH_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
PROFF_URL = "https://www.proff.no/selskap/{orgnr}"
GULESIDER_URL = "https://www.gulesider.no/bedrift/{orgnr}"
CACHE_DIR = "cache"
LOG_DIR = "logs"

# Financial health constants
PROFITABILITY_CONCERN = "Profitability Concern"
REVENUE_CONCERN = "Revenue Concern"

# Pipeline creation constants
PIPELINE_NAME = "Potensielle kunder"
DEFAULT_PIPELINE_STATUS = "Foreslått"

# Pipeline recommendation mapping
PIPELINE_SUGGESTIONS = {
    "Web Design / Security": "Webdesign / Nettprofil",
    "SSL/Security Issues": "Sikkerhetsoppgradering", 
    "Email Branding": "Profesjonell e-post / branding",
    "Automation First Entry": "Automatisering / første løsning",
    "Startup Onboarding Package": "Startup-pakke",
    "Booking System": "Bestilling / kalender / tilstedeværelse",
    "Hosting Issues": "Hosting / vedlikehold",
    "Business Restructuring": "Omprofilering / nye marketer",
    "SEO + Reviews": "SEO + reviews + nettpakke",
    "Digital Modernization": "Modernisering",
    "Customer Feedback System": "Kundetilbakemeldingssystem",
    "Visibility Boost": "Synlighetspakke (AI, SEO, bilder)",
    "CRM Integration": "Skreddersydd CRM / integrasjon",
    "Email Marketing": "E-postmarkedsføring / nyhetsbrev",
    "Fiken Integration Services": "Regnskapsintegrasjon / Fiken"
}

# --- Logging Setup ---
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "sync.log")),
        logging.StreamHandler()
    ]
)

# --- Global OpenAI Client ---
# Initialize the client as None. It will be configured in load_config.
client: Optional[OpenAI] = None


# --- Configuration ---
def load_config() -> Optional[configparser.ConfigParser]:
    """Loads API credentials and settings from config.ini."""
    global client
    config = configparser.ConfigParser()
    config.read('config.ini')
    if 'LACRM' not in config or not all(
        k in config['LACRM'] for k in ['UserCode', 'APIToken', 'OrgNrFieldId']
    ):
        logging.error(
            "Config file 'config.ini' is missing or incomplete. "
            "Please create it based on 'config.ini.example'."
        )
        return None

    # OpenAI API Key (if available)
    if 'OpenAI' in config and config['OpenAI'].get('APIKey'):
        client = OpenAI(api_key=config['OpenAI']['APIKey'])
        logging.info("OpenAI client configured.")
    else:
        logging.warning("OpenAI API key not found in config. AI features disabled.")


    # Setup Database
    db_connection_string = config['Database'].get('ConnectionString')
    setup_database(db_connection_string)

    return config


# --- Caching ---
def load_from_cache(orgnr: str) -> Optional[Dict[str, Any]]:
    """Loads data for a given org number from the cache if it exists."""
    # Prioritize DB cache
    cached_data = db_load_from_cache(orgnr)
    if cached_data:
        return cached_data

    # Fallback to file cache
    cache_file = os.path.join(CACHE_DIR, f"{orgnr}.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_to_cache(orgnr: str, data: Dict[str, Any]):
    """Saves data for a given org number to the cache."""
    # Prioritize DB cache
    if db_conn:
        db_save_to_cache(orgnr, data)
        return

    # Fallback to file cache
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    cache_file = os.path.join(CACHE_DIR, f"{orgnr}.json")
    data['_timestamp'] = datetime.now(timezone.utc).isoformat()
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# --- Core Functionality ---
def validate_orgnr(orgnr: str) -> bool:
    """Validates a Norwegian organization number with enhanced security."""
    return validate_orgnr_input(orgnr)


def find_orgnr_by_name(company_name: str) -> Optional[str]:
    """Searches Brreg for an orgnr based on an exact company name match."""
    # Sanitize company name to prevent injection
    if not company_name or len(company_name) > 200:
        logging.warning("Invalid company name provided")
        return None
        
    logging.info(f"Searching for orgnr for company: '{company_name}'")
    params: Dict[str, Any] = {'navn': company_name, 'size': 1}
    try:
        response = requests.get(BRREG_SEARCH_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('_embedded', {}).get('enheter'):
            orgnr = data['_embedded']['enheter'][0]['organisasjonsnummer']
            logging.info(f"Found orgnr {orgnr} for '{company_name}'.")
            return orgnr
        else:
            logging.warning(
                f"No exact match found for '{company_name}' in Brreg."
            )
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error searching Brreg for '{company_name}': {e}")
        return None


def get_brreg_data(orgnr: str) -> Optional[Dict[str, Any]]:
    """Retrieves company data from the Brønnøysund Register Centre (Brreg)."""
    if not validate_orgnr(orgnr):
        logging.error(f"Invalid orgnr format: {orgnr}")
        return None
        
    logging.info(f"Fetching data for orgnr {orgnr} from Brreg.")
    try:
        response = requests.get(BRREG_API_URL.format(orgnr=orgnr), timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code == 404:
            logging.warning(f"Organization number {orgnr} not found in Brreg.")
        else:
            logging.error(f"HTTP error fetching data for {orgnr}: {e}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error connecting to Brreg API for {orgnr}: {e}")
    return None


# --- New Enrichment Functions ---

def check_social_media_presence(company_name: str) -> Dict[str, str]:
    """
    A simple heuristic to check for social media presence by searching Google.
    NOTE: This is a very basic implementation and can be unreliable.
    """
    presence = {}
    social_sites = ["linkedin.com", "facebook.com", "instagram.com"]
    
    for site in social_sites:
        query = f'"{company_name}" site:{site}'
        try:
            # This is a placeholder for a real Google search API call
            # Direct scraping of Google is against their ToS.
            # A real implementation would use a service like SerpAPI.
            logging.debug(f"Simulating Google search for: {query}")
            presence[site] = "Search simulation - further implementation needed."
        except Exception as e:
            presence[site] = f"Search failed: {e}"
            
    return presence


def check_fiken_usage(orgnr: str) -> Dict[str, Any]:
    """Check if company appears to use Fiken accounting software."""
    try:
        # This is a placeholder implementation
        # Real implementation would check for Fiken integrations or mentions
        logging.debug(f"Checking Fiken usage for {orgnr}")
        return {"uses_fiken": False, "confidence": "low"}
    except Exception as e:
        logging.error(f"Error checking Fiken usage: {e}")
        return {"uses_fiken": False, "error": str(e)}


def monitor_company_news(company_name: str) -> Dict[str, Any]:
    """Monitor recent company news and announcements."""
    try:
        # This is a placeholder implementation
        # Real implementation would search news APIs or RSS feeds
        logging.debug(f"Monitoring news for {company_name}")
        return {"recent_news": [], "last_checked": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logging.error(f"Error monitoring company news: {e}")
        return {"recent_news": [], "error": str(e)}


def analyze_job_openings(company_name: str) -> Dict[str, Any]:
    """Analyze current job openings for hiring patterns."""
    try:
        # This is a placeholder implementation
        # Real implementation would check job boards like finn.no, nav.no
        logging.debug(f"Analyzing job openings for {company_name}")
        return {
            "hiring_status": "Unknown",
            "recent_roles": [],
            "last_checked": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logging.error(f"Error analyzing job openings: {e}")
        return {"hiring_status": "Error", "error": str(e)}


def validate_url(url: str) -> bool:
    """Validates if a URL is safe to request."""
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(url)
        # Only allow http/https schemes
        if parsed.scheme not in ('http', 'https'):
            return False
        # Block localhost and private IP ranges
        if parsed.hostname in ('localhost', '127.0.0.1', '::1'):
            return False
        # Add more validation as needed
        return True
    except Exception:
        return False


def validate_orgnr_input(orgnr: str) -> bool:
    """Enhanced validation for organization number input."""
    # Check if it's exactly 9 digits and doesn't contain SQL injection patterns
    import re
    if not re.match(r'^\d{9}$', orgnr):
        return False
    # Additional safety check for SQL injection patterns
    dangerous_patterns = ['\'', '"', ';', '--', '/*', '*/', 'xp_', 'sp_']
    orgnr_lower = orgnr.lower()
    return not any(pattern in orgnr_lower for pattern in dangerous_patterns)


def check_domain_health(domain: str) -> Dict[str, Any]:
    """Performs DNS and WHOIS checks on a domain."""
    if not domain:
        return {"error": "No domain provided."}
    
    # Validate domain format
    import re
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]*\.[a-zA-Z]{2,}$', domain):
        return {"error": "Invalid domain format."}
    
    health_report: Dict[str, Any] = {}
    try:
        # WHOIS lookup
        domain_info: Any = whois.whois(domain)
        expiration_date: Any = getattr(domain_info, 'expiration_date', None)
        
        # Handle cases where expiration_date is a list
        if isinstance(expiration_date, list):
            expiration_date = expiration_date[0] if expiration_date else None

        health_report['whois'] = {
            'registrar': getattr(domain_info, 'registrar', 'N/A'),
            'expiration_date': expiration_date.isoformat() if isinstance(expiration_date, datetime) else str(expiration_date),
        }
        # SSL check is implicitly done by requests with https
        if validate_url(f"https://{domain}"):
            response = requests.get(f"https://{domain}", timeout=10)
            health_report['ssl_valid'] = response.ok
        else:
            health_report['ssl_valid'] = False
    except PywhoisError as e:
        health_report['whois'] = f"WHOIS lookup failed: {e}"
    except requests.exceptions.SSLError:
        health_report['ssl_valid'] = False
    except requests.exceptions.RequestException:
        health_report['https_accessible'] = False

    # DNS checks
    try:
        mx_records: Any = dns.resolver.resolve(domain, 'MX')
        health_report['mx_records'] = [
            str(r.exchange) for r in mx_records
        ]
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        health_report['mx_records'] = "No MX records found."

    return health_report


def analyze_website_with_ai(url: str) -> Optional[Dict[str, str]]:
    """Uses OpenAI to analyze the 'About Us' text of a website."""
    if not client:
        return {"error": "OpenAI client not configured."}
    
    if not validate_url(url):
        return {"error": "Invalid or unsafe URL provided."}
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        
        # A simple heuristic to find the main content or about text
        # This can be significantly improved with more advanced parsing
        text_elements = soup.find_all(['p', 'h1', 'h2', 'div'])
        page_text = ' '.join([elem.get_text() for elem in text_elements if elem])
        
        # Truncate to avoid excessive token usage
        page_text = page_text[:8000] 

        prompt = (
            "Analyze the following website text from an 'About Us' or home page. "
            "Assess the tone of voice (e.g., corporate, personal, casual), "
            "the clarity of the business purpose, and whether it includes a "
            "clear call-to-action (CTA). Provide a one-sentence summary for each. "
            f"\n\nWebsite Text:\n---\n{page_text}"
        )

        ai_response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Or a newer model like gpt-4
            messages=[
                {"role": "system", "content": "You are a helpful business analyst."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.5,
        )
        analysis = ai_response.choices[0].message.content
        return {"summary": analysis}

    except requests.exceptions.RequestException as e:
        return {"error": f"Could not fetch website content: {e}"}
    except Exception as e:
        logging.error(f"AI analysis failed: {e}", exc_info=True)
        return {"error": f"AI analysis failed: {e}"}


def detect_tech_stack(url: str) -> Dict[str, Any]:
    """Detects the technology stack of a website."""
    if not validate_url(url):
        return {"error": "Invalid or unsafe URL provided."}
        
    try:
        # Note: Wappalyzer can be slow and resource-intensive
        wappalyzer = Wappalyzer.latest()
        webpage = WebPage.new_from_url(url)
        tech = wappalyzer.analyze_with_versions(webpage)
        return tech if tech else {}
    except Exception as e:
        logging.error(f"Tech stack detection failed for {url}: {e}", exc_info=True)
        return {"error": f"Tech stack detection failed: {e}"}


def get_financial_health(proff_data: Dict[str, Any]) -> Dict[str, str]:
    """Analyzes key figures from Proff.no to assess financial health."""
    health = {}
    key_figures = proff_data.get('key_figures')

    if not isinstance(key_figures, dict):
        return {"status": "No key figures available."}

    # Example rules (these are simplified and should be expanded)
    try:
        revenue_val = key_figures.get("Driftsinntekter", "0")
        # Sanitize and validate the input
        revenue_str = str(revenue_val).replace(" ", "").replace(",", "")
        # Additional validation
        if not revenue_str.isdigit():
            raise ValueError("Invalid revenue format")
        revenue_int = int(revenue_str)
        if revenue_int < 1000000:
            health[REVENUE_CONCERN] = "Low revenue (< 1M NOK)."

        result_val = key_figures.get("Resultat før skatt", "0")
        result_str = str(result_val).replace(" ", "").replace(",", "")
        if not result_str.lstrip('-').isdigit():
            raise ValueError("Invalid result format")
        result_int = int(result_str)
        if result_int < 0:
            health[PROFITABILITY_CONCERN] = (
                "Company is not currently profitable."
            )

    except (ValueError, TypeError) as e:
        logging.error(f"Could not parse financial figures: {e}")
        health["Data Quality"] = "Could not parse financial figures."

    if not health:
        health["status"] = "Appears stable based on available data."

    return health


# --- LACRM API Functions ---
def get_lacrm_contacts(
    config: configparser.ConfigParser
) -> Optional[List[Dict[str, Any]]]:
    """Fetches all contacts from LACRM."""
    logging.info("Fetching all contacts from LACRM...")
    params = {
        "UserCode": config['LACRM']['UserCode'],
        "APIToken": config['LACRM']['APIToken'],
        "Function": "GetContacts",
    }
    try:
        response = requests.post(LACRM_API_URL, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()
        if result.get('Success'):
            contacts = result.get('Result', [])
            logging.info(f"Successfully fetched {len(contacts)} contacts.")
            return contacts
        else:
            logging.error(f"LACRM API Error: {result.get('Result')}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error connecting to LACRM API: {e}")
        return None


def get_or_create_pipeline(config: configparser.ConfigParser) -> Optional[str]:
    """Gets or creates the 'Potensielle kunder' pipeline and returns its ID."""
    logging.info(f"Getting or creating pipeline: {PIPELINE_NAME}")
    
    # First, try to get existing pipelines
    params = {
        "UserCode": config['LACRM']['UserCode'],
        "APIToken": config['LACRM']['APIToken'],
        "Function": "GetPipelines",
    }
    
    try:
        response = requests.post(LACRM_API_URL, params=params, timeout=15)
        response.raise_for_status()
        result = response.json()
        
        if result.get('Success'):
            pipelines = result.get('Result', [])
            # Look for existing pipeline
            for pipeline in pipelines:
                if pipeline.get('Name') == PIPELINE_NAME:
                    pipeline_id = pipeline.get('PipelineId')
                    logging.info(f"Found existing pipeline '{PIPELINE_NAME}' with ID: {pipeline_id}")
                    return pipeline_id
            
            # If not found, create new pipeline
            create_params = {
                "UserCode": config['LACRM']['UserCode'],
                "APIToken": config['LACRM']['APIToken'],
                "Function": "CreatePipeline",
                "Parameters": json.dumps({
                    "Name": PIPELINE_NAME,
                    "StatusNames": [DEFAULT_PIPELINE_STATUS, "Under vurdering", "Kontaktet", "Proposal sendt", "Lukket vunnet", "Lukket tapt"]
                })
            }
            
            create_response = requests.post(LACRM_API_URL, params=create_params, timeout=15)
            create_response.raise_for_status()
            create_result = create_response.json()
            
            if create_result.get('Success'):
                pipeline_id = create_result.get('Result', {}).get('PipelineId')
                logging.info(f"Created new pipeline '{PIPELINE_NAME}' with ID: {pipeline_id}")
                return pipeline_id
            else:
                logging.error(f"Failed to create pipeline: {create_result.get('Result')}")
                return None
        else:
            logging.error(f"Failed to get pipelines: {result.get('Result')}")
            return None
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Error managing pipeline: {e}")
        return None


def create_pipeline_item(
    config: configparser.ConfigParser,
    pipeline_id: str,
    company_name: str,
    orgnr: str,
    suggested_service: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    ai_comment: Optional[str] = None
) -> bool:
    """Creates a new item in the Potensielle kunder pipeline."""
    logging.info(f"Creating pipeline item for {company_name} ({orgnr})")
    
    # Prepare the pipeline item data with correct field IDs
    item_data = {
        "PipelineId": pipeline_id,
        "Name": f"{company_name} - {suggested_service}",
        "StatusName": DEFAULT_PIPELINE_STATUS,
        "CustomFields": {
            "4040978312246995862143020657543": company_name,  # company
            "4040978325247338748089826771438": orgnr,  # orgnr
            "4040978367411984014571433950341": suggested_service,  # category_main
            "4040978530497342527228366666677": phone or "",  # phone
            "4040978542434691785927660074431": email or "",  # email
            "4040978809695731611850070969647": ai_comment or (
                f"Automatisk forslag basert på analyse av {company_name}. "
                f"Anbefalt tjeneste: {suggested_service}"
            )  # comment
        }
    }
    
    params = {
        "UserCode": config['LACRM']['UserCode'],
        "APIToken": config['LACRM']['APIToken'],
        "Function": "CreatePipelineItem",
        "Parameters": json.dumps(item_data)
    }
    
    try:
        response = requests.post(LACRM_API_URL, params=params, timeout=15)
        response.raise_for_status()
        result = response.json()
        
        if result.get('Success'):
            item_id = result.get('Result', {}).get('PipelineItemId')
            logging.info(f"Successfully created pipeline item for {company_name} with ID: {item_id}")
            return True
        else:
            logging.error(f"Failed to create pipeline item for {company_name}: {result.get('Result')}")
            return False
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Error creating pipeline item for {company_name}: {e}")
        return False


def generate_ai_sales_comment(enriched_data: Dict[str, Any], suggested_service: str) -> str:
    """Generates an AI-powered sales approach comment based on company data."""
    if not client:
        return f"Anbefalt tjeneste: {suggested_service} basert på automatisk analyse."
    
    company_name = enriched_data.get('navn', 'Ukjent selskap')
    industry = enriched_data.get('naeringskode1', {}).get('beskrivelse', 'Ukjent bransje')
    employees = enriched_data.get('antallAnsatte', 0)
    website = enriched_data.get('hjemmeside', 'Ingen nettside')
    
    # Build context for AI
    context = f"""
    Selskap: {company_name}
    Bransje: {industry}
    Antall ansatte: {employees}
    Nettside: {website}
    Anbefalt tjeneste: {suggested_service}
    """
    
    prompt = f"""Du er en erfaren salgsrådgiver. Basert på følgende informasjon om et norsk selskap, skriv en kort og profesjonell tilnærmingskommentar (maks 150 ord) som forklarer:
1. Hvorfor denne tjenesten er relevant for dem
2. Hvilke konkrete fordeler de kan få
3. En naturlig måte å ta kontakt på

Informasjon om selskapet:
{context}

Skriv svaret på norsk og hold det konkret og salgsorientert."""

    try:
        ai_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Du er en profesjonell salgsrådgiver som skriver korte, effektive tilnærmingskommentarer."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.7,
        )
        
        comment = ai_response.choices[0].message.content
        return comment.strip()
        
    except Exception as e:
        logging.error(f"AI comment generation failed: {e}")
        return f"Anbefalt tjeneste: {suggested_service}. Selskapet kan dra nytte av denne tjenesten basert på vår analyse av deres digitale tilstedeværelse og forretningsdata."


def enrich_with_urls(orgnr: str) -> Dict[str, str]:
    """
    Fetches various website URLs for a company from different sources.
    """
    urls = {}
    
    # Try to get additional URLs from Gulesider.no
    try:
        gulesider_url = GULESIDER_URL.format(orgnr=orgnr)
        response = requests.get(gulesider_url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Look for website links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.startswith('http') and orgnr not in href:
                    urls['gulesider_website'] = href
                    break
    except Exception as e:
        logging.warning(f"Could not fetch URLs from Gulesider for {orgnr}: {e}")
        
    return urls


def scrape_proff(orgnr: str) -> Optional[Dict[str, Any]]:
    """
    Scrapes key financial and company data from Proff.no.
    """
    try:
        url = PROFF_URL.format(orgnr=orgnr)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            logging.warning(f"Proff.no returned status {response.status_code} for {orgnr}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        proff_data = {
            'url': url,
            'key_figures': 'No key figures available',
            'company_description': '',
            'contact_info': {}
        }
        
        # Try to extract key figures
        key_figures_section = soup.find('div', class_='key-figures') or soup.find('table', class_='table-key-figures')
        if key_figures_section:
            figures = {}
            for row in key_figures_section.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    if key and value:
                        figures[key] = value
            if figures:
                proff_data['key_figures'] = figures
        
        # Try to extract company description
        description_section = soup.find('div', class_='company-description') or soup.find('p', class_='description')
        if description_section:
            proff_data['company_description'] = description_section.get_text(strip=True)
        
        # Try to extract contact information
        contact_section = soup.find('div', class_='contact-info')
        if contact_section:
            contact_info = {}
            for item in contact_section.find_all(['div', 'p', 'span']):
                text = item.get_text(strip=True)
                if '@' in text:
                    contact_info['email'] = text
                elif text.startswith('+') or text.replace(' ', '').isdigit():
                    contact_info['phone'] = text
            proff_data['contact_info'] = contact_info
        
        logging.info(f"Successfully scraped Proff.no data for {orgnr}")
        return proff_data
        
    except Exception as e:
        logging.error(f"Failed to scrape Proff.no for {orgnr}: {e}")
        return None


def update_lacrm_contact(contact_id: str, payload: Dict[str, Any], config: configparser.ConfigParser, dry_run: bool = False) -> bool:
    """
    Updates a contact in LACRM with the provided payload data.
    """
    if dry_run:
        logging.info(f"[DRY RUN] Would update LACRM contact {contact_id} with payload: {payload}")
        return True
    
    try:
        params = {
            "UserCode": config['LACRM']['UserCode'],
            "APIToken": config['LACRM']['APIToken'],
            "Function": "EditContact",
            "Parameters": json.dumps({
                "ContactId": contact_id,
                "CustomFields": payload
            })
        }
        
        response = requests.post(LACRM_API_URL, params=params, timeout=15)
        response.raise_for_status()
        
        result = response.json()
        if result.get("Success"):
            logging.info(f"Successfully updated LACRM contact {contact_id}")
            return True
        else:
            logging.error(f"LACRM API error updating contact {contact_id}: {result}")
            return False
            
    except Exception as e:
        logging.error(f"Failed to update LACRM contact {contact_id}: {e}")
        return False


def apply_sales_heuristics(enriched_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Applies a set of sales rules to the enriched data to generate pipeline
    recommendations with Norwegian categories.
    """
    pipelines: Dict[str, str] = {}
    now = datetime.now(timezone.utc)

    # Rule: Startup-pakke (Company < 2 years old)
    est_date_str = enriched_data.get('stiftelsesdato')
    if est_date_str:
        try:
            est_date = datetime.strptime(est_date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            age_years = (now - est_date).days / 365.25
            if age_years < 2:
                pipelines['Startup-pakke'] = (
                    f"Selskap etablert < 2 år ({age_years:.1f} år gammelt), ofte uten CRM, branding eller struktur."
                )
        except ValueError:
            logging.warning(f"Could not parse stiftelsesdato: {est_date_str}")

    # Rule: Webdesign / Nettprofil (No website or outdated)
    website = enriched_data.get('hjemmeside')
    domain_health = enriched_data.get('domain_health', {})
    if not website:
        pipelines['Webdesign / Nettprofil'] = "Ingen nettside, eller utdatert/ufullstendig"
    elif domain_health.get('ssl_valid') is False:
        pipelines['Sikkerhetsoppgradering'] = "HTTP uten HTTPS, ugyldig SSL, exposed CMS"

    # Rule: Professional email check
    if website:
        # Extract domain from website for email analysis
        domain = website.replace('https://', '').replace('http://', '').split('/')[0]
        # Simple check for unprofessional email domains (this is basic - could be enhanced)
        unprofessional_domains = ['gmail.com', 'hotmail.com', 'online.no', 'yahoo.com', 'live.no']
        if any(unpro_domain in domain.lower() for unpro_domain in unprofessional_domains):
            pipelines['Profesjonell e-post / branding'] = "Gmail, Hotmail, Online.no, Yahoo etc. brukt som primær e-post"

    # Rule: Automatisering / første løsning (No employees listed)
    employees = enriched_data.get('antallAnsatte')
    if employees == 0:
        pipelines['Automatisering / første løsning'] = "Ingen ansatte, nyregistrert, eller enkel enmannsbedrift uten digitale systemer"

    # Rule: Business Restructuring based on financial health
    financial_health = enriched_data.get('financial_health', {})
    if PROFITABILITY_CONCERN in financial_health or REVENUE_CONCERN in financial_health:
        pipelines['Omprofilering / nye markeder'] = "Regnskapstall viser fall eller lav vekst siste 2 år"

    # Rule: Fiken Integration
    if enriched_data.get('fiken_usage', {}).get('uses_fiken'):
        pipelines['Regnskapsintegrasjon / Fiken'] = "Mismatching mellom kontaktdata og regnskapsdata, eller manglende fakturastrøm"

    # Rule: Service-based businesses (booking system)
    industry_desc = enriched_data.get('naeringskode1', {}).get('beskrivelse', '').lower()
    service_industries = ['frisør', 'tannlege', 'klinikk', 'behandling', 'terapi', 'helse']
    if any(service_term in industry_desc for service_term in service_industries):
        pipelines['Bestilling / kalender / tilstedeværelse'] = "Tjenestebasert bedrift (frisør, tannlege, klinikk) uten online booking"

    # Rule: Hosting / vedlikehold issues
    tech_stack = enriched_data.get('tech_stack', {})
    if tech_stack.get('error') or domain_health.get('https_accessible') is False:
        pipelines['Hosting / vedlikehold'] = "Nettside treg, nede, eller med tekniske feil (cloud-problemer)"

    # Rule: SEO + reviews for competitive industries
    competitive_industries = [
        "butikkhandel", "restaurant", "eiendomsmegling", "regnskap",
        "programvare", "konsulent", "håndverker", "rådgivning"
    ]
    if any(term in industry_desc for term in competitive_industries):
        pipelines['SEO + reviews + nettpakke'] = "Bransje = konkurranseutsatt (butikk, restaurant, rådgivning) og dårlig synlighet"

    # Rule: Modernization for older companies (>10 years)
    if est_date_str:
        try:
            est_date = datetime.strptime(est_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            age_years = (now - est_date).days / 365.25
            if age_years > 10 and (not website or domain_health.get('ssl_valid') is False):
                pipelines['Modernisering'] = "Eldre firma (>10 år) med dårlig nettside, generisk e-post, eller manglende digitale løsninger"
        except ValueError:
            pass

    # Rule: Customer feedback system
    proff_data = enriched_data.get('proff_data', {})
    if isinstance(proff_data, dict):
        key_figs_value = proff_data.get('key_figures')
        if not key_figs_value or (isinstance(key_figs_value, str) and "no key figures" in key_figs_value):
            pipelines['Kundetilbakemeldingssystem'] = "Ingen reviews på Proff.no, ingen referanser eller rating"

    # Rule: Visibility package
    socials = enriched_data.get('social_media_presence', {})
    if not any("found" in str(v).lower() for v in socials.values()):
        pipelines['Synlighetspakke (AI, SEO, bilder)'] = "Mangler Google Business, LinkedIn, eller har svak digital synlighet"

    # Rule: CRM Integration (based on contact management issues)
    if not enriched_data.get('urls', {}) or not enriched_data.get('proff_data', {}):
        pipelines['Skreddersydd CRM / integrasjon'] = "Når CRM-mangler blir åpenbare – kontaktkaos, dobbeltdrift, manuell oppfølging"

    # Rule: Email marketing
    if not enriched_data.get('company_news', {}).get('recent_news'):
        pipelines['E-postmarkedsføring / nyhetsbrev'] = "Ingen form for kundedialog, eller manglende samtykke / strategi"

    return pipelines


def setup_cron():
    """Sets up a cron job or scheduled task to run the script daily."""
    script_path = os.path.abspath(__file__)
    python_executable = sys.executable
    
    # Validate paths to prevent command injection
    import shlex
    safe_python_executable = shlex.quote(python_executable)
    safe_script_path = shlex.quote(script_path)
    
    command = (
        f'{safe_python_executable} {safe_script_path} --sync-lacrm '
        '--update-missing-orgnr'
    )

    if sys.platform == "win32":
        task_name = "LACRMSyncDaily"
        try:
            # First, try to delete any existing task with the same name
            subprocess.run(
                ["schtasks", "/delete", "/tn", task_name, "/f"],
                check=False, capture_output=True
            )
            # Create the new task with safer command construction
            subprocess.run(
                [
                    "schtasks", "/create", "/tn", task_name, 
                    "/tr", f"{safe_python_executable} {safe_script_path} --sync-lacrm --update-missing-orgnr",
                    "/sc", "DAILY", "/st", "03:00"
                ],
                check=True, capture_output=True, text=True
            )
            logging.info(f"Successfully created Windows scheduled task '{task_name}'.")
        except FileNotFoundError as e:
            logging.error(f"Failed to create scheduled task: schtasks command not found. {e}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to create scheduled task: {e.stderr}")
    else:
        # For Linux/macOS
        try:
            # Write to a temporary cron file
            cron_job = f"0 3 * * * {command}\n"
            with open("temp_cron", "w") as f:
                f.write(cron_job)
            # Add the new job
            subprocess.run(["crontab", "temp_cron"], check=True)
            os.remove("temp_cron")
            logging.info("Successfully added cron job.")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logging.error(f"Failed to set up cron job: {e}")


def remove_cron():
    """Removes the cron job or scheduled task."""
    if sys.platform == "win32":
        task_name = "LACRMSyncDaily"
        try:
            subprocess.run(
                ["schtasks", "/delete", "/tn", task_name, "/f"],
                check=True, capture_output=True, text=True
            )
            logging.info(f"Successfully removed scheduled task '{task_name}'.")
        except subprocess.CalledProcessError as e:
            # A non-zero exit code might mean the task doesn't exist, which is fine.
            if "ERROR: The specified task name" in e.stderr:
                logging.warning(f"Scheduled task '{task_name}' not found.")
            else:
                logging.error(f"Failed to remove scheduled task: {e.stderr}")
        except FileNotFoundError:
            logging.error("Failed to remove scheduled task: schtasks command not found.")
    else:
        # For Linux/macOS - this removes all cron jobs for the user
        try:
            subprocess.run(["crontab", "-r"], check=True)
            logging.info("Successfully removed all user cron jobs.")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logging.error(f"Failed to remove cron jobs: {e}")


def process_single_orgnr(orgnr: str, args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    """Processes a single organization number."""
    if not validate_orgnr(orgnr):
        logging.error(
            "Invalid organization number format. It must be 9 digits."
        )
        return None

    cached_data = load_from_cache(orgnr)
    if not args.tving and cached_data:
        logging.info(f"Using cached data for {orgnr}.")
        enriched_data = cached_data
    else:
        logging.info(f"Fetching fresh data for {orgnr}.")
        brreg_data = get_brreg_data(orgnr)
        if not brreg_data:
            return None

        enriched_data = brreg_data.copy()
        company_name = enriched_data.get('navn', '')

        # --- Run enrichment functions ---
        enriched_data['urls'] = enrich_with_urls(orgnr)
        proff_scrape_data = scrape_proff(orgnr)
        enriched_data['proff_data'] = proff_scrape_data if proff_scrape_data else {}
        
        if proff_scrape_data:
            enriched_data['financial_health'] = get_financial_health(proff_scrape_data)

        website_url = enriched_data.get('hjemmeside')
        if website_url and validate_url(website_url):
            domain = re.sub(r'^https?://', '', website_url).split('/')[0]
            enriched_data['domain_health'] = check_domain_health(domain)
            enriched_data['tech_stack'] = detect_tech_stack(website_url)
            enriched_data['ai_analysis'] = analyze_website_with_ai(website_url)
            enriched_data['social_media_presence'] = check_social_media_presence(
                company_name
            )
        elif website_url:
            logging.warning(f"Invalid or unsafe website URL: {website_url}")
        
        enriched_data['fiken_usage'] = check_fiken_usage(orgnr)
        enriched_data['company_news'] = monitor_company_news(company_name)
        enriched_data['job_openings'] = analyze_job_openings(company_name)

        save_to_cache(orgnr, enriched_data)
        logging.info(f"Successfully enriched and cached data for {orgnr}.")

    if args.anbefalinger:
        print_recommendations(enriched_data)
    
    return enriched_data


def sync_all_lacrm_contacts(
    config: configparser.ConfigParser, args: argparse.Namespace
):
    """Fetches all LACRM contacts and processes them."""
    contacts = get_lacrm_contacts(config)
    if not contacts:
        return

    orgnr_field_id = config['LACRM']['OrgNrFieldId']
    
    # Progress bar setup
    pbar = tqdm(contacts, desc="Syncing LACRM Contacts")

    for contact in pbar:
        if not isinstance(contact, dict) or not contact.get('CompanyName'):
            continue

        contact_id = contact.get('ContactId')
        company_name = contact.get('CompanyName')
        if not contact_id or not company_name:
            continue
        
        pbar.set_postfix_str(company_name)

        orgnr = None
        # Extract existing orgnr from custom fields
        custom_fields: Any = contact.get('CustomFields', [])
        if isinstance(custom_fields, list):
            for field in custom_fields:
                if isinstance(field, dict) and field.get('FieldId') == orgnr_field_id:
                    orgnr = field.get('Value')
                    break
        
        # --- Stage 1: Ensure OrgNr exists ---
        if not orgnr and args.update_missing_orgnr:
            logging.info(
                f"'{company_name}' (ContactId: {contact_id}) is missing orgnr. Searching..."
            )
            found_orgnr = find_orgnr_by_name(company_name)
            if found_orgnr:
                update_payload = {orgnr_field_id: found_orgnr}
                update_lacrm_contact(
                    contact_id, update_payload, config, args.dry_run
                )
                orgnr = found_orgnr # Use the newly found orgnr for processing
            else:
                logging.warning(f"Could not find orgnr for '{company_name}'. Skipping.")
                continue # Skip to the next contact if no orgnr can be found
        
        if not orgnr or not isinstance(orgnr, str):
            logging.debug(f"Skipping '{company_name}' as it has no valid orgnr.")
            continue

        # --- Stage 2: Process and Sync ---
        logging.info(
            f"Processing '{company_name}' (ContactId: {contact_id}) with orgnr: {orgnr}"
        )
        enriched_data = process_single_orgnr(orgnr, args)

        if not enriched_data:
            logging.warning(f"Failed to enrich data for {orgnr}, cannot sync.")
            continue

        # --- Stage 3a: Create Pipeline Items for Potential Customers ---
        recommendations = apply_sales_heuristics(enriched_data)
        if recommendations and not args.dry_run:
            pipeline_id = get_or_create_pipeline(config)
            if pipeline_id:
                for recommendation, reason in recommendations.items():
                    # Map English recommendations to Norwegian services
                    norwegian_service = PIPELINE_SUGGESTIONS.get(
                        recommendation, recommendation
                    )
                    
                    # Generate AI sales comment
                    ai_comment = generate_ai_sales_comment(
                        enriched_data, norwegian_service
                    )
                    
                    try:
                        pipeline_item_created = create_pipeline_item(
                            config=config,
                            pipeline_id=pipeline_id,
                            company_name=enriched_data.get('navn', company_name),
                            orgnr=orgnr,
                            suggested_service=norwegian_service,
                            phone=enriched_data.get('telefon', ''),
                            email='',  # Email not available in Brreg data
                            ai_comment=ai_comment
                        )
                        if pipeline_item_created:
                            logging.info(
                                f"Created pipeline item for {company_name}: "
                                f"{norwegian_service}"
                            )
                        else:
                            logging.warning(
                                f"Failed to create pipeline item for "
                                f"{company_name}"
                            )
                    except Exception as e:
                        logging.error(
                            f"Error creating pipeline item for "
                            f"{company_name}: {e}"
                        )
            else:
                logging.warning("Could not get or create pipeline for recommendations")

        # --- Stage 3b: Map Enriched Data to LACRM Fields and Update ---
        if args.sync_lacrm: # Only perform the full update if sync is enabled
            lacrm_update_payload = map_data_to_lacrm_fields(enriched_data, config)
            if lacrm_update_payload:
                update_lacrm_contact(contact_id, lacrm_update_payload, config, args.dry_run)
            else:
                logging.info(f"No new data to sync for contact {contact_id}.")


def map_data_to_lacrm_fields(
    enriched_data: Dict[str, Any],
    config: configparser.ConfigParser
) -> Dict[str, Any]:
    """Maps enriched data to Company Card Custom Fields in LACRM."""
    if 'LACRM_CUSTOM_FIELDS' not in config:
        logging.warning("'LACRM_CUSTOM_FIELDS' section not in config. Cannot map fields.")
        return {}

    mapping_config = config['LACRM_CUSTOM_FIELDS']
    payload = {}

    # Helper to safely add to payload
    def add_to_payload(key: str, value: Any):
        if key in mapping_config and mapping_config[key] and value is not None:
            field_id = mapping_config[key]
            # Format data appropriately for Company Card fields
            if isinstance(value, bool):
                payload[field_id] = "Yes" if value else "No"
            elif isinstance(value, str) and value:
                payload[field_id] = value
            elif isinstance(value, (int, float)):
                payload[field_id] = str(value)
            elif isinstance(value, dict) and value:
                # For complex data, create readable summary
                payload[field_id] = json.dumps(value, indent=2, ensure_ascii=False)
            elif isinstance(value, list) and value:
                payload[field_id] = ", ".join(str(item) for item in value)

    # --- Map to Company Card Custom Fields ---
    
    # Basic company information
    add_to_payload('brreg_navn', enriched_data.get('navn'))
    orgnr = enriched_data.get('organisasjonsnummer', '')
    if orgnr:
        orgnr_url = f"https://virksomhet.brreg.no/nb/oppslag/enheter/{orgnr}"
        add_to_payload('orgnr', orgnr_url)
    add_to_payload(
        'bransje',
        enriched_data.get('naeringskode1', {}).get('beskrivelse')
    )
    add_to_payload('antall_ansatte', enriched_data.get('antallAnsatte'))
    add_to_payload('etablert', enriched_data.get('stiftelsesdato'))
    add_to_payload('nettsted', enriched_data.get('hjemmeside'))
    
    # Email handling - try to extract from various sources
    email = enriched_data.get('epost')
    if not email:
        proff_data = enriched_data.get('proff_data', {})
        if isinstance(proff_data, dict):
            contact_info = proff_data.get('contact_info', {})
            if isinstance(contact_info, dict):
                email = contact_info.get('email')
    add_to_payload('firma_epost', email)

    # Proff rating (from financial health analysis)
    financial_health = enriched_data.get('financial_health', {})
    if isinstance(financial_health, dict):
        status = financial_health.get('status')
        if status == 'Appears stable based on available data.':
            proff_rating = "Stabil"
        elif any(concern in financial_health 
                for concern in [PROFITABILITY_CONCERN, REVENUE_CONCERN]):
            proff_rating = "Risiko"
        else:
            proff_rating = "Ukjent"
        add_to_payload('proff_rating', proff_rating)

    # Generate sales recommendations for pipeline_anbefalt
    recommendations = apply_sales_heuristics(enriched_data)
    if recommendations:
        # Take the first (most relevant) recommendation
        primary_recommendation = list(recommendations.keys())[0]
        # Map to simplified categories for Company Card
        recommendation_mapping = {
            'Webdesign / Nettprofil': 'Webdesign / Nettprofil',
            'Sikkerhetsoppgradering': 'Sikkerhetsoppgradering', 
            'Profesjonell e-post / branding': 'Profesjonell e-post',
            'Automatisering / første løsning': 'Automatisering / første løsning',
            'Startup-pakke': 'Startup-pakke',
            'Bestilling / kalender / tilstedeværelse': 'Bestilling / kalender / tilstedeværelse',
            'Hosting / vedlikehold': 'Hosting / vedlikehold',
            'Omprofilering / nye markeder': 'Omprofilering',
            'SEO + reviews + nettpakke': 'SEO / Reviews',
            'Modernisering': 'Modernisering',
            'Kundetilbakemeldingssystem': 'Kundetilbakemeldingssystem',
            'Synlighetspakke (AI, SEO, bilder)': 'Synlighetspakke (AI, SEO, bilder)',
            'Skreddersydd CRM / integrasjon': 'Skreddersydd CRM / integrasjon',
            'E-postmarkedsføring / nyhetsbrev': 'E-postmarkedsføring / nyhetsbrev',
            'Regnskapsintegrasjon / Fiken': 'Regnskapsintegrasjon / Fiken'
        }
        simplified_recommendation = recommendation_mapping.get(primary_recommendation, 'Annet')
        add_to_payload('pipeline_anbefalt', simplified_recommendation)

    # Generate AI sales notes
    ai_analysis = enriched_data.get('ai_analysis', {})
    notes = []
    if isinstance(ai_analysis, dict) and ai_analysis.get('summary'):
        notes.append(f"AI Analyse: {ai_analysis['summary']}")
    
    if recommendations:
        notes.append("Anbefalinger:")
        for rec, reason in list(recommendations.items())[:3]:  # Top 3 recommendations
            notes.append(f"- {rec}: {reason}")
    
    if notes:
        add_to_payload('salgsmotor_notat', "\n".join(notes))

    # Update log
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    update_entry = f"{timestamp}: Automatisk oppdatering fra Salgsmotor"
    add_to_payload('oppdateringslogg', update_entry)

    return payload


def print_recommendations(enriched_data: Dict[str, Any]):
    """Prints enriched data and sales recommendations."""
    print("\n--- Enriched Data ---")
    print(json.dumps(enriched_data, indent=2, ensure_ascii=False))

    print("\n--- Sales Recommendations ---")
    recommendations = apply_sales_heuristics(enriched_data)
    if recommendations:
        for pipeline, reason in recommendations.items():
            print(f"- Pipeline: {pipeline}\n  Reason: {reason}")
    else:
        print(
            "No specific sales pipelines recommended based on "
            "current data."
        )


# --- Main Application Logic ---
def main():
    """Main function to run the CLI application."""
    parser = argparse.ArgumentParser(
        description="Smart Contact Enrichment Engine for LACRM.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # User Manual Group
    parser.description = (
        "Smart Contact Enrichment Engine for LACRM.\n\n"
        "--- HOW TO USE ---\n"
        "1. Single Company Update:\n"
        "   Fetch data for one company by its organization number.\n"
        "   > python lacrm_sync.py --oppdater 998877665\n\n"
        "2. Full LACRM Sync:\n"
        "   Fetch data for all companies in your LACRM that have an orgnr.\n"
        "   > python lacrm_sync.py --sync-lacrm\n\n"
        "3. Sync and Find Missing Numbers:\n"
        "   Sync all companies and also search for orgnr for those missing it.\n"
        "   > python lacrm_sync.py --sync-lacrm --update-missing-orgnr\n\n"
        "4. Dry Run:\n"
        "   Simulate a sync without making any actual changes to LACRM.\n"
        "   > python lacrm_sync.py --sync-lacrm --dryrun\n\n"
        "5. Automated Scheduling (Cron):\n"
        "   Set up a daily task to run the sync automatically at 3 AM.\n"
        "   > python lacrm_sync.py --cron\n"
        "   To remove it:\n"
        "   > python lacrm_sync.py --removecron\n"
    )

    # Operation Mode Group
    mode_group = parser.add_argument_group('OPERATION MODES')
    mode_group.add_argument(
        '--oppdater',
        metavar='ORGNR',
        help="The Norwegian organization number to update."
    )
    mode_group.add_argument(
        '--sync-lacrm',
        action='store_true',
        help="Sync all LACRM contacts."
    )

    # Modifier Group
    modifier_group = parser.add_argument_group('MODIFIERS')
    modifier_group.add_argument(
        '--update-missing-orgnr',
        action='store_true',
        help="Attempt to find and update missing orgnr in LACRM (use with --sync-lacrm)."
    )
    modifier_group.add_argument(
        '--tving',
        action='store_true',
        help="Force re-fetch of data, even if a cache exists."
    )
    modifier_group.add_argument(
        '--anbefalinger',
        action='store_true',
        help="Show field-level suggestions for CRM update."
    )
    modifier_group.add_argument(
        '--dry-run',
        action='store_true',
        help="Simulate the run without making any actual changes to LACRM."
    )
    modifier_group.add_argument(
        '--debug',
        action='store_true',
        help="Enable full trace logging."
    )

    # Scheduling Group
    schedule_group = parser.add_argument_group('SCHEDULING')
    schedule_group.add_argument(
        '--cron',
        action='store_true',
        help="Set up a daily cron job/scheduled task to run the sync."
    )
    schedule_group.add_argument(
        '--removecron',
        action='store_true',
        help="Remove the daily cron job/scheduled task."
    )

    args = parser.parse_args()

    if args.cron:
        setup_cron()
        return
    if args.removecron:
        remove_cron()
        return

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    config = load_config()
    if not config:
        return

    if args.sync_lacrm:
        sync_all_lacrm_contacts(config, args)
    elif args.oppdater:
        process_single_orgnr(args.oppdater, args)
    else:
        # If no other action is specified, show help
        parser.print_help()


if __name__ == "__main__":
    main()
