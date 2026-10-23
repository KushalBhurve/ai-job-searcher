import os
import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

CONFIG_FILE = Path(__file__).parent / "profile.yaml"

class SearchConfig(BaseModel):
    keywords: List[str] = Field(default_factory=lambda: ["AI Engineer", "Software Engineer"])
    locations: List[str] = Field(default_factory=lambda: ["Bengaluru", "Remote"])
    hours_old: int = 24
    results_per_query: int = 15
    sites: List[str] = Field(default_factory=lambda: ["linkedin", "indeed", "glassdoor"])
    country: str = "india"
    is_remote: Optional[bool] = None

class ExperienceFilterConfig(BaseModel):
    max_experience_years: int = 3
    exclude_senior_titles: bool = True
    senior_keywords: List[str] = Field(default_factory=lambda: [
        "senior", "sr.", "sr ", "lead", "principal", "architect",
        "staff", "director", "manager", "head of", "vp", "expert",
        "consultant - senior", "specialist iii", "engineer iii",
        "7+ years", "8+ years", "10+ years"
    ])

class ExecutionConfig(BaseModel):
    evaluate_limit: int = 0 # 0 means evaluate all relevant jobs
    include_all_in_report: bool = True

class CandidateProfile(BaseModel):
    full_name: str = "Kushal B R"
    title: str = "AI & Platform Engineer / GenAI Developer"
    years_of_experience: float = 1.5
    education: str = "B.E. Computer Science (2020-2024, GPA: 8.5)"
    skills: List[str] = Field(default_factory=list)
    preferences: List[str] = Field(default_factory=list)
    dealbreakers: List[str] = Field(default_factory=list)
    bio_summary: str = ""

class OllamaConfig(BaseModel):
    model: str = "llama3.2:latest"
    base_url: str = "http://localhost:11434"

class FreeApiConfig(BaseModel):
    provider: str = "groq"
    api_key: str = ""
    model: str = "llama-3.3-70b-versatile"

class AiMatcherConfig(BaseModel):
    provider: str = "ollama"
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    free_api: FreeApiConfig = Field(default_factory=FreeApiConfig)
    min_match_score: int = 60

class EmailConfig(BaseModel):
    enabled: bool = False
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    sender_email: str = ""
    sender_password: str = ""
    recipient_email: str = ""

class WhatsAppConfig(BaseModel):
    enabled: bool = False
    provider: str = "callmebot"
    phone_number: str = ""
    api_key: str = ""

class TelegramConfig(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""

class NotificationChannels(BaseModel):
    email: EmailConfig = Field(default_factory=EmailConfig)
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)

class NotificationsConfig(BaseModel):
    enabled: bool = False
    channels: NotificationChannels = Field(default_factory=NotificationChannels)

class AppConfig(BaseModel):
    search: SearchConfig = Field(default_factory=SearchConfig)
    experience_filter: ExperienceFilterConfig = Field(default_factory=ExperienceFilterConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    candidate_profile: CandidateProfile = Field(default_factory=CandidateProfile)
    ai_matcher: AiMatcherConfig = Field(default_factory=AiMatcherConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)

def load_config(file_path: Path = CONFIG_FILE) -> AppConfig:
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    
    cfg = AppConfig(**data)

    # Allow environment variables to override settings (ideal for Cloud Run / Docker)
    if os.environ.get("GROQ_API_KEY"):
        cfg.ai_matcher.free_api.api_key = os.environ["GROQ_API_KEY"]
    if os.environ.get("AI_PROVIDER"):
        cfg.ai_matcher.provider = os.environ["AI_PROVIDER"]
    elif cfg.ai_matcher.free_api.api_key and cfg.ai_matcher.provider == "ollama" and os.environ.get("GROQ_API_KEY"):
        cfg.ai_matcher.provider = "free_api"

    return cfg
