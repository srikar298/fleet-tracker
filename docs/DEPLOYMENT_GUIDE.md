# Deployment & Maintenance Guide

## Pre-Deployment Checklist
1.  **Environment Variables**: Ensure `TELEGRAM_TOKEN` and `GOOGLE_CREDENTIALS` (JSON path) are set in `.env`.
2.  **Service Accounts**: Verify the Google Service Account has "Editor" access to your Google Sheet and Drive folder.
3.  **Sanity Check**: Run the following to ensure the codebase is clean:
    ```bash
    ruff check .
    mypy .
    ```

## Local Execution
To start the bot in development/production:
```bash
python src/main.py
```

## System Maintenance
### 1. Sheet Initialization
If you need to reset headers or add new sheets:
```bash
python src/init_sheets.py
```

### 2. Beautification
To re-apply professional formatting to the Google Sheets:
```bash
python src/beautify_sheets.py
```

### 3. Daily Summaries
To generate the daily fleet performance summary:
```bash
python src/generate_daily_summary.py
```

## Maintenance Workflow
1.  **Logs**: Monitor `bot.log` for any API errors.
2.  **Backups**: Periodically download the "Trips" sheet as a CSV for offline backup.
3.  **Flagged Reviews**: Check the `Flagged_Review` folder on Google Drive for any trips with odometer discrepancies.
