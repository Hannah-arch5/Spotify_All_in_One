# Spotify Browser Access Failure

Observed date: 2026-10-23, Asia/Shanghai.

## Impact

The 261019 report cannot complete native transcript collection. Original
transcripts collected: 1 of 15; remaining: 14. No report was delivered or marked
seen. Existing Comet windows and user tabs were preserved.

## Reproduction

1. Connect to the existing browser extension session.
2. Create a new task tab using the documented `browser.tabs.new()` API.
3. Navigate using `tab.goto()` to
   `https://open.spotify.com/search/Dr%20Christopher%20Kerr/episodes`.

Actual result: `Host access is restricted by policy`.
The new tab exists but remains at `about:blank`. The error occurs during
navigation, before Spotify content loads. The convenience tab-creation API
produces the same result.

Expected result: honor the existing Spotify browsing permission, or expose the
specific overriding policy and the appropriate approval/remediation route.

## Confirmed Checks

- User-supplied application settings screenshot shows
  `https://open.spotify.com`: Browsing = `Always allow`.
- Local browser allowlist also contains the exact Spotify origin.
- Spotify Downloads = `Requires approval`; no download was attempted during
  the navigation failure. Full CDP access is disabled and was not changed.
- Refreshing the tool connection did not resolve the error. The user was asked
  to restart the chat application; subsequent reconnection still failed.
- No explicit browser restriction was found in the checked main user/project
  configs, local managed TOML files or standard macOS managed-preferences paths.
  This does not rule out cloud-managed or other effective policies.
- Browser numeric IDs changed between tool sessions. The extension's stable
  identity was used to select the intended existing browser after refresh.
- The documented browser troubleshooting instructions provided no further
  policy-error remediation. Local application logs did not expose the rule.

## Unknowns And Boundaries

The exact denying rule and its owner are unknown. There is insufficient
evidence to call this a Spotify failure, an application regression, an account
restriction, or a permission-cache defect. Application-side support is needed
to identify the effective rule. Do not broadly enable permissions, alter private
app state, or use another transport to circumvent the denial.

No credentials, cookies, transcript contents, or private browsing history are
included in this diagnostic report.
