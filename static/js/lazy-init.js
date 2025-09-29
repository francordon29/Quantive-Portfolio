const charts = document.querySelectorAll("[data-chart]");
if (charts.length) {
  const loadCharts = async () => {
    try {
      const { default: Chart } = await import("/static/js/vendor/chart.min.js");
      const { initCharts } = await import("/static/js/charts.bundle.js");
      initCharts(Chart);
    } catch (err) {
      console.error("Error cargando gráficos:", err);
    }
  };

  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries, obs) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          loadCharts();
          obs.disconnect();
        }
      });
    }, { rootMargin: "200px" });
    io.observe(charts[0]);
  } else {
    (window.requestIdleCallback || setTimeout)(loadCharts, 500);
  }
}
