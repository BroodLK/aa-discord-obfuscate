(function () {
  function ready(fn) {
    if (document.readyState !== "loading") {
      fn();
      return;
    }
    document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    var tbody = document.getElementById("role-order-body");
    var hidden = document.getElementById("id_role_order_data");
    var container = document.querySelector(".role-ordering");
    if (!tbody || !hidden) {
      return;
    }
    if (container && container.dataset.enabled === "0") {
      return;
    }

    function rows() {
      return Array.prototype.slice.call(tbody.querySelectorAll("tr"));
    }

    function matchesSelector(el, selector) {
      if (!el || el.nodeType !== 1) {
        return false;
      }
      var proto =
        el.matches ||
        el.msMatchesSelector ||
        el.webkitMatchesSelector ||
        el.mozMatchesSelector;
      if (!proto) {
        return false;
      }
      return proto.call(el, selector);
    }

    function closestRow(el) {
      var node = el;
      while (node) {
        if (matchesSelector(node, "tr")) {
          return node;
        }
        node = node.parentElement;
      }
      return null;
    }

    function isLocked(row) {
      return row.dataset.locked === "1";
    }

    tbody.querySelectorAll(".role-lock").forEach(function (checkbox) {
      checkbox.addEventListener("change", function () {
        var row = closestRow(checkbox);
        if (!row || row.dataset.systemLocked === "1") {
          return;
        }
        var locked = checkbox.checked;
        row.dataset.locked = locked ? "1" : "0";
        row.dataset.userLocked = locked ? "1" : "0";
      });
    });

    var form = tbody.closest("form");
    if (form) {
      form.addEventListener("submit", function () {
        var data = rows().map(function (row) {
          var locked = row.dataset.userLocked === "1";
          return {
            role_id: row.dataset.roleId,
            locked: locked
          };
        });
        hidden.value = JSON.stringify(data);
      });
    }
  });
})();
