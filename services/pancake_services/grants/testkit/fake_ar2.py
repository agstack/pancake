from contextlib import contextmanager
from unittest.mock import patch
import httpx
from pancake_services.grants.merkle import merkle_root

@contextmanager
def fake_ar2_node():
    """In-process stand-in for the AR2 node: stateful registry + real BFS.
    Used by services/tests/conftest.py and services/demo/end_to_end_demo.py."""
    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self._json_data = json_data
            self.status_code = status_code

        def json(self):
            return self._json_data
            
        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPError("mock error")

    original_post = httpx.post
    original_get = httpx.get

    registry: dict[str, list[str]] = {}

    def mock_post(url, *args, **kwargs):
        if url.endswith("/list-artifact"):
            json_payload = kwargs.get("json", {})
            members = json_payload.get("members", [])
            list_id = merkle_root(members)
            registry[list_id] = sorted(set(members))
            return MockResponse({"list_id": list_id, "message": "Success"})
        elif "/traceforward" in url:
            json_payload = kwargs.get("json", {})
            geoid = json_payload.get("seed_geoid", "")
                
            found = set()
            frontier = set()
            
            for list_id, members in registry.items():
                if geoid in members:
                    frontier.add(list_id)
            
            found.update(frontier)
            while frontier:
                parents = set()
                for list_id, members in registry.items():
                    for member in members:
                        if member.startswith("L:") and member[2:] in frontier:
                            parents.add(list_id)
                frontier = parents - found
                found.update(parents)
                
            return MockResponse({
                "seed_geoid": geoid,
                "tier": 1,
                "matches": [{"list_id": lid, "region_id": None} for lid in found]
            })
        return original_post(url, *args, **kwargs)

    def mock_get(url, *args, **kwargs):
        if "/list-artifact/reverse/" in url:
            geoid = url.rstrip("/").rsplit("/", 1)[-1]
            return MockResponse({"list_ids": [lid for lid, m in registry.items() if geoid in m]})
        elif "/list-artifact/" in url:
            list_id = url.rstrip("/").rsplit("/", 1)[-1]
            if list_id not in registry:
                return MockResponse({"detail": "not found"}, status_code=404)
            return MockResponse({"members": registry[list_id]})
        return original_get(url, *args, **kwargs)

    with patch("pancake_services.grants.routers.fieldlists.httpx.post", side_effect=mock_post), \
         patch("pancake_services.grants.routers.audit.httpx.post", side_effect=mock_post), \
         patch("pancake_services.grants.routers.fieldlists.httpx.get", side_effect=mock_get), \
         patch("pancake_services.grants.routers.grants.httpx.get", side_effect=mock_get):
        yield
