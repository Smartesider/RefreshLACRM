#!/usr/bin/env python3
"""
Test new Proff.no URL patterns based on site inspection
"""

import requests
from bs4 import BeautifulSoup
import json

def test_new_proff_patterns(orgnr: str):
    """Test new URL patterns discovered from site inspection"""
    print(f"Testing new patterns for orgnr: {orgnr}")
    print("=" * 60)
    
    # Based on the HTML analysis, try these patterns that seem to be used by the new site
    url_patterns = [
        # New patterns discovered from site analysis
        f"https://www.proff.no/company/{orgnr}",
        f"https://www.proff.no/enterprise/{orgnr}",
        f"https://www.proff.no/firm/{orgnr}",
        f"https://www.proff.no/search?q={orgnr}",
        f"https://www.proff.no/search/{orgnr}",
        
        # Try API endpoints that might exist
        f"https://www.proff.no/api/company/{orgnr}",
        f"https://www.proff.no/api/enterprise/{orgnr}",
        
        # Try with Norwegian paths
        f"https://www.proff.no/foretaksinfo/{orgnr}",
        f"https://www.proff.no/bedriftsinfo/{orgnr}",
        f"https://www.proff.no/firmainfo/{orgnr}",
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'no,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    working_urls = []
    
    for url in url_patterns:
        try:
            print(f"\nTesting: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.find('title')
                title_text = title.get_text() if title else 'No title'
                print(f"✅ SUCCESS! Title: {title_text}")
                
                # Check if the orgnr appears in the content
                if orgnr in response.text:
                    print(f"✅ Organization number {orgnr} found in page content")
                    working_urls.append(url)
                    
                    # Save the working response
                    with open(f'proff_working_{orgnr}_{len(working_urls)}.html', 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    print(f"Saved to proff_working_{orgnr}_{len(working_urls)}.html")
                else:
                    print("⚠️  Organization number not found in content")
                    
            elif response.status_code in [301, 302, 307, 308]:
                location = response.headers.get('Location', 'Unknown')
                print(f"🔄 Redirect to: {location}")
                
                # Follow the redirect if it looks promising
                if any(keyword in location.lower() for keyword in ['company', 'bedrift', 'selskap', orgnr]):
                    print(f"Following redirect to: {location}")
                    if not location.startswith('http'):
                        location = 'https://www.proff.no' + location
                    
                    redirect_response = requests.get(location, headers=headers, timeout=10)
                    if redirect_response.status_code == 200 and orgnr in redirect_response.text:
                        print(f"✅ Redirect SUCCESS! Final URL: {location}")
                        working_urls.append(location)
                        
                        with open(f'proff_redirect_{orgnr}_{len(working_urls)}.html', 'w', encoding='utf-8') as f:
                            f.write(redirect_response.text)
                        print(f"Saved redirect result to proff_redirect_{orgnr}_{len(working_urls)}.html")
                        
            else:
                print(f"❌ Failed with status {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    return working_urls

def test_proff_search_api(orgnr: str):
    """Test if there's a search API we can use"""
    print(f"\n🔍 Testing search functionality for {orgnr}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'no,en;q=0.5',
        'Content-Type': 'application/json',
        'Origin': 'https://www.proff.no',
        'Referer': 'https://www.proff.no/'
    }
    
    # Try different API endpoints that might exist
    api_endpoints = [
        'https://www.proff.no/api/search',
        'https://www.proff.no/api/autocomplete',
        'https://www.proff.no/api/companies/search',
        'https://api.proff.no/search',
        'https://api.proff.no/companies',
    ]
    
    search_payloads = [
        {'q': orgnr},
        {'query': orgnr},
        {'search': orgnr},
        {'organisationNumber': orgnr},
        {'orgNr': orgnr}
    ]
    
    for endpoint in api_endpoints:
        for payload in search_payloads:
            try:
                print(f"POST {endpoint} with {payload}")
                response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
                print(f"Status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"✅ JSON response received: {json.dumps(data, indent=2)[:500]}...")
                        
                        # Save the API response
                        with open(f'proff_api_response_{orgnr}.json', 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        print(f"Saved API response to proff_api_response_{orgnr}.json")
                        
                        return endpoint, payload, data
                    except json.JSONDecodeError:
                        print("Response is not JSON")
                elif response.status_code != 404:
                    print(f"Non-404 response: {response.text[:200]}")
                    
            except Exception as e:
                print(f"Error: {e}")
    
    return None

if __name__ == "__main__":
    test_orgnr = "931122541"  # User's company
    
    print("🔧 PROFF.NO NEW PATTERN DISCOVERY")
    print("=" * 60)
    
    # Test new URL patterns
    working_urls = test_new_proff_patterns(test_orgnr)
    
    # Test API endpoints
    api_result = test_proff_search_api(test_orgnr)
    
    print(f"\n📊 RESULTS SUMMARY")
    print("=" * 40)
    
    if working_urls:
        print(f"✅ Found {len(working_urls)} working URLs:")
        for url in working_urls:
            print(f"  - {url}")
    else:
        print("❌ No working URLs found")
    
    if api_result:
        endpoint, payload, data = api_result
        print(f"✅ Found working API: {endpoint} with {payload}")
    else:
        print("❌ No working API found")
    
    if not working_urls and not api_result:
        print("\n💡 SUGGESTIONS:")
        print("1. Proff.no may have completely changed their architecture")
        print("2. They might be using client-side rendering with JavaScript")
        print("3. Consider using Selenium for browser automation")
        print("4. Look for alternative Norwegian business data sources")
        print("5. Check if they have an official API with registration")
