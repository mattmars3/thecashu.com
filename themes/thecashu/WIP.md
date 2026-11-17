# Work in Progress

Developer notes for lower-priority image improvements.

## Image sizing and delivery

- Separate image placement from rendered size in the shortcode. Keep
  `position` for `left`, `right`, and `center`, and introduce a distinct `size`
  option.
- Consider consistent `small`, `medium`, `large`, and `natural` size presets.
  Reserve full-width rendering for an explicit choice rather than the default.
- Avoid enlarging images beyond their intrinsic dimensions, particularly for
  small source assets.
- Consider capping unusually tall images relative to the viewport, such as
  `max-height: 65svh`, while preserving their complete aspect ratio with
  `object-fit: contain`.
- Keep original images as the canonical page-bundle assets while generating
  static responsive derivatives during the Zola build with `resize_image`.
- Add `srcset` and position-aware `sizes` values so mobile browsers can select
  an appropriately sized derivative instead of downloading every original.
- Use `get_image_metadata` to emit intrinsic `width` and `height` attributes
  and reserve layout space before an image loads.
- Optionally link a displayed derivative to its untouched original.
