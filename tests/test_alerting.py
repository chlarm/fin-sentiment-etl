"""
The alerting path sits at the very end of the ETL, so a hang here fails a run
whose work was already committed — and it is also the thing that is supposed
to tell us when something broke. Both make an unbounded network call
unacceptable.
"""
from __future__ import annotations
import smtplib
from unittest.mock import MagicMock, patch

from src import alerting


def _settings(monkeypatch):
    fake = MagicMock(email_sender="a@b.c", email_password="pw", email_receiver="d@e.f")
    monkeypatch.setattr(alerting, "Settings", lambda: fake)


def test_smtp_connection_passes_a_timeout(monkeypatch):
    """Without one, smtplib blocks forever on a socket that connects but never
    replies, which is exactly how a nightly run burns until Airflow SIGTERMs
    it."""
    _settings(monkeypatch)
    with patch.object(smtplib, "SMTP_SSL") as smtp:
        alerting.send_email_alert("subject", "body")
    _args, kwargs = smtp.call_args
    assert kwargs.get("timeout") == alerting.SMTP_TIMEOUT_SECONDS
    assert alerting.SMTP_TIMEOUT_SECONDS > 0


def test_a_failing_send_does_not_raise(monkeypatch, capsys):
    """Alerting must never become the reason a run fails."""
    _settings(monkeypatch)
    with patch.object(smtplib, "SMTP_SSL", side_effect=OSError("network down")):
        alerting.send_email_alert("subject", "body")
    assert "Failed to send Email alert" in capsys.readouterr().out


def test_missing_credentials_skip_silently(monkeypatch, capsys):
    monkeypatch.setattr(alerting, "Settings",
                        lambda: MagicMock(email_sender=None, email_password=None, email_receiver=None))
    with patch.object(smtplib, "SMTP_SSL") as smtp:
        alerting.send_email_alert("subject", "body")
    smtp.assert_not_called()
    assert "Skipping alert" in capsys.readouterr().out
