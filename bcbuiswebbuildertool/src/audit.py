"""
Phase 4 - AI Opportunity Audit

Analyse the business holistically and produce a professional PDF proposal
identifying where AI and automation can reduce costs, increase revenue, or
save time. Written for a non-technical audience - this document is handed
directly to the business owner.

Five audit dimensions:
  1. Automations       - booking, invoicing, follow-ups
  2. Customer Service  - chatbots, after-hours, missed calls
  3. Marketing         - ads, SEO, email, review generation
  4. Operations        - scheduling, inventory, document automation
  5. Revenue           - upsells, adjacent services, loyalty/referral

PDF structure (max 10 pages):
  Cover Page
  Page 1  - Executive Summary (3-5 sentences, hours saved, top 3 quick wins)
  Pages 2-6 - One page per audit category
  Page 7  -30/60/90 day implementation roadmap
  Back    - Next steps CTA + contact info placeholder

Saved to: ./output/{business_slug}/ai_opportunity_report.pdf
"""

import json
from datetime import date
from pathlib import Path
from typing import Optional

from logging_config import get_logger

log = get_logger("audit")

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False


# fpdf2's core fonts (Helvetica) only support latin-1. AI-generated copy often
# contains em-dashes and smart quotes, so normalise text before it is written.
_PDF_CHAR_MAP = {
    "—": "-", "–": "-", "‑": "-", "−": "-",
    "‘": "'", "’": "'", "‚": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "″": '"',
    "…": "...", "•": "-", "·": "-", "→": "->",
    " ": " ", "​": "", "﻿": "",
}


def _pdf_safe(s):
    if not isinstance(s, str):
        return s
    for bad, good in _PDF_CHAR_MAP.items():
        s = s.replace(bad, good)
    # Drop any remaining non-latin-1 characters (e.g. emoji) safely
    return s.encode("latin-1", "ignore").decode("latin-1")


def _pdf_safe_args(args, kwargs):
    """Sanitise the text argument of FPDF cell/multi_cell calls."""
    args = list(args)
    if len(args) >= 3:
        args[2] = _pdf_safe(args[2])
    for key in ("text", "txt"):
        if key in kwargs:
            kwargs[key] = _pdf_safe(kwargs[key])
    return tuple(args), kwargs


def run_audit(profile_dir: str, output_dir: str = "./output") -> Path:
    """
    Entry point for Phase 4. Reads the business profile and generates the
    AI Opportunity PDF report.
    """
    profile_path = Path(profile_dir) / "profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8", errors="replace"))
    business = profile["business"]

    slug = _slugify(business.get("name", "unknown-business"))
    site_dir = Path(output_dir) / slug
    site_dir.mkdir(parents=True, exist_ok=True)

    findings = _analyse_all_dimensions(business, profile)
    pdf_path = _generate_pdf(business, findings, site_dir)

    log.info(f"[audit] PDF report saved to {pdf_path}")
    return pdf_path


def _analyse_all_dimensions(business: dict, profile: dict) -> dict:
    return {
        "automations": _audit_automations(business, profile),
        "customer_service": _audit_customer_service(business, profile),
        "marketing": _audit_marketing(business, profile),
        "operations": _audit_operations(business, profile),
        "revenue": _audit_revenue(business, profile),
    }


# ── Profile signal helpers ──────────────────────────────────────────────────

def _website_text(profile: dict) -> str:
    return profile.get("website_analysis", {}).get("text_content", "").lower()


def _has_booking_system(profile: dict) -> bool:
    text = _website_text(profile)
    pages = profile.get("website_analysis", {}).get("internal_pages", [])
    keywords = ["book now", "book an appointment", "schedule", "booking",
                "calendly", "acuity", "setmore", "jane app", "online booking"]
    if any(k in text for k in keywords):
        return True
    for p in pages:
        slug = (p.get("url", "") + p.get("title", "")).lower()
        if any(k in slug for k in ["book", "schedul", "appoint", "reserv"]):
            return True
    return False


def _has_live_chat(profile: dict) -> bool:
    text = _website_text(profile)
    tech = str(profile.get("website_analysis", {}).get("technology_signals", [])).lower()
    signals = ["intercom", "drift", "zendesk", "tidio", "tawk", "crisp",
               "livechat", "chat widget", "chat with us"]
    return any(s in text or s in tech for s in signals)


def _has_email_capture(profile: dict) -> bool:
    text = _website_text(profile)
    signals = ["subscribe", "newsletter", "email list", "sign up for",
               "join our list", "mailchimp", "klaviyo", "constant contact"]
    return any(s in text for s in signals)


def _has_pricing_page(profile: dict) -> bool:
    text = _website_text(profile)
    pages = profile.get("website_analysis", {}).get("internal_pages", [])
    if any(c in text for c in ["starting at", "per hour", "flat rate"]):
        return True
    for p in pages:
        slug = (p.get("url", "") + p.get("title", "")).lower()
        if any(k in slug for k in ["pric", "rate", "cost", "fee"]):
            return True
    return False


def _review_count(profile: dict) -> int:
    return profile.get("reviews", {}).get("total_reviews", 0) or 0


def _social_score(profile: dict) -> int:
    detected = profile.get("social_media", {}).get("detected_profiles", {})
    return len([v for v in detected.values() if v])


# ── Audit dimensions ────────────────────────────────────────────────────────

def _audit_automations(business: dict, profile: dict) -> dict:
    findings = []
    recs = []
    hours = 0.0

    has_booking = _has_booking_system(profile)
    phone = profile.get("website_analysis", {}).get("contact_info", {}).get("phone")
    has_site = bool(profile.get("website_analysis", {}).get("url"))

    if phone and not has_booking:
        findings.append(
            "Phone-only booking requires staff time for every appointment request."
        )
        recs.append(
            "Add an online booking widget (Calendly, Acuity, or Jane App) so customers "
            "can self-serve 24/7. Automate SMS reminders 24 hours before appointments "
            "to cut no-shows by up to 30 percent."
        )
        hours += 5.0

    if has_site and not has_booking:
        findings.append("No online booking system detected on the website.")
        recs.append(
            "A 24/7 self-serve booking page captures late-night decisions that phone-only "
            "businesses miss entirely."
        )
        hours += 3.0

    rc = _review_count(profile)
    if rc < 20:
        findings.append(
            "No customer reviews found yet, and no system in place to ask for them automatically."
            if rc == 0 else
            f"Just {rc} reviews so far, with no automated way to ask happy customers for more."
        )
        recs.append(
            "Set up an automated SMS or email request after each service. "
            "This alone typically doubles review velocity within 60 days."
        )
        hours += 2.0

    if not findings:
        findings.append("Basic automation signals present - opportunity lies in optimisation.")
        recs.append(
            "Connect your booking, invoicing, and follow-up tools into a single "
            "automated workflow to eliminate manual hand-offs."
        )
        hours = 2.0

    return {
        "title": "Automations",
        "findings": findings,
        "recommendations": recs,
        "estimated_hours_saved_per_week": round(hours, 1),
        "quick_win": not has_booking and bool(phone),
        "difficulty": "Low" if not has_booking else "Medium",
        "estimated_monthly_cost": "$49-$149/mo",
    }


def _audit_customer_service(business: dict, profile: dict) -> dict:
    findings = []
    recs = []
    hours = 0.0

    has_chat = _has_live_chat(profile)
    has_site = bool(profile.get("website_analysis", {}).get("url"))
    neg = str(profile.get("reviews", {}).get("negative_keywords", [])).lower()
    category = business.get("category", "").lower()

    if not has_chat and has_site:
        findings.append("No live chat or chatbot detected on the website.")
        recs.append(
            "Deploy a trained FAQ chatbot powered by AI on your website. "
            "Answer hours, pricing, and service questions automatically around the clock."
        )
        hours += 4.0

    if any(k in neg for k in ["reach", "respond", "answer", "call back", "return"]):
        findings.append(
            "Review text signals customers have difficulty reaching the business."
        )
        recs.append(
            "Implement missed-call text-back: when a call goes unanswered, an automated "
            "SMS replies within 30 seconds and captures the lead before they call a competitor."
        )
        hours += 3.0

    if any(k in category for k in ["plumb", "electr", "hvac", "roof", "contrac", "landscap"]):
        findings.append(
            "Trades businesses receive high volumes of after-hours quote requests."
        )
        recs.append(
            "Add an AI quote estimator to your website. Customers answer 5 questions and "
            "receive an instant ballpark estimate while you receive their project details."
        )
        hours += 6.0

    if not findings:
        findings.append(
            "Customer service infrastructure appears adequate - optimise for speed."
        )
        recs.append(
            "Add a proactive satisfaction check-in 3 days after service to build loyalty "
            "and surface issues before they become negative reviews."
        )
        hours = 1.5

    return {
        "title": "Customer Service",
        "findings": findings,
        "recommendations": recs,
        "estimated_hours_saved_per_week": round(hours, 1),
        "quick_win": not has_chat and has_site,
        "difficulty": "Low",
        "estimated_monthly_cost": "$79-$199/mo",
    }


def _audit_marketing(business: dict, profile: dict) -> dict:
    findings = []
    recs = []
    hours = 0.0

    social = _social_score(profile)
    rc = _review_count(profile)
    has_email = _has_email_capture(profile)
    has_site = bool(profile.get("website_analysis", {}).get("url"))
    city = business.get("city", "your area")
    category = business.get("category", "services")

    if rc < 50:
        findings.append(
            "No Google reviews yet — competitors with 100+ reviews earn far more clicks."
            if rc == 0 else
            f"Just {rc} Google reviews — competitors with 100+ reviews earn far more clicks."
        )
        recs.append(
            "Automate review requests via SMS immediately after each completed job. "
            "Businesses with 100+ fresh reviews earn 35 percent more clicks in Google Maps."
        )
        hours += 3.0

    if social < 2:
        findings.append(
            "No active social media presence detected."
            if social == 0 else
            f"Limited social media presence — only {social} active platform detected."
        )
        recs.append(
            "Use an AI content calendar to generate and schedule 3 posts per week across "
            "Facebook and Instagram. Consistent posting drives brand recall and repeat business."
        )
        hours += 4.0

    if not has_email and has_site:
        findings.append(
            "No email capture form detected - missing opportunity to own your audience."
        )
        recs.append(
            "Add a lead-capture form with a value offer such as a free estimate or seasonal "
            "discount. Build an automated email sequence: welcome, value content, testimonials, offer."
        )
        hours += 2.0

    if not findings:
        findings.append("Basic marketing signals are present - optimise for conversion.")
        recs.append(
            f"Run Google Local Service Ads for high-intent searches. "
            f"'{category} in {city}' queries convert at 3-5x the rate of social media traffic."
        )
        hours = 3.0

    return {
        "title": "Marketing",
        "findings": findings,
        "recommendations": recs,
        "estimated_hours_saved_per_week": round(hours, 1),
        "quick_win": rc < 50,
        "difficulty": "Low" if rc < 50 else "Medium",
        "estimated_monthly_cost": "$299-$599/mo",
    }


def _audit_operations(business: dict, profile: dict) -> dict:
    findings = []
    recs = []
    hours = 0.0

    category = business.get("category", "").lower()
    is_trades = any(k in category for k in
                    ["plumb", "electr", "hvac", "roof", "contrac", "landscap", "clean"])
    is_service = any(k in category for k in
                     ["salon", "spa", "clinic", "dental", "physio", "massage", "fitness"])
    is_retail = any(k in category for k in ["retail", "store", "shop", "supply"])

    if is_trades:
        findings.append(
            "Trades businesses spend significant time on job scheduling and crew dispatch."
        )
        recs.append(
            "Implement a field service management tool such as Jobber or ServiceM8 with AI "
            "route optimisation. Reduces drive time by 15-20 percent and automates job "
            "cards, invoices, and follow-ups in one workflow."
        )
        hours += 8.0

        findings.append("Manual quoting and invoicing creates delays and cash flow gaps.")
        recs.append(
            "AI-assisted quote templates let you enter scope and generate a professional PDF "
            "quote in 2 minutes. Connected invoicing with online payment links gets you paid faster."
        )
        hours += 5.0

    elif is_service:
        findings.append(
            "Service businesses lose revenue to scheduling gaps and no-shows."
        )
        recs.append(
            "AI schedule optimisation fills cancellation gaps automatically by sending waitlist "
            "offers via SMS - recover 5-10 missed appointments every month."
        )
        hours += 4.0

    elif is_retail:
        findings.append(
            "Retail operations benefit from demand forecasting to cut overstock and stockouts."
        )
        recs.append(
            "Implement inventory management with AI reorder alerts. "
            "Typically reduces capital tied up in slow-moving stock by 15-25 percent."
        )
        hours += 6.0

    if not findings:
        findings.append(
            "Standard operational processes - automation can still deliver meaningful time savings."
        )
        recs.append(
            "Audit your most repetitive tasks: quotes, reports, scheduling, and communication. "
            "Automating just 2-3 recurring tasks typically saves 5 or more hours per week."
        )
        hours = 3.0

    return {
        "title": "Operations",
        "findings": findings,
        "recommendations": recs,
        "estimated_hours_saved_per_week": round(hours, 1),
        "quick_win": is_trades,
        "difficulty": "Medium",
        "estimated_monthly_cost": "$99-$299/mo",
    }


def _audit_revenue(business: dict, profile: dict) -> dict:
    findings = []
    recs = []
    hours = 0.0

    has_pricing = _has_pricing_page(profile)
    text = _website_text(profile)

    if not has_pricing:
        findings.append(
            "Pricing is not visible on the website - customers must call to get basic information."
        )
        recs.append(
            "Add transparent pricing or service packages to your website. "
            "Businesses with visible pricing convert 60 percent more website visitors into inquiries."
        )
        hours += 2.0

    findings.append("No loyalty or referral program detected.")
    recs.append(
        "Launch a simple referral program: existing customers earn a discount for sending a friend. "
        "Referral customers have 37 percent higher retention and cost nothing to acquire."
    )
    hours += 2.0

    recurring_signals = ["seasonal", "annual", "maintenance", "checkup", "inspection", "renewal"]
    if not any(k in text for k in recurring_signals):
        findings.append("No recurring service or maintenance plan detected.")
        recs.append(
            "Package your services into a monthly or annual maintenance plan. "
            "Recurring revenue stabilises cash flow and dramatically increases customer lifetime value."
        )
        hours += 1.0

    return {
        "title": "Revenue Growth",
        "findings": findings,
        "recommendations": recs,
        "estimated_hours_saved_per_week": round(hours, 1),
        "quick_win": not has_pricing,
        "difficulty": "Low",
        "estimated_monthly_cost": "Varies",
    }


# ── Executive summary ────────────────────────────────────────────────────────

def _build_executive_summary(business: dict, findings: dict) -> dict:
    total_hours = sum(d.get("estimated_hours_saved_per_week", 0) for d in findings.values())
    quick_wins = [d["title"] for d in findings.values() if d.get("quick_win")]
    all_findings = []
    for d in findings.values():
        all_findings.extend(d.get("findings", []))

    name = business.get("name", "This business")
    count = len(all_findings)
    hours_str = f"{total_hours:.0f}"

    summary = (
        f"We looked at how {name} runs day to day and shows up online, and found "
        f"{count} clear ways to save time and win more customers using simple, proven tools. "
        f"Just the quick wins below could free up around {hours_str} hours a week — "
        "time you can put straight back into the work that grows the business."
    )

    return {
        "summary": summary,
        "total_hours_saved": total_hours,
        "quick_wins": quick_wins[:3],
        "total_opportunities": count,
    }


# ── PDF generation ───────────────────────────────────────────────────────────

def _generate_pdf(business: dict, findings: dict, site_dir: Path) -> Path:
    pdf_path = site_dir / "ai_opportunity_report.pdf"
    executive = _build_executive_summary(business, findings)

    if not FPDF_AVAILABLE:
        txt_path = site_dir / "ai_opportunity_report.txt"
        _write_text_report(business, findings, executive, txt_path)
        log.warning("[audit] fpdf2 not installed - wrote text report. Run: pip install fpdf2")
        return txt_path

    live_url = None
    dep_file = site_dir / "deployment.json"
    if dep_file.exists():
        try:
            live_url = json.loads(dep_file.read_text()).get("url")
        except Exception:
            pass

    pdf = BCOpportunityPDF(business, executive, findings, live_url)
    pdf.build_report()
    pdf.output(str(pdf_path))
    return pdf_path


def _write_text_report(business: dict, findings: dict, executive: dict, path: Path):
    name = business.get("name", "Business")
    today = date.today().strftime("%B %d, %Y")
    lines = [
        "=" * 70,
        "AI OPPORTUNITY AUDIT REPORT",
        name,
        f"Prepared: {today}",
        "=" * 70,
        "",
        "EXECUTIVE SUMMARY",
        "-" * 40,
        executive["summary"],
        f"Total estimated hours saved per week: {executive['total_hours_saved']:.0f}h",
        "Quick wins: " + (", ".join(executive["quick_wins"]) or "See recommendations below"),
        "",
    ]

    for dim in findings.values():
        lines += [
            dim["title"].upper(),
            "-" * 40,
            f"  Time saved: {dim['estimated_hours_saved_per_week']}h/week",
            f"  Estimated cost: {dim['estimated_monthly_cost']}",
            f"  Quick win: {'Yes' if dim['quick_win'] else 'No'}",
            "",
            "  Findings:",
        ]
        for f in dim.get("findings", []):
            lines.append(f"    * {f}")
        lines.append("")
        lines.append("  Recommendations:")
        for r in dim.get("recommendations", []):
            lines.append(f"    > {r}")
        lines.append("")

    quick_w = [d for d in findings.values() if d.get("quick_win")]
    lines += [
        "30/60/90-DAY ROADMAP",
        "-" * 40,
        "Days 1-30 (Quick Wins):",
    ]
    for d in quick_w[:2]:
        lines.append(f"  * Implement {d['title']} automation")
    if not quick_w:
        lines += [
            "  * Set up automated review request SMS after each service",
            "  * Add online booking or improved contact form",
        ]
    lines += [
        "Days 31-60 (Build Systems):",
        "  * Deploy chatbot or FAQ automation on website",
        "  * Launch email capture form and automated welcome sequence",
        "Days 61-90 (Scale and Measure):",
        "  * Review analytics and ROI from quick wins",
        "  * Launch customer referral program",
        "  * A/B test pricing page and calls-to-action",
        "",
        "NEXT STEPS",
        "-" * 40,
        "Contact us to build a custom implementation plan.",
        "victoriaai.ca  |  hello@victoriaai.ca",
    ]
    path.write_text("\n".join(lines))


# ── PDF class ────────────────────────────────────────────────────────────────

if FPDF_AVAILABLE:
    class BCOpportunityPDF(FPDF):
        NAVY = (26, 58, 92)
        GREEN = (34, 162, 98)
        LGREY = (245, 247, 250)
        MGREY = (120, 130, 145)
        WHITE = (255, 255, 255)
        DARK = (30, 35, 45)
        LBLUE = (180, 210, 240)

        def __init__(self, business, executive, findings, live_url=None):
            super().__init__(orientation="P", unit="mm", format="A4")
            self.business = business
            self.executive = executive
            self.findings = findings
            self.live_url = live_url
            self.set_auto_page_break(auto=True, margin=20)
            self.set_margins(20, 20, 20)

        def header(self):
            pass

        def footer(self):
            if self.page_no() == 1:
                return
            self.set_y(-12)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*self.MGREY)
            self.cell(0, 5, f"Page {self.page_no()}", align="C")

        def _rect(self, x, y, w, h, color):
            self.set_fill_color(*color)
            self.rect(x, y, w, h, "F")

        def _f(self, style="", size=10):
            self.set_font("Helvetica", style, size)

        def _c(self, color):
            self.set_text_color(*color)

        def cell(self, *args, **kwargs):
            args, kwargs = _pdf_safe_args(args, kwargs)
            return super().cell(*args, **kwargs)

        def multi_cell(self, *args, **kwargs):
            args, kwargs = _pdf_safe_args(args, kwargs)
            return super().multi_cell(*args, **kwargs)

        def build_report(self):
            self._cover()
            self._exec_summary()
            for dim in self.findings.values():
                self._dim_page(dim)
            self._roadmap()
            self._next_steps()

        def _cover(self):
            self.add_page()
            # Disable auto page break — cover intentionally places content near the bottom
            self.set_auto_page_break(False)
            w, h = self.w, self.h

            self._rect(0, 0, w, h * 0.55, self.NAVY)
            self._rect(0, h * 0.55 - 3, w, 6, self.GREEN)

            self._f("B", 11)
            self._c(self.GREEN)
            self.set_xy(20, 22)
            self.cell(0, 8, "VICTORIA AI")

            self._f("", 8)
            self._c(self.LBLUE)
            self.set_xy(20, 30)
            self.cell(0, 5, "AI and Automation Solutions for BC Small Business")

            name = self.business.get("name", "Your Business")
            self._f("B", 26)
            self._c(self.WHITE)
            self.set_xy(20, h * 0.22)
            self.multi_cell(w - 40, 12, name, align="C")

            # Track Y manually so subtitle and city don't overlap
            subtitle_y = self.get_y() + 5
            self._f("", 13)
            self._c(self.LBLUE)
            self.set_xy(20, subtitle_y)
            self.cell(w - 40, 8, "AI Opportunity Audit Report", align="C")

            today = date.today().strftime("%B %Y")
            city = self.business.get("city", "British Columbia")
            self._f("", 9)
            self._c((140, 180, 210))
            self.set_xy(20, subtitle_y + 11)
            self.cell(w - 40, 6, f"{city}  |  {today}", align="C")

            self._rect(0, h * 0.58, w, 36, self.LGREY)

            total = self.executive.get("total_hours_saved", 0)
            opps = self.executive.get("total_opportunities", 0)
            qw = len(self.executive.get("quick_wins", []))
            stats = [
                (f"{total:.0f}h", "Saved Per Week"),
                (str(opps), "Opportunities Found"),
                (str(qw), "Quick Wins"),
            ]
            cw = (w - 40) / 3
            for i, (val, label) in enumerate(stats):
                x = 20 + i * cw
                self._f("B", 20)
                self._c(self.GREEN)
                self.set_xy(x, h * 0.60)
                self.cell(cw, 10, val, align="C")
                self._f("", 8)
                self._c(self.MGREY)
                self.set_xy(x, h * 0.60 + 11)
                self.cell(cw, 5, label, align="C")

            if self.live_url:
                self._f("", 9)
                self._c(self.NAVY)
                self.set_xy(20, h * 0.58 + 28)
                self.cell(w - 40, 5, f"Website: {self.live_url}", align="C")

            self._rect(0, h - 28, w, 28, self.NAVY)
            self._f("", 9)
            self._c(self.LBLUE)
            self.set_xy(20, h - 18)
            self.cell(w - 40, 5,
                      "CONFIDENTIAL - Prepared exclusively for the business owner above",
                      align="C")
            self._f("", 8)
            self.set_xy(20, h - 12)
            self.cell(w - 40, 5, "victoriaai.ca  |  hello@victoriaai.ca", align="C")

            # Re-enable auto page break for remaining pages
            self.set_auto_page_break(auto=True, margin=20)

        def _exec_summary(self):
            self.add_page()
            self._page_header("Executive Summary")
            y = self.get_y() + 6

            self._f("", 11)
            self._c(self.DARK)
            self.set_xy(20, y)
            self.multi_cell(self.w - 40, 6.5, self.executive.get("summary", ""))
            y = self.get_y() + 8

            total = self.executive.get("total_hours_saved", 0)
            opps = self.executive.get("total_opportunities", 0)
            qw = len(self.executive.get("quick_wins", []))
            cw = (self.w - 40) / 3
            metrics = [
                (f"{total:.0f}h", "Hours Saved Per Week"),
                (str(opps), "Specific Opportunities"),
                (str(qw), "Quick Wins Identified"),
            ]
            for i, (val, label) in enumerate(metrics):
                x = 20 + i * cw
                self._rect(x + 2, y, cw - 4, 26, self.LGREY)
                self._f("B", 18)
                self._c(self.GREEN)
                self.set_xy(x + 2, y + 2)
                self.cell(cw - 4, 10, val, align="C")
                self._f("", 8)
                self._c(self.MGREY)
                self.set_xy(x + 2, y + 14)
                self.cell(cw - 4, 5, label, align="C")
            y += 32

            qws = self.executive.get("quick_wins", [])
            if qws:
                self._sec_header("Top Quick Wins", y)
                y += 10
                for item in qws:
                    self._bullet(item, y, green=True)
                    y += 7

            y += 4
            self._sec_header("What Is Inside This Report", y)
            y += 10
            for dim in self.findings.values():
                self._bullet(dim["title"], y)
                y += 7
            self._bullet("30 / 60 / 90-Day Implementation Roadmap", y)
            y += 7
            self._bullet("Next Steps and Recommended Action Plan", y)

        def _dim_page(self, dim: dict):
            self.add_page()
            self._page_header(dim.get("title", "Dimension"))
            y = self.get_y() + 6

            cw = (self.w - 40) / 4
            chips = [
                (f"{dim.get('estimated_hours_saved_per_week', 0)}h/wk", "Time Saved"),
                (dim.get("difficulty", "Medium"), "Difficulty"),
                (dim.get("estimated_monthly_cost", "Varies"), "Est. Cost"),
                ("Yes" if dim.get("quick_win") else "No", "Quick Win"),
            ]
            for i, (val, label) in enumerate(chips):
                x = 20 + i * cw
                is_qw = label == "Quick Win" and val == "Yes"
                bg = self.GREEN if is_qw else self.LGREY
                vc = self.WHITE if is_qw else self.GREEN
                lc = (220, 240, 220) if is_qw else self.MGREY
                self._rect(x + 1, y, cw - 2, 20, bg)
                # Use smaller font for longer values so they fit in the chip
                vsize = 9 if len(val) > 10 else 11
                self._f("B", vsize)
                self._c(vc)
                self.set_xy(x + 1, y + 2)
                self.cell(cw - 2, 8, val, align="C")
                self._f("", 7)
                self._c(lc)
                self.set_xy(x + 1, y + 11)
                self.cell(cw - 2, 5, label, align="C")
            y += 26

            findings_done = False
            for finding in dim.get("findings", []):
                if y > self.h - 40:
                    break
                if not findings_done:
                    self._sec_header("What We Found", y)
                    y += 10
                    findings_done = True
                self._bullet(finding, y, bullet="!")
                y += self._line_h(finding) + 4

            recs_done = False
            for rec in dim.get("recommendations", []):
                if y > self.h - 30:
                    break
                if not recs_done:
                    y += 2
                    self._sec_header("Recommendations", y)
                    y += 10
                    recs_done = True
                self._bullet(rec, y, green=True, bullet=">")
                y += self._line_h(rec) + 4

        def _roadmap(self):
            self.add_page()
            self._page_header("30 / 60 / 90-Day Implementation Roadmap")
            y = self.get_y() + 8

            qw = [d for d in self.findings.values() if d.get("quick_win")]
            phases = [
                {
                    "label": "Days 1-30",
                    "sub": "Quick Wins - Get Moving",
                    "color": self.GREEN,
                    "items": (
                        [f"Implement {d['title']} automation" for d in qw[:2]]
                        or [
                            "Set up automated review request SMS after each service",
                            "Add online booking or improved contact form to website",
                        ]
                    ),
                },
                {
                    "label": "Days 31-60",
                    "sub": "Build Systems - Create Consistency",
                    "color": self.NAVY,
                    "items": [
                        "Deploy website chatbot or FAQ automation",
                        "Launch email capture form and automated welcome sequence",
                        "Connect booking system to invoicing tool",
                    ],
                },
                {
                    "label": "Days 61-90",
                    "sub": "Scale and Measure - Compound the Gains",
                    "color": (80, 120, 170),
                    "items": [
                        "Review analytics: bookings, reviews, email signups",
                        "Launch customer referral program",
                        "A/B test pricing page and calls-to-action",
                        "Plan next automation phase based on ROI data",
                    ],
                },
            ]

            for phase in phases:
                self._rect(20, y, self.w - 40, 12, phase["color"])
                self._f("B", 11)
                self._c(self.WHITE)
                self.set_xy(24, y + 2)
                self.cell(70, 7, phase["label"])
                self._f("", 9)
                self._c((200, 220, 240))
                self.set_xy(96, y + 3)
                self.cell(self.w - 116, 6, phase["sub"])
                y += 14
                for item in phase["items"]:
                    self._bullet(item, y, bullet="+")
                    y += 8
                y += 4

        def _next_steps(self):
            self.add_page()
            self.set_auto_page_break(False)
            w, h = self.w, self.h
            self._rect(0, 0, w, h, self.NAVY)
            self._rect(0, 0, w, 8, self.GREEN)

            self._f("B", 22)
            self._c(self.WHITE)
            self.set_xy(20, 28)
            self.cell(w - 40, 12, "Your Next Steps", align="C", ln=True)

            self._f("", 11)
            self._c(self.LBLUE)
            self.set_xy(20, 44)
            self.multi_cell(
                w - 40, 7,
                "You've seen what's possible. The hardest part is starting — so keep it simple. "
                "Here are three easy steps:",
                align="C",
            )

            steps = [
                ("1", "Share this report",
                 "Forward it to your business partner, manager, or accountant."),
                ("2", "Choose one quick win",
                 "Pick the highest-impact item from Days 1-30 and commit to it this week."),
                ("3", "Book a strategy call",
                 "We will build a custom implementation plan at no obligation."),
            ]

            y = self.get_y() + 14
            for num, title, desc in steps:
                self._rect(20, y, w - 40, 28, (35, 70, 115))
                self._rect(20, y, 20, 28, self.GREEN)
                self._f("B", 16)
                self._c(self.WHITE)
                self.set_xy(20, y + 7)
                self.cell(20, 12, num, align="C")
                self._f("B", 12)
                self._c(self.WHITE)
                self.set_xy(44, y + 4)
                self.cell(w - 64, 7, title)
                self._f("", 9)
                self._c(self.LBLUE)
                self.set_xy(44, y + 13)
                self.multi_cell(w - 64, 6, desc)
                y += 34

            y += 10
            self._f("B", 14)
            self._c(self.GREEN)
            self.set_xy(20, y)
            self.cell(w - 40, 8, "Get in Touch", align="C", ln=True)

            self._f("", 10)
            self._c(self.WHITE)
            self.set_xy(20, y + 12)
            self.cell(w - 40, 6, "victoriaai.ca  |  hello@victoriaai.ca", align="C")

            self._f("", 8)
            self._c((120, 160, 200))
            today = date.today().strftime("%B %d, %Y")
            self.set_xy(20, h - 20)
            self.cell(
                w - 40, 5,
                f"Report generated {today}  |  Victoria AI  |  Victoria, BC",
                align="C",
            )

        def _page_header(self, title: str):
            w = self.w
            self._rect(0, 0, w, 22, self.NAVY)
            self._rect(0, 0, 5, 22, self.GREEN)
            self._f("B", 13)
            self._c(self.WHITE)
            self.set_xy(12, 6)
            self.cell(w - 60, 10, title.upper())
            self._f("", 8)
            self._c(self.LBLUE)
            self.set_xy(w - 55, 8)
            self.cell(50, 5, "VICTORIA AI | CONFIDENTIAL", align="R")
            self.set_xy(20, 26)

        def _sec_header(self, text: str, y: float):
            self._f("B", 9)
            self._c(self.NAVY)
            self.set_xy(20, y)
            self.cell(0, 6, text.upper())
            self.set_fill_color(*self.GREEN)
            self.rect(20, y + 6, self.w - 40, 0.5, "F")

        def _bullet(self, text: str, y: float, bullet: str = "-", green: bool = False):
            self.set_xy(22, y)
            if green:
                self._f("B", 9)
                self._c(self.GREEN)
                self.cell(4, 5, ">")
                self._f("", 9)
                self._c(self.DARK)
                self.set_xy(28, y)
            else:
                self._f("", 9)
                self._c(self.MGREY)
                self.cell(4, 5, bullet[:1] or "-")
                self._c(self.DARK)
                self.set_xy(28, y)
            self.multi_cell(self.w - 48, 5.5, text)

        def _line_h(self, text: str) -> float:
            return max(5.5, (len(text) // 95 + 1) * 5.5)

else:
    class BCOpportunityPDF:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise ImportError("fpdf2 is required. Run: pip install fpdf2")


def _slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("/", "-")
