/**
 * ShipSafe AI — Web Dashboard Client Application
 * Handles filtering, requirement detail drawer, live refresh, and interactions.
 */

document.addEventListener("DOMContentLoaded", () => {
  initFindingsFilters();
  initRequirementModal();
  initRefreshButton();
  initCopyButtons();
});

/**
 * Filter findings table by Severity, Requirement, and Agent
 */
function initFindingsFilters() {
  const table = document.getElementById("findingsTable");
  if (!table) return;

  const rows = table.querySelectorAll("tbody tr");
  const sevButtons = document.querySelectorAll(".filter-btn[data-severity]");
  const reqSelect = document.getElementById("filterRequirement");
  const agentSelect = document.getElementById("filterAgent");
  const counterSpan = document.getElementById("findingsFilteredCount");

  let activeSeverity = "ALL";
  let activeRequirement = "ALL";
  let activeAgent = "ALL";

  function applyFilters() {
    let visibleCount = 0;

    rows.forEach(row => {
      const rowSev = row.getAttribute("data-severity") || "";
      const rowReq = row.getAttribute("data-requirement") || "";
      const rowAgent = row.getAttribute("data-agent") || "";

      const matchSev = (activeSeverity === "ALL" || rowSev === activeSeverity);
      const matchReq = (activeRequirement === "ALL" || rowReq === activeRequirement);
      const matchAgent = (activeAgent === "ALL" || rowAgent === activeAgent);

      if (matchSev && matchReq && matchAgent) {
        row.style.display = "";
        visibleCount++;
      } else {
        row.style.display = "none";
      }
    });

    if (counterSpan) {
      counterSpan.textContent = visibleCount;
    }
  }

  sevButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      sevButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeSeverity = btn.getAttribute("data-severity");
      applyFilters();
    });
  });

  if (reqSelect) {
    reqSelect.addEventListener("change", () => {
      activeRequirement = reqSelect.value;
      applyFilters();
    });
  }

  if (agentSelect) {
    agentSelect.addEventListener("change", () => {
      activeAgent = agentSelect.value;
      applyFilters();
    });
  }
}

/**
 * Requirement Traceability Modal / Detail Drawer
 */
function initRequirementModal() {
  const modal = document.getElementById("reqModal");
  if (!modal) return;

  const closeBtn = modal.querySelector(".modal-close");
  const titleEl = document.getElementById("modalReqId");
  const textEl = document.getElementById("modalReqText");
  const statusEl = document.getElementById("modalReqStatus");
  const implList = document.getElementById("modalImplList");
  const testList = document.getElementById("modalTestList");
  const findingsList = document.getElementById("modalFindingsList");
  const actionEl = document.getElementById("modalAction");

  function openModal(reqData) {
    titleEl.textContent = reqData.requirement_id;
    textEl.textContent = reqData.requirement_text;
    statusEl.textContent = reqData.status;
    statusEl.className = "badge " + (reqData.status === "PASS" ? "badge-success" : "badge-blocked");

    // Implementation files
    implList.innerHTML = "";
    if (reqData.implementation && reqData.implementation.length > 0) {
      reqData.implementation.forEach(item => {
        const li = document.createElement("li");
        li.style.marginBottom = "8px";
        const code = document.createElement("span");
        code.className = "mono";
        code.style.color = "var(--accent-cyan)";
        code.textContent = item.file + (item.line_start ? `:${item.line_start}` : "");
        li.appendChild(code);
        if (item.description) {
          const desc = document.createElement("p");
          desc.style.fontSize = "12px";
          desc.style.color = "var(--text-secondary)";
          desc.textContent = item.description;
          li.appendChild(desc);
        }
        implList.appendChild(li);
      });
    } else {
      implList.innerHTML = "<li style='color:var(--text-muted)'>No modified implementation files.</li>";
    }

    // Test evidence
    testList.innerHTML = "";
    if (reqData.tests && reqData.tests.length > 0) {
      reqData.tests.forEach(test => {
        const li = document.createElement("li");
        li.style.marginBottom = "8px";
        const tag = document.createElement("span");
        tag.className = "badge badge-blocked";
        tag.textContent = test.status || "TEST";
        tag.style.marginRight = "8px";
        li.appendChild(tag);
        const name = document.createElement("span");
        name.className = "mono";
        name.textContent = test.test_name || test.file;
        li.appendChild(name);
        if (test.description) {
          const desc = document.createElement("p");
          desc.style.fontSize = "12px";
          desc.style.color = "var(--text-secondary)";
          desc.textContent = test.description;
          li.appendChild(desc);
        }
        testList.appendChild(li);
      });
    } else {
      testList.innerHTML = "<li style='color:var(--text-muted)'>No specific test evidence recorded.</li>";
    }

    // Bob findings
    findingsList.innerHTML = "";
    if (reqData.bob_findings && reqData.bob_findings.length > 0) {
      reqData.bob_findings.forEach(bf => {
        const li = document.createElement("li");
        li.style.marginBottom = "6px";
        const idBadge = document.createElement("span");
        idBadge.className = "badge badge-neutral";
        idBadge.style.marginRight = "6px";
        idBadge.textContent = bf.finding_id;
        li.appendChild(idBadge);
        const title = document.createElement("span");
        title.textContent = `${bf.title} (${bf.source_agent || "Bob agent"})`;
        li.appendChild(title);
        findingsList.appendChild(li);
      });
    } else {
      findingsList.innerHTML = "<li style='color:var(--text-muted)'>No direct Bob findings attached.</li>";
    }

    // Recommended action
    actionEl.textContent = reqData.recommended_action || "Review requirement specification and implement verified remediation.";

    modal.classList.add("open");
  }

  function closeModal() {
    modal.classList.remove("open");
  }

  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.classList.contains("open")) closeModal();
  });

  // Attach click to rows
  const reqRows = document.querySelectorAll(".req-row");
  reqRows.forEach(row => {
    row.addEventListener("click", () => {
      const jsonStr = row.getAttribute("data-json");
      if (jsonStr) {
        try {
          const data = JSON.parse(jsonStr);
          openModal(data);
        } catch (err) {
          console.error("Failed to parse requirement data:", err);
        }
      }
    });
  });
}

/**
 * Handle Live Refresh of Report Artifacts
 */
function initRefreshButton() {
  const btn = document.getElementById("btnRefreshData");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    const originalText = btn.innerHTML;
    btn.innerHTML = `<span class="pulse-dot"></span> Reloading...`;
    btn.disabled = true;

    try {
      const res = await fetch("/api/refresh", { method: "POST" });
      if (res.ok) {
        // Show success briefly, then reload page to reflect refreshed data
        btn.innerHTML = `✓ Reloaded`;
        setTimeout(() => {
          window.location.reload();
        }, 400);
      } else {
        alert("Failed to refresh analysis data from disk.");
        btn.innerHTML = originalText;
        btn.disabled = false;
      }
    } catch (err) {
      console.error("Refresh error:", err);
      alert("Network error refreshing data.");
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  });
}

/**
 * Copy to clipboard for command snippets
 */
function initCopyButtons() {
  document.querySelectorAll(".copy-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const text = btn.getAttribute("data-copy") || "";
      if (text) {
        navigator.clipboard.writeText(text).then(() => {
          const orig = btn.textContent;
          btn.textContent = "Copied!";
          setTimeout(() => { btn.textContent = orig; }, 1500);
        });
      }
    });
  });
}
