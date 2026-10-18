#!/bin/sh
set -eu

secret_file=${PYAO_REDIS_PASSWORD_FILE:-/run/secrets/redis_password}
if [ ! -r "$secret_file" ]; then
  echo "Se requiere un archivo de secreto Redis legible" >&2
  exit 1
fi
redis_secret=$(cat "$secret_file")
if [ -z "$redis_secret" ]; then
  echo "El secreto Redis no puede estar vacío" >&2
  exit 1
fi
umask 077
redis_hash=$(printf '%s' "$redis_secret" | sha256sum | cut -d ' ' -f 1)
unset redis_secret
printf 'user default on #%s ~* &* +@all\n' "$redis_hash" > /data/pyao-users.acl.tmp
chown redis:redis /data/pyao-users.acl.tmp
mv /data/pyao-users.acl.tmp /data/pyao-users.acl
unset redis_hash
exec /usr/local/bin/docker-entrypoint.sh "$@"
