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
import smtplib
import traceback
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import anthropic

# ── Configuration ────────────────────────────────────────────────────────────

RECIPIENT     = "max.corfield@stages.co.uk"
SENDER        = os.environ.get("BRIEFING_FROM_EMAIL", "briefing@stages.co.uk")
SMTP_HOST     = os.environ.get("SMTP_HOST", "localhost")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "25"))
SMTP_USER     = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_TLS      = os.environ.get("SMTP_TLS", "").lower() in ("1", "true", "yes")

UK_TZ = ZoneInfo("Europe/London")

# ── Claude client ─────────────────────────────────────────────────────────────

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ── Research prompts ──────────────────────────────────────────────────────────

def build_section_1_prompt(date_str: str) -> str:
    return f"""Today is {date_str}. You are researching the morning briefing for Max Corfield, CEO of Serious Stages (staging company for outdoor festivals/concerts) and Serious International / Longcross Studios (film).

SECTION 1 — BUSINESS & ECONOMICS UPDATE

Search for the very latest news (today or yesterday) on each of the following. For each item include:
- The key headline / figure
- A 2-3 sentence summary of what happened and why it matters
- A direct link to the source article

Items to research:
1. Major global stock market movements: FTSE 100, S&P 500, Dow Jones, NASDAQ, DAX (% moves, direction, key drivers)
2. Gold price (current spot price USD/oz and any notable moves)
3. Oil price (Brent Crude USD/barrel and WTI, key drivers)
4. Bitcoin price (current USD price, 24h change, key narrative)
5. Key geopolitical events that may impact global economics and world growth — with particular focus on:
   - UK economic news (interest rates, trade, sterling, government policy)
   - US economic news (Fed, tariffs, trade policy, key economic data)
   - Any major global events (wars, sanctions, energy supply, trade disputes) affecting markets

Be specific with numbers. Include source links to Reuters, Bloomberg, FT, BBC Business, CNBC, or similar reputable financial news sources. Format your response as clean HTML for an email (use <h3> for sub-headings, <p> for text, <a href="..."> for links, <strong> for key figures)."""


def build_section_2_prompt(date_str: str) -> str:
    return f"""Today is {date_str}. You are researching the morning briefing for Max Corfield, CEO of Serious Stages — a UK company that builds stages for outdoor festivals and concerts (www.stages.co.uk).

SECTION 2 — UK EVENTS INDUSTRY UPDATE (Live Music Focus)

Search for the very latest news on each of the following. For each item include a 2-3 sentence summary and a direct link to the source.

1. MAJOR CLIENTS — what are these organisations doing right now?
   - Live Nation (UK/Europe): any new events, venue announcements, financial news, policy changes
   - Glastonbury Festival: lineup news, ticket news, infrastructure, contracts
   - Other major UK festival promoters: AEG, SJM, DF Concerts, Festival Republic

2. KEY COMPETITORS — what are these staging/production companies doing?
   - ES Global Ltd (staging company)
   - Star Events Live (staging/production)
   - Acorn Events (staging)
   - Any other major UK staging/outdoor production companies

3. ARTIST TOUR ANNOUNCEMENTS — who is announcing UK, European, or global tours?
   Search for: major artist UK tour announcements, stadium tours announced, arena tours UK 2024/2025/2026, festival headliner announcements

4. TICKET SALES — how are UK live events performing commercially?
   - Any reports on UK ticket sales performance
   - Sell-out shows, struggling tours, pricing news
   - Industry confidence / economic pressures on live events

5. UK LIVE MUSIC INDUSTRY NEWS — search these specific trade publications:
   - Access All Areas magazine (accessaa.co.uk) — any latest stories
   - TPI Magazine (tpimagazine.com) — any latest stories
   - LIVE (liveuk.com) — any latest stories
   - IQ Magazine — any latest stories
   - Music Week — any latest stories
   - Any other relevant trade press

Format your response as clean HTML for an email (use <h3> for sub-headings, <p> for text, <a href="..."> for links, <strong> for key names)."""


def build_section_3_prompt(date_str: str) -> str:
    return f"""Today is {date_str}. You are researching the morning briefing for Max Corfield, who runs:
- Serious International (film production/services)
- Longcross Studios (www.lxss.co.uk) — a major UK film studio near London

SECTION 3 — FILM INDUSTRY UPDATE

Search for the very latest news on each of the following. For each item include a 2-3 sentence summary and a direct link to the source.

1. UK FILM INDUSTRY NEWS
   - What is happening at UK film studios (Pinewood, Shepperton, Longcross, Leavesden etc)
   - UK film production news — what major productions are filming or announced
   - UK film tax relief / government policy news affecting production
   - British Film Institute (BFI) news

2. US / HOLLYWOOD NEWS (where most decisions are made)
   - Major studio announcements (Disney, Warner Bros, Universal, Netflix, Amazon, Apple TV+, Paramount, Sony)
   - Streaming service news affecting film production decisions
   - Box office performance (this week's results and what it means for the industry)
   - Major production greenlight/cancellation/delay news
   - Strike/union news (SAG-AFTRA, WGA, IATSE, Teamsters)
   - Any major mergers, acquisitions, or deals in Hollywood

3. GLOBAL FILM MARKET
   - International box office news
   - Major foreign film markets news (China, India, Europe)
   - Any major festival news (Cannes, Venice, Berlin, Sundance) if relevant

4. TECHNOLOGY & INNOVATION
   - AI in film production news
   - Virtual production / LED volume technology news (relevant to Longcross Studios)
   - Any major tech affecting how films are made

Search these specific trade publications:
   - The Hollywood Reporter (hollywoodreporter.com)
   - Variety (variety.com)
   - Deadline Hollywood (deadline.com)
   - Screen International (screendaily.com)
   - The Guardian Film (theguardian.com/film)
   - Reuters Entertainment
   - BBC Culture / Film

Format your response as clean HTML for an email (use <h3> for sub-headings, <p> for text, <a href="..."> for links, <strong> for key names/titles)."""


# ── Claude web-search query ───────────────────────────────────────────────────

def research_section(prompt: str, section_name: str) -> str:
    """Use Claude with web search to research a section and return HTML."""
    print(f"  Researching {section_name}...", flush=True)
    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            tools=[
                {"type": "web_search_20260209", "name": "web_search"},
            ],
            messages=[{"role": "user", "content": prompt}],
        )
        # Extract text content from response
        html_parts = []
        for block in response.content:
            if block.type == "text":
                html_parts.append(block.text)
        return "\n".join(html_parts).strip()
    except Exception as e:
        print(f"  ERROR in {section_name}: {e}", flush=True)
        return f"<p><em>Unable to retrieve {section_name} at this time. Error: {e}</em></p>"


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

    # Plain text fallback
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
            pass  # server doesn't support STARTTLS — continue without

    if SMTP_USER and SMTP_PASSWORD:
        server.login(SMTP_USER, SMTP_PASSWORD)

    server.sendmail(SENDER, [RECIPIENT], msg.as_string())
    server.quit()
    print(f"  Email sent to {RECIPIENT}", flush=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    now_uk   = datetime.now(UK_TZ)
    date_str = now_uk.strftime("%A %d %B %Y")   # e.g. "Friday 04 April 2025"
    subject  = f"Morning Briefing — {date_str}"

    print(f"=== Morning Briefing: {date_str} ===", flush=True)

    s1 = research_section(build_section_1_prompt(date_str), "Section 1: Economics")
    s2 = research_section(build_section_2_prompt(date_str), "Section 2: Events")
    s3 = research_section(build_section_3_prompt(date_str), "Section 3: Film")

    print("  Building email...", flush=True)
    html = build_email_html(date_str, s1, s2, s3)

    # Save a local copy for debugging / preview
    preview_path = "/home/user/New/briefing_preview.html"
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Preview saved: {preview_path}", flush=True)

    print("  Sending email...", flush=True)
    try:
        send_email(subject, html)
    except Exception as e:
        print(f"  EMAIL SEND FAILED: {e}", flush=True)
        print("  (HTML preview still saved — configure SMTP env vars to enable sending)", flush=True)
        traceback.print_exc()

    print("=== Done ===", flush=True)


if __name__ == "__main__":
    main()
