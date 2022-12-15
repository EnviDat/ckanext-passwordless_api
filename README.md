# CKAN Passwordless API

<div align="center">
  <em>Extension to allow paswordless login to the CKAN API.</em>
</div>
<div align="center">
  <a href="https://pypi.org/project/ckanext-passwordless_api" target="_blank">
      <img src="https://img.shields.io/pypi/v/ckanext-passwordless_api?color=%2334D058&label=pypi%20package" alt="Package version">
  </a>
  <a href="https://pypistats.org/packages/ckanext-passwordless_api" target="_blank">
      <img src="https://img.shields.io/pypi/dm/ckanext-passwordless_api.svg" alt="Downloads">
  </a>
  <a href="https://gitlabext.wsl.ch/EnviDat/ckanext-passwordless_api/-/raw/main/LICENCE" target="_blank">
      <img src="https://img.shields.io/github/license/EnviDat/ckanext-passwordless_api.svg" alt="Licence">
  </a>
</div>

---

**Documentation**: <a href="https://envidat.gitlab-pages.wsl.ch/ckanext-passwordless_api/" target="_blank">https://envidat.gitlab-pages.wsl.ch/ckanext-passwordless_api/</a>

**Source Code**: <a href="https://gitlabext.wsl.ch/EnviDat/ckanext-passwordless_api" target="_blank">https://gitlabext.wsl.ch/EnviDat/ckanext-passwordless_api</a>

---

**This plugin is primarily intended for custom frontends built on the CKAN API.**

By using API tokens from CKAN core (>2.9), this plugin provides an authentication flow where:

1. Users receive a login token via email (via reset key in core).
2. API token is returned on valid login token (reset key) submission.
3. The API token should then be included in Authorization headers from the frontend --> CKAN calls.

Based on work by @espona (Lucia Espona Pernas) for ckanext-passwordless (https://github.com/EnviDat/ckanext-passwordless).

## Config

Optional variables can be set in your ckan.ini to modify the email templates:

- **passwordless_api.guidelines_url**
  Description: A link to your website guidelines.
  Default: None, not included.
- **passwordless_api.policies_url**
  Description: A link to your website policies.
  Default: None, not included.
- **passwordless_api.welcome_template**
  Description: Path to welcome template to render as html email.
  Default: uses default template.
- **passwordless_api.reset_key_template**
  Description: Path to reset key template to render as html email
  Default: uses default template.

## Endpoints

All endpoints require a POST body.

- **passwordless_request_reset_key**
  Description: Request a login token for a given email.
  Creates user if they do not exist & sends welcome email.
  Param1: email (str).
- **passwordless_request_api_token**
  Description: Request an API token, given the email and login token (reset_key).
  Param1: email (str).
  Param2: key (str).
- **passwordless_revoke_api_token**
  Description: Revoke an API token.
  Param1: token (str).

## Notes

- It is also recommended to disable access to the API via cookie, to help prevent CSRF:
  `ckan.auth.disable_cookie_auth_in_api = true`
- The configuration for API tokens can be configured in core:

```ini
api_token.nbytes = 60
api_token.jwt.decode.secret = string:YOUR_SUPER_SECRET_STRING
api_token.jwt.algorithm = HS256

# expire_api_token plugin (unit = 1 day in seconds, lifetime = 3 days)
expire_api_token.default_lifetime = 3
expire_api_token.default_unit = 86400
```
