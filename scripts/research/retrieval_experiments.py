"""BL-58 — Advanced Retrieval Architecture experiments harness.

Runs the retrieval golden set (``data/retrieval_golden_set_v1.jsonl``) through
a pluggable set of retrieval strategies and writes a comparison report to
``outputs/retrieval_eval_report_v1.json``. The script is **offline by default**:
it uses a deterministic hash-token embedder over a synthetic in-memory knowledge
base, so the harness runs in CI without ChromaDB, sentence-transformers or
Ollama. The same strategies can later be wired to the production
:class:`HybridChromaRetriever` by setting ``--backend chroma`` (BL-58 follow-up).

Strategies exposed via ``--strategy``:

* ``naive``                — BM25 + dense + RRF, baseline (matches BL-01).
* ``query_expansion``      — keyword-driven sub-queries fused with RRF
                             (mirrors LangChain ``MultiQueryRetriever``).
* ``parent_context_tuning``— small-to-big: child hits expanded to parent
                             section to improve context recall.
* ``hybrid_alpha_tuning``  — weighted BM25/dense fusion driven by query
                             length (short → favour dense, long → favour BM25).
* ``metadata_routing``     — pre-filter chunks by ``doc_type`` derived from
                             the query before scoring.
* ``reranker_cross_encoder``— lightweight token-overlap rerank as a
                             cross-encoder stand-in (``bge-reranker-large`` /
                             ``ms-marco-MiniLM`` style late-interaction).

Each strategy is required to be deterministic and stdlib-only so the harness
can run unchanged in CI.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

logger = logging.getLogger("retrieval_experiments")

DEFAULT_GOLDEN = REPO_ROOT / "data" / "retrieval_golden_set_v1.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "outputs" / "retrieval_eval_report_v1.json"
DEFAULT_K = 5
DEFAULT_RRF_K = 60
DEFAULT_STRICT_MIN_SCORE = 0.30
DEFAULT_SEED = 20260521

ALL_STRATEGIES: Tuple[str, ...] = (
    "naive",
    "query_expansion",
    "parent_context_tuning",
    "hybrid_alpha_tuning",
    "metadata_routing",
    "reranker_cross_encoder",
)

# -------------------------------------------------- synthetic knowledge base --
# A compact, deterministic surrogate for the production ChromaDB index. Each
# chunk text carries vocabulary plausible for the Mango Office / VATS knowledge
# base so the relative ordering between strategies is meaningful even without
# real embeddings or the real PDF corpus.
SYNTHETIC_CHUNKS: List[Dict[str, Any]] = [
    {
        "source": "MANGO_OFFICE_LK_VATS_Auth_SSO.pdf",
        "section_number": "1",
        "section_title": "Авторизация через корпоративный домен",
        "doc_type": "auth",
        "text": (
            "Single Sign-On позволяет авторизоваться в Личном кабинете ВАТС "
            "через корпоративный домен. Поддерживаются SAML 2.0 и LDAP "
            "синхронизация. Аутентификация выполняется внешним IdP без "
            "повторного ввода учётных данных."
        ),
    },
    {
        "source": "MANGO_OFFICE_LK_VATS_Auth_SSO.pdf",
        "section_number": "2",
        "section_title": "Настройка SAML провайдера",
        "doc_type": "auth",
        "text": (
            "Для подключения SAML 2.0 IdP администратор указывает Entity ID, "
            "endpoint SSO, сертификат подписи и атрибуты пользователя. "
            "Синхронизация LDAP импортирует пользователей из Active Directory."
        ),
    },
    {
        "source": "Rolevaya-model-VATS_1_26_08.pdf",
        "section_number": "3",
        "section_title": "Ролевая модель и RBAC",
        "doc_type": "auth",
        "text": (
            "Ролевая модель ВАТС реализует RBAC (Role-Based Access Control). "
            "Администратор управляет группами безопасности и матрицей доступа: "
            "сотрудники получают права на элементы интерфейса по своей роли."
        ),
    },
    {
        "source": "Rolevaya-model-VATS_1_26_08.pdf",
        "section_number": "4",
        "section_title": "Матрица доступа",
        "doc_type": "auth",
        "text": (
            "Матрица доступа определяет, какие разделы Личного кабинета и "
            "виджеты оператора видны для каждой роли. Изменения вступают в "
            "силу немедленно для всех активных сессий."
        ),
    },
    {
        "source": "MangoOffice_VPBX_API_v1.9.pdf",
        "section_number": "3.1",
        "section_title": "REST API VPBX",
        "doc_type": "api",
        "text": (
            "VPBX API построен на REST. Все методы доступны по HTTPS и "
            "возвращают JSON. Интеграция с внешней МИС выполняется через REST "
            "API с токеном доступа."
        ),
    },
    {
        "source": "MangoOffice_VPBX_API_v1.9.pdf",
        "section_number": "4.2",
        "section_title": "Аутентификация OAuth 2.0",
        "doc_type": "api",
        "text": (
            "Поддерживается OAuth 2.0 в режиме client_credentials. Токены "
            "обновляются по refresh_token. Срок жизни access_token — 3600 "
            "секунд."
        ),
    },
    {
        "source": "MangoOffice_VPBX_API_v1.9.pdf",
        "section_number": "5.4",
        "section_title": "Журнал и аудит запросов API",
        "doc_type": "api",
        "text": (
            "Все исходящие запросы API логируются в журнал аудита: метод, "
            "URL, код ответа, заголовки и идентификатор корреляции."
        ),
    },
    {
        "source": "MangoOffice_VPBX_API_v1.9.pdf",
        "section_number": "6.1",
        "section_title": "Повторные попытки и отказоустойчивость",
        "doc_type": "api",
        "text": (
            "При получении HTTP 5xx клиент VPBX API выполняет автоматический "
            "повтор с экспоненциальной задержкой. Конфигурируется число "
            "ретраев и таймаут."
        ),
    },
    {
        "source": "SIP_trunk-1.23.43.pdf",
        "section_number": "1",
        "section_title": "Подключение SIP транка",
        "doc_type": "telephony",
        "text": (
            "SIP транк настраивается через Личный кабинет ВАТС. Поддерживается "
            "регистрация по логину/паролю и по IP. WebRTC поддерживается "
            "клиентами оператора."
        ),
    },
    {
        "source": "SIP_trunk-1.23.43.pdf",
        "section_number": "2",
        "section_title": "Подключение H.323 и АТС заказчика",
        "doc_type": "telephony",
        "text": (
            "Помимо SIP, ВАТС поддерживает H.323 транк для интеграции с "
            "корпоративной АТС заказчика. Используется для маршрутизации ТФОП."
        ),
    },
    {
        "source": "QM_manual_v-1.26.08_compressed.pdf",
        "section_number": "1",
        "section_title": "Quality Management — запись звонков",
        "doc_type": "qm",
        "text": (
            "Модуль Quality Management записывает все входящие и исходящие "
            "звонки контакт-центра. Срок хранения настраивается. Дополнительно "
            "ведётся запись экранов операторов."
        ),
    },
    {
        "source": "QM_manual_v-1.26.08_compressed.pdf",
        "section_number": "2",
        "section_title": "Оценка операторов и отчёты",
        "doc_type": "qm",
        "text": (
            "QM формирует отчёты по эффективности операторов. Доступен экспорт "
            "в Excel. Оценщик заполняет формы оценки на основании записи "
            "звонков и экранов."
        ),
    },
    {
        "source": "Click2call_Chrome_UserManual_1_0.pdf",
        "section_number": "1",
        "section_title": "Расширение Click2Call для Chrome",
        "doc_type": "channels",
        "text": (
            "Click2Call — расширение для браузера Chrome, позволяющее "
            "инициировать звонок прямо со страницы CRM или сайта одним кликом."
        ),
    },
    {
        "source": "RECHEVAYA-ANALITIKA_1.26.18.pdf",
        "section_number": "1",
        "section_title": "Речевая аналитика — классификация звонков",
        "doc_type": "analytics",
        "text": (
            "Речевая аналитика автоматически классифицирует звонки по "
            "тематикам. Поддерживается распознавание голоса и синтез речи."
        ),
    },
    {
        "source": "RECHEVAYA-ANALITIKA_VATS-_-Skoring-1.26.18.pdf",
        "section_number": "2",
        "section_title": "Скоринг диалогов",
        "doc_type": "analytics",
        "text": (
            "Скоринг диалогов оценивает соответствие оператора скрипту по "
            "результатам распознавания. Оценщик может вручную перепроверить "
            "автоматический результат."
        ),
    },
    {
        "source": "RECHEVAYA-ANALITIKA_Skoring_Rukovodstvo-polzovatelya_v.1.26.15.pdf",
        "section_number": "3",
        "section_title": "Скоринг — руководство пользователя",
        "doc_type": "analytics",
        "text": (
            "Сценарии скоринга настраиваются в Личном кабинете речевой "
            "аналитики. Доступны автоматические и ручные сценарии оценки."
        ),
    },
    {
        "source": "LK_manual_v-119_compressed.pdf",
        "section_number": "5",
        "section_title": "IVR и маршрутизация входящих обращений",
        "doc_type": "lk",
        "text": (
            "В Личном кабинете ВАТС настраивается дерево IVR. Маршрутизация "
            "входящих обращений выполняется по выбранному в меню варианту, "
            "позволяя направлять звонок в нужную очередь."
        ),
    },
    {
        "source": "LK_manual_v-119_compressed.pdf",
        "section_number": "6",
        "section_title": "Группы операторов и очереди",
        "doc_type": "lk",
        "text": (
            "Администратор управляет группами операторов и распределяет "
            "входящие очереди между ними. Поддерживаются настройки приоритета "
            "и скиллов."
        ),
    },
    {
        "source": "LK_manual_v-119_compressed.pdf",
        "section_number": "7",
        "section_title": "Сценарии диалога и интеграция с МИС",
        "doc_type": "lk",
        "text": (
            "Сценарии диалога отображают информацию о клиенте, полученную из "
            "МИС заказчика через REST API. Логика обслуживания согласуется "
            "по каждой тематике звонка."
        ),
    },
    {
        "source": "LK_manual_v-119_compressed.pdf",
        "section_number": "8",
        "section_title": "Отказоустойчивость и резервное копирование",
        "doc_type": "infra",
        "text": (
            "Решение обеспечивает отказоустойчивость по технологии N+1. "
            "Базы данных, содержащие персональные данные пациентов, "
            "выгружаются в резервные копии."
        ),
    },
]


# Documents that share a parent section number provide a parent_text view used
# by the ``parent_context_tuning`` strategy.
def _build_parent_index(chunks: Sequence[Mapping[str, Any]]) -> Dict[str, str]:
    index: Dict[str, List[str]] = {}
    for chunk in chunks:
        key = f"{chunk['source']}::{chunk['section_number']}"
        index.setdefault(key, []).append(str(chunk["text"]))
    return {k: " ".join(v) for k, v in index.items()}


# -------------------------------------------------------------- golden set --
@dataclass
class GoldenItem:
    id: str
    case_type: str
    subset: str
    requirement_text: str
    expected_sources: List[str] = field(default_factory=list)
    expected_section_numbers: List[str] = field(default_factory=list)
    expected_substrings: List[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any], fallback_id: str = "") -> "GoldenItem":
        return cls(
            id=str(raw.get("id") or fallback_id),
            case_type=str(raw.get("case_type") or "direct"),
            subset=str(raw.get("subset") or ""),
            requirement_text=str(
                raw.get("requirement_text") or raw.get("query") or ""
            ),
            expected_sources=[str(s) for s in raw.get("expected_sources", []) or []],
            expected_section_numbers=[
                str(s) for s in raw.get("expected_section_numbers", []) or []
            ],
            expected_substrings=[
                str(s) for s in raw.get("expected_substrings", []) or []
            ],
            notes=str(raw.get("notes") or ""),
        )


def load_golden_set(path: Path) -> List[GoldenItem]:
    if not path.exists():
        raise FileNotFoundError(f"Golden set not found: {path}")
    items: List[GoldenItem] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        raw = json.loads(line)
        items.append(GoldenItem.from_dict(raw, fallback_id=f"L{line_no:03d}"))
    if not items:
        raise ValueError(f"Golden set is empty: {path}")
    return items


# -------------------------------------------------- deterministic text utils --
_WORD_RE = re.compile(r"\w+", flags=re.UNICODE)


def _tokenize(text: str) -> List[str]:
    return [tok.lower() for tok in _WORD_RE.findall(text or "")]


def _bag(text: str) -> Dict[str, int]:
    bag: Dict[str, int] = {}
    for tok in _tokenize(text):
        bag[tok] = bag.get(tok, 0) + 1
    return bag


def _hash_embedding(text: str, dim: int = 256) -> List[float]:
    vec = [0.0] * dim
    for tok in _tokenize(text):
        vec[hash(tok) % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm:
        vec = [v / norm for v in vec]
    return vec


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    if dot == 0:
        return 0.0
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _bm25_scores(
    corpus_tokens: Sequence[Sequence[str]], query_tokens: Sequence[str],
    k1: float = 1.5, b: float = 0.75,
) -> List[float]:
    if not corpus_tokens:
        return []
    doc_len = [len(d) for d in corpus_tokens]
    avgdl = sum(doc_len) / max(1, len(corpus_tokens))
    df: Dict[str, int] = {}
    doc_freqs: List[Dict[str, int]] = []
    for d in corpus_tokens:
        freq: Dict[str, int] = {}
        for tok in d:
            freq[tok] = freq.get(tok, 0) + 1
        doc_freqs.append(freq)
        for tok in freq:
            df[tok] = df.get(tok, 0) + 1
    n = len(corpus_tokens)
    idf = {
        tok: math.log(1 + (n - cnt + 0.5) / (cnt + 0.5)) for tok, cnt in df.items()
    }
    scores = [0.0] * n
    for q in query_tokens:
        w = idf.get(q)
        if not w:
            continue
        for i, freq in enumerate(doc_freqs):
            tf = freq.get(q, 0)
            if tf == 0:
                continue
            dl = doc_len[i] or 1
            denom = tf + k1 * (1 - b + b * dl / (avgdl or 1))
            scores[i] += w * (tf * (k1 + 1)) / denom
    return scores


def _rrf_fuse(
    ranked_lists: Sequence[Sequence[Tuple[int, float]]],
    *,
    k: int = DEFAULT_RRF_K,
    top_k: int,
) -> List[Tuple[int, float]]:
    fused: Dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, (idx, _score) in enumerate(ranked, start=1):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank)
    ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
    return ordered[:top_k]


def _order_scores(scores: Sequence[float], top_k: int) -> List[Tuple[int, float]]:
    indexed = [(i, s) for i, s in enumerate(scores) if s > 0]
    indexed.sort(key=lambda x: x[1], reverse=True)
    return indexed[:top_k]


# ---------------------------------------------------------- KB-aware corpus --
@dataclass
class CorpusView:
    chunks: List[Dict[str, Any]]
    tokens: List[List[str]]
    embeddings: List[List[float]]
    parent_index: Dict[str, str]

    @classmethod
    def build(cls, chunks: Sequence[Mapping[str, Any]]) -> "CorpusView":
        prepared = [dict(c) for c in chunks]
        tokens = [_tokenize(c["text"]) for c in prepared]
        emb = [_hash_embedding(c["text"]) for c in prepared]
        return cls(
            chunks=prepared, tokens=tokens, embeddings=emb,
            parent_index=_build_parent_index(prepared),
        )


# ------------------------------------------------------- query enrichers --
SYNONYM_EXPANSIONS: Dict[str, List[str]] = {
    "sso": ["single sign-on", "saml", "ldap", "single sign on", "корпоративный домен"],
    "single sign-on": ["sso", "saml", "ldap"],
    "rbac": ["ролевая модель", "матрица доступа", "группы безопасности"],
    "роль": ["rbac", "ролевая модель", "матрица доступа"],
    "click-to-call": ["click2call", "расширение", "chrome"],
    "click2call": ["click-to-call", "chrome"],
    "webrtc": ["sip", "транк"],
    "ivr": ["маршрутизация", "дерево"],
    "запись экрана": ["запись экранов", "qm", "quality management"],
    "rest api": ["vpbx api", "интеграция"],
    "oauth": ["oauth 2.0", "client_credentials", "токен"],
    "распознавание": ["речевая аналитика", "синтез"],
    "отчёт": ["qm", "оценка", "экспорт"],
    "очередь": ["группа", "оператор"],
    "резервное копирование": ["backup", "n+1", "отказоустойчивость"],
}


def _expand_query(query: str, max_expansions: int = 3) -> List[str]:
    """Return the original query plus deterministic synonym rewrites.

    Mirrors the behaviour of LangChain's ``MultiQueryRetriever`` and
    LlamaIndex's ``SubQuestionQueryEngine`` without contacting an LLM. Sub-
    queries are derived from a fixed synonym dictionary so the experiment is
    fully deterministic in CI.
    """
    expansions: List[str] = [query]
    lowered = query.lower()
    for phrase, alts in SYNONYM_EXPANSIONS.items():
        if phrase in lowered:
            for alt in alts:
                if alt not in expansions:
                    expansions.append(alt)
        if len(expansions) >= max_expansions + 1:
            break
    return expansions[: max_expansions + 1]


_DOC_TYPE_HINTS: Tuple[Tuple[str, str], ...] = (
    ("sso", "auth"),
    ("single sign", "auth"),
    ("rbac", "auth"),
    ("ролев", "auth"),
    ("права доступа", "auth"),
    ("oauth", "api"),
    ("rest api", "api"),
    ("vpbx", "api"),
    ("интеграция", "api"),
    ("sip", "telephony"),
    ("транк", "telephony"),
    ("h.323", "telephony"),
    ("webrtc", "telephony"),
    ("запис", "qm"),
    ("оценка", "qm"),
    ("quality", "qm"),
    ("отчёт", "qm"),
    ("экран", "qm"),
    ("ivr", "lk"),
    ("маршрутизация", "lk"),
    ("очеред", "lk"),
    ("груп", "lk"),
    ("сценарий", "lk"),
    ("резерв", "infra"),
    ("отказоустойч", "infra"),
    ("click2call", "channels"),
    ("click-to-call", "channels"),
    ("речев", "analytics"),
    ("распознав", "analytics"),
    ("скоринг", "analytics"),
    ("синтез", "analytics"),
)


def _routed_doc_types(query: str) -> List[str]:
    lowered = query.lower()
    result: List[str] = []
    for hint, doc_type in _DOC_TYPE_HINTS:
        if hint in lowered and doc_type not in result:
            result.append(doc_type)
    return result


# ------------------------------------------------------ strategy implementations --
def _to_chunk_hit(corpus: CorpusView, idx: int, score: float) -> Dict[str, Any]:
    chunk = corpus.chunks[idx]
    return {
        "source": chunk["source"],
        "section_number": chunk.get("section_number", ""),
        "section_title": chunk.get("section_title", ""),
        "doc_type": chunk.get("doc_type", ""),
        "text": chunk["text"],
        "score": float(score),
    }


def strategy_naive(corpus: CorpusView, query: str, top_k: int) -> List[Dict[str, Any]]:
    q_tokens = _tokenize(query)
    bm25 = _bm25_scores(corpus.tokens, q_tokens)
    q_emb = _hash_embedding(query)
    dense = [_cosine(q_emb, e) for e in corpus.embeddings]
    candidate_k = max(top_k * 2, top_k)
    bm25_ranked = _order_scores(bm25, candidate_k)
    dense_ranked = _order_scores(dense, candidate_k)
    fused = _rrf_fuse([bm25_ranked, dense_ranked], top_k=top_k)
    return [_to_chunk_hit(corpus, i, s) for i, s in fused]


def strategy_query_expansion(
    corpus: CorpusView, query: str, top_k: int
) -> List[Dict[str, Any]]:
    rewrites = _expand_query(query)
    q_emb = _hash_embedding(query)
    candidate_k = max(top_k * 2, top_k)
    ranked_lists: List[List[Tuple[int, float]]] = []
    for rewrite in rewrites:
        bm25 = _bm25_scores(corpus.tokens, _tokenize(rewrite))
        dense = [_cosine(_hash_embedding(rewrite), e) for e in corpus.embeddings]
        ranked_lists.append(_order_scores(bm25, candidate_k))
        ranked_lists.append(_order_scores(dense, candidate_k))
    fused = _rrf_fuse(ranked_lists, top_k=top_k)
    hits = [_to_chunk_hit(corpus, i, s) for i, s in fused]
    # Boost score for chunks whose tokens overlap with the original embedding.
    for hit, (idx, _s) in zip(hits, fused):
        hit["score"] += 0.05 * _cosine(q_emb, corpus.embeddings[idx])
    return hits


def strategy_parent_context_tuning(
    corpus: CorpusView, query: str, top_k: int
) -> List[Dict[str, Any]]:
    base = strategy_naive(corpus, query, top_k * 2)
    seen: Dict[str, Dict[str, Any]] = {}
    for hit in base:
        parent_key = f"{hit['source']}::{hit['section_number']}"
        parent_text = corpus.parent_index.get(parent_key, hit["text"])
        if parent_key in seen:
            seen[parent_key]["score"] = max(seen[parent_key]["score"], hit["score"])
        else:
            seen[parent_key] = {
                **hit,
                "text": parent_text,
                "parent_context": True,
            }
    ranked = sorted(seen.values(), key=lambda h: h["score"], reverse=True)
    return ranked[:top_k]


def strategy_hybrid_alpha_tuning(
    corpus: CorpusView, query: str, top_k: int
) -> List[Dict[str, Any]]:
    q_tokens = _tokenize(query)
    # Short queries → favour dense (semantic). Long queries → favour BM25.
    alpha = 0.3 if len(q_tokens) <= 4 else 0.7
    bm25 = _bm25_scores(corpus.tokens, q_tokens)
    q_emb = _hash_embedding(query)
    dense = [_cosine(q_emb, e) for e in corpus.embeddings]
    # Min-max normalise to keep contributions comparable.
    def _norm(scores: Sequence[float]) -> List[float]:
        if not scores:
            return []
        mx = max(scores)
        return [s / mx if mx > 0 else 0.0 for s in scores]

    bm25_n = _norm(bm25)
    dense_n = _norm(dense)
    blended = [alpha * b + (1 - alpha) * d for b, d in zip(bm25_n, dense_n)]
    ranked = _order_scores(blended, top_k)
    return [_to_chunk_hit(corpus, i, s) for i, s in ranked]


def strategy_metadata_routing(
    corpus: CorpusView, query: str, top_k: int
) -> List[Dict[str, Any]]:
    doc_types = _routed_doc_types(query)
    if not doc_types:
        return strategy_naive(corpus, query, top_k)
    keep_idx = [
        i for i, c in enumerate(corpus.chunks) if c.get("doc_type") in doc_types
    ]
    if not keep_idx:
        return strategy_naive(corpus, query, top_k)
    sub_chunks = [corpus.chunks[i] for i in keep_idx]
    sub_tokens = [corpus.tokens[i] for i in keep_idx]
    sub_emb = [corpus.embeddings[i] for i in keep_idx]
    sub_view = CorpusView(
        chunks=sub_chunks, tokens=sub_tokens, embeddings=sub_emb,
        parent_index=corpus.parent_index,
    )
    return strategy_naive(sub_view, query, top_k)


def strategy_reranker_cross_encoder(
    corpus: CorpusView, query: str, top_k: int
) -> List[Dict[str, Any]]:
    # Get a larger candidate pool from naive hybrid, then rerank with a
    # token-overlap "cross-encoder" stand-in. This mirrors the latency profile
    # of bge-reranker-large / ms-marco MiniLM rerankers without the GPU.
    candidates = strategy_naive(corpus, query, top_k * 3)
    q_bag = _bag(query)

    def _overlap(text: str) -> float:
        b = _bag(text)
        common = sum(min(q_bag[t], b.get(t, 0)) for t in q_bag)
        denom = math.sqrt(sum(v * v for v in q_bag.values()) * sum(v * v for v in b.values())) or 1.0
        return common / denom

    reranked = sorted(
        candidates,
        key=lambda h: 0.4 * h["score"] + 0.6 * _overlap(h["text"]),
        reverse=True,
    )
    return reranked[:top_k]


STRATEGY_FNS: Dict[str, Callable[[CorpusView, str, int], List[Dict[str, Any]]]] = {
    "naive": strategy_naive,
    "query_expansion": strategy_query_expansion,
    "parent_context_tuning": strategy_parent_context_tuning,
    "hybrid_alpha_tuning": strategy_hybrid_alpha_tuning,
    "metadata_routing": strategy_metadata_routing,
    "reranker_cross_encoder": strategy_reranker_cross_encoder,
}


# ---------------------------------------------------------------- metrics --
def _hit_rank(hits: Sequence[Mapping[str, Any]], expected_sources: Iterable[str]) -> int:
    wanted = {str(s).lower() for s in expected_sources if str(s).strip()}
    if not wanted:
        return 0
    for rank, hit in enumerate(hits, start=1):
        if str(hit.get("source", "")).lower() in wanted:
            return rank
    return 0


def _recall_at_k(hits: Sequence[Mapping[str, Any]], expected_sources: Iterable[str]) -> float:
    wanted = {str(s).lower() for s in expected_sources if str(s).strip()}
    if not wanted:
        return 1.0
    found = {str(h.get("source", "")).lower() for h in hits} & wanted
    return len(found) / len(wanted)


def _precision_at(
    hits: Sequence[Mapping[str, Any]], expected_sources: Iterable[str], k: int
) -> float:
    wanted = {str(s).lower() for s in expected_sources if str(s).strip()}
    if not wanted:
        return 1.0 if not hits[:k] else 0.0
    top = hits[:k]
    if not top:
        return 0.0
    matched = sum(1 for h in top if str(h.get("source", "")).lower() in wanted)
    return matched / len(top)


def _context_recall(
    hits: Sequence[Mapping[str, Any]], expected_substrings: Iterable[str]
) -> float:
    needles = [s for s in expected_substrings if str(s).strip()]
    if not needles:
        return 1.0
    haystack = " ".join(str(h.get("text", "")) for h in hits).lower()
    return sum(1 for n in needles if n.lower() in haystack) / len(needles)


def _strict_mode_fallback(
    hits: Sequence[Mapping[str, Any]], min_score: float
) -> bool:
    if not hits:
        return True
    top_score = max(float(h.get("score", 0.0)) for h in hits)
    return top_score < min_score


# ------------------------------------------------------------- experiment runner --
@dataclass
class StrategyResult:
    strategy: str
    metrics: Dict[str, float]
    items: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"strategy": self.strategy, "metrics": self.metrics, "items": self.items}


def evaluate_strategy(
    strategy: str,
    items: Sequence[GoldenItem],
    corpus: CorpusView,
    top_k: int,
    strict_min_score: float,
) -> StrategyResult:
    fn = STRATEGY_FNS[strategy]
    latencies: List[float] = []
    hit_count = 0
    rr_sum = 0.0
    recall_sum = 0.0
    p3_sum = 0.0
    ctx_recall_sum = 0.0
    strict_fallback_count = 0
    items_log: List[Dict[str, Any]] = []
    for item in items:
        t0 = time.perf_counter()
        hits = fn(corpus, item.requirement_text, top_k)
        latencies.append((time.perf_counter() - t0) * 1000.0)
        rank = _hit_rank(hits, item.expected_sources)
        recall = _recall_at_k(hits, item.expected_sources)
        precision_3 = _precision_at(hits, item.expected_sources, k=3)
        context_recall = _context_recall(hits, item.expected_substrings)
        strict_fallback = _strict_mode_fallback(hits, strict_min_score)
        if rank > 0:
            hit_count += 1
            rr_sum += 1.0 / rank
        recall_sum += recall
        p3_sum += precision_3
        ctx_recall_sum += context_recall
        if strict_fallback:
            strict_fallback_count += 1
        items_log.append(
            {
                "id": item.id,
                "case_type": item.case_type,
                "subset": item.subset,
                "hit_rank": rank,
                "recall_at_k": round(recall, 3),
                "precision_at_3": round(precision_3, 3),
                "context_recall": round(context_recall, 3),
                "strict_mode_fallback": strict_fallback,
                "top_sources": [h.get("source") for h in hits],
            }
        )
    n = max(1, len(items))
    metrics = {
        "n": len(items),
        "top_k": top_k,
        "hit_rate_at_k": round(hit_count / n, 4),
        "mrr_at_k": round(rr_sum / n, 4),
        "recall_at_k": round(recall_sum / n, 4),
        "precision_at_3": round(p3_sum / n, 4),
        "context_recall": round(ctx_recall_sum / n, 4),
        "strict_mode_fallback_rate": round(strict_fallback_count / n, 4),
        "latency_p50_ms": round(statistics.median(latencies), 3) if latencies else 0.0,
        "latency_p95_ms": round(_percentile(latencies, 95), 3) if latencies else 0.0,
        "latency_mean_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
    }
    return StrategyResult(strategy=strategy, metrics=metrics, items=items_log)


def _percentile(values: Sequence[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_v[int(k)])
    return float(sorted_v[f] + (sorted_v[c] - sorted_v[f]) * (k - f))


# --------------------------------------------------------------------- CLI --
def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BL-58 retrieval architecture experiments harness",
    )
    parser.add_argument(
        "--golden",
        type=Path,
        default=DEFAULT_GOLDEN,
        help="Path to the retrieval golden set JSONL (default: %(default)s)",
    )
    parser.add_argument(
        "--strategy",
        action="append",
        choices=list(ALL_STRATEGIES) + ["all"],
        help="Strategy to run (repeatable). Use 'all' to enumerate everything.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON report path (default: %(default)s)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_K,
        help="Top-K cap for retrieval (default: %(default)s)",
    )
    parser.add_argument(
        "--strict-min-score",
        type=float,
        default=DEFAULT_STRICT_MIN_SCORE,
        help="strict_min_score threshold for fallback counting (default: %(default)s)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="PRNG seed for any randomised components (default: %(default)s)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-strategy progress logs (CI mode)",
    )
    return parser.parse_args(argv)


def _resolve_strategies(selected: Optional[Sequence[str]]) -> List[str]:
    if not selected:
        return list(ALL_STRATEGIES)
    if "all" in selected:
        return list(ALL_STRATEGIES)
    seen: List[str] = []
    for name in selected:
        if name not in seen:
            seen.append(name)
    return seen


def run(args: argparse.Namespace) -> Dict[str, Any]:
    random.seed(args.seed)
    if not args.quiet:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    items = load_golden_set(args.golden)
    corpus = CorpusView.build(SYNTHETIC_CHUNKS)
    strategies = _resolve_strategies(args.strategy)
    results: List[StrategyResult] = []
    for name in strategies:
        logger.info("Running strategy %s (n=%d, top_k=%d)", name, len(items), args.top_k)
        results.append(
            evaluate_strategy(
                strategy=name,
                items=items,
                corpus=corpus,
                top_k=args.top_k,
                strict_min_score=args.strict_min_score,
            )
        )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "golden_set": str(args.golden),
        "top_k": args.top_k,
        "strict_min_score": args.strict_min_score,
        "seed": args.seed,
        "n_items": len(items),
        "corpus_chunks": len(corpus.chunks),
        "results": [r.to_dict() for r in results],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote report → %s", args.output)
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
