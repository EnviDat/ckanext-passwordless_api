"""Util to send emails."""

import logging

from ckan.common import config
from ckan.lib import mailer
from ckan.lib.base import render

log = logging.getLogger(__name__)


def send_login_token(user):
    """Send the login token email."""
    mailer.create_reset_key(user)
    # log.debug("passwordless_send_reset_link user = " + str(user))
    body = _get_login_token_body(user)
    subject = f"{config.get('ckan.site_title')} access token"
    mailer.mail_user(user, subject, body)


def _get_login_token_body(user):
    """Render the login token email."""
    if reset_key := user.get("reset_key"):
        # Strip b'' wrapping
        reset_key = reset_key[2:-1]
    extra_vars = {
        "site_title": config.get("ckan.site_title"),
        "site_url": config.get("ckan.site_url"),
        "user_name": user.get("name"),
        "user_fullname": user.get("fullname"),
        "user_email": user.get("email"),
        "key": reset_key,
    }
    # NOTE: This template is translated
    return render("emails/login_token.txt", extra_vars)


def send_welcome_email(user):
    """Send the welcome email."""
    body = _get_welcome_email_body(user)
    subject = "Welcome to {}".format(config.get("ckan.site_title"))

    # log.debug(
    #     f"passwordless_mailer: Welcome email subject: '{subject}',  body: \n {body}"
    # )
    mailer.mail_recipient(user.get("name"), user.get("email"), subject, body)


def _get_welcome_email_body(user):
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
        "passwordless.welcome_template", "emails/welcome_user.txt"
    )
    return render(welcome_template, extra_vars)
