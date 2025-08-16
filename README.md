# YC Company Valuation Analyzer

A Python tool that analyzes the valuation history of Y Combinator companies using Claude AI to search the internet for funding rounds, IPO data, and market valuations.

## Features

- Load company data from JSON files
- Use Claude AI to search the internet for company valuations
- Analyze multiple years of valuation data
- Track source websites for each valuation
- Export results to CSV format with clean, structured data

## Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd yc-growth
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Get your Anthropic API key from [https://console.anthropic.com/](https://console.anthropic.com/)

4. Set up your API key:
```bash
cp .env.example .env
# Edit .env and add your API key
```

## Usage

### Basic Usage (with .env file)

```bash
python yc_growth_analyzer.py --companies sample_companies.json
```

This will generate:
- `yc_valuations.csv` - CSV file with company valuations by year
- `yc_valuation_summary.txt` - Summary report

### Basic Usage (with command line API key)

```bash
python yc_growth_analyzer.py --companies sample_companies.json --api-key YOUR_API_KEY
```

### Advanced Usage

```bash
python yc_growth_analyzer.py \
    --companies sample_companies.json \
    --years 2020 2021 2022 2023 2024 \
    --output custom_valuations.csv \
    --summary custom_summary.txt
```

### Command Line Arguments

- `--companies`: Path to JSON file containing company data (required)
- `--api-key`: Your Anthropic API key (optional if set in .env)
- `--years`: Years to analyze (default: 2020-2024)
- `--output`: Output CSV file for results (default: yc_valuations.csv)
- `--summary`: Output file for summary report (default: yc_valuation_summary.txt)

## Company Data Format

The input JSON file should contain an array of company objects with the following structure:

```json
[
  {
    "name": "Company Name",
    "batch": "S09",
    "description": "Company description",
    "website": "https://company.com",
    "founded": 2010,
    "founders": ["Founder 1", "Founder 2"],
    "category": "Category"
  }
]
```

## Example Output

The tool generates two types of output:

1. **CSV Results**: Clean, structured data with columns:
   - `company`: Company name
   - `year`: Year of valuation
   - `valuation`: Dollar amount (e.g., "$1.2B", "$500M")
   - `source`: Website URL where the valuation was found
   - `notes`: Context about the valuation (funding round, IPO, etc.)

2. **Summary Report**: High-level overview of the analysis results

### Sample CSV Output

```csv
company,year,valuation,source,notes
Stripe,2020,$36B,https://techcrunch.com/...,Series G funding round
Stripe,2021,$95B,https://bloomberg.com/...,Series H funding round
Airbnb,2020,$18B,https://sec.gov/...,IPO filing
Airbnb,2021,$132B,https://finance.yahoo.com/...,Market cap after IPO
```

## Environment Variables

You can also set your API key as an environment variable:

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

## Internet Search Capability

The tool is specifically designed to prompt Claude to search the internet for current valuation data from:
- News articles about funding rounds (TechCrunch, Bloomberg, Reuters)
- SEC filings and regulatory documents
- Company press releases
- Investment databases (Crunchbase, PitchBook)
- Financial news sites

## Rate Limiting

The tool includes built-in rate limiting (2-second delays between API calls) to respect Anthropic's API limits.

## Error Handling

- Companies with API errors are marked with "Error" valuation status
- Missing valuation data is marked as "Not found"
- Detailed error logs are provided
- The tool continues processing remaining companies even if some fail
- All requested years are included in the output, even if no data is found

## Sample Companies

The repository includes `sample_companies.json` with 10 notable YC companies:
- Stripe
- Airbnb  
- DoorDash
- Coinbase
- Instacart
- Twitch
- Reddit
- GitLab
- Zapier
- OpenSea

## Testing

For quick testing with a single company:

```bash
python test_single_company.py
```

This will analyze Stripe for years 2021-2023 and generate test output files.

## Contributing

Feel free to submit issues and enhancement requests!