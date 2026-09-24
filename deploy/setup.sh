#!/usr/bin/env bash
# One-time setup on the Ubuntu outreach VPS. Run as root from the copied project folder:
#   sudo bash deploy/setup.sh
# Safe to re-run. Does NOT enable the timer — do that after checking a dry run (see deploy/README.md).
set -euo pipefail

APP=/opt/tob-social

apt-get update -q
apt-get install -y -q python3-venv fonts-noto-core fonts-crosextra-caladea fonts-texgyre

id tob >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin tob

mkdir -p "$APP"
# Copy code only; .env, data/ and generated files on the server are left alone.
rsync -a --exclude .git --exclude .env --exclude data/ --exclude today.png \
      --exclude design_previews/ --exclude post_log.txt --exclude '__pycache__/' ./ "$APP"/
mkdir -p "$APP/data"

[ -d "$APP/.venv" ] || python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"

if [ ! -f "$APP/.env" ]; then
    cp "$APP/.env.example" "$APP/.env"
    echo "Created $APP/.env from the example — fill in the secrets before the first run."
fi
chown -R tob:tob "$APP"
chmod 600 "$APP/.env"

install -m 644 "$APP/deploy/tob-blessing.service" /etc/systemd/system/
install -m 644 "$APP/deploy/tob-blessing.timer" /etc/systemd/system/
systemctl daemon-reload
echo "Installed. Next: edit $APP/.env, then follow deploy/README.md."
