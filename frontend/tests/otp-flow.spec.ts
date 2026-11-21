import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('mirrage-availability-notice-dismissed', 'true');
  });
  // Every API request is intercepted. These tests never send real email or
  // connect to the live backend, including post-login background polling.
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/request-otp') || path.endsWith('/resend-otp')) {
      await route.fulfill({ json: { message: 'Verification code sent.', resend_after_seconds: 0 } });
    } else {
      await route.fulfill({ status: 503, json: { code: 'TEST_UNAVAILABLE', message: 'Test service unavailable' } });
    }
  });
});

test('a failed email request preserves the email and shows the backend error', async ({ page }) => {
  await page.route('**/api/v1/auth/request-otp', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 150));
    await route.fulfill({ status: 503, json: { code: 'OTP_EMAIL_UNAVAILABLE', message: 'OTP email is temporarily unavailable' } });
  });
  await page.goto('/login');
  await page.getByLabel('Email address').fill('operator@example.com');
  await page.getByRole('button', { name: 'Send verification code' }).click();
  await expect(page.getByRole('alert')).toContainText('OTP email is temporarily unavailable');
  await expect(page.getByLabel('Email address')).toHaveValue('operator@example.com');
  await expect(page).toHaveURL(/\/login$/);
});

test('a successful email request opens the code entry screen', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email address').fill('operator@example.com');
  await page.getByRole('button', { name: 'Send verification code' }).click();
  await expect(page).toHaveURL(/\/verify-otp$/);
  await expect(page.getByLabel('Verification code')).toBeVisible();
  await expect(page.getByText('Verification code sent to operator@example.com.')).toBeVisible();
});

test('an invalid code remains visible with its error', async ({ page }) => {
  await page.route('**/api/v1/auth/verify-otp', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 150));
    await route.fulfill({ status: 401, json: { code: 'AUTHENTICATION_FAILED', message: 'Invalid OTP' } });
  });
  await page.goto('/login');
  await page.getByLabel('Email address').fill('operator@example.com');
  await page.getByRole('button', { name: 'Send verification code' }).click();
  await page.getByLabel('Verification code').fill('112233');
  await page.getByRole('button', { name: 'Verify and continue' }).click();
  await expect(page.getByText('Invalid OTP', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Verification code')).toHaveValue('112233');
  await expect(page).toHaveURL(/\/verify-otp$/);
});

test('a failed resend preserves the code and shows the error', async ({ page }) => {
  await page.route('**/api/v1/auth/resend-otp', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 150));
    await route.fulfill({ status: 429, headers: { 'Retry-After': '45' }, json: { code: 'OTP_COOLDOWN', message: 'Please wait before requesting a new code.' } });
  });
  await page.goto('/login');
  await page.getByLabel('Email address').fill('operator@example.com');
  await page.getByRole('button', { name: 'Send verification code' }).click();
  await page.getByLabel('Verification code').fill('112233');
  await page.getByRole('button', { name: 'Resend code', exact: true }).click();
  await expect(page.getByText('Please wait before requesting a new code.')).toBeVisible();
  await expect(page.getByLabel('Verification code')).toHaveValue('112233');
  await expect(page.getByRole('button', { name: /Resend code in \d+s/ })).toBeDisabled();
});

test('successful verification returns to the protected page originally requested', async ({ page }) => {
  await page.route('**/api/v1/auth/verify-otp', async (route) => {
    await route.fulfill({ json: {
      access_token: 'browser-test-token', token_type: 'bearer', expires_in: 3600, is_new_user: false,
      user: { id: 'browser-user', username: 'operator', email: 'operator@example.com',
        is_active: true, is_admin: false, created_at: '2026-11-21T00:00:00Z' },
    } });
  });
  await page.goto('/challenges');
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Email address').fill('operator@example.com');
  await page.getByRole('button', { name: 'Send verification code' }).click();
  await page.getByLabel('Verification code').fill('112233');
  await page.getByRole('button', { name: 'Verify and continue' }).click();
  await expect(page).toHaveURL(/\/challenges$/);
});

test('a successful resend clears the old code and keeps the OTP screen', async ({ page }) => {
  await page.route('**/api/v1/auth/resend-otp', async (route) => {
    await route.fulfill({ json: { message: 'A new code was sent.', resend_after_seconds: 60 } });
  });
  await page.goto('/login');
  await page.getByLabel('Email address').fill('operator@example.com');
  await page.getByRole('button', { name: 'Send verification code' }).click();
  await page.getByLabel('Verification code').fill('112233');
  await page.getByRole('button', { name: 'Resend code', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('A fresh verification code was sent to operator@example.com.');
  await expect(page.getByLabel('Verification code')).toHaveValue('');
  await expect(page.getByRole('button', { name: /Resend code in \d+s/ })).toBeDisabled();
  await expect(page).toHaveURL(/\/verify-otp$/);
});

test('a stored token is checked before rendering a protected page', async ({ page }) => {
  let release = () => {};
  const pending = new Promise<void>((resolve) => { release = resolve; });
  await page.addInitScript(() => localStorage.setItem('mirrage-token', 'expired-browser-test-token'));
  await page.route('**/api/v1/auth/me', async (route) => {
    await pending;
    await route.fulfill({ status: 401, json: { message: 'Token expired', code: 'AUTHENTICATION_FAILED' } });
  });
  try {
    await page.goto('/dashboard');
    await expect(page.getByText('Verifying operator credentials...')).toBeVisible();
  } finally {
    release();
  }
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel('Email address')).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('mirrage-token'))).toBeNull();
});
