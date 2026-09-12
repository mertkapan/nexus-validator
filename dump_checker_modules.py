import zlib, struct, marshal

with open(r"C:\Users\Muhammed\Downloads\steam-account-checker-main\steam-account-checker-main\Steam_Checker.exe", "rb") as f:
    f.seek(14789978 + 4478167)
    toc = marshal.load(f)
    
custom_modules = []
for item in toc:
    name, (ispkg, pos, length) = item
    if not any(name.startswith(p) for p in ["PIL", "customtkinter", "tkinter", "requests", "urllib", "chardet", "certifi", "idna", "encodings", "email", "http", "asyncio", "ctypes", "logging", "importlib", "collections", "unittest", "distutils", "pkg_resources", "xml", "json"]):
        custom_modules.append(item)

print(f"Found {len(custom_modules)} custom modules:")
for item in custom_modules:
    name, (ispkg, pos, length) = item
    print(f" - {name}")

for item in custom_modules:
    name, (ispkg, pos, length) = item
    f.seek(14789978 + pos)
    decomp = zlib.decompress(f.read(length))
    code = marshal.loads(decomp)
    
    # Let's write disassembled / constants to a log
    print(f"\n==================== {name} ====================")
    def inspect_code(co, depth=0):
        prefix = "  " * depth
        for c in co.co_consts:
            if isinstance(c, str) and len(c) > 3:
                if any(k in c.lower() for k in ["steam", "guard", "game", "ban", "valid", "login", "http", "api", "auth", "key"]):
                    print(f"{prefix}STR: {c}")
            elif hasattr(c, "co_code"):
                print(f"{prefix}SUB-FUNC: {c.co_name}")
                inspect_code(c, depth + 1)
    inspect_code(code)
