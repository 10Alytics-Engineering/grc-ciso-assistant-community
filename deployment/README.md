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
is skipped if a newer commit has reached `main`. A server lock also serializes
manual rehearsals and CI releases.

### Blue/green web deployments

`deployment/deploy.py` alternates between `grc-blue` and `grc-green` Compose
projects using `compose.slot.yml`. Both slots share the managed PostgreSQL
database and `/opt/ciso/db`. Each slot has a private network; its web containers
also join the existing proxy network with unique `backend-blue`/`frontend-blue`
(or green) aliases. This avoids changing the DNS names used by the legacy stack
while converting an existing installation.

The existing `grc-caddy-1` container stays running with **unchanged configuration**
throughout ordinary deployments. Two small CoreDNS containers serve the selected
backend/frontend addresses from an atomically updated hosts file. Caddy's dynamic
upstream discovery refreshes these addresses every second. This avoids the TLS
handshake resets observed when reloading Caddy 2.11.4 under live probes.
The DNS service is internal only and publishes no host ports.

See [Caddy dynamic upstreams](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#dynamic-upstreams)
and [CoreDNS hosts reloads](https://coredns.io/plugins/hosts/).

Each release:

1. Pull images and check for unapplied database migrations **without applying
   them**. If any are pending, fail the release and keep the current site live.
2. Take online backups, refresh framework libraries, and start the inactive web
   slot. Check both container health and access from the proxy's network.
3. Preserve the current and candidate frontend's hashed assets in Caddy's
   persistent `/data/grc-assets` directory so existing browser tabs can still
   load their JavaScript after a switch.
4. Validate the new worker, send the old Huey consumer SIGINT, and let its running
   tasks finish. Start one new worker only after the old one exits. Tasks can
   queue briefly during this handover; HTTP stays available. If draining exceeds
   five minutes, fail without forcibly killing in-flight tasks.
5. Atomically update `/opt/ciso/routing/hosts` to select the healthy candidate.
   No proxy reload or restart occurs. Confirm the API and login page return
   HTTP 200 and their diagnostic `X-GRC-Upstream` headers identify the candidate
   container addresses. Save
   the active slot in `/opt/ciso/deployment-state.json` and version in
   `/opt/ciso/deployed-tag`.
6. Keep the previous web slot running for rollback and existing requests. It is
   recycled at the next deployment, after at least a five-minute drain window.
   Keep the two release images and seven complete automatic backups.

Failures before cutover leave the live route untouched. Failures during cutover
restore the previous routing addresses and worker; no database restore is
performed. The first release automatically converts the legacy stack to blue.
The following release retires the legacy application containers while preserving
Caddy. Its certificate volumes and network remain in place.

### Database and recovery limits

Schema changes must use a separately reviewed, backwards-compatible
expand/contract migration: add new structures first, deploy code compatible with
both schemas, and remove old structures only after the old release is retired.
The automatic deployment intentionally fails on pending migrations; it never
runs destructive or locking migrations under active traffic. Queue payloads and
library changes must also remain compatible with the previous version during
handover. Library refreshes are normal online data updates and are not undone
by an image rollback.

PostgreSQL dumps are transactionally consistent. Uploads are archived while the
site remains writable, retrying if files change during the archive. Huey's
SQLite queue uses SQLite's online backup API. These are separate snapshots, not
one atomic snapshot across all three stores. Keep off-server backups, and test
recovery with the managed database and uploaded evidence together. Deployment
backups are kept on the droplet; they do not replace off-site recovery.

This removes the planned interruption for compatible web releases. A single
server still has downtime during a host failure/reboot or proxy-container
upgrade. Long-lived streams beyond the five-minute drain window require a
longer drain policy. Host-level high availability needs another server and load
balancing.

### Operations

Inspect GitHub's **Deploy GRC Lab** job and the active slot:

```bash
cat /opt/ciso/deployment-state.json
docker ps --filter name=grc-
docker logs --tail=100 grc-caddy-1
```

Use slot-specific container logs, e.g. `docker logs grc-blue-backend-1`.
Do not run `docker compose up` or `down` on the legacy `/opt/ciso/compose.yml`
after conversion: it is retained for bootstrap/reference and proxy inspection,
not application releases. Never stop or recreate Caddy to deploy the web app.

For an operator-run rehearsal using already loaded images, stage `deploy.sh`,
`deploy.py`, `compose.slot.yml`, `Caddyfile.slot`, `compose.routing.yml`, and `Corefile` in
`/opt/ciso/releases/<tag>`, then run:

```bash
bash /opt/ciso/releases/<tag>/deploy.sh <tag> <github-user> --loaded-images
```

This takes the same deployment lock and runs the same backup, readiness,
worker-handover, cutover and rollback logic.

### One-time routing setup

Before the first blue/green deployment on a new server, stage the same release
files and run `deploy.sh <tag> <github-user> --setup-routing-only`. This starts the
two resolvers, initially pointing them at the currently running web containers,
preserves frontend assets, validates the stable proxy configuration, and applies
it once. This infrastructure conversion can reset an in-progress TLS handshake;
perform it before the deployment availability measurement. Subsequent routine
releases never reload Caddy. If the routing template, resolver addresses, image,
or Corefile changes, the release fails before touching the app until routing
infrastructure is explicitly updated with the setup command.

Never restore the entire shared
PostgreSQL cluster to roll back this application.

The modified source is in the public 10Alytics repository, linked from the login
page. No AGPL notices or source files are removed.
