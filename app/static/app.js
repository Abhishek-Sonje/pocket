const $ = id => document.getElementById(id);
let group = '', groups = [], members = [], loading = false, viewLoading = false, navigation = 0;

function text(tag, value = '', className = '') {
  const element = document.createElement(tag);
  element.textContent = value;
  element.className = className;
  return element;
}
function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  const use = document.createElementNS(svg.namespaceURI, 'use');
  svg.classList.add('icon'); svg.setAttribute('aria-hidden', 'true');
  use.setAttribute('href', '#icon-' + name); svg.append(use);
  return svg;
}
function emptyState(title, detail = '', symbol = 'pocket') {
  const block = text('div', '', 'empty-state');
  block.append(icon(symbol), text('strong', title));
  if (detail) block.append(text('p', detail));
  return block;
}
function label(user, scope = members) {
  return user.name + (scope.filter(item => item.name === user.name).length > 1 ? ' (#' + (user.user_id || user.id) + ')' : '');
}
function member(id) { return members.find(user => user.user_id === String(id)) || {id: String(id), name: 'Member'}; }
function person(id) { return label(member(id)); }
function avatar(user) {
  const initials = user.name.trim().split(/\s+/).slice(0, 2).map(word => [...word][0]).join('').toLocaleUpperCase();
  const node = text('span', initials, 'avatar');
  node.dataset.color = String(BigInt(user.user_id || user.id) % 6n);
  node.setAttribute('aria-hidden', 'true');
  return node;
}
function personNode(user, className = 'person') {
  const node = text('span', '', className);
  node.append(avatar(user), text('span', label(user), 'person-name'));
  return node;
}
function notify(message, failed = false, form) {
  $('message-text').textContent = message;
  $('message').dataset.error = String(failed);
  $('message').hidden = false;
  if (form?.isConnected) {
    let local = form.querySelector('.form-message');
    if (!local) { local = text('p', '', 'form-message'); form.append(local); }
    local.textContent = message; local.dataset.error = String(failed);
  }
}
function readable(message) {
  const names = {recorded_by: 'person entering the record', paid_by: 'payer', from_user: 'sender',
    to_user: 'recipient', amount_paise: 'amount', participant_ids: 'people sharing the expense',
    user_id: 'person', group_id: 'group', net_balance_paise: 'remaining balance'};
  return message.replace(/request ID/gi, 'submission').replace(/request_id/g, 'submission')
    .replace(/\b(recorded_by|paid_by|from_user|to_user|amount_paise|participant_ids|user_id|group_id|net_balance_paise)\b/g, key => names[key])
    .replace(/paise/gi, 'the supported amount');
}
async function api(path, body) {
  let response;
  try {
    response = await fetch(path, body === undefined ? {} : {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: encodeJson(body)
    });
  } catch { throw new Error('Could not connect to Pocket. Check your connection and try again.'); }
  const data = parseExactJson(await response.text());
  if (!response.ok) {
    const problem = data.error;
    throw new Error(problem ? readable(problem.message + (problem.details || []).map(d => ' ' + d.message).join('')) : 'Request failed. Try again.');
  }
  return data;
}
function options(select, people, key = 'user_id', scope = people) {
  const previous = select.value;
  select.replaceChildren(...people.map(user => new Option(label(user, scope), user[key])));
  if (people.some(user => user[key] === previous)) select.value = previous;
}
function syncControls() {
  const selected = $('participants').querySelectorAll('input:checked').length;
  $('expense-save').disabled = loading || viewLoading || !selected;
  $('participant-help').hidden = Boolean(selected);
  $('expense-empty').hidden = Boolean(members.length);
  $('settlement-save').disabled = loading || viewLoading || members.length < 2;
  $('member-form').querySelector('button').disabled = loading || viewLoading || !$('user').value;
  $('group-switcher').disabled = loading;
}
function bindForm(form, handler) {
  for (const event of ['input', 'change']) form.addEventListener(event, () => { form.retry = null; });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (loading || viewLoading) return;
    loading = true;
    const controls = [...document.querySelectorAll('button, input, select')];
    const disabled = controls.map(control => control.disabled);
    controls.forEach(control => { control.disabled = true; });
    form.setAttribute('aria-busy', 'true');
    const submit = event.submitter || form.querySelector('button:not([type]), button[type=submit]');
    const original = submit ? [...submit.childNodes] : [];
    if (submit) submit.replaceChildren(document.createTextNode('Saving...'));
    form.querySelector('.form-message')?.remove();
    try { await handler(form); }
    catch (error) { notify(readable(error.message), true, form); }
    finally {
      controls.forEach((control, index) => { if (control.isConnected) control.disabled = disabled[index]; });
      loading = false; form.removeAttribute('aria-busy');
      if (submit?.isConnected) submit.replaceChildren(...original);
      syncControls();
    }
  });
}
async function loadGroups() {
  try {
    groups = await api('/groups');
    options($('group-switcher'), groups, 'id');
    if (group) $('group-switcher').value = group;
    $('group-list').replaceChildren(...groups.map(item => {
      const button = text('button', '', 'group-link');
      button.type = 'button';
      button.append(icon('pocket'), text('span', label(item, groups), 'person-name'), icon('arrow'));
      button.addEventListener('click', () => { if (!loading) openGroup(item); });
      return button;
    }));
    if (!groups.length) $('group-list').append(emptyState('Create your first group', 'Start with a trip, a home, or a meal together.'));
  } catch (error) {
    $('group-list').replaceChildren(emptyState('Your groups could not load', 'Check your connection, then try again.'));
    const retry = text('button', 'Try again'); retry.type = 'button';
    retry.addEventListener('click', () => loadGroups().catch(error => notify(error.message, true)));
    $('group-list').append(retry);
    throw error;
  } finally { $('group-list').removeAttribute('aria-busy'); }
}
async function loadMembers(highlight = '') {
  const selectedGroup = group, version = navigation;
  const [nextMembers, users] = await Promise.all([api('/groups/' + selectedGroup + '/members'), api('/users')]);
  if (selectedGroup !== group || version !== navigation) return;
  members = nextMembers;
  $('member-count').textContent = members.length + (members.length === 1 ? ' person' : ' people');
  $('member-list').replaceChildren(...members.map(user => personNode(user, 'chip' + (user.user_id === highlight ? ' new-row' : ''))));
  if (!members.length) $('member-list').append(text('p', 'Who is sharing this trip? Add your first person.', 'muted'));
  const selected = new Map([...$('participants').querySelectorAll('input')].map(input => [input.value, input.checked]));
  $('participants').replaceChildren(...members.map(user => {
    const row = document.createElement('label'), check = document.createElement('input');
    check.type = 'checkbox'; check.value = user.user_id; check.defaultChecked = true;
    check.checked = selected.has(user.user_id) ? selected.get(user.user_id) : true;
    row.append(check, avatar(user), text('span', label(user), 'person-name'));
    return row;
  }));
  for (const id of ['payer', 'expense-recorder', 'sender', 'recipient', 'settlement-recorder']) options($(id), members);
  const available = users.filter(user => !members.some(item => item.user_id === user.id));
  options($('user'), available, 'id', users);
  if (!available.length) $('user').append(new Option('No other people yet', ''));
  syncControls();
}
async function openGroup(item) {
  const version = ++navigation;
  group = item.id; members = []; viewLoading = true;
  for (const form of document.querySelectorAll('form')) {
    form.reset(); form.retry = null; form.createdPerson = null; form.querySelector('.form-message')?.remove();
  }
  for (const id of ['participants', 'member-list', 'suggestions', 'balances', 'expense-history', 'settlement-history']) $(id).replaceChildren();
  $('group-switcher').value = group;
  $('group-title').textContent = $('current-group').textContent = item.name;
  $('home').hidden = $('home-header').hidden = true;
  $('workspace').hidden = $('group-header').hidden = false;
  $('group-content').hidden = true; $('group-loading').hidden = false; $('group-load-error').hidden = true;
  $('workspace').setAttribute('aria-busy', 'true');
  $('group-title').closest('.hero').classList.add('is-loading');
  $('group-title').closest('.hero').querySelector('.hero-summary').hidden = false;
  $('different-payment').open = false;
  $('message').hidden = true;
  syncControls();
  try {
    await loadMembers();
    if (version !== navigation) return;
    await refresh();
    if (version !== navigation) return;
    $('group-content').hidden = false;
    $('group-title').focus();
  } catch (error) {
    if (version === navigation) {
      $('group-load-error').hidden = false;
      $('group-title').closest('.hero').querySelector('.hero-summary').hidden = true;
      notify(error.message, true);
    }
  } finally {
    if (version === navigation) {
      viewLoading = false; $('group-loading').hidden = true;
      $('workspace').removeAttribute('aria-busy');
      $('group-title').closest('.hero').classList.remove('is-loading');
      syncControls();
    }
  }
}
function repaymentRow(payment) {
  const row = text('div', '', 'suggestion'), line = text('div', '', 'suggestion-line');
  const route = text('div', '', 'payment-route');
  route.setAttribute('aria-label', person(payment.from_user) + ' pays ' + person(payment.to_user) + ' ' + money(payment.amount_paise));
  route.append(personNode(member(payment.from_user)), text('span', 'pays', 'sr-only'), icon('arrow'),
    personNode(member(payment.to_user)), text('span', money(payment.amount_paise), 'amount'));
  const button = text('button', 'Mark as paid'); button.type = 'button';
  button.setAttribute('aria-expanded', 'false');
  const reveal = text('div', '', 'repayment-reveal'), inner = text('div', '', 'repayment-inner');
  reveal.inert = true; reveal.setAttribute('aria-hidden', 'true'); reveal.append(inner);
  line.append(route, button); row.append(line, reveal);
  button.addEventListener('click', () => {
    if (loading || viewLoading) return;
    let form = inner.querySelector('form');
    if (!form) {
      form = document.createElement('form');
      const amountLabel = text('label', 'Amount in rupees'), amount = document.createElement('input');
      amount.name = 'amount'; amount.inputMode = 'decimal'; amount.required = true;
      amount.pattern = '[0-9]+(\\.[0-9]{1,2})?'; amount.value = paiseToRupees(payment.amount_paise);
      amountLabel.append(amount);
      const actions = text('div', '', 'actions'), save = text('button', 'Save', 'primary'), cancel = text('button', 'Cancel');
      cancel.type = 'button';
      cancel.addEventListener('click', () => {
        if (loading) return;
        reveal.classList.remove('is-open'); reveal.inert = true; reveal.setAttribute('aria-hidden', 'true');
        button.setAttribute('aria-expanded', 'false'); button.focus();
        form.retry = null; form.reset(); amount.value = paiseToRupees(payment.amount_paise);
        form.querySelector('.form-message')?.remove();
      });
      actions.append(save, cancel);
      form.append(text('p', 'Record a payment that happened outside Pocket.', 'muted'), amountLabel, actions);
      bindForm(form, async () => {
        await saveFinancial('settlement', form, {
          from_user: BigInt(payment.from_user), to_user: BigInt(payment.to_user),
          recorded_by: BigInt(payment.from_user), amount_paise: rupeesToPaise(amount.value)
        });
        $('payments-heading').focus();
      });
      inner.append(form);
    }
    reveal.inert = false; reveal.removeAttribute('aria-hidden');
    reveal.classList.add('is-open'); button.setAttribute('aria-expanded', 'true');
    form.elements.amount.focus();
  });
  return row;
}
async function refresh(highlight = {}) {
  const selected = group, version = navigation;
  const [summary, expenses, settlements] = await Promise.all([
    api('/groups/' + selected + '/balances'), api('/groups/' + selected + '/expenses?limit=50&offset=0'),
    api('/groups/' + selected + '/settlements?limit=50&offset=0')
  ]);
  if (selected !== group || version !== navigation) return;
  $('total').textContent = money(summary.total_expenses_paise);
  const outstanding = BigInt(summary.total_outstanding_paise);
  $('group-status').textContent = outstanding ? money(outstanding) + ' left to settle' : 'All settled up';
  $('group-status').className = 'status ' + (outstanding ? 'owes' : 'settled');
  $('balances').replaceChildren(...summary.members.map(user => {
    const net = BigInt(user.net_balance_paise), status = net > 0n ? 'gets back' : net < 0n ? 'owes' : 'settled';
    const row = document.createElement('tr'), who = document.createElement('td'), cell = document.createElement('td');
    who.append(personNode(user));
    cell.append(text('span', status + (net ? ' ' + money(net < 0n ? -net : net) : ''), 'status ' + status.replace(' ', '-')));
    row.append(who, text('td', money(user.paid_paise)), text('td', money(user.share_paise)), cell);
    return row;
  }));
  $('suggestions').replaceChildren(...summary.suggested_payments.map(repaymentRow));
  if (!summary.suggested_payments.length) $('suggestions').append(emptyState('All settled up', 'No suggested payments left to record.', 'check'));
  renderHistory('expense', expenses, highlight);
  renderHistory('settlement', settlements, highlight);
}
function renderHistory(kind, page, highlight) {
  $(kind + '-history').replaceChildren(...page.items.map(item => {
    const row = text('div', '', 'history-row' + (highlight.kind === kind && highlight.id === item.id ? ' new-row' : ''));
    const body = text('div', '', 'history-body'), heading = text('div', '', 'history-heading');
    if (kind === 'expense') {
      heading.append(text('strong', item.description), text('span', money(item.amount_paise), 'amount'));
      body.append(heading, text('p', 'Paid by ' + person(item.paid_by)),
        text('small', item.shares.map(share => person(share.user_id) + ': ' + money(share.share_paise)).join(' · ')));
    } else {
      heading.append(text('strong', person(item.from_user) + ' paid ' + person(item.to_user)), text('span', money(item.amount_paise), 'amount'));
      body.append(heading);
    }
    body.append(text('small', 'Entered by ' + person(item.recorded_by) + ' · ' + new Date(item.created_at).toLocaleString()));
    row.append(avatar(member(kind === 'expense' ? item.paid_by : item.from_user)), body);
    return row;
  }));
  if (!page.items.length) $(kind + '-history').append(emptyState('No ' + (kind === 'expense' ? 'expenses' : 'repayments') + ' recorded yet.',
    kind === 'expense' ? 'Your shared expenses will appear here.' : 'Recorded payments will appear here.'));
}
async function afterWrite(message, form, highlight) {
  notify(message, false, form);
  try { await refresh(highlight); }
  catch { notify(message + ' Reload the page to see updated balances and activity.', true, form); }
}
async function saveFinancial(kind, form, body) {
  const signature = group + ':' + encodeJson(body);
  if (!form.retry || form.retry.signature !== signature) form.retry = {signature, id: crypto.randomUUID()};
  const saved = await api('/groups/' + group + '/' + (kind === 'expense' ? 'expenses' : 'settlements'), {...body, request_id: form.retry.id});
  form.retry = null; form.reset();
  if (kind === 'expense') $('expense-recorder').value = $('payer').value;
  if (kind === 'settlement' && form === $('settlement-form')) {
    $('settlement-recorder').value = $('sender').value; $('different-payment').open = false;
  }
  await afterWrite(kind === 'expense' ? 'Expense saved.' : 'Repayment recorded.', form, {kind, id: saved.id});
}
bindForm($('group-form'), async form => {
  const created = await api('/groups', {name: form.elements.name.value.trim()});
  await loadGroups(); await openGroup(created); notify('Group created. Add your people to begin.');
});
bindForm($('person-form'), async form => {
  const name = form.elements.name.value.trim();
  if (!form.createdPerson || form.createdPerson.name !== name) form.createdPerson = await api('/users', {name});
  const id = form.createdPerson.id;
  await api('/groups/' + group + '/members', {user_id: BigInt(id)});
  form.createdPerson = null; form.reset();
  await loadMembers(id); await afterWrite('Person added to the group.', form);
});
bindForm($('member-form'), async form => {
  const id = $('user').value;
  await api('/groups/' + group + '/members', {user_id: BigInt(id)});
  await loadMembers(id); await afterWrite('Person added to the group.', form);
});
bindForm($('expense-form'), async form => {
  const ids = [...$('participants').querySelectorAll('input:checked')].map(input => BigInt(input.value));
  if (!ids.length) throw new Error('Select at least one person to split the expense.');
  await saveFinancial('expense', form, {
    description: form.elements.description.value.trim(), amount_paise: rupeesToPaise(form.elements.amount.value),
    paid_by: BigInt($('payer').value), recorded_by: BigInt($('expense-recorder').value), participant_ids: ids
  });
});
bindForm($('settlement-form'), async form => {
  if ($('sender').value === $('recipient').value) throw new Error('Choose different people for From and To.');
  await saveFinancial('settlement', form, {
    from_user: BigInt($('sender').value), to_user: BigInt($('recipient').value),
    recorded_by: BigInt($('settlement-recorder').value), amount_paise: rupeesToPaise(form.elements.amount.value)
  });
});
$('payer').addEventListener('change', () => { $('expense-recorder').value = $('payer').value; });
$('sender').addEventListener('change', () => { $('settlement-recorder').value = $('sender').value; });
$('participants').addEventListener('change', syncControls);
$('everyone').addEventListener('click', () => { $('participants').querySelectorAll('input').forEach(input => { input.checked = true; }); syncControls(); });
$('settlement-cancel').addEventListener('click', () => { $('different-payment').open = false; $('different-payment').querySelector('summary').focus(); });
$('dismiss-message').addEventListener('click', () => {
  $('message').hidden = true;
  (group ? $('group-title') : $('group-form').elements.name).focus();
});
$('group-switcher').addEventListener('change', () => {
  if (loading) return;
  const selected = groups.find(item => item.id === $('group-switcher').value);
  if (selected) openGroup(selected);
});
$('retry-group').addEventListener('click', () => { const selected = groups.find(item => item.id === group); if (selected) openGroup(selected); });
$('back').addEventListener('click', async () => {
  if (loading) return;
  navigation++; group = ''; members = []; viewLoading = false;
  $('workspace').hidden = $('group-header').hidden = true;
  $('home').hidden = $('home-header').hidden = false; $('message').hidden = true;
  try { await loadGroups(); $('group-form').elements.name.focus(); } catch (error) { notify(error.message, true); }
});
for (const kind of ['expenses', 'repayments']) $('show-' + kind).addEventListener('click', () => {
  $('expense-history').hidden = kind !== 'expenses'; $('settlement-history').hidden = kind !== 'repayments';
  $('activity-toggle').dataset.active = kind;
  for (const other of ['expenses', 'repayments']) {
    if (other === kind) $('show-' + other).setAttribute('aria-current', 'true');
    else $('show-' + other).removeAttribute('aria-current');
  }
});
loadGroups().catch(error => notify(error.message, true));
