from typing import List, Optional
from pydantic import BaseModel, Field

class MatchAnalysis(BaseModel):
    match_score: int = Field(default=0, description="Match score from 0 to 100")
    decision: str = Field(default="PENDING", description="STRONG_MATCH, MODERATE_MATCH, or LOW_MATCH")
    key_matching_skills: List[str] = Field(default_factory=list)
    missing_skills_or_gaps: List[str] = Field(default_factory=list)
    summary_reason: str = Field(default="")
    recommended_action: str = Field(default="")

class JobPost(BaseModel):
    id: str
    title: str
    company: str
    location: str = "Not specified"
    site: str
    job_url: str
    date_posted: Optional[str] = None
    is_remote: bool = False
    description: str = ""
    salary: Optional[str] = None
    match_analysis: Optional[MatchAnalysis] = None
