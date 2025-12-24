import os
from datetime import datetime
from typing import List, Optional, Dict
from atproto import Client
from atproto_client.models.app.bsky.feed.defs import PostView, FeedViewPost
from .config import settings


class BskyClient:
    def __init__(self):
        self.client = Client()
        self._login()

    def _login(self):
        # Requires env vars: BSKY_USERNAME, BSKY_PASSWORD
        user = os.getenv("BSKY_USERNAME")
        pw = os.getenv("BSKY_PASSWORD")
        if not user or not pw:
            raise ValueError("BSKY_USERNAME and BSKY_PASSWORD required")
        self.client.login(user, pw)

    def search_candidates(self, query: str, limit: int = 25) -> List[Dict]:
        """Returns list of {did, handle} from post searches."""
        print(f"Searching for: {query}")
        try:
            # Note: The ATProto SDK search method syntax
            resp = self.client.app.bsky.feed.search_posts(
                params={"q": query, "limit": limit}
            )
            candidates = []
            for post in resp.posts:
                candidates.append(
                    {"did": post.author.did, "handle": post.author.handle}
                )
            return candidates
        except Exception as e:
            print(f"Search failed: {e}")
            return []

    def get_followers(self, handle: str, limit: int = 1000) -> List[Dict]:
        """Get followers of an account. Returns list of {did, handle}."""
        print(f"Fetching followers of: {handle}")
        followers = []
        try:
            cursor = None
            fetched = 0

            while fetched < limit:
                resp = self.client.get_followers(
                    actor=handle,
                    limit=min(100, limit - fetched),
                    cursor=cursor
                )

                for follower in resp.followers:
                    followers.append({
                        "did": follower.did,
                        "handle": follower.handle
                    })
                    fetched += 1
                    if fetched >= limit:
                        break

                # Check if there are more results
                if not resp.cursor or fetched >= limit:
                    break
                cursor = resp.cursor

        except Exception as e:
            print(f"Failed to fetch followers for {handle}: {e}")

        return followers

    def get_following(self, handle: str, limit: int = 1000) -> List[Dict]:
        """Get accounts that this account follows. Returns list of {did, handle}."""
        print(f"Fetching following of: {handle}")
        following = []
        try:
            cursor = None
            fetched = 0

            while fetched < limit:
                resp = self.client.get_follows(
                    actor=handle,
                    limit=min(100, limit - fetched),
                    cursor=cursor
                )

                for follow in resp.follows:
                    following.append({
                        "did": follow.did,
                        "handle": follow.handle
                    })
                    fetched += 1
                    if fetched >= limit:
                        break

                # Check if there are more results
                if not resp.cursor or fetched >= limit:
                    break
                cursor = resp.cursor

        except Exception as e:
            print(f"Failed to fetch following for {handle}: {e}")

        return following

    def fetch_profile(self, did: str) -> Optional[Dict]:
        try:
            p = self.client.get_profile(actor=did)
            return {
                "did": p.did,
                "handle": p.handle,
                "display_name": p.display_name,
                "description": p.description,
                "avatar_url": p.avatar,
            }
        except Exception as e:
            print(f"Profile fetch failed for {did}: {e}")
            return None

    def fetch_recent_posts(self, did: str, limit: int = 50) -> List[Dict]:
        posts = []
        try:
            # filter='posts_no_replies' helps reduce noise if desired,
            # but spec says include replies, exclude pure reposts.
            feed = self.client.get_author_feed(
                actor=did, limit=limit, filter="posts_with_replies"
            )

            for item in feed.feed:
                # Filter out pure reposts (ReasonRepost)
                if item.reason:
                    continue

                record = item.post.record
                # record is strict typed model or dict depending on SDK version/usage
                # We handle the object access safely
                text = getattr(record, "text", "")
                created_at_str = getattr(
                    record, "created_at", datetime.utcnow().isoformat()
                )

                # Normalize time
                dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))

                posts.append(
                    {
                        "uri": item.post.uri,
                        "cid": item.post.cid,
                        "author_did": item.post.author.did,
                        "created_at": dt,
                        "text": text,
                        "is_repost": False,
                    }
                )
        except Exception as e:
            print(f"Feed fetch failed for {did}: {e}")

        return posts
