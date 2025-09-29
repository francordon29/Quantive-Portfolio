document.addEventListener("DOMContentLoaded", () => {
  const chartDataEl = document.getElementById("chart-data");
  if (!chartDataEl) return;

  const chartData = JSON.parse(chartDataEl.textContent);

  const canvases = [
    document.getElementById("distributionChart"),
    document.getElementById("growthChart"),
  ].filter(Boolean);

  if (canvases.length === 0) return;

  const observer = new IntersectionObserver(async (entries, obs) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        const [{ Chart }, _] = await Promise.all([
          import("https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"),
          import("https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"),
        ]);

        initCharts(Chart, chartData);
        obs.disconnect();
        break;
      }
    }
  }, { threshold: 0.2 });

  canvases.forEach((canvas) => observer.observe(canvas));
});

function initCharts(Chart, chartData) {
  // Asset Distribution Chart
  if (chartData.distribution && chartData.distribution.labels.length > 0) {
    const ctxDist = document.getElementById("distributionChart").getContext("2d");
    new Chart(ctxDist, {
      type: "doughnut",
      data: {
        labels: chartData.distribution.labels,
        datasets: [{
          data: chartData.distribution.values,
          backgroundColor: [
            "rgba(153, 102, 255, 0.7)",
            "rgba(255, 159, 64, 0.7)",
            "rgba(46, 204, 113, 0.7)",
            "rgba(255, 205, 86, 0.7)",
            "rgba(241, 196, 15, 0.7)",
            "rgba(26, 188, 156, 0.7)",
            "rgba(142, 68, 173, 0.7)",
            "rgba(230, 126, 34, 0.7)",
          ],
          borderColor: "#111827",
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#e5e7eb" } },
          tooltip: {
            callbacks: {
              label: function (context) {
                const total = context.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                const value = context.raw;
                const pct = ((value / total) * 100).toFixed(2) + "%";
                return context.label + ": " + pct;
              },
            },
          },
        },
      },
    });
  }

  // Portfolio Growth Chart
  if (chartData.growth && chartData.growth.labels.length > 1) {
    const ctxGrowth = document.getElementById("growthChart").getContext("2d");
    new Chart(ctxGrowth, {
      type: "line",
      data: {
        labels: chartData.growth.labels,
        datasets: [
          {
            label: "Portfolio Value",
            data: chartData.growth.values_abs,
            borderColor: "rgb(54, 162, 235)",
            backgroundColor: "rgba(54, 162, 235, 0.2)",
            fill: true,
            yAxisID: "y",
          },
          {
            label: "Growth",
            data: chartData.growth.values_pct,
            borderColor: "rgb(255, 99, 132)",
            yAxisID: "y1",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { labels: { color: "#e5e7eb" } },
          tooltip: {
            callbacks: {
              label: function (context) {
                let label = context.dataset.label || "";
                if (label) label += ": ";
                if (context.parsed.y !== null) {
                  if (context.dataset.yAxisID === "y1") {
                    label += context.parsed.y.toFixed(2) + "%";
                  } else {
                    label +=
                      "$" +
                      context.parsed.y.toLocaleString("en-US", {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      });
                  }
                }
                return label;
              },
            },
          },
        },
        scales: {
          x: {
            type: "time",
            time: { unit: "day" },
            title: { display: true, text: "Date", color: "#e5e7eb" },
            ticks: { color: "#9ca3af" },
            grid: { color: "#374151" },
          },
          y: {
            type: "linear",
            position: "left",
            title: { display: true, text: "Value ($)", color: "#e5e7eb" },
            ticks: { color: "#9ca3af" },
            grid: { color: "#374151" },
          },
          y1: {
            type: "linear",
            position: "right",
            title: { display: true, text: "Growth (%)", color: "#e5e7eb" },
            ticks: { color: "#9ca3af" },
            grid: { drawOnChartArea: false },
          },
        },
      },
    });
  }
}
