"""Util to send emails."""

import logging

from ckan.common import config
from ckan.lib import mailer
from ckan.lib.base import render

log = logging.getLogger(__name__)


def send_user_reset_key(user):
    """Send the login token email."""
    mailer.create_reset_key(user)
    if reset_key := user.reset_key:
        # Strip b'' wrapping
        reset_key = reset_key[2:-1]
    # log.debug("passwordless_send_reset_link user = " + str(user))
    body = _get_user_reset_key_body(user.as_dict(), reset_key)
    subject = f"Access token: {reset_key}"
    mailer.mail_user(user, subject, body)


def _get_user_reset_key_body(user: dict, reset_key):
    """Render the login token email."""
    if display_name := user.get("fullname"):
        pass
    elif display_name := user.get("name"):
        pass
    else:
        display_name = user.get("email")
    extra_vars = {
        "site_title": config.get("ckan.site_title"),
        "site_url": config.get("ckan.site_url"),
        "display_name": display_name,
        "reset_key_bold": reset_key,
    }
    # NOTE: This template is translated
    reset_key_template = config.get(
        "passwordless_api.reset_key_template",
        "reset_key.txt",
    )
    return render(reset_key_template, extra_vars)


def send_welcome_email(user):
    """Send the welcome email."""
    body = _get_welcome_email_body(user.as_dict())
    subject = "Welcome to {}".format(config.get("ckan.site_title"))

    # log.debug(
    #     f"passwordless_mailer: Welcome email subject: '{subject}',  body: \n {body}"
    # )
    mailer.mail_user(user, subject, body)


def _get_welcome_email_body(user: dict):
    """Render the welcome email."""
    extra_vars = {
        "site_title": config.get("ckan.site_title"),
        "site_url": config.get("ckan.site_url"),
        "guidelines_url": config.get("passwordless_api.guidelines_url", None),
        "policies_url": config.get("passwordless_api.policies_url", None),
        "site_org": config.get("ckan.site_org", "our organization"),
        "email_to": config.get("email_to"),
        "user_name": user.get("name"),
        "user_fullname": user.get("fullname"),
        "user_email": user.get("email"),
    }

    # NOTE: This template is translated
    welcome_template = config.get(
        "passwordless_api.welcome_template",
        "welcome_user.txt",
    )
    return render(welcome_template, extra_vars)
