export function decimalUnits(value, places) {
  const text = String(value).trim().replace(',', '.');
  if (!/^\d+(\.\d+)?$/.test(text)) throw new Error('Valor numérico inválido.');
  const [whole, fraction = ''] = text.split('.');
  if (fraction.slice(places).replace(/0/g, '')) throw new Error('Precisão decimal não suportada.');
  const result = Number(whole) * 10 ** places + Number(fraction.slice(0, places).padEnd(places, '0'));
  if (!Number.isSafeInteger(result)) throw new Error('Valor fora do limite.');
  return result;
}
export function lineCents(priceMilli, quantity) {
  if (!Number.isSafeInteger(quantity) || quantity < 0 || !Number.isSafeInteger(priceMilli * quantity)) throw new Error('Quantidade inválida.');
  return Math.floor((priceMilli * quantity + 5) / 10);
}
export function money(cents) { return (cents / 100).toFixed(2); }
