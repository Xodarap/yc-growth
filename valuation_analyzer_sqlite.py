#!/usr/bin/env python3

import os
import csv
import sqlite3
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

class ValuationAnalyzer:
    def __init__(self, db_path='valuations.db'):
        self.client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.current_year = datetime.now().year
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """Initialize SQLite database and create tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create valuations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS valuations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                year INTEGER NOT NULL,
                valuation TEXT NOT NULL,
                source TEXT NOT NULL,
                notes TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company, year)
            )
        ''')
        
        # Create companies table for tracking progress
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT UNIQUE NOT NULL,
                founded_year INTEGER NOT NULL,
                website TEXT,
                status TEXT DEFAULT 'pending',
                processed_at TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"📁 Database initialized: {self.db_path}")
    
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
    
    def load_companies_to_db(self, companies):
        """Load companies into database for tracking."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for company in companies:
            cursor.execute('''
                INSERT OR REPLACE INTO companies (company, founded_year, website, status)
                VALUES (?, ?, ?, 'pending')
            ''', (company['name'], company['founded_year'], company['website']))
        
        conn.commit()
        conn.close()
        print(f"📋 Loaded {len(companies)} companies into database")
    
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
    
    def save_valuations_to_db(self, company_name, valuations):
        """Save valuations to database immediately."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        for val_data in valuations:
            cursor.execute('''
                INSERT OR REPLACE INTO valuations (company, year, valuation, source, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (company_name, val_data['year'], val_data['valuation'], 
                  val_data['source'], val_data['notes']))
            saved_count += 1
        
        # Mark company as completed
        cursor.execute('''
            UPDATE companies 
            SET status = 'completed', processed_at = CURRENT_TIMESTAMP
            WHERE company = ?
        ''', (company_name,))
        
        conn.commit()
        conn.close()
        return saved_count
    
    async def analyze_company(self, company):
        """Analyze a single company and save results to database immediately."""
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
                # Save to database immediately
                saved_count = self.save_valuations_to_db(company['name'], submitted_data['valuations'])
                print(f"   ✅ Found {len(submitted_data['valuations'])} valuations, saved {saved_count} to database")
                return saved_count
            else:
                print(f"   ❌ No data submitted for {company['name']}")
                # Mark as failed in database
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE companies 
                    SET status = 'failed', processed_at = CURRENT_TIMESTAMP
                    WHERE company = ?
                ''', (company['name'],))
                conn.commit()
                conn.close()
                return 0
                
        except Exception as e:
            print(f"   ❌ Error analyzing {company['name']}: {str(e)}")
            # Mark as error in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE companies 
                SET status = 'error', processed_at = CURRENT_TIMESTAMP
                WHERE company = ?
            ''', (company['name'],))
            conn.commit()
            conn.close()
            return 0
    
    def export_to_csv(self, csv_filename='valuations_export.csv'):
        """Export all valuations from database to CSV."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT company, year, valuation, source, notes 
            FROM valuations 
            ORDER BY company, year
        ''')
        
        rows = cursor.fetchall()
        
        with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['company', 'year', 'valuation', 'source', 'notes']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for row in rows:
                writer.writerow({
                    'company': row[0],
                    'year': row[1], 
                    'valuation': row[2],
                    'source': row[3],
                    'notes': row[4]
                })
        
        conn.close()
        print(f"📄 Exported {len(rows)} valuations to {csv_filename}")
        return len(rows)
    
    def show_progress(self):
        """Show current progress from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT status, COUNT(*) FROM companies GROUP BY status')
        status_counts = dict(cursor.fetchall())
        
        cursor.execute('SELECT COUNT(*) FROM valuations')
        total_valuations = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"\n📊 Progress Summary:")
        print(f"   Companies completed: {status_counts.get('completed', 0)}")
        print(f"   Companies pending: {status_counts.get('pending', 0)}")
        print(f"   Companies failed/error: {status_counts.get('failed', 0) + status_counts.get('error', 0)}")
        print(f"   Total valuations saved: {total_valuations}")
    
    async def analyze_all_companies(self, input_file):
        """Analyze all companies and stream results to database."""
        companies = self.read_companies_csv(input_file)
        print(f"📊 Loaded {len(companies)} companies from {input_file}")
        
        # Load companies into database for tracking
        self.load_companies_to_db(companies)
        
        total_valuations = 0
        
        for i, company in enumerate(companies, 1):
            print(f"\n📈 Processing {i}/{len(companies)}: {company['name']}")
            
            valuations_found = await self.analyze_company(company)
            total_valuations += valuations_found
            
            # Show progress after each company
            self.show_progress()
            
            # Rate limiting
            if i < len(companies):
                print("   ⏳ Waiting 3 seconds...")
                await asyncio.sleep(3)
        
        print(f"\n🎉 Analysis complete!")
        print(f"   Companies processed: {len(companies)}")
        print(f"   Total valuations found: {total_valuations}")
        
        # Export final results to CSV
        exported_count = self.export_to_csv()
        print(f"   Final export: {exported_count} records")

async def main():
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("❌ Error: Please set ANTHROPIC_API_KEY in .env file")
        return
    
    analyzer = ValuationAnalyzer()
    await analyzer.analyze_all_companies('companies_input.csv')

if __name__ == "__main__":
    asyncio.run(main())