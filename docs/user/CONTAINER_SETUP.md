# Container Setup Guide — Docker or Podman (macOS, Linux, Windows)

Run the whole app in containers. You do **not** need Python, pip, or a virtual environment on your computer. One command builds the image and starts two services:

| Service | URL | What it is |
|---|---|---|
| `web` | **http://localhost:8000** | HTML front end + JSON API (primary UI) |
| `streamlit` | http://localhost:8501 | Legacy Streamlit UI (same data) |

Both services share one data volume, so edits in one UI show up in the other. Both ports are published on `127.0.0.1` only. The app holds sensitive financial data and has no login, so nothing else on your network can reach it.

> Prefer a native Python install instead? See the [Quick Start](QUICKSTART.md).

---

## 1. Pick a container platform

Any one of these works. The scripts auto-detect what you have (Podman first, then Docker).

| Platform | macOS | Linux | Windows |
|---|---|---|---|
| **Docker Desktop** | yes | yes | yes (WSL2 backend) |
| **Rancher Desktop** (dockerd/moby mode) | yes | yes | yes |
| **Colima** / **OrbStack** | yes | — | — |
| **Docker Engine** (+ compose plugin) | — | yes | — |
| **Podman** (+ `podman-compose`) | yes | yes | yes (WSL2) |

Podman users also need `podman-compose` (`brew install podman-compose` or `pip install podman-compose`). Docker users need the **Compose v2 plugin** (`docker compose version` must work) or the older `docker-compose`.

### Resources

Monte Carlo is CPU-bound. Give the container VM at least **4 CPUs and 4 GB RAM**, and about 5 GB of free disk space for the image and volume (the image is roughly 900 MB).

- Docker Desktop / Rancher Desktop: Settings → Resources (or Virtual Machine).
- Podman: `podman machine set --cpus 4 --memory 4096` (stop the machine first).

---

## 2. Install prerequisites

### macOS

```bash
# Option A: Podman
brew install podman podman-compose
podman machine init        # one time
podman machine start

# Option B: Docker Desktop, Rancher Desktop, Colima or OrbStack
brew install --cask docker           # Docker Desktop (or install one of the others)
```

### Linux

- **Docker Engine:** follow https://docs.docker.com/engine/install/, then run `sudo usermod -aG docker $USER` and log out and in again. Check that `docker compose version` works.
- **Podman:** `sudo apt install podman podman-compose` (Debian/Ubuntu) or `sudo dnf install podman podman-compose` (Fedora/RHEL). Rootless Podman works. No VM is needed on Linux.

### Windows

1. Turn on WSL2 if the platform asks for it (`wsl --install` in an administrator PowerShell, then reboot).
2. Install **one** of:
   - **Docker Desktop** (WSL2 backend), then start it.
   - **Podman:** `winget install RedHat.Podman` and `pip install podman-compose`, then `podman machine init` and `podman machine start`.
3. Install **Git for Windows** (https://git-scm.com/), or download the repository ZIP and extract it.

> If you clone the repository on Windows, Git keeps the shell scripts on LF line endings (`.gitattributes`). If you edit them yourself, keep LF. CRLF breaks `docker-entrypoint.sh` inside the Linux container.

---

## 3. Get the code

```bash
git clone https://github.com/yourusername/retirement_planning.git
cd retirement_planning
```

---

## 4. Start the app

| Platform | Command |
|---|---|
| macOS / Linux | `./start.sh` |
| Windows (PowerShell or Command Prompt) | `start.bat` (or `.\start.ps1` if scripts are allowed) |

On the first run the script:

1. Detects Podman or Docker, and starts the Podman machine if it is stopped.
2. Creates `.env` from `.env.example` if it is missing.
3. Builds the image (the first build takes several minutes) and starts both services.
4. Waits for the health checks and opens http://localhost:8000.

Force a runtime when you have both installed:

```bash
CONTAINER_RUNTIME=docker ./start.sh          # macOS / Linux
```
```powershell
$env:CONTAINER_RUNTIME = "docker"; .\start.ps1   # Windows
```

Without the scripts, run `docker compose up -d --build` (or `podman compose up -d --build`). `.env` **must exist first** (`cp .env.example .env` / `copy .env.example .env`). If it is missing, the container runtime creates a *directory* named `.env` and the app will not start.

### Commands

| Command | Does |
|---|---|
| `./start.sh` or `./start.sh up` | Build if needed, start, open browser |
| `./start.sh down` | Stop and remove the containers (**your data volume is kept**) |
| `./start.sh logs` | Follow the logs |
| `./start.sh restart` | Recreate the containers without rebuilding. Use this after editing `.env`. |
| `./start.sh rebuild` | Rebuild the image from scratch, then recreate (after `git pull`) |

On Windows, use `start.bat <command>` with the same names.

---

## 5. First-time configuration

1. Open http://localhost:8000 → **Settings / Configuration** and enter your names, birth dates, retirement ages, expenses, filing status and state.
2. Load holdings in **Portfolio Hub**: enter them by hand, import a CSV, or restore a backup bundle (see §7).
3. The sample file `portfolio_data_truth.sample.csv` shows the CSV format. The image does not contain your real data, so the app starts with the shipped tax tables and defaults.

### The `.env` file (optional — brokerage sync only)

The app works without any keys. Fill in `.env` only for SnapTrade or Schwab sync:

| Variable | Needed for |
|---|---|
| `ENCRYPTION_KEY` | Encrypting stored brokerage credentials. **Generate your own** and never change it afterwards, or saved logins become unreadable. |
| `SNAPTRADE_CLIENT_ID`, `SNAPTRADE_CONSUMER_KEY`, `SNAPTRADE_USER_ID`, `SNAPTRADE_USER_SECRET`, `SNAPTRADE_ENV` | SnapTrade sync |
| `SCHWAB_APP_KEY`, `SCHWAB_APP_SECRET`, `SCHWAB_CALLBACK_URL` | Schwab Direct API |

Generate an encryption key without installing Python, by using the image you just built:

```bash
docker run --rm --entrypoint python retirement-planning:local -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Replace `docker` with `podman` if that is your runtime. Paste the output into `.env` as `ENCRYPTION_KEY=...`.

**Compose reads `.env` only when the containers are created**, so after editing it run `./start.sh restart` (`start.bat restart` on Windows).

Schwab sign-in works inside the container without extra setup. After you authorize in the browser, the redirect to `https://localhost:8080/callback` is expected to fail to load. Copy the full URL from the address bar and paste it into the app.

`.env` is git-ignored and excluded from the image. It holds secrets, so never share it or commit it.

---

## 6. Where your data lives

Your data is in a **named volume**, `retirement-planning_retirement_data`, mounted at `/data` in both containers. It holds your config, holdings, SQLite databases, caches, and the app's own timestamped `.backups/`.

- `./start.sh down` and rebuilds keep it.
- It is **not** deleted unless you run `down -v` or remove the volume yourself.
- It is intentionally not a host folder. SQLite is unreliable on Windows and macOS file-sharing mounts.
- The host's `.env` is bind-mounted into `/data/.env`, so Settings → Import/Export can read and replace it.
- Do not point Docker **and** Podman at the same volume at the same time. Each platform keeps its own volumes.

Check the volume with `docker volume ls` or `podman volume ls`.

---

## 7. Back up, move, and update

### Back up and move to another machine

Use the app. Go to **Settings → Advanced → Export Configuration** and download the `.zip`. It contains settings, holdings, estate plan, history, scenarios and `.env`.

On the new machine: install a platform (§2), run `./start.sh` or `start.bat`, then use **Import Configuration**, then `./start.sh restart`. The ZIP holds `.env` **in plain text**, so keep it private. Saved brokerage logins are not included, so reconnect them on the new machine.

### Raw volume backup (optional)

macOS / Linux:

```bash
docker run --rm --entrypoint tar -v retirement-planning_retirement_data:/data -v "$PWD":/backup \
  retirement-planning:local czf /backup/retirement-data-backup.tar.gz -C /data .
```

Windows PowerShell:

```powershell
docker run --rm --entrypoint tar -v retirement-planning_retirement_data:/data -v "${PWD}:/backup" `
  retirement-planning:local czf /backup/retirement-data-backup.tar.gz -C /data .
```

Use `podman` in place of `docker` when that is your runtime.

### Update to a new version

```bash
git pull
./start.sh rebuild        # Windows: start.bat rebuild
```

Your data volume is kept. Seeding never overwrites files you already have.

### Remove everything

```bash
./start.sh down
docker volume rm retirement-planning_retirement_data    # DELETES your data. Export a backup first.
docker image rm retirement-planning:local
```

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `neither podman nor docker found` | Install a platform (§2) and open a new terminal so `PATH` refreshes. |
| `the Docker daemon is not running` | Start Docker Desktop, Rancher Desktop, Colima or OrbStack. |
| `Docker Compose not found` | Install the Compose v2 plugin (`docker compose version`). |
| `podman-compose not found` | `pip install podman-compose` or `brew install podman-compose`. |
| Podman: "Cannot connect to Podman" or machine stuck | `podman machine stop`, then `podman machine start`. If none exists, run `podman machine init` first. |
| `.env` is a directory / mount error | A compose run happened before `.env` existed. Stop, delete the `.env` directory, run the start script again. |
| Port 8000 or 8501 already in use | Stop the other program. To change ports, edit the `ports:` mappings in [`compose.yaml`](../../compose.yaml). |
| `/data is not writable` on start | The volume was created earlier by another user or runtime. Remove it (back up first) or recreate it. |
| Rootless Podman or SELinux (Fedora/RHEL): permission denied on the `.env` mount | Add `:z` to the `./.env:/data/.env` volume line in `compose.yaml`. Docker Desktop and macOS ignore it. |
| Windows: `start.ps1 cannot be loaded` (execution policy) | Use `start.bat`, which bypasses the policy for this script only. |
| Windows: `exec /app/docker-entrypoint.sh: no such file` | The script was saved with CRLF line endings. Convert it to LF (`git checkout -- docker-entrypoint.sh` with the repo's `.gitattributes`), then `rebuild`. |
| `HTTP 400 Invalid host header` when using a hostname other than `localhost` | The web service only accepts `localhost`, `127.0.0.1` and `[::1]`. Set `ALLOWED_HOSTS` in `.env` only if you deliberately expose it, and add TLS and a login in front, since the app has no authentication. |
| Slow Monte Carlo | Raise the VM CPU and memory limits (§1). |
| New `.env` values ignored | Run `./start.sh restart`. |
| Market data fails to load | The container needs outbound internet access (yfinance, SnapTrade, Schwab). Check VPN and proxy settings. |

View logs with `./start.sh logs`, or for one service: `docker compose logs web` (or `podman compose logs web`).

---

*Made with Bob*
