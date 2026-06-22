// Framework-region coverage detection.
//
// The humanness scorer needs a variable region covering at least 3 of the 4
// framework regions (FR1..FR4). This module decides, from the per-chain
// amino-acid sequence columns available in the result pool, whether a dataset
// clears that bar — so the run can be blocked up front for under-covered
// inputs (e.g. clonotypes assembled by a short feature such as CDR1:CDR3).
//
// Why not just count which FR columns exist? The upstream producer exports a
// per-region column for EVERY standard region (FR1..FR4, CDR1..CDR3)
// regardless of how clonotypes were actually assembled — the columns outside
// the assembling feature simply hold no data. So column presence is identical
// for a full VDJRegion dataset and a CDR1:CDR3 one and tells us nothing. The
// honest signal is the assembling feature itself: the widest contiguous span
// present per chain (e.g. "VDJRegionInFrame" for full, "{CDR1Begin:CDR3End}"
// for CDR1:CDR3). We count only the framework regions fully inside that span.

export const FEATURE_DOMAIN = 'pl7.app/vdj/feature';
export const MIN_FRAMEWORK_REGIONS = 3;

// Linear coordinates of the V-region reference points, in order. Each region
// spans [Begin, End]; the End of one region is the Begin of the next, so a
// single shared axis of positions is enough.
//   FR1 CDR1 FR2 CDR2 FR3 CDR3 FR4
//   0   1    2   3    4   5    6   7
const REF_POINT_POS: Record<string, number> = {
  FR1Begin: 0,
  CDR1Begin: 1, FR1End: 1,
  FR2Begin: 2, CDR1End: 2,
  CDR2Begin: 3, FR2End: 3,
  FR3Begin: 4, CDR2End: 4,
  CDR3Begin: 5, FR3End: 5,
  FR4Begin: 6, CDR3End: 6,
  FR4End: 7,
};

// [Begin, End] position of each framework region. A framework counts as covered
// only when it is fully contained in the assembled feature's span.
const FRAMEWORK_SPANS: [number, number][] = [
  [0, 1], // FR1
  [2, 3], // FR2
  [4, 5], // FR3
  [6, 7], // FR4
];

// [Begin, End] position of each single named region we may see as a feature.
const SINGLE_REGION_SPANS: Record<string, [number, number]> = {
  FR1: [0, 1], CDR1: [1, 2], FR2: [2, 3], CDR2: [3, 4],
  FR3: [4, 5], CDR3: [5, 6], FR4: [6, 7], FR4InFrame: [6, 7],
};

// Resolve the [Begin, End] span of a sequence feature, or undefined if it
// doesn't describe a contiguous V-region range we understand.
//   - VDJRegion / VDJRegionInFrame -> the full V region (all 4 frameworks).
//   - single named regions (FR1..FR4, FR4InFrame, CDR1..CDR3).
//   - composite ranges emitted by the producer, e.g. "{CDR1Begin:CDR3End}".
const featureSpan = (feature: string): [number, number] | undefined => {
  if (feature === 'VDJRegion' || feature === 'VDJRegionInFrame') return [0, 7];
  const single = SINGLE_REGION_SPANS[feature];
  if (single) return single;
  const m = /^\{(\w+):(\w+)\}$/.exec(feature);
  if (m) {
    const start = REF_POINT_POS[m[1]];
    const end = REF_POINT_POS[m[2]];
    if (start !== undefined && end !== undefined && start < end) return [start, end];
  }
  return undefined;
};

const insufficientFrameworksMessage = (chainLabel: string | undefined, n: number): string => {
  const where = chainLabel ? ` (${chainLabel} chain)` : '';
  return `Humanness scoring needs a variable region covering at least ${MIN_FRAMEWORK_REGIONS} `
    + `of the 4 framework regions, but this dataset's variable region${where} covers only ${n}. `
    + `This usually means clonotypes were assembled by a short feature such as CDR1:CDR3 `
    + `(FR2+FR3 only); the score cannot be computed. Re-run clonotyping with full (VDJRegion) `
    + `or partial (>=${MIN_FRAMEWORK_REGIONS} framework) variable-region assembly.`;
};

// Minimal shape of a matched amino-acid sequence column needed for detection.
export interface CoverageColumn {
  spec: { domain?: Record<string, string> };
}

/**
 * Returns one warning per chain whose assembled variable region covers fewer
 * than `MIN_FRAMEWORK_REGIONS` framework regions. Empty when every chain clears
 * the bar (or when there are no understandable feature columns).
 *
 * @param cols       amino-acid `pl7.app/vdj/sequence` columns for the dataset
 * @param chainDomain domain key carrying the chain type (e.g. CHAIN_DOMAIN)
 * @param chainLabels map of chain-type value -> human label (e.g. {A:'Heavy'})
 */
export function computeCoverageWarnings(
  cols: readonly CoverageColumn[],
  chainDomain: string,
  chainLabels: Record<string, string>,
): string[] {
  // The widest contiguous feature span present per chain is the assembling
  // feature; everything narrower is a sub-region of it (or empty noise).
  const widestSpanByChain = new Map<string | undefined, [number, number]>();
  for (const col of cols) {
    const domain = col.spec.domain ?? {};
    const index = domain[`${chainDomain}/index`];
    if (index !== undefined && index !== 'primary') continue;
    const feature = domain[FEATURE_DOMAIN];
    if (!feature) continue;
    const span = featureSpan(feature);
    if (!span) continue;
    const chain = domain[chainDomain];
    const current = widestSpanByChain.get(chain);
    if (!current || span[1] - span[0] > current[1] - current[0]) {
      widestSpanByChain.set(chain, span);
    }
  }

  const warnings: string[] = [];
  for (const [chain, [start, end]] of widestSpanByChain) {
    const frameworks = FRAMEWORK_SPANS.filter(([b, e]) => b >= start && e <= end).length;
    if (frameworks < MIN_FRAMEWORK_REGIONS) {
      warnings.push(insufficientFrameworksMessage(chain ? chainLabels[chain] : undefined, frameworks));
    }
  }
  return warnings;
}
