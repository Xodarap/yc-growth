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

prompt = f"""
Search the internet for the market valuation of "{company['name']}" for each of these years: {', '.join(map(str, years))}

Please search for:
- Funding rounds and valuations
- IPO information if public  
- Acquisition details if acquired
- Market cap data if publicly traded

When you have gathered the valuation data, use the submit_valuations tool to submit your final answer.

For each year, provide:
- The valuation amount (e.g., "$95B", "$50M")
- The source URL where you found this information
- Brief notes about the context (funding round, IPO, etc.)

If you cannot find data for a specific year, still include that year with "Not found" as the valuation.
"""

# Define the custom submit tool
submit_tool = {
    "name": "submit_valuations",
    "description": "Submit the final valuation data for the company",
    "input_schema": {
        "type": "object",
        "properties": {
            "company": {
                "type": "string",
                "description": "Name of the company"
            },
            "valuations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "year": {
                            "type": "integer",
                            "description": "Year of the valuation"
                        },
                        "valuation": {
                            "type": "string", 
                            "description": "Valuation amount (e.g., '$95B', '$50M') or 'Not found'"
                        },
                        "source": {
                            "type": "string",
                            "description": "URL source where the valuation was found, or 'N/A'"
                        },
                        "notes": {
                            "type": "string",
                            "description": "Brief context about the valuation"
                        }
                    },
                    "required": ["year", "valuation", "source", "notes"]
                }
            }
        },
        "required": ["company", "valuations"]
    }
}

client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=4000,
    temperature=0.1,
    messages=[{
        "role": "user",
        "content": prompt
    }],
    tools=[
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5
        },
        submit_tool
    ]
)

print("=== CLAUDE RESPONSE ===")
print("Number of content blocks:", len(message.content))

submitted_data = None

for i, content_block in enumerate(message.content):
    print(f"\nBlock {i}: {type(content_block).__name__}")
    
    if hasattr(content_block, 'text') and content_block.text:
        print("TEXT CONTENT:")
        print(content_block.text)
    
    if hasattr(content_block, 'name') and content_block.name == 'submit_valuations':
        print("🎯 SUBMITTED VALUATIONS:")
        submitted_data = content_block.input
        print(json.dumps(submitted_data, indent=2))
    
    print("-" * 50)

if submitted_data:
    print("\n✅ Successfully received structured data via submit tool!")
    print(f"Company: {submitted_data['company']}")
    print(f"Found {len(submitted_data['valuations'])} valuation entries")
else:
    print("\n❌ No data submitted via submit tool")

print("======================")