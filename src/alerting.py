import smtplib
from email.message import EmailMessage
from src.config import Settings

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
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        print("[Alert] Successfully sent Email alert.")
    except Exception as e:
        print(f"[Alert] Failed to send Email alert: {e}")
