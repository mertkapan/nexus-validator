import zlib, marshal, dis

exe_path = r"C:\Users\Muhammed\Downloads\steam-account-checker-main\steam-account-checker-main\Steam_Checker.exe"
with open(exe_path, "rb") as f:
    f.seek(14789978 + 4478167)
    toc = marshal.load(f)
    
    for item in toc:
        name, (ispkg, pos, length) = item
        if name == "steam_manager":
            f.seek(14789978 + pos)
            decomp = zlib.decompress(f.read(length))
            code = marshal.loads(decomp)
            
            for const in code.co_consts:
                if hasattr(const, "co_name") and const.co_name in ["_begin_auth", "_poll_auth", "_finalize_login", "_get_games", "login_account"]:
                    print(f"\n==================== DISASSEMBLY: {const.co_name} ====================")
                    dis.dis(const)
