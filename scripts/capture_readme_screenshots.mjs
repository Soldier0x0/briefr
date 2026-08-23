import { createRequire } from 'module';
import { copyFile, mkdir } from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(__dirname, '../frontend/package.json'));
const { chromium } = require('playwright');
const outDir = path.join(__dirname, '..', 'docs', 'assets', 'screenshots');
const assetDir = path.join(__dirname, '..', 'docs', 'assets');
const baseUrl = process.env.SCREENSHOT_BASE_URL || 'http://127.0.0.1:5173';
const apiUrl = 'http://127.0.0.1:8000';

const VIEWPORT = { width: 1440, height: 900 };

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const screenshotUser = process.env.SCREENSHOT_USERNAME || 'harsha';
const screenshotPassword = process.env.SCREENSHOT_PASSWORD || '';

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
      else if (lower === 'secure') cookie.secure = false;
      else if (lower.startsWith('path=')) cookie.path = attr.slice(5);
      else if (lower.startsWith('samesite=')) {
        const raw = attr.slice(9).toLowerCase();
        cookie.sameSite = raw === 'none' ? 'None' : raw === 'lax' ? 'Lax' : 'Strict';
      }
    }
    return [cookie];
  });
}

async function loginSession() {
  if (!screenshotPassword) {
    throw new Error(
      'Set SCREENSHOT_PASSWORD (and optional SCREENSHOT_USERNAME) for authenticated capture',
    );
  }
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
  const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join('; ');
  return { cookies, cookieHeader };
}

async function fetchJson(url, cookieHeader = '') {
  const headers = cookieHeader ? { Cookie: cookieHeader } : {};
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`${url} returned ${res.status}`);
  }
  return res.json();
}

async function preflightBackend(cookieHeader) {
  await fetchJson(`${apiUrl}/api/health`, cookieHeader);

  const health = await fetchJson(`${apiUrl}/api/health`, cookieHeader);
  const cveCount = Number(health?.cve_count ?? 0);
  if (!cveCount) {
    throw new Error(
      'Backend has 0 CVEs — run: python3 scripts/seed_screenshot_data.py (with backend stopped or after fresh DB)',
    );
  }
  console.log(`Backend preflight OK — ${cveCount} CVEs in database`);

  let feed = await fetchJson(`${apiUrl}/api/case-studies/feed?atlas_limit=20`, cookieHeader);
  if (feed.meta?.warming) {
    console.log('Incidents feed warming — waiting for snapshot build…');
    for (let i = 0; i < 30; i += 1) {
      await sleep(2000);
      feed = await fetchJson(`${apiUrl}/api/case-studies/feed?atlas_limit=20`, cookieHeader);
      if (!feed.meta?.warming && (feed.data || []).length) break;
    }
  }
  const locked = (feed.errors || []).filter((e) =>
    String(e.message || '').toLowerCase().includes('database is locked'),
  );
  if (locked.length) {
    throw new Error(`Incidents feed reports database lock: ${JSON.stringify(locked)}`);
  }
  const newsCount = (feed.data || []).filter((c) => c.kind === 'news').length;
  if (!newsCount) {
    throw new Error(
      'Incidents feed has no RSS news cards — check network access and RSS sources',
    );
  }
  console.log(
    `Incidents feed preflight OK — ${newsCount} news cards, ${(feed.data || []).length} total`,
  );
}

async function shot(page, name) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(300);
  const file = path.join(outDir, name);
  await page.screenshot({ path: file, fullPage: false });
  console.log('Wrote', file);
}

async function clickTab(page, label) {
  const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  await page.locator('.header-tab').filter({ hasText: new RegExp(escaped, 'i') }).click();
  await sleep(800);
}

async function waitForBriefFeed(page) {
  await page.waitForSelector('.stats-row', { timeout: 60000 });
  await page.waitForFunction(
    () => {
      const briefRows = document.querySelectorAll('.morning-brief-row').length;
      const briefReady = document.querySelector('.morning-brief-list, .morning-brief-empty');
      const charts = document.querySelector('.brief-charts, .brief-vendor-chart');
      const heatmap = document.querySelector('.timeline-heatmap');
      return (briefReady && (briefRows > 0 || document.querySelector('.morning-brief-empty'))) ||
        charts ||
        heatmap;
    },
    { timeout: 120000 },
  );
  const stats = await page.evaluate(() => ({
    briefRows: document.querySelectorAll('.morning-brief-row').length,
    stats: !!document.querySelector('.stats-row'),
    heatmap: !!document.querySelector('.timeline-heatmap'),
  }));
  if (!stats.stats) {
    throw new Error('BRIEF tab stats row missing');
  }
  console.log(
    `BRIEF tab ready — ${stats.briefRows} brief rows, heatmap=${stats.heatmap}`,
  );
  await sleep(2000);
}

async function waitForIncidentsContent(page) {
  await page.waitForSelector('.cs-hero', { timeout: 60000 });
  await page.waitForFunction(
    () => {
      const cards = document.querySelectorAll('.cs-card');
      const skeleton = document.querySelector('.cs-skeleton-list');
      const hasError = !!document.querySelector('.cs-source-error');
      const isEmpty = !!document.querySelector('.cs-empty');
      return (cards.length > 0 && !skeleton) || hasError || isEmpty;
    },
    { timeout: 120000 },
  );

  const state = await page.evaluate(() => {
    const errors = [...document.querySelectorAll('.cs-source-error')].map((el) =>
      el.textContent.trim(),
    );
    const empty = document.querySelector('.cs-empty');
    const newsBadges = [...document.querySelectorAll('.cs-source-badge')]
      .map((el) => el.textContent.trim())
      .filter((label) => label && label !== 'MITRE ATLAS');
    return {
      errors,
      empty: empty?.textContent?.trim() || null,
      newsBadges,
      cardCount: document.querySelectorAll('.cs-card').length,
    };
  });

  const locked = state.errors.filter((msg) => /database is locked/i.test(msg));
  if (locked.length) {
    throw new Error(`Incidents tab shows database lock: ${locked.join('; ')}`);
  }
  if (state.errors.length) {
    throw new Error(`Incidents tab feed errors: ${state.errors.join('; ')}`);
  }
  if (state.empty) {
    throw new Error(state.empty);
  }
  if (!state.newsBadges.length) {
    throw new Error('Incidents tab has no RSS news source badges (only ATLAS?)');
  }
  console.log(
    `Incidents tab ready — ${state.cardCount} cards, sources: ${state.newsBadges.slice(0, 4).join(', ')}…`,
  );

  await sleep(3000);
}

async function waitForFeedTab(page) {
  await page.waitForSelector('.cve-feed', { timeout: 60000 });
  await page.waitForFunction(
    () => document.querySelectorAll('.cve-card').length > 0,
    { timeout: 120000 },
  );
  await sleep(2000);
}

async function openFirstCveDrawer(page) {
  const card = page.locator('.cve-card').first();
  await card.click();
  await page.waitForSelector('.drawer-panel.drawer-panel-open, .drawer-panel-open', { timeout: 60000 });
  await sleep(2500);
}

async function main() {
  const { cookies } = await loginSession();
  await preflightBackend(cookies.map((c) => `${c.name}=${c.value}`).join('; '));
  await mkdir(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    colorScheme: 'dark',
  });
  await context.addCookies(cookies);
  const page = await context.newPage();

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
  await sleep(5000);

  const styled = await page.evaluate(() => {
    const root = getComputedStyle(document.documentElement);
    return root.getPropertyValue('--red').trim() === '#e85533';
  });
  if (!styled) {
    throw new Error('CSS not applied (check CSP / Vite). --red token missing.');
  }

  await waitForBriefFeed(page);
  await shot(page, 'brief.png');

  await clickTab(page, 'FEED');
  await waitForFeedTab(page);
  await shot(page, 'feed.png');

  await openFirstCveDrawer(page);
  await shot(page, 'detail-drawer.png');
  await page.keyboard.press('Escape');
  await sleep(500);

  await clickTab(page, 'IOC LOOKUP');
  await page.waitForSelector('.ioc-lookup, .ioc-panel, [class*="ioc"]', { timeout: 30000 });
  await sleep(1500);
  await shot(page, 'ioc-lookup.png');

  await clickTab(page, 'ADVISORIES & INTEL');
  await waitForIncidentsContent(page);
  await shot(page, 'advisories-intel.png');

  await clickTab(page, 'FORGE');
  await page.waitForSelector('.forge-root, .forge-page, [class*="forge"]', { timeout: 30000 });
  await sleep(1500);
  await shot(page, 'forge.png');

  await clickTab(page, 'INVESTIGATE');
  await page.waitForSelector('.investigate-canvas, .investigate-root, [class*="investigate"]', {
    timeout: 30000,
  });
  await sleep(1500);
  await shot(page, 'investigate.png');

  await page.goto(`${baseUrl}/admin?p=overview`, { waitUntil: 'networkidle', timeout: 120000 });
  await page.waitForSelector('.admin-root, .admin-page-title', { timeout: 60000 });
  await sleep(2000);
  await shot(page, 'admin-analyst.png');

  await page.goto(`${baseUrl}/admin?p=security`, { waitUntil: 'networkidle', timeout: 120000 });
  await page.evaluate(() => {
    localStorage.setItem('briefr-admin-mode', 'operator');
    sessionStorage.setItem('briefr-operator-ack', '1');
  });
  await page.reload({ waitUntil: 'networkidle', timeout: 120000 });
  await page.waitForSelector('.admin-root, .admin-page-title', { timeout: 60000 });
  await sleep(2000);
  await shot(page, 'admin-operator.png');

  const aliases = [
    ['brief.png', 'ui-brief-tab.png'],
    ['feed.png', 'ui-feed-tab.png'],
    ['detail-drawer.png', 'ui-detail-drawer.png'],
    ['ioc-lookup.png', 'ui-ioc-lookup.png'],
    ['admin-analyst.png', 'ui-admin-analyst.png'],
    ['admin-operator.png', 'ui-admin-operator.png'],
  ];
  for (const [src, dest] of aliases) {
    await copyFile(path.join(outDir, src), path.join(assetDir, dest));
    console.log('Wrote', path.join(assetDir, dest));
  }

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
