#!/usr/bin/env python3
"""
Test script for YC Company Valuation Analyzer - Single Company Test

This script tests the valuation analysis on just one company for quick testing.
"""

import asyncio
import sys
from yc_growth_analyzer import YCGrowthAnalyzer

async def test_single_company():
    """Test the analyzer with a single company."""
    
    # Test with Stripe - a well-known company with lots of public funding data
    test_company = {
        "name": "Stripe",
        "batch": "S09",
        "description": "Online payment processing platform for internet businesses",
        "website": "https://stripe.com",
        "founded": 2010,
        "founders": ["Patrick Collison", "John Collison"],
        "category": "Fintech"
    }
    
    # Test with just 3 years for faster testing
    test_years = [2021, 2022, 2023]
    
    print("Testing YC Valuation Analyzer with Stripe...")
    print(f"Years to analyze: {test_years}")
    print("-" * 50)
    
    try:
        # Initialize analyzer (will get API key from .env)
        analyzer = YCGrowthAnalyzer()
        
        # Analyze single company
        print("Starting analysis...")
        valuations = await analyzer.analyze_company_valuations(test_company, test_years)
        
        print(f"\nResults for {test_company['name']}:")
        print("-" * 30)
        
        for valuation in valuations:
            print(f"Year: {valuation['year']}")
            print(f"Valuation: {valuation['valuation']}")
            print(f"Source: {valuation['source']}")
            print(f"Notes: {valuation['notes']}")
            print()
        
        # Save test results to CSV
        analyzer.save_results_csv(valuations, 'test_single_result.csv')
        print("Test results saved to: test_single_result.csv")
        
        # Generate summary
        summary = analyzer.generate_summary_report(valuations, test_years)
        with open('test_single_summary.txt', 'w') as f:
            f.write(summary)
        print("Test summary saved to: test_single_summary.txt")
        
        print("\n✅ Test completed successfully!")
        
    except ValueError as e:
        if "API key" in str(e):
            print("❌ Error: Please set up your .env file with ANTHROPIC_API_KEY")
            print("Copy .env.example to .env and add your API key")
        else:
            print(f"❌ Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_single_company())