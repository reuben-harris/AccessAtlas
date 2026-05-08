(() => {
  const chartElement = document.getElementById("job-status-chart");
  const dataElement = document.getElementById("job-status-chart-data");
  const Chart = window.Chart;
  if (!chartElement || !dataElement || typeof Chart !== "function") {
    return;
  }

  const chartData = JSON.parse(dataElement.textContent);
  new Chart(chartElement, {
    type: "doughnut",
    data: {
      labels: chartData.labels,
      datasets: [
        {
          data: chartData.counts,
          backgroundColor: chartData.colors,
          borderWidth: 0,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "bottom",
        },
        tooltip: {
          callbacks: {
            label(context) {
              const value = Number(context.parsed || 0);
              const total = Number(chartData.total || 0);
              const percent = total ? Math.round((value / total) * 100) : 0;
              return `${context.label}: ${value} (${percent}%)`;
            },
          },
        },
      },
    },
  });
})();
