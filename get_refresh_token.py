"""
One-off: generate a Google Ads API refresh token.

Run this on your own machine, not in CI.

Setup:
    pip install google-auth-oauthlib

Then put the OAuth client JSON you downloaded from Cloud Console in the
same folder as this file, named client_secret.json, and run:

    python get_refresh_token.py

A browser window opens. Sign in with the Google account that has access
to the PBH MCC (321-743-7621). Approve the request. The refresh token
prints to your terminal.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/adwords"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", scopes=SCOPES)

# prompt="consent" forces Google to issue a fresh refresh token even if
# you've authorised this client before. Without it you can get a token
# response with no refresh_token at all.
creds = flow.run_local_server(port=8080, prompt="consent", access_type="offline")

print("\n" + "=" * 60)
print("REFRESH TOKEN:")
print(creds.refresh_token)
print("=" * 60)
print("\nStore this securely. Do not commit it, and do not paste it into chat.")
