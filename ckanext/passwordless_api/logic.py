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
from requests import get as get_url
from sqlalchemy.exc import InternalError as SQLAlchemyError

from ckanext.passwordless_api import util
from ckanext.passwordless_api.mailer import send_user_reset_key, send_welcome_email

log = logging.getLogger(__name__)


def request_reset_key(
    context,  #: Context,
    data_dict,  #: DataDict,
):
    """Request a reset key (login token) to be sent by email.

    Args:
        context (Context): CKAN context, including user.
        data_dict (DataDict):
            - email (str): Email of user.

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
        # A user with this email address doesn't yet exist in CKAN, so create one.
        new_user_email = _create_user(email)
        log.debug(f"Created user {str(email)}")
        user = util.get_user_from_email(new_user_email)
        send_welcome_email(user)

    if user:
        # make sure is not deleted
        if user.state == "deleted":
            raise toolkit.ValidationError(
                {"user": f"User with email {email} was deleted already. Contact Admin."}
            )
        try:
            send_user_reset_key(user)

        except mailer.MailerException as e:
            log.error(f"Could not send token link: {str(e)}")
            raise mailer.MailerException from e(
                f"Could not send token link by mail: {str(e)}"
            )

    else:
        raise toolkit.ValidationError from None(
            {"user": "cannot retrieve or create user with given email"}
        )

    return {"message": "success"}


def _create_user(email):
    """Create a new user and send welcome email.

    Returns the user email.
    """
    # first check temporary quota
    util.check_new_user_quota()

    try:
        data_dict = {
            "email": email.lower(),
            "fullname": util.generate_user_fullname(email),
            "name": util.get_new_username(email),
            "password": util.generate_password(),
        }
        user_dict = toolkit.get_action("user_create")(
            context={"ignore_auth": True}, data_dict=data_dict
        )
    except SQLAlchemyError as error:
        exception_message = f"{error}"
        log.error(f"Failed to create user: {error}")
        if exception_message.find("quota") >= 0:
            raise DataError from error(
                "Error creating a new user, daily new user quota exceeded"
            )
        else:
            raise DataError from error("Internal error creating a new user")
    except Exception as e:
        log.error(e)
        log.error("Error creating new user")
        raise Exception from e

    return user_dict.get("email")


def request_api_token(
    context,  #: Context,
    data_dict,  #: DataDict,
):
    """Get API token for a user, if reset key valid.

    Args:
        context (Context): CKAN context, including user.
        data_dict (DataDict):
            - email (str): Email of user.
            - key (str): Reset key of user (from email after request_reset_key).

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
    if not (key := data_dict.get("key")):
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

    user_id = user.id
    log.debug(f"User id: {user_id} | Key: {key}")

    # Check provided key is valid
    if not user or not mailer.verify_reset_link(user, key):
        raise toolkit.ValidationError({"key": "token provided is not valid"})

    # Invalidate reset_key in db
    mailer.create_reset_key(user)

    # delete attempts from Redis
    log.debug(f"Redis: reset attempts for {email}")
    redis_conn = connect_to_redis()
    redis_conn.delete(email)

    expiry = int(config.get("expire_api_token.default_lifetime", 3))
    units = int(config.get("expire_api_token.default_unit", 86400))
    return util.renew_main_token(user_id, expiry, units)


def request_api_token_azure_ad(
    context,  #: Context,
    data_dict,  #: DataDict,
):
    """Get API token for a user, if valid Azure AD token provided.

    To be called from a custom frontend, using a Azure AD login flow.

    Args:
        context (Context): CKAN context, including user.
        data_dict (DataDict):
            - email (str): Email of user.
            - token (token): Token generated by Azure AD from frontend.

    Returns:
        dict: CKAN API token for user {'token': token_value}.
    """
    log.debug(f"Requesting API token using Azure AD token params: {data_dict}")

    # Check if parameters are present
    if not (email := data_dict.get("email")):
        raise toolkit.ValidationError({"email": "missing email"})
    if not (token := data_dict.get("token")):
        raise toolkit.ValidationError({"token": "missing token"})

    # Check email valid
    email = email.lower()
    if not util.email_is_valid(email):
        raise toolkit.ValidationError({"email": "invalid email"})

    # Validate Azure AD token
    try:
        log.debug("Verifying JWT token")
        response = get_url(
            "https://graph.microsoft.com/v1.0/me", headers={"Authorization": token}
        ).json()
        log.debug(f"Returned response for verification: {response}")

        azure_ad_email = response.get("mail", None)
        if azure_ad_email != email:
            raise toolkit.NotAuthorized from None(
                "email from azure verification does not match email provided "
                "from frontend app. verification failed"
            )

    except Exception as e:
        log.error(e)
        raise toolkit.ValidationError from e(
            {"token": "unknown error while validating token with azure"}
        )

    # Check user exists, else create new user
    if not (user := util.get_user_from_email(email)):
        _create_user(email)
        log.debug(f"Created user {str(email)}")
        user = util.get_user_from_email(email)
    # Get user id from database model
    user_id = user.id

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
    data_dict,  #: DataDict,
):
    """Revoke API token for a user, without requiring auth.

    Useful for when user API token has expired already, but they wish to check
    if revokation is possible (i.e. during logout - revoke if possible).

    Args:
        context (Context): CKAN context, including user.
        data_dict (DataDict):
            - token (str, optional): Value of API token to revoke.

    Returns:
        dict: {message: 'success'}
    """
    log.debug("Revoking API token if present.")

    # User cookie / logged in
    if (user := context.get("user", "")) != "":
        log.debug("User ID extracted from context user key")
        user_id = user
    elif user := context.get("auth_user_obj", None):
        # Handle AnonymousUser in CKAN 2.10
        if user.name != "":
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
    data_dict,  #: DataDict,
):
    """Return CKAN user and renew API token.

    Uses the user_show core action to return the user, and renews the main API token.

    Returns:
        dict: {user: ckan_user_obj, token: api_token}
    """
    log.debug("start function get_current_user_and_renew_api_token")

    if (user := context.get("user", "")) != "":
        log.debug("User ID extracted from context user key")
        user_id = user
    elif user := context.get("auth_user_obj", None):
        # Handle AnonymousUser in CKAN 2.10
        if user.name == "":
            return {
                "message": "API token is invalid or missing from Authorization header",
            }
        log.debug("User ID extracted from context auth_user_obj key")
        user_id = user.id
    else:
        return {
            "message": "API token is invalid or missing from Authorization header",
        }

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

    if _check_token_valid(context, data_dict):
        expiry = config.get("expire_api_token.default_lifetime", 3)
        units = config.get("expire_api_token.default_unit", 86400)
        token_json = util.renew_main_token(user_id, expiry, units)
        return {
            "user": user,
            "token": token_json.get("token"),
        }

    return {"message": "failed"}


@side_effect_free
def check_token_valid(
    context,  #: Context,
    data_dict,  #: DataDict,
):
    """Check if the token is valid and user is authenticated.

    Allows for verifying user auth without renewing token.
    Useful for verifying a token from microservices.

    Returns:
        bool: True if valid, False if not.
    """
    if _check_token_valid(context, data_dict):
        return True

    return False


def _check_token_valid(
    context,  #: Context,
    data_dict,  #: DataDict,
):
    """Verify the JWT API token.

    Returns:
        bool: True if valid, False if not.
    """
    log.debug("start function _check_token_valid")

    if (user_id := context.get("user", "")) != "":
        log.debug("User ID extracted from context user key")
    elif user_obj := context.get("auth_user_obj", None):
        # Handle AnonymousUser in CKAN 2.10
        if user_obj.name == "":
            return {
                "message": "API token is invalid or missing from Authorization header",
            }
        log.debug("User ID extracted from context auth_user_obj key")
        user_id = user_obj.id
    else:
        return {
            "message": "API token is invalid or missing from Authorization header",
        }

    user = None
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
        return True

    return False
