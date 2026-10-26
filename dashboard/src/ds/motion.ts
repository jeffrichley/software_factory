/** Motion tokens for Framer Motion; same values as the CSS variables in tokens.css. */
export const motion = {
  dur: 0.2,
  glide: 0.4,
  easeOut: [0.2, 0.7, 0.2, 1],
  easeIn: [0.5, 0, 0.8, 0.3],
} as const;

/** How a State chip glides to its new flow-strip column when its Phase changes. */
export const glide = { layout: { duration: motion.glide, ease: motion.easeOut } } as const;
