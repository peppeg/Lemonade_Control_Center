/** Default llama.cpp backend from Lemonade's config: nested since 11.x, flat before. */
export function configuredBackend(config: Record<string, unknown>): string | null {
  const section = config.llamacpp;
  const nested = section && typeof section === 'object' ? (section as Record<string, unknown>).backend : undefined;
  const value = nested ?? config['llamacpp.backend'] ?? config.llamacpp_backend ?? config.backend;
  return typeof value === 'string' && value ? value : null;
}
