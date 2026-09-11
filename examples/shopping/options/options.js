const button = document.querySelector("#open-all");
const status = document.querySelector("#status");
const help = document.querySelector("#help");
let options = [], windows = new Map();

function remaining() {
  return options.map((_, i) => i).filter(i => !windows.has(i) || windows.get(i).closed);
}

function openOption(index) {
  // Open synchronously during the click. Detach opener before visiting any store.
  const tab = window.open("about:blank", "_blank");
  if (!tab) return false;
  try {
    tab.opener = null;
    tab.location.replace(options[index].url);
    windows.set(index, tab);
    return true;
  } catch {
    tab.close();
    return false;
  }
}

function openAll() {
  for (const index of remaining()) openOption(index);
  const left = remaining().length;
  const opened = options.length - left;
  status.textContent = left
    ? `${opened} of ${options.length} product tabs opened. Your browser may require permission to open multiple tabs.`
    : `All ${options.length} product tabs are open. Switch between stores and keep talking with Ruth.`;
  help.hidden = left === 0;
  button.disabled = left === 0;
  button.textContent = left ? `Open remaining products (${left}) ↗` : "All product tabs opened ✓";
}
button.addEventListener("click", openAll);
window.addEventListener("focus", () => {
  if (options.length && remaining().length) {
    button.disabled = false;
    button.textContent = `Open remaining products (${remaining().length}) ↗`;
  }
});

function validate(payload, origins) {
  if (payload.version !== 1 || !Array.isArray(payload.options) || !payload.options.length || payload.options.length > 6) throw Error();
  return payload.options.map(p => {
    const url = new URL(p.url);
    if (!origins.includes(url.origin) || url.username || url.password || url.pathname !== "/" || !url.searchParams.has("product")) throw Error();
    if (typeof p.name !== "string" || p.name.length > 200 || typeof p.store !== "string" || p.store.length > 100) throw Error();
    if (![p.price_cents, p.total_cents].every(n => Number.isSafeInteger(n) && n >= 0 && n <= 100000000)) throw Error();
    const image = p.image ? new URL(p.image) : null;
    if (image && (image.origin !== url.origin || image.username || image.password || image.hash)) throw Error();
    return {...p, url: url.href, image: image?.href || ""};
  });
}

function render() {
  const money = cents => new Intl.NumberFormat("en-US", {style: "currency", currency: "USD"}).format(cents / 100);
  const container = document.querySelector("#products");
  container.replaceChildren();
  for (const [index, p] of options.entries()) {
    const card = document.createElement("article"); card.className = "product";
    // The template is fixed; all payload strings below use textContent or validated URLs.
    card.innerHTML = '<div class="photo"><span class="number"></span></div><div class="details"><p class="store"></p><h2></h2><p class="price"></p><p class="total"></p><a target="_blank" rel="noopener noreferrer"><span>Open product</span><span aria-hidden="true">↗</span></a></div>';
    card.querySelector(".number").textContent = index + 1;
    if (p.image) {
      const image = document.createElement("img"); image.src = p.image; image.alt = p.name; image.referrerPolicy = "no-referrer";
      card.querySelector(".photo").prepend(image);
    }
    card.querySelector(".store").textContent = p.store;
    card.querySelector("h2").textContent = p.name;
    card.querySelector(".price").textContent = money(p.price_cents);
    card.querySelector(".total").textContent = `${money(p.total_cents)} total · mock tax included`;
    const link = card.querySelector("a"); link.href = p.url;
    link.setAttribute("aria-label", `Open option ${index + 1}: ${p.name} in a new tab`);
    link.addEventListener("click", event => {
      if (event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      if (!openOption(index)) { help.hidden = false; status.textContent = "This tab was blocked. Allow pop-ups, or use your browser's Open Link in New Tab command."; }
    });
    container.append(card);
  }
  document.querySelector("#count").textContent = `${options.length} products · ${new Set(options.map(p => new URL(p.url).origin)).size} stores`;
  button.disabled = false;
}

async function load() {
  try {
    const encoded = new URLSearchParams(location.hash.slice(1)).get("options");
    const data = encoded || sessionStorage.getItem("ruth-options");
    if (!data) return;
    if (data.length > 20000) throw Error();
    // Remove browser account links from the address bar before loading any assets.
    history.replaceState(null, "", location.pathname);
    const bytes = Uint8Array.from(atob(data.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0));
    const config = await fetch("/config.json", {credentials: "omit"}).then(r => r.json());
    options = validate(JSON.parse(new TextDecoder().decode(bytes)), config.origins);
    windows = new Map();
    sessionStorage.setItem("ruth-options", data);
    render();
    // A deep link explicitly asks to open this shortlist. Browsers may block this;
    // the visible button supplies a user gesture and links always remain available.
    if (encoded) openAll();
    else status.textContent = "Your shortlist is ready. Open all products, or choose a product below.";
  } catch {
    status.textContent = "This shortlist link is invalid. Open a fresh View all options link from Ruth.";
    button.disabled = true;
  }
}
window.addEventListener("hashchange", () => {
  if (new URLSearchParams(location.hash.slice(1)).has("options")) load();
});
load();
