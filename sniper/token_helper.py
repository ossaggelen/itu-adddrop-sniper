import os
import sys
import time
from typing import Optional

# Allow importing from project root / src if needed
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if os.path.join(PROJECT_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

class TokenHelper:
    """
    Handles Kepler Authorization token acquisition either manually or via automated headless browser.
    """

    TARGET_URL = "https://obs.itu.edu.tr/ogrenci/DersKayitIslemleri/DersKayit"

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None, manual_token: Optional[str] = None):
        self.username = username
        self.password = password
        self.manual_token = manual_token
        self.fetcher = None

    def get_token(self, headless: bool = True) -> str:
        """
        Returns a valid Kepler Authorization token.
        """
        # If a manual token was provided and starts with Bearer or is non-empty, use it
        if self.manual_token and len(self.manual_token.strip()) > 20:
            token = self.manual_token.strip()
            if not token.lower().startswith("bearer"):
                token = f"Bearer {token}"
            return token

        if not self.username or not self.password:
            raise ValueError("Kullanıcı adı ve şifre veya geçerli bir manuel token gereklidir.")

        from token_fetcher import ContinuousTokenFetcher

        print("[Sniper-Auth] Headless tarayıcı ile Kepler'e giriş yapılıyor...")
        self.fetcher = ContinuousTokenFetcher(
            self.TARGET_URL,
            self.username,
            self.password,
            use_headless_browser=headless
        )
        self.fetcher.login_to_kepler()
        self.fetcher.start()

        print("[Sniper-Auth] API Authorization Token yakalanması bekleniyor...")
        if not self.fetcher.wait_for_first_token(timeout=90):
            self.fetcher.stop()
            raise TimeoutError("90 saniye içinde Kepler Authorization Token alınamadı!")

        token = self.fetcher.get_token()
        print("[Sniper-Auth] Token başarıyla yakalandı.")
        return token

    def stop(self):
        if self.fetcher:
            try:
                self.fetcher.stop()
            except Exception:
                pass
