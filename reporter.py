import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import os
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import List
from rich.console import Console
from rich.table import Table

from models import JobPost

console = Console(highlight=False)
RESULTS_DIR = Path(__file__).parent / "results"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Job Searcher - 24H Fresh Matches</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-primary: #0a0d14;
      --bg-card: rgba(18, 24, 38, 0.7);
      --bg-card-hover: rgba(26, 35, 54, 0.85);
      --border-color: rgba(255, 255, 255, 0.08);
      --border-hover: rgba(99, 102, 241, 0.4);
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent-purple: #6366f1;
      --accent-cyan: #06b6d4;
      --accent-green: #10b981;
      --accent-amber: #f59e0b;
      --accent-red: #ef4444;
      --glass-blur: blur(16px);
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background: radial-gradient(circle at top left, #13172e 0%, var(--bg-primary) 60%);
      color: var(--text-main);
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      min-height: 100vh;
      padding: 2.5rem 1.5rem;
      line-height: 1.5;
    }

    .container {
      max-width: 1280px;
      margin: 0 auto;
    }

    header {
      margin-bottom: 2.5rem;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1.5rem;
      padding-bottom: 2rem;
      border-bottom: 1px solid var(--border-color);
    }

    .brand-title {
      font-size: 2.2rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      background: linear-gradient(135deg, #fff 30%, #a5b4fc 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .brand-subtitle {
      color: var(--text-muted);
      font-size: 0.95rem;
      margin-top: 0.25rem;
    }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1.25rem;
      margin-bottom: 2.5rem;
    }

    .stat-card {
      background: var(--bg-card);
      backdrop-filter: var(--glass-blur);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 1.25rem 1.5rem;
      transition: transform 0.2s, border-color 0.2s;
    }
    .stat-card:hover {
      transform: translateY(-2px);
      border-color: var(--border-hover);
    }
    .stat-label {
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      font-weight: 600;
    }
    .stat-val {
      font-size: 2rem;
      font-weight: 800;
      color: #fff;
      margin-top: 0.25rem;
    }

    /* Controls */
    .controls {
      background: var(--bg-card);
      backdrop-filter: var(--glass-blur);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 1.25rem;
      margin-bottom: 2rem;
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      align-items: center;
      justify-content: space-between;
    }

    .search-input {
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid var(--border-color);
      color: #fff;
      padding: 0.65rem 1.2rem;
      border-radius: 10px;
      font-size: 0.95rem;
      width: 100%;
      max-width: 360px;
      outline: none;
      transition: border-color 0.2s;
    }
    .search-input:focus {
      border-color: var(--accent-purple);
    }

    .filter-group {
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
    }

    .filter-btn {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      padding: 0.5rem 1rem;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    .filter-btn:hover, .filter-btn.active {
      background: var(--accent-purple);
      color: #fff;
      border-color: var(--accent-purple);
    }

    /* Job Card Grid */
    .jobs-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
      gap: 1.5rem;
    }

    .job-card {
      background: var(--bg-card);
      backdrop-filter: var(--glass-blur);
      border: 1px solid var(--border-color);
      border-radius: 18px;
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: all 0.25s ease;
      position: relative;
      overflow: hidden;
    }

    .job-card:hover {
      background: var(--bg-card-hover);
      transform: translateY(-4px);
      border-color: var(--border-hover);
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4);
    }

    .job-card-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 1rem;
      margin-bottom: 1rem;
    }

    .job-role-info {
      flex: 1;
    }

    .job-title {
      font-size: 1.25rem;
      font-weight: 700;
      color: #fff;
      line-height: 1.3;
      margin-bottom: 0.35rem;
    }

    .job-company {
      font-size: 0.95rem;
      color: var(--accent-cyan);
      font-weight: 600;
    }

    .score-badge {
      padding: 0.45rem 0.85rem;
      border-radius: 12px;
      font-weight: 800;
      font-size: 0.95rem;
      text-align: center;
      min-width: 60px;
    }
    .score-high {
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: var(--accent-green);
    }
    .score-mid {
      background: rgba(6, 182, 212, 0.15);
      border: 1px solid rgba(6, 182, 212, 0.4);
      color: var(--accent-cyan);
    }
    .score-low {
      background: rgba(245, 158, 11, 0.15);
      border: 1px solid rgba(245, 158, 11, 0.4);
      color: var(--accent-amber);
    }

    .meta-badges {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      margin: 0.75rem 0 1.2rem;
    }

    .meta-tag {
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.25rem 0.65rem;
      border-radius: 6px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.06);
      color: var(--text-muted);
    }
    .tag-platform {
      background: rgba(99, 102, 241, 0.15);
      color: #a5b4fc;
      border-color: rgba(99, 102, 241, 0.3);
      text-transform: capitalize;
    }
    .tag-remote {
      background: rgba(16, 185, 129, 0.12);
      color: #6ee7b7;
      border-color: rgba(16, 185, 129, 0.25);
    }

    .ai-analysis {
      background: rgba(0, 0, 0, 0.25);
      border-radius: 12px;
      padding: 0.85rem 1rem;
      margin-bottom: 1.25rem;
      font-size: 0.85rem;
      border-left: 3px solid var(--accent-purple);
    }

    .ai-reason {
      color: #e2e8f0;
      margin-bottom: 0.5rem;
    }

    .skill-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 0.3rem;
      margin-top: 0.4rem;
    }

    .pill-match {
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
      font-size: 0.7rem;
      font-weight: 600;
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
    }

    .pill-missing {
      background: rgba(239, 68, 68, 0.15);
      color: #f87171;
      font-size: 0.7rem;
      font-weight: 600;
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
    }

    .apply-btn {
      display: block;
      width: 100%;
      text-align: center;
      background: linear-gradient(135deg, var(--accent-purple) 0%, #4f46e5 100%);
      color: #fff;
      text-decoration: none;
      font-weight: 700;
      padding: 0.75rem 1rem;
      border-radius: 10px;
      font-size: 0.9rem;
      transition: opacity 0.2s, transform 0.1s;
    }
    .apply-btn:hover {
      opacity: 0.95;
      transform: scale(1.01);
    }

    .empty-state {
      text-align: center;
      padding: 4rem 1rem;
      color: var(--text-muted);
      grid-column: 1 / -1;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1 class="brand-title">⚡ AI Job Searcher</h1>
        <p class="brand-subtitle">Fresh job postings from the last 24h matched to your profile with local LLM</p>
      </div>
      <div style="text-align: right;">
        <span style="font-size: 0.85rem; color: var(--text-muted);">Generated on: <strong>{{ timestamp }}</strong></span>
      </div>
    </header>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Total Jobs Found</div>
        <div class="stat-val">{{ total_jobs }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Strong Matches (≥75%)</div>
        <div class="stat-val" style="color: var(--accent-green);">{{ strong_matches }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Moderate Matches</div>
        <div class="stat-val" style="color: var(--accent-cyan);">{{ moderate_matches }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Avg Match Score</div>
        <div class="stat-val">{{ avg_score }}%</div>
      </div>
    </div>

    <div class="controls">
      <input type="text" id="searchInput" class="search-input" placeholder="Search by role, company, or keyword...">
      <div class="filter-group">
        <button class="filter-btn active" onclick="filterScore('all', this)">All Jobs ({{ total_jobs }})</button>
        <button class="filter-btn" onclick="filterScore('high', this)">75%+ Score</button>
        <button class="filter-btn" onclick="filterScore('mid', this)">60%+ Score</button>
        <button class="filter-btn" onclick="filterScore('ai', this)">Detailed AI Matches</button>
        <button class="filter-btn" onclick="filterRemote(this)">Remote Only</button>
      </div>
    </div>

    <div class="jobs-grid" id="jobsGrid">
      {% for job in jobs %}
      <div class="job-card" 
           data-score="{{ job.match_analysis.match_score if job.match_analysis else 0 }}" 
           data-remote="{{ 'true' if job.is_remote else 'false' }}"
           data-decision="{{ job.match_analysis.decision if job.match_analysis else 'UNASSESSED' }}"
           data-search="{{ job.title | lower }} {{ job.company | lower }} {{ job.location | lower }}">
        
        <div>
          <div class="job-card-top">
            <div class="job-role-info">
              <h2 class="job-title">{{ job.title }}</h2>
              <div class="job-company">{{ job.company }}</div>
            </div>
            
            {% set score = job.match_analysis.match_score if job.match_analysis else 0 %}
            <div class="score-badge {% if score >= 75 %}score-high{% elif score >= 60 %}score-mid{% else %}score-low{% endif %}">
              {{ score }}%
            </div>
          </div>

          <div class="meta-badges">
            <span class="meta-tag tag-platform">{{ job.site }}</span>
            <span class="meta-tag">📍 {{ job.location }}</span>
            {% if job.is_remote %}
            <span class="meta-tag tag-remote">🌐 Remote</span>
            {% endif %}
            {% if job.salary %}
            <span class="meta-tag">💰 {{ job.salary }}</span>
            {% endif %}
            {% if job.date_posted %}
            <span class="meta-tag">🕒 {{ job.date_posted }}</span>
            {% endif %}
          </div>

          {% if job.match_analysis %}
          <div class="ai-analysis">
            <div class="ai-reason">{{ job.match_analysis.summary_reason }}</div>
            
            {% if job.match_analysis.key_matching_skills %}
            <div class="skill-pills">
              {% for skill in job.match_analysis.key_matching_skills %}
              <span class="pill-match">✓ {{ skill }}</span>
              {% endfor %}
            </div>
            {% endif %}

            {% if job.match_analysis.missing_skills_or_gaps %}
            <div class="skill-pills">
              {% for gap in job.match_analysis.missing_skills_or_gaps %}
              <span class="pill-missing">✕ {{ gap }}</span>
              {% endfor %}
            </div>
            {% endif %}
          </div>
          {% endif %}
        </div>

        <a href="{{ job.job_url }}" target="_blank" rel="noopener noreferrer" class="apply-btn">
          Apply on {{ job.site | capitalize }} →
        </a>
      </div>
      {% endfor %}
    </div>
  </div>

  <script>
    let currentScoreFilter = 'all';
    let remoteOnly = false;

    const searchInput = document.getElementById('searchInput');
    const cards = document.querySelectorAll('.job-card');

    searchInput.addEventListener('input', applyFilters);

    function filterScore(level, btn) {
      document.querySelectorAll('.filter-group .filter-btn').forEach(b => {
        if (b.innerText.includes('Score') || b.innerText.includes('All')) b.classList.remove('active');
      });
      btn.classList.add('active');
      currentScoreFilter = level;
      applyFilters();
    }

    function filterRemote(btn) {
      remoteOnly = !remoteOnly;
      btn.classList.toggle('active', remoteOnly);
      applyFilters();
    }

    function applyFilters() {
      const query = searchInput.value.toLowerCase().trim();

      cards.forEach(card => {
        const score = parseInt(card.dataset.score || 0);
        const isRemote = card.dataset.remote === 'true';
        const searchText = card.dataset.search || '';

        const matchesQuery = !query || searchText.includes(query);
        const matchesRemote = !remoteOnly || isRemote;
        
        let matchesScore = true;
        if (currentScoreFilter === 'high') matchesScore = score >= 75;
        else if (currentScoreFilter === 'mid') matchesScore = score >= 60;
        else if (currentScoreFilter === 'ai') matchesScore = card.dataset.decision !== 'UNASSESSED';

        if (matchesQuery && matchesRemote && matchesScore) {
          card.style.display = 'flex';
        } else {
          card.style.display = 'none';
        }
      });
    }
  </script>
</body>
</html>
"""

def print_terminal_summary(jobs: List[JobPost]):
    """Print an aesthetic Rich table summary in the terminal."""
    if not jobs:
        console.print("[yellow]No jobs to display.[/yellow]")
        return

    table = Table(title="🚀 AI Matched Jobs (Last 24 Hours)", show_header=True, header_style="bold magenta")
    table.add_column("Score", style="bold", justify="center", width=8)
    table.add_column("Title", style="bold white", width=28)
    table.add_column("Company", style="cyan", width=20)
    table.add_column("Site", style="dim", width=12)
    table.add_column("Location", style="green", width=18)
    table.add_column("AI Verdict", style="yellow", width=36)

    for job in jobs[:15]: # Show top 15 in console
        score = job.match_analysis.match_score if job.match_analysis else 0
        score_str = f"[bold green]{score}%[/bold green]" if score >= 75 else (
            f"[bold cyan]{score}%[/bold cyan]" if score >= 60 else f"[yellow]{score}%[/yellow]"
        )
        reason = job.match_analysis.summary_reason if job.match_analysis else "N/A"
        if len(reason) > 60:
            reason = reason[:57] + "..."

        table.add_row(
            score_str,
            job.title[:26],
            job.company[:18],
            job.site.capitalize(),
            job.location[:16],
            reason
        )

    console.print(table)
    if len(jobs) > 15:
        console.print(f"[dim]...and {len(jobs) - 15} more jobs saved to reports.[/dim]\n")

def export_reports(jobs: List[JobPost]) -> dict:
    """Exports jobs to JSON, CSV, and HTML reports."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. Export JSON
    json_path = RESULTS_DIR / f"jobs_{timestamp_str}.json"
    latest_json_path = RESULTS_DIR / "latest_jobs.json"
    
    jobs_data = [job.model_dump() for job in jobs]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(jobs_data, f, indent=2, ensure_ascii=False)
    with open(latest_json_path, "w", encoding="utf-8") as f:
        json.dump(jobs_data, f, indent=2, ensure_ascii=False)

    # 2. Export CSV
    csv_path = RESULTS_DIR / f"jobs_{timestamp_str}.csv"
    latest_csv_path = RESULTS_DIR / "latest_jobs.csv"

    fieldnames = [
        "id", "score", "decision", "title", "company", "location", 
        "site", "is_remote", "salary", "date_posted", "ai_summary", 
        "matching_skills", "missing_skills", "job_url"
    ]
    
    def write_csv(path: Path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for job in jobs:
                analysis = job.match_analysis
                writer.writerow({
                    "id": job.id,
                    "score": analysis.match_score if analysis else 0,
                    "decision": analysis.decision if analysis else "",
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "site": job.site,
                    "is_remote": job.is_remote,
                    "salary": job.salary or "",
                    "date_posted": job.date_posted or "",
                    "ai_summary": analysis.summary_reason if analysis else "",
                    "matching_skills": ", ".join(analysis.key_matching_skills) if analysis else "",
                    "missing_skills": ", ".join(analysis.missing_skills_or_gaps) if analysis else "",
                    "job_url": job.job_url
                })

    write_csv(csv_path)
    write_csv(latest_csv_path)

    # 3. Export HTML
    html_path = RESULTS_DIR / f"jobs_{timestamp_str}.html"
    latest_html_path = RESULTS_DIR / "latest_jobs.html"

    from jinja2 import Template
    tmpl = Template(HTML_TEMPLATE)

    scores = [j.match_analysis.match_score for j in jobs if j.match_analysis]
    avg_score = round(sum(scores) / len(scores)) if scores else 0
    strong_matches = len([s for s in scores if s >= 75])
    moderate_matches = len([s for s in scores if 60 <= s < 75])

    rendered_html = tmpl.render(
        jobs=jobs,
        timestamp=datetime.now().strftime("%B %d, %Y - %I:%M %p"),
        total_jobs=len(jobs),
        strong_matches=strong_matches,
        moderate_matches=moderate_matches,
        avg_score=avg_score
    )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)
    with open(latest_html_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    console.print(f"[bold green]📊 Reports saved successfully:[/bold green]")
    console.print(f"   • HTML Dashboard: [underline]{latest_html_path}[/underline]")
    console.print(f"   • CSV Spreadsheet: [underline]{latest_csv_path}[/underline]")
    console.print(f"   • JSON Data: [underline]{latest_json_path}[/underline]\n")

    return {
        "html": str(latest_html_path),
        "csv": str(latest_csv_path),
        "json": str(latest_json_path)
    }
