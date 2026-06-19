/**
 * Returns the path to a crop image.
 *
 * Each crop has 5 variants: {crop}_1.jpg … {crop}_5.jpg
 *
 * - When a seed (e.g. declarationId) is supplied the same listing always
 *   shows the same image but different listings show different ones.
 * - Without a seed the crop name itself is hashed so the homepage grid is
 *   stable across page loads.
 */

const VARIANTS = 5

function stableHash(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = Math.imul(31, h) + s.charCodeAt(i)
    h |= 0
  }
  return Math.abs(h)
}

export function cropImageSrc(crop: string | null | undefined, seed?: number): string {
  const base   = (crop ?? 'maize').toLowerCase().trim()
  const hash   = seed !== undefined ? seed : stableHash(base)
  const idx    = (hash % VARIANTS) + 1
  return `/crops/${base}_${idx}.jpg`
}
