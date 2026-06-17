"use strict";

// ---- 标签切换 ----
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
  });
});

// ---- 工具 ----
async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

function renderOps(el, ops) {
  el.innerHTML =
    `<div class="cat">element_wise</div>${ops.element_wise.join(", ")}` +
    `<div class="cat">time_series</div>${ops.time_series.join(", ")}` +
    `<div class="cat">cross_sectional</div>${ops.cross_sectional.join(", ")}`;
}

function renderTable(records, title) {
  let html = `<div class="tbl-title">${title}</div><table><thead><tr><th></th>`;
  records.columns.forEach((c) => (html += `<th>${c}</th>`));
  html += "</tr></thead><tbody>";
  records.index.forEach((idx, i) => {
    html += `<tr><td>${idx}</td>`;
    records.rows[i].forEach((v) => (html += `<td>${v === null ? "" : v}</td>`));
    html += "</tr>";
  });
  return html + "</tbody></table>";
}

// ================= 模块一 =================
const M1_EXAMPLES = [
  "rank(-close)",
  "mean(close,3)",
  "zscore(delta(close,1))",
  "-delta(close,3)",
  "rank(delta(log(volume),1))",
  "corr(close, volume, 6)",
];

(function initM1() {
  const ex = document.getElementById("m1-examples");
  M1_EXAMPLES.forEach((e) => {
    const b = document.createElement("button");
    b.textContent = e;
    b.onclick = () => (document.getElementById("m1-expr").value = e);
    ex.appendChild(b);
  });

  fetch("/api/m1/meta").then((r) => r.json()).then((m) => {
    renderOps(document.getElementById("m1-ops"), m.operators);
  });

  document.getElementById("m1-run").addEventListener("click", runM1);
})();

async function runM1() {
  const status = document.getElementById("m1-status");
  const errBox = document.getElementById("m1-error");
  const meta = document.getElementById("m1-meta");
  const tables = document.getElementById("m1-tables");
  const images = document.getElementById("m1-images");
  const btn = document.getElementById("m1-run");

  errBox.hidden = true;
  tables.innerHTML = "";
  images.innerHTML = "";
  meta.innerHTML = "";
  status.className = "status loading";
  status.textContent = "正在运行 alphalens 完整分析";
  btn.disabled = true;

  const periods = document
    .getElementById("m1-periods")
    .value.split(",")
    .map((s) => parseInt(s.trim(), 10))
    .filter((n) => !isNaN(n));

  try {
    const data = await postJSON("/api/m1/run", {
      expr: document.getElementById("m1-expr").value,
      quantiles: parseInt(document.getElementById("m1-quantiles").value, 10),
      periods: periods.length ? periods : [1],
      max_loss: parseFloat(document.getElementById("m1-maxloss").value),
    });

    status.className = "status";
    if (!data.ok) {
      status.textContent = "";
      errBox.hidden = false;
      errBox.textContent = "错误：" + data.error;
      return;
    }
    status.textContent = "✅ 分析完成";
    meta.textContent = `因子=${data.meta.expr} | 有效因子值=${data.meta.n_factor_values} | 清洗后=${data.meta.n_clean} | 缓存=${JSON.stringify(data.meta.cache)} | 耗时=${data.meta.elapsed_ms}ms`;

    tables.innerHTML =
      renderTable(data.tables.ic_summary, "IC 概要") +
      renderTable(data.tables.mean_return_by_quantile_bps, "各分位平均收益 (bps)");

    data.images.forEach((b64) => {
      const img = document.createElement("img");
      img.src = "data:image/png;base64," + b64;
      images.appendChild(img);
    });
  } catch (e) {
    status.className = "status";
    status.textContent = "";
    errBox.hidden = false;
    errBox.textContent = "请求失败：" + e;
  } finally {
    btn.disabled = false;
  }
}

// ================= 模块二 =================
const M2_EXAMPLES = [
  ["cross_up(close, mean(close,20))", "cross_down(close, mean(close,20))"],
  ["cross_up(mean(close,5), mean(close,20))", "cross_down(mean(close,5), mean(close,20))"],
  ["close > mean(close,60)", "close < mean(close,60)"],
];

(function initM2() {
  const ex = document.getElementById("m2-examples");
  M2_EXAMPLES.forEach(([buy, sell]) => {
    const b = document.createElement("button");
    b.textContent = buy.split("(")[0] + " 策略";
    b.title = "买:" + buy + "  卖:" + sell;
    b.onclick = () => {
      document.getElementById("m2-buy").value = buy;
      document.getElementById("m2-sell").value = sell;
    };
    ex.appendChild(b);
  });

  fetch("/api/m2/instruments").then((r) => r.json()).then((m) => {
    renderOps(document.getElementById("m2-ops"), m.operators);
    const sel = document.getElementById("m2-instruments");
    window._allInstruments = m.instruments;
    m.instruments.forEach((code) => {
      const o = document.createElement("option");
      o.value = code;
      o.textContent = code;
      sel.appendChild(o);
    });
  });

  document.getElementById("m2-top10").onclick = () => {
    const sel = document.getElementById("m2-instruments");
    [...sel.options].forEach((o, i) => (o.selected = i < 10));
  };
  document.getElementById("m2-clear").onclick = () => {
    [...document.getElementById("m2-instruments").options].forEach((o) => (o.selected = false));
  };

  document.getElementById("m2-run").addEventListener("click", runM2);
})();

function metricCard(k, v, kind) {
  let cls = "";
  if (kind === "ret") cls = v >= 0 ? "pos" : "neg";
  return `<div class="metric"><div class="k">${k}</div><div class="v ${cls}">${v}</div></div>`;
}

async function runM2() {
  const status = document.getElementById("m2-status");
  const errBox = document.getElementById("m2-error");
  const metricsBox = document.getElementById("m2-metrics");
  const imageBox = document.getElementById("m2-image");
  const tableBox = document.getElementById("m2-table");
  const btn = document.getElementById("m2-run");

  errBox.hidden = true;
  metricsBox.innerHTML = "";
  imageBox.innerHTML = "";
  tableBox.innerHTML = "";
  status.className = "status loading";
  status.textContent = "正在回测";
  btn.disabled = true;

  const selected = [...document.getElementById("m2-instruments").selectedOptions].map((o) => o.value);

  try {
    const data = await postJSON("/api/m2/run", {
      buy_expr: document.getElementById("m2-buy").value,
      sell_expr: document.getElementById("m2-sell").value,
      instruments: selected.length ? selected : null,
      init_capital: parseFloat(document.getElementById("m2-capital").value),
      fee: parseFloat(document.getElementById("m2-fee").value),
    });

    status.className = "status";
    if (!data.ok) {
      status.textContent = "";
      errBox.hidden = false;
      errBox.textContent = "错误：" + data.error;
      return;
    }
    status.textContent = `✅ 回测完成（${data.metrics.n_instruments} 个品种，耗时 ${data.meta.elapsed_ms}ms）`;

    const m = data.metrics;
    const pct = (x) => (x * 100).toFixed(2) + "%";
    metricsBox.innerHTML =
      metricCard("总收益", pct(m.total_return), "ret") +
      metricCard("年化收益", pct(m.annual_return), "ret") +
      metricCard("年化波动", pct(m.annual_volatility)) +
      metricCard("Sharpe", m.sharpe, "ret") +
      metricCard("最大回撤", pct(m.max_drawdown), "neg") +
      metricCard("胜率", pct(m.win_rate)) +
      metricCard("交易次数", m.total_trades);

    const img = document.createElement("img");
    img.src = "data:image/png;base64," + data.image;
    imageBox.appendChild(img);

    // 品种明细表
    let html = `<div class="tbl-title">各品种明细</div><table><thead><tr>
      <th>品种</th><th>总收益</th><th>最大回撤</th><th>交易次数</th><th>胜率</th><th>盈亏比</th>
      </tr></thead><tbody>`;
    data.per_instrument.forEach((p) => {
      html += `<tr><td>${p.instrument}</td><td>${pct(p.total_return)}</td><td>${pct(p.max_drawdown)}</td>
        <td>${p.n_trades}</td><td>${pct(p.win_rate)}</td><td>${p.profit_factor === null ? "∞" : p.profit_factor}</td></tr>`;
    });
    tableBox.innerHTML = html + "</tbody></table>";
  } catch (e) {
    status.className = "status";
    status.textContent = "";
    errBox.hidden = false;
    errBox.textContent = "请求失败：" + e;
  } finally {
    btn.disabled = false;
  }
}
