"""
Author: Zulqarnain Ahmad (Freelancer: https://www.freelancer.com/u/zulqarnaina43)
In collaboration with team leader: Afaq Ahmad (Freelancer: https://www.freelancer.com/u/AFAQCEO , GitHub: https://github.com/H-tech-AFAQ-CEO)

Classify displayed promo text into volume vs digital deals. Never computes prices.
"""
import re

EXCLUDE = re.compile(r"walmart cash|cash ?back|rebate|ibotta|manufacturer|fetch|checkout 51", re.I)
DIGITAL = re.compile(r"clip|digital coupon|with coupon|e-?coupon|activate|add (?:this )?(?:offer|coupon)|"
                     r"save to (?:account|wallet)|clipped", re.I)
VOLUME = re.compile(r"\b\d+\s*for\s*\$\s*\d|buy\s+\d+.{0,40}get|\bbogo\b|mix\s*(?:or|&|and)\s*match|"
                    r"save\s+\$?[\d.]+\s+when you buy|must buy\s+\d+|buy\s+\d+\s+(?:or more\s+)?(?:and\s+)?save", re.I)
EACH = re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)\s*(?:each|ea\b)", re.I)
N_FOR = re.compile(r"\b\d+\s*for\s*\$\s*([\d,]+(?:\.\d{1,2})?)", re.I)


def _price(text: str) -> str:
    m = EACH.search(text) or N_FOR.search(text)
    return f"{float(m.group(1).replace(',', '')):.2f}" if m else ""


def classify_deals(texts: list[str]) -> dict:
    vol, dig = [], []
    for t in texts:
        if EXCLUDE.search(t):
            continue
        if DIGITAL.search(t):
            dig.append(t)
        elif VOLUME.search(t):
            vol.append(t)
    vp = next((p for p in (_price(t) for t in vol) if p), "")
    dp = next((p for p in (_price(t) for t in dig) if p), "")
    return {
        "volume_deals_description": " | ".join(vol), "volume_deals_price": vp,
        "digital_deals_description": " | ".join(dig), "digital_deals_price": dp,
    }
