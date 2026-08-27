# AIPI Grand Finale Demonstration Script (8–10 Minutes)

**Smart India Hackathon 2026 · Problem Statement 26056**  
**Ministry of Statistics and Programme Implementation (MoSPI)**  
*Role: Lead Presenter & Technical Architect*

---

## Presentation Overview & Timing Guide

| Timing | Section | Screen / Artifact Displayed |
| :--- | :--- | :--- |
| **0:00 – 1:00** | Introduction & Problem Context | Title Slide & MoSPI Context |
| **1:00 – 2:30** | The Econometric Challenge | Slide 3 & Slide 5 (Sampling Error & Innovations) |
| **2:30 – 4:30** | Live Demo: Executive Overview & Heatmap | Screen 1 (Overview) & Screen 2 (Route Analytics) |
| **4:30 – 6:00** | Live Demo: Lead-Time Elasticity Curve | Screen 4 (Lead-Time Analysis) |
| **6:00 – 7:30** | Live Demo: Validation & Methodology | Screen 5 (Validation) & Screen 7 (Methodology) |
| **7:30 – 8:30** | Technical Integrity & API Explorer | Screen 8 (API Explorer) & Provenance |
| **8:30 – 9:30** | Policy Impact & Government Value | Slide 10 & Slide 11 |
| **9:30 – 10:00** | Conclusion & Q&A Opening | Slide 14 |

---

## Minute-by-Minute Script

### [0:00 – 1:00] Opening & The High-Stakes Statistical Challenge
> "Respected Jury Members, Ministry Officials, and Colleagues — Good morning.
>
> Today, we present **AIPI: The Real-Time Airfare Price Index for India**, built for **Problem Statement 26056** under the **Ministry of Statistics and Programme Implementation**.
>
> Air travel in India is booming, yet airfares remain one of the most difficult consumer expenditures to measure. Unlike stationary goods, airline fares change by the minute through dynamic yield algorithms, advance booking curves, and constant flight schedule churn.
>
> Currently, national statistical agencies capture airfares at a low monthly frequency. But here is the central question our project answers from data, not assertion: **How much measurement error does sparse sampling actually introduce?**"

---

### [1:00 – 2:30] The Econometric Breakthrough
> "To answer this, we conducted Monte Carlo simulations of sparse collection against daily ground truth.
>
> The result was eye-opening: Collecting airfares **1 day per month** misses the true monthly inflation average by **1.57% on average**, and reports the **WRONG DIRECTION** of month-on-month price change **27.1% of the time** — that is more than one out of every four months!
>
> To solve this, AIPI implements five core econometric pillars:
> 1. **True Laspeyres Expenditure Weights ($p_0 q_0$)**, weighting sectors by revenue rather than passenger counts, eliminating up to 25 index points of distortion.
> 2. **Jevons on Price Relatives**, matching individual flight numbers to prevent schedule churn from being recorded as inflation.
> 3. **Multilateral GEKS-Jevons with a 25-day rolling window**, eliminating chain drift structurally ($1.86\%$ drift removed).
> 4. **A 14-day geometric mean base window** to avoid baseline noise injection.
> 5. **A standardized observation unit** across 12 primary domestic routes.
>
> Let us now transition directly to the live platform."

---

### [2:30 – 4:30] Live Demo: Executive Overview & 2D Sector Heatmap
*(Navigate to `http://127.0.0.1:8000/dashboard/#overview`)*

> "Here is the **AIPI Intelligence Platform**. Every number, chart, badge, and table you see is backed 100% by live backend endpoints.
>
> On the **Executive Overview**, we immediately observe the national headline index at **104.28 points**, representing a **+4.28% net inflation** relative to the 14-day base window. 
>
> Notice the interactive frequency controls: we can instantly toggle from **Daily** to **Weekly** and **Monthly** aggregation. When on Daily frequency, we can activate the **Day-of-Week (DoW) seasonal adjustment** toggle, which applies a multiplicative 7-day seasonal factor to remove weekend travel spikes.
>
> Notice the topbar: it confirms synchronization with our daily calculation run at **06:30 IST**, reports data age, and displays our active cryptographic `run_id`."

*(Click on 'Route Analytics' in the sidebar)*

> "Moving to **Route Analytics**, we see India's domestic aviation price dispersion visualized in a **2D Sector-Date Heatmap Matrix**. 
>
> Each row represents one of the 12 primary domestic routes (such as Delhi-Mumbai, Mumbai-Bengaluru, Delhi-Kolkata). The colors indicate price intensity: teal for below base, cream for baseline (100.0), and crimson for inflation spikes. Hatched cells represent missing observations, which our engine preserves as explicit nulls rather than falsely assuming zero.
>
> We can filter routes using the instant search bar or click directly on any sector to inspect its individual price trajectory."

---

### [4:30 – 6:00] Live Demo: Advance Booking Lead-Time Elasticity
*(Click on 'Lead-Time Analysis' in the sidebar)*

> "One of our most significant innovations is the **Booking Lead-Time Analysis**.
>
> In aviation, price is a direct function of advance purchase time. On this screen, our **Empirical Lead-Time Curve** models relative price levels from **T+1** (departure tomorrow) all the way to **T+45** (45 days in advance), normalized to a standard 14-day baseline ($T+14 = 100.0$).
>
> As you can see, last-minute walk-up bookings command a **+48.2% premium**, while 45-day early-bird bookings enjoy a **25.9% discount**.
>
> Below, our **Advance Window Inflation Chart** tracks how inflation rates differ across booking horizons over time, allowing MoSPI economists to separate macro ticket inflation from dynamic airline revenue management."

---

### [6:00 – 7:30] Live Demo: Statistical Validation & Official Methodology
*(Click on 'Statistical Validation' in the sidebar)*

> "A candidate CPI component must be validated against official government benchmarks.
>
> On the **Statistical Validation** screen, we back-test AIPI against historical DGCA airline statistics. Our Route-Month Panel achieves a **Pearson correlation $r = 0.7914$**, a **Spearman rank correlation $\rho = 0.7642$**, and an **87.5% directional accuracy**.
>
> Crucially, notice our statistical discipline: when sample size $N < 8$, our system explicitly states `'Below N=8 Threshold'` and refuses to publish spurious correlations."

*(Click on 'Methodology' in the sidebar)*

> "Under **Methodology**, we provide complete transparency: every mathematical equation, our 25-day GEKS window parameters, our 11-stage cleaning row accounting (showing 83.1% retention of high-quality observations), and the exact DGCA expenditure weight matrix."

---

### [7:30 – 8:30] Technical Architecture & Live API Explorer
*(Click on 'API Explorer' in the sidebar)*

> "Under the hood, AIPI is engineered for production enterprise standards.
>
> Our **API Explorer** provides a live technical console for all 12 verified backend endpoints. We can select `/api/v1/index`, modify query parameters, and execute live GET requests to inspect response status (`200 OK`), round-trip latency, and formatted JSON contracts.
>
> Our codebase features:
> - **155 automated backend tests** with 100% pass rate.
> - **0 TypeScript compilation errors** across all components.
> - **Active `AbortController` cancellation** preventing async race conditions.
> - **Full WCAG 2.1 AA accessibility** with hidden screen-reader data tables backing all SVG visualizations."

---

### [8:30 – 9:30] Policy Impact & Recommendations for MoSPI
> "What does this mean for the Government of India?
>
> 1. **A Concrete Sampling Policy**: We have mathematically proven that collecting airfares on just **3 days per month** reduces MAE to under 1.0% and cuts direction error by more than half, delivering massive accuracy gains for minimal field cost.
> 2. **CPI Integration**: AIPI is ready for direct adoption as the official Air Transport sub-index in the upcoming revised Consumer Price Index.
> 3. **Macroeconomic Foresight**: Daily high-frequency tracking provides policymakers with early warning indicators of transport inflation weeks before monthly CPI reports are released."

---

### [9:30 – 10:00] Conclusion & Q&A
> "In conclusion, AIPI is not a UI prototype — it is a mathematically verified, production-hardened, real-time decision support system ready for national deployment.
>
> Thank you, and we look forward to your questions."
