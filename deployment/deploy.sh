#!/usr/bin/env bash
set -euo pipefail
umask 077

tag=${1:?Release tag required}
registry_user=${2:?Registry username required}
[[ "$tag" =~ ^canary-[a-zA-Z0-9-]+$ ]] || exit 2
registry_user_pattern='^[a-zA-Z0-9_-]+(\[bot\])?$'
[[ "$registry_user" =~ $registry_user_pattern ]] || exit 2
cd /opt/ciso
release="/opt/ciso/releases/$tag"
test -f "$release/compose.yml"
test -f "$release/Caddyfile"
exec 9>/opt/ciso/deploy.lock
flock -w 1200 9

export DOCKER_CONFIG
DOCKER_CONFIG=$(mktemp -d)
stopped=false
migrations_started=false
backup=""
cleanup() {
  result=$?
  trap - EXIT
  rm -rf "$DOCKER_CONFIG"
  if (( result != 0 )); then
    echo "Deployment failed. Backup (if created): $backup" >&2
    if [[ "$stopped" == true && "$migrations_started" == false ]]; then
      echo "Resuming the previous release; migrations have not started." >&2
      if [[ -f "$backup/complete" ]]; then
        cp "$backup/.env" "$backup/compose.yml" "$backup/Caddyfile" /opt/ciso/
      fi
      docker compose start || true
    elif [[ "$migrations_started" == true ]]; then
      echo "Migrations may have changed the database. Inspect before restoring a backup or reverting images." >&2
      docker compose ps || true
    fi
  fi
  exit "$result"
}
trap cleanup EXIT

# The short-lived Actions token arrives on stdin and is erased before exit.
docker login ghcr.io --username "$registry_user" --password-stdin
TAG="$tag" docker compose --project-directory /opt/ciso \
  --env-file .env -f "$release/compose.yml" config --quiet
TAG="$tag" docker compose --project-directory /opt/ciso \
  --env-file .env -f "$release/compose.yml" pull
docker pull postgres:17

previous_tag=$(sed -n 's/^TAG=//p' .env)
domain=$(sed -n 's/^DOMAIN=//p' .env)
[[ "$previous_tag" =~ ^[a-zA-Z0-9_.-]+$ ]]
[[ "$domain" =~ ^[a-zA-Z0-9.-]+$ ]]
docker run --rm -e DOMAIN="$domain" \
  -v "$release/Caddyfile:/etc/caddy/Caddyfile:ro" \
  caddy:2.11.4 caddy validate --config /etc/caddy/Caddyfile

backup="/opt/ciso/backups/auto-$(date -u +%Y%m%dT%H%M%SZ)-$tag"
install -d -m 700 "$backup"
cp .env compose.yml Caddyfile "$backup/"
printf '%s\n' "$previous_tag" > "$backup/previous-tag"

# Stop writers so the database and uploads represent the same recovery point.
stopped=true
docker compose stop --timeout 60 caddy frontend huey backend
docker run --rm --env-file .env -v /opt/ciso/db:/code/db:ro \
  postgres:17 sh -ec '
    export PGPASSWORD="$POSTGRES_PASSWORD" PGSSLMODE="$POSTGRES_SSL_MODE"
    exec pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" \
      -d "$POSTGRES_NAME" --format=custom --no-owner --no-acl
  ' > "$backup/database.dump"
test -s "$backup/database.dump"
docker run --rm -i postgres:17 pg_restore --list < "$backup/database.dump" > /dev/null
tar -czf "$backup/uploads.tar.gz" db
tar -tzf "$backup/uploads.tar.gz" > /dev/null
touch "$backup/complete"

# Keep .env in place; it contains credentials that never enter GitHub artifacts.
sed "s/^TAG=.*/TAG=$tag/" .env > .env.next
chmod 600 .env.next
mv .env.next .env
install -m 600 "$release/compose.yml" compose.yml
install -m 600 "$release/Caddyfile" Caddyfile
migrations_started=true
# Fail explicitly on migration errors; the image's startup script does not.
docker compose run --rm --no-deps --entrypoint python backend manage.py migrate --noinput
docker compose up -d --force-recreate --pull never --wait --wait-timeout 600
curl --fail --silent --show-error --retry 12 --retry-delay 5 --retry-all-errors \
  --connect-timeout 10 --max-time 20 "https://$domain/api/health/" > /dev/null
curl --fail --silent --show-error --location --retry 12 --retry-delay 5 --retry-all-errors \
  --connect-timeout 10 --max-time 20 "https://$domain/" > /dev/null
docker compose exec -T backend python manage.py migrate --check
printf '%s\n' "$tag" > /opt/ciso/deployed-tag
echo "Deployment healthy: $tag (previous: $previous_tag; backup: $backup)"

# Bound disk growth, retaining the previous images and seven recovery points.
for component in backend frontend; do
  repository="ghcr.io/10alytics-engineering/grc-ciso-assistant-community/$component"
  while IFS= read -r image_tag; do
    if [[ "$image_tag" == canary-* && "$image_tag" != "$tag" && "$image_tag" != "$previous_tag" ]]; then
      docker image rm "$repository:$image_tag" || true
    fi
  done < <(docker image ls "$repository" --format '{{.Tag}}')
done
while IFS= read -r old_backup; do
  rm -rf -- "/opt/ciso/backups/$old_backup"
done < <(find /opt/ciso/backups -mindepth 1 -maxdepth 1 -type d -name 'auto-*' \
  -printf '%f\n' | sort -r | tail -n +8)
