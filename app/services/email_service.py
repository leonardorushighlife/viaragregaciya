import aiosmtplib
from email.message import EmailMessage
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_email(subject: str, body: str, recipient: str) -> bool:
    if not settings.EMAIL_ENABLED:
        logger.info(f"[EMAIL STUB] Email output disabled. Message to {recipient}: {subject}")
        print(f"[EMAIL STUB] To: {recipient} | Subject: {subject}\n{body}")
        return True

    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=False,
            start_tls=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False
