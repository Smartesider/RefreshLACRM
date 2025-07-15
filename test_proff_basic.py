#!/usr/bin/env python3
"""
Test basic Proff.no connectivity
"""

import requests
from bs4 import BeautifulSoup

def test_proff_main_site():
    """Test if we can access Proff.no at all"""
    print("Testing basic Proff.no connectivity...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'no,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    urls_to_test = [
        'https://www.proff.no',
        'https://proff.no',
        'https://www.proff.no/',
    ]
    
    for url in urls_to_test:
        try:
            print(f"\nTesting: {url}")
            response = requests.get(url, headers=headers, timeout=15)
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.find('title')
                print(f"Title: {title.get_text() if title else 'No title'}")
                
                # Look for search functionality
                search_forms = soup.find_all('form')
                search_inputs = soup.find_all('input', {'type': 'search'}) + soup.find_all('input', {'name': lambda x: x and 'search' in x.lower()})
                
                print(f"Found {len(search_forms)} forms and {len(search_inputs)} search inputs")
                
                # Look for any links that might indicate company pages
                links = soup.find_all('a', href=True)
                company_related_links = []
                
                for link in links[:20]:  # Check first 20 links
                    href = link.get('href', '')
                    text = link.get_text().strip()
                    if any(keyword in href.lower() for keyword in ['selskap', 'bedrift', 'enhet', 'org', 'firma']):
                        company_related_links.append((href, text))
                
                if company_related_links:
                    print(f"\nFound {len(company_related_links)} company-related links:")
                    for href, text in company_related_links[:5]:
                        print(f"  - {href} | {text}")
                
                # Save the main page for inspection
                with open(f'proff_main_page.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"Saved main page to proff_main_page.html")
                
                return True
                
            elif response.status_code in [301, 302]:
                print(f"Redirect to: {response.headers.get('Location', 'Unknown')}")
            else:
                print(f"Failed with status {response.status_code}")
                if response.text:
                    print(f"Response preview: {response.text[:200]}")
                
        except Exception as e:
            print(f"Error accessing {url}: {e}")
    
    return False

if __name__ == "__main__":
    print("🌐 PROFF.NO CONNECTIVITY TEST")
    print("=" * 50)
    
    success = test_proff_main_site()
    
    if success:
        print("\n✅ Successfully connected to Proff.no")
        print("The site structure may have changed, requiring a different approach.")
    else:
        print("\n❌ Could not connect to Proff.no")
        print("The site may be blocking automated requests or is temporarily unavailable.")
