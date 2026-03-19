const form = document.getElementById('asset-form');
const printButton = document.getElementById('print-btn');
const resetButton = document.getElementById('reset-btn');
const qrImage = document.getElementById('qr-image');
const placeholders = document.querySelectorAll('[data-field]');

const formatDate = (value) => {
  if (!value) return '-';
  const [year, month, day] = value.split('-');
  return `${year}-${month}-${day}`;
};

const buildQrUrl = (assetCode) => {
  if (!assetCode) {
    return '';
  }
  const encoded = encodeURIComponent(assetCode);
  return `https://api.qrserver.com/v1/create-qr-code/?size=100x100&margin=0&data=${encoded}`;
};

const updatePreview = () => {
  const formData = new FormData(form);
  const values = Object.fromEntries(formData.entries());

  placeholders.forEach((node) => {
    const field = node.dataset.field;
    let value = values[field]?.trim();

    if (field === 'startDate') {
      value = formatDate(value);
    }

    node.textContent = value || '-';
  });

  qrImage.src = buildQrUrl(values.assetCode?.trim());
};

form.addEventListener('submit', (event) => {
  event.preventDefault();
  if (!form.reportValidity()) {
    return;
  }
  updatePreview();
});

printButton.addEventListener('click', () => {
  if (!form.reportValidity()) {
    return;
  }
  updatePreview();
  window.print();
});

resetButton.addEventListener('click', () => {
  form.reset();
  updatePreview();
});

form.addEventListener('input', updatePreview);
updatePreview();
