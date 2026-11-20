import { expect, test } from '@playwright/test';

const SUFFISSO_UNIVOCO = Date.now().toString(36);

test('il cittadino si registra, accede e invia una segnalazione', async ({
  page,
}) => {
  const email = `cittadino.${SUFFISSO_UNIVOCO}@example.com`;
  const nickname = `cittadino_${SUFFISSO_UNIVOCO}`.slice(0, 30);
  const password = 'PasswordSicura123!';
  const titolo = `Lampione spento ${SUFFISSO_UNIVOCO}`;
  const descrizione =
    'Il lampione davanti al civico 12 non si accende da tre giorni.';

  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: 'Segnalazioni dei cittadini' }),
  ).toBeVisible();

  await page.getByRole('link', { name: 'Registrati' }).click();
  await expect(
    page.getByRole('heading', { name: 'Registrati' }),
  ).toBeVisible();
  await page.getByLabel('Nickname').fill(nickname);
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: "Crea l'account" }).click();

  await expect(page.getByRole('link', { name: nickname })).toBeVisible();
  await page.getByRole('button', { name: 'Esci' }).click();

  await page.getByRole('link', { name: 'Accedi' }).click();
  await expect(page.getByRole('heading', { name: 'Accedi' })).toBeVisible();
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Accedi' }).click();

  await expect(page.getByRole('link', { name: nickname })).toBeVisible();

  await page.getByRole('link', { name: 'Segnala un problema' }).click();
  await expect(
    page.getByRole('heading', { name: 'Segnala un problema' }),
  ).toBeVisible();

  const mappa = page.locator('.leaflet-container');
  await expect(mappa).toBeVisible();
  await mappa.click({ position: { x: 240, y: 180 } });
  await expect(
    page.getByText(/Comune competente|non è ancora coperto/),
  ).toBeVisible();

  await page.getByLabel('Titolo').fill(titolo);
  await page.getByLabel('Descrizione').fill(descrizione);
  const categoria = page.locator('#categoria');
  await expect(categoria.locator('option')).toHaveCount(5);
  await categoria.selectOption({ index: 1 });

  await page.getByRole('button', { name: 'Invia la segnalazione' }).click();

  await expect(page).toHaveURL(/\/reports\/[^/]+$/);
  await expect(page.getByRole('heading', { name: titolo })).toBeVisible();
  await expect(page.getByText(descrizione)).toBeVisible();
});
