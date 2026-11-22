const socialProfiles = [
  { label: 'LinkedIn', logo: 'linkedin', url: 'https://www.linkedin.com/in/websrp/', override: import.meta.env.VITE_CONTACT_LINKEDIN_URL },
  { label: 'X', logo: 'x', url: 'https://x.com/websrp', override: import.meta.env.VITE_CONTACT_TWITTER_URL },
  { label: 'Instagram', logo: 'instagram', url: 'https://www.instagram.com/in_soum_niaaaa/', override: import.meta.env.VITE_CONTACT_INSTAGRAM_URL },
];

function profileUrl(value: unknown): string | undefined {
  if (typeof value !== 'string' || !value.trim()) return undefined;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' ? url.href : undefined;
  } catch {
    return undefined;
  }
}

export const contactProfiles = socialProfiles.map(({ label, logo, url, override }) => ({
  label,
  logo,
  href: profileUrl(override) || url,
}));
