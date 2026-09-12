import zlib, struct, marshal, dis

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
            print("Found steam_manager! Decompiling / inspecting constants & functions...")
            
            # Print all functions and strings
            for const in code.co_consts:
                if isinstance(const, str):
                    print("  GLOBAL STR:", const)
                elif hasattr(const, "co_code"):
                    print(f"\n--- Function: {const.co_name} (args: {const.co_varnames[:const.co_argcount]}) ---")
                    for c2 in const.co_consts:
                        if isinstance(c2, str):
                            print(f"    STR: {c2}")
                        elif hasattr(c2, "co_code"):
                            print(f"    SUB-FUNC: {c2.co_name}")
                            for c3 in c2.co_consts:
                                if isinstance(c3, str):
                                    print(f"      STR: {c3}")
