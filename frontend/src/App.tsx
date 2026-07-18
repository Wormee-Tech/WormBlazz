import { useState } from 'react';
import {
    crawlNetwork,
    startBackgroundCrawl,
    waitForCrawlJob,
    getNetworkOverview,
    getNetworkGraph,
    getNetworkGraphStats,
} from './networkApi';
import type {
    ArchitectureResponse,
    GraphStatsResponse,
    NetworkOverview,
    SocialPlatform,
    CrawlSource,
} from './types';
import NetworkOverviewPanel from './components/NetworkOverviewPanel';
import ArchitectureGraph from './components/ArchitectureGraph';
import './App.css';

type Tab = 'overview' | 'network';

function App() {
    const [platform, setPlatform] = useState<SocialPlatform>('Instagram');
    const [source, setSource] = useState<CrawlSource>('apify');
    const [username, setUsername] = useState('vtv24news');
    const [depth, setDepth] = useState(2);
    const [networkId, setNetworkId] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [progressMsg, setProgressMsg] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<Tab>('network');

    const [overview, setOverview] = useState<NetworkOverview | null>(null);
    const [graph, setGraph] = useState<ArchitectureResponse | null>(null);
    const [graphStats, setGraphStats] = useState<GraphStatsResponse | null>(null);

    const handleCrawl = async (e: React.FormEvent, forceRefresh = false) => {
        e.preventDefault();
        if (!username.trim() && platform !== 'Demo') return;

        setLoading(true);
        setError(null);
        setProgressMsg(null);
        setOverview(null);
        setGraph(null);
        setGraphStats(null);

        const request = {
            username: username.trim() || 'wormee',
            platform,
            source,
            depth,
            maxProfiles: 1000,
            forceRefresh,
        };

        try {
            let resultNetworkId: string;

            if (source === 'local' && platform !== 'Demo') {
                setProgressMsg('Starting background crawl…');
                const job = await startBackgroundCrawl(request);
                const finished = await waitForCrawlJob(job.jobId, (j) => {
                    setProgressMsg(
                        j.message
                            ? `${j.message} (${Math.round(j.progress * 100)}%)`
                            : `${j.status}…`,
                    );
                });
                if (finished.status === 'failed' || !finished.networkId) {
                    throw new Error(finished.error || 'Background crawl failed');
                }
                resultNetworkId = finished.networkId;
            } else {
                const result = await crawlNetwork(request);
                resultNetworkId = result.networkId;
            }

            setNetworkId(resultNetworkId);

            const [ov, g, stats] = await Promise.all([
                getNetworkOverview(resultNetworkId),
                getNetworkGraph(resultNetworkId),
                getNetworkGraphStats(resultNetworkId),
            ]);

            setOverview(ov);
            setGraph(g);
            setGraphStats(stats);
            setActiveTab('network');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Crawl failed');
        } finally {
            setLoading(false);
            setProgressMsg(null);
        }
    };

    return (
        <div className="app">
            <header className="app-header">
                <img src="/logo.svg" alt="WormBlazz" className="app-logo" />
                <div>
                    <h1>WormBlazz</h1>
                    <p className="subtitle">Map public social connections as an interactive graph.</p>
                </div>
            </header>

            <main>
                <form className="url-form network-form" onSubmit={handleCrawl}>
                    <select
                        className="platform-select"
                        value={platform}
                        onChange={(e) => setPlatform(e.target.value as SocialPlatform)}
                        disabled={loading}
                        aria-label="Platform"
                    >
                        <option value="Demo">Demo</option>
                        <option value="Instagram">Instagram</option>
                        <option value="TikTok">TikTok</option>
                    </select>
                    {platform !== 'Demo' && (
                        <select
                            className="source-select"
                            value={source}
                            onChange={(e) => setSource(e.target.value as CrawlSource)}
                            disabled={loading}
                            aria-label="Data source"
                        >
                            <option value="apify">Apify (paid)</option>
                            <option value="local">Local (free)</option>
                        </select>
                    )}
                    <input
                        type="text"
                        placeholder="@username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        disabled={loading}
                    />
                    <select
                        className="depth-select"
                        value={depth}
                        onChange={(e) => setDepth(Number(e.target.value))}
                        disabled={loading}
                        aria-label="Depth"
                    >
                        <option value={1}>Depth 1</option>
                        <option value={2}>Depth 2</option>
                        <option value={3}>Depth 3</option>
                    </select>
                    <button type="submit" disabled={loading || (!username.trim() && platform !== 'Demo')}>
                        {loading ? 'Mapping...' : 'Map network'}
                    </button>
                </form>

                <p className="token-hint network-hint">
                    Đang chọn <strong>{platform}</strong>.{' '}
                    {platform === 'Demo' ? (
                        <>
                            Demo = dữ liệu giả (handle fake → Instagram báo không tồn tại). Muốn
                            followers thật: chọn <strong>Instagram</strong> + username public.
                        </>
                    ) : source === 'local' ? (
                        <>
                            Nguồn <strong>Local (free)</strong> = chạy ngầm,{' '}
                            <strong>không tốn Apify, không cần login</strong>. Đọc dữ liệu public
                            (tên, followers, bio) và dựng graph từ @mention + #hashtag trong bio
                            rồi BFS theo depth. Chỉ account public, dữ liệu thưa hơn Apify.
                        </>
                    ) : platform === 'Instagram' ? (
                        <>
                            Instagram = crawl followers thật qua Apify (tối đa 1000). Cần{' '}
                            <code>APIFY_TOKEN</code> trong <code>backend/.env</code>. Chỉ account
                            public.
                        </>
                    ) : (
                        <>
                            TikTok = crawl tối đa 1000 followers thật và hashtag từ 5 bài gần nhất
                            của tối đa 20 profiles qua Apify. Cần <code>APIFY_TOKEN</code>.
                        </>
                    )}
                </p>

                {loading && progressMsg && (
                    <p className="token-hint network-hint progress-hint">{progressMsg}</p>
                )}

                {error && <p className="error">{error}</p>}

                {networkId && !loading && (
                    <>
                        <div className="results-toolbar">
                            <div className="tabs">
                                <button
                                    className={activeTab === 'overview' ? 'active' : ''}
                                    onClick={() => setActiveTab('overview')}
                                >
                                    Overview
                                </button>
                                <button
                                    className={activeTab === 'network' ? 'active' : ''}
                                    onClick={() => setActiveTab('network')}
                                >
                                    Network graph
                                </button>
                            </div>
                            <button
                                className="reanalyze-btn"
                                onClick={(e) => handleCrawl(e, true)}
                                title="Force refresh"
                            >
                                &#x21bb; Refresh
                            </button>
                        </div>

                        {activeTab === 'overview' && overview && (
                            <NetworkOverviewPanel overview={overview} />
                        )}
                        {activeTab === 'network' && graph && (
                            <ArchitectureGraph architecture={graph} stats={graphStats} />
                        )}
                    </>
                )}

                {!networkId && !loading && (
                    <div className="empty-state">
                        <p>Enter a public handle and map the connection graph.</p>
                        <p className="empty-hint">Try Demo + any username to see the graph structure.</p>
                    </div>
                )}
            </main>

            <footer className="app-footer">
                <p>WormBlazz · public social network mapper</p>
            </footer>
        </div>
    );
}

export default App;
