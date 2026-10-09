# ITU Kepler Milisaniye Hassasiyetli Ders Sniper Botu

Bu modül, klasik botların yaptığı gibi sürekli istek spam'lemek yerine; **ağ gecikmesini (RTT/Ping), yerel saat kaymasını (Offset) ve TCP/TLS el sıkışma sürelerini sıfıra indirerek** kayıt kapısının açıldığı ilk milisaniyede (`14:00:00.015`) tek ve kusursuz bir kayıt isteği (**Sniper Shot**) göndermek üzere tasarlanmıştır.

---

## 🎯 Temel Yetenekler ve Avantajlar

1. **Atomik Saat Kalibrasyonu (NTP / Offset):**
   - Bilgisayarınızın saati ile İTÜ atomik saati arasındaki farkı milisaniyesine kadar ölçer (Örn: bilgisayarınız ~900 ms gerideyse, sistem bunu otomatik olarak hesaba katar).
2. **T-30s Otomatik Yeniden Kalibrasyon:**
   - Bilgisayarların anakartlarındaki kuvars kristali 10-15 dakikada 5-15 ms kayabilir. Bot, seçime 30 saniye kala (`T-30s`) otomatik taze bir kalibrasyon daha yaparak son saniyelerdeki kaymayı da sıfırlar.
3. **Sıcak Bağlantı (Connection Pre-warming):**
   - Seçim saati öncesinde `obs.itu.edu.tr` ile TCP ve TLS 1.3 el sıkışmasını tamamlayarak soketi açık ve sıcak tutar.
   - İlk soğuk bağlantı süresi **~172 ms** iken, ısıtılmış bağlantı süresi **~3 ms** seviyesine iner (100ms'den fazla kazanç).
4. **CPU Spin-Wait Zamanlayıcı:**
   - Standart `time.sleep()` işletim sistemi seviyesinde 10-15 ms dalgalanır. Sniper botu son 150 ms'ye kadar uyur, son 150 ms'de ise işlemciyi mikrosaniye hassasiyetli `spin-wait` döngüsüne alarak tam hedef anda paketi hatta basar.
5. **Tek Ders ve Çoklu Ders (Batch) Desteği:**
   - İster tek bir ders, ister birden fazla ders tek bir HTTP isteğinde aynı anda sunucuya gönderilebilir.
6. **Yedek CRN Yönetimi:**
   - Asıl dersin kontenjanı doluysa (`VAL06`), 3.1 saniyelik güvenli bekleme süresinden sonra otomatik olarak tanımlı yedek CRN istenir.
7. **Ders Ekleme (ADD) ve Ders Bırakma (DROP) Desteği:**
   - Hem ders seçmek (`ECRN`) hem de ders bırakmak (`SCRN`) için kullanılabilir.
8. **İTÜ Güvenlik Limitlerine Tam Uyum:**
   - Asla erken istek atıp 3 saniye kuralını bozmaz (`VAL16`).
   - Saniyede onlarca istek yollayıp 1 saatlik engel (`VAL21`) almaz.

---

## 🚀 Kullanım Kılavuzu

### 1. Yapılandırma (`sniper/config.json`)
`sniper/config.example.json` dosyasını kopyalayarak `sniper/config.json` oluşturabilirsiniz:

```json
{
  "account": {
    "username": "ITU_KULLANICI_ADINIZ",
    "password": "ITU_SIFRENIZ",
    "manual_token": ""
  },
  "action": "add",
  "target": {
    "crn": "12476",
    "crns": ["12476", "12477:12478"],
    "backup_crn": "",
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

> **Not:** Şifrelerinizin bulunduğu `sniper/config.json` dosyası `.gitignore` ile korunmaktadır, GitHub'a yüklenmez.

---

### 2. Komut Satırı Seçenekleri

#### A. Tek Bir Dersi Almak İçin:
```powershell
py sniper/main.py --action add --crn 12476 --time 14:00:00
```

#### B. Birden Fazla Dersi Tek Seferde Almak İçin:
```powershell
py sniper/main.py --action add --crns 12476,12477:12478,12480 --time 14:00:00
```
*(Yukarıdaki örnekte `12476`, `12477` ve `12480` tek pakette istenir. Eğer `12477` kontenjanı doluysa, 3.1 sn sonra otomatik olarak `12478` denenir).*

#### C. Ders Bırakmak (DROP) İçin:
```powershell
py sniper/main.py --action drop --crn 12477 --time 12:20:00
```

#### D. Sadece Saat & Bağlantı Hızını Ölçmek İçin:
```powershell
py sniper/main.py --calibrate-only
```

#### E. 12 Saniyelik Hızlı Canlı Prova İçin:
```powershell
py sniper/main.py --test
```
