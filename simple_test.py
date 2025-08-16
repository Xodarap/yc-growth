#!/usr/bin/env python3

import os
import json
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

# Test company
company = {
    "name": "Stripe",
    "batch": "S09",
    "description": "Online payment processing platform for internet businesses",
    "website": "https://stripe.com"
}

years = [2021, 2022, 2023]
years_str = ', '.join(map(str, years))

prompt = f"""
I need you to search the internet for the market valuation/company value of "{company['name']}" for each of these years: {years_str}

Please return your response as a valid JSON object with this EXACT structure:

{{
  "company": "{company['name']}",
  "analysis_date": "2024-XX-XX",
  "valuations": [
    {{
      "year": 2021,
      "valuation": "$36B",
      "source": "https://techcrunch.com/exact-url",
      "notes": "Series G funding round led by Sequoia"
    }}
  ]
}}

Search the internet for funding rounds, IPO data, and market valuations from reputable sources.
"""

client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=4000,
    temperature=0.1,
    messages=[{
        "role": "user",
        "content": prompt
    }],
    tools=[{
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 5
    }]
)

print("=== CLAUDE RESPONSE ===")
print("Number of content blocks:", len(message.content))

for i, content_block in enumerate(message.content):
    print(f"\nBlock {i}: {type(content_block).__name__}")
    
    if hasattr(content_block, 'text') and content_block.text:
        print("TEXT CONTENT:")
        print(content_block.text)
    
    if hasattr(content_block, 'input'):
        print("TOOL INPUT:")
        print(json.dumps(content_block.input, indent=2))
    
    if hasattr(content_block, 'content') and hasattr(content_block.content, '__iter__'):
        print(f"SEARCH RESULTS: {len(content_block.content)} results found")
        for j, result in enumerate(content_block.content):
            if hasattr(result, 'url'):
                print(f"  {j+1}. {result.url}")
                if hasattr(result, 'title'):
                    print(f"     Title: {result.title}")
    
    print("-" * 50)

print("======================")