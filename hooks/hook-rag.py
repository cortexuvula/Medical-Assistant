# -*- coding: utf-8 -*-
"""
PyInstaller hook for the internal rag package.

Ensures all RAG modules including models.py with TemporalInfo
are properly collected.
"""

import os
import sys

# Add src to path to find the rag package
spec_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(spec_dir, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect all rag submodules
hiddenimports = collect_submodules('rag')

# Explicitly list all rag modules to ensure they're included
hiddenimports += [
    'rag',
    'rag.models',
    'rag.adaptive_threshold',
    'rag.bm25_search',
    'rag.cache',
    'rag.embedding_manager',
    'rag.graph_data_provider',
    'rag.graphiti_client',
    'rag.health_manager',
    'rag.hybrid_retriever',
    'rag.medical_ner',
    'rag.mmr_reranker',
    'rag.neon_migrations',
    'rag.neon_vector_store',
    'rag.query_expander',
    'rag.rag_resilience',
    'rag.search_config',
    'rag.temporal_reasoner',
    'rag.conversation_manager',
    'rag.conversation_summarizer',
    'rag.entity_classifier',
    'rag.entity_deduplicator',
    'rag.feedback_manager',
    'rag.followup_detector',
    'rag.search_syntax_parser',
    'rag.streaming_models',
    'rag.streaming_retriever',
    'rag.cancellation',
]

# Collect data files
datas = collect_data_files('rag')
