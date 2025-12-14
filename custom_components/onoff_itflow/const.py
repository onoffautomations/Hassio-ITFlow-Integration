"""Constants for the AWS S3 integration."""

from typing import Final


DOMAIN: Final = "onoff_itflow"

# Platforms
PLATFORMS: Final = ["sensor", "button"]

# ITFlow Configuration
CONF_ITFLOW_API_KEY: Final = "itflow_api_key"
CONF_ITFLOW_CLIENT_ID: Final = "itflow_client_id"
CONF_ITFLOW_SERVER: Final = "itflow_server"
CONF_ITFLOW_ENABLED: Final = "itflow_enabled"
CONF_PUBLIC_URL: Final = "public_url"
CONF_ALERT_ON_ERRORS: Final = "alert_on_errors"
CONF_CREATE_STARTUP_TICKET: Final = "create_startup_ticket"
CONF_ALERT_ON_NEW_UPDATE: Final = "alert_on_new_update"
CONF_ALERT_ON_AUTOMATION_FAILURE: Final = "alert_on_automation_failure"
CONF_ALERT_ON_ERROR_LOGS: Final = "alert_on_error_logs"
CONF_ALERT_ON_BACKUP_FAILURE: Final = "alert_on_backup_failure"
CONF_ALERT_ON_REPAIRS: Final = "alert_on_repairs"

# System Monitoring Configuration
CONF_MONITOR_DISK: Final = "monitor_disk"
CONF_DISK_THRESHOLD: Final = "disk_threshold"
CONF_MONITOR_MEMORY: Final = "monitor_memory"
CONF_MEMORY_THRESHOLD: Final = "memory_threshold"
CONF_MONITOR_CPU: Final = "monitor_cpu"
CONF_CPU_THRESHOLD: Final = "cpu_threshold"
CONF_MONITOR_IP: Final = "monitor_ip_changes"

# Network Monitoring Configuration
CONF_GATEWAY_IP: Final = "gateway_ip"
CONF_CF_TUNNEL_ENABLED: Final = "cf_tunnel_enabled"
CONF_CF_TUNNEL_IP: Final = "cf_tunnel_ip"

# Default thresholds
DEFAULT_DISK_THRESHOLD: Final = 90
DEFAULT_MEMORY_THRESHOLD: Final = 90
DEFAULT_CPU_THRESHOLD: Final = 90

# ITFlow Services
SERVICE_CREATE_TICKET: Final = "create_ticket"

# ITFlow Ticket Priorities
TICKET_PRIORITY_LOW: Final = "Low"
TICKET_PRIORITY_MEDIUM: Final = "Medium"
TICKET_PRIORITY_HIGH: Final = "High"

# ITFlow Ticket Status Mapping
TICKET_STATUS_MAP = {
    "1": "New",
    "2": "Open",
    "3": "On Hold",
    "4": "Resolved",
    "New": "New",
    "Open": "Open",
    "On Hold": "On Hold",
    "Resolved": "Resolved",
    "Closed": "Closed",
}

def map_ticket_status(status):
    """Map ITFlow ticket status number to friendly name."""
    if status is None:
        return "Unknown"
    status_str = str(status)
    # If it's exactly 5, it's Closed
    if status_str == "5":
        return "Closed"
    # If it's a number higher than 5
    if status_str.isdigit() and int(status_str) > 5:
        return "Waiting..."
    return TICKET_STATUS_MAP.get(status_str, status_str)

# Integration Mode Configuration
CONF_INTEGRATION_MODE: Final = "integration_mode"
INTEGRATION_MODE_FULL: Final = "full"
INTEGRATION_MODE_TICKETS_ONLY: Final = "manual"  # Renamed from tickets_only to manual
INTEGRATION_MODE_MANUAL: Final = "manual"  # Alias for backwards compatibility

# Master Account Mode (deprecated)
CONF_MASTER_ACCOUNT_MODE: Final = "master_account_mode"

# Health Report Configuration
CONF_HEALTH_REPORT_ENABLED: Final = "health_report_enabled"
CONF_HEALTH_REPORT_FREQUENCY: Final = "health_report_frequency"
HEALTH_REPORT_DAILY: Final = "daily"
HEALTH_REPORT_WEEKLY: Final = "weekly"
HEALTH_REPORT_MONTHLY: Final = "monthly"
HEALTH_REPORT_NEVER: Final = "never"

# Backup Check Configuration
CONF_BACKUP_CHECK_ENABLED: Final = "backup_check_enabled"
CONF_BACKUP_CHECK_FREQUENCY: Final = "backup_check_frequency"
BACKUP_CHECK_DAILY: Final = "daily"
BACKUP_CHECK_WEEKLY: Final = "weekly"
BACKUP_CHECK_MONTHLY: Final = "monthly"
BACKUP_CHECK_NEVER: Final = "never"

# Scheduling Configuration
CONF_HEALTH_REPORT_TIME: Final = "health_report_time"
CONF_HEALTH_REPORT_DAY_OF_WEEK: Final = "health_report_day_of_week"
CONF_HEALTH_REPORT_DAY_OF_MONTH: Final = "health_report_day_of_month"
CONF_BACKUP_CHECK_TIME: Final = "backup_check_time"
CONF_BACKUP_CHECK_DAY_OF_WEEK: Final = "backup_check_day_of_week"
CONF_BACKUP_CHECK_DAY_OF_MONTH: Final = "backup_check_day_of_month"

# Default scheduling values
DEFAULT_REPORT_TIME: Final = "08:00:00"
DEFAULT_DAY_OF_WEEK: Final = "monday"
DEFAULT_DAY_OF_MONTH: Final = 1
