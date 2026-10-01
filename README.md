# blimpsim

Digital twin of a person-tracking camera blimp: a simulated hall, crowd and blimp whose camera feed drives and trains a tracking controller.

## Quick start

```bash
./setup.sh          # creates .env, then brings the stack up
```

Fill in `VONK_KEY` and `DB_PASSWORD` in `.env` when it asks, then run it again.

- Frontend: `https://$APP_DOMAIN`
- API health: `https://$API_DOMAIN/api/health`

See `CLAUDE.md` for architecture, tests and day-to-day commands.
