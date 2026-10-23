import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional
import requests
from rich.console import Console

from config import NotificationsConfig
from models import JobPost, MatchAnalysis
import db

console = Console(highlight=False)
logger = logging.getLogger("ai_job_searcher.notifier")

# ==============================================================================
# Single-Job Match Notifications (Instant Deep Analysis Alerts)
# ==============================================================================

def format_whatsapp_job_message(job: JobPost, analysis: MatchAnalysis) -> str:
    """Format an attractive, high-signal WhatsApp alert for a single job."""
    score = analysis.match_score
    skills_text = ", ".join(analysis.key_matching_skills[:5]) if analysis.key_matching_skills else "Strong overall profile fit"

    # Truncate JD cleanly to ensure URL limits for CallMeBot GET requests are not exceeded
    jd_snippet = ""
    if job.description:
        clean_desc = " ".join(job.description.split())
        if len(clean_desc) > 650:
            jd_snippet = clean_desc[:650] + "..."
        else:
            jd_snippet = clean_desc

    lines = [
        f"🎯 *High Match Job Alert ({score}%)*",
        f"",
        f"💼 *Role:* {job.title}",
        f"🏢 *Company:* {job.company}",
        f"📍 *Location:* {job.location} ({job.site.upper()})",
    ]
    if job.salary:
        lines.append(f"💰 *Salary:* {job.salary}")

    lines.extend([
        f"",
        f"💡 *Why You Match:*",
        f"{analysis.summary_reason or 'High alignment with your skills and background.'}",
        f"",
        f"✅ *Key Skills:* {skills_text}",
        f"",
        f"🔗 *Apply Here:*",
        f"{job.job_url}",
    ])

    if jd_snippet:
        lines.extend([
            f"",
            f"📋 *JD Preview:*",
            f"{jd_snippet}",
        ])

    return "\n".join(lines)


def format_html_job_email(job: JobPost, analysis: MatchAnalysis) -> str:
    """Format an elegant HTML email for a single job match with full JD and 1-click apply."""
    score = analysis.match_score
    score_color = "#10b981" if score >= 75 else "#3b82f6" if score >= 60 else "#f59e0b"

    matching_skills_html = "".join([
        f'<span style="display:inline-block;background:#e0f2fe;color:#0369a1;padding:4px 10px;border-radius:12px;font-size:13px;margin:3px;">✓ {s}</span>'
        for s in analysis.key_matching_skills
    ]) or "<span>General profile alignment</span>"

    missing_skills_html = "".join([
        f'<span style="display:inline-block;background:#fee2e2;color:#b91c1c;padding:4px 10px;border-radius:12px;font-size:13px;margin:3px;">! {s}</span>'
        for s in analysis.missing_skills_or_gaps
    ])

    # Convert linebreaks and special chars in description safely
    description_formatted = (job.description or "No description provided.").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #334155; margin: 0; padding: 24px 12px; }}
    .card {{ max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 14px; box-shadow: 0 10px 25px rgba(0,0,0,0.15); border: 1px solid #e2e8f0; overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 28px 24px; color: #ffffff; text-align: left; }}
    .badge {{ display: inline-block; background: {score_color}; color: #ffffff; padding: 6px 14px; border-radius: 20px; font-weight: 700; font-size: 14px; margin-bottom: 12px; }}
    .content {{ padding: 28px 24px; }}
    .role-title {{ font-size: 22px; font-weight: 700; color: #0f172a; margin-top: 0; margin-bottom: 6px; }}
    .meta {{ color: #64748b; font-size: 14px; margin-bottom: 20px; }}
    .reason-box {{ background: #f0fdf4; border-left: 4px solid #22c55e; padding: 14px 18px; border-radius: 6px; margin: 20px 0; font-size: 14px; color: #166534; line-height: 1.5; }}
    .btn {{ display: inline-block; background: #2563eb; color: #ffffff !important; padding: 12px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px; text-align: center; margin: 15px 0; }}
    .section-title {{ font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #475569; margin-top: 24px; margin-bottom: 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }}
    .jd-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; font-size: 13px; line-height: 1.6; color: #334155; white-space: pre-wrap; word-break: break-word; max-height: 400px; overflow-y: auto; }}
    .footer {{ background: #f8fafc; padding: 16px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="badge">🎯 {score}% Match • {analysis.decision}</div>
      <div style="font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px;">AI Job Searcher Radar</div>
    </div>
    <div class="content">
      <h1 class="role-title">{job.title}</h1>
      <div class="meta">
        🏢 <strong>{job.company}</strong> &nbsp;|&nbsp; 📍 {job.location} &nbsp;|&nbsp; 🌐 {job.site.capitalize()}
        {f' &nbsp;|&nbsp; 💰 {job.salary}' if job.salary else ''}
      </div>

      <div style="text-align: center; margin: 20px 0;">
        <a href="{job.job_url}" target="_blank" class="btn">👉 Apply on {job.site.capitalize()}</a>
      </div>

      <div class="reason-box">
        <strong>💡 AI Match Analysis:</strong><br>
        {analysis.summary_reason or 'This position aligns strongly with your technical background and experience level.'}
      </div>

      <div class="section-title">Matching Skills</div>
      <div style="margin-bottom: 14px;">{matching_skills_html}</div>

      {f'<div class="section-title">Areas to Prepare</div><div style="margin-bottom: 14px;">{missing_skills_html}</div>' if missing_skills_html else ''}

      <div class="section-title">Job Description (JD)</div>
      <div class="jd-box">{description_formatted}</div>

      <div style="text-align: center; margin-top: 24px;">
        <a href="{job.job_url}" target="_blank" class="btn">👉 Open Job Posting</a>
      </div>
    </div>
    <div class="footer">
      Sent automatically by your AI Job Searcher Radar when job match &ge; 60%.
    </div>
  </div>
</body>
</html>"""
    return html


def send_single_job_whatsapp(job: JobPost, analysis: MatchAnalysis, cfg: NotificationsConfig) -> bool:
    """Send individual job alert to WhatsApp via CallMeBot."""
    wa_cfg = cfg.channels.whatsapp
    if not wa_cfg.enabled or not wa_cfg.phone_number or not wa_cfg.api_key:
        return False

    message_text = format_whatsapp_job_message(job, analysis)

    clean_phone = wa_cfg.phone_number.strip().replace(" ", "").replace("-", "")
    if clean_phone.startswith("+"):
        clean_phone = clean_phone[1:]

    try:
        url = "https://api.callmebot.com/whatsapp.php"
        params = {
            "phone": clean_phone,
            "text": message_text,
            "apikey": wa_cfg.api_key
        }
        res = requests.get(url, params=params, timeout=15)
        if res.status_code == 200:
            console.print(f"[green]✓ WhatsApp alert sent: {job.title[:25]} at {job.company[:18]} ({analysis.match_score}% match)[/green]")
            return True
        else:
            logger.warning(f"CallMeBot WhatsApp error {res.status_code}: {res.text}")
            console.print(f"[yellow]⚠️ CallMeBot WhatsApp returned status {res.status_code}[/yellow]")
            return False
    except Exception as e:
        logger.error(f"WhatsApp sending error: {e}")
        console.print(f"[red]✕ WhatsApp error: {e}[/red]")
        return False


def send_single_job_email(job: JobPost, analysis: MatchAnalysis, cfg: NotificationsConfig) -> bool:
    """Send individual job alert with full JD via SMTP (e.g., Gmail)."""
    email_cfg = cfg.channels.email
    if not email_cfg.enabled or not email_cfg.sender_email or not email_cfg.recipient_email:
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🎯 [{analysis.match_score}% Match] {job.title} at {job.company} ({job.location})"
        msg["From"] = email_cfg.sender_email
        msg["To"] = email_cfg.recipient_email

        # Plaintext fallback
        text_content = format_whatsapp_job_message(job, analysis)
        part1 = MIMEText(text_content, "plain")
        msg.attach(part1)

        # Full HTML
        html_content = format_html_job_email(job, analysis)
        part2 = MIMEText(html_content, "html")
        msg.attach(part2)

        server = smtplib.SMTP(email_cfg.smtp_server, email_cfg.smtp_port, timeout=20)
        server.starttls()
        server.login(email_cfg.sender_email, email_cfg.sender_password)
        server.sendmail(email_cfg.sender_email, email_cfg.recipient_email, msg.as_string())
        server.quit()

        console.print(f"[green]✓ Email alert sent: {job.title[:25]} to {email_cfg.recipient_email} ({analysis.match_score}% match)[/green]")
        return True
    except Exception as e:
        console.print(f"[red]✕ Failed to send job email: {e}[/red]")
        logger.error(f"Email job notification error: {e}")
        return False


def format_telegram_job_message(job: JobPost, analysis: MatchAnalysis) -> str:
    """Format a clean HTML message for Telegram with clickable link and preview."""
    score = analysis.match_score
    skills_text = ", ".join(analysis.key_matching_skills[:5]) if analysis.key_matching_skills else "Strong overall profile fit"

    clean_title = job.title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    clean_company = job.company.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    clean_loc = job.location.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    clean_reason = (analysis.summary_reason or "High alignment with your skills and background.").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    clean_skills = skills_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    jd_snippet = ""
    if job.description:
        desc = " ".join(job.description.split())
        clean_desc = desc[:700].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        jd_snippet = clean_desc + "..." if len(desc) > 700 else clean_desc

    msg = f"🎯 <b>High Match Job Alert ({score}%)</b>\n\n"
    msg += f"💼 <b>Role:</b> {clean_title}\n"
    msg += f"🏢 <b>Company:</b> {clean_company}\n"
    msg += f"📍 <b>Location:</b> {clean_loc} ({job.site.upper()})\n"
    if job.salary:
        msg += f"💰 <b>Salary:</b> {job.salary}\n"
    msg += f"\n💡 <b>Why You Match:</b>\n{clean_reason}\n"
    msg += f"\n✅ <b>Key Skills:</b> {clean_skills}\n"
    msg += f"\n🔗 <b><a href=\"{job.job_url}\">Click Here to Apply on {job.site.capitalize()}</a></b>\n"
    if jd_snippet:
        msg += f"\n📋 <b>JD Preview:</b>\n{jd_snippet}\n"

    return msg


def send_single_job_telegram(job: JobPost, analysis: MatchAnalysis, cfg: NotificationsConfig) -> bool:
    """Send individual job alert to Telegram bot."""
    tg_cfg = cfg.channels.telegram
    if not tg_cfg.enabled or not tg_cfg.bot_token or not tg_cfg.chat_id:
        return False

    try:
        message_text = format_telegram_job_message(job, analysis)
        url = f"https://api.telegram.org/bot{tg_cfg.bot_token}/sendMessage"
        payload = {
            "chat_id": tg_cfg.chat_id,
            "text": message_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            console.print(f"[green]✓ Telegram alert sent: {job.title[:25]} ({analysis.match_score}% match)[/green]")
            return True
        else:
            logger.warning(f"Telegram API returned {res.status_code}: {res.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram alert error: {e}")
        return False


def notify_job_match(job: JobPost, analysis: MatchAnalysis, cfg: NotificationsConfig, force: bool = False) -> Dict[str, bool]:
    """
    Dispatches instant notification (WhatsApp and/or Email) for a single job
    if match_score >= min_score and the job has not already been notified.
    """
    results = {"whatsapp": False, "email": False, "telegram": False}

    if not cfg.enabled:
        return results

    if analysis.match_score < cfg.min_score:
        return results

    if not force and db.is_job_notified(job.id):
        logger.info(f"Job {job.id} already notified. Skipping alert.")
        return results

    sent_any = False

    if cfg.channels.whatsapp.enabled:
        res_wa = send_single_job_whatsapp(job, analysis, cfg)
        results["whatsapp"] = res_wa
        if res_wa:
            sent_any = True

    if cfg.channels.email.enabled:
        res_email = send_single_job_email(job, analysis, cfg)
        results["email"] = res_email
        if res_email:
            sent_any = True

    if cfg.channels.telegram.enabled:
        res_tg = send_single_job_telegram(job, analysis, cfg)
        results["telegram"] = res_tg
        if res_tg:
            sent_any = True

    if sent_any and not force:
        db.mark_job_notified(job.id)

    return results


# ==============================================================================
# Batch / Digest Notifications
# ==============================================================================

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
        server = smtplib.SMTP(email_cfg.smtp_server, email_cfg.smtp_port, timeout=20)
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
    """Send WhatsApp digest message using CallMeBot."""
    wa_cfg = cfg.channels.whatsapp
    if not wa_cfg.enabled or not wa_cfg.phone_number or not wa_cfg.api_key:
        return False

    message_text = format_text_digest(jobs, top_n=5)
    clean_phone = wa_cfg.phone_number.strip().replace(" ", "").replace("-", "")
    if clean_phone.startswith("+"):
        clean_phone = clean_phone[1:]

    try:
        url = "https://api.callmebot.com/whatsapp.php"
        params = {
            "phone": clean_phone,
            "text": message_text,
            "apikey": wa_cfg.api_key
        }
        res = requests.get(url, params=params, timeout=15)
        if res.status_code == 200:
            console.print(f"[green]✓ WhatsApp digest sent to {clean_phone}[/green]")
            return True
        else:
            console.print(f"[red]✕ WhatsApp sending failed with status {res.status_code}[/red]")
            return False
    except Exception as e:
        console.print(f"[red]✕ WhatsApp error: {e}[/red]")
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
