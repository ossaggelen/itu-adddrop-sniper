import time
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Union

class SniperEngine:
    """
    High-precision course registration sniper engine.
    Supports single-course or multi-course batch sniping with backup CRNs.
    """

    COURSE_SELECTION_URL = "https://obs.itu.edu.tr/api/ders-kayit/v21/"
    COOLDOWN_DELAY = 3.1  # Safe ITU rate-limit cooldown delay in seconds (must be >= 3.0s)

    RESULT_MESSAGES = {
        "successResult": "BAŞARILI: CRN {} başarıyla alındı! 🎉",
        "Ekleme İşlemi Başarılı": "BAŞARILI: CRN {} için ekleme işlemi tamamlandı! 🎉",
        "Silme İşlemi Başarılı": "BAŞARILI: CRN {} başarıyla bırakıldı! (Silindi)",
        "VAL01": "HATA: CRN {} bir problemden dolayı alınamadı.",
        "VAL02": "ZAMAN ENGELİ (VAL02): İstek kayıt zamanı açılmadan hemen önce ulaştı.",
        "VAL03": "HATA: CRN {} bu dönem zaten alınmış.",
        "VAL04": "HATA: CRN {} ders planında yer almıyor.",
        "VAL05": "KREDİ SINIRI (VAL05): Dönemlik maksimum kredi sınırı aşıldı.",
        "VAL06": "KONTENJAN DOLU (VAL06): CRN {} için kontenjan yetersiz.",
        "Kontenjan Dolu": "KONTENJAN DOLU: CRN {} için kontenjan dolmuş.",
        "VAL08": "HATA: Program/bölüm şartı sağlanamadı.",
        "VAL09": "ÇAKIŞMA (VAL09): CRN {} başka bir dersle çakışıyor.",
        "VAL14": "SUNUCU HATASI (VAL14): Sistem geçici olarak yanıt vermiyor.",
        "VAL16": "RATE LIMIT (VAL16): Aktif işlem devam ediyor (3 sn kuralı).",
        "VAL21": "CEZA (VAL21): İstek limiti aşıldı, 1 saatlik engel tetiklendi!",
        "ERRLoad": "YOĞUNLUK: Sistem geçici olarak yanıt vermiyor.",
        "CRNListEmpty": "HATA: CRN {} listenizde bulunamadı."
    }

    def __init__(
        self,
        session,
        token: str,
        target_crns: Union[str, List[str]],
        backup_map: Optional[Dict[str, str]] = None,
        arrival_buffer_ms: float = 15.0,
        action: str = "add"
    ):
        self.session = session
        self.token = token.strip() if token.startswith("Bearer ") else f"Bearer {token.strip()}"
        
        # Handle string or list of CRNs
        if isinstance(target_crns, str):
            self.target_crns = [c.strip() for c in target_crns.split(",") if c.strip()]
        else:
            self.target_crns = [str(c).strip() for c in target_crns if str(c).strip()]

        self.backup_map = backup_map or {}
        self.arrival_buffer_ms = arrival_buffer_ms
        self.action = action.lower().strip()  # "add" or "drop"

    def calculate_fire_timestamp(
        self,
        target_datetime: datetime,
        offset_seconds: float,
        rtt_seconds: float
    ) -> float:
        """
        Calculates the exact local unix timestamp when the POST request must be launched.
        Formula:
          t_fire = target_timestamp - offset - (rtt / 2) + (buffer_ms / 1000)
        """
        target_timestamp = target_datetime.timestamp()
        one_way_latency = rtt_seconds / 2.0
        buffer_seconds = self.arrival_buffer_ms / 1000.0

        fire_timestamp = target_timestamp - offset_seconds - one_way_latency + buffer_seconds
        return fire_timestamp

    def wait_and_spin(self, fire_timestamp: float, connection_warmer=None) -> None:
        """
        Two-stage high precision timing:
        1. Coarse wait via time.sleep()
        2. Spin-wait (busy loop) via time.time() for the final 150ms.
        """
        while True:
            remaining = fire_timestamp - time.time()
            if remaining <= 0.150:
                break
            if remaining > 5.0 and connection_warmer:
                connection_warmer.ensure_warm(max_idle_seconds=10.0)
            sleep_chunk = max(0.01, remaining - 0.150)
            time.sleep(min(sleep_chunk, 1.0))

        # Spin-wait for ultimate sub-millisecond precision
        while time.time() < fire_timestamp:
            pass

    def send_sniper_request(self, crns: Union[str, List[str]]) -> Dict[str, Any]:
        """
        Sends the targeted course registration (add or drop) request for one or multiple CRNs.
        """
        if isinstance(crns, str):
            crn_list = [crns.strip()]
        else:
            crn_list = [str(c).strip() for c in crns]

        headers = {
            "Authorization": self.token,
            "Content-Type": "application/json;charset=UTF-8",
            "Referer": "https://obs.itu.edu.tr/ogrenci/DersKayitIslemleri/DersKayit",
            "Origin": "https://obs.itu.edu.tr"
        }

        if self.action == "drop":
            payload = {
                "ECRN": [],
                "SCRN": crn_list
            }
        else:
            payload = {
                "ECRN": crn_list,
                "SCRN": []
            }

        t_start = time.perf_counter()
        t_utc_fired = datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]

        try:
            response = self.session.post(
                self.COURSE_SELECTION_URL,
                headers=headers,
                json=payload,
                timeout=6.0
            )
            elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            return {
                "success": True,
                "status_code": response.status_code,
                "response_text": response.text,
                "elapsed_ms": elapsed_ms,
                "fired_at_utc": t_utc_fired,
                "crn_list": crn_list,
                "action": self.action
            }
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            return {
                "success": False,
                "error": str(e),
                "elapsed_ms": elapsed_ms,
                "fired_at_utc": t_utc_fired,
                "crn_list": crn_list,
                "action": self.action
            }

    def parse_response(self, result: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]:
        """
        Parses Kepler API JSON response for one or multiple courses.
        Returns:
          (successful_crns, retry_backup_crns, detail_messages)
        """
        if not result.get("success"):
            return [], [], [f"Ag / Timeout Hatasi: {result.get('error')}"]

        resp_text = result.get("response_text", "")
        crn_list = result.get("crn_list", [])

        successful_crns = []
        retry_backup_crns = []
        detail_messages = []

        try:
            data = json.loads(resp_text)

            if self.action == "drop":
                results_list = data.get("scrnResultList", [])
                if not results_list:
                    return [], [], [f"Sunucudan bos silme sonuc listesi dondu: {resp_text}"]

                for item in results_list:
                    crn = str(item.get("crn", ""))
                    res_code = item.get("resultCode")
                    msg_template = self.RESULT_MESSAGES.get(res_code, f"Sonuc: {res_code}")
                    readable_msg = msg_template.format(crn) if "{}" in msg_template else f"{msg_template} (CRN: {crn})"
                    detail_messages.append(readable_msg)

                    if res_code in ["successResult", "Silme İşlemi Başarılı"]:
                        successful_crns.append(crn)
            else:
                ecrn_results = data.get("ecrnResultList", [])
                if not ecrn_results:
                    return [], [], [f"Sunucudan bos sonuc listesi dondu: {resp_text}"]

                for item in ecrn_results:
                    crn = str(item.get("crn", ""))
                    res_code = item.get("resultCode")
                    msg_template = self.RESULT_MESSAGES.get(res_code, f"Bilinmeyen Kod ({res_code})")
                    readable_msg = msg_template.format(crn) if "{}" in msg_template else f"{msg_template} (CRN: {crn})"
                    detail_messages.append(readable_msg)

                    if res_code in ["successResult", "Ekleme İşlemi Başarılı"]:
                        successful_crns.append(crn)
                    elif res_code in ["VAL06", "Kontenjan Dolu"]:
                        if crn in self.backup_map:
                            retry_backup_crns.append(self.backup_map[crn])

        except Exception:
            return [], [], [f"JSON Ayristirma Hatasi: {resp_text[:120]}"]

        return successful_crns, retry_backup_crns, detail_messages
