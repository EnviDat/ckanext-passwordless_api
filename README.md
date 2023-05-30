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
  <a href="https://gitlabext.wsl.ch/EnviDat/ckanext-passwordless_api/-/raw/main/LICENSE" target="_blank">
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

A second login flow is also supported, using Azure AD:

1. User logs in with authorization code flow in frontend (@azure/msal-browser or similar).
2. Azure token is passed to azure specific endpoint.
3. Token is validated and API token for CKAN is returned.
4. The API token should then be included in Authorization headers from the frontend --> CKAN calls.

## Install

```bash
pip install ckanext-passwordless-api
```

## Config

Optional variables can be set in your ckan.ini:

- **passwordless_api.guidelines_url**
  - Description: A link to your website guidelines.
  - Default: None, not included.
- **passwordless_api.policies_url**
  - Description: A link to your website policies.
  - Default: None, not included.
- **passwordless_api.welcome_template**
  - Description: Path to welcome template to render as html email.
  - Default: uses default template.
- **passwordless_api.reset_key_template**
  - Description: Path to reset key template to render as html email
  - Default: uses default template.
- **passwordless_api.cookie_name**
  - Description: Set to place the API token in a cookie, with given name.
    The cookie will default to `secure`, `httpOnly`, `samesite: Lax`.
  - Default: None, no cookie used.
- **passwordless_api.cookie_domain**
  - Description: The domain for samesite to respect, required if cookie set.
  - Default: None.
- **passwordless_api.cookie_samesite**
  - Description: To change the cookie samesite value to `Strict`.
    Only enable this if you know what you are doing.
  - Default: None, samesite value is set to `Lax`.
- **passwordless_api.cookie_http_only**
  - Description: Use a httpOnly cookie, recommended.
  - Default: true.
- **passwordless_api.cookie_path**
  - Description: Set a specific path to use the cookie, e.g. `/api`.
  - Default: `/` (all paths).
- **passwordless_api.anonymous_usernames**
  - Description: Set to true to anonymise usernames when generated.
  - Default: false.
- **passwordless_api.anonymous_domain_exceptions**
  - Description: Email domain exceptions that should not be anonymised, if enabled.
  - Default: None.

## Endpoints

**POST**

- **<CKAN_HOST>/api/3/action/passwordless_request_reset_key**
  - Description: Request a login token for a given email.
    - Creates user if they do not exist & sends welcome email.
  - Param1: email (str).
- **<CKAN_HOST>/api/3/action/passwordless_request_api_token**
  - Description: Request an API token, given the email and login token (reset_key).
  - Param1: email (str).
  - Param2: key (str).
- **<CKAN_HOST>/api/3/action/passwordless_request_api_token_azure_ad**
  - Description: Request an API token, given the email and Azure AD token.
  - Param1: email (str).
  - Param2: token (str).
- **<CKAN_HOST>/api/3/action/passwordless_revoke_api_token**
  - Description: Revoke an API token.
  - Param1: token (str).

**GET**

- **<CKAN_HOST>/api/3/action/passwordless_revoke_api_token**
  - Description: If logged in, revoke the current API token.
- **<CKAN_HOST>/api/3/action/passwordless_get_user**
  - Description: Get user details, given their API token.
    - Also resets and returns a new API token (i.e. renewal).
    - Fails silently if the user is not logged in.
    - Use the core `user_show` action if refresh is not required.
- **<CKAN_HOST>/api/3/action/passwordless_introspect**
  - Description: Verify if the API token is valid for a user.
    - This does not renew the token in the same call.
    - Mostly useful for auth checking in microservice APIs.

## Using the cookie in an Authorization header

If configured, the cookie containing an API token can't do much on it's own.

It is possible to extract the cookie value using frontend JS and pass to the CKAN backend, but this makes your site vulnerable to XSS attacks.

Instead the cookie should be stored in a secure way:

- `samesite=Lax` with `domain=YOUR_DOMAIN` to help prevent CSRF.
  - `samesite=Strict` is even more secure, but significantly impacts UX for your site.
- `secure` to help prevent man-in-the-middle.
- `httpOnly` to help prevent XSS.
  - Setting this means the cookie can no longer be accessed from your JS code.

Then a middleware must be used to convert the cookie value into a header than CKAN can interpret:

**NGINX server example**
(nginx is the default/recommended server to reverse proxy CKAN)
(https://docs.ckan.org/en/latest/maintaining/installing/deployment.html)

```nginx
# Add the cookie-based API token to the request Authorization header
# This is passed to the CKAN backend & read automatically by CKAN
proxy_set_header 'Authorization' $cookie_${AUTH_COOKIE_NAME};

# If using caching omit the cookie
proxy_cache_bypass $cookie_${AUTH_COOKIE_NAME};
proxy_no_cache $cookie_${AUTH_COOKIE_NAME};
```

**Apache server example**

```apache
SetEnvIf Cookie "(^|;\ *)${AUTH_COOKIE_NAME}=([^;\ ]+)" ckan_cookie_value=$2
RequestHeader set Authorization "%{ckan_cookie_value}e"
```

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
