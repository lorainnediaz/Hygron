import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// WCAG 2.x contrast. Text needs 4.5:1 (AA, normal size); focus rings, chart lines and
// other non-text indicators need 3:1 (SC 1.4.11).
const css = readFileSync(resolve(process.cwd(), 'src/App.css'), 'utf8')
const root = css.match(/:root\s*{([^}]*)}/)[1]
const tokens = Object.fromEntries(
  [...root.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)].map(([, name, value]) => [name, value]),
)

function channels(hex) {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
}

function luminance(hex) {
  const [r, g, b] = channels(hex).map((value) => {
    const c = value / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a, b) {
  const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (high + 0.05) / (low + 0.05)
}

function blend(fg, bg, alpha) {
  const f = channels(fg)
  const b = channels(bg)
  return `#${f.map((value, i) => Math.round(alpha * value + (1 - alpha) * b[i]).toString(16).padStart(2, '0')).join('')}`
}

const t = (name) => {
  if (!tokens[name]) throw new Error(`Missing CSS token --${name}`)
  return tokens[name]
}

const backgrounds = {
  surface: t('surface'),
  canvas: t('canvas'),
  raised: t('surface-raised'),
  hover: t('surface-hover'),
  'alert card': '#fbf3f1',
}

const textTokens = ['text', 'text-soft', 'muted', 'accent-bright', 'coral', 'amber', 'green', 'unavailable']
const riskTokens = ['coral', 'amber', 'green', 'unavailable']

describe('risk pill badges (color-mix 12% over white)', () => {
  for (const name of riskTokens) {
    it(`--${name} text on its own pill is at least 4.5:1`, () => {
      expect(contrast(t(name), blend(t(name), '#ffffff', 0.12))).toBeGreaterThanOrEqual(4.5)
    })
  }
  it('white text on every priority tile color is at least 4.5:1', () => {
    for (const name of riskTokens) expect(contrast('#ffffff', t(name))).toBeGreaterThanOrEqual(4.5)
  })
})

describe('color contrast (WCAG AA)', () => {
  for (const name of textTokens) {
    for (const [bgName, bg] of Object.entries(backgrounds)) {
      it(`--${name} text on ${bgName} is at least 4.5:1`, () => {
        expect(contrast(t(name), bg)).toBeGreaterThanOrEqual(4.5)
      })
    }
  }

  it.each([
    ['white on refresh button', '#ffffff', t('action')],
    ['white on refresh button hover', '#ffffff', t('action-deep')],
    ['white on methodology link', '#ffffff', t('accent')],
    ['alert "needs action" pill', '#74352f', blend('#b84d45', backgrounds['alert card'], 0.1)],
    ['alert "acknowledged" pill', '#2f6d55', blend('#3e8067', t('surface'), 0.1)],
    ['priority eyebrow text (non-High)', t('coral'), t('surface')],
    ['white text on red banner (light end)', '#ffffff', '#d92d45'],
    ['white text on red banner (dark end)', '#ffffff', '#b21d35'],
    ['red text on white banner button', '#b21d35', '#ffffff'],
    ['red text on banner button hover', '#b21d35', '#fff4f0'],
    ['red text on yellow room tile', '#b21d35', '#ffe066'],
    ['priority readings text', t('text-soft'), t('surface')],
    ['white on priority tile', '#ffffff', t('coral')],
    ['80% RH chart label', '#8a5a12', blend('#a8423a', t('surface'), 0.06)],
    ['humidity bar caption', t('text-soft'), t('surface')],
  ])('%s is at least 4.5:1', (_, fg, bg) => {
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(4.5)
  })

  it.each([
    ['focus ring on canvas', t('focus'), t('canvas')],
    ['focus ring on surface', t('focus'), t('surface')],
    ['humidity line', '#4f8a7b', t('surface')],
    ['temperature line', t('temp-line'), t('surface')],
    ['80% RH reference line', '#b77929', t('surface')],
    ['humidity bar fill on its track', t('accent'), t('surface-hover')],
    ['humidity bar 80% marker', t('text'), t('surface-hover')],
    ['yellow warning icon on red banner', '#ffe066', '#d92d45'],
    ['white button against red banner', '#ffffff', '#d92d45'],
    ['risk bar Medium segment', '#a06a1c', t('canvas')],
  ])('%s is at least 3:1', (_, fg, bg) => {
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(3)
  })
})
