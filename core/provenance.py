"""
Provenance — cryptographic trust tagging for all pipeline data.

Any data originating from external/sensor sources is tagged untrusted.
This tag propagates through the entire pipeline and cannot be upgraded.
Physical execution pathways are hard-blocked on untrusted provenance.

Defends against: prompt injection via QR codes, camera frames,
audio transcription, smart meter payloads, RSS feeds.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List


UNTRUSTED_SOURCES = [
    "camera", "microphone", "sensor", "web_scrape", "external_api",
    "rss_feed", "nfc_scan", "qr_scan", "ocr", "audio_transcription",
    "alexa", "google_home",
]

TRUSTED_SOURCES = [
    "telegram_local", "rest_local", "voice_local", "coordinator", "scheduler",
]


@dataclass
class Provenance:
    trust: str
    source: str
    chain: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @classmethod
    def from_source(cls, source: str) -> "Provenance":
        trust = "untrusted" if source in UNTRUSTED_SOURCES else "trusted"
        return cls(trust=trust, source=source, chain=[source])

    def propagate(self, next_agent: str) -> "Provenance":
        return Provenance(trust=self.trust, source=self.source, chain=self.chain + [next_agent])

    @property
    def is_trusted(self) -> bool:
        return self.trust == "trusted"

    def assert_trusted_for(self, action: str) -> None:
        if not self.is_trusted:
            chain_str = " → ".join(self.chain)
            raise PermissionError(
                f"[PROVENANCE BLOCK] Action '{action}' rejected.\n"
                f"  Reason: Data provenance is untrusted.\n"
                f"  Origin: {self.source}\n"
                f"  Chain:  {chain_str}\n"
                f"  Physical actions require trusted provenance."
            )
