import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, Loader2, Share2, Info, X, GitCommit, UserCheck, Network, Zap, FileText, ArrowUp, HelpCircle, ExternalLink, Home, MessageSquare, UserPlus, Settings2, ChevronDown, ChevronUp, Camera } from 'lucide-react';
import * as d3 from 'd3';
import './App.css';

// --- Types ---

interface ParsedUrl {
  handle: string;
  rkey: string;
}

interface BlueskyProfile {
  did: string;
  handle: string;
  displayName?: string;
  avatar?: string;
  followersCount?: number;
}

interface BlueskyPost {
  uri: string;
  cid: string;
  author: BlueskyProfile;
  record: {
    text: string;
    createdAt?: string;
  };
  embed?: {
    images?: Array<{
      thumb: string;
      fullsize: string;
      alt?: string;
    }>;
  };
  likeCount?: number;
  repostCount?: number;
  replyCount?: number;
  indexedAt?: string;
}

interface ThreadNode {
  $type?: string;
  post: BlueskyPost;
  parent?: ThreadNode;
  replies?: ThreadNode[];
}

interface LikeData {
  actor: BlueskyProfile;
  indexedAt: string;
  targetDid?: string;
}

interface RepostData extends BlueskyProfile {
  targetDid?: string;
}

interface GraphNode {
  id: string;
  handle: string;
  displayName: string;
  avatar?: string;
  types: Set<string>;
  isFocus: boolean;
  followers: number;
  socialStatus: 'mutual' | 'follows_op' | 'followed_by_op' | 'none';
  postData?: {
    uri: string;
    text: string;
    embed?: BlueskyPost['embed'];
    indexedAt?: string;
    cid: string;
  };
  primaryType?: string;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  type: string;
  isOpAction?: boolean;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

interface RawData {
  thread: ThreadNode | null;
  likes: LikeData[];
  reposts: RepostData[];
  focusUri: string;
}

interface DeepData {
  deepLikes: LikeData[];
  deepReposts: RepostData[];
}

interface Stats {
  nodes: number;
  likes: number;
  reposts: number;
  replies: number;
}

interface PostPreview {
  author: BlueskyProfile;
  record: { text: string };
  embed?: BlueskyPost['embed'];
  parent?: ThreadNode;
  uri: string;
}

// --- API & Data Utilities ---

const BSKY_PUBLIC_API = 'https://public.api.bsky.app/xrpc';

const parsePostUrl = (url: string): ParsedUrl | null => {
  try {
    const urlObj = new URL(url);
    const pathParts = urlObj.pathname.split('/').filter(Boolean);
    if (pathParts.length >= 4 && pathParts[0] === 'profile' && pathParts[2] === 'post') {
      return {
        handle: pathParts[1],
        rkey: pathParts[3]
      };
    }
    return null;
  } catch {
    return null;
  }
};

const resolveHandle = async (handle: string): Promise<string> => {
  if (handle.startsWith('did:')) return handle;

  const maxRetries = 2;
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const controller = new AbortController();
    const timeoutMs = attempt === 0 ? 15000 : 25000;
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(
        `${BSKY_PUBLIC_API}/com.atproto.identity.resolveHandle?handle=${handle}`,
        { signal: controller.signal }
      );
      clearTimeout(timeoutId);

      if (!res.ok) throw new Error(`Could not resolve handle: ${handle}`);
      const data = await res.json();
      return data.did;
    } catch (e) {
      clearTimeout(timeoutId);
      lastError = e instanceof Error ? e : new Error('Unknown error');

      // Only retry on timeout
      if (lastError.name === 'AbortError' && attempt < maxRetries) {
        await new Promise(r => setTimeout(r, 500));
        continue;
      }
      break;
    }
  }

  console.error("Resolve Error", lastError);
  if (lastError?.name === 'AbortError') {
    throw new Error(`Request timed out resolving ${handle}`);
  }
  throw new Error(`Failed to verify user: ${handle}`);
};

// --- Cache Utilities ---
const CACHE_PREFIX = 'bsky-viz-cache-';
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes for fresh data
const CACHE_STALE_TTL = 60 * 60 * 1000; // 1 hour before requiring full refresh

interface CachedData<T> {
  data: T;
  timestamp: number;
  checksum: string; // Based on interaction counts
}

const generateChecksum = (likes: number, reposts: number, replies: number): string => {
  return `${likes}-${reposts}-${replies}`;
};

const getCachedData = <T,>(key: string): CachedData<T> | null => {
  try {
    const cached = localStorage.getItem(CACHE_PREFIX + key);
    if (!cached) return null;
    return JSON.parse(cached) as CachedData<T>;
  } catch {
    return null;
  }
};

const setCachedData = <T,>(key: string, data: T, checksum: string): void => {
  try {
    const cacheEntry: CachedData<T> = {
      data,
      timestamp: Date.now(),
      checksum
    };
    localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(cacheEntry));

    // Clean up old cache entries (keep only last 20)
    const keys = Object.keys(localStorage).filter(k => k.startsWith(CACHE_PREFIX));
    if (keys.length > 20) {
      const entries = keys.map(k => ({
        key: k,
        time: JSON.parse(localStorage.getItem(k) || '{}').timestamp || 0
      })).sort((a, b) => a.time - b.time);

      // Remove oldest entries
      entries.slice(0, keys.length - 20).forEach(e => localStorage.removeItem(e.key));
    }
  } catch {
    // localStorage might be full or disabled
  }
};

const isCacheFresh = (timestamp: number): boolean => {
  return Date.now() - timestamp < CACHE_TTL;
};

const isCacheStale = (timestamp: number): boolean => {
  return Date.now() - timestamp > CACHE_STALE_TTL;
};

const fetchWithTimeout = async (url: string, timeoutMs = 20000): Promise<Response> => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timeoutId);
    return res;
  } catch (e) {
    clearTimeout(timeoutId);
    throw e;
  }
};

const fetchAllPages = async <T,>(
  endpoint: string,
  params: Record<string, string>,
  key: string,
  onProgress?: ((count: number) => void) | null,
  limit = 5000
): Promise<T[]> => {
  let allItems: T[] = [];
  let cursor: string | null = null;
  const paramStr = new URLSearchParams(params).toString();
  let consecutiveFailures = 0;

  do {
    const url = `${endpoint}?${paramStr}&limit=100${cursor ? `&cursor=${cursor}` : ''}`;
    try {
      const res = await fetchWithTimeout(url, 20000);
      if (!res.ok) {
        consecutiveFailures++;
        if (consecutiveFailures >= 2) break;
        await new Promise(r => setTimeout(r, 1000));
        continue;
      }
      consecutiveFailures = 0;

      const data = await res.json();
      const items = data[key] || [];
      allItems = [...allItems, ...items];
      cursor = data.cursor;

      if (onProgress) onProgress(allItems.length);
      if (allItems.length >= limit) break;
      if (cursor) await new Promise(r => setTimeout(r, 20));
    } catch (e) {
      // On timeout/network error, try once more then continue with what we have
      consecutiveFailures++;
      if (consecutiveFailures >= 2) break;
      await new Promise(r => setTimeout(r, 1000));
    }

  } while (cursor);

  return allItems;
};

// Batch fetch profile details
const fetchNodeMetrics = async (
  dids: string[],
  onProgress?: (curr: number, total: number) => void
): Promise<Map<string, number>> => {
  const uniqueDids = [...new Set(dids)];
  const chunkData: BlueskyProfile[] = [];
  const chunkSize = 25;

  for (let i = 0; i < uniqueDids.length; i += chunkSize) {
    const chunk = uniqueDids.slice(i, i + chunkSize);
    const query = chunk.map(did => `actors=${encodeURIComponent(did)}`).join('&');

    try {
      const res = await fetchWithTimeout(
        `${BSKY_PUBLIC_API}/app.bsky.actor.getProfiles?${query}`,
        15000
      );
      if (res.ok) {
        const json = await res.json();
        chunkData.push(...(json.profiles || []));
      }
    } catch (e) {
      console.warn("Failed to fetch chunk metrics", e);
    }

    if (onProgress) onProgress(Math.min(i + chunkSize, uniqueDids.length), uniqueDids.length);
    await new Promise(r => setTimeout(r, 50));
  }

  const metricsMap = new Map<string, number>();
  chunkData.forEach(p => {
    metricsMap.set(p.did, p.followersCount || 0);
  });
  return metricsMap;
};

// --- Deep Interaction Logic ---

const fetchDeepInteractions = async (
  threadData: ThreadNode,
  onProgress?: (curr: number, total: number) => void
): Promise<DeepData> => {
  const replies: BlueskyPost[] = [];
  const traverse = (node: ThreadNode | null) => {
    if (!node) return;
    if (node.post && node.replies) {
      replies.push(node.post);
    }
    if (node.replies) node.replies.forEach(traverse);
  };
  if (threadData.replies) threadData.replies.forEach(traverse);

  const activeReplies = replies
    .filter(p => ((p.likeCount || 0) > 0 || (p.repostCount || 0) > 0))
    .sort((a, b) => ((b.likeCount || 0) + (b.repostCount || 0)) - ((a.likeCount || 0) + (a.repostCount || 0)))
    .slice(0, 200);

  const deepLikes: LikeData[] = [];
  const deepReposts: RepostData[] = [];

  let completed = 0;
  const total = activeReplies.length;

  for (const reply of activeReplies) {
    completed++;
    if (onProgress) onProgress(completed, total);

    const uri = reply.uri;
    const authorDid = reply.author.did;

    const [likes, reposts] = await Promise.all([
      fetchAllPages<LikeData>(`${BSKY_PUBLIC_API}/app.bsky.feed.getLikes`, { uri }, 'likes', null, 300),
      fetchAllPages<BlueskyProfile>(`${BSKY_PUBLIC_API}/app.bsky.feed.getRepostedBy`, { uri }, 'repostedBy', null, 300)
    ]);

    likes.forEach(l => deepLikes.push({ ...l, targetDid: authorDid }));
    reposts.forEach(r => deepReposts.push({ ...r, targetDid: authorDid }));

    await new Promise(r => setTimeout(r, 50));
  }

  return { deepLikes, deepReposts };
};

/* --- Social Graph Logic --- (UI removed, preserved for future use)

interface SocialScanResult {
  newLinks: GraphLink[];
  nodeUpdates: Map<string, { socialStatus: GraphNode['socialStatus'] }>;
}

const scanSocialConnections = async (
  nodes: GraphNode[],
  focusDid: string | undefined,
  onProgress: (status: string) => void
): Promise<SocialScanResult> => {
  const nodeSet = new Set(nodes.map(n => n.id));
  const newLinks: GraphLink[] = [];
  const nodeUpdates = new Map<string, { socialStatus: GraphNode['socialStatus'] }>();

  if (focusDid) {
    onProgress("☕ Fetching who OP follows... (this may take a few minutes)");
    try {
      // Fetch who OP follows
      const opFollows = await fetchAllPages<BlueskyProfile>(
        `${BSKY_PUBLIC_API}/app.bsky.graph.getFollows`,
        { actor: focusDid },
        'follows',
        (count) => onProgress(`☕ Fetching OP's follows (${count} found)... grab a tea!`),
        5000
      );

      onProgress(`☕ Fetching OP's followers... (found ${opFollows.length} follows)`);
      // Fetch who follows OP
      const opFollowers = await fetchAllPages<BlueskyProfile>(
        `${BSKY_PUBLIC_API}/app.bsky.graph.getFollowers`,
        { actor: focusDid },
        'followers',
        (count) => onProgress(`☕ Fetching OP's followers (${count} found)...`),
        5000
      );

      const opFollowsSet = new Set(opFollows.map(f => f.did));
      const opFollowersSet = new Set(opFollowers.map(f => f.did));

      nodes.forEach(node => {
        if (node.id === focusDid) return;

        const isFollowing = opFollowsSet.has(node.id); // OP follows Node
        const isFollower = opFollowersSet.has(node.id); // Node follows OP

        let socialStatus: GraphNode['socialStatus'] = 'none';
        if (isFollowing && isFollower) socialStatus = 'mutual';
        else if (isFollowing) socialStatus = 'followed_by_op';
        else if (isFollower) socialStatus = 'follows_op';

        if (socialStatus !== 'none') {
          nodeUpdates.set(node.id, { socialStatus });
        }

        // Add visual link if OP follows them (strong connection)
        if (isFollowing) {
          newLinks.push({ source: focusDid, target: node.id, type: 'follow', isOpAction: true });
        }
      });
    } catch (e) {
      console.warn("Failed to fetch OP social graph", e);
    }
  }

  const topNodes = [...nodes].sort((a, b) => b.followers - a.followers).slice(0, 50);
  onProgress(`☕ Scanning top ${topNodes.length} accounts for interconnections... this takes a while!`);

  let scanned = 0;
  for (const node of topNodes) {
    if (node.id === focusDid) continue;

    scanned++;
    const handle = node.handle || 'user';
    onProgress(`☕ Checking who @${handle} follows (${scanned}/${topNodes.length})...`);

    try {
      const follows = await fetchAllPages<BlueskyProfile>(
        `${BSKY_PUBLIC_API}/app.bsky.graph.getFollows`,
        { actor: node.id },
        'follows',
        null,
        1000
      );

      follows.forEach(followed => {
        if (nodeSet.has(followed.did) && followed.did !== node.id) {
          newLinks.push({
            source: node.id,
            target: followed.did,
            type: 'follow',
            isOpAction: false
          });
        }
      });
      await new Promise(r => setTimeout(r, 100));

    } catch {
      // Ignore private accounts / errors
    }
  }

  return { newLinks, nodeUpdates };
};
*/


const countReplies = (thread: ThreadNode | null): number => {
  if (!thread) return 0;
  let count = 0;
  const traverse = (node: ThreadNode) => {
    if (node.replies) {
      count += node.replies.length;
      node.replies.forEach(traverse);
    }
  };
  traverse(thread);
  return count;
};

const fetchInteractionData = async (
  postUrl: string,
  setStatus: (status: string) => void
): Promise<RawData> => {
  const parsed = parsePostUrl(postUrl);
  if (!parsed) throw new Error('Invalid Bluesky Post URL');

  setStatus('Resolving Handle...');
  const did = await resolveHandle(parsed.handle);
  const uri = `at://${did}/app.bsky.feed.post/${parsed.rkey}`;
  const cacheKey = `${did}-${parsed.rkey}`;

  // Check cache first
  const cached = getCachedData<RawData>(cacheKey);

  // First, do a quick fetch to get current counts for checksum
  setStatus('Checking for updates...');
  const threadRes = await fetchWithTimeout(
    `${BSKY_PUBLIC_API}/app.bsky.feed.getPostThread?uri=${uri}&depth=1000&parentHeight=1`,
    25000
  );
  let threadData: ThreadNode | null = null;
  if (threadRes.ok) {
    const json = await threadRes.json();
    threadData = json.thread;
  } else {
    throw new Error("Post not found or API error.");
  }

  // Get current counts from the post metadata
  const currentLikes = threadData?.post?.likeCount || 0;
  const currentReposts = threadData?.post?.repostCount || 0;
  const currentReplies = threadData?.post?.replyCount || 0;
  const currentChecksum = generateChecksum(currentLikes, currentReposts, currentReplies);

  // If we have fresh cache with matching checksum, use it
  if (cached && isCacheFresh(cached.timestamp) && cached.checksum === currentChecksum) {
    setStatus('Using cached data (no changes detected)...');
    // Return cached data but with fresh thread (for any content updates)
    return {
      ...cached.data,
      thread: threadData // Always use fresh thread for latest content
    };
  }

  // If cache is not stale and checksum matches, we can still use it (stale-while-revalidate)
  if (cached && !isCacheStale(cached.timestamp) && cached.checksum === currentChecksum) {
    setStatus('Using cached data...');
    return {
      ...cached.data,
      thread: threadData
    };
  }

  // Cache miss or stale - fetch fresh data
  setStatus('Fetching Likes...');
  const likesData = await fetchAllPages<LikeData>(
    `${BSKY_PUBLIC_API}/app.bsky.feed.getLikes`,
    { uri },
    'likes',
    (count) => setStatus(`Fetching Likes (${count})...`)
  );

  setStatus('Fetching Reposts...');
  const repostsData = await fetchAllPages<RepostData>(
    `${BSKY_PUBLIC_API}/app.bsky.feed.getRepostedBy`,
    { uri },
    'repostedBy',
    (count) => setStatus(`Fetching Reposts (${count})...`)
  );

  const result: RawData = {
    thread: threadData,
    likes: likesData,
    reposts: repostsData,
    focusUri: uri
  };

  // Cache the result with checksum based on actual fetched data
  const actualChecksum = generateChecksum(likesData.length, repostsData.length, countReplies(threadData));
  setCachedData(cacheKey, result, actualChecksum);

  return result;
};

const processGraphData = (
  data: RawData,
  metricsMap: Map<string, number> | null,
  socialUpdates: Map<string, { socialStatus: GraphNode['socialStatus'] }> | null = null,
  extraLinks: GraphLink[] = [],
  deepData: DeepData | null = null
): GraphData => {
  const nodes = new Map<string, GraphNode>();
  const links: GraphLink[] = [];

  const addNode = (item: BlueskyPost | BlueskyProfile | LikeData, type: string, isFocus = false) => {
    const profile = ('author' in item ? item.author : 'actor' in item ? item.actor : item) as BlueskyProfile;
    const did = profile.did;
    if (!did) return;

    let postData: GraphNode['postData'] = undefined;
    if ('record' in item && 'uri' in item) {
      const post = item as BlueskyPost;
      postData = {
        uri: post.uri,
        text: post.record.text,
        embed: post.embed,
        indexedAt: post.indexedAt,
        cid: post.cid
      };
    }

    if (!nodes.has(did)) {
      nodes.set(did, {
        id: did,
        handle: profile.handle,
        displayName: profile.displayName || profile.handle,
        avatar: profile.avatar,
        types: new Set([type]),
        isFocus: isFocus,
        followers: metricsMap ? (metricsMap.get(did) || 0) : 0,
        socialStatus: 'none',
        postData: postData
      });
    } else {
      const node = nodes.get(did)!;
      node.types.add(type);
      if (isFocus) node.isFocus = true;
      if (!node.postData && postData) {
        node.postData = postData;
      }
    }
  };

  if (data.thread) {
    const processReplies = (current: ThreadNode) => {
      if (!current || !current.replies) return;
      current.replies.forEach(reply => {
        if (reply.$type === 'app.bsky.feed.defs#notFoundPost' || reply.$type === 'app.bsky.feed.defs#blockedPost') return;
        addNode(reply.post, 'reply');

        links.push({
          source: reply.post.author.did,
          target: current.post.author.did,
          type: 'reply'
        });

        processReplies(reply);
      });
    };

    if (data.thread.post) {
      addNode(data.thread.post, 'focus', true);
      processReplies(data.thread);
    }
  }

  const focusDid = data.thread?.post?.author?.did;
  if (focusDid) {
    data.likes.forEach(like => {
      addNode(like, 'like');
      links.push({ source: like.actor.did, target: focusDid, type: 'like' });
    });

    data.reposts.forEach(repost => {
      addNode(repost, 'repost');
      links.push({ source: repost.did, target: focusDid, type: 'repost' });
    });
  }

  if (deepData) {
    if (deepData.deepLikes) {
      deepData.deepLikes.forEach(like => {
        addNode(like, 'like');
        links.push({ source: like.actor.did, target: like.targetDid!, type: 'deep-like' });
      });
    }
    if (deepData.deepReposts) {
      deepData.deepReposts.forEach(repost => {
        addNode(repost, 'repost');
        links.push({ source: repost.did, target: repost.targetDid!, type: 'deep-repost' });
      });
    }
  }

  if (socialUpdates) {
    socialUpdates.forEach((update, did) => {
      if (nodes.has(did)) {
        const node = nodes.get(did)!;
        if (update.socialStatus) node.socialStatus = update.socialStatus;
      }
    });
  }

  if (extraLinks) {
    links.push(...extraLinks);
  }

  const finalNodes = Array.from(nodes.values()).map(n => {
    let primaryType = 'like';
    if (n.isFocus) primaryType = 'focus';
    else if (n.types.has('reply')) primaryType = 'reply';
    else if (n.types.has('repost')) primaryType = 'repost';
    return { ...n, primaryType };
  });

  return { nodes: finalNodes, links };
};

// --- D3 Component ---

interface ForceGraphProps {
  data: GraphData;
  scalingMode: 'uniform' | 'relative' | 'actual';
  onNodeClick: (node: GraphNode) => void;
  svgRef: React.RefObject<SVGSVGElement | null>;
}

const ForceGraph = ({ data, scalingMode, onNodeClick, svgRef }: ForceGraphProps) => {
  const containerRef = useRef<HTMLDivElement>(null);

  const getNodeRadius = useCallback((d: GraphNode, isLargeGraph: boolean): number => {
    let baseRadius: number;

    if (scalingMode === 'uniform') {
      baseRadius = isLargeGraph ? 4 : 6;
    } else if (scalingMode === 'actual') {
      const raw = Math.pow(d.followers, 0.5) * 0.12;
      baseRadius = Math.max(3, raw);
    } else {
      // Relative: logarithmic scale, much gentler range (4-20)
      const logFollowers = d.followers > 0 ? Math.log10(d.followers + 1) : 0;
      const normalized = Math.min(logFollowers / 6, 1); // 6 = ~1M followers as max
      baseRadius = 4 + (normalized * 16); // Range: 4-20
      baseRadius = isLargeGraph ? baseRadius * 0.7 : baseRadius;
    }

    if (d.isFocus) {
      return Math.max(baseRadius, isLargeGraph ? 20 : 30);
    }

    return baseRadius;
  }, [scalingMode]);

  useEffect(() => {
    if (!data || !containerRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;
    const nodeCount = data.nodes.length;
    const isLargeGraph = nodeCount > 500;

    const focusNode = data.nodes.find(n => n.isFocus);
    if (focusNode) {
      focusNode.fx = 0;
      focusNode.fy = 0;
    }

    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3.select(svgRef.current)
      .attr("viewBox", [-width / 2, -height / 2, width, height].join(' '))
      .style("cursor", "grab");

    // Define Filters (Glow)
    const defs = svg.append("defs");
    const filter = defs.append("filter")
      .attr("id", "glow")
      .attr("x", "-50%")
      .attr("y", "-50%")
      .attr("width", "200%")
      .attr("height", "200%");
    filter.append("feGaussianBlur")
      .attr("stdDeviation", "2.5")
      .attr("result", "coloredBlur");
    const feMerge = filter.append("feMerge");
    feMerge.append("feMergeNode").attr("in", "coloredBlur");
    feMerge.append("feMergeNode").attr("in", "SourceGraphic");

    defs.selectAll("marker")
      .data(["end-arrow"])
      .enter().append("marker")
      .attr("id", String)
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 15)
      .attr("refY", 0)
      .attr("markerWidth", 5)
      .attr("markerHeight", 5)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", "#64748b");

    const g = svg.append("g");

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 10])
      .on("zoom", (event) => g.attr("transform", event.transform));

    // Apply zoom behavior to SVG
    svg.call(zoom as any);

    // Forces
    const simulation = d3.forceSimulation<GraphNode>(data.nodes)
      .force("link", d3.forceLink<GraphNode, GraphLink>(data.links).id(d => d.id).distance(d => {
        // Follow links (social graph) - tight
        if (d.type === 'follow') return 50;
        // Reply chains - medium tight
        if (d.type === 'reply') return isLargeGraph ? 50 : 80;
        // Deep interactions (on replies) - relative to their parent
        if (d.type === 'deep-like' || d.type === 'deep-repost') return 40;
        // Direct interactions with focus post - all similar distance
        // Reposts, likes treated equally
        return isLargeGraph ? 80 : 140;
      }))
      .force("charge", d3.forceManyBody<GraphNode>().strength(d => {
        const r = getNodeRadius(d, isLargeGraph);

        if (d.isFocus) {
          return -3000 - (r * 50);
        }

        // Base repulsion
        let strength = isLargeGraph ? -40 : -120;
        strength -= r * (isLargeGraph ? 5 : 8);

        // Nodes with multiple interaction types get pulled closer (less repulsion)
        const interactionCount = d.types.size;
        if (interactionCount > 1) {
          strength *= 0.4; // Much less repulsion for multi-interaction users
        }

        // Social status affects positioning - mutuals closest, then followed_by_op
        if (d.socialStatus === 'mutual') {
          strength *= 0.3; // Very low repulsion - stay close
        } else if (d.socialStatus === 'followed_by_op') {
          strength *= 0.5; // Low repulsion
        } else if (d.socialStatus === 'follows_op') {
          strength *= 0.7; // Slightly less repulsion
        }

        return strength;
      }))
      .force("collide", d3.forceCollide<GraphNode>().radius(d => {
        const r = getNodeRadius(d, isLargeGraph);
        if (d.isFocus) return r + 30;
        return r + (isLargeGraph ? 3 : 6);
      }).iterations(2))
      .force("x", d3.forceX().strength(0.03))
      .force("y", d3.forceY().strength(0.03));

    simulation.stop();
    simulation.tick(100);
    simulation.restart();

    // Links
    const link = g.append("g")
      .attr("stroke-opacity", 0)
      .selectAll("line")
      .data(data.links)
      .join("line")
      .attr("stroke", d => {
        if (d.type === 'reply') return "#60A5FA";
        if (d.type === 'like') return "#F472B6";
        if (d.type === 'repost') return "#FACC15"; // Yellow
        if (d.type === 'deep-like') return "#EC4899";
        if (d.type === 'deep-repost') return "#FDE047"; // Light yellow
        if (d.type === 'follow') return "#94a3b8";
        return "#999";
      })
      .attr("stroke-width", d => {
        if (d.type === 'follow' || d.type === 'deep-like' || d.type === 'deep-repost') return 0.5;
        const base = d.type === 'reply' ? 1.5 : 1;
        return isLargeGraph ? base * 0.5 : base;
      })
      .attr("stroke-dasharray", d => {
        if (d.type === 'follow') return "2 2";
        if (d.type === 'deep-like' || d.type === 'deep-repost') return "2 1";
        if (d.type === 'reply') return "0";
        return "3 3";
      })
      .attr("marker-end", d => d.type === 'reply' ? "url(#end-arrow)" : null);

    link
      .attr("x1", d => (d.source as GraphNode).x || 0)
      .attr("y1", d => (d.source as GraphNode).y || 0)
      .attr("x2", d => (d.target as GraphNode).x || 0)
      .attr("y2", d => (d.target as GraphNode).y || 0);

    // Nodes
    const node = g.append("g")
      .attr("stroke-width", 2)
      .selectAll("circle")
      .data(data.nodes)
      .join("circle")
      .attr("r", d => getNodeRadius(d, isLargeGraph))
      .attr("fill", d => {
        if (d.isFocus) return "#fff";
        if (d.primaryType === 'reply') return "#3B82F6";
        if (d.primaryType === 'like') return "#EC4899";
        if (d.primaryType === 'repost') return "#FACC15"; // Yellow
        return "#9CA3AF";
      })
      .attr("stroke", d => {
        if (d.isFocus) return "#000";
        if (d.socialStatus === 'mutual') return "#22c55e"; // Green Stroke
        if (d.socialStatus === 'followed_by_op') return "#3b82f6"; // Blue Stroke
        if (d.socialStatus === 'follows_op') return "#f59e0b"; // Amber Stroke (Fan)
        return "#1e293b"; // Dark Slate
      })
      .attr("filter", d => d.primaryType === 'repost' ? "url(#glow)" : null) // Add Glow to Reposts (Yellow)
      .attr("opacity", 0)
      .style("cursor", "pointer")
      .call(drag(simulation) as any);

    node
      .attr("cx", d => d.x || 0)
      .attr("cy", d => d.y || 0);

    // Labels
    const labels = g.append("g")
      .selectAll("text")
      .data(data.nodes.filter(n => n.isFocus || (n.followers > 5000 && scalingMode !== 'uniform') || n.socialStatus === 'mutual' || n.socialStatus === 'followed_by_op'))
      .join("text")
      .text(d => d.handle)
      .attr("font-size", d => {
        const r = getNodeRadius(d, isLargeGraph);
        if (scalingMode === 'uniform') return 10;
        return Math.max(8, Math.min(r * 0.8, 24));
      })
      .attr("fill", "white")
      .attr("text-anchor", "middle")
      .attr("dy", d => {
        const r = getNodeRadius(d, isLargeGraph);
        return r + 12;
      })
      .style("pointer-events", "none")
      .style("opacity", 0)
      .style("text-shadow", "0 2px 4px rgba(0,0,0,0.9)");

    labels
      .attr("x", d => d.x || 0)
      .attr("y", d => d.y || 0);

    node.transition().duration(800).attr("opacity", 1);
    link.transition().duration(800).attr("stroke-opacity", 0.5);
    labels.transition().delay(300).duration(800).style("opacity", 0.9);

    // Handle both click and touch for node selection
    node
      .on("click", (event, d) => {
        event.preventDefault();
        event.stopPropagation();
        onNodeClick(d);
      })
      .on("touchend", (event, d) => {
        // Only trigger if it wasn't a drag
        if (!event.defaultPrevented) {
          event.preventDefault();
          event.stopPropagation();
          onNodeClick(d);
        }
      });

    simulation.on("tick", () => {
      link
        .attr("x1", d => (d.source as GraphNode).x || 0)
        .attr("y1", d => (d.source as GraphNode).y || 0)
        .attr("x2", d => (d.target as GraphNode).x || 0)
        .attr("y2", d => (d.target as GraphNode).y || 0);

      node
        .attr("cx", d => d.x || 0)
        .attr("cy", d => d.y || 0);

      labels
        .attr("x", d => d.x || 0)
        .attr("y", d => d.y || 0);
    });

    return () => { simulation.stop(); };
  }, [data, onNodeClick, getNodeRadius, scalingMode]);

  const drag = (simulation: d3.Simulation<GraphNode, GraphLink>) => {
    function dragstarted(event: d3.D3DragEvent<SVGCircleElement, GraphNode, GraphNode>) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }
    function dragged(event: d3.D3DragEvent<SVGCircleElement, GraphNode, GraphNode>) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }
    function dragended(event: d3.D3DragEvent<SVGCircleElement, GraphNode, GraphNode>) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }
    return d3.drag<SVGCircleElement, GraphNode>().on("start", dragstarted).on("drag", dragged).on("end", dragended);
  };

  return (
    <div ref={containerRef} className="w-full h-full bg-slate-950 rounded-sm overflow-hidden relative shadow-inner touch-none">
      <svg ref={svgRef} className="w-full h-full block touch-none"></svg>
      {/* Legend - Desktop Only */}
      <div className="hidden md:block absolute bottom-4 right-4 bg-slate-900/90 p-3 rounded-sm border border-slate-800 backdrop-blur shadow-lg text-xs text-slate-300 pointer-events-none select-none max-h-60 overflow-y-auto">
        <div className="space-y-2">
          <div className="flex items-center space-x-2"><span className="w-3 h-3 rounded-full bg-white border border-slate-600"></span><span>Post</span></div>
          <div className="flex items-center space-x-2"><span className="w-3 h-3 rounded-full bg-blue-500"></span><span>Reply</span></div>
          <div className="flex items-center space-x-2"><span className="w-3 h-3 rounded-full bg-pink-500"></span><span>Like</span></div>
          <div className="flex items-center space-x-2"><span className="w-3 h-3 rounded-full bg-yellow-400 shadow-[0_0_8px_rgba(250,204,21,0.8)]"></span><span>Repost</span></div>
        </div>
        <div className="border-t border-slate-700 pt-2 mt-2">
          <div className="space-y-2">
            <div className="flex items-center space-x-2"><span className="w-3 h-3 rounded-full border-2 border-green-500 bg-slate-800"></span><span>Mutual</span></div>
            <div className="flex items-center space-x-2"><span className="w-3 h-3 rounded-full border-2 border-blue-500 bg-slate-800"></span><span>By OP</span></div>
            <div className="flex items-center space-x-2"><span className="w-3 h-3 rounded-full border-2 border-amber-500 bg-slate-800"></span><span>Follows</span></div>
            <div className="flex items-center space-x-2"><span className="w-8 border-t border-dashed border-slate-400 h-0 block"></span><span>Connection</span></div>
          </div>
        </div>
      </div>
    </div>
  );
};

// --- Intro Tooltip Component ---

interface IntroTooltipProps {
  onDismiss: () => void;
  onLoadDemo: () => void;
  onLoadUrl: (url: string) => void;
}

const IntroTooltip = ({ onDismiss, onLoadDemo, onLoadUrl }: IntroTooltipProps) => {
  const [postUrl, setPostUrl] = useState('');
  const [handle, setHandle] = useState('');
  const [handleLoading, setHandleLoading] = useState(false);
  const [handleError, setHandleError] = useState<string | null>(null);

  const handleSubmitUrl = () => {
    if (postUrl.trim()) {
      onLoadUrl(postUrl.trim());
    }
  };

  const handleSubmitHandle = async () => {
    const cleanHandle = handle.trim().replace(/^@/, '');
    if (!cleanHandle || handleLoading) return;

    setHandleLoading(true);
    setHandleError(null);

    // Retry logic for mobile networks
    const maxRetries = 2;
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      // Create abort controller for timeout - longer timeout for mobile (20s first try, 30s retry)
      const controller = new AbortController();
      const timeoutMs = attempt === 0 ? 20000 : 30000;
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      try {
        // Fetch user's most recent post
        const res = await fetch(
          `${BSKY_PUBLIC_API}/app.bsky.feed.getAuthorFeed?actor=${cleanHandle}&limit=1&filter=posts_no_replies`,
          { signal: controller.signal }
        );
        clearTimeout(timeoutId);

        if (!res.ok) {
          throw new Error('User not found');
        }
        const data = await res.json();

        if (!data.feed || data.feed.length === 0) {
          throw new Error('No posts found');
        }

        const post = data.feed[0].post;
        const rkey = post.uri.split('/').pop();
        const newUrl = `https://bsky.app/profile/${post.author.handle}/post/${rkey}`;
        setHandleLoading(false);
        onLoadUrl(newUrl);
        return; // Success - exit the function
      } catch (e) {
        clearTimeout(timeoutId);
        lastError = e instanceof Error ? e : new Error('Failed to load');

        // Only retry on timeout/network errors, not on user not found
        if (lastError.name !== 'AbortError' && lastError.message !== 'User not found') {
          break; // Don't retry on non-network errors
        }

        // If we have retries left and it was a timeout, wait briefly and retry
        if (attempt < maxRetries && lastError.name === 'AbortError') {
          await new Promise(r => setTimeout(r, 500));
          continue;
        }
      }
    }

    // All retries exhausted
    if (lastError?.name === 'AbortError') {
      setHandleError('Request timed out - try again');
    } else {
      setHandleError(lastError?.message || 'Failed to load');
    }
    setHandleLoading(false);
  };

  return (
    <div className="fixed left-1/2 -translate-x-1/2 top-24 sm:top-28 z-50 w-[min(28rem,calc(100%-2rem))] sm:w-[min(32rem,calc(100%-3rem))] p-4 sm:p-5 bg-slate-900/95 backdrop-blur-lg border border-slate-700 rounded-sm shadow-2xl animate-in fade-in slide-in-from-top-4 duration-500 max-h-[70vh] overflow-y-auto">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          <Network className="w-5 h-5 text-blue-400" />
          Bluesky Post Visualizer
        </h3>
        <button onClick={onDismiss} className="text-slate-400 hover:text-white"><X className="w-5 h-5" /></button>
      </div>

      <p className="text-sm text-slate-300 mb-4">
        See who's engaging with any Bluesky post. Each node is a person — the closer to the center, the more connected they are to the conversation.
      </p>

      {/* Quick Start Section */}
      <div className="space-y-3 mb-4">
        {/* Paste URL */}
        <div className="bg-slate-800/50 p-3 rounded-sm border border-slate-700/50">
          <label className="text-white block mb-2 uppercase tracking-wider text-[10px] font-bold">Paste a Post URL</label>
          <form onSubmit={(e) => { e.preventDefault(); handleSubmitUrl(); }} className="flex gap-2">
            <input
              type="url"
              inputMode="url"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              placeholder="https://bsky.app/profile/.../post/..."
              value={postUrl}
              onChange={(e) => setPostUrl(e.target.value)}
              className="flex-1 bg-slate-950 border border-slate-600 rounded-sm px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              disabled={!postUrl.trim()}
              className="bg-blue-600 hover:bg-blue-500 active:bg-blue-400 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 rounded-sm font-medium text-sm transition-colors flex items-center gap-1 touch-manipulation"
            >
              <Search className="w-4 h-4" />
            </button>
          </form>
        </div>

        {/* Or divider */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-slate-700"></div>
          <span className="text-slate-500 text-xs">or</span>
          <div className="flex-1 h-px bg-slate-700"></div>
        </div>

        {/* Handle Input */}
        <div className="bg-slate-800/50 p-3 rounded-sm border border-slate-700/50">
          <label className="text-white block mb-2 uppercase tracking-wider text-[10px] font-bold">View Someone's Latest Post</label>
          <form onSubmit={(e) => { e.preventDefault(); handleSubmitHandle(); }} className="flex gap-2">
            <input
              type="text"
              inputMode="text"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              placeholder="handle.bsky.social"
              value={handle}
              onChange={(e) => { setHandle(e.target.value); setHandleError(null); }}
              className="flex-1 bg-slate-950 border border-slate-600 rounded-sm px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              disabled={!handle.trim() || handleLoading}
              className="bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-400 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 rounded-sm font-medium text-sm transition-colors flex items-center gap-1 touch-manipulation"
            >
              {handleLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            </button>
          </form>
          {handleError && <p className="text-red-400 text-xs mt-2">{handleError}</p>}
        </div>

        {/* Or divider */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-slate-700"></div>
          <span className="text-slate-500 text-xs">or</span>
          <div className="flex-1 h-px bg-slate-700"></div>
        </div>

        {/* Demo Button */}
        <button
          onClick={onLoadDemo}
          className="w-full bg-emerald-600 hover:bg-emerald-500 text-white py-3 rounded-sm font-bold text-sm transition-colors flex items-center justify-center gap-2"
        >
          <Zap className="w-4 h-4 text-yellow-300 fill-current" /> Load Demo Visualization
        </button>
      </div>

      {/* Collapsible Help Section */}
      <details className="group">
        <summary className="cursor-pointer text-slate-400 hover:text-white text-xs flex items-center gap-2 mb-3">
          <HelpCircle className="w-4 h-4" />
          <span>How to read the graph</span>
          <ChevronDown className="w-4 h-4 group-open:rotate-180 transition-transform" />
        </summary>

        <div className="space-y-3 text-xs text-slate-300">
          <div className="bg-slate-800/50 p-3 rounded-sm border border-slate-700/50">
            <strong className="text-white block mb-2 uppercase tracking-wider text-[10px]">How to Read the Graph</strong>
            <div className="space-y-1.5">
              <p><span className="text-white font-medium">Center:</span> The original post author (white node)</p>
              <p><span className="text-white font-medium">Node size:</span> Follower count — bigger = more reach</p>
              <p><span className="text-white font-medium">Distance from center:</span> Relationship strength</p>
              <p><span className="text-white font-medium">Multiple interactions:</span> Users who like + reply + repost get pulled closer</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-800/50 p-3 rounded-sm border border-slate-700/50">
              <strong className="text-white block mb-2 uppercase tracking-wider text-[10px]">Interaction Type</strong>
              <div className="space-y-1.5">
                <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-pink-500"></span> Like</span>
                <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span> Reply</span>
                <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-yellow-400 shadow-sm shadow-yellow-400"></span> Repost</span>
              </div>
            </div>
            <div className="bg-slate-800/50 p-3 rounded-sm border border-slate-700/50">
              <strong className="text-white block mb-2 uppercase tracking-wider text-[10px]">Social Connection</strong>
              <div className="space-y-1.5">
                <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full border-2 border-green-500 bg-slate-700"></span> Mutual follow</span>
                <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full border-2 border-blue-500 bg-slate-700"></span> OP follows them</span>
                <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full border-2 border-amber-500 bg-slate-700"></span> They follow OP</span>
              </div>
            </div>
          </div>

          <div className="bg-slate-800/50 p-3 rounded-sm border border-slate-700/50">
            <strong className="text-white block mb-2 uppercase tracking-wider text-[10px]">Tips</strong>
            <div className="space-y-1.5 text-slate-400">
              <p>• Click any node to see their profile and interactions</p>
              <p>• Drag nodes to rearrange, scroll/pinch to zoom</p>
              <p>• Click a reply node to visualize that sub-thread</p>
            </div>
          </div>
        </div>
      </details>
    </div>
  );
};

// --- App Component ---

export default function App() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [showIntro, setShowIntro] = useState(true);

  // Data State
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [, setRawData] = useState<RawData | null>(null); // Value used by commented-out scanSocial
  const [, setMetrics] = useState<Map<string, number> | null>(null); // Value used by commented-out scanSocial
  const [, setDeepData] = useState<DeepData | null>(null); // Value used by commented-out scanSocial
  const [postPreview, setPostPreview] = useState<PostPreview | null>(null);

  // UI State
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [stats, setStats] = useState<Stats>({ nodes: 0, likes: 0, reposts: 0, replies: 0 });
  // Scan social UI removed - keeping state for potential future use
  // const [socialScanned, setSocialScanned] = useState(false);
  const [scalingMode, setScalingMode] = useState<'uniform' | 'relative' | 'actual'>('actual');
  const [showMobileControls, setShowMobileControls] = useState(false);
  const [showDesktopControls, setShowDesktopControls] = useState(true);
  const [shareId, setShareId] = useState<string | null>(null);
  const [justShared, setJustShared] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [shareImageUrl, setShareImageUrl] = useState<string | null>(null);
  const graphSvgRef = useRef<SVGSVGElement>(null);

  // Initialize from Share URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const incomingShareId = params.get('share');
    if (incomingShareId) {
      loadSharedGraph(incomingShareId);
    }
  }, []);

  const loadSharedGraph = async (id: string) => {
    setLoading(true);
    setLoadingStatus('Loading shared visualization...');
    setError(null);
    setShowIntro(false);

    try {
      const baseUrl = import.meta.env.BASE_URL.endsWith('/') ? import.meta.env.BASE_URL.slice(0, -1) : import.meta.env.BASE_URL;
      const res = await fetch(`${baseUrl}/api/share/${id}`);
      if (!res.ok) throw new Error('Shared visualization not found');

      const data = await res.json();
      const { graphData, params } = data;

      // Strip out cached positions to allow force simulation to run fresh
      // Also convert link source/target back to IDs (D3 serializes them as full objects)
      const cleanGraphData = {
        nodes: graphData.nodes.map((node: any) => {
          const { x, y, fx, fy, vx, vy, index, ...cleanNode } = node;
          return cleanNode as GraphNode;
        }),
        links: graphData.links.map((link: GraphLink) => ({
          ...link,
          source: typeof link.source === 'object' ? (link.source as GraphNode).id : link.source,
          target: typeof link.target === 'object' ? (link.target as GraphNode).id : link.target,
        }))
      };

      // Restore state
      setGraphData(cleanGraphData);
      if (params?.url) setUrl(params.url);
      if (params?.scalingMode) setScalingMode(params.scalingMode);

      // Compute stats from restored data
      setStats({
        nodes: cleanGraphData.nodes.length,
        likes: cleanGraphData.nodes.filter((n: any) => n.primaryType === 'like').length,
        reposts: cleanGraphData.nodes.filter((n: any) => n.primaryType === 'repost').length,
        replies: cleanGraphData.nodes.filter((n: any) => n.primaryType === 'reply').length
      });

      setShareId(id);
    } catch (e) {
      console.error(e);
      setError('Failed to load shared visualization. It may have expired.');
    } finally {
      setLoading(false);
      setLoadingStatus('');
    }
  };

  // Load Demo Post - redirect to pre-generated share
  const loadDemo = () => {
    window.location.href = 'https://dr.eamer.dev/bluesky/post-visualizer/?share=7hsdfjeznj';
  };

  const handleVisualize = async (overrideUrl: string | null = null) => {
    const targetUrl = overrideUrl || url;
    if (!targetUrl) return;

    setShowIntro(false);
    setLoading(true);
    setLoadingStatus('Initializing...');
    setError(null);
    setGraphData(null);
    setRawData(null);
    setMetrics(null);
    setDeepData(null);
    setPostPreview(null);
    setSelectedNode(null);
    // setSocialScanned(false); // Removed with scan social UI
    setShareId(null); // Reset share state for new visualization
    setJustShared(false);
    // Clear share param from URL when loading new visualization
    const currentUrl = new URL(window.location.href);
    if (currentUrl.searchParams.has('share')) {
      currentUrl.searchParams.delete('share');
      window.history.replaceState({}, '', currentUrl);
    }

    try {
      const data = await fetchInteractionData(targetUrl, setLoadingStatus);
      setRawData(data);

      if (data.thread && data.thread.post) {
        setPostPreview({
          author: data.thread.post.author,
          record: data.thread.post.record,
          embed: data.thread.post.embed,
          parent: data.thread.parent,
          uri: data.thread.post.uri
        });
      }

      const allDids = new Set<string>();
      const collectInteractions = (items: (LikeData | RepostData)[]) => {
        items.forEach(i => {
          const did = ('actor' in i ? i.actor?.did : i.did);
          if (did) allDids.add(did);
        });
      };

      const traverse = (node: ThreadNode | null) => {
        if (!node) return;
        if (node.post) allDids.add(node.post.author.did);
        if (node.replies) node.replies.forEach(traverse);
      };
      traverse(data.thread);
      collectInteractions(data.likes);
      collectInteractions(data.reposts);

      setLoadingStatus(`Fetching Metrics for ${allDids.size} users...`);
      const metricsMap = await fetchNodeMetrics(Array.from(allDids), (curr, total) => {
        setLoadingStatus(`Fetching Metrics (${curr}/${total})...`);
      });
      setMetrics(metricsMap);

      // PHASE 1 Render
      setLoadingStatus('Rendering Graph...');
      await new Promise(r => setTimeout(r, 100));

      let processed = processGraphData(data, metricsMap);
      setGraphData(processed);

      setStats({
        nodes: processed.nodes.length,
        likes: data.likes.length,
        reposts: data.reposts.length,
        replies: processed.nodes.filter(n => n.primaryType === 'reply').length
      });

      // PHASE 2: Deep Scan (Automatic)
      setLoadingStatus('Expanding Thread Interactions...');

      const deepInteractions = await fetchDeepInteractions(data.thread!, (curr, total) => {
        setLoadingStatus(`Expanding Sub-threads (${curr}/${total})...`);
      });
      setDeepData(deepInteractions);

      const newDids = new Set<string>();
      deepInteractions.deepLikes.forEach(l => newDids.add(l.actor.did));
      deepInteractions.deepReposts.forEach(r => newDids.add(r.did));

      if (newDids.size > 0 && newDids.size < 500) {
        setLoadingStatus(`Fetching metrics for new interactors...`);
        const deepMetrics = await fetchNodeMetrics(Array.from(newDids));
        deepMetrics.forEach((val, key) => metricsMap.set(key, val));
      }

      processed = processGraphData(data, metricsMap, null, [], deepInteractions);
      setGraphData(processed);

      setStats({
        nodes: processed.nodes.length,
        likes: data.likes.length + deepInteractions.deepLikes.length,
        reposts: data.reposts.length + deepInteractions.deepReposts.length,
        replies: processed.nodes.filter(n => n.primaryType === 'reply').length
      });

    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Failed to fetch data.");
    } finally {
      setLoading(false);
      setLoadingStatus('');
    }
  };

  /* Scan social function removed from UI but preserved for future use
  const handleScanSocial = async () => {
    if (!graphData || !rawData || !metrics) return;
    setLoading(true);
    setLoadingStatus("Analyzing Social Connections...");

    try {
      const focusDid = rawData.thread?.post?.author?.did;

      const { newLinks, nodeUpdates } = await scanSocialConnections(
        graphData.nodes,
        focusDid,
        (status) => setLoadingStatus(status)
      );

      const processed = processGraphData(rawData, metrics, nodeUpdates, newLinks, deepData);
      setGraphData(processed);
      setSocialScanned(true);

    } catch (e) {
      console.error("Social Scan Failed", e);
      setError("Social scan partial failure. Some connections may be missing.");
    } finally {
      setLoading(false);
      setLoadingStatus('');
    }
  };
  */

  const openProfile = (handle: string) => {
    window.open(`https://bsky.app/profile/${handle}`, '_blank');
  };

  const loadParentPost = () => {
    if (postPreview?.parent?.post) {
      const p = postPreview.parent.post;
      const newUrl = `https://bsky.app/profile/${p.author.handle}/post/${p.uri.split('/').pop()}`;
      setUrl(newUrl);
      handleVisualize(newUrl);
    }
  };

  const openOriginalPost = () => {
    if (postPreview?.uri && postPreview?.author?.handle) {
      const rkey = postPreview.uri.split('/').pop();
      window.open(`https://bsky.app/profile/${postPreview.author.handle}/post/${rkey}`, '_blank');
    }
  };

  const goHome = () => {
    window.location.href = 'https://dr.eamer.dev/skymarshal/';
  };

  // Handle jumping to a reply thread from the node detail card
  const jumpToThread = (postUri: string, handle: string) => {
    if (!postUri || !handle) return;
    const rkey = postUri.split('/').pop();
    const newUrl = `https://bsky.app/profile/${handle}/post/${rkey}`;
    setUrl(newUrl);
    handleVisualize(newUrl);
  };

  // Generate graph image for saving or sharing
  const generateGraphImage = async (forShare = false): Promise<string | null> => {
    if (!graphSvgRef.current) return null;

    const svg = graphSvgRef.current;
    const svgClone = svg.cloneNode(true) as SVGSVGElement;

    // Get the viewBox to understand the coordinate system
    const viewBox = svg.getAttribute('viewBox')?.split(' ').map(Number) || [0, 0, 800, 600];
    const [vbX, vbY, vbWidth, vbHeight] = viewBox;

    // For social cards, use 1200x630 (Twitter/OG standard)
    // For regular saves, use actual size scaled up
    const targetWidth = forShare ? 1200 : Math.max(1200, vbWidth * 2);
    const targetHeight = forShare ? 630 : Math.max(630, vbHeight * 2);

    // Convert external image URLs to data URLs to avoid CORS issues
    const images = svgClone.querySelectorAll('image');
    const imagePromises = Array.from(images).map(async (img) => {
      const href = img.getAttribute('href') || img.getAttribute('xlink:href');
      if (href && href.startsWith('http')) {
        try {
          // Use a proxy or skip external images for now
          // External images often fail due to CORS, so we'll use a placeholder circle
          const parent = img.parentElement;
          if (parent) {
            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            const x = parseFloat(img.getAttribute('x') || '0');
            const y = parseFloat(img.getAttribute('y') || '0');
            const width = parseFloat(img.getAttribute('width') || '20');
            circle.setAttribute('cx', String(x + width / 2));
            circle.setAttribute('cy', String(y + width / 2));
            circle.setAttribute('r', String(width / 2));
            circle.setAttribute('fill', '#475569');
            parent.replaceChild(circle, img);
          }
        } catch {
          // Keep original on error
        }
      }
    });
    await Promise.all(imagePromises);

    // Set explicit dimensions on the SVG clone
    svgClone.setAttribute('width', String(targetWidth));
    svgClone.setAttribute('height', String(targetHeight));

    // Adjust viewBox to center the content nicely for social cards
    if (forShare) {
      // Zoom out a bit for social cards to show more of the network
      const padding = Math.max(vbWidth, vbHeight) * 0.1;
      svgClone.setAttribute('viewBox', `${vbX - padding} ${vbY - padding} ${vbWidth + padding * 2} ${vbHeight + padding * 2}`);
    }

    // Add background rect as first element
    const bgRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bgRect.setAttribute('x', String(vbX - 1000));
    bgRect.setAttribute('y', String(vbY - 1000));
    bgRect.setAttribute('width', String(vbWidth + 2000));
    bgRect.setAttribute('height', String(vbHeight + 2000));
    bgRect.setAttribute('fill', '#020617');
    svgClone.insertBefore(bgRect, svgClone.firstChild);

    // Serialize SVG
    const svgData = new XMLSerializer().serializeToString(svgClone);
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const svgUrl = URL.createObjectURL(svgBlob);

    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = targetWidth;
        canvas.height = targetHeight;
        const ctx = canvas.getContext('2d')!;

        // Dark background
        ctx.fillStyle = '#020617';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Draw the SVG
        ctx.drawImage(img, 0, 0, targetWidth, targetHeight);

        // Add watermark/branding
        ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
        ctx.font = 'bold 18px system-ui, -apple-system, sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText('dr.eamer.dev/bluesky/post-visualizer', canvas.width - 24, canvas.height - 24);

        // Add post info if available
        if (postPreview?.author?.handle) {
          ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
          ctx.font = '16px system-ui, -apple-system, sans-serif';
          ctx.textAlign = 'left';
          ctx.fillText(`@${postPreview.author.handle}'s post network`, 24, canvas.height - 24);
        }

        // Add title for social cards
        if (forShare) {
          ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
          ctx.font = 'bold 28px system-ui, -apple-system, sans-serif';
          ctx.textAlign = 'left';
          ctx.fillText('Bluesky Post Visualizer', 24, 40);

          if (stats) {
            ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
            ctx.font = '18px system-ui, -apple-system, sans-serif';
            ctx.fillText(`${stats.nodes} interactions • ${stats.replies} replies • ${stats.likes} likes • ${stats.reposts} reposts`, 24, 70);
          }
        }

        URL.revokeObjectURL(svgUrl);
        resolve(canvas.toDataURL('image/png'));
      };
      img.onerror = () => {
        URL.revokeObjectURL(svgUrl);
        resolve(null);
      };
      img.src = svgUrl;
    });
  };

  // Save graph as image with watermark
  const saveImage = async () => {
    const dataUrl = await generateGraphImage(false);
    if (!dataUrl) return;

    const link = document.createElement('a');
    const timestamp = new Date().toISOString().slice(0, 10);
    const handle = postPreview?.author?.handle || 'network';
    link.download = `bluesky-network-${handle}-${timestamp}.png`;
    link.href = dataUrl;
    link.click();
  };

  const handleShare = async () => {
    if (!graphData) return;
    setLoading(true);
    setLoadingStatus('Generating share image...');

    try {
      // Generate social card image
      const imageDataUrl = await generateGraphImage(true);

      const baseUrl = import.meta.env.BASE_URL.endsWith('/') ? import.meta.env.BASE_URL.slice(0, -1) : import.meta.env.BASE_URL;
      const res = await fetch(`${baseUrl}/api/share`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          graphData,
          params: { url, scalingMode },
          image: imageDataUrl
        })
      });

      if (!res.ok) throw new Error('Failed to create share link');

      const { id } = await res.json();
      setShareId(id);

      // Build share URL
      const generatedUrl = `${window.location.origin}${baseUrl}/?share=${id}`;
      setShareUrl(generatedUrl);

      // Build image URL for the share
      const imageUrl = `https://dr.eamer.dev${baseUrl}/images/${id}.png`;
      setShareImageUrl(imageDataUrl ? imageUrl : null);

      // Update browser URL without reload
      const newUrl = new URL(window.location.href);
      newUrl.searchParams.set('share', id);
      window.history.pushState({}, '', newUrl);

      // Show the share modal
      setShowShareModal(true);
    } catch (e) {
      console.error(e);
      alert('Failed to generate share link');
    } finally {
      setLoading(false);
      setLoadingStatus('');
    }
  };

  const copyShareLink = () => {
    if (!shareUrl) return;
    navigator.clipboard.writeText(shareUrl);
    setJustShared(true);
    setTimeout(() => setJustShared(false), 2000);
  };

  const openShareModal = () => {
    if (shareId) {
      const baseUrl = import.meta.env.BASE_URL.endsWith('/') ? import.meta.env.BASE_URL.slice(0, -1) : import.meta.env.BASE_URL;
      setShareUrl(`${window.location.origin}${baseUrl}/?share=${shareId}`);
      setShareImageUrl(`https://dr.eamer.dev${baseUrl}/images/${shareId}.png`);
      setShowShareModal(true);
    }
  };

  return (
    <div className="flex flex-col min-h-[var(--app-height)] h-[var(--app-height)] bg-slate-950 text-slate-100 font-sans overflow-hidden relative">

      {showIntro && <IntroTooltip
        onDismiss={() => setShowIntro(false)}
        onLoadDemo={loadDemo}
        onLoadUrl={(url) => { setUrl(url); setShowIntro(false); handleVisualize(url); }}
      />}

      {/* Share Modal */}
      {showShareModal && shareUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-700 rounded-sm shadow-2xl max-w-lg w-full p-6 animate-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Share2 className="w-5 h-5 text-blue-400" />
                Share Visualization
              </h3>
              <button
                onClick={() => setShowShareModal(false)}
                className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Share URL */}
            <div className="mb-4">
              <label className="text-xs text-slate-400 uppercase tracking-wider mb-2 block">Share Link</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={shareUrl}
                  className="flex-1 bg-slate-800 border border-slate-700 rounded-sm px-3 py-2 text-sm text-slate-200 font-mono"
                  onClick={(e) => (e.target as HTMLInputElement).select()}
                />
                <button
                  onClick={copyShareLink}
                  className={`px-4 py-2 rounded-sm text-sm font-medium transition-all ${justShared
                    ? 'bg-green-600 text-white'
                    : 'bg-blue-600 hover:bg-blue-500 text-white'
                    }`}
                >
                  {justShared ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>

            {/* Preview Image */}
            {shareImageUrl && (
              <div className="mb-4">
                <label className="text-xs text-slate-400 uppercase tracking-wider mb-2 block">Preview Image</label>
                <div className="bg-slate-800 rounded-sm overflow-hidden border border-slate-700">
                  <img
                    src={shareImageUrl}
                    alt="Share preview"
                    className="w-full h-auto"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-3">
              <button
                onClick={saveImage}
                className="flex-1 flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 text-white py-2.5 rounded-sm text-sm font-medium transition-colors"
              >
                <Camera className="w-4 h-4" />
                Save Full Image
              </button>
              <button
                onClick={() => setShowShareModal(false)}
                className="flex-1 bg-slate-700 hover:bg-slate-600 text-white py-2.5 rounded-sm text-sm font-medium transition-colors"
              >
                Done
              </button>
            </div>

            <p className="text-xs text-slate-500 mt-4 text-center">
              This link includes a preview image for social media sharing
            </p>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="flex-none p-4 border-b border-slate-800 bg-slate-950 z-20">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2 md:space-x-8 w-full md:w-auto justify-between md:justify-start">
            {/* Left Nav */}
            <div className="flex items-center gap-2">
              <button onClick={goHome} className="px-4 py-2 bg-white text-black hover:bg-slate-200 rounded-sm font-bold text-sm tracking-tight flex items-center gap-2 transition-colors" title="Skymarshal">
                <Home className="w-4 h-4" />
                <span>HOME</span>
              </button>
              <a href="https://dr.eamer.dev/bluesky/network/" className="px-4 py-2 bg-slate-800 text-slate-200 hover:bg-slate-700 hover:text-white rounded-sm font-bold text-sm tracking-tight flex items-center gap-2 transition-colors" title="Network Visualization">
                <Network className="w-4 h-4" />
                <span>NETWORK</span>
              </a>
            </div>

            {/* Title / Logo */}
            <a
              href="https://dr.eamer.dev/bluesky/post-visualizer/"
              className="flex items-center gap-3 group"
              title="Reset visualizer"
            >
              <div className="w-10 h-10 bg-blue-600 text-white flex items-center justify-center rounded-sm">
                <GitCommit className="w-6 h-6" />
              </div>
              <div className="flex flex-col justify-center h-10">
                <h1 className="text-xl font-black text-white tracking-tighter leading-none uppercase">Post<br />Visualizer</h1>
              </div>
            </a>
          </div>

          <div className="flex-1 w-full md:max-w-xl flex items-center gap-2">
            <div className="flex-1 flex gap-0 bg-slate-900 border border-slate-700 rounded-sm p-1">
              <input
                type="text"
                placeholder="Paste bsky.app post URL..."
                className="flex-1 bg-transparent border-none px-3 py-1.5 text-sm focus:outline-none text-white placeholder-slate-500 font-medium"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleVisualize()}
              />
              <button
                onClick={() => handleVisualize()}
                disabled={loading || !url}
                className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white px-5 py-1.5 rounded-sm font-bold text-sm uppercase tracking-wide transition-colors flex items-center gap-2"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                <span className="hidden sm:inline">Visualize</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 min-h-0 relative flex overflow-hidden">

        {/* Mobile Controls Toggle */}
        {graphData && (
          <button
            onClick={() => setShowMobileControls(!showMobileControls)}
            className="flex md:hidden absolute top-2 left-2 z-40 bg-slate-900 border border-slate-700 p-2.5 rounded-sm shadow-xl items-center gap-2 active:bg-slate-800 touch-manipulation"
          >
            <Settings2 className="w-5 h-5 text-blue-400" />
            <span className="text-xs font-medium text-slate-300">Menu</span>
            {showMobileControls ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>
        )}

        {/* Desktop Controls Toggle */}
        {graphData && (
          <button
            onClick={() => setShowDesktopControls(!showDesktopControls)}
            className="hidden md:flex absolute top-2 left-2 z-30 bg-slate-900/95 backdrop-blur border border-slate-700 p-2.5 rounded-sm shadow-xl pointer-events-auto items-center gap-2 hover:bg-slate-800 transition-colors"
          >
            <Settings2 className="w-5 h-5 text-blue-400" />
            <span className="text-xs font-medium text-slate-300">Menu</span>
            {showDesktopControls ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </button>
        )}

        {/* Controls Overlay */}
        {graphData && (
          <div className={`absolute top-14 left-4 z-20 w-64 md:w-72 space-y-3 pointer-events-none flex flex-col max-h-[calc(100%-4rem)] pb-4 transition-opacity duration-150 ${showMobileControls ? 'opacity-100 pointer-events-auto md:opacity-0 md:pointer-events-none' : 'opacity-0 pointer-events-none'} ${showDesktopControls ? 'md:opacity-100 md:pointer-events-auto' : 'md:opacity-0 md:pointer-events-none'}`}>

            {/* Stats Panel */}
            <div className="bg-slate-900 border border-slate-800 p-3 md:p-4 rounded-sm shadow-xl pointer-events-auto overflow-y-auto">
              <div className="flex justify-between items-center mb-3">
                <h3 className="text-slate-400 text-[10px] font-bold uppercase tracking-wider">Snapshot Data</h3>
              </div>

              <div className="grid grid-cols-2 gap-2 mb-4">
                <div className="bg-slate-800/50 p-2 rounded text-center">
                  <div className="text-lg font-bold text-white">{stats.nodes}</div>
                  <div className="text-[10px] text-slate-500">Total Nodes</div>
                </div>
                <div className="bg-slate-800/50 p-2 rounded text-center">
                  <div className="text-lg font-bold text-pink-400">{stats.likes}</div>
                  <div className="text-[10px] text-slate-500">Total Likes</div>
                </div>
                <div className="bg-slate-800/50 p-2 rounded text-center">
                  <div className="text-lg font-bold text-emerald-400">{stats.reposts}</div>
                  <div className="text-[10px] text-slate-500">Total Reposts</div>
                </div>
                <div className="bg-slate-800/50 p-2 rounded text-center">
                  <div className="text-lg font-bold text-blue-400">{stats.replies}</div>
                  <div className="text-[10px] text-slate-500">Replies</div>
                </div>
              </div>

              {/* Legend - Mobile Only */}
              <div className="md:hidden grid grid-cols-2 gap-2 mb-4 text-[10px]">
                <div className="space-y-1">
                  <span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-pink-500"></span> Like</span>
                  <span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-blue-500"></span> Reply</span>
                  <span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-yellow-400"></span> Repost</span>
                </div>
                <div className="space-y-1">
                  <span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full border border-green-500 bg-slate-700"></span> Mutual</span>
                  <span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full border border-blue-500 bg-slate-700"></span> OP follows</span>
                  <span className="flex items-center gap-2"><span className="w-2 h-2 rounded-full border border-amber-500 bg-slate-700"></span> Follows OP</span>
                </div>
              </div>

              {/* Node Scaling Controls */}
              <div>
                <h4 className="text-slate-500 text-[10px] font-bold uppercase tracking-wider mb-2">Node Scaling Mode</h4>
                <div className="grid grid-cols-3 gap-1 bg-slate-800 p-1 rounded-sm">
                  <button
                    onClick={() => setScalingMode('uniform')}
                    className={`py-1 text-[10px] font-medium rounded ${scalingMode === 'uniform' ? 'bg-slate-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                  >
                    Uniform
                  </button>
                  <button
                    onClick={() => setScalingMode('relative')}
                    className={`py-1 text-[10px] font-medium rounded ${scalingMode === 'relative' ? 'bg-slate-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                  >
                    Relative
                  </button>
                  <button
                    onClick={() => setScalingMode('actual')}
                    className={`py-1 text-[10px] font-medium rounded ${scalingMode === 'actual' ? 'bg-slate-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
                  >
                    True Scale
                  </button>
                </div>
              </div>

              {/* Save Image Button */}
              <button
                onClick={saveImage}
                className="w-full mt-3 flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 active:bg-slate-600 text-slate-300 hover:text-white py-2 rounded-sm text-xs font-medium transition-colors"
              >
                <Camera className="w-4 h-4" />
                <span>Save Image</span>
              </button>

              {/* Share Button */}
              <button
                onClick={shareId ? openShareModal : handleShare}
                className="w-full mt-2 flex items-center justify-center gap-2 py-2 rounded-sm text-xs font-medium bg-blue-600 hover:bg-blue-500 active:bg-blue-400 text-white"
              >
                <Share2 className="w-4 h-4" />
                <span>{shareId ? 'View Share Link' : 'Share Visualization'}</span>
              </button>
            </div>

            {/* Post Context Preview */}
            {postPreview && (
              <div className="bg-slate-900/90 backdrop-blur border border-slate-800 p-4 rounded-sm shadow-xl pointer-events-auto flex-shrink-0 overflow-hidden flex flex-col max-h-80 animate-in fade-in slide-in-from-left-4 duration-500 delay-100">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="text-slate-400 text-[10px] font-bold uppercase tracking-wider flex items-center gap-2">
                    <FileText className="w-3 h-3" /> Post Context
                  </h3>
                  <div className="flex gap-1">
                    {postPreview.parent && (
                      <button
                        onClick={loadParentPost}
                        className="text-[10px] text-blue-300 hover:text-white flex items-center gap-1 bg-blue-900/30 px-2 py-0.5 rounded border border-blue-800 hover:bg-blue-800 transition-colors"
                        title="Load parent post"
                      >
                        <ArrowUp className="w-3 h-3" /> Up
                      </button>
                    )}
                    <button
                      onClick={openOriginalPost}
                      className="text-[10px] text-slate-300 hover:text-white flex items-center gap-1 bg-slate-800 px-2 py-0.5 rounded border border-slate-700 hover:bg-slate-700 transition-colors"
                      title="Open on Bluesky"
                    >
                      <ExternalLink className="w-3 h-3" /> Open
                    </button>
                  </div>
                </div>
                <div className="overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-700">
                  <div
                    className="flex items-center gap-2 mb-2 cursor-pointer hover:bg-slate-800/50 p-1 rounded transition-colors"
                    onClick={() => openProfile(postPreview.author.handle)}
                  >
                    {postPreview.author.avatar && <img src={postPreview.author.avatar} className="w-8 h-8 rounded-full" />}
                    <div>
                      <div className="text-xs font-bold text-white truncate">{postPreview.author.displayName || postPreview.author.handle}</div>
                      <div className="text-[10px] text-slate-400">@{postPreview.author.handle}</div>
                    </div>
                  </div>
                  <p className="text-xs text-slate-300 mb-2 leading-relaxed whitespace-pre-wrap">
                    {postPreview.record.text}
                  </p>
                  {/* Media Preview support */}
                  {postPreview.embed?.images && (
                    <div className={`grid gap-1 mt-2 ${postPreview.embed.images.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
                      {postPreview.embed.images.map((img, i) => (
                        <div key={i} className="relative group">
                          <img src={img.thumb} className="rounded w-full h-24 object-cover bg-slate-800 border border-slate-700" />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Selected Node Details - Desktop */}
            {selectedNode && (
              <div className="hidden md:block bg-slate-900/90 backdrop-blur border border-slate-700 p-4 rounded-sm shadow-2xl pointer-events-auto animate-in zoom-in duration-200 mt-auto">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center space-x-3">
                    {selectedNode.avatar ? (
                      <img src={selectedNode.avatar} alt="" className="w-10 h-10 rounded-full border border-slate-600 bg-slate-800" />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold">
                        {selectedNode.handle[0]}
                      </div>
                    )}
                    <div className="overflow-hidden">
                      <h4 className="font-bold text-sm text-white truncate w-32">{selectedNode.displayName}</h4>
                      <p className="text-xs text-slate-400 truncate w-32">@{selectedNode.handle}</p>
                    </div>
                  </div>
                  <button onClick={() => setSelectedNode(null)} className="text-slate-500 hover:text-white">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-2 mb-3 text-xs text-slate-300">
                  <div className="bg-slate-800 p-2 rounded">
                    <span className="block text-slate-500 text-[10px]">Followers</span>
                    <span className="font-mono">{selectedNode.followers.toLocaleString()}</span>
                  </div>
                  <div className="bg-slate-800 p-2 rounded">
                    <span className="block text-slate-500 text-[10px]">Interactions</span>
                    <div className="flex gap-1 mt-1">
                      {selectedNode.types.has('reply') && <div className="w-2 h-2 rounded-full bg-blue-500" title="Reply"></div>}
                      {selectedNode.types.has('like') && <div className="w-2 h-2 rounded-full bg-pink-500" title="Like"></div>}
                      {selectedNode.types.has('repost') && <div className="w-2 h-2 rounded-full bg-emerald-500" title="Repost"></div>}
                    </div>
                  </div>
                </div>

                {/* Reply Preview */}
                {selectedNode.postData && (
                  <div className="mb-3 bg-slate-800/50 p-2 rounded border border-slate-700/50">
                    <div className="text-[10px] text-slate-400 uppercase font-bold mb-1">Reply Context</div>
                    <p className="text-xs text-slate-200 line-clamp-3 mb-2 font-medium">"{selectedNode.postData.text}"</p>
                    <button
                      onClick={() => jumpToThread(selectedNode.postData!.uri, selectedNode.handle)}
                      className="w-full bg-blue-600/20 hover:bg-blue-600/40 text-blue-200 border border-blue-500/30 py-1.5 rounded text-xs font-semibold transition-colors flex items-center justify-center gap-2"
                    >
                      <MessageSquare className="w-3 h-3" /> Visualize This Thread
                    </button>
                  </div>
                )}

                {/* Social Status Indicators */}
                {selectedNode.socialStatus === 'mutual' && (
                  <div className="mb-3 bg-green-900/30 border border-green-900/50 p-2 rounded flex items-center gap-2">
                    <UserCheck className="w-3 h-3 text-green-400" />
                    <span className="text-[10px] text-green-200">Mutual Follow (Friend)</span>
                  </div>
                )}
                {selectedNode.socialStatus === 'followed_by_op' && (
                  <div className="mb-3 bg-blue-900/30 border border-blue-900/50 p-2 rounded flex items-center gap-2">
                    <UserCheck className="w-3 h-3 text-blue-400" />
                    <span className="text-[10px] text-blue-200">Followed by OP</span>
                  </div>
                )}
                {selectedNode.socialStatus === 'follows_op' && (
                  <div className="mb-3 bg-amber-900/30 border border-amber-900/50 p-2 rounded flex items-center gap-2">
                    <UserPlus className="w-3 h-3 text-amber-400" />
                    <span className="text-[10px] text-amber-200">Follows OP (Fan)</span>
                  </div>
                )}

                <button
                  onClick={() => openProfile(selectedNode.handle)}
                  className="w-full bg-slate-100 hover:bg-white text-slate-900 py-2 rounded-sm text-xs font-bold transition-colors"
                >
                  View on Bluesky
                </button>
              </div>
            )}
          </div>
        )}

        {/* Selected Node Details - Mobile Bottom Sheet */}
        {selectedNode && (
          <div className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-slate-900/98 backdrop-blur-lg border-t border-slate-700 p-4 rounded-t-2xl shadow-2xl pointer-events-auto animate-in slide-in-from-bottom duration-300 max-h-[60vh] overflow-y-auto">
            <div className="w-12 h-1 bg-slate-600 rounded-full mx-auto mb-3" />
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center space-x-3">
                {selectedNode.avatar ? (
                  <img src={selectedNode.avatar} alt="" className="w-12 h-12 rounded-full border border-slate-600 bg-slate-800" />
                ) : (
                  <div className="w-12 h-12 rounded-full bg-slate-700 flex items-center justify-center text-sm font-bold">
                    {selectedNode.handle[0]}
                  </div>
                )}
                <div className="overflow-hidden">
                  <h4 className="font-bold text-base text-white truncate max-w-[200px]">{selectedNode.displayName}</h4>
                  <p className="text-sm text-slate-400 truncate max-w-[200px]">@{selectedNode.handle}</p>
                </div>
              </div>
              <button onClick={() => setSelectedNode(null)} className="text-slate-400 hover:text-white p-2 -mr-2 -mt-2 active:bg-slate-800 rounded-sm">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2 mb-3 text-sm text-slate-300">
              <div className="bg-slate-800 p-3 rounded-sm">
                <span className="block text-slate-500 text-xs mb-1">Followers</span>
                <span className="font-mono text-lg">{selectedNode.followers.toLocaleString()}</span>
              </div>
              <div className="bg-slate-800 p-3 rounded-sm">
                <span className="block text-slate-500 text-xs mb-1">Interactions</span>
                <div className="flex gap-2 mt-1.5">
                  {selectedNode.types.has('reply') && <div className="w-3 h-3 rounded-full bg-blue-500" title="Reply"></div>}
                  {selectedNode.types.has('like') && <div className="w-3 h-3 rounded-full bg-pink-500" title="Like"></div>}
                  {selectedNode.types.has('repost') && <div className="w-3 h-3 rounded-full bg-emerald-500" title="Repost"></div>}
                </div>
              </div>
            </div>

            {/* Reply Preview */}
            {selectedNode.postData && (
              <div className="mb-3 bg-slate-800/50 p-3 rounded-sm border border-slate-700/50">
                <div className="text-xs text-slate-400 uppercase font-bold mb-1.5">Reply Context</div>
                <p className="text-sm text-slate-200 line-clamp-3 mb-2 font-medium">"{selectedNode.postData.text}"</p>
                <button
                  onClick={() => jumpToThread(selectedNode.postData!.uri, selectedNode.handle)}
                  className="w-full bg-blue-600/20 hover:bg-blue-600/40 active:bg-blue-600/60 text-blue-200 border border-blue-500/30 py-2 rounded-sm text-sm font-semibold transition-colors flex items-center justify-center gap-2"
                >
                  <MessageSquare className="w-4 h-4" /> Visualize This Thread
                </button>
              </div>
            )}

            {/* Social Status Indicators */}
            {selectedNode.socialStatus === 'mutual' && (
              <div className="mb-3 bg-green-900/30 border border-green-900/50 p-2.5 rounded-sm flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-green-400" />
                <span className="text-xs text-green-200">Mutual Follow</span>
              </div>
            )}
            {selectedNode.socialStatus === 'followed_by_op' && (
              <div className="mb-3 bg-blue-900/30 border border-blue-900/50 p-2.5 rounded-sm flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-blue-400" />
                <span className="text-xs text-blue-200">Followed by OP</span>
              </div>
            )}
            {selectedNode.socialStatus === 'follows_op' && (
              <div className="mb-3 bg-amber-900/30 border border-amber-900/50 p-2.5 rounded-sm flex items-center gap-2">
                <UserPlus className="w-4 h-4 text-amber-400" />
                <span className="text-xs text-amber-200">Follows OP</span>
              </div>
            )}

            <button
              onClick={() => openProfile(selectedNode.handle)}
              className="w-full bg-slate-100 hover:bg-white active:bg-slate-200 text-slate-900 py-3 rounded-sm text-sm font-bold transition-colors"
            >
              View on Bluesky
            </button>
          </div>
        )}

        {/* Graph Container */}
        <div className="flex-1 min-h-0 bg-slate-950 relative">
          {!graphData && !loading && !error && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-600 p-8 text-center pointer-events-none">
              <div className="w-24 h-24 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center mb-6 shadow-2xl shadow-blue-900/20">
                <Share2 className="w-10 h-10 opacity-30" />
              </div>
              <h2 className="text-xl font-semibold text-slate-400 mb-2">Ready to Visualize</h2>
              <p className="text-sm opacity-50 max-w-sm mb-6">
                Paste a Bluesky post URL to see the conversation tree and interactions in a force-directed graph.
              </p>
              <button
                onClick={() => setShowIntro(true)}
                className="pointer-events-auto text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
              >
                <HelpCircle className="w-3 h-3" /> Show Intro Guide
              </button>
            </div>
          )}

          {loading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-sm z-50 text-center px-6">
              <Loader2 className="w-10 h-10 text-blue-500 animate-spin mb-4" />
              <p className="text-blue-400 font-medium animate-pulse">{loadingStatus}</p>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/90 z-50 p-6">
              <div className="bg-red-950/30 border border-red-900/50 p-6 rounded-sm max-w-md text-center">
                <Info className="w-12 h-12 mx-auto mb-4 text-red-500" />
                <h3 className="text-lg font-bold text-red-200 mb-2">Notice</h3>
                <p className="text-sm text-red-300/70 mb-6">{error}</p>
                <button
                  onClick={() => setError(null)}
                  className="px-6 py-2 bg-red-900/50 hover:bg-red-900 text-red-100 rounded-sm text-sm font-medium transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          )}

          {graphData && (
            <ForceGraph
              data={graphData}
              scalingMode={scalingMode}
              onNodeClick={setSelectedNode}
              svgRef={graphSvgRef}
            />
          )}

        </div>

        {/* Share Button - Upper Right (outside graph container for proper z-index) */}
        {graphData && (
          <button
            onClick={shareId ? openShareModal : handleShare}
            className="absolute top-2 right-2 z-40 bg-slate-900 border border-slate-700 p-2.5 rounded-sm shadow-xl hover:bg-slate-800 active:bg-slate-700 transition-colors touch-manipulation"
            title={shareId ? 'View Share Link' : 'Share Visualization'}
          >
            <Share2 className="w-5 h-5 text-blue-400" />
          </button>
        )}

      </main>
    </div>
  );
}
