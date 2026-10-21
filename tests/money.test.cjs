const assert = require('node:assert/strict');
const {parseExactJson, encodeJson, rupeesToPaise, paiseToRupees} = require('../app/static/money.js');
assert.equal(rupeesToPaise('92233720368547758.07'), 9223372036854775807n);
assert.equal(paiseToRupees(-1n), '-0.01');
for (const value of ['0', '-1', '1.001', '1e2', '92233720368547758.08']) assert.throws(() => rupeesToPaise(value));
const exact = '{"amount":9223372036854775807,"description":' + JSON.stringify('dinner 123 "quoted"') + '}';
assert.deepEqual(parseExactJson(exact), {amount: '9223372036854775807', description: 'dinner 123 "quoted"'});
assert.equal(encodeJson({amount_paise: 9223372036854775807n, name: 'Dinner'}), '{"amount_paise":9223372036854775807,"name":"Dinner"}');
console.log('Exact money conversion and JSON checks passed.');
