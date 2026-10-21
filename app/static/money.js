/* Preserve all integer JSON tokens before JSON.parse can round them. API numbers are integers. */
function parseExactJson(text) {
  return JSON.parse(text.replace(/("(?:\\.|[^"\\])*")|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (token, quoted) => quoted || JSON.stringify(token)));
}

function encodeJson(value) {
  if (typeof value === 'bigint') return value.toString();
  if (Array.isArray(value)) return '[' + value.map(encodeJson).join(',') + ']';
  if (value !== null && typeof value === 'object') {
    return '{' + Object.entries(value).map(([key, item]) => JSON.stringify(key) + ':' + encodeJson(item)).join(',') + '}';
  }
  return JSON.stringify(value);
}

function rupeesToPaise(value) {
  if (!/^\d+(\.\d{1,2})?$/.test(value)) throw new Error('Enter rupees with at most two decimal places.');
  const [whole, fraction = ''] = value.split('.');
  const amount = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  if (amount <= 0n || amount > 9223372036854775807n) throw new Error('Enter a positive amount within the supported range.');
  return amount;
}

function paiseToRupees(value) {
  let amount = BigInt(value);
  const sign = amount < 0n ? '-' : '';
  if (amount < 0n) amount = -amount;
  return sign + (amount / 100n) + '.' + (amount % 100n).toString().padStart(2, '0');
}

function money(value) { return '₹' + paiseToRupees(value); }

if (typeof module !== 'undefined') module.exports = {parseExactJson, encodeJson, rupeesToPaise, paiseToRupees};
