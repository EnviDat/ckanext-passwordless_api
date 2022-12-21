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
