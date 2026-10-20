/* Renders a concept mockup for one prospect. Usage: mockup.html?b=<id> */
(function () {
  var P = window.PROSPECTS || [];
  var STUDIO = window.STUDIO || {};
  var id = new URLSearchParams(location.search).get("b");
  var p = P.filter(function (x) { return x.id === id; })[0];

  var app = document.getElementById("app");
  if (!p) {
    app.innerHTML = '<div class="concept">No business selected. <a href="index.html">Back to the lead desk</a></div>' +
      '<div class="wrap" style="padding:60px 0"><h1>Pick a business</h1>' +
      '<p class="lede">Open <a href="index.html">the lead desk</a> and choose a company to see its mockup.</p></div>';
    return;
  }

  var pal = p.palette || ["#0f766e", "#134e4a", "#f59e0b"];
  var root = document.documentElement;
  root.style.setProperty("--primary", pal[0]);
  root.style.setProperty("--primary-dark", pal[1]);
  root.style.setProperty("--accent", pal[2]);
  document.title = p.name + " — " + p.tradeLabel;

  var phone = p.phone || "";
  var phoneHref = phone ? "tel:" + phone.replace(/[^\d+]/g, "") : "#quote";
  var initial = p.name.replace(/[^A-Za-z ]/g, "").split(" ").map(function (w) { return w[0]; }).slice(0, 2).join("").toUpperCase();

  var trust = [
    ["Licensed & Insured", "Full liability + workers comp"],
    ["Free Estimates", "No-obligation, same-week quotes"],
    [p.since ? "Since " + p.since : p.city + " local", "Serving the " + p.city + " area"],
    ["Fast Response", "Callbacks within business hours"]
  ];

  var serviceCards = (p.services || []).map(function (s, i) {
    return '<div class="card"><div class="badge">' + (i + 1) + '</div><h3>' + s + '</h3><p>' +
      'Add a short description of your ' + s.toLowerCase() + ' process, what it costs, and what area you cover.</p></div>';
  }).join("");

  var reviews = [
    ["Paste your best customer review here.", "Customer name — Neighborhood"],
    ["A second review builds trust before the first phone call.", "Customer name — Neighborhood"],
    ["Third slot. Recent reviews push older ones down, so keep it current.", "Customer name — Neighborhood"]
  ].map(function (r) {
    return '<div class="review"><div class="s">★★★★★</div><p class="ph">"' + r[0] + '"</p><div class="who">' + r[1] + '</div></div>';
  }).join("");

  var chips = [p.city + ", " + p.state, "Nearby cities", "Service area", "Areas served", "Free estimates"]
    .map(function (c) { return '<span class="chip">' + c + '</span>'; }).join("");

  app.innerHTML = [
    '<div class="concept">Concept mockup prepared by <b>' + (STUDIO.name || "Vibe Studio") + '</b> for <b>' + p.name +
      '</b> — <i>not yet a live site</i>. Real business name, phone and services; placeholder copy. <a href="index.html">Back to lead desk</a></div>',

    '<header><div class="wrap nav"><div class="brand"><span class="mark">' + initial + '</span>' + p.name + '</div>' +
      '<nav class="navlinks"><a href="#services">Services</a><a href="#why">Why us</a><a href="#reviews">Reviews</a><a href="#area">Service area</a></nav>' +
      '<a class="btn btn-primary" href="' + phoneHref + '">Call ' + (phone ? phone : 'us') + '</a></div></header>',

    '<div class="hero"><div class="wrap hero-grid"><div>' +
      '<span class="eyebrow">' + p.tradeLabel + ' · ' + p.city + ', ' + p.state + '</span>' +
      '<h1>' + (p.headline || "Dependable " + p.tradeLabel.toLowerCase() + " in " + p.city + ".") + '</h1>' +
      '<div class="stars"><span class="s">★★★★★</span><span>Google reviews widget connects here at launch</span></div>' +
      '<p class="lede">' + (p.pitch || "Call today for a free, no-obligation estimate.") + '</p>' +
      '<div class="cta-row"><a class="btn btn-accent" href="' + phoneHref + '">Call now</a>' +
      '<a class="btn btn-ghost" href="#quote">Get a free estimate</a></div>' +
      '</div>' +
      '<div class="hero-panel">' + trust.map(function (t) {
        return '<div class="row"><span class="tick">✓</span><div><div class="t">' + t[0] + '</div><div class="d">' + t[1] + '</div></div></div>';
      }).join("") + '</div>' +
      '</div></div>',

    '<div class="trust"><div class="wrap trust-grid">' + trust.map(function (t) {
      return '<div><span>★</span>' + t[0] + '</div>';
    }).join("") + '</div></div>',

    '<section id="services"><div class="wrap"><span class="pill">What we do</span><h2>Services</h2>' +
      '<p class="sub">Six clear service cards, each one landing on its own page so you rank for "' + p.trade.toLowerCase() + ' near me".</p>' +
      '<div class="grid-3 six">' + serviceCards + '</div></div></section>',

    '<section class="alt" id="why"><div class="wrap"><span class="pill">Why us</span><h2>Why customers pick you</h2>' +
      '<p class="sub">Three proof points, each with a number. Replace the placeholders with your real ones.</p>' +
      '<div class="grid-3">' +
      '<div class="card"><div class="badge">01</div><h3>Real proof</h3><p>Your real review count, real warranties, real licence number.</p></div>' +
      '<div class="card"><div class="badge">02</div><h3>Real speed</h3><p>Book online in under a minute. No phone tag, no waiting for an answer.</p></div>' +
      '<div class="card"><div class="badge">03</div><h3>Real local</h3><p>Service-area pages for every neighbourhood you actually cover.</p></div>' +
      '</div></div></section>',

    '<section id="reviews"><div class="wrap"><span class="pill">Social proof</span><h2>What your customers say</h2>' +
      '<p class="sub">Live Google reviews pull in automatically and rotate so the newest one shows first.</p>' +
      '<div class="grid-3">' + reviews + '</div></div></section>',

    '<section class="alt" id="area"><div class="wrap"><span class="pill">Local SEO</span><h2>Service area</h2>' +
      '<p class="sub">One page per town you serve — this is what wins the map pack and the "near me" searches.</p>' +
      '<div class="chips">' + chips + '</div></div></section>',

    '<section id="quote"><div class="wrap"><div class="quote"><h2>Get a free estimate</h2>' +
      '<p class="sub">Fill this in and we call you back within business hours. No obligation.</p>' +
      '<form class="form" id="qf"><div class="row2">' +
      '<div><label for="n">Your name</label><input id="n" name="n" placeholder="Jane Smith" required></div>' +
      '<div><label for="p">Phone</label><input id="p" name="p" placeholder="(555) 000-0000" required></div></div>' +
      '<div><label for="s">What do you need?</label><select id="s" name="s">' +
      (p.services || []).map(function (x) { return '<option>' + x + '</option>'; }).join("") + '</select></div>' +
      '<div><label for="m">Anything else?</label><textarea id="m" name="m" rows="3" placeholder="Tell us about the job, your timeline, and the neighbourhood."></textarea></div>' +
      '<button class="btn btn-accent" type="submit">Request my free estimate</button></form>' +
      '<div class="done" id="done">✓ Request received. We call you back within business hours. <br><small>Demo only — this form is not connected to a live inbox.</small></div>' +
      '</div></div></section>',

    '<footer><div class="wrap"><div class="fgrid">' +
      '<div><b>' + p.name + '</b>' + (p.address ? p.address + '<br>' : '') + p.city + ', ' + p.state +
        (p.license ? '<br>Licence: ' + p.license : '') + '</div>' +
      '<div><b>Contact</b>' + (phone ? 'Phone: ' + phone + '<br>' : '') + (p.email ? 'Email: ' + p.email + '<br>' : '') +
        'Mon–Sat 7:00 AM – 6:00 PM</div>' +
      '<div><b>Services</b>' + (p.services || []).slice(0, 4).join('<br>') + '</div>' +
      '</div>' +
      '<div class="foot-note">Concept mockup by ' + (STUDIO.name || "Vibe Studio") + ' for ' + p.name +
        '. Business name, phone and services are real; all copy and reviews are placeholders. This page is a proposal, not a live website.</div>' +
      '</div></footer>'
  ].join("");

  var qf = document.getElementById("qf");
  if (qf) qf.addEventListener("submit", function (e) {
    e.preventDefault();
    qf.style.display = "none";
    document.getElementById("done").classList.add("show");
  });
})();
