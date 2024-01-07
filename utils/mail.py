from datetime import datetime
import logging
from typing import Dict, List, TypeVar
import smtplib
import hashlib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os
from utils.event import Event, EventSeverity, EventType

from utils.logging import get_module_logger

logger = get_module_logger()

load_dotenv()

EmailSender = TypeVar('EmailSender')  # type: ignore


class Email:
    """Class representing an email."""

    def __init__(self, subject: str, body: str, to_addresses: List[str]):
        """
        Initializes the Email class.

        Parameters:
        :param subject: Email subject.
        :param body: Email body.
        :param to_address: Recipient's email address.
        """
        self.subject: str = subject
        self.body: str = body
        self.to_addresses: List[str] = to_addresses

    def __str__(self) -> str:
        return f"Email(subject='{self.subject}', body='{self.body}', to_addresses={self.to_addresses})"

    def send(self, email_sender: EmailSender, to_print: bool = False):
        email_sender.send_email(self)
        if to_print:
            Event(f"Email send: {self}",
                  initiator="Mail Util",
                  event_severity=EventSeverity.DEBUG).store()


class AlertEmail(Email):
    """Class representing an alert email, inherits from Email."""

    def __init__(self, subject: str, body: str, alerting_component: str):
        """
        Initializes the AlertEmail class.
        Takes a 'florian.schleuss@gmx.net' as default recipient or .env provided recipients

        Parameters:
        :param subject: Email subject.
        :param body: Email body.
        :param alerting_component: Additional string indicating the alerting component.
        """
        to_addresses = [i.strip() for i in os.getenv(
            "ALERT_RECIPIENTS", "florian.schleuss@gmx.net").split(",")]
        super().__init__(subject, body, to_addresses)
        self.alerting_component: str = alerting_component

    def __str__(self) -> str:
        return f"AlertEmail(alerting_component='{self.alerting_component}', subject='{self.subject}', body='{self.body}', to_addresses={self.to_addresses})"


class EmailSender:
    """
    Class to handle all email sends to statefully evaluate sending.
    Handles all authentication with smtp.
    """

    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str, cooldown_seconds: int = 3600):
        """
        Initializes the EmailSender class.

        :param smtp_server: SMTP server address.
        :param smtp_port: SMTP server port.
        :param username: GMX.NET username.
        :param password: GMX.NET password.
        :param cooldown_seconds: Cooldown time in seconds for sending the same email again. Default is 3600 seconds (60 minutes).
        """
        self.smtp_server: str = smtp_server
        self.smtp_port: int = smtp_port
        self.username: str = username
        self.password: str = password
        self.cooldown_seconds: int = cooldown_seconds
        self._email_cache: Dict[str, float] = {}

    @classmethod
    def from_env(cls):
        # Load credentials from .env file
        smtp_server: str = os.getenv("SMTP_SERVER", "mail.gmx.net")
        smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
        assert os.getenv("GMX_USERNAME") is not None
        username: str = os.getenv("GMX_USERNAME")  # type: ignore
        assert os.getenv("GMX_PASSWORD") is not None
        password: str = os.getenv("GMX_PASSWORD")  # type: ignore

        # Initialize EmailSender with a cooldown of 300 seconds (5 minutes)
        return cls(
            smtp_server, smtp_port, username, password)

    def _get_email_hash(self, email: Email) -> str:
        """Generate a hash for the email."""
        content: str = f"{email.subject}{','.join(email.to_addresses)}"
        return hashlib.md5(content.encode()).hexdigest()

    def _is_email_on_cooldown(self, email_hash: str) -> bool:
        """Check if the email is still on cooldown."""
        timestamp: float = self._email_cache.get(email_hash, 0)
        return time.time() - timestamp < self.cooldown_seconds

    def send_email(self, email: Email) -> None:
        """
        Sends an email using the provided credentials, respecting the cooldown.

        :param email: An instance of the Email class.
        """
        email_hash: str = self._get_email_hash(email)

        if self._is_email_on_cooldown(email_hash):
            # Email on cooldown. Please wait before sending the same email again.
            return

        try:
            # Connect to the SMTP server
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                # Log in to the SMTP server
                server.starttls()
                server.login(self.username, self.password)

                # Construct the email message
                message = MIMEMultipart()

                sender: str = f"FLEYBACH Backend <{self.username}>"
                if isinstance(email, AlertEmail):
                    message['Importance'] = 'High'
                    message['X-Priority'] = '1'
                    message['X-MSMail-Priority'] = 'High'
                    sender = f"FLEYBACH Backend - {email.alerting_component} <{self.username}>"
                message['From'] = sender
                message['To'] = ', '.join(email.to_addresses)
                message['Subject'] = email.subject
                message.attach(
                    MIMEText(f"{datetime.now()} UTC:\n{email.body}", 'plain'))

                # Send the email
                server.sendmail(self.username, email.to_addresses,
                                message.as_string())

                # Update the cache with the timestamp
                self._email_cache[email_hash] = time.time()

        except Exception as e:
            Event(f"Error sending email: {str(e)}",
                  initiator="Mail Util",
                  event_severity=EventSeverity.IMPORTANT,
                  event_type=EventType.ERROR).store()
