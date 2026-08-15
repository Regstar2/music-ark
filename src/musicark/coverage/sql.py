"""SQL fragments for MusicArk v0.6 Library Coverage."""

from __future__ import annotations


def coverage_base_cte() -> str:
    # provider_collection_items.external_id is a storage key for playlist
    # duplicate occurrences. payload_json.external_id is the provider identity.
    # Liked rows use the same value in both places.
    return """
    WITH
    ctx(provider_id, collection_id, matcher_version, local_library_fingerprint) AS (
        VALUES (?, ?, ?, ?)
    ),
    membership_rows AS (
        SELECT
            pci.provider_id,
            CASE
                WHEN json_valid(pci.payload_json)
                THEN COALESCE(
                    NULLIF(CAST(json_extract(pci.payload_json, '$.external_id') AS TEXT), ''),
                    pci.external_id
                )
                ELSE pci.external_id
            END AS external_id,
            pci.collection_id,
            pci.position,
            pci.payload_json,
            CASE
                WHEN pci.collection_id='liked' THEN 'Мне нравится'
                ELSE COALESCE(NULLIF(pcs.title, ''), pci.collection_id)
            END AS collection_title
        FROM provider_collection_items pci
        JOIN ctx ON ctx.provider_id=pci.provider_id
        LEFT JOIN provider_collection_snapshots pcs
          ON pcs.provider_id=pci.provider_id
         AND pcs.collection_id=pci.collection_id
        WHERE COALESCE(pcs.active, 1)=1
    ),
    memberships AS (
        SELECT provider_id, external_id, collection_id,
               MIN(position) AS position,
               MAX(collection_title) AS collection_title,
               MIN(payload_json) AS payload_json
        FROM membership_rows
        WHERE TRIM(external_id) <> ''
        GROUP BY provider_id, external_id, collection_id
    ),
    ranked_payloads AS (
        SELECT provider_id, external_id, payload_json,
               ROW_NUMBER() OVER (
                   PARTITION BY provider_id, external_id
                   ORDER BY CASE WHEN collection_id='liked' THEN 0 ELSE 1 END,
                            collection_id, position
               ) AS rn
        FROM memberships
    ),
    active_tracks AS (
        SELECT provider_id, external_id, payload_json
        FROM ranked_payloads
        WHERE rn=1
    ),
    membership_agg AS (
        SELECT provider_id, external_id,
               json_group_array(
                   json_object(
                       'id', collection_id,
                       'title', collection_title,
                       'position', position
                   )
               ) AS collections_json,
               GROUP_CONCAT(collection_title, ' ') AS collection_search
        FROM memberships
        GROUP BY provider_id, external_id
    ),
    scoped AS (
        SELECT
            at.provider_id,
            at.external_id,
            at.payload_json,
            ma.collections_json,
            ma.collection_search,
            CASE
                WHEN ctx.collection_id='' THEN NULL
                ELSE (
                    SELECT MIN(mx.position)
                    FROM memberships mx
                    WHERE mx.provider_id=at.provider_id
                      AND mx.external_id=at.external_id
                      AND mx.collection_id=ctx.collection_id
                )
            END AS scope_position
        FROM active_tracks at
        JOIN membership_agg ma
          ON ma.provider_id=at.provider_id
         AND ma.external_id=at.external_id
        JOIN ctx
        WHERE ctx.collection_id=''
           OR EXISTS (
                SELECT 1 FROM memberships sm
                WHERE sm.provider_id=at.provider_id
                  AND sm.external_id=at.external_id
                  AND sm.collection_id=ctx.collection_id
           )
    ),
    coverage_base AS (
        SELECT
            s.provider_id,
            s.external_id,
            s.payload_json,
            s.collections_json,
            s.collection_search,
            s.scope_position,
            mr.status AS matching_status,
            mr.local_file_id,
            mr.confidence,
            mr.method,
            mr.reason,
            mr.manual,
            mr.updated_at AS matching_updated_at,
            laf.path AS local_path,
            laf.title AS local_title,
            laf.artists_json AS local_artists_json,
            laf.album AS local_album,
            laf.duration_seconds AS local_duration_seconds,
            CASE
                WHEN mr.provider_id IS NULL THEN 'not_analyzed'

                WHEN mr.manual=1 AND mr.status='matched' THEN
                    CASE
                        WHEN COALESCE(mr.reason, '') LIKE 'manual_match_stale:%'
                            THEN 'needs_review'
                        WHEN COALESCE(mr.provider_fingerprint, '') <> ''
                         AND COALESCE(mr.local_fingerprint, '') <> ''
                         AND (
                            mr.provider_fingerprint <> musicark_provider_fingerprint(
                                s.provider_id, s.external_id, s.payload_json
                            )
                            OR mr.local_fingerprint <> musicark_local_fingerprint(
                                laf.path, laf.file_size, laf.modified_ns, laf.title,
                                laf.artists_json, laf.album, laf.duration_seconds, laf.codec
                            )
                         )
                            THEN 'needs_review'
                        WHEN mr.local_file_id IS NULL
                          OR laf.id IS NULL
                          OR COALESCE(laf.availability, 'missing') <> 'available'
                          OR tl.id IS NULL
                            THEN 'needs_review'
                        ELSE 'covered'
                    END

                WHEN COALESCE(mr.manual, 0)=0
                 AND (
                    COALESCE(mr.matcher_version, 0) <> ctx.matcher_version
                    OR COALESCE(mr.provider_fingerprint, '') <>
                       musicark_provider_fingerprint(
                           s.provider_id, s.external_id, s.payload_json
                       )
                    OR COALESCE(mr.local_fingerprint, '') <>
                       ctx.local_library_fingerprint
                 )
                    THEN 'not_analyzed'

                WHEN mr.status='matched' THEN
                    CASE
                        WHEN mr.local_file_id IS NOT NULL
                         AND laf.id IS NOT NULL
                         AND COALESCE(laf.availability, 'missing')='available'
                         AND tl.id IS NOT NULL
                            THEN 'covered'
                        ELSE 'needs_review'
                    END
                WHEN mr.status='conflict' THEN 'needs_review'
                WHEN mr.status='unmatched' THEN 'missing'
                ELSE 'not_analyzed'
            END AS coverage_status,
            CASE
                WHEN tvr.status IN (
                    'same', 'altered', 'different_version', 'uncertain', 'not_checked'
                ) THEN tvr.status
                ELSE 'not_checked'
            END AS variant_status,
            COALESCE(pta.action, 'unreviewed') AS user_action
        FROM scoped s
        JOIN ctx
        LEFT JOIN matching_results mr
          ON mr.provider_id=s.provider_id
         AND mr.external_id=s.external_id
        LEFT JOIN local_audio_files laf
          ON laf.id=mr.local_file_id
        LEFT JOIN track_links tl
          ON tl.source_provider_id=s.provider_id
         AND tl.source_external_id=s.external_id
         AND tl.local_file_id=mr.local_file_id
        LEFT JOIN track_variant_results tvr
          ON tvr.provider_id=s.provider_id
         AND tvr.external_id=s.external_id
         AND tvr.local_file_id=mr.local_file_id
        LEFT JOIN provider_track_actions pta
          ON pta.provider_id=s.provider_id
         AND pta.external_id=s.external_id
    )
    """

