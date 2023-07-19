## 1.1.1 (2023-07-19)

### Fix

- welcome email logic
- response error handling

## 1.1.0 (2023-05-30)

### Feat

- add option to anonymise usernames
- add introspect endpoint, verify token only

### Refactor

- improve log message for when user is deleted
- tweak to plugin init logic
- correct link to license

## 1.0.2 (2023-04-03)

### Fix

- remove ckan.types until upgrade 2.10

## 1.0.1 (2023-04-03)

### Fix

- pin requests dep =>2.25.1 for compatibility

## 1.0.0 (2023-04-03)

### Fix

- validate azure ad token with azure /me, linting on logic
- remove azure ad config params from plugin

## 0.4.0 (2023-01-26)

### Feat

- endpoint for verifying azure ad auth code, config param validation

## 0.3.2 (2023-01-17)

### Fix

- allow silent fail of get_user endpoint, preventing 403 browser cors error

## 0.3.1 (2022-12-21)

### Fix

- pdm bundling not including ckanext dir for wheel/dist

## 0.3.0 (2022-12-18)

### Feat

- logic to allow revoke api token for current cookie (i.e. user logged in)

### Fix

- fix handling of cookie config booleans, add cookie path param

## 0.2.2 (2022-12-16)

### Fix

- add api token cookie to get_user requests also

## 0.2.1 (2022-12-16)

### Fix

- add cookie config, optional api token in cookie, typing

## 0.2.0 (2022-12-16)

### Feat

- add get_user endpoint to also renew token, tidy exceptions

## 0.1.0 (2022-12-15)

### Feat

- add passwordless api revoke endpoint, requiring no auth
- working endpoints - request reset key and api token
