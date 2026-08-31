import { computed, watch } from "vue";

export function syncCoverageWargings(model: {
  outputs: { coverageWarnings?: null | string[] };
  data: { coverageWarnings?: null | string[] };
}) {
  // Spread (`...`) is load-bearing: the SDK patches output arrays IN PLACE, so
  // `app.model.outputs.coverageWarnings` keeps the same array reference and a
  // plain getter never looks "changed". Spreading reads each element, so this
  // computed subscribes element-wise (fires on in-place mutation) AND returns a
  // fresh array reference every recompute.
  const coverageWarnings = computed(() =>
    model.outputs.coverageWarnings == null ? null : [...model.outputs.coverageWarnings],
  );
  watch(
    coverageWarnings,
    (warns) => {
      model.data.coverageWarnings = warns == null ? undefined : warns;
    },
    { immediate: true },
  );
}
