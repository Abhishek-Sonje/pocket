const $ = id => document.getElementById(id);
let group = '', members = [], expenseOffset = 0, settlementOffset = 0, loading = false;
const pageSize = 10;
const retry = {expense: null, settlement: null};

function notify(message, failed = false) {
  $('message').textContent = message;
  $('message').dataset.error = String(failed);
}

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: encodeJson(body)
  });
  const data = parseExactJson(await response.text());
  if (!response.ok) {
    const problem = data.error;
    throw new Error(problem ? problem.message + (problem.details || []).map(d => ` ${d.field}: ${d.message}`).join('') : 'Request failed. Try again.');
  }
  return data;
}

function label(user) { return `${user.name} (#${user.user_id || user.id})`; }
function person(id) { return label(members.find(user => user.user_id === String(id)) || {name: 'Member', id}); }
function options(select, users, key = 'user_id') {
  const previous = select.value;
  select.replaceChildren(...users.map(user => new Option(label(user), user[key])));
  if (users.some(user => user[key] === previous)) select.value = previous;
}
function text(tag, value, className) {
  const element = document.createElement(tag);
  element.textContent = value;
  if (className) element.className = className;
  return element;
}

async function loadPeople() {
  const users = await api('/users');
  options($('user'), users.filter(user => !members.some(member => member.user_id === user.id)), 'id');
}

async function loadGroups(selected = group) {
  const groups = await api('/groups');
  options($('group'), groups, 'id');
  if (groups.some(item => item.id === selected)) $('group').value = selected;
  await changeGroup();
}

async function changeGroup() {
  group = $('group').value;
  expenseOffset = settlementOffset = 0;
  retry.expense = retry.settlement = null;
  $('workspace').hidden = !group;
  if (!group) { members = []; await loadPeople(); return; }
  members = await api(`/groups/${group}/members`);
  for (const id of ['recorder', 'payer', 'sender', 'recipient']) options($(id), members);
  $('member-list').textContent = members.length ? members.map(label).join(' · ') : 'No members yet. Create a person, then add them to this group.';
  $('participants').replaceChildren(...members.map(user => {
    const row = document.createElement('label');
    const check = document.createElement('input');
    check.type = 'checkbox'; check.value = user.user_id; check.defaultChecked = true;
    row.append(check, document.createTextNode(label(user)));
    return row;
  }));
  $('expense-save').disabled = $('settlement-save').disabled = !members.length;
  await Promise.all([loadPeople(), refresh()]);
}

async function refresh() {
  const selected = group;
  const [summary, expenses, settlements] = await Promise.all([
    api(`/groups/${selected}/balances`),
    api(`/groups/${selected}/expenses?limit=${pageSize}&offset=${expenseOffset}`),
    api(`/groups/${selected}/settlements?limit=${pageSize}&offset=${settlementOffset}`)
  ]);
  if (group !== selected) return;
  $('total').textContent = money(summary.total_expenses_paise);
  $('outstanding').textContent = money(summary.total_outstanding_paise);
  $('balances').replaceChildren(...summary.members.map(member => {
    const row = document.createElement('tr');
    row.append(text('td', label(member)), ...['paid_paise', 'share_paise', 'repayments_sent_paise', 'repayments_received_paise', 'net_balance_paise'].map(key => text('td', money(member[key]))));
    return row;
  }));
  $('suggestions').replaceChildren(...summary.suggested_payments.map(payment => {
    const row = document.createElement('div'); row.className = 'suggestion';
    const button = text('button', 'Use amount', 'quiet'); button.type = 'button';
    button.addEventListener('click', () => {
      $('sender').value = payment.from_user; $('recipient').value = payment.to_user;
      $('settlement-form').elements.amount.value = paiseToRupees(payment.amount_paise);
      retry.settlement = null;
      $('settlement-form').elements.amount.focus();
      notify('Repayment filled in. Save only after the money has been paid.');
    });
    row.append(text('span', `${person(payment.from_user)} pays ${person(payment.to_user)} ${money(payment.amount_paise)}`), button);
    return row;
  }));
  if (!summary.suggested_payments.length) $('suggestions').append(text('p', members.length ? 'Nothing left to settle.' : 'Add members to begin.', 'muted'));
  renderHistory('expense', expenses, expenseOffset);
  renderHistory('settlement', settlements, settlementOffset);
}

function renderHistory(kind, page, offset) {
  $(kind + '-history').replaceChildren(...page.items.map(item => {
    const row = document.createElement('div'); row.className = 'history-row';
    if (kind === 'expense') {
      row.append(text('strong', `${item.description} · ${money(item.amount_paise)}`),
        text('p', `Paid by ${person(item.paid_by)}`),
        text('small', item.shares.map(share => `${person(share.user_id)}: ${money(share.share_paise)}`).join(' · ')));
    } else row.append(text('strong', `${person(item.from_user)} paid ${person(item.to_user)} ${money(item.amount_paise)}`));
    row.append(text('small', `Added by ${person(item.recorded_by)} · ${new Date(item.created_at).toLocaleString()}`));
    return row;
  }));
  if (!page.items.length) $(kind + '-history').append(text('p', `No ${kind === 'expense' ? 'expenses' : 'repayments'} recorded yet.`, 'muted'));
  $(kind + '-page').textContent = `${page.total === '0' ? 0 : offset + 1}–${offset + page.items.length} of ${page.total}`;
  $(kind + '-prev').disabled = offset === 0;
  $(kind + '-next').disabled = BigInt(offset + page.items.length) >= BigInt(page.total);
}

function recordBody(kind, form) {
  if (!group || !$('recorder').value) throw new Error('Choose a group with members first.');
  const body = {recorded_by: BigInt($('recorder').value), amount_paise: rupeesToPaise(form.elements.amount.value)};
  if (kind === 'expense') {
    body.description = form.elements.description.value.trim();
    body.paid_by = BigInt($('did-pay').value === 'yes' ? $('recorder').value : $('payer').value);
    body.participant_ids = [...$('participants').querySelectorAll('input:checked')].map(input => BigInt(input.value));
    if (!body.participant_ids.length) throw new Error('Select at least one person who shared the expense.');
  } else {
    body.from_user = BigInt($('sender').value); body.to_user = BigInt($('recipient').value);
    if (body.from_user === body.to_user) throw new Error('Choose different sender and recipient members.');
  }
  return body;
}

function bindForm(id, handler) {
  $(id).addEventListener('submit', async event => {
    event.preventDefault();
    if (loading) return;
    loading = true;
    const controls = [...event.currentTarget.querySelectorAll('button, input, select'), $('group'), $('recorder')];
    const disabled = controls.map(control => control.disabled);
    controls.forEach(control => { control.disabled = true; });
    try { await handler(event.currentTarget); }
    catch (error) { notify(error.message, true); }
    finally {
      controls.forEach((control, index) => { if (control.isConnected) control.disabled = disabled[index]; });
      loading = false;
    }
  });
}

bindForm('group-form', async form => {
  const created = await api('/groups', {name: form.elements.name.value});
  form.reset(); await loadGroups(created.id); notify('Group created. Add people to begin.');
});
bindForm('user-form', async form => {
  await api('/users', {name: form.elements.name.value});
  form.reset(); await loadPeople(); notify('Person created. Add them to your group below.');
});
bindForm('member-form', async () => {
  if (!group || !$('user').value) throw new Error('Choose a group and an existing person first.');
  await api(`/groups/${group}/members`, {user_id: BigInt($('user').value)});
  await changeGroup(); notify('Person added to the group.');
});
for (const kind of ['expense', 'settlement']) {
  bindForm(kind + '-form', async form => {
    const body = recordBody(kind, form);
    const signature = group + ':' + encodeJson(body);
    if (!retry[kind] || retry[kind].signature !== signature) retry[kind] = {signature, id: crypto.randomUUID()};
    body.request_id = retry[kind].id;
    await api(`/groups/${group}/${kind === 'expense' ? 'expenses' : 'settlements'}`, body);
    retry[kind] = null;
    form.reset();
    if (kind === 'expense') $('payer-label').hidden = true;
    expenseOffset = settlementOffset = 0;
    notify(kind === 'expense' ? 'Expense saved.' : 'Repayment recorded.');
    try { await refresh(); } catch { notify('Saved successfully. Reload the page to see updated balances.', true); }
  });
  for (const event of ['input', 'change']) $(kind + '-form').addEventListener(event, () => { retry[kind] = null; });
  for (const direction of ['prev', 'next']) $(kind + '-' + direction).addEventListener('click', async () => {
    if (loading) return;
    const delta = direction === 'next' ? pageSize : -pageSize;
    if (kind === 'expense') expenseOffset += delta; else settlementOffset += delta;
    try { await refresh(); } catch (error) { notify(error.message, true); }
  });
}
$('recorder').addEventListener('change', () => { retry.expense = retry.settlement = null; });
$('did-pay').addEventListener('change', () => { $('payer-label').hidden = $('did-pay').value === 'yes'; });
$('clear-participants').addEventListener('click', () => {
  $('participants').querySelectorAll('input').forEach(input => { input.checked = false; }); retry.expense = null;
});
$('group').addEventListener('change', () => { changeGroup().catch(error => notify(error.message, true)); });
loadGroups().catch(error => notify(error.message, true));
