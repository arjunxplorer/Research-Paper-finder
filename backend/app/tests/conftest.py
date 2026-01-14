"""Pytest configuration and fixtures."""

import pytest
import asyncio
from typing import Generator

from app.adapters.base import PaperResult, Author
from app.dedup.merge import MergedPaper


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_paper_result() -> PaperResult:
    """Create a sample PaperResult for testing."""
    return PaperResult(
        title="Attention Is All You Need",
        source="semantic_scholar",
        doi="10.5555/3295222.3295349",
        source_id="204e3073870fae3d05bcbc2f6a8e263d9b72e776",
        abstract="The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder.",
        year=2017,
        venue="NIPS",
        authors=[
            Author(name="Ashish Vaswani"),
            Author(name="Noam Shazeer"),
            Author(name="Niki Parmar"),
        ],
        citation_count=50000,
        oa_url="https://arxiv.org/pdf/1706.03762.pdf",
        publisher_url="https://papers.nips.cc/paper/7181-attention-is-all-you-need",
        topics=["Deep Learning", "NLP", "Attention"],
        is_survey=False,
        is_open_access=True,
    )


@pytest.fixture
def sample_merged_paper() -> MergedPaper:
    """Create a sample MergedPaper for testing."""
    return MergedPaper(
        id="test-uuid-1234",
        doi="10.5555/3295222.3295349",
        title="Attention Is All You Need",
        abstract="The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
        year=2017,
        venue="NIPS",
        authors=[
            Author(name="Ashish Vaswani"),
            Author(name="Noam Shazeer"),
        ],
        citation_count=50000,
        citation_source="semantic_scholar",
        oa_url="https://arxiv.org/pdf/1706.03762.pdf",
        publisher_url="https://papers.nips.cc/paper/7181-attention-is-all-you-need",
        doi_url="https://doi.org/10.5555/3295222.3295349",
        topics=["Deep Learning", "NLP"],
        is_survey=False,
        is_open_access=True,
        source_ids={"semantic_scholar": "204e3073870fae3d05bcbc2f6a8e263d9b72e776"},
        sources=["semantic_scholar"],
    )


@pytest.fixture
def sample_papers_for_ranking() -> list[MergedPaper]:
    """Create sample papers for ranking tests."""
    return [
        MergedPaper(
            id="paper-1",
            doi="10.1234/paper1",
            title="High Citation Paper",
            abstract="A highly cited paper.",
            year=2015,
            venue="Nature",
            authors=[Author(name="Alice Smith")],
            citation_count=10000,
            citation_source="semantic_scholar",
            oa_url=None,
            publisher_url="https://nature.com/paper1",
            doi_url="https://doi.org/10.1234/paper1",
            topics=["AI"],
            is_survey=False,
            is_open_access=False,
        ),
        MergedPaper(
            id="paper-2",
            doi="10.1234/paper2",
            title="Recent Paper with Momentum",
            abstract="A recent paper gaining traction.",
            year=2024,
            venue="ICML",
            authors=[Author(name="Bob Jones")],
            citation_count=500,
            citation_source="semantic_scholar",
            oa_url="https://arxiv.org/pdf/paper2.pdf",
            publisher_url="https://icml.cc/paper2",
            doi_url="https://doi.org/10.1234/paper2",
            topics=["AI", "ML"],
            is_survey=False,
            is_open_access=True,
        ),
        MergedPaper(
            id="paper-3",
            doi="10.1234/paper3",
            title="Survey Paper",
            abstract="A comprehensive survey.",
            year=2022,
            venue="ACM Computing Surveys",
            authors=[Author(name="Carol White")],
            citation_count=2000,
            citation_source="openalex",
            oa_url="https://arxiv.org/pdf/paper3.pdf",
            publisher_url="https://dl.acm.org/paper3",
            doi_url="https://doi.org/10.1234/paper3",
            topics=["AI", "Survey"],
            is_survey=True,
            is_open_access=True,
        ),
    ]

