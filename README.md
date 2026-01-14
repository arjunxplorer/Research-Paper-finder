# Best Papers Finder

A web tool for faculty and students to find the **Top 20** research papers for any field from a topic query.

## Features

- **Two Search Modes**:
  - **Foundational**: Classic, highly-cited papers that shaped the field
  - **Recent**: Recent papers with fast-rising citations and momentum

- **Filters**:
  - Year range
  - Open access only
  - Survey/Review papers only
  - Source toggles (PubMed, arXiv)

- **Paper Cards Include**:
  - Title, authors, year, venue
  - Citation count with source
  - Abstract (expandable)
  - Links: DOI, Publisher, Open Access
  - "Why recommended" explanations

- **Data Sources**:
  - Semantic Scholar
  - OpenAlex
  - PubMed (optional)
  - arXiv (optional)
  - Unpaywall (for OA link enrichment)

## Project Structure

```
Research_tool/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── adapters/       # Source API adapters
│   │   ├── ranking/        # Ranking and scoring
│   │   ├── dedup/          # Deduplication and merging
│   │   ├── cache/          # Caching layer
│   │   ├── db/             # Database models
│   │   └── tests/          # Unit and integration tests
│   └── requirements.txt
├── frontend/               # Next.js frontend
│   ├── app/               # App router pages
│   ├── components/        # React components
│   └── lib/               # Utilities and hooks
└── mvp.md                 # Original specification
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (optional, uses in-memory cache for MVP)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (optional)
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/papers
export UNPAYWALL_EMAIL=your@email.com
export SEMANTIC_SCHOLAR_API_KEY=your_key  # Optional, for higher rate limits

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run the development server
npm run dev
```

The frontend will be available at http://localhost:3000 and will connect to the backend at http://localhost:8000.

### Running Tests

```bash
cd backend
pytest app/tests/ -v
```

## API Endpoints

### Search

```
GET /search
  ?q=topic                    # Required: search query
  &mode=foundational|recent   # Required: ranking mode
  &year_min=int              # Optional: minimum year
  &year_max=int              # Optional: maximum year
  &oa_only=bool              # Optional: open access only
  &survey_only=bool          # Optional: survey/review only
  &include_pubmed=bool       # Optional: include PubMed (default: true)
  &include_arxiv=bool        # Optional: include arXiv (default: true)
```

Returns top 20 ranked papers with metadata and explanations.

### Paper Details

```
GET /paper/{id}              # Get paper metadata
GET /paper/{id}/related      # Get related papers
```

## Ranking Algorithm

### Foundational Mode
Prioritizes classic, highly-cited papers:
- 45% Relevance score
- 35% Log-scaled citations
- 10% Venue signal
- 5% Survey bonus
- 5% Open access bonus

### Recent Mode
Prioritizes papers with momentum:
- 55% Relevance score
- 25% Citation velocity
- 15% Recency score
- 3% Venue signal
- 2% Open access bonus

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | In-memory cache |
| `SEMANTIC_SCHOLAR_API_KEY` | API key for higher rate limits | None (uses public API) |
| `UNPAYWALL_EMAIL` | Email for Unpaywall API access | user@example.com |
| `SEARCH_CACHE_TTL_HOURS` | Cache TTL for search results | 24 |
| `PAPER_CACHE_TTL_DAYS` | Cache TTL for paper metadata | 7 |

## Architecture

```
Frontend (Next.js)
    ↓
Backend API (FastAPI)
    ↓
┌───────────────────────────────────────┐
│           Source Adapters              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │Semantic │ │OpenAlex │ │ PubMed  │  │
│  │Scholar  │ │         │ │         │  │
│  └─────────┘ └─────────┘ └─────────┘  │
│  ┌─────────┐ ┌─────────┐              │
│  │  arXiv  │ │Unpaywall│              │
│  └─────────┘ └─────────┘              │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│         Processing Pipeline            │
│  Normalize → Dedupe → Enrich → Rank   │
└───────────────────────────────────────┘
    ↓
Cache Layer → PostgreSQL (optional)
```

## License

MIT

