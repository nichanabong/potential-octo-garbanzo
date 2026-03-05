#!/usr/bin/env python3
"""Notify via email when Winnipeg jobs match company/title filters.

Example:
python notify_winnipeg_jobs.py \
  --companies "Shopify,SkipTheDishes" \
  --titles "Software Engineer,Data Analyst" \
  --smtp-host smtp.gmail.com --smtp-port 587 \
  --smtp-user you@example.com --smtp-password app-password \
  --from-email you@example.com --to-email you@example.com
"""

from __future__ import annotations

import argparse
import json
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.request import urlopen

API_URL = "https://www.arbeitnow.com/api/job-board-api"


@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    tags: list[str]


def parse_csv_values(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def normalized_contains_any(value: str, terms: Iterable[str]) -> bool:
    value = value.lower()
    terms = [t.lower() for t in terms]
    if not terms:
        return True
    return any(term in value for term in terms)


def fetch_jobs(max_pages: int) -> list[Job]:
    jobs: list[Job] = []

    for page in range(1, max_pages + 1):
        page_url = f"{API_URL}?page={page}"
        try:
            with urlopen(page_url, timeout=20) as response:  # nosec B310
                payload = json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            print(f"[WARN] Failed to fetch page {page}: {exc}")
            break

        entries = payload.get("data", [])
        if not entries:
            break

        for entry in entries:
            jobs.append(
                Job(
                    title=entry.get("title", "Unknown title"),
                    company=entry.get("company_name", "Unknown company"),
                    location=entry.get("location", "Unknown location"),
                    url=entry.get("url", ""),
                    tags=entry.get("tags", []),
                )
            )

    return jobs


def filter_jobs(jobs: Iterable[Job], companies: list[str], titles: list[str]) -> list[Job]:
    filtered: list[Job] = []
    for job in jobs:
        location_text = f"{job.location} {' '.join(job.tags)}"
        if "winnipeg" not in location_text.lower():
            continue
        if not normalized_contains_any(job.company, companies):
            continue
        if not normalized_contains_any(job.title, titles):
            continue
        filtered.append(job)
    return filtered


def build_email_body(matches: list[Job], companies: list[str], titles: list[str]) -> str:
    company_txt = ", ".join(companies) if companies else "Any company"
    title_txt = ", ".join(titles) if titles else "Any title"

    lines = [
        "Winnipeg career alert",
        "",
        f"Company filters: {company_txt}",
        f"Title filters: {title_txt}",
        f"Matches found: {len(matches)}",
        "",
    ]

    for idx, job in enumerate(matches, start=1):
        lines.extend(
            [
                f"{idx}. {job.title}",
                f"   Company: {job.company}",
                f"   Location: {job.location}",
                f"   Link: {job.url or 'N/A'}",
                "",
            ]
        )

    return "\n".join(lines)


def send_email(
    host: str,
    port: int,
    username: str,
    password: str,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls(context=context)
        smtp.login(username, password)
        smtp.send_message(msg)


def load_config(path: str | None) -> dict:
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    return json.loads(config_path.read_text(encoding="utf-8"))


def get_value(cli_value, cfg: dict, key: str):
    return cli_value if cli_value is not None else cfg.get(key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Optional JSON config file path")
    parser.add_argument("--companies", help="Comma-separated company names")
    parser.add_argument("--titles", help="Comma-separated job titles")
    parser.add_argument("--max-pages", type=int, default=5, help="Max API pages to scan")
    parser.add_argument("--notify-on-empty", action="store_true", help="Send email even with zero matches")

    parser.add_argument("--smtp-host")
    parser.add_argument("--smtp-port", type=int)
    parser.add_argument("--smtp-user")
    parser.add_argument("--smtp-password")
    parser.add_argument("--from-email")
    parser.add_argument("--to-email")
    parser.add_argument("--subject", default="Winnipeg career alert")

    args = parser.parse_args()
    cfg = load_config(args.config)

    companies_raw = get_value(args.companies, cfg, "companies")
    titles_raw = get_value(args.titles, cfg, "titles")

    if not companies_raw:
        companies_raw = input("Enter company names (comma-separated, blank for any): ").strip()
    if not titles_raw:
        titles_raw = input("Enter job titles (comma-separated, blank for any): ").strip()

    companies = parse_csv_values(companies_raw)
    titles = parse_csv_values(titles_raw)

    jobs = fetch_jobs(max_pages=get_value(args.max_pages, cfg, "max_pages") or 5)
    matches = filter_jobs(jobs, companies, titles)

    if not matches and not args.notify_on_empty:
        print("No matching Winnipeg jobs found. Skipping email.")
        return 0

    smtp_host = get_value(args.smtp_host, cfg, "smtp_host")
    smtp_port = int(get_value(args.smtp_port, cfg, "smtp_port") or 0)
    smtp_user = get_value(args.smtp_user, cfg, "smtp_user")
    smtp_password = get_value(args.smtp_password, cfg, "smtp_password")
    from_email = get_value(args.from_email, cfg, "from_email")
    to_email = get_value(args.to_email, cfg, "to_email")
    subject = get_value(args.subject, cfg, "subject") or "Winnipeg career alert"

    required = {
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_user": smtp_user,
        "smtp_password": smtp_password,
        "from_email": from_email,
        "to_email": to_email,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ValueError(f"Missing SMTP/email fields: {', '.join(missing)}")

    body = build_email_body(matches, companies, titles)
    send_email(
        host=smtp_host,
        port=smtp_port,
        username=smtp_user,
        password=smtp_password,
        from_email=from_email,
        to_email=to_email,
        subject=subject,
        body=body,
    )
    print(f"Email sent. Matching jobs: {len(matches)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
