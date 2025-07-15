#!/usr/bin/env python3
"""
Test script to find the correct Proff.no URL format
"""

import requests
from bs4 import BeautifulSoup
import time

def test_proff_url_formats(orgnr: str):
    """Test different URL formats for Proff.no"""
    print(f"Testing different URL formats for orgnr: {orgnr}")
    print("=" * 60)
    
    # Different URL formats to try
    url_formats = [
        f"https://www.proff.no/selskap/{orgnr}",
        f"https://www.proff.no/regnskap/{orgnr}",
        f"https://www.proff.no/bedrift/{orgnr}",
        f"https://www.proff.no/org/{orgnr}",
        f"https://www.proff.no/foretaksregister/{orgnr}",
        f"https://www.proff.no/sok/{orgnr}",
        f"https://www.proff.no/enheter/{orgnr}",
        f"https://proff.no/selskap/{orgnr}",
        f"https://proff.no/bedrift/{orgnr}",
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for url in url_formats:
        try:
            print(f"\nTrying: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.find('title')
                print(f"✅ SUCCESS! Title: {title.get_text() if title else 'No title'}")
                
                # Look for company name or orgnr in the page
                if orgnr in response.text:
                    print(f"✅ Organization number {orgnr} found in page content")
                
                # Save successful response for inspection
                with open(f'proff_success_{orgnr}.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"Saved response to proff_success_{orgnr}.html")
                return url
                
            elif response.status_code == 302 or response.status_code == 301:
                print(f"🔄 Redirect to: {response.headers.get('Location', 'Unknown')}")
            else:
                print(f"❌ Failed with status {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Small delay to be respectful to the server
        time.sleep(0.5)
    
    return None

def search_proff_for_orgnr(orgnr: str):
    """Try to search for the organization on Proff.no"""
    print(f"\n🔍 Searching Proff.no for orgnr: {orgnr}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Try the main search page
    search_url = f"https://www.proff.no/sok"
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        print(f"Search page status: {response.status_code}")
        
        if response.status_code == 200:
            # Try searching with the organization number
            search_params = {
                'q': orgnr,
                'type': 'company'
            }
            
            search_response = requests.get(search_url, params=search_params, headers=headers, timeout=10)
            print(f"Search results status: {search_response.status_code}")
            
            if search_response.status_code == 200:
                soup = BeautifulSoup(search_response.text, 'html.parser')
                
                # Look for links to company pages
                links = soup.find_all('a', href=True)
                company_links = [link for link in links if orgnr in link.get('href', '')]
                
                if company_links:
                    print(f"✅ Found {len(company_links)} links containing the orgnr:")
                    for link in company_links[:3]:  # Show first 3
                        href = link.get('href')
                        text = link.get_text().strip()
                        print(f"  - {href} | {text}")
                        
                    # Try the first link
                    first_link = company_links[0].get('href')
                    if not first_link.startswith('http'):
                        first_link = 'https://www.proff.no' + first_link
                    
                    print(f"\nTrying first search result: {first_link}")
                    return test_direct_url(first_link, orgnr)
                else:
                    print("❌ No company links found in search results")
    
    except Exception as e:
        print(f"❌ Search error: {e}")
    
    return None

def test_direct_url(url: str, orgnr: str):
    """Test a direct URL"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Direct URL status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.find('title')
            print(f"✅ SUCCESS! Title: {title.get_text() if title else 'No title'}")
            
            with open(f'proff_direct_{orgnr}.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"Saved response to proff_direct_{orgnr}.html")
            return url
            
    except Exception as e:
        print(f"❌ Direct URL error: {e}")
    
    return None

if __name__ == "__main__":
    test_orgnr = "931122541"  # User's company
    
    print("🔧 PROFF.NO URL FORMAT DISCOVERY TOOL")
    print("=" * 60)
    
    # First try different URL formats
    working_url = test_proff_url_formats(test_orgnr)
    
    if not working_url:
        # If no direct URL works, try searching
        working_url = search_proff_for_orgnr(test_orgnr)
    
    if working_url:
        print(f"\n✅ Found working URL format: {working_url}")
    else:
        print(f"\n❌ Could not find working URL format for {test_orgnr}")
        print("The Proff.no site structure may have changed significantly.")
