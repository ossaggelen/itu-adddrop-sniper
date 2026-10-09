import socket
import struct
import time
from datetime import datetime, timezone
import email.utils
import requests
from typing import Tuple, Optional

class ClockSync:
    """
    Measures network Round Trip Time (RTT) and calculates local clock offset
    relative to atomic time (NTP) and ITU server HTTP headers.
    """

    NTP_SERVERS = ["tr.pool.ntp.org", "pool.ntp.org", "time.google.com", "time.cloudflare.com"]

    @staticmethod
    def get_ntp_offset(timeout: float = 2.0) -> Optional[Tuple[float, float]]:
        """
        Queries an NTP server over UDP port 123.
        Returns: (offset_seconds, rtt_seconds) where:
          offset_seconds = NTP_time - local_system_time
          Returns None if NTP is blocked or fails.
        """
        NTP_EPOCH_DELTA = 2208988800  # 1970 - 1900 in seconds
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(timeout)

        for server in ClockSync.NTP_SERVERS:
            try:
                # NTP v3 client packet (48 bytes, first byte = 0x1B)
                msg = b'\x1b' + 47 * b'\0'
                t_send = time.time()
                client.sendto(msg, (server, 123))
                data, _ = client.recvfrom(1024)
                t_recv = time.time()

                if len(data) >= 48:
                    # Unpack Transmit Timestamp from bytes 40-48
                    seconds, fraction = struct.unpack("!II", data[40:48])
                    ntp_server_time = (seconds - NTP_EPOCH_DELTA) + (fraction / (2**32))
                    rtt = t_recv - t_send
                    # Estimate arrival: local time corresponding to server transmit
                    offset = ntp_server_time - (t_send + rtt / 2.0)
                    client.close()
                    return offset, rtt
            except Exception:
                continue

        client.close()
        return None

    @staticmethod
    def measure_http_rtt_and_offset(session: requests.Session, target_url: str = "https://obs.itu.edu.tr/ogrenci/", samples: int = 5) -> Tuple[float, float]:
        """
        Measures HTTP RTT and estimates server clock offset from HTTP 'Date' response header.
        Returns: (median_offset_seconds, median_rtt_seconds)
        """
        rtts = []
        offsets = []

        for _ in range(samples):
            try:
                t_send = time.time()
                response = session.head(target_url, timeout=4.0)
                t_recv = time.time()

                rtt = t_recv - t_send
                rtts.append(rtt)

                date_header = response.headers.get("Date")
                if date_header:
                    server_dt = email.utils.parsedate_to_datetime(date_header)
                    # Convert server_dt to unix timestamp UTC
                    server_timestamp = server_dt.timestamp()
                    # Midpoint local time
                    local_midpoint = t_send + rtt / 2.0
                    offset = server_timestamp - local_midpoint
                    offsets.append(offset)
            except Exception:
                pass
            time.sleep(0.1)

        median_rtt = sorted(rtts)[len(rtts) // 2] if rtts else 0.030
        median_offset = sorted(offsets)[len(offsets) // 2] if offsets else 0.0

        return median_offset, median_rtt

    @staticmethod
    def calibrate(session: requests.Session, target_url: str = "https://obs.itu.edu.tr/ogrenci/") -> dict:
        """
        Performs full calibration using both NTP and HTTP probes.
        Returns a dictionary with offset, rtt, and recommendations.
        """
        ntp_result = ClockSync.get_ntp_offset()
        http_offset, http_rtt = ClockSync.measure_http_rtt_and_offset(session, target_url)

        chosen_offset = ntp_result[0] if ntp_result is not None else http_offset
        source = "NTP (Atomic)" if ntp_result is not None else "HTTP Date Header"

        return {
            "source": source,
            "offset_seconds": chosen_offset,
            "offset_ms": chosen_offset * 1000.0,
            "rtt_seconds": http_rtt,
            "rtt_ms": http_rtt * 1000.0,
            "one_way_latency_ms": (http_rtt / 2.0) * 1000.0,
            "ntp_available": ntp_result is not None
        }
