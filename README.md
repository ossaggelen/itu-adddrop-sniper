# 🎯 İTÜ Kepler Add/Drop Sniper

> İTÜ Kepler (ÖBS) üzerinde milisaniye hassasiyetli, atomik saat senkronizasyonlu ve TCP/TLS el sıkışması önceden ısıtılmış tek atış (**Sniper Shot**) ders ekleme/bırakma otomasyonu.

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-windows%20%7C%20linux%20%7C%20macos-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

---

## ⚡ Neden Sniper Motoru?

Klasik botlar kayıt saatinde sürekli istek gönderip sunucuyu yoklar (polling/spam) veya tarayıcıda buton bekler. Ancak İTÜ Kepler sisteminde:
1. **İstek Sınırı:** Hızlı peş peşe gelen isteklere 3 saniye engeli (`VAL16`) ve aşırı istekte 1 saatlik kısıtlama (`VAL21`) uygulanır.
2. **Saat Kayması (Clock Drift):** Bilgisayar saatiniz gerçek atomik zamandan 500–900 ms geride veya ileride olabilir. Tam 14:00'da tıkladığınızı sansanız bile sunucuya göre geç kalmış olursunuz.
3. **Soğuk Bağlantı Maliyeti:** Sıfırdan bir HTTPS isteği atmak DNS + TCP + TLS el sıkışmaları nedeniyle **~170 ms** gecikme yaratır.

### 🎯 Sniper Motorunun Farkı:
- **NTP Atomik Saat Kalibrasyonu:** Bilgisayar saatiniz ile atomik zaman arasındaki farkı ($\Delta t$) milisaniyesine kadar ölçer ve telafi eder.
- **T-30s Otomatik Re-Sync:** Fırlatmaya 30 saniye kala son ve taze kalibrasyon yaparak kuvars saat kaymasını sıfırlar.
- **Önceden Isıtılmış Bağlantı (Pre-warming):** DNS ve TLS el sıkışmasını dakikalar öncesinden tamamlayıp soketi sıcak tutar. Fırlatma anında ağ gecikmesi **~170 ms'den ~3 ms'ye** iner.
- **CPU Spin-Wait Zamanlayıcı:** Son 150 ms'de işlemciyi mikrosaniye kilidine alarak tam `14:00:00.015` anında paketi hatta basar.
- **Toplu İstek (Batch Sniping):** Birden fazla dersi tek bir HTTP paketinde sunucuya göndererek tek transaction'da alır.
- **Akıllı Yedek CRN:** Asıl dersin kontenjanı doluysa (`VAL06`), 3.1 saniyelik güvenli rate-limit süresini bekleyip otomatik olarak yedek dersi ateşler.

---

## 🚀 Kurulum

1. Depoyu klonlayın:
   ```bash
   git clone https://github.com/ossaggelen/itu-adddrop-sniper.git
   cd itu-adddrop-sniper
   ```

2. Gerekli kütüphaneleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

3. Konfigürasyon dosyasını oluşturun:
   `sniper/config.example.json` dosyasını `sniper/config.json` olarak kopyalayın ve İTÜ bilgilerinizi girin:
   ```json
   {
     "account": {
       "username": "kullanici_adiniz",
       "password": "sifreniz",
       "manual_token": ""
     },
     "action": "add",
     "target": {
       "crn": "12476",
       "crns": ["12476", "12477:12478"],
       "arrival_buffer_ms": 15
     },
     "registration_time": {
       "year": 2026,
       "month": 10,
       "day": 9,
       "hour": 14,
       "minute": 0,
       "second": 0
     }
   }
   ```
   > 🔒 *Not: `config.json` dosyası `.gitignore` ile korunmaktadır, şifreniz asla GitHub'a gitmez.*

---

## 🛠️ Kullanım

### 1. Hızlı Saat & Bağlantı Hızı Kalibrasyonu
```bash
py sniper/main.py --calibrate-only
```

### 2. Canlı Prova / Test Modu (12 sn sonra simülasyon)
```bash
py sniper/main.py --test
```

### 3. Tek Ders Alma (ADD)
```bash
py sniper/main.py --action add --crn 12476 --time 14:00:00
```

### 4. Çoklu Ders Alma ve Yedek CRN (ADD Batch)
```bash
py sniper/main.py --action add --crns 12476,12477:12478,12480 --time 14:00:00
```
*(12476, 12477 ve 12480 aynı anda istenir. 12477 doluysa 3.1 sn sonra otomatik 12478 denenir).*

### 5. Ders Bırakma (DROP)
```bash
py sniper/main.py --action drop --crn 12477 --time 12:20:00
```

---

## 🔄 Klasik Mod (Spam / Polling)
Eski usul 3 saniyede bir istek spam'leyen mod için:
```bash
py src/run.py
```

---

## 📜 Lisans & Teşekkür
Bu proje MIT lisansı altındadır.  
Klasik mod ve temel Kepler oturum yapıları [Ata Türkoğlu (AtaTrkgl/itu-ders-secici)](https://github.com/AtaTrkgl/itu-ders-secici) projesinden esinlenilmiş, üzerine milisaniye hassasiyetli **Sniper Motoru** inşa edilmiştir.
