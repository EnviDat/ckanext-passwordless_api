# CKAN Passwordless API

Extension to allow paswordless login to the CKAN API.

**This plugin is primarily intended for custom frontends built on the CKAN API.**

By using API tokens from CKAN core (>2.9), this plugin provides an authentication flow where tokens are sent to the user via email.

Based on work by @espona (Lucia Espona Pernas) for ckanext-passwordless (https://github.com/EnviDat/ckanext-passwordless).

## Config

Two variables can be set in your ckan.ini:

- passwordless_api.guidelines_url
  A link to your website guidelines.
- passwordless_api.policies_url
  A link to your website policies.
- passwordless_api.welcome_template
  Path to welcome template to render as html email
- passwordless_api.reset_key_template
  Path to reset key template to render as html email

All variables are optional:

- Omitting guidelines_url or policies_url will not include them in the welcome email.
- Omitting welcome_template or reset_key_template will use default templates.

Notes:

- It is also recommended to disable access to the API via cookie, to help prevent CSRF:
  `ckan.auth.disable_cookie_auth_in_api = true`
- Tokens should be revoked on logout using the core action (api_token_revoke).
- The configuration for API tokens can be configured in core:

```ini
api_token.nbytes = 60
api_token.jwt.decode.secret = string:YOUR_SUPER_SECRET_STRING
api_token.jwt.algorithm = HS256

# expire_api_token plugin (unit = 1 day in seconds, lifetime = 3 days)
expire_api_token.default_lifetime = 3
expire_api_token.default_unit = 86400
```
