import smtplib
from email.message import EmailMessage

def send_email(to_email: str, subject: str, content: str):
    import os # os must only be imported later, messes with load_dotenv
    smtp_host = os.environ.get("SUPABASE_SMTP_HOST") or os.environ.get("SMTP_HOST")
    smtp_port = os.environ.get("SUPABASE_SMTP_PORT") or os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SUPABASE_SMTP_USER") or os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SUPABASE_SMTP_PASS") or os.environ.get("SMTP_PASS")
    smtp_sender = os.environ.get("SUPABASE_SMTP_SENDER") or "noreply@fixel.com"

    if not (smtp_host and smtp_port and smtp_user and smtp_pass):
        print(f"MOCK EMAIL to {to_email}: [{subject}] {content}")
        return

    try:
        msg = EmailMessage()
        msg.set_content(content)
        msg["Subject"] = subject
        msg["From"] = smtp_sender
        msg["To"] = to_email

        with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")
