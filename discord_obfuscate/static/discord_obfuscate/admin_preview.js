(function () {
  function getPreviewUrl() {
    var path = window.location.pathname;
    if (path.endsWith("/change/")) {
      return path.replace(/\/[^/]+\/change\/$/, "/preview/");
    }
    if (path.endsWith("/add/")) {
      return path.replace(/\/add\/$/, "/preview/");
    }
    if (!path.endsWith("/")) {
      path += "/";
    }
    return path + "preview/";
  }

  function getCsrfToken() {
    var tokenInput = document.querySelector("input[name='csrfmiddlewaretoken']");
    return tokenInput ? tokenInput.value : "";
  }

  function collectFormData() {
    var formData = new FormData();
    var group = document.getElementById("id_group");
    var optOut = document.getElementById("id_opt_out");
    var customName = document.getElementById("id_custom_name");
    var useRandomKey = document.getElementById("id_use_random_key");
    var randomKey = document.getElementById("id_random_key");
    var rotateName = document.getElementById("id_random_key_rotate_name");
    var rotatePosition = document.getElementById("id_random_key_rotate_position");
    var obfuscationType = document.getElementById("id_obfuscation_type");
    var obfuscationFormat = document.getElementById("id_obfuscation_format");
    var minChars = document.getElementById("id_min_chars_before_divider");

    toggleRandomKeyFields(useRandomKey, randomKey, rotateName, rotatePosition);

    if (group) {
      formData.append("group", group.value || "");
    }
    if (optOut && optOut.checked) {
      formData.append("opt_out", "1");
    }
    if (customName) {
      formData.append("custom_name", customName.value || "");
    }
    if (useRandomKey && useRandomKey.checked) {
      formData.append("use_random_key", "1");
    }
    if (randomKey) {
      formData.append("random_key", randomKey.value || "");
    }
    if (rotateName && rotateName.checked) {
      formData.append("random_key_rotate_name", "1");
    }
    if (rotatePosition && rotatePosition.checked) {
      formData.append("random_key_rotate_position", "1");
    }
    if (obfuscationType) {
      formData.append("obfuscation_type", obfuscationType.value || "");
    }
    if (obfuscationFormat) {
      formData.append("obfuscation_format", obfuscationFormat.value || "");
    }
    if (minChars) {
      formData.append("min_chars_before_divider", minChars.value || "0");
    }

    var dividerInputs = document.querySelectorAll(
      "input[name='divider_characters']:checked"
    );
    dividerInputs.forEach(function (input) {
      formData.append("divider_characters", input.value);
    });

    return formData;
  }

  function generateRandomKey(length) {
    var chars =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    var key = "";
    if (window.crypto && window.crypto.getRandomValues) {
      var values = new Uint32Array(length);
      window.crypto.getRandomValues(values);
      for (var i = 0; i < length; i++) {
        key += chars[values[i] % chars.length];
      }
      return key;
    }
    for (var j = 0; j < length; j++) {
      key += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return key;
  }

  function toggleRandomKeyFields(
    useRandomKey,
    randomKey,
    rotateName,
    rotatePosition
  ) {
    if (!useRandomKey || !randomKey) {
      return;
    }
    if (useRandomKey.checked) {
      if (!randomKey.value) {
        randomKey.value = generateRandomKey(16);
      }
      showFieldRow(rotateName, true);
      showFieldRow(rotatePosition, true);
    } else {
      randomKey.value = "";
      if (rotateName) {
        rotateName.checked = false;
      }
      if (rotatePosition) {
        rotatePosition.checked = false;
      }
      showFieldRow(rotateName, false);
      showFieldRow(rotatePosition, false);
    }
  }

  function showFieldRow(input, visible) {
    if (!input) {
      return;
    }
    var row = input.closest(".form-row");
    if (!row) {
      return;
    }
    row.style.display = visible ? "" : "none";
  }

  function updatePreview() {
    var previewField = document.getElementById("id_preview");
    if (!previewField) {
      return;
    }
    var formData = collectFormData();
    var url = getPreviewUrl();
    fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCsrfToken(),
      },
      body: formData,
      credentials: "same-origin",
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        previewField.value = data.preview || "";
      })
      .catch(function () {
        previewField.value = "";
      });
  }

  function findForm() {
    var groupField = document.getElementById("id_group");
    if (groupField && groupField.form) {
      return groupField.form;
    }
    var form = document.getElementById("discordroleobfuscation_form");
    if (form) {
      return form;
    }
    return document.querySelector("#content-main form");
  }

  function bindPreview() {
    var form = findForm();
    if (!form) {
      return;
    }
    form.addEventListener("input", updatePreview);
    form.addEventListener("change", updatePreview);
    var useRandomKey = document.getElementById("id_use_random_key");
    if (useRandomKey) {
      useRandomKey.addEventListener("change", function () {
        var randomKey = document.getElementById("id_random_key");
        var rotateName = document.getElementById("id_random_key_rotate_name");
        var rotatePosition = document.getElementById("id_random_key_rotate_position");
        toggleRandomKeyFields(useRandomKey, randomKey, rotateName, rotatePosition);
        updatePreview();
      });
    }
    var randomKey = document.getElementById("id_random_key");
    var rotateName = document.getElementById("id_random_key_rotate_name");
    var rotatePosition = document.getElementById("id_random_key_rotate_position");
    toggleRandomKeyFields(useRandomKey, randomKey, rotateName, rotatePosition);
    updatePreview();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindPreview);
  } else {
    bindPreview();
  }
})();
