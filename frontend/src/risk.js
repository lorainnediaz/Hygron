// Plain-language meanings shown next to the risk counts. Wording follows the model's
// own category descriptions in inference.py; it must not imply that mold is detected.
export const riskMeanings = {
  High: 'Higher modeled mold-growth risk. Inspect the room first.',
  Medium: 'Moderate modeled mold-growth risk. Monitor and plan a follow-up check.',
  Low: 'Lower modeled mold-growth risk. Continue normal monitoring.',
  Unavailable: 'No estimate could be made. Do not treat this as Low; check the reason for the room.',
}
