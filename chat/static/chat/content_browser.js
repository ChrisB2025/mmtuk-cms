/* MMTUK CMS — Content Browser JavaScript */

(function () {
  var searchInput = document.getElementById('searchInput');
  var sortSelect = document.getElementById('sortSelect');
  var debounceTimer = null;

  function getParams() {
    return new URLSearchParams(window.location.search);
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
  document.querySelectorAll('.view-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      navigateWithParams({ view: this.getAttribute('data-view') });
    });
  });

  // --- Bulk Selection ---

  var selectAllCb = document.getElementById('selectAll');
  var bulkToolbar = document.getElementById('bulkToolbar');
  var bulkCountEl = document.getElementById('bulkCount');

  function getChecked() {
    return Array.from(document.querySelectorAll('.bulk-checkbox:checked'));
  }

  function getAll() {
    return Array.from(document.querySelectorAll('.bulk-checkbox'));
  }

  function updateBulkToolbar() {
    var checked = getChecked();
    var all = getAll();

    if (bulkToolbar) {
      bulkToolbar.style.display = checked.length > 0 ? 'flex' : 'none';
    }
    if (bulkCountEl) {
      bulkCountEl.textContent = checked.length + ' selected';
    }
    if (selectAllCb) {
      selectAllCb.indeterminate = checked.length > 0 && checked.length < all.length;
      selectAllCb.checked = all.length > 0 && checked.length === all.length;
    }
  }

  // Wire up each checkbox
  getAll().forEach(function (cb) {
    cb.addEventListener('change', updateBulkToolbar);
  });

  // Select-all toggle
  if (selectAllCb) {
    selectAllCb.addEventListener('change', function () {
      getAll().forEach(function (cb) { cb.checked = selectAllCb.checked; });
      updateBulkToolbar();
    });
  }

  // Deselect all
  var deselectBtn = document.getElementById('deselectAll');
  if (deselectBtn) {
    deselectBtn.addEventListener('click', function () {
      getAll().forEach(function (cb) { cb.checked = false; });
      updateBulkToolbar();
    });
  }

  // Bulk API call
  function bulkApiCall(action, items, onSuccess) {
    fetch(window.BULK_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': window.CSRF_TOKEN,
      },
      body: JSON.stringify({ action: action, items: items }),
    })
      .then(function (resp) {
        if (resp.status === 403) throw new Error('permission');
        if (!resp.ok) throw new Error('server');
        return resp.json();
      })
      .then(function (data) {
        var succeeded = data.success || 0;
        var failed = data.errors || 0;
        if (succeeded > 0 && window.showToast) {
          window.showToast(succeeded + ' item' + (succeeded !== 1 ? 's' : '') + ' updated.', 'success');
        }
        if (failed > 0 && window.showToast) {
          window.showToast(failed + ' item' + (failed !== 1 ? 's' : '') + ' failed.', 'error');
        }
        if (onSuccess) onSuccess(succeeded);
      })
      .catch(function (err) {
        if (window.showToast) {
          var msg = err.message === 'permission'
            ? 'You do not have permission to perform this action.'
            : 'Something went wrong. Please try again.';
          window.showToast(msg, 'error');
        }
      });
  }

  function getSelectedItems() {
    return getChecked().map(function (cb) {
      return { slug: cb.value, content_type: cb.getAttribute('data-type') };
    });
  }

  // Bulk delete
  var bulkDeleteBtn = document.getElementById('bulkDelete');
  if (bulkDeleteBtn) {
    bulkDeleteBtn.addEventListener('click', function () {
      var items = getSelectedItems();
      if (!items.length) return;
      if (!confirm('Delete ' + items.length + ' item' + (items.length !== 1 ? 's' : '') + '? This cannot be undone.')) return;
      bulkApiCall('delete', items, function (count) {
        if (count > 0) setTimeout(function () { window.location.reload(); }, 1500);
      });
    });
  }

  // Bulk set draft
  var bulkSetDraftBtn = document.getElementById('bulkSetDraft');
  if (bulkSetDraftBtn) {
    bulkSetDraftBtn.addEventListener('click', function () {
      var items = getSelectedItems();
      if (!items.length) return;
      bulkApiCall('set_draft', items, function (count) {
        if (count > 0) setTimeout(function () { window.location.reload(); }, 1500);
      });
    });
  }

  // Bulk unset draft (publish)
  var bulkUnsetDraftBtn = document.getElementById('bulkUnsetDraft');
  if (bulkUnsetDraftBtn) {
    bulkUnsetDraftBtn.addEventListener('click', function () {
      var items = getSelectedItems();
      if (!items.length) return;
      bulkApiCall('unset_draft', items, function (count) {
        if (count > 0) setTimeout(function () { window.location.reload(); }, 1500);
      });
    });
  }
})();
