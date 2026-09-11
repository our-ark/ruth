import "/sdk/agent-chat.js";
import {orderButtonState} from "/sdk/order-state.js";

const chat = document.querySelector("agent-chat");
const productSelect = document.querySelector("#product");
const sizeSelect = document.querySelector("#size");
const orderButton = document.querySelector("#order");
const orderHistory = document.querySelector("#order-history");
const money = cents => new Intl.NumberFormat("en-US", {style:"currency", currency:"USD"}).format(cents / 100);
let selected, revision;
function updateOrderButton() {
  if (!selected) return;
  const state = orderButtonState(chat.transcript, selected.id, sizeSelect.value, chat.sending);
  orderButton.disabled = state.disabled;
  orderButton.textContent = state.text;
  orderButton.title = state.title;
  orderHistory.textContent = state.notice;
  orderHistory.hidden = !state.notice;
}
chat.addEventListener("agent-transcript", updateOrderButton);
chat.addEventListener("agent-send-state", updateOrderButton);
const response = await fetch("/products");
if (!response.ok) throw new Error("The catalog is unavailable");
const {products} = await response.json();
for (const product of products) {
  const option = document.createElement("option"); option.value = product.id; option.textContent = product.name;
  productSelect.append(option);
}
function render() {
  const size = sizeSelect.value;
  selected = products.find(p => p.id === productSelect.value) || products[0];
  revision = crypto.randomUUID();
  document.querySelector("#product-name").textContent = selected.name;
  document.querySelector("#price").textContent = money(selected.price_cents);
  document.querySelector("#description").textContent = selected.description;
  document.querySelector("#fit").textContent = `${selected.fit} fit · ${selected.cushioning} cushioning`;
  sizeSelect.replaceChildren();
  for (const value of selected.sizes) {
    const option = document.createElement("option"); option.value = value; option.textContent = value; sizeSelect.append(option);
  }
  sizeSelect.value = selected.sizes.includes(size) ? size : selected.sizes.includes("9") ? "9" : selected.sizes[0];
  document.querySelector("#total").textContent = `${money(selected.total_cents)} with mock tax · Shipping included`;
  history.replaceState(null, "", `/?product=${selected.id}${location.hash}`);
  updateOrderButton();
}
const requested = new URLSearchParams(location.search).get("product");
if (products.some(p => p.id === requested)) productSelect.value = requested;
render();
productSelect.addEventListener("change", render);
sizeSelect.addEventListener("change", () => { revision = crypto.randomUUID(); updateOrderButton(); });
chat.contextProvider = () => ({revision, page_type:"product", product_id:selected.id, selected_size:sizeSelect.value});
orderButton.addEventListener("click", () => {
  if (orderButton.disabled) return;
  const state = orderButtonState(chat.transcript, selected.id, sizeSelect.value, chat.sending);
  const item = state.repeat ? "another pair of this product" : "this pair";
  chat.input.value = `Please place a simulated order for ${item} in US ${sizeSelect.value}, quantity 1, up to ${money(selected.total_cents)} total.`;
  chat.send(chat.input.value);
});
chat.addEventListener("agent-context", ({detail}) => {
  const box = document.querySelector("#preferences");
  const parts = [detail.budget_cents !== undefined ? `Budget ${money(detail.budget_cents)}` : "", detail.size ? `US ${detail.size}` : "", detail.purpose || ""].filter(Boolean);
  box.textContent = `Your shopping preferences · ${parts.join(" / ")}`;
  box.hidden = !parts.length;
});
