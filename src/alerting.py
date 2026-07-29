import smtplib
from email.message import EmailMessage
from src.config import Settings

# Without a timeout, smtplib blocks forever on a network that accepts the
# connection but never replies. That turns the alerting path — the thing meant
# to tell us something went wrong — into the reason the run hangs until
# Airflow SIGTERMs it, and because this call sits at the very end of the ETL,
# a hang here fails a run whose work had already been committed.
SMTP_TIMEOUT_SECONDS = 30


def send_email_alert(subject: str, body: str) -> None:
    settings = Settings()
    
    sender = settings.email_sender
    password = settings.email_password
    receiver = settings.email_receiver
    
    if not sender or not password or not receiver:
        print("[Alert] Email credentials not fully set. Skipping alert.")
        return

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    try:
        # Assuming Gmail SMTP for simplicity. User can adapt if using another provider.
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=SMTP_TIMEOUT_SECONDS) as server:
            server.login(sender, password)
            server.send_message(msg)
        print("[Alert] Successfully sent Email alert.")
    except Exception as e:
        print(f"[Alert] Failed to send Email alert: {e}")
