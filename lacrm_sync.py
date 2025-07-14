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
from wappalyzer_py import Wappalyzer, WebPage
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
        webpage = WebPage(url)
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


def update_lacrm_contact(
    contact_id: str, 
    fields_to_update: Dict[str, Any], 
    config: configparser.ConfigParser, 
    dry_run: bool = False
) -> bool:
    """Updates a contact in LACRM with a dictionary of custom fields."""
    if not fields_to_update:
        logging.info(f"No fields to update for contact {contact_id}.")
        return True

    logging.info(f"Updating contact {contact_id} with {len(fields_to_update)} fields.")
    if dry_run:
        # Don't log sensitive data in dry-run mode
        logging.warning(
            f"[DRY RUN] Would have updated contact {contact_id} with {len(fields_to_update)} fields."
        )
        return True

    params = {
        "UserCode": config['LACRM']['UserCode'],
        "APIToken": config['LACRM']['APIToken'],
        "Function": "EditContact",
        "Parameters": json.dumps({
            "ContactId": contact_id,
            "CustomFields": fields_to_update
        })
    }
    try:
        response = requests.post(LACRM_API_URL, params=params, timeout=15)
        response.raise_for_status()
        result = response.json()
        if result.get('Success'):
            logging.info(f"Successfully updated contact {contact_id}.")
            return True
        else:
            logging.error(
                f"Failed to update contact {contact_id}: "
                f"{result.get('Result')}"
            )
            return False
    except requests.exceptions.RequestException as e:
        logging.error(f"Error updating contact {contact_id}: {e}")
        return False


def enrich_with_urls(
    orgnr: str, phone_number: Optional[str] = None
) -> Dict[str, str]:
    """Generates relevant business URLs."""
    urls = {
        "brreg": f"https://w2.brreg.no/enhet/sok/detalj.jsp?orgnr={orgnr}",
        "proff": PROFF_URL.format(orgnr=orgnr),
        "gulesider": GULESIDER_URL.format(orgnr=orgnr)
    }
    if phone_number:
        urls["1881"] = f"https://www.1881.no/?query={phone_number}"
    return urls


def _extract_proff_key_figures(soup: BeautifulSoup) -> Dict[str, str]:
    """Extracts key financial figures from a Proff.no page soup."""
    key_figures: Dict[str, str] = {}
    key_figures_table = soup.find('table', class_='key-figures-table')
    if not isinstance(key_figures_table, Tag):
        return key_figures

    for row in key_figures_table.find_all('tr'):
        if not isinstance(row, Tag):
            continue

        cells = row.find_all('td')
        if len(cells) != 2:
            continue

        key_cell, value_cell = cells[0], cells[1]
        if not (key_cell and value_cell):
            continue

        key = key_cell.text.strip()
        value = value_cell.text.strip()
        if key and value:
            key_figures[key] = value

    return key_figures


def scrape_proff(orgnr: str) -> Optional[Dict[str, Any]]:
    """Scrapes Proff.no for additional company details."""
    if not validate_orgnr(orgnr):
        logging.error(f"Invalid orgnr format: {orgnr}")
        return None
        
    logging.info(f"Scraping Proff.no for orgnr {orgnr}.")
    proff_url = PROFF_URL.format(orgnr=orgnr)
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/58.0.3029.110 Safari/537.3'
        )
    }

    try:
        response = requests.get(proff_url, timeout=10, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')

        proff_data: Dict[str, Any] = {}

        name_tag = soup.find('h1')
        if name_tag:
            proff_data['company_name'] = name_tag.text.strip()

        key_figures = _extract_proff_key_figures(soup)
        proff_data['key_figures'] = (
            key_figures if key_figures
            else "No key figures table found with current selectors."
        )

        logging.info(f"Successfully scraped data from Proff.no for {orgnr}.")
        return proff_data

    except requests.exceptions.RequestException as e:
        logging.error(f"Could not scrape Proff.no for {orgnr}: {e}")
        return None  # Changed from {} to None for consistency


# --- Sales Heuristics Engine ---
def apply_sales_heuristics(enriched_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Applies a set of sales rules to the enriched data to generate pipeline
    recommendations.
    """
    pipelines: Dict[str, str] = {}
    now = datetime.now(timezone.utc)

    # Rule: Startup Onboarding Package (Org < 2 yrs old)
    est_date_str = enriched_data.get('stiftelsesdato')
    if est_date_str:
        try:
            est_date = datetime.strptime(est_date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            age_years = (now - est_date).days / 365.25
            if age_years < 2:
                pipelines['Startup Onboarding Package'] = (
                    f"Company is young ({age_years:.1f} years old)."
                )
        except ValueError:
            logging.warning(f"Could not parse stiftelsesdato: {est_date_str}")

    # Rule: Web Design / Security (No website or HTTPS missing)
    website = enriched_data.get('hjemmeside')
    domain_health = enriched_data.get('domain_health', {})
    if not website:
        pipelines['Web Design / Security'] = "No website listed in Brreg."
    elif domain_health.get('ssl_valid') is False:
        pipelines['Web Design / Security'] = "Website does not use HTTPS or has an invalid SSL certificate."

    # Rule: Automation First Entry (No employees listed)
    employees = enriched_data.get('antallAnsatte')
    if employees == 0:
        pipelines['Automation First Entry'] = "No registered employees."

    # Rule: Financial Health
    financial_health = enriched_data.get('financial_health', {})
    if PROFITABILITY_CONCERN in financial_health:
        pipelines['Financial Consulting'] = (
            financial_health[PROFITABILITY_CONCERN]
        )

    # Rule: Fiken User
    if enriched_data.get('fiken_usage', {}).get('uses_fiken'):
        pipelines['Fiken Integration Services'] = "Company appears to use Fiken."

    # Rule: Growth Signals (Hiring)
    job_openings = enriched_data.get('job_openings', {})
    if isinstance(job_openings, dict) and job_openings.get('hiring_status') == "Actively hiring":
        recent_roles = job_openings.get('recent_roles', [])
        if isinstance(recent_roles, list):
            roles_str = [str(r) for r in recent_roles]
            pipelines['Recruitment & HR Services'] = f"Company is actively hiring for roles like: {', '.join(roles_str)}"

    # Rule: Visibility Boost (Weak Proff/LinkedIn presence)
    proff_data = enriched_data.get('proff_data', {})
    if isinstance(proff_data, dict):
        key_figs_value = proff_data.get('key_figures')
        if not key_figs_value or (
            isinstance(key_figs_value, str)
            and "no key figures" in key_figs_value
        ):
            pipelines['Visibility Boost'] = "Weak Proff.no presence."

    # Rule: Domain Health Issues
    if "No MX records" in str(domain_health.get('mx_records')):
        pipelines['Email Setup & Security'] = "Missing MX records suggest broken or poorly configured email."

    # Rule: AI Website Analysis
    ai_analysis = enriched_data.get('ai_analysis', {})
    if "unclear" in ai_analysis.get('summary', '').lower():
        pipelines['Copywriting & UX Review'] = "AI analysis suggests website clarity is low."

    # Rule: Social Media
    socials = enriched_data.get('social_media_presence', {})
    if not any("found" in v.lower() for v in socials.values()):
        pipelines['Social Media Management'] = (
            "Low or no detectable social media presence."
        )

    # Rule: SEO + Reviews (Industry = competition-heavy)
    competitive_industries = [
        "butikkhandel", "restaurant", "eiendomsmegling", "regnskap",
        "programvare", "konsulent", "håndverker"
    ]
    industry_desc = enriched_data.get('naeringskode1', {}).get(
        'beskrivelse', ''
    ).lower()
    if any(term in industry_desc for term in competitive_industries):
        pipelines['SEO + Reviews'] = (
            f"Industry '{industry_desc}' may be competition-heavy."
        )

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

        # --- Stage 3: Map Enriched Data to LACRM Fields and Update ---
        if args.sync_lacrm: # Only perform the full update if sync is enabled
            lacrm_update_payload = map_data_to_lacrm_fields(enriched_data, config)
            if lacrm_update_payload:
                update_lacrm_contact(contact_id, lacrm_update_payload, config, args.dry_run)
            else:
                logging.info(f"No new data to sync for contact {contact_id}.")


def map_data_to_lacrm_fields(enriched_data: Dict[str, Any], config: configparser.ConfigParser) -> Dict[str, Any]:
    """Maps the enriched data dictionary to a dictionary of LACRM Custom Field IDs and values."""
    if 'LACRM_CUSTOM_FIELDS' not in config:
        logging.warning("'LACRM_CUSTOM_FIELDS' section not in config. Cannot map fields.")
        return {}

    mapping_config = config['LACRM_CUSTOM_FIELDS']
    payload = {}

    # Helper to safely add to payload
    def add_to_payload(key: str, value: Any):
        if key in mapping_config and value is not None:
            field_id = mapping_config[key]
            # Simple formatting for various data types
            if isinstance(value, (dict, list)) and value:
                payload[field_id] = json.dumps(value, indent=2, ensure_ascii=False)
            elif isinstance(value, bool):
                payload[field_id] = "Yes" if value else "No"
            elif isinstance(value, str) and value:
                payload[field_id] = value
            elif not isinstance(value, (dict, list, str, bool)):
                payload[field_id] = str(value)


    # --- Mapping Logic ---
    add_to_payload('BrregJson', enriched_data) 
    
    proff_data = enriched_data.get('proff_data')
    if isinstance(proff_data, dict):
        add_to_payload('ProffJson', proff_data)
        key_figures = proff_data.get('key_figures')
        if key_figures and isinstance(key_figures, dict):
            add_to_payload(
                'ProffKeyFigures',
                json.dumps(key_figures, indent=2, ensure_ascii=False)
            )
        elif key_figures:
            add_to_payload('ProffKeyFigures', str(key_figures))

    domain_health = enriched_data.get('domain_health')
    if isinstance(domain_health, dict):
        add_to_payload('DomainHealth', domain_health)
        add_to_payload('SslValid', domain_health.get('ssl_valid'))

    tech_stack = enriched_data.get('tech_stack')
    if (tech_stack and isinstance(tech_stack, dict) and
            not tech_stack.get("error")):
        add_to_payload('TechStack', tech_stack)

    ai_summary = enriched_data.get('ai_analysis', {}).get('summary')
    if ai_summary:
        add_to_payload('AiAnalysis', ai_summary)
    
    # Add new fields
    add_to_payload('FinancialHealth', enriched_data.get('financial_health'))
    add_to_payload('UsesFiken', enriched_data.get('fiken_usage', {}).get('uses_fiken'))
    add_to_payload('CompanyNews', enriched_data.get('company_news'))
    add_to_payload('JobOpenings', enriched_data.get('job_openings'))

    recommendations = apply_sales_heuristics(enriched_data)
    if recommendations:
        # Format recommendations into a readable string
        rec_string = "\n".join([f"- {pipeline}: {reason}" for pipeline, reason in recommendations.items()])
        add_to_payload('SalesRecommendations', rec_string)

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
    manual_group = parser.add_argument_group('USER MANUAL')
    manual_group.add_argument(
        '-h', '--help', action='help',
        help="Show this help message and exit.\n\n"
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
