# Slack setup (required)

Slack is where the results show up: the audit digest, the monthly spend report with its CSV, renewal alerts, contract review requests, the weekly health summary and every failure alert.
The workflows need a Slack app with a bot token. It takes about 5 minutes and is free.

## 1. Create the app
1. Open <https://api.slack.com/apps> and click **Create New App**, then **From scratch**.
2. Name it (for example `Northwind Bot`) and pick your workspace.

## 2. Give it permissions
1. In the app, open **OAuth & Permissions**, then **Scopes**, then **Bot Token Scopes**.
2. Add these scopes:

| Scope | Why |
|---|---|
| `chat:write` | post the messages |
| `chat:write.public` | post to public channels without being invited first (optional if you invite the bot to each channel) |
| `files:write` | upload the CSV of the spend report into the report's thread |

## 3. Install it and copy the token
1. At the top of **OAuth & Permissions**, click **Install to Workspace** and approve.
2. Copy the **Bot User OAuth Token**. It starts with `xoxb-`. Keep it secret: it goes into `.env` and into n8n, never into git.
3. If you add or change a scope later you must click **Reinstall to Workspace** for it to take effect.

## 4. Create the channels
The workflows post to channels named in the database table `app_config`:

| Key | Default | Used by |
|---|---|---|
| `slack_channel_alerts` | `#automation-alerts` | failure alerts, audit digest, contract review requests, weekly health |
| `slack_channel_reports` | `#license-reports` | monthly spend report and its CSV |
| `slack_channel_renewals` | `#license-reports` | renewal alerts |

Create the channels (or change the names), then invite the bot to each one: type `/invite @Northwind Bot` in the channel. Skip the invite if you added `chat:write.public`.
To use other channel names:
```
docker compose exec postgres psql -U licenseops -d licenseops -c \
  "update app_config set value = '\"#my-channel\"' where key = 'slack_channel_reports'"
```

## 5. Add the credential to n8n
1. In n8n open **Credentials**, **Add credential**, **Slack API**.
2. Access token: the `xoxb-...` token. Name it exactly `Slack account` (the workflow exports refer to that name).
3. Click **Test** (it should say the connection works) and save.

## 6. Check it from a terminal (optional)
```
curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" https://slack.com/api/auth.test
curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" -d channel='#automation-alerts' -d text='hello from the license ops stack' https://slack.com/api/chat.postMessage
```
`"ok":true` in both answers means the token and the channel are right.

## Common errors
| Error | Fix |
|---|---|
| `channel_not_found` | the channel does not exist, has another name in `app_config`, or is private and the bot is not in it |
| `not_in_channel` | invite the bot to the channel (or add `chat:write.public`) |
| `missing_scope` / "missing required OAuth scopes" | add the scope, then **Reinstall to Workspace** |
| `invalid_auth` | wrong or revoked token; copy the **Bot User OAuth Token** again |

## Why not slash commands?
Slash commands and interactive buttons need Slack to reach n8n from the internet. This n8n is deliberately private (localhost or Tailscale only), so the project uses the n8n chat page and webhooks for questions instead. That is on the roadmap with a signed, authenticated public endpoint.
