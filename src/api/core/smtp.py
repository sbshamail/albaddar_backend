import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM


def send_email(to_email: str, subject: str, body: str):
    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "html"))

    print(f"✅ Email sent to {to_email}")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"❌ Email sending failed: {e}")
        return False


def send_email_options(
    to_emails: str | list[str],
    subject: str,
    body: str,
    cc_emails: list[str] | None = None,
    bcc_emails: list[str] | None = None,
):
    """
    Send email with To, CC, BCC support.

    Example:
        send_email(
            to_emails=["user@gmail.com"],
            cc_emails=["manager@gmail.com"],
            bcc_emails=["admin@gmail.com"],
            subject="Order Created",
            body="<h1>Hello</h1>"
        )
    """

    if isinstance(to_emails, str):
        to_emails = [to_emails]

    cc_emails = cc_emails or []
    bcc_emails = bcc_emails or []

    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = ", ".join(to_emails)

    if cc_emails:
        msg["Cc"] = ", ".join(cc_emails)

    msg["Subject"] = subject

    msg.attach(MIMEText(body, "html"))

    all_recipients = to_emails + cc_emails + bcc_emails

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)

            server.sendmail(
                SMTP_FROM,
                all_recipients,
                msg.as_string(),
            )

        print(f"✅ Email sent to {all_recipients}")
        return True

    except Exception as e:
        print(f"❌ Email sending failed: {e}")
        return False
