"""Logic for the API."""

import logging

from ckan.common import config
from ckan.lib import mailer
from ckan.lib.api_token import decode as successful_jwt_decode
from ckan.lib.navl.dictization_functions import DataError
from ckan.lib.redis import connect_to_redis
from ckan.logic import side_effect_free
from ckan.plugins import toolkit

# from ckan.types import Context, DataDict
from sqlalchemy.exc import InternalError as SQLAlchemyError

from ckanext.passwordless_api import util
from ckanext.passwordless_api.mailer import send_user_reset_key, send_welcome_email

log = logging.getLogger(__name__)


def request_reset_key(
    context,  #: Context,
    data_dict,  #: DataDict
):
    """
    Request a reset key (login token) to be sent by email.

    Args:
        data_dict.email (str): Email of user.

    Returns:
        dict: {message: 'success'}
    """
    log.debug(f"Request reset key with params: {data_dict}")

    if toolkit.c.user:
        # Don't offer the reset if already logged in
        log.warning("User already logged in")
        raise toolkit.NotAuthorized("user already logged in, logout first")

    # Check email is present in POST data
    if not (email := data_dict.get("email")):
        raise toolkit.ValidationError({"email": "missing email"})

    # Check email is valid
    email = email.lower()
    if not util.email_is_valid(email):
        raise toolkit.ValidationError({"email": "invalid email"})

    # control attempts (exception raised on fail)
    util.check_reset_attempts(email.encode())

    # get existing user from email
    user = util.get_user_from_email(email)
    # log.debug(f'USER is {str(user)})

    if not user:
        # A user with this email address doesn't yet exist in CKAN,
        # so create one.
        user = _create_user(email)
        log.debug(f"Created user {str(email)}")

    if user:
        # make sure is not deleted
        if user.state == "deleted":
            raise toolkit.ValidationError(
                {"user": f"User with email {email} was deleted"}
            )
        try:
            send_user_reset_key(user)

        except mailer.MailerException as e:
            log.error(f"Could not send token link: {str(e)}")
            raise mailer.MailerException(f"Could not send token link by mail: {str(e)}")

    else:
        raise toolkit.ValidationError(
            {"user": "cannot retrieve or create user with given email"}
        )

    return {"message": "success"}


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
        send_welcome_email(user)
    except SQLAlchemyError as error:
        exception_message = f"{error}"
        log.error(f"Failed to create user: {error}")
        if exception_message.find("quota") >= 0:
            raise DataError("Error creating a new user, daily new user quota exceeded")
        else:
            raise DataError("Internal error creating a new user")

    return user


def request_api_token(
    context,  #: Context,
    data_dict,  #: DataDict
):
    """
    Get API token for a user, if reset key valid.

    Args:
        data_dict.email (str): Email of user.
        data_dict.key (str): Reset key of user (from email after request_reset_key).

    Returns:
        dict: CKAN API token for user {'token': token_value}.
    """
    log.debug(f"Requesting API token with params: {data_dict}")

    if toolkit.c.user:
        # Don't offer the reset if already logged in
        log.warning("User already logged in")
        raise toolkit.NotAuthorized("user already logged in, logout first")

    # Check if parameters are present
    if not (email := data_dict.get("email")):
        raise toolkit.ValidationError({"email": "missing email"})
    if not (orig_key := data_dict.get("key")):
        raise toolkit.ValidationError({"key": "missing token"})
    # Check email valid
    email = email.lower()
    if not util.email_is_valid(email):
        raise toolkit.ValidationError({"email": "invalid email"})
    # Set user
    if not (user := util.get_user_from_email(email)):
        raise toolkit.ValidationError(
            {"email": "email does not correspond to a registered user"}
        )

    # Validate key
    if len(orig_key) <= 32 and not orig_key.startswith("b'"):
        key = f"b'{orig_key}'"
    else:
        key = orig_key

    user_id = user.id
    log.debug(f"User id: {user_id} ({orig_key}) => {key}")

    # Check provided key is valid
    if not user or not mailer.verify_reset_link(user, key):
        raise toolkit.ValidationError({"key": "token provided is not valid"})

    # Recreate reset_key in db
    mailer.create_reset_key(user)

    # delete attempts from Redis
    log.debug(f"Redis: reset attempts for {email}")
    redis_conn = connect_to_redis()
    redis_conn.delete(email)

    expiry = int(config.get("expire_api_token.default_lifetime", 3))
    units = int(config.get("expire_api_token.default_unit", 86400))
    return util.renew_main_token(user_id, expiry, units)


@side_effect_free
def revoke_api_token_no_auth(
    context,  #: Context,
    data_dict,  #: DataDict
):
    """
    Revoke API token for a user, without requiring auth.

    Useful for when user API token has expired already, but they wish to check
    if revokation is possible (i.e. during logout - revoke if possible).

    Args:
        data_dict.token (str, optional): Value of API token to revoke.

    Returns:
        dict: {message: 'success'}
    """
    log.debug("Revoking API token if present.")

    # User cookie / logged in
    if (user := context.get("user", "")) != "":
        log.debug("User ID extracted from context user key")
        user_id = user
    elif user := context.get("auth_user_obj", None):
        log.debug("User ID extracted from context auth_user_obj key")
        user_id = user.id

    else:
        # Attempt revoke provided token via POST
        if not (api_token := data_dict.get("token")):
            log.warning("Attempting to revoke API token, but none provided")
            raise toolkit.ValidationError({"token": "missing api token to revoke"})

        if not successful_jwt_decode(api_token):
            raise toolkit.ValidationError(
                {"token": "failed to decode token, not valid"}
            )

        try:
            toolkit.get_action("api_token_revoke")(
                context={"ignore_auth": True},
                data_dict={
                    "token": api_token,
                },
            )
            return {"message": "success"}

        except Exception as e:
            log.warning(f"Could not delete API token due to: {e}")
            return {"message": "failed"}

    # Renew with 1 second expiry
    api_token = util.renew_main_token(user_id, 1, 60)
    if api_token:
        return {"message": "success"}

    return {"message": "failed"}


@side_effect_free
def get_current_user_and_renew_api_token(
    context,  #: Context,
    data_dict,  #: DataDict
):
    """
    Return CKAN user and renew API token.

    Uses the user_show core action to return the user, and renews the main API token.

    Returns:
        dict: {user: ckan_user_obj, token: api_token}
    """
    log.debug("start function get_current_user_and_renew_api_token")

    if (user := context.get("user", "")) != "":
        log.debug("User ID extracted from context user key")
        user_id = user
    elif user := context.get("auth_user_obj", None):
        log.debug("User ID extracted from context auth_user_obj key")
        user_id = user.id
    else:
        raise toolkit.NotAuthorized(
            {"message": "API token is invalid or missing from Authorization header"}
        )

    try:
        log.info(f"Getting user details with user_id: {user_id}")
        user = toolkit.get_action("user_show")(
            data_dict={
                "id": user_id,
            },
        )

    except Exception as e:
        log.error(str(e))
        log.warning(f"Could not find a user for ID: {user_id}")
        return {"message": f"could not find a user for id: {user_id}"}

    if user:
        expiry = config.get("expire_api_token.default_lifetime", 3)
        units = config.get("expire_api_token.default_unit", 86400)
        token_json = util.renew_main_token(user_id, expiry, units)
        return {
            "user": user,
            "token": token_json.get("token"),
        }

    return {"message": "failed"}
