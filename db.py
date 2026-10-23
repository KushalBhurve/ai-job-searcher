import sqlite3
import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from models import JobPost, MatchAnalysis

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).parent / "jobs.db"))

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        location TEXT,
        site TEXT,
        job_url TEXT,
        date_posted TEXT,
        is_remote INTEGER DEFAULT 0,
        salary TEXT,
        description TEXT,
        match_score INTEGER DEFAULT 0,
        decision TEXT DEFAULT 'UNASSESSED',
        matching_skills TEXT,
        missing_skills TEXT,
        summary_reason TEXT,
        recommended_action TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(match_score DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_site ON jobs(site)")
    conn.commit()
    conn.close()

def clear_db():
    """Wipes all jobs from the database and vacuums SQLite storage."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs")
    cursor.execute("VACUUM")
    conn.commit()
    conn.close()


def upsert_job(cursor, job: JobPost):
    """Insert or update a job post. Preserves match_analysis if newly scraped job has none."""
    analysis = job.match_analysis
    matching_skills_json = json.dumps(analysis.key_matching_skills) if analysis else "[]"
    missing_skills_json = json.dumps(analysis.missing_skills_or_gaps) if analysis else "[]"
    score = analysis.match_score if analysis else 0
    decision = analysis.decision if analysis else "UNASSESSED"
    reason = analysis.summary_reason if analysis else ""
    rec_action = analysis.recommended_action if analysis else ""

    cursor.execute("""
    INSERT INTO jobs (
        id, title, company, location, site, job_url, date_posted,
        is_remote, salary, description, match_score, decision,
        matching_skills, missing_skills, summary_reason, recommended_action,
        updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(id) DO UPDATE SET
        title=excluded.title,
        company=excluded.company,
        location=excluded.location,
        site=excluded.site,
        job_url=excluded.job_url,
        date_posted=excluded.date_posted,
        is_remote=excluded.is_remote,
        salary=excluded.salary,
        description=excluded.description,
        match_score=CASE WHEN jobs.match_score > 0 THEN jobs.match_score ELSE excluded.match_score END,
        decision=CASE WHEN jobs.decision != 'UNASSESSED' THEN jobs.decision ELSE excluded.decision END,
        matching_skills=CASE WHEN jobs.decision != 'UNASSESSED' THEN jobs.matching_skills ELSE excluded.matching_skills END,
        missing_skills=CASE WHEN jobs.decision != 'UNASSESSED' THEN jobs.missing_skills ELSE excluded.missing_skills END,
        summary_reason=CASE WHEN jobs.decision != 'UNASSESSED' THEN jobs.summary_reason ELSE excluded.summary_reason END,
        recommended_action=CASE WHEN jobs.decision != 'UNASSESSED' THEN jobs.recommended_action ELSE excluded.recommended_action END,
        updated_at=CURRENT_TIMESTAMP
    """, (
        job.id, job.title, job.company, job.location, job.site, job.job_url,
        job.date_posted, 1 if job.is_remote else 0, job.salary, job.description,
        score, decision, matching_skills_json, missing_skills_json, reason, rec_action
    ))

def upsert_jobs(jobs: List[JobPost]) -> int:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    count = 0
    for job in jobs:
        upsert_job(cursor, job)
        count += 1
    conn.commit()
    conn.close()
    return count

def update_job_analysis(job_id: str, analysis: MatchAnalysis):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE jobs SET
        match_score = ?,
        decision = ?,
        matching_skills = ?,
        missing_skills = ?,
        summary_reason = ?,
        recommended_action = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (
        analysis.match_score,
        analysis.decision,
        json.dumps(analysis.key_matching_skills),
        json.dumps(analysis.missing_skills_or_gaps),
        analysis.summary_reason,
        analysis.recommended_action,
        job_id
    ))
    conn.commit()
    conn.close()

def row_to_job(row: sqlite3.Row) -> dict:
    matching_skills = []
    missing_skills = []
    try:
        if row["matching_skills"]:
            matching_skills = json.loads(row["matching_skills"])
        if row["missing_skills"]:
            missing_skills = json.loads(row["missing_skills"])
    except Exception:
        pass

    return {
        "id": row["id"],
        "title": row["title"],
        "company": row["company"],
        "location": row["location"] or "Not specified",
        "site": row["site"] or "linkedin",
        "job_url": row["job_url"],
        "date_posted": row["date_posted"] or "",
        "is_remote": bool(row["is_remote"]),
        "salary": row["salary"] or "",
        "description": row["description"] or "",
        "match_score": row["match_score"],
        "decision": row["decision"],
        "matching_skills": matching_skills,
        "missing_skills": missing_skills,
        "summary_reason": row["summary_reason"] or "",
        "recommended_action": row["recommended_action"] or "",
        "created_at": str(row["created_at"])
    }

def get_jobs(
    page: int = 1,
    limit: int = 12,
    search: Optional[str] = None,
    min_score: Optional[int] = None,
    remote_only: bool = False,
    platform: Optional[str] = None,
    sort_by: str = "score" # "score" or "date"
) -> Dict[str, Any]:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    conditions = ["1=1"]
    params: List[Any] = []

    if search:
        search_like = f"%{search.strip().lower()}%"
        conditions.append("(LOWER(title) LIKE ? OR LOWER(company) LIKE ? OR LOWER(location) LIKE ?)")
        params.extend([search_like, search_like, search_like])

    if min_score is not None and min_score > 0:
        conditions.append("match_score >= ?")
        params.append(min_score)

    if remote_only:
        conditions.append("is_remote = 1")

    if platform and platform.lower() != "all":
        conditions.append("LOWER(site) = ?")
        params.append(platform.lower())

    where_clause = " AND ".join(conditions)

    # Count total
    count_query = f"SELECT COUNT(*) FROM jobs WHERE {where_clause}"
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    # Order by
    if sort_by == "date":
        order_clause = "ORDER BY created_at DESC, match_score DESC"
    else:
        order_clause = "ORDER BY match_score DESC, created_at DESC"

    # Pagination
    offset = (page - 1) * limit
    data_query = f"""
    SELECT * FROM jobs 
    WHERE {where_clause} 
    {order_clause} 
    LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    cursor.execute(data_query, params)
    rows = cursor.fetchall()
    jobs = [row_to_job(r) for r in rows]

    total_pages = (total + limit - 1) // limit if limit > 0 else 1
    has_more = page < total_pages

    conn.close()
    return {
        "jobs": jobs,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "has_more": has_more
    }

def get_stats() -> Dict[str, Any]:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM jobs")
    total_jobs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM jobs WHERE match_score >= 75")
    strong_matches = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM jobs WHERE match_score >= 60 AND match_score < 75")
    moderate_matches = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(match_score) FROM jobs WHERE match_score > 0")
    avg_score_row = cursor.fetchone()[0]
    avg_score = round(avg_score_row) if avg_score_row else 0

    cursor.execute("SELECT site, COUNT(*) FROM jobs GROUP BY site")
    platforms = {row[0]: row[1] for row in cursor.fetchall()}

    cursor.execute("SELECT COUNT(*) FROM jobs WHERE decision != 'UNASSESSED'")
    evaluated_jobs = cursor.fetchone()[0]
    unassessed_jobs = total_jobs - evaluated_jobs

    conn.close()
    return {
        "total_jobs": total_jobs,
        "strong_matches": strong_matches,
        "moderate_matches": moderate_matches,
        "avg_score": avg_score,
        "evaluated_jobs": evaluated_jobs,
        "unassessed_jobs": unassessed_jobs,
        "platforms": platforms
    }

def get_unassessed_jobs(limit: int = 15) -> List[JobPost]:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM jobs 
    WHERE decision = 'UNASSESSED'
    ORDER BY 
      CASE 
        WHEN LOWER(title) LIKE '%genai%' OR LOWER(title) LIKE '%ai engineer%' OR LOWER(title) LIKE '%ai developer%' THEN 1
        WHEN LOWER(title) LIKE '%python%' OR LOWER(title) LIKE '%sde%' OR LOWER(title) LIKE '%software engineer%' OR LOWER(title) LIKE '%backend%' THEN 2
        ELSE 3
      END ASC,
      created_at DESC 
    LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    unassessed = []
    for r in rows:
        unassessed.append(JobPost(
            id=r["id"],
            title=r["title"],
            company=r["company"],
            location=r["location"] or "",
            site=r["site"] or "",
            job_url=r["job_url"],
            date_posted=r["date_posted"] or "",
            is_remote=bool(r["is_remote"]),
            salary=r["salary"] or "",
            description=r["description"] or ""
        ))
    conn.close()
    return unassessed
