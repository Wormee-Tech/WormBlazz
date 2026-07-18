import type {
    ArchitectureResponse,
    GraphStatsResponse,
    NetworkOverview,
    CrawlNetworkRequest,
    CrawlNetworkResponse,
    CrawlJob,
} from './types';

const NETWORK_BASE = '/api/network';

export async function crawlNetwork(request: CrawlNetworkRequest): Promise<CrawlNetworkResponse> {
    const res = await fetch(`${NETWORK_BASE}/crawl`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
    });
    if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Crawl failed: ${res.statusText}`);
    }
    return res.json();
}

export async function startBackgroundCrawl(request: CrawlNetworkRequest): Promise<CrawlJob> {
    const res = await fetch(`${NETWORK_BASE}/crawl/background`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
    });
    if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Crawl failed: ${res.statusText}`);
    }
    return res.json();
}

export async function getCrawlJob(jobId: string): Promise<CrawlJob> {
    const res = await fetch(`${NETWORK_BASE}/jobs/${encodeURIComponent(jobId)}`);
    if (!res.ok) throw new Error(`Failed to fetch job: ${res.statusText}`);
    return res.json();
}

/** Poll a background crawl until it finishes, reporting progress along the way. */
export async function waitForCrawlJob(
    jobId: string,
    onProgress?: (job: CrawlJob) => void,
    intervalMs = 2000,
): Promise<CrawlJob> {
    for (;;) {
        const job = await getCrawlJob(jobId);
        onProgress?.(job);
        if (job.status === 'succeeded' || job.status === 'failed') return job;
        await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
}

export async function getNetworkOverview(networkId: string): Promise<NetworkOverview> {
    const res = await fetch(`${NETWORK_BASE}/${encodeURIComponent(networkId)}/overview`);
    if (!res.ok) throw new Error(`Failed to fetch overview: ${res.statusText}`);
    return res.json();
}

export async function getNetworkGraph(networkId: string): Promise<ArchitectureResponse> {
    const res = await fetch(`${NETWORK_BASE}/${encodeURIComponent(networkId)}/graph`);
    if (!res.ok) throw new Error(`Failed to fetch graph: ${res.statusText}`);
    return res.json();
}

export async function getNetworkGraphStats(networkId: string): Promise<GraphStatsResponse> {
    const res = await fetch(`${NETWORK_BASE}/${encodeURIComponent(networkId)}/graph/stats`);
    if (!res.ok) throw new Error(`Failed to fetch graph stats: ${res.statusText}`);
    return res.json();
}
