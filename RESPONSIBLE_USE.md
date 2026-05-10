# Responsible use

`ghostpress` provides a stealth-browser surface that bypasses passive
fingerprinting (TLS, navigator, canvas, WebGL, fonts, headless detection). That
capability is dual-use: it makes legitimate automation against modern
JavaScript-heavy sites possible, and it can also be misused.

## Intended use

This project is designed for situations where you have legitimate authority to
inspect or interact with a target, including but not limited to:

- Sites you own or operate.
- Sites you have explicit permission to inspect (a customer's portal you are
  contracted to integrate with, an authorized penetration test, an
  accessibility audit you have been retained to perform).
- Public, openly indexed web pages where the activity is consistent with the
  site's terms of service and applicable law.
- Sandbox targets such as `httpbin.org` and `example.com`.

## Out of scope

The maintainers do not support and will not assist with:

- Account creation farms, fake-review fleets, or other deceptive content
  generation against third-party platforms.
- Bypassing access controls, paywalls, or rate limits in violation of a site's
  terms of service.
- Aggregating personal data without a lawful basis under the applicable
  privacy regime (GDPR, CCPA, and equivalents).
- Activity that interferes with the normal operation of a service (resource
  exhaustion, denial of service).

## Operator responsibilities

Before running `ghostpress` against any target:

1. Confirm you have authority to inspect or interact with the target.
2. Read the target's terms of service and `robots.txt`. If they prohibit your
   intended use, do not proceed.
3. Set conservative concurrency. The default `--parallel 1` is intentional.
4. Persist evidence (logs, HAR, screenshots) for auditability.

By using `ghostpress` you accept sole responsibility for compliance with the
laws of your jurisdiction and the terms of any service you interact with.
