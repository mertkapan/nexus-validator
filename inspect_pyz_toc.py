import zlib, struct, marshal, os

exe_path = r"C:\Users\Muhammed\Downloads\steam-account-checker-main\steam-account-checker-main\Steam_Checker.exe"
with open(exe_path, "rb") as f:
    f.seek(14789978) # PYZ pos
    magic = f.read(4) # PYZ\0
    pyc_magic = f.read(4)
    toc_pos = struct.unpack("!i", f.read(4))[0]
    print("TOC pos:", toc_pos)
    f.seek(14789978 + toc_pos)
    toc = marshal.load(f)
    print("Total modules in PYZ:", len(toc))
    
    # Let's list non-standard modules
    interesting = []
    for name in toc.keys():
        if not name.startswith("_") and not any(name.startswith(p) for p in ["encodings", "email", "http", "urllib", "asyncio", "ctypes", "logging", "importlib", "collections", "unittest", "distutils", "pkg_resources"]):
            interesting.append(name)
    print("Interesting modules:", interesting)

    # Let's extract any checker or steam module
    for name in interesting:
        if any(k in name.lower() for k in ["steam", "check", "main", "auth", "api"]):
            ispkg, pos, length = toc[name]
            f.seek(14789978 + pos)
            decomp = zlib.decompress(f.read(length))
            code = marshal.loads(decomp)
            print(f"\n--- Code object for {name} ---")
            # print code constants that are strings
            strings = [c for c in code.co_consts if isinstance(c, str)]
            for s in strings:
                if any(x in s for x in ["http", "steam", "guard", "valid", "game", "ban", "key"]):
                    print("   ", s[:100])
