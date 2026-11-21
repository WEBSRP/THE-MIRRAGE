import { expect, test } from '@playwright/test';

test('VPN downloads unlock only after the server confirms readiness', async ({ page }) => {
  let available = false;
  let downloads = 0;
  await page.addInitScript(() => {
    localStorage.setItem('mirrage-token', 'test-token');
    sessionStorage.setItem('mirrage-availability-notice-dismissed', 'true');
  });
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/auth/me')) {
      await route.fulfill({ json: {
        id: 'vpn-test-user', username: 'player', email: 'player@example.com', is_active: true,
      } });
    } else if (path.endsWith('/session/status')) {
      await route.fulfill({ json: {
        session_id: 'vpn-test-session', status: 'ready', is_ready: true, vpn_download_available: available && downloads < 3,
        vpn_downloads_remaining: 3 - downloads,
        expires_at: new Date(Date.now() + 600_000).toISOString(),
      } });
    } else if (path.endsWith('/vpn/download')) {
      downloads++;
      await route.fulfill({ body: 'test VPN profile', contentType: 'application/x-openvpn-profile' });
    } else {
      await route.fulfill({ status: 503, json: { message: 'Test service unavailable' } });
    }
  });

  await page.goto('/vpn');
  const download = page.getByRole('button', { name: 'Download .ovpn Profile' }).first();
  await expect(download).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Download Signal' })).toBeDisabled();
  await expect(page.getByRole('heading', { name: 'Your session is ready' })).toHaveCount(0);
  expect(downloads).toBe(0);

  available = true;
  await expect(page.getByRole('heading', { name: 'Your session is ready' })).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: 'Go to VPN page' }).click();
  await expect(page).toHaveURL(/\/vpn$/);
  await expect(download).toBeEnabled();
  const downloaded = page.waitForEvent('download');
  await download.click();
  await downloaded;
  expect(downloads).toBe(1);

  await expect(page.getByText('2 VPN downloads remaining this session.')).toBeVisible();
  for (const remaining of [1, 0]) {
    const nextDownload = page.waitForEvent('download');
    await download.click();
    await nextDownload;
    if (remaining) {
      await expect(page.getByText('1 VPN download remaining this session.')).toBeVisible();
    }
  }
  await expect(download).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Download Signal' })).toBeDisabled();
  await expect(page.getByText(/You have used all VPN downloads/)).toBeVisible();
  expect(downloads).toBe(3);

  await page.reload();
  await expect(download).toBeDisabled();
  await expect(page.getByRole('heading', { name: 'Your session is ready' })).toHaveCount(0);
});
