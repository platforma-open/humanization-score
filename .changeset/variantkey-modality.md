---
'@platforma-open/milaboratories.humanness-score.workflow': minor
'@platforma-open/milaboratories.humanness-score.model': minor
'@platforma-open/milaboratories.humanness-score': minor
---

Accept bare imported antibody sets keyed on pl7.app/variantKey

Import VDJ Data's bare receptor sets key a record on `pl7.app/variantKey`, an axis peptide-extraction
and synthetic-repertoire-profiler also key on. The axis name therefore identifies no producer — the
run-id in its domain does (`pl7.app/vdj/clonotypingRunId` for a receptor set) — and this block read
neither: such a set was not offered in the dataset dropdown at all, so an imported antibody panel
could not be scored.

The dropdown now offers a `pl7.app/variantKey` dataset whose axis carries
`pl7.app/vdj/receptor: IG`, which only the VDJ producer stamps on that axis; peptide and amplicon
sets are still not offered, and a TCR set stamps TCRAB/TCRGD and is not offered either. The workflow
re-checks the run-id key and refuses an unrecognised producer by name instead of falling through to
the nearest branch.

Whether the two chains are scored separately now follows the `pl7.app/vdj/scClonotypeChain` COLUMN
domain rather than the key axis being `pl7.app/vdj/scClonotypeKey`. A paired bare set carries both
chains in one frame under that domain, so reading it off the axis name sent it down the bulk path,
where one chain is picked and the other silently dropped — and the result still looks complete. A
single-chain bare set carries no chain domain and stays bulk-shaped, which is what its producer
intends.

Bulk, single-cell and VHH inputs take exactly the paths they took before: the Ig/TCR guard reads the
receptor from the key axis where the axis states it and the chain where it does not, which is the
same decision it made when it read the axis name.
