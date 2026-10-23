import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import time
import hashlib
import logging
from typing import List, Dict, Any, Optional
import pandas as pd
from jobspy import scrape_jobs
from rich.console import Console

from config import SearchConfig
from models import JobPost

console = Console(highlight=False)
logger = logging.getLogger("ai_job_searcher.scraper")

def generate_job_id(site: str, title: str, company: str, job_url: str) -> str:
    """Generate a deterministic unique ID for deduplication."""
    raw = f"{site}_{title}_{company}_{job_url}".lower().strip()
    return hashlib.md5(raw.encode('utf-8')).hexdigest()[:12]

def clean_text(text: Any) -> str:
    if text is None or pd.isna(text):
        return ""
    return str(text).strip()

def scrape_all_jobs(search_cfg: SearchConfig) -> List[JobPost]:
    """
    Scrapes job portals based on SearchConfig (keywords, locations, sites, hours_old).
    Deduplicates results and returns a list of JobPost objects.
    """
    all_jobs: Dict[str, JobPost] = {}
    sites = [s.lower() for s in search_cfg.sites]

    console.print(f"[bold cyan]🔍 Starting job scrape for {len(search_cfg.keywords)} keywords across {len(sites)} platforms...[/bold cyan]")
    console.print(f"[dim]Filter: Posted within last {search_cfg.hours_old} hours[/dim]\n")

    for keyword in search_cfg.keywords:
        for location in search_cfg.locations:
            console.print(f"👉 Searching for '[bold yellow]{keyword}[/bold yellow]' in '[bold green]{location}[/bold green]'...")
            
            try:
                # Run scrape_jobs with hours_old
                df: pd.DataFrame = scrape_jobs(
                    site_name=sites,
                    search_term=keyword,
                    location=location,
                    results_wanted=search_cfg.results_per_query,
                    hours_old=search_cfg.hours_old,
                    country_indeed=search_cfg.country,
                    is_remote=search_cfg.is_remote if search_cfg.is_remote is not None else False,
                    fetch_description=True,
                    linkedin_fetch_description=True,
                    verbose=0
                )

                if df is None or df.empty:
                    console.print(f"   [yellow]No new jobs found for {keyword} in {location}[/yellow]")
                    continue

                count_added = 0
                for _, row in df.iterrows():
                    title = clean_text(row.get("title"))
                    company = clean_text(row.get("company"))
                    job_url = clean_text(row.get("job_url") or row.get("job_url_direct"))
                    site = clean_text(row.get("site")) or "unknown"
                    
                    if not title or not job_url:
                        continue

                    # Deduplication key based on title + company
                    dedup_key = f"{title.lower()}::{company.lower()}"
                    if dedup_key in all_jobs:
                        continue

                    job_id = generate_job_id(site, title, company, job_url)
                    loc = clean_text(row.get("location")) or location
                    date_posted = clean_text(row.get("date_posted"))
                    is_remote = bool(row.get("is_remote")) if "is_remote" in row else False
                    description = clean_text(row.get("description"))

                    # Format salary if available
                    salary = None
                    min_amt = row.get("min_amount")
                    max_amt = row.get("max_amount")
                    curr = clean_text(row.get("currency")) or "$"
                    interval = clean_text(row.get("interval")) or "yr"
                    if min_amt and not pd.isna(min_amt):
                        if max_amt and not pd.isna(max_amt) and max_amt != min_amt:
                            salary = f"{curr}{min_amt:,.0f} - {curr}{max_amt:,.0f}/{interval}"
                        else:
                            salary = f"{curr}{min_amt:,.0f}/{interval}"

                    job_post = JobPost(
                        id=job_id,
                        title=title,
                        company=company,
                        location=loc,
                        site=site,
                        job_url=job_url,
                        date_posted=date_posted,
                        is_remote=is_remote,
                        description=description,
                        salary=salary
                    )

                    all_jobs[dedup_key] = job_post
                    count_added += 1

                console.print(f"   [green]✓ Found {len(df)} postings ({count_added} unique added)[/green]")

            except Exception as e:
                console.print(f"   [red]⚠️ Error scraping {keyword} in {location}: {e}[/red]")
                logger.warning(f"Error during scrape for {keyword}: {e}")

            time.sleep(1.2)

    job_list = list(all_jobs.values())
    console.print(f"\n[bold green]✨ Scraping complete! Total unique jobs collected: {len(job_list)}[/bold green]\n")
    return job_list
