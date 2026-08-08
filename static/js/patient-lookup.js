/**
 * Verify patient identity for ER Visit / OutPatient Procedure intake.
 *
 * Uses Patient ID (preferred) or an unambiguous exact full name.
 * Sets a hidden patient_id only after a successful, unique match — never a guess.
 */
(function () {
  var DEFAULT_MESSAGE =
    "Patient not found. Please insert patient details first before attempting to request this service.";

  function ensureDialog() {
    var existing = document.getElementById("patient-lookup-dialog");
    if (existing) return existing;

    var overlay = document.createElement("div");
    overlay.id = "patient-lookup-dialog";
    overlay.className = "patient-lookup-dialog";
    overlay.hidden = true;
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-labelledby", "patient-lookup-dialog-title");
    overlay.innerHTML =
      '<div class="patient-lookup-dialog-panel">' +
      '<h2 id="patient-lookup-dialog-title">Patient lookup</h2>' +
      '<p class="patient-lookup-dialog-message"></p>' +
      '<button type="button" class="btn btn-solid patient-lookup-dialog-close">OK</button>' +
      "</div>";
    document.body.appendChild(overlay);

    function close() {
      overlay.hidden = true;
    }

    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) close();
    });
    overlay
      .querySelector(".patient-lookup-dialog-close")
      .addEventListener("click", close);
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !overlay.hidden) close();
    });
    return overlay;
  }

  function showDialog(title, message) {
    var dialog = ensureDialog();
    var heading = dialog.querySelector("#patient-lookup-dialog-title");
    var text = dialog.querySelector(".patient-lookup-dialog-message");
    heading.textContent = title || "Patient lookup";
    text.textContent = message || DEFAULT_MESSAGE;
    dialog.hidden = false;
    var closeBtn = dialog.querySelector(".patient-lookup-dialog-close");
    if (closeBtn) closeBtn.focus();
  }

  function setStatus(el, state, message) {
    if (!el) return;
    el.classList.remove(
      "patient-lookup-status--ok",
      "patient-lookup-status--error",
      "patient-lookup-status--checking"
    );
    if (state) {
      el.classList.add("patient-lookup-status--" + state);
    }
    el.textContent = message || "";
    el.hidden = !message;
  }

  function getOrCreatePatientIdField(form) {
    var field = form.querySelector("input[name='patient_id']");
    if (field) return field;
    field = document.createElement("input");
    field.type = "hidden";
    field.name = "patient_id";
    field.id = "patient_id";
    form.appendChild(field);
    return field;
  }

  function initField(input) {
    if (!input || input.dataset.patientLookupBound === "1") return;
    input.dataset.patientLookupBound = "1";

    var form = input.form;
    if (!form) return;

    var patientIdField = getOrCreatePatientIdField(form);
    var statusId = input.id + "-lookup-status";
    var status = document.getElementById(statusId);
    if (!status) {
      status = document.createElement("p");
      status.id = statusId;
      status.className = "patient-lookup-status form-note";
      status.hidden = true;
      input.insertAdjacentElement("afterend", status);
    }

    var lookupUrl =
      input.getAttribute("data-patient-lookup-url") ||
      form.getAttribute("data-patient-lookup-url") ||
      "/client/api/patient-lookup";
    var lastQuery = "";
    var verifiedPatientId = (patientIdField.value || "").trim();

    function clearVerified() {
      verifiedPatientId = "";
      patientIdField.value = "";
    }

    function runLookup(options) {
      options = options || {};
      var silent = !!options.silent;
      var query = (input.value || "").trim();
      if (!query) {
        clearVerified();
        setStatus(status, "", "");
        return Promise.resolve(false);
      }

      // Already verified for this resolved patient id embedded in the display value.
      if (
        verifiedPatientId &&
        query.indexOf("ID " + verifiedPatientId) !== -1 &&
        patientIdField.value === verifiedPatientId
      ) {
        return Promise.resolve(true);
      }

      if (
        query === lastQuery &&
        status.classList.contains("patient-lookup-status--checking")
      ) {
        return Promise.resolve(false);
      }

      lastQuery = query;
      setStatus(status, "checking", "Verifying patient…");

      var url =
        lookupUrl +
        (lookupUrl.indexOf("?") >= 0 ? "&" : "?") +
        "q=" +
        encodeURIComponent(query);
      return fetch(url, {
        method: "GET",
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      })
        .then(function (response) {
          if (!response.ok) throw new Error("lookup failed");
          return response.json();
        })
        .then(function (data) {
          if (data && data.found && data.patient_id) {
            verifiedPatientId = String(data.patient_id);
            patientIdField.value = verifiedPatientId;
            // Canonical display: full name + ID so submit uses the verified id.
            if (data.display_name) {
              input.value = data.display_name + " (ID " + data.patient_id + ")";
            }
            setStatus(
              status,
              "ok",
              data.message ||
                "Patient verified: ID " + data.patient_id
            );
            return true;
          }

          clearVerified();
          var msg = (data && data.message) || DEFAULT_MESSAGE;
          var title =
            data && data.status === "ambiguous"
              ? "Multiple patients match"
              : "Patient not found";
          setStatus(status, "error", msg);
          if (!silent) {
            showDialog(title, msg);
          }
          return false;
        })
        .catch(function () {
          clearVerified();
          var msg =
            "Unable to verify the patient right now. Please try again.";
          setStatus(status, "error", msg);
          if (!silent) {
            showDialog("Lookup unavailable", msg);
          }
          return false;
        });
    }

    input.addEventListener("input", function () {
      // Any edit invalidates prior verification until re-checked.
      if (patientIdField.value) {
        clearVerified();
        setStatus(status, "", "");
      }
    });

    input.addEventListener("blur", function () {
      runLookup({ silent: false });
    });

    form.addEventListener("submit", function (event) {
      if ((patientIdField.value || "").trim()) {
        return;
      }
      event.preventDefault();
      runLookup({ silent: false }).then(function (found) {
        if (found && (patientIdField.value || "").trim()) {
          form.submit();
        } else if (!status.classList.contains("patient-lookup-status--error")) {
          showDialog("Patient not found", DEFAULT_MESSAGE);
        }
      });
    });

    // Prefill from Service Request handoff: verify silently if patient_id already set.
    if ((patientIdField.value || "").trim()) {
      verifiedPatientId = String(patientIdField.value).trim();
      setStatus(
        status,
        "ok",
        "Patient verified: ID " + verifiedPatientId
      );
    } else if ((input.value || "").trim()) {
      runLookup({ silent: true });
    }
  }

  function init() {
    document
      .querySelectorAll("form[data-require-existing-patient='1']")
      .forEach(function (form) {
        var input =
          form.querySelector("[data-patient-lookup='1']") ||
          form.querySelector("#patient_name") ||
          form.querySelector("input[name='patient_name']");
        if (!input) return;
        input.setAttribute("data-patient-lookup", "1");
        if (!input.getAttribute("data-patient-lookup-url")) {
          input.setAttribute(
            "data-patient-lookup-url",
            form.getAttribute("data-patient-lookup-url") ||
              "/client/api/patient-lookup"
          );
        }
        initField(input);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
