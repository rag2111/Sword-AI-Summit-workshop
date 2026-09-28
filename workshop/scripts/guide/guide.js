(() => {
  "use strict";
  const storageKey = "prototype-to-proof:guide:v1";
  const pages = [...document.querySelectorAll(".page")];
  const order = ["home", "setup", ...Array.from({ length: 7 }, (_, i) => `lab${i}`), "wrap-up"];
  const checks = [];
  let progress = {};
  const announce = (text) => { document.getElementById("announcement").textContent = text; };
  const storageWarning = (text) => {
    const notice = document.getElementById("storage-notice");
    notice.textContent = text;
    notice.hidden = false;
  };
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey) || "{}");
    if (!stored || Array.isArray(stored) || typeof stored !== "object" ||
        Object.values(stored).some((value) => typeof value !== "boolean")) {
      throw new Error("Invalid progress format");
    }
    progress = stored;
  } catch (error) {
    storageWarning("Saved progress could not be read. Checkboxes still work for this visit; allow browser storage to keep progress.");
    console.warn("Guide progress could not be read:", error);
  }

  function updateProgress() {
    let complete = 0;
    for (let i = 0; i < 7; i++) {
      const lab = `lab${i}`;
      const required = checks.filter((check) => check.dataset.lab === lab && check.dataset.optional !== "true");
      const done = required.filter((check) => check.checked).length;
      const finished = required.length > 0 && done === required.length;
      if (finished) complete++;
      document.querySelectorAll(`[data-lab="${lab}"]:not(input)`).forEach((element) => {
        element.classList.toggle("complete", finished);
        const status = element.querySelector(".card-status");
        if (status) status.textContent = finished ? "Completed" : done ? `${done} / ${required.length} checkpoints` : "Not started";
        const dot = element.querySelector(".nav-status");
        if (dot) dot.setAttribute("aria-label", finished ? "Completed" : done ? "In progress" : "Not started");
      });
      document.getElementById(`${lab}-progress`).textContent = `${done} / ${required.length} required checkpoints`;
    }
    checks.forEach((check) => check.closest(".admonition").classList.toggle("step-done", check.checked));
    document.getElementById("progress").value = complete;
    document.getElementById("progress-label").textContent = `${complete} / 7 labs`;
    const next = order.find((id) => id.startsWith("lab") && !document.querySelector(`.lab-card[data-lab="${id}"]`).classList.contains("complete"));
    const resume = document.getElementById("resume");
    resume.href = `#${next || "wrap-up"}`;
    resume.textContent = next ? `${checks.some((check) => check.checked) ? "Continue" : "Start"} Lab ${next.slice(3)} →` : "Review your takeaways →";
  }

  function save() {
    try {
      localStorage.setItem(storageKey, JSON.stringify(progress));
    } catch (error) {
      storageWarning("Progress could not be saved. Your current checkmarks work until you close or reload this page.");
      console.warn("Guide progress could not be saved:", error);
    }
  }

  for (let i = 0; i < 7; i++) {
    const lab = document.getElementById(`lab${i}`);
    const toolbar = document.createElement("div");
    toolbar.className = "lab-toolbar";
    const count = document.createElement("strong");
    count.id = `${lab.id}-progress`;
    const jump = document.createElement("a");
    jump.href = `#${lab.id}/steps`;
    jump.textContent = "Jump to the steps ↓";
    toolbar.append(count, jump);
    lab.querySelector("h1").after(toolbar);
    lab.querySelectorAll(".dothis, .checkpoint").forEach((step, index) => {
      const title = step.querySelector(".admonition-title");
      const key = `${lab.id}-step-${index + 1}`;
      step.id = `${lab.id}--step-${index + 1}`;
      const optional = /\(optional/i.test(title.textContent);
      const label = document.createElement("label");
      label.className = "step-check";
      const check = document.createElement("input");
      check.type = "checkbox";
      check.id = key;
      check.dataset.lab = lab.id;
      check.dataset.optional = String(optional);
      check.checked = progress[key] === true;
      check.setAttribute("aria-label", `Mark complete: ${title.textContent}`);
      const text = step.classList.contains("checkpoint") ? "I verified the lab checkpoint" : optional ? "Optional step completed" : "Step completed";
      label.append(check, document.createTextNode(text));
      step.append(label);
      checks.push(check);
      const permalink = document.createElement("a");
      permalink.href = `#${lab.id}/step-${index + 1}`;
      permalink.className = "step-link";
      permalink.textContent = "Link to step";
      title.append(permalink);
      check.addEventListener("change", () => {
        progress[key] = check.checked;
        save();
        updateProgress();
        announce(check.checked ? `${lab.id.replace("lab", "Lab ")} checkpoint completed.` : "Checkpoint marked incomplete.");
      });
    });
  }

  document.querySelectorAll(".page pre").forEach((pre) => {
    const wrap = document.createElement("div");
    wrap.className = "code-wrap";
    pre.before(wrap);
    wrap.append(pre);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy-button";
    button.textContent = "Copy";
    button.setAttribute("aria-label", "Copy code block");
    wrap.append(button);
    button.addEventListener("click", async () => {
      const text = pre.textContent;
      try {
        if (!navigator.clipboard?.writeText) throw new Error("Clipboard API unavailable");
        await navigator.clipboard.writeText(text);
        button.textContent = "Copied!";
        announce("Code copied to clipboard.");
      } catch (error) {
        const selection = getSelection();
        const range = document.createRange();
        range.selectNodeContents(pre);
        selection.removeAllRanges();
        selection.addRange(range);
        button.textContent = "Selected";
        announce("Automatic copy is unavailable. Code selected: press Ctrl+C or Command+C to copy.");
        console.info("Automatic clipboard access unavailable:", error);
      }
      setTimeout(() => { button.textContent = "Copy"; }, 2500);
    });
  });
  document.querySelectorAll(".page table").forEach((table) => {
    const wrap = document.createElement("div");
    wrap.className = "table-scroll";
    wrap.tabIndex = 0;
    wrap.setAttribute("role", "region");
    wrap.setAttribute("aria-label", "Scrollable reference table");
    table.before(wrap);
    wrap.append(table);
  });
  document.getElementById("reset-progress").addEventListener("click", () => {
    if (!confirm("Reset all workshop checkmarks in this browser? Your code and lab results will not be changed.")) return;
    progress = {};
    checks.forEach((check) => { check.checked = false; });
    save();
    updateProgress();
    announce("Workshop progress reset.");
  });
  document.getElementById("print").addEventListener("click", () => window.print());

  function navigate(moveFocus = true) {
    let route;
    try {
      route = decodeURIComponent(location.hash.slice(1));
    } catch {
      route = "invalid-link";
    }
    if (route === "content" && document.querySelector(".page.active")) {
      document.getElementById("content").focus();
      return;
    }
    const [requested = "", fragment] = route.split("/");
    const id = !requested || requested === "content" ? "home" : requested;
    const page = pages.find((entry) => entry.id === id) || document.getElementById("home");
    const notice = document.getElementById("route-notice");
    notice.hidden = page.id === id;
    notice.textContent = "That page could not be found. Choose a lab from the learning path.";
    pages.forEach((entry) => entry.classList.toggle("active", entry === page));
    document.querySelectorAll(".sidebar nav a").forEach((link) => {
      if (link.hash === `#${page.id}`) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    document.title = page.id === "home" ? "From Prototype to Proof | Workshop" : `${page.querySelector("h1").textContent} | From Prototype to Proof`;
    const position = order.indexOf(page.id);
    const previous = order[Math.max(0, position - 1)];
    const next = order[position + 1];
    const nav = document.getElementById("page-navigation");
    nav.hidden = page.id === "home";
    const prevLink = document.getElementById("previous-page");
    const nextLink = document.getElementById("next-page");
    prevLink.href = `#${previous}`;
    prevLink.textContent = previous === "home" ? "← Overview" : `← ${previous.startsWith("lab") ? "Lab " + previous.slice(3) : "Setup"}`;
    nextLink.href = `#${next || "home"}`;
    nextLink.textContent = next ? `${next.startsWith("lab") ? "Lab " + next.slice(3) : "Key takeaways"} →` : "Back to overview →";
    const target = fragment && document.getElementById(`${page.id}--${fragment}`);
    if (fragment && !target) {
      notice.hidden = false;
      notice.textContent = "That section could not be found. The full lab is shown below.";
    }
    if (moveFocus) {
      const focus = target || page.querySelector("h1");
      focus.tabIndex = -1;
      focus.focus({ preventScroll: true });
      focus.scrollIntoView({ block: "start" });
    }
  }
  updateProgress();
  document.documentElement.classList.add("js");
  navigate(Boolean(location.hash));
  window.addEventListener("hashchange", () => navigate());
})();
