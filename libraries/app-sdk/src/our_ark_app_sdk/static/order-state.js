/** Store controls use authoritative receipts and outstanding messages from the SDK. */
export function orderButtonState(transcript, productId, size, sending = false) {
  const outputs = transcript?.outputs || [];
  const order = outputs.map(output => output.order).find(order => order?.status === "confirmed"
    && order.product_id === productId && order.size === size);
  if (order) return {disabled: true, text: "Order confirmed", title: order.order_id};
  const answered = new Set(outputs.map(output => output.in_reply_to));
  const waiting = (transcript?.messages || []).some(event => event.context.product_id === productId
    && event.context.selected_size === size && !answered.has(event.message.id));
  if (sending || waiting) return {disabled: true, text: "Waiting for Ruth…", title: "Your message is being processed."};
  return {disabled: false, text: "Ask Ruth to order", title: ""};
}
