# Disneyland Paris Pricing Dashboard

A Streamlit-based dashboard for mapping Disneyland Paris dynamic pricing to GlobalTix fixed pricing tiers.

## Overview

This application fetches ticket pricing data from the Disneyland Paris API and maps it to GlobalTix's pricing tiers (Low Peak, Shoulder, Peak, Super Peak, Mega Peak). It provides visualizations, analytics, and export capabilities to help GlobalTix set competitive pricing.

## Features

- Fetch pricing data for all 5 Disneyland Paris ticket types
- Automatic price-to-tier mapping using percentile-based algorithm
- Interactive visualizations (heatmaps, timelines, distributions)
- Monthly pricing recommendations
- Price alerts for significant changes
- Historical data tracking
- Export to CSV and Excel
- Product comparison across ticket types

## Quick Start

### Installation

```bash
make install
```

This will install all required dependencies in the `.venv` virtual environment.

### Running the Dashboard

```bash
make run
```

This will start the Streamlit dashboard at http://localhost:8501

### Running Tests

```bash
make test
```

### Fetching Prices via CLI

```bash
make fetch-prices
```

## Deployment

### Streamlit Community Cloud (Recommended)

1. Push this repository (including `requirements.txt` and `streamlit_app.py`) to GitHub.
2. Sign in to [Streamlit Community Cloud](https://streamlit.io/cloud) and choose **New app**.
3. Select the repository, branch, and set the app entry point to `streamlit_app.py`.
4. Keep the default command (`pip install -r requirements.txt`) unless you maintain a different dependency file.
5. Click **Deploy** to build and launch the app; Streamlit will display a public URL when ready.

#### Notes
- The `data/` folder is short-lived in Streamlit Cloud; containers reset it on restart, so download exports you need to keep.
- Add a `runtime.txt` (e.g. `python-3.11`) if you must target a specific Python version.
- Configure any future secrets via Streamlit Cloud's **Secrets** manager.

## Project Structure

```
.
├── src/
│   ├── api/           # Disney API client
│   ├── models/        # Tier mapping logic
│   ├── storage/       # Historical data storage
│   ├── utils/         # Logger and utilities
│   └── app.py         # Streamlit dashboard
├── docs/              # Documentation
├── tests/             # Unit tests
├── data/              # Historical data storage
├── Makefile           # Build automation
└── requirements.txt   # Python dependencies
```

## Usage

### Dashboard Interface

1. **Select Products**: Choose which ticket types to analyze (1-day, 2-day, etc.)
2. **Set Date Range**: Select start and end dates for pricing analysis
3. **Fetch Data**: Click "Fetch New Data" to retrieve latest prices from Disney API
4. **View Analysis**:
   - Calendar heatmaps showing price variations
   - Price timelines with tier color coding
   - Tier distribution charts
   - Monthly recommendations
   - Price alerts
5. **Compare Products**: View side-by-side comparison across ticket types
6. **Export Data**: Download pricing data in CSV or Excel format

### Price Tiers

The system uses 5 GlobalTix pricing tiers:

- **Low Peak**: 0-20th percentile (lowest prices)
- **Shoulder (Normal)**: 20-40th percentile
- **Peak**: 40-60th percentile
- **Super Peak**: 60-80th percentile
- **Mega Peak**: 80-100th percentile (highest prices)

## Available Ticket Products

| Product Type | Description |
|-------------|-------------|
| 1-day-1-park | Single day, single park access |
| 1-day-2-parks | Single day, both parks access |
| 2-day-2-parks | Two consecutive days, both parks |
| 3-day-2-parks | Three consecutive days, both parks |
| 4-day-2-parks | Four consecutive days, both parks |

## Documentation

Comprehensive documentation is available in the `docs/` folder:

- **[Pricing Strategy](docs/pricing_strategy.md)**: Detailed explanation of the tier mapping methodology
- **[Architecture](docs/architecture.md)**: System design and component overview
- **[API Reference](docs/api_reference.md)**: Disney API documentation and usage examples

## Development

### Running Tests

```bash
make test
```

All 25 tests should pass:
- 11 tests for API client
- 14 tests for tier mapper

### Cleaning Build Artifacts

```bash
make clean
```

### Project Guidelines

- Use logger at appropriate levels (no print statements)
- Keep code simple and concise
- Add all tests to `tests/` folder
- Use `.venv/` for all Python commands

## Technologies

- **Python 3.9+**
- **Streamlit**: Web dashboard framework
- **Pandas**: Data manipulation and analysis
- **Plotly**: Interactive visualizations
- **Requests**: HTTP client for API calls
- **pytest**: Testing framework

## API Details

The application uses the Disneyland Paris pricing calendar API:

```
POST https://api.disneylandparis.com/prices-calendar/api/v2/prices/ticket-price-calendar
```

No authentication required. See [API Reference](docs/api_reference.md) for complete documentation.

## Data Storage

Historical pricing data is stored in the `data/` folder:

- Raw API responses: `{product-type}_{timestamp}.json`
- Mapped tier data: `{product-type}_mapped_{timestamp}.csv`

Data is automatically saved when fetching new prices.

## Troubleshooting

### Import Errors

Make sure you're using the virtual environment:

```bash
source .venv/bin/activate
```

### API Connection Issues

The Disney API may occasionally timeout or return errors. The application includes automatic retry logic with exponential backoff.

### Missing Data

If the dashboard shows no data, click "Fetch New Data" to retrieve pricing information from the API.

## Future Enhancements

Potential improvements:

- Machine learning for price prediction
- Automated scheduled data fetching
- Database backend for production use
- Multi-user authentication
- API endpoint for programmatic access
- Competitor pricing comparison

## Support

For issues or questions:
- Check the documentation in `docs/`
- Review test files in `tests/` for usage examples
- Examine the code in `src/` for implementation details

## License

Internal GlobalTix tool for Disneyland Paris pricing analysis.
