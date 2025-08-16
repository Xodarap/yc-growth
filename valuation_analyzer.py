#!/usr/bin/env python3

import os
import csv
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

class ValuationAnalyzer:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.current_year = datetime.now().year
        
    def read_companies_csv(self, input_file):
        """Read companies from input CSV file."""
        companies = []
        with open(input_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                companies.append({
                    'name': row['company'],
                    'founded_year': int(row['founded_year']),
                    'website': row.get('website', '')
                })
        return companies
    
    def get_years_to_analyze(self, founded_year):
        """Get list of years from founding to current year."""
        return list(range(founded_year, self.current_year + 1))
    
    def create_valuation_prompt(self, company, years):
        """Create prompt for Claude to search for company valuations."""
        years_str = ', '.join(map(str, years))
        
        return f"""
Search the internet for the market valuation of "{company['name']}" for each of these years: {years_str}

Company website: {company['website']}
Founded: {company['founded_year']}

Please search for:
- Funding rounds and valuations
- IPO information if public
- Acquisition details if acquired  
- Market cap data if publicly traded
- Private market valuations

Search sources like:
- TechCrunch, Bloomberg, Reuters
- SEC filings and regulatory documents
- Company press releases
- Crunchbase, PitchBook
- Financial news sites

When you have gathered the data, use the submit_valuations tool to submit your findings.

For each year, provide:
- The valuation amount (e.g., "$95B", "$50M") 
- The source URL where you found this information
- Brief notes about the context

Include ALL years from {company['founded_year']} to {self.current_year}, even if no valuation data exists (use "Not found").
"""
    
    async def analyze_company(self, company, csv_writer):
        """Analyze a single company and write results to CSV immediately."""
        print(f"\n🔍 Analyzing {company['name']} (founded {company['founded_year']})...")
        
        years = self.get_years_to_analyze(company['founded_year'])
        print(f"   Years to analyze: {len(years)} years ({years[0]}-{years[-1]})")
        
        # Define the submit tool
        submit_tool = {
            "name": "submit_valuations",
            "description": "Submit the final valuation data for the company",
            "input_schema": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "valuations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "year": {"type": "integer"},
                                "valuation": {"type": "string"},
                                "source": {"type": "string"},
                                "notes": {"type": "string"}
                            },
                            "required": ["year", "valuation", "source", "notes"]
                        }
                    }
                },
                "required": ["company", "valuations"]
            }
        }
        
        try:
            prompt = self.create_valuation_prompt(company, years)
            
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=6000,
                messages=[{"role": "user", "content": prompt}],
                tools=[
                    {"type": "web_search_20250305", "name": "web_search", "max_uses": 8},
                    submit_tool
                ]
            )
            
            # Find the submitted data
            submitted_data = None
            for content_block in message.content:
                if hasattr(content_block, 'name') and content_block.name == 'submit_valuations':
                    submitted_data = content_block.input
                    break
            
            if submitted_data:
                # Write each valuation to CSV immediately
                for val_data in submitted_data['valuations']:
                    csv_writer.writerow({
                        'company': company['name'],
                        'year': val_data['year'],
                        'valuation': val_data['valuation'],
                        'source': val_data['source'],
                        'notes': val_data['notes']
                    })
                
                print(f"   ✅ Found {len(submitted_data['valuations'])} valuations, written to CSV")
                return len(submitted_data['valuations'])
            else:
                print(f"   ❌ No data submitted for {company['name']}")
                return 0
                
        except Exception as e:
            print(f"   ❌ Error analyzing {company['name']}: {str(e)}")
            return 0
    
    async def analyze_all_companies(self, input_file, output_file):
        """Analyze all companies and stream results to CSV."""
        companies = self.read_companies_csv(input_file)
        print(f"📊 Loaded {len(companies)} companies from {input_file}")
        
        # Open CSV file for streaming output
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['company', 'year', 'valuation', 'source', 'notes']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            total_valuations = 0
            
            for i, company in enumerate(companies, 1):
                print(f"\n📈 Processing {i}/{len(companies)}: {company['name']}")
                
                valuations_found = await self.analyze_company(company, writer)
                total_valuations += valuations_found
                
                # Flush to ensure data is written immediately
                f.flush()
                
                # Rate limiting
                if i < len(companies):
                    print("   ⏳ Waiting 3 seconds...")
                    await asyncio.sleep(3)
            
            print(f"\n🎉 Analysis complete!")
            print(f"   Companies processed: {len(companies)}")
            print(f"   Total valuations found: {total_valuations}")
            print(f"   Results written to: {output_file}")

async def main():
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("❌ Error: Please set ANTHROPIC_API_KEY in .env file")
        return
    
    analyzer = ValuationAnalyzer()
    await analyzer.analyze_all_companies('companies_input.csv', 'streaming_results.csv')

if __name__ == "__main__":
    asyncio.run(main())