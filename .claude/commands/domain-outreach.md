# Domain Outreach

Draft a cold email to a potential buyer for a domain in the App-Engine portfolio.

## Usage

Provide:
- The domain name (e.g., `signalbase.ai`)
- The target company or buyer type (e.g., "Series A analytics startup", or a specific company name)
- Any context about why they'd want it (optional — will be inferred if not provided)

## Output

A cold outreach email with this structure:

**Subject line**: Direct, no clickbait. State the domain or value immediately.

**Email body** (under 150 words):
1. One sentence on who you are and why you're reaching out.
2. One sentence on the domain and its specific relevance to their business.
3. One sentence on the opportunity — what owning it enables or protects against.
4. A soft close — asking if there's interest, not demanding a response.

No attachments mentioned. No "I hope this email finds you well." No "synergy."

## Tone

Professional. Peer-to-peer, not salesperson to prospect. The reader should feel like they're hearing from a fellow entrepreneur, not a domain broker.

## Context
- Domains are valued and appraised by `app-engine/modules/domains/appraisal.ts`
- Afternic and GoDaddy are the primary marketplaces — mention only if the buyer seems to prefer a brokered transaction
- Follow-up cadence: one follow-up after 5 business days, then let it go
