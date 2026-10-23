import json
import logging
import re
from typing import List, Optional
import ollama
from rich.console import Console
from rich.progress import track

from config import CandidateProfile, AiMatcherConfig
from models import JobPost, MatchAnalysis

console = Console()
logger = logging.getLogger("ai_job_searcher.matcher")

EVALUATION_SYSTEM_PROMPT = """You are an expert technical recruiter and career coach.
Your job is to objectively analyze a job posting against a candidate's profile and evaluate how well they match.

CRITICAL EXPERIENCE & SENIORITY RULES:
1. Pay STRICT attention to years of experience. The candidate has 1.5 years of experience (2024 B.E. graduate, currently AI Developer at TCS).
2. If the job posting asks for 4+ years of experience, or is clearly a Senior/Lead/Staff/Architect role:
   - Score it LOW (< 45).
   - In "missing_skills_or_gaps", explicitly include: "Experience mismatch: Role requires senior-level years (candidate has 1.5 years)".
   - In "summary_reason", highlight the seniority gap as the primary reason.
3. LOCATION PREFERENCE RULES:
   - The candidate STRICTLY wants roles located in Bengaluru (Bangalore) OR 100% Remote roles.
   - If a job is explicitly on-site or hybrid in another city (e.g. Hyderabad, Pune, Mumbai, Delhi, Gurgaon, Noida, Chennai) and NOT remote:
     - Score it LOW (< 45).
     - In "missing_skills_or_gaps", include: "Location mismatch: On-site/hybrid role outside Bengaluru (candidate only accepts Bengaluru or Remote)".
     - In "recommended_action", say "Skip".
4. If the role is for Early Career / Junior / SDE 1 / Mid-level (0 - 3 years experience) in Bengaluru or Remote:
   - If candidate's skills (Python, GenAI, LangChain, LangGraph, Vertex AI, GCP, Node.js, Java Spring Boot) match, award a HIGH score (75 - 95).
   - In "recommended_action", say "Apply now".
5. Return ONLY valid JSON with this exact schema:
{
  "match_score": <integer from 0 to 100>,
  "decision": "<STRONG_MATCH | MODERATE_MATCH | LOW_MATCH>",
  "key_matching_skills": ["skill1", "skill2"],
  "missing_skills_or_gaps": ["gap1", "gap2"],
  "summary_reason": "<1-2 concise sentences explaining score and experience fit>",
  "recommended_action": "<Apply now | Consider applying | Skip>"
}
6. Return raw JSON without markdown formatting.
"""

def extract_json(text: str) -> dict:
    """Extract and parse JSON object from LLM response text."""
    text = text.strip()
    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try regex search for { ... }
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    # Fallback default
    return {
        "match_score": 50,
        "decision": "MODERATE_MATCH",
        "key_matching_skills": [],
        "missing_skills_or_gaps": [],
        "summary_reason": "Could not parse detailed AI evaluation.",
        "recommended_action": "Review manually"
    }

def evaluate_single_job(
    job: JobPost,
    profile: CandidateProfile,
    ai_cfg: AiMatcherConfig
) -> MatchAnalysis:
    """Evaluate one job description against candidate profile using Ollama or Free API."""
    # Truncate description to keep local inference snappy (~2500 chars)
    desc = job.description[:2500] if job.description else "No description provided."
    
    user_prompt = f"""
CANDIDATE PROFILE:
- Name: {profile.full_name}
- Current Title: {profile.title}
- Years of Experience: {profile.years_of_experience}
- Core Skills: {', '.join(profile.skills)}
- Preferences: {', '.join(profile.preferences)}
- Dealbreakers: {', '.join(profile.dealbreakers)}
- Summary: {profile.bio_summary}

JOB POSTING:
- Title: {job.title}
- Company: {job.company}
- Location: {job.location} (Remote: {job.is_remote})
- Salary: {job.salary or 'Not specified'}
- Description Snippet:
{desc}

Evaluate the candidate for this job and return the JSON evaluation.
"""

    try:
        if ai_cfg.provider == "ollama":
            # Using local Ollama with JSON format enforcement
            response = ollama.chat(
                model=ai_cfg.ollama.model,
                messages=[
                    {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                format="json"
            )
            raw_content = response.message.content
            parsed = extract_json(raw_content)

            return MatchAnalysis(
                match_score=int(parsed.get("match_score", 50)),
                decision=str(parsed.get("decision", "MODERATE_MATCH")),
                key_matching_skills=list(parsed.get("key_matching_skills", [])),
                missing_skills_or_gaps=list(parsed.get("missing_skills_or_gaps", [])),
                summary_reason=str(parsed.get("summary_reason", "")),
                recommended_action=str(parsed.get("recommended_action", "Consider applying"))
            )

        elif ai_cfg.provider == "free_api" and ai_cfg.free_api.provider == "groq":
            key = (ai_cfg.free_api.api_key or "").strip()
            if not key or not key.startswith("gsk_"):
                masked = f"{key[:4]}..." if len(key) >= 4 else "empty"
                raise ValueError(
                    f"Invalid Groq API key '{masked}'. Groq API keys start with 'gsk_'. "
                    f"Note: 16-letter codes (like 'nkyi dvyw...') are Gmail App Passwords, not Groq keys! "
                    f"Please get a free Groq key at https://console.groq.com/keys and set GROQ_API_KEY."
                )

            from groq import Groq
            client = Groq(api_key=key)

            primary_model = ai_cfg.free_api.model or "openai/gpt-oss-120b"
            candidate_models = [
                primary_model,
                "openai/gpt-oss-120b",
                "openai/gpt-oss-20b",
                "qwen/qwen3.8-27b",
                "llama-3.1-8b-instant",
                "llama-3.3-70b-versatile",
            ]
            # Deduplicate preserving order
            seen = set()
            models_to_try = [m for m in candidate_models if m and not (m in seen or seen.add(m))]

            content = None
            last_err = None
            for model_name in models_to_try:
                try:
                    completion = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt}
                        ],
                        response_format={"type": "json_object"}
                    )
                    content = completion.choices[0].message.content
                    ai_cfg.free_api.model = model_name  # Cache working model
                    break
                except Exception as ex:
                    last_err = ex
                    err_msg = str(ex).lower()
                    if "model_not_found" in err_msg or "does not exist" in err_msg or "404" in err_msg or "access" in err_msg:
                        logger.info(f"Model {model_name} not accessible on Groq, trying next fallback...")
                        continue
                    raise ex

            if content is None:
                raise last_err or RuntimeError("No compatible Groq model available.")
            parsed = extract_json(content)
            return MatchAnalysis(
                match_score=int(parsed.get("match_score", 50)),
                decision=str(parsed.get("decision", "MODERATE_MATCH")),
                key_matching_skills=list(parsed.get("key_matching_skills", [])),
                missing_skills_or_gaps=list(parsed.get("missing_skills_or_gaps", [])),
                summary_reason=str(parsed.get("summary_reason", "")),
                recommended_action=str(parsed.get("recommended_action", "Consider applying"))
            )
        else:
            # Fallback
            return MatchAnalysis(
                match_score=60,
                decision="MODERATE_MATCH",
                summary_reason="AI evaluation skipped (unsupported provider).",
                recommended_action="Review manually"
            )

    except Exception as e:
        logger.warning(f"Error evaluating job {job.title} at {job.company}: {e}")
        return MatchAnalysis(
            match_score=50,
            decision="MODERATE_MATCH",
            summary_reason=f"Evaluation failed: {str(e)[:100]}",
            recommended_action="Review manually"
        )

def evaluate_all_jobs(
    jobs: List[JobPost],
    profile: CandidateProfile,
    ai_cfg: AiMatcherConfig
) -> List[JobPost]:
    """Score and match all scraped jobs with progress bar."""
    if not jobs:
        return []

    console.print(f"[bold cyan]🧠 AI Evaluating {len(jobs)} jobs using {ai_cfg.provider} ({ai_cfg.ollama.model if ai_cfg.provider == 'ollama' else ai_cfg.free_api.model})...[/bold cyan]")

    for job in track(jobs, description="Analyzing job descriptions..."):
        job.match_analysis = evaluate_single_job(job, profile, ai_cfg)

    # Sort jobs by match_score descending
    jobs.sort(key=lambda j: j.match_analysis.match_score if j.match_analysis else 0, reverse=True)
    return jobs
