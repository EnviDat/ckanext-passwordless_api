"""Init plugin with CKAN interfaces."""

import logging

from ckan.plugins import SingletonPlugin, implements, interfaces, toolkit

from ckanext.passwordless_api.logic import (
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

    implements(interfaces.IActions)
    implements(interfaces.IConfigurer)

    # IConfigurer
    def update_config(self, _config):
        """Update CKAN with plugin specific config."""
        toolkit.add_template_directory(_config, "templates")

    # IActions
    def get_actions(self):
        """Actions to be accessible via the API."""
        return {
            "passwordless_request_reset_key": request_reset_key,
            "passwordless_request_api_token": request_api_token,
            "passwordless_revoke_api_token": revoke_api_token_no_auth,
        }
