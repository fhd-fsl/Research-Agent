# Product Research Assistant — Problem Statement

## The Problem

People with a product idea usually start with a vague sense of what they want to build, but not a clear picture of what already exists, what's wrong with it, and where the actual opportunity is. Doing this research properly — reading competitor sites, digging through pricing pages, searching Reddit and forums for complaints, reading reviews, cross-referencing all of it — is slow, manual, and easy to do shallowly. Most people either skip this step entirely and build blind, or spend days on it and still miss things because they can't read everything.

The result: products get built that either copy an existing competitor too closely, or solve a problem nobody was actually complaining about.

## Who This Is For

Someone with an early-stage product idea — could be a solo founder, a student project, a side-project builder — who wants a fast, evidence-backed picture of the competitive landscape before they commit time to building. They're not looking for someone to hand them a business plan; they're looking for a well-researched starting point they can reason about themselves.

## What The System Does

The user describes their product idea in plain language. The system then:

1. **Understands the idea** — figures out what category/space the idea sits in, who the target user likely is, and what the core features seem to be, based on what the user described.
2. **Finds real competitors** — searches the web for existing products/companies solving a similar problem.
3. **Digs into those competitors** — pulls their pricing, feature sets, and general positioning from their own sites and from articles/reviews about them.
4. **Finds real user pain points** — searches Reddit, forums, blogs, app store reviews, Hacker News, and other places people actually complain about, praise, or wish for things in this space. This is the part that generic "competitor analysis" tools usually skip, and it's the most valuable part — real complaints from real users are stronger signal than a feature comparison table.

   Sources considered:
   - Reddit (via Reddit's API)
   - Forums and blogs surfaced through search
   - App store reviews (Google Play / Apple App Store), when the idea is mobile-relevant — reviews tend to be specific and blunt ("crashes on export," "wish it had X")
   - Hacker News (via Algolia's free HN Search API) — useful for technical/early-adopter reactions
   - Product Hunt launch comments — useful for seeing what early users of similar products pushed back on
   - Job postings that reveal unmet needs (e.g. a company hiring specifically to solve a problem manually) — a secondary, lower-priority source
   - Sites that actively block automated access (e.g. G2, Capterra) are not scraped directly, but articles/blogs that summarize review sentiment from those sites (which do turn up in normal search) are a valid source
5. **Synthesizes gaps, not verdicts** — cross-references what competitors are missing against what users are actually complaining about, and surfaces candidate gaps/opportunities. Each gap comes with the evidence behind it (which complaints, which competitor weaknesses, how strong the signal is) rather than a single confident "build this" recommendation. The user makes the final call — the system's job is to make that call well-informed, not to make it for them.
6. **Produces a report** — a structured, readable output laying out the competitive landscape, the pain points found, and the candidate gaps with their supporting evidence, so the user can quickly orient themselves and decide how to position or adjust their idea.

The user can also choose how deep the research should go — a fast pass for a quick sanity check, or a deeper pass that covers more sources for something closer to a real research writeup.

## The Relevance Problem (a core requirement, not a detail)

Raw search results are not the same as relevant results. A search for a product's general category will surface things that share keywords but aren't real competitors — wrong target user, wrong scale, wrong core problem, or simply irrelevant. Treating "top N search results" as "the competitors" produces a shallow, noisy report, and this is the actual hard part of doing product research well — most of the manual effort in doing this by hand goes into figuring out what's actually relevant, not into finding things in the first place.

So relevance filtering is not an implementation detail to figure out later — it's a core part of what makes this system useful instead of generic. Before anything gets deep research treatment (pricing analysis, pain-point cross-referencing, inclusion in the final gaps), it needs to be checked against the user's actual idea: does this serve a similar target user, solve a similar core problem, and is it still active — not just "does it share a keyword." The same check applies to pain points and complaints, not just competitors — a complaint about "scheduling apps" in general might be about a completely different use case than the one the user is building.

Candidates that don't clear this bar shouldn't be silently discarded and shouldn't be treated as equal to genuinely relevant ones — they should be set aside as lower-priority or "related but not a direct match," so the user can still see them if they want to, without them diluting the core findings.

This also controls cost and effort sensibly: cast a wide net in the initial search, filter down to what's genuinely relevant, and only spend the expensive, deeper analysis on that smaller, higher-quality set.

## What "Good" Looks Like

- Every claim in the final report is traceable back to an actual source (a real URL, a real Reddit thread, a real competitor page) — not the system inventing plausible-sounding facts.
- The competitors and pain points that make it into the report are actually relevant to the user's specific idea, not just topically adjacent search results.
- The report distinguishes between well-supported findings (multiple independent sources agree) and weaker, more speculative ones — it doesn't present every finding with the same confidence.
- The output is something a person could actually use to make a decision, not a wall of generic AI-generated text that says nothing specific.
- A full run completes in a reasonable amount of time (not hours) and produces a report a person can read in a few minutes.

## What This Is Not

- Not a business plan generator or a "here's your startup idea" tool — it doesn't tell the user what to build.
- Not a replacement for talking to real users — it's a fast first pass to inform that, not a substitute for it.
- Not scraping sites that actively block automated access (e.g., G2, Capterra) — research is done through legitimate search APIs, public APIs (e.g., Reddit's), and publicly accessible pages.

## How It Will Be Built (high level, not architecture)

- A backend system that takes a product idea as input and produces a research report as output, accessible via a simple API to start.
- Real web search and Reddit/forum data is used for research — no fabricated or hallucinated "example" data standing in for real findings.
- The system is built and tested locally first, containerized, and then deployed to the cloud (AWS, free-tier resources) so it's a real, reachable, running service rather than something that only works on one machine.
- A UI is a possible later addition once the backend reliably produces good reports — not a requirement for the first version.

## Constraints / Notes

- The project is meant to be low-cost. Infrastructure (AWS free tier, search API free tiers) should stay free or near-free. For the LLM itself, Groq's free API tier (no credit card required, open-source models like Llama 3.3 70B) is the planned option to keep this at effectively zero cost — with the tradeoff that it's rate-limited (requests/tokens per minute and per day), so agent calls need basic pacing/backoff rather than firing everything at once. This should be kept in mind when deciding how many agents/steps run per research pass, and how large a model each step really needs — simpler extraction steps can use smaller/faster models, reserving more capability for the synthesis step that actually requires judgment.
- Depth of research is configurable so cost and runtime can be controlled per run rather than fixed.
