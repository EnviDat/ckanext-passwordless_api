"""Init plugin with CKAN interfaces."""

import logging
from json import loads as load_json

from ckan.plugins import SingletonPlugin, implements, interfaces, toolkit

from ckanext.passwordless_api.logic import (
    get_current_user_and_renew_api_token,
    request_api_token,
    request_reset_key,
    revoke_api_token_no_auth,
)

log = logging.getLogger(__name__)


class PasswordlessAPIPlugin(SingletonPlugin):
    """
    PasswordlessPlugin.

    Plugin to add endpoints that allow passwordless login via email.
    """

    implements(interfaces.IConfigurer)
    implements(interfaces.IActions)
    implements(interfaces.IMiddleware)

    # IConfigurer
    def update_config(self, config):
        """Update CKAN with plugin specific config."""
        toolkit.add_template_directory(config, "templates")

        # Check cookie config
        if cookie_name := config.get("passwordless_api.cookie_name", None):
            log.debug("ckanext-passwordless_api cookies enabled")

            if not (
                cookie_domain := config.get("passwordless_api.cookie_domain", None)
            ):
                err_str = (
                    "passwordless_api.cookie_domain setting is required if "
                    "cookies are enabled"
                )
                log.error(err_str)
                raise toolkit.ObjectNotFound(err_str)

            self.cookie_name = cookie_name
            self.cookie_domain = cookie_domain
            self.cookie_path = config.get("passwordless_api.cookie_path", "/")
            self.cookie_http_only = bool(
                load_json(config.get("passwordless_api.cookie_http_only", "true"))
            )
            self.cookie_samesite = config.get("passwordless_api.cookie_samesite", "Lax")
            self.cookie_secure = bool(
                load_json(config.get("passwordless_api.cookie_secure", "true"))
            )
            token_expiry = int(config.get("expire_api_token.default_lifetime", 3))
            token_units = int(config.get("expire_api_token.default_unit", 86400))
            self.cookie_expiry = token_expiry * token_units

    # IActions
    def get_actions(self):
        """Actions to be accessible via the API."""
        return {
            "passwordless_request_reset_key": request_reset_key,
            "passwordless_request_api_token": request_api_token,
            "passwordless_revoke_api_token": revoke_api_token_no_auth,
            "passwordless_get_user": get_current_user_and_renew_api_token,
        }

    # IActions
    def make_middleware(self, app, config):
        """Create middleware for the Flask app."""

        @app.after_request
        def add_api_token_cookie(response):
            """If cookie settings in config, add API token to cookie."""
            if not config.get("passwordless_api.cookie_name", None):
                return response

            try:
                # token present in both renew_api_token and get_user
                token = load_json(response.data).get("result").get("token")
                if not token:
                    return response
            except Exception:
                return response

            log.debug(
                "Adding cookie to response with vars: "
                f"key={self.cookie_name} | value={token} | "
                f"max_age={self.cookie_expiry} | domain={self.cookie_domain} | "
                f"secure={self.cookie_secure} | httponly={self.cookie_http_only} | "
                f"samesite={self.cookie_samesite}"
            )
            response.set_cookie(
                key=self.cookie_name,
                value=token,
                max_age=self.cookie_expiry,
                domain=self.cookie_domain,
                secure=self.cookie_secure,
                httponly=self.cookie_http_only,
                samesite=self.cookie_samesite,
                path=self.cookie_path,
            )
            return response

        return app

    def make_error_log_middleware(self, app, config):
        """Create error log middleware for the Flask app."""
        return app
