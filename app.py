
import os
import re
import json
from urllib.parse import urlparse

import requests
import pandas as pd
import plotly.express as px
import streamlit as st
from bs4 import BeautifulSoup
from ddgs import DDGS
from dotenv import load_dotenv

from agents.analysis_agents import run_competitor_analysis

load_dotenv()

st.set_page_config(
    page_title="NEXUS | Competitor Intelligence",
    page_icon="🔎",
    layout="wide",
)

WEIGHTS = {
    "🔍 Search Visibility": 25,
    "⭐ Reputation": 20,
    "📢 Paid Activity": 15,
    "🔑 Keyword Strategy": 15,
    "🌐 Social Presence": 10,
    "💻 Website Quality": 10,
    "📍 Local Presence": 5,
}

st.markdown("""
<style>
.stApp {
    background:
        radial-gradient(ellipse at 10% 0%, #25245a 0%, transparent 42%),
        radial-gradient(ellipse at 90% 10%, #123c50 0%, transparent 35%),
        #0b1120;
    color: #e5e7eb;
}
[data-testid="stMetric"] {
    background: rgba(255,255,255,.06);
    border: 1px solid rgba(148,163,184,.22);
    border-radius: 16px;
    padding: 18px;
}
[data-testid="stSidebar"] {
    background: #111827;
}
.hero {
    font-size: 2.8rem;
    font-weight: 850;
    background: linear-gradient(90deg,#818cf8,#22d3ee);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.panel {
    background: rgba(255,255,255,.045);
    border: 1px solid rgba(148,163,184,.22);
    border-radius: 16px;
    padding: 18px;
    margin-bottom: 12px;
}
</style>
""", unsafe_allow_html=True)


def search_web(query, limit=8):
    """Search public web results."""
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=limit))
    except Exception:
        return []


def inspect_website(url):
    info = {
        "reachable": False,
        "title": "",
        "description": "",
        "https": False,
        "mobile_hint": False,
    }

    if not url or not url.startswith(("http://", "https://")):
        return info

    info["https"] = url.lower().startswith("https://")

    try:
        response = requests.get(
            url,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        info["reachable"] = response.status_code < 400

        soup = BeautifulSoup(response.text[:500000], "html.parser")

        if soup.title:
            info["title"] = soup.title.get_text(" ", strip=True)

        meta = soup.find(
            "meta",
            attrs={"name": re.compile("^description$", re.I)},
        )
        if meta:
            info["description"] = meta.get("content", "") or ""

        info["mobile_hint"] = (
            soup.find("meta", attrs={"name": "viewport"}) is not None
        )

    except requests.RequestException:
        pass

    return info


def calculate_scores(location, industry, results, website):
    text = " ".join(
        str(r.get("title", "")) + " " + str(r.get("body", ""))
        for r in results
    ).lower()

    urls = [str(r.get("href", "")) for r in results]

    location_words = [
        word.lower() for word in location.split() if len(word) > 2
    ]
    industry_words = [
        word.lower() for word in industry.split() if len(word) > 2
    ]

    scores = {}

    scores["🔍 Search Visibility"] = min(
        100, 20 + len(results) * 8
    )

    review_terms = ["review", "rating", "testimonial", "customer feedback"]
    scores["⭐ Reputation"] = min(
        100, 25 + sum(term in text for term in review_terms) * 15
    )

    # Placeholder until genuine advertising evidence is available.
    scores["📢 Paid Activity"] = 25

    keyword_matches = sum(word in text for word in industry_words)
    scores["🔑 Keyword Strategy"] = min(
        100, 20 + keyword_matches * 10
    )

    social_domains = [
        "instagram.com", "facebook.com", "linkedin.com",
        "youtube.com", "x.com", "tiktok.com",
    ]
    social_count = sum(
        any(domain in url.lower() for domain in social_domains)
        for url in urls
    )
    scores["🌐 Social Presence"] = min(100, 20 + social_count * 20)

    website_score = 20
    if website["reachable"]:
        website_score += 35
    if website["https"]:
        website_score += 15
    if website["title"]:
        website_score += 15
    if website["description"]:
        website_score += 10
    if website["mobile_hint"]:
        website_score += 5

    scores["💻 Website Quality"] = min(100, website_score)

    local_matches = sum(word in text for word in location_words)
    scores["📍 Local Presence"] = min(
        100,
        25 + local_matches * 15 + (10 if website["reachable"] else 0),
    )

    total = sum(
        scores[category] * weight / 100
        for category, weight in WEIGHTS.items()
    )

    return round(total, 1), scores


def get_threat(score):
    if score >= 70:
        return "🔴 High"
    if score >= 40:
        return "🟠 Medium"
    return "🟢 Low"


def discover_competitors(company, location, industry, limit):
    query = f"{industry} businesses competitors in {location}"
    results = search_web(query, limit=limit * 2)

    competitors = []
    seen_domains = set()

    for item in results:
        url = item.get("href", "")
        title = item.get("title", "").strip()

        if not url.startswith(("http://", "https://")) or not title:
            continue

        domain = urlparse(url).netloc.lower().removeprefix("www.")

        company_domain = ""
        if company.startswith(("http://", "https://")):
            company_domain = (
                urlparse(company).netloc.lower().removeprefix("www.")
            )

        if not domain or domain in seen_domains:
            continue

        if domain == company_domain:
            continue

        if any(x in domain for x in [
            "wikipedia.org", "youtube.com", "reddit.com"
        ]):
            continue

        seen_domains.add(domain)

        competitors.append({
            "Competitor": title[:100],
            "Website": url,
            "Domain": domain,
            "Evidence": item.get("body", ""),
        })

        if len(competitors) >= limit:
            break

    return competitors


def create_recommendations(own_scores, competitor_average):
    suggestions = {
        "🔍 Search Visibility":
            "Improve local SEO and create useful service pages.",
        "⭐ Reputation":
            "Request honest customer reviews and respond to feedback.",
        "📢 Paid Activity":
            "Check public ad libraries before planning paid campaigns.",
        "🔑 Keyword Strategy":
            "Target relevant industry and location search terms.",
        "🌐 Social Presence":
            "Publish useful content consistently on relevant platforms.",
        "💻 Website Quality":
            "Improve mobile usability, page speed and contact options.",
        "📍 Local Presence":
            "Keep business details consistent across local listings.",
    }

    items = []

    for category in WEIGHTS:
        gap = competitor_average[category] - own_scores[category]

        if gap > 0:
            items.append({
                "Category": category,
                "Priority": "High" if gap >= 20 else "Medium",
                "Gap": round(gap, 1),
                "Recommendation": suggestions[category],
            })

    items.sort(key=lambda x: x["Gap"], reverse=True)

    if not items:
        items.append({
            "Category": "Growth",
            "Priority": "Medium",
            "Gap": 0,
            "Recommendation":
                "Validate the available evidence and test one measurable improvement.",
        })

    return items[:8]


# ---------------- MAIN DASHBOARD ----------------

st.markdown(
    '<div class="hero">NEXUS INTELLIGENCE</div>',
    unsafe_allow_html=True,
)
st.write("AI Competitor Analysis Agent")
st.caption(
    "Public web research • Gemini AI • CrewAI • Weighted marketing scores"
)

with st.sidebar:
    st.header("Research Settings")

    company = st.text_input(
        "Your Company Name",
        placeholder="ABC Digital",
    )

    location = st.text_input(
        "City / Location",
        value="Chennai, India",
    )

    industry = st.text_input(
        "Industry",
        placeholder="Digital Marketing Agency",
    )

    own_url = st.text_input(
        "Your Website (optional)",
        placeholder="https://example.com",
    )

    limit = st.slider(
        "Number of Competitors",
        min_value=3,
        max_value=10,
        value=5,
    )

    run_button = st.button(
        "🚀 Run Competitor Analysis",
        type="primary",
        use_container_width=True,
    )

st.info(
    "Scores are heuristic estimates from available search results. "
    "They are not verified Google rankings, advertising spend, or sales data."
)

if run_button:
    if not company.strip() or not location.strip() or not industry.strip():
        st.error("Please enter your company, location and industry.")
        st.stop()

    if not os.getenv("GEMINI_API_KEY"):
        st.error("GEMINI_API_KEY missing. Check your .env file.")
        st.stop()

    with st.spinner("Discovering competitors..."):
        own_results = search_web(
            f"{company} {industry} {location} official website",
            limit=8,
        )
        competitors = discover_competitors(
            company, location, industry, limit
        )

    if not competitors:
        st.error(
            "No competitors found. Check your internet connection, "
            "try another search, or retry later."
        )
        st.stop()

    with st.spinner("Analyzing websites and marketing signals..."):
        own_website = inspect_website(own_url) if own_url else {
            "reachable": False,
            "title": "",
            "description": "",
            "https": False,
            "mobile_hint": False,
        }

        own_score, own_scores = calculate_scores(
            location, industry, own_results, own_website
        )

        records = []
        evidence_list = []

        for competitor in competitors:
            website = inspect_website(competitor["Website"])

            results = search_web(
                f'"{competitor["Domain"]}" {location} {industry}',
                limit=5,
            )

            if not results:
                results = [{
                    "title": competitor["Competitor"],
                    "body": competitor["Evidence"],
                    "href": competitor["Website"],
                }]

            score, scores = calculate_scores(
                location, industry, results, website
            )

            records.append({
                "Competitor": competitor["Competitor"],
                "Website": competitor["Website"],
                "Score": score,
                "Threat": get_threat(score),
                **scores,
            })

            evidence_list.append({
                "name": competitor["Competitor"],
                "url": competitor["Website"],
                "snippet": competitor["Evidence"],
                "website": website,
                "scores": scores,
            })

    df = pd.DataFrame(records)
    avg_score = float(df["Score"].mean())
    gap = round(own_score - avg_score, 1)

    average_scores = {
        category: float(df[category].mean())
        for category in WEIGHTS
    }

    st.session_state["results"] = {
        "company": company,
        "location": location,
        "industry": industry,
        "own_score": own_score,
        "own_scores": own_scores,
        "average_score": avg_score,
        "gap": gap,
        "df": df,
        "average_scores": average_scores,
        "evidence": evidence_list,
    }


# ---------------- RESULTS ----------------

if "results" in st.session_state:
    result = st.session_state["results"]
    df = result["df"]

    st.subheader("📊 Executive Overview")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Your Score", f'{result["own_score"]}/100')
    c2.metric("Competitors", len(df))
    c3.metric("Competitor Average", f'{result["average_score"]:.1f}')
    c4.metric("Gap vs Average", f'{result["gap"]:+.1f}')

    st.caption(
        "Positive gap means your estimated score is above average; "
        "negative gap means it is below average."
    )

    left, right = st.columns(2)

    with left:
        st.subheader("🏆 Competitor Strength")

        fig = px.bar(
            df.sort_values("Score"),
            x="Score",
            y="Competitor",
            orientation="h",
            color="Score",
            range_color=[0, 100],
            color_continuous_scale=[
                "#22c55e", "#f59e0b", "#ef4444"
            ],
        )

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False,
        )

        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("🎯 Your Marketing Profile")

        profile = pd.DataFrame({
            "Category": list(WEIGHTS.keys()),
            "Score": [
                result["own_scores"][category]
                for category in WEIGHTS
            ],
        })

        fig2 = px.bar(
            profile,
            x="Category",
            y="Score",
            range_y=[0, 100],
            color="Score",
            color_continuous_scale=[
                "#ef4444", "#f59e0b", "#22c55e"
            ],
        )

        fig2.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False,
            xaxis_tickangle=-35,
        )

        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("⚖️ Weighted Score Breakdown")

    breakdown = pd.DataFrame({
        "Category": list(WEIGHTS.keys()),
        "Weight (%)": list(WEIGHTS.values()),
        "Your Score": [
            result["own_scores"][key] for key in WEIGHTS
        ],
        "Competitor Average": [
            result["average_scores"][key] for key in WEIGHTS
        ],
    })

    st.dataframe(breakdown, use_container_width=True, hide_index=True)

    st.subheader("🔎 Competitor Comparison")

    display_columns = [
        "Competitor", "Website", "Score", "Threat"
    ] + list(WEIGHTS.keys())

    st.dataframe(
        df[display_columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Website": st.column_config.LinkColumn("Website"),
            "Score": st.column_config.ProgressColumn(
                "Strength Score",
                min_value=0,
                max_value=100,
                format="%.1f",
            ),
        },
    )

    st.subheader("💡 Prioritized Recommendations")

    ideas = create_recommendations(
        result["own_scores"],
        result["average_scores"],
    )

    for number, idea in enumerate(ideas, 1):
        st.markdown(
            f"""
            <div class="panel">
                <b>{number}. {idea["Category"]}</b>
                &nbsp; | &nbsp; <b>{idea["Priority"]} Priority</b>
                <p>{idea["Recommendation"]}</p>
                <small>Estimated gap: {idea["Gap"]} points</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("🤖 Gemini + CrewAI Analysis")

    if st.button("Generate AI Strategy Report", type="primary"):
        try:
            evidence = json.dumps(
                result["evidence"],
                ensure_ascii=False,
                indent=2,
            )

            with st.spinner("CrewAI agents are analyzing the evidence..."):
                report = run_competitor_analysis(
                    result["company"],
                    result["location"],
                    result["industry"],
                    evidence,
                )

            st.markdown(report)

        except Exception as exc:
            st.error(f"AI analysis failed: {exc}")
            st.info(
                "Check your API key, Gemini model access, quota, "
                "and agents/analysis_agents.py."
            )

    st.subheader("📁 Research Evidence")

    for item in result["evidence"]:
        with st.expander(item["name"]):
            st.write("Website:", item["url"])
            st.write("Search snippet:", item["snippet"])
            st.write("Website inspection:", item["website"])

    st.download_button(
        "⬇️ Download CSV Report",
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name="competitor_analysis.csv",
        mime="text/csv",
    )

st.caption(
    "NEXUS Intelligence | Public data only | "
    "Paid advertising activity is not verified in this version."
)
