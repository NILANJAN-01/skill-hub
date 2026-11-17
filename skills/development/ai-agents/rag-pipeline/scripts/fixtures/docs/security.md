# Security

General security notes for the service.

## API keys

Rotate the API key from the dashboard under Settings, then update every client. Old keys stop working after 24 hours.

```bash
service keys rotate --project demo
service keys list
```

## Passwords

Passwords must be at least 12 characters. Two-factor authentication is required for administrators. Sessions expire after 8 hours of inactivity. Failed logins are rate limited to five attempts per minute per account.
