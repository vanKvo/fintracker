# Setting Up PostgreSQL 16 via Homebrew

## Description
Explains how to install and run a persistent, system-level PostgreSQL 16 on macOS via Homebrew — an alternative to the Docker-based Postgres described in `connect_ledger_to_shared_postgres.md`. Unlike a container, a Homebrew-managed Postgres started via `brew services` survives closing Docker Desktop and (with `RunAtLoad`) restarts automatically at login. This guide covers installing it, starting it as a background service, creating a database, and connecting to it with pgAdmin.

## Guideline
Step 1: Install PostgreSQL 16
```bash
brew install postgresql@16
```
Homebrew installs it keg-only (not symlinked onto `PATH` automatically, since multiple Postgres versions can coexist). Confirm the install and note its prefix:
```bash
brew --prefix postgresql@16
# e.g. /usr/local/opt/postgresql@16 (Intel) or /opt/homebrew/opt/postgresql@16 (Apple Silicon)
```
If `psql`/`createdb`/`initdb` aren't on your `PATH`, either add `$(brew --prefix postgresql@16)/bin` to your shell profile, or prefix every command below with that path.

Step 2: Start it as a background service
```bash
brew services start postgresql@16
```
This registers a launchd agent (`~/Library/LaunchAgents/homebrew.mxcl.postgresql@16.plist`) that starts Postgres now and at every login, using the default data directory `$(brew --prefix)/var/postgresql@16`. On first run it also runs `initdb` for you.

Verify it's accepting connections:
```bash
pg_isready -h localhost -p 5432
brew services list | grep postgresql@16   # should show "started", not "error"
```

**Troubleshooting — permission denied / service errors on a shared Mac:** If `brew --prefix`'s `var/postgresql@16` directory (or `var/log`) is owned by a different macOS user account than the one you're logged in as, `brew services start` will fail silently or loop into an `error` state, since your account can't read/write the data directory or write the log file. `sudo chown` only works if your account is in the `admin` group (`dscl . -read /Groups/admin GroupMembership` to check) — if it isn't, no password will fix it.

In that case, skip `brew services` and run Postgres as your own launchd user agent against a data directory you own:
```bash
mkdir -p ~/Library/Application\ Support/postgresql16/data
$(brew --prefix postgresql@16)/bin/initdb --locale=en_US.UTF-8 -E UTF-8 -U postgres \
  -D "$HOME/Library/Application Support/postgresql16/data"
```
Then create `~/Library/LaunchAgents/com.postgresql16.local.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.postgresql16.local</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>LC_ALL</key>
        <string>en_US.UTF-8</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>REPLACE_WITH_brew_prefix/bin/postgres</string>
        <string>-D</string>
        <string>REPLACE_WITH_HOME/Library/Application Support/postgresql16/data</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>REPLACE_WITH_HOME/Library/Logs/postgresql16.log</string>
    <key>StandardErrorPath</key>
    <string>REPLACE_WITH_HOME/Library/Logs/postgresql16.log</string>
</dict>
</plist>
```
Replace the `REPLACE_WITH_*` placeholders with your actual `brew --prefix postgresql@16` and `$HOME` paths, then load it:
```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.postgresql16.local.plist
```
The `LC_ALL` environment variable is required — without it, Postgres can fail to start under launchd with `FATAL: postmaster became multithreaded during startup`, a known macOS locale-resolution issue. To stop/restart this variant, use `launchctl bootout gui/$(id -u) <plist path>` / `launchctl bootstrap gui/$(id -u) <plist path>` instead of `brew services`.

Step 3: Create a new database
```bash
createdb -h localhost -p 5432 -U postgres <database_name>
```
Or from `psql`:
```bash
psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE <database_name>;"
```
For the Ledger service specifically, the expected database name is `fintracker` — see `connect_ledger_to_shared_postgres.md` for pointing `services/fintracker-ledger/.env` at it.

If you initialized with `initdb -U postgres` (Step 2's troubleshooting path), a `postgres` superuser role with a password already exists if you passed `--pwfile`; otherwise set one:
```bash
psql -h localhost -p 5432 -U postgres -c "ALTER USER postgres PASSWORD '<password>';"
```
The default `brew services` path (no `-U postgres` override) instead creates a superuser role matching your macOS username, with no password (trust auth for local connections) — use that username instead of `postgres` if you went that route.

Step 4: Connect with pgAdmin
1. Install pgAdmin if you don't have it: `brew install --cask pgadmin4`, or download from [pgadmin.org](https://www.pgadmin.org/download/).
2. Open pgAdmin, right-click **Servers** → **Register** → **Server...**
3. **General** tab: give it a name, e.g. `fintracker-local`.
4. **Connection** tab:
   - Host name/address: `localhost`
   - Port: `5432`
   - Maintenance database: `postgres`
   - Username: `postgres` (or your macOS username, per Step 3)
   - Password: whatever you set in Step 3 (leave blank if using trust auth)
   - Check **Save password** if you don't want to re-enter it each time
5. Click **Save**. pgAdmin connects and lists all databases on the instance, including any created in Step 3 — expand **Databases** in the tree to browse tables, run queries, etc.

Step 5: Manage the service
```bash
brew services stop postgresql@16      # stop
brew services restart postgresql@16   # restart (e.g. after a config change)
brew services info postgresql@16      # check status
```
If you're on the custom-LaunchAgent path from Step 2's troubleshooting section, use `launchctl bootout`/`bootstrap` as shown there instead — `brew services` doesn't know about that agent.

Logs: `brew services`-managed instances log to `$(brew --prefix)/var/log/postgresql@16.log`; the custom LaunchAgent path logs to whatever `StandardOutPath`/`StandardErrorPath` you configured (e.g. `~/Library/Logs/postgresql16.log`).
