import zlib, marshal, dis

with open(r"C:\Users\Muhammed\Downloads\steam-account-checker-main\steam-account-checker-main\Steam_Checker.exe", "rb") as f:
    f.seek(14789978 + 4478167)
    toc = marshal.load(f)
    for name, (ispkg, pos, length) in toc:
        if name == "steam_manager":
            f.seek(14789978 + pos)
            code = marshal.loads(zlib.decompress(f.read(length)))
            for c in code.co_consts:
                if hasattr(c, "co_consts"):
                    for sub in c.co_consts:
                        if hasattr(sub, "co_name") and sub.co_name == "fetch_single":
                            print("="*25, sub.co_name, "="*25)
                            for instr in dis.get_instructions(sub):
                                print(f"{instr.starts_line or ''} {instr.opname} {instr.argval}")


