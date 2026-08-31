import {
  defaultGraphStateHistogram,
  platforma,
} from "@platforma-open/milaboratories.humanness-score.model";
import { defineAppV3 } from "@platforma-sdk/ui-vue";
import HistogramPage from "./pages/HistogramPage.vue";
import MainPage from "./pages/MainPage.vue";
import { syncCoverageWargings } from "./syncCoverageWargings.ts";

export const sdkPlugin = defineAppV3(platforma, (app) => {
  app.model.data.customBlockLabel ??= "";
  app.model.data.graphStateHistogram ??= defaultGraphStateHistogram();
  syncCoverageWargings(app.model);

  return {
    routes: {
      "/": () => MainPage,
      "/histogram": () => HistogramPage,
    },
  };
});

export const useApp = sdkPlugin.useApp;
