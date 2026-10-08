# Apprise Notification Configuration for CampusPilot
# This file configures the alerting service (carlesdp/notify) which wraps Apprise
# Supports: Telegram, Discord, Slack, Email, Webhooks, Pushbullet, Gotify, etc.

# ================================================================
# Telegram Bot Configuration
# ================================================================
# Create a bot with @BotFather, get the token and chat ID
# Format: tgram://bot_token/chat_id
# Multiple chat IDs: tgram://bot_token/chat_id1/chat_id2/...

# Example:
# NOTIFY_TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz
# NOTIFY_TELEGRAM_CHAT_ID=-1001234567890

# ================================================================
# Discord Webhook
# ================================================================
# Format: discord://webhook_id/webhook_token
# Example:
# NOTIFY_DISCORD_WEBHOOK=discord://123456789012345678/abcdefghijklmnopqrstuvwxyz

# ================================================================
# Slack Webhook
# ================================================================
# Format: slack://token_a/token_b/token_c/#channel
# Or for bot token: slack://xoxb-token/#channel
# Example:
# NOTIFY_SLACK_WEBHOOK=slack://xoxb-YOUR_BOT_TOKEN_HERE/#alerts

# ================================================================
# Email (SMTP)
# ================================================================
# Format: email://user:password@host:port/from_email/to_email1,to_email2
# Supports TLS/SSL
# Example:
# NOTIFY_EMAIL=email://user:YOUR_PASSWORD@smtp.gmail.com:587/noreply@iiitdmj.ac.in/admin@iiitdmj.ac.in,security@iiitdmj.ac.in

# ================================================================
# Generic Webhook
# ================================================================
# Format: webhook://host/path?method=POST&header=Content-Type:application/json
# Can be used for custom integrations (e.g., PagerDuty, OpsGenie, custom endpoints)
# Example:
# NOTIFY_WEBHOOK_URL=webhook://hooks.example.com/alerts?method=POST&header=Content-Type:application/json

# ================================================================
# Gotify
# ================================================================
# Format: gotify://host/token?priority=5
# Example:
# NOTIFY_GOTIFY=gotify://gotify.example.com/YOUR_TOKEN_HERE?priority=10

# ================================================================
# Pushbullet
# ================================================================
# Format: pushbullet://access_token
# Example:
# NOTIFY_PUSHBULLET=pushbullet://YOUR_ACCESS_TOKEN_HERE

# ================================================================
# Microsoft Teams
# ================================================================
# Format: msteams://webhook_url
# Example:
# NOTIFY_TEAMS=msteams://outlook.office.com/webhook/YOUR_WEBHOOK_URL_HERE

# ================================================================
# Matrix
# ================================================================
# Format: matrix://user:password@host/room_id
# Example:
# NOTIFY_MATRIX=matrix://bot:YOUR_PASSWORD@matrix.org/!room:matrix.org

# ================================================================
# Rocket.Chat
# ================================================================
# Format: rocketchat://user:password@host/channel
# Example:
# NOTIFY_ROCKETCHAT=rocketchat://bot:pass@chat.example.com/#alerts

# ================================================================
# Pushover
# ================================================================
# Format: pushover://user_key@api_token
# Example:
# NOTIFY_PUSHOVER=pushover://user_key@api_token

# ================================================================
# Custom Webhook with Custom Headers
# ================================================================
# The notify container supports custom headers for webhooks
# Example for PagerDuty:
# NOTIFY_PAGERDUTY=webhook://events.pagerduty.com/v2/enqueue?method=POST&header=Content-Type:application/json&header=Authorization:Token+token=YOUR_INTEGRATION_KEY

# ================================================================
# Template Variables Available in Messages
# ================================================================
# {{ alertname }} - Name of the alert
# {{ severity }} - Severity (critical, warning, info)
# {{ summary }} - Summary annotation
# {{ description }} - Description annotation
# {{ labels.* }} - Any label value (e.g., {{ labels.subsection }})
# {{ annotations.* }} - Any annotation value
# {{ startsAt }} - Alert start time
# {{ endsAt }} - Alert end time (if resolved)
# {{ generatorURL }} - Link to Prometheus rule
# {{ .CommonAnnotations }} - All common annotations
# {{ .CommonLabels }} - All common labels
# {{ .ExternalURL }} - Alertmanager external URL

# ================================================================
# Sample Message Templates
# ================================================================
# Telegram:
# [{{ .Status }}] {{ .Labels.alertname }} ({{ .Labels.severity }})
# {{ .Annotations.summary }}
# {{ .Annotations.description }}
# Subsection: {{ .Labels.subsection }}

# Email Subject:
# [{{ .Status }}] {{ .Labels.alertname }} - {{ .Labels.severity }}

# Slack/Discord:
# *{{ .Labels.alertname }}* ({{ .Labels.severity }})
# {{ .Annotations.summary }}
# {{ .Annotations.description }}
# *Subsection:* {{ .Labels.subsection }}

# ================================================================
# Testing Notifications
# ================================================================
# Test via command line:
# docker compose --profile lite exec alerting notify -t "test" -b "Test message" -tgram://bot_token/chat_id

# Test via HTTP API:
# curl -X POST http://localhost:8001/alerting/test \
#   -H "Authorization: Bearer $ADMIN_TOKEN" \
#   -d '{"channels": ["telegram"], "message": "Test alert"}'

# ================================================================
# Environment Variables for docker-compose
# ================================================================
# Copy these to your .env file:
#
# # Telegram (required for all profiles)
# ALERT_TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz
# ALERT_TELEGRAM_CHAT_ID=-1001234567890
#
# # Optional webhook (PagerDuty, OpsGenie, custom)
# ALERT_WEBHOOK_URL=https://hooks.example.com/alerts
#
# # Optional Discord
# NOTIFY_DISCORD_WEBHOOK=discord://webhook_id/webhook_token
#
# # Optional Slack
# NOTIFY_SLACK_WEBHOOK=slack://xoxb-token/#alerts
#
# # Optional Email
# NOTIFY_EMAIL=email://user:YOUR_PASSWORD@smtp.gmail.com:587/from@domain.com/to1@domain.com,to2@domain.com
#
# # Optional Gotify
# NOTIFY_GOTIFY=gotify://gotify.example.com/token?priority=10
#
# # Optional Pushover
# NOTIFY_PUSHOVER=pushover://user_key@api_token