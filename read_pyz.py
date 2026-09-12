import sys, os, zlib, struct

exe_path = r"C:\Users\Muhammed\Downloads\steam-account-checker-main\steam-account-checker-main\Steam_Checker.exe"

with open(exe_path, "rb") as f:
    data = f.read()

# PyInstaller cookie is MAGIC = b'MEI\014\013\012\013\016'
MAGIC = b'MEI\x0c\x0b\n\x0b\x0e'
pos = data.rfind(MAGIC)
print("Magic pos:", pos)

if pos != -1:
    # Read cookie
    cookie = data[pos:pos+64]
    print("Cookie found! Parsing TOC...")
    # Search for compressed PYZ
    pyz_magic = b'PYZ\x00'
    pyz_pos = data.find(pyz_magic)
    print("PYZ pos:", pyz_pos)
    if pyz_pos != -1:
        # Inside PYZ is a marshal dict of table of contents
        # Let's search for python files in data
        import re
        names = re.findall(rb'[a-zA-Z0-9_\-\.]+\.py[co]?', data)
        print("Sample py files:", set(names[:20]))
