<script setup lang="ts">
import type { PredefinedGraphOption } from '@milaboratories/graph-maker';
import { GraphMaker } from '@milaboratories/graph-maker';
import strings from '@milaboratories/strings';
import { defaultGraphStateHistogram, HUMANNESS_SCORE_COLUMN } from '@platforma-open/milaboratories.humanization-score.model';
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
// straight away; the user can still re-bind it in the graph-maker UI.
const defaultOptions = computed((): PredefinedGraphOption<'histogram'>[] | undefined => {
  const pcols = app.model.outputs.histogramPfPcols;
  if (!pcols) return undefined;

  const scoreCol = pcols.find((p) => p.spec.name === HUMANNESS_SCORE_COLUMN);
  if (!scoreCol) return undefined;

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
