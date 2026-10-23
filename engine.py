import threading
import logging
import time
from typing import Dict, Any, List, Optional
from rich.console import Console

import db
from config import load_config
from scraper import scrape_all_jobs
from matcher import evaluate_single_job
from models import JobPost, MatchAnalysis
from notifier import notify_job_match

console = Console(highlight=False)
logger = logging.getLogger("ai_job_searcher.engine")

class ScrapeEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self.is_running: bool = False
        self.mode: str = "idle" # "idle", "scraping", "batch_evaluating"
        self.status_message: str = "Idle"
        self.total_scraped: int = 0
        self.total_evaluated: int = 0
        self.started_at: float = 0
        self.errors: List[str] = []

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            stats = db.get_stats()
            elapsed = round(time.time() - self.started_at) if self.is_running else 0
            return {
                "is_running": self.is_running,
                "mode": self.mode,
                "status_message": self.status_message,
                "total_scraped_this_run": self.total_scraped,
                "total_evaluated_this_run": self.total_evaluated,
                "elapsed_seconds": elapsed,
                "stats": stats,
                "errors": self.errors[-3:]
            }

    def stop(self) -> bool:
        """Requests graceful stop of the background scrape or batch evaluation."""
        with self._lock:
            if not self.is_running:
                return False
            self._stop_event.set()
            self.status_message = "Pausing background analysis..."
            return True

    def start_refresh_async(self, limit_evaluations: int = 25, continuous_batch: bool = True) -> bool:
        """Starts scraping 24H jobs and begins AI evaluation."""
        with self._lock:
            if self.is_running:
                return False
            self._stop_event.clear()
            self.is_running = True
            self.mode = "scraping"
            self.status_message = "Starting job scrape..."
            self.total_scraped = 0
            self.total_evaluated = 0
            self.started_at = time.time()
            self.errors = []

        thread = threading.Thread(
            target=self._run_pipeline,
            args=(limit_evaluations, continuous_batch),
            daemon=True
        )
        thread.start()
        return True

    def start_batch_evaluator_async(self, batch_size: int = 10) -> bool:
        """Starts batch AI evaluation on all unassessed jobs in the database."""
        with self._lock:
            if self.is_running:
                return False
            self._stop_event.clear()
            self.is_running = True
            self.mode = "batch_evaluating"
            self.status_message = "Starting batch evaluation for unassessed jobs..."
            self.total_scraped = 0
            self.total_evaluated = 0
            self.started_at = time.time()
            self.errors = []

        thread = threading.Thread(
            target=self._run_batch_evaluation_loop,
            args=(batch_size,),
            daemon=True
        )
        thread.start()
        return True

    def _run_pipeline(self, limit_evaluations: int, continuous_batch: bool):
        cfg = load_config()
        db.init_db()

        try:
            with self._lock:
                self.status_message = f"Scraping LinkedIn, Indeed, Glassdoor (last {cfg.search.hours_old}h)..."

            # 1. Run Scrape
            jobs = scrape_all_jobs(cfg.search)
            if self._stop_event.is_set():
                with self._lock:
                    self.status_message = "Scrape stopped by user."
                return

            with self._lock:
                self.total_scraped = len(jobs)
                self.status_message = f"Scraped {len(jobs)} postings. Upserting to database..."

            # 2. Upsert newly scraped jobs into DB immediately
            db.upsert_jobs(jobs)

            # 3. Filter & Sort by relevance for candidate Kushal
            senior_kws = cfg.experience_filter.senior_keywords

            def calculate_relevance(j: JobPost) -> int:
                t = j.title.lower()
                s = 0
                for kw in cfg.search.keywords:
                    if kw.lower() in t:
                        s += 25
                for tech in ["genai", "ai", "langgraph", "langchain", "rag", "vertex ai", "gcp", "python", "fastapi", "node"]:
                    if tech in t:
                        s += 15
                for sk in senior_kws:
                    if sk in t:
                        s -= 40
                return s

            jobs.sort(key=calculate_relevance, reverse=True)

            # 4. In-depth AI Evaluation using Ollama on initial high-priority batch
            target_eval_limit = limit_evaluations if limit_evaluations > 0 else len(jobs)
            to_eval = jobs[:target_eval_limit]

            with self._lock:
                self.mode = "batch_evaluating"
                self.status_message = f"AI evaluating initial top {len(to_eval)} relevant jobs with Ollama..."

            for idx, job in enumerate(to_eval, 1):
                if self._stop_event.is_set():
                    with self._lock:
                        self.status_message = "Evaluation paused by user."
                    return

                with self._lock:
                    self.status_message = f"Evaluating initial batch ({idx}/{len(to_eval)}): {job.title[:25]} at {job.company[:18]}..."
                
                try:
                    analysis = evaluate_single_job(job, cfg.candidate_profile, cfg.ai_matcher)
                    job.match_analysis = analysis
                    db.update_job_analysis(job.id, analysis)
                    with self._lock:
                        self.total_evaluated += 1

                    # Trigger instant alert if job matches threshold (e.g. >= 60%)
                    if cfg.notifications.enabled and cfg.notifications.notify_on_analysis and analysis.match_score >= cfg.notifications.min_score:
                        try:
                            notify_job_match(job, analysis, cfg.notifications)
                        except Exception as n_err:
                            logger.warning(f"Notification error for {job.id}: {n_err}")
                except Exception as e:
                    logger.warning(f"Error evaluating {job.id}: {e}")

                time.sleep(0.1)

            # 5. If continuous_batch is requested, seamlessly continue evaluating all remaining unassessed jobs in batches
            if continuous_batch and not self._stop_event.is_set():
                self._run_batch_evaluation_loop(batch_size=10, is_continuation=True)
            else:
                with self._lock:
                    self.status_message = f"Complete! {len(jobs)} jobs scraped, {self.total_evaluated} AI-evaluated."

        except Exception as e:
            logger.error(f"Error in background scrape pipeline: {e}")
            with self._lock:
                self.errors.append(str(e))
                self.status_message = f"Error during scrape: {str(e)[:80]}"
        finally:
            with self._lock:
                self.is_running = False
                self.mode = "idle"

    def _run_batch_evaluation_loop(self, batch_size: int = 10, is_continuation: bool = False):
        cfg = load_config()
        db.init_db()

        try:
            with self._lock:
                self.mode = "batch_evaluating"

            batch_num = 0
            while not self._stop_event.is_set():
                unassessed = db.get_unassessed_jobs(limit=batch_size)
                if not unassessed:
                    with self._lock:
                        self.status_message = f"Complete! All jobs in database have been evaluated by AI."
                    break

                batch_num += 1
                stats = db.get_stats()
                total_in_db = stats.get("total_jobs", 0)
                evaluated_in_db = stats.get("evaluated_jobs", 0)

                with self._lock:
                    self.status_message = f"Batch #{batch_num}: Processing {len(unassessed)} jobs ({evaluated_in_db}/{total_in_db} evaluated)..."

                for idx, job in enumerate(unassessed, 1):
                    if self._stop_event.is_set():
                        with self._lock:
                            self.status_message = f"Batch analysis paused by user ({evaluated_in_db}/{total_in_db} assessed)."
                        return

                    with self._lock:
                        self.status_message = f"Batch #{batch_num} ({idx}/{len(unassessed)}): {job.title[:25]} at {job.company[:18]}..."

                    try:
                        analysis = evaluate_single_job(job, cfg.candidate_profile, cfg.ai_matcher)
                        job.match_analysis = analysis
                        db.update_job_analysis(job.id, analysis)
                        with self._lock:
                            self.total_evaluated += 1

                        # Trigger instant alert if job matches threshold (e.g. >= 60%)
                        if cfg.notifications.enabled and cfg.notifications.notify_on_analysis and analysis.match_score >= cfg.notifications.min_score:
                            try:
                                notify_job_match(job, analysis, cfg.notifications)
                            except Exception as n_err:
                                logger.warning(f"Notification error for {job.id}: {n_err}")
                    except Exception as e:
                        logger.warning(f"Error evaluating {job.id}: {e}")

                    # Brief yield between jobs so CPU and Ollama remain smooth and responsive
                    time.sleep(0.15)

                # Small rest between batches
                time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error in batch evaluation loop: {e}")
            with self._lock:
                self.errors.append(str(e))
                self.status_message = f"Batch analysis error: {str(e)[:80]}"
        finally:
            if not is_continuation:
                with self._lock:
                    self.is_running = False
                    self.mode = "idle"

# Global singleton
engine = ScrapeEngine()
