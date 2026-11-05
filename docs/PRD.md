# Product Requirements Document (PRD)
# AI Stock Analyst – Institutional-Grade Equity Research Platform

## 1. Product Overview

Build a modern, responsive web application that acts as an AI-powered stock research analyst.

The application should allow users to enter any publicly listed stock ticker and generate a comprehensive, data-driven investment analysis report.

The tool should analyse the company's:
- Business model and competitive positioning.
- Financial health and historical performance.
- Revenue and earnings growth.
- Profitability and operational efficiency.
- Valuation and intrinsic value.
- Technical indicators and price momentum.
- Industry outlook and competitive advantages.
- Management, risks and future growth opportunities.
- Institutional ownership and market sentiment.
- Potential long-term investment returns.

The application must produce an overall investment recommendation:

**BUY / STRONG BUY / HOLD / SELL / STRONG SELL**

Every analysed stock must also be compared against four permanent benchmark companies:

1. Microsoft (MSFT)
2. Alphabet / Google (GOOGL)
3. Meta Platforms (META)
4. Apple (AAPL)

The comparison should be available in a comprehensive side-by-side financial and investment metrics table.

### Primary objective

Help an investor identify high-quality companies trading at attractive valuations, discover potential multibagger opportunities, avoid overvalued stocks and make better long-term investment decisions.

### Target user

A long-term investor with:
- Investment horizon: 5–10 years.
- Moderate risk tolerance.
- Interest in global equities, particularly US, European and Indian markets.
- Preference for companies with strong competitive advantages, defensible business models and substantial growth potential.
- Interest in emerging industries such as AI, robotics, autonomous systems, semiconductors and automation.

---

## 2. Main User Experience

### Landing page

Create a clean, professional financial research dashboard.

The landing page should contain:

**A. Stock search**

A prominent search bar:

"Enter company name or ticker symbol"

Examples:
- NVDA
- GOOGL
- OUST
- TER
- SHA0.DE
- JYOTICNC.NS

The application should automatically identify:
- Company name.
- Ticker symbol.
- Exchange.
- Country.
- Industry and sector.
- Trading currency.

Allow the user to select the correct exchange when a ticker is ambiguous.

**B. Analyse button**

On submission, retrieve the latest available financial and market data, conduct the analysis and generate a comprehensive stock research report.

**C. Benchmark companies**

Always display the four benchmark companies:

- Microsoft
- Alphabet
- Meta
- Apple

**D. Recent analyses**

Show previously analysed stocks with:
- Company name and ticker.
- Latest rating.
- Last analysed date.
- Stock price at last analysis.
- Change since last analysis.

Allow users to reopen historical reports and compare rating changes.

---

## 3. Stock Analysis Dashboard

After entering a ticker, generate a detailed dashboard with the following sections.

### Section 1: Investment Summary

Display an executive summary at the top.

Include:

- Company name and ticker.
- Current share price.
- Market capitalisation.
- Exchange and trading currency.
- Sector and industry.
- Latest available price timestamp.
- 52-week high and low.
- Overall investment rating.
- Confidence score.
- Fair value estimate.
- Potential upside/downside percentage.
- Investment horizon.
- Risk classification.

Example layout:

| Metric | Result |
|---|---|
| Current price | Live/latest available |
| Market cap | Latest |
| Overall rating | BUY |
| Fair value | Model estimate |
| Expected upside | +35% |
| Risk level | Medium |
| Investment horizon | 5 years |
| Confidence | 82/100 |

The rating must be generated from transparent analysis, not simply an AI-generated opinion.

Include a short explanation:

- Why is this stock attractive?
- What could drive its growth?
- What could go wrong?
- Is the current price attractive?
- What would change the recommendation?

### Section 2: Company Overview and Business Model

Analyse the company's business in detail.

Include:
- Company history and background.
- Main products and services.
- Revenue segments.
- Geographic revenue distribution.
- Customer segments.
- Major customers, where publicly disclosed.
- Main competitors.
- Industry position.
- Business model and revenue streams.
- Recurring versus non-recurring revenue.
- Competitive advantages.
- Barriers to entry.
- Technology and intellectual property.
- Dependency on suppliers or major customers.

Explain how the company makes money in simple language.

Identify whether the business has a defensible moat.

Moat assessment:
- Brand strength.
- Network effects.
- Switching costs.
- Cost advantages.
- Proprietary technology.
- Patents and intellectual property.
- Distribution advantages.
- Economies of scale.
- Regulatory advantages.

Give each moat category a score from 1–10, with evidence supporting the score.

### Section 3: Financial Performance

Analyse historical financial performance over the last 5–10 financial years, where data is available.

Include the following metrics:

**Revenue**
- Annual revenue.
- Revenue growth YoY.
- Revenue CAGR (3 years).
- Revenue CAGR (5 years).
- Quarterly revenue growth.
- Segment-wise revenue growth.
- Geographic revenue growth.

**Profitability**
- Gross profit.
- Gross margin.
- Operating profit.
- Operating margin.
- EBITDA.
- EBITDA margin.
- Net income.
- Net profit margin.
- Earnings per share.
- EPS growth.
- Free cash flow.

**Financial health**
- Cash and cash equivalents.
- Total debt.
- Net debt.
- Net debt / EBITDA.
- Current ratio.
- Quick ratio.
- Interest coverage.
- Operating cash flow.
- Free cash flow.
- Capital expenditure.
- Working capital.
- Debt maturity profile, where available.

**Efficiency**
- Return on equity (ROE).
- Return on invested capital (ROIC).
- Return on assets (ROA).
- Asset turnover.
- Inventory turnover.
- Cash conversion cycle.

For every metric, show:
- Latest value.
- Historical trend.
- Industry/peer comparison.
- Whether the trend is improving or deteriorating.

Use charts for revenue, operating margin, net income, EPS and free cash flow.

### Section 4: Valuation Analysis

This is one of the most important sections.

Evaluate whether the stock is cheap, fairly valued or expensive.

Include:

**Market valuation**
- Market capitalisation.
- Enterprise value.
- P/E ratio.
- Forward P/E.
- PEG ratio.
- Price-to-sales.
- Price-to-book.
- EV/EBITDA.
- EV/EBIT.
- EV/Revenue.
- Price-to-free-cash-flow.
- Free cash flow yield.
- Earnings yield.
- Dividend yield.
- Share buyback yield, where available.

**Historical valuation**
- Current valuation versus 3-year historical average.
- Current valuation versus 5-year historical average.
- Current valuation versus 10-year historical average, where available.
- Current valuation versus industry average.
- Current valuation versus direct competitors.

Clearly identify whether the stock is trading at a historical premium or discount.

**Intrinsic valuation**

Implement at least two valuation methods:

1. Discounted Cash Flow (DCF).
2. Comparable company valuation.

Where applicable, add:
3. Dividend Discount Model.
4. Sum-of-the-parts valuation.

DCF assumptions must be visible and editable:
- Revenue growth.
- Operating margin.
- Tax rate.
- Capital expenditure.
- Working capital.
- Free cash flow growth.
- Discount rate / WACC.
- Terminal growth rate.
- Projection period.

Show:
- Bear-case intrinsic value.
- Base-case intrinsic value.
- Bull-case intrinsic value.
- Current market price.
- Margin of safety.
- Potential upside/downside.

Do not present a DCF estimate as an objective fact. Explain the sensitivity of the result to the assumptions.

### Section 5: Growth Potential and Multibagger Analysis

This section is especially important.

Evaluate whether the company has the potential to become a 2x, 3x, 5x or 10x investment over 5–10 years.

Analyse:
- Addressable market (TAM).
- Serviceable available market (SAM).
- Expected industry growth.
- Market share potential.
- Product expansion.
- Geographic expansion.
- New technologies.
- AI and automation opportunities.
- Competitive threats.
- Operating leverage.
- Scalability.
- Future revenue opportunities.

Provide three scenarios:

**Bear case**
- Weak growth.
- Margin pressure.
- Competitive challenges.
- Valuation compression.

**Base case**
- Realistic revenue growth.
- Expected margin evolution.
- Reasonable valuation assumptions.

**Bull case**
- Strong market adoption.
- Successful product expansion.
- Market share gains.
- Significant operating leverage.

For each scenario, estimate:

| Metric | Bear | Base | Bull |
|---|---:|---:|---:|
| Revenue CAGR | | | |
| EPS CAGR | | | |
| Revenue in year 5 | | | |
| Expected P/E | | | |
| Estimated share price | | | |
| Total return | | | |
| Annualised return | | | |

Include a multibagger assessment:

- Is 2x plausible?
- Is 3x plausible?
- Is 5x plausible?
- Is 10x plausible?
- What market capitalisation would the company need to reach?
- What revenue and earnings would justify that valuation?
- What market share would be required?

Do not assign arbitrary multibagger probabilities. Explain the assumptions and practical barriers to each outcome.

### Section 6: Competitive Advantage and Industry Position

Identify the company's most important competitors.

Compare:
- Market share.
- Revenue growth.
- Gross margins.
- Operating margins.
- R&D investment.
- Product differentiation.
- Technology advantages.
- Customer concentration.
- Pricing power.
- Switching costs.
- Competitive threats.

Explicitly evaluate competition from large incumbents.

For example:
- Could Microsoft, Google, Amazon or NVIDIA replicate the company's technology?
- Could a large competitor develop an in-house alternative?
- Is the company a critical supplier or an easily replaceable vendor?
- Does the company own proprietary IP?
- Is the technology difficult to manufacture at scale?

Classify the moat:

- Strong and defensible.
- Moderate.
- Weak.
- No meaningful moat.

### Section 7: Technical Analysis

Provide a separate technical assessment.

Include:

**Price indicators**
- Current price.
- 1-day change.
- 1-week change.
- 1-month change.
- 3-month change.
- 6-month change.
- Year-to-date performance.
- 1-year performance.
- 3-year performance.
- 5-year performance.

**Moving averages**
- 20-day SMA.
- 50-day SMA.
- 100-day SMA.
- 200-day SMA.
- EMA 20.
- EMA 50.
- EMA 200.

**Momentum indicators**
- RSI (14).
- MACD.
- MACD signal.
- MACD histogram.
- Stochastic oscillator.
- ADX.

**Volatility**
- Bollinger Bands.
- Average True Range (ATR).
- Historical volatility.
- Beta.
- Maximum drawdown.

**Volume**
- Average trading volume.
- Relative volume.
- On-balance volume.
- Volume trends.

**Technical signals**
- Golden cross / death cross.
- Overbought / oversold.
- Bullish / bearish MACD.
- Price relative to 50-day and 200-day averages.
- Support and resistance levels.

Provide an overall technical rating:
- Strong bullish.
- Bullish.
- Neutral.
- Bearish.
- Strong bearish.

Display interactive price charts with selectable timeframes:
1M, 3M, 6M, 1Y, 3Y, 5Y and MAX.

Allow users to overlay:
- SMA 50.
- SMA 200.
- EMA 20.
- Bollinger Bands.
- Volume.

Technical indicators must be calculated using historical price data rather than generated by AI.

### Section 8: Ownership, Institutional Activity and Sentiment

Include:
- Insider ownership.
- Institutional ownership.
- Largest institutional shareholders.
- Recent insider buying and selling.
- Institutional ownership changes.
- Short interest.
- Short interest as percentage of float.
- Analyst consensus.
- Number of buy/hold/sell recommendations.
- Analyst price targets.
- Recent target revisions.

Where data is unavailable, clearly mark it unavailable.

Do not interpret routine insider sales as automatically bearish.

### Section 9: Management and Corporate Governance

Assess:
- CEO track record.
- Management experience.
- Capital allocation.
- Acquisition history.
- Shareholder returns.
- Executive compensation.
- Insider ownership.
- Corporate governance.
- Management guidance versus actual delivery.

Assess whether management has created or destroyed shareholder value over time.

### Section 10: News and Catalysts

Retrieve relevant news and company announcements.

Include:
- Latest earnings results.
- Earnings guidance.
- Product launches.
- New contracts.
- Partnerships.
- Acquisitions.
- Regulatory changes.
- Industry developments.
- Management changes.
- Insider transactions.
- Major litigation or controversies.

Show:
- Headline.
- Publication date.
- Source.
- Short summary.
- Positive / negative / neutral classification.
- Potential impact on the stock.

Prioritise official company announcements, regulatory filings and reputable financial publications.

Include source links.

Avoid generating news summaries from old or unrelated information.

### Section 11: Risk Assessment

Identify and score major risks:

- Valuation risk.
- Business execution risk.
- Financial risk.
- Competitive risk.
- Technology disruption.
- Regulatory risk.
- Geopolitical risk.
- Customer concentration.
- Supply-chain dependency.
- Management risk.
- Currency risk.
- Liquidity risk.

Provide:
- Risk score from 1–10.
- Probability assessment.
- Potential financial impact.
- Mitigation factors.

Explain the three biggest reasons the stock could underperform.

### Section 12: Final Investment Recommendation

Generate a final investment rating based on all sections.

Possible ratings:

| Rating | Meaning |
|---|---|
| STRONG BUY | High-quality business, attractive valuation and strong risk-adjusted upside |
| BUY | Attractive investment with reasonable expected returns |
| HOLD | Good business but limited current upside or uncertain valuation |
| SELL | Poor risk/reward or deteriorating investment thesis |
| STRONG SELL | Significant downside risk or fundamentally broken investment thesis |

Display separate ratings:

- Business quality: 0–100.
- Financial health: 0–100.
- Competitive moat: 0–100.
- Growth potential: 0–100.
- Valuation attractiveness: 0–100.
- Technical strength: 0–100.
- Risk score: 0–100, where higher means riskier.
- Overall investment score: 0–100.

Show the weighting methodology.

Suggested default weighting:

| Dimension | Weight |
|---|---:|
| Business quality | 15% |
| Financial health | 15% |
| Competitive moat | 15% |
| Growth potential | 20% |
| Valuation attractiveness | 20% |
| Technical strength | 5% |
| Risk assessment | 10% |

The risk score should reduce the overall score, not increase it.

Allow the user to change weights in settings.

The final recommendation must explain:
1. Why to buy.
2. Why not to buy.
3. What price represents an attractive entry point.
4. What price would make the stock expensive.
5. What would invalidate the investment thesis.
6. Expected holding period.
7. Whether the stock is suitable for a moderate-risk, long-term investor.

---

## 4. Mandatory Benchmark Comparison

Every analysed company must be compared against these four permanent benchmark stocks:

- Microsoft (MSFT)
- Alphabet (GOOGL)
- Meta Platforms (META)
- Apple (AAPL)

The benchmark comparison must be one of the most prominent sections of the application.

### Comparison table

Rows represent financial metrics. Columns represent:

- Analysed stock.
- Microsoft.
- Alphabet.
- Meta.
- Apple.

Include at least:

**Company and size**
- Share price.
- Market cap.
- Enterprise value.
- Sector.
- Revenue.
- Revenue growth.
- 3-year revenue CAGR.
- 5-year revenue CAGR.

**Profitability**
- Gross margin.
- Operating margin.
- EBITDA margin.
- Net margin.
- ROE.
- ROIC.

**Growth**
- EPS growth.
- Forward EPS growth.
- Revenue growth forecast.
- Free cash flow growth.

**Valuation**
- P/E.
- Forward P/E.
- PEG.
- Price/sales.
- EV/EBITDA.
- Price/free cash flow.
- FCF yield.
- Dividend yield.

**Financial health**
- Cash.
- Total debt.
- Net cash/debt.
- Current ratio.
- Net debt/EBITDA.

**Stock performance**
- 1-month return.
- 6-month return.
- YTD return.
- 1-year return.
- 3-year return.
- 5-year return.
- Beta.
- Maximum drawdown.

**Investment quality**
- Business quality score.
- Financial health score.
- Moat score.
- Growth score.
- Valuation score.
- Overall investment rating.
- Estimated upside.

### Comparison functionality

- Highlight the best company for each metric.
- Use green for favourable values and red for unfavourable values.
- Do not automatically assume that the highest value is best. For example, a lower P/E can be attractive, while a higher margin is generally favourable.
- Include explanatory tooltips.
- Allow sorting by any metric.
- Allow filtering between financial, valuation, growth and technical metrics.
- Allow exporting the comparison to CSV or Excel.

Important: Comparisons must use consistent fiscal periods and reporting currencies wherever possible. Show the reporting currency and period beside each figure. Clearly flag when accounting standards or fiscal-year differences make a comparison imperfect.

Also explain that these four companies are cross-sector benchmarks, not necessarily direct competitors. Include industry-specific peer comparisons separately.

---

## 5. Industry-Specific Peer Comparison

In addition to the four permanent benchmarks, automatically identify 5–10 relevant competitors or comparable companies.

Examples:

- Robotics: Teradyne, Symbotic, Ouster, Schaeffler, Harmonic Drive.
- Semiconductors: NVIDIA, AMD, Broadcom, TSMC, ASML.
- Software: Microsoft, Salesforce, Adobe, ServiceNow.
- E-commerce: Amazon, Alibaba, Shopify.
- Payments: Visa, Mastercard, PayPal, Adyen.

The system should choose relevant peers based on industry, products, business model and revenue composition.

Do not use the same peer list for every company.

Allow users to manually add or remove peer companies.

---

## 6. AI Research and Analysis Engine

Use AI to interpret financial information, identify patterns and produce understandable investment conclusions.

The AI must not invent financial figures, financial statements, contracts, analyst targets or news.

### Research workflow

1. Resolve the ticker and exchange.
2. Retrieve the latest available market data.
3. Retrieve historical price information.
4. Retrieve historical financial statements.
5. Retrieve quarterly earnings and guidance.
6. Retrieve analyst estimates and institutional information where available.
7. Retrieve official company filings and announcements.
8. Retrieve relevant industry and competitor information.
9. Calculate financial ratios and technical indicators programmatically.
10. Perform valuation calculations.
11. Compare against benchmarks and relevant peers.
12. Generate the research report using the verified data.

### Source hierarchy

Prioritise:

1. Company annual reports and quarterly filings.
2. SEC EDGAR and equivalent national regulatory filings.
3. Company investor relations pages.
4. Official exchange data.
5. Established financial data providers.
6. Reputable financial publications.
7. Analyst estimates from licensed providers.

Use source citations throughout the report.

Every material financial figure should be traceable to its source and reporting period.

### AI behaviour

The AI should act like a sceptical equity research analyst.

It should:
- Challenge optimistic management guidance.
- Distinguish revenue growth from profitable growth.
- Identify unsustainable margins.
- Identify aggressive accounting or cash-flow weaknesses.
- Challenge overly optimistic valuation assumptions.
- Identify competitive threats.
- Explain when evidence is insufficient.
- Distinguish reported facts, estimates and AI-generated interpretations.

The AI should not produce a BUY rating simply because the company operates in a fast-growing industry.

---

## 7. Data Architecture and External APIs

Build the application using a modular data-provider architecture.

The application should not depend on a single hardcoded data provider.

Potential data providers to evaluate:

**Market and fundamental data**
- Financial Modeling Prep (FMP).
- Finnhub.
- Alpha Vantage.
- EODHD.
- Twelve Data.
- Polygon.io / Massive.
- Yahoo Finance as a fallback where permitted by its terms.

**Company filings**
- SEC EDGAR.
- Company investor relations.
- Relevant European and Indian regulatory/exchange filings.

**News**
- Finnhub News.
- Financial Modeling Prep News.
- Company investor relations announcements.
- Reputable news sources.

**AI analysis**
- OpenAI API.
- Use a model appropriate for detailed reasoning and financial analysis.
- Keep the model configurable.

Before implementation, compare API providers on:
- Coverage of US, European, Indian and Japanese stocks.
- Historical financial statement coverage.
- Analyst estimates.
- Real-time versus delayed data.
- API rate limits.
- Pricing.
- Commercial usage rights.
- Reliability.

Choose one primary data provider and one fallback provider.

Do not scrape websites in ways that violate terms of service.

### Data integrity requirements

Every data point should include:
- Value.
- Currency.
- Reporting period.
- Source.
- Retrieval timestamp.
- Whether reported, estimated or calculated.

Never silently substitute missing data with zero.

Display "N/A" where data is unavailable.

Clearly distinguish:
- Real-time market price.
- Delayed market price.
- Last closing price.
- Financial reporting data.
- Analyst estimates.

---

## 8. UI / UX Design

Build a premium financial dashboard with a clean, professional institutional research aesthetic.

Reference the design quality of:
- Koyfin.
- TradingView.
- Simply Wall St.
- Bloomberg Terminal (modernised, not cluttered).

### Design guidelines

- Responsive desktop-first web application.
- Clean typography.
- Professional neutral background.
- Dark and light mode.
- Green for positive indicators.
- Red for negative indicators.
- Amber for caution.
- Interactive charts.
- Expandable financial tables.
- Clear data hierarchy.
- Tooltips for financial terms.
- Avoid unnecessary visual clutter.

### Suggested navigation

1. Dashboard
2. Stock Analysis
3. Stock Comparison
4. Valuation
5. Technical Analysis
6. Industry & Peers
7. Watchlist
8. Saved Reports
9. Settings

### Dashboard visualisations

Use charts for:
- Historical share price.
- Revenue and earnings growth.
- Margin evolution.
- Free cash flow.
- Valuation multiples.
- Peer comparisons.
- Bull/base/bear projections.
- Portfolio/watchlist performance.

---

## 9. Watchlist and Portfolio Features

Implement a watchlist where users can save stocks for further research.

Each watchlist item should show:
- Ticker.
- Company name.
- Current price.
- Daily percentage change.
- Overall rating.
- Fair value.
- Estimated upside.
- Last analysed date.

Allow users to:
- Add/remove stocks.
- Sort by valuation, growth, market cap and rating.
- Compare selected stocks.
- Re-run analysis.
- Track changes in recommendations.

Optional future feature: portfolio tracking with purchase price, number of shares, current value, unrealised gains/losses and allocation by sector/country.

---

## 10. Export and Reporting

Allow users to export:

- Full company research report as PDF.
- Financial comparison as Excel.
- Financial metrics as CSV.
- Investment thesis and valuation assumptions.
- Bull/base/bear scenarios.

PDF report should include:
- Company overview.
- Investment summary.
- Financial analysis.
- Valuation.
- Growth prospects.
- Risk assessment.
- Benchmark comparison.
- Final investment recommendation.
- Sources and retrieval timestamps.

---

## 11. Technical Architecture

Preferred architecture:

**Frontend**
- Next.js / React.
- TypeScript.
- Tailwind CSS.
- shadcn/ui.
- Recharts or equivalent charting library.

**Backend**
- Python FastAPI or Next.js API routes.
- Modular financial data service.
- AI analysis orchestration service.
- Financial calculation engine.

**Database**
- PostgreSQL / Supabase.
- Store users, watchlists, analysis history, valuation assumptions and cached market data.

**Authentication**
- Supabase Auth.
- Email/password or supported OAuth.

**Deployment**
- Vercel for frontend.
- Supabase for database and authentication.
- Backend deployment on an appropriate managed service.

### Suggested data model

Users:
- id
- email
- created_at

Companies:
- id
- ticker
- exchange
- company_name
- sector
- industry
- country
- currency

Stock_prices:
- company_id
- date
- open
- high
- low
- close
- adjusted_close
- volume

Financial_statements:
- company_id
- reporting_period
- statement_type
- financial_metrics
- currency
- source

Analysis_reports:
- id
- user_id
- company_id
- analysis_date
- market_data_timestamp
- overall_rating
- overall_score
- fair_value
- upside_percentage
- analysis_content
- source_references

Valuation_assumptions:
- report_id
- scenario
- revenue_growth
- margin_assumptions
- discount_rate
- terminal_growth
- fair_value

Watchlists:
- id
- user_id
- name

Watchlist_items:
- watchlist_id
- company_id
- added_at

---

## 12. Important Calculation and Quality Requirements

All quantitative financial analysis must be calculated in code, not invented by the AI model.

Examples:

Revenue CAGR:

CAGR = (Ending Revenue / Beginning Revenue) ^ (1 / Number of Years) - 1

Free Cash Flow:

FCF = Operating Cash Flow - Capital Expenditure

Enterprise Value:

EV = Market Capitalisation + Total Debt - Cash and Cash Equivalents

FCF Yield:

FCF Yield = Free Cash Flow / Market Capitalisation

Margin of Safety:

MOS = (Intrinsic Value - Current Price) / Intrinsic Value

Annualised Return:

CAGR = (Ending Value / Beginning Value) ^ (1 / Number of Years) - 1

Use consistent accounting definitions and document any differences.

For negative earnings or cash flow:
- Do not calculate misleading P/E or yield values.
- Display N/M (not meaningful).
- Explain why the metric cannot be meaningfully compared.

Technical indicators should be computed from historical adjusted price data where appropriate.

The AI should consume structured calculation outputs and interpret them, rather than independently calculating critical figures from text.

---

## 13. Security, Reliability and Compliance

- Store all API keys as secure environment variables.
- Never expose API keys in frontend code.
- Implement API rate limiting.
- Cache expensive financial data.
- Handle provider failures gracefully.
- Log errors.
- Validate all ticker inputs.
- Protect user data.
- Use authorised data sources and respect redistribution and display licences.
- Include clear investment research and risk disclosures.
- Do not execute trades or provide brokerage functionality.

The application is an analytical research tool, not an automated trading system.

---

## 14. MVP Development Priorities

Build in phases. Do not attempt to implement every advanced feature before the core analysis works.

### Phase 1 – Core working application

- Stock ticker search.
- Company identification and exchange selection.
- Market price and historical data.
- Historical financial statements.
- Financial ratios.
- Technical indicators.
- Company overview.
- AI-generated investment analysis.
- BUY / HOLD / SELL recommendation.
- Microsoft, Google, Meta and Apple comparison table.
- Sources and timestamps.

### Phase 2 – Advanced investment analysis

- DCF valuation.
- Comparable valuation.
- Bear/base/bull scenarios.
- Multibagger analysis.
- Industry peer comparison.
- Moat and competitive analysis.
- Ownership and analyst sentiment.
- News and catalysts.
- Risk scoring.

### Phase 3 – Investor workspace

- Watchlists.
- Saved reports.
- Historical rating tracking.
- PDF and Excel exports.
- Portfolio tracking.
- Custom comparison groups.
- Configurable scoring weights.

---

## 15. Acceptance Criteria

The application is considered functional when:

1. A user can enter a valid stock ticker from a supported US, European, Indian or Japanese exchange.
2. The system correctly identifies the company and trading currency.
3. It retrieves actual financial and market data.
4. It generates at least five years of historical financial analysis when available.
5. It calculates the main financial ratios and technical indicators.
6. It generates a transparent BUY/HOLD/SELL rating.
7. It calculates and displays bear/base/bull valuation scenarios.
8. It evaluates multibagger potential using explicit financial assumptions.
9. It compares the stock against MSFT, GOOGL, META and AAPL.
10. It identifies relevant industry peers.
11. It provides traceable sources for material claims and financial data.
12. It displays timestamps and flags missing or stale data.
13. It does not fabricate unavailable financial figures.
14. It works on desktop and mobile.
15. It allows users to save and revisit analyses.

---

## 16. Final Product Principle

The application must not be another generic AI stock-picking tool that produces attractive-looking reports with unsupported claims.

It must combine:

**Verified financial data + programmatic financial calculations + valuation models + technical analysis + AI-driven qualitative research.**

The ultimate goal is to answer five investment questions:

1. Is this a good company?
2. Does it have a durable competitive advantage?
3. Is the stock attractively valued today?
4. What is the realistic 5–10-year return potential, including multibagger scenarios?
5. Is this a better investment than Microsoft, Google, Meta or Apple at their respective current valuations?

Prioritise analytical accuracy, transparency, data provenance and decision usefulness over visual effects or unnecessary features.