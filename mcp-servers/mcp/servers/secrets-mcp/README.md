# Secrets MCP server
# MCP server for secure secrets management (1Password Connect backend).

This server exposes MCP tools (`get_secret`, `set_secret`, `list_secrets`, `delete_secret`) over HTTP.

## Required environment variables

- `OP_CONNECT_HOST`: Base URL for your 1Password Connect API, for example `http://connect-api:8080`
- `OP_CONNECT_TOKEN`: Connect access token used as `Authorization: Bearer <token>`
- `ENCRYPTION_KEY`: 32+ char local key for `encrypt_data` / `decrypt_data`

## Optional request authentication

To reduce the impact of prompt-injection or accidental exposure, you can require an auth token for the `/call` endpoint:

- Set `MCP_SECRETS_AUTH_TOKEN` in the `mcp-secrets` container environment.
- Clients must send `Authorization: Bearer <token>` on `POST /call`.

## Secret addressing (`get_secret`)

`get_secret(path, key)` supports two modes:

1. OpenClaw-style op refs:
   - `path` begins with `op://`
   - Format: `op://<Vault>/<Item>/<field>`
   - Example: `op://Personal/notion/apiKey`
2. Vault/item + key:
   - `path` is `<Vault>/<Item>`
   - `key` is the field label

## Notes

For this repo, the OpenClaw secret map already uses `op://...` refs; the goal of this MCP server is to resolve those refs via Connect (no interactive `op signin` required).

```bash
pip install -e ".[dev]"
```
