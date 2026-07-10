export function backendStateLabel(state: string): string {
  if (state === 'update_required') return 'Update required';
  if (state === 'installed') return 'Installed';
  if (state === 'installable') return 'Installable';
  if (state === 'unsupported') return 'Unsupported';
  return state || 'Unknown';
}

export function backendStateBadgeClass(state: string): string {
  if (state === 'installed') return 'ops-badge-ok';
  if (state === 'update_required') return 'ops-badge-warn';
  if (state === 'unsupported') return 'ops-badge-danger';
  return '';
}
