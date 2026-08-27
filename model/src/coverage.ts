// Framework-region coverage detection.
//
// The humanness scorer needs a variable region covering at least 3 of the 4
// framework regions (FR1..FR4). This module decides, from the per-chain
// amino-acid sequence columns available in the result pool, whether a dataset
// clears that bar — so the run can be blocked up front for under-covered
// inputs (e.g. clonotypes assembled by a short feature such as CDR1:CDR3).
export const FEATURE_DOMAIN = 'pl7.app/vdj/feature';

// synthetic-repertoire-profiler keys the region on `pl7.app/feature` instead, on
// columns named `pl7.app/sequence`. The region NAMES are the same (FR1..FR4,
// CDR1..CDR3), so the spans below apply unchanged; only the domain key differs.
// A column carries one key or the other, never both.
export const PROFILER_FEATURE_DOMAIN = 'pl7.app/feature';

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

// The seven canonical regions in N->C order, each spanning [i, i+1]. This is the
// same template `software/src/main.py:_CANONICAL_REGIONS` walks, and the order the
// scorer concatenates in.
const CANONICAL_REGIONS = ['FR1', 'CDR1', 'FR2', 'CDR2', 'FR3', 'CDR3', 'FR4'] as const;

// Which of those seven count toward the coverage gate (mirrors `_FR_REGIONS`).
const FRAMEWORK_REGIONS: ReadonlySet<string> = new Set(['FR1', 'FR2', 'FR3', 'FR4']);

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
// The profiler's whole-variant feature ("amplicon-sequence") names no range, so
// it lands here as undefined and is skipped. That is deliberate: its span depends
// on the run's region scheme, which the feature key does not state, and the
// per-region columns of the same run do state their spans.
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
 * Number of framework regions in the longest gap-free run of covered regions.
 *
 * `covered[i]` says whether canonical region `i` is covered by at least one of the
 * chain's columns. A run must be gap-free because the scorer never bridges a hole:
 * gluing FR2 straight onto FR4 would fabricate a junction 9-mer that occurs in no
 * real antibody (`software/src/main.py:assemble_and_score`).
 */
const frameworksInLongestRun = (covered: readonly boolean[]): number => {
  let best = 0;
  let runFrameworks = 0;
  for (let i = 0; i < CANONICAL_REGIONS.length; i++) {
    if (!covered[i]) {
      runFrameworks = 0;
      continue;
    }
    if (FRAMEWORK_REGIONS.has(CANONICAL_REGIONS[i])) runFrameworks++;
    if (runFrameworks > best) best = runFrameworks;
  }
  return best;
};

/**
 * Returns one warning per chain whose assembled variable region covers fewer
 * than `MIN_FRAMEWORK_REGIONS` framework regions. Empty when every chain clears
 * the bar (or when there are no understandable feature columns).
 *
 * Coverage is the UNION of what the chain's columns span, not the span of the
 * widest one. Both dataset shapes have to work:
 *
 *  - MiXCR and Import VDJ Data emit an assembling-feature column whose name states
 *    the whole span (`VDJRegion`, or a composite like `{CDR1Begin:CDR3End}`), with
 *    the per-region columns as sub-regions of it. The union is that span.
 *  - synthetic-repertoire-profiler emits SEVEN single-region columns and no
 *    assembling column with a span in its name. Reading the widest one would see a
 *    single region and refuse a complete V domain — which is exactly what happened
 *    before this was a union.
 *
 * @param cols       amino-acid sequence columns for the dataset (both naming
 *                   worlds: `pl7.app/vdj/sequence` and `pl7.app/sequence`)
 * @param chainDomain domain key carrying the chain type (e.g. CHAIN_DOMAIN)
 * @param chainLabels map of chain-type value -> human label (e.g. {A:'Heavy'})
 */
export function computeCoverageWarnings(
  cols: readonly CoverageColumn[],
  chainDomain: string,
  chainLabels: Record<string, string>,
): string[] {
  const coveredByChain = new Map<string | undefined, boolean[]>();
  for (const col of cols) {
    const domain = col.spec.domain ?? {};
    const index = domain[`${chainDomain}/index`];
    if (index !== undefined && index !== 'primary') continue;
    const feature = domain[FEATURE_DOMAIN] ?? domain[PROFILER_FEATURE_DOMAIN];
    if (!feature) continue;
    const span = featureSpan(feature);
    if (!span) continue;
    const chain = domain[chainDomain];
    let covered = coveredByChain.get(chain);
    if (!covered) {
      covered = CANONICAL_REGIONS.map(() => false);
      coveredByChain.set(chain, covered);
    }
    // Region i occupies [i, i+1], so this column covers it when the region sits
    // wholly inside the column's span.
    for (let i = 0; i < CANONICAL_REGIONS.length; i++) {
      if (span[0] <= i && i + 1 <= span[1]) covered[i] = true;
    }
  }

  const warnings: string[] = [];
  for (const [chain, covered] of coveredByChain) {
    const frameworks = frameworksInLongestRun(covered);
    if (frameworks < MIN_FRAMEWORK_REGIONS) {
      warnings.push(insufficientFrameworksMessage(chain ? chainLabels[chain] : undefined, frameworks));
    }
  }
  return warnings;
}
