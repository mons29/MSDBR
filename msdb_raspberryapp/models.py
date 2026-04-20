"""DTO reçus depuis l'API MSDBS — miroir de MsdbUrl.kt côté Android."""

from dataclasses import dataclass


@dataclass
class MsdbUrl:
    id: str
    url: str
    display_duration_seconds: int
    scroll_speed: int = 0
    tempo_scroll: int = 0
    rafraichissement: int = 30

    @classmethod
    def from_json(cls, data: dict) -> "MsdbUrl":
        return cls(
            id=data["id"],
            url=data["url"],
            display_duration_seconds=data["displayDurationSeconds"],
            scroll_speed=data.get("scrollSpeed", 0),
            tempo_scroll=data.get("tempoScroll", 0),
            rafraichissement=data.get("rafraichissement", 30),
        )
