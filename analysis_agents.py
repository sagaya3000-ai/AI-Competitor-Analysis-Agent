
import os

from crewai import Agent, Task, Crew, LLM


def run_competitor_analysis(company, location, industry, evidence):

    api_key = os.getenv("GEMINI_API_KEY")

    model = os.getenv(
        "GEMINI_MODEL",
        "gemini/gemini-2.5-flash"
    )

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY missing. Please check your .env file."
        )

    llm = LLM(
        model=model,
        api_key=api_key,
        temperature=0.2,
    )

    # Agent 1: Competitor Research
    researcher = Agent(
        role="Competitor Research Analyst",
        goal=(
            "Analyze competitor information and identify "
            "useful public marketing evidence."
        ),
        backstory=(
            "You are a market research analyst. "
            "You distinguish verified facts from assumptions "
            "and never invent competitor information."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    # Agent 2: Marketing Analysis
    marketing_analyst = Agent(
        role="Digital Marketing Analyst",
        goal=(
            "Evaluate competitor marketing signals and "
            "identify strengths and weaknesses."
        ),
        backstory=(
            "You analyze SEO, reputation, advertising signals, "
            "keywords, social media, website quality and "
            "local presence using available evidence."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    # Agent 3: Strategy Recommendations
    strategist = Agent(
        role="Competitive Strategy Advisor",
        goal=(
            "Create practical, prioritized recommendations "
            "to improve the company's competitive position."
        ),
        backstory=(
            "You provide clear marketing advice for businesses. "
            "Your recommendations must be realistic and "
            "based on the available evidence."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    # Task 1: Research
    research_task = Task(
        description=f"""
        Analyze the following company:

        Company: {company}
        Location: {location}
        Industry: {industry}

        Public research evidence:
        {evidence}

        Identify competitor names, websites, observed signals,
        and missing information.

        Do not invent facts, review counts, ad spend,
        or search rankings.
        """,
        expected_output=(
            "A competitor research report with evidence, "
            "website links, findings and data limitations."
        ),
        agent=researcher,
    )

    # Task 2: Marketing Analysis
    marketing_task = Task(
        description="""
        Use the research findings to analyze:

        1. Search visibility
        2. Reputation
        3. Paid activity
        4. Keyword strategy
        5. Social presence
        6. Website quality
        7. Local presence

        Explain strengths, weaknesses and data gaps.
        Never claim that unavailable advertising data
        or private analytics have been verified.
        """,
        expected_output=(
            "A structured marketing analysis explaining "
            "competitor strengths, weaknesses and uncertainties."
        ),
        agent=marketing_analyst,
        context=[research_task],
    )

    # Task 3: Recommendations
    strategy_task = Task(
        description="""
        Prepare 5 to 10 prioritized recommendations
        for the company.

        For each recommendation provide:
        - Priority: High, Medium or Low
        - Action to take
        - Reason
        - Suggested timeframe

        Focus on SEO, customer reviews, website improvements,
        relevant keywords, social content and local visibility.

        Do not invent numerical results.
        """,
        expected_output=(
            "Five to ten actionable recommendations with "
            "priority, explanation and suggested timeframe."
        ),
        agent=strategist,
        context=[research_task, marketing_task],
    )

    # Execute CrewAI workflow
    crew = Crew(
        agents=[
            researcher,
            marketing_analyst,
            strategist,
        ],
        tasks=[
            research_task,
            marketing_task,
            strategy_task,
        ],
        verbose=False,
    )

    result = crew.kickoff()

    return str(result)
