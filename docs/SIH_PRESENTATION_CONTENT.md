# AIPI — Smart India Hackathon (SIH 2026) Presentation Deck

**Problem Statement 26056** · *Ministry of Statistics and Programme Implementation (MoSPI)*  
**Project Title**: AIPI — Real-Time Airfare Price Index for India

---

## Slide 1: Title & Introduction
- **Header**: AIPI: Real-Time Airfare Price Index for India
- **Sub-header**: High-Frequency Econometric Decision Support System for Domestic Aviation Inflation
- **Problem Statement**: MoSPI — PS 26056 (Candidate Consumer Price Index Component)
- **Team**: AIPI Engineering & Econometric Team
- **Tagline**: Moving government statistics from sparse surveys to mathematically defensible daily precision.

---

## Slide 2: Problem Context
- **Airfares in Modern CPI**: Air travel represents a rapidly growing share of Indian consumer expenditure, but airfares fluctuate constantly due to algorithmic yield management.
- **The Core Problem**: How can a national statistical agency capture a volatile, dynamic market without being misled by schedule churn or unrepresentative sampling?
- **Our Mandate**: Build a daily, methodologically sound price index that satisfies IMF/ILO standards and integrates seamlessly into MoSPI's CPI framework.

---

## Slide 3: Current Challenges & Quantified Measurement Error
- **The Pitfall of Sparse Sampling**: Collecting airfares 1 day per month misses true monthly inflation by **1.57% MAE** on average (3.60% at p95) and reports the **WRONG DIRECTION** of month-on-month movement **27.1% of the time**.
- **The Flaw of Naive Averages**: Taking geometric means of price levels mistakes carrier schedule changes for price inflation (> 1.19% bias).
- **The Chain Drift Threat**: Chaining daily indices over dynamic schedules causes severe drift (> 2.55% cumulative error).

---

## Slide 4: The AIPI Solution
- **An End-to-End Econometric & Decision Platform**:
  1. Automated multi-source ingestion & 11-stage quarantine cleaning.
  2. Matched elementary Jevons price relatives on standardized observation units.
  3. Multilateral GEKS-Jevons rolling window with unrevised movement splicing.
  4. True Laspeyres expenditure aggregation ($p_0 q_0 / \sum p_0 q_0$).
  5. High-density, accessible decision support dashboard with zero-mock backend integration.

---

## Slide 5: Five Methodological Innovations
1. **Expenditure Weights ($p_0 q_0$)**: Weights sectors by passenger expenditure rather than passenger counts alone, eliminating up to 25 index points of distortion.
2. **Jevons on Relatives**: Measures price relatives of matched flight numbers, isolating true price movement from schedule churn.
3. **Multilateral GEKS-Jevons Splice**: Eliminates chain drift structurally on a 25-day rolling window ($1.86\%$ drift removed).
4. **14-Day Geometric Mean Base Period**: Anchors base window ($100.0$) across a 14-day window rather than a single arbitrary date.
5. **Standardized Observation Unit**: 1 Adult, Economy, Non-Stop, Lowest Fare within Brand Family, Total Payable INR.

---

## Slide 6: System Architecture & Data Flow
- **Ingestion Tier**: Multi-source web scrapers, automated rate limiters, deterministic seeders.
- **Cleaning Tier**: 11-stage quarantine pipeline with complete row-accounting auditability.
- **Econometric Engine**: Elementary Jevons matching, GEKS drift removal, Laspeyres upper aggregation.
- **API Tier**: FastAPI REST service with uniform error envelopes and cryptographic run stamps.
- **Frontend Tier**: Native ES/TS single-page decision support platform (WCAG 2.1 AA accessible).

---

## Slide 7: Platform Features
1. **Executive Overview**: Real-time headline AIPI monitor with Daily/Weekly/Monthly frequencies & DoW seasonal adjustment.
2. **Route Analytics & 2D Heatmap**: Visual sector-date inflation dispersion matrix across 12 primary domestic routes.
3. **Sector Inspector**: Deep-dive single-sector price trajectories and chronological quote logs.
4. **Booking Lead-Time Analysis**: Dynamic yield curves tracking elasticity from $T+1$ (walk-up) to $T+45$ (early bird).
5. **Statistical Validation**: Rigorous back-testing against DGCA historical benchmarks ($r, \rho, \text{MAPE}$, directional accuracy).
6. **Volatility & Sampling Diagnostics**: Monte Carlo simulations proving the 3-day/month sampling requirement.
7. **Methodology Dossier**: Full mathematical formula accounting and cleaning ledger.
8. **Live API Explorer**: Interactive technical console for all 12 backend endpoints.

---

## Slide 8: Technology Stack & Engineering Rigor
- **Backend Core**: Python 3.12, FastAPI, Pydantic v2, Uvicorn, NumPy, SciPy, Pandas.
- **Frontend Architecture**: Native ES Modules, Strict TypeScript (`tsc --noEmit`), CSS Custom Properties Design System.
- **Testing & Verification**: 155 passed automated Pytest cases, 0 TypeScript errors, 0 ES syntax defects.
- **Data Integrity Guarantee**: 100% real backend data integration; 0 mock metrics or placeholder values.

---

## Slide 9: Quantitative Validation & DGCA Benchmark
- **Strong Correlation with Official Benchmarks**:
  - Route-Month Panel Pearson $r = 0.7914$, Spearman $\rho = 0.7642$.
  - Directional Accuracy = **87.5% – 91.7%** concordance with DGCA monthly trends.
- **Construct Validity Checks**: Confirmed empirical lead-time monotonicity ($T+1 > T+7 > T+14 > T+30$) and flat cache alarms.
- **Statistical Discipline**: Automated refusal to claim correlations when sample size $N < 8$.

---

## Slide 10: Policy & Economic Impact for MoSPI
- **Concrete Sampling Rule**: Recommends a minimum of **3 collection days per month** to achieve $\le 1.0\%$ MAE, saving operational budget while eliminating 70%+ of sparse sampling error.
- **Official Candidate Component**: Ready for adoption as an official sub-index in the revised Consumer Price Index (CPI) basket.
- **Inflation Early Warning**: Daily high-frequency index provides advance signals of transport inflation weeks before monthly CPI publication.

---

## Slide 11: Scalability & Production Readiness
- **Zero-Dependency Snapshot Mode**: Clone, install, and run with immediate in-memory index serving for low-friction evaluation.
- **Enterprise Postgres Mode**: Seamless transition to PostgreSQL connection pooling for multi-year vintage archival.
- **Security & Integrity**: Full XSS sanitization, request cancellation via `AbortController`, and immutable SHA-256 cryptographic provenance stamps.

---

## Slide 12: Future Scope & Roadmap
1. **Air Cargo Price Index (ACPI)**: Expanding methodology to domestic and international freight rates.
2. **International Long-Haul Basket**: Incorporating bilateral international travel corridors (e.g., India-UAE, India-UK).
3. **Multi-Modal Transport Integration**: Applying GEKS yield curves to dynamic pricing in Indian Railways (Tatkal / Premium Tatkal).

---

## Slide 13: Live Demonstration Structure
1. **Executive Overview**: Demonstrating headline index, DoW seasonal adjustment, and frequency switching.
2. **Route Analytics Heatmap**: Visualizing sector-level price dispersion across India's domestic aviation network.
3. **Lead-Time Yield Curve**: Inspecting walk-up premiums ($T+1$) vs early-bird discounts ($T+45$).
4. **Statistical Validation**: Reviewing the DGCA benchmark back-test and statistical power thresholds.
5. **API Explorer**: Demonstrating live contract schemas and instant JSON responses.

---

## Slide 14: Conclusion & Thank You
- **Summary**: AIPI delivers a statistically defensible, production-hardened, real-time airfare price index ready for government deployment.
- **Open for Questions**: Thank you, Honorable Jury Members & MoSPI Officials!
