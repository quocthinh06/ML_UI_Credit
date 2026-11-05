'use strict';
let csrf, loginReady = false;
const form = document.getElementById('login-form');
document.getElementById('toggle-password').addEventListener('click', event => {
  const input = document.getElementById('password'); input.type = input.type === 'password' ? 'text' : 'password';
  event.target.textContent = input.type === 'password' ? 'Hiện' : 'Ẩn';
  event.target.setAttribute('aria-label', input.type === 'password' ? 'Hiện mật khẩu' : 'Ẩn mật khẩu');
});
async function initializeLogin() {
  const notice = document.getElementById('auth-notice');
  try {
    const response = await fetch('/api/auth/session', {cache:'no-store'});
    if (!response.ok) throw new Error('Không tải được trạng thái đăng nhập.');
    const data = await response.json();
    csrf = data.csrf;
    const change = document.body.dataset.passwordChange === 'true';
    if (change && !data.user) { location.assign('/login'); return; }
    loginReady = data.configured === true;
    form.querySelectorAll('input, button[type="submit"]').forEach(input => input.disabled = !loginReady);
    notice.hidden = loginReady;
    notice.textContent = 'Đăng nhập chưa được kích hoạt. Quản trị viên cần cấu hình MongoDB Atlas và khóa phiên bảo mật trên Vercel.';
  } catch (error) {
    notice.hidden = false;
    notice.textContent = 'Không kết nối được backend. Hãy mở trang qua địa chỉ Flask đang chạy và tải lại để thử lại.';
  } finally {
    form.setAttribute('aria-busy', 'false');
  }
}
initializeLogin();
form.addEventListener('submit', async event => {
  event.preventDefault();if(!loginReady)return;const error=document.getElementById('auth-error'),button=document.getElementById('submit-login');
  error.hidden=true;button.disabled=true;const previous=button.textContent;button.textContent='Đang xử lý…';
  try {
    const change=document.body.dataset.passwordChange==='true';
    if(change&&document.getElementById('new-password').value!==document.getElementById('confirm-password').value)throw new Error('Mật khẩu mới nhập lại chưa khớp.');
    const body=change?{current_password:document.getElementById('password').value,new_password:document.getElementById('new-password').value}:{username:document.getElementById('username').value.trim(),password:document.getElementById('password').value};
    const response=await fetch(`/api/auth/${change?'password':'login'}`,{method:'POST',headers:{'Content-Type':'application/json',...(csrf?{'X-CSRF-Token':csrf}:{})},body:JSON.stringify(body)});
    const data=await response.json();if(!response.ok)throw new Error((data.error||'Không thể đăng nhập.')+(data.code?' ['+data.code+']':''));
    location.assign(data.redirect);
  } catch(err) {error.textContent=err.message;error.hidden=false;button.disabled=false;button.textContent=previous;}
});
