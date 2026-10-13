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

## Automatic releases from main

Every push to `main` runs **Build/Push Canary Images - CE**. The workflow builds
both images with a unique date/commit/run/attempt tag and deploys them to
`https://grc.10alytics.io`. Manual runs from `main` also deploy; canary tags and
runs from other branches only publish images. A failed build never deploys.
The existing application test workflows run on pull requests; they are not a
separate gate for direct pushes to `main`.

The GitHub `production` environment must allow only the `main` branch and contain:

- Variable `GRC_DEPLOY_HOST`: the droplet IP or hostname.
- Secret `GRC_DEPLOY_SSH_KEY`: a dedicated SSH private key authorized for root on
  the droplet. Authorize its public key with the `restrict` option, which disables
  forwarding and PTYs. This key can update the application and is privileged;
  keep it scoped to the production environment.
- Secret `GRC_DEPLOY_KNOWN_HOSTS`: the droplet's verified SSH host key entry.
  Obtain the host key through an already trusted connection, never an unverified
  `ssh-keyscan` during deployment.

No permanent registry token is stored on the server. The deploy job sends its
short-lived, read-packages GitHub token over SSH and removes the temporary Docker
credential directory on exit. Application/database/email secrets stay in
`/opt/ciso/.env`.

Releases are serialized without cancelling an active deployment. An older build
is skipped if a newer commit has already reached `main`. A server-side lock also
prevents concurrent deployment scripts. The release files are staged beneath
`/opt/ciso/releases/<tag>` before `deployment/deploy.sh`:

1. Validates configuration and pulls images while the old release remains online.
2. Briefly stops the app and worker, dumps only `grc_pool_lab`, and archives the
   uploads/queue and configuration under `/opt/ciso/backups/auto-<timestamp>-<tag>`.
   It checks the dump's table of contents and archive readability before proceeding.
3. Updates `TAG`, applies database migrations explicitly, and recreates services.
4. Waits for container health, checks public HTTPS for the API and frontend, and
   verifies no migrations remain pending. The successful tag is written to
   `/opt/ciso/deployed-tag` and GitHub records the production deployment result.
5. Retains the previous release images and seven automatic backup directories.

Expect a short maintenance window during the backup, migration and restart.
Inspect failures in the workflow's **Deploy GRC Lab** job. Before migrations start,
a failure resumes the old services. Once migrations may have run, no automatic
image rollback is attempted: inspect the error and restore the matching database,
`db` archive and configuration if required. An image rollback cannot undo schema
changes. Never restore an entire shared cluster over other live applications.
Automatic backups live on the droplet; retain off-server copies and test restores
as described above. This is not a replacement for off-site recovery.

For a manual release, record the previous tag and take matching backups, update
`TAG`, then run `docker compose pull && docker compose up -d`.

The modified source is in the public 10Alytics repository, linked from the login
page. No AGPL notices or source files are removed.
