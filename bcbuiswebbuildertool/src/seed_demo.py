"""
Seed the dashboard with realistic demo clients — for presenting the tool.

Creates 7 fictional Vancouver-area businesses with:
  • built premium sites (real template, real stock photography)
  • real-looking Google reviews in customize.json (deploy-check passes)
  • a billing mix (3 active plans incl. one overdue → MRR + red badge)
  • prospects whose portal was "sent" days ago → live Follow-ups queue

Safe: never touches an existing client slug (your real clients are kept).

Run once:  python src/seed_demo.py
Undo:      python src/seed_demo.py --remove
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

OUTPUT_DIR   = Path("./output")
RESEARCH_DIR = Path("./research")

_now = datetime.now()


def _days_ago(n: int) -> str:
    return (_now - timedelta(days=n)).isoformat()


SEEDS = [
    {
        "name": "North Shore Plumbing Co.", "category": "plumber",
        "city": "North Vancouver", "phone": "604-555-0182",
        "address": "1450 Marine Dr, North Vancouver, BC",
        "rating": 4.9, "review_count": 47,
        "status": "client", "created_at": _days_ago(34),
        "billing": {"plan": "Tier 2 — Growth", "monthly_fee": 299,
                    "billing_status": "active",
                    "next_due": (_now + timedelta(days=12)).date().isoformat(),
                    "payment_link": "https://buy.stripe.com/demo_northshore"},
        "reviews": [
            {"name": "Karen D.", "rating": 5, "text": "Burst pipe at 11pm and they were here within the hour. Professional, calm, and the price was exactly the quote.", "location": "North Vancouver"},
            {"name": "Raj P.", "rating": 5, "text": "Re-piped our whole 1970s house. Tidy crew, clear communication, passed inspection first try.", "location": "Lynn Valley"},
            {"name": "Melissa T.", "rating": 5, "text": "Finally a plumber who shows up when they say they will. Our new water heater was installed same week.", "location": "Deep Cove"},
        ],
    },
    {
        "name": "Kitsilano Electric", "category": "electrician",
        "city": "Vancouver", "phone": "604-555-0147",
        "address": "2210 W 4th Ave, Vancouver, BC",
        "rating": 4.8, "review_count": 33,
        "status": "client", "created_at": _days_ago(58),
        "billing": {"plan": "Tier 1 — Entry", "monthly_fee": 99,
                    "billing_status": "active",
                    "next_due": (_now - timedelta(days=6)).date().isoformat()},  # overdue!
        "reviews": [
            {"name": "Dave H.", "rating": 5, "text": "Panel upgrade done in a day, permit handled for us. Everything explained in plain English.", "location": "Kitsilano"},
            {"name": "Sophie L.", "rating": 5, "text": "Installed our EV charger and tidied wiring the last guy left a mess of. Fair price, spotless work.", "location": "Point Grey"},
            {"name": "Marcus W.", "rating": 4, "text": "Quick response, honest advice — told us what we DIDN'T need, which won our trust.", "location": "Fairview"},
        ],
    },
    {
        "name": "Granville Painting Studio", "category": "painter",
        "city": "Vancouver", "phone": "604-555-0126",
        "address": "3105 Granville St, Vancouver, BC",
        "rating": 4.7, "review_count": 21,
        "status": "prospect", "created_at": _days_ago(9),
        "portal_sent_at": _days_ago(5),  # → follow-up due
        "reviews": [
            {"name": "Anita R.", "rating": 5, "text": "Our heritage exterior looks brand new. The prep work alone took two days — that's how you know they care.", "location": "Shaughnessy"},
            {"name": "Tom B.", "rating": 5, "text": "Interior repaint of our condo, done while we were away. Came home to perfect lines and zero mess.", "location": "South Granville"},
            {"name": "Grace K.", "rating": 5, "text": "Colour consultation was worth every penny. The living room finally feels like us.", "location": "Kerrisdale"},
        ],
    },
    {
        "name": "Fraser Valley Landscaping", "category": "landscaper",
        "city": "Surrey", "phone": "604-555-0164",
        "address": "8820 152 St, Surrey, BC",
        "rating": 4.6, "review_count": 18,
        "status": "prospect", "created_at": _days_ago(8),
        "portal_sent_at": _days_ago(4),  # → follow-up due
        "reviews": [
            {"name": "Paul N.", "rating": 5, "text": "Full backyard redesign — new patio, cedar fence, irrigation. On budget and a week early.", "location": "Surrey"},
            {"name": "Jasmine C.", "rating": 4, "text": "They maintain our strata's grounds and the difference is night and day. Very responsive.", "location": "Fleetwood"},
            {"name": "Bill & Donna M.", "rating": 5, "text": "The crew treats our garden like their own. Best yard on the street two summers running.", "location": "Cloverdale"},
        ],
    },
    {
        "name": "Harbourview Roofing", "category": "roofer",
        "city": "Burnaby", "phone": "604-555-0139",
        "address": "4012 Hastings St, Burnaby, BC",
        "rating": 4.8, "review_count": 26,
        "status": "prospect", "created_at": _days_ago(1),
        "reviews": [
            {"name": "Steve G.", "rating": 5, "text": "Replaced our roof after the November storms. Honest assessment, no upselling, immaculate cleanup.", "location": "Burnaby Heights"},
            {"name": "Priya S.", "rating": 5, "text": "Fixed a leak two other companies couldn't find. Sent photos of everything before and after.", "location": "Capitol Hill"},
            {"name": "John T.", "rating": 5, "text": "Straight shooters. Quoted a repair when others quoted a full replacement.", "location": "Brentwood"},
        ],
    },
    {
        "name": "Mount Pleasant Cleaning Co.", "category": "cleaner",
        "city": "Vancouver", "phone": "604-555-0118",
        "address": "155 E Broadway, Vancouver, BC",
        "rating": 4.9, "review_count": 61,
        "status": "client", "created_at": _days_ago(75),
        "billing": {"plan": "Tier 3 — Pro", "monthly_fee": 599,
                    "billing_status": "active",
                    "next_due": (_now + timedelta(days=20)).date().isoformat(),
                    "payment_link": "https://buy.stripe.com/demo_mtpleasant"},
        "reviews": [
            {"name": "Officeworks YVR", "rating": 5, "text": "They've cleaned our two floors nightly for a year. Zero complaints from staff — unheard of.", "location": "Mount Pleasant"},
            {"name": "Hannah F.", "rating": 5, "text": "Move-out clean got our full damage deposit back. Landlord asked who we used.", "location": "Main Street"},
            {"name": "Dr. Chen's Dental", "rating": 5, "text": "Medical-grade attention to detail. Reliable, insured, and lovely to deal with.", "location": "Cambie Village"},
        ],
    },
    {
        "name": "Oakridge Contracting", "category": "contractor",
        "city": "Vancouver", "phone": "604-555-0171",
        "address": "650 W 41st Ave, Vancouver, BC",
        "rating": 4.5, "review_count": 14,
        "status": "closed", "created_at": _days_ago(41),
        "notes": "Went with nephew's friend. Revisit in 6 months.",
        "reviews": [
            {"name": "Amir Z.", "rating": 5, "text": "Kitchen reno finished on schedule. Daily photo updates kept us sane while travelling.", "location": "Oakridge"},
            {"name": "Lucy P.", "rating": 4, "text": "Basement suite conversion handled permits to paint. Great subs, tidy site.", "location": "Marpole"},
            {"name": "The Hendersons", "rating": 5, "text": "Second project with them. There will be a third.", "location": "South Cambie"},
        ],
    },
]


def _slug(name: str) -> str:
    import re
    s = name.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")[:60]


def _load_clients() -> list:
    f = OUTPUT_DIR / "clients.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_clients(clients: list):
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "clients.json").write_text(
        json.dumps(clients, indent=2), encoding="utf-8")


def seed():
    from build import build_website

    clients = _load_clients()
    existing = {c.get("slug") for c in clients}
    added = 0

    for s in SEEDS:
        slug = _slug(s["name"])
        if slug in existing:
            print(f"  ↷ {s['name']} already exists — skipped")
            continue

        # 1) research profile so rebuilds work later
        prof_dir = RESEARCH_DIR / slug
        prof_dir.mkdir(parents=True, exist_ok=True)
        (prof_dir / "profile.json").write_text(json.dumps({
            "business": {
                "name": s["name"], "city": s["city"],
                "category": s["category"], "categories": [s["category"]],
                "phone": s["phone"], "address": s["address"],
                "rating": s["rating"], "review_count": s["review_count"],
            },
            "seeded_demo": True,
        }, indent=2), encoding="utf-8")

        # 2) customize with real-looking reviews (deploy-check turns green)
        site_dir = OUTPUT_DIR / slug
        site_dir.mkdir(parents=True, exist_ok=True)
        (site_dir / "customize.json").write_text(json.dumps({
            "reviews": s["reviews"],
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        # 3) build the premium site
        print(f"  ⚒ building {s['name']} …")
        try:
            build_website(str(prof_dir), str(OUTPUT_DIR))
        except Exception as exc:
            print(f"    ! build failed ({exc}) — client registered without site")

        # 4) client record
        record = {
            "slug": slug, "name": s["name"], "address": s["address"],
            "phone": s["phone"], "category": s["category"],
            "status": s["status"], "created_at": s["created_at"],
            "has_site": (site_dir / "index.html").exists(),
            "has_pdf": False, "live_url": None,
            "portal_url": f"/portal/{slug}", "source": "demo_seed",
        }
        if s.get("portal_sent_at"):
            record["portal_sent_at"] = s["portal_sent_at"]
        if s.get("notes"):
            record["notes"] = s["notes"]
        for k, v in (s.get("billing") or {}).items():
            record[k] = v
        clients.append(record)
        existing.add(slug)
        added += 1

    _save_clients(clients)
    active = [s for s in SEEDS if (s.get("billing") or {}).get("billing_status") == "active"]
    mrr = sum(s["billing"]["monthly_fee"] for s in active)
    print(f"\n✓ Seeded {added} demo client(s).")
    print(f"  MRR on Billing tab: ${mrr}/mo across {len(active)} active plans (1 overdue)")
    print("  Follow-ups tab: 2 prospects due (portal sent 4–5 days ago)")
    print("  Remove any time with:  python src/seed_demo.py --remove")


def remove():
    import shutil
    clients = _load_clients()
    keep = [c for c in clients if c.get("source") != "demo_seed"]
    removed = len(clients) - len(keep)
    _save_clients(keep)
    for s in SEEDS:
        slug = _slug(s["name"])
        for base in (OUTPUT_DIR, RESEARCH_DIR):
            d = base / slug
            marker_ok = True
            prof = RESEARCH_DIR / slug / "profile.json"
            if base is OUTPUT_DIR and prof.exists():
                try:
                    marker_ok = json.loads(prof.read_text()).get("seeded_demo", False)
                except Exception:
                    marker_ok = False
            if d.exists() and marker_ok:
                shutil.rmtree(d, ignore_errors=True)
    print(f"✓ Removed {removed} demo client(s) and their files.")


if __name__ == "__main__":
    if "--remove" in sys.argv:
        remove()
    else:
        print("Seeding demo clients (fictional businesses — safe to remove later)…")
        seed()
