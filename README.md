# YC Company Growth Analyzer

A Python tool that analyzes the growth trajectory of Y Combinator companies using Claude AI to research and provide insights on company metrics over multiple years.

## Features

- Load company data from JSON files
- Use Claude AI to research company growth metrics
- Analyze multiple years of data
- Generate structured analysis reports
- Export results to JSON and summary reports

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

### Basic Usage (with command line API key)

```bash
python yc_growth_analyzer.py --companies sample_companies.json --api-key YOUR_API_KEY
```

### Advanced Usage

```bash
python yc_growth_analyzer.py \
    --companies sample_companies.json \
    --years 2020 2021 2022 2023 2024 \
    --output custom_results.json \
    --summary custom_summary.txt
```

### Command Line Arguments

- `--companies`: Path to JSON file containing company data (required)
- `--api-key`: Your Anthropic API key (optional if set in .env)
- `--years`: Years to analyze (default: 2020-2024)
- `--output`: Output file for detailed results (default: yc_growth_analysis.json)
- `--summary`: Output file for summary report (default: yc_growth_summary.txt)

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

1. **Detailed JSON Results**: Complete analysis data including Claude's research findings
2. **Summary Report**: High-level overview of the analysis process and results

### Sample Analysis Output

For each company, Claude will provide:
- Revenue/GMV data (when available)
- Employee count growth
- User/customer metrics
- Major milestones and funding rounds
- Market valuation information
- Growth drivers and key achievements

## Environment Variables

You can also set your API key as an environment variable:

```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

## Rate Limiting

The tool includes built-in rate limiting (1-second delays between API calls) to respect Anthropic's API limits.

## Error Handling

- Companies that fail analysis are marked with error status
- Detailed error logs are provided
- The tool continues processing remaining companies even if some fail

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

## Contributing

Feel free to submit issues and enhancement requests!