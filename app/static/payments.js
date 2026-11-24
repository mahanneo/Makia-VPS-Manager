(() => {
  const form = document.getElementById('paymentForm');
  if (!form) return;
  const status = document.getElementById('payFormStatus');
  const submit = document.getElementById('paySubmit');
  const file = form.querySelector('input[name="receipt"]');
  const fileName = document.getElementById('payFileName');

  function showStatus(message, kind) {
    status.textContent = message;
    status.className = 'pay-form-status show ' + (kind || '');
  }
  async function copyValue(value) {
    try {
      await navigator.clipboard.writeText(value);
    } catch (_) {
      const input = document.createElement('textarea');
      input.value = value;
      input.style.position = 'fixed';
      input.style.opacity = '0';
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      input.remove();
    }
  }

  document.querySelectorAll('[data-copy-card]').forEach(button => {
    button.addEventListener('click', async () => {
      await copyValue(button.dataset.copyCard || '');
      const old = button.textContent;
      button.textContent = 'شماره کارت کپی شد ✓';
      button.classList.add('copied');
      setTimeout(() => {
        button.textContent = old;
        button.classList.remove('copied');
      }, 1800);
    });
  });

  file?.addEventListener('change', () => {
    const chosen = file.files && file.files[0];
    fileName.textContent = chosen ? chosen.name + ' · ' + (chosen.size / 1024 / 1024).toFixed(2) + ' MB' : 'JPG · PNG · WEBP · PDF';
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    status.className = 'pay-form-status';
    const amount = String(form.elements.amount_toman.value || '').replace(/[۰-۹٠-٩]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d) >= 0 ? '۰۱۲۳۴۵۶۷۸۹'.indexOf(d) : '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
    if (!amount.replace(/\D/g, '')) {
      showStatus('مبلغ پرداختی را وارد کنید.', 'error');
      form.elements.amount_toman.focus();
      return;
    }
    if (!String(form.elements.tracking_code.value || '').trim() && !(file?.files?.length)) {
      showStatus('شناسه پیگیری یا تصویر رسید را وارد کنید.', 'error');
      return;
    }
    submit.disabled = true;
    submit.querySelector('span').textContent = 'در حال ثبت اطلاعات…';
    try {
      const response = await fetch('/api/public/payments/submit', {
        method: 'POST',
        credentials: 'same-origin',
        body: new FormData(form),
        headers: {'Accept': 'application/json'}
      });
      let data = {};
      try { data = await response.json(); } catch (_) {}
      if (!response.ok) throw new Error(data.detail || 'ثبت اطلاعات با خطا مواجه شد.');
      showStatus('درخواست شما ثبت شد. کد پیگیری: ' + data.reference + ' · وضعیت: در انتظار بررسی', 'success');
      form.reset();
      fileName.textContent = 'JPG · PNG · WEBP · PDF';
      status.scrollIntoView({behavior: 'smooth', block: 'center'});
    } catch (error) {
      showStatus(error.message || 'ارتباط با سرور برقرار نشد؛ دوباره تلاش کنید.', 'error');
    } finally {
      submit.disabled = false;
      submit.querySelector('span').textContent = 'ثبت اطلاعات پرداخت';
    }
  });
})();
