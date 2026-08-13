r"""Offline tests for the Claude OAuth credential refresh in collector.py.

No network and no real credentials: the paths are redirected into a temp
directory and `_post_refresh` is replaced with a fake, so the whole refresh
path can be exercised without spending a real refresh token (which rotates,
and is therefore not something a test may burn).

Run it with the collector's own venv:

    .venv\Scripts\python.exe test_refresh.py

Exits non-zero when anything fails, so it works as a pre-commit check.
"""
import json, logging, sys, time, pathlib, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import collector as c

# collector.py configures a file handler at import time; without this the tests
# would append their fake refreshes to the real collector.log and make a later
# reader think the collector had been busy at 3am.
logging.getLogger("tokentracker").handlers = [logging.NullHandler()]

tmp = pathlib.Path(tempfile.mkdtemp())
c.CREDENTIALS_PATH = tmp / ".credentials.json"
c.CANONICAL_CREDENTIALS_PATH = tmp / "secrets" / ".credentials.json"
c.REFRESH_LOCK_PATH = tmp / ".lock"

def creds(expires_in_seconds):
    return {
        "mcpOAuth": {"some-server": {"accessToken": "MCP-MUST-SURVIVE"}},
        "claudeAiOauth": {
            "accessToken": "old-access",
            "refreshToken": "old-refresh",
            "expiresAt": int((time.time() + expires_in_seconds) * 1000),
            "refreshTokenExpiresAt": int((time.time() + 20 * 86400) * 1000),
            "scopes": ["user:inference"],
            "subscriptionType": "pro",
        },
    }

def write(data):
    c.CREDENTIALS_PATH.write_text(json.dumps(data), encoding="utf-8")

def read():
    return json.loads(c.CREDENTIALS_PATH.read_text(encoding="utf-8"))

calls = []
def fake_post(refresh_token):
    calls.append(refresh_token)
    return {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 18000}
c._post_refresh = fake_post

def check(name, cond):
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        globals()["failed"] = True

# 1. Fresh token: no refresh, no network call.
write(creds(4 * 3600))
c.PROBLEMS.clear(); calls.clear()
check("fresh token is left alone", c._refresh_credentials() is False and not calls)
check("  no problem reported", not c.PROBLEMS)

# 2. Nearly expired: refreshes, stores the rotated pair, keeps mcpOAuth.
write(creds(10 * 60))
c.PROBLEMS.clear(); calls.clear()
ok = c._refresh_credentials()
after = read()
check("expiring token is refreshed", ok is True and calls == ["old-refresh"])
check("  new access token stored", after["claudeAiOauth"]["accessToken"] == "new-access")
check("  rotated refresh token stored", after["claudeAiOauth"]["refreshToken"] == "new-refresh")
check("  expiresAt moved forward", after["claudeAiOauth"]["expiresAt"] / 1000 - time.time() > 17000)
check("  mcpOAuth preserved", after["mcpOAuth"]["some-server"]["accessToken"] == "MCP-MUST-SURVIVE")
check("  scopes preserved", after["claudeAiOauth"]["scopes"] == ["user:inference"])
check("  canonical copy updated", json.loads(c.CANONICAL_CREDENTIALS_PATH.read_text())["claudeAiOauth"]["refreshToken"] == "new-refresh")
check("  lock released", not c.REFRESH_LOCK_PATH.exists())
check("  no problem reported", not c.PROBLEMS)
check("  token now reads as the new one", c._oauth_access_token() == "new-access")

# 3. Already-expired token still refreshes (not only the margin window).
write(creds(-600))
c.PROBLEMS.clear(); calls.clear()
check("expired token is refreshed", c._refresh_credentials() is True)

# 4. Refresh rejected: old credentials untouched, error reported.
c._post_refresh = lambda t: None
write(creds(10 * 60))
c.PROBLEMS.clear()
ok = c._refresh_credentials()
check("rejected refresh returns False", ok is False)
check("  old credentials untouched", read()["claudeAiOauth"]["refreshToken"] == "old-refresh")
check("  error reported", any(s == "error" for s, _ in c.PROBLEMS))
check("  lock released after failure", not c.REFRESH_LOCK_PATH.exists())
c._post_refresh = fake_post

# 5. Lock held by another run: no refresh attempted.
write(creds(10 * 60))
c.PROBLEMS.clear(); calls.clear()
c.REFRESH_LOCK_PATH.touch()
check("held lock blocks the refresh", c._refresh_credentials() is False and not calls)
check("  no problem reported for a held lock", not c.PROBLEMS)

# 6. Stale lock is cleared and the refresh proceeds.
import os
old = time.time() - c.REFRESH_LOCK_STALE_SECONDS - 60
os.utime(c.REFRESH_LOCK_PATH, (old, old))
calls.clear()
check("stale lock is broken", c._refresh_credentials() is True and calls == ["old-refresh"])

# 7. Blank credentials (the CLI-logged-out case) are not treated as refreshable.
write({"claudeAiOauth": {"accessToken": "", "refreshToken": "", "scopes": []}})
c.PROBLEMS.clear(); calls.clear()
check("blank credentials do not trigger a refresh", c._refresh_credentials() is False and not calls)

# 7b. A transient WinError 5 on the rename is retried, not treated as fatal.
#     This really happens: a scanner holding a handle on the file just written.
import os as _os
write(creds(10 * 60))
c.PROBLEMS.clear()
real_replace = _os.replace
state = {"fails": 2}
def flaky_replace(src, dst):
    if state["fails"]:
        state["fails"] -= 1
        raise PermissionError(5, "Access is denied")
    return real_replace(src, dst)
c.os.replace = flaky_replace
ok = c._refresh_credentials()
c.os.replace = real_replace
check("transient rename failure is retried", ok is True)
check("  new token landed despite the retries", read()["claudeAiOauth"]["accessToken"] == "new-access")
check("  no problem reported for a retried write", not c.PROBLEMS)

# 7c. A rename that never succeeds is fatal, and says so loudly -- the token is
#     already rotated server-side at that point.
write(creds(10 * 60))
c.PROBLEMS.clear()
c.os.replace = lambda src, dst: (_ for _ in ()).throw(PermissionError(5, "Access is denied"))
ok = c._refresh_credentials()
c.os.replace = real_replace
check("permanent rename failure returns False", ok is False)
check("  reported as an error needing a login", any(s == "error" and "not saved" in t for s, t in c.PROBLEMS))
check("  no temp file left behind", not list(c.CREDENTIALS_PATH.parent.glob("*.tokentracker.tmp")))

# 8. Missing file does not raise.
c.CREDENTIALS_PATH.unlink()
check("missing credentials file is survivable", c._refresh_credentials() is False)

if globals().get("failed"):
    print("\nFAILURES PRESENT")
    sys.exit(1)
print("\nall green")
