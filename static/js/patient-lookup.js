/**
 * On blur of Patient Name/ID fields, verify the patient exists before
 * service-specific intake (ER Visit, OutPatient Procedure) can proceed.
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
      '<h2 id="patient-lookup-dialog-title">Patient not found</h2>' +
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

  function showDialog(message) {
    var dialog = ensureDialog();
    var text = dialog.querySelector(".patient-lookup-dialog-message");
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

  function initField(input) {
    if (!input || input.dataset.patientLookupBound === "1") return;
    input.dataset.patientLookupBound = "1";

    var form = input.form;
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
      "/client/api/patient-lookup";
    var lastQuery = "";
    var verifiedQuery = "";

    function runLookup() {
      var query = (input.value || "").trim();
      if (!query) {
        verifiedQuery = "";
        setStatus(status, "", "");
        return Promise.resolve(false);
      }
      if (query === verifiedQuery) {
        return Promise.resolve(true);
      }
      if (query === lastQuery && status.classList.contains("patient-lookup-status--checking")) {
        return Promise.resolve(false);
      }

      lastQuery = query;
      setStatus(status, "checking", "Looking up patient…");

      var url = lookupUrl + (lookupUrl.indexOf("?") >= 0 ? "&" : "?") + "q=" + encodeURIComponent(query);
      return fetch(url, {
        method: "GET",
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      })
        .then(function (response) {
          if (!response.ok) throw new Error("Lookup failed");
          return response.json();
        })
        .then(function (data) {
          if (data && data.found) {
            verifiedQuery = query;
            setStatus(
              status,
              "ok",
              data.message ||
                "Patient found" +
                  (data.display_name ? ": " + data.display_name : "") +
                  (data.patient_id ? " (ID " + data.patient_id + ")" : "")
            );
            return true;
          }
          verifiedQuery = "";
          var msg = (data && data.message) || DEFAULT_MESSAGE;
          setStatus(status, "error", msg);
          showDialog(msg);
          return false;
        })
        .catch(function () {
          verifiedQuery = "";
          var msg =
            "Unable to verify the patient right now. Please try again.";
          setStatus(status, "error", msg);
          return false;
        });
    }

    input.addEventListener("blur", function () {
      runLookup();
    });

    if (form) {
      form.addEventListener("submit", function (event) {
        var query = (input.value || "").trim();
        if (!query) return;
        if (query === verifiedQuery) return;

        event.preventDefault();
        runLookup().then(function (found) {
          if (found) {
            form.submit();
          } else if (!status.classList.contains("patient-lookup-status--error")) {
            showDialog(DEFAULT_MESSAGE);
          }
        });
      });
    }
  }

  function init() {
    document.querySelectorAll("form[data-require-existing-patient='1']").forEach(function (form) {
      var input =
        form.querySelector("[data-patient-lookup='1']") ||
        form.querySelector("#patient_name") ||
        form.querySelector("input[name='patient_name']");
      if (!input) return;
      if (!input.getAttribute("data-patient-lookup-url")) {
        input.setAttribute(
          "data-patient-lookup-url",
          form.getAttribute("data-patient-lookup-url") || "/client/api/patient-lookup"
        );
      }
      input.setAttribute("data-patient-lookup", "1");
      initField(input);
    });

    document.querySelectorAll("[data-patient-lookup='1']").forEach(initField);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
