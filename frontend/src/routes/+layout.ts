import { redirect } from '@sveltejs/kit';
import type { LayoutLoad } from './$types';

export const prerender = false;

export const load: LayoutLoad = async ({ fetch, url }) => {
  if (url.pathname === '/setup') {
    return {};
  }

  let setupIncomplete = false;

  try {
    const response = await fetch('/api/setup/status');
    if (!response.ok) {
      return {};
    }

    const status = await response.json() as { setup_complete?: boolean };
    if (status.setup_complete === false) {
      setupIncomplete = true;
    }
  } catch {
    return {};
  }

  if (setupIncomplete) {
    throw redirect(307, '/setup');
  }

  return {};
};
