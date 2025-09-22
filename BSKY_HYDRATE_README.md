# Bluesky Post Hydration Script

A Python script that logs into Bluesky, downloads your latest 500 posts, and hydrates them with engagement data (likes, reposts, quotes, and replies).

## Features

- **Authentication**: Secure login using Bluesky handle and app password
- **Post Fetching**: Downloads up to 500 of your most recent posts
- **Engagement Hydration**: Fetches detailed engagement data for each post:
  - Likes with actor information and timestamps
  - Reposts with actor information
  - Quote posts with full post content
  - Replies via thread traversal
- **Multiple Output Formats**:
  - `posts_500.jsonl`: Raw post data (one JSON per line)
  - `post_engagements.jsonl`: Detailed engagement data per post
  - `post_summary.csv`: Summary table with engagement counts

## Requirements

```bash
pip install atproto pandas
```

## Setup

### 1. Create App Password

1. Go to Bluesky Settings → App passwords
2. Create a new app password (format: `xxxx-xxxx-xxxx-xxxx`)
3. **Never use your real Bluesky password**

### 2. Set Environment Variables (Optional)

```bash
export BSKY_HANDLE="your-handle.bsky.social"
export BSKY_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"
```

If not set, the script will prompt you for these values.

## Usage

```bash
python bsky_hydrate.py
```

The script will:
1. Authenticate with Bluesky
2. Fetch your recent posts (up to 500)
3. Hydrate each post with engagement data
4. Save results to three files

## Output Files

### posts_500.jsonl
Contains basic post information:
```json
{
  "uri": "at://did:plc:example/app.bsky.feed.post/abc123",
  "cid": "bafyrei...",
  "indexedAt": "2024-01-01T12:00:00.000Z",
  "author_did": "did:plc:example",
  "author_handle": "you.bsky.social",
  "text": "Your post content here",
  "likeCount": 5,
  "repostCount": 2,
  "replyCount": 1,
  "quoteCount": 0
}
```

### post_engagements.jsonl
Contains detailed engagement data:
```json
{
  "uri": "at://did:plc:example/app.bsky.feed.post/abc123",
  "likeCount": 5,
  "repostCount": 2,
  "quoteCount": 0,
  "replyCount": 1,
  "likes": [
    {
      "uri": "at://did:plc:example/app.bsky.feed.post/abc123",
      "actor_did": "did:plc:liker",
      "actor_handle": "friend.bsky.social",
      "createdAt": "2024-01-01T12:05:00.000Z"
    }
  ],
  "reposts": [...],
  "quotes": [...],
  "replies": [...]
}
```

### post_summary.csv
CSV file with engagement summary for easy analysis:
```csv
uri,cid,indexedAt,likes,reposts,quotes,replies,total_engagements
at://did:plc:example/app.bsky.feed.post/abc123,bafyrei...,2024-01-01T12:00:00.000Z,5,2,0,1,8
```

## Configuration

You can modify these constants in the script:

```python
MAX_POSTS = 500                    # Maximum posts to fetch
PAGE_LIMIT = 100                   # API page size (max 100)
SLEEP_BETWEEN_REQUESTS = 0.2       # Rate limiting delay
```

## API Endpoints Used

- `app.bsky.feed.getAuthorFeed` - Fetch your posts
- `app.bsky.feed.getLikes` - Get post likes
- `app.bsky.feed.getRepostedBy` - Get reposts
- `app.bsky.feed.getQuotes` - Get quote posts
- `app.bsky.feed.getPostThread` - Get replies via thread traversal

## Error Handling

- Rate limiting with configurable delays
- Defensive attribute access for SDK compatibility
- Graceful handling of missing data

## Security Notes

- Uses app passwords, never your real password
- Environment variables prevent credentials in shell history
- No credentials are logged or saved to output files

## Testing

Run the included test:
```bash
python test_bsky_hydrate.py
```

## Troubleshooting

### Rate Limits
If you hit rate limits, increase `SLEEP_BETWEEN_REQUESTS`:
```python
SLEEP_BETWEEN_REQUESTS = 0.5  # or higher
```

### Authentication Issues
- Ensure you're using an app password, not your real password
- Check that your handle is correct (include domain: `.bsky.social`)
- Verify the app password format: `xxxx-xxxx-xxxx-xxxx`

### Missing Engagement Data
Some posts may have incomplete engagement data due to:
- API rate limits
- Privacy settings of other users
- Deleted posts/users

## Example Output

```
Fetching up to 500 posts for you.bsky.social...
Wrote 342 posts to posts_500.jsonl
[1/342] Hydrating at://did:plc:example/app.bsky.feed.post/abc123
[2/342] Hydrating at://did:plc:example/app.bsky.feed.post/def456
...
Wrote engagement details for 342 posts to post_engagements.jsonl
Wrote summary to post_summary.csv
Done.
```

The summary CSV will be sorted by total engagement count, making it easy to identify your most popular posts.
