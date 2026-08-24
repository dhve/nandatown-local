# Operating a shared coordinator

The town is self-hostable by design. One coordinator governs only one
set of runs, the SQLite database is the source of operational truth,
and everything an operator needs ships in this repository.

## Run it

```
TOWN_ADMIN_TOKEN=$(openssl rand -hex 16) nandatown coordinator --host 0.0.0.0 --port 8477 --db /var/lib/nandatown/town.db
```

- The admin token gates run creation, fault plans, event export, and
  finish. Hand it only to the runner or operator tooling, never to
  participants.
- Participants authenticate with per-run join tokens or portable
  identity run grants; they can never create runs or read the event
  log.
- The database file is the whole operational state. Back it up with
  sqlite3's `.backup` while the coordinator runs; restoring the file
  restores every accepted message, claim, acknowledgement, and event.

## Keep it up

Service units ship under `deploy/`:

- `deploy/nandatown-coordinator.service` for systemd (Linux):
  `cp` it to `/etc/systemd/system/`, set the environment file with
  TOWN_ADMIN_TOKEN, then `systemctl enable --now
  nandatown-coordinator`.
- `deploy/com.nandatown.coordinator.plist` for launchd (macOS):
  `cp` it to `~/Library/LaunchAgents/` and `launchctl load` it.

Point Town Pulse at the coordinator for operational history:

```
nandatown pulse --target coordinator=http://host:8477/health --count 0
```

## Quotas and abuse

The coordinator caps request bodies through FastAPI's parsing, holds
work under leases so a stalled participant cannot pin the mailbox, and
rejects identity reuse. Rate limiting beyond that belongs in the
reverse proxy in front of it (nginx or caddy), which should also
terminate TLS; the coordinator itself speaks plain HTTP on localhost.

## What an operator attests

An operator's evidence bundles are signed with the operator keystore
(`nandatown identity`); the attestation carries the operator's
portable id, so different operators' results stay separately
attributable. Publishing a bundle never makes it a certificate: one
run stays one scoped observation, whoever operated it.
