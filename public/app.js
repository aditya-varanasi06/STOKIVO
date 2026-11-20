const state = { products: [], search: "", lowOnly: false, view: "overview", dashboard: null, report: null, period: "month" };
const $ = (s) => document.querySelector(s), $$ = (s) => [...document.querySelectorAll(s)];
const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const precise = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const number = new Intl.NumberFormat("en-IN");
const dt = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
async function api(url, options) {
  const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Something went wrong. Please try again.");
  return data;
}
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[c]); }
function color(s) { return "color-" + [...String(s || "")].reduce((n, c) => n + c.charCodeAt(0), 0) % 5; }
function when(s) { if (!s) return "—"; const d = new Date(String(s).includes("T") ? s : String(s).replace(" ", "T") + "Z"); return isNaN(d) ? s : dt.format(d); }
function toast(s) { const t = $("#toast"); t.textContent = s; t.classList.add("show"); clearTimeout(state.toastTimer); state.toastTimer = setTimeout(() => t.classList.remove("show"), 2800); }
function cellProduct(name) { return '<div class="table-product"><span class="product-thumb ' + color(name) + '">' + esc((name || "?")[0].toUpperCase()) + '</span><strong>' + esc(name) + "</strong></div>"; }
function emptyRow(n, title, msg) { return '<tr><td colspan="' + n + '"><div class="empty-state"><strong>' + esc(title) + "</strong>" + esc(msg) + "</div></td></tr>"; }
function view(name) {
  state.view = name;
  $$(".page-view").forEach((e) => e.classList.toggle("active", e.id === name + "View"));
  $$(".nav-item").forEach((e) => e.classList.toggle("active", e.dataset.view === name));
  $("#breadcrumbCurrent").textContent = { overview: "Overview", inventory: "Inventory", sales: "Sales", reports: "Reports" }[name];
  if (name === "inventory") products();
  if (name === "sales") sales();
  if (name === "reports") report();
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function dashboardUI(d) {
  state.dashboard = d;
  $("#currentDate").textContent = new Intl.DateTimeFormat("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(new Date()).toUpperCase();
  const h = new Date().getHours();
  $("#overviewView h1").childNodes[0].textContent = h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
  $("#todayRevenue").textContent = money.format(d.today.revenue); $("#todayProfit").textContent = money.format(d.today.profit);
  $("#todayOrders").textContent = d.today.orders + (d.today.orders === 1 ? " order" : " orders");
  $("#todayUnits").textContent = d.today.units + (d.today.units === 1 ? " unit sold" : " units sold");
  $("#inventoryUnits").textContent = number.format(d.units_in_stock);
  $("#productCount").textContent = number.format(d.product_count) + " products";
  $("#navProductCount").textContent = d.product_count;
  $("#lowStockCount").textContent = d.low_stock.length; $("#stockWatchCount").textContent = d.low_stock.length;
  $("#alertDot").classList.toggle("show", d.low_stock.length > 0);
  $("#weekRevenue").textContent = money.format(d.week_series.reduce((n, r) => n + r.revenue, 0));
  $("#stockWatchList").innerHTML = d.low_stock.length ? d.low_stock.slice(0, 4).map((p) =>
    '<div class="stock-item"><span class="product-thumb ' + color(p.name) + '">' + esc(p.name[0].toUpperCase()) +
    '</span><div class="stock-copy"><strong>' + esc(p.name) + '</strong><span>' + esc(p.category) +
    " · Reorder at " + p.min_stock + '</span></div><span class="stock-level ' + (p.stock ? "" : "out") +
    '">' + (p.stock ? p.stock + " left" : "Out of stock") + "</span></div>"
  ).join("") : '<div class="empty-state"><strong>All stocked up.</strong>No products need attention right now.</div>';
  $("#recentSalesBody").innerHTML = d.recent_sales.length ? d.recent_sales.map((s) =>
    "<tr><td>" + cellProduct(s.product_name) + '<td><span class="table-subtext">' + esc(when(s.sold_at)) +
    "</span><td>" + s.quantity + '<td class="profit-positive">' + precise.format(s.profit) +
    '<td class="align-right"><strong>' + precise.format(s.total) + "</strong></tr>"
  ).join("") : emptyRow(5, "No sales recorded yet.", "Once you record a sale, it will show up here.");
  chart($("#salesChart"), d.week_series, "week");
}
function chart(canvas, rows, period) {
  const box = canvas?.getBoundingClientRect(); if (!box?.width || !box.height) return;
  const ratio = devicePixelRatio || 1; canvas.width = box.width * ratio; canvas.height = box.height * ratio;
  const c = canvas.getContext("2d"); c.scale(ratio, ratio); c.clearRect(0, 0, box.width, box.height);
  const left = 5, top = 7, bottom = 20, plotH = box.height - top - bottom, plotW = box.width - 9;
  let data = rows;
  if (period === "week") {
    const today = new Date(), start = new Date(today); start.setDate(today.getDate() - 6);
    data = Array.from({ length: 7 }, (_, i) => {
      const d = new Date(start); d.setDate(start.getDate() + i);
      const key = [d.getFullYear(), String(d.getMonth() + 1).padStart(2, "0"), String(d.getDate()).padStart(2, "0")].join("-");
      const r = rows.find((x) => x.label === key);
      return { label: new Intl.DateTimeFormat("en-IN", { weekday: "short" }).format(d), revenue: r?.revenue || 0, profit: r?.profit || 0 };
    });
  }
  const max = Math.max(2500, Math.ceil(Math.max(...data.map((x) => x.revenue), 0) / 2500) * 2500);
  for (let i = 0; i < 5; i++) { c.beginPath(); c.strokeStyle = "#edf0ef"; c.setLineDash([3, 4]); c.moveTo(left, top + plotH * i / 4); c.lineTo(left + plotW, top + plotH * i / 4); c.stroke(); }
  c.setLineDash([]);
  const group = plotW / Math.max(data.length, 1), bar = Math.min(12, group * .23);
  data.forEach((r, i) => {
    const x = left + group * (i + .5), a = Math.max(2, r.revenue / max * plotH), b = r.profit > 0 ? Math.max(2, r.profit / max * plotH) : 0;
    barRect(c, x - bar - 1, top + plotH - a, bar, a, "#85a8e8");
    if (b) barRect(c, x + 1, top + plotH - b, bar, b, "#80d2aa");
    c.fillStyle = "#aab2b0"; c.font = '9px "DM Sans", sans-serif'; c.textAlign = "center";
    c.fillText(period === "month" ? r.label.slice(8) : period === "year" ? r.label.slice(5) : r.label, x, box.height - 4);
  });
}
function barRect(c, x, y, w, h, fill) { const r = Math.min(3, w / 2, h / 2); c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); c.fillStyle = fill; c.fill(); }
async function refresh() {
  try {
    dashboardUI(await api("/api/dashboard"));
    $("#connectionStatus").innerHTML = "<i></i> Connected";
  } catch (e) {
    $("#connectionStatus").innerHTML = '<i style="background:#df897e"></i> Connection issue';
    $("#connectionStatus").title = e.message;
    $("#stockWatchList").innerHTML = '<div class="error-state"><strong>Could not reach your store.</strong>Check your database connection and refresh.</div>';
  }
}
async function products() {
  try { state.products = await api("/api/products" + (state.search ? "?search=" + encodeURIComponent(state.search) : "")); renderProducts(); }
  catch (e) { $("#productsBody").innerHTML = emptyRow(7, "Couldn't load inventory.", e.message); }
}
function renderProducts() {
  const all = state.products, shown = state.lowOnly ? all.filter((p) => p.stock <= p.min_stock) : all;
  const out = all.filter((p) => !p.stock).length, low = all.filter((p) => p.stock && p.stock <= p.min_stock).length;
  $("#inventorySummary").innerHTML = "<span><i></i><strong>" + all.length + "</strong> total products</span><span><strong>" + all.reduce((a, p) => a + p.stock, 0) + "</strong> units on hand</span><span><strong style=\"color:#ca8450\">" + low + "</strong> low stock</span><span><strong style=\"color:#c96f68\">" + out + "</strong> out of stock</span>";
  $("#inventoryResultCount").textContent = shown.length + " products"; $("#inventoryFooter").textContent = "Showing " + shown.length + " of " + all.length + " products";
  $("#stockFilter").classList.toggle("selected", state.lowOnly);
  $("#productsBody").innerHTML = shown.length ? shown.map((p) => {
    const status = !p.stock ? "out" : p.stock <= p.min_stock ? "low" : "";
    return "<tr><td>" + cellProduct(p.name) + "<td>" + esc(p.sku) + "<td>" + esc(p.category) +
      '<td><strong>' + precise.format(p.price) + '</strong><span class="table-subtext">Cost ' + precise.format(p.cost_price) +
      '</span><td class="stock-cell">' + p.stock + ' <span class="table-subtext" style="display:inline">/ ' + p.min_stock +
      ' min</span><td><span class="status-badge ' + status + '"><i></i>' + (!p.stock ? "Out of stock" : status ? "Low stock" : "In stock") +
      '</span><td><div class="row-actions"><button class="row-action" title="Edit product" data-edit="' + p.id +
      '">✎</button><button class="row-action" title="Delete product" data-delete="' + p.id + '">×</button></div>';
  }).join("") : emptyRow(7, state.lowOnly ? "No low stock items." : "Your inventory is ready.", state.lowOnly ? "Everything is above its reorder point." : "Add your first product to keep track of stock.");
  $("#productsBody [data-edit]").forEach((b) => b.onclick = () => productModal(+b.dataset.edit));
  $("#productsBody [data-delete]").forEach((b) => b.onclick = () => removeProduct(+b.dataset.delete));
  $("#navProductCount").textContent = all.length;
}
async function sales() {
  try {
    const [items, r] = await Promise.all([api("/api/sales?limit=100"), api("/api/reports?period=month")]);
    $("#monthRevenue").textContent = money.format(r.summary.revenue); $("#monthProfit").textContent = money.format(r.summary.profit);
    $("#monthOrders").textContent = number.format(r.summary.orders); $("#monthUnits").textContent = number.format(r.summary.units);
    $("#allSalesBody").innerHTML = items.length ? items.map((s) =>
      "<tr><td>" + cellProduct(s.product_name) + '<td><span class="table-subtext">' + esc(when(s.sold_at)) +
      "</span><td>" + precise.format(s.unit_price) + "<td>" + s.quantity + '<td class="profit-positive">' +
      precise.format(s.profit) + '<td class="align-right"><strong>' + precise.format(s.total) + "</strong>"
    ).join("") : emptyRow(6, "No transactions yet.", "Your sales history will appear here.");
  } catch (e) { $("#allSalesBody").innerHTML = emptyRow(6, "Couldn't load sales.", e.message); }
}
async function report() {
  const period = $("#reportPeriod").value; state.period = period;
  try {
    const r = state.report = await api("/api/reports?period=" + period);
    $("#reportRevenue").textContent = money.format(r.summary.revenue); $("#reportProfit").textContent = money.format(r.summary.profit);
    $("#reportOrders").textContent = number.format(r.summary.orders); $("#reportUnits").textContent = number.format(r.summary.units);
    $("#reportChartSubtitle").textContent = { today: "Daily performance today", week: "Daily performance over the last 7 days", month: "Daily performance this month", year: "Monthly performance this year" }[period];
    chart($("#reportChart"), r.series, period);
    $("#topProductsList").innerHTML = r.top_products.length ? r.top_products.map((p, i) =>
      '<div class="top-product-row"><span class="top-product-rank">' + String(i + 1).padStart(2, "0") +
      '</span><div class="top-product-name"><strong>' + esc(p.name) + "</strong><span>" + p.units +
      ' units sold</span></div><div class="top-product-value">' + precise.format(p.revenue) +
      '<span class="profit-positive">' + precise.format(p.profit) + " profit</span></div></div>"
    ).join("") : '<div class="empty-state"><strong>No sales in this period.</strong>Top products will appear when you record sales.</div>';
  } catch (e) { $("#topProductsList").innerHTML = '<div class="empty-state"><strong>Report unavailable.</strong>' + esc(e.message) + "</div>"; }
}
function modal(id) { $("#" + id).classList.add("open"); $("#" + id).setAttribute("aria-hidden", "false"); document.body.style.overflow = "hidden"; }
function close() { $$(".modal-backdrop").forEach((e) => { e.classList.remove("open"); e.setAttribute("aria-hidden", "true"); }); document.body.style.overflow = ""; }
function productModal(id) {
  const p = id ? state.products.find((x) => x.id === id) : null, f = $("#productForm"); f.reset();
  $("#productError").textContent = ""; $("#productId").value = p?.id || "";
  $("#productModalTitle").textContent = p ? "Edit product" : "Add a product"; $("#saveProductButton").textContent = p ? "Save changes" : "Save product";
  $("#productName").value = p?.name || ""; $("#productSku").value = p?.sku || ""; $("#productCategory").value = p?.category || "";
  $("#productPrice").value = p?.price ?? ""; $("#productCost").value = p?.cost_price ?? ""; $("#productStock").value = p?.stock ?? ""; $("#productMinStock").value = p?.min_stock ?? 5;
  modal("productModal");
}
async function saleModal() {
  if (!state.products.length) await products();
  const choices = state.products.filter((p) => p.stock > 0);
  $("#saleForm").reset(); $("#saleQuantity").value = 1; $("#saleError").textContent = "";
  $("#saleProduct").innerHTML = choices.length ? choices.map((p) => '<option value="' + p.id + '">' + esc(p.name) + " · " + p.stock + " in stock · " + precise.format(p.price) + "</option>").join("") : '<option value="">No products in stock</option>';
  $("#saveSaleButton").disabled = !choices.length; $("#saveSaleButton").style.opacity = choices.length ? "1" : ".55";
  modal("saleModal"); preview();
}
function preview() { const p = state.products.find((x) => x.id === +$("#saleProduct").value), qty = Math.max(0, +$("#saleQuantity").value || 0); $("#salePreviewTotal").textContent = precise.format((p?.price || 0) * qty); $("#saleStockHint").textContent = p ? p.stock + " units available" : "Add products to your inventory first."; $("#saleQuantity").max = p?.stock || 1; }
async function removeProduct(id) {
  const p = state.products.find((x) => x.id === id);
  if (!p || !confirm("Remove " + p.name + " from your inventory?")) return;
  try { await api("/api/products/" + id, { method: "DELETE" }); toast("Product removed from inventory."); await Promise.all([products(), refresh()]); }
  catch (e) { toast(e.message); }
}
$$(".nav-item").forEach((b) => b.onclick = () => view(b.dataset.view));
$$("[data-view-link]").forEach((b) => b.onclick = () => view(b.dataset.viewLink));
$$("[data-action='new-product']").forEach((b) => b.onclick = () => productModal());
$$("[data-action='new-sale']").forEach((b) => b.onclick = saleModal);
$$("[data-close-modal]").forEach((b) => b.onclick = close);
$$(".modal-backdrop").forEach((m) => m.onclick = (e) => { if (e.target === m) close(); });
$("#alertsButton").onclick = () => { state.search = ""; $("#globalSearch").value = ""; $("#productSearch").value = ""; state.lowOnly = true; view("inventory"); };
$("#stockFilter").onclick = () => { state.lowOnly = !state.lowOnly; renderProducts(); };
$("#globalSearch").oninput = (e) => { state.search = e.target.value.trim(); state.lowOnly = false; $("#productSearch").value = e.target.value; view("inventory"); clearTimeout(state.searchTimer); state.searchTimer = setTimeout(products, 180); };
$("#productSearch").oninput = (e) => { state.search = e.target.value.trim(); clearTimeout(state.searchTimer); state.searchTimer = setTimeout(products, 180); };
$("#reportPeriod").onchange = report; $("#saleProduct").onchange = preview; $("#saleQuantity").oninput = preview;
$("#productForm").onsubmit = async (e) => {
  e.preventDefault(); const id = $("#productId").value;
  const body = { name: $("#productName").value.trim(), sku: $("#productSku").value.trim(), category: $("#productCategory").value.trim() || "General", price: +$("#productPrice").value, cost_price: +$("#productCost").value, stock: +$("#productStock").value, min_stock: +$("#productMinStock").value };
  $("#productError").textContent = ""; $("#saveProductButton").disabled = true;
  try { await api(id ? "/api/products/" + id : "/api/products", { method: id ? "PUT" : "POST", body: JSON.stringify(body) }); close(); toast(id ? "Product details updated." : "Product added to inventory."); await Promise.all([products(), refresh()]); }
  catch (err) { $("#productError").textContent = err.message; }
  finally { $("#saveProductButton").disabled = false; }
};
$("#saleForm").onsubmit = async (e) => {
  e.preventDefault(); $("#saleError").textContent = ""; $("#saveSaleButton").disabled = true;
  try { const s = await api("/api/sales", { method: "POST", body: JSON.stringify({ product_id: +$("#saleProduct").value, quantity: +$("#saleQuantity").value }) }); close(); toast("Sale recorded · " + precise.format(s.total)); await Promise.all([products(), refresh()]); if (state.view === "sales") await sales(); if (state.view === "reports") await report(); }
  catch (err) { $("#saleError").textContent = err.message; }
  finally { $("#saveSaleButton").disabled = false; }
};
document.onkeydown = (e) => { if (e.key === "Escape") close(); if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); $("#globalSearch").focus(); } };
window.onresize = () => { if (state.dashboard) chart($("#salesChart"), state.dashboard.week_series, "week"); if (state.report) chart($("#reportChart"), state.report.series, state.period); };
refresh();
