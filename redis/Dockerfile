FROM redis:8.10.2-alpine@sha256:3811787313eba226a2ef38658c6ccb91cd5e110edc89c37767de373120a0e5a0

COPY redis.conf /usr/local/etc/redis/pyao.conf
COPY --chmod=755 entrypoint.sh /usr/local/bin/pyao-redis-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/pyao-redis-entrypoint.sh"]
EXPOSE 6379
CMD ["redis-server", "/usr/local/etc/redis/pyao.conf", "--aclfile", "/data/pyao-users.acl"]
