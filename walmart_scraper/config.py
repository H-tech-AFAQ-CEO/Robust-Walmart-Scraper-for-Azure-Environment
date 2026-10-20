"""
Author: Zulqarnain Ahmad (Freelancer: https://www.freelancer.com/u/zulqarnaina43)
In collaboration with team leader: Afaq Ahmad (Freelancer: https://www.freelancer.com/u/AFAQCEO , GitHub: https://github.com/H-tech-AFAQ-CEO)

Configuration: categories CSV + locations JSON + env settings. No secrets in code.
"""
from __future__ import annotations
import csv, json, os, re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Category:
    name: str
    url: str
    excluded_subcategories: list[str] = field(default_factory=list)
    scope: str = ""


@dataclass
class Location:
    id: str
    zipcode: str
    store_id: str
    store_name: str = ""
    store_location: str = ""
    store_logo: str = ""
    canaries: list[str] = field(default_factory=list)  # usItemIds expected in this store's catalog


@dataclass
class Settings:
    state_dir: str = "state"
    output_dir: str = "output"
    storage: str = "local"                 # local | azure
    azure_account_url: str = ""            # https://<acct>.blob.core.windows.net (managed identity)
    azure_container: str = "walmart"
    proxy_url: str = ""                    # from Key Vault -> env, never committed
    headless: bool = True
    pace_min: float = 2.0
    pace_max: float = 5.0
    max_retries: int = 4
    max_pages: int = 25                    # Walmart caps listing pagination (~25 pages)
    max_depth: int = 2                     # category -> sub -> sub-sub
    max_consecutive_blocks: int = 3
    resume_max_hours: int = 36
    enrich_upc: bool = True
    include_sponsored_only: bool = False
    min_yield_ratio: float = 0.70          # vs last successful run, per category
    min_canary_ratio: float = 0.60
    min_completeness: float = 0.98
    config_dir: str = "config"
    capture_raw: bool = False        # save raw HTML + __NEXT_DATA__ per request (evidence)

    @classmethod
    def from_env(cls) -> "Settings":
        s = cls()
        for k, v in os.environ.items():
            if not k.startswith("WS_"):
                continue
            name = k[3:].lower()
            if hasattr(s, name):
                cur = getattr(s, name)
                if isinstance(cur, bool):
                    v = v.lower() in ("1", "true", "yes")
                elif isinstance(cur, int):
                    v = int(v)
                elif isinstance(cur, float):
                    v = float(v)
                setattr(s, name, v)
        return s


def load_categories(path: str) -> list[Category]:
    cats = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if not row.get("URL"):
                continue
            notes = row.get("Notes", "") or ""
            excl = re.findall(r"'([^']+)'", notes) if re.search(r"exclude", notes, re.I) else []
            cats.append(Category(row["Category (Auto)"].strip(), row["URL"].strip(), excl, row.get("Scope", "")))
    return cats


def load_locations(path: str) -> list[Location]:
    data = json.loads(Path(path).read_text())
    return [Location(**d) for d in data if not d.get("disabled")]
