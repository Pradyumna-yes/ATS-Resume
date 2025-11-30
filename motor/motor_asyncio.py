# Minimal in-memory Motor shim for testing environments.
# Provides AsyncIOMotorClient with databases and collections that support async CRUD used in tests.
import asyncio
import uuid
from typing import Any, Dict, List, Optional, AsyncIterator

class InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id

class DeleteResult:
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count

class FakeCursor:
    def __init__(self, items: List[Dict[str, Any]]):
        self._items = list(items)
        self._index = 0
    def sort(self, *args, **kwargs):
        return self
    def skip(self, n: int):
        if n and n < len(self._items):
            self._items = self._items[n:]
        else:
            self._items = []
        return self
    def limit(self, n: int):
        if n and n < len(self._items):
            self._items = self._items[:n]
        return self
    def __aiter__(self):
        self._index = 0
        return self
    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        await asyncio.sleep(0)
        return item

class Collection:
    def __init__(self, store: List[Dict[str,Any]]):
        self._store = store
    async def insert_one(self, doc: Dict[str,Any]):
        # emulate ObjectId by using uuid4 string
        _id = str(uuid.uuid4())
        doc_copy = dict(doc)
        doc_copy["_id"] = _id
        self._store.append(doc_copy)
        return InsertOneResult(_id)
    async def find_one(self, query: Dict[str,Any]):
        # support queries like {"_id": {"$oid": id}} or {"_id": id} or {"id": id}
        for d in self._store:
            if not query:
                return d
            ok = True
            for k,v in query.items():
                if k == "_id" and isinstance(v, dict) and "$oid" in v:
                    if d.get("_id") != v["$oid"]:
                        ok = False; break
                else:
                    if d.get(k) != v:
                        ok = False; break
            if ok:
                return d
        return None
    def find(self, query: Dict[str,Any]):
        # very simple matching: returns all docs matching all provided fields
        matched = []
        for d in self._store:
            ok = True
            for k,v in (query or {}).items():
                if d.get(k) != v:
                    ok = False; break
            if ok: matched.append(d)
        return FakeCursor(matched)
    async def delete_many(self, query: Dict[str,Any]):
        before = len(self._store)
        new = []
        for d in self._store:
            match = True
            for k,v in (query or {}).items():
                if d.get(k) != v:
                    match = False; break
            if not match:
                new.append(d)
        self._store[:] = new
        return DeleteResult(before - len(self._store))
    async def delete_one(self, query: Dict[str,Any]):
        for i,d in enumerate(self._store):
            match = True
            for k,v in (query or {}).items():
                if d.get(k) != v:
                    match = False; break
            if match:
                del self._store[i]
                return DeleteResult(1)
        return DeleteResult(0)

class Database:
    def __init__(self, data: Dict[str,List[Dict[str,Any]]], name: str):
        self._data = data
        self._name = name
    def __getitem__(self, key: str) -> Collection:
        if key not in self._data:
            self._data[key] = []
        return Collection(self._data[key])

class AsyncIOMotorClient:
    def __init__(self, uri: Optional[str] = None):
        self._data: Dict[str, List[Dict[str,Any]]] = {}
        # allow providing a default db name in URI like mongodb://host:port/db
        self._default_db = None
        if uri and "/" in uri:
            parts = uri.rsplit('/', 1)
            if parts[-1]:
                self._default_db = parts[-1]
    def __getitem__(self, name: str) -> Database:
        return Database(self._data, name)
    def get_database(self, name: Optional[str] = None) -> Database:
        return self[name or self._default_db or "test"]
