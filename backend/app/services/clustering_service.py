"""
SevaSetu — Clustering Service
Clusters needs using DBSCAN to detect geographic and semantic anomalies/hotspots.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, func

from app.models.db_models import Need, NeedCluster
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

class ClusteringService:
    def __init__(self):
        self._dbscan_available = False
        try:
            from sklearn.cluster import DBSCAN
            self.DBSCAN = DBSCAN
            self._dbscan_available = True
            logger.info("✅ DBSCAN available for clustering")
        except ImportError:
            logger.warning("⚠️ sklearn not installed. Clustering service in fallback mode.")

    async def cluster_existing_needs(self, db: AsyncSession) -> dict:
        """
        Runs DBSCAN clustering on open needs.
        Finds overlapping/related needs that should be aggregated.
        """
        if not self._dbscan_available:
            return {"status": "fallback", "clusters_formed": 0}

        # Get active needs with embeddings
        result = await db.execute(
            select(Need).where(
                and_(
                    Need.status.in_(["new", "matched", "in_progress"]),
                    Need.embedding.isnot(None)
                )
            )
        )
        needs = result.scalars().all()

        if len(needs) < 2:
            return {"status": "skipped_not_enough_needs", "clusters_formed": 0}

        # Prepare data for DBSCAN
        # We'll cluster primarily by semantics first
        embeddings = np.array([list(n.embedding) for n in needs])
        
        # eps 0.3 for cosine distance -> similarity of 0.7
        # metric='cosine' is often better but scikit-learn DBSCAN with cosine needs distances.
        # we can use euclidean on normalized vectors which relates to cosine.
        dbscan = self.DBSCAN(eps=0.4, min_samples=2, metric='euclidean')
        
        labels = dbscan.fit_predict(embeddings)
        
        # Clear old clusters roughly (for simplicity, recreating clusters)
        await db.execute(update(Need).values(cluster_id=None))
        await db.execute(NeedCluster.__table__.delete())
        
        # Group by label
        clusters = {}
        for i, label in enumerate(labels):
            if label == -1:
                continue # Noise
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(needs[i])

        new_cluster_count = 0
        for label, cluster_needs in clusters.items():
            # Create a NeedCluster
            valid_lats = [n.latitude for n in cluster_needs if n.latitude]
            valid_lngs = [n.longitude for n in cluster_needs if n.longitude]
            
            c_lat = sum(valid_lats)/len(valid_lats) if valid_lats else None
            c_lng = sum(valid_lngs)/len(valid_lngs) if valid_lngs else None
            
            types = [n.need_type for n in cluster_needs if n.need_type]
            c_type = max(set(types), key=types.count) if types else "MIXED"
            
            urgencies = [n.urgency_current or n.urgency_base for n in cluster_needs]
            c_urgency = sum(urgencies)/len(urgencies) if urgencies else 0.5
            
            nc = NeedCluster(
                center_lat=c_lat,
                center_lng=c_lng,
                need_type=c_type,
                need_count=len(cluster_needs),
                avg_urgency=c_urgency
            )
            db.add(nc)
            await db.flush() # get id
            
            # update needs
            for n in cluster_needs:
                n.cluster_id = nc.id
            
            new_cluster_count += 1
            
        await db.commit()
        return {"status": "success", "clusters_formed": new_cluster_count}

clustering_service = ClusteringService()
