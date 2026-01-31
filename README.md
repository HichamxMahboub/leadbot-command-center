# LeadScraper AI Web App

A FastAPI + Playwright web app that scrapes Google Maps results and streams live logs to a modern Tailwind UI.

## Quick Start

```bash
/home/homemadesavior/Dev/LeadScraper/.venv/bin/python -m pip install -r requirements.txt
/home/homemadesavior/Dev/LeadScraper/.venv/bin/python -m playwright install chromium
/home/homemadesavior/Dev/LeadScraper/.venv/bin/python -m uvicorn app:app --reload --port 8000
```

Open `http://localhost:8000` in your browser.

## Notes

- The scraper runs in headless mode for server usage.
- Results are saved to `results/latest_results.json` and `results/latest_results.xlsx`.
- Click **Download Results (Excel)** after a run to fetch the spreadsheet.
