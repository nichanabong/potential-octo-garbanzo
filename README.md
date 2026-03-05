## Winnipeg Career Email Notifier

`notify_winnipeg_jobs.py` scans public job listings, filters jobs in **Winnipeg**, applies your company/title filters, and emails matching roles.

### Features
- Dynamic company filter (comma-separated input).
- Dynamic title filter (comma-separated input).
- Configurable SMTP email delivery.
- Optional JSON config file for automation (cron-friendly).

### Quick start
```bash
python3 notify_winnipeg_jobs.py \
  --companies "Shopify,SkipTheDishes" \
  --titles "Software Engineer,Data Analyst" \
  --smtp-host smtp.gmail.com --smtp-port 587 \
  --smtp-user you@example.com --smtp-password app-password \
  --from-email you@example.com --to-email you@example.com
```

### Using a config file
1. Copy `config.example.json` to `config.json` and fill in your values.
2. Run:
```bash
python3 notify_winnipeg_jobs.py --config config.json
```

### Automation (optional)
Run every morning using cron:
```bash
0 8 * * * /usr/bin/python3 /path/to/notify_winnipeg_jobs.py --config /path/to/config.json
```
