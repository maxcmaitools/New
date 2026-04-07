#!/usr/bin/env python3
"""
Morning Briefing Email — max.corfield@stages.co.uk
Sections:
  1. Business & Economics (markets, gold, oil, bitcoin, geopolitics)
  2. UK Events / Live Music (Stages clients, competitors, tours, tickets)
  3. Film Industry (UK & global, Serious International / Longcross Studios)
"""

import os
import sys
import time
import smtplib
import traceback
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import anthropic

# ── Configuration ────────────────────────────────────────────────────────────

RECIPIENT     = "max.corfield@stages.co.uk"
SMTP_HOST     = os.environ.get("SMTP_HOST", "").strip()
SMTP_USER     = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
SMTP_TLS      = os.environ.get("SMTP_TLS", "").strip().lower() in ("1", "true", "yes")
_port_str     = os.environ.get("SMTP_PORT", "").strip()
SMTP_PORT     = int(_port_str) if _port_str else (465 if SMTP_TLS else 587)
SENDER        = os.environ.get("BRIEFING_FROM_EMAIL", "").strip() or SMTP_USER

UK_TZ = ZoneInfo("Europe/London")

# ── Claude client ─────────────────────────────────────────────────────────────

def _make_client() -> anthropic.Anthropic:
    token = os.environ.get("ANTHROPIC_API_KEY", "")
    if not token:
        for path in [
            "/home/claude/.claude/remote/.oauth_token",
            "/root/.claude/remote/.oauth_token",
        ]:
            try:
                with open(path) as f:
                    token = f.read().strip()
                if token:
                    break
            except Exception:
                pass
    if not token:
        raise RuntimeError("No Anthropic API key found. Set ANTHROPIC_API_KEY.")
    if token.startswith(("sk-ant-oat", "sk-ant-si-")):
        return anthropic.Anthropic(auth_token=token)
    return anthropic.Anthropic(api_key=token)

client = _make_client()

# ── Research prompts ──────────────────────────────────────────────────────────

def build_section_1_prompt(date_str: str) -> str:
    return f"""Today is {date_str}. Research today's financial markets and economic news for a CEO briefing.

Use web search to find TODAY's data on:
1. Stock markets: FTSE 100, S&P 500, NASDAQ, DAX — current level and % change
2. Commodities: Gold price (USD/oz) and Brent Crude oil (USD/barrel)
3. Bitcoin price in USD today
4. The 2 most important UK or US economic/geopolitical headlines moving markets today

For each: the key number/headline, one sentence of context, and the source URL.
Keep it factual and brief."""


def build_section_2_prompt(date_str: str) -> str:
    return f"""Today is {date_str}. Research UK live events industry news for a CEO briefing. The CEO runs Serious Stages, a UK staging company for outdoor festivals (stages.co.uk).

Use web search to find:
1. Any news about Live Nation UK, Glastonbury Festival, or major UK festival promoters (AEG, SJM, Festival Republic) this week
2. Any news about UK staging/production companies: ES Global, Star Events, Acorn Events
3. The biggest UK or European artist tour announcement or ticket sales story this week

For each: a 2-sentence summary and the source URL. Use trade sources: Access All Areas (accessaa.co.uk), TPI Magazine (tpimagazine.com), Music Week, NME, Billboard, Guardian Music."""


def build_section_3_prompt(date_str: str) -> str:
    return f"""Today is {date_str}. Research film industry news for a CEO briefing. The CEO runs Longcross Studios (lxss.co.uk) near London and Serious International.

Use web search to find:
1. The biggest UK film studio or production news this week (Pinewood, Shepperton, Longcross, or Leavesden — what's filming, announced, or happening)
2. The biggest Hollywood story today (Disney, Netflix, Warner Bros, Universal etc — greenlight, merger, box office, or deal)
3. Any virtual production or LED volume technology news relevant to UK studios

For each: a 2-sentence summary and the source URL. Use: Hollywood Reporter, Variety, Deadline, Screen International, Broadcast."""


# ── Two-step research: gather facts, then format as HTML ──────────────────────

def _gather_facts(prompt: str, section_name: str) -> str:
    """Step 1: web search to gather raw facts. Returns text (markdown is fine here)."""
    print(f"  Researching {section_name}...", flush=True)
    delays = [0, 120, 180, 240]
    for attempt, delay in enumerate(delays):
        if delay:
            print(f"  Rate limited — waiting {delay}s before retry {attempt}/{len(delays)-1}...", flush=True)
            time.sleep(delay)
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=(
                    "You are a research assistant. Use web_search to find current facts. "
                    "Use the tool a maximum of 3 times. "
                    "Report findings as clear bullet points with exact source URLs."
                ),
                tools=[{"type": "web_search_20260209", "name": "web_search"}],
                messages=[{"role": "user", "content": prompt}],
            )
            text_blocks = [b.text for b in response.content if b.type == "text"]
            if not text_blocks:
                return ""
            result = max(text_blocks, key=len).strip()
            print(f"  Facts gathered for {section_name} ({len(result)} chars)", flush=True)
            return result
        except anthropic.RateLimitError:
            if attempt < len(delays) - 1:
                continue
            msg = f"Rate limit: {section_name} failed after {len(delays)} attempts"
            print(f"::error::{msg}", flush=True)
            return ""
        except anthropic.AuthenticationError as e:
            print(f"::error::API key rejected ({e}) — check ANTHROPIC_API_KEY secret", flush=True)
            sys.exit(1)
        except Exception as e:
            print(f"::error::{section_name} research error: {type(e).__name__}: {e}", flush=True)
            return ""
    return ""


def _format_as_html(raw_facts: str, section_name: str) -> str:
    """Step 2: convert raw facts to clean HTML. No web search — output is always clean."""
    if not raw_facts:
        return f"<p><em>No data available for {section_name} today.</em></p>"

    print(f"  Formatting {section_name} as HTML...", flush=True)
    format_prompt = f"""Convert the following research notes into a clean HTML section for an email briefing.

RESEARCH NOTES:
{raw_facts}

OUTPUT REQUIREMENTS:
- Output ONLY valid HTML — begin immediately with a <h3> tag, nothing before it
- Use <h3> for each topic heading
- Use <p> for paragraph text
- Use <strong> for key numbers, names, and figures
- Use <a href="URL">Source Name</a> for all source links (put at end of each paragraph)
- Do NOT use: markdown, emoji, --- separators, bullet points with - or *, asterisks for bold
- Aim for 3–5 topics, each with one <h3> and one or two <p> tags
- Be factual and concise"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system="You are an HTML email formatter. Output ONLY valid HTML. The very first character of your response must be '<'. No markdown, no emoji, no preamble.",
            messages=[{"role": "user", "content": format_prompt}],
        )
        text_blocks = [b.text for b in response.content if b.type == "text"]
        if not text_blocks:
            return f"<p><em>Formatting failed for {section_name}.</em></p>"
        result = max(text_blocks, key=len).strip()
        # Safety: strip any text before the first HTML tag
        import re
        match = re.search(r'<[a-zA-Z]', result)
        if match and match.start() > 0:
            result = result[match.start():]
        print(f"  Formatted {section_name} ({len(result)} chars)", flush=True)
        return result
    except Exception as e:
        print(f"::error::Format step failed for {section_name}: {e}", flush=True)
        # Fallback: wrap raw facts in a preformatted block
        escaped = raw_facts.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<p><em>Formatting error — raw notes below:</em></p><pre style='font-size:13px;white-space:pre-wrap'>{escaped[:2000]}</pre>"


def research_section(prompt: str, section_name: str) -> str:
    """Two-step: gather facts with web search, then format as clean HTML."""
    facts = _gather_facts(prompt, section_name)
    return _format_as_html(facts, section_name)


# ── Email assembly ────────────────────────────────────────────────────────────

EMAIL_CSS = """
<style>
  body { font-family: Georgia, 'Times New Roman', serif; background: #f5f5f0; margin: 0; padding: 0; }
  .wrapper { max-width: 720px; margin: 0 auto; background: #ffffff; }
  .header { background: #1a1a2e; color: #ffffff; padding: 28px 32px; }
  .header h1 { margin: 0 0 4px 0; font-size: 22px; letter-spacing: 1px; color: #e8d5b0; }
  .header .date { margin: 0; font-size: 14px; color: #aaaaaa; }
  .section { padding: 24px 32px; border-bottom: 2px solid #f0ece0; }
  .section-label {
    display: inline-block; padding: 4px 12px; border-radius: 3px;
    font-size: 11px; font-weight: bold; letter-spacing: 1.5px; text-transform: uppercase;
    margin-bottom: 16px;
  }
  .label-economics { background: #1a3a5c; color: #ffffff; }
  .label-events    { background: #2d6a2d; color: #ffffff; }
  .label-film      { background: #5c1a3a; color: #ffffff; }
  .section h2 { margin: 0 0 16px 0; font-size: 20px; color: #1a1a2e; border-bottom: 1px solid #e0ddd0; padding-bottom: 8px; }
  .section h3 { font-size: 16px; color: #2c2c4a; margin: 20px 0 8px 0; }
  .section p  { margin: 0 0 12px 0; font-size: 15px; line-height: 1.65; color: #333333; }
  .section a  { color: #1a5276; text-decoration: underline; }
  .section strong { color: #1a1a2e; }
  .footer { background: #f0ece0; padding: 20px 32px; text-align: center; }
  .footer p { margin: 0; font-size: 12px; color: #888888; }
</style>
"""

def build_email_html(date_str: str, s1: str, s2: str, s3: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Morning Briefing — {date_str}</title>
  {EMAIL_CSS}
</head>
<body>
<div class="wrapper">

  <div class="header">
    <h1>Morning Briefing</h1>
    <p class="date">{date_str}</p>
  </div>

  <div class="section">
    <span class="section-label label-economics">Section 1</span>
    <h2>Business &amp; Economics</h2>
    {s1}
  </div>

  <div class="section">
    <span class="section-label label-events">Section 2</span>
    <h2>UK Events Industry &amp; Live Music</h2>
    {s2}
  </div>

  <div class="section">
    <span class="section-label label-film">Section 3</span>
    <h2>Film Industry</h2>
    {s3}
  </div>

  <div class="footer">
    <p>Morning Briefing for Max Corfield &mdash; Serious Stages &amp; Serious International<br>
    Generated automatically at 08:00 UK time &bull; <a href="https://www.stages.co.uk">stages.co.uk</a> &bull; <a href="https://www.lxss.co.uk">lxss.co.uk</a></p>
  </div>

</div>
</body>
</html>"""


# ── Email sending ─────────────────────────────────────────────────────────────

def send_email(subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER
    msg["To"]      = RECIPIENT

    plain = f"Morning Briefing — {subject}\n\nPlease view this email in an HTML-capable email client."
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    if SMTP_TLS:
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
    else:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        try:
            server.starttls()
        except smtplib.SMTPException:
            pass

    if SMTP_USER and SMTP_PASSWORD:
        server.login(SMTP_USER, SMTP_PASSWORD)

    server.sendmail(SENDER, [RECIPIENT], msg.as_string())
    server.quit()
    print(f"  Email sent to {RECIPIENT}", flush=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    now_uk   = datetime.now(UK_TZ)
    date_str = now_uk.strftime("%A %d %B %Y")
    subject  = f"Morning Briefing — {date_str}"

    print(f"=== Morning Briefing: {date_str} ===", flush=True)

    s1 = research_section(build_section_1_prompt(date_str), "Section 1: Economics")
    print("  Waiting 3 minutes between sections (API rate limit)...", flush=True)
    time.sleep(180)
    s2 = research_section(build_section_2_prompt(date_str), "Section 2: Events")
    print("  Waiting 3 minutes between sections (API rate limit)...", flush=True)
    time.sleep(180)
    s3 = research_section(build_section_3_prompt(date_str), "Section 3: Film")

    print("  Building email...", flush=True)
    html = build_email_html(date_str, s1, s2, s3)

    preview_path = "briefing_preview.html"
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Preview saved: {preview_path}", flush=True)

    print("  Sending email...", flush=True)
    try:
        send_email(subject, html)
        print("=== Done — email sent successfully ===", flush=True)
    except smtplib.SMTPAuthenticationError as e:
        msg = f"SMTP login failed for {SMTP_USER}@{SMTP_HOST} — Gmail needs an App Password. Error: {e}"
        print(f"::error::{msg}", flush=True)
        traceback.print_exc()
        sys.exit(1)
    except smtplib.SMTPException as e:
        msg = f"SMTP error sending to {SMTP_HOST}:{SMTP_PORT} (TLS={SMTP_TLS}): {e}"
        print(f"::error::{msg}", flush=True)
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        msg = f"Email send failed: {type(e).__name__}: {e}"
        print(f"::error::{msg}", flush=True)
        traceback.print_exc()
        sys.exit(1)


def gha_error(msg: str) -> None:
    print(f"::error::{msg.replace(chr(10), ' | ')}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        gha_error(f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        sys.exit(1)
