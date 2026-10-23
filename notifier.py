import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List
import requests
from rich.console import Console

from config import NotificationsConfig
from models import JobPost

console = Console()
logger = logging.getLogger("ai_job_searcher.notifier")

def format_text_digest(jobs: List[JobPost], top_n: int = 5) -> str:
    """Format a compact text digest of top matched jobs."""
    top_jobs = jobs[:top_n]
    if not top_jobs:
        return "No matching jobs found in the last 24 hours."

    lines = [f"🎯 AI Job Searcher: Top {len(top_jobs)} Fresh Matches\n"]
    for i, job in enumerate(top_jobs, 1):
        score = job.match_analysis.match_score if job.match_analysis else 0
        lines.append(f"{i}. *{job.title}* at *{job.company}* ({score}% match)")
        lines.append(f"   📍 {job.location} | Portal: {job.site.capitalize()}")
        if job.match_analysis and job.match_analysis.summary_reason:
            lines.append(f"   💡 {job.match_analysis.summary_reason}")
        lines.append(f"   🔗 Apply: {job.job_url}\n")
    return "\n".join(lines)

def send_email_alert(jobs: List[JobPost], cfg: NotificationsConfig) -> bool:
    """Send an HTML email digest via SMTP."""
    email_cfg = cfg.channels.email
    if not email_cfg.enabled or not email_cfg.sender_email or not email_cfg.recipient_email:
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🎯 AI Job Matches ({len(jobs)} found in last 24h)"
        msg["From"] = email_cfg.sender_email
        msg["To"] = email_cfg.recipient_email

        # Plaintext fallback
        text_content = format_text_digest(jobs, top_n=10)
        part1 = MIMEText(text_content, "plain")
        msg.attach(part1)

        # Connect to SMTP
        server = smtplib.SMTP(email_cfg.smtp_server, email_cfg.smtp_port)
        server.starttls()
        server.login(email_cfg.sender_email, email_cfg.sender_password)
        server.sendmail(email_cfg.sender_email, email_cfg.recipient_email, msg.as_string())
        server.quit()

        console.print(f"[green]✓ Email digest sent to {email_cfg.recipient_email}[/green]")
        return True
    except Exception as e:
        console.print(f"[red]✕ Failed to send email: {e}[/red]")
        logger.error(f"Email notification error: {e}")
        return False

def send_whatsapp_alert(jobs: List[JobPost], cfg: NotificationsConfig) -> bool:
    """Send WhatsApp message using CallMeBot free API or Twilio."""
    wa_cfg = cfg.channels.whatsapp
    if not wa_cfg.enabled:
        return False

    message_text = format_text_digest(jobs, top_n=5)

    if wa_cfg.provider == "callmebot":
        # Free CallMeBot API (https://www.callmebot.com/)
        if not wa_cfg.phone_number or not wa_cfg.api_key:
            console.print("[yellow]WhatsApp skipped: Phone number or API key missing.[/yellow]")
            return False
        try:
            url = f"https://api.callmebot.com/whatsapp.php?phone={wa_cfg.phone_number}&text={requests.utils.quote(message_text)}&apikey={wa_cfg.api_key}"
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
                console.print(f"[green]✓ WhatsApp message sent to {wa_cfg.phone_number}[/green]")
                return True
            else:
                console.print(f"[red]✕ WhatsApp sending failed with status {res.status_code}[/red]")
                return False
        except Exception as e:
            console.print(f"[red]✕ WhatsApp error: {e}[/red]")
            return False

    return False

def send_telegram_alert(jobs: List[JobPost], cfg: NotificationsConfig) -> bool:
    """Send free Telegram alert via bot."""
    tg_cfg = cfg.channels.telegram
    if not tg_cfg.enabled or not tg_cfg.bot_token or not tg_cfg.chat_id:
        return False

    try:
        message_text = format_text_digest(jobs, top_n=5)
        url = f"https://api.telegram.org/bot{tg_cfg.bot_token}/sendMessage"
        payload = {
            "chat_id": tg_cfg.chat_id,
            "text": message_text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            console.print(f"[green]✓ Telegram notification sent successfully[/green]")
            return True
        else:
            console.print(f"[red]✕ Telegram failed: {res.text}[/red]")
            return False
    except Exception as e:
        console.print(f"[red]✕ Telegram error: {e}[/red]")
        return False

def dispatch_all_notifications(jobs: List[JobPost], cfg: NotificationsConfig):
    """Dispatches notifications across all enabled channels."""
    if not cfg.enabled:
        return

    console.print("\n[bold cyan]📬 Dispatching notifications...[/bold cyan]")
    if cfg.channels.email.enabled:
        send_email_alert(jobs, cfg)
    if cfg.channels.whatsapp.enabled:
        send_whatsapp_alert(jobs, cfg)
    if cfg.channels.telegram.enabled:
        send_telegram_alert(jobs, cfg)
