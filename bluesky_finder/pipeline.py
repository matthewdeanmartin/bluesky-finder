from datetime import datetime
from pathlib import Path
from typing import Literal
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader
from .database import get_db, DbCandidate, DbProfile, DbPost, DbLlmEval
from .at_client import BskyClient
from .llm import evaluate_candidate
from .config import settings
from .models import DiscoverySource


class Pipeline:
    def __init__(self):
        self.db: Session = get_db()
        self.bsky = BskyClient()

    def run_discovery(self):
        print("[*] Starting Discovery...")
        new_count = 0

        # Hashtags
        print("\n[Hashtag Discovery]")
        for tag in settings.seed_hashtags:
            results = self.bsky.search_candidates(
                tag, limit=settings.discovery_limits.max_candidates_per_hashtag
            )
            for res in results:
                if self._add_candidate(
                        res["did"], res["handle"], DiscoverySource.HASHTAG
                ):
                    new_count += 1

        # Anchor Accounts
        print("\n[Anchor Account Discovery]")
        for anchor_handle in settings.anchor_handles:
            print(f"\nProcessing anchor: {anchor_handle}")

            # Get followers
            followers = self.bsky.get_followers(
                anchor_handle,
                limit=settings.discovery_limits.max_accounts_per_anchor // 2
            )
            print(f"  Found {len(followers)} followers")
            for follower in followers:
                if self._add_candidate(
                        follower["did"],
                        follower["handle"],
                        DiscoverySource.ANCHOR_FOLLOW
                ):
                    new_count += 1

            # Get following
            following = self.bsky.get_following(
                anchor_handle,
                limit=settings.discovery_limits.max_accounts_per_anchor // 2
            )
            print(f"  Found {len(following)} following")
            for follow in following:
                if self._add_candidate(
                        follow["did"],
                        follow["handle"],
                        DiscoverySource.ANCHOR_FOLLOW
                ):
                    new_count += 1

        self.db.commit()
        print(f"\n[*] Discovery complete. Added {new_count} new candidates.")

    def _add_candidate(self, did: str, handle: str, source: DiscoverySource) -> bool:
        exists = self.db.query(DbCandidate).filter_by(did=did).first()
        if not exists:
            cand = DbCandidate(did=did, handle=handle, discovery_sources=[source.value])
            self.db.add(cand)
            return True
        else:
            # Update discovery sources if this is a new source
            if source.value not in exists.discovery_sources:
                exists.discovery_sources = exists.discovery_sources + [source.value]
                self.db.add(exists)
        return False

    def run_fetch(self, force: bool = False):
        """Fetch profiles and posts for candidates who need it."""
        print("[*] Starting Fetch...")
        candidates = self.db.query(DbCandidate).all()

        for cand in candidates:
            # 1. Profile Fetch
            # Simple TTL check: if no profile OR profile is old
            need_profile = False
            if not cand.profile:
                need_profile = True
            elif (
                    force
                    or (datetime.utcnow() - cand.profile.fetched_at)
                    > settings.min_interval_profile_refresh
            ):
                need_profile = True

            if need_profile:
                p_data = self.bsky.fetch_profile(cand.did)
                if p_data:
                    if not cand.profile:
                        cand.profile = DbProfile(did=cand.did)
                    cand.profile.handle = p_data["handle"]
                    cand.profile.display_name = p_data["display_name"]
                    cand.profile.description = p_data["description"]
                    cand.profile.avatar_url = p_data["avatar_url"]
                    cand.profile.fetched_at = datetime.utcnow()
                    self.db.add(cand.profile)
                    print(f"   Fetched profile: {cand.handle}")

            # 2. Posts Fetch
            # Similar TTL logic could apply, for MVP we fetch if empty
            if not cand.posts or force:
                posts_data = self.bsky.fetch_recent_posts(
                    cand.did, limit=settings.fetch_posts_limit
                )
                # Clear old posts for simplicity in MVP (or use upsert logic for robustness)
                self.db.query(DbPost).filter_by(author_did=cand.did).delete()

                for p in posts_data:
                    db_post = DbPost(
                        uri=p["uri"],
                        cid=p["cid"],
                        author_did=cand.did,
                        created_at=p["created_at"],
                        text=p["text"],
                        is_repost=p["is_repost"],
                    )
                    self.db.add(db_post)
                print(f"   Fetched {len(posts_data)} posts: {cand.handle}")

            self.db.commit()

    def run_evaluation(self, force: bool = False):
        print("[*] Starting LLM Evaluation...")
        # Get candidates with profile + posts but no (or stale) eval
        candidates = self.db.query(DbCandidate).join(DbProfile).all()

        for cand in candidates:
            if not cand.profile or not cand.posts:
                continue

            if cand.llm_eval and not force:
                continue

            print(f"   Evaluating: {cand.handle}")

            # Serialize for LLM
            p_data = {"handle": cand.handle, "description": cand.profile.description}
            posts_data = [
                {"text": p.text, "created_at": str(p.created_at)} for p in cand.posts
            ]

            try:
                result = evaluate_candidate(p_data, posts_data)

                # Upsert Eval
                if not cand.llm_eval:
                    cand.llm_eval = DbLlmEval(did=cand.did)

                eval_rec = cand.llm_eval
                eval_rec.model = settings.openai_model
                eval_rec.run_at = datetime.utcnow()
                eval_rec.score_location = result.score_location
                eval_rec.score_tech = result.score_tech
                eval_rec.score_overall = result.score_overall
                eval_rec.label = result.label.value
                eval_rec.rationale = result.rationale
                eval_rec.evidence = result.evidence
                eval_rec.uncertainties = result.uncertainties

                self.db.add(eval_rec)
                self.db.commit()
            except Exception as e:
                print(f"   [!] Eval failed for {cand.handle}: {e}")

    def export_results(self, format: str = "jsonl"):
        import json

        results = (
            self.db.query(DbCandidate)
            .join(DbLlmEval)
            .filter(
                DbLlmEval.score_overall >= settings.scoring_thresholds.maybe_overall
            )
            .order_by(DbLlmEval.score_overall.desc())
            .all()
        )

        timestamp = datetime.utcnow().strftime("%Y%m%d")

        # Prepare data for both formats
        candidates_data = []
        for c in results:
            row = {
                "handle": c.handle,
                "did": c.did,
                "score": c.llm_eval.score_overall,
                "label": c.llm_eval.label,
                "location_score": c.llm_eval.score_location,
                "tech_score": c.llm_eval.score_tech,
                "bio": c.profile.description if c.profile else "",
                "rationale": c.llm_eval.rationale,
                "profile_url": f"https://bsky.app/profile/{c.handle}",
                "avatar_url": c.profile.avatar_url if c.profile else None,
                "display_name": c.profile.display_name if c.profile else c.handle,
                "discovery_sources": c.discovery_sources,
            }
            candidates_data.append(row)

        if format == "jsonl":
            filename = f"export_{timestamp}.jsonl"
            with open(filename, "w") as f:
                for row in candidates_data:
                    f.write(json.dumps(row) + "\n")
            print(f"Exported {len(results)} candidates to {filename}")

        elif format == "html":
            # Generate HTML using Jinja2
            templates_dir = Path(__file__).parent / "templates"
            templates_dir.mkdir(exist_ok=True)

            env = Environment(loader=FileSystemLoader(str(templates_dir)))

            template = env.get_template("export.html")

            html_content = template.render(
                candidates=candidates_data,
                total_count=len(candidates_data),
                export_date=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                thresholds=settings.scoring_thresholds,
            )

            filename = f"export_{timestamp}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"Exported {len(results)} candidates to {filename}")
