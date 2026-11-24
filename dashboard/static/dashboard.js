"use strict";

const POLL_INTERVAL_MS = 2000;
const STALE_AFTER_S = 5;
const COLORS = {
  trendLine: "#3c3c3c",
  alarmLimit: "#c62828",
  grid: "#c8c8c8",
  text: "#5a5a5a",
};

const signals = JSON.parse(document.getElementById("signal-settings").textContent);
const charts = new Map();

function formatTime(isoTimestamp) {
  return new Date(isoTimestamp).toLocaleTimeString([], { hour12: false });
}

function createChart(signal) {
  const datasets = [
    {
      label: signal.label,
      data: [],
      borderColor: COLORS.trendLine,
      borderWidth: 1.5,
      pointRadius: 0,
    },
  ];
  if (signal.alarm_limit !== null) {
    datasets.push({
      label: "Alarm limit",
      data: [],
      borderColor: COLORS.alarmLimit,
      borderWidth: 1,
      borderDash: [6, 4],
      pointRadius: 0,
    });
  }
  return new Chart(document.getElementById(`chart-${signal.name}`), {
    type: "line",
    data: { labels: [], datasets },
    options: {
      animation: false,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { color: COLORS.text, maxTicksLimit: 6, maxRotation: 0 },
          grid: { color: COLORS.grid },
        },
        y: {
          ticks: { color: COLORS.text },
          grid: { color: COLORS.grid },
        },
      },
    },
  });
}

function updateValues(latest) {
  for (const signal of signals) {
    const value = latest[signal.name];
    document.getElementById(`value-${signal.name}`).textContent =
      value.toFixed(signal.decimals);
    const aboveLimit = signal.alarm_limit !== null && value > signal.alarm_limit;
    document.getElementById(`tile-${signal.name}`).classList.toggle("alarm", aboveLimit);
  }
}

function updateCharts(measurements) {
  const labels = measurements.map((row) => formatTime(row.timestamp));
  for (const signal of signals) {
    const chart = charts.get(signal.name);
    chart.data.labels = labels;
    chart.data.datasets[0].data = measurements.map((row) => row[signal.name]);
    if (signal.alarm_limit !== null) {
      chart.data.datasets[1].data = labels.map(() => signal.alarm_limit);
    }
    chart.update("none");
  }
}

function updateDataStatus(serverTime, latestTimestamp) {
  const ageSeconds = (new Date(serverTime) - new Date(latestTimestamp)) / 1000;
  const badge = document.getElementById("data-status");
  const stale = ageSeconds > STALE_AFTER_S;
  badge.textContent = stale ? "Data stale" : "Live";
  badge.classList.toggle("stale", stale);
  document.getElementById("last-update").textContent = formatTime(latestTimestamp);
}

function showNoData(message) {
  const badge = document.getElementById("data-status");
  badge.textContent = message;
  badge.classList.add("stale");
}

function alarmRow(alarm) {
  const row = document.createElement("tr");
  const active = alarm.cleared_at === null;
  row.className = active ? "active" : "cleared";
  const cells = [
    active ? "Active" : "Cleared",
    formatTime(alarm.raised_at),
    active ? "" : formatTime(alarm.cleared_at),
    alarm.source,
    alarm.message,
  ];
  for (const text of cells) {
    const cell = document.createElement("td");
    cell.textContent = text;
    row.append(cell);
  }
  return row;
}

function updateAlarms(alarms) {
  const body = document.getElementById("alarm-rows");
  const sorted = [...alarms].sort(
    (a, b) => (a.cleared_at === null ? 0 : 1) - (b.cleared_at === null ? 0 : 1),
  );
  if (sorted.length === 0) {
    const row = document.createElement("tr");
    row.className = "alarm-empty";
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.textContent = "No alarms recorded";
    row.append(cell);
    body.replaceChildren(row);
  } else {
    body.replaceChildren(...sorted.map(alarmRow));
  }
  const activeCount = alarms.filter((alarm) => alarm.cleared_at === null).length;
  document.getElementById("active-alarm-count").textContent = activeCount;
  document
    .getElementById("active-alarm-count")
    .parentElement.classList.toggle("alarm", activeCount > 0);
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }
  return response.json();
}

async function refresh() {
  try {
    const [measurementData, alarmData] = await Promise.all([
      fetchJson("/api/measurements"),
      fetchJson("/api/alarms"),
    ]);
    const { server_time: serverTime, measurements } = measurementData;
    if (measurements.length === 0) {
      showNoData("No data");
    } else {
      const latest = measurements[measurements.length - 1];
      updateValues(latest);
      updateCharts(measurements);
      updateDataStatus(serverTime, latest.timestamp);
    }
    updateAlarms(alarmData.alarms);
  } catch (error) {
    showNoData("Dashboard offline");
    console.error(error);
  }
}

function start() {
  for (const signal of signals) {
    charts.set(signal.name, createChart(signal));
  }
  refresh();
  setInterval(refresh, POLL_INTERVAL_MS);
}

start();
