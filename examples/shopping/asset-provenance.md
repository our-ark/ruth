# Image asset provenance

Reused without image editing from the earlier Bob concept video. Both stores use
these fictional product photographs; alternate mock catalog entries reuse their
store image. The complete assets needed to run are checked into this repository.

Mode: built-in `image_gen`, followed by edits with the same built-in tool. No CLI fallback was used.

Final project assets:
- `dayform/shoe.png`
- `stride/shoe.png`

The initial generation requested transparency, but the returned images contained a checkerboard background. The final edits replaced it with opaque studio backgrounds. Both product designs and stores are fictional.

## Initial generation prompts

### DAYFORM

Use case: product-mockup. Asset: fictional sneaker product photograph for a shopping interface in a concept demo video. One single unbranded premium everyday low-top sneaker, matte charcoal-black suede and fine knit upper, clean off-white cushioned rubber sole, black laces, roomy rounded toe, understated office-friendly design. Entire shoe in a three-quarter side profile, toe facing left, heel right, centered with generous padding. Photorealistic premium e-commerce studio photography, detailed natural materials, soft light. Genuinely transparent background with preserved alpha, subtle contact shadow only. Landscape image. No text, no logo, no watermark, no extra shoes or objects.

### STRIDE

Use case: product-mockup. Asset: second fictional sneaker product photograph for a contrasting editorial shopping interface in a concept demo video. One single unbranded sleek low-top urban sneaker, cool light-gray technical mesh upper with dark graphite sculpted overlays, off-white slim sole, gray laces, narrow streamlined silhouette. Entire shoe in a three-quarter side profile, toe facing left, heel right, centered with generous padding. Photorealistic premium e-commerce studio photography, detailed materials, soft neutral light. Genuinely transparent background with preserved alpha, subtle contact shadow only. Landscape image. No text, no logo, no watermark, no extra shoes or objects.

## Final edit prompts

### dayform

Use case: precise-object-edit. Edit this product photograph for a fictional shopping demo. Preserve the exact sneaker design, materials, color, orientation and realistic detail. Replace the entire checkerboard background with one seamless opaque solid studio background in color #e8e8dc, with a subtle natural contact shadow. Remove every checkerboard square. Do not use transparency or draw a transparency pattern. Keep the complete sneaker visible, centered in a wide landscape 16:9 composition, shoe filling about 82% of the width. No text or logos.

### stride

Use case: precise-object-edit. Edit this product photograph for a fictional shopping demo. Preserve the exact sneaker design, materials, color, orientation and realistic detail. Replace the entire checkerboard background with one seamless opaque solid studio background in color #9baba1, with a subtle natural contact shadow. Remove every checkerboard square. Do not use transparency or draw a transparency pattern. Keep the complete sneaker visible, centered in a wide landscape 16:9 composition, shoe filling about 82% of the width. No text or logos.
