'use client';

import React, { useState, useReducer, useCallback, useEffect } from 'react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts';

// ─────────────────────────────────────────────
// CONSTANTS
// ─────────────────────────────────────────────

const INDUSTRIES = [
  'Retail','Restaurant/Food Service','Healthcare/Medical','Legal Services',
  'Accounting/Finance','Real Estate','Construction/Trades','E-commerce',
  'Education/Training','Fitness/Wellness','Marketing/Agency','Manufacturing',
  'Logistics/Transportation','Insurance','Hospitality/Travel','Non-Profit','Other',
];

const SUB_INDUSTRIES = {
  'Retail':['General Merchandise','Specialty/Boutique','Grocery/Food','Auto Parts/Accessories','Home & Garden'],
  'Restaurant/Food Service':['Full-Service Restaurant','Fast Casual','Food Truck/Pop-up','Catering','Bakery/Café'],
  'Healthcare/Medical':['Primary Care','Dental','Mental Health/Therapy','Chiropractic/PT','Veterinary'],
  'Legal Services':['Family Law','Business/Corporate','Personal Injury','Real Estate Law','Criminal Defense'],
  'Accounting/Finance':['Tax Preparation','Bookkeeping','Financial Planning','Business Accounting','Payroll Services'],
  'Real Estate':['Residential Sales','Commercial Real Estate','Property Management','Real Estate Investment','Rental/Leasing'],
  'Construction/Trades':['General Contracting','HVAC/Plumbing/Electric','Landscaping','Remodeling','Specialty Trades'],
  'E-commerce':['Physical Products','Digital Products','Dropshipping','Marketplace Seller','D2C Brand'],
  'Education/Training':['Tutoring/Test Prep','Corporate Training','Online Courses','Vocational/Skills','Childcare/Preschool'],
  'Fitness/Wellness':['Gym/Studio','Personal Training','Nutrition/Coaching','Spa/Massage','Yoga/Pilates'],
  'Marketing/Agency':['Digital Marketing','Creative/Design','PR/Communications','SEO/Content','Social Media Management'],
  'Manufacturing':['Consumer Goods','Industrial/B2B','Food & Beverage','Medical Devices','Custom/Job Shop'],
  'Logistics/Transportation':['Freight/Shipping','Last-Mile Delivery','Courier Services','Warehousing','Moving/Relocation'],
  'Insurance':['Property & Casualty','Life & Health','Commercial Lines','Independent Agency','Specialty Insurance'],
  'Hospitality/Travel':['Hotel/B&B','Tour Operator','Event Venue','Travel Agency','Short-Term Rental'],
  'Non-Profit':['Social Services','Education Foundation','Healthcare Non-Profit','Arts & Culture','Community Organization'],
  'Other':['Professional Services','Technology/Software','Agriculture','Media/Publishing','Other/Unique Business'],
};

const TECH_STACK_OPTIONS = [
  'QuickBooks','Xero','FreshBooks','Salesforce','HubSpot','Zoho',
  'Shopify','WooCommerce','Square','Toast','Mindbody','Jobber',
  'ServiceTitan','Slack','Teams','Asana','Monday','ClickUp',
  'Mailchimp','Klaviyo','Hootsuite','Google Workspace','Microsoft 365',
  'No dedicated tools','Paper-based','Other',
];

const TIME_ALLOCATION_DEFAULTS = [
  'Customer acquisition','Customer service/support','Admin & paperwork',
  'Financial management','Team management','Product/service delivery',
  'Marketing & content','Inventory/supply chain','Reporting & analytics',
];

const REVENUE_STREAMS = [
  'Product sales','Service fees','Subscriptions','Contracts/Retainers',
  'Consulting','Licensing','Advertising','Referral/Commission','Other',
];

const ACQUISITION_METHODS = [
  'Word of mouth','Google/SEO','Paid ads','Social media',
  'Cold outreach','Events/networking','Partnerships','Repeat business',
];

const REVENUE_LEAKS = [
  'Leads not converting','Customers churning','Slow invoicing/collections',
  'Underpricing','Operational inefficiency','Staff turnover','Missed upsells',
];

const PAIN_AREAS = [
  'Sales & lead generation','Customer service','Marketing & content',
  'Financial management','HR & hiring','Operations & fulfillment',
  'Reporting & decision-making','IT & tools management',
];

const GOALS_12_MONTHS = [
  'Increase revenue by 20%+','Reduce operating costs','Save 10+ hours/week',
  'Improve customer satisfaction','Scale without hiring more',
  'Launch a new product/service','Enter a new market','Prepare to sell/exit',
];

const BLOCKERS = [
  'Cost','Time to implement','Team resistance',"Don't know where to start",
  'Past bad experiences','No clear ROI','Lack of technical knowledge','Nothing — ready to go',
];

const AI_EXPERIENCE = [
  'Never used AI tools','Used ChatGPT casually','Used AI for content creation',
  'Tried AI tools but abandoned them','Have AI integrated in 1-2 workflows',
  'AI is core to our operations',
];

const STEP_NAMES = ['Business Identity','Operations','Customers & Revenue','Pain Points','AI Readiness','Final Context'];

// ─────────────────────────────────────────────
// INITIAL STATE & REDUCER
// ─────────────────────────────────────────────

const initialFormState = {
  step1: {
    businessName:'',industry:'',subIndustry:'',businessModel:'',
    employees:'',locations:'',revenueRange:'',yearsInBusiness:'',geographicMarket:'',
  },
  step2: {
    coreOperations:'',revenueStreams:[],timeAllocation:[...TIME_ALLOCATION_DEFAULTS.slice(0,5)],
    techStack:[],toolIntegration:'',manualHours:10,remoteWork:'',
  },
  step3: {
    avgTransactionValue:'',acquisitionMethods:[],retentionRate:'',
    revenueLeak:[],hasCRM:'',followUpMethod:'',
  },
  step4: {
    painRatings:Object.fromEntries(PAIN_AREAS.map(a => [a,0])),
    keepsMeAwake:'',goals:[],blockers:[],
  },
  step5: {
    ownerTechComfort:5,teamTechComfort:5,aiExperience:[],
    dayToDayManager:'',monthlyBudget:'',implementationTimeline:'',
  },
  step6: {
    competitorAdvantage:'',automateOneThingTomorrow:'',
    openToReplacing:'',fractionalConsultant:'',howFound:'',
  },
};

function formReducer(state, action) {
  switch (action.type) {
    case 'UPDATE_STEP':
      return { ...state, [action.step]: { ...state[action.step], [action.field]: action.value } };
    case 'TOGGLE_MULTI': {
      const cur = state[action.step][action.field];
      const next = cur.includes(action.value)
        ? cur.filter(v => v !== action.value)
        : (action.max && cur.length >= action.max) ? cur : [...cur, action.value];
      return { ...state, [action.step]: { ...state[action.step], [action.field]: next } };
    }
    case 'UPDATE_PAIN':
      return { ...state, step4: { ...state.step4, painRatings: { ...state.step4.painRatings, [action.area]: action.value } } };
    case 'REORDER_TIME':
      return { ...state, step2: { ...state.step2, timeAllocation: action.value } };
    default:
      return state;
  }
}

// ─────────────────────────────────────────────
// THEME HELPERS  (avoids dynamic Tailwind classes)
// ─────────────────────────────────────────────

const C = {
  base:    '#0d1117',
  card:    '#161b22',
  card2:   '#1c2128',
  border:  '#30363d',
  green:   '#3fb950',
  red:     '#f85149',
  blue:    '#58a6ff',
  yellow:  '#d29922',
  purple:  '#bc8cff',
  orange:  '#ffa657',
  accent:  '#1f6feb',
  txtPri:  '#e6edf3',
  txtSec:  '#8b949e',
  txtMut:  '#6e7681',
};

const card = { background: C.card, border: `1px solid ${C.border}` };
const card2 = { background: C.card2, border: `1px solid ${C.border}` };

// ─────────────────────────────────────────────
// BASE UI COMPONENTS
// ─────────────────────────────────────────────

function FormCard({ children, title, subtitle }) {
  return (
    <div className="rounded-2xl p-6 mb-4" style={card}>
      {title && <h3 className="text-base font-semibold mb-1" style={{ color: C.txtPri }}>{title}</h3>}
      {subtitle && <p className="text-sm mb-4" style={{ color: C.txtSec }}>{subtitle}</p>}
      {children}
    </div>
  );
}

function FieldLabel({ children, required }) {
  return (
    <label className="block text-sm font-medium mb-2" style={{ color: C.txtSec }}>
      {children}{required && <span className="ml-1" style={{ color: C.green }}>*</span>}
    </label>
  );
}

function StyledInput({ value, onChange, placeholder, type = 'text' }) {
  return (
    <input
      type={type}
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full rounded-lg px-4 py-3 text-sm outline-none transition-all"
      style={{
        background: C.card2, border: `1px solid ${C.border}`,
        color: C.txtPri,
      }}
      onFocus={e => { e.target.style.borderColor = C.green; }}
      onBlur={e => { e.target.style.borderColor = C.border; }}
    />
  );
}

function StyledSelect({ value, onChange, options, placeholder }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="w-full rounded-lg px-4 py-3 text-sm outline-none cursor-pointer"
      style={{ background: C.card2, border: `1px solid ${C.border}`, color: value ? C.txtPri : C.txtMut }}
    >
      <option value="">{placeholder || 'Select...'}</option>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

function RadioGroup({ value, onChange, options, inline = false }) {
  return (
    <div className={`flex ${inline ? 'flex-wrap gap-3' : 'flex-col gap-2'}`}>
      {options.map(opt => (
        <label key={opt} className="flex items-center gap-3 cursor-pointer select-none" onClick={() => onChange(opt)}>
          <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition-all"
            style={{
              border: `2px solid ${value === opt ? C.green : C.border}`,
              background: value === opt ? C.green : 'transparent',
            }}>
            {value === opt && <div className="w-2 h-2 rounded-full bg-white" />}
          </div>
          <span className="text-sm" style={{ color: C.txtSec }}>{opt}</span>
        </label>
      ))}
    </div>
  );
}

function MultiSelect({ selected, onToggle, options, max, cols = 2 }) {
  return (
    <div className={`grid gap-2`} style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
      {options.map(opt => {
        const on = selected.includes(opt);
        const disabled = max && !on && selected.length >= max;
        return (
          <button key={opt} type="button" onClick={() => !disabled && onToggle(opt)}
            className="text-left px-3 py-2 rounded-lg text-sm transition-all"
            style={{
              background: on ? `${C.green}18` : disabled ? `${C.card2}80` : C.card2,
              border: `1px solid ${on ? C.green : disabled ? C.border + '50' : C.border}`,
              color: on ? C.green : disabled ? C.txtMut : C.txtSec,
              cursor: disabled ? 'not-allowed' : 'pointer',
              opacity: disabled ? 0.5 : 1,
            }}>
            {opt}
          </button>
        );
      })}
    </div>
  );
}

function StarRating({ area, value, onChange }) {
  return (
    <div className="flex items-center gap-3 py-2.5 border-b" style={{ borderColor: C.border }}>
      <span className="text-sm w-52 flex-shrink-0" style={{ color: C.txtSec }}>{area}</span>
      <div className="flex gap-1">
        {[1,2,3,4,5].map(s => (
          <button key={s} type="button" onClick={() => onChange(area, s)}
            className="text-xl transition-all hover:scale-110"
            style={{ color: s <= value ? C.yellow : C.border }}>★</button>
        ))}
      </div>
      <span className="text-xs ml-1" style={{ color: C.txtMut }}>
        {['','Low pain','Minor','Moderate','High','Critical'][value] || 'Not rated'}
      </span>
    </div>
  );
}

function RangeSlider({ value, onChange, min, max, leftLabel, rightLabel, unit = '' }) {
  return (
    <div>
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs" style={{ color: C.txtMut }}>{leftLabel}</span>
        <span className="text-xl font-bold" style={{ color: C.green }}>{value}{unit}</span>
        <span className="text-xs" style={{ color: C.txtMut }}>{rightLabel}</span>
      </div>
      <input type="range" min={min} max={max} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full h-2 rounded-lg appearance-none cursor-pointer"
        style={{ accentColor: C.green, background: C.card2 }}
      />
    </div>
  );
}

// Searchable tech-stack multi-select
function TechStackSelect({ selected, onToggle }) {
  const [search, setSearch] = useState('');
  const filtered = TECH_STACK_OPTIONS.filter(t => t.toLowerCase().includes(search.toLowerCase()));
  return (
    <div>
      <StyledInput value={search} onChange={setSearch} placeholder="Search tools..." />
      <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto mt-3 pr-1">
        {filtered.map(opt => {
          const on = selected.includes(opt);
          return (
            <button key={opt} type="button" onClick={() => onToggle(opt)}
              className="text-left px-3 py-2 rounded-lg text-xs transition-all"
              style={{
                background: on ? `${C.green}18` : C.card2,
                border: `1px solid ${on ? C.green : C.border}`,
                color: on ? C.green : C.txtSec,
              }}>
              {opt}
            </button>
          );
        })}
      </div>
      {selected.length > 0 && (
        <p className="text-xs mt-2" style={{ color: C.green }}>Selected: {selected.join(', ')}</p>
      )}
    </div>
  );
}

// HTML5 drag-to-reorder list
function RankOrderList({ items, onChange }) {
  const [dragging, setDragging] = useState(null);
  const [over, setOver] = useState(null);

  const handleDrop = idx => {
    if (dragging === null || dragging === idx) return;
    const next = [...items];
    const [moved] = next.splice(dragging, 1);
    next.splice(idx, 0, moved);
    onChange(next);
    setDragging(null);
    setOver(null);
  };

  return (
    <div className="space-y-2">
      <p className="text-xs mb-3" style={{ color: C.txtMut }}>Drag to reorder — #1 = most time spent</p>
      {items.map((item, idx) => (
        <div key={item} draggable
          onDragStart={() => setDragging(idx)}
          onDragOver={e => { e.preventDefault(); setOver(idx); }}
          onDrop={() => handleDrop(idx)}
          onDragEnd={() => { setDragging(null); setOver(null); }}
          className="flex items-center gap-3 rounded-lg px-4 py-3 cursor-grab active:cursor-grabbing transition-all"
          style={{
            background: over === idx ? `${C.green}12` : C.card2,
            border: `1px solid ${over === idx ? C.green : C.border}`,
          }}>
          <span className="text-sm font-mono w-6" style={{ color: C.txtMut }}>{idx + 1}.</span>
          <span style={{ color: C.txtSec, fontSize: 18 }}>⠿</span>
          <span className="text-sm" style={{ color: C.txtPri }}>{item}</span>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────
// STEP 1 — Business Identity
// ─────────────────────────────────────────────

function Step1({ state, dispatch }) {
  const upd = (f, v) => dispatch({ type: 'UPDATE_STEP', step: 'step1', field: f, value: v });
  return (
    <div className="space-y-4">
      <FormCard title="Business Basics">
        <div className="space-y-4">
          <div>
            <FieldLabel required>Business Name</FieldLabel>
            <StyledInput value={state.businessName} onChange={v => upd('businessName', v)} placeholder="Your business name" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <FieldLabel required>Industry</FieldLabel>
              <StyledSelect value={state.industry}
                onChange={v => { upd('industry', v); upd('subIndustry', ''); }}
                options={INDUSTRIES} placeholder="Select industry" />
            </div>
            <div>
              <FieldLabel>Sub-Industry</FieldLabel>
              <StyledSelect value={state.subIndustry} onChange={v => upd('subIndustry', v)}
                options={SUB_INDUSTRIES[state.industry] || []}
                placeholder={state.industry ? 'Select sub-industry' : 'Select industry first'} />
            </div>
          </div>
          <div>
            <FieldLabel required>Business Model</FieldLabel>
            <RadioGroup value={state.businessModel} onChange={v => upd('businessModel', v)}
              options={['B2B','B2C','Both']} inline />
          </div>
        </div>
      </FormCard>

      <FormCard title="Company Size & Scope">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <FieldLabel required>Number of Employees</FieldLabel>
              <StyledSelect value={state.employees} onChange={v => upd('employees', v)}
                options={['Solo','2-5','6-15','16-30','31-75','76-200']} placeholder="Select size" />
            </div>
            <div>
              <FieldLabel required>Number of Locations</FieldLabel>
              <RadioGroup value={state.locations} onChange={v => upd('locations', v)}
                options={['1','2-3','4-10','10+']} inline />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <FieldLabel required>Annual Revenue Range</FieldLabel>
              <StyledSelect value={state.revenueRange} onChange={v => upd('revenueRange', v)}
                options={['Under $100K','$100K-$500K','$500K-$1M','$1M-$3M','$3M-$10M','$10M+']}
                placeholder="Select range" />
            </div>
            <div>
              <FieldLabel required>Years in Business</FieldLabel>
              <StyledSelect value={state.yearsInBusiness} onChange={v => upd('yearsInBusiness', v)}
                options={['Less than 1','1-3','3-7','7-15','15+']} placeholder="Select years" />
            </div>
          </div>
          <div>
            <FieldLabel required>Geographic Market</FieldLabel>
            <RadioGroup value={state.geographicMarket} onChange={v => upd('geographicMarket', v)}
              options={['Local','Regional','National','International']} inline />
          </div>
        </div>
      </FormCard>
    </div>
  );
}

// ─────────────────────────────────────────────
// STEP 2 — Operations Deep Dive
// ─────────────────────────────────────────────

function Step2({ state, dispatch }) {
  const upd = (f, v) => dispatch({ type: 'UPDATE_STEP', step: 'step2', field: f, value: v });
  const tog = (f, v, max) => dispatch({ type: 'TOGGLE_MULTI', step: 'step2', field: f, value: v, max });
  return (
    <div className="space-y-4">
      <FormCard title="Core Operations" subtitle="Walk us through a typical day or week in your business">
        <textarea value={state.coreOperations} onChange={e => upd('coreOperations', e.target.value)}
          rows={5} placeholder="Describe your day-to-day operations, key workflows, and how value is delivered to customers..."
          className="w-full rounded-lg px-4 py-3 text-sm outline-none resize-none"
          style={{ background: C.card2, border: `1px solid ${C.border}`, color: C.txtPri }} />
      </FormCard>

      <FormCard title="Primary Revenue Streams" subtitle="Select your top revenue streams (up to 3)">
        <MultiSelect selected={state.revenueStreams} onToggle={v => tog('revenueStreams', v, 3)}
          options={REVENUE_STREAMS} max={3} />
      </FormCard>

      <FormCard title="Where Does Your Time Go?" subtitle="Rank these by time consumed — drag to reorder">
        <RankOrderList items={state.timeAllocation}
          onChange={v => dispatch({ type: 'REORDER_TIME', value: v })} />
      </FormCard>

      <FormCard title="Current Tech Stack" subtitle="Which tools does your business use?">
        <TechStackSelect selected={state.techStack} onToggle={v => tog('techStack', v)} />
      </FormCard>

      <FormCard title="Operations Details">
        <div className="space-y-6">
          <div>
            <FieldLabel>How integrated are your current tools?</FieldLabel>
            <RadioGroup value={state.toolIntegration} onChange={v => upd('toolIntegration', v)}
              options={['Completely siloed','Some manual data transfer','Partially automated','Fully integrated']} />
          </div>
          <div>
            <FieldLabel>Weekly hours on manual / repetitive tasks</FieldLabel>
            <RangeSlider value={state.manualHours} onChange={v => upd('manualHours', v)}
              min={0} max={60} leftLabel="0 hrs" rightLabel="60 hrs" unit=" hrs/week" />
          </div>
          <div>
            <FieldLabel>Work arrangement</FieldLabel>
            <RadioGroup value={state.remoteWork} onChange={v => upd('remoteWork', v)}
              options={['All in-person','Hybrid','Fully remote']} inline />
          </div>
        </div>
      </FormCard>
    </div>
  );
}

// ─────────────────────────────────────────────
// STEP 3 — Customer & Revenue Intelligence
// ─────────────────────────────────────────────

function Step3({ state, dispatch }) {
  const upd = (f, v) => dispatch({ type: 'UPDATE_STEP', step: 'step3', field: f, value: v });
  const tog = (f, v, max) => dispatch({ type: 'TOGGLE_MULTI', step: 'step3', field: f, value: v, max });
  return (
    <div className="space-y-4">
      <FormCard title="Transaction & Customer Value">
        <div className="space-y-5">
          <div>
            <FieldLabel required>Average Transaction or Contract Value</FieldLabel>
            <StyledSelect value={state.avgTransactionValue} onChange={v => upd('avgTransactionValue', v)}
              options={['Under $50','$50-$200','$200-$1K','$1K-$5K','$5K-$25K','$25K+']}
              placeholder="Select value range" />
          </div>
          <div>
            <FieldLabel>Customer Acquisition Methods</FieldLabel>
            <MultiSelect selected={state.acquisitionMethods} onToggle={v => tog('acquisitionMethods', v)}
              options={ACQUISITION_METHODS} />
          </div>
          <div>
            <FieldLabel>Customer Retention Rate</FieldLabel>
            <RadioGroup value={state.retentionRate} onChange={v => upd('retentionRate', v)}
              options={['Low (most are one-time)','Medium (some repeat)','High (mostly loyal)']} />
          </div>
        </div>
      </FormCard>

      <FormCard title="Revenue Leaks" subtitle="Where are you losing the most revenue? (up to 2)">
        <MultiSelect selected={state.revenueLeak} onToggle={v => tog('revenueLeak', v, 2)}
          options={REVENUE_LEAKS} max={2} />
      </FormCard>

      <FormCard title="CRM & Follow-Up">
        <div className="space-y-5">
          <div>
            <FieldLabel>Do you have a CRM?</FieldLabel>
            <RadioGroup value={state.hasCRM} onChange={v => upd('hasCRM', v)}
              options={['No','Spreadsheet-based','Basic CRM','Advanced CRM']} inline />
          </div>
          <div>
            <FieldLabel>How do you handle customer follow-up?</FieldLabel>
            <RadioGroup value={state.followUpMethod} onChange={v => upd('followUpMethod', v)}
              options={['Manually/ad hoc','Basic email','Automated sequences','AI-assisted']} />
          </div>
        </div>
      </FormCard>
    </div>
  );
}

// ─────────────────────────────────────────────
// STEP 4 — Pain Points & Priorities
// ─────────────────────────────────────────────

function Step4({ state, dispatch }) {
  const upd = (f, v) => dispatch({ type: 'UPDATE_STEP', step: 'step4', field: f, value: v });
  const tog = (f, v, max) => dispatch({ type: 'TOGGLE_MULTI', step: 'step4', field: f, value: v, max });
  return (
    <div className="space-y-4">
      <FormCard title="Pain Level Assessment" subtitle="Rate your pain in each area (1 = manageable, 5 = critical)">
        <div>
          {PAIN_AREAS.map(area => (
            <StarRating key={area} area={area} value={state.painRatings[area]}
              onChange={(a, v) => dispatch({ type: 'UPDATE_PAIN', area: a, value: v })} />
          ))}
        </div>
      </FormCard>

      <FormCard title="What Keeps You Up at Night?" subtitle="Your top 1-2 business frustrations in your own words">
        <textarea value={state.keepsMeAwake} onChange={e => upd('keepsMeAwake', e.target.value)}
          rows={4} placeholder="Be honest — what's the biggest thing holding your business back right now?"
          className="w-full rounded-lg px-4 py-3 text-sm outline-none resize-none"
          style={{ background: C.card2, border: `1px solid ${C.border}`, color: C.txtPri }} />
      </FormCard>

      <FormCard title="12-Month Goals" subtitle="Select your top 2 priorities (in order of importance)">
        <MultiSelect selected={state.goals} onToggle={v => tog('goals', v, 2)}
          options={GOALS_12_MONTHS} max={2} />
        {state.goals.length > 0 && (
          <p className="text-sm mt-3" style={{ color: C.txtSec }}>
            Priority 1: <span style={{ color: C.green }}>{state.goals[0]}</span>
            {state.goals[1] && <> · Priority 2: <span style={{ color: C.green }}>{state.goals[1]}</span></>}
          </p>
        )}
      </FormCard>

      <FormCard title="Technology Adoption Blockers">
        <MultiSelect selected={state.blockers} onToggle={v => tog('blockers', v)}
          options={BLOCKERS} />
      </FormCard>
    </div>
  );
}

// ─────────────────────────────────────────────
// STEP 5 — AI Readiness Assessment
// ─────────────────────────────────────────────

function Step5({ state, dispatch }) {
  const upd = (f, v) => dispatch({ type: 'UPDATE_STEP', step: 'step5', field: f, value: v });
  const tog = (f, v) => dispatch({ type: 'TOGGLE_MULTI', step: 'step5', field: f, value: v });
  return (
    <div className="space-y-4">
      <FormCard title="Technology Comfort Levels">
        <div className="space-y-6">
          <div>
            <FieldLabel>Owner / Founder Tech Comfort</FieldLabel>
            <RangeSlider value={state.ownerTechComfort} onChange={v => upd('ownerTechComfort', v)}
              min={1} max={10} leftLabel="Technophobe" rightLabel="Early Adopter" unit="/10" />
          </div>
          <div>
            <FieldLabel>Team Tech Comfort</FieldLabel>
            <RangeSlider value={state.teamTechComfort} onChange={v => upd('teamTechComfort', v)}
              min={1} max={10} leftLabel="Technophobe" rightLabel="Early Adopter" unit="/10" />
          </div>
        </div>
      </FormCard>

      <FormCard title="Prior AI Experience" subtitle="Select all that apply">
        <MultiSelect selected={state.aiExperience} onToggle={v => tog('aiExperience', v)}
          options={AI_EXPERIENCE} cols={2} />
      </FormCard>

      <FormCard title="Implementation Details">
        <div className="space-y-5">
          <div>
            <FieldLabel>Who would manage AI tools day-to-day?</FieldLabel>
            <RadioGroup value={state.dayToDayManager} onChange={v => upd('dayToDayManager', v)}
              options={['Just me (owner)','Office manager/ops person','Dedicated team member',"We'd need to hire",'Looking to outsource']} />
          </div>
          <div>
            <FieldLabel required>Monthly Budget for New Tools</FieldLabel>
            <StyledSelect value={state.monthlyBudget} onChange={v => upd('monthlyBudget', v)}
              options={['$0 — need free tools only','$100-$300','$300-$750','$750-$2,000','$2,000-$5,000','$5,000+']}
              placeholder="Select budget range" />
          </div>
          <div>
            <FieldLabel>Implementation Timeline</FieldLabel>
            <RadioGroup value={state.implementationTimeline} onChange={v => upd('implementationTimeline', v)}
              options={['Immediate (this month)','Short-term (1-3 months)','Medium-term (3-6 months)','Planning phase (6-12 months)']} />
          </div>
        </div>
      </FormCard>
    </div>
  );
}

// ─────────────────────────────────────────────
// STEP 6 — Final Context (Optional)
// ─────────────────────────────────────────────

function Step6({ state, dispatch }) {
  const upd = (f, v) => dispatch({ type: 'UPDATE_STEP', step: 'step6', field: f, value: v });
  return (
    <div className="space-y-4">
      <div className="text-center py-6">
        <div className="text-5xl mb-3">🎯</div>
        <h3 className="text-xl font-semibold" style={{ color: C.txtPri }}>Almost there!</h3>
        <p className="text-sm mt-1" style={{ color: C.txtSec }}>
          These optional details make your report significantly more personalized and actionable.
        </p>
      </div>

      <FormCard title="Competitive Landscape">
        <FieldLabel>What advantage do your biggest competitors have over you? (optional)</FieldLabel>
        <StyledInput value={state.competitorAdvantage} onChange={v => upd('competitorAdvantage', v)}
          placeholder="e.g., Bigger marketing budget, more locations, better technology..." />
      </FormCard>

      <FormCard title="Dream Automation">
        <FieldLabel>One thing you wish you could automate tomorrow (optional)</FieldLabel>
        <StyledInput value={state.automateOneThingTomorrow} onChange={v => upd('automateOneThingTomorrow', v)}
          placeholder="e.g., Following up with leads, scheduling, generating reports..." />
      </FormCard>

      <FormCard title="Preferences">
        <div className="space-y-5">
          <div>
            <FieldLabel>Open to replacing existing tools if something better exists?</FieldLabel>
            <RadioGroup value={state.openToReplacing} onChange={v => upd('openToReplacing', v)}
              options={['Yes','Maybe','No']} inline />
          </div>
          <div>
            <FieldLabel>Would you consider hiring a fractional AI consultant?</FieldLabel>
            <RadioGroup value={state.fractionalConsultant} onChange={v => upd('fractionalConsultant', v)}
              options={['Yes definitely','Possibly if ROI is clear','No — prefer DIY','Not sure']} />
          </div>
          <div>
            <FieldLabel>How did you find this tool?</FieldLabel>
            <StyledSelect value={state.howFound} onChange={v => upd('howFound', v)}
              options={['Google','Referral','Social media','Consultant recommended','Other']}
              placeholder="Select source" />
          </div>
        </div>
      </FormCard>
    </div>
  );
}

// ─────────────────────────────────────────────
// API CALL
// ─────────────────────────────────────────────

async function generateReport(formState, apiKey) {
  const { step1, step2, step3, step4, step5, step6 } = formState;

  const systemPrompt = `You are a senior AI transformation consultant with deep expertise across industries, operational efficiency, revenue optimization, and practical AI implementation for small and medium businesses. You have helped 500+ SMBs adopt AI tools. Your analysis is data-driven, industry-specific, brutally honest, and immediately actionable. You understand that SMBs have limited budgets, small teams, and low tolerance for complexity. You always prioritize ROI, simplicity, and quick wins alongside longer-term strategy. Return ONLY valid JSON with no markdown, no code fences, no commentary outside the JSON structure.`;

  const userPrompt = `Analyze this business and generate a comprehensive AI transformation report.

BUSINESS PROFILE:
- Business Name: ${step1.businessName}
- Industry: ${step1.industry}${step1.subIndustry ? ` (${step1.subIndustry})` : ''}
- Business Model: ${step1.businessModel}
- Team Size: ${step1.employees} employees
- Locations: ${step1.locations}
- Annual Revenue: ${step1.revenueRange}
- Years in Business: ${step1.yearsInBusiness}
- Geographic Market: ${step1.geographicMarket}

OPERATIONS:
- Core Operations Description: ${step2.coreOperations}
- Primary Revenue Streams: ${step2.revenueStreams.join(', ') || 'Not specified'}
- Time Allocation (most → least consumed): ${step2.timeAllocation.join(' → ')}
- Current Tech Stack: ${step2.techStack.join(', ') || 'No dedicated tools'}
- Tool Integration Level: ${step2.toolIntegration || 'Not specified'}
- Weekly Hours on Manual Tasks: ${step2.manualHours} hrs/week
- Work Arrangement: ${step2.remoteWork || 'Not specified'}

CUSTOMERS & REVENUE:
- Average Transaction/Contract Value: ${step3.avgTransactionValue}
- Customer Acquisition Methods: ${step3.acquisitionMethods.join(', ') || 'Not specified'}
- Customer Retention Rate: ${step3.retentionRate || 'Not specified'}
- Primary Revenue Leaks: ${step3.revenueLeak.join(', ') || 'Not specified'}
- CRM Status: ${step3.hasCRM || 'Not specified'}
- Customer Follow-up Method: ${step3.followUpMethod || 'Not specified'}

PAIN POINTS (1–5 severity):
${Object.entries(step4.painRatings).map(([a,r])=>`- ${a}: ${r}/5${r>=4?' (CRITICAL)':r>=3?' (HIGH)':''}`).join('\n')}
- Key Frustrations: ${step4.keepsMeAwake || 'Not provided'}
- Top 12-Month Goals (priority order): ${step4.goals.join(', then ') || 'Not specified'}
- Tech Adoption Blockers: ${step4.blockers.join(', ') || 'Not specified'}

AI READINESS:
- Owner Tech Comfort: ${step5.ownerTechComfort}/10
- Team Tech Comfort: ${step5.teamTechComfort}/10
- Prior AI Experience: ${step5.aiExperience.join(', ') || 'None'}
- Day-to-Day AI Manager: ${step5.dayToDayManager || 'Not specified'}
- Monthly Tool Budget: ${step5.monthlyBudget || 'Not specified'}
- Implementation Timeline: ${step5.implementationTimeline || 'Not specified'}

ADDITIONAL CONTEXT:
- Competitor Advantage Over Them: ${step6.competitorAdvantage || 'Not provided'}
- Dream Automation: ${step6.automateOneThingTomorrow || 'Not provided'}
- Open to Replacing Tools: ${step6.openToReplacing || 'Not specified'}
- Fractional AI Consultant Interest: ${step6.fractionalConsultant || 'Not specified'}

Generate a deeply personalized, industry-specific AI transformation report. Be concrete with tool names, realistic ROI numbers, and first steps. Return exactly this JSON structure:

{
  "businessProfile": {
    "summary": "3-sentence synthesis of this specific business",
    "archetype": "The [Specific Creative Name] Business",
    "maturityScore": 0,
    "maturityLabel": "AI Beginner"
  },
  "opportunityScore": {
    "overall": 0,
    "label": "Untapped",
    "breakdown": {
      "operationalEfficiency": 0,
      "revenueGrowth": 0,
      "customerExperience": 0,
      "costReduction": 0,
      "competitiveAdvantage": 0
    },
    "benchmarkNote": "How this compares to similar businesses"
  },
  "executiveSummary": "4-5 sentence personalized summary",
  "topOpportunities": [
    {
      "rank": 1,
      "title": "specific opportunity title",
      "category": "Operations",
      "problemSolved": "1 sentence",
      "solution": "2-3 sentence description",
      "impact": "Transformational",
      "effort": "Quick Win",
      "timeToImplement": "1-2 weeks",
      "weeklyTimeSaved": "X hrs/week",
      "estimatedMonthlyROI": "$X-$Y",
      "confidenceLevel": "High",
      "primaryTool": { "name": "Tool Name", "cost": "$X/mo", "url": "https://example.com" },
      "alternativeTools": ["Tool2", "Tool3"],
      "firstStep": "Exact action they can take today",
      "warning": "One risk to consider or null"
    }
  ],
  "quickWins": [
    {
      "action": "specific action",
      "timeRequired": "30 minutes",
      "cost": "Free",
      "expectedOutcome": "what happens"
    }
  ],
  "automationMap": [
    {
      "currentProcess": "manual task",
      "automatedVersion": "automated version",
      "toolSuggestion": "specific tool",
      "complexityToAutomate": "Simple"
    }
  ],
  "roadmap": [
    {
      "phase": "Week 1-2: Foundation",
      "theme": "theme title",
      "objective": "what this accomplishes",
      "actions": ["action1", "action2", "action3"],
      "milestone": "how they know this phase is complete",
      "estimatedCost": "$X/month"
    },
    {
      "phase": "Month 1-2: Quick Wins",
      "theme": "theme title",
      "objective": "objective",
      "actions": ["action1", "action2", "action3"],
      "milestone": "milestone",
      "estimatedCost": "$X/month"
    },
    {
      "phase": "Month 3-4: Optimization",
      "theme": "theme title",
      "objective": "objective",
      "actions": ["action1", "action2", "action3"],
      "milestone": "milestone",
      "estimatedCost": "$X/month"
    },
    {
      "phase": "Month 5-6: Scale",
      "theme": "theme title",
      "objective": "objective",
      "actions": ["action1", "action2", "action3"],
      "milestone": "milestone",
      "estimatedCost": "$X/month"
    }
  ],
  "financialProjection": {
    "estimatedAnnualTimeSaved": "X-Y hours/year",
    "estimatedAnnualCostSaved": "$X-$Y",
    "estimatedRevenueUpside": "$X-$Y",
    "totalAnnualImpact": "$X-$Y",
    "paybackPeriod": "X-Y weeks",
    "assumptions": "key assumptions"
  },
  "riskAssessment": [
    {
      "risk": "risk description",
      "likelihood": "High",
      "mitigation": "mitigation strategy"
    }
  ],
  "industryBenchmark": {
    "insight": "What leading businesses in their industry are doing with AI now",
    "gap": "Where this business is currently behind",
    "opportunity": "Competitive advantage available if they act now"
  },
  "consultantNote": "A personalized, direct 2-3 sentence message. Be candid and specific to their situation."
}

Rules: Generate exactly 5 topOpportunities, 4 quickWins, 5 automationMap entries, exactly 4 roadmap phases, and 3-4 riskAssessment items. All scores must be integers 0-100.`;

  const res = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ apiKey, systemPrompt, userPrompt }),
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.error?.message || `API Error: ${res.status}`);
  }

  const text = data.content?.[0]?.text || '';
  return JSON.parse(text);
}

// ─────────────────────────────────────────────
// LOADING SCREEN
// ─────────────────────────────────────────────

function LoadingScreen() {
  const steps = [
    'Analyzing your business profile...',
    'Identifying high-impact AI opportunities...',
    'Calculating ROI projections...',
    'Building your personalized roadmap...',
    'Benchmarking against your industry...',
    'Finalizing your transformation report...',
  ];
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setIdx(p => (p < steps.length - 1 ? p + 1 : p)), 3500);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: C.base }}>
      <div className="text-center max-w-sm px-4">
        <div className="relative w-24 h-24 mx-auto mb-8">
          <div className="absolute inset-0 rounded-full animate-ping opacity-30"
            style={{ background: `${C.green}30`, border: `2px solid ${C.green}` }} />
          <div className="absolute inset-0 rounded-full animate-spin"
            style={{ border: `3px solid ${C.card}`, borderTopColor: C.green }} />
          <div className="absolute inset-3 rounded-full flex items-center justify-center text-3xl"
            style={{ background: C.card }}>🤖</div>
        </div>
        <h2 className="text-2xl font-bold mb-2" style={{ color: C.txtPri }}>Analyzing Your Business</h2>
        <p className="text-sm mb-8" style={{ color: C.txtSec }}>
          Claude AI is crafting your personalized transformation report…
        </p>
        <div className="space-y-3 text-left">
          {steps.map((s, i) => (
            <div key={i} className="flex items-center gap-3 text-sm transition-all duration-500"
              style={{ color: i < idx ? C.green : i === idx ? C.txtPri : C.txtMut }}>
              <span className="w-4 flex-shrink-0 font-mono">
                {i < idx ? '✓' : i === idx ? '●' : '○'}
              </span>
              <span>{s}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// REPORT SUB-COMPONENTS
// ─────────────────────────────────────────────

function Gauge({ value }) {
  const r = 48;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - value / 100);
  const color = value >= 70 ? C.green : value >= 40 ? C.yellow : C.red;
  return (
    <svg width={120} height={120} viewBox="0 0 120 120" className="mx-auto">
      <circle cx="60" cy="60" r={r} fill="none" stroke={C.card2} strokeWidth="10" />
      <circle cx="60" cy="60" r={r} fill="none" stroke={color} strokeWidth="10"
        strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round" transform="rotate(-90 60 60)"
        style={{ transition: 'stroke-dashoffset 1.2s ease-in-out' }} />
      <text x="60" y="54" textAnchor="middle" fill={C.txtPri} fontSize="22" fontWeight="bold">{value}</text>
      <text x="60" y="70" textAnchor="middle" fill={C.txtMut} fontSize="10">/100</text>
    </svg>
  );
}

function SectionTitle({ icon, title, subtitle }) {
  return (
    <div className="flex items-start gap-3 mb-5">
      <span className="text-2xl mt-0.5">{icon}</span>
      <div>
        <h2 className="text-lg font-bold" style={{ color: C.txtPri }}>{title}</h2>
        {subtitle && <p className="text-xs mt-0.5" style={{ color: C.txtSec }}>{subtitle}</p>}
      </div>
    </div>
  );
}

function OpportunityCard({ opp, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen);

  const impactStyle = {
    'Transformational': { bg: `${C.purple}18`, border: C.purple, color: C.purple },
    'High': { bg: `${C.green}18`, border: C.green, color: C.green },
    'Medium': { bg: `${C.yellow}18`, border: C.yellow, color: C.yellow },
    'Low': { bg: `${C.txtMut}18`, border: C.txtMut, color: C.txtMut },
  }[opp.impact] || { bg: `${C.txtMut}18`, border: C.txtMut, color: C.txtMut };

  const effortStyle = {
    'Quick Win': { bg: `${C.green}15`, color: C.green },
    'Moderate': { bg: `${C.yellow}15`, color: C.yellow },
    'Strategic Investment': { bg: `${C.purple}15`, color: C.purple },
  }[opp.effort] || { bg: `${C.txtMut}15`, color: C.txtMut };

  return (
    <div className="rounded-xl overflow-hidden mb-3" style={{ border: `1px solid ${C.border}`, background: C.card }}>
      <button onClick={() => setOpen(p => !p)}
        className="w-full text-left p-5 flex items-start justify-between gap-4 transition-all hover:opacity-90">
        <div className="flex items-start gap-4 min-w-0">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 font-bold text-sm"
            style={{ background: impactStyle.bg, color: impactStyle.color }}>
            {opp.rank}
          </div>
          <div className="min-w-0">
            <h4 className="font-semibold mb-1.5" style={{ color: C.txtPri }}>{opp.title}</h4>
            <div className="flex flex-wrap gap-2">
              <span className="text-xs px-2 py-0.5 rounded" style={{ background: C.card2, color: C.txtMut }}>{opp.category}</span>
              <span className="text-xs px-2 py-0.5 rounded" style={{ background: impactStyle.bg, color: impactStyle.color }}>{opp.impact}</span>
              <span className="text-xs px-2 py-0.5 rounded" style={{ background: effortStyle.bg, color: effortStyle.color }}>{opp.effort}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4 flex-shrink-0">
          <div className="text-right hidden sm:block">
            <div className="text-sm font-semibold" style={{ color: C.green }}>{opp.weeklyTimeSaved}</div>
            <div className="text-xs" style={{ color: C.txtMut }}>saved/week</div>
          </div>
          <span style={{ color: C.txtMut }}>{open ? '▼' : '▶'}</span>
        </div>
      </button>

      {open && (
        <div className="px-5 pb-5 border-t" style={{ borderColor: C.border }}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-4">
            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: C.txtMut }}>Problem Solved</p>
                <p className="text-sm" style={{ color: C.txtSec }}>{opp.problemSolved}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: C.txtMut }}>AI Solution</p>
                <p className="text-sm" style={{ color: C.txtSec }}>{opp.solution}</p>
              </div>
              {opp.warning && (
                <div className="rounded-lg p-3" style={{ background: `${C.yellow}12`, border: `1px solid ${C.yellow}40` }}>
                  <p className="text-xs font-semibold mb-1" style={{ color: C.yellow }}>⚠ Consider This</p>
                  <p className="text-xs" style={{ color: C.yellow + 'cc' }}>{opp.warning}</p>
                </div>
              )}
            </div>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                {[
                  ['Time to Implement', opp.timeToImplement, C.txtPri],
                  ['Monthly ROI Est.', opp.estimatedMonthlyROI, C.green],
                  ['Confidence', opp.confidenceLevel, C.txtPri],
                  ['Time Saved', opp.weeklyTimeSaved, C.green],
                ].map(([lbl, val, col]) => (
                  <div key={lbl} className="rounded-lg p-3" style={{ background: C.card2 }}>
                    <p className="text-xs mb-1" style={{ color: C.txtMut }}>{lbl}</p>
                    <p className="text-sm font-semibold" style={{ color: col }}>{val}</p>
                  </div>
                ))}
              </div>
              {opp.primaryTool && (
                <div className="rounded-lg p-3" style={{ background: `${C.green}10`, border: `1px solid ${C.green}40` }}>
                  <p className="text-xs font-semibold mb-2" style={{ color: C.green }}>Primary Tool</p>
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium" style={{ color: C.txtPri }}>{opp.primaryTool.name}</span>
                    <span className="text-xs" style={{ color: C.green }}>{opp.primaryTool.cost}</span>
                  </div>
                  {opp.alternativeTools?.length > 0 && (
                    <p className="text-xs mt-1" style={{ color: C.txtMut }}>Alt: {opp.alternativeTools.join(', ')}</p>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className="mt-4 rounded-lg p-4" style={{ background: `${C.accent}15`, border: `1px solid ${C.accent}40` }}>
            <p className="text-xs font-semibold mb-1" style={{ color: C.blue }}>🚀 Your First Step (Do This Today)</p>
            <p className="text-sm" style={{ color: C.txtPri }}>{opp.firstStep}</p>
          </div>
        </div>
      )}
    </div>
  );
}

const PHASE_COLORS = [
  { border: C.green, dot: C.green, label: C.green, bg: `${C.green}08` },
  { border: C.blue, dot: C.blue, label: C.blue, bg: `${C.blue}08` },
  { border: C.purple, dot: C.purple, label: C.purple, bg: `${C.purple}08` },
  { border: C.orange, dot: C.orange, label: C.orange, bg: `${C.orange}08` },
];

function RoadmapPhase({ phase, idx }) {
  const col = PHASE_COLORS[idx % PHASE_COLORS.length];
  return (
    <div className="rounded-xl p-5" style={{ background: col.bg, border: `1px solid ${col.border}30` }}>
      <div className="flex items-center gap-2 mb-3">
        <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: col.dot }} />
        <span className="text-xs font-bold uppercase tracking-wider" style={{ color: col.label }}>{phase.phase}</span>
      </div>
      <h4 className="font-semibold mb-1" style={{ color: C.txtPri }}>{phase.theme}</h4>
      <p className="text-sm mb-4" style={{ color: C.txtSec }}>{phase.objective}</p>
      <ul className="space-y-2 mb-4">
        {phase.actions?.map((a, i) => (
          <li key={i} className="flex items-start gap-2 text-sm" style={{ color: C.txtSec }}>
            <span className="flex-shrink-0 mt-0.5" style={{ color: col.dot }}>→</span>
            <span>{a}</span>
          </li>
        ))}
      </ul>
      <div className="flex justify-between items-start pt-3" style={{ borderTop: `1px solid ${col.border}30` }}>
        <div>
          <p className="text-xs" style={{ color: C.txtMut }}>Milestone</p>
          <p className="text-xs mt-0.5" style={{ color: C.txtSec }}>{phase.milestone}</p>
        </div>
        <div className="text-right">
          <p className="text-xs" style={{ color: C.txtMut }}>Est. Cost</p>
          <p className="text-sm font-bold mt-0.5" style={{ color: col.label }}>{phase.estimatedCost}</p>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// FULL REPORT
// ─────────────────────────────────────────────

function Report({ data, businessName, onReset }) {
  const radarData = data.opportunityScore ? [
    { subject: 'Operations', value: data.opportunityScore.breakdown.operationalEfficiency },
    { subject: 'Revenue', value: data.opportunityScore.breakdown.revenueGrowth },
    { subject: 'Customer Exp.', value: data.opportunityScore.breakdown.customerExperience },
    { subject: 'Cost Red.', value: data.opportunityScore.breakdown.costReduction },
    { subject: 'Competitive', value: data.opportunityScore.breakdown.competitiveAdvantage },
  ] : [];

  const scoreColor = data.opportunityScore?.overall >= 70 ? C.green
    : data.opportunityScore?.overall >= 45 ? C.yellow : C.red;

  return (
    <div className="min-h-screen pb-20" style={{ background: C.base }}>
      {/* Hero */}
      <div className="text-center py-14 px-4" style={{ background: `linear-gradient(180deg, ${C.card} 0%, ${C.base} 100%)` }}>
        <div className="inline-flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-full mb-4"
          style={{ background: `${C.green}18`, border: `1px solid ${C.green}50`, color: C.green }}>
          ✓ Report Generated Successfully
        </div>
        <h1 className="text-4xl font-black mb-2" style={{ color: C.txtPri }}>
          {businessName ? `${businessName}'s` : 'Your'} AI Transformation Report
        </h1>
        <p className="text-sm" style={{ color: C.txtSec }}>
          Powered by Claude AI · {new Date().toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'})}
        </p>
        <div className="flex justify-center gap-3 mt-5">
          <button onClick={() => window.print()}
            className="text-sm px-5 py-2 rounded-lg font-medium transition-all hover:opacity-80"
            style={{ background: C.green, color: '#000' }}>
            ⬇ Print / Save PDF
          </button>
          <button onClick={onReset}
            className="text-sm px-5 py-2 rounded-lg font-medium transition-all hover:opacity-80"
            style={{ background: C.card2, border: `1px solid ${C.border}`, color: C.txtSec }}>
            Analyze Another Business
          </button>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 space-y-4">

        {/* Business Profile + Opportunity Score */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 rounded-2xl p-6" style={card}>
            <SectionTitle icon="🏢" title="Business Profile" />
            <div className="inline-block px-3 py-1 rounded-full text-sm font-medium mb-4"
              style={{ background: `${C.purple}18`, border: `1px solid ${C.purple}50`, color: C.purple }}>
              {data.businessProfile?.archetype}
            </div>
            <p className="text-sm leading-relaxed mb-6" style={{ color: C.txtSec }}>{data.businessProfile?.summary}</p>
            <div className="flex items-center gap-5">
              <Gauge value={data.businessProfile?.maturityScore || 0} />
              <div>
                <div className="text-lg font-bold" style={{ color: C.txtPri }}>{data.businessProfile?.maturityLabel}</div>
                <div className="text-sm mt-0.5" style={{ color: C.txtMut }}>AI Maturity Level</div>
              </div>
            </div>
          </div>

          <div className="rounded-2xl p-6" style={card}>
            <SectionTitle icon="📊" title="Opportunity Score" />
            <div className="text-center mb-4">
              <div className="text-6xl font-black" style={{ color: scoreColor }}>{data.opportunityScore?.overall}</div>
              <div className="text-sm mt-1 font-medium" style={{ color: scoreColor }}>{data.opportunityScore?.label}</div>
            </div>
            <div style={{ height: 180 }}>
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData} outerRadius={60}>
                  <PolarGrid stroke={C.border} />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: C.txtMut, fontSize: 9 }} />
                  <PolarRadiusAxis domain={[0,100]} tick={false} axisLine={false} />
                  <Radar dataKey="value" stroke={C.green} fill={C.green} fillOpacity={0.15} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
            <p className="text-xs mt-2" style={{ color: C.txtMut }}>{data.opportunityScore?.benchmarkNote}</p>
          </div>
        </div>

        {/* Executive Summary */}
        <div className="rounded-2xl p-6"
          style={{ background: `linear-gradient(135deg, ${C.green}12, ${C.purple}08)`, border: `1px solid ${C.green}30` }}>
          <SectionTitle icon="💼" title="Executive Summary" />
          <p className="text-sm leading-relaxed" style={{ color: C.txtPri }}>{data.executiveSummary}</p>
        </div>

        {/* Top Opportunities */}
        <div>
          <div className="mb-3">
            <SectionTitle icon="🎯" title="Top AI Opportunities"
              subtitle="Ranked by impact and fit for your specific business — click to expand" />
          </div>
          {data.topOpportunities?.map((opp, i) => (
            <OpportunityCard key={opp.rank} opp={opp} defaultOpen={i === 0} />
          ))}
        </div>

        {/* Quick Wins */}
        <div className="rounded-2xl p-6" style={card}>
          <SectionTitle icon="⚡" title="Quick Wins" subtitle="Actions you can take this week with minimal effort" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data.quickWins?.map((win, i) => (
              <div key={i} className="rounded-xl p-4" style={card2}>
                <div className="flex justify-between items-start mb-2">
                  <span className="text-xs font-medium px-2 py-0.5 rounded"
                    style={{ background: `${C.green}18`, color: C.green }}>{win.timeRequired}</span>
                  <span className="text-xs" style={{ color: C.txtMut }}>{win.cost}</span>
                </div>
                <p className="text-sm font-medium mb-1" style={{ color: C.txtPri }}>{win.action}</p>
                <p className="text-xs" style={{ color: C.txtSec }}>{win.expectedOutcome}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Automation Map */}
        <div className="rounded-2xl p-6" style={card}>
          <SectionTitle icon="🤖" title="Automation Map" subtitle="Your current manual processes — and what they look like automated" />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  {['Current Manual Process','Automated Version','Tool','Complexity'].map(h => (
                    <th key={h} className="text-left py-2 pr-4 text-xs font-semibold uppercase tracking-wider"
                      style={{ color: C.txtMut }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.automationMap?.map((row, i) => {
                  const compColor = { Simple: C.green, Moderate: C.yellow, Complex: C.purple }[row.complexityToAutomate] || C.txtMut;
                  return (
                    <tr key={i} style={{ borderBottom: `1px solid ${C.border}30` }}>
                      <td className="py-3 pr-4" style={{ color: C.txtSec }}>{row.currentProcess}</td>
                      <td className="py-3 pr-4" style={{ color: C.txtPri }}>{row.automatedVersion}</td>
                      <td className="py-3 pr-4 font-medium" style={{ color: C.green }}>{row.toolSuggestion}</td>
                      <td className="py-3">
                        <span className="text-xs px-2 py-0.5 rounded"
                          style={{ background: `${compColor}18`, color: compColor }}>{row.complexityToAutomate}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Roadmap */}
        <div>
          <div className="mb-3">
            <SectionTitle icon="🗺️" title="6-Month Implementation Roadmap"
              subtitle="Your step-by-step path from where you are now to AI-powered operations" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.roadmap?.map((phase, i) => <RoadmapPhase key={i} phase={phase} idx={i} />)}
          </div>
        </div>

        {/* Financial Projection */}
        <div className="rounded-2xl p-6" style={card}>
          <SectionTitle icon="💰" title="Financial Impact Projection" subtitle="Estimated annual value of AI transformation" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            {[
              { label: 'Time Saved / Year', val: data.financialProjection?.estimatedAnnualTimeSaved, col: C.blue },
              { label: 'Cost Savings / Year', val: data.financialProjection?.estimatedAnnualCostSaved, col: C.green },
              { label: 'Revenue Upside', val: data.financialProjection?.estimatedRevenueUpside, col: C.purple },
              { label: 'Total Annual Impact', val: data.financialProjection?.totalAnnualImpact, col: C.orange },
            ].map(({ label, val, col }) => (
              <div key={label} className="rounded-xl p-4" style={card2}>
                <p className="text-xs mb-2" style={{ color: C.txtMut }}>{label}</p>
                <p className="text-base font-bold" style={{ color: col }}>{val}</p>
              </div>
            ))}
          </div>
          <div className="rounded-xl p-4 flex justify-between items-start gap-4"
            style={{ background: `${C.green}10`, border: `1px solid ${C.green}30` }}>
            <div>
              <p className="text-xs font-semibold mb-1" style={{ color: C.green }}>Payback Period</p>
              <p className="text-xl font-black" style={{ color: C.txtPri }}>{data.financialProjection?.paybackPeriod}</p>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold mb-1" style={{ color: C.txtMut }}>Key Assumptions</p>
              <p className="text-xs" style={{ color: C.txtSec }}>{data.financialProjection?.assumptions}</p>
            </div>
          </div>
        </div>

        {/* Risk Assessment */}
        <div className="rounded-2xl p-6" style={card}>
          <SectionTitle icon="⚠️" title="Risk Assessment" subtitle="Challenges to watch and how to mitigate them" />
          <div className="space-y-3">
            {data.riskAssessment?.map((risk, i) => {
              const col = { High: C.red, Medium: C.yellow, Low: C.green }[risk.likelihood] || C.txtMut;
              return (
                <div key={i} className="flex gap-4 rounded-xl p-4" style={card2}>
                  <div className="flex-shrink-0 text-center w-14">
                    <span className="text-xs font-bold px-2 py-1 rounded"
                      style={{ background: `${col}18`, color: col }}>{risk.likelihood}</span>
                  </div>
                  <div>
                    <p className="text-sm font-medium mb-0.5" style={{ color: C.txtPri }}>{risk.risk}</p>
                    <p className="text-xs" style={{ color: C.txtSec }}>Mitigation: {risk.mitigation}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Industry Benchmark */}
        <div className="rounded-2xl p-6" style={card}>
          <SectionTitle icon="📈" title="Industry Benchmark" subtitle="How you compare to similar businesses right now" />
          <div className="space-y-3">
            {[
              { label: 'What Industry Leaders Are Doing', text: data.industryBenchmark?.insight, col: C.blue },
              { label: "Where You're Currently Behind", text: data.industryBenchmark?.gap, col: C.yellow },
              { label: 'Your Competitive Opportunity', text: data.industryBenchmark?.opportunity, col: C.green },
            ].map(({ label, text, col }) => (
              <div key={label} className="rounded-xl p-4"
                style={{ background: `${col}10`, border: `1px solid ${col}30` }}>
                <p className="text-xs font-semibold mb-1.5" style={{ color: col }}>{label}</p>
                <p className="text-sm" style={{ color: C.txtSec }}>{text}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Consultant Note */}
        <div className="rounded-2xl p-8"
          style={{ background: `linear-gradient(135deg, ${C.purple}15, ${C.green}08)`, border: `1px solid ${C.purple}30` }}>
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-full flex items-center justify-center text-xl flex-shrink-0"
              style={{ background: `${C.purple}30`, border: `2px solid ${C.purple}50` }}>👤</div>
            <div>
              <p className="text-xs font-semibold mb-3" style={{ color: C.purple }}>A Note From Your AI Consultant</p>
              <p className="text-sm leading-relaxed italic" style={{ color: C.txtPri }}>"{data.consultantNote}"</p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center pt-4">
          <button onClick={() => window.print()}
            className="text-sm px-8 py-3 rounded-xl font-medium mr-3 transition-all hover:opacity-80"
            style={{ background: C.green, color: '#000' }}>Print / Save as PDF</button>
          <button onClick={onReset}
            className="text-sm px-8 py-3 rounded-xl font-medium transition-all hover:opacity-80"
            style={{ background: C.card2, border: `1px solid ${C.border}`, color: C.txtSec }}>
            Analyze Another Business
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// MAIN APP
// ─────────────────────────────────────────────

const VALIDATION = [
  s => s.step1.businessName && s.step1.industry && s.step1.businessModel && s.step1.employees && s.step1.revenueRange && s.step1.yearsInBusiness,
  s => s.step2.coreOperations.length >= 20,
  s => !!s.step3.avgTransactionValue,
  s => s.step4.goals.length > 0,
  s => !!s.step5.monthlyBudget,
  () => true,
];

export default function AIBusinessAnalyzerPro() {
  const [formState, dispatch] = useReducer(formReducer, initialFormState);
  const [step, setStep] = useState(-1); // -1 = API key entry
  const [apiKey, setApiKey] = useState('');
  const [apiKeyError, setApiKeyError] = useState('');
  const [generating, setGenerating] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [validErr, setValidErr] = useState(false);

  const totalSteps = STEP_NAMES.length;
  const pct = Math.round(((step + 1) / totalSteps) * 100);

  const canProceed = useCallback(() => {
    if (step < 0 || step >= totalSteps) return true;
    return VALIDATION[step]?.(formState) ?? true;
  }, [step, formState]);

  const handleNext = useCallback(() => {
    if (!canProceed()) { setValidErr(true); return; }
    setValidErr(false);
    if (step < totalSteps - 1) {
      setStep(p => p + 1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      handleGenerate();
    }
  }, [step, canProceed]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError('');
    try {
      const result = await generateReport(formState, apiKey);
      setReport(result);
    } catch (e) {
      setError(e.message || 'Something went wrong generating your report.');
    } finally {
      setGenerating(false);
    }
  };

  const handleReset = () => {
    setReport(null);
    setStep(0);
    setError('');
  };

  // API Key Entry Screen
  if (step === -1) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 py-12" style={{ background: C.base }}>
        <div className="w-full max-w-md">
          {/* Brand */}
          <div className="text-center mb-10">
            <div className="text-6xl mb-4">🤖</div>
            <h1 className="text-3xl font-black mb-2" style={{ color: C.txtPri }}>AI Business Analyzer Pro</h1>
            <p className="text-sm leading-relaxed" style={{ color: C.txtSec }}>
              Answer 6 steps about your business and receive a comprehensive, personalized AI transformation report
              powered by Claude — with ROI estimates, tool recommendations, and a 6-month roadmap.
            </p>
          </div>

          {/* Feature list */}
          <div className="rounded-2xl p-5 mb-6 space-y-2.5" style={card}>
            {[
              ['🎯','5 ranked AI opportunities tailored to your business'],
              ['⚡','Instant quick wins you can act on this week'],
              ['🗺️','6-month implementation roadmap with cost estimates'],
              ['💰','Financial impact projection with payback period'],
              ['📊','Radar chart scoring across 5 dimensions'],
              ['🤖','Full automation map of your manual processes'],
            ].map(([icon, text]) => (
              <div key={text} className="flex items-center gap-3">
                <span className="text-lg">{icon}</span>
                <span className="text-sm" style={{ color: C.txtSec }}>{text}</span>
              </div>
            ))}
          </div>

          {/* API Key input */}
          <div className="rounded-2xl p-6" style={card}>
            <label className="block text-sm font-semibold mb-1" style={{ color: C.txtPri }}>
              Anthropic API Key
            </label>
            <p className="text-xs mb-3" style={{ color: C.txtMut }}>
              Your key is used only for this analysis and never stored. Get one at console.anthropic.com.
            </p>
            <input
              type="password"
              value={apiKey}
              onChange={e => { setApiKey(e.target.value); setApiKeyError(''); }}
              placeholder="sk-ant-api03-..."
              className="w-full rounded-lg px-4 py-3 text-sm outline-none font-mono"
              style={{ background: C.card2, border: `1px solid ${apiKeyError ? C.red : C.border}`, color: C.txtPri }}
            />
            {apiKeyError && <p className="text-xs mt-2" style={{ color: C.red }}>{apiKeyError}</p>}

            <button
              onClick={() => {
                if (!apiKey.startsWith('sk-')) {
                  setApiKeyError('Please enter a valid Anthropic API key (starts with sk-)');
                  return;
                }
                setStep(0);
              }}
              className="w-full mt-4 py-3 rounded-xl font-semibold text-sm transition-all hover:opacity-90"
              style={{ background: C.green, color: '#000' }}>
              Start Analysis →
            </button>
          </div>

          <p className="text-center text-xs mt-4" style={{ color: C.txtMut }}>
            Takes about 5–7 minutes to complete · ~$0.05–0.10 per analysis
          </p>
        </div>
      </div>
    );
  }

  if (generating) return <LoadingScreen />;
  if (report) return <Report data={report} businessName={formState.step1.businessName} onReset={handleReset} />;

  const stepComponents = [
    <Step1 state={formState.step1} dispatch={dispatch} />,
    <Step2 state={formState.step2} dispatch={dispatch} />,
    <Step3 state={formState.step3} dispatch={dispatch} />,
    <Step4 state={formState.step4} dispatch={dispatch} />,
    <Step5 state={formState.step5} dispatch={dispatch} />,
    <Step6 state={formState.step6} dispatch={dispatch} />,
  ];

  return (
    <div className="min-h-screen" style={{ background: C.base }}>
      {/* Sticky Progress Bar */}
      <div className="sticky top-0 z-50 shadow-lg" style={{ background: C.card, borderBottom: `1px solid ${C.border}` }}>
        <div className="max-w-2xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold" style={{ color: C.green }}>
              Step {step + 1} of {totalSteps}: {STEP_NAMES[step]}
            </span>
            <span className="text-xs font-bold" style={{ color: C.txtMut }}>{pct}% complete</span>
          </div>
          {/* Step dots */}
          <div className="flex items-center gap-1.5 mb-2">
            {STEP_NAMES.map((name, i) => (
              <div key={i} className="flex-1 h-1.5 rounded-full transition-all duration-500"
                style={{
                  background: i < step ? C.green : i === step ? C.green : C.card2,
                  opacity: i <= step ? 1 : 0.4,
                }} />
            ))}
          </div>
          <div className="flex gap-1 overflow-x-auto">
            {STEP_NAMES.map((name, i) => (
              <button key={i}
                onClick={() => i < step && setStep(i)}
                disabled={i > step}
                className="text-xs px-2 py-0.5 rounded whitespace-nowrap flex-shrink-0 transition-all"
                style={{
                  color: i === step ? C.green : i < step ? C.txtSec : C.txtMut,
                  cursor: i < step ? 'pointer' : 'default',
                  background: i === step ? `${C.green}18` : 'transparent',
                }}>
                {i < step ? '✓ ' : ''}{name}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Form Content */}
      <div className="max-w-2xl mx-auto px-4 py-8">
        <div className="mb-6">
          <h2 className="text-2xl font-black mb-1" style={{ color: C.txtPri }}>
            {step === 0 && 'Tell us about your business'}
            {step === 1 && 'How does your business operate?'}
            {step === 2 && 'Your customers & revenue'}
            {step === 3 && 'Pain points & priorities'}
            {step === 4 && 'AI readiness & budget'}
            {step === 5 && 'Final details (optional but valuable)'}
          </h2>
          <p className="text-sm" style={{ color: C.txtSec }}>
            {step === 0 && 'The basics — so we can tailor everything that follows to your specific situation.'}
            {step === 1 && 'Understanding how you work is key to finding the right automation opportunities.'}
            {step === 2 && 'Revenue and customer patterns reveal where AI will have the biggest impact.'}
            {step === 3 && 'Be honest — the more specific you are, the more actionable your report will be.'}
            {step === 4 && 'We need to know your starting point and constraints before recommending solutions.'}
            {step === 5 && 'These details help Claude personalize the strategic and financial recommendations.'}
          </p>
        </div>

        {validErr && (
          <div className="mb-4 rounded-lg px-4 py-3 text-sm"
            style={{ background: `${C.red}15`, border: `1px solid ${C.red}40`, color: C.red }}>
            Please complete the required fields before continuing.
          </div>
        )}

        {stepComponents[step]}

        {/* Navigation */}
        <div className="flex justify-between items-center mt-6 pt-4" style={{ borderTop: `1px solid ${C.border}` }}>
          <button
            onClick={() => { setValidErr(false); setStep(p => Math.max(0, p - 1)); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
            disabled={step === 0}
            className="text-sm px-6 py-2.5 rounded-lg font-medium transition-all"
            style={{
              background: step === 0 ? 'transparent' : C.card2,
              border: `1px solid ${step === 0 ? 'transparent' : C.border}`,
              color: step === 0 ? C.txtMut : C.txtSec,
              cursor: step === 0 ? 'not-allowed' : 'pointer',
            }}>
            ← Previous
          </button>

          <span className="text-xs" style={{ color: C.txtMut }}>{step + 1} / {totalSteps}</span>

          <button
            onClick={handleNext}
            className="text-sm px-6 py-2.5 rounded-lg font-semibold transition-all hover:opacity-90"
            style={{ background: C.green, color: '#000' }}>
            {step === totalSteps - 1 ? '✨ Generate Report' : 'Next →'}
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-lg px-4 py-3 text-sm"
            style={{ background: `${C.red}15`, border: `1px solid ${C.red}40`, color: C.red }}>
            <strong>Error:</strong> {error}
          </div>
        )}
      </div>
    </div>
  );
}
