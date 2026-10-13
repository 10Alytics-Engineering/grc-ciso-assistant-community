# 10A GRC Lab deployment

Target: https://grc.10alytics.io. Ubuntu 24.04 AMD64 droplet in NYC3 and the
existing `db-postgresql-10alytics-db` PostgreSQL 17 cluster in `default-nyc3`.
No additional managed database cluster is required.

## Provision and configure

1. Create a 2 CPU / 4 GB droplet with weekly backups and David's existing SSH
   public key. Permit inbound TCP 22, 80 and 443 only. Preserve the database
   cluster's existing trusted sources; append this droplet if access is restricted.
2. Run `bootstrap.sh` as root. This installs Docker, configures the host firewall,
   disables password SSH login, and creates `/opt/ciso/db` for UID 1001.
3. Create database `grc_pool_lab` and dedicated role `grc_lab`. Grant the role
   ownership/access to this database and its public schema. Do not grant
   administrative roles or change permissions on existing application databases.
4. Copy `compose.yml` and `Caddyfile` to `/opt/ciso`. Copy `.env.example` to
   `/opt/ciso/.env`, fill secrets, and `chmod 600 /opt/ciso/.env`.
   Use the cluster's private hostname and TLS. Download its CA certificate into
   `/opt/ciso/db/ca-certificate.crt`, readable by UID 1001, for `verify-full`.
   Do not commit credentials.
   Configure `MAILGUN_API_KEY`, `MAILGUN_DOMAIN=10alyticsbusiness.ca`, and the sender.
   Email uses Mailgun's US HTTPS API through Django Anymail, avoiding the
   droplet's blocked SMTP ports. Keep the key only in the protected `.env`.
5. Publish an immutable canary tag using the CE canary GitHub workflow and set
   `TAG` to that release. The workflow also exports short-lived deployment
   archives. Download each archive with an authorized GitHub account, verify
   `sha256sum -c image.tar.gz.sha256`, then load it with
   `docker load < image.tar.gz` on the droplet. This supports private packages
   without storing a GitHub credential on the server. With loaded images, use
   `docker compose up -d --pull never`. Alternatively, supply a narrowly scoped
   read-packages credential for direct registry pulls.
6. Set the Cloudflare `grc` A record to the droplet IPv4. Use DNS-only while
   Caddy obtains its certificate; if enabling proxying, require Full (strict)
   encryption and verify the application again.
7. Run `docker compose up -d` in `/opt/ciso`. Watch backend logs until migrations
   and initial library loading finish. Create the administrator with Django's
   `createsuperuser` command using an ephemeral secret, not a persistent Compose
   superuser environment variable.

## Verify and operate

Check HTTPS, login, domain creation, evidence upload/download, background jobs,
configured email delivery, and recovery after a reboot. Never treat an SMTP
configuration placeholder as verified delivery.

`docker compose ps` and `docker compose logs --tail=100 backend huey caddy`
show health. Only Caddy publishes application ports. AI chat is disabled.

The managed database stores application records. `/opt/ciso/db` holds uploads and
Huey's SQLite queue. Weekly droplet backups cover uploads with up to a week of
potential loss. Managed Postgres backups do not include uploads. Before every
upgrade, take a logical database backup and archive `/opt/ciso/db` together.
Keep copies off the droplet and periodically test restores.

To release, record the previous tag and backup, update TAG, then run
`docker compose pull && docker compose up -d`. An image rollback does not undo
migrations; schema-changing rollback also requires the matching database backup.
Never restore an entire shared cluster over live applications to roll back this lab.

The modified source is in the public 10Alytics repository, linked from the login
page. No AGPL notices or source files are removed.
