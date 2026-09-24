# Deploying the blessing worker (outreach VPS, Ubuntu)

The worker runs every 15 minutes (systemd timer). On each run it reads the control panel in the
Frappe app (**TOB Blessing Automation Settings** + approved **TOB Blessing Verse** records),
sends the Slack preview, posts at the configured time, and writes every result to
**TOB Automation Log**. Switching "Automatic posting" off in the panel stops it on the next run.

## 1. Frappe (learn.truthofbible.org)
1. Deploy the `truthofbible-ai` changes the usual way (commit → push → `git pull` → `bench migrate`).
   This adds the two DocTypes, the KJV/approval fields and the `TOB Social Worker` role.
2. Create a user, e.g. `social-worker@truthofbible.org`, give it **only** the `TOB Social Worker`
   role, and generate its API key/secret (User → Settings → API Access).
3. Open **TOB Blessing Automation Settings**: leave *Automatic posting* OFF for now, set the
   Slack Channel ID (e.g. `C0BRUBKRLE5` for #project-truthofbible) and check the post time.
4. In Slack, invite the bot to that channel: `/invite @qtt`.

## 2. VPS
```bash
# from your PC (Git Bash), in the project folder: copy the COMMITTED code only —
# git archive can't include .env or any other ignored file, so no secrets travel.
git archive --format=tar HEAD | ssh tob-vps 'rm -rf /root/tob-social-src && mkdir -p /root/tob-social-src && tar xf - -C /root/tob-social-src'
ssh tob-vps 'cd /root/tob-social-src && bash deploy/setup.sh'
ssh tob-vps 'nano /opt/tob-social/.env'   # fill in the values listed in .env.example
```

## 3. Check before switching on
```bash
ssh tob-vps
cd /opt/tob-social
sudo -u tob .venv/bin/python blessing_worker.py --status        # reaches Frappe? verses approved?
sudo -u tob .venv/bin/python blessing_worker.py --import-verses # optional: fill empty KJV text (never approves)
sudo -u tob .venv/bin/python blessing_worker.py --test-slack    # message arrives in the channel?
sudo -u tob .venv/bin/python post_blessing.py --check           # Meta token + Instagram link OK?
sudo -u tob .venv/bin/python blessing_worker.py --dry-run       # decides + renders today.png, sends nothing
```
Look at `/opt/tob-social/today.png` (fonts are Linux substitutes; check it looks right).

## 4. Switch on
```bash
systemctl enable --now tob-blessing.timer
systemctl list-timers tob-blessing.timer
```
Then tick **Automatic posting ON** in the control panel.

## Operating
| Want to | Do |
|---|---|
| Pause posting | Untick *Automatic posting ON* in the panel |
| Stop one verse | Untick its *Checked & approved* |
| See what happened | **TOB Automation Log** in the Desk, or `journalctl -u tob-blessing -n 50` |
| Is the worker alive? | *Worker Last Checked In* in the panel (should be < 30 min old) |
| Local post history | `sudo -u tob .venv/bin/python post_blessing.py --history` |
| Update the code | commit, then re-run step 2 (git archive + `bash deploy/setup.sh`) |
