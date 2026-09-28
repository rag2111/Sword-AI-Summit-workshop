// Per-lab countdown: click a "⏱ N min" badge (<span class="lab-timer" data-minutes="N">) to start/stop.
// Works with Material's instant navigation (document$) and with plain page loads.
(function () {
  function format(seconds) {
    const sign = seconds < 0 ? "-" : "";
    const s = Math.abs(seconds);
    return `${sign}${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }

  function wire(badge) {
    if (badge.dataset.wired) return;
    badge.dataset.wired = "1";
    const minutes = parseInt(badge.dataset.minutes || "0", 10);
    const label = badge.textContent;
    let timer = null;
    badge.title = "Click to start a countdown for this lab";
    badge.addEventListener("click", function () {
      if (timer) {
        clearInterval(timer);
        timer = null;
        badge.classList.remove("running", "overtime");
        badge.textContent = label;
        return;
      }
      let remaining = minutes * 60;
      badge.classList.add("running");
      badge.textContent = `⏱ ${format(remaining)}`;
      timer = setInterval(function () {
        remaining -= 1;
        badge.textContent = `⏱ ${format(remaining)}`;
        if (remaining < 0) badge.classList.add("overtime");
      }, 1000);
    });
  }

  function init() {
    document.querySelectorAll(".lab-timer").forEach(wire);
  }

  if (typeof window.document$ !== "undefined" && window.document$.subscribe) {
    window.document$.subscribe(init);
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }
})();
