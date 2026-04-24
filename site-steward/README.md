# site-steward

Local-first homepage reviewer for ministry and portfolio sites.

## Current MVP

The current MVP reviews a single homepage URL and produces:

- `report.md`
- `report.json`
- `issues.csv`
- optional screenshots when Playwright is available

## Run

From the repo root:

```bash
python3 site-steward/site-steward review --url http://localhost:4000 --profile ministry
```

Or from the tool directory:

```bash
python3 -m site_steward.cli review --url https://jnskm.com --profile ministry
```

## Notes

- The browser screenshot module is optional in this first pass.
- If Playwright is not installed, the review still runs and records that screenshots were skipped.

