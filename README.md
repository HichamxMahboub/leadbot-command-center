# LeadScraper AI Web App

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=github.com/HichamxMahboub/leadbot-command-center)

A FastAPI + Playwright web app that scrapes Google Maps results and streams live logs to a modern Tailwind UI.


## Deploy (Railway + Vercel)

### Backend on Railway

This repo includes a `Dockerfile` built on Playwright’s Python image. Railway will run it automatically.

1. Create a new Railway project and link this repo.
2. Set the **Start Command** to use `start.sh` (default `CMD` already does this).
3. Deploy and copy the backend URL, e.g. `https://leadbot-backend.up.railway.app`.

### Frontend on Vercel

1. Deploy the same repo to Vercel.
2. Add a small override in Vercel’s project settings by injecting a global variable:

```html
<script>
	window.API_BASE = "https://leadbot-backend.up.railway.app";
</script>
```

Place it near the top of `index.html` (before the main script) or use Vercel’s HTML injection feature.

The frontend will route WebSocket + download requests to Railway automatically.

## Notes

- The scraper runs in headless mode for server usage.
- Results are saved to `results/latest_results.json` and `results/latest_results.xlsx`.
- Click **Download Results (Excel)** after a run to fetch the spreadsheet.
