# Post-Mortem: INC-106 - Redis Eviction Storm on Session Cache

## Incident Summary
On January 30, 2024, an eviction storm occurred on the shared Redis cache instance, causing active user checkout sessions to be evicted prematurely.

## Root Cause
An uncompressed product catalog dataset was cached in Redis without an explicit TTL setting. As catalog writes grew, Redis reached its 8GB `maxmemory` threshold and triggered its default `volatile-lru` eviction policy. Active user session keys were evicted rapidly, causing a 92% cache miss rate and forcing a thundering herd of read queries directly onto the primary PostgreSQL database.

## What Worked
- Upgrading Redis memory allocation to 16GB and changing maxmemory eviction policy to `allkeys-lru`.
- Using `UNLINK` in batches to clear large catalog entries and enforcing a mandatory 1-hour TTL on catalog items.

## What Didn't Work
- Issuing `FLUSHALL` on Redis. Flushing all keys wiped all active cart states completely, crashing `orders-db` under the sudden database load spike.

## Key Learnings & Observations
1. Caching large catalog datasets on the same Redis instance as active session keys risks eviction cascades unless TTLs and separate namespaces are enforced.
2. Never execute `FLUSHALL` during an active incident on shared Redis nodes.
