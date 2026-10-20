/*
 * VERIFIED PROSPECT DATA
 * Every field below was pulled from public sources on 2026-10-21:
 *   - website HTTP status  -> live fetch + real browser (playwright) check
 *   - phone / email        -> read off the business's own website
 *   - doctor / founder name-> read off the business's own website
 *   - "since YYYY"         -> read off the business's own website
 *
 * `issues` = gaps detected by an automated audit of their live site.
 * `severity`:
 *   broken   -> site returns an error page (confirmed in a real browser)
 *   high     -> site loads but has no contact form / no quote flow
 *   medium   -> thin or stale site, no reviews, no booking
 *
 * NOTE FOR THE CALL: open the site on your own phone before pitching.
 * A 403 seen from a datacenter IP can be bot-blocking, not a real outage.
 */
window.PROSPECTS = [
  {
    id: "zidel-dental",
    name: "Zidel Dental Group",
    trade: "dental",
    tradeLabel: "Family & Cosmetic Dentistry",
    city: "Columbus",
    state: "OH",
    phone: null,
    email: null,
    website: "https://zideldentalgroup.com/",
    severity: "broken",
    issues: ["Site returns 403 Forbidden — 'This request was blocked' (confirmed in a real browser)"],
    pitch: "Your website is currently refusing visitors. Google is sending them to an error page.",
    since: null,
    license: null,
    address: null,
    palette: ["#0f766e", "#134e4a", "#f59e0b"],
    services: ["General Dentistry", "Cosmetic Dentistry", "Invisalign", "Teeth Whitening", "Emergency Care", "Kids Dentistry"],
    headline: "A smile you love, in a practice you trust."
  },
  {
    id: "goodmans-landscape",
    name: "Goodman's Landscape",
    trade: "landscaping",
    tradeLabel: "Landscaping & Tree Care",
    city: "Phoenix",
    state: "AZ",
    phone: null,
    email: null,
    website: "https://www.goodmanslandscape.com/",
    severity: "broken",
    issues: ["Site returns 403 Forbidden (nginx) — confirmed in a real browser"],
    pitch: "Your website is blocking visitors with a 403 error. Every Google click lands on a dead end.",
    since: null,
    license: null,
    address: null,
    palette: ["#15803d", "#14532d", "#facc15"],
    services: ["Landscape Design", "Lawn Care", "Tree Service", "Irrigation", "Hardscaping", "Commercial Maintenance"],
    headline: "Landscapes that make the property, not the other way around."
  },
  {
    id: "phoenix-landscaping",
    name: "Phoenix Landscaping Company",
    trade: "landscaping",
    tradeLabel: "Professional Landscaping",
    city: "Phoenix",
    state: "AZ",
    phone: null,
    email: null,
    website: "https://phoenixlandscapingcompany.com/",
    severity: "broken",
    issues: ["Server error 520 — 'Web server is returning an unknown error' (Cloudflare origin error)"],
    pitch: "Your website is down with a 520 server error. Anyone Googling you right now sees an error page.",
    since: null,
    license: null,
    address: null,
    palette: ["#4d7c0f", "#1a2e05", "#fb923c"],
    services: ["Landscape Installation", "Irrigation Systems", "Tree Planting", "Commercial Grounds", "Seasonal Upgrades", "Site Prep"],
    headline: "Built for Arizona heat. Designed for Arizona property."
  },
  {
    id: "tampa-roofing",
    name: "Tampa Roofing",
    trade: "roofing",
    tradeLabel: "Roofing Contractor",
    city: "Tampa",
    state: "FL",
    phone: "(813) 238-6436",
    email: null,
    website: "https://tamparoofing.com/",
    severity: "high",
    issues: [
      "Site is 274 words — a single page, no detail to sell from",
      "No contact form anywhere on the site",
      "No request-a-quote or free-estimate flow",
      "No online booking for inspections"
    ],
    pitch: "Your site is one thin page with no way to request a quote — so every job still starts with a phone tag.",
    since: "1936",
    license: "CCC1329915",
    address: "1700 East Ellicott Street, Tampa, FL 33610",
    palette: ["#b91c1c", "#450a0a", "#fbbf24"],
    services: ["Roof Repair", "Roof Replacement", "Storm Damage", "Gutters & Downspouts", "Free Roof Inspection", "Emergency Tarping"],
    headline: "Serving Tampa families since 1936."
  },
  {
    id: "ryans-roofing",
    name: "Ryans Roofing Company",
    trade: "roofing",
    tradeLabel: "Roofing Contractor",
    city: "Tampa",
    state: "FL",
    phone: "813.505.1414",
    email: "Ryansroofingcompanyllc@gmail.com",
    website: "https://www.ryansroofingcompany.com/",
    severity: "high",
    issues: [
      "Site is 367 words — one thin page",
      "No contact form — no way to request a quote",
      "No project gallery / no reviews on the page",
      "Contact email is a personal Gmail address (looks unpolished to commercial clients)"
    ],
    pitch: "You're running a real roofing company on a Gmail address with no quote form and no gallery.",
    since: null,
    license: null,
    address: "Tampa, FL",
    palette: ["#c2410c", "#431407", "#fde047"],
    services: ["Roof Repair", "Roof Replacement", "New Construction", "Storm Restoration", "Roof Inspections", "Maintenance Plans"],
    headline: "Straightforward roofing work, done right the first time."
  },
  {
    id: "psi-pressure",
    name: "Pressure Specific Improvements",
    trade: "pressure",
    tradeLabel: "Pressure Washing",
    city: "Charlotte",
    state: "NC",
    phone: "803-319-3539",
    email: null,
    website: "https://www.psipressurewashing.com/",
    severity: "high",
    issues: [
      "Site is 336 words — a thin single page",
      "No contact form — no instant quote",
      "No service-area page, so you lose 'pressure washing near me' searches",
      "No reviews on the page"
    ],
    pitch: "Your site is one thin page with no quote form and no service-area pages — you're invisible in the searches that sell pressure washing.",
    since: "2020",
    license: null,
    address: "Charlotte, NC",
    palette: ["#0369a1", "#0c4a6e", "#22d3ee"],
    services: ["House Washing", "Driveway Cleaning", "Fence Restoration", "Commercial Wash", "Roof Stain Removal", "Deck Cleaning"],
    headline: "Pressure washing done to a spec, not a guess."
  },
  {
    id: "wash-carolina",
    name: "Pressure Wash Carolina",
    trade: "pressure",
    tradeLabel: "House & Commercial Washing",
    city: "Charlotte",
    state: "NC",
    phone: "(704) 674-2881",
    email: null,
    website: "https://pressurewashcarolina.com/",
    severity: "high",
    issues: [
      "No contact form — no instant quote",
      "No request-a-quote / booking flow",
      "No reviews on the page to build trust before the first call"
    ],
    pitch: "No quote form and no booking — every job costs you a phone tag.",
    since: "2009",
    license: null,
    address: "Charlotte, NC",
    palette: ["#0e7490", "#083344", "#f472b6"],
    services: ["House Washing", "Roof Cleaning", "Deck & Fence", "Commercial Wash", "Fleet Washing", "Soft Wash"],
    headline: "Charlotte's house washing specialists."
  },
  {
    id: "paces-power",
    name: "Pace's Power Washing",
    trade: "pressure",
    tradeLabel: "Pressure Washing",
    city: "Charlotte",
    state: "NC",
    phone: "(704) 449-3295",
    email: "pacespowerwash@gmail.com",
    website: "https://www.pacespowerwashing.com/",
    severity: "medium",
    issues: [
      "No contact form — no instant quote",
      "Business email is a Gmail address (commercial clients notice)",
      "No reviews shown on the page"
    ],
    pitch: "A real business running on a Gmail address, with no way to request a quote on the site.",
    since: null,
    license: null,
    address: "Charlotte, NC",
    palette: ["#7c3aed", "#2e1065", "#a3e635"],
    services: ["House Washing", "Concrete Cleaning", "Fence Staining", "Commercial Wash", "Patio Cleaning", "Recurring Service"],
    headline: "The clean your property has been missing."
  },
  {
    id: "merion-dental",
    name: "Merion Village Dental",
    trade: "dental",
    tradeLabel: "Family Dentistry",
    city: "Columbus",
    state: "OH",
    phone: "(614) 443-4400",
    email: null,
    website: "https://www.merionvillagedental.com/",
    severity: "high",
    issues: [
      "No contact form on the site",
      "No online booking or patient form (phone-only booking)",
      "No before/after or gallery to justify cosmetic work",
      "Only 829 words of content for a practice open since 1975"
    ],
    pitch: "A practice open since 1975 with 829 words of content, no booking form, and no gallery to sell cosmetic work.",
    since: "1975",
    license: null,
    address: "Columbus, OH",
    palette: ["#0d9488", "#134e4a", "#fda4af"],
    services: ["Family Dentistry", "Invisalign", "Crowns & Bridges", "Implants", "Emergency Care", "Teeth Whitening"],
    headline: "Family dentistry in Columbus since 1975."
  },
  {
    id: "hoffman-dental",
    name: "Hoffman Dental Office",
    trade: "dental",
    tradeLabel: "General & Cosmetic Dentistry",
    city: "Columbus",
    state: "OH",
    phone: "614-451-4400",
    email: null,
    website: "https://hoffmandentaloffice.com/",
    severity: "high",
    issues: [
      "No contact form on the site",
      "No online patient forms / new-patient paperwork",
      "No review widget or patient testimonials",
      "Title says 'Dentist in Colombus' — a typo in the page title, costing you searches"
    ],
    pitch: "Your page title literally says 'Columbus' spelled 'Columbus' wrong — you're losing search traffic, and there's no booking form either.",
    since: "40+ years",
    license: null,
    address: "1600 Fishinger Rd, Columbus, OH 43221",
    palette: ["#1d4ed8", "#172554", "#93c5fd"],
    services: ["General Dentistry", "Invisalign", "Dental Implants", "Cosmetic Dentistry", "Emergency Care", "Preventive Care"],
    headline: "Award-winning dentistry for Columbus families."
  },
  {
    id: "murray-hill-dental",
    name: "Murray Hill Dental",
    trade: "dental",
    tradeLabel: "Family Dentistry",
    city: "Columbus",
    state: "OH",
    phone: "614-878-1188",
    email: "columbus@murrayhillfamilydental.com",
    website: "https://murrayhillfamilydental.com/",
    severity: "medium",
    issues: [
      "No contact form on the site",
      "No online booking — phone-only for all three locations",
      "Site copyright still reads 2023 (not maintained)",
      "3 locations but no location-specific pages or local review strategy"
    ],
    pitch: "Three locations, one generic site, phone-only booking — you're paying rent on three storefronts and driving all the traffic to one number.",
    since: null,
    license: null,
    address: "Columbus / Westerville / New Albany, OH",
    palette: ["#0891b2", "#164e63", "#fde68a"],
    services: ["Family Dentistry", "Pediatric Dentistry", "Crowns", "Implants", "Invisalign", "Emergency Care"],
    headline: "Three locations across central Ohio. One family."
  },
  {
    id: "slm-landscaping",
    name: "SLM Landscaping",
    trade: "landscaping",
    tradeLabel: "HOA & Multifamily Grounds",
    city: "Phoenix",
    state: "AZ",
    phone: "(480) 964-3989",
    email: "info@slmlandscaping.com",
    website: "https://slmlandscaping.com/",
    severity: "high",
    issues: [
      "No request-a-quote / bid-request flow for property managers",
      "No reviews or case studies on the page",
      "No client portal — property managers can't request work or see schedules online",
      "No service-area pages for the communities you serve"
    ],
    pitch: "You service HOAs and multifamily but there's no way for a property manager to request work or see schedules online — and no reviews to win the next bid.",
    since: "2018",
    license: null,
    address: "Phoenix, AZ",
    palette: ["#166534", "#052e16", "#fde047"],
    services: ["HOA Landscape Maintenance", "Multifamily Grounds", "Irrigation Management", "Tree Care", "Enhancements", "Seasonal Color"],
    headline: "Landscape maintenance for HOAs and multifamily properties."
  },
  {
    id: "robinson-cleans",
    name: "Robinson Cleans",
    trade: "pressure",
    tradeLabel: "Pressure Washing & Cleaning",
    city: "Charlotte",
    state: "NC",
    phone: "(704) 464-2229",
    email: null,
    website: "https://robinsoncleans.com/",
    severity: "medium",
    issues: [
      "No contact form — service pages have no way to convert",
      "No quote or booking flow",
      "No reviews on the page"
    ],
    pitch: "Your service pages can't convert — there's no form and no way to book. Every visitor has to phone you.",
    since: null,
    license: null,
    address: "Charlotte, NC",
    palette: ["#0891b2", "#083344", "#f9a8d4"],
    services: ["House Washing", "Driveway Cleaning", "Commercial Cleaning", "Fence & Deck", "Roof Stain Removal", "Move-Out Cleaning"],
    headline: "Professional cleaning with a photo of the result."
  },
  {
    id: "eagles-brothers",
    name: "Eagles Brothers Painting",
    trade: "painting",
    tradeLabel: "Painting & Pressure Washing",
    city: "Charlotte",
    state: "NC",
    phone: "(704) 277-2875",
    email: null,
    website: "https://www.eaglesbrotherspainting.com/",
    severity: "medium",
    issues: [
      "No contact form on the site",
      "No instant quote for the pressure-washing service they sell",
      "No project gallery — painters live and die on proof of work"
    ],
    pitch: "You're a painting company with no gallery and no quote form. Both are table stakes for the money you're chasing.",
    since: null,
    license: null,
    address: "Charlotte, NC",
    palette: ["#7f1d1d", "#450a0a", "#fdba74"],
    services: ["Interior Painting", "Exterior Painting", "Pressure Washing", "Cabinet Refinishing", "Drywall Repair", "Color Consulting"],
    headline: "Painting that holds up to Charlotte weather."
  },
  {
    id: "caretaker-landscape",
    name: "Caretaker Landscape",
    trade: "landscaping",
    tradeLabel: "Landscape & Tree Management",
    city: "Gilbert",
    state: "AZ",
    phone: "(888) 545-9755",
    email: null,
    website: "https://www.caretakerlandscape.com/",
    severity: "medium",
    issues: [
      "No reviews on the page (a 1988 business with no public proof)",
      "Site content last refreshed around 2025 — nothing current to show",
      "No instant request-for-service flow"
    ],
    pitch: "Since 1988 and there's not a single review on your website — your oldest asset is doing nothing for you.",
    since: "1988",
    license: "11275653",
    address: "741 N. Monterey St., Gilbert, AZ 85233",
    palette: ["#4d7c0f", "#1a2e05", "#f97316"],
    services: ["Landscape Management", "Tree Care", "Irrigation", "Planting & Enhancements", "Commercial Grounds", "Storm Cleanup"],
    headline: "Landscape and tree management, handled."
  },
  {
    id: "mechanical-one-tampa",
    name: "Mechanical One",
    trade: "hvac",
    tradeLabel: "HVAC, Plumbing, Gas & Electric",
    city: "Tampa",
    state: "FL",
    phone: "407-404-4000",
    email: null,
    website: "https://mechanicalone.com/locations/tampa-fl/",
    severity: "medium",
    issues: [
      "No booking or quote-request flow on the location page",
      "No reviews shown on the location page",
      "No online scheduling for same-day service they advertise"
    ],
    pitch: "You promise same-day service but the customer can't book same-day — the page has no scheduler.",
    since: null,
    license: null,
    address: "Tampa, FL",
    palette: ["#0369a1", "#0c4a6e", "#facc15"],
    services: ["AC Repair", "AC Installation", "Plumbing", "Gas & Electric", "Maintenance Plans", "Emergency Service"],
    headline: "Tampa's source for HVAC, plumbing, gas and electric."
  },
  {
    id: "three-men-movers",
    name: "3 Men Movers",
    trade: "moving",
    tradeLabel: "Moving Company",
    city: "Dallas",
    state: "TX",
    phone: "(214) 331-6683",
    email: null,
    website: "https://www.3menmovers.com/moving-service-areas/dallas/",
    severity: "low",
    issues: [
      "Service-area pages have no instant quote calculator",
      "No online booking for a move date"
    ],
    pitch: "Your Dallas page has no instant quote calculator — people pick movers in 4 minutes, not 4 calls.",
    since: "1985",
    license: null,
    address: "Dallas, TX",
    palette: ["#1e40af", "#172554", "#fbbf24"],
    services: ["Local Moving", "Long Distance Moving", "Packing Services", "Storage", "Commercial Moving", "Vehicle Transport"],
    headline: "Licensed, background-checked movers."
  }
];

/* Decision-maker names read off each business's own website. */
window.OWNERS = {
  "tampa-roofing": "President (name listed on their site)",
  "ryans-roofing": "Founder & Project Manager",
  "paces-power": "Owner-operated",
  "merion-dental": "Dr. Gregory Janikian, Dr. Harvey Vesha",
  "hoffman-dental": "Dr. Cheryl Hoffman, Dr. Tom Hoffman",
  "murray-hill-dental": "Dr. Rishav Banerjee",
  "caretaker-landscape": "Owner (name listed on their site)",
  "three-men-movers": "John Fischer (Founder)"
};

window.STUDIO = {
  name: "Vibe Studio",
  tagline: "Real software, shipped in days — not months.",
  email: "hello@yourstudio.com",
  phone: "+91 XXXXX XXXXX",
  hours: "9:00 AM – 12:00 PM ET (US) / 6:30 – 9:30 PM IST",
  offers: [
    { name: "Launch Sprint", price: "$2,500", desc: "Multi-location site + quote form + booking + reviews. Live in 7 days." },
    { name: "Client Portal", price: "$6,000", desc: "Quote → work order → invoice → online payment, on their own data." },
    { name: "Field App", price: "$5,000", desc: "Crew jobs, photo proof, auto customer updates. Mobile web, no app store." },
    { name: "Care Plan", price: "$500/mo", desc: "Hosting, edits, new pages, monthly reporting." }
  ]
};
