import datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from httpx import Timeout
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class SpeshitsClient:
    def __init__(
        self,
        username: str,
        password: str,
        base_url: str = "https://speshits.hinature.cn",
        http_client: httpx.AsyncClient = httpx.AsyncClient(),
    ):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.access_token = None
        self.client = http_client

    async def get_token(self):
        token_url = urljoin(self.base_url, "/v1/token")
        payload = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
        }
        res = await self.client.post(token_url, data=payload)
        res.raise_for_status()
        data = res.json()
        expires_in = data["expires_in"]
        now_time = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        self.expire = now_time + expires_in - 60
        self.access_token = res.json()["access_token"]

        return self.access_token

    async def refresh_token(self):
        if self.access_token is None:
            await self.get_token()
        if self.expire < int(datetime.datetime.now(datetime.timezone.utc).timestamp()):
            await self.get_token()

    @retry(
        stop=stop_after_attempt(3),  # Retry up to 3 times
        wait=wait_exponential(
            multiplier=1, min=2, max=10
        ),  # Wait 2s, 4s, 8s... up to 10s
        retry=retry_if_exception_type(
            (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError)
        ),  # Retry on these specific errors
        reraise=True,  # Reraise the exception if all retries fail
    )
    async def search_taxons(
        self,
        canonicalName: str | None = None,
        chineseName: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[int, list[dict[str, int | str | None]]]:
        endpoint = urljoin(self.base_url, "/v1/taxons/search")
        await self.refresh_token()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        if not canonicalName and not chineseName:
            raise ValueError("Either canonicalName or chineseName must be provided")
        params: dict[str, str | int | None] = {
            "canonicalName": canonicalName,
            "chineseName": chineseName,
            "page": page,
            "pageSize": page_size,
        }
        res = await self.client.get(
            url=endpoint, headers=headers, params=params, timeout=Timeout(30.0)
        )
        res.raise_for_status()
        data = res.json()
        if not data["success"]:
            raise Exception(data["message"])
        total = data["total"]
        return total, data["data"]

    async def search_all_taxons(
        self, canonicalName: str | None = None, chineseName: str | None = None
    ):
        page = 1
        all_taxons: list[dict[str, str | int | None]] = []
        while True:
            total, taxons = await self.search_taxons(
                canonicalName, chineseName, page, page_size=1000
            )
            all_taxons.extend(taxons)
            if len(taxons) < total:
                break
            page += 1

        return all_taxons

    async def get_taxons_by_ids(
        self, taxon_ids: list[str], traversal: bool = False
    ) -> list[dict[str, int | str | None]]:
        endpoint = urljoin(self.base_url, "/v1/taxons/batch")
        await self.refresh_token()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        params: dict[str, list[str] | bool] = {
            "taxon_ids": taxon_ids,
            "traversal": traversal,
        }
        res = await self.client.get(
            url=endpoint, headers=headers, params=params, timeout=Timeout(30.0)
        )
        res.raise_for_status()
        data = res.json()
        if not data["success"]:
            raise Exception(data["message"])
        return data["data"]

    @retry(
        stop=stop_after_attempt(3),  # Retry up to 3 times
        wait=wait_exponential(
            multiplier=3, min=2, max=10
        ),  # Wait 2s, 4s, 8s... up to 10s
        retry=retry_if_exception_type(
            (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError)
        ),  # Retry on these specific errors
        reraise=True,  # Reraise the exception if all retries fail
    )
    async def get_taxon_by_id(
        self, taxon_id: str, traversal: bool = False
    ) -> dict[str, str | int | None] | None:
        endpoint = urljoin(self.base_url, "/v1/taxons")
        await self.refresh_token()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        res = await self.client.get(
            url=endpoint,
            headers=headers,
            params={"taxon_id": taxon_id, "traversal": traversal},
            timeout=Timeout(30.0),
        )
        res.raise_for_status()
        data = res.json()
        if not data["success"]:
            raise Exception(data["message"])
        return data["data"]

    @retry(
        stop=stop_after_attempt(3),  # Retry up to 3 times
        wait=wait_exponential(
            multiplier=3, min=2, max=10
        ),  # Wait 2s, 4s, 8s... up to 10s
        retry=retry_if_exception_type(
            (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError)
        ),  # Retry on these specific errors
        reraise=True,  # Reraise the exception if all retries fail
    )
    async def get_taxon_iucn(self, canonical_name: str) -> list[str]:
        endpoint = urljoin(self.base_url, "/v1/taxons/iucn")
        await self.refresh_token()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        res = await self.client.get(
            url=endpoint,
            headers=headers,
            params={"canonicalName": canonical_name},
            timeout=Timeout(30.0),
        )
        res.raise_for_status()
        data = res.json()
        if not data["success"]:
            raise Exception(data["message"])
        return data["data"]

    @retry(
        stop=stop_after_attempt(3),  # Retry up to 3 times
        wait=wait_exponential(
            multiplier=3, min=2, max=10
        ),  # Wait 2s, 4s, 8s... up to 10s
        retry=retry_if_exception_type(
            (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError)
        ),  # Retry on these specific errors
        reraise=True,  # Reraise the exception if all retries fail
    )
    async def get_taxon_cnpw(self, canonical_name: str) -> list[str]:
        endpoint = urljoin(self.base_url, "/v1/taxons/cnpw")
        await self.refresh_token()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        res = await self.client.get(
            url=endpoint,
            headers=headers,
            params={"canonicalName": canonical_name},
            timeout=Timeout(30.0),
        )
        res.raise_for_status()
        data = res.json()
        if not data["success"]:
            raise Exception(data["message"])
        return data["data"]

    async def create_taxon(self, taxon: dict[str, Any]) -> str:
        endpoint = urljoin(self.base_url, "/v1/taxons")
        await self.refresh_token()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        res = await self.client.post(
            url=endpoint, headers=headers, json=taxon, timeout=Timeout(30.0)
        )
        res.raise_for_status()
        data = res.json()
        if not data["success"]:
            raise Exception(data["message"])
        return data["data"]

    async def batch_create_taxons(self, taxons: list[dict[str, Any]]):
        # todo
        ...
    
    async def update_taxon(self, taxon_id: str, taxon: dict[str, Any]):
        # todo
        ...