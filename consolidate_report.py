import os
import re
from pathlib import Path

BASE_DIR = Path("d:/Steam Checker")
master_accounts = {}

# 1. Parse detailed files
for path in [BASE_DIR / 'cloud_extracted/results/hits_detailed.txt', BASE_DIR / 'results/hits_detailed.txt']:
    if not path.exists():
        continue
    content = path.read_text(encoding='utf-8', errors='ignore')
    blocks = content.split('=================================================================')
    for b in blocks:
        if not b.strip():
            continue
        acc_m = re.search(r'Account:\s*(\S+)', b)
        if not acc_m:
            continue
        acc = acc_m.group(1).strip()
        status_m = re.search(r'Status:\s*([^\n\r]+)', b)
        status = status_m.group(1).strip() if status_m else 'DIRECT HIT'
        steamid_m = re.search(r'SteamID:\s*(\S+)', b)
        steamid = steamid_m.group(1).strip() if steamid_m else 'N/A'
        vac_m = re.search(r'VAC Status:\s*([^\n\r]+)', b)
        vac = vac_m.group(1).strip() if vac_m else 'CLEAN'
        games_m = re.search(r'Total Games:\s*(\d+)\s*\(Paid:\s*(\d+)\)', b)
        tot_g = games_m.group(1) if games_m else '0'
        paid_g = games_m.group(2) if games_m else '0'
        
        games = []
        for line in b.splitlines():
            line = line.strip()
            if line.startswith('[') and ']' in line and ('[Paid]' in line or '[Free]' in line):
                games.append(line)
            elif line.startswith('⭐'):
                games.append(line)

        if acc not in master_accounts or len(games) > len(master_accounts[acc].get('games', [])):
            master_accounts[acc] = {
                'account': acc,
                'status': status,
                'steamid': steamid,
                'vac': vac,
                'total_games': tot_g,
                'paid_games': paid_g,
                'games': games,
                'source': 'detailed'
            }

# 2. Parse hits_all_paid.txt
for path in [BASE_DIR / 'cloud_extracted/results/hits_all_paid.txt', BASE_DIR / 'results/hits_all_paid.txt']:
    if not path.exists():
        continue
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or '|' not in line:
                continue
            parts = [p.strip() for p in line.split('|')]
            acc = parts[0]
            tot_g = '0'
            paid_g = '0'
            games_str = ''
            vac = 'CLEAN'
            for p in parts[1:]:
                if 'Total Games:' in p:
                    m = re.search(r'Total Games:\s*(\d+)\s*\(Paid:\s*(\d+)\)', p)
                    if m:
                        tot_g, paid_g = m.group(1), m.group(2)
                elif 'Games:' in p:
                    games_str = p.replace('Games:', '').strip()
                elif 'VAC:' in p:
                    vac = p.replace('VAC:', '').strip()
            
            if acc not in master_accounts:
                games = [g.strip() for g in games_str.strip('[]').split(',') if g.strip() and g.strip() != 'None']
                master_accounts[acc] = {
                    'account': acc,
                    'status': 'VALID HIT',
                    'steamid': 'N/A',
                    'vac': vac,
                    'total_games': tot_g,
                    'paid_games': paid_g,
                    'games': games,
                    'source': 'all_paid'
                }

# 3. Parse hits.txt
for path in [BASE_DIR / 'cloud_extracted/results/hits.txt', BASE_DIR / 'results/hits.txt']:
    if not path.exists():
        continue
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or '|' not in line:
                continue
            parts = [p.strip() for p in line.split('|')]
            acc = parts[0]
            if acc not in master_accounts:
                master_accounts[acc] = {
                    'account': acc,
                    'status': 'HIT',
                    'steamid': 'N/A',
                    'vac': 'CLEAN' if 'CLEAN' in line else 'BANNED',
                    'total_games': '0',
                    'paid_games': '0',
                    'games': [],
                    'source': 'hits'
                }

print(f"Total consolidated accounts: {len(master_accounts)}")

out_path = BASE_DIR / "results/TUM_CHECK_EDILEN_HESAPLAR_VE_OYUNLARI.txt"
out_path.parent.mkdir(parents=True, exist_ok=True)

def sort_key(item):
    acc_data = item[1]
    games_joined = ' '.join(str(g) for g in acc_data['games']).lower()
    is_football = any(k in games_joined for k in ['fifa', 'fc 24', 'fc 25', 'pes', 'efootball'])
    paid_num = int(acc_data['paid_games']) if str(acc_data['paid_games']).isdigit() else 0
    return (1 if is_football else 0, paid_num)

sorted_accounts = sorted(master_accounts.items(), key=sort_key, reverse=True)

with open(out_path, 'w', encoding='utf-8') as out:
    out.write("================================================================================\n")
    out.write("         NEXUS PLATFORM DOGRULAMA - TUM HESAPLAR VE OYUN LISTESI\n")
    out.write(f"         Toplam Bulunan Gecerli Hesap: {len(master_accounts)}\n")
    out.write("================================================================================\n\n")
    
    idx = 1
    for acc, data in sorted_accounts:
        games_joined = ' '.join(str(g) for g in data['games']).lower()
        is_football = any(k in games_joined for k in ['fifa', 'fc 24', 'fc 25', 'pes', 'efootball'])
        flag = " [🚨 FIFA / PES / FC HITI]" if is_football else ""
        
        status_val = data['status']
        steamid_val = data['steamid']
        vac_val = data['vac']
        tot_val = data['total_games']
        paid_val = data['paid_games']
        
        out.write(f"[{idx:03d}] Hesap: {acc}{flag}\n")
        out.write(f"      Durum: {status_val} | SteamID: {steamid_val} | VAC: {vac_val}\n")
        out.write(f"      Oyun Sayisi: Toplam {tot_val} (Ucretli: {paid_val})\n")
        if data['games']:
            out.write("      Oyunlar:\n")
            for g in data['games']:
                out.write(f"        • {g}\n")
        else:
            out.write("      Oyunlar: [0 Oyun / Kutuphane Bos]\n")
        out.write("-" * 80 + "\n\n")
        idx += 1

print(f"Report saved to {out_path}")
