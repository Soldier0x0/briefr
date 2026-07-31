/**
 * Record an authenticated BRIEFR UI walkthrough for the Instagram Reel.
 * Requires backend :8000, frontend :5173, and seeded data.
 *
 * Usage:
 *   SCREENSHOT_USERNAME=admin SCREENSHOT_PASSWORD='…' \
 *     node scripts/capture_reel_walkthrough.mjs
 */
import { createRequire } from 'module';
import { mkdir, rename } from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(__dirname, '../frontend/package.json'));
const { chromium } = require('playwright');

const baseUrl = process.env.SCREENSHOT_BASE_URL || 'http://127.0.0.1:5173';
const apiUrl = 'http://127.0.0.1:8000';
const outDir = path.join(__dirname, '..', 'briefer-reel', 'assets', 'capture');
const VIEWPORT = { width: 1440, height: 900 };

const screenshotUser = process.env.SCREENSHOT_USERNAME || 'admin';
const screenshotPassword = process.env.SCREENSHOT_PASSWORD || 'ReelDemo2026!';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function parseSetCookieHeaders(headers) {
  const raw = typeof headers.getSetCookie === 'function'
    ? headers.getSetCookie()
    : [headers.get('set-cookie')].filter(Boolean);
  return raw.flatMap((line) => {
    const parts = line.split(';').map((p) => p.trim());
    const [nameValue, ...attrs] = parts;
    const eq = nameValue.indexOf('=');
    if (eq <= 0) return [];
    const name = nameValue.slice(0, eq);
    const value = nameValue.slice(eq + 1);
    const cookie = {
      name,
      value,
      domain: new URL(baseUrl).hostname,
      path: '/',
      httpOnly: false,
      secure: false,
      sameSite: 'Strict',
    };
    for (const attr of attrs) {
      const lower = attr.toLowerCase();
      if (lower === 'httponly') cookie.httpOnly = true;
      else if (lower.startsWith('path=')) cookie.path = attr.slice(5);
      else if (lower.startsWith('samesite=')) {
        const rawSite = attr.slice(9).toLowerCase();
        cookie.sameSite = rawSite === 'none' ? 'None' : rawSite === 'lax' ? 'Lax' : 'Strict';
      }
    }
    return [cookie];
  });
}

async function loginSession() {
  const res = await fetch(`${apiUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: screenshotUser,
      password: screenshotPassword,
      remember_me: true,
    }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Login failed (${res.status}): ${detail}`);
  }
  const cookies = parseSetCookieHeaders(res.headers);
  if (!cookies.some((c) => c.name === 'briefr_at')) {
    throw new Error('Login succeeded but briefr_at cookie missing');
  }
  return { cookies };
}

const CURSOR_INIT = () => {
  if (document.getElementById('reel-cursor')) return;
  const style = document.createElement('style');
  style.textContent = `
    #reel-cursor {
      position: fixed;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: rgba(232, 85, 51, 0.95);
      border: 2px solid #fff;
      box-shadow: 0 0 0 1px rgba(0,0,0,0.35), 0 4px 16px rgba(232,85,51,0.45);
      z-index: 2147483646;
      pointer-events: none;
      transform: translate(-50%, -50%);
      transition: left 0.55s cubic-bezier(0.22, 1, 0.36, 1),
                  top 0.55s cubic-bezier(0.22, 1, 0.36, 1);
      left: 720px;
      top: 450px;
    }
    #reel-cursor.click {
      animation: reel-click 0.35s ease;
    }
    @keyframes reel-click {
      0% { transform: translate(-50%, -50%) scale(1); }
      50% { transform: translate(-50%, -50%) scale(0.72); }
      100% { transform: translate(-50%, -50%) scale(1); }
    }
  `;
  document.head.appendChild(style);
  const cursor = document.createElement('div');
  cursor.id = 'reel-cursor';
  document.body.appendChild(cursor);

  window.__reelMoveCursor = (x, y, instant = false) => {
    const el = document.getElementById('reel-cursor');
    if (!el) return;
    if (instant) el.style.transition = 'none';
    else el.style.transition = 'left 0.55s cubic-bezier(0.22, 1, 0.36, 1), top 0.55s cubic-bezier(0.22, 1, 0.36, 1)';
    el.style.left = `${x}px`;
    el.style.top = `${y}px`;
    if (instant) {
      requestAnimationFrame(() => {
        el.style.transition = 'left 0.55s cubic-bezier(0.22, 1, 0.36, 1), top 0.55s cubic-bezier(0.22, 1, 0.36, 1)';
      });
    }
  };

  window.__reelClick = () => {
    const el = document.getElementById('reel-cursor');
    if (!el) return;
    el.classList.remove('click');
    void el.offsetWidth;
    el.classList.add('click');
  };
};

async function moveCursor(page, x, y, instant = false) {
  await page.evaluate(
    ({ px, py, inst }) => window.__reelMoveCursor(px, py, inst),
    { px: x, py: y, inst: instant },
  );
  if (!instant) await sleep(580);
}

async function clickAt(page, x, y) {
  await moveCursor(page, x, y);
  await page.evaluate(() => window.__reelClick());
  await sleep(180);
  await page.mouse.click(x, y);
  await sleep(400);
}

async function clickTab(page, label) {
  const tab = page.locator('.header-tab').filter({ hasText: new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i') });
  await tab.waitFor({ state: 'visible', timeout: 30000 });
  const box = await tab.boundingBox();
  if (!box) throw new Error(`Tab not found: ${label}`);
  await clickAt(page, box.x + box.width / 2, box.y + box.height / 2);
  await sleep(1200);
}

async function ensureCursor(page) {
  await page.evaluate(CURSOR_INIT);
}

async function goToTab(page, tabId) {
  await page.goto(`${baseUrl}/?tab=${tabId}`, { waitUntil: 'networkidle', timeout: 120000 });
  await page.evaluate(() => document.fonts.ready);
  await ensureCursor(page);
  await sleep(1200);
}

async function smoothScroll(page, deltaY, steps = 8) {
  const step = deltaY / steps;
  for (let i = 0; i < steps; i += 1) {
    await page.mouse.wheel(0, step);
    await sleep(80);
  }
}

async function waitForBrief(page) {
  await page.waitForSelector('.stats-row', { timeout: 60000 });
  await page.waitForFunction(
    () => document.querySelector('.morning-brief-list, .morning-brief-empty, .timeline-heatmap'),
    { timeout: 120000 },
  );
  await sleep(1500);
}

async function waitForFeed(page) {
  await page.waitForFunction(
    () => {
      const feed = document.querySelector('.cve-feed');
      if (!feed) return false;
      const style = window.getComputedStyle(feed);
      return style.display !== 'none' && style.visibility !== 'hidden' && !feed.hidden;
    },
    { timeout: 120000 },
  );
  await page.waitForFunction(() => document.querySelectorAll('.cve-card').length > 0, { timeout: 120000 });
  await sleep(1200);
}

async function waitForDrawer(page) {
  await page.waitForSelector('.drawer-panel.drawer-panel-open, .drawer-panel-open', { timeout: 60000 });
  await sleep(1800);
}

async function main() {
  await mkdir(outDir, { recursive: true });
  const { cookies } = await loginSession();

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    colorScheme: 'dark',
    recordVideo: {
      dir: outDir,
      size: VIEWPORT,
    },
  });
  await context.addCookies(cookies);
  const page = await context.newPage();

  await page.addInitScript(CURSOR_INIT);
  await page.addInitScript(() => {
    try {
      localStorage.removeItem('briefr_theme');
      localStorage.setItem('briefr_tutorial_seen', '1');
      document.documentElement.removeAttribute('data-theme');
    } catch {}
  });

  await page.goto(baseUrl, { waitUntil: 'networkidle', timeout: 120000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForSelector('.header .header-logo-btn', { timeout: 60000 });
  if (await page.locator('.tutorial-overlay').isVisible().catch(() => false)) {
    await page.locator('.tutorial-skip, .tutorial-close').first().click();
    await sleep(400);
  }
  await page.evaluate(CURSOR_INIT);
  await ensureCursor(page);
  await moveCursor(page, 200, 120, true);
  await sleep(800);

  // ── BRIEF tab (0–12s) ──
  await waitForBrief(page);
  const statsBox = await page.locator('.stats-row').first().boundingBox();
  if (statsBox) await moveCursor(page, statsBox.x + statsBox.width * 0.25, statsBox.y + statsBox.height / 2);
  await sleep(1200);
  const heatmap = page.locator('.timeline-heatmap').first();
  if (await heatmap.count()) {
    const hb = await heatmap.boundingBox();
    if (hb) await moveCursor(page, hb.x + hb.width / 2, hb.y + hb.height / 2);
  }
  await sleep(1200);
  const briefRow = page.locator('.morning-brief-row').first();
  if (await briefRow.count()) {
    const br = await briefRow.boundingBox();
    if (br) await moveCursor(page, br.x + br.width * 0.5, br.y + br.height / 2);
    await sleep(1000);
    await smoothScroll(page, 280);
    await sleep(1200);
  }

  // ── FEED tab (12–24s) ──
  await goToTab(page, 'feed');
  await waitForFeed(page);
  const feedBox = await page.locator('.cve-feed').boundingBox();
  if (feedBox) await moveCursor(page, feedBox.x + feedBox.width * 0.5, feedBox.y + 180);
  await sleep(1000);
  await smoothScroll(page, 320);
  await sleep(800);

  const firstCard = page.locator('.cve-card').first();
  const cardBox = await firstCard.boundingBox();
  if (!cardBox) throw new Error('No CVE card found');
  await moveCursor(page, cardBox.x + cardBox.width * 0.45, cardBox.y + cardBox.height / 2);
  await sleep(600);
  await clickAt(page, cardBox.x + cardBox.width * 0.45, cardBox.y + cardBox.height / 2);
  await waitForDrawer(page);

  // Drawer tabs
  const drawerTabs = page.locator('.drawer-tab, .drawer-shell-tab, [role="tab"]');
  const tabCount = await drawerTabs.count();
  for (let i = 0; i < Math.min(tabCount, 3); i += 1) {
    const tab = drawerTabs.nth(i);
    const tb = await tab.boundingBox();
    if (tb) {
      await clickAt(page, tb.x + tb.width / 2, tb.y + tb.height / 2);
      await sleep(1400);
      await smoothScroll(page, 220, 6);
      await sleep(800);
    }
  }

  await page.keyboard.press('Escape');
  await sleep(700);

  // ── IOC LOOKUP (24–36s) ──
  await goToTab(page, 'ioc');
  await page.waitForSelector('.ioc-lookup', { timeout: 30000 });
  await sleep(1000);
  const iocInput = page.locator('#ioc-value-input');
  const iocBox = await iocInput.boundingBox();
  if (iocBox) {
    await clickAt(page, iocBox.x + iocBox.width * 0.35, iocBox.y + iocBox.height / 2);
    await iocInput.fill('185.220.101.42');
    await sleep(800);
    const lookupBtn = page.locator('.ioc-lookup-btn, .ioc-btn-lookup').first();
    const lb = await lookupBtn.boundingBox();
    if (lb) await clickAt(page, lb.x + lb.width / 2, lb.y + lb.height / 2);
    await sleep(3500);
  }

  // ── FORGE (36–48s) ──
  await goToTab(page, 'forge');
  await page.waitForSelector('.forge-root, .forge-page, [class*="forge"]', { timeout: 30000 });
  await sleep(1500);
  const forgeView = page.locator('.forge-view-tab, .forge-nav-tab, [class*="forge"] button, [class*="forge"] a').first();
  if (await forgeView.count()) {
    const fb = await forgeView.boundingBox();
    if (fb) await moveCursor(page, fb.x + fb.width / 2, fb.y + fb.height / 2);
  }
  await sleep(1000);
  await smoothScroll(page, 400);
  await sleep(1500);
  const matrix = page.locator('.forge-matrix, .attack-matrix, [class*="matrix"]').first();
  if (await matrix.count()) {
    const mb = await matrix.boundingBox();
    if (mb) await moveCursor(page, mb.x + mb.width * 0.4, mb.y + mb.height * 0.35);
  }
  await sleep(2000);
  await smoothScroll(page, -300, 6);
  await sleep(1200);

  // ── Hold on header logo (48–52s) ──
  const logo = page.locator('.header-logo-btn').first();
  const logoBox = await logo.boundingBox();
  if (logoBox) await moveCursor(page, logoBox.x + logoBox.width / 2, logoBox.y + logoBox.height / 2);
  await sleep(3500);

  const video = page.video();
  await context.close();
  await browser.close();

  if (!video) throw new Error('No video recorded');
  const tempPath = await video.path();
  const finalPath = path.join(outDir, 'walkthrough.webm');
  await rename(tempPath, finalPath);
  console.log('Wrote', finalPath);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
