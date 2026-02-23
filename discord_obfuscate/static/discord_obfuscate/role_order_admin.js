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

    function setRowDraggable(row, draggable) {
      if (draggable) {
        row.setAttribute("draggable", "true");
      } else {
        row.removeAttribute("draggable");
      }
    }

    rows().forEach(function (row) {
      setRowDraggable(row, row.dataset.draggable === "1");
    });

    var dragged = null;

    function lockedBetween(rowA, rowB) {
      var list = rows();
      var idxA = list.indexOf(rowA);
      var idxB = list.indexOf(rowB);
      if (idxA === -1 || idxB === -1) {
        return false;
      }
      var start = Math.min(idxA, idxB);
      var end = Math.max(idxA, idxB);
      for (var i = start + 1; i < end; i += 1) {
        if (isLocked(list[i])) {
          return true;
        }
      }
      return false;
    }

    tbody.addEventListener("dragstart", function (event) {
      var row = closestRow(event.target);
      if (!row || isLocked(row)) {
        event.preventDefault();
        return;
      }
      if (!event.target.classList.contains("drag-handle")) {
        event.preventDefault();
        return;
      }
      dragged = row;
      row.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      try {
        event.dataTransfer.setData("text/plain", "");
      } catch (err) {
        // Ignore if the browser blocks setData.
      }
    });

    tbody.addEventListener("dragover", function (event) {
      if (!dragged) {
        return;
      }
      var row = closestRow(event.target);
      if (!row || row === dragged || isLocked(row)) {
        return;
      }
      if (lockedBetween(dragged, row)) {
        return;
      }
      event.preventDefault();
      var rect = row.getBoundingClientRect();
      var next = event.clientY > rect.top + rect.height / 2;
      tbody.insertBefore(dragged, next ? row.nextSibling : row);
    });

    tbody.addEventListener("dragend", function () {
      if (dragged) {
        dragged.classList.remove("dragging");
      }
      dragged = null;
    });

    tbody.querySelectorAll(".role-lock").forEach(function (checkbox) {
      checkbox.addEventListener("change", function () {
        var row = closestRow(checkbox);
        if (!row || row.dataset.systemLocked === "1") {
          return;
        }
        var locked = checkbox.checked;
        row.dataset.locked = locked ? "1" : "0";
        row.dataset.draggable = locked ? "0" : "1";
        row.dataset.userLocked = locked ? "1" : "0";
        setRowDraggable(row, !locked);
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
