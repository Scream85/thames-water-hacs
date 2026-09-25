# From "WTF?!" to Data-Driven Insights: How My AI Agent Helped Me Understand My Water Bill

*How a shocking £1,125 water bill led me to build a personal water monitoring system - and discover my gardener was the culprit*

---

## The Letter That Started It All

In late November 2025, I received a letter from Thames Water that made me do a double-take. My new payment plan: **£173 per month**. Total amount due: **£1,125.49**.

But what really caught my attention was the usage graph showing my daily water consumption had jumped from 514 litres to **872 litres per day** - a 70% increase. My immediate reaction, scrawled across the bill in red marker: "WTF?!"

The bill helpfully suggested I check for "a leaky loo or dripping tap." Thanks, Thames Water.

## Down the Rabbit Hole: Understanding the Numbers

Rather than panic or ignore it, I decided to investigate. This is where having a personal AI agent becomes invaluable - not for the simple tasks, but for the complex, multi-step research projects that would otherwise take hours.

### The Ofwat Price Increase

My first question: was this just about my usage, or had prices changed? A quick investigation revealed that Ofwat had approved a **40.7% price increase** effective April 2025. Thames Water's rates had jumped to:

- Fresh water: £2.4743 per cubic metre
- Wastewater: £1.5480 per cubic metre
- Combined: **£4.02 per cubic metre** (or about £0.40 per 100 litres)
- Plus daily fixed charges of £0.53

So yes, prices had increased significantly. But that didn't explain the 70% jump in my *consumption*.

### The Smart Meter Discovery

Here's where it got interesting. Looking at my bill more carefully, I noticed something I'd overlooked for years: **"Your tariff: Metered - Smart"**.

I had a smart meter installed. Thames Water had been reading it automatically. And crucially, they had a web portal where I could see my **daily and hourly** water usage data.

This changed everything. I wasn't limited to a six-monthly bill summary - I could potentially access granular data going back months.

## Finding Inspiration: Standing on the Shoulders of Giants

Before building anything, I did what any good engineer does: I searched for prior art. My AI agent found several people who had tackled similar problems, including someone who had built a simple scraper to extract their Thames Water data.

Their approach was straightforward:
- Use Selenium to automate browser login
- Navigate to the usage page
- Extract the data from the charts

This gave me a starting point. But I wanted to go further.

## The Vision: A Personal Water Monitoring Service

I already had a pattern I'd used successfully before: a Raspberry Pi 5 running as a home server, hosting various personal services. Why not add water monitoring to the mix?

My requirements evolved:
1. **Automated daily data collection** - no manual intervention needed
2. **REST API** - so I could query data programmatically
3. **Visual dashboard** - to see trends at a glance
4. **Spike alerts** - email me if usage exceeds a threshold
5. **Cost tracking** - real-time cost estimates based on actual rates
6. **Data verification** - ensure the data quality is reliable

## Building the Thames Water Monitoring Service

### The Tech Stack

- **FastAPI** for the REST API
- **Selenium** with headless Chrome for web scraping
- **SQLite** for data storage (simple, no external dependencies)
- **APScheduler** for automated daily collection
- **Chart.js** for the dashboard visualisations
- **Docker** for deployment on my Raspberry Pi 5

### The Scraper Challenge

Thames Water's website isn't designed for automation. The scraper needed to:

1. Log in with credentials
2. Navigate through JavaScript-heavy pages
3. Select specific date ranges from dropdown menus
4. Capture data from network responses (the actual API calls the page makes)
5. Handle the quirky DD-MM-YYYY date format

One particular challenge: Thames Water uses different dropdown selections for different views:
- "Monthly (by days)" + "Last 30 days" for daily data
- "Daily (by hours)" + specific date for hourly breakdowns

Getting this reliable took several iterations, but eventually I had a scraper that could extract both daily and hourly usage data, including the actual meter readings.

### The Dashboard

I wanted something I could glance at and immediately understand. The dashboard includes:

**Usage Cards:**
- Latest day's usage (note: there's always a ~3 day delay from Thames Water)
- 7-day rolling average
- Month-to-date total
- Active alerts count

**Cost Cards (in green, because money):**
- Average daily cost
- Month-to-date cost
- Projected monthly cost
- Annual estimate

**Interactive Charts:**
- Daily usage bar chart (30/90/365 day views) with an 800L threshold line
- Hourly breakdown for any selected date
- Monthly comparison with averages

The dashboard is accessible at `water.gavinslater.co.uk` - a real URL, running on my home server.

### Data Quality: The Meter Reading Discovery

As I collected more data, I noticed discrepancies. The sum of hourly readings didn't always match the daily totals. Was this a bug in my code?

Investigation revealed something fascinating about Thames Water's data: they allocate "overnight" usage inconsistently between days. The hourly reading at midnight might include usage from the previous evening.

The solution? Capture the actual **meter readings** along with usage figures. The cumulative meter reading is authoritative - it's the physical counter on the meter. By comparing meter reading changes, I could verify data accuracy regardless of how Thames Water allocated the usage between time periods.

This led to an enhanced weekly verification job that:
1. Compares daily reported usage with actual meter reading changes
2. Calculates overnight gaps between days
3. Flags genuine anomalies vs. expected allocation differences

## The Revelation: Finding the Gardener Pattern

With weeks of hourly data now available, I could finally investigate my 70% usage increase. The analysis was revealing:

**Pattern 1: Bi-weekly spikes**
Certain days showed dramatically higher usage - often 800-1000+ litres. These weren't random. They occurred every two weeks, like clockwork.

**Pattern 2: Daytime concentration**
On spike days, the extra usage clustered between 10am and 4pm. Not overnight (ruling out leaks), not early morning (ruling out household showers).

**The culprit: The gardener.**

We have a gardener who comes every fortnight to maintain our garden. They use a significant amount of water for:
- Watering plants and flower beds
- Cleaning patios and pathways
- General garden maintenance

Mystery solved. The 70% increase wasn't a leak or faulty meter - it was legitimate garden watering that we'd authorised but hadn't realised was so water-intensive.

## What I Learned

### 1. Personal AI Agents Excel at Multi-Step Research

This project involved:
- Parsing a PDF bill
- Researching regulatory pricing decisions
- Exploring web scraping approaches
- Analysing data patterns
- Building and deploying a service

No single step was particularly hard, but orchestrating them all? That's where having an AI agent that remembers context and can reason across domains becomes genuinely useful.

### 2. Your Data is Valuable - If You Can Access It

Thames Water has been collecting my hourly water usage for years. But until I built a tool to extract it, that data was effectively locked away, visible only through their clunky web interface.

The same is true for many services: your bank, your energy provider, your health apps. The data exists. The challenge is liberating it.

### 3. Home Servers are Underrated

My Raspberry Pi 5 now runs:
- Water monitoring service
- Health data aggregation
- Location tracking
- Various other personal automations

Total cost: ~£80 for the Pi, plus electricity (minimal). It's always on, always available, and completely under my control.

### 4. The Bill Was Actually Correct

After all this investigation, was Thames Water overcharging me? No. The meter readings were accurate. The rates matched Ofwat's approved tariffs. The 70% usage increase was real - and explained by garden watering we'd authorised.

Sometimes the answer isn't fraud or error. Sometimes it's just... you're using more water than you realised.

## The Ongoing Value

The water monitoring service continues to run, collecting data daily at 6am. I can now:

- **Track costs in real-time** rather than waiting for six-monthly bills
- **Get alerts** if daily usage exceeds 800L (my chosen threshold)
- **See patterns** like the gardener's bi-weekly visits
- **Verify data quality** using meter reading comparisons
- **Make informed decisions** about water usage

Was it overkill? Perhaps. But it's also a genuine example of how personal AI infrastructure can transform a frustrating experience ("WTF?! £1,125?!") into an educational project with lasting value.

---

*The Thames Water Monitoring Service is running at [water.gavinslater.co.uk](https://water.gavinslater.co.uk). The code captures daily and hourly usage data, calculates costs based on December 2025 Thames Water rates, and sends email alerts for unusual usage patterns.*

*Built with FastAPI, Selenium, Chart.js, and deployed on a Raspberry Pi 5 home server.*
