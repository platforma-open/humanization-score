import {
  defaultGraphStateBoxplot,
  defaultGraphStateHistogram,
  platforma,
} from '@platforma-open/milaboratories.humanization-score.model';
import { defineAppV3 } from '@platforma-sdk/ui-vue';
import HistogramPage from './pages/HistogramPage.vue';
import MainPage from './pages/MainPage.vue';
import SampleBoxPlotPage from './pages/SampleBoxPlotPage.vue';

export const sdkPlugin = defineAppV3(platforma, (app) => {
  app.model.data.customBlockLabel ??= '';
  // Blocks created before the charts existed carry `data` without these graph
  // states; GraphMaker's v-model can't be undefined, so backfill the defaults.
  app.model.data.graphStateHistogram ??= defaultGraphStateHistogram();
  app.model.data.graphStateBoxplot ??= defaultGraphStateBoxplot();

  return {
    routes: {
      '/': () => MainPage,
      '/histogram': () => HistogramPage,
      '/by-sample': () => SampleBoxPlotPage,
    },
  };
});

export const useApp = sdkPlugin.useApp;
