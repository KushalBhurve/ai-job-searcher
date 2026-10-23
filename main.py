import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import os
import argparse
import webbrowser
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.panel import Panel

from config import load_config
from scraper import scrape_all_jobs
from matcher import evaluate_all_jobs, evaluate_single_job
from reporter import print_terminal_summary, export_reports
from notifier import dispatch_all_notifications
from models import JobPost, MatchAnalysis
import db

console = Console(highlight=False)

def is_senior_job(title: str, senior_keywords: List[str]) -> bool:
    t = title.lower()
    for kw in senior_keywords:
        if kw in t:
            return True
    return False

def calculate_relevance_score(job: JobPost, target_keywords: List[str], senior_keywords: List[str]) -> int:
    t = job.title.lower()
    score = 0

    # 1. High boost for target keywords
    for kw in target_keywords:
        if kw.lower() in t:
            score += 25

    # 2. High boost for Kushal's core technical profile
    core_tech = [
        "genai", "generative ai", "ai engineer", "ai developer",
        "langgraph", "langchain", "rag", "vertex ai", "gcp",
        "python", "fastapi", "node", "spring boot", "sde 1", "sde-1",
        "associate", "junior"
    ]
    for tech in core_tech:
        if tech in t:
            score += 15

    # 3. Penalty for senior/lead titles when candidate has 1.5 years experience
    for sk in senior_keywords:
        if sk in t:
            score -= 50

    return score

def run_job_search(open_browser: bool = True, limit: Optional[int] = None):
    console.print(Panel.fit(
        "[bold cyan]⚡ AI Job Searcher - 24H Radar[/bold cyan]\n"
        "[dim]Scraping LinkedIn, Indeed, Glassdoor & Matching with local LLM (Ollama)[/dim]",
        border_style="cyan"
    ))

    # 1. Load config
    cfg = load_config()
    console.print(f"[bold]👤 Candidate Profile:[/bold] {cfg.candidate_profile.full_name} ({cfg.candidate_profile.title})")
    console.print(f"[bold]🎓 Background:[/bold] {cfg.candidate_profile.education} | {cfg.candidate_profile.years_of_experience} yrs exp")
    console.print(f"[bold]🎯 Target Keywords:[/bold] {', '.join(cfg.search.keywords[:5])}...")
    console.print(f"[bold]📍 Target Locations:[/bold] {', '.join(cfg.search.locations)}")
    console.print(f"[bold]🤖 AI Model:[/bold] {cfg.ai_matcher.provider} ({cfg.ai_matcher.ollama.model if cfg.ai_matcher.provider == 'ollama' else cfg.ai_matcher.free_api.model})\n")

    # 2. Scrape Jobs
    jobs = scrape_all_jobs(cfg.search)
    if not jobs:
        console.print("[bold yellow]⚠️ No jobs found matching search criteria in the last 24 hours.[/bold yellow]")
        console.print("[dim]Tip: You can increase `hours_old` to 48 or 72 in profile.yaml, or expand keywords.[/dim]")
        return

    total_scraped = len(jobs)

    # 3. Apply Experience & Seniority Filtering
    senior_kws = cfg.experience_filter.senior_keywords
    senior_count = sum(1 for j in jobs if is_senior_job(j.title, senior_kws))
    
    # Sort all jobs by relevance score
    jobs.sort(key=lambda j: calculate_relevance_score(j, cfg.search.keywords, senior_kws), reverse=True)

    console.print(f"[cyan]📊 Scraped {total_scraped} total jobs. Identified {senior_count} senior/lead postings (deprioritized).[/cyan]")

    # 4. Determine AI Evaluation Limit
    effective_limit = limit if limit is not None else cfg.execution.evaluate_limit
    
    if effective_limit and effective_limit > 0 and total_scraped > effective_limit:
        console.print(f"[dim]⚡ Running in-depth LLM evaluations on top {effective_limit} most relevant postings (all {total_scraped} will be saved in dashboard/CSV)...[/dim]")
        jobs_to_evaluate = jobs[:effective_limit]
        remaining_jobs = jobs[effective_limit:]
    else:
        console.print(f"[dim]⚡ Running in-depth LLM evaluations on all {total_scraped} postings...[/dim]")
        jobs_to_evaluate = jobs
        remaining_jobs = []

    # 5. In-depth AI Evaluation using Ollama
    evaluated_jobs = evaluate_all_jobs(jobs_to_evaluate, cfg.candidate_profile, cfg.ai_matcher)

    # 6. For remaining jobs, assign baseline data so ALL 200+ jobs are kept in reports
    for rj in remaining_jobs:
        if not rj.match_analysis:
            rel = calculate_relevance_score(rj, cfg.search.keywords, senior_kws)
            is_senior = is_senior_job(rj.title, senior_kws)
            if is_senior:
                quick_score = 35
                reason = "Senior/Lead role requiring more experience than current 1.5 yrs."
            else:
                quick_score = min(70, max(45, 50 + rel // 2))
                reason = f"Scraped listing matching {rj.title} in {rj.location}."

            rj.match_analysis = MatchAnalysis(
                match_score=quick_score,
                decision="UNASSESSED",
                summary_reason=reason,
                recommended_action="Review posting"
            )

    all_reporting_jobs = evaluated_jobs + remaining_jobs
    all_reporting_jobs.sort(key=lambda j: j.match_analysis.match_score if j.match_analysis else 0, reverse=True)

    # 7. Filter high matches for notification
    min_score = cfg.ai_matcher.min_match_score
    recommended_jobs = [j for j in all_reporting_jobs if j.match_analysis and j.match_analysis.match_score >= min_score]
    console.print(f"\n[bold green]🎯 {len(recommended_jobs)} of {len(all_reporting_jobs)} jobs meet your match threshold (≥{min_score}%)[/bold green]\n")

    # 8. Display Console Table
    print_terminal_summary(all_reporting_jobs)

    # 9. Persist to SQLite Database for Live Web Dashboard
    db.upsert_jobs(all_reporting_jobs)

    # 10. Export Reports (now includes 100% of scraped jobs)
    paths = export_reports(all_reporting_jobs)

    # 10. Notifications
    dispatch_all_notifications(recommended_jobs or all_reporting_jobs, cfg.notifications)

    # 11. Open HTML Dashboard
    if open_browser and paths.get("html"):
        html_file = Path(paths["html"]).resolve()
        console.print(f"[cyan]🌐 Opening dashboard in browser...[/cyan]")
        webbrowser.open(html_file.as_uri())

def test_ai():
    """Test AI model connection with a dummy job description."""
    console.print("[cyan]Testing AI connection...[/cyan]")
    cfg = load_config()
    test_job = JobPost(
        id="test-1",
        title="AI Engineer - GenAI / Python",
        company="Tech Innovators Inc",
        location="Bengaluru",
        site="linkedin",
        job_url="https://example.com/job/1",
        date_posted="Today",
        is_remote=True,
        description="Looking for an AI Developer with 1-2 years experience in Python, LangGraph, RAG pipelines, and GCP. Experience with LLM prompting and Vertex AI is a huge plus."
    )

    console.print("[dim]Evaluating sample job for Kushal B R...[/dim]")
    analysis = evaluate_single_job(test_job, cfg.candidate_profile, cfg.ai_matcher)
    console.print(Panel(
        f"[bold]Match Score:[/bold] {analysis.match_score}%\n"
        f"[bold]Decision:[/bold] {analysis.decision}\n"
        f"[bold]Matching Skills:[/bold] {', '.join(analysis.key_matching_skills)}\n"
        f"[bold]Missing / Gaps:[/bold] {', '.join(analysis.missing_skills_or_gaps)}\n"
        f"[bold]Summary:[/bold] {analysis.summary_reason}\n"
        f"[bold]Recommendation:[/bold] {analysis.recommended_action}",
        title="AI Evaluation Result",
        border_style="green"
    ))

def test_scrape():
    """Quick scrape test with 2 jobs."""
    console.print("[cyan]Running a fast scrape test (1 keyword, 2 results)...[/cyan]")
    cfg = load_config()
    test_search_cfg = cfg.search.model_copy()
    test_search_cfg.keywords = [cfg.search.keywords[0]]
    test_search_cfg.results_per_query = 2
    test_search_cfg.hours_old = 72
    
    jobs = scrape_all_jobs(test_search_cfg)
    console.print(f"[bold green]Successfully retrieved {len(jobs)} jobs in test![/bold green]")
    for j in jobs[:3]:
        console.print(f"• [bold]{j.title}[/bold] at {j.company} ({j.site}) - [link={j.job_url}]Link[/link]")

def view_dashboard():
    """Open existing latest HTML report in browser."""
    latest_html = Path(__file__).parent / "results" / "latest_jobs.html"
    if not latest_html.exists():
        console.print("[yellow]No report found yet. Run `python main.py run` first![/yellow]")
        return
    console.print(f"[cyan]Opening {latest_html}...[/cyan]")
    webbrowser.open(latest_html.resolve().as_uri())

def start_server(port: int = 8000, open_browser: bool = True):
    """Start FastAPI backend server with live infinite-scroll frontend."""
    console.print(Panel.fit(
        f"[bold cyan]⚡ AI Job Radar Live Server[/bold cyan]\n"
        f"[green]Open in browser: http://127.0.0.1:{port}[/green]\n"
        f"[dim]Supports Infinite Scrolling & Real-Time Dynamic Refresh[/dim]",
        border_style="cyan"
    ))
    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{port}")
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)

def main():
    parser = argparse.ArgumentParser(description="AI Job Searcher & 24H Matcher")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # serve command (Live dynamic web app)
    serve_parser = subparsers.add_parser("serve", help="Start FastAPI server with live infinite-scroll dashboard")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to run server on (default: 8000)")
    serve_parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")

    # run command
    run_parser = subparsers.add_parser("run", help="Scrape, match, and export jobs")
    run_parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    run_parser.add_argument("--limit", type=int, default=None, help="Max jobs to evaluate with AI (default from profile.yaml, 0 for all)")
    run_parser.add_argument("--all", action="store_true", help="Evaluate all scraped jobs with AI")

    # test-ai command
    subparsers.add_parser("test-ai", help="Test LLM connection and evaluation")

    # test-scrape command
    subparsers.add_parser("test-scrape", help="Test scraping with 2 jobs")

    # view command
    subparsers.add_parser("view", help="View latest static HTML dashboard")

    # reset command
    subparsers.add_parser("reset", help="Reset SQLite database and clear all stored jobs")

    args = parser.parse_args()

    if args.command == "serve":
        start_server(
            port=getattr(args, "port", 8000),
            open_browser=not getattr(args, "no_browser", False)
        )
    elif args.command == "run" or args.command is None:
        eval_limit = 0 if getattr(args, "all", False) else getattr(args, "limit", None)
        run_job_search(
            open_browser=not getattr(args, "no_browser", False),
            limit=eval_limit
        )
    elif args.command == "test-ai":
        test_ai()
    elif args.command == "test-scrape":
        test_scrape()
    elif args.command == "view":
        view_dashboard()
    elif args.command == "reset":
        import db
        db.clear_db()
        console.print("[bold green]✓ SQLite database reset successfully! All jobs cleared.[/bold green]")

if __name__ == "__main__":
    main()
