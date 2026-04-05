#!/bin/bash
#====================================================================
# SECURITY AUDIT SCRIPT - Run regularly via cron
#====================================================================

LOG_FILE="/var/log/trading-desk-security.log"

echo "=============================================="
echo "Trading Desk Security Audit"
echo "Date: $(date)"
echo "==============================================" >> "$LOG_FILE"

# Check failed SSH attempts
echo "" >> "$LOG_FILE"
echo "[SSH FAILURES]" >> "$LOG_FILE"
grep "Failed password" /var/log/auth.log 2>/dev/null | tail -10 >> "$LOG_FILE" || echo "No auth log access" >> "$LOG_FILE"

# Check active connections
echo "" >> "$LOG_FILE"
echo "[ACTIVE CONNECTIONS]" >> "$LOG_FILE"
who >> "$LOG_FILE"

# Check port scans
echo "" >> "$LOG_FILE"
echo "[RECENT LOGIN ATTEMPTS]" >> "$LOG_FILE"
last -10 >> "$LOG_FILE"

# Check fail2ban
echo "" >> "$LOG_FILE"
echo "[FAIL2BAN STATUS]" >> "$LOG_FILE"
fail2ban-client status 2>/dev/null >> "$LOG_FILE" || echo "Fail2ban not running" >> "$LOG_FILE"

# Check file permissions
echo "" >> "$LOG_FILE"
echo "[RECENTLY MODIFIED FILES]" >> "$LOG_FILE"
find /home/ubuntu -type f -mtime -1 2>/dev/null | head -20 >> "$LOG_FILE"

echo "" >> "$LOG_FILE"
echo "Audit complete. Review $LOG_FILE for details."
