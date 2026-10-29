// Kiểm tra validateCredentials (web/src/auth/validate.ts) bằng Node, không cần thư viện test.
// tests/test_web_auth_validate.py gọi script này; thoát mã khác 0 nếu có assert sai.
// Chạy: node web/scripts/check-auth-validate.ts   (Node ≥ 22.18 chạy thẳng .ts)
import assert from 'node:assert/strict'
import { hasErrors, lockoutMessage, validateCredentials } from '../src/auth/validate.ts'

const ok = 'an@example.com'

// Đăng nhập đúng hình dạng: không lỗi; mật khẩu ngắn vẫn cho gửi (tài khoản cũ, server quyết).
assert.deepEqual(validateCredentials('login', ok, '123', ''), {})
assert.equal(hasErrors({}), false)

// Bỏ trống
assert.deepEqual(validateCredentials('login', '', '', ''), {
  email: 'Vui lòng nhập email.',
  password: 'Vui lòng nhập mật khẩu.',
})

// Email sai hình dạng (giống server: một @, hai bên không rỗng, tên miền có dấu chấm, không khoảng trắng)
for (const bad of ['an', 'an@', '@x.com', 'a@b@c', 'an @x.com', 'an@x', 'an@x.', 'an@.com']) {
  assert.equal(validateCredentials('login', bad, 'pw', '').email, 'Email không hợp lệ.', bad)
}
// Không sửa hoa thường: email viết hoa vẫn hợp lệ
assert.equal(validateCredentials('login', 'An@Example.com', 'pw', '').email, undefined)

// Tạo tài khoản: độ dài mật khẩu, ô nhập lại
assert.equal(
  validateCredentials('register', ok, '1234567', '1234567').password,
  'Mật khẩu phải có ít nhất 8 ký tự.',
)
assert.equal(validateCredentials('register', ok, '12345678', '').confirm, 'Vui lòng nhập lại mật khẩu.')
assert.equal(
  validateCredentials('register', ok, '12345678', '12345679').confirm,
  'Mật khẩu nhập lại không khớp.',
)
assert.deepEqual(validateCredentials('register', ok, '12345678', '12345678'), {})

// Ô nhập lại không được kiểm tra khi đăng nhập
assert.equal(validateCredentials('login', ok, 'pw', 'khac').confirm, undefined)

// lockoutMessage: Retry-After (giây) → số phút làm tròn lên; thiếu/lạ → không nói số phút
assert.equal(lockoutMessage('900'), 'Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau 15 phút.')
assert.equal(lockoutMessage('61'), 'Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau 2 phút.')
assert.equal(lockoutMessage('1'), 'Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau 1 phút.')
for (const bad of [null, '', 'abc', '0', '-5'])
  assert.equal(lockoutMessage(bad), 'Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau ít phút.')

console.log('check-auth-validate: ok')
