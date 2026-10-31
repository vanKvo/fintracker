# Setting Up PostgreSQL 16 via Homebrew

## Description
Explains how to install, run, stop and uninstall a PostgreSQL 16 server on macOS from Homebrew, outside Docker, and how the
server on this Mac was set up and removed on 2026-10-30.

**Current default:** the shared PostgreSQL container in `infrastructure/local-postgres/` serves the Ledger and Knowledge.
Use this guide only if you need a native server. On this Mac the Homebrew server was stopped on 2026-10-30 and its data
was copied into that container (see "Record of changes" below). Do not run both at once: only one process can bind port 5432.

## Guideline

### Step 1: Install PostgreSQL 16
```bash
brew install postgresql@16
```
Homebrew installs it keg-only, so `psql`, `initdb` and `pg_dump` are not on `PATH`. Use the full path:
```bash
brew --prefix postgresql@16
# /usr/local/opt/postgresql@16 on this Mac (Intel prefix on Apple Silicon); /opt/homebrew/opt/postgresql@16 on a default install
```
Installing needs write access to the Homebrew prefix. On this Mac that prefix is owned by the account that installed Homebrew
(`vanvo`), so a standard account such as `gabong` cannot install or upgrade there. Use that account, or have an admin fix the ownership.
Never run `brew` with `sudo`.

### Step 2: Run it as a background service

**Do not use `brew services` on this Mac yet.** With the Homebrew version installed on 2026-10-30, every `brew services`
command (`list`, `start`, `stop`, `restart`, `info`) fails with:
```
Error: undefined method 'stop_timeout' for an instance of Homebrew::Service
```
This is a Homebrew internal error, not a setup problem. Use the custom LaunchAgent below until it is fixed. Once
`brew services list` runs cleanly, `brew services start postgresql@16` is the simpler option.

**Custom LaunchAgent (used on this Mac).** It starts the server at login and restarts it if it stops.

1. Create the data directory and initialise it once:
   ```bash
   mkdir -p "$HOME/Library/Application Support/postgresql16-fintracker"
   /usr/local/opt/postgresql@16/bin/initdb --locale=en_US.UTF-8 -E UTF-8 -U postgres \
     -D "$HOME/Library/Application Support/postgresql16-fintracker/data"
   ```
2. Create `~/Library/LaunchAgents/com.fintracker.postgresql16.plist` (replace `/Users/gabong` with your home directory if it differs):
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.fintracker.postgresql16</string>
       <key>EnvironmentVariables</key>
       <dict>
           <key>LC_ALL</key>
           <string>en_US.UTF-8</string>
       </dict>
       <key>ProgramArguments</key>
       <array>
           <string>/usr/local/opt/postgresql@16/bin/postgres</string>
           <string>-D</string>
           <string>/Users/gabong/Library/Application Support/postgresql16-fintracker/data</string>
       </array>
       <key>RunAtLoad</key>
       <true/>
       <key>KeepAlive</key>
       <true/>
       <key>StandardOutPath</key>
       <string>/Users/gabong/Library/Logs/postgresql16-fintracker.log</string>
       <key>StandardErrorPath</key>
       <string>/Users/gabong/Library/Logs/postgresql16-fintracker.log</string>
   </dict>
   </plist>
   ```
   `LC_ALL` is required. Without it, launchd can fail with `FATAL: postmaster became multithreaded during startup`.
3. Load and start it:
   ```bash
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.fintracker.postgresql16.plist
   ```

On Apple Silicon, replace `/usr/local` with `/opt/homebrew` in the paths above.

### Step 3: Verify it is running
```bash
pg_isready -h localhost -p 5432
lsof -nP -iTCP:5432 -sTCP:LISTEN   # should show the postgres process, not a Docker process
```
Check the log at `~/Library/Logs/postgresql16-fintracker.log` if it does not answer.

### Step 4: Create a database
```bash
/usr/local/opt/postgresql@16/bin/psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE <database_name>;"
```
The Ledger's database is named `fintracker`. See `connect_ledger_to_shared_postgres.md` for pointing the Ledger at it.

### Step 5: Connect with pgAdmin
1. Install pgAdmin: `brew install --cask pgadmin4`, or download it from [pgadmin.org](https://www.pgadmin.org/download/).
2. Right-click **Servers** → **Register** → **Server...**.
3. **General** tab: name it, e.g. `fintracker-local`.
4. **Connection** tab: host `localhost`, port `5432`, maintenance database `postgres`, username `postgres`, and the password you set.
5. Click **Save**. Every database on the server appears under **Databases**.

### Step 6: Stop and restart
```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.fintracker.postgresql16.plist    # stop
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.fintracker.postgresql16.plist   # start again
```
Do not stop it by killing the process: `KeepAlive` restarts it. `brew services stop` does not work here (see Step 2).

### Step 7: Uninstall
Back up first. Uninstalling does not delete the data, but the data is the only copy until it is backed up or moved.

1. **Back up the databases and roles** (the server must be running):
   ```bash
   BK="$HOME/fintracker-backups/$(date +%Y-%m-%d_%H%M%S)"; mkdir -p "$BK"
   /usr/local/opt/postgresql@16/bin/pg_dumpall -h localhost -p 5432 -U postgres --globals-only > "$BK/globals.sql"
   /usr/local/opt/postgresql@16/bin/pg_dump -h localhost -p 5432 -U postgres -Fc -d fintracker -f "$BK/fintracker.dump"
   ```
   Check the dump with `pg_restore -l "$BK/fintracker.dump"` and keep the folder.
2. **Stop the agent** (Step 6, stop command).
3. **Remove the LaunchAgent**: delete `~/Library/LaunchAgents/com.fintracker.postgresql16.plist`.
4. **Remove the data and logs** only after the backup is verified: `~/Library/Application Support/postgresql16-fintracker` and `~/Library/Logs/postgresql16-fintracker.log`.
5. **Uninstall the package** (requires write access to the Homebrew prefix, see Step 1): `brew uninstall postgresql@16`.

Keep the backup folder. It is outside the repository and holds the only copy of the old data.

## Record of changes

### 2026-10-30: moved from the Homebrew server to the shared container
Run by `gabong` on this Mac:
1. Tried `brew services stop postgresql@16`. It failed with the `stop_timeout` error above. Nothing was changed.
2. Found the server on port 5432 was not a Homebrew service. It was the custom LaunchAgent `com.fintracker.postgresql16`, and it has `KeepAlive` set, so killing the process would have restarted it.
3. Stopped it with `launchctl bootout` (Step 6). Port 5432 was free. The data directory was not touched.
4. Restarted it for the backup with `launchctl bootstrap`. It contained the `fintracker` database (`ledger` schema, 35 Flyway migrations, 5 accounts, 19 categories, 5 budgets, 31 budget lines, 1 statement, 2 upcoming bills, 26 budget template lines, 4 budget templates) and the roles `app_user` and `ledger_rpt_owner`.
5. Backed up with `pg_dumpall --globals-only` and `pg_dump -Fc -d fintracker` into `~/fintracker-backups/<timestamp>/`. The dump was checked with `pg_restore -l`.
6. Started the shared container from `infrastructure/local-postgres/` (`docker compose up -d`). The first attempt failed because a single file could not be mounted inside the already-mounted init directory. The mount was moved to `/opt/fintracker/knowledge-roles.sh` and `init/20-knowledge-roles.sh` runs it.
7. Restored the `app_user` and `ledger_rpt_owner` roles from the globals dump, but not the old `postgres` superuser line, so the container keeps the password from its `.env`. Then restored the `fintracker` dump into the container's database.
8. Compared every `ledger` table's row count between the old and new databases. All matched.
9. Stopped the Homebrew agent again with `launchctl bootout`, because it had been restarted for the backup. Port 5432 is now owned by Docker only.

The Homebrew server is stopped and its plist and data directory are kept. Nothing has been uninstalled or deleted.
