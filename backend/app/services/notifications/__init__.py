"""Optional high-severity alert notifications (Slack webhook / SMTP). Off by default."""

from app.services.notifications.sink import notify_alert

__all__ = ["notify_alert"]
