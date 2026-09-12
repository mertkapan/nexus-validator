# NEXUS v1.0.0 — 24/7 Cloud State Validator & Discord Telemetry Suite

Platform Authentication State Validator & High-Scale Telemetry Engine.

---

## ⚡ Temel Özellikler & Yenilikler

1. **Tam Otomatik Proxy Yönetimi (Auto-Harvest & Persist)**
   - 60+ global kaynaktan HTTP, SOCKS4 ve SOCKS5 proxyleri anlık olarak çeker.
   - Ölü nodeları eler, çalışanları anında `proxies.txt` dosyasına kaydeder.
   - Doğrulama sırasında arka planda sürekli çalışarak havuzu tazeler; ölü proxy ile hesap doğrulanmasını engeller.

2. **Gelişmiş Veri Temizleme & Sahte Hesap Koruması (Dirty Dump Sanitizer)**
   - Wild dump'lardaki bozuk formatları (`user:pass`, `user;pass`, `user|pass`, `email:pass:user:pass`, BOM karakterleri, null byte'lar, trailing metadata) otomatik filtreler ve temizler.
   - Sahte/çöp satırları (`username:password`, HTML tag'leri, test hesapları) eler.
   - Rate limit durumunda (`eresult=84`, `429`) hesabı INVALID saymaz; otomatik olarak temiz proxy'ye aktarıp yeniden dener.

3. **Discord Anlık Webhook Bildirimi (Hit & 2FA Alert Sink)**
   - İçinde **1 oyun**, **0 oyun (temiz hit)** veya **100+ oyun** olan tüm doğrulanmış girişleri doğrudan Discord kanalınıza gönderir.
   - Zengin Discord Embed içeriği:
     - Hesap bilgisi (`username : ||password||`)
     - SteamID64 ve profil bağlantısı
     - Toplam oyun sayısı ve ücretli oyun sayısı
     - Detaylı kütüphane oyun listesi ve oynama süreleri
     - Cüzdan bakiyesi ve para birimi
     - VAC Ban & Trade Ban durumu
     - Ülke / Bölge bayrağı ve konumu
   - Rate limit (HTTP 429) korumalı asenkron kuyruk yapısıyla hiçbir bildirimi kaçırmaz.

4. **900K+ Hesap Streaming Mimarisi & Checkpoint Kurtarma**
   - 900.000+ satırlık devasa dosyaları belleği şişirmeden streaming generator ile satır satır işler (<35MB RAM tüketimi).
   - `results/checkpoint.json` ile ilerlemeyi sürekli kaydeder. Kesinti durumunda veya iş tekrar başlatıldığında kaldığı satırdan devam eder.

5. **24/7 GitHub Actions Cloud Runner (VDS / Para Ödemeden Çalıştırma)**
   - Bilgisayarınızı kapatsanız bile GitHub Actions üzerinde ücretsiz Linux sunucularda 7/24 çalışabilir.
   - Headless mod sayesinde grafik arayüze (GUI) ihtiyaç duymadan bulutta tam verimle işler.

---

## 🚀 Kullanım Rehberi

### Yöntem A: Masaüstü Grafik Arayüzü (GUI)
```bash
python main.py
```
- **Credentials Batch**: Dosyanızı seçin (`.txt`). 900k hesap bile olsa anında streaming modunda algılanır.
- **Discord Webhook**: Webhook URL'nizi yapıştırın ve **📡 Test Webhook** butonuna basarak bağlantıyı test edin (otomatik olarak kaydedilir).
- **Threads**: Eşzamanlı worker sayısını belirleyin (Önerilen: 25 - 50).
- **▶ START ENGINE**: Tıklayın, arkaya yaslanın.

---

### Yöntem B: Headless Terminal / Arka Plan CLI
```bash
python headless.py --combos combos.txt --threads 35 --auto-scrape --resume
```
Parametreler:
- `-c`, `--combos`: Hesap dosyasının yolu (varsayılan: `combos.txt`).
- `-t`, `--threads`: Thread sayısı (varsayılan: `30`).
- `-w`, `--webhook`: Discord webhook URL'si (varsayılan: `config.json` veya ortam değişkeni).
- `--auto-scrape`: Proxyleri sürekli otomatik çek ve doğrula.
- `--resume`: `checkpoint.json` dosyasından kaldığı satırdan devam et.

---

### Yöntem C: GitHub Actions ile 24/7 Bulutta Çalıştırma (PC Kapanınca Bile Çalışır)

VDS'e para ödemeden GitHub'ın ücretsiz sunucularında 7/24 çalıştırmak için:

1. **Büyük Combo Dosyasını Parçalayın (İsteğe Bağlı - 100MB+ ise)**
   GitHub 100MB üzeri tekil dosyalara izin vermez. 900k dosyanızı GitHub uyumlu parçalara bölmek için:
   ```bash
   python scripts/split_combos.py "D:\Steam Checker\900k.txt" 150000
   ```
   Bu işlem `chunks/chunk_1.txt`, `chunks/chunk_2.txt` şeklinde temiz parçalar oluşturur.

2. **Projeyi GitHub Deponuza Yükleyin**
   Klasör içindeki `push_to_github.bat` dosyasına çift tıklayın veya:
   ```bash
   git add .
   git commit -m "NEXUS Cloud Validator"
   git push origin main
   ```

3. **Discord Webhook Secret Ekleyin**
   - GitHub deponuza gidin: **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**.
   - Name: `DISCORD_WEBHOOK_URL`
   - Value: Discord Webhook URL'nizi yapıştırın ve kaydedin.

4. **Bulut Görevini Başlatın**
   - Deponuzdaki **Actions** sekmesine tıklayın.
   - Sol taraftan **NEXUS Cloud State Validator (24/7 Headless)** seçin.
   - **Run workflow** butonuna tıklayın, thread sayısını ve dosya adını belirleyip çalıştırın!
   - Artık bilgisayarınızı kapatsanız dahi GitHub bulutunda çalışır ve tüm hitleri anında Discord kanalınıza fırlatır!
   - Çıktıları dilediğiniz zaman **Artifacts** kısmından tek tıkla (`hits.txt`, `results.json`) indirebilirsiniz.

---

## 📁 Sonuç Dosyaları (`results/`)

- `results/hits.txt` : Tek satırlık tüm hitler (0 oyunlu, 1 oyunlu ve tüm kütüphane listeli hesaplar).
- `results/hits_detailed.txt` : Hesapların tam dökümü, oyunlar, saatler ve cüzdan bilgisi.
- `results/checkpoint.json` : Anlık işlenen satır indeksi ve durum bilgisi.
- `proxies.txt` : Canlı, doğrulanmış ve çalışan proxy havuzu.
