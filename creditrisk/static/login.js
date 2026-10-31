'use strict';
let csrf;
const form = document.getElementById('login-form');
document.getElementById('toggle-password').addEventListener('click', event => {
  const input = document.getElementById('password'); input.type = input.type === 'password' ? 'text' : 'password';
  event.target.textContent = input.type === 'password' ? 'Hiện' : 'Ẩn';
  event.target.setAttribute('aria-label', input.type === 'password' ? 'Hiện mật khẩu' : 'Ẩn mật khẩu');
});
fetch('/api/auth/session').then(r=>r.json()).then(data=>csrf=data.csrf).catch(()=>{});
form.addEventListener('submit', async event => {
  event.preventDefault();const error=document.getElementById('auth-error'),button=document.getElementById('submit-login');
  error.hidden=true;button.disabled=true;const previous=button.textContent;button.textContent='Đang xử lý…';
  try {
    const change=document.body.dataset.passwordChange==='true';
    if(change&&document.getElementById('new-password').value!==document.getElementById('confirm-password').value)throw new Error('Mật khẩu mới nhập lại chưa khớp.');
    const body=change?{current_password:document.getElementById('password').value,new_password:document.getElementById('new-password').value}:{username:document.getElementById('username').value.trim(),password:document.getElementById('password').value};
    const response=await fetch(`/api/auth/${change?'password':'login'}`,{method:'POST',headers:{'Content-Type':'application/json',...(csrf?{'X-CSRF-Token':csrf}:{})},body:JSON.stringify(body)});
    const data=await response.json();if(!response.ok)throw new Error(data.error||'Không thể đăng nhập.');
    location.assign(data.redirect);
  } catch(err) {error.textContent=err.message;error.hidden=false;button.disabled=false;button.textContent=previous;}
});
