# Security

This is a single-user local application. Keep the HTTP server bound to loopback; do not expose it through public tunnels or a reverse proxy.

Never commit `.state/`, database files, browser exports, prompts, answers, adapter keys, `.env` or logs. `.env.example` contains names and safe defaults only. The server reads the adapter key from a local file and never embeds it in `index.html`.

AI requests are explicit. The local adapter is a separate trusted component and may forward submitted exercise data to its configured provider. Do not submit confidential production data.

If a credential is accidentally committed, revoke/rotate it immediately. Deleting a file in a later commit does not remove it from Git history.

For a security issue, use GitHub private vulnerability reporting when available. Do not post credentials or personal exercise history in a public issue.
