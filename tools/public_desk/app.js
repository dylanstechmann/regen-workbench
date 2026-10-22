'use strict';

// Only filters pre-rendered public entries. No network calls or browser storage.
const cards = Array.from(document.querySelectorAll('.research-card'));
const topic = document.querySelector('#topic');
const kind = document.querySelector('#kind');
const query = document.querySelector('#query');
const count = document.querySelector('#result-count');
const empty = document.querySelector('#no-results');
const fields = { topic, kind, q: query };

function restoreFilters() {
  const params = new URLSearchParams(location.search);
  for (const [name, field] of Object.entries(fields)) {
    field.value = (params.get(name) || '').slice(0, 300);
    if (field.tagName === 'SELECT' && field.selectedIndex < 0) field.value = '';
  }
}

function filterEntries(updateAddress = false) {
  const needle = query.value.trim().toLocaleLowerCase();
  let visible = 0;
  for (const card of cards) {
    card.hidden = Boolean((topic.value && card.dataset.topic !== topic.value) ||
      (kind.value && card.dataset.kind !== kind.value) ||
      (needle && !card.textContent.toLocaleLowerCase().includes(needle)));
    if (!card.hidden) visible++;
  }
  count.textContent = `${visible} of ${cards.length} entries`;
  empty.hidden = visible !== 0;
  if (updateAddress) {
    const url = new URL(location.href);
    for (const [name, field] of Object.entries(fields)) {
      if (field.value) url.searchParams.set(name, field.value);
      else url.searchParams.delete(name);
    }
    history.replaceState(null, '', url);
  }
}

function revealLinkedEntry() {
  const target = cards.find(card => `#${card.id}` === location.hash);
  if (target && target.hidden) {
    for (const field of Object.values(fields)) field.value = '';
    filterEntries(true);
  }
  if (target) target.scrollIntoView({ block: 'start' });
}

for (const field of Object.values(fields)) field.addEventListener('input', () => filterEntries(true));
document.querySelector('#clear').addEventListener('click', () => {
  for (const field of Object.values(fields)) field.value = '';
  filterEntries(true);
  query.focus();
});
window.addEventListener('popstate', () => { restoreFilters(); filterEntries(); revealLinkedEntry(); });
window.addEventListener('hashchange', revealLinkedEntry);
restoreFilters();
filterEntries();
document.querySelector('#filters').hidden = false;
revealLinkedEntry();
