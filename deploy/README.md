# Deployment artifacts

Linux/VPS files referenced by [`../Docs/DEPLOYMENT.md`](../Docs/DEPLOYMENT.md).
Nothing here is used by local development.

| File | Install target |
|---|---|
| `nginx-vendorpulse.conf` | `/etc/nginx/sites-available/vendorpulse` (replace the example domain) |
| `vendorpulse.service` | `/etc/systemd/system/vendorpulse.service` |
| `release.sh` | run from the repo on the server (or copy to `/usr/local/bin/vendorpulse-deploy`) |
| `vendorpulse-backup.cron` | `/etc/cron.d/vendorpulse-backup` |
| `backup.cnf.example` | `/etc/vendorpulse/backup.cnf` (mode 600, real password) |

## One-time server setup

```bash
sudo apt install -y nginx mysql-server redis-server git curl \
    python3-venv python3-dev build-essential pkg-config \
    default-libmysqlclient-dev certbot python3-certbot-nginx

sudo mkdir -p /var/www/vendorpulse/{releases,shared/media}
sudo chown -R www-data:www-data /var/www/vendorpulse

sudo -u www-data python3 -m venv /var/www/vendorpulse/venv
sudo -u www-data /var/www/vendorpulse/venv/bin/pip install -r \
    /var/www/vendorpulse/current/Backend/requirements.txt

sudo install -o www-data -g www-data -m 640 \
    /var/www/vendorpulse/current/Backend/.env.example \
    /var/www/vendorpulse/shared/.env
sudo nano /var/www/vendorpulse/shared/.env   # fill in real values

sudo cp deploy/vendorpulse.service /etc/systemd/system/
sudo cp deploy/nginx-vendorpulse.conf /etc/nginx/sites-available/vendorpulse
sudo ln -s /etc/nginx/sites-available/vendorpulse /etc/nginx/sites-enabled/
sudo systemctl daemon-reload
sudo systemctl enable vendorpulse
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d vendorpulse.example.com

sudo chmod +x deploy/release.sh
sudo HEALTH_URL=http://127.0.0.1/health/ HEALTH_HOST=vendorpulse.example.com \
    ./deploy/release.sh
```

## Every release

```bash
sudo HEALTH_URL=http://127.0.0.1/health/ HEALTH_HOST=vendorpulse.example.com \
    ./deploy/release.sh
```

The script takes a `mysqldump`-able database for granted: **back up the DB
before any release that ships a migration.** Rollback is a symlink switch:

```bash
sudo ln -sfn /var/www/vendorpulse/releases/<previous> /var/www/vendorpulse/current
sudo systemctl restart vendorpulse
```
