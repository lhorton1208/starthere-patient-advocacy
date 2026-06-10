(function () {
  function fieldLabel(input) {
    var group = input.closest(".form-group");
    if (!group) return "Required field";
    var label = group.querySelector(".field-label");
    if (!label) return "Required field";
    return label.textContent.replace(/\*$/, "").trim();
  }

  function isFilled(input) {
    if (input.disabled) return true;
    if (input.type === "checkbox" || input.type === "radio") return true;
    if (input.tagName === "SELECT") {
      return input.value !== "" && input.value !== "0";
    }
    return input.value.trim() !== "";
  }

  function markInvalid(input, invalid) {
    var group = input.closest(".form-group");
    if (group) group.classList.toggle("is-invalid", invalid);
  }

  function clearInvalidMarks(form) {
    form.querySelectorAll(".form-group.is-invalid").forEach(function (group) {
      group.classList.remove("is-invalid");
    });
  }

  function validateForm(form) {
    clearInvalidMarks(form);
    var missing = [];
    var firstInvalid = null;

    form.querySelectorAll("[data-required]").forEach(function (input) {
      if (!isFilled(input)) {
        missing.push(fieldLabel(input));
        markInvalid(input, true);
        if (!firstInvalid) firstInvalid = input;
      }
    });

    if (missing.length) {
      alert(
        "Please complete the required fields before saving:\n\n• " +
          missing.join("\n• ")
      );
      if (firstInvalid) firstInvalid.focus();
      return false;
    }
    return true;
  }

  function alertServerValidationErrors() {
    var errorNodes = document.querySelectorAll(".field-error");
    if (!errorNodes.length) return;

    var labels = [];
    errorNodes.forEach(function (node) {
      var group = node.closest(".form-group");
      if (!group) return;
      group.classList.add("is-invalid");
      var label = fieldLabel(group.querySelector("[data-required], input, select, textarea"));
      if (label && labels.indexOf(label) === -1) labels.push(label);
    });

    var message =
      labels.length > 0
        ? "Please correct the required fields:\n\n• " + labels.join("\n• ")
        : "Please correct the highlighted fields before saving.";

    alert(message);

    var firstInput = document.querySelector(".form-group.is-invalid input, .form-group.is-invalid select, .form-group.is-invalid textarea");
    if (firstInput) firstInput.focus();
  }

  document.querySelectorAll('form[method="post"]').forEach(function (form) {
    form.setAttribute("novalidate", "novalidate");
    form.addEventListener("submit", function (event) {
      if (!validateForm(form)) event.preventDefault();
    });
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", alertServerValidationErrors);
  } else {
    alertServerValidationErrors();
  }
})();
