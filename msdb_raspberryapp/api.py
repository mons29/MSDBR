"""Client HTTP MSDBS — équivalent ApiService/SchedulerRepository Android."""

import requests

from .models import MsdbUrl


class ApiError(Exception):
    pass


class MsdbsClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_next_url(self, msdb_id: str) -> MsdbUrl:
        try:
            response = requests.get(
                f"{self.base_url}/api/scheduler/next",
                params={"msdbId": msdb_id},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return MsdbUrl.from_json(response.json())
        except requests.RequestException as exc:
            raise ApiError(str(exc)) from exc
