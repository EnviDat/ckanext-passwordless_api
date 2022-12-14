"""Logic for the API."""

import logging

from ckan.lib import mailer
from ckan.lib.navl.dictization_functions import DataError
from ckan.lib.redis import connect_to_redis
from ckan.plugins import toolkit
from sqlalchemy.exc import InternalError as SQLAlchemyError

from ckanext.passwordless_api import util
from ckanext.passwordless_api.mailer import send_login_token, send_welcome_email

log = logging.getLogger(__name__)


def request_reset_key(context, data_dict):
    """
    Request a passwordless API token to be sent by email.

    POST data_dict must contain email.

    Returns:
        str: Success string.
    """
    log.debug(f"Action request_reset_key: {data_dict}")

    # Check email is present in POST data
    try:
        email = data_dict["email"]
        email = email.lower()
    except KeyError:
        raise toolkit.ValidationError({"email": "missing email"})

    # Check email is valid
    if not util.email_is_valid(email):
        raise toolkit.ValidationError({"email": "invalid email"})

    # control attempts (exception raised on fail)
    util.check_reset_attempts(email.encode())

    # get existing user from email
    user = util.get_user(email)
    # log.debug('passwordless_request_reset: USER is = ' + str(user))

    if not user:
        # A user with this email address doesn't yet exist in CKAN,
        # so create one.
        user = _create_user(email)
        log.debug("passwordless_request_reset: created user = " + str(email))

    if user:
        # make sure is not deleted
        if user.get("state") == "deleted":
            raise toolkit.ValidationError(
                {"user": f"User with email {email} was deleted"}
            )
        try:
            send_login_token(user)

        except mailer.MailerException as e:
            log.error(f"Could not send token link: {str(e)}")
            raise mailer.MailerException(f"Could not send token link by mail: {str(e)}")

    else:
        raise toolkit.ValidationError(
            {"user": "cannot retrieve or create user with given email"}
        )

    return "Token requested successfully."


def _create_user(email):
    """Create a new user and send welcome email."""
    # first check temporary quota
    util.check_new_user_quota()

    try:
        data_dict = {
            "email": email.lower(),
            "fullname": util.generate_user_fullname(email),
            "name": util.get_new_username(email),
            "password": util.generate_password(),
        }
        user = toolkit.get_action("user_create")(
            context={"ignore_auth": True}, data_dict=data_dict
        )
        # log.debug("_create_user: user = {0}".format(user))
        send_welcome_email(user)
    except SQLAlchemyError as error:
        exception_message = f"{error}"
        log.error(f"Failed to create user: {error}")
        if exception_message.find("quota") >= 0:
            raise DataError("Error creating a new user, daily new user quota exceeded")
        else:
            raise DataError("Internal error creating a new user")

    return user


def request_api_token(context, data_dict):
    """
    Get API token for a user, if reset key valid.

    data_dict contains reset key and user email.

    Returns:
        str: CKAN API token for user.
    """
    log.debug(f"Action request_api_token: {data_dict}")

    if toolkit.c.user:
        # Don't offer the reset form if already logged in
        log.warning("User already logged in")
        raise toolkit.NotAuthorized("user already logged in, logout first")

    # Check if parameters are present
    if not (email := data_dict.get("email")):
        raise toolkit.ValidationError({"email": "missing email"})
    if not (orig_key := data_dict.get("key")):
        raise toolkit.ValidationError({"key": "missing token"})
    # Check email valid
    email = email.lower()
    if not util.check_email(email):
        raise toolkit.ValidationError({"email": "invalid email"})
    # Set user
    if not (user := util.get_user(email)):
        raise toolkit.ValidationError(
            {"email": "email does not correspond to a registered user"}
        )

    # Validate key
    if len(orig_key) <= 32 and not orig_key.startswith("b'"):
        key = f"b'{orig_key}'"
    else:
        key = orig_key

    user_id = user.get("id")
    log.debug(f"login: {user_id} ({orig_key}) => {key}")

    # Check provided key is valid
    if not user or not mailer.verify_reset_link(user, key):
        raise toolkit.ValidationError({"key": "token provided is not valid"})

    # Recreate reset_key in db
    mailer.create_reset_key(user)

    # delete attempts from Redis
    log.debug(f"Redis: reset attempts for {email}")
    redis_conn = connect_to_redis()
    redis_conn.delete(email)

    return util.renew_main_token(user_id)


def revoke_api_token(context, data_dict):
    """
    Revoke API token for a user.

    data_dict contains API token value.

    Returns:
        str: Success message.
    """
    log.debug(f"Action revoke_api_token: {data_dict}")

    # Check if parameters are present
    if not (api_token := data_dict.get("api_token")):
        raise toolkit.ValidationError({"token": "missing api token to revoke"})

    try:
        toolkit.get_action("api_token_revoke")(
            data_dict={
                "token": api_token,
            },
        )
    except toolkit.NotAuthorized:
        raise toolkit.NotAuthorized(
            "NotAuthorized to revoke API token. "
            "Did you provide a valid token in the Authorization header?"
        )
        return {"message": "failed"}
    except Exception as e:
        log.warning(f"Could not delete API token due to: {e}")
        return {"message": "failed"}

    return {"message": "success"}
