import datetime
from typing import Dict, List, Tuple
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
    def __init__(self, username: str, password: str):
        self.base_url = "https://speshits.hinature.cn"
        self.username = username
        self.password = password
        self.access_token = None

    async def get_token(self):
        token_url = urljoin(self.base_url, "/v1/token")
        payload = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
        }
        async with httpx.AsyncClient() as client:
            res = await client.post(token_url, data=payload)
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
    async def get_taxons_page(
        self,
        canonicalName: str | None = None,
        chineseName: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[int, List[Dict[str, int | str | None]]]:
        endpoint = urljoin(self.base_url, "/v1/taxons")
        await self.refresh_token()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        if not canonicalName and not chineseName:
            raise ValueError("Either canonicalName or chineseName must be provided")
        params: Dict[str, str | int | None] = {
            "canonicalName": canonicalName,
            "chineseName": chineseName,
            "page": page,
            "pageSize": page_size,
        }
        async with httpx.AsyncClient(timeout=Timeout(30.0)) as client:
            res = await client.get(url=endpoint, headers=headers, params=params)
        res.raise_for_status()
        data = res.json()
        if not data["success"]:
            raise Exception(data["message"])
        total = data["total"]
        return total, data["data"]

    async def get_all_taxons(
        self, canonicalName: str | None = None, chineseName: str | None = None
    ):
        page = 1
        all_taxons: List[Dict[str, str | int | None]] = []
        while True:
            total, taxons = await self.get_taxons_page(
                canonicalName, chineseName, page, page_size=1000
            )
            all_taxons.extend(taxons)
            if len(taxons) < total:
                break
            page += 1

        return all_taxons

    async def get_taxons_by_ids(
        self, taxon_ids: List[str]
    ) -> List[Dict[str, int | str | None]]:
        endpoint = urljoin(self.base_url, "/v1/taxons/batch_get")
        await self.refresh_token()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        json_data = {"taxon_ids": taxon_ids}
        async with httpx.AsyncClient(timeout=Timeout(30.0)) as client:
            res = await client.post(url=endpoint, headers=headers, json=json_data)
        res.raise_for_status()
        data = res.json()
        if not data["success"]:
            raise Exception(data["message"])
        return data["data"]

    async def get_taxon_by_id(self, taxon_id: str) -> Dict[str, str | int | None]:
        endpoint = urljoin(self.base_url, f"/v1/taxons/{taxon_id}")
        await self.refresh_token()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        async with httpx.AsyncClient(timeout=Timeout(30.0)) as client:
            res = await client.get(url=endpoint, headers=headers)
        res.raise_for_status()
        data = res.json()
        if not data["success"]:
            raise Exception(data["message"])
        return data["data"]
