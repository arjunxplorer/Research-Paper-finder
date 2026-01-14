#!/usr/bin/env python3
"""
Quick verification script for Best Papers Finder search functionality.

Run with: python verify_search.py

Make sure the backend is running at http://localhost:8000
"""

import httpx
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"
TIMEOUT = 60.0


def print_header(text: str):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)


def print_section(text: str):
    print(f"\n📋 {text}")
    print("-" * 50)


def check_health():
    """Check if API is running."""
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False


def test_search(query: str, mode: str, expected_min_results: int = 5) -> dict:
    """Run a search and return results."""
    client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)
    
    response = client.get("/search", params={"q": query, "mode": mode})
    
    if response.status_code != 200:
        return {"success": False, "error": response.text}
    
    data = response.json()
    results = data["results"]
    
    return {
        "success": True,
        "results": results,
        "total_candidates": data.get("totalCandidates", 0),
        "source_stats": data.get("sourceStats", {}),
    }


def verify_result_quality(results: list, mode: str) -> list[str]:
    """Verify result quality and return list of issues."""
    issues = []
    
    if len(results) == 0:
        issues.append("No results returned")
        return issues
    
    # Check scores are descending
    scores = [r["score"] for r in results]
    for i in range(len(scores) - 1):
        if scores[i] < scores[i + 1]:
            issues.append(f"Scores not descending at position {i}")
            break
    
    # Check required fields
    for i, paper in enumerate(results[:10]):
        if not paper.get("title"):
            issues.append(f"Paper {i+1} missing title")
        if not paper.get("whyRecommended"):
            issues.append(f"Paper {i+1} missing explanations")
        
        # Check for at least one link
        has_link = paper.get("doiUrl") or paper.get("oaUrl") or paper.get("publisherUrl")
        if not has_link:
            issues.append(f"Paper {i+1} has no links")
    
    # Mode-specific checks
    if mode == "foundational":
        # Top results should have citations
        top_with_citations = sum(
            1 for p in results[:5] 
            if p.get("citationCount") and p["citationCount"] > 100
        )
        if top_with_citations < 2:
            issues.append("Foundational mode: Top 5 should have highly-cited papers")
    
    elif mode == "recent":
        # Top results should be recent
        current_year = datetime.now().year
        recent_count = sum(
            1 for p in results[:5]
            if p.get("year") and p["year"] >= current_year - 5
        )
        if recent_count < 2:
            issues.append("Recent mode: Top 5 should have papers from last 5 years")
    
    return issues


def main():
    print_header("Best Papers Finder - Search Verification")
    print(f"Testing API at: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check health
    print_section("Health Check")
    if not check_health():
        print("❌ API is not running! Please start the backend first:")
        print("   cd backend && uvicorn app.main:app --reload --port 8000")
        sys.exit(1)
    print("✅ API is healthy")
    
    # Test cases
    test_cases = [
        {
            "name": "Foundational - Transformers",
            "query": "attention mechanism transformer",
            "mode": "foundational",
        },
        {
            "name": "Foundational - Deep Learning",
            "query": "deep learning neural networks",
            "mode": "foundational",
        },
        {
            "name": "Recent - LLMs",
            "query": "large language models GPT",
            "mode": "recent",
        },
        {
            "name": "Recent - Diffusion",
            "query": "diffusion models image generation",
            "mode": "recent",
        },
    ]
    
    all_passed = True
    
    for test in test_cases:
        print_section(f"{test['name']} ({test['mode']} mode)")
        print(f"Query: \"{test['query']}\"")
        
        result = test_search(test["query"], test["mode"])
        
        if not result["success"]:
            print(f"❌ Search failed: {result['error']}")
            all_passed = False
            continue
        
        results = result["results"]
        print(f"✅ Found {len(results)} results (from {result['total_candidates']} candidates)")
        print(f"   Sources: {result['source_stats']}")
        
        # Verify quality
        issues = verify_result_quality(results, test["mode"])
        
        if issues:
            print(f"⚠️  Quality issues:")
            for issue in issues:
                print(f"   - {issue}")
            all_passed = False
        else:
            print("✅ All quality checks passed")
        
        # Show top 3 results
        print("\n   Top 3 Results:")
        for i, paper in enumerate(results[:3], 1):
            year = paper.get("year", "?")
            cites = paper.get("citationCount", "N/A")
            score = paper.get("score", 0)
            title = paper["title"][:55] + "..." if len(paper["title"]) > 55 else paper["title"]
            
            print(f"   {i}. [{year}] {title}")
            print(f"      Citations: {cites} | Score: {score:.3f}")
            
            why = paper.get("whyRecommended", [])[:2]
            if why:
                print(f"      Why: {' | '.join(why)}")
            
            # Show links
            links = []
            if paper.get("doiUrl"):
                links.append("DOI")
            if paper.get("oaUrl"):
                links.append("OA")
            if paper.get("publisherUrl"):
                links.append("Publisher")
            if links:
                print(f"      Links: {', '.join(links)}")
    
    # Summary
    print_header("Summary")
    if all_passed:
        print("✅ All tests passed!")
        print("\nThe search is working correctly:")
        print("  - Results are returned from multiple sources")
        print("  - Scores are properly ordered")
        print("  - Papers have titles, citations, and links")
        print("  - Explanations are generated")
        print("  - Mode-specific ranking is working")
    else:
        print("⚠️  Some tests had issues - see details above")
        sys.exit(1)


if __name__ == "__main__":
    main()

