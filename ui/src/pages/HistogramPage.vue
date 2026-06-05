<script setup lang="ts">
import type { PredefinedGraphOption } from '@milaboratories/graph-maker';
import { GraphMaker } from '@milaboratories/graph-maker';
import strings from '@milaboratories/strings';
import { CHAIN_DOMAIN, CHAIN_HEAVY, defaultGraphStateHistogram, HUMANNESS_SCORE_COLUMN } from '@platforma-open/milaboratories.humanness-score.model';
import { PlBlockPage } from '@platforma-sdk/ui-vue';
import { computed } from 'vue';
import { useApp } from '../app';

const app = useApp();

// Blocks created before the charts existed carry `data` without this state.
// GraphMaker reads `initialData.optionsState` eagerly, so guarantee a non-undefined
// object here (the fallback persists on the first user change via the setter).
const graphState = computed({
  get: () => app.model.data.graphStateHistogram ?? defaultGraphStateHistogram(),
  set: (v) => { app.model.data.graphStateHistogram = v; },
});

// Pre-select the humanness score as the histogram value so the chart renders
// straight away; the user can still re-bind it (e.g. switch Heavy -> Light) in
// the graph-maker UI.
//
// Single-cell now emits multiple score columns sharing `HUMANNESS_SCORE_COLUMN`,
// distinguished by the `CHAIN_DOMAIN` chain-type domain. Default the histogram
// to the Heavy chain ('A'); fall back to the first name match (covers bulk,
// which has a single column with no chain domain).
const defaultOptions = computed((): PredefinedGraphOption<'histogram'>[] | undefined => {
  const pcols = app.model.outputs.histogramPfPcols;
  if (!pcols) return undefined;

  const scoreCols = pcols.filter((p) => p.spec.name === HUMANNESS_SCORE_COLUMN);
  if (scoreCols.length === 0) return undefined;

  const scoreCol
    = scoreCols.find((p) => p.spec.domain?.[CHAIN_DOMAIN] === CHAIN_HEAVY)
      ?? scoreCols[0];

  return [{ inputName: 'value', selectedSource: scoreCol.spec }];
});
</script>

<template>
  <PlBlockPage>
    <GraphMaker
      v-model="graphState"
      chartType="histogram"
      :data-state-key="app.model.outputs.histogramPf"
      :p-frame="app.model.outputs.histogramPf"
      :default-options="defaultOptions"
      :status-text="{ noPframe: { title: strings.callToActions.configureSettingsAndRun } }"
    />
  </PlBlockPage>
</template>
