// Salary parsing + entry-level enforcement.

// Parse a free-text compensation string into a normalized ANNUAL midpoint
// (CAD/USD/etc. not converted — used only for relative wage sorting).
// Handles "$165,000 - $195,000 a year", "$15 - $17 an hour", "$90,000 a year".
export function parseSalary(comp) {
  if (!comp) return null;
  const hourly = /hour|hr|\/h/i.test(comp);
  const nums = (comp.match(/\d[\d,]*(?:\.\d+)?/g) || [])
    .map((n) => parseFloat(n.replace(/,/g, '')))
    .filter((n) => !Number.isNaN(n) && n > 0);
  if (!nums.length) return null;
  const lo = nums[0];
  const hi = nums.length > 1 ? nums[1] : nums[0];
  let mid = (lo + hi) / 2;
  if (hourly) mid *= 2080; // 40h/week * 52 weeks
  return { min: hourly ? lo * 2080 : lo, max: hourly ? hi * 2080 : hi, mid, hourly };
}

// Senior / non-entry markers. Roman numerals II/III and "5+ years" included.
const SENIOR = /\b(senior|sr\.?|vp|vice president|director|head|principal|lead|chief|manager|mgr|executive|partner|associate director|ii|iii|iv)\b|\b\d+\+?\s*years\b/i;

// Entry-level if it lacks senior markers OR explicitly signals entry.
export function isEntryLevel(title = '') {
  const t = title.toLowerCase();
  if (/\b(junior|jr\.?|graduate|grad|intern|internship|entry[- ]level|trainee|new analyst|summer analyst|assistant)\b/.test(t)) {
    return true;
  }
  return !SENIOR.test(t);
}

// Christian's rule: finance & real estate MUST be entry-level; golf any level.
export function passesLevelRule(job) {
  if (job.sector === 'finance' || job.sector === 'real_estate') {
    return isEntryLevel(job.title);
  }
  return true;
}
