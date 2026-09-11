/** Store controls use authoritative receipts and outstanding messages from the SDK. */
export function orderButtonState(transcript, productId, size, sending = false) {
  const outputs = transcript?.outputs || [];
  const order = outputs.map(output => output.order).reverse().find(order => order?.status === "confirmed"
    && order.product_id === productId && order.size === size);
  const notice = order ? `You previously ordered this pair in US ${size} (${order.order_id}). You can order another.` : "";
  const answered = new Set(outputs.map(output => output.in_reply_to));
  const waiting = (transcript?.messages || []).some(event => event.context.product_id === productId
    && event.context.selected_size === size && !answered.has(event.message.id));
  if (sending || waiting) return {disabled: true, text: "Waiting for Ruth…", title: "Your message is being processed.", notice};
  if (order) return {disabled: false, text: "Order another pair", title: order.order_id, repeat: true, notice};
  return {disabled: false, text: "Ask Ruth to order", title: "", notice};
}
