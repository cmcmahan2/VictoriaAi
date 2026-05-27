"""
Phase 4 - AI Opportunity Audit

Produce a professional PDF proposal for the business owner covering 5 dimensions:
  1. Automations      - booking, invoicing, follow-ups
  2. Customer Service - chatbots, after-hours, missed calls
  3. Marketing        - ads, SEO, email, review generation
  4. Operations       - scheduling, inventory, document automation
  5. Revenue          - upsells, adjacent services, loyalty/referral

PDF structure (max 10 pages):
  Cover, Executive Summary, 5x audit pages, 30/60/90 day roadmap, Next Steps

Saved to: ./output/{business_slug}/ai_opportunity_report.pdf
"""

import json
from pathlib import Path


def run_audit(profile_dir: str, output_dir: str = "./output") -> Path:
    """Entry point for Phase 4. Reads profile and generates PDF report."""
    profile_path = Path(profile_dir) / "profile.json"
    profile  = json.loads(profile_path.read_text())
    business = profile["business"]
    slug     = _slugify(business.get("name", "unknown-business"))
    site_dir = Path(output_dir) / slug
    site_dir.mkdir(parents=True, exist_ok=True)
    findings = {
        "automations":     _audit_automations(business, profile),
        "customer_service":_audit_customer_service(business, profile),
        "marketing":       _audit_marketing(business, profile),
        "operations":      _audit_operations(business, profile),
        "revenue":         _audit_revenue(business, profile),
    }
    pdf_path = _generate_pdf(business, findings, site_dir)
    print(f"[audit] PDF report saved -> {pdf_path}")
    return pdf_path


def _audit_automations(business, profile):
    # TODO: check for booking form, invoicing signals, follow-up/CRM signals
    raise NotImplementedError("Automations audit not yet implemented")

def _audit_customer_service(business, profile):
    # TODO: check for live chat, analyse reviews for contact difficulty signals
    raise NotImplementedError("Customer service audit not yet implemented")

def _audit_marketing(business, profile):
    # TODO: check social posting frequency, review recency, GMB completeness
    raise NotImplementedError("Marketing audit not yet implemented")

def _audit_operations(business, profile):
    # TODO: infer crew size, check for inventory/quote/contract signals
    raise NotImplementedError("Operations audit not yet implemented")

def _audit_revenue(business, profile):
    # TODO: check pricing visibility, service breadth, seasonal opportunities
    raise NotImplementedError("Revenue audit not yet implemented")


def _generate_pdf(business, findings, site_dir):
    """
    Render AI Opportunity Report PDF using fpdf2.
    Sections: Cover, Executive Summary, 5x audit pages, Roadmap, Next Steps.
    """
    pdf_path = site_dir / "ai_opportunity_report.pdf"
    # TODO: initialise fpdf2, render all sections, save to pdf_path
    raise NotImplementedError("PDF generation not yet implemented")


def _slugify(name):
    return name.lower().replace(" ", "-").replace("/", "-")
