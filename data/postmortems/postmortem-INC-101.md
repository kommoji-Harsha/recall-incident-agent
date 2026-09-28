# Post-Mortem: INC-101 - Checkout DB Connection Pool Exhaustion

## Incident Summary
On November 13, 2023, the `checkout-api` service experienced major downtime during a promotional flash sale event. Requests to POST /api/v1/checkout timed out, returning HTTP 500 errors to customers.

## Root Cause
The database connection pool limit for `checkout-api` was capped at 100 connections. During the traffic peak, concurrent user requests exceeded 350 req/sec, exhausting the database connection pool in under 15 seconds. Worker threads backed up waiting for database connections, leading to thread starvation and system unavailability.

## What Worked
- Increasing `max_connections` on PostgreSQL `orders-db` primary instance to 500.
- Bumping `checkout-api` connection pool size from 100 to 300 in Helm deployment configuration.

## What Didn't Work
- Restarting the `checkout-api` pods without increasing pool limits. New pods immediately exhausted their pools upon startup due to queued request backlog.

## Key Learnings & Observations
1. Flash sales require pre-warming connection pools and adjusting database max connection thresholds in advance.
2. Connection pool timeouts must be paired with circuit breakers on the API gateway layer to prevent thundering herd recovery.
