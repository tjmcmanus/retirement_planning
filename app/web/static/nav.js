// Shared navigation for every HTML page. One list, so a newly migrated page is a one-line change:
// set `href` to its route. Pages not migrated yet link to the same page in the Streamlit service.
(function () {
  const STREAMLIT = `${location.protocol}//${location.hostname}:8501`;
  const PAGES = [
    { label: "Dashboard", href: "/" },
    { label: "Portfolio", href: "/portfolio" },
    { label: "Strategy", href: "/strategy" },
    { label: "Advanced Strategy Tools", href: "/advanced" },
    { label: "Monte Carlo", href: "/monte-carlo" },
    { label: "Scenario Planning", href: "/scenarios" },
    { label: "Estate Planning", href: "/estate" },
    { label: "Reports", href: "/reports" },
    { label: "Settings", href: "/settings" },
    { label: "Tax Data Admin", href: "/tax-data" },
  ];

  function render() {
    const nav = document.getElementById("main-nav");
    if (!nav) return;
    const here = location.pathname.replace(/\/+$/, "") || "/";
    PAGES.forEach((p) => {
      const url = p.href || STREAMLIT + p.legacy;
      const isCurrent = p.href === here;
      const el = document.createElement(isCurrent ? "span" : "a");
      el.textContent = p.label;
      if (isCurrent) {
        el.className = "current";
      } else {
        el.href = url;
        if (!p.href) {
          el.className = "legacy";
          el.title = "Not migrated yet - opens the Streamlit version";
        }
      }
      nav.appendChild(el);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render);
  else render();
})();
