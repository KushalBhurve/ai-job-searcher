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
    model: str = "openai/gpt-oss-120b"

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
    notify_on_analysis: bool = True
    min_score: int = 60
    channels: NotificationChannels = Field(default_factory=NotificationChannels)

class AppConfig(BaseModel):
    search: SearchConfig = Field(default_factory=SearchConfig)
    experience_filter: ExperienceFilterConfig = Field(default_factory=ExperienceFilterConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    candidate_profile: CandidateProfile = Field(default_factory=CandidateProfile)
    ai_matcher: AiMatcherConfig = Field(default_factory=AiMatcherConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)

def _load_dotenv(env_path: Path):
    """Simple, zero-dependency .env reader."""
    if not env_path.exists():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass

def load_config(file_path: Path = CONFIG_FILE) -> AppConfig:
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {file_path}")
    
    # Auto-load local .env if present
    _load_dotenv(file_path.parent / ".env")

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    
    cfg = AppConfig(**data)

    # AI overrides from environment variables
    if os.environ.get("GROQ_API_KEY"):
        cfg.ai_matcher.free_api.api_key = os.environ["GROQ_API_KEY"]
    if os.environ.get("GROQ_MODEL"):
        cfg.ai_matcher.free_api.model = os.environ["GROQ_MODEL"]
    if os.environ.get("AI_PROVIDER"):
        cfg.ai_matcher.provider = os.environ["AI_PROVIDER"]
    elif cfg.ai_matcher.free_api.api_key and cfg.ai_matcher.provider == "ollama" and os.environ.get("GROQ_API_KEY"):
        cfg.ai_matcher.provider = "free_api"

    # Notification overrides from environment variables
    if os.environ.get("NOTIFICATIONS_ENABLED"):
        cfg.notifications.enabled = os.environ["NOTIFICATIONS_ENABLED"].lower() in ("1", "true", "yes")
    if os.environ.get("NOTIFICATION_MIN_SCORE"):
        try:
            cfg.notifications.min_score = int(os.environ["NOTIFICATION_MIN_SCORE"])
        except ValueError:
            pass

    # Email overrides
    if os.environ.get("GMAIL_SENDER") or os.environ.get("SENDER_EMAIL"):
        cfg.notifications.channels.email.sender_email = os.environ.get("GMAIL_SENDER") or os.environ.get("SENDER_EMAIL", "")
    if os.environ.get("GMAIL_APP_PASSWORD") or os.environ.get("SENDER_PASSWORD"):
        cfg.notifications.channels.email.sender_password = os.environ.get("GMAIL_APP_PASSWORD") or os.environ.get("SENDER_PASSWORD", "")
    if os.environ.get("RECIPIENT_EMAIL"):
        cfg.notifications.channels.email.recipient_email = os.environ["RECIPIENT_EMAIL"]
    if os.environ.get("EMAIL_ENABLED"):
        cfg.notifications.channels.email.enabled = os.environ["EMAIL_ENABLED"].lower() in ("1", "true", "yes")
    elif cfg.notifications.channels.email.sender_email and cfg.notifications.channels.email.sender_password and cfg.notifications.channels.email.recipient_email:
        cfg.notifications.channels.email.enabled = True

    # WhatsApp overrides
    if os.environ.get("CALLMEBOT_PHONE") or os.environ.get("WHATSAPP_PHONE"):
        cfg.notifications.channels.whatsapp.phone_number = os.environ.get("CALLMEBOT_PHONE") or os.environ.get("WHATSAPP_PHONE", "")
    if os.environ.get("CALLMEBOT_API_KEY") or os.environ.get("WHATSAPP_API_KEY"):
        cfg.notifications.channels.whatsapp.api_key = os.environ.get("CALLMEBOT_API_KEY") or os.environ.get("WHATSAPP_API_KEY", "")
    if os.environ.get("WHATSAPP_ENABLED"):
        cfg.notifications.channels.whatsapp.enabled = os.environ["WHATSAPP_ENABLED"].lower() in ("1", "true", "yes")
    elif cfg.notifications.channels.whatsapp.phone_number and cfg.notifications.channels.whatsapp.api_key:
        cfg.notifications.channels.whatsapp.enabled = True

    # Telegram overrides
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        cfg.notifications.channels.telegram.bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    if os.environ.get("TELEGRAM_CHAT_ID"):
        cfg.notifications.channels.telegram.chat_id = os.environ["TELEGRAM_CHAT_ID"]
    if os.environ.get("TELEGRAM_ENABLED"):
        cfg.notifications.channels.telegram.enabled = os.environ["TELEGRAM_ENABLED"].lower() in ("1", "true", "yes")
    elif cfg.notifications.channels.telegram.bot_token and cfg.notifications.channels.telegram.chat_id:
        cfg.notifications.channels.telegram.enabled = True

    # Automatically set notifications.enabled = True if any channel is enabled
    if (cfg.notifications.channels.whatsapp.enabled or 
        cfg.notifications.channels.email.enabled or 
        cfg.notifications.channels.telegram.enabled):
        cfg.notifications.enabled = True

    return cfg
