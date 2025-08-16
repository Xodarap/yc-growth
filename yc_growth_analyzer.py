#!/usr/bin/env python3
"""
YC Company Growth Analyzer

This script analyzes the growth of Y Combinator companies over various years
by using Claude AI to research and analyze company data.
"""

import json
import asyncio
import logging
import os
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime
import argparse
import sys
import re

try:
    import anthropic
    from anthropic import Anthropic
    from dotenv import load_dotenv
except ImportError:
    print("Error: Required packages not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class YCGrowthAnalyzer:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the analyzer with Anthropic API key."""
        if not api_key:
            api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if not api_key:
            raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY in .env file or pass --api-key")
        
        self.client = Anthropic(api_key=api_key)
        
    def load_companies(self, file_path: str) -> List[Dict[str, Any]]:
        """Load company data from JSON file."""
        try:
            with open(file_path, 'r') as f:
                companies = json.load(f)
            logger.info(f"Loaded {len(companies)} companies from {file_path}")
            return companies
        except FileNotFoundError:
            logger.error(f"Company file not found: {file_path}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in company file: {e}")
            return []

    def create_valuation_search_prompt(self, company: Dict[str, Any], years: List[int]) -> str:
        """Create a prompt for Claude to search for company valuations."""
        company_name = company.get('name', 'Unknown Company')
        company_website = company.get('website', '')
        years_str = ', '.join(map(str, years))
        
        prompt = f"""
I need you to search the internet for the market valuation/company value of "{company_name}" for each of these years: {years_str}

Company website: {company_website}

Please search online for:
1. Funding rounds and valuations
2. IPO information if public
3. Acquisition details if acquired
4. Market cap data if publicly traded
5. Private market valuations from funding announcements

IMPORTANT: I need you to actually search the internet for this information. Look for:
- News articles about funding rounds
- SEC filings
- Company press releases
- Financial news sites (TechCrunch, Bloomberg, Reuters, etc.)
- Investment databases (Crunchbase, PitchBook, etc.)

For each year where you find valuation data, please provide EXACTLY this format:

YEAR: [year]
VALUATION: [dollar amount, e.g., $1.2B or $500M]
SOURCE: [exact website URL where you found this information]
NOTES: [brief context about the valuation - funding round, IPO, etc.]

---

If you cannot find valuation data for a specific year, write:
YEAR: [year]
VALUATION: Not found
SOURCE: N/A
NOTES: No valuation data available for this year

---

Please search thoroughly and provide the most recent and reliable sources. Focus on official announcements, reputable financial news, and regulatory filings.
"""
        return prompt

    def parse_valuation_response(self, response_text: str, company_name: str, years: List[int]) -> List[Dict[str, Any]]:
        """Parse Claude's response to extract valuation data."""
        valuations = []
        
        # Split response by year sections
        sections = response_text.split('---')
        
        for section in sections:
            if not section.strip():
                continue
                
            year_match = re.search(r'YEAR:\s*(\d{4})', section)
            valuation_match = re.search(r'VALUATION:\s*([^\n]+)', section)
            source_match = re.search(r'SOURCE:\s*([^\n]+)', section)
            notes_match = re.search(r'NOTES:\s*([^\n]+)', section)
            
            if year_match:
                year = int(year_match.group(1))
                valuation = valuation_match.group(1).strip() if valuation_match else 'Not found'
                source = source_match.group(1).strip() if source_match else 'N/A'
                notes = notes_match.group(1).strip() if notes_match else ''
                
                valuations.append({
                    'company': company_name,
                    'year': year,
                    'valuation': valuation,
                    'source': source,
                    'notes': notes
                })
        
        # Ensure we have entries for all requested years
        found_years = {v['year'] for v in valuations}
        for year in years:
            if year not in found_years:
                valuations.append({
                    'company': company_name,
                    'year': year,
                    'valuation': 'Not found',
                    'source': 'N/A',
                    'notes': 'No data available'
                })
        
        return valuations

    async def analyze_company_valuations(self, company: Dict[str, Any], years: List[int]) -> List[Dict[str, Any]]:
        """Analyze valuations for a single company."""
        company_name = company.get('name', 'Unknown')
        logger.info(f"Searching valuations for {company_name}")
        
        try:
            prompt = self.create_valuation_search_prompt(company, years)
            
            message = self.client.messages.create(
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
            
            response_text = message.content[0].text
            valuations = self.parse_valuation_response(response_text, company_name, years)
            
            logger.info(f"Found {len(valuations)} valuation entries for {company_name}")
            return valuations
            
        except Exception as e:
            logger.error(f"Error analyzing {company_name}: {str(e)}")
            # Return error entries for all years
            return [{
                'company': company_name,
                'year': year,
                'valuation': 'Error',
                'source': 'N/A',
                'notes': f'API Error: {str(e)}'
            } for year in years]

    async def analyze_all_companies(self, companies: List[Dict[str, Any]], years: List[int]) -> List[Dict[str, Any]]:
        """Analyze valuations for all companies."""
        logger.info(f"Starting valuation analysis of {len(companies)} companies for years {years}")
        
        all_valuations = []
        for i, company in enumerate(companies, 1):
            logger.info(f"Processing company {i}/{len(companies)}")
            company_valuations = await self.analyze_company_valuations(company, years)
            all_valuations.extend(company_valuations)
            
            # Add a small delay to respect API rate limits
            await asyncio.sleep(2)
        
        return all_valuations

    def save_results_csv(self, valuations: List[Dict[str, Any]], output_file: str):
        """Save valuation results to CSV file."""
        try:
            fieldnames = ['company', 'year', 'valuation', 'source', 'notes']
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                # Sort by company name, then by year
                sorted_valuations = sorted(valuations, key=lambda x: (x['company'], x['year']))
                writer.writerows(sorted_valuations)
            
            logger.info(f"Results saved to {output_file}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")

    def generate_summary_report(self, valuations: List[Dict[str, Any]], years: List[int]) -> str:
        """Generate a summary report of the valuation analysis."""
        companies = set(v['company'] for v in valuations)
        total_companies = len(companies)
        
        # Count how many valuations were found vs not found
        found_valuations = len([v for v in valuations if v['valuation'] not in ['Not found', 'Error']])
        total_possible = len(companies) * len(years)
        
        summary = f"""
YC Company Valuation Analysis Summary
====================================

Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Companies Analyzed: {total_companies}
Years Analyzed: {', '.join(map(str, years))}
Valuations Found: {found_valuations}/{total_possible} ({found_valuations/total_possible*100:.1f}%)

Company Results:
"""
        
        for company in sorted(companies):
            company_vals = [v for v in valuations if v['company'] == company]
            found_count = len([v for v in company_vals if v['valuation'] not in ['Not found', 'Error']])
            summary += f"- {company}: {found_count}/{len(years)} valuations found\n"
        
        return summary


async def main():
    parser = argparse.ArgumentParser(description='Analyze YC company growth using Claude AI')
    parser.add_argument('--companies', required=True, help='Path to JSON file containing company data')
    parser.add_argument('--api-key', help='Anthropic API key (or set ANTHROPIC_API_KEY in .env)')
    parser.add_argument('--years', nargs='+', type=int, default=[2020, 2021, 2022, 2023, 2024],
                       help='Years to analyze (default: 2020 2021 2022 2023 2024)')
    parser.add_argument('--output', default='yc_growth_analysis.json', help='Output file for results')
    parser.add_argument('--summary', default='yc_growth_summary.txt', help='Output file for summary report')
    
    args = parser.parse_args()
    
    try:
        analyzer = YCGrowthAnalyzer(api_key=args.api_key)
        
        companies = analyzer.load_companies(args.companies)
        if not companies:
            logger.error("No companies loaded. Exiting.")
            return
        
        results = await analyzer.analyze_all_companies(companies, args.years)
        
        analyzer.save_results(results, args.output)
        
        summary = analyzer.generate_summary_report(results)
        with open(args.summary, 'w') as f:
            f.write(summary)
        
        print(f"\nAnalysis complete!")
        print(f"Results saved to: {args.output}")
        print(f"Summary saved to: {args.summary}")
        print(f"\nQuick Summary:")
        print(f"- Companies analyzed: {len(companies)}")
        print(f"- Years: {', '.join(map(str, args.years))}")
        print(f"- Successful analyses: {len([r for r in results if r.get('status') == 'completed'])}")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())