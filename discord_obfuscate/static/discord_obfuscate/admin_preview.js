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
    var obfuscationType = document.getElementById("id_obfuscation_type");
    var obfuscationFormat = document.getElementById("id_obfuscation_format");
    var minChars = document.getElementById("id_min_chars_before_divider");

    if (group) {
      formData.append("group", group.value || "");
    }
    if (optOut && optOut.checked) {
      formData.append("opt_out", "1");
    }
    if (customName) {
      formData.append("custom_name", customName.value || "");
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

  function bindPreview() {
    var form = document.querySelector("form");
    if (!form) {
      return;
    }
    form.addEventListener("input", updatePreview);
    form.addEventListener("change", updatePreview);
    updatePreview();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindPreview);
  } else {
    bindPreview();
  }
})();
