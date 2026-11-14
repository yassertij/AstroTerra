import type { AnalysisResult } from "../lib/api";

// SYNTHETIC result used by component tests (values mirror a real run, labelled synthetic).
export const RESULT: AnalysisResult = {
  disclaimer: "SYNTHETIC DEMO DATA - not a real finding. Topographic analog assessment only.",
  is_synthetic: true, software_version: "0.1.0",
  target: { body: "MARS", patch_km: 40 },
  target_metrics: { slope: { median: 5 }, flags: [] },
  target_record: {
    product_id: "MEGT00N090HB.IMG", data_set_id: "MGS-M-MOLA-5-MEGDR-L3-V1.0", product_version: "2.0", doi: "10.17189/1519460",
    mission: "MGS", instrument: "MOLA", archive: "PDS", body: "MARS", projection: "SIMPLE CYLINDRICAL", horizontal_reference: "x",
    vertical_reference: "Areoid", units: "metre", fill_value: "none", citation: "Smith et al.", quality_flags: ["observation_counts_not_loaded"],
    processing_history: [{ operation: "crop", parameters: {}, note: "No resampling.", timestamp: "" }],
  },
  earth_records: {},
  settings: {},
  coverage: { selection_method: "Tiles listed explicitly.", tiles_requested: ["N38W111"], tiles_examined: ["N38W111"], tiles_failed: {}, tiles_unavailable: {}, tiles_outside_coverage: ["N75W090"], note: "Not global coverage." },
  ranking: {
    score_meaning: "Distance in robust (MAD) units; lower = more similar. Not a probability.",
    features_used: ["relief_20km_m", "slope_median_deg"], features_dropped: {}, weights: {}, exclusion_rules: {},
    target_features: { relief_20km_m: 3375, slope_median_deg: 5.5 },
    flags: [],
    results: [
      { candidate_id: "N38W111_r154_c88", tile: "N38W111", rank: 1, distance: 8.12,
        feature_differences: { relief_20km_m: 2607.7, slope_median_deg: 0.6 }, normalized_differences: {},
        contributions: { relief_20km_m: 0.66, slope_median_deg: 0.34 }, valid_fraction: 1, fill_fraction: 0.033,
        native_spacing_m: 27, analysis_spacing_m: 462, excluded: false, exclusion_reasons: [],
        sensitivity: { weight_perturbation_rank_median: 1, rank_p05: 1, rank_p95: 2, top1_fraction: 0.9, fill_excluded_rank: 2 }, flags: [] },
      { candidate_id: "N38W111_r0_c0", tile: "N38W111", rank: null, distance: null, feature_differences: {}, normalized_differences: {},
        contributions: {}, valid_fraction: 1, fill_fraction: 0.2, native_spacing_m: 27, analysis_spacing_m: 462, excluded: true,
        exclusion_reasons: ["non-SRTM fill fraction 0.200 > 0.05"], sensitivity: {}, flags: [] },
    ],
  },
  limitations: ["The distance is not a probability and the method is not empirically validated."],
};
