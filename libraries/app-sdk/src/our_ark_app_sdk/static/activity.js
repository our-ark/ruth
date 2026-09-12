/** Optional UAAP context-presence/1 reporter for an authenticated app session. */
export class ActivityReporter {
  constructor({request, sessionId, context, storage = sessionStorage, doc = document, win = window}) {
    Object.assign(this, {request, sessionId, context, storage, doc, win});
    this.key = `ark-activity-sequence:${sessionId}`;
    this.latest = {};
    this.onChange = () => this.update();
    this.onHide = () => this.presence("inactive");
  }

  start() {
    this.stopped = false;
    this.doc.addEventListener("visibilitychange", this.onChange);
    for (const event of ["focus", "blur", "pageshow"]) this.win.addEventListener(event, this.onChange);
    this.win.addEventListener("pagehide", this.onHide);
    this.update();
    this.timer = this.win.setInterval(() => {
      if (this.active()) this.update();
      else if (this.lastPresence !== "inactive") this.presence("inactive");
    }, 15000);
  }

  active() { return this.doc.visibilityState === "visible" && this.doc.hasFocus(); }

  async publish(type, fields) {
    if (this.stopped) return false;
    const sequence = Number(this.storage.getItem(this.key) || 0) + 1;
    this.storage.setItem(this.key, String(sequence));
    this.latest[type] = sequence;
    try {
      const result = await this.request("/ui/activity", {
        event_id: crypto.randomUUID(), session_id: this.sessionId, type, sequence, ...fields,
      });
      return result.accepted && this.latest[type] === sequence;
    } catch {
      // A fresh heartbeat renews presence; failed context is resent on update.
      return false;
    }
  }

  async presence(state) {
    if (await this.publish("presence.updated", {state})) this.lastPresence = state;
  }

  async contextChanged() {
    const context = structuredClone(this.context());
    const signature = JSON.stringify(context);
    if (signature === this.lastContext) return;
    if (await this.publish("context.updated", {context})) this.lastContext = signature;
  }

  update() {
    this.presence(this.active() ? "active" : "inactive");
    this.contextChanged();
  }

  stop() {
    this.presence("inactive");
    this.stopped = true;
    this.win.clearInterval(this.timer);
    this.doc.removeEventListener("visibilitychange", this.onChange);
    for (const event of ["focus", "blur", "pageshow"]) this.win.removeEventListener(event, this.onChange);
    this.win.removeEventListener("pagehide", this.onHide);
  }
}
