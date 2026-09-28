# Post-Mortem: INC-111 - Bad Deploy Release v3.1.0

## Incident Summary
On April 15, 2024, release `v3.1.0` of `checkout-api` broke payment routing logic for mobile clients, resulting in an 88% HTTP 500 error rate on checkout submissions.

## Root Cause
Release `v3.1.0` introduced a non-backwards-compatible schema change in `CheckoutController.ts`. Mobile app endpoints running API `v2` passed payment method objects that lacked new required fields, causing unhandled promise rejections and crashing worker pods.

## What Worked
- Executing an immediate Helm rollback (`helm rollback checkout-api`) to release `v3.0.9`. Error rates dropped to zero within 2 minutes of rollback completion.

## What Didn't Work
- Attempting to hotfix source code directly on live Kubernetes pods via `kubectl exec`. This created pod configuration drift and failed because container filesystems were read-only.

## Key Learnings & Observations
1. Schema changes in core controllers must retain backwards compatibility for legacy client versions.
2. Automated deployment rollback triggers based on error rate thresholds prevent prolonged outages.
