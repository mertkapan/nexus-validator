import re

with open(r"C:\Users\Muhammed\Downloads\steam-account-checker-main\steam-account-checker-main\Steam_Checker.exe", "rb") as f:
    data = f.read()

urls = re.findall(b"https?://[a-zA-Z0-9./_?=&%-]+", data)
print("--- Extracted Steam URLs ---")
for u in sorted(set(urls)):
    if b"steam" in u:
        print(u.decode("ascii", errors="ignore"))

# Also search for endpoint names or function names
keywords = [b"BeginAuthSession", b"GetPasswordRSA", b"GetOwnedGames", b"IPlayerService", b"guarded", b"confirmation_type", b"IAuthenticationService"]
print("\n--- Keywords found ---")
for kw in keywords:
    if kw in data:
        print("Found keyword:", kw.decode())
