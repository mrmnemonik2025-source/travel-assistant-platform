const state = { excursions: [], selected: null };
const cards = document.querySelector('#cards');
const statusText = document.querySelector('#catalog-status');
const detailsDialog = document.querySelector('#details-dialog');
const bookingDialog = document.querySelector('#booking-dialog');
const bookingForm = document.querySelector('#booking-form');

document.querySelector('#year').textContent = new Date().getFullYear();
bookingForm.elements.excursion_date.min = new Date().toISOString().slice(0, 10);

function make(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderCards(items) {
  cards.replaceChildren();
  items.forEach((item, index) => {
    const card = make('article', 'card');
    card.tabIndex = 0;
    card.setAttribute('aria-label', `Подробнее: ${item.title}`);
    const image = make('img');
    image.src = item.image_url;
    image.alt = item.title;
    image.loading = index < 3 ? 'eager' : 'lazy';
    const overlay = make('div', 'card-overlay');
    const tags = make('div', 'card-tags');
    [...item.interests, ...item.formats].slice(0, 2).forEach(value => tags.append(make('span', 'tag', value)));
    const title = make('h3', '', item.title);
    const time = make('p', 'card-time', item.time);
    const bottom = make('div', 'card-bottom');
    bottom.append(make('span', 'card-price', item.price), make('span', 'card-arrow', '↗'));
    overlay.append(tags, title, time, bottom);
    card.append(image, overlay);
    card.addEventListener('click', () => openDetails(item));
    card.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') openDetails(item);
    });
    cards.append(card);
  });
  statusText.textContent = `${items.length} маршрутов · бронирование онлайн`;
}

function openDetails(item) {
  state.selected = item;
  const content = document.querySelector('#details-content');
  content.replaceChildren();
  const image = make('img', 'detail-image');
  image.src = item.image_url;
  image.alt = item.title;
  const body = make('div', 'detail-body');
  body.append(make('span', 'eyebrow dark', 'АВТОРСКИЙ МАРШРУТ'), make('h2', '', item.title), make('p', 'detail-lead', item.description));
  const meta = make('div', 'detail-meta');
  const duration = make('div');
  duration.append(make('small', '', 'Продолжительность'), make('strong', '', item.time));
  const price = make('div');
  price.append(make('small', '', 'Стоимость'), make('strong', '', item.price));
  meta.append(duration, price);
  body.append(meta);
  if (item.included.length) {
    const included = make('div', 'included');
    included.append(make('h3', '', 'Что включено'));
    const list = make('ul');
    item.included.forEach(value => list.append(make('li', '', value.replace(/[;.]$/, ''))));
    included.append(list);
    body.append(included);
  }
  const button = make('button', 'button button-primary', 'Забронировать экскурсию');
  button.type = 'button';
  button.addEventListener('click', () => {
    detailsDialog.close();
    openBooking(item);
  });
  body.append(button);
  content.append(image, body);
  detailsDialog.showModal();
  document.body.classList.add('modal-open');
}

function openBooking(item) {
  state.selected = item;
  bookingForm.reset();
  bookingForm.elements.people_count.value = 2;
  bookingForm.elements.excursion_date.min = new Date().toISOString().slice(0, 10);
  bookingForm.elements.excursion_id.value = item.id;
  document.querySelector('#booking-excursion').textContent = item.title;
  document.querySelector('#form-message').textContent = '';
  document.querySelector('#booking-content').hidden = false;
  document.querySelector('#booking-success').hidden = true;
  bookingDialog.showModal();
  document.body.classList.add('modal-open');
}

async function submitBooking(event) {
  event.preventDefault();
  const button = bookingForm.querySelector('.submit-button');
  const message = document.querySelector('#form-message');
  const data = Object.fromEntries(new FormData(bookingForm));
  data.people_count = Number(data.people_count);
  button.disabled = true;
  button.textContent = 'Отправляем…';
  message.textContent = '';
  try {
    const response = await fetch('/api/bookings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Не удалось отправить заявку');
    document.querySelector('#booking-content').hidden = true;
    document.querySelector('#booking-success').hidden = false;
    document.querySelector('#success-text').textContent = `Заявка №${result.booking_id} создана. Менеджер свяжется с вами для подтверждения деталей.`;
  } catch (error) {
    message.textContent = error.message || 'Проверьте соединение и попробуйте ещё раз.';
  } finally {
    button.disabled = false;
    button.textContent = 'Отправить заявку';
  }
}

function closeDialog(dialog) {
  dialog.close();
  document.body.classList.remove('modal-open');
}

document.querySelectorAll('.modal-close').forEach(button => button.addEventListener('click', () => closeDialog(button.closest('dialog'))));
document.querySelector('[data-close]').addEventListener('click', () => closeDialog(bookingDialog));
[detailsDialog, bookingDialog].forEach(dialog => {
  dialog.addEventListener('click', event => {
    if (event.target === dialog) closeDialog(dialog);
  });
  dialog.addEventListener('close', () => document.body.classList.remove('modal-open'));
});
bookingForm.addEventListener('submit', submitBooking);

fetch('/api/excursions')
  .then(response => {
    if (!response.ok) throw new Error('Каталог временно недоступен');
    return response.json();
  })
  .then(items => {
    state.excursions = items;
    renderCards(items);
  })
  .catch(error => {
    statusText.textContent = 'Не удалось загрузить каталог';
    cards.append(make('p', 'catalog-error', `${error.message}. Обновите страницу или откройте Telegram-бота.`));
  });
