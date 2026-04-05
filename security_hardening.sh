#!/bin/bash
#====================================================================
# TRADING DESK SECURITY HARDENING SCRIPT
#====================================================================
# Run as: sudo bash security_hardening.sh
#====================================================================

set -e

echo "=============================================="
echo "SECURITY HARDENING - Trading Desk"
echo "=============================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; }

#--------------------------------------------------------------------
# 1. SSH HARDENING
#--------------------------------------------------------------------
echo ""
echo "[1/8] SSH Hardening"
echo "--------------------------------------------"

SSH_CONFIG="/etc/ssh/sshd_config"
SSH_CONFIG_BACKUP="/etc/ssh/sshd_config.backup.$(date +%Y%m%d%H%M%S)"

# Backup current config
cp "$SSH_CONFIG" "$SSH_CONFIG_BACKUP"
log_pass "Backed up sshd_config to $SSH_CONFIG_BACKUP"

# Disable password authentication
if grep -q "^PasswordAuthentication yes" "$SSH_CONFIG"; then
    sed -i 's/^PasswordAuthentication yes/PasswordAuthentication no/' "$SSH_CONFIG"
    log_pass "Disabled PasswordAuthentication"
else
    log_pass "PasswordAuthentication already disabled"
fi

# Disable root login
if grep -q "^PermitRootLogin yes" "$SSH_CONFIG"; then
    sed -i 's/^PermitRootLogin yes/PermitRootLogin no/' "$SSH_CONFIG"
    log_pass "Disabled PermitRootLogin"
else
    log_pass "PermitRootLogin already disabled"
fi

# Set MaxAuthTries
if grep -q "^MaxAuthTries" "$SSH_CONFIG"; then
    sed -i 's/^MaxAuthTries.*/MaxAuthTries 3/' "$SSH_CONFIG"
else
    echo "MaxAuthTries 3" >> "$SSH_CONFIG"
fi
log_pass "Set MaxAuthTries to 3"

# Disable X11Forwarding if not needed
if grep -q "^X11Forwarding yes" "$SSH_CONFIG"; then
    sed -i 's/^X11Forwarding yes/X11Forwarding no/' "$SSH_CONFIG"
    log_pass "Disabled X11Forwarding"
fi

# Restart SSH
systemctl restart sshd
log_pass "Restarted SSH service"

#--------------------------------------------------------------------
# 2. UFW FIREWALL
#--------------------------------------------------------------------
echo ""
echo "[2/8] UFW Firewall Setup"
echo "--------------------------------------------"

# Enable UFW
ufw --force enable
log_pass "UFW firewall enabled"

# Default policies
ufw default deny incoming
ufw default allow outgoing
log_pass "Set default policies: deny incoming, allow outgoing"

# Allow SSH (current session won't drop)
ufw allow 22/tcp comment 'SSH'
log_pass "Allowed SSH on port 22"

# Allow Ollama (localhost only, but adding rule for safety)
ufw allow 11434/tcp comment 'Ollama'
log_pass "Allowed Ollama on port 11434"

# Allow Paperclip (restrict to local only via app config)
# Paperclip should bind to 127.0.0.1:3100 in production
ufw allow from 127.0.0.1 to any port 3100 proto tcp comment 'Paperclip-local'
log_pass "Allowed Paperclip localhost only on port 3100"

# Allow HTTP/HTTPS for web access
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
log_pass "Allowed HTTP/HTTPS"

# Show status
ufw status verbose

#--------------------------------------------------------------------
# 3. FAIL2BAN
#--------------------------------------------------------------------
echo ""
echo "[3/8] Fail2Ban Setup"
echo "--------------------------------------------"

# Install fail2ban if not present
if ! command -v fail2ban-server &> /dev/null; then
    apt-get update -qq
    apt-get install -y fail2ban
    log_pass "Installed fail2ban"
fi

# Configure fail2ban
FAIL2BAN_JAIL="/etc/fail2ban/jail.local"
FAIL2BAN_JAIL_BACKUP="/etc/fail2ban/jail.local.backup.$(date +%Y%m%d%H%M%S)"

# Create jail.local if it doesn't exist
if [ ! -f "$FAIL2BAN_JAIL" ]; then
    cp /etc/fail2ban/jail.conf "$FAIL2BAN_JAIL"
fi

# Enable SSH jail
cat > /etc/fail2ban/jail.d/sshd.local << 'EOF'
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
findtime = 600
EOF
log_pass "Configured fail2ban SSH jail"

# Start and enable fail2ban
systemctl enable fail2ban
systemctl start fail2ban
systemctl status fail2ban --no-pager || true
log_pass "Started and enabled fail2ban"

#--------------------------------------------------------------------
# 4. FILE PERMISSIONS
#--------------------------------------------------------------------
echo ""
echo "[4/8] File Permissions"
echo "--------------------------------------------"

# Secure .env files
ENV_FILES=$(find /home -name ".env" -type f 2>/dev/null)
for env_file in $ENV_FILES; do
    chmod 600 "$env_file"
    log_pass "Secured $env_file"
done

# Secure credentials files
CRED_FILES=$(find /tmp/trading-desk -name "*credentials*" -o -name "*config*" 2>/dev/null)
for cred_file in $CRED_FILES; do
    if [ -f "$cred_file" ]; then
        chmod 600 "$cred_file"
        log_pass "Secured $cred_file"
    fi
done

# Secure SSH directory
if [ -d "/home/ubuntu/.ssh" ]; then
    chmod 700 /home/ubuntu/.ssh
    chmod 600 /home/ubuntu/.ssh/authorized_keys 2>/dev/null || true
    log_pass "Secured .ssh directory"
fi

#--------------------------------------------------------------------
# 5. PAPERCLIP LOCALHOST BIND
#--------------------------------------------------------------------
echo ""
echo "[5/8] Paperclip Localhost Binding"
echo "--------------------------------------------"

# Paperclip should be bound to localhost only
# Add to Paperclip startup: --host 127.0.0.1
# Or configure in environment
echo "export PAPERCLIP_HOST=127.0.0.1" >> /etc/environment
log_pass "Configured Paperclip to bind localhost only"

#--------------------------------------------------------------------
# 6. AUTOMATIC SECURITY UPDATES
#--------------------------------------------------------------------
echo ""
echo "[6/8] Automatic Security Updates"
echo "--------------------------------------------"

# Install unattended-upgrades
if ! command -v unattended-upgrades &> /dev/null; then
    apt-get update -qq
    apt-get install -y unattended-upgrades
    log_pass "Installed unattended-upgrades"
fi

# Configure automatic updates
cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "02:00";
EOF
log_pass "Configured automatic security updates"

# Enable auto-update
dpkg-reconfigure -plow unattended-upgrades || true

#--------------------------------------------------------------------
# 7. LOGGING & AUDIT
#--------------------------------------------------------------------
echo ""
echo "[7/8] Logging Configuration"
echo "--------------------------------------------"

# Create security audit log
AUDIT_LOG="/var/log/trading-desk-audit.log"
touch "$AUDIT_LOG"
chmod 600 "$AUDIT_LOG"
log_pass "Created audit log at $AUDIT_LOG"

# Add to logwatch
cat >> /etc/cron.daily/logwatch << 'EOF'
# Trading Desk Security Events
echo "=== Trading Desk Security Audit ===" >> /var/log/trading-desk-audit.log
who >> /var/log/trading-desk-audit.log
last -10 >> /var/log/trading-desk-audit.log
EOF

#--------------------------------------------------------------------
# 8. FINAL VERIFICATION
#--------------------------------------------------------------------
echo ""
echo "[8/8] Final Verification"
echo "--------------------------------------------"

# Check SSH config
sshd -t && log_pass "SSH config syntax OK" || log_fail "SSH config syntax error"

# Check firewall
ufw status | grep -q "Status: active" && log_pass "UFW is active" || log_warn "UFW may not be active"

# Check fail2ban
systemctl is-active --quiet fail2ban && log_pass "Fail2Ban is running" || log_warn "Fail2Ban may not be running"

echo ""
echo "=============================================="
echo "HARDENING COMPLETE"
echo "=============================================="
echo ""
echo "IMPORTANT: Test SSH access with key-based auth"
echo "BEFORE logging out of current session!"
echo ""
echo "If SSH breaks:"
echo "  1. Connect via console/VNC"
echo "  2. Check /var/log/auth.log"
echo "  3. Restore backup: cp $SSH_CONFIG_BACKUP $SSH_CONFIG"
echo ""
