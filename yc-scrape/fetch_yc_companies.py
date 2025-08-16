#!/usr/bin/env python3
import requests
import json
import csv
from typing import List, Dict, Any

def fetch_yc_companies() -> List[Dict[str, Any]]:
    """Fetch YC company data from Algolia API"""
    url = "https://45bwzj1sgc-dsn.algolia.net/1/indexes/*/queries"
    
    headers = {
        'Accept-Language': 'en-US,en;q=0.9,es-US;q=0.8,es;q=0.7,su;q=0.6',
        'Connection': 'keep-alive',
        'Origin': 'https://www.ycombinator.com',
        'Referer': 'https://www.ycombinator.com/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'x-algolia-agent': 'Algolia for JavaScript (3.35.1); Browser; JS Helper (3.16.1)',
        'x-algolia-application-id': '45BWZJ1SGC',
        'x-algolia-api-key': 'MjBjYjRiMzY0NzdhZWY0NjExY2NhZjYxMGIxYjc2MTAwNWFkNTkwNTc4NjgxYjU0YzFhYTY2ZGQ5OGY5NDMxZnJlc3RyaWN0SW5kaWNlcz0lNUIlMjJZQ0NvbXBhbnlfcHJvZHVjdGlvbiUyMiUyQyUyMllDQ29tcGFueV9CeV9MYXVuY2hfRGF0ZV9wcm9kdWN0aW9uJTIyJTVEJnRhZ0ZpbHRlcnM9JTVCJTIyeWNkY19wdWJsaWMlMjIlNUQmYW5hbHl0aWNzVGFncz0lNUIlMjJ5Y2RjJTIyJTVE'
    }
    
    data = {
        "requests": [{
            "indexName": "YCCompany_production",
            "params": "facets=%5B%22app_answers%22%2C%22app_video_public%22%2C%22batch%22%2C%22demo_day_video_public%22%2C%22industries%22%2C%22isHiring%22%2C%22nonprofit%22%2C%22question_answers%22%2C%22regions%22%2C%22subindustry%22%2C%22top_company%22%5D&hitsPerPage=1000&maxValuesPerFacet=1000&page=0&query=&tagFilters="
        }]
    }
    
    all_companies = []
    page = 0
    
    while True:
        print(f"Fetching page {page}...")
        
        # Update page number in params
        data["requests"][0]["params"] = data["requests"][0]["params"].replace(f"page={page-1}", f"page={page}") if page > 0 else data["requests"][0]["params"]
        if page > 0:
            data["requests"][0]["params"] = data["requests"][0]["params"].replace("page=0", f"page={page}")
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            break
            
        result = response.json()
        hits = result["results"][0]["hits"]
        
        if not hits:
            break
            
        all_companies.extend(hits)
        print(f"Retrieved {len(hits)} companies from page {page}")
        
        # Check if we got less than 1000 results (last page)
        if len(hits) < 1000:
            break
            
        page += 1
    
    print(f"Total companies retrieved: {len(all_companies)}")
    return all_companies

def extract_company_data(companies: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Extract relevant company information"""
    extracted_data = []
    
    for company in companies:
        company_data = {
            'name': company.get('name', ''),
            'batch': company.get('batch', ''),
            'website': company.get('website', '')
        }
        extracted_data.append(company_data)
    
    return extracted_data

def save_to_csv(data: List[Dict[str, str]], filename: str = 'yc_companies.csv'):
    """Save company data to CSV file"""
    if not data:
        print("No data to save")
        return
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['name', 'batch', 'website']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(data)
    
    print(f"Data saved to {filename}")

def main():
    print("Fetching YC company data...")
    companies = fetch_yc_companies()
    
    print("Extracting relevant data...")
    extracted_data = extract_company_data(companies)
    
    print("Saving to CSV...")
    save_to_csv(extracted_data)
    
    print("Done!")

if __name__ == "__main__":
    main()