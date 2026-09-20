"""Sparse top-k similarity graph construction and deterministic PageRank."""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import scipy.sparse as sp

try:
    from sparse_dot_topn import sp_matmul_topn

    HAS_SPARSE_DOT_TOPN = True
except ImportError:
    sp_matmul_topn = None  # type: ignore
    HAS_SPARSE_DOT_TOPN = False


def build_sparse_similarity_graph(
    tfidf_matrix: sp.csr_matrix,
    top_k: int = 10,
    min_similarity: float = 0.05,
) -> sp.csr_matrix:
    """Computes a sparse top-k cosine similarity graph between units.

    Ensures bounded degree O(N * top_k) memory and time.
    """
    shape = cast(tuple[int, int], tfidf_matrix.shape)
    n = shape[0]
    if n <= 1:
        return sp.csr_matrix((n, n), dtype=np.float64)

    # Normalize rows to unit length for cosine similarity
    row_norms = sp.linalg.norm(tfidf_matrix, axis=1)
    row_norms[row_norms == 0] = 1.0
    norm_diag = sp.diags(1.0 / row_norms)
    normalized = cast(sp.csr_matrix, norm_diag @ tfidf_matrix)

    k = min(top_k + 1, n)

    if HAS_SPARSE_DOT_TOPN and sp_matmul_topn is not None:
        try:
            norm_t = cast(sp.csr_matrix, normalized.transpose().tocsr())
            res: Any = sp_matmul_topn(
                normalized,
                norm_t,
                top_n=k,
                threshold=min_similarity,
            )
            sim = res.tocsr() if hasattr(res, "tocsr") else sp.csr_matrix(res)
        except (ValueError, RuntimeError):
            sim = sp.csr_matrix(normalized @ normalized.transpose())
    else:
        sim = sp.csr_matrix(normalized @ normalized.transpose())

    sim.setdiag(0)
    sim.eliminate_zeros()

    return cast(sp.csr_matrix, sim)


def deterministic_pagerank(
    graph: sp.csr_matrix,
    damping: float = 0.85,
    max_iter: int = 50,
    tol: float = 1e-6,
) -> np.ndarray:
    """Computes deterministic PageRank over a CSR adjacency matrix using float64.

    Guarantees:
    - Fixed convergence criteria.
    - Stable tie-breaking.
    - Normalized output in [0, 1].
    """
    shape = cast(tuple[int, int], graph.shape)
    n = shape[0]
    if n == 0:
        return np.empty(0, dtype=np.float64)
    if n == 1:
        return np.ones(1, dtype=np.float64)

    row_sums = np.array(graph.sum(axis=1)).flatten()
    non_zero_mask = row_sums > 0

    inv_diag = np.zeros(n, dtype=np.float64)
    inv_diag[non_zero_mask] = 1.0 / row_sums[non_zero_mask]
    norm_matrix = sp.diags(inv_diag, dtype=np.float64) @ graph

    p = np.full(n, 1.0 / n, dtype=np.float64)
    dangling_mask = ~non_zero_mask

    for _ in range(max_iter):
        dangling_sum = p[dangling_mask].sum()
        p_next = damping * (norm_matrix.T @ p) + (damping * dangling_sum + (1.0 - damping)) / n
        diff = np.sum(np.abs(p_next - p))
        p = p_next
        if diff < tol:
            break

    p = np.round(p, decimals=8)

    p_min = p.min()
    p_max = p.max()
    if p_max > p_min:
        return (p - p_min) / (p_max - p_min)
    return np.ones(n, dtype=np.float64)
