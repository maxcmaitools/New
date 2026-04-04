#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# Morning Briefing Setup — Serious Stages / Serious International
# Schedules morning_briefing.py to run at 08:00 UK time each day.
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIEFING_SCRIPT="$SCRIPT_DIR/morning_briefing.py"
LOG_FILE="$SCRIPT_DIR/briefing.log"
ENV_FILE="$SCRIPT_DIR/.env"

echo "=== Morning Briefing Scheduler Setup ==="
echo ""

# ── Check ANTHROPIC_API_KEY ────────────────────────────────────────────────
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "ERROR: ANTHROPIC_API_KEY is not set."
    echo ""
    echo "Create $ENV_FILE with your configuration:"
    cat <<'ENVEXAMPLE'
ANTHROPIC_API_KEY=sk-ant-...

# Email sending (choose one of the options below)
# --- Option A: Gmail / Google Workspace ---
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_TLS=true
SMTP_USER=your-gmail@gmail.com
SMTP_PASSWORD=your-app-password          # Use an App Password, not your Google password
BRIEFING_FROM_EMAIL=your-gmail@gmail.com

# --- Option B: Microsoft 365 / Outlook ---
# SMTP_HOST=smtp.office365.com
# SMTP_PORT=587
# SMTP_TLS=false
# SMTP_USER=you@stages.co.uk
# SMTP_PASSWORD=your-password
# BRIEFING_FROM_EMAIL=you@stages.co.uk

# --- Option C: SendGrid / Mailgun / Postmark ---
# SMTP_HOST=smtp.sendgrid.net
# SMTP_PORT=465
# SMTP_TLS=true
# SMTP_USER=apikey
# SMTP_PASSWORD=your-sendgrid-api-key
# BRIEFING_FROM_EMAIL=briefing@stages.co.uk
ENVEXAMPLE
    exit 1
fi

echo "✓ ANTHROPIC_API_KEY found"

# ── Build cron command ─────────────────────────────────────────────────────
# We use TZ=Europe/London in the cron line so 08:00 is always UK time
# (handles both GMT in winter and BST in summer automatically).

CRON_ENV=""
if [ -f "$ENV_FILE" ]; then
    CRON_ENV="source $ENV_FILE && "
fi

CRON_CMD="TZ=Europe/London 0 8 * * * $CRON_ENV python3 $BRIEFING_SCRIPT >> $LOG_FILE 2>&1"

echo ""
echo "Installing cron job: 08:00 UK time every day"
echo "  $CRON_CMD"
echo ""

# Remove any previous version of this job, then add the new one
(crontab -l 2>/dev/null | grep -v "morning_briefing.py" || true; echo "$CRON_CMD") | crontab -

echo "✓ Cron job installed"
echo ""
crontab -l | grep morning_briefing || true
echo ""

# ── Offer a test run ──────────────────────────────────────────────────────
echo "=== Setup Complete ==="
echo ""
echo "The briefing will be emailed to max.corfield@stages.co.uk at 08:00 UK time."
echo ""
echo "To run a test NOW:"
echo "  cd $SCRIPT_DIR && python3 morning_briefing.py"
echo ""
echo "To watch the log:"
echo "  tail -f $LOG_FILE"
echo ""
echo "To remove the cron job:"
echo "  crontab -l | grep -v morning_briefing.py | crontab -"
