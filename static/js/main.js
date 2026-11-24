(function () {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return match ? decodeURIComponent(match[2]) : "";
  }

  function showToast(message) {
    const toast = $("#notification-toast");
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    setTimeout(() => { toast.hidden = true; }, 4200);
  }

  /* Reading progress ----------------------------------------------------- */
  const progressBar = $("#reading-progress");
  const articleBody = $(".article-body");
  if (progressBar && articleBody) {
    const updateProgress = () => {
      const start = articleBody.getBoundingClientRect().top + window.scrollY;
      const end = start + articleBody.offsetHeight - window.innerHeight;
      const percent = Math.min(100, Math.max(0, ((window.scrollY - start) / Math.max(end - start, 1)) * 100));
      progressBar.style.width = percent + "%";
    };
    window.addEventListener("scroll", updateProgress, { passive: true });
    window.addEventListener("resize", updateProgress);
    updateProgress();
  }

  /* Mobile navigation ---------------------------------------------------- */
  const menuToggle = $("#menu-toggle");
  const mainNav = $("#main-nav");
  if (menuToggle && mainNav) {
    menuToggle.addEventListener("click", () => {
      const open = mainNav.classList.toggle("is-open");
      menuToggle.setAttribute("aria-expanded", String(open));
    });
    $$(".nav-link", mainNav).forEach((link) => {
      link.addEventListener("click", () => {
        mainNav.classList.remove("is-open");
        menuToggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  /* Dashboard sidebar on small screens ---------------------------------- */
  const dashboardToggle = $("#dashboard-menu-toggle");
  const dashboardSidebar = $("#dashboard-sidebar");
  if (dashboardToggle && dashboardSidebar) {
    dashboardToggle.addEventListener("click", () => dashboardSidebar.classList.toggle("is-open"));
  }

  /* Dark mode ------------------------------------------------------------ */
  const themeToggle = $("#theme-toggle");
  const savedTheme = localStorage.getItem("kd-theme");
  if (savedTheme) document.documentElement.dataset.theme = savedTheme;
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      localStorage.setItem("kd-theme", next);
      showToast(next === "dark" ? "Dark mode enabled" : "Light mode enabled");
    });
  }

  /* Newsletter subscription --------------------------------------------- */
  $$("form.newsletter-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      if (button) button.disabled = true;
      try {
        const response = await fetch("/newsletter/subscribe/", {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": getCookie("csrftoken"),
          },
          body: new FormData(form),
        });
        const data = await response.json();
        showToast(data.message || (data.ok ? "Subscribed!" : "Please check your email."));
        if (data.ok) form.reset();
      } catch (error) {
        showToast("Could not subscribe right now. Please try again.");
      } finally {
        if (button) button.disabled = false;
      }
    });
  });

  /* Breaking-news notification consent ---------------------------------- */
  const notificationButton = $("#notification-toggle");
  if (notificationButton && "Notification" in window) {
    if (localStorage.getItem("kd-notifications") === "granted") {
      notificationButton.classList.add("is-enabled");
    }
    notificationButton.addEventListener("click", async () => {
      try {
        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
          showToast("Alerts were not enabled. You can change this in your browser settings.");
          return;
        }
        localStorage.setItem("kd-notifications", "granted");
        notificationButton.classList.add("is-enabled");
        if ("serviceWorker" in navigator) {
          const registration = await navigator.serviceWorker.register("/sw.js");
          const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: localStorage.getItem("kd-vapid-key") || undefined,
          }).catch(() => null);
          if (subscription) {
            await fetch("/notifications/subscribe/", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
              },
              body: JSON.stringify(subscription),
            });
          }
        }
        showToast("Breaking news alerts enabled. Demo notice: no live alerts are sent from this sample site.");
      } catch (error) {
        showToast("Your browser could not enable alerts.");
      }
    });
  }

  /* Ad impression tracking ----------------------------------------------- */
  $$(".ad-unit[data-ad-id]").forEach((unit) => {
    fetch(`/ads/impression/${unit.dataset.adId}/`, { keepalive: true }).catch(() => {});
  });

  /* Native share / copy link -------------------------------------------- */
  $$("[data-share-native]").forEach((button) => {
    button.addEventListener("click", async () => {
      const payload = {
        title: button.dataset.title || document.title,
        text: button.dataset.text || "",
        url: button.dataset.url || window.location.href,
      };
      if (navigator.share) {
        try { await navigator.share(payload); } catch (error) { /* user cancelled */ }
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(payload.url);
        showToast("Link copied to clipboard");
      }
    });
  });

  /* Infinite scroll for paginated story lists --------------------------- */
  const loadMore = $("#load-more");
  if (loadMore) {
    const url = new URL(loadMore.href, window.location.href);
    url.searchParams.set("partial", "1");
    let loading = false;
    let nextUrl = url.toString();
    const sentinel = $("#load-sentinel");
    const observer = new IntersectionObserver(async (entries) => {
      if (!entries[0].isIntersecting || loading || !nextUrl) return;
      loading = true;
      try {
        const response = await fetch(nextUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } });
        if (!response.ok) throw new Error("failed");
        const html = await response.text();
        const template = document.createElement("template");
        template.innerHTML = html.trim();
        const cards = template.content.querySelectorAll(".story-card");
        const target = $("#infinite-results");
        if (target && cards.length) {
          cards.forEach((card) => target.appendChild(card));
          const next = template.content.querySelector("[data-next-url]");
          nextUrl = next ? next.dataset.nextUrl : "";
          if (!nextUrl) loadMore.remove();
        } else {
          nextUrl = "";
          loadMore.remove();
        }
      } catch (error) {
        nextUrl = "";
        loadMore.remove();
      } finally {
        loading = false;
      }
    }, { rootMargin: "300px" });
    if (sentinel) observer.observe(sentinel);
  }

  /* Dashboard destructive-action confirmation --------------------------- */
  $$("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  /* Auto-dismiss alerts --------------------------------------------------- */
  setTimeout(() => {
    $$(".message-stack .alert").forEach((alert) => {
      alert.style.transition = "opacity .4s ease";
      alert.style.opacity = "0";
      setTimeout(() => alert.remove(), 400);
    });
  }, 6000);
})();
