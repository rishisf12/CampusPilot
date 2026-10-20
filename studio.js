/* Lead desk logic: filters, one-click outreach scripts, mockup links. */
(function () {
  var P = window.PROSPECTS || [];
  var S = window.STUDIO || {};
  var app = document.getElementById("app");

  var PRICE = { broken: 4000, high: 3000, medium: 2000, low: 2500 };

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]; }); }

  function mockupUrl(id) { return location.href.replace(/[^/]*$/, "") + "mockup.html?b=" + encodeURIComponent(id); }

  function callScript(p) {
    return "Hi, is this " + p.name + "? My name is " + (S.owner || "[your name]") + ", I'm a developer with " + (S.name || "Vibe Studio") +
      ". Sorry to bother you directly.\n\n" +
      "I came across " + p.name + " on Google and I noticed something: " + p.pitch + "\n\n" +
      "I already put together a quick concept of what a fixed site would look like for " + p.name +
      " — free, no strings. It takes 20 seconds to click through:\n" + mockupUrl(p.id) +
      "\n\nCan I send it to your email, or would you rather I just talk you through it here?\n\n" +
      "(If it's easier: " + (p.phone || p.email || "your contact form") + " is right here.)";
  }

  function emailScript(p) {
    return "Subject: " + p.name + " — quick fix for your website\n\n" +
      "Hi " + (S.owner || "there") + ",\n\n" +
      "I'm " + (S.owner || "[your name]") + " from " + (S.name || "Vibe Studio") + ". I build websites for small businesses.\n\n" +
      "I came across " + p.name + " and noticed: " + p.pitch + "\n\n" +
      "I've already designed a concept for " + p.name + " — real name, real services, your number, quote form, booking and reviews:\n" +
      mockupUrl(p.id) + "\n\n" +
      "Worth 15 minutes to see? If you like it, the live site is " +
      "$" + (PRICE[p.severity] || 2500).toLocaleString() + " and I can have it live in 7 days. 50% to start, " +
      "your domain and hosting in your name, 30 days of free fixes after launch.\n\n" +
      "If it's not a fit, no problem — the mockup is yours to keep.\n\n" +
      "Best,\n" + (S.owner || "[your name]") + "\n" + (S.email || "hello@yourstudio.com") + " · " + (S.phone || "[phone]");
  }

  function toast(msg) {
    var t = document.getElementById("toast");
    t.textContent = msg; t.classList.add("show");
    setTimeout(function () { t.classList.remove("show"); }, 1800);
  }
  function copy(text, label) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { toast(label + " copied"); }, function () { fallback(text, label); });
    } else fallback(text, label);
  }
  function fallback(text, label) {
    var ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); toast(label + " copied"); } catch (e) { toast("Copy failed — select manually"); }
    document.body.removeChild(ta);
  }

  function card(p) {
    var contact = [];
    if (p.phone) contact.push("<b>Phone:</b> " + esc(p.phone));
    if (p.email) contact.push("<b>Email:</b> " + esc(p.email));
    if (!p.phone && !p.email) contact.push("<b>Route:</b> no email/phone found on site — open their contact page and use the form");
    if (p.address) contact.push("<b>Address:</b> " + esc(p.address));
    if (p.license) contact.push("<b>Licence:</b> " + esc(p.license));
    var owner = (window.OWNERS || {})[p.id];
    if (owner) contact.push("<b>Decision-maker:</b> " + esc(owner));
    return '<article class="lead ' + p.severity + '">' +
      '<div class="lhead"><div style="flex:1;min-width:210px">' +
      '<div class="lname">' + esc(p.name) + '</div>' +
      '<div class="lmeta">' + esc(p.tradeLabel) + ' · ' + esc(p.city) + ', ' + esc(p.state) + ' · ' + esc(p.website.replace(/^https?:\/\//, "")) + '</div>' +
      '</div><span class="chip ' + p.severity + '">' + p.severity + '</span></div>' +
      '<ul class="lissues">' + p.issues.map(function (i) { return '<li>' + esc(i) + '</li>'; }).join("") + '</ul>' +
      '<div class="contact">' + contact.join("<br>") + '</div>' +
      '<div class="lactions">' +
      '<a class="abtn primary" target="_blank" rel="noopener" href="' + mockupUrl(p.id) + '">Open their mockup</a>' +
      '<button class="abtn" data-copy="call" data-id="' + p.id + '">Copy call script</button>' +
      '<button class="abtn" data-copy="email" data-id="' + p.id + '">Copy email</button>' +
      '<button class="abtn" data-copy="link" data-id="' + p.id + '">Copy mockup link</button>' +
      '<a class="abtn" target="_blank" rel="noopener" href="' + esc(p.website) + '">See their site</a>' +
      '</div></article>';
  }

  function render() {
    var sev = document.getElementById("f-sev").value;
    var trade = document.getElementById("f-trade").value;
    var q = document.getElementById("f-q").value.trim().toLowerCase();
    var list = P.filter(function (p) {
      if (sev !== "all" && p.severity !== sev) return false;
      if (trade !== "all" && p.trade !== trade) return false;
      if (q && (p.name + " " + p.city + " " + p.state + " " + p.tradeLabel).toLowerCase().indexOf(q) === -1) return false;
      return true;
    });
    document.getElementById("list").innerHTML = list.length
      ? list.map(card).join("")
      : '<div class="lead low"><div class="lname">No matches</div><div class="lmeta">Clear the filters.</div></div>';
    document.getElementById("shown").textContent = list.length + " of " + P.length + " leads shown";
  }

  var trades = {};
  P.forEach(function (p) { trades[p.trade] = p.tradeLabel; });

  app.innerHTML =
    '<header class="top"><div class="wrap topin">' +
    '<div class="logo">V</div><div><div class="brandt">' + esc(S.name || "Vibe Studio") + ' — Lead Desk</div>' +
    '<div class="brands">US small businesses with a broken or weak website · verified ' + new Date().toISOString().slice(0, 10) + '</div></div>' +
    '<div class="toplinks">' +
    '<a class="tbtn" href="mockup.html" target="_blank" rel="noopener">Mockup viewer</a>' +
    '<a class="tbtn" href="PROSPECTS.md" target="_blank" rel="noopener">Prospect sheet</a>' +
    '<a class="tbtn" href="prospects.csv" target="_blank" rel="noopener">CSV</a>' +
    '<a class="tbtn" href="#" id="dl">Download all scripts</a>' +
    '</div></div></header>' +

    '<main><div class="wrap">' +
    '<h1>Small businesses that need a website fixed</h1>' +
    '<p class="lede">Every lead below is a real US company whose live site was audited on ' + new Date().toISOString().slice(0, 10) +
    '. Red = the site is returning an error to visitors. Amber = the site loads but has no way to convert. ' +
    'Each one has a ready-made concept mockup you can send in under a minute.</p>' +

    '<div class="kpis">' +
    '<div class="kpi"><div class="n">' + P.length + '</div><div class="l">Verified leads</div></div>' +
    '<div class="kpi red"><div class="n">' + P.filter(function (p) { return p.severity === "broken"; }).length + '</div><div class="l">Site returning errors</div></div>' +
    '<div class="kpi amb"><div class="n">' + P.filter(function (p) { return p.severity === "high" || p.severity === "medium"; }).length + '</div><div class="l">No contact / quote form</div></div>' +
    '<div class="kpi grn"><div class="n">$' + P.reduce(function (a, p) { return a + (PRICE[p.severity] || 2500); }, 0).toLocaleString() + '</div><div class="l">Pipeline if all close</div></div>' +
    '</div>' +

    '<div class="controls">' +
    '<select id="f-sev"><option value="all">All severities</option><option value="broken">Broken (error page)</option><option value="high">High (no quote form)</option><option value="medium">Medium</option><option value="low">Low</option></select>' +
    '<select id="f-trade"><option value="all">All trades</option>' +
    Object.keys(trades).map(function (t) { return '<option value="' + t + '">' + esc(trades[t]) + '</option>'; }).join("") + '</select>' +
    '<input type="search" id="f-q" placeholder="Search name, city, state…" />' +
    '<span class="brands" id="shown"></span>' +
    '</div>' +

    '<div class="grid" id="list"></div>' +

    '<div class="panel"><h2>What you are selling</h2>' +
    '<p>Price against the contract of work, not against a website rate card. These are the four packages. Lead with the deadline, not the deliverable.</p>' +
    '<div class="offers">' + (S.offers || []).map(function (o) {
      return '<div class="offer"><div class="n">' + esc(o.name) + '</div><div class="p">' + esc(o.price) + '</div><div class="d">' + esc(o.desc) + '</div></div>';
    }).join("") + '</div></div>' +

    '<div class="panel"><h2>Rules for the call</h2><p>Do not pitch a website. Pitch the money they are losing.</p>' +
    '<div class="script">' +
    '1. Call during THEIR business hours (your 6:30–9:30 PM IST = their 9 AM–12 PM ET).\n' +
    '2. Open with the specific problem above. Not "I build websites".\n' +
    '3. Say you already made the mock. Send the link while they are on the phone.\n' +
    '4. Ask ONE question: "Where do most of your new customers come from right now?"\n' +
    '5. If the answer is referrals or the phone, you already know they need it.\n' +
    '6. Do not argue about price on the call. The mockup already set the price.\n' +
    '7. Close: "$X, live in 7 days, 50% to start, your domain in your name, 30 days free fixes."\n' +
    '8. Never build the real site before money. Mockup is free; the build is paid.' +
    '</div></div>' +

    '<div class="panel"><h2>Before you pitch a red lead</h2>' +
    '<p>403 errors can be triggered by datacenter IPs (bot protection) rather than a real outage. Open the site on your own phone, on mobile data, before you claim their site is broken. The 520 and connection-failure cases are unambiguous.</p>' +
    '<div class="script">' +
    'BROKEN (403 / blocked):  → verify on your phone first. If it 403s there too, lead with "your website is refusing visitors right now".\n' +
    'BROKEN (520 / timeout): → unambiguous. Lead with "your website is down with a server error — anyone Googling you sees an error page".\n' +
    'HIGH (no quote form):    → safe. Lead with "every job starts with a phone tag instead of a form".\n' +
    'MEDIUM (thin/stale):     → safe. Lead with "your site is one thin page with no gallery, no reviews, no booking".' +
    '</div></div>' +
    '</div></main>' +

    '<footer><div class="wrap">All business data above was read from public sources on the date shown. ' +
    'Phone numbers, emails and names come from each business\' own website. Nothing here is invented, and every mockup is labelled as a concept.</div></footer>' +
    '<div class="toast" id="toast"></div>';

  ["f-sev", "f-trade"].forEach(function (id) { document.getElementById(id).addEventListener("change", render); });
  document.getElementById("f-q").addEventListener("input", render);

  document.getElementById("list").addEventListener("click", function (e) {
    var b = e.target.closest("[data-copy]");
    if (!b) return;
    var p = P.filter(function (x) { return x.id === b.getAttribute("data-id"); })[0];
    var kind = b.getAttribute("data-copy");
    if (kind === "call") copy(callScript(p), "Call script");
    if (kind === "email") copy(emailScript(p), "Email");
    if (kind === "link") copy(mockupUrl(p.id), "Mockup link");
  });

  document.getElementById("dl").addEventListener("click", function (e) {
    e.preventDefault();
    var out = P.map(function (p) {
      return "=== " + p.name + " (" + p.city + ", " + p.state + ") ===\n" +
        "Phone: " + (p.phone || "not found") + "\nEmail: " + (p.email || "not found") + "\n" +
        "Site: " + p.website + "\nSeverity: " + p.severity + "\nIssues:\n" + p.issues.map(function (i) { return "  - " + i; }).join("\n") +
        "\n\n--- CALL SCRIPT ---\n" + callScript(p) + "\n\n--- EMAIL ---\n" + emailScript(p) + "\n";
    }).join("\n\n");
    var blob = new Blob([out], { type: "text/plain" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "outreach-scripts.txt";
    a.click();
    toast("Downloaded");
  });

  render();
})();
