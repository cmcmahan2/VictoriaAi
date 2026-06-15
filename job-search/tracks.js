// Search tracks: where a Canadian post-grad can work, by sector and geography.
//
// Geographies are chosen for realistic work-authorization pathways for a
// Canadian citizen, and tagged with wage/benefit/tax context so the ranker
// can weight Christian's stated priorities (high wage, good benefits, abroad).

export const SECTORS = {
  golf: {
    label: 'Golf',
    // Queries are tried against job boards; broad-to-specific.
    queries: [
      'golf operations',
      'golf shop attendant',
      'pro shop',
      'golf club management',
      'caddie master',
      'golf analytics TrackMan',
    ],
  },
  finance: {
    label: 'Finance',
    queries: [
      'financial analyst',
      'investment analyst graduate',
      'economics research analyst',
      'FP&A analyst',
      'pricing analyst',
      'corporate finance graduate',
    ],
  },
  real_estate: {
    label: 'Real Estate & Development',
    queries: [
      'real estate analyst',
      'real estate development analyst',
      'property investment analyst',
      'acquisitions analyst',
      'appraisal analyst',
      'urban land economics',
    ],
  },
};

// Each geography documents the route a Canadian can actually use to work there.
export const GEOGRAPHIES = {
  CA: {
    label: 'Canada (home)',
    cities: ['Vancouver, BC', 'Victoria, BC', 'Toronto, ON', 'Calgary, AB'],
    work_authorization: 'Citizen — no permit required',
    tax_note: 'Standard federal + provincial income tax',
    wage_context: 'Baseline. Strong in BC/ON/AB; lower entry pay in golf.',
    abroad: false,
  },
  AE: {
    label: 'United Arab Emirates (Dubai/Abu Dhabi)',
    cities: ['Dubai', 'Abu Dhabi'],
    work_authorization: 'Employer-sponsored work permit + residence visa',
    tax_note: 'No personal income tax — take-home pay is high',
    wage_context:
      'Tax-free salaries, housing/flights/insurance often included. Booming luxury golf + real estate. Strong fit for high-wage + benefits + abroad.',
    abroad: true,
  },
  GB: {
    label: 'United Kingdom',
    cities: ['London', 'Edinburgh', 'Manchester'],
    work_authorization:
      'Youth Mobility Scheme visa — open to Canadians aged 18–35, up to 2 years, no employer sponsor needed',
    tax_note: 'PAYE income tax + National Insurance',
    wage_context: 'Deep finance market (London). St Andrews / golf heritage.',
    abroad: true,
  },
  AU: {
    label: 'Australia',
    cities: ['Sydney', 'Melbourne', 'Gold Coast'],
    work_authorization:
      'Working Holiday visa (subclass 417) — Canadians aged 18–35, up to 3 years',
    tax_note: 'Income tax applies; high statutory minimum wage',
    wage_context:
      'Very high minimum wage, strong benefits, year-round golf on the Gold Coast.',
    abroad: true,
  },
  NZ: {
    label: 'New Zealand',
    cities: ['Auckland', 'Queenstown'],
    work_authorization: 'Working Holiday visa — Canadians aged 18–35, up to 23 months',
    tax_note: 'Income tax applies',
    wage_context: 'Resort golf, growing finance hubs.',
    abroad: true,
  },
  IE: {
    label: 'Ireland',
    cities: ['Dublin'],
    work_authorization:
      'Working Holiday Authorisation — Canadians aged 18–35, up to 2 years',
    tax_note: 'PAYE income tax',
    wage_context: 'EU finance hub; tech + fund administration.',
    abroad: true,
  },
  US: {
    label: 'United States',
    cities: ['Scottsdale, AZ', 'New York, NY', 'Dallas, TX'],
    work_authorization:
      'TN visa under CUSMA — "Economist" is a TN-eligible profession, so a Financial Economics grad can qualify for finance/economics roles with a US job offer',
    tax_note: 'Federal + state income tax (no state tax in TX/FL/NV)',
    wage_context:
      'Highest finance salaries globally; premier golf market (Scottsdale, Florida).',
    abroad: true,
  },
};

// ISO country code -> code used by the live job-board MCP search tools.
export const COUNTRY_CODES = Object.keys(GEOGRAPHIES);

// Build a list of {sector, geo, city, query} search jobs to run / link out.
export function buildSearchPlan({ sectors, geos } = {}) {
  const useSectors = sectors?.length ? sectors : Object.keys(SECTORS);
  const useGeos = geos?.length ? geos : Object.keys(GEOGRAPHIES);
  const plan = [];
  for (const sector of useSectors) {
    for (const geo of useGeos) {
      const g = GEOGRAPHIES[geo];
      if (!g) continue;
      // Use the lead (broadest) query per sector for the plan; the ranker
      // and search links expand to the rest.
      plan.push({
        sector,
        sectorLabel: SECTORS[sector].label,
        geo,
        geoLabel: g.label,
        city: g.cities[0],
        queries: SECTORS[sector].queries,
        abroad: g.abroad,
      });
    }
  }
  return plan;
}

// Deep links the user can click to run each search themselves.
export function searchLinks(query, geo) {
  const g = GEOGRAPHIES[geo];
  const where = encodeURIComponent(g?.cities?.[0] || '');
  const what = encodeURIComponent(query);
  const indeedDomain = {
    CA: 'ca.indeed.com',
    GB: 'uk.indeed.com',
    AU: 'au.indeed.com',
    NZ: 'nz.indeed.com',
    IE: 'ie.indeed.com',
    AE: 'ae.indeed.com',
    US: 'www.indeed.com',
  }[geo] || 'www.indeed.com';
  return {
    indeed: `https://${indeedDomain}/jobs?q=${what}&l=${where}`,
    linkedin: `https://www.linkedin.com/jobs/search/?keywords=${what}&location=${where}`,
  };
}
