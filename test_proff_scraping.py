#!/usr/bin/env python3
"""
Test the updated Proff.no scraping function
"""

import sys
import os

# Add the current directory to Python path to import lacrm_sync
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import required modules
import requests
from bs4 import BeautifulSoup
import logging
import json
from typing import Optional, Dict, Any

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

PROFF_URL = "https://www.proff.no/company/{orgnr}"

def scrape_proff(orgnr: str) -> Optional[Dict[str, Any]]:
    """
    Scrapes key financial and company data from Proff.no.
    Updated for the new Proff.no site structure (2025).
    """
    try:
        url = PROFF_URL.format(orgnr=orgnr)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'no,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            logging.warning(f"Proff.no returned status {response.status_code} for {orgnr}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        proff_data = {
            'url': url,
            'key_figures': {},
            'company_description': '',
            'contact_info': {}
        }
        
        # Extract financial data from the new structure
        # Look for the accounting table with class "AccountFiguresWidget-accountingtable"
        financial_table = soup.find('table', class_='AccountFiguresWidget-accountingtable')
        if financial_table:
            print("✅ Found financial table!")
            figures = {}
            rows = financial_table.find_all('tr')
            for row in rows:
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 2:
                    key_elem = cells[0]
                    value_elem = cells[1]
                    
                    # Skip header rows
                    if key_elem.name == 'th' and value_elem.name == 'th':
                        continue
                    
                    key = key_elem.get_text(strip=True)
                    value = value_elem.get_text(strip=True)
                    
                    # Filter out non-financial entries
                    if key and value and key not in ['Regnskap', 'Valuta']:
                        # Clean up the value (remove NOK, convert negative signs)
                        cleaned_value = value.replace('NOK', '').replace('−', '-').strip()
                        figures[key] = cleaned_value
                        print(f"  {key}: {cleaned_value}")
            
            if figures:
                proff_data['key_figures'] = figures
        else:
            print("❌ No financial table found")
        
        # Also try to extract from StatsWidget cells (summary stats at top)
        stats_widgets = soup.find_all('div', class_='StatsWidget-cell')
        if stats_widgets:
            print(f"✅ Found {len(stats_widgets)} stats widgets!")
            if not proff_data['key_figures']:
                figures = {}
                for widget in stats_widgets:
                    header_elem = widget.find('span', class_='StatsWidget-header')
                    value_elem = widget.find('span', class_='StatsWidget-value')
                    
                    if header_elem and value_elem:
                        key = header_elem.get_text(strip=True)
                        value = value_elem.get_text(strip=True)
                        
                        # Only keep financial figures, skip company form etc.
                        if any(term in key.lower() for term in ['inntekt', 'resultat', 'ebitda', 'omsetning']):
                            # Clean up the value
                            cleaned_value = value.replace('NOK', '').replace('−', '-').strip()
                            figures[key] = cleaned_value
                            print(f"  Widget: {key}: {cleaned_value}")
                
                if figures:
                    proff_data['key_figures'] = figures
        else:
            print("❌ No stats widgets found")
        
        # Extract company description from meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            proff_data['company_description'] = meta_desc.get('content', '')
            print(f"✅ Company description: {proff_data['company_description'][:100]}...")
        
        # Try to extract contact information
        # Look for contact info in various possible locations
        contact_info = {}
        
        # Look for phone, email, etc. in the text content
        page_text = soup.get_text()
        
        # Simple email extraction
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, page_text)
        if emails:
            contact_info['email'] = emails[0]  # Take the first email found
            print(f"✅ Found email: {emails[0]}")
        
        # Simple phone extraction (Norwegian format)
        phone_pattern = r'(?:\+47\s?)?(?:\d{2}\s?\d{2}\s?\d{2}\s?\d{2}|\d{8})'
        phones = re.findall(phone_pattern, page_text)
        if phones:
            contact_info['phone'] = phones[0]
            print(f"✅ Found phone: {phones[0]}")
        
        proff_data['contact_info'] = contact_info
        
        # If we got some data, consider it successful
        if proff_data['key_figures'] or proff_data['company_description']:
            logging.info(f"Successfully scraped Proff.no data for {orgnr}")
            return proff_data
        else:
            logging.warning(f"No meaningful data extracted from Proff.no for {orgnr}")
            return None
        
    except Exception as e:
        logging.error(f"Failed to scrape Proff.no for {orgnr}: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_proff_scraping():
    """Test the updated Proff.no scraping function"""
    test_orgnrs = [
        "931122541",  # User's company
        "923609016",  # DNB (large company)
    ]
    
    print("🧪 TESTING UPDATED PROFF.NO SCRAPING")
    print("=" * 60)
    
    for orgnr in test_orgnrs:
        print(f"\n🔍 Testing orgnr: {orgnr}")
        print("-" * 40)
        
        result = scrape_proff(orgnr)
        
        if result:
            print("✅ Scraping successful!")
            print("📊 Results:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            # Save results
            with open(f'proff_scrape_test_{orgnr}.json', 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"Saved to proff_scrape_test_{orgnr}.json")
        else:
            print("❌ Scraping failed!")
        
        print("-" * 40)

if __name__ == "__main__":
    test_proff_scraping()
