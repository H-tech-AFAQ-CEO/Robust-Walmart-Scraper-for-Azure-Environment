"""
Author: Zulqarnain Ahmad (Freelancer: https://www.freelancer.com/u/zulqarnaina43)
In collaboration with team leader: Afaq Ahmad (Freelancer: https://www.freelancer.com/u/AFAQCEO , GitHub: https://github.com/H-tech-AFAQ-CEO)

Durable checkpoint enabling genuine resume (per node, per page, with stored records).
"""
from __future__ import annotations
import json, os, time
from collections import Counter
from pathlib import Path


class Checkpoint:
    def __init__(self, d: Path):
        self.dir = d
        self.meta: dict = {}
        self.nodes: dict[str, dict] = {}     # key -> {category,sub,url,depth,status,last_page,kept,...}
        self.records: dict[str, dict] = {}   # item id -> record
        self.sponsored_only: dict[str, dict] = {}
        self.counters: Counter = Counter()
        self.events: list[dict] = []

    # ---- persistence
    def _w(self, name, obj):
        p = self.dir / name
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj))
        os.replace(tmp, p)

    def save(self):
        self._w("meta.json", self.meta)
        self._w("nodes.json", self.nodes)
        self._w("counters.json", dict(self.counters))
        self._w("records.json", self.records)
        self._w("sponsored.json", self.sponsored_only)
        self._w("events.json", self.events[-2000:])

    @classmethod
    def open_or_create(cls, root: Path, job: str, max_age_h: int, fresh: bool = False):
        jobdir = root / job
        jobdir.mkdir(parents=True, exist_ok=True)
        if not fresh:
            for d in sorted(jobdir.iterdir(), reverse=True):
                mp = d / "meta.json"
                if mp.exists():
                    m = json.loads(mp.read_text())
                    if m.get("status") == "in_progress" and time.time() - m.get("started_ts", 0) < max_age_h * 3600:
                        return cls._load(d), True
        run_id = time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + f"{int(time.time() * 1000) % 1000:03d}Z"
        d = jobdir / run_id
        d.mkdir(parents=True)
        cp = cls(d)
        cp.meta = {"run_id": run_id, "job": job, "status": "in_progress", "started_ts": time.time(),
                   "crawl_date": time.strftime("%Y-%m-%d")}
        cp.save()
        return cp, False

    @classmethod
    def _load(cls, d: Path):
        cp = cls(d)
        rd = lambda n, default: json.loads((d / n).read_text()) if (d / n).exists() else default
        cp.meta = rd("meta.json", {})
        cp.nodes = rd("nodes.json", {})
        cp.counters = Counter(rd("counters.json", {}))
        cp.records = rd("records.json", {})
        cp.sponsored_only = rd("sponsored.json", {})
        cp.events = rd("events.json", [])
        return cp

    def event(self, kind: str, **kw):
        self.events.append({"t": time.strftime("%H:%M:%S"), "kind": kind, **kw})
