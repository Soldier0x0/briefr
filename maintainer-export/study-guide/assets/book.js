
(function () {
  const PROGRESS_KEY = 'briefr-study-progress-v1';
  const PAGE_ID = document.body.dataset.pageId || '';
  const ASSETS_BASE = document.body.dataset.assetsBase || 'assets/';

  const toggle = document.getElementById('nav-toggle');
  const backdrop = document.getElementById('nav-backdrop');
  function setNav(open) {
    document.body.classList.toggle('nav-open', open);
    if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (backdrop) {
      if (open) backdrop.removeAttribute('hidden');
      else backdrop.setAttribute('hidden', '');
    }
  }
  if (toggle) toggle.addEventListener('click', () => setNav(!document.body.classList.contains('nav-open')));
  if (backdrop) backdrop.addEventListener('click', () => setNav(false));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setNav(false); });

  document.querySelectorAll('.toc-link').forEach(link => {
    const href = link.getAttribute('href') || '';
    const id = href.replace(/^.*\//, '').replace(/\.html$/, '');
    const labelHtml = link.innerHTML;
    link.innerHTML = '';
    const check = document.createElement('span');
    check.className = 'toc-check';
    check.dataset.page = id;
    check.title = 'Mark as read';
    const label = document.createElement('span');
    label.className = 'toc-label';
    label.innerHTML = labelHtml;
    link.appendChild(check);
    link.appendChild(label);
    if (id === PAGE_ID) link.classList.add('active');
  });

  function loadProgress() {
    try { return new Set(JSON.parse(localStorage.getItem(PROGRESS_KEY) || '[]')); }
    catch (e) { return new Set(); }
  }
  function saveProgress(set) {
    try { localStorage.setItem(PROGRESS_KEY, JSON.stringify(Array.from(set))); } catch (e) {}
  }
  let progress = loadProgress();
  function renderProgress() {
    const checks = document.querySelectorAll('.toc-check');
    checks.forEach(cb => cb.classList.toggle('done', progress.has(cb.dataset.page)));
    const total = checks.length;
    const done = Array.from(checks).filter(cb => progress.has(cb.dataset.page)).length;
    const label = document.getElementById('progress-label');
    const fill = document.getElementById('progress-fill');
    if (label) label.textContent = done + ' / ' + total + ' read';
    if (fill) fill.style.width = (total ? (done / total * 100) : 0) + '%';
  }
  const toc = document.getElementById('toc');
  if (toc) toc.addEventListener('click', (e) => {
    const check = e.target.closest('.toc-check');
    if (!check) return;
    e.preventDefault();
    e.stopPropagation();
    const id = check.dataset.page;
    if (progress.has(id)) progress.delete(id); else progress.add(id);
    saveProgress(progress);
    renderProgress();
  });
  const resetBtn = document.getElementById('progress-reset');
  if (resetBtn) resetBtn.addEventListener('click', () => {
    progress = new Set();
    saveProgress(progress);
    renderProgress();
  });
  renderProgress();

  let searchIndex = null;
  fetch(ASSETS_BASE + 'search-index.json').then(r => r.json()).then(data => { searchIndex = data; }).catch(() => {});
  const searchInput = document.getElementById('search');
  const emptyMsg = document.getElementById('search-empty');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.trim().toLowerCase();
      const links = document.querySelectorAll('.toc-link');
      const groups = document.querySelectorAll('.toc-group');
      if (!q) {
        links.forEach(l => l.classList.remove('hidden-by-search'));
        groups.forEach(g => g.classList.remove('hidden-by-search'));
        if (emptyMsg) emptyMsg.style.display = 'none';
        return;
      }
      const matchIds = new Set();
      if (searchIndex) {
        searchIndex.forEach(row => {
          if ((row.title + ' ' + row.text).toLowerCase().includes(q)) matchIds.add(row.id);
        });
      }
      let anyVisible = false;
      groups.forEach(g => { g.dataset.anyMatch = '0'; });
      links.forEach(l => {
        const href = l.getAttribute('href') || '';
        const id = href.replace(/^.*\//, '').replace(/\.html$/, '');
        const match = matchIds.has(id) || l.textContent.toLowerCase().includes(q);
        l.classList.toggle('hidden-by-search', !match);
        if (match) {
          anyVisible = true;
          const g = l.closest('.toc-group');
          if (g) g.dataset.anyMatch = '1';
        }
      });
      groups.forEach(g => g.classList.toggle('hidden-by-search', g.dataset.anyMatch !== '1'));
      if (emptyMsg) emptyMsg.style.display = anyVisible ? 'none' : 'block';
    });
    searchInput.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const firstMatch = document.querySelector('.toc-link:not(.hidden-by-search)');
      if (firstMatch) location.href = firstMatch.getAttribute('href');
    });
  }
})();
