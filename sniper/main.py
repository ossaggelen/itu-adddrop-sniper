import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

# Path configurations
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if os.path.join(PROJECT_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from sniper.clock_sync import ClockSync
from sniper.connection_warmer import ConnectionWarmer
from sniper.token_helper import TokenHelper
from sniper.sniper_engine import SniperEngine

try:
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Konfigürasyon dosyası bulunamadı: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def format_ms(val: float) -> str:
    return f"{val:+.2f} ms" if val >= 0 else f"{val:.2f} ms"

def parse_crn_inputs(args, target_cfg) -> tuple[list[str], dict[str, str]]:
    """
    Parses single or multiple CRNs and creates target_crns list and backup_map.
    Supports format: '12476' or '12476:12477' (primary:backup).
    """
    raw_crn_items = []
    backup_map = {}

    # CLI has highest priority
    if args.crns:
        raw_crn_items = [c.strip() for c in args.crns.split(",") if c.strip()]
    elif args.crn:
        raw_crn_items = [args.crn.strip()]
    elif "crns" in target_cfg and isinstance(target_cfg["crns"], list) and len(target_cfg["crns"]) > 0:
        raw_crn_items = [str(c).strip() for c in target_cfg["crns"] if str(c).strip()]
    elif "crn" in target_cfg and str(target_cfg["crn"]).strip():
        raw_crn_items = [str(target_cfg["crn"]).strip()]

    target_crns = []
    for item in raw_crn_items:
        if ":" in item:
            primary, backup = item.split(":", 1)
            primary = primary.strip()
            backup = backup.strip()
            target_crns.append(primary)
            backup_map[primary] = backup
        else:
            target_crns.append(item)

    # Legacy single backup_crn support
    single_backup = str(target_cfg.get("backup_crn", "")).strip()
    if single_backup and len(target_crns) == 1 and target_crns[0] not in backup_map:
        backup_map[target_crns[0]] = single_backup

    return target_crns, backup_map

def main():
    parser = argparse.ArgumentParser(
        prog="itu-sniper",
        description="İTÜ Kepler Milisaniye Hassasiyetli Tek Atış Ders Sniper Botu"
    )
    parser.add_argument("--test", action="store_true", help="Test modu: Atışı 10 saniye sonraya ayarlar.")
    parser.add_argument("--calibrate-only", action="store_true", help="Sadece saat kalibrasyonu ve RTT ölçüp çıkar.")
    parser.add_argument("--show-browser", action="store_true", help="Tarayıcıyı görünür modda açar.")
    parser.add_argument("--action", choices=["add", "drop"], default=None, help="İşlem türü: 'add' (ekle) veya 'drop' (bırak).")
    parser.add_argument("--crn", type=str, default=None, help="Tek hedef CRN (örnek: 12476).")
    parser.add_argument("--crns", type=str, default=None, help="Virgülle ayrılmış çoklu CRN listesi (örnek: 12476,12477:12478).")
    parser.add_argument("--time", type=str, default=None, help="Hedef saat: HH:MM veya HH:MM:SS (örn: 14:00:00).")
    args = parser.parse_args()

    print("=" * 65)
    print("        [ITU KEPLER MILISECOND SNIPER ENGINE]        ")
    print("=" * 65)

    config = load_config()
    account = config.get("account", {})
    target_cfg = config.get("target", {})
    reg_time = config.get("registration_time", {})

    action = args.action or config.get("action", "add").lower()
    target_crns, backup_map = parse_crn_inputs(args, target_cfg)
    arrival_buffer_ms = float(target_cfg.get("arrival_buffer_ms", 15.0))

    if not target_crns:
        print("[HATA] Hedef CRN belirtilmemiş! Lütfen --crn, --crns veya config.json ile belirtin.")
        return

    print(f"[*] İşlem Türü              : {'DERS BIRAKMA (DROP)' if action == 'drop' else 'DERS EKLEME (ADD)'}")
    print(f"[*] Hedef Ders(ler) (CRN)   : {target_crns}")
    if action == "add" and backup_map:
        print(f"[*] Yedek CRN Eşleşmeleri   : {backup_map}")
    print(f"[*] Varış Güvenlik Payı     : +{arrival_buffer_ms:.1f} ms")

    # 1. Connection Warmer Başlat
    print("\n[1/5] [BAGLANTI] TCP/TLS Baglantisi Hazirlaniyor (Pre-warming)...")
    warmer = ConnectionWarmer()
    cold_latency = warmer.warm_up()
    warm_latency = warmer.warm_up()
    print(f"      -> Ilk Soguk Baglanti : {cold_latency:.2f} ms")
    print(f"      -> Isitilmis Baglanti : {warm_latency:.2f} ms (Tasarruf: {cold_latency - warm_latency:.2f} ms)")

    # 2. Saat Kalibrasyonu ve RTT Ölçümü
    print("\n[2/5] [ZAMAN] Saat Kalibrasyonu & RTT Olcumu Yapiliyor...")
    calib = ClockSync.calibrate(warmer.session)
    offset_ms = calib["offset_ms"]
    rtt_ms = calib["rtt_ms"]
    one_way_ms = calib["one_way_latency_ms"]

    print(f"      -> Zaman Kaynagi      : {calib['source']}")
    print(f"      -> Saat Sapmasi       : {format_ms(offset_ms)} (Yerel saat atomik zamandan bu kadar kayik)")
    print(f"      -> RTT (Ping)         : {rtt_ms:.2f} ms")
    print(f"      -> Tek Yonlu Gecikme  : {one_way_ms:.2f} ms")

    if args.calibrate_only:
        print("\n[BILGI] --calibrate-only bayragi aktif, islem sonlandirildi.")
        return

    # 3. Hedef Kayıt Zamanını Belirle
    now = datetime.now()
    if args.test:
        target_dt = now + timedelta(seconds=12)
        print(f"\n[3/5] [TEST] TEST MODU AKTIF! Hedef Zaman (Simdi + 12 sn): {target_dt.strftime('%H:%M:%S')}")
    elif args.time:
        parts = [int(p) for p in args.time.split(":")]
        hour = parts[0]
        minute = parts[1]
        second = parts[2] if len(parts) > 2 else 0
        target_dt = datetime(now.year, now.month, now.day, hour, minute, second)
        print(f"\n[3/5] [TAKVIM] Belirtilen Hedef Zaman: {target_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        target_dt = datetime(
            reg_time["year"], reg_time["month"], reg_time["day"],
            reg_time["hour"], reg_time["minute"], reg_time["second"]
        )
        print(f"\n[3/5] [TAKVIM] Planlanan Kayit Zamani: {target_dt.strftime('%Y-%m-%d %H:%M:%S')}")

    # 4. Token Yönetimi
    print("\n[4/5] [TOKEN] Yetkilendirme (Token) Hazirlaniyor...")
    token_helper = TokenHelper(
        username=account.get("username"),
        password=account.get("password"),
        manual_token=account.get("manual_token")
    )

    try:
        token = token_helper.get_token(headless=not args.show_browser)
        print("      -> Token hazir ve aktif.")
    except Exception as e:
        print(f"[HATA] Token alinamadi: {e}")
        return

    # 5. Sniper Motorunu Başlat
    engine = SniperEngine(
        session=warmer.session,
        token=token,
        target_crns=target_crns,
        backup_map=backup_map if action == "add" else None,
        arrival_buffer_ms=arrival_buffer_ms,
        action=action
    )

    fire_ts = engine.calculate_fire_timestamp(
        target_datetime=target_dt,
        offset_seconds=calib["offset_seconds"],
        rtt_seconds=calib["rtt_seconds"]
    )

    fire_dt = datetime.fromtimestamp(fire_ts)
    print(f"\n[5/5] [HEDEF] Firlatma Hesaplamasi:")
    print(f"      -> Hedef Sunucu Zamani : {target_dt.strftime('%H:%M:%S.%f')[:-3]}")
    print(f"      -> Yerel Firlatma Zamani: {fire_dt.strftime('%H:%M:%S.%f')[:-3]}")
    print(f"      -> Geri Sayim Basliyor...")

    # Geri sayım, soket sıcak tutma ve T-30s otomatik yeniden kalibrasyon
    re_calibrated = False
    while True:
        remaining = fire_ts - time.time()
        if remaining <= 1.0:
            break

        # T-30 saniye kala son ve taze saat kalibrasyonu yap (Quartz drift'i sıfırla)
        if 20.0 <= remaining <= 32.0 and not re_calibrated:
            print(f"\n      [RE-SYNC] T-30s Taze Saat Kalibrasyonu Yapiliyor...", flush=True)
            new_calib = ClockSync.calibrate(warmer.session)
            calib = new_calib
            fire_ts = engine.calculate_fire_timestamp(
                target_datetime=target_dt,
                offset_seconds=calib["offset_seconds"],
                rtt_seconds=calib["rtt_seconds"]
            )
            re_calibrated = True
            print(f"      [RE-SYNC] Guncel Offset: {format_ms(calib['offset_ms'])}, Ping: {calib['rtt_ms']:.2f} ms")

        print(f"\r      [GERI SAYIM] Kalan sure: {remaining:5.1f} sn | Soket sicak tutuluyor...", end="", flush=True)
        time.sleep(0.5)
        warmer.ensure_warm(max_idle_seconds=8.0)

    print("\n\n[!] Son 1 saniye! CPU Spin-Wait dongusune giriliyor...")
    engine.wait_and_spin(fire_ts, connection_warmer=warmer)

    # TEK ATIS (SNIPER SHOT)
    print(f"[ATES] CRN listesi {target_crns} gonderildi!")
    result = engine.send_sniper_request(target_crns)

    print("\n" + "=" * 65)
    print("                    SONUC RAPORU                    ")
    print("=" * 65)
    print(f"[*] Gonderim Zamani (UTC)  : {result.get('fired_at_utc')}")
    print(f"[*] Toplam Yanit Suresi    : {result.get('elapsed_ms'):.2f} ms")
    print(f"[*] HTTP Durum Kodu        : {result.get('status_code', 'HATA')}")
    print(f"[*] Sunucu Ham Yaniti      : {result.get('response_text', '')}")

    successful_crns, retry_backup_crns, detail_messages = engine.parse_response(result)
    print("\n[*] Detayli Durum Bildirimleri:")
    for msg in detail_messages:
        print(f"      -> {msg}")

    # Yedek CRN tetikleme (Yalnızca kontenjanı dolu olup yedeği olanlar için)
    if retry_backup_crns and action == "add":
        print("\n" + "-" * 65)
        print(f"[!] Kontenjani dolan dersler icin yedekler denenecek: {retry_backup_crns}")
        print(f"[!] Guvenli rate-limit icin 3.1 saniye bekleniyor...")
        time.sleep(engine.COOLDOWN_DELAY)
        
        print(f"[YEDEK ATES] Yedek CRN listesi {retry_backup_crns} gonderiliyor...")
        backup_result = engine.send_sniper_request(retry_backup_crns)
        print(f"[*] Yedek Yanit Suresi     : {backup_result.get('elapsed_ms'):.2f} ms")
        print(f"[*] Yedek Ham Yaniti       : {backup_result.get('response_text', '')}")
        b_success, _, b_details = engine.parse_response(backup_result)
        print("\n[*] Yedek Durum Bildirimleri:")
        for msg in b_details:
            print(f"      -> {msg}")

    print("=" * 65)
    token_helper.stop()

if __name__ == "__main__":
    main()
