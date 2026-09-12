import zlib, marshal, dis

with open(r"C:\Users\Muhammed\Downloads\steam-account-checker-main\steam-account-checker-main\Steam_Checker.exe", "rb") as f:
    f.seek(14789978 + 4478167)
    toc = marshal.load(f)
    for name, (ispkg, pos, length) in toc:
        if name == "steam_manager":
            f.seek(14789978 + pos)
            code = marshal.loads(zlib.decompress(f.read(length)))
            for c in code.co_consts:
                if hasattr(c, "co_name") and c.co_name in ["_poll_auth", "_finalize_login", "_begin_auth"]:
                    print("="*25, c.co_name, "="*25)
                    for instr in dis.get_instructions(c):
                        if instr.opname in ["LOAD_CONST", "LOAD_GLOBAL", "CALL", "STORE_FAST", "LOAD_FAST", "LOAD_METHOD", "RETURN_VALUE", "COMPARE_OP"]:
                            print(f"{instr.starts_line or ''} {instr.opname} {instr.argval}")
