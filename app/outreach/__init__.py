# outreach — sub-package for outreach and template rendering

from app.outreach.subjects import generate_subject_lines
from app.outreach.email import generate_email
from app.outreach.mailer import send_email, send_test_email

__all__ = ["generate_subject_lines", "generate_email", "send_email", "send_test_email"]
