<script setup lang="ts">
import type { PredefinedGraphOption } from '@milaboratories/graph-maker';
import { GraphMaker } from '@milaboratories/graph-maker';
import strings from '@milaboratories/strings';
import { defaultGraphStateBoxplot, HUMANNESS_SCORE_COLUMN } from '@platforma-open/milaboratories.humanization-score.model';
import { PlBlockPage } from '@platforma-sdk/ui-vue';
import { computed } from 'vue';
import { useApp } from '../app';

const app = useApp();

// Blocks created before the charts existed carry `data` without this state.
// GraphMaker reads `initialData.optionsState` eagerly, so guarantee a non-undefined
// object here (the fallback persists on the first user change via the setter).
const graphState = computed({
  get: () => app.model.data.graphStateBoxplot ?? defaultGraphStateBoxplot(),
  set: (v) => { app.model.data.graphStateBoxplot = v; },
});

// Group humanness by sample: y = score, primary grouping = the sampleId axis
// carried by the joined-in abundance column (axesSpec[0]).
const defaultOptions = computed((): PredefinedGraphOption<'discrete'>[] | undefined => {
  const pcols = app.model.outputs.perSamplePfPcols;
  if (!pcols) return undefined;

  const scoreCol = pcols.find((p) => p.spec.name === HUMANNESS_SCORE_COLUMN);
  const abundanceCol = pcols.find(
    (p) => p.spec.annotations?.['pl7.app/isAbundance'] === 'true',
  );
  if (!scoreCol || !abundanceCol) return undefined;

  const sampleAxis = abundanceCol.spec.axesSpec[0];
  if (!sampleAxis) return undefined;

  return [
    { inputName: 'y', selectedSource: scoreCol.spec },
    { inputName: 'primaryGrouping', selectedSource: sampleAxis },
  ];
});
</script>

<template>
  <PlBlockPage>
    <GraphMaker
      v-model="graphState"
      chartType="discrete"
      :data-state-key="app.model.outputs.perSamplePf"
      :p-frame="app.model.outputs.perSamplePf"
      :default-options="defaultOptions"
      :status-text="{ noPframe: { title: strings.callToActions.configureSettingsAndRun } }"
    />
  </PlBlockPage>
</template>
