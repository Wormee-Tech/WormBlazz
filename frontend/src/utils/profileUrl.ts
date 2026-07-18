/**
 * Public profile deep links — only for live platforms with real handles.
 * Demo never links out: synthetic names do not exist on Instagram/TikTok.
 */
export function resolveProfileUrl(metadata?: Record<string, string>): string | null {
    if (!metadata) return null;

    const username = (metadata.username ?? '').trim().replace(/^@+/, '');
    const platform = (metadata.platform ?? '').trim();
    const raw = (metadata.profileUrl ?? '').trim();

    // Demo handles are fake — do not open Instagram/TikTok (would 404).
    if (platform === 'Demo') {
        return null;
    }

    if (metadata.linkType === 'Hashtag' && raw) {
        try {
            const url = new URL(raw);
            return url.protocol === 'https:' || url.protocol === 'http:' ? url.toString() : null;
        } catch {
            return null;
        }
    }

    if (username && platform === 'Instagram') {
        return `https://www.instagram.com/${username}/`;
    }
    if (username && platform === 'TikTok') {
        return `https://www.tiktok.com/@${username}`;
    }

    if (!raw || raw.includes('example.com')) {
        return null;
    }

    try {
        const url = new URL(raw);
        if (url.protocol !== 'https:' && url.protocol !== 'http:') return null;

        if (url.hostname.includes('instagram.com')) {
            const handle = url.pathname.replace(/^\/+/, '').replace(/\/+$/, '').replace(/^@+/, '');
            return handle ? `https://www.instagram.com/${handle}/` : null;
        }

        return url.toString();
    } catch {
        return null;
    }
}
