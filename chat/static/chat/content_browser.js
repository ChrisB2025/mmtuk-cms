/* MMTUK CMS — Content Browser JavaScript */

(function () {
  var searchInput = document.getElementById('searchInput');
  var sortSelect = document.getElementById('sortSelect');
  var debounceTimer = null;

  function getParams() {
    var params = new URLSearchParams(window.location.search);
    return params;
  }

  function navigateWithParams(updates) {
    var params = getParams();
    for (var key in updates) {
      if (updates[key]) {
        params.set(key, updates[key]);
      } else {
        params.delete(key);
      }
    }
    window.location.href = window.location.pathname + '?' + params.toString();
  }

  // Search with debounce
  if (searchInput) {
    searchInput.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        navigateWithParams({ q: searchInput.value });
      }, 400);
    });

    // Allow Enter to search immediately
    searchInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        clearTimeout(debounceTimer);
        navigateWithParams({ q: searchInput.value });
      }
    });
  }

  // Sort change
  if (sortSelect) {
    sortSelect.addEventListener('change', function () {
      navigateWithParams({ sort: sortSelect.value });
    });
  }

  // View toggle
  var viewBtns = document.querySelectorAll('.view-btn');
  viewBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      navigateWithParams({ view: this.getAttribute('data-view') });
    });
  });

  // Bulk selection (Phase 7)
  var checkboxes = document.querySelectorAll('.bulk-checkbox');
  var bulkToolbar = document.getElementById('bulkToolbar');

  function updateBulkToolbar() {
    if (!bulkToolbar) return;
    var checked = document.querySelectorAll('.bulk-checkbox:checked');
    if (checked.length > 0) {
      bulkToolbar.style.display = 'flex';
      bulkToolbar.querySelector('.bulk-count').textContent = checked.length + ' selected';
    } else {
      bulkToolbar.style.display = 'none';
    }
  }

  checkboxes.forEach(function (cb) {
    cb.addEventListener('change', updateBulkToolbar);
  });
})();
