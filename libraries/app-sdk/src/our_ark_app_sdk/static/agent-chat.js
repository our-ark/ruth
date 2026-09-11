/** App-owned UI for one continuing personal-agent conversation.
 * No model client or agent address. Both stores import this exact module.
 */
export class AgentChat extends HTMLElement {
  connectedCallback() {
    if (this.started) return;
    this.started = true;
    this.contextProvider = () => ({});
    this.innerHTML = `<section class="agent-panel" aria-label="Conversation with Ruth">
      <header class="agent-header"><span class="agent-avatar" aria-hidden="true">R</span>
        <div><strong>Ruth</strong><small>Your personal agent · same conversation</small></div>
        <span class="agent-connection" role="status">Connecting…</span></header>
      <div class="agent-messages" role="log" aria-label="Messages" aria-live="polite"></div>
      <form class="agent-form"><label class="agent-share"><input type="checkbox" name="share"> Share my shopping preferences with this store</label>
        <div class="agent-compose"><label class="sr-only" for="agent-input">Message Ruth</label>
          <textarea id="agent-input" name="message" rows="2" maxlength="8000" placeholder="Ask Ruth about this pair…" required></textarea>
          <button type="submit" aria-label="Send message to Ruth">Send</button></div>
        <p class="agent-error" role="alert"></p></form></section>`;
    const appName = this.getAttribute("app-name");
    if (appName) {
      this.querySelector(".agent-header strong").textContent = `Ruth on ${appName}`;
      this.querySelector(".agent-panel").setAttribute("aria-label", `Conversation with Ruth on ${appName}`);
    }
    this.form = this.querySelector("form");
    this.input = this.querySelector("textarea");
    this.messages = this.querySelector(".agent-messages");
    this.status = this.querySelector(".agent-connection");
    this.error = this.querySelector(".agent-error");
    this.form.addEventListener("submit", e => { e.preventDefault(); this.send(this.input.value); });
    this.input.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); this.form.requestSubmit(); }
    });
    this.ready = this.connect();
    this.onHashChange = () => {
      if (new URLSearchParams(location.hash.slice(1)).has("connect")) this.ready = this.connect();
    };
    window.addEventListener("hashchange", this.onHashChange);
  }

  disconnectedCallback() { clearTimeout(this.timer); window.removeEventListener("hashchange", this.onHashChange); }

  async request(path, body) {
    const response = await fetch(path, {method: body ? "POST" : "GET", credentials: "same-origin",
      headers: body ? {"Content-Type": "application/json"} : {}, body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(10000)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The store is unavailable. Try again.");
    return result;
  }

  async connect() {
    clearTimeout(this.timer);
    try {
      const params = new URLSearchParams(location.hash.slice(1));
      const token = params.get("connect");
      if (token) {
        await this.request("/ui/connect", {token});
        history.replaceState(null, "", location.pathname + location.search);
      }
      this.sessionId = sessionStorage.getItem("ark-session");
      if (this.sessionId) {
        // Validate restored sessions; a reset demo can use the same browser.
        try { await this.request(`/ui/transcript?session_id=${this.sessionId}`); }
        catch { this.sessionId = null; }
      }
      if (!this.sessionId) this.sessionId = (await this.request("/ui/sessions", {})).session_id;
      sessionStorage.setItem("ark-session", this.sessionId);
      this.status.textContent = "Connected";
      this.poll();
      return true;
    } catch (error) {
      this.status.textContent = "Not connected";
      this.error.textContent = error.message;
      return false;
    }
  }

  async send(text) {
    text = text.trim();
    if (!text || this.sending) return;
    this.sending = true;
    this.dispatchEvent(new CustomEvent("agent-send-state", {bubbles: true}));
    const button = this.form.querySelector('button[type="submit"]');
    button.disabled = true;
    this.error.textContent = "";
    const snapshot = structuredClone(this.contextProvider());
    try {
      if (!await this.ready) throw new Error("Open a recommendation link from Ruth to connect this store.");
      // Freeze context BEFORE any network wait. Retry uses the identical id and body.
      if (!this.pending) this.pending = {id: crypto.randomUUID(), session_id: this.sessionId, text,
        context: snapshot, share_preferences: this.form.elements.share.checked};
      await this.request("/ui/messages", this.pending);
      this.pending = null;
      this.input.value = "";
      await this.refresh();
    } catch (error) {
      this.error.textContent = `${error.message} Your message is saved here; Send retries the same message.`;
    } finally {
      this.sending = false; button.disabled = false;
      this.dispatchEvent(new CustomEvent("agent-send-state", {bubbles: true}));
    }
  }

  async refresh() {
    const data = await this.request(`/ui/transcript?session_id=${this.sessionId}`);
    const signature = JSON.stringify(data);
    if (this.lastSignature === signature) return;
    this.lastSignature = signature;
    this.transcript = data;
    this.dispatchEvent(new CustomEvent("agent-transcript", {detail: data, bubbles: true}));
    this.messages.replaceChildren();
    if (!data.messages.length) {
      const intro = document.createElement("p");
      intro.className = "agent-empty";
      intro.textContent = "Continue with Ruth here. Ask about this pair, or compare it with the one you saw at another store.";
      this.messages.append(intro);
    }
    for (const event of data.messages) {
      this.bubble("You", event.message.text, "user", event.context.product.name);
      const replies = data.outputs.filter(o => o.in_reply_to === event.message.id);
      for (const output of replies) {
        this.bubble("Ruth", output.text, "ruth");
        if (Object.keys(output.shared_context || {}).length) {
          this.dispatchEvent(new CustomEvent("agent-context", {detail: output.shared_context, bubbles: true}));
        }
      }
      if (!replies.length) this.bubble("Ruth", "Waiting for Ruth…", "waiting");
    }
    this.messages.scrollTop = this.messages.scrollHeight;
  }

  bubble(name, text, kind, context) {
    const item = document.createElement("article"); item.className = `agent-bubble ${kind}`;
    const label = document.createElement("small"); label.textContent = name + (context ? " · " + context : "");
    const body = document.createElement("p");
    // Render text and http(s) links only. Never insert model or app text as HTML.
    const urlPattern = /https?:\/\/[^\s<>]+/g;
    let last = 0;
    for (const match of text.matchAll(urlPattern)) {
      body.append(document.createTextNode(text.slice(last, match.index)));
      const link = document.createElement("a"); link.href = match[0]; link.textContent = "View product";
      link.target = "_blank"; link.rel = "noopener noreferrer"; body.append(link);
      last = match.index + match[0].length;
    }
    body.append(document.createTextNode(text.slice(last)));
    item.append(label, body); this.messages.append(item);
  }

  async poll() {
    if (!this.isConnected) return;
    try { await this.refresh(); this.status.textContent = "Connected"; }
    catch { this.status.textContent = "Reconnecting…"; }
    this.timer = setTimeout(() => this.poll(), 1200);
  }
}
customElements.define("agent-chat", AgentChat);
