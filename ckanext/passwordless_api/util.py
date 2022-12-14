"""Separated helper utils to keep logic file clean."""

import logging
from datetime import datetime, timedelta
from re import match as regexmatch
from uuid import uuid4

from ckan import logic
from ckan.lib.redis import connect_to_redis
from ckan.plugins import toolkit
from dateutil import parser as dateparser

log = logging.getLogger(__name__)


def email_is_valid(email):
    """Match an email against regex for validation."""
    if email:
        if regexmatch(r"^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$", email):
            return True
    return False


def get_user_id(email):
    """
    Return the CKAN user id with the given email address.

    Returns:
        str: A CKAN user id
    """
    # make case insensitive
    email = email.lower()

    try:
        # Email filter option doesn't seem to work, so used q filter instead
        users = toolkit.get_action("user_list")(data_dict={"q": email})
    except toolkit.NotAuthorized:
        raise toolkit.NotAuthorized(f"Exception (Not Authorized) email={email}")

    if users:
        user = users[0]
        return user.id
    return None


def get_user(email):
    """
    Get the CKAN user with the given email address.

    Returns:
        dict: A CKAN user dict.
    """
    id = get_user_id(email)

    if id:
        try:
            user_dict = toolkit.get_action("user_show")(data_dict={"id": id})
            return user_dict
        except toolkit.NotAuthorized:
            raise toolkit.NotAuthorized(
                f"Exception (Not Authorized) email={email} id={str(id)}"
            )
    return None


def get_new_username(email):
    """Generate a new username and check does not exist."""
    offset = 0
    email = email.lower()
    username = generate_user_name(email)
    while offset < 100000:
        try:
            toolkit.get_action("user_show")(data_dict={"id": username})
            log.debug(f"User creation: {username} exists. Attempting next...")
        except logic.NotFound:
            log.debug(f"User creation: {username} does not exist. Creating...")
            return username
        offset += 1
        username = generate_user_name(email, offset)
    return None


def generate_user_name(email, offset=0):
    """
    Generate a user name for the given email address.

    Offset should be unique.
    """
    # unique_num = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    max_len = 99
    username = email.lower().replace("@", "-").replace(".", "_")[0:max_len]

    if offset > 0:
        str_offset = "_" + str(offset)
        username = username[: (max_len - len(str_offset))]
        username += str_offset
    return username


def generate_user_fullname(email):
    """Generate fullname from a given email address."""
    # FIXME: Generate a better user name, based on the email, but still making
    # sure it's unique.
    # return str(uuid4())
    return email.split("@")[0].replace(".", " ").title()


def generate_password():
    """Generate a random password."""
    # FIXME: Replace this with a better way of generating passwords, or enable
    # users without passwords in CKAN.
    return str(uuid4())


def renew_main_token(user_id):
    """
    Revoke and re-create API token named 'main' for a user.

    user can be either user object or user id.
    """
    log.debug("renew_main_token: Renewing API KEY token **")

    if isinstance(user_id, str):
        user_id = user_id.get("id")
        # check if there is one already and delete it
        data_dict = {"user": user_id}
        api_keys = toolkit.get_action("api_token_list")(
            context={"ignore_auth": True}, data_dict=data_dict
        )
        log.debug(
            f"renew_main_token ({data_dict[u'user']}) "
            "api_keys = {', '.join([k['name'] for k in api_keys])}"
        )
        for key in api_keys:
            if key.get("name") == "main":
                log.debug(f"renew_main_token deleting key = {key}")
                toolkit.get_action("api_token_revoke")(
                    context={"ignore_auth": True}, data_dict={"jti": key["id"]}
                )

        # generate new API KEY for user
        new_api_key = toolkit.get_action("api_token_create")(
            context={"ignore_auth": True},
            data_dict={
                "user": user_id,
                "name": "main",
            },
        )
        log.debug(f"renew_main_token new API key: {new_api_key}")
        return new_api_key["token"]
    else:
        return None


def check_reset_attempts(email):
    """Check if token reset limit exceeded by user."""
    redis_conn = connect_to_redis()
    if email not in redis_conn.keys():
        log.debug(f"Redis: first login attempt for {email}")
        redis_conn.hmset(email, {"attempts": 1, "latest": datetime.now().isoformat()})
    else:
        base = 3
        attempts = int(redis_conn.hmget(email, "attempts")[0])
        latest = dateparser.parse(redis_conn.hmget(email, "latest")[0])

        waiting_seconds = base**attempts
        limit_date = latest + timedelta(seconds=waiting_seconds)

        log.debug(
            f"Redis: wait {waiting_seconds} seconds after {attempts} attempts "
            f"=> after date {limit_date.isoformat()}"
        )

        if limit_date > datetime.now():
            msg = (
                "User should wait "
                f"{int((limit_date - datetime.now()).total_seconds())} "
                f"seconds until {limit_date.isoformat()} for a new token request"
            )
            raise logic.ValidationError({"user": msg})
        else:
            # increase counter
            redis_conn.hmset(
                email, {"attempts": attempts + 1, "latest": datetime.now().isoformat()}
            )


def check_new_user_quota():
    """Check if signup limit exceeded by user."""
    redis_conn = connect_to_redis()
    new_users_list = "new_latest_users"
    if "new_latest_users" not in redis_conn.keys():
        redis_conn.lpush(new_users_list, datetime.now().isoformat())
    else:
        # TODO: read this rom config
        max_new_users = 10
        period = 60 * 10
        begin_date = datetime.now() - timedelta(seconds=period)

        count = 0
        elements_to_remove = []

        for i in range(0, redis_conn.llen(new_users_list)):
            value = redis_conn.lindex(new_users_list, i)
            new_user_creation_date = dateparser.parse(value)
            if new_user_creation_date >= begin_date:
                count += 1
            else:
                elements_to_remove += [value]

        for value in elements_to_remove:
            redis_conn.lrem(new_users_list, value)

        if count >= max_new_users:
            log.error(f"New user temporary quota exceeded. Count: {count}")
            msg = (
                f"New user temporary quota exceeded, wait {period / 60} "
                "minutes for a new request."
            )
            raise logic.ValidationError({"user": msg})
        else:
            # add new user creation
            redis_conn.lpush(new_users_list, datetime.now().isoformat())
